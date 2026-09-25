"""WP-1423 — what holds still on the ``rietx watch`` page, measured in a browser.

A python test cannot see layout (WP-1402 and WP-1405 each found a page defect
no substring assertion could have), and ``node --check`` sees only syntax.
This file drives the page in chromium through playwright, which is not a
dependency (``docs/manual/make_screenshots.py`` says why), so every test here
skips where the package or a cached chromium is missing. That includes CI:
the guard is this machine's, and the handover names the skip.

What it pins is the WP's two rules. Nothing on the page is rebuilt on a poll,
and no dimension follows the stage being drawn: over two polls that rewrite
the snapshot and the status, the columns, the bar, the strip's slots, the
plot's inner size and its data-derived ranges are unchanged while the text in
the slots is not.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
import time
from pathlib import Path

import pytest

from rietx import runs
from rietx._about import STATE_DIR_ENV
from rietx.viz.theme import PHASE_TOKENS, TOKENS
from tests.test_watch_app import _served

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKE_SHOTS = REPO_ROOT / "docs" / "manual" / "make_screenshots.py"

#: One poll of the page, in seconds (``schedule`` in
#: ``watch/static/watch.mjs``); a wait of two of them is what "the page has
#: seen the write" means here.
POLL = 1.2


def _chromium() -> str:
    """The cached chromium ``make_screenshots.py`` drives, loaded by path.

    The script's playwright imports are inside its functions, so loading it
    costs nothing a suite without a browser would notice.
    """
    spec = importlib.util.spec_from_file_location("_make_screenshots", MAKE_SHOTS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["_make_screenshots"] = module
    spec.loader.exec_module(module)
    return module.chromium_path()


@pytest.fixture(scope="module")
def browser():
    executable = _chromium()
    with sync_playwright() as p:
        try:
            handle = p.chromium.launch(executable_path=executable or None)
        except Exception as exc:  # no browser on this machine: not a failure
            pytest.skip(f"no chromium to drive: {exc}")
        try:
            yield handle
        finally:
            handle.close()


# ----------------------------------------------------------------------
# a run whose stages differ in everything but the data
# ----------------------------------------------------------------------
N = 600


def _snapshot(stage: str, *, scale: float, noise: float, bkg: bool = True) -> dict:
    """A pattern with three peaks, and a fit at ``scale`` of it.

    Observed is the same in every stage; calculated and Δ/σ are not. That is
    the contract the page's ranges rest on: two of three are the data's.

    ``bkg=False`` writes an all-zero background, which the page reads as no
    background to draw. It is one trace and one legend entry fewer, and so the
    way to write the stage that *frees* the background: the entry arrives, the
    legend gains a row, and before WP-1426 the whole picture moved down.
    """
    tt = [10.0 + 70.0 * i / (N - 1) for i in range(N)]
    obs = [50.0 + 3000.0 * math.exp(-((t - 25) ** 2) / 0.05)
           + 1200.0 * math.exp(-((t - 44) ** 2) / 0.08)
           + 600.0 * math.exp(-((t - 63) ** 2) / 0.1) for t in tt]
    calc = [scale * v for v in obs]
    delta = [(o - c) / math.sqrt(max(o, 1.0)) for o, c in zip(obs, calc)]
    # a wide residual reads as a wide stage, so the ladder can be seen moving
    delta = [d + noise * math.sin(i) for i, d in enumerate(delta)]
    return {"schema": 1, "stage": stage, "weighted": False, "n_points": N,
            "n_drawn": N, "two_theta": tt, "y_obs": obs, "y_calc": calc,
            "y_bkg": [50.0 if bkg else 0.0] * N, "delta": delta,
            # `hkl` rides beside `two_theta`, index for index (WP-1438);
            # `-1` because a negative index is how the label is told apart
            # from a run of digits, and this fixture is where that is drawn
            "ticks": {"phase 0": {"two_theta": [25.0, 44.0],
                                  "hkl": [[1, 1, 0], [2, 0, -1]],
                                  "n_total": 2},
                      "phase 1": {"two_theta": [63.0],
                                  "hkl": [[0, 0, 2]], "n_total": 1}},
            "statistics": {"rwp": 0.3 if scale < 1 else 0.05, "gof": 2.0,
                           "chi2": 4.0, "rp": 0.2, "n_free": 5}}


def _write_stage(run_dir: Path, stage: str, *, scale: float, noise: float,
                 rwp: float, bkg: bool = True) -> None:
    (run_dir / runs.SNAPSHOT_FILE).write_text(
        json.dumps(_snapshot(stage, scale=scale, noise=noise, bkg=bkg)),
        encoding="utf-8")
    (run_dir / runs.STATUS_FILE).write_text(
        json.dumps({"state": "done", "stage": stage, "rwp": rwp, "gof": 2.0,
                    "n_free": 5, "index": 2 if stage == "cell" else 3,
                    "n_stages": 3, "series_index": 4, "series_n": 8,
                    "series_label": "cpd-1e", "series_pass": "backward"}),
        encoding="utf-8")


def _make_tree(root: Path, *, n_done: int = 40) -> Path:
    """``n_done`` finished runs so the list scrolls, plus the one watched."""
    for i in range(n_done):
        d = root / f"old-{i:02d}"
        d.mkdir()
        (d / runs.EVENTS_FILE).write_text(
            json.dumps({"record": "event", "v": "2", "t": 1.0 + i,
                        "kind": "fit_start", "data": {}}) + "\n",
            encoding="utf-8")
        (d / runs.STATUS_FILE).write_text(
            json.dumps({"state": "done", "stage": "biso", "rwp": 0.1 + i / 1000,
                        "gof": 1.4}), encoding="utf-8")
    watched = root / "watched"
    watched.mkdir()
    (watched / runs.EVENTS_FILE).write_text(
        json.dumps({"record": "event", "v": "2", "t": 1e9, "kind": "fit_start",
                    "data": {"series_index": 4}}) + "\n", encoding="utf-8")
    _write_stage(watched, "cell", scale=0.7, noise=30.0, rwp=0.3)
    return watched


#: The picture has been drawn: the page hangs the chart module's figure on
#: ``#plot`` once it is up (``watch.mjs``, ``makeChart``). Its panes are uPlot
#: instances, whose scales are the ranges the axes were painted with.
DRAWN = ("() => document.getElementById('plot') && "
         "document.getElementById('plot').__rx")

#: Every stroke and fill on every canvas, with the style it was made in, from
#: before the page's own scripts run. What a curve was *painted* in, where a
#: series' own colour is only what it was handed: under plotly a tick row
#: declared one colour and painted another (WP-1438). ``test_gui_browser.py``
#: reads the GUI's panel through the same script.
RECORD = """
window.__ink = [];
const ids = new WeakMap();
let next = 0;
const id = (c) => { if (!ids.has(c)) ids.set(c, next++); return ids.get(c); };
window.__canvasId = id;
for (const op of ["stroke", "fill", "fillRect"]) {
  const original = CanvasRenderingContext2D.prototype[op];
  CanvasRenderingContext2D.prototype[op] = function (...args) {
    window.__ink.push({ canvas: id(this.canvas), op,
                        style: String(op === "stroke" ? this.strokeStyle : this.fillStyle),
                        dash: this.getLineDash().length > 0, alpha: this.globalAlpha });
    return original.apply(this, args);
  };
}
"""

#: The styles each of the picture's three panes (main, ticks, residual)
#: painted since the record was last cleared, by operation.
INKS = """() => [...document.querySelectorAll('#plot canvas')].map(c => {
  const id = window.__canvasId(c), mine = window.__ink.filter(m => m.canvas === id);
  const of = op => [...new Set(mine.filter(m => m.op === op).map(m => m.style))];
  return {stroke: of('stroke'), fill: of('fill').concat(of('fillRect'))};
})"""

CLEAR_INK = "() => { window.__ink = []; }"

GEOMETRY = """() => {
  const r = el => { const b = el.getBoundingClientRect();
                    return [b.x, b.y, b.width, b.height].map(Math.round); };
  const plot = document.getElementById('plot');
  const P = plot && plot.__rx && plot.__rx.panes;
  const at = (u, d) => [u.scales.y.min, u.scales.y.max].map(v => +v.toFixed(d));
  const area = u => { const b = u.over.getBoundingClientRect(),
                            p = plot.getBoundingClientRect();
                      return [b.x - p.x, b.y - p.y, b.width, b.height].map(Math.round); };
  return {
    bar: r(document.getElementById('bar')),
    strip: r(document.getElementById('strip')),
    slots: [...document.querySelectorAll('#strip > *')].map(r),
    cols: [...document.querySelectorAll('th')].map(th =>
      Math.round(th.getBoundingClientRect().width)),
    plot: plot ? r(plot) : null,
    size: P ? area(P.main) : null,
    x: P ? [P.main.scales.x.min, P.main.scales.x.max].map(v => +v.toFixed(3)) : null,
    y: P ? at(P.main, 1) : null,
    y2: P ? at(P.resid, 2) : null,
    y3: P ? {range: at(P.ticks, 2), height: P.ticks.height} : null,
    listScroll: document.getElementById('runs').scrollTop,
    stripText: document.getElementById('strip').textContent.replace(/\\s+/g, ' ').trim(),
    stage: document.getElementById('s-stage').textContent,
    series: document.getElementById('s-series').textContent,
    rowsRebuilt: window.__rows,
  };
}"""

OBSERVE = """() => {
  window.__rows = 0;
  new MutationObserver(ms => { window.__rows += ms.length; })
    .observe(document.getElementById('rows'), {childList: true});
}"""


def _open(browser, base: str, run_id: str, **context):
    page = browser.new_page(viewport={"width": 1400, "height": 900}, **context)
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(RECORD)
    page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
    page.wait_for_function(DRAWN, timeout=15000)
    page.wait_for_timeout(500)
    return page, errors


# ----------------------------------------------------------------------
# the theme (WP-1429)
# ----------------------------------------------------------------------
def _rgb(value: str) -> tuple[int, int, int]:
    """A colour as a triple, from either spelling a browser hands back.

    A canvas reports a colour it was given as `#rrggbb`, or as `rgba(…)` when
    it has an alpha; `getComputedStyle` answers in `rgb()`. Comparing strings
    would be comparing spellings.
    """
    value = value.strip()
    if value.startswith("#"):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(int(float(n)) for n in re.findall(r"[\d.]+", value)[:3])


def _inks(styles) -> set[tuple[int, int, int]]:
    return {_rgb(s) for s in styles}


#: The chrome's colours, and the main pane's inks since the record was cleared.
THEME_STATE = """() => {
  const root = document.documentElement;
  const main = (""" + INKS + """)()[0];
  return {
    stamped: root.dataset.theme ?? null,
    strokes: main.stroke, fills: main.fill,
    page: getComputedStyle(document.body).backgroundColor,
    ink: getComputedStyle(document.body).color,
  };
}"""


def _painted(state: dict, token: str, *, op: str) -> bool:
    """Whether the main pane painted ``token``'s colour with ``op``."""
    return _rgb(token) in _inks(state["strokes" if op == "stroke" else "fills"])


@pytest.mark.parametrize("choice", ["dark", "light"])
def test_the_page_is_drawn_in_the_theme_the_gui_stored(browser, tmp_path,
                                                       monkeypatch, choice):
    """Chrome *and* curves, against the GUI's own token values (WP-1429).

    The assertion that matters is the calculated line: the watcher drew it
    `#ff9d4d` and the GUI `#e56a52`, so a reader with both open saw one fit in
    two colour schemes.  Read off the canvas's own record of what it
    painted, rather than off what the series was handed, and never painted in
    the other theme first.
    """
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    (state / "settings.json").write_text(
        json.dumps({"ui": {"theme": choice}}), encoding="utf-8")
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        drawn = page.evaluate(THEME_STATE)
        page.close()
    assert errors == []
    tokens = TOKENS[choice]
    other = TOKENS["light" if choice == "dark" else "dark"]
    assert drawn["stamped"] == choice
    assert _painted(drawn, tokens["--plot-calc"], op="stroke"), drawn
    assert not _painted(drawn, other["--plot-calc"], op="stroke"), drawn
    assert _painted(drawn, tokens["--plot-obs"], op="fill"), drawn
    assert _rgb(drawn["page"]) == _rgb(tokens["--bg"])
    assert _rgb(drawn["ink"]) == _rgb(tokens["--fg"])


def test_a_theme_changed_in_the_gui_reaches_an_open_page(browser, tmp_path,
                                                         monkeypatch):
    """Through the poll the page already makes, without a reload.

    The canvas is the half CSS cannot repaint: a stylesheet reaches the chrome
    the moment `data-theme` moves, and the plot keeps whatever colours it was
    painted with until something redraws it.  So the page drops the mark it
    uses to skip an unchanged snapshot, and the next poll draws.
    """
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    (state / "settings.json").write_text(
        json.dumps({"ui": {"theme": "dark"}}), encoding="utf-8")
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        before = page.evaluate(THEME_STATE)
        page.evaluate(CLEAR_INK)
        (state / "settings.json").write_text(
            json.dumps({"ui": {"theme": "light"}}), encoding="utf-8")
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        after = page.evaluate(THEME_STATE)
        page.close()
    assert errors == []
    assert _painted(before, TOKENS["dark"]["--plot-calc"], op="stroke")
    assert after["stamped"] == "light"
    assert _rgb(after["page"]) == _rgb(TOKENS["light"]["--bg"])
    # the picture too, which is the half a stylesheet does not reach: it was
    # repainted, and in the new theme's ink alone
    assert _painted(after, TOKENS["light"]["--plot-calc"], op="stroke"), after
    assert not _painted(after, TOKENS["dark"]["--plot-calc"], op="stroke"), after


