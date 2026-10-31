# The manual's build settings that the tests read too (WP-1978): the fenced
# constants, the citation style, the diagram theme, the tutorial copy and the
# `{source}` role.  `docs/docs/conf.py` imports this module.  It is not a
# conf.py itself, because importing a conf.py would also write the Reference
# bodies, copy the tutorials and set the tree's whole Sphinx config.  (It
# served two trees until WP-1986 retired the old one in docs/manual/.)
#
# Anti-divergence rule (WP-0604): a threshold or fenced constant is never
# typed into a chapter.  It is imported here from the live package and exposed
# as a MyST substitution ({{ BRINDLEY_MU_R_FENCE }} etc.), so a renamed or
# retuned constant fails the -W build instead of leaving a stale number in
# print.  Prose derivations stay in the module docstrings; chapters carry the
# numbered equations and point at their source symbols.

import dataclasses as _dataclasses
import importlib as _importlib
import importlib.util as _importlib_util
import inspect as _inspect
import os as _os
import re as _re
import shutil as _shutil
from pathlib import Path as _Path

import sphinxcontrib.bibtex.plugin as _bibtex_plugin
from docs_versions import docs_version
from docutils import nodes as _nodes
from sphinxcontrib.bibtex.style.referencing import BracketStyle
from sphinxcontrib.bibtex.style.referencing.author_year import AuthorYearReferenceStyle

from rietx import __version__
from rietx._about import REPO_URL
from rietx.crystallography.atomic_volume import VOLUME_RATIO_BOUNDS, VOLUME_SCATTER
from rietx.crystallography.dispersion import NEAR_EDGE_EV
from rietx.crystallography.magnetic.moments import MOMENT_DIRECTION_SUPPORT
from rietx.crystallography.representation.distortion import DISTORTION_SEED
from rietx.crystallography.scattering import _itc_handover
from rietx.crystallography.superspace import (
    ITC_C_EXCEPTIONS,
    N_MAGNETIC_SUPERSPACE_GROUPS_D1,
    N_BRAVAIS_CLASSES_D1,
    N_SUPERSPACE_GROUPS_D1,
)
from rietx.crystallography.symmetry import SYMMETRY_ANGLE_TOL_DEG
from rietx.examples import list_examples
from rietx.gui.textdoc import FORMAT_VERSION as RXT_FORMAT_VERSION
from rietx.gui.textdoc import VALUE_DIGITS as RXT_VALUE_DIGITS
from rietx.indexing.ambiguity import MAX_AMBIGUITY_INDEX, SUPERCELL_CHANCE_ALPHA
from rietx.indexing.diagnostics import Z_INTEGER_TOLERANCE
from rietx.indexing.extinction import DENSITY_Z_TOLERANCE
from rietx.indexing.dichotomy import ANGLE_STEP_DEG, AXIS_STEP
from rietx.indexing.engines import (
    DEFAULT_N_UNINDEXED,
    DEFAULT_SEARCH_LINES,
    SEARCH_POOL_MULTIPLE,
)
from rietx.indexing.reduce import NIGGLI_EPS_RELATIVE
from rietx.model.absorption import CYLINDER_MU_R_MAX
from rietx.model.forward import PAWLEY_OVERLAP_FWHM_FRAC, PHASE_SUPPORT_SIGMA, WINDOW_AREA_TOL
from rietx.model.geometry import (
    ANGLE_LINEARISATION_LIMIT_DEG,
    VARIANCE_CANCELLATION_FLOOR,
)
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2
from rietx.model.profiles.fcj import (
    CLOSING_NODES_PER_FWHM,
    CLOSING_SKIP_EXTENT_FWHM_RATIO,
    NODES_PER_FWHM,
    SKIP_EXTENT_FWHM_RATIO,
)
from rietx.optimize.least_squares import STATIONARY_ANGLE_LEVEL
from rietx.optimize.qpa import BRINDLEY_MU_R_FENCE
from rietx.optimize.statistics import (
    EFFECTIVE_OBS_ALPHA,
    MAX_SHIFT_CONVERGED,
    OBS_PER_PARAMETER_MIN,
    OBS_PER_PARAMETER_PREFERRED,
    PINV_RCOND,
)
from rietx.params.parametric import FORM_TEST_LEVEL
from rietx.params.vector import SIZE_CAP_RANGE_FRACTION, STRAIN_CAP_RANGE_FRACTION
from rietx.refine import SCALE_B_SEPARATION_FLOOR, SIZE_FLAG_SIZE_A, STRAIN_FLAG_WIDTH
from rietx.report.layer0 import LAYER0_MATCH_TOL_DEG, build_layer0
from rietx.report.layer2 import IMPURITY_SIGMA
from rietx.report.schemas import (
    MATURITY_MAX_RWP,
    MATURITY_MIN_EXPLAINED_FRACTION,
    MATURITY_MIN_MISFIT_SHARE,
    MAX_GRAM_CONDITION,
    MIN_COEF_SIGNIFICANCE,
    MIN_REGION_CHI2_RED,
    MIN_REGION_R2,
    SEPARABILITY_MIN_SS_RATIO,
    THRESHOLDS_VERSION,
    VALIDITY_RADIUS_FWHM,
)
from rietx.schemas.fraction import FRACTION_PROFILE_DCHI2
from rietx.schemas.indexing import MAX_RELATIVE_SIGMA_Q, MIN_LINES_PER_DOF
from rietx.schemas.interval import PARAMETER_INTERVAL_MAX_REFITS
from rietx.schemas.plan import CLOSING_WINDOW_TOL
from rietx.schemas.structure import RIGID_BODY_OVERLAP_FACTOR
from rietx.schemas.suggest import SUGGEST_MIN_GAIN
from rietx.strategy.staged import HUMP_MIN_WIDTH_MULT

