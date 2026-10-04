"""The solve cost: the whole-profile χ² at a frozen profile, as a quadratic form.

With the cell, the peak shapes and the background shape frozen at a converged
Le Bail or Pawley extraction, the calculated profile is linear in the
per-reflection |F|² of the phase being solved,

    y_calc = Xβ + s·ΩF,        F_k = |F_k|²,

where Ω (points × reflections) holds each reflection's unit-area profile summed
over the emission lines, with that line's per-hkl factor (multiplicity, Lp,
preferred orientation, absorption, roughness, line weight) folded into the
column; X holds the *nuisance* columns (the linear background terms, and the
other phases); anything else (a fixed background curve, humps, declared sharp
peaks) is held at the extraction's values and subtracted from y; s is the phase
scale and β the nuisance coefficients.  With W = diag(1/σ²), minimising the
weighted squared residual over β is a projection,

    P = W − WX(XᵀWX)⁺XᵀW,    M = ΩᵀPΩ,    b = ΩᵀPy,    c = yᵀPy,

and minimising over s ≥ 0 in closed form leaves

    χ²(F) = c − (bᵀF)²/(FᵀMF)    (bᵀF > 0; otherwise s = 0 and χ² = c).

Over free intensities I (sign unconstrained) the same form is
χ²(I) = χ²_min + (I − I_P)ᵀM(I − I_P) with I_P = M⁺b and χ²_min = c − bᵀM⁺b.
**The floor is this module's own unconstrained least-squares solve**, never
the extraction's intensities: the Le Bail update and the Pawley fit carry the
equal-split restraint rows, WP-1459's off-data ridge rows, the I ≥ 0 bounds and
a solver tolerance, none of which is in M, so χ²_min about their intensities is
not this form's minimum.  M is built from Ω directly for the same reason.  The
profile χ² at frozen profile is then a correlated-intensity χ² with weight
matrix M, with no intensity covariance inverted (M has no inverse under exact
overlap, and S0 needs none).  The form is derived here; what can fail is Ω, and
the acceptance test is Ω·F against Rietveld-mode ``evaluate`` at moved
structures (``tests/test_solve_cost.py``).  The equivalence of the Rietveld and the
correlated-integrated-intensity costs is published by David (2004), J. Appl.
Cryst. 37, 621; that paper is cited for the concept only, not for this form.

**Storage.**  ΩᵀWΩ is sparse and banded: two reflections couple only where
their windows overlap.  The projection adds a dense term of rank at most the
number of nuisance columns, so M is kept as M₀ − VVᵀ with M₀ = ΩᵀWΩ sparse and
V = ΩᵀWX·L, where L·Lᵀ is the pseudo-inverse of XᵀWX.  An evaluation costs
O(nnz(M₀) + N·rank), never O(N²); M is formed densely once, at construction,
for the least-squares solve that gives the floor, which is O(N³) in
reflections and is construction's cost, not an evaluation's.

**Nuisance modes.**  ``"pawley"`` projects every other phase out as free
per-reflection intensities (one column per reflection, its emission lines
tied at the ratios the compiled model gives them).  ``"scale"`` projects each
as a single column, its own calculated profile, from its atoms as declared
(:func:`blind_structure`).  The first discards whatever the solved phase
shares with a dense impurity pattern; the second keeps it.

Ω is built per emission line (:func:`omega_lines`) from the unit profiles of
``derivative_bases`` and a per-line factor taken by linearity, read off a
Rietveld-mode compile of the extraction's own cell, instrument and data with the
solved phase's atoms replaced by one dummy atom on a general position:
intensity/|F|² does not depend on the atoms.  So a lab Kα₁/Kα₂ doublet carries
each line's own Lp, which Le Bail and Pawley do not apply (Lp(Kα₂)/Lp(Kα₁) − 1
runs from −0.6 % to +1.3 % over 17–128° on the FAP pattern), and multi-line
data is supported.  Two private members are read,
:meth:`~rietx.model.forward.CompiledModel._total_f2` and
``Refinement._two_theta_limits``, so a rename of either fails this module's
tests.

**Refusals** (:class:`ExtractionRefused`, by ``reason``): no fit; a
Rietveld-mode fit; an unconverged or a poor extraction; a magnetic phase
anywhere in the model; two terms that are not linear, primary extinction on
the solved phase and a penalised background under projection; and two cases
the form would otherwise **leave out in silence**, by name.  A satellite
(WP-1326) inside the fitted range, on any phase: the Rietveld compile gives it
factor 0, so the solved phase's column, a ``"pawley"`` nuisance column and a
``"scale"`` impurity's profile are all empty there while the data carries the
peak.  And, under ``"pawley"``, a nuisance reflection only a line other than
line 0 reaches (a λ/n harmonic beyond line 0's sphere): its columns carry the
line ratios relative to line 0's intensity, which is zero there.  The solved
phase reads its factor off |F|², so a λ/n reflection is carried there, and
``"scale"`` draws every line (#580 review, item 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from scipy.sparse import csr_matrix

from ..crystallography.symmetry import reflection_label
from ..model.forward import d_spacings
from ..optimize.statistics import column_rescale

_CELL_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")

#: Eigenvalues of the equilibrated XᵀWX (unit diagonal) below this fraction of
#: the largest are dropped from the pseudo-inverse: a nuisance column that is a
#: linear combination of others (two coincident impurity reflections) carries
#: no direction of its own.
NUISANCE_RCOND = 1e-12

Refusal = Literal["not_an_extraction", "rietveld", "unconverged", "poor",
                  "magnetic", "nonlinear", "satellite", "secondary_line_only"]

#: How many reflections a refusal names before it counts the rest.
NAMED_REFLECTIONS = 5


class ExtractionRefused(ValueError):
    """The extraction cannot carry a solve cost; ``reason`` says why.

    ``"not_an_extraction"``: no fit at all.  ``"rietveld"``: a Rietveld-mode
    fit, whose profile was refined with its intensities tied to a structure, so
    it is not a free-intensity extraction of the pattern.  ``"unconverged"``:
    the solver did not report ``converged``, so the frozen profile is not the
    extraction's.  ``"poor"``: the fit is not a fit of this pattern, by the
    package's own reading (``RefinementResult.usable``).  ``"magnetic"``: the
    compile draws a magnetic term for some phase; that term is a second function
    of the atoms (its own form factor, and under WP-1343 its own frozen
    windows) that one |F|² per reflection and the dummy-atom compile cannot
    carry.  ``"nonlinear"``: something in the frozen model is not linear in |F|²
    (primary extinction on the solved phase) or in the nuisance coefficients (a
    penalised background, whose coefficients are not free), so the quadratic
    form would not be the profile χ².  ``"satellite"``: some phase has
    satellite reflections in the fitted range, which the form has no column
    for.  ``"secondary_line_only"``: under ``"pawley"``, a nuisance reflection
    is reached only by a line other than line 0, so its free-intensity column
    would be empty.  Both name the phase and the reflections.
    """

    def __init__(self, reason: Refusal, message: str):
        super().__init__(message)
        self.reason = reason


def _refuse_magnetic_model(model) -> None:
    """Refuse where the compile draws a magnetic term.  The compile decides,
    not the schema: a moment under X-rays scatters nothing and is accepted."""
    for j, cp in enumerate(model.phases):
        if cp.magnetic is not None or cp.batch_mag is not None:
            raise ExtractionRefused(
                "magnetic", f"compiled phase {j} carries a magnetic term: the "
                "solve cost holds one |F|² per reflection and has no magnetic term")


def _in_range(cp) -> np.ndarray:
    """(N,) bool: the reflection has a nonempty frozen window on some line."""
    return np.asarray((cp.win[..., 1] > cp.win[..., 0]).any(axis=0))


def _named(cp, rows: np.ndarray) -> str:
    hklm = cp.reflections.hklm
    names = ", ".join(reflection_label(hklm[k]) for k in rows[:NAMED_REFLECTIONS])
    more = len(rows) - NAMED_REFLECTIONS
    return names + (f" and {more} more" if more > 0 else "")


def _refuse_silent_absence(model, values: dict, phase: int, nuisance: str) -> None:
    """Refuse, by name, a reflection the form would leave out in silence.

    Read-only: nothing here enters the arithmetic of a case it accepts.  A
    satellite's factor is 0 in the Rietveld compile (``_nuclear_f2``), so on
    the solved phase its column is empty, under ``"pawley"`` the ``live``
    filter drops it and under ``"scale"`` the impurity's profile is zero at
    it.  Under ``"pawley"`` a nuisance phase's columns are relative to line
    0's intensity (:func:`omega_lines`), zero for a reflection beyond line 0's
    sphere, so a reflection only another line's window holds is dropped too.
    """
    for j, cp in enumerate(model.phases):
        if cp.satellites is None:
            continue
        rows = np.flatnonzero(cp.reflections.is_satellite & _in_range(cp))
        if rows.size:
            role = "the solved phase" if j == phase else f"nuisance phase {j}"
            raise ExtractionRefused(
                "satellite", f"{role} has {rows.size} satellite reflection(s) in "
                f"the fitted range ({_named(cp, rows)}): a satellite has no "
                "nuclear |F|², so the solve cost has no column for it and would "
                "leave its intensity out of the form; drop the propagation "
                "vector, or the range that holds its satellites")
    if nuisance != "pawley":
        return
    for j, cp in enumerate(model.phases):
        if j == phase or cp.win.shape[0] < 2:
            continue
        peaks = model.phase_peaks(j, values)
        line0 = np.asarray(peaks[0][3], dtype=np.float64) > 0
        other = np.zeros_like(line0)
        for il in range(1, len(peaks)):
            other |= ((np.asarray(peaks[il][3], dtype=np.float64) > 0)
                      & (cp.win[il, :, 1] > cp.win[il, :, 0]))
        rows = np.flatnonzero(other & ~line0)
        if rows.size:
            raise ExtractionRefused(
                "secondary_line_only", f"nuisance phase {j} has {rows.size} "
                f"reflection(s) in the fitted range that only a line other than "
                f"line 0 reaches ({_named(cp, rows)}): under nuisance='pawley' "
                "its columns are the line ratios relative to line 0's "
                "intensity, which is zero there, so they would be left out; "
                "pass nuisance='scale', or narrow the range")


def _cell(values: dict, ip: int) -> tuple:
    return tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_KEYS)


def omega_lines(model, ip: int, values: dict, *, with_factor: bool = True
                ) -> list[csr_matrix]:
    """Ω for phase ``ip``, one (points × reflections) matrix per emission line.

    The unit-area profiles are the ``entries`` view of
    :meth:`~rietx.model.forward.CompiledModel.derivative_bases` (Ω alone,
    ``profile_derivs=False``).  The per-(line, reflection) factor is taken by
    linearity: :meth:`~rietx.model.forward.CompiledModel.phase_peaks`' intensity
    over the |F|² it was built from, so it carries whatever the compile applies
    per line — the line weight, Lp at that line's angle, absorption, roughness,
    preferred orientation, multiplicity and the scale.  A Le Bail or Pawley
    compile applies no per-line Lp, which is why the factor is read off a
    Rietveld-mode compile.  ``with_factor=False`` gives each line's columns its
    intensity relative to the first line's instead, which is what a
    free-intensity nuisance phase needs.
    """
    cp = model.phases[ip]
    n_refl = len(cp.reflections)
    bases = model.derivative_bases(values, profile_derivs=False)
    peaks = bases.peaks[ip]
    if with_factor:
        cell = _cell(values, ip)
        ref = np.asarray(model._total_f2(ip, d_spacings(cp.reflections.index, *cell),
                                         values, cell), dtype=np.float64)
    else:
        ref = np.asarray(peaks[0][3], dtype=np.float64)
    safe = np.where(ref > 0, ref, 1.0)
    fac = [np.where(ref > 0, np.asarray(p[3], dtype=np.float64) / safe, 0.0)
           for p in peaks]
    parts: list[tuple[list, list, list]] = [([], [], []) for _ in peaks]
    for il, k, i0, i1, prof, *_ in bases.entries[ip]:
        if fac[il][k] == 0.0:
            continue
        rows, cols, vals = parts[il]
        rows.append(np.arange(i0, i1))
        cols.append(np.full(i1 - i0, k))
        vals.append(np.asarray(prof, dtype=np.float64) * fac[il][k])
    shape = (len(model.tt), n_refl)
    out = []
    for rows, cols, vals in parts:
        if not rows:
            out.append(csr_matrix(shape))
            continue
        om = csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                        shape=shape)
        om.sum_duplicates()
        out.append(om)
    return out


def _omega(model, ip: int, values: dict, *, with_factor: bool) -> csr_matrix:
    """Ω for phase ``ip`` summed over the emission lines (:func:`omega_lines`)."""
    lines = omega_lines(model, ip, values, with_factor=with_factor)
    om = lines[0]
    for extra in lines[1:]:
        om = om + extra
    return om.tocsr()


def _design(model, values: dict, phase: int, background: str, nuisance: str):
    """(y, w, Ω, X): the target, the weights, the solved phase's columns and
    the nuisance columns (``None`` when there are none), as the module
    docstring defines them; y already has every held term subtracted."""
    if not model.phases[phase].skip_extinction and values[f"phases.{phase}.extinction"] != 0:
        raise ExtractionRefused(
            "nonlinear", "primary extinction is on for the solved phase: its "
            "intensity is not linear in |F|² (hold extinction at 0)")
    y = np.asarray(model.y_obs, dtype=np.float64)
    w = 1.0 / np.asarray(model.sigma, dtype=np.float64) ** 2
    if model.peak_components:
        # declared sharp peaks are nonlinear in position and width: held
        y = y - np.asarray(model.extra_peak_curve(values), dtype=np.float64)
    xcols: list[np.ndarray] = []
    if background == "projected":
        if model.bkg_penalty is not None:
            raise ExtractionRefused(
                "nonlinear", "a penalised (P-spline) background cannot be "
                "projected as free coefficients; pass background='held'")
        design = np.asarray(model.bkg_design, dtype=np.float64)
        coeffs = np.array([values[p] for p in model.bkg_paths], dtype=np.float64)
        # the fixed curve and any humps are held; only the linear block moves
        y = y - (np.asarray(model.background(values), dtype=np.float64)
                 - (coeffs @ design if design.size else 0.0))
        if design.size:
            xcols.append(design.T)
    else:
        y = y - np.asarray(model.background(values), dtype=np.float64)
    others = [j for j in range(len(model.phases)) if j != phase]
    for j in others:
        if nuisance == "scale":
            xcols.append(np.asarray(model.phase_component(j, values),
                                    dtype=np.float64)[:, None])
            continue
        omj = _omega(model, j, values, with_factor=False)
        live = np.flatnonzero(omj.getnnz(axis=0))
        if live.size:
            xcols.append(omj[:, live].toarray())

    om = _omega(model, phase, values, with_factor=True)
    return y, w, om, (np.hstack(xcols) if xcols else None)


def _low_rank_pinv(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """L with WX·L·Lᵀ·XᵀW the projection term of P, for G = XᵀWX.

    G is equilibrated to unit diagonal before the cut (root ``CLAUDE.md``,
    the normal-matrix rule; :func:`rietx.optimize.statistics.normal_factors`
    is the same construction): with D = diag(G)^(-1/2), L = D·Q·Λ^(-1/2) from
    the eigenpairs of D·G·D above :data:`NUISANCE_RCOND`.  Rescaling a column
    of X leaves the column space and so the projection unchanged, and the cut
    no longer depends on a column's units: an impurity's stored scale, a free
    nuisance coefficient, otherwise sets the cutoff for the background columns
    (#580 review).  A zero column has no direction and is dropped.
    """
    sw = np.sqrt(w)[:, None] * X
    e = column_rescale(sw)             # exact powers of two, far columns only
    if e is not None:
        sw = sw * e
    G = sw.T @ sw
    G = 0.5 * (G + G.T)
    d = np.sqrt(np.diag(G))
    live = d > 0.0
    inv_d = np.where(live, 1.0 / np.where(live, d, 1.0), 0.0)
    lam, Q = np.linalg.eigh(G * np.outer(inv_d, inv_d))
    keep = lam > NUISANCE_RCOND * max(float(lam[-1]), 0.0)
    if e is not None:
        inv_d = inv_d * e
    return inv_d[:, None] * (Q[:, keep] / np.sqrt(lam[keep]))


def _dummy(species: str):
    from ..schemas.structure import Atom, Parameter

    # a general position with incommensurate coordinates: no reflection the
    # group allows has |F|² = 0 by symmetry, so every column is defined
    return Atom(label="Dummy", species=species, x=Parameter(value=0.1234),
                y=Parameter(value=0.2345), z=Parameter(value=0.3456),
                biso=Parameter(value=0.0))


def blind_structure(structure, phase: int, nuisance: str):
    """A copy of ``structure`` that a solve compiles to read Ω and the factor.

    The solved phase keeps its cell and profile terms and gets one dummy atom
    and scale 1.  Under ``nuisance="pawley"`` every other phase gets a dummy
    atom too (its columns carry line ratios only).  A phase given a dummy loses
    its restraints, which name atoms it no longer has and which the cost does
    not read.  Under ``"scale"`` every other phase keeps its atoms **as
    declared**, and a positive scale: its calculated profile is the impurity's
    column, and nothing here can tell a real structure from a placeholder
    atom (the one Le Bail needs), whose |F|² is then projected as the
    impurity's profile.
    """
    s = structure.model_copy(deep=True)
    for j, ph in enumerate(s.phases):
        if j == phase or nuisance == "pawley":
            ph.restraints = []
            ph.atoms = [_dummy(ph.atoms[0].species)]
        if j == phase or ph.scale.value <= 0:
            ph.scale.value = 1.0
    return s


@dataclass
class SolveCost:
    """χ²(F) at a frozen profile for one phase: the module docstring's form.

    ``F`` is the vector of |F|² over :attr:`hkl` in the units of
    :func:`~rietx.crystallography.structure_factor.structure_factors_squared`
    (electrons², or fm² for neutrons); the scale returned beside χ² multiplies
    the phase scale of the compile the cost was built from, which is 1.
    """

    hkl: np.ndarray            # (N, 3) the frozen reflection list's representatives
    d: np.ndarray              # (N,) d-spacings at the frozen cell, Å
    multiplicity: np.ndarray   # (N,)
    M0: csr_matrix             # (N, N) ΩᵀWΩ, sparse and banded
    V: np.ndarray              # (N, r): M = M0 − V·Vᵀ
    b: np.ndarray              # (N,)
    c: float
    chi2_floor: float          # c − bᵀM⁺b, the Pawley floor of the same form
    intensities: np.ndarray    # (N,) I_P = M⁺b, per-reflection |F|²·s at the floor
    n_points: int
    background: Literal["projected", "held"]
    nuisance: Literal["pawley", "scale"]
    n_nuisance: int            # nuisance columns projected out, background included
    records: dict = field(default_factory=dict)

    # -- the form -------------------------------------------------------------
    def matvec(self, f: np.ndarray) -> np.ndarray:
        """M·f for a vector (N,) or a stack (R, N), without forming M."""
        f = np.asarray(f, dtype=np.float64)
        ft = f.T
        return (self.M0 @ ft - self.V @ (self.V.T @ ft)).T

    def dense(self) -> np.ndarray:
        """M as a dense array: for checks and one-off solves, never a loop."""
        return self.M0.toarray() - self.V @ self.V.T

    def chi2(self, f2: np.ndarray) -> tuple[float, float]:
        """χ² at the closed-form non-negative scale, and that scale."""
        f2 = np.asarray(f2, dtype=np.float64)
        q = float(f2 @ self.matvec(f2))
        p = float(self.b @ f2)
        if q <= 0.0 or p <= 0.0:
            return float(self.c), 0.0
        s = p / q
        return float(self.c - p * s), s

    def chi2_batch(self, f2: np.ndarray) -> np.ndarray:
        """χ² for a stack (R, N) of |F|² vectors, one per replica."""
        f2 = np.atleast_2d(np.asarray(f2, dtype=np.float64))
        q = np.einsum("rn,rn->r", self.matvec(f2), f2)
        p = f2 @ self.b
        ok = (q > 0) & (p > 0)
        out = np.full(len(f2), float(self.c))
        out[ok] = self.c - p[ok] ** 2 / q[ok]
        return out

    def ratio(self, chi2: float) -> float:
        """χ²/χ²_floor; ∞ when the floor is not positive."""
        return float(chi2 / self.chi2_floor) if self.chi2_floor > 0 else np.inf

    # -- construction ---------------------------------------------------------
    @classmethod
    def from_pawley(cls, refinement, data, *, phase: int = 0,
                    background: Literal["projected", "held"] = "projected",
                    nuisance: Literal["pawley", "scale"] = "pawley") -> SolveCost:
        """Build the cost from a converged Le Bail or Pawley ``refinement``.

        ``data`` is the pattern it was fitted to; the 2θ range is the fit's,
        and a fitted-point count other than the fit's is refused
        (``ValueError``).
        Refuses, with :class:`ExtractionRefused`, a magnetic structure, a
        refinement that holds no fit or a Rietveld fit, one whose solver did not
        converge, and one the package calls unusable
        (:attr:`~rietx.schemas.results.RefinementResult.usable`, WP-1902): an
        error-level diagnostic, which today is only ``MODEL_FAR_FROM_DATA``
        at Rwp above :data:`rietx.refine.MODEL_FAR_FROM_DATA_RWP` (0.8).  An
        error-level code added later refuses here with no edit.  That bar is
        the package's measured
        line between a bad fit and no fit of this model (WP-1028 §(c): Rwp = 1
        is y_calc ≡ 0, the zero-scale attractor converges at 0.99999, and the
        failures above it exceed it by orders of magnitude; a Le Bail fit of
        NAC with its cell 3 % off converges at Rwp ≈ 29).  It refuses a
        non-extraction; it is not a quality bar, and a tighter one needs a
        measurement on public data.
        """
        from ..model.forward import compile_model
        from ..params.vector import ParameterTable

        instrument = refinement.fitted_instrument
        # the dummy-atom compile drops every moment, so ask the fitted one
        _refuse_magnetic_model(compile_model(
            refinement.fitted_structure, instrument, data, mode="rietveld",
            two_theta_limits=refinement._two_theta_limits))
        result = getattr(refinement, "result_", None)
        if result is None:
            raise ExtractionRefused(
                "not_an_extraction", "SolveCost.from_pawley needs a Le Bail or "
                "Pawley fit, got no fit: a solve cost is built at free intensities")
        if result.mode not in ("lebail", "pawley"):
            raise ExtractionRefused(
                "rietveld", f"SolveCost.from_pawley needs a Le Bail or Pawley fit, "
                f"got a {result.mode!r} fit: its profile was refined with the "
                "intensities tied to a structure, not extracted")
        if result.status != "converged":
            raise ExtractionRefused(
                "unconverged", f"the extraction's solver stopped with status "
                f"{result.status!r}, not 'converged'; refit before solving")
        rwp = float(result.statistics.rwp)
        if not result.usable:
            errors = ", ".join(sorted({dg.code for dg in result.diagnostics
                                       if dg.level == "error"}))
            raise ExtractionRefused(
                "poor", f"the extraction carries {errors} at Rwp {rwp:.3g}, so "
                "the package calls it unusable (RefinementResult.usable): it is "
                "not a fit of this pattern")
        structure = blind_structure(refinement.fitted_structure, phase, nuisance)
        model = compile_model(structure, instrument, data, mode="rietveld",
                              two_theta_limits=refinement._two_theta_limits)
        if len(model.tt) != result.statistics.n_points:
            raise ValueError(
                f"data gives {len(model.tt)} fitted points where the extraction "
                f"fitted {result.statistics.n_points}: pass the pattern the "
                "refinement was fitted to, with its excluded regions")
        table = ParameterTable(structure, instrument)
        cost = cls.from_model(model, table.decode(table.x0()), phase=phase,
                              background=background, nuisance=nuisance)
        cost.records["extraction"] = {"mode": result.mode, "status": result.status,
                                      "rwp": rwp}
        return cost

    @classmethod
    def from_model(cls, model, values: dict, *, phase: int = 0,
                   background: Literal["projected", "held"] = "projected",
                   nuisance: Literal["pawley", "scale"] = "pawley") -> SolveCost:
        """Build from a **Rietveld-mode** compiled ``model`` at frozen ``values``.

        The lower rung of :meth:`from_pawley`, which compiles the model; this
        one reads whatever structure the model holds, since the per-hkl factor
        intensity/|F|² does not depend on it.  Refuses by name, with
        :class:`ExtractionRefused`, satellites in the fitted range and, under
        ``"pawley"``, a nuisance reflection only a line other than line 0
        reaches (the module docstring's last two refusals).
        """
        if model.mode != "rietveld":
            raise ValueError(
                f"SolveCost.from_model needs a Rietveld-mode compiled model (got "
                f"{model.mode!r}): the per-hkl factor is read as intensity/|F|²")
        if background not in ("projected", "held"):
            raise ValueError(f"background must be 'projected' or 'held', got {background!r}")
        if nuisance not in ("pawley", "scale"):
            raise ValueError(f"nuisance must be 'pawley' or 'scale', got {nuisance!r}")
        _refuse_magnetic_model(model)
        _refuse_silent_absence(model, values, phase, nuisance)
        y, w, om, X = _design(model, values, phase, background, nuisance)
        wom = om.multiply(w[:, None]).tocsr()                 # WΩ
        M0 = (om.T @ wom).tocsr()
        M0 = (0.5 * (M0 + M0.T)).tocsr()
        b = np.asarray(wom.T @ y).ravel()
        c = float(y @ (w * y))
        n_x = 0
        V = np.zeros((len(b), 0))
        if X is not None:
            n_x = X.shape[1]
            wx = w[:, None] * X
            L = _low_rank_pinv(X, w)                          # L·Lᵀ = (XᵀWX)⁺, equilibrated
            yx = L.T @ (wx.T @ y)
            V = np.asarray(wom.T @ X) @ L                     # ΩᵀWX·L
            b = b - V @ yx
            c = c - float(yx @ yx)
        M = M0.toarray() - V @ V.T                            # once, for the floor
        ip_sol, *_ = np.linalg.lstsq(M, b, rcond=None)
        cp = model.phases[phase]
        cell = _cell(values, phase)
        return cls(
            hkl=np.asarray(cp.reflections.index, dtype=np.int64),
            d=np.asarray(d_spacings(cp.reflections.index, *cell), dtype=np.float64),
            multiplicity=np.asarray(cp.reflections.multiplicity, dtype=np.float64),
            M0=M0, V=V, b=b, c=c, chi2_floor=float(c - b @ ip_sol), intensities=ip_sol,
            n_points=len(y), background=background, nuisance=nuisance, n_nuisance=n_x,
            records={"nnz_omega": int(om.nnz), "nnz_M0": int(M0.nnz),
                     "rank_V": int(V.shape[1]), "n_reflections": int(len(b))})
