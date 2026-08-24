"""v0.2 events stream, HTML viewer, live watch, and history merge/cherry-pick."""

import json
import urllib.request
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.history.events import EventStream, read_events
from rietx.strategy.staged import Stage
from tests.test_refine_synthetic import perturbed_models, synthesize

OUT = Path(__file__).parent / "output"


@pytest.fixture(scope="module")
def synthetic_pattern():
    return synthesize()


# ----------------------------------------------------------------------
# event stream
# ----------------------------------------------------------------------
def test_events_written_and_readable(tmp_path, synthetic_pattern):
    structure, ins = perturbed_models()
    log = tmp_path / "events.jsonl"
    ref = rx.Refinement(structure, ins, history=False)
    ref.fit(synthetic_pattern, events=log)

    events = read_events(log)
    kinds = [e.kind for e in events]
    assert kinds[0] == "fit_start"
    assert kinds[-1] == "fit_end"
    stages = [e.data["stage"] for e in events if e.kind == "stage_start"]
    assert stages == ["scale_bkg", "zero", "cell", "profile_w", "profile"]
    # per-iteration heartbeat really came from inside the solver
    evals = [e for e in events if e.kind == "eval"]
    assert len(evals) > 10
    assert all("cost" in e.data and e.data["cost"] >= 0 for e in evals)
    # timestamps are monotone
    ts = [e.t for e in events]
    assert all(b >= a for a, b in zip(ts, ts[1:]))
    # costs within a stage end lower than they start
    for e in events:
        if e.kind == "stage_end":
            assert e.data["cost_final"] <= e.data["cost_initial"] * (1 + 1e-12)


def test_eval_events_carry_the_trajectory_fields(synthetic_pattern):
    """WP-1113: ``accepted``/``step_norm``/``values`` ride every ``eval``.

    Open-dict fields on an existing kind — no ``EVENT_SCHEMA_VERSION`` bump
    (the rule is the module docstring's).  Three properties, per stage: the
    accepted subset is cost-monotone (TRF accepts only strictly better
    trials, and ``accepted`` is that reconstruction made explicit); the first
    evaluation of a solve has no ``step_norm`` (there is no incumbent yet)
    while every later one does; and ``values`` aligns element for element
    with ``stage_start.free_paths``, which is what makes the physical
    trajectory readable off the stream alone.
    """
    structure, ins = perturbed_models()
    seen: list[dict] = []
    ref = rx.Refinement(structure, ins, history=False)
    ref.fit(synthetic_pattern, events=seen.append)

    free_paths: dict[str, list[str]] = {}
    evals: dict[str, list[dict]] = {}
    for event in seen:
        if event["kind"] == "stage_start":
            free_paths[event["data"]["stage"]] = event["data"]["free_paths"]
        elif event["kind"] == "eval":
            evals.setdefault(event["data"]["stage"], []).append(event["data"])
    assert evals and set(evals) == set(free_paths)

    # stage_end names *which* criterion ended the solve — the writer the
    # declared field needs (WP-1076's rule; the vocabulary is
    # LSQOutcome.termination's)
    terminations = [e["data"]["termination"] for e in seen
                    if e["kind"] == "stage_end"]
    assert terminations and all(
        t in {"ftol", "xtol", "gtol", "ftol+xtol", "max_nfev"}
        for t in terminations), terminations

    for stage, stage_evals in evals.items():
        assert all({"accepted", "cost", "values"} <= e.keys()
                   for e in stage_evals)
        first, rest = stage_evals[0], stage_evals[1:]
        assert first["accepted"] and "step_norm" not in first
        assert all("step_norm" in e and e["step_norm"] >= 0.0 for e in rest)
        accepted = [e["cost"] for e in stage_evals if e["accepted"]]
        assert accepted == sorted(accepted, reverse=True), \
            f"{stage}: an accepted cost went back up"
        paths = free_paths[stage]
        assert paths, "a stage with nothing free emits no evals to align"
        assert all(len(e["values"]) == len(paths) for e in stage_evals)
        assert all(np.isfinite(v) for e in stage_evals for v in e["values"])