def test_the_reader_can_choose_a_theme_here_and_it_is_stored(browser,
                                                             tmp_path,
                                                             monkeypatch):
    """WP-1429 made the GUI the one writer, and the person this page exists
    for never opens it (WP-1438).

    Measured on this machine: ``settings.json`` held ``light``, the watcher
    obeyed it correctly, and there was nothing on the page that could change
    it. The click is the whole verb — the chrome, the canvas and the file.
    """
    from rietx.viz import theme as theme_mod

    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    (state / "settings.json").write_text(
        json.dumps({"recent": ["/keep.rex"], "ui": {"theme": "light"}}),
        encoding="utf-8")
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        offered = page.evaluate(
            "() => [...document.querySelectorAll('#theme button')].map("
            "  b => [b.dataset.choice, b.textContent,"
            "        b.getAttribute('aria-pressed')])")
        page.evaluate(CLEAR_INK)
        page.click("#theme button[data-choice='dark']")
        page.wait_for_timeout(600)
        after = page.evaluate(THEME_STATE)
        pressed = page.evaluate(
            "() => [...document.querySelectorAll('#theme button')]"
            ".filter(b => b.getAttribute('aria-pressed') === 'true')"
            ".map(b => b.dataset.choice)")
        page.close()
    assert not errors, errors

    # the three, in the module's order, wearing the module's glyphs
    assert [c for c, _, _ in offered] == list(theme_mod.THEME_CHOICES)
    assert [g for _, g, _ in offered] == [theme_mod.THEME_GLYPHS[c]
                                          for c in theme_mod.THEME_CHOICES]
    assert [c for c, _, on in offered if on == "true"] == ["light"]

    # the chrome, and the canvas, which is the half a stylesheet cannot reach
    assert after["stamped"] == "dark"
    assert _rgb(after["page"]) == _rgb(TOKENS["dark"]["--bg"])
    assert _painted(after, TOKENS["dark"]["--plot-calc"], op="stroke"), after
    assert not _painted(after, TOKENS["light"]["--plot-calc"], op="stroke"), after
    assert pressed == ["dark"]

    # and the file, with the rest of it intact
    assert theme_mod.theme_choice() == "dark"
    stored = json.loads((state / "settings.json").read_text(encoding="utf-8"))
    assert stored == {"recent": ["/keep.rex"], "ui": {"theme": "dark"}}


def test_choosing_system_hands_the_question_back_to_the_browser(browser,
                                                                tmp_path,
                                                                monkeypatch):
    """"Follow the system" is a choice, not the absence of one (WP-1029).

    It stores ``system`` and takes the explicit stamp *off* the root, so the
    ``prefers-color-scheme`` block in ``tokens.css`` answers — which no server
    can do, not being able to see the machine the page is open on.
    """
    from rietx.viz import theme as theme_mod

    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    (state / "settings.json").write_text(
        json.dumps({"ui": {"theme": "light"}}), encoding="utf-8")
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id, color_scheme="dark")
        light = page.evaluate(THEME_STATE)
        page.evaluate(CLEAR_INK)
        page.click("#theme button[data-choice='system']")
        page.wait_for_timeout(600)
        followed = page.evaluate(THEME_STATE)
        page.close()
    assert not errors, errors
    assert light["stamped"] == "light"
    assert _rgb(light["page"]) == _rgb(TOKENS["light"]["--bg"])
    # no stamp, and the browser's own dark answers
    assert followed["stamped"] is None
    assert _rgb(followed["page"]) == _rgb(TOKENS["dark"]["--bg"])
    # and the canvas with it, which no stylesheet repaints
    assert _painted(followed, TOKENS["dark"]["--plot-calc"], op="stroke"), followed
    assert theme_mod.theme_choice() == "system"


def test_a_stage_that_frees_the_background_leaves_the_tick_colours_alone(
        browser, tmp_path):
    """A phase's row keeps its colour across a stage boundary (WP-1429).

    The row has to be nameable against the list beside it, so a colour that
    moves under the reader is worse than one that is merely not the GUI's.
    Measured while WP-1429 briefly handed these rows to plotly's own colorway,
    which the GUI's tick rows took: the colorway was indexed by position in the
    trace array and the background trace is conditional, so the stage that
    frees the background moved every row one step along it — `phase 0` from
    `#d62728` to `#9467bd` with no reader action. `#d62728` is also 0.043 from
    `--plot-calc` in OKLab, a third of the distance the curve colours are held
    apart by, which is the two-marks-in-one-red shape WP-1210 exists to
    prevent. So each row wears its `--phase-N` whatever else is drawn, and
    this reads the tick band's canvas either side of the stage.
    """
    watched = _make_tree(tmp_path, n_done=2)
    _write_stage(watched, "cell", scale=0.7, noise=30.0, rwp=0.3, bkg=False)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        before = page.evaluate(INKS)[1]["stroke"]
        page.evaluate(CLEAR_INK)
        time.sleep(0.05)
        _write_stage(watched, "biso", scale=1.0, noise=4.0, rwp=0.05, bkg=True)
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        after = page.evaluate(INKS)[1]["stroke"]
        stage = page.evaluate("() => document.getElementById('s-stage').textContent")
        page.close()
    assert errors == []
    assert stage == "stage 3/3 biso", "the stage never landed"
    # the four follow no theme (`viz/theme.PHASE_TOKENS`)
    rows = {_rgb(PHASE_TOKENS["--phase-0"]), _rgb(PHASE_TOKENS["--phase-1"])}
    assert _inks(before) >= rows, before
    assert _inks(after) >= rows, "the stage did not repaint the band"
    assert _inks(before) == _inks(after), \
        "a stage boundary moved a phase's tick colour"


#: The tick band's pixel for a tick at ``tt`` in ``row`` of ``rows``, in the
#: page's coordinates, where a pointer can be sent.
TICK_AT = """([tt, row, rows]) => {
  const u = document.getElementById('plot').__rx.panes.ticks;
  const o = u.over.getBoundingClientRect();
  return {x: o.x + u.valToPos(tt, 'x'), y: o.y + o.height * (row + 0.5) / rows};
}"""

TIP = """() => {
  const tip = document.querySelector('#plot .tip');
  return tip.hidden ? null : tip.textContent;
}"""


def _point_at(page, tt: float, row: int, rows: int = 2):
    at = page.evaluate(TICK_AT, [tt, row, rows])
    page.mouse.move(at["x"], at["y"])
    page.wait_for_timeout(150)
    return page.evaluate(TIP)


def test_a_tick_says_which_reflection_it_is(browser, tmp_path):
    """It hovered the 2θ alone, which the axis under it already says
    (WP-1438).

    Pointed at, in the row the tick is in: the label is the row's own indices
    over the 2θ. The fixture's `(2 0 −1)` carries a minus, spelled U+2212 in
    front of the digit — `formatHkl`'s own output, which
    `gui/src/lib/plot.test.ts` holds `hklLabel` equal to.
    """
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        seen = {tt: _point_at(page, tt, row)
                for tt, row in ((25.0, 0), (44.0, 0), (63.0, 1))}
        # the other row, at the same angle, has no tick there
        wrong_row = _point_at(page, 25.0, 1)
        # and between ticks nothing is named
        between = _point_at(page, 35.0, 0)
        page.close()
    assert not errors, errors
    assert seen == {25.0: "(1 1 0)\n25.0000°", 44.0: "(2 0 −1)\n44.0000°",
                    63.0: "(0 0 2)\n63.0000°"}, seen
    assert wrong_row is None
    assert between is None


def test_a_snapshot_with_no_indices_keeps_the_hover_it_had(browser, tmp_path):
    """`rietx watch` opens directories somebody else wrote, including ones
    written before this (WP-1438).

    The fallback is the 2θ the row always hovered, never a label reading
    `undefined`: a page that gets worse on an older file is worse than one
    that simply gains nothing.
    """
    watched = _make_tree(tmp_path, n_done=2)
    snapshot = json.loads(
        (watched / runs.SNAPSHOT_FILE).read_text(encoding="utf-8"))
    for row in snapshot["ticks"].values():
        row.pop("hkl", None)
    (watched / runs.SNAPSHOT_FILE).write_text(json.dumps(snapshot),
                                              encoding="utf-8")
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        seen = [_point_at(page, 25.0, 0), _point_at(page, 63.0, 1)]
        page.close()
    assert not errors, errors
    assert seen == ["25.0000°", "63.0000°"], seen


def test_a_stage_changes_the_text_and_nothing_else(browser, tmp_path):
    """The WP's acceptance: two polls after the writer moves on, every
    dimension the eye fixes on is where it was."""
    watched = _make_tree(tmp_path)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        page.evaluate(OBSERVE)
        page.evaluate("() => { document.getElementById('runs').scrollTop = 250; }")
        page.wait_for_timeout(300)
        before = page.evaluate(GEOMETRY)

        # a later stage: the fit converged, the residual tightened
        time.sleep(0.05)
        _write_stage(watched, "biso", scale=1.0, noise=4.0, rwp=0.05)
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        after = page.evaluate(GEOMETRY)
        page.close()

    assert not errors, errors
    # the poll happened: what the slots say moved with the writer
    assert before["stage"] == "stage 2/3 cell"
    assert after["stage"] == "stage 3/3 biso"
    assert before["series"] == after["series"] == "pattern 5/8 cpd-1e backward"
    assert before["stripText"] != after["stripText"]
    # and nothing the eye fixes on did
    for key in ("bar", "strip", "slots", "cols", "plot", "size", "x", "y", "y3"):
        assert before[key] == after[key], key
    assert before["listScroll"] == after["listScroll"] == 250
    assert after["rowsRebuilt"] == 0, "a poll rebuilt the run list"
    # the Δ/σ range is the one dimension that is the fit's: it stepped down
    # the ladder, symmetric both times
    assert before["y2"] == [-50, 50]
    assert after["y2"] == [-5, 5]


def test_the_ranges_are_the_datas(browser, tmp_path):
    """The x range is the pattern's span and the intensity range the observed
    curve's, with the page's own padding — never a range fitted to whatever
    the stage drew, which here is a calculated curve at 0.7 of the data."""
    watched = _make_tree(tmp_path, n_done=1)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        got = page.evaluate(GEOMETRY)
        page.close()
    assert not errors, errors
    # the pattern's span, as the GUI shows it
    assert got["x"] == [pytest.approx(10), pytest.approx(80)]
    snap = _snapshot("cell", scale=0.7, noise=30.0)
    lo, hi = min(snap["y_obs"]), max(snap["y_obs"])
    span = hi - lo
    assert got["y"] == [pytest.approx(lo - 0.03 * span, abs=0.1),
                        pytest.approx(hi + 0.05 * span, abs=0.1)]
    # two tick rows on a pane of their own, whose range no zoom moves and
    # whose height is the rows' (`rxplot.tickHeight`: 12 + 16 a row)
    assert got["y3"] == {"range": [0, 1], "height": 12 + 16 * 2}


def test_a_zoom_survives_a_stage(browser, tmp_path):
    """A stage is new numbers for the figure on screen, never a new figure.

    The reader's x range holds across it, which is the whole reason the
    picture stopped being a page that reloads (WP-1402), while the Δ/σ axis
    still steps down its ladder, being the fit's. A double-click goes back to
    the whole pattern.
    """
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        box = page.evaluate("() => { const b = document.getElementById('plot')"
                            ".__rx.panes.main.over.getBoundingClientRect();"
                            " return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }")
        page.mouse.move(box["x"], box["y"])
        page.mouse.wheel(0, -300)
        page.wait_for_timeout(300)
        zoomed = page.evaluate(GEOMETRY)
        time.sleep(0.05)
        _write_stage(watched, "biso", scale=1.0, noise=4.0, rwp=0.05)
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        landed = page.evaluate(GEOMETRY)
        page.mouse.dblclick(box["x"], box["y"])
        page.wait_for_timeout(300)
        reset = page.evaluate(GEOMETRY)
        page.close()

    assert not errors, errors
    assert landed["stage"] == "stage 3/3 biso", "the stage never landed"
    lo, hi = zoomed["x"]
    assert 10 < lo < hi < 80, zoomed["x"]
    assert landed["x"] == zoomed["x"]
    assert zoomed["y2"] == [-50, 50] and landed["y2"] == [-5, 5]
    assert reset["x"] == [10, 80]


LEGEND = """() => Object.fromEntries([...document.querySelectorAll('#plot .legend button')]
  .map(b => [b.dataset.id, b.getAttribute('aria-pressed')]))"""


def _light(monkeypatch, tmp_path) -> None:
    """A state directory of the test's own, so the page draws in the light
    theme whatever this machine's reader chose."""
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    (state / "settings.json").write_text(
        json.dumps({"ui": {"theme": "light"}}), encoding="utf-8")


