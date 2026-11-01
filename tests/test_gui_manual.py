"""The GUI chapters' anti-divergence guards (WP-1017).

The chapters are `start/gui-quickstart.md`, `reference/gui-guide.md` and
`reference/gui-power.md`, under `docs/docs/` since WP-1986, with their
screenshots and the script that takes them beside the tree's pages.

The Theory tab is guarded by injected constants, every page by name resolution
(`test_manual.py`, `test_manual_api.py`).  A GUI chapter is guarded by neither,
because its subject is routes and panels rather than importable names — and the
prose-drift problem is worse here than anywhere else in the manual: this WP's
own mailbox recorded "three sentences in this chapter are now wrong" eight
times over eight sessions, each time because a control moved.

So the two vocabularies a GUI chapter is *about* are partitioned the way
`tests/api_surface.py` partitions the call surface:

* every route in the server's table is named in a GUI chapter or excluded with
  a written reason — a new route fails this until one or the other is true;
* every tab in the live tab strip is named in a GUI chapter, the strip arriving
  as a committed corpus that vitest writes from the app's own `TABS`
  (`tests/data/gui/panels.json`, the `test_gui_fnmatch.py` mechanism with the
  authorities swapped: TypeScript owns the strip, python proves the manual
  states it).

What this does not measure is whether the sentence about a route is *true*.
The bar for that is review and the screenshots; this stops a route or a panel
from being silently forgotten.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

from rietx.gui.server import ROUTES, UPLOAD_ROUTES
from rietx.gui.session import RESERVED_ROUTES

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_TREE = REPO_ROOT / "docs" / "docs"
#: Globbed rather than listed, so a fourth GUI page fails the name check below
#: instead of sitting outside the partition.  `_build/` is sphinx output.
GUI_PAGES = sorted(p for p in DOCS_TREE.rglob("gui-*.md")
                   if not {"_build", "_generated"} & set(p.relative_to(DOCS_TREE).parts))
#: Where a new route is documented, named in the failure that asks for it.
ROUTES_PAGE = DOCS_TREE / "reference" / "gui-power.md"
PANELS_CORPUS = REPO_ROOT / "tests" / "data" / "gui" / "panels.json"
SHOTS_DIR = DOCS_TREE / "screenshots"
MAKE_SHOTS = DOCS_TREE / "make_screenshots.py"

IMAGE_REF = re.compile(r"^```\{image\}\s+(\S+)\s*$", re.M)


def _rel(path: Path) -> str:
    """A path as a failure message names it: from the repo root where it can be."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _screenshot_refs() -> list[tuple[Path, str, Path]]:
    """(page, target as written, the file it resolves to) per screenshot shown.

    A screenshot is an image whose directory is named `screenshots`, however
    the page reaches it: the pages sit in two tabs, so the relative path
    differs by page, and a prefix match on the target would miss one.
    """
    refs = []
    for page in GUI_PAGES:
        for target in IMAGE_REF.findall(page.read_text(encoding="utf-8")):
            if Path(target).parent.name == "screenshots":
                refs.append((page, target, (page.parent / target).resolve()))
    return refs