def test_events_callback_no_file(synthetic_pattern):
    structure, ins = perturbed_models()
    seen = []
    ref = rx.Refinement(structure, ins, history=False)
    ref.fit(synthetic_pattern, events=seen.append)
    assert any(e["kind"] == "eval" for e in seen)
    assert seen[-1]["kind"] == "fit_end"
    assert seen[-1]["data"]["rwp"] < 0.2


def test_event_stream_hot_loop_is_plain_json(tmp_path):
    stream = EventStream(path=tmp_path / "e.jsonl")
    stream.emit("eval", stage="s", n_eval=1, cost=1.5)
    stream.close()
    line = (tmp_path / "e.jsonl").read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["record"] == "event"
    assert parsed["data"] == {"stage": "s", "n_eval": 1, "cost": 1.5}


# ----------------------------------------------------------------------
# plotly HTML viewer
# ----------------------------------------------------------------------
def test_write_html_self_contained(tmp_path, synthetic_pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)

    out = tmp_path / "fit.html"
    from rietx.viz import write_html
    write_html(result, str(out))
    html = out.read_text(encoding="utf-8")
    assert "plotly" in html.lower()
    assert "scattergl" in html.lower()
    # self-contained: no external <script src=…> tag (the embedded plotly
    # bundle *mentions* URLs inside its own JS string constants — harmless)
    import re
    assert not re.search(r"<script[^>]+src=", html)
    assert out.stat().st_size > 1_000_000       # plotly.js embedded
    # the raw difference is the default here as it is in the matplotlib panel:
    # both are a file someone takes away and reads as a figure
    assert "difference" in html
    # Δ/σ stays available (the trace name survives either ensure_ascii choice
    # in plotly's JSON serialization)
    write_html(result, str(tmp_path / "fit_weighted.html"), weighted=True,
               include_plotlyjs="cdn")
    weighted_html = (tmp_path / "fit_weighted.html").read_text(encoding="utf-8")
    assert ("Δ/σ" in weighted_html) or ("\\u0394" in weighted_html)


def test_figure_from_arrays_weighted_and_raw():
    from rietx.viz.html import figure_from_arrays

    tt = np.linspace(10, 60, 500)
    y_calc = 100 + 50 * np.exp(-((tt - 30) ** 2) / 0.05)
    rng = np.random.default_rng(0)
    y_obs = y_calc + rng.normal(0, 5, tt.size)
    sigma = np.full_like(tt, 5.0)
    ticks = {"phase 0": [30.0, 45.0]}

    weighted = figure_from_arrays(tt, y_obs, y_calc, None, ticks, sigma=sigma)
    names = [t.name for t in weighted.data]
    assert "Δ/σ" in names and "difference" not in names
    dsig = weighted.data[names.index("Δ/σ")]
    assert dsig.yaxis == "y2", "Δ/σ must live on its own axis, not intensity"
    assert max(abs(v) for v in dsig.y) < 10     # statistical scale, not counts
    assert len(weighted.layout.shapes) == 1     # the ±3σ band
    # the rows follow the residual into the lower panel: the reading order is
    # data, residual, index — the residual is read against the peaks that
    # caused it, so nothing comes between them
    row = weighted.data[names.index("hkl: phase 0")]
    assert row.yaxis == "y2"
    assert max(row.y) < min(dsig.y), "tick rows must sit below the Δ/σ trace"

    raw = figure_from_arrays(tt, y_obs, y_calc, None, ticks)
    names = [t.name for t in raw.data]
    assert "difference" in names and "Δ/σ" not in names
    assert all(t.yaxis in (None, "y") for t in raw.data)
    assert (max(raw.data[names.index("hkl: phase 0")].y)
            < min(raw.data[names.index("difference")].y))


