"""Weighted least-squares driver on scipy's Trust Region Reflective solver.

Minimises  S(θ) = Σ_i w_i (y_obs,i − y_calc,i(θ))²,  w_i = 1/σ_i²
(Rietveld 1969; weights per counting statistics — see PatternData.sig).

The Jacobian is assembled column-by-column, preferring exact work over
full-model finite differences:

* **linear columns** — Chebyshev background coefficients (design-matrix rows);
* **peak-chain columns** — every parameter whose effect flows through the
  per-peak scalars (position, Γ, η, intensity): cell constants, zero shift,
  displacement/transparency, Caglioti U V W, size/strain X Y, scales,
  occupancies, Biso, polarization, emission-line weights.  The expensive
  per-point part uses the analytic profile derivatives
  (``CompiledModel.derivative_bases``); the per-reflection scalar derivatives
  are finite-differenced through ``phase_peaks`` (cheap — no per-point work);
* **site-DOF columns** — Wyckoff coordinate and anisotropic-ADP DOFs, whose
  ∂|F|²/∂p is analytic over the frozen op subsets and chains through the
  site's constraint directions;
* **axial columns** — S/L, H/L through the analytic node-weighted bases;
* **plain forward differences** — anything else (fallback only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import least_squares

from ..backend import get_backend
from ..backend.linalg64 import get_precision_policy, require_fp64, to_host_fp64
from ..crystallography.adp import U_NAMES
from ..model.forward import CompiledModel, DerivativeBases
from ..model.restraints import restraint_partials
from ..params.transforms import dphys_dinternal
from ..params.vector import ParameterTable

if TYPE_CHECKING:
    from ..params.multi import MultiParameterTable

#: Wyckoff site DOFs — coordinates (``dof``, tied to x, y, z) and anisotropic
#: ADPs (``adp``, tied to the six U^ij).  Both get analytic columns that chain
#: the structure-factor derivative through the site's constraint directions.
_STRUCTURAL_PATH = re.compile(r"^phases\.(\d+)\.atoms\.(\d+)\.(dof|adp)\.\d+$")
#: March-Dollase coefficient — an analytic intensity-multiplier column
#: (``po_intensity_grad``), not the peak-chain FD path.
_PO_PATH = re.compile(r"^phases\.(\d+)\.preferred_orientation\.r$")


@dataclass
class LSQOutcome:
    theta: np.ndarray            # table free vector only (never the aux block)
    cost_initial: float
    cost_final: float
    n_iterations: int
    status: str  # "converged" | "max_iter" | "diverged"
    jac: np.ndarray | None       # table columns only (guards read this)
    stderr_internal: np.ndarray | None
    correlation: np.ndarray | None
    #: length of the appended Pawley intensity block (its esds land on
    #: ``model.pawley.stderr``, its values in the per-phase buffers)
    n_aux: int = 0


def _lebail_snapshot(model: CompiledModel) -> list[np.ndarray] | None:
    """Le Bail intensities frozen for one solve (taken at closure build).

    They are constant during a least-squares run — ``lebail_update`` only runs
    between solves — so snapshotting here is what lets the residual never read
    the mutable per-phase buffers (the purity contract).
    """
    if model.mode != "lebail":
        return None
    return [np.asarray(cp.hkl_intensity, dtype=np.float64) for cp in model.phases]


def _make_residual(model: CompiledModel, table: ParameterTable):
    """Weighted residual, optionally augmented with a Pawley intensity block.

    In Pawley mode θ = [table θ | per-hkl intensities]; the intensity tail is
    split into per-phase slices and passed *through* the evaluation (never
    written to the buffers — those are committed once, post-solve), and the
    overlap-restraint rows are appended after the background penalty rows.
    """
    sqrt_w = 1.0 / model.sigma
    n_table = len(table.free_paths)
    xp = get_backend()
    fixed_intens = _lebail_snapshot(model)

    def residual(theta: np.ndarray) -> np.ndarray:
        if model.pawley is not None:
            intens = model.split_pawley_intensities(theta[n_table:])
            values = table.decode(theta[:n_table])
        else:
            intens = fixed_intens
            values = table.decode(theta)
        r = sqrt_w * (model.y_obs - model.evaluate(values, intens))
        parts = [r]
        pen = model.penalty_residual(values)
        if pen is not None:
            parts.append(pen)
        if model.pawley is not None:
            rpen = model.pawley_restraint_residual(theta[n_table:])
            if rpen is not None:
                parts.append(rpen)
        rr = model.restraint_residual(values)
        if rr is not None:
            parts.append(rr)
        return parts[0] if len(parts) == 1 else xp.concatenate(parts)

    return residual


def _peak_chain_column(model: CompiledModel, table: ParameterTable,
                       bases: DerivativeBases, theta: np.ndarray,
                       values: dict[str, float], c: int, path: str,
                       intensities: list[np.ndarray] | None = None) -> np.ndarray:
    """∂y/∂θ_c via the analytic bases + per-reflection scalar FD.

    Only the phases the path touches are re-derived (``phases.2.…`` leaves
    the others' scalars untouched; instrument paths touch all).
    ``intensities`` carries the lebail/pawley per-hkl vectors — the perturbed
    ``phase_peaks`` must see the same intensities as the expansion point.
    """
    h = 1e-6 * max(1.0, abs(theta[c]))
    tp = theta.copy()
    tp[c] += h
    values_p = table.decode(tp)
    if path.startswith("phases."):
        affected = [int(path.split(".")[1])]
    else:
        affected = range(len(model.phases))

    xp = get_backend()
    dy = xp.zeros_like(model.tt)
    for ip in affected:
        peaks_p = model.phase_peaks(
            ip, values_p, None if intensities is None else intensities[ip])
        peaks_0 = bases.peaks[ip]
        for (il, k, i0, i1, omega, d_pos, d_gamma, d_eta, _dsl, _dhl) in bases.entries[ip]:
            pos0, gam0, eta0, int0 = peaks_0[il]
            pos1, gam1, eta1, int1 = peaks_p[il]
            if not (np.isfinite(pos1[k]) and np.isfinite(pos0[k])):
                continue
            d_i = (int1[k] - int0[k]) / h
            d_p = (pos1[k] - pos0[k]) / h
            d_g = (gam1[k] - gam0[k]) / h
            d_e = (eta1[k] - eta0[k]) / h
            # one window_add per term keeps the pre-shim accumulation order
            if d_i != 0.0:
                dy = xp.window_add(dy, i0, i1, d_i * omega)
            if int0[k] != 0.0:
                if d_p != 0.0:
                    dy = xp.window_add(dy, i0, i1, (int0[k] * d_p) * d_pos)
                if d_g != 0.0:
                    dy = xp.window_add(dy, i0, i1, (int0[k] * d_g) * d_gamma)
                if d_e != 0.0:
                    dy = xp.window_add(dy, i0, i1, (int0[k] * d_e) * d_eta)
    return dy


def _structural_column(model: CompiledModel, table: ParameterTable,
                       bases: DerivativeBases, values: dict[str, float],
                       c: int, ip: int, j: int, rows: tuple[str, ...],
                       grad) -> np.ndarray:
    """∂y/∂θ_c for a coordinate or ADP DOF: only the intensity scalar moves.

    The constraint direction ∂p/∂θ_c is read off the affine constraint block
    (the DOF's column of C restricted to the atom's ``rows``), so the analytic
    column follows whatever site-symmetry basis WP-0301 wired — displacement
    directions for x, y, z; U^ij patterns for the six ADP components.
    """
    xp = get_backend()
    C, _ = table.constraint_block()
    coeffs = np.array([C[table._paths[f"phases.{ip}.atoms.{j}.{name}"], c]
                       for name in rows], dtype=np.float64)
    dint = grad(ip, j, coeffs, values)
    dy = xp.zeros_like(model.tt)
    for (il, k, i0, i1, omega, *_rest) in bases.entries[ip]:
        v = dint[il][k]
        if v != 0.0:
            dy = xp.window_add(dy, i0, i1, v * omega)
    return dy


def _po_column(model: CompiledModel, bases: DerivativeBases,
               values: dict[str, float], ip: int) -> np.ndarray:
    """∂y/∂r for the March coefficient: only the intensity scalar moves.

    ``po_intensity_grad`` supplies the analytic per-(line, reflection)
    ∂intensity/∂r (P is a pure multiplier, so positions and widths are
    untouched); it is applied to the same frozen profile bases the forward
    model uses.  The softplus chain factor ∂r/∂θ is applied by the caller.
    """
    xp = get_backend()
    dy = xp.zeros_like(model.tt)
    dint = model.po_intensity_grad(ip, values)
    if dint is None:
        return dy
    for (il, k, i0, i1, omega, *_rest) in bases.entries[ip]:
        v = dint[il][k]
        if v != 0.0:
            dy = xp.window_add(dy, i0, i1, v * omega)
    return dy


def _axial_column(model: CompiledModel, bases: DerivativeBases,
                  which: int, dpdu: float) -> np.ndarray:
    """∂y/∂θ_c for S/L (which=8) or H/L (which=9) from the node-FD bases."""
    xp = get_backend()
    dy = xp.zeros_like(model.tt)
    for ip, rows in enumerate(bases.entries):
        for row in rows:
            il, k, i0, i1 = row[0], row[1], row[2], row[3]
            d_ax = row[which]
            if d_ax is None:
                continue
            intensity = bases.peaks[ip][il][3][k]
            if intensity != 0.0:
                dy = xp.window_add(dy, i0, i1, (intensity * dpdu) * d_ax)
    return dy


def _pawley_intensity_columns(model: CompiledModel, bases: DerivativeBases,
                              values: dict[str, float], sqrt_w: np.ndarray,
                              J: np.ndarray, n_table: int, n_below: int) -> None:
    """Exact analytic columns for the Pawley intensity block.

    ``I_k`` enters y linearly and only through its own peak: ∂y/∂I_k =
    Σ_lines w_l·Ω_lk on the reflection's window (the same argument as the
    background coefficients — take the exact column, never FD).  The overlap
    restraint rows are ∂(R·I)/∂I = R, appended below the data (and background
    penalty) rows.
    """
    n_lines = len(model.line_wavelengths)
    w_lines = [values[f"instrument.source.lines.{il}.weight"] for il in range(n_lines)]
    for ip, (a, _b) in enumerate(model.pawley.phase_slices):
        for (il, k, i0, i1, omega, *_rest) in bases.entries[ip]:
            J[i0:i1, n_table + a + k] += -sqrt_w[i0:i1] * (w_lines[il] * omega)
    if model.pawley.restraint is not None:
        # bound the write to exactly the Pawley-restraint stripe: soft-restraint
        # rows (WP-0406) may sit below it, though Pawley + geometry restraints
        # never coexist (restraints are Rietveld-only)
        n_res = model.pawley.restraint.shape[0]
        J[n_below:n_below + n_res, n_table:] = model.pawley.restraint


def _make_jacobian(model: CompiledModel, table: ParameterTable):
    """Mixed analytic/FD Jacobian of the residual w.r.t. the internal vector.

    In Pawley mode the vector is [table θ | intensities]; the table columns are
    built exactly as for Rietveld/Le Bail, then the intensity block gets its own
    exact linear columns (:func:`_pawley_intensity_columns`).
    """
    sqrt_w = 1.0 / model.sigma
    free = table.free_paths
    n_table = len(free)
    n_data = len(model.tt)
    n_bkg_pen = 0 if model.bkg_penalty is None else model.bkg_penalty.shape[0]
    n_res = (0 if model.pawley is None or model.pawley.restraint is None
             else model.pawley.restraint.shape[0])
    n_restraint = 0 if model.restraints is None else model.restraints.n_rows
    n_rows = n_data + n_bkg_pen + n_res + n_restraint

    bkg_cols = {path: n for n, path in enumerate(model.bkg_paths)}
    axial_paths = {"instrument.geometry.axial_sl": 8, "instrument.geometry.axial_hl": 9}

    def dpdu_of(c: int, theta: np.ndarray) -> float:
        e = table.entries[table._paths[free[c]]]
        return dphys_dinternal(float(theta[c]), e.transform)

    fixed_intens = _lebail_snapshot(model)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        if model.pawley is not None:
            intens = model.split_pawley_intensities(theta[n_table:])
            theta_t = theta[:n_table]
        else:
            intens = fixed_intens
            theta_t = theta
        values = table.decode(theta_t)
        J = np.zeros((n_rows, len(theta)), dtype=np.float64)
        fd_cols = []
        bases: DerivativeBases | None = None

        def get_bases() -> DerivativeBases:
            nonlocal bases
            if bases is None:
                bases = model.derivative_bases(values, intens)
            return bases

        for c, path in enumerate(free):
            if path in bkg_cols:
                # y is linear in the coefficient: ∂y/∂c_n = basis row; the
                # penalty rows are linear too (√λ·D₂), chain-ruled through
                # the transform for the (softplus-bounded) air term
                n = bkg_cols[path]
                dpdu = dpdu_of(c, theta_t)
                J[:n_data, c] = -sqrt_w * model.bkg_design[n] * dpdu
                if n_bkg_pen:
                    J[n_data:n_data + n_bkg_pen, c] = model.bkg_penalty[:, n] * dpdu
            elif path in axial_paths:
                b = get_bases()
                if b.axial_ok:
                    J[:n_data, c] = -sqrt_w * _axial_column(
                        model, b, axial_paths[path], dpdu_of(c, theta_t))
                else:
                    fd_cols.append(c)
            elif (dof := _STRUCTURAL_PATH.match(path)) and model.mode == "rietveld":
                rows, grad = (("x", "y", "z"), model.coordinate_intensity_grad) \
                    if dof.group(3) == "dof" else (U_NAMES, model.adp_intensity_grad)
                J[:n_data, c] = -sqrt_w * dpdu_of(c, theta_t) * _structural_column(
                    model, table, get_bases(), values, c,
                    int(dof.group(1)), int(dof.group(2)), rows, grad)
            elif (po := _PO_PATH.match(path)) and model.mode == "rietveld":
                J[:n_data, c] = -sqrt_w * dpdu_of(c, theta_t) * _po_column(
                    model, get_bases(), values, int(po.group(1)))
            elif model.scalar_chain_supported(path):
                J[:n_data, c] = -sqrt_w * _peak_chain_column(
                    model, table, get_bases(), theta_t, values, c, path, intens)
            else:
                fd_cols.append(c)

        if fd_cols:
            r0 = sqrt_w * (model.y_obs - model.evaluate(values, intens))
            for c in fd_cols:
                h = 1e-6 * max(1.0, abs(theta_t[c]))
                tp = theta_t.copy()
                tp[c] += h
                rp = sqrt_w * (model.y_obs - model.evaluate(table.decode(tp), intens))
                J[:n_data, c] = (rp - r0) / h

        if model.pawley is not None:
            _pawley_intensity_columns(model, get_bases(), values, sqrt_w, J,
                                      n_table, n_data + n_bkg_pen)

        if model.restraints is not None and n_table:
            # One unconditional matrix block below the data/penalty/Pawley rows:
            # ∂row/∂θ_c = (R_phys @ C)[i,c]·dφ/du[c], since decode gives
            # p = C·to_physical(θ) + d.  Rietveld-only (n_res is then 0), and the
            # rows touch table θ only — no Pawley-intensity columns.
            restr0 = n_data + n_bkg_pen + n_res
            r_phys = restraint_partials(model.restraints, values, table)
            cmat = table.constraint_block()[0].toarray()  # C small: dense is fine
            dpdu = np.array([dpdu_of(c, theta_t) for c in range(n_table)],
                            dtype=np.float64)
            J[restr0:restr0 + n_restraint, :n_table] = (r_phys @ cmat) * dpdu
        return J

    return jacobian


def _jacobian_for(model, table, backend: str):
    """The Jacobian callable for ``backend`` (lazy import keeps numpy pure).

    The jax callable produces the same fp64 host array in the same row/column
    layout as :func:`_make_jacobian`; the residual used for cost/statistics
    and the TRF solve stay numpy either way (WP-0402).

    This is also the assembly's exit point, so it is where the WP-0403
    mixed-precision policy is applied: whichever backend built the columns,
    they cross ``linalg64``'s host boundary here — cast to fp64, then reduced
    per column if (and only if) a policy asked for it.  With the default fp64
    policy the wrapper is a plain ``np.asarray``, so the numpy path is
    unchanged.
    """
    if backend == "jax":
        from ..backend.jax_backend import make_jax_jacobian

        inner = make_jax_jacobian(model, table)
    elif backend == "numpy":
        inner = _make_jacobian(model, table)
    else:
        raise ValueError(f"unknown backend {backend!r}; available: numpy, jax")

    def jacobian(theta: np.ndarray) -> np.ndarray:
        # policy read per call, not per closure build: a `with precision_policy`
        # block around a refine must take effect on an already-built solver
        return get_precision_policy().cast_columns(inner(theta))

    return jacobian


def run_least_squares(model: CompiledModel, table: ParameterTable,
                      *, max_iter: int = 100, ftol: float = 1e-9,
                      compute_uncertainties: bool = True,
                      events=None, stage: str = "",
                      backend: str = "numpy") -> LSQOutcome:
    residual = _make_residual(model, table)
    jacobian = _jacobian_for(model, table, backend)

    if events is not None:
        # scipy TRF has no per-iteration callback, so the residual closure is
        # the hook; the emitted dict is plain floats (no pydantic here)
        inner = residual
        counter = {"n": 0}

        def residual(theta: np.ndarray):
            r = inner(theta)
            counter["n"] += 1
            events.emit("eval", stage=stage, n_eval=counter["n"],
                        cost=0.5 * float(r @ r))
            return r
    n_table = len(table.free_paths)
    x0 = table.x0()
    lo, hi = table.bounds()
    if model.pawley is not None:
        # append the per-hkl intensity block (identity transform, bounded ≥ 0)
        plo, phi = model.pawley_bounds()
        x0 = np.concatenate([x0, model.pawley_x0()])
        lo = np.concatenate([lo, plo])
        hi = np.concatenate([hi, phi])
    n_aux = len(x0) - n_table
    # TRF requires x0 strictly inside the bounds
    x0 = np.clip(x0, lo + 1e-12, hi - 1e-12) if len(x0) else x0

    r0 = residual(x0)
    # invariant 2: whatever built the columns, the residual is fp64 on host —
    # checked once per solve, not per iteration
    require_fp64(r0, "least-squares residual")
    cost0 = 0.5 * float(r0 @ r0)
    if len(x0) == 0:
        return LSQOutcome(x0, cost0, cost0, 0, "converged", None, None, None)

    res = least_squares(residual, x0, jac=jacobian, bounds=(lo, hi), method="trf",
                        ftol=ftol, xtol=1e-12, gtol=1e-12, max_nfev=max_iter * max(len(x0), 1))
    status = "converged" if res.status > 0 else ("max_iter" if res.status == 0 else "diverged")

    # esds from the *full* augmented covariance (table ↔ intensity correlation
    # feeds the table esds too), then split: table columns stay in the outcome,
    # the intensity tail lands on the model's Pawley block.
    stderr = corr = None
    if compute_uncertainties and res.jac is not None and len(res.fun) > len(res.x):
        stderr_full, corr_full = covariance_estimates(res.jac, res.fun, len(res.x),
                                                       n_data=len(model.tt))
        stderr, corr = stderr_full[:n_table], corr_full[:n_table, :n_table]
        if model.pawley is not None:
            model.pawley.stderr = stderr_full[n_table:]
    if model.pawley is not None:
        # pin the final refined intensities into the per-phase buffers (the last
        # residual eval is not guaranteed to sit exactly at the solution)
        model.set_pawley_intensities(res.x[n_table:])
    jac_table = np.asarray(res.jac)[:, :n_table] if res.jac is not None else None
    return LSQOutcome(res.x[:n_table], cost0, float(res.cost), int(res.nfev), status,
                      jac_table, stderr, corr, n_aux=n_aux)


def run_multi_least_squares(models: list[CompiledModel],
                            mtable: "MultiParameterTable", *,
                            weights: list[float] | None = None,
                            max_iter: int = 100, ftol: float = 1e-9,
                            compute_uncertainties: bool = True,
                            backend: str = "numpy") -> LSQOutcome:
    """Joint TRF solve of several histograms stacked into one residual (WP-0308).

    Each histogram keeps its own compiled model (⇒ its own frozen hkl list,
    windows, FCJ node counts) and its own :class:`ParameterTable`; the combined
    free vector θ threads through them via ``mtable``'s column map, so a *shared*
    structural column (cell, coordinates, ADPs …) receives Jacobian
    contributions from *every* histogram — that is what refines the shared
    quantity better than any single pattern could.

    Row layout is [all histograms' data rows] then [all histograms' background-
    penalty rows], so :func:`covariance_estimates` (which treats the first
    ``n_data`` rows as data for χ² and the Bérar-Lelann factor) is reused
    verbatim.  A per-histogram scalar weight ``w_h`` scales both that
    histogram's data and its penalty rows by ``√w_h`` — keeping the smoothness
    prior's strength relative to the data fixed; default unit weights leave the
    residual identical to N independent solves sharing the structure.
    """
    n_hist = len(models)
    if any(m.restraints is not None for m in models):
        # The stacked layout sizes the below-data slot from the background
        # penalty rows only; a per-histogram restraint stripe would need a third
        # offset row-block.  Deferred — see docs/wp/0308 ### Inherited (WP-0406).
        raise NotImplementedError(
            "soft restraints are not yet supported in a multi-histogram joint "
            "refinement; run each restrained phase in a single-histogram fit")
    weights = [1.0] * n_hist if weights is None else list(weights)
    if len(weights) != n_hist:
        raise ValueError("weights must have one entry per histogram")
    sqrt_w = [float(np.sqrt(w)) for w in weights]

    residuals = [_make_residual(m, t) for m, t in zip(models, mtable.tables, strict=True)]
    jacobians = [_jacobian_for(m, t, backend)
                 for m, t in zip(models, mtable.tables, strict=True)]
    n_data = [len(m.tt) for m in models]
    n_pen = [0 if m.bkg_penalty is None else m.bkg_penalty.shape[0] for m in models]
    data_off = np.concatenate([[0], np.cumsum(n_data)])
    n_data_total = int(data_off[-1])
    pen_off = n_data_total + np.concatenate([[0], np.cumsum(n_pen)])
    n_rows = int(pen_off[-1])
    n_cols = len(mtable.free_paths)

    def residual(theta: np.ndarray) -> np.ndarray:
        thetas = mtable.split(theta)
        data_parts: list[np.ndarray] = []
        pen_parts: list[np.ndarray] = []
        for h in range(n_hist):
            r = residuals[h](thetas[h])
            data_parts.append(sqrt_w[h] * r[:n_data[h]])
            if n_pen[h]:
                pen_parts.append(sqrt_w[h] * r[n_data[h]:])
        return np.concatenate(data_parts + pen_parts) if n_rows else np.zeros(0)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        thetas = mtable.split(theta)
        J = np.zeros((n_rows, n_cols), dtype=np.float64)
        for h in range(n_hist):
            Jh = jacobians[h](thetas[h])
            cm = mtable.col_map(h)
            do = int(data_off[h])
            J[do:do + n_data[h], cm] = sqrt_w[h] * Jh[:n_data[h]]
            if n_pen[h]:
                po = int(pen_off[h])
                J[po:po + n_pen[h], cm] = sqrt_w[h] * Jh[n_data[h]:]
        return J

    x0 = mtable.x0()
    lo, hi = mtable.bounds()
    x0 = np.clip(x0, lo + 1e-12, hi - 1e-12) if len(x0) else x0
    r0 = residual(x0)
    require_fp64(r0, "least-squares residual")
    cost0 = 0.5 * float(r0 @ r0)
    if n_cols == 0:
        return LSQOutcome(x0, cost0, cost0, 0, "converged", None, None, None)

    res = least_squares(residual, x0, jac=jacobian, bounds=(lo, hi), method="trf",
                        ftol=ftol, xtol=1e-12, gtol=1e-12,
                        max_nfev=max_iter * max(len(x0), 1))
    status = "converged" if res.status > 0 else ("max_iter" if res.status == 0 else "diverged")

    stderr = corr = None
    if compute_uncertainties and res.jac is not None and len(res.fun) > len(res.x):
        stderr, corr = covariance_estimates(res.jac, res.fun, len(res.x),
                                            n_data=n_data_total)
    jac_data = np.asarray(res.jac)[:n_data_total] if res.jac is not None else None
    return LSQOutcome(res.x, cost0, float(res.cost), int(res.nfev), status,
                      jac_data, stderr, corr)


def covariance_estimates(jac: np.ndarray, fun: np.ndarray, n_free: int,
                         n_data: int | None = None
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Esds and correlation matrix from the weighted Jacobian at the solution.

    Cov = χ²_red · (JᵀJ)⁻¹ with χ²_red = Σr²/(N−P); esd_i = √Cov_ii, then
    multiplied by the Bérar-Lelann serial-correlation factor (Bérar & Lelann,
    1991, J. Appl. Cryst. 24, 1 — see ``statistics.berar_lelann_factor``);
    the factor cancels in the correlation matrix.
    A pseudo-inverse guards against singular normal matrices.

    With P-spline penalty rows appended (rows beyond ``n_data``), JᵀJ keeps
    them — (J_dᵀJ_d + λD₂ᵀD₂)⁻¹ is the regularised covariance — but χ² and
    the serial-correlation factor are evaluated on the *data* rows only
    (run-of-sign statistics on penalty rows would be meaningless).

    The solve is fp64 unconditionally (architecture invariant 2): cond(JᵀJ) =
    cond(J)², so forming and inverting the normal matrix is the step reduced
    precision can never take.  ``to_host_fp64`` is that boundary — a Jacobian
    whose columns were computed at fp32 is upcast here before JᵀJ, while the
    residual is *required* to have been fp64 all along.
    """
    from .statistics import berar_lelann_factor

    data = fun if n_data is None else fun[:n_data]
    require_fp64(data, "residual entering the covariance solve")
    jac = to_host_fp64(jac)
    JTJ = jac.T @ jac
    chi2_red = float(data @ data) / max(len(data) - n_free, 1)
    cov = np.linalg.pinv(JTJ) * chi2_red
    diag = np.sqrt(np.maximum(np.diag(cov), 0.0)) * berar_lelann_factor(data)
    denom = np.outer(diag, diag)
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.where(denom > 0, cov / denom, 0.0)
    return diag, corr