#: The repository root, which is what a blob URL's path is relative to.
REPO_ROOT = _Path(__file__).resolve().parents[1]

#: The bibliography the manual cites from.
BIBFILE = REPO_ROOT / "docs" / "docs" / "references.bib"

MYST_EXTENSIONS = ["dollarmath", "amsmath", "substitution", "colon_fence", "deflist"]

# Diagrams render in the browser (`raw` output needs no mermaid-cli at build
# time).  The extension detects the active theme itself and re-renders on a
# MutationObserver when the toggle moves, so these two names are the whole
# light/dark story.  It reads a `dark`/`light` class or `data-theme` on *either*
# `html` or `body` and falls back to `prefers-color-scheme`, which covers
# pydata-sphinx-theme's `html[data-theme]`: WP-1412 drove all four of its
# spellings and the diagrams followed every one.  mermaid.js itself comes from a CDN when the page
# is *viewed*; set `mermaid_use_local` if a built copy of the manual has to
# render diagrams offline.
#
# The colours are the site's tokens, set by the manual's `custom.css` over
# whatever mermaid draws (WP-2021): mermaid's `base` theme takes its variables
# as literal colours, one set for both themes, which cannot follow a toggle.
# `neutral` is the light theme so a part the stylesheet misses is grey rather
# than the stock theme's lilac.
MERMAID_LIGHT_THEME = "neutral"
MERMAID_DARK_THEME = "dark"
# Without the title margin, a subgraph label is drawn on the cluster border and
# collides with the first node inside it.
MERMAID_INIT_CONFIG = {
    "startOnLoad": False,
    "flowchart": {"subGraphTitleMargin": {"top": 6, "bottom": 12}},
}


# ----------------------------------------------------------------------
# Citations
#
# `alpha` still formats and sorts the list, by author then year, which is the
# order an author-year reference list wants.  What changes is the citation:
# `author_year` renders it as [Boultif and Louër, 1991] instead of [BL91a].
# The manual cites 105 distinct works across 150 citations, so a reader meets
# almost every label once and builds no memory of it, and 143 of those
# citations carry no author name in the prose beside them.  The bibliography
# also sits on a different page from all but one citation, so decoding a label
# costs a navigation.  61 % of the entries are crystallography journals, whose
# own house style is name-date.  WP-1408 § G3 has the numbers, the numeric
# styles it rules out and what each renders.
# ----------------------------------------------------------------------