def test_plot_result_default_is_one_panel_with_the_raw_difference(
        synthetic_pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)

    OUT.mkdir(exist_ok=True)
    fig = result.plot(path=str(OUT / "viz_raw_default.png"))
    axes = fig.get_axes()
    assert len(axes) == 1, "the raw difference shares the intensity axis"
    # the caption is the title: fit statistics ride as a corner annotation, so
    # a panel pasted into a report does not arrive carrying a second one
    assert axes[0].get_title() == ""
    assert axes[0].get_legend() is None
    assert any("Rwp" in t.get_text() or "R_" in t.get_text()
               for t in axes[0].texts)

    fig_w = result.plot(path=str(OUT / "viz_weighted_optin.png"), weighted=True)
    assert len(fig_w.get_axes()) == 2
    assert fig_w.get_axes()[1].get_ylabel() == r"$\Delta/\sigma$"

    # every gutter label lands inside the axes it labels, tick rows or not.
    # Without rows there is almost nothing below the data floor, and the curve
    # labels — which converge there on any pattern that ends in background —
    # spread straight out of the bottom of the panel.  Nothing in matplotlib
    # warns about that; only looking at it, or this, catches it.
    bare = result.model_copy(deep=True)
    bare.ticks = {}
    for kw in ({}, {"weighted": True}, {"label_align": "curve"}):
        stem = "_".join(["viz_no_ticks", *(f"{k}-{v}" for k, v in kw.items())])
        ax = bare.plot(path=str(OUT / f"{stem}.png"), **kw).get_axes()[0]
        lo, hi = ax.get_ylim()
        assert all(lo <= t.get_position()[1] <= hi for t in ax.texts), kw


def test_the_residual_sits_between_the_data_and_the_tick_rows(
        synthetic_pattern):
    """Reading order down the figure: data, residual, index — in both layouts.

    Before this the weighted panel drew the rows on the *intensity* axes, which
    put the index between the peaks and the residual they explain.  The two
    layouts reach it differently — one axes with everything offset below the
    floor, or the rows following the residual into the lower panel — so both
    are asserted, and asserting only the drawn y values would pass on either
    while the rows sat in the wrong axes.
    """
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    OUT.mkdir(exist_ok=True)

    from rietx.viz.plots import PALETTES
    grey = PALETTES["light"]["diff"]
    n = len(result.ticks)

    inline = result.plot(path=str(OUT / "viz_order_inline.png")).get_axes()[0]
    rows = inline.get_lines()[-n:]              # rows are drawn last
    diff_line = next(ln for ln in inline.get_lines() if ln.get_color() == grey)
    assert max(max(r.get_ydata()) for r in rows) < min(diff_line.get_ydata())

    panel = result.plot(path=str(OUT / "viz_order_panel.png"),
                        weighted=True).get_axes()
    assert len(panel[0].get_lines()) <= 3, "rows left on the intensity axes"
    assert len(panel[1].get_lines()) == 1 + n
    rows = panel[1].get_lines()[-n:]
    assert max(max(r.get_ydata()) for r in rows) < min(panel[1].get_lines()[0].get_ydata())


def test_nonlinear_intensity_moves_the_difference_to_its_own_panel(
        synthetic_pattern):
    """A raw difference is negative by construction; a log axis cannot draw it.

    So `y_scale` other than linear forces the panel layout — on a *linear*
    axis, in the intensity's own units, which is a move and not a rescale.  The
    layout arithmetic is done in the axis's transformed space, and the check
    that it was is the headroom: on a log axis a fraction of the *data* range
    would put the ceiling orders of magnitude above the tallest peak.
    """
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    OUT.mkdir(exist_ok=True)
    top = float(np.max(result.y_obs))

    def headroom(ax):
        """Share of the panel's *height* left above the tallest point."""
        y_top = ax.transData.transform((ax.get_xlim()[0], top))[1]
        floor_px = ax.transAxes.transform((0.0, 0.0))[1]
        ceil_px = ax.transAxes.transform((0.0, 1.0))[1]
        return (ceil_px - y_top) / (ceil_px - floor_px)

    for scale in ("linear", "log", "sqrt", "asinh"):
        fig = result.plot(path=str(OUT / f"viz_yscale_{scale}.png"),
                          y_scale=scale, weighted=scale == "linear")
        axes = fig.get_axes()
        assert len(axes) == 2, scale
        assert axes[0].get_yscale() == ("log" if scale == "log" else
                                        "function" if scale == "sqrt" else
                                        "linear" if scale == "linear" else scale)
        assert axes[1].get_yscale() == "linear", scale
        assert axes[1].get_ylabel() == ("obs $-$ calc" if scale != "linear"
                                        else r"$\Delta/\sigma$"), scale
        # the headroom is one fixed share of the panel's *height* on every
        # scale — which is what "the layout is arithmetic in display distance"
        # means, and what a fraction of the data range would not give
        assert headroom(axes[0]) == pytest.approx(1 / 6, abs=0.01), scale
        # and the spine still stops at the data, not at the ceiling
        assert axes[0].spines["left"].get_bounds()[1] == pytest.approx(top)

    with pytest.raises(ValueError, match="y_scale must be one of"):
        result.plot(y_scale="logit")

    # a pattern living inside one decade has no decade to label, and asking a
    # log axis for the decades *inside its range* then returns none at all —
    # an axis with no numbers on it, which nothing else here would notice
    flat = result.model_copy(deep=True)
    flat.y_obs = list(np.clip(np.asarray(result.y_obs), 300.0, 900.0))
    ax = flat.plot(path=str(OUT / "viz_yscale_log_sub_decade.png"),
                   y_scale="log").get_axes()[0]
    assert len(ax.get_yticks()) >= 3


