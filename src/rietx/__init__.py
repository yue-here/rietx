"""rietx: Python-API-first analysis and Rietveld refinement of powder diffraction data."""

import difflib
import importlib
import inspect
import pkgutil

from . import schemas

# The background estimator and the model-free pattern diagnostics were reachable
# only as ``rietx.background.auto_background`` — this module never imported
# ``background`` at all — so the two calls a client makes *before* its first fit
# were the two it had to go digging for (WP-1007).  Remember the invariant: an
# estimated background is held additively or co-refined under a penalty, never
# subtracted.
from .background import auto_background, diagnose
from .capabilities import capabilities
from .crystallography.cif import format_su
from .help import HelpEntry, help_for, help_key_for, help_registry
from .history import RefinementTree
from .indexing import determine_extinction_symbol, index_pattern, pick_peaks
from .io.exporters import (
    ReflectionRow,
    reflection_table,
    write_qpa_table,
    write_refinement_cif,
    write_reflection_table,
)
from .io.instrument_profile import (
    load_instrument_profile,
    read_gsas_prm,
    save_instrument_profile,
)
from .io.readers import read_pattern, read_pdcif
from .io.recipe import Recipe, RecipeError, read_recipe, write_recipe_tables
from .multi import MultiHistogramRefinement, refine_multi
from .optimize.cancel import CancelToken, RefinementCancelled
from .params.multi import SharingMap
from .project import Project

# ``__version__`` is the universal python spelling of "what am I running", and
# it raised AttributeError here until WP-1110 — the first thing anyone types,
# answered only by ``capabilities().package_version``, which a caller reaches
# by already knowing about ``capabilities()``.  Re-exported rather than
# recomputed: ``refine`` resolves it once from ``importlib.metadata`` at import
# and every ``Provenance``, ``TreeHeader`` and ``project.json`` is stamped from
# that same string, so a second lookup here could disagree with what a result
# says produced it.
from .refine import _VERSION as __version__
from .refine import NoPhasesError, Refinement, estimate_mu_r, refine, replay
from .report import FitReport, RegionAttribution, SuggestedAction, build_report
from .schemas import (
    AnisoU,
    Atom,
    Cell,
    Instrument,
    Parameter,
    PatternData,
    Phase,
    PreferredOrientation,
    RefinementResult,
    Structure,
)
from .schemas.history import HistoryNode, NodeAction, RefinementState
from .schemas.indexing import (
    CellCandidate,
    ExtinctionCandidate,
    ExtinctionScreen,
    IndexingResult,
    LeBailValidation,
    PeakList,
)
from .schemas.params import ParameterRow, TieSpec
from .schemas.plan import PlanSpec, StageSpec
from .schemas.project import DataRef, ProjectDoc
from .schemas.sequential import SeriesEntry, SeriesResult, Trajectory
from .schemas.suggest import CandidateGroup, ParameterCandidate, SuggestionResult
from .sequential import SequentialRefinement, refine_sequential
from .strategy.staged import (
    PLAN_INFO,
    PLAN_PRESETS,
    GuardFinding,
    PlanInfo,
    RefinementPlan,
    Stage,
)

__all__ = [
    "__version__",
    "AnisoU",
    "Atom",
    "CancelToken",
    "CandidateGroup",
    "Cell",
    "CellCandidate",
    "DataRef",
    "FitReport",
    "GuardFinding",
    "HelpEntry",
    "HistoryNode",
    "Instrument",
    "ExtinctionCandidate",
    "ExtinctionScreen",
    "IndexingResult",
    "MultiHistogramRefinement",
    "NoPhasesError",
    "NodeAction",
    "PLAN_INFO",
    "PLAN_PRESETS",
    "LeBailValidation",
    "Parameter",
    "ParameterCandidate",
    "ParameterRow",
    "PatternData",
    "PeakList",
    "Phase",
    "PlanInfo",
    "PlanSpec",
    "PreferredOrientation",
    "Project",
    "ProjectDoc",
    "Recipe",
    "RecipeError",
    "Refinement",
    "RefinementCancelled",
    "RefinementPlan",
    "RefinementResult",
    "RefinementState",
    "RefinementTree",
    "ReflectionRow",
    "RegionAttribution",
    "SequentialRefinement",
    "SeriesEntry",
    "SeriesResult",
    "SharingMap",
    "Stage",
    "StageSpec",
    "Structure",
    "TieSpec",
    "Trajectory",
    "SuggestedAction",
    "SuggestionResult",
    "auto_background",
    "build_report",
    "capabilities",
    "diagnose",
    "format_su",
    "help_for",
    "help_key_for",
    "help_registry",
    "determine_extinction_symbol",
    "index_pattern",
    "load_instrument_profile",
    "pick_peaks",
    "read_gsas_prm",
    "read_pattern",
    "read_pdcif",
    "read_recipe",
    "reflection_table",
    "refine",
    "refine_sequential",
    "refine_multi",
    "replay",
    "save_instrument_profile",
    "write_qpa_table",
    "estimate_mu_r",
    "write_recipe_tables",
    "write_reflection_table",
    "write_refinement_cif",
]