BIBTEX_DEFAULT_STYLE = "alpha"
BIBTEX_REFERENCE_STYLE = "author_year_semicolon"


def _bracket_style() -> BracketStyle:
    """A semicolon between works in one citation, and square brackets kept.

    Registering a subclassed reference style from `conf.py` is what
    sphinxcontrib-bibtex § Custom Formatting documents for this. Fourteen of
    the 150 citations name more than one work, and `BracketStyle.sep` defaults
    to a comma, which is also what separates an author from its year: three
    works came out as one flat list of six comma-separated fragments.

    The brackets stay square, which is the library default. Name-date
    convention is round, and round was measured on this tree first: ten
    citations sit inside a parenthetical the prose already opened, so round
    brackets print `((Prince, 2004) eq. 6.3.3.1)` and nine more like it. A
    square bracket nests inside a parenthesis without collision, which is why
    house styles that cite by name-date inside parentheses use one.
    """
    return BracketStyle(sep="; ", sep2="; ", last_sep="; ")


@_dataclasses.dataclass
class _AuthorYearSemicolon(AuthorYearReferenceStyle):
    bracket_textual: BracketStyle = _dataclasses.field(default_factory=_bracket_style)
    bracket_parenthetical: BracketStyle = _dataclasses.field(default_factory=_bracket_style)
    bracket_author: BracketStyle = _dataclasses.field(default_factory=_bracket_style)
    bracket_label: BracketStyle = _dataclasses.field(default_factory=_bracket_style)
    bracket_year: BracketStyle = _dataclasses.field(default_factory=_bracket_style)


_bibtex_plugin.register_plugin(
    "sphinxcontrib.bibtex.style.referencing", BIBTEX_REFERENCE_STYLE, _AuthorYearSemicolon
)


# ----------------------------------------------------------------------
# The fenced constants, as MyST substitutions
#
# The conf.py adds `release` and `N_TUTORIALS` (the count
# `copy_tutorials` below returns), since those are facts about the build
# rather than about the package.
# ----------------------------------------------------------------------

