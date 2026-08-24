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

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import least_squares

from ..backend import get_backend
from ..backend.api import TORCH_DEVICES
from ..backend.linalg64 import get_precision_policy, require_fp64
from ..crystallography.adp import U_NAMES
from ..crystallography.stephens import S_NAMES
from ..model import rows as row_layout
from ..model.forward import PHASE_SUPPORT_SIGMA, CompiledModel, DerivativeBases
from ..model.forward import accumulate_planes as _accumulate
from ..model.restraints import restraint_partials
from ..params.transforms import dphys_dinternal
from ..params.vector import ParameterTable
from .cancel import RefinementCancelled

if TYPE_CHECKING:
    from ..params.multi import MultiParameterTable
    from . import lm as lm_mod

#: Available minimisers.  ``"trf"`` is scipy's Trust Region Reflective — the
#: default, the reference, and the driver every shipped acceptance number was
#: measured with.  ``"lm"`` is the bounded Levenberg-Marquardt of
#: :mod:`.lm` (WP-0601), whose reason to exist is constraint vocabulary rather
#: than speed: bounds enforced inside the linear solve, and linear inequalities
#: on *functionals* of θ (the Stephens strain positivity cone) that a box
#: cannot express.
SOLVERS = ("trf", "lm")

#: Wyckoff site DOFs — coordinates (``dof``, tied to x, y, z) and anisotropic
#: ADPs (``adp``, tied to the six U^ij).  Both get analytic columns that chain
#: the structure-factor derivative through the site's constraint directions.
_STRUCTURAL_PATH = re.compile(r"^phases\.(\d+)\.atoms\.(\d+)\.(dof|adp)\.\d+$")
#: March-Dollase coefficient — an analytic intensity-multiplier column
#: (``po_intensity_grad``), not the peak-chain FD path.
_PO_PATH = re.compile(r"^phases\.(\d+)\.preferred_orientation\.r$")
#: Phase scale — the one parameter the intensity is *exactly linear* in, so
#: its column needs no perturbed ``phase_peaks`` at all (``_scale_column``).
_SCALE_PATH = re.compile(r"^phases\.(\d+)\.scale$")

#: Residual evaluations per accepted iteration that TRF's budget must allow
#: for, so that a run genuinely needing ``max_iter`` iterations is never cut
#: short.  scipy exposes no iteration cap — only ``max_nfev`` — and an
#: iteration costs one evaluation plus one per rejected trial point.
#:
#: **Measured**, not assumed: 28 stages across four real protocols (the QPA
#: round-robin cpd-2 texture protocol, cpd-1a, and 11-BM NAC in both Le Bail
#: and Rietveld) give nfev/njev median 1.11, p90 1.64, worst 3.20.  Rounded up
#: from the worst case.
#:
#: The multiplier this replaced was ``n_params``, which priced a
#: *finite-difference* Jacobian — n_params evaluations per iteration — and no
#: finite-difference column is built for any common parameter family any more
#: (WP-1109 retired-item 1 counted zero across five NAC stages).  At 42 free
#: parameters that made ``max_iter=100`` a ~4200-evaluation budget, roughly 30x
#: what its name says, which is what let a diverging pattern spend ten minutes
#: before giving up.  This is CLAUDE.md's "runaway guard, never a timer": every
#: converging fit measured stays an order of magnitude inside it.
NFEV_PER_ITERATION = 4

#: Convergence tolerances handed to TRF alongside ``ftol``.  Four orders below
#: scipy's own 1e-8 default, and **deliberately not loosened** — named here so
#: the number has one home and the measurement that keeps it has somewhere to
#: live (WP-1109 tried 1e-8 and put it back).
#:
#: It is not the free hygiene it looks like.  It is not even a speed win: 1e-8
#: measured 1.22-1.27x faster on the IUCr cpd-1a protocol but 1.04x *slower* on
#: the QPA-acceptance cpd-2 one, because an earlier stage stops sooner at a
#: worse point and a later stage then takes more iterations to recover. And it
#: is not answer-preserving: it takes ``test_acceptance_stephens``'s isotropic
#: control past a shipped bar — corundum's reported strain anisotropy 3.64
#: against a < 2.0 assertion, on a specimen whose whole role is to come back
#: isotropic so the brucite result beside it means something. The strain still
#: reads undetected with r2 = 0.41, so the conclusion survives; the quotable
#: ratio does not, which is the distinction that matters for a number a
#: reader would cite.
#:
#: Read that as a statement about how well determined a nearly-isotropic
#: strain tensor is, not about TRF. Loosening these is a real change to the
#: answer on the ill-conditioned directions, so it needs its own evidence,
#: not a tidy-up.
XTOL = GTOL = 1e-12

#: Paths whose whole effect on the pattern is a peak's **integrated
#: intensity**: the peak keeps the position, width and mixing it had, so
#: ∂pos/∂p, ∂Γ/∂p and ∂η/∂p are identically zero and the three profile
#: partials they multiply are never read.  A stage that frees only these can
#: ask ``derivative_bases(profile_derivs=False)`` and skip building them.
#:
#: This is a claim about what a parameter *name* reaches, so it is written the
#: safe way round: an **allow**-list of the intensity-only families, with
#: everything unrecognised — a new parameter included — falling through to the
#: full bases.  Getting the inverse list wrong would cost a silently short
#: column; getting this one wrong costs only the work it was meant to save.
#: The claim is verified where it is used, in ``_peak_chain_column``.
_INTENSITY_ONLY = (
    re.compile(r"^phases\.\d+\.(scale|extinction)$"),
    # every atom parameter: x/y/z and their Wyckoff DOFs, occupancy, Biso and
    # the ADP components — all of them enter through |F|² alone
    re.compile(r"^phases\.\d+\.atoms\.\d+\."),
    re.compile(r"^phases\.\d+\.preferred_orientation\.r$"),
    # a line weight and the polarization ratio scale the intensity of a peak
    # that is already placed.  The line's ``wavelength`` beside it is a table
    # entry since WP-1128 and is deliberately **absent** from this list: λ moves
    # every peak of its histogram (2θ = 2·asin(λ/2d)), so it needs the position,
    # width and mixing partials.  Spelled ``\.weight$`` rather than as a
    # ``lines\.\d+\.`` prefix precisely so the wavelength cannot be swept in.
    re.compile(r"^instrument\.source\.lines\.\d+\.weight$"),
    re.compile(r"^instrument\.polarization$"),
)


