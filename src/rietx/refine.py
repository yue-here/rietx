"""The public refinement API: :class:`Refinement` and :func:`refine`."""

from __future__ import annotations

import dataclasses
import fnmatch
import math
import re
import warnings
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .io.exporters import ReflectionRow
    from .schemas.suggest import SuggestionResult

from . import runs
from ._about import DIST_NAME
from ._nearmiss import did_you_mean
from .backend.api import backend_dtype_note
from .background.diagnostics import (
    STEPS_PER_FWHM_MIN,
    _dead_interval,
    dead_channels,
    sampling_steps_per_fwhm,
)
from .help import help_key_for
from .history.events import _attach_progress, as_event_stream
from .history.store import fingerprint
from .history.tree import RefinementTree
from .model.absorption import (
    CYLINDER_MU_R_MAX,
    equivalent_delta_biso,
    equivalent_delta_biso_from_transmission,
    mu_t_identifiable_fraction,
    transmission_intensity_fraction,
)
from .model.components import EXTRA_TICK_KEY
from .model.forward import (
    PHASE_SUPPORT_SIGMA,
    CompiledModel,
    Mode,
    compile_model,
)
from .model.geometry import geometry_table
from .model.microstructure import microstructure_table
from .model.profiles.caglioti import (
    SCHERRER_K,
    apparent_size_from_size_coefficient,
    gaussian_fwhm,
    lorentzian_fwhm,
)
from .model.restraints import summarise_restraints
from .optimize.cancel import RefinementCancelled
from .optimize.least_squares import (
    SOLVERS,
    _longest_line_wavelength,
    run_least_squares,
)
from .optimize.qpa import (
    compute_qpa,
    estimate_capillary_mu_r,
    estimate_flat_plate_mu_t,
    microabsorption_diagnostics,
)
from .optimize.statistics import (
    OBS_PER_PARAMETER_MIN,
    OBS_PER_PARAMETER_PREFERRED,
    berar_lelann_factor,
    compute_statistics,
    data_support,
    structure_r_factors,
)
from .params.vector import (
    CELL_SAFETY_ANGLE_DEG,
    CELL_SAFETY_FRACTION,
    VAR_PREFIX,
    AffineTie,
    ParameterTable,
    _cell_parameter_name,
    _is_wavelength,
    cell_window,
    is_literal_path,
    is_variable_path,
)
from .report.schemas import THRESHOLDS_VERSION, FitReport, StageReport
from .schemas.common import Diagnostic, Parameter, Provenance
from .schemas.history import NodeAction, NodeMetrics, RefinementState, ReflectionState
from .schemas.instrument import CAPILLARY_OFFSETS, Instrument
from .schemas.params import ParameterRow, TieSpec
from .schemas.pattern import PatternData
from .schemas.results import (
    DELIVERABLES,
    AbsorptionCorrection,
    Identifiability,
    PhaseAgreement,
    RefinedParameter,
    RefinementResult,
    StageResult,
    _agreement_line,
    _diagnostic_lines,
    _provenance_line,
    _stage_lines,
)
from .schemas.structure import Structure
from .strategy.staged import (
    PLAN_PRESETS,
    RefinementPlan,
    Stage,
    check_guards,
    resolve_plan,
)

#: What gets stamped when the distribution cannot be found.  It is not a
#: cosmetic string: ``_VERSION`` reaches every ``RefinementResult.provenance``,
#: every ``TreeHeader`` in every ``history.jsonl``, every ``project.json`` and
#: ``/api/capabilities``, so a silent fallback mislabels the provenance of real
#: results rather than merely reading oddly.
_DEV_VERSION = "0.0.0+dev"

try:
    _VERSION = version(DIST_NAME)
except PackageNotFoundError:  # a source tree on sys.path, or a stale install
    # loud on purpose (WP-1062).  Asking for the *wrong* name is a successful
    # lookup of nothing: nothing raises, and no audit for a stale name can
    # catch it either, because nothing stale is left behind.  The rename's own
    # reinstall window is exactly this — the package directory moves and
    # ``import`` keeps working while the dist-info still holds the old name.
    warnings.warn(
        f"no installed distribution named {DIST_NAME!r}: results will be "
        f"stamped {_DEV_VERSION!r} instead of a real version.  Reinstall "
        f'(uv pip install -e ".[dev]") if this is a checkout.',
        RuntimeWarning, stacklevel=2)
    _VERSION = _DEV_VERSION

def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def mode_fixed_path(path: str, mode: Mode) -> bool:
    """Whether ``mode`` force-fixes ``path`` whatever the table says.

    Against an intensity model that partitions or refines the per-hkl
    intensities, three families of parameter cannot be refined at all: the
    structural parameters (there is no |F|² to fit), the phase scale (degenerate
    with those intensities) and the emission-line weights (which the intensities
    absorb pairwise).  ``_run_stage`` drops them from the freed set; exported
    once so :meth:`Refinement.parameters` reports the same set rather than a
    second opinion about it.
    """
    if mode not in ("lebail", "pawley"):
        return False
    # The scale test is anchored at ``phases.``, not left as a bare suffix.
    # Since WP-1119 a caller's own ``add_variable("scale", …)`` produces
    # ``vars.scale``, which the suffix alone force-fixed — a variable held in
    # Le Bail and Pawley for spelling its name like a phase parameter — and
    # since WP-1309 ``instrument.background.scale`` is the second such path.
    # That one must stay free here: a measured background is scaled against the
    # data, and Le Bail extracts intensities rather than absorbing a background
    # level.
    return (".atoms." in path
            or (path.startswith("phases.") and path.endswith(".scale"))
            or ".source.lines." in path)


def mode_fixed_column(reached: list[str], mode: Mode) -> bool:
    """Whether ``mode`` force-fixes every model path this column moves.

    :func:`mode_fixed_path` one rank up, and the same repair
    :func:`_only_moves` is for the phase freeze (WP-1342): the drop was a test
    on the free path's **name**, so a caller's ``vars.B`` driving an atom's
    ``biso`` was not force-fixed and entered θ as a column Le Bail has no |F|²
    to fit — a dead direction carrying a value and an esd that read as
    measurements.  Measured on LaB₆: freeing ``vars.*`` in ``lebail`` put
    ``vars.B`` in the freed set and moved the atom's ``biso`` 0.5 → 0.7, where
    freeing the ``biso`` glob itself freed nothing.

    **All, never any**, for the flatness reason again: a column driving one
    force-fixed path and one live parameter has gradient through the live one,
    and fixing it would freeze that too.  Variables are dropped before the
    test, being entries the forward model never reads.
    """
    moved = [p for p in reached if not is_variable_path(p)]
    return bool(moved) and all(mode_fixed_path(p, mode) for p in moved)


@dataclasses.dataclass(frozen=True)
class _StageHold:
    """What one stage held, and what it let go again (WP-1301).

    Carried out of ``_run_stage`` rather than read back off the table, because
    by then the release has already put the freed paths back and the table can
    no longer tell the two apart.

    ``blocked_by_hold`` rides here for delivery rather than for that reason
    (WP-1435).  It is the caller's declaration, decided before the solve and
    unchanged by it, and it travels this way because the two ``StageResult``
    call sites already unpack this object.
    """

    held: list[str]
    released: list[str]
    #: what each held *column* also stopped (WP-1342), readable only while the
    #: column is still in θ — so it travels with the rest rather than being
    #: asked of the table afterwards, for this carrier's own reason.
    reach: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    blocked_by_hold: list[str] = dataclasses.field(default_factory=list)
    #: the literal ``turn_on`` paths naming no entry (WP-1414), riding here
    #: for ``blocked_by_hold``'s reason: decided before the solve, unchanged
    #: by it, and delivered to the two ``StageResult`` call sites this way
    unknown_paths: list[str] = dataclasses.field(default_factory=list)
    #: ``(path, escaped_value, clamped_value)`` for every free cell parameter
    #: ``clamp_cell_runaway`` pulled back this stage — empty on every stage
    #: that never leaves the safety window, which is every stage measured so
    #: far (WP-1110's own 51-transition survey).
    cell_runaway: list[tuple[str, float, float]] = dataclasses.field(
        default_factory=list)
    #: ``(driver_path, [escaped_dependent_paths])`` per ``vars.*`` column
    #: :func:`_vars_driven_cell_escapes` found driving a cell outside the
    #: safety window this stage — named, never clamped (review of #385
    #: finding 1).  Empty whenever :attr:`cell_runaway` is, and on every
    #: stage this package's own suite runs outside this file's own fixture.
    cell_runaway_unresolved: list[tuple[str, list[str]]] = dataclasses.field(
        default_factory=list)


def _tie_terms(source: "str | dict[str, float] | Sequence[tuple[str, float]]",
               scale: float) -> list[tuple[str, float]]:
    """Normalise ``tie``'s ``source`` to ``(path, coefficient)`` pairs.

    One source, a mapping or a pair sequence all become the same list, so the
    single-source spelling is the one-entry case rather than its own branch.
    ``scale`` multiplies every term: on one source that is its documented
    meaning, and on several it is the only reading under which the two
    spellings agree.
    """
    if isinstance(source, str):
        return [(source, scale)]
    if isinstance(source, dict):
        pairs = list(source.items())
    else:
        # checked as a *shape*, not destructured: ``["a.b", "c.d"]`` is the
        # natural mistake here (``tie`` takes a bare path too), and unpacking it
        # would silently read a two-character path as (path, coefficient) and
        # fail two lines later on ``float('b')``
        pairs = []
        for term in source:
            if isinstance(term, str) or len(tuple(term)) != 2:
                raise ValueError(
                    f"a tie term is a (path, coefficient) pair; got {term!r}. "
                    "Pass one path, a {path: coefficient} dict, or a list of "
                    "(path, coefficient) pairs")
            pairs.append(tuple(term))
    if not pairs:
        raise ValueError("a tie needs at least one source")
    seen: dict[str, float] = {}
    for path, coeff in pairs:
        if not isinstance(path, str):
            raise ValueError(
                f"a tie source is a dot-path; got {path!r}. Pass one path, a "
                "{path: coefficient} dict, or a list of (path, coefficient) pairs")
        if path in seen:
            raise ValueError(
                f"{path!r} appears twice in one tie; sum the coefficients "
                "instead, so the tie says what it means")
        seen[path] = float(coeff)
    return [(path, scale * coeff) for path, coeff in seen.items()]


#: ``phases.i.atoms.j.moment.dof<k>`` — the moment block's own DOF paths.
_MOMENT_DOF = re.compile(r"^phases\.\d+\.atoms\.\d+\.moment\.dof\d+$")


def _unsupported_phase_paths(model: CompiledModel, table: ParameterTable,
                             support: np.ndarray | None = None) -> list[str]:
    """The free columns that move nothing but phases the data cannot see.

    **Columns, never names** (WP-1342).  This filtered ``free_paths`` by
    ``phases.{ip}.`` until a caller's ``vars.X`` could drive a phase's cell
    (WP-1119), at which point the only free *name* was the variable's, the
    prefix matched nothing, and the freeze reported that it had done its job on
    a set it could not see into — the class this repo's rules are strictest
    about.  ``ParameterTable.column_reach`` is the question restated as what a
    column *moves*; :func:`_only_moves` is the decision over it.

    "Cannot see" is ``CompiledModel.phase_support`` below
    :data:`~rietx.model.forward.PHASE_SUPPORT_SIGMA` — the one authority, shared
    with the ``PHASE_UNCONSTRAINED`` diagnostic and the default cell window, and
    read here at the values the stage *starts* from like every other per-stage
    freeze.

    **The phase's own scale is never held.**  Every structural parameter of a
    phase reaches the pattern only through ``scale × |F|² × profile``, so with
    the scale at its floor they are all flat — but the scale itself is the one
    direction that is *not* flat, and it is how a phase legitimately climbs out
    of the noise.  Holding it would make the hold permanent, which is the one
    outcome this must never have.

    Every currently free structural path, not only the ones this stage turned
    on: staging is cumulative, so a cell freed two stages ago is still refining
    against nothing, and the ``refit="single"`` collapse — one stage carrying
    the whole plan — is exactly the shape the ramp that motivated this ran.

    ``support`` is the ``phase_support`` vector when a caller has already
    measured it at these values (the post-solve pass asks two questions of one
    measurement); ``None`` measures it here.
    """
    if support is None:
        support = model.phase_support(table.decode(table.x0()))
    absent = {ip for ip, s in enumerate(support)
              if s < PHASE_SUPPORT_SIGMA}
    if not absent:
        return []
    prefixes = tuple(f"phases.{ip}." for ip in sorted(absent))
    reach = table.column_reach()
    return [p for p in table.free_paths
            if _only_moves(reach.get(p, [p]), prefixes)]


#: A moment direction whose calculated-pattern response is this far below the
#: modulus's measures nothing, and is held (WP-1327).
#:
#: **Measured, not chosen.**  On the cubic collinear test structure — where the
#: orbit-averaged intensity is provably independent of the moment direction —
#: the two angle DOFs respond at ~1e-15 of the modulus's response for the
#: finite rotation below, which is roundoff.  On Cr₂WO₆ at 4 K under BNS
#: 58.395, where the in-plane angle *is* determined, the same probe reads
#: ~1e0.  Fifteen orders of magnitude separate the two, so the floor sits in
#: the middle of the gap rather than at the edge of either.
#:
#: This exists because the package's other "measured nothing" mechanism
#: (:meth:`ParameterTable.unmeasured_free`, through
#: ``optimize.statistics.normal_covariance``) fires only on a column with **no
#: gradient at all** — ``d > 0.0`` — and an analytically flat direction is not
#: bitwise flat.  Widening that test to a relative one would change the esd of
#: every fit in the package; holding the moment block's own flat directions
#: changes nothing outside it.
MOMENT_DIRECTION_SUPPORT = 1e-6

#: **A finite rotation, and that is the whole point.**  0.1 rad ≈ 5.7°.
#:
#: A derivative-scale step (1e-6) does not answer the question this probe is
#: asking.  The intensity as a function of a moment's azimuth is *stationary*
#: at every direction the symmetry fixes, so its first derivative vanishes
#: there even when the angle is perfectly well determined — measured on
#: Cr₂WO₆ at 4 K, where a 1e-6 step reads 5e-7 of the modulus's response with
#: the moment along **a** and 1e0 with it at 45° to a.  A first-derivative
#: probe would have held a determined direction sitting at its own optimum and
#: reported it as something the powder could not see, which is the one thing
#: this rung must not do.  A finite rotation reads the *curvature* as well, so
#: "flat here" and "flat everywhere" stop looking alike.
#:
#: The modulus is probed by the displacement the same rotation produces —
#: μ → μ + 0.1·|μ| — so the ratio is "does moving the moment sideways matter,
#: compared to moving it lengthwise by as much".
MOMENT_PROBE_ANGLE_RAD = 0.1

#: Purity cut (issue #278) deciding which of a magnetic phase's reflections
#: draw on the nuclear tick row and which on its own "(magnetic)" row, by the
#: magnetic fraction p²⟨|F_⊥|²⟩ / (⟨|F_N|²⟩ + p²⟨|F_⊥|²⟩): a reflection at or
#: above ``1 - MAGNETIC_TICK_PURITY`` is magnetic, at or below it is nuclear,
#: and one in between draws on **neither** row rather than picking a side
#: arbitrarily.  ``CompiledPhase.nuclear_mask`` alone is not enough: it is
#: exact for a k = 0 magnetic space group's own absences, but on a k != 0
#: supercell the strongest magnetic reflections sit in the child group's own
#: reflection list with the mask at 1.0 and an identically-zero ⟨|F_N|²⟩ (the
#: nuclear atoms still carry the parent's translation) — a classifier reading
#: the mask alone would draw those on the nuclear row.
MAGNETIC_TICK_PURITY = 0.05


def _flat_moment_paths(model: CompiledModel, table: ParameterTable,
                       candidates: list[str] | None = None) -> list[str]:
    """Moment **direction** DOFs the calculated pattern does not respond to.

    The rule WP-1327 takes from WP-1301, one object down: a direction the data
    cannot see is a flat direction, and holding it is cheaper and truer than
    letting it wander into a number with an esd.  What a powder cannot see of
    a moment is Shirane's (1959) result — a cubic collinear structure's
    direction entirely, a uniaxial one's azimuth — and it is *measured* here
    rather than derived from the symmetry, so a structure the classification
    does not anticipate is handled by the same rule.

    **The modulus is never held.**  It is the one direction that is not flat,
    and it is how a moment legitimately climbs out of the noise — exactly the
    argument that keeps a phase's own ``scale`` out of
    :func:`_unsupported_phase_paths`.  A modulus sitting at its floor makes
    every direction flat (|F_m|² ∝ m²), so the probe holds them all without
    needing a special case for it; what the *report* says about the modulus
    there is ``MomentEvidence.supported``.

    ``candidates`` defaults to the free paths.  Passing a held list asks the
    opposite question — which of these could now move — because the probe
    perturbs the decoded value dict directly rather than θ, and a moment DOF
    has no tie, so a held path is perturbable exactly as a free one is.
    """
    paths = [p for p in (table.free_paths if candidates is None else candidates)
             if _MOMENT_DOF.match(p) and not p.endswith(".dof0")]
    if not paths:
        return []
    values = table.decode(table.x0())
    y0 = np.asarray(model.evaluate(values), dtype=np.float64)

    def response(path: str, step: float) -> float:
        v = dict(values)
        v[path] = values[path] + step
        return float(np.linalg.norm(
            np.asarray(model.evaluate(v), dtype=np.float64) - y0))

    flat: list[str] = []
    for path in paths:
        modulus = path.rsplit(".dof", 1)[0] + ".dof0"
        mu = abs(values[modulus])
        # the same tip displacement both ways: a rotation by δφ moves the
        # moment by |μ|·δφ, so the modulus is probed by exactly that much
        scale = response(modulus, MOMENT_PROBE_ANGLE_RAD * max(mu, 1e-6))
        if scale <= 0.0 or response(path, MOMENT_PROBE_ANGLE_RAD) <= (
                MOMENT_DIRECTION_SUPPORT * scale):
            flat.append(path)
    return flat


def _hold_flat_moments(model: CompiledModel, table: ParameterTable) -> list[str]:
    """Apply :func:`_flat_moment_paths` to the table; returns what it held."""
    held = _flat_moment_paths(model, table)
    if held:
        table.set_vary(held, False)
    return held


def _only_moves(reached: list[str], prefixes: tuple[str, ...]) -> bool:
    """Whether a column moves nothing but structural paths of these phases.

    **The rule is "all", never "any"**, and it is the flatness argument rather
    than a preference.  A column driving two phases' cells through one
    ``vars.X`` (WP-1119) has real gradient wherever *either* phase is visible,
    so it is not a flat direction and holding it would freeze something the
    data can see: measured on the two-phase fixture, holding a shared column
    left the present phase's cell at its 4.20 Å seed — 10 441 ppm from the
    truth, Rwp 0.9589 — against 4.156594 Å at −1 ppm and Rwp 0.0416 free.

    The phase's own ``scale`` excludes a column the same way and for
    :func:`_unsupported_phase_paths`' reason: it is the one direction that is
    not flat, and the only way a phase climbs back out of the noise.  Under a
    reach test that needs no special case beyond naming it — a column moving
    ``phases.1.scale`` moves something the data can see, exactly as one moving
    a supported phase's cell does.

    **A variable is not a model parameter**, so it is dropped before the test
    rather than answered about.  A column's own entry is in its reach, and a
    caller's ``vars.X`` is an entry the forward model never reads — it reaches
    the pattern only through what it drives, which is the whole point of the
    namespace (:func:`~rietx.params.vector.is_variable_path`, the one authority
    for that distinction).  Left in, every tied column failed the test on its
    own name and nothing was ever held.

    A column left with no model path at all is **not** held: it moves nothing
    the data could see either way, so it is not a flat direction *of a phase*,
    and ``all()`` over nothing would hold it on a vacuous truth.
    """
    moved = [p for p in reached if not is_variable_path(p)]
    return bool(moved) and all(
        p.startswith(prefixes) and not p.endswith(".scale") for p in moved)


def _reach_beyond_self(table: ParameterTable,
                       columns: list[str]) -> dict[str, list[str]]:
    """Per column, the entries it moves other than itself (WP-1342).

    The record half of a hold, and it must be read **before** ``set_vary``
    takes the column out of θ: a held column is no longer a column, so its
    reach is no longer a question the table can answer.

    Columns reaching only themselves are left out rather than mapped to an
    empty list, so the answer is the paths a reader could not have derived
    from :attr:`~rietx.schemas.results.StageResult.held` alone.
    """
    if not columns:
        return {}
    reach = table.column_reach()
    out = {}
    for c in columns:
        other = [p for p in reach.get(c, [c]) if p != c]
        if other:
            out[c] = other
    return out


def _hold_unsupported_phases(model: CompiledModel, table: ParameterTable
                             ) -> tuple[list[str], dict[str, list[str]]]:
    """Apply :func:`_unsupported_phase_paths`; returns what it held and its reach.

    Both halves, because the reach is only readable while the columns are
    still free — see :func:`_reach_beyond_self`.
    """
    held = _unsupported_phase_paths(model, table)
    reach = _reach_beyond_self(table, held)
    if held:
        table.set_vary(held, False)
    return held, reach


def clamp_cell_runaway(table: ParameterTable, start_values: dict[str, float]
                       ) -> list[tuple[str, float, float]]:
    """Pull every free cell parameter back inside ``CELL_SAFETY_FRACTION`` /
    ``CELL_SAFETY_ANGLE_DEG`` of ``start_values`` — the stage's own — and
    report what it pulled back, as ``(path, escaped_value, clamped_value)``.

    Call this **after** ``table.commit(outcome.theta)``, on the committed
    ``Entry.value``\\ s, never as a bound the solver sees — that is the whole
    design (:data:`~rietx.params.vector.CELL_SAFETY_FRACTION`'s docstring):
    ``cell_window``'s own support-based window is deliberately restricted to
    phases ``phase_support`` judges invisible, because a live bound changes
    scipy TRF's trust-region step scaling even where it is never hit,
    measurably costing iterations and pinned digits on a phase that was never
    going to run away.  A phase judged **visible** the whole time (the trigger
    case: two free phases sharing a near-identical cell, one at full scale)
    is exactly what that window cannot reach, so this checks the *outcome*
    unconditionally instead — bit-identical for every fit whose cell never
    leaves the window (every one measured in WP-1110's own 51-transition
    survey), and a correction rather than a crash for one that does.

    Symmetry-derived cell parameters (``b``/``c`` tied to ``a`` on a cubic
    cell, etc.) are not in ``table.free_paths`` and are not visited here —
    :meth:`~rietx.params.vector.ParameterTable.refresh_ties` (called by the
    caller, exactly as the WP-1301 collapse-restore beside this call already
    does) re-derives them off the clamped source.

    **A cell driven by a caller's free ``vars.X`` is a different case, and
    this function deliberately does not touch it** (review of #385 finding
    1).  ``e.path not in free`` below tests the free path's own *name*, the
    same construction :func:`_unsupported_phase_paths` and
    :func:`_reach_beyond_self` already had to repair for WP-1342: a cell tied
    to a free variable is not itself a free column (so the loop never visits
    its entry) and the variable's own name is not a cell name either, so
    testing names alone leaves it invisible twice over.  A single clamp target
    would not even be the right fix if it were visible — a variable driving
    two cells has no one path to pull back without moving the other — so the
    escape is *named*, never silently passed through, by
    :func:`_vars_driven_cell_escapes` beside this function, which the caller
    folds into the same ``CELL_RUNAWAY`` diagnostic.
    """
    clamped: list[tuple[str, float, float]] = []
    free = set(table.free_paths)
    for e in table.entries:
        if e.path not in free:
            continue
        cell_name = _cell_parameter_name(e.path, phases=None)
        if cell_name is None:
            continue
        start = start_values.get(e.path)
        if start is None or not math.isfinite(start):
            continue
        lo, hi = cell_window(cell_name, start, -math.inf, math.inf,
                             path=e.path, fraction=CELL_SAFETY_FRACTION,
                             angle_deg=CELL_SAFETY_ANGLE_DEG)
        if not (lo <= e.value <= hi):
            target = min(max(e.value, lo), hi)
            clamped.append((e.path, float(e.value), float(target)))
            e.value = target
    return clamped


def _vars_driven_cell_escapes(table: ParameterTable,
                              start_values: dict[str, float]
                              ) -> list[tuple[str, list[str]]]:
    """Cell parameters a free ``vars.X`` drives outside the safety window —
    named, never clamped (review of #385 finding 1).

    :func:`clamp_cell_runaway` tests a free entry's own path against a cell
    name, so a cell tied to a free ``vars.X`` is invisible to it: the cell is
    not a free column (it is that column's dependent) and the free column's
    own name is the variable's, not a cell's.  This asks the other question
    instead — **columns, never names**, :func:`_unsupported_phase_paths`'s
    repair for the identical construction (refine.py's own docstring on the
    ``moving_paths``-vs-``free_paths`` split names this file) — by reading
    :meth:`~rietx.params.vector.ParameterTable.column_reach`, which answers
    what a column *moves* rather than what it is called.

    **Never clamped, by design, not merely by omission.**  A variable driving
    one cell has a single target and pulling it back would still move
    whatever else that variable drives; a variable driving several has no
    single target at all.  Either way, deciding which of the driver's other
    directions may move is the caller's physics, not a post-solve safety
    net's — so this only reports, and the report names the driver *and* every
    escaped dependent, never the driver alone (a reader must be able to find
    what it drove without re-deriving ``column_reach`` themselves).

    Returns ``(driver_path, [escaped_dependent_paths])`` per ``vars.*``
    column with at least one escaped dependent — empty on every stage where
    no variable drives a cell outside the window, which is every stage this
    package's own suite runs outside this file's own fixture.
    """
    by_path = {e.path: e for e in table.entries}
    reach = table.column_reach()
    out: list[tuple[str, list[str]]] = []
    for column in table.free_paths:
        if not is_variable_path(column):
            continue
        escaped: list[str] = []
        for dependent in reach.get(column, []):
            if dependent == column:
                continue
            cell_name = _cell_parameter_name(dependent, phases=None)
            if cell_name is None:
                continue
            e = by_path[dependent]
            start = start_values.get(dependent)
            if start is None or not math.isfinite(start):
                continue
            lo, hi = cell_window(cell_name, start, -math.inf, math.inf,
                                 path=dependent, fraction=CELL_SAFETY_FRACTION,
                                 angle_deg=CELL_SAFETY_ANGLE_DEG)
            if not (lo <= e.value <= hi):
                escaped.append(dependent)
        if escaped:
            out.append((column, escaped))
    return out


def _cell_runaway_withheld(table: ParameterTable,
                           named: Iterable[str]) -> set[str]:
    """The paths whose esd a result withholds, given the paths one stage's
    ``CELL_RUNAWAY`` finding names (its ``where``).

    Every cell path named, and every entry tied to one of them, transitively:
    a tie inherits its source's blindness (root CLAUDE.md, the covariance
    clause), so a cubic ``b``/``c`` following a withheld ``a`` cannot report
    the esd ``a`` lost.  A ``vars.X`` driver the finding names is not a cell
    and keeps its esd; the cells it drives are named themselves.  Which
    stage's finding is the caller's to decide (:func:`_build_result`).
    """
    withheld = {p for p in named if _cell_parameter_name(p, phases=None) is not None}
    grew = bool(withheld)
    while grew:
        grew = False
        for e in table.entries:
            if (e.tie is not None and e.path not in withheld
                    and any(src in withheld for src, _ in e.tie.terms)):
                withheld.add(e.path)
                grew = True
    return withheld


#: An angle path's name (``_cell_parameter_name``'s output), the same test
#: :func:`~rietx.params.vector.cell_window` branches on -- ``alpha``/``beta``/
#: ``gamma`` are clamped by ``CELL_SAFETY_ANGLE_DEG`` (degrees, absolute),
#: never ``CELL_SAFETY_FRACTION`` (a fraction of Å), so a message built for
#: one and printed for the other names the wrong unit and the wrong window.
_ANGLE_CELL_NAMES = ("alpha", "beta", "gamma")


def _cell_runaway_diagnostic(
        cell_runaway: list[tuple[str, float, float]],
        unresolved: list[tuple[str, list[str]]] | None = None,
        ) -> Diagnostic | None:
    """``CELL_RUNAWAY`` for one stage's :func:`clamp_cell_runaway` and
    :func:`_vars_driven_cell_escapes` findings, or ``None`` when neither
    found anything (the overwhelming majority of stages, including every
    one this package's own suite runs).

    ``unresolved`` never says "pulled back" — the whole point of review of
    #385 finding 1 is that a ``vars.X``-driven escape is *not* clamped, so
    the sentence for it says what happened instead: the driver and every
    escaped dependent are named, and why nothing moved.  A stage that fires
    both is one message, not two, since a reader tracing one ``CELL_RUNAWAY``
    code should not have to reassemble it from two diagnostics that differ
    only in which clause fired.
    """
    unresolved = unresolved or []
    if not cell_runaway and not unresolved:
        return None

    def is_angle(path: str) -> bool:
        return _cell_parameter_name(path, phases=None) in _ANGLE_CELL_NAMES

    paths = [p for p, _, _ in cell_runaway]
    for driver, escaped in unresolved:
        paths.append(driver)
        paths.extend(escaped)

    sentences = []
    value = None
    if cell_runaway:
        worst = max(cell_runaway, key=lambda t: abs(t[1] - t[2]))
        value = abs(worst[1] - worst[2])
        detail = "; ".join(
            f"{p} {old:.6g} -> {new:.6g} {'°' if is_angle(p) else 'Å'}"
            for p, old, new in cell_runaway)
        has_length = any(not is_angle(p) for p, _, _ in cell_runaway)
        has_angle = any(is_angle(p) for p, _, _ in cell_runaway)
        if has_length and has_angle:
            window_clause = (f"±{CELL_SAFETY_FRACTION:.0%} (a/b/c) or "
                             f"±{CELL_SAFETY_ANGLE_DEG:.0f}° (α/β/γ)")
        elif has_angle:
            window_clause = f"±{CELL_SAFETY_ANGLE_DEG:.0f}°"
        else:
            window_clause = f"±{CELL_SAFETY_FRACTION:.0%}"
        sentences.append(
            f"{len(cell_runaway)} free cell parameter"
            f"{'' if len(cell_runaway) == 1 else 's'} left "
            f"{window_clause} of this stage's starting cell "
            f"during solving and {'was' if len(cell_runaway) == 1 else 'were'} "
            f"pulled back to the window edge rather than left to reach "
            f"an unphysical value: {detail}")
    if unresolved:
        driver_detail = "; ".join(
            f"{driver} drives {', '.join(escaped)} outside its window"
            for driver, escaped in unresolved)
        sentences.append(
            f"{driver_detail}, and {'was' if len(unresolved) == 1 else 'were'} "
            f"not pulled back: a variable driving a cell has no single "
            f"clamp target, and clamping the driver would move every other "
            f"value it also reaches, so this is reported rather than "
            f"corrected")
    return Diagnostic(
        level="warning", code="CELL_RUNAWAY", where=paths, value=value,
        message=". ".join(sentences),
        suggestion=(
            "a value this diagnostic names is not a measurement: this "
            "phase's own cell is degenerate with another free phase's, "
            "with another free parameter, or with the variable driving it, "
            "along this direction; fix one phase's cell, hold the other "
            "free phase, or free the cell in its own stage away from the "
            "degenerate pairing"),
    )


def _released_phases(model: CompiledModel, table: ParameterTable,
                     held: list[str], support: np.ndarray | None = None,
                     reach: dict[str, list[str]] | None = None) -> list[str]:
    """Of ``held``, the columns whose phase has risen above support since.

    Measured at the values the solve *landed* on, against the same threshold
    the hold was taken at — a phase whose scale climbed while the stage ran is
    now one the data can see, and its parameters are measurable in this stage
    rather than the next one.

    **Columns, never names**, the other half of :func:`_unsupported_phase_paths`
    and the same repair: a held column may be a caller's ``vars.X``, whose own
    name carries no phase, so the phase is looked for in what the column
    *moved* as well.  ``reach`` is the hold's own record, read while the column
    was still in θ (:func:`_reach_beyond_self`) — read again here it would be
    empty, the column no longer being one.  Left out, the hold this WP made
    possible could never be lifted: measured on the ramp's 700 °C pattern with
    the CaF₂ cell driven through a variable, the stage held it and kept it, the
    cell stayed at its 5.40 Å seed against 5.463026 Å released, and Rwp went
    0.0550 → 0.1939 with no diagnostic saying why.

    **Any, never all** — the mirror of :func:`_only_moves`' rule.  A column is
    held only while every phase it moves is invisible, so one phase appearing
    is enough to give it gradient again, and a direction the data can see must
    not stay frozen.
    """
    if support is None:
        support = model.phase_support(table.decode(table.x0()))
    seen = {ip for ip, s in enumerate(support) if s >= PHASE_SUPPORT_SIGMA}
    if not seen:
        return []
    prefixes = tuple(f"phases.{ip}." for ip in sorted(seen))
    reach = reach or {}
    return [p for p in held
            if any(name.startswith(prefixes)
                   for name in (p, *reach.get(p, ())))]


class NoPhasesError(ValueError):
    """A refining verb was handed a model with no phases (WP-1207).

    ``code`` is ``"NO_PHASES"``, and it is the same string on every surface: the
    agent envelope's fourth error code, and the GUI's reason for a disabled Run
    button.  A code rather than a sentence because the consumer's next action is
    specific and not the one any other refusal implies — index the pattern, or
    type a cell — where ``INVALID_REQUEST`` would send an agent back to check
    its field spelling and ``REFINEMENT_FAILED`` would suggest the fit is worth
    retrying.

    A :class:`~rietx.schemas.structure.Structure` with no phases is legal on
    purpose (that class says why), so this is a refusal by the **verb**: holding
    a phase-free model, picking peaks on it and indexing it are all supported,
    and only refining it is not.  Raised before the history tree is built or an
    event is emitted, for the reason the zero-stage plan is (WP-1110 item 6).
    """

    code = "NO_PHASES"


def _refuse_without_phases(structure: Structure, verb: str) -> None:
    """Refuse ``verb`` on a phase-free model, naming the ways forward.

    Not a check the caller can be trusted to have done: with no phases the
    forward model is the background and nothing else, every phase consumer is a
    loop over zero items, and the fit therefore *succeeds* — measured Rwp 0.9637
    and GoF 23.89 reported as ``converged`` against a pattern with 36 clear
    peaks (WP-1207's audit).  Silence here is a confident wrong answer, not a
    crash, which is why the refusal is explicit.
    """
    if structure.phases:
        return
    raise NoPhasesError(
        f"{verb} needs at least one phase: this model has none, so there is "
        "nothing but the background to fit and the run would converge on it "
        "and report success. A pattern-only project is a starting point, not a "
        "refinement — pick peaks and index it (rietx.index_pattern, or the "
        "GUI's Peaks panel), then adopt a candidate cell; or build the Le Bail "
        "scaffold directly from a symbol and a cell "
        "(rietx.schemas.structure.lebail_scaffold). To evaluate the background "
        "as it stands without refining, call ref.predict(pattern).")


def _snapshot_sinks(*candidates) -> list:
    """The objects a completed stage hands its picture to.

    Duck typing stays — it is what lets ``viz/live.py`` be a live view with no
    import from here into ``viz/``. What changes is that the *candidates* are
    named. The stage loop used to test whichever object ``events=`` resolved
    to, which cost two things: ``run_stage`` never refreshed a picture at all,
    and a caller who wrapped their stream would silently stop getting one.

    Deduped by identity, because ``as_event_stream`` returns an ``EventStream``
    unchanged and the two candidates are then one object writing one file
    twice.
    """
    sinks: list = []
    for candidate in candidates:
        if candidate is None or not hasattr(candidate, "write_snapshot"):
            continue
        if any(candidate is seen for seen in sinks):
            continue
        sinks.append(candidate)
    return sinks