MYST_SUBSTITUTIONS = {
    # An angle's esd is withheld this close to 0°/180°; the raw value carries
    # fifteen digits of an arccos clamp, so it is formatted rather than typed —
    # still derived, and a retuned clamp still moves the printed number.
    "ANGLE_LINEARISATION_LIMIT_DEG": f"{ANGLE_LINEARISATION_LIMIT_DEG:.1e}",
    "HUMP_MIN_WIDTH_MULT": HUMP_MIN_WIDTH_MULT,
    # a declared peak this close to a predicted position sits on it, and the
    # report matches an observed peak to a tick by the same distance
    "LAYER0_MATCH_TOL_DEG": LAYER0_MATCH_TOL_DEG,
    "BRINDLEY_MU_R_FENCE": BRINDLEY_MU_R_FENCE,
    "FRACTION_PROFILE_DCHI2": FRACTION_PROFILE_DCHI2,
    "PARAMETER_INTERVAL_MAX_REFITS": PARAMETER_INTERVAL_MAX_REFITS,
    "CYLINDER_MU_R_MAX": CYLINDER_MU_R_MAX,
    "EFFECTIVE_OBS_ALPHA": EFFECTIVE_OBS_ALPHA,
    "MAX_SHIFT_CONVERGED": MAX_SHIFT_CONVERGED,
    # the Γ_G² clamp, which is also the Caglioti W's floor and the LM rows' bound
    "MIN_GAMMA_G2": f"{_MIN_GAMMA_G2:.0e}",
    "OBS_PER_PARAMETER_MIN": OBS_PER_PARAMETER_MIN,
    "OBS_PER_PARAMETER_PREFERRED": OBS_PER_PARAMETER_PREFERRED,
    "VARIANCE_CANCELLATION_FLOOR": VARIANCE_CANCELLATION_FLOOR,
    # the covariance's pinv cut and the scale-B floor derived from it
    # (WP-1534); formatted, the floor being an irrational sqrt
    "PINV_RCOND": f"{PINV_RCOND:.0e}",
    # the moment-direction floor both the hold and the stationary-angle test
    # read, and that test's level (WP-1929)
    "MOMENT_DIRECTION_SUPPORT": f"{MOMENT_DIRECTION_SUPPORT:.0e}",
    "DISTORTION_SEED": f"{DISTORTION_SEED:g}",
    "STATIONARY_ANGLE_LEVEL": STATIONARY_ANGLE_LEVEL,
    # the parametric form test's level (WP-1325)
    "PARAMETRIC_FORM_LEVEL": FORM_TEST_LEVEL,
    "SCALE_B_SEPARATION_FLOOR": f"{SCALE_B_SEPARATION_FLOOR:.1e}",
    "DEFAULT_N_UNINDEXED": DEFAULT_N_UNINDEXED,
    "DEFAULT_SEARCH_LINES": DEFAULT_SEARCH_LINES,
    "SEARCH_POOL_MULTIPLE": SEARCH_POOL_MULTIPLE,
    "IMPURITY_SIGMA": IMPURITY_SIGMA,
    "ANGLE_STEP_DEG": ANGLE_STEP_DEG,
    "AXIS_STEP": AXIS_STEP,
    "MAX_AMBIGUITY_INDEX": MAX_AMBIGUITY_INDEX,
    "MAX_RELATIVE_SIGMA_Q": MAX_RELATIVE_SIGMA_Q,
    "MIN_LINES_PER_DOF": MIN_LINES_PER_DOF,
    # the formula-volume window and the Z check (WP-1510): the scatter of one
    # crystal, the ratio bounds the window takes, the tolerance at twice the
    # scatter, and the Z above which every value is within it of a whole number
    "VOLUME_SCATTER_PCT": f"{VOLUME_SCATTER * 100:.2f}",
    "VOLUME_RATIO_LOW": f"{VOLUME_RATIO_BOUNDS[0]:g}",
    "VOLUME_RATIO_HIGH": f"{VOLUME_RATIO_BOUNDS[1]:g}",
    "Z_INTEGER_TOLERANCE_PCT": f"{Z_INTEGER_TOLERANCE * 100:g}",
    "DENSITY_Z_TOLERANCE_PCT": f"{DENSITY_Z_TOLERANCE * 100:g}",
    # two whole numbers fit a window of ±DENSITY_Z_TOLERANCE·Z once Z passes this
    "DENSITY_Z_AMBIGUOUS_ABOVE": f"{0.5 / DENSITY_Z_TOLERANCE:g}",
    "Z_CHECK_SILENT_ABOVE": f"{0.5 / Z_INTEGER_TOLERANCE:g}",
    # How many example projects the wheel carries.  A *count* in prose is the
    # same class of stale number as a retuned threshold, and it rots the same
    # silent way: `using/first-refinement.md` said "Three" while the page's own
    # listing showed two, because a standard whose data may not ship in the
    # wheel leaves `list_examples()` and nothing reads the sentence again.
    "N_EXAMPLES": len(list_examples()),
    # The (3+1)D counts the superspace chapter quotes (#682 review): the
    # literature counts the tests pin, and how many printed symbols ITC-C
    # spells differently from the Stokes 2011 § 5.2 convention.
    "N_SUPERSPACE_GROUPS_D1": N_SUPERSPACE_GROUPS_D1,
    "N_BRAVAIS_CLASSES_D1": N_BRAVAIS_CLASSES_D1,
    "N_ITC_C_EXCEPTIONS": len(ITC_C_EXCEPTIONS),
    # Stokes & Campbell 2022 Table 6's d = 1 magnetic count (WP-1992).
    "N_MAGNETIC_SUPERSPACE_GROUPS_D1": N_MAGNETIC_SUPERSPACE_GROUPS_D1,
    # The `.rxt` document's own version and precision (WP-1009 asked for this
    # explicitly: a format bump that misses the manual must fail the docs
    # build).  `gui-power.md` states the grammar normatively, so both numbers
    # are quoted from the parser rather than typed beside it.
    "RXT_FORMAT_VERSION": RXT_FORMAT_VERSION,
    "RXT_VALUE_DIGITS": RXT_VALUE_DIGITS,
    # The Rwp past which Layer 1 abstains and the GUI header wears
    # `⚠ not a fit yet`.  The GUI chapters state it, so it is injected for the
    # same reason every other threshold here is: a retune must move the page.
    "MATURITY_MAX_RWP": MATURITY_MAX_RWP,
    # Layer 1's other gates, which the Concepts page on the report states.
    # Shares are quoted as percentages and the Gram bound as a whole number.
    "MATURITY_MIN_EXPLAINED_PCT": f"{100 * MATURITY_MIN_EXPLAINED_FRACTION:g}",
    "MATURITY_MIN_MISFIT_PCT": f"{100 * MATURITY_MIN_MISFIT_SHARE:g}",
    "MAX_GRAM_CONDITION": f"{MAX_GRAM_CONDITION:,.0f}".replace(",", " "),
    "MIN_COEF_SIGNIFICANCE": f"{MIN_COEF_SIGNIFICANCE:g}",
    "MIN_REGION_CHI2_RED": MIN_REGION_CHI2_RED,
    # How much better the best position trend must fit than the runner-up.
    "SEPARABILITY_MIN_SS_RATIO": f"{SEPARABILITY_MIN_SS_RATIO:g}",
    # The height in esds a residual peak needs to join Layer 0's unmatched
    # list.  It is a keyword default, not a module constant, so it is read
    # off the signature.
    "LAYER0_PEAK_SIGMA":
        f"{_inspect.signature(build_layer0).parameters['min_peak_sigma'].default:g}",
    # A phase under this many esds of scale is held for the stage (WP-1523).
    "PHASE_SUPPORT_SIGMA": f"{PHASE_SUPPORT_SIGMA:g}",
    "MIN_REGION_R2": MIN_REGION_R2,
    "NEAR_EDGE_EV": NEAR_EDGE_EV,
    # where Y³⁺'s ITC fit hands over to neutral Y (WP-1527).  The package
    # computes it from the two curves, so the chapter quotes it.
    "Y3_HANDOVER_STOL": f"{_itc_handover('Y3+'):.3f}",
    "NIGGLI_EPS_RELATIVE": NIGGLI_EPS_RELATIVE,
    "NODES_PER_FWHM": NODES_PER_FWHM,
    "CLOSING_NODES_PER_FWHM": CLOSING_NODES_PER_FWHM,
    "CLOSING_SKIP_EXTENT_FWHM_RATIO": CLOSING_SKIP_EXTENT_FWHM_RATIO,
    "CLOSING_WINDOW_TOL": CLOSING_WINDOW_TOL,
    "PAWLEY_OVERLAP_FWHM_FRAC": PAWLEY_OVERLAP_FWHM_FRAC,
    "SKIP_EXTENT_FWHM_RATIO": SKIP_EXTENT_FWHM_RATIO,
    "STRAIN_CAP_RANGE_FRACTION": STRAIN_CAP_RANGE_FRACTION,
    "STRAIN_FLAG_WIDTH": STRAIN_FLAG_WIDTH,
    "SIZE_CAP_RANGE_FRACTION": SIZE_CAP_RANGE_FRACTION,
    "SIZE_FLAG_SIZE_NM": SIZE_FLAG_SIZE_A / 10.0,
    "SUGGEST_MIN_GAIN": SUGGEST_MIN_GAIN,
    "SUPERCELL_CHANCE_ALPHA": SUPERCELL_CHANCE_ALPHA,
    "SYMMETRY_ANGLE_TOL_DEG": SYMMETRY_ANGLE_TOL_DEG,
    # a body atom's image this close (× the covalent-radius sum) to the body
    # refuses it, RIGID_BODY_IMAGE_OVERLAP (WP-1807)
    "RIGID_BODY_OVERLAP_FACTOR": RIGID_BODY_OVERLAP_FACTOR,
    "THRESHOLDS_VERSION": THRESHOLDS_VERSION,
    "VALIDITY_RADIUS_FWHM": VALIDITY_RADIUS_FWHM,
    "WINDOW_AREA_TOL": WINDOW_AREA_TOL,
}