def _schema_classes() -> dict[str, type]:
    """Every class ``rietx.schemas.*`` defines, keyed by name.

    Walked rather than typed (WP-1302): a class the manual already names in
    prose — ``Source``, ``EmissionLine``, ``BackgroundChebyshev``, ``Geometry``,
    the profile blocks — was reachable through an existing export's own
    fields but not importable by that name (``from rietx import Source``
    raised, verified 2026-08-28), because nothing forced this list to grow
    with the schema. No two submodules define the same class name (pinned by
    ``tests/test_schemas.py``'s meta-test), so last-writer-wins here is never
    live.
    """
    from .schemas.common import Base

    found: dict[str, type] = {}
    for info in pkgutil.iter_modules(schemas.__path__):
        module = importlib.import_module(f"{schemas.__name__}.{info.name}")
        for name, obj in vars(module).items():
            if (not name.startswith("_") and inspect.isclass(obj)
                    and obj.__module__ == module.__name__ and issubclass(obj, Base)):
                found[name] = obj
    return found


for _name, _cls in _schema_classes().items():
    globals().setdefault(_name, _cls)
    if _name not in __all__:
        __all__.append(_name)
del _name, _cls


#: A name ``difflib`` below cannot help with, answered with where the thing
#: actually is.  Two kinds qualify, both real: a miss that is really one level
#: down under a *different* name than the one reached for
#: (``identify_format``, WP-1302 — an agent wanted "what format is this", the
#: function of that name lives in ``io.readers``, but the more useful landmark
#: for that question is the registry it reads); and a name this package
#: **used** to export (``agent``, deleted in WP-1303), where the miss is a
#: caller written against an older release and the useful answer is what
#: replaces it, not a spelling.
_TOP_LEVEL_HINTS: dict[str, str] = {
    "identify_format": "it lives one level down: rietx.io.readers.PATTERN_FORMATS",
    "agent": ("removed in v1.3 — call rietx.refine() or Refinement.fit() and "
              "dump the answer with result.model_dump(mode='json'); the "
              "envelope's ok:false is now a raised ValueError/RuntimeError"),
}


def __getattr__(name: str) -> object:
    """PEP 562: a missing top-level name answered with where it actually is.

    Two kinds of miss reach here.  A public submodule nothing above imported
    eagerly (``rietx.viz``, ``rietx.gui``, …) is imported on first touch —
    paying an import for every submodule up front is not the fix for typing
    ``rietx.viz``, and the root CLAUDE.md's own commands write it that way.
    Anything else gets the closest match against the top-level surface
    (``difflib``, cutoff 0.6), falling back to one curated pointer for a name
    that exists but answers to a different address, and failing that the
    plain ``ImportError``-shaped message untouched.

    A submodule that exists but fails to import for its own reason — ``viz``
    and ``gui`` both pull in optional dependencies (``matplotlib``,
    ``plotly``) that a minimal install does not have — raises
    ``AttributeError`` rather than letting the underlying
    ``ModuleNotFoundError`` escape: the two look identical from outside
    (``rietx.viz`` is not there either way), but only ``AttributeError`` is
    what ``hasattr``/``getattr(default=)`` catch, and a caller checking
    "is this built with plotting support" before touching it must not crash
    instead of getting ``False``.  The original exception rides along as
    ``__cause__``, so nothing about *why* is actually hidden.
    """
    if not name.startswith("_"):
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"{__name__}.{name}":
                pass  # no such submodule at all — falls through below
            else:
                raise AttributeError(
                    f"rietx.{name} exists but failed to import: {exc}. A "
                    "dependency it needs is probably missing — see "
                    "pyproject.toml's [project.optional-dependencies] for "
                    "the extra that provides it") from exc
        else:
            globals()[name] = module
            return module
    plain = f"module {__name__!r} has no attribute {name!r}"
    if name.startswith("_"):
        raise AttributeError(plain)
    extra = _TOP_LEVEL_HINTS.get(name)
    if extra:
        raise AttributeError(f"{plain}; {extra}")
    close = difflib.get_close_matches(name, __all__, n=3, cutoff=0.6)
    if close:
        raise AttributeError(f"{plain}; did you mean {', '.join(close)!r}?")
    raise AttributeError(plain)