class Refinement:
    """Refine ``structure`` + ``instrument`` against a powder pattern.

    The input models are deep-copied; refined values are exposed on
    ``fitted_structure`` / ``fitted_instrument`` after :meth:`fit`.

    Borrowing git's split: this object is the *working tree* (mutable, holds
    the current parameter values), while :attr:`history` is an append-only DAG
    of immutable checkpoints.  Each stage auto-commits a node, so any
    intermediate state can be restored with :meth:`checkout` and continued
    down a different branch with :meth:`run_stage`.

    Pass ``history=False`` for the light path: no snapshots, no per-stage
    statistics, no serialisation.
    """

    def __init__(self, structure: Structure, instrument: Instrument, *,
                 backend: str = "numpy", solver: str = "trf",
                 history: bool | str | Path | RefinementTree = True):
        if backend != "numpy":
            # fail fast (with the install hint) instead of at the first stage;
            # resolve_backend caches the instance, so this costs one import
            from .backend import resolve_backend

            try:
                resolve_backend(backend)
            except ValueError as exc:
                raise NotImplementedError(str(exc)) from exc
        if solver not in SOLVERS:
            raise ValueError(f"unknown solver {solver!r}; "
                             f"available: {', '.join(SOLVERS)}")
        self._backend = backend
        self._solver = solver
        self.structure = structure.model_copy(deep=True)
        self.instrument = instrument.model_copy(deep=True)
        #: λ per line as *declared*, snapshotted once here at construction — the
        #: wavelengths on the instrument this ``Refinement`` was built with.
        #: ``WAVELENGTH_CALIBRATION`` measures a refined λ against this, so
        #: every verb (``fit``/``run_stage``) reports the move *cumulatively*
        #: from the truly-declared value rather than from the previous call's
        #: answer, matching the joint path (``multi.py`` snapshots at
        #: construction for the same reason).  A deliberate model ``edit`` that
        #: replaces the instrument redefines it; a ``checkout`` to an earlier
        #: node does **not**, and a ``branch`` inherits the root's reference
        #: rather than re-declaring its own — see
        #: ``_wavelength_calibration_diagnostics``.
        self._declared_wavelengths = _declared_wavelengths(self.instrument)
        # Resolve a capillary µR from composition once, here, rather than per
        # stage: µR is a property of the specimen as mounted, so it must not
        # chase the refinement.  Writing it onto the (already copied)
        # instrument makes the value visible in ``fitted_instrument`` and in
        # every history snapshot instead of hiding inside the compiled model.
        self._mu_r_source, self._mu_r_skipped = _resolve_specimen_absorption(
            self.structure, self.instrument)
        self.result_: RefinementResult | None = None
        #: the last ``fit(stage_reports=True)`` run's trajectory, one
        #: :class:`~rietx.report.StageReport` per completed stage (WP-1058).
        #: Empty after a fit that was not asked for one — a report is *derived*
        #: from a result, so it is carried beside ``result_`` rather than
        #: inside it (the arrow's direction is why ``schemas/results.py``
        #: cannot import the report contract at all).
        self.stage_reports_: list[StageReport] = []
        self._model: CompiledModel | None = None

        # history state
        self.history: RefinementTree | None = None
        self._history_spec = history
        self._head_id: str | None = None
        if isinstance(history, RefinementTree):
            self.history = history
            self._head_id = history.head

        # carried across calls so a checkout can be continued
        self._mode: Mode = "rietveld"
        self._two_theta_limits: tuple[float, float] | None = None
        self._free_paths: list[str] = []
        #: paths the *last* stage held because the data could not see their
        #: phase (WP-1301).  Carried between stages rather than lifted at the
        #: end of one, because the free set a stage ends with is the set its
        #: solve used and everything downstream — the esd map, the guard, the
        #: statistics' ``n_free`` — is indexed by it.  So the lift happens at
        #: the *start* of the next stage, which is also where the hold is
        #: re-decided: a hold is a claim about one stage's data, never a change
        #: to what the caller asked to refine.
        self._held: list[str] = []
        self._pending_reflections: list[ReflectionState] = []
        #: user constraints (WP-1070), path → the affine dependence declared for
        #: it.  The one authority for *which* ties are the user's: the symmetry
        #: ties are rederived by every ``ParameterTable`` build and are absent
        #: here, which is what ``untie`` and ``TieSpec.user`` read.
        self._ties: dict[str, TieSpec] = {}
        #: named variables (WP-1119), bare name → its ``Parameter``.  The one
        #: authority, and one step beyond ``_ties``: a tie is not a property of
        #: the models, and a variable is not *in* them at all — there is no
        #: field for ``apply_to_models`` to write, so this dict is where its
        #: value lives between table builds and what ``snapshot`` persists.
        self._variables: dict[str, Parameter] = {}
        #: of those, the ones the most recent table build actually declared —
        #: what ``TieSpec.user`` is answered from, so a row names whose tie is
        #: *in force* on it rather than whose was asked for
        self._applied_ties: set[str] = set()
        #: caller-declared holds (WP-1435), the paths that do not move whatever
        #: a plan asks for.  The one authority, on ``_ties``' model and for its
        #: reason: ``vary`` cannot carry the declaration, because a plan
        #: *replaces* the vary flags rather than continuing them (WP-1208), so
        #: a pinned certified cell was refined anyway and the model went on
        #: reading ``vary=False`` (issue #211).
        #:
        #: Distinct from :attr:`_held` above, which is WP-1301's and nearly
        #: shares this name.  That one is the *package's* reading of what this
        #: stage's data can see, and it is lifted at the start of the next
        #: stage.  This one is the *caller's* declaration, and only ``unhold``
        #: lifts it.  They never overlap: ``_hold_unsupported_phases`` holds
        #: free paths, and a path in here is never free.
        self._user_holds: set[str] = set()
        #: what :meth:`fit` last ran, for :meth:`summary` alone — nothing
        #: computes from these, only prints them back (WP-1302)
        self._last_plan: RefinementPlan | None = None
        self._sigma_from_file: bool | None = None
        self._excluded_regions: list[tuple[float, float]] = []

    # ------------------------------------------------------------------
    # history plumbing
    # ------------------------------------------------------------------
    def _ensure_history(self, data: PatternData,
                        plan: RefinementPlan | None = None) -> RefinementTree | None:
        """Create the tree on first use (it needs the pattern to fingerprint)."""
        spec = self._history_spec
        if self.history is None:
            if not spec:
                return None
            path = None if spec is True else spec
            self.history = RefinementTree.for_data(
                data, path=path, plan=plan, package_version=_VERSION)
        if len(self.history) == 0:
            root = self.history.add(
                parents=[], action=NodeAction(kind="root"), state=self.snapshot())
            self._head_id = root.id
        return self.history

    def _project_hint(self) -> Path | None:
        """``<project>.rex/live`` when this refinement was built from a project.

        A ``Refinement`` holds no back-reference to a ``Project``, and giving it
        one so that telemetry could find a directory would be a coupling bought
        for a default. This derives the answer instead: a history tree whose
        file sits beside a ``project.json`` is a project's tree.

        **Both attributes are optional**, so this is two ``is not None`` tests
        before one ``exists()`` a run, and it answers ``None`` rather than
        raising. :attr:`history` is ``None`` until :meth:`_ensure_history` has
        run, and ``RefinementTree.path`` is ``None`` for an in-memory tree,
        which is what ``history=False`` and every synthetic fixture produce.

        ``Project.fit`` sets the same directory as a ``telemetry=`` default and
        never depends on this, which is the point: the project stays the only
        place that *knows* its own path, and this is the fallback for a bare
        ``ref.fit()`` on the refinement a project handed out. The import is
        deferred because ``project.py`` imports this module; it is also free in
        the only case that reaches it, since a tree beside a ``project.json``
        means ``project.py`` is already imported in this process.
        """
        tree = self.history
        if tree is None or tree.path is None:
            return None
        parent = Path(tree.path).parent
        from .project import LIVE_DIR, PROJECT_JSON
        if not (parent / PROJECT_JSON).exists():
            return None
        return parent / LIVE_DIR

    def _invalidate_fit(self) -> None:
        """Drop everything that described the previous values.

        One place rather than four, because the set grows: the fitted curve and
        statistics went stale together long before the trajectory joined them
        (WP-1058), and a rung is a statement *about a state* — it goes stale
        exactly when ``result_`` does.
        """
        self._model = None
        self.result_ = None
        self.stage_reports_ = []

    def _require_history(self) -> RefinementTree:
        if self.history is None:
            raise RuntimeError(
                "this Refinement has no history; construct it with "
                "history=True (the default) or history='path.jsonl' to enable "
                "checkpoints and branching")
        return self.history

    def snapshot(self, *, model: CompiledModel | None = None) -> RefinementState:
        """The full state needed to reconstruct this refinement exactly."""
        return RefinementState(
            structure=self.structure.model_copy(deep=True),
            instrument=self.instrument.model_copy(deep=True),
            mode=self._mode,
            free_paths=list(self._free_paths),
            two_theta_limits=self._two_theta_limits,
            reflections=_extract_reflections(model or self._model),
            ties={p: s.model_copy(deep=True) for p, s in self._ties.items()},
            variables={n: v.model_copy(deep=True)
                       for n, v in self._variables.items()},
            holds=sorted(self._user_holds),
        )

    def _record(self, tree: RefinementTree, action: NodeAction, model: CompiledModel,
                table: ParameterTable, outcome, diagnostics) -> str:
        values = table.decode(outcome.theta)
        y_calc = model.evaluate(values)
        stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                   n_free=len(table.free_paths) + _pawley_n(model),
                                   y_background=model.background(values))
        stats.max_shift_over_esd = outcome.max_shift_over_esd  # copied, never derived
        stderr = (table.stderr_physical(outcome.theta, outcome.stderr_internal,
                                        outcome.correlation)
                  if outcome.stderr_internal is not None else {})
        metrics = NodeMetrics(
            statistics=stats, status=outcome.status, n_iterations=outcome.n_iterations,
            cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
            stderr=stderr)
        node = tree.add(
            parents=[self._head_id] if self._head_id else [],
            action=action, state=self.snapshot(model=model),
            metrics=metrics, diagnostics=diagnostics)
        self._head_id = node.id
        return node.id

    # ------------------------------------------------------------------
    # branching
    # ------------------------------------------------------------------
    def checkout(self, node_id: str) -> "Refinement":
        """Restore the state recorded at ``node_id`` (a node id or a tag).

        Mutates this object's working state, like ``git checkout``.  The node
        itself is untouched.
        """
        tree = self._require_history()
        node = tree[node_id]
        self.structure = node.state.structure.model_copy(deep=True)
        self.instrument = node.state.instrument.model_copy(deep=True)
        self._mode = node.state.mode
        self._two_theta_limits = node.state.two_theta_limits
        self._free_paths = list(node.state.free_paths)
        # the node's free set is the declared one (``_record_free_paths``), so
        # a checkout starts with no hold and the next stage takes its own
        self._held = []
        self._ties = {p: s.model_copy(deep=True) for p, s in node.state.ties.items()}
        self._variables = {n: v.model_copy(deep=True)
                           for n, v in node.state.variables.items()}
        # unlike ``_held`` above, a user hold is restored: it is a declaration
        # the node recorded, and a checkout that dropped it would hand back a
        # state whose pin had quietly expired (WP-1435)
        self._user_holds = set(node.state.holds)
        self._pending_reflections = [r.model_copy(deep=True) for r in node.state.reflections]
        self._head_id = node.id
        self._invalidate_fit()
        tree.set_head(node.id)
        return self

    def branch(self, node_id: str | None = None) -> "Refinement":
        """A second working tree over the same history, for a rival strategy."""
        tree = self._require_history()
        ref = Refinement(self.structure, self.instrument,
                         backend=self._backend, solver=self._solver, history=tree)
        ref._mode = self._mode
        ref._two_theta_limits = self._two_theta_limits
        ref._free_paths = list(self._free_paths)
        ref._ties = {p: s.model_copy(deep=True) for p, s in self._ties.items()}
        ref._variables = {n: v.model_copy(deep=True)
                          for n, v in self._variables.items()}
        # a rival strategy inherits the caller's declarations, as it inherits
        # the ties: a branch is a second working tree, and a hold the branch
        # dropped would make the two rivals answer different questions
        ref._user_holds = set(self._user_holds)
        ref._head_id = self._head_id
        ref._pending_reflections = [r.model_copy(deep=True) for r in self._pending_reflections]
        # The branch is built from ``self.instrument``, which carries the last
        # stage's *refined* λ — so its own ``__init__`` snapshot would declare a
        # refined value.  A branch is "a second working tree over the same
        # history, for a rival strategy", and the calibration diagnostic exists
        # to compare strategies against one reference; two rivals quoting
        # different declared λ for the same physical instrument would make that
        # comparison meaningless.  So the declared reference is inherited from
        # the root, exactly as ``_free_paths`` and the ties are (WP-1134).  An
        # ``edit`` on the branch still re-snapshots — a branch that swaps the
        # anode genuinely re-declares — so "declared = the instrument this
        # Refinement is built with, as last set" survives, with "built with"
        # meaning the root construction, inherited through branching.  Copied
        # rather than aliased so a later ``edit`` on either side cannot mutate
        # the other's reference.
        ref._declared_wavelengths = list(self._declared_wavelengths)
        if node_id is not None:
            ref.checkout(node_id)
        return ref

    def edit(self, *, structure: Structure | None = None,
             instrument: Instrument | None = None, label: str = "") -> str | None:
        """Record a change to the model itself — adding an impurity phase,
        raising the background order, swapping the geometry.

        Structural edits are refinement moves too: they belong in the history
        beside the stages, so a branch that adds a phase can be compared
        against one that does not.  Returns the new node id (``None`` when
        history is disabled).

        **The proposed models must have a parameter table, and that is checked
        here rather than discovered later.**  Pydantic validates a `Structure`
        against its schema and knows no crystallography: every symmetry refusal
        in this package — an anisotropic tensor outside the site's allowed
        subspace, a Stephens block outside the Laue subspace, a ``vary=True``
        coordinate on a fully fixed special position, a cell angle disagreeing
        with the space group — is raised when :class:`ParameterTable` is
        *constructed*, and the snapshot this method commits never constructs one.
        Without the check an incompatible edit succeeded, wrote a history node,
        and then raised from whatever next asked for the table, leaving the
        working state somewhere no fit and no listing can be built from
        (WP-1035, measured through the GUI as a 500 on the following
        ``GET /api/params``).

        The check is on the **proposed** pair, never on the current one, so an
        edit that *repairs* such a state is not refused by the damage it is
        undoing.  It costs one table build on a cold path — the same build the
        next stage compile or ``parameters()`` call performs anyway.
        """
        candidate = self.structure if structure is None else structure
        try:
            table = ParameterTable(
                candidate, self.instrument if instrument is None else instrument)
        except ValueError as exc:
            raise ValueError(
                f"this model has no parameter table, so the edit is refused "
                f"rather than recorded: {exc}") from None
        # Reconcile the user constraints with the model being accepted, here
        # rather than at the next table build: this is the recorded verb, so the
        # register it leaves is the one the node carries, and a tie that stopped
        # applying is said once — at the edit that ended it — instead of on
        # every listing afterwards (WP-1070).
        self._declare_variables(table)
        applied = self._apply_ties(table)
        self._ties = {p: s for p, s in self._ties.items() if p in applied}
        # The holds are reconciled here too, and the outcome is the opposite
        # one: a tie that stopped applying is *dropped*, because the model it
        # described is gone and a stale affine relation would silently
        # reimpose itself.  A hold that stopped applying is **kept**.  It
        # forbids rather than describes, so there is nothing in it to go
        # stale, and dropping it at an edit would be the one way a
        # declaration could lapse without anybody saying so.  The warning
        # ``_apply_holds`` gives is the saying-so.
        self._apply_holds(table)
        if structure is not None:
            self.structure = structure.model_copy(deep=True)
        if instrument is not None:
            self.instrument = instrument.model_copy(deep=True)
            # An instrument edit is a deliberate redefinition of the instrument
            # this Refinement is built with — swapping the anode changes the
            # emission lines outright — so the declared reference the calibration
            # diagnostic reports against moves with it.  A checkout does not
            # (that is history navigation, not a new instrument), which is the
            # caveat the construction snapshot documents.
            self._declared_wavelengths = _declared_wavelengths(self.instrument)
        self._invalidate_fit()
        if self.history is None:
            return None
        node = self.history.add(
            parents=[self._head_id] if self._head_id else [],
            action=NodeAction(kind="edit_model", name=label or "model edited"),
            state=self.snapshot(), label=label)
        self._head_id = node.id
        return node.id

    # ------------------------------------------------------------------
    # the parameter table as data, and the two verbs that edit it
    # ------------------------------------------------------------------
    def _working_table(self) -> ParameterTable:
        """The table describing the current working state.

        After a stage there is a recorded free set to restore; before the first
        one there is not, and the models' own ``vary`` flags are what the caller
        set — so a fresh table (which reads them) is the honest answer rather
        than an all-fixed one.
        """
        if self._free_paths:
            return self._prepare_table(restore=True)
        table = ParameterTable(self.structure, self.instrument)
        self._declare_variables(table)
        self._apply_ties(table)
        self._apply_holds(table)
        return table

    def parameters(self, *, mode: Mode | None = None) -> list[ParameterRow]:
        """Every parameter as data — fixed, locked and tied rows included.

        The counterpart of ``result_.parameters`` (which lists only what a fit
        refined): this is the whole table, in θ order, with the most recent
        fit's esds merged in and each held row saying *why* it is held.  A cold
        path — pydantic here is fine, the no-pydantic rule binds the residual.

        ``mode`` overrides which intensity mode ``mode_fixed`` is answered for.
        It exists because this object's carried ``_mode`` is what the last stage
        *ran* in, and before the first run that is the ``"rietveld"`` default —
        so a caller that knows the mode the **next** run will use (a
        :class:`~rietx.project.Project`, from its document) has to be able to
        say so, or a Le Bail project's atom rows come back looking editable,
        which is the one thing ``mode_fixed`` exists to prevent.
        """
        esd = ({p.path: p.stderr for p in self.result_.parameters}
               if self.result_ is not None else {})
        mode = mode or self._mode
        table = self._working_table()
        # Whether a wavelength could be freed depends on the cell's *current*
        # state, so it is read here rather than stored on the entry.
        blocked = (table._wavelength_paths()
                   if table._cell_is_free() else frozenset())
        # the same test the stage's drop applies, so the report and the drop
        # cannot disagree about which columns this mode force-fixes (WP-1076's
        # rule, WP-1342's question).  ``entry_reach`` rather than
        # ``column_reach`` because this answers about every entry: the drop
        # *makes* a variable fixed, and a row that then called it refinable
        # would invite the caller to free what the next stage fixes again.
        reach = table.entry_reach()
        rows = []
        for e in table.entries:
            rows.append(ParameterRow(
                path=e.path, value=e.value, vary=e.vary, lo=e.lo, hi=e.hi,
                transform=e.transform,
                tie=(TieSpec._from_tie(e.tie, user=e.path in self._applied_ties)
                     if e.tie is not None else None),
                locked=e.locked,
                held=e.held,
                esd=esd.get(e.path),
                mode_fixed=(mode_fixed_column(reach[e.path], mode)
                            if e.path in reach
                            else mode_fixed_path(e.path, mode)),
                needs_held_cell=e.path in blocked,
                help_key=help_key_for(e.path),
            ))
        return rows

    def set_vary(self, path_globs: list[str] | str, vary: bool = True) -> list[str]:
        """Free (or hold) every parameter matching ``path_globs``.

        Dot-path globs with fnmatch semantics, exactly as a stage's ``turn_on``
        (``"phases.*.cell.*"``).  Returns the paths actually changed, and
        records a ``set_vary`` history node — freeing a parameter is a
        refinement move, so it belongs in the log beside the stages.

        Delegates to :meth:`ParameterTable.set_vary`, which is where the rules
        live: a locked or tied entry never matches, however broad the glob.
        Paths this mode force-fixes (see :func:`mode_fixed_path`) can be freed
        here but are dropped again when a stage runs, and
        :meth:`parameters` reports them as ``mode_fixed``.

        The node is recorded only once the history tree exists — it is created
        on the first ``fit``/``run_stage``, because a tree is pinned to its
        pattern by a fingerprint and no pattern has been seen before then.  The
        working state changes either way.
        """
        globs = [path_globs] if isinstance(path_globs, str) else list(path_globs)
        table = self._working_table()
        if vary:
            # A literal path is a claim about one parameter, and a held one
            # contradicts a declaration this same caller made, so it is
            # refused with the verb that resolves it.  A *pattern* is a sweep
            # and its held rows are skipped in silence — the treatment a
            # symmetry-fixed cell angle gets, for the reason
            # ``ParameterTable.set_vary`` gives: turning a broad glob into an
            # error is worse than declining one row of it.
            #
            # Only where the hold is the reason that *bites*, which is the
            # filter ``StageResult.blocked_by_hold`` uses and the order
            # ``ParameterRow.held_because`` reports in.  A broad
            # ``hold("phases.*.cell.*")`` marks the symmetry-tied and locked
            # rows too, and on those the message below would be false advice:
            # ``unhold`` gives them back no freer than they were, so they keep
            # ``set_vary``'s older answer of declining in silence.
            by_path = {e.path: e for e in table.entries}
            blocked = [g for g in globs
                       if is_literal_path(g) and g in self._user_holds
                       and g in by_path and by_path[g].tie is None
                       and not by_path[g].locked]
            if blocked:
                raise ValueError(
                    f"{blocked[0]!r} is held by this refinement and cannot be "
                    "freed; unhold it first if you mean to refine it")
        hits = table.set_vary(globs, vary)
        # A carried hold (WP-1301) is lifted at the start of the next stage, so
        # a path the caller has just declared on must leave it: otherwise the
        # lift re-frees a parameter the caller explicitly fixed, and the
        # declaration is silently undone by the next ``run_stage``.
        if self._held and hits:
            declared = set(hits)
            self._held = [p for p in self._held if p not in declared]
        self._free_paths = list(table.free_paths)
        if self.history is None:
            return hits
        node = self.history.add(
            parents=[self._head_id] if self._head_id else [],
            action=NodeAction(kind="set_vary",
                              turn_on=hits if vary else [],
                              turn_off=[] if vary else hits),
            state=self.snapshot())
        self._head_id = node.id
        return hits

    def set_values(self, values: dict[str, float]) -> None:
        """Set parameter values by dot-path, recording a ``set_value`` node.

        Plural because a GUI (or a script) edits a table, not a cell: one node
        per keystroke would bury the log, and a set of values applied together
        is one refinement move.  The name is also what
        ``NodeAction.api_call()`` has always rendered for the ``"set_value"``
        node kind.

        Raises rather than guessing, because each refusal has a different fix:
        an unknown path is a typo; a **locked** path is structurally fixed; a
        **tied** path names its sources, since setting those is what the caller
        meant; a value outside the parameter's own bounds would make the
        starting point infeasible for the bounded solver.

        Dependents follow their sources (``b`` after ``a`` on a cubic cell, a
        coordinate after its Wyckoff DOF).  Like :meth:`set_vary`, the node is
        recorded only once the history tree exists.
        """
        table = self._working_table()
        by_path = {e.path: e for e in table.entries}
        unknown = [p for p in values if p not in by_path]
        if unknown:
            raise ValueError(f"unknown parameter path(s): {sorted(unknown)}")
        for path, value in values.items():
            e = by_path[path]
            if e.locked:
                raise ValueError(
                    f"{path!r} is structurally fixed (symmetry, or a "
                    "representation that owns this channel) and cannot be set")
            if e.tie is not None:
                sources = ", ".join(repr(p) for p, _ in e.tie.terms)
                one = len(e.tie.terms) == 1
                raise ValueError(
                    f"{path!r} follows {sources} as an affine tie; set "
                    f"{'that' if one else 'those'} instead")
            if not (e.lo <= float(value) <= e.hi):
                raise ValueError(
                    f"{path}={value} lies outside its bounds [{e.lo}, {e.hi}]")
        for path, value in values.items():
            by_path[path].value = float(value)
        table.refresh_ties()  # dependents follow their sources (b←a, x←dof)
        self._write_back(table)
        # the fitted curve and statistics described the *old* values
        self._invalidate_fit()
        if self.history is None:
            return
        node = self.history.add(
            parents=[self._head_id] if self._head_id else [],
            action=NodeAction(kind="set_value", values=dict(values)),
            state=self.snapshot())
        self._head_id = node.id

    # ------------------------------------------------------------------
    # user constraints (WP-1070)
    # ------------------------------------------------------------------
    def _declare_variables(self, table: ParameterTable) -> None:
        """Append this refinement's named variables to a freshly built table.

        The counterpart of :meth:`_apply_ties`, and it runs **first**, because a
        user tie may name a variable as its source and a table cannot be told
        about a tie whose source it has never heard of.

        A variable is a synthetic entry exactly as a Wyckoff DOF is — the shape
        :meth:`ParameterTable.add_parameter` exists for — but with one
        difference that is the whole reason this method exists: a DOF is
        *rederived* from the structure on every build, and a variable cannot be,
        because nothing in the structure knows about it.  So it is re-declared
        from :attr:`_variables`, which is why that dict is the one authority for
        what a variable *is* and why ``snapshot`` has to carry it.

        Bounds and transform come straight off the caller's ``Parameter``, which
        is what makes a variable and the model parameter it replaces produce the
        identical :class:`~rietx.params.vector.Entry`.
        """
        for name, prm in self._variables.items():
            table.add_parameter(f"{VAR_PREFIX}{name}", prm.value, vary=prm.vary,
                                lo=prm.min, hi=prm.max, transform=prm.transform)

    def _write_back(self, table: ParameterTable) -> None:
        """``apply_to_models``, plus the one thing it structurally cannot do.

        ``ParameterTable.apply_to_models`` writes values back by walking the
        pydantic model tree, so a synthetic entry with no model field has
        nowhere to be written — true of a Wyckoff DOF too, but harmless there,
        since the DOF is rebuilt from the coordinates it wrote.  A variable has
        no such second home: drop its refined value here and the next table
        build re-declares it at the value it was *created* with, silently
        undoing the fit for every parameter that follows it.

        So the register is the variable's model, and this is where it is
        written.  Every call site holding the *working* state goes through
        here; the two that do not — ``suggest``'s deep copies and the
        module-level exporter — have no register to write to.

        No ``stderr`` argument, unlike ``apply_to_models``: the esd of a
        variable reaches a caller through ``result_.parameters`` and the
        ``ParameterRow`` built from it, keyed by ``vars.<name>`` like any other
        path, so a second copy on the register would have no reader.  A
        parameter nothing writes is the shape WP-1076 removes, and one added
        here would fail no test.
        """
        table.apply_to_models(self.structure, self.instrument)
        if not self._variables:
            return
        values = {e.path: e.value for e in table.entries}
        for name, prm in self._variables.items():
            value = values.get(f"{VAR_PREFIX}{name}")
            if value is not None:
                prm.value = value

    def _apply_ties(self, table: ParameterTable) -> set[str]:
        """Re-declare this refinement's user ties on a freshly built table.

        Every ``ParameterTable`` rederives the *symmetry* ties from the space
        group and the Wyckoff positions and knows nothing about a user's, so
        each build has to be told again — which is exactly what makes
        :attr:`_ties` the one authority for which ties are the user's.

        **Symmetry outranks a user tie, and this is the one place that can be
        violated.**  The verbs refuse a target that is already tied, but a tie
        declared while a path was free stays declared if a later :meth:`edit`
        makes that same path symmetry-tied — a P1 phase respaced to a cubic
        symbol ties ``b`` and ``c`` to ``a``.  Overwriting would silently break
        the symmetry the derived tie exists to enforce, so an occupied row is
        skipped and said out loud, alongside the vanished-path case
        :meth:`_prepare_table` reports for a free path.

        Returns the paths actually declared, which is what
        :meth:`parameters` answers ``TieSpec.user`` from: a row must say whose
        tie is *in force* on it, and after such a collision the register and the
        table disagree about that.  :meth:`edit` prunes the register against the
        model it accepts, so the disagreement is momentary on the recorded path
        and this stays the defence for the unrecorded ones.
        """
        self._applied_ties: set[str] = set()
        if not self._ties:
            return self._applied_ties
        by_path = {e.path: e for e in table.entries}
        dropped: list[str] = []
        for path, spec in self._ties.items():
            entry = by_path.get(path)
            missing = [p for p, _ in spec.terms if p not in by_path]
            if entry is None:
                dropped.append(f"{path} (no such parameter)")
            elif entry.locked:
                dropped.append(f"{path} (now structurally fixed)")
            elif entry.tie is not None:
                dropped.append(f"{path} (now tied by symmetry to "
                               f"{', '.join(p for p, _ in entry.tie.terms)})")
            elif missing:
                dropped.append(f"{path} (source {missing[0]} no longer exists)")
            else:
                table.set_tie(path, AffineTie(
                    terms=tuple((p, float(c)) for p, c in spec.terms),
                    const=float(spec.const)))
                self._applied_ties.add(path)
        # A displacement DOF's anchor is the coordinate the model stores, and
        # that coordinate has already absorbed whatever the tie contributed at
        # the last write-back.  Anchoring on it again adds the source's value a
        # second time, once per table build (WP-1432), so the anchors are
        # corrected here — on the fresh table, before anything reads it.
        table.rebase_anchored_dofs(self._applied_ties)
        if dropped:
            warnings.warn(
                f"{len(dropped)} user tie(s) no longer apply to this model and "
                f"were dropped: {'; '.join(dropped)}. Symmetry outranks a user "
                "tie.", UserWarning, stacklevel=3)
        return self._applied_ties

    def _apply_holds(self, table: ParameterTable) -> None:
        """Re-declare this refinement's holds on a freshly built table.

        The counterpart of :meth:`_apply_ties`, and it runs **after** it, for
        one reason: :meth:`ParameterTable.set_held` forces ``vary=False``, and
        a path the space group has since tied is left alone by ``set_tie``
        anyway, so the order only decides which reason a row reports first.

        Every path in the register is marked, whether or not something else
        already held it.  A hold on a locked or tied row changes nothing and
        is not an error: the caller held a glob, the space group had taken
        some of the rows, and ``held_because`` reports the structural reason
        first because that is the one ``unhold`` cannot lift.

        A path that has **vanished** is the case worth a word, and it is the
        one :meth:`_apply_ties` warns about too.  The register keeps it, since
        a removed phase can come back through a checkout and the caller's
        declaration about it has not been withdrawn.  What is said out loud is
        that the hold is not in force on *this* model, because a promise
        nobody can keep is exactly what this WP exists to stop being silent.
        """
        if not self._user_holds:
            return
        marked = set(table.set_held(self._user_holds, True))
        missing = sorted(self._user_holds - marked)
        if missing:
            warnings.warn(
                f"{len(missing)} held path(s) are not in this model and so hold "
                f"nothing here: {missing[:5]}{'…' if len(missing) > 5 else ''}. "
                "The declaration is kept, in case a checkout restores them.",
                UserWarning, stacklevel=3)

    def _tie_entry(self, table: ParameterTable, path: str, *, role: str):
        """The entry ``path`` names, refusing with the reason a tie cannot use it.

        One function for both ends because the refusals overlap and their
        wording must not: ``set_values``' sentences are reused verbatim where
        they apply, so two surfaces never disagree about why a parameter is
        held.
        """
        by_path = {e.path: e for e in table.entries}
        entry = by_path.get(path)
        if entry is None:
            raise ValueError(f"unknown parameter path: {path!r}")
        if entry.locked:
            raise ValueError(
                f"{path!r} is structurally fixed (symmetry, or a representation "
                f"that owns this channel) and cannot be a tie {role}")
        if entry.tie is not None and not (role == "source" and is_variable_path(path)):
            # **A tied source is accepted iff it is a variable** (WP-1119).  The
            # table has always flattened chains exactly — a depth-2 chain comes
            # back with the product coefficient and the composed constant, and a
            # cycle raises — so this refusal is a judgement about what a caller
            # meant, not a limit of the machinery.  It is kept for a *model*
            # path, where the advice it gives is right: ``biso = 4·x`` with
            # ``x ← dof.0`` silently becomes ``4·dof.0 + 0.7972``, a constant
            # nobody wrote, and naming ``dof.0`` says the same thing out loud.
            # It is lifted between variables, where composing is the point —
            # ``B = A + C``, TOPAS's ``prm B = 2 A`` — and where there is no
            # symmetry to outrank and no hidden constant to inherit.
            sources = ", ".join(repr(p) for p, _ in entry.tie.terms)
            # ``_applied_ties``, not ``_ties``: the question is whose tie is in
            # force on this row, and after a symmetry collision the register
            # still names the user's while the table holds the space group's
            kind = "a user tie" if path in self._applied_ties else "symmetry"
            if role == "source":
                raise ValueError(
                    f"{path!r} follows {sources} ({kind}), so it carries no "
                    "freedom of its own; tie to what it follows instead, or "
                    "name a variable, which may follow other variables")
            raise ValueError(
                f"{path!r} already follows {sources} ({kind}); "
                f"{'untie it first' if kind == 'a user tie' else 'symmetry outranks a user tie'}")
        if role == "target" and mode_fixed_path(path, self._mode):
            raise ValueError(
                f"{path!r} is force-fixed by the {self._mode!r} intensity mode, "
                "so tying it would reduce a parameter count that is already zero")
        return entry

    def add_variable(self, name: str, value: float, *, vary: bool = False,
                     min: float = -math.inf, max: float = math.inf,
                     transform: str = "identity",
                     unit: str | None = None) -> str:
        """Declare a named variable other parameters can follow.  Returns its path.

        A parameter of the caller's own, with its own value and bounds, living
        outside the model tree — TOPAS's ``prm``.  It exists so a constraint can
        be written in terms of a *quantity* rather than in terms of whichever
        model parameter happened to be nominated as the master::

            ref.add_variable("B_metal", 0.7, min=0.0, max=25.0)
            ref.tie_equal(["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"],
                          source="vars.B_metal")
            ref.tie("phases.0.atoms.3.biso", "vars.B_metal", scale=2.0)
            ref.set_vary("vars.*", True)

        The path is ``"vars." + name``, and it is an ordinary dot-path from
        there on: :meth:`parameters` lists it, :meth:`set_vary` globs it,
        :meth:`set_values` moves it, and a fit refines it and gives it an esd.

        ``min``/``max``/``transform`` are the declaration that matters.  A
        variable is a :class:`~rietx.schemas.common.Parameter`, and the table
        reads an entry's bounds and transform straight off one — so a variable
        declared like the model parameter it replaces is **indistinguishable**
        to the fit, which is the property that makes this a renaming rather
        than a new degree of freedom.  Declared unlike it, it is a different
        problem: a softplus parameter given the default identity transform is
        no longer kept off its own floor.

        Refuses a name that is not a single identifier, one that would collide
        with an existing entry, and a redeclaration — :meth:`remove_variable`
        first, so the history records that the old one ended.
        """
        if not name or not name.isidentifier():
            raise ValueError(
                f"variable name {name!r} must be a single identifier — no dots "
                "(the path is built as 'vars.' + name) and no fnmatch "
                "metacharacters, or a glob could not name it")
        if name in self._variables:
            raise ValueError(
                f"variable {name!r} already exists; remove_variable({name!r}) "
                "first, so the history records that the old one ended")
        prm = Parameter(value=value, vary=vary, min=min, max=max,
                        transform=transform, unit=unit)
        path = f"{VAR_PREFIX}{name}"
        # the table is the authority on collisions: add_parameter raises on a
        # path that already exists, and probing one here means the refusal
        # happens before the register is touched
        self._working_table().add_parameter(
            path, prm.value, vary=prm.vary, lo=prm.min, hi=prm.max,
            transform=prm.transform)
        self._variables[name] = prm
        if prm.vary and self._free_paths:
            # ``_free_paths`` is the *declared* free set, and once a stage has
            # recorded one it is what ``_prepare_table`` restores — it clears
            # every vary flag and replays that list.  A variable declared
            # ``vary=True`` after the first stage would otherwise come back
            # held, its own declaration silently overruled by a list written
            # before it existed.  Appended, not inserted: entry order is what
            # the restore replays and a variable is appended to the table too.
            self._free_paths.append(path)
        self._commit_variable_edit(declared={name: prm}, removed=[])
        return path

    def remove_variable(self, name: str) -> str:
        """Delete a named variable, refusing while anything follows it.

        The refusal names the dependents, because the fix is theirs: untie them
        (or retie them elsewhere) and the variable is free to go.  Deleting it
        under them would leave ties naming a parameter that does not exist,
        which :meth:`_apply_ties` would then drop one build later — a
        constraint lost two moves away from the call that lost it.

        A tie whose *target* is this variable is the other direction and is not
        a refusal: it is the removed parameter's own constraint, so it goes with
        it.  Leaving it in the register would warn "no such parameter" on every
        table build afterwards, and a later ``add_variable`` of the same name
        would silently resurrect it — the new declaration's value overwritten by
        a tie the caller had already deleted.

        Returns the path removed.
        """
        if name not in self._variables:
            raise ValueError(
                f"no variable named {name!r}; declared: "
                f"{sorted(self._variables) or 'none'}")
        path = f"{VAR_PREFIX}{name}"
        dependents = sorted(p for p, spec in self._ties.items()
                            if any(src == path for src, _ in spec.terms))
        if dependents:
            raise ValueError(
                f"{path!r} still has {len(dependents)} dependent(s) "
                f"({', '.join(dependents[:5])}"
                f"{'…' if len(dependents) > 5 else ''}); untie them first, or "
                "the ties would be left naming a parameter that no longer exists")
        del self._variables[name]
        self._ties.pop(path, None)  # its own tie, if it followed another variable
        self._free_paths = [p for p in self._free_paths if p != path]
        self._commit_variable_edit(declared={}, removed=[name])
        return path

    def _commit_variable_edit(self, *, declared: dict[str, Parameter],
                              removed: list[str]) -> None:
        """Land a variable edit: the fit is invalidated and a node is added."""
        # a declared variable follows nothing and nothing follows it yet, so no
        # value in the model moved — but the parameter *count* can have, and
        # every esd and statistic the last fit reported was computed against the
        # table as it stood
        self._invalidate_fit()
        if self.history is None:
            return
        node = self.history.add(
            parents=[self._head_id] if self._head_id else [],
            action=NodeAction(kind="set_variable",
                              variables={n: v.model_copy(deep=True)
                                         for n, v in declared.items()},
                              removed_variables=list(removed)),
            state=self.snapshot())
        self._head_id = node.id

    def tie(self, path: str, source: "str | dict[str, float] | Sequence[tuple[str, float]]",
            *, scale: float = 1.0, offset: float = 0.0) -> str:
        """Constrain ``path`` to ``scale·source + offset``, recording a node.

        The general affine form, of which :meth:`tie_equal` is the ``scale=1,
        offset=0`` case.  Complementary occupancies on a shared site are the
        other one a powder refinement reaches for often::

            ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ",
                    scale=-1.0, offset=1.0)

        A constraint, not a restraint: ``path`` leaves θ and the freedom stays
        with ``source``, so the parameter count drops by one and the
        observation/parameter ratio rises — which is what makes the esds
        contract.  ``path`` takes its implied value immediately (the models are
        written through, as :meth:`set_values` writes them), so nothing is
        left describing the pre-tie state.

        Refuses rather than approximating, each with its own fix: an unknown
        path is a typo; a **locked** end is structurally fixed; an
        **already-tied** target names what holds it, and symmetry always
        outranks a user tie; a **tied source** carries no freedom, so the tie
        would be a chain — name what *it* follows; a **mode-fixed** target
        would reduce a parameter count that is already zero; ``scale=0`` is
        :meth:`set_values` spelled obscurely; and an implied value outside the
        target's own bounds would start the bounded solver infeasible.

        ``source`` takes **several** sources as well as one — a dict or a list
        of ``(path, coefficient)`` pairs — because the representation underneath
        has always been ``Σ c·source + const`` and only the verb was
        single-term::

            ref.tie("vars.B", {"vars.A": 1.0, "vars.C": 1.0})

        ``scale`` multiplies every term, so the one-source spelling is exactly
        the one-entry case of the many-source one and neither is a special
        path through the code.

        Returns ``path``.  Like :meth:`set_vary`, the node is recorded only
        once the history tree exists.
        """
        return self._declare_ties({path: (_tie_terms(source, float(scale)),
                                          float(offset))})[0]

    def tie_equal(self, paths: list[str] | str, *,
                  source: str | None = None) -> list[str]:
        """Make every parameter matching ``paths`` one parameter.

        The verb §7 of McCusker et al. (1999) asks for twice — equal
        displacement parameters across similar atoms, chemically constrained
        occupancies — spelled the way the recommendation reads::

            ref.tie_equal(["phases.0.atoms.1.biso", "phases.0.atoms.2.biso",
                           "phases.0.atoms.3.biso"])

        Dot-path globs with fnmatch semantics, exactly as :meth:`set_vary`
        takes them.  The **first match in table order** carries the freedom and
        the rest follow it; name ``source`` to choose a different one (it need
        not be among the matches).  Table order is
        :meth:`parameters`' order, so which one that is is readable rather than
        guessed at.

        All-or-nothing, and a matched path that cannot be tied is a refusal
        rather than a silent omission — an unasked-for constraint that did not
        happen is the failure this verb exists to make impossible.  A glob that
        sweeps in a locked row is a glob to narrow, and the message names it.

        Returns the paths actually tied, source excluded.
        """
        globs = [paths] if isinstance(paths, str) else list(paths)
        table = self._working_table()
        import fnmatch

        matched = [e.path for e in table.entries
                   if any(fnmatch.fnmatchcase(e.path, g) for g in globs)]
        if not matched:
            raise ValueError(f"no parameter matches {globs}")
        src = source if source is not None else matched[0]
        targets = [p for p in matched if p != src]
        if not targets:
            raise ValueError(
                f"{globs} matches only {src!r}, so there is nothing to tie to "
                "it; an equality group needs at least two parameters")
        return self._declare_ties({p: ([(src, 1.0)], 0.0) for p in targets})

    def untie(self, paths: list[str] | str) -> list[str]:
        """Release user ties, recording a ``set_tie`` node.

        Globs match against the *declared* ties only, so a sweep such as
        ``untie("phases.0.atoms.*.biso")`` releases what this refinement tied
        and leaves symmetry alone.  A literal path that is not a user tie is
        refused with the reason — that call meant one specific parameter, and a
        silent no-op would read as success.

        An untied parameter comes back **held** at the value its tie last gave
        it, not free: releasing a constraint is not a decision to refine, and
        :meth:`set_vary` is where that decision is spelled.
        """
        globs = [paths] if isinstance(paths, str) else list(paths)
        import fnmatch

        hits = [p for p in self._ties
                if any(fnmatch.fnmatchcase(p, g) for g in globs)]
        table = self._working_table()
        known = {e.path: e for e in table.entries}
        for glob in globs:
            if not is_literal_path(glob) or glob in hits:
                continue
            entry = known.get(glob)
            if entry is None:
                raise ValueError(f"unknown parameter path: {glob!r}")
            if entry.tie is not None:
                raise ValueError(
                    f"{glob!r} is tied by symmetry, not by this refinement, and "
                    "cannot be released")
            raise ValueError(f"{glob!r} is not tied")
        if not hits:
            return []
        for path in hits:
            del self._ties[path]
            if path in self._applied_ties:
                # a register entry symmetry has since taken over is dropped from
                # the register and left alone on the table: releasing it there
                # would strip the space group's tie for one build
                table.set_tie(path, None)
        self._commit_tie_edit(table, ties={}, untied=hits)
        return hits

    # ------------------------------------------------------------------
    # caller-declared holds (WP-1435)
    # ------------------------------------------------------------------
    def hold(self, path_globs: list[str] | str) -> list[str]:
        """Declare that these parameters do not move, whatever a plan asks.

        Dot-path globs with fnmatch semantics, exactly as :meth:`set_vary` and
        a stage's ``turn_on`` (``"phases.*.cell.*"``).  Returns the paths this
        call **newly** held, sorted, and records a ``set_hold`` node carrying
        them.  A second call over the same glob returns ``[]`` and records
        nothing, having changed nothing; an unknown literal path raises, while
        a pattern matching none is an empty sweep rather than an error.

        **This is not ``set_vary(paths, False)``.**  A plan *replaces* the
        vary flags rather than continuing them (WP-1208), so a stage whose
        ``turn_on`` matches a pinned path frees it and refines it.  Before
        this verb existed there was no way to say otherwise: the value moved
        while the model still read ``vary=False``, and nothing reported which
        declaration had won (issue #211).  A hold outranks the glob, and a
        stage that matched one records it on ``StageResult.blocked_by_hold``
        and raises ``HOLD_BLOCKED_PLAN``.

        The case it is for is calibrate-on-a-certified-standard.  Holding the
        certificate's cell is what decorrelates the zero, the displacement and
        the profile terms, so a plan that frees that cell leaves a calibration
        that is worthless and looks clean::

            ref.hold("phases.0.cell.*")
            ref.fit(data, plan="lab_calibrate")

        Structurally fixed rows are marked and say so with their own reason
        first, because ``unhold`` cannot lift a space group.  A held parameter
        stops being free at once, since a declaration that took effect only at
        the next stage would be honoured by everything except the solve
        already running.

        A series declares its holds through the per-pattern ``constrain``
        hook, the way it declares its ties: a hold lives on the
        ``Refinement``, and ``refine_sequential`` builds one of those per
        pattern (WP-1441).
        """
        globs = [path_globs] if isinstance(path_globs, str) else list(path_globs)
        table = self._working_table()
        known = {e.path for e in table.entries}
        for glob in globs:
            if not is_literal_path(glob) or glob in known:
                continue
            raise ValueError(f"unknown parameter path: {glob!r}")
        hits = sorted(p for p in known
                      if any(fnmatch.fnmatchcase(p, g) for g in globs))
        new = [p for p in hits if p not in self._user_holds]
        if not new:
            return []
        self._user_holds.update(new)
        table.set_held(new, True)
        self._commit_hold_edit(table, held=new, unheld=[])
        return new

    def unhold(self, path_globs: list[str] | str) -> list[str]:
        """Take back a hold.  Returns the paths released, sorted.

        Globs match against the **declared** holds only, so a sweep such as
        ``unhold("phases.0.cell.*")`` releases what this refinement held and
        cannot reach anything the space group fixed.  A literal path that is
        not held is refused with the reason, exactly as :meth:`untie` refuses
        one that is not tied: that call meant one parameter, and a silent
        no-op would read as success.

        A released parameter comes back **fixed** at its current value, never
        free.  Withdrawing a declaration that something must not move is not a
        decision to move it, and :meth:`set_vary` is where that decision is
        spelled.
        """
        globs = [path_globs] if isinstance(path_globs, str) else list(path_globs)
        hits = sorted(p for p in self._user_holds
                      if any(fnmatch.fnmatchcase(p, g) for g in globs))
        literals = [g for g in globs
                    if is_literal_path(g) and g not in hits]
        if literals:
            known = {e.path for e in self._working_table().entries}
            glob = literals[0]
            raise ValueError(
                f"{glob!r} is not held by this refinement" if glob in known
                else f"unknown parameter path: {glob!r}")
        if not hits:
            return []
        # the register first, so the table this rebuilds comes back without
        # them: ``_working_table`` re-applies whatever ``_user_holds`` holds
        self._user_holds.difference_update(hits)
        self._commit_hold_edit(self._working_table(), held=[], unheld=hits)
        return hits

    def _commit_hold_edit(self, table: ParameterTable, *,
                          held: list[str], unheld: list[str]) -> None:
        """Land a hold edit: the free set follows, a node is added.

        No ``_write_back`` and no ``refresh_ties``, unlike
        :meth:`_commit_tie_edit`: a hold moves no value, so there is nothing
        for a dependent to follow and nothing new to write into the models.
        The free set can move — holding a free parameter fixes it — so it is
        re-read here, and that is also why the fit is invalidated: an esd
        measured with the parameter free no longer describes this state.
        """
        self._free_paths = list(table.free_paths)
        self._invalidate_fit()
        if self.history is None:
            return
        node = self.history.add(
            parents=[self._head_id] if self._head_id else [],
            action=NodeAction(kind="set_hold", held=list(held),
                              unheld=list(unheld)),
            state=self.snapshot())
        self._head_id = node.id

    def _declare_ties(self, spec: "dict[str, tuple[list[tuple[str, float]], float]]"
                      ) -> list[str]:
        """Validate and apply ``{target: (terms, offset)}`` as one move.

        ``terms`` is the ``(path, coefficient)`` list the affine block has
        always held; a single-source tie arrives here as a one-entry list, so
        there is no second path through the checks for it.
        """
        table = self._working_table()
        for path, (terms, offset) in spec.items():
            entry = self._tie_entry(table, path, role="target")
            implied = offset
            for source, scale in terms:
                if path == source:
                    raise ValueError(f"{path!r} cannot be tied to itself")
                if scale == 0.0:
                    # one term at zero is the whole tie, and its sentence is
                    # the pre-WP-1119 one, byte for byte; among several it is
                    # a term that says nothing, and the fix is to drop it
                    raise ValueError(
                        f"a tie with scale 0 fixes {path!r} at {offset}; that "
                        "is set_values, and it says so in the history"
                        if len(terms) == 1 else
                        f"the term on {source!r} has coefficient 0, so this "
                        f"tie does not depend on it; drop the term")
                implied += scale * self._tie_entry(
                    table, source, role="source").value
            if not (entry.lo <= implied <= entry.hi):
                raise ValueError(
                    f"the tie puts {path}={implied:g} outside its bounds "
                    f"[{entry.lo}, {entry.hi}]")
        specs = {path: TieSpec(terms=list(terms), const=offset, user=True)
                 for path, (terms, offset) in spec.items()}
        # **The table first, the register second, and never interleaved.**
        # ``set_tie`` rebuilds the affine block, which raises on a cycle — now
        # reachable through a user's own ties, since WP-1119 lets a variable be
        # a tied source.  Interleaved, a group whose *second* target closes a
        # cycle left the first one in ``self._ties`` with no history node and no
        # table: half a ``tie_equal``, applied by a call that reported failure.
        # The table is thrown away on the raise, so writing it first costs
        # nothing and makes the declaration the single move it says it is.
        for path, (terms, offset) in spec.items():
            table.set_tie(path, AffineTie(terms=tuple(terms), const=offset))
        self._ties.update(specs)
        self._commit_tie_edit(table, ties=specs, untied=[])
        return list(spec)

    def _commit_tie_edit(self, table: ParameterTable, *,
                         ties: dict[str, TieSpec], untied: list[str]) -> None:
        """Land a tie edit: values follow, models are written, a node is added."""
        table.refresh_ties()  # a new dependent takes its source's value at once
        self._write_back(table)
        self._free_paths = list(table.free_paths)
        # the fitted curve, its statistics and its esds all described a model
        # with a different parameter count
        self._invalidate_fit()
        if self.history is None:
            return
        node = self.history.add(
            parents=[self._head_id] if self._head_id else [],
            action=NodeAction(kind="set_tie", ties=ties, untied=list(untied)),
            state=self.snapshot())
        self._head_id = node.id

    def suggest(self, data: PatternData, *, top_n: int = 5,
                include: "str | list[str]" = "*",
                exclude: "list[str] | tuple[str, ...]" = (),
                mode: Mode | None = None,
                two_theta_limits: tuple[float, float] | None = None,
                report=None) -> "SuggestionResult":
        """Which held parameter should be freed next?  Ranked, gated, read-only.

        Every held-but-refinable parameter (the :meth:`parameters` surface:
        locked, tied and mode-fixed rows never enumerate) matching
        ``include``/``exclude`` is scored by its exact Gauss-Newton
        one-parameter gain at the current state — one combined probe table
        (free ∪ candidates), one Jacobian build, no solve — then gated for
        absorption by the free set and grouped by pairwise collinearity, so a
        tie comes back as one unresolved :class:`CandidateGroup`, never a
        confident winner (:meth:`SuggestionResult.best_or_none` returns
        ``None`` rather than defend one).

        Read-only means literally: the probe table is applied to **deep
        copies** of the models before compiling, no history node is recorded
        (*considering* freeing is not a refinement move), and
        ``result_``/working state are untouched.

        Candidates sitting on a transform floor are probed from their
        family's stage seed (``seeded=True``, ``seed_value`` says from
        where), and the seeds live in a **second** build whose only
        contribution is those candidates' columns: the residual, the free
        block and every live column come from the unseeded current state.
        Measured on the layers suite's truth fixture, seeding the shared
        state instead broadens every peak, moves the probe χ²_red from ~1 to
        7.1, and hands every width parameter a spurious gain ≈ 3×10⁴ at a
        converged fit — the confident wrong answer this method exists to
        never give.  ``chi2_red`` and ``noise_floor`` are therefore the
        *current state's*, seeds excluded.

        ``report`` takes a :class:`~rietx.report.FitReport` (or its
        ``suggested_actions``): candidates whose path matches an action's
        paths are annotated with the action's kind — two independent methods
        agreeing.  Layer 2 speaks a closed template vocabulary while the
        leverage ranking covers every table entry, so a top candidate with no
        ``action_kind`` (an instrument width, an atom DOF) is an expected
        disagreement, not an inconsistency.
        """
        from .params.transforms import dphys_dinternal
        from .strategy.suggest import (
            SUGGEST_SEED_ROUGHNESS,
            SUGGEST_SEED_SOFTPLUS,
            SUGGEST_SEED_STEPHENS,
            Candidate,
            build_suggestion,
        )

        mode = mode or self._mode
        limits = two_theta_limits or self._two_theta_limits
        includes = [include] if isinstance(include, str) else list(include)
        excludes = list(exclude)

        table = self._working_table()
        # the free block must be the set a stage in `mode` would actually
        # leave free — mirror _run_stage's mode-fixed drop
        reach = table.column_reach()
        for path in [p for p in table.free_paths
                     if mode_fixed_column(reach.get(p, [p]), mode)]:
            table.set_vary([path], False)
        free_before = set(table.free_paths)

        import fnmatch

        cand_paths = [
            row.path for row in self.parameters(mode=mode)
            if row.refinable and not row.vary
            and any(fnmatch.fnmatchcase(row.path, g) for g in includes)
            and not any(fnmatch.fnmatchcase(row.path, g) for g in excludes)]
        if cand_paths:
            table.set_vary(cand_paths, True)

        from .optimize.least_squares import _jacobian_for, _make_residual

        n_data = [0]

        def probe():
            """Compile the table's state on model copies; return (jac, resid, x0)."""
            structure = self.structure.model_copy(deep=True)
            instrument = self.instrument.model_copy(deep=True)
            table.apply_to_models(structure, instrument)
            model = compile_model(structure, instrument, data, mode=mode,
                                  two_theta_limits=limits,
                                  moving_paths=set(table.moving_paths))
            carried = False
            if (self._model is not None and mode in ("lebail", "pawley")
                    and self._model.mode == mode):
                _carry_lebail(self._model, model)
                carried = True
            elif mode in ("lebail", "pawley") and self._pending_reflections:
                # a checkout's pending intensities seed the probe too — but
                # they stay pending: the next *stage* consumes them, not this
                _restore_lebail(self._pending_reflections, model)
                carried = True
            cycles = Stage("suggest", []).lebail_cycles
            if mode == "lebail":
                model.lebail_update(table.decode(table.x0()), n_cycles=cycles)
            elif mode == "pawley":
                if not carried:
                    model.lebail_update(table.decode(table.x0()),
                                        n_cycles=cycles)
                model.build_pawley_restraint()
            x0 = table.x0()
            if model.pawley is not None:
                x0 = np.concatenate([x0, model.pawley_x0()])
            n_data[0] = len(model.tt)
            return (_jacobian_for(model, table, self._backend)(x0),
                    _make_residual(model, table)(x0), x0)

        # build 1 — the honest current state: residual, free block, and every
        # candidate column whose physical derivative is quotable there
        jac, resid, x0 = probe()
        fp = table.free_paths

        # build 2 — floor candidates only.  A softplus column at its floor is
        # fp noise (dp/du ≈ 1e-12 puts the chain's perturbation below the
        # model's own rounding), a Stephens block at S ≡ 0 has √'s unbounded
        # slope, and Suortti roughness at b = 0 is the identity with a column
        # of exact zeros — so those columns (and only those) are taken from
        # the seeded state a stage would actually start such a solve at.
        seeded: dict[str, float] = {}
        rough = [p for p in cand_paths
                 if p.startswith("instrument.geometry.surface_roughness.")]
        for p in table.seed_softplus(rough, SUGGEST_SEED_ROUGHNESS):
            seeded[p] = SUGGEST_SEED_ROUGHNESS
        for p in table.seed_softplus(cand_paths, SUGGEST_SEED_SOFTPLUS):
            seeded[p] = SUGGEST_SEED_SOFTPLUS
        strain = [p for p in cand_paths if ".microstrain.dof." in p]
        entries = {e.path: e for e in table.entries}
        for p in table.seed_stephens(strain, SUGGEST_SEED_STEPHENS):
            seeded[p] = entries[p].value
        if seeded:
            jac2, _, x2 = probe()
            for i, p in enumerate(fp):
                if p in seeded:
                    jac[:, i] = jac2[:, i]
                    x0[i] = x2[i]  # dp/du is the seeded point's too
        free_idx = [i for i, p in enumerate(fp) if p in free_before]
        # in Pawley mode the intensity block co-refines with anything, so it
        # belongs to the free block, not to the candidates
        free_idx += list(range(len(fp), jac.shape[1]))
        candidates = [
            Candidate(path=p, index=i,
                      dp_du=dphys_dinternal(float(x0[i]), entries[p].transform),
                      seeded=p in seeded, seed_value=seeded.get(p))
            for i, p in enumerate(fp) if p not in free_before]
        chi2_red = float(resid @ resid) / max(len(resid) - len(free_idx), 1)
        actions = () if report is None else getattr(
            report, "suggested_actions", report)
        # the data rows' serial correlation, which ΔBIC's N must not ignore
        # (#270): the data block leads the row layout, penalty rows after it
        inflation = berar_lelann_factor(resid[:n_data[0]])
        return build_suggestion(jac, resid, free_idx, candidates,
                                chi2_red=chi2_red, top_n=top_n,
                                actions=actions, esd_inflation=inflation)

    @classmethod
    def from_node(cls, tree: RefinementTree, node_id: str, *,
                  backend: str = "numpy", solver: str = "trf") -> "Refinement":
        """Open a refinement positioned at an existing checkpoint."""
        node = tree[node_id]
        ref = cls(node.state.structure, node.state.instrument,
                  backend=backend, solver=solver, history=tree)
        return ref.checkout(node_id)

    def merge(self, other: str, *, prefer: str = "theirs",
              label: str = "") -> str:
        """Three-way merge of another branch into the current state.

        Parameter values are merged per dot-path against the two branches'
        **common ancestor** (git semantics): a path changed on only one side
        takes that side's value; a path changed on both takes ``prefer``
        ("ours" = current head, "theirs" = the merged branch).  The merged
        node records *both* parents — the reason ``HistoryNode.parents`` has
        always been a list.

        Only parameter values merge; the model *composition* (which phases,
        background type, free set, mode) comes from ``prefer``'s side whole —
        merging a phase-added branch into a phase-removed one path-by-path is
        not meaningful.  Returns the merge node's id.
        """
        tree = self._require_history()
        ours_id = self._head_id
        if ours_id is None:
            raise RuntimeError("nothing committed yet on this branch")
        theirs_id = tree.resolve(other)
        base = tree.common_ancestor(ours_id, theirs_id)
        if base is None:
            raise ValueError(f"{ours_id} and {theirs_id} share no ancestor")
        if prefer not in ("ours", "theirs"):
            raise ValueError("prefer must be 'ours' or 'theirs'")

        values_base = tree._values(tree[base])
        values_ours = tree._values(tree[ours_id])
        values_theirs = tree._values(tree[theirs_id])

        # composition from the preferred side
        if prefer == "theirs":
            self.checkout(theirs_id)
        merged = dict(values_ours if prefer == "ours" else values_theirs)
        for path in set(values_base) & set(values_ours) & set(values_theirs):
            b, o, t = values_base[path], values_ours[path], values_theirs[path]
            if o != b and t == b:
                merged[path] = o
            elif t != b and o == b:
                merged[path] = t
            # both changed → keep the preferred side (already in `merged`)

        table = ParameterTable(self.structure, self.instrument)
        self._declare_variables(table)
        for e in table.entries:
            if e.path in merged:
                e.value = merged[e.path]
        self._write_back(table)
        self._invalidate_fit()

        node = tree.add(
            parents=[ours_id, theirs_id],
            action=NodeAction(kind="merge",
                              name=label or f"merge {theirs_id} (prefer {prefer})"),
            state=self.snapshot(), label=label)
        self._head_id = node.id
        return node.id

    def cherry_pick(self, node_id: str, data: PatternData) -> RefinementResult:
        """Re-run another node's *stage action* on top of the current state.

        Takes the recorded action (stage name, turn-on globs, iteration
        budget) — not the recorded parameter values — and executes it from
        here, exactly like ``git cherry-pick`` replays a commit's diff.  This
        is the enabling verb for reusing a refined strategy on a different
        branch (and, in v0.5, on a different sample via
        ``SequentialRefinement``).
        """
        tree = self._require_history()
        node = tree[node_id]
        if node.action.kind != "stage":
            raise ValueError(
                f"{node.id} records a {node.action.kind!r} action; only stage "
                "nodes can be cherry-picked")
        stage = Stage(node.action.name or "cherry-pick",
                      list(node.action.turn_on),
                      max_iter=node.action.max_iter or 100,
                      lebail_cycles=node.action.lebail_cycles or 3,
                      seed=node.action.seed, strain_seed=node.action.strain_seed,
                      restraint_weight_scale=node.action.restraint_weight_scale,
                      ftol=node.action.ftol,
                      window_slack_deg=node.action.window_slack_deg)
        return self.run_stage(data, stage)

    # ------------------------------------------------------------------
    # fitting
    # ------------------------------------------------------------------
    def _prepare_table(self, *, restore: bool) -> ParameterTable:
        table = ParameterTable(self.structure, self.instrument)
        self._declare_variables(table)
        table.set_vary(["*"], False)
        # before the free set, not after: a tied entry never matches set_vary,
        # so restoring first would report every tied path as "no longer exists"
        self._apply_ties(table)
        # and before it for the same reason: a held entry does not match
        # set_vary either, so a hold declared over a path that was free at the
        # time would otherwise be reported as a vanished parameter
        self._apply_holds(table)
        if restore and self._free_paths:
            missing = [p for p in self._free_paths
                       if p not in self._ties and p not in self._user_holds
                       and not table.set_vary([p], True)]
            if missing:
                # set_vary reports no hits for a path that no longer exists
                # (e.g. a phase was removed); dropping it silently would lose
                # refinement state without a trace.
                warnings.warn(
                    f"{len(missing)} restored parameter path(s) no longer exist "
                    f"and were dropped: {missing[:5]}"
                    f"{'…' if len(missing) > 5 else ''}",
                    UserWarning, stacklevel=3)
        return table

    def _record_free_paths(self, table: ParameterTable) -> None:
        """Carry the **declared** free set forward — the current hold included.

        A hold (WP-1301) is one stage's answer to what the data can see, not a
        change to what the caller asked to refine, so it must not survive into
        the state a checkout or a later ``run_stage`` restores: that would turn
        one stage's measurement into a permanently fixed parameter, and the
        phase would then stay unrefined in the very pattern where it appears.

        Entry order, because the restore in :meth:`_prepare_table` replays
        ``set_vary`` one path at a time and the cell-before-λ ordering is
        load-bearing there (``ParameterTable._cell_is_free``).
        """
        held = set(self._held)
        self._free_paths = [e.path for e in table.entries
                            if e.vary or e.path in held]

    @contextmanager
    def _abandon_on_cancel(self, cancel, stage_name: str, completed: list, stream):
        """Make "the in-flight stage is abandoned" literally true.

        A stage writes to ``self.structure``/``self.instrument`` *before*
        solving — the between-stage recompile needs the freed values in the
        models, and a seeding stage (extinction's softplus lift, the Stephens
        isotropic ray) changes them.  Without restoring, a cancelled stage would
        leave that seed behind: half a stage, and exactly the kind of state
        nobody would think to look for.  The parameter table and the history
        node need no undoing — the table is local to the run and is committed
        only after a solve returns, so cancelling simply means neither happens.

        The copies are taken only when a token is present. That used to mean an
        ordinary fit paid nothing, and since WP-1405 it means a fit that
        declined telemetry pays nothing: a recorded run gets a token whether or
        not the caller passed one, because that is what the watcher's stop
        button acts on. Measured before it was spent — two copies a stage is
        132 µs at 2 atoms and 19.3 ms at 1024, which is 1.002-1.004× on the
        three-stage synthetic fit and a 0.19 s bound over ten stages at 1024
        atoms, against a fit whose evaluations alone run to minutes.
        """
        if cancel is None:
            yield
            return
        saved = (self.structure.model_copy(deep=True),
                 self.instrument.model_copy(deep=True), list(self._held))
        try:
            yield
        except RefinementCancelled as exc:
            self.structure, self.instrument, self._held = saved
            exc.stage = exc.stage or stage_name
            exc.completed_stages = list(completed)
            exc.node_id = self._head_id
            if stream is not None:
                # the stage really did end, so it gets a stage_end — with no
                # costs, because an abandoned stage has no outcome to report
                stream.emit("stage_end", stage=exc.stage, status="cancelled")
            raise

    def _run_stage(self, stage: Stage, data: PatternData, mode: Mode,
                   table: ParameterTable, model: CompiledModel | None,
                   two_theta_limits: tuple[float, float] | None,
                   correlation_guard: float, events=None, cancel=None,
                   stage_index: int = 1, n_stages: int = 1,
                   ftol: float | None = None):
        """One stage: free params, recompile, solve, commit, guard.

        The recompile is what keeps the residual smooth *within* the stage —
        the hkl list, symmetry-op subsets, FCJ node counts and windows are
        frozen here and never move until the next stage.
        """
        freed = table.set_vary(stage.turn_on, True)
        # What the glob matched and the hold refused (WP-1435).  Read off the
        # table rather than re-globbing the register, so it names the paths
        # that are held *on this model* and cannot disagree with what
        # ``set_vary`` just did.  A stage that frees nothing held records an
        # empty list, which is every stage of every fit that declares no hold.
        blocked_by_hold = sorted(
            e.path for e in table.entries
            if e.held and e.tie is None and not e.locked
            and any(fnmatch.fnmatchcase(e.path, g) for g in stage.turn_on))
        # What the stage asked for by name and the model does not have
        # (WP-1414).  A literal only: a pattern matching nothing is how the
        # shipped plans reach components a model may not declare, so it stays
        # silent, while a literal names one parameter and missing it is a
        # typo or a rename.  Recorded, never raised — one plan runs a whole
        # series, and a path one pattern's model lacks must not end the chain.
        unknown_paths = table.unknown_literals(stage.turn_on)
        if self._held:
            # lift the previous stage's hold before this one decides its own:
            # a phase invisible then may be plain now, and a cumulative plan
            # need not name its cell again for it to keep refining
            table.set_vary(self._held, True)
            self._held = []
        if stage.seed:
            # lift softplus coefficients (e.g. extinction) off the zero floor
            # so TRF has a live gradient this stage
            table.seed_softplus(freed, stage.seed)
        if stage.strain_seed:
            # the Stephens DOFs are identity-transform, so the softplus seed
            # above never sees them; put an all-zero block on the isotropic ray
            table.seed_stephens(freed, stage.strain_seed)
        if mode in ("lebail", "pawley"):
            # never refine structural parameters, the phase scale (degenerate
            # with the per-hkl intensities) or the line-intensity ratio (which
            # those intensities can absorb pairwise) against the intensity
            # model; drop them from the reported freed list too — it must
            # describe the set actually left free.  By what the column *moves*
            # since WP-1342, so a tie cannot carry one past the drop.
            reach = table.column_reach()
            for path in list(freed):
                if mode_fixed_column(reach.get(path, [path]), mode):
                    table.set_vary([path], False)
                    freed.remove(path)

        # regenerate reflection list/windows/FCJ nodes with current values
        # (between-stage refresh; frozen within the stage); the free-path
        # set lets the compiler allocate FCJ nodes for axial parameters
        # that are about to refine from zero
        self._write_back(table)
        new_model = compile_model(
            self.structure, self.instrument, data, mode=mode,
            two_theta_limits=two_theta_limits,
            moving_paths=set(table.moving_paths),
            # eq (7)'s c_w for this stage: frozen onto the model here, with the
            # hkl list and the windows, because a schedule reweights the
            # restraints *between* stages and never inside one (WP-1074)
            restraint_weight_scale=stage.restraint_weight_scale,
            # the stage's declared window capture slack (WP-1112): the same
            # frozen-at-compile shape as c_w, and None for every plan that
            # does not state one
            window_slack_deg=stage.window_slack_deg)
        carried = False
        if model is not None and mode in ("lebail", "pawley") and model.mode == mode:
            _carry_lebail(model, new_model)
            carried = True
        elif mode in ("lebail", "pawley") and self._pending_reflections:
            # first stage after a checkout: re-seed the per-hkl intensities
            _restore_lebail(self._pending_reflections, new_model)
            carried = True
        self._pending_reflections = []
        model = new_model

        if mode == "lebail":
            values = table.decode(table.x0())
            model.lebail_update(values, n_cycles=stage.lebail_cycles)
        elif mode == "pawley":
            if not carried:
                # seed the intensity block from one Le Bail partition — a good
                # warm start for the joint solve; refined values carry onward
                model.lebail_update(table.decode(table.x0()), n_cycles=stage.lebail_cycles)
            # equal-split restraint on overlapped groups, scaled to the current
            # intensities (constant within the coming least-squares run)
            model.build_pawley_restraint()

        # A phase the data cannot see is a flat direction, and holding it is
        # cheaper and truer than bounding it (WP-1301).  Decided *after* the
        # compile, so the frozen state — windows, FCJ node counts, off-state
        # gates — was sized with these parameters still in ``moving_paths``:
        # a superset claim, which is the safe direction and is what lets the
        # release below free them again inside the same stage.
        # ``freed`` is recomputed from this whenever the hold moves, so that
        # ``StageResult.freed`` and ``.held`` stay disjoint however the stage
        # ends: a path this stage freed and then held — at the start, or after
        # a mid-stage collapse — did not refine, and one it held and released
        # did.  Derived rather than patched, because a collapse and a release
        # can happen in the same stage.
        declared_freed = list(freed)
        # Two holds, and they answer different questions of the same stage: a
        # phase the data cannot see at all (WP-1301), and a moment *direction*
        # the powder average cannot determine (WP-1327).  Both are flat
        # directions, both are taken after the compile at the values the stage
        # starts from, and both go into ``StageResult.held`` so the report can
        # say which and why.
        held, held_reach = _hold_unsupported_phases(model, table)
        # kept apart, because the release below judges each hold by its own
        # question: a moment DOF the *phase* hold took (every free structural
        # path of an invisible phase, ``moment.dof0`` included) stays with the
        # phase, and only what this probe itself held is asked again as a
        # direction (review of #433, finding 2)
        moment_hold = _hold_flat_moments(model, table)
        held = held + moment_hold
        if held:
            held_set = set(held)
            freed = [p for p in declared_freed if p not in held_set]
        self._held = list(held)

        if events is not None:
            events.emit("stage_start", stage=stage.name, turn_on=list(stage.turn_on),
                        freed=freed, n_free=len(table.free_paths),
                        free_paths=list(table.free_paths),
                        # open dict, so no EVENT_SCHEMA_VERSION bump: an
                        # existing kind gaining a field is additive by the rule
                        # in history/events.py
                        held=list(held),
                        # at stage start, where a watcher can see the typo
                        # before the stage it emptied has spent its budget
                        unknown_paths=list(unknown_paths),
                        n_points=len(model.tt),
                        index=stage_index, n_stages=n_stages)
        # ftol is passed only when there is one to pass, so a stage with no
        # schedule keeps the solver default from one authority (the runner's
        # signature).  *Which* tolerance this is was decided by the caller:
        # RefinementPlan.stage_ftols for a plan, the stage's own for the
        # single-stage verb, which has no plan and therefore no notion of last.
        stage_ftol = {} if ftol is None else {"ftol": ftol}
        # what the stage starts from, kept for the collapse case below
        start_values = table.decode(table.x0())
        outcome = run_least_squares(model, table, max_iter=stage.max_iter,
                                    events=events, stage=stage.name,
                                    backend=self._backend, solver=self._solver,
                                    cancel=cancel, **stage_ftol)
        table.commit(outcome.theta)
        # A phase's own support can stay comfortably above PHASE_SUPPORT_SIGMA
        # the whole time and its cell still walk to nonsense — a joint
        # degeneracy with another free phase's cell, invisible to the
        # per-phase test above (CELL_SAFETY_FRACTION's docstring).  Checked
        # and corrected once, on the outcome, never as a bound the solver saw.
        cell_runaway = clamp_cell_runaway(table, start_values)
        # A caller's free ``vars.X`` can drive a cell the same way and is
        # invisible to the clamp above by construction (review of #385
        # finding 1) — named here instead, never silently passed through.
        cell_runaway_unresolved = _vars_driven_cell_escapes(table, start_values)
        if cell_runaway:
            table.refresh_ties()
            # ``table.commit`` above wrote ``outcome.theta`` into
            # ``Entry.value``, and the clamp above just wrote past it again
            # directly on the entries — ``outcome.theta`` itself never
            # changed, so every reader downstream that decodes *it* (this
            # stage's own lebail/guard/event uses, and ``_build_result`` at
            # the end of ``fit()``) would silently see the pre-clamp cell
            # while ``RefinedParameter.value`` (read off these same entries)
            # reports the clamped one.  ``table.x0()`` is the encoder inverse
            # of ``decode`` over the free columns (round-trips through the
            # same ``to_internal``/``to_physical`` pair `decode` uses), so
            # re-deriving it here is a re-encoding of the committed table,
            # not a second source of truth.
            outcome = dataclasses.replace(outcome, theta=table.x0())

        # Support is a fact about the values, and a stage moves them.  So the
        # measurement is taken again at the answer, and it can have moved
        # either way: a held phase that has *appeared* (its scale stayed free
        # precisely so it could), or a phase that looked visible at stage start
        # and **collapsed** while solving.  The second is the case a start-of-
        # stage test cannot see, and the one the in-situ ramp actually hit: its
        # CaF₂ was seeded at scale 1e-4, so it began every pattern well above
        # the noise, and the flat direction opened up only as the solver drove
        # that scale to nothing.
        # one measurement, two questions — the release and the collapse are
        # complementary readings of the same ``phase_support`` vector
        support = model.phase_support(table.decode(table.x0()))
        # the moment holds are asked of the answer separately: they are about a
        # direction rather than a phase, so ``_released_phases``'s prefix test
        # would release them for the wrong reason — a phase rising above the
        # noise says nothing about whether its moment direction became
        # determinable.  *Which* paths are moment holds is what
        # ``_hold_flat_moments`` returned, never a name match on ``held``: the
        # phase hold takes an invisible phase's moment DOFs too, and read by
        # name those went to the direction probe, which skips ``dof0`` and so
        # released the modulus of a phase the data still could not see.
        moment_held = [p for p in held if p in set(moment_hold)]
        phase_held = [p for p in held if p not in set(moment_hold)]
        # the hold's reach travels with it: a held ``vars.X`` names no phase,
        # and asking the table now would get nothing back (WP-1342)
        released = (_released_phases(model, table, phase_held, support, held_reach)
                    if phase_held else [])
        if moment_held:
            still_flat = set(_flat_moment_paths(model, table, moment_held))
            released = released + [p for p in moment_held if p not in still_flat]
        # the same question the hold asked, asked again of the answer: what is
        # free now and belongs to a phase the data cannot see, and what moment
        # direction went flat while the stage ran
        collapsed = (_unsupported_phase_paths(model, table, support)
                     + _flat_moment_paths(model, table))
        if released or collapsed:
            if collapsed:
                # Restore before holding: those values moved in a direction the
                # data cannot see, and the restore is invisible to the data by
                # the very measurement that licences the hold — a phase under
                # 1σ contributes under 1σ wherever its peaks sit, since the
                # height is scale·|F|²·profile and the cell only moves them.
                # Without it the stage would freeze the walk it was trying to
                # prevent (measured on the ramp: cells at 20.3 Å and −6.5 Å).
                by_path = {e.path: e for e in table.entries}
                for path in collapsed:
                    by_path[path].value = start_values[path]
                table.refresh_ties()  # dependents follow (b←a on a cubic cell)
                # read while they are still columns, as at stage start
                held_reach.update(_reach_beyond_self(table, collapsed))
                table.set_vary(collapsed, False)
                held = held + collapsed
            if released:
                released_set = set(released)
                table.set_vary(released, True)
                held = [p for p in held if p not in released_set]
            self._held = list(held)
            held_set = set(held)
            freed = [p for p in declared_freed if p not in held_set]
            # a released column is not held, so its reach is not this record's
            held_reach = {c: v for c, v in held_reach.items() if c in held_set}
            if events is not None:
                # The resumed half gets its own ``stage_start``, because an
                # ``eval``'s ``values`` are declared to align with
                # ``stage_start.free_paths`` and this solve has a different
                # free vector from the first.  Same stage, same index — a
                # reader aligns on the *most recent* one, which is what an
                # indexing run's revisable ladder already asks of it.
                events.emit("stage_start", stage=stage.name,
                            turn_on=list(stage.turn_on),
                            freed=list(released),
                            n_free=len(table.free_paths),
                            free_paths=list(table.free_paths),
                            held=list(held), released=list(released),
                            # the reader aligns on this, the most recent one,
                            # so it repeats what the first stage_start said
                            unknown_paths=list(unknown_paths),
                            n_points=len(model.tt),
                            index=stage_index, n_stages=n_stages)
            # Once — never a third solve, whichever way the measurement moved,
            # so the cost of a wrong hold is bounded at one stage's budget.
            second = run_least_squares(
                model, table, max_iter=stage.max_iter, events=events,
                stage=stage.name, backend=self._backend,
                solver=self._solver, cancel=cancel, **stage_ftol)
            table.commit(second.theta)
            second_runaway = clamp_cell_runaway(table, start_values)
            if second_runaway:
                table.refresh_ties()
                cell_runaway = cell_runaway + second_runaway
                # same re-derivation as the first clamp above, on ``second``
                # rather than ``outcome`` — the merge just below carries
                # ``second``'s ``theta`` field forward untouched otherwise.
                second = dataclasses.replace(second, theta=table.x0())
            # same measurement as the first solve, re-taken on the values the
            # collapse-restore's own second solve landed on -- merged by
            # driver rather than concatenated, so a driver still escaping
            # after both solves is named once, not twice
            merged = dict(cell_runaway_unresolved)
            for driver, escaped in _vars_driven_cell_escapes(table, start_values):
                merged[driver] = sorted(set(merged.get(driver, [])) | set(escaped))
            cell_runaway_unresolved = list(merged.items())
            # the record is one stage: the second solve's answer, the first
            # solve's starting cost, and the iterations of both — the whole
            # point being that the hold cost something and it must be visible
            # where the budget is read
            outcome = dataclasses.replace(
                second, cost_initial=outcome.cost_initial,
                n_iterations=outcome.n_iterations + second.n_iterations,
                n_constraint_truncations=(outcome.n_constraint_truncations
                                          + second.n_constraint_truncations))

        if mode == "lebail":
            model.lebail_update(table.decode(outcome.theta), n_cycles=stage.lebail_cycles)

        guard = check_guards(table, outcome, correlation_guard, model=model,
                             scan_exchangeability=stage_index == n_stages)
        if events is not None:
            # a real number, not the raw least-squares cost: additive on the
            # existing kind (history/events.py's rule), paid only when a
            # caller asked for events at all — one forward evaluation, not a
            # fit, the same pattern _record uses for a history node's metrics.
            # background(values) computed once and reused, never twice —
            # evaluate() is background [+ extra_peak_curve] + bragg_component
            # internally, so calling both would price this at two background
            # passes.  The sum is therefore evaluate()'s, restated in its own
            # association order: a declared peak is in the model the stage
            # fitted but not in background(), and leaving it out made every
            # stage Rwp that of a model with the peaks deleted (#441); a model
            # declaring none keeps the two-term sum, bit for bit.
            values = table.decode(outcome.theta)
            y_bkg = model.background(values)
            y_stage = (y_bkg + model.bragg_component(values)
                       if not model.peak_components else
                       y_bkg + model.extra_peak_curve(values)
                       + model.bragg_component(values))
            stage_rwp = compute_statistics(
                model.y_obs, y_stage, model.sigma,
                n_free=len(table.free_paths) + _pawley_n(model),
                y_background=y_bkg).rwp
            events.emit("stage_end", stage=stage.name, status=outcome.status,
                        n_iterations=outcome.n_iterations,
                        termination=outcome.termination,
                        cost_initial=outcome.cost_initial,
                        cost_final=outcome.cost_final, rwp=stage_rwp,
                        held=list(held), released=list(released))
        return model, outcome, guard, freed, _StageHold(
            held=list(held), released=list(released),
            reach={c: list(v) for c, v in held_reach.items()},
            blocked_by_hold=blocked_by_hold, unknown_paths=unknown_paths,
            cell_runaway=list(cell_runaway),
            cell_runaway_unresolved=[(d, list(e)) for d, e in cell_runaway_unresolved])

    def fit(self, data: PatternData, *, mode: Mode = "rietveld",
            plan: RefinementPlan | str = "mccusker_default",
            two_theta_limits: tuple[float, float] | None = None,
            events=None, cancel=None, telemetry=None, label: str | None = None,
            stage_reports: bool = False, progress=None) -> RefinementResult:
        """Run a staged refinement.

        ``events`` — optional per-iteration telemetry: a path (JSONL appended),
        a callable (called per event dict), or an
        :class:`~rietx.history.events.EventStream`.  See that module for the
        record format; ``rietx watch`` tails it live.

        ``progress`` — a text stream or path; one line per stage boundary
        (``[series 7/13] 250C stage cell converged Rwp 0.0812 12s`` under
        :func:`refine_sequential`, ``stage cell converged Rwp 0.0812 12s``
        here).  Implemented as an ``events=`` consumer
        (:func:`~rietx.history.events.progress_writer`), never a second
        telemetry channel — combine both freely, ``progress`` adds a
        subscriber rather than replacing ``events``'s.

        ``telemetry`` — where this run records **itself**.  A fit writes its
        events, its status, a per-stage picture and its termination view into a
        run directory whether or not ``events=`` was passed, because the knob
        nobody had to switch on is the one an agent cannot switch off by
        accident (WP-1322 measured three of three doing exactly that).  A path
        names the *root* to put the run directory in; ``False`` declines;
        ``None`` derives one — a project's ``live/`` if this refinement came
        from one, else ``.rietx/runs`` under the working directory.
        :data:`~rietx._about.TELEMETRY_ENV` outranks all of it, and there is
        deliberately no value here that argues back.  Recording never breaks a
        fit: a failure latches, says so in the run's status, and warns once.

        ``label`` — what this run is **called** in ``rietx watch``'s list
        (WP-1431).  Unnamed, a run is called after the directory it ran in, or
        after its project; a batch of forty candidates driven from one
        directory therefore writes forty rows under one name, and only the
        caller knows which candidate each one fitted.  Pass that: the phase, the
        sample, the candidate cell.  It is written to the run's ``meta.json``
        and lives nowhere a result reproduces — telemetry, not a refined
        quantity — so naming a run changes no number the fit produces.

        ``cancel`` — an :class:`~rietx.optimize.cancel.CancelToken` another
        thread can set.  The stage in flight is abandoned (no node, no commit,
        the models restored to their pre-stage values) and
        :class:`~rietx.optimize.cancel.RefinementCancelled` is raised carrying
        the stages that *did* complete and the node the working state stands at.

        ``stage_reports`` — build the report at every stage boundary and leave
        the rungs on :attr:`stage_reports_` (WP-1058).  **Off by default here
        and on at the agent surface**, and the asymmetry is the measurement:
        a report build is ~0.33 s on 59.5k channels against a ~1.0 s five-stage
        fit, so a trajectory costs ≈2.5× the fit — nothing to a consumer that
        calls once and reads, a tax on a library primitive that suites and
        series call in loops.  It changes **no** number the fit produces: the
        rungs are read off states the plan already passes through, never
        states it is made to visit, so a fit run with them lands exactly where
        the same fit run without them does.  (That is also why this is not the
        "declared ladder" WP-1058 set out to build: measured, every shipped
        rietveld preset already opens on a background+scale stage — the
        McCusker turn-on order *is* the bootstrap ladder — so prepending one
        reproduced stage 1's report to three decimals.)
        """
        _refuse_without_phases(self.structure, "fit")
        plan = resolve_plan(plan, mode)
        if not plan.stages:
            # Refused here, before a history tree is created or an event is
            # emitted, because the assertion this replaces fired *after* the
            # run had built both (WP-1110 item 6).  The message names the verb
            # rather than only the mistake: a zero-stage plan is what someone
            # reaches for when they want the model evaluated and not refined,
            # which is exactly what an agent on the trigger dataset did before
            # settling on a one-stage refit used as a "replot".
            raise ValueError(
                "a plan with no stages refines nothing: every stage is a group "
                "of parameters to free, so an empty list frees none. To "
                "evaluate the model as it stands without refining it, call "
                "ref.predict(pattern) — that needs no prior fit. To run a "
                "refinement, name a preset "
                f"({', '.join(sorted(PLAN_PRESETS))}) or list at least one "
                "stage.")

        self._mode = mode
        self._two_theta_limits = two_theta_limits
        self._free_paths = []
        self._held = []
        # state summary() reads for the "protocol actually run" section —
        # nothing computes from these, they are only ever printed back
        self._last_plan = plan
        self._sigma_from_file = data.sigma is not None
        self._excluded_regions = list(data.excluded_regions)
        tree = self._ensure_history(data, plan)
        stream = _attach_progress(as_event_stream(events), progress)
        # Attached beside the caller's stream, never inside it: the recorder
        # has its own lifetime (the try/finally below) and the existing
        # ``stream is not events`` close rule is left exactly as it was.
        recorder = runs.attach(stream, events, telemetry=telemetry,
                               project_hint=self._project_hint(), label=label)
        if recorder is not None and stream is None:
            stream = recorder
        # A recorded run can be stopped from outside the process (WP-1405), and
        # this is the whole of it: the token handed down is the caller's, read
        # through one that also watches the run directory for a request.
        # ``recorder_of`` rather than ``recorder``, because a series attached
        # its own further up and this call declined — and a series that could
        # not be stopped would be the case the button exists for.
        cancel = runs.attach_cancel(runs.recorder_of(stream), cancel)
        # built here, where both the caller's object and the stream we
        # made from it are in scope, and handed down rather than
        # rediscovered per stage. The recorder is a third candidate and not a
        # fourth hasattr test at a call site: chained onto a caller's stream it
        # is a *different* object, which the two-candidate call would have
        # found nothing at all in (WP-1402).
        sinks = _snapshot_sinks(stream, events, recorder)
        try:
            if stream is not None:
                from .project import fitted_mask

                # the fitted count, as every ``stage_start``'s is, and the
                # file's beside it (#441): ``fitted_mask`` is the authority
                # ``compile_model`` is pinned to (WP-1033)
                stream.emit("fit_start", mode=mode,
                            stages=[s.name for s in plan.stages],
                            n_points=int(fitted_mask(data, two_theta_limits).sum()),
                            n_points_file=len(data.two_theta))

            # Stages are cumulative *within the plan*, and the plan drives the whole
            # turn-on sequence: `restore=False` holds everything first, so a fit
            # replaces the vary flags a caller set by hand rather than continuing
            # them (`run_stage`, which continues from the working state, restores
            # them instead).  The comment here said the opposite until WP-1208
            # measured it — `set_vary("phases.*.atoms.*.biso")` then
            # `fit(plan="profile_only")` refines no biso — and the GUI's plan panel
            # now names the difference, since nothing a user could read said it.
            table = self._prepare_table(restore=False)

            # the λ this Refinement was constructed with (or last edited to), so a
            # second λ-freeing call reports the cumulative move from the truly
            # declared value rather than from the first call's answer (WP-1134).
            # Copied, never aliased: ``_build_result`` is only a reader today, but a
            # snapshot handed out by reference is a mutation waiting to happen.
            declared_wavelengths = list(self._declared_wavelengths)

            diagnostics: list[Diagnostic] = (
                _symmetry_silence_diagnostics(self.structure, mode)
                + _dispersion_diagnostics(self.structure, self.instrument)
                + _resonant_absorber_diagnostics(self.structure,
                                                 self.instrument)
                + _species_fallback_diagnostics(self.structure, self.instrument))
            stage_results: list[StageResult] = []
            self.stage_reports_ = []
            outcome = None
            model = None

            try:
                (model, outcome, guard, stage_results, diagnostics,
                 answer_runaway) = self._run_plan(
                    plan, data, mode, table, two_theta_limits, tree, stream, cancel,
                    stage_results, diagnostics, sinks=sinks,
                    stage_reports=stage_reports)
            except RefinementCancelled as exc:
                if stream is not None:
                    stream.emit("fit_end", status="cancelled", stage=exc.stage,
                                completed=[s.name for s in exc.completed_stages],
                                node_id=exc.node_id)
                    if stream is not events:
                        stream.close()
                raise

            assert model is not None and outcome is not None
            self._write_back(table)
            self._record_free_paths(table)
            # the result's curves and statistics from a compile at the values
            # it returns, never the last stage's start-of-stage one (#272)
            model, recompiled = self._final_compile(
                model, table, outcome, data, mode, two_theta_limits,
                plan.stages[-1])
            diagnostics.extend(recompiled)
            self._model = model

            if mode == "pawley":
                diagnostics.extend(_pawley_unresolved_diagnostics(model, self.structure))
                diagnostics.extend(_pawley_off_data_diagnostics(model, self.structure))
            diagnostics.extend(_constraint_diagnostics(plan.stages[-1].name, outcome))
            diagnostics.extend(_degenerate_cell_diagnostics(
                [(sr.name, sr.n_degenerate_cell_probes) for sr in stage_results]))
            diagnostics.extend(_hold_diagnostics(stage_results))
            diagnostics.extend(_unknown_path_diagnostics(
                stage_results, [e.path for e in table.entries]))

            self.result_ = _build_result(
                model, table, outcome.theta, mode=mode, status=outcome.status,
                stage_results=stage_results, diagnostics=diagnostics,
                structure=self.structure, stderr_internal=outcome.stderr_internal,
                correlation=outcome.correlation, backend=self._backend,
                solver=self._solver,
                mu_r_source=self._mu_r_source, mu_r_skipped=self._mu_r_skipped,
                guard=guard, max_shift_over_esd=outcome.max_shift_over_esd,
                declared_wavelengths=declared_wavelengths,
                cell_runaway=answer_runaway)
            _apply_esds(table, self.result_, self.structure, self.instrument)
            self._stamp(self.result_, tree)
            if stream is not None:
                stream.emit("fit_end", status=self.result_.status,
                            rwp=self.result_.statistics.rwp,
                            gof=self.result_.statistics.gof,
                            node_id=self.result_.node_id)
                if stream is not events:  # we created it from a path/callable
                    stream.close()
            if recorder is not None:
                # Not a projection of the stream, and so a second explicit call
                # site: ``fit_end`` hands a sink a data dict, while the
                # termination view needs the ``RefinementResult`` object. It
                # writes ``str(result)`` and never ``ref.summary()``, which
                # builds a whole FitReport (WP-1335).
                recorder.write_summary(self.result_)
            return self.result_
        except BaseException:
            # A telemetry directory must not turn a raised fit into a run that
            # merely looks abandoned. ``close`` applies a state only when
            # nothing has claimed one, so the ``cancelled`` a ``fit_end``
            # already recorded survives this.
            if recorder is not None:
                recorder.close("failed")
            raise
        finally:
            if recorder is not None:
                recorder.close()

    def _run_plan(self, plan, data, mode, table, two_theta_limits, tree, stream,
                  cancel, stage_results, diagnostics, *, sinks,
                  stage_reports: bool = False):
        """The stage loop of :meth:`fit`, split out so cancellation has one exit.

        Returns ``(model, outcome, guard, stage_results, diagnostics,
        answer_runaway)``; raises :class:`RefinementCancelled` with the
        completed stages attached.  The guard returned is the **last** stage's,
        for the same reason :func:`_constraint_diagnostics` reads only that
        stage: earlier stages measured an intermediate state, and it is the
        answer-producing one whose Jacobian the result's identifiability
        evidence describes.  ``answer_runaway`` is that stage's
        ``CELL_RUNAWAY`` finding (``[]`` or one), for the same reason: it is
        what :func:`_build_result` withholds esds on, while ``diagnostics``
        carries every stage's.

        ``stage_reports`` appends one :class:`~rietx.report.StageReport` per
        completed stage to :attr:`stage_reports_`.  A cancelled run keeps the
        rungs of the stages that *did* complete, for the same reason
        :class:`~rietx.optimize.cancel.RefinementCancelled` carries them:
        the in-flight stage is abandoned, the ones before it happened.

        ``HIGH_CORRELATION`` findings are collected as the loop runs
        (``correlation_hits``) rather than extended straight into
        ``diagnostics`` like every other code: a persistently correlated pair
        fires on every stage that re-measures it, and ``_dedup_high_correlations``
        needs the per-stage attribution to say so.  ``stage_diagnostics`` itself
        — unfiltered, duplicates and all — still goes to :meth:`_stage_report`
        and the history node below: a trajectory rung and a replay both
        describe *that stage's* guard run, not the fit's final summary.

        ``BOUND_HIT`` is held back for a different reason (WP-1310, issue
        #231): it is not deduplicated but **discarded and re-taken**, because
        a bound hit is a statement about a *vector* rather than about a run.
        A staged plan exists to let an early stage absorb an error a later one
        corrects, so a parameter pressed onto its limit in stage 1 and back in
        the interior at convergence is the plan working.  Emitting that stage's
        finding on the final result says "``<path>`` refined to its bound" of a
        fit five orders of magnitude from it — measured on the repo's own
        ``make_lab6`` with a ±0.02° zero shift absorbing a 500 ppm cell error:
        ``zero_shift`` ends at 5.5e-07 with the cell recovered to 4.1565999
        against a truth of 4.15660, and the warning survived.  It cost two
        rounds of misdirected analysis on a real capillary fit.

        ``RESOLUTION_NOT_POSITIVE``, ``BISO_UNUSUALLY_LARGE`` and
        ``RESOLUTION_UNCONSTRAINED`` (WP-1311) are re-taken the same way.  Each
        reads one number off the values its stage landed on, so all three make
        the same kind of claim a bound hit does (``_REVISABLE_CODES`` carries
        the extra clause the third one needs, its free set being cumulative).  A
        plan whose later stages repair the resolution otherwise reports an
        earlier stage's collapse on an answer that is physical: measured on
        ``make_lab6`` from a schema-legal U, V, W with the quadratic negative
        across the scan, the five-stage ``mccusker_default`` converges at
        min Γ_G² = +0.084 deg² and carried four copies of the warning.

        The final guard is therefore the only one that speaks here, which is
        also what makes WP-1076's set-equality true rather than nearly true:
        ``RefinedParameter.at_bound`` has always been projected from
        ``guard.at_bounds`` of the **last** stage (see ``_build_result``),
        so before this the two surfaces of one bound test disagreed inside a
        single result — ``at_bound=False`` on the row, ``BOUND_HIT`` in the
        diagnostics, about the same parameter.  Every stage's own findings
        stay on its ``StageReport`` and its history node, where they describe
        the vector they were measured on.
        """
        model = outcome = guard = None
        ftols = plan.stage_ftols()
        correlation_hits: dict[tuple[str, frozenset],
                              list[tuple[str, Diagnostic]]] = {}
        answer_runaway: list[Diagnostic] = []
        for k, (stage, ftol) in enumerate(zip(plan.stages, ftols, strict=True),
                                          start=1):
            with self._abandon_on_cancel(cancel, stage.name, stage_results, stream):
                model, outcome, guard, freed, hold = self._run_stage(
                    stage, data, mode, table, model, two_theta_limits,
                    plan.correlation_guard, events=stream, cancel=cancel,
                    stage_index=k, n_stages=len(plan.stages), ftol=ftol)
            stage_diagnostics = _guard_diagnostics(guard) + _covariance_diagnostics(
                stage.name, outcome, answer=k == len(plan.stages))
            for d in stage_diagnostics:
                if d.code in ("HIGH_CORRELATION", "FLAT_DIRECTION"):
                    # keyed by code *and* pair: a flat pair fires both, and a
                    # key of the pair alone would let one evict the other
                    correlation_hits.setdefault(
                        (d.code, frozenset(d.where)), []).append((stage.name, d))
                elif d.code in _REVISABLE_CODES:
                    continue          # re-taken on the converged vector below
                else:
                    diagnostics.append(d)
            runaway_diag = _cell_runaway_diagnostic(hold.cell_runaway, hold.cell_runaway_unresolved)
            # the last stage's alone survives the loop: an earlier stage's
            # clamp is re-measured by every later one (staging is cumulative)
            answer_runaway = [] if runaway_diag is None else [runaway_diag]
            if runaway_diag is not None:
                diagnostics.append(runaway_diag)
                stage_diagnostics = stage_diagnostics + [runaway_diag]
            stage_results.append(StageResult(
                name=stage.name, status=outcome.status, n_iterations=outcome.n_iterations,
                cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                freed=freed,
                n_constraint_truncations=outcome.n_constraint_truncations,
                n_degenerate_cell_probes=outcome.n_degenerate_cell_probes,
                ftol=ftol, held=hold.held, released=hold.released,
                held_reach=hold.reach,
                blocked_by_hold=hold.blocked_by_hold,
                unknown_paths=hold.unknown_paths,
                # checked, trivially: one histogram has no elsewhere
                unreached_histograms={},
            ))
            if stage_reports:
                self.stage_reports_.append(self._stage_report(
                    stage.name, plan, data, mode, table, model, outcome, guard,
                    stage_diagnostics))
            for sink in sinks:
                # live monitoring (viz.live.LiveSession): rewrite the snapshot
                sink.write_snapshot(model, table, outcome, stage.name)
            if tree is not None:
                self._write_back(table)
                self._record_free_paths(table)
                self._record(tree, NodeAction(
                    kind="stage", name=stage.name, turn_on=list(stage.turn_on),
                    max_iter=stage.max_iter, lebail_cycles=stage.lebail_cycles,
                    seed=stage.seed, strain_seed=stage.strain_seed,
                    restraint_weight_scale=stage.restraint_weight_scale,
                    # the tolerance this stage *ran* at, not the one it declared
                    # (Stage.ftol is None for every stage taking the plan's
                    # schedule), because a cherry-pick re-runs what happened
                    ftol=ftol, window_slack_deg=stage.window_slack_deg,
                ), model, table, outcome, stage_diagnostics)
        # the converged vector's own findings, and nothing earlier: the same
        # ``guard`` object ``_build_result`` projects ``at_bound`` from
        if guard is not None:
            diagnostics.extend(d for d in _guard_diagnostics(guard)
                               if d.code in _REVISABLE_CODES)
        diagnostics.extend(_dedup_high_correlations(correlation_hits))
        return model, outcome, guard, stage_results, diagnostics, answer_runaway

    def _final_compile(self, model: CompiledModel, table: ParameterTable,
                       outcome, data: PatternData, mode: Mode,
                       two_theta_limits, stage: Stage,
                       ) -> tuple[CompiledModel, list[Diagnostic]]:
        """A compile at the values a result returns, for the result (#272).

        A stage's compile froze its windows and FCJ node counts at the values
        the stage *started* from (root CLAUDE.md § Invariants), so when the
        last stage moves what sized them — λ, zero, the axial terms, the
        widths — the frozen model evaluated at the answer is not the model a
        reader rebuilds from ``result.parameters``: 1.38 % in χ² on the Si SRM
        640c acceptance fixture.  The result's ``y_calc``, statistics and every
        per-point residual are therefore measured here, on one more compile
        with the last stage's own discrete settings (moving set, c_w, window
        slack) and nothing else changed.  **What this does not move**: the
        solve, which ran on the frozen compile and is not biased by it (the
        issue measured the minimum moving ≤ 0.0014 esd); the covariance and
        every esd, which stay those of that solve's Jacobian; the weights,
        which stay the solve's σ, so ``result.sigma`` is still a lookup of the
        σ the model used (WP-1309: a measured background widens σ at the scale
        a compile sees, and a fresh σ would re-weight a result whose esds did
        not); and the history
        node, which keeps its as-optimised metrics, so a node and the result
        it produced differ by the amount ``FROZEN_COMPILE_STALE`` quotes.

        Le Bail intensities are carried by hkl, never re-partitioned.  A Pawley
        model is returned as it is: its intensity block and their esds belong
        to the solve and a compile does not carry them, so a Pawley result is
        still the frozen compile's.

        Returns the model to report from and a ``FROZEN_COMPILE_STALE`` finding
        when the two χ² differ by more than :data:`FROZEN_COMPILE_CHI2_REL`,
        so a caller can see when the frozen windows mattered.
        """
        if mode == "pawley":
            return model, []
        fresh = compile_model(
            self.structure, self.instrument, data, mode=mode,
            two_theta_limits=two_theta_limits,
            moving_paths=set(table.moving_paths),
            restraint_weight_scale=stage.restraint_weight_scale,
            window_slack_deg=stage.window_slack_deg)
        # the solve's weights, never the fresh compile's: a measured
        # background widens σ at the scale a compile sees (WP-1309), so a last
        # stage that moved that scale would re-weight here, and the result
        # would divide by a σ its χ², esds and solve never used
        fresh.sigma = model.sigma
        if mode == "lebail":
            _carry_lebail(model, fresh)
        values = table.decode(outcome.theta)
        chi2_frozen = float(np.sum(
            ((model.y_obs - model.evaluate(values)) / model.sigma) ** 2))
        chi2_fresh = float(np.sum(
            ((fresh.y_obs - fresh.evaluate(values)) / fresh.sigma) ** 2))
        rel = (abs(chi2_fresh - chi2_frozen) / chi2_frozen
               if chi2_frozen > 0 else 0.0)
        if not rel > FROZEN_COMPILE_CHI2_REL:
            return fresh, []
        return fresh, [Diagnostic(
            level="info", code="FROZEN_COMPILE_STALE",
            message=(
                f"the reported statistics and curves come from a compile at "
                f"the returned parameters, chi2 = {chi2_fresh:.6g}; the last "
                f"stage's own compile, whose peak windows and FCJ node counts "
                f"were frozen at the values it started from, gives "
                f"{chi2_frozen:.6g} at the same parameters, "
                f"{100 * rel:.2g} % apart. The fit is not biased by it; the "
                f"history node keeps the frozen figure, the result the fresh "
                f"one, and the esds are the last solve's either way"),
            value=rel)]

    def _stage_report(self, name, plan, data, mode, table, model, outcome,
                      guard, stage_diagnostics) -> StageReport:
        """One trajectory rung: the report at this stage's end (WP-1058).

        The result it reads is transient — built here from the state the stage
        landed on and thrown away — because a rung delivers *statements*, not
        the curves and per-parameter blocks a result carries.  Two choices in
        the arguments are load-bearing:

        **The veto sees the whole plan**, not the stages run so far, so a rung
        answers "what will this plan still not fix?" rather than "what is not
        free yet".  That is what leaves ``refine_sample_displacement`` standing
        at 0.997 on the WP-1053 E2 fixture while the zero and cell suggestions
        beside it are marked as the plan's own later stages.

        **The diagnostics are this stage's**, not the run's accumulated list:
        a rung describes a state, and a guard that fired two stages ago is
        already carried on the result the caller gets back.
        """
        from .report import build_report

        result = _build_result(
            model, table, outcome.theta, mode=mode, status=outcome.status,
            stage_results=[], diagnostics=list(stage_diagnostics),
            structure=self.structure, stderr_internal=outcome.stderr_internal,
            correlation=outcome.correlation, backend=self._backend,
            solver=self._solver, mu_r_source=self._mu_r_source,
            mu_r_skipped=self._mu_r_skipped, guard=guard,
            max_shift_over_esd=outcome.max_shift_over_esd)
        report = build_report(result, model=model,
                              values=table.decode(outcome.theta), plan=plan,
                              structure=self.structure,
                              free_paths=list(table.free_paths))
        return report.for_stage(name)

    def run_stage(self, data: PatternData, stage: Stage, *,
                  mode: Mode | None = None,
                  two_theta_limits: tuple[float, float] | None = None,
                  correlation_guard: float = 0.98,
                  events=None, cancel=None, telemetry=None,
                  label: str | None = None) -> RefinementResult:
        """Run a single stage from the current state, recording a child node.

        This is the incremental verb: after ``checkout``, it continues down a
        new branch.  (``fit`` is the other verb — it resets the free set and
        runs a whole plan from wherever the working state currently is.)

        ``events``, ``cancel``, ``telemetry`` and ``label`` mean exactly what
        they mean on :meth:`fit`, and are here for the same reason the GUI
        exists:
        interactive single-stage work was the one path with no telemetry at all,
        so a client driving stages one at a time was blind to a run it had
        started.  One stage is one run here — a caller driving five stages in a
        row records five, each with its own directory and its own picture, which
        is the honest shape when nothing in the package knows they were meant as
        one job.
        """
        _refuse_without_phases(self.structure, "run_stage")
        mode = mode or self._mode
        ttl = two_theta_limits if two_theta_limits is not None else self._two_theta_limits
        self._mode = mode
        self._two_theta_limits = ttl
        # the trajectory belongs to the last *fit*: one stage on top of it
        # leaves rungs that describe states this one no longer stands on
        self.stage_reports_ = []
        tree = self._ensure_history(data)
        stream = as_event_stream(events)
        recorder = runs.attach(stream, events, telemetry=telemetry,
                               project_hint=self._project_hint(), label=label)
        if recorder is not None and stream is None:
            stream = recorder
        cancel = runs.attach_cancel(runs.recorder_of(stream), cancel)   # WP-1405
        sinks = _snapshot_sinks(stream, events, recorder)

        try:
            table = self._prepare_table(restore=True)
            # the constructed (or last-edited) λ, not the value the previous stage
            # left behind: a second λ-freeing stage reports cumulatively, matching
            # the joint path, rather than a delta from its own predecessor (WP-1134).
            # Copied, never aliased (see fit's call site) — the snapshot stays the
            # construction fact whatever a reader does with the list it is handed.
            declared_wavelengths = list(self._declared_wavelengths)
            try:
                with self._abandon_on_cancel(cancel, stage.name, [], stream):
                    model, outcome, guard, freed, hold = self._run_stage(
                        stage, data, mode, table, self._model, ttl, correlation_guard,
                        events=stream, cancel=cancel,
                        # no plan here, so no notion of an intermediate stage: one
                        # stage run on its own is the state the caller is asking
                        # for, and it takes its own ftol or the solver default
                        ftol=stage.ftol)
            finally:
                if (stream is not None and stream is not events
                        and stream is not recorder):
                    # ...and never the recorder, whose lifetime is the whole
                    # verb.  Closing it here wrote the run's terminal state
                    # before the result existed, so a stage that raised on the
                    # way out — or was cancelled, which reaches here with no
                    # ``fit_end`` to say so — recorded itself ``done``.
                    stream.close()  # we created it from a path/callable
            diagnostics = _guard_diagnostics(guard)
            diagnostics.extend(_covariance_diagnostics(stage.name, outcome,
                                                       answer=True))
            if mode == "pawley":
                diagnostics.extend(_pawley_unresolved_diagnostics(model, self.structure))
                diagnostics.extend(_pawley_off_data_diagnostics(model, self.structure))
            diagnostics.extend(_constraint_diagnostics(stage.name, outcome))
            diagnostics.extend(_degenerate_cell_diagnostics(
                [(stage.name, outcome.n_degenerate_cell_probes)]))
            runaway_diag = _cell_runaway_diagnostic(hold.cell_runaway, hold.cell_runaway_unresolved)
            if runaway_diag is not None:
                diagnostics.append(runaway_diag)

            self._model = model
            self._write_back(table)
            self._record_free_paths(table)

            stage_result = StageResult(
                name=stage.name, status=outcome.status, n_iterations=outcome.n_iterations,
                cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                freed=freed,
                n_constraint_truncations=outcome.n_constraint_truncations,
                n_degenerate_cell_probes=outcome.n_degenerate_cell_probes,
                ftol=stage.ftol, held=hold.held, released=hold.released,
                held_reach=hold.reach,
                blocked_by_hold=hold.blocked_by_hold,
                unknown_paths=hold.unknown_paths, unreached_histograms={})
            # after the StageResult rather than beside the other two extends
            # above, because this one reads the record it has just built; and
            # before the node, so the node carries what the result carries
            diagnostics.extend(_hold_diagnostics([stage_result]))
            diagnostics.extend(_unknown_path_diagnostics(
                [stage_result], [e.path for e in table.entries]))

            # before the node is recorded, which is where `_run_plan` writes it
            # too; the two call sites must not disagree about when a stage's
            # picture appears.  The orders are independent anyway: a watcher reads
            # this directory, and the node goes to the project's history.  A caller
            # driving one stage at a time — report/apply.py's recipes, the GUI's
            # stage verb — used to get events and no picture at all, because this
            # call site did not exist.
            for sink in sinks:
                sink.write_snapshot(model, table, outcome, stage.name)

            if tree is not None:
                self._record(tree, NodeAction(
                    kind="stage", name=stage.name, turn_on=list(stage.turn_on),
                    max_iter=stage.max_iter, lebail_cycles=stage.lebail_cycles,
                    seed=stage.seed, strain_seed=stage.strain_seed,
                    restraint_weight_scale=stage.restraint_weight_scale,
                    ftol=stage.ftol, window_slack_deg=stage.window_slack_deg,
                ), model, table, outcome, diagnostics)

            # after the node, which keeps its as-optimised metrics: the result
            # is measured on a compile at the values it returns (#272)
            model, recompiled = self._final_compile(
                model, table, outcome, data, mode, ttl, stage)
            diagnostics = diagnostics + recompiled
            self._model = model

            self.result_ = _build_result(
                model, table, outcome.theta, mode=mode, status=outcome.status,
                stage_results=[stage_result], diagnostics=diagnostics,
                structure=self.structure, stderr_internal=outcome.stderr_internal,
                correlation=outcome.correlation, backend=self._backend,
                solver=self._solver,
                mu_r_source=self._mu_r_source, mu_r_skipped=self._mu_r_skipped,
                guard=guard, max_shift_over_esd=outcome.max_shift_over_esd,
                declared_wavelengths=declared_wavelengths)
            _apply_esds(table, self.result_, self.structure, self.instrument)
            self._stamp(self.result_, tree)
            if recorder is not None:
                recorder.write_summary(self.result_)
            return self.result_
        except RefinementCancelled:
            # before the generic handler: an abandoned stage is not a failure,
            # and this verb emits no ``fit_end`` for the recorder to read it off
            if recorder is not None:
                recorder.close("cancelled")
            raise
        except BaseException:
            if recorder is not None:
                recorder.close("failed")
            raise
        finally:
            if recorder is not None:
                recorder.close()

    def _stamp(self, result: RefinementResult, tree: RefinementTree | None) -> None:
        if tree is not None:
            result.node_id = self._head_id
            result.tree_id = tree.header.tree_id

    # ------------------------------------------------------------------
    def predict(self, two_theta=None) -> np.ndarray:
        """y_calc at the current parameters — **the evaluate-only path**.

        With a grid — an array of 2θ values, or a
        :class:`~rietx.PatternData` whose 2θ column is used — this compiles a
        fresh model on it and evaluates.  With no argument it evaluates on the
        grid the last fit ran on, which is the one form that needs a fit to
        have happened: nothing else supplies a grid.

        **It does not require a fit** (WP-1110 item 6).  Until then it did, and
        the refusal was ``RuntimeError: call fit() first`` on both forms, which
        is why an agent wanting y_calc at known parameters to redraw a figure
        ended up calling ``set_values(...)`` and then *re-refining* a one-stage
        plan as a "replot".  Evaluating a model is not refining it; the
        parameters are read off the structure and instrument as they stand,
        whether a fit put them there, ``set_values`` did, or they were typed.

        Le Bail and Pawley are the exception that proves it, and they say so:
        their per-hkl intensities live outside θ and are produced by a fit, so
        a fresh grid carries them over from the fitted model by hkl and there
        is nothing to carry before one exists.

        **The two forms are not bit-identical on the same grid, and that is
        the frozen-per-stage invariant rather than a defect.**  ``predict()``
        reuses the model compiled for the last stage, whose per-reflection
        window index ranges were frozen at the values the stage *started*
        from; a grid argument compiles fresh, so the windows are sized at the
        values it *ended* on.  Measured on the synthetic five-stage fit: 36 of
        4200 channels differ at all, by at most 8e-6 of the peak height, every
        one of them in a peak tail at a window edge.  ``RefinementResult.y_calc``
        is the first of the two — the curve the fit actually minimised.
        """
        table = ParameterTable(self.structure, self.instrument)
        if two_theta is None:
            if self._model is None:
                raise RuntimeError(
                    "predict() with no grid evaluates on the grid the last fit "
                    "ran on, and this Refinement has not been fitted. Pass the "
                    "pattern (or a 2θ array) to evaluate the model as it "
                    "stands: ref.predict(data).")
            return self._model.evaluate(table.decode(table.x0()))
        if isinstance(two_theta, PatternData):
            two_theta = two_theta.two_theta
        tt = np.asarray(two_theta, dtype=np.float64)
        grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
        mode = self._mode
        if mode in ("lebail", "pawley") and self._model is None:
            raise RuntimeError(
                f"{mode} intensities are extracted by a fit, not computed from "
                "the structure, so there is nothing to evaluate before one has "
                "run. Fit first, or predict in rietveld mode.")
        model = compile_model(self.structure, self.instrument, grid,
                              mode=mode, moving_paths=set(table.moving_paths))
        if mode in ("lebail", "pawley"):
            _carry_lebail(self._model, model)
        return model.evaluate(table.decode(table.x0()))

    def report(self, *, plan: RefinementPlan | str | None = None, **kw):
        """The full :class:`~rietx.report.FitReport` for the last fit.

        Unlike ``build_report(result)``, this has the compiled model in hand,
        so Layers 1-2 (misfit attribution and typed suggested actions) are
        computed — subject to their gates.  ``plan`` supplies the Layer-2
        strategy veto; pass the plan you ran (or its preset name).
        """
        from .report import build_report

        if self._model is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        if isinstance(plan, str):
            plan = PLAN_PRESETS[plan]()
        table = ParameterTable(self.structure, self.instrument)
        return build_report(self.result_, model=self._model,
                            values=table.decode(table.x0()), plan=plan,
                            structure=self.structure, held=list(self._held),
                            free_paths=list(self._free_paths), **kw)

    def summary(self, *, deliverable: str | None = None, plot: str | None = None,
               plan: RefinementPlan | str | None = None,
               report: FitReport | None = None) -> str:
        """The termination view (WP-1302): "done, or not, and why" from one call.

        ``report`` takes the :class:`~rietx.report.schemas.FitReport` this
        fit's :meth:`report` already built, so a caller that wants the text
        *and* the structured report builds one rather than two — the report
        is the expensive half of this call (issue #251). Its default,
        ``None``, builds one here under ``plan``; passing both is refused,
        because a report was built under its own plan and a second one
        would be silently ignored.

        Numerical heuristics first, agreement indices second-to-last, the
        visual check named but never substituted for them (the agent skill
        §10's design rule) — the two fits that agree on every index and the
        plot alike (one with a correct background, one over-flexible) are told
        apart only by ``worst_absorption`` in the deliverable rows below, never
        by looking harder at either.

        ``deliverable`` selects §4b's deciding rows for one purpose —
        ``"phase_id"``, ``"qpa"`` or ``"structure"``.  The report will not
        infer your purpose for you: ``None`` (the default) prints the three
        stop conditions and nothing past them.  ``"series"`` is accepted and
        answers with where it is decided: a trajectory's deciding rows are
        the chain's, on
        :meth:`~rietx.schemas.sequential.SeriesResult.summary`, because no
        single pattern carries a ``SEQUENTIAL_*`` row.

        ``plot`` writes :func:`~rietx.viz.plots.plot_for_vlm` to that path and
        names it on the last line — the picture confirms the text, the text
        stays the criterion.  Without it, the line names the call instead.

        Requires the compiled model (call :meth:`fit` first); a caller holding
        only the result prints ``str(result)`` for the rows that need no
        model — see :meth:`~rietx.schemas.results.RefinementResult.__str__`.
        """
        if self._model is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        result = self.result_
        if report is not None and plan is not None:
            raise ValueError(
                "summary(plan=..., report=...): a report is built under its own "
                "plan, so pass the report or the plan, not both")
        if report is None:
            report = self.report(plan=plan)

        lines = [f"Refinement.summary: {result.status} ({result.mode})"]
        lines += _stage_lines(result.stages, result.statistics.max_shift_over_esd)
        lines += _diagnostic_lines(result.diagnostics)
        lines += self._report_stop_condition_lines(report)
        lines.append(self._next_parameter_line())
        if deliverable is not None:
            lines += self._deliverable_lines(deliverable, report)
        lines += self._protocol_lines()
        lines.append(_provenance_line(result.provenance))
        lines.append(_agreement_line(result.statistics))
        lines.append(self._visual_check_line(report, plot))
        return "\n".join(lines)

    def _report_stop_condition_lines(self, report) -> list[str]:
        """Section 2b: the second stop condition — is the misfit explained?"""
        lines = [f"  layer0/1: {report.summary}"]
        if report.abstained_kind:
            lines.append(f"    abstained: {report.abstained_kind} "
                         f"— {report.abstained_reason}")
        worst = sorted(report.regions, key=lambda r: r.chi2_share, reverse=True)[:3]
        for r in worst:
            lines.append(f"    region {r.two_theta_lo:.1f}-{r.two_theta_hi:.1f}°: "
                         f"{r.chi2_share:.0%} of χ², "
                         f"max|Δ|/σ={r.max_abs_delta_over_sigma:.1f}")
        n_unmatched_obs = sum(1 for u in report.unmatched if u.kind == "unmatched_obs")
        lines.append(f"    unmatched obs peaks: {n_unmatched_obs}")
        stats = self.result_.statistics
        if stats.durbin_watson is not None:
            note = (f", esds inflated ×{stats.esd_inflation:.2f}"
                    if stats.esd_inflation is not None else "")
            lines.append(f"    serial correlation (DW): {stats.durbin_watson:.2f}{note}")
        return lines

    def _next_parameter_line(self) -> str:
        """Section 2c: the third stop condition — is anything left to free?

        Answered in **ΔBIC**, not in the Δχ² that ranks: §4's rule is that a
        powder pattern's channel count blesses improvements that are
        physically inert, so "the leverage does not pay for the parameter" is
        the sentence a caller stops on (WP-1305 b).

        The probe runs on the channels the last fit *ran on*, rebuilt from the
        compiled model — the same σ (a lookup, never a re-derivation), the same
        limits and exclusions already applied — so this asks about the fit that
        produced the view above rather than about a pattern the caller happens
        to still be holding.  One Jacobian build, no solve.
        """
        model = self._model
        data = PatternData(two_theta=model.tt.tolist(),
                           intensity=model.y_obs.tolist(),
                           sigma=model.sigma.tolist())
        s = self.suggest(data)
        if not s.groups:
            return (f"  next: nothing to free — no held parameter clears the "
                    f"noise floor ({s.n_evaluated} evaluated)")
        top = s.groups[0]
        what = (top.members[0].path if top.resolved
                else "|".join(pc.path for pc in top.members) + " (a tie)")
        # the count the ΔBIC was charged at, said where the verdict is read
        # (WP-1417): N/f², not the raw channel count, since #270
        at = ("" if s.n_effective is None
              else f" at N_eff {s.n_effective:.0f}")
        if top.delta_bic > 0.0:
            return (f"  next: free {what}, predicted ΔBIC {top.delta_bic:+.1f}"
                    f"{at} (Δχ² {top.gain:.4g})")
        # The groups are ranked by Δχ², and ΔBIC charges k·ln N — so a
        # multi-member tie can lead the ranking and still be refused while a
        # single-member group below it is admitted.  "The leader is refused"
        # is what this line can say; "nothing is admitted" would be a claim
        # about the whole list that only the leader was tested for.
        admits = next((g for g in s.groups if g.delta_bic > 0.0), None)
        tail = ("" if admits is None else
                f"; {admits.members[0].path} ranks lower on Δχ² "
                f"{admits.gain:.4g} and ΔBIC does admit it "
                f"({admits.delta_bic:+.1f})")
        return (f"  next: {what} leads on Δχ² {top.gain:.4g} and ΔBIC "
                f"refuses it ({top.delta_bic:+.1f}{at}){tail}")

    def _deliverable_lines(self, deliverable: str, report) -> list[str]:
        """Section 3: §4b's deciding rows for one declared purpose only."""
        result = self.result_
        lines = [f"  deliverable: {deliverable}"]
        if deliverable == "phase_id":
            n_unmatched_obs = sum(1 for u in report.unmatched
                                  if u.kind == "unmatched_obs")
            lines.append(f"    unmatched obs peaks: {n_unmatched_obs}")
            if report.lebail_gap is not None:
                lines.append(f"    lebail_gap ratio: {report.lebail_gap.ratio:.2f}")
            else:
                lines.append("    lebail_gap: not computed (needs a Le Bail "
                             "re-partition, mccusker_default/lebail mode)")
        elif deliverable == "qpa":
            bg = report.background
            if bg is not None and bg.absorption:
                worst_path, worst_r2 = max(bg.absorption.items(), key=lambda kv: kv[1])
                lines.append(f"    background.absorption worst: "
                             f"{worst_path} R²={worst_r2:.2f}")
            if result.qpa is not None:
                for row in result.qpa.phases:
                    esd = (f" ± {row.weight_fraction_stderr:.3f}"
                          if row.weight_fraction_stderr is not None else "")
                    lines.append(f"    {row.name}: {row.weight_fraction:.3f}{esd}")
            else:
                lines.append("    qpa: none (Le Bail scales are degenerate)")
        elif deliverable == "structure":
            if result.identifiability is not None:
                exch = result.identifiability.exchangeability
                lines.append(f"    exchangeability: {len(exch)} row(s)")
                for row in exch[:5]:
                    lines.append(f"      {row.held} ~ {', '.join(row.partners)} "
                                 f"(R²={row.r2:.2f})")
            else:
                lines.append("    identifiability: not measured on this result")
        elif deliverable == "series":
            # A series deliverable is decided one rank up and this is the
            # honest thing one pattern can say about it: no single fit carries
            # a SEQUENTIAL_* row, and the two statements below are the
            # caller's on any fit (WP-1305 a).
            lines.append("    the deciding rows are the series': run the chain "
                         "with rx.refine_sequential and print "
                         "SeriesResult.summary(deliverable='series') — no "
                         "single pattern carries a SEQUENTIAL_* row")
            lines.append("    2θ-scale anchor: state it — an internal standard, "
                         "a calibrant, or none. Nothing in this result knows")
            lines.append("    precision vs accuracy: the esds are precision on "
                         "the *shape* of the trajectory; without an anchor "
                         "there is no accuracy claim on the absolute")
        else:
            raise ValueError(
                f"unknown deliverable {deliverable!r}; one of "
                f"{', '.join(repr(d) for d in DELIVERABLES)}")
        return lines

    def _protocol_lines(self) -> list[str]:
        """Section 4 (minus provenance, appended separately — the one clause
        a bare result can also answer): the protocol actually run."""
        plan = self._last_plan
        lines = ["  protocol:"]
        if plan is not None:
            lines.append(f"    plan: {', '.join(s.name for s in plan.stages)}")
        rows = self.parameters()
        # exhaustive over ParameterRow.held_because's four reasons, minus
        # "tied" (excluded above: a tied path moves with its source, so it
        # is not held in this sense — CLAUDE.md's moving_paths rule). A row
        # reaching neither mode_fixed, locked nor refinable can only be
        # needs_held_cell, so this catches it by name rather than into a
        # silent "other" (code review finding: a row held because its cell
        # is free was landing unlabelled).
        held: dict[str, list[str]] = {"mode_fixed": [], "symmetry-locked": [],
                                      "user-fixed": [], "wavelength-blocked": []}
        for row in rows:
            if row.tie is not None or row.vary:
                continue
            if row.mode_fixed:
                held["mode_fixed"].append(row.path)
            elif row.locked:
                held["symmetry-locked"].append(row.path)
            elif row.refinable:
                held["user-fixed"].append(row.path)
            else:
                held["wavelength-blocked"].append(row.path)
        phase_unsupported = list(self.result_.stages[-1].held) if self.result_.stages else []
        counts = ", ".join(f"{len(v)} {k}" for k, v in held.items() if v)
        if phase_unsupported:
            counts += (", " if counts else "") + \
                f"{len(phase_unsupported)} phase-unsupported (WP-1301)"
        lines.append(f"    held: {counts or 'none'}")
        if self._excluded_regions:
            ranges = ", ".join(f"{lo:.2f}-{hi:.2f}°" for lo, hi in self._excluded_regions)
            lines.append(f"    excluded: {ranges}")
        support = self.result_.data_support
        stats = self.result_.statistics
        if support is not None:
            lines.append(f"    N points={stats.n_points}, "
                         f"N reflections={support.n_unique_reflections}, "
                         f"effective obs={support.n_effective_observations:.0f}")
        else:
            lines.append(f"    N points={stats.n_points}")
        sigma_source = ("file" if self._sigma_from_file else
                        "Poisson √max(y,1)" if self._sigma_from_file is not None else
                        "unknown")
        lines.append(f"    σ source: {sigma_source}")
        return lines

    def _visual_check_line(self, report, plot: str | None) -> str:
        """Section 6: named, never substituted — the picture confirms the
        text; the text stays the criterion (the agent skill §10)."""
        if plot is not None:
            from .viz.plots import plot_for_vlm

            plot_for_vlm(self.result_, report, path=plot)
            return f"  visual check written: {plot}"
        return ("  visual check: call summary(plot='fit.png') or "
                "plot_for_vlm(result, report) to draw these regions")

    # ------------------------------------------------------------------
    # exporters (WP-0309): reflection table, refinement CIF, QPA table
    # ------------------------------------------------------------------
    def reflection_table(self) -> list["ReflectionRow"]:
        """Every (emission line, reflection) of the last fit as typed rows.

        See :func:`rietx.io.exporters.reflection_table`.  In Le Bail/Pawley
        mode the intensities are the extracted/refined ones held on the model.
        """
        from .io.exporters import reflection_table

        if self._model is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        table = ParameterTable(self.structure, self.instrument)
        values = table.decode(table.x0())
        return reflection_table(self._model, values, self.structure)

    def write_reflection_table(self, path, **kw) -> None:
        """Write the reflection table to CSV/TSV (delimiter from the suffix)."""
        from .io.exporters import write_reflection_table

        write_reflection_table(self.reflection_table(), path, **kw)

    def write_cif(self, path) -> None:
        """Write a refinement CIF: structure with esds, R-factors, wavelength,
        profile/background description, and the observed/calculated pattern."""
        from .io.exporters import write_refinement_cif

        if self.result_ is None:
            raise RuntimeError("call fit() first")
        write_refinement_cif(self.result_, self.structure, self.instrument, path)

    def write_qpa_table(self, path, **kw) -> None:
        """Write the QPA weight-fraction table (crystalline-only caveat included)."""
        from .io.exporters import write_qpa_table

        if self.result_ is None or self.result_.qpa is None:
            raise RuntimeError("no QPA on this result (Rietveld fits only)")
        write_qpa_table(self.result_.qpa, path, **kw)

    @property
    def fitted_structure(self) -> Structure:
        return self.structure

    @property
    def fitted_instrument(self) -> Instrument:
        return self.instrument