# ----------------------------------------------------------------------
# The tutorial notebooks (WP-1916, WP-1986)
#
# The notebooks live in `examples/tutorials/`, beside the scripts they are
# built from, and Sphinx reads only its own source tree.  So the build copies
# them into the gitignored `start/tutorials/`.  The set is `build.py`'s own
# glob, so a new tutorial needs no edit here, and a copy whose source is gone
# is deleted.  The page-globbing tests read `*.md` only, so the copies do not
# make the suite depend on whether a build has run.
# ----------------------------------------------------------------------

#: Where the tutorial scripts and their committed notebooks live.
TUTORIALS_SRC = REPO_ROOT / "examples" / "tutorials"


def tutorial_notebooks() -> list[_Path]:
    """The committed notebook of each tutorial script, in `build.py`'s order."""
    spec = _importlib_util.spec_from_file_location("_tutorials_build", TUTORIALS_SRC / "build.py")
    build = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return [s.with_suffix(".ipynb") for s in build.sources(TUTORIALS_SRC)]


def copy_tutorials(destination: _Path) -> int:
    """Copy every committed notebook into `destination`, and return how many.

    The count is what a tree's index page quotes as `N_TUTORIALS`.
    """
    notebooks = tutorial_notebooks()
    missing = [nb.name for nb in notebooks if not nb.is_file()]
    if missing:
        raise RuntimeError(
            f"tutorial scripts with no committed notebook: {missing} -- run "
            "examples/tutorials/build.py")
    destination.mkdir(exist_ok=True)
    for stale in set(destination.glob("*.ipynb")) - {destination / nb.name for nb in notebooks}:
        stale.unlink()
    for nb in notebooks:
        # copy2 keeps the mtime, so Sphinx rereads a page only when its
        # notebook changed.
        _shutil.copy2(nb, destination / nb.name)
    return len(notebooks)