def test_the_legend_hides_a_curve_and_a_stage_keeps_it_hidden(browser, tmp_path,
                                                             monkeypatch):
    """Clicking an entry hides its curve until it is clicked again, and a
    stage landing in between brings nothing back."""
    _light(monkeypatch, tmp_path)
    watched = _make_tree(tmp_path, n_done=2)
    calc = _rgb(TOKENS["light"]["--plot-calc"])
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        page.click("#plot .legend button[data-id='calc']")
        page.wait_for_timeout(200)
        page.evaluate(CLEAR_INK)
        time.sleep(0.05)
        _write_stage(watched, "biso", scale=1.0, noise=4.0, rwp=0.05)
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        hidden = page.evaluate(INKS)[0]["stroke"]
        pressed = page.evaluate(LEGEND)
        page.evaluate(CLEAR_INK)
        page.click("#plot .legend button[data-id='calc']")
        page.wait_for_timeout(200)
        shown = page.evaluate(INKS)[0]["stroke"]
        page.close()

    assert not errors, errors
    assert pressed == {"obs": "true", "calc": "false", "bkg": "true",
                       "diff": "true", "ticks:phase 0": "true",
                       "ticks:phase 1": "true"}
    assert hidden, "the stage did not repaint the picture"
    assert calc not in _inks(hidden)
    assert calc in _inks(shown)


def test_the_picture_exports_from_a_menu_in_the_bar(browser, tmp_path, monkeypatch):
    """D6: the four exports sit behind one word in the bar, which keeps its one
    row at the narrowest window. The SVG loads svgcanvas from the watcher's own
    server, and the file is named after the run."""
    _light(monkeypatch, tmp_path)
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path) if r.path == watched)
        page, errors = _open(browser, base, run_id)
        asked: list[str] = []
        page.on("request", lambda r: asked.append(r.url.removeprefix(base)))
        page.click("#export > summary")
        with page.expect_download() as download:
            page.click("#export-menu button:text-is('SVG')")
        name = download.value.suggested_filename
        said = page.text_content("#export-menu output")
        page.set_viewport_size({"width": 420, "height": 700})
        page.wait_for_timeout(100)
        bar = page.evaluate("(() => { const b = document.getElementById('bar');"
                            " return [b.scrollWidth, b.clientWidth]; })()")
        page.close()

    assert not errors, errors
    assert name == f"rietx-{run_id}.svg" and said == "saved an SVG"
    assert "/svgcanvas.esm.js" in asked
    # nothing in the bar runs past its edge at 420 px
    assert bar[0] <= bar[1], bar


def test_the_residual_carries_the_three_sigma_band(browser, tmp_path,
                                                   monkeypatch):
    """Δ/σ has expectation 1 under a correct model, so the band puts the
    residual on an absolute scale (Toby 2024): `--ok` at 15 %, from −3 to +3
    on whatever rung the axis is at."""
    _light(monkeypatch, tmp_path)
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        bands = page.evaluate("""() => {
          const resid = window.__canvasId(document.querySelectorAll('#plot canvas')[2]);
          return window.__ink.filter(m => m.canvas === resid && m.op === 'fillRect'
                                          && Math.abs(m.alpha - 0.15) < 1e-9)
                             .map(m => m.style);
        }""")
        page.close()
    assert not errors, errors
    assert _rgb(TOKENS["light"]["--ok"]) in _inks(bands), bands


def test_a_grip_collapses_its_pane_and_the_other_takes_the_room(browser, tmp_path):
    """WP-1425: the list's toggle button is gone and the grips do their job.

    A double-click on a grip collapses the pane it sizes, and the choice
    survives a reload — which is the whole of what `toggle-runs` did, minus a
    control.

    `toggle-run` is the other one and it came back in WP-1438, for the pane no
    grip sizes — so this page carries it and the grips still answer for
    themselves, which is what the rest of this test measures.
    """
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        assert page.query_selector("#toggle-runs") is None
        assert page.query_selector("#toggle-run") is not None, (
            "the run pane's own command (WP-1438)")
        both = page.evaluate(GEOMETRY)

        page.dblclick("#grip-list")
        page.wait_for_timeout(600)
        list_closed = page.evaluate(GEOMETRY)
        assert page.evaluate("() => document.body.dataset.list") == "closed"
        # the choice survives a reload
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(600)
        assert page.evaluate("() => document.body.dataset.list") == "closed"
        # ...and the same grip is the way back, a collapsed pane's only one
        page.dblclick("#grip-list")
        page.wait_for_timeout(600)
        assert page.evaluate("() => document.body.dataset.list") == "open"

        # the console's seam is the same control over the other pair
        picture_before = page.evaluate(
            "() => Math.round(document.getElementById"
            "('picture').getBoundingClientRect().height)")
        page.dblclick("#grip-console")
        page.wait_for_timeout(600)
        assert page.evaluate(
            "() => document.getElementById('run').dataset.console") == "closed"
        picture_after = page.evaluate(
            "() => Math.round(document.getElementById"
            "('picture').getBoundingClientRect().height)")
        page.close()

    assert not errors, errors
    # the grip keeps its 5 px, because with the buttons gone it is the only
    # way back to a collapsed pane
    assert list_closed["plot"][0] == 5
    assert list_closed["plot"][2] > both["plot"][2]
    assert list_closed["size"][2] > both["size"][2], "the plot did not resize"
    assert picture_after > picture_before, "the picture did not take the room"


def test_with_no_run_in_the_url_the_page_follows_the_newest(browser, tmp_path):
    _make_tree(tmp_path, n_done=3)
    with _served(tmp_path) as base:
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{base}/", wait_until="networkidle")
        page.wait_for_timeout(int(1.5 * POLL * 1000))
        assert page.evaluate("() => document.getElementById('s-stage').textContent") \
            == "stage 2/3 cell"
        selected = page.evaluate("() => document.querySelector('tr.run.selected').dataset.id")
        newest = page.evaluate("() => document.querySelector('tr.run').dataset.id")
        assert selected == newest
        assert page.evaluate("() => location.hash") == ""
        # a newer run arrives: the page moves to it, the URL still says nothing
        later = tmp_path / "later"
        later.mkdir()
        (later / runs.EVENTS_FILE).write_text(
            json.dumps({"record": "event", "v": "2", "t": 2e9,
                        "kind": "fit_start", "data": {}}) + "\n",
            encoding="utf-8")
        (later / runs.STATUS_FILE).write_text(
            json.dumps({"state": "done", "stage": "scale", "rwp": 0.5}),
            encoding="utf-8")
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        assert page.evaluate("() => document.getElementById('s-stage').textContent") \
            == "stage scale"
        assert page.evaluate("() => location.hash") == ""
        # clicking a row pins it
        page.click("tr.run:nth-child(2)")
        page.wait_for_timeout(int(1.5 * POLL * 1000))
        assert page.evaluate("() => location.hash").startswith("#/run/")
        assert page.evaluate("() => document.getElementById('s-stage').textContent") \
            == "stage 2/3 cell"
        page.close()


# ----------------------------------------------------------------------
# WP-1426: what moves when a stage lands, a run arrives, or the window changes
#
# Two instruments, because neither sees what the other does. The browser's own
# `layout-shift` entry is the measure of a *box* moving, and it names the
# element; it is blind to the picture, the plot being canvases the chart
# repaints without the layout engine ever hearing about it. Measured on the
# page before this WP, under plotly: a stage that freed the background took the
# plot area from y=45 to y=64 and reported a layout shift of exactly 0. So the
# picture is read off the chart's own plot box, each pane's `over`, which is
# where that movement would be.
# ----------------------------------------------------------------------

OBSERVE_SHIFT = """() => {
  window.__shifts = [];
  new PerformanceObserver(list => {
    for (const e of list.getEntries()) window.__shifts.push({
      value: e.value,
      nodes: (e.sources || []).map(s =>
        s.node ? (s.node.id || s.node.tagName + '.' + (s.node.className || '')) : null),
    });
  }).observe({type: 'layout-shift', buffered: true});
}"""

#: Reading drains, so each read covers the interval since the last one and the
#: shifts of settling in after load are never charged to a later act.
READ_SHIFT = """() => {
  const s = window.__shifts;
  window.__shifts = [];
  return {sum: s.reduce((a, e) => a + e.value, 0), n: s.length,
          nodes: s.flatMap(e => e.nodes)};
}"""

#: The main pane's plot area and the legend, in the plot div's own
#: coordinates. The area's top growing is the picture being pushed down by
#: whatever sits above it.
PLOT_GEOMETRY = """() => {
  const div = document.getElementById('plot');
  const pr = div.getBoundingClientRect();
  const box = el => { const b = el.getBoundingClientRect();
                      return [b.x - pr.x, b.y - pr.y, b.width, b.height].map(Math.round); };
  const area = box(div.__rx.panes.main.over);
  const g = div.querySelector('.legend');
  const legend = box(g);
  return {entries: g.children.length, area, legend,
          rel: [legend[0] - area[0], legend[1] - area[1]],
          div: [Math.round(pr.width), Math.round(pr.height)]};
}"""

#: A wipe and a tail are both `childList` mutations, and the console's *line
#: count* tells them apart not at all: the wipe re-fetched from offset 0 and
#: put all 121 lines back, so before WP-1426 the count was 121 either way.
#: What separates them is whether any node was removed, whether the node that
#: was first still is, and whether a reader scrolled up kept their place.
WATCH_CONSOLE = """() => {
  const pane = document.getElementById('console');
  window.__con = {removed: 0, added: 0};
  window.__firstNode = pane.firstElementChild;
  new MutationObserver(ms => { for (const m of ms) {
    window.__con.removed += m.removedNodes.length;
    window.__con.added += m.addedNodes.length; } })
    .observe(pane, {childList: true});
}"""

READ_CONSOLE = """() => {
  const pane = document.getElementById('console');
  return Object.assign({}, window.__con, {
    lines: pane.childElementCount,
    sameFirstNode: window.__firstNode === pane.firstElementChild,
    scrollTop: Math.round(pane.scrollTop)});
}"""


def _pinned(browser, base: str, run_id: str):
    """Open a run named in the URL, and check the URL still names it.

    `run_id` is a digest of the path string (``runs.run_id_for``), so a caller
    that walked one spelling of a directory while the server walked another
    hands over an id the page cannot find — whereupon the page clears the hash
    and follows the newest run instead, which is a different measurement
    wearing this one's name. ``tmp_path`` is already resolved and the two
    agree; this says so rather than trusting it.
    """
    page, errors = _open(browser, base, run_id)
    assert page.evaluate("() => location.hash") == f"#/run/{run_id}", \
        "the page did not stay on the run this test pinned"
    return page, errors


#: The list pane's floor, read off the page it is drawn on.
#:
#: `watch.css` states the rule and the page obeys it: 71ch of declared columns
#: plus whatever box the pane carries, *measured* rather than added as a
#: constant. These tests used to add 1 for the border and nothing for a
#: scrollbar, which is true only where the scrollbar is an overlay — and macOS
#: decides that from whether a mouse is attached (measured both ways on one
#: machine within an hour, 1 px and 16). So the bar is the rule, not a number.
LIST_FLOOR = """() => {
  const runs = document.getElementById('runs');
  const probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;visibility:hidden;width:10ch';
  document.body.appendChild(probe);
  const ch = probe.getBoundingClientRect().width / 10;
  probe.remove();
  return {ch: ch, chrome: runs.offsetWidth - runs.clientWidth,
          floor: Math.round(71 * ch) + (runs.offsetWidth - runs.clientWidth)};
}"""


def _drag(page, selector: str, dx: int, dy: int) -> None:
    """Drag a grip by (dx, dy), in steps, the way a pointer arrives."""
    box = page.locator(selector).bounding_box()
    assert box is not None, selector
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    steps = 20
    for i in range(1, steps + 1):
        page.mouse.move(box["x"] + box["width"] / 2 + dx * i / steps,
                        box["y"] + box["height"] / 2 + dy * i / steps)
    page.mouse.up()
    page.wait_for_timeout(400)


SEAM = """() => {
  const plot = document.getElementById('plot');
  const main = plot && plot.__rx && plot.__rx.panes.main;
  const px = el => Math.round(el.getBoundingClientRect().width);
  const py = el => Math.round(el.getBoundingClientRect().height);
  return {
    list: px(document.getElementById('runs')),
    run: px(document.getElementById('run')),
    console: py(document.getElementById('console')),
    picture: py(document.getElementById('picture')),
    inner: main ? [px(main.over), py(main.over)] : null,
    box: [px(plot), py(plot)],
    resizes: window.__resizes,
    stored: JSON.parse(localStorage.getItem('rietx-watch-layout') || 'null'),
    valuenow: +document.getElementById('grip-list')
      .getAttribute('aria-valuenow'),
    valuemax: +document.getElementById('grip-list')
      .getAttribute('aria-valuemax'),
  };
}"""

#: Each time the main pane was given a new size. The chart's ResizeObserver
#: gives it one (`rxplot.panes`), at most once a frame.
COUNT_RESIZES = """() => {
  window.__resizes = 0;
  const main = document.getElementById('plot').__rx.panes.main;
  const orig = main.setSize;
  main.setSize = function (...a) {
    window.__resizes += 1;
    return orig.apply(this, a);
  };
}"""