# ----------------------------------------------------------------------
# module-level helpers
# ----------------------------------------------------------------------
#: Guard codes that are **discarded per stage and re-taken on the converged
#: vector** rather than accumulated (WP-1310 for the first, WP-1311 for the
#: other three).  Each reads a number straight off the values a stage landed
#: on, so it describes a *vector* and not a run: a plan exists to let an early
#: stage absorb an error a later one corrects, and an intermediate state's
#: finding on the final result is a claim about a fit that no longer holds.
#: Every stage's own copy stays on its ``StageReport`` and its history node.
#:
#: ``RESOLUTION_UNCONSTRAINED`` belongs here on a second fact and not only on
#: that one: it also reads *which* terms the stage freed, and staging is
#: **cumulative** (``Refinement`` § stages), so a plan that frees U, V, W once
#: still has them free at the last stage and the final guard re-takes the
#: finding.  A plan that turned them back off would drop it, which is the
#: intended reading — held at instrumental values is the remedy the paper
#: prescribes, not the fault.
_REVISABLE_CODES = ("BOUND_HIT", "RESOLUTION_NOT_POSITIVE",
                    "RESOLUTION_UNCONSTRAINED",
                    "BISO_UNUSUALLY_LARGE")


def _guard_diagnostics(guard) -> list[Diagnostic]:
    """Guard findings as diagnostics — one prose message per :class:`GuardFinding`.

    The paths come from ``finding.paths`` (WP-1007).  They used to come from
    ``msg.split(" ")[0]``, which worked for the single-path findings and produced
    *nothing* for a correlation, since its rendered form leads with no single
    path — so ``where`` was empty on exactly the finding a client most wants to
    make clickable.  ``finding.value`` rides along as ``Diagnostic.value``
    (WP-1003) for the same reason.  Every ``message`` is unchanged, byte for
    byte: it is built from ``str(finding)``, which is the old list entry.
    """
    out: list[Diagnostic] = []
    for finding in guard.high_correlations:
        out.append(Diagnostic(
            level="warning", code="HIGH_CORRELATION", message=str(finding),
            where=list(finding.paths), value=finding.value,
            suggestion="consider fixing one of the correlated parameters",
        ))
    for finding in guard.at_bounds:
        path = str(finding)
        out.append(Diagnostic(
            level="warning", code="BOUND_HIT", where=list(finding.paths),
            value=finding.value,
            message=f"{path} refined to its bound{finding.detail}",
            suggestion="widen the bound or fix the parameter",
        ))
    for finding in guard.nonpositive_adps:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="ADP_NOT_POSITIVE_DEFINITE",
            where=list(finding.paths), value=finding.value,
            message=f"the anisotropic displacement tensor of {msg} is not "
                    "positive definite — it is not an ellipsoid, and its "
                    "Debye-Waller factor grows without bound at high Q",
            suggestion="the data probably do not support this many "
                       "displacement parameters: revert the site to an "
                       "isotropic biso, check the occupancy and species "
                       "assignment, or extend the fit range; do not report "
                       "the tensor as measured",
        ))
    for finding in guard.nonpositive_strain:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="STEPHENS_STRAIN_NOT_POSITIVE",
            where=list(finding.paths), value=finding.value,
            message=f"the Stephens strain coefficients of {msg} — σ²(M) is a "
                    "variance, so a negative value is not a large anisotropy "
                    "but coefficients outside the physical cone, and those "
                    "reflections silently get no strain broadening at all",
            suggestion="the data do not support this many strain patterns in "
                       "this direction: restart from the isotropic limit "
                       "(StephensStrain.isotropic), refine fewer patterns (a "
                       "higher-symmetry Laue class has fewer), or extend the "
                       "fit range; do not report the S_HKL as measured",
        ))
    for finding in guard.unsupported_resolution:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="RESOLUTION_UNCONSTRAINED",
            where=list(finding.paths), value=finding.value,
            message=f"{msg} — on a pattern of this character the Gaussian "
                    "resolution terms are not determined by the data, so what "
                    "they converged to is a fitted artefact rather than a "
                    "measurement of the instrument",
            suggestion="measure the instrument instead of refining it here: "
                       "lab_calibrate on a standard with its certified cell "
                       "held fixed, save_instrument_profile, then "
                       "load_instrument_profile before this fit, which holds "
                       "U, V and W at the instrumental values. Do not quote "
                       "the widths, and treat any crystallite size or strain "
                       "read off this profile as unmeasured",
        ))
    for finding in guard.flat_directions:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="FLAT_DIRECTION",
            where=list(finding.paths), value=finding.value,
            message=f"{msg} — at this |ρ| the pair is a statement about the "
                    "rank of the data rather than a strong correlation: one "
                    "direction of the two is not measured at all, and each "
                    "esd is conditional on the other parameter being right",
            suggestion="quote neither as measured from this fit — one is "
                       "as unmeasured as the other and the report cannot say "
                       "which. Fix one at an independently known "
                       "value and refine the other, or free them in "
                       "different stages, and say in the result which one was "
                       "held. Widening the fitted range or adding a second "
                       "histogram is what actually separates them",
        ))
    for finding in guard.large_biso:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="BISO_UNUSUALLY_LARGE",
            where=list(finding.paths), value=finding.value,
            message=f"{msg} — at that amplitude an atom in a cell this "
                    "dense would have melted, so the number is evidence "
                    "about the model rather than a displacement",
            suggestion="a large B is what a wrong model does: check the "
                       "species and occupancy on that site, the absorption "
                       "correction and the background flexibility before "
                       "reading it as motion. If the site is genuinely "
                       "mobile (a cavity cation, a superionic sublattice) "
                       "the number may be real, and saying so is part of "
                       "quoting it",
        ))
    for finding in guard.nonpositive_resolution:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="RESOLUTION_NOT_POSITIVE",
            where=list(finding.paths), value=finding.value,
            message=f"{msg} goes negative inside the fitted range — Γ_G² is a "
                    "variance, so this is not a narrow instrument but U, V, W "
                    "outside the physical set, and the forward model clamps "
                    "Γ_G to a 1e-4° floor there rather than raising",
            suggestion="the resolution parameters are not quotable and "
                       "anything judged against them is unsafe: refit the "
                       "resolution on a standard with its certified cell held "
                       "fixed (lab_calibrate), or hold a loaded instrument "
                       "profile rather than refining U, V and W on this "
                       "pattern; do not report the widths or the "
                       "microstructure derived from them",
        ))
    for finding in guard.narrow_humps:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="HUMP_TOO_NARROW",
            where=list(finding.paths), value=finding.value,
            message=f"the declared background peak {msg} is no longer "
                    "describing a broad feature: at that width it is a "
                    "reflection with no cell and no structure factor behind "
                    "it, and a free peak improves Rwp whether or not anything "
                    "is there",
            suggestion="a background peak is for diffuse or amorphous "
                       "scattering, a cryostat or sample-container "
                       "contribution — features whose width comes from "
                       "disorder and is many times the resolution. If there "
                       "is a real unindexed line here, the honest answers are "
                       "a second phase or the unmatched-peak report in the "
                       "FitReport's Layer 0, not a background peak; do not "
                       "report these peak parameters as measured",
        ))
    for finding in guard.background_correlations:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="BACKGROUND_ABSORPTION",
            where=list(finding.paths), value=finding.value,
            message=f"the background can reproduce most of {msg}",
            suggestion="stiffen the background (fewer Chebyshev terms, larger "
                       "P-spline lambda_smooth, coarser knots) or hold an "
                       "estimated curve additively; ADPs, scales and any QPA "
                       "fractions from this fit are biased even though Rwp "
                       "looks good",
        ))
    for finding in guard.roughness_correlations:
        msg = str(finding)
        rough = any("surface_roughness" in p for p in finding.paths)
        out.append(Diagnostic(
            level="warning", code="ROUGHNESS_ABSORPTION",
            where=list(finding.paths), value=finding.value,
            message=(f"surface roughness is not separable from the "
                     f"displacement/scale/background block here — {msg} of the "
                     f"roughness column is reproducible by it"
                     if rough else
                     f"most of {msg} is reproducible by the surface-roughness "
                     f"block: this displacement parameter is hiding in it"),
            suggestion=("extend the fit to lower 2θ, where roughness has a "
                        "lever arm the displacement parameters do not, or hold "
                        "roughness fixed at an independently measured value; "
                        "refining both against this range reports two numbers "
                        "where the data support one, and their esds understate "
                        "it (Pitschke et al. 1993 Table III: uncorrected "
                        "roughness drives Biso negative, so neither leaving it "
                        "out nor freeing it blind is safe)"),
        ))
    return out