# ----------------------------------------------------------------------
# The `{source}` role (WP-1408)
#
# Every displayed equation in the Theory tab carries a *Source:* line naming the
# symbol its docstring was transcribed from.  The name resolving is the
# manual's oldest guard (WP-0604), and the role turns the same resolution into
# a link: `inspect` gives the file and the line, so a reader goes from the
# equation to the code that runs it in one click, and a renamed symbol breaks
# the **build** rather than leaving a dead link on the page.
#
# A release's manual links its tag, and `main`'s links `main` (WP-1979).
# The tag pins each line number to the tree the page was built from.  Until
# WP-1979 every build linked `main`, because `pyproject.version` was once the
# last shipped milestone whether or not it was tagged (on 2026-09-14 it read
# 1.4.0 while the tags stopped at v1.3.0).  The ref now follows the hosted
# version instead: only release.yml builds a release's manual, and only at a
# tag its own check has matched to `pyproject.version`.
# ----------------------------------------------------------------------

#: Which hosted manual this build is: ``dev`` for `main`, ``X.Y`` for a
#: release (`docs_versions.docs_version`).  Unset, it is ``dev``: every build but
#: release.yml's is `main`'s, even at the commit a release is cut from, whose
#: tag is pushed hours later.  release.yml sets it from the tag, and a value
#: that is not the installed release's refuses to build.
DOCS_VERSION = _os.environ.get("DOCS_VERSION", "dev")
if DOCS_VERSION not in ("dev", docs_version(__version__)):
    raise RuntimeError(f"DOCS_VERSION={DOCS_VERSION} names another release than "
                       f"the installed {__version__}")

