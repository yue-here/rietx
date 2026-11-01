"""Regenerate the GUI pages' committed screenshots (WP-1017).

    .venv/bin/python -m pip install playwright     # once, see below
    .venv/bin/python docs/docs/make_screenshots.py

The pages are `start/gui-quickstart.md`, `reference/gui-guide.md` and
`reference/gui-power.md`, moved here from the old tree by WP-1986.

`docs/docs/make_figures.py`'s rule, one medium over: the screenshots are **committed**,
not built, so the sphinx build stays offline and dependency-free, and this
script is the one authority for how each was taken.  The cost is that a
screenshot can go stale when a control moves, so `SHOTS` below is the
*declared* set and `tests/test_gui_manual.py` fails on a chapter referencing a
picture this script does not produce — which is what makes a moved control a
stale picture the build can name rather than one a reader finds.

**playwright is deliberately not a dependency.**  It is not in `[dev]`, this
script is the only thing that wants it, and a docs build never runs it.  The
chromium it drives is whatever `PLAYWRIGHT_CHROMIUM` names, defaulting to the
newest build in playwright's own cache: on a machine that has run a browser
pass before, the binaries are already there, and a revision mismatch with the
installed `playwright` package is not a reason to download a second copy
(`gui/CLAUDE.md`, "Driving a real browser").

**Every shot is of a real project**, never a mock.  The server is the real one,
booted in-process on a thread the way `tests/test_gui_server.py` boots it, and
it starts with **no project** — so the empty state is photographed as a first
run of the app actually finds it, and the project is then opened through the
same route the example row calls.  A fitted shot runs the plan first, so the
curves in the picture are curves the package produced.

Each shot is written twice, `-light` and `-dark`, and the pages select
between them with the `only-light` / `only-dark` classes the theme reads
(pydata-sphinx-theme), exactly as the manual's figures do.  A single white-ground screenshot on a dark page is what
that avoids.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SHOTS_DIR = Path(__file__).resolve().parent / "screenshots"
sys.path.insert(0, str(REPO_ROOT))

#: The example every shot is taken of.  `fap` rather than `nac`: a lab pattern
#: with seven atomic sites is the one a reader is likelier to have an analogue
#: of, and its 2.5 MB neighbour makes every boot slower for no difference in
#: any picture here.
EXAMPLE = "fap"

#: Where the window is measured.  Wide enough that the panel column is at a
#: comfortable width rather than its floor — the model form stacks below
#: 1256 px (WP-1216) and the history compare row side-scrolls below about a
#: 400 px sidebar (WP-1217), so a narrower shot would document the reflow
#: rather than the panel.
VIEWPORT = {"width": 1440, "height": 900}

THEMES = ("light", "dark")


@dataclass(frozen=True)
class Shot:
    """One picture, and how it is taken.

    `selector` is the element photographed — a panel rather than the whole
    window wherever the panel is the subject, because a full-window shot of a
    360 px column is mostly pattern.  `tab` is the tab *label* to open first
    (the strip's own word, `gui/src/lib/tabs.ts`), and `fitted` says the plan
    must have been run before the shot is taken.
    """

    name: str
    caption: str
    selector: str
    tab: str | None = None
    #: Which state of the session this shot is of.  **One field rather than a
    #: flag each**: the session passes through these in order and a shot
    #: belongs to exactly one of them, which three independent booleans could
    #: not say — the first version of this had `first-run` matching both the
    #: empty pass and the opened one, and it was photographed twice, the first
    #: time showing the wrong screen entirely.
    #:
    #: ``empty``  — no project open.
    #: ``opened`` — the project open, nothing run, the checklist still up.
    #: ``fitted`` — the plan has run and the curves are on the plot.
    #: ``forked`` — a second lineage exists; the curves are gone with the
    #:              checkout that made it, so these come last.
    when: str = "fitted"


#: The session states, in the order the driver walks them.  A `when` outside
#: this set would silently take no picture at all, which is how the bug above
#: hid: the file was written by the *other* pass that matched it.
PHASES = ("empty", "opened", "fitted", "forked")


#: The declared set.  A page may reference `../screenshots/<name>-light.png`
#: and `-dark.png` for any name here and no other; `tests/test_gui_manual.py`
#: holds the two together.
SHOTS: tuple[Shot, ...] = (
    Shot(
        "empty-state",
        "The screen with no project open: the shipped examples, the way out "
        "to a filesystem browser, and the four-step wizard under them.",
        selector=".side",
        when="empty",
    ),
    Shot(
        "first-run",
        "The checklist a project shows on its first open: four derived steps, "
        "above the tab strip and dismissible rather than modal.",
        selector=".side",
        when="opened",
    ),
    Shot(
        "first-fit",
        "The whole window after one run: the header carrying Rwp, the pattern "
        "on the left, the panel column on the right.",
        selector="body",
    ),
    Shot(
        "plot-readout",
        "The pattern with its readout strip, the drawing knobs and the "
        "protocol strip below it.",
        selector=".plotcol",
    ),
    Shot(
        "parameters",
        "The parameter table: the filter box that is the selection, and the "
        "marks on rows nothing can free.",
        selector=".side",
        tab="Parameters",
    ),
    Shot(
        "plan-ladder",
        "The plan as a ladder — per stage, what it frees and what stays held.",
        selector=".side",
        tab="Plan",
    ),
    Shot(
        "report",
        "The fit report: the headline, the worst regions, and the suggested "
        "actions.",
        selector=".side",
        tab="Report",
    ),
    Shot(
        "history-graph",
        "The history after a second strategy was tried from an earlier node: "
        "two lanes, and the compare table for two selected nodes under them.",
        selector=".side",
        tab="History",
        when="forked",
    ),
    Shot(
        "text-document",
        "The project as an `.rxt` document, where `@` frees a parameter.",
        selector=".side",
        tab="Text",
    ),
)


def chromium_path() -> str:
    """The cached chromium to drive, or "" to let playwright choose.

    A revision mismatch between the installed package and the cached browser is
    the normal state of a machine that has run a browser pass before, and
    downloading a second copy to fix it is 150 MB for no difference in any
    picture.
    """
    override = os.environ.get("PLAYWRIGHT_CHROMIUM")
    if override:
        return override
    cache = Path.home() / "Library/Caches/ms-playwright"
    if not cache.exists():
        cache = Path.home() / ".cache/ms-playwright"

    def revision(build: Path) -> int:
        # The suffix is a build *number*, so it is sorted as one: lexically,
        # `chromium-989` sorts above `chromium-1148` and "newest" would have
        # meant "oldest" on any cache that has crossed four digits.
        tail = build.name.rpartition("-")[2]
        return int(tail) if tail.isdigit() else -1

    for build in sorted(cache.glob("chromium-*"), key=revision, reverse=True):
        for candidate in (
            build / "chrome-mac-arm64/Google Chrome for Testing.app/Contents"
            "/MacOS/Google Chrome for Testing",
            build / "chrome-linux/chrome",
        ):
            if candidate.exists():
                return str(candidate)
    return ""


def _serve(state_dir: Path):
    """The real server, no project open, on an ephemeral port."""
    from rietx.gui import GuiSession, build_server

    session = GuiSession(state_dir=state_dir)
    httpd = build_server(session, port=0)
    threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
    ).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def _set_theme(page, theme: str) -> None:
    """Press the header's explicit light or dark button.

    Explicit rather than the context's `color_scheme` alone: the app resolves a
    three-way choice and stamps `data-theme` on the root, and "follow the
    system" is a third state — a shot taken under it would be documenting the
    default rather than the theme.
    """
    page.click(f'.theme button[aria-label="{theme}"]')
    page.wait_for_function(
        f'() => document.documentElement.dataset.theme === "{theme}"', timeout=10_000
    )
    page.wait_for_timeout(400)


def _run_once(page) -> None:
    """Run the plan and wait for the run state to come back to idle."""
    page.get_by_role("button", name="Run", exact=True).click()
    pill = 'header .pill[data-state="idle"]'
    page.wait_for_selector('header .pill[data-state="running"]', timeout=30_000)
    page.wait_for_selector(pill, timeout=600_000)
    # the curves arrive on the run's own reload, one fetch after the pill
    page.wait_for_timeout(2_500)


#: The node the second strategy is tried from.  Mid-plan on purpose: forking
#: at the tip draws a fork nobody would make, and forking at the root redraws
#: the whole plan in the second lane.
FORK_FROM = "n0003"


def _fork(page, url: str) -> None:
    """Try a second strategy from an earlier node, so the graph has two lanes.

    This is the workflow the History section teaches, so the picture of it
    should be one — a linear chain photographed as a "lane graph" would be
    documenting the one case where lanes do not show.  A checkout is what makes
    the fork: running the plan from a node that already has a child gives the
    second child a lane of its own.
    """
    page.request.post(f"{url}api/history/checkout", data={"node_id": FORK_FROM})
    page.reload()
    page.wait_for_selector(".tab", timeout=60_000)
    page.wait_for_timeout(1_200)
    _run_once(page)


def _compare_two(page) -> None:
    """Select a node and compare another against it, so the table is populated.

    Empty, the panel says `select · ⇄ compare` and shows nothing, which is the
    resting state rather than what the section is about.
    """
    page.click(f'.node:has(.id:text-is("{FORK_FROM}")) button.pick')
    page.wait_for_timeout(400)
    last = page.locator(".node").last
    last.locator("button.ghost").click()
    page.wait_for_timeout(1_200)


def _shrink(path: Path) -> tuple[int, int]:
    """Quantise the shot to a 256-colour palette, in place.

    These are committed files, and a screenshot of a user interface is flat
    colour and antialiased text — which is exactly what a palette encodes well.
    Measured over this set: 5.2 MB of truecolour becomes about 2.3 MB with no
    difference visible at reading size, against 1.3 MB for the whole of Part
    1's plotted figures. Dithering is off because it defeats PNG's row filters
    and adds noise to flat panels.
    """
    from PIL import Image

    before = path.stat().st_size
    # The source handle is closed before the same path is written back: PIL
    # opens lazily, and rewriting a file it still holds open is a failure on
    # Windows and a leaked descriptor everywhere else.
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    image.quantize(
        colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    ).save(path, optimize=True)
    return before, path.stat().st_size


def _shoot(page, shot: Shot, theme: str) -> None:
    if shot.tab:
        page.click(f'.tab:text-is("{shot.tab}")')
        page.wait_for_timeout(900)
    page.wait_for_timeout(500)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out = SHOTS_DIR / f"{shot.name}-{theme}.png"
    page.locator(shot.selector).first.screenshot(path=str(out))
    before, after = _shrink(out)
    print(f"  {out.name}  {before // 1024} → {after // 1024} kB")


def main() -> int:
    from playwright.sync_api import sync_playwright

    work = Path(tempfile.mkdtemp(prefix="rietx-shots-"))
    httpd = None
    try:
        httpd, url = _serve(work / "state")
        executable = chromium_path()
        print(f"serving at {url}")
        print(f"chromium: {executable or 'playwright default'}")

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=executable or None)
            for theme in THEMES:
                context = browser.new_context(
                    viewport=VIEWPORT, device_scale_factor=2, color_scheme=theme
                )
                page = context.new_page()

                # The empty state, before any project is opened into this
                # session: its subject is the *absence* of a project, so it
                # cannot be taken after the others.
                page.goto(url)
                page.wait_for_selector(".side", timeout=60_000)
                page.wait_for_timeout(1_200)
                _set_theme(page, theme)
                for shot in SHOTS:
                    if shot.when == "empty":
                        _shoot(page, shot, theme)

                # Then open the example the way its own row does, and run.
                page.request.post(f"{url}api/examples/open", data={"name": EXAMPLE})
                # The light pass dismissed the checklist and that persisted, so
                # the dark pass would photograph a screen with no strip on it.
                # `null` drops a `ui` key (WP-1044's grammar), which is the one
                # way back to "never dismissed".
                page.request.post(f"{url}api/project", data={"ui": {"first_run": None}})
                page.goto(url)
                page.wait_for_selector(".tab", timeout=60_000)
                page.wait_for_timeout(1_200)
                _set_theme(page, theme)

                # Before the run, and before the checklist is dismissed: this
                # is the one screen that strip is on.
                for shot in SHOTS:
                    if shot.when == "opened":
                        _shoot(page, shot, theme)

                # Dismissed for every shot after this one — it is a first-run
                # aid, and leaving it up would put it in eight pictures of
                # panels it is not about.
                page.click('.checklist button:text-is("Dismiss")')
                page.wait_for_timeout(600)

                _run_once(page)
                for shot in SHOTS:
                    if shot.when == "fitted":
                        _shoot(page, shot, theme)

                # The curves die with the checkout, so every shot that shows
                # them is already taken by here.
                _fork(page, url)
                for shot in SHOTS:
                    if shot.when != "forked":
                        continue
                    # The tab has to be open before the compare row can be
                    # clicked, so it is opened here as well as in `_shoot` —
                    # guarded, because a forked shot declaring no tab would
                    # otherwise click `text-is("None")` and wait out the
                    # timeout.
                    if shot.tab:
                        page.click(f'.tab:text-is("{shot.tab}")')
                        page.wait_for_timeout(900)
                    _compare_two(page)
                    _shoot(page, shot, theme)

                context.close()
            browser.close()
    finally:
        # In the `finally` beside the temp tree: a shot that raises used to
        # leave the serving thread up, so the script kept the port and the
        # example project it had opened until the process was killed.
        if httpd is not None:
            httpd.shutdown()
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