def test_q_and_d_axes_are_the_same_pattern_in_another_coordinate(
        synthetic_pattern):
    """Q and d are derived through λ, so both demand it and neither states it.

    A *d* axis is drawn ascending — the pattern mirrored rather than the axis
    counting down — and the reflection rows have to make the same trip, which
    is the half a transform on the curves alone would silently get wrong.
    """
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    lam = ins.source.lines[0].wavelength.value
    OUT.mkdir(exist_ok=True)

    tt = np.asarray(result.two_theta)
    sin_theta = np.sin(np.radians(tt) / 2.0)

    q = result.plot(path=str(OUT / "viz_axis_q.png"), x_axis="q",
                    wavelength=lam).get_axes()[0]
    assert "$Q$" in q.get_xlabel() and "lambda" not in q.get_xlabel()
    assert q.get_xlim()[1] == pytest.approx(4 * np.pi * sin_theta.max() / lam)

    d = result.plot(path=str(OUT / "viz_axis_d.png"), x_axis="d",
                    wavelength=lam).get_axes()[0]
    lo, hi = d.get_xlim()
    assert lo < hi, "a d axis is drawn ascending, never reversed"
    assert hi == pytest.approx(lam / (2 * sin_theta.min()))
    row = d.get_lines()[-1]
    assert lo <= min(row.get_xdata()) and max(row.get_xdata()) <= hi

    with pytest.raises(ValueError, match="wavelength"):
        result.plot(x_axis="q")
    with pytest.raises(ValueError, match="x_axis must be one of"):
        result.plot(x_axis="tof", wavelength=lam)


def test_curve_names_are_a_block_bottom_aligned_with_their_data(
        synthetic_pattern):
    """One block, one line of type apart, anchored at the foot of the data.

    Levelling each name with where its own curve ends is the prettier rule and
    the fragile one: observed, calculated and background all converge on the
    background at the right-hand end of most patterns, so their natural heights
    collide and the resolved order is whichever curve happened to end higher —
    it shuffles between datasets and reads as meaning something.  The block is
    fixed, in series order, and cannot collide with the residual's own label.
    """
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    OUT.mkdir(exist_ok=True)

    ax = result.plot(path=str(OUT / "viz_labels_block.png")).get_axes()[0]
    named = {t.get_text(): t.get_position()[1] for t in ax.texts}
    block = [named["observed"], named["calculated"]]
    if "background" in named:
        block.append(named["background"])
    assert block == sorted(block, reverse=True), "series order, top to bottom"
    gaps = [a - b for a, b in zip(block[:-1], block[1:], strict=True)]
    assert max(gaps) - min(gaps) < 1e-9, "one line of type, evenly"
    assert block[-1] - named["obs $-$ calc"] >= gaps[0] - 1e-9

    with pytest.raises(ValueError, match="label_align must be"):
        result.plot(label_align="middle")


def test_a_zoom_is_a_figure_of_its_own_data(synthetic_pattern):
    """`two_theta_range` is a window on the pattern, not a crop of the figure.

    Before the panel took the house conventions the y axis autoscaled over the
    *whole* pattern whatever the window was, so zooming into a weak region drew
    it as a flat line under the full pattern's tallest peak.  Everything the
    layout is built from — the intensity scale, the residual offset, the tick
    rows — now comes from what the window contains.
    """
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)

    tt = np.asarray(result.two_theta)
    y = np.asarray(result.y_obs)
    peak = float(tt[int(np.argmax(y))])
    # a window that excludes the tallest peak, on whichever side has room
    lo, hi = ((tt[0], peak - 1.0) if peak - tt[0] > tt[-1] - peak
              else (peak + 1.0, tt[-1]))
    window = (y[(tt >= lo) & (tt <= hi)]).max()

    OUT.mkdir(exist_ok=True)
    zoom = result.plot(path=str(OUT / "viz_zoom_window.png"),
                       two_theta_range=(float(lo), float(hi)))
    assert zoom.get_axes()[0].get_ylim()[1] < float(y.max())
    # the spine spans the window's own data, so no peak escapes the axis and
    # none of the axis is empty above it
    assert zoom.get_axes()[0].spines["left"].get_bounds()[1] == pytest.approx(window)