def test_a_drag_moves_the_seam_and_the_picture_follows_it(browser, tmp_path):
    """WP-1425's acceptance, and the defect it was opened for.

    Measured before the change, under plotly: moving the list seam from 72ch
    to 40ch drew **zero** `Plots.resize` calls. The plot *element* followed the
    seam, 879 px wide to 1110, while plotly's inner size stayed at 807 — the
    picture drawn 303 px narrower than its own box, and nothing repaired it
    until the pane was collapsed and reopened. So what this asserts is not
    that the number of resizes is small; it is that the inner size moved at
    all, and by what the box did.
    """
    watched = _make_tree(tmp_path, n_done=6)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        page.evaluate(COUNT_RESIZES)
        before = page.evaluate(SEAM)

        _drag(page, "#grip-list", 180, 0)
        after = page.evaluate(SEAM)

        # the choice survives a reload, and is applied before the plot is drawn
        page.reload(wait_until="networkidle")
        page.wait_for_function(DRAWN, timeout=15000)
        page.wait_for_timeout(500)
        page.evaluate(COUNT_RESIZES)
        reloaded = page.evaluate(SEAM)

        # ...and a window that cannot hold it re-clamps it, because a drag
        # clamps against the extent it happened in and nothing else does
        page.set_viewport_size({"width": 900, "height": 900})
        page.wait_for_timeout(700)
        narrow = page.evaluate(SEAM)
        page.set_viewport_size({"width": 1400, "height": 900})
        page.wait_for_timeout(700)
        back = page.evaluate(SEAM)
        page.close()

    assert not errors, errors
    # the seam moved, by about what the pointer asked for
    assert after["list"] == pytest.approx(before["list"] + 180, abs=4)
    assert after["run"] == pytest.approx(before["run"] - 180, abs=4)
    # and the picture followed it, which is the whole WP: narrower by what
    # its box lost, the axis gutter beside it unchanged
    assert after["inner"][0] < before["inner"][0]
    assert (after["box"][0] - after["inner"][0]
            == pytest.approx(before["box"][0] - before["inner"][0], abs=1)), \
        "the plot is drawn at a width that is not its box's"
    # told by the observer, at most once a frame, so a 20-move drag is at
    # most 20 of the 2-3 ms resizes WP-1461's pilot measured
    assert 0 < after["resizes"] <= 20, after["resizes"]
    # persisted on the verb
    assert reloaded["stored"]["list"]["size"] == pytest.approx(after["list"],
                                                              abs=2)
    assert reloaded["list"] == pytest.approx(after["list"], abs=2)
    # re-clamped at render against the window it reopened in: 900 px of window
    # cannot hold a 700 px list *and* the 340 px the run pane keeps
    assert narrow["list"] < reloaded["list"]
    assert narrow["list"] == pytest.approx(narrow["valuemax"], abs=2)
    assert narrow["run"] >= 340
    # ...and the stored size is still the reader's, so the wide window gives it
    # back rather than keeping what a narrow one could afford
    assert back["list"] == pytest.approx(reloaded["list"], abs=2)


STACK = """() => {
  const r = el => { const b = el.getBoundingClientRect();
                    return [Math.round(b.width), Math.round(b.height)]; };
  const grip = document.getElementById('grip-list');
  const body = document.body;
  return {
    stacked: getComputedStyle(document.documentElement)
      .getPropertyValue('--stacked').trim(),
    flow: getComputedStyle(document.getElementById('main')).flexDirection,
    runs: r(document.getElementById('runs')),
    run: r(document.getElementById('run')),
    grip: r(grip),
    orientation: grip.getAttribute('aria-orientation'),
    cursor: getComputedStyle(grip).cursor,
    overflow: [document.documentElement.scrollWidth,
               document.documentElement.clientWidth],
    listVar: body.style.getPropertyValue('--list'),
    listHVar: body.style.getPropertyValue('--list-h'),
    stored: JSON.parse(localStorage.getItem('rietx-watch-layout') || '{}'),
  };
}"""


def test_a_window_too_narrow_for_two_panes_stacks_them(browser, tmp_path):
    """Measured at 420 px before this: the list kept its declared 80ch =
    578 px, the run pane came out **0 px wide**, and the document scrolled to
    1283 px against a 420 px window (WP-1438).

    The seam could not have saved it. 71ch of columns is 513 px at this font,
    plus the pane's 1 px border, the grip's 5 and the 340 px of picture the
    run pane keeps — 859 px, below which the two panes cannot both meet their
    floors however the seam is dragged. So below it they stack, and the same
    seam sizes the list's height instead of its width.
    """
    watched = _make_tree(tmp_path, n_done=6)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        wide = page.evaluate(STACK)
        page.set_viewport_size({"width": 500, "height": 900})
        page.wait_for_timeout(700)
        narrow = page.evaluate(STACK)
        page.set_viewport_size({"width": 1400, "height": 900})
        page.wait_for_timeout(700)
        back = page.evaluate(STACK)
        page.close()
    assert not errors, errors

    assert wide["stacked"] == "0" and wide["flow"] == "row"
    assert narrow["stacked"] == "1" and narrow["flow"] == "column"
    # both panes get the whole width, and neither is nothing
    assert narrow["runs"][0] == 500 and narrow["run"][0] == 500
    assert narrow["runs"][1] > 80 and narrow["run"][1] > 200
    # the defect itself: no horizontal scroll at any width
    assert narrow["overflow"][0] == narrow["overflow"][1] == 500
    # the separator turned with the panes
    assert narrow["orientation"] == "horizontal"
    assert narrow["cursor"] == "row-resize"
    assert narrow["grip"][0] == 500
    # and the arrangement is not a one-way door
    assert back["stacked"] == "0" and back["flow"] == "row"
    assert back["orientation"] == "vertical"


def test_a_seam_dragged_stacked_does_not_move_the_wide_one(browser, tmp_path):
    """A px width is not a px height, so the two arrangements store two
    numbers (WP-1438; Chrome DevTools keeps a setting per orientation for the
    same reason). One number for both would hand the reader a pane they never
    asked for the moment the window turns.
    """
    watched = _make_tree(tmp_path, n_done=6)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        _drag(page, "#grip-list", -120, 0)          # a width, side by side
        wide = page.evaluate(STACK)

        page.set_viewport_size({"width": 500, "height": 900})
        page.wait_for_timeout(700)
        _drag(page, "#grip-list", 0, 90)            # a height, stacked
        stacked = page.evaluate(STACK)

        page.set_viewport_size({"width": 1400, "height": 900})
        page.wait_for_timeout(700)
        back = page.evaluate(STACK)
        page.close()
    assert not errors, errors

    chosen_width = wide["runs"][0]
    assert chosen_width < 560, "the wide drag did not narrow the list"
    chosen_height = stacked["runs"][1]
    assert chosen_height > 200, "the stacked drag did not grow the list"
    # two fields, and the stacked drag left the first alone
    assert stacked["stored"]["list"]["size"] == wide["stored"]["list"]["size"]
    assert stacked["stored"]["list"]["stackedSize"] is not None
    assert stacked["stored"]["list"]["stackedSize"] != \
        stacked["stored"]["list"]["size"]
    # and coming back is the width that was chosen, not the height
    assert back["runs"][0] == chosen_width


def test_a_phone_width_list_sheds_columns_before_it_sheds_the_name(browser,
                                                                   tmp_path):
    """Stacked at 500 px every name read `5…` (WP-1438).

    The six declared columns are 66ch = 477 px at this font and the run
    column is what is left, so the one thing a reader picks a run by is the
    one thing the table drops. Below 563 px the stage and the start time go
    instead — the two the page answers elsewhere, the strip naming the stage
    and the list's own order carrying the time.

    The assertion is per column and not a count, because the mechanism that
    fails here fails *silently*: `display:none` on the cells shifts every
    later one a place left into the colgroup, so Rwp inherited the zeroed
    width while the launch button took GoF's 9ch and the table still had the
    right number of visible cells.
    """
    watched = _make_tree(tmp_path, n_done=6)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        page.set_viewport_size({"width": 380, "height": 900})
        page.wait_for_timeout(700)
        cells = page.evaluate(
            "() => [...document.querySelectorAll('#rows tr')][0]"
            ".querySelectorAll('td')"
            " && [...[...document.querySelectorAll('#rows tr')][0].cells]"
            ".map(td => [td.textContent.trim(),"
            "            Math.round(td.getBoundingClientRect().width)])")
        page.close()
    assert not errors, errors

    widths = [w for _, w in cells]
    text = [t for t, _ in cells]
    # state, run, (stage), Rwp, GoF, (started), gui — seven cells, two at zero
    assert len(cells) == 7, cells
    assert widths[2] == 0 and widths[5] == 0, cells
    for i in (0, 1, 3, 4, 6):
        assert widths[i] > 20, (i, cells)
    # the values are still in their own columns: Rwp is a percentage and GoF
    # is not, which is what the shift got wrong
    assert text[3].endswith("%"), cells
    assert text[4] and not text[4].endswith("%"), cells
    # and the name has room to be a name
    assert widths[1] > 60, cells


def test_a_drag_stops_at_the_floor_the_columns_set(browser, tmp_path):
    """The list's floor is measured, not chosen.

    Its five declared columns are 58ch and that is the table's whole
    min-content; the run column takes the remainder, so it absorbs every
    narrowing alone and hits 0 px at 56ch with the table overflowing the
    panel. `run` as a heading inks 36 px, so the floor is the width below
    which a column cannot show its own name.
    """
    watched = _make_tree(tmp_path, n_done=6)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        _drag(page, "#grip-list", -400, 0)       # far past the floor
        floored = page.evaluate(SEAM)
        floor = page.evaluate(LIST_FLOOR)
        # the run column still has room for its own heading, which is what the
        # floor is for
        head = page.evaluate(
            "() => { const th = document.querySelectorAll('th')[1];"
            "        return [Math.round(th.getBoundingClientRect().width),"
            "                th.scrollWidth]; }")
        page.close()

    assert not errors, errors
    # 71ch of columns plus the pane's own box, the basis being border-box;
    # the assertion that matters is the next one. 63ch until WP-1428 gave the
    # list the launch button's 8ch column. The box is read off the page and
    # not added as a constant, for the reason `LIST_FLOOR` carries.
    assert floored["list"] == pytest.approx(floor["floor"], abs=2)
    assert floor["ch"] == pytest.approx(7.225, abs=0.05), floor
    assert floored["list"] == floored["valuenow"]
    assert head[0] >= head[1], head


def test_the_console_seam_is_the_same_control_the_other_way_up(browser, tmp_path):
    """The log's grip grows it upward, which is the sign `dragged` carries
    per edge rather than globally."""
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        page.evaluate(COUNT_RESIZES)
        before = page.evaluate(SEAM)
        # the pointer goes *up*, and the pane below the grip gets taller
        _drag(page, "#grip-console", 0, -120)
        after = page.evaluate(SEAM)
        page.close()

    assert not errors, errors
    assert after["console"] == pytest.approx(before["console"] + 120, abs=6)
    assert after["picture"] == pytest.approx(before["picture"] - 120, abs=6)
    # the picture is shorter and the plot was told, at most once a frame
    assert after["inner"][1] < before["inner"][1]
    assert 0 < after["resizes"] <= 20, after["resizes"]


def test_the_grips_carry_the_aria_splitter_keyboard(browser, tmp_path):
    """The WAI-ARIA window splitter pattern, so nobody has to invent one.

    It is a pattern rather than a library, so the javascript is still the
    page's; what the pattern fixes is what the keys do.
    """
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        grip = page.locator("#grip-list")
        assert grip.get_attribute("role") == "separator"
        assert grip.get_attribute("aria-orientation") == "vertical"
        assert grip.get_attribute("aria-controls") == "runs"

        grip.focus()
        start = page.evaluate(SEAM)
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(250)
        left = page.evaluate(SEAM)
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(250)
        right = page.evaluate(SEAM)
        page.keyboard.press("End")
        page.wait_for_timeout(300)
        end = page.evaluate(SEAM)
        page.keyboard.press("Home")
        page.wait_for_timeout(300)
        home = page.evaluate(SEAM)
        floor = page.evaluate(LIST_FLOOR)
        # Enter collapses, and the pane it collapses is the one it sizes
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        collapsed = page.evaluate("() => document.body.dataset.list")
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        restored = page.evaluate("() => document.body.dataset.list")
        page.close()

    assert not errors, errors
    assert left["list"] == start["list"] - 16
    assert right["list"] == start["list"]
    # End and Home are the seam's stops, and they are the clamp's own numbers
    assert end["list"] == end["valuemax"]
    assert home["list"] < end["list"]
    # 66ch of declared columns plus 5ch for the run column's own heading, and
    # the pane's own box on top — read off the page rather than added as a
    # constant (`LIST_FLOOR`). 58 + 5 until WP-1428's launch column.
    assert home["list"] == pytest.approx(floor["floor"], abs=2)
    assert collapsed == "closed"
    assert restored == "open"


