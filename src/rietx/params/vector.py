"""The named ↔ flat-vector translation layer.

Compiles a (Structure, Instrument) pair into:

* an ordered table of every :class:`Parameter` with a stable dot-separated
  path (``phases.0.cell.a``, ``instrument.profile.w``,
  ``instrument.background.c2`` …);
* an affine constraint block **p_phys = C·p_free + d** (sparse C, rebuilt at
  every stage boundary, constant during a least-squares run — a constant
  matmul stays exact under the future autodiff backends).  Crystal-system
  cell ties are the identity-row special case; Wyckoff site constraints
  (``crystallography.wyckoff``) supply general rows;
* the mapping between the free internal vector θ (what the optimiser sees)
  and the full physical value dict consumed by the forward model.

The decode path is plain float/array arithmetic on a pre-built sparse
matrix — no pydantic objects are touched per iteration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from pydantic import ValidationError
from scipy import sparse

from ..crystallography.adp import U_NAMES
from ..crystallography.stephens import S_NAMES, isotropic_coefficients, strain_basis
from ..crystallography.symmetry import (
    cell_constraints,
    check_cell_angles,
    get_spacegroup,
    rotation_matrices,
)
from ..crystallography.wyckoff import adp_basis, coordinate_basis, stabilizer_rotations
from ..schemas.common import Parameter
from ..schemas.instrument import (
    CAPILLARY_OFFSETS,
    COMPONENT_FIELDS,
    BackgroundFixedPlusChebyshev,
    BackgroundPSpline,
    Instrument,
)
from ..schemas.structure import Structure
from .transforms import dphys_dinternal, internal_bounds, to_internal, to_physical

#: Dot-path suffix of a source line's wavelength row.  One authority for the
#: spelling, since three places test for it: the collector, the freedom check
#: below and the ``WAVELENGTH_CALIBRATION`` diagnostic in ``refine.py`` (shared
#: with the joint path in ``multi.py``).
WAVELENGTH_SUFFIX = ".wavelength"


def _is_wavelength(path: str) -> bool:
    return (path.startswith("instrument.source.lines.")
            and path.endswith(WAVELENGTH_SUFFIX))


def check_wavelength_freedom(free_wavelengths: list[str], n_wavelengths: int,
                             n_histograms: int, *,
                             cell_shared: bool = True) -> None:
    """Refuse a wavelength freedom the data cannot support.  Three cases.

    A powder pattern measures d = λ/(2 sin θ), which fixes only the *product*
    λ·(1/d) — so for **one** histogram a free λ beside a free cell is a flat
    direction, exactly, and no amount of data removes it.  Across **N**
    histograms of one specimen sharing one cell the degeneracy breaks: holding
    one λ pins the cell's scale, and the remaining N − 1 are then
    over-determined by that shared cell and genuinely measurable.  Holding
    *all* of them instead forces every monochromator's calibration error into
    the shared cell; freeing all of them restores the flat direction.

    **The shared cell is the whole mechanism, so it is part of the rule**:

        a free wavelength requires its histogram's cell to be *shared* with at
        least one histogram whose wavelength is held.

    "Exactly one held, at most N − 1 free" is that statement's special case
    when every histogram shares one cell, which is the default
    (:class:`~rietx.params.multi.SharingMap` shares everything that is not
    ``instrument.*`` or ``*.scale``).  Un-share the cell — a legitimate thing to
    want, when two histograms are two preparations — and the degeneracy of a
    single-histogram fit is back inside the joint one, per histogram, which is
    why ``cell_shared=False`` refuses every free λ rather than letting the fit
    wander.

    **Which one to hold is not arbitrary**: hold the wavelength of the
    histogram that determines the cell.  On a synchrotron-plus-neutron pair
    that is the synchrotron — its wavelength calibration is the better known
    *and* its angular resolution makes its cell the better determined — and the
    neutron wavelengths then refine against a cell the X-ray data has pinned,
    which is the only way their monochromator calibrations can be measured at
    all.

    This is :class:`~rietx.schemas.instrument.EmissionLine`'s weight convention
    one rank up — one member of a set pinned to fix a scale the data cannot
    set, the rest free — and the same argument fixes *where* each is enforced.
    A line weight's scale lives inside one source, so line 0 can be locked in
    the collector.  A wavelength's scale lives in the *cell*, which is shared
    across instruments, so no single instrument can count the set and the check
    has to sit at the two constructors that see it: :class:`ParameterTable`
    (which sees one instrument, hence always the N = 1 case) and
    :class:`~rietx.params.multi.MultiParameterTable` (which sees all of them).
    That is why this is a function and not a validator on ``EmissionLine``.

    ``free_wavelengths`` are the free wavelength paths, spelled as the caller's
    own surface spells them; ``n_wavelengths`` is how many wavelength rows the
    whole problem has and ``n_histograms`` how many patterns it stacks.

    **Scope: constant-wavelength only.**  The same fence generalises verbatim to
    a time-of-flight multi-bank fit, where each bank carries its own DIFC
    calibration and exactly one of them must be held to pin the cell; nothing
    here implements TOF.
    """
    if not free_wavelengths:
        return
    if not cell_shared:
        raise ValueError(
            f"{free_wavelengths[0]} cannot vary while the cell is "
            "per-histogram: λ is measurable only against a cell some *other* "
            "histogram's held wavelength has pinned, so a histogram with its "
            "own cell is back in the single-histogram degeneracy — inside a "
            "joint fit, where it looks solved.  Share the cell "
            "(SharingMap's default does) or hold every wavelength")
    if n_histograms < 2:
        raise ValueError(
            f"{free_wavelengths[0]} cannot vary in a single-histogram fit: "
            "d = λ/(2 sin θ) fixes only the product, so a free wavelength "
            "beside a free cell is an exactly flat direction — the same "
            "degeneracy that makes a certified standard's cell the thing you "
            "hold in order to calibrate λ.  It becomes measurable only in a "
            "joint fit of several histograms of one specimen sharing one cell "
            "(rietx.refine_multi), where one wavelength is held and the rest "
            "are free")
    if len(free_wavelengths) >= n_wavelengths:
        raise ValueError(
            f"{len(free_wavelengths)} of {n_wavelengths} wavelengths are "
            f"free; hold one.  Across {n_histograms} histograms of one "
            "specimen the shared cell makes N − 1 wavelengths measurable, but "
            "only because the held one pins the cell's scale — free them all "
            "and the flat direction of a single-histogram fit is back.  Hold "
            f"{sorted(free_wavelengths)[0]} (the convention is to hold the "
            "best-calibrated histogram's) and leave the others free")


def background_parameters(bkg) -> list[tuple[str, Parameter]]:
    """(sub-path, Parameter) pairs for any background model, in design order.

    Design order is what the name says: ``compile_model`` builds the linear
    block's rows in this order, so ``scale`` comes after the Chebyshev
    coefficients here because its row is appended after theirs — the
    ``air`` term's arrangement one member over, and for the same reason.
    """
    if isinstance(bkg, BackgroundPSpline):
        out = [(f"c{n}", p) for n, p in enumerate(bkg.coefficients)]
        out.append(("air", bkg.air_scatter))
        return out
    if isinstance(bkg, BackgroundFixedPlusChebyshev):
        out = [(f"c{n}", p) for n, p in enumerate(bkg.chebyshev.coefficients)]
        out.append(("scale", bkg.scale))
        return out
    return [(f"c{n}", p) for n, p in enumerate(bkg.coefficients)]


def extra_component_parameters(components) -> list[tuple[str, Parameter]]:
    """(sub-path, Parameter) pairs for ``Instrument.extra_components``, or [].

    Shared by the collector and by :meth:`ParameterTable.apply_to_models` for
    the reason :func:`roughness_parameters` is — a parameter registered in one
    and forgotten in the other silently loses its refined value at the next
    stage's recompile, which has bitten this file before.  ``[]`` for the empty
    list, so a table built from an instrument that declares no component is
    byte-for-byte the pre-``extra_components`` table.

    The index comes first (``0.position``, not ``position.0``) so the component,
    not the field, is the thing a path prefix names, and so a plan can free one
    declared component (``instrument.extra_components.0.*``) without touching
    the others.

    **Member-agnostic by dispatch, never by ``isinstance``.**  Which fields a
    member refines is read from :data:`~rietx.schemas.instrument.COMPONENT_FIELDS`
    keyed by its ``kind`` — clause 4 of the member contract, whose whole point is
    that this function and ``apply_to_models`` cannot be grown out of step.  A
    ladder here would be a second ladder there, and the failure is silent.
    """
    return [(f"{i}.{name}", getattr(comp, name))
            for i, comp in enumerate(components)
            for name in COMPONENT_FIELDS[comp.kind]]


def roughness_parameters(rough) -> list[tuple[str, Parameter]]:
    """(sub-path, Parameter) pairs for a surface-roughness block, or [].

    Shared by the collector and by :meth:`ParameterTable.apply_to_models` on
    purpose: a parameter registered in one and forgotten in the other silently
    loses its refined value at the next stage's recompile, which has bitten this
    file before (see the coordinate write-back comment below).  One source of
    truth for the field names makes that class of bug unrepresentable.

    The sub-path is the model's own field name, so the ``kind`` is legible
    straight from the dot-path (``…surface_roughness.b`` vs
    ``…surface_roughness.tau``) and a glob over
    ``instrument.geometry.surface_roughness.*`` frees whichever model is
    attached without the stage plan having to know which one it is.
    """
    if rough is None:
        return []
    return [(name, getattr(rough, name)) for name in type(rough).model_fields
            if name != "kind"]


@dataclass(frozen=True)
class AffineTie:
    """Declares one physical parameter as an affine function of others.

    value(path) = Σ coeff · value(source path) + const.  Sources may
    themselves be tied (chains are flattened at rebuild); cycles are an
    error.  :meth:`identity` gives the b ← a cell-tie special case.
    """

    terms: tuple[tuple[str, float], ...]
    const: float = 0.0

    @classmethod
    def identity(cls, source: str) -> "AffineTie":
        return cls(terms=((source, 1.0),))


@dataclass
class Entry:
    """One row of the internal free-parameter vector — ``.value`` is the number.

    Public callers want the mirror instead:
    ``rietx.ParameterRow``/``Refinement.parameters()``, which adds the esd a
    completed fit measured and every held row this internal table drops.
    """

    path: str
    value: float
    vary: bool
    lo: float
    hi: float
    transform: str
    tie: AffineTie | None = None  # affine dependence on other entries
    locked: bool = False  # structurally fixed: set_vary may never free it


#: Path prefix of a caller's own named variable (WP-1119).  A variable is a
#: synthetic entry like a Wyckoff DOF, so it needs a namespace outside the model
#: tree; ``phases`` and ``instrument`` are that tree's only top-level segments,
#: so ``vars.`` cannot collide, and it is a plain dot-path so ``set_vary("vars.*")``
#: globs it like anything else.  Declared here because this module is where a
#: path means something, and read by ``Refinement`` and the tie verbs.
VAR_PREFIX = "vars."


def is_variable_path(path: str) -> bool:
    """Is ``path`` a caller's named variable rather than a model parameter?

    One predicate rather than a repeated ``startswith``, because two rules turn
    on it and they must not drift: a tied source is accepted only where this is
    true (a variable may follow other variables — TOPAS's ``prm B = 2 A`` — while
    a tied *model* path keeps the refusal that steers a caller to what it
    follows), and only a path answering true is written back to the variable
    register instead of into the pydantic models.
    """
    return path.startswith(VAR_PREFIX)


#: Cell parameter names in table order — lengths first, then angles.
_CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")

#: Fraction of the value a stage *starts from* that a cell length may travel
#: within that stage, and an additive pad in Å so a small cell is not held
#: tighter than a large one in absolute terms.
CELL_WINDOW_FRACTION = 0.05
CELL_WINDOW_PAD_A = 0.05

#: The same window for a cell angle, in degrees.
CELL_WINDOW_ANGLE_DEG = 2.0

#: Absolute floor on a cell length (Å).  TOPAS's number; no crystal has a
#: lattice repeat this short, so it is a floor on nonsense rather than a
#: refinement bound.
CELL_MIN_LENGTH_A = 1.5

#: Unconditional post-solve safety window (fraction, degrees) — see
#: ``refine.clamp_cell_runaway``, which applies this to *every* free cell
#: parameter regardless of ``phase_support``, after a stage has solved and
#: committed.  ``phase_support`` (the authority behind ``cell_window``'s own
#: window above, and ``refine._hold_unsupported_phases``, WP-1301) is a
#: per-phase amplitude test and cannot see a *joint* degeneracy: two free
#: phases sharing a near-identical cell trade scale against each other along
#: an axis that is exactly as flat as an absent phase's, and the phase that
#: ends up walking it can be the one with the real, undiminished scale — its
#: own modelled contribution never drops below
#: :data:`~rietx.model.forward.PHASE_SUPPORT_SIGMA`, so neither the window
#: nor the hold ever applies to it.  Measured (a multi-phase in-situ
#: series, 2026-09-17): a synthetic two-phase LaB6 pattern, one copy at full scale
#: and a second at a 2 % trace with the *same* starting cell, freeing scale
#: and cell together in one stage — the fully-supported phase's own cell
#: (not the trace phase's) ran 4.1566 -> 3803 Å in twenty TRF iterations of
#: that one stage, unwindowed the whole time, and crashed the next stage's
#: ``generate_reflections`` with the WP-1110 refusal before
#: ``freeze_cell_windows`` for that next stage ever ran.
#:
#: Applied to the *outcome*, never as a live solver bound: a bound scipy's
#: TRF actually sees changes its trust-region step scaling even when never
#: hit (measured, WP-1110: windowing an honest phase's cell alone took the
#: IUCr ``cpd-1c`` collapsed refit from 82 to its 400-iteration budget and
#: left it at a worse Rwp) — which is exactly why the support-based window
#: is restricted to phases judged invisible rather than applied to every free
#: cell, and why this fallback cannot be a second live bound without costing
#: every other test's iteration count and pinned digits.  A stage that never
#: leaves this window (every one WP-1110's own 51-transition survey measured:
#: worst honest single-stage move 2.8e-4 relative, five orders inside it) is
#: therefore bit-identical whether or not this check exists at all.
#: ±15 % is three times :data:`CELL_WINDOW_FRACTION` — wide enough that no
#: real measurement needs it (thermal expansion and a composition swing are
#: each a few percent at most) and narrow enough that an escaping cell is
#: pulled back in Å rather than left to reach the thousands.
CELL_SAFETY_FRACTION = 0.15
CELL_SAFETY_ANGLE_DEG = 3.0 * CELL_WINDOW_ANGLE_DEG

#: A cell angle is degenerate at 0° and 180° — the metric tensor is singular
#: there — so the window is clipped inside them.
_ANGLE_MIN_DEG = 1.0
_ANGLE_MAX_DEG = 179.0


def _cell_parameter_name(path: str, *, phases: set[int] | None) -> str | None:
    """``"phases.0.cell.a"`` → ``"a"`` when phase 0 is in ``phases``, else None.

    ``phases=None`` means *any* phase — the unconditional safety fallback in
    :meth:`ParameterTable.bounds` asks this of every free cell path regardless
    of which phase it belongs to, where the support-based window asks it only
    of the phases ``freeze_cell_windows`` declared.

    Read off the path rather than recorded on the :class:`Entry`, because the
    window is applied at the optimiser interface and the entries there arrive
    from :meth:`ParameterTable.bounds` with nothing but their paths to go on.
    """
    parts = path.split(".")
    if len(parts) == 4 and parts[0] == "phases" and parts[2] == "cell":
        if parts[3] not in _CELL_NAMES:
            return None
        try:
            ip = int(parts[1])
        except ValueError:
            return None
        return parts[3] if phases is None or ip in phases else None
    return None


def cell_window(name: str, value: float, lo: float, hi: float,
                *, path: str | None = None,
                fraction: float = CELL_WINDOW_FRACTION,
                angle_deg: float = CELL_WINDOW_ANGLE_DEG) -> tuple[float, float]:
    """The default bounds on one cell parameter, anchored at ``value``.

    ``fraction``/``angle_deg`` default to the per-phase-support window's own
    constants; ``refine.clamp_cell_runaway`` passes
    :data:`CELL_SAFETY_FRACTION`/:data:`CELL_SAFETY_ANGLE_DEG` instead, three
    times as wide, to pull an escaped cell back after a stage regardless of
    which phase it belonged to — see that constant's docstring.  Every
    existing caller of this function keeps the old numbers.

    **Why a cell needs a default bound at all.**  Every structural parameter of
    a phase reaches the pattern only through ``scale × |F|² × profile``, so a
    phase whose scale has fallen to its floor contributes a *flat direction*:
    moving its cell changes the calculated pattern by nothing, the Jacobian
    column is zero to within noise, and the trust region wanders along it.  The
    fit still reports ``converged`` — the runaway parameter genuinely does not
    affect Rwp — while the reflection count grows with the cell volume until
    :func:`~rietx.crystallography.symmetry.generate_reflections` refuses
    outright, hundreds of stages downstream of the cause.  Measured in WP-1110:
    an absent phase went 5.2 → 25.6 Å in one synthetic fit (Rwp 0.0415,
    ``converged``), and two independent agents drove real phases to a ≈ 39 293 Å
    and a ≈ 40 000 Å on a 68-pattern series.

    **The shape is TOPAS's** (TOPAS-Academic v8 Technical Reference § 2.17,
    Table 2-1), which bounds ``a, b, c`` by ``Max(1.5, 0.995·Val − 0.05)`` to
    ``1.005·Val + 0.05`` and the angles by ``Val ± 0.2``, re-evaluating ``Val``
    every iteration — *"hard limits are avoided where possible; instead,
    parameter values move within a range during an iteration."*  A moving
    window is not available here: a stage hands ``scipy.optimize.least_squares``
    one fixed ``bounds`` pair.  So the window is re-anchored at every **stage**
    compile instead — this table is rebuilt there, and ``apply_to_models``
    writes back only ``Parameter.value``, so the window never enters the stored
    structure and a cell that legitimately drifts across a series re-anchors on
    every stage of every pattern.

    That makes the fraction a stage's worth of TOPAS travel rather than an
    iteration's, and 0.5 % per iteration compounds to 5.1 % over ten.  WP-1110
    measured the other side of it: across 51 stage transitions of the 11-BM NAC
    and SRM 660c protocols the widest honest single-stage move was 2.8e-4
    (median 9.2e-8), a synthetic LaB₆ started 1 % wrong closed the whole gap in
    one stage at 9.9e-3, and started 3 % wrong the fit failed on its own (Rwp
    0.96) with the basin, not any bound, as the obstacle.  So
    :data:`CELL_WINDOW_FRACTION` clears the widest legitimate single-stage move
    by 5× and the real-protocol one by 180×.

    **A finite stored bound is the caller's claim and is kept**, per side —
    TOPAS's *"user defined min/max limits override the defaults"*.  Only an
    infinite side is a side on which nobody made a claim, and ±inf is what a
    :class:`~rietx.schemas.common.Parameter` carries when its bounds were never
    set.  That test is used rather than ``model_fields_set`` because it has to
    survive a JSON round trip, where every field arrives "set".

    **It is applied only to phases the data cannot see** — the set
    ``run_least_squares`` freezes through
    :meth:`ParameterTable.freeze_cell_windows`, off
    :meth:`~rietx.model.forward.CompiledModel.phase_support` — and that
    restriction is measured, not conservatism.  A window is not free: scipy's
    TRF derives its per-coordinate trust-region scale from the distance to the
    bounds, so bounding a cell changes the *step* the solver takes in it even
    when the bound is never reached.  Measured on the IUCr round robin's
    chained ``cpd-1c``, whose cell finishes 0.24 Å inside a ±5 % window and
    never touches it: windowing every phase took the collapsed warm refit from
    82 iterations to its 400-iteration budget, and it stopped at Rwp 0.1501
    against 0.1079 — just good enough to clear ``sequential``'s reseed fence, so
    the pattern was accepted rather than rescued and its corundum fraction came
    back 9.04 wt % against 6.30. A bound that silently degrades a fit nothing
    reports is the failure this WP exists to remove, not a cost worth paying on
    phases that were never going to run away.

    (The same sweep found ±10 % and wider *beating* unbounded on that pattern —
    82 iterations against 641, same answer — because finite bounds precondition
    a badly-scaled problem.  That is a speed lead for the v1.1 harness WPs, not
    something to take here: a correction does not ship on an Rwp comparison, and
    this one's evidence is a diagnostic.)
    **A value no cell can take is refused here, by name.**  The clamp below
    keeps the window from excluding where the parameter already is, and a
    *positive* length under :data:`CELL_MIN_LENGTH_A` therefore keeps its
    window and travels — a cell below the floor is a model to refuse where
    there is a diagnostics channel (the rule in ``crystallography.cif`` one
    rank up), not a bound to raise on here.  But a length ``≤ 0`` or an angle
    outside ``(0°, 180°)`` is not a short cell, it is not a cell: the metric
    tensor is singular or indefinite there, and the clamp turns it into a
    *degenerate* window, because ``value·(1 + f) + pad < value`` once
    ``value ≤ −pad/f`` snaps both ends onto ``value``.  ``least_squares``
    then raises ``Each lower bound must be strictly less than each upper
    bound``, which names no parameter, nothing about cells and nothing about
    the phase — measured in WP-1130, where a trigonal ``a`` ran to −42.7 Å
    during a cumulative stage and the traceback said none of that.  So the
    raise is made here instead, carrying ``path``.  The postcondition is the
    point and is asserted at the end: this function never returns
    ``lo >= hi``.
    """
    where = repr(path) if path is not None else f"cell parameter {name!r}"
    if name in ("alpha", "beta", "gamma"):
        if not 0.0 < value < 180.0:
            raise ValueError(
                f"{where} is {value}°, which is not a cell angle: the metric "
                "tensor is singular at 0° and 180° and indefinite outside "
                "them.  Refuse the model rather than bounding it — a cell "
                "this far out is a transcription or a diverged stage, not a "
                "parameter to window.")
        window_lo = max(_ANGLE_MIN_DEG, value - angle_deg)
        window_hi = min(_ANGLE_MAX_DEG, value + angle_deg)
    else:
        if not value > 0.0:
            raise ValueError(
                f"{where} is {value} Å, which is not a cell length.  Refuse "
                "the model rather than bounding it — a cell this far out is a "
                "transcription or a diverged stage, not a parameter to "
                f"window.  (A positive length below the {CELL_MIN_LENGTH_A} Å "
                "floor is left alone here and reported where there is a "
                "diagnostics channel.)")
        window_lo = max(CELL_MIN_LENGTH_A,
                        value * (1.0 - fraction) - CELL_WINDOW_PAD_A)
        window_hi = value * (1.0 + fraction) + CELL_WINDOW_PAD_A
    # never propose a window that excludes where the parameter already is: a
    # cell below the floor is a model to refuse elsewhere, not a bound to raise
    # on here (ParameterTable has no diagnostics channel — the rule in
    # crystallography.cif one rank up)
    window_lo, window_hi = min(window_lo, value), max(window_hi, value)
    out_lo = window_lo if lo == -np.inf else lo
    out_hi = window_hi if hi == np.inf else hi
    if not out_lo < out_hi:
        # The window branches above cannot produce this (both clamp around
        # ``value``), so it is always a *stored* bound pair that has no
        # interior: ``min == max`` passes the schema's ``min <= value <= max``
        # and reaches here whenever such an entry is also free.  Kept because
        # the caller hands scipy this pair directly and a degenerate one is
        # what WP-1130 came here for.
        raise ValueError(
            f"{where}: the window for value {value} is degenerate, "
            f"[{out_lo}, {out_hi}].  A stored bound pair with no interior "
            "(min == max) on a free parameter is the way to reach this; "
            "fix the model rather than refining against it.")
    return out_lo, out_hi


#: The sample strain terms this cap covers, in the units each one is stored in:
#: ``lor_strain`` is a Lorentzian **FWHM** coefficient (deg 2θ, multiplying
#: tanθ) and ``gauss_strain`` a Gaussian **variance** coefficient (deg² 2θ,
#: multiplying tan²θ) — see :mod:`rietx.model.profiles.caglioti`.  So one cap
#: expressed as a width governs both, squared for the variance, and there is no
#: second number to calibrate.
_STRAIN_NAMES = ("lor_strain", "gauss_strain")

#: How much of the **fitted** 2θ range one strain term's own FWHM contribution
#: may reach at the pattern's highest θ.  1.0 is the statement that a line
#: wider than the whole range it was measured over is not a line: at that width
#: the phase has stopped being a set of peaks and become a second background,
#: which is a numerical regime and not a strained sample.  Deliberately not
#: calibrated to any material — see :func:`strain_cap`.
STRAIN_CAP_RANGE_FRACTION = 1.0

#: Hysteresis.  The cap is armed only where the term has already reached it
#: (:func:`strain_cap_hi`), and TRF leaves a bounded iterate a hair *inside*
#: its bound, so an exactly-equal test would disarm the cap on the stage after
#: it fired and let the runaway restart.  Eight orders of magnitude above the
#: ~1e-14 relative offset ``run_least_squares``' feasibility clip introduces,
#: and far below any move a fit makes on purpose.
STRAIN_CAP_ARM_RTOL = 1e-6

#: Both range backstops have a pole at θ = 90°, i.e. at 2θ = 180° — tanθ → ∞
#: for strain and cosθ → 0 for size — where the cap would collapse to zero for a
#: reason that is about arithmetic and not about peak widths.  A pattern reaching
#: there is clipped to this θ instead.  One constant because it is one
#: pathology; see :func:`_backstop_span_theta`.
_BACKSTOP_THETA_MAX_DEG = 89.0


def _backstop_span_theta(tt_min: float, tt_max: float) -> tuple[float, float] | None:
    """``(span, θ)`` for a range backstop, or ``None`` where the range states none.

    The part of :func:`strain_cap` and :func:`size_cap` that is genuinely *one*
    rule — "a line wider than the interval it was measured over is not a line",
    evaluated at the highest θ the scan reaches, clipped off the shared
    2θ = 180° pole (:data:`_BACKSTOP_THETA_MAX_DEG`).

    What is **not** shared deliberately stays with each cap: the angular factor
    is the physics (÷tanθ for strain, ×cosθ for size) and each carries its own
    fraction, so folding those in would make one function that means two things.
    Nor is the degenerate handling folded in — each cap guards its own trig
    value, because "θ too small for tanθ to be usable" and "cosθ ≈ 1, so the
    backstop is just the span" are different answers to the same θ.

    ``None`` is "no claim", the honest output for an empty or inverted fitted
    range, which both callers read as ``inf``.
    """
    span = float(tt_max) - float(tt_min)
    if not span > 0.0:
        return None
    return span, min(float(tt_max) / 2.0, _BACKSTOP_THETA_MAX_DEG)


def _strain_parameter_name(path: str) -> str | None:
    """``"phases.0.lor_strain"`` → ``"lor_strain"``, anything else → None.

    Read off the path for the same reason :func:`_cell_parameter_name` is: the
    cap is applied at the optimiser interface, where entries arrive from
    :meth:`ParameterTable.bounds` with nothing but their paths to go on.
    """
    parts = path.split(".")
    if len(parts) == 3 and parts[0] == "phases" and parts[2] in _STRAIN_NAMES:
        try:
            int(parts[1])
        except ValueError:
            return None
        return parts[2]
    return None


def strain_cap(tt_min: float, tt_max: float) -> float:
    """The widest ``lor_strain`` (deg 2θ) the *fitted range* can express.

    **Why strain needs a bound at all.**  The sample strain terms enter the
    profile as Γ_L = ``lor_strain``·tanθ and Γ_G² = ``gauss_strain``·tan²θ
    (:mod:`rietx.model.profiles.caglioti`), and nothing in that arithmetic
    stops at a physical strain.  Measured on a 248-pattern CuO→Cu reduction
    series (issue #140): Cu's ``lor_strain`` exceeded 1 in 133 of 248 patterns
    and peaked at 1.1e5, against 0.3 in the TOPAS protocol for the same data.
    The consequences are not a slightly wide peak — at that width the phase's
    lines are flat across the whole scan, so it is degenerate with the
    background, a genuine 16 wt % support phase was starved below 1 wt % in
    195 of 248 patterns, absolute weight fractions inflated ×1.19, and the
    covariance overflowed until 179 of 248 patterns returned weight-fraction
    esds above 100 wt % (worst 1.3e10).

    **Where the number comes from.**  Not from a material and not from TOPAS's
    0.3, both of which are claims about how strained a sample may be — a bound
    on *that* would prejudge the physics, and nanocrystalline and heavily
    defective specimens legitimately live far out in that tail.  It comes from
    the measurement instead: a peak whose FWHM exceeds the 2θ interval it was
    measured over carries no information the fit could have got from the data.
    So the contribution the strain term alone makes at the pattern's highest θ
    is held to :data:`STRAIN_CAP_RANGE_FRACTION` of the fitted range,

        ``lor_strain`` · tan(θ_max) ≤ f · (2θ_max − 2θ_min),

    and the Gaussian variance to the square of the same width.  This is
    dimensional and self-scaling — a 15–80° lab scan and a 0.5–50° synchrotron
    scan get different caps out of one rule, and no magic constant enters —
    which is the same reasoning ``mu_t``'s off state and the observation counts
    already use: a bound the measurement itself states.

    It is also *generous by construction*.  On a 10–80° scan it is ≈ 83.4 deg:
    278× the TOPAS protocol's 0.3, 56× the ``STRAIN_UNUSUALLY_LARGE`` flag
    below, and still 1300× under the runaway above.  That separation is the
    design and not slack — this fence is not the judgement about whether a
    strain is *believable*, which is a question about the sample that only a
    reader can settle.  That judgement is
    :data:`~rietx.refine.STRAIN_FLAG_WIDTH`, set from the corpus of solved
    refinements, which changes no number and only speaks.

    **Enforced at stage granularity**, exactly like :func:`cell_window`, and
    with the same consequence: a single stage that starts below the cap is
    unbounded and can cross it, and the *next* stage — plans are cumulative,
    so a strain term freed once stays free — pulls it back and reports
    ``BOUND_HIT``.  A fence to be pulled back behind, not one it is forbidden
    to cross.  That is also what keeps an untriggered fit bit-identical: a
    finite bound is never free (TRF takes its per-coordinate trust-region scale
    from the distance to the bounds), so it is spent only where the value has
    already gone somewhere the data cannot express.

    Returns ``inf`` when the range cannot state a bound — an empty or
    degenerate fit range, or one that does not reach far enough in θ for tanθ
    to be usable — because "no claim" is the honest output there.
    """
    backstop = _backstop_span_theta(tt_min, tt_max)
    if backstop is None:
        return math.inf
    span, theta = backstop
    tan_theta = math.tan(math.radians(theta)) if theta > 0.0 else 0.0
    if not tan_theta > 0.0:
        return math.inf
    return STRAIN_CAP_RANGE_FRACTION * span / tan_theta


def strain_cap_hi(name: str, value: float, hi: float, cap: float) -> float:
    """The upper bound one strain term takes this stage — ``hi`` unless capped.

    ``cap`` is :func:`strain_cap`'s width; ``gauss_strain`` is a variance and
    takes its square, so the two terms are held to the *same* width.

    Two clauses, and both are load-bearing:

    * **A finite stored bound is the caller's claim and is kept.**  ``±inf`` is
      what a :class:`~rietx.schemas.common.Parameter` carries when nobody set
      its bounds, so an infinite side is the only side on which no claim was
      made — :func:`cell_window`'s rule, and TOPAS's *"user defined min/max
      limits override the defaults"*.  Setting ``max`` on the parameter is
      therefore also the one-line way to switch this cap off: any finite value,
      including a deliberately enormous one, outranks it.
    * **Armed only where the term has already reached the cap**
      (:data:`STRAIN_CAP_ARM_RTOL`).  A bound changes the solver's step in a
      coordinate even where it is never approached, so a fit whose strain stays
      in the range the data can express must not pay for it, and does not: it
      gets no bound at all and is bit-identical to an uncapped build.
    """
    if not math.isinf(hi):
        return hi
    if not math.isfinite(cap):
        return hi
    limit = cap * cap if name == "gauss_strain" else cap
    if value >= limit * (1.0 - STRAIN_CAP_ARM_RTOL):
        return limit
    return hi


#: The sample size terms this cap covers, in the units each one is stored in:
#: ``lor_size`` is a Lorentzian **FWHM** coefficient (deg 2θ, multiplying
#: 1/cosθ) and ``gauss_size`` a Gaussian **variance** coefficient (deg² 2θ,
#: multiplying 1/cos²θ) — see :mod:`rietx.model.profiles.caglioti`.  So one cap
#: expressed as a width governs both, squared for the variance, exactly as the
#: strain pair above.
_SIZE_NAMES = ("lor_size", "gauss_size")

#: The smallest crystallite (Å) the size cap will let a fit *reach* — a floor
#: on size, hence a ceiling on the 1/cosθ coefficient.  **2 nm, deliberately
#: permissive.**  This is not a physics claim about how small a crystallite may
#: be (genuinely nanocrystalline specimens reach a few nm and must refine
#: freely); it is a runaway fence a couple of unit cells below anything the
#: archive contains — the smallest well-determined refined size in 606 solved
#: TOPAS refinements is ≈ 33 nm, and every refined size below ~2 nm in that
#: corpus is an exploratory or placeholder fit (a phase named ``pixie_dust``, a
#: 0.69 nm "crystallite" of Si — smaller than 1.3 unit cells — in a folder
#: literally named *To Rietveld or not to Rietveld*).  The surprising-but-
#: possible band above it is the :data:`~rietx.refine.SIZE_FLAG_SIZE_A` flag,
#: which bounds nothing.  See :func:`size_cap`.
SIZE_CAP_MIN_SIZE_A = 20.0

#: The range backstop's fraction, the strain rule reused: a size term whose own
#: FWHM at the highest θ exceeds this fraction of the fitted range is a line
#: wider than the interval it was measured over.  On any real scan this is far
#: looser than the 2 nm floor (≈ 54 deg on a 10–80° Cu scan against ≈ 4 deg), so
#: it binds only in degenerate high-angle windows where 1/cosθ blows up — the
#: floor is what governs everywhere else.
SIZE_CAP_RANGE_FRACTION = 1.0

#: Hysteresis, for the reason :data:`STRAIN_CAP_ARM_RTOL` is: TRF leaves a
#: bounded iterate a hair inside its bound, so an exactly-equal arming test
#: would disarm the cap on the stage after it fired.
SIZE_CAP_ARM_RTOL = 1e-6


def _size_parameter_name(path: str) -> str | None:
    """``"phases.0.lor_size"`` → ``"lor_size"``, anything else → None.

    Read off the path like :func:`_strain_parameter_name`, for the same reason:
    the cap is applied at the optimiser interface where entries arrive from
    :meth:`ParameterTable.bounds` with nothing but their paths to go on.
    """
    parts = path.split(".")
    if len(parts) == 3 and parts[0] == "phases" and parts[2] in _SIZE_NAMES:
        try:
            int(parts[1])
        except ValueError:
            return None
        return parts[2]
    return None


#: Scherrer K for the size cap's physics floor — a **deliberate second spelling**
#: of :data:`~rietx.model.profiles.caglioti.SCHERRER_K`, not an independent
#: choice.  Spelled twice because :func:`size_cap` inlines caglioti eq. (4) to
#: keep this module free of a ``params`` → ``model`` import (the formula's
#: authority is there, and the inline is one expression); the two spellings are
#: held together by an equality pin rather than by this comment —
#: ``tests/test_strain_cap.py::test_the_size_caps_scherrer_k_is_the_one_in_caglioti``,
#: which fails if either number moves.  Same idiom as
#: ``schemas.structure._SOFTPLUS_FLOOR`` against
#: ``params.transforms._SOFTPLUS_MIN``.
_SIZE_CAP_SCHERRER_K = 0.9


def size_cap(tt_min: float, tt_max: float, wavelength_a: float,
             *, k: float = _SIZE_CAP_SCHERRER_K,
             min_size_a: float = SIZE_CAP_MIN_SIZE_A) -> float:
    """The widest ``lor_size`` (deg 2θ) allowed: the *tighter* of a 2 nm floor
    and the fitted-range backstop.

    **Why size needs a bound at all, and why a gentle one.**  The sample size
    terms enter the profile as Γ_L = ``lor_size``/cosθ and Γ_G² =
    ``gauss_size``/cos²θ (:mod:`rietx.model.profiles.caglioti`), and nothing in
    that arithmetic stops at a physical crystallite — the same runaway geometry
    the strain terms have.  But unlike strain the intent here is only to catch a
    runaway, never to legislate a size: real specimens are genuinely
    nanocrystalline, so the floor is set two unit cells *below* the archive
    (:data:`SIZE_CAP_MIN_SIZE_A`), where a "crystallite" has stopped being one.

    **The two bounds, and which binds.**  A 1/cosθ coefficient maps to a
    Scherrer size with no reference angle (caglioti eq. 4,
    :func:`~rietx.model.profiles.caglioti.size_coefficient_for_size`): a floor
    ``L ≥ min_size_a`` is therefore a ceiling

        ``lor_size`` ≤ (180/π)·k·λ / min_size_a          [the physics floor]

    on the coefficient directly, per wavelength — ≈ 3.97 deg at Cu Kα for 2 nm,
    i.e. Michael's "≈ 4°/cosθ".  The range backstop is the strain rule with
    1/cosθ in place of tanθ, evaluated where 1/cosθ is largest (the highest θ):

        ``lor_size``/cos θ_max ≤ f·(2θ_max − 2θ_min)     [the range backstop]

    The Gaussian variance takes the square of whichever width binds.  On every
    normal scan the physics floor is far the tighter (Cu 10–80°: ≈ 4 deg against
    ≈ 54 deg), so the floor governs and the backstop only catches the arithmetic
    pathology of 1/cosθ near 2θ = 180°.  Returns ``inf`` when neither can state
    a bound (no wavelength *and* a degenerate range) — "no claim" is honest.

    Enforced at stage granularity, armed only on a term that has already reached
    the cap, and outranked by any finite stored ``max`` — all exactly as
    :func:`strain_cap`/:func:`strain_cap_hi`, and for the same measured
    identity reason: a finite bound is never free.
    """
    # physics floor: L ≥ min_size_a  ⇔  lor_size ≤ (180/π)·k·λ/min_size_a.
    # This is caglioti.size_coefficient_for_size(min_size_a, λ, k) inlined to
    # keep this hot module free of a model import; the formula's authority is
    # there.
    physics = math.inf
    if wavelength_a > 0.0 and min_size_a > 0.0 and k > 0.0:
        physics = math.degrees(k * wavelength_a / min_size_a)
    # range backstop: 1/cosθ is largest at θ_max, and the shared θ clip
    # (:func:`_backstop_span_theta`) keeps it off the cosθ → 0 pole at 2θ = 180°.
    rng = math.inf
    backstop = _backstop_span_theta(tt_min, tt_max)
    if backstop is not None:
        span, theta = backstop
        cos_theta = math.cos(math.radians(theta)) if theta > 0.0 else 1.0
        rng = SIZE_CAP_RANGE_FRACTION * span * cos_theta
    return min(physics, rng)


def size_cap_hi(name: str, value: float, hi: float, cap: float) -> float:
    """The upper bound one size term takes this stage — ``hi`` unless capped.

    The mirror of :func:`strain_cap_hi`: ``cap`` is :func:`size_cap`'s width,
    ``gauss_size`` is a variance and takes its square, a finite stored ``hi`` is
    the caller's claim and is kept (the off switch), and the cap is armed only
    where the coefficient has already reached it.  Because the cap is a ceiling
    on the coefficient — a *floor* on the crystallite — reaching it means the
    fit has driven the size down to 2 nm, which is where a runaway lives.
    """
    if not math.isinf(hi):
        return hi
    if not math.isfinite(cap):
        return hi
    limit = cap * cap if name == "gauss_size" else cap
    if value >= limit * (1.0 - SIZE_CAP_ARM_RTOL):
        return limit
    return hi


def _tie_text(tie: AffineTie) -> str:
    """``2·phases.0.atoms.0.biso + 0.5`` — a tie in the spelling a caller wrote."""
    parts = [f"{coeff:g}\u00b7{src}" for src, coeff in tie.terms]
    if tie.const:
        parts.append(f"{tie.const:g}")
    return " + ".join(parts)


def tie_window(lo: float, hi: float, coeff: float,
               offset_lo: float, offset_hi: float) -> tuple[float, float]:
    """Where a source must stay for its dependent to honour *its own* bounds.

    A tie says ``dependent = coeff·source + offset``, and the dependent carries
    the schema's declared physical limits ``[lo, hi]`` — ``Biso`` in [0, 25],
    ``occ`` in [0, 1.5], March-Dollase ``r`` in its floored range.  The solver's
    box, though, covers the **free** column, and a tied entry is not one, so
    nothing stops a coefficient other than 1 carrying the dependent straight
    past a limit that is physics.  This is the interval that stops it:
    ``lo ≤ coeff·s + offset ≤ hi`` solved for ``s``, with the sign of ``coeff``
    swapping the ends.

    ``offset_lo``/``offset_hi`` bracket everything in the tie that is *not*
    this source — the flattened constant, every held source, and every other
    free source at its own declared bounds.  With one source they are equal and
    the answer is exact.  With several they are not, and the answer is the
    **outer** box: the projection of a half-space onto one axis, which can
    admit an infeasible corner but can never exclude a feasible point.  That
    direction is the whole point — a relaxation bounds the runaway wherever the
    co-sources are themselves bounded and gets out of the way where they are
    not, whereas the inner box would quietly delete solutions the caller asked
    for.  An unbounded co-source gives ±inf here, which is the honest answer.

    Applied in :meth:`ParameterTable.bounds` beside :func:`cell_window`,
    :func:`strain_cap_hi` and :func:`size_cap_hi`, and for the same reason they
    live there: it is a **solver** bound for the stage about to run, derived
    from two declarations the caller already made, never a fact about the
    stored parameter — so it must not surface through ``ParameterRow`` or the
    ``.rxt`` document as a claim nobody wrote.  **Last of the four, and that is
    load-bearing**: :func:`cell_window` reads an infinite side as the side
    nobody claimed, so a window applied ahead of it would pass as a claim the
    caller never made and switch the runaway guard off (measured: the cell comes
    back at the dependent's own [0, 100] instead of [3.89877, 4.41443]).

    **Prior art.**  TOPAS honours bounds inside the matrix solve and lets a
    limit itself be an expression of other parameters (Coelho, 2018,
    *J. Appl. Cryst.* **51**, 210, §3.2).  Structurally it never meets this
    case at all: a constrained quantity there is an *equation* rather than a
    parameter, so it carries no limits of its own and the limit is written on
    the independent one, by hand and visibly.  rietx cannot copy that — its
    limits are schema physics that go on existing after a parameter is tied —
    so it derives what TOPAS has the user write, and reports it: a source held
    at a window it did not declare comes back through ``bound_findings`` as
    ``BOUND_HIT`` like any other bound the stage imposed.
    """
    a, b = lo - offset_hi, hi - offset_lo
    a, b = a / coeff, b / coeff
    return (a, b) if coeff > 0.0 else (b, a)


class ParameterTable:
    """The tree-to-flat-θ machinery behind a fit — internal, not the agent surface.

    A caller wanting numbers out wants ``Refinement.parameters()`` instead:
    this table's own :meth:`decode` returns a plain dict, by design (no
    pydantic in the hot loop), and it holds only free/tied entries, unlike the
    public surface, which also lists held rows and why.
    """

    def __init__(self, structure: Structure, instrument: Instrument, *,
                 joint: bool = False):
        #: ``True`` when this table is one histogram of a joint fit, so the
        #: wavelength count is somebody else's to make —
        #: :class:`~rietx.params.multi.MultiParameterTable`, the only object
        #: that can see the whole set (:func:`check_wavelength_freedom`).
        #: ``False`` (the default) is a single-histogram fit, where a free
        #: wavelength is refused here, in ``__init__``, like every other
        #: symmetry-of-the-problem refusal.
        self._joint = joint
        self.entries: list[Entry] = []
        #: phase base path → the Stephens DOF vector of the *unit* isotropic
        #: limit (1 ppm), kept so :meth:`seed_stephens` can put a freed block
        #: on the isotropic ray without rebuilding the symmetry basis
        self._strain_unit: dict[str, np.ndarray] = {}
        #: phases whose cells take the default window this stage, or None for
        #: "no claim made" — see :meth:`freeze_cell_windows`
        self._cell_window_phases: set[int] | None = None
        #: the stage's strain cap, or ``None`` for "no claim made" —
        #: see :meth:`freeze_strain_cap`
        self._strain_cap: float | None = None
        #: the stage's size cap (a width, deg 2θ), or ``None`` for "no claim
        #: made" — see :meth:`freeze_size_cap`
        self._size_cap: float | None = None
        #: path → a fixed positive factor between this table's *physical* value
        #: and the number the free column carries — see :meth:`apply_value_scale`.
        #: Empty for every single-histogram table, which is why an unscaled
        #: table's arithmetic is untouched: the rebuild writes the literal 1.0
        #: it always wrote, and ``x0``/``bounds`` skip the lookup's branch.
        self._value_scale: dict[str, float] = {}
        self._collect(structure, instrument)
        self._rebuild()

    # -- collection ----------------------------------------------------
    def _add(self, path: str, p: Parameter, *, force_fixed: bool = False,
             tie: AffineTie | None = None) -> None:
        self.entries.append(Entry(
            path=path, value=p.value, vary=p.vary and not force_fixed and tie is None,
            lo=p.min, hi=p.max, transform=p.transform, tie=tie,
            locked=force_fixed,
        ))

    def _collect(self, structure: Structure, instrument: Instrument) -> None:
        for ip, phase in enumerate(structure.phases):
            sg = get_spacegroup(phase.space_group)
            # The cell ties come from the *setting*, not from the crystal system
            # alone: a c-unique monoclinic symbol fixes β, not γ, and an R group
            # on rhombohedral axes ties c←a and α=β=γ rather than leaving c free
            # (WP-1036, crystallography.symmetry.CellConstraints).
            constraints = cell_constraints(sg)
            check_cell_angles(sg, {name: getattr(phase.cell, name).value
                                   for name in ("alpha", "beta", "gamma")})
            base = f"phases.{ip}"
            for name in _CELL_NAMES:
                p: Parameter = getattr(phase.cell, name)
                if name in constraints.ties:
                    self._add(f"{base}.cell.{name}", p, tie=AffineTie.identity(
                        f"{base}.cell.{constraints.ties[name]}"))
                elif name in constraints.fixed_angles:
                    self._add(f"{base}.cell.{name}", p, force_fixed=True)
                else:
                    self._add(f"{base}.cell.{name}", p)
            self._add(f"{base}.scale", phase.scale)
            self._add(f"{base}.extinction", phase.extinction)
            if phase.preferred_orientation is not None:
                self._add(f"{base}.preferred_orientation.r",
                          phase.preferred_orientation.r)
            self._add(f"{base}.lor_size", phase.lor_size)
            # a Stephens block owns the tanθ Lorentzian channel outright: its
            # isotropic direction is the same column, so lor_strain is locked
            # (the Atom.aniso ⇒ biso bargain, one level up)
            self._add(f"{base}.lor_strain", phase.lor_strain,
                      force_fixed=phase.microstrain is not None)
            self._add(f"{base}.gauss_size", phase.gauss_size)
            self._add(f"{base}.gauss_strain", phase.gauss_strain)
            self._collect_microstrain(base, sg, phase)
            for j, atom in enumerate(phase.atoms):
                self._collect_atom_coords(f"{base}.atoms.{j}", sg, atom)
                self._add(f"{base}.atoms.{j}.occ", atom.occ)
                self._collect_atom_adps(f"{base}.atoms.{j}", sg, atom)

        self._add("instrument.zero_shift", instrument.zero_shift)
        self._collect_instrument(instrument)

    def _collect_microstrain(self, base: str, sg, phase) -> None:
        """Stephens S_HKL enter θ through Laue-symmetry-allowed patterns.

        The rank-4 twin of :meth:`_collect_atom_adps`: the phase contributes
        ``phases.i.microstrain.dof.k`` parameters, one per allowed pattern
        (``crystallography.stephens``), and the fifteen components become
        affine rows S = Σₖ Bₖ·θₖ.  **Absolute**, like the ADP patterns — the
        basis spans the whole allowed subspace, so writing S this way enforces
        the lattice symmetry exactly and coefficients outside it are an error
        rather than something to symmetrise.  Components the symmetry forces to
        zero are locked; the DOFs are unbounded, because σ²(M) ≥ 0 couples all
        fifteen and cannot be a box (positivity is a guard — the same argument
        that keeps the ADP cone out of ``bounds``).

        An all-zero block is the exact no-broadening identity, so it is allowed
        to *exist*; refining from there is not.  Λ ∝ √Σ has unbounded slope at
        the origin, so the first Jacobian column would be enormous and TRF's
        first step garbage — the failure inverts the softplus-at-zero trap
        (dead gradient) into an exploding one, and neither is something to
        discover from a bad fit.  ``Stage(seed=…)`` cannot help: it lifts
        softplus entries only, and these are identity-transform.
        """
        block = phase.microstrain
        if block is None:
            return
        basis = strain_basis(rotation_matrices(sg))  # (n_free, 15)
        s0 = np.array(block.values(), dtype=np.float64)
        coef, *_ = np.linalg.lstsq(basis.T.astype(np.float64), s0, rcond=None)
        residual = basis.T @ coef - s0
        scale = max(float(np.abs(s0).max()), 1.0)
        if float(np.abs(residual).max()) > 1e-6 * scale:
            raise ValueError(
                f"{base}.microstrain: the coefficients {s0.tolist()} are not "
                f"compatible with the lattice symmetry, which allows only "
                f"{basis.tolist()} in {list(S_NAMES)}; the nearest allowed set "
                f"is {(basis.T @ coef).tolist()}")
        want_vary = any(getattr(block, n).vary for n in S_NAMES)
        if want_vary and not np.any(s0):
            raise ValueError(
                f"{base}.microstrain: every S_HKL is zero, which is the point "
                "where the √ of the width law has unbounded slope — refining "
                "from there gives a meaningless first step.  Start from the "
                "isotropic limit instead: "
                "StephensStrain.isotropic(microstrain_ppm, phase.cell)")
        dof_paths = [f"{base}.microstrain.dof.{k}" for k in range(len(basis))]
        for v, name in enumerate(S_NAMES):
            p: Parameter = getattr(block, name)
            terms = tuple((dof_paths[k], float(basis[k][v]))
                          for k in range(len(basis)) if basis[k][v] != 0)
            if terms:
                self._add(f"{base}.microstrain.{name}", p, tie=AffineTie(terms=terms))
            else:
                # symmetry forces this monomial to vanish, so it is locked *at
                # zero* rather than at whatever the caller passed: the residual
                # check above has already bounded that to roundoff (the
                # isotropic seed goes through a matrix inverse), and carrying
                # the noise forward would break the symmetry the basis exists
                # to enforce exactly
                self.entries.append(Entry(
                    path=f"{base}.microstrain.{name}", value=0.0, vary=False,
                    lo=p.min, hi=p.max, transform=p.transform, locked=True))
        for k, path in enumerate(dof_paths):
            self.entries.append(Entry(path=path, value=float(coef[k]), vary=want_vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))
        # S scales as microstrain², so one unit-ppm projection serves any seed
        unit, *_ = np.linalg.lstsq(
            basis.T.astype(np.float64),
            isotropic_coefficients(phase.cell.lengths_angles(), 1.0), rcond=None)
        self._strain_unit[base] = unit

    def _collect_atom_coords(self, base: str, sg, atom) -> None:
        """Coordinates enter θ through site-symmetry displacement DOFs.

        Each site contributes ``…dof.k`` parameters — one per site-symmetry-
        allowed direction (``crystallography.wyckoff``) — and x, y, z become
        affine rows x = x₀ + Σₖ Bₖ·θₖ anchored at the compile-time position.
        Fully fixed special positions contribute none (their coordinates are
        locked); ``vary=True`` on any coordinate of such a site is an error.
        A vary request on a constrained-but-free site frees *all* of the
        site's DOFs — per-axis intent does not map onto rows such as [1,1,0].
        DOFs are unbounded displacements; bounds declared on x/y/z do not
        constrain them.
        """
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        basis = coordinate_basis(stabilizer_rotations(sg, xyz))
        want_vary = any(getattr(atom, c).vary for c in ("x", "y", "z"))
        if len(basis) == 0 and want_vary:
            raise ValueError(
                f"{base} sits on a fully fixed special position; its site "
                "symmetry allows no positional freedom — set vary=False")
        dof_paths = [f"{base}.dof.{k}" for k in range(len(basis))]
        for c_idx, c in enumerate(("x", "y", "z")):
            p: Parameter = getattr(atom, c)
            terms = tuple((dof_paths[k], float(basis[k][c_idx]))
                          for k in range(len(basis)) if basis[k][c_idx] != 0)
            if terms:
                self._add(f"{base}.{c}", p, tie=AffineTie(terms=terms, const=p.value))
            else:
                self._add(f"{base}.{c}", p, force_fixed=True)
        for path in dof_paths:
            self.entries.append(Entry(path=path, value=0.0, vary=want_vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))

    def _collect_atom_adps(self, base: str, sg, atom) -> None:
        """Displacement parameters: ``biso``, or aniso U^ij through DOFs.

        An anisotropic site contributes ``…adp.k`` parameters — one per
        site-symmetry-allowed U^ij *pattern* (``crystallography.wyckoff``) —
        and the six components become affine rows U = Σₖ Bₖ·θₖ.  Unlike the
        coordinate DOFs these are **absolute**, not displacements from an
        anchor: the pattern basis spans the whole allowed subspace, so writing
        U that way enforces the site symmetry exactly rather than only
        preserving whatever asymmetry the starting values carried.  θ₀ is
        therefore the least-squares projection of the input tensor onto the
        basis, and an input that does not lie in it is an error, not something
        to silently symmetrise.

        Components the site symmetry forces to zero (empty rows) are locked;
        the DOFs are unbounded, so ``min``/``max`` on a component do not
        constrain them — positive-definiteness is a guard, not a box.
        ``biso`` is still collected (locked when aniso is present) so its
        path exists for globs and write-back either way.
        """
        if atom.aniso is None:
            self._add(f"{base}.biso", atom.biso)
            return
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        basis = adp_basis(stabilizer_rotations(sg, xyz))  # (n_free, 6)
        u0 = np.array(atom.aniso.values(), dtype=np.float64)
        coef, *_ = np.linalg.lstsq(basis.T.astype(np.float64), u0, rcond=None)
        residual = basis.T @ coef - u0
        scale = max(float(np.abs(u0).max()), 1e-6)
        if float(np.abs(residual).max()) > 1e-6 * scale:
            raise ValueError(
                f"{base}: the anisotropic tensor {u0.tolist()} is not "
                f"compatible with the site symmetry, which allows only "
                f"{basis.tolist()} in (U11, U22, U33, U12, U13, U23); the "
                f"nearest allowed tensor is {(basis.T @ coef).tolist()}")
        dof_paths = [f"{base}.adp.{k}" for k in range(len(basis))]
        want_vary = any(getattr(atom.aniso, n).vary for n in U_NAMES)
        for v, name in enumerate(U_NAMES):
            p: Parameter = getattr(atom.aniso, name)
            terms = tuple((dof_paths[k], float(basis[k][v]))
                          for k in range(len(basis)) if basis[k][v] != 0)
            if terms:
                self._add(f"{base}.{name}", p, tie=AffineTie(terms=terms))
            else:
                self._add(f"{base}.{name}", p, force_fixed=True)
        for k, path in enumerate(dof_paths):
            self.entries.append(Entry(path=path, value=float(coef[k]), vary=want_vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))
        self._add(f"{base}.biso", atom.biso, force_fixed=True)

    def _collect_instrument(self, instrument: Instrument) -> None:
        # K is a fact about the radiation, not about this instrument, wherever
        # the radiation pins it.  A neutron beam is not polarised the way the
        # Thomson cross-section polarises X-rays, so Lp collapses to the bare
        # Lorentz factor at K = 1 — and a *free* entry there is worse than a
        # dead column: Lp(2θ, K) does move the pattern, so the solver would buy
        # Rwp by refining a term whose value the physics already knows.
        # Force-fixed rather than merely unfree, the WP-1073 rule — a parameter
        # the forward branch cannot legitimately use must be locked, or
        # ``set_vary`` frees it and nothing objects.
        self._add("instrument.polarization", instrument.source.polarization,
                  force_fixed=instrument.source.kind != "xray_cw")
        for il, line in enumerate(instrument.source.lines):
            # line 0 defines the intensity scale: its weight is degenerate with
            # the phase scale factors, so it is always held fixed
            self._add(f"instrument.source.lines.{il}.weight", line.weight,
                      force_fixed=(il == 0))
        # The wavelength, and the mirror image of the weight rule above it.  A
        # line weight's scale lives inside this source, so **line 0** is the one
        # that must be held; a wavelength's scale lives in the *cell*, which may
        # be shared across histograms this table cannot see, so line 0 is the
        # one that may be *free* — and only when somebody else is counting.
        #
        # Two locks and one refusal, in the shape ``CAPILLARY_OFFSETS`` uses
        # just below.  Lines 1+ are force-fixed unconditionally: within one
        # source the lines' wavelength *ratio* is atomic physics (the NIST
        # column in ``schemas.instrument._KA_DOUBLETS`` is quoted for exactly
        # this reason, ~20 ppm), so a free secondary line is a second flat
        # direction beside the first — the WP-1073 rule that a parameter which
        # cannot legitimately move is force-fixed rather than merely unfree.  In
        # a single-histogram table *every* line is force-fixed, because there λ
        # is exactly degenerate with the cell whatever the data; that is what
        # lets ``ParameterRow.held_because`` tell the truth about it without a
        # fourth held-reason, and what stops a glob freeing it by accident.  And
        # a *declared* ``vary=True`` there is refused by name rather than
        # quietly swallowed, because it is a claim the caller made.
        wl_params = list(instrument.source.wavelength_parameters)
        # No single-histogram check here: ``_rebuild`` runs at the end of
        # ``__init__`` and at every stage boundary, and it is the only place
        # that sees both free sets at once.  Checking here as well would be a
        # second authority for one fact, and the weaker of the two — it cannot
        # see a cell freed by a later stage.
        for il, wl in enumerate(wl_params):
            # Line 0 is NOT force-fixed even in a single-histogram table.  A
            # free λ there is admissible whenever the *cell* is held — which is
            # what a certified standard is for — so "can never legitimately
            # move", which is what force_fixed asserts, would be false.  The
            # λ-versus-cell condition is dynamic (stages call ``set_vary``), so
            # it is enforced in ``_rebuild`` where the free set is known rather
            # than frozen here.  Line > 0 keeps it: a Kα2 wavelength is a
            # physical constant, not a calibration target.
            self._add(f"instrument.source.lines.{il}.wavelength", wl,
                      force_fixed=il > 0)
        geom = instrument.geometry
        for name in ("sample_displacement", "sample_transparency",
                     "axial_sl", "axial_hl"):
            self._add(f"instrument.geometry.{name}", getattr(geom, name),
                      force_fixed=(geom.kind != "bragg_brentano"
                                   and name.startswith("sample_")))
        for name in CAPILLARY_OFFSETS:
            offset = getattr(geom, name)
            # eq (4) divides by R.  Geometry's validator refuses a *stored*
            # free offset without one, but ``vary`` set after construction
            # re-runs no validator, and this is the last gate before a solve —
            # so refuse here too, naming the field rather than quietly holding
            # the parameter (a held aberration reads as "measured zero").
            usable = bool(geom.kind == "debye_scherrer"
                          and geom.goniometer_radius_mm)
            if offset.vary and not usable:
                raise ValueError(
                    f"instrument.geometry.{name} cannot vary without "
                    f"goniometer_radius_mm: eq (4) is "
                    f"Δ2θ = (−a·sin2θ + b·cos2θ)/R and R is unset")
            # force-fixed rather than merely unfree when R is missing, because
            # ``_position_shift_deg`` skips the term without one: a free entry
            # there would be a dead column — a parameter the solver moves and
            # the model does not read.
            self._add(f"instrument.geometry.{name}", offset,
                      force_fixed=not usable)
        # surface roughness is opt-in, so it is *skipped* when absent rather
        # than added locked: a table built from an instrument without the block
        # is byte-for-byte the pre-WP-0502 table.  No geometry gate needed —
        # Geometry's validator already refuses the block on non-flat specimens.
        for sub, cp in roughness_parameters(geom.surface_roughness):
            self._add(f"instrument.geometry.surface_roughness.{sub}", cp)
        for name in ("u", "v", "w", "x", "y"):
            self._add(f"instrument.profile.{name}", getattr(instrument.profile, name))
        for sub, cp in background_parameters(instrument.background):
            self._add(f"instrument.background.{sub}", cp)
        # Additive broad peaks: skipped when none is declared rather than added
        # locked, the surface-roughness idiom one loop up.  No gate — a peak
        # composes with every background model and every geometry, which is the
        # whole reason it lives beside ``background`` rather than inside its
        # union.
        for sub, cp in extra_component_parameters(instrument.extra_components):
            self._add(f"instrument.extra_components.{sub}", cp)

    # -- the affine constraint block -----------------------------------
    def _flatten(self, tie: AffineTie, _seen: tuple[str, ...] = ()
                 ) -> tuple[list[tuple[int, float]], float]:
        """Resolve a tie onto untied entries: chains collapse, cycles raise."""
        terms: list[tuple[int, float]] = []
        const = tie.const
        for path, coeff in tie.terms:
            if path in _seen:
                raise ValueError(f"cyclic parameter tie through {path!r}")
            i = self._paths.get(path)
            if i is None:
                raise ValueError(f"tie references unknown parameter {path!r}")
            src = self.entries[i]
            if src.tie is None:
                terms.append((i, coeff))
            else:
                sub_terms, sub_const = self._flatten(src.tie, _seen + (path,))
                terms.extend((j, coeff * c) for j, c in sub_terms)
                const += coeff * sub_const
        return terms, const

    def _rebuild(self) -> None:
        """Recompile p_phys = C·p_free + d from the current entries.

        Free entries get unit rows, held entries put their value in ``d``,
        tied entries scatter flattened coefficients into ``C`` (free
        sources) and ``d`` (held sources + constants).  Rebuilds happen
        only at stage boundaries (``set_vary`` / ``commit`` / ``set_tie``),
        never inside a least-squares run, so the map is a constant matmul
        while the optimiser looks at it.
        """
        self._paths = {e.path: i for i, e in enumerate(self.entries)}
        self._free_idx = [i for i, e in enumerate(self.entries) if e.vary and e.tie is None]
        col = {i: k for k, i in enumerate(self._free_idx)}
        n, m = len(self.entries), len(self._free_idx)
        c_rows: list[int] = []
        c_cols: list[int] = []
        c_vals: list[float] = []
        tied: list[tuple[int, list[tuple[int, float]]]] = []
        d = np.zeros(n, dtype=np.float64)
        for i, e in enumerate(self.entries):
            if e.tie is None:
                if i in col:
                    c_rows.append(i)
                    c_cols.append(col[i])
                    c_vals.append(self._value_scale.get(e.path, 1.0))
                else:
                    d[i] = e.value
            else:
                terms, const = self._flatten(e.tie, (e.path,))
                d[i] = const
                for j, coeff in terms:
                    if j in col:
                        c_rows.append(i)
                        c_cols.append(col[j])
                        c_vals.append(coeff)
                    else:
                        d[i] += coeff * self.entries[j].value
                tied.append((i, [(j, c) for j, c in terms
                                 if j in col and c != 0.0]))
        self._C = sparse.csr_matrix((c_vals, (c_rows, c_cols)), shape=(n, m))
        self._d = d
        self._tie_windows = self._derive_tie_windows(tied, d)

    def _derive_tie_windows(self, tied: list[tuple[int, list[tuple[int, float]]]],
                            d: np.ndarray) -> dict[int, tuple[float, float]]:
        """Each free source's window, intersected over every dependent it drives.

        The derivation and its prior art are :func:`tie_window`'s; this is the
        bookkeeping around it.  Two rules the arithmetic does not state.

        A dependent claiming nothing on either side constrains nothing, so an
        entry with two infinite bounds is skipped rather than contributing a
        ±inf window — measured on this tree, that is **every tie the package
        derives**: 52 of them across four real structures (68 with anisotropic
        ADPs), all single-term, and not one with a finite bound, because cell
        lengths, angles and fractional coordinates all carry the
        :class:`~rietx.schemas.common.Parameter` default of ±inf.  So this
        narrows a *user's* tie and provably nothing else, which is what made it
        safe to apply unconditionally rather than behind a freeze.

        Co-source ranges are read from the entries' own **declared** bounds and
        never from another window computed here, so the result does not depend
        on the order dependents are visited in.  Using the wider input keeps
        every window an outer box, which is the direction :func:`tie_window`
        needs.

        An empty intersection is **refused, not clipped**: two declarations that
        cannot both hold is the caller contradicting themselves, and this table
        has no diagnostics channel to say so in (the rule that puts a CIF's
        angle repair in the reader instead).
        """
        # each side carries the dependent that set it, because the fix for a
        # window is almost never on the parameter the window is *on*
        acc: dict[int, tuple[float, str, float, str]] = {}
        for i, free_terms in tied:
            e = self.entries[i]
            if not (math.isfinite(e.lo) or math.isfinite(e.hi)):
                continue
            spans = [(j, c, min(c * self.entries[j].lo, c * self.entries[j].hi),
                      max(c * self.entries[j].lo, c * self.entries[j].hi))
                     for j, c in free_terms]
            for j, coeff, _, _ in spans:
                off_lo = float(d[i]) + sum(s for k, _, s, _ in spans if k != j)
                off_hi = float(d[i]) + sum(s for k, _, _, s in spans if k != j)
                if math.isnan(off_lo) or math.isnan(off_hi):
                    continue          # ±inf cancelling: nothing is claimed
                lo, hi = tie_window(e.lo, e.hi, coeff, off_lo, off_hi)
                if math.isnan(lo) or math.isnan(hi):
                    continue          # …and again once the bound is subtracted
                w_lo, from_lo, w_hi, from_hi = acc.get(
                    j, (-math.inf, e.path, math.inf, e.path))
                if lo > w_lo:
                    w_lo, from_lo = lo, e.path
                if hi < w_hi:
                    w_hi, from_hi = hi, e.path
                acc[j] = (w_lo, from_lo, w_hi, from_hi)
        out: dict[int, tuple[float, float]] = {}
        for j, (lo, from_lo, hi, from_hi) in acc.items():
            e = self.entries[j]
            if max(lo, e.lo) > min(hi, e.hi):
                blame = from_lo if lo > e.lo else from_hi
                raise ValueError(
                    f"{blame!r} follows {e.path!r}, and staying inside its own "
                    f"bounds needs {e.path} in [{lo:g}, {hi:g}] — which cannot "
                    f"be reconciled with {e.path}'s own [{e.lo:g}, {e.hi:g}]. "
                    f"Widen one of the two, or change the tie's coefficient")
            # **Never hand the solver an x0 it has already left.**  A window
            # says where a source may *go*, and the value it is *at* is a
            # separate fact — one that ``commit`` can put an ulp the wrong side
            # of, since a stage that stops on a window writes its answer back
            # through ``decode`` and ``_rebuild`` recomputes the window from it.
            # Widening to admit the value costs an ulp there and needs no
            # tolerance to tune, where the alternative is ``least_squares``
            # refusing the *next* stage with "x0 is infeasible" about a
            # parameter nobody tied.
            #
            # It also decides what happens to a state that was inconsistent
            # before any window existed.  Those are caught earlier now — the
            # write-back in ``apply_to_models`` refuses at declaration, naming
            # the path, the value, the bound and the tie — but "earlier" is not
            # "always", and this is deliberately not the place to raise: the
            # refusal WP-1337 § #246 wants belongs in its own voice beside
            # ``tie()``'s other six, and reaching a DOF target's coordinates is
            # that WP's task 4.  The computation it needs is right here, on the
            # *flattened* ties; only the refusal is missing.
            v = e.value
            out[j] = (min(lo, v), max(hi, v))
        return out

    #: Paths whose freedom λ trades against.  A cell *angle* is included: a
    #: monoclinic β scales no length on its own, but the metric it enters is
    #: what d is computed from, so freeing it alongside λ is the same family.
    _CELL_SUFFIXES = ("a", "b", "c", "alpha", "beta", "gamma")

    def check_wavelength_against_cell(self) -> None:
        """Refuse a free λ beside a free cell.  Called once per **solve**.

        The condition is *dynamic* — a cumulative plan can free the cell in one
        stage and λ in a later one — so it cannot be frozen at construction,
        and ``force_fixed`` (which asserts a parameter can *never* legitimately
        move) is the wrong mechanism for it.

        **Why the solve entry and not** ``_rebuild``.  ``_rebuild`` sees every
        vary change, which makes it the tempting seam, but not every vary
        change is a request to fit: ``identifiability.exchangeability_scan``
        frees candidate parameters temporarily to measure whether the data can
        tell them apart, and *that* probe is exactly how a caller finds out λ
        and the cell are exchangeable.  Refusing it there would break the
        diagnostic that diagnoses this very degeneracy.  A raise belongs where
        an answer would otherwise be produced from a flat direction, which is
        the solve.

        Single-histogram only.  The joint case is ``MultiParameterTable``'s,
        where the rule is "exactly one held, at most N − 1 free" and the shared
        cell is the mechanism; that check runs there and this one must not
        second-guess it.
        """
        if getattr(self, "_joint", False):
            return
        free = {self.entries[i].path for i in self._free_idx}
        lam = sorted(p for p in free
                     if p.startswith("instrument.source.lines.")
                     and p.endswith(".wavelength"))
        if not lam:
            return
        cell = sorted(p for p in free
                      if ".cell." in p and p.rsplit(".", 1)[-1] in self._CELL_SUFFIXES)
        if cell:
            raise ValueError(
                f"{lam[0]} and {cell[0]} cannot both be free: d = λ/(2 sin θ) "
                "fixes only the product, so scaling λ and every reciprocal "
                "lattice length together leaves every computed position "
                "unchanged — an exactly flat direction no amount of data "
                "removes.  Hold the cell (what a certified standard is for, "
                "and how a wavelength is calibrated) or hold λ.  Across "
                "several histograms of one specimen sharing a cell the "
                "degeneracy breaks and N − 1 wavelengths are measurable: "
                "rietx.refine_multi")

    def constraint_block(self) -> tuple[sparse.csr_matrix, np.ndarray]:
        """The current (C, d) with rows in entry order, columns in θ order."""
        return self._C, self._d

    # -- table surgery (used by Wyckoff constraint wiring) -------------
    def add_parameter(self, path: str, value: float, *, vary: bool = False,
                      lo: float = -np.inf, hi: float = np.inf,
                      transform: str = "identity") -> None:
        """Append a synthetic parameter (e.g. a Wyckoff displacement DOF).

        Synthetic paths must not collide with existing entries; pick names
        outside the model tree, e.g. ``phases.0.atoms.2.dof.0``.
        """
        if path in self._paths:
            raise ValueError(f"parameter {path!r} already exists")
        self.entries.append(Entry(path=path, value=value, vary=vary,
                                  lo=lo, hi=hi, transform=transform))
        self._rebuild()

    def set_tie(self, path: str, tie: AffineTie | None) -> None:
        """(Re)declare an entry as an affine function of other entries.

        Tying forces ``vary=False`` (the entry leaves θ; its sources carry
        the freedom).  Locked entries cannot be retied.  ``None`` unties.
        """
        i = self._paths.get(path)
        if i is None:
            raise ValueError(f"unknown parameter {path!r}")
        e = self.entries[i]
        if e.locked:
            raise ValueError(f"cannot tie structurally locked parameter {path!r}")
        e.tie = tie
        if tie is not None:
            e.vary = False
        self._rebuild()

    def refresh_ties(self) -> None:
        """Recompute every tied entry's value from its sources.

        :meth:`commit` does this as a side effect of decoding θ, which is the
        only way values change *during* a refinement.  A direct edit of a source
        value — ``Refinement.set_values`` — has no θ to decode, and without this
        the dependents would keep the values they were collected with: setting
        ``a`` on a cubic phase would leave ``b`` and ``c`` behind, silently
        breaking the symmetry the tie exists to enforce.

        One pass suffices: :meth:`_flatten` resolves each tie onto *untied*
        entries, so no dependent is read before it is written.
        """
        self._rebuild()
        for e in self.entries:
            if e.tie is not None:
                terms, const = self._flatten(e.tie, (e.path,))
                e.value = const + sum(c * self.entries[j].value for j, c in terms)
        self._rebuild()  # held tied entries contribute to d through their values

    # -- vary control (used by the staged strategy) --------------------
    def set_vary(self, path_globs: list[str], vary: bool) -> list[str]:
        """Glob-match entry paths (fnmatch semantics on dot paths); returns hits.

        Tied and locked entries never match: symmetry-fixed cell angles and
        the line-0 emission weight cannot be freed even by a broad glob such
        as ``phases.*.cell.*``.
        """
        import fnmatch

        # A wavelength is freeable only while the cell is held, and that is a
        # *dynamic* fact, so it cannot be an ``Entry.locked`` flag.  Skipping it
        # by glob rather than raising is the same treatment a symmetry-fixed
        # cell angle gets, and for the reason this method's docstring gives: a
        # staged plan frees by glob, and turning a broad plan into an error
        # would be worse than declining one row of it.  A *declared*
        # ``vary=True`` is a claim rather than a broad sweep, and is refused
        # loudly instead — at the solve, by
        # :meth:`check_wavelength_against_cell`.
        lam_paths = self._wavelength_paths()
        hits = []
        for e in self.entries:
            if any(fnmatch.fnmatchcase(e.path, g) for g in path_globs):
                if e.tie is None and not e.locked:
                    # Asked per row rather than once before the loop.  Computed
                    # once, the contract was order-dependent: two calls freeing
                    # the cell then λ skipped λ, while ONE call carrying both
                    # globs froze the skip set before the cell was free and so
                    # freed both, deferring the refusal to the solve.  Nothing
                    # shipped hits it, and a contract that reads differently
                    # depending on how a caller batched its globs is not one.
                    if (vary and e.path in lam_paths
                            and not getattr(self, "_joint", False)
                            and self._cell_is_free()):
                        continue
                    e.vary = vary
                    hits.append(e.path)
        self._rebuild()
        return hits

    def _wavelength_paths(self) -> frozenset[str]:
        return frozenset(e.path for e in self.entries
                         if e.path.startswith("instrument.source.lines.")
                         and e.path.endswith(".wavelength"))

    def _cell_is_free(self) -> bool:
        """Any free cell parameter, read from the **entries**, not ``_free_idx``.

        ``_free_idx`` is rebuilt only at the end of ``set_vary``, so inside that
        loop it is one call stale — which made a single call carrying both a
        cell glob and a λ glob free both, because the cell had not been seen to
        move yet.  Reading ``e.vary`` sees the in-progress state and makes the
        decision order-independent — but only *given* that the build order puts
        every phase entry before every instrument entry in ``entries``.  The
        cell is entry 0 and λ sits among the instrument entries well after it
        (index 26 with a single line, 27/28 with a Kα doublet), so within one
        call the cell is always freed before λ is tested.  Flip that order and a
        single ``*`` glob would free both again;
        ``test_a_glob_skips_it_while_the_cell_is_free_but_not_when_held``'s
        ``WL not in hits`` assertion on the held-cell table goes red on the
        flip, which is where the dependence is pinned.
        """
        return any(e.vary and e.tie is None and ".cell." in e.path
                   and e.path.rsplit(".", 1)[-1] in self._CELL_SUFFIXES
                   for e in self.entries)

    def seed_softplus(self, paths: list[str], value: float) -> list[str]:
        """Lift softplus-bounded free params sitting below ``value`` up to it.

        A softplus coefficient at ~0 has an internal gradient ≈ 0 (dp/du =
        σ(u) → 0 as p → 0), so TRF cannot move it off the floor.  When a stage
        frees such a parameter this nudges it to a small positive seed so the
        first Jacobian has a live column.  Only softplus entries strictly
        below ``value`` are touched (already-lifted ones and other transforms
        are left alone); returns the paths actually seeded.

        **The seed is in column units, not this table's** (WP-1131): a scaled
        entry (:meth:`apply_value_scale`) is seeded to ``value`` times its
        scale, so the shared column lands on ``value`` in every histogram.
        Seeding the physical value instead would give the histograms
        different internal coordinates for one shared column, and the joint
        table's *identical values from each histogram* would quietly stop
        being true -- nothing raises, the last write simply wins.
        """
        seeded = []
        for path in paths:
            i = self._paths.get(path)
            if i is None:
                continue
            e = self.entries[i]
            target = value * self._value_scale.get(path, 1.0)
            if e.transform == "softplus" and e.value < target:
                e.value = target
                seeded.append(path)
        if seeded:
            self._rebuild()
        return seeded

    def seed_stephens(self, paths: list[str], microstrain: float) -> list[str]:
        """Put a freed but still all-zero Stephens block on the isotropic ray.

        The counterpart of :meth:`seed_softplus` for the anisotropic-strain
        DOFs, and needed for the opposite reason: they are identity-transform,
        so ``seed_softplus`` skips them, and their pathology at zero is an
        *exploding* rather than a dead gradient (Λ ∝ √Σ).  The seed is the
        isotropic limit — S = microstrain²·[M²], the one point of the allowed
        subspace that is guaranteed to give σ²(M) > 0 for every reflection.

        Only phases whose *whole* block is still zero are touched, so a
        deliberate starting model is never overwritten.  Returns the paths
        actually seeded.
        """
        if microstrain <= 0.0:
            return []
        wanted: dict[str, set[int]] = {}
        for path in paths:
            base, _, tail = path.rpartition(".microstrain.dof.")
            if base and tail.isdigit():
                wanted.setdefault(base, set()).add(int(tail))
        seeded: list[str] = []
        for base, _ in wanted.items():
            unit = self._strain_unit.get(base)
            if unit is None:
                continue
            dofs = [(k, self._paths[f"{base}.microstrain.dof.{k}"])
                    for k in range(len(unit))]
            if any(self.entries[i].value != 0.0 for _, i in dofs):
                continue
            for k, i in dofs:
                self.entries[i].value = float(microstrain) ** 2 * float(unit[k])
                seeded.append(self.entries[i].path)
        if seeded:
            self._rebuild()
        return seeded

    # -- optimiser interface -------------------------------------------
    @property
    def free_paths(self) -> list[str]:
        return [self.entries[i].path for i in self._free_idx]

    @property
    def moving_paths(self) -> list[str]:
        """Every path this table can move — the free entries *and* their ties.

        ``free_paths`` answers "which entries are columns of θ"; this answers
        "which physical values can change while θ moves", and the two differ by
        exactly the tied rows: a tie carries its coefficient on the free
        column it follows (p = C·p_free + d), so a tied entry has a nonzero row
        of C while a held one lives entirely in ``d``.

        A consumer freezing a *structural* decision on "this cannot change
        during the stage" — window sizing, or a correction gated at its off
        state — must ask this rather than ``free_paths``, or a user tie
        (:meth:`Refinement.tie`) silently invalidates the freeze.  Read in
        entry order, so the answer does not depend on how θ was assembled.
        """
        reach = np.asarray(abs(self._C).sum(axis=1)).ravel()
        return [e.path for i, e in enumerate(self.entries) if reach[i] > 0.0]

    def x0(self) -> np.ndarray:
        return np.array([to_internal(self._unscaled(self.entries[i]),
                                     self.entries[i].transform)
                         for i in self._free_idx], dtype=np.float64)

    def _unscaled(self, e: Entry) -> float:
        """``e.value`` in the units the free column carries (see
        :meth:`apply_value_scale`); identical to ``e.value`` unscaled."""
        s = self._value_scale.get(e.path)
        return e.value if s is None else e.value / s

    def freeze_cell_windows(self, phases: set[int] | None) -> None:
        """Declare which phases' cells get the default window this stage.

        Frozen at stage compile like every other per-stage decision, and
        ``None`` means **no claim made** and windows nothing — the
        ``moving_paths`` convention, where an empty set is the claim that
        nothing needs one.  Held on the table rather than passed to
        :meth:`bounds` so that every reader agrees: ``run_least_squares`` solves
        against these bounds and ``staged.check_guards`` calls ``bounds()``
        again afterwards to decide ``at_bounds``, and a window the solver used
        but the guard did not see would be a bound hit nothing could report.
        """
        self._cell_window_phases = phases

    def freeze_strain_cap(self, cap: float | None) -> None:
        """Declare the sample-strain cap (a width, deg 2θ) for this stage.

        ``None`` means **no claim made** and caps nothing — the
        ``freeze_cell_windows`` convention.  The number comes from the fitted
        2θ range (:func:`strain_cap`), which is a property of the *data*, so it
        is frozen where every other per-stage decision is and held on the table
        for the same reason cell windows are: ``run_least_squares`` solves
        against these bounds and ``staged.check_guards`` calls ``bounds()``
        again afterwards to decide ``at_bounds``, and a cap the solver used but
        the guard did not see would be a bound hit nothing could report.
        """
        self._strain_cap = cap

    def freeze_size_cap(self, cap: float | None) -> None:
        """Declare the sample-size cap (a width, deg 2θ) for this stage.

        ``None`` means **no claim made** and caps nothing — the
        ``freeze_cell_windows``/``freeze_strain_cap`` convention.  The width
        comes from :func:`size_cap` (the fitted 2θ range and the pattern's
        wavelength, both properties of the *data*), and is held on the table
        for the same reason the strain cap is: the solver used it and
        ``staged.check_guards`` must see the same bound to report ``BOUND_HIT``.
        """
        self._size_cap = cap

    def apply_value_scale(self, scale: dict[str, float]) -> None:
        """Declare a fixed factor between a path's physical value and its column.

        For every ``path: s`` here this table's physical value is ``s`` times
        what the free column carries — :meth:`decode` multiplies (the factor is
        that path's row of C), :meth:`x0` divides, :meth:`bounds` divides the
        physical window, and an esd comes back multiplied because it goes
        through the same C.  The derivative chain needs no edit at all:
        ``_peak_chain_column`` finite-differences θ *through* :meth:`decode`, so
        an analytic column picks the factor up exactly where the whole-model FD
        column does, and the two cannot disagree about it.

        **What it is for** (WP-1131).  A joint fit shares a column between
        histograms by giving them the same internal coordinate, which is right
        only for a quantity that is the same number in every histogram.  A
        crystallite-size coefficient is not: it is (180/π)·K·λ/L, so one
        specimen needs coefficients in the ratio of the wavelengths
        (:func:`~rietx.model.profiles.caglioti.apparent_size_from_size_coefficient`).
        :class:`~rietx.params.multi.MultiParameterTable` therefore hands each
        histogram the factor λ_h/λ_ref, and the shared column becomes the
        coefficient at λ_ref — one specimen, one number, with each histogram's
        structure copy still carrying the coefficient *it* needs.

        Three rules, enforced rather than commented:

        * a factor is **finite and positive** — it divides;
        * a **tied** path may not be scaled, and a scaled path may not be a
          tie's source: a tie's coefficients are written against physical
          values, so neither the row nor its sources would still mean what the
          tie says.  Nothing in the package ties a size coefficient, so this is
          a refusal a caller has to go looking for;
        * an **unknown** path is a caller's typo, not a silent no-op.

        ``{}`` (or a map of exact ``1.0``\\ s) restores the unscaled table bit
        for bit, and no single-histogram fit ever sets one.
        """
        cleaned: dict[str, float] = {}
        for path, factor in scale.items():
            if path not in self._paths:
                raise KeyError(f"no such parameter: {path!r}")
            if not (factor > 0.0 and math.isfinite(factor)):
                raise ValueError(
                    f"value scale for {path!r} must be finite and positive, "
                    f"got {factor!r}")
            e = self.entries[self._paths[path]]
            if e.tie is not None:
                raise ValueError(
                    f"{path!r} is tied and cannot carry a value scale; a tie's "
                    "coefficients are written against physical values")
            if factor != 1.0:
                cleaned[path] = float(factor)
        if cleaned:
            for e in self.entries:
                if e.tie is None:
                    continue
                for src, _ in e.tie.terms:
                    if src in cleaned:
                        raise ValueError(
                            f"{e.path!r} is tied to {src!r}, which carries a "
                            "value scale; a tie's sources must be unscaled")
        self._value_scale = cleaned
        self._rebuild()

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Internal-space bounds for the free vector, in ``free_paths`` order.

        This is where :func:`cell_window`, :func:`strain_cap_hi`,
        :func:`size_cap_hi` and :func:`tie_window` are applied, rather than on
        the :class:`Entry`, and the distinction is the point: all four are
        **solver** bounds for the stage about to run, not facts about the
        stored parameter.  Putting any of them on the entry would surface it
        through ``ParameterRow`` and the ``.rxt`` document, both of which tell a
        reader that bounds come from the schema — and there it would read as a
        claim the caller never made.
        ``bound_findings`` is fed from here, so a cell that reaches its window,
        a strain/size term held at its cap, or a tie source held where its
        dependent's own limits put it (:func:`tie_window`) is still reported.

        **They do not commute, and a new one goes last.**  :func:`cell_window`
        reads an *infinite* side as the side nobody claimed and applies its
        runaway default only there, so anything that makes a side finite ahead
        of it passes as a claim the caller never made and disarms the guard —
        measured, an unsupported phase's cell came back at a tied dependent's
        [0, 100] instead of [3.89877, 4.41443].  Each of the four only ever
        narrows, so appending a fifth is always safe and inserting one is not
        (WP-1119).
        """
        windowed = getattr(self, "_cell_window_phases", None)
        cap = getattr(self, "_strain_cap", None)
        size_cap_width = getattr(self, "_size_cap", None)
        lo, hi = [], []
        for i in self._free_idx:
            e = self.entries[i]
            e_lo, e_hi = e.lo, e.hi
            if windowed:
                cell_name = _cell_parameter_name(e.path, phases=windowed)
                if cell_name is not None:
                    e_lo, e_hi = cell_window(cell_name, e.value, e_lo, e_hi,
                                             path=e.path)
            if cap is not None:
                strain_name = _strain_parameter_name(e.path)
                if strain_name is not None:
                    e_hi = strain_cap_hi(strain_name, e.value, e_hi, cap)
            if size_cap_width is not None:
                size_name = _size_parameter_name(e.path)
                if size_name is not None:
                    e_hi = size_cap_hi(size_name, e.value, e_hi, size_cap_width)
            tied_window = self._tie_windows.get(i)
            if tied_window is not None:
                # **last of the four, and the order is load-bearing.**
                # ``cell_window`` branches on whether a side is infinite — an
                # infinite one being the side nobody claimed — so a tie window
                # applied ahead of it would hand it a finite bound the caller
                # never wrote and suppress the runaway guard it exists to be.
                # Narrowing afterwards cannot: every one of the three only ever
                # narrows, so intersecting last is the tightest of all four and
                # leaves each of their decisions reading the stored bounds.
                e_lo, e_hi = max(e_lo, tied_window[0]), min(e_hi, tied_window[1])
            scale = self._value_scale.get(e.path)
            if scale is not None:
                # every bound above is a *physical* limit on this table's own
                # value; the column carries value/scale, so the window it sees
                # is that limit divided.  Applied here rather than in each
                # branch, so a new bound kind inherits it.
                e_lo, e_hi = e_lo / scale, e_hi / scale
            low, high = internal_bounds(e_lo, e_hi, e.transform)
            lo.append(low)
            hi.append(high)
        return np.asarray(lo), np.asarray(hi)

    def decode(self, theta: np.ndarray) -> dict[str, float]:
        """Internal free vector → full physical value dict, via C·p_free + d."""
        p_free = np.array([to_physical(float(t), self.entries[i].transform)
                           for t, i in zip(theta, self._free_idx, strict=True)],
                          dtype=np.float64)
        p = self._C @ p_free + self._d if len(p_free) else self._d
        return {e.path: float(p[i]) for i, e in enumerate(self.entries)}

    def commit(self, theta: np.ndarray) -> None:
        """Write refined values back into the table (used between stages)."""
        values = self.decode(theta)
        for e in self.entries:
            e.value = values[e.path]
        self._rebuild()  # held-source contributions to d follow the new values

    def stderr_physical(self, theta: np.ndarray, stderr_internal: np.ndarray,
                        correlation: np.ndarray | None = None) -> dict[str, float]:
        """Physical esds for every free or tied parameter.

        σ²_phys = diag(C · Cov_free · Cᵀ), where Cov_free is the covariance
        of the *physical* free parameters: the internal esds chain-ruled
        through the transforms, correlated by ``correlation`` when given
        (diagonal otherwise — the pre-v0.3 behaviour).  Identity ties
        thereby report exactly the source esd; general rows get full linear
        propagation including cross terms.  Held parameters are omitted.

        **A row drawing on a column that measured nothing is omitted too**, so
        the caller's ``.get(path)`` gives ``None`` (WP-1110 item 14).  Such a
        column comes back from the covariance solve with infinite variance, and
        WP-1072's rule is that a derived quantity which cannot be measured is
        *absent* rather than zero — this is that rule one rank down, and it
        reaches the tied rows as well, since a tie whose source measured
        nothing measured nothing.
        """
        if correlation is None:
            # stays on the diagonal *vector*: this branch is the cheap one, and
            # a Pawley table's dense n×n would be tens of MB for a number that
            # never leaves the diagonal
            s = self._sigma_free_measured(theta, stderr_internal)
            var = np.asarray(self._C.multiply(self._C) @ (s * s)).ravel()
        else:
            cov = self._cov_free(theta, stderr_internal, correlation)
            var = np.asarray(self._C.multiply(self._C @ cov).sum(axis=1)).ravel()
        var = np.maximum(var, 0.0)
        touched = np.diff(self._C.indptr) > 0  # rows with any free source
        blind = self.unmeasured_rows(theta, stderr_internal)
        return {e.path: float(np.sqrt(var[i]))
                for i, e in enumerate(self.entries) if touched[i] and not blind[i]}

    def _phys_sigma_free(self, theta: np.ndarray, stderr_internal: np.ndarray
                         ) -> np.ndarray:
        """Chain-ruled physical esd of each free parameter (θ-column order)."""
        return np.array(
            [abs(dphys_dinternal(float(t), self.entries[i].transform)) * float(sd)
             for t, sd, i in zip(theta, stderr_internal, self._free_idx, strict=True)],
            dtype=np.float64)

    def _cov_free(self, theta: np.ndarray, stderr_internal: np.ndarray,
                  correlation: np.ndarray | None) -> np.ndarray:
        """Covariance of the *physical* free parameters (Cov_free).

        Diagonal from the chain-ruled esds; off-diagonal from ``correlation``
        when given.  This is the construction :meth:`stderr_physical` uses —
        it calls this method rather than repeating it — so any block extracted
        from it carries the same Bérar-Lelann conditioning as the reported
        per-parameter esds.

        **A column the data carries no gradient in is left out of the matrix,
        not written into it** (WP-1110 item 14).
        :func:`~rietx.optimize.statistics.normal_covariance` reports such a
        direction as infinite variance, which is the true value and an
        unusable one to propagate with: every product against a zero
        coefficient — an off-diagonal correlation of exactly 0, a ``C`` row
        that does not use the column — is ``0 × inf``, a NaN, and one NaN in
        ``Cov_free`` reaches every row of ``C @ Cov_free`` that shares any
        source with it.  A rutile geometry table lost all six Ti-O bond esds
        that way while the offender was ``instrument.profile.y``, a parameter
        no bond depends on.

        So the infinite entries are zeroed here and reported through
        :meth:`unmeasured_free`, which names the columns.  A consumer marks the
        rows that *use* one absent and propagates the rest exactly — a bond
        length is not made unmeasurable by an unrelated profile term, and it is
        made unmeasurable by a coordinate that measured nothing.
        """
        s = self._sigma_free_measured(theta, stderr_internal)
        if correlation is None:
            return np.diag(s * s)
        return np.asarray(correlation, dtype=np.float64) * np.outer(s, s)

    def _sigma_free_measured(self, theta: np.ndarray, stderr_internal: np.ndarray
                             ) -> np.ndarray:
        """:meth:`_phys_sigma_free` with the unmeasured columns zeroed.

        The one place the infinities leave the arithmetic, so no consumer can
        forget: :meth:`unmeasured_free` is where they are *reported*.
        """
        s = self._phys_sigma_free(theta, stderr_internal)
        return np.where(np.isfinite(s), s, 0.0)

    def unmeasured_free(self, theta: np.ndarray, stderr_internal: np.ndarray
                        ) -> np.ndarray:
        """Boolean over the free columns: which of them measured nothing.

        A free column with no gradient anywhere in the residual comes back from
        the covariance solve with infinite variance (WP-1110 item 14).  This is
        the mask of those, in θ-column order, so a caller propagating through
        ``C`` can tell "no free source" — the all-zero ``C`` row WP-1072
        already reports as ``None`` — from "a free source that measured
        nothing", which needs the same answer for the same reason.
        """
        return ~np.isfinite(self._phys_sigma_free(theta, stderr_internal))

    def unmeasured_rows(self, theta: np.ndarray, stderr_internal: np.ndarray,
                        rows: np.ndarray | None = None) -> np.ndarray:
        """Boolean over ``C``'s rows (or ``rows`` of it): which are unmeasured.

        A row is unmeasured when it draws on any column
        :meth:`unmeasured_free` names — the propagated variance would be
        infinite, and an infinite esd is the absent one, not a large one.
        """
        bad = self.unmeasured_free(theta, stderr_internal)
        if not bad.any():
            n = self._C.shape[0] if rows is None else len(rows)
            return np.zeros(n, dtype=bool)
        c = self._C if rows is None else self._C[rows, :]
        return np.asarray(abs(c) @ bad.astype(np.float64)).ravel() > 0.0

    def physical_covariance(self, theta: np.ndarray, stderr_internal: np.ndarray,
                            correlation: np.ndarray | None,
                            paths: list[str]) -> np.ndarray:
        """Physical covariance sub-block for ``paths`` (free or tied entries).

        Generalises :meth:`stderr_physical` (which returns only the diagonal)
        to the full block ``Cov = C_rows · Cov_free · C_rowsᵀ``, so callers can
        propagate correlated functions of several parameters — e.g. QPA weight
        fractions from the phase scales.  A parameter that was never freed has
        an all-zero ``C`` row, hence a zero covariance row/column (no
        uncertainty), which the caller handles naturally.
        """
        rows = [self._paths[p] for p in paths]
        if not self._free_idx:
            return np.zeros((len(paths), len(paths)), dtype=np.float64)
        cov_free = self._cov_free(theta, stderr_internal, correlation)
        c_rows = self._C[rows, :].toarray()
        return c_rows @ cov_free @ c_rows.T

    def apply_to_models(self, structure: Structure, instrument: Instrument,
                        stderr: dict[str, float] | None = None) -> None:
        """Write current table values back into (copies of) the pydantic models.

        With ``stderr`` (a path → esd map, e.g. from
        :meth:`stderr_physical`) every parameter touched here also gets its
        ``stderr`` set — to ``None`` where the map has no entry, so a stale
        esd from an earlier stage can never survive.  That is what lets the
        CIF exporter write standard uncertainties.
        """
        values = {e.path: e.value for e in self.entries}
        #: Every (parameter, path) the walk below reaches, written only once the
        #: walk is complete.  **The write is all-or-nothing**: the bound refusal
        #: under ``_write`` raises part-way through a tree of hundreds of
        #: parameters, and assigning as we go left ``structure`` holding some of
        #: the stage's answer and some of the previous one — a model nothing
        #: reports as damaged.  Assignment order is unchanged, and no parent
        #: model is revalidated by a write to a ``Parameter``, so deferring the
        #: writes cannot change what any of them sees.
        pending: list[tuple[Parameter, str]] = []

        def put(p: Parameter, path: str) -> None:
            pending.append((p, path))

        def _refuse(path: str, value: float, exc: Exception | None = None):
            # A bound broken *here* is one the solver never saw: the box
            # covers free columns, and this is where a tied value first
            # meets the schema.  :func:`tie_window` closes the single-source
            # case exactly, so what survives is a multi-source tie's
            # infeasible corner — rare, and previously arriving as a bare
            # pydantic error naming no path, no phase and no tie, *after*
            # the solve.  Naming all three is the least a caller needs to
            # know which of their declarations to widen.
            # ``ValueError`` rather than re-raising: pydantic's own
            # ValidationError *is* a ValueError, so nothing catching the
            # broad type notices, and nothing in the package catches the
            # narrow one around this call.
            entry = self.entries[self._paths[path]]
            tie = (f"; it follows {_tie_text(entry.tie)}"
                   if entry.tie is not None else "")
            raise ValueError(
                f"writing {path}={value:g} back to the model breaks "
                f"its own bounds [{entry.lo:g}, {entry.hi:g}]{tie}"
            ) from exc

        def _write(p: Parameter, path: str) -> None:
            try:
                p.value = values[path]
            except ValidationError as exc:
                _refuse(path, values[path], exc)
            if stderr is not None:
                p.stderr = stderr.get(path)

        for ip, phase in enumerate(structure.phases):
            base = f"phases.{ip}"
            for name in ("a", "b", "c", "alpha", "beta", "gamma"):
                put(getattr(phase.cell, name), f"{base}.cell.{name}")
            put(phase.scale, f"{base}.scale")
            put(phase.extinction, f"{base}.extinction")
            if phase.preferred_orientation is not None:
                put(phase.preferred_orientation.r, f"{base}.preferred_orientation.r")
            put(phase.lor_size, f"{base}.lor_size")
            put(phase.lor_strain, f"{base}.lor_strain")
            put(phase.gauss_size, f"{base}.gauss_size")
            put(phase.gauss_strain, f"{base}.gauss_strain")
            if phase.microstrain is not None:
                for name in S_NAMES:
                    put(getattr(phase.microstrain, name), f"{base}.microstrain.{name}")
            for j, atom in enumerate(phase.atoms):
                # coordinates too — without this, refined positions vanish at
                # the next stage's recompile (models feed compile_phase_sites)
                for name in ("x", "y", "z", "occ", "biso"):
                    put(getattr(atom, name), f"{base}.atoms.{j}.{name}")
                if atom.aniso is not None:
                    for name in U_NAMES:
                        put(getattr(atom.aniso, name), f"{base}.atoms.{j}.{name}")
        put(instrument.zero_shift, "instrument.zero_shift")
        put(instrument.source.polarization, "instrument.polarization")
        for il, line in enumerate(instrument.source.lines):
            put(line.weight, f"instrument.source.lines.{il}.weight")
        # …and the wavelength through ``wavelength_parameters``, never through
        # ``lines``: a neutron source's ``lines`` is a *property* that builds a
        # fresh EmissionLine per access, so a write there lands on a throwaway
        # and the refined λ is silently lost at the next recompile — exactly the
        # half-wired-parameter failure this file's docstring warns about.
        for il, wl in enumerate(instrument.source.wavelength_parameters):
            put(wl, f"instrument.source.lines.{il}.wavelength")
        for name in ("sample_displacement", "sample_transparency",
                     "axial_sl", "axial_hl", *CAPILLARY_OFFSETS):
            put(getattr(instrument.geometry, name), f"instrument.geometry.{name}")
        for sub, cp in roughness_parameters(instrument.geometry.surface_roughness):
            put(cp, f"instrument.geometry.surface_roughness.{sub}")
        for name in ("u", "v", "w", "x", "y"):
            put(getattr(instrument.profile, name), f"instrument.profile.{name}")
        for sub, cp in background_parameters(instrument.background):
            put(cp, f"instrument.background.{sub}")
        # the other half of the pair the helper exists for (see
        # extra_component_parameters): registered in _collect_instrument and
        # written back here, or a refined hump silently reverts at the next
        # stage's recompile
        for sub, cp in extra_component_parameters(instrument.extra_components):
            put(cp, f"instrument.extra_components.{sub}")
        # the walk is over.  Check every value against the schema *before*
        # assigning any of them, so the refusal below leaves the models exactly
        # as it found them; the assignment pass keeps the guard as a backstop
        # for anything the check does not model.
        for p, path in pending:
            v = values[path]
            if not (p.min <= v <= p.max):
                _refuse(path, v)
        for p, path in pending:
            _write(p, path)