def _dedup_high_correlations(
    hits: dict[tuple[str, frozenset], list[tuple[str, Diagnostic]]],
) -> list[Diagnostic]:
    """One ``HIGH_CORRELATION`` (and one ``FLAT_DIRECTION``) per pair.

    A pair that stays correlated fires on every stage that re-measures the
    Jacobian after it becomes free, so ``hits`` — built by the caller as it
    walks the stage loop — routinely holds several entries under one
    key.  A flat pair produces one of each code and they are keyed apart, so
    neither evicts the other.  Keeps the worst |ρ| (correlation only ever
    strengthens or weakens; the largest magnitude is the most informative
    one to show) and names every stage the pair was flagged in, because
    "still correlated at the last stage" and "correlated once, early, and
    never again" are different findings a client should be able to tell
    apart without re-running the fit.
    """
    out = []
    # ``.values()``, never an unpack of the key: a two-element ``frozenset``
    # unpacks into ``(code, pair)`` without complaint, so a caller still
    # passing the pre-WP-1311 key shape would be served silently rather than
    # raising.  Nothing here reads the key — the paths come off ``worst``.
    for stage_hits in hits.values():
        stage_names = list(dict.fromkeys(name for name, _ in stage_hits))
        worst = max(stage_hits, key=lambda sd: abs(sd[1].value))[1]
        message = worst.message if len(stage_names) == 1 else (
            f"{worst.message} — flagged in stages: {', '.join(stage_names)}")
        out.append(Diagnostic(
            # worst.where, never list(pair): the dict key is a frozenset for
            # dedup only, and its iteration order is hash-randomized per
            # process — list(pair) could name the two paths in the opposite
            # order from the one worst.message already spelled them in
            level=worst.level, code=worst.code, message=message,
            where=list(worst.where), value=worst.value, suggestion=worst.suggestion))
    out.sort(key=lambda d: abs(d.value) if d.value is not None else 0.0, reverse=True)
    return out


