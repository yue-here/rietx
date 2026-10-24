"""WP-2001 — the generality audit table: every heuristic with its tier.

The rule lives in ``docs/milestones/generality.md`` § The rule and is not
restated here beyond what a row needs.  Each part of a heuristic is tiered on
its own: (1) physics or arithmetic; (2) established practice, a citation that
validated it or the same choice made *by default* in an established Rietveld
program (the seven rietx-bench runs: GSAS-II, FullProf, TOPAS, RIETAN-FP,
BGMN, MAUD, EasyDiffraction), whatever the other six do; (3) rietx's own, kept only on the record's two grounds with the
maintainer's dated approval.  ``invariant`` is the record's answer-invariant
class.  ``caller`` is no evidence grade: it marks a row where the package
decided nothing for the caller, since DESIGN.md § Rules, 1 governs what the
package decides alone.  Both must hold: the caller asked for it by name (a flag
or field whose default is off, or a verb no default path calls), and nothing
inside it that moves the answer is the package's choice.  A number defaulted
once the switch is on is tiered on its own, and a caller row holds only while
its switch stays off the default paths (the record's § The rule, ruled
2026-10-21).  Every row opened at ``unaudited``; WPs 2002-2007 fill them.

**Five kinds, each named the way the tree names it.**

- ``code``: a :class:`~rietx.schemas.common.Diagnostic` code, spelled as in
  :data:`rietx.help.DIAGNOSTIC_HELP`, whose keys ``tests/test_help.py`` holds
  equal to the raise sites.  Never a grep for ``code="…"``: seven codes are
  raised through a name.
- ``action``: an automatic action, keyed on the record field that reports it
  (``rietx.schemas.results.StageResult.held``).  Fields of
  :data:`RECORD_SCHEMAS` that report no action the filing named are listed in
  :data:`OTHER_RECORD_FIELDS`, so a new field must land in one or the other.
- ``constant``: a module-level number, or tuple of numbers, in a file under
  :data:`WALKED`, named ``module.NAME``.
- ``default``: a default at a seat in :data:`DEFAULT_SEATS`, named
  ``seat:parameter``, ``None`` included: a ``None`` often means the package
  picks (``telemetry=None`` records the run, ``preset=None`` runs ``quick``).
- ``suggestion``: the ``suggestion=`` sites of one code, named
  ``CODE.suggestion``, or ``module.function.suggestion`` where the call names
  its code through a variable.  The value is the site count, so a new site
  fails and a reworded one does not.

Constant, default and suggestion rows store the live value, so a retune fails
``tests/test_audit_table.py`` and reopens the row's audit.

**The suite's growth guard reads no git.**  CI's test jobs have no
``origin/main``, so a comparison against the base table would skip exactly
where it gates a merge.  A local ``origin/main`` can be stale.
:data:`UNAUDITED_BASELINE` is instead the committed list of the rows still
waiting for their audit.  A row at
``unaudited`` off the list fails, and so does a name on the list whose row was
audited, so the list shrinks as the audits land.  CI's lint job does read the
base, at ``HEAD^1`` (``tests/audit_delta.py``).  It prints every row a change
adds, changes or deletes.  It fails a name new to :data:`ROWS` at
``unaudited``.  The ``generality-review`` agent reads every edit to this
table.  ``/wp-handover`` step 7 dispatches it on a WP branch, and
``/pr-review`` on an outside pull request.

**Out of scope by declaration.**  An entry of :data:`NOT_WALKED`, each with
its reason, and a default outside :data:`DEFAULT_SEATS`: the walk over all of ``src/rietx``
found 619 constants, the surplus being byte offsets in file readers, pixel
sizes in the 3D viewer and schema defaults (third review).  **What the guard
cannot see**: an inline literal (about 30 in ``refine.py``, such as
``< 0.7`` at the plate-thickness test); a number inside a dict, list or array
(``indexing.engines.SEARCH_PRESETS``' 120 s quick budget,
``report.texture._R_GRID``); an ordering or a fallback chain; an
always-on correction with no switch, threshold or new field (the
Bérar-Lelann esd inflation was one); and a heuristic written as skill prose
(WP-2008).

The owning audit of each constant is its directory's, recorded in
:data:`WALKED`; ``optimize/statistics.py``'s report-facing rows go to 2004.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import math
import numbers
import pathlib
from typing import Literal

Kind = Literal["code", "action", "constant", "default", "suggestion"]
Tier = Literal[1, 2, 3, "invariant", "caller", "unaudited"]
Ambiguity = Literal[1, 2, 3]

KINDS: tuple[str, ...] = Kind.__args__
TIERS: tuple[object, ...] = Tier.__args__
_VALUED = ("constant", "default", "suggestion")
_STATES_AMBIGUITY = ("code", "action", "default")


@dataclasses.dataclass(frozen=True)
class Row:
    """One heuristic.  ``grounds`` and ``approved`` are required on a tier-3
    row and on a tier-2 action row; ``ambiguity`` is DESIGN.md § Rules, 1's
    kind, required on an audited code, action or default row (DESIGN.md
    § Rules, 4 asks a new default or action for it) and allowed on a
    suggestion row."""

    name: str
    kind: Kind
    tier: Tier = "unaudited"
    ambiguity: Ambiguity | None = None
    evidence: str = ""
    grounds: str = ""
    approved: str | None = None
    value: object = None


_PACKAGE = pathlib.Path(__file__).resolve().parent

#: The files and directories the constant walk covers, each with the audit WP
#: that owns its rows.  ``io/`` and ``gui/`` contribute only the files that
#: decide something, :data:`NOT_WALKED` saying what the rest hold.
#: Within ``schemas/``, ``indexing.py``'s rows go to 2007 and ``results.py``'s
#: and ``suggest.py``'s to 2004; ``params/multi.py``'s go to 2003.
WALKED: dict[str, int] = {
    "refine.py": 2002,
    "strategy": 2002,
    "background": 2002,
    "optimize": 2002,
    "model": 2002,
    "params": 2002,
    "schemas": 2002,
    "sequential.py": 2003,
    "multi.py": 2003,
    "report": 2004,
    "io/readers.py": 2006,
    "io/formats/base.py": 2006,
    "crystallography": 2006,
    "indexing": 2007,
    "solve": 2007,
    "project.py": 2002,
    "io/formats/dif.py": 2006,
    "io/formats/gsas.py": 2006,
    "io/formats/peaklist.py": 2006,
    "io/instrument_profile.py": 2006,
    "io/projects/fullprof.py": 2006,
    "io/projects/registry.py": 2006,
    "io/projects/topas_input.py": 2006,
    "gui/imports.py": 2006,
    "gui/symmetry.py": 2006,
}

#: Every top-level entry of the package the walk leaves out, with the reason.
#: ``io`` is here for what its two walked files leave.  Each entry is in
#: :data:`WALKED` or here, held by test, so a new module is placed when it is
#: made.  An entry is walked where a module-level number in it could move a
#: fitted value, a verdict, how a file is read, or what another program
#: computes from a file rietx writes (WP-2014, which walked ``solve``,
#: ``project.py`` and nine files under ``io`` and ``gui``).
NOT_WALKED: dict[str, str] = {
    "__init__.py": "re-exports and the lazy-import table",
    "_about.py": "the distribution's names, format tokens and state directory",
    "_audit.py": "this table",
    "_display.py": "the widths of printed displays, which read fields and compute nothing",
    "_nearmiss.py": "difflib's own 0.6 cutoff, ranking the names a 'did you mean' error offers",
    "backend": ("two bars the tests hold an fp32 Jacobian column to, and a chunk size that "
                "moves memory use and no value"),
    "capabilities.py": "reads the registries and decides nothing",
    "cli.py": "terminal entry points over the API",
    "compare_app": "the comparison page's port",
    "data": "bundled tables, read by modules the walk covers",
    "examples.py": "the shipped example projects",
    "gui": ("beyond its import pre-fill and its symmetry edit gates: the server and 3D "
            "viewer's ports, payload caps and drawing tolerances"),
    "help.py": "the explanation text",
    "history": "the history tree's storage, and its event summary's printed row count and read chunk",
    "io": ("beyond the walked files, which repair, sniff, translate or write a number another "
           "program computes from: foreign formats' byte offsets, field widths, unit factors "
           "and size caps"),
    "runs.py": ("telemetry: flush cadence, retention by bytes and age, and Windows error codes; "
                "none reads a pattern"),
    "skill.py": "installs the agent skill",
    "viz": "figures and the live snapshot: sizes, colours, point caps and the 3D view drawn first",
    "watch": "the live viewer's timeouts and cache lifetime",
}

#: The classes and functions whose defaults the table holds, each with its
#: owning audit.  ``Source`` is here because its ``dispersion`` default
#: turned a correction on in v1.0, ``ProfileTCHZ`` because its widths' seeds
#: and box are dicts the constant walk cannot see (WP-2002, B14);
#: ``SequentialRefinement.fit`` and
#: ``SearchSpec`` because a declared seat reaches them, through
#: ``refine_sequential``'s ``**kw`` and ``index_pattern``'s ``spec=None``.
DEFAULT_SEATS: dict[str, int] = {
    "rietx.schemas.plan.PlanSpec": 2002,
    "rietx.schemas.plan.StageSpec": 2002,
    "rietx.schemas.instrument.Source": 2002,
    "rietx.schemas.instrument.ProfileTCHZ": 2002,
    "rietx.refine.Refinement.fit": 2002,
    "rietx.refine.Refinement.run_stage": 2002,
    "rietx.refine.refine": 2002,
    "rietx.background.auto.auto_background": 2002,
    "rietx.sequential.refine_sequential": 2003,
    "rietx.sequential.SequentialRefinement.fit": 2003,
    "rietx.indexing.workflow.index_pattern": 2007,
    "rietx.indexing.engines.SearchSpec": 2007,
}

#: The record schemas whose fields the guard holds.
RECORD_SCHEMAS: tuple[str, ...] = (
    "rietx.schemas.results.StageResult",
    "rietx.schemas.sequential.SeriesEntry",
    "rietx.schemas.results.RefinementResult",
    "rietx.schemas.results.Statistics",
)


def resolve(path: str) -> object:
    """The object a dotted ``module.attr.attr`` path names.

    Only a miss on the candidate module itself falls back to a shorter one; a
    dependency missing inside a real module raises as itself."""
    parts = path.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        try:
            obj = importlib.import_module(candidate)
        except ModuleNotFoundError as exc:
            if exc.name is None or not (candidate == exc.name
                                        or candidate.startswith(exc.name + ".")):
                raise
            continue
        for attr in parts[i:]:
            obj = getattr(obj, attr)
        return obj
    raise ImportError(path)


def normal(value: object) -> object:
    """``value`` in the form a row stores: plain python, comparable by repr."""
    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return float(value)
    if isinstance(value, (tuple, list)):
        return tuple(normal(v) for v in value)
    if callable(value) and hasattr(value, "__qualname__"):
        # repr carries a memory address, which no two processes share
        return f"{getattr(value, '__module__', '?')}.{value.__qualname__}"
    return repr(value)


def same(a: object, b: object) -> bool:
    """Equal to the bit, NaN included, and of the same type."""
    return repr(a) == repr(b)


def _number(value: object) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def _module_name(path: pathlib.Path) -> str:
    parts = path.relative_to(_PACKAGE).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(("rietx", *parts))


def _walked_files() -> list[pathlib.Path]:
    files = []
    for entry in WALKED:
        path = _PACKAGE / entry
        files += [path] if path.is_file() else sorted(path.rglob("*.py"))
    return files


def _assigned(node: ast.stmt) -> list[str]:
    """The names a module-level statement binds: ``A = B = 1`` and
    ``LO, HI = 0.4, 10.0`` bind two each."""
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
    else:
        return []
    names = []
    for target in targets:
        elts = target.elts if isinstance(target, ast.Tuple) else [target]
        names += [t.id for t in elts if isinstance(t, ast.Name)]
    return names


def constants() -> dict[str, object]:
    """Every module-level number, or tuple of numbers, under :data:`WALKED`."""
    out = {}
    for path in _walked_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # a name a function rebinds through ``global`` is state, and its live
        # value is whatever ran before (``compiled._POOL_WORKERS``)
        rebound = {n for node in ast.walk(tree) if isinstance(node, ast.Global)
                   for n in node.names}
        names = [n for node in tree.body for n in _assigned(node)
                 if not n.startswith("__") and n not in rebound]
        if not names:
            continue
        module = importlib.import_module(_module_name(path))
        for name in names:
            value = getattr(module, name)
            if _number(value) or (isinstance(value, tuple) and value
                                  and all(_number(v) for v in value)):
                out[f"{module.__name__}.{name}"] = normal(value)
    return out


def defaults() -> dict[str, object]:
    """Every default at :data:`DEFAULT_SEATS`."""
    from pydantic import BaseModel

    out = {}
    for seat in DEFAULT_SEATS:
        obj = resolve(seat)
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            items = [(name, field.get_default(call_default_factory=True))
                     for name, field in obj.model_fields.items()
                     if not field.is_required()]
        elif dataclasses.is_dataclass(obj):
            missing = dataclasses.MISSING
            items = [(f.name, f.default if f.default is not missing else f.default_factory())
                     for f in dataclasses.fields(obj)
                     if f.default is not missing or f.default_factory is not missing]
        else:
            items = [(name, p.default)
                     for name, p in inspect.signature(obj).parameters.items()
                     if p.default is not inspect.Parameter.empty]
        for name, value in items:
            out[f"{seat}:{name}"] = normal(value)
    return out


def record_fields() -> list[str]:
    """Every field of :data:`RECORD_SCHEMAS`, as ``schema.field``."""
    return [f"{schema}.{field}" for schema in RECORD_SCHEMAS
            for field in resolve(schema).model_fields]


class _SuggestionSites(ast.NodeVisitor):
    def __init__(self, module: str):
        self.module, self.stack, self.counts = module, [], {}

    def _scope(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope

    def visit_Call(self, node):
        keywords = {kw.arg: kw.value for kw in node.keywords}
        given = keywords.get("suggestion")
        if given is not None and not (isinstance(given, ast.Constant)
                                      and given.value is None):
            code = keywords.get("code")
            if isinstance(code, ast.Constant) and isinstance(code.value, str):
                key = f"{code.value}.suggestion"
            else:
                key = ".".join((self.module, *self.stack, "suggestion"))
            self.counts[key] = self.counts.get(key, 0) + 1
        self.generic_visit(node)


def suggestions() -> dict[str, int]:
    """The ``suggestion=`` sites across the package, counted per code."""
    out: dict[str, int] = {}
    for path in sorted(_PACKAGE.rglob("*.py")):
        visitor = _SuggestionSites(_module_name(path))
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        for key, n in visitor.counts.items():
            out[key] = out.get(key, 0) + n
    return out


def codes() -> list[str]:
    """Every diagnostic code, from the help registry."""
    from .help import DIAGNOSTIC_HELP

    return sorted(DIAGNOSTIC_HELP)


def _literal(value: object) -> str:
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, float) and not math.isfinite(value):
        return f'float("{value}")'
    if isinstance(value, tuple):
        inner = ", ".join(_literal(v) for v in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_literal(k)}: {_literal(v)}" for k, v in value.items()) + "}"
    return repr(value)


#: What a printed row holds where the author's answer goes.  Neither is a tier
#: or a kind of ambiguity, so a row pasted unfilled fails the table's tests.
PENDING = "?"


def row_source(name: str, kind: str, value: object = None) -> str:
    """The line a failure prints for ``name``: its tier, its kind of
    ambiguity where the row must state one, and its evidence left for the
    author.  A name new to the table may not enter at ``unaudited``."""
    ambiguity = f", ambiguity={_literal(PENDING)}" if kind in _STATES_AMBIGUITY else ""
    tail = f", value={_literal(value)}" if kind in _VALUED else ""
    return (f"Row({_literal(name)}, {_literal(kind)}, tier={_literal(PENDING)}{ambiguity}, "
            f'evidence=""{tail}),')


#: Fields of :data:`RECORD_SCHEMAS` that report no action the filing named.
#: An audit that finds one reporting an action moves it into :data:`ROWS`.
OTHER_RECORD_FIELDS: frozenset[str] = frozenset({
    "rietx.schemas.results.RefinementResult.cell_volumes",
    "rietx.schemas.results.RefinementResult.data_support",
    "rietx.schemas.results.RefinementResult.diagnostics",
    "rietx.schemas.results.RefinementResult.geometry",
    "rietx.schemas.results.RefinementResult.histograms",
    "rietx.schemas.results.RefinementResult.identifiability",
    "rietx.schemas.results.RefinementResult.microstructure",
    "rietx.schemas.results.RefinementResult.mode",
    "rietx.schemas.results.RefinementResult.n_background_components",
    "rietx.schemas.results.RefinementResult.n_extra_components",
    "rietx.schemas.results.RefinementResult.node_id",
    "rietx.schemas.results.RefinementResult.parameters",
    "rietx.schemas.results.RefinementResult.parametric",
    "rietx.schemas.results.RefinementResult.parametric_equations",
    "rietx.schemas.results.RefinementResult.parametric_form",
    "rietx.schemas.results.RefinementResult.parametric_form_joint",
    "rietx.schemas.results.RefinementResult.phase_agreement",
    "rietx.schemas.results.RefinementResult.provenance",
    "rietx.schemas.results.RefinementResult.qpa",
    "rietx.schemas.results.RefinementResult.restraints",
    "rietx.schemas.results.RefinementResult.sigma",
    "rietx.schemas.results.RefinementResult.stages",
    "rietx.schemas.results.RefinementResult.statistics",
    "rietx.schemas.results.RefinementResult.status",
    "rietx.schemas.results.RefinementResult.texture",
    "rietx.schemas.results.RefinementResult.tick_hkl",
    "rietx.schemas.results.RefinementResult.ticks",
    "rietx.schemas.results.RefinementResult.tree_id",
    "rietx.schemas.results.RefinementResult.two_theta",
    "rietx.schemas.results.RefinementResult.y_background",
    "rietx.schemas.results.RefinementResult.y_calc",
    "rietx.schemas.results.RefinementResult.y_obs",
    "rietx.schemas.results.StageResult.cost_final",
    "rietx.schemas.results.StageResult.cost_initial",
    "rietx.schemas.results.StageResult.freed",
    "rietx.schemas.results.StageResult.held_reach",
    "rietx.schemas.results.StageResult.n_iterations",
    "rietx.schemas.results.StageResult.name",
    "rietx.schemas.results.StageResult.status",
    "rietx.schemas.results.StageResult.unknown_paths",
    "rietx.schemas.results.StageResult.unreached_histograms",
    "rietx.schemas.results.Statistics.chi2",
    "rietx.schemas.results.Statistics.durbin_watson",
    "rietx.schemas.results.Statistics.gof",
    "rietx.schemas.results.Statistics.identifiability_clause",
    "rietx.schemas.results.Statistics.max_shift_over_esd",
    "rietx.schemas.results.Statistics.n_free_parameters",
    "rietx.schemas.results.Statistics.n_points",
    "rietx.schemas.results.Statistics.rexp",
    "rietx.schemas.results.Statistics.rp",
    "rietx.schemas.results.Statistics.rwp",
    "rietx.schemas.results.Statistics.rwp_background_subtracted",
    "rietx.schemas.sequential.SeriesEntry.diagnostics",
    "rietx.schemas.sequential.SeriesEntry.index",
    "rietx.schemas.sequential.SeriesEntry.label",
    "rietx.schemas.sequential.SeriesEntry.magnetic",
    "rietx.schemas.sequential.SeriesEntry.n_iterations",
    "rietx.schemas.sequential.SeriesEntry.node_id",
    "rietx.schemas.sequential.SeriesEntry.parameters",
    "rietx.schemas.sequential.SeriesEntry.phase_agreement",
    "rietx.schemas.sequential.SeriesEntry.qpa",
    "rietx.schemas.sequential.SeriesEntry.rwp_warm",
    "rietx.schemas.sequential.SeriesEntry.statistics",
    "rietx.schemas.sequential.SeriesEntry.status",
    "rietx.schemas.sequential.SeriesEntry.tree_id",
    "rietx.schemas.sequential.SeriesEntry.x",
})

ROWS: tuple[Row, ...] = (
    # code: 257
    Row("ABSORPTION_ESTIMATE_UNAVAILABLE", "code"),
    Row("ABSORPTION_MU_R_OUT_OF_RANGE", "code"),
    Row("ABSORPTION_PLATE_THICKNESS", "code"),
    Row("ABSORPTION_THICKNESS_MATTERS", "code"),
    Row("ADP_NOT_POSITIVE_DEFINITE", "code"),
    Row("AIR_SCATTER_UNDECLARED", "code"),
    Row("BACKGROUND_ABSORPTION", "code"),
    Row("BACKGROUND_ORDER_AT_CAP", "code"),
    Row("BISO_NEGATIVE", "code"),
    Row("BISO_UNUSUALLY_LARGE", "code"),
    Row("BOUND_HIT", "code"),
    Row("BRINDLEY_OUTSIDE_REGIME", "code"),
    Row("BRML_ABSORBER_ENGAGED", "code"),
    Row("CAPILLARY_OFFSET_UNAVAILABLE", "code"),
    Row("CELL_DEGENERATE_PROBE", "code"),
    Row("CELL_RUNAWAY", "code", tier=3, ambiguity=1,
        evidence=("WP-1110's trigger: a visible phase sharing its cell with a 2 % trace copy ran "
                  "4.16 -> 3803 A in one stage; fired in none of WP-1523's 104 fits; names what "
                  "StageResult.cell_reset records"),
        grounds=("The cell's reset is the package's own act, so it is said out loud with the "
                 "paths it put back (B8, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("CHILD_GROUP_UNNAMED", "code"),
    Row("CIF_CELL_ANGLE_CORRECTED", "code"),
    Row("CIF_MAGNETIC_CENTERING_ASSUMED", "code"),
    Row("CIF_MAGNETIC_ION_UNCHARGED", "code"),
    Row("CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED", "code"),
    Row("CIF_MAGNETIC_MOMENT_ON_ALLOWED", "code"),
    Row("CIF_MAGNETIC_NUCLEAR_GROUP", "code"),
    Row("CIF_MAGNETIC_NUCLEAR_SETTING", "code"),
    Row("CIF_MAGNETIC_NUMBER_MISMATCH", "code"),
    Row("CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED", "code"),
    Row("CIF_MAGNETIC_SYMMFORM", "code"),
    Row("CIF_MAGNETIC_UNIDENTIFIED", "code"),
    Row("CIF_SITE_LISTED_TWICE", "code"),
    Row("CIF_SITE_MULTIPLICITY_DISAGREES", "code"),
    Row("CIF_SITE_TWINS_MERGED", "code"),
    Row("CIF_SPECIES_NORMALISED", "code"),
    Row("CONSTRAINT_ACTIVE", "code"),
    Row("COVARIANCE_DIRECTION_DISCARDED", "code"),
    Row("COVARIANCE_UNAVAILABLE", "code"),
    Row("DATA_SUPPORT_LOW", "code"),
    Row("DECLARED_RANGE_NOT_RESTORED", "code"),
    Row("DECLARED_RANGE_RESTORED", "code"),
    Row("DISPERSION_NEGLECTED", "code"),
    Row("EXTINCTION_CONDITIONS_PARTIAL", "code"),
    Row("EXTINCTION_FORBIDDEN_INTENSITY", "code"),
    Row("EXTINCTION_GROUPS_NOT_SEPARABLE", "code"),
    Row("EXTINCTION_PRIOR_APPLIED", "code"),
    Row("EXTINCTION_SCREEN_FAILED", "code"),
    Row("EXTINCTION_SYMBOL_AMBIGUOUS", "code"),
    Row("EXTRA_PEAK_NO_INTENSITY", "code"),
    Row("EXTRA_PEAK_ON_REFLECTION", "code"),
    Row("FLAT_DIRECTION", "code"),
    Row("FLAT_DIRECTION_OMITTED", "code"),
    Row("FLOOR_HIT", "code"),
    Row("FROZEN_COMPILE_STALE", "code"),
    Row("FULLPROF_MAGNETIC_PHASE_OMITTED", "code"),
    Row("FULLPROF_MAGNETIC_PHASE_READ", "code"),
    Row("FULLPROF_OCCUPANCY_UNCHECKED", "code"),
    Row("FULLPROF_ORIGIN_CHOICE", "code"),
    Row("FULLPROF_RHOMBOHEDRAL_RESTATED", "code"),
    Row("FULLPROF_SPECIES_NORMALISED", "code"),
    Row("FULLPROF_SPECIES_WRITTEN_NEUTRAL", "code"),
    Row("FULLPROF_TIE_DROPPED", "code"),
    Row("GSAS2_CIF_DEUTERIUM_AS_D", "code"),
    Row("GSAS2_CIF_FIELD_NOT_WRITTEN", "code"),
    Row("GSAS2_CIF_RHOMBOHEDRAL_RESTATED", "code"),
    Row("GSAS2_CIF_SETTING_IN_OPERATORS", "code"),
    Row("GSAS2_CIF_SPECIES_WRITTEN_NEUTRAL", "code"),
    Row("GSAS2_GPX_BACKGROUND_NOT_CARRIED", "code"),
    Row("GSAS2_GPX_CONSTRAINT_NOT_CARRIED", "code"),
    Row("GSAS2_GPX_COORDINATES_SYMMETRY_FIXED", "code"),
    Row("GSAS2_GPX_ITEM_NOT_READ", "code"),
    Row("GSAS2_GPX_PHASE_MAGNETIC", "code"),
    Row("GSAS2_GPX_SCALE_NOT_COMPARABLE", "code"),
    Row("GSAS2_GPX_SETTING_FROM_OPERATORS", "code"),
    Row("GSAS2_GPX_SPECIES_NORMALISED", "code"),
    Row("GSAS2_GPX_TEXTURE_CONVERTED", "code"),
    Row("GSAS2_GPX_TEXTURE_NOT_CARRIED", "code"),
    Row("GSAS2_INSTPRM_CONVENTION_ASSUMED", "code"),
    Row("GSAS2_INSTPRM_FIELD_DROPPED", "code"),
    Row("GSAS2_INSTPRM_FIELD_NOT_READ", "code"),
    Row("GSAS2_INSTPRM_FIELD_NOT_WRITTEN", "code"),
    Row("GSAS2_INSTPRM_GEOMETRY_ASSUMED", "code"),
    Row("GSAS2_INSTPRM_VALUE_DEFAULTED", "code"),
    Row("GSAS2_INSTPRM_VALUE_FLOORED", "code"),
    Row("GSAS2_INSTPRM_VALUE_MERGED", "code"),
    Row("GSAS_BANK_COMMENTED", "code"),
    Row("GSAS_EXP_BACKGROUND_NOT_CARRIED", "code"),
    Row("GSAS_EXP_COORDINATES_SYMMETRY_FIXED", "code"),
    Row("GSAS_EXP_HISTOGRAM_NOT_READ", "code"),
    Row("GSAS_EXP_PHASE_MAGNETIC", "code"),
    Row("GSAS_EXP_REFINE_FLAG_MERGED", "code"),
    Row("GSAS_EXP_SCALE_NOT_COMPARABLE", "code"),
    Row("GSAS_EXP_SPECIES_NORMALISED", "code"),
    Row("GSAS_EXP_SPECIES_WRITTEN_NEUTRAL", "code"),
    Row("GSAS_EXP_VALUE_NARROWED", "code"),
    Row("GSAS_FIELD_OVERFLOW", "code"),
    Row("GSAS_IPARM_FIELD_DROPPED", "code"),
    Row("GSAS_IPARM_LEGACY_LAYOUT", "code"),
    Row("GSAS_IPARM_PROFILE_DECLINED", "code"),
    Row("GSAS_IPARM_PROFILE_READ", "code"),
    Row("GSAS_PRM_FIELD_DROPPED", "code"),
    Row("GSAS_PRM_FIELD_NOT_WRITTEN", "code"),
    Row("GSAS_PRM_GEOMETRY_ASSUMED", "code"),
    Row("GSAS_PRM_PROFILE_SET_DEFAULTED", "code"),
    Row("GSAS_PRM_VALUE_NARROWED", "code"),
    Row("HARMONIC_ABSENT", "code"),
    Row("HARMONIC_FRACTION", "code"),
    Row("HARMONIC_HELD", "code"),
    Row("HIGH_CORRELATION", "code"),
    Row("HIGH_CORRELATION_OMITTED", "code"),
    Row("HOLD_BLOCKED_PLAN", "code"),
    Row("HUMP_TOO_NARROW", "code"),
    Row("INDEX_ABSTAINED", "code"),
    Row("INDEX_BRAVAIS_AMBIGUOUS", "code"),
    Row("INDEX_BUDGET_EXHAUSTED", "code"),
    Row("INDEX_CANDIDATES_TRUNCATED", "code"),
    Row("INDEX_CELL_SYSTEMATIC_UNQUANTIFIED", "code"),
    Row("INDEX_DATA_INSUFFICIENT", "code"),
    Row("INDEX_DOMINANT_ZONE", "code"),
    Row("INDEX_GEOMETRIC_AMBIGUITY", "code"),
    Row("INDEX_IMPURITY_LINES", "code"),
    Row("INDEX_INLIER_RETRY", "code"),
    Row("INDEX_MULTIPLE_SOLUTIONS", "code"),
    Row("INDEX_NOT_VALIDATED", "code"),
    Row("INDEX_PANEL_REDUCED", "code"),
    Row("INDEX_PREDICTED_BUT_ABSENT", "code"),
    Row("INDEX_PRIOR_USED", "code"),
    Row("INDEX_SEARCH_INCOMPLETE", "code"),
    Row("INDEX_SHIFT_ALLOWANCE", "code"),
    Row("INDEX_SHIFT_DETECTED", "code"),
    Row("INDEX_SHIFT_FROM_PAIRS", "code"),
    Row("INDEX_SHIFT_MODEL_AMBIGUOUS", "code"),
    Row("INDEX_SINGLE_ENGINE", "code"),
    Row("INDEX_SUPERCELL_REFUTED", "code"),
    Row("INDEX_SYSTEMS_NOT_COVERED", "code"),
    Row("INDEX_VALIDATION_FAILED", "code"),
    Row("INDEX_VOLUME_UNPHYSICAL", "code"),
    Row("INDEX_Z_NOT_INTEGER", "code"),
    Row("K_VECTOR_UNSEPARATED", "code", tier=3, ambiguity=2,
        evidence=("info; fires when the top two k trials' best eligible ΔBIC lie within "
                  "SOLVE_K_TIE_DELTA_BIC, charged at N/f² since WP-2002 B12; Ba2FeSbSe5 1.5 K "
                  "(PRB 103, 054115, not vendored) is the one family with two k refined; "
                  "reports and changes no pick"),
        grounds=("Reports only, beside k_trials, the ranking that travels with solve_magnetic's "
                 "pick; Rare feature inside solve_magnetic, a pick verb whose whole ranking "
                 "travels with the pick; the Kass-Raftery band is cited, the N/f² count it is "
                 "applied to is rietx's own, so the row stays tier 3 (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("LANDE_G_ASSUMED", "code", tier=1, ambiguity=1,
        evidence=("physics: g_J from (S, L, J), Ashcroft & Mermin (1976) eq. 31.27 (docstring); "
                  "fires exactly when used")),
    Row("LAUE_CLASS_NOT_SEPARABLE", "code"),
    Row("LEBAIL_ALTERNATION_STOPPED", "code"),
    Row("LOW_ANGLE_UNMODELLED", "code"),
    Row("MAGNETIC_ION_ASSUMED", "code", tier=1, ambiguity=3,
        evidence=("arithmetic: fires exactly when the substitution was made (info); the "
                  "substitution's own tier is crystallography.magnetic.form_factor._ASSUMED_ION, "
                  "a hand row (a dict the walk cannot see; docs/wp/2002-batch/inventory.json)")),
    Row("MAGNETIC_SUBGROUP_PREFERRED", "code", tier=3, ambiguity=2,
        evidence=("warning; fires when a maximal subgroup refit from the winner beats it by "
                  "more than SOLVE_TIE_DELTA_BIC at the winner's own N/f² (WP-2002 B12); never "
                  "swaps the winner; the descent audit's synthetic negative control (F m -3 m, "
                  "BNS 71.536 against 12.62) stays inside the width; Cr2WO6 4 K and LaMnO3 50 K "
                  "winners have no subgroup among their classes"),
        grounds=("Reports only and hands the choice to the caller; Rare feature inside "
                 "solve_magnetic, a pick verb whose whole ranking travels with the pick; the "
                 "Kass-Raftery band is cited, the N/f² count it is applied to is rietx's own, "
                 "so the row stays tier 3 (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("MAGNETIC_WIDTH_MOVED_MOMENT", "code"),
    Row("MAGNETIC_WIDTH_UNMEASURED", "code"),
    Row("MAGNETIC_WIDTH_UNMODELLED", "code"),
    Row("MICROABSORPTION_SKIPPED", "code"),
    Row("MODEL_FAR_FROM_DATA", "code"),
    Row("MOMENT_ANGLE_STATIONARY", "code", tier=3, ambiguity=1,
        evidence=("WP-1929: two-site Pnma moduli 0.0015/0.0011 mu_B with the angle columns out, "
                  "0.031/0.159 in, 0.0035-0.47 as ftol moved; LaMnO3 BT-1: a polar angle 5.2 deg "
                  "off 90 with a 3.5 deg linear esd, Delta chi2 0.56 against 3.84; names what "
                  "StageResult.moment_angle_tests records and quotes RefinedParameter.interval; "
                  "one angle tested alone passes below the one-sided cut 2.706 and so nearly "
                  "always lies inside its 95 % interval (cut 3.84): the test's linearised "
                  "refit can sit up to 1.5 from the full refit the interval walks, more "
                  "than the 1.13 between the cuts, so 'excludes' stays reachable"),
        grounds=("The column leaves the covariance by the package's own act, so the finding "
                 "says so, with each angle's distance from the direction and its profile "
                 "interval (B2 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("MOMENT_PAIR_DEGENERATE", "code"),
    Row("NEUTRON_RESONANT_ABSORBER", "code"),
    Row("OCCUPANCY_ABOVE_ONE", "code", tier=1, ambiguity=3,
        evidence=("physics: a full site is occupancy 1 by definition; reports the refined "
                  "value with its distance in esds and gates nothing (B9 ruling "
                  "2026-10-19: occupancy unbounded above; an info record, ruled "
                  "2026-10-20, because noise puts a free full site above 1 about half "
                  "the time, 1.032 ± 0.025 on synthetic LaB6)")),
    Row("ORIGIN_FIXED_ON_POLAR_AXIS", "code"),
    Row("ORIGIN_NOT_FIXED", "code"),
    Row("PARAMETRIC_FORM_REJECTED", "code"),
    Row("PARAMETRIC_OUT_OF_RANGE", "code"),
    Row("PARAMETRIC_TARGET_UNSEEN", "code"),
    Row("PATTERN_DEAD_CHANNELS", "code"),
    Row("PATTERN_DUPLICATE_POINTS", "code"),
    Row("PATTERN_INTENSITY_SCALED", "code"),
    Row("PATTERN_MULTISCAN_DEFAULTED", "code"),
    Row("PATTERN_ROWS_DROPPED", "code"),
    Row("PATTERN_SCAN_REVERSED", "code"),
    Row("PATTERN_SIGMA_CONSTANT", "code"),
    Row("PATTERN_UNDERSAMPLED", "code"),
    Row("PATTERN_X_AXIS_ASSUMED", "code"),
    Row("PATTERN_X_AXIS_IMPLAUSIBLE", "code"),
    Row("PAWLEY_OFF_DATA_RIDGED", "code"),
    Row("PAWLEY_OVERLAP_UNRESOLVED", "code"),
    Row("PEAK_ASYMMETRY_UNMODELLED", "code"),
    Row("PEAK_AXIAL_TAIL", "code"),
    Row("PEAK_CONTAMINATION_LINE", "code"),
    Row("PEAK_EXPECTED_FALSE_LINES", "code"),
    Row("PEAK_KALPHA2_ALIAS", "code"),
    Row("PEAK_KALPHA2_RESIDUAL", "code"),
    Row("PEAK_LIST_TOO_SHORT", "code"),
    Row("PEAK_NOT_SEPARABLE", "code"),
    Row("PEAK_POSITION_PRECISION", "code"),
    Row("PEAK_SHOULDER_SEEDED", "code"),
    Row("PEAK_SIGMA_ASSUMED", "code"),
    Row("PEAK_UNRESOLVED_SHOULDER", "code"),
    Row("PEAK_UNRESOLVED_SPLIT", "code"),
    Row("PEAK_WIDTH_CAPPED", "code"),
    Row("PEAK_WIDTH_LAW_MISMATCH", "code"),
    Row("PHASE_UNCONSTRAINED", "code"),
    Row("QPA_ESD_UNAVAILABLE", "code"),
    Row("QPA_FRACTION_RANGE", "code", tier=1, ambiguity=3,
        evidence=("arithmetic: an info record on every width profile whose fit carries an esd, "
                  "with no threshold (B12 3(a), ruled 2026-10-19, replacing "
                  "QPA_FRACTION_UNDETERMINED); states the range and excess the profile "
                  "computed, whose cut is FRACTION_PROFILE_DCHI2's row")),
    Row("QPA_UNAVAILABLE", "code"),
    Row("RAS_ATTENUATOR_PRESENT", "code"),
    Row("READER_OPTION_IGNORED", "code"),
    Row("RECIPE_BACKGROUND_PEAK_DEGENERATE", "code"),
    Row("RECIPE_BACKGROUND_RESEEDED", "code"),
    Row("RECIPE_BOUND_HONOURED", "code"),
    Row("RECIPE_CONVENTION_ASSUMED", "code"),
    Row("RECIPE_DISPERSION_DECLINED", "code"),
    Row("RECIPE_ENGINE_DEFAULT_DECLINED", "code"),
    Row("RECIPE_FIELD_DROPPED", "code"),
    Row("RECIPE_FIT_RANGE_CHANNELS", "code"),
    Row("RECIPE_FLAG_DROPPED", "code"),
    Row("RECIPE_FLAG_TRANSLATED", "code"),
    Row("RECIPE_NOTHING_REFINED", "code"),
    Row("RECIPE_PLAN_STAGED", "code"),
    Row("RECIPE_SCALE_RESEEDED", "code"),
    Row("RECIPE_SCHEMA_UNTESTED", "code"),
    Row("RECIPE_ZERO_WEIGHT_EXCLUDED", "code"),
    Row("RESOLUTION_NOT_POSITIVE", "code"),
    Row("RESOLUTION_UNCONSTRAINED", "code"),
    Row("RESTRAINT_TENSION", "code"),
    Row("RIGID_BODY_MISFIT", "code"),
    Row("RIGID_BODY_UNSUPPORTED", "code"),
    Row("ROUGHNESS_ABSORPTION", "code"),
    Row("ROUGHNESS_OUTSIDE_REGIME", "code"),
    Row("ROUGHNESS_UNCONSTRAINED", "code"),
    Row("SCALE_B_INSEPARABLE", "code"),
    Row("SEQUENTIAL_CANCELLED", "code"),
    Row("SEQUENTIAL_DISCONTINUITY", "code"),
    Row("SEQUENTIAL_MOMENT_HOLD", "code"),
    Row("SEQUENTIAL_MOMENT_ONSET", "code"),
    Row("SEQUENTIAL_PATH_CHECK_INCOMPLETE", "code"),
    Row("SEQUENTIAL_PATH_DEPENDENT", "code"),
    Row("SEQUENTIAL_PERSISTENT_FINDING", "code"),
    Row("SEQUENTIAL_RESEED", "code"),
    Row("SEQUENTIAL_RWP_OUTLIER", "code"),
    Row("SEQUENTIAL_UNRECOVERED", "code"),
    Row("SEQUENTIAL_WIDTH_GROWTH", "code"),
    Row("SERIES_PATTERN_FAILED", "code"),
    Row("SITE_SNAPPED_TO_SPECIAL_POSITION", "code"),
    Row("SIZE_NORMALISED_ACROSS_WAVELENGTHS", "code"),
    Row("SIZE_UNUSUALLY_SMALL", "code"),
    Row("SOLVE_B_TIED_PER_PARENT_SITE", "code", tier="caller", ambiguity=2,
        evidence="opt-in: solve_magnetic(tie_to_parent=True), default False"),
    Row("SPACE_GROUP_SETTING_ASSUMED", "code"),
    Row("SPECIES_FALLBACK_NEUTRAL", "code"),
    Row("STAGE_FREED_NOTHING", "code"),
    Row("STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT", "code"),
    Row("STAGE_MAX_ITER", "code"),
    Row("STAGE_PATH_NOT_FREE", "code"),
    Row("STAGE_PATH_UNKNOWN", "code"),
    Row("STEPHENS_STRAIN_NOT_POSITIVE", "code"),
    Row("STRAIN_UNUSUALLY_LARGE", "code"),
    Row("TEXTURE_NOT_POSITIVE", "code"),
    Row("TOPAS_BLOCK_SKIPPED", "code"),
    Row("TOPAS_CELL_COUPLING_DROPPED", "code"),
    Row("TOPAS_FEATURES_NOT_IMPORTED", "code"),
    Row("TOPAS_FEATURE_REFUSED", "code"),
    Row("TOPAS_FIELD_NOT_WRITTEN", "code"),
    Row("TOPAS_FIRST_RUN_READ", "code"),
    Row("TOPAS_MAGNETIC_GROUP_READ", "code"),
    Row("TOPAS_MAGNETIC_PART_MERGED", "code"),
    Row("TOPAS_MOMENT_CONVENTION", "code"),
    Row("TOPAS_MOMENT_G_HELD", "code"),
    Row("TOPAS_MOMENT_ION_UNCHARGED", "code"),
    Row("TOPAS_ORIGIN_TRANSLATED", "code"),
    Row("TOPAS_PHASE_RESTATED_IN_P1", "code"),
    Row("TOPAS_PHASE_TERM_READ", "code"),
    Row("TOPAS_SPECIES_NORMALISED", "code"),
    Row("TOPAS_SPECIES_WRITTEN_NEUTRAL", "code"),
    Row("WAVELENGTH_CALIBRATION", "code"),
    Row("XRDML_ATTENUATOR_APPLIED", "code"),
    # action: 22
    Row("rietx.schemas.results.StageResult.held", "action", tier=3, ambiguity=1,
        evidence=("WP-1301/1523: free, an absent phase's cell walked 14.9 A from truth over 13 "
                  "sub-onset ramp patterns at unchanged Rwp; silent on IUCr CPD cpd-1c; GSAS-II, "
                  "FullProf and TOPAS hold nothing by default, TOPAS's Remove_Phase is opt-in "
                  "(Tech Ref V9 § 20.19); the collapse restore also appends here, and "
                  "StageResult.collapsed says which (B14)"),
        grounds=("No competent refiner lets a phase the data cannot see refine its cell, and the "
                 "hold touches only what the data cannot determine; on by default, which no "
                 "program does (B1, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.results.StageResult.scale_b_held", "action", tier=1, ambiguity=1,
        evidence=("numerical floor: under 2*sqrt(PINV_RCOND) the covariance's pinv cut cannot see "
                  "scale and B as two directions (WP-1534 derivation); measured cases read 1e-12 or"
                  " 0.19-0.40")),
    Row("rietx.schemas.results.StageResult.width_twins_held", "action", tier=3, ambiguity=1,
        evidence=("physics: a pattern sees each angular term of the widths as one total "
                  "(CompiledModel._width_block): U with gauss_strain in tan^2, X with lor_size in "
                  "1/cos, Y with lor_strain in tan; gauss_size (1/cos^2 = 1 + tan^2) is flat with "
                  "U and W together and holding U alone removes it, so W, the constant width, is "
                  "never held (holding W too moved three CPD acceptance answers; the generality "
                  "judge, WP-2002 9th session); "
                  "refine._width_twin_flats holds the instrument "
                  "terms on the null space of those totals read off C, so one seen phase with its "
                  "specimen width held holds nothing; a free Stephens block is Y's twin by rule "
                  "(flat exactly at its isotropic seed); the test reads no bound "
                  "(tests/test_width_twin_hold.py). Unheld and unfloored, CPD corundum walked y to "
                  "-180 and lor_strain to +180.04 with their sum unchanged, then every residual "
                  "went NaN (WP-2002 8th session). Practice (docs/practice.md § Instrument and "
                  "specimen widths refined together): FullProf's resolution file, BGMN's ray "
                  "tracing and RIETAN-FP's advised protocol fix the instrument by design; GSAS-II "
                  "5.8.4 keeps both free and takes an SVD step that does not move along the flat "
                  "direction, printing a singularity warning (GSASIImath.py:280-289, checked by "
                  "the judge); none holds a twin automatically. Real two-phase family, 11-BM LaB6 "
                  "+ cBN: once two exactly flat directions, now LaB6's widths on their floor and "
                  "cBN lor_strain 0.0354(8), every esd finite; LaB6 16.779(194) wt % against "
                  "16.850 before, TOPAS 17.907-17.950. The costs: the specimen width ends on its 0 "
                  "floor in three of four real fits (brucite, corundum, LaB6 + cBN), so the held "
                  "instrument value binds, Rwp 0.186391 -> 0.186423 on brucite and 0.179951 -> "
                  "0.181008 with a Stephens block; a plan fitting X and Y on the specimen first "
                  "keeps that stage's start-dependent split, 15.68 plain esd on cpd-1a zincite's "
                  "lor_strain between Biso starts (strict xfail in "
                  "tests/test_staged_start_invariance.py). Measured and not adopted: moving the "
                  "hold to a specimen width on its floor recovers the single-phase Rwp exactly "
                  "but on cpd-1a takes Y to -0.18 and zincite's lor_strain to 0.26, still "
                  "start-dependent (WP-2002 9th session). No shipped plan frees a twin pair"),
        grounds=("Stopping the walk has no dissenter; holding the instrument side is what the "
                 "programs that separate the two do by design, and no program does it by default "
                 "for a caller who freed both, so tier 3 (the generality judge, 2026-10-23). "
                 "Approved as option (b) of the width-floor ruling with the cpd-1a cost before the "
                 "maintainer (decision 1(a), 2026-10-23); where the held value was not taken from "
                 "a standard, which side carries the width is the caller's, and the record names "
                 "the pair."),
        approved="2026-10-23"),
    Row("rietx.schemas.results.StageResult.released", "action", tier=3, ambiguity=1,
        evidence=("WP-1301/1523: a held phase reading >= 3 sigma at the answer is released and the "
                  "stage re-solved once; one that fell under it is restored to its stage start and "
                  "held; the ramp's worst cell error fell from 11.96 A (start-only hold) to 0"),
        grounds=("A phase the data now see is one the plan asked to refine, and a cell chased "
                 "into noise is no measurement; kept with the hold (B1, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.results.StageResult.cell_reset", "action", tier=3, ambiguity=1,
        evidence=("WP-1110's trigger: a visible phase sharing its cell with a 2 % trace copy ran "
                  "4.16 -> 3803 A in one stage; fired in none of WP-1523's 104 fits; until "
                  "WP-2002 the cell was pulled to the 15 % window edge, a value no fit produced, "
                  "with esds from the runaway point"),
        grounds=("A refiner whose cell ran away puts it back and fixes it for the stage, through "
                 "the restore, hold and second solve the collapse already takes (B1); ordinary "
                 "fits do not change (B8, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.results.StageResult.collapsed", "action", tier=3, ambiguity=1,
        evidence=("WP-1301/1523: a phase visible at stage start that fell under 3 sigma at the "
                  "answer, or a moment direction gone flat, is restored to its stage start, held "
                  "and the stage re-solved once; on the ramp's sub-onset patterns the CaF2 cell "
                  "walked to 1.73-20.34 A unheld and -6.49 A under the start-only hold, and the "
                  "restore leaves it exactly at its stage-start value "
                  "(tests/test_held_phase.py collapsed_fit); until B14 the restore joined "
                  "StageResult.held unmarked"),
        grounds=("A cell chased into noise is no measurement, so a refiner puts it back where "
                 "the data last constrained it; kept with the hold and the release (B1, ruled "
                 "2026-10-19), the moment direction's with the moment actions (B2, ruled "
                 "2026-10-19), and given its own field by B14's option 3 (ruled 2026-10-20)."),
        approved="2026-10-19"),
    Row("rietx.schemas.results.StageResult.moment_flat_axes", "action", tier=1, ambiguity=1,
        evidence=("physics: Shirane (1959) Acta Cryst. 12, 282: a powder cannot see a cubic "
                  "collinear moment's direction or a uniaxial one's azimuth (docstring); measured "
                  "1e-15 vs 1e0 response")),
    Row("rietx.schemas.results.StageResult.moment_turned", "action", tier=3, ambiguity=1,
        evidence=("issue #599, WP-1327: unturned, psi stopped at 27.84 deg against 10.20 "
                  "(tests/test_magnetic.py:1810-1823), and holding nothing left psi's esd at 448 "
                  "and 20 490 deg on 2 of 16 seeds; synthetic R-3m:R only; GSAS-II, TOPAS and "
                  "FullProf handle no powder-only case (third-round reading)"),
        grounds=("Rare feature: it moves the moment only along a rotation the pattern cannot see, "
                 "checks the pattern unchanged before writing, and a caller has no verb to do it "
                 "by hand (B2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.results.StageResult.blocked_by_hold", "action", tier="caller", ambiguity=1,
        evidence=("opt-in: Refinement.hold(), nothing held by default; the caller's hold outranks a"
                  " plan glob (WP-1435)")),
    Row("rietx.schemas.results.StageResult.seeded", "action", tier=3, ambiguity=1,
        evidence=("the one shipped seed is _ROUGHNESS_STAGE's 0.3, recorded per model. Suortti's "
                  "b: start-invariant from 0.3 and 0 on five lab patterns from three families "
                  "(NIST LaB6, GSAS-II FAP, CPD corundum, fluorite, zincite), every Biso, scale "
                  "and b within 2.7e-3 of the smaller esd (tests/test_seed_invariance.py). "
                  "Pitschke's c: not start-invariant, from 0 CPD zincite lands in the turned-over "
                  "regime (scale x2.1, ROUGHNESS_OUTSIDE_REGIME) and corundum's Biso moves 0.26 "
                  "esd; no program supplies a Pitschke start (FullProf's examples start at "
                  "1.2-1.5; docs/practice.md). Since B14 the field also records "
                  "Stage.strain_seed's Stephens rows, whose start is STRAIN_SEED_PPM's row"),
        grounds=("The seeding action is the stage's, recorded in the field; Suortti's start is "
                 "answer-invariant and Pitschke's is kept at 0.3 because from 0.3 the fit reaches "
                 "the switched-off branch inside the model's valid range, while from 0 the lower "
                 "chi2 is one the model flags as invalid (the sixth round's Q3, ruled (c) "
                 "2026-10-21: one number in the code, the two models recorded apart)."),
        approved="2026-10-21"),
    Row("rietx.schemas.results.StageResult.moment_angle_tests", "action", tier=3, ambiguity=1,
        evidence=("WP-1929: two-site Pnma moduli 0.0015/0.0011 mu_B with the angle columns out, "
                  "0.031/0.159 in, 0.0035-0.47 as ftol moved; LaMnO3 BT-1: an angle 5.2 deg off "
                  "90 with a 3.5 deg linear esd, Delta chi2 0.56 against 3.84, whose esd the "
                  "test removed; neither GSAS-II nor TOPAS has such a test"),
        grounds=("B2 option 2: the test keeps the moment sizes' esds free of the stopping-point "
                 "artefact, and the angle it leaves out reports its likelihood interval "
                 "(RefinedParameter.interval) in place of an esd (ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.results.StageResult.n_constraint_truncations", "action", tier=1, ambiguity=1,
        evidence=("physics: a strain variance and a pole density are non-negative (Stephens 1999; "
                  "WP-1960 D4); the Gamma_G^2 floor's value is tiered on "
                  "caglioti._MIN_GAMMA_G2's row")),
    Row("rietx.schemas.results.StageResult.n_degenerate_cell_probes", "action", tier=1, ambiguity=1,
        evidence=("arithmetic: a cell of zero or negative volume has no metric, so the residual is "
                  "undefined there and the step must be rejected (issue #283)")),
    Row("rietx.schemas.results.StageResult.n_lapack_fallbacks", "action", tier=1, ambiguity=1,
        evidence=("arithmetic: a decomposition the divide-and-conquer LAPACK driver did not "
                  "converge on is repeated with its QR-iteration twin, the same decomposition by "
                  "another route (gesdd/gesvd, syevd/syev, gelsd/gelss; Anderson et al. 1999, "
                  "LAPACK Users' Guide; optimize.lapack); a converging call is numpy's own, bit "
                  "for bit.  On CPD brucite under TRF, macOS Accelerate's gesdd failed 20 of 20 "
                  "on a 7279 x 28 step matrix (condition 7.9e10) that OpenBLAS's gesdd "
                  "decomposed with singular values equal to gesvd's to the last bit; the fit "
                  "lands at Rwp 0.1787 (WP-2002, 2026-10-22).  Practice: TenPy's svd_robust, "
                  "the same retry; MATLAB and Octave call gesvd by default"),
        approved="2026-10-22"),
    Row("rietx.schemas.results.StageResult.ftol", "action", tier=3, ambiguity=1,
        evidence=("behind the closing stage, 1e-6 against every stage at 1e-9 within 0.1 plain "
                  "esd on SRM 660c, FAP, cpd-1a and 11-BM NAC (0.000, 0.000, 0.042, 0.000; "
                  "tests/test_staged_start_invariance.py); fails on cpd-1a with an absent zircon "
                  "declared, 0.185 esd on fluorite a, where at 1e-9 the unseen zircon's cell "
                  "walks to the stage budget (STAGE_MAX_ITER) before the closing stage holds it, "
                  "a strict xfail; 1.00-2.15x fewer evaluations (WP-1113/1123)"),
        grounds=("A schedule rietx chose (WP-1123); kept on four families with its failing case "
                 "stated, where the alternative is the arm that runs out of budget (the sixth "
                 "round's Q2, bar 0.1 plain esd, ruled 2026-10-21)."),
        approved="2026-10-21"),
    Row("rietx.schemas.results.StageResult.window_area_tol", "action", tier=2, ambiguity=1,
        evidence=("the record of the closing stage PlanSpec:closing_window_tol runs (that "
                  "row's evidence: BGMN's closing run by default), written by both stage "
                  "runners on every stage, None on a declared one"),
        grounds=("Records the action rather than taking one: a reader rebuilding the model "
                 "from the result passes it to compile_model (the sixth round's Q1 and Q2, "
                 "ruled 2026-10-21)."),
        approved="2026-10-21"),
    Row("rietx.schemas.sequential.SeriesEntry.rung", "action"),
    Row("rietx.schemas.sequential.SeriesEntry.reseeded", "action"),
    Row("rietx.schemas.sequential.SeriesEntry.rwp_fence", "action"),
    Row("rietx.schemas.sequential.SeriesEntry.rungs_tried", "action"),
    Row("rietx.schemas.sequential.SeriesEntry.rungs_raised", "action"),
    Row("rietx.schemas.results.RefinementResult.absorption", "action", tier="caller", ambiguity=1,
        evidence=("opt-in: Geometry.mu_r/mu_t or capillary_radius_mm/thickness_mm, default None "
                  "(off); choosing flat_plate_transmission applies sec theta; Rouse et al. (1970) "
                  "Acta Cryst. A26, 682 (docstring)")),
    Row("rietx.schemas.results.Statistics.esd_inflation", "action", tier=3, ambiguity=1,
        evidence=("Berar & Lelann (1991) J. Appl. Cryst. 24, 1, § IV (docstring; not in the "
                  "corpus); f 1.13 on uncorrelated residuals, 2.15 on FAP, 8.07 on NAC; GSAS-II "
                  "5.8.4 does not apply it (GSASIIstrMain.py:397, checked); FullProf prints SCOR "
                  "and advises multiplying by it (fp2k strings, checked); TOPAS not checked; the "
                  "textbook esd beside it is owed"),
        grounds=("On serially correlated residuals the textbook esd is too small by an amount the "
                 "step width sets, and f corrects most of it; kept on every esd, with the "
                 "textbook esd reported beside it for comparison with other codes (B4, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    # constant: 612
    Row("rietx.background.auto.AIR_SCATTER_TRIGGER", "constant", tier=3, value=0.3,
        evidence=("v0.2: 0.3 sits between 0.85 (synthetic air scatter) and 1e-4 (flat), "
                  "synthetics only; WP-1130 F7: a planted 900/(2θ) term reads 0.069, and #636: "
                  "a synthetic capillary's rise reads 0.0035, so it misses both; "
                  "AIR_SCATTER_UNDECLARED reports a missed rise after the fit; 6 of 30 real "
                  "patterns score within 0.06 of 0.3; "
                  "WP-2002 2026-10-20: seven real patterns (11-BM NAC, lab FAP, five qarr) "
                  "refitted with 3° or 8° knots and the air term on or off: no near-trigger choice "
                  "moved a cell, scale or Biso past 0.8 esd; only FAP with its air term left "
                  "out (score 0.75) moved scale 2 esd and Lorentzian size and strain 3 esd, "
                  "and AIR_SCATTER_UNDECLARED fired there"),
        grounds=("On the default path, since the skill tells every agent to call "
                 "auto_background (B12's ruling); kept as a pick rather than an abstention "
                 "near the trigger (ruled 2026-10-20) because no near-trigger choice moved a "
                 "refined value past 0.8 esd on the seven patterns measured, and the score and "
                 "its trigger travel beside the pick on BackgroundChoice."),
        approved="2026-10-20"),
    Row("rietx.background.auto.AUTO_BACKGROUND_SEED_PERCENTILE", "constant", tier=3, value=10.0,
        evidence=("WP-1542/#725: the skill's Le Bail rule 5 recipe, the 10th percentile; a "
                  "private CW neutron showcase and three synthetics, no independent reference; "
                  "GSAS-II 5.8.4 starts a new Chebyshev at (1.0, 0, 0) (GSASIIdataGUI.py:2207, "
                  "inventory check)"),
        grounds=("Read under seed=True, which the skill's Le Bail rule 5 passes, so on the "
                 "default path (B12's ruling); the level travels as BackgroundChoice.seed_level "
                 "(B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.auto.HUMP_TRIGGER", "constant", tier=3, value=0.05,
        evidence=("v0.2: chosen on synthetics (tests/test_background_auto.py); WP-1130 F7: "
                  "0.047 with a planted 40-count hump and 0.043 without, so it does not "
                  "separate them; WP-2002 2026-10-20, 30 real patterns: 0.036-0.067 on five "
                  "synchrotron or low-background ones and 0.10-2.3 on all 25 lab ones (corundum "
                  "0.39, fluorite 0.29), so it separates lab from synchrotron data and does not "
                  "detect a hump; "
                  "WP-2002 2026-10-20: seven real patterns (11-BM NAC, lab FAP, five qarr) "
                  "refitted with 3° or 8° knots and the air term on or off: no near-trigger choice "
                  "moved a cell, scale or Biso past 0.8 esd; only FAP with its air term left "
                  "out (score 0.75) moved scale 2 esd and Lorentzian size and strain 3 esd, "
                  "and AIR_SCATTER_UNDECLARED fired there"),
        grounds=("On the default path, since the skill tells every agent to call "
                 "auto_background (B12's ruling); kept as a pick rather than an abstention "
                 "near the trigger (ruled 2026-10-20) because no near-trigger choice moved a "
                 "refined value past 0.8 esd on the seven patterns measured, and the score and "
                 "its trigger travel beside the pick on BackgroundChoice."),
        approved="2026-10-20"),
    Row("rietx.background.auto._KNOT_STEP_HUMPY_DEG", "constant", tier=3, value=3.0,
        evidence=("WP-1454: 3° knots on IUCr CPD sample 2 (qarr) held Rwp and Biso flat from λ "
                  "0.1 to 100; a v0.2 choice; no failure stated; "
                  "WP-2002 2026-10-20: seven real patterns (11-BM NAC, lab FAP, five qarr) "
                  "refitted with 3° or 8° knots and the air term on or off: no near-trigger choice "
                  "moved a cell, scale or Biso past 0.8 esd; only FAP with its air term left "
                  "out (score 0.75) moved scale 2 esd and Lorentzian size and strain 3 esd, "
                  "and AIR_SCATTER_UNDECLARED fired there"),
        grounds=("On the default path, since the skill tells every agent to call "
                 "auto_background (B12's ruling); kept as a pick rather than an abstention "
                 "near the trigger (ruled 2026-10-20) because no near-trigger choice moved a "
                 "refined value past 0.8 esd on the seven patterns measured, and the score and "
                 "its trigger travel beside the pick on BackgroundChoice."),
        approved="2026-10-20"),
    Row("rietx.background.auto._KNOT_STEP_SMOOTH_DEG", "constant", tier=3, value=8.0,
        evidence=("v0.2: 8° knots measured R² 0.01-0.03 against broad peaks (v0.2.md:71); "
                  "WP-1454: flat in λ on 11-BM NAC and IUCr CPD sample 2; no failure stated; "
                  "WP-2002 2026-10-20: seven real patterns (11-BM NAC, lab FAP, five qarr) "
                  "refitted with 3° or 8° knots and the air term on or off: no near-trigger choice "
                  "moved a cell, scale or Biso past 0.8 esd; only FAP with its air term left "
                  "out (score 0.75) moved scale 2 esd and Lorentzian size and strain 3 esd, "
                  "and AIR_SCATTER_UNDECLARED fired there"),
        grounds=("On the default path, since the skill tells every agent to call "
                 "auto_background (B12's ruling); kept as a pick rather than an abstention "
                 "near the trigger (ruled 2026-10-20) because no near-trigger choice moved a "
                 "refined value past 0.8 esd on the seven patterns measured, and the score and "
                 "its trigger travel beside the pick on BackgroundChoice."),
        approved="2026-10-20"),
    Row("rietx.background.auto._MIN_FIT_CHANNELS", "constant", tier=1, value=10,
        evidence=("numerical floor: mirrors compile_model's refusal of a fit on under 10 channels "
                  "(model/forward.py:3661); decides only whether the verb raises")),
    Row("rietx.background.diagnostics.AIR_GAIN_CHEBYSHEV_TERMS", "constant", tier=3, value=4,
        evidence=("v0.2's nested-model test, a cubic and then the cubic plus a 1/(2theta) "
                  "column; WP-1130 F7: a cubic already absorbs 1/x over 60 deg, so a planted "
                  "900/(2theta) term reads 0.069 against AIR_SCATTER_TRIGGER's 0.3; an inline "
                  "literal in diagnose until the B14 lift"),
        grounds=("The air-scatter score's own parameter, behind AIR_SCATTER_TRIGGER's pick, which "
                 "is on the default path (B12's ruling) and travels with its score on "
                 "BackgroundChoice.air_scatter_gain (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.diagnostics.COVERAGE_INFLATION_THRESHOLD", "constant", value=1.5),
    Row("rietx.background.diagnostics.COVERAGE_SMOOTH_DEG", "constant", value=1.0),
    Row("rietx.background.diagnostics.CUTOFF_FRACTION", "constant", value=0.25),
    Row("rietx.background.diagnostics.CUTOFF_INTERIOR_FRACTION", "constant", value=0.7),
    Row("rietx.background.diagnostics.CUTOFF_MIN_DEG", "constant", value=1.0),
    Row("rietx.background.diagnostics.CUTOFF_ONSET_FRACTION", "constant", value=0.9),
    Row("rietx.background.diagnostics.CUTOFF_PLATEAU_DEG", "constant", value=2.0),
    Row("rietx.background.diagnostics.CUTOFF_SMOOTH_DEG", "constant", value=0.5),
    Row("rietx.background.diagnostics.DEAD_LEVEL_FRACTION", "constant", value=0.1),
    Row("rietx.background.diagnostics.DEAD_LEVEL_WINDOW_DEG", "constant", value=3.0),
    Row("rietx.background.diagnostics.DEAD_WEIGHT_RATIO_MIN", "constant", value=100.0),
    Row("rietx.background.diagnostics.ENVELOPE_QUANTILE", "constant", tier=3, value=10.0,
        evidence=("v0.2: low enough to land under the peaks; the 1.28 sigma downward bias at "
                  "10 % (norm.ppf(0.10) = -1.2816, checked) is removed by "
                  "indexing.peaks._debiased_envelope; read by every diagnose() score and on the "
                  "indexing default path; background_envelope's signature default until the "
                  "B14 lift"),
        grounds=("Read on the default path through diagnose(), which auto_background calls, "
                 "and through the indexing peak picker; kept at its v0.2 value (B12, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.diagnostics.ENVELOPE_WINDOW_DEG", "constant", tier=3, value=3.0,
        evidence=("v0.2: chosen so the low quantile lands on background channels; WP-1018 "
                  "reused it for peak picking; WP-1028 repaired its edges on 7 round-robin "
                  "patterns; also envelope_measured_span's window, and DEAD_LEVEL_WINDOW_DEG is "
                  "it by reference; background_envelope's signature default until the B14 lift"),
        grounds=("Read on the default path through diagnose(), which auto_background calls, "
                 "and through the indexing peak picker; kept at its v0.2 value (B12, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.diagnostics.GHOST_ESD_MAX_DEG", "constant", value=0.15),
    Row("rietx.background.diagnostics.GHOST_MATCH_K", "constant", value=3.0),
    Row("rietx.background.diagnostics.GHOST_MIN_PARENTS", "constant", value=5),
    Row("rietx.background.diagnostics.GHOST_N_PARENTS", "constant", value=8),
    Row("rietx.background.diagnostics.GHOST_RATIO_RANGE", "constant", value=(0.005, 0.25)),
    Row("rietx.background.diagnostics.GHOST_RATIO_TOL", "constant", value=2.0),
    Row("rietx.background.diagnostics.GHOST_TOL_DEG", "constant", value=0.15),
    Row("rietx.background.diagnostics.SAMPLING_HEIGHT_FRACTION", "constant", value=0.03),
    Row("rietx.background.diagnostics.SAMPLING_PROMINENCE_SIGMA", "constant", value=5.0),
    Row("rietx.background.diagnostics.STEPS_PER_FWHM_MAX", "constant", tier=2, value=10.0,
        evidence=("McCusker, Von Dreele, Cox, Louer & Scardi (1999) J. Appl. Cryst. 32, 36 section "
                  "2 (docstring; not in the local corpus)")),
    Row("rietx.background.diagnostics.STEPS_PER_FWHM_MIN", "constant", tier=2, value=5.0,
        evidence=("McCusker, Von Dreele, Cox, Louer & Scardi (1999) J. Appl. Cryst. 32, 36 section "
                  "2 (docstring; not in the local corpus)")),
    Row("rietx.background.diagnostics._ANODE_MATCH_TOL", "constant", value=0.01),
    Row("rietx.background.diagnostics._DEAD_INTERVAL_DECIMALS", "constant", value=3),
    Row("rietx.background.diagnostics._DEAD_REPAIR_PASSES", "constant", value=6),
    Row("rietx.background.diagnostics._W_LA1", "constant", tier=1, value=1.47638,
        evidence=("physics: tabulated emission wavelength, Bearden (1967) Rev. Mod. Phys. 39, 78 "
                  "(docstring)")),
    Row("rietx.background.models.FIXED_RANGE_SLACK_STEPS", "constant", tier=1, value=1.0,
        evidence=("arithmetic: one curve step is the grid-alignment bound between two scans of one "
                  "nominal range; beyond it the end value would be invented counts")),
    Row("rietx.background.models.FOUR_LN2_NEG", "constant", tier=1, value=-2.772588722239781,
        evidence="arithmetic: exp[-4 ln2 (x/Gamma)^2] has half height at x = Gamma/2"),
    Row("rietx.background.select.ARPLS_DW_FLOOR", "constant", tier=3, value=1.2,
        evidence=("v0.2: the largest lambda whose masked residuals look white; no source for "
                  "1.2, no measurement recorded; feeds only PatternDiagnostics.baseline_lambda, "
                  "which nothing in src reads; select_arpls_lambda's signature default until "
                  "the B14 lift"),
        grounds=("Reached through diagnose(), which auto_background calls on the default path; "
                 "its answer is reported on PatternDiagnostics.baseline_lambda and read by "
                 "nothing (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.select.CHEBYSHEV_MAX_ORDER", "constant", tier=3, value=16,
        evidence=("WP-1931/#833: 16 returned as the choice on 11-BM Si640c, LaB6 and FAP.XRA "
                  "while BIC was still falling; harmless there (bias <= 0.7 % of a background "
                  "<= 0.4 % of the peak); reported as BACKGROUND_ORDER_AT_CAP (info); "
                  "select_chebyshev_order's signature default until the B14 lift"),
        grounds=("Caps auto_background(kind='chebyshev')'s order scan, whose whole scan travels "
                 "on BackgroundChoice.selection, and a scan ending at the cap says so (B12, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.select.DW_STOP", "constant", tier=3, value=1.8,
        evidence=("the statistic is tier 2 (GSAS-II 5.8.4 GSASIIstrMath.py:4995 reports the same "
                  "d, checked; Durbin & Watson 1950, Hill & Flack 1987, docstring); the 1.8 "
                  "threshold has no source; select_chebyshev_order's signature default until "
                  "the B14 lift"),
        grounds=("Stops auto_background(kind='chebyshev')'s order scan, which travels with "
                 "stopped_by_whiteness on BackgroundChoice.selection (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.select.PEAK_MASK_BASELINE_LAMBDA", "constant", tier=3, value=10000000.0,
        evidence=("no source; arpls's docstring calls 1e6-1e9 typical for ~1e4 points; the "
                  "signature default of peak_mask and select_chebyshev_order until the B14 "
                  "lift; arpls's own lam default and viz.compare's literal are the same 1e7 "
                  "and are not tied to it"),
        grounds=("Sets which channels the Chebyshev order scan scores under "
                 "auto_background(kind='chebyshev') (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.select.PEAK_MASK_SIGMA", "constant", tier=3, value=3.0,
        evidence=("no source for 3 sigma; per Schwarz 1978 the masked BIC is tier 2 as a "
                  "statistic; inline in peak_mask until the B14 lift; diagnose's peak_fraction "
                  "census over the rolling envelope and estimators.auto_lambda's 3 sigma "
                  "overshoot test (caller) are other rules and keep their literals"),
        grounds=("Masks the channels the Chebyshev order scan and the arPLS lambda scan score, "
                 "both reached from auto_background (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.crystallography.atomic_volume.TABLE_TEMPERATURE", "constant", value=298.0),
    Row("rietx.crystallography.atomic_volume.THERMAL_EXPANSION", "constant", value=9.5e-05),
    Row("rietx.crystallography.atomic_volume.THERMAL_EXPANSION_ESD", "constant", value=3e-06),
    Row("rietx.crystallography.atomic_volume.VOLUME_RATIO_BOUNDS", "constant", value=(0.8, 1.25)),
    Row("rietx.crystallography.atomic_volume.VOLUME_SCATTER", "constant", value=0.04),
    Row("rietx.crystallography.attenuation._HC_EV_ANGSTROM", "constant", value=12398.4198),
    Row("rietx.crystallography.attenuation._NA_BARN", "constant", value=0.602214076),
    Row("rietx.crystallography.cif.CIF_ANGLE_CORRECT_MAX_DEG", "constant", value=0.1),
    Row("rietx.crystallography.cif.CIF_STATED_MULTIPLICITY_SNAP_TOL", "constant", value=0.001),
    Row("rietx.crystallography.cif.DUPLICATE_U_TOLERANCE", "constant", value=0.0002),
    Row("rietx.crystallography.cif.OCCUPANCY_TOLERANCE", "constant", value=0.01),
    Row("rietx.crystallography.cif.TWIN_DISTANCE", "constant", value=0.02),
    Row("rietx.crystallography.dispersion.LINE_DISPERSION_TOL", "constant", value=0.01),
    Row("rietx.crystallography.dispersion.NEAR_EDGE_EV", "constant", value=50.0),
    Row("rietx.crystallography.fragments.COLLINEAR_TOL", "constant", value=1e-06),
    Row("rietx.crystallography.fragments.INERTIA_RANK_TOL", "constant", value=1e-06),
    Row("rietx.crystallography.fragments._COINCIDENT_A2", "constant", value=1e-20),
    Row("rietx.crystallography.magcif.MOMENT_FORM_AGREEMENT_MU_B", "constant", value=0.02),
    Row("rietx.crystallography.magnetic.isotropy.CROSS_IRREP_DRAWS", "constant", value=12),
    Row("rietx.crystallography.magnetic.isotropy.DEFAULT_CELL_SCALE", "constant", value=5.0),
    Row("rietx.crystallography.magnetic.isotropy.DUAL_AFTER_RESTART", "constant", value=1),
    Row("rietx.crystallography.magnetic.isotropy.FARKAS_FLOOR", "constant", value=1e-12),
    Row("rietx.crystallography.magnetic.isotropy.FARKAS_QUOTE", "constant", value=1e-10),
    Row("rietx.crystallography.magnetic.isotropy.INTENSITY_RTOL", "constant", value=1e-09),
    Row("rietx.crystallography.magnetic.isotropy.ISOMETRY_RESIDUAL", "constant", value=1e-12),
    Row("rietx.crystallography.magnetic.isotropy.KERNEL_AMPLITUDE_RATIO", "constant", value=1.0),
    Row("rietx.crystallography.magnetic.isotropy.TRANSFER_FLOAT_STACK", "constant", value=1e-08),
    Row("rietx.crystallography.magnetic.isotropy.WITHIN_IRREP_DRAWS", "constant", value=3),
    Row("rietx.crystallography.magnetic.isotropy._CLOSURE_LIMIT", "constant", value=4096),
    Row("rietx.crystallography.magnetic.isotropy._PROBE_DRAWS", "constant", tier=1, value=3,
        evidence=("probability: a false DISTORTION_CHILD_LARGER needs every draw to keep an accidental "
                  "operation; one draw did in 3 of 320 calls at the shipped 50x (perovskite, Gamma/X/M/R, "
                  "seeds 0-79), and a genuine one keeps it on every draw; the first draw is the one an "
                  "answered call uses; tests/test_distortion_candidates.py::test_the_probe_seed_decides_no_child "
                  "bounds it at 3 (seeds 142 and 194 at R, 41 at M answer as seed 1419), "
                  "tests/test_distortion_candidates.py::test_one_unlucky_draw_does_not_refuse_a_child "
                  "its positive arm (the same seeds refuse at 1)")),
    Row("rietx.crystallography.magnetic.isotropy._PROBE_RMS", "constant", tier=1, value=0.05,
        evidence=("numerical scale, 50x _PROBE_SYMPREC: the operation check fixes an answered child's group, and "
                  "tests/test_distortion_candidates.py::test_the_probe_tolerance_and_scale_decide_no_child bounds the raise path (0.01 and "
                  "0.2 A: the same children at Gamma, R, X and M, no false DISTORTION_CHILD_LARGER)")),
    Row("rietx.crystallography.magnetic.isotropy._PROBE_SEED", "constant", tier="invariant", value=1419,
        evidence=("answer-invariant: tests/test_distortion_candidates.py::test_the_probe_seed_decides_no_child (seeds 1 and 2026, two whose "
                  "first draw keeps an accidental operation at R, and one whose first draw does at M) asserts the same child "
                  "groups, (P, p) and child atoms at Gamma, R, X and M")),
    Row("rietx.crystallography.magnetic.isotropy._PROBE_SYMPREC", "constant", tier=1, value=0.001,
        evidence=("numerical tolerance: the operation check fixes an answered child's group, and "
                  "tests/test_distortion_candidates.py::test_the_probe_tolerance_and_scale_decide_no_child bounds the raise path (1e-6: the "
                  "same children at Gamma, R, X and M, no false DISTORTION_CHILD_LARGER); "
                  "tests/test_distortion_candidates.py::test_a_tolerance_at_the_probe_scale_finds_extra_operations its positive arm")),
    Row("rietx.crystallography.magnetic.isotropy._SPAN_GAP", "constant", value=(1e-12, 1e-06)),
    Row("rietx.crystallography.magnetic.moments.MOMENT_DIRECTION_SUPPORT", "constant", value=1e-06),
    Row("rietx.crystallography.magnetic.moments.SEED_TILT", "constant", value=0.02),
    Row("rietx.crystallography.magnetic.operators.N_MAGNETIC_SPACE_GROUPS", "constant", value=1651),
    Row("rietx.crystallography.magnetic.operators._MAX_CODE", "constant", value=4611686018427387904),
    Row("rietx.crystallography.magnetic.p1._WRAP_TOL", "constant", value=1e-12),
    Row("rietx.crystallography.magnetic.scattering.INVARIANCE_MOMENT_TOL", "constant", value=0.001),
    Row("rietx.crystallography.magnetic.scattering.INVARIANCE_POS_TOL", "constant", value=0.001),
    Row("rietx.crystallography.magnetic.scattering.METRIC_TOL", "constant", value=0.001),
    Row("rietx.crystallography.magnetic.scattering.P_MAGNETIC_FM", "constant", value=2.695),
    Row("rietx.crystallography.magnetic.supercell.CHILD_SITE_TOL", "constant", value=0.0001),
    Row("rietx.crystallography.neutron.NEUTRON_LAMBDA_EV_ANGSTROM", "constant", value=0.286014),
    Row("rietx.crystallography.neutron.SIGMA_ABS_REFERENCE_WAVELENGTH", "constant", value=1.798),
    Row("rietx.crystallography.representation.distortion._POSITION_TOL", "constant", value=1e-06),
    Row("rietx.crystallography.representation.distortion._PROBE_AMPLITUDE", "constant", value=0.05),
    Row("rietx.crystallography.representation.distortion._PROBE_SYMPREC", "constant", value=0.001),
    Row("rietx.crystallography.representation.distortion._RANK_TOL", "constant", value=1e-08),
    Row("rietx.crystallography.representation.irreps.IRREP_ATOL", "constant", value=1e-08),
    Row("rietx.crystallography.representation.irreps.K_FLOAT_TOL", "constant", value=1e-09),
    Row("rietx.crystallography.representation.irreps.K_MAX_DENOMINATOR", "constant", value=64),
    Row("rietx.crystallography.representation.irreps._H", "constant", value=0.5),
    Row("rietx.crystallography.representation.irreps._SEEDS", "constant", value=(0, 1, 2, 3, 4, 5, 6, 7)),
    Row("rietx.crystallography.representation.irreps._T", "constant", value=0.3333333333333333),
    Row("rietx.crystallography.representation.irreps._TT", "constant", value=0.6666666666666666),
    Row("rietx.crystallography.representation.irreps._ZERO", "constant", value=0.0),
    Row("rietx.crystallography.representation.modes.MODE_ATOL", "constant", value=1e-09),
    Row("rietx.crystallography.representation.modes.POSITION_ATOL", "constant", value=1e-06),
    Row("rietx.crystallography.representation.order_parameter.ISOTROPY_ATOL", "constant", value=1e-08),
    Row("rietx.crystallography.riding.RIDING_MIN_SEPARATION", "constant", value=1e-06),
    Row("rietx.crystallography.rotation.SERIES_THRESHOLD", "constant", value=0.25),
    Row("rietx.crystallography.rotation.UNIT_TOLERANCE", "constant", value=1e-09),
    Row("rietx.crystallography.rotation._A_SERIES", "constant", value=(1.0, -0.16666666666666666, 0.008333333333333333, -0.0001984126984126984, 2.7557319223985893e-06, -2.505210838544172e-08)),
    Row("rietx.crystallography.rotation._B_SERIES", "constant", value=(0.5, -0.041666666666666664, 0.001388888888888889, -2.48015873015873e-05, 2.755731922398589e-07, -2.08767569878681e-09)),
    Row("rietx.crystallography.rotation._C_SERIES", "constant", value=(0.16666666666666666, -0.008333333333333333, 0.0001984126984126984, -2.7557319223985893e-06, 2.505210838544172e-08, -1.6059043836821613e-10)),
    Row("rietx.crystallography.rotation._LOG_SERIES_NORM", "constant", value=1e-08),
    Row("rietx.crystallography.satellites._ORDERS", "constant", value=(1, -1)),
    Row("rietx.crystallography.site_classes.GRID", "constant", tier=1,
        evidence="Arithmetic: every translation of a gemmi space-group operation is a "
                 "multiple of 1/Op.DEN = 1/24, so the affine stabilisers are exact on the "
                 "1/24 grid, and an off-grid translation is refused by name "
                 "(SITE_CLASSES_GRID). Special positions can still fall off it (-x+1/24 "
                 "fixes x = 1/48; a 3-fold -y+t,x-y,z fixes (2t/3,t/3)), so an operator "
                 "list is refused by the same name when (a) an operation that has fixed "
                 "points, decided exactly over the integers, fixes none on the 1/24 grid "
                 "(test_an_operator_list_with_a_special_position_off_the_grid_is_refused, "
                 "test_a_three_fold_axis_off_the_grid_is_refused_whatever_the_translation), "
                 "or (b) a 1/48 scan finds a stabiliser the 1/24 grid missed. (a) is exact per "
                 "operation; (b) is a grid, kept for a point only several operations share. "
                 "Completeness is checked on all 564 gemmi settings "
                 "against spglib's Wyckoff letters (test_every_setting_matches_spglib).",
        value=24),
    Row("rietx.crystallography.site_classes.MAX_SITE_ASSIGNMENTS", "constant", tier=3,
        evidence="refuses with the exact count and never truncates "
                 "(SITE_ASSIGNMENTS_EXCEED_CAP); max_assignments= overrides; largest case "
                 "seen 4 000 on our own solve kits",
        grounds="The cap is rietx's own choice: five times the largest case seen on "
                "one family. A correct large cell can exceed it (a 315-atom one-species "
                "cell in R -3 m does); the refusal carries the exact count, nothing is "
                "truncated, and the caller who wants the list passes max_assignments=.",
        approved="2026-10-21",
        value=20000),
    Row("rietx.crystallography.site_classes._CACHE_SIZE", "constant", tier="invariant",
        evidence="The cache only skips a rederivation of a group's classes; "
                 "test_the_scan_chunk_and_the_cache_size_do_not_change_the_classes holds a "
                 "one-entry cache to the same classes, to the bit.",
        value=64),
    Row("rietx.crystallography.site_classes._CHUNK", "constant", tier="invariant",
        evidence="A memory bound that only partitions the grid scan; "
                 "test_the_scan_chunk_and_the_cache_size_do_not_change_the_classes holds a "
                 "7-point chunk to the same classes, to the bit, and fails when the scan "
                 "stops after one chunk.",
        value=1728),
    Row("rietx.crystallography.spherical_harmonics._TOL", "constant", value=1e-09),
    Row("rietx.crystallography.stephens._DEG_PER_RAD", "constant", value=57.29577951308232),
    Row("rietx.crystallography.superspace.generation.N_BRAVAIS_CLASSES_D1", "constant", value=24),
    Row("rietx.crystallography.superspace.generation.N_SUPERSPACE_GROUPS_D1", "constant", value=775),
    Row("rietx.crystallography.superspace.generation._F0", "constant", value=0.0),
    Row("rietx.crystallography.superspace.generation._GRID", "constant", value=24),
    Row("rietx.crystallography.superspace.generation._QR_COMPONENTS", "constant", value=(0.0, 0.5, 1.0, 0.3333333333333333, 0.6666666666666666)),
    Row("rietx.crystallography.superspace.operators._ZERO3", "constant", value=(0.0, 0.0, 0.0)),
    Row("rietx.crystallography.symmetry.MAX_HKL_GRID_POINTS", "constant", value=30000000),
    Row("rietx.crystallography.symmetry.SITE_TOL", "constant", value=0.0001),
    Row("rietx.crystallography.symmetry.SYMMETRY_ANGLE_TOL_DEG", "constant", value=0.001),
    Row("rietx.crystallography.symmetry._COINCIDENCE_TOL", "constant", value=1e-09),
    Row("rietx.crystallography.symmetry._GAMMA_HEX", "constant", value=120.0),
    Row("rietx.crystallography.symmetry._ORBIT_CHUNK_ELEMENTS", "constant", value=24000000),
    Row("rietx.crystallography.symmetry._SITE_TOL_SLACK", "constant", value=1e-09),
    Row("rietx.crystallography.symmetry._SNAP_MESSAGE_SITES", "constant", value=4),
    Row("rietx.crystallography.symmetry._SNAP_NOISE", "constant", value=1e-12),
    Row("rietx.crystallography.symmetry._TRANSLATION_DEN", "constant", value=12),
    Row("rietx.gui.imports.MAX_UPLOAD_BYTES", "constant", value=67108864),
    Row("rietx.gui.imports.PREVIEW_POINTS", "constant", value=900),
    Row("rietx.gui.imports.WAVELENGTH_RTOL", "constant", value=0.0005),
    Row("rietx.gui.symmetry.LETTER_CACHE", "constant", value=64),
    Row("rietx.gui.symmetry.ORBIT_COLLISION_TOL", "constant", value=0.001),
    Row("rietx.gui.symmetry.POSITION_TOL", "constant", value=1e-06),
    Row("rietx.indexing.ambiguity.AMBIGUITY_DISCREPANCY_SLACK", "constant", value=1.5),
    Row("rietx.indexing.ambiguity.AMBIGUITY_EXTEND_FACTOR", "constant", value=1.5),
    Row("rietx.indexing.ambiguity.MAX_AMBIGUITY_INDEX", "constant", value=4),
    Row("rietx.indexing.ambiguity.MAX_DISCRIMINATING", "constant", value=6),
    Row("rietx.indexing.ambiguity.SUPERCELL_CHANCE_ALPHA", "constant", value=0.01),
    Row("rietx.indexing.ambiguity.UNCANCELLABLE_METRIC_RTOL", "constant", value=0.052335956242943835),
    Row("rietx.indexing.ambiguity._DERIVATIVE_VOLUME_RTOL", "constant", value=0.01),
    Row("rietx.indexing.consensus.CONSENSUS_CHECK_TOP", "constant", value=3),
    Row("rietx.indexing.diagnostics.BRAGG_BRENTANO_CELL_PPM", "constant", value=85.0),
    Row("rietx.indexing.diagnostics.WIDTH_MISMATCH_RATIO", "constant", value=3.0),
    Row("rietx.indexing.diagnostics.Z_INTEGER_TOLERANCE", "constant", value=0.08),
    Row("rietx.indexing.dichotomy.ACCEPT_SPACING_FRAC", "constant", value=0.25),
    Row("rietx.indexing.dichotomy.ANGLE_STEP_DEG", "constant", value=5.0),
    Row("rietx.indexing.dichotomy.ANNEAL_FACTOR", "constant", value=4.0),
    Row("rietx.indexing.dichotomy.AXIS_STEP", "constant", value=0.4),
    Row("rietx.indexing.dichotomy.DEDUP_EVERY", "constant", value=2000),
    Row("rietx.indexing.dichotomy.MAX_ANGLE_COSINE", "constant", value=0.8660254037844387),
    Row("rietx.indexing.dichotomy.MAX_ASSIGN_PASSES", "constant", value=4),
    Row("rietx.indexing.dichotomy.MAX_DEPTH", "constant", value=60),
    Row("rietx.indexing.dichotomy.MAX_GRID_CELLS", "constant", value=400000),
    Row("rietx.indexing.dichotomy.MAX_TRIAL_HKL", "constant", value=200000),
    Row("rietx.indexing.dichotomy._SAME_BOX_RTOL", "constant", value=0.001),
    Row("rietx.indexing.engines.ANCHOR_LINES", "constant", value=5),
    Row("rietx.indexing.engines.CEILING_GRANULARITY_SECONDS", "constant", value=10.0),
    Row("rietx.indexing.engines.DEDUP_STACK_FIRST", "constant", value=16),
    Row("rietx.indexing.engines.DEDUP_VOLUME_RTOL", "constant", value=0.01),
    Row("rietx.indexing.engines.DEFAULT_BUDGET_SECONDS", "constant", value=30.0),
    Row("rietx.indexing.engines.DEFAULT_MAX_CANDIDATES", "constant", value=12),
    Row("rietx.indexing.engines.DEFAULT_MAX_D_AXIS", "constant", value=25.0),
    Row("rietx.indexing.engines.DEFAULT_MIN_D_AXIS", "constant", value=2.0),
    Row("rietx.indexing.engines.DEFAULT_MIN_VOLUME", "constant", value=15.0),
    Row("rietx.indexing.engines.DEFAULT_N_UNINDEXED", "constant", value=2),
    Row("rietx.indexing.engines.DEFAULT_SEARCH_LINES", "constant", value=20),
    Row("rietx.indexing.engines.DEFAULT_UNKNOWN_SHIFT_DEG", "constant", value=0.05),
    Row("rietx.indexing.engines.DEFAULT_VOLUME_CEILING", "constant", value=8000.0),
    Row("rietx.indexing.engines.DRIVEN_MIN_LINES", "constant", tier=1,
        evidence="Arithmetic: the triclinic reciprocal metric Q(hkl) has six independent "
                 "components, so fewer than six driven lines cannot determine every "
                 "lattice a search may be asked for; a floor below which flagged lines are "
                 "taken back, not a tuned optimum.",
        value=6),
    Row("rietx.indexing.engines.ENGINE_POOL_MULTIPLE", "constant", value=5),
    Row("rietx.indexing.engines.INLIER_DOF_MARGIN", "constant", value=4),
    Row("rietx.indexing.engines.INLIER_FRACTION", "constant", value=0.6),
    Row("rietx.indexing.engines.MAX_PREDICTED_REFLECTIONS", "constant", value=2000000),
    Row("rietx.indexing.engines.MEASURED_TYPICAL_SECONDS", "constant", value=(4.0, 440.0)),
    Row("rietx.indexing.engines.MEASURED_VALIDATION_SECONDS", "constant", value=(0.6, 44.0)),
    Row("rietx.indexing.engines.MIN_AGREEMENT", "constant", value=2),
    Row("rietx.indexing.engines.PROVISIONAL_STREAM_TOP", "constant", value=3),
    Row("rietx.indexing.engines.QUICK_TOTAL_BUDGET_SECONDS", "constant", value=120.0),
    Row("rietx.indexing.engines.SAME_SOLUTION_RTOL", "constant", value=0.001),
    Row("rietx.indexing.engines.SEARCH_POOL_MULTIPLE", "constant", value=2),
    Row("rietx.indexing.engines.VALIDATION_RESERVE_FRACTION", "constant", value=0.08),
    Row("rietx.indexing.engines.WIDTH_ALLOWANCE_FWHM", "constant", value=1.0),
    Row("rietx.indexing.engines.WIDTH_ALLOWANCE_QUANTILE", "constant", value=0.25),
    Row("rietx.indexing.engines._INDEX_MARGIN", "constant", value=1e-06),
    Row("rietx.indexing.engines._INDEX_MAX_CONDITION", "constant", value=1000000.0),
    Row("rietx.indexing.engines._INDEX_MAX_SHARE", "constant", value=0.5),
    Row("rietx.indexing.engines._INDEX_MIN_DEFECT", "constant", value=1e-06),
    Row("rietx.indexing.engines._INDEX_MIN_ROWS", "constant", value=15000),
    Row("rietx.indexing.extinction.DECISIVE_DELTA_BIC", "constant", value=10.0),
    Row("rietx.indexing.extinction._MODULI", "constant", value=(2, 3, 4, 6)),
    Row("rietx.indexing.extinction.N_A_CM3_PER_A3", "constant", tier=1,
        evidence="Physics: Avogadro's number, exact in the SI since 2019 (CODATA 2018, "
                 "6.02214076e23 /mol), times 1e-24 cm3 per A3, so Z = rho*V*N_A/M with rho "
                 "in g/cm3, V in A3 and M in g/mol (WP-2033).  The same value qpa.ZMV.density "
                 "uses inline.",
        value=0.602214076),
    Row("rietx.indexing.fom.FOM_N", "constant", value=20),
    Row("rietx.indexing.fom.LINE_COINCIDENCE_RTOL", "constant", value=1e-09),
    Row("rietx.indexing.fom.MATCH_SIGMA", "constant", value=3.0),
    Row("rietx.indexing.fom._AGGREGATE_FLOOR_RTOL", "constant", value=1e-06),
    Row("rietx.indexing.fom._BOUNDARY_RTOL", "constant", value=1e-09),
    Row("rietx.indexing.peakfit._H_POS", "constant", value=1e-05),
    Row("rietx.indexing.peakfit._H_WIDTH", "constant", value=1e-07),
    Row("rietx.indexing.peakfit._SEED_GAUSS_FRACTION", "constant", value=0.8),
    Row("rietx.indexing.peakfit._SPARROW_DIP_MIN", "constant", value=1e-06),
    Row("rietx.indexing.peaks.MIN_GROUP_POINTS", "constant", value=8),
    Row("rietx.indexing.peaks.TRIAL_GAP_STEPS", "constant", value=3.0),
    Row("rietx.indexing.peaks._LN2_8", "constant", value=5.545177444479562),
    Row("rietx.indexing.priors.CLASSIFY_ATOL_DEG", "constant", value=0.25),
    Row("rietx.indexing.priors.CLASSIFY_RTOL", "constant", value=0.002),
    Row("rietx.indexing.priors.MAX_PRIOR_INDEX", "constant", value=40),
    Row("rietx.indexing.priors.MAX_PRIOR_PASSES", "constant", value=4),
    Row("rietx.indexing.priors.PRIOR_DRIFT_MAX", "constant", value=0.1),
    Row("rietx.indexing.qspace._VOIGT_OF_AF", "constant", value=(0, 1, 2, 5, 4, 3)),
    Row("rietx.indexing.quality.VOLUME_ENVELOPE_SLACK", "constant", value=1.5),
    Row("rietx.indexing.reduce.BRAVAIS_OBLIQUITIES", "constant", value=(0.5, 1.0, 2.0, 3.0)),
    Row("rietx.indexing.reduce.BRAVAIS_SYMPREC_SIGMAS", "constant", value=(1.0, 3.0, 10.0)),
    Row("rietx.indexing.reduce.CELL_EQUALITY_CHI2", "constant", value=16.8119),
    Row("rietx.indexing.reduce.CELL_EQUALITY_RELATIVE", "constant", value=0.005),
    Row("rietx.indexing.reduce.CELL_PINV_RCOND", "constant", value=1e-15),
    Row("rietx.indexing.reduce.NIGGLI_EPS_RELATIVE", "constant", value=1e-05),
    Row("rietx.indexing.reduce.SELLING_GATE_RELATIVE", "constant", value=0.05),
    Row("rietx.indexing.reduce.SELLING_GATE_SIGMAS", "constant", value=5.125289625962615),
    Row("rietx.indexing.reduce._SELLING_DEPTH", "constant", value=(1, 2)),
    Row("rietx.indexing.reduce._SELLING_STEPS", "constant", value=1000),
    Row("rietx.indexing.reduce._SETTING_STEPS", "constant", value=200),
    Row("rietx.indexing.reduce._SETTING_TIE", "constant", value=1e-12),
    Row("rietx.indexing.svd.ANGLE_HI", "constant", value=130.0),
    Row("rietx.indexing.svd.ANGLE_LO", "constant", value=90.0),
    Row("rietx.indexing.svd.IMPURITY_CUT_DEG", "constant", value=0.05),
    Row("rietx.indexing.svd.KAPPA_PROBES", "constant", value=24),
    Row("rietx.indexing.svd.KAPPA_VOLUME", "constant", value=500.0),
    Row("rietx.indexing.svd.MAX_BOX_INDEX", "constant", value=40),
    Row("rietx.indexing.svd.MAX_ITERATIONS", "constant", value=20),
    Row("rietx.indexing.svd.NC_NO_HI", "constant", value=4.0),
    Row("rietx.indexing.svd.NC_NO_LO", "constant", value=0.3333333333333333),
    Row("rietx.indexing.svd.TRIM_RETRY", "constant", value=1),
    Row("rietx.indexing.svd.VOLUME_LADDER_RATIO", "constant", value=1.1),
    Row("rietx.indexing.svd.WEIGHT_EXPONENT", "constant", value=4.0),
    Row("rietx.indexing.svd.ZERO_ERROR_LIMIT_DEG", "constant", value=0.1),
    Row("rietx.indexing.trial_error.BASE_INDEX_MAX", "constant", value=2),
    Row("rietx.indexing.trial_error.BASE_POOL_MIN", "constant", value=8),
    Row("rietx.indexing.trial_error.DOMINANT_ZONE_MAX_DOF", "constant", value=2),
    Row("rietx.indexing.trial_error.DOMINANT_ZONE_PROBE_LADDER", "constant", value=(3, 5, 9)),
    Row("rietx.indexing.trial_error.DOMINANT_ZONE_PROBE_SECONDS", "constant", value=30.0),
    Row("rietx.indexing.trial_error.MAX_ASSIGN_PER_BASE", "constant", value=4000000),
    Row("rietx.indexing.trial_error.SOLVE_CHUNK", "constant", value=200000),
    Row("rietx.indexing.workflow.ABSENT_SIGMA", "constant", value=3.0),
    Row("rietx.indexing.workflow.ABSENT_WINDOW_FWHM", "constant", value=0.5),
    Row("rietx.indexing.workflow.VALIDATION_METRIC_REL", "constant", value=0.01),
    Row("rietx.indexing.workflow.VALIDATION_SLACK_BOUNDS_DEG", "constant", value=(0.3, 6.0)),
    Row("rietx.io.formats.base.HEAD_BYTES", "constant", value=4096),
    Row("rietx.io.formats.base.INTEGRAL_TOL", "constant", value=0.001),
    Row("rietx.io.formats.dif._MIN_ROWS", "constant", value=3),
    Row("rietx.io.formats.gsas.ESD_FIELD_CHARS", "constant", value=8),
    Row("rietx.io.formats.gsas.TIME_MAP_FIELD_CHARS", "constant", value=8),
    Row("rietx.io.formats.gsas._GSAS_TIME_MAP_SCAN_BYTES", "constant", value=65536),
    Row("rietx.io.formats.peaklist._MIN_ROWS", "constant", value=8),
    Row("rietx.io.instrument_profile.INSTPRM_SHL_FLOOR", "constant", value=0.002),
    Row("rietx.io.instrument_profile._PRCF_TYPE_3", "constant", value=3),
    Row("rietx.io.instrument_profile._PRM_BANK", "constant", value=1),
    Row("rietx.io.instrument_profile._PRM_CENTIDEG", "constant", value=100.0),
    Row("rietx.io.instrument_profile._PRM_CENTIDEG_SQUARED", "constant", value=10000.0),
    Row("rietx.io.instrument_profile._PRM_COEFFICIENT_COLUMNS", "constant", value=15),
    Row("rietx.io.instrument_profile._PRM_COEFFICIENT_DIGITS", "constant", value=14),
    Row("rietx.io.instrument_profile._PRM_CUTOFF", "constant", value=0.001),
    Row("rietx.io.instrument_profile._PRM_GAUSS_TO_DEG2", "constant", value=0.0005545177444479562),
    Row("rietx.io.instrument_profile._PRM_PER_RECORD", "constant", value=4),
    Row("rietx.io.projects.fullprof._CELL_TIE_MULTIPLIER_TOL", "constant", value=1e-06),
    Row("rietx.io.projects.fullprof._DISPERSION_ATOL_E", "constant", value=0.01),
    Row("rietx.io.projects.fullprof._MAGNETIC_MATCH_ATOL", "constant", value=0.0001),
    Row("rietx.io.projects.fullprof._NAM_WIDTH", "constant", value=4),
    Row("rietx.io.projects.fullprof._OCCUPANCY_RTOL", "constant", value=0.005),
    Row("rietx.io.projects.fullprof._RHOMBOHEDRAL_ANGLE_ATOL", "constant", value=0.01),
    Row("rietx.io.projects.fullprof._RHOMBOHEDRAL_LENGTH_RTOL", "constant", value=0.001),
    Row("rietx.io.projects.fullprof._USER_B_ATOL_FM", "constant", value=0.001),
    Row("rietx.io.projects.registry.INP_SNIFF_BYTES", "constant", value=65536),
    Row("rietx.io.projects.topas_input.CALC_POINTS_PER_FWHM", "constant", value=16),
    Row("rietx.io.projects.topas_input.DEFAULT_RADIUS_MM", "constant", value=217.5),
    Row("rietx.io.projects.topas_input._SABINE_LAUE", "constant", value=(-0.5, 0.25, -0.10416667, 0.036458333, -0.0109375, 0.0028497409)),
    Row("rietx.io.projects.topas_input._SABINE_XPOL", "constant", value=0.079411),
    Row("rietx.io.projects.topas_input._TCH_ETA", "constant", value=(1.36603, -0.47719, 0.11116)),
    Row("rietx.io.projects.topas_input._TCH_GAMMA", "constant", value=(2.69269, 2.42843, 4.47163, 0.07842)),
    Row("rietx.io.readers.TWO_THETA_MAX_DEG", "constant", value=180.0),
    Row("rietx.model.absorption.CYLINDER_MU_R_MAX", "constant", tier=2, value=1.0,
        evidence=("Rouse, Cooper, York & Chakera (1970) Acta Cryst. A26, 682: fit domain 0 <= µR <="
                  " 1 (docstring); gates a warning only")),
    Row("rietx.model.absorption._A1", "constant", tier=2, value=1.7133,
        evidence=("Rouse et al. (1970) Acta Cryst. A26, 682, eq 2 (docstring); quadrature of ITC "
                  "6.3.3.4 reproduces the paper's 0.0035 bound (tests/test_absorption.py:195)")),
    Row("rietx.model.absorption._A2", "constant", tier=2, value=-0.0927,
        evidence=("Rouse et al. (1970) Acta Cryst. A26, 682, eq 2 (docstring); quadrature of ITC "
                  "6.3.3.4 reproduces the paper's 0.0035 bound (tests/test_absorption.py:195)")),
    Row("rietx.model.absorption._B1", "constant", tier=2, value=-0.0368,
        evidence=("Rouse et al. (1970) Acta Cryst. A26, 682, eq 2 (docstring); quadrature of ITC "
                  "6.3.3.4 reproduces the paper's 0.0035 bound (tests/test_absorption.py:195)")),
    Row("rietx.model.absorption._B2", "constant", tier=2, value=-0.375,
        evidence=("Rouse et al. (1970) Acta Cryst. A26, 682, eq 2 (docstring); quadrature of ITC "
                  "6.3.3.4 reproduces the paper's 0.0035 bound (tests/test_absorption.py:195)")),
    Row("rietx.model.compiled.KERNEL_ABI", "constant", tier=1, value=1,
        evidence=("arithmetic: interface version (the wheel's major), moves only with a signature "
                  "change; test_a_wheel_of_another_interface_is_declined_by_both_numbers")),
    Row("rietx.model.compiled.MAX_TERMS", "constant", tier=1, value=4,
        evidence=("arithmetic: the kernel signature has four term slots and _peak_chain_column "
                  "builds four (I, pos, width, mixing); "
                  "test_the_scatter_declines_an_arity_it_was_not_written_for")),
    Row("rietx.model.compiled.SPELL_BASIS", "constant", tier=1, value=1,
        evidence=("arithmetic: enum naming one of two associations of one expression; "
                  "test_the_forward_and_the_bases_keep_their_separate_spellings")),
    Row("rietx.model.compiled.SPELL_FORWARD", "constant", tier=1, value=0,
        evidence=("arithmetic: enum naming one of two associations of one expression; "
                  "test_the_forward_and_the_bases_keep_their_separate_spellings")),
    Row("rietx.model.compiled._NS_PER_CONTACT", "constant", tier="invariant", value=1.0,
        evidence=("A work estimate that only decides whether a call is split across the "
                  "pool; reflections and replicas are disjoint rows, and "
                  "tests/test_solve_kernels.py::test_a_split_call_lands_on_the_inline_bits "
                  "holds a four-worker split bit-identical to the inline call for all three "
                  "solve kernels.")),
    Row("rietx.model.compiled._NS_PER_IMAGE", "constant", tier="invariant", value=7.5,
        evidence=("A work estimate that only decides whether a call is split across the "
                  "pool; reflections and replicas are disjoint rows, and "
                  "tests/test_solve_kernels.py::test_a_split_call_lands_on_the_inline_bits "
                  "holds a four-worker split bit-identical to the inline call for all three "
                  "solve kernels.")),
    Row("rietx.model.compiled._THREAD_MIN_NS", "constant", tier="invariant", value=100000.0,
        evidence=("answer-invariant: rows are disjoint and each computed whole in one chunk; "
                  "tests/test_compiled_kernels.py::test_a_split_call_lands_on_the_inline_bits")),
    Row("rietx.model.extinction._PI2", "constant", tier=1, value=0.7978845608028654,
        evidence="arithmetic: sqrt(2/pi)"),
    Row("rietx.model.extinction._XPOL", "constant", tier=1, value=0.079411,
        evidence=("physics: (r_e x 1e4 A/um)^2 with r_e = 2.818 fm is 0.079411; GSAS-II 5.8.4 "
                  "GSASIIstrMath.GetPwdrExt uses the same value (checked)")),
    Row("rietx.model.forward.AXIAL_SIZING_FLOOR", "constant", tier=3, value=0.02,
        evidence=("window and node sizing floor for S/L, H/L freed from zero; fails: sized at 0.02, "
                  "a stage reaching 0.05/0.05 leaves 0.27 of the peak maximum (15 nodes; bar 7.2e-4) "
                  "and drops up to 19.5 % of a peak area (tests/test_lab_instrument.py, the axial "
                  "floor block); 0.05 passes at 1.25-1.8x fit time, mostly because the floor also "
                  "applies to every positive ratio below it; the error is transient, since the next "
                  "stage recompiles, and the answers of the floors 0.02 and 0.05 differ by 0.229, "
                  "0.516 and 0.380 plain esd on LaB6, FAP and cpd-1a without the closing stage and "
                  "by 0.007, 0.002 and 0.138 behind it (tests/test_staged_start_invariance.py; "
                  "cpd-1a's corundum c a strict xfail; WP-2002, 2026-10-21)"),
        grounds=("A numerical setting whose domain test fails over part of the domain it claims; "
                 "tier 3 under B10 option 2 (ruled 2026-10-19).  The seventh round's Q2 (ruled "
                 "2026-10-21) left it alone if it passed behind the closing stage; it passes on "
                 "LaB6 and FAP and misses on cpd-1a, so it stays here; the eighth round (ruled "
                 "2026-10-22) keeps it at tier 3 for WP-2017's second pass over a refine-from-zero "
                 "floor of its own."),
        approved="2026-10-22"),
    Row("rietx.model.forward.MAGNETIC_SIZING_FLOOR", "constant", tier=3, value=0.1,
        evidence=("invariant behind the closing stage only: a magnetic width freed from "
                  "zero is drawn on windows sized at the floor, which lose 3.2 and 4.1 % of a "
                  "magnetic peak at the planted 0.22 and 0.30 deg against 2 %, and the closing "
                  "stage recompiles at the width reached; the preset's answer with the floor "
                  "shipped and at the planted width agrees to 0.000 plain esd (0.031 before the "
                  "closing stage), on the synthetic MnF2 round trip, one family "
                  "(tests/test_magnetic_width.py); the magnetic default solve's ranked trials (its "
                  "winner runs one on a solved verdict since 2026-10-22; the default solve frees "
                  "no magnetic width), a plan with closing_window_tol=None and a "
                  "stage run by hand have none, and a plan "
                  "ending on the stage that frees the width keeps the clipping: 0.07, 0.17 and "
                  "0.57 esd on the moment (WP-2002, the seventh round's Q2, 2026-10-21)"),
        grounds=("A numerical setting whose domain test passes behind the closing stage and "
                 "fails on the paths without one; tier 3 under B10 option 2 (ruled 2026-10-19), "
                 "the value left alone under the seventh round's Q2 (ruled 2026-10-21).  It was "
                 "first recorded invariant, a class with no conditional form (the generality "
                 "judge, 2026-10-22)."),
        approved="2026-10-21"),
    Row("rietx.model.forward.PAWLEY_OFF_DATA_SCALE_FLOOR", "constant", tier=3, value=1.0,
        evidence=("WP-1459 (outside PR #453): the off-data ridge is as wide as the phase's "
                  "largest on-data intensity; the floor of 1 has no stated source and binds "
                  "only where that intensity is under 1 or absent; inline in "
                  "build_pawley_restraint until the B14 lift"),
        grounds=("Opt-in Pawley mode: acts only on reflections outside the data, whose "
                 "intensity nothing constrains; kept at 1.0 (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.model.forward.PAWLEY_OVERLAP_FWHM_FRAC", "constant", tier=3, value=0.5,
        evidence=("WP-0306: 'the point past which least squares cannot apportion intensity'; LaB6 "
                  "only (synchrotron and Cu, tests/test_pawley.py), never swept; second pass owed"),
        grounds=("Opt-in Pawley mode: an overlapped group gets an equal-split restraint and is "
                 "flagged PAWLEY_OVERLAP_UNRESOLVED rather than split confidently; kept at the "
                 "LaB6 value (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.model.forward.PAWLEY_OVERLAP_LAMBDA", "constant", tier=3, value=1.0,
        evidence=("WP-0306, WP-1459: unit weight, per-group intensity scaling; Cu LaB6 (221)/(300) "
                  "sum 0.6 % off, split esd ~112 %; without the off-data ridge a (6 0 2) reached "
                  "1.45e8 against a median of 81; synthetic LaB6 and FAP only; second pass owed"),
        grounds=("Opt-in Pawley mode: the weight acts only on directions the data do not "
                 "constrain, and the group sum stays free; kept at 1.0 (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.model.forward.REFLECTION_MARGIN_DEG", "constant", tier=3, value=0.5,
        evidence=("reflection-list margin past the scan; measured 2026-10-21 on SRM 660c, FAP, cpd-1a and 11-BM NAC: fails on FAP (0.124 sigma at "
                  "129.98 deg, 0.016 esd) and cpd-1a (0.119 sigma, 0.103 esd on fluorite lor_strain), "
                  "against a bar of 0.1 sigma a point (tests/test_window_domain.py); 5 deg is "
                  "bit-identical to 20 deg on both, and the margin needed grows with the window: "
                  "at the closing stage's 1e-3 windows 0.186 and 0.124 sigma at the last "
                  "points, the answers moving 0.026 and 0.043 esd (WP-2002, 2026-10-21); generating "
                  "out to the widest edge window met 0.1 sigma (0.027 FAP, 0.022 cpd-1a) at 1.3x "
                  "FAP's closing stage, but its tail-only reflections lifted the scale-B separation "
                  "over its floor on the synthetic narrow scan of tests/test_scale_b_ridge.py and the "
                  "closing stage freed a ridge (corundum 72.5 to "
                  "50.8 wt%, true 72.7), so it was reverted"),
        grounds=("A numerical setting whose domain test fails over part of the domain it claims; "
                 "tier 3 under B10 option 2 (ruled 2026-10-19).  Ruled on 2026-10-21 (the seventh "
                 "round's Q2): an edge rule at CLOSING_WINDOW_TOL was built and reverted (evidence), "
                 "so this margin serves every compile; the eighth round (ruled 2026-10-22) keeps "
                 "it at 0.5 deg, the 0.03-0.04 esd it costs recorded, for WP-2017's second pass."),
        approved="2026-10-22"),
    Row("rietx.model.forward.WINDOW_AREA_TOL", "constant", tier=3, value=0.02,
        evidence=("window area tolerance; measured 2026-10-21 on SRM 660c, FAP, cpd-1a and 11-BM NAC against 5e-5 (converged): fails on all four, "
                  "max |dy|/sigma 0.71-2.15 at fixed parameters against a bar of 0.1, a converged "
                  "refit moving non-background rows 0.17-0.97 esd (cpd-1a zincite scale, FAP "
                  "lor_size) and background 2.1-5.1 esd (tests/test_window_domain.py); 1e-3 passes "
                  "at 1.2-3.5x fit time. Against: FAP's chi2 is 110 higher with converged tails; "
                  "GSAS-II 5.8.4 drops about 0.6 % of a pure Lorentzian (50 FWHM below, 75 "
                  "above, getWidthsCW)"),
        grounds=("A numerical setting whose domain test fails over part of the domain it claims; "
                 "tier 3 under B10 option 2 (ruled 2026-10-19).  Ruled on 2026-10-21 (the sixth "
                 "round's Q1 and Q2): it stays for the declared stages, which only steer, and the "
                 "answer is computed in a closing stage at CLOSING_WINDOW_TOL, as is every "
                 "evaluation outside a fit and a stage run by hand (the seventh round's Q1).  Its "
                 "error still reaches a number a caller reads from a plan with "
                 "closing_window_tol=None, on purpose the magnetic default solve's ranking (every "
                 "ΔBIC, and the other trials' and the nuclear reference's Rwp, GoF and "
                 "R_mag, so that all compare at one precision; on a solved verdict the "
                 "winner's moments and statistics come from a closing stage, ruled "
                 "2026-10-22), and "
                 "SolveCost.from_pawley, and on purpose the FitReport's shapes, which "
                 "report._reading_models compiles at this fraction (the eighth round's item 1, "
                 "ruled 2026-10-22)."),
        approved="2026-10-22"),
    Row("rietx.model.forward.WINDOW_MIN_DEG", "constant", tier=3, value=0.3,
        evidence=("minimum window half-width, the room a peak has to move within one stage; "
                  "measured 2026-10-21 on SRM 660c, FAP, cpd-1a and 11-BM NAC from starts near "
                  "each answer and a zero 0.1 deg off: largest move 0.21 deg (1.4x margin, "
                  "tests/test_window_domain.py); untested from a cell off its answer, where 0.3 % "
                  "moves a 120 deg peak about 0.6 deg, and a peak leaving its window is silent"),
        grounds=("A numerical setting whose domain test covers less than the domain it claims; "
                 "tier 3 under B10 option 2 (ruled 2026-10-19) until that is measured."),
        approved="2026-10-19"),
    Row("rietx.model.forward._BASES_CHUNK_ROWS", "constant", tier="invariant", value=128,
        evidence=("chunking of the derivative bases; bit-identical at 1, 7, 128 and 4096 rows on a "
                  "298-row node bucket, every derivative plane and the forward pattern, tchz_pv and "
                  "voigt (tests/test_derivative_bases_batched.py)"),
        grounds=("An internal split whose test asserts the identity; invariant under B10 "
                 "option 2 (ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.model.forward._GAUSS_TAIL_C", "constant", tier=1, value=1.6651092223153954,
        evidence=("arithmetic: sigma = G/(2 sqrt(2 ln2)) so the area outside +-kG is erfc(2 "
                  "sqrt(ln2) k)")),
    Row("rietx.model.forward._MEMO_DEPTH", "constant", tier="invariant", value=2,
        evidence=("answer-invariant: a hit needs bit-equal inputs; tests/test_scalar_memo.py::test_"
                  "a_whole_fit_is_bit_identical_with_the_memo_denied")),
    Row("rietx.model.geometry.ANGLE_LINEARISATION_LIMIT_DEG", "constant", tier=1, value=0.002562345120281331,
        evidence=("physics: a straight angle is a stationary point of the coordinates; value "
                  "inherits restraints._COS_CLAMP with no free factor")),
    Row("rietx.model.geometry.BOND_SLACK_ANG", "constant", tier=2, value=0.4,
        evidence=("CSD bond-perception convention (radii sum + 0.4 A), named in WP-1072; radii are "
                  "Cordero 2008, checked in the docstring (not checked by me)")),
    Row("rietx.model.geometry.CONTACT_MAX_ANG", "constant", tier=1, value=3.5,
        evidence=("report scope (tier 1's cap clause, ruled 2026-10-21): every contact within "
                  "3.5 A is listed, in an unreduced cell where a fixed one-cell shell drops a "
                  "3.04 A contact, and bonds are found past it (CsCl's 3.571 A Cs-Cl, eight a "
                  "site; the search once stopped at the radius and listed none), "
                  "tests/test_geometry_table.py; the radius travels on "
                  "GeometryTable.contact_max (WP-2002)")),
    Row("rietx.model.geometry.MAX_ASYM_ATOMS", "constant", tier=1, value=200,
        evidence=("report scope (tier 1's cap clause, ruled 2026-10-21): a phase past it is "
                  "skipped whole and GeometryTable.notes says so, tests/test_geometry_table.py; "
                  "the structure CIFs in tests/data reach 32 atoms. The search time at 200 is "
                  "unmeasured and a caller cannot raise it, a cost question rather than one of "
                  "completeness (WP-2002)")),
    Row("rietx.model.geometry.MAX_CONTACTS_PER_ATOM", "constant", tier=1, value=24,
        evidence=("report scope (tier 1's cap clause, ruled 2026-10-21): the note counts "
                  "exactly what the cap drops, the kept contacts are the nearest and bonds are "
                  "never dropped (31 on corundum with the cap at 2, "
                  "tests/test_geometry_table.py); tests/data's structures reach 20 a site "
                  "(WP-2002)")),
    Row("rietx.model.geometry.SYMMETRY_CODE_MAX_SHIFT", "constant", tier=1, value=4,
        evidence="format: CIF symmetry code digit = shift + 5, so -4..+4 (docstring)"),
    Row("rietx.model.geometry.VARIANCE_CANCELLATION_FLOOR", "constant", tier=1, value=1e-12,
        evidence=("numerical floor: about 4.5e3 x fp64 eps, five orders below the smallest powder "
                  "esd (docstring); stops 90.00000000000(43)")),
    Row("rietx.model.geometry._COINCIDENT_D2", "constant", tier=1, value=1e-06,
        evidence=("numerical floor: any value between roundoff and the shortest real interatomic "
                  "d^2 (>0.1 A^2) gives the same lists")),
    Row("rietx.model.origin.A5_CLIP", "constant", tier=1, value=1e-4,
        evidence=("numerical setting with a domain test (tests/test_floating_origin.py, "
                  "test_the_clipped_centroid_stays_within_an_esds_own_error_of_the_hold): moves only "
                  "the origin convention (contrast variances unchanged to 4e-16), and light sites' z "
                  "esds sit at most 0.14 % from the hold limit over 1200 realisable (A5) failures "
                  "against a 1 % bar (an esd's own sampling error at N - P = 5000); 1e-3 left 1.40 %; "
                  "about 1 ms more per solve (WP-2002, the seventh round's Q2, 2026-10-21)")),
    Row("rietx.model.origin.A6_MAX_ITER", "constant", tier="invariant", value=2000,
        evidence=("answer-invariant: caps a weights-only iteration; reached by 498 of the 1200 "
                  "realisable (A5) failures at A5_CLIP 1e-4, every one met by the sum solve; "
                  "tests/test_floating_origin.py::test_eq_21_is_met_where_a5_holds_by_a_hair asserts "
                  "eq 21 met where (A6) stalls at its cap")),
    Row("rietx.model.origin.A6_RTOL", "constant", tier=2, value=0.001,
        evidence=("Flack & Schwarzenbach (1988) Acta Cryst. A44, 499, Appendix: 'about five "
                  "iterations ... the 0.1% level' (docstring)")),
    Row("rietx.model.origin.A6_STEP_RTOL", "constant", tier=1, value=1e-12,
        evidence=("numerical floor: 4e3 x eps; each pass is O(N); moves only the covariance "
                  "weights, not the answer")),
    Row("rietx.model.origin.ORIGIN_FD_STEP", "constant", tier=1, value=1e-05,
        evidence=("numerical floor: eps^(1/3) = 6e-6 is the central-difference optimum; truncation "
                  "~1e-10 of the curvature (docstring); only the weights a_n, hence the covariance,"
                  " depend on it")),
    Row("rietx.model.preferred_orientation.TEXTURE_POSITIVITY_TOL", "constant", tier=1, value=1e-09,
        evidence=("numerical floor: roundoff of a quantity of order 1; lm stopped at min P -2.2e-16"
                  " on the face, trf at -0.45 (WP-1960 D4)")),
    Row("rietx.model.preferred_orientation.TEXTURE_POLISH_LEVELS", "constant", tier=1, value=6,
        evidence=("numerical setting with a domain test (tests/test_texture.py, "
                  "test_the_sampled_sphere_minimum_meets_the_true_one): the polish's last patch "
                  "steps about 1e-5 rad, and the polished minimum sits at most 1.7e-9 above the "
                  "true one at orders 2-8 (9.4e-9 at 16) against a 1e-3 bar (WP-2002, the seventh "
                  "round's Q2, 2026-10-21)")),
    Row("rietx.model.preferred_orientation.TEXTURE_POLISH_STARTS", "constant", tier=1, value=5,
        evidence=("numerical setting with a domain test (tests/test_texture.py, "
                  "test_the_sampled_sphere_minimum_meets_the_true_one): polished from the five "
                  "lowest of the 2000 samples, the minimum sits at most 1.7e-9 above the true one "
                  "at orders 2-8 against a 1e-3 bar; at 0 starts it sat 2.0e-3 to 7.9e-3 above; "
                  "9-15 ms a call at order 8 in P -1 (WP-2002, the seventh round's Q2, "
                  "2026-10-21)")),
    Row("rietx.model.preferred_orientation.TEXTURE_SPHERE_SAMPLES", "constant", tier=1, value=2000,
        evidence=("numerical setting with a domain test (tests/test_texture.py, "
                  "test_the_sampled_sphere_minimum_meets_the_true_one): the samples find the dips "
                  "and sphere_minimum polishes the lowest, leaving at most 1.7e-9 at orders 2-8 "
                  "against a 1e-3 bar; sampled alone they left 2.0e-3 to 7.9e-3, falling as 1/N "
                  "(WP-2002, the seventh round's Q2, 2026-10-21)")),
    Row("rietx.model.profiles.caglioti.GAUSSIAN_VARIANCE_TO_FWHM_SQUARED", "constant", tier=1, value=5.545177444479562,
        evidence=("arithmetic: FWHM = 2 sqrt(2 ln2) sigma; pinned against GSAS-II's drawn LaB6 "
                  "peaks, tests/test_gsas2_instprm.py")),
    Row("rietx.model.profiles.caglioti.SCHERRER_K", "constant", tier=2, value=0.9,
        evidence=("Scherrer (1918); Langford & Wilson (1978) J. Appl. Cryst. 11, 102 (0.89 sphere "
                  "FWHM; docstring; not checked)")),
    Row("rietx.model.profiles.caglioti._MIN_GAMMA_G2", "constant", tier=3, value=1e-08,
        evidence=("Gaussian-variance floor (WP-2002, 2026-10-21, tests/test_gaussian_width_floor.py): "
                  "max |dy|/sigma at fixed parameters 0 on SRM 660c, FAP and NAC and 4.8e-9 on cpd-1a; "
                  "where it binds it moves a peak 4.4e-4 (Lorentz FWHM 0.005 deg) and 1.6e-4 (0.01 deg) "
                  "of its height, within the lab and synchrotron bars respectively, but 9.9e-4 at "
                  "0.003 deg; the "
                  "LaB6 and cpd-1a answers end on the floor and move 1.2 esd on U under a 1e-10 floor"),
        grounds=("A numerical setting whose domain test fails over part of the domain it claims; "
                 "tier 3 under B10 option 2 (ruled 2026-10-19) until it is ruled on."),
        approved="2026-10-19"),
    Row("rietx.model.profiles.faddeeva.WEIDEMAN_N", "constant", tier=1, value=32,
        evidence=("numerical floor: abs error < 1e-12 vs scipy wofz over the upper half-plane, "
                  "tests/test_voigt.py::test_faddeeva_matches_scipy_over_upper_half_plane; Weideman"
                  " (1994)")),
    Row("rietx.model.profiles.faddeeva._INV_SQRT_PI", "constant", tier=1, value=0.5641895835477563,
        evidence="arithmetic: 1/sqrt(pi)"),
    Row("rietx.model.profiles.faddeeva._WEIDEMAN_L", "constant", tier=1, value=4.756828460010884,
        evidence=("arithmetic: derived from WEIDEMAN_N with no free factor, Weideman (1994) J. "
                  "Numer. Anal. 31, 1497 (docstring)")),
    Row("rietx.model.profiles.fcj.CLOSING_MAX_NODES", "constant", tier=1, value=1024,
        evidence=("numerical setting with a domain test (tests/test_lab_instrument.py, test_the_closing_node_rule_meets_the_bar): the closing rule, taken by a compile finer than WINDOW_AREA_TOL (the closing stage at any closing_window_tol below it, a stage run by hand, every evaluation outside a fit; the line moved from CLOSING_WINDOW_TOL on 2026-10-22), meets the tenth-of-sigma bar on lab and synchrotron peaks at every eta: worst 1.6e-4 and 9.9e-5 of the peak maximum over 8 500 cases, 0.25 and 0.81 of the bars; the cheaper 11 / 8 / 768 / 3.5e-4 sat at 0.95 (WP-2002, the seventh round's Q2, 2026-10-21)")),
    Row("rietx.model.profiles.fcj.CLOSING_MIN_NODES", "constant", tier=1, value=10,
        evidence=("numerical setting with a domain test (tests/test_lab_instrument.py, test_the_closing_node_rule_meets_the_bar): the closing rule, taken by a compile finer than WINDOW_AREA_TOL (the closing stage at any closing_window_tol below it, a stage run by hand, every evaluation outside a fit; the line moved from CLOSING_WINDOW_TOL on 2026-10-22), meets the tenth-of-sigma bar on lab and synchrotron peaks at every eta: worst 1.6e-4 and 9.9e-5 of the peak maximum over 8 500 cases, 0.25 and 0.81 of the bars; the cheaper 11 / 8 / 768 / 3.5e-4 sat at 0.95 (WP-2002, the seventh round's Q2, 2026-10-21)")),
    Row("rietx.model.profiles.fcj.CLOSING_NODES_PER_FWHM", "constant", tier=1, value=12.0,
        evidence=("numerical setting with a domain test (tests/test_lab_instrument.py, test_the_closing_node_rule_meets_the_bar): the closing rule, taken by a compile finer than WINDOW_AREA_TOL (the closing stage at any closing_window_tol below it, a stage run by hand, every evaluation outside a fit; the line moved from CLOSING_WINDOW_TOL on 2026-10-22), meets the tenth-of-sigma bar on lab and synchrotron peaks at every eta: worst 1.6e-4 and 9.9e-5 of the peak maximum over 8 500 cases, 0.25 and 0.81 of the bars; the cheaper 11 / 8 / 768 / 3.5e-4 sat at 0.95 (WP-2002, the seventh round's Q2, 2026-10-21)")),
    Row("rietx.model.profiles.fcj.CLOSING_SKIP_EXTENT_FWHM_RATIO", "constant", tier=1, value=0.0003,
        evidence=("numerical setting with a domain test (tests/test_lab_instrument.py, test_the_closing_node_rule_meets_the_bar): the closing rule, taken by a compile finer than WINDOW_AREA_TOL (the closing stage at any closing_window_tol below it, a stage run by hand, every evaluation outside a fit; the line moved from CLOSING_WINDOW_TOL on 2026-10-22), meets the tenth-of-sigma bar on lab and synchrotron peaks at every eta: worst 1.6e-4 and 9.9e-5 of the peak maximum over 8 500 cases, 0.25 and 0.81 of the bars; the cheaper 11 / 8 / 768 / 3.5e-4 sat at 0.95 (WP-2002, the seventh round's Q2, 2026-10-21)")),
    Row("rietx.model.profiles.fcj.MAX_NODES", "constant", tier=3, value=64,
        evidence=("FCJ quadrature cap; the bar is a tenth of sigma/peak at the strongest peak of FAP.XRA (lab, 7.2e-4) and 11BM_NAC (synchrotron, 1.75e-4), in units of the peak maximum; measured 2026-10-21: "
                  "fails where it binds, past extent/FWHM 10 (lab below ~6.2 deg at S/L = H/L = "
                  "0.025, FWHM 0.07), 0.21-0.26 of the peak; synchrotron fails at eta 0.5 and 1"),
        grounds=("A numerical setting whose domain test (tests/test_lab_instrument.py, the FCJ "
                 "section) fails over part of the domain it claims; tier 3 under B10 option 2 "
                 "(ruled 2026-10-19).  Ruled on 2026-10-21 (the seventh round's Q2): it stays for "
                 "the declared stages, and the answer is sampled at the closing rule "
                 "(CLOSING_NODES_PER_FWHM and its siblings).  It still computes the answer of a "
                 "plan with closing_window_tol=None (up to 5.6e-3 of a lab peak's maximum), and "
                 "the FitReport's shapes (the eighth round's item 1)."),
        approved="2026-10-21"),
    Row("rietx.model.profiles.fcj.MIN_NODES", "constant", tier=3, value=8,
        evidence=("FCJ quadrature floor; the bar is a tenth of sigma/peak at the strongest peak of FAP.XRA (lab, 7.2e-4) and 11BM_NAC (synchrotron, 1.75e-4), in units of the peak maximum; measured 2026-10-21: "
                  "passes lab eta <= 0.5 (worst 3.95e-4), fails lab eta 1 (7.9e-4) and "
                  "synchrotron eta 0.5 and 1; any value <= 8 is inert, since max(n//2, 4) "
                  "floors every reflection at 8 images, so only a rise changes anything"),
        grounds=("A numerical setting whose domain test (tests/test_lab_instrument.py, the FCJ "
                 "section) fails over part of the domain it claims; tier 3 under B10 option 2 "
                 "(ruled 2026-10-19).  Ruled on 2026-10-21 (the seventh round's Q2): it stays for "
                 "the declared stages, and the answer is sampled at the closing rule "
                 "(CLOSING_NODES_PER_FWHM and its siblings).  It still computes the answer of a "
                 "plan with closing_window_tol=None (up to 5.6e-3 of a lab peak's maximum), and "
                 "the FitReport's shapes (the eighth round's item 1)."),
        approved="2026-10-21"),
    Row("rietx.model.profiles.fcj.NODES_PER_FWHM", "constant", tier=3, value=6.0,
        evidence=("FCJ quadrature density; the bar is a tenth of sigma/peak at the strongest peak of FAP.XRA (lab, 7.2e-4) and 11BM_NAC (synchrotron, 1.75e-4), in units of the peak maximum; measured 2026-10-21: "
                  "passes lab eta 0 (4.4e-4), fails lab eta 0.5 and 1 (2.4e-3, 5.6e-3) and "
                  "synchrotron at every eta; worst at S/L = H/L or one aperture zero, where half "
                  "the images sit on a zero-length segment"),
        grounds=("A numerical setting whose domain test (tests/test_lab_instrument.py, the FCJ "
                 "section) fails over part of the domain it claims; tier 3 under B10 option 2 "
                 "(ruled 2026-10-19).  Ruled on 2026-10-21 (the seventh round's Q2): it stays for "
                 "the declared stages, and the answer is sampled at the closing rule "
                 "(CLOSING_NODES_PER_FWHM and its siblings).  It still computes the answer of a "
                 "plan with closing_window_tol=None (up to 5.6e-3 of a lab peak's maximum), and "
                 "the FitReport's shapes (the eighth round's item 1)."),
        approved="2026-10-21"),
    Row("rietx.model.profiles.fcj.SKIP_EXTENT_FWHM_RATIO", "constant", tier=3, value=0.02,
        evidence=("FCJ skip below this extent; the bar is a tenth of sigma/peak at the strongest peak of FAP.XRA (lab, 7.2e-4) and 11BM_NAC (synchrotron, 1.75e-4), in units of the peak maximum; measured 2026-10-21: "
                  "fails both at 9.5e-3, the error being about 0.48 x extent/FWHM, so the bar "
                  "needs 1.5e-3 (lab) or 3.7e-4 (synchrotron)"),
        grounds=("A numerical setting whose domain test (tests/test_lab_instrument.py, the FCJ "
                 "section) fails over part of the domain it claims; tier 3 under B10 option 2 "
                 "(ruled 2026-10-19).  Ruled on 2026-10-21 (the seventh round's Q2): it stays for "
                 "the declared stages, and the answer is sampled at the closing rule "
                 "(CLOSING_NODES_PER_FWHM and its siblings).  It still computes the answer of a "
                 "plan with closing_window_tol=None (up to 5.6e-3 of a lab peak's maximum), and "
                 "the FitReport's shapes (the eighth round's item 1)."),
        approved="2026-10-21"),
    Row("rietx.model.profiles.pseudovoigt._4LN2", "constant", tier=1, value=2.772588722239781,
        evidence="arithmetic: exp(-4 ln2 x^2/G^2) puts the half maximum at x = G/2"),
    Row("rietx.model.profiles.pseudovoigt._SQRT_LN2_PI", "constant", tier=1, value=0.46971863934982566,
        evidence="arithmetic: (2/G) sqrt(ln2/pi) normalises the FWHM-parameterised Gaussian"),
    Row("rietx.model.profiles.pseudovoigt._TCH_ETA", "constant", tier=2, value=(1.36603, -0.47719, 0.11116),
        evidence=("Thompson, Cox & Hastings (1987) J. Appl. Cryst. 20, 79, eq 5 (docstring); TCHZ "
                  "is the default CW shape of GSAS-II and FullProf's TCH function"
                  "; seven programs, 2026-10-21 (docs/practice.md): the same coefficients in GSAS-II, FullProf, RIETAN-FP, EasyDiffraction and TOPAS (whose 0.1116 for the cubic term is likely a misprint); MAUD and BGMN use no TCH")),
    Row("rietx.model.profiles.pseudovoigt._TCH_GAMMA", "constant", tier=2, value=(2.69269, 2.42843, 4.47163, 0.07842),
        evidence=("Thompson, Cox & Hastings (1987) J. Appl. Cryst. 20, 79, eq 4; GSAS-II 5.8.4 "
                  "GSASIIpwd.py:975 same coefficients (checked)"
                  "; seven programs, 2026-10-21 (docs/practice.md): the same coefficients in GSAS-II, FullProf, RIETAN-FP, EasyDiffraction and TOPAS; MAUD and BGMN use no TCH")),
    Row("rietx.model.profiles.voigt.GAUSS_FWHM_TO_SIGMA", "constant", tier=1, value=2.3548200450309493,
        evidence="arithmetic: FWHM = 2 sqrt(2 ln2) sigma"),
    Row("rietx.model.profiles.voigt._SQRT2", "constant", tier=1, value=1.4142135623730951,
        evidence="arithmetic: sqrt(2), the Voigt argument z = (x + i gamma)/(sigma sqrt 2)"),
    Row("rietx.model.profiles.voigt._SQRT2PI", "constant", tier=1, value=2.5066282746310002,
        evidence="arithmetic: sqrt(2 pi)"),
    Row("rietx.model.restraints.MIN_IMAGE_SHELL", "constant", tier=1, value=1,
        evidence=("numerical setting (tier 1's domain clause): the first pass of the minimum-image "
                  "search, which only bounds the second, sized per cell by geometry._shell; "
                  "exact on 50 000 pairs over reduced triclinic, reduced monoclinic, hexagonal, "
                  "rhombohedral and unreduced monoclinic (beta 135-150 deg) cells, where one "
                  "shell alone missed 72 of 2518 pairs within 4 A, tests/test_restraints.py "
                  "(WP-2002, 2026-10-21)")),
    Row("rietx.model.restraints._COINCIDENT_D2", "constant", tier=1, value=1e-06,
        evidence=("numerical floor: any value between roundoff and the shortest real interatomic "
                  "d^2 gives the same image")),
    Row("rietx.model.restraints._COS_CLAMP", "constant", tier=1, value=0.999999999,
        evidence=("numerical floor: affects only angles within 0.0026 deg of 0 or 180, which are "
                  "unsupported restraint targets; value chosen, not sqrt(eps)")),
    Row("rietx.model.restraints._DEG", "constant", tier=1, value=0.017453292519943295,
        evidence="arithmetic: pi/180"),
    Row("rietx.model.tof_spectrum.POINT_BY_POINT_ITYP", "constant", tier=1, value=10,
        evidence="format: GSAS Technical Manual p. 129, 222 define ITYP 10 (docstring)"),
    Row("rietx.optimize.bccg._CAUCHY_ARMIJO", "constant", tier=3, value=0.0001,
        evidence=("Moré & Toraldo (1991) SIAM J. Optim. 1, 93 for the projected search (docstring);"
                  " 1e-4 is the textbook Armijo c1 (recalled, not checked)"),
        grounds=("A constant that decides where a line search stops, the textbook Armijo "
                 "value; no source validated it on rietx's problems, so tier 3 until refits "
                 "of three families on either side give one answer, as B10's solver-path "
                 "switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.bccg._CAUCHY_HALVINGS", "constant", tier=1, value=60,
        evidence=("arithmetic: 2^-60 = 8.7e-19 sits below fp64 epsilon, so no further halving "
                  "changes the point")),
    Row("rietx.optimize.bccg._CONVERGED_FRACTION", "constant", tier=3, value=0.0001,
        evidence=("Coelho (2005) J. Appl. Cryst. 38, 455, § 2 termination (docstring; paper not on "
                  "disk)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.bccg._CONVERGED_RUNS", "constant", tier=3, value=3,
        evidence=("Coelho (2005) J. Appl. Cryst. 38, 455, § 2 termination (docstring; paper not on "
                  "disk)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.bccg._PCG_BUDGET_PER_VARIABLE", "constant", tier=3, value=2,
        evidence=("WP-1953: 24 NAC Pawley systems, 2n held every solve under 0.64 s, Rwp "
                  "0.12620721 against 0.12620514 unbudgeted; one family; second pass owed (refits "
                  "of three families on either side)"),
        grounds=("A solver-path switch no refiner has a view on; kept at tier 3 until refits of "
                 "three families on either side give one answer (B10, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.bccg._PCG_TOL", "constant", tier=3, value=1e-10,
        evidence=("WP-1953: FAP.XRA Pawley (343 columns) and 11-BM NAC Pawley; BCCG's 1e-2 stop "
                  "took 341 evaluations against 20 on FAP's profile stage; second pass owed "
                  "(refits of three families on either side)"),
        grounds=("A solver-path switch no refiner has a view on; kept at tier 3 until refits of "
                 "three families on either side give one answer (B10, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.bccg._SMALL_FACTOR", "constant", tier=3, value=200.0,
        evidence="Coelho (2005) J. Appl. Cryst. 38, 455, eq (2) (docstring; paper not on disk)",
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.bccg._SMALL_RUNS", "constant", tier=3, value=6,
        evidence="Coelho (2005) J. Appl. Cryst. 38, 455, § 2 (docstring; paper not on disk)",
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.blocked.DENSE_JACOBIAN_MAX_BYTES", "constant", tier=3, value=268435456,
        evidence=("switches the dense solve to the blocked one; "
                  "tests/test_parametric_series.py::test_a_blocked_fit_lands_on_the_dense_answer holds "
                  "the two within 0.01 esd on one case; refits of three families on either side owed"),
        grounds=("A solver-path switch no refiner has a view on, the seventh beside B10's six; "
                 "tier 3 until refits of three families on either side give one answer "
                 "(ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.blocked._DENSE_EIGEN_MAX", "constant", tier="invariant", value=64,
        evidence=("dense against Lanczos |lambda|max; it only places the pseudo-inverse cut: across "
                  "the switch (83-84 and 204 columns) |lambda|max agrees to 3.7e-14 relative against a "
                  "1e-6 tolerance, the nearest eigenvalue sits 2.4e10x the cut away, and esds, "
                  "correlations and discarded directions are bit-identical "
                  "(tests/test_parametric_series.py)"),
        grounds=("An internal split whose test asserts the identity; invariant under B10 "
                 "option 2 (ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.identifiability.EXCHANGE_MIN_LOADING", "constant", value=0.05),
    Row("rietx.optimize.identifiability.SOFT_MODES_K", "constant", value=3),
    Row("rietx.optimize.identifiability.SOFT_MODE_MIN_LOADING", "constant", value=0.1),
    Row("rietx.optimize.identifiability.TOP_CORRELATIONS_K", "constant", value=5),
    Row("rietx.optimize.least_squares.FD_STEP", "constant", tier=3, value=1e-06,
        evidence=("finite-difference step (WP-2002, 2026-10-21, tests/test_cross_backend.py): every FD "
                  "column of the 23 configurations within 2.5e-4 of a Richardson oracle (5.0e-4 with "
                  "the oracle's own error, SRM 660c's extinction) against a 1e-3 bar, and at the FAP and NAC answers an answer shift of 3.3e-5 esd; fails where a "
                  "reflection sits on the Gaussian-variance floor (LaB6 and cpd-1a answers, u column "
                  "2.2e-2 off), a face of the clamp rather than of the step: 1e-8 does not cure it"),
        grounds=("A numerical setting whose domain test fails over part of the domain it claims; "
                 "tier 3 under B10 option 2 (ruled 2026-10-19) until it is ruled on."),
        approved="2026-10-19"),
    Row("rietx.optimize.least_squares.GTOL", "constant", tier=3, value=1e-12,
        evidence=("a tolerance defaulted inside opt-in solver='trf' (default 'lm', "
                  "DEFAULT_SOLVER), four orders under SciPy's own 1e-8; WP-1109 tried 1e-8: "
                  "1.22-1.27x faster on cpd-1a, 1.04x slower on cpd-2, and corundum's strain "
                  "anisotropy past test_acceptance_stephens's bar (3.64 against < 2.0); "
                  "domain test owed (B10)"),
        grounds=("A number the package chooses once the caller switches TRF on, so not caller "
                 "under the caller-tier ruling (2026-10-21); a numerical setting whose domain "
                 "test is owed, tier 3 under B10 option 2 (ruled 2026-10-19)."),
        approved="2026-10-22"),
    Row("rietx.optimize.least_squares.NFEV_PER_ITERATION", "constant", tier="invariant", value=4,
        evidence=("answer-invariant: the stage budget is max_iter x 4 evaluations; on nine "
                  "configurations from four laboratories under the shipped schedule the worst "
                  "stage used 49 of 400 (8.2x, LM) and 47 (8.5x, TRF), at most 1.39 (LM) and "
                  "1.79 (TRF) evaluations an iteration; every stage at 1e-9 leaves LM 1.24x, and a "
                  "cell walking unheld bound it once, so the invariance is the shipped schedule's "
                  "(intermediate_ftol 1e-6) and B7's ruling triggers a re-measure (WP-2002, "
                  "2026-10-21); tests/test_budget_and_tolerance_invariance.py asserts the margin under both solvers and a bit-identical answer at a quarter "
                  "of the budget"),
        grounds=("B11 (ruled 2026-10-19): a budget is treated as not affecting the answer "
                 "once a test confirms its margin under both LM and TRF."),
        approved="2026-10-19"),
    Row("rietx.optimize.least_squares.STATIONARY_ANGLE_LEVEL", "constant", tier=3, value=0.95,
        evidence=("the profile interval's own level, PARAMETER_INTERVAL_LEVEL, held equal by "
                  "test; at one angle its chi-bar-squared cut is the one-sided interval's 2.706 "
                  "(test_the_cut_is_the_chi_bar_squared_point); WP-1929 measured 3 false keeps "
                  "in 48 at 95 %"),
        grounds=("B2 option 2: the test's level, cut as the profile interval cuts, so the angle "
                 "it leaves out reports that interval in place of an esd (ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.least_squares.STATIONARY_ANGLE_MAX_ITER", "constant", tier=3, value=8,
        evidence=("two-site Pnma set (WP-1929, macOS arm64): the step reaches the floor in two "
                  "or three iterations from every stop, and stops improving after one beside a "
                  "determined angle"),
        grounds=("B2 option 2: a budget on the test's Newton step, which keeps the moment sizes' "
                 "esds free of the stopping-point artefact (ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.least_squares.STATIONARY_ANGLE_STEP", "constant", tier=3, value=0.0001,
        evidence=("central-difference step in radians on an angle of order one, which "
                  "refine._flat_rotation_axis also takes for its SVD proposal (an inline 1e-4 "
                  "until the B14 lift; the finite turn decides the hold); the test it serves "
                  "moved the two-site Pnma moduli' esds from 0.031/0.159 to 0.0015/0.0011 mu_B "
                  "(WP-1929)"),
        grounds=("B2 option 2: the difference step of the test that keeps the moment sizes' "
                 "esds free of the stopping-point artefact (ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.least_squares.XTOL", "constant", tier=3, value=1e-12,
        evidence=("a tolerance defaulted inside opt-in solver='trf' (default 'lm', "
                  "DEFAULT_SOLVER), four orders under SciPy's own 1e-8; WP-1109 tried 1e-8: "
                  "1.22-1.27x faster on cpd-1a, 1.04x slower on cpd-2, and corundum's strain "
                  "anisotropy past test_acceptance_stephens's bar (3.64 against < 2.0); "
                  "domain test owed (B10)"),
        grounds=("A number the package chooses once the caller switches TRF on, so not caller "
                 "under the caller-tier ruling (2026-10-21); a numerical setting whose domain "
                 "test is owed, tier 3 under B10 option 2 (ruled 2026-10-19)."),
        approved="2026-10-22"),
    Row("rietx.optimize.lm.BVLS_MAX_COLUMNS", "constant", tier=3, value=128,
        evidence=("WP-1937, WP-1953: BVLS costs 2-34 ms at 128 columns and 10-177 s at 2000; FAP "
                  "Pawley reaches Rwp 0.0803 on one side and 0.0782 on the other (lm.py:728-735); "
                  "also the bound test's exactness limit; second pass owed (refits of three "
                  "families on either side)"),
        grounds=("A solver-path switch no refiner has a view on; kept at tier 3 until refits of "
                 "three families on either side give one answer (B10, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.lm.FTOL", "constant", tier=3, value=1e-09,
        evidence=("no stated source; one decade under SciPy's 1e-8 default (checked); GSAS-II "
                  "5.8.4's default 'min dM/M' is 1e-3, a relative chi2 change between cycles "
                  "(GSASIIobj.py:20, checked); the closing stage solves at it, and so does every "
                  "stage under intermediate_ftol=None; INTERMEDIATE_FTOL's test measures "
                  "against it (tests/test_staged_start_invariance.py), and this value itself "
                  "was never varied; the signature default of run_least_squares, "
                  "run_multi_least_squares and lm.minimize until the B14 lift"),
        grounds=("The last tolerance of the schedule rietx chose (WP-1123): B7's class went to "
                 "tier 3 once its invariance test failed on cpd-1a (ruled 2026-10-19), and the "
                 "schedule was kept on four families with that failure stated (the sixth "
                 "round's Q2, bar 0.1 plain esd, ruled 2026-10-21). That test holds 1e-9 "
                 "fixed, so the maintainer delegated this value's tier to the lead on "
                 "2026-10-23: tier 3, with WP-2017 refitting the four start-test families at "
                 "1e-8 and 1e-10."),
        approved="2026-10-23"),
    Row("rietx.optimize.lm._CONVERGED_RUNS", "constant", tier=3, value=3,
        evidence=("Coelho (2018) J. Appl. Cryst. 51, 428, termination rule (docstring: 'Coelho's "
                  "own criterion'; paper not on disk)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.lm._CURVATURE_GATE", "constant", tier=3, value=100.0,
        evidence=("WP-1953: 3762 of 3831 LM solves never raise lambda past 10, and the crawls it "
                  "catches pass 1e8; no measurement chose 100 over 30 or 1000; second pass owed "
                  "(refits of three families on either side)"),
        grounds=("A solver-path switch no refiner has a view on; kept at tier 3 until refits of "
                 "three families on either side give one answer (B10, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.lm._CURVATURE_STEP", "constant", tier=1, value=0.0001220703125,
        evidence=("arithmetic: eps^(1/4) balances the difference's truncation (h^2 S''''/12) "
                  "against its rounding (4uS/h^2) (docstring)")),
    Row("rietx.optimize.lm._EIGEN_CUT_PER_ROW", "constant", tier=1, value=2.220446049250313e-16,
        evidence=("numerical floor: eps*m, the rounding error of one inner product over m terms "
                  "(Higham 2002 §3.1; docstring)")),
    Row("rietx.optimize.lm._INNER_MAX", "constant", tier="invariant", value=18,
        evidence=("answer-invariant: on nine acceptance configurations an iteration that took "
                  "a step tried at most 6 damped trials and a stage's last iteration up to 9 "
                  "(2.0x); tests/test_budget_and_tolerance_invariance.py "
                  "asserts that margin and a bit-identical answer at 9; at 4 the answer "
                  "changes (WP-2002, 2026-10-21)"),
        grounds=("B11 (ruled 2026-10-19): a budget is treated as not affecting the answer "
                 "once a test confirms its margin under both LM and TRF; TRF has no "
                 "inner loop."),
        approved="2026-10-19"),
    Row("rietx.optimize.lm._LAMBDA_FAIL_FACTOR", "constant", tier=3, value=10.0,
        evidence=("Coelho (2018) J. Appl. Cryst. 51, 428, eq (9) (docstring; WP-0601 restates it; "
                  "paper not on disk, not checked)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.lm._LAMBDA_FAIL_FLOOR", "constant", tier=3, value=0.1,
        evidence=("Coelho (2018) J. Appl. Cryst. 51, 428, eq (9) (docstring; WP-0601 restates it; "
                  "paper not on disk, not checked)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.lm._M_HI", "constant", tier=3, value=10.0,
        evidence=("Coelho (2018) J. Appl. Cryst. 51, 428, eq (9) (docstring; WP-0601 restates it; "
                  "paper not on disk, not checked)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.lm._M_LO", "constant", tier=3, value=0.4,
        evidence=("Coelho (2018) J. Appl. Cryst. 51, 428, eq (9) (docstring; WP-0601 restates it; "
                  "paper not on disk, not checked)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.lm._NULL_CURVATURE", "constant", tier=1, value=1.4901161193847656e-08,
        evidence=("numerical floor: sqrt(eps); at the cut itself three of 1000 random problems "
                  "stayed rank-deficient, sqrt(eps) left none (docstring)")),
    Row("rietx.optimize.lm._ON_FACE", "constant", tier=1, value=1e-09,
        evidence=("numerical floor: tolerance covering the last-bit disagreement of two association"
                  " orders; the value of strategy.staged.STEPHENS_CONE_TOL (docstring)")),
    Row("rietx.optimize.lm._POLISH_FEASIBLE", "constant", tier=3, value=1e-10,
        evidence=("WP-1938 D8: 1000 random synthetic problems, the polish passed on all 898 that "
                  "crossed a row, worst row -7e-13; synthetic only; second pass owed (refits of "
                  "three families on either side)"),
        grounds=("A solver-path switch no refiner has a view on; kept at tier 3 until refits of "
                 "three families on either side give one answer (B10, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.lm._POLISH_STATIONARY", "constant", tier=3, value=1e-08,
        evidence=("WP-1938 D8: the same 1000 problems, worst stationarity residual 4e-10, eight "
                  "decades inside; synthetic only; second pass owed (refits of three families on "
                  "either side)"),
        grounds=("A solver-path switch no refiner has a view on; kept at tier 3 until refits of "
                 "three families on either side give one answer (B10, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.optimize.lm._PREDICTED_FLOOR", "constant", tier=1, value=1e-12,
        evidence=("numerical floor: rounding bound of a sum of N squares, N*eps/2 ~ 1e-12 at N ~ "
                  "9e3 (Higham 2002 §3.1; docstring: S is a sum of ~1e4 squares, resolution "
                  "~1e-16*S)")),
    Row("rietx.optimize.lm._Q_TRIGGER", "constant", tier=3, value=5,
        evidence=("Coelho (2018) J. Appl. Cryst. 51, 428, eq (9) (docstring; WP-0601 restates it; "
                  "paper not on disk, not checked)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.lm._Q_WINDOW", "constant", tier=3, value=10,
        evidence=("Coelho (2018) J. Appl. Cryst. 51, 428, eq (9) (docstring; WP-0601 restates it; "
                  "paper not on disk, not checked)"),
        grounds=("A constant that decides where a solve stops, taken from the paper that "
                 "defines the algorithm; the paper did not validate it on rietx's problems, so "
                 "tier 3 until refits of three families on either side give one answer, as "
                 "B10's solver-path switches (ruled 2026-10-20)."),
        approved="2026-10-20"),
    Row("rietx.optimize.lm._ROW_ROUNDING", "constant", tier=1, value=1e-12,
        evidence=("numerical floor: rounding of the row's own evaluation, 4.5e3 eps, seven decades "
                  "under the guards' 1e-9 (docstring)")),
    Row("rietx.optimize.qpa.BRINDLEY_MU_R_FENCE", "constant", tier=2, value=0.05,
        evidence=("Brindley (1945) Phil. Mag. 36, 347: medium powders mu*D <= 0.1, D = 2R; FullProf"
                  " manual's QPA section gives the same classes (checked: FullProf_Manual.pdf, 0.01"
                  " < mD < 0.1)"
                  "; seven programs, 2026-10-21 (docs/practice.md): FullProf prints the classes; the others not checked")),
    Row("rietx.optimize.statistics.COLUMN_SAFE_EXPONENT", "constant", tier=1, value=400,
        evidence=("arithmetic: 2^-400 = 3.9e-121 squares to 1.5e-241, a normal double; 1/d^2 stays "
                  "under 1e241 (docstring, WP-1463)")),
    Row("rietx.optimize.statistics.EFFECTIVE_OBS_ALPHA", "constant", value=2.0),
    Row("rietx.optimize.statistics.MAX_SHIFT_CONVERGED", "constant", value=0.1),
    Row("rietx.optimize.statistics.OBS_PER_PARAMETER_MIN", "constant", value=3.0),
    Row("rietx.optimize.statistics.OBS_PER_PARAMETER_PREFERRED", "constant", value=5.0),
    Row("rietx.optimize.statistics.PINV_RCOND", "constant", tier=1, value=1e-15,
        evidence=("numerical floor: 1e-15 = 4.5 eps_fp64, numpy.linalg.pinv's own default (checked:"
                  " numpy 2.5.4 docstring)")),
    Row("rietx.params.bodies.TORSION_STILL_TOL", "constant", tier=1, value=1e-06,
        evidence=("numerical floor: guards the division by the axis length and a zero Jacobian "
                  "column; 1e-6 A is far below any structural distance")),
    Row("rietx.params.bodies._DEG", "constant", tier=1, value=0.017453292519943295,
        evidence="arithmetic: degrees to radians"),
    Row("rietx.params.derived._DEG", "constant", tier=1, value=0.017453292519943295,
        evidence="arithmetic: degrees to radians"),
    Row("rietx.params.parametric.FORM_TEST_LEVEL", "constant", tier=2, value=0.95,
        evidence=("Venzon & Moolgavkar (1988) Appl. Statist. 37, 87 for the profile-likelihood cut;"
                  " the 95 % level is convention, = PARAMETER_INTERVAL_LEVEL (docstring)")),
    Row("rietx.params.parametric.RANK_RTOL", "constant", tier=1, value=3.162277660168379e-08,
        evidence=("numerical floor: sqrt(PINV_RCOND) = 3.2e-8, the R diagonal at which the "
                  "covariance's pinv would discard the direction anyway (docstring derivation)")),
    Row("rietx.params.vector.CELL_MIN_LENGTH_A", "constant", tier=2, value=1.5,
        evidence=("TOPAS Tech Ref Version 9 § 2.17 Table 2-1 (checked 2026-10-19): a, b, c floored "
                  "at Max(1.5, ...)"
                  "; seven programs, 2026-10-21 (docs/practice.md): TOPAS alone floors a cell length, and the other six have no floor; it binds on no real cell")),
    Row("rietx.params.vector.CELL_SAFETY_ANGLE_DEG", "constant", tier=3, value=6.0,
        evidence=("three times CELL_WINDOW_ANGLE_DEG; WP-1110's trigger: a visible phase sharing "
                  "its cell with a 2 % trace copy ran 4.16 -> 3803 A in one stage; fired in none "
                  "of WP-1523's 104 fits"),
        grounds=("A trigger for the reset only, set where no honest stage reaches (B8, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.params.vector.CELL_SAFETY_FRACTION", "constant", tier=3, value=0.15,
        evidence=("three times CELL_WINDOW_FRACTION; worst honest single-stage move 2.8e-4 over "
                  "WP-1110's 51 transitions; WP-1110's trigger: a visible phase sharing its cell "
                  "with a 2 % trace copy ran 4.16 -> 3803 A in one stage; fired in none of "
                  "WP-1523's 104 fits"),
        grounds=("A trigger for the reset only, set where no honest stage reaches (B8, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.params.vector.CELL_WINDOW_ANGLE_DEG", "constant", tier=3, value=2.0,
        evidence=("TOPAS Tech Ref Version 9 § 2.17 Table 2-1 (checked 2026-10-19): angles Val +- "
                  "0.2 deg per iteration, here ten iterations' worth per stage (the ten is "
                  "rietx's, and no angle was surveyed)"),
        grounds=("A guard on a barely-seen phase's cell.  Tier 3, re-tiered from 2 on "
                 "2026-10-20: TOPAS bounds every phase's cell at each iteration, while this "
                 "bounds a barely-seen phase's once per stage, ten iterations' worth, and the "
                 "ten is rietx's.  The second pass counts the stages where it binds and removes "
                 "it if none do (B8)."),
        approved="2026-10-20"),
    Row("rietx.params.vector.CELL_WINDOW_FRACTION", "constant", tier=3, value=0.05,
        evidence=("TOPAS Tech Ref Version 9 § 2.17 Table 2-1 (checked 2026-10-19): a, b, c within "
                  "0.995 Val - 0.05 .. 1.005 Val + 0.05, Val re-read each iteration; a stage takes "
                  "one bound pair, so 0.5 % compounds to 5.1 % over ten iterations (the ten is "
                  "rietx's)"),
        grounds=("A guard on a barely-seen phase's cell.  Tier 3, re-tiered from 2 on "
                 "2026-10-20: TOPAS bounds every phase's cell at each iteration, while this "
                 "bounds a barely-seen phase's once per stage, ten iterations' worth, and the "
                 "ten is rietx's.  The second pass counts the stages where it binds and removes "
                 "it if none do (B8)."),
        approved="2026-10-20"),
    Row("rietx.params.vector.CELL_WINDOW_PAD_A", "constant", tier=3, value=0.05,
        evidence=("TOPAS Tech Ref Version 9 § 2.17 Table 2-1 (checked 2026-10-19): the 0.05 A pad "
                  "on a, b, c"),
        grounds=("A guard on a barely-seen phase's cell.  Tier 3, re-tiered from 2 on "
                 "2026-10-20: TOPAS bounds every phase's cell at each iteration, while this "
                 "bounds a barely-seen phase's once per stage, ten iterations' worth, and the "
                 "ten is rietx's.  The second pass counts the stages where it binds and removes "
                 "it if none do (B8)."),
        approved="2026-10-20"),
    Row("rietx.params.vector.SIZE_CAP_ARM_RTOL", "constant", tier=1, value=1e-06,
        evidence=("numerical floor: as STRAIN_CAP_ARM_RTOL; hysteresis pinned by "
                  "test_strain_cap.py:414")),
    Row("rietx.params.vector.SIZE_CAP_RANGE_FRACTION", "constant", tier=1, value=1.0,
        evidence=("arithmetic: as STRAIN_CAP_RANGE_FRACTION, no free factor; since the 2 nm "
                  "floor went (B8, ruled 2026-10-19) the whole size bound, ~0.15 nm on a Cu "
                  "10-80 deg scan")),
    Row("rietx.params.vector.STRAIN_CAP_ARM_RTOL", "constant", tier=1, value=1e-06,
        evidence=("numerical floor: 1e-6 sits eight decades above the ~1e-14 feasibility offset and"
                  " far under any deliberate move; hysteresis pinned by test_strain_cap.py:160")),
    Row("rietx.params.vector.STRAIN_CAP_RANGE_FRACTION", "constant", tier=1, value=1.0,
        evidence=("arithmetic: a line wider than the interval it was measured over carries no "
                  "information; 1.0 is the interval itself, no free factor (docstring)")),
    Row("rietx.params.vector._ANGLE_MAX_DEG", "constant", tier=1, value=179.0,
        evidence=("arithmetic: the metric tensor is singular at 180 deg; the 1 deg margin is inert "
                  "for real cells (angles 60-120 deg)")),
    Row("rietx.params.vector._ANGLE_MIN_DEG", "constant", tier=1, value=1.0,
        evidence=("arithmetic: the metric tensor is singular at 0 deg; the 1 deg margin is inert "
                  "for real cells (angles 60-120 deg)")),
    Row("rietx.params.vector._BACKSTOP_THETA_MAX_DEG", "constant", tier=1, value=89.0,
        evidence=("numerical floor: pole guard at 2theta = 180 deg; moves no number for any pattern"
                  " ending below 2theta = 178 deg")),
    Row("rietx.params.vector._MOMENT_REFRAME_TOL", "constant", tier=1, value=1e-12,
        evidence=("numerical floor: ~4.5e3 eps, above roundoff; a frame moved 1e-12 moves the "
                  "moment by 1e-12 of its modulus (docstring)")),
    Row("rietx.params.vector._SIGMA_MAX", "constant", tier=1, value=1.3407807929942596e+154,
        evidence=("numerical floor: sqrt(float64 max) from np.finfo (the floating-point format "
                  "itself)")),
    Row("rietx.refine.AIR_SCATTER_UNDECLARED_FRACTION", "constant", value=0.005),
    Row("rietx.refine.AIR_SCATTER_UNDECLARED_SCORE", "constant", value=25.0),
    Row("rietx.refine.DISPERSION_NEGLECT_FRAC", "constant", value=0.02),
    Row("rietx.refine.DISPERSION_NEGLECT_SEVERE", "constant", value=0.05),
    Row("rietx.refine.FLAT_PLATE_BIAS_MIN", "constant", value=0.05),
    Row("rietx.refine.FROZEN_COMPILE_CHI2_REL", "constant", value=0.01),
    Row("rietx.refine.HARMONIC_ABSENT_FRAC", "constant", value=0.001),
    Row("rietx.refine.HARMONIC_IMPLAUSIBLE_FRAC", "constant", value=0.15),
    Row("rietx.refine.LEBAIL_CONVERGED_REL", "constant", tier=3, value=0.0001,
        evidence=("WP-1323: one family, 11-BM LaB6+cBN (cell exact 16.908 to 16.908; +0.3 % 16.969 "
                  "to 16.967); stops the opt-in multi-pass alternation (lebail_passes > 1) and "
                  "labels a non-lowering pass converged; second pass owed"),
        grounds=("Stops an opt-in alternation once a pass no longer lowers Rwp; kept at the "
                 "measured value, one family (B11, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.refine.LOW_ANGLE_MIN_CHANNELS", "constant", value=10),
    Row("rietx.refine.LOW_ANGLE_UNMODELLED_RATIO", "constant", value=3.0),
    Row("rietx.refine.MAGNETIC_TICK_PURITY", "constant", value=0.05),
    Row("rietx.refine.MODEL_FAR_FROM_DATA_RWP", "constant", tier=3, value=0.8,
        evidence=("WP-1028 (c): the zero-scale attractor converges at Rwp 0.99999, honest bad fits "
                  "sit at 0.2-0.5, the failures above it at 72.25 and 2.6e3 (docstring); gates "
                  "MODEL_FAR_FROM_DATA (error), hence RefinementResult.usable, read by "
                  "solve/cost.py:477; family count not recorded, second pass owed"),
        grounds=("A fit whose calculated pattern has collapsed towards zero is no answer to any "
                 "refiner; 0.8 sits in a gap 0.3 wide below and three orders wide above (B12, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.refine.MOMENT_PROBE_ANGLE_RAD", "constant", tier=3, value=0.1,
        evidence=("WP-1327, WP-1929: on Cr2WO6 4 K (HB-2A) a 1e-6 step reads 5e-7 of the modulus "
                  "response at a determined direction, the 0.1 rad turn ~1e0; both signs tried "
                  "since WP-1929; one real family plus synthetic cubic and R-3m:R"),
        grounds=("Rare feature: gates the moment hold and turn, kept at the measured value and "
                 "untested beyond its one real family (B2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.refine.PAWLEY_UNRESOLVED_REL", "constant", value=0.3),
    Row("rietx.refine.RESONANT_ABSORBER_SEVERE_BARN", "constant", value=1000.0),
    Row("rietx.refine.RESTRAINT_TENSION_SIGMA", "constant", value=3.0),
    Row("rietx.refine.ROUGHNESS_MIN_DEPRESSION", "constant", value=0.01),
    Row("rietx.refine.SCALE_B_SEPARATION_FLOOR", "constant", tier=1, value=6.324555320336758e-08,
        evidence=("numerical floor: 2*sqrt(PINV_RCOND), where pinv's cut drops a unit pair at angle"
                  " r (eigenvalue 1-|c| ~ r^2/2 against rcond*lambda_max, lambda_max ~ 2); inherits"
                  " PINV_RCOND's tier")),
    Row("rietx.refine.SCALE_B_STEP", "constant", tier=1, value=0.001,
        evidence=("numerical floor: a displacement changes heights only, so the forward difference "
                  "is exact for the question; h sets the rounding floor eps/(2h*s^2), 1e-12 to "
                  "4e-11, three decades under the floor")),
    Row("rietx.refine.SIZE_FLAG_SIZE_A", "constant", value=50.0),
    Row("rietx.refine.SPECIES_FALLBACK_MIN_DELTA_FRAC", "constant", tier=1, value=0.0,
        evidence=("arithmetic: a cut of 0 gates nothing (|delta| < 0 never holds), so every "
                  "substitution is reported; the maintainer's choice on issue #202")),
    Row("rietx.refine.STRAIN_FLAG_WIDTH", "constant", value=1.5),
    Row("rietx.refine._CENTROID_SITES_NAMED", "constant", value=12),
    Row("rietx.report.body_misfit.MISFIT_ALPHA", "constant", value=0.001),
    Row("rietx.report.body_misfit.MISFIT_BIC", "constant", value=10.0),
    Row("rietx.report.layer0.LAYER0_MATCH_TOL_DEG", "constant", value=0.08),
    Row("rietx.report.layer2.BACKGROUND_INCREASE_CAP", "constant", value=0.6),
    Row("rietx.report.layer2.IMPURITY_SIGMA", "constant", value=8.0),
    Row("rietx.report.layer2.TEXTURE_AXIS_AMBIGUITY", "constant", value=0.8),
    Row("rietx.report.localisation.SPLIT_TOLERANCE_DEG", "constant", value=1e-06),
    Row("rietx.report.magnetic._MAGNETIC_WIDTH_FLOOR_DEG", "constant", value=1e-12),
    Row("rietx.report.satellites._FWHM_FALLBACK_DEG", "constant", value=0.2),
    Row("rietx.report.schemas.BACKGROUND_ABSORPTION_NOTABLE", "constant", value=0.25),
    Row("rietx.report.schemas.COLLECT_DATA_CONFIDENCE", "constant", value=0.5),
    Row("rietx.report.schemas.CONTENTS_MAX_TEMPLATE_R2", "constant", value=0.3),
    Row("rietx.report.schemas.CONTENTS_MIN_INTENSITY_SHARE", "constant", value=0.5),
    Row("rietx.report.schemas.CONTENTS_MIN_REGIONS", "constant", value=4),
    Row("rietx.report.schemas.CONTENTS_MIN_SIGN_MINORITY", "constant", value=0.25),
    Row("rietx.report.schemas.EXCHANGEABLE_MIN_R2", "constant", value=0.9),
    Row("rietx.report.schemas.EXCHANGE_PARTNER_MIN_SIGNIFICANCE", "constant", value=5.0),
    Row("rietx.report.schemas.IMPURITY_SHIFT_CAP", "constant", value=0.3),
    Row("rietx.report.schemas.LEBAIL_GAP_CYCLES", "constant", value=5),
    Row("rietx.report.schemas.LEBAIL_GAP_NOTABLE", "constant", value=1.5),
    Row("rietx.report.schemas.MAGNETIC_WIDTH_MIN_REFLECTIONS", "constant", value=2),
    Row("rietx.report.schemas.MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA", "constant", value=1.0),
    Row("rietx.report.schemas.MAGNETIC_WIDTH_PURITY", "constant", value=0.05),
    Row("rietx.report.schemas.MAGNETIC_WIDTH_SIGMA", "constant", value=3.0),
    Row("rietx.report.schemas.MAGNETIC_WIDTH_TAIL_FWHM", "constant", value=2.0),
    Row("rietx.report.schemas.MATURITY_MAX_RWP", "constant", value=0.35),
    Row("rietx.report.schemas.MATURITY_MIN_EXPLAINED_FRACTION", "constant", value=0.4),
    Row("rietx.report.schemas.MATURITY_MIN_MISFIT_SHARE", "constant", value=0.2),
    Row("rietx.report.schemas.MAX_GRAM_CONDITION", "constant", value=10000.0),
    Row("rietx.report.schemas.MIN_COEF_SIGNIFICANCE", "constant", value=3.0),
    Row("rietx.report.schemas.MIN_REGION_CHI2_RED", "constant", value=1.5),
    Row("rietx.report.schemas.MIN_REGION_R2", "constant", value=0.5),
    Row("rietx.report.schemas.MOMENT_PAIR_RHO_MIN", "constant", value=0.95),
    Row("rietx.report.schemas.MOMENT_SUPPORT_SIGMA", "constant", value=3.0),
    Row("rietx.report.schemas.OFF_REGION_CHI2_RED_HIGH", "constant", value=1.5),
    Row("rietx.report.schemas.OFF_REGION_DW_LOW", "constant", value=1.0),
    Row("rietx.report.schemas.REINDEX_MIN_FAR_FRACTION", "constant", value=0.5),
    Row("rietx.report.schemas.REINDEX_MIN_FAR_REGIONS", "constant", value=3),
    Row("rietx.report.schemas.RESOLUTION_LIMITED_MIN_FRACTION", "constant", value=0.5),
    Row("rietx.report.schemas.RESOLUTION_LIMITED_MIN_R2", "constant", value=0.9),
    Row("rietx.report.schemas.RESOLUTION_LIMITED_MIN_REGIONS", "constant", value=3),
    Row("rietx.report.schemas.RIVAL_DECISIVE_MIN_CHI2_RATIO", "constant", value=1.1),
    Row("rietx.report.schemas.SEPARABILITY_MIN_SS_RATIO", "constant", value=2.0),
    Row("rietx.report.schemas.SHIFT_PAIR_WINDOW_DEG", "constant", value=1.0),
    Row("rietx.report.schemas.SHIFT_TICK_PROXIMITY_FWHM", "constant", value=1.0),
    Row("rietx.report.schemas.SOFT_MODE_NOTABLE_EIGENVALUE", "constant", value=0.003),
    Row("rietx.report.schemas.STRAIN_MAX_GRAM_CONDITION", "constant", value=1000.0),
    Row("rietx.report.schemas.STRAIN_MIN_ANISOTROPY", "constant", value=1.3),
    Row("rietx.report.schemas.STRAIN_MIN_R2", "constant", value=0.5),
    Row("rietx.report.schemas.STRAIN_MIN_REFLECTIONS", "constant", value=6),
    Row("rietx.report.schemas.TEXTURE_IMPURITY_MARGIN", "constant", value=0.05),
    Row("rietx.report.schemas.TEXTURE_MIN_R2", "constant", value=0.5),
    Row("rietx.report.schemas.TEXTURE_MIN_REFLECTIONS", "constant", value=4),
    Row("rietx.report.schemas.TEXTURE_MIN_STRENGTH", "constant", value=0.03),
    Row("rietx.report.schemas.TRAJECTORY_MAX_ACTIONS", "constant", value=5),
    Row("rietx.report.schemas.VALIDITY_RADIUS_FWHM", "constant", value=0.4),
    Row("rietx.report.strain._C", "constant", value=5.729577951308232e-05),
    Row("rietx.report.strain._GAUSS_NEWTON_ITERATIONS", "constant", value=4),
    Row("rietx.report.strain._QUOTABLE_WEIGHT_FRAC", "constant", value=0.01),
    Row("rietx.report.texture._EQUIV_REF_R", "constant", value=0.5),
    Row("rietx.schemas.fraction.FRACTION_PROFILE_DCHI2", "constant", tier=2, value=3.84,
        evidence=("Venzon & Moolgavkar (1988) Appl. Statist. 37, 87: profile-likelihood cut at the "
                  "chi-squared(1) 95 % point (docstring)")),
    Row("rietx.schemas.fraction.FRACTION_PROFILE_FWHM_MAX_SPAN", "constant", tier=3, value=0.5,
        evidence=("WP-1320: on the full span a pinned width outran the frozen windows "
                  "(FROZEN_COMPILE_STALE at 85 deg on an 85 deg fixture, not at 60 deg); inline "
                  "in default_fwhm_grid until the B14 lift"),
        grounds=("A numerical setting of the width grid, on the default path since the "
                 "skill sends every agent to profile_fraction (B12's ruling); tier 3 with a "
                 "test bounding its error over the claimed domain owed, tier 1 once it "
                 "passes (B10 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.fraction.FRACTION_PROFILE_FWHM_MIN", "constant", tier=3, value=0.01,
        evidence=("grid start below a lab instrument's own width; the skill tells agents to call "
                  "profile_fraction (SKILL.md), so no longer opt-in"),
        grounds=("A numerical setting of the width grid, on the default path since the "
                 "skill sends every agent to profile_fraction (B12's ruling); tier 3 with a "
                 "test bounding its error over the claimed domain owed, tier 1 once it "
                 "passes (B10 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.fraction.FRACTION_PROFILE_N_FWHM", "constant", tier=3, value=11,
        evidence=("the number of widths the grid samples; the skill tells agents to call "
                  "profile_fraction (SKILL.md), so no longer opt-in"),
        grounds=("A numerical setting of the width grid, on the default path since the "
                 "skill sends every agent to profile_fraction (B12's ruling); tier 3 with a "
                 "test bounding its error over the claimed domain owed, tier 1 once it "
                 "passes (B10 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.indexing.INDEX_MIN_INDEXED_FRACTION", "constant", value=0.9),
    Row("rietx.schemas.indexing.MAX_RELATIVE_SIGMA_Q", "constant", value=0.001),
    Row("rietx.schemas.indexing.MIN_LINES_PER_DOF", "constant", value=5.0),
    Row("rietx.schemas.indexing.PAIR_CLUSTER_HALF_WIDTH_DEG", "constant", value=0.01),
    Row("rietx.schemas.indexing.PAIR_MAX_M", "constant", value=8),
    Row("rietx.schemas.indexing.PAIR_MAX_P", "constant", value=0.01),
    Row("rietx.schemas.indexing.PAIR_MIN_CLUSTERED", "constant", value=3),
    Row("rietx.schemas.indexing.PAIR_MIN_Z", "constant", value=4.0),
    Row("rietx.schemas.indexing.PAIR_NULL_REPLICATES", "constant", value=200),
    Row("rietx.schemas.indexing.PAIR_REFUTE_K_FRACTION", "constant", value=0.6),
    Row("rietx.schemas.indexing.PAIR_WINDOW_DEG", "constant", value=0.2),
    Row("rietx.schemas.indexing.PEAK_ALIAS_RATIO_RANGE", "constant", value=(0.25, 4.0)),
    Row("rietx.schemas.indexing.PEAK_ALIAS_TOL_FWHM_FRAC", "constant", value=0.3),
    Row("rietx.schemas.indexing.PEAK_ASSUMED_ESD_DEG", "constant", value=0.02),
    Row("rietx.schemas.indexing.PEAK_ASYMMETRY_MIN_SIGMA", "constant", value=4.0),
    Row("rietx.schemas.indexing.PEAK_AXIAL_TAIL_MAX_FWHM", "constant", value=3.5),
    Row("rietx.schemas.indexing.PEAK_DETECT_SEPARATION_FWHM_FRAC", "constant", value=0.25),
    Row("rietx.schemas.indexing.PEAK_FDR_Q", "constant", value=0.01),
    Row("rietx.schemas.indexing.PEAK_KEEP_COMPONENT_MIN_DELTA_BIC", "constant", value=6.0),
    Row("rietx.schemas.indexing.PEAK_MAX_RESEED_PASSES", "constant", value=2),
    Row("rietx.schemas.indexing.PEAK_MIN_HEIGHT_SIGMA", "constant", value=5.0),
    Row("rietx.schemas.indexing.PEAK_MIN_PROMINENCE_SIGMA", "constant", value=3.0),
    Row("rietx.schemas.indexing.PEAK_MIN_USABLE_LINES", "constant", value=20),
    Row("rietx.schemas.indexing.PEAK_NO_INTENSITY_SIGMA", "constant", value=1.0),
    Row("rietx.schemas.indexing.PEAK_POSITION_BOUND_FWHM", "constant", value=0.5),
    Row("rietx.schemas.indexing.PEAK_POSITION_ESD_MAX_DEG", "constant", value=180.0),
    Row("rietx.schemas.indexing.PEAK_REFUTED_SIGMA", "constant", value=3.0),
    Row("rietx.schemas.indexing.PEAK_SATELLITE_MAX_RATIO", "constant", value=0.25),
    Row("rietx.schemas.indexing.PEAK_SATELLITE_NEAR_FWHM", "constant", value=1.5),
    Row("rietx.schemas.indexing.PEAK_SHOULDER_MIN_SIGMA", "constant", value=5.0),
    Row("rietx.schemas.indexing.PEAK_WIDTH_BOUND_FACTORS", "constant", value=(0.0001, 5.0)),
    Row("rietx.schemas.indexing.PEAK_WIDTH_CENSUS_N", "constant", value=12),
    Row("rietx.schemas.indexing.PEAK_WIDTH_SCALE_BOUNDS", "constant", value=(0.5, 50.0)),
    Row("rietx.schemas.indexing.PEAK_WINDOW_FWHM_MULT", "constant", value=4.0),
    Row("rietx.schemas.indexing.SHIFT_ALLOWANCE_K_ESD", "constant", value=3.0),
    Row("rietx.schemas.indexing.SMITH_VOLUME_C1", "constant", value=0.6),
    Row("rietx.schemas.indexing.SMITH_VOLUME_C2", "constant", value=0.0052),
    Row("rietx.schemas.instrument.BRAGG_BRENTANO_RADIUS_MM", "constant", tier=3, value=217.5,
        evidence=("no source stated; 217.5 mm is the Bruker D8 Advance's standard radius "
                  "(recalled); the bragg_brentano geometry refuses a missing radius, so the "
                  "preset's default exists to stop the refusal; only the specimen displacement reads "
                  "it, as s/R (model/corrections.py), so a wrong radius rescales the reported "
                  "displacement in mm and leaves the fit, the cell and Rwp unchanged; nothing "
                  "records it as assumed, which WP-2015 owes; bragg_brentano's signature "
                  "default until the B14 lift"),
        grounds=("The goniometer radius is a fact about the caller's instrument, outside the "
                 "pattern; kept as the preset's default (B9, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.instrument.DEBYE_SCHERRER_POLARIZATION", "constant", tier=3, value=0.99,
        evidence=("APS 11-BM instrument-parameter files (docstring, GSAS POLA convention), one "
                  "facility; a wrong K moved a refined Biso by 12 sigma (WP-1311 item 2); "
                  "debye_scherrer's signature default until the B14 lift"),
        grounds=("The beam's polarisation is a fact about the caller's instrument, outside the "
                 "pattern; 0.99 stays the preset's held value (B9, ruled 2026-10-19). B9 also "
                 "asked for it to be recorded as assumed; nothing writes that record yet, "
                 "and WP-2015 owes it (its task on the assumed instrument facts)."),
        approved="2026-10-19"),
    Row("rietx.schemas.instrument.EXTRA_PEAK_FWHM_MAX", "constant", tier=1, value=0.5,
        evidence=("arithmetic: the frozen evaluation window is k(eta.max) * fwhm.max + "
                  "WINDOW_MIN_DEG, so a finite max is what makes the windowed peak exact "
                  "(an infinite one is refused, PeakComponent._window_bounds_are_finite); "
                  "0.5 deg sets the default window near +-8 deg, a cost the caller resizes "
                  "by stating max")),
    Row("rietx.schemas.instrument.EXTRA_PEAK_FWHM_MIN", "constant", value=0.005),
    Row("rietx.schemas.instrument.HARMONIC_WEIGHT_SEED", "constant", tier=3, value=0.01,
        evidence=("answer-invariant behind the closing stage only (closing_window_tol=None "
                  "keeps the 0.15 esd it moved before): seeds 0.001 and 0.3 against 0.01 within "
                  "0.1 plain esd (at most 0.003) at true lambda/2 weights 0, 0.003 and 0.05, a "
                  "synthetic CW neutron corundum drawn by the package's own forward model, the "
                  "one family a harmonic has here (tests/test_staged_start_invariance.py, the "
                  "sixth round's Q2 bar)"),
        grounds=("The maintainer delegated this tier to the lead on 2026-10-23 ('use your best "
                 "judgement'), on the generality judge's reading that an answer-invariant claim "
                 "has no conditional form (MAGNETIC_SIZING_FLOOR's precedent): tier 3, with "
                 "WP-2017 measuring the start without the closing stage on three families."),
        approved="2026-10-23"),
    Row("rietx.schemas.instrument.HUMP_FWHM_MIN", "constant", value=0.1),
    Row("rietx.schemas.instrument.KA2_RATIO", "constant", tier=2, value=0.5,
        evidence=("GSAS-II 5.8.4's default lab instrument carries I(L2)/I(L1) = 0.5 "
                  "(defaultIparms.py:35, GSASIIpwd.py:5782; checked); the 2j+1 degeneracy ratio, "
                  "with measured integrated ratios a few percent above it (Hoelzer et al. 1997, "
                  "the B14 review's source) and a diffracted-beam monochromator clipping it; "
                  "lab_bragg_brentano refines it and mccusker_default holds it, a B9 assumption "
                  "whose record WP-2015 owes; the bragg_brentano and flat_plate_transmission signature default "
                  "until the B14 lift")),
    Row("rietx.schemas.instrument.PACKING_FRACTION", "constant", tier=3, value=0.6,
        evidence=("docstring: 0.3-0.6 typical for a tapped powder, 0.64 random close packing of "
                  "spheres; no measurement; GSAS-II 5.8.4's absorption calculator starts at 0.50 "
                  "(Absorb.py:89, checked in the batch); read only to estimate mu_r or mu_t from a "
                  "declared capillary radius or thickness; the Geometry field default and the "
                  "debye_scherrer and flat_plate_transmission signature default until the B14 "
                  "lift"),
        grounds=("The packing is a fact about the caller's specimen, read only by an estimate "
                 "the caller opts into by declaring a radius or a thickness; kept (B9, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.instrument.PSPLINE_LAMBDA_SMOOTH", "constant", tier=3, value=1.0,
        evidence=("WP-1454: derived (lambda = 1 suppresses features narrower than a knot "
                  "spacing); Rwp and Biso flat from 0.1 to 100 on IUCr CPD sample 2 and 11-BM "
                  "NAC; the BackgroundPSpline field default, BackgroundPSpline.for_range's "
                  "default and auto_background's literal until the B14 lift"),
        grounds=("On the default path, since the skill tells every agent to call "
                 "auto_background, which builds every P-spline at it (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.instrument.TCHZ_CEILING_DEG", "constant", tier=3, value=180.0,
        evidence=("the width of the 2theta axis (180 deg for X and Y, its square for U, V and W), "
                  "four orders over any measured line, so no fit reaches it; it exists for TRF, "
                  "which scales a step by a finite bound's distance and by 1 for an infinite one: "
                  "CPD brucite Stephens under TRF stopped at Rwp 0.17891, one S_HKL t = -203, "
                  "without it, and at 0.17878 with the pre-removal t values with it, the closing "
                  "stage off (one family); with the closing stage on, TRF collapses that fit "
                  "again (t = -268), so the Stephens suite declines it; none of the seven "
                  "programs bounds these widths, the reason named here; since "
                  "2026-10-23 its negative is also the U, V and Y floor, for the "
                  "same reason"),
        grounds=("A solver-path setting, held at tier 3 as B10's are until refits of three "
                 "families under TRF agree with and without it; kept on the maintainer's ruling "
                 "(the sixth round's Q7, (a), 2026-10-21)."),
        approved="2026-10-21"),
    Row("rietx.schemas.instrument._DIFC_MIN", "constant", tier=1, value=1.0,
        evidence=("physics: DIFC = (m_N/h)(L1+L2)2 sin(theta) is strictly positive; 1 us/A is three"
                  " orders under the smallest real bank (GEM bank 1, ~740)")),
    Row("rietx.schemas.instrument._WAVELENGTH_MIN_A", "constant", tier=1, value=0.001,
        evidence=("physics: lambda <= 0 puts every reflection at 2theta = 0; 1e-3 A is three orders"
                  " under any diffraction wavelength (docstring)")),
    Row("rietx.schemas.instrument._ZERO_BOUND", "constant", tier=1, value=1e-12,
        evidence=("numerical floor: 1e-12 is the value under which a stored min meant no bound "
                  "before schema 0.46 (docstring)")),
    Row("rietx.schemas.interval.PARAMETER_INTERVAL_BRACKET_GROWTH", "constant", tier=3,
        value=2.0,
        evidence=("no stated source; doubling from one esd; where window recompiles give a "
                  "profile several crossings the growth can choose which one the bracket holds "
                  "(the generality judge, 2026-10-23); fit and run_stage call profile_interval "
                  "for every moment angle the stationary test leaves out (B2 option 2); inline "
                  "in _walk until the B14 lift"),
        grounds=("A numerical setting of the profile walk, on the default path since B2 "
                 "option 2; tier 3 with a test bounding its error over the claimed domain "
                 "owed (WP-2017), tier 1 once it passes (B10 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.interval.PARAMETER_INTERVAL_CHI2_TOL", "constant", tier=3, value=0.01,
        evidence=("fit and run_stage call profile_interval for every moment angle the "
                  "stationary test leaves out (B2 option 2, 2026-10-19), 20-32 refits an angle on the "
                  "two-site Pnma fixtures"),
        grounds=("A numerical setting of the profile walk, on the default path since B2 "
                 "option 2; tier 3 with a test bounding its error over the claimed domain "
                 "owed, tier 1 once it passes (B10 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.interval.PARAMETER_INTERVAL_LEVEL", "constant", tier=2, value=0.95,
        evidence=("Venzon & Moolgavkar (1988) Appl. Statist. 37, 87 for the interval; 95 % is the "
                  "conventional level and the caller's argument (docstring)")),
    Row("rietx.schemas.interval.PARAMETER_INTERVAL_MAX_REFITS", "constant", tier=3, value=60,
        evidence=("fit and run_stage call profile_interval for every moment angle the "
                  "stationary test leaves out (B2 option 2, 2026-10-19), 20-32 refits an angle on the "
                  "two-site Pnma fixtures"),
        grounds=("A numerical setting of the profile walk, on the default path since B2 "
                 "option 2; tier 3 with a test bounding its error over the claimed domain "
                 "owed, tier 1 once it passes (B10 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.interval.PARAMETER_INTERVAL_SETTLE_RUNS", "constant", tier=3, value=4,
        evidence=("fit and run_stage call profile_interval for every moment angle the "
                  "stationary test leaves out (B2 option 2, 2026-10-19), 20-32 refits an angle on the "
                  "two-site Pnma fixtures"),
        grounds=("A numerical setting of the profile walk, on the default path since B2 "
                 "option 2; tier 3 with a test bounding its error over the claimed domain "
                 "owed, tier 1 once it passes (B10 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.interval.PARAMETER_INTERVAL_XTOL", "constant", tier=3, value=0.001,
        evidence=("fit and run_stage call profile_interval for every moment angle the "
                  "stationary test leaves out (B2 option 2, 2026-10-19), 20-32 refits an angle on the "
                  "two-site Pnma fixtures"),
        grounds=("A numerical setting of the profile walk, on the default path since B2 "
                 "option 2; tier 3 with a test bounding its error over the claimed domain "
                 "owed, tier 1 once it passes (B10 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.pattern.POISSON_FLOOR_COUNTS", "constant", tier=2, value=1.0,
        evidence=("TOPAS weights a file without esds by 1/Max(Yobs, 1) (Technical Reference "
                  "section 6.2, docs/wp/2002-batch/rulings.md B5); GSAS-II 5.8.4's xye reader "
                  "gives w = 0 at y <= 0 instead (imports/G2pwd_xye.py:172-185, checked); one "
                  "rule for PatternData.sig, RefinementResult.sig, background.diagnostics and "
                  "io.formats.base.sigma_from_scaled, four literals until the B14 lift")),
    Row("rietx.schemas.pattern.SIGMA_FLOOR_RELATIVE", "constant", tier=3, value=0.001,
        evidence=("#650 (relative floor) and WP-1952's inherited note (#897): a zero esd then "
                  "weighs ~1e6x its neighbours; no source for the 1e-3; inline in _floor_sigma "
                  "until the B14 lift"),
        grounds=("Kept until WP-1952 replaces it: a channel with sigma <= 0 takes no weight by "
                 "default, the reader warns with the count and the lines, and a reader option "
                 "keeps such channels at one count (B5, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.plan.CLOSING_WINDOW_TOL", "constant", tier=1, value=0.001,
        evidence=("numerical setting with a domain test (tests/test_window_domain.py, "
                  "test_the_closing_stage_meets_the_bar): its windows are within 0.1 sigma of "
                  "5e-5's at every point on SRM 660c, FAP, cpd-1a and 11-BM NAC (0.022-0.091), "
                  "and the closing answer within 0.1 plain esd of the 5e-5 fixed point on FAP, "
                  "cpd-1a and NAC (0.008-0.019); LaB6 misses that by 0.908 esd on U from the "
                  "Gaussian-variance clamp, which moves U at any window (WP-1467); 1.05-2.05x the "
                  "fit time (WP-2002, the sixth round's Q1 and Q2)")),
    Row("rietx.schemas.plan.CORRELATION_GUARD", "constant", value=0.98),
    Row("rietx.schemas.plan.INTERMEDIATE_FTOL", "constant", tier=3, value=1e-06,
        evidence=("behind the closing stage, 1e-6 against every stage at 1e-9 within 0.1 plain "
                  "esd on SRM 660c, FAP, cpd-1a and 11-BM NAC (0.000, 0.000, 0.042, 0.000; "
                  "tests/test_staged_start_invariance.py); fails on cpd-1a with an absent zircon "
                  "declared, 0.185 esd on fluorite a, where at 1e-9 the unseen zircon's cell "
                  "walks to the stage budget (STAGE_MAX_ITER) before the closing stage holds it, "
                  "a strict xfail; 1.00-2.15x fewer evaluations (WP-1113/1123)"),
        grounds=("A schedule rietx chose (WP-1123); kept on four families with its failing case "
                 "stated, where the alternative is the arm that runs out of budget (the sixth "
                 "round's Q2, bar 0.1 plain esd, ruled 2026-10-21)."),
        approved="2026-10-21"),
    Row("rietx.schemas.plan.PHASE_SUPPORT_SIGMA", "constant", tier=3, value=3.0,
        evidence=("WP-1523: 3 sigma, = indexing ABSENT_SIGMA by test; 20 blank fits read 1 phase "
                  "seen, 9 at the old 1 sigma; fails on a real phase at ~1/16 000 of a strong "
                  "one's scale, seen in 1 fit of 8; own fixtures only; second pass owed (a weighed "
                  "phase at 0.1-1 wt %, a minor phase started one FWHM off its cell)"),
        grounds=("The hold it gates passes the judgement ground; the 3 sigma is rietx's own, "
                 "which Currie (1968) does not carry; kept at its value as the default of a "
                 "caller's option, PlanSpec.phase_support_sigma with None for off (B1, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.results.HIGH_CORRELATION_MAX", "constant", value=10),
    Row("rietx.schemas.structure.BISO_SEED", "constant", tier=3, value=0.5,
        evidence=("starts 0.5 and 1.5 within 0.1 plain esd behind the closing stage on FAP and "
                  "11-BM NAC (0.000, 0.000; tests/test_staged_start_invariance.py); cpd-1a 0.070 "
                  "until the width twin hold kept a start-dependent X/Y split, 15.68 on zincite's "
                  "lor_strain since (WP-2002, a strict xfail); LaB6's two starts land in its "
                  "mirrored axial minima (1.16 esd, 9.36 before WP-2002; WP-2012), a strict "
                  "xfail; the Atom.biso "
                  "default and the literal of three readers for a site with no ADP "
                  "(crystallography/cif.py, io/recipe.py, io/projects/topas.py) until the B14 "
                  "lift"),
        grounds=("The maintainer delegated this tier to the lead on 2026-10-23 ('use your best "
                 "judgement'), on the generality judge's reading that an answer-invariant claim "
                 "has no conditional form (MAGNETIC_SIZING_FLOOR's precedent): tier 3, with "
                 "WP-2017 measuring the start without the closing stage on three families."),
        approved="2026-10-23"),
    Row("rietx.schemas.structure.MARCH_R_MIN", "constant", tier=1, value=1e-06,
        evidence=("arithmetic: the March factor (r^2 cos^2 a + sin^2 a / r)^(-3/2) divides by "
                  "r, a pole at 0; at 1e-6 the factor (<= 1e18) and its r-derivative "
                  "(<= 3e24) are finite at every angle (test_robustness_external.py); "
                  "lowered from 0.15, an Rwp-chosen floor, by the B9 ruling 2026-10-19")),
    Row("rietx.schemas.structure.MOMENT_FLOOR_MU_B", "constant", tier=3, value=0.001,
        evidence=("WP-1327: 1e-3 muB, three orders under the smallest resolvable ordered moment; "
                  "NIST BT-1 LaMnO3 and HB-2A Cr2WO6 only; read by solve_magnetic, sequential's "
                  "reseed and the magnetic report, and no single-fit code holds at it (batch "
                  "appendix 11)"),
        grounds=("Rare feature: a modulus at 1e-3 muB has no direction and a vanishing column, so "
                 "every refiner treats it as absent; kept at the measured value, untested beyond "
                 "two neutron families (B2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.structure.RIGID_BODY_DRIFT_TOL", "constant", tier=1, value=1e-06,
        evidence=("numerical floor: roundoff drift measured at <= 1e-14 A, tolerance 1e-6 A "
                  "(docstring); refusing at it protects against a hand-edited body atom")),
    Row("rietx.schemas.structure.RIGID_BODY_ROTATION_BOUND", "constant", tier=1, value=3.141592653589793,
        evidence=("arithmetic: the increment's Jacobian is singular only at |d omega| = 2 pi; +-pi "
                  "per component keeps |d omega| <= pi*sqrt(3) < 2 pi (docstring, WP-1803 review)")),
    Row("rietx.schemas.structure._ZERO_BOUND", "constant", tier=1, value=1e-12,
        evidence=("numerical floor: 1e-12 is the value under which a stored min meant no bound "
                  "before schema 0.46 (docstring)")),
    Row("rietx.schemas.suggest.SUGGEST_ABSORPTION_MAX", "constant", value=0.95),
    Row("rietx.schemas.suggest.SUGGEST_GROUP_R2", "constant", value=0.95),
    Row("rietx.schemas.suggest.SUGGEST_MIN_GAIN", "constant", value=9.0),
    Row("rietx.sequential.DISCONTINUITY_FACTOR", "constant", value=5.0),
    Row("rietx.sequential.DISCONTINUITY_SIGMA", "constant", value=3.0),
    Row("rietx.sequential.FIRST_RUNG_FACTOR", "constant", value=3.0),
    Row("rietx.sequential.FIRST_RUNG_SAMPLES", "constant", value=3),
    Row("rietx.sequential.MIN_POINTS_FOR_DISCONTINUITY", "constant", value=5),
    Row("rietx.sequential.MIN_POINTS_FOR_PERSISTENCE", "constant", value=5),
    Row("rietx.sequential.NOISE_FLOOR_REL", "constant", value=1e-09),
    Row("rietx.sequential.PATH_DEPENDENCE_SIGMA", "constant", value=3.0),
    Row("rietx.sequential.RESEED_FACTOR", "constant", value=1.25),
    Row("rietx.sequential.WIDTH_GROWTH_FACTOR", "constant", value=3.0),
    Row("rietx.sequential.WIDTH_GROWTH_GOF_FACTOR", "constant", value=2.0),
    Row("rietx.sequential.WIDTH_GROWTH_SIGMA", "constant", value=3.0),
    Row("rietx.solve.cost.NAMED_REFLECTIONS", "constant", value=5),
    Row("rietx.solve.cost.NUISANCE_RCOND", "constant", value=1e-12),
    Row("rietx.strategy.magnetic.SOLVE_D_MIN", "constant", value=1.5),
    Row("rietx.strategy.magnetic.SOLVE_K_OFFSET_MARGIN_DEG", "constant", tier=3, value=0.5,
        evidence=("magnetic.py docstring: the Ba2FeSbSe5 pair sits 0.081 deg apart, inside 0.5 deg "
                  "by 6x; one family"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; kept at the measured value, untested beyond its one family (B12, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_K_TIE_DELTA_BIC", "constant", tier=3, value=10.0,
        evidence=("Kass & Raftery (1995) J. Am. Stat. Assoc. 90, 773: 2 ln B > 10 'very strong' "
                  "(recalled; the docstring gives a rationale, not the cite); applied at N/f² "
                  "since WP-2002 B12; no family measures the gap between two k"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; the Kass-Raftery band is cited, the N/f² count it is applied "
                 "to is rietx's own, so the row stays tier 3 (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_K_TRIALS", "constant", tier=3, value=2,
        evidence=("magnetic.py docstring: Ba2FeSbSe5 1.5 K (Phys. Rev. B 103, 054115; not "
                  "vendored), two k index the same 11 peaks and intensity separates them; one "
                  "family"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; kept at the measured value, untested beyond its one family (B12, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_MAX_CONTINUATIONS", "constant", tier=3, value=10,
        evidence=("review of #592: Cr2WO6 150 K (HB-2A) needed 5 continuations for the reference "
                  "and 3 and 7 for the classes under TRF's 400-evaluation stops; 1.4x margin, one "
                  "family"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; kept at the measured value, untested beyond its one family (B12, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_MINIMUM_RTOL", "constant", tier=3, value=0.0001,
        evidence=("WP-1327: no stated source, never measured; gates the reported n_minima count, "
                  "not the pick"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; kept at its value, which no family measured (B12, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_RELEASE_FRACTION", "constant", tier=3, value=0.05,
        evidence=("WP-1327: Ba6Co6 (GSAS-II Magnetic-III tutorial, not vendored), released from "
                  "the one-site leg: Rwp 0.08752 (the published answer) against 0.08952 flat; one "
                  "family"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; kept at the measured value, untested beyond its one family (B12, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_SEED_MU_B", "constant", tier=3, value=2.0,
        evidence=("WP-1327: four in-plane seed directions on Cr2WO6 4 K (HB-2A) reach one answer; "
                  "the 2 muB modulus itself unmeasured; one family"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; kept at the measured value, untested beyond its one family (B12, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_SEED_TILT", "constant", tier=3, value=0.02,
        evidence=("alias of crystallography.magnetic.moments.SEED_TILT (WP-2006's row takes the "
                  "same tier): WP-1418, 20 simulated MAGNDATA structures; 0.15 lost 2 exact "
                  "recoveries, 0.02 none"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; kept at the measured value, untested beyond its one family (B12, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_TIE_DELTA_BIC", "constant", tier=3, value=6.0,
        evidence=("Kass & Raftery (1995) J. Am. Stat. Assoc. 90, 773: 2 ln B 6-10 'strong' "
                  "(docstring); at N/f² (WP-2002 B12) the winner's lead is 143 on Cr2WO6 4 K "
                  "(HB-2A, f 3.38) and 164 on LaMnO3 50 K (BT-1, f 3.22), 1682 and 1704 at raw "
                  "N, verdicts unchanged; Cr2WO6 150 K nothing to solve either way; a ΔBIC tie "
                  "no longer falls to R_mag"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; the Kass-Raftery band is cited, the N/f² count it is applied "
                 "to is rietx's own, so the row stays tier 3 (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.magnetic.SOLVE_TOP_K", "constant", tier=3, value=3,
        evidence=("WP-1326/1418: no stated source, never measured; changes the answer only if a "
                  "fourth k would win"),
        grounds=("Rare feature inside solve_magnetic, a pick verb whose whole ranking travels "
                 "with the pick; kept at its value, which no family measured (B12, ruled "
                 "2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.staged.BACKGROUND_ABSORPTION_GUARD", "constant", value=0.25),
    Row("rietx.strategy.staged.BOUND_HIT_COS_MIN", "constant", tier=3, value=0.0001,
        evidence=("WP-1434: |cos| 1.5e-2 to 2.1e-1 over the 32 binding cases against 5.0e-10 at a "
                  "free optimum, 1e-4 sits 145x and 2e5x inside; FAP, Si SRM 640c, make_lab6; "
                  "second pass owed (a third family under TRF)"),
        grounds=("Reports only, through BOUND_HIT, FLOOR_HIT and at_bound; with f kept on the esd "
                 "(B4) the margins stand as measured (B16, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.staged.BOUND_HIT_ESD_FRAC", "constant", tier=3, value=0.01,
        evidence=("WP-1434: 32 binding cases on FAP and Si SRM 640c, ftol 1e-9 to 1e-3: largest "
                  "binding gap 7.7e-4 esd, early stop 2.36 esd (make_lab6 synthetic), margins 13x "
                  "and 236x with f in the esd; read off LM's exact active set only beyond it; "
                  "second pass owed (a third family under TRF)"),
        grounds=("Reports only, through BOUND_HIT, FLOOR_HIT and at_bound; with f kept on the esd "
                 "(B4) the margins stand as measured (B16, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.strategy.staged.BOUND_HIT_RTOL", "constant", tier=1, value=1e-10,
        evidence=("numerical floor: scipy TRF's own active-set rtol and make_strictly_feasible "
                  "rstep, both 1e-10 (_lsq/common.py:401, 440, checked)")),
    Row("rietx.strategy.staged.FLAT_DIRECTION_RHO", "constant", tier=1, value=0.9995,
        evidence=("arithmetic: 1 − 5e-4 is the half-width of ρ's three-decimal rendering, so the "
                  "finding claims only '1.000 as printed' (WP-1311)")),
    Row("rietx.strategy.staged.HUMP_MIN_WIDTH_MULT", "constant", value=4.0),
    Row("rietx.strategy.staged.LINDEMANN_RHO", "constant", tier=2, value=0.105,
        evidence=("Gilvarry (1956) Phys. Rev. 102, 308, eq 8: the loosest of the paper's four "
                  "ratios (docstring)")),
    Row("rietx.strategy.staged.RESOLUTION_CONE_TOL", "constant", tier=1, value=1e-09,
        evidence="numerical floor: same association-order argument as STEPHENS_CONE_TOL"),
    Row("rietx.strategy.staged.ROUGHNESS_ABSORPTION_GUARD", "constant", value=0.9),
    Row("rietx.strategy.staged.ROUGHNESS_SEED", "constant", tier=3, value=0.3,
        evidence=("_ROUGHNESS_STAGE's seed, recorded per model on StageResult.seeded. Suortti's "
                  "b: start-invariant from 0.3 and 0 on five lab patterns from three families "
                  "(NIST LaB6, GSAS-II FAP, CPD corundum, fluorite, zincite), every Biso, scale "
                  "and b within 2.7e-3 of the smaller esd (tests/test_seed_invariance.py). "
                  "Pitschke's c: not start-invariant, from 0 CPD zincite lands in the turned-over "
                  "regime (scale x2.1, ROUGHNESS_OUTSIDE_REGIME) and corundum's Biso moves 0.26 "
                  "esd; no program supplies a Pitschke start (FullProf's examples start at "
                  "1.2-1.5; docs/practice.md); suggest.SUGGEST_SEED_ROUGHNESS and "
                  "viz.compare's two roughness variants take it by reference since the B14 lift"),
        grounds=("Suortti's start is answer-invariant and Pitschke's is kept at 0.3 because "
                 "from 0.3 the fit reaches the switched-off branch inside the model's valid "
                 "range, while from 0 the lower chi2 is one the model flags as invalid (the "
                 "sixth round's Q3, ruled (c) 2026-10-21: one number in the code, the two models "
                 "recorded apart)."),
        approved="2026-10-21"),
    Row("rietx.strategy.staged.STEPHENS_CONE_TOL", "constant", tier=1, value=1e-09,
        evidence=("numerical floor: absorbs last-bit disagreement between the solver's and the "
                  "guard's association orders; ~6 decades above fp64 noise")),
    Row("rietx.strategy.staged.STRAIN_SEED_PPM", "constant", tier=3, value=1000.0,
        evidence=("lab_sample_refine's strain_seed, 1000 ppm on the isotropic ray: GSAS-II "
                  "5.8.4's isotropic microstrain default, its generalised start 0.01 each "
                  "(GSASIIddataGUI.py:180-190, :1432; checked); WP-1467, one pattern: chi2 1.160 "
                  "from 1000 ppm against 1.482 from the previous stage's strain. Second family, "
                  "2026-10-20 (tests/test_acceptance_stephens.py's plan): CPD brucite chi2 7.7662 "
                  "from 1000 ppm against 8.3241 from the isotropic value; CPD corundum both starts "
                  "equal to 2e-10; suggest.SUGGEST_SEED_STEPHENS and viz.compare's Stephens "
                  "variant take it by reference since the B14 lift"),
        grounds=("Some start is forced, since the width's square root has unbounded slope at "
                 "zero; kept at 1000 ppm until a second dataset compares the starts (B3, ruled "
                 "2026-10-19); the second compared them on 2026-10-20 and favoured 1000 ppm."),
        approved="2026-10-19"),
    Row("rietx.strategy.suggest.SUGGEST_SEED_ROUGHNESS", "constant", value=0.3),
    Row("rietx.strategy.suggest.SUGGEST_SEED_STEPHENS", "constant", tier=3, value=1000.0,
        evidence=("= strategy.staged.STRAIN_SEED_PPM by reference (B14 lift), 1000 ppm on the "
                  "isotropic ray: GSAS-II "
                  "5.8.4's isotropic microstrain default, its generalised start 0.01 each "
                  "(GSASIIddataGUI.py:180-190, :1432; checked); WP-1467, one pattern: chi2 1.160 "
                  "from 1000 ppm against 1.482 from the previous stage's strain. Second family, "
                  "2026-10-20 (tests/test_acceptance_stephens.py's plan): CPD brucite, whose "
                  "isotropic strain folds to 0.35 ppm, chi2 7.7662 from 1000 ppm (800 ppm the "
                  "same to 0.01 esd) against 8.3241 from the isotropic value, the block left at "
                  "the singularity; CPD corundum (903 ppm) both starts equal to 2e-10. So 1000 "
                  "ppm reached the lower or equal minimum in all three comparisons; brucite "
                  "tests only a near-zero start, and these are the plan's solve seed: the "
                  "suggestion probe's own start is unmeasured, as SUGGEST_SEED_ROUGHNESS's is"),
        grounds=("Some start is forced, since the width's square root has unbounded slope at "
                 "zero; kept at 1000 ppm until a second dataset compares the starts (B3, ruled "
                 "2026-10-19); the second compared them on 2026-10-20 and favoured 1000 ppm."),
        approved="2026-10-19"),
    # default: 117
    Row("rietx.schemas.instrument.ProfileTCHZ:shape", "default", tier=2, ambiguity=2, value="tchz_pv",
        evidence=("GSAS-II 5.8.4's constant-wavelength peak is the Thompson, Cox & Hastings (1987) "
                  "pseudo-Voigt with the FCJ asymmetry (GSASIIpwd.getFWHM :916, getFCJVoigt3 "
                  ":1316; checked); 'voigt' is the opt-in true Voigt")),
    Row("rietx.schemas.instrument.ProfileTCHZ:u", "default", tier=3, ambiguity=1, value={"value": 0.0, "vary": False, "min": -32400.0, "max": 32400.0, "expr": None, "unit": "deg^2", "stderr": None},
        evidence=("TCHZ_DEFAULTS' seed 0 and TCHZ_BOUNDS' box, dicts the constant walk cannot see; the "
                  "seed is start-invariant for a freed width (tests/test_seed_invariance.py, LaB6, CPD "
                  "and 11-BM NAC within 1.3e-4 esd) and is the held value of an uncalibrated one; the "
                  "ceiling is TCHZ_CEILING_DEG squared; no per-coefficient floor: a finite bound at "
                  "-180^2 deg^2 (TCHZ_CEILING_DEG squared, the ceiling's mirror image) no width "
                  "reaches, kept finite for TRF's step scaling; the physical condition is held as "
                  "Gamma_G^2 >= eps by LM (optimize.least_squares.gaussian_width_inequalities), guarded "
                  "under TRF by RESOLUTION_NOT_POSITIVE; GSAS-II 5.8.4 and FullProf bound none of U, V, "
                  "W, X, Y (docs/wp/2002-batch/rulings.md, fourth round); the walk along its specimen "
                  "twin, which the floor bounded, is held instead (StageResult.width_twins_held)"),
        grounds=("The floor went on the maintainer's ruling of 2026-10-23 ('remove the per-coefficient "
                 "floors'; B9, no chosen limit on a quantity that stays physical); the far bound and "
                 "the ceiling are TCHZ_CEILING_DEG's (the sixth round's Q7, ruled 2026-10-21)."),
        approved="2026-10-23"),
    Row("rietx.schemas.instrument.ProfileTCHZ:v", "default", tier=3, ambiguity=1, value={"value": 0.0, "vary": False, "min": -32400.0, "max": 32400.0, "expr": None, "unit": "deg^2", "stderr": None},
        evidence=("TCHZ_DEFAULTS' seed 0 and TCHZ_BOUNDS' box, as ProfileTCHZ:u; the public D1B Co3O4 "
                  "model's V = -0.501, under the old X-ray floor of -0.5, now builds on every preset, "
                  "which retired TCHZ_BOUNDS_COARSE; no per-coefficient floor: a finite bound at -180^2 "
                  "deg^2 (TCHZ_CEILING_DEG squared, the ceiling's mirror image) no width reaches, kept "
                  "finite for TRF's step scaling; the physical condition is held as Gamma_G^2 >= eps by "
                  "LM (optimize.least_squares.gaussian_width_inequalities), guarded under TRF by "
                  "RESOLUTION_NOT_POSITIVE; GSAS-II 5.8.4 and FullProf bound none of U, V, W, X, Y "
                  "(docs/wp/2002-batch/rulings.md, fourth round)"),
        grounds=("The floor went on the maintainer's ruling of 2026-10-23 ('remove the per-coefficient "
                 "floors'; B9, no chosen limit on a quantity that stays physical); the far bound and "
                 "the ceiling are TCHZ_CEILING_DEG's (the sixth round's Q7, ruled 2026-10-21)."),
        approved="2026-10-23"),
    Row("rietx.schemas.instrument.ProfileTCHZ:w", "default", tier=3, ambiguity=1, value={"value": 0.001, "vary": False, "min": 1e-08, "max": 32400.0, "expr": None, "unit": "deg^2", "stderr": None},
        evidence=("TCHZ_DEFAULTS' seed 1e-3 deg^2, start-invariant for a freed width from 1e-6 "
                  "to 1.0 on LaB6 (tests/test_seed_invariance.py), a start too wide losing NAC's "
                  "phase at w = x = 1e-2; the floor is caglioti._MIN_GAMMA_G2 and the ceiling "
                  "TCHZ_CEILING_DEG squared, each tiered on its own row"),
        grounds=("Its floor and ceiling are tier 3 on their own rows (_MIN_GAMMA_G2 under B10; "
                 "TCHZ_CEILING_DEG, the sixth round's Q7, ruled 2026-10-21); the seed is "
                 "start-invariant on the side the default sits on."),
        approved="2026-10-21"),
    Row("rietx.schemas.instrument.ProfileTCHZ:x", "default", tier=3, ambiguity=1, value={"value": 0.001, "vary": False, "min": 0.0, "max": 180.0, "expr": None, "unit": "deg", "stderr": None},
        evidence=("TCHZ_DEFAULTS' seed 1e-3 deg: start-invariant on LaB6 except starts at x = "
                  "0.02-0.03, which land 0.38 esd away in u on a mirrored S/L-H/L minimum (WP-2012); "
                  "FAP's GSAS protocol holds x at it, and x = 0 instead moves lor_size 0.69 esd at "
                  "equal chi2 (tests/test_seed_invariance.py); the floor 0 is physical, kept when U, V "
                  "and Y lost theirs: at theta -> 0 the tan term vanishes and the instrument's "
                  "Lorentzian FWHM is X itself; the ceiling TCHZ_CEILING_DEG; GSAS-II 5.8.4 and "
                  "FullProf bound none of U, V, W, X, Y (docs/wp/2002-batch/rulings.md, fourth round)"),
        grounds=("Its ceiling is TCHZ_CEILING_DEG's (the sixth round's Q7, ruled 2026-10-21); its "
                 "floor is a width's own, which the ruling of 2026-10-23 kept."),
        approved="2026-10-23"),
    Row("rietx.schemas.instrument.ProfileTCHZ:y", "default", tier=3, ambiguity=1, value={"value": 0.0, "vary": False, "min": -180.0, "max": 180.0, "expr": None, "unit": "deg", "stderr": None},
        evidence=("TCHZ_DEFAULTS' seed 0, start-invariant for a freed width "
                  "(tests/test_seed_invariance.py); the ceiling TCHZ_CEILING_DEG; a negative Y is "
                  "physical as a coefficient: a constant positive Lorentzian width projected onto "
                  "{1/cos, tan} over 18-120 deg 2theta is X = 1.20, Y = -0.73 (WP-2002 9th session), "
                  "so Y >= 0 would refuse a real instrument; cost measured on tests/test_v02_core.py's "
                  "synthetic calibration, whose truth Y = 0 sat on the old floor: Y -0.0059, X 58 % "
                  "high, sample lor_size 55 % low against 27-39 %, HIGH_CORRELATION raised; no "
                  "per-coefficient floor: a finite bound at -180 deg (TCHZ_CEILING_DEG, the ceiling's mirror image) no "
                  "width reaches, kept finite for TRF's step scaling; the physical condition is held as "
                  "Gamma_L >= 0 by LM (optimize.least_squares.lorentzian_width_inequalities), guarded "
                  "under TRF by RESOLUTION_NOT_POSITIVE; GSAS-II 5.8.4 and FullProf bound none of U, V, "
                  "W, X, Y (docs/wp/2002-batch/rulings.md, fourth round); the walk along its specimen "
                  "twin, which the floor bounded, is held instead (StageResult.width_twins_held)"),
        grounds=("The floor went on the maintainer's ruling of 2026-10-23 ('remove the per-coefficient "
                 "floors'; B9, no chosen limit on a quantity that stays physical); the far bound and "
                 "the ceiling are TCHZ_CEILING_DEG's (the sixth round's Q7, ruled 2026-10-21)."),
        approved="2026-10-23"),
    Row("rietx.schemas.plan.PlanSpec:stages", "default", tier=1, ambiguity=1, value=(),
        evidence="arithmetic: the empty container; resolve_plan supplies every plan a fit runs"),
    Row("rietx.schemas.plan.PlanSpec:correlation_guard", "default", value=0.98),
    Row("rietx.schemas.plan.PlanSpec:intermediate_ftol", "default", tier=3, ambiguity=1, value=1e-06,
        evidence=("behind the closing stage, 1e-6 against every stage at 1e-9 within 0.1 plain "
                  "esd on SRM 660c, FAP, cpd-1a and 11-BM NAC (0.000, 0.000, 0.042, 0.000; "
                  "tests/test_staged_start_invariance.py); fails on cpd-1a with an absent zircon "
                  "declared, 0.185 esd on fluorite a, where at 1e-9 the unseen zircon's cell "
                  "walks to the stage budget (STAGE_MAX_ITER) before the closing stage holds it, "
                  "a strict xfail; 1.00-2.15x fewer evaluations (WP-1113/1123)"),
        grounds=("A schedule rietx chose (WP-1123); kept on four families with its failing case "
                 "stated, where the alternative is the arm that runs out of budget (the sixth "
                 "round's Q2, bar 0.1 plain esd, ruled 2026-10-21)."),
        approved="2026-10-21"),
    Row("rietx.schemas.plan.PlanSpec:closing_window_tol", "default", tier=2, ambiguity=1, value=0.001,
        evidence=("BGMN ends every refinement ladder with a closing run, all free and restarted "
                  "from the answer, by default (manual A.4; Doebelin & Kleeberg 2015 J. Appl. "
                  "Cryst. 48, 1573, 2); RIETAN-FP's NAUTO = 2 ends with everything refining "
                  "together, its windows moving each evaluation; MAUD's wizard has no final "
                  "cycle, but its windows also move every evaluation, so the window error the "
                  "stage removes never arises there (docs/practice.md); the value "
                  "is CLOSING_WINDOW_TOL's row; SRM 660c's cell 4.1568823 A without it and "
                  "4.1568821 with it, +24.6 ppm from the reference both ways; it fails twice: on "
                  "SRM 660c one closing solve sits 0.908 esd from the fixed point in u (the "
                  "Gaussian clamp, WP-1467), and under TRF it collapses CPD brucite's S_HKL "
                  "(t = -268); recorded in RefinementResult.stages as the stage named "
                  "'closing'; solve_magnetic runs it on its winner too, when the package "
                  "chose the plan and the verdict is solved, after ranking every trial "
                  "without it (2026-10-22)"),
        grounds=("The maintainer's ruling (the sixth round's Q2, option 3, 2026-10-21): every "
                 "plan ends with a closing stage at tight windows, which removes the 2 % "
                 "window's error from the answer and most of a staged plan's start dependence; "
                 "None runs the declared stages alone, bit-identical to before.")),
    Row("rietx.schemas.plan.PlanSpec:lebail_passes", "default", tier="caller", ambiguity=1, value=1,
        evidence="opt-in: lebail_passes > 1, default 1 (one run, bit-identical to pre-WP-1323)"),
    Row("rietx.schemas.plan.PlanSpec:phase_support_sigma", "default", tier=3, ambiguity=1, value=3.0,
        evidence=("WP-1523: 3 sigma, = indexing ABSENT_SIGMA by test; 20 blank fits read 1 phase "
                  "seen, 9 at the old 1 sigma; fails on a real phase at ~1/16 000 of a strong "
                  "one's scale, seen in 1 fit of 8; own fixtures only; second pass owed (a weighed "
                  "phase at 0.1-1 wt %, a minor phase started one FWHM off its cell)"),
        grounds=("On by default: the hold touches only parameters the data cannot determine, "
                 "and an unseen phase's free cell walked 14.9 A from the truth while Rwp did "
                 "not move; no other code holds by default (TOPAS's Remove_Phase is opt-in), "
                 "so the 3 sigma is rietx's own, a caller sets another or None for off (B1, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.plan.StageSpec:turn_on", "default", tier=1, ambiguity=1, value=(),
        evidence="arithmetic: the empty container"),
    Row("rietx.schemas.plan.StageSpec:max_iter", "default", tier="invariant", ambiguity=1, value=100,
        evidence=("answer-invariant: caps evaluations at max_iter x NFEV_PER_ITERATION, "
                  "never iterations; the worst stage under the shipped schedule ran 48 "
                  "iterations (2.1x, reported, not asserted) and 49 evaluations (8.2x); tests/test_budget_and_tolerance_invariance.py "
                  "asserts a bit-identical answer at max_iter 25 under LM and TRF, on the shipped "
                  "schedule; B7's ruling triggers a re-measure (WP-2002, 2026-10-21)"),
        grounds=("B11 (ruled 2026-10-19): a budget is treated as not affecting the answer "
                 "once a test confirms its margin under both LM and TRF."),
        approved="2026-10-19"),
    Row("rietx.schemas.plan.StageSpec:ftol", "default", tier=3, ambiguity=1, value=None,
        evidence=("behind the closing stage, 1e-6 against every stage at 1e-9 within 0.1 plain "
                  "esd on SRM 660c, FAP, cpd-1a and 11-BM NAC (0.000, 0.000, 0.042, 0.000; "
                  "tests/test_staged_start_invariance.py); fails on cpd-1a with an absent zircon "
                  "declared, 0.185 esd on fluorite a, where at 1e-9 the unseen zircon's cell "
                  "walks to the stage budget (STAGE_MAX_ITER) before the closing stage holds it, "
                  "a strict xfail; 1.00-2.15x fewer evaluations (WP-1113/1123)"),
        grounds=("A schedule rietx chose (WP-1123); kept on four families with its failing case "
                 "stated, where the alternative is the arm that runs out of budget (the sixth "
                 "round's Q2, bar 0.1 plain esd, ruled 2026-10-21)."),
        approved="2026-10-21"),
    Row("rietx.schemas.plan.StageSpec:lebail_cycles", "default", tier=3, ambiguity=1, value=3,
        evidence=("no stated source; issue #740 (synthetic LaMnO3-like neutron, cell and profile "
                  "at truth): Rwp 4.56 % at 3 cycles, 1.62 % at 100-400, 1.09 % for the true "
                  "structure; GSAS-II's DoLeBail runs 10 (GSASIIstrMain.py:761, checked); changed "
                  "by WP-1542 (converge with a cap)"),
        grounds=("Kept at 3 until WP-1542 replaces it with a stop once the intensities stop "
                 "changing, under a cap; #740 is its stated failure (B11, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.plan.StageSpec:seed", "default", tier="caller", ambiguity=1, value=0.0,
        evidence=("opt-in: Stage.seed > 0, default 0; the one shipped seed is "
                  "strategy.staged.ROUGHNESS_SEED's 0.3")),
    Row("rietx.schemas.plan.StageSpec:strain_seed", "default", tier="caller", ambiguity=1, value=0.0,
        evidence=("opt-in: Stage.strain_seed > 0, default 0; the one shipped value is "
                  "strategy.staged.STRAIN_SEED_PPM's 1000 ppm")),
    Row("rietx.schemas.plan.StageSpec:restraint_weight_scale", "default", tier=1, ambiguity=1, value=1.0,
        evidence=("arithmetic: c_w = 1 is the identity, every restraint at the σ its caller "
                  "declared (bit-identical to pre-WP-1074)")),
    Row("rietx.schemas.plan.StageSpec:window_slack_deg", "default", tier=3, ambiguity=1, value=None,
        evidence=("None resolves to WINDOW_MIN_DEG and compiles bit-identical windows and pattern "
                  "(tests/test_window_domain.py), so it inherits that row's tier"),
        grounds=("A numerical setting whose domain test covers less than the domain it claims; "
                 "tier 3 under B10 option 2 (ruled 2026-10-19) until that is measured."),
        approved="2026-10-19"),
    Row("rietx.schemas.instrument.Source:kind", "default", tier=1, ambiguity=1, value="xray_cw",
        evidence="arithmetic: a union tag, no value judgement"),
    Row("rietx.schemas.instrument.Source:polarization", "default", tier=3, ambiguity=3, value={"value": 0.5, "vary": False, "min": 0.0, "max": 1.0, "expr": None, "unit": None, "stderr": None},
        evidence=("physics: K = 0.5 is the unpolarised beam (docstring; GSAS POLA convention); a "
                  "monochromated lab beam or a synchrotron (K ~ 0.99) built without K is fitted at "
                  "0.5, and a wrong K moved Biso by 12 sigma at near-unchanged Rwp (WP-1311); "
                  "recorded as assumed in WP-2015"),
        grounds=("The beam's polarisation is a fact about the caller's instrument, outside the "
                 "pattern; 0.5 stays the held start and the result records it as assumed (B9, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.schemas.instrument.Source:kbeta", "default", tier=1, ambiguity=1, value=None,
        evidence=("arithmetic: None is 'no claim made', never 'no filter'; the contamination screen"
                  " runs unchanged (docstring, WP-1445)")),
    Row("rietx.schemas.instrument.Source:dispersion", "default", tier=2, ambiguity=1, value={"table": "cromer_liberman", "overrides": {}},
        evidence=("GSAS-II 5.8.4 applies Cromer-Liberman f', f'' to every X-ray histogram with no "
                  "switch (GSASIIstrIO.py:251-273, on every refinement path; checked); WP-1001: "
                  "round-robin QPA RMS 2.26 to 0.62 wt %; None declines it and "
                  "DISPERSION_NEGLECTED says so"
                  "; seven programs, 2026-10-21 (docs/practice.md): all seven apply f', f'' by default, BGMN through the .ano table its default LAMBDA names")),
    Row("rietx.schemas.instrument.Source:harmonics", "default", tier=1, ambiguity=1, value=(),
        evidence=("physics/arithmetic: an X-ray Source refuses a declared harmonic "
                  "(harmonics_supported False, f' shared across lines), so empty is the only legal "
                  "value; off is exact")),
    Row("rietx.refine.Refinement.fit:mode", "default", tier=2, ambiguity=1, value="rietveld",
        evidence=("GSAS-II 5.8.4 GSASIIphsGUI.py:9404: a phase-histogram's 'LeBail' defaults False,"
                  " i.e. Rietveld (checked)"
                  "; seven programs, 2026-10-21 (docs/practice.md): none defaults to Le Bail; FullProf, RIETAN-FP and TOPAS make the user state it")),
    Row("rietx.refine.Refinement.fit:plan", "default", tier=3, ambiguity=1, value="mccusker_default",
        evidence=("McCusker et al. (1999) J. Appl. Cryst. 32, 36, the order only (docstring); no "
                  "program ships a default plan; it frees the zero and no displacement, which "
                  "lab_bragg_brentano frees; changed by WP-2015 (the declared geometry picks the "
                  "plan)"),
        grounds=("A default must be some plan, and the one run is recorded; it frees nothing "
                 "geometry-specific, which the ruling keeps for an unstated geometry, and WP-2015 "
                 "picks by declared geometry (B7, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.refine.Refinement.fit:two_theta_limits", "default", tier=2, ambiguity=1, value=None,
        evidence=("GSAS-II 5.8.4 GSASIIdataGUI.py:2192-2201: a histogram's Limits default to the "
                  "full data range on import (checked)"
                  "; seven programs, 2026-10-21 (docs/practice.md): the full range in GSAS-II, FullProf, RIETAN-FP, MAUD and EasyDiffraction, BGMN the instrument function's range, TOPAS's default not stated")),
    Row("rietx.refine.Refinement.fit:events", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: an observation channel; "
                  "tests/test_answer_invariant_defaults.py asserts the answer bit-identical with it"
                  " on")),
    Row("rietx.refine.Refinement.fit:cancel", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: an observation channel; "
                  "tests/test_answer_invariant_defaults.py asserts the answer bit-identical with it"
                  " on")),
    Row("rietx.refine.Refinement.fit:telemetry", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: the run recorder; tests/test_answer_invariant_defaults.py "
                  "asserts the answer bit-identical with it on")),
    Row("rietx.refine.Refinement.fit:label", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: a run's name; tests/test_answer_invariant_defaults.py asserts "
                  "the answer bit-identical with it on")),
    Row("rietx.refine.Refinement.fit:stage_reports", "default", tier="invariant", ambiguity=1, value=False,
        evidence=("answer-invariant: per-stage reports; tests/test_answer_invariant_defaults.py "
                  "asserts the answer bit-identical with it on")),
    Row("rietx.refine.Refinement.fit:progress", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: an observation channel; "
                  "tests/test_answer_invariant_defaults.py asserts the answer bit-identical with it"
                  " on")),
    Row("rietx.refine.Refinement.run_stage:mode", "default", tier=2, ambiguity=1, value=None,
        evidence=("None continues the Refinement's current mode (the last fit, run_stage or "
                  "checkout set it), 'rietveld' on a fresh one: GSAS-II LeBail False, checked"
                  "; seven programs, 2026-10-21 (docs/practice.md): none defaults to Le Bail; FullProf, RIETAN-FP and TOPAS make the user state it")),
    Row("rietx.refine.Refinement.run_stage:two_theta_limits", "default", tier=2, ambiguity=1, value=None,
        evidence=("None continues the Refinement's current limits (the last fit, run_stage or "
                  "checkout set them), the full range on a fresh one: GSAS-II full-range Limits, "
                  "checked"
                  "; seven programs, 2026-10-21 (docs/practice.md): the full range in GSAS-II, FullProf, RIETAN-FP, MAUD and EasyDiffraction, BGMN the instrument function's range, TOPAS's default not stated")),
    Row("rietx.refine.Refinement.run_stage:correlation_guard", "default", value=0.98),
    Row("rietx.refine.Refinement.run_stage:window_area_tol", "default", tier=1, ambiguity=1, value=None,
        evidence=("None resolves to schemas.plan.CLOSING_WINDOW_TOL, the windows an answer is "
                  "measured on, and inherits that row's tier and domain test; the stage records "
                  "the fraction it ran at"),
        grounds=("No closing stage follows a stage driven by hand (the GUI's Run this stage "
                 "among them), so its own windows compute its answer; at the declared stages' "
                 "2 % that answer carried up to 0.97 esd on lab data. A caller wanting the fast "
                 "stage passes WINDOW_AREA_TOL, and cherry_pick passes a recorded node's "
                 "through forward.recorded_window_tol. Ruled 2026-10-21 (the seventh round's "
                 "Q1, evaluation outside a fit at the closing windows, which the brief extended "
                 "to this seat)."),
        approved="2026-10-21"),
    Row("rietx.refine.Refinement.run_stage:phase_support_sigma", "default", tier=3, ambiguity=1, value=3.0,
        evidence=("WP-1523: 3 sigma, = indexing ABSENT_SIGMA by test; 20 blank fits read 1 phase "
                  "seen, 9 at the old 1 sigma; fails on a real phase at ~1/16 000 of a strong "
                  "one's scale, seen in 1 fit of 8; own fixtures only; second pass owed (a weighed "
                  "phase at 0.1-1 wt %, a minor phase started one FWHM off its cell)"),
        grounds=("On by default: the hold touches only parameters the data cannot determine, "
                 "and an unseen phase's free cell walked 14.9 A from the truth while Rwp did "
                 "not move; no other code holds by default (TOPAS's Remove_Phase is opt-in), "
                 "so the 3 sigma is rietx's own, a caller sets another or None for off (B1, "
                 "ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.refine.Refinement.run_stage:events", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: an observation channel; "
                  "tests/test_answer_invariant_defaults.py asserts the answer bit-identical with it"
                  " on")),
    Row("rietx.refine.Refinement.run_stage:cancel", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: an observation channel; "
                  "tests/test_answer_invariant_defaults.py asserts the answer bit-identical with it"
                  " on")),
    Row("rietx.refine.Refinement.run_stage:telemetry", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: the run recorder; tests/test_answer_invariant_defaults.py "
                  "asserts the answer bit-identical with it on")),
    Row("rietx.refine.Refinement.run_stage:label", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: a run's name; tests/test_answer_invariant_defaults.py asserts "
                  "the answer bit-identical with it on")),
    Row("rietx.refine.refine:mode", "default", tier=2, ambiguity=1, value="rietveld",
        evidence=("GSAS-II 5.8.4 GSASIIphsGUI.py:9404: a phase-histogram's 'LeBail' defaults False,"
                  " i.e. Rietveld (checked)"
                  "; seven programs, 2026-10-21 (docs/practice.md): none defaults to Le Bail; FullProf, RIETAN-FP and TOPAS make the user state it")),
    Row("rietx.refine.refine:plan", "default", tier=3, ambiguity=1, value="mccusker_default",
        evidence=("McCusker et al. (1999) J. Appl. Cryst. 32, 36, the order only (docstring); no "
                  "program ships a default plan; it frees the zero and no displacement, which "
                  "lab_bragg_brentano frees; changed by WP-2015 (the declared geometry picks the "
                  "plan)"),
        grounds=("A default must be some plan, and the one run is recorded; it frees nothing "
                 "geometry-specific, which the ruling keeps for an unstated geometry, and WP-2015 "
                 "picks by declared geometry (B7, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.refine.refine:two_theta_limits", "default", tier=2, ambiguity=1, value=None,
        evidence=("GSAS-II 5.8.4 GSASIIdataGUI.py:2192-2201: a histogram's Limits default to the "
                  "full data range on import (checked)"
                  "; seven programs, 2026-10-21 (docs/practice.md): the full range in GSAS-II, FullProf, RIETAN-FP, MAUD and EasyDiffraction, BGMN the instrument function's range, TOPAS's default not stated")),
    Row("rietx.refine.refine:backend", "default", tier="caller", ambiguity=1, value="numpy",
        evidence=("opt-in: jax/torch/torch-mps need an extra no default install has; not "
                  "answer-invariant, since another backend agrees only to fp tolerance (torch-mps "
                  "fp32 columns land 3.5e-8 A from the numpy cell; tests/test_cross_backend.py "
                  "holds columns, not answers)")),
    Row("rietx.refine.refine:solver", "default", tier=2, ambiguity=1, value="lm",
        evidence=("GSAS-II 5.8.4 GSASIIobj.DefaultControls 'deriv type': 'analytic Hessian' runs "
                  "GSASIImath.HessianLSQ, a Marquardt-damped solve (checked)"
                  "; seven programs, 2026-10-21 (docs/practice.md): Marquardt-damped in six; FullProf dissents, Gauss-Newton with relaxation factors")),
    Row("rietx.refine.refine:history", "default", tier="invariant", ambiguity=1, value=False,
        evidence=("answer-invariant: a history tree; tests/test_answer_invariant_defaults.py "
                  "asserts the answer bit-identical with it on")),
    Row("rietx.refine.refine:events", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: an observation channel; "
                  "tests/test_answer_invariant_defaults.py asserts the answer bit-identical with it"
                  " on")),
    Row("rietx.refine.refine:cancel", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: an observation channel; "
                  "tests/test_answer_invariant_defaults.py asserts the answer bit-identical with it"
                  " on")),
    Row("rietx.refine.refine:telemetry", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: the run recorder; tests/test_answer_invariant_defaults.py "
                  "asserts the answer bit-identical with it on")),
    Row("rietx.refine.refine:label", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: a run's name; tests/test_answer_invariant_defaults.py asserts "
                  "the answer bit-identical with it on")),
    Row("rietx.background.auto.auto_background:kind", "default", tier=3, ambiguity=2, value="pspline",
        evidence=("GSAS-II 5.8.4 defaults to a 3-term Chebyshev (GSASIIdataGUI.py:2207, "
                  "inventory check), TOPAS and FullProf to polynomials (recalled); WP-1454: the "
                  "P-spline at λ 1 flat on 11-BM NAC and IUCr CPD sample 2"),
        grounds=("The skill presents the P-spline as the default background, so this is a "
                 "default (B12's ruling); the kind travels as BackgroundChoice.kind and "
                 "kind='chebyshev' is one keyword (B12, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("rietx.background.auto.auto_background:diagnostics", "default", tier=1, ambiguity=1, value=None,
        evidence=("arithmetic: None computes PatternDiagnostics from the data handed in, over "
                  "two_theta_limits; a caller's copy is used as given, and the two scores the "
                  "pick was made on ride on BackgroundChoice")),
    Row("rietx.background.auto.auto_background:wavelength", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: reaches only diagnose's contamination screen, which "
                  "auto_background does not read; tests/test_answer_invariant_defaults.py "
                  "asserts the BackgroundChoice equal with it, on a Kβ-doped pattern the screen "
                  "flags")),
    Row("rietx.background.auto.auto_background:two_theta_limits", "default", tier=2, ambiguity=1, value=None,
        evidence=("the range a fit without limits uses (Refinement.fit:two_theta_limits); "
                  "GSAS-II 5.8.4 GSASIIdataGUI.py:2192-2201: a histogram's Limits default to "
                  "the full data range on import (checked, the fit row)"
                  "; seven programs, 2026-10-21 (docs/practice.md): the full range in GSAS-II, FullProf, RIETAN-FP, MAUD and EasyDiffraction, BGMN the instrument function's range, TOPAS's default not stated")),
    Row("rietx.background.auto.auto_background:source", "default", tier="invariant", ambiguity=1, value=None,
        evidence=("answer-invariant: as wavelength, it reaches only the contamination screen; "
                  "tests/test_answer_invariant_defaults.py asserts the BackgroundChoice equal "
                  "with it")),
    Row("rietx.background.auto.auto_background:seed", "default", tier=2, ambiguity=1, value=False,
        evidence=("unseeded, every coefficient at the schema's 0.0; GSAS-II 5.8.4 starts a new "
                  "Chebyshev at the constant (1.0, 0, 0) and not from the data "
                  "(GSASIIdataGUI.py:2207, inventory check); seed=True is the opt-in, and #725 "
                  "is open on flipping it"
                  "; seven programs, 2026-10-21 (docs/practice.md): none of the seven seeds a background from the data by default")),
    Row("rietx.sequential.refine_sequential:carry", "default", value=("*",)),
    Row("rietx.sequential.refine_sequential:carry_hkl_intensities", "default", value=True),
    Row("rietx.sequential.refine_sequential:backend", "default", value="numpy"),
    Row("rietx.sequential.refine_sequential:solver", "default", value="lm"),
    Row("rietx.sequential.refine_sequential:history", "default", value=False),
    Row("rietx.sequential.SequentialRefinement.fit:x", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:x_label", "default", value="index"),
    Row("rietx.sequential.SequentialRefinement.fit:labels", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:mode", "default", value="rietveld"),
    Row("rietx.sequential.SequentialRefinement.fit:plan", "default", value="mccusker_default"),
    Row("rietx.sequential.SequentialRefinement.fit:refit", "default", value="single"),
    Row("rietx.sequential.SequentialRefinement.fit:two_theta_limits", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:direction", "default", value="forward"),
    Row("rietx.sequential.SequentialRefinement.fit:reseed", "default", value=True),
    Row("rietx.sequential.SequentialRefinement.fit:reseed_factor", "default", value=1.25),
    Row("rietx.sequential.SequentialRefinement.fit:first_rung_factor", "default", value=3.0),
    Row("rietx.sequential.SequentialRefinement.fit:verify_discontinuities", "default", value=False),
    Row("rietx.sequential.SequentialRefinement.fit:prepare", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:constrain", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:on_result", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:on_error", "default", value="carry"),
    Row("rietx.sequential.SequentialRefinement.fit:events", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:cancel", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:progress", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:telemetry", "default", value=None),
    Row("rietx.sequential.SequentialRefinement.fit:label", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:peaks", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:data", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:instrument", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:spec", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:preset", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:engines", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:quality", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:shift_from_pairs", "default", value=True),
    Row("rietx.indexing.workflow.index_pattern:validate", "default", value=True),
    Row("rietx.indexing.workflow.index_pattern:check_top", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:two_theta_limits", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:formula", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:temperature", "default", value=298.0),
    Row("rietx.indexing.workflow.index_pattern:events", "default", value=None),
    Row("rietx.indexing.workflow.index_pattern:cancel", "default", value=None),
    Row("rietx.indexing.engines.SearchSpec:systems", "default", value=("cubic", "hexagonal", "trigonal", "tetragonal", "orthorhombic", "monoclinic", "triclinic")),
    Row("rietx.indexing.engines.SearchSpec:centrings", "default", value=None),
    Row("rietx.indexing.engines.SearchSpec:min_d_axis", "default", value=2.0),
    Row("rietx.indexing.engines.SearchSpec:max_d_axis", "default", value=25.0),
    Row("rietx.indexing.engines.SearchSpec:min_volume", "default", value=15.0),
    Row("rietx.indexing.engines.SearchSpec:max_volume", "default", value=None),
    Row("rietx.indexing.engines.SearchSpec:n_unindexed", "default", value=None),
    Row("rietx.indexing.engines.SearchSpec:n_search_lines", "default", value=20),
    Row("rietx.indexing.engines.SearchSpec:k_sigma", "default", value=3.0),
    Row("rietx.indexing.engines.SearchSpec:shift_allowance_deg", "default", value=0.0),
    Row("rietx.indexing.engines.SearchSpec:shift_template", "default", value=None),
    Row("rietx.indexing.engines.SearchSpec:budget_seconds", "default", value=30.0),
    Row("rietx.indexing.engines.SearchSpec:total_budget_seconds", "default", value=None),
    Row("rietx.indexing.engines.SearchSpec:max_candidates", "default", value=12),
    Row("rietx.indexing.engines.SearchSpec:seed", "default", value=0),
    Row("rietx.indexing.engines.SearchSpec:prior_cells", "default", value=()),
    Row("rietx.indexing.engines.SearchSpec:prior_spacegroups", "default", value=()),
    # suggestion: 197
    Row("ABSORPTION_ESTIMATE_UNAVAILABLE.suggestion", "suggestion", value=1),
    Row("ABSORPTION_MU_R_OUT_OF_RANGE.suggestion", "suggestion", value=1),
    Row("ABSORPTION_THICKNESS_MATTERS.suggestion", "suggestion", value=1),
    Row("ADP_NOT_POSITIVE_DEFINITE.suggestion", "suggestion", value=1),
    Row("AIR_SCATTER_UNDECLARED.suggestion", "suggestion", value=1),
    Row("BACKGROUND_ABSORPTION.suggestion", "suggestion", value=1),
    Row("BACKGROUND_ORDER_AT_CAP.suggestion", "suggestion", value=1),
    Row("BISO_NEGATIVE.suggestion", "suggestion", value=1),
    Row("BISO_UNUSUALLY_LARGE.suggestion", "suggestion", value=1),
    Row("BOUND_HIT.suggestion", "suggestion", value=1),
    Row("BRINDLEY_OUTSIDE_REGIME.suggestion", "suggestion", value=1),
    Row("CAPILLARY_OFFSET_UNAVAILABLE.suggestion", "suggestion", value=1),
    Row("CELL_RUNAWAY.suggestion", "suggestion", tier=3, ambiguity=1, value=1,
        evidence=("WP-1110's trigger: a visible phase sharing its cell with a 2 % trace copy ran "
                  "4.16 -> 3803 A in one stage; fired in none of WP-1523's 104 fits"),
        grounds=("Each named fix breaks the joint degeneracy the trigger case walked, and the "
                 "choice among them is the caller's (B8, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("CHILD_GROUP_UNNAMED.suggestion", "suggestion", value=1),
    Row("CIF_CELL_ANGLE_CORRECTED.suggestion", "suggestion", value=1),
    Row("CIF_MAGNETIC_CENTERING_ASSUMED.suggestion", "suggestion", value=1),
    Row("CIF_MAGNETIC_ION_UNCHARGED.suggestion", "suggestion", value=1),
    Row("CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED.suggestion", "suggestion", value=1),
    Row("CIF_MAGNETIC_NUCLEAR_GROUP.suggestion", "suggestion", value=1),
    Row("CIF_MAGNETIC_NUCLEAR_SETTING.suggestion", "suggestion", value=1),
    Row("CIF_MAGNETIC_NUMBER_MISMATCH.suggestion", "suggestion", value=1),
    Row("CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED.suggestion", "suggestion", value=1),
    Row("CIF_MAGNETIC_SYMMFORM.suggestion", "suggestion", value=1),
    Row("CIF_SITE_LISTED_TWICE.suggestion", "suggestion", value=1),
    Row("CIF_SITE_MULTIPLICITY_DISAGREES.suggestion", "suggestion", value=1),
    Row("CIF_SITE_TWINS_MERGED.suggestion", "suggestion", value=1),
    Row("CONSTRAINT_ACTIVE.suggestion", "suggestion", value=1),
    Row("COVARIANCE_DIRECTION_DISCARDED.suggestion", "suggestion", value=1),
    Row("COVARIANCE_UNAVAILABLE.suggestion", "suggestion", value=1),
    Row("DATA_SUPPORT_LOW.suggestion", "suggestion", value=1),
    Row("DECLARED_RANGE_NOT_RESTORED.suggestion", "suggestion", value=1),
    Row("DECLARED_RANGE_RESTORED.suggestion", "suggestion", value=1),
    Row("DISPERSION_NEGLECTED.suggestion", "suggestion", value=1),
    Row("EXTINCTION_CONDITIONS_PARTIAL.suggestion", "suggestion", value=1),
    Row("EXTINCTION_FORBIDDEN_INTENSITY.suggestion", "suggestion", value=1),
    Row("EXTINCTION_GROUPS_NOT_SEPARABLE.suggestion", "suggestion", value=1),
    Row("EXTINCTION_PRIOR_APPLIED.suggestion", "suggestion", value=1),
    Row("EXTINCTION_SCREEN_FAILED.suggestion", "suggestion", value=2),
    Row("EXTINCTION_SYMBOL_AMBIGUOUS.suggestion", "suggestion", value=3),
    Row("EXTRA_PEAK_NO_INTENSITY.suggestion", "suggestion", value=1),
    Row("EXTRA_PEAK_ON_REFLECTION.suggestion", "suggestion", value=1),
    Row("FLAT_DIRECTION.suggestion", "suggestion", value=1),
    Row("FLOOR_HIT.suggestion", "suggestion", value=1),
    Row("FULLPROF_MAGNETIC_PHASE_OMITTED.suggestion", "suggestion", value=1),
    Row("FULLPROF_MAGNETIC_PHASE_READ.suggestion", "suggestion", value=1),
    Row("FULLPROF_OCCUPANCY_UNCHECKED.suggestion", "suggestion", value=1),
    Row("FULLPROF_TIE_DROPPED.suggestion", "suggestion", value=3),
    Row("GSAS2_CIF_FIELD_NOT_WRITTEN.suggestion", "suggestion", value=1),
    Row("GSAS2_GPX_BACKGROUND_NOT_CARRIED.suggestion", "suggestion", value=1),
    Row("GSAS2_GPX_CONSTRAINT_NOT_CARRIED.suggestion", "suggestion", value=1),
    Row("GSAS2_GPX_PHASE_MAGNETIC.suggestion", "suggestion", value=1),
    Row("GSAS2_GPX_SCALE_NOT_COMPARABLE.suggestion", "suggestion", value=1),
    Row("GSAS2_GPX_TEXTURE_NOT_CARRIED.suggestion", "suggestion", value=1),
    Row("GSAS2_INSTPRM_GEOMETRY_ASSUMED.suggestion", "suggestion", value=1),
    Row("GSAS_BANK_COMMENTED.suggestion", "suggestion", value=1),
    Row("GSAS_EXP_BACKGROUND_NOT_CARRIED.suggestion", "suggestion", value=1),
    Row("GSAS_EXP_PHASE_MAGNETIC.suggestion", "suggestion", value=1),
    Row("GSAS_EXP_REFINE_FLAG_MERGED.suggestion", "suggestion", value=1),
    Row("GSAS_EXP_SCALE_NOT_COMPARABLE.suggestion", "suggestion", value=1),
    Row("GSAS_PRM_GEOMETRY_ASSUMED.suggestion", "suggestion", value=1),
    Row("GSAS_PRM_PROFILE_SET_DEFAULTED.suggestion", "suggestion", value=1),
    Row("HARMONIC_ABSENT.suggestion", "suggestion", value=1),
    Row("HARMONIC_FRACTION.suggestion", "suggestion", value=1),
    Row("HARMONIC_HELD.suggestion", "suggestion", value=1),
    Row("HIGH_CORRELATION.suggestion", "suggestion", value=1),
    Row("HOLD_BLOCKED_PLAN.suggestion", "suggestion", value=1),
    Row("HUMP_TOO_NARROW.suggestion", "suggestion", value=1),
    Row("INDEX_ABSTAINED.suggestion", "suggestion", value=1),
    Row("INDEX_BRAVAIS_AMBIGUOUS.suggestion", "suggestion", value=1),
    Row("INDEX_BUDGET_EXHAUSTED.suggestion", "suggestion", value=1),
    Row("INDEX_CANDIDATES_TRUNCATED.suggestion", "suggestion", value=1),
    Row("INDEX_CELL_SYSTEMATIC_UNQUANTIFIED.suggestion", "suggestion", value=2),
    Row("INDEX_DATA_INSUFFICIENT.suggestion", "suggestion", value=4),
    Row("INDEX_DOMINANT_ZONE.suggestion", "suggestion", value=1),
    Row("INDEX_GEOMETRIC_AMBIGUITY.suggestion", "suggestion", value=1),
    Row("INDEX_IMPURITY_LINES.suggestion", "suggestion", value=1),
    Row("INDEX_INLIER_RETRY.suggestion", "suggestion", value=1),
    Row("INDEX_MULTIPLE_SOLUTIONS.suggestion", "suggestion", value=1),
    Row("INDEX_NOT_VALIDATED.suggestion", "suggestion", value=1),
    Row("INDEX_PANEL_REDUCED.suggestion", "suggestion", value=1),
    Row("INDEX_PREDICTED_BUT_ABSENT.suggestion", "suggestion", value=1),
    Row("INDEX_PRIOR_USED.suggestion", "suggestion", value=2),
    Row("INDEX_SEARCH_INCOMPLETE.suggestion", "suggestion", value=1),
    Row("INDEX_SHIFT_ALLOWANCE.suggestion", "suggestion", value=1),
    Row("INDEX_SHIFT_DETECTED.suggestion", "suggestion", value=1),
    Row("INDEX_SHIFT_FROM_PAIRS.suggestion", "suggestion", value=1),
    Row("INDEX_SHIFT_MODEL_AMBIGUOUS.suggestion", "suggestion", value=1),
    Row("INDEX_SINGLE_ENGINE.suggestion", "suggestion", value=1),
    Row("INDEX_SUPERCELL_REFUTED.suggestion", "suggestion", value=1),
    Row("INDEX_SYSTEMS_NOT_COVERED.suggestion", "suggestion", value=1),
    Row("INDEX_VALIDATION_FAILED.suggestion", "suggestion", value=1),
    Row("INDEX_VOLUME_UNPHYSICAL.suggestion", "suggestion", value=1),
    Row("INDEX_Z_NOT_INTEGER.suggestion", "suggestion", value=1),
    Row("LANDE_G_ASSUMED.suggestion", "suggestion", tier=1, ambiguity=1, value=2,
        evidence="arithmetic: names the argument that overrides the default"),
    Row("LAUE_CLASS_NOT_SEPARABLE.suggestion", "suggestion", value=1),
    Row("LEBAIL_ALTERNATION_STOPPED.suggestion", "suggestion", value=1),
    Row("LOW_ANGLE_UNMODELLED.suggestion", "suggestion", value=1),
    Row("MAGNETIC_ION_ASSUMED.suggestion", "suggestion", tier=1, ambiguity=3, value=2,
        evidence="arithmetic: names the argument that overrides the default"),
    Row("MAGNETIC_SUBGROUP_PREFERRED.suggestion", "suggestion", tier=1, ambiguity=2, value=1,
        evidence="arithmetic: defers the pick to the caller, as Rule 1's second kind asks"),
    Row("MAGNETIC_WIDTH_MOVED_MOMENT.suggestion", "suggestion", value=1),
    Row("MAGNETIC_WIDTH_UNMEASURED.suggestion", "suggestion", value=2),
    Row("MAGNETIC_WIDTH_UNMODELLED.suggestion", "suggestion", value=1),
    Row("MICROABSORPTION_SKIPPED.suggestion", "suggestion", value=1),
    Row("MODEL_FAR_FROM_DATA.suggestion", "suggestion", value=1),
    Row("MOMENT_ANGLE_STATIONARY.suggestion", "suggestion", tier=3, ambiguity=1, value=1,
        evidence=("LaMnO3 BT-1 (WP-1929): an angle 5.2 deg off 90 whose interval includes the "
                  "direction, Delta chi2 0.56 against the interval's 3.84"),
        grounds=("Says what the interval means: one that includes the direction cannot tell "
                 "the moment from one along it, one that excludes it measures the tilt "
                 "(B2 option 2, ruled 2026-10-19)."),
        approved="2026-10-19"),
    Row("NEUTRON_RESONANT_ABSORBER.suggestion", "suggestion", value=1),
    Row("OCCUPANCY_ABOVE_ONE.suggestion", "suggestion", tier=1, ambiguity=3, value=1,
        evidence=("physics: names the one reading under which the value is right (site "
                  "scattering on a mixed site) and the model terms to check otherwise")),
    Row("ORIGIN_FIXED_ON_POLAR_AXIS.suggestion", "suggestion", value=2),
    Row("ORIGIN_NOT_FIXED.suggestion", "suggestion", value=1),
    Row("PARAMETRIC_FORM_REJECTED.suggestion", "suggestion", value=2),
    Row("PARAMETRIC_OUT_OF_RANGE.suggestion", "suggestion", value=1),
    Row("PARAMETRIC_TARGET_UNSEEN.suggestion", "suggestion", value=1),
    Row("PATTERN_DEAD_CHANNELS.suggestion", "suggestion", value=2),
    Row("PATTERN_INTENSITY_SCALED.suggestion", "suggestion", value=6),
    Row("PATTERN_MULTISCAN_DEFAULTED.suggestion", "suggestion", value=1),
    Row("PATTERN_ROWS_DROPPED.suggestion", "suggestion", value=1),
    Row("PATTERN_SIGMA_CONSTANT.suggestion", "suggestion", value=1),
    Row("PATTERN_UNDERSAMPLED.suggestion", "suggestion", value=1),
    Row("PATTERN_X_AXIS_ASSUMED.suggestion", "suggestion", value=1),
    Row("PATTERN_X_AXIS_IMPLAUSIBLE.suggestion", "suggestion", value=1),
    Row("PAWLEY_OFF_DATA_RIDGED.suggestion", "suggestion", value=1),
    Row("PAWLEY_OVERLAP_UNRESOLVED.suggestion", "suggestion", value=1),
    Row("PEAK_ASYMMETRY_UNMODELLED.suggestion", "suggestion", value=1),
    Row("PEAK_AXIAL_TAIL.suggestion", "suggestion", value=1),
    Row("PEAK_CONTAMINATION_LINE.suggestion", "suggestion", value=1),
    Row("PEAK_EXPECTED_FALSE_LINES.suggestion", "suggestion", value=1),
    Row("PEAK_KALPHA2_ALIAS.suggestion", "suggestion", value=1),
    Row("PEAK_KALPHA2_RESIDUAL.suggestion", "suggestion", value=1),
    Row("PEAK_LIST_TOO_SHORT.suggestion", "suggestion", value=1),
    Row("PEAK_NOT_SEPARABLE.suggestion", "suggestion", value=1),
    Row("PEAK_POSITION_PRECISION.suggestion", "suggestion", value=1),
    Row("PEAK_SHOULDER_SEEDED.suggestion", "suggestion", value=1),
    Row("PEAK_SIGMA_ASSUMED.suggestion", "suggestion", value=1),
    Row("PEAK_UNRESOLVED_SHOULDER.suggestion", "suggestion", value=1),
    Row("PEAK_UNRESOLVED_SPLIT.suggestion", "suggestion", value=1),
    Row("PEAK_WIDTH_CAPPED.suggestion", "suggestion", value=1),
    Row("PEAK_WIDTH_LAW_MISMATCH.suggestion", "suggestion", value=2),
    Row("PHASE_UNCONSTRAINED.suggestion", "suggestion", value=1),
    Row("QPA_ESD_UNAVAILABLE.suggestion", "suggestion", value=1),
    Row("QPA_FRACTION_RANGE.suggestion", "suggestion", tier=2, ambiguity=3, value=1,
        evidence=("profile-likelihood interval in place of the Wald esd: Venzon & Moolgavkar (1988)"
                  " Appl. Statist. 37, 87; Hamilton (1965) (docstring)")),
    Row("QPA_UNAVAILABLE.suggestion", "suggestion", value=1),
    Row("RAS_ATTENUATOR_PRESENT.suggestion", "suggestion", value=1),
    Row("READER_OPTION_IGNORED.suggestion", "suggestion", value=1),
    Row("RECIPE_BACKGROUND_PEAK_DEGENERATE.suggestion", "suggestion", value=1),
    Row("RECIPE_ENGINE_DEFAULT_DECLINED.suggestion", "suggestion", value=1),
    Row("RECIPE_FIELD_DROPPED.suggestion", "suggestion", value=1),
    Row("RECIPE_FIT_RANGE_CHANNELS.suggestion", "suggestion", value=1),
    Row("RESOLUTION_NOT_POSITIVE.suggestion", "suggestion", value=1),
    Row("RESOLUTION_UNCONSTRAINED.suggestion", "suggestion", value=1),
    Row("RESTRAINT_TENSION.suggestion", "suggestion", value=1),
    Row("RIGID_BODY_MISFIT.suggestion", "suggestion", value=1),
    Row("RIGID_BODY_UNSUPPORTED.suggestion", "suggestion", value=1),
    Row("ROUGHNESS_ABSORPTION.suggestion", "suggestion", value=1),
    Row("ROUGHNESS_OUTSIDE_REGIME.suggestion", "suggestion", value=2),
    Row("ROUGHNESS_UNCONSTRAINED.suggestion", "suggestion", value=1),
    Row("SCALE_B_INSEPARABLE.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_CANCELLED.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_DISCONTINUITY.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_MOMENT_HOLD.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_MOMENT_ONSET.suggestion", "suggestion", value=6),
    Row("SEQUENTIAL_PATH_CHECK_INCOMPLETE.suggestion", "suggestion", value=3),
    Row("SEQUENTIAL_PATH_DEPENDENT.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_PERSISTENT_FINDING.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_RESEED.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_RWP_OUTLIER.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_UNRECOVERED.suggestion", "suggestion", value=1),
    Row("SEQUENTIAL_WIDTH_GROWTH.suggestion", "suggestion", value=1),
    Row("SERIES_PATTERN_FAILED.suggestion", "suggestion", value=1),
    Row("SITE_SNAPPED_TO_SPECIAL_POSITION.suggestion", "suggestion", value=2),
    Row("SIZE_NORMALISED_ACROSS_WAVELENGTHS.suggestion", "suggestion", value=1),
    Row("SIZE_UNUSUALLY_SMALL.suggestion", "suggestion", value=1),
    Row("SPACE_GROUP_SETTING_ASSUMED.suggestion", "suggestion", value=1),
    Row("SPECIES_FALLBACK_NEUTRAL.suggestion", "suggestion", value=1),
    Row("STAGE_FREED_NOTHING.suggestion", "suggestion", value=1),
    Row("STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT.suggestion", "suggestion", value=1),
    Row("STAGE_MAX_ITER.suggestion", "suggestion", value=1),
    Row("STAGE_PATH_NOT_FREE.suggestion", "suggestion", value=1),
    Row("STAGE_PATH_UNKNOWN.suggestion", "suggestion", value=2),
    Row("STEPHENS_STRAIN_NOT_POSITIVE.suggestion", "suggestion", value=1),
    Row("STRAIN_UNUSUALLY_LARGE.suggestion", "suggestion", value=1),
    Row("TEXTURE_NOT_POSITIVE.suggestion", "suggestion", value=1),
    Row("TOPAS_BLOCK_SKIPPED.suggestion", "suggestion", value=1),
    Row("TOPAS_CELL_COUPLING_DROPPED.suggestion", "suggestion", value=1),
    Row("TOPAS_FEATURES_NOT_IMPORTED.suggestion", "suggestion", value=2),
    Row("TOPAS_FEATURE_REFUSED.suggestion", "suggestion", value=2),
    Row("TOPAS_FIELD_NOT_WRITTEN.suggestion", "suggestion", value=1),
    Row("TOPAS_MAGNETIC_GROUP_READ.suggestion", "suggestion", value=1),
    Row("TOPAS_MAGNETIC_PART_MERGED.suggestion", "suggestion", value=1),
    Row("TOPAS_MOMENT_CONVENTION.suggestion", "suggestion", value=1),
    Row("TOPAS_MOMENT_G_HELD.suggestion", "suggestion", value=1),
    Row("TOPAS_MOMENT_ION_UNCHARGED.suggestion", "suggestion", value=1),
    Row("TOPAS_PHASE_TERM_READ.suggestion", "suggestion", value=1),
    Row("WAVELENGTH_CALIBRATION.suggestion", "suggestion", value=1),
    Row("rietx.crystallography.scattering.written_neutral_diagnostics.suggestion", "suggestion", value=1),
    Row("rietx.crystallography.symmetry.rhombohedral_restated_diagnostic.suggestion", "suggestion", value=1),
    Row("rietx.refine._dedup_high_correlations.suggestion", "suggestion", value=1),
    Row("rietx.schemas.results._cap_one_code.suggestion", "suggestion", value=1),
)

#: The names allowed at ``unaudited``, sorted.  Written once at the open
#: (2026-10-19); it shrinks as rows are audited.
UNAUDITED_BASELINE: tuple[str, ...] = (
    "ABSORPTION_ESTIMATE_UNAVAILABLE",
    "ABSORPTION_ESTIMATE_UNAVAILABLE.suggestion",
    "ABSORPTION_MU_R_OUT_OF_RANGE",
    "ABSORPTION_MU_R_OUT_OF_RANGE.suggestion",
    "ABSORPTION_PLATE_THICKNESS",
    "ABSORPTION_THICKNESS_MATTERS",
    "ABSORPTION_THICKNESS_MATTERS.suggestion",
    "ADP_NOT_POSITIVE_DEFINITE",
    "ADP_NOT_POSITIVE_DEFINITE.suggestion",
    "AIR_SCATTER_UNDECLARED",
    "AIR_SCATTER_UNDECLARED.suggestion",
    "BACKGROUND_ABSORPTION",
    "BACKGROUND_ABSORPTION.suggestion",
    "BACKGROUND_ORDER_AT_CAP",
    "BACKGROUND_ORDER_AT_CAP.suggestion",
    "BISO_NEGATIVE",
    "BISO_NEGATIVE.suggestion",
    "BISO_UNUSUALLY_LARGE",
    "BISO_UNUSUALLY_LARGE.suggestion",
    "BOUND_HIT",
    "BOUND_HIT.suggestion",
    "BRINDLEY_OUTSIDE_REGIME",
    "BRINDLEY_OUTSIDE_REGIME.suggestion",
    "BRML_ABSORBER_ENGAGED",
    "CAPILLARY_OFFSET_UNAVAILABLE",
    "CAPILLARY_OFFSET_UNAVAILABLE.suggestion",
    "CELL_DEGENERATE_PROBE",
    "CHILD_GROUP_UNNAMED",
    "CHILD_GROUP_UNNAMED.suggestion",
    "CIF_CELL_ANGLE_CORRECTED",
    "CIF_CELL_ANGLE_CORRECTED.suggestion",
    "CIF_MAGNETIC_CENTERING_ASSUMED",
    "CIF_MAGNETIC_CENTERING_ASSUMED.suggestion",
    "CIF_MAGNETIC_ION_UNCHARGED",
    "CIF_MAGNETIC_ION_UNCHARGED.suggestion",
    "CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED",
    "CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED.suggestion",
    "CIF_MAGNETIC_MOMENT_ON_ALLOWED",
    "CIF_MAGNETIC_NUCLEAR_GROUP",
    "CIF_MAGNETIC_NUCLEAR_GROUP.suggestion",
    "CIF_MAGNETIC_NUCLEAR_SETTING",
    "CIF_MAGNETIC_NUCLEAR_SETTING.suggestion",
    "CIF_MAGNETIC_NUMBER_MISMATCH",
    "CIF_MAGNETIC_NUMBER_MISMATCH.suggestion",
    "CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED",
    "CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED.suggestion",
    "CIF_MAGNETIC_SYMMFORM",
    "CIF_MAGNETIC_SYMMFORM.suggestion",
    "CIF_MAGNETIC_UNIDENTIFIED",
    "CIF_SITE_LISTED_TWICE",
    "CIF_SITE_LISTED_TWICE.suggestion",
    "CIF_SITE_MULTIPLICITY_DISAGREES",
    "CIF_SITE_MULTIPLICITY_DISAGREES.suggestion",
    "CIF_SITE_TWINS_MERGED",
    "CIF_SITE_TWINS_MERGED.suggestion",
    "CIF_SPECIES_NORMALISED",
    "CONSTRAINT_ACTIVE",
    "CONSTRAINT_ACTIVE.suggestion",
    "COVARIANCE_DIRECTION_DISCARDED",
    "COVARIANCE_DIRECTION_DISCARDED.suggestion",
    "COVARIANCE_UNAVAILABLE",
    "COVARIANCE_UNAVAILABLE.suggestion",
    "DATA_SUPPORT_LOW",
    "DATA_SUPPORT_LOW.suggestion",
    "DECLARED_RANGE_NOT_RESTORED",
    "DECLARED_RANGE_NOT_RESTORED.suggestion",
    "DECLARED_RANGE_RESTORED",
    "DECLARED_RANGE_RESTORED.suggestion",
    "DISPERSION_NEGLECTED",
    "DISPERSION_NEGLECTED.suggestion",
    "EXTINCTION_CONDITIONS_PARTIAL",
    "EXTINCTION_CONDITIONS_PARTIAL.suggestion",
    "EXTINCTION_FORBIDDEN_INTENSITY",
    "EXTINCTION_FORBIDDEN_INTENSITY.suggestion",
    "EXTINCTION_GROUPS_NOT_SEPARABLE",
    "EXTINCTION_GROUPS_NOT_SEPARABLE.suggestion",
    "EXTINCTION_PRIOR_APPLIED",
    "EXTINCTION_PRIOR_APPLIED.suggestion",
    "EXTINCTION_SCREEN_FAILED",
    "EXTINCTION_SCREEN_FAILED.suggestion",
    "EXTINCTION_SYMBOL_AMBIGUOUS",
    "EXTINCTION_SYMBOL_AMBIGUOUS.suggestion",
    "EXTRA_PEAK_NO_INTENSITY",
    "EXTRA_PEAK_NO_INTENSITY.suggestion",
    "EXTRA_PEAK_ON_REFLECTION",
    "EXTRA_PEAK_ON_REFLECTION.suggestion",
    "FLAT_DIRECTION",
    "FLAT_DIRECTION.suggestion",
    "FLAT_DIRECTION_OMITTED",
    "FLOOR_HIT",
    "FLOOR_HIT.suggestion",
    "FROZEN_COMPILE_STALE",
    "FULLPROF_MAGNETIC_PHASE_OMITTED",
    "FULLPROF_MAGNETIC_PHASE_OMITTED.suggestion",
    "FULLPROF_MAGNETIC_PHASE_READ",
    "FULLPROF_MAGNETIC_PHASE_READ.suggestion",
    "FULLPROF_OCCUPANCY_UNCHECKED",
    "FULLPROF_OCCUPANCY_UNCHECKED.suggestion",
    "FULLPROF_ORIGIN_CHOICE",
    "FULLPROF_RHOMBOHEDRAL_RESTATED",
    "FULLPROF_SPECIES_NORMALISED",
    "FULLPROF_SPECIES_WRITTEN_NEUTRAL",
    "FULLPROF_TIE_DROPPED",
    "FULLPROF_TIE_DROPPED.suggestion",
    "GSAS2_CIF_DEUTERIUM_AS_D",
    "GSAS2_CIF_FIELD_NOT_WRITTEN",
    "GSAS2_CIF_FIELD_NOT_WRITTEN.suggestion",
    "GSAS2_CIF_RHOMBOHEDRAL_RESTATED",
    "GSAS2_CIF_SETTING_IN_OPERATORS",
    "GSAS2_CIF_SPECIES_WRITTEN_NEUTRAL",
    "GSAS2_GPX_BACKGROUND_NOT_CARRIED",
    "GSAS2_GPX_BACKGROUND_NOT_CARRIED.suggestion",
    "GSAS2_GPX_CONSTRAINT_NOT_CARRIED",
    "GSAS2_GPX_CONSTRAINT_NOT_CARRIED.suggestion",
    "GSAS2_GPX_COORDINATES_SYMMETRY_FIXED",
    "GSAS2_GPX_ITEM_NOT_READ",
    "GSAS2_GPX_PHASE_MAGNETIC",
    "GSAS2_GPX_PHASE_MAGNETIC.suggestion",
    "GSAS2_GPX_SCALE_NOT_COMPARABLE",
    "GSAS2_GPX_SCALE_NOT_COMPARABLE.suggestion",
    "GSAS2_GPX_SETTING_FROM_OPERATORS",
    "GSAS2_GPX_SPECIES_NORMALISED",
    "GSAS2_GPX_TEXTURE_CONVERTED",
    "GSAS2_GPX_TEXTURE_NOT_CARRIED",
    "GSAS2_GPX_TEXTURE_NOT_CARRIED.suggestion",
    "GSAS2_INSTPRM_CONVENTION_ASSUMED",
    "GSAS2_INSTPRM_FIELD_DROPPED",
    "GSAS2_INSTPRM_FIELD_NOT_READ",
    "GSAS2_INSTPRM_FIELD_NOT_WRITTEN",
    "GSAS2_INSTPRM_GEOMETRY_ASSUMED",
    "GSAS2_INSTPRM_GEOMETRY_ASSUMED.suggestion",
    "GSAS2_INSTPRM_VALUE_DEFAULTED",
    "GSAS2_INSTPRM_VALUE_FLOORED",
    "GSAS2_INSTPRM_VALUE_MERGED",
    "GSAS_BANK_COMMENTED",
    "GSAS_BANK_COMMENTED.suggestion",
    "GSAS_EXP_BACKGROUND_NOT_CARRIED",
    "GSAS_EXP_BACKGROUND_NOT_CARRIED.suggestion",
    "GSAS_EXP_COORDINATES_SYMMETRY_FIXED",
    "GSAS_EXP_HISTOGRAM_NOT_READ",
    "GSAS_EXP_PHASE_MAGNETIC",
    "GSAS_EXP_PHASE_MAGNETIC.suggestion",
    "GSAS_EXP_REFINE_FLAG_MERGED",
    "GSAS_EXP_REFINE_FLAG_MERGED.suggestion",
    "GSAS_EXP_SCALE_NOT_COMPARABLE",
    "GSAS_EXP_SCALE_NOT_COMPARABLE.suggestion",
    "GSAS_EXP_SPECIES_NORMALISED",
    "GSAS_EXP_SPECIES_WRITTEN_NEUTRAL",
    "GSAS_EXP_VALUE_NARROWED",
    "GSAS_FIELD_OVERFLOW",
    "GSAS_IPARM_FIELD_DROPPED",
    "GSAS_IPARM_LEGACY_LAYOUT",
    "GSAS_IPARM_PROFILE_DECLINED",
    "GSAS_IPARM_PROFILE_READ",
    "GSAS_PRM_FIELD_DROPPED",
    "GSAS_PRM_FIELD_NOT_WRITTEN",
    "GSAS_PRM_GEOMETRY_ASSUMED",
    "GSAS_PRM_GEOMETRY_ASSUMED.suggestion",
    "GSAS_PRM_PROFILE_SET_DEFAULTED",
    "GSAS_PRM_PROFILE_SET_DEFAULTED.suggestion",
    "GSAS_PRM_VALUE_NARROWED",
    "HARMONIC_ABSENT",
    "HARMONIC_ABSENT.suggestion",
    "HARMONIC_FRACTION",
    "HARMONIC_FRACTION.suggestion",
    "HARMONIC_HELD",
    "HARMONIC_HELD.suggestion",
    "HIGH_CORRELATION",
    "HIGH_CORRELATION.suggestion",
    "HIGH_CORRELATION_OMITTED",
    "HOLD_BLOCKED_PLAN",
    "HOLD_BLOCKED_PLAN.suggestion",
    "HUMP_TOO_NARROW",
    "HUMP_TOO_NARROW.suggestion",
    "INDEX_ABSTAINED",
    "INDEX_ABSTAINED.suggestion",
    "INDEX_BRAVAIS_AMBIGUOUS",
    "INDEX_BRAVAIS_AMBIGUOUS.suggestion",
    "INDEX_BUDGET_EXHAUSTED",
    "INDEX_BUDGET_EXHAUSTED.suggestion",
    "INDEX_CANDIDATES_TRUNCATED",
    "INDEX_CANDIDATES_TRUNCATED.suggestion",
    "INDEX_CELL_SYSTEMATIC_UNQUANTIFIED",
    "INDEX_CELL_SYSTEMATIC_UNQUANTIFIED.suggestion",
    "INDEX_DATA_INSUFFICIENT",
    "INDEX_DATA_INSUFFICIENT.suggestion",
    "INDEX_DOMINANT_ZONE",
    "INDEX_DOMINANT_ZONE.suggestion",
    "INDEX_GEOMETRIC_AMBIGUITY",
    "INDEX_GEOMETRIC_AMBIGUITY.suggestion",
    "INDEX_IMPURITY_LINES",
    "INDEX_IMPURITY_LINES.suggestion",
    "INDEX_INLIER_RETRY",
    "INDEX_INLIER_RETRY.suggestion",
    "INDEX_MULTIPLE_SOLUTIONS",
    "INDEX_MULTIPLE_SOLUTIONS.suggestion",
    "INDEX_NOT_VALIDATED",
    "INDEX_NOT_VALIDATED.suggestion",
    "INDEX_PANEL_REDUCED",
    "INDEX_PANEL_REDUCED.suggestion",
    "INDEX_PREDICTED_BUT_ABSENT",
    "INDEX_PREDICTED_BUT_ABSENT.suggestion",
    "INDEX_PRIOR_USED",
    "INDEX_PRIOR_USED.suggestion",
    "INDEX_SEARCH_INCOMPLETE",
    "INDEX_SEARCH_INCOMPLETE.suggestion",
    "INDEX_SHIFT_ALLOWANCE",
    "INDEX_SHIFT_ALLOWANCE.suggestion",
    "INDEX_SHIFT_DETECTED",
    "INDEX_SHIFT_DETECTED.suggestion",
    "INDEX_SHIFT_FROM_PAIRS",
    "INDEX_SHIFT_FROM_PAIRS.suggestion",
    "INDEX_SHIFT_MODEL_AMBIGUOUS",
    "INDEX_SHIFT_MODEL_AMBIGUOUS.suggestion",
    "INDEX_SINGLE_ENGINE",
    "INDEX_SINGLE_ENGINE.suggestion",
    "INDEX_SUPERCELL_REFUTED",
    "INDEX_SUPERCELL_REFUTED.suggestion",
    "INDEX_SYSTEMS_NOT_COVERED",
    "INDEX_SYSTEMS_NOT_COVERED.suggestion",
    "INDEX_VALIDATION_FAILED",
    "INDEX_VALIDATION_FAILED.suggestion",
    "INDEX_VOLUME_UNPHYSICAL",
    "INDEX_VOLUME_UNPHYSICAL.suggestion",
    "INDEX_Z_NOT_INTEGER",
    "INDEX_Z_NOT_INTEGER.suggestion",
    "LAUE_CLASS_NOT_SEPARABLE",
    "LAUE_CLASS_NOT_SEPARABLE.suggestion",
    "LEBAIL_ALTERNATION_STOPPED",
    "LEBAIL_ALTERNATION_STOPPED.suggestion",
    "LOW_ANGLE_UNMODELLED",
    "LOW_ANGLE_UNMODELLED.suggestion",
    "MAGNETIC_WIDTH_MOVED_MOMENT",
    "MAGNETIC_WIDTH_MOVED_MOMENT.suggestion",
    "MAGNETIC_WIDTH_UNMEASURED",
    "MAGNETIC_WIDTH_UNMEASURED.suggestion",
    "MAGNETIC_WIDTH_UNMODELLED",
    "MAGNETIC_WIDTH_UNMODELLED.suggestion",
    "MICROABSORPTION_SKIPPED",
    "MICROABSORPTION_SKIPPED.suggestion",
    "MODEL_FAR_FROM_DATA",
    "MODEL_FAR_FROM_DATA.suggestion",
    "MOMENT_PAIR_DEGENERATE",
    "NEUTRON_RESONANT_ABSORBER",
    "NEUTRON_RESONANT_ABSORBER.suggestion",
    "ORIGIN_FIXED_ON_POLAR_AXIS",
    "ORIGIN_FIXED_ON_POLAR_AXIS.suggestion",
    "ORIGIN_NOT_FIXED",
    "ORIGIN_NOT_FIXED.suggestion",
    "PARAMETRIC_FORM_REJECTED",
    "PARAMETRIC_FORM_REJECTED.suggestion",
    "PARAMETRIC_OUT_OF_RANGE",
    "PARAMETRIC_OUT_OF_RANGE.suggestion",
    "PARAMETRIC_TARGET_UNSEEN",
    "PARAMETRIC_TARGET_UNSEEN.suggestion",
    "PATTERN_DEAD_CHANNELS",
    "PATTERN_DEAD_CHANNELS.suggestion",
    "PATTERN_DUPLICATE_POINTS",
    "PATTERN_INTENSITY_SCALED",
    "PATTERN_INTENSITY_SCALED.suggestion",
    "PATTERN_MULTISCAN_DEFAULTED",
    "PATTERN_MULTISCAN_DEFAULTED.suggestion",
    "PATTERN_ROWS_DROPPED",
    "PATTERN_ROWS_DROPPED.suggestion",
    "PATTERN_SCAN_REVERSED",
    "PATTERN_SIGMA_CONSTANT",
    "PATTERN_SIGMA_CONSTANT.suggestion",
    "PATTERN_UNDERSAMPLED",
    "PATTERN_UNDERSAMPLED.suggestion",
    "PATTERN_X_AXIS_ASSUMED",
    "PATTERN_X_AXIS_ASSUMED.suggestion",
    "PATTERN_X_AXIS_IMPLAUSIBLE",
    "PATTERN_X_AXIS_IMPLAUSIBLE.suggestion",
    "PAWLEY_OFF_DATA_RIDGED",
    "PAWLEY_OFF_DATA_RIDGED.suggestion",
    "PAWLEY_OVERLAP_UNRESOLVED",
    "PAWLEY_OVERLAP_UNRESOLVED.suggestion",
    "PEAK_ASYMMETRY_UNMODELLED",
    "PEAK_ASYMMETRY_UNMODELLED.suggestion",
    "PEAK_AXIAL_TAIL",
    "PEAK_AXIAL_TAIL.suggestion",
    "PEAK_CONTAMINATION_LINE",
    "PEAK_CONTAMINATION_LINE.suggestion",
    "PEAK_EXPECTED_FALSE_LINES",
    "PEAK_EXPECTED_FALSE_LINES.suggestion",
    "PEAK_KALPHA2_ALIAS",
    "PEAK_KALPHA2_ALIAS.suggestion",
    "PEAK_KALPHA2_RESIDUAL",
    "PEAK_KALPHA2_RESIDUAL.suggestion",
    "PEAK_LIST_TOO_SHORT",
    "PEAK_LIST_TOO_SHORT.suggestion",
    "PEAK_NOT_SEPARABLE",
    "PEAK_NOT_SEPARABLE.suggestion",
    "PEAK_POSITION_PRECISION",
    "PEAK_POSITION_PRECISION.suggestion",
    "PEAK_SHOULDER_SEEDED",
    "PEAK_SHOULDER_SEEDED.suggestion",
    "PEAK_SIGMA_ASSUMED",
    "PEAK_SIGMA_ASSUMED.suggestion",
    "PEAK_UNRESOLVED_SHOULDER",
    "PEAK_UNRESOLVED_SHOULDER.suggestion",
    "PEAK_UNRESOLVED_SPLIT",
    "PEAK_UNRESOLVED_SPLIT.suggestion",
    "PEAK_WIDTH_CAPPED",
    "PEAK_WIDTH_CAPPED.suggestion",
    "PEAK_WIDTH_LAW_MISMATCH",
    "PEAK_WIDTH_LAW_MISMATCH.suggestion",
    "PHASE_UNCONSTRAINED",
    "PHASE_UNCONSTRAINED.suggestion",
    "QPA_ESD_UNAVAILABLE",
    "QPA_ESD_UNAVAILABLE.suggestion",
    "QPA_UNAVAILABLE",
    "QPA_UNAVAILABLE.suggestion",
    "RAS_ATTENUATOR_PRESENT",
    "RAS_ATTENUATOR_PRESENT.suggestion",
    "READER_OPTION_IGNORED",
    "READER_OPTION_IGNORED.suggestion",
    "RECIPE_BACKGROUND_PEAK_DEGENERATE",
    "RECIPE_BACKGROUND_PEAK_DEGENERATE.suggestion",
    "RECIPE_BACKGROUND_RESEEDED",
    "RECIPE_BOUND_HONOURED",
    "RECIPE_CONVENTION_ASSUMED",
    "RECIPE_DISPERSION_DECLINED",
    "RECIPE_ENGINE_DEFAULT_DECLINED",
    "RECIPE_ENGINE_DEFAULT_DECLINED.suggestion",
    "RECIPE_FIELD_DROPPED",
    "RECIPE_FIELD_DROPPED.suggestion",
    "RECIPE_FIT_RANGE_CHANNELS",
    "RECIPE_FIT_RANGE_CHANNELS.suggestion",
    "RECIPE_FLAG_DROPPED",
    "RECIPE_FLAG_TRANSLATED",
    "RECIPE_NOTHING_REFINED",
    "RECIPE_PLAN_STAGED",
    "RECIPE_SCALE_RESEEDED",
    "RECIPE_SCHEMA_UNTESTED",
    "RECIPE_ZERO_WEIGHT_EXCLUDED",
    "RESOLUTION_NOT_POSITIVE",
    "RESOLUTION_NOT_POSITIVE.suggestion",
    "RESOLUTION_UNCONSTRAINED",
    "RESOLUTION_UNCONSTRAINED.suggestion",
    "RESTRAINT_TENSION",
    "RESTRAINT_TENSION.suggestion",
    "RIGID_BODY_MISFIT",
    "RIGID_BODY_MISFIT.suggestion",
    "RIGID_BODY_UNSUPPORTED",
    "RIGID_BODY_UNSUPPORTED.suggestion",
    "ROUGHNESS_ABSORPTION",
    "ROUGHNESS_ABSORPTION.suggestion",
    "ROUGHNESS_OUTSIDE_REGIME",
    "ROUGHNESS_OUTSIDE_REGIME.suggestion",
    "ROUGHNESS_UNCONSTRAINED",
    "ROUGHNESS_UNCONSTRAINED.suggestion",
    "SCALE_B_INSEPARABLE",
    "SCALE_B_INSEPARABLE.suggestion",
    "SEQUENTIAL_CANCELLED",
    "SEQUENTIAL_CANCELLED.suggestion",
    "SEQUENTIAL_DISCONTINUITY",
    "SEQUENTIAL_DISCONTINUITY.suggestion",
    "SEQUENTIAL_MOMENT_HOLD",
    "SEQUENTIAL_MOMENT_HOLD.suggestion",
    "SEQUENTIAL_MOMENT_ONSET",
    "SEQUENTIAL_MOMENT_ONSET.suggestion",
    "SEQUENTIAL_PATH_CHECK_INCOMPLETE",
    "SEQUENTIAL_PATH_CHECK_INCOMPLETE.suggestion",
    "SEQUENTIAL_PATH_DEPENDENT",
    "SEQUENTIAL_PATH_DEPENDENT.suggestion",
    "SEQUENTIAL_PERSISTENT_FINDING",
    "SEQUENTIAL_PERSISTENT_FINDING.suggestion",
    "SEQUENTIAL_RESEED",
    "SEQUENTIAL_RESEED.suggestion",
    "SEQUENTIAL_RWP_OUTLIER",
    "SEQUENTIAL_RWP_OUTLIER.suggestion",
    "SEQUENTIAL_UNRECOVERED",
    "SEQUENTIAL_UNRECOVERED.suggestion",
    "SEQUENTIAL_WIDTH_GROWTH",
    "SEQUENTIAL_WIDTH_GROWTH.suggestion",
    "SERIES_PATTERN_FAILED",
    "SERIES_PATTERN_FAILED.suggestion",
    "SITE_SNAPPED_TO_SPECIAL_POSITION",
    "SITE_SNAPPED_TO_SPECIAL_POSITION.suggestion",
    "SIZE_NORMALISED_ACROSS_WAVELENGTHS",
    "SIZE_NORMALISED_ACROSS_WAVELENGTHS.suggestion",
    "SIZE_UNUSUALLY_SMALL",
    "SIZE_UNUSUALLY_SMALL.suggestion",
    "SPACE_GROUP_SETTING_ASSUMED",
    "SPACE_GROUP_SETTING_ASSUMED.suggestion",
    "SPECIES_FALLBACK_NEUTRAL",
    "SPECIES_FALLBACK_NEUTRAL.suggestion",
    "STAGE_FREED_NOTHING",
    "STAGE_FREED_NOTHING.suggestion",
    "STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT",
    "STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT.suggestion",
    "STAGE_MAX_ITER",
    "STAGE_MAX_ITER.suggestion",
    "STAGE_PATH_NOT_FREE",
    "STAGE_PATH_NOT_FREE.suggestion",
    "STAGE_PATH_UNKNOWN",
    "STAGE_PATH_UNKNOWN.suggestion",
    "STEPHENS_STRAIN_NOT_POSITIVE",
    "STEPHENS_STRAIN_NOT_POSITIVE.suggestion",
    "STRAIN_UNUSUALLY_LARGE",
    "STRAIN_UNUSUALLY_LARGE.suggestion",
    "TEXTURE_NOT_POSITIVE",
    "TEXTURE_NOT_POSITIVE.suggestion",
    "TOPAS_BLOCK_SKIPPED",
    "TOPAS_BLOCK_SKIPPED.suggestion",
    "TOPAS_CELL_COUPLING_DROPPED",
    "TOPAS_CELL_COUPLING_DROPPED.suggestion",
    "TOPAS_FEATURES_NOT_IMPORTED",
    "TOPAS_FEATURES_NOT_IMPORTED.suggestion",
    "TOPAS_FEATURE_REFUSED",
    "TOPAS_FEATURE_REFUSED.suggestion",
    "TOPAS_FIELD_NOT_WRITTEN",
    "TOPAS_FIELD_NOT_WRITTEN.suggestion",
    "TOPAS_FIRST_RUN_READ",
    "TOPAS_MAGNETIC_GROUP_READ",
    "TOPAS_MAGNETIC_GROUP_READ.suggestion",
    "TOPAS_MAGNETIC_PART_MERGED",
    "TOPAS_MAGNETIC_PART_MERGED.suggestion",
    "TOPAS_MOMENT_CONVENTION",
    "TOPAS_MOMENT_CONVENTION.suggestion",
    "TOPAS_MOMENT_G_HELD",
    "TOPAS_MOMENT_G_HELD.suggestion",
    "TOPAS_MOMENT_ION_UNCHARGED",
    "TOPAS_MOMENT_ION_UNCHARGED.suggestion",
    "TOPAS_ORIGIN_TRANSLATED",
    "TOPAS_PHASE_RESTATED_IN_P1",
    "TOPAS_PHASE_TERM_READ",
    "TOPAS_PHASE_TERM_READ.suggestion",
    "TOPAS_SPECIES_NORMALISED",
    "TOPAS_SPECIES_WRITTEN_NEUTRAL",
    "WAVELENGTH_CALIBRATION",
    "WAVELENGTH_CALIBRATION.suggestion",
    "XRDML_ATTENUATOR_APPLIED",
    "rietx.background.diagnostics.COVERAGE_INFLATION_THRESHOLD",
    "rietx.background.diagnostics.COVERAGE_SMOOTH_DEG",
    "rietx.background.diagnostics.CUTOFF_FRACTION",
    "rietx.background.diagnostics.CUTOFF_INTERIOR_FRACTION",
    "rietx.background.diagnostics.CUTOFF_MIN_DEG",
    "rietx.background.diagnostics.CUTOFF_ONSET_FRACTION",
    "rietx.background.diagnostics.CUTOFF_PLATEAU_DEG",
    "rietx.background.diagnostics.CUTOFF_SMOOTH_DEG",
    "rietx.background.diagnostics.DEAD_LEVEL_FRACTION",
    "rietx.background.diagnostics.DEAD_LEVEL_WINDOW_DEG",
    "rietx.background.diagnostics.DEAD_WEIGHT_RATIO_MIN",
    "rietx.background.diagnostics.GHOST_ESD_MAX_DEG",
    "rietx.background.diagnostics.GHOST_MATCH_K",
    "rietx.background.diagnostics.GHOST_MIN_PARENTS",
    "rietx.background.diagnostics.GHOST_N_PARENTS",
    "rietx.background.diagnostics.GHOST_RATIO_RANGE",
    "rietx.background.diagnostics.GHOST_RATIO_TOL",
    "rietx.background.diagnostics.GHOST_TOL_DEG",
    "rietx.background.diagnostics.SAMPLING_HEIGHT_FRACTION",
    "rietx.background.diagnostics.SAMPLING_PROMINENCE_SIGMA",
    "rietx.background.diagnostics._ANODE_MATCH_TOL",
    "rietx.background.diagnostics._DEAD_INTERVAL_DECIMALS",
    "rietx.background.diagnostics._DEAD_REPAIR_PASSES",
    "rietx.crystallography.atomic_volume.TABLE_TEMPERATURE",
    "rietx.crystallography.atomic_volume.THERMAL_EXPANSION",
    "rietx.crystallography.atomic_volume.THERMAL_EXPANSION_ESD",
    "rietx.crystallography.atomic_volume.VOLUME_RATIO_BOUNDS",
    "rietx.crystallography.atomic_volume.VOLUME_SCATTER",
    "rietx.crystallography.attenuation._HC_EV_ANGSTROM",
    "rietx.crystallography.attenuation._NA_BARN",
    "rietx.crystallography.cif.CIF_ANGLE_CORRECT_MAX_DEG",
    "rietx.crystallography.cif.CIF_STATED_MULTIPLICITY_SNAP_TOL",
    "rietx.crystallography.cif.DUPLICATE_U_TOLERANCE",
    "rietx.crystallography.cif.OCCUPANCY_TOLERANCE",
    "rietx.crystallography.cif.TWIN_DISTANCE",
    "rietx.crystallography.dispersion.LINE_DISPERSION_TOL",
    "rietx.crystallography.dispersion.NEAR_EDGE_EV",
    "rietx.crystallography.fragments.COLLINEAR_TOL",
    "rietx.crystallography.fragments.INERTIA_RANK_TOL",
    "rietx.crystallography.fragments._COINCIDENT_A2",
    "rietx.crystallography.magcif.MOMENT_FORM_AGREEMENT_MU_B",
    "rietx.crystallography.magnetic.isotropy.CROSS_IRREP_DRAWS",
    "rietx.crystallography.magnetic.isotropy.DEFAULT_CELL_SCALE",
    "rietx.crystallography.magnetic.isotropy.DUAL_AFTER_RESTART",
    "rietx.crystallography.magnetic.isotropy.FARKAS_FLOOR",
    "rietx.crystallography.magnetic.isotropy.FARKAS_QUOTE",
    "rietx.crystallography.magnetic.isotropy.INTENSITY_RTOL",
    "rietx.crystallography.magnetic.isotropy.ISOMETRY_RESIDUAL",
    "rietx.crystallography.magnetic.isotropy.KERNEL_AMPLITUDE_RATIO",
    "rietx.crystallography.magnetic.isotropy.TRANSFER_FLOAT_STACK",
    "rietx.crystallography.magnetic.isotropy.WITHIN_IRREP_DRAWS",
    "rietx.crystallography.magnetic.isotropy._CLOSURE_LIMIT",
    "rietx.crystallography.magnetic.isotropy._SPAN_GAP",
    "rietx.crystallography.magnetic.moments.MOMENT_DIRECTION_SUPPORT",
    "rietx.crystallography.magnetic.moments.SEED_TILT",
    "rietx.crystallography.magnetic.operators.N_MAGNETIC_SPACE_GROUPS",
    "rietx.crystallography.magnetic.operators._MAX_CODE",
    "rietx.crystallography.magnetic.p1._WRAP_TOL",
    "rietx.crystallography.magnetic.scattering.INVARIANCE_MOMENT_TOL",
    "rietx.crystallography.magnetic.scattering.INVARIANCE_POS_TOL",
    "rietx.crystallography.magnetic.scattering.METRIC_TOL",
    "rietx.crystallography.magnetic.scattering.P_MAGNETIC_FM",
    "rietx.crystallography.magnetic.supercell.CHILD_SITE_TOL",
    "rietx.crystallography.neutron.NEUTRON_LAMBDA_EV_ANGSTROM",
    "rietx.crystallography.neutron.SIGMA_ABS_REFERENCE_WAVELENGTH",
    "rietx.crystallography.representation.distortion._POSITION_TOL",
    "rietx.crystallography.representation.distortion._PROBE_AMPLITUDE",
    "rietx.crystallography.representation.distortion._PROBE_SYMPREC",
    "rietx.crystallography.representation.distortion._RANK_TOL",
    "rietx.crystallography.representation.irreps.IRREP_ATOL",
    "rietx.crystallography.representation.irreps.K_FLOAT_TOL",
    "rietx.crystallography.representation.irreps.K_MAX_DENOMINATOR",
    "rietx.crystallography.representation.irreps._H",
    "rietx.crystallography.representation.irreps._SEEDS",
    "rietx.crystallography.representation.irreps._T",
    "rietx.crystallography.representation.irreps._TT",
    "rietx.crystallography.representation.irreps._ZERO",
    "rietx.crystallography.representation.modes.MODE_ATOL",
    "rietx.crystallography.representation.modes.POSITION_ATOL",
    "rietx.crystallography.representation.order_parameter.ISOTROPY_ATOL",
    "rietx.crystallography.riding.RIDING_MIN_SEPARATION",
    "rietx.crystallography.rotation.SERIES_THRESHOLD",
    "rietx.crystallography.rotation.UNIT_TOLERANCE",
    "rietx.crystallography.rotation._A_SERIES",
    "rietx.crystallography.rotation._B_SERIES",
    "rietx.crystallography.rotation._C_SERIES",
    "rietx.crystallography.rotation._LOG_SERIES_NORM",
    "rietx.crystallography.satellites._ORDERS",
    "rietx.crystallography.scattering.written_neutral_diagnostics.suggestion",
    "rietx.crystallography.spherical_harmonics._TOL",
    "rietx.crystallography.stephens._DEG_PER_RAD",
    "rietx.crystallography.superspace.generation.N_BRAVAIS_CLASSES_D1",
    "rietx.crystallography.superspace.generation.N_SUPERSPACE_GROUPS_D1",
    "rietx.crystallography.superspace.generation._F0",
    "rietx.crystallography.superspace.generation._GRID",
    "rietx.crystallography.superspace.generation._QR_COMPONENTS",
    "rietx.crystallography.superspace.operators._ZERO3",
    "rietx.crystallography.symmetry.MAX_HKL_GRID_POINTS",
    "rietx.crystallography.symmetry.SITE_TOL",
    "rietx.crystallography.symmetry.SYMMETRY_ANGLE_TOL_DEG",
    "rietx.crystallography.symmetry._COINCIDENCE_TOL",
    "rietx.crystallography.symmetry._GAMMA_HEX",
    "rietx.crystallography.symmetry._ORBIT_CHUNK_ELEMENTS",
    "rietx.crystallography.symmetry._SITE_TOL_SLACK",
    "rietx.crystallography.symmetry._SNAP_MESSAGE_SITES",
    "rietx.crystallography.symmetry._SNAP_NOISE",
    "rietx.crystallography.symmetry._TRANSLATION_DEN",
    "rietx.crystallography.symmetry.rhombohedral_restated_diagnostic.suggestion",
    "rietx.gui.imports.MAX_UPLOAD_BYTES",
    "rietx.gui.imports.PREVIEW_POINTS",
    "rietx.gui.imports.WAVELENGTH_RTOL",
    "rietx.gui.symmetry.LETTER_CACHE",
    "rietx.gui.symmetry.ORBIT_COLLISION_TOL",
    "rietx.gui.symmetry.POSITION_TOL",
    "rietx.indexing.ambiguity.AMBIGUITY_DISCREPANCY_SLACK",
    "rietx.indexing.ambiguity.AMBIGUITY_EXTEND_FACTOR",
    "rietx.indexing.ambiguity.MAX_AMBIGUITY_INDEX",
    "rietx.indexing.ambiguity.MAX_DISCRIMINATING",
    "rietx.indexing.ambiguity.SUPERCELL_CHANCE_ALPHA",
    "rietx.indexing.ambiguity.UNCANCELLABLE_METRIC_RTOL",
    "rietx.indexing.ambiguity._DERIVATIVE_VOLUME_RTOL",
    "rietx.indexing.consensus.CONSENSUS_CHECK_TOP",
    "rietx.indexing.diagnostics.BRAGG_BRENTANO_CELL_PPM",
    "rietx.indexing.diagnostics.WIDTH_MISMATCH_RATIO",
    "rietx.indexing.diagnostics.Z_INTEGER_TOLERANCE",
    "rietx.indexing.dichotomy.ACCEPT_SPACING_FRAC",
    "rietx.indexing.dichotomy.ANGLE_STEP_DEG",
    "rietx.indexing.dichotomy.ANNEAL_FACTOR",
    "rietx.indexing.dichotomy.AXIS_STEP",
    "rietx.indexing.dichotomy.DEDUP_EVERY",
    "rietx.indexing.dichotomy.MAX_ANGLE_COSINE",
    "rietx.indexing.dichotomy.MAX_ASSIGN_PASSES",
    "rietx.indexing.dichotomy.MAX_DEPTH",
    "rietx.indexing.dichotomy.MAX_GRID_CELLS",
    "rietx.indexing.dichotomy.MAX_TRIAL_HKL",
    "rietx.indexing.dichotomy._SAME_BOX_RTOL",
    "rietx.indexing.engines.ANCHOR_LINES",
    "rietx.indexing.engines.CEILING_GRANULARITY_SECONDS",
    "rietx.indexing.engines.DEDUP_STACK_FIRST",
    "rietx.indexing.engines.DEDUP_VOLUME_RTOL",
    "rietx.indexing.engines.DEFAULT_BUDGET_SECONDS",
    "rietx.indexing.engines.DEFAULT_MAX_CANDIDATES",
    "rietx.indexing.engines.DEFAULT_MAX_D_AXIS",
    "rietx.indexing.engines.DEFAULT_MIN_D_AXIS",
    "rietx.indexing.engines.DEFAULT_MIN_VOLUME",
    "rietx.indexing.engines.DEFAULT_N_UNINDEXED",
    "rietx.indexing.engines.DEFAULT_SEARCH_LINES",
    "rietx.indexing.engines.DEFAULT_UNKNOWN_SHIFT_DEG",
    "rietx.indexing.engines.DEFAULT_VOLUME_CEILING",
    "rietx.indexing.engines.ENGINE_POOL_MULTIPLE",
    "rietx.indexing.engines.INLIER_DOF_MARGIN",
    "rietx.indexing.engines.INLIER_FRACTION",
    "rietx.indexing.engines.MAX_PREDICTED_REFLECTIONS",
    "rietx.indexing.engines.MEASURED_TYPICAL_SECONDS",
    "rietx.indexing.engines.MEASURED_VALIDATION_SECONDS",
    "rietx.indexing.engines.MIN_AGREEMENT",
    "rietx.indexing.engines.PROVISIONAL_STREAM_TOP",
    "rietx.indexing.engines.QUICK_TOTAL_BUDGET_SECONDS",
    "rietx.indexing.engines.SAME_SOLUTION_RTOL",
    "rietx.indexing.engines.SEARCH_POOL_MULTIPLE",
    "rietx.indexing.engines.SearchSpec:budget_seconds",
    "rietx.indexing.engines.SearchSpec:centrings",
    "rietx.indexing.engines.SearchSpec:k_sigma",
    "rietx.indexing.engines.SearchSpec:max_candidates",
    "rietx.indexing.engines.SearchSpec:max_d_axis",
    "rietx.indexing.engines.SearchSpec:max_volume",
    "rietx.indexing.engines.SearchSpec:min_d_axis",
    "rietx.indexing.engines.SearchSpec:min_volume",
    "rietx.indexing.engines.SearchSpec:n_search_lines",
    "rietx.indexing.engines.SearchSpec:n_unindexed",
    "rietx.indexing.engines.SearchSpec:prior_cells",
    "rietx.indexing.engines.SearchSpec:prior_spacegroups",
    "rietx.indexing.engines.SearchSpec:seed",
    "rietx.indexing.engines.SearchSpec:shift_allowance_deg",
    "rietx.indexing.engines.SearchSpec:shift_template",
    "rietx.indexing.engines.SearchSpec:systems",
    "rietx.indexing.engines.SearchSpec:total_budget_seconds",
    "rietx.indexing.engines.VALIDATION_RESERVE_FRACTION",
    "rietx.indexing.engines.WIDTH_ALLOWANCE_FWHM",
    "rietx.indexing.engines.WIDTH_ALLOWANCE_QUANTILE",
    "rietx.indexing.engines._INDEX_MARGIN",
    "rietx.indexing.engines._INDEX_MAX_CONDITION",
    "rietx.indexing.engines._INDEX_MAX_SHARE",
    "rietx.indexing.engines._INDEX_MIN_DEFECT",
    "rietx.indexing.engines._INDEX_MIN_ROWS",
    "rietx.indexing.extinction.DECISIVE_DELTA_BIC",
    "rietx.indexing.extinction._MODULI",
    "rietx.indexing.fom.FOM_N",
    "rietx.indexing.fom.LINE_COINCIDENCE_RTOL",
    "rietx.indexing.fom.MATCH_SIGMA",
    "rietx.indexing.fom._AGGREGATE_FLOOR_RTOL",
    "rietx.indexing.fom._BOUNDARY_RTOL",
    "rietx.indexing.peakfit._H_POS",
    "rietx.indexing.peakfit._H_WIDTH",
    "rietx.indexing.peakfit._SEED_GAUSS_FRACTION",
    "rietx.indexing.peakfit._SPARROW_DIP_MIN",
    "rietx.indexing.peaks.MIN_GROUP_POINTS",
    "rietx.indexing.peaks.TRIAL_GAP_STEPS",
    "rietx.indexing.peaks._LN2_8",
    "rietx.indexing.priors.CLASSIFY_ATOL_DEG",
    "rietx.indexing.priors.CLASSIFY_RTOL",
    "rietx.indexing.priors.MAX_PRIOR_INDEX",
    "rietx.indexing.priors.MAX_PRIOR_PASSES",
    "rietx.indexing.priors.PRIOR_DRIFT_MAX",
    "rietx.indexing.qspace._VOIGT_OF_AF",
    "rietx.indexing.quality.VOLUME_ENVELOPE_SLACK",
    "rietx.indexing.reduce.BRAVAIS_OBLIQUITIES",
    "rietx.indexing.reduce.BRAVAIS_SYMPREC_SIGMAS",
    "rietx.indexing.reduce.CELL_EQUALITY_CHI2",
    "rietx.indexing.reduce.CELL_EQUALITY_RELATIVE",
    "rietx.indexing.reduce.CELL_PINV_RCOND",
    "rietx.indexing.reduce.NIGGLI_EPS_RELATIVE",
    "rietx.indexing.reduce.SELLING_GATE_RELATIVE",
    "rietx.indexing.reduce.SELLING_GATE_SIGMAS",
    "rietx.indexing.reduce._SELLING_DEPTH",
    "rietx.indexing.reduce._SELLING_STEPS",
    "rietx.indexing.reduce._SETTING_STEPS",
    "rietx.indexing.reduce._SETTING_TIE",
    "rietx.indexing.svd.ANGLE_HI",
    "rietx.indexing.svd.ANGLE_LO",
    "rietx.indexing.svd.IMPURITY_CUT_DEG",
    "rietx.indexing.svd.KAPPA_PROBES",
    "rietx.indexing.svd.KAPPA_VOLUME",
    "rietx.indexing.svd.MAX_BOX_INDEX",
    "rietx.indexing.svd.MAX_ITERATIONS",
    "rietx.indexing.svd.NC_NO_HI",
    "rietx.indexing.svd.NC_NO_LO",
    "rietx.indexing.svd.TRIM_RETRY",
    "rietx.indexing.svd.VOLUME_LADDER_RATIO",
    "rietx.indexing.svd.WEIGHT_EXPONENT",
    "rietx.indexing.svd.ZERO_ERROR_LIMIT_DEG",
    "rietx.indexing.trial_error.BASE_INDEX_MAX",
    "rietx.indexing.trial_error.BASE_POOL_MIN",
    "rietx.indexing.trial_error.DOMINANT_ZONE_MAX_DOF",
    "rietx.indexing.trial_error.DOMINANT_ZONE_PROBE_LADDER",
    "rietx.indexing.trial_error.DOMINANT_ZONE_PROBE_SECONDS",
    "rietx.indexing.trial_error.MAX_ASSIGN_PER_BASE",
    "rietx.indexing.trial_error.SOLVE_CHUNK",
    "rietx.indexing.workflow.ABSENT_SIGMA",
    "rietx.indexing.workflow.ABSENT_WINDOW_FWHM",
    "rietx.indexing.workflow.VALIDATION_METRIC_REL",
    "rietx.indexing.workflow.VALIDATION_SLACK_BOUNDS_DEG",
    "rietx.indexing.workflow.index_pattern:cancel",
    "rietx.indexing.workflow.index_pattern:check_top",
    "rietx.indexing.workflow.index_pattern:data",
    "rietx.indexing.workflow.index_pattern:engines",
    "rietx.indexing.workflow.index_pattern:events",
    "rietx.indexing.workflow.index_pattern:formula",
    "rietx.indexing.workflow.index_pattern:instrument",
    "rietx.indexing.workflow.index_pattern:peaks",
    "rietx.indexing.workflow.index_pattern:preset",
    "rietx.indexing.workflow.index_pattern:quality",
    "rietx.indexing.workflow.index_pattern:shift_from_pairs",
    "rietx.indexing.workflow.index_pattern:spec",
    "rietx.indexing.workflow.index_pattern:temperature",
    "rietx.indexing.workflow.index_pattern:two_theta_limits",
    "rietx.indexing.workflow.index_pattern:validate",
    "rietx.io.formats.base.HEAD_BYTES",
    "rietx.io.formats.base.INTEGRAL_TOL",
    "rietx.io.formats.dif._MIN_ROWS",
    "rietx.io.formats.gsas.ESD_FIELD_CHARS",
    "rietx.io.formats.gsas.TIME_MAP_FIELD_CHARS",
    "rietx.io.formats.gsas._GSAS_TIME_MAP_SCAN_BYTES",
    "rietx.io.formats.peaklist._MIN_ROWS",
    "rietx.io.instrument_profile.INSTPRM_SHL_FLOOR",
    "rietx.io.instrument_profile._PRCF_TYPE_3",
    "rietx.io.instrument_profile._PRM_BANK",
    "rietx.io.instrument_profile._PRM_CENTIDEG",
    "rietx.io.instrument_profile._PRM_CENTIDEG_SQUARED",
    "rietx.io.instrument_profile._PRM_COEFFICIENT_COLUMNS",
    "rietx.io.instrument_profile._PRM_COEFFICIENT_DIGITS",
    "rietx.io.instrument_profile._PRM_CUTOFF",
    "rietx.io.instrument_profile._PRM_GAUSS_TO_DEG2",
    "rietx.io.instrument_profile._PRM_PER_RECORD",
    "rietx.io.projects.fullprof._CELL_TIE_MULTIPLIER_TOL",
    "rietx.io.projects.fullprof._DISPERSION_ATOL_E",
    "rietx.io.projects.fullprof._MAGNETIC_MATCH_ATOL",
    "rietx.io.projects.fullprof._NAM_WIDTH",
    "rietx.io.projects.fullprof._OCCUPANCY_RTOL",
    "rietx.io.projects.fullprof._RHOMBOHEDRAL_ANGLE_ATOL",
    "rietx.io.projects.fullprof._RHOMBOHEDRAL_LENGTH_RTOL",
    "rietx.io.projects.fullprof._USER_B_ATOL_FM",
    "rietx.io.projects.registry.INP_SNIFF_BYTES",
    "rietx.io.projects.topas_input.CALC_POINTS_PER_FWHM",
    "rietx.io.projects.topas_input.DEFAULT_RADIUS_MM",
    "rietx.io.projects.topas_input._SABINE_LAUE",
    "rietx.io.projects.topas_input._SABINE_XPOL",
    "rietx.io.projects.topas_input._TCH_ETA",
    "rietx.io.projects.topas_input._TCH_GAMMA",
    "rietx.io.readers.TWO_THETA_MAX_DEG",
    "rietx.optimize.identifiability.EXCHANGE_MIN_LOADING",
    "rietx.optimize.identifiability.SOFT_MODES_K",
    "rietx.optimize.identifiability.SOFT_MODE_MIN_LOADING",
    "rietx.optimize.identifiability.TOP_CORRELATIONS_K",
    "rietx.optimize.statistics.EFFECTIVE_OBS_ALPHA",
    "rietx.optimize.statistics.MAX_SHIFT_CONVERGED",
    "rietx.optimize.statistics.OBS_PER_PARAMETER_MIN",
    "rietx.optimize.statistics.OBS_PER_PARAMETER_PREFERRED",
    "rietx.refine.AIR_SCATTER_UNDECLARED_FRACTION",
    "rietx.refine.AIR_SCATTER_UNDECLARED_SCORE",
    "rietx.refine.DISPERSION_NEGLECT_FRAC",
    "rietx.refine.DISPERSION_NEGLECT_SEVERE",
    "rietx.refine.FLAT_PLATE_BIAS_MIN",
    "rietx.refine.FROZEN_COMPILE_CHI2_REL",
    "rietx.refine.HARMONIC_ABSENT_FRAC",
    "rietx.refine.HARMONIC_IMPLAUSIBLE_FRAC",
    "rietx.refine.LOW_ANGLE_MIN_CHANNELS",
    "rietx.refine.LOW_ANGLE_UNMODELLED_RATIO",
    "rietx.refine.MAGNETIC_TICK_PURITY",
    "rietx.refine.PAWLEY_UNRESOLVED_REL",
    "rietx.refine.RESONANT_ABSORBER_SEVERE_BARN",
    "rietx.refine.RESTRAINT_TENSION_SIGMA",
    "rietx.refine.ROUGHNESS_MIN_DEPRESSION",
    "rietx.refine.Refinement.run_stage:correlation_guard",
    "rietx.refine.SIZE_FLAG_SIZE_A",
    "rietx.refine.STRAIN_FLAG_WIDTH",
    "rietx.refine._CENTROID_SITES_NAMED",
    "rietx.refine._dedup_high_correlations.suggestion",
    "rietx.report.body_misfit.MISFIT_ALPHA",
    "rietx.report.body_misfit.MISFIT_BIC",
    "rietx.report.layer0.LAYER0_MATCH_TOL_DEG",
    "rietx.report.layer2.BACKGROUND_INCREASE_CAP",
    "rietx.report.layer2.IMPURITY_SIGMA",
    "rietx.report.layer2.TEXTURE_AXIS_AMBIGUITY",
    "rietx.report.localisation.SPLIT_TOLERANCE_DEG",
    "rietx.report.magnetic._MAGNETIC_WIDTH_FLOOR_DEG",
    "rietx.report.satellites._FWHM_FALLBACK_DEG",
    "rietx.report.schemas.BACKGROUND_ABSORPTION_NOTABLE",
    "rietx.report.schemas.COLLECT_DATA_CONFIDENCE",
    "rietx.report.schemas.CONTENTS_MAX_TEMPLATE_R2",
    "rietx.report.schemas.CONTENTS_MIN_INTENSITY_SHARE",
    "rietx.report.schemas.CONTENTS_MIN_REGIONS",
    "rietx.report.schemas.CONTENTS_MIN_SIGN_MINORITY",
    "rietx.report.schemas.EXCHANGEABLE_MIN_R2",
    "rietx.report.schemas.EXCHANGE_PARTNER_MIN_SIGNIFICANCE",
    "rietx.report.schemas.IMPURITY_SHIFT_CAP",
    "rietx.report.schemas.LEBAIL_GAP_CYCLES",
    "rietx.report.schemas.LEBAIL_GAP_NOTABLE",
    "rietx.report.schemas.MAGNETIC_WIDTH_MIN_REFLECTIONS",
    "rietx.report.schemas.MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA",
    "rietx.report.schemas.MAGNETIC_WIDTH_PURITY",
    "rietx.report.schemas.MAGNETIC_WIDTH_SIGMA",
    "rietx.report.schemas.MAGNETIC_WIDTH_TAIL_FWHM",
    "rietx.report.schemas.MATURITY_MAX_RWP",
    "rietx.report.schemas.MATURITY_MIN_EXPLAINED_FRACTION",
    "rietx.report.schemas.MATURITY_MIN_MISFIT_SHARE",
    "rietx.report.schemas.MAX_GRAM_CONDITION",
    "rietx.report.schemas.MIN_COEF_SIGNIFICANCE",
    "rietx.report.schemas.MIN_REGION_CHI2_RED",
    "rietx.report.schemas.MIN_REGION_R2",
    "rietx.report.schemas.MOMENT_PAIR_RHO_MIN",
    "rietx.report.schemas.MOMENT_SUPPORT_SIGMA",
    "rietx.report.schemas.OFF_REGION_CHI2_RED_HIGH",
    "rietx.report.schemas.OFF_REGION_DW_LOW",
    "rietx.report.schemas.REINDEX_MIN_FAR_FRACTION",
    "rietx.report.schemas.REINDEX_MIN_FAR_REGIONS",
    "rietx.report.schemas.RESOLUTION_LIMITED_MIN_FRACTION",
    "rietx.report.schemas.RESOLUTION_LIMITED_MIN_R2",
    "rietx.report.schemas.RESOLUTION_LIMITED_MIN_REGIONS",
    "rietx.report.schemas.RIVAL_DECISIVE_MIN_CHI2_RATIO",
    "rietx.report.schemas.SEPARABILITY_MIN_SS_RATIO",
    "rietx.report.schemas.SHIFT_PAIR_WINDOW_DEG",
    "rietx.report.schemas.SHIFT_TICK_PROXIMITY_FWHM",
    "rietx.report.schemas.SOFT_MODE_NOTABLE_EIGENVALUE",
    "rietx.report.schemas.STRAIN_MAX_GRAM_CONDITION",
    "rietx.report.schemas.STRAIN_MIN_ANISOTROPY",
    "rietx.report.schemas.STRAIN_MIN_R2",
    "rietx.report.schemas.STRAIN_MIN_REFLECTIONS",
    "rietx.report.schemas.TEXTURE_IMPURITY_MARGIN",
    "rietx.report.schemas.TEXTURE_MIN_R2",
    "rietx.report.schemas.TEXTURE_MIN_REFLECTIONS",
    "rietx.report.schemas.TEXTURE_MIN_STRENGTH",
    "rietx.report.schemas.TRAJECTORY_MAX_ACTIONS",
    "rietx.report.schemas.VALIDITY_RADIUS_FWHM",
    "rietx.report.strain._C",
    "rietx.report.strain._GAUSS_NEWTON_ITERATIONS",
    "rietx.report.strain._QUOTABLE_WEIGHT_FRAC",
    "rietx.report.texture._EQUIV_REF_R",
    "rietx.schemas.indexing.INDEX_MIN_INDEXED_FRACTION",
    "rietx.schemas.indexing.MAX_RELATIVE_SIGMA_Q",
    "rietx.schemas.indexing.MIN_LINES_PER_DOF",
    "rietx.schemas.indexing.PAIR_CLUSTER_HALF_WIDTH_DEG",
    "rietx.schemas.indexing.PAIR_MAX_M",
    "rietx.schemas.indexing.PAIR_MAX_P",
    "rietx.schemas.indexing.PAIR_MIN_CLUSTERED",
    "rietx.schemas.indexing.PAIR_MIN_Z",
    "rietx.schemas.indexing.PAIR_NULL_REPLICATES",
    "rietx.schemas.indexing.PAIR_REFUTE_K_FRACTION",
    "rietx.schemas.indexing.PAIR_WINDOW_DEG",
    "rietx.schemas.indexing.PEAK_ALIAS_RATIO_RANGE",
    "rietx.schemas.indexing.PEAK_ALIAS_TOL_FWHM_FRAC",
    "rietx.schemas.indexing.PEAK_ASSUMED_ESD_DEG",
    "rietx.schemas.indexing.PEAK_ASYMMETRY_MIN_SIGMA",
    "rietx.schemas.indexing.PEAK_AXIAL_TAIL_MAX_FWHM",
    "rietx.schemas.indexing.PEAK_DETECT_SEPARATION_FWHM_FRAC",
    "rietx.schemas.indexing.PEAK_FDR_Q",
    "rietx.schemas.indexing.PEAK_KEEP_COMPONENT_MIN_DELTA_BIC",
    "rietx.schemas.indexing.PEAK_MAX_RESEED_PASSES",
    "rietx.schemas.indexing.PEAK_MIN_HEIGHT_SIGMA",
    "rietx.schemas.indexing.PEAK_MIN_PROMINENCE_SIGMA",
    "rietx.schemas.indexing.PEAK_MIN_USABLE_LINES",
    "rietx.schemas.indexing.PEAK_NO_INTENSITY_SIGMA",
    "rietx.schemas.indexing.PEAK_POSITION_BOUND_FWHM",
    "rietx.schemas.indexing.PEAK_POSITION_ESD_MAX_DEG",
    "rietx.schemas.indexing.PEAK_REFUTED_SIGMA",
    "rietx.schemas.indexing.PEAK_SATELLITE_MAX_RATIO",
    "rietx.schemas.indexing.PEAK_SATELLITE_NEAR_FWHM",
    "rietx.schemas.indexing.PEAK_SHOULDER_MIN_SIGMA",
    "rietx.schemas.indexing.PEAK_WIDTH_BOUND_FACTORS",
    "rietx.schemas.indexing.PEAK_WIDTH_CENSUS_N",
    "rietx.schemas.indexing.PEAK_WIDTH_SCALE_BOUNDS",
    "rietx.schemas.indexing.PEAK_WINDOW_FWHM_MULT",
    "rietx.schemas.indexing.SHIFT_ALLOWANCE_K_ESD",
    "rietx.schemas.indexing.SMITH_VOLUME_C1",
    "rietx.schemas.indexing.SMITH_VOLUME_C2",
    "rietx.schemas.instrument.EXTRA_PEAK_FWHM_MIN",
    "rietx.schemas.instrument.HUMP_FWHM_MIN",
    "rietx.schemas.plan.CORRELATION_GUARD",
    "rietx.schemas.plan.PlanSpec:correlation_guard",
    "rietx.schemas.results.HIGH_CORRELATION_MAX",
    "rietx.schemas.results._cap_one_code.suggestion",
    "rietx.schemas.sequential.SeriesEntry.reseeded",
    "rietx.schemas.sequential.SeriesEntry.rung",
    "rietx.schemas.sequential.SeriesEntry.rungs_raised",
    "rietx.schemas.sequential.SeriesEntry.rungs_tried",
    "rietx.schemas.sequential.SeriesEntry.rwp_fence",
    "rietx.schemas.suggest.SUGGEST_ABSORPTION_MAX",
    "rietx.schemas.suggest.SUGGEST_GROUP_R2",
    "rietx.schemas.suggest.SUGGEST_MIN_GAIN",
    "rietx.sequential.DISCONTINUITY_FACTOR",
    "rietx.sequential.DISCONTINUITY_SIGMA",
    "rietx.sequential.FIRST_RUNG_FACTOR",
    "rietx.sequential.FIRST_RUNG_SAMPLES",
    "rietx.sequential.MIN_POINTS_FOR_DISCONTINUITY",
    "rietx.sequential.MIN_POINTS_FOR_PERSISTENCE",
    "rietx.sequential.NOISE_FLOOR_REL",
    "rietx.sequential.PATH_DEPENDENCE_SIGMA",
    "rietx.sequential.RESEED_FACTOR",
    "rietx.sequential.SequentialRefinement.fit:cancel",
    "rietx.sequential.SequentialRefinement.fit:constrain",
    "rietx.sequential.SequentialRefinement.fit:direction",
    "rietx.sequential.SequentialRefinement.fit:events",
    "rietx.sequential.SequentialRefinement.fit:first_rung_factor",
    "rietx.sequential.SequentialRefinement.fit:label",
    "rietx.sequential.SequentialRefinement.fit:labels",
    "rietx.sequential.SequentialRefinement.fit:mode",
    "rietx.sequential.SequentialRefinement.fit:on_error",
    "rietx.sequential.SequentialRefinement.fit:on_result",
    "rietx.sequential.SequentialRefinement.fit:plan",
    "rietx.sequential.SequentialRefinement.fit:prepare",
    "rietx.sequential.SequentialRefinement.fit:progress",
    "rietx.sequential.SequentialRefinement.fit:refit",
    "rietx.sequential.SequentialRefinement.fit:reseed",
    "rietx.sequential.SequentialRefinement.fit:reseed_factor",
    "rietx.sequential.SequentialRefinement.fit:telemetry",
    "rietx.sequential.SequentialRefinement.fit:two_theta_limits",
    "rietx.sequential.SequentialRefinement.fit:verify_discontinuities",
    "rietx.sequential.SequentialRefinement.fit:x",
    "rietx.sequential.SequentialRefinement.fit:x_label",
    "rietx.sequential.WIDTH_GROWTH_FACTOR",
    "rietx.sequential.WIDTH_GROWTH_GOF_FACTOR",
    "rietx.sequential.WIDTH_GROWTH_SIGMA",
    "rietx.sequential.refine_sequential:backend",
    "rietx.sequential.refine_sequential:carry",
    "rietx.sequential.refine_sequential:carry_hkl_intensities",
    "rietx.sequential.refine_sequential:history",
    "rietx.sequential.refine_sequential:solver",
    "rietx.solve.cost.NAMED_REFLECTIONS",
    "rietx.solve.cost.NUISANCE_RCOND",
    "rietx.strategy.magnetic.SOLVE_D_MIN",
    "rietx.strategy.staged.BACKGROUND_ABSORPTION_GUARD",
    "rietx.strategy.staged.HUMP_MIN_WIDTH_MULT",
    "rietx.strategy.staged.ROUGHNESS_ABSORPTION_GUARD",
    "rietx.strategy.suggest.SUGGEST_SEED_ROUGHNESS",
)