def _intensity_only(path: str, bkg_cols: dict[str, int]) -> bool:
    """Whether ``path`` can be refined without any peak moving or reshaping.

    Background coefficients qualify trivially — they never touch a peak at all
    — which is what lets a background-plus-scale stage skip the bases outright.
    """
    return path in bkg_cols or any(p.match(path) for p in _INTENSITY_ONLY)


#: scipy ``least_squares`` termination codes as tokens (its docs, `status`):
#: which tolerance fired, for :attr:`LSQOutcome.termination`.
_TRF_TERMINATION = {-1: "invalid_input", 0: "max_nfev", 1: "gtol", 2: "ftol",
                    3: "xtol", 4: "ftol+xtol"}


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
    #: which driver produced this — "trf" (scipy, the reference) or "lm"
    solver: str = "trf"
    #: steps the bounded-LM driver shortened to stay inside a linear-inequality
    #: constraint (the Stephens strain cone).  0 under TRF, which has no such
    #: vocabulary — see ``optimize/lm.py``.
    n_constraint_truncations: int = 0
    #: McCusker et al. (1999) §7's convergence quantity, measured over the
    #: final accepted step with both sides in external parameter units — see
    #: :func:`_final_shift_over_esd`.  ``None`` when it cannot be measured (no
    #: accepted step, or no esds), never zero.  ``refine`` copies this onto
    #: ``Statistics.max_shift_over_esd``; nothing else derives it (WP-1076).
    max_shift_over_esd: float | None = None
    #: *which* criterion ended the solve (WP-1113) — the ``status`` string
    #: above says only whether it converged, and the evaluation-count work
    #: needs the difference between "the cost stopped moving" (ftol), "the
    #: step stopped moving" (xtol) and "the gradient vanished" (gtol): a
    #: linear-rate tail rides exactly one of them.  TRF: scipy's status code
    #: as a token (``ftol``/``xtol``/``gtol``/``ftol+xtol``/``max_nfev``).
    #: LM: :attr:`~.lm.LMOutcome.termination`.  ``""`` only on the
    #: zero-parameter early return, where no criterion was ever consulted.
    termination: str = ""


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

    The row *layout* is not written here: ``model.rows`` owns it, and the
    traced residuals every autodiff backend uses call the same assembler, so
    the numpy reference and the traced twins cannot disagree about block order.
    """
    sqrt_w = 1.0 / model.sigma
    n_table = len(table.free_paths)
    xp = get_backend()
    fixed_intens = _lebail_snapshot(model)
    empty_aux = np.zeros(0, dtype=np.float64)

    def residual(theta: np.ndarray) -> np.ndarray:
        if model.pawley is not None:
            aux = theta[n_table:]
            intens = model.split_pawley_intensities(aux)
            values = table.decode(theta[:n_table])
        else:
            aux = empty_aux
            intens = fixed_intens
            values = table.decode(theta)
        return row_layout.assemble(model, row_layout.ResidualInputs(
            values=values, intens=intens, theta_aux=aux,
            sqrt_w=sqrt_w, y_obs=model.y_obs, xp=xp))

    return residual


def _gather_per_line(lay, arrays) -> np.ndarray:
    """(R,) row gather of per-line arrays (``arrays[il][k]``)."""
    return lay.gather([(a,) for a in arrays], 0)


def _peak_chain_column(model: CompiledModel, table: ParameterTable,
                       bases: DerivativeBases, theta: np.ndarray,
                       values: dict[str, float], c: int, path: str,
                       intensities: list[np.ndarray] | None = None,
                       affected: "list[int] | range | None" = None) -> np.ndarray:
    """∂y/∂θ_c via the analytic bases + per-reflection scalar FD.

    Only the phases the column touches are re-derived (``phases.2.…`` leaves
    the others' scalars untouched; instrument paths touch all).  ``affected``
    overrides that reading of the path, and a tie is why it has to: the
    perturbed values come from ``table.decode``, so every dependent moves with
    the source whatever phase it sits in, while the phases whose scalars are
    *re-derived* here are chosen by name.  A user tie across phases would
    otherwise drop the far phase's whole contribution from the column
    (WP-1070); the caller passes the union C actually touches.
    ``intensities`` carries the lebail/pawley per-hkl vectors — the perturbed
    ``phase_peaks`` must see the same intensities as the expansion point.

    Since WP-1112 the scalar FDs are vectorised over the rows and the
    accumulation is one order-preserving scatter (:func:`~rietx.model.forward.accumulate_planes`, bit
    -identical to the per-row loop); the claim verification is unchanged — a
    term whose coefficients are nonzero under a ``profile_derivs=False``
    build still raises through :func:`_require_basis`, naming the path.
    """
    h = 1e-6 * max(1.0, abs(theta[c]))
    tp = theta.copy()
    tp[c] += h
    values_p = table.decode(tp)
    if affected is None:
        affected = ([int(path.split(".")[1])] if path.startswith("phases.")
                    else range(len(model.phases)))

    parts = []
    for ip in affected:
        peaks_p = model.phase_peaks(
            ip, values_p, None if intensities is None else intensities[ip])
        pp = bases.planes[ip]
        lay = pp.layout
        if not len(lay.i0):
            continue
        pos1 = lay.gather(peaks_p, 0)
        w1p = lay.gather(peaks_p, 1)
        w2p = lay.gather(peaks_p, 2)
        int1 = lay.gather(peaks_p, 3)
        pair = pp.finite & np.isfinite(pos1)
        with np.errstate(invalid="ignore"):
            d_i = np.where(pair, (int1 - pp.inten) / h, 0.0)
            c_p = np.where(pair, pp.inten * ((pos1 - pp.pos) / h), 0.0)
            c_g = np.where(pair, pp.inten * ((w1p - pp.w1) / h), 0.0)
            c_e = np.where(pair, pp.inten * ((w2p - pp.w2) / h), 0.0)
        terms = []
        if np.any(d_i != 0.0):
            terms.append((d_i, pp.omega))
        for coef, plane, what in ((c_p, pp.d_pos, "position"),
                                  (c_g, pp.d_gamma, "width"),
                                  (c_e, pp.d_eta, "mixing")):
            if np.any(coef != 0.0):
                _require_basis(plane, path, what)
                terms.append((coef, plane))
        parts.append((lay, terms))
    return _accumulate(len(model.tt), parts)


def _require_basis(basis: np.ndarray | None, path: str, what: str) -> None:
    """Check the caller's ``profile_derivs=False`` claim against the scalars.

    The claim is that no free column moves a peak's position, width or mixing,
    and here is where it meets the finite differences that would say otherwise.
    Both sides recompute from the same decoded values, so an intensity-only
    parameter leaves these scalars bit-zero; a non-zero one means ``path``
    belongs to a family ``_INTENSITY_ONLY`` wrongly claims.  Raising names the
    path — the alternative, using the missing basis as zero, is exactly the
    silently-short column the FD fallback exists to prevent.
    """
    if basis is None:
        raise AssertionError(
            f"{path!r} moves a peak's {what}, but the profile-derivative bases "
            f"were skipped as if it could not — see _INTENSITY_ONLY in "
            f"optimize/least_squares.py")


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
    C, _ = table.constraint_block()
    coeffs = np.array([C[table._paths[f"phases.{ip}.atoms.{j}.{name}"], c]
                       for name in rows], dtype=np.float64)
    dint = grad(ip, j, coeffs, values)
    pp = bases.planes[ip]
    coef = np.where(pp.finite, _gather_per_line(pp.layout, dint), 0.0)
    terms = [(coef, pp.omega)] if np.any(coef != 0.0) else []
    return _accumulate(len(model.tt), [(pp.layout, terms)])


def _po_column(model: CompiledModel, bases: DerivativeBases,
               values: dict[str, float], ip: int) -> np.ndarray:
    """∂y/∂r for the March coefficient: only the intensity scalar moves.

    ``po_intensity_grad`` supplies the analytic per-(line, reflection)
    ∂intensity/∂r (P is a pure multiplier, so positions and widths are
    untouched); it is applied to the same frozen profile bases the forward
    model uses.  The softplus chain factor ∂r/∂θ is applied by the caller.
    """
    dint = model.po_intensity_grad(ip, values)
    if dint is None:
        return np.zeros(len(model.tt))
    pp = bases.planes[ip]
    coef = np.where(pp.finite, _gather_per_line(pp.layout, dint), 0.0)
    terms = [(coef, pp.omega)] if np.any(coef != 0.0) else []
    return _accumulate(len(model.tt), [(pp.layout, terms)])


def _scale_column(model: CompiledModel, bases: DerivativeBases,
                  values: dict[str, float], ip: int) -> np.ndarray:
    """∂y/∂scale for phase ip: its own contribution, divided by the scale.

    The scale enters ``phase_peaks`` exactly once, in ``base = scale · mult ·
    |F|²``, and every factor applied after it is independent of it — the
    March multiplier, the line weight, Lp, Sabine extinction (which reads the
    *raw* ``|F|²``, never the scaled product), specimen absorption, surface
    roughness, and the mask that zeroes a reflection pushed off the sphere.
    So the intensity is exactly linear in the scale, no position or width
    moves at all, and ∂intensity/∂scale is the intensity over the scale.

    That makes this the cheapest column in the Jacobian and it was the
    **dearest** before WP-1121: the peak-chain FD perturbed the scale and
    rebuilt the phase's whole scalar chain, which on the trigger case was
    1148 columns and 3.3 % of the fit, most of it a structure-factor
    evaluation that the perturbation could not have changed.  It cost that
    much *because* it could not change anything — the memoised blocks all
    hit, so the price was the ones a neighbouring cell column had evicted.

    **Not valid at ``scale == 0``**, where the true derivative is the whole
    unscaled chain and this expression is 0/0.  A softplus lower bound of 0
    is reachable in fp (root CLAUDE.md § Invariants: safe where zero is the
    off state, a bug where the physics divides — here it divides), so the
    caller tests the scale and leaves a dead phase to the FD path, which
    stays correct there.
    """
    scale = values[f"phases.{ip}.scale"]
    pp = bases.planes[ip]
    coef = np.where(pp.finite, pp.inten / scale, 0.0)
    terms = [(coef, pp.omega)] if np.any(coef != 0.0) else []
    return _accumulate(len(model.tt), [(pp.layout, terms)])


def _axial_column(model: CompiledModel, bases: DerivativeBases,
                  which: int, dpdu: float) -> np.ndarray:
    """∂y/∂θ_c for S/L (which=8) or H/L (which=9) from the node-FD bases.

    The plane holds zeros at symmetric rows, so one term over all rows is
    the loop over FCJ rows with ±0 additions interleaved — bitwise neutral.
    """
    parts = []
    for pp in bases.planes:
        plane = pp.d_sl if which == 8 else pp.d_hl
        if plane is None:
            continue
        coef = np.where(pp.finite, pp.inten * dpdu, 0.0)
        parts.append((pp.layout,
                      [(coef, plane)] if np.any(coef != 0.0) else []))
    return _accumulate(len(model.tt), parts)


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


def _column_extras(table: ParameterTable) -> list[list[str]]:
    """Per free column, the *other* physical paths it moves through C.

    Empty for a column that stands for itself alone.  Non-empty wherever a tie
    is live — the derived ones (a cubic ``b``←``a``, a Wyckoff coordinate
    behind its DOF) as much as a user's, which is what makes this a dispatch
    input rather than a special case: each analytic branch then declares the
    reach it can account for, and anything further falls to the whole-model FD
    column, which is exact because it decodes through C like the residual does.
    """
    C, _ = table.constraint_block()
    free = table.free_paths
    csc = C.tocsc()
    paths = [e.path for e in table.entries]
    return [[paths[r] for r in csc.indices[csc.indptr[c]:csc.indptr[c + 1]]
             if paths[r] != free[c]]
            for c in range(len(free))]


def _within_atom(extra: list[str], ip: str, j: str) -> bool:
    """Whether every path this column also moves belongs to atom ``j`` of ``ip``.

    The reach ``_structural_column`` accounts for: it reads the coefficients of
    one atom's x/y/z (or six U) rows.  The site-symmetry ties always satisfy
    this — that is the case it was written for — while a user tie between two
    atoms' DOFs does not, and would otherwise contribute only the near atom.
    """
    prefix = f"phases.{ip}.atoms.{j}."
    return all(p.startswith(prefix) for p in extra)


def _affected_phases(model: CompiledModel, path: str, extra: list[str]):
    """The phases whose peak scalars a column moves — its own and its tie's."""
    touched = [path, *extra]
    if any(not p.startswith("phases.") for p in touched):
        return range(len(model.phases))
    return sorted({int(p.split(".")[1]) for p in touched})


def _make_jacobian(model: CompiledModel, table: ParameterTable):
    """Mixed analytic/FD Jacobian of the residual w.r.t. the internal vector.

    In Pawley mode the vector is [table θ | intensities]; the table columns are
    built exactly as for Rietveld/Le Bail, then the intensity block gets its own
    exact linear columns (:func:`_pawley_intensity_columns`).
    """
    sqrt_w = 1.0 / model.sigma
    free = table.free_paths
    n_table = len(free)
    # row extents from the one layout authority — the Jacobian writes into the
    # same blocks the residual stacks, so it must not re-derive them
    data_blk, pen_blk, pawley_blk, restr_blk = row_layout.layout(model)
    n_data, n_bkg_pen, n_restraint = data_blk.n, pen_blk.n, restr_blk.n
    n_rows = row_layout.n_rows(model)

    bkg_cols = {path: n for n, path in enumerate(model.bkg_paths)}
    axial_paths = {"instrument.geometry.axial_sl": 8, "instrument.geometry.axial_hl": 9}

    # Which *other* physical parameters each free column moves, read off the
    # affine block once (C is frozen for the run).  Every analytic branch below
    # is written for one named path and computes the rows *it* knows about, so a
    # column that reaches further than its own branch covers must not take that
    # branch: the missing dependence would silently leave the column short
    # rather than fail (WP-1070).  Empty for every untied column, which is why
    # an unconstrained model dispatches exactly as it did before.
    extras = _column_extras(table)
    # every physical path some column of this Jacobian can move — the free
    # names plus everything their ties reach.  Any question of the form "can
    # this stage move X?" must be asked here rather than of ``free``, which is
    # the same distinction ``ParameterTable.moving_paths`` draws one rank down.
    reach = set(free).union(*extras) if extras else set(free)

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
        # the aperture node-FD bases feed only the axial columns, so ask for
        # them only in a stage that will build those columns — two FCJ node
        # generations per (line, reflection) per iteration otherwise wasted
        # (WP-0605 task 0; the FitReport callers keep the full default)
        need_axial = any(p in axial_paths for p in reach)
        # ∂Ω/∂pos, ∂Ω/∂Γ and ∂Ω/∂η are read only through ∂pos/∂p, ∂Γ/∂p and
        # ∂η/∂p, so a stage refining nothing but intensities multiplies all
        # three by zero.  Asked over ``reach``, not ``free``: a tie carries a
        # column onto paths whose names never appear in the free list.
        need_profile = not all(_intensity_only(p, bkg_cols) for p in reach)

        def get_bases() -> DerivativeBases:
            nonlocal bases
            if bases is None:
                bases = model.derivative_bases(values, intens,
                                               axial_derivs=need_axial,
                                               profile_derivs=need_profile)
            return bases

        for c, path in enumerate(free):
            extra = extras[c]
            if path in bkg_cols and not extra:
                # y is linear in the coefficient: ∂y/∂c_n = basis row; the
                # penalty rows are linear too (√λ·D₂), chain-ruled through
                # the transform for the (softplus-bounded) air term
                n = bkg_cols[path]
                dpdu = dpdu_of(c, theta_t)
                J[:n_data, c] = -sqrt_w * model.bkg_design[n] * dpdu
                if n_bkg_pen:
                    J[n_data:n_data + n_bkg_pen, c] = model.bkg_penalty[:, n] * dpdu
            elif path in axial_paths and not extra:
                b = get_bases()
                if b.axial_ok:
                    J[:n_data, c] = -sqrt_w * _axial_column(
                        model, b, axial_paths[path], dpdu_of(c, theta_t))
                else:
                    fd_cols.append(c)
            elif ((dof := _STRUCTURAL_PATH.match(path)) and model.mode == "rietveld"
                    and _within_atom(extra, dof.group(1), dof.group(2))):
                rows, grad = (("x", "y", "z"), model.coordinate_intensity_grad) \
                    if dof.group(3) == "dof" else (U_NAMES, model.adp_intensity_grad)
                J[:n_data, c] = -sqrt_w * dpdu_of(c, theta_t) * _structural_column(
                    model, table, get_bases(), values, c,
                    int(dof.group(1)), int(dof.group(2)), rows, grad)
            elif ((po := _PO_PATH.match(path)) and model.mode == "rietveld"
                    and not extra):
                J[:n_data, c] = -sqrt_w * dpdu_of(c, theta_t) * _po_column(
                    model, get_bases(), values, int(po.group(1)))
            elif ((sc := _SCALE_PATH.match(path)) and model.mode == "rietveld"
                    and not extra and values[path] > 0.0):
                # exactly linear, so no perturbed ``phase_peaks``; the scale
                # test is the 0/0 fence _scale_column's docstring names, and
                # a phase sitting at zero falls through to the FD path below
                J[:n_data, c] = -sqrt_w * dpdu_of(c, theta_t) * _scale_column(
                    model, get_bases(), values, int(sc.group(1)))
            elif model.scalar_chain_supported(path) and all(
                    model.scalar_chain_supported(p) and p not in bkg_cols
                    and p not in axial_paths for p in extra):
                J[:n_data, c] = -sqrt_w * _peak_chain_column(
                    model, table, get_bases(), theta_t, values, c, path, intens,
                    affected=_affected_phases(model, path, extra))
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
                                      n_table, pawley_blk.start)

        if model.restraints is not None and n_table:
            # One unconditional matrix block below the data/penalty/Pawley rows:
            # ∂row/∂θ_c = (R_phys @ C)[i,c]·dφ/du[c], since decode gives
            # p = C·to_physical(θ) + d.  Rietveld-only (the Pawley block is then
            # empty, so restr_blk starts right after the penalty rows), and the
            # rows touch table θ only — no Pawley-intensity columns.
            restr0 = restr_blk.start
            r_phys = restraint_partials(model.restraints, values, table)
            if model.restraint_weight_scale != 1.0:
                # eq (7)'s c_w, applied to the assembled block and never inside
                # restraint_partials — model.geometry calls that same function
                # at unit weight for the unweighted partials every reported
                # geometry esd is built from (WP-1074; CompiledModel's field
                # comment).  √ matches restraint_residual: c_w weights S_G, the
                # sum of these rows squared.
                r_phys = r_phys * math.sqrt(model.restraint_weight_scale)
            cmat = table.constraint_block()[0].toarray()  # C small: dense is fine
            dpdu = np.array([dpdu_of(c, theta_t) for c in range(n_table)],
                            dtype=np.float64)
            J[restr0:restr0 + n_restraint, :n_table] = (r_phys @ cmat) * dpdu
        return J

    return jacobian