def _constraint_diagnostics(stage_name: str, outcome) -> list[Diagnostic]:
    """`CONSTRAINT_ACTIVE` when the answer-producing stage pressed a constraint.

    Only the stage whose θ becomes the result is examined: earlier stages'
    counts are on their :class:`StageResult` rows, but a truncation there
    shaped an intermediate state, not the reported values.  ``info`` rather
    than ``warning`` — landing on the cone face is what the constrained driver
    is *for* (the admissible optimum), but an agent must know the constraint
    was active rather than merely declared, because an active face means the
    coefficients are admissible, not measured (WP-0601: they still span
    ~100 % across starting seeds under both drivers).
    """
    n = getattr(outcome, "n_constraint_truncations", 0)
    if not n:
        return []
    return [Diagnostic(
        level="info", code="CONSTRAINT_ACTIVE",
        message=(f"the bounded-LM driver shortened {n} step(s) against a linear "
                 f"inequality constraint (the Stephens strain positivity cone) "
                 f"in stage {stage_name!r} — the optimum sits on or near a "
                 "constraint face"),
        suggestion="the constrained coefficients are admissible, not measured: "
                   "vary the starting seed and quote them only if they survive "
                   "(the STEPHENS_STRAIN_NOT_POSITIVE protocol row applies even "
                   "though that guard is silent under solver='lm')",
    )]


def _covariance_diagnostics(stage_name: str, outcome, *,
                            answer: bool) -> list[Diagnostic]:
    """``COVARIANCE_UNAVAILABLE`` when a stage's esd computation raised after
    its solve returned (WP-1333, issue #225).

    One per stage, because the two cases say different things and a caller
    acts on only one of them.  On the **answer-producing** stage (``answer``)
    every esd on the result is absent — ``None``, the empty state the schema
    has always declared — and so is everything built on the covariance (QPA
    fractions' esds, geometry esds, the Bérar-Lelann factor's effect).  On an
    **intermediate** stage the reported values are untouched and what did not
    run is that stage's correlation guard, whose findings would have been read
    off the matrix that was never formed.  ``warning`` either way: an esd that
    is missing because its computation failed is not the same statement as one
    that is missing because the parameter was not refined, and only this
    diagnostic tells them apart.
    """
    error = getattr(outcome, "covariance_error", None)
    if error is None:
        return []
    if answer:
        consequence = ("every esd on this result is absent (None), as are the "
                       "correlations and everything propagated from them")
        suggestion = ("the refined values stand — the solve had returned "
                      "before the esd computation failed — but quote none of them "
                      "with an uncertainty from this fit; refit from these "
                      "values (a near-singular normal matrix is the usual "
                      "cause, so fixing or restraining the most correlated "
                      "block is the usual cure) and read the esds from that")
    else:
        consequence = ("this intermediate stage's guards ran without a "
                       "covariance; the result's esds are the answer-producing "
                       "stage's, so this stage's failure is not why any of "
                       "them would be absent")
        suggestion = ("whatever this stage's guards would have read off the "
                      "covariance — a HIGH_CORRELATION or FLAT_DIRECTION "
                      "finding, an esd-scaled bound test — is unknown rather "
                      "than absent on its stage report and history node; the "
                      "result's own findings are the last stage's")
    return [Diagnostic(
        level="warning", code="COVARIANCE_UNAVAILABLE", where=[stage_name],
        message=(f"stage {stage_name!r} returned ({outcome.status}), but its "
                 f"esd computation raised {error}: {consequence}"),
        suggestion=suggestion,
    )]


def _degenerate_cell_diagnostics(rows: list[tuple[str, int]]) -> list[Diagnostic]:
    """``CELL_DEGENERATE_PROBE`` when any stage's search reached a degenerate
    cell (issue #283).

    Unlike :func:`_constraint_diagnostics`, every completed stage is summed
    here rather than only the answer-producing one: a degenerate probe is a
    fact about the *search's* robustness (it was reached and pushed back out,
    never a value that entered the reported parameters — see
    ``_DegenerateCellGuard``), not about whether the final point is
    admissible, so it is worth surfacing wherever it happened, including a
    ``cell`` stage that ran and converged before a later stage produced the
    answer.  ``info``, not ``warning``: the guard already contained it before
    it reached the caller, so however common it is on a given fit — ``Cell``
    declares no bounds of its own, so an underdetermined cell stage may reach
    this often, not rarely — nothing about the reported values is in
    question.
    """
    hits = [(name, n) for name, n in rows if n]
    if not hits:
        return []
    total = sum(n for _, n in hits)
    where = [name for name, _ in hits]
    return [Diagnostic(
        level="info", code="CELL_DEGENERATE_PROBE",
        message=(f"the search reached {total} degenerate cell trial(s) "
                 f"(zero or negative volume) in stage(s) "
                 f"{', '.join(repr(n) for n in where)} and was pushed back "
                 "out rather than crashing (issue #283) — the reported "
                 "values were never a degenerate point"),
        where=where, value=float(total),
    )]


def _hold_diagnostics(stage_results: list[StageResult]) -> list[Diagnostic]:
    """``HOLD_BLOCKED_PLAN`` — which declaration won, and over what.

    A stage's ``turn_on`` glob and a caller's ``Refinement.hold`` can name the
    same parameter, and one of them has to lose.  The hold wins, and the point
    of this WP is that the loss is said out loud (issue #211).  Before it, the
    glob won and nothing reported it: a certified cell pinned for a
    calibration was refined anyway, ``RefinementResult.parameters`` said
    ``vary=True``, and the model it was fitted from went on saying ``False``.

    ``info``, for the reason :func:`_degenerate_cell_diagnostics` is: the run
    did exactly what the caller declared, so nothing about the reported values
    is in question.  It fires anyway, because a plan quietly doing less than
    it says is the half a caller cannot see. Reading it as a fault of the plan
    is wrong — a preset frees the cell because most fits want that, and a hold
    is how one fit says it does not.

    Keyed on the *paths*, one diagnostic for the fit rather than one per
    stage: a cumulative plan names the same glob in several stages and a
    per-stage code would print the same sentence four times.  ``where`` is
    the union, and the message names the stages so a caller can still see
    which ones asked.

    This is the discriminator WP-1310 could not build.  ``vary=False`` is the
    default rather than a decision, so "declared fixed and freed by a plan"
    named 8 of 16 paths on an ordinary LaB6 fit; a hold is only ever
    deliberate, so the set here is the caller's own declarations and nothing
    else.
    """
    by_path: dict[str, list[str]] = {}
    for sr in stage_results:
        for path in sr.blocked_by_hold:
            by_path.setdefault(path, []).append(sr.name)
    if not by_path:
        return []
    where = sorted(by_path)
    stages = sorted({n for names in by_path.values() for n in names})
    n = len(where)
    return [Diagnostic(
        level="info", code="HOLD_BLOCKED_PLAN",
        message=(f"{n} held parameter{'' if n == 1 else 's'} "
                 f"{'was' if n == 1 else 'were'} matched by the turn_on glob "
                 f"of stage{'' if len(stages) == 1 else 's'} "
                 f"{', '.join(repr(s) for s in stages)} and stayed fixed: "
                 f"{', '.join(where[:5])}{'…' if n > 5 else ''}. The hold you "
                 "declared outranks the plan's glob"),
        where=where, value=float(n),
        suggestion=("this is the hold working. If you meant the plan to "
                    "refine these, unhold() them first; if you meant them "
                    "held, the plan is doing less than its name suggests and "
                    "a narrower one would say so"),
    )]


def _unknown_path_diagnostics(stage_results: list[StageResult],
                              known: list[str], *,
                              listing: str = "ref.parameters()"
                              ) -> list[Diagnostic]:
    """``STAGE_PATH_UNKNOWN`` — a stage asked for a parameter by a name no row has.

    Issue #265: ``turn_on=["instrument.source.wavelength"]`` freed nothing,
    the stage converged, and nothing said so, because the table spells it
    ``instrument.source.lines.0.wavelength``.  ``StageResult.freed`` was
    empty, which is also what a healthy stage looks like when its pattern
    reaches a component this model does not declare, so the record alone
    could not tell the two apart.  A *literal* can: it names one parameter
    (:func:`~rietx.params.vector.is_literal_path`), and a pattern matching
    nothing stays silent for that reason.

    ``warning``, where :func:`_hold_diagnostics` is ``info``: that one
    reports the run doing what the caller declared, and this one the caller
    being wrong about the model, so whatever the stage was meant to refine
    was not refined.  Never raised, because one plan runs every pattern of a
    series and a path one pattern's model lacks must not end the chain.

    One diagnostic per **path**, for the reason the hold's is one per fit: a
    cumulative plan repeats itself, and the message names the stages.
    ``where`` is the missing path, so a client can put the cursor on the typo;
    the nearest real path (:mod:`rietx._nearmiss`, the ``__getattr__`` helper)
    rides in the message.  One suggestion rather than three, since on dot
    paths the second and third are usually siblings of the first: for the
    issue's typo they were ``lines.0.weight`` and ``profile.w``.

    ``listing`` is the call the suggestion names for seeing every path, which
    is the caller's: a joint fit has no ``parameters()``.
    """
    by_path: dict[str, list[str]] = {}
    for sr in stage_results:
        for path in sr.unknown_paths or ():
            by_path.setdefault(path, []).append(sr.name)
    out = []
    for path, stages in by_path.items():
        hint = did_you_mean(path, known, n=1)
        which = (f"stage {stages[0]!r}" if len(stages) == 1 else
                 f"stages {', '.join(repr(s) for s in stages)}")
        out.append(Diagnostic(
            level="warning", code="STAGE_PATH_UNKNOWN",
            message=(f"{which} asked for {path}, which names no parameter of "
                     "this model, so nothing was freed for it"
                     + (f"; {hint}" if hint else "")),
            where=[path],
            suggestion=("a literal path names exactly one parameter: correct "
                        f"it ({listing} lists every path this model "
                        "has), or write a glob if the stage is meant to reach "
                        "a component some models do not declare"),
        ))
    return out


def _apply_esds(table: ParameterTable, result: RefinementResult,
                structure: Structure, instrument: Instrument) -> None:
    """Carry the fitted esds into the models, so exporters can quote them.

    Parameters the fit did not estimate get ``stderr = None`` rather than a
    stale value from an earlier stage — that is why the whole map is rewritten
    instead of only the entries that have one.
    """
    table.apply_to_models(structure, instrument, stderr={
        p.path: p.stderr for p in result.parameters if p.stderr is not None})


#: Why the composition estimator declines on a source that is not X-ray.
#:
#: :mod:`rietx.crystallography.attenuation` is an **X-ray** compilation —
#: photoabsorption plus scattering, cross-checked against the Cromer-Liberman
#: f'' table — and a neutron does not attenuate that way at all.  Neutron
#: attenuation is σ_abs(λ) + σ_coh + σ_inc, where σ_abs is quoted at 2200 m/s
#: (λ = 1.798 Å) and scales as 1/v, i.e. **linearly in λ**, while X-ray µ/ρ
#: falls roughly as λ⁻³ between edges and has edges at all.  The two are
#: unrelated numbers: hydrogen is nearly transparent to X-rays and one of the
#: strongest neutron attenuators there is.
#:
#: So this is not a coarse estimate, it is the wrong physical quantity, and
#: writing it into ``Geometry.mu_r`` would apply a confidently wrong correction
#: with nothing said — the outcome the docstring below calls the worst of the
#: three.  It declines and reports instead.  A neutron estimator is buildable
#: from the table this package already ships (WP-1132); until it exists an
#: explicit ``mu_r``/``mu_t`` is how to apply the correction on a neutron
#: instrument, and an explicit value always won anyway.
_NON_XRAY_ABSORPTION_ESTIMATE = (
    "specimen absorption was not estimated: the composition estimator is X-ray "
    "photoabsorption (McMaster tables), and neutron attenuation is a different "
    "quantity from a different table — sigma_abs scales as lambda rather than "
    "as lambda^-3, and the scattering cross-sections dominate for light "
    "elements. Declare Geometry.mu_r (capillary) or Geometry.mu_t (flat plate) "
    "explicitly to apply the correction; see WP-1132 for a neutron estimator."
)


def _resolve_specimen_absorption(structure: Structure,
                            instrument: Instrument) -> tuple[str, str | None]:
    """Fill in ``Geometry.mu_r`` **or** ``Geometry.mu_t`` from composition, in
    place.  Returns ``(source, skipped_reason)``.

    Only acts when the geometry declares a specimen dimension (capillary radius
    or flat-specimen thickness) and no explicit dimensionless product — an
    explicit value always wins, because the user measured their specimen and we
    did not.  Failure to estimate leaves the field at ``None`` (correction off)
    and returns the reason, which the result then reports: silently running with
    no absorption after the user asked for it would be the worst of the three
    outcomes.
    """
    geom = instrument.geometry
    if geom.kind == "debye_scherrer":
        if geom.capillary_radius_mm is None or geom.mu_r is not None:
            return "given", None
        # Asked *after* the explicit-value check, so declaring µR on a neutron
        # capillary still works — only the X-ray table is fenced off, not the
        # correction (:data:`_NON_XRAY_ABSORPTION_ESTIMATE`).
        if instrument.source.kind != "xray_cw":
            return "estimated", _NON_XRAY_ABSORPTION_ESTIMATE
        table = ParameterTable(structure, instrument)
        mu_r, reason = estimate_capillary_mu_r(
            structure, table.decode(table.x0()),
            instrument.source.primary_wavelength,
            geom.capillary_radius_mm, geom.packing_fraction)
        if mu_r is None:
            return "estimated", reason
        geom.mu_r = mu_r
        return "estimated", None

    if geom.thickness_mm is None or geom.mu_t is not None:
        return "given", None
    if instrument.source.kind != "xray_cw":
        return "estimated", _NON_XRAY_ABSORPTION_ESTIMATE
    table = ParameterTable(structure, instrument)
    mu_t, reason = estimate_flat_plate_mu_t(
        structure, table.decode(table.x0()),
        instrument.source.primary_wavelength,
        geom.thickness_mm, geom.packing_fraction)
    if mu_t is None:
        return "estimated", reason
    geom.mu_t = mu_t
    return "estimated", None


#: |ΔBiso| (Å²) above which a declared flat-specimen thickness is worth telling
#: the user about.  Gated on the **bias**, not on the identifiable fraction:
#: that fraction is 3-47 % for every flat-plate µt worth declaring — including
#: µt ≥ 2, where A is within 1 % of 1 everywhere and there is nothing to say —
#: so a fence on it would fire always, which WP-0502 established is a fence
#: that measures nothing.  0.05 Å² is roughly a typical Biso esd and ~10 % of a
#: typical Biso: below it the correction cannot move a quoted displacement
#: parameter outside its own uncertainty.
FLAT_PLATE_BIAS_MIN = 0.05


def _absorption_record(model: CompiledModel, source: str, skipped: str | None,
                       values: dict[str, float] | None = None):
    """The :class:`AbsorptionCorrection` record, or None when nothing applies."""
    if model.mode != "rietveld":
        return None
    lam = model.line_wavelengths[0] if model.line_wavelengths else model.wavelength
    if model.geometry_kind == "debye_scherrer":
        if not model.mu_r and skipped is None:
            return None
        return AbsorptionCorrection(
            mu_r=float(model.mu_r), mu_r_source=source, wavelength=float(lam),
            equivalent_delta_biso=equivalent_delta_biso(model.mu_r, lam),
            skipped=skipped, out_of_range=model.mu_r > CYLINDER_MU_R_MAX)

    transmission = model.geometry_kind == "flat_plate_transmission"
    # transmission always applies its factor (sec θ survives at µt = 0), so it
    # always gets a record; reflection with no declared thickness applied
    # nothing and says nothing
    if not transmission and model.mu_t is None and skipped is None:
        return None
    mu_t = 0.0 if model.mu_t is None else float(model.mu_t)
    delta_biso = unabsorbed = identifiable = None
    positions = _reflection_positions(model, values)
    if (model.mu_t is not None or transmission) and positions.size:
        a = np.asarray(model._absorption(positions), dtype=np.float64)
        delta_biso, unabsorbed = equivalent_delta_biso_from_transmission(
            positions, a, lam)
        identifiable = mu_t_identifiable_fraction(positions, mu_t,
                                                  model.geometry_kind)
    return AbsorptionCorrection(
        method=("flat_plate_transmission" if transmission
                else "flat_plate_reflection"),
        mu_r=mu_t, mu_r_source=source, wavelength=float(lam),
        equivalent_delta_biso=delta_biso or 0.0, skipped=skipped,
        unabsorbed_fraction=unabsorbed, identifiable_fraction=identifiable,
        intensity_fraction_of_optimal=(
            transmission_intensity_fraction(mu_t) if transmission else None))