def test_one_phase_tick_row_is_neutral_and_two_are_not(synthetic_pattern):
    """Colour is for telling rows apart, and one row has nothing to tell apart.

    The failure this pins is a renderer that reaches into a phase palette by
    row index: a single-phase pattern then gets a coloured row that means
    nothing, and the reader spends attention learning a code with one entry.
    """
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    assert len(result.ticks) == 1

    from rietx.viz.plots import PALETTES

    OUT.mkdir(exist_ok=True)
    one = result.plot(path=str(OUT / "viz_ticks_one_phase.png"), weighted=False)
    # the tick row is the last thing drawn on the intensity axes
    assert one.get_axes()[0].get_lines()[-1].get_markerfacecolor() == \
        PALETTES["light"]["tick"]

    two = result.model_copy(deep=True)
    name, positions = next(iter(result.ticks.items()))
    two.ticks = {name: positions, "impurity": [p + 0.3 for p in positions]}
    fig = two.plot(path=str(OUT / "viz_ticks_two_phases.png"), weighted=False)
    rows = fig.get_axes()[0].get_lines()[-2:]
    assert [r.get_markerfacecolor() for r in rows] == PALETTES["light"]["phase"][:2]


def test_plot_style_dark_flips_the_ground_and_leaves_light_alone(synthetic_pattern):
    """`style="dark"` exists because the residual, the background line and the
    zero rule are chosen *per ground* (WP-1068, for the manual's dark-mode
    figures): subordinate means darker than the text on a white page and dimmer
    than it on a black one, so a plain `dark_background` context around the call
    would flip the axes and leave all three at their light-ground hues.  What
    matters is that the ground flips and the series colours change with it."""
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)

    OUT.mkdir(exist_ok=True)
    light = result.plot(path=str(OUT / "viz_style_light.png"), weighted=True)
    dark = result.plot(path=str(OUT / "viz_style_dark.png"), style="dark",
                       weighted=True)

    assert light.get_facecolor()[:3] == (1.0, 1.0, 1.0)
    assert sum(dark.get_facecolor()[:3]) < 0.3, "dark style did not darken the figure"
    # the difference curve is the one the plain style context would have lost
    light_diff = light.get_axes()[1].get_lines()[0].get_color()
    dark_diff = dark.get_axes()[1].get_lines()[0].get_color()
    assert light_diff == "#737373" and dark_diff != light_diff

    with pytest.raises(ValueError, match="style must be one of"):
        result.plot(style="solarized")


def test_minmax_decimation_keeps_peaks():
    from rietx.viz.html import _minmax_decimate
    tt = np.linspace(0, 100, 50_001)
    y = np.zeros_like(tt)
    y[25_000] = 1e6                             # a single sharp spike
    tt_d, (y_d,) = _minmax_decimate(tt, [y], max_points=2_000)
    assert len(tt_d) <= 2_100
    assert y_d.max() == 1e6, "decimation dropped the peak top"


# ----------------------------------------------------------------------
# live session + watch server
# ----------------------------------------------------------------------
def test_live_session_and_watch_server(tmp_path, synthetic_pattern):
    from rietx.viz.live import LiveSession
    from rietx.watch import serve

    structure, ins = perturbed_models()
    live = tmp_path / "live"
    ref = rx.Refinement(structure, ins, history=False)
    ref.fit(synthetic_pattern, events=LiveSession(live))

    assert (live / "fit.html").exists()
    assert (live / "events.jsonl").exists()
    status = json.loads((live / "status.json").read_text(encoding="utf-8"))
    assert status["stage"] == "profile"          # last stage of the plan
    assert status["rwp"] < 0.2

    server = serve(live, port=0, block=False)    # port 0 → ephemeral
    try:
        port = server.server_address[1]
        index = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/", timeout=5).read().decode()
        assert "rietx watch" in index and "events.jsonl" in index
        page = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/fit.html", timeout=5).read()
        assert b"plotly" in page.lower()
        tail = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/events.jsonl", timeout=5).read()
        assert b'"fit_end"' in tail
    finally:
        server.shutdown()
        server.server_close()


