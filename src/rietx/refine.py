"""The public refinement API: :class:`Refinement` and :func:`refine`."""

from __future__ import annotations

import dataclasses
import fnmatch
import math
import os
import re
import subprocess
import tomllib
import warnings
from collections.abc import Callable, Iterable, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .io.exporters import ReflectionRow
    from .schemas.fraction import FractionProfile
    from .schemas.interval import ParameterInterval
    from .schemas.results import QuantitativePhaseAnalysis
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
from .crystallography.magnetic.moments import (
    MOMENT_DIRECTION_SUPPORT,
)
from .crystallography.magnetic.moments import (
    MOMENT_DOF_PATH as _MOMENT_DOF,
)
from .crystallography.magnetic.scattering import check_group_is_structure_symmetry
from .crystallography.symmetry import reflection_label, reflection_label_row
from .crystallography.twins import (
    NumberingMoves,
    carry_constraints,
    carry_state_constraints,
    coordinate_snapshot,
    merge_site_twins,
    numbering_moves,
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
    recorded_window_tol,
    window_loss,
)
from .model.geometry import cell_volumes, geometry_table
from .model.microstructure import microstructure_table
from .model.origin import CompiledOrigin, OriginPhaseRows, compile_origin
from .model.profiles.caglioti import (
    SCHERRER_K,
    apparent_size_from_size_coefficient,
    gaussian_fwhm,
    lorentzian_fwhm,
)
from .model.restraints import summarise_restraints
from .model.rows import layout as row_layout
from .optimize import lapack
from .optimize.cancel import RefinementCancelled
from .optimize.least_squares import (
    _SCALE_PATH,
    DEFAULT_SOLVER,
    SOLVERS,
    STATIONARY_ANGLE_STEP,
    _jacobian_for,
    _longest_line_wavelength,
    covariance_estimates,
    rechart_outcome,
    run_least_squares,
    stationary_columns,
)
from .optimize.qpa import (
    LINEAR_ATTENUATION_BY_SOURCE,
    compute_qpa,
    estimate_capillary_mu_r,
    estimate_flat_plate_mu_t,
    microabsorption_diagnostics,
    unmeasured_reason,
)
from .optimize.statistics import (
    OBS_PER_PARAMETER_MIN,
    OBS_PER_PARAMETER_PREFERRED,
    PINV_RCOND,
    berar_lelann_factor,
    compute_statistics,
    data_support,
    structure_r_factors,
)
from .params.multi import _unscoped
from .params.vector import (
    CELL_SAFETY_ANGLE_DEG,
    CELL_SAFETY_FRACTION,
    VAR_PREFIX,
    AffineTie,
    ParameterTable,
    _cell_parameter_name,
    _is_wavelength,
    _tie_text,
    cell_window,
    is_literal_path,
    is_variable_path,
    retired_spelling,
)
from .report.magnetic import (
    magnetic_width_findings,
    moment_angle_stationary_diagnostics,
)
from .report.schemas import (
    MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA,
    THRESHOLDS_VERSION,
    FitReport,
    StageReport,
)
from .schemas.common import Diagnostic, Parameter, Provenance
from .schemas.history import NodeAction, NodeMetrics, RefinementState, ReflectionState
from .schemas.instrument import CAPILLARY_OFFSETS, Instrument
from .schemas.interval import PARAMETER_INTERVAL_LEVEL, PARAMETER_INTERVAL_MAX_REFITS
from .schemas.params import ParameterRow, TieSpec
from .schemas.pattern import PatternData, require_two_theta
from .schemas.plan import (
    CLOSING_WINDOW_TOL,
    check_closing_window_tol,
    check_phase_support_sigma,
)
from .schemas.results import (
    DELIVERABLES,
    AbsorptionCorrection,
    Identifiability,
    PhaseAgreement,
    PhaseTexture,
    Radiation,
    RefinedParameter,
    RefinementResult,
    StageResult,
    _agreement_line,
    _check_deliverable,
    _check_levels,
    _diagnostic_lines,
    _provenance_line,
    _stage_lines,
)
from .schemas.structure import Structure
from .strategy.staged import (
    CLOSING_STAGE_NAME,
    CORRELATION_GUARD,
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


def _source_version(package_dir: Path) -> str | None:
    """``pyproject.version`` of the source tree ``package_dir`` is in, else ``None``.

    ``src/rietx`` sits two levels below the tree's root.  Only that layout and
    a pyproject naming this distribution count, so a wheel install beside
    somebody else's project, or unpacked by ``pip install --target`` into a
    directory of this one's checkout, reads nothing and stays on the metadata.
    """
    if package_dir.parent.name != "src":
        return None
    try:
        text = (package_dir.parent.parent / "pyproject.toml").read_text(encoding="utf-8")
        project = tomllib.loads(text).get("project")
    except (OSError, ValueError):  # TOMLDecodeError and UnicodeDecodeError are both
        return None
    if not isinstance(project, dict) or project.get("name") != DIST_NAME:
        return None
    found = project.get("version")
    return found if isinstance(found, str) else None


#: The ``GIT_*`` variables that say *how* to run git, never *which* repository.
_GIT_ENV_KEEP = frozenset({"GIT_EXEC_PATH", "GIT_SSH", "GIT_SSH_COMMAND"})


def _git_env() -> dict[str, str]:
    """``os.environ`` less every ``GIT_*`` outside :data:`_GIT_ENV_KEEP`.

    setuptools-scm's ``no_git_env`` rule rather than a list of the variables
    known to redirect: ``GIT_OBJECT_DIRECTORY``, ``GIT_NAMESPACE`` or a
    ``GIT_CONFIG_PARAMETERS`` inherited from a parent ``git -c`` point git
    elsewhere as surely as ``GIT_DIR`` does, and a list misses the next one.
    """
    return {key: value for key, value in os.environ.items()
            if not key.startswith("GIT_") or key in _GIT_ENV_KEEP}


def _same_version(source: str, installed: str) -> bool:
    """Whether two version strings name one release, as the metadata spells it.

    The build backend writes the PEP 440 *normal* form (``1.6.0-dev0`` becomes
    ``1.6.0.dev0``), so string equality alone would call a fresh install of a
    non-normal ``pyproject.version`` stale.  ``packaging`` is not a dependency,
    so where it is absent the strings are compared as they stand.
    """
    if source == installed:
        return True
    try:
        from packaging.version import InvalidVersion, Version
    except ImportError:
        return False
    try:
        return str(Version(source)) == str(Version(installed))
    except InvalidVersion:
        return False


def _source_node(root: Path) -> str | None:
    """HEAD of the git work tree rooted at ``root`` as a local label, else ``None``.

    setuptools-scm's ``node-and-date`` node (``g`` + abbreviated hash) with its
    ``dirty-tag`` word appended when a tracked file differs from HEAD (WP-1456
    § The prior art).  The top level must be ``root`` itself: a source tree
    unpacked inside somebody else's repository would otherwise be stamped with
    that repository's commit.  For the same reason git runs under
    :func:`_git_env` (a git hook running the suite exports ``GIT_DIR`` and its
    kin).  ``status`` takes no optional lock, so an import never contends with
    a git command another process is running in the same tree.
    """
    env = _git_env()
    env["GIT_OPTIONAL_LOCKS"] = "0"

    def git(*args: str) -> str:
        proc = subprocess.run(["git", "-C", str(root), *args], env=env,
                              capture_output=True, encoding="utf-8", timeout=10)
        if proc.returncode != 0:
            raise OSError(proc.stderr.strip())
        return proc.stdout.strip()

    try:
        top, head = git("rev-parse", "--show-toplevel", "HEAD").splitlines()
        dirty = git("status", "--porcelain", "--untracked-files=no")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if Path(top).resolve() != root.resolve() or not re.fullmatch(r"[0-9a-f]{40,64}", head):
        return None
    return f"g{head[:12]}" + (".dirty" if dirty else "")


def _resolve_version(package_dir: Path) -> str:
    """The version every result is stamped with: the one authority (WP-1456).

    The installed metadata, unless the package is imported from a source tree
    whose ``pyproject.version`` disagrees with it.  An editable install writes
    its metadata once, at install time, so a version bump without a reinstall
    left 1.4.0 on results of 1.6.0.dev0 code, and on 887 run records, with
    nothing raised.  On disagreement the stamp is the source version plus the
    commit as a PEP 440 local label, or the bare source version when git
    cannot say, and the warning says which.  The commit is read only on that
    path, so a matching install is stamped byte for byte as before.
    """
    try:
        installed = version(DIST_NAME)
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
            RuntimeWarning, stacklevel=3)
        return _DEV_VERSION
    source = _source_version(package_dir)
    if source is None or _same_version(source, installed):
        return installed
    node = _source_node(package_dir.parent.parent)
    stamp = source if node is None else f"{source}{'.' if '+' in source else '+'}{node}"
    warnings.warn(
        f"the installed {DIST_NAME} metadata says {installed!r} but the source "
        f"tree it is imported from says {source!r}: results will be stamped "
        f"{stamp!r}{' (its commit could not be read)' if node is None else ''}.  "
        f'Reinstall (uv pip install -e ".[dev]") to make the two agree.',
        RuntimeWarning, stacklevel=3)
    return stamp


_VERSION = _resolve_version(Path(__file__).resolve().parent)

def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def mode_fixed_path(path: str, mode: Mode) -> bool:
    """Whether ``mode`` force-fixes ``path`` whatever the table says.

    Against an intensity model that partitions or refines the per-hkl
    intensities, these families of parameter cannot be refined at all: the
    structural parameters (there is no |F|² to fit), the phase scale (degenerate
    with those intensities), a texture coefficient, and a magnetic width, whose
    component only a Rietveld draw separates.  ``_run_stage`` drops them from
    the freed set; exported once so :meth:`Refinement.parameters` reports the
    same set rather than a second opinion about it.

    **The emission lines refine in every mode** (WP-2002, 2026-10-20).  Both
    modes keep one intensity per reflection and draw it through every line at
    that line's weight (:meth:`CompiledModel.lebail_update`), so the doublet's
    ratio is a shape the intensities cannot absorb; line 0's weight is the
    one degenerate with them, and it is locked structurally.  Measured on NIST
    SRM 660c: Kα2/Kα1 0.5126 ± 0.0048 Rietveld, 0.5145 ± 0.0036 Pawley,
    0.5224 ± 0.0033 Le Bail, and with the cell held Le Bail refines λ to
    1.540605 ± 3e-6 Å.  Until then ``.source.lines.`` was force-fixed here,
    the wavelength with it, so a Pawley calibration of λ on a standard could
    not run.
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
    # And the magnetic component's own widths (WP-1343): the second frozen
    # family is drawn only in Rietveld, so under an intensity model a free
    # width would be a dead column, as the moment it broadens (``.atoms.``)
    # already is here.
    # A rigid body's origin and rotation (WP-1805) move nothing but its atoms'
    # coordinates, so they are structural parameters too, and so is a
    # distortion-mode amplitude (WP-1419), which writes only coordinates.
    # A texture coefficient (WP-1960) multiplies |F|², which an intensity model
    # does not compute, so its column is dead there: measured on March-Dollase's
    # r, its single-axis sibling, which ended 1.7e-13 from its start.
    return (".atoms." in path or ".rigid_bodies." in path
            or ".distortion_modes." in path
            or (path.startswith("phases.") and path.endswith(".scale"))
            or (path.startswith("phases.") and ".texture." in path)
            or _MAGNETIC_WIDTH_PATH.match(path) is not None)


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
    #: the ``turn_on`` paths naming no entry (WP-1414), riding here
    #: for ``blocked_by_hold``'s reason: decided before the solve, unchanged
    #: by it, and delivered to the two ``StageResult`` call sites this way
    unknown_paths: list[str] = dataclasses.field(default_factory=list)
    #: ``StageResult.seeded`` (WP-1930), riding here for the same reason:
    #: decided before the solve, and unrecoverable after it, when the seeded
    #: row has moved.  ``Stage.seed``'s rows and ``Stage.strain_seed``'s.
    seeded: dict[str, float] = dataclasses.field(default_factory=dict)
    #: one :class:`CellReset`, ``(path, solved_value, start_value)``, for
    #: every free cell parameter :func:`reset_cell_runaway` put back this
    #: stage, after either solve — empty on every stage that never leaves the
    #: safety window, which is every stage measured so far (WP-1110's own
    #: 51-transition survey, WP-1523's 104 fits).
    cell_runaway: list[tuple[str, float, float]] = dataclasses.field(
        default_factory=list)
    #: ``StageResult.cell_reset`` (WP-2002, B8): the paths of
    #: :attr:`cell_runaway` the stage did not hand to the collapse's hold,
    #: decided inside the stage beside ``held``.
    cell_reset: list[str] = dataclasses.field(default_factory=list)
    #: ``StageResult.collapsed`` (WP-2002, B14): the free columns the answer
    #: found unsupported or flat, restored to their stage-start values and
    #: held for the second solve.  A subset of :attr:`held`, decided inside
    #: the stage, where the start-of-stage hold and the collapse are still
    #: two lists.
    collapsed: list[str] = dataclasses.field(default_factory=list)
    #: ``(driver_path, [escaped_dependent_paths])`` per ``vars.*`` column
    #: :func:`_vars_driven_cell_escapes` found driving a cell outside the
    #: safety window this stage — named, never reset (review of #385
    #: finding 1).  Empty on every stage this package's own suite runs
    #: outside this file's own fixture.
    cell_runaway_unresolved: list[tuple[str, list[str]]] = dataclasses.field(
        default_factory=list)
    #: the origin restraint the stage's last solve ran with (WP-1912,
    #: ``model.origin``), for ``ORIGIN_FIXED_ON_POLAR_AXIS``: built from the
    #: free set and the values at the solve's start, neither of which the
    #: table can give back afterwards.  ``None`` where no ``"centroid"``
    #: phase could slide, which is every stage of every other fit.
    origin: CompiledOrigin | None = None
    #: ``StageResult.moment_flat_axes`` and ``.moment_turned`` (#599), decided
    #: inside the stage by :func:`_hold_flat_moments` and the post-solve hold
    moment_flat_axes: dict[str, list[float]] = dataclasses.field(
        default_factory=dict)
    moment_turned: list[str] = dataclasses.field(default_factory=list)
    #: ``StageResult.scale_b_held`` (WP-1534): per phase whose displacement
    #: columns :func:`_hold_scale_b_ridges` held, the separation it measured
    scale_b_held: dict[int, float] = dataclasses.field(default_factory=dict)
    #: ``StageResult.width_twins_held`` (WP-2002): per instrument width column
    #: :func:`_hold_width_twins` held, the specimen twin columns it pairs with
    width_twins_held: dict[str, list[str]] = dataclasses.field(
        default_factory=dict)
    #: each phase's :func:`_answer_significance` at the stage's answer
    #: (WP-1523), written by ``_run_stage`` alone.  Carried so the result's
    #: ``PHASE_UNCONSTRAINED`` reads the number the hold was decided on: a
    #: phase the support hold still holds keeps that reading, taken with its
    #: held columns free, which the result's own covariance cannot do.  A
    #: phase that refined is read off the last solve.  The next stage of a
    #: plan starts its support hold from it too.  ``None`` outside Rietveld
    #: mode, where the result reads the screen itself.
    significance: np.ndarray | None = None
    #: ``StageResult.window_loss`` (WP-2047): measured on the stage's own
    #: frozen model at its answer, which only ``_run_stage`` still holds
    window_loss: float | None = None


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


def _unsupported_phase_paths(model: CompiledModel, table: ParameterTable,
                             support: np.ndarray | None = None, *,
                             sigma: float | None = PHASE_SUPPORT_SIGMA
                             ) -> list[str]:
    """The free columns that move nothing but phases the data cannot see.

    **Columns, never names** (WP-1342).  This filtered ``free_paths`` by
    ``phases.{ip}.`` until a caller's ``vars.X`` could drive a phase's cell
    (WP-1119), at which point the only free *name* was the variable's, the
    prefix matched nothing, and the freeze reported that it had done its job on
    a set it could not see into — the class this repo's rules are strictest
    about.  ``ParameterTable.column_reach`` is the question restated as what a
    column *moves*; :func:`_only_moves` is the decision over it.

    "Cannot see" is a phase's significance below
    :data:`~rietx.model.forward.PHASE_SUPPORT_SIGMA` (WP-1523).  At the values
    the stage *starts* from, like every other per-stage freeze, there is no
    Jacobian, so it is ``CompiledModel.phase_support``, the screen the default
    cell window also reads.  The screen bounds the full test from above, so a
    phase it holds is one :func:`_answer_significance` would call unseen too.
    A plan's later stage reads the previous answer's significance beside it
    (:func:`_hold_unsupported_phases`).  At the answer the caller passes
    :func:`_answer_significance` instead.

    **The phase's own scale is never held.**  Every structural parameter of a
    phase reaches the pattern only through ``scale × |F|² × profile``, so with
    the scale at its floor they are all flat — but the scale itself is the one
    direction that is *not* flat, and it is how a phase legitimately climbs out
    of the noise.  Holding it would make the hold permanent, which is the one
    outcome this must never have.

    **Except where no reflection of the phase lies in the fitted range**
    (WP-1958, decided on #954).  Then the scale's column is identically zero
    at every value, no climb is possible within the stage, and the step along
    it is whatever the solver's damping makes of a zero column: LM left bcc
    Fe's scale at its 1e-4 start on WP-1534's fixture over 25-33° Cu Kα, TRF
    walked it to 164.7 and the QPA read 99.99 wt%.  Such a phase
    (:func:`_lineless_phases`) is held whole, scale included, and is held
    whatever ``sigma`` says, because "no line in range" is a count rather than
    a significance call; :func:`_released_phases` never releases it, since
    the count is frozen with the stage's windows.

    Every currently free structural path, not only the ones this stage turned
    on: staging is cumulative, so a cell freed two stages ago is still refining
    against nothing, and the ``refit="single"`` collapse — one stage carrying
    the whole plan — is exactly the shape the ramp that motivated this ran.

    ``support`` is the significance vector when a caller has already measured
    it at these values (the post-solve pass asks two questions of one
    measurement); ``None`` measures the screen here.  ``sigma`` is the plan's
    ``phase_support_sigma`` (WP-2002, B1), and ``None`` there calls no phase
    unseen on its significance, so only a phase with no line in range is held
    and no significance is measured.
    """
    lineless = _lineless_phases(model)
    absent = set(lineless)
    flat_scales = lineless - _restrained_scale_phases(model, table)
    if sigma is not None:
        if support is None:
            support = model.phase_support(table.decode(table.x0()))
        absent |= {ip for ip, s in enumerate(support) if s < sigma}
    if not absent:
        return []
    prefixes = tuple(f"phases.{ip}." for ip in sorted(absent))
    scales = tuple(f"phases.{ip}.scale" for ip in sorted(flat_scales))
    reach = table.column_reach()
    return [p for p in table.free_paths
            if _only_moves(reach.get(p, [p]), prefixes, scales)]


def _lineless_phases(model: CompiledModel) -> set[int]:
    """The phases no (emission line, reflection) window of which covers a
    point of the fitted range: :meth:`CompiledModel.phase_line_counts`' zero
    limit (WP-1958).  Only a Rietveld phase has a refinable scale to hold, so
    Le Bail and Pawley, which fix it, return the empty set."""
    if model.mode != "rietveld":
        return set()
    return {ip for ip, n in enumerate(model.phase_line_counts()) if int(n) == 0}


def _restrained_scale_phases(model: CompiledModel,
                             table: ParameterTable) -> set[int]:
    """The phases whose ``scale`` a caller's ``ValueRestraint`` pulls: its row
    gives the scale a column even with no line in range, so the WP-1958 hold
    leaves that scale to the restraint (its fraction stays absent all the
    same, the value being the caller's target and not the data's).

    Only a restraint **whose row has weight** counts: a weight of 0, or a
    stage's ``restraint_weight_scale`` of 0, silences the row and gives the
    column nothing (TRF walked such a scale from 1e-4 to 64.9).  And a
    restraint **reaches** the scales a variable drives as well as the one it
    names, so its path is read through ``ParameterTable.entry_reach``, never
    literally: a restraint on ``vars.s`` with ``phases.1.scale`` tied to it
    restrains phase 1's scale.
    """
    items = model.restraints.items if model.restraints is not None else []
    if not items or not model.restraint_weight_scale > 0.0:
        return set()
    reach = table.entry_reach()
    out: set[int] = set()
    for it in items:
        path = getattr(it, "path", None)
        if not path or not getattr(it, "weight", 1.0) > 0.0:
            continue
        for name in (path, *reach.get(path, ())):
            if (m := _SCALE_PATH.match(name)):
                out.add(int(m.group(1)))
    return out


def _held_scale_phases(sr: StageResult, hist: int | None = None) -> set[int]:
    """The phases whose own ``scale`` the stage held, off its record: a held
    column named it, or moved it (``held_reach``, a ``vars.X`` driving it).  A
    joint record's scoped path ``hist.h.…`` counts for histogram ``hist`` only,
    a bare (shared) one for every histogram."""
    out: set[int] = set()
    for path in sr.held:
        for name in (path, *sr.held_reach.get(path, ())):
            if name.startswith("hist."):
                h, _, name = name[len("hist."):].partition(".")
                if hist is None or not h.isdigit() or int(h) != hist:
                    continue
            if (m := _SCALE_PATH.match(name)):
                out.add(int(m.group(1)))
    return out


def _unmeasured_phases(model: CompiledModel,
                       stage_results: list[StageResult] | None,
                       hist: int | None = None,
                       lineless: set[int] | None = None,
                       held: set[int] | None = None) -> set[int]:
    """The phases whose scale the answer did not measure, so the QPA quotes
    them no fraction (WP-1958, #954).

    **What the last stage held, and what the answer's own count finds.**  The
    hold reads the line count at the stage's compile, and a refined zero shift
    can move a line across the range edge before the final compile counts
    again: iron held at its handed-in 1e-4 then came back at 0.607 ± 0.0035
    wt%, the value handed in with an esd (#1103).  So a scale the last stage
    held is unmeasured whatever the recount says.  The recount still counts,
    the other way round and for a restrained scale (whose column is the
    restraint's, not the data's): a phase with no line at the answer has no
    data at the values quoted.  A line entering at a closing recompile makes
    that stage free the scale, so neither reading fires and the scale is
    measured.  ``hist`` scopes a joint record to one histogram; ``lineless``
    replaces the recount where the caller owns a better one (a joint fit's
    shared scale, :func:`rietx.multi._joint_unmeasured_phases`).  ``held``
    replaces the stage record where there is none: ``replay`` reads it off the
    node (``NodeMetrics.held_scale_phases``).
    """
    if held is None:
        held = (_held_scale_phases(stage_results[-1], hist)
                if stage_results else set())
    return held | (_lineless_phases(model) if lineless is None else lineless)


#: Below this separation of a phase's scale column from its displacement
#: column, the covariance cannot see the pair as two directions, and the stage
#: holds the displacement parameters rather than solving along the ridge
#: (WP-1534).  **Derived from the covariance's own cut, never tuned.**
#: :func:`~rietx.optimize.statistics.normal_factors` equilibrates the normal
#: matrix to unit diagonal and hands it to ``pinv`` with
#: :data:`~rietx.optimize.statistics.PINV_RCOND`.  Two unit columns at angle φ
#: give the block ``[[1, c], [c, 1]]``, c = cos φ, whose eigenvalues are
#: 1 ± |c|, and 1 − |c| = r²/(1 + |c|) ≈ r²/2 with r = sin φ.  So the pair
#: alone is discarded when r²/2 < rcond · 2 — λmax is 1 + |c| ≈ 2 — that is when
#: r < 2·√rcond ≈ 6.3e-8.  In the full matrix λmax can reach the column count
#: P rather than 2, which raises the real cut by up to √(P/2), a decade at
#: P = 200.  The cases measured on WP-1534's four-phase fixture sit far
#: either side of it: bcc Fe's one reflection reads
#: 1.0e-12 through this probe (its rounding floor, :data:`SCALE_B_STEP`;
#: 2.2e-16 between the analytic columns), corundum, zincite and fluorite
#: 0.19-0.40 at stage start, so that factor decides none of them.  A pair above
#: the floor keeps its honest, possibly huge esd, which ``HIGH_CORRELATION``
#: already names.  With several displacement columns the reading is the sine
#: between the scale's column and their span, and the pair is the scale's
#: column against its projection there, so the same floor applies.
SCALE_B_SEPARATION_FLOOR = 2.0 * math.sqrt(PINV_RCOND)

#: The step in θ each displacement column is read with: Å² for a ``biso``,
#: Å² of U for an ADP DOF.  A forward difference is **exact for the question
#: asked**: a displacement parameter changes peak heights and never shapes, so
#: its difference lies in the span of the phase's reflection profiles at any
#: step, and a phase with one d-spacing has every intensity multiplied by one
#: factor.  The step only sets the rounding floor of the reading, which is
#: ε/(2·h·s²) for one column — measured 1.0e-12 on bcc Fe (s² = 0.061 Å⁻²),
#: and about 4e-11 at the lowest s² a lab scan reaches (2θ = 10° Cu Kα,
#: s² ≈ 0.003 Å⁻²), three decades under the floor.  Measured on WP-1534's
#: fixture, the separable phases' readings move by under 6 % between
#: h = 1e-3 and 1 Å².
SCALE_B_STEP = 1e-3

#: ``phases.i.atoms.j.<displacement>``: an isotropic ``biso``, an anisotropic
#: site's ADP DOF, or the U^ij component one drives — every entry a phase's
#: Debye-Waller factor reads, and nothing else.
_DISPLACEMENT_PATH = re.compile(
    r"^phases\.(\d+)\.atoms\.\d+\.(?:biso|adp\.\d+|u11|u22|u33|u12|u13|u23)$")


def _displacement_columns(table: ParameterTable,
                          reach: dict[str, list[str]]) -> dict[int, list[str]]:
    """Per phase, the free columns that move its displacement parameters only.

    **All, never any; columns, never names** — :func:`_only_moves`' two rules
    for the same reason.  A column driving two phases' B through one
    ``vars.B`` has a direction neither phase's scale can imitate unless both
    sit on one d-spacing, so it is never held for one phase's ridge, and a
    variable is dropped before the test, being an entry the forward model
    never reads.
    """
    out: dict[int, list[str]] = {}
    for col in table.free_paths:
        moved = [p for p in reach.get(col, [col]) if not is_variable_path(p)]
        if not moved:
            continue
        phases = set()
        for p in moved:
            m = _DISPLACEMENT_PATH.match(p)
            if m is None:
                break
            phases.add(int(m.group(1)))
        else:
            if len(phases) == 1:
                out.setdefault(phases.pop(), []).append(col)
    return out


def _own_scale_is_free(reach: dict[str, list[str]], ip: int) -> bool:
    """Whether some free column moves phase ``ip``'s scale and nothing else.

    The ridge is a pair of columns, so it needs the scale's as well as the
    displacement's.  With the scale held, B is measured against the one
    intensity the data gives, and holding it would freeze a determined
    parameter.  A scale shared with another phase through a variable is a
    column that phase moves too, so it is not one the displacement column can
    imitate, and it does not count.
    """
    want = [f"phases.{ip}.scale"]
    return any([p for p in moved if not is_variable_path(p)] == want
               for moved in reach.values())


def _scale_b_separation(model: CompiledModel, table: ParameterTable
                       ) -> dict[int, float]:
    """Per phase whose scale and displacement both refine, how far the scale's
    column sits from the span of its displacement columns: the sine of the
    angle between the column and that span (WP-1534).

    A phase's intensity is ``scale · exp(−2B·s²)`` times terms neither
    parameter touches, with s = sinθ/λ = 1/(2d) and the isotropic
    Debye-Waller factor T = exp(−B·s²) of International Tables Vol. C
    (Prince, 2004).  Where every reflection of the phase in the fitted range
    sits at one d-spacing, ln(scale) − 2B·s² is one coordinate, and the two
    columns are one direction — issue #204's walk of bcc Fe to B = −165 Å² on
    a 25–50° scan, scale and B moving together at an Rwp agreeing to eleven
    figures.

    **One d-spacing is the smallest case of a wider one.**  A displacement
    parameter changes peak heights and never peak shapes, so every
    displacement column lies in the span of the phase's reflection profiles
    in range, and so does the scale's.  Where the phase has more free
    displacement columns than that span has room for beside the scale, some
    combination of them imitates the scale exactly: fluorite on 25–33° Cu Kα
    has two reflections, (111) and (200), against B(Ca) and B(F), and an
    unbounded fit walked them to +99 and −111 Å² and the phase to 0.0 wt%
    (weighed 1.36; WP-1534's round-robin measurement).  Stepping every B
    together could not see it, since the uniform direction alone is separable
    there.  So the question is asked of the whole block.  A degeneracy among
    the displacement columns alone, with the scale outside it, leaves the
    fraction measured and is not this function's (WP-1535's).

    ``a`` is the weighted component ``y_p/σ`` (the scale's column, up to a
    factor) and each displacement column its change when that one column of
    θ moves by :data:`SCALE_B_STEP`.  The answer is the residual of the
    unit ``a`` after least squares onto the unit displacement columns, which
    for one column is ``|b − (a·b/a·a)·a| / (|a|·|b|)``.  The least squares
    is numpy's at its default cut, so the span carries no tolerance of this
    package's.  Read at the values the stage starts from, on the frozen
    reflection list, like every other per-stage freeze.  It reads the
    intensity the phase actually puts in the data, so it needs no tolerance
    on d and is not fooled by a reflection whose |F|² vanishes by site
    symmetry, which a count of distinct d-spacings would be.

    A phase is measured only where the question exists: Rietveld mode (Le
    Bail and Pawley force-fix every displacement path), a free column moving
    its displacement paths alone (:func:`_displacement_columns`), its own
    scale free (:func:`_own_scale_is_free`), and a nonzero component.  Every
    other phase is absent from the answer, never 1.0 or 0.0.  An anisotropic
    site's ADP DOFs are columns like any other.
    """
    return _scale_b_probe(model, table)[0]


def _column_separation(scales: list[np.ndarray], columns: list[np.ndarray]
                       ) -> float | None:
    """The sine of the smallest angle between the span of ``scales`` and the
    span of ``columns``, every vector taken at unit length
    (:func:`_scale_b_separation`), or ``None`` where either set is all zero.

    ``scales`` are one phase's scale columns: one in a single fit, one per
    histogram in a joint fit, where each lives on its own histogram's rows and
    so they are orthonormal once unit.  Each is projected off the span of
    ``columns`` by least squares at numpy's default cut, and the answer is the
    smallest singular value of what is left.  For one scale column that is
    its distance from the span.
    """
    unit_a = [a / n for a in scales if (n := float(np.linalg.norm(a))) > 0.0]
    unit_b = [c / n for c in columns if (n := float(np.linalg.norm(c))) > 0.0]
    if not (unit_a and unit_b):
        return None
    span = np.column_stack(unit_b)
    a = np.column_stack(unit_a)
    rest = a - span @ lapack.lstsq(span, a, rcond=None)[0]
    return float(lapack.svd(rest, compute_uv=False)[-1])


def _scale_b_probe(model: CompiledModel, table: ParameterTable,
                   phases: set[int] | None = None
                   ) -> tuple[dict[int, float], dict[str, list[str]],
                              dict[int, list[str]]]:
    """:func:`_scale_b_separation`, with the column reach and the
    displacement columns it read, so a caller holding on the answer does not
    read **C** again; ``phases`` limits the question to those phases."""
    if model.mode != "rietveld":
        return {}, {}, {}
    reach = table.column_reach()
    columns = _displacement_columns(table, reach)
    if phases is not None:
        columns = {ip: c for ip, c in columns.items() if ip in phases}
    if not columns:
        return {}, reach, columns
    theta = table.x0()
    values = table.decode(theta)
    index = {p: k for k, p in enumerate(table.free_paths)}
    sigma = np.asarray(model.sigma, dtype=np.float64)
    out: dict[int, float] = {}
    for ip in sorted(columns):
        if not _own_scale_is_free(reach, ip):
            continue
        a = np.asarray(model.phase_component(ip, values), dtype=np.float64) / sigma
        stepped = []
        for col in columns[ip]:
            th = theta.copy()
            th[index[col]] += SCALE_B_STEP
            stepped.append(np.asarray(model.phase_component(ip, table.decode(th)),
                                      dtype=np.float64) / sigma - a)
        r = _column_separation([a], stepped)
        if r is not None:
            out[ip] = r
    return out, reach, columns


def _hold_scale_b_ridges(model: CompiledModel, table: ParameterTable,
                         phases: set[int] | None = None
                         ) -> tuple[list[str], dict[str, list[str]],
                                    dict[int, float]]:
    """Hold every phase's displacement columns where :func:`_scale_b_separation`
    is under :data:`SCALE_B_SEPARATION_FLOOR`.

    Returns what it held, the held columns' reach (read while they are still
    columns, :func:`_reach_beyond_self`), and the separation of every phase it
    held for — the record ``StageResult.scale_b_held`` carries.  The phase's
    scale is never held: it is the half of the pair the data does measure,
    the phase's one intensity, and holding B leaves it measuring exactly that.
    ``phases`` limits the test to those phases (a release inside the stage).
    """
    separation, reach, columns = _scale_b_probe(model, table, phases)
    ridged = {ip: r for ip, r in separation.items()
              if r < SCALE_B_SEPARATION_FLOOR}
    if not ridged:
        return [], {}, {}
    held = [c for ip in sorted(ridged) for c in columns.get(ip, [])]
    held_reach = _reach_beyond_self(table, held, reach)
    table.set_vary(held, False)
    return held, held_reach, ridged


#: What a pattern sees of the peak widths (``CompiledModel._width_block``): per
#: angular term, the instrument coefficient, the specimen widths that add to it,
#: and whether the hold may take the instrument side.  Γ_G² = U·tan²θ + V·tanθ +
#: W + ``gauss_size``/cos²θ + ``gauss_strain``·tan²θ, and 1/cos²θ = 1 + tan²θ, so
#: ``gauss_size`` adds to the tan²θ and the constant terms; Γ_L = (X +
#: ``lor_size``)/cosθ + (Y + ``lor_strain``)·tanθ.  A joint fit's λ factors on
#: the size terms (WP-1131) are in **C**, so the test below reads them without
#: naming them.
#:
#: **W is never held.**  It is the constant width every fit needs and has no
#: specimen twin of its own: with U and W free beside ``gauss_size``,
#: (δU, δW, δsize) = (−1, −1, 1) is flat, and holding U alone removes it, since
#: δW + δsize·(1 + tan²θ) = 0 at every angle forces both to zero.  W's total
#: stays a row of the test, so a held W pins the size and nothing is held.
#: Holding W as well moved three acceptance answers (the generality judge,
#: WP-2002 9th session).
WIDTH_TERMS: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("instrument.profile.u", ("gauss_strain", "gauss_size"), True),  # tan²θ in Γ_G²
    ("instrument.profile.w", ("gauss_size",), False),                # 1 in Γ_G²
    ("instrument.profile.x", ("lor_size",), True),                   # 1/cosθ in Γ_L
    ("instrument.profile.y", ("lor_strain",), True),                 # tanθ in Γ_L
)


def _width_twin_flats(parts: list[tuple[ParameterTable, np.ndarray, set[int]]],
                      n_columns: int) -> dict[int, list[int]]:
    """The instrument width columns on a flat direction with specimen widths
    (:data:`WIDTH_TERMS`), each with the specimen columns it pairs with.

    ``parts`` holds one ``(table, col_map, unseen)`` per pattern: the table,
    the θ column each of its free columns is (the identity for a single fit),
    and the phases its data cannot see.  Columns are θ indices.

    **Columns, never names** (WP-1342), and exact.  Each seen phase of each
    pattern sees one total per angular term, so a move of the free columns is
    flat when it changes none of those totals and no other entry.  That is the
    null space of a matrix read off **C**, so a tie, a ``vars.X`` and a joint
    fit's λ factor all enter as coefficients.  The pairs U with
    ``gauss_strain``, X with ``lor_size`` and Y with ``lor_strain`` are flat
    this way, and ``gauss_size`` with U and W together, of which only U is
    held (:data:`WIDTH_TERMS`).  Two consequences follow without a rule of
    their own.
    One seen phase whose specimen width is held pins the instrument term for
    every phase, so nothing is flat.  A pattern whose instrument width is held
    pins the shared specimen width, and every other pattern's instrument width
    with it.  An unseen phase's totals are left out, because its peaks pin
    nothing; its own columns are the support hold's.

    A free Stephens block (``Phase.microstrain``) locks ``lor_strain`` and
    takes its place as Y's twin.  The block's isotropic direction is Y's
    exactly at the seed (``Stage.strain_seed``) and only near it once the
    strain turns anisotropic, so this one pair is held by rule rather than
    by the null space.  At the seed the first steps would face an exactly
    singular pair, and FullProf's shipped Stephens example holds its tanθ
    Lorentzian term while refining the block (``docs/practice.md``).  It also
    keeps an isotropic fit and its Stephens rival on the same instrument
    parameters (``tests/test_acceptance_stephens.py``).  A block that is
    present and held pins Y like a held ``lor_strain``.
    """
    def row(C, col_map: np.ndarray, i: int) -> np.ndarray:
        out = np.zeros(n_columns, dtype=np.float64)
        sl = slice(C.indptr[i], C.indptr[i + 1])
        np.add.at(out, col_map[C.indices[sl]], C.data[sl])
        return out

    sums: list[np.ndarray] = []
    couples: list[tuple[set[int], set[int]]] = []
    # the instrument columns the hold may take: W's total is a row, never a hold
    holdable: set[int] = set()
    families: list[set[int]] = []
    Cs = [table.constraint_block()[0].tocsr() for table, _, _ in parts]
    for (table, col_map, unseen), C in zip(parts, Cs, strict=True):
        pos = table._paths
        family: set[int] = set()
        families.append(family)
        for inst, names, may_hold in WIDTH_TERMS:
            i_inst = pos.get(inst)
            if i_inst is None:
                continue
            family.add(i_inst)
            r_inst = row(C, col_map, i_inst)
            if may_hold:
                holdable.update(np.flatnonzero(r_inst).tolist())
            ip = 0
            while f"phases.{ip}.scale" in pos:
                idx = [pos[f"phases.{ip}.{n}"] for n in names
                       if f"phases.{ip}.{n}" in pos]
                family.update(idx)
                block = (_stephens_block(pos, ip) if "lor_strain" in names
                         else [])
                r_block = sum((np.abs(row(C, col_map, i)) for i in block),
                              np.zeros(n_columns))
                family.update(block)
                if ip not in unseen and r_block.any():
                    # a free Stephens block is Y's twin: no total pins Y
                    couples.append((set(np.flatnonzero(r_inst).tolist()),
                                    set(np.flatnonzero(r_block).tolist())))
                elif ip not in unseen:
                    r_phase = sum((row(C, col_map, i) for i in idx),
                                  np.zeros(n_columns))
                    sums.append(r_inst + r_phase)
                    couples.append((set(np.flatnonzero(r_inst).tolist()),
                                    set(np.flatnonzero(r_phase).tolist())))
                ip += 1
    inst_cols = set().union(*(a for a, _ in couples))
    if not inst_cols & holdable:
        return {}
    # the columns a family entry reaches; a move of any other is no twin's
    cand = sorted(inst_cols.union(*(b for _, b in couples)))
    in_cand = np.zeros(n_columns, dtype=bool)
    in_cand[cand] = True
    # every other entry those columns move must stay still too: a column
    # driving a twin and a cell is pinned by the cell
    others = []
    for (_, col_map, _), family, C in zip(parts, families, Cs, strict=True):
        touched = np.flatnonzero(in_cand[col_map])
        for i in np.unique(C[:, touched].nonzero()[0]):
            if int(i) not in family:
                others.append(row(C, col_map, int(i)))
    A = np.array([r[cand] for r in (*sums, *others) if r[cand].any()],
                 dtype=np.float64).reshape(-1, len(cand))
    if A.shape[0]:
        _, s, vt = lapack.svd(A)
        rank = int(np.sum(s > s[0] * len(cand) * np.finfo(np.float64).eps))
        null = vt[rank:].T
    else:
        null = np.eye(len(cand))
    on_flat = {c for c, r in zip(cand, null, strict=True)
               if r.size and np.abs(r).max() > 1e-8}
    out: dict[int, list[int]] = {}
    for c in sorted(inst_cols & holdable & on_flat):
        twins = {k for a, b in couples if c in a
                 for k in b if k in on_flat and k not in inst_cols}
        if twins:
            out[c] = sorted(twins)
    return out


def _stephens_block(pos: dict[str, int], ip: int) -> list[int]:
    """The entry indices of phase ``ip``'s Stephens block, its DOFs and the
    S_HKL they drive, empty without a block."""
    prefix = f"phases.{ip}.microstrain."
    return [i for p, i in pos.items() if p.startswith(prefix)]


def _hold_width_twins(table: ParameterTable, unseen: set[int]
                      ) -> tuple[list[str], dict[str, list[str]],
                                 dict[str, list[str]]]:
    """Hold every instrument width column :func:`_width_twin_flats` puts on a
    flat direction with a free specimen twin (WP-2002).

    Returns the held columns, their reach (:func:`_reach_beyond_self`) and,
    per held column, the twin columns it pairs with — the record
    ``StageResult.width_twins_held`` carries.  The instrument half is the one
    held because every program that separates the two does it by fixing the
    instrument from a standard (``docs/practice.md`` § Instrument and
    specimen widths refined together), and the specimen value is then the
    width the instrument does not account for.
    """
    names = table.free_paths
    flats = _width_twin_flats([(table, np.arange(len(names)), unseen)],
                              len(names))
    if not flats:
        return [], {}, {}
    held = [names[c] for c in flats]
    reach = _reach_beyond_self(table, held)
    table.set_vary(held, False)
    return held, reach, {names[c]: [names[k] for k in ks]
                         for c, ks in flats.items()}


# ``MOMENT_DIRECTION_SUPPORT`` is defined in
# :mod:`rietx.crystallography.magnetic.moments` (imported at the top of this
# module), because the solver's stationary-angle test reads it as well and
# ``optimize`` may not import ``refine``.  Its comment there says how the
# hold below and that test relate.

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


#: Generic test directions for :func:`_flat_rotation_axis`, on the frame's
#: coefficient sphere.  Fixed rather than random so two runs of one stage hold
#: the same thing, and chosen on no symmetry element of any lattice — none on
#: an axis, a face diagonal or a body diagonal — so a rotation that is trivial
#: at one of them (about the direction itself) is not trivial at the others.
_FLAT_AXIS_TEST_DIRECTIONS = np.array([[0.48, 0.36, 0.80],
                                       [-0.64, 0.60, 0.48]])


def _direction(theta: float, phi: float) -> np.ndarray:
    """Unit coefficient vector of an n = 3 frame at polar θ, azimuth φ."""
    st = math.sin(theta)
    return np.array([st * math.cos(phi), st * math.sin(phi), math.cos(theta)])


def _angles(s: np.ndarray) -> tuple[float, float]:
    """(θ, φ) of a unit coefficient vector — the inverse of :func:`_direction`."""
    return (float(np.arccos(np.clip(s[2], -1.0, 1.0))),
            float(np.arctan2(s[1], s[0])))


def _rotate(s: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    """``s`` turned by ``angle`` about the unit ``axis``.

    Rodrigues' rotation formula (Rodrigues, O., 1840, *J. Math. Pures Appl.*
    **5**, 380): v cos α + (k × v) sin α + k (k·v)(1 − cos α).
    """
    c, sn = math.cos(angle), math.sin(angle)
    return (s * c + np.cross(axis, s) * sn
            + axis * float(axis @ s) * (1.0 - c))


def _flat_rotation_axis(model: CompiledModel, values: dict[str, float],
                        base: str) -> np.ndarray | None:
    """The axis a three-DOF moment can turn about unseen, or ``None`` (#599).

    The per-column test in :func:`_flat_moment_paths` asks whether the polar
    angle *or* the azimuth is flat, and that is the right question only when
    the frame's polar row lies along the axis the powder is uniaxial about.
    :func:`~rietx.crystallography.magnetic.moments.moment_frame` builds that
    row by Gram–Schmidt on the allowed basis, so on tetragonal and hexagonal
    axes it is **c** and the azimuth is the flat column; on rhombohedral axes
    the unique axis is [111], the row is not, and the flat rotation is a
    *combination* of the two angles that neither column owns.  Measured on
    R-3m:R (a = 4 Å, α = 70°): each column alone responds at order 1 of the
    modulus, the rotation about [111] at 4.8e-16, and the fit came back with
    esds on both angles and a ρ = +1.000 between them.

    **Rank, not columns.**  A rotation of the moment about a unit axis **u**
    moves it by **u** × **m**, so the first-order response to rotating about
    **u** is linear in **u**: three columns (rotations about the frame's own
    axes) span it.  A flat *axis* is a null vector of that 3-column block —
    but at a single direction the block always has one, **u** = **m** itself
    (a rotation that does nothing), and at a direction the symmetry fixes it
    has more, because every first derivative vanishes at a stationary point
    (the reason :data:`MOMENT_PROBE_ANGLE_RAD` is finite).  So the block is
    stacked over the current direction *and* two generic ones
    (:data:`_FLAT_AXIS_TEST_DIRECTIONS`): a rotation trivial at one is not at
    the others, a stationary point at one is not at the others, and what is
    left null is a rotation the pattern does not see **wherever the moment
    points** — Shirane's uniaxial invariance (Shirane, G., 1959, *Acta
    Cryst.* **12**, 282), measured rather than derived, as the per-column
    probe is.

    **The SVD proposes, the finite rotation decides.**  The smallest right
    singular vector is a candidate only; it is held only when turning the
    moment about it by :data:`MOMENT_PROBE_ANGLE_RAD` each way, at every one
    of those directions, moves the pattern by no more than
    :data:`MOMENT_DIRECTION_SUPPORT` of what the same tip displacement of the
    modulus does — the per-column test's own floor and step, so a direction
    is held by one rule whichever way the frame happens to lie.

    ``values`` are decoded physical values; the moment's modulus is never
    moved, and a site at the floor returns ``None`` (the per-column test
    already holds every direction there).
    """
    mu = abs(values[f"{base}.dof0"])
    if mu <= 0.0:
        return None

    def evaluate(s: np.ndarray, modulus: float | None = None) -> np.ndarray:
        theta, phi = _angles(s)
        v = dict(values)
        v[f"{base}.dof1"], v[f"{base}.dof2"] = theta, phi
        if modulus is not None:
            v[f"{base}.dof0"] = modulus
        return np.asarray(model.evaluate(v), dtype=np.float64)

    current = _direction(values[f"{base}.dof1"], values[f"{base}.dof2"])
    tests = [current] + [t / np.linalg.norm(t)
                         for t in _FLAT_AXIS_TEST_DIRECTIONS]
    # the stationary-angle test's own step on the same quantity, an angle of
    # order one; the SVD only proposes, the finite turn below decides
    h = STATIONARY_ANGLE_STEP
    blocks = []
    for s in tests:
        cols = [(evaluate(_rotate(s, e, h)) - evaluate(_rotate(s, e, -h)))
                / (2.0 * h) for e in np.eye(3)]
        blocks.append(np.column_stack(cols))
    _, _, vt = lapack.svd(np.vstack(blocks), full_matrices=False)
    axis = vt[-1] / np.linalg.norm(vt[-1])
    signed = values[f"{base}.dof0"]
    for s in tests:
        y = evaluate(s)
        scale = float(np.linalg.norm(
            evaluate(s, signed + math.copysign(MOMENT_PROBE_ANGLE_RAD * mu,
                                               signed)) - y))
        if scale <= 0.0:
            return None
        # both senses of the turn, for the per-column probe's reason: a
        # one-sided turn can land on a mirror image of ``s`` and read flat
        for sign in (1.0, -1.0):
            turned = float(np.linalg.norm(
                evaluate(_rotate(s, axis, sign * MOMENT_PROBE_ANGLE_RAD)) - y))
            if turned > MOMENT_DIRECTION_SUPPORT * scale:
                return None
    return axis


def _onto_flat_meridian(model: CompiledModel, values: dict[str, float],
                        base: str, axis: np.ndarray
                        ) -> tuple[float, float] | None:
    """(θ, φ) of the moment turned about ``axis`` into the polar meridian.

    Holding one of two angles removes a flat *combination* from the problem
    only when the held column's own motion is that combination, and is a
    trap otherwise: with the azimuth held at an arbitrary value the polar
    angle sweeps a great circle that need not come within the measured angle
    of the axis at all.  So the moment is first turned about the flat axis —
    a move the data cannot see, which is what makes it flat — until it lies
    in the plane of the axis and the frame's polar row.  There the azimuth's
    tangent is **u** × **m**, the flat rotation exactly, and the polar angle
    sweeps the great circle *through* the axis, so it reaches every angle to
    it: the frame now refines what the P4/mmm frame refines, the modulus and
    the angle to the unique axis, offset by the axis's own polar angle.

    Of the two points on that circle the one farther from the frame's pole
    is taken, so the azimuth stays defined.  The construction is elementary
    spherical geometry — the cone of half-angle ψ about **u** meets the great
    circle through **u** and the pole at the two points cos ψ **u** ± sin ψ
    **v̂**, **v̂** the unit in-plane normal to **u** — and the turn reaching
    it is a rotation about **u** (:func:`_rotate`); that the turn is unseen
    is Shirane's uniaxial invariance (*Acta Cryst.* **12**, 282, 1959),
    which this function does not assume but measures against the floor.  ``None`` when the axis already
    is the pole (nothing to turn) or the turned moment does not reproduce the
    pattern to the same floor — the rotation is then left undone and the
    caller holds the azimuth where it is.
    """
    pole = np.array([0.0, 0.0, 1.0])
    s = _direction(values[f"{base}.dof1"], values[f"{base}.dof2"])
    u = axis if float(axis @ s) >= 0.0 else -axis
    v = pole - float(pole @ u) * u
    if np.linalg.norm(v) <= 1e-9:
        return None
    v = v / np.linalg.norm(v)
    cos_psi = float(np.clip(u @ s, -1.0, 1.0))
    sin_psi = math.sqrt(max(1.0 - cos_psi ** 2, 0.0))
    turned = max((cos_psi * u + sign * sin_psi * v for sign in (1.0, -1.0)),
                 key=lambda t: float(np.hypot(t[0], t[1])))
    theta, phi = _angles(turned)
    mu = abs(values[f"{base}.dof0"])
    signed = values[f"{base}.dof0"]
    v0 = dict(values)
    y = np.asarray(model.evaluate(v0), dtype=np.float64)
    v1 = dict(values)
    v1[f"{base}.dof1"], v1[f"{base}.dof2"] = theta, phi
    v2 = dict(values)
    v2[f"{base}.dof0"] = signed + math.copysign(MOMENT_PROBE_ANGLE_RAD * mu,
                                                signed)
    scale = float(np.linalg.norm(np.asarray(model.evaluate(v2)) - y))
    moved = float(np.linalg.norm(np.asarray(model.evaluate(v1)) - y))
    if scale <= 0.0 or moved > MOMENT_DIRECTION_SUPPORT * scale:
        return None
    return theta, phi


def _flat_moment_scan(model: CompiledModel, table: ParameterTable,
                      candidates: list[str] | None = None
                      ) -> tuple[list[str], dict[str, np.ndarray]]:
    """:func:`_flat_moment_paths`, with the flat axis of every site whose
    flat direction is a combination (#599) — ``{site base: axis}``, the axis
    in the site's frame coefficients — for :func:`_hold_flat_moments`, which
    turns the moment onto it before holding."""
    paths = [p for p in (table.free_paths if candidates is None else candidates)
             if _MOMENT_DOF.match(p) and not p.endswith(".dof0")]
    if not paths:
        return [], {}
    values = table.decode(table.x0())
    y0 = np.asarray(model.evaluate(values), dtype=np.float64)

    def response(path: str, step: float) -> float:
        v = dict(values)
        v[path] = values[path] + step
        return float(np.linalg.norm(
            np.asarray(model.evaluate(v), dtype=np.float64) - y0))

    def column_flat(path: str) -> bool:
        modulus = path.rsplit(".dof", 1)[0] + ".dof0"
        mu = abs(values[modulus])
        # the same tip displacement both ways: a rotation by δφ moves the
        # moment by |μ|·δφ, so the modulus is probed by exactly that much
        scale = response(modulus, MOMENT_PROBE_ANGLE_RAD * max(mu, 1e-6))
        # **Both signs** (WP-1929).  The pattern is even about every direction
        # the symmetry fixes, so from a start 0.05 rad off one a +0.1 rad turn
        # lands on the start's mirror image and moves nothing.  That held a
        # determined angle, and the fit ended at χ² 20614.  A direction is flat
        # only when neither turn moves the pattern.
        return scale <= 0.0 or all(
            response(path, sign * MOMENT_PROBE_ANGLE_RAD)
            <= MOMENT_DIRECTION_SUPPORT * scale for sign in (1.0, -1.0))

    flat = [p for p in paths if column_flat(p)]
    # The combination (#599): a site whose two angles are both live — free,
    # or asked about — and neither flat on its own.  "Live" rather than
    # "asked about", because the release question passes only the held
    # azimuth, and whether it is still flat depends on the polar angle being
    # free beside it; one angle the caller holds already breaks the
    # combination, and the per-column answer above is then the whole answer.
    live = set(table.free_paths) | set(paths)
    axes: dict[str, np.ndarray] = {}
    for base in dict.fromkeys(p.rsplit(".", 1)[0] for p in paths):
        polar, azimuth = f"{base}.dof1", f"{base}.dof2"
        if (polar not in live or azimuth not in live
                or polar in flat or azimuth in flat
                or (polar not in paths and column_flat(polar))):
            continue
        axis = _flat_rotation_axis(model, values, base)
        if axis is None:
            continue
        axes[base] = axis
        # the azimuth, always: :func:`_hold_flat_moments` turns the moment
        # until the azimuth *is* the flat rotation, and a release asked after
        # it finds the moment still on that meridian
        if azimuth in paths:
            flat.append(azimuth)
    return flat, axes


def _flat_moment_paths(model: CompiledModel, table: ParameterTable,
                       candidates: list[str] | None = None) -> list[str]:
    """Moment **direction** DOFs the calculated pattern does not respond to.

    The rule WP-1327 takes from WP-1301, one object down: a direction the data
    cannot see is a flat direction, and holding it is cheaper and truer than
    letting it wander into a number with an esd.  What a powder cannot see of
    a moment is Shirane's result (Shirane, G., 1959, *Acta Cryst.* **12**,
    282) — a cubic collinear structure's direction entirely, a uniaxial
    one's azimuth — and it is *measured* here
    rather than derived from the symmetry, so a structure the classification
    does not anticipate is handled by the same rule.

    Two measurements, one floor.  Each angle column on its own, by a finite
    rotation; and, on a three-DOF site where neither column is flat, the
    rank of the angle block (:func:`_flat_rotation_axis`), because the flat
    rotation of a uniaxial structure is a column only when the frame's polar
    row happens to lie along the unique axis — on rhombohedral axes it does
    not (#599).  A flat combination is answered with the **azimuth**, which
    :func:`_hold_flat_moments` makes the flat rotation exactly before holding
    it.

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
    return _flat_moment_scan(model, table, candidates)[0]


def _turn_onto_meridians(model: CompiledModel, table: ParameterTable,
                         axes: dict[str, np.ndarray]) -> dict[str, list[float]]:
    """Turn each site in ``axes`` onto its flat meridian; returns the turned.

    The one place a flat combination's moment is turned (#599, review of
    #624 item 1), so every hold of one — at stage start, after a release at
    the answer, after a collapse — turns before it holds.  Writes into the
    table at its current values (:func:`_onto_flat_meridian` checks the turn
    against the floor there) and returns ``{site: flat axis}`` for the sites
    it actually turned, the axis in crystal-axis components (a unit vector
    in the magCIF unit-vector metric) — the record ``StageResult`` carries.
    A site whose turn did not reproduce the pattern is left where it was and
    is absent from the answer.
    """
    if not axes:
        return {}
    values = table.decode(table.x0())
    frames = table.moment_frames()
    by_path = {e.path: e for e in table.entries}
    turned: dict[str, list[float]] = {}
    for base, axis in axes.items():
        angles = _onto_flat_meridian(model, values, base, axis)
        if angles is None:
            continue
        by_path[f"{base}.dof1"].value, by_path[f"{base}.dof2"].value = angles
        turned[_site(base)] = _axis_in_crystal_axes(axis, frames[_site(base)])
    table.refresh_ties()
    return turned


def _site(base: str) -> str:
    """``phases.i.atoms.j`` of a moment DOF block ``phases.i.atoms.j.moment``
    — the key the frames and ``StageResult.moment_flat_axes`` use."""
    return base.removesuffix(".moment")


def _axis_in_crystal_axes(axis: np.ndarray, frame: np.ndarray) -> list[float]:
    """A frame-coefficient axis as crystal-axis components."""
    return [float(c) for c in np.asarray(axis) @ np.asarray(frame)]


def _hold_flat_moments(model: CompiledModel, table: ParameterTable
                       ) -> tuple[list[str], dict[str, list[float]],
                                  dict[str, list[float]]]:
    """Apply :func:`_flat_moment_paths` to the table.

    Returns what it held, the flat axis (crystal-axis components) of every
    site held as a combination, and which of those it turned
    (:func:`_turn_onto_meridians`) before holding their azimuth.
    """
    held, axes = _flat_moment_scan(model, table)
    frames = table.moment_frames()
    found = {_site(b): _axis_in_crystal_axes(a, frames[_site(b)])
             for b, a in axes.items()}
    turned = _turn_onto_meridians(model, table, axes)
    if held:
        table.set_vary(held, False)
    return held, found, turned


def _only_moves(reached: list[str], prefixes: tuple[str, ...],
                scales: tuple[str, ...] = ()) -> bool:
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

    ``scales`` names the scales that *are* flat: those of a phase with no
    reflection in the fitted range (WP-1958, :func:`_lineless_phases`), whose
    column is identically zero at every value, so no climb is possible.

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
        p.startswith(prefixes) and (not p.endswith(".scale") or p in scales)
        for p in moved)


def _reach_beyond_self(table: ParameterTable, columns: list[str],
                       reach: dict[str, list[str]] | None = None
                       ) -> dict[str, list[str]]:
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
    # a caller that has just read C for the same table hands it in
    reach = table.column_reach() if reach is None else reach
    out = {}
    for c in columns:
        other = [p for p in reach.get(c, [c]) if p != c]
        if other:
            out[c] = other
    return out


def _hold_unsupported_phases(model: CompiledModel, table: ParameterTable,
                             prior: np.ndarray | None = None,
                             seeded_phases: Iterable[int] = (), *,
                             sigma: float | None = PHASE_SUPPORT_SIGMA,
                             ) -> tuple[list[str], dict[str, list[str]], set[int]]:
    """Apply :func:`_unsupported_phase_paths`; returns what it held, its reach
    and the phases it judged unseen.

    The first two, because the reach is only readable while the columns are
    still free — see :func:`_reach_beyond_self`.  The third is what
    :func:`_hold_width_twins` leaves out: an unseen phase's peaks pin no
    instrument width.

    ``prior`` is the previous stage's :func:`_answer_significance` in a plan
    (WP-1523), read beside the screen: a phase under the threshold by either
    is held.  The screen alone frees a phase whose scale was fitted to noise
    whenever its conditional z passes while the marginal one does not, and
    the stage then chases the noise, collapses it, restores it and solves
    again.  A plan's free set only grows, so the marginal z here is no larger
    to first order.

    The reading was taken where the previous answer stood, and three things
    can move a phase off it before this stage starts.  A stage seed writes a
    row (``Stage.seed``, ``Stage.strain_seed``), so the caller names the
    phases a seed reached in ``seeded_phases`` and their prior is dropped:
    a seeded scale would otherwise stay held on a reading from before the
    seed and pay the second solve this exists to remove.  A collapse puts
    the phase back where its stage started, after the reading was taken.
    ``reset_cell_runaway`` can put a cell back after a stage's last solve,
    whose Jacobian the reading used.  In the last two cases the phase stays held by a reading
    that the stage's own measurement called unseen, and a stale reading errs
    only towards holding, since the minimum is taken and the scale stays
    free for the release at the answer.

    Measured on seed 107 of #481's blank frame under ``mccusker_structural``:
    18 solves for 11 stages with the screen alone, 11 with the prior read.
    A significance hold never takes the scale (only a phase with no
    line in range has it held), so a phase that appears while this
    stage solves is released at its answer as before.  What it gives up is a
    second look with the phase's columns refining: a held phase is judged at
    its held values.  Over the WP's sweep that moved one weak real phase of
    64 fits from refined to held, at 2.46σ.

    ``sigma`` is the plan's ``phase_support_sigma`` (WP-2002, B1); ``None``
    measures nothing and holds only a phase with no line in range (WP-1958).
    """
    if sigma is None:
        held = _unsupported_phase_paths(model, table, sigma=None)
        reach = _reach_beyond_self(table, held)
        if held:
            table.set_vary(held, False)
        return held, reach, _lineless_phases(model)
    support = np.asarray(model.phase_support(table.decode(table.x0())),
                         dtype=np.float64)
    if prior is not None:
        # one plan, one structure: the two vectors index the same phases
        prior = np.array(prior, dtype=np.float64)
        prior[list(seeded_phases)] = np.inf
        support = np.minimum(support, prior)
    held = _unsupported_phase_paths(model, table, support, sigma=sigma)
    reach = _reach_beyond_self(table, held)
    if held:
        table.set_vary(held, False)
    return held, reach, {ip for ip, z in enumerate(support) if z < sigma}


def _escaped_cell_paths(table: ParameterTable, start_values: dict[str, float]
                        ) -> list[str]:
    """The free cell parameters outside ``CELL_SAFETY_FRACTION`` /
    ``CELL_SAFETY_ANGLE_DEG`` of ``start_values``, the stage's own, in entry
    order.  :func:`reset_cell_runaway`'s test, kept apart so the joint runner
    can ask it of every histogram before it restores any of them."""
    escaped: list[str] = []
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
            escaped.append(e.path)
    return escaped


def _restore_phase_cells(table: ParameterTable, start_values: dict[str, float],
                         phases: Iterable[str], escaped: Iterable[str]
                         ) -> list[CellReset]:
    """Put every free cell parameter of ``phases`` (phase indices as they
    appear in a path) back at ``start_values``; one :class:`CellReset` each.

    The tied entries are refreshed off the restored sources, so a cubic ``b``
    and ``c`` follow ``a`` and a rhombohedral ``β``, ``γ`` follow ``α``.
    """
    phases, escaped = set(phases), set(escaped)
    if not phases:
        return []
    by_path = {e.path: e for e in table.entries}
    out: list[CellReset] = []
    for path in table.free_paths:
        parts = path.split(".")
        if (_cell_parameter_name(path, phases=None) is None
                or parts[1] not in phases
                or not math.isfinite(start_values.get(path, math.nan))):
            continue
        out.append(CellReset(path, float(by_path[path].value),
                             float(start_values[path]),
                             escaped=path in escaped))
        by_path[path].value = start_values[path]
    table.refresh_ties()
    return out


def reset_cell_runaway(table: ParameterTable, start_values: dict[str, float]
                       ) -> list[CellReset]:
    """Put back at ``start_values`` (the stage's own) the whole free cell of
    every phase whose free cell parameter left ``CELL_SAFETY_FRACTION`` /
    ``CELL_SAFETY_ANGLE_DEG`` of it; report each restored parameter as
    ``(path, solved_value, start_value)``.

    The caller holds what this restored for the rest of the stage and solves
    once more without it (WP-2002, B8, ruled 2026-10-19), through the same
    path a collapsing phase takes (WP-1301).  This function moves values
    only and never calls ``set_vary``, because the caller measures each
    phase's significance at the restored values before it decides which hold
    claims each path.  A refiner whose cell ran away puts it back and fixes
    it; a cell pulled to the window's edge, as this did before, was a value
    no fit produced, with esds from the runaway point.

    The **whole** free cell of the phase goes back, also a parameter that
    stayed inside its window: the parameters moved together, so one restored
    beside its partners' solved values is again a cell no fit produced.  The
    restored cell is the one the stage's own residual evaluated, so its volume
    is positive.

    Call this **after** ``table.commit(outcome.theta)``, on the committed
    ``Entry.value``\\ s, never as a bound the solver sees, which is the whole
    design (:data:`~rietx.params.vector.CELL_SAFETY_FRACTION`'s docstring):
    ``cell_window``'s own support-based window is deliberately restricted to
    phases ``phase_support`` judges invisible, because a live bound changes
    scipy TRF's trust-region step scaling even where it is never hit,
    measurably costing iterations and pinned digits on a phase that was never
    going to run away.  A phase judged **visible** the whole time (the trigger
    case: two free phases sharing a near-identical cell, one at full scale)
    is exactly what that window cannot reach, so this checks the *outcome*
    unconditionally instead.  A fit whose cell never leaves the window is
    bit-identical (every one measured in WP-1110's own 51-transition survey,
    and none of WP-1523's 104 fits fired it).

    Symmetry-derived cell parameters (``b``/``c`` tied to ``a`` on a cubic
    cell, etc.) are not in ``table.free_paths`` and are not visited here;
    :meth:`~rietx.params.vector.ParameterTable.refresh_ties` re-derives them
    off the restored sources before this returns.

    **A cell driven by a caller's free ``vars.X`` is a different case, and
    this function deliberately does not touch it** (review of #385 finding
    1).  ``e.path not in free`` in :func:`_escaped_cell_paths` tests the free
    path's own *name*, the same construction :func:`_unsupported_phase_paths`
    and :func:`_reach_beyond_self` already had to repair for WP-1342: a cell
    tied to a free variable is not itself a free column (so the loop never
    visits its entry) and the variable's own name is not a cell name either,
    so testing names alone leaves it invisible twice over.  Resetting the
    driver would not be the right fix if it were visible: it would move
    whatever else that variable drives, and a variable driving two cells has
    no one start to go back to.  So the escape is *named*, never silently
    passed through, by :func:`_vars_driven_cell_escapes` beside this
    function, which the caller folds into the same ``CELL_RUNAWAY``
    diagnostic.
    """
    escaped = _escaped_cell_paths(table, start_values)
    if not escaped:
        return []
    return _restore_phase_cells(table, start_values,
                                {p.split(".")[1] for p in escaped}, escaped)


class CellReset(tuple):
    """``(path, solved_value, start_value)`` of one :func:`reset_cell_runaway`
    finding, unpackable as the plain triple ``for path, old, new in ...``
    reads.

    ``escaped`` is True where this parameter itself left the safety window,
    and False for a free cell parameter of the same phase that stayed inside
    it and went back with its cell.  ``held`` is True where the stage then
    held the parameter and solved again, which is a runaway found after the
    stage's first solve.  It is False for one found after the stage's second
    solve, which has no solve after it: the value is restored and the column
    stays free in that answer, its esd withheld.  A tuple subclass, not more
    elements, so equality with a plain triple stands.
    """

    escaped: bool
    held: bool

    def __new__(cls, path: str, solved: float, start: float, *,
                escaped: bool = True, held: bool = True):
        self = super().__new__(cls, (path, solved, start))
        self.escaped = escaped
        self.held = held
        return self


def _vars_driven_cell_escapes(table: ParameterTable,
                              start_values: dict[str, float]
                              ) -> list[tuple[str, list[str]]]:
    """Cell parameters a free ``vars.X`` drives outside the safety window —
    named, never reset (review of #385 finding 1).

    :func:`reset_cell_runaway` tests a free entry's own path against a cell
    name, so a cell tied to a free ``vars.X`` is invisible to it: the cell is
    not a free column (it is that column's dependent) and the free column's
    own name is the variable's, not a cell's.  This asks the other question
    instead — **columns, never names**, :func:`_unsupported_phase_paths`'s
    repair for the identical construction (refine.py's own docstring on the
    ``moving_paths``-vs-``free_paths`` split names this file) — by reading
    :meth:`~rietx.params.vector.ParameterTable.column_reach`, which answers
    what a column *moves* rather than what it is called.

    **Never reset, by design, not merely by omission.**  A variable driving
    one cell has a single target and putting it back would still move
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


def _merge_unresolved(first: list[tuple[str, list[str]]],
                      second: list[tuple[str, list[str]]]
                      ) -> list[tuple[str, list[str]]]:
    """Two solves' driven escapes as one record, merged by driver, so a
    driver still escaping after both is named once, not twice.

    One rule for both runners, :meth:`Refinement._run_stage` and the joint
    stage loop in ``multi.py`` (WP-2028 task 7).
    """
    merged = dict(first)
    for driver, escaped in second:
        merged[driver] = sorted(set(merged.get(driver, [])) | set(escaped))
    return list(merged.items())


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
#: ``gamma`` are windowed by ``CELL_SAFETY_ANGLE_DEG`` (degrees, absolute),
#: never ``CELL_SAFETY_FRACTION`` (a fraction of Å), so a message built for
#: one and printed for the other names the wrong unit and the wrong window.
_ANGLE_CELL_NAMES = ("alpha", "beta", "gamma")

#: a cell path's phase index, bare or scoped ``hist.h.`` by a joint fit
_CELL_PHASE = re.compile(r"phases\.(\d+)\.cell\.")


def _cell_runaway_diagnostic(
        cell_runaway: list[tuple[str, float, float]],
        unresolved: list[tuple[str, list[str]]] | None = None,
        ) -> Diagnostic | None:
    """``CELL_RUNAWAY`` for one stage's :func:`reset_cell_runaway` and
    :func:`_vars_driven_cell_escapes` findings, or ``None`` when neither
    found anything (the overwhelming majority of stages, including every
    one this package's own suite runs).

    The message names the parameters that left the window, then says what
    happened to their phases' cells: restored and held while the stage solved
    again, or restored after the stage's second solve with nothing after it
    (:class:`CellReset`'s ``held``).  A plain triple reads as an escaped,
    held row.  ``where`` names every restored path, also one that went back
    only with its cell, since none of them is a measurement of this stage.

    ``unresolved`` never says "restored" — the whole point of review of
    #385 finding 1 is that a ``vars.X``-driven escape is *not* reset, so
    the sentence for it says what happened instead: the driver and every
    escaped dependent are named, and that nothing moved.  A stage that fires
    both is one message, not two, since a reader tracing one ``CELL_RUNAWAY``
    code should not have to reassemble it from two diagnostics that differ
    only in which clause fired.
    """
    unresolved = unresolved or []
    if not cell_runaway and not unresolved:
        return None

    def is_angle(path: str) -> bool:
        return path.rsplit(".", 1)[-1] in _ANGLE_CELL_NAMES

    paths = [p for p, _, _ in cell_runaway]
    for driver, escaped in unresolved:
        paths.append(driver)
        paths.extend(escaped)

    sentences = []
    value = None
    if cell_runaway:
        worst = max(cell_runaway, key=lambda t: abs(t[1] - t[2]))
        value = abs(worst[1] - worst[2])

    def _detail(rows):
        return "; ".join(
            f"{p} {old:.6g} -> {new:.6g} {'°' if is_angle(p) else 'Å'}"
            for p, old, new in rows)

    left = [c for c in cell_runaway if getattr(c, "escaped", True)]
    if left:
        has_length = any(not is_angle(p) for p, _, _ in left)
        has_angle = any(is_angle(p) for p, _, _ in left)
        if has_length and has_angle:
            window_clause = (f"±{CELL_SAFETY_FRACTION:.0%} (a/b/c) or "
                             f"±{CELL_SAFETY_ANGLE_DEG:.0f}° (α/β/γ)")
        elif has_angle:
            window_clause = f"±{CELL_SAFETY_ANGLE_DEG:.0f}°"
        else:
            window_clause = f"±{CELL_SAFETY_FRACTION:.0%}"
        sentences.append(
            f"{len(left)} free cell parameter{'' if len(left) == 1 else 's'} "
            f"left {window_clause} of this stage's starting cell during "
            f"solving: {', '.join(p for p, _, _ in left)}")
    held = [c for c in cell_runaway if getattr(c, "held", True)]
    late = [c for c in cell_runaway if not getattr(c, "held", True)]
    for rows, clause in (
            (held, "and held while the stage solved again"),
            (late, "after the stage's second solve, with no solve after it, "
                   "so the stage's other values were fitted beside the "
                   "escaped cell")):
        if not rows:
            continue
        n = len({m.group(1) for p, _, _ in rows
                 if (m := _CELL_PHASE.search(p)) is not None})
        subject = ("The phase's free cell was" if n <= 1 else
                   f"The {n} phases' free cells were")
        sentences.append(
            f"{subject} restored to this stage's starting values {clause} "
            f"(solved -> restored): {_detail(rows)}")
    if unresolved:
        driver_detail = "; ".join(
            f"{driver} drives {', '.join(escaped)} outside its window"
            for driver, escaped in unresolved)
        sentences.append(driver_detail)
        sentences.append(
            f"{'It was' if len(unresolved) == 1 else 'They were'} not "
            f"put back")
    return Diagnostic(
        level="warning", code="CELL_RUNAWAY", where=paths, value=value,
        message=". ".join(sentences) + ".",
        suggestion=(
            "Fix one phase's cell, hold the other free phase, or free the "
            "cell in its own stage away from the degenerate pairing."),
    )


def _released_phases(model: CompiledModel, table: ParameterTable,
                     held: list[str], support: np.ndarray | None = None,
                     reach: dict[str, list[str]] | None = None, *,
                     sigma: float | None = PHASE_SUPPORT_SIGMA) -> list[str]:
    """Of ``held``, the columns whose phase has risen above support since.

    Measured at the values the solve *landed* on, against the same threshold
    the hold was taken at — a phase whose scale climbed while the stage ran is
    now one the data can see, and its parameters are measurable in this stage
    rather than the next one.  ``support`` is :func:`_answer_significance`,
    which measures a held phase with its held columns free (WP-1523), so a held
    cell cannot make the phase look better determined than it would be free.

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

    ``sigma`` is the threshold the hold was taken at, the plan's
    ``phase_support_sigma`` (WP-2002, B1).  ``None`` took no significance
    hold, so there is nothing to release.  A phase with no line in range is
    never released (WP-1958): its count is frozen with the stage's windows,
    so nothing the solve did can have given it one.
    """
    if sigma is None:
        return []
    if support is None:
        support = model.phase_support(table.decode(table.x0()))
    lineless = _lineless_phases(model)
    seen = {ip for ip, s in enumerate(support)
            if s >= sigma and ip not in lineless}
    if not seen:
        return []
    prefixes = tuple(f"phases.{ip}." for ip in sorted(seen))
    reach = reach or {}
    return [p for p in held
            if any(name.startswith(prefixes)
                   for name in (p, *reach.get(p, ())))]


#: ``phases.<i>.`` — the phase a path or a column's reach belongs to.
_PHASE_PREFIX = re.compile(r"^phases\.(\d+)\.")


def _phases_reached(columns: list[str], reach: dict[str, list[str]]) -> set[int]:
    """Every phase a column names or moves — the name, and the hold's reach
    for a ``vars.X`` whose own name carries no phase (WP-1342)."""
    return {int(m.group(1)) for c in columns for name in (c, *reach.get(c, ()))
            if (m := _PHASE_PREFIX.match(name))}


#: An occupancy path.  With :data:`_DISPLACEMENT_PATH` (an anisotropic ADP
#: column reaches the U^ij components it drives, so ``biso|adp`` alone would
#: keep it), the paths a column may move and still be left out of the
#: significance (:func:`_significance_columns`), beside another phase's
#: scale (``_SCALE_PATH``): they rescale a phase's intensities and move no
#: peak.
_OCCUPANCY_PATH = re.compile(r"^phases\.\d+\.atoms\.\d+\.occ$")


def _intensity_only_path(path: str) -> bool:
    return bool(_DISPLACEMENT_PATH.match(path) or _OCCUPANCY_PATH.match(path))


def _significance_columns(free: list[str], held: list[str],
                          reach: dict[str, list[str]], ip: int) -> list[str]:
    """The columns phase ``ip``'s scale significance is marginal over (WP-1523).

    Every free column, and the phase's own held columns, except a column that
    moves only displacements, occupancies and other phases' scales.
    The freedom that inflates a fit to noise is where the peaks sit: a cell, a
    width, a zero shift (Davies, R. B., 1977, *Biometrika* 64, 247-254, a
    nuisance parameter present only under the alternative).  A column that
    only rescales intensities, B or an occupancy, says how the intensity
    splits between it and the scale, not whether the phase is there.
    Marginal over B, a phase whose scale and B nearly share a direction reads
    as absent: measured on ``tests/test_scale_b_ridge.py``'s fluorite, 153.7σ
    on the screen and 0.02σ marginal.

    **Another phase's scale is the same split one rank up**: it says which
    phase carries an intensity, not whether the intensity is there.  Marginal
    over it, two phases able to draw the same pattern each read under 3σ, and
    the hold landed on whichever the start left weaker, the specimen's only
    phase included: issue #219's cubic Cu modelled with an absent ``I 4/m m m``
    subgroup, scales at ρ −1.000, held the parent from 9 of 15 split seeds.
    Conditional on the partner's scale the parent reads 45-90σ there, while
    a phase fitted to noise still reads low, its inflation coming from its
    own cell and widths; on the suite's multi-phase fixtures the two readings
    differ by at most 9 %.  The ambiguity between the pair is
    ``HIGH_CORRELATION``'s to report, which fires on the two scales.

    "Moves only" is read off the column's reach, a variable dropped first, so
    a ``vars.B`` driving two displacements is left out too (WP-1342), and a
    ``vars.S`` tying this phase's scale to another's stays in.
    """
    def moved(column: str) -> list[str]:
        return [p for p in reach.get(column, [column]) if not is_variable_path(p)]

    def other_scale(path: str) -> bool:
        m = _SCALE_PATH.match(path)
        return bool(m) and int(m.group(1)) != ip

    def left_out(column: str) -> bool:
        paths = moved(column)
        return bool(paths) and all(_intensity_only_path(p) or other_scale(p)
                                   for p in paths)

    return [c for c in [*free, *(h for h in held if h not in free)]
            if not left_out(c)]


def _scale_significance(table: ParameterTable, theta: np.ndarray,
                        jac: np.ndarray, columns: list[str], ip: int) -> float:
    """Phase ``ip``'s scale over its esd from (JᵀWJ)⁻¹ on ``columns`` alone.

    **Against counting noise**, as the screen and
    :data:`~rietx.indexing.workflow.ABSENT_SIGMA` are: the covariance carries
    neither √χ²_red nor the Bérar-Lelann factor the reported esds do.  Both
    grow with a misfit anywhere in the pattern, so with them a present phase
    read as absent: measured on two dead channels under LaB₆, 2865σ on the
    screen and 0.23σ by the reported esd (``tests/test_data_support.py``), and
    on CaF₂ held 1.2 % off its cell, 6.74σ against 0.65σ
    (``tests/test_held_phase.py``).  The esd goes through
    ``ParameterTable.stderr_physical`` like a reported one, so a tied or
    transformed scale is propagated the same way.  A scale column with no
    gradient reads 0.
    """
    path = f"phases.{ip}.scale"
    index = {p: k for k, p in enumerate(table.free_paths)}
    idx = np.array([index[c] for c in columns if c in index], dtype=np.intp)
    if not len(idx):
        return 0.0
    # a residual with Σr² = 1 and one degree of freedom is a unit χ²_red, and
    # one nonzero entry has no same-sign run, so a unit Bérar-Lelann factor:
    # ``covariance_estimates`` returns pinv(JᵀWJ) unscaled, through the same
    # equilibration, cut and tiny-column esd (WP-1463) every reported esd takes
    unit = np.zeros(len(idx) + 1)
    unit[0] = 1.0
    sd, corr_sub = covariance_estimates(np.asarray(jac)[:, idx], unit, len(idx))
    n = len(table.free_paths)
    stderr = np.zeros(n)
    stderr[idx] = sd
    corr = np.zeros((n, n))
    corr[np.ix_(idx, idx)] = corr_sub
    esd = table.stderr_physical(theta, stderr, corr).get(path)
    if esd is None or not np.isfinite(esd) or esd <= 0.0:
        return 0.0
    return float(table.decode(theta)[path]) / esd


def _reported_support_sigma(phase_support_sigma: float | None) -> float:
    """The threshold ``PHASE_UNCONSTRAINED`` reports against.

    The plan's ``phase_support_sigma`` where it set one, so the report and the
    hold read one number; the default where the plan switched the hold off
    (WP-2002, B1).  Switching the significance test off lets a weak phase's
    structure refine against nothing (a phase with no line in range is still
    held, scale included), which is the case the diagnostic was written for
    before any hold existed (WP-1110), so it still speaks.
    """
    return PHASE_SUPPORT_SIGMA if phase_support_sigma is None else phase_support_sigma


def _answer_significance(model: CompiledModel, table: ParameterTable,
                         outcome, held: list[str],
                         reach: dict[str, list[str]], backend: str, *,
                         sigma: float = PHASE_SUPPORT_SIGMA) -> np.ndarray:
    """Each phase's significance in σ at a stage's answer (WP-1523).

    The one test of "can the data see this phase", read by the release, the
    collapse and the result's ``PHASE_UNCONSTRAINED``.  A phase is seen when
    its scale is :data:`~rietx.model.forward.PHASE_SUPPORT_SIGMA` of its esds
    from zero (:func:`_scale_significance`), marginal over the columns
    :func:`_significance_columns` names.  A phase with columns in ``held``
    (the support hold's, never the moment or ridge holds) is measured with
    them freed for the measurement and held again, so a held cell cannot make
    the phase look better determined than it would be free.

    The screen ``CompiledModel.phase_support`` comes first.  It is the scale's
    conditional z, which bounds the marginal one, so a phase under it keeps
    the screen value with no Jacobian built.  So does a phase outside
    Rietveld mode (Le Bail and Pawley fix the scale), one whose scale nothing
    refines, and one whose covariance cannot be formed.  The solve's own
    Jacobian is reused unless a held column must be freed; ``set_vary`` can
    decline a row, so only what it freed is held again.

    ``sigma`` is the threshold the readers will compare against: the plan's
    ``phase_support_sigma``, or :data:`~rietx.model.forward.PHASE_SUPPORT_SIGMA`
    where the plan switched the hold off and only ``PHASE_UNCONSTRAINED``
    reads the vector (WP-2002, B1).  Skipping the full test under it is exact
    for every reader, since the screen bounds the full test from above.
    """
    theta = outcome.theta
    out = np.array(model.phase_support(table.decode(theta)), dtype=np.float64)
    if model.mode != "rietveld":
        return out
    moving = set(table.moving_paths)
    seen = [ip for ip in range(len(out)) if out[ip] >= sigma
            and f"phases.{ip}.scale" in moving]
    if not seen:
        return out
    held_of = {ip: [c for c in held if ip in _phases_reached([c], reach)]
               for ip in seen}
    free = list(table.free_paths)
    # the moment angles the solve's covariance left out at a stationary
    # direction (WP-1929) leave this marginal too, or the significance would
    # be read off the matrix the reported esds were not
    stationary = {free[i] for i in stationary_columns(outcome, free)}
    extra = list(dict.fromkeys(c for cs in held_of.values() for c in cs))
    freed = table.set_vary(extra, True) if extra else []
    try:
        th = table.x0()
        if freed or outcome.jac is None:
            jac = np.asarray(_jacobian_for(model, table, backend)(th),
                             dtype=np.float64)
        else:
            jac = np.asarray(outcome.jac, dtype=np.float64)
        column_reach = table.column_reach()
        for ip in seen:
            columns = [c for c in _significance_columns(
                free, [c for c in held_of[ip] if c in freed], column_reach, ip)
                if c not in stationary]
            try:
                # never above the screen it is bounded by: a direction the
                # pinv cut discards reads zero variance, which would inflate z
                out[ip] = min(out[ip],
                              _scale_significance(table, th, jac, columns, ip))
            except np.linalg.LinAlgError:
                pass  # no covariance: the screen stands
    finally:
        if freed:
            table.set_vary(freed, False)
    return out


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


#: whether ``Refinement.__init__`` judges the magnetic groups of what it is given
_JUDGE_GROUPS: ContextVar[bool] = ContextVar("rietx_judge_groups", default=True)


@contextmanager
def _refined_state():
    """Construct a ``Refinement`` from state a fit already moved: not judged.

    A context rather than a keyword so the public signature stays what a
    caller's statement enters through.
    """
    token = _JUDGE_GROUPS.set(False)
    try:
        yield
    finally:
        _JUDGE_GROUPS.reset(token)


def _judge_magnetic_groups(structure: Structure) -> None:
    """Judge every phase's magnetic group against its structure (issue #597).

    The one spelling of the check for the entry points in this module and its
    siblings (``multi``, ``sequential``); a phase with no magnetic group passes.
    """
    for phase in structure.phases:
        check_group_is_structure_symmetry(phase)


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
                 backend: str = "numpy", solver: str = DEFAULT_SOLVER,
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
        # Before the copies below, because what this constructor goes on to
        # read (the declared wavelengths, the specimen absorption) is a
        # wavelength a TOF bank does not carry — so without this the refusal
        # is an AttributeError about a missing attribute rather than a
        # statement about the radiation.
        require_two_theta(None, "Refinement()", instrument=instrument)
        self._backend = backend
        self._solver = solver
        self.structure = structure.model_copy(deep=True)
        #: ``SITE_TWINS_MERGED`` findings a verb has made and no result has
        #: yet carried (#1007): the schema is strict and has no channel, so a
        #: verb that takes a structure in merges its twin sites and the next
        #: ``fit``/``run_stage`` says so (:meth:`_drain_twin_findings`).
        self._twin_findings: list[Diagnostic] = []
        self._merge_twins()
        # A magnetic group has to be a symmetry of the structure it decorates
        # (issue #597).  Judged here, where a statement enters a fit, and not
        # on the schema or at compile: a refined phase whose group-related
        # copies were listed separately (the supercell builder's, a file's)
        # has drifted apart once B, occupancy or coordinates were freed, and
        # must still validate and read back.  The package's own constructions
        # (``branch``, ``_trial``, ``from_node``, a series' later patterns) hand
        # this a structure a fit already moved and run under
        # :func:`_refined_state`: refined state is never re-judged, only a
        # caller's statement is.
        if _JUDGE_GROUPS.get():
            _judge_magnetic_groups(self.structure)
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
        #: The covariance ``result_``'s esds were read off, kept in memory beside
        #: it and never serialized (the Identifiability argument: the Jacobian
        #: does not survive fit time).  ``(result, table, theta,
        #: stderr_internal, correlation)``, the answer-producing stage's own, so
        #: a caller that needs a correlation between two parameters the
        #: top-|ρ| list truncated can take it from the **same** compile as the
        #: σ's it multiplies — never from the run's ``HIGH_CORRELATION``
        #: findings, which keep the worst |ρ| across every stage.  The result
        #: rides in the tuple so a reader can check it holds the covariance of
        #: the result it was handed.  ``None`` until a fit returns, and dropped
        #: with ``result_``.
        self._answer_covariance: tuple | None = None
        #: what :meth:`report` and :meth:`reflection_table` read beside
        #: ``_model``, frozen with ``result_`` (:meth:`_freeze_answer`), and
        #: dropped with it.
        self._answer: dict | None = None
        #: the last ``fit(stage_reports=True)`` run's trajectory, one
        #: :class:`~rietx.report.StageReport` per completed stage (WP-1058).
        #: Empty after a fit that was not asked for one — a report is *derived*
        #: from a result, so it is carried beside ``result_`` rather than
        #: inside it (the arrow's direction is why ``schemas/results.py``
        #: cannot import the report contract at all).
        self.stage_reports_: list[StageReport] = []
        self._model: CompiledModel | None = None
        #: whether ``fit`` and ``run_stage`` compute the profile interval of
        #: each moment angle the stationary-angle test left out of the answer
        #: stage's covariance (WP-2002, B2;
        #: ``parameter_interval.attach_stationary_intervals``).  ``False`` on a
        #: tree the package runs for itself and discards: :meth:`_trial` sets
        #: it, which is also what keeps the interval's own refits from
        #: starting intervals of their own, and so does every package fit
        #: built without one (``strategy.magnetic._fit``).
        self._auto_intervals = True
        #: the two plan settings a stage reads, as the last ``fit`` or
        #: ``run_stage`` ran them (WP-2002, B1): the keywords of
        #: :meth:`run_stage`, so a fit the package runs on the caller's behalf
        #: and discards (the profile interval, the fraction profile, a rival
        #: or verify trial) passes them on with ``**`` and answers under the
        #: hold the caller chose rather than the default.  Set beside
        #: ``result_``, because every such trial reads that result, and
        #: carried by :meth:`_carry_into`, so :meth:`_trial` inherits it.
        #: ``window_area_tol`` is the answer stage's window fraction, a plan's
        #: closing stage's (WP-2002, the sixth round's Q1 and Q2): a trial that
        #: compares its χ² with the fit's must compile the same windows, since
        #: the 2 % and 0.1 % windows of one answer differ by 37-1730 in χ².
        self._plan_settings: dict[str, float | None] = {
            "correlation_guard": CORRELATION_GUARD,
            "phase_support_sigma": PHASE_SUPPORT_SIGMA,
            "window_area_tol": None}

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
        #: whether ``_free_paths`` is a declaration.  Until something declares a
        #: free set (``set_vary``, a hold or tie edit, a stage) the models' own
        #: ``vary`` flags are the caller's declaration; afterwards the list is,
        #: **including when it is empty**.  Read from the list alone, holding
        #: the last free path would hand the decision back to the model flags
        #: and resurrect every parameter the caller had just fixed.
        self._free_set_declared = False
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
        #: the pattern the last fit or stage was given, every measured point
        #: included, for :meth:`write_cif`'s pattern block (WP-1933)
        self._fit_pattern: PatternData | None = None

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
        self._answer_covariance = None
        self._answer = None
        self.stage_reports_ = []

    def _freeze_answer(self) -> dict:
        """What :meth:`report` and :meth:`reflection_table` read, beside ``_model``.

        Taken when the result is built, because the models are the working
        state and the result is not: a later fit that is cancelled keeps the
        stages it completed and the previous result, and a view that read the
        live models then would pair those values with this result's model
        (WP-1421; the joint fit's ``MultiHistogramRefinement._freeze_answer``).
        """
        table = ParameterTable(self.structure, self.instrument)
        # the model's moment frames are the last stage's, not this table's (#598)
        table.pull_moment_frames(self._model)
        return {"values": table.decode(table.x0()),
                "structure": self.structure.model_copy(deep=True),
                "instrument": self.instrument.model_copy(deep=True),
                "held": list(self._held),
                "free_paths": list(self._free_paths)}

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
            free_declared=self._free_set_declared,
            two_theta_limits=self._two_theta_limits,
            reflections=_extract_reflections(model or self._model),
            ties={p: s.model_copy(deep=True) for p, s in self._ties.items()},
            variables={n: v.model_copy(deep=True)
                       for n, v in self._variables.items()},
            holds=sorted(self._user_holds),
        )

    def _record(self, tree: RefinementTree, action: NodeAction, model: CompiledModel,
                table: ParameterTable, outcome, diagnostics,
                held_scales: set[int] | None = None,
                window_loss: float | None = None) -> str:
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
            stderr=stderr, held_scale_phases=sorted(held_scales or ()),
            window_loss=window_loss)
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
        self._restore_state(node.state)
        self._head_id = node.id
        tree.set_head(node.id)
        return self

    def _merge_twins(self) -> None:
        """Put every twin site of the working structure on its special position.

        The one call every verb that brings a structure in makes
        (construction, :meth:`edit`, :meth:`set_values`, :meth:`checkout`):
        ``Phase`` validation is strict and moves nothing, and a coordinate
        assigned after a phase was built never re-validates it.  What moved is
        held in ``_twin_findings`` for the next result.
        """
        before = self.structure
        found: list[Diagnostic] = []
        self.structure = merge_site_twins(self.structure, diagnostics=found)
        self._carry_twin_moves(numbering_moves(before, self.structure), found)
        self._twin_findings.extend(found)

    def _carry_twin_moves(self, moves: dict, found: list[Diagnostic]) -> None:
        """Carry holds, user ties and free paths through the DOF renumbering of a merge.

        A site whose symmetry changes (onto or off a special position) renumbers
        its coordinate DOFs, so a hold on ``dof.1`` (y on the general position)
        would read z on the mirror and keep the wrong coordinate fixed with
        nothing saying so.  Each register
        follows its DOFs (:func:`~.crystallography.twins.carry_constraints`;
        a hold onto the coupled direction where the position couples
        coordinates), and what cannot follow is dropped and named in the
        site's ``SITE_TWINS_MERGED`` message.
        """
        if "_user_holds" not in self.__dict__:
            return            # construction: no constraint has been declared yet
        sites = sorted({path.rsplit(".dof.", 1)[0] for path in moves})
        for site in sites:
            site_moves = {p: m for p, m in moves.items()
                          if p.rsplit(".dof.", 1)[0] == site}
            holds, ties, free, notes = carry_constraints(
                site_moves, holds=sorted(self._user_holds), ties=self._ties,
                free_paths=self._free_paths)
            self._user_holds = set(holds)
            self._ties = ties
            self._free_paths = free
            self._held = [new for p in self._held
                          if (new := (site_moves[p][0] if p in site_moves else p))]
            if not notes:
                continue
            # the findings and the paths the caller sees read the new numbering
            site = moves.new_site(site) if isinstance(moves, NumberingMoves) else site
            for n, d in enumerate(found):
                if d.code == "SITE_TWINS_MERGED" and d.where == [site]:
                    found[n] = d.model_copy(update={
                        "message": d.message + " Constraints: "
                        + "; ".join(notes) + "."})
                    break
            else:
                found.append(Diagnostic(
                    level="warning", code="SITE_DOFS_RENUMBERED", where=[site],
                    message=(f"site {site} changed its site symmetry, so its coordinate "
                             f"directions were renumbered: " + "; ".join(notes)
                             + "."),
                    suggestion="check the holds and ties on this site's "
                               "coordinates against parameters()."))

    def _drain_twin_findings(self) -> list[Diagnostic]:
        """The merges no result has reported yet; each is reported once."""
        out, self._twin_findings = self._twin_findings, []
        # a site left as stored is found again by every verb that follows
        return list({(d.code, tuple(d.where), d.message): d for d in out}.values())

    def _restore_state(self, state: RefinementState) -> None:
        """Make ``state`` the working state; ``checkout`` and keep-best share it.

        Whether its free set is a declaration (``_free_set_declared``) is the
        state's own ``free_declared``; a non-empty set always is one, which is
        what a document written before the field meant.
        """
        self.structure = state.structure.model_copy(deep=True)
        self.instrument = state.instrument.model_copy(deep=True)
        self._mode = state.mode
        self._two_theta_limits = state.two_theta_limits
        self._free_paths = list(state.free_paths)
        self._free_set_declared = bool(state.free_paths) or state.free_declared
        # the node's free set is the declared one (``_record_free_paths``), so
        # a checkout starts with no hold and the next stage takes its own
        self._held = []
        self._ties = {p: s.model_copy(deep=True) for p, s in state.ties.items()}
        self._variables = {n: v.model_copy(deep=True)
                           for n, v in state.variables.items()}
        # unlike ``_held`` above, a user hold is restored: it is a declaration
        # the node recorded, and a checkout that dropped it would hand back a
        # state whose pin had quietly expired (WP-1435)
        self._user_holds = set(state.holds)
        self._pending_reflections = [r.model_copy(deep=True) for r in state.reflections]
        self._merge_twins()
        self._invalidate_fit()

    def branch(self, node_id: str | None = None) -> "Refinement":
        """A second working tree over the same history, for a rival strategy."""
        tree = self._require_history()
        with _refined_state():
            ref = Refinement(self.structure, self.instrument,
                             backend=self._backend, solver=self._solver,
                             history=tree)
        self._carry_into(ref)
        ref._head_id = self._head_id
        if node_id is not None:
            ref.checkout(node_id)
        return ref

    def _trial(self, *, record: bool = True) -> "Refinement":
        """A private working tree for a fit the *package* runs, never the caller's.

        :meth:`branch` where there is a history to branch, and otherwise a
        history-free ``Refinement`` over copies of the same models carrying the
        same declarations — the one builder both paths share, so a trial run
        on a caller who disabled history answers the caller's question and not
        a looser one (before WP-1320 that path copied only the free set, and a
        user tie or a named variable fell off it).  ``record=False`` takes the
        history-free path even where there is a history, for a trial whose
        stages the caller's tree should not gain nodes from.

        A trial computes no automatic profile interval (``_auto_intervals``,
        WP-2002): the package discards its result, and the interval's own
        refits are trials.
        """
        if self.history is not None and record:
            ref = self.branch()
        else:
            with _refined_state():
                ref = Refinement(self.structure, self.instrument,
                                 backend=self._backend, solver=self._solver,
                                 history=False)
            self._carry_into(ref)
        ref._auto_intervals = False
        return ref

    def _carry_into(self, ref: "Refinement") -> None:
        """Copy this working tree's declarations onto a fresh ``ref``."""
        ref._mode = self._mode
        ref._two_theta_limits = self._two_theta_limits
        ref._free_paths = list(self._free_paths)
        ref._free_set_declared = self._free_set_declared
        ref._ties = {p: s.model_copy(deep=True) for p, s in self._ties.items()}
        ref._variables = {n: v.model_copy(deep=True)
                          for n, v in self._variables.items()}
        # a rival strategy inherits the caller's declarations, as it inherits
        # the ties: a branch is a second working tree, and a hold the branch
        # dropped would make the two rivals answer different questions
        ref._user_holds = set(self._user_holds)
        ref._pending_reflections = [r.model_copy(deep=True) for r in self._pending_reflections]
        # and the settings the last fit ran under, so a trial's refits hold
        # an absent phase by the caller's rule (WP-2002, B1)
        ref._plan_settings = dict(self._plan_settings)
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
        # ``ref`` was built from this structure and merged it on construction,
        # before it held any constraint; they follow its DOFs now
        ref._carry_twin_moves(numbering_moves(self.structure, ref.structure),
                              ref._twin_findings)

    def edit(self, *, structure: Structure | None = None,
             instrument: Instrument | None = None, label: str = "") -> str | None:
        """Record a change to the model itself, such as adding an impurity phase,
        raising the background order or swapping the geometry.

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
        # Refused before anything is touched: a bank's table builds without
        # error, so nothing later stops the edit, and by then the structure,
        # the ties and the holds have moved (WP-1035's half-applied edit).
        if instrument is not None:
            require_two_theta(None, "Refinement.edit()", instrument=instrument)
        candidate = self.structure if structure is None else structure
        # a proposed structure meets the twin merge before its table is built,
        # since moving a site changes the symmetry its table is checked against
        merged: list[Diagnostic] = []
        if structure is not None:
            candidate = merge_site_twins(candidate, diagnostics=merged)
        # No magnetic-group judgement here: ``edit`` receives refined state
        # plus one change (the GUI's funnel for every model edit), which is the
        # case :func:`_refined_state` exists for (issue #597).
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
        self._carry_twin_moves(numbering_moves(self.structure, candidate), merged)
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
            self.structure = candidate.model_copy(deep=True)
            self._twin_findings.extend(merged)
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

    def fix_special_positions(self) -> list[str]:
        """Set ``vary=False`` on every coordinate of a fully fixed special position.

        A ``vary=True`` coordinate on an atom whose site symmetry allows no
        positional freedom (``F d -3 m`` 8a, ``P n m a`` inversion centres, …) is
        refused when the parameter table is first built, at the first
        :meth:`parameters` or :meth:`fit`, and the refusal names only the first
        such atom.  After a step that frees "every coordinate" of a structure
        holding special and general sites together, this is the one call that
        makes it fittable: it clears the flag on exactly those coordinates,
        records one ``edit_model`` node, and returns their paths, sorted.  Atoms
        with any free direction are untouched, and a structure with nothing to
        fix returns ``[]`` and records nothing.  Opt-in: construction and
        ``fit()`` still refuse, as before.
        """
        from .crystallography.symmetry import resolve_group
        from .crystallography.wyckoff import coordinate_basis, stabilizer_rotations

        structure = self.structure.model_copy(deep=True)
        cleared: list[str] = []
        for ip, phase in enumerate(structure.phases):
            sg = resolve_group(phase.space_group, phase.symmetry_operations)
            for ia, atom in enumerate(phase.atoms):
                xyz = [atom.x.value, atom.y.value, atom.z.value]
                if len(coordinate_basis(stabilizer_rotations(sg, xyz))) > 0:
                    continue
                for axis in ("x", "y", "z"):
                    param = getattr(atom, axis)
                    if param.vary:
                        param.vary = False
                        cleared.append(f"phases.{ip}.atoms.{ia}.{axis}")
        if cleared:
            self.edit(structure=structure, label="fix_special_positions")
        return sorted(cleared)

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
        if self._free_paths or self._free_set_declared:
            return self._prepare_table(restore=True)
        table = ParameterTable(self.structure, self.instrument)
        self._declare_variables(table)
        self._apply_ties(table)
        self._apply_holds(table)
        return table

    def __str__(self) -> str:
        """What this refinement holds, read off its fields: phases, mode, the
        last fit's status and the parameters that vary (WP-1544).

        Never :meth:`summary`, which builds a report and can run fits: a
        notebook calls this for every cell that displays the refinement.
        """
        from ._display import refinement_text
        return refinement_text(self)

    def _repr_pretty_(self, p, cycle) -> None:
        p.text(str(self))

    def parameters(self, *, mode: Mode | None = None) -> list[ParameterRow]:
        """Every parameter as data, with fixed, locked and tied rows included.

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
        owned = table.body_rows()
        origin = table.origin_holds
        rows = []
        for e in table.entries:
            rows.append(ParameterRow(
                path=e.path, value=e.value, vary=e.vary, lo=e.lo, hi=e.hi,
                tie=(TieSpec._from_tie(e.tie, user=e.path in self._applied_ties)
                     if e.tie is not None else None),
                locked=e.locked,
                held=e.held,
                esd=esd.get(e.path),
                mode_fixed=(mode_fixed_column(reach[e.path], mode)
                            if e.path in reach
                            else mode_fixed_path(e.path, mode)),
                needs_held_cell=e.path in blocked,
                body=owned.get(e.path),
                origin_axis=origin[e.path][1] if e.path in origin else None,
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
            #
            # Who holds it is the table's answer (``held_by``), so the table's
            # own floating-origin hold is refused exactly as the caller's is.
            by_path = {e.path: e for e in table.entries}
            blocked = [g for g in globs
                       if is_literal_path(g) and g in by_path
                       and by_path[g].tie is None and not by_path[g].locked
                       and table.held_by(g) is not None]
            if blocked and table.held_by(blocked[0]) == "origin":
                raise ValueError(
                    f"{blocked[0]!r} is held to fix its phase's floating origin "
                    "(Phase.floating_origin) and cannot be freed; unhold it "
                    "first if you mean to refine it, which withdraws that "
                    "phase's declaration")
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
        self._free_set_declared = True
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
        # a value set next to its own image is the twin case #1007 describes
        self._merge_twins()
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

        Bounds come straight off the caller's ``Parameter``, which is what
        makes a variable and the model parameter it replaces produce the
        identical :class:`~rietx.params.vector.Entry`.
        """
        for name, prm in self._variables.items():
            table.add_parameter(f"{VAR_PREFIX}{name}", prm.value, vary=prm.vary,
                                lo=prm.min, hi=prm.max, unit=prm.unit)

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
        before = coordinate_snapshot(self.structure)
        table.apply_to_models(self.structure, self.instrument)
        # a coordinate written within reach of a special position renumbers
        # its DOFs, and the constraints must follow wherever it was written
        # (#1014, round 5)
        self._carry_twin_moves(numbering_moves(before, self.structure),
                               self._twin_findings)
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
                tie = AffineTie(terms=tuple((p, float(c)) for p, c in spec.terms),
                                const=float(spec.const))
                refused = table.tie_source_refusal(tie)
                if refused is not None:
                    # a later model edit locked (or derived) the source, or a
                    # row its own tie rests on: the tie cannot move the target
                    # any more, and ``set_tie`` would raise, stopping a build a
                    # model edit must not stop
                    dropped.append(_tie_refusal_text(path, refused))
                    continue
                table.set_tie(path, tie)
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

        ``min``/``max`` are the declaration that matters.  A variable is a
        :class:`~rietx.schemas.common.Parameter`, and the table reads an
        entry's bounds straight off one — so a variable declared like the model
        parameter it replaces is **indistinguishable** to the fit, which is the
        property that makes this a renaming rather than a new degree of
        freedom.  Declared unlike it, it is a different problem: a width
        whose variable leaves out ``min=0.0`` may refine below zero.

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
        prm = Parameter(value=value, vary=vary, min=min, max=max, unit=unit)
        path = f"{VAR_PREFIX}{name}"
        # the table is the authority on collisions: add_parameter raises on a
        # path that already exists, and probing one here means the refusal
        # happens before the register is touched
        self._working_table().add_parameter(
            path, prm.value, vary=prm.vary, lo=prm.min, hi=prm.max,
            unit=prm.unit)
        self._variables[name] = prm
        if prm.vary and (self._free_paths or self._free_set_declared):
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
        # a body owns its atoms' coordinates as symmetry owns a special
        # position, and the hold that means anything is on the body's own
        # DOFs (WP-1805's record); a glob sweeping body rows is refused too,
        # since holding half of what it names would be a silent partial hold
        owned = table.body_rows()
        if blocked := [p for p in hits if p in owned]:
            names = sorted({owned[p] for p in blocked})
            raise ValueError(
                f"cannot hold {blocked[0]!r}"
                + (f" and {len(blocked) - 1} more" if len(blocked) > 1 else "")
                + f": placed by rigid body {names[0]!r}; hold the body's own "
                "origin, rotation and torsions instead "
                "(phases.*.rigid_bodies.*.origin.dof.*, "
                "phases.*.rigid_bodies.*.rotation.*, "
                "phases.*.rigid_bodies.*.torsions.*.twist)")
        new = [p for p in hits if p not in self._user_holds]
        if not new:
            return []
        self._user_holds.update(new)
        table.set_held(new, True)
        self._commit_hold_edit(table, held=new, unheld=[])
        return new

    def hold_floating_origin(self) -> list[Diagnostic]:
        """Fix the origin of every phase whose space group lets it float.

        In a polar group (P 6₃ m c, P 4 m m, Pna2₁, Cc, P 1, …) every atom has
        a free coordinate along the polar axis, and shifting the whole structure
        along it changes no intensity, so a fit that frees them all has a flat
        direction it walks and quotes an esd along (``FLAT_DIRECTION``, ρ = −1).
        This sets ``Phase.floating_origin = "hold"`` on each phase whose group
        floats (:func:`~rietx.crystallography.wyckoff.floating_origin_basis`)
        and records one ``edit_model`` node.  The parameter table then holds,
        per floating direction, the first atom's displacement DOF that a shift
        along it moves, so a plan that frees ``phases.*.atoms.*.dof.*``
        leaves that atom where it is and the other atoms' coordinates are
        quoted relative to it.  The same as setting the field yourself: since
        WP-1912 the table does the holding, so a series pattern, a joint
        histogram and a history replay hold the same atom.

        Opt-in: nothing is held unless this is called or the field is set.
        :meth:`unhold` on a held DOF takes it back, with the rest of that
        phase's fix.  A direction the caller's own ties or holds already fix
        gets no second hold.  The alternative is a least-squares restraint on
        a weighted centroid of the sites along the axis, which keeps an esd on
        every atom (Flack & Schwarzenbach, 1988, Acta Cryst. A44, 499):
        ``Phase.floating_origin = "centroid"``, set on the phase rather than
        through this verb, which leaves a phase already declaring either alone.

        A phase where the table would hold nothing is left undeclared: its
        origin is fixed already by the caller's own ties or holds, or no DOF
        the shift moves is free to hold.  So every declaration this sets holds
        something :meth:`unhold` can name.  A declaration set by hand that
        holds nothing is withdrawn with :meth:`edit`.

        Returns what the table holds: one ``ORIGIN_FIXED_ON_POLAR_AXIS``
        (info) per phase that needed a hold, naming the held parameters in
        ``where``, and an ``ORIGIN_NOT_FIXED`` (warning) where a direction has
        no untied DOF to hold, so the flat direction is still there.  A
        structure with no polar phase returns ``[]`` and records nothing.
        """
        from .crystallography.symmetry import resolve_group
        from .crystallography.wyckoff import floating_origin_basis

        structure = self.structure.model_copy(deep=True)
        declared: list[int] = []
        for ip, phase in enumerate(structure.phases):
            if phase.floating_origin is not None:
                continue
            sg = resolve_group(phase.space_group, phase.symmetry_operations)
            if len(floating_origin_basis(sg)) > 0:
                phase.floating_origin = "hold"
                declared.append(ip)
        if not declared:
            return _origin_diagnostics(self._working_table())
        probe = self._table_for(structure)
        holding = {ip for ip, _ in probe.origin_holds.values()}
        for ip in declared:
            if ip not in holding:
                structure.phases[ip].floating_origin = None
        if holding & set(declared):
            self.edit(structure=structure, label="hold_floating_origin")
        return _origin_diagnostics(probe)

    def _table_for(self, structure: Structure) -> ParameterTable:
        """A table over ``structure`` with this refinement's ties and holds.

        What a fresh :meth:`_working_table` would be for a model not yet
        adopted, for a verb that has to ask the table before it records
        anything (:meth:`hold_floating_origin`).  :meth:`edit` builds the same
        one over the model it accepts.
        """
        table = ParameterTable(structure, self.instrument)
        self._declare_variables(table)
        self._apply_ties(table)
        self._apply_holds(table)
        return table

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

        A DOF the table holds to fix a floating origin (``Phase.floating_origin``,
        WP-1912) is released by setting that field back to ``None``, recorded
        as an ``edit_model`` node.  That takes back the phase's whole fix, so
        unholding one of P 1's three held DOFs releases all three, and all three
        are returned.  Only the table's own hold does that.  A caller's hold on
        a DOF the fix would otherwise take is the caller's alone: this lifts it,
        the declaration stays, and the fix holds that DOF again, which its
        ``held_because`` then says.  Which of the two holds a path is
        ``ParameterTable.held_by``'s answer.
        """
        globs = [path_globs] if isinstance(path_globs, str) else list(path_globs)
        table = self._working_table()
        hits = sorted(p for p in self._user_holds
                      if any(fnmatch.fnmatchcase(p, g) for g in globs))
        # A floating-origin hold is the table's, from the phase's own
        # declaration (WP-1912), so it is lifted by taking that declaration
        # back: per phase, since the table re-derives the whole fix at the next
        # build and a register of exceptions would be a second authority.
        origin = table.origin_holds
        released = {ip for p, (ip, _) in origin.items()
                    if table.held_by(p) == "origin"
                    and any(fnmatch.fnmatchcase(p, g) for g in globs)}
        origin_hits = sorted(p for p, (ip, _) in origin.items() if ip in released)
        literals = [g for g in globs
                    if is_literal_path(g) and g not in hits
                    and g not in origin_hits]
        if literals:
            glob = literals[0]
            raise ValueError(
                f"{glob!r} is not held by this refinement"
                if any(e.path == glob for e in table.entries)
                else f"unknown parameter path: {glob!r}")
        if not hits and not origin_hits:
            return []
        if hits:
            # the register first, then the same table: ``set_held`` re-runs the
            # origin fix, so a DOF it takes over shows as held in the node
            self._user_holds.difference_update(hits)
            table.set_held(hits, False)
            self._commit_hold_edit(table, held=[], unheld=hits)
        if origin_hits:
            # released fixed, as a user hold is: a DOF free before the field was
            # set must not come back free when the next table restores the set
            self._free_paths = [p for p in self._free_paths
                                if p not in origin_hits]
            structure = self.structure.model_copy(deep=True)
            for ip in released:
                structure.phases[ip].floating_origin = None
            self.edit(structure=structure, label="unhold: floating origin")
        return sorted(set(hits) | set(origin_hits))

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
        self._free_set_declared = True
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
        before = {e.path: e.value for e in table.entries}
        for path, (terms, offset) in spec.items():
            table.set_tie(path, AffineTie(terms=tuple(terms), const=offset))
        # The target's own bounds are checked above; a displacement DOF has
        # none, and the bound it breaks is on the coordinate its symmetry
        # tie reaches.  Found here, in this verb's voice and naming what the
        # caller wrote, rather than at the model write-back (#246).
        table.refresh_ties()
        broken = [e for e in table.entries if e.value != before[e.path]
                  and not (e.lo <= e.value <= e.hi)]
        if broken:
            e = broken[0]
            wrote = "; ".join(
                f"{p} to {_tie_text(AffineTie(terms=tuple(t), const=o))}"
                for p, (t, o) in spec.items())
            more = f" ({len(broken)} parameters in all)" if len(broken) > 1 else ""
            raise ValueError(
                f"tying {wrote} implies {e.path}={e.value:g}"
                f"{self._owner_label(e.path)}, outside its bounds "
                f"[{e.lo:g}, {e.hi:g}]{more}; loosen that bound or change "
                "the tie")
        previous = dict(self._ties)
        self._ties.update(specs)
        try:
            self._commit_tie_edit(table, ties=specs, untied=[])
        except BaseException:
            # a refused tie must not stay registered: the call reported
            # failure, and a retry would meet "already follows" (#246)
            self._ties = previous
            raise
        return list(spec)

    def _owner_label(self, path: str) -> str:
        """`` (atom O1 of phase X)`` for an atom's path, else ``""``."""
        parts = path.split(".")
        if len(parts) > 3 and parts[0] == "phases" and parts[2] == "atoms":
            try:
                phase = self.structure.phases[int(parts[1])]
                return f" (atom {phase.atoms[int(parts[3])].label} of phase {phase.name})"
            except (ValueError, IndexError):
                pass
        return ""

    def _commit_tie_edit(self, table: ParameterTable, *,
                         ties: dict[str, TieSpec], untied: list[str]) -> None:
        """Land a tie edit: values follow, models are written, a node is added."""
        table.refresh_ties()  # a new dependent takes its source's value at once
        self._write_back(table)
        self._free_paths = list(table.free_paths)
        self._free_set_declared = True
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

        Surface roughness on its floor and a Stephens block at S ≡ 0 are
        probed from their stage's seed (``seeded=True``, ``seed_value`` says
        from where).  A width on its floor is probed where it is, from its
        physical column (``strategy.suggest`` has the measurement).  The
        seeds live in a **second** build whose only
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
        require_two_theta(data, "Refinement.suggest()",
                          instrument=self.instrument)
        from .strategy.suggest import (
            SUGGEST_SEED_ROUGHNESS,
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
            # A wavelength first, while the cell is still held: ``set_vary``
            # declines one beside a free cell, and the probe frees a held
            # cell as a candidate too, so in one call the wavelength was
            # neither scored nor reported (WP-2002, found when Le Bail began
            # to offer it).  Each candidate is scored alone against the free
            # set, where the cell is held, so this is the gain it would have.
            lam = set(table._wavelength_paths())
            table.set_vary([p for p in cand_paths if p in lam], True)
            table.set_vary([p for p in cand_paths if p not in lam], True)

        from .optimize.least_squares import _jacobian_for, _make_residual

        n_data = [0]
        blocks = [()]

        def probe():
            """Compile the table's state on model copies; return (jac, resid)."""
            structure = self.structure.model_copy(deep=True)
            instrument = self.instrument.model_copy(deep=True)
            table.apply_to_models(structure, instrument)
            # at the windows the last answer was measured on: a closing
            # stage's (WP-2002), or the 2 % truncation reads as a gain on
            # every width and background candidate at a converged fit
            model = compile_model(structure, instrument, data, mode=mode,
                                  two_theta_limits=limits,
                                  moving_paths=set(table.moving_paths),
                                  window_area_tol=recorded_window_tol(
                                      self._plan_settings["window_area_tol"]))
            # a "centroid" phase's origin rows, or the probe's covariance
            # reads the floating origin as a flat direction (WP-1912)
            model.origin = compile_origin(model, table)
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
            blocks[0] = row_layout(model)
            return (_jacobian_for(model, table, self._backend)(x0),
                    _make_residual(model, table)(x0))

        # build 1 — the honest current state: residual, free block, and every
        # candidate column whose physical derivative is quotable there
        jac, resid = probe()
        blocks_now = blocks[0]
        fp = table.free_paths

        # build 2 — two kinds of floor candidate only.  A Stephens block at
        # S ≡ 0 (√'s unbounded slope) and Suortti roughness at b = 0 (the
        # identity) are scored from the seeded state a stage would start such
        # a solve at, so those columns (and only those) come from build 2.
        # A width on its floor stays in build 1.  Its column there is the
        # physical one (WP-1938), and probed from a 1e-3 seed it led the list
        # with gains no refit realised (``strategy.suggest`` has the numbers).
        seeded: dict[str, float] = {}
        rough = [p for p in cand_paths
                 if p.startswith("instrument.geometry.surface_roughness.")]
        for p in table.seed_floored(rough, SUGGEST_SEED_ROUGHNESS):
            seeded[p] = SUGGEST_SEED_ROUGHNESS
        strain = [p for p in cand_paths if ".microstrain.dof." in p]
        entries = {e.path: e for e in table.entries}
        for p in table.seed_stephens(strain, SUGGEST_SEED_STEPHENS):
            seeded[p] = entries[p].value
        if seeded:
            jac2, _ = probe()
            for i, p in enumerate(fp):
                if p in seeded:
                    _copy_seeded_column(jac, jac2, i, blocks_now, blocks[0], p)
        free_idx = [i for i, p in enumerate(fp) if p in free_before]
        # in Pawley mode the intensity block co-refines with anything, so it
        # belongs to the free block, not to the candidates
        free_idx += list(range(len(fp), jac.shape[1]))
        candidates = [
            Candidate(path=p, index=i, seeded=p in seeded,
                      seed_value=seeded.get(p))
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

    def profile_fraction(self, data: PatternData, phase: int | str, *,
                         axes: "list[str] | None" = None,
                         fwhm: "list[float] | None" = None) -> "FractionProfile":
        """Every weight fraction of ``phase`` the pattern admits along its width.

        The QPA esd is the curvature of χ² where the fit stopped, so it
        describes one basin.  A trace phase's scale trades against its width
        until its peaks are background, and that ridge can hold several basins
        at one χ²: issue #203 measured 1.41 ± 0.65 wt% on a pattern admitting
        0 %, ~1.5 % and 98.7 % within 0.011 pp of Rwp, with nothing flagged.
        This pins each of the phase's width terms (``axes``; by default every
        one of ``lor_strain``, ``lor_size``, ``gauss_strain``, ``gauss_size``
        free in the last fit) on a grid of FWHM, refits everything else from
        the previous point, and reads the fraction and the data's χ² at each.

        ``fwhm`` is the grid as the phase's own FWHM contribution in degrees 2θ
        at the middle of the fitted range; the default is 0 and then
        :data:`~rietx.schemas.fraction.FRACTION_PROFILE_N_FWHM` log-spaced
        values up to half the fitted span.  A point is admissible within
        Δχ² = 3.84 × χ²_red × f² of the lowest χ² found, f the fit's
        ``esd_inflation`` — the calibration every esd carries, so on one
        quadratic basin the range reproduces W ± 1.96 esd.  The answer
        (:class:`~rietx.schemas.fraction.FractionProfile`) carries the grid,
        the admissible range, and a ``QPA_FRACTION_RANGE`` info record
        stating it and how far its farthest fraction lies from the fit's, in
        the esd's 95 % half-widths.

        Opt-in and read-only: it costs one refit per grid point per axis (12
        each by default), all on a branch with ``telemetry=False``, so the
        working state and ``result_`` are untouched and the history's HEAD is
        put back where it stood.  Rietveld mode only, and
        a fit must have run.  Why the axis is the width and not the scale is
        :mod:`rietx.strategy.fraction_profile`'s docstring.
        """
        require_two_theta(data, "Refinement.profile_fraction()",
                          instrument=self.instrument)
        from .strategy.fraction_profile import profile_fraction

        return profile_fraction(self, data, phase, axes=axes, fwhm=fwhm)

    def profile_interval(self, data: PatternData, path: str, *,
                         level: float = PARAMETER_INTERVAL_LEVEL,
                         max_refits: int = PARAMETER_INTERVAL_MAX_REFITS
                         ) -> "ParameterInterval":
        """The profile-likelihood interval for one parameter of the last fit.

        An esd read as an interval is symmetric, and on a bound it is not an
        interval at all: an estimate there has no symmetric sampling
        distribution (Self & Liang, 1987).  A row the fit left on its bound
        keeps its value and its marginal esd and reads
        ``RefinedParameter.at_bound`` (``FLOOR_HIT`` on a floor of 0), and
        this is the number to quote for it.  It pins ``path`` at a value,
        refits everything the last fit freed, and reads the data's χ² there;
        the ends are where that χ² has risen by a threshold (Venzon &
        Moolgavkar, 1988).

        A row on its bound gets a **one-sided** interval: the bound is one
        end, and the other is at Δχ² = 2.71 × χ²_red × f² at 95 %.  Any other
        row gets a two-sided one at Δχ² = 3.84 × χ²_red × f², f the fit's
        ``esd_inflation``, so on a quadratic profile its ends are the value ±
        1.96 esd.  ``level`` sets both quantiles.  Each side steps outward by
        1, 2, 4, … esd to bracket its end and solves it to a thousandth of an
        esd, refitting each pinned value until its χ² stops falling; a side
        that reaches the parameter's own limit first reports the limit as its
        end.  ``max_refits`` caps each side, and a side that runs
        out says so rather than guessing.  The answer
        (:class:`~rietx.schemas.interval.ParameterInterval`) carries every
        refit, and ``fit_is_minimum`` is ``False`` when one found χ² below the
        fit's.

        A moment angle the fit's covariance left out at a direction the
        symmetry fixes (``MOMENT_ANGLE_STATIONARY``, WP-1929) has no esd and
        still has an interval.  It is two-sided, and it steps from the
        angle's half-width in ``StageResult.moment_angle_tests``: the distance
        either side at which χ², everything else held, rises by χ²_red·f².
        ``fit`` and ``run_stage`` already compute it at the default level, on
        a copy of the models, and store it on the row
        (``RefinedParameter.interval``, WP-2002); this call repeats those
        refits, on a branch.

        Opt-in and read-only: 6-30 refits a side as measured, all on a branch
        with ``telemetry=False``, so the working
        state and ``result_`` are untouched and the history's HEAD is put back
        where it stood.  A fit must have run, and ``path`` must have been free
        in it; a tied, locked or fixed path is refused with the reason.  Why
        the bound changes the threshold is
        :mod:`rietx.strategy.parameter_interval`'s docstring (WP-1929).
        """
        from .strategy.parameter_interval import profile_interval

        return profile_interval(self, data, path, level=level,
                                max_refits=max_refits)

    @classmethod
    def from_node(cls, tree: RefinementTree, node_id: str, *,
                  backend: str = "numpy", solver: str = DEFAULT_SOLVER) -> "Refinement":
        """Open a refinement positioned at an existing checkpoint."""
        node = tree[node_id]
        with _refined_state():
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
        budget, and the absent-phase threshold and correlation guard it ran
        at) — not the recorded parameter values — and executes it from
        here, exactly like ``git cherry-pick`` replays a commit's diff.  This
        is the enabling verb for reusing a refined strategy on a different
        branch (and, in v0.5, on a different sample via
        ``SequentialRefinement``).
        """
        require_two_theta(data, "Refinement.cherry_pick()",
                          instrument=self.instrument)
        tree = self._require_history()
        node = tree[node_id]
        if node.action.kind != "stage":
            raise ValueError(
                f"{node.id} records a {node.action.kind!r} action; only stage "
                "nodes can be cherry-picked")
        # the node's own numbers, an explicit 0 included: ``NodeAction``
        # carries the frozen 100 and 3 for a node written before the fields
        stage = Stage(node.action.name or "cherry-pick",
                      list(node.action.turn_on),
                      max_iter=node.action.max_iter,
                      lebail_cycles=node.action.lebail_cycles,
                      seed=node.action.seed, strain_seed=node.action.strain_seed,
                      restraint_weight_scale=node.action.restraint_weight_scale,
                      ftol=node.action.ftol,
                      window_slack_deg=node.action.window_slack_deg)
        # and the plan settings the stage ran under, which are run_stage's
        # keywords rather than the Stage's (WP-2002, B1): the 3σ and 0.98 for
        # a node written before the fields
        return self.run_stage(
            data, stage, correlation_guard=node.action.correlation_guard,
            phase_support_sigma=node.action.phase_support_sigma,
            # a declared stage's record says None and ran at the declared 2 %,
            # which run_stage's own None no longer is (the seventh round's Q1)
            window_area_tol=recorded_window_tol(node.action.window_area_tol))

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
            # a held path is declined, whoever holds it (``held_by``: the
            # caller, or the floating-origin fix, WP-1912), so it is not a
            # vanished parameter; the register is asked too, for a held path
            # the model no longer has
            missing = [p for p in self._free_paths
                       if p not in self._ties and p not in self._user_holds
                       and table.held_by(p) is None
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
        self._free_set_declared = True

    @contextmanager
    def _abandon_on_cancel(self, cancel, stage_name: str, completed: list, stream):
        """Make "the in-flight stage is abandoned" literally true.

        A stage writes to ``self.structure``/``self.instrument`` *before*
        solving — the between-stage recompile needs the freed values in the
        models, and a seeding stage (extinction's floor lift, the Stephens
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
                   ftol: float | None = None,
                   prior_significance: np.ndarray | None = None,
                   phase_support_sigma: float | None = PHASE_SUPPORT_SIGMA,
                   window_area_tol: float | None = None):
        """One stage: free params, recompile, solve, commit, guard.

        The recompile is what keeps the residual smooth *within* the stage —
        the hkl list, symmetry-op subsets, FCJ node counts and windows are
        frozen here and never move until the next stage.

        ``prior_significance`` is the previous stage's answer significance in
        a plan (WP-1523), which the support hold reads beside the screen
        (:func:`_hold_unsupported_phases`).  ``None`` for a plan's first stage,
        outside Rietveld mode (``_StageHold.significance`` is), and for
        :meth:`run_stage`, which has no previous stage of its own: a
        reading kept across verbs would outlive a ``set_values`` or a
        checkout that moved the values it was taken at.

        ``phase_support_sigma`` is the plan's (WP-2002 B1), or
        :meth:`run_stage`'s own keyword: the threshold of the support hold, its
        release, its collapse and the default cell window.  ``None`` switches all four off, and the answer's
        significance is then read against the default for
        ``PHASE_UNCONSTRAINED`` alone.
        """
        # the threshold the answer's significance is read against: the hold's
        # own, or the default where there is no hold and only the report reads
        report_sigma = _reported_support_sigma(phase_support_sigma)
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
        # (WP-1414).  A literal, or a pattern under a retired spelling: any
        # other pattern matching nothing is how the shipped plans reach
        # components a model may not declare, so it stays silent, while a
        # literal names one parameter and missing it is a typo or a rename,
        # and a retired name is a rename the plan missed.  Recorded, never
        # raised — one plan runs a whole series, and a path one pattern's
        # model lacks must not end the chain.
        unknown_paths = table.unknown_paths(stage.turn_on)
        if self._held:
            # lift the previous stage's hold before this one decides its own:
            # a phase invisible then may be plain now, and a cumulative plan
            # need not name its cell again for it to keep refining
            table.set_vary(self._held, True)
            self._held = []
        if mode in ("lebail", "pawley"):
            # never refine what ``mode_fixed_path`` force-fixes against the
            # intensity model (structure, the phase scale, texture, a magnetic
            # width); drop them from the reported freed list too — it must
            # describe the set actually left free.  By what the column *moves*
            # since WP-1342, so a tie cannot carry one past the drop.  Before
            # the seeds, never after: a seed writes the value whether or not
            # the path then refines, so a force-fixed path seeded first came
            # back holding the seed (the magnetic_width preset's 0.05° under
            # Le Bail, drawn split by the next Rietveld fit).
            reach = table.column_reach()
            for path in list(freed):
                if mode_fixed_column(reach.get(path, [path]), mode):
                    table.set_vary([path], False)
                    freed.remove(path)
        seeded: dict[str, float] = {}
        if stage.seed:
            # start a freed row sitting on its floor where the plan says:
            # roughness at b = 0 is the identity, and its stage starts b in
            # the band the data can see (WP-1938)
            seeded = dict.fromkeys(table.seed_floored(freed, stage.seed),
                                   stage.seed)
        strain_seeded: list[str] = []
        if stage.strain_seed:
            # the Stephens DOFs are unbounded below, so the seed above never
            # sees them; put an all-zero block on the isotropic ray
            strain_seeded = table.seed_stephens(freed, stage.strain_seed)
        # a seed moved these phases off the values the previous answer's
        # significance was read at, so the support hold drops that reading
        # for them (WP-1523)
        seeded_phases = (_phases_reached([*seeded, *strain_seeded],
                                         table.column_reach())
                         if seeded or strain_seeded else set())
        # ``StageResult.seeded``'s second writer (WP-2002, B14): each DOF of
        # the block at the value the seed wrote, read off the entry because
        # the isotropic ray gives every DOF its own coefficient
        seeded.update({p: table.entries[table._paths[p]].value
                       for p in strain_seeded})

        # regenerate reflection list/windows/FCJ nodes with current values
        # (between-stage refresh; frozen within the stage); the free-path
        # set lets the compiler allocate FCJ nodes for axial parameters
        # that are about to refine from zero
        self._write_back(table)
        # the moment frames are frozen per stage like the rest, and from the
        # cell this stage starts at: a β the last stage moved leaves the table
        # reading the moment DOFs in the old frame and the compile building a
        # new one, two moments by one set of numbers (#598).  So the table
        # rebuilds its frames from the written-back cell, re-seeds the DOFs to
        # the same components, and hands the compile those frames.
        table.reframe_moments(self.structure)
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
            window_slack_deg=stage.window_slack_deg,
            # and the area its windows may drop: the closing stage's own, None
            # for every declared stage (WP-2002, the sixth round's Q1 and Q2),
            # which compiles at the declared 2 % by name
            window_area_tol=recorded_window_tol(window_area_tol))
        table.push_moment_frames(new_model)
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
        # Three holds, and they answer different questions of the same stage:
        # a phase the data cannot see at all (WP-1301), a moment *direction*
        # the powder average cannot determine (WP-1327), and a phase's
        # displacement the fitted range cannot tell from its scale (WP-1534).
        # All are flat directions, all are taken after the compile at the
        # values the stage starts from, and all go into ``StageResult.held``
        # so the report can say which and why.  The phase hold also reads the
        # previous answer's significance where a plan hands one in (WP-1523).
        held, held_reach, unseen = _hold_unsupported_phases(
            model, table, prior_significance, seeded_phases,
            sigma=phase_support_sigma)
        # kept apart, because the release below judges each hold by its own
        # question: a moment DOF the *phase* hold took (every free structural
        # path of an invisible phase, ``moment.dof0`` included) stays with the
        # phase, and only what this probe itself held is asked again as a
        # direction (review of #433, finding 2)
        moment_hold, flat_axes, moment_turned = _hold_flat_moments(model, table)
        # last, on what the other two left free: an invisible phase's B is
        # already the phase hold's.  Kept apart for the moment hold's reason,
        # and more strictly: the ridge rests on the frozen reflection list, so
        # it is never asked again at the answer — a phase that rises above the
        # noise still has one d-spacing, and ``_released_phases`` would release
        # it for being visible.  The one later question is the converse: a
        # phase the support hold released below, whose B was never probed.
        ridge_hold, ridge_reach, scale_b_held = _hold_scale_b_ridges(model, table)
        # and an instrument width whose specimen twin is free (WP-2002): a
        # fact about which columns are free, so it is never asked again
        twin_hold, twin_reach, width_twins_held = _hold_width_twins(table, unseen)
        held = held + moment_hold + ridge_hold + twin_hold
        held_reach.update(ridge_reach)
        held_reach.update(twin_reach)
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
        # A "centroid" phase's origin restraint (WP-1912), built here and not
        # at the compile: its rows exist only where the *free* set can slide
        # the phase, and the holds above have just decided that set
        model.origin = compile_origin(model, table)
        outcome = run_least_squares(model, table, max_iter=stage.max_iter,
                                    events=events, stage=stage.name,
                                    backend=self._backend, solver=self._solver,
                                    cancel=cancel,
                                    phase_support_sigma=phase_support_sigma,
                                    **stage_ftol)
        # the table commits a moment in its principal chart (#604), and the
        # outcome is restated in that chart so every later reader of its
        # theta, Jacobian and correlations describes the values committed
        signs = table.commit(outcome.theta)
        outcome = rechart_outcome(outcome, table.x0(), signs,
                                  table.free_paths)
        # A phase can stay comfortably significant (phase_support_sigma) the
        # whole time and its cell still walk to nonsense — a joint
        # degeneracy with another free phase's cell, invisible to the
        # per-phase test above (CELL_SAFETY_FRACTION's docstring).  Checked
        # on the outcome, never as a bound the solver saw.  The cell goes back
        # to where the stage found it here, before the answer is measured
        # below, and is held for the second solve with the collapse's paths
        # (WP-2002, B8).
        cell_runaway = reset_cell_runaway(table, start_values)
        # A caller's free ``vars.X`` can drive a cell the same way and is
        # invisible to the reset above by construction (review of #385
        # finding 1) — named here instead, never silently passed through.
        cell_runaway_unresolved = _vars_driven_cell_escapes(table, start_values)
        if cell_runaway:
            # ``table.commit`` above wrote ``outcome.theta`` into
            # ``Entry.value``, and the reset above wrote past it again
            # directly on the entries, so ``outcome.theta`` is re-derived:
            # ``table.x0()`` reads the free columns off the committed
            # entries, a re-encoding of the table rather than a second source
            # of truth.  The Jacobian was taken at the escaped cell, so it
            # goes too, and the measurement below builds one where the values
            # now are.  Only this outcome's starting cost and counts reach the
            # result: the reset always buys the second solve, whose outcome
            # replaces the rest.
            outcome = dataclasses.replace(outcome, theta=table.x0(), jac=None)

        # Support is a fact about the values, and a stage moves them.  So the
        # measurement is taken again at the answer, and it can have moved
        # either way: a held phase that has *appeared* (its scale stayed free
        # precisely so it could), or a phase that looked visible at stage start
        # and **collapsed** while solving.  The second is the case a start-of-
        # stage test cannot see, and the one the in-situ ramp actually hit: its
        # CaF₂ was seeded at scale 1e-4, so it began every pattern well above
        # the noise, and the flat direction opened up only as the solver drove
        # that scale to nothing.
        # the moment holds are asked of the answer separately: they are about a
        # direction rather than a phase, so ``_released_phases``'s prefix test
        # would release them for the wrong reason — a phase rising above the
        # noise says nothing about whether its moment direction became
        # determinable.  *Which* paths are moment holds is what
        # ``_hold_flat_moments`` returned, never a name match on ``held``: the
        # phase hold takes an invisible phase's moment DOFs too, and read by
        # name those went to the direction probe, which skips ``dof0`` and so
        # released the modulus of a phase the data still could not see.
        moment_set = set(moment_hold)
        apart = moment_set | set(ridge_hold) | set(twin_hold)
        moment_held = [p for p in held if p in moment_set]
        phase_held = [p for p in held if p not in apart]
        # one measurement, two questions — the release and the collapse are
        # complementary readings of the same significance vector (WP-1523):
        # a held phase measured with its held columns free, every other phase
        # off this solve's own covariance
        support = _answer_significance(model, table, outcome, phase_held,
                                       held_reach, self._backend,
                                       sigma=report_sigma)
        # the hold's reach travels with it: a held ``vars.X`` names no phase,
        # and asking the table now would get nothing back (WP-1342)
        released = (_released_phases(model, table, phase_held, support, held_reach,
                                     sigma=phase_support_sigma)
                    if phase_held else [])
        # A combination found by either question below is turned before the
        # re-solve, as at stage start (review of #624, item 1): a site held at
        # stage start as two flat *columns* (its modulus under the floor) can
        # come back from the answer as a flat combination — its polar angle
        # released, its azimuth still held — and a held azimuth that was never
        # turned leaves the polar angle on a meridian that need not pass near
        # the flat axis, which is #599's trap.
        late_axes: dict[str, np.ndarray] = {}
        still_flat: set[str] = set()
        if moment_held:
            still, still_axes = _flat_moment_scan(model, table, moment_held)
            still_flat = set(still)
            released = released + [p for p in moment_held if p not in still_flat]
            late_axes.update({b: a for b, a in still_axes.items()
                              if _site(b) not in moment_turned})
        # the same question the hold asked, asked again of the answer: what is
        # free now and belongs to a phase the data cannot see, and what moment
        # direction went flat while the stage ran
        frames = table.moment_frames()
        for b, a in late_axes.items():
            flat_axes.setdefault(_site(b),
                                 _axis_in_crystal_axes(a, frames[_site(b)]))
        # Turned here, at the answer, wherever the azimuth stays held and the
        # site is not yet turned — after a release, and also where nothing was
        # released because the stage-start turn was refused (measured: a start
        # at 3e-8 μ_B reads roundoff on both sides of the floor test, the
        # rank probe still finds the axis, the turn is declined, and the
        # answer sat at ψ = 27.84° against 10.20° with nothing re-solved).
        # A turn here is a reason to solve again, as a release is.
        late_turned = _turn_onto_meridians(
            model, table, {b: a for b, a in late_axes.items()
                           if f"{b}.dof2" in still_flat})
        moment_turned.update(late_turned)
        flat_now, collapse_axes = _flat_moment_scan(model, table)
        collapsed_phase = _unsupported_phase_paths(model, table, support,
                                                   sigma=phase_support_sigma)
        collapsed = collapsed_phase + flat_now
        # the support hold's columns once the release and the collapse have
        # acted: taken now, because a late scale-B hold below re-holds some of
        # the released columns for a different reason
        released_now = set(released)
        support_held = ([p for p in phase_held if p not in released_now]
                        + collapsed_phase)
        for b, a in collapse_axes.items():
            flat_axes.setdefault(_site(b),
                                 _axis_in_crystal_axes(a, frames[_site(b)]))
        # the cell reset's hold (WP-2002, B8) takes what the collapse left: a
        # path both reach is the collapse's, in ``held``, so the two records
        # stay disjoint and PHASE_UNCONSTRAINED still names the phase
        collapsed_set = set(collapsed)
        reset_hold = list(dict.fromkeys(p for p, _, _ in cell_runaway
                                        if p not in collapsed_set))
        # ``StageResult.cell_reset``: the held ones, and any the second solve
        # puts back below
        cell_reset = list(reset_hold)
        if released or collapsed or late_turned or reset_hold:
            if collapsed:
                # Restore before holding.  A phase whose scale is not 3σ from
                # zero (``_answer_significance``) is one the data cannot tell
                # from absent, so where its cell and widths went is not a
                # measurement: under that null they are free to chase the noise
                # (WP-1523), and the values they reached are the chase.  The
                # restore can move χ², since a curve fitted to noise does lower
                # it, which is why the second solve below re-fits everything
                # else against the restored phase rather than assuming the
                # restore changed nothing.  Without it the stage would freeze
                # the walk it was trying to prevent (measured on the ramp:
                # cells at 20.3 Å and −6.5 Å).
                by_path = {e.path: e for e in table.entries}
                for path in collapsed:
                    by_path[path].value = start_values[path]
                # a body's rotation restarts at zero either side of the
                # commit, which composed the turn into its anchor (WP-1805)
                table.restore_body_anchors(collapsed)
                table.refresh_ties()  # dependents follow (b←a on a cubic cell)
                # a collapsed combination is turned at the restored values,
                # then held — the stage-start order
                moment_turned.update(_turn_onto_meridians(
                    model, table, {b: a for b, a in collapse_axes.items()
                                   if f"{b}.dof2" in collapsed}))
                # read while they are still columns, as at stage start
                held_reach.update(_reach_beyond_self(table, collapsed))
                table.set_vary(collapsed, False)
                held = held + collapsed
            if reset_hold:
                # Already back where the stage found it (the reset above), and
                # held for the second solve, which re-fits everything else
                # without the walk.  The next stage lifts it with the other
                # holds (``self._held``), so the plan's cell refines again
                # from a value the data saw.
                reset_hold = table.set_vary(reset_hold, False)
                cell_reset = list(reset_hold)
            if released:
                released_set = set(released)
                table.set_vary(released, True)
                held = [p for p in held if p not in released_set]
                # A phase held unseen at stage start was never asked the
                # scale-B question — its displacement columns were not free —
                # so it is asked here, before the second solve frees them
                # along the ridge #204 walked.  Its B is still the value the
                # stage started from, having been held through the first solve.
                late = {int(m.group(1)) for p in released
                        for name in (p, *held_reach.get(p, ()))
                        if (m := _DISPLACEMENT_PATH.match(name))}
                if late:
                    late_hold, late_reach, late_sep = _hold_scale_b_ridges(
                        model, table, phases=late)
                    if late_hold:
                        held_reach.update(late_reach)
                        held = held + late_hold
                        scale_b_held.update(late_sep)
                        late_set = set(late_hold)
                        released = [p for p in released if p not in late_set]
            # the twin question asked again of the second solve's free set
            # (code review of WP-2002's 9th session): a phase that collapsed
            # pins nothing now, so a pair it pinned at stage start is flat
            if phase_support_sigma is not None and support is not None:
                late_twin, late_twin_reach, late_twins = _hold_width_twins(
                    table, {ip for ip, z in enumerate(support)
                            if z < phase_support_sigma})
                held = held + late_twin
                held_reach.update(late_twin_reach)
                width_twins_held.update(late_twins)
            self._held = list(held) + reset_hold
            held_set = set(held)
            freed = [p for p in declared_freed
                     if p not in held_set and p not in reset_hold]
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
            # the origin restraint follows the free set, which the release or
            # the collapse has just changed: asked again, at the values this
            # solve starts from, and frozen for it (WP-1912)
            model.origin = compile_origin(model, table)
            # Once — never a third solve, whichever way the measurement moved,
            # so the cost of a wrong hold is bounded at one stage's budget.
            second = run_least_squares(
                model, table, max_iter=stage.max_iter, events=events,
                stage=stage.name, backend=self._backend,
                solver=self._solver, cancel=cancel,
                phase_support_sigma=phase_support_sigma, **stage_ftol)
            signs = table.commit(second.theta)
            second = rechart_outcome(second, table.x0(), signs,
                                     table.free_paths)
            # Asked again, because a column this solve freed (a release) can
            # walk too.  There is no third solve, so the cell goes back and
            # stays a free column of this answer: holding it now would leave
            # the covariance a column wider than θ.  Its esd is withheld
            # through ``CELL_RUNAWAY``.
            second_runaway = [CellReset(*c, escaped=c.escaped, held=False)
                              for c in reset_cell_runaway(table, start_values)]
            if second_runaway:
                cell_runaway = cell_runaway + second_runaway
                put_back = [p for p, _, _ in second_runaway]
                cell_reset = cell_reset + put_back
                freed = [p for p in freed if p not in put_back]
                # same re-derivation as the first reset above, on ``second``
                # rather than ``outcome`` — the merge just below carries
                # ``second``'s ``theta`` field forward untouched otherwise.
                second = dataclasses.replace(second, theta=table.x0())
            # same measurement as the first solve, re-taken on the values the
            # collapse-restore's own second solve landed on -- merged by
            # driver rather than concatenated, so a driver still escaping
            # after both solves is named once, not twice
            cell_runaway_unresolved = _merge_unresolved(
                cell_runaway_unresolved,
                _vars_driven_cell_escapes(table, start_values))
            # the record is one stage: the second solve's answer, the first
            # solve's starting cost, and the iterations of both — the whole
            # point being that the hold cost something and it must be visible
            # where the budget is read
            outcome = dataclasses.replace(
                second, cost_initial=outcome.cost_initial,
                n_iterations=outcome.n_iterations + second.n_iterations,
                n_constraint_truncations=(outcome.n_constraint_truncations
                                          + second.n_constraint_truncations),
                # counts of the whole search, as multi.py's merge sums them
                n_degenerate_cell_probes=(outcome.n_degenerate_cell_probes
                                          + second.n_degenerate_cell_probes),
                n_lapack_fallbacks=outcome.n_lapack_fallbacks + second.n_lapack_fallbacks,
                truncated_by={k: (outcome.truncated_by.get(k, 0)
                                  + second.truncated_by.get(k, 0))
                              for k in {**outcome.truncated_by,
                                        **second.truncated_by}})
            # the significance the result will quote.  A phase the support
            # hold still holds keeps the reading its hold was decided on, so
            # the hold and PHASE_UNCONSTRAINED cannot disagree; every other
            # phase is read again off the second solve's own covariance
            decided = support
            # a cell the second solve's reset put back moved the values off
            # the point ``outcome.jac`` was taken at, so the measurement builds
            # its own there, the first reset's rule; the guards below keep the
            # solve's Jacobian
            measured = (dataclasses.replace(outcome, jac=None) if second_runaway
                        else outcome)
            support = _answer_significance(model, table, measured, [],
                                           held_reach, self._backend,
                                           sigma=report_sigma)
            for ip in _phases_reached(support_held, held_reach):
                support[ip] = decided[ip]

        if mode == "lebail":
            model.lebail_update(table.decode(outcome.theta), n_cycles=stage.lebail_cycles)

        guard = check_guards(table, outcome, correlation_guard, model=model,
                             scan_exchangeability=stage_index == n_stages)
        # what the frozen windows drop at the answer, against windows sized
        # there (WP-2047): after the collapse and the Le Bail update, so it
        # reads the answer the stage hands on
        loss = window_loss(model, table.decode(outcome.theta))
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
                        held=list(held), released=list(released),
                        window_loss=loss)
        final_held = set(held)
        kept_axes = {b: a for b, a in flat_axes.items()
                     if f"{b}.moment.dof2" in final_held}
        return model, outcome, guard, freed, _StageHold(
            held=list(held), released=list(released),
            moment_flat_axes=kept_axes,
            moment_turned=[b for b in kept_axes if b in moment_turned],
            reach={c: list(v) for c, v in held_reach.items()},
            scale_b_held=dict(scale_b_held),
            width_twins_held=width_twins_held,
            blocked_by_hold=blocked_by_hold, unknown_paths=unknown_paths,
            seeded=seeded,
            cell_runaway=list(cell_runaway),
            cell_reset=list(cell_reset), collapsed=list(collapsed),
            cell_runaway_unresolved=[(d, list(e)) for d, e in cell_runaway_unresolved],
            origin=model.origin,
            # Le Bail and Pawley read the screen alone, which the result
            # measures on its own compile as it always has
            significance=support if mode == "rietveld" else None,
            window_loss=loss)

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
        plan = resolve_plan(plan, mode)
        if mode == "lebail" and plan.lebail_passes > 1 and plan.stages:
            return self._fit_lebail_alternation(
                data, plan=plan, two_theta_limits=two_theta_limits,
                events=events, cancel=cancel, telemetry=telemetry, label=label,
                stage_reports=stage_reports, progress=progress)
        return self._fit_pass(
            data, mode=mode, plan=plan, two_theta_limits=two_theta_limits,
            events=events, cancel=cancel, telemetry=telemetry, label=label,
            stage_reports=stage_reports, progress=progress)

    def _fit_lebail_alternation(self, data: PatternData, *,
                                plan: RefinementPlan, **kw) -> RefinementResult:
        """Run the plan up to ``plan.lebail_passes`` times and keep the best pass.

        The extracted intensities are frozen inside a run (the
        frozen-per-stage invariant), so they and the profile converge only by
        alternating, and the alternation is no descent on one objective: from
        a poor start Rwp rose monotonically over 15-20 passes, from a good one
        it fell to a fixed point (#210, WP-1323's baseline table).  Hence the
        rule, which is the reporter's and not a tuned one: stop at the first
        pass that does not lower Rwp, never while it still falls, and answer
        with the pass that had the lowest.  What a plan that is not a descent
        has at pass *k* is a state, so the best pass is *restored* rather than
        merely reported.
        """
        best = None            # (rwp, result, state, head, pass number, fit view)
        rows: list[float] = []
        spans: list[list[str]] = []     # the history nodes each pass created
        reason = "cap"
        # **Once per job** (WP-1403): each pass would otherwise attach its own
        # recorder and write a run directory, so N passes drew N rows in
        # ``rietx watch``.  The stream is built and the recorder attached here,
        # and the passes get the stream as ``events`` — an object the caller
        # owns as far as ``_fit_pass`` is concerned, so it closes none — and
        # find the recorder through ``runs.recorder_of``, as a series' do.
        events = kw.pop("events", None)
        telemetry = kw.pop("telemetry", None)
        label = kw.pop("label", None)
        cancel = kw.pop("cancel", None)
        stream = _attach_progress(as_event_stream(events),
                                  kw.pop("progress", None))
        recorder = runs.attach(stream, events, telemetry=telemetry,
                               project_hint=self._project_hint(), label=label)
        if recorder is not None and stream is None:
            stream = recorder
        cancel = runs.attach_cancel(runs.recorder_of(stream), cancel)
        try:
            for number in range(1, plan.lebail_passes + 1):
                # the whole plan, cap and all: ``_fit_pass`` never reads
                # ``lebail_passes``, and what it records (``_last_plan``, the
                # history header) should say the cap that was asked for
                before = 0 if self.history is None else len(self.history.order)
                try:
                    result = self._fit_pass(data, mode="lebail", plan=plan,
                                            events=stream, cancel=cancel,
                                            telemetry=False, lebail_pass=number,
                                            **kw)
                finally:
                    # an abandoned pass's committed stages are its nodes too
                    if self.history is not None:
                        spans.append([i for i in self.history.order[before:]
                                      if self.history.nodes[i].parents])
                rwp = float(result.statistics.rwp)
                rows.append(rwp)
                if best is not None and (rwp >= best[0] or not np.isfinite(rwp)):
                    # not lower: a fixed point if it is level to within the
                    # tolerance, a wander if it is worse
                    reason = ("converged" if rwp <= best[0] * (1 + LEBAIL_CONVERGED_REL)
                              else "non_monotone")
                    break
                gain = None if best is None else (best[0] - rwp) / best[0]
                best = (rwp, result, self.snapshot(), self._head_id, len(rows),
                        (self._model, self._answer_covariance, self._answer,
                         self.stage_reports_))
                if gain is not None and gain <= LEBAIL_CONVERGED_REL:
                    reason = "converged"
                    break
            _, result, state, head, kept, fit_view = best
            if kept != len(rows):
                self._keep_pass(result, state, head, fit_view)
            self._mark_passes(spans, kept)
            result.diagnostics.append(_lebail_stop_diagnostic(
                reason, kept, rows, plan.lebail_passes))
            if recorder is not None:
                # the last pass wrote its own; the answer is the kept one
                recorder.write_summary(result)
            return result
        except BaseException as exc:
            # a cancel or an error in pass k > 1 leaves the state wherever the
            # in-flight pass had got to (its completed stages stand), which is
            # neither the last pass nor the best; the best pass is the one
            # worth standing at, and a cancel names the node it stands at
            if best is not None:
                self._keep_pass(best[1], best[2], best[3], best[5])
                if isinstance(exc, RefinementCancelled):
                    exc.node_id = best[3]
            if recorder is not None:
                recorder.close("failed")
            raise
        finally:
            if stream is not None and stream is not events:
                stream.close()        # built here from a path or a callable
            if recorder is not None:
                recorder.close()

    def _mark_passes(self, spans: list[list[str]], kept: int) -> None:
        """Write which pass each history node belongs to, as node ``notes``.

        ``lebail_pass`` on every node a pass created, ``lebail_kept`` on the
        kept pass's nodes (``"k of N"``, N the passes run) and
        ``lebail_discarded`` on the rest, so a viewer can tell the passes the
        head left behind from the one it stands in.  Notes are the tree's own
        free-form channel, so no schema moves.  Nothing is written, and nothing
        raised, when the refinement keeps no history.
        """
        tree = self.history
        if tree is None:
            return
        for number, ids in enumerate(spans, start=1):
            mark = {"lebail_pass": str(number)}
            if number == kept:
                mark["lebail_kept"] = f"{kept} of {len(spans)}"
            else:
                mark["lebail_discarded"] = "true"
            for node_id in ids:
                tree.annotate(node_id, notes=mark)

    def _keep_pass(self, result, state, head, fit_view) -> None:
        """Restore the pass ``_fit_lebail_alternation`` decided to keep."""
        self._restore_state(state)
        # ``_restore_state`` drops the fit's view of the values (it is what
        # ``checkout`` needs), but these *are* the values the kept pass
        # fitted, so ``result_``, ``report()``, ``predict()`` and the
        # plots read the answer this call returns, not nothing
        self.result_ = result
        (self._model, self._answer_covariance, self._answer,
         self.stage_reports_) = fit_view
        # A fit re-extracts the intensities at its first stage, so the
        # pass after a plain ``fit()`` starts from the parameters alone.
        # Seeding them from the restored state would hand the next fit a
        # start the hand loop never had: measured on the +2 % LaB6+cBN
        # start, 254.09 % against the loop's 194.56 %.
        self._pending_reflections = []
        if self.history is not None and head is not None:
            self.history.set_head(head)
            self._head_id = head

    def _fit_pass(self, data: PatternData, *, mode: Mode,
                  plan: RefinementPlan,
                  two_theta_limits: tuple[float, float] | None = None,
                  events=None, cancel=None, telemetry=None,
                  label: str | None = None, stage_reports: bool = False,
                  progress=None, lebail_pass: int | None = None) -> RefinementResult:
        """One run of ``plan``: what ``fit`` was before WP-1323.

        ``lebail_pass`` is set by the alternation and stamps this pass's
        ``fit_start``/``fit_end``, so a recorder reads the pass's end as the end
        of a pass and not of the run (``runs.RunRecorder._observe``).
        """
        stamp = ({} if lebail_pass is None else
                 {"lebail_pass": lebail_pass, "lebail_of": plan.lebail_passes})
        _refuse_without_phases(self.structure, "fit")
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

        require_two_theta(data, "Refinement.fit()", instrument=self.instrument)
        self._mode = mode
        self._two_theta_limits = two_theta_limits
        self._free_paths = []
        # the fit's stages declare the free set; until the first one does, the
        # models' flags are it again, as for a fresh refinement
        self._free_set_declared = False
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

                # the file's count, and beside it the fitted count every
                # ``stage_start`` carries (#441): ``fitted_mask`` is the
                # authority ``compile_model`` is pinned to (WP-1033)
                stream.emit("fit_start", mode=mode,
                            stages=[s.name for s in plan.run_stages()],
                            n_points=len(data.x()),
                            n_fitted=int(fitted_mask(data, two_theta_limits).sum()),
                            **stamp)

            # Stages are cumulative *within the plan*, and the plan drives the whole
            # turn-on sequence: `restore=False` holds everything first, so a fit
            # replaces the vary flags a caller set by hand rather than continuing
            # them (`run_stage`, which continues from the working state, restores
            # them instead).  The comment here said the opposite until WP-1208
            # measured it — `set_vary("phases.*.atoms.*.biso")` then
            # `fit(plan="profile_only")` refines no biso — and the GUI's plan panel
            # now names the difference, since nothing a user could read said it.
            table = self._prepare_table(restore=False)
            # the phases before any stage moves an atom, whose contacts inside
            # r₀ RESTRAINT_PAIRS_STALE needs to tell a drifted pair from one
            # the caller left out of the list on purpose
            stale_since = _anti_bump_start_phases(self.structure, mode)

            # the λ this Refinement was constructed with (or last edited to), so a
            # second λ-freeing call reports the cumulative move from the truly
            # declared value rather than from the first call's answer (WP-1134).
            # Copied, never aliased: ``_build_result`` is only a reader today, but a
            # snapshot handed out by reference is a mutation waiting to happen.
            declared_wavelengths = list(self._declared_wavelengths)

            diagnostics: list[Diagnostic] = (
                self._drain_twin_findings()
                + _symmetry_silence_diagnostics(self.structure, mode)
                + _dispersion_diagnostics(self.structure, self.instrument)
                + _resonant_absorber_diagnostics(self.structure,
                                                 self.instrument)
                + _species_fallback_diagnostics(self.structure, self.instrument)
                # WP-1343: the one check in the package that reads a *plan*
                # rather than a solved state, and it is here because that is
                # the only place it can be true to its own claim — the
                # confound it names is created by the stage list itself, so
                # the report has to arrive before the first stage runs rather
                # than after the answer it spoiled.
                + _stage_order_diagnostics(plan, table, mode)
                # a plan read too, and here for the same reason: a literal a
                # stage cannot free is decided by the model before any stage
                + _fixed_literal_diagnostics(plan.stages, table, self._ties))
            stage_results: list[StageResult] = []
            self.stage_reports_ = []
            outcome = None
            model = None

            try:
                (model, outcome, guard, stage_results, diagnostics,
                 answer_runaway, answer_significance, origins) = self._run_plan(
                    plan, data, mode, table, two_theta_limits, tree, stream, cancel,
                    stage_results, diagnostics, sinks=sinks,
                    stage_reports=stage_reports)
            except RefinementCancelled as exc:
                if stream is not None:
                    stream.emit("fit_end", status="cancelled", stage=exc.stage,
                                completed=[s.name for s in exc.completed_stages],
                                node_id=exc.node_id, **stamp)
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
                plan.run_stages()[-1], plan.stage_window_tols()[-1])
            diagnostics.extend(recompiled)
            self._model = model

            if mode == "pawley":
                diagnostics.extend(_pawley_unresolved_diagnostics(model, self.structure))
                diagnostics.extend(_pawley_off_data_diagnostics(model, self.structure))
            diagnostics.extend(_constraint_diagnostics(plan.run_stages()[-1].name,
                                                       outcome))
            diagnostics.extend(_degenerate_cell_diagnostics(
                [(sr.name, sr.n_degenerate_cell_probes) for sr in stage_results]))
            diagnostics.extend(_hold_diagnostics(stage_results,
                                                 table.origin_holds))
            diagnostics.extend(_origin_diagnostics(table, stage_results,
                                                   origins=origins))
            diagnostics.extend(_unknown_path_diagnostics(
                stage_results, [e.path for e in table.entries]))
            diagnostics.extend(_window_loss_diagnostics(stage_results))
            if mode == "rietveld":
                # after the write-back: the search reads the answer's coordinates
                diagnostics.extend(_restraint_pairs_stale_diagnostics(
                    self.structure, stale_since))

            self.result_ = _build_result(
                model, table, outcome.theta, mode=mode, status=outcome.status,
                stage_results=stage_results, diagnostics=diagnostics,
                structure=self.structure, stderr_internal=outcome.stderr_internal,
                esd_inflation=outcome.esd_inflation,
                correlation=outcome.correlation, backend=self._backend,
                solver=self._solver,
                mu_r_source=self._mu_r_source, mu_r_skipped=self._mu_r_skipped,
                guard=guard, max_shift_over_esd=outcome.max_shift_over_esd,
                declared_wavelengths=declared_wavelengths,
                cell_runaway=answer_runaway,
                significance=answer_significance,
                phase_support_sigma=plan.phase_support_sigma)
            # beside result_, never at entry: a call that is cancelled or fails
            # leaves the previous result and the pattern it was fitted to
            self._fit_pattern = data
            self._plan_settings = {
                "correlation_guard": plan.correlation_guard,
                "phase_support_sigma": plan.phase_support_sigma,
                # resolved, never the record's None: a trial hands this to
                # run_stage, whose None is the closing fraction, so a plan with
                # closing_window_tol=None would refit at 0.1 % windows against
                # a χ² measured at the declared 2 %
                "window_area_tol": recorded_window_tol(plan.stage_window_tols()[-1])}
            _apply_esds(table, self.result_, self.structure, self.instrument)
            self._answer_covariance = (self.result_, table, outcome.theta,
                                       outcome.stderr_internal,
                                       outcome.correlation)
            self._answer = self._freeze_answer()
            self._stamp(self.result_, tree)
            if self._auto_intervals:
                # WP-2002, B2: an angle the answer stage left out of its
                # covariance carries its profile interval in place of an esd.
                # After the stamp, which it never moves (no node, HEAD kept),
                # and before ``fit_end``, so the run ends when the result does
                from .strategy.parameter_interval import (
                    attach_stationary_intervals,
                )

                attach_stationary_intervals(self, data, cancel=cancel)
            if stream is not None:
                stream.emit("fit_end", status=self.result_.status,
                            rwp=self.result_.statistics.rwp,
                            gof=self.result_.statistics.gof,
                            node_id=self.result_.node_id, **stamp)
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
        answer_runaway, answer_significance, origins)``; raises
        :class:`RefinementCancelled` with the completed stages attached.  The guard returned is the **last** stage's,
        for the same reason :func:`_constraint_diagnostics` reads only that
        stage: earlier stages measured an intermediate state, and it is the
        answer-producing one whose Jacobian the result's identifiability
        evidence describes.  ``answer_runaway`` is that stage's
        ``CELL_RUNAWAY`` finding (``[]`` or one), for the same reason: it is
        what :func:`_build_result` withholds esds on, while ``diagnostics``
        carries every stage's.  ``answer_significance`` is that stage's
        :func:`_answer_significance` too (WP-1523), the vector its hold was
        decided on, which ``PHASE_UNCONSTRAINED`` quotes.  ``origins`` is
        ``(stage name, _StageHold.origin)`` per stage, the origin restraint
        each ran with (WP-1912), which ``ORIGIN_FIXED_ON_POLAR_AXIS`` words.

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
        #231), and so is ``FLOOR_HIT``, its twin on a floor (WP-1929): it is
        not deduplicated but **discarded and re-taken**, because
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
        # the declared stages and the closing one, with the schedule of each
        # (WP-2002, the sixth round's Q1 and Q2): the plan is the one authority
        stages = plan.run_stages()
        ftols = plan.stage_ftols()
        window_tols = plan.stage_window_tols()
        # a dataclass validates nothing, so the plan's threshold is checked
        # where it is read, in the words its mirror uses (WP-2002, B1)
        phase_support_sigma = check_phase_support_sigma(plan.phase_support_sigma)
        correlation_hits: dict[tuple[str, frozenset],
                              list[tuple[str, Diagnostic]]] = {}
        answer_runaway: list[Diagnostic] = []
        #: the last stage's ``_StageHold.significance`` (WP-1523), which the
        #: result's ``PHASE_UNCONSTRAINED`` quotes
        answer_significance = None
        #: the moment's rung at the first stage that moved it with every
        #: magnetic width still at its off state (WP-1343)
        moment_off_state: dict[str, tuple[float, float | None]] = {}
        #: (stage name, moment rung, width values) of the last stage that had a
        #: magnetic width free — the released state the off state is compared
        #: against, once, after the loop
        moment_released: tuple | None = None
        #: (stage name, origin restraint) per stage (WP-1912)
        origins: list[tuple[str, CompiledOrigin | None]] = []
        #: every other per-stage finding, keyed by what it is about: a later
        #: stage re-measuring the same paths replaces an earlier one's, which
        #: the closing stage does for every finding the last declared stage
        #: made (WP-2002).  Each stage's own list stays on its report and node.
        restated: dict[tuple, Diagnostic] = {}
        for k, (stage, ftol, window_tol) in enumerate(
                zip(stages, ftols, window_tols, strict=True), start=1):
            with self._abandon_on_cancel(cancel, stage.name, stage_results, stream):
                model, outcome, guard, freed, hold = self._run_stage(
                    stage, data, mode, table, model, two_theta_limits,
                    plan.correlation_guard, events=stream, cancel=cancel,
                    stage_index=k, n_stages=len(stages), ftol=ftol,
                    # still the previous stage's here: the support hold
                    # starts from that answer as well as the screen (WP-1523)
                    prior_significance=answer_significance,
                    phase_support_sigma=phase_support_sigma,
                    window_area_tol=window_tol)
            # WP-1343: the moment's rung at this boundary, and the shift the
            # moment took when the widths were released.  Gated on what the
            # stage actually freed, so an ordinary fit never pays for the
            # physical-esd build ``_moment_rung`` needs.
            width_paths = [q for q in freed if _MAGNETIC_WIDTH_PATH.match(q)]
            if width_paths or any(_MOMENT_DOF.match(q) for q in freed):
                rung = _moment_rung(table, outcome)
                if width_paths:
                    esds = (table.stderr_physical(
                        outcome.theta, outcome.stderr_internal,
                        outcome.correlation)
                        if outcome.stderr_internal is not None else {})
                    vals = table.decode(outcome.theta)
                    # the *last* stage that had a width free is the released
                    # state: one row per moment path in the result, not one
                    # per (path, stage) — the shape ``_dedup_high_correlations``
                    # exists to stop one rank over
                    moment_released = (stage.name, rung, {
                        q: (float(vals[q]), esds.get(q)) for q in width_paths})
                elif rung:
                    # the off state: a stage that moved the moment while no
                    # magnetic width could move at all.  The *first* such rung
                    # is the reference, because it is the number a reader who
                    # stopped at the prescribed step 1 would have quoted.
                    moment_off_state = moment_off_state or rung
            stage_diagnostics = _guard_diagnostics(guard) + _covariance_diagnostics(
                stage.name, outcome, answer=k == len(stages))
            for d in stage_diagnostics:
                if d.code in ("HIGH_CORRELATION", "FLAT_DIRECTION"):
                    # keyed by code *and* pair: a flat pair fires both, and a
                    # key of the pair alone would let one evict the other
                    correlation_hits.setdefault(
                        (d.code, frozenset(d.where)), []).append((stage.name, d))
                elif d.code in _REVISABLE_CODES:
                    continue          # re-taken on the converged vector below
                else:
                    key = (d.code, tuple(d.where) or (d.message,))
                    restated.pop(key, None)
                    restated[key] = d
            runaway_diag = _cell_runaway_diagnostic(hold.cell_runaway, hold.cell_runaway_unresolved)
            # the last stage's alone survives the loop: an earlier stage's
            # reset is re-measured by every later one (staging is cumulative)
            answer_runaway = [] if runaway_diag is None else [runaway_diag]
            answer_significance = hold.significance
            origins.append((stage.name, hold.origin))
            if runaway_diag is not None:
                diagnostics.append(runaway_diag)
                stage_diagnostics = stage_diagnostics + [runaway_diag]
            stage_results.append(StageResult(
                name=stage.name, status=outcome.status, n_iterations=outcome.n_iterations,
                cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                freed=freed,
                n_constraint_truncations=outcome.n_constraint_truncations,
                n_degenerate_cell_probes=outcome.n_degenerate_cell_probes,
                n_lapack_fallbacks=outcome.n_lapack_fallbacks,
                ftol=ftol, window_area_tol=window_tol,
                held=hold.held, released=hold.released,
                held_reach=hold.reach,
                scale_b_held=hold.scale_b_held,
                width_twins_held=hold.width_twins_held,
                moment_flat_axes=hold.moment_flat_axes,
                moment_turned=hold.moment_turned,
                blocked_by_hold=hold.blocked_by_hold,
                unknown_paths=hold.unknown_paths,
                window_loss=hold.window_loss,
                seeded=hold.seeded,
                cell_reset=hold.cell_reset, collapsed=hold.collapsed,
                # checked, trivially: one histogram has no elsewhere
                unreached_histograms={},
                moment_angle_tests=outcome.moment_angle_tests,
            ))
            if stage_reports:
                self.stage_reports_.append(self._stage_report(
                    stage.name, plan, data, mode, table, model, outcome, guard,
                    stage_diagnostics, significance=hold.significance))
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
                    window_area_tol=window_tol,
                    # and the plan's two settings, for the same reason
                    # (WP-2002, B1)
                    phase_support_sigma=phase_support_sigma,
                    correlation_guard=plan.correlation_guard,
                ), model, table, outcome, stage_diagnostics,
                    held_scales=_held_scale_phases(stage_results[-1]),
                    window_loss=stage_results[-1].window_loss)
        diagnostics.extend(restated.values())
        # the converged vector's own findings, and nothing earlier: the same
        # ``guard`` object ``_build_result`` projects ``at_bound`` from
        if guard is not None:
            diagnostics.extend(d for d in _guard_diagnostics(guard)
                               if d.code in _REVISABLE_CODES)
        diagnostics.extend(_dedup_high_correlations(correlation_hits))
        if moment_off_state and moment_released is not None:
            name, rung, widths = moment_released
            diagnostics.extend(_moved_moment_diagnostics(
                name, moment_off_state, rung, widths))
        return (model, outcome, guard, stage_results, diagnostics,
                answer_runaway, answer_significance, origins)

    def _final_compile(self, model: CompiledModel, table: ParameterTable,
                       outcome, data: PatternData, mode: Mode,
                       two_theta_limits, stage: Stage,
                       window_area_tol: float | None = None,
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
        slack, and the closing stage's window area) and nothing else changed.  **What this does not move**: the
        solve, which ran on the frozen compile (on #272's two fixtures the
        minimum moved ≤ 0.0014 esd between the two, but a stage that carries
        its peaks past their windows can stop at a minimum the windows moved:
        9 % of χ² on the fluorapatite tutorial, WP-1986, recovered by one more
        stage, which is why a plan ends on a closing stage); the covariance and
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
            window_slack_deg=stage.window_slack_deg,
            window_area_tol=recorded_window_tol(window_area_tol))
        # and the solve's moment frames, never the fresh compile's: this one is
        # built at the fitted cell, so a last stage that moved an angle would
        # otherwise read the refined moment DOFs in a frame they were never
        # refined in, and ``y_calc`` would describe a third moment (#598)
        table.push_moment_frames(fresh)
        # the solve's weights, never the fresh compile's: a measured
        # background widens σ at the scale a compile sees (WP-1309), so a last
        # stage that moved that scale would re-weight here, and the result
        # would divide by a σ its χ², esds and solve never used
        fresh.sigma = model.sigma
        # and the solve's origin rows (WP-1912), for the same reason: the
        # reported covariance was read with them, so the model reported from
        # carries the block it was read with
        fresh.origin = model.origin
        if mode == "lebail":
            _carry_lebail(model, fresh)
        values = table.decode(outcome.theta)
        chi2_frozen = float(np.sum(
            ((model.y_obs - model.evaluate(values)) / model.sigma) ** 2))
        chi2_fresh = float(np.sum(
            ((fresh.y_obs - fresh.evaluate(values)) / fresh.sigma) ** 2))
        return fresh, _frozen_compile_diagnostics(chi2_frozen, chi2_fresh)

    def _stage_report(self, name, plan, data, mode, table, model, outcome,
                      guard, stage_diagnostics, *, significance=None
                      ) -> StageReport:
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
            esd_inflation=outcome.esd_inflation,
            correlation=outcome.correlation, backend=self._backend,
            solver=self._solver, mu_r_source=self._mu_r_source,
            mu_r_skipped=self._mu_r_skipped, guard=guard,
            max_shift_over_esd=outcome.max_shift_over_esd,
            significance=significance,
            phase_support_sigma=plan.phase_support_sigma)
        report = build_report(result, model=model,
                              values=table.decode(outcome.theta), plan=plan,
                              structure=self.structure, instrument=self.instrument,
                              free_paths=list(table.free_paths))
        return report.for_stage(name)

    def run_stage(self, data: PatternData, stage: Stage, *,
                  mode: Mode | None = None,
                  two_theta_limits: tuple[float, float] | None = None,
                  correlation_guard: float = CORRELATION_GUARD,
                  phase_support_sigma: float | None = PHASE_SUPPORT_SIGMA,
                  window_area_tol: float | None = None,
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

        ``correlation_guard`` and ``phase_support_sigma`` are the two plan
        settings a stage reads, taken here as keywords because there is no plan:
        ``RefinementPlan.phase_support_sigma`` says what the second does, and
        ``None`` switches the significance test off for this stage; a phase with no
        line in range is still held, scale included (WP-2002, B1; WP-1958).
        A project's ``run_stage`` passes its stored plan's.

        ``window_area_tol`` is the fraction of each peak's area this stage's
        windows may drop.  ``None`` is ``schemas.plan.CLOSING_WINDOW_TOL``, the
        fraction an answer is measured at: no closing stage follows a stage run
        here, so its answer is computed on its own windows (WP-2002, the
        seventh round's Q1).  Pass ``forward.WINDOW_AREA_TOL`` for the declared
        stages' faster windows.  :meth:`cherry_pick` passes a recorded node's.
        The stage's ``window_area_tol`` records the fraction it ran at.
        """
        _refuse_without_phases(self.structure, "run_stage")
        phase_support_sigma = check_phase_support_sigma(phase_support_sigma)
        if window_area_tol is not None:
            try:
                window_area_tol = check_closing_window_tol(window_area_tol)
            except ValueError:
                raise ValueError(
                    f"window_area_tol is the fraction of each peak's area this "
                    f"stage's windows may drop, a number strictly between 0 and 1, "
                    f"or None for the default; got {window_area_tol!r}") from None
        else:
            window_area_tol = CLOSING_WINDOW_TOL
        require_two_theta(data, "Refinement.run_stage()",
                          instrument=self.instrument)
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
            stale_since = _anti_bump_start_phases(self.structure, mode)
            # the constructed (or last-edited) λ, not the value the previous stage
            # left behind: a second λ-freeing stage reports cumulatively, matching
            # the joint path, rather than a delta from its own predecessor (WP-1134).
            # Copied, never aliased (see fit's call site) — the snapshot stays the
            # construction fact whatever a reader does with the list it is handed.
            declared_wavelengths = list(self._declared_wavelengths)
            # WP-1343: asked here, before the solve, for the reason ``fit`` asks
            # it before its first stage — a single stage freeing a magnetic
            # width beside a cold moment is the same confound, and this is the
            # entry point a caller reaches for when they are driving the order
            # by hand.
            order = _stage_order_diagnostics(
                RefinementPlan(stages=[stage]), table, mode)
            order += _fixed_literal_diagnostics([stage], table, self._ties)
            try:
                with self._abandon_on_cancel(cancel, stage.name, [], stream):
                    model, outcome, guard, freed, hold = self._run_stage(
                        stage, data, mode, table, self._model, ttl, correlation_guard,
                        events=stream, cancel=cancel,
                        # no plan here, so no notion of an intermediate stage: one
                        # stage run on its own is the state the caller is asking
                        # for, and it takes its own ftol or the solver default
                        ftol=stage.ftol,
                        phase_support_sigma=phase_support_sigma,
                        window_area_tol=window_area_tol)
            finally:
                if (stream is not None and stream is not events
                        and stream is not recorder):
                    # ...and never the recorder, whose lifetime is the whole
                    # verb.  Closing it here wrote the run's terminal state
                    # before the result existed, so a stage that raised on the
                    # way out — or was cancelled, which reaches here with no
                    # ``fit_end`` to say so — recorded itself ``done``.
                    stream.close()  # we created it from a path/callable
            diagnostics = (self._drain_twin_findings() + order
                           + _guard_diagnostics(guard))
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
            if mode == "rietveld":
                diagnostics.extend(_restraint_pairs_stale_diagnostics(
                    self.structure, stale_since))

            stage_result = StageResult(
                name=stage.name, status=outcome.status, n_iterations=outcome.n_iterations,
                cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                freed=freed,
                n_constraint_truncations=outcome.n_constraint_truncations,
                n_degenerate_cell_probes=outcome.n_degenerate_cell_probes,
                n_lapack_fallbacks=outcome.n_lapack_fallbacks,
                ftol=stage.ftol, window_area_tol=window_area_tol,
                held=hold.held, released=hold.released,
                held_reach=hold.reach,
                scale_b_held=hold.scale_b_held,
                width_twins_held=hold.width_twins_held,
                moment_flat_axes=hold.moment_flat_axes,
                moment_turned=hold.moment_turned,
                blocked_by_hold=hold.blocked_by_hold,
                unknown_paths=hold.unknown_paths, unreached_histograms={},
                window_loss=hold.window_loss,
                seeded=hold.seeded, cell_reset=hold.cell_reset,
                collapsed=hold.collapsed,
                moment_angle_tests=outcome.moment_angle_tests)
            # after the StageResult rather than beside the other two extends
            # above, because this one reads the record it has just built; and
            # before the node, so the node carries what the result carries
            diagnostics.extend(_hold_diagnostics([stage_result],
                                                 table.origin_holds))
            diagnostics.extend(_origin_diagnostics(
                table, [stage_result], origins=[(stage.name, hold.origin)]))
            diagnostics.extend(_unknown_path_diagnostics(
                [stage_result], [e.path for e in table.entries]))
            diagnostics.extend(_window_loss_diagnostics([stage_result]))

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
                    window_area_tol=window_area_tol,
                    phase_support_sigma=phase_support_sigma,
                    correlation_guard=correlation_guard,
                ), model, table, outcome, diagnostics,
                    held_scales=_held_scale_phases(stage_result),
                    window_loss=stage_result.window_loss)

            # after the node, which keeps its as-optimised metrics: the result
            # is measured on a compile at the values it returns (#272)
            model, recompiled = self._final_compile(
                model, table, outcome, data, mode, ttl, stage, window_area_tol)
            diagnostics = diagnostics + recompiled
            self._model = model

            self.result_ = _build_result(
                model, table, outcome.theta, mode=mode, status=outcome.status,
                stage_results=[stage_result], diagnostics=diagnostics,
                structure=self.structure, stderr_internal=outcome.stderr_internal,
                esd_inflation=outcome.esd_inflation,
                correlation=outcome.correlation, backend=self._backend,
                solver=self._solver,
                mu_r_source=self._mu_r_source, mu_r_skipped=self._mu_r_skipped,
                guard=guard, max_shift_over_esd=outcome.max_shift_over_esd,
                declared_wavelengths=declared_wavelengths,
                significance=hold.significance,
                phase_support_sigma=phase_support_sigma)
            # beside result_, never at entry: a call that is cancelled or fails
            # leaves the previous result and the pattern it was fitted to
            self._fit_pattern = data
            self._plan_settings = {"correlation_guard": correlation_guard,
                                   "phase_support_sigma": phase_support_sigma,
                                   "window_area_tol": window_area_tol}
            _apply_esds(table, self.result_, self.structure, self.instrument)
            self._answer_covariance = (self.result_, table, outcome.theta,
                                       outcome.stderr_internal,
                                       outcome.correlation)
            self._answer = self._freeze_answer()
            self._stamp(self.result_, tree)
            if self._auto_intervals:
                # ``fit``'s rule (WP-2002, B2), on this stage's own record
                from .strategy.parameter_interval import (
                    attach_stationary_intervals,
                )

                attach_stationary_intervals(self, data, cancel=cancel)
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
        """Evaluate ``y_calc`` at the current parameters, without a fit.

        With a grid — an array of 2θ values, or a
        :class:`~rietx.PatternData` whose 2θ column is used — this compiles a
        fresh model on it and evaluates.  With no argument it evaluates on the
        grid the last fit ran on, which is the one form that needs a fit to
        have happened: nothing else supplies a grid.  That form evaluates the
        last result's answer on that result's model, so a later fit that is
        cancelled, keeping its completed stages, does not move it (WP-1421).

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

        **After a default fit the two forms agree bit for bit.**  ``predict()``
        evaluates the model the result was measured on, a compile at the
        answer (#272, WP-1421), so it returns ``RefinementResult.y_calc``; a
        grid compiles at the same values and windows.  Measured on the
        fluorapatite tutorial under ``mccusker_default``: 0 of 5751 channels
        differ.

        **The free set reaches the curve in one case** (#774).  With both
        axial-divergence ratios at exactly zero and either refined, the
        compile sizes the peak windows as if each were
        ``forward.AXIAL_SIZING_FLOOR``, so that a stage starting from zero
        has a derivative to follow; held at zero, the asymmetry is off and
        the windows are not widened.  The two curves differ by up to 4.8e-5
        of the strongest peak (the issue's rutile reproducer, 2026-10-25).
        Every positive value is sized by value alone.

        A grid compiles at ``compile_model``'s default windows whatever this
        object has fitted, so a never-fitted twin carrying the same models
        returns the same array.  That default is the closing stage's
        ``CLOSING_WINDOW_TOL`` (WP-2002, the seventh round's Q1), the windows a
        default fit measures its answer on, so a grid redraws a default fit's
        ``y_calc`` and a synthetic pattern carries the tails a default fit
        fits.  A plan with ``closing_window_tol=None`` measured its answer at
        the declared stages' ``forward.WINDOW_AREA_TOL`` instead; redraw it
        with ``compile_model(..., window_area_tol=recorded_window_tol(
        result.stages[-1].window_area_tol))``.
        """
        table = ParameterTable(self.structure, self.instrument)
        if two_theta is None:
            if self._model is None:
                raise RuntimeError(
                    "predict() with no grid evaluates on the grid the last fit "
                    "ran on, and this Refinement has not been fitted. Pass the "
                    "pattern (or a 2θ array) to evaluate the model as it "
                    "stands: ref.predict(data).")
            if self._answer is not None:
                # the answer frozen with the result, never the live models: a
                # later cancelled fit keeps its completed stages and this
                # result, as in report() (WP-1421)
                return self._model.evaluate(self._answer["values"])
            # the fitted model reads the moment DOFs in the last stage's frames
            table.pull_moment_frames(self._model)
            return self._model.evaluate(table.decode(table.x0()))
        if isinstance(two_theta, PatternData):
            require_two_theta(two_theta, "Refinement.predict()",
                              instrument=self.instrument)
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
        # the answer frozen with the result, never the live models: a later
        # cancelled fit keeps its completed stages and this result (WP-1421)
        answer = self._answer
        return build_report(self.result_, model=self._model,
                            values=answer["values"], plan=plan,
                            structure=answer["structure"],
                            instrument=answer["instrument"],
                            held=list(answer["held"]),
                            free_paths=list(answer["free_paths"]), **kw)

    def check_rigid_bodies(self, data: PatternData, **kw):
        """Test each rigid body against the data (``RIGID_BODY_MISFIT``).

        Refits every body as the body and as restrained free atoms, from this
        fitted state and under this refinement's declarations, and warns where
        the data reject the template's shape.  Needs a prior :meth:`fit`; not
        run inside it.  Keywords and the test:
        :func:`rietx.report.body_misfit.rigid_body_misfit`.
        """
        from .report.body_misfit import rigid_body_misfit

        require_two_theta(data, "Refinement.check_rigid_bodies()",
                          instrument=self.instrument)
        return rigid_body_misfit(self, data, **kw)

    def summary(self, *, deliverable: str | None = None, plot: str | None = None,
               plan: RefinementPlan | str | None = None,
               report: FitReport | None = None,
               levels: dict[str, str] | None = None) -> str:
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
        ``"phase_id"``, ``"qpa"``, ``"structure"``, ``"cell"``,
        ``"microstructure"``, ``"calibration"`` or ``"magnetic"``
        (:data:`rietx.purposes.PURPOSES` is the vocabulary).  The report will
        not infer your purpose for you: ``None`` (the default) prints the three
        stop conditions and nothing past them.  ``"series"`` is accepted and
        answers with where it is decided: a trajectory's deciding rows are
        the chain's, on
        :meth:`~rietx.schemas.sequential.SeriesResult.summary`, because no
        single pattern carries a ``SEQUENTIAL_*`` row.  It also decides which
        diagnostics print in full (WP-2037,
        :func:`~rietx.schemas.results.diagnostic_view`): under a deliverable
        the errors and the warnings for that purpose, the rest one line each;
        with none only the errors, every other row one line naming the
        purposes it is a warning under.  An unknown one is refused before
        anything is built.

        ``levels`` is the caller's per-code override,
        ``{code: "allow" | "warn" | "deny"}`` (WP-2037 clause 4,
        :func:`~rietx.schemas.results.diagnostic_view`): the caller's word
        replaces the audited level, and never lowers an error.  Its default,
        ``None``, overrides nothing.  An unknown code or word is refused before
        anything is built, as an unknown deliverable is.

        ``plot`` writes :func:`~rietx.viz.plots.plot_for_vlm` to that path and
        names it on the last line — the picture confirms the text, the text
        stays the criterion.  Without it, the line names the call instead.

        Requires the compiled model (call :meth:`fit` first); a caller holding
        only the result prints ``str(result)`` for the rows that need no
        model — see :meth:`~rietx.schemas.results.RefinementResult.__str__`.
        """
        if self._model is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        if deliverable is not None:
            # refused before the report is built, the expensive half of this call
            _check_deliverable(deliverable)
        _check_levels(levels)
        result = self.result_
        if report is not None and plan is not None:
            raise ValueError(
                "summary(plan=..., report=...): a report is built under its own "
                "plan, so pass the report or the plan, not both")
        if report is None:
            report = self.report(plan=plan)

        lines = [f"Refinement.summary: {result.status} ({result.mode})"]
        lines += _stage_lines(result.stages, result.statistics.max_shift_over_esd)
        lines += _diagnostic_lines(result.diagnostics, deliverable, levels=levels)
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
        # the report's own sentences, one a line; its abstention sentence
        # names the kind, so it is printed here once (WP-1985)
        lines = ["  report:"] + [f"    {line}" for line in report.summary.splitlines()]
        worst = sorted(report.regions, key=lambda r: r.chi2_share, reverse=True)[:3]
        for r in worst:
            lines.append(f"    region {r.two_theta_lo:.1f}-{r.two_theta_hi:.1f}°: "
                         f"{r.chi2_share:.0%} of χ², "
                         f"max|Δ|/σ={r.max_abs_delta_over_sigma:.1f}")
        stats = self.result_.statistics
        if stats.durbin_watson is not None:
            # the factor the rows carry, as the CIF quotes it: it can differ
            # from ``Statistics.esd_inflation`` by 0.07-4 % (WP-2002)
            carried = sorted({round(p.stderr / p.stderr_uncorrected, 2)
                              for p in self.result_.parameters
                              if p.stderr is not None and p.stderr_uncorrected})
            factor = (stats.esd_inflation if not carried
                      else carried[0] if len(carried) == 1 else None)
            note = (f", esds inflated ×{carried[0]:.2f}-{carried[-1]:.2f}"
                    if len(carried) > 1 else
                    f", esds inflated ×{factor:.2f}" if factor is not None else "")
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
            elif bg is not None:
                # said, because this row is the one that tells the two fits
                # apart (the docstring above) and its silence read as clean
                # an empty table has more causes than a missing target: a
                # non-finite block withholds it (WP-1130), a zero-norm or
                # non-finite target is skipped, and a scale driven through a
                # ``vars.`` name is not a target by spelling — so the line
                # names the one cause it can see and does not pick among them
                why = ("nothing on this result measured it"
                       if result.identifiability is None
                       else "the answer stage screened no scale, Biso, "
                            "occupancy or ADP column against a background "
                            "term")
                lines.append(f"    background.absorption: not measured ({why})")
            if result.qpa is not None:
                for row in result.qpa.phases:
                    if row.weight_fraction is None:
                        lines.append(f"    {row.name}: not measured ("
                                     f"{unmeasured_reason(result.qpa, row.name)})")
                        continue
                    esd = (f" ± {row.weight_fraction_stderr:.3f}"
                          if row.weight_fraction_stderr is not None else "")
                    lines.append(f"    {row.name}: {row.weight_fraction:.3f}{esd}")
                if result.qpa.unmeasured_phases:
                    lines.append("    fractions are relative to the phases "
                                 "seen in range; "
                                 + ", ".join(result.qpa.unmeasured_phases)
                                 + " not measured")
            else:
                lines.append("    qpa: none (Le Bail scales are degenerate)")
        elif deliverable == "structure":
            lines += _exchangeability_lines(result)
        elif deliverable == "cell":
            lines += _cell_lines(result)
            lines += _exchangeability_lines(result, about=".cell.")
        elif deliverable == "microstructure":
            lines += _microstructure_lines(result)
        elif deliverable == "calibration":
            lines += _calibration_lines(result)
        elif deliverable == "magnetic":
            lines += _magnetic_lines(result)
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
        last = self.result_.stages[-1] if self.result_.stages else None
        # the last stage's ``held`` carries every hold's columns; the ones the
        # scale-B test took are counted apart, read off its own record
        # (WP-1534).  A moment-direction hold still lands under the WP-1301
        # label, as it did before: no field names which held paths were its.
        ridge = ({c for cols in _scale_b_columns(last).values() for c in cols}
                 if last is not None else set())
        phase_unsupported = ([p for p in last.held if p not in ridge]
                             if last is not None else [])
        counts = ", ".join(f"{len(v)} {k}" for k, v in held.items() if v)
        if phase_unsupported:
            counts += (", " if counts else "") + \
                f"{len(phase_unsupported)} phase-unsupported (WP-1301)"
        if ridge:
            counts += (", " if counts else "") + \
                f"{len(ridge)} scale-B inseparable (WP-1534)"
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
        # the answer frozen with the result, as in report() (WP-1421)
        answer = self._answer
        return reflection_table(self._model, answer["values"], answer["structure"])

    def write_reflection_table(self, path, **kw) -> None:
        """Write the reflection table to CSV/TSV (delimiter from the suffix)."""
        from .io.exporters import write_reflection_table

        write_reflection_table(self.reflection_table(), path, **kw)

    def write_cif(self, path) -> None:
        """Write a refinement CIF: structure with esds, R-factors, wavelength,
        profile/background description, and the observed/calculated pattern.

        The pattern loop carries every point of the pattern the last fit was
        given, with weight 0 on the ones it did not fit, and the reflection loop
        each reflection's phase, d and |F|²."""
        from .io.cif.blocks import write_document
        from .io.exporters import refinement_cif_doc

        if self.result_ is None:
            raise RuntimeError("call fit() first")
        # the models frozen with the result, as the reflection loop below reads
        # them: a later cancelled fit moves the live ones and keeps this result
        answer = self._answer
        structure = self.structure if answer is None else answer["structure"]
        instrument = self.instrument if answer is None else answer["instrument"]
        write_document(refinement_cif_doc(self.result_, structure,
                                          instrument, pattern=self._fit_pattern,
                                          reflections=self.reflection_table()), path)

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
# The deciding rows of ``Refinement.summary(deliverable=…)`` (WP-2037): each a
# projection of fields the result already carries, never a computation, and a
# row nothing on this result measured says so rather than printing clean.

_CELL_UNITS = {"a": "Å", "b": "Å", "c": "Å", "alpha": "°", "beta": "°", "gamma": "°"}


def _moved(p: RefinedParameter) -> bool:
    """Whether a result row moved in the fit: a free row, or a tied one carrying
    an esd, which only a free source gives it.  A tied row whose sources were
    all held is listed too (the membership filter is "varied or tied") and
    carries none."""
    return p.vary or p.stderr is not None


def _cell_rows(result: RefinementResult) -> dict[int, list[RefinedParameter]]:
    """The cell rows that moved, by phase index."""
    by_phase: dict[int, list[RefinedParameter]] = {}
    for p in result.parameters:
        parts = p.path.split(".")
        if (len(parts) == 4 and parts[0] == "phases" and parts[2] == "cell"
                and parts[3] in _CELL_UNITS and _moved(p)):
            by_phase.setdefault(int(parts[1]), []).append(p)
    return by_phase


def _cell_lines(result: RefinementResult) -> list[str]:
    """``cell``: each phase's refined cell with esds, tied axes named, and the
    volume the whole covariance gives it (WP-1933)."""
    from ._display import _number

    rows = _cell_rows(result)
    if not rows:
        return ["    cell: no cell parameter refined on this fit; the cell is "
                "the model's as given"]
    volumes = {v.phase_index: v for v in result.cell_volumes or []}
    lines = []
    for i, ps in sorted(rows.items()):
        name = {p.path: p.path.rsplit(".", 1)[1] for p in ps}
        # a cell whose every row is tied (to a named variable) has no free row
        # to quote, so its tied rows carry the values instead
        quoted = [p for p in ps if p.vary] or ps
        text = ", ".join(f"{name[p.path]} = {_number(p.value, p.stderr)} "
                         f"{_CELL_UNITS[name[p.path]]}" for p in quoted)
        tied = [name[p.path] for p in ps if not p.vary]
        if tied:
            text += f" ({', '.join(tied)} tied)"
        if i in volumes:
            v = volumes[i]
            text += f"; V = {_number(v.volume, v.stderr)} Å³"
        lines.append(f"    phases.{i}.cell: {text.lstrip()}")
    return lines


def _exchangeability_lines(result: RefinementResult, about: str | None = None) -> list[str]:
    """The exchange rows, worst five: what ``structure`` and ``cell`` both
    decide on, since a held parameter the free ones imitate moves either.
    ``about`` keeps the rows naming a path containing it (``".cell."``), so a
    cell is not read against five rows of Biso exchanges."""
    if result.identifiability is None:
        return ["    identifiability: not measured on this result"]
    exch = result.identifiability.exchangeability
    if about is not None:
        exch = [row for row in exch
                if about in row.held or any(about in p for p in row.partners)]
    noun = "row(s)" if about is None else f"row(s) naming a {about.strip('.')} path"
    lines = [f"    exchangeability: {len(exch)} {noun}"]
    for row in exch[:5]:
        lines.append(f"      {row.held} ~ {', '.join(row.partners)} "
                     f"(R²={row.r2:.2f})")
    return lines


def _microstructure_lines(result: RefinementResult) -> list[str]:
    """``microstructure``: each phase's size and strain readings, under the
    code that says they are not quotable where it fired.  The readings stay
    printed beneath it, because a withheld verdict leaves its statistic
    (DESIGN.md § Rules, 1)."""
    if not result.microstructure:
        return ["    microstructure: not measured on this result"]
    lines = []
    if any(d.code == "RESOLUTION_UNCONSTRAINED" for d in result.diagnostics):
        # the code's own suggestion: "do not quote the widths, or any size or
        # strain read from them"
        lines.append("    size and strain: not quotable (RESOLUTION_UNCONSTRAINED); "
                     "the readings below are the fit's, not answers")
    return lines + ["    " + line for block in result.microstructure
                    for line in str(block).splitlines()]


def _calibration_lines(result: RefinementResult) -> list[str]:
    """``calibration``: the instrument terms the fit refined, and whether the
    standard's cell was held, which is what decorrelates the zero, the
    specimen position and the cell (``lab_calibrate``)."""
    rows = [p for p in result.parameters
            if p.path.startswith("instrument.") and _moved(p)
            and not p.path.startswith(("instrument.background.",
                                       "instrument.extra_components."))]
    lines = ([f"    {p}" for p in rows]
             or ["    instrument: no instrument parameter refined on this fit"])
    refined = sorted(_cell_rows(result))
    if refined:
        # which phase is the standard is the caller's to know: an internal
        # standard's sample refines its cell while the standard's is held
        names = ", ".join(f"phases.{i}" for i in refined)
        lines.append(f"    cell refined on {names}: a calibration holds the standard's "
                     "certified cell fixed (Refinement.hold); a sample's may refine")
    else:
        lines.append("    cell: held on every phase")
    return lines


def _magnetic_lines(result: RefinementResult) -> list[str]:
    """``magnetic``: each site's moment rows (the modulus carries the esd) and
    what the stages held or turned because a powder average cannot see it."""
    rows = [p for p in result.parameters
            if fnmatch.fnmatchcase(p.path, "phases.*.atoms.*.moment.*")
            or fnmatch.fnmatchcase(p.path, "phases.*.magnetic_lor_*")]
    if not any(".moment." in p.path for p in rows):
        return ["    moment: none refined on this fit "
                "(no phases.*.atoms.*.moment.* row)"]
    lines = [f"    {p}" for p in rows]
    held = ([p for p in result.stages[-1].held if ".moment." in p]
            if result.stages else [])
    if held:
        lines.append(f"    held, not measured: {', '.join(held)}")
    flat: dict[str, list[float]] = {}
    turned: set[str] = set()
    for stage in result.stages:
        flat.update(stage.moment_flat_axes)
        turned.update(stage.moment_turned)
    for site, axis in flat.items():
        how = (", turned onto the meridian first (the reported direction moved)"
               if site in turned else ", where it was")
        lines.append(f"    {site}: azimuth held about "
                     f"[{', '.join(f'{x:.3f}' for x in axis)}]{how}")
    return lines


#: Guard codes that are **discarded per stage and re-taken on the converged
#: vector** rather than accumulated (WP-1310 for the first, WP-1311 for the
#: other three).  Each reads a number straight off the values a stage landed
#: on, so it describes a *vector* and not a run: a plan exists to let an early
#: stage absorb an error a later one corrects, and an intermediate state's
#: finding on the final result is a claim about a fit that no longer holds.
#: Every stage's own copy stays on its ``StageReport`` and its history node.
#:
#: ``FLOOR_HIT`` is ``BOUND_HIT`` on a floor (WP-1929), the same claim about
#: the same vector, so it is re-taken the same way.  Left out, a scale pressed
#: onto 0 in stage 1 and back in the interior at convergence keeps its stage-1
#: warning on the final result, which is WP-1310's defect come back.
#:
#: ``RESOLUTION_UNCONSTRAINED`` belongs here on a second fact and not only on
#: that one: it also reads *which* terms the stage freed, and staging is
#: **cumulative** (``Refinement`` § stages), so a plan that frees U, V, W once
#: still has them free at the last stage and the final guard re-takes the
#: finding.  A plan that turned them back off would drop it, which is the
#: intended reading — held at instrumental values is the remedy the paper
#: prescribes, not the fault.
#:
#: ``COVARIANCE_DIRECTION_DISCARDED`` (WP-1535) is a claim about the esds of the
#: **answer-producing** solve, which are the only ones a result quotes.  An
#: intermediate stage's cut is a different matrix (cumulative staging adds
#: columns), and unkeyed it was appended once per stage, so one persistent
#: combination printed as many copies as the plan has stages.
#:
#: ``ADP_NOT_POSITIVE_DEFINITE``, ``STEPHENS_STRAIN_NOT_POSITIVE``,
#: ``TEXTURE_NOT_POSITIVE`` and ``HUMP_TOO_NARROW`` read values the stage landed
#: on too, and join on WP-2002's closing stage: it makes every plan's last
#: declared stage an intermediate one, so a finding that stage raised and the
#: closing stage cleared would otherwise reach the result as a claim about an
#: answer that does not hold it (the generality judge, 2026-10-21).
_REVISABLE_CODES = ("BOUND_HIT", "FLOOR_HIT", "RESOLUTION_NOT_POSITIVE",
                    "RESOLUTION_UNCONSTRAINED",
                    "BISO_UNUSUALLY_LARGE", "BISO_NEGATIVE",
                    "COVARIANCE_DIRECTION_DISCARDED",
                    "ADP_NOT_POSITIVE_DEFINITE", "STEPHENS_STRAIN_NOT_POSITIVE",
                    "TEXTURE_NOT_POSITIVE", "HUMP_TOO_NARROW")


#: ``FLOOR_HIT``'s advice: the limit that carried load is a lower bound of
#: exactly 0, or W's Γ_G² clamp (``staged._at_zero_floor``, WP-1938).  A scale
#: or a width cannot go negative, so ``BOUND_HIT``'s "widen the bound" is wrong
#: there, and WP-1929 gave the floor its own code to carry this instead.  A
#: caller's ``min=0`` on a displacement parameter reaches it too: the 11-BM NAC
#: acceptance fit declares one, and its Biso stops there.  So the reasons name
#: what a negative B stands in for (``BISO_NEGATIVE``'s list) beside the
#: scale's and the width's.
_ZERO_FLOOR_SUGGESTION = (
    "Quote an upper limit instead of a value, or remove the parameter if its "
    "phase or term is unsupported. For a displacement parameter, check "
    "absorption, species and occupancy.")


def _guard_diagnostics(guard) -> list[Diagnostic]:
    """Guard findings as diagnostics — one prose message per :class:`GuardFinding`.

    The paths come from ``finding.paths`` (WP-1007).  They used to come from
    ``msg.split(" ")[0]``, which worked for the single-path findings and produced
    *nothing* for a correlation, since its rendered form leads with no single
    path — so ``where`` was empty on exactly the finding a client most wants to
    make clickable.  ``finding.value`` rides along as ``Diagnostic.value``
    (WP-1003) for the same reason.  Each ``message`` is a sentence built around
    ``str(finding)``, which is the old list entry and is pinned byte for byte.
    """
    out: list[Diagnostic] = []
    for finding in guard.high_correlations:
        out.append(Diagnostic(
            level="warning", code="HIGH_CORRELATION",
            message=f"Correlated pair: {finding}.",
            where=list(finding.paths), value=finding.value,
            suggestion="Fix one of the two at a known value, or free them in "
                       "separate stages.",
        ))
    for finding in guard.at_bounds:
        path = str(finding)
        # the finding carries its code (``GuardFinding.at_bound``): a lower
        # limit of 0, or W's clamp, is a scale or width that cannot go
        # negative, which no wider bound can help (WP-1938, WP-1929)
        if finding.code == "FLOOR_HIT":
            out.append(Diagnostic(
                level="warning", code="FLOOR_HIT", where=list(finding.paths),
                value=finding.value,
                message=f"{path} refined to its floor{finding.detail}.",
                suggestion=_ZERO_FLOOR_SUGGESTION,
            ))
            continue
        out.append(Diagnostic(
            level="warning", code="BOUND_HIT", where=list(finding.paths),
            value=finding.value,
            message=f"{path} refined to its bound{finding.detail}.",
            suggestion="Widen the bound or fix the parameter.",
        ))
    for finding in guard.nonpositive_adps:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="ADP_NOT_POSITIVE_DEFINITE",
            where=list(finding.paths), value=finding.value,
            message=f"The anisotropic displacement tensor of {msg} is not "
                    "positive definite.",
            suggestion="Revert the site to an isotropic biso, check its "
                       "occupancy and species, or extend the fit range. Do "
                       "not report the tensor as measured.",
        ))
    for finding in guard.nonpositive_strain:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="STEPHENS_STRAIN_NOT_POSITIVE",
            where=list(finding.paths), value=finding.value,
            message=f"The Stephens strain coefficients of {msg} lie outside "
                    "the physical cone.",
            suggestion="Restart from the isotropic limit "
                       "(StephensStrain.isotropic), refine fewer patterns "
                       "(a higher-symmetry Laue class has fewer), or extend "
                       "the fit range. Do not report the S_HKL as measured.",
        ))
    for finding in guard.nonpositive_texture:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="TEXTURE_NOT_POSITIVE",
            where=list(finding.paths), value=finding.value,
            message=f"The spherical-harmonics texture of {msg} goes below "
                    "zero.",
            suggestion="Lower the order, or hold the highest-order terms. "
                       "Under solver='trf' switch to the default LM driver, "
                       "which holds P positive at the reflections.",
        ))
    for finding in guard.unsupported_resolution:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="RESOLUTION_UNCONSTRAINED",
            where=list(finding.paths), value=finding.value,
            message=f"{msg}.",
            suggestion="Calibrate on a standard with lab_calibrate (certified "
                       "cell held fixed) and save_instrument_profile, then "
                       "load_instrument_profile before this fit. Until then, "
                       "do not quote the widths, or any size or strain read "
                       "from them.",
        ))
    for finding in guard.flat_directions:
        out.append(Diagnostic(
            level="warning", code="FLAT_DIRECTION",
            where=list(finding.paths), value=finding.value,
            message=f"Flat direction: {finding}.",
            suggestion="Fix one at an independently known value and refine "
                       "the other, or free them in different stages, and say "
                       "in the result which one was held. Do not quote "
                       "either as measured from this fit.",
        ))
    for finding in guard.discarded_directions:
        out.append(Diagnostic(
            level="warning", code="COVARIANCE_DIRECTION_DISCARDED",
            where=list(finding.paths), value=finding.value,
            message=f"{finding.message}.",
            suggestion="Free fewer of these parameters in one stage, hold the "
                       "ones known independently, or widen the fitted range. "
                       "Do not quote their esds as measured from this fit.",
        ))
    for finding in guard.large_biso:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="BISO_UNUSUALLY_LARGE",
            where=list(finding.paths), value=finding.value,
            message=f"The displacement parameter {msg} is implausibly large.",
            suggestion="Check the species and occupancy on that site, the "
                       "absorption correction and the background flexibility "
                       "before you read it as motion. If the site is "
                       "genuinely mobile (a cavity cation, a superionic "
                       "sublattice), say so when you quote it.",
        ))
    for finding in guard.negative_biso:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="BISO_NEGATIVE",
            where=list(finding.paths), value=finding.value,
            message=f"The displacement parameter {msg} is below zero.",
            suggestion="Correct the likely cause (uncorrected absorption or "
                       "roughness, a wrong species or occupancy, a background "
                       "that bends at high angle), or hold B at a physical "
                       "value and say so in the result.",
        ))
    for finding in guard.nonpositive_resolution:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="RESOLUTION_NOT_POSITIVE",
            where=list(finding.paths), value=finding.value,
            message=f"{msg[:1].upper()}{msg[1:]} goes negative inside the "
                    "fitted range.",
            suggestion="Refit the resolution on a standard with its certified "
                       "cell held fixed (lab_calibrate), or hold a loaded "
                       "instrument profile instead of refining its widths on "
                       "this pattern. Do not report the widths, or the "
                       "microstructure derived from them.",
        ))
    for finding in guard.narrow_humps:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="HUMP_TOO_NARROW",
            where=list(finding.paths), value=finding.value,
            message=f"The declared background peak {msg} has narrowed "
                    "towards the instrumental resolution.",
            suggestion="Add a second phase for a real unindexed line, or read "
                       "the unmatched-peak report in the FitReport's Layer 0. "
                       "Do not report these peak parameters as measured.",
        ))
    for finding in guard.background_correlations:
        msg = str(finding)
        out.append(Diagnostic(
            level="warning", code="BACKGROUND_ABSORPTION",
            where=list(finding.paths), value=finding.value,
            message=f"The background can reproduce most of {msg}.",
            suggestion="Stiffen the background (fewer Chebyshev terms, a "
                       "larger P-spline lambda_smooth, coarser knots), or hold "
                       "an estimated curve additively.",
        ))
    for finding in guard.roughness_correlations:
        msg = str(finding)
        rough = any("surface_roughness" in p for p in finding.paths)
        out.append(Diagnostic(
            level="warning", code="ROUGHNESS_ABSORPTION",
            where=list(finding.paths), value=finding.value,
            message=(f"The displacement, scale and background block "
                     f"reproduces most of the roughness column {msg}."
                     if rough else
                     f"The surface-roughness block reproduces most of {msg}."),
            suggestion="Extend the fit to lower 2θ, where roughness has "
                       "leverage the displacement parameters lack, or hold "
                       "roughness at an independently measured value.",
        ))
    return out


_MAGNETIC_WIDTH_PATH = re.compile(
    r"^phases\.(\d+)\.magnetic_lor_(?:size|strain)$")


def _stage_order_diagnostics(plan, table,
                             mode: Mode) -> list[Diagnostic]:
    """``STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT`` — the ordering rule, checked
    against the plan **before the first stage runs** (WP-1343).

    A magnetic width and the moment it belongs to both lower the calculated
    peak's *height*: |F_m|² ∝ m² takes it down by shrinking the moment, and an
    extra Lorentzian width takes it down by spreading the same area.  Freed
    together from a cold start they trade against each other and the plan
    converges on whichever pair the first step happened to like — the same
    degeneracy the package already stages around for nuclear size/strain
    against scale, and the discipline ``mccusker_structural`` encodes.

    The order the package prescribes is **moment first with the widths held at
    zero, then the widths freed beside the converged moment, then both
    together** (cumulative, so the moment is not held in the middle stage)
    (``strategy.staged.MAGNETIC_WIDTH_STAGE_PATHS`` is that order as a stage
    list, and ``RefinementPlan.magnetic_width`` builds it).

    What is reported is precisely a stage that frees a magnetic width **in the
    same stage in which a moment DOF of the same phase is first freed**, from a
    width of zero: the order starts the widths held at zero, so a width that
    already has a value is a refit of a measured one (the finalising step of
    a converged fit), and the degeneracy the message describes is a cold
    start's.
    Staging is cumulative, so a width freed after the moment's own stage does
    not appear here — that is the prescribed order — and a width freed beside
    a moment that has already converged is the third step, which is fine.  The
    globs are expanded against the table's real paths rather than matched as
    text, so a plan written with ``phases.*.…`` is read exactly as the stage
    runner will read it.  What ``table`` already has free counts as freed
    before the first stage: ``fit`` hands it a table with everything held,
    ``run_stage`` one carrying the working state's free set.  And ``mode``
    is read as the stage runner reads it: under Le Bail and Pawley both the
    moment (an ``.atoms.`` path) and the widths are force-fixed after
    ``set_vary`` has matched them, so a stage naming both frees neither there.

    ``warning`` rather than ``error``: the plan is a caller's to write, the fit
    will run, and what this owes them is the name of the confound and the
    order that avoids it — not a refusal.
    """
    out: list[Diagnostic] = []
    # **What is already free is not being first freed.**  ``fit`` prepares its
    # table with everything held, so this is empty there; ``run_stage``
    # restores the free set the working state carries, so a hand-driven third
    # stage — the moment and the widths together after the moment's own stage
    # converged — reads as the step the order prescribes, not as a cold start.
    seen: set[str] = set(table.free_paths)
    start = table.decode(table.x0())
    for stage in plan.stages:
        # asked of the table, never restated here: ``would_free`` is
        # ``set_vary``'s own matcher, so a tied, locked or **held** row
        # (WP-1435) is skipped by the same predicate the stage runner uses,
        # and then the mode's force-fix, by the same column test
        # ``_run_stage`` drops with, so this cannot report a stage the mode
        # empties.  A hold the data decides later (``_hold_unsupported_phases``,
        # the flat-moment hold) is not seen here.
        freed = table.would_free(stage.turn_on)
        if mode in ("lebail", "pawley"):
            reach = table.column_reach()
            freed = [p for p in freed
                     if not mode_fixed_column(reach.get(p, [p]), mode)]
        new = [p for p in freed if p not in seen]
        seen.update(freed)
        widths = {m.group(1): p for p in new
                  if (m := _MAGNETIC_WIDTH_PATH.match(p))}
        moments = {p.split(".")[1] for p in new if _MOMENT_DOF.match(p)}
        for ip in sorted(set(widths) & moments):
            if float(start.get(widths[ip], 0.0)) > 0.0:
                continue            # a width already measured: not a cold start
            out.append(Diagnostic(
                level="warning", code="STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT",
                where=[widths[ip], f"phases.{ip}.atoms.*.moment.dof*"],
                message=(
                    f"Stage {stage.name!r} frees phase {ip}'s magnetic "
                    f"broadening in the same stage that first frees its "
                    f"moment."),
                suggestion=(
                    "Use the three-step order: the moment with the widths "
                    "held at zero, then the widths beside the converged "
                    "moment, then both together. Use plan=\"magnetic_width\" "
                    "or strategy.staged.MAGNETIC_WIDTH_STAGE_PATHS as stages.")))
    return out


def _moment_rung(table, outcome) -> dict[str, tuple[float, float | None]]:
    """Every moment **modulus** at this stage boundary: path → (|m|, esd).

    WP-1343.  The trajectory is where a released width's evidence
    lives (WP-1058, and WP-1073's rule that a correction's evidence is a rung
    rather than the endpoint), and the modulus is the only moment quantity
    with an esd — the crystal-axis components are derived and carry none
    (WP-1327).  ``abs`` because the modulus DOF is signed and its sign is a
    domain choice the powder cannot see.

    ``stderr_physical`` is asked for **only** on a stage that touched a moment
    or a magnetic width, which is why this costs an ordinary fit nothing: with
    a correlation matrix that call builds a dense n x n, and a Pawley table
    would make it large.
    """
    values = table.decode(outcome.theta)
    # **Tied followers are excluded.**  The child asymmetric unit of a k != 0
    # supercell lists each orbit twice (the anti-translation pair), and a
    # caller tying two orbits equal (a published constraint is often exactly
    # that) makes three of four modulus rows followers of one master.  All four
    # carry the same value and the same esd, so keeping them would repeat one
    # measurement four times in the diagnostics list; the untied row *is* the
    # measurement, which is the same reading ``stderr_physical`` takes when it
    # reports a tie's esd as its source's.
    paths = [e.path for e in table.entries
             if _MOMENT_DOF.match(e.path) and e.path.endswith(".dof0")
             and e.tie is None]
    if not paths:
        return {}
    esds: dict[str, float] = {}
    if outcome.stderr_internal is not None:
        esds = table.stderr_physical(outcome.theta, outcome.stderr_internal,
                                     outcome.correlation)
    return {q: (abs(float(values[q])), esds.get(q)) for q in paths}


def _moved_moment_diagnostics(stage_name: str, off_state: dict, released: dict,
                              widths: dict) -> list[Diagnostic]:
    """``MAGNETIC_WIDTH_MOVED_MOMENT`` — the preset already holds the answer.

    WP-1343's thesis is that **the moment pays for a missing width**, and the
    three-step order measures exactly that twice: step 1 fits the moment with
    the widths at their off state, step 3 fits it with them free.  The shift
    between those two rungs is the measurement, and it is a different question
    from whether the width is significant — which is why
    ``MAGNETIC_WIDTH_UNMEASURED`` can be right and misleading at the same
    time.

    The two can disagree: a width that comes back at 1.3 of its own esd is
    "unmeasured" by the support ratio, while releasing it can still move the
    moment by more than the moment's esd.  Reading the ratio alone there
    licenses dropping the term, and dropping it puts the moment back where the
    off-state stage had it — the bias this rung exists to stop.

    The shift is quoted in units of ``min(esd_off, esd_released)`` — see
    :data:`~rietx.report.schemas.MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA` for why
    the tighter of the two is the yardstick.
    """
    out: list[Diagnostic] = []
    for path, (m1, e1) in sorted(off_state.items()):
        if path not in released:
            continue
        m3, e3 = released[path]
        bars = [e for e in (e1, e3) if e is not None and e > 0.0]
        if not bars:
            continue
        z = abs(m3 - m1) / min(bars)
        if z <= MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA:
            continue
        wtxt = ", ".join(
            f"{q} = {v:.4g}" + ("" if e is None else f" +- {e:.4g}")
            for q, (v, e) in sorted(widths.items()))
        out.append(Diagnostic(
            level="warning", code="MAGNETIC_WIDTH_MOVED_MOMENT",
            where=[path, *sorted(widths)], value=float(z),
            message=(
                f"Releasing this phase's magnetic broadening moved |m| from "
                f"{m1:.4g}"
                + ("" if e1 is None else f" +- {e1:.4g}")
                + f" with the widths held at zero to {m3:.4g}"
                + ("" if e3 is None else f" +- {e3:.4g}")
                + f" with them free in stage {stage_name!r}. The shift is "
                f"{z:.2f}x the tighter of the two esds. The widths are "
                f"{wtxt}."),
            suggestion=(
                "Quote |m| from the stage that freed the widths, and report "
                "the width as an upper bound (value + esd). Do not drop the "
                "width on the strength of MAGNETIC_WIDTH_UNMEASURED.")))
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
            f"{worst.message} Flagged in stages: {', '.join(stage_names)}.")
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
    counts are on their :class:`StageResult` rows, but a constrained step
    there shaped an intermediate state, not the reported values.  ``info`` rather
    than ``warning`` — landing on the cone face is what the constrained driver
    is *for* (the admissible optimum), but an agent must know the constraint
    was active rather than merely declared, because an active face means the
    coefficients are admissible, not measured (WP-0601: they still span
    ~100 % across starting seeds under both drivers).
    """
    n = getattr(outcome, "n_constraint_truncations", 0)
    if not n:
        return []
    # which block bound each step, by its label (WP-1938 D7): the Stephens
    # cone's end in ``.microstrain``, the Γ_G² floor's start with
    # ``instrument.profile``
    by = getattr(outcome, "truncated_by", None) or {}
    which = "; ".join(f"{label}: {k}" for label, k in sorted(by.items()))
    suggestion = ("Vary the starting seed and quote the values only if they "
                  "survive.")
    if any(label.endswith(".microstrain") for label in by):
        suggestion += (" The STEPHENS_STRAIN_NOT_POSITIVE protocol row "
                       "applies to the strain cone, although that guard stays "
                       "silent while the default LM driver holds the cone.")
    if any(label.startswith("instrument.profile") for label in by):
        suggestion += (" At some reflection the data asked for no Gaussian "
                       "width (the Γ_G² floor, 1e-8 deg²), so U, V, W and the "
                       "phase's Gaussian size and strain describe that floor.")
    return [Diagnostic(
        level="info", code="CONSTRAINT_ACTIVE",
        message=(f"The bounded-LM driver held {n} step(s) on a linear "
                 f"inequality constraint"
                 + (f" ({which})" if which else "")
                 + f" in stage {stage_name!r}."),
        suggestion=suggestion,
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
        consequence = ("Every esd, correlation and derived uncertainty on "
                       "this result is absent (None).")
        suggestion = ("Fix or restrain the most correlated parameters, refit "
                      "from the returned values, and quote the esds from "
                      "that fit.")
    else:
        consequence = ("This intermediate stage's guards ran without a "
                       "covariance.")
        suggestion = None
    return [Diagnostic(
        level="warning", code="COVARIANCE_UNAVAILABLE", where=[stage_name],
        message=(f"Stage {stage_name!r} returned ({outcome.status}), but its "
                 f"esd computation raised {error}. {consequence}"),
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
        message=(f"The search reached {total} degenerate cell trial(s) "
                 f"(zero or negative volume) in stage(s) "
                 f"{', '.join(repr(n) for n in where)} and pushed each one "
                 "back out."),
        where=where, value=float(total),
    )]


def _origin_diagnostics(table: ParameterTable,
                        stage_results: list[StageResult] | None = None, *,
                        canonical=None,
                        origins: Iterable[tuple[str, CompiledOrigin | None]]
                        | None = None) -> list[Diagnostic]:
    """``ORIGIN_FIXED_ON_POLAR_AXIS`` and ``ORIGIN_NOT_FIXED``, read off the table.

    The table is the authority for what it holds and why
    (``ParameterTable.origin_holds``/``origin_unfixed``, WP-1912), so this
    only words it: per phase, the space group, each floating direction, and
    the atom whose DOF holds it.

    With ``stage_results`` (a fit) a phase is reported only where its fix
    mattered, which is where a stage freed a column that moves one of the
    phase's coordinates.  That is read off the table's reach
    (``ParameterTable.entry_reach``), never off DOF names, so a named variable
    driving the DOFs counts and a Le Bail stage, whose coordinates the mode
    force-fixes out of ``freed``, does not (root CLAUDE.md, "a freeze resting on
    flatness needs the other reading of C").  A hold is reported where such a
    stage's ``turn_on`` also matched it (``StageResult.blocked_by_hold``), an
    unfixed direction wherever such a stage ran.  Without stage results
    (:meth:`Refinement.hold_floating_origin`) every declaring phase that holds
    or cannot hold is reported, that being the question the verb asks.

    ``canonical`` is a joint fit's (``multi._joint_origin_findings``): the
    name a held row carries in the joint fit, for ``where`` and the message.

    ``origins`` is ``(stage name, model.origin)`` per stage, the restraint a
    ``"centroid"`` phase's stages ran with (Flack & Schwarzenbach 1988).  A
    phase one of them restrained gets one ``ORIGIN_FIXED_ON_POLAR_AXIS``,
    worded from the **last** such stage: its weights are the ones the answer's
    covariance was read with.  A stage that could not slide the phase built
    no row, so it says nothing, which is the hold's "only where it mattered"
    read off the restraint itself.
    """
    name = canonical or (lambda p: p)
    phases = table.origin_phases
    if not phases:
        return []
    holds = table.origin_holds
    unfixed = table.origin_unfixed
    reach = table.entry_reach() if stage_results is not None else {}
    # phase → (every stage that restrained it, the last one's rows)
    restrained: dict[int, tuple[list[str], OriginPhaseRows]] = {}
    for stage_name, block in origins or ():
        for rows_of in (block.phases if block is not None else ()):
            stages = restrained.get(rows_of.phase, ([], None))[0]
            restrained[rows_of.phase] = ([*stages, stage_name], rows_of)
    out: list[Diagnostic] = []
    for ip, rec in sorted(phases.items()):
        if ip in restrained:
            out.append(_centroid_finding(rec, *restrained[ip], name))
        held = [p for f in rec.directions for p, (jp, g) in holds.items()
                if jp == ip and g == f]
        rows = set(rec.coords) | set(rec.labels)
        moving = [sr for sr in stage_results or []
                  if any(rows.intersection(reach.get(p, [p])) for p in sr.freed)]
        if stage_results is None:
            report_held, report_lost = bool(held), True
        else:
            report_held = any(set(held) & set(sr.blocked_by_hold) for sr in moving)
            report_lost = bool(moving)
        if held and report_held:
            axes = ", ".join(str(list(holds[p][1])) for p in held)
            named = ", ".join(f"{name(p)} ({rec.labels[p]})" for p in held)
            out.append(Diagnostic(
                level="info", code="ORIGIN_FIXED_ON_POLAR_AXIS",
                message=(f"Phase {ip} ({rec.space_group}) has a floating "
                         f"origin along {axes}, and {named} "
                         f"{'is' if len(held) == 1 else 'are'} held."),
                where=[name(p) for p in held],
                suggestion=("Call unhold() to let the whole structure slide "
                            "again. The fit then has a flat direction "
                            "(FLAT_DIRECTION).")))
        lost = unfixed.get(ip, [])
        if lost and report_lost:
            axes = ", ".join(str(list(f)) for f in lost)
            out.append(Diagnostic(
                level="warning", code="ORIGIN_NOT_FIXED",
                message=(f"Phase {ip} ({rec.space_group}) floats along {axes}, "
                         f"and no atom has an untied, unheld coordinate DOF "
                         f"that a shift along it moves."),
                where=[f"phases.{ip}"],
                suggestion=("Call hold() on what the tied coordinates follow "
                            "(a variable, say), or tie one of them to a "
                            "constant.")))
    return out


#: how many sites ``ORIGIN_FIXED_ON_POLAR_AXIS`` names with their weights
#: before it counts the rest
_CENTROID_SITES_NAMED = 12


def _centroid_finding(rec, stages: list[str], rows: OriginPhaseRows,
                      name) -> Diagnostic:
    """``ORIGIN_FIXED_ON_POLAR_AXIS`` for a phase a centroid restraint fixed.

    Names what the restraint was built from: the phase, the space group, the
    directions, the stages, and each site with its normalised coefficient
    aₙ/Σa in the last of them (Flack & Schwarzenbach 1988, eq 9's weights,
    from eq 21), plus the clip where (A5) had no solution.  ``where`` is the
    DOFs a shift along the directions moves, the coordinates the restraint
    ties together.  Each stage restrains its own weighted centroid to where
    that stage began, and the restrained solve keeps eq 9 (eq 11); the weights
    are re-measured per stage, so the origin is fixed within each solve, not
    pinned to where the first stage began.
    """
    axes = ", ".join(str(list(f)) for f in rows.axes)
    share = rows.a / rows.a.sum()
    named = [f"{label} {w:.3f}" for label, w in zip(rows.labels, share,
                                                      strict=True)]
    if len(named) > _CENTROID_SITES_NAMED:
        named = named[:_CENTROID_SITES_NAMED] + [
            f"and {len(named) - _CENTROID_SITES_NAMED} more"]
    message = (f"Phase {rows.phase} ({rows.space_group}) has a floating origin "
               f"along {axes}. {_stage_list(stages).capitalize()} "
               f"restrained the weighted centroid of its sites to where it "
               f"stood (Flack & Schwarzenbach 1988), with weights "
               f"{', '.join(named)}. Every coordinate along it is refined and "
               f"keeps an esd.")
    if rows.clipped is not None:
        message += (f" No weighting met eq 21 exactly: (A5) fails because "
                    f"{rows.clipped}'s curvature exceeds the others' "
                    f"combined. {rows.clipped} was clipped to just below "
                    f"them, so the restraint is close to a hold on "
                    f"{rows.clipped}.")
    elif not rows.converged:
        message += (" The weights met eq 21 only approximately. This changes "
                    "the spread of the esds and leaves the fixed origin "
                    "alone.")
    where = list(dict.fromkeys(name(p) for f in rows.axes
                               for p in rec.candidates[f]))
    return Diagnostic(
        level="info", code="ORIGIN_FIXED_ON_POLAR_AXIS",
        message=message, where=where,
        suggestion=("Set Phase.floating_origin to 'hold' to quote the "
                    "coordinates against one atom, or to None to let the "
                    "structure slide (FLAT_DIRECTION)."))


def _hold_diagnostics(stage_results: list[StageResult],
                      origin: Iterable[str] = ()) -> list[Diagnostic]:
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

    ``origin`` names the paths the table holds to fix a floating origin
    (``ParameterTable.origin_holds``, WP-1912).  They stay on
    ``StageResult.blocked_by_hold``, being holds that blocked a glob, and are
    left out here: :func:`_origin_diagnostics` reports them, with the
    direction and the atom, and its advice differs from this one's.
    """
    skip = set(origin)
    by_path: dict[str, list[str]] = {}
    for sr in stage_results:
        for path in sr.blocked_by_hold:
            if path not in skip:
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
                 f"{', '.join(where[:5])}{'…' if n > 5 else ''}."),
        where=where, value=float(n),
        suggestion="Call unhold() on them first if you meant the plan to refine them.",
    )]


#: an atom's coordinate, which a site-symmetry table drives through
#: ``….dof.k`` rather than freeing directly
_COORDINATE_PATH = re.compile(r"^(phases\.\d+\.atoms\.\d+)\.[xyz]$")


def _stage_list(names: list[str]) -> str:
    """``stage 'a'`` or ``stages 'a', 'b'``, for a per-path diagnostic."""
    return (f"stage {names[0]!r}" if len(names) == 1 else
            f"stages {', '.join(repr(s) for s in names)}")


def _fixed_literal_diagnostics(stages, table: ParameterTable, user_ties, *,
                               canonical=None) -> list[Diagnostic]:
    """``STAGE_PATH_NOT_FREE`` — a literal phase path the model will not free.

    ``STAGE_PATH_UNKNOWN``'s other half.  A literal names one parameter, and
    when the model has that row but it is locked or follows a symmetry tie,
    ``set_vary`` declines it in silence: the stage frees nothing for it,
    converges, and the result looks like any other.  The measured case is an
    oxygen on 16h in I4₁/amd: ``phases.0.atoms.2.x`` is fixed at 0 and ``y``
    and ``z`` follow ``…dof.0``/``…dof.1``, so a stage naming a coordinate
    left the site where it started.  The message names the paths that would
    have freed it.

    **Phase paths only.**  The shipped presets name instrument literals that
    are locked on some geometries by design (``sample_displacement`` on a
    capillary), and a preset reaching a component a model lacks is the
    healthy miss ``STAGE_PATH_UNKNOWN`` stays silent on for patterns.  No
    preset names a phase literal.  **Not a user tie** either: that is the
    caller's own declaration, and its row says so.

    **Silent when the stage frees the tie's sources itself**: ``cell.a`` and
    ``cell.b`` named together on a cubic phase free ``a``, and ``b`` follows.

    A plan read, decided before the first stage like
    :func:`_stage_order_diagnostics`, and one diagnostic per path naming its
    stages, for :func:`_unknown_path_diagnostics`' reason.

    ``canonical`` is a joint fit's (#803, WP-1341): the second name a row
    answers to in a :class:`~rietx.params.multi.MultiParameterTable`, bare
    when shared and ``hist.<h>.``-scoped when not.  A literal then matches a
    row exactly when ``MultiParameterTable.set_vary`` would match it, and
    ``where`` and the suggestion name rows as the joint result spells them.
    A single fit's row has one name and passes nothing.
    """
    name_of = canonical or (lambda p: p)
    by_path = {e.path: e for e in table.entries}
    by_name = dict(by_path)
    by_name.update({name_of(e.path): e for e in table.entries})
    asked: dict[str, tuple[str, list[str]]] = {}
    for stage in stages:
        for glob in stage.turn_on:
            entry = by_name.get(glob)
            if (entry is None or not is_literal_path(glob)
                    or not entry.path.startswith("phases.")
                    or entry.path in user_ties
                    or not (entry.locked or entry.tie is not None)):
                continue
            if entry.tie is not None and all(
                    any(fnmatch.fnmatchcase(src, g)
                        or fnmatch.fnmatchcase(name_of(src), g)
                        for g in stage.turn_on)
                    for src, _ in entry.tie.terms):
                # the same stage frees every source it follows, so it did
                # get what it named: ``cell.a`` and ``cell.b`` side by side
                continue
            _, names = asked.setdefault(entry.path, (glob, []))
            if stage.name not in names:
                names.append(stage.name)
    out = []
    for row, (path, names) in asked.items():
        which = _stage_list(names)
        entry = by_path[row]
        sources = ([] if entry.tie is None else
                   [name_of(src) for src, _ in entry.tie.terms])
        why = ("is fixed by symmetry or by the model" if entry.locked else
               f"follows {', '.join(sources)}")
        site = _COORDINATE_PATH.match(row)
        dofs = ([name_of(p) for p in by_path
                 if p.startswith(f"{site.group(1)}.dof.")] if site else [])
        if site and dofs:
            fix = (f"Free {name_of(site.group(1))}.dof.* ({', '.join(dofs)}) "
                   "instead.")
        elif site:
            fix = None      # every coordinate of the site is fixed by symmetry
        elif sources:
            fix = f"Free {', '.join(sources)} instead."
        elif canonical is None:
            fix = "Read held_because for this row in ref.parameters()."
        else:
            # a joint fit has no parameters() to point at
            fix = None
        out.append(Diagnostic(
            level="warning", code="STAGE_PATH_NOT_FREE",
            message=(f"{which[:1].upper()}{which[1:]} asked for {path}, which "
                     f"{why}, so nothing was freed for it."),
            where=[name_of(row)], suggestion=fix))
    return out


def _window_loss_diagnostics(stage_results: list[StageResult]) -> list[Diagnostic]:
    """``STAGE_WINDOWS_STALE``: a stage ended on frozen windows dropping more
    of the Bragg intensity than its compile allows each peak.

    WP-2047.  A stage sizes its windows when it compiles, so a peak that moves
    or broadens while it solves spills past them, and the frozen model then
    rewards that direction with a χ² it does not have.  On the QPA round-robin
    chain before WP-2045 the warm stage reached ``axial_sl`` 558 that way,
    "converged", with its windows dropping 73 % of the intensity.  The
    threshold is the stage's own window tolerance, so no number is new; the
    four acceptance protocols' stages stay at or under 1.73 % against 2 %.

    ``warning``, and only on the stages whose answer reaches the result with
    at most one refit: the last stage, and the one before it when the last is
    the plan's closing stage.  Every stage records its loss, but an earlier
    one is refitted from its answer on fresh windows by every stage after it,
    and that repaired the one stale earlier stage measured: the calibrate
    guide's ``sample_profile`` stage frees the sample broadening from zero and
    ends at 12 %, and the guide's size lands within its esd of the truth.  The
    runaway above was the last declared stage, which only the closing stage
    refits, and that did not repair it.  One per stage, since each compiled
    its own windows.  ``FROZEN_COMPILE_STALE`` is the last stage's χ² read at
    the result, and misses half of the runaway, where frozen and fresh fit
    equally badly.
    """
    # the closing stage is the one a plan appended: its name, and a recorded
    # fraction, which no declared stage of a plan carries (``None``); the name
    # alone would take a user's own last stage called "closing" for it
    reach = stage_results[-1:]
    if (len(stage_results) > 1 and stage_results[-1].name == CLOSING_STAGE_NAME
            and stage_results[-1].window_area_tol is not None):
        reach = stage_results[-2:]
    out = []
    for sr in reach:
        tol = recorded_window_tol(sr.window_area_tol)
        if sr.window_loss is None or not sr.window_loss > tol:
            continue
        out.append(Diagnostic(
            level="warning", code="STAGE_WINDOWS_STALE",
            message=(f"Stage {sr.name!r} ended with its peak windows, sized "
                     f"where it started, dropping {100 * sr.window_loss:.3g} % "
                     "of the Bragg intensity that windows sized at its answer "
                     f"hold, against the {100 * tol:.3g} % each window may "
                     "drop. Its peaks moved or broadened past the windows it "
                     "was solved on, so its answer may fit that loss rather "
                     "than the data."),
            value=sr.window_loss,
            suggestion=("Refit from starting values nearer the data, and do "
                        "not polish this answer: on the case measured, a "
                        "further stage from it ran further away."),
        ))
    return out


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

    **One pattern can be told apart too: one under a retired spelling.**
    WP-1102 renamed ``instrument.background_peaks`` to
    ``instrument.extra_components``.  A stored plan is migrated as it is read,
    but ``Stage("hump", ["instrument.background_peaks.*"])`` written in code is
    not, and it froze a declared hump at its seed in silence, where the class
    and the attribute under the old names both raise.  The retired name is
    :mod:`rietx.schemas.migrate`'s to know
    (:func:`~rietx.params.vector.retired_spelling`), and such a path is named
    here with its current spelling in place of the nearest-path guess, which
    for that literal was ``instrument.background.c0``.

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
        which = _stage_list(stages)
        current = retired_spelling(path)
        if current is not None:
            out.append(Diagnostic(
                level="warning", code="STAGE_PATH_UNKNOWN",
                message=(f"{which[:1].upper()}{which[1:]} asked for {path}, a "
                         "spelling retired after v1.2, so nothing was freed "
                         f"for it. The current spelling is {current!r}."),
                where=[path],
                suggestion=f"Write {current!r} in the plan.",
            ))
            continue
        hint = did_you_mean(path, known, n=1)
        out.append(Diagnostic(
            level="warning", code="STAGE_PATH_UNKNOWN",
            message=(f"{which[:1].upper()}{which[1:]} asked for {path}, which "
                     "names no parameter of this model, so nothing was freed "
                     "for it."
                     + (f" {hint[:1].upper()}{hint[1:]}" if hint else "")),
            where=[path],
            suggestion=(f"Correct the path ({listing} lists every path this "
                        "model has), or write a glob if the stage should "
                        "reach a component that only some models declare."),
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


#: Why the composition estimator declines on a source it has no table for.
#:
#: Attenuation is a property of the radiation, not a coarse or fine version of
#: one number: X-ray µ/ρ (McMaster, :mod:`rietx.crystallography.attenuation`)
#: rises roughly as λ³ (falls as E⁻³) between edges and has edges at all,
#: while neutron attenuation is σ_abs(λ) + σ_coh + σ_inc, σ_abs linear in λ
#: (the 1/v law), and hydrogen is nearly transparent to one and among the
#: strongest attenuators of the other.  So each source kind needs *its own* table
#: (:data:`rietx.optimize.qpa.LINEAR_ATTENUATION_BY_SOURCE`: X-ray, and
#: constant-wavelength neutron from Sears 1992 since WP-1132), and a kind with
#: none declines here rather than borrowing another radiation's — writing the
#: wrong quantity into ``Geometry.mu_r`` would apply a confidently wrong
#: correction with nothing said, the outcome the docstring below calls the
#: worst of the three.  This fence is what made WP-1132 visible and it stays
#: for every kind still without a table: a time-of-flight bank spans a range
#: of λ, so one µ per histogram is not even well defined there.  An explicit
#: ``mu_r``/``mu_t`` is always honoured, whatever the source.
_NO_ATTENUATION_TABLE_ESTIMATE = (
    "there is no attenuation table for this source kind, so the composition "
    "estimator cannot run; declare Geometry.mu_r (capillary) or Geometry.mu_t "
    "(flat plate) explicitly"
)


def _has_attenuation_table(instrument: Instrument) -> bool:
    """Whether the composition estimator has a table for this source kind."""
    return instrument.source.kind in LINEAR_ATTENUATION_BY_SOURCE


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
        # Asked *after* the explicit-value check, so declaring µR on a source
        # with no table still works — only the estimate is fenced off, not the
        # correction (:data:`_NO_ATTENUATION_TABLE_ESTIMATE`).
        if not _has_attenuation_table(instrument):
            return "estimated", _NO_ATTENUATION_TABLE_ESTIMATE
        table = ParameterTable(structure, instrument)
        mu_r, reason = estimate_capillary_mu_r(
            structure, table.decode(table.x0()),
            instrument.source.primary_wavelength,
            geom.capillary_radius_mm, geom.packing_fraction,
            source_kind=instrument.source.kind)
        if mu_r is None:
            return "estimated", reason
        geom.mu_r = mu_r
        return "estimated", None

    if geom.thickness_mm is None or geom.mu_t is not None:
        return "given", None
    if not _has_attenuation_table(instrument):
        return "estimated", _NO_ATTENUATION_TABLE_ESTIMATE
    table = ParameterTable(structure, instrument)
    mu_t, reason = estimate_flat_plate_mu_t(
        structure, table.decode(table.x0()),
        instrument.source.primary_wavelength,
        geom.thickness_mm, geom.packing_fraction,
        source_kind=instrument.source.kind)
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
    if values is not None and model.line_wavelengths:
        # the λ the Bragg angles below are found at (WP-1976), so the
        # sin²θ basis and ΔB = β·λ²/2 read one wavelength
        lam = model.line_lambdas(values)[0]
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
    positions = _reflection_bragg_angles(model, values)
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


def _reflection_bragg_angles(model: CompiledModel,
                             values: dict[str, float] | None) -> np.ndarray:
    """Bragg 2θ of every modelled reflection drawn in range, primary line.

    Where an intensity correction is *judged* — never on the fitted grid, which
    can start far below the first peak and make a correction look enormous that
    no modelled reflection ever experienced (WP-0502 measured exactly that on
    the round-robin patterns).

    Two angles per reflection, and each test takes its own.  *Which*
    reflections count is read at the drawn angle, because that is where the
    pattern shows them.  The value returned is the Bragg angle, because the
    forward model evaluates absorption and roughness there (``phase_peaks``
    passes ``tt_bragg``).  Until WP-1976 this returned the drawn
    angle, so a refined displacement judged both corrections at angles no
    reflection was corrected at.
    """
    if not model.phases or not model.line_wavelengths or values is None:
        return np.empty(0)
    out = []
    for ip in range(len(model.phases)):
        bragg, drawn = (np.asarray(a, dtype=np.float64)
                        for a in model.reflection_angles(ip, values)[0])
        keep = (np.isfinite(bragg) & np.isfinite(drawn)
                & (drawn >= model.tt_min) & (drawn <= model.tt_max))
        out.append(bragg[keep])
    return np.concatenate(out)


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
    a degeneracy the fit walks along while Rwp *improves*, and the cell moves
    5111 ppm with no bound to stop it (1097 ppm while a ±1 mm default bound
    did, until WP-2002).  So they stay report-driven, and this says only that
    the door is shut and which field opens it.

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
        message=("This capillary geometry declares no goniometer radius, so the "
                 "eq (4) specimen-offset aberrations are held at zero."),
        suggestion=("Set instrument.geometry.goniometer_radius_mm if you "
                    "know the diffractometer's."))]


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
                     + f" could not be estimated ({record.skipped}). The "
                     "pattern was fitted with no absorption correction."),
            suggestion=(f"Set {where[0]} explicitly, measured or computed by "
                        "hand for this specimen. On an X-ray source, a "
                        "wavelength away from an absorption edge of the "
                        "specimen also lets the estimate run.")))
    if record.out_of_range:
        out.append(Diagnostic(
            level="warning", code="ABSORPTION_MU_R_OUT_OF_RANGE", where=where,
            message=(f"µR = {record.mu_r:.2f} is outside the range of the "
                     f"Rouse et al. (1970) fit (µR ≤ {CYLINDER_MU_R_MAX:g})."),
            suggestion=("Dilute the specimen, use a narrower capillary, or "
                        "use a shorter wavelength. Call rietx.estimate_mu_r() "
                        "to see what each choice buys.")))
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
                     "reproducible by the scale and the displacement "
                     "parameters."),
            suggestion=("Measure the specimen thickness and packing density "
                        "instead of assuming nominal values.")))
    if record.method == "flat_plate_transmission" \
            and record.intensity_fraction_of_optimal is not None \
            and record.intensity_fraction_of_optimal < 0.7:
        out.append(Diagnostic(
            level="info", code="ABSORPTION_PLATE_THICKNESS", where=where,
            message=(f"This transmission plate (µt = {record.mu_r:.3f}) "
                     f"delivered "
                     f"{100 * record.intensity_fraction_of_optimal:.0f} % of the "
                     "counts it could have at µt = 1.")))
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


def _radiation(model: CompiledModel, values: dict[str, float]) -> Radiation:
    """The source a result's curves were fitted with (WP-2042): the compiled
    kind and each line's λ at ``values``, so a refined wavelength is recorded
    as refined.  One builder for both result writers, the single fit's and
    the joint fit's per histogram."""
    return Radiation(kind=model.source_kind,
                     wavelengths=[float(lam) for lam in model.line_lambdas(values)])



def _phase_texture(model: CompiledModel, values: dict[str, float],
                   structure: Structure) -> list[PhaseTexture]:
    """J and the two minima of P per textured phase at the answer (WP-1960).

    The writer :class:`~rietx.schemas.results.PhaseTexture` names.  Empty
    outside Rietveld mode, where no phase carries a compiled texture.
    """
    rows = []
    for ip, cp in enumerate(model.phases):
        summary = model.texture_summary(ip, values)
        if summary is None:
            continue
        j, on_reflections, on_sphere = summary
        rows.append(PhaseTexture(name=structure.phases[ip].name, texture_index=j,
                                 min_p_reflections=on_reflections,
                                 min_p_sphere=on_sphere))
    return rows


def _reflection_tick_support(model: CompiledModel, ip: int,
                             values: dict[str, float], n_rows: int) -> np.ndarray:
    """Each tick's support in σ, for phase ``ip``'s ``n_rows`` emission-line
    rows tiled in reflection order — the pairing ``tick_support`` carries.

    A tick carries its *reflection's* support, the largest window norm
    ‖y/σ‖₂ over every emission-line image of that hkl (WP-1458, WP-1523).
    One authority for :func:`_tick_rows`, the tick builder both the single and
    the joint path call (WP-1344, WP-2028), so the joint fit's low-angle
    boundary asks the question the single fit's does.
    """
    if not n_rows:
        return np.array([])
    line_support = model.reflection_support(ip, values)
    return np.tile(np.max(np.stack(line_support), axis=0), n_rows)


def _extra_peak_tick_support(model: CompiledModel,
                             values: dict[str, float]) -> list[float]:
    """The support of each ``EXTRA_TICK_KEY`` tick, paired by index with
    :meth:`CompiledModel.extra_peak_tick_positions` — a peak's images are
    judged together, as a reflection's are (:func:`_reflection_tick_support`).
    """
    images = model.extra_peak_support(values)
    best: dict[int, float] = {}
    for _, j, s in images:
        best[j] = max(best.get(j, 0.0), s)
    return [best[j] for _, j, _ in images]


def _tick_rows(model: CompiledModel, structure: Structure,
               values: dict[str, float]
               ) -> tuple[dict[str, list[float]], dict[str, list[list[int]]],
                          dict[str, list[float]]]:
    """Every tick row of one histogram: positions, Miller indices and
    support, keyed alike.

    One builder for both paths, this module's :func:`_build_result` and each
    histogram of ``multi.MultiHistogramRefinement._build_result`` (WP-2028
    task 7), so a joint fit draws the rows a single fit draws: a magnetic
    phase's own ``"<phase> (magnetic)"`` row (issue #278) and the declared
    peaks' ``EXTRA_TICK_KEY`` row as well as one row per phase.
    """
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
    # (WP-1458).  Each tick carries its *reflection's* support: the largest
    # window norm in σ (`CompiledModel.reflection_support`, WP-1523) over every
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
        # where the forward model puts each peak, and which reflection each
        # position is, from the one walk every tick builder shares
        # (`CompiledModel.reflection_positions`, WP-1908): the zero shift and
        # the geometry's own shift are in it, and `hkl` is the reflection list
        # tiled once per emission line, so a Kα2 image says it is the same hkl
        # (H, m), not H: a satellite is labelled by its order (WP-1326)
        pos, hkl = model.reflection_positions(ip, values)
        n_lines = len(model.line_wavelengths)
        sup = _reflection_tick_support(model, ip, values, n_lines)
        keep = np.isfinite(pos)
        if cp.magnetic is not None:
            # issue #278: a magnetic phase's reflections are drawn as their
            # own tick row, as a second phase would be -- split by a purity
            # cut on the magnetic fraction (MAGNETIC_TICK_PURITY: see its
            # docstring for why the mask on ``CompiledPhase`` is not enough
            # on a k != 0 supercell).  One
            # fraction per *reflection*, tiled once per emission line (each
            # line already ``cp.reflections``-ordered, as ``pos`` is) before
            # the positions are sorted.
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
            mag_row = np.tile(mag_hkl, n_lines)
            rows_out = ((name, keep & ~mag_row),
                        (f"{name} (magnetic)", keep & mag_row))
        else:
            rows_out = ((name, keep),)
        for key, sel in rows_out:
            pos_k, hkl_k, sup_k = pos[sel], hkl[sel], sup[sel]
            order = np.argsort(pos_k, kind="stable")
            ticks[key] = [float(v) for v in pos_k[order]]
            tick_hkl[key] = [reflection_label_row(r) for r in hkl_k[order]]
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
    # `CompiledModel.extra_peak_tick_positions` — one authority, because a
    # joint fit's histograms owe the same list, and a second copy is how a
    # joint fit ends up disagreeing with a single one.
    #
    # Accepted wrinkle, recorded rather than special-cased: Layer 0's
    # `Region.n_reflections` counts ticks, so these inflate that count in their
    # own regions.  It is right for segmentation and for the unmatched logic,
    # and mislabelled as a count of reflections.
    extra_ticks = model.extra_peak_tick_positions(values)
    if extra_ticks:
        ticks[EXTRA_TICK_KEY] = extra_ticks
        tick_support[EXTRA_TICK_KEY] = _extra_peak_tick_support(model, values)
    return ticks, tick_hkl, tick_support


def _uncorrected(stderr: float | None, esd_inflation: float | None) -> float | None:
    """``RefinedParameter.stderr_uncorrected``: ``stderr`` without the
    Bérar-Lelann factor the solve multiplied it by (WP-2002, B4).

    Every row's physical esd is linear in the internal esds, so one division
    by the solve's own factor undoes it on a free, tied or derived row alike.
    ``None`` where there is no esd or no factor to divide by.
    """
    if stderr is None or esd_inflation is None:
        return None
    return stderr / esd_inflation


def _build_result(model: CompiledModel, table: ParameterTable, theta: np.ndarray, *,
                  mode: Mode, status: str, stage_results: list[StageResult],
                  diagnostics: list[Diagnostic], structure: Structure,
                  stderr_internal=None, correlation=None,
                  esd_inflation: float | None = None,
                  backend: str = "numpy", solver: str = DEFAULT_SOLVER,
                  mu_r_source: str = "given",
                  mu_r_skipped: str | None = None,
                  guard=None,
                  max_shift_over_esd: float | None = None,
                  declared_wavelengths: list[float] | None = None,
                  cell_runaway: Sequence[Diagnostic] | None = None,
                  significance: np.ndarray | None = None,
                  phase_support_sigma: float | None = PHASE_SUPPORT_SIGMA,
                  held_scales: set[int] | None = None,
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
    # at_bound is the BOUND_HIT and FLOOR_HIT findings projected onto the
    # rows, never a second bound test (WP-1076).  Only the free set was
    # tested, so a tied row — in `parameters`, absent from the free vector —
    # reports None, and so does every row when no guard ran at all
    # (`replay`).  A free row on a floor of 0 is tested like any other bound
    # (WP-1938), and reads True under either code (WP-1929).
    tested = set(table.free_paths) if guard is not None else set()
    on_bound = {p for f in guard.at_bounds for p in f.paths} if guard is not None else set()
    # A CELL_RUNAWAY finding's own message says the named cell's value is
    # "not a measurement", so its esd is withheld while the row stays (it is
    # still a free column; WP-1301's hold is what drops a row).  Keyed on the
    # **answer-producing stage's** finding, never the run's accumulated list
    # (review of #385 round 3): staging is cumulative, so a cell reset in
    # stage 1 is refined again from its stage-start value by every later stage,
    # and the esd the last stage measured is a measurement.  ``cell_runaway`` is
    # that stage's finding; ``None`` reads it off ``diagnostics``, which is
    # right for every caller whose list is one stage's (``run_stage``, a stage
    # report, ``replay``).  The flag stays the finding's own ``where``, as
    # ``at_bound`` is a projection of ``BOUND_HIT`` and ``FLOOR_HIT``, and a
    # tie inherits it.
    withheld = _cell_runaway_withheld(table, (
        p for d in (diagnostics if cell_runaway is None else cell_runaway)
        if d.code == "CELL_RUNAWAY" for p in d.where))
    params = []
    # a derived row (a rigid body's atom, WP-1805) moves with θ as a tied row
    # does and carries its esd through the block, so it is reported like one
    derived = table.derived_paths()
    for e in table.entries:
        if e.vary or e.tie is not None or e.path in derived:
            stderr = None if e.path in withheld else stderr_phys.get(e.path)
            params.append(RefinedParameter(
                path=e.path, value=e.value, vary=e.vary, stderr=stderr,
                # the esd without the Bérar-Lelann factor the solve applied,
                # as GSAS-II and FullProf print it (WP-2002, B4)
                stderr_uncorrected=_uncorrected(stderr, esd_inflation),
                at_bound=(e.path in on_bound) if e.path in tested else None,
                # a single fit declares no parametric equation (WP-1325)
                equations=[],
            ))

    # every row, and its labels and support, from the one builder the joint
    # fit's histograms call too (`_tick_rows`)
    ticks, tick_hkl, tick_support = _tick_rows(model, structure, values)

    # Quantitative phase analysis from the refined scales.  Le Bail scales are
    # degenerate with the extracted intensities, so QPA is Rietveld-only.  σ(W)
    # comes from the correlated scale block of the covariance (physical_covariance
    # reuses the same Cov_free as stderr_physical → consistent conditioning).
    qpa = None
    unmeasured_now: set[int] | None = None
    if mode == "rietveld":
        held_now = (_held_scale_phases(stage_results[-1]) if stage_results
                    else set(held_scales or ()))
        unmeasured_now = _unmeasured_phases(model, stage_results, held=held_now)
        qpa, qpa_diagnostics = _quantify_phases(
            table, theta, stderr_internal, correlation, structure, values, model,
            unmeasured=unmeasured_now, held=held_now)
        diagnostics = diagnostics + qpa_diagnostics

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
    volumes = cell_volumes(table, theta, structure,
                           stderr_internal=stderr_internal, correlation=correlation)

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

    # WP-1343: whether the magnetic peaks are broader than the profile drew
    # them, read off the converged residual's *shape* rather than from any
    # observed-width measurement (there is none in this package).  Silent on
    # a stage that freed the term — there the trajectory is the evidence.
    #
    # ``moved``: the width paths a MAGNETIC_WIDTH_MOVED_MOMENT rung already
    # named, read off the accumulated list rather than recomputed — one writer
    # per measurement (WP-1076), and it is what stops the support row being
    # worded as licence to drop a term that is carrying the answer.
    diagnostics = diagnostics + magnetic_width_findings(
        model, values, esds=stderr_phys, free=table.free_paths,
        moved={q for d in diagnostics
               if d.code == "MAGNETIC_WIDTH_MOVED_MOMENT"
               for q in d.where if "magnetic_lor" in q})

    # WP-1929: the moment angles the answer stage's covariance left out at a
    # stationary direction, read off its own record.  The rows carry no
    # interval yet: ``attach_stationary_intervals`` rebuilds this finding
    # once they do (WP-2002)
    if stage_results:
        diagnostics = diagnostics + moment_angle_stationary_diagnostics(
            stage_results[-1], params)

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
    # the record quote one measurement.  The significance is the answer
    # stage's own (WP-1523): a Rietveld fit hands in the vector its hold was
    # decided on, and any other caller (Le Bail, Pawley, a replay) gets the
    # screen at these values, an upper bound on the scale's significance.
    # Read against the plan's threshold, the hold's own, or the default
    # where the plan switched the hold off (``_reported_support_sigma``).
    decided = significance is not None
    if significance is None:
        significance = model.phase_support(values)
    support_sigma = _reported_support_sigma(phase_support_sigma)
    diagnostics = diagnostics + _phase_support_diagnostics(
        significance, model.phase_line_counts(),
        (model.tt_min, model.tt_max), list(table.free_paths), structure,
        stage_results, decided=decided, sigma=support_sigma,
        quantified=model.mode == "rietveld", unmeasured=unmeasured_now)

    # A phase whose scale and B the range cannot separate (WP-1534), and what
    # its fraction is conditional on.  Read off the stage records, which carry
    # the hold, so the finding and the record quote one measurement.
    diagnostics = diagnostics + _scale_b_ridge_diagnostics(
        [model], [values], structure, stage_results)

    # A strain broader than solved refinements normally use — a flag to check,
    # not a bound (the bound is params.vector.strain_cap, one tier up).
    diagnostics = diagnostics + _strain_flag_diagnostics(model, values, structure)

    # A crystallite smaller than solved refinements normally report — the size
    # twin of the flag above (bound: params.vector.size_cap, one tier up).
    diagnostics = diagnostics + _size_flag_diagnostics(model, values, structure)

    # A refined occupancy past a full site (WP-2002): Atom.occ has no ceiling,
    # so this is what meets one.
    diagnostics = diagnostics + _occupancy_flag_diagnostics(
        values, set(table.moving_paths), structure, stderr_phys)

    # A free rigid-body DOF the data gave no gradient (WP-1805): named, never
    # left to read as a body that refined
    if stderr_internal is not None:
        diagnostics = diagnostics + _rigid_body_unsupported(table, params)

    # The width census against the answer's own widths (WP-1336, issue #249):
    # the one width check that looks at the data rather than at a refined
    # coefficient, so it speaks where the two flags above have nothing to read
    # — a model with no size or strain freed.  Why here and not as a
    # precondition call: ``indexing.diagnostics.refinement_width_diagnostics``.
    diagnostics = diagnostics + _width_census_diagnostics(model, values, structure,
                                                          significance, support_sigma)

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

    # The whole residual's half of the same question, for a P-spline whose
    # air term was declined: the region above reads only below the first
    # reflection, and auto_background's trigger reads the envelope (#636).
    diagnostics = diagnostics + _air_scatter_undeclared_diagnostics(
        model, values, y_calc, stats)

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
        ticks=ticks, tick_hkl=tick_hkl, radiation=_radiation(model, values),
        qpa=qpa, restraints=restraints_report, geometry=geometry,
        cell_volumes=volumes,
        microstructure=microstructure,
        phase_agreement=_phase_agreement(model, values, structure),
        texture=_phase_texture(model, values, structure),
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


#: A Le Bail pass that lowers Rwp by no more than this fraction, or raises it by
#: no more, has reached a fixed point.  Measured on WP-1323's baseline: cells
#: exact 16.908 -> 16.908 (0), cells +0.3 % 16.969 -> 16.967 (1e-4).
LEBAIL_CONVERGED_REL = 1e-4


def _lebail_stop_diagnostic(reason: str, kept: int, rows: list[float],
                            cap: int) -> Diagnostic:
    """``LEBAIL_ALTERNATION_STOPPED``: why the passes stopped, and which was kept (WP-1323).

    ``info`` when the alternation ended at a fixed point, ``warning`` when it
    did not: a run that hit the cap with Rwp still falling is truncated rather
    than finished, and one that wandered has a start-state-dependent answer.
    """
    table = ", ".join(f"{100 * r:.3f}" for r in rows)
    said = {"converged": "reached a fixed point",
            "non_monotone": "stopped at the first pass that did not lower Rwp",
            "cap": f"reached the cap of {cap} passes with Rwp still falling"}[reason]
    return Diagnostic(
        level="info" if reason == "converged" else "warning",
        code="LEBAIL_ALTERNATION_STOPPED", where=[],
        message=(f"The Le Bail alternation {said}. Pass {kept} of {len(rows)} "
                 f"was kept (Rwp % per pass: {table})."),
        suggestion={
            "converged": None,
            "non_monotone": ("Check the cell and the background before you "
                             "read the kept pass."),
            "cap": ("Raise plan.lebail_passes, or continue from this state "
                    "with another fit()."),
        }[reason],
        value=float(rows[kept - 1]))


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
        order = cp.reflections.satellite_order
        state = ReflectionState(
            phase_index=ip,
            hkl=[[int(v) for v in h] for h in cp.reflections.hkl],
            # WP-1326: the parent H alone does not identify a row — a phase
            # with a propagation vector has up to two satellites sharing one
            # H — so the key a checkout matches on is (H, m).  ``None`` for a
            # phase with no k: the document gains that one null and nothing
            # else, which is what makes the version bump additive.
            satellite_order=(None if order is None
                             else [int(v) for v in order]),
            intensity=[float(v) for v in cp.hkl_intensity],
            kind="pawley_refined" if is_pawley else "lebail_extracted",
            varied=is_pawley,
        )
        if is_pawley and stderr_all is not None:
            a, b = model.pawley.phase_slices[ip]
            state.stderr = [float(v) for v in stderr_all[a:b]]
        out.append(state)
    return out


def _reflection_keys(hkl, order) -> list[tuple]:
    """(h, k, l, m) per row — the key a Le Bail intensity is matched on.

    ``m`` is the satellite order (WP-1326) and is 0 on every nuclear row, so a
    phase with no propagation vector produces exactly the keys the three-index
    form did with one constant appended, and matching is unchanged.  With a
    propagation vector the parent H alone is ambiguous: H + k and H − k are
    two reflections at two positions carrying two intensities.
    """
    if order is None:
        return [(int(h[0]), int(h[1]), int(h[2]), 0) for h in hkl]
    return [(int(h[0]), int(h[1]), int(h[2]), int(m))
            for h, m in zip(hkl, order, strict=True)]


def _scatter_lebail(lookup: dict[tuple, float], cp_new) -> None:
    """Write intensities into a freshly compiled phase, matching by (hkl, m)."""
    if cp_new.hkl_intensity is None:
        return
    keys = _reflection_keys(cp_new.reflections.hkl,
                            cp_new.reflections.satellite_order)
    for i, key in enumerate(keys):
        value = lookup.get(key)
        if value is not None:
            cp_new.hkl_intensity[i] = value


def _copy_seeded_column(jac: np.ndarray, jac2: np.ndarray, i: int,
                        blocks_now, blocks_seeded, path: str) -> None:
    """Carry candidate column ``i`` from :meth:`Refinement.suggest`'s seeded
    build into the current state's Jacobian, one row block at a time.

    The two builds share the data rows but not always every penalty block:
    a seeded Stephens block decides which Pawley reflections count as
    overlapped (a width did too, until WP-1938 stopped seeding one), so
    the equal-split restraint block can differ in length and a whole-column
    copy dies in a numpy broadcast (#244).  A block of equal length is
    copied; one whose length differs keeps the current state's rows, which
    is exact only where the column is zero in both builds — true of every
    table column against the Pawley restraint, whose rows read the intensity
    tail alone — and that is checked where it is used rather than assumed.
    """
    for now, seeded in zip(blocks_now, blocks_seeded):
        if now.n == seeded.n:
            jac[now.rows, i] = jac2[seeded.rows, i]
        elif np.any(jac[now.rows, i]) or np.any(jac2[seeded.rows, i]):
            raise ValueError(
                f"suggest(): seeding {path!r} off its floor changed the "
                f"{now.name} block from {now.n} to {seeded.n} rows, and "
                f"{path!r} reaches that block, so its seeded column cannot be "
                f"carried into the current state; seed {path!r} off its floor "
                f"yourself (set_values) and ask again")


def _carry_lebail(old: CompiledModel, new: CompiledModel) -> None:
    """Carry per-hkl intensities across a stage recompile (match by (hkl, m))."""
    for cp_old, cp_new in zip(old.phases, new.phases, strict=True):
        if cp_old.hkl_intensity is None:
            continue
        keys = _reflection_keys(cp_old.reflections.hkl,
                                cp_old.reflections.satellite_order)
        lookup = {key: float(cp_old.hkl_intensity[i])
                  for i, key in enumerate(keys)}
        _scatter_lebail(lookup, cp_new)


def _restore_lebail(states: list[ReflectionState], model: CompiledModel) -> None:
    """Re-seed per-hkl intensities from a checkpoint (match by (hkl, m))."""
    for state in states:
        if not 0 <= state.phase_index < len(model.phases):
            continue
        keys = _reflection_keys(state.hkl, state.satellite_order)
        lookup = {key: state.intensity[i] for i, key in enumerate(keys)}
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


def _frozen_compile_diagnostics(chi2_frozen: float, chi2_fresh: float, *,
                                histogram: int | None = None) -> list[Diagnostic]:
    """``FROZEN_COMPILE_STALE`` when the two χ² differ past :data:`FROZEN_COMPILE_CHI2_REL`.

    One comparison for both runners: the single fit's
    :meth:`Refinement._final_compile` and the joint fit's
    ``MultiHistogramRefinement._final_compiles``, which passes its worst
    histogram's pair and index (``histogram``) and keeps no history node to
    hold the frozen figure.
    """
    rel = (abs(chi2_fresh - chi2_frozen) / chi2_frozen
           if chi2_frozen > 0 else 0.0)
    if not rel > FROZEN_COMPILE_CHI2_REL:
        return []
    joint = histogram is not None
    whose = f" for histogram {histogram}" if joint else ""
    kept = ("the last stage's record keeps the frozen one" if joint
            else "the history node keeps the frozen one")
    return [Diagnostic(
        level="info", code="FROZEN_COMPILE_STALE",
        message=(
            f"A fresh compile at the returned parameters gives "
            f"chi2{whose} = {chi2_fresh:.6g}. The last stage's own compile gives "
            f"{chi2_frozen:.6g} at the same parameters, "
            f"{100 * rel:.2g} % apart. The result reports the fresh "
            f"figure and {kept}."),
        value=rel)]


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
            h = reflection_label(model.phases[ip].reflections.hklm[k])
            labels.append(f"{structure.phases[ip].name} {h}")
        total = float(np.sum(inten))
        out.append(Diagnostic(
            level="info", code="PAWLEY_OVERLAP_UNRESOLVED", where=labels,
            message=(f"{len(g)} reflections overlap too strongly to split. "
                     f"Their summed intensity ({total:.4g}) is determined, and "
                     f"the relative esd of an individual value reaches "
                     f"{float(np.max(rel)):.0%}."),
            suggestion="Use the group's summed intensity as the datum.",
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
        h = reflection_label(model.phases[ip].reflections.hklm[k])
        by_phase.setdefault(ip, []).append(f"{structure.phases[ip].name} {h}")
    return [Diagnostic(
        level="info", code="PAWLEY_OFF_DATA_RIDGED", where=labels,
        message=(f"{len(labels)} reflection(s) of {structure.phases[ip].name} have "
                 f"no emission line centred on the fitted data, so their "
                 f"intensities come from the restraint."),
        suggestion="Do not export or use these intensities. Widen the fitted "
                   "range if you need them.",
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
        message=(f"Anomalous scattering is off, but at lambda = {lam:.5f} A it "
                 f"changes the scattering power of {named}."),
        suggestion="Restore it with Dispersion(). If the wavelength sits in "
                   "an absorption-edge interval, supply the measured pair "
                   "through Dispersion.overrides instead.",
    )]


#: A resonant absorber whose *element* absorbs at least this much is reported
#: as a warning rather than as info.  1000 barn separates the four classic
#: black absorbers on this table -- Cd 2520, Eu 4530, Sm 5922, Gd 49700 -- from
#: Yb, whose element absorbs 34.80 and whose resonance lives in one minority
#: isotope (``168Yb``, 2230).  The split is about how much of the beam the
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
    The message also says where each species' lowest resonance sits, as an
    energy and as the neutron wavelength it corresponds to
    (``neutron.resonance_wavelengths``, ENDF/B-VIII.0), so the reader can set
    it beside the instrument's own wavelength.  Reported, never judged: how
    near is near needs the resonance's width, which is not carried.
    """
    from .crystallography.neutron import (  # noqa: PLC0415
        is_resonant_absorber,
        normalize_species,
        properties,
        resonance_wavelengths,
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
    sits = "; ".join(f"{n} {e:.4g} eV = {lam:.3g} A"
                     for s in sorted(flagged, key=lambda k: -flagged[k])
                     for n, (e, lam) in resonance_wavelengths(s).items())
    return [Diagnostic(
        level=("warning" if worst >= RESONANT_ABSORBER_SEVERE_BARN else "info"),
        code="NEUTRON_RESONANT_ABSORBER",
        where=sorted(where),
        message=(f"This structure contains a resonant absorber ({named}). The "
                 f"lowest resonance is at {sits}, and this source's "
                 f"wavelength is {instrument.source.primary_wavelength:.4g} A."),
        suggestion="Check that this wavelength is away from the resonance "
                   "before you quote an occupancy or a displacement parameter "
                   "on that site. A wavelength-resolved fit (a range of "
                   "wavelengths, or TOF) may not use one thermal value at all.",
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
    atom when an ion is absent from its table — deliberate
    (refusing would break files that currently refine, and 100 of issue
    #202's 111 chemically-real oxidation states resolve correctly, Y3+ since
    WP-1527) but previously silent:
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
        frac_text = ("undefined because the ion's own electron count is zero"
                     if delta is None else f"{delta:+.1%}")
        out.append(Diagnostic(
            level="warning", code="SPECIES_FALLBACK_NEUTRAL", where=where,
            value=delta,
            message=(f"{fb.species!r} is absent from the Waasmaier-Kirfel "
                     f"table and was scattered as neutral {fb.element}, with "
                     f"{fb.returned_electrons:.4g} electrons against the "
                     f"ion's {fb.true_electrons:.0f} ({frac_text})."),
            suggestion=(f"Accept neutral {fb.element} as the model, or "
                        "substitute a tabulated ion of the same element with "
                        "a nearby charge as a deliberate approximation."),
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
        head = (f"The lambda/{order} line ({lam:.5f} A) carries "
                f"{pct:.2f}{esd_txt} % of the fundamental")
        if path not in free_paths:
            out.append(Diagnostic(
                level="info", code="HARMONIC_HELD", where=where,
                message=(f"{head}, but the weight was never refined, so this "
                         f"is the declared value."),
                suggestion=("Free instrument.source.lines.*.weight in a stage "
                            "after the profile and the scale have settled.")))
            continue
        if frac < HARMONIC_ABSENT_FRAC:
            out.append(Diagnostic(
                level="info", code="HARMONIC_ABSENT", where=where,
                message=(f"The declared lambda/{order} line refined to "
                         f"{pct:.3f}{esd_txt} % of the fundamental."),
                suggestion=("Drop the declaration to remove a parameter the "
                            "data do not support.")))
            continue
        implausible = frac > HARMONIC_IMPLAUSIBLE_FRAC
        out.append(Diagnostic(
            level="warning" if implausible else "info",
            code="HARMONIC_FRACTION", where=where,
            message=(head + "." + (" That is far above the few per cent a "
                                   "monochromator harmonic is reported at."
                                   if implausible else "")),
            suggestion=("Check the tick marks against the unfitted peaks "
                        "before you believe it."
                        if implausible else
                        "Quote this as a property of this beam on this "
                        "monochromator, and do not transfer it to another "
                        "histogram.")))
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
            message=(f"{head[:1].upper()}{head[1:]}: wavelength refined from "
                     f"the declared {lam0:.6f} A to {lam:.6f} A, {ppm:+.1f} "
                     f"ppm{resolved}. The shift is {pinned_by}."),
            where=where, value=float(ppm),
            suggestion=("Compare it with the instrument's own calibration "
                        "history before you quote the cell.")))
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
    """Flag restraints the data fights (|deviation/σ| beyond the threshold).

    One finding per restraint, a plane included: its rows are one per atom
    (each atom's distance to the plane, consecutive in the report, as many as
    the plane has atoms), so a strained plane is one finding whose ``where``
    is the atoms out of it past the threshold, worst first, rather than one
    finding per atom each naming the whole plane.
    """
    out: list[Diagnostic] = []
    rows = report.rows
    k = 0
    while k < len(rows):
        row = rows[k]
        if row.kind == "planarity":
            plane = rows[k:k + len(row.atoms)]
            k += len(plane)
            found = _plane_tension(plane, structure)
        else:
            k += 1
            found = (None if abs(row.deviation_over_sigma) <= RESTRAINT_TENSION_SIGMA
                     else (_restraint_where(row, structure),
                           f"The {row.kind} restraint deviates "
                           f"{row.deviation_over_sigma:+.1f}σ from its target "
                           f"({row.computed:.4g} vs {row.target:.4g})."))
        if found is None:
            continue
        where, message = found
        out.append(Diagnostic(
            level="warning", code="RESTRAINT_TENSION", where=where, message=message,
            suggestion="Loosen its sigma, correct the target, or raise sigma "
                       "so the measured pattern overrides the prior.",
        ))
    return out


def _plane_tension(plane: list, structure: Structure) -> tuple | None:
    """``(where, message)`` for a planarity restraint's rows past the
    threshold, worst first, or ``None`` where none is."""
    out = sorted((r for r in plane
                  if abs(r.deviation_over_sigma) > RESTRAINT_TENSION_SIGMA),
                 key=lambda r: -abs(r.deviation_over_sigma))
    if not out:
        return None
    phase = structure.phases[plane[0].phase_index]
    lab = [a.label for a in phase.atoms]
    shown = ", ".join(f"{lab[r.atoms[0]]} {r.deviation_over_sigma:+.1f}σ "
                      f"({r.computed:+.4g} Å)" for r in out)
    return (list(dict.fromkeys(f"{phase.name} {lab[r.atoms[0]]}" for r in out)),
            f"The planarity restraint on "
            f"{', '.join(lab[j] for j in plane[0].atoms)} has {len(out)} of "
            f"{len(plane)} atoms more than {RESTRAINT_TENSION_SIGMA:g}σ from "
            f"its plane: {shown}.")


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
        share = (f" The model accounts for {bragg_calc / obs_excess:.1%} of "
                 f"the observed above-background intensity.")
    return [Diagnostic(
        level="error", code="MODEL_FAR_FROM_DATA",
        message=f"Rwp = {stats.rwp:.1%}.{share}",
        where=[],
        suggestion="Do not read the status, the parameter values or their "
                   "esds. Check the cell (it must lie within about 1 % of "
                   "the true one), the wavelength, the zero shift and the "
                   "2θ range, then re-index if the cell is in doubt.",
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
    one, and tested with ``BOUND_HIT_RTOL``, the distance of the
    refinement's own bound test where no solve stands behind it
    (``staged.bound_findings``, which reads the driver's exact active set or
    a conjunction where it has a solve, WP-1434 and WP-1929) rather than a
    second constant.

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
        # ``BOUND_HIT_RTOL`` is scipy's own test and ``bound_findings``'
        # fallback, imported rather than restated so the two cannot drift
        # apart on what counts as *at* a limit.  The ``<= 0`` clause beside
        # it covers an area whose stated lower bound is below zero, which is
        # off at its identity without being "at" that bound.
        at_zero = (area <= 0.0
                   or (np.isfinite(lo)
                       and abs(area - lo) <= BOUND_HIT_RTOL * max(1.0, abs(lo))))
        if at_zero:
            out.append(Diagnostic(
                level="warning", code="EXTRA_PEAK_NO_INTENSITY",
                message=(
                    f"Declared peak {name!r} refined to no intensity "
                    f"(area {area:.3g} at its zero bound)."),
                where=[pc.paths["center"], area_path],
                suggestion=(
                    "Drop the component, or check that its centre bounds "
                    "bracket the feature you meant.")))
            continue

        if len(predicted_arr):
            gap = float(np.min(np.abs(predicted_arr - centre)))
            if gap <= LAYER0_MATCH_TOL_DEG:
                out.append(Diagnostic(
                    level="warning", code="EXTRA_PEAK_ON_REFLECTION",
                    message=(
                        f"Declared peak {name!r} sits {gap:.3f} deg from a "
                        "position this model already predicts."),
                    where=[pc.paths["center"], pc.paths["area"]],
                    suggestion=(
                        "If the component stands in for a misfitting "
                        "reflection, fix the phase's scale, profile and "
                        "preferred orientation instead.")))
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
                f"{support.n_structural_parameters} free), below the "
                f"guideline of at least {OBS_PER_PARAMETER_MIN:g} and "
                f"preferably {OBS_PER_PARAMETER_PREFERRED:g}."),
            suggestion=(
                "Hold the least determined parameters (start from the "
                "report's identifiability section), restrain the geometry, "
                "or extend the 2θ range."),
        ))

    steps, n_measured = sampling_steps_per_fwhm(
        model.tt, model.y_obs, model.sigma)
    if steps is not None and steps < STEPS_PER_FWHM_MIN:
        out.append(Diagnostic(
            level="warning", code="PATTERN_UNDERSAMPLED",
            message=(
                f"The median fitted peak spans {steps:.1f} steps across its "
                f"FWHM ({n_measured} peaks), below the {STEPS_PER_FWHM_MIN:g} "
                "the guidelines ask for."),
            suggestion=("Re-collect at a step near FWHM/5 if the intensities "
                        "must be quotable."),
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
                    "there."),
                where=[f"{lo:.3f}-{hi:.3f}"],
                suggestion=(
                    f"Exclude the interval ({lo:.3f}, {hi:.3f}) and refit."),
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

#: fraction of the fit's own weighted residual sum of squares that a 1/(2θ)
#: column would remove, at or above which ``AIR_SCATTER_UNDECLARED`` fires on a
#: P-spline background that declares no air term (issue #636).  Measured on
#: the issue's synthetic NAC capillary pattern (λ 0.4133 Å, 2θ 0.5-50°, 3°
#: knots, a broad hump under an A/(2θ) rise): 0.127, 0.035 and 0.0063 at
#: A = 600, 300 and 150, where declaring the term cuts χ² by 24 %, 11 % and
#: 4.3 %; 0 at A = 50 and on five seeds without the rise, where declaring it
#: cuts nothing and the column's best coefficient is negative, a direction
#: the bounded term cannot take.  The same at a 0.001° step.  A = 150 is
#: the case ``LOW_ANGLE_UNMODELLED`` is already silent on.
AIR_SCATTER_UNDECLARED_FRACTION = 0.005

#: the same removal in units of the fit's reduced χ², i.e. the score
#: statistic, which is χ²(1)-distributed when the column explains nothing.  25
#: is 5σ, so a short pattern whose 1/N noise floor sits near the fraction
#: above cannot fire on noise alone.
AIR_SCATTER_UNDECLARED_SCORE = 25.0


def _first_reflection_fwhm(model: CompiledModel, values: dict[str, float],
                           ticks: dict[str, list[float]],
                           support: dict[str, list[float]] | None = None
                           ) -> tuple[float, float] | None:
    """``(2θ, FWHM)`` of the lowest-angle reflection the data can see, over
    every phase, emission line and declared peak, or ``None`` when there is
    none (an empty structure list, or no tick carrying intensity).

    **Which ticks count** (WP-1458): the images of a reflection whose window
    norm ‖y/σ‖₂, on any emission line, reaches
    :data:`~rietx.model.forward.PHASE_SUPPORT_SIGMA` — read off ``support``,
    which :func:`_build_result` builds from
    :meth:`CompiledModel.reflection_support` and
    :meth:`CompiledModel.extra_peak_support` and pairs with ``ticks`` by
    index.  That is :data:`~rietx.indexing.workflow.ABSENT_SIGMA`'s test on a
    line, and :meth:`CompiledModel.phase_support`'s one rank down (WP-1523).
    Per reflection rather than per phase, because a *supported* row can still
    carry empty ticks below its first real line (a declared peak at zero
    area, a superstructure reflection whose |F| is zero), and because a
    phase's summed curve can clear the threshold where none of its
    reflections does (issue #436's large-cell dummy, measured under the
    pre-WP-1523 strongest-point test: 1.23σ summed, no reflection above
    0.62σ).  A tick with nothing behind it reaches nothing; before this rule
    one below the data moved the boundary there and silenced the diagnostic.

    **Per reflection, not per image**: the unit is the hkl, as ``tick_hkl``
    has it, so a Kα2 or λ/2 image of a reflection the data sees keeps its
    place however weak the image is on its own.  Judged image by image under
    the strongest-point test, the λ/2 (111) of the published BT-1 Cu(311)
    Nd₂Ru₂O₇ fit (0.095σ, beside its primary's 2.86σ) was dropped, the region
    grew from 36 to 185 channels, and a warning firing at 5.92× fell to
    2.66×.

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
            f"the whole-pattern reduced χ² ({chi2_red:.2f})."),
        suggestion=(
            f"Raise the pattern's lower limit to {suggested:.2f}° "
            "(the channel where the residual falls under 2σ), or add "
            "the background's air-scatter term."),
        value=ratio,
    )]


def _air_scatter_undeclared_diagnostics(model: CompiledModel,
                                        values: dict[str, float],
                                        y_calc, stats) -> list[Diagnostic]:
    """``AIR_SCATTER_UNDECLARED``: a P-spline background with no air term,
    on a fit whose residual a 1/(2θ) column would cut materially (#636).

    ``auto_background`` declares the term only on
    ``PatternDiagnostics.air_scatter_gain``, a cubic-against-cubic+1/x test
    on the rolling low-quantile envelope over the whole range, and since
    WP-1454 a declined term is absent.  That envelope is blind on exactly the
    pattern the term is for: on a peak-dense synchrotron capillary scan its
    3° windows miss a rise confined to the first few degrees and read far
    above the true background where the lines crowd, so the gain is set by the
    hump and the line density rather than by the rise (#636's synthetic
    pattern: 0.0035 with the rise, 0.047 without it).
    ``LOW_ANGLE_UNMODELLED`` reads the fit's residual instead, but only below
    the first reflection, so a rise that runs on under the first lines is
    outside its region.

    This reads the fit's whole residual.  It is the one-column score test:
    with r the weighted residual, penalty rows appended, and a the weighted
    1/(2θ) row ``compile_model`` would build, projected off the background
    block the fit already has, the column removes (a⊥·r)²/(a⊥·a⊥) of χ² at
    coefficient t = a⊥·r/(a⊥·a⊥).  At the solution r is orthogonal to the
    background block, so this is what one Gauss-Newton step on the extended
    model buys with the Bragg model held, and projecting off the background
    block alone, rather than every free column, makes it a lower bound on
    that step.  It is not a bound on what a fresh run of a staged plan with
    the term declared reaches, which is path-dependent: on round-robin
    sample 2 (``tests/data/qarr/cpd-2.prn``), where the trigger declares the
    term, taking it away again reads 0.028 here, while the declared refit's
    χ² moves 1.5 % with nothing but the term's seed and sits 0.75 % under
    the undeclared one.  **One-sided**:
    the term is bounded at zero, so a negative t is a direction the declared
    term cannot take, and it does not fire.  That is what separates the arms
    on #636's pattern, where every no-rise seed has t < 0.  Where the spline
    can already draw 1/(2θ) (fine knots), a⊥ is small and so is the score,
    which is the flat direction WP-1454 and WP-1460 describe.

    Fires when the removal is at least :data:`AIR_SCATTER_UNDECLARED_FRACTION`
    of χ² **and** at least :data:`AIR_SCATTER_UNDECLARED_SCORE` reduced-χ²
    units.  Silent on any background without penalty rows: only a P-spline
    carries the term, and a λ = 0 spline has no rows to tell it from a
    Chebyshev by.
    """
    if model.bkg_penalty is None or any(
            p.endswith("background.air") for p in model.bkg_paths):
        return []
    w = 1.0 / model.sigma
    r = (model.y_obs - np.asarray(y_calc)) * w
    pen = model.penalty_residual(values)
    pen = np.zeros(0) if pen is None else np.asarray(pen, dtype=np.float64)
    total = float(r @ r)
    if not (total > 0.0 and stats.chi2 > 0.0):
        return []
    r_aug = np.concatenate([r, -pen])
    block = np.vstack([(model.bkg_design * w).T, model.bkg_penalty])
    air = np.concatenate([w / np.maximum(model.tt, 1e-3),
                          np.zeros(model.bkg_penalty.shape[0])])
    beta, *_ = lapack.lstsq(block, air, rcond=None)
    perp = air - block @ beta
    norm = float(perp @ perp)
    lean = float(perp @ r_aug)
    if not (norm > 0.0 and lean > 0.0):
        return []
    removed = lean * lean / norm
    fraction = removed / total
    if (fraction < AIR_SCATTER_UNDECLARED_FRACTION
            or removed / stats.chi2 < AIR_SCATTER_UNDECLARED_SCORE):
        return []
    return [Diagnostic(
        level="warning", code="AIR_SCATTER_UNDECLARED",
        message=(
            "The P-spline background declares no 1/(2θ) air-scatter term. "
            "Re-fitting the background with one, the Bragg model held, "
            f"would remove at least {fraction:.1%} of this fit's χ² "
            f"({removed / stats.chi2:.0f}× its reduced χ², from a score test "
            "on the fit's own residual)."),
        suggestion=(
            "Declare the term with instrument.background.air_scatter = "
            "Parameter(value=1e-3, min=0.0) and refit. If the rise is not "
            "air scatter, raise the pattern's lower limit instead."),
        value=fraction,
    )]


def _quantify_phases(table: ParameterTable, theta: np.ndarray,
                     stderr_internal: np.ndarray | None,
                     correlation: np.ndarray | None, structure: Structure,
                     values: dict[str, float], model: CompiledModel, *,
                     where_of: Callable[[str], str] | None = None,
                     unmeasured: set[int] | None = None,
                     held: set[int] | None = None,
                     ) -> tuple[QuantitativePhaseAnalysis | None, list[Diagnostic]]:
    """Weight fractions from the refined scales, and the findings they carry.

    One builder for the single fit and for each histogram of a joint one
    (:mod:`rietx.multi`), which had its own until WP-1463 and skipped the
    blind-scale rule below.  ``where_of`` maps a table path to the row path a
    client holds (``hist.h.…`` for a per-histogram row); identity by default.

    **A scale the data carries no gradient in makes every fraction's esd
    unquotable, not only its own** (WP-1110 item 14).  W_i normalises by
    Σ S_j M_j V_j, so one unmeasured term is an unmeasured sum.  Its column is
    zeroed in Cov_free rather than infinite (``ParameterTable._cov_free``), so
    propagating it anyway would report each *other* phase's fraction to the
    precision it would have had if this phase were known, which is the
    confident wrong number.  So the whole block is withheld, and
    ``QPA_ESD_UNAVAILABLE`` names the phase that withheld it.
    ``PHASE_UNCONSTRAINED`` does not: it is about a phase's *other* free
    parameters, and a plan freeing only the scale gives it nothing to say
    (WP-1463 measured it silent at S = 0.0).

    Since WP-1463 a scale is blind only where its column is exactly zero.
    Since WP-1938 a scale is refined in its own units, so its column is the
    phase's pattern at any value, and an absent phase's scale at 0.0 keeps
    its esd.  The zero column that remains is a phase with no gradient at any
    scale, such as one whose sites are all empty.

    **A phase with no reflection in the fitted range has no fraction at all**
    (WP-1958, decided on #954): the absent-rather-than-zero rule carried from
    its esd to the number.  Its scale is the value handed in (the support hold
    takes it), so a fraction read off it is the caller's start, not a
    measurement.  It leaves the sum, so the others are fractions of the phases
    seen in range, ``QuantitativePhaseAnalysis.unmeasured_phases`` names it,
    and its zero column no longer withholds their esds.  ``unmeasured`` is the
    caller's answer to which (:func:`_unmeasured_phases`, read off what the
    last stage held); ``None`` recounts the lines at this model.  ``held`` is
    the part of it a stage held, which the record names apart from the phases
    with no line at the answer (``unmeasured_held``).
    """
    lineless = _lineless_phases(model)
    unmeasured = sorted(lineless if unmeasured is None else unmeasured)
    held_only = sorted((set(held or ()) & set(unmeasured)) - lineless)
    scale_paths = [f"phases.{ip}.scale" for ip in range(len(structure.phases))
                   if ip not in unmeasured]
    scale_cov = None
    blind_paths: list[str] = []
    if stderr_internal is not None and scale_paths:
        blind = table.unmeasured_rows(theta, stderr_internal,
                                      [table._paths[q] for q in scale_paths])
        blind_paths = [q for q, b in zip(scale_paths, blind, strict=True) if b]
        if not blind_paths:
            scale_cov = table.physical_covariance(theta, stderr_internal,
                                                  correlation, scale_paths)
    # Site multiplicities frozen on the compiled model (never re-derived
    # from refined coordinates, which could have drifted near a special
    # position and collapsed an orbit).  The primary emission line feeds
    # the Brindley microabsorption attenuation (µ ∝ λ³ makes the Kα₂
    # offset sub-percent in µ, far smaller in τ), from the table of the
    # histogram's own radiation (#543): the neutron µ, not the X-ray one.
    multiplicities = [[len(op[0]) for op in cp.sites.ops] for cp in model.phases]
    wavelength = model.line_wavelengths[0] if model.line_wavelengths else None
    qpa = compute_qpa(structure, values, scale_cov, multiplicities,
                      wavelength=wavelength, source_kind=model.source_kind,
                      unmeasured=unmeasured, held=held_only)
    if qpa is None:
        return None, _qpa_unavailable_diagnostics(structure, values)
    diagnostics = microabsorption_diagnostics(qpa, structure)
    if blind_paths:
        diagnostics = diagnostics + _qpa_esd_unavailable_diagnostics(
            structure, values, blind_paths, where_of or (lambda p: p))
    return qpa, diagnostics


def _qpa_esd_unavailable_diagnostics(structure: Structure,
                                     values: dict[str, float],
                                     blind: list[str],
                                     where_of: Callable[[str], str],
                                     ) -> list[Diagnostic]:
    """``QPA_ESD_UNAVAILABLE``: every fraction is quoted, none carries an esd.

    Before WP-1463 this was silent.  16 of 48 patterns of a real series came
    back with every ``weight_fraction_stderr`` at ``None`` and no finding, and
    the agent propagated the scale esds by hand, without the covariance.
    """
    named = []
    for path in blind:
        ip = int(path.split(".")[1])
        named.append(f"the scale of phase {ip} ({structure.phases[ip].name}) "
                     f"refined to {values.get(path, 0.0):.3g}")
    phase = int(blind[0].split(".")[1])
    return [Diagnostic(
        level="warning", code="QPA_ESD_UNAVAILABLE",
        where=[where_of(p) for p in blind],
        message=("No weight fraction carries an esd: " + "; ".join(named)
                 + (" and could not be measured there" if len(named) == 1
                    else ", and none could be measured there")
                 + ", and every fraction divides by a sum that includes "
                 + ("it" if len(named) == 1 else "them") + "."),
        suggestion=(
            "Remove the phase if its scale sits at zero, which gives the "
            "other fractions their esds. On a single-pattern fit, "
            f"call Refinement.profile_fraction(data, {phase}) for the "
            "admissible range of one fraction."),
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
        message=("The refined phase scales give a non-positive Σ S·ZMV, so "
                 "weight fractions cannot be formed"
                 + (f" ({', '.join(dead)} at or below zero)" if dead else "")
                 + "."),
        suggestion="Check whether the phase belongs in the model and whether "
                   "its starting cell put its peaks where the data have none. "
                   "Read the other diagnostics from this run.",
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
        message=(("Stage " if len(hit) == 1 else "Stages ")
                 + ", ".join(repr(n) for n in hit)
                 + (" stopped on its iteration budget."
                    if len(hit) == 1 else
                    " stopped on their iteration budgets.")),
        where=[],
        suggestion="Free fewer parameters at once, or check the diagnostics "
                   "for a correlation or bound hit in the same stage.",
    )]


def _moves_scale(path: str, held_reach: dict[str, set[str]], scale: str) -> bool:
    """Whether held column ``path`` is phase ``scale``'s, by its name or by
    what it moved (``StageResult.held_reach``), either spelled bare or
    ``hist.h.``-scoped."""
    return any(_unscoped(n) == scale for n in (path, *held_reach.get(path, ())))


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

    **Only this hold's columns.**  ``held`` also carries what the scale–B test
    held (WP-1534), which is about a visible phase and is
    ``SCALE_B_INSEPARABLE``'s to report; counted here, a phase that collapsed
    after a ridge stage would name that stage as one that held it unseen.
    """
    paths: list[set[str]] = [set() for _ in range(n_phases)]
    stages: list[dict[str, None]] = [{} for _ in range(n_phases)]
    for sr in stage_results:
        ridge = {c for cols in _scale_b_columns(sr).values() for c in cols}
        for path in sr.held:
            if path in ridge:
                continue
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
                               *, basis: str = "against the counting noise",
                               decided: bool = True,
                               sigma: float = PHASE_SUPPORT_SIGMA,
                               quantified: bool = False,
                               unmeasured: set[int] | None = None,
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

    ``support_by_phase`` is each phase's significance in σ (WP-1523).  A
    single fit hands in :func:`_answer_significance`: the scale over its esd
    against counting noise, or the screen ``‖y_p/σ‖₂`` where that is already
    under the threshold.  The screen bounds the other from above, so the
    scale is *at most* that many σ from zero either way, and the message says
    so.  A ratio is unmoved by the scale's degeneracy with |F|², the widths
    and the line weights, since rescaling one rescales the scale and its esd
    alike.  ``basis`` names how the σ was taken, for the message: a joint fit
    reads the screen in the histogram that shows the phase best.
    ``decided`` says whether a held phase's reading is the one the last
    stage's answer kept its hold on (a single Rietveld fit's stage vector,
    measured with the held columns freed) or one the result took at the
    final values (a joint fit, Le Bail, Pawley, a replay), so the message
    claims only what is true of the number.  A hold taken at a stage start
    read min(screen, prior) instead (WP-1523), and the message quotes the
    answer's reading because the answer is what kept it.

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

    ``sigma`` is the threshold a phase must reach to count as seen: the plan's
    ``phase_support_sigma``, so the report and the hold read one number, or
    the default where the plan switched the hold off (WP-2002, B1).  With the
    hold off nothing is held on significance, so the message names only what
    refined, and a phase with no line in range, which is held either way.

    ``quantified`` says the fit forms weight fractions (a Rietveld fit), so
    the message for a phase with no line in range says it has none and what
    the others are relative to (WP-1958, ``QuantitativePhaseAnalysis.
    unmeasured_phases``).  ``unmeasured`` is the set that QPA quotes no fraction
    for (:func:`_unmeasured_phases`): a phase in it with a line at the answer
    had its scale **held**, and the message says that rather than "no
    reflection" (#1103); ``None`` reads the line count alone.
    """
    n_phases = len(support_by_phase)
    held_paths, held_stages = _held_by_phase(stage_results or [], n_phases)
    held_reach: dict[str, set[str]] = {}
    for sr in stage_results or []:
        for q, moved in sr.held_reach.items():
            held_reach.setdefault(q, set()).update(moved)
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
        lacks = no_lines if unmeasured is None else (ip in unmeasured or no_lines)
        scale_only = lacks and not no_lines
        if not unconstrained and not held and not lacks:
            continue
        support = float(support_by_phase[ip])
        if support >= sigma and not lacks:
            continue
        if n_phases < 2 and not held and not lacks:
            continue
        name = structure.phases[ip].name
        if no_lines:
            cause = (f"No reflection of phase {ip} ({name}) lies in the fitted "
                     f"range {tt_range[0]:.4g}-{tt_range[1]:.4g}°.")
        elif scale_only:
            cause = (f"Phase {ip} ({name})'s scale was held at the value handed "
                     "in, so it is not a measurement, though a reflection of "
                     "it lies in the fitted range at the answer.")
        elif held and decided:
            # a held phase quotes the reading the last stage's answer kept or
            # took its hold on, which a second solve at the restored values
            # can since have moved; a hold taken at a stage start read
            # min(screen, prior) instead, and the answer is what kept it
            cause = (f"Phase {ip} ({name})'s scale was at most "
                     f"{support:.2g}σ from zero {basis} at the last stage's "
                     f"answer, under the {sigma:g}σ a phase "
                     f"needs to count as seen.")
        else:
            cause = (f"Phase {ip} ({name})'s scale is at most {support:.2g}σ "
                     f"from zero {basis}, under the {sigma:g}σ "
                     f"a phase needs to count as seen.")
        clauses = []
        # a phase with no line in range has its scale held too (WP-1958), and
        # the scale is not a structural parameter, so it is named on its own
        # (a joint fit's per-histogram scale is scoped ``hist.h.``).  A held
        # column is the scale's by what it moves, not by its name: a held
        # ``vars.S`` driving the scale is the scale held (#1103, round 2)
        structural = [p for p in held
                      if not _moves_scale(p, held_reach, f"{prefix}scale")]
        scale_held = len(structural) < len(held)
        if held:
            stages = held_stages[ip]
            during = (f"stage{'' if len(stages) == 1 else 's'} "
                      f"{', '.join(stages)}")
            if structural:
                clauses.append(f"Its {len(structural)} structural parameter"
                               f"{'' if len(structural) == 1 else 's'} "
                               f"{'was' if len(structural) == 1 else 'were'} "
                               f"held for {during}.")
            if scale_held:
                scale_stages = []
                scale_hists: set[int] = set()
                for sr in stage_results or []:
                    hit = False
                    for q in sr.held:
                        for n in (q, *sr.held_reach.get(q, ())):
                            if _unscoped(n) != f"{prefix}scale":
                                continue
                            hit = True
                            if n.startswith("hist."):
                                h = n[len("hist."):].partition(".")[0]
                                if h.isdigit():
                                    scale_hists.add(int(h))
                    if hit:
                        scale_stages.append(sr.name)
                where = (f" in histogram{'' if len(scale_hists) == 1 else 's'} "
                         f"{', '.join(map(str, sorted(scale_hists)))}"
                         if scale_hists else "")
                last = stage_results[-1] if stage_results else None
                refined_last = last is not None and last.name not in scale_stages
                if refined_last and no_lines:
                    # nothing reached the range: only a weighted restraint
                    # keeps the column alive, and its value is the target's
                    tail = (f", and left free in the last stage ({last.name}) "
                            "by a weighted restraint on it, so its value is "
                            "the restraint's, not the data's.")
                elif refined_last:
                    tail = (f", and refined in the last stage ({last.name}), "
                            "where a reflection reached the range, so the "
                            "answer's scale is a measurement.")
                else:
                    tail = "."
                clauses.append(
                    f"Its scale was held at the value handed in for stage"
                    f"{'' if len(scale_stages) == 1 else 's'} "
                    f"{', '.join(scale_stages)}{where}{tail}")
        if lacks and quantified:
            clauses.append("It has no weight fraction"
                           + (", and the other fractions are relative to the "
                              "phases seen in range." if n_phases > 1 else "."))
        if unconstrained:
            clauses.append(f"{len(unconstrained)} of its parameters "
                           f"{'was' if len(unconstrained) == 1 else 'were'} "
                           f"refined without signal.")
        message = " ".join([cause, *clauses])
        out.append(Diagnostic(
            level="warning", code="PHASE_UNCONSTRAINED",
            # the held paths as well as the still-free ones: a held value is
            # the one the caller handed in rather than a measurement, and
            # reading it as a result is the same mistake either way
            where=sorted(set(unconstrained) | set(held)),
            value=support,
            message=message,
            suggestion=(
                "Take the phase out of the model, or widen the fitted range "
                "to cover one of its reflections."
                if no_lines else
                "Take the phase out of the model, or start the run where a "
                "reflection of it is already in range (or free the zero shift "
                "first), so its scale refines from the first stage."
                if scale_only else
                "Treat those values as unmeasured. Take the phase out of the "
                "model, or seed its scale off the floor before you free "
                "anything else of it."),
        ))
    return out


def _scale_b_columns(sr: StageResult) -> dict[int, list[str]]:
    """Per phase this stage held on the scale–B test, the columns held for it.

    Read off the record, for :func:`_held_by_phase`'s reason: the finding and
    the record must not disagree about what happened.  ``held`` carries all
    three holds' columns, and :attr:`~StageResult.scale_b_held` names the
    phases; a column belongs to phase ``ip``'s ridge when its name or its
    reach is one of ``ip``'s displacement paths — the reach because a held
    ``vars.B`` names no phase (WP-1342).  Within one stage the three holds
    cannot share a column: a phase the data cannot see has its displacement
    columns held before the probe runs, which then has nothing of it to test.
    """
    out: dict[int, list[str]] = {}
    for ip in sorted(sr.scale_b_held or {}):
        for col in sr.held:
            for name in (col, *sr.held_reach.get(col, ())):
                # a joint fit's per-histogram override is scoped ``hist.h.``
                m = _DISPLACEMENT_PATH.match(_unscoped(name))
                if m is not None and int(m.group(1)) == ip:
                    out.setdefault(ip, []).append(col)
                    break
    return out


def _intensity_weighted_s2(models: list[CompiledModel], ip: int,
                           per_values: list[dict[str, float]]) -> float | None:
    """Phase ``ip``'s mean s² = 1/(4d²) over its reflections in the fitted range
    of every histogram (one in a single fit).

    Weighted by each (emission line, reflection)'s integrated intensity, since
    the fraction's sensitivity to B is the intensity's, and a weak reflection
    at high s moves it less than a strong one at low s.  s is λ-free, so a
    joint fit's histograms pool.  "In range" is a nonempty frozen window
    (:meth:`CompiledModel.phase_line_counts`' reading), and the plain mean
    stands in where every intensity is zero.  ``None`` when no reflection of
    the phase lies in range.
    """
    weights, s2s = [], []
    for model, values in zip(models, per_values, strict=True):
        cp = model.phases[ip]
        inside = cp.win[:, :, 1] > cp.win[:, :, 0]
        if not inside.any():
            continue
        s2 = np.broadcast_to(
            0.25 / np.asarray(cp.reflections.d, dtype=np.float64) ** 2, inside.shape)
        w = np.stack([np.asarray(p[3], dtype=np.float64)
                      for p in model.phase_peaks(ip, values)])
        weights.append(np.where(inside & np.isfinite(w), np.abs(w), 0.0)[inside])
        s2s.append(s2[inside])
    if not s2s:
        return None
    w, s2 = np.concatenate(weights), np.concatenate(s2s)
    if float(w.sum()) > 0.0:
        return float((w * s2).sum() / w.sum())
    return float(s2.mean())


def _scale_b_ridge_diagnostics(models: list[CompiledModel],
                               per_values: list[dict[str, float]],
                               structure: Structure,
                               stage_results: list[StageResult] | None,
                               ) -> list[Diagnostic]:
    """``SCALE_B_INSEPARABLE`` — a scale and a B the range cannot separate,
    and what was done (WP-1534).

    One per phase across the run.  The phase's intensity is
    ``scale · exp(−2B·s²)`` (the isotropic Debye-Waller factor,
    International Tables Vol. C, Prince 2004), so on a range where its
    reflections sit at one d-spacing the data give one number for the pair;
    the stage held the displacement half (``StageResult.scale_b_held``), and
    the scale measured the intensity at the B handed in.  What that costs is
    the **fraction**: holding the intensity fixed, the scale goes as
    exp(2B·s²), so an error δB in the held B moves the phase's weight fraction
    by the factor exp(2·δB·s̄²) — about 100·(exp(2·s̄²) − 1) % per Å², relative,
    before the normalisation over phases damps it for a major phase.  s̄² is
    intensity-weighted (:func:`_intensity_weighted_s2`).  The covariance
    cannot say this: with B held, the fraction's esd carries none of B's
    uncertainty, and with B free it was the pinv cut that discarded the
    ridge and returned 0.000 ± 0.000 wt% (WP-1534 task 1).

    ``warning``: the reported fraction is a conditional statement, and nothing
    else in the result says on what.  A joint fit passes every histogram's
    model and values; the range quoted spans them.
    """
    def value_of(path: str) -> float | None:
        # a joint fit's held name is bare where shared, ``hist.h.``-scoped
        # where a histogram owns it
        h = int(path.split(".")[1]) if path.startswith("hist.") else 0
        return per_values[h].get(_unscoped(path))

    tt_min = min(m.tt_min for m in models)
    tt_max = max(m.tt_max for m in models)
    paths: dict[int, dict[str, None]] = {}
    stages: dict[int, dict[str, None]] = {}
    least: dict[int, float] = {}
    for sr in stage_results or ():
        columns = _scale_b_columns(sr)
        for ip, r in (sr.scale_b_held or {}).items():
            stages.setdefault(ip, {})[sr.name] = None
            least[ip] = min(float(r), least.get(ip, math.inf))
            for col in columns.get(ip, ()):
                paths.setdefault(ip, {})[col] = None
    out: list[Diagnostic] = []
    for ip in sorted(least):
        held = sorted(paths.get(ip, {}))
        names = list(stages[ip])
        name = structure.phases[ip].name
        n = len(held)
        at = ", ".join(f"{p} = {v:.4g}" for p in held[:3]
                       if (v := value_of(p)) is not None)
        message = (
            f"The fitted range {tt_min:.4g}-{tt_max:.4g}° cannot "
            f"separate phase {ip} ({name})'s scale from its displacement "
            f"parameters: their columns are {least[ip]:.1e} apart, under the "
            f"{SCALE_B_SEPARATION_FLOOR:.1e} the covariance can resolve. "
            f"{n} displacement "
            f"parameter{'' if n == 1 else 's'} {'was' if n == 1 else 'were'} "
            f"held for stage{'' if len(names) == 1 else 's'} "
            f"{', '.join(names)}"
            + (f" ({at}{'…' if n > 3 else ''})" if at else "")
            + ". The phase's weight fraction is conditional on "
            + ("that value." if n == 1 else "those values."))
        s2 = _intensity_weighted_s2(models, ip, per_values)
        if s2 is not None:
            message += (f" Each 1 Å² of error in B moves it by about "
                        f"{100.0 * math.expm1(2.0 * s2):.2g} % "
                        f"(intensity-weighted mean s² = {s2:.3g} Å⁻² over its "
                        f"reflections in range).")
        out.append(Diagnostic(
            level="warning", code="SCALE_B_INSEPARABLE",
            where=held, value=least[ip], message=message,
            suggestion=(
                "Supply B from elsewhere (a fit over a wider range, or a "
                "published value for this material at this temperature). "
                "Widening the fitted range to a second d-spacing of the "
                "phase also lifts the hold."),
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
                message=(f"Phase {ip} ({name}) refined {term} to a strain "
                         f"broadening of {width:.4g} deg (FWHM coefficient of "
                         f"tanθ), {width / STRAIN_FLAG_WIDTH:.0f}× the "
                         f"flag threshold of {STRAIN_FLAG_WIDTH}."),
                suggestion="Check whether BOUND_HIT fired on the same path. "
                           "If the specimen really is this defective, the "
                           "value stands; this flag changes nothing in the fit.",
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
#: 5 nm is placed inside that gap, well below the smallest real fit.  It is
#: deliberately *not* pushed up towards 33 nm: a real nanocrystalline specimen
#: of 5–30 nm is routine even though this particular archive of bulk
#: inorganics happens not to contain one, and a flag that fired on it would be
#: noise.  So this says only "a number to look at", which is the whole job of
#: the flag tier; the intent Michael set is *prevent runaways, do not
#: legislate physics*.  Since 1.10 nothing bounds a size from below but the
#: fitted range (:func:`~rietx.params.vector.size_cap`, WP-2002), so this flag
#: is also what meets a size small enough to leave the Bragg-peak model.
#:
#: ``gauss_size`` is a variance, so the size is read from its square root, the
#: same conversion :func:`~rietx.params.vector.size_cap_hi` uses for the bound.
SIZE_FLAG_SIZE_A = 50.0


def _width_census_diagnostics(model: CompiledModel, values: dict[str, float],
                              structure: Structure,
                              significance: np.ndarray | None = None,
                              sigma: float = PHASE_SUPPORT_SIGMA
                              ) -> list[Diagnostic]:
    """``PEAK_WIDTH_LAW_MISMATCH`` from the fit: the indexing census taken on
    the fitted channels, against each phase's width at the returned values.

    The comparison and the reason it runs here are
    :func:`~rietx.indexing.diagnostics.refinement_width_diagnostics`'s; this
    gathers the two numbers.  Declines, rather than guessing, where the model's
    width is not one number per angle: a phase with a Stephens ``microstrain``
    block (its width is per reflection, and the isotropic law alone would
    under-read it), or a width law that is not finite and positive on the grid.
    Only phases the data can see (``significance`` at or above
    :data:`~rietx.model.forward.PHASE_SUPPORT_SIGMA`, with a line in range)
    take part: an invisible phase's width explains no line of the census.
    ``significance`` is the vector ``PHASE_UNCONSTRAINED`` reads
    (:func:`_answer_significance`, WP-1523); ``None`` reads the screen, which
    is all a joint fit asks.  ``sigma`` is the threshold that diagnostic
    reads too (:func:`_reported_support_sigma`, WP-2002 B1).
    """
    from .indexing.diagnostics import refinement_width_diagnostics
    from .indexing.peaks import width_census

    if not model.phases or any(ph.microstrain is not None
                               for ph in structure.phases):
        return []
    tt = np.asarray(model.tt, dtype=np.float64)
    fwhm_inst = np.asarray(model.instrument_fwhm_deg(tt, values), dtype=np.float64)
    if not (np.all(np.isfinite(fwhm_inst)) and float(fwhm_inst.min()) > 0.0):
        return []
    census = width_census(tt, np.asarray(model.y_obs, dtype=np.float64),
                          np.asarray(model.sigma, dtype=np.float64), fwhm_inst)
    if census is None:
        return []
    positions, measured = census
    # only a phase the data can see is a candidate for "the closest width": a
    # phase at its scale floor contributes nothing to the lines measured, so
    # its width — a seeded or runaway lor_size — would otherwise be free to
    # land near the census and silence the warning the visible phases owe
    # (#585 follow-up).  Same authority and threshold as PHASE_UNCONSTRAINED.
    support = model.phase_support(values) if significance is None else significance
    line_counts = model.phase_line_counts()
    modelled: dict[int, tuple[str, float]] = {}
    for ip in range(len(model.phases)):
        if line_counts[ip] == 0 or support[ip] < sigma:
            continue
        (w1, w2), = model._width_block(ip, values, [positions], 0.0)
        fw = np.asarray(model.peak_fwhm(w1, w2), dtype=np.float64)
        if np.all(np.isfinite(fw)):
            modelled[ip] = (structure.phases[ip].name, float(np.median(fw)))
    return refinement_width_diagnostics(measured, modelled)


def _rigid_body_unsupported(table: ParameterTable,
                            params: list[RefinedParameter]) -> list[Diagnostic]:
    """``RIGID_BODY_UNSUPPORTED``: a free body DOF that measured nothing.

    One finding per body, ``where`` its DOFs whose column had no gradient at
    all (``ParameterTable.unmeasured_free``, so the esd is absent rather than
    infinite).  The commonest cause is a body whose atoms the pattern cannot
    see in that direction: a turn that moves only zero-occupancy atoms, or one
    about an axis the template is symmetric under.  Every body atom row then
    carries no esd either, which the rows already say; this says which DOF
    did it.  A body a stage *held* (an absent phase, WP-1301) is
    ``PHASE_UNCONSTRAINED``'s, never this.
    """
    owner = table.body_dofs()
    free = set(table.free_paths)
    blind: dict[str, list[str]] = {}
    for row in params:
        if row.path in owner and row.path in free and row.stderr is None:
            blind.setdefault(owner[row.path], []).append(row.path)
    return [Diagnostic(
        level="warning", code="RIGID_BODY_UNSUPPORTED", where=paths,
        message=(f"Rigid body {name!r}: {len(paths)} free degree(s) of freedom "
                 f"measured nothing ({', '.join(paths)})."),
        suggestion="Hold them (Refinement.hold) and refit.")
        for name, paths in blind.items()]


def _size_flag_diagnostics(model: CompiledModel, values: dict[str, float],
                           structure: Structure) -> list[Diagnostic]:
    """``SIZE_UNUSUALLY_SMALL`` — a crystallite past what solved refinements use.

    The size twin of :func:`_strain_flag_diagnostics`, and the two do the same
    two-tier job.  One tier down, :func:`~rietx.params.vector.size_cap` is a
    solver bound (a line no wider than the fitted range); it protects the
    *numerics* and reports itself as ``BOUND_HIT``.  This tier protects the
    *interpretation*: a refined size below :data:`SIZE_FLAG_SIZE_A` is
    physically possible — real nanocrystals reach a few nm — so the fit is
    finished and may be right, but it sits below the archive of solved
    refinements and is worth a look.  Below about 2 nm a crystallite is a few
    unit cells, and the message says the Bragg-peak model may not describe its
    pattern; the Debye scattering equation does (Debye, 1915, *Ann. Phys.*
    **351**, 809).  It gates nothing ("report, never refuse") and is
    per-pattern, which is where a batch caller needs it.

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
                message=(f"Phase {ip} ({name}) refined {term} to an apparent "
                         f"crystallite size of {size_nm:.3g} nm "
                         f"(Scherrer K={SCHERRER_K}, λ={lam:.4g} Å), below the "
                         f"flag threshold of {floor_nm:.0f} nm. Below about "
                         f"2 nm a crystallite is a few unit cells, and "
                         f"broadened Bragg peaks may not describe its pattern "
                         f"(the Debye scattering equation does)."),
                suggestion="Check whether BOUND_HIT fired on the same path. "
                           "If the specimen really is this small, the value "
                           "stands; this flag changes nothing in the fit.",
            ))
    return out


def _occupancy_flag_diagnostics(values: dict[str, float], moving: set[str],
                                structure: Structure,
                                esds: dict[str, float] | None = None
                                ) -> list[Diagnostic]:
    """``OCCUPANCY_ABOVE_ONE`` — a refined occupancy past a full site.

    ``Atom.occ`` is bounded at 0 and nowhere above since 1.10 (WP-2002, the B9
    ruling of 2026-10-19: "Unlimited occupancy is fine.  We can give a
    warning.").  An occupancy above 1 puts more scatterers on a site than the
    site holds.  It is still the right number when the occupancy is doing the
    work of site scattering: Mg declared on a mixed Fe-Mg site reads
    26/12 ≈ 2.2 at full Fe.  So this reports the number and gates nothing,
    the third kind of DESIGN.md § Rules, 1.  Full occupancy is 1 by
    definition, so the threshold is no choice.

    Only an occupancy the fit moved is judged: ``moving`` is the free paths
    and the ties that follow them (``ParameterTable.moving_paths``).  A held
    value is the caller's own statement, and judging it would repeat the
    declaration back on every fit.  Strictly above 1, so a site refined to
    exactly full is silent.

    An info record, never a warning (ruled 2026-10-20).  A full site refined
    freely lands above 1 by counting noise about half the time (measured on
    synthetic LaB6: true occupancy 1.0, refined 1.032 ± 0.025), so a warning
    fired on half of honest fits, and a significance gate would add a chosen
    number of esds.  The message states the distance in esds wherever
    ``esds`` holds one, so a reader can tell noise from a site that really
    scatters more than its declared species.
    """
    out: list[Diagnostic] = []
    for ip, phase in enumerate(structure.phases):
        for j, atom in enumerate(phase.atoms):
            path = f"phases.{ip}.atoms.{j}.occ"
            occ = values.get(path)
            if path not in moving or occ is None or not occ > 1.0:
                continue
            esd = (esds or {}).get(path)
            if esd is not None and esd > 0.0:
                how_far = (f"{occ:.4g} ± {esd:.2g}, {(occ - 1.0) / esd:.1f} esd "
                           f"above a full site")
            else:
                how_far = f"{occ:.4g}, more than a full site"
            out.append(Diagnostic(
                level="info", code="OCCUPANCY_ABOVE_ONE",
                where=[path], value=float(occ),
                message=(f"Phase {ip} ({phase.name}): atom {atom.label!r} "
                         f"({atom.species}) refined its occupancy to "
                         f"{how_far}."),
                suggestion=("This is expected when the occupancy refines the site "
                            "scattering of a mixed site declared as its lighter "
                            "species. Otherwise check the species, the site "
                            "multiplicity and the displacement parameter, which "
                            "competes with the occupancy for the same intensity."),
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
    positions = _reflection_bragg_angles(model, values)
    if not positions.size:
        return []
    tt_min = float(np.min(positions))
    factor = np.asarray(model._roughness_factor(positions, values))
    depression = float(1.0 - np.min(factor))

    def drawn(tt: float) -> float:
        # the checks read Bragg angles; a message quotes the pattern's own axis,
        # which is where a reader looks and where a fit range is set
        return float(np.asarray(model.apparent_two_theta(np.array([tt]), values),
                                dtype=np.float64).reshape(-1)[0])

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
                         f"angle ({drawn(tt_min):.2f}° 2θ)."),
                suggestion="Restrict the fit to 2θ above "
                           f"{drawn(2 * np.degrees(np.arcsin(min(tau, 1.0)))):.1f}°, or "
                           "switch to kind='suortti'.",
            ))
        elif tau > 0.5 * sin_min:
            out.append(Diagnostic(
                level="info", code="ROUGHNESS_OUTSIDE_REGIME",
                where=[f"{base}.tau"],
                message=(f"Pitschke roughness is past its turnover at the low "
                         f"end of the fit (tau={tau:.4f} vs sin(theta)="
                         f"{sin_min:.4f} at {drawn(tt_min):.2f}° 2θ)."),
                suggestion="Treat tau as a fitting parameter, or restrict the "
                           "fit to higher angle.",
            ))

    if depression < ROUGHNESS_MIN_DEPRESSION:
        # Suortti's form is the identity at b = 0 and at a = 1, and the esds
        # the fit quotes depend on which the solver stopped at: b's column is
        # zero at a = 1, a's at b = 0.  Measured on the CPD round robin, the
        # scale's and Biso's esds differ ×1.1 to ×4.4 between the two at one
        # set of values (WP-2002, fifth round's Q4).  Said rather than
        # canonicalised: the case is rare, and dropping the block, which this
        # warning already asks for, gives one reading whichever way it ended.
        off = model.roughness == "suortti" and depression == 0.0
        at = ("b = 0" if off and values[f"{base}.b"] == 0.0 else "a = 1")
        out.append(Diagnostic(
            level="warning", code="ROUGHNESS_UNCONSTRAINED",
            where=[f"{base}.{n}" for n in ("a", "b", "c", "tau")
                   if f"{base}.{n}" in values],
            message=(f"The refined surface roughness depresses intensity by at "
                     f"most {depression:.2%} at any modelled reflection "
                     f"(lowest at {drawn(tt_min):.2f}° 2θ)."
                     + (f" It ended switched off at {at}, one of the Suortti "
                        "form's two off states (b = 0, or a = 1), and the "
                        "esds of the scale and Biso depend on which one."
                        if off else "")),
            suggestion=("Drop the roughness block, or extend the measurement "
                        "to lower 2θ."
                        + (" Without the block the esds no longer depend on "
                           "where the correction switched off." if off else "")),
        ))
    return out


#: how many stale pairs a ``RESTRAINT_PAIRS_STALE`` message spells out; the
#: count is always given in full
RESTRAINT_PAIRS_STALE_LISTED = 5


def _anti_bump_start_phases(structure: Structure, mode: str) -> list:
    """Per phase, a copy of it as the run starts (``None`` where nothing is searched).

    A copy rather than its contacts inside r₀: those cost a whole pair search,
    23 ms a call on paracetamol (20 atoms, P2₁/n), and the two a run makes were
    12 % of a 0.40 s scale-and-background fit of it.  A run that moves no
    coordinate and no cell length or angle cannot bring a contact inside r₀,
    so the search waits for the end of the run and is made only where the
    geometry moved.
    """
    from .schemas.structure import AntiBumpRestraint

    if mode != "rietveld":
        return [None] * len(structure.phases)
    return [ph.model_copy(deep=True)
            if any(isinstance(r, AntiBumpRestraint) for r in ph.restraints) else None
            for ph in structure.phases]


def _contact_geometry(phase) -> tuple:
    """Everything a phase's contacts are measured from that a fit can move."""
    return (tuple((a.x.value, a.y.value, a.z.value) for a in phase.atoms),
            phase.cell.lengths_angles())


def _restraint_pairs_stale_diagnostics(structure: Structure,
                                       since: list) -> list[Diagnostic]:
    """``RESTRAINT_PAIRS_STALE`` — a contact inside r₀ that no row restrains.

    The anti-bump pair list is built by the caller, once, so the plan's row
    count never moves (WP-1809's handover); the cost is that a pair which
    drifts inside its minimum from outside the list is not restrained.  At
    plan end each phase with an anti-bump row is searched at the answer's
    coordinates (:func:`rietx.model.restraints.stale_anti_bump_pairs`), and
    one warning per phase names what it found, closest-inside first.
    ``since`` is each phase as the run *started* (:func:`_anti_bump_start_phases`),
    whose contacts inside r₀
    (:func:`~rietx.model.restraints.anti_bump_contact_keys`) are the caller's:
    the list does not remember what it was built from, so a contact already
    inside r₀ then — a bond the caller left out of the list — is theirs and
    never named, which makes "entered" true.  A phase whose coordinates and
    cell are bit-for-bit where they started has the same contacts, so none
    entered and neither search runs.  ``run_stage`` runs it too, one stage's
    start being its own ``since``.
    """
    from .model.restraints import anti_bump_contact_keys, stale_anti_bump_pairs

    out: list[Diagnostic] = []
    for phase, start in zip(structure.phases, since, strict=True):
        if start is None or _contact_geometry(start) == _contact_geometry(phase):
            continue
        stale = stale_anti_bump_pairs(phase, since=anti_bump_contact_keys(start))
        if not stale:
            continue
        lab = [a.label for a in phase.atoms]
        shown = "; ".join(f"{lab[i]}–{lab[j]} {d:.3f} Å (r₀ {r0:.3g})"
                          for i, j, d, r0 in stale[:RESTRAINT_PAIRS_STALE_LISTED])
        more = len(stale) - RESTRAINT_PAIRS_STALE_LISTED
        out.append(Diagnostic(
            level="warning", code="RESTRAINT_PAIRS_STALE",
            where=sorted({f"{phase.name} {lab[k]}" for i, j, _, _ in stale
                          for k in (i, j)}),
            value=float(len(stale)),
            message=(f"phase {phase.name!r}: {len(stale)} contact(s) came inside "
                     f"their anti-bump minimum during the run and have no row "
                     f"in the pair list: "
                     f"{shown}" + (f"; and {more} more" if more > 0 else "")),
            suggestion="rebuild the list with anti_bump_restraints from these "
                       "coordinates (or with a wider margin) and refit; or, if "
                       "the contact is real, lower that species pair's minimum "
                       "distance"))
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


def _tie_refusal_text(path: str, refused: tuple[str, str]) -> str:
    """The reason a recorded tie is dropped, from ``tie_source_refusal``.

    One sentence for ``_apply_ties`` and ``replay``.  A source resting on a
    fixed row through its own tie is not itself fixed, so it is named as what
    it is.
    """
    src, what = refused
    if what in ("locked row", "derived row"):
        return f"{path} (source {src} now structurally fixed)"
    return f"{path} (source {src} is now a {what})"


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
    require_two_theta(data, "replay()")
    node = tree[node_id]
    expected = tree.header.data_fingerprint
    if expected:
        actual = fingerprint(data.x(), data.intensity)
        if actual != expected:
            raise ValueError(
                f"pattern does not match this history: fingerprint {actual[:8]} "
                f"but the tree was recorded against {expected[:8]}")

    state = node.state
    twins: list[Diagnostic] = []
    structure = merge_site_twins(state.structure.model_copy(deep=True),
                                 diagnostics=twins)
    moves = numbering_moves(state.structure, structure)
    if moves:
        state = state.model_copy(deep=True)
        carry_state_constraints(state, moves, twins)
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
                            lo=prm.min, hi=prm.max, unit=prm.unit)
    table.set_vary(["*"], False)
    applied_ties: dict = {}
    dropped: list[str] = []
    for path, spec in state.ties.items():
        # the user constraints the node was recorded under: without them the
        # replayed model has a different parameter count from the one whose
        # statistics this call exists to reproduce (WP-1070)
        tie = AffineTie(terms=tuple((p, float(c)) for p, c in spec.terms),
                        const=float(spec.const))
        # A node recorded before WP-1804 can hold a tie whose source a later
        # model edit locked.  ``_apply_ties`` drops it (and ``checkout`` with
        # it); ``set_tie`` would raise, so replay and checkout would disagree
        # about one node.  The flattened tie had an empty C row — never a
        # column — so skipping it changes no count, value or statistic.
        refused = table.tie_source_refusal(tie)
        if refused is not None:
            dropped.append(_tie_refusal_text(path, refused))
            continue
        table.set_tie(path, tie)
        applied_ties[path] = spec
    if dropped:
        warnings.warn(
            f"{len(dropped)} user tie(s) recorded on this node no longer apply "
            f"to its model and were dropped: {'; '.join(dropped)}.",
            UserWarning, stacklevel=2)
    # and the anchors, for ``_apply_ties``' reason (WP-1432): this table is
    # built from the node's *own* structure, whose coordinates already carry
    # whatever the recorded tie displaced them by.  Un-rebased, replay
    # answered for a model one displacement further on than the node it was
    # asked about — 0.2174 against the recorded 0.2084 — and nothing in the
    # answer said so.
    table.rebase_anchored_dofs(applied_ties)
    table.refresh_ties()
    for path in state.free_paths:
        table.set_vary([path], True)

    # the compile settings the stage ran at, which the node records: its
    # windows (a closing stage's area fraction, WP-2002, the sixth round's Q1
    # and Q2, and a declared capture slack) and its c_w.  At the defaults the
    # curve would be a different model from the one the stage solved.  Every
    # other kind of node carries the defaults.
    action = node.action
    model = compile_model(structure, instrument, data, mode=state.mode,
                          two_theta_limits=state.two_theta_limits,
                          moving_paths=set(table.moving_paths),
                          restraint_weight_scale=action.restraint_weight_scale,
                          window_slack_deg=action.window_slack_deg,
                          window_area_tol=recorded_window_tol(action.window_area_tol))
    if state.mode in ("lebail", "pawley"):
        _restore_lebail(state.reflections, model)

    result = _build_result(
        model, table, table.x0(), mode=state.mode,
        status=node.metrics.status or "converged", stage_results=[],
        diagnostics=twins + list(node.diagnostics), structure=structure,
        # ``PHASE_UNCONSTRAINED`` read against the threshold the stage ran
        # at, or the default where the node is not a stage (WP-2002, B1)
        phase_support_sigma=node.action.phase_support_sigma,
        held_scales=set(node.metrics.held_scale_phases))
    result.node_id = node.id
    result.tree_id = tree.header.tree_id
    return result


def estimate_mu_r(structure: Structure, instrument: Instrument) -> float | None:
    """Starting µR for a packed capillary, from composition and geometry.

    Combines each phase's linear attenuation coefficient — McMaster tables
    (:mod:`rietx.crystallography.attenuation`) on an X-ray source, Sears
    (1992) cross-sections (:mod:`rietx.crystallography.neutron`) on a
    constant-wavelength neutron one — into a volume-fraction-weighted bulk µ,
    scales it by ``Geometry.packing_fraction`` — voids do not absorb — and
    multiplies by ``Geometry.capillary_radius_mm``.

    Returns ``None`` rather than raising when µ is unavailable (a wavelength
    whose tabulation interval straddles an absorption edge, an element outside
    the compilation, an energy outside 2-120 keV; on neutrons, a species the
    Sears table lacks or a resonant absorber — Cd, Sm, Eu, Gd, Yb — refused at
    every wavelength) or when the geometry carries no capillary radius.  Use
    it to *populate* ``Geometry.mu_r``; a refinement will do the same thing
    itself at compile time if ``mu_r`` is left ``None``.

    ``None`` on a source kind with no table (time-of-flight among them) —
    each radiation's attenuation is its own quantity
    (:data:`_NO_ATTENUATION_TABLE_ESTIMATE` has the physics).  Returning a
    number from another radiation's table would be worse than returning
    nothing: the caller asked for a starting µR and would have no way to tell
    that it came from the wrong radiation.

    µR is not refinable, deliberately — see :mod:`rietx.model.absorption`.
    """
    geom = instrument.geometry
    if geom.kind != "debye_scherrer" or geom.capillary_radius_mm is None:
        return None
    if not _has_attenuation_table(instrument):
        return None
    table = ParameterTable(structure, instrument)
    mu_r, _ = estimate_capillary_mu_r(
        structure, table.decode(table.x0()),
        instrument.source.primary_wavelength,
        geom.capillary_radius_mm, geom.packing_fraction,
        source_kind=instrument.source.kind)
    return mu_r


def refine(data: PatternData, structure: Structure, instrument: Instrument,
           *, mode: Mode = "rietveld", plan: RefinementPlan | str = "mccusker_default",
           two_theta_limits: tuple[float, float] | None = None,
           backend: str = "numpy", solver: str = DEFAULT_SOLVER,
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