def _reflection_positions(model: CompiledModel,
                          values: dict[str, float] | None) -> np.ndarray:
    """In-range Bragg 2θ of every modelled reflection, primary line.

    Where an intensity correction is *judged* — never on the fitted grid, which
    can start far below the first peak and make a correction look enormous that
    no modelled reflection ever experienced (WP-0502 measured exactly that on
    the round-robin patterns).
    """
    if not model.phases or values is None:
        return np.empty(0)
    positions = np.concatenate(
        [np.asarray(model.phase_peaks(ip, values)[0][0], dtype=np.float64)
         for ip in range(len(model.phases))])
    positions = positions[np.isfinite(positions)]
    return positions[(positions >= model.tt_min) & (positions <= model.tt_max)]


def _capillary_offset_diagnostics(model: CompiledModel,
                                  table: ParameterTable) -> list[Diagnostic]:
    """Say when the eq (4) offsets could not be expressed, rather than holding
    them silently.

    They are the capillary geometry's position aberration (McCusker et al. 1999
    eq 4), and eq (4) divides by the goniometer radius — so without one they are
    force-fixed at zero, correctly, because there is nothing to divide by.  What
    is not correct is leaving that quiet: **a held aberration reads as a measured
    zero** (WP-1073), and this one is not small.  Measured on a BT-1 neutron
    refinement where TOPAS refined a specimen displacement of 0.0975 and this
    package could not express one: both cell axes came back low by 143 ppm
    *together*, so c/a agreed with TOPAS to 3.4 ppm while neither axis did.  A
    uniform d-scale offset is what an unmodelled cos θ position error looks
    like, and an axial ratio hides it by construction.

    Info rather than warning, and it deliberately does **not** ask for the
    offsets to be freed.  WP-1073 measured what that costs on 11-BM: the pair is
    a degeneracy the fit rides to a bound while Rwp *improves* and the cell moves
    1117 ppm.  So they stay report-driven, and this says only that the door is
    shut and which field opens it.

    **What it covers, and what it does not.**  The condition is *could not
    express* — a capillary geometry with no radius for eq (4) to divide by — not
    *declared a radius and chose not to free the pair*.  A capillary that carries
    an R and whose plan never frees the offsets leaves the cell in exactly the
    same place and stays **silent** here: that case has a route already (Layer 2
    reads it off the plan signature), and firing on it would fire on nearly every
    capillary fit.  This one fact is about the model being unable to hold the
    aberration at all.

    **The breadth is intended, including on a calibrated instrument.**  Every
    ``Instrument.debye_scherrer(wavelength=…)`` built with no radius trips it —
    the bundled 11-BM references (``examples/nac_11bm.py``, the NAC and SRM 660a
    standards on the ``rietx compare`` page) among them — because the statement
    is true there too: the offsets *were* held for want of an R.  What the
    diagnostic cannot see is whether that is harmless.  On a calibrated
    synchrotron the 2θ scale is pinned and a certified cell reproduces to spec,
    so the held offsets cost nothing and the info is noted and dismissed; on a
    laboratory capillary the same silence is a real accuracy gap (measured, a
    corundum fit with the displacement force-fixed: both axes off by +500 ppm
    together while c/a held to +34.5 ppm).  The message names the field rather
    than the verdict for exactly that reason — the protocol row (§7) carries the
    clause on how to read it on a calibrated instrument.
    """
    if model.geometry_kind != "debye_scherrer":
        return []
    # Read the gate off the table rather than re-deriving it from the geometry.
    # ``ParameterTable`` force-fixes these two exactly when eq (4) has no R to
    # divide by, so a *locked* entry on a capillary is the radius being absent,
    # said by the one authority that decides it.  Re-testing the geometry here
    # would be a second opinion that could drift from the first.
    locked = {e.path for e in table.entries if e.locked}
    if not any(f"instrument.geometry.{name}" in locked
               for name in CAPILLARY_OFFSETS):
        return []
    return [Diagnostic(
        level="info", code="CAPILLARY_OFFSET_UNAVAILABLE",
        where=["instrument.geometry.goniometer_radius_mm"],
        message=("this capillary geometry declares no goniometer radius, so the "
                 "eq (4) specimen-offset aberrations are held at zero — which is "
                 "not the same statement as having measured them to be zero"),
        suggestion=("set instrument.geometry.goniometer_radius_mm if the "
                    "diffractometer's is known; an unmodelled offset of this "
                    "kind lands in the cell as a uniform d-scale error, moving "
                    "both axes together, which leaves an axial ratio looking "
                    "better than either axis deserves"))]


def _absorption_diagnostics(record) -> list[Diagnostic]:
    """Surface the ways a specimen absorption correction can mislead."""
    out: list[Diagnostic] = []
    flat = record.method != "rouse_cylinder"
    where = ["instrument.geometry." + ("mu_t" if flat else "mu_r")]
    if record.skipped is not None:
        out.append(Diagnostic(
            level="warning", code="ABSORPTION_ESTIMATE_UNAVAILABLE",
            where=where,
            message=(("a specimen thickness" if flat else "a capillary radius")
                     + " was given but "
                     + ("µt" if flat else "µR")
                     + f" could not be estimated ({record.skipped}); the "
                     "pattern was fitted with NO absorption correction"),
            suggestion=(f"set {where[0]} explicitly, or use a wavelength away "
                        "from an absorption edge of the specimen")))
    if record.out_of_range:
        out.append(Diagnostic(
            level="warning", code="ABSORPTION_MU_R_OUT_OF_RANGE", where=where,
            message=(f"µR = {record.mu_r:.2f} is outside the Rouse et al. "
                     f"(1970) fit's range (µR ≤ {CYLINDER_MU_R_MAX:g}); the "
                     "transmission factor is an extrapolation there"),
            suggestion=("dilute the specimen, use a narrower capillary, or a "
                        "shorter wavelength — rietx.estimate_mu_r() shows "
                        "what each choice buys")))
    if flat and abs(record.equivalent_delta_biso) > FLAT_PLATE_BIAS_MIN:
        # Not a fence — the opposite.  It says the correction is doing something
        # to the displacement parameters that is worth the user knowing the size
        # of, so µt is worth measuring rather than taken from a nominal
        # thickness and a guessed packing.  "At least" because the projected
        # bias understates what a weighted fit absorbs, by a factor that grows
        # with the unabsorbed fraction quoted beside it (model/absorption.py).
        residue = record.identifiable_fraction or 0.0
        out.append(Diagnostic(
            level="info", code="ABSORPTION_THICKNESS_MATTERS", where=where,
            message=(f"µt = {record.mu_r:.3f} shifts every Biso by at least "
                     f"{record.equivalent_delta_biso:+.3f} Å², and "
                     f"{100 * residue:.0f} % of its angular signature is not "
                     "reproducible by the scale and the ADPs — so an error in "
                     "the specimen thickness or packing lands partly in the fit "
                     "and partly in the displacement parameters"),
            suggestion=("measure the specimen thickness rather than assuming a "
                        "nominal one; µt is held fixed by design (it is not "
                        "refinable) precisely because it would otherwise "
                        "re-apportion the ADPs")))
    if record.method == "flat_plate_transmission" \
            and record.intensity_fraction_of_optimal is not None \
            and record.intensity_fraction_of_optimal < 0.7:
        out.append(Diagnostic(
            level="info", code="ABSORPTION_PLATE_THICKNESS", where=where,
            message=(f"a transmission plate is brightest at µt = 1, so this one "
                     f"(µt = {record.mu_r:.3f}) delivered "
                     f"{100 * record.intensity_fraction_of_optimal:.0f} % of the "
                     "counts it could have"),
            suggestion=("a plate far from t = 1/µ fits just as well and simply "
                        "measures fewer counts — a specimen-preparation note, "
                        "not a fit problem")))
    return out


def _phase_agreement(model: CompiledModel, values: dict[str, float],
                     structure: Structure) -> list[PhaseAgreement]:
    """R_Bragg and R_F per phase at the converged state (WP-1069).

    Empty outside Rietveld mode, where the observed-intensity partition would
    be compared against the very intensities it produced — the ``lebail_gap``
    rule, and the reason
    :meth:`~rietx.model.forward.CompiledModel.structure_intensity_partition`
    refuses rather than returning a circular number.
    """
    if model.mode != "rietveld" or not model.phases:
        return []
    rows = []
    for ip, (i_obs, i_calc) in enumerate(
            model.structure_intensity_partition(values)):
        r_b, r_f, n = structure_r_factors(
            i_obs, i_calc, model.phases[ip].reflections.multiplicity)
        rows.append(PhaseAgreement(name=structure.phases[ip].name,
                                   r_bragg=r_b, r_f=r_f, n_reflections=n))
    return rows



def _build_result(model: CompiledModel, table: ParameterTable, theta: np.ndarray, *,
                  mode: Mode, status: str, stage_results: list[StageResult],
                  diagnostics: list[Diagnostic], structure: Structure,
                  stderr_internal=None, correlation=None,
                  backend: str = "numpy", solver: str = "trf",
                  mu_r_source: str = "given",
                  mu_r_skipped: str | None = None,
                  guard=None,
                  max_shift_over_esd: float | None = None,
                  declared_wavelengths: list[float] | None = None,
                  cell_runaway: Sequence[Diagnostic] | None = None,
                  ) -> RefinementResult:
    values = table.decode(theta)
    y_calc = model.evaluate(values)
    y_bkg = model.background(values)
    stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                               n_free=len(table.free_paths) + _pawley_n(model),
                               y_background=y_bkg)
    # copied from the outcome, never derived here (WP-1076: run_least_squares
    # is the one writer); an evaluate-only caller leaves the honest None
    stats.max_shift_over_esd = max_shift_over_esd

    stderr_phys = (table.stderr_physical(theta, stderr_internal, correlation)
                   if stderr_internal is not None else {})
    # at_bound is the BOUND_HIT findings projected onto the rows, never a
    # second bound test (WP-1076).  Only the free set was tested, so a tied
    # row — in `parameters`, absent from the free vector — reports None, and
    # so does every row when no guard ran at all (`replay`).
    tested = set(table.free_paths) if guard is not None else set()
    on_bound = {p for f in guard.at_bounds for p in f.paths} if guard is not None else set()
    # A CELL_RUNAWAY finding's own message says the named cell's value is
    # "not a measurement", so its esd is withheld while the row stays (it is
    # still a free column; WP-1301's hold is what drops a row).  Keyed on the
    # **answer-producing stage's** finding, never the run's accumulated list
    # (review of #385 round 3): staging is cumulative, so a cell clamped in
    # stage 1 is refined again from the window edge by every later stage, and
    # the esd the last stage measured is a measurement.  ``cell_runaway`` is
    # that stage's finding; ``None`` reads it off ``diagnostics``, which is
    # right for every caller whose list is one stage's (``run_stage``, a stage
    # report, ``replay``).  The flag stays the finding's own ``where``, as
    # ``at_bound`` is a projection of ``BOUND_HIT``, and a tie inherits it.
    withheld = _cell_runaway_withheld(table, (
        p for d in (diagnostics if cell_runaway is None else cell_runaway)
        if d.code == "CELL_RUNAWAY" for p in d.where))
    params = []
    for e in table.entries:
        if e.vary or e.tie is not None:
            params.append(RefinedParameter(
                path=e.path, value=e.value, vary=e.vary,
                stderr=(None if e.path in withheld
                       else stderr_phys.get(e.path)),
                at_bound=(e.path in on_bound) if e.path in tested else None,
            ))

    # Tick positions cover **every** emission line, not just the primary one.
    # The calculated pattern really does have a peak at each Kα2 position, and
    # a tick list that omitted them would make the FitReport flag every Kα2
    # peak as an unindexed impurity.
    #
    # `tick_hkl` is built here and not anywhere downstream, because a second
    # answer to *where* a tick goes is the thing this must not become: the
    # index is carried through the same sort the positions are, so a tick and
    # its Miller index cannot come apart (WP-1438).
    #
    # `tick_support` rides beside the positions on the same terms, carried
    # through the same filter and sort, so the low-angle boundary can ask
    # which ticks have anything behind them without pairing by position
    # (WP-1458).  Each tick carries its *reflection's* support: the strongest
    # modelled point in σ (`CompiledModel.reflection_support`) over every
    # emission-line image of that hkl, so a Kα2 or λ/2 image is judged with the
    # reflection it is an image of, as its index already says.  It is not a
    # result field; `_low_angle_diagnostics` is its one reader.
    ticks = {}
    tick_hkl = {}
    tick_support = {}
    for ip, cp in enumerate(model.phases):
        name = structure.phases[ip].name
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        rows = [cp.reflections.two_theta(cell, lam)
                + values["instrument.zero_shift"]
                for lam in model.line_wavelengths]
        pos = np.concatenate(rows) if rows else np.array([])
        # one reflection list per emission line, in the same order each time,
        # so the index list is that list tiled — the Kα2 image of a peak is
        # the same hkl and says so.
        hkl = (np.tile(cp.reflections.hkl, (len(rows), 1)) if rows
               else np.zeros((0, 3), dtype=np.int64))
        line_support = model.reflection_support(ip, values)
        sup = (np.tile(np.max(np.stack(line_support), axis=0), len(rows))
               if rows else np.array([]))
        keep = np.isfinite(pos)
        if cp.magnetic is not None:
            # issue #278: a magnetic phase's reflections are drawn as their
            # own tick row, as a second phase would be -- split by a purity
            # cut on the magnetic fraction (MAGNETIC_TICK_PURITY: see its
            # docstring for why the mask on ``CompiledPhase`` is not enough
            # on a k != 0 supercell).  One
            # fraction per *reflection*, tiled across ``rows`` (one row per
            # emission line, each already ``cp.reflections``-ordered) before
            # the positions are concatenated and sorted.
            # ``tick_hkl`` and ``tick_support`` are carried through the same
            # mask and the same sort as the positions, so a split row keeps its
            # Miller indices and its support.
            d = np.asarray(cp.reflections.d, dtype=np.float64)
            f_nuc = np.asarray(model._nuclear_f2(ip, d, values, cell),
                               dtype=np.float64)
            f_mag = np.asarray(model._magnetic_f2(ip, d, values, cell),
                               dtype=np.float64)
            total = f_nuc + f_mag
            with np.errstate(invalid="ignore", divide="ignore"):
                frac = np.where(total > 0.0, f_mag / total, 0.0)
            mag_hkl = frac >= 1.0 - MAGNETIC_TICK_PURITY
            mag_row = (np.concatenate([mag_hkl for _ in rows])
                       if rows else np.zeros(0, dtype=bool))
            rows_out = ((name, keep & ~mag_row),
                        (f"{name} (magnetic)", keep & mag_row))
        else:
            rows_out = ((name, keep),)
        for key, sel in rows_out:
            pos_k, hkl_k, sup_k = pos[sel], hkl[sel], sup[sel]
            order = np.argsort(pos_k, kind="stable")
            ticks[key] = [float(v) for v in pos_k[order]]
            tick_hkl[key] = [[int(h), int(k), int(el)]
                             for h, k, el in hkl_k[order]]
            tick_support[key] = [float(v) for v in sup_k[order]]

    # Declared sharp peaks are ticks too, under one reserved key.  This is the
    # whole of the member contract's clause 2 for `PeakComponent`: a hump joins
    # the reported background, a peak joins this list, and the destination is
    # read from `model.components.COMPONENT_AGGREGATE` rather than inferred.
    #
    # Without it Layer 0's `unmatched_obs` reports every declared peak as an
    # unindexed impurity — the Kα2-ticks lesson one rank over, and the same
    # failure: a peak the model *does* put intensity at, reported as
    # unexplained because nothing wrote it down.
    #
    # No zero-shift is added, unlike a phase's: the centre is the *apparent*
    # position by declaration and carries its own aberrations (see
    # `PeakComponent`).  That, and where each emission line's image falls, is
    # `CompiledModel.extra_peak_tick_positions` — one authority, because
    # `multi.MultiHistogramRefinement._ticks` owes the same list and a second
    # copy there is how a joint fit ends up disagreeing with this one.
    #
    # Accepted wrinkle, recorded rather than special-cased: Layer 0's
    # `Region.n_reflections` counts ticks, so these inflate that count in their
    # own regions.  It is right for segmentation and for the unmatched logic,
    # and mislabelled as a count of reflections.
    extra_ticks = model.extra_peak_tick_positions(values)
    if extra_ticks:
        ticks[EXTRA_TICK_KEY] = extra_ticks
        images = model.extra_peak_support(values)
        best = {}
        for _, j, s in images:
            best[j] = max(best.get(j, 0.0), s)
        tick_support[EXTRA_TICK_KEY] = [best[j] for _, j, _ in images]

    # Quantitative phase analysis from the refined scales.  Le Bail scales are
    # degenerate with the extracted intensities, so QPA is Rietveld-only.  σ(W)
    # comes from the correlated scale block of the covariance (physical_covariance
    # reuses the same Cov_free as stderr_physical → consistent conditioning).
    qpa = None
    if mode == "rietveld":
        scale_paths = [f"phases.{ip}.scale" for ip in range(len(structure.phases))]
        scale_cov = None
        if stderr_internal is not None:
            # A scale the data carries no gradient in makes *every* fraction
            # unquotable, not only its own (WP-1110 item 14): W_i normalises by
            # Σ S_j M_j V_j, so one unmeasured term is an unmeasured sum.  Its
            # column is zeroed in Cov_free rather than infinite (see
            # ``ParameterTable._cov_free``), so propagating it anyway would
            # report each *other* phase's fraction to the precision it would
            # have had if this phase were known — which is the confident wrong
            # number.  `None` is the block-level absence `compute_qpa` already
            # takes, and is the same phase `PHASE_UNCONSTRAINED` names.
            blind = table.unmeasured_rows(theta, stderr_internal,
                                          [table._paths[q] for q in scale_paths])
            if not blind.any():
                scale_cov = table.physical_covariance(theta, stderr_internal,
                                                      correlation, scale_paths)
        # Site multiplicities frozen on the compiled model (never re-derived
        # from refined coordinates, which could have drifted near a special
        # position and collapsed an orbit).  The primary emission line feeds
        # the Brindley microabsorption attenuation (µ ∝ λ³ makes the Kα₂
        # offset sub-percent in µ, far smaller in τ).
        multiplicities = [[len(op[0]) for op in cp.sites.ops] for cp in model.phases]
        wavelength = model.line_wavelengths[0] if model.line_wavelengths else None
        qpa = compute_qpa(structure, values, scale_cov, multiplicities,
                          wavelength=wavelength)
        if qpa is None:
            diagnostics = diagnostics + _qpa_unavailable_diagnostics(
                structure, values)
        else:
            diagnostics = diagnostics + microabsorption_diagnostics(qpa)

    # Soft-restraint summary (bond/angle/value deviations).  Rietveld-only, so
    # model.restraints is None outside it and this is naturally skipped.  A
    # restraint fighting the data (|dev/σ| large) becomes a RESTRAINT_TENSION
    # diagnostic — never hide a bad sub-fit.
    restraints_report = summarise_restraints(model.restraints, values,
                                             model.restraint_weight_scale)
    if restraints_report is not None:
        diagnostics = diagnostics + _restraint_tension_diagnostics(
            restraints_report, structure)

    # Bonding geometry, with esds through the *whole* covariance (WP-1072,
    # McCusker §10) — built here because that covariance is read off the final
    # Jacobian and never serialized, the Identifiability carrier argument.  The
    # table judges nothing; §11's "chemical sense" is the reader's call.
    geometry = geometry_table(model, table, theta, structure,
                              stderr_internal=stderr_internal,
                              correlation=correlation)

    # The widths read as a coherent domain size and a Δd/d (WP-1131), built
    # here for geometry's reason — the esds come off the same final Jacobian —
    # and through the same λ selector the size bound and the size flag use, so
    # the three cannot attribute one coefficient to different wavelengths.
    # ``stderr_phys`` rather than a second ``stderr_physical`` call: with a
    # correlation matrix that build is a dense n x n, which a Pawley table
    # makes large, and the two calls would return the same dict.
    microstructure = microstructure_table(
        structure, values, wavelength=_longest_line_wavelength(model),
        esds=stderr_phys)

    # Specimen absorption: report what was applied and, crucially, the Biso
    # bias it removed — for a capillary Rwp is provably unchanged by it, so
    # nothing else in the result would show that the correction did anything.
    absorption = _absorption_record(model, mu_r_source, mu_r_skipped, values)
    if absorption is not None:
        diagnostics = diagnostics + _absorption_diagnostics(absorption)

    # The position aberration this geometry has and could not express, for the
    # same reason as above: nothing else in the result says it was unavailable
    # rather than measured at zero.
    diagnostics = diagnostics + _capillary_offset_diagnostics(model, table)

    # Surface-roughness regime fences (WP-0502): whether the fitted range can
    # see the correction at all, and whether it left its derivation's domain.
    diagnostics = diagnostics + _roughness_regime_diagnostics(model, values)

    # A declared λ/n monochromator harmonic, and what fraction of the
    # fundamental it refined to.  Empty unless the source declared one, so this
    # is silent on every model built before harmonics existed.
    diagnostics = diagnostics + _harmonic_diagnostics(
        model, values, set(table.free_paths), stderr_phys)

    # A refined wavelength, reported in ppm against its declared value — the
    # single-histogram twin of the joint diagnostic in ``multi.py`` (WP-1134),
    # for the case the held-cell fence exists to admit.  Empty unless a
    # wavelength was actually freed, and only when the caller passed the
    # pre-fit declared values: a wavelength refines against the *held cell*
    # here, which is the clause that differs from the joint framing.  ``replay``
    # passes nothing and reuses the node's recorded diagnostics instead.
    if declared_wavelengths is not None:
        diagnostics = diagnostics + _wavelength_calibration_diagnostics(
            declared_wavelengths, table, values, stderr_phys,
            pinned_by=_WAVELENGTH_PINNED_BY_HELD_CELL)

    # A phase the data cannot see (WP-1110), and what the run did about it
    # (WP-1301).  Named here rather than left to HIGH_CORRELATION, which reports
    # the ρ≈1 between the phase's cell and its scale — the symptom — while this
    # reports the cause.  The stage records carry the hold, so the message and
    # the record quote one measurement.
    diagnostics = diagnostics + _phase_support_diagnostics(
        model.phase_support(values), model.phase_line_counts(),
        (model.tt_min, model.tt_max), list(table.free_paths), structure,
        stage_results)

    # A strain broader than solved refinements normally use — a flag to check,
    # not a bound (the bound is params.vector.strain_cap, one tier up).
    diagnostics = diagnostics + _strain_flag_diagnostics(model, values, structure)

    # A crystallite smaller than solved refinements normally report — the size
    # twin of the flag above (bound: params.vector.size_cap, one tier up).
    diagnostics = diagnostics + _size_flag_diagnostics(model, values, structure)

    # The two robustness statements that are about the *run* rather than a
    # parameter, so they are Diagnostics here rather than GuardFindings (which
    # exist to carry paths — these have none).  Both cover the silent-failure
    # case a batch caller hits: a status of "converged" that is true of the
    # solver and false of the answer (WP-1028 §§(c),(d)).
    diagnostics = (diagnostics
                   + _far_from_data_diagnostics(model, y_calc, y_bkg, stats)
                   + _max_iter_diagnostics(stage_results))

    # Does the data support it (WP-1071): the observation/parameter ratio and
    # the step size, both reported and neither gating.  Built before the
    # result so the diagnostic and the record quote one measurement.
    support = data_support(model, values, list(table.free_paths))
    diagnostics = diagnostics + _data_support_diagnostics(support, model)

    # The region below the first reflection (Q3): read off the fit's own
    # residual, never the background-envelope proxy above — same ``ticks``
    # this function already built, so the two cannot disagree about where
    # the first reflection sits.
    diagnostics = diagnostics + _low_angle_diagnostics(
        model, values, y_calc, stats, ticks, tick_support)

    # What a declared sharp peak did, once the fit has an answer about it
    # (WP-1103).  Built after ``ticks`` because "is this component sitting on a
    # reflection" is asked against the same predicted positions Layer 0 uses,
    # and the two must not disagree about where the model puts a line.
    diagnostics = diagnostics + _extra_peak_diagnostics(
        model, values, ticks, table)

    # Degeneracy evidence off the answer-producing stage's Jacobian, which is
    # not serialized and so cannot be recovered later (WP-1055/-1056).  The
    # same numbers the guards screened, carried whole rather than as the
    # fired subset — the FitReport's background and identifiability sections
    # quote them.
    identifiability = None
    if guard is not None and (guard.measured_background_absorption
                              or guard.measured_extra_peak_absorption
                              or guard.measured_top_correlations
                              or guard.measured_soft_modes
                              or guard.measured_exchangeability):
        identifiability = Identifiability(
            background_absorption=dict(guard.measured_background_absorption),
            extra_peak_absorption=dict(guard.measured_extra_peak_absorption),
            top_correlations=list(guard.measured_top_correlations),
            soft_modes=list(guard.measured_soft_modes),
            exchangeability=list(guard.measured_exchangeability))

    return RefinementResult(
        status=status, mode=mode,
        parameters=params, statistics=stats,
        stages=stage_results, diagnostics=diagnostics,
        provenance=Provenance(package_version=_VERSION, created_utc=_utcnow(),
                              backend=backend, dtype=backend_dtype_note(backend),
                              solver=solver,
                              report_thresholds_version=THRESHOLDS_VERSION),
        two_theta=model.tt.tolist(), y_obs=model.y_obs.tolist(),
        y_calc=y_calc.tolist(), y_background=y_bkg.tolist(),
        sigma=model.sigma.tolist(),
        ticks=ticks, tick_hkl=tick_hkl,
        qpa=qpa, restraints=restraints_report, geometry=geometry,
        microstructure=microstructure,
        phase_agreement=_phase_agreement(model, values, structure),
        data_support=support,
        absorption=absorption, identifiability=identifiability,
        # Declared, not measured, so it is written here rather than behind the
        # guard above: every caller of this function has a compiled model, which
        # is the whole authority for the count, so ``replay`` reports it too.
        # Every declared component, both members — the field is named for
        # the list and a client reads it as that list's length.  It was
        # ``len(component_paths)`` while a hump was the only member and the
        # two coincided; since WP-1103 that tuple is the background-landing
        # half alone, so the sum is what keeps the name true.
        n_extra_components=(len(model.component_paths)
                            + len(model.peak_components)),
        n_background_components=len(model.component_paths),
    )


def _extract_reflections(model: CompiledModel | None) -> list[ReflectionState]:
    """Capture the per-hkl state that is not in the parameter vector.

    Le Bail intensities are tagged ``lebail_extracted`` (no esds); Pawley
    intensities are ``pawley_refined`` and carry their per-reflection esds and
    ``varied=True`` — the distinction is what lets a checkout reseed a Le Bail
    fixed point but restore a Pawley refinement's actual values.
    """
    if model is None or model.mode not in ("lebail", "pawley"):
        return []
    is_pawley = model.mode == "pawley"
    stderr_all = model.pawley.stderr if (is_pawley and model.pawley is not None) else None
    out: list[ReflectionState] = []
    for ip, cp in enumerate(model.phases):
        if cp.hkl_intensity is None:
            continue
        state = ReflectionState(
            phase_index=ip,
            hkl=[[int(v) for v in h] for h in cp.reflections.hkl],
            intensity=[float(v) for v in cp.hkl_intensity],
            kind="pawley_refined" if is_pawley else "lebail_extracted",
            varied=is_pawley,
        )
        if is_pawley and stderr_all is not None:
            a, b = model.pawley.phase_slices[ip]
            state.stderr = [float(v) for v in stderr_all[a:b]]
        out.append(state)
    return out


def _scatter_lebail(lookup: dict[tuple, float], cp_new) -> None:
    """Write intensities into a freshly compiled phase, matching by hkl."""
    if cp_new.hkl_intensity is None:
        return
    for i, h in enumerate(map(tuple, cp_new.reflections.hkl)):
        value = lookup.get(h)
        if value is not None:
            cp_new.hkl_intensity[i] = value


def _carry_lebail(old: CompiledModel, new: CompiledModel) -> None:
    """Carry per-hkl intensities across a stage recompile (match by hkl)."""
    for cp_old, cp_new in zip(old.phases, new.phases, strict=True):
        if cp_old.hkl_intensity is None:
            continue
        lookup = {tuple(h): float(cp_old.hkl_intensity[i])
                  for i, h in enumerate(map(tuple, cp_old.reflections.hkl))}
        _scatter_lebail(lookup, cp_new)


def _restore_lebail(states: list[ReflectionState], model: CompiledModel) -> None:
    """Re-seed per-hkl intensities from a checkpoint (match by hkl)."""
    for state in states:
        if not 0 <= state.phase_index < len(model.phases):
            continue
        lookup = {tuple(h): state.intensity[i] for i, h in enumerate(state.hkl)}
        _scatter_lebail(lookup, model.phases[state.phase_index])


#: Relative gap between χ² on the last stage's frozen compile and on a fresh
#: compile at the returned values above which ``FROZEN_COMPILE_STALE`` reports
#: it (#272).  One part in a hundred, set from the gap measured on the 358
#: fits the acceptance files and the synthetic chains run: every single-pattern
#: acceptance fixture sits at or under 2.8e-3 (Si SRM 640c 8e-5, FAP 2e-4,
#: Stephens brucite 2.5e-3) and the held-phase ramp under 5.2e-3, while the QPA
#: round-robin sample-1 chain reaches 1.3-2.1e-2.  At 1e-3 it fired on 74 of
#: the 358, a fifth of ordinary fits, which is noise and not a signal.  The
#: issue's 1.38 % on Si is the compile that claims nothing moves
#: (``moving_paths=None``), not the frozen one, and would still fire.
FROZEN_COMPILE_CHI2_REL = 1e-2


#: a Pawley overlap group is reported unresolved when *any* member carries a
#: relative esd above this — that reflection's intensity is not apportioned by
#: the data even though the group sum is fixed
PAWLEY_UNRESOLVED_REL = 0.3


def _pawley_n(model: CompiledModel | None) -> int:
    """Free-parameter count contributed by the Pawley intensity block."""
    return model.pawley.n if (model is not None and model.pawley is not None) else 0


def _pawley_unresolved_diagnostics(model: CompiledModel,
                                   structure: Structure) -> list[Diagnostic]:
    """Flag overlapped groups whose intensity *split* the data cannot resolve.

    The summed intensity of an overlapped group is determined; its partition is
    not, and the equal-split restraint leaves that ambiguity visible as a large
    per-reflection esd.  A group is reported when *any* member's relative esd
    exceeds :data:`PAWLEY_UNRESOLVED_REL` — a reflection the data cannot pin is a
    confident-wrong-singleton risk even when a stronger neighbour in the same
    group is well determined, so flagging the whole group is the safe report.
    """
    pb = model.pawley
    if pb is None or pb.stderr is None or not pb.groups:
        return []
    intens = model.pawley_x0()
    out: list[Diagnostic] = []
    for g in pb.groups:
        inten = intens[list(g)]
        sd = np.asarray(pb.stderr)[list(g)]
        rel = sd / np.maximum(np.abs(inten), 1e-10)
        if float(np.max(rel)) < PAWLEY_UNRESOLVED_REL:
            continue  # every member is pinned by the data — the split is real
        labels = []
        for gi in g:
            ip, k = _pawley_locate(pb, gi)
            h = tuple(int(v) for v in model.phases[ip].reflections.hkl[k])
            labels.append(f"{structure.phases[ip].name} {h}")
        total = float(np.sum(inten))
        out.append(Diagnostic(
            level="info", code="PAWLEY_OVERLAP_UNRESOLVED", where=labels,
            message=(f"{len(g)} reflections overlap too strongly to split: their "
                     f"summed intensity ({total:.4g}) is determined but at least "
                     f"one individual value is not (relative esd up to "
                     f"{float(np.max(rel)):.0%})"),
            suggestion="treat the group's summed intensity as the datum; the "
                       "per-reflection split is not resolved by these data",
        ))
    return out


def _pawley_off_data_diagnostics(model: CompiledModel,
                                 structure: Structure) -> list[Diagnostic]:
    """Name, per phase, the reflections whose intensity came from the ridge.

    A reflection with no emission line centred on the fitted data is kept in
    the list (so a stage can move it onto the data) and ridged toward zero
    (:meth:`CompiledModel.build_pawley_restraint`, WP-1459).  Its reported
    intensity is then the ridge's answer, not the data's, and nothing in the
    value or its esd says so — the overlap rows' precedent
    (:func:`_pawley_unresolved_diagnostics`) is to name what the restraint set.
    """
    pb = model.pawley
    if pb is None or not pb.off_data:
        return []
    by_phase: dict[int, list[str]] = {}
    for gi in pb.off_data:
        ip, k = _pawley_locate(pb, gi)
        h = tuple(int(v) for v in model.phases[ip].reflections.hkl[k])
        by_phase.setdefault(ip, []).append(f"{structure.phases[ip].name} {h}")
    return [Diagnostic(
        level="info", code="PAWLEY_OFF_DATA_RIDGED", where=labels,
        message=(f"{len(labels)} reflection(s) of {structure.phases[ip].name} have "
                 f"no emission line centred on the fitted data; their "
                 f"intensities were ridged toward zero and are the ridge's "
                 f"value, not a measurement"),
        suggestion="do not export or use these intensities; widen the fitted "
                   "range if they are needed",
    ) for ip, labels in by_phase.items()]


#: a species whose |f|² at k = 0 moves by more than this fraction when f′, f″
#: are applied is reported as a neglected correction.  2 % is set by what it
#: costs: the v0.3 QPA acceptance carries a several-wt-% bias whose sign and
#: size the neglected corrections reproduce (WP-0504), and the phases driving
#: it sit at 5-16 %.
DISPERSION_NEGLECT_FRAC = 0.02
#: above this the effect is large enough that the numbers should not be
#: quoted without it, so the diagnostic escalates from info to warning
DISPERSION_NEGLECT_SEVERE = 0.05