#: What the `{source}` role and the Reference tab's file links point at.
SOURCE_REF = "main" if DOCS_VERSION == "dev" else f"v{__version__}"


def _assignment_line(path: _Path, name: str) -> int:
    """Where a module-level constant is bound.

    `inspect.getsourcelines` works on anything with code behind it and raises
    on a float, so a `*Source:*` line naming a threshold — and several do —
    needs the assignment found by reading.  Falling back to the top of the
    file would be worse than useless: it would look like a working link.
    """
    pattern = _re.compile(rf"^{_re.escape(name)}\s*[:=]")
    matches = [number
               for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
               if pattern.match(line)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        # Two column-0 bindings of one name: a real rebind, or a line inside a
        # module docstring that reads like one.  Guessing picks a link that
        # looks right and is not, so refuse and name the lines.
        raise LookupError(f"{name}: {len(matches)} module-level bindings in "
                          f"{path.name}, lines {matches}")
    raise LookupError(f"{name}: no module-level assignment in {path.name}")


def _resolve_source(dotted: str) -> tuple[str, int]:
    """(path relative to the repository root, 1-based line) for a dotted name."""
    parts = dotted.split(".")
    for split in range(len(parts), 0, -1):
        try:
            module = _importlib.import_module(".".join(parts[:split]))
        except ImportError:
            continue
        break
    else:
        raise LookupError(f"{dotted}: no importable module prefix")

    obj = module
    for attr in parts[split:]:
        if not hasattr(obj, attr):
            raise LookupError(f"{dotted}: {obj!r} has no attribute {attr!r}")
        obj = getattr(obj, attr)

    # The file has to be the one the *line* was read out of.  `getsourcelines`
    # reports where the object was **defined**, which for a re-exported name
    # (`schemas.history` re-exports `StageSpec`, and the package does that on
    # purpose) is not the module the dotted name went through — taking the path
    # from the module and the line from the object then links a real file at a
    # line belonging to another one, and every guard here still passes because
    # the name imports.  A constant has no code behind it, so it falls back to
    # the module's own file, which is where `_assignment_line` reads.
    try:
        line = _inspect.getsourcelines(obj)[1] or 1
        path = _Path(_inspect.getsourcefile(obj) or _inspect.getsourcefile(module)).resolve()
    except (TypeError, OSError):
        path = _Path(_inspect.getsourcefile(module)).resolve()
        line = _assignment_line(path, parts[-1]) if parts[split:] else 1
    try:
        return path.relative_to(REPO_ROOT).as_posix(), line
    except ValueError:
        # The imported package is not this checkout's — a non-editable install,
        # or a venv belonging to another worktree.  Say so: `relative_to`'s own
        # message reaches the reader as an unexplained `-W` build failure.
        raise LookupError(
            f"{dotted}: resolved to {path}, which is outside {REPO_ROOT} — "
            "build the manual against an editable install of this checkout"
        ) from None


def source_role(name, rawtext, text, lineno, inliner, options=None, content=None):
    dotted = text.strip().strip("`")
    try:
        path, line = _resolve_source(dotted)
    except Exception as exc:                      # noqa: BLE001 — reported, not raised
        message = inliner.reporter.error(f"{{source}}: {exc}", line=lineno)
        return [inliner.problematic(rawtext, rawtext, message)], [message]
    url = f"{REPO_URL}/blob/{SOURCE_REF}/{path}#L{line}"
    link = _nodes.reference("", "", _nodes.literal(text=dotted), refuri=url,
                            classes=["source-link"])
    return [_nodes.emphasis(text="Source: "), link], []