def test_the_old_panel_choice_survives_more_than_one_render(browser, tmp_path):
    """WP-1423's key carried one bit, and migrating it is a write.

    `readLayout` folds `runs: false` into the new shape and drops the old key.
    Nothing else stores a layout — `storeLayout` is reached only from a drag,
    an arrow key or a collapse — so dropping the old key without writing the
    new one spends the migration on a single render: the list is closed once,
    and the reload after it finds neither key and opens it again.
    """
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # a reader who collapsed the list before this WP shipped
        page.add_init_script(
            "try { localStorage.setItem('rietx-watch-panels',"
            " JSON.stringify({runs: false, run: true})); } catch (e) {}")
        page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
        page.wait_for_timeout(700)
        first = page.evaluate("() => document.body.dataset.list")
        keys = page.evaluate(
            "() => [localStorage.getItem('rietx-watch-panels'),"
            "       localStorage.getItem('rietx-watch-layout')]")

        # the init script runs on every navigation, so the old key is put back
        # before the reload: the page must prefer what it stored itself
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(700)
        second = page.evaluate("() => document.body.dataset.list")
        page.close()

    assert not errors, errors
    assert first == "closed", "the old choice was not carried over at all"
    assert keys[0] is None, "the old key outlived its migration"
    assert keys[1] is not None, "the migration stored nothing"
    assert second == "closed", "the migrated choice was lost on the reload"


def test_a_run_with_no_picture_cannot_hide_its_only_content(browser, tmp_path):
    """A GUI project's run writes a log and never a snapshot.

    `#run.full` hides the console's grip, there being no picture to size
    against — and the grip is the collapse's only control now that the buttons
    are gone. Collapsed first and then opened on such a run, the reader would
    get a strip, a "no picture here" line, and no way to reach the one thing
    the run has. The rule this replaces was "closing the last open panel opens
    the other".
    """
    project = tmp_path / "sample.rex" / "live"
    project.mkdir(parents=True)
    (project / runs.EVENTS_FILE).write_text(
        json.dumps({"record": "event", "v": "2", "t": 1e9,
                    "kind": "fit_start", "data": {}}) + "\n",
        encoding="utf-8")
    (project / runs.STATUS_FILE).write_text(
        json.dumps({"state": "done", "stage": "biso", "rwp": 0.1, "gof": 1.4}),
        encoding="utf-8")

    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path))
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # the log collapsed from an earlier run that did have a picture
        page.add_init_script(
            "try { localStorage.setItem('rietx-watch-layout',"
            " JSON.stringify({list: {size: null, open: true},"
            "                 console: {size: null, open: false}})); }"
            " catch (e) {}")
        page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
        page.wait_for_timeout(700)
        seen = page.evaluate("""() => {
          const run = document.getElementById('run');
          const con = document.getElementById('console');
          const grip = document.getElementById('grip-console');
          const box = el => {
            const b = el.getBoundingClientRect();
            return [Math.round(b.width), Math.round(b.height)];
          };
          return {
            full: run.classList.contains('full'),
            stored: run.dataset.console,
            console: box(con),
            grip: box(grip),
            noplot: !!document.getElementById('noplot'),
          };
        }""")
        page.close()

    assert not errors, errors
    assert seen["full"] and seen["noplot"], "this is not the picture-less case"
    assert seen["stored"] == "closed", "the stored collapse was not applied"
    # the grip is gone, so the collapse it is the only control for goes too
    assert seen["grip"] == [0, 0]
    assert seen["console"][1] > 0, "the run panel is showing nothing at all"


def test_the_legend_is_a_dimension_the_page_fixes(browser, tmp_path):
    """A window resize moves the legend with the plot and nothing else.

    Under plotly the legend sat above the plot area, where plotly grew the top
    margin to fit it. Narrowing the window wrapped its one row to two and then
    four, and each row came out of the picture: the plot area's top ran
    46 → 65 → 139 px and its height 465 → 446 → 372 across 1400 → 700 px. A
    resize moves everything by design, so the bar is not a layout shift of
    zero; it is that the legend's box relative to the plot area is the same at
    every width, which is what "a dimension the page fixes" means.

    The legend is now the page's own, laid over the plot area at its top left
    and as wide as the area at most, so it wraps inside the picture. The widths
    are all **side by side**: below 859 px the two panes stack (WP-1438), and
    then the picture is shorter because the list took the top of the window,
    which is a pane changing and not a legend growing.
    """
    _make_tree(tmp_path, n_done=2)
    seen = {}
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path.name == "watched")
        page, errors = _pinned(browser, base, run_id)
        for width in (1400, 1000, 860):
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(800)
            seen[width] = page.evaluate(PLOT_GEOMETRY)
        # and once past the seam, where the height moves for a reason that is
        # not this one. What stacking changes is the pane, never what the
        # legend takes out of it.
        page.set_viewport_size({"width": 700, "height": 900})
        page.wait_for_timeout(800)
        stacked = page.evaluate(PLOT_GEOMETRY)
        page.close()

    assert not errors, errors
    tops = {w: g["area"][1] for w, g in seen.items()}
    heights = {w: g["area"][3] for w, g in seen.items()}
    rows = {w: g["legend"][3] for w, g in seen.items()}
    # the legend wrapped as the window narrowed, which is the case at issue
    assert rows[860] > rows[1400], rows
    # and took nothing from the picture for it
    assert len(set(tops.values())) == 1, tops
    assert len(set(heights.values())) == 1, heights
    # its top left is the plot area's, and it is never wider, at every width
    for width, g in [*seen.items(), (700, stacked)]:
        assert g["rel"] == [0, 0], (width, g)
        assert g["legend"][2] <= g["area"][2], (width, g)
    # stacked: a shorter pane, the same top, the same legend rule
    assert stacked["area"][1] == tops[1400], stacked
    assert stacked["area"][3] < heights[860], (stacked, heights)


#: A viewport where the legend's fifth entry fits on one row and its sixth
#: wraps. Measured in chromium: five entries take 409 px in one row and six
#: 504, and the plot area is the viewport less 690 px with the list open, so
#: 1150 leaves it 460.
WRAPS_AT_SIX = 1150


def test_a_stage_that_adds_a_legend_entry_does_not_move_the_picture(browser, tmp_path):
    """The stage that frees the background is the one that used to jump.

    It adds a curve, the curve adds a legend entry, the entry wraps the legend
    to a second row, and under plotly the row came out of the picture. No
    `layout-shift` entry was ever raised for it: the plot div's own box is
    untouched, and the movement was entirely inside the redraw. Both
    instruments are read here, and the point of the second is that the first
    reported 0 while the picture moved 19 px.
    """
    watched = _make_tree(tmp_path, n_done=4)
    _write_stage(watched, "cell", scale=0.7, noise=30.0, rwp=0.3, bkg=False)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _pinned(browser, base, run_id)
        # narrow enough that the sixth entry is the one that wraps the row
        page.set_viewport_size({"width": WRAPS_AT_SIX, "height": 800})
        page.wait_for_timeout(800)
        page.evaluate(OBSERVE_SHIFT)
        page.wait_for_timeout(300)
        page.evaluate(READ_SHIFT)
        before = page.evaluate(PLOT_GEOMETRY)
        _write_stage(watched, "bkg", scale=0.9, noise=10.0, rwp=0.2, bkg=True)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        after = page.evaluate(PLOT_GEOMETRY)
        shift = page.evaluate(READ_SHIFT)
        page.close()

    assert not errors, errors
    # the stage landed, and it is the legend's entries that changed
    assert before["entries"] + 1 == after["entries"]
    assert after["legend"][3] > before["legend"][3], "the legend did not gain a row"
    # and the picture did not move
    assert before["area"] == after["area"]
    assert before["div"] == after["div"]
    assert shift["sum"] == 0, shift


def test_a_stage_lands_with_no_layout_shift(browser, tmp_path):
    """The ordinary stage boundary, on both instruments."""
    watched = _make_tree(tmp_path, n_done=4)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _pinned(browser, base, run_id)
        page.evaluate(OBSERVE_SHIFT)
        page.wait_for_timeout(300)
        page.evaluate(READ_SHIFT)
        before = page.evaluate(PLOT_GEOMETRY)
        time.sleep(0.05)
        _write_stage(watched, "biso", scale=1.0, noise=4.0, rwp=0.05)
        page.wait_for_timeout(int(2.5 * POLL * 1000))
        after = page.evaluate(PLOT_GEOMETRY)
        shift = page.evaluate(READ_SHIFT)
        stage = page.evaluate("() => document.getElementById('s-stage').textContent")
        page.close()

    assert not errors, errors
    assert stage == "stage 3/3 biso", "the poll never happened"
    assert shift["sum"] == 0, shift
    assert before["area"] == after["area"]


def test_a_run_arriving_holds_the_readers_place(browser, tmp_path):
    """A new run is prepended, and the list must not move under the reader.

    Every row below the insertion goes down a row's height. Measured before
    WP-1426: one arrival on a scrolled list, 0.0134 of layout shift across four
    rows. A list already at its top is the other case and is left alone, the
    arriving run being the thing a reader at the top is watching for.
    """
    watched = _make_tree(tmp_path, n_done=40)

    def arrive(name: str, t: float) -> None:
        d = tmp_path / name
        d.mkdir()
        (d / runs.EVENTS_FILE).write_text(
            json.dumps({"record": "event", "v": "2", "t": t,
                        "kind": "fit_start", "data": {}}) + "\n", encoding="utf-8")
        (d / runs.STATUS_FILE).write_text(
            json.dumps({"state": "done", "stage": "scale", "rwp": 0.5}),
            encoding="utf-8")

    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _pinned(browser, base, run_id)

        page.evaluate("() => { document.getElementById('runs').scrollTop = 250; }")
        page.wait_for_timeout(300)
        page.evaluate(OBSERVE_SHIFT)
        page.wait_for_timeout(200)
        page.evaluate(READ_SHIFT)
        rows_before = page.evaluate("() => document.getElementById('rows').childElementCount")
        arrive("later-a", 2e9)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        scrolled = page.evaluate(READ_SHIFT)
        rows_after = page.evaluate("() => document.getElementById('rows').childElementCount")
        moved_to = page.evaluate("() => document.getElementById('runs').scrollTop")

        # and again with the list at its top
        page.evaluate("() => { document.getElementById('runs').scrollTop = 0; }")
        page.wait_for_timeout(300)
        page.evaluate(READ_SHIFT)
        arrive("later-b", 3e9)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        at_top = page.evaluate("() => document.getElementById('runs').scrollTop")
        newest_visible = page.evaluate(
            "() => { const box = document.getElementById('runs');"
            "        const tr = document.querySelector('tr.run');"
            "        return tr.getBoundingClientRect().top"
            "               >= box.getBoundingClientRect().top - 1; }")
        page.close()

    assert not errors, errors
    assert rows_after == rows_before + 1, "the run never arrived"
    # the reader's rows are where they were, and the scroll took the difference
    assert scrolled["sum"] == 0, scrolled
    assert moved_to > 250, "the scroll was not compensated"
    # a list at its top stays at its top, and the new run is what is there
    assert at_top == 0
    assert newest_visible


def test_the_console_survives_the_picture_being_rebuilt(browser, tmp_path):
    """A run opened before its first snapshot keeps its log at that snapshot.

    The picture and the console shared a builder, so the kind going from
    'none' to 'json' wiped the console and re-tailed it from offset 0: 121
    lines out and 121 back, and a reader who had scrolled up to read was
    dropped at the bottom. The line count is the one thing that did *not*
    change, which is why nothing about it is asserted here.
    """
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / runs.EVENTS_FILE).write_text(
        "".join(json.dumps({"record": "event", "v": "2", "t": 1e9 + i,
                            "kind": "iteration", "data": {"i": i}}) + "\n"
                for i in range(120)), encoding="utf-8")
    (bare / runs.STATUS_FILE).write_text(
        json.dumps({"state": "running", "stage": "scale", "rwp": 0.4}),
        encoding="utf-8")

    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path) if r.path == bare)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        assert page.evaluate("() => !document.getElementById('plot')"), \
            "this run was supposed to open with no picture"
        # a reader who scrolled up to read
        page.evaluate("() => { document.getElementById('console').scrollTop = 200; }")
        page.wait_for_timeout(200)
        page.evaluate(WATCH_CONSOLE)
        page.wait_for_timeout(200)
        _write_stage(bare, "cell", scale=0.7, noise=30.0, rwp=0.3)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        console = page.evaluate(READ_CONSOLE)
        drawn = page.evaluate("() => !!document.getElementById('plot')")
        page.close()

    assert not errors, errors
    assert drawn, "the picture was never built"
    assert console["removed"] == 0, "the console was wiped"
    assert console["added"] == 0, "the console was re-tailed"
    assert console["sameFirstNode"]
    assert console["scrollTop"] == 200, "the reader lost their place"


# ----------------------------------------------------------------------
# what a poll costs (WP-1427)
# ----------------------------------------------------------------------
#: Installed before the page's own script, so the observer is watching by the
#: time anything is drawn. The page does not carry one: an observer nobody
#: reads is telemetry on somebody's overnight tab.
LONG_TASKS = """
window.__long = [];
try {
  new PerformanceObserver(list => {
    for (const e of list.getEntries()) window.__long.push(Math.round(e.duration));
  }).observe({type: 'longtask', buffered: true});
} catch (e) { window.__long = null; }
"""