def _symmetry_silence_diagnostics(structure: Structure,
                                  mode: str = "rietveld") -> list[Diagnostic]:
    """The two ways a structure's symmetry can be wrong without saying so.

    Both are about *how many atoms a site puts in the cell* — the number that
    feeds ``phase_zmv`` and therefore every weight fraction — and neither shows
    up in Rwp, which is why they are reported here rather than left to a fit to
    reveal (issues #215 and #217, WP-1324).

    ``SITE_SNAPPED_TO_SPECIAL_POSITION``: a site within the site tolerance of a
    special position but not on it.  ``crystallography.symmetry`` builds the
    message, so a structure read from a CIF says the same thing on the reader's
    channel that a hand-built one says here.

    ``SPACE_GROUP_SETTING_ASSUMED``: a bare H-M symbol where the tables hold
    more than one setting.  The **composition each setting implies** is the
    discriminator, not the symbol — spinel's tetrahedral and octahedral
    multiplicities swap between ``F d -3 m:1`` and ``:2``, so origin-2
    coordinates under the bare symbol give A₂BO₄ where AB₂O₄ was meant — so the
    message quotes both, and the caller recognises which one they meant.

    ``mode`` decides how much of that a phase's atoms can be asked.  Outside
    ``"rietveld"`` they are a Le Bail or Pawley **scaffold** — one dummy atom
    standing in for a structure nobody supplied — so a snap is a report about a
    placeholder and a composition is a fiction (``C8`` from the dummy carbon).
    The setting still matters there and is still reported: ``:H`` against
    ``:R`` changes the operators themselves, not only the origin.
    """
    from .crystallography.symmetry import (
        resolve_group,
        setting_diagnostics,
        snap_diagnostics,
        split_group_label,
    )

    structural = mode == "rietveld"
    out: list[Diagnostic] = []
    for i, phase in enumerate(structure.phases):
        sg = resolve_group(phase.space_group, phase.symmetry_operations)
        if structural:
            out.extend(snap_diagnostics(
                sg,
                [(a.label, (a.x.value, a.y.value, a.z.value)) for a in phase.atoms],
                source=f"phase {phase.name!r}", prefix=f"phases.{i}"))

        # **A label is not a symbol.**  The setting-assumed warning asks which
        # of a *symbol's* tabulated settings gemmi picked; a phase carrying its
        # own operation list has no ambiguity to warn about — the operations
        # say which setting it is in — and the bracketed label names a type
        # rather than a setting, so resolving it here would compare the cell
        # contents of settings the phase never claimed to be in.
        if split_group_label(phase.space_group) is not None:
            continue
        # ``mode`` decides whether the atoms may be asked for a composition:
        # outside rietveld they are a scaffold and ``C8`` from a dummy carbon is
        # a fiction.  The setting is reported either way.
        out.extend(setting_diagnostics(
            phase.space_group,
            source=f"phase {phase.name!r}",
            where=[f"phases.{i}.space_group"],
            cell=(tuple(getattr(phase.cell, n).value
                        for n in ("a", "b", "c", "alpha", "beta", "gamma"))
                  if structural else None),
            sites=([(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
                    for a in phase.atoms] if structural else None)))
    return out


def _dispersion_diagnostics(structure: Structure,
                            instrument: Instrument) -> list[Diagnostic]:
    """Flag anomalous corrections the model is *not* applying.

    ``Source.dispersion`` has been **on by default since v1.0**, so this fires
    only for a caller who set it to ``None`` — declining is now the act that
    needs saying out loud, and the two legitimate reasons for it (reproducing
    a pre-v1.0 number, or a wavelength inside an absorption-edge interval
    where the table is wrong in principle) both leave a fit whose intensities
    are knowingly mis-scaled.  The size reported is the change in |f|² at k = 0,
    ((Z + f′)² + f″²)/Z², which is the fraction by which every reflection of
    that species' contribution is mis-scaled.  A refinement is never blocked
    by a lookup failure here: an untabulated element or an on-edge wavelength
    is skipped, because enabling the block is what should raise, not
    describing it.
    """
    import gemmi

    from .crystallography.dispersion import dispersion, normalize_element

    # A neutron source has no anomalous dispersion to neglect: f'/f'' is an
    # X-ray core-level effect, so this diagnostic would be advising a caller to
    # restore a correction that does not exist for their radiation. The neutron
    # analogue -- complex b near a nuclear resonance -- belongs to a handful of
    # nuclides rather than to the source, and lives in crystallography.neutron.
    if instrument.source.kind != "xray_cw":
        return []
    if instrument.source.dispersion is not None:
        return []
    lam = instrument.source.primary_wavelength
    effects: dict[str, float] = {}
    for phase in structure.phases:
        for atom in phase.atoms:
            try:
                sym = normalize_element(atom.species)
                if sym in effects:
                    continue
                z = float(gemmi.Element(sym).atomic_number)
                fp, fpp = dispersion(sym, lam)
            except (KeyError, ValueError):
                continue
            if z <= 0.0:
                continue
            effects[sym] = abs(((z + fp) ** 2 + fpp ** 2) / z ** 2 - 1.0)
    flagged = {s: v for s, v in effects.items() if v >= DISPERSION_NEGLECT_FRAC}
    if not flagged:
        return []
    worst = max(flagged.values())
    named = ", ".join(f"{s} {v:.0%}" for s, v in
                      sorted(flagged.items(), key=lambda kv: -kv[1]))
    return [Diagnostic(
        level="warning" if worst >= DISPERSION_NEGLECT_SEVERE else "info",
        code="DISPERSION_NEGLECTED",
        message=(f"anomalous scattering is off, but at lambda = {lam:.5f} A it "
                 f"changes the scattering power of {named}"),
        suggestion="this model sets instrument.source.dispersion = None, "
                   "declining a correction that is on by default; restore it "
                   "with Dispersion() — it is a fixed constant, not a refined "
                   "parameter, and unequal effects across phases bias QPA "
                   "weight fractions directly. If it was declined because the "
                   "wavelength sits in an absorption-edge interval, supply the "
                   "measured pair through Dispersion.overrides instead",
    )]


#: A resonant absorber whose *element* absorbs at least this much is reported
#: as a warning rather than as info.  1000 barn separates the four classic
#: black absorbers on this table -- Cd 2520, Eu 4530, Sm 5923, Gd 49700 -- from
#: Yb, whose element absorbs 34.80 and whose resonance lives in one minority
#: isotope (``168Yb``, 2230.40).  The split is about how much of the beam the
#: specimen eats, which is a different question from whether b is complex, and
#: both are worth saying.
RESONANT_ABSORBER_SEVERE_BARN = 1000.0


def _resonant_absorber_diagnostics(structure: Structure,
                                   instrument: Instrument) -> list[Diagnostic]:
    """Name a resonant absorber instead of silently using its thermal ``b``.

    The neutron analogue of ``DISPERSION_NEGLECTED`` (issue #113 (a),
    WP-1312).  For a handful of nuclides the tabulated bound coherent
    scattering length is complex and varies with wavelength near a nuclear
    resonance; ``b_Sears.dat`` stores the **real part of the thermal value**
    and nothing else, so a refinement of such a species is using a number that
    is incomplete rather than wrong.  At one constant wavelength away from the
    resonance the thermal value is the right one, which is why this is a
    statement and not a refusal -- but nothing said so, and
    ``is_resonant_absorber`` had no caller in the package at all.

    Neutron sources only: ``f'/f''`` is the X-ray effect and it has its own
    diagnostic, so this is the same gate ``_dispersion_diagnostics`` uses,
    the other way round.

    Everything reported comes from the shipped table, so a reader can check it
    against ``src/rietx/data/b_Sears.dat`` without leaving the repository.
    Deliberately **not** reported: the resonance energy per nuclide, which
    WP-1312 also asks for.  That needs a citation this package does not
    currently carry (Mughabghab's *Atlas of Neutron Resonances* is the usual
    source) and transcribing it from memory is the failure this campaign has
    already met once -- so the flag lands without it, and the energies can be
    added with their citation.
    """
    from .crystallography.neutron import (  # noqa: PLC0415
        is_resonant_absorber,
        normalize_species,
        properties,
    )

    if instrument.source.kind == "xray_cw":
        return []
    flagged: dict[str, float] = {}
    where: list[str] = []
    for i, phase in enumerate(structure.phases):
        for j, atom in enumerate(phase.atoms):
            if not is_resonant_absorber(atom.species):
                continue
            sym = normalize_species(atom.species)
            where.append(f"phases.{i}.atoms.{j}")
            if sym in flagged:
                continue
            try:
                flagged[sym] = float(properties(sym)["xs_abs_barn"])
            except KeyError:
                flagged[sym] = float("nan")
    if not flagged:
        return []
    worst = max((v for v in flagged.values() if v == v), default=0.0)
    named = ", ".join(f"{s} {v:.0f} barn" for s, v in
                      sorted(flagged.items(), key=lambda kv: -kv[1]))
    return [Diagnostic(
        level=("warning" if worst >= RESONANT_ABSORBER_SEVERE_BARN else "info"),
        code="NEUTRON_RESONANT_ABSORBER",
        where=sorted(where),
        message=(f"this structure contains a resonant absorber ({named}); the "
                 f"tabulated b is the real part of the thermal value and is "
                 f"incomplete near the resonance"),
        suggestion="at one constant wavelength away from the resonance the "
                   "thermal value is the right number and nothing is owed. "
                   "Check that this wavelength is away from it before quoting "
                   "an occupancy or a displacement parameter on that site: b "
                   "is complex there, and this table carries only its real "
                   "part, so both the amplitude and the phase of that species' "
                   "contribution are wrong near a resonance in a way no "
                   "agreement index will show. A wavelength-resolved fit "
                   "(a range of wavelengths, or TOF) may not use one thermal "
                   "value at all",
    )]


#: Fires when a substitution's |electron-count error| is at least this
#: fraction of the ion's true count.  0.0 fires on **any** substitution — the
#: choice issue #202 leaves to the maintainer, argued for on the grounds that
#: a substitution the code chose silently is exactly what should be visible,
#: with the user left to judge materiality.  A one-line change to a nonzero
#: fraction restricts the diagnostic to substitutions past that size instead.
SPECIES_FALLBACK_MIN_DELTA_FRAC = 0.0


def _species_fallback_diagnostics(structure: Structure,
                                  instrument: Instrument) -> list[Diagnostic]:
    """Flag an ion ``normalize_species`` could not find, one row per label
    (issue #202).

    ``crystallography.scattering.normalize_species`` falls back to the neutral
    atom when an ion is absent from the Waasmaier-Kirfel table — deliberate
    (refusing would break files that currently refine, and 99 of 111
    chemically-real oxidation states resolve correctly) but previously silent:
    nothing recorded that the model's scattering power was not what the
    species label claimed. A wrong electron count biases site occupancies,
    ADPs and QPA fractions without moving Rwp much, because the model simply
    rescales — the same shape as a phase compile silently accepting an
    ambiguous choice, which is why this is computed alongside
    ``_dispersion_diagnostics`` rather than left to whatever first calls
    ``f0`` downstream.

    Neutron phases resolve species through ``crystallography.neutron``
    instead — a different table with a different (isotope-aware) fallback —
    so this is silent there, the same gate ``_dispersion_diagnostics`` uses
    for the reciprocal reason (an X-ray core-level effect neutron has none of).
    """
    from .crystallography.scattering import detect_fallback

    if instrument.source.kind == "neutron_cw":
        return []
    # {raw species label -> (SpeciesFallback, [atom paths])}; grouped by the
    # label as written so two different ions of the same element (Fe2+ *and*
    # Fe3+, say) are not merged into one row if only one of them falls back.
    found: dict[str, tuple] = {}
    for ip, phase in enumerate(structure.phases):
        for j, atom in enumerate(phase.atoms):
            fb = detect_fallback(atom.species)
            if fb is None:
                continue
            path = f"phases.{ip}.atoms.{j}.species"
            if fb.species in found:
                found[fb.species][1].append(path)
            else:
                found[fb.species] = (fb, [path])
    out = []
    for fb, where in found.values():
        delta = fb.delta_frac
        # `delta` is None only when the ion's own electron count is zero
        # (formal charge == Z, e.g. H1+/He2+) -- the fractional error is
        # undefined, not below any threshold, so it always fires rather than
        # being compared against SPECIES_FALLBACK_MIN_DELTA_FRAC.
        if delta is not None and abs(delta) < SPECIES_FALLBACK_MIN_DELTA_FRAC:
            continue
        frac_text = ("undefined — the ion's own electron count is zero"
                     if delta is None else f"{delta:+.1%}")
        out.append(Diagnostic(
            level="warning", code="SPECIES_FALLBACK_NEUTRAL", where=where,
            value=delta,
            message=(f"{fb.species!r} is absent from the Waasmaier-Kirfel "
                     f"table and was scattered as neutral {fb.element} "
                     f"instead — {fb.returned_electrons:.4g} electrons "
                     f"against the ion's {fb.true_electrons:.0f} "
                     f"({frac_text})"),
            suggestion=(f"this changes every reflection {fb.species!r} "
                        "contributes to by that fraction and biases site "
                        "occupancies, ADPs and QPA fractions together, "
                        "without moving Rwp much because the model "
                        "rescales; there is no override table for this "
                        "lookup the way Dispersion.overrides covers f'/f'', "
                        f"so either accept that neutral {fb.element} is what "
                        "was fitted or substitute a tabulated ion of the "
                        "same element and a nearby charge as a deliberate "
                        "approximation"),
        ))
    return out


#: Below this refined fraction a declared λ/n harmonic is reported as **not
#: detected** rather than measured.  Not a tuning and not a detection limit:
#: the weight's own esd is the detection limit and the diagnostic quotes it.
#: This is the band inside which the fitted value is indistinguishable from the
#: zero its bound sits at, so calling it a measurement of the beam would be the
#: confident wrong singleton the FitReport rules exist to prevent.  0.1 % is one
#: tenth of :data:`~rietx.schemas.instrument.HARMONIC_WEIGHT_SEED`, i.e. the
#: refinement travelled *away* from its seed toward zero and stayed there.
HARMONIC_ABSENT_FRAC = 1e-3

#: Above this refined fraction the number is reported as evidence about the
#: **model**, not about the beam.  Reported values for real monochromators are a
#: few per cent — the published Nd₂Ru₂O₇ pyrochlore refinement carried its λ/2
#: entry at 1.2 % of the fundamental's scale — and a harmonic an order above
#: that is a line being used as a general-purpose intensity sink for peaks the
#: model puts nowhere: an unindexed impurity, a magnetic contribution, a
#: background too stiff to follow. Placed an order of magnitude above the
#: reported band rather than at its edge, so a genuinely strong harmonic is
#: still reported as one.
HARMONIC_IMPLAUSIBLE_FRAC = 0.15


def _harmonic_diagnostics(model: CompiledModel, values: dict[str, float],
                          free_paths: set[str],
                          stderr: dict[str, float]) -> list[Diagnostic]:
    """``HARMONIC_FRACTION``: what a declared λ/n line refined to, in per cent.

    The number a user judges this correction by is the fraction of the
    fundamental the harmonic carries, so that is what is reported — not the
    internal weight, and never an Rwp comparison (which is not evidence for a
    correction; see CLAUDE.md).  Three distinct statements, because a fitted
    fraction can fail in three different ways and only one of them is a
    measurement:

    * **held** — the weight never entered θ, so the value is the caller's
      assumption dressed as a result.  Reported so it cannot be quoted.
    * **absent** — refined to within :data:`HARMONIC_ABSENT_FRAC` of zero.  A
      *positive* result about the beam, and the one this correction's negative
      control turns on: a Ge monochromator cut on all-odd indices has an
      extinct second order, and the fit should find nothing.
    * **implausible** — past :data:`HARMONIC_IMPLAUSIBLE_FRAC`, or sitting on
      the parameter's upper bound.  The line is absorbing something that is not
      a harmonic.

    This is the *post-fit, refined* counterpart of the **pre-fit, model-free**
    contamination flags in :mod:`rietx.background.diagnostics`
    (``ContaminationFlag``, ``kind="kbeta"``/``"tungsten_la"``), and the
    difference is what each can be used for.  Those look for a weak peak at a
    known ghost wavelength in the *raw* pattern, need no structure and no
    refinement, and answer "is there something here that looks like a known
    contaminant?".  This one needs a converged model and answers "how much of
    the intensity did the model attribute to the harmonic once everything else
    had its chance?".  Neither substitutes for the other: the pre-fit check
    fires on a pattern nobody has modelled, and this one sees a contamination
    whose peaks overlap the fundamental's too closely for a peak search to
    separate.
    """
    out: list[Diagnostic] = []
    for il, order in sorted(model.harmonic_orders.items()):
        path = f"instrument.source.lines.{il}.weight"
        frac = float(values.get(path, 0.0))
        # ``line_lambdas`` and not ``line_wavelengths``: the latter is the
        # compile-time tuple, and a derived harmonic's entry in it goes stale
        # as soon as the fundamental refines.  Reporting a lambda/n the fit did
        # not use is the shape this package's evidence rule exists to prevent.
        lam = model.line_lambdas(values)[il]
        esd = stderr.get(path)
        pct = 100.0 * frac
        where = [path]
        esd_txt = f" ± {100.0 * esd:.2f}" if esd is not None else ""
        head = (f"lambda/{order} = {lam:.5f} A carries {pct:.2f}{esd_txt} % of "
                f"the fundamental")
        if path not in free_paths:
            out.append(Diagnostic(
                level="info", code="HARMONIC_HELD", where=where,
                message=(f"{head}, but the weight was never refined -- that is "
                         f"the declared value, not a measured one"),
                suggestion=("free instrument.source.lines.*.weight in a stage "
                            "after the profile and the scale have settled; a "
                            "held harmonic weight must not be quoted as a "
                            "property of the beam")))
            continue
        if frac < HARMONIC_ABSENT_FRAC:
            out.append(Diagnostic(
                level="info", code="HARMONIC_ABSENT", where=where,
                message=(f"the declared lambda/{order} line refined to "
                         f"{pct:.3f}{esd_txt} % of the fundamental, i.e. to "
                         f"nothing"),
                suggestion=("this is a result, not a failure: the beam carries "
                            "no measurable order-n contamination, which is what "
                            "a monochromator whose nth order is extinct should "
                            "give. Dropping the declaration reproduces the fit "
                            "and removes a parameter the data does not support")))
            continue
        implausible = frac > HARMONIC_IMPLAUSIBLE_FRAC
        out.append(Diagnostic(
            level="warning" if implausible else "info",
            code="HARMONIC_FRACTION", where=where,
            message=(head + (", which is far above the few per cent a "
                             "monochromator harmonic is reported at"
                             if implausible else "")),
            suggestion=(("a fraction this large is evidence about the model "
                         "rather than about the beam -- the line is absorbing "
                         "intensity the model puts nowhere (an unindexed "
                         "impurity, a magnetic contribution, a background too "
                         "stiff to follow). Check the tick marks against the "
                         "unfitted peaks before believing it")
                        if implausible else
                        ("quote this as a property of this beam on this "
                         "monochromator, never as one of the specimen, and "
                         "never transfer it to another histogram -- it is a "
                         "refined scale ratio between two wavelength "
                         "components of one measurement"))))
    return out


def _wavelength_calibration_diagnostics(
        declared: list[float], table, values: dict[str, float],
        esd: dict[str, float], *, pinned_by: str,
        h: int | None = None) -> list[Diagnostic]:
    """``WAVELENGTH_CALIBRATION`` — how far a refined λ moved, in ppm.

    A refined wavelength is a **measurement of the monochromator's calibration
    error**, and ppm is the unit it is quoted in: 100-200 ppm is a real
    take-off-angle or lattice-constant error on a CW instrument, and it is the
    same size as the cell discrepancies that motivate freeing it at all.  The
    package's rule is that a new correction ships with a record field or a
    diagnostic saying what it changed and never with an Rwp comparison as its
    evidence (root ``CLAUDE.md``); this is that statement for this one, and it
    is deliberately the *only* number the feature is defended with.

    Reported at ``info`` with no threshold, because there is no published band
    to quote and a tuned one would pretend to a judgement the diagnostic cannot
    make — whether a 300 ppm move is a calibration error or a wrong wavelength
    depends on the beamline, not on the fit.  What it does carry is Δλ/σ, so a
    reader can see whether the move is resolved at all: a freed λ that comes
    back inside its own esd measured nothing, which is a different (and
    commoner) outcome from one that measured a calibration error.

    Two callers, one function.  ``h`` selects the histogram framing —
    ``None`` for a single-histogram fit (``refine.py``), an index for a joint
    one (``multi.py``), which is the whole difference in the message's *head*
    and its ``where`` addressing.  The message's *last clause* is passed in as
    ``pinned_by`` because the two are false of each other: a single histogram
    measures λ against the **held cell**, a joint fit against the cell pinned by
    the histogram whose λ is held.  ``declared`` is λ per line as taken off the
    instrument the ``Refinement`` was **constructed** with (or last edited to) —
    the refined values have been written back by the time a result is built, so
    there is nothing left to compare to otherwise — and is indexed by line,
    matching the ``.lines.<il>.`` path segment.  Because the reference is fixed
    at construction, a :meth:`~Refinement.checkout` to an earlier node does
    **not** reset it, and a :meth:`~Refinement.branch` **inherits** the root's
    reference rather than re-declaring its own (both are history navigation over
    one physical instrument, and a rival strategy the diagnostic exists to
    compare must quote the same reference): the ppm is a fact about the built
    instrument, not about whatever node the working state currently stands on,
    so a second λ-freeing call — on this Refinement or on a branch of it —
    reports the cumulative move from the declared value, never a delta from the
    previous call.  Only an :meth:`~Refinement.edit` that replaces the
    instrument re-declares.
    """
    out: list[Diagnostic] = []
    for e in table.entries:
        if not (_is_wavelength(e.path) and e.vary):
            continue
        il = int(e.path.split(".")[3])
        lam0 = declared[il]
        lam = values[e.path]
        ppm = 1e6 * (lam - lam0) / lam0
        sigma = esd.get(e.path)
        resolved = ("" if sigma in (None, 0.0)
                    else f", {abs(lam - lam0) / sigma:.1f}× its own esd "
                         f"({sigma:.2e} A)")
        head = f"line {il}" if h is None else f"histogram {h} line {il}"
        where = [e.path] if h is None else [f"hist.{h}.{e.path}"]
        out.append(Diagnostic(
            level="info", code="WAVELENGTH_CALIBRATION",
            message=(f"{head}: wavelength refined from the "
                     f"declared {lam0:.6f} A to {lam:.6f} A, {ppm:+.1f} ppm"
                     f"{resolved}.  This is a measurement of that "
                     f"monochromator's calibration error, {pinned_by}"),
            where=where, value=float(ppm),
            suggestion=("compare it with the instrument's own calibration "
                        "history before quoting the cell: a wavelength that "
                        "moved further than the beamline's known drift is more "
                        "likely a modelling error in this histogram (an "
                        "unmodelled harmonic, a zero-shift traded against λ) "
                        "than a real calibration shift")))
    return out


#: the ``WAVELENGTH_CALIBRATION`` clause naming what pins the scale the refined
#: λ is measured against — the held cell for a single histogram, the cell a
#: held wavelength pins for a joint fit (the two are false of each other, so
#: each caller states its own; see :func:`_wavelength_calibration_diagnostics`).
_WAVELENGTH_PINNED_BY_HELD_CELL = "taken against the held cell"
_WAVELENGTH_PINNED_BY_HELD_HISTOGRAM = (
    "taken against the cell pinned by the histogram whose wavelength is held")


def _declared_wavelengths(instrument: Instrument) -> list[float]:
    """λ per emission line as it stands, in line order.

    Snapshotted **at construction** (``Refinement.__init__``, and again on an
    instrument :meth:`~Refinement.edit`) into ``self._declared_wavelengths``,
    then handed to :func:`_build_result` unchanged by every verb — a stage
    writes the refined value back onto the instrument, so by the time the result
    is built there is nothing left to compare a refined λ to, and snapshotting
    per call would make a second λ-freeing call report against the first call's
    answer rather than against the declared value.  A :meth:`~Refinement.branch`
    inherits the reference rather than re-snapshotting it, because it is built
    from an instrument already carrying a refined λ.  The joint path
    (``multi.py``) snapshots the same list at construction for the same reason.
    """
    return [p.value for p in instrument.source.wavelength_parameters]


#: a soft restraint is flagged in tension when its computed value sits more
#: than this many σ from the target — the data and the prior disagree, which
#: must be visible rather than silently averaged into a slightly-worse Rwp
RESTRAINT_TENSION_SIGMA = 3.0


def _restraint_tension_diagnostics(report, structure: Structure) -> list[Diagnostic]:
    """Flag restraints the data fights (|deviation/σ| beyond the threshold)."""
    out: list[Diagnostic] = []
    for row in report.rows:
        if abs(row.deviation_over_sigma) <= RESTRAINT_TENSION_SIGMA:
            continue
        out.append(Diagnostic(
            level="warning", code="RESTRAINT_TENSION",
            where=_restraint_where(row, structure),
            message=(f"{row.kind} restraint deviates "
                     f"{row.deviation_over_sigma:+.1f}σ from its target "
                     f"({row.computed:.4g} vs {row.target:.4g})"),
            suggestion="the data and this restraint disagree: loosen its sigma, "
                       "correct the target, or accept that the measured pattern "
                       "should override the prior (raise sigma so it does)",
        ))
    return out


#: Rwp above which a fit is reported as a **model/data mismatch** rather than
#: a converged refinement.  Not a quality bar — an honestly bad Rietveld fit
#: lands at 0.2-0.5 — and its placement is fixed at both ends by measurement
#: rather than taste (WP-1028 §(c)):
#:
#: * **Rwp = 1 is exactly "no better than y_calc ≡ 0"**, since Σw·Δ² = Σw·y_obs²
#:   there.  That is not the ceiling of the broken cases, it is their
#:   *attractor*: with the cell 3 % off, every reflection sits outside its
#:   frozen evaluation window, the only escape the solver has is to drive the
#:   scale to zero, and it converges — ``status="converged"`` — at Rwp
#:   0.99999.  A bar at 1.0 would miss the commonest failure by 1e-5.
#: * The failures that do exceed it exceed it enormously: 72.25 on a Le Bail
#:   fit from the source paper's own starting cells, 2.6e3 on a three-phase
#:   one.
#:
#: So 0.8 sits in a gap three orders of magnitude wide at the top and ~0.3
#: wide at the bottom, and catches the zero-scale attractor that is the whole
#: point.
MODEL_FAR_FROM_DATA_RWP = 0.8


def _far_from_data_diagnostics(model: CompiledModel, y_calc, y_bkg,
                               stats) -> list[Diagnostic]:
    """``MODEL_FAR_FROM_DATA``: the answer is not a refinement of this model.

    The defect this exists for is a *silent* one — the refinement does not
    error at Rwp = 7225 %, it returns ``status="converged"`` with the profile
    terms pinned to bounds, and a batch caller reads the status and believes
    it (WP-1028 §(c)).  ``report/layer2.py`` has emitted
    ``reindex_or_recheck_cell`` since v0.2, but at that Rwp nobody builds a
    report.

    The **cause is measured, not asserted**: the diagnostic reports what share
    of the observed above-background intensity the model actually put
    somewhere, because the signature of the frozen-window failure is that the
    calculated pattern is nearly all background — every reflection is being
    evaluated outside the window it was compiled with, so it contributes
    nothing anywhere.  A model that is merely *wrong* still has peaks.
    """
    if stats.rwp <= MODEL_FAR_FROM_DATA_RWP:
        return []
    import numpy as np

    bragg_calc = float(np.sum(np.asarray(y_calc) - np.asarray(y_bkg)))
    obs_excess = float(np.sum(np.asarray(model.y_obs) - np.asarray(y_bkg)))
    share = ""
    if obs_excess > 0.0:
        share = (f"; the model accounts for {bragg_calc / obs_excess:.1%} of "
                 f"the observed above-background intensity")
    return [Diagnostic(
        level="error", code="MODEL_FAR_FROM_DATA",
        message=(f"Rwp = {stats.rwp:.1%} — this is a mismatch between the "
                 f"model and the data, not a converged refinement{share}"),
        where=[],
        suggestion="do not read the status, the parameter values or their "
                   "esds: check the cell (the method needs it within ~1 %, "
                   "and further off puts every reflection outside its frozen "
                   "evaluation window), the wavelength, the zero shift and "
                   "the 2θ range, then re-index if the cell is the doubt",
    )]



def _extra_peak_diagnostics(model: CompiledModel, values: dict,
                            ticks: dict, table) -> list[Diagnostic]:
    """The two things a declared sharp peak is owed (WP-1103).

    Both **report and gate nothing.**  Declaring a peak the phases cannot
    account for is a legitimate act — it is the whole point of the member, and
    the alternative a caller would otherwise reach for (``excluded_regions``)
    masks the sample peak underneath along with the intruder.  What the package
    owes in return is honest evidence about what the declared peak then did.

    ``EXTRA_PEAK_ON_REFLECTION`` — the component sits within Layer 0's match
    tolerance of a position the model *already* predicts.  That is the
    impurity-shortcut use, and it is a scale/intensity degeneracy by
    construction: two terms describing one peak, with nothing in Rwp to say
    which owns the counts.  It may be exactly right (a holder line genuinely
    overlapping a reflection is the design case), which is why it is a warning
    about interpretation and not a refusal.

    ``EXTRA_PEAK_NO_INTENSITY`` — the area refined onto its zero bound.  A peak
    reaches the pattern only through ``area x profile``, so at zero area
    nothing constrains its centre either: it is the zero-scale phase of WP-1110
    item 13, one rank down, and the position it reports is a walk rather than a
    measurement.  Said in the vocabulary the peak list already chose for this
    fact (``no_intensity`` in ``PEAK_UNUSABLE_FLAGS``) rather than in a second
    one, and tested with ``BOUND_HIT_RTOL``, the distance half of the
    refinement's own bound test (``staged.bound_findings``, a conjunction
    since WP-1434) rather than a second constant.

    This is the honest evidence for "the peak was not needed", and it is not an
    Rwp comparison — which the package forbids as a correction's evidence for
    the reason ``docs/milestones/v0.5.md`` records.
    """
    from .report.layer0 import LAYER0_MATCH_TOL_DEG
    from .strategy.staged import BOUND_HIT_RTOL

    out: list[Diagnostic] = []
    if not model.peak_components:
        return out

    predicted = sorted(t for name, row in ticks.items()
                       if name != EXTRA_TICK_KEY for t in row)
    predicted_arr = np.asarray(predicted, dtype=np.float64)
    # "Refined to no intensity" is a statement about what the *fit* did, so it
    # is asked only of an area the fit could move.  A declared peak's area
    # defaults to 0.0 and no preset but ``mccusker_structural`` frees it, so
    # without this every inert declaration would come back carrying a warning
    # about a refinement that never happened.  ``moving_paths`` and not
    # ``free_paths`` for the usual reason: a tie moves a path that is no column
    # of θ (root CLAUDE.md § Invariants).
    moving = set(table.moving_paths)

    for pc in model.peak_components:
        name = pc.label or f"extra_components[{pc.index}]"
        centre = float(values[pc.paths["center"]])
        area_path = pc.paths["area"]
        area = float(values[area_path])

        if area <= 0.0 and area_path not in moving:
            # Declared and inert: area 0 makes the term identically zero and
            # nothing in this fit could change that, so there is neither a
            # refinement to report on nor a degeneracy to warn about.
            continue

        entry = (table.entries[table._paths[area_path]]
                 if area_path in table._paths else None)
        lo = entry.lo if entry is not None else 0.0
        # ``BOUND_HIT_RTOL`` is scipy's own test, imported rather than
        # restated so this and ``BOUND_HIT`` cannot drift apart on what
        # counts as *at* a limit.  The ``<= 0`` clause beside it
        # is not a second test of the same thing: softplus underflows to
        # *exactly* zero well before the internal coordinate reaches any
        # bound, so an area can be off at its identity without ever being
        # "at" a bound in scipy's sense.
        at_zero = (area <= 0.0
                   or (np.isfinite(lo)
                       and abs(area - lo) <= BOUND_HIT_RTOL * max(1.0, abs(lo))))
        if at_zero:
            out.append(Diagnostic(
                level="warning", code="EXTRA_PEAK_NO_INTENSITY",
                message=(
                    f"declared peak {name!r} refined to no intensity "
                    f"(area {area:.3g} at its zero bound) — the data does not "
                    "see it, and its centre is therefore unmeasured rather "
                    "than precisely measured: a peak reaches the pattern only "
                    "through area x profile, so at zero area nothing "
                    "constrains where it sits"),
                where=[pc.paths["center"], area_path],
                suggestion=(
                    "quote neither the centre nor its esd; drop the component, "
                    "or check that its centre bounds bracket the feature you "
                    "meant")))
            continue

        if len(predicted_arr):
            gap = float(np.min(np.abs(predicted_arr - centre)))
            if gap <= LAYER0_MATCH_TOL_DEG:
                out.append(Diagnostic(
                    level="warning", code="EXTRA_PEAK_ON_REFLECTION",
                    message=(
                        f"declared peak {name!r} sits {gap:.3f} deg from a "
                        "position this model already predicts — the two "
                        "describe one peak between them, so the intensity "
                        "split between phase and component is a degeneracy "
                        "rather than a measurement"),
                    where=[pc.paths["center"], pc.paths["area"]],
                    suggestion=(
                        "if the overlap is real (a holder line on a sample "
                        "peak) this is expected and the component is doing its "
                        "job; if the component was a shortcut for a misfitting "
                        "reflection, fix the model instead — check the phase's "
                        "scale, profile and preferred orientation")))
    return out


def _data_support_diagnostics(support, model: CompiledModel) -> list[Diagnostic]:
    """``DATA_SUPPORT_LOW`` and ``PATTERN_UNDERSAMPLED`` (WP-1071).

    The two halves of "does the data support this refinement", from
    McCusker et al. (1999) §9 and §2.  Both **report and gate nothing**: the
    numbers are on :class:`~rietx.schemas.results.DataSupport` either way and
    a fit is never refused for either.

    They differ in what a reader can do about them, which is why they are two
    codes rather than one.  A low ratio is a statement about *this* refinement
    — hold parameters, add restraints, or extend the range, and it improves.
    Undersampling is a statement about the *measurement*, and the only remedy
    is a finer scan: no choice made afterwards recovers an intensity that was
    never collected. Hence the levels — the ratio is graded against the
    paper's own two-part band ("at least three and preferably five") while the
    sampling flag is one-sided, because more than ten steps per FWHM costs
    beam time and nothing else.
    """
    out: list[Diagnostic] = []
    ratio = None if support is None else (
        support.effective_observations_per_parameter)
    if ratio is not None and ratio < OBS_PER_PARAMETER_PREFERRED:
        low = ratio < OBS_PER_PARAMETER_MIN
        out.append(Diagnostic(
            level="warning" if low else "info", code="DATA_SUPPORT_LOW",
            message=(
                f"{ratio:.1f} effective observations per structural parameter "
                f"({support.n_effective_observations:.1f} from "
                f"{support.n_unique_reflections} measured reflections, against "
                f"{support.n_structural_parameters} free) — the guideline is "
                f"at least {OBS_PER_PARAMETER_MIN:g} and preferably "
                f"{OBS_PER_PARAMETER_PREFERRED:g}"),
            suggestion=(
                "the esds are the place this shows: an over-parameterised "
                "refinement reports large ones rather than wrong values. Hold "
                "the least determined parameters (start from the report's "
                "identifiability section), restrain the geometry, or extend "
                "the 2θ range — the reflection count, not the point count, is "
                "what rises"),
        ))

    steps, n_measured = sampling_steps_per_fwhm(
        model.tt, model.y_obs, model.sigma)
    if steps is not None and steps < STEPS_PER_FWHM_MIN:
        out.append(Diagnostic(
            level="warning", code="PATTERN_UNDERSAMPLED",
            message=(
                f"{steps:.1f} steps across the FWHM (median over {n_measured} "
                f"fitted peaks) — below the {STEPS_PER_FWHM_MIN:g} the "
                "guidelines ask for"),
            suggestion=("a data-collection limit, not a refinement one: the "
                        "integrated intensities were not measured finely "
                        "enough and no choice made here recovers them. "
                        "Re-collect at a step size near FWHM/5 if the "
                        "intensities have to be quotable"),
        ))

    # Reported on the fitted channels, because that is the question: a dead
    # cell outside the fit range costs nothing and one inside it outvotes the
    # pattern.  Gated on ``sigma_measured`` rather than on ``model.sigma``,
    # which is already the Poisson fallback by the time it is an array
    # (WP-1029) — and under that fallback the test cannot separate a dead cell
    # from a channel that honestly counted zero.
    if model.sigma_measured:
        for run in dead_channels(model.tt, model.y_obs, model.sigma):
            lo, hi = _dead_interval(run)
            out.append(Diagnostic(
                level="warning", code="PATTERN_DEAD_CHANNELS",
                message=(
                    f"{run.n_channels} channel(s) at "
                    f"{lo:.3f}-{hi:.3f}° measure "
                    f"{run.level_fraction:.2%} of the local background with an "
                    f"esd that fell with them, so each carries about "
                    f"{run.weight_ratio:,.0f}× the weight of a live channel "
                    "there"),
                where=[f"{lo:.3f}-{hi:.3f}"],
                suggestion=(
                    "a dead or masked detector cell, not a feature of the "
                    "specimen: weights are 1/σ², so these channels pull the "
                    "background down to meet them and the symptoms surface "
                    "elsewhere — parameters at their bounds, a background "
                    "driven negative. Exclude the interval "
                    f"({lo:.3f}, {hi:.3f}) and "
                    "refit. Nothing here excludes it for you"),
            ))
    return out


#: mean weighted-squared-residual ratio (the region below the first
#: reflection, over the whole-pattern reduced χ², ``Statistics.chi2``) above
#: which that region is unmodelled rather than merely quiet.  A Layer-0
#: constant beside ``STEPS_PER_FWHM_MIN``/``OBS_PER_PARAMETER_MIN`` above —
#: not part of ``report.schemas.THRESHOLDS_VERSION``, which is the FitReport
#: Layer-2 gates/vocabulary contract and has never moved for a raw
#: ``Diagnostic`` (``PATTERN_UNDERSAMPLED`` did not bump it either).
#:
#: Measured on Ba₂FeSbSe₅ 1.5 K (Maier, Gaultois et al. 2021, PRB 103,
#: 054115; G4.1, λ = 2.426 Å, 0.1° steps): with the first reflection pinned
#: at its cited position (9.4°, magnetic). A compiled model cannot place a
#: magnetic phase yet — that lands with WP-1327
#: (docs/wp/1327-magnetic-structure.md), still unscheduled — so today the
#: compiled model's own first tick is always its first *nuclear* one, and
#: this constant is exercised through that path instead: a 4° start's
#: beam/air-scatter tail reads at ≈2.5-3× (χ²/pt ≈30 against a
#: whole-pattern χ²_red ≈12, both cited); a 6° start, which excludes the
#: tail, is silent.  3.0 sits just above the 4° reading with headroom below
#: the 6° one.
LOW_ANGLE_UNMODELLED_RATIO = 3.0

#: fewest channels the region below the first reflection must hold before
#: the ratio above is trusted.  Below it there is nothing to measure a level
#: from — a handful of noisy points can cross any ratio by chance, and a
#: pattern whose first reflection sits at or near the low edge should read
#: as "no region" rather than as a level computed on three points.
LOW_ANGLE_MIN_CHANNELS = 10


def _first_reflection_fwhm(model: CompiledModel, values: dict[str, float],
                           ticks: dict[str, list[float]],
                           support: dict[str, list[float]] | None = None
                           ) -> tuple[float, float] | None:
    """``(2θ, FWHM)`` of the lowest-angle reflection the data can see, over
    every phase, emission line and declared peak, or ``None`` when there is
    none (an empty structure list, or no tick carrying intensity).

    **Which ticks count** (WP-1458): the images of a reflection whose
    strongest modelled point, on any emission line, reaches
    :data:`~rietx.model.forward.PHASE_SUPPORT_SIGMA` σ of the noise — read
    off ``support``, which :func:`_build_result` builds from
    :meth:`CompiledModel.reflection_support` and
    :meth:`CompiledModel.extra_peak_support` and pairs with ``ticks`` by
    index.  That is :meth:`CompiledModel.phase_support`'s test one rank down,
    per reflection rather than per phase, because a *supported* row can still
    carry empty ticks below its first real line (a declared peak at zero
    area, a superstructure reflection whose |F| is zero), and because a
    phase's summed curve can clear the threshold where none of its
    reflections does (issue #436's large-cell dummy: 1.23σ summed, no
    reflection above 0.62σ).  A tick with nothing behind it reaches nothing;
    before this rule one below the data moved the boundary there and silenced
    the diagnostic.

    **Per reflection, not per image**: the unit is the hkl, as ``tick_hkl``
    has it, so a Kα2 or λ/2 image of a reflection the data sees keeps its
    place however weak the image is on its own.  Judged image by image, the
    λ/2 (111) of the published BT-1 Cu(311) Nd₂Ru₂O₇ fit (0.095σ, beside its
    primary's 2.86σ) was dropped, the region grew from 36 to 185 channels,
    and a warning firing at 5.92× today fell to 2.66×.

    ``support=None`` makes no claim and counts every tick by position alone.

    The FWHM is the **instrumental** resolution function alone (Caglioti
    U/V/W + the Lorentzian X/Y, no per-phase size/strain broadening): this
    is a boundary heuristic for where the *background* stops being trusted,
    not a per-reflection width report, and the two sample terms both vanish
    or are smallest at the lowest angle in the pattern anyway (strain ∝ tanθ,
    size ∝ 1/cosθ). ``ticks`` is the positions dict :func:`_build_result`
    already built (zero-shift included), reused rather than re-derived so the
    two cannot disagree about where the first reflection sits.
    """
    if support is None:
        all_ticks = [t for row in ticks.values() for t in row]
    else:
        all_ticks = [t for name, row in ticks.items()
                     for t, s in zip(row, support[name], strict=True)
                     if s >= PHASE_SUPPORT_SIGMA]
    if not all_ticks:
        return None
    first_tick = min(all_ticks)
    theta = np.array([first_tick / 2.0])
    gam_g = gaussian_fwhm(theta, values["instrument.profile.u"],
                          values["instrument.profile.v"],
                          values["instrument.profile.w"])
    gam_l = lorentzian_fwhm(theta, values["instrument.profile.x"],
                            values["instrument.profile.y"])
    w1, w2 = model._peak_widths(gam_g, gam_l)
    fwhm = float(np.asarray(model.peak_fwhm(w1, w2))[0])
    return first_tick, fwhm


def _low_angle_diagnostics(model: CompiledModel, values: dict[str, float],
                           y_calc, stats, ticks: dict[str, list[float]],
                           support: dict[str, list[float]] | None = None
                           ) -> list[Diagnostic]:
    """``LOW_ANGLE_UNMODELLED``: the channels below the first reflection carry
    more residual than the fit's own whole-pattern χ²_red would predict.

    Nothing else in the package tests this specifically. The nearest
    relative, ``PatternDiagnostics.air_scatter_gain``
    (``background/diagnostics.py``), is a nested cubic-vs-cubic+1/x test on
    the background *envelope* over the **whole** fitted range — so a tail a
    few tens of channels wide out of several hundred barely moves it (measured
    on Ba₂FeSbSe₅ 1.5 K: 0.019, against the ``AIR_SCATTER_TRIGGER`` of 0.3;
    19 tail channels out of 779 carry 0.3 % of the whole-range RSS the nested
    fit compares). This diagnostic instead reads the fit's own residual, and
    only over the region no reflection — of any phase, any emission line,
    any declared peak — can reach: ``[two_theta_min, first_tick − 2·FWHM)``,
    so a peak's own low-angle flank is never counted as unmodelled.
    ``first_tick`` is the lowest tick carrying calculated intensity the data
    can see (``support``; :func:`_first_reflection_fwhm` states the rule), so
    an empty tick below the first real line does not move the boundary.

    Silent (``[]``) rather than firing, under either of two conditions:

    * fewer than :data:`LOW_ANGLE_MIN_CHANNELS` channels in the region — no
      reflections in the model at all, or the first one sits at or near the
      low edge, so there is nothing to measure a level from;
    * the region's mean weighted-squared residual is not more than
      :data:`LOW_ANGLE_UNMODELLED_RATIO` times the whole-pattern reduced χ².

    The region's own mean is not d.o.f.-corrected — it has no free
    parameters of its own to subtract — while ``stats.chi2`` is divided by
    ``n − n_free`` over the whole pattern. The comparison is deliberately
    against that d.o.f.-corrected whole-pattern figure rather than a
    like-for-like plain mean, which makes the ratio slightly conservative:
    ``n_free`` only enlarges the denominator, so the region has to clear a
    slightly higher bar than a straight ratio of means would set, and the
    diagnostic fires marginally less often as a result.

    The message reports the ratio and **does not choose** between its two
    remedies — raising the pattern's lower limit, or adding the background's
    air-scatter term — because they answer different causes (the region is
    genuinely outside the beam, versus the background model is locally
    wrong) and only whoever is looking at the pattern can tell which.
    """
    first = _first_reflection_fwhm(model, values, ticks, support)
    if first is None:
        return []
    first_tick, fwhm = first
    boundary = first_tick - 2.0 * fwhm

    mask = model.tt < boundary
    n = int(mask.sum())
    if n < LOW_ANGLE_MIN_CHANNELS:
        return []

    diff = model.y_obs[mask] - np.asarray(y_calc)[mask]
    sigma = model.sigma[mask]
    weighted = diff / sigma
    local_stat = float(np.mean(weighted ** 2))
    chi2_red = stats.chi2
    if not chi2_red > 0.0:
        return []
    ratio = local_stat / chi2_red
    if ratio <= LOW_ANGLE_UNMODELLED_RATIO:
        return []

    # Where raising the lower limit would stop: the channel just past the
    # highest-angle point still ≥ 2σ, scanning from the low edge up — the
    # region above it is the part already reading as agreement.  If no
    # channel reaches 2σ (the mean is high without any single outlier), the
    # boundary itself is reported, since no sharper angle is evidenced.
    tt_region = model.tt[mask]
    bad = np.flatnonzero(np.abs(weighted) >= 2.0)
    if len(bad):
        past = int(bad[-1]) + 1
        suggested = float(tt_region[past]) if past < len(tt_region) else boundary
    else:
        suggested = boundary

    return [Diagnostic(
        level="warning", code="LOW_ANGLE_UNMODELLED",
        message=(
            f"{n} channels below the first reflection ({first_tick:.2f}° "
            f"− 2×FWHM = {boundary:.2f}°) carry a mean "
            f"weighted-squared residual {local_stat:.2f}, {ratio:.2f}× "
            f"the whole-pattern reduced χ² ({chi2_red:.2f}) — "
            "there are no reflections in this region to explain it"),
        suggestion=(
            f"either raise the pattern's lower limit to {suggested:.2f}° "
            "(the channel where the residual falls under 2σ) or add "
            "the background's air-scatter term; this diagnostic does not "
            "choose between them"),
        value=ratio,
    )]


def _qpa_unavailable_diagnostics(structure: Structure,
                                 values: dict[str, float]) -> list[Diagnostic]:
    """``QPA_UNAVAILABLE``: the scales cannot form weight fractions.

    W_p ∝ S_p·(ZMV)_p renormalised, so a non-positive Σ S·ZMV has no
    renormalisation to do.  This is reported rather than raised because QPA is
    one field of a result, and raising from inside the result builder took a
    whole 157-pattern sequential run down with one bad pattern (WP-1028 §(f)).
    """
    dead = [f"phases.{ip}.scale" for ip in range(len(structure.phases))
            if values.get(f"phases.{ip}.scale", 0.0) <= 0.0]
    return [Diagnostic(
        level="warning", code="QPA_UNAVAILABLE",
        where=dead,
        message=("the refined phase scales give a non-positive Σ S·ZMV, so "
                 "weight fractions cannot be formed"
                 + (f" ({', '.join(dead)} at or below zero)" if dead else "")),
        suggestion="this is a statement about the fit, not the specimen: a "
                   "phase scale at zero means that phase contributed nothing, "
                   "so check whether it belongs in the model, whether its "
                   "starting cell put its peaks where the data has none, and "
                   "the other diagnostics from this run",
    )]


def _max_iter_diagnostics(stage_results: list[StageResult]) -> list[Diagnostic]:
    """``STAGE_MAX_ITER``: a stage stopped on its budget, not on convergence.

    ``StageResult.status`` has carried ``"max_iter"`` all along, but folded
    into a per-stage record nobody reads in a batch run — while the *result's*
    status can still say ``converged`` because it is the last stage's.  The
    measured cost of leaving it silent: three identical NaCl/Li₂CO₃ mixtures,
    same models and parameter counts, ran 39 s, 858 s and 2838 s — a 73×
    spread with no difference in the answer (WP-1028 §(d)).

    Naming the stage is still the fix, because the stages that stall are the
    degenerate groups the agent skill §3 enumerates rather than merely slow
    ones.  What *has* changed since (WP-1109) is what the cap means: it was
    ``max_iter × n_par``, a multiplier that priced a finite-difference
    Jacobian nothing builds any more, so at 42 free parameters a
    ``max_iter=100`` stage could spend ~4200 evaluations before saying so.  It
    is now ``max_iter ×`` :data:`~rietx.optimize.least_squares.NFEV_PER_ITERATION`,
    sized from the measured worst-case rejection rate, so a stage that stalls
    reports it roughly 30x sooner with its answer unchanged.
    """
    hit = [s.name for s in stage_results if s.status == "max_iter"]
    if not hit:
        return []
    return [Diagnostic(
        level="warning", code="STAGE_MAX_ITER",
        message=("stage " + ", ".join(repr(n) for n in hit)
                 + (" stopped on its iteration budget rather than converging"
                    if len(hit) == 1 else
                    " stopped on their iteration budgets rather than converging")),
        where=[],
        suggestion="the parameters freed there are probably degenerate "
                   "(the agent skill §3) rather than merely slow: free fewer "
                   "at once, or check the diagnostics for a correlation or "
                   "bound hit in the same stage — raising max_iter buys "
                   "solver evaluations, not a different minimum",
    )]


def _held_by_phase(stage_results: list[StageResult], n_phases: int
                   ) -> tuple[list[set[str]], list[list[str]]]:
    """Per phase: the paths held anywhere in the run, and the stages that held.

    Read off the stage records rather than tracked separately, so the message
    and the record cannot disagree about what happened (WP-1301).  Stage names
    come out in the order the stages ran, which is how a reader looks for them
    in the plan.

    The index is read off the ``phases`` segment rather than off position one,
    because the joint runner's records carry *scoped* paths whenever the
    sharing map makes a structural family per-histogram
    (``hist.0.phases.1.cell.a``), and position one is then the histogram.

    Since WP-1342 a held path need not name a phase at all: the freeze holds
    *columns*, and a caller's ``vars.X`` driving a cell is one.  So the phase is
    looked for in what the column moved (``StageResult.held_reach``) as well as
    in its own name.

    **Every phase the column reached, not the first one.**  A column is held
    only while *every* phase it moves is invisible (:func:`_only_moves`), which
    one driving two **absent** phases satisfies — so such a column belongs in
    both buckets, and stopping at the first name that parses reported it under
    the lower index alone.  The second phase then had nothing held, nothing
    free under its own prefix, and so no ``PHASE_UNCONSTRAINED`` at all
    (measured on a three-phase fixture with one ``vars.A`` driving both absent
    cells: one finding, for phase 1).  The buckets are sets, so a path whose
    name and whose reach both point at one phase still lands once.

    **What goes in the bucket is the column, never its reach.**  The bucket
    becomes ``PHASE_UNCONSTRAINED``'s ``where``, which ``sequential`` keys its
    persistent-finding aggregation on — so adding the derived ties would turn
    one finding about a phase into one per tied cell parameter (measured: 3 on
    the ramp's cubic CaF₂, for a single absent phase). The account of what else
    a hold stopped is ``held_reach`` itself, on the record.
    """
    paths: list[set[str]] = [set() for _ in range(n_phases)]
    stages: list[dict[str, None]] = [{} for _ in range(n_phases)]
    for sr in stage_results:
        for path in sr.held:
            for name in (path, *sr.held_reach.get(path, ())):
                parts = name.split(".")
                try:
                    ip = int(parts[parts.index("phases") + 1])
                except (IndexError, ValueError):
                    continue
                if 0 <= ip < n_phases:
                    paths[ip].add(path)
                    stages[ip][sr.name] = None
    return paths, [list(s) for s in stages]


def _phase_support_diagnostics(support_by_phase: np.ndarray,
                               line_counts: np.ndarray,
                               tt_range: tuple[float, float],
                               free_paths: list[str],
                               structure: Structure,
                               stage_results: list[StageResult] | None = None,
                               ) -> list[Diagnostic]:
    """``PHASE_UNCONSTRAINED`` — a phase the data cannot see, and what was done.

    Every structural parameter of a phase reaches the pattern only through
    ``scale × |F|² × profile``.  So when a phase's scale falls to its floor,
    the whole phase becomes a **flat direction**: its Jacobian columns go to
    the noise floor, the fit still reports ``converged`` because those
    parameters genuinely do not affect Rwp, and whatever the optimiser leaves
    in them is not a measurement.  Two agents on a real 68-pattern series drove
    such a phase's cell to a ≈ 39 293 Å and a ≈ 40 000 Å, and the run died
    hundreds of stages later inside ``generate_reflections`` (WP-1110).

    Measured on the **modelled contribution**, not on ``scale``, for the reason
    :data:`ROUGHNESS_MIN_DEPRESSION` is measured on the depression: scale is
    degenerate with |F|², the profile widths and the line weights, so a small
    scale is not the same statement as a small contribution and only one of
    them is about what the data can see.

    ``params.vector.cell_window`` bounds the *symptom* — it stops the cell
    running away — but a windowed cell re-anchors on every stage, so it walks
    quietly instead of loudly and ``BOUND_HIT`` need never fire.  This names
    the cause, which is the half a caller can act on.

    Since WP-1301 the flat direction is **held** rather than walked, so this
    also reports what the run did about it: which parameters were held and in
    which stages, and — the limit case that was silent altogether — that no
    line of the phase lies in the fitted range at all.  The code and its
    meaning do not move: it fires when the phase is one the data cannot see at
    the end of the run, which is what an agent has been told to read it as
    (the agent skill's "do not quote anything about this phase" row).  A phase
    that was held and then *released* is one the fit could see after all, so it
    fires nothing here and says so in ``StageResult.released``: a warning on a
    healthy phase teaches a consumer to ignore the code.

    Fires for a single-phase model only when there is something to say — a hold
    that acted, or a phase with no line in range.  A lone phase under the noise
    with nothing held is MODEL_FAR_FROM_DATA's statement, not this one, and
    that is what it was before this diagnostic said anything about holds.
    """
    n_phases = len(support_by_phase)
    held_paths, held_stages = _held_by_phase(stage_results or [], n_phases)
    out: list[Diagnostic] = []
    for ip in range(n_phases):
        prefix = f"phases.{ip}."
        # the scale is what makes a phase visible, so a free scale is how a
        # phase legitimately climbs out of the noise — it is the *other* free
        # parameters that are being refined against nothing
        unconstrained = sorted(p for p in free_paths
                               if p.startswith(prefix) and p != f"{prefix}scale")
        held = held_paths[ip]
        no_lines = int(line_counts[ip]) == 0
        if not unconstrained and not held and not no_lines:
            continue
        support = float(support_by_phase[ip])
        if support >= PHASE_SUPPORT_SIGMA:
            continue
        if n_phases < 2 and not held and not no_lines:
            continue
        name = structure.phases[ip].name
        if no_lines:
            cause = (f"no reflection of phase {ip} ({name}) lies in the fitted "
                     f"range {tt_range[0]:.4g}-{tt_range[1]:.4g}°, so nothing "
                     f"about it is measurable here")
        else:
            cause = (f"phase {ip} ({name}) contributes at most {support:.2g}σ of "
                     f"the observation noise anywhere in the fitted range, so "
                     f"the data cannot distinguish it from absent")
        clauses = []
        if held:
            stages = held_stages[ip]
            clauses.append(f"its {len(held)} structural parameter"
                           f"{'' if len(held) == 1 else 's'} "
                           f"{'was' if len(held) == 1 else 'were'} held for "
                           f"stage{'' if len(stages) == 1 else 's'} "
                           f"{', '.join(stages)}")
        if unconstrained:
            clauses.append(f"{len(unconstrained)} of its parameters "
                           f"{'was' if len(unconstrained) == 1 else 'were'} "
                           f"refined against it")
        message = cause if not clauses else f"{cause} — {'; and '.join(clauses)}"
        out.append(Diagnostic(
            level="warning", code="PHASE_UNCONSTRAINED",
            # the held paths as well as the still-free ones: a held value is
            # the one the caller handed in rather than a measurement, and
            # reading it as a result is the same mistake either way
            where=sorted(set(unconstrained) | set(held)),
            value=support,
            message=message,
            suggestion=(
                "this specimen or this fitted range cannot measure the phase: "
                "either it is not present and belongs out of the model, or the "
                "range must cover a reflection of it"
                if no_lines else
                "treat those values as unmeasured, not as results: a held one "
                "is what you handed in, a refined one moved in a flat "
                "direction. Either the phase is not in this specimen and "
                "belongs out of the model, or its scale is stuck at its floor "
                "and needs seeding before anything else of it is freed"),
        ))
    return out


#: Sample strain (as a Lorentzian **FWHM** coefficient in deg 2θ, i.e. in
#: ``lor_strain``'s own units) above which a refinement is flagged for a reader
#: to adjudicate.  Not a bound — nothing is constrained by this number, and the
#: fit that trips it is complete and may well be right.
#:
#: **Set from the corpus, not from taste.**  Surveyed across the 606 solved
#: TOPAS ``.inp`` files of our archive (1213 strain records in 346 files;
#: `strain_L` and the `Microstrain()` macro that wraps it, which is the same
#: FWHM·tanθ convention as ``lor_strain``): median 0.076, p75 0.16, p90 0.68,
#: p99 1.21, and the explicit ceilings those authors wrote by hand cluster at
#: 0.1, 0.2, 0.3, 0.7, 1.0 and 1.5.  1.5 is the top of that band and just over
#: the p99.
#:
#: What actually chose it is the **gap**, which is a more robust authority than
#: a percentile in a corpus this heavily templated (a single calibration block
#: copy-pasted into 78 files inflates any quantile).  Above 1.5 the corpus holds
#: 8 of 1213 records (0.66 %) in 5 independent contexts, and every one was
#: inspected: five are pegged at an author's own ``max 5`` ceiling and carry
#: TOPAS's ``_LIMIT_MAX_5`` divergence annotation, one belongs to a phase named
#: "pixie_dust" — an unindexed placeholder mid structure-solution — and the rest
#: are a minor secondary phase absorbing an unmodelled peak shape.  So this
#: threshold separates *fits* from *divergence signatures* in the corpus we
#: have, rather than separating materials, and the nanocrystalline and heavily
#: defective specimens that legitimately live in the 0.4–1.5 tail (dozens of
#: independent files) stay below it and stay silent.
#:
#: ``gauss_strain`` is a variance in deg², so it is compared against the square
#: of this width — one number, both terms, the same reasoning
#: :func:`~rietx.params.vector.strain_cap_hi` uses for the bound.
STRAIN_FLAG_WIDTH = 1.5


def _strain_flag_diagnostics(model: CompiledModel, values: dict[str, float],
                             structure: Structure) -> list[Diagnostic]:
    """``STRAIN_UNUSUALLY_LARGE`` — a strain past what solved refinements use.

    **The upper of two tiers, and the two do different jobs.**  One tier down,
    :func:`~rietx.params.vector.strain_cap` is a solver bound derived from the
    pattern's own 2θ extent; it protects the *numerics*, is not a judgement
    about the specimen, and reports itself as ``BOUND_HIT`` on the path it
    holds.  This tier protects the *interpretation*: it says a number is
    surprising, which only a reader can settle.  Collapsing them into one
    threshold would either flag honest broad-peak fits or permit the 1.1e5 that
    :data:`~rietx.params.vector.strain_cap`'s docstring measures — the corpus
    ceiling and the numerical fence are two orders of magnitude apart, and each
    is wrong in the other's job.

    So the register is deliberately *not* the Stephens cone's "not quotable".
    A fit here is finished, and its strain is physically possible; what is
    unusual is how far out in the corpus it sits.  It does not gate anything
    ("report, never refuse"), and it is per-pattern, which is where a batch
    caller most needs it — a series of 248 patterns cannot be read as 248
    reports, and this is the kind of flag issue #141's batch verb would
    aggregate.

    ``microstrain`` blocks are deliberately **not** covered; see the module's
    ``STRAIN_FLAG_WIDTH`` note and the PR that added it.  A declared Stephens
    block *locks* ``lor_strain`` — its isotropic direction is identically that
    column — so this cannot contradict it: a locked term keeps whatever value
    it was given, and the block's own Λ(hkl) is not an entry with a width.
    """
    out: list[Diagnostic] = []
    for ip in range(len(model.phases)):
        name = structure.phases[ip].name
        for term, width in (
                ("lor_strain", values.get(f"phases.{ip}.lor_strain")),
                ("gauss_strain", _sqrt_or_none(values.get(f"phases.{ip}.gauss_strain")))):
            if width is None or not width > STRAIN_FLAG_WIDTH:
                continue
            path = f"phases.{ip}.{term}"
            out.append(Diagnostic(
                level="warning", code="STRAIN_UNUSUALLY_LARGE",
                where=[path], value=float(width),
                message=(f"phase {ip} ({name}) refined {term} to a strain "
                         f"broadening of {width:.4g} deg (FWHM coefficient of "
                         f"tanθ), {width / STRAIN_FLAG_WIDTH:.0f}× the "
                         f"{STRAIN_FLAG_WIDTH} that solved refinements stay "
                         f"under — of 1213 strain records in our archive of 606 "
                         f"TOPAS refinements, 8 sit above it and every one is a "
                         f"divergence signature rather than a material"),
                suggestion="physically possible, so this is a number to check "
                           "rather than a failure: confirm the broad lines are "
                           "really this phase's and not an unmodelled peak "
                           "shape, an amorphous component or a second phase it "
                           "is absorbing, and check whether BOUND_HIT fired on "
                           "the same path — at the cap the width is held by the "
                           "fitted range and is not a measurement. If the "
                           "specimen really is this defective, declare the "
                           "bound you mean (a finite Parameter.max outranks "
                           "both tiers and silences them)",
            ))
    return out


def _sqrt_or_none(variance: float | None) -> float | None:
    """A Gaussian **variance** (deg²) as the width it contributes (deg).

    ``gauss_strain`` multiplies tan²θ, so its square root is the quantity
    comparable with ``lor_strain`` and with the corpus's ``strain_G`` — the
    conversion that lets :data:`STRAIN_FLAG_WIDTH` be one number.
    """
    if variance is None or not variance > 0.0:
        return None
    return math.sqrt(float(variance))


#: Crystallite size (Å) below which a refinement is flagged for a reader to
#: adjudicate — the size twin of :data:`STRAIN_FLAG_WIDTH`, and like it a flag
#: that **bounds nothing**.  5 nm.
#:
#: **Set from the corpus and from intent.**  A survey of the 606 solved TOPAS
#: ``.inp`` of our archive finds 317 refined ``CS_L`` (Lorentzian crystallite
#: size, nm — the dominant idiom; ``CS_G`` and ``LVol`` are a handful) whose
#: smallest *well-determined* value is ≈ 33 nm (a rutile size–strain fit); every
#: refined size below ~2 nm is a divergence or placeholder signature — the two
#: at 0.69 and 1.19 nm are Si and a minor Ge phase in a folder named *To
#: Rietveld or not to Rietveld*, and the 18 nm one is a phase named
#: ``pixie_dust``.  So the corpus has a clean gap: real fits floor near 33 nm,
#: artefacts sit below ~2 nm, and nothing legitimate lives between.
#:
#: 5 nm is placed inside that gap, above the 2 nm hard floor
#: (:data:`~rietx.params.vector.SIZE_CAP_MIN_SIZE_A`) and well below the
#: smallest real fit.  It is deliberately *not* pushed up towards 33 nm: a real
#: nanocrystalline specimen of 5–30 nm is routine even though this particular
#: archive of bulk inorganics happens not to contain one, and a flag that fired
#: on it would be noise.  So this says only "smaller than a runaway fence, a
#: number to look at", which is the whole job of the flag tier — the intent
#: Michael set is *prevent runaways, do not legislate physics*.
#:
#: ``gauss_size`` is a variance, so the size is read from its square root, the
#: same conversion :func:`~rietx.params.vector.size_cap_hi` uses for the bound.
SIZE_FLAG_SIZE_A = 50.0


def _size_flag_diagnostics(model: CompiledModel, values: dict[str, float],
                           structure: Structure) -> list[Diagnostic]:
    """``SIZE_UNUSUALLY_SMALL`` — a crystallite past what solved refinements use.

    The size twin of :func:`_strain_flag_diagnostics`, and the two do the same
    two-tier job.  One tier down, :func:`~rietx.params.vector.size_cap` is a
    solver bound (a 2 nm floor on the crystallite, per wavelength); it protects
    the *numerics* and reports itself as ``BOUND_HIT``.  This tier protects the
    *interpretation*: a refined size below :data:`SIZE_FLAG_SIZE_A` is
    physically possible — real nanocrystals reach a few nm — so the fit is
    finished and may be right, but it sits below the archive of solved
    refinements and is worth a look.  It gates nothing ("report, never refuse")
    and is per-pattern, which is where a batch caller needs it.

    The size is read from the **sample** coefficient alone (``lor_size``, or
    ``sqrt(gauss_size)``), not the instrument ⊕ sample total: the question is
    what crystallite *this phase's* refined broadening implies, and a runaway is
    that coefficient ballooning.  Reported in nm, the transferable unit, because
    a coefficient in deg is not comparable between instruments and a size is
    (:mod:`rietx.model.profiles.caglioti`); the apparent size is an order-of-
    magnitude statement (Scherrer K moves it ~10–20 %), which is exactly the
    resolution a "this is suspiciously small" flag needs.

    ``microstrain`` (Stephens) blocks do not touch ``lor_size``, so unlike the
    strain flag there is no locked-column interaction to guard here.

    λ comes from :func:`~rietx.optimize.least_squares._longest_line_wavelength`,
    the same selector the tier-1 bound reads — one authority for "which line",
    so the two tiers cannot come to attribute a coefficient to different
    wavelengths.  A source stating none returns no diagnostic, which is where
    this tier's empty state differs from the bound's; that function's docstring
    is where the difference is argued.
    """
    lam = _longest_line_wavelength(model)
    if lam is None:
        return []
    out: list[Diagnostic] = []
    floor_nm = SIZE_FLAG_SIZE_A / 10.0
    for ip in range(len(model.phases)):
        name = structure.phases[ip].name
        for term, coeff in (
                ("lor_size", values.get(f"phases.{ip}.lor_size")),
                ("gauss_size", _sqrt_or_none(values.get(f"phases.{ip}.gauss_size")))):
            if coeff is None or not coeff > 0.0:
                continue
            size_a = apparent_size_from_size_coefficient(coeff, lam, SCHERRER_K)
            if not size_a < SIZE_FLAG_SIZE_A:
                continue
            size_nm = size_a / 10.0
            path = f"phases.{ip}.{term}"
            out.append(Diagnostic(
                level="warning", code="SIZE_UNUSUALLY_SMALL",
                where=[path], value=float(size_nm),
                message=(f"phase {ip} ({name}) refined {term} to an apparent "
                         f"crystallite size of {size_nm:.3g} nm "
                         f"(Scherrer K={SCHERRER_K}, λ={lam:.4g} Å), below the "
                         f"{floor_nm:.0f} nm that solved refinements stay above "
                         f"— of 606 TOPAS refinements in our archive the "
                         f"smallest well-determined crystallite is ≈ 33 nm, and "
                         f"every refined size below ~2 nm is a divergence or "
                         f"placeholder signature rather than a material"),
                suggestion="physically possible — real nanocrystals reach a few "
                           "nm — so this is a number to check rather than a "
                           "failure: confirm the broad lines are really size "
                           "broadening and not an unmodelled peak shape, strain, "
                           "an amorphous component or a second phase it is "
                           "absorbing, and check whether BOUND_HIT fired on the "
                           "same path — at the cap the width is held at the 2 nm "
                           "floor and is not a measurement. If the specimen "
                           "really is this small, declare the bound you mean (a "
                           "finite Parameter.max outranks both tiers and "
                           "silences them)",
            ))
    return out


#: below this modelled depression at the lowest fitted angle, a refined
#: roughness correction is doing nothing the fit could have noticed.  Chosen
#: against the counting statistics it competes with: 1 % of the strongest
#: low-angle peak is at or under the noise of a typical lab scan, so a
#: "correction" that small is a number the data did not constrain.
ROUGHNESS_MIN_DEPRESSION = 0.01


def _roughness_regime_diagnostics(model: CompiledModel,
                                  values: dict[str, float]) -> list[Diagnostic]:
    """Fences on where the roughness models are meaningful (WP-0502).

    Two distinct failures, both invisible in Rwp:

    ``ROUGHNESS_UNCONSTRAINED`` — the refined correction barely departs from
    1.0 anywhere in the fitted range, so its value is arbitrary.  This is
    measured on the *modelled depression*, not on the parameters, because the
    Suortti model reaches the identity from **both** ends (b → 0 and b → ∞ —
    see :class:`~rietx.schemas.instrument.RoughnessSuortti`); a test on ``b``
    alone would catch only one of the two dead branches.  It also fires for the
    legitimate case of data that simply starts too high in 2θ to see roughness.

    ``ROUGHNESS_OUTSIDE_REGIME`` — Pitschke only, and taken from that paper's
    own Eq (18): the derivation holds for sinθ ≥ τ.  Between τ and 2τ the
    depression turns back over, and below τ the "correction" *amplifies*
    intensity.  Reported rather than clamped, because clamping would put a kink
    in the residual (the frozen-per-stage smoothness invariant).
    """
    if model.roughness is None or not len(model.tt):
        return []
    import numpy as np

    base = "instrument.geometry.surface_roughness"
    # Evaluated at the **reflection** positions, not over the 2θ grid.  Real
    # data forced this (WP-0502): the IUCr round-robin patterns start at 5° 2θ
    # but their first reflection is at 25-32°, and a grid-based fence happily
    # reported a 27 % depression that no modelled peak ever experienced.
    # Roughness is constrained by low-angle reflections, so that is where it
    # has to be judged.
    positions = np.concatenate(
        [np.asarray(pos) for ip in range(len(model.phases))
         for pos, *_ in [model.phase_peaks(ip, values)[0]]]) \
        if model.phases else np.empty(0)
    positions = positions[np.isfinite(positions)]
    positions = positions[(positions >= model.tt_min) & (positions <= model.tt_max)]
    if not positions.size:
        return []
    tt_min = float(np.min(positions))
    factor = np.asarray(model._roughness_factor(positions, values))
    depression = float(1.0 - np.min(factor))

    out: list[Diagnostic] = []
    if model.roughness == "pitschke":
        tau = values[f"{base}.tau"]
        sin_min = float(np.sin(np.radians(0.5 * tt_min)))
        if tau > sin_min:
            out.append(Diagnostic(
                level="warning", code="ROUGHNESS_OUTSIDE_REGIME",
                where=[f"{base}.tau"],
                message=(f"Pitschke roughness tau={tau:.4f} exceeds "
                         f"sin(theta) = {sin_min:.4f} at the lowest fitted "
                         f"angle ({tt_min:.2f}° 2θ): past that point the model "
                         f"amplifies rather than depresses intensity"),
                suggestion="restrict the fit to 2θ above "
                           f"{2 * np.degrees(np.arcsin(min(tau, 1.0))):.1f}°, or "
                           "switch to kind='suortti', which is bounded ≤ 1 "
                           "everywhere (Pitschke et al. 1993 Eq 18)",
            ))
        elif tau > 0.5 * sin_min:
            out.append(Diagnostic(
                level="info", code="ROUGHNESS_OUTSIDE_REGIME",
                where=[f"{base}.tau"],
                message=(f"Pitschke roughness is past its turnover at the low "
                         f"end of the fit (tau={tau:.4f} vs sin(theta)="
                         f"{sin_min:.4f} at {tt_min:.2f}° 2θ): the depression "
                         f"stops deepening there"),
                suggestion="the model is empirical rather than geometric in "
                           "this range (the paper says so); treat tau as a "
                           "fitting parameter, not a measured roughness",
            ))

    if depression < ROUGHNESS_MIN_DEPRESSION:
        out.append(Diagnostic(
            level="warning", code="ROUGHNESS_UNCONSTRAINED",
            where=[f"{base}.{n}" for n in ("a", "b", "c", "tau")
                   if f"{base}.{n}" in values],
            message=(f"the refined surface roughness depresses intensity by at "
                     f"most {depression:.2%} at any modelled reflection "
                     f"(lowest at {tt_min:.2f}° 2θ) — the data cannot see it"),
            suggestion="drop the roughness block, or extend the measurement to "
                       "lower 2θ where the depression has a lever arm; note "
                       "the Suortti model reaches the identity from both ends, "
                       "so a large b is as inert as a zero one",
        ))
    return out


def _restraint_where(row, structure: Structure) -> list[str]:
    if row.path is not None:
        return [row.path]
    if row.phase_index is None or row.atoms is None:
        return []
    phase = structure.phases[row.phase_index]
    return [f"{phase.name} {phase.atoms[j].label}" for j in row.atoms]


def _pawley_locate(pb, gi: int) -> tuple[int, int]:
    """Map a flat intensity index to (phase index, in-phase reflection index)."""
    for ip, (a, b) in enumerate(pb.phase_slices):
        if a <= gi < b:
            return ip, gi - a
    raise IndexError(gi)


def replay(tree: RefinementTree, node_id: str, data: PatternData) -> RefinementResult:
    """Recompute the curves and statistics of a recorded node.

    The model is compiled fresh at the node's own parameter values, so the
    statistics returned here can differ marginally from
    ``node.metrics.statistics``, which the optimiser measured on a model
    frozen at the values its stage *started* from.  See :class:`NodeMetrics`.

    Strictly evaluate-only: it never calls ``lebail_update``, which mutates
    the extracted intensities in place — inspecting a checkpoint must not
    change it.
    """
    node = tree[node_id]
    expected = tree.header.data_fingerprint
    if expected:
        actual = fingerprint(data.two_theta, data.intensity)
        if actual != expected:
            raise ValueError(
                f"pattern does not match this history: fingerprint {actual[:8]} "
                f"but the tree was recorded against {expected[:8]}")

    state = node.state
    structure = state.structure.model_copy(deep=True)
    instrument = state.instrument.model_copy(deep=True)
    table = ParameterTable(structure, instrument)
    for name, prm in state.variables.items():
        # ``Refinement._declare_variables`` one rank down, and for its reason:
        # a named variable (WP-1119) has no model field, so a table rebuilt
        # from the structure and instrument alone does not have it — and a tie
        # the node recorded against one would then raise "tie references
        # unknown parameter".  Declared *before* the ties, exactly as
        # ``_prepare_table`` does it.
        table.add_parameter(f"{VAR_PREFIX}{name}", prm.value, vary=prm.vary,
                            lo=prm.min, hi=prm.max, transform=prm.transform)
    table.set_vary(["*"], False)
    for path, spec in state.ties.items():
        # the user constraints the node was recorded under: without them the
        # replayed model has a different parameter count from the one whose
        # statistics this call exists to reproduce (WP-1070)
        table.set_tie(path, AffineTie(
            terms=tuple((p, float(c)) for p, c in spec.terms),
            const=float(spec.const)))
    # and the anchors, for ``_apply_ties``' reason (WP-1432): this table is
    # built from the node's *own* structure, whose coordinates already carry
    # whatever the recorded tie displaced them by.  Un-rebased, replay
    # answered for a model one displacement further on than the node it was
    # asked about — 0.2174 against the recorded 0.2084 — and nothing in the
    # answer said so.
    table.rebase_anchored_dofs(state.ties)
    table.refresh_ties()
    for path in state.free_paths:
        table.set_vary([path], True)

    model = compile_model(structure, instrument, data, mode=state.mode,
                          two_theta_limits=state.two_theta_limits,
                          moving_paths=set(table.moving_paths))
    if state.mode in ("lebail", "pawley"):
        _restore_lebail(state.reflections, model)

    result = _build_result(
        model, table, table.x0(), mode=state.mode,
        status=node.metrics.status or "converged", stage_results=[],
        diagnostics=list(node.diagnostics), structure=structure)
    result.node_id = node.id
    result.tree_id = tree.header.tree_id
    return result


def estimate_mu_r(structure: Structure, instrument: Instrument) -> float | None:
    """Starting µR for a packed capillary, from composition and geometry.

    Combines each phase's linear attenuation coefficient (McMaster tables, via
    :mod:`rietx.crystallography.attenuation`) into a volume-fraction-weighted
    bulk µ, scales it by ``Geometry.packing_fraction`` — voids do not absorb —
    and multiplies by ``Geometry.capillary_radius_mm``.

    Returns ``None`` rather than raising when µ is unavailable (a wavelength
    whose tabulation interval straddles an absorption edge, an element outside
    the compilation, an energy outside 2-120 keV) or when the geometry carries
    no capillary radius.  Use it to *populate* ``Geometry.mu_r``; a refinement
    will do the same thing itself at compile time if ``mu_r`` is left ``None``.

    **X-ray sources only**, and ``None`` on any other — the tables are X-ray
    photoabsorption and neutron attenuation is a different quantity entirely
    (:data:`_NON_XRAY_ABSORPTION_ESTIMATE` has the physics and names the WP).
    Returning a number here would be worse than returning nothing: the caller
    asked for a starting µR and would have no way to tell that it came from
    the wrong radiation.

    µR is not refinable, deliberately — see :mod:`rietx.model.absorption`.
    """
    geom = instrument.geometry
    if geom.kind != "debye_scherrer" or geom.capillary_radius_mm is None:
        return None
    if instrument.source.kind != "xray_cw":
        return None
    table = ParameterTable(structure, instrument)
    mu_r, _ = estimate_capillary_mu_r(
        structure, table.decode(table.x0()),
        instrument.source.primary_wavelength,
        geom.capillary_radius_mm, geom.packing_fraction)
    return mu_r


def refine(data: PatternData, structure: Structure, instrument: Instrument,
           *, mode: Mode = "rietveld", plan: RefinementPlan | str = "mccusker_default",
           two_theta_limits: tuple[float, float] | None = None,
           backend: str = "numpy", solver: str = "trf",
           history: bool | str | Path | RefinementTree = False,
           events=None, cancel=None, telemetry=None,
           label: str | None = None) -> RefinementResult:
    """One-shot functional API: ``refine(data, structure, instrument)``.

    History defaults to *off* here: this call discards the ``Refinement``, so
    an in-memory tree would be unreachable.  Pass a path to keep one.

    ``events``/``cancel``/``telemetry``/``label`` are :meth:`Refinement.fit`'s,
    forwarded — a run this call started is otherwise unwatchable, unstoppable
    and unnamed, and a caller who reached for the one-shot form is the one least
    able to build the object graph that would fix that.  ``label`` matters most
    here for the reason below: the run directory is all that survives the call,
    so a batch written as a loop over ``refine`` is the case with nothing else
    to tell its runs apart.

    Telemetry matters more here than anywhere, for the same reason history
    defaults off: this call discards the ``Refinement``, so **the run directory
    is the only thing that survives it**.  ``history=False`` leaves no tree to
    derive a project from, so the run lands under the working directory unless
    ``telemetry=`` names somewhere else.
    """
    ref = Refinement(structure, instrument, backend=backend, solver=solver,
                     history=history)
    return ref.fit(data, mode=mode, plan=plan, two_theta_limits=two_theta_limits,
                   events=events, cancel=cancel, telemetry=telemetry, label=label)