def _declared_shots():
    """`SHOTS` out of `make_screenshots.py`, without importing playwright.

    Loaded by path rather than imported as a module: `docs/` is not a package,
    and the script's own imports of playwright are inside its functions for
    exactly this reason — the declaration has to be readable by a suite that
    will never drive a browser.
    """
    name = "_make_screenshots"
    spec = importlib.util.spec_from_file_location(name, MAKE_SHOTS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Registered before it is executed: `Shot` is a dataclass, and resolving a
    # field's annotation reads `sys.modules[cls.__module__]`, which is None for
    # a module loaded by path alone.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.SHOTS, module.THEMES

CODE_SPAN = re.compile(r"`([^`\n]+)`")
#: `GET /api/params` inside a code span.  The method is part of the name on
#: purpose: a GET and a PATCH on one path are two capabilities, and a chapter
#: that describes reading a thing has not thereby described writing it.
ROUTE_SPAN = re.compile(r"^(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)$")

# A route a GUI chapter deliberately does not name, and why.  Same bar as
# `api_surface.EXCLUSIONS`: an empty reason is a shrug, and an entry that has
# stopped matching a live route has to fail rather than sit here.
ROUTE_EXCLUSIONS: dict[tuple[str, str], str] = {}


def _documented_routes() -> set[tuple[str, str]]:
    """Every `METHOD /path` a GUI chapter spells in a code span."""
    found: set[tuple[str, str]] = set()
    for page in GUI_PAGES:
        for span in CODE_SPAN.findall(page.read_text(encoding="utf-8")):
            match = ROUTE_SPAN.match(span.strip())
            if match:
                found.add((match.group(1), match.group(2)))
    return found


def _live_routes() -> set[tuple[str, str]]:
    return set(ROUTES) | set(UPLOAD_ROUTES) | set(RESERVED_ROUTES)


def test_the_gui_chapters_exist():
    """The partition below is vacuous if the pages moved or were renamed."""
    names = {page.relative_to(DOCS_TREE).as_posix() for page in GUI_PAGES}
    assert names == {"start/gui-quickstart.md", "reference/gui-guide.md",
                     "reference/gui-power.md"}, (
        f"GUI chapters are not the three this suite guards: {sorted(names)}"
    )


def test_every_route_is_documented_or_excluded():
    """The wire surface is partitioned: named in a chapter, or excluded here.

    This is the guard the WP was written for.  A route is the one part of the
    GUI a reader cannot discover by looking at the app, so a new one that
    nobody documented is invisible until somebody needs it.
    """
    live = _live_routes()
    documented = _documented_routes() & live
    excluded = set(ROUTE_EXCLUSIONS)
    missing = sorted(live - documented - excluded)
    assert not missing, (
        f"{len(missing)} route(s) no GUI chapter names and no exclusion covers:\n"
        + "\n".join(f"  {m} {p}" for m, p in missing)
        + f"\n\nDocument them in {_rel(ROUTES_PAGE)}, or add an entry "
        "to ROUTE_EXCLUSIONS with a written reason."
    )
    both = sorted(documented & excluded)
    assert not both, f"route(s) both documented and excluded: {both}"


def test_route_exclusions_are_live_and_reasoned():
    """An exclusion for a route that no longer exists is a dead promise, and an
    empty reason is a shrug (`api_surface`'s rule, one vocabulary over)."""
    live = _live_routes()
    for route, reason in ROUTE_EXCLUSIONS.items():
        assert route in live, f"{route}: excluded but not a live route"
        assert len(reason.split()) >= 5, f"{route}: exclusion carries no real reason"


def test_no_chapter_names_a_route_that_does_not_exist():
    """The partition tightens from both sides.  A chapter naming a route the
    server does not serve is the WP-1037 bug in the other direction: the page
    is green, the reader gets a 404."""
    live = _live_routes()
    invented = sorted(_documented_routes() - live)
    assert not invented, (
        "GUI chapter names route(s) the server does not serve: "
        + ", ".join(f"{m} {p}" for m, p in invented)
    )


def test_every_screenshot_a_chapter_shows_is_one_the_script_takes():
    """A referenced screenshot is declared in `make_screenshots.py`.

    `test_manual_api.test_every_figure_reference_exists` already catches a
    reference to a file that is not there.  This catches the other half, which
    is the one that matters for a picture of a moving user interface: a file
    that *is* there, was taken by hand or by an older version of the script,
    and no longer has anything regenerating it.  A control then moves, the
    build stays green, and the reader is looking at last month's app.
    """
    shots, themes = _declared_shots()
    declared = {f"{shot.name}-{theme}.png" for shot in shots for theme in themes}
    refs = _screenshot_refs()
    assert refs, "no GUI chapter shows a screenshot — has the image syntax moved?"
    for page, target, resolved in refs:
        assert resolved.parent == SHOTS_DIR.resolve(), (
            f"{_rel(page)}: `{target}` resolves to {resolved}, outside "
            f"{_rel(SHOTS_DIR)} where make_screenshots.py writes"
        )
        assert resolved.name in declared, (
            f"{_rel(page)}: `{target}` is not a shot make_screenshots.py "
            f"produces — add it to SHOTS, or reference a declared one"
        )
        assert resolved.exists(), (
            f"{_rel(page)}: `{target}` is declared but not committed — run "
            f"{_rel(MAKE_SHOTS)}"
        )


def test_no_committed_screenshot_is_undeclared():
    """The other direction: a committed picture nothing regenerates.

    It would sit in the tree looking current for as long as nobody opened it,
    which is what `make_figures.py`'s one-authority rule exists to prevent.
    """
    if not SHOTS_DIR.exists():
        return
    shots, themes = _declared_shots()
    declared = {f"{shot.name}-{theme}.png" for shot in shots for theme in themes}
    orphans = sorted(p.name for p in SHOTS_DIR.glob("*.png") if p.name not in declared)
    assert not orphans, (
        f"committed screenshot(s) make_screenshots.py does not produce: {orphans}"
    )


def test_every_shot_names_a_session_state_the_driver_walks():
    """A `when` outside `PHASES` takes no picture and says nothing.

    Measured while writing it: `first-run` was declared with two independent
    booleans, matched the empty-state pass as well as its own, and was written
    twice — the committed file being the *first* of the two, showing a screen
    with no project open. The loop is a filter, so a name it never matches is
    silent, and a name it matches twice is silent too.
    """
    shots, _ = _declared_shots()
    module = sys.modules["_make_screenshots"]
    bad = sorted({shot.name: shot.when for shot in shots
                  if shot.when not in module.PHASES}.items())
    assert not bad, f"shot(s) declaring a session state the driver never walks: {bad}"
    for phase in module.PHASES:
        assert any(shot.when == phase for shot in shots), (
            f"no shot is taken in the {phase!r} state — the driver walks it for nothing"
        )


def test_every_declared_shot_is_committed_and_used():
    """A declared shot that nothing shows is dead weight in a slow script, and
    one that is declared but missing from the tree is a broken image waiting
    for the next build."""
    shots, themes = _declared_shots()
    shown = {resolved.name for _, _, resolved in _screenshot_refs()
             if resolved.parent == SHOTS_DIR.resolve()}
    for shot in shots:
        for theme in themes:
            name = f"{shot.name}-{theme}.png"
            assert (SHOTS_DIR / name).exists(), (
                f"{name} is declared but not committed — run {_rel(MAKE_SHOTS)}"
            )
        # The whole filename, not the `<name>-` prefix: `first` would have been
        # covered by a chapter showing `first-fit`, so a shot whose name is
        # another's prefix could go unshown and still pass.
        assert any(f"{shot.name}-{theme}.png" in shown for theme in themes), (
            f"{shot.name} is taken by make_screenshots.py but no chapter shows it"
        )
        assert len(shot.caption.split()) >= 5, f"{shot.name}: caption says nothing"


def test_nothing_gitignores_the_screenshots():
    """The repo-wide `*.png` rule matched them, which is the third committed
    image directory it has swallowed (`test_gui_dist`'s `*.html` twin, and
    Part 1's figures before that).

    It fails in the worst way: the build is green on the machine that took the
    pictures, and a fresh clone has a manual whose images are all broken. The
    filter is on the *shape* of the matching rule rather than its text — a
    rule beginning `!` is a negation — because spelling the un-ignore path
    here would be a second copy of a .gitignore line, which is how a guard of
    this shape goes quiet (`tests/CLAUDE.md`).
    """
    import subprocess

    files = sorted(SHOTS_DIR.glob("*.png"))
    assert files, f"no screenshots committed — run {_rel(MAKE_SHOTS)}"
    result = subprocess.run(
        # --no-index: check-ignore answers for a *tracked* file from the index
        # without reading the rules at all, and every file here is committed.
        ["git", "check-ignore", "-v", "--no-index", *[str(f) for f in files]],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    ignored = [
        line for line in result.stdout.splitlines()
        if line and not line.split("\t")[0].rpartition(":")[2].startswith("!")
    ]
    assert not ignored, f"committed screenshots are gitignored: {ignored}"


def test_every_panel_is_named_in_a_chapter():
    """Every tab in the live strip is named in a GUI chapter.

    The corpus is written by `gui/src/lib/tabs.test.ts` from the same `TABS`
    the app renders, so this cannot be satisfied by a stale list: a renamed tab
    rewrites the corpus, and the chapter that still uses the old word fails
    here.
    """
    assert PANELS_CORPUS.exists(), (
        f"{PANELS_CORPUS} missing — run `npm --prefix gui test` to write it"
    )
    panels = json.loads(PANELS_CORPUS.read_text(encoding="utf-8"))
    labels = [entry["label"] for entry in panels["tabs"]]
    assert labels, "the panel corpus carries no tabs"
    prose = "\n".join(page.read_text(encoding="utf-8") for page in GUI_PAGES)
    missing = [label for label in labels if not re.search(rf"\b{re.escape(label)}\b", prose)]
    assert not missing, (
        f"tab(s) the GUI chapters never name: {missing} — the strip is "
        f"{labels}"
    )