SPANS = """() => {
  const out = {};
  for (const e of performance.getEntriesByType('measure')) {
    (out[e.name] ||= []).push(+e.duration.toFixed(1));
  }
  return {spans: out, long: window.__long,
          lines: document.getElementById('console').childElementCount,
          gap: document.querySelector('#console .muted')?.textContent ?? null};
}"""

#: A runaway guard and not a timer (root CLAUDE.md § Testing). The render this
#: bounds measured 31.0 ms after the cap landed and 997 ms before it, so
#: anything in between is this machine having a bad day and anything above it
#: is the cap gone.
LONG_TASK_CEILING_MS = 300


def _boot_traffic(browser, url: str):
    """Load `url` and return the ordered network log of the boot.

    Each entry is ``("req"|"res", path)`` in the order the browser issued or
    received it, which is what these two tests are about: not how long the
    boot took on this machine, but what waited for what.
    """
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors: list[str] = []
    traffic: list[tuple[str, str]] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: traffic.append(("req", r.url.split("/", 3)[-1])))
    page.on("response", lambda r: traffic.append(("res", r.url.split("/", 3)[-1])))
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(300)
    return page, errors, traffic


def test_the_log_is_asked_for_before_the_walk_answers(browser, tmp_path):
    """The console comes back with the page, not a beat after it (WP-1438).

    Measured on a reload with a run pinned: the list and the picture were
    drawn at 107 ms with the console still empty, and it filled at 248 ms —
    the log's fetch was third in a chain of three, behind a boot walk and
    then the first poll's walk. A run named in the URL is known before
    anything is fetched, so its log is asked for beside the walk instead.

    Asserted as an ordering rather than a duration: a threshold in
    milliseconds would be a measurement of the machine.
    """
    watched = _make_tree(tmp_path, n_done=3)
    with _served(tmp_path) as base:
        page, errors, traffic = _boot_traffic(
            browser, f"{base}/#/run/{runs.read_run(watched).run_id}")
        page.close()
    assert not errors, errors
    events_req = next(i for i, (kind, path) in enumerate(traffic)
                      if kind == "req" and "/events" in path)
    runs_res = next(i for i, (kind, path) in enumerate(traffic)
                    if kind == "res" and path.endswith("api/runs"))
    assert events_req < runs_res, (
        "the log waited for the walk to answer:\n"
        + "\n".join(f"  {k} {v}" for k, v in traffic))


def test_the_boot_walks_the_directory_once(browser, tmp_path):
    """The page's constants rode on a fetch of their own, and needed none.

    `api/runs` carries `single_run_id`, `can_cancel` and `can_open_gui` on
    every poll, so asking for them separately was the same request twice
    about 85 ms apart — with the log queued behind both.
    """
    watched = _make_tree(tmp_path, n_done=3)
    with _served(tmp_path) as base:
        page, errors, traffic = _boot_traffic(
            browser, f"{base}/#/run/{runs.read_run(watched).run_id}")
        page.close()
    assert not errors, errors
    walks = [path for kind, path in traffic
             if kind == "req" and path.endswith("api/runs")]
    assert len(walks) == 1, walks


def test_two_readers_of_one_log_do_not_append_it_twice(browser, tmp_path):
    """The boot's fetch and the walk's fetch are the same tail (WP-1438).

    Both take `tail.offset`, so two in flight would append the same lines
    twice and the reader would meet a doubled log. They are serialised, and
    the second finds the offset the first moved.
    """
    watched = tmp_path / "run"
    watched.mkdir()
    lines = [json.dumps({"record": "event", "v": "2", "t": 1.0 + i,
                         "kind": "iteration", "data": {"i": i}})
             for i in range(60)]
    (watched / runs.EVENTS_FILE).write_text("\n".join(lines) + "\n",
                                            encoding="utf-8")
    with _served(tmp_path) as base:
        page, errors = _open_list(browser, base)
        page.wait_for_timeout(1500)     # a poll beyond the boot
        drawn = page.evaluate(
            "() => [...document.querySelectorAll('#console .line')]"
            ".filter(el => !el.classList.contains('gap'))"
            ".map(el => el.textContent)")
        page.close()
    assert not errors, errors
    assert len(drawn) == 60, len(drawn)
    assert len(set(drawn)) == 60, "a line was appended twice"


def test_opening_a_long_log_does_not_freeze_the_page(browser, tmp_path):
    """A reader clicks a job that has been running a while (WP-1427).

    ``resetTail`` asks from offset 0, so the whole log arrives on one poll.
    Uncapped, 60 000 events were parsed and built into ``<div>``s to keep the
    last 2000: 997 ms of frozen main thread and three long tasks, measured in
    this browser. The pane names its own length as the route's ``limit``, so
    what arrives is what the pane can hold, and what did not arrive is counted
    in a line the reader can see.
    """
    n_events = 40_000
    d = tmp_path / "long"
    d.mkdir()
    (d / runs.EVENTS_FILE).write_text(
        "".join(json.dumps({"record": "event", "v": "2", "t": 1e9 + i,
                            "kind": "eval",
                            "data": {"i": i, "cost": 1234.56789 / (i + 1),
                                     "series_index": 4, "series_n": 8,
                                     "series_label": "cpd-1e"}}) + "\n"
                for i in range(n_events)), encoding="utf-8")
    (d / runs.STATUS_FILE).write_text(
        json.dumps({"state": "running", "stage": "biso", "rwp": 0.2}),
        encoding="utf-8")

    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path) if r.path == d)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(LONG_TASKS)
        page.goto(f"{base}/#/run/{run_id}", wait_until="domcontentloaded")
        page.wait_for_function(
            "() => document.getElementById('console').childElementCount > 0",
            timeout=30000)
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        seen = page.evaluate(SPANS)
        page.close()

    assert not errors, errors
    # the pane holds what a pane holds, however long the log is
    assert seen["lines"] <= 2001, seen["lines"]
    assert seen["gap"] and "earlier lines" in seen["gap"], seen["gap"]

    long = seen["long"]
    assert long is not None, "this browser reports no long tasks; the guard is blind"
    worst = max(long, default=0)
    assert worst <= LONG_TASK_CEILING_MS, (
        f"a poll froze the page for {worst} ms; the tail cap is the thing to "
        f"look at (WP-1427). All tasks over 50 ms: {sorted(long, reverse=True)}")


def test_an_idle_poll_does_no_work_at_all(browser, tmp_path):
    """The page's own spans, which is how any of this was measured.

    A poll where nothing changed asks for the list and is told it has not
    moved, so there is nothing to parse and nothing to patch. The picture is
    not redrawn either, its mtime not having moved. What is left of an idle
    poll is one conditional request.
    """
    watched = _make_tree(tmp_path, n_done=40)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        page.evaluate("() => performance.clearMeasures()")
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        seen = page.evaluate(SPANS)
        page.close()

    assert not errors, errors
    spans = seen["spans"]
    assert "runs:net" in spans, sorted(spans)
    assert "runs:parse" not in spans, "an idle poll parsed a list it had"
    assert "runs:patch" not in spans, "an idle poll patched a list it had"
    assert "snap:draw" not in spans, "an idle poll redrew the picture"
    assert all(v >= 0 for vals in spans.values() for v in vals)


def test_a_run_that_moves_still_reaches_the_list(browser, tmp_path):
    """The other half of the tag: a 304 must mean *this list*, not *a list*.

    Without this, the test above is satisfied by a page that stopped polling.
    """
    watched = _make_tree(tmp_path, n_done=40)
    stage = "() => document.getElementById('s-stage').textContent"
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page, errors = _open(browser, base, run_id)
        before = page.evaluate(stage)
        _write_stage(watched, "biso", scale=0.95, noise=2.0, rwp=0.11)
        page.wait_for_timeout(int(4.0 * POLL * 1000))
        after = page.evaluate(stage)
        seen = page.evaluate(SPANS)
        page.close()

    assert not errors, errors
    assert before != after, (before, after)
    assert "biso" in after
    # the poll that carried the change did parse and patch
    assert "runs:patch" in seen["spans"], sorted(seen["spans"])


def test_a_click_moves_the_highlight_on_a_poll_that_did_not_move(browser,
                                                                 tmp_path):
    """The highlight follows the URL, and the URL moves without the list.

    A directory of finished runs answers every poll with a 304, which is what
    the tag is for. `patchList` was the one place the `selected` class was set,
    so a click there left the highlight on the row the reader had just come
    from, for as long as nothing on disk changed — which, on a directory
    nobody is writing to, is forever.
    """
    _make_tree(tmp_path, n_done=4)
    with _served(tmp_path) as base:
        found = {r.path.name: r.run_id for r in runs.discover(tmp_path)}
        page, errors = _open(browser, base, found["watched"])
        page.evaluate("() => performance.clearMeasures()")
        page.click(f'tr[data-id="{found["old-02"]}"]')
        page.wait_for_timeout(int(3.0 * POLL * 1000))
        seen = page.evaluate(SPANS)
        selected = page.evaluate(
            "() => [...document.querySelectorAll('tr.run.selected')]"
            ".map(tr => tr.dataset.id)")
        page.close()

    assert not errors, errors
    # nothing was written, so the polls after the click were all 304s: this is
    # the case the highlight has to survive
    assert "runs:patch" not in seen["spans"], sorted(seen["spans"])
    assert selected == [found["old-02"]], selected


def test_the_console_is_re_tailed_when_the_run_changes(browser, tmp_path):
    """The other half of the rule above: a reset still happens when it should.

    The tail follows the log, so moving to another run must drop it. Without
    this the console would keep the previous run's lines and carry an offset
    into a file it does not belong to.
    """
    for name, n in (("run-a", 10), ("run-b", 40)):
        d = tmp_path / name
        d.mkdir()
        (d / runs.EVENTS_FILE).write_text(
            "".join(json.dumps({"record": "event", "v": "2", "t": 1e9 + i,
                                "kind": "iteration", "data": {"i": i}}) + "\n"
                    for i in range(n)), encoding="utf-8")
        (d / runs.STATUS_FILE).write_text(
            json.dumps({"state": "done", "stage": name, "rwp": 0.1}),
            encoding="utf-8")

    lines = "() => document.getElementById('console').childElementCount"
    with _served(tmp_path) as base:
        found = {r.path.name: r.run_id for r in runs.discover(tmp_path)}
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}/#/run/{found['run-a']}", wait_until="networkidle")
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        first = page.evaluate(lines)
        page.evaluate("id => { location.hash = '#/run/' + id; }", found["run-b"])
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        second = page.evaluate(lines)
        page.evaluate("id => { location.hash = '#/run/' + id; }", found["run-a"])
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        back = page.evaluate(lines)
        page.close()

    assert not errors, errors
    assert (first, second, back) == (10, 40, 10)



# ----------------------------------------------------------------------
# WP-1424: every number is drawn whole, and every row can be told apart
#
# `table-layout: fixed` makes a `<col>` width the cell's whole box, padding
# included, so a column declared wide enough for its content is short by the
# 14 px the cell pads with. Nothing about that is visible in the markup or to
# a substring assertion: the cell renders, the text is in the DOM, and the
# browser quietly replaces the last character with an ellipsis.
#
# What is measured is the ink against the room — the range rectangle of the
# cell's contents against its content box — rather than `scrollWidth`, which
# is the same as `clientWidth` for anything whose overflow is `visible` and so
# reports 0 for a `<th>` whose heading is spilling into its neighbour.
# ----------------------------------------------------------------------

#: Every cell and slot, with how far its contents overrun the box.
OVERFLOW = """() => {
  const out = [];
  const rng = document.createRange();
  const add = (what, el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none') return;
    rng.selectNodeContents(el);
    const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
    const room = el.clientWidth - pad;
    const ink = rng.getBoundingClientRect().width;
    out.push({what: what, over: +(ink - room).toFixed(2), room: room,
              ink: +ink.toFixed(2), text: el.textContent.trim(),
              title: el.getAttribute('title')});
  };
  const heads = [...document.querySelectorAll('#runs th')];
  heads.forEach(th => add('th:' + th.textContent.trim(), th));
  [...document.querySelectorAll('tr.run')].forEach((tr, r) =>
    [...tr.children].forEach((td, i) =>
      add(`td${r}:` + heads[i].textContent.trim(), td)));
  [...document.querySelectorAll('#strip > *')].forEach(el =>
    add('slot:' + el.id, el));
  return out;
}"""

def _open_list(browser, base: str):
    """The page, waiting on the run list rather than on a plot.

    :func:`_open` waits for the drawn chart (:data:`DRAWN`), which a run with
    no snapshot never grows. These tests are about the list, and want runs that
    are an event log and nothing else.
    """
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base, wait_until="networkidle")
    page.wait_for_selector("tr.run", timeout=15000)
    page.wait_for_timeout(400)
    return page, errors


def _bare_run(directory: Path, t: float = 1.0) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / runs.EVENTS_FILE).write_text(
        json.dumps({"record": "event", "v": "2", "t": t, "kind": "fit_start",
                    "data": {}}) + "\n", encoding="utf-8")
    return directory