def _jacobian_for(model, table, backend: str):
    """The Jacobian callable for ``backend`` (lazy import keeps numpy pure).

    Every autodiff callable produces the same fp64 host array in the same
    row/column layout as :func:`_make_jacobian`; the residual used for
    cost/statistics and the TRF solve stay numpy whichever backend built the
    columns (WP-0402 for jax, WP-0408 for torch — ``"torch"`` is fp64 on CPU,
    ``"torch-mps"`` fp32 on the Apple GPU, since no Apple GPU has fp64).

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
    elif backend in TORCH_DEVICES:
        from ..backend.torch_backend import make_torch_jacobian

        inner = make_torch_jacobian(model, table, device=TORCH_DEVICES[backend])
    elif backend == "numpy":
        inner = _make_jacobian(model, table)
    else:
        raise ValueError(f"unknown backend {backend!r}; "
                         f"available: numpy, jax, {', '.join(TORCH_DEVICES)}")

    def jacobian(theta: np.ndarray) -> np.ndarray:
        # policy read per call, not per closure build: a `with precision_policy`
        # block around a refine must take effect on an already-built solver
        return get_precision_policy().cast_columns(inner(theta))

    return jacobian


def strain_cone_inequalities(model: CompiledModel, table: ParameterTable,
                             x0: np.ndarray) -> list["lm_mod.LinearInequality"]:
    """Stephens positivity rows σ²(M) = T·θ + c ≥ 0, one block per phase.

    σ²(M) is ``strain_monomials @ S`` and S is an *affine* function of the free
    vector (``decode`` gives p = C·to_physical(θ) + d), so on the strain rows —
    whose DOFs carry the identity transform, by construction, since the cone
    couples all fifteen coefficients and cannot be a box — the whole thing is
    linear in θ.  That is what makes it expressible to the bounded-LM driver
    and inexpressible to TRF.

    Two cases are skipped rather than enforced, both deliberately:

    * **no strain DOF free in this stage** — T is then identically zero, so the
      rows are a constant that the solver could never satisfy if it were
      already negative, and would silently freeze the step at τ = 0;
    * **an infeasible starting point** — feasibility is *maintained*, not
      restored, by a fraction-to-the-boundary rule.  The staged plans start
      from the isotropic limit S = ε²·[M²], which is strictly inside the cone,
      so this is the pathological case and not the normal one; when it does
      happen the existing ``STEPHENS_STRAIN_NOT_POSITIVE`` guard still fires on
      the result, which is the honest outcome.
    """
    from . import lm as lm_mod

    free = table.free_paths
    if not free:
        return []
    C, d = table.constraint_block()
    C = C.toarray()
    out: list[lm_mod.LinearInequality] = []
    for ip, cp in enumerate(model.phases):
        if cp.strain_monomials is None:
            continue
        try:
            rows = [table._paths[f"phases.{ip}.microstrain.{n}"] for n in S_NAMES]
        except KeyError:                      # phase carries no microstrain block
            continue
        mono = np.asarray(cp.strain_monomials, dtype=np.float64)
        T = mono @ C[rows, :]
        c = mono @ d[rows]
        if not np.any(T):                     # nothing free in this direction
            continue
        block = lm_mod.LinearInequality(T=T, c=c, label=f"phases.{ip}.microstrain")
        if block.violated(x0).any():
            continue
        out.append(block)
    return out


def _free_values(table: ParameterTable, theta: np.ndarray) -> list[float]:
    """Physical values of the table's free paths at ``theta`` — the ``values``
    field of an ``eval`` event, in ``free_paths`` order (which ``stage_start``
    carries as ``free_paths``, so a stream consumer can align them).

    The slice drops the appended Pawley intensity tail: it refines on the
    identity transform outside the table, and its per-hkl values are
    serialized per history node (``ReflectionState``), not per evaluation.
    """
    values = table.decode(np.asarray(theta[:len(table.free_paths)],
                                     dtype=np.float64))
    return [float(values[p]) for p in table.free_paths]


def _lm_outcome(residual, jacobian, x0, lo, hi, *, max_iter, ftol,
                inequalities, events, stage: str, track=None, table=None):
    """Run the bounded-LM driver, adapted to the scipy result shape.

    The two drivers are kept interchangeable at exactly this point: everything
    downstream (covariance, guards, history) reads ``x``/``fun``/``jac``/
    ``cost``/``nfev``/``status``, and :class:`~.lm.LMOutcome` carries those with
    scipy's meanings.  ``track`` is a :class:`_StepTracker` fed from the
    driver's accepted-point callback — the LM half of the final-step record
    the TRF path reconstructs from its residual closure.  ``events`` gets one
    ``eval`` per *measured trial* via the driver's ``on_trial`` hook
    (WP-1113): a rejected step arrives with ``accepted: false`` and the λ that
    produced it, which is exactly the trajectory the evaluation-count
    mechanism analysis reads.  Trials the driver's linear model discards
    without evaluating the residual emit nothing — ``eval`` means one residual
    evaluation on both drivers.
    """
    from . import lm as lm_mod

    counter = {"n": 0}

    def accept_cb(theta: np.ndarray, cost: float) -> None:
        track.accept(theta, cost)

    def trial_cb(theta: np.ndarray, cost: float, accepted: bool,
                 lam: float, step_norm: float) -> None:
        counter["n"] += 1
        data = {"stage": stage, "n_eval": counter["n"], "cost": cost,
                "accepted": accepted, "step_norm": step_norm, "lam": lam}
        if table is not None:
            data["values"] = _free_values(table, theta)
        events.emit("eval", **data)

    return lm_mod.minimize(residual, jacobian, x0, lo=lo, hi=hi,
                           max_iter=max_iter, ftol=ftol,
                           inequalities=inequalities,
                           callback=accept_cb if track is not None else None,
                           on_trial=trial_cb if events is not None else None)


class _StepTracker:
    """The last two accepted iterates of one solve, full θ vector each.

    scipy TRF exposes no accepted-point hook, so the TRF path reconstructs
    acceptance from the solver-facing residual closure: TRF accepts a trial
    exactly when its cost is strictly below the incumbent's, so the strictly
    cost-decreasing evaluations *are* the accepted iterates.  The jacobian
    closure never routes through that residual, which is what keeps FD probe
    points out of the record.  The LM driver reports accepted points through
    its callback and feeds :meth:`accept` directly.
    """

    def __init__(self) -> None:
        self.prev: np.ndarray | None = None
        self.best: np.ndarray | None = None
        self.best_cost = np.inf

    def accept(self, x: np.ndarray, cost: float) -> None:
        if cost < self.best_cost:
            self.prev, self.best = self.best, np.asarray(x, dtype=np.float64).copy()
            self.best_cost = cost

    def step(self) -> tuple[np.ndarray, np.ndarray] | None:
        """(previous, final) accepted iterate, or ``None`` before any step."""
        return None if self.prev is None else (self.prev, self.best)


def _final_shift_over_esd(table: ParameterTable,
                          step: tuple[np.ndarray, np.ndarray] | None,
                          stderr_full: np.ndarray | None,
                          correlation: np.ndarray | None,
                          n_table: int) -> float | None:
    """McCusker et al. (1999) §7's convergence quantity, external units.

    max |Δp_i| / esd(p_i) over the solve's final accepted step, with *both*
    sides in external parameter units: Δp decoded exactly through the
    transform chain, the esd the chain-ruled physical one every reported
    parameter carries — an internal-space ratio is meaningless at finite step
    (softplus/logit curvature).  The appended Pawley intensity block refines
    on the identity transform, so internal equals external there and its rows
    join directly.  ``None`` when the quantity cannot be measured — no
    accepted step, or no esds — never zero (WP-1076's honest empty state).
    """
    if step is None or stderr_full is None:
        return None
    x_prev, x_final = step
    vals_prev = table.decode(x_prev[:n_table])
    vals_final = table.decode(x_final[:n_table])
    esd = table.stderr_physical(x_final[:n_table], stderr_full[:n_table],
                                correlation)
    ratios = [abs(vals_final[p] - vals_prev[p]) / esd[p]
              for p in table.free_paths
              if np.isfinite(esd.get(p, np.nan)) and esd[p] > 0.0]
    ratios += [abs(float(x_final[i]) - float(x_prev[i])) / float(stderr_full[i])
               for i in range(n_table, len(x_final))
               if np.isfinite(stderr_full[i]) and stderr_full[i] > 0.0]
    return max(ratios) if ratios else None


def _freeze_cell_windows(model: CompiledModel, table: ParameterTable) -> None:
    """Declare which phases' cells take the default window for this stage.

    Only the phases the data cannot see (WP-1110).  A window is not free — TRF
    derives its per-coordinate trust-region scale from the distance to the
    bounds, so bounding a cell changes the step taken in it even where the bound
    is never reached — so it is spent only where the alternative is a flat
    direction the fit will wander down.  ``phase_support`` is the one authority
    for that, shared with the ``PHASE_UNCONSTRAINED`` diagnostic.

    Read at the values the stage *starts* from, which is the whole point of
    doing it here: the same place every other per-stage freeze happens.
    """
    values = table.decode(table.x0())
    support = model.phase_support(values)
    table.freeze_cell_windows({ip for ip, s in enumerate(support)
                               if s < PHASE_SUPPORT_SIGMA})


def _freeze_cell_windows_multi(models: list[CompiledModel],
                               mtable: "MultiParameterTable") -> None:
    """The freeze above for a joint refinement, where a cell can be *shared*.

    A phase invisible in one histogram may be plain in another, and if its cell
    is shared then the data — jointly, which is what a joint refinement fits —
    can see it. So a phase is windowed only when it is below support in **every**
    histogram, and the same set is frozen on every sub-table: the combined bound
    vectors write shared columns once per histogram and keep the last, which is
    only harmless while they agree.
    """
    per_model = [m.phase_support(t.decode(t.x0()))
                 for m, t in zip(models, mtable.tables, strict=True)]
    n_phases = min((len(s) for s in per_model), default=0)
    windowed = {ip for ip in range(n_phases)
                if all(s[ip] < PHASE_SUPPORT_SIGMA for s in per_model)}
    for table in mtable.tables:
        table.freeze_cell_windows(windowed)
    mtable.refresh_bounds()


def run_least_squares(model: CompiledModel, table: ParameterTable,
                      *, max_iter: int = 100, ftol: float = 1e-9,
                      compute_uncertainties: bool = True,
                      events=None, stage: str = "",
                      backend: str = "numpy",
                      solver: str = "trf",
                      cancel=None) -> LSQOutcome:
    """Solve one stage.  ``cancel`` — a :class:`~.cancel.CancelToken`, read
    between residual evaluations; a set token raises
    :class:`~.cancel.RefinementCancelled` out of this call, leaving the model
    and table exactly as the last accepted evaluation found them."""
    if solver not in SOLVERS:
        raise ValueError(f"unknown solver {solver!r}; available: {', '.join(SOLVERS)}")
    _freeze_cell_windows(model, table)
    residual = _make_residual(model, table)
    jacobian = _jacobian_for(model, table, backend)

    if cancel is not None:
        # Both drivers, and *before* the event wrapper, so the check costs one
        # branch on the path that would otherwise evaluate: the flag is read at
        # an eval boundary, where the compiled state is quiescent — nothing
        # reaches into the frozen discreteness.  This is deliberately not the LM
        # driver's callback, which fires only on *accepted* points: an inner
        # loop that never accepts a step would never see the token.
        inner_c = residual

        def residual(theta: np.ndarray):
            if cancel.is_set():
                raise RefinementCancelled(
                    f"cancelled during stage {stage!r}" if stage else "cancelled",
                    stage=stage)
            return inner_c(theta)

    tracker = _StepTracker()
    if solver == "trf":
        # One wrapper, two jobs in a fixed order per call: emit the eval event
        # *measured against the incumbent*, then let the tracker accept.  scipy
        # TRF exposes no per-iteration callback, so the residual closure is the
        # hook (the emitted dict is plain floats — no pydantic here), and
        # acceptance/step fields are reconstructed exactly as _StepTracker's
        # docstring describes.  TRF's trust radius is scipy-internal: the trial
        # ``step_norm`` sequence is its observable shadow — a trial step never
        # exceeds the radius, and rejections shrink it (WP-1113).  The LM
        # driver reports its trials through a real callback instead
        # (``_lm_outcome``), so it does not wrap the residual.
        inner_t = residual
        counter = {"n": 0}

        def residual(theta: np.ndarray):
            r = inner_t(theta)
            cost = 0.5 * float(r @ r)
            if events is not None:
                counter["n"] += 1
                data = {"stage": stage, "n_eval": counter["n"], "cost": cost,
                        "accepted": bool(cost < tracker.best_cost)}
                if tracker.best is not None:
                    data["step_norm"] = float(np.linalg.norm(
                        np.asarray(theta, dtype=np.float64) - tracker.best))
                data["values"] = _free_values(table, theta)
                events.emit("eval", **data)
            tracker.accept(theta, cost)
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
    tracker.accept(x0, cost0)  # the LM path's seed; a no-op after the TRF wrapper
    if len(x0) == 0:
        return LSQOutcome(x0, cost0, cost0, 0, "converged", None, None, None,
                          solver=solver)

    n_truncated = 0
    if solver == "lm":
        # the strain cone is built against the *starting* point, because
        # feasibility is maintained rather than restored (see the builder)
        cone = strain_cone_inequalities(model, table, x0[:n_table])
        res = _lm_outcome(residual, jacobian, x0, lo, hi, max_iter=max_iter,
                          ftol=ftol, inequalities=cone, events=events, stage=stage,
                          track=tracker, table=table)
        n_truncated = res.n_truncated
    else:
        res = least_squares(residual, x0, jac=jacobian, bounds=(lo, hi), method="trf",
                            ftol=ftol, xtol=XTOL, gtol=GTOL,
                            max_nfev=max_iter * NFEV_PER_ITERATION)
    status = "converged" if res.status > 0 else ("max_iter" if res.status == 0 else "diverged")
    termination = (res.termination if solver == "lm"
                   else _TRF_TERMINATION.get(res.status, str(res.status)))

    # esds from the *full* augmented covariance (table ↔ intensity correlation
    # feeds the table esds too), then split: table columns stay in the outcome,
    # the intensity tail lands on the model's Pawley block.
    stderr = corr = stderr_full = None
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
                      jac_table, stderr, corr, n_aux=n_aux, solver=solver,
                      n_constraint_truncations=n_truncated,
                      max_shift_over_esd=_final_shift_over_esd(
                          table, tracker.step(), stderr_full, corr, n_table),
                      termination=termination)


def _multi_closures(models: list[CompiledModel], mtable: "MultiParameterTable",
                    *, weights: list[float] | None = None,
                    backend: str = "numpy"):
    """(residual, jacobian, n_data_total) for the stacked multi-histogram solve.

    Split out of :func:`run_multi_least_squares` so the stacked layout is
    reachable without running a solve — WP-0404's cross-backend matrix compares
    this Jacobian across backends exactly as the solver would build it.
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

    return residual, jacobian, n_data_total


def run_multi_least_squares(models: list[CompiledModel],
                            mtable: "MultiParameterTable", *,
                            weights: list[float] | None = None,
                            max_iter: int = 100, ftol: float = 1e-9,
                            compute_uncertainties: bool = True,
                            backend: str = "numpy",
                            solver: str = "trf") -> LSQOutcome:
    """Joint solve of several histograms stacked into one residual (WP-0308).

    Each histogram keeps its own compiled model (⇒ its own frozen hkl list,
    windows, FCJ node counts) and its own :class:`ParameterTable`; the combined
    free vector θ threads through them via ``mtable``'s column map, so a *shared*
    structural column (cell, coordinates, ADPs …) receives Jacobian
    contributions from *every* histogram — that is what refines the shared
    quantity better than any single pattern could.

    Row layout is [all histograms' data rows] then [all histograms' background-
    penalty rows], so :func:`covariance_estimates` (which treats the first
    ``n_data`` rows as data for χ² and the Bérar-Lelann factor) is reused
    verbatim.  The BL run-of-signs statistic is therefore evaluated on the
    *concatenated* data residual: WP-0407 examined this and kept it as-is —
    each histogram join contaminates the statistic with at most one artificial
    run boundary (a point where consecutive residuals are not 2θ-neighbours),
    i.e. ≤ ``n_hist − 1`` boundaries out of ``n_data_total``, negligible for the
    handful of patterns co-refined here.  A per-histogram decomposition was not
    adopted because BL applies as a single scalar to the whole covariance
    diagonal and a *shared* parameter draws from every histogram, so there is
    no clean single per-parameter factor to combine.  A per-histogram scalar
    weight ``w_h`` scales both that
    histogram's data and its penalty rows by ``√w_h`` — keeping the smoothness
    prior's strength relative to the data fixed; default unit weights leave the
    residual identical to N independent solves sharing the structure.

    ``solver`` selects the driver exactly as in :func:`run_least_squares` —
    this is the *second* entry point WP-0308 warned about, and a solver swap
    that reached only the single-histogram one would leave joint refinements
    silently on scipy.  The Stephens cone is not built here: its rows are
    per-model and the stacked column map would have to scatter each phase's T
    into the joint vector.  Deferred rather than half-done — a joint refinement
    with `solver="lm"` gets the bounded driver, not the cone.
    """
    if solver not in SOLVERS:
        raise ValueError(f"unknown solver {solver!r}; available: {', '.join(SOLVERS)}")
    residual, jacobian, n_data_total = _multi_closures(
        models, mtable, weights=weights, backend=backend)
    n_cols = len(mtable.free_paths)

    _freeze_cell_windows_multi(models, mtable)
    x0 = mtable.x0()
    lo, hi = mtable.bounds()
    x0 = np.clip(x0, lo + 1e-12, hi - 1e-12) if len(x0) else x0
    r0 = residual(x0)
    require_fp64(r0, "least-squares residual")
    cost0 = 0.5 * float(r0 @ r0)
    if n_cols == 0:
        return LSQOutcome(x0, cost0, cost0, 0, "converged", None, None, None,
                          solver=solver)

    if solver == "lm":
        res = _lm_outcome(residual, jacobian, x0, lo, hi, max_iter=max_iter,
                          ftol=ftol, inequalities=[], events=None, stage="")
    else:
        res = least_squares(residual, x0, jac=jacobian, bounds=(lo, hi), method="trf",
                            ftol=ftol, xtol=XTOL, gtol=GTOL,
                            max_nfev=max_iter * NFEV_PER_ITERATION)
    status = "converged" if res.status > 0 else ("max_iter" if res.status == 0 else "diverged")
    termination = (res.termination if solver == "lm"
                   else _TRF_TERMINATION.get(res.status, str(res.status)))

    stderr = corr = None
    if compute_uncertainties and res.jac is not None and len(res.fun) > len(res.x):
        stderr, corr = covariance_estimates(res.jac, res.fun, len(res.x),
                                            n_data=n_data_total)
    jac_data = np.asarray(res.jac)[:n_data_total] if res.jac is not None else None
    return LSQOutcome(res.x, cost0, float(res.cost), int(res.nfev), status,
                      jac_data, stderr, corr, solver=solver,
                      termination=termination)


def covariance_estimates(jac: np.ndarray, fun: np.ndarray, n_free: int,
                         n_data: int | None = None
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Esds and correlation matrix from the weighted Jacobian at the solution.

    Cov = χ²_red · (JᵀJ)⁻¹ with χ²_red = Σr²/(N−P); esd_i = √Cov_ii, then
    multiplied by the Bérar-Lelann serial-correlation factor (Bérar & Lelann,
    1991, J. Appl. Cryst. 24, 1 — see ``statistics.berar_lelann_factor``).  The
    returned esds therefore carry the inflation; the correlation matrix does
    **not** — it is the true Pearson matrix (unit diagonal) normalised by the
    *raw* sqrt-diagonal, so a genuinely degenerate pair reports |ρ| ≈ 1 and the
    0.98 high-correlation guard means what it says (WP-0407 fixed a placement
    bug where normalising by the inflated diagonal left corr with a 1/BL²
    diagonal, cancelling BL in the reported physical esds and deflating the
    guard).  A pseudo-inverse guards against singular normal matrices.

    Both esd consumers inherit the inflation: table esds flow through
    ``ParameterTable.stderr_physical`` as ``diag(C·corr·outer(s,s)·Cᵀ)`` with
    ``s`` already ×BL and ``corr`` now unit-diagonal (no cancellation), and the
    Pawley per-hkl tail (``model.pawley.stderr`` in :func:`run_least_squares`)
    is a slice of this ×BL diagonal used directly.

    With P-spline penalty rows appended (rows beyond ``n_data``), JᵀJ keeps
    them — (J_dᵀJ_d + λD₂ᵀD₂)⁻¹ is the regularised covariance — but χ² and
    the serial-correlation factor are evaluated on the *data* rows only
    (run-of-sign statistics on penalty rows would be meaningless).

    The solve is fp64 unconditionally (architecture invariant 2): cond(JᵀJ) =
    cond(J)², so forming and inverting the normal matrix is the step reduced
    precision can never take.  ``to_host_fp64`` is that boundary — a Jacobian
    whose columns were computed at fp32 is upcast here before JᵀJ, while the
    residual is *required* to have been fp64 all along.

    The pinv guarding, the symmetrisation and the fp64 boundary live in
    :func:`statistics.normal_covariance`, shared with the per-peak profile fits
    (WP-1018) so the two surfaces cannot disagree about them; the final clip
    below removes the 1-ulp overshoot ``eigh`` can leave, so a reported
    correlation is always a valid one.  Note the clip is *not* the fix —
    clipping a 2.75 to 1.0 would report a degeneracy that the arithmetic, not
    the data, invented.
    """
    from .statistics import berar_lelann_factor, normal_covariance

    data = fun if n_data is None else fun[:n_data]
    cov, _chi2_red = normal_covariance(jac, data, n_free)
    # Normalise the correlation by the *raw* (un-inflated) sqrt-diagonal so it is
    # a true Pearson matrix with unit diagonal; apply Bérar-Lelann only to the
    # returned esd diagonal.  Normalising by the inflated diagonal instead (the
    # pre-WP-0407 bug) left corr with a 1/BL² diagonal, which then cancelled the
    # BL factor exactly inside ``ParameterTable.stderr_physical`` (making the
    # reported physical esds effectively raw) and deflated every off-diagonal by
    # BL² (killing the 0.98 high-correlation guard).
    sqrt = np.sqrt(np.maximum(np.diag(cov), 0.0))
    # the outer product is inside the errstate, not before it: with WP-1110's
    # infinite variance on a gradient-free column and an exactly-zero one on a
    # direction the pinv dropped, ``denom`` has a genuine 0 × inf.  The NaN is
    # then *discarded* correctly — ``nan > 0`` is False, so that pair's
    # correlation is 0, which is what it should be — but a RuntimeWarning
    # raised from a covariance path is noise that hides the next real one.
    with np.errstate(invalid="ignore", divide="ignore"):
        denom = np.outer(sqrt, sqrt)
        corr = np.where(denom > 0, cov / denom, 0.0)
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, np.where(sqrt > 0.0, 1.0, 0.0))
    diag = sqrt * berar_lelann_factor(data)
    return diag, corr
