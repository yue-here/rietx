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
  and the full physical value dict consumed by the forward model;
* zero or more **derived blocks** (``params.derived``, WP-1804) applied after
  the affine matmul: closed-form nonlinear maps onto locked rows, a rigid
  body's atoms being the case they exist for.  "Constant during a run" is a
  property of the affine rows only; every reader that needs ∂p/∂θ takes
  :meth:`ParameterTable.local_jacobian`, and every reader of *which* rows a
  column reaches takes :meth:`ParameterTable.reach_block`.  Both are C itself
  on a table that declares no block.

The decode path is plain float/array arithmetic on a pre-built sparse
matrix — no pydantic objects are touched per iteration.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace

import numpy as np
from pydantic import ValidationError
from scipy import sparse

from ..crystallography.adp import U_NAMES
from ..crystallography.magnetic.moments import (
    canonical_dofs,
    dofs_from_moment,
    dofs_in_frame,
    moment_frame,
    moment_from_dofs,
    wrap_angle,
)
from ..crystallography.stephens import S_NAMES, isotropic_coefficients, strain_basis
from ..crystallography.symmetry import (
    cell_constraints,
    check_cell_angles,
    resolve_group,
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
from ..schemas.structure import MOMENT_COMPONENTS, Structure
from .derived import DerivedBlock
from .transforms import dphys_dinternal, internal_bounds, to_internal, to_physical

#: Dot-path suffix of a source line's wavelength row.  One authority for the
#: spelling, since three places test for it: the collector, the freedom check
#: below and the ``WAVELENGTH_CALIBRATION`` diagnostic in ``refine.py`` (shared
#: with the joint path in ``multi.py``).
WAVELENGTH_SUFFIX = ".wavelength"

#: The largest esd whose square is still a double (≈ 1.3e+154).  Past it a
#: physical esd is read as unmeasured, as an infinite one is (WP-1463,
#: ``ParameterTable._phys_sigma_free``).
_SIGMA_MAX = float(np.sqrt(np.finfo(np.float64).max))

#: How far a moment frame (orthonormal rows, entries of order one) may move
#: between stages before :meth:`ParameterTable.reframe_moments` rebuilds it
#: (or :meth:`ParameterTable.pull_moment_frames` takes a model's).
#: Above roundoff and far below anything a fit could see: a frame moved by
#: 1e-12 moves the moment by 1e-12 of its modulus.
_MOMENT_REFRAME_TOL = 1e-12


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
        if bkg.air_scatter is not None:  # absent is no term, not a zero one
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
    #: the caller declared this parameter does not move (WP-1435).  Written by
    #: ``Refinement._apply_holds`` from its own register on every build, for
    #: the reason a user tie is: a hold is not a property of the models, and
    #: nothing the table derives from a structure could rebuild it.
    #:
    #: Read by :meth:`set_vary` alongside ``locked``, which is the whole
    #: mechanism.  The two differ in who said so and in what can undo it: a
    #: locked entry is the space group's and no caller may free it, a held one
    #: is the caller's own and ``Refinement.unhold`` takes it back.
    held: bool = False


#: Path prefix of a caller's own named variable (WP-1119).  A variable is a
#: synthetic entry like a Wyckoff DOF, so it needs a namespace outside the model
#: tree; ``phases`` and ``instrument`` are that tree's only top-level segments,
#: so ``vars.`` cannot collide, and it is a plain dot-path so ``set_vary("vars.*")``
#: globs it like anything else.  Declared here because this module is where a
#: path means something, and read by ``Refinement`` and the tie verbs.
VAR_PREFIX = "vars."


def is_variable_path(path: str) -> bool:
    """Is ``path`` a caller's named variable rather than a model parameter?

    One predicate rather than a repeated ``startswith``, because three rules
    turn on it and they must not drift: a tied source is accepted only where
    this is true (a variable may follow other variables — TOPAS's ``prm B =
    2 A`` — while a tied *model* path keeps the refusal that steers a caller to
    what it follows); only a path answering true is written back to the
    variable register instead of into the pydantic models; and a freeze asking
    what a column *moves* drops these before deciding, because the forward
    model never reads one (``refine._only_moves``, WP-1342).

    All three are the same fact — a variable is not a model parameter — and it
    is a fact about the **namespace** rather than a guess from a name: the
    model tree's only top-level segments are ``phases`` and ``instrument``, so
    nothing it owns can answer true here.
    """
    return path.startswith(VAR_PREFIX)


#: ``fnmatch``'s metacharacters.  A ``set_vary``/``turn_on`` entry carrying
#: none of them is a *literal* path, and a literal is the one spelling that can
#: be wrong in a way a pattern cannot (WP-1414).
_GLOB_CHARS = frozenset("*?[")


def is_literal_path(glob: str) -> bool:
    """Does ``glob`` name exactly one path, rather than match a family?

    The distinction every "matched nothing" rule turns on (WP-1414).  A
    pattern that matches nothing is ordinary: the shipped plans free
    ``phases.*.microstrain.dof.*`` and ``instrument.extra_components.*`` on
    models with neither, and a rule firing there would fire on every healthy
    plan.  A literal names one parameter, so if the table has no such entry the
    caller is wrong — a typo, or a path renamed under them.  Also the test
    ``Refinement.set_vary`` applies before refusing a held path, so that the
    two cannot disagree about which spellings are claims.
    """
    return not any(ch in _GLOB_CHARS for ch in glob)


def retired_spelling(path: str) -> str | None:
    """``path`` in the current spelling, when it uses a name a release retired.

    ``None`` for a path this release spells as written.  The answer is
    :func:`rietx.schemas.migrate.migrate_document_text`'s, the one authority on
    renamed dot-paths, so there is no second list of retired names to drift
    from it: ``instrument.background_peaks.*`` comes back as
    ``instrument.extra_components.*`` (WP-1102).  A stored plan is migrated as
    it is read; a plan written in code reaches the table under the old name,
    and this is how a stage tells that miss from a healthy one.
    """
    from ..schemas.migrate import migrate_document_text

    current, moved = migrate_document_text(path)
    return current if moved else None


def unknown_paths_among(path_globs: Iterable[str], known: set[str]) -> list[str]:
    """The ``turn_on`` entries that name nothing in ``known`` and can be wrong.

    Two kinds, both the caller's mistake and never a healthy plan's miss
    (WP-1414): a literal no entry has (:func:`is_literal_path`), and a pattern
    under a retired spelling (:func:`retired_spelling`) that matches nothing.
    Any other pattern matching nothing stays out, because that is how the
    shipped plans reach a component a model may not declare.  A retired
    pattern that does match something (a ``vars.background_peaks`` the
    caller declared) is answered and stays out too.  Order kept, repeats
    dropped.  The one statement of the rule, for :class:`ParameterTable` and
    the joint table alike.
    """
    import fnmatch

    def unknown(g: str) -> bool:
        if is_literal_path(g):
            return g not in known
        return (retired_spelling(g) is not None
                and not any(fnmatch.fnmatchcase(p, g) for p in known))

    return [g for g in dict.fromkeys(path_globs) if unknown(g)]


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
#: ``refine.clamp_cell_runaway``, which applies this to every cell parameter
#: that is itself a free *column* regardless of ``phase_support``, after a
#: stage has solved and committed.  **"Free" is narrower than "moving" here**
#: (the ``moving_paths``-vs-``free_paths`` rule, root CLAUDE.md), and the gap
#: is not closed: a cell tied to a caller's free ``vars.X`` is a *moving*
#: path, not a *free* one, so it is never clamped directly — clamping the
#: driver would move every other value it also reaches, which is not this
#: function's decision to make.  Such an escape is named instead, never
#: silently passed through: see ``refine._vars_driven_cell_escapes`` and the
#: review of #385 finding 1.  ``phase_support`` (the screen behind
#: ``cell_window``'s own
#: window above, and ``refine._hold_unsupported_phases``, WP-1301) is a
#: per-phase test and cannot see a *joint* degeneracy: two free
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

    ``phases=None`` means *any* phase — asked only by ``refine``'s
    unconditional post-solve safety net (``clamp_cell_runaway`` and the
    helpers that name, word and withhold around it), which reads every cell
    path regardless of which phase it belongs to.
    (:meth:`ParameterTable.bounds` never passes ``None`` here: it calls this
    with ``phases=windowed``, the support-based window's own set from
    ``freeze_cell_windows``, which asks only of the phases that declared.)

    Read off the path rather than recorded on the :class:`Entry`, because the
    window is applied at the optimiser interface and the entries there arrive
    from :meth:`ParameterTable.bounds` (or the safety net above) with nothing
    but their paths to go on.
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
    :meth:`ParameterTable.freeze_cell_windows`, off the screen
    :meth:`~rietx.model.forward.CompiledModel.phase_support` at the stage
    start, where there is no Jacobian for the scale's significance — and that
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



def _magnetic_component_drawn(phase, instrument) -> bool:
    """Whether a histogram on ``instrument`` draws ``phase``'s magnetic term.

    :func:`rietx.model.forward.magnetic_wanted` is the one authority on that
    dispatch and this only asks it.  A source it refuses by name is refused
    again, by the same words, at compile — so here it reads as "not drawn"
    rather than raising from a table build.
    """
    from ..model.forward import magnetic_wanted

    try:
        return magnetic_wanted(phase, instrument.source)
    except ValueError:
        return False


#: A softplus entry at or below this value is on its floor (WP-1930).  The
#: transform clamps a stored 0 to 1e-12 (``transforms._SOFTPLUS_MIN``), and a
#: fit that ends on the floor leaves the value near there: 1e-12 on one
#: platform and 3e-11 on the other in issue #832's sweep.  This bar is 30× above
#: the larger.  At 1e-9 the softplus slope is 1e-9, so a row that far down
#: carries no gradient a solver can act on, and no width or coefficient that
#: small is a measurement.
SOFTPLUS_FLOOR_VALUE = 1e-9

#: The value a stage starts a freed softplus row at when the row sits on its
#: floor, keyed by the unit its :class:`Parameter` declares (WP-1930, #836).
#:
#: **Why a seed at all.**  At the floor the softplus slope is 1e-12, so the row's
#: Jacobian column is twelve orders below its neighbours.  A Gauss-Newton step
#: there predicts a change in cost below the cost's own rounding, so whether the
#: trust region ever lifts the row is decided by the last bits.  On LaB₆ + cBN a
#: 3e-14 relative change to one start value moved χ²_red from 9.69 to 12.48,
#: with ``instrument.profile.y`` left on its floor.  MINUIT's manual warns of
#: the same thing for any transformed parameter at its limit.
#:
#: **The sizes.**  A width in deg 2θ starts at 1e-3°, the extinction stage's
#: own seed.  A Gaussian variance in deg² starts at its square, so it adds the
#: same 1e-3° to the FWHM.  An extinction coefficient in µm² starts at 1e-3 too.
#: At 1e-3 the softplus slope is 1e-3, nine orders above the floor's, and a
#: seed that small is cheap to walk back where the data put the width at zero.
#: Measured on 11-BM LaB₆ + cBN, BT-1 neutron and lab Cu Kα brucite: every seed
#: from 1e-3° to 0.05° reached one χ² per fit, under rounding-level changes to
#: the start as well.  The larger seed saved a few iterations on the sharp
#: instrument (36-40 against 41-45).  It cost more elsewhere: at 0.05° nine
#: synthetic suites whose true width is zero ran out of iterations or moved,
#: and LaB₆ + cBN with its Gaussian free stopped at χ²_red 9.84 rather than
#: 9.66.  WP-1930's log has the tables.
#:
#: A row with any other unit has no natural size: a background hump's height
#: is in counts, and its scale is the data's.  It is left where it is and
#: reported (``SOFTPLUS_FREED_AT_FLOOR``).
#:
#: **A second reader.**  The finite-difference step of an identity width row
#: is sized by the same table (``optimize.least_squares._fd_typicals``,
#: WP-1936), so a new width unit belongs here for both reasons.
FLOOR_SEEDS: dict[str, float] = {"deg": 1e-3, "deg^2": 1e-3 ** 2, "um^2": 1e-3}


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
        #: displacement DOF path → the coordinate rows anchored on it, as
        #: ``(path, coefficient)`` pairs.  Built where the anchor is built
        #: (:meth:`_collect_atom_coords`) rather than read back off a name,
        #: because "this entry is a displacement from a stored value" is a
        #: fact about how the row was constructed and nothing in the row says
        #: it — the ADP and Stephens DOFs spell their paths the same way and
        #: are absolute.  :meth:`rebase_anchored_dofs` is the one consumer.
        self._anchored_dofs: dict[str, tuple[tuple[str, float], ...]] = {}
        #: the anchored DOF paths :meth:`rebase_anchored_dofs` has already
        #: taken out of their coordinates on *this* table.  The correction is
        #: a subtraction from a stored constant, so it is not idempotent and a
        #: second application walks the coordinate the other way — exactly the
        #: defect it exists to end, mirrored.
        self._rebased: set[str] = set()
        #: the anchored DOF paths :meth:`reanchor_dofs` has corrected on this
        #: table — a subtraction from a stored constant, guarded as above
        self._reanchored: set[str] = set()
        #: path → a fixed positive factor between this table's *physical* value
        #: and the number the free column carries — see :meth:`apply_value_scale`.
        #: Empty for every single-histogram table, which is why an unscaled
        #: table's arithmetic is untouched: the rebuild writes the literal 1.0
        #: it always wrote, and ``x0``/``bounds`` skip the lookup's branch.
        self._value_scale: dict[str, float] = {}
        #: path → the unit its :class:`Parameter` declared, for every entry
        #: :meth:`_add` built.  Read by :meth:`seed_floor` alone, which sizes a
        #: floor seed by unit; kept beside :class:`Entry` rather than in it,
        #: because ``Entry`` mirrors ``ParameterRow`` field for field.
        self._units: dict[str, str | None] = {}
        #: atom base path (``phases.0.atoms.2``) → the orthonormal frame of
        #: that site's allowed moment subspace, in crystal-axis rows.  Built
        #: here from the declared cell, rebuilt at every stage start by
        #: :meth:`reframe_moments` from the cell that stage starts from, and
        #: read by :meth:`_refresh_moment_components`.  The runners hand these
        #: to the forward model (:meth:`push_moment_frames`) rather than let each
        #: compile build its own, so there is exactly one frame per site per
        #: stage and the table is its authority (issue #598).
        self._moment_frames: dict[str, np.ndarray] = {}
        #: the nonlinear maps applied after the affine block, in order
        #: (WP-1804, ``params.derived``).  Empty for every table that declares
        #: no rigid body, and every reader below takes the affine path
        #: bit-for-bit when it is.
        self.derived: list[DerivedBlock] = []
        #: (body base path, body name, its block), in collection order
        #: (WP-1805): the write-back and the rigidity check walk this
        self._bodies: list[tuple[str, str, DerivedBlock]] = []
        #: body base path → its rotation DOF paths: the **anchored-rotation**
        #: kind (WP-1805).  An increment δω = E·θ composed into the body's
        #: R₀ and zeroed at every :meth:`commit`, so its value is a step
        #: within one stage and never a position.  Built where the anchor is
        #: (:meth:`_collect_body`), never read off a path's name, for
        #: ``_anchored_dofs``' reason; and never *in* ``_anchored_dofs``,
        #: whose subtraction rule is wrong for a rotation by O(δω²)
        #: (WP-1803's record), so nothing rebases one.
        self._anchored_rotations: dict[str, tuple[str, ...]] = {}
        #: body base path → its torsions' twist increments (WP-1808): the
        #: same anchored-rotation kind about one named axis each, composed
        #: into the torsion's ``angle`` and zeroed at every :meth:`commit`
        self._anchored_torsions: dict[str, tuple[str, ...]] = {}
        #: a body origin's displacement DOFs (they are in ``_anchored_dofs``
        #: too, being an atom-like site): with the rotations, the increments
        #: that restart at every build while the record moves, which is what
        #: :meth:`_refuse_body_increment_tie` refuses as a tie source
        self._body_origin_dofs: dict[str, tuple[str, ...]] = {}
        #: body base path → (q₀, R₀, E) as the last :meth:`commit` found them,
        #: so a stage that restores a collapsed phase to where it began can
        #: put the anchor back too (:meth:`restore_body_anchors`)
        self._precommit_anchor: dict[str, tuple] = {}
        #: body base path → φ₀ as the last :meth:`commit` found it (WP-1808)
        self._precommit_torsions: dict[str, np.ndarray] = {}
        self._collect(structure, instrument)
        self._rebuild()
        if self._bodies:
            # the stored atoms are checked against their bodies before the
            # blocks write them, so an edit of a body atom is refused rather
            # than silently undone; ``add_derived`` then validates each block
            # (locked outputs, declaration order, shapes) and writes its rows
            self._check_body_drift()
            for _, _, block in self._bodies:
                self.add_derived(block)

    # -- collection ----------------------------------------------------
    def _add(self, path: str, p: Parameter, *, force_fixed: bool = False,
             tie: AffineTie | None = None) -> None:
        self.entries.append(Entry(
            path=path, value=p.value, vary=p.vary and not force_fixed and tie is None,
            lo=p.min, hi=p.max, transform=p.transform, tie=tie,
            locked=force_fixed,
        ))
        self._units[path] = p.unit

    def _collect(self, structure: Structure, instrument: Instrument) -> None:
        for ip, phase in enumerate(structure.phases):
            sg = resolve_group(phase.space_group, phase.symmetry_operations)
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
            # **The magnetic pair exists only on a phase that has a magnetic
            # component to broaden** (WP-1343).  Registering them on every
            # phase would put two rows in every table in the package for a
            # term whose forward model is `None` there — the declared-name
            # trap — so a phase with no ``magnetic_symmetry`` carries neither
            # path at all and no stage can free what it does not have.  The
            # schema refuses a non-zero *value* there for the same reason,
            # which is the half a table cannot state.
            if phase.magnetic_symmetry is not None:
                # **Force-fixed where this histogram carries no magnetic
                # component**, the WP-1073 rule: on an X-ray source (or a
                # phase declaring no moment) the forward model never draws
                # the second family, so a free width would be a dead column —
                # and ``run_least_squares`` refuses one by name, which a plan
                # freeing ``phases.*.magnetic_lor_*`` would hit with advice
                # it cannot take.  Not in a joint table: there a neutron
                # histogram shares the entry and does see it.
                off = (not self._joint
                       and not _magnetic_component_drawn(phase, instrument))
                self._add(f"{base}.magnetic_lor_size", phase.magnetic_lor_size,
                          force_fixed=off)
                self._add(f"{base}.magnetic_lor_strain",
                          phase.magnetic_lor_strain, force_fixed=off)
            self._collect_microstrain(base, sg, phase)
            owner = {label: body.name for body in phase.rigid_bodies
                     for label in body.atoms}
            for j, atom in enumerate(phase.atoms):
                if atom.label in owner:
                    self._collect_body_atom_coords(f"{base}.atoms.{j}", atom,
                                                   owner[atom.label])
                else:
                    self._collect_atom_coords(f"{base}.atoms.{j}", sg, atom)
                self._add(f"{base}.atoms.{j}.occ", atom.occ)
                self._collect_atom_adps(f"{base}.atoms.{j}", sg, atom)
                self._collect_atom_moment(f"{base}.atoms.{j}", phase, atom)
            for b, body in enumerate(phase.rigid_bodies):
                self._collect_body(base, sg, phase, b, body)

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
                "symmetry allows no positional freedom — set vary=False "
                "(Refinement.fix_special_positions() does it for every such "
                "site)")
        dof_paths = [f"{base}.dof.{k}" for k in range(len(basis))]
        for c_idx, c in enumerate(("x", "y", "z")):
            p: Parameter = getattr(atom, c)
            terms = tuple((dof_paths[k], float(basis[k][c_idx]))
                          for k in range(len(basis)) if basis[k][c_idx] != 0)
            if terms:
                self._add(f"{base}.{c}", p, tie=AffineTie(terms=terms, const=p.value))
            else:
                self._add(f"{base}.{c}", p, force_fixed=True)
        for k, path in enumerate(dof_paths):
            self.entries.append(Entry(path=path, value=0.0, vary=want_vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))
            self._anchored_dofs[path] = tuple(
                (f"{base}.{c}", float(basis[k][c_idx]))
                for c_idx, c in enumerate(("x", "y", "z")) if basis[k][c_idx] != 0)

    def _collect_body_atom_coords(self, base: str, atom, body: str) -> None:
        """A body atom's x, y, z: locked rows its body's block writes (WP-1805).

        No displacement DOF, no affine row: the coordinates are outputs of a
        derived block (``params.bodies``), which is their one writer, as the
        space group is a fixed special position's.  They still carry esds,
        through the block's local Jacobian.  ``vary=True`` on one is refused in
        the shape of the special-position refusal, naming what does refine.
        """
        if any(getattr(atom, c).vary for c in ("x", "y", "z")):
            raise ValueError(
                f"{base} ({atom.label!r}) is placed by rigid body {body!r}; its "
                "coordinates are the body's — refine the body's origin and "
                "rotation (phases.*.rigid_bodies.*.origin.dof.*, "
                "phases.*.rigid_bodies.*.rotation.*) and set vary=False here")
        for c in ("x", "y", "z"):
            self._add(f"{base}.{c}", getattr(atom, c), force_fixed=True)

    def _collect_body(self, base: str, sg, phase, b: int, body) -> None:
        """A rigid body: origin DOFs, three rotation DOFs, and its block.

        The origin is collected exactly as an atom's coordinates are
        (:meth:`_collect_atom_coords`): anchored displacement DOFs on its
        site-symmetry basis.  A body whose origin, or any of whose atoms, sits
        on a special position is refused for now (``RIGID_BODY_NOT_INVARIANT``;
        WP-1807 takes the stabiliser's axial subspace for the rotation).  The rotation is an
        **anchored increment** δω = E·θ about the record's R₀, zero at every
        build and every commit, bounded per component by
        ``RIGID_BODY_ROTATION_BOUND``; it has as many DOFs as the template's
        inertia rank (two for a linear body, ``params.bodies``), and it is
        never in ``_anchored_dofs`` (:attr:`_anchored_rotations` says why).
        The block is declared after collection, through :meth:`add_derived`.
        """
        from ..schemas.structure import RIGID_BODY_ROTATION_BOUND
        from .bodies import RigidBodyBlock

        bbase = f"{base}.rigid_bodies.{b}"
        xyz = np.array(body.origin.values())
        if len(coordinate_basis(stabilizer_rotations(sg, xyz))) < 3:
            raise ValueError(
                f"RIGID_BODY_NOT_INVARIANT: rigid body {body.name!r} has its "
                f"origin {tuple(xyz)} on a special position of "
                f"{phase.space_group!r}; a body on a special position is not "
                "supported yet (WP-1807) — move the origin to a general "
                "position")
        index = {a.label: j for j, a in enumerate(phase.atoms)}
        # the origin is not the only point a site can fix: a member atom on a
        # special position keeps its coset split for the stage while the body
        # turns it off the site, and the next compile counts |G_x| times as
        # many images (S, O1, O2 of PbSO4 on the Pnma mirror: 8 S and 24 O in
        # a cell of 4 and 16).  Keyed on the stabiliser the forward model's
        # multiplicity is read from (``wyckoff.stabilizer_rotations``)
        for label in body.atoms:
            atom = phase.atoms[index[label]]
            at = np.array([atom.x.value, atom.y.value, atom.z.value])
            order = len(stabilizer_rotations(sg, at))
            if order > 1:
                raise ValueError(
                    f"RIGID_BODY_NOT_INVARIANT: rigid body {body.name!r} has its "
                    f"atom {label!r} at {tuple(float(v) for v in at)} on a "
                    f"special position of {phase.space_group!r} (site symmetry "
                    f"of order {order}); a turn of the body moves it off the "
                    f"site and the next stage counts {order}× its images, and a "
                    "body on a special position is not supported yet (WP-1807) "
                    "— refine that atom outside the body, or state the "
                    "structure in a subgroup where its site is general")
        member = {label: i for i, label in enumerate(body.atoms)}
        try:
            block = RigidBodyBlock(
                phase_base=base, body_base=bbase,
                atom_bases=[f"{base}.atoms.{index[label]}" for label in body.atoms],
                template=np.array(body.template, dtype=np.float64),
                q0=np.array(body.orientation, dtype=np.float64),
                torsions=[(member[t.axis[0]], member[t.axis[1]],
                           [member[m] for m in t.moves]) for t in body.torsions],
                angles=[t.angle for t in body.torsions],
                names=[t.name for t in body.torsions])
        except ValueError as exc:
            raise ValueError(f"rigid body {body.name!r}: {exc}") from None
        before = set(self._anchored_dofs)
        self._collect_atom_coords(f"{bbase}.origin", sg, body.origin)
        self._body_origin_dofs[bbase] = tuple(d for d in self._anchored_dofs
                                              if d not in before)
        # the anchored-rotation kind: identity entries (radians) that a commit
        # composes into R₀ and zeroes, boxed so |δω| stays below the 2π where
        # the exponential map's Jacobian degenerates (WP-1803's handover)
        paths = block.rotation_paths(bbase)
        for path in paths:
            self.entries.append(Entry(
                path=path, value=0.0, vary=body.rotation_vary,
                lo=-RIGID_BODY_ROTATION_BOUND, hi=RIGID_BODY_ROTATION_BOUND,
                transform="identity"))
        self._anchored_rotations[bbase] = paths
        # named-bond torsions (WP-1808): the same kind about one axis each, in
        # degrees and unboxed — a turn about a fixed axis has no singular
        # chart to keep away from, and the commit wraps the record
        twists = block.twist_paths(bbase)
        for path, torsion in zip(twists, body.torsions, strict=True):
            self.entries.append(Entry(path=path, value=0.0, vary=torsion.vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))
        self._anchored_torsions[bbase] = twists
        self._bodies.append((bbase, body.name, block))

    def _check_body_drift(self) -> None:
        """Refuse a body whose stored atoms sit off its map (WP-1805).

        ``RIGID_BODY_TEMPLATE_DRIFT``: measured in Å through the cell, against
        :data:`~rietx.schemas.structure.RIGID_BODY_DRIFT_TOL`.  The write-back
        stores exactly what the map computed, so only an edit of an atom the
        body owns trips this — and silently moving that atom back would undo
        the edit without a word, which is the table's no-diagnostics rule.
        """
        from ..schemas.structure import RIGID_BODY_DRIFT_TOL
        from .derived import cartesian_frame

        values = np.array([e.value for e in self.entries], dtype=np.float64)
        for bbase, name, block in self._bodies:
            x = values[[self._paths[q] for q in block.inputs]]
            placed = block.evaluate(x)
            phase_base = bbase.split(".rigid_bodies.")[0]
            cell = tuple(values[self._paths[f"{phase_base}.cell.{n}"]]
                         for n in ("a", "b", "c", "alpha", "beta", "gamma"))
            m = np.asarray(cartesian_frame(cell), dtype=np.float64)
            rows = [self._paths[q] for q in block.outputs]
            diff = (values[rows] - placed).reshape(-1, 3) @ m.T
            worst = float(np.sqrt((diff * diff).sum(axis=1)).max())
            if worst > RIGID_BODY_DRIFT_TOL:
                i = int(np.argmax((diff * diff).sum(axis=1)))
                atom = block.outputs[3 * i].rsplit(".", 1)[0]
                raise ValueError(
                    f"RIGID_BODY_TEMPLATE_DRIFT: {atom} sits {worst:.3g} Å from "
                    f"where rigid body {name!r} places it.  A body owns its "
                    "atoms' coordinates: move the body (its origin and "
                    "orientation), or rewrite the atoms from it with "
                    "rietx.crystallography.bodies.place_body_atoms")

    def body_rows(self) -> dict[str, str]:
        """Every derived row a rigid body writes → that body's name (WP-1805)."""
        return {q: name for _, name, block in self._bodies for q in block.outputs}

    def body_dofs(self) -> dict[str, str]:
        """Every rigid body's own DOF → that body's name (WP-1805).

        Its origin's displacement DOFs, its rotation DOFs and its torsions'
        twists, read off the data :meth:`_collect_body` built.
        """
        out: dict[str, str] = {}
        for bbase, name, _ in self._bodies:
            out.update(dict.fromkeys(self._anchored_rotations[bbase], name))
            out.update(dict.fromkeys(self._anchored_torsions[bbase], name))
            out.update(dict.fromkeys(self._body_origin_dofs[bbase], name))
        return out

    def body_bond_errors(self) -> dict[str, float]:
        """Per body, the largest |d_ij − d_ij(template)| over its atoms (Å).

        The commit-time rigidity check (WP-1805): a body that is not rigid
        in the committed cell to 1e-9 Å means the map and the record disagree
        — WP-1803 measured a stale anchor at 2e-3 Å against 1e-15 Å.
        """
        from .derived import cartesian_frame

        out: dict[str, float] = {}
        values = {e.path: e.value for e in self.entries}
        for bbase, name, block in self._bodies:
            phase_base = bbase.split(".rigid_bodies.")[0]
            cell = tuple(values[f"{phase_base}.cell.{n}"]
                         for n in ("a", "b", "c", "alpha", "beta", "gamma"))
            m = np.asarray(cartesian_frame(cell), dtype=np.float64)
            x = np.array([values[q] for q in block.outputs]).reshape(-1, 3) @ m.T
            x_in = np.array([values[q] for q in block.inputs])
            t = block.body_points(x_in)
            d = np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)
            d0 = np.linalg.norm(t[:, None, :] - t[None, :, :], axis=2)
            out[name] = float(np.abs(d - d0).max())
        return out

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

    def _collect_atom_moment(self, base: str, phase, atom) -> None:
        """A moment enters θ as a modulus and the angles the site leaves free.

        The **one** parameterisation in the package that is not affine, and the
        reason is in ``crystallography.magnetic.moments``: a direction a powder
        average cannot determine has to be a *column* for
        :meth:`unmeasured_rows` to name it, and neither the components nor
        their coefficients on the allowed basis is one.  So the three
        ``crystalaxis_*`` components are **locked** entries — a record, carried
        for globs, exporters and write-back — and the freedom lives entirely in
        ``…moment.dof<k>``, whose value is the modulus in μ_B and then one or
        two angles in radians.

        The consequence of the non-affine map, stated so nobody looks for it:
        a component has no ``C`` row, so it has no esd.  The esd of this block
        is the modulus's, which is the quantity the data measures; an esd on a
        direction that a powder cannot determine would be a number about
        nothing, and where the powder *can* determine it the angle DOF carries
        it.

        A site whose symmetry allows no moment contributes no DOFs, so a
        ``vary`` request on it is impossible rather than silently dead — the
        schema has already refused the declaration itself.
        """
        moment = getattr(atom, "moment", None)
        if moment is None:
            return
        group = phase.magnetic_symmetry.group()
        cell = phase.cell.lengths_angles()
        xyz = (atom.x.value, atom.y.value, atom.z.value)
        frame = moment_frame(group.allowed_moment_basis(xyz), cell)
        self._moment_frames[base] = frame
        seed = dofs_from_moment(frame, cell, moment.values())
        want_vary = moment.vary
        for name in MOMENT_COMPONENTS:
            self._add(f"{base}.moment.{name}", getattr(moment, name),
                      force_fixed=True)
        # Unbounded and identity-transform, like every other DOF here: the
        # modulus is *signed* on a one-dimensional subspace (the only way two
        # independent sites can be stated antiparallel along one axis), and on
        # a larger one the antipode is an angle away.  |μ| is the magnitude,
        # and the floor that decides support is on |μ|, not a bound.
        for k, value in enumerate(seed):
            self.entries.append(Entry(
                path=f"{base}.moment.dof{k}", value=float(value),
                vary=want_vary, lo=-np.inf, hi=np.inf, transform="identity"))

    def _refresh_moment_components(self) -> None:
        """Write every moment block's components back from its DOFs.

        Called from :meth:`commit` and from :meth:`apply_to_models`, and from
        nowhere in the residual: the map is not affine, so it cannot ride in
        the constraint block with the ADP and coordinate rows, and running it
        per residual evaluation would put a trigonometric call on the hot path
        for a quantity only the *report* reads.  The forward model computes the
        components it needs from the DOFs directly, through the same frame.
        """
        if not self._moment_frames:
            return
        by_path = {e.path: e for e in self.entries}
        for base, frame in self._moment_frames.items():
            dofs = [by_path[f"{base}.moment.dof{k}"].value
                    for k in range(len(frame))]
            components = moment_from_dofs(frame, dofs)
            for name, value in zip(MOMENT_COMPONENTS, components, strict=True):
                by_path[f"{base}.moment.{name}"].value = float(value)

    def _canonicalise_moment_dofs(self) -> np.ndarray | None:
        """Move every moment block's DOFs into the principal chart (#604).

        :func:`~rietx.crystallography.magnetic.moments.canonical_dofs` says
        what the chart is and why every move is an identity on the moment.
        Returns the ±1 that each **free column** was multiplied by, for the
        caller to carry its outcome across
        (:func:`~rietx.optimize.least_squares.rechart_outcome`), or
        ``None`` when nothing moved.

        Only an entry that is untied, unlocked, not held by the caller and no
        tie's source is moved: a tie reads its source's *value*, so a turn
        added to a source would add a turn's multiple to its dependent, and a
        reflection would negate one that is not an angle; and a caller's
        ``hold`` (``Entry.held``) is a number they set, which the next stage
        and the next pattern of a chain start from (review of #631).  An
        entry the *stage* froze (``vary=False``, e.g. ``_hold_flat_moments``'
        flat azimuth) is moved with its block, which is exactly the entry a
        reflected polar angle needs.  A move that would touch an entry it may
        not is not made; that block's other angles still lose their whole
        turns, which touch nothing but themselves.

        A sign is recorded wherever the move negates a column, **whether or
        not its value changed**: the antipode maps θ to π − θ, which leaves
        θ = π/2 — the seed of every in-plane moment — where it was and still
        negates its column (review of #631).
        """
        if not self._moment_frames:
            return None
        sources = {path for e in self.entries if e.tie is not None
                   for path, _ in e.tie.terms}
        column = {self.entries[i].path: k for k, i in enumerate(self._free_idx)}
        by_path = {e.path: e for e in self.entries}
        signs = np.ones(len(self._free_idx), dtype=np.float64)
        moved = False
        for base, frame in self._moment_frames.items():
            block = [by_path[f"{base}.moment.dof{k}"] for k in range(len(frame))]
            movable = [e.tie is None and not e.locked and not e.held
                       and e.path not in sources for e in block]
            old = np.array([e.value for e in block], dtype=np.float64)
            new, s = canonical_dofs(old)
            changed = (new != old) | (s != 1.0)
            if not all(m for m, c in zip(movable, changed, strict=True) if c):
                # whole turns only, angle by angle
                new, s = old.copy(), np.ones(len(old))
                for k in range(1, len(old)):
                    if movable[k]:
                        new[k] = wrap_angle(old[k])
                changed = new != old
            for e, value, sign, c in zip(block, new, s, changed, strict=True):
                if c:
                    e.value = float(value)
                    if e.path in column:
                        signs[column[e.path]] = sign
                    moved = True
        return signs if moved else None

    def reframe_moments(self, structure: Structure) -> list[str]:
        """Rebuild every moment frame from ``structure``'s cell; keep the moment.

        A stage's start (issue #598).  The frame is Gram-Schmidt in the unit-
        vector metric, which moves with the cell *angles*, so a stage that
        refined β left the table reading the DOFs in the frame of the cell the
        fit started from while the next compile built one from the cell it had
        reached: the forward model and the write-back then meant two moments by
        the same DOFs, 9σ apart on a monoclinic β that moved 2°.  Here the
        frame is rebuilt from the cell the caller has just written back and
        each DOF block is re-seeded so that it states, in the new frame, the
        crystal-axis components it stated in the old one — the moment the data
        were fitted with is what carries across the boundary, not its numbers
        in a frame that no longer applies.  :meth:`push_moment_frames` then
        hands the compile these frames.

        Returns the atom base paths whose frame was rebuilt.
        """
        frames: dict[str, np.ndarray] = {}
        for base in self._moment_frames:
            _, ip, _, j = base.split(".")
            phase = structure.phases[int(ip)]
            atom = phase.atoms[int(j)]
            xyz = (atom.x.value, atom.y.value, atom.z.value)
            frames[base] = moment_frame(
                phase.magnetic_symmetry.group().allowed_moment_basis(xyz),
                phase.cell.lengths_angles())
        return self._reseed_moments(frames)

    def pull_moment_frames(self, model) -> list[str]:
        """Seat this table's moment DOFs in ``model``'s frames (#598).

        For a table built *after* a fit from the written-back structure and
        evaluated on the fit's own model (``predict()``, ``report()``, the
        reflection table, a series' moment rows): the table seeds its DOFs in a
        frame built at the fitted cell, the model reads them in the last
        stage's, and where that stage moved an angle the pair would describe a
        moment neither of them holds.  The components are what the two agree
        on, so the DOFs are re-seeded to state them in the model's frames.
        Returns the atom base paths re-seeded.
        """
        frames: dict[str, np.ndarray] = {}
        for base in self._moment_frames:
            own = self._model_frame(model, base)
            if own is not None:
                frames[base] = own
        return self._reseed_moments(frames)

    def push_moment_frames(self, model) -> None:
        """Make ``model`` read the moment DOFs in this table's frames (#598).

        A compile builds each site's frame from the cell it is given, which is
        the right frame only when that is the cell the DOFs were seeded in.
        After a stage start's :meth:`reframe_moments` it is, and this changes
        nothing a compile did not already hold to roundoff.  The result's own
        compile (``Refinement._final_compile``) is the case it exists for: it
        is built at the *fitted* cell, so where the last stage moved an angle
        its frames are a third frame for the DOFs the solve refined in the
        stage's, and ``y_calc`` described a moment neither the solve nor the
        write-back had.
        """
        for base, frame in self._moment_frames.items():
            if self._model_frame(model, base) is None:
                continue
            _, ip, _, j = base.split(".")
            model.phases[int(ip)].magnetic.frames[int(j)] = frame

    def _model_frame(self, model, base: str) -> np.ndarray | None:
        """``model``'s frame for the site at ``base``, checked against ours."""
        _, ip, _, j = base.split(".")
        msites = getattr(model.phases[int(ip)], "magnetic", None)
        if msites is None:
            return None
        own = msites.frames[int(j)]
        mine = self._moment_frames[base]
        if own is None or own.shape != mine.shape:
            raise ValueError(
                f"{base}: the compiled model has a "
                f"{0 if own is None else len(own)}-dimensional moment subspace "
                f"and the parameter table a {len(mine)}-dimensional one; they "
                f"were built from different structures")
        return own

    def _reseed_moments(self, frames: Mapping[str, np.ndarray]) -> list[str]:
        """Swap in ``frames`` and re-seed each DOF block to the same moment.

        A frame within ``_MOMENT_REFRAME_TOL`` of the one held is left as it
        was, DOFs and all: every orthogonal or hexagonal cell, whose angles are
        fixed by symmetry, and every boundary the cell did not move across, so
        those fits are bit-identical to what they were.  A zero moment keeps
        its DOFs too, because its angles are not recoverable from components
        that are all zero and they are what a later stage grows the moment
        along.  The coefficients are solved on the frame's rows
        (:func:`~rietx.crystallography.magnetic.moments.dofs_in_frame`), so a
        frame need not have been built at the cell this table holds.
        """
        if not frames:
            return []
        self._refresh_moment_components()
        by_path = {e.path: e for e in self.entries}
        moved: list[str] = []
        for base, frame in frames.items():
            old = self._moment_frames[base]
            if (frame.shape == old.shape
                    and float(np.max(np.abs(frame - old), initial=0.0))
                    <= _MOMENT_REFRAME_TOL):
                continue
            components = [by_path[f"{base}.moment.{name}"].value
                          for name in MOMENT_COMPONENTS]
            self._moment_frames[base] = np.array(frame, dtype=np.float64)
            moved.append(base)
            if not any(components):
                continue
            for k, value in enumerate(dofs_in_frame(frame, components)):
                entry = by_path[f"{base}.moment.dof{k}"]
                # a tied entry's own value is never read: decoding takes its
                # source's.  Writing one here would give the write-back a
                # moment (this entry's re-seed) that the compile (the
                # source's) does not hold, #598's mismatch again (review of
                # #615).  Its source is re-seeded in its own frame; the tied
                # entry follows it, as a tie means.
                if entry.tie is None:
                    entry.value = float(value)
        if moved:
            self._rebuild()
            # bring each tied entry's stored value to what decoding gives it,
            # so the components below are the ones the compile will build
            decoded = self.decode(self.x0())
            for e in self.entries:
                if e.tie is not None and e.path.endswith(
                        tuple(f".moment.dof{k}" for k in range(3))):
                    e.value = decoded[e.path]
            self._refresh_moment_components()
        return moved

    def moment_frames(self) -> dict[str, np.ndarray]:
        """The per-site frames of the current stage, for a caller that has to
        reproduce them — the forward model takes these, not its own."""
        return dict(self._moment_frames)

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

        **The derived rows follow, here** (WP-1805, the #773 follow-up).  Every
        writer that moves a value outside a solve ends in a rebuild — the
        seeds, the anchored-DOF rebase, re-anchor and displacement, the tie
        refresh — and any of them can move a block input (a softplus cell
        length, a body origin), so the refresh is made where they all pass
        rather than remembered by each.
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
        self._rebuild_derived()
        if self._derived_idx:
            self._refresh_derived()

    # -- the derived blocks (WP-1804) ------------------------------------
    def _rebuild_derived(self) -> None:
        """Index every block's inputs/outputs and build the declared reach.

        ``_reach`` has C's shape: an affine row carries C's own pattern, and a
        derived row the union of the rows its declared inputs reach — so a
        body atom row reaches the origin, rotation and cell columns whether or
        not the rotation happens to leave it still at this θ.  Built once per
        rebuild, like C, and read by every pattern reader instead of C.
        """
        blocks = getattr(self, "derived", [])
        self._derived_idx: list[tuple[np.ndarray, np.ndarray]] = []
        if not blocks:
            self._reach = self._C
            return
        for block in blocks:
            ins = np.array([self._paths[q] for q in block.inputs], dtype=np.intp)
            outs = np.array([self._paths[q] for q in block.outputs], dtype=np.intp)
            self._derived_idx.append((ins, outs))
        reach = (abs(self._C) > 0.0).astype(np.float64).tolil()
        for block, (ins, outs) in zip(blocks, self._derived_idx, strict=True):
            pattern = block.reach_pattern()
            for r, out in enumerate(outs):
                row = sparse.csr_matrix((1, reach.shape[1]), dtype=np.float64)
                for k in np.flatnonzero(pattern[r]):
                    row = row + reach[int(ins[k])].tocsr()
                reach[int(out)] = (abs(row) > 0.0).astype(np.float64)
        self._reach = reach.tocsr()

    def add_derived(self, block: DerivedBlock) -> None:
        """Declare a nonlinear block after the affine one (WP-1804).

        Every output must be an existing **locked** entry no earlier block
        writes: the block is that row's only writer, as the space group is a
        locked coordinate's.  Every input must exist and must not be written
        by this block or a later one, so the blocks apply in one pass in
        declaration order.  The outputs' values are written from the map at
        once, so the table never holds a derived row that disagrees with it.
        """
        for q in (*block.inputs, *block.outputs):
            if q not in self._paths:
                raise ValueError(f"derived block names unknown parameter {q!r}")
        # the shapes are checked before anything is registered: the rebuild
        # below reads the reach pattern, and a block that failed there would
        # be left half-declared (the #773 follow-up)
        shape = (len(block.outputs), len(block.inputs))
        pattern = np.asarray(block.reach_pattern())
        if pattern.shape != shape or pattern.dtype != bool:
            raise ValueError(
                f"derived block's reach_pattern() is {pattern.dtype} "
                f"{pattern.shape}; it must be bool {shape} (outputs × inputs)")
        written = {q for b in self.derived for q in b.outputs}
        for q in block.outputs:
            e = self.entries[self._paths[q]]
            if not e.locked or e.tie is not None:
                raise ValueError(
                    f"{q!r} cannot be a derived row: a block's output must be "
                    "a locked entry with no tie, which only the block writes")
            if q in written:
                raise ValueError(f"{q!r} is already written by another derived block")
        own = set(block.outputs)
        for q in block.inputs:
            if q in own:
                raise ValueError(f"derived block reads its own output {q!r}")
        # an earlier block has already been evaluated on its inputs, so a later
        # block may not write one of them: the earlier block would hold a value
        # computed from the input's state before this write
        earlier_inputs = {q for b in self.derived for q in b.inputs}
        for q in block.outputs:
            if q in earlier_inputs:
                raise ValueError(
                    f"{q!r} is an input of an earlier derived block, so this "
                    "block cannot write it: blocks apply in declaration order "
                    "and the earlier one would evaluate on a stale value")
        self.derived.append(block)
        self._rebuild()            # which refreshes the derived rows too

    def derived_paths(self) -> frozenset[str]:
        """Every entry a derived block writes."""
        return frozenset(q for b in self.derived for q in b.outputs)

    def _apply_derived(self, p: np.ndarray) -> None:
        """Overwrite the derived rows of the physical vector ``p``, in order."""
        for block, (ins, outs) in zip(self.derived, self._derived_idx, strict=True):
            p[outs] = block.evaluate(p[ins])

    def _refresh_derived(self) -> None:
        """Write every derived row's entry value from its block.

        Where a value changes outside a solve (a build, ``set_values``, a
        commit) the derived rows follow it here — the slot
        :meth:`_refresh_moment_components` holds for the moment.
        """
        if not self.derived:
            return
        p = np.array([e.value for e in self.entries], dtype=np.float64)
        self._apply_derived(p)
        for _, outs in self._derived_idx:
            for i in outs:
                self.entries[int(i)].value = float(p[int(i)])
            # a derived row is held in the affine block, so ``d`` carries it
            self._d[outs] = p[outs]

    def local_jacobian(self, theta: np.ndarray) -> sparse.csr_matrix:
        """∂p_phys/∂p_free at θ (n_entries × n_free): C, with derived rows exact.

        With no block this **is** C (the same object), so every reader that
        switched from C to this is bit-identical on a table without a body.
        With blocks, each derived row is its block's Jacobian chained through
        the rows of its inputs — C's rows, or an earlier block's — so a body
        atom's row carries the origin, rotation and cell columns at θ, where
        the anchor rows of a linearisation would be 2.3–2.9 % off after a 3°
        solve (WP-1803's record).
        """
        if not self.derived:
            return self._C
        p_free = np.array([to_physical(float(t), self.entries[i].transform)
                           for t, i in zip(theta, self._free_idx, strict=True)],
                          dtype=np.float64)
        p = self._C @ p_free + self._d if len(p_free) else self._d.copy()
        jac = self._C.toarray()
        for block, (ins, outs) in zip(self.derived, self._derived_idx, strict=True):
            x = p[ins]
            jac[outs] = block.jacobian(x) @ jac[ins]
            p[outs] = block.evaluate(x)
        return sparse.csr_matrix(jac)

    def reach_block(self) -> sparse.csr_matrix:
        """C's sparsity with each derived row's **declared** reach (WP-1804).

        What the pattern readers ask instead of C: :attr:`moving_paths`,
        :meth:`column_reach`, :meth:`unmeasured_rows` and
        ``optimize.least_squares._column_extras``.  Only the pattern is a
        claim: on a table with a block every stored value is 1.0, so a
        coefficient is read off :meth:`constraint_block`, never here (#801).
        ``C`` itself on a table without a block.
        """
        return self._reach

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
                      transform: str = "identity",
                      unit: str | None = None) -> None:
        """Append a synthetic parameter (e.g. a Wyckoff displacement DOF).

        Synthetic paths must not collide with existing entries; pick names
        outside the model tree, e.g. ``phases.0.atoms.2.dof.0``.  ``unit`` is
        recorded as :meth:`_add` records a model parameter's, so a named
        variable sized like the width it replaces gets that width's floor seed.
        """
        if path in self._paths:
            raise ValueError(f"parameter {path!r} already exists")
        self.entries.append(Entry(path=path, value=value, vary=vary,
                                  lo=lo, hi=hi, transform=transform))
        self._units[path] = unit
        self._rebuild()

    def tie_source_refusal(self, tie: AffineTie) -> tuple[str, str] | None:
        """The first source of ``tie`` the affine block cannot carry, or ``None``.

        A source that is locked or derived is flattened into d at its value of
        the moment and never moves again: a locked row holds no column, and a
        derived row is written after the matmul.  Measured before this refusal
        (WP-1803): the dependent's C row emptied and it left ``moving_paths``
        with no error.  The mirror of ``apply_value_scale``'s refusal of a
        scaled source.  Returns ``(path, "derived" | "locked")``; one authority
        for :meth:`set_tie`, which raises, and ``Refinement._apply_ties``,
        which drops the tie and says so (a model edit never stops a build).
        """
        derived = self.derived_paths()
        for src, _ in tie.terms:
            j = self._paths.get(src)
            if j is not None and (src in derived or self.entries[j].locked):
                return src, "derived" if src in derived else "locked"
        return None

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
        if tie is not None:
            reason = self.tie_source_refusal(tie)
            if reason is not None:
                src, kind = reason
                raise ValueError(
                    f"cannot tie {path!r} to {src!r}: the source is a "
                    f"{kind} row, which the affine block cannot carry, so "
                    f"{path!r} would be frozen at its present value")
        if tie is not None:
            self._refuse_body_increment_tie(path, tie)
        e.tie = tie
        if tie is not None:
            e.vary = False
        self._rebuild()

    def _body_increment_kind(self, path: str) -> str | None:
        """``"rotation"``/``"torsion"``/``"origin"`` for a body increment, else ``None``.

        Read off :attr:`_anchored_rotations` and :attr:`_body_origin_dofs`,
        the data built where each increment is anchored, never off the name.
        """
        if any(path in paths for paths in self._anchored_rotations.values()):
            return "rotation"
        if any(path in paths for paths in self._anchored_torsions.values()):
            return "torsion"
        if any(path in dofs for dofs in self._body_origin_dofs.values()):
            return "origin"
        return None

    def _refuse_body_increment_tie(self, path: str, tie: AffineTie) -> None:
        """A body increment ties only to an increment of its own kind (WP-1805).

        δω and δo restart at zero at every table build while the record moves,
        so a dependent that does not restart with them reads the increment of
        one build against the anchor of the next: WP-1803 measured the
        dependent at 0.07 after the commit and back at 0.02 on the next build.
        Both directions are refused, naming the pair; a body DOF may follow
        another body DOF of the same kind, since both reset together.
        """
        target = self._body_increment_kind(path)
        for src, _ in tie.terms:
            kind = self._body_increment_kind(src)
            if kind == target:
                continue
            if kind is not None or target in ("rotation", "torsion"):
                raise ValueError(
                    f"cannot tie {path!r} to {src!r}: a rigid body's rotation, "
                    "torsion and origin increments restart at zero at every build "
                    "while its record moves, so only an increment of the same "
                    "kind can follow one (or be followed by one)")

    def set_held(self, paths: str | Iterable[str], held: bool) -> list[str]:
        """Mark entries as the caller's declared hold.  Returns the ones that exist.

        Holding forces ``vary=False``, for the reason tying does: the caller
        has said this parameter does not move, and leaving it free would mean
        the very next solve moved it.  A locked or tied entry is marked anyway
        and the mark changes nothing about it, so a hold declared over a broad
        glob does not have to know which rows the space group had already
        taken; ``ParameterRow.held_because`` reports the structural reason
        first, because that is the one a caller cannot lift.

        It takes **several paths in one call**, and that is not a
        convenience.  The whole register is re-applied on every table build,
        and :meth:`_rebuild` walks every entry, so one rebuild per path made
        that re-application quadratic in the size of the hold: at 41 entries a
        ``hold("*")`` put a build from 1.13 ms to 2.10 ms, and the term grows
        as N².

        Unlike :meth:`set_tie` this returns rather than raising on an unknown
        path.  The register is re-applied on every build, and a path can
        vanish between two of them (a phase removed by ``edit``), which is
        ``Refinement._apply_holds``' warning to give rather than this
        method's crash.
        """
        if isinstance(paths, str):
            paths = [paths]
        hits = []
        for path in paths:
            i = self._paths.get(path)
            if i is None:
                continue
            e = self.entries[i]
            e.held = held
            if held:
                e.vary = False
            hits.append(path)
        self._rebuild()
        return hits

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
                e.value = self._implied(e.tie, e.path)
        self._rebuild()  # held tied entries contribute to d through their values
        self._refresh_derived()

    def rebase_anchored_dofs(self, paths: Iterable[str]) -> list[str]:
        """Take a user-tied displacement DOF back out of its coordinates' anchor.

        A coordinate DOF is a displacement *from the stored coordinate*: the
        row is ``x = x_stored + Σ Bₖ·θₖ`` and the DOF is rederived to zero on
        every build, so a rebuild reproduces ``x`` exactly.  That holds only
        while the DOF comes back at zero.  Tie one to a source that does
        **not** reset — a named variable, re-declared from its register at the
        value it holds — and the rebuild anchors at a coordinate that has
        already absorbed the displacement and then adds it again, once per
        table build, for as long as the tie is declared (WP-1432, issue #293).

        So the anchor is corrected here, where the tie is known: ``x_stored``
        less what the tie is about to contribute.  The rebuild then preserves
        the coordinate, which is the invariant the free case already had, and
        the DOF reads the displacement its tie says it is rather than zero.
        The anchor stops moving after the first rebuild and the coordinate is
        *derived* from the variable rather than accumulated, which is what
        makes a second ``fit()`` report what the first one did.

        Takes the paths just declared and returns the ones it rebased, so a
        caller can say that it happened.  A DOF whose source is another
        coordinate DOF contributes zero (both ends reset together) and is
        rebased by exactly nothing — that arm stays bit-identical.  An ADP or
        Stephens DOF is **absolute** and never appears in
        :attr:`_anchored_dofs`, so it is not reachable from here at all.

        Values are recomputed for the rows this touches rather than through
        :meth:`refresh_ties`, which would recompute every tied entry in the
        table for a repair that reaches two of them.

        **A path is rebased once per table, and the table is what remembers
        it.**  The correction subtracts from a stored constant, so a second
        application walks the coordinate the other way by the same amount.
        That is the defect mirrored, and it is just as silent.  A repeat call
        therefore skips what the first one did and rebases only what is new,
        which lets a caller hand the whole register over after declaring one
        more tie.  The guard is in the table rather than in a calling
        convention, for the reason :attr:`Entry.held` is: a convention is
        honoured only by the callers that remembered it, and the register
        gains consumers.
        """
        hits = [p for p in paths
                if p in self._anchored_dofs and p in self._paths
                and p not in self._rebased
                and self.entries[self._paths[p]].tie is not None]
        if not hits:
            return []
        for path in hits:
            dof = self.entries[self._paths[path]]
            dof.value = self._implied(dof.tie, path)
            # a row symmetry took over is skipped there; _apply_ties says so
            self._shift_anchor(path, dof.value)
        self._rebased.update(hits)
        self._rebuild()
        return hits

    @property
    def anchored_dof_paths(self) -> frozenset[str]:
        """The displacement DOFs, whose values are relative to where a fit began.

        A coordinate DOF reads the displacement from the coordinate this table
        was built on, so a fit reports how far it moved the atom, and two fits
        of one pattern started from different coordinates report different
        values for the same answer.  A reader comparing that value *across*
        fits is comparing their starting points, and should compare the
        coordinate rows, which are absolute and carry the same esd.  Read off
        :attr:`_anchored_dofs`, the data built where the anchor is, never off
        the path's name: the ADP and Stephens DOFs spell theirs the same way
        and are absolute.
        """
        return frozenset(self._anchored_dofs)

    @property
    def anchored_rotation_paths(self) -> frozenset[str]:
        """Every rigid body's rotation DOFs, the anchored-rotation kind (WP-1805).

        Zero at every build and every commit, which composes them into the
        body's stored orientation, so the value a fit reports is the step its
        last stage took and never an orientation; a reader comparing it across
        fits compares nothing.  The quaternion record and the body atoms' rows
        are what carry the answer.  A torsion's twist is the same kind about
        one axis (WP-1808), its record the torsion's ``angle``.  Read off
        :attr:`_anchored_rotations` and :attr:`_anchored_torsions`.
        """
        return frozenset(p for kind in (self._anchored_rotations, self._anchored_torsions)
                         for paths in kind.values() for p in paths)

    @property
    def angle_dof_paths(self) -> frozenset[str]:
        """The moment DOFs that are angles, compared across fits modulo a turn.

        Every ``…moment.dof<k>`` past the modulus of a block with two or three
        DOFs (:data:`~rietx.crystallography.magnetic.moments.DOF_NAMES`).  A
        commit leaves them in the principal chart
        (:meth:`_canonicalise_moment_dofs`), and that chart still has a cut:
        a moment along −a is φ = π − ε in one fit and −π + ε in the next, the
        same direction 2π apart in value (#604).  A reader comparing them
        across fits takes the difference into (−π, π] first; for the polar
        angle, which the chart keeps in [0, π], that changes nothing.  Read off
        the frames, the data built where the block is, never off the path's
        name.
        """
        return frozenset(f"{base}.moment.dof{k}"
                         for base, frame in self._moment_frames.items()
                         for k in range(1, len(frame)))

    def displace_anchored_dofs(self, coordinates: Mapping[str, float],
                               named: Callable[[str], bool],
                               orientations: Mapping[str, Iterable[float]] | None = None,
                               torsions: Mapping[str, Iterable[float]] | None = None
                               ) -> list[str]:
        """Set displacement DOFs so their coordinates reach ``coordinates``.

        The inverse of what a build does.  A build anchors each coordinate row
        at the stored value and rederives its DOF to zero, so the DOF of a
        table built from a *fitted* model reads zero however far the fit moved
        the atom: the displacement lives in the anchor, and copying the DOF
        from one table to another copies nothing.  A series did exactly that,
        and restarted every pattern's refined coordinates from the initial
        model while ``carry=["*"]`` said they crossed (WP-1333).  So the
        displacement is recovered from the coordinates themselves: the DOF
        values θ solving ``anchor + B·θ = target`` over a site's rows.

        **A site moves as a site.**  A DOF moves when ``named`` admits its own
        path or any coordinate row it reaches, and then every row it reaches
        follows, since a row is a tie and ``named`` is a caller's policy, not
        the site's.  θ is solved over all of a site's rows present in
        ``coordinates``, so a target that is not on the site is *projected*
        onto the site's own directions: nothing here can move an atom off the
        special position this table's model puts it on.  A DOF already tied
        by the caller follows its source and is left alone, as is a row
        symmetry has taken over.

        Sites are grouped by the rows their DOFs share, read off
        :attr:`_anchored_dofs` rather than off the path names, for the reason
        that attribute gives.  Returns the DOF paths set.

        **A rigid body moves as a body** (WP-1805).  Its origin is a site like
        any other, δo = o_target − o₀ through the rule above, exact for a
        translation.  Its rotation is not: the subtraction rule is wrong by
        O(δω²), 0.0147° at 3° (WP-1803's record), so the increment is set from
        the record instead, δω = Log(R_target·R₀ᵀ), with R_target the unit
        quaternion ``orientations`` gives for the body's base path
        (``phases.i.rigid_bodies.b``).  A linear body's two DOFs take the
        smallest turn carrying its axis R₀·u onto R_target·u, which lies in
        their plane exactly (a spin about the axis moves no atom).  The body
        moves when ``named`` admits one of its rotation DOFs or one of its
        atoms' rows; a rotation DOF the caller tied is left alone.  A body's
        torsions (WP-1808) follow the same rule from their record:
        ``torsions`` gives the target angles per body base path, and each
        twist is set to the target less its anchor, taken into (−180, 180] —
        exact, since turns about one axis add.
        """
        groups: list[tuple[list[str], set[str]]] = []
        for dof, rows in self._anchored_dofs.items():
            if dof not in self._paths:
                continue
            reach = {p for p, _ in rows}
            dofs = [dof]
            for group in [g for g in groups if g[1] & reach]:
                groups.remove(group)
                dofs = group[0] + dofs
                reach |= group[1]
            groups.append((dofs, reach))
        moved: list[str] = []
        for dofs, reach in groups:
            chosen = [d for d in dofs
                      if self.entries[self._paths[d]].tie is None
                      and (named(d) or any(named(p) for p, _ in self._anchored_dofs[d]))]
            rows = sorted(p for p in reach
                          if p in coordinates and self.entries[self._paths[p]].tie is not None)
            if not chosen or not rows:
                continue
            row_of = {p: i for i, p in enumerate(rows)}
            basis = np.zeros((len(rows), len(dofs)), dtype=np.float64)
            for k, d in enumerate(dofs):
                for p, coeff in self._anchored_dofs[d]:
                    if p in row_of:
                        basis[row_of[p], k] = coeff
            gap = np.array([coordinates[p] - self.entries[self._paths[p]].tie.const
                            for p in rows], dtype=np.float64)
            # a DOF of the group that is not chosen stays where it is, so its
            # contribution is taken out of the gap and θ is solved over the
            # chosen columns alone — solving jointly and then writing only the
            # chosen half would leave the rows short of their targets
            cols = [k for k, d in enumerate(dofs) if d in chosen]
            held = [k for k, d in enumerate(dofs) if d not in chosen]
            if held:
                gap -= basis[:, held] @ np.array(
                    [self.entries[self._paths[dofs[k]]].value for k in held],
                    dtype=np.float64)
            theta, *_ = np.linalg.lstsq(basis[:, cols], gap, rcond=None)
            for k, value in zip(cols, theta):
                self.entries[self._paths[dofs[k]]].value = float(value)
                moved.append(dofs[k])
        for d in moved:
            for p, _ in self._anchored_dofs[d]:
                e = self.entries[self._paths[p]]
                if e.tie is not None:
                    e.value = self._implied(e.tie, p)
        moved += self._displace_body_rotations(orientations or {}, named)
        moved += self._displace_body_torsions(torsions or {}, named)
        if moved:
            self._rebuild()
        return moved

    def _displace_body_rotations(self, orientations: Mapping[str, Iterable[float]],
                                 named: Callable[[str], bool]) -> list[str]:
        """The rotation half of :meth:`displace_anchored_dofs` (its docstring)."""
        from ..crystallography import rotation

        moved: list[str] = []
        for bbase, _, block in self._bodies:
            target = orientations.get(bbase)
            paths = self._anchored_rotations[bbase]
            if target is None or not (any(named(p) for p in paths)
                                      or any(named(q) for q in block.outputs)):
                continue
            r_t = np.asarray(rotation.matrix_from_quaternion(
                np.asarray(tuple(target), dtype=np.float64)), dtype=np.float64)
            if block.n_rot == 3:
                omega = np.asarray(rotation.vector_from_matrix(r_t @ block.r0.T),
                                   dtype=np.float64)
            else:
                u = np.cross(block.body_axes[:, 0], block.body_axes[:, 1])
                a, b = block.r0 @ u, r_t @ u
                axis = np.cross(a, b)
                sin, cos = float(np.linalg.norm(axis)), float(a @ b)
                # near antiparallel the cross product is rounding noise, with
                # a component along ``a`` that E's plane would drop, shortening
                # the turn (1e-5 in a coordinate at sin = 6e-17); any axis
                # normal to ``a`` is exact there, so project onto that plane
                axis = axis - (axis @ a) * a
                norm = float(np.linalg.norm(axis))
                if norm != 0.0:
                    omega = axis / norm * math.atan2(sin, cos)
                elif cos > 0.0:
                    omega = np.zeros(3)
                else:
                    # exactly antiparallel: a half turn about any axis normal
                    # to the body's, and E's first column is one (#801)
                    e0 = block.axes[:, 0]
                    omega = math.pi * e0 / np.linalg.norm(e0)
            theta, *_ = np.linalg.lstsq(block.axes, omega, rcond=None)
            for path, value in zip(paths, theta, strict=True):
                e = self.entries[self._paths[path]]
                if e.tie is None:
                    e.value = float(value)
                    moved.append(path)
        return moved

    def _displace_body_torsions(self, torsions: Mapping[str, Iterable[float]],
                                named: Callable[[str], bool]) -> list[str]:
        """The torsion half of :meth:`displace_anchored_dofs` (its docstring)."""
        from .bodies import wrap_degrees

        moved: list[str] = []
        for bbase, _, block in self._bodies:
            target = torsions.get(bbase)
            paths = self._anchored_torsions[bbase]
            if target is None or not paths or not (
                    any(named(p) for p in paths)
                    or any(named(q) for q in block.outputs)):
                continue
            for path, want, phi0 in zip(paths, tuple(target), block.phi0, strict=True):
                e = self.entries[self._paths[path]]
                if e.tie is None:
                    e.value = wrap_degrees(float(want) - float(phi0))
                    moved.append(path)
        return moved

    def reanchor_dofs(self, paths: Iterable[str],
                      absorbed: Mapping[str, float]) -> list[str]:
        """Re-anchor tied DOFs whose coordinates absorbed the tie elsewhere.

        :meth:`rebase_anchored_dofs` takes a tie's contribution at its sources'
        *current* values out of the anchor, which is right while the stored
        coordinate was written by this table's own sources.  A coordinate
        carried in from another model was written by *that* model's: a
        series' previous pattern, whose variable held its fitted value, while
        this pattern's ``constrain`` hook re-declares the variable at its
        start.  The anchor is then short by ``B·(f(absorbed) − f(now))``, and
        warming the variable adds that displacement a second time, once per
        pattern (WP-1333, the chain form of WP-1432).

        ``absorbed`` maps source paths to the values they held when the
        coordinate was written; a source it does not name is taken to have
        held its current value, so contributes nothing.  The tie is read as
        declared *here*: a caller whose sources were tied differently when the
        coordinate was written has no correct answer to ask this for.  So is
        its flattening: a source that is another atom's coordinate row
        flattens onto *this* table's anchor for it, so a DOF tied to a
        coordinate whose own carry differed is not corrected for the
        difference.

        Guarded once per path per table, like :attr:`_rebased` and for its
        reason: the correction subtracts from a stored constant, so a repeat
        walks the coordinate back.  Only a move is remembered, so a call that
        found nothing to correct does not stand in the way of one that does.
        Returns the paths whose anchor moved.
        """
        moved: list[str] = []
        for path in paths:
            if (path not in self._anchored_dofs or path not in self._paths
                    or path in self._reanchored):
                continue
            dof = self.entries[self._paths[path]]
            if dof.tie is None:
                continue
            terms, const = self._flatten(dof.tie, (path,))
            then = const + sum(
                c * absorbed.get(self.entries[j].path, self.entries[j].value)
                for j, c in terms)
            shift = then - self._implied(dof.tie, path)
            if shift == 0.0:
                continue
            self._reanchored.add(path)
            self._shift_anchor(path, shift)
            moved.append(path)
        if moved:
            self._rebuild()
        return moved

    def _shift_anchor(self, dof: str, shift: float) -> None:
        """Move the anchor of every coordinate row ``dof`` reaches by ``−B·shift``.

        The one subtraction :meth:`rebase_anchored_dofs` and
        :meth:`reanchor_dofs` both make; each caller owns its own guard, since
        the subtraction is not idempotent.  A row symmetry has taken over (no
        tie) is left alone.
        """
        for coord, coeff in self._anchored_dofs[dof]:
            e = self.entries[self._paths[coord]]
            if e.tie is None:   # symmetry took the row over
                continue
            e.tie = replace(e.tie, const=e.tie.const - coeff * shift)
            e.value = self._implied(e.tie, coord)

    def _implied(self, tie: AffineTie, path: str) -> float:
        """The value a tie implies right now, chains flattened onto free rows."""
        terms, const = self._flatten(tie, (path,))
        return const + sum(c * self.entries[j].value for j, c in terms)

    # -- vary control (used by the staged strategy) --------------------
    def set_vary(self, path_globs: list[str], vary: bool) -> list[str]:
        """Glob-match entry paths (fnmatch semantics on dot paths); returns hits.

        Tied and locked entries never match: symmetry-fixed cell angles and
        the line-0 emission weight cannot be freed even by a broad glob such
        as ``phases.*.cell.*``.

        Nor does a **held** entry, the caller's own declaration that this
        parameter does not move (WP-1435).  It is skipped here rather than
        checked by each caller because a stage's ``turn_on`` arrives through
        this method, and a hold that only ``Refinement.set_vary`` honoured
        would be silently overridden by every plan.  Whether a caller is told
        about the skip is that caller's question: a plan records it on
        ``StageResult.blocked_by_hold``, and ``Refinement.set_vary`` refuses a
        literal path outright.
        """
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
            if self._glob_reaches(e, path_globs, vary):
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

    @staticmethod
    def _glob_reaches(e: Entry, path_globs: list[str], vary: bool) -> bool:
        """``set_vary``'s matching rule for one row, and nothing else.

        Tied and locked rows never match, and a held one never matches a
        *freeing* call.  One predicate, so :meth:`would_free` cannot drift
        from what ``set_vary`` does (WP-1343: a restated copy at a call site
        left the hold out).
        """
        import fnmatch

        return (any(fnmatch.fnmatchcase(e.path, g) for g in path_globs)
                and e.tie is None and not e.locked
                and not (vary and e.held))

    def would_free(self, path_globs: list[str]) -> list[str]:
        """The paths ``set_vary(path_globs, True)`` would match — a dry run.

        Entry order, and the table is not touched.  The one thing it does not
        replay is ``set_vary``'s *dynamic* wavelength skip, which depends on
        the order the cell and λ are freed in the same call; a caller asking
        about any other family gets exactly ``set_vary``'s answer (WP-1343,
        for a plan check that runs before the stage does).
        """
        return [e.path for e in self.entries
                if self._glob_reaches(e, path_globs, True)]

    def unknown_paths(self, path_globs: list[str]) -> list[str]:
        """The paths among ``path_globs`` that name no entry (WP-1414).

        The half of a ``set_vary`` call its return cannot carry.  ``hits``
        answers "what did this free", and an empty list is the same answer for
        a pattern that legitimately matched nothing, for a row declined as
        locked, tied or held, and for a path that does not exist.  Only the
        last is the caller's mistake, and only a literal or a retired spelling
        can be seen to make it (:func:`unknown_paths_among`), so this reports
        exactly those: a declined row *was* found, and
        ``ParameterRow.held_because`` says why.

        A question about the table's paths and nothing else, so it is asked
        separately rather than folded into ``set_vary``'s return, which a
        dozen callers read as a list of freed paths.  Order kept, repeats
        dropped.
        """
        return unknown_paths_among(path_globs, {e.path for e in self.entries})

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

    def seed_floor(self, paths: list[str], cap: dict[str, float] | None = None,
                   *, write: bool = True) -> tuple[dict[str, float], list[str]]:
        """Start each freed softplus row sitting on its floor a short way inside.

        A row is on its floor at or below :data:`SOFTPLUS_FLOOR_VALUE` (in
        column units, as :meth:`seed_softplus` reads a seed).  It is lifted to
        :data:`FLOOR_SEEDS`' value for its unit, times its value scale, or
        to half its upper bound where that is lower.  Only
        rows on the floor are touched, so a start a caller chose is never
        overwritten: issue #499 was a seed that lifted every row below it,
        the moment and the scale included.

        ``cap`` maps a path to a ceiling on its seed in column units.  A joint
        table passes it so a shared column takes one seed in every histogram,
        since each histogram's box divides by its own value scale.
        ``write=False`` returns what would be seeded and changes nothing.

        Returns ``(seeded, unseeded)``: the paths lifted with the column value
        each now starts at, and the floor rows whose unit has no seed, a
        ``.scale`` excepted.
        """
        seeded: dict[str, float] = {}
        unseeded: list[str] = []
        for path in paths:
            i = self._paths.get(path)
            if i is None:
                continue
            e = self.entries[i]
            scale = self._value_scale.get(path, 1.0)
            if e.transform != "softplus" or e.value > SOFTPLUS_FLOOR_VALUE * scale:
                continue
            seed = FLOOR_SEEDS.get(self._units.get(path))
            if seed is None:
                # a scale on its floor is a phase or curve the data cannot see,
                # which PHASE_UNCONSTRAINED reports (WP-1301); starting it
                # positive is the advice that report exists to withhold
                if not path.endswith(".scale"):
                    unseeded.append(path)
                continue
            # a box narrower than the seed takes half its own width instead
            seed = min(seed, 0.5 * e.hi / scale,
                       (cap or {}).get(path, float("inf")))
            if write:
                e.value = seed * scale
            seeded[path] = seed
        if seeded and write:
            self._rebuild()
        return seeded, unseeded

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
        reach = np.asarray(abs(self._reach).sum(axis=1)).ravel()
        return [e.path for i, e in enumerate(self.entries) if reach[i] > 0.0]

    def column_reach(self) -> dict[str, list[str]]:
        """Per free column, every entry path it moves — itself and its ties.

        :attr:`moving_paths` answers "does this entry move"; this answers
        "*which column* moves it", which is the question a freeze resting on
        flatness has to ask.  A column is a flat direction only when everything
        it reaches is flat, and the entry that is flat is rarely the one
        carrying the freedom: since WP-1119 a caller's ``vars.X`` can drive a
        phase's cell, and the only free *name* is then the variable's.

        One column-wise read of the same **C** that :attr:`moving_paths` reads
        row-wise and that ``optimize._column_extras`` reads for the Jacobian's
        own reach gate — never a second derivation, which could disagree with
        the matrix the residual is actually built from.  An explicitly stored
        zero coefficient is not reach, matching ``moving_paths``' test rather
        than the sparsity pattern, since a tie may flatten to a zero term.

        **With no tie every column reaches exactly itself**, so a consumer
        replacing a test on ``free_paths`` with a test on this is bit-identical
        on every model that declared none — which is what made it safe to apply
        unconditionally rather than behind a freeze.  Keyed and ordered by
        :attr:`free_paths`; the values are in entry order, so neither answer
        depends on how θ was assembled.
        """
        csc = self._reach.tocsc()
        out: dict[str, list[str]] = {}
        for j, path in enumerate(self.free_paths):
            sl = slice(csc.indptr[j], csc.indptr[j + 1])
            rows = csc.indices[sl][csc.data[sl] != 0.0]
            out[path] = [self.entries[i].path for i in sorted(rows)]
        return out

    def entry_reach(self) -> dict[str, list[str]]:
        """The same question asked of **every** entry, free or not.

        :meth:`column_reach` reads **C**, which has a column only for a free
        entry — so it cannot answer for one that is fixed, and a consumer that
        must give the same answer either way (a *report* about what a mode
        would force-fix, say) has nothing to ask.  This reads the declarations
        C is compiled from instead: each tied entry's flattened sources, which
        ``_flatten`` has already resolved through chains, transposed.

        **One declaration, two readings, and a test holds them equal** on every
        free path — ``column_reach()[p] == entry_reach()[p]`` there — so this
        is not a second opinion about the constraint block.  It is the wider
        one: a fixed source's dependents are still its dependents, and C simply
        has no room to say so.

        Every entry is a key, including one nothing follows, whose value is
        itself.  Ordered by entry for the same reason ``column_reach`` is.

        A source's coefficients are **summed before the zero test**, because
        ``_rebuild`` scatters them into one C entry and the sparse constructor
        sums duplicates there too.  Per term, the two readings come apart:
        ``dep = p - q`` with ``p`` and ``q`` both following one source is a
        cancelled dependency C does not carry, and ``entry_reach`` called it
        reach while ``moving_paths`` did not.
        """
        deps: dict[int, set[int]] = {}
        for i, e in enumerate(self.entries):
            if e.tie is None:
                continue
            summed: dict[int, float] = {}
            for j, coeff in self._flatten(e.tie, (e.path,))[0]:
                summed[j] = summed.get(j, 0.0) + coeff
            for j, coeff in summed.items():
                if coeff != 0.0:
                    deps.setdefault(j, set()).add(i)
        # a derived row is reached by whatever reaches one of its declared
        # inputs (the input itself, or anything the input follows), in block
        # order so a later block reading an earlier one's output chains
        for block, (ins, outs) in zip(self.derived, self._derived_idx, strict=True):
            pattern = block.reach_pattern()
            for r, out in enumerate(outs):
                for k in np.flatnonzero(pattern[r]):
                    src = int(ins[k])
                    for j in range(len(self.entries)):
                        if j == src or src in deps.get(j, ()):
                            deps.setdefault(j, set()).add(int(out))
        return {e.path: [self.entries[k].path
                         for k in sorted({i, *deps.get(i, ())})]
                for i, e in enumerate(self.entries)}

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
        if self.derived:
            p = np.array(p, dtype=np.float64)   # never write into ``_d``
            self._apply_derived(p)
        return {e.path: float(p[i]) for i, e in enumerate(self.entries)}

    def commit(self, theta: np.ndarray) -> np.ndarray | None:
        """Write refined values back into the table (used between stages).

        A moment block lands in its principal chart
        (:meth:`_canonicalise_moment_dofs`, #604), so the committed values can
        differ from ``decode(theta)`` there — the same moment, never a
        different one.  A rigid body's rotation composes (WP-1805): R₀ ←
        Exp(δω)·R₀ and δω ← 0, the same pose in a new chart; a torsion's twist
        composes by addition, φ₀ ← φ₀ + δφ and δφ ← 0 (WP-1808).

        The return says how the chart moved, for a caller still holding the
        solver's outcome to pass to
        :func:`~rietx.optimize.least_squares.rechart_outcome` with ``x0()``
        so its ``theta``, Jacobian and correlations describe these values:
        ``None`` when nothing moved; the ±1 per free column when only a
        moment flipped; all ones when only a torsion twist moved (composing
        about one axis is addition, so the chart moves by a translation); the
        square matrix ∂θ_old/∂θ_new over the free columns
        (:meth:`_chart_matrix`) when a body turned.

        A body that fails the commit-time guard (:meth:`_check_committed_bodies`)
        raises ``ValueError`` with the table as it was before the call: the
        guard can only run on the composed anchors, so the commit is undone
        rather than left half-written for a caller that catches it (#801).
        """
        values = self.decode(theta)
        if self._bodies:
            before = self._commit_state()
        for e in self.entries:
            e.value = values[e.path]
        signs = self._canonicalise_moment_dofs()
        # the moment components are locked entries fed by a *non-affine* map,
        # so the constraint block cannot carry them and they are derived here
        self._refresh_moment_components()
        charts = self._compose_bodies(values) if self._bodies else {}
        twisted = self._compose_torsions(values) if self._bodies else False
        # held-source contributions to d follow the new values, and the
        # derived rows the composed anchors
        self._rebuild()
        if self._bodies:
            try:
                self._check_committed_bodies(values)
            except ValueError:
                self._restore_commit_state(before)
                raise
        if not charts:
            if twisted and signs is None:
                # a twist composes by a translation of its chart: the outcome
                # keeps every number and takes the committed θ (WP-1808)
                return np.ones(len(self._free_idx))
            return signs
        for bbase, _, block in self._bodies:
            if bbase in charts:
                block.settle_anchor()
        self._refresh_derived()
        return self._chart_matrix(signs, charts)

    def _commit_state(self) -> tuple:
        """What :meth:`commit` changes, for :meth:`_restore_commit_state`.

        The entries' values, each body's anchor and torsion anchors (WP-1808),
        and the anchors a later :meth:`restore_body_anchors` steps back to.  An
        anchor is rebound at a commit, never written in place, so holding the
        arrays is enough.
        """
        return ([e.value for e in self.entries],
                [(b.q0, b.r0, b.axes) for _, _, b in self._bodies],
                dict(self._precommit_anchor),
                [b.phi0 for _, _, b in self._bodies],
                dict(self._precommit_torsions))

    def _restore_commit_state(self, state: tuple) -> None:
        """Put the table back as :meth:`_commit_state` found it.

        Undoes a commit this table refused (#801), or one it made inside a
        joint commit that another histogram's table refused
        (:meth:`MultiParameterTable.commit`).
        """
        old_values, anchors, precommit, phi0s, precommit_torsions = state
        self._precommit_anchor = dict(precommit)
        self._precommit_torsions = dict(precommit_torsions)
        for e, v in zip(self.entries, old_values, strict=True):
            e.value = v
        for (_, _, block), anchor, phi0 in zip(self._bodies, anchors, phi0s,
                                               strict=True):
            block.restore_anchor(*anchor)
            block.restore_torsions(phi0)
        self._rebuild()

    def _compose_bodies(self, values: Mapping[str, float]) -> dict[str, np.ndarray]:
        """R₀ ← Exp(δω)·R₀ and δω ← 0 for every body, at a commit (WP-1805).

        The record (``docs/DESIGN.md`` § Parameter system, "An anchored
        rotation composes"): every stage starts at the identity of the
        exponential map.  Returns, per body that turned, the k × k matrix
        ∂θ_old/∂θ_new of :meth:`RigidBodyBlock.commit_rotation`.  The previous
        anchor is kept for :meth:`restore_body_anchors`.
        """
        charts: dict[str, np.ndarray] = {}
        self._precommit_anchor = {}
        for bbase, _, block in self._bodies:
            paths = self._anchored_rotations[bbase]
            anchor = (block.q0, block.r0, block.axes)
            chart = block.commit_rotation([values[q] for q in paths])
            if chart is None:
                continue
            self._precommit_anchor[bbase] = anchor
            charts[bbase] = chart
            for q in paths:
                self.entries[self._paths[q]].value = 0.0
        return charts

    def _compose_torsions(self, values: Mapping[str, float]) -> bool:
        """φ₀ ← φ₀ + δφ and δφ ← 0 for every torsion, at a commit (WP-1808).

        The body's rotation rule about one axis
        (:meth:`RigidBodyBlock.commit_torsions`), where composing is addition,
        so no chart matrix: ∂θ_old/∂θ_new is the identity on the twist
        columns.  Returns whether any torsion turned; the previous anchors are
        kept for :meth:`restore_body_anchors`.
        """
        self._precommit_torsions = {}
        turned = False
        for bbase, _, block in self._bodies:
            paths = self._anchored_torsions[bbase]
            before = block.phi0.copy()
            if not block.commit_torsions([values[q] for q in paths]):
                continue
            self._precommit_torsions[bbase] = before
            turned = True
            for q in paths:
                self.entries[self._paths[q]].value = 0.0
        return turned

    def _check_committed_bodies(self, answer: Mapping[str, float]) -> None:
        """The commit-time guard: each body rigid, and where the solve put it.

        Two failures, one test each, both to 1e-9 Å.  A body that is not rigid
        in the committed cell means its anchor is not a rotation (WP-1803
        measured a stale linearised anchor at 2e-3 Å against 1e-15 Å); atoms
        that are rigid but no longer at the solver's answer mean the increment
        was zeroed without being composed.  Either way the commit would make a
        model that is not the stage's answer, so it refuses: ``ValueError``,
        the error :meth:`__init__`'s drift check raises, which :meth:`commit`
        turns into a no-op before re-raising.
        """
        from .derived import cartesian_frame

        bad = {n: e for n, e in self.body_bond_errors().items() if e > 1e-9}
        moved: dict[str, float] = {}
        for bbase, name, block in self._bodies:
            phase_base = bbase.split(".rigid_bodies.")[0]
            cell = tuple(answer[f"{phase_base}.cell.{n}"]
                         for n in ("a", "b", "c", "alpha", "beta", "gamma"))
            m = np.asarray(cartesian_frame(cell), dtype=np.float64)
            gap = np.array([self.entries[self._paths[q]].value - answer[q]
                            for q in block.outputs]).reshape(-1, 3) @ m.T
            worst = float(np.sqrt((gap * gap).sum(axis=1)).max())
            if worst > 1e-9:
                moved[name] = worst
        if bad or moved:
            raise ValueError(
                "RIGID_BODY_TEMPLATE_DRIFT at commit: "
                + (f"rigid bodies {bad} are not rigid (largest |d − d_template| "
                   "in Å)" if bad else "")
                + ("; " if bad and moved else "")
                + (f"rigid bodies {moved} left the solver's answer (largest "
                   "atom shift in Å)" if moved else ""))

    def _chart_matrix(self, signs: np.ndarray | None,
                      charts: Mapping[str, np.ndarray]) -> np.ndarray:
        """∂θ_old/∂θ_new over the free columns, for ``rechart_outcome``.

        The moment signs on the diagonal and each composed body's block on
        its rotation columns (disjoint sets).  A rotation entry is an identity
        transform, so its free column is its value or an affine image of
        another's; the block is carried through C's rows as
        pinv(A)·chart·A, A the rows of the body's rotation entries over the
        columns that reach them.  That is exact when each rotation entry is its
        own free column; a body with some rotation DOFs held or tied gets the
        projection, because composing then changes which orientations the
        held components leave reachable, and no matrix maps one family onto
        the other.
        """
        n = len(self._free_idx)
        out = np.diag(np.ones(n) if signs is None else np.asarray(signs, dtype=np.float64))
        C = self._C.toarray()
        for bbase, chart in charts.items():
            rows = [self._paths[q] for q in self._anchored_rotations[bbase]]
            a = C[rows]
            cols = np.flatnonzero(np.abs(a).sum(axis=0) > 0.0)
            if not len(cols):
                continue
            a = a[:, cols]
            out[np.ix_(cols, cols)] = np.linalg.pinv(a) @ chart @ a
        return out

    def restore_body_anchors(self, paths: Iterable[str]) -> list[str]:
        """Put back the anchor the last commit replaced, for bodies in ``paths``.

        A stage that restores a collapsed phase to the values it started from
        (``refine``'s support hold, WP-1301) sets each rotation DOF back to
        its start, zero; after a commit composed the increment that is no
        restore at all, since the turn now lives in R₀.  So the anchor is put
        back with it.  Returns the body base paths restored.
        """
        wanted = set(paths)
        done = []
        for bbase, _, block in self._bodies:
            restored = False
            if (bbase in self._precommit_anchor
                    and wanted & set(self._anchored_rotations[bbase])):
                block.restore_anchor(*self._precommit_anchor.pop(bbase))
                restored = True
            # a torsion's twist is the same kind (WP-1808): each one restored
            # gets its own anchor back, the others keep what the commit made
            if bbase in self._precommit_torsions:
                phi0 = block.phi0.copy()
                old = self._precommit_torsions[bbase]
                for t, q in enumerate(self._anchored_torsions[bbase]):
                    if q in wanted:
                        phi0[t] = old[t]
                        restored = True
                block.restore_torsions(phi0)
            if restored:
                done.append(bbase)
        if done:
            self._refresh_derived()
        return done

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
        # C itself without a derived block; with one, each derived row is the
        # block's local Jacobian at θ chained through its inputs (WP-1804)
        jac = self.local_jacobian(theta)
        if correlation is None:
            # stays on the diagonal *vector*: this branch is the cheap one, and
            # a Pawley table's dense n×n would be tens of MB for a number that
            # never leaves the diagonal
            s = self._sigma_free_measured(theta, stderr_internal)
            with np.errstate(over="ignore", invalid="ignore"):
                var = np.asarray(jac.multiply(jac) @ (s * s)).ravel()
        else:
            cov = self._cov_free(theta, stderr_internal, correlation)
            with np.errstate(over="ignore", invalid="ignore"):
                var = np.asarray(jac.multiply(jac @ cov).sum(axis=1)).ravel()
        var = np.maximum(var, 0.0)
        # rows with any free source, read off the declared reach: a derived
        # row whose Jacobian is zero at this θ still has its sources
        touched = np.diff(self._reach.indptr) > 0
        # a propagated variance past the double range is an infinite one, and
        # absent for the same reason (WP-1463; ``_phys_sigma_free``)
        blind = self.unmeasured_rows(theta, stderr_internal) | ~np.isfinite(var)
        return {e.path: float(np.sqrt(var[i]))
                for i, e in enumerate(self.entries) if touched[i] and not blind[i]}

    def _phys_sigma_free(self, theta: np.ndarray, stderr_internal: np.ndarray
                         ) -> np.ndarray:
        """Chain-ruled physical esd of each free parameter (θ-column order).

        **An esd whose variance has no double is returned as ``inf``**, the
        value every consumer already reads as unmeasured (WP-1463).  Since the
        covariance takes a tiny column's esd without forming its variance, a
        free cell of a phase whose scale sits at 1e-160 comes back with an esd
        near 1e+160 Å.  Squared in :meth:`_cov_free` that is ``inf`` again, and
        a row would then report an infinite esd where WP-1072 wants an absent
        one.  Nothing measured sits within a hundred orders of this cap.
        """
        with np.errstate(invalid="ignore", over="ignore"):
            s = np.array(
                [abs(dphys_dinternal(float(t), self.entries[i].transform)) * float(sd)
                 for t, sd, i in zip(theta, stderr_internal, self._free_idx,
                                     strict=True)],
                dtype=np.float64)
        return np.where(np.isnan(s) | (s < _SIGMA_MAX), s, np.inf)

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
        c = self._reach if rows is None else self._reach[rows, :]
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
        c_rows = self.local_jacobian(theta)[rows, :].toarray()
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
        self._refresh_moment_components()
        self._refresh_derived()
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
            if phase.magnetic_symmetry is not None:
                put(phase.magnetic_lor_size, f"{base}.magnetic_lor_size")
                put(phase.magnetic_lor_strain, f"{base}.magnetic_lor_strain")
            if phase.microstrain is not None:
                for name in S_NAMES:
                    put(getattr(phase.microstrain, name), f"{base}.microstrain.{name}")
            for b, body in enumerate(phase.rigid_bodies):
                for c in ("x", "y", "z"):
                    put(getattr(body.origin, c), f"{base}.rigid_bodies.{b}.origin.{c}")
            for j, atom in enumerate(phase.atoms):
                # coordinates too — without this, refined positions vanish at
                # the next stage's recompile (models feed compile_phase_sites)
                for name in ("x", "y", "z", "occ", "biso"):
                    put(getattr(atom, name), f"{base}.atoms.{j}.{name}")
                if atom.aniso is not None:
                    for name in U_NAMES:
                        put(getattr(atom.aniso, name), f"{base}.atoms.{j}.{name}")
                if atom.moment is not None:
                    # derived from the DOFs above, never refined directly; the
                    # esd map has no entry for them, so ``stderr`` is cleared
                    # rather than left holding a previous stage's number
                    for name in MOMENT_COMPONENTS:
                        put(getattr(atom.moment, name),
                            f"{base}.atoms.{j}.moment.{name}")
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
        # a body's orientation record: R₀ as the commit composed it, which is
        # the record itself, since a commit leaves δω = 0 (WP-1805).  A value
        # set by hand and not committed (``set_values``, a series carry) is a
        # pose Exp(δω)·R₀ not yet composed, written as the pose it describes
        for bbase, _, block in self._bodies:
            ip, b = (int(t) for t in bbase.split(".")[1::2][:2])
            q = block.orientation([values[p] for p in self._anchored_rotations[bbase]])
            structure.phases[ip].rigid_bodies[b].orientation = tuple(
                float(v) for v in np.asarray(q))
            # its torsions' records the same way (WP-1808): φ₀ + δφ, which is
            # φ₀ wherever a commit left δφ = 0
            angles = block.angles([values[p] for p in self._anchored_torsions[bbase]])
            for torsion, angle in zip(structure.phases[ip].rigid_bodies[b].torsions,
                                      angles, strict=True):
                torsion.angle = float(angle)