def test_the_launch_button_is_drawn_only_for_a_run_in_a_project(browser,
                                                                tmp_path):
    """One row has a project behind it and the other does not (WP-1428).

    A bare ``fit()`` records under the runs directory with nothing to copy, so
    its row offers no button. The button is in the list rather than the status
    strip because the strip drops its flexible slot below 990 px of run panel
    and an ordinary window is under that (WP-1424), which is how the GUI
    command the page already had came to be invisible.
    """
    _bare_run(tmp_path / "loose")
    _bare_run(tmp_path / "sample.rex" / "live" / "20260917-120000-1234", t=2.0)

    with _served(tmp_path) as base:
        page, errors = _open_list(browser, base)
        seen = page.evaluate(
            "() => [...document.querySelectorAll('tr.run')].map(tr => ["
            "  tr.children[1].textContent.trim().split(' ')[0],"
            "  !tr.querySelector('td.gui button').hidden])")
        page.close()
    assert not errors, errors
    # the names carry a `· legacy` tail, these runs having no `meta.json`;
    # the first word is the label and the second value is the whole claim
    assert dict(seen) == {"sample.rex": True, "loose": False}


def test_the_row_with_no_button_says_why_it_has_none(browser, tmp_path):
    """An empty cell is an answer the reader has to guess at (WP-1438).

    The two shapes sat side by side in the list with the difference between
    them showing only as a missing control, which reads as a control that
    failed. The run that cannot be opened gets an em dash carrying the
    reason, and the run that can gets the button and no dash.
    """
    _bare_run(tmp_path / "loose")
    _bare_run(tmp_path / "sample.rex" / "live" / "20260917-120000-1234", t=2.0)

    with _served(tmp_path) as base:
        page, errors = _open_list(browser, base)
        seen = page.evaluate(
            "() => [...document.querySelectorAll('tr.run')].map(tr => ["
            "  tr.children[1].textContent.trim().split(' ')[0], {"
            "    button: !tr.querySelector('td.gui button').hidden,"
            "    dash: !tr.querySelector('td.gui .why').hidden,"
            "    why: tr.querySelector('td.gui .why').getAttribute('title')}])")
        page.close()
    assert not errors, errors
    cells = dict(seen)
    assert cells["sample.rex"]["button"] is True
    assert cells["sample.rex"]["dash"] is False
    assert cells["loose"]["button"] is False
    assert cells["loose"]["dash"] is True
    assert "project" in (cells["loose"]["why"] or "").lower()


def test_a_read_only_watcher_explains_nothing_per_row(browser, tmp_path):
    """The column is empty for every run, so the reason is not about a run.

    Saying "no project to open" on a row whose project is right there would
    be a false claim about that run; the reason is the whole page's.
    """
    _bare_run(tmp_path / "loose")
    _bare_run(tmp_path / "sample.rex" / "live" / "20260917-120000-1234", t=2.0)
    with _served(tmp_path, allow_cancel=False, allow_gui=False) as base:
        page, errors = _open_list(browser, base)
        shown = page.evaluate(
            "() => [...document.querySelectorAll('td.gui .why')]"
            ".some(el => !el.hidden)")
        page.close()
    assert not errors, errors
    assert shown is False


def test_read_only_draws_no_launch_button(browser, tmp_path):
    """The page cannot be the check, and it is not the only answer either.

    A button that only ever 403s is a worse answer than no button, which is
    what the stop button already does under the same flag.
    """
    _bare_run(tmp_path / "sample.rex" / "live" / "20260917-120000-1234")
    with _served(tmp_path, allow_cancel=False, allow_gui=False) as base:
        page, errors = _open_list(browser, base)
        shown = page.evaluate(
            "() => !document.querySelector('td.gui button').hidden")
        page.close()
    assert not errors, errors
    assert shown is False


def test_clicking_launch_selects_the_run_and_says_what_it_is_doing(browser,
                                                                   tmp_path):
    """The click's two visible effects, with the route faked at the network.

    A notice belongs to one run and ``drawRun`` drops one that is not the run
    on screen, so a launch from a row the reader is not looking at would report
    neither its progress nor its refusal. Selecting the run is what gives the
    notice somewhere to appear, and this is what keeps the two together.

    ``window.open`` is stubbed: a real one is a second browser window in the
    middle of a test, and what is measured here is the page. The launch itself
    is ``test_a_real_gui_boots_on_a_scratch_copy_and_the_project_is_untouched``
    in ``test_watch_app.py``.
    """
    for i in range(3):
        _bare_run(tmp_path / f"sample{i}.rex" / "live" / f"2026091{i}-120000-1",
                  t=1.0 + i)

    with _served(tmp_path) as base:
        page, errors = _open_list(browser, base)
        page.route("**/api/run/*/gui", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"url": "http://127.0.0.1:65000/"})))
        page.evaluate("() => { window.open = (u) => { window.__opened = u; }; }")
        # the *last* row, which is not the one the page opened on
        rows = page.locator("tr.run")
        last = rows.nth(rows.count() - 1)
        wanted = last.get_attribute("data-id")
        last.locator("td.gui button").click()
        page.wait_for_timeout(1200)
        after = page.evaluate(
            "() => ({hash: location.hash,"
            " notice: document.getElementById('s-notice').textContent,"
            " opened: window.__opened || null})")
        page.close()

    assert not errors, errors
    assert after["hash"] == f"#/run/{wanted}"
    assert "65000" in after["notice"], after["notice"]
    assert after["opened"] == "http://127.0.0.1:65000/"


#: Which cells must fit and which may elide, by what fills them. A cell the
#: page fills itself — a state word from a closed vocabulary, a number it
#: formats, a clock time — has a worst case the CSS can be sized for, and a
#: reader who cannot see all of it has simply been shown the wrong number. A
#: cell holding a name somebody else chose has no worst case: a stage is the
#: plan author's string (`preferred_orientation` is 21 characters), a label
#: and a path are the caller's. Those may be cut, and what is asserted of them
#: is that the whole string is in a `title` where the reader can still reach
#: it.
#: The two halves are a *partition*, and a cell in neither fails below rather
#: than being quietly waved through: a column or slot added without a decision
#: about which kind it is would otherwise be tested by nothing.
BOUNDED = ("state", "Rwp", "GoF", "started", "gui")
ELIDED = ("run", "stage")
BOUNDED_SLOTS = {"slot:s-state", "slot:s-rwp", "slot:s-gof", "slot:s-free",
                 "slot:s-notice", "slot:stop"}
ELIDED_SLOTS = {"slot:s-label", "slot:s-series", "slot:s-stage",
                "slot:s-where"}


def _batch(root: Path, *, n: int = 4) -> list[Path]:
    """One label over several runs, which is what a batch looks like.

    Every run here is one fit launched from one directory, so
    `RunRecorder._default_label` gives them all the same word and the list
    names nothing. The numbers are the maintainer's, off the 2026-09-16 demo:
    an Rwp that reads `0.1734` in the old form, a GoF of `12.34`, and a start
    time a minute apart run to run. The last run is cancelled, for the
    longest word the state pill has.

    The start times are held inside the *local day*, because `clock` renders a
    date rather than a time for a run that did not start today. Three hours
    back is yesterday between 00:00 and 03:00, so a fixed offset would have
    made this suite fail for three hours out of every twenty-four.
    """
    made = []
    now = time.time()
    midnight = time.mktime((*time.localtime(now)[:3], 0, 0, 0, 0, 0, -1))
    first = max(now - 10800, midnight)
    for i in range(n):
        d = root / f"20260916-14{20 + i:02d}00-9{i}"
        d.mkdir()
        (d / runs.EVENTS_FILE).write_text(
            json.dumps({"record": "event", "v": "2", "t": first + i,
                        "kind": "fit_start", "data": {}}) + "\n",
            encoding="utf-8")
        (d / runs.META_FILE).write_text(
            json.dumps({"record": runs.RECORD_TAG, "label": "campaign",
                        "created": first + 60 * i,
                        "cwd": "/Users/someone/work/campaign",
                        "command": f"python fit_one.py candidate-{i}"}),
            encoding="utf-8")
        (d / runs.SNAPSHOT_FILE).write_text(
            json.dumps(_snapshot("preferred_orientation", scale=0.83,
                                 noise=6.0)), encoding="utf-8")
        (d / runs.STATUS_FILE).write_text(
            json.dumps({"state": "cancelled" if i == n - 1 else "done",
                        "stage": "preferred_orientation", "rwp": 0.1734,
                        "gof": 12.34, "n_free": 17, "index": 3,
                        "n_stages": 3}), encoding="utf-8")
        made.append(d)
    return made


def test_every_number_on_the_page_is_drawn_whole(browser, tmp_path):
    """No cell the page fills itself is cut off, at either window size.

    Measured on the page before WP-1424, in these two viewports, ink minus
    room in CSS pixels: `GoF` over by 7.13 in every row, `state` by 0.62 on
    the cancelled one, the `started` heading by 6.58, and `stage` by 20.67
    with no title to recover it. In the strip, `s-where` over by 1127 at both
    sizes — its `1fr` track had been squeezed to nothing, so the drawn-point
    count and the path were not cut but absent. At 1000x700 `s-stage` went
    with it, over by 136.95 with the stage name the reader is watching for.
    """
    _batch(tmp_path)
    with _served(tmp_path) as base:
        newest = max(runs.discover(tmp_path), key=lambda r: r.created)
        page, errors = _pinned(browser, base, newest.run_id)
        seen = {}
        for width, height in ((1400, 900), (1000, 700)):
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(600)
            seen[width] = page.evaluate(OVERFLOW)
        page.close()

    assert not errors, errors
    # reported per column rather than per cell: forty rows cut the same way
    # is one defect, and the widest cut is the one to size for
    bad = {}
    for width, cells in seen.items():
        for c in cells:
            what = c["what"].split(":")[1]
            if c["what"].startswith("th:"):
                # a heading is the page's own word whatever its column holds
                bounded = True
            else:
                bounded = what in BOUNDED or c["what"] in BOUNDED_SLOTS
                elided = what in ELIDED or c["what"] in ELIDED_SLOTS
                assert bounded != elided, (
                    f"{c['what']} is in neither half of the partition, so "
                    f"nothing here decides whether it may be cut")
            if c["over"] <= 0.5:
                continue
            why = "cut" if bounded else "cut with no title"
            if not bounded and c["title"]:
                continue
            where = (width, c["what"].split(":")[0].rstrip("0123456789")
                     + ":" + what)
            if c["over"] > bad.get(where, (0, ""))[0]:
                bad[where] = (c["over"], why, c["text"])
    assert not bad, sorted(bad.items())


#: Every row's visible text, cell by cell, and the tooltip behind each.
ROWS = """() => [...document.querySelectorAll('tr.run')].map(tr =>
  [...tr.children].map(td => [td.textContent.trim(),
                              (td.firstElementChild || td).getAttribute('title')]))"""


def test_two_runs_of_one_batch_are_told_apart(browser, tmp_path):
    """Forty runs of a batch carry one label, and the list must still name them.

    `RunRecorder._default_label` calls a run after the directory it was
    launched from, so a batch driven from one directory is forty rows reading
    `campaign`, `campaign`, `campaign`. Nothing in the record says what a run
    fitted — that is a caller's fact and WP-1431 gives the caller a way to
    write it — but the record does know when each one started, to the second,
    which is what the run directory is named after. So the started column is
    a clock time rather than `3h ago`, and the row's tooltip carries the
    directory, the command line and the working directory behind it.
    """
    made = _batch(tmp_path, n=6)
    with _served(tmp_path) as base:
        newest = max(runs.discover(tmp_path), key=lambda r: r.created)
        page, errors = _pinned(browser, base, newest.run_id)
        rows = page.evaluate(ROWS)
        page.close()

    assert not errors, errors
    assert len(rows) == len(made)
    # the label column is the same word on every row, which is the defect
    assert len({r[1][0] for r in rows}) == 1
    # and every row is still distinct, in a cell the reader can see
    started = [r[5][0] for r in rows]
    assert len(set(started)) == len(rows), started
    assert all(re.fullmatch(r"\d\d:\d\d:\d\d", s) for s in started), started
    # the tooltip is where the rest of the record is
    titles = [r[1][1] for r in rows]
    assert len(set(titles)) == len(rows), titles
    for i, title in enumerate(sorted(titles)):
        assert "fit_one.py candidate-" in title, title
        assert "in /Users/someone/work/campaign" in title, title


#: Which slots the strip is drawing, and what each one says.
SLOTS = """() => Object.fromEntries(
  [...document.querySelectorAll('#strip > *')].map(el =>
    [el.id, getComputedStyle(el).display === 'none' ? null
            : el.textContent.trim()]))"""