def test_cli_help_and_html(tmp_path, synthetic_pattern):
    from rietx.cli import main
    assert main(["--help"]) == 0

    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    src = tmp_path / "result.json"
    src.write_text(result.model_dump_json(), encoding="utf-8")
    out = tmp_path / "out.html"
    assert main(["html", str(src), str(out)]) == 0
    assert out.exists() and out.stat().st_size > 1_000_000


# ----------------------------------------------------------------------
# history: merge + cherry-pick
# ----------------------------------------------------------------------
def test_merge_combines_disjoint_branches(synthetic_pattern):
    """Branch A refines zero only, branch B refines the cell only; the merge
    must carry BOTH refined values and record two parents."""
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    ref.fit(synthetic_pattern, plan=rx.RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"])]))
    base_id = ref.result_.node_id

    # branch A: zero only
    a = ref.branch(base_id)
    a.run_stage(synthetic_pattern, Stage("zero", ["instrument.zero_shift"]))
    zero_a = a.fitted_instrument.zero_shift.value
    a_id = a.result_.node_id

    # branch B: cell only
    b = ref.branch(base_id)
    b.run_stage(synthetic_pattern, Stage("cell", ["phases.*.cell.*"]))
    cell_b = b.fitted_structure.phases[0].cell.a.value
    b_id = b.result_.node_id
    assert b.fitted_instrument.zero_shift.value != pytest.approx(zero_a)

    merge_id = b.merge(a_id, prefer="ours")
    assert b.fitted_instrument.zero_shift.value == pytest.approx(zero_a)
    assert b.fitted_structure.phases[0].cell.a.value == pytest.approx(cell_b)

    node = ref.history[merge_id]
    assert node.action.kind == "merge"
    assert set(node.parents) == {a_id, b_id}
    assert ref.history.common_ancestor(a_id, b_id) == base_id

    # a merged state is a state like any other: it must refine onward
    result = b.run_stage(synthetic_pattern,
                         Stage("both", ["instrument.zero_shift", "phases.*.cell.*"]))
    assert result.status == "converged"


def test_merge_conflict_takes_preferred_side(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    ref.fit(synthetic_pattern, plan=rx.RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"])]))
    base_id = ref.result_.node_id

    a = ref.branch(base_id)
    a.run_stage(synthetic_pattern, Stage("zero", ["instrument.zero_shift"]),
                two_theta_limits=(4.0, 20.0))
    zero_a = a.fitted_instrument.zero_shift.value

    b = ref.branch(base_id)
    b.run_stage(synthetic_pattern, Stage("zero", ["instrument.zero_shift"]))
    zero_b = b.fitted_instrument.zero_shift.value
    assert zero_a != pytest.approx(zero_b, abs=0.0)

    b.merge(a.result_.node_id, prefer="theirs")
    assert b.fitted_instrument.zero_shift.value == pytest.approx(zero_a)


def test_cherry_pick_replays_a_stage_action(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    ref.fit(synthetic_pattern, plan=rx.RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("zero", ["instrument.zero_shift"]),
    ]))
    zero_node = ref.result_.node_id             # last stage = zero
    root_children = ref.history.children(ref.history.root.id)
    base_id = root_children[0].id               # after scale_bkg

    other = ref.branch(base_id)
    before = other.fitted_instrument.zero_shift.value
    result = other.cherry_pick(zero_node, synthetic_pattern)
    assert result.status == "converged"
    assert other.fitted_instrument.zero_shift.value != pytest.approx(before)
    picked = ref.history[result.node_id]
    assert picked.action.kind == "stage"
    assert picked.action.turn_on == ["instrument.zero_shift"]
    assert picked.parents == [base_id]

    with pytest.raises(ValueError, match="stage"):
        other.cherry_pick(ref.history.root.id, synthetic_pattern)