def test_the_status_line_drops_slots_it_cannot_fit(browser, tmp_path):
    """Whole slots go, in a declared order, rather than each being cut a bit.

    The strip's ten slots want 931 px of declared track and the run panel is
    882 at 1400x900 with the list open, so something always goes without.
    Sharing the deficit is the answer that reads worst: before WP-1424 the
    flexible slot was at zero at both sizes and the stage — the fact being
    watched — was cut by 49 px and then 202. The order is what a reader can
    get elsewhere: the GUI command and the label are in the row's tooltip and
    in the list, the free count is in the report, the series in the list.

    The container is the run panel, not the window, so collapsing the list
    brings slots back at an unchanged window size. That is measured here too.
    """
    project = tmp_path / "sample.rex" / "live"
    project.mkdir(parents=True)
    now = time.time()
    (project / runs.EVENTS_FILE).write_text(
        json.dumps({"record": "event", "v": "2", "t": now, "kind": "fit_start",
                    "data": {}}) + "\n", encoding="utf-8")
    (project / runs.META_FILE).write_text(
        json.dumps({"record": runs.RECORD_TAG, "label": "sample.rex",
                    "created": now, "cwd": str(tmp_path),
                    "command": "rietx gui sample.rex"}), encoding="utf-8")
    (project / runs.SNAPSHOT_FILE).write_text(
        json.dumps(_snapshot("preferred_orientation", scale=0.83, noise=6.0)),
        encoding="utf-8")
    (project / runs.STATUS_FILE).write_text(
        json.dumps({"state": "done", "stage": "preferred_orientation",
                    "rwp": 0.1734, "gof": 12.34, "n_free": 17, "index": 3,
                    "n_stages": 4, "series_index": 4, "series_n": 8,
                    "series_label": "cpd-1e", "series_pass": "forward"}),
        encoding="utf-8")

    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path))
        page, errors = _pinned(browser, base, run_id)
        seen = {}
        for width in (1600, 1400, 1000):
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(700)
            seen[width] = page.evaluate(SLOTS)
        page.dblclick("#grip-list")         # the list closes, the panel grows
        page.wait_for_timeout(700)
        wide = page.evaluate(SLOTS)
        page.close()

    assert not errors, errors
    # never dropped, at any width
    for width, slots in seen.items():
        assert slots["s-state"] == "done", (width, slots)
        assert slots["s-rwp"] == "Rwp 17.34%", (width, slots)
        assert slots["s-gof"] == "GoF 12.34", (width, slots)
        assert slots["s-stage"].startswith("stage 3/4 preferred"), (width, slots)
    # the GUI command is the whole of the flexible slot now, the path having
    # moved to the label's tooltip and the point count onto the picture
    assert seen[1600]["s-where"] == "rietx gui --scratch sample.rex"
    assert "pts drawn" not in (seen[1600]["s-where"] or "")
    # and it is the first thing to go
    assert seen[1400]["s-where"] is None
    assert seen[1400]["s-free"] is None
    assert seen[1400]["s-label"] == "sample.rex"
    assert seen[1400]["s-series"] == "pattern 5/8 cpd-1e forward"
    # at 1000 with the list open the panel is 482 px and only the state, the
    # stage and the two numbers are left
    assert seen[1000]["s-label"] is None
    assert seen[1000]["s-series"] is None
    # closing the list gives the panel the window, and the slots come back at
    # a window size that had none of them
    assert wide["s-label"] == "sample.rex"
    assert wide["s-series"] == "pattern 5/8 cpd-1e forward"


# ----------------------------------------------------------------------
# the run pane's collapse (WP-1438)
# ----------------------------------------------------------------------
def test_the_toggle_hides_the_run_and_gives_the_list_the_window(browser,
                                                                tmp_path):
    """WP-1425 removed this and left the question to the maintainer.

    Its argument stands — a splitter's collapse belongs to the pane its grip
    sizes, and neither grip sizes the run pane — so what comes back is a
    *command* rather than a third grip. Practice is why: VS Code has ⌘B as
    well as a draggable sash, because a gesture on a focused 5 px separator is
    not a control anybody finds.

    What the End key does instead is measured here beside it: it drives the
    list to its stop, which leaves the run pane at its own minimum rather than
    at nothing, so the two gestures are not two ways to the same state.
    """
    _bare_run(tmp_path / "20260101-000001-00001")

    with _served(tmp_path) as base:
        page, errors = _open_list(browser, base)
        width = "() => document.getElementById('runs').getBoundingClientRect().width"
        shown = "(id) => document.getElementById(id).offsetParent !== null"
        before = page.evaluate(width)

        page.click("#toggle-run")
        page.wait_for_timeout(300)
        collapsed = page.evaluate(width)
        assert page.evaluate(shown, "run") is False, "the run pane is still up"
        assert page.evaluate(shown, "grip-list") is False, (
            "the grip still sizes a pane that is not there")
        assert page.get_attribute("#toggle-run", "aria-pressed") == "true"

        # it survives a reload, like every other layout choice on this page
        page.reload(wait_until="networkidle")
        page.wait_for_selector("tr.run", timeout=15000)
        page.wait_for_timeout(300)
        assert page.evaluate(shown, "run") is False, "the choice did not persist"
        assert page.get_attribute("#toggle-run", "aria-pressed") == "true"

        page.click("#toggle-run")
        page.wait_for_timeout(300)
        restored = page.evaluate(width)
        assert page.evaluate(shown, "run") is True
        assert page.get_attribute("#toggle-run", "aria-pressed") == "false"

        # and the other gesture: End on the list grip is not this state
        page.focus("#grip-list")
        page.keyboard.press("End")
        page.wait_for_timeout(300)
        dragged_wide = page.evaluate(width)
        run_kept = page.evaluate(
            "() => document.getElementById('run').getBoundingClientRect().width")
        page.close()

    assert not errors, errors
    assert collapsed > before, (before, collapsed)
    assert restored == before, (before, restored)
    # the whole window minus the border, against a list that keeps the run
    # pane's 340 px floor beside it
    assert collapsed > dragged_wide > before, (before, dragged_wide, collapsed)
    assert run_kept >= 300, run_kept


def test_the_run_pane_cannot_be_collapsed_where_there_is_no_list(browser,
                                                                 tmp_path):
    """A single-run directory has no list to give the window to.

    The collapse is stored per origin rather than per directory, so a reader
    who clicked ``full list`` on a directory of runs carries that choice into
    ``rietx watch <one-run>`` served from the same host and port. There the
    stylesheet already hides ``#runs``, ``#grip-list`` *and* the button that
    would undo it, so the stored ``false`` drew a title bar over nothing with
    no control anywhere on the page to bring the run back.

    The choice is kept rather than cleared: it is about the directory of runs
    and applies again the moment there is one.
    """
    _bare_run(tmp_path)

    with _served(tmp_path) as base:
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(
            "try { localStorage.setItem('rietx-watch-layout',"
            " JSON.stringify({run: {size: null, open: false}})); } catch (e) {}")
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(700)
        seen = page.evaluate("""() => {
          const up = id => {
            const el = document.getElementById(id);
            return !!(el && el.offsetParent !== null);
          };
          return {single: 'single' in document.body.dataset,
                  run: document.body.dataset.run,
                  showsRun: up('run'), showsList: up('runs'),
                  showsToggle: up('toggle-run'),
                  stored: JSON.parse(
                    localStorage.getItem('rietx-watch-layout') || '{}')};
        }""")
        page.close()

    assert not errors, errors
    assert seen["single"], "this fixture is not the single-run page"
    assert seen["showsRun"], "the page drew nothing the reader could look at"
    assert seen["run"] == "open"
    # the two halves of why it was unrecoverable, kept as the record of it
    assert not seen["showsList"] and not seen["showsToggle"]
    # and the preference itself is untouched, for the next directory of runs
    assert seen["stored"]["run"]["open"] is False


def test_a_cold_open_shows_the_newest_line_first(browser, tmp_path):
    """What a reader opening a long-running job sees in their first paint.

    Measured before this (WP-1438), on the 7.35 MB log of a 32-pattern series:
    the first line painted at 0.64 s carried events 42 s old, and the tail
    arrived at 1.99 s after a second 4 MiB chunk. The page asks for the end
    now and paints it at 0.69 s.

    The log here is bigger than one read window on purpose — under it there is
    nothing to seek over and the test would pass without the feature.
    """
    d = tmp_path / "long-run"
    d.mkdir()
    lines = [json.dumps({"record": "event", "v": "2", "t": 1e9 + i,
                         "kind": "eval", "data": {"i": i}}) + "\n"
             for i in range(60000)]
    (d / runs.EVENTS_FILE).write_text("".join(lines), encoding="utf-8")
    assert sum(len(line.encode()) for line in lines) > (4 << 20)
    (d / runs.STATUS_FILE).write_text(
        json.dumps({"state": "done", "stage": "biso", "rwp": 0.1}),
        encoding="utf-8")

    last = "() => document.getElementById('console').lastElementChild.textContent"
    top = "() => document.getElementById('console').firstElementChild.textContent"
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path))
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
        page.wait_for_selector("#console div", timeout=15000)
        painted = page.evaluate(last)
        gap = page.evaluate(top)
        page.wait_for_timeout(int(2.0 * POLL * 1000))
        settled = page.evaluate(last)
        page.close()

    assert not errors, errors
    # the newest event of the log, in the first paint rather than after a walk
    assert "i=59999" in painted, painted
    assert "i=59999" in settled, settled
    # and the pane says there is more above it, without claiming a count it
    # would have had to read the whole file to know
    assert "earlier lines are in the log" in gap, gap
    assert re.search(r"\d", gap.split("earlier")[0]) is None, gap


BOXES = """() => {
  const rect = (el) => { const b = el.getBoundingClientRect();
    return {left: b.left, right: b.right, top: b.top, bottom: b.bottom}; };
  const legend = document.querySelector('#plot .legend');
  const note = document.querySelector('#plot .caption');
  return legend && note ? {legend: rect(legend), note: rect(note)} : null;
}"""


@pytest.mark.parametrize("width", [1500, 1180, 900])
def test_the_point_count_is_never_drawn_over_the_legend(browser, tmp_path,
                                                        width):
    """WP-1424's rule on the picture: measure ink against room.

    The caption sat at the paper's top right, which is where the legend's
    first row ends. Measured at 1180 px on a two-phase fit, the row wrapped and
    `Δ/σ` was drawn under `901 of 901 pts drawn`, each legible and the pair not
    (WP-1438). Two marks in one place, and the room up there belongs to the
    legend: it grows with the model, while the caption is one line of a fixed
    length.
    """
    run = tmp_path / "two-phase"
    run.mkdir()
    (run / runs.EVENTS_FILE).write_text(
        json.dumps({"record": "event", "v": "2", "t": 1e9, "kind": "fit_start",
                    "data": {}}) + "\n", encoding="utf-8")
    _write_stage(run, "cell", scale=0.7, noise=3.0, rwp=0.2)

    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path))
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
        page.wait_for_function(DRAWN, timeout=15000)
        page.wait_for_timeout(600)
        boxes = page.evaluate(BOXES)
        page.close()

    assert not errors, errors
    assert boxes, "the legend or the caption was not drawn"
    legend, note = boxes["legend"], boxes["note"]
    overlap = (min(legend["right"], note["right"]) - max(legend["left"], note["left"]) > 0
               and min(legend["bottom"], note["bottom"])
               - max(legend["top"], note["top"]) > 0)
    assert not overlap, f"{width} px: legend {legend} under caption {note}"


#: The caption's box and the x axis title's, in the page's coordinates. The
#: title is canvas ink, so its box is computed: centred on the residual pane's
#: plot area (uPlot's placement) and as wide as its text in the font uPlot
#: drew it in, which uPlot holds scaled by the device pixel ratio.
TITLE_AND_CAPTION = """() => {
  const u = document.getElementById('plot').__rx.panes.resid;
  const o = u.over.getBoundingClientRect(), axis = u.axes[0];
  const ctx = document.createElement('canvas').getContext('2d');
  ctx.font = Array.isArray(axis.labelFont) ? axis.labelFont[0] : axis.labelFont;
  const w = ctx.measureText(axis.label).width / devicePixelRatio;
  const c = document.querySelector('#plot .caption').getBoundingClientRect();
  return {run: Math.round(document.getElementById('run').getBoundingClientRect().width),
          title: [o.left + o.width / 2 - w / 2, o.left + o.width / 2 + w / 2],
          caption: [c.left, c.right]};
}"""


def test_the_point_count_keeps_clear_of_the_axis_title_at_the_floor(browser,
                                                                    tmp_path):
    """WP-1424's rule again, at the narrowest the run pane gets.

    Found by looking at the first chart-module build (WP-1461): at the run
    pane's 340 px floor the caption, then at the title row's right end, ran
    into the centred `2θ (°)` and read `2θ (°)600 of 600 pts drawn`.
    """
    watched = _make_tree(tmp_path, n_done=2)
    with _served(tmp_path) as base:
        run_id = next(r.run_id for r in runs.discover(tmp_path)
                      if r.path == watched)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # a list dragged as wide as it goes, so the run pane is at its floor
        page.add_init_script(
            "try { localStorage.setItem('rietx-watch-layout', JSON.stringify("
            "{list: {size: 5000, open: true}, console: {size: null, open: true}}));"
            " } catch (e) {}")
        page.goto(f"{base}/#/run/{run_id}", wait_until="networkidle")
        page.wait_for_function(DRAWN, timeout=15000)
        page.wait_for_timeout(500)
        seen = page.evaluate(TITLE_AND_CAPTION)
        page.close()

    assert not errors, errors
    assert seen["run"] == 340, "the run pane is not at its floor"
    assert seen["caption"][1] < seen["title"][0], seen
