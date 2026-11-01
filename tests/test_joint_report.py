"""What a joint fit reports about itself (WP-1341, issue #252).

A joint refinement used to converge and leave nothing to inspect: no event
log, no convergence figure, no report.  These tests hold each piece the WP
added.  The fixture is test_multi_histogram's synthetic LaB6 pair at two
wavelengths, so no number here is a claim about a specimen.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from rietx import MultiHistogramRefinement, Refinement, Stage, runs
from rietx.history.events import as_event_stream, read_events
from rietx.optimize.cancel import CancelToken, RefinementCancelled
from rietx.optimize.statistics import MAX_SHIFT_CONVERGED
from rietx.params.multi import SharingMap
from rietx.refine import FROZEN_COMPILE_CHI2_REL
from rietx.strategy.staged import RefinementPlan
from tests.test_multi_histogram import (
    _broadened,
    _width_plan,
    _width_start,
    perturbed_inputs,
    synthesize,
)

OUT = Path(__file__).parent / "output"
LAMS = (0.41390, 0.71070)

# the module fixtures below are shared, so the module stays on one worker
# (tests/CLAUDE.md § Shared fixtures and xdist groups)
pytestmark = pytest.mark.xdist_group("joint-report")

TURN_ON = ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
           "instrument.zero_shift"]


@pytest.fixture(scope="module")
def two_patterns():
    return [
        synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]


def _plot(result, stem: str) -> None:
    OUT.mkdir(exist_ok=True)
    for h in range(len(result.histograms)):
        result.for_histogram(h).plot(OUT / f"{stem}_h{h}.png")


# ---------------------------------------------------- the convergence figure --
@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_a_joint_fit_measures_how_far_it_was_still_moving(two_patterns, solver):
    """McCusker §7's quantity on both branches, now on the joint θ.

    Measured 2026-10-12 on this fixture: converged 5e-7 to 2.2e-3 across both
    drivers, unit and 1:4 weights; starved to one iteration, 4.0 (LM) and 17.9
    (TRF).  Both sides clear the 0.1 band by 40× or more, so neither assertion
    senses where a solver happened to stop.
    """
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, solver=solver)
    done = ref.fit(two_patterns, plan="mccusker_default", weights=[1.0, 4.0])
    assert done.status == "converged"
    shift = done.statistics.max_shift_over_esd
    assert shift is not None and shift < MAX_SHIFT_CONVERGED
    _plot(done, f"joint_report_shift_{solver}")

    # whole-fit: the per-histogram statistics have no writer for it, and the
    # view that keeps the joint stages carries the joint figure beside them
    for h, hist in enumerate(done.histograms):
        assert hist.statistics.max_shift_over_esd is None
        assert done.for_histogram(h).statistics.max_shift_over_esd == shift
    assert f"max|Δθ|/esd={shift:.3f}" in str(done)

    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, solver=solver)
    starved = ref.fit(two_patterns, plan=RefinementPlan(
        stages=[Stage("starved", turn_on=TURN_ON, max_iter=1)]))
    assert starved.status == "max_iter"
    assert starved.statistics.max_shift_over_esd > MAX_SHIFT_CONVERGED


# ------------------------------------------------------------- the event log --
def test_a_joint_event_log_partitions_by_histogram(two_patterns, tmp_path):
    """Issue #252's first ask: an event log a reader can split by histogram.

    The joint solve is one solve, so each kind is emitted once per fit, stage
    or evaluation, and a per-histogram fact rides in a ``histograms`` row
    stamped with its ``histogram_index``.
    """
    progress = io.StringIO()
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(two_patterns, plan="mccusker_default",
                     events=tmp_path / "joint.jsonl", progress=progress)
    _plot(result, "joint_report_events")
    log = [(e.kind, e.data) for e in read_events(tmp_path / "joint.jsonl")]
    kinds = [k for k, _ in log]
    n_stages = len(result.stages)
    assert kinds[0] == "fit_start" and kinds[-1] == "fit_end"
    assert kinds.count("stage_start") == kinds.count("stage_end") == n_stages
    assert kinds.count("eval") > n_stages

    by_hist: dict[int, list[dict]] = {0: [], 1: []}
    for kind, data in log:
        if kind == "eval":
            continue
        assert data["n_histograms"] == 2, kind
        rows = data["histograms"]
        assert [r["histogram_index"] for r in rows] == [0, 1], kind
        if kind == "stage_end":
            for r in rows:
                by_hist[r["histogram_index"]].append(r)
    for h, rows in by_hist.items():
        assert len(rows) == n_stages
        # the last stage's reading is the as-optimised one, on that stage's
        # compile; the result's is a compile at the answer (WP-1421), so the
        # two differ by the frozen windows alone, under FROZEN_COMPILE_STALE's 1 %
        assert rows[-1]["rwp"] == pytest.approx(
            result.histograms[h].statistics.rwp, rel=FROZEN_COMPILE_CHI2_REL / 2)

    start = log[0][1]
    assert start["n_points"] == sum(r["n_points"] for r in start["histograms"])
    ends = [d for k, d in log if k == "stage_end"]
    assert log[-1][1]["rwp"] == result.statistics.rwp
    assert ends[-1]["rwp"] == pytest.approx(result.statistics.rwp,
                                            rel=FROZEN_COMPILE_CHI2_REL / 2)
    assert "FROZEN_COMPILE_STALE" not in {d.code for d in result.diagnostics}

    # an eval's values align with the most recent stage_start's free paths,
    # and those split by histogram on their ``hist.<h>.`` scope
    free, last = None, None
    for kind, data in log:
        if kind == "stage_start":
            free = data["free_paths"]
        elif kind == "eval":
            assert len(data["values"]) == len(free)
            last = data
    owned = {h: [p for p in free if p.startswith(f"hist.{h}.")] for h in (0, 1)}
    assert "hist.0.instrument.zero_shift" in owned[0]
    assert "hist.1.instrument.zero_shift" in owned[1]
    assert "phases.0.cell.a" in free            # shared, so bare
    values = dict(zip(free, last["values"], strict=True))
    assert values["phases.0.cell.a"] == pytest.approx(
        result.parameter("phases.0.cell.a").value, rel=1e-6)

    # ``progress=`` reads the same stream: one line per stage
    assert len(progress.getvalue().splitlines()) == n_stages


def test_a_monitoring_hook_that_raises_is_the_callers_to_see(two_patterns):
    """``history/events.py``'s rule: a callback's exception propagates."""
    def hook(event):
        if event["kind"] == "stage_end":
            raise RuntimeError("the caller's own bug")

    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    with pytest.raises(RuntimeError, match="the caller's own bug"):
        ref.fit(two_patterns, plan="mccusker_default", events=hook)


def test_a_raised_joint_fit_closes_the_stream_it_built(two_patterns, tmp_path,
                                                       monkeypatch):
    """A stream built from a path is the fit's to close, on every exit."""
    import rietx.multi as multi_mod

    built = []

    def capture(events):
        stream = as_event_stream(events)
        built.append(stream)
        return stream

    def fail(*_args, **_kw):
        raise RuntimeError("after the last stage")

    monkeypatch.setattr(multi_mod, "as_event_stream", capture)
    monkeypatch.setattr(MultiHistogramRefinement, "_build_result", fail)
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    with pytest.raises(RuntimeError, match="after the last stage"):
        ref.fit(two_patterns, plan=RefinementPlan(stages=[
            Stage("scale+bkg", ["phases.*.scale", "instrument.background.*"])]),
            events=tmp_path / "joint.jsonl")
    (stream,) = built
    assert stream._fh is None


def test_a_cancelled_joint_stage_is_abandoned(two_patterns):
    """The cooperative cancel, one rank out: the stage in flight leaves no
    trace, and the working state is the last completed stage's."""
    # one tolerance for every stage, so the two-stage prefix below solves its
    # stages exactly as the three-stage plan does (WP-1123's schedule would
    # run "zero" at 1e-6 here and at 1e-9 there)
    plan = RefinementPlan(stages=[
        Stage("scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage("zero", turn_on=["instrument.zero_shift"]),
        Stage("cell", turn_on=["phases.*.cell.*"]),
    ], intermediate_ftol=None)
    token = CancelToken()
    log: list[dict] = []

    def hook(event):
        log.append(event)
        data = event["data"]
        if event["kind"] == "eval" and data["stage"] == "cell" and data["n_eval"] == 3:
            token.cancel()

    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    with pytest.raises(RefinementCancelled) as info:
        ref.fit(two_patterns, plan=plan, events=hook, cancel=token)
    exc = info.value
    assert exc.stage == "cell"
    assert [s.name for s in exc.completed_stages] == ["scale+bkg", "zero"]
    assert exc.node_id is None
    assert ref.result_ is None
    tail = [(e["kind"], e["data"].get("status")) for e in log[-2:]]
    assert tail == [("stage_end", "cancelled"), ("fit_end", "cancelled")]

    # the same two stages run to completion land exactly where the cancel left
    structure, instruments = perturbed_inputs()
    done = MultiHistogramRefinement(structure, instruments)
    # the declared stages' working state; the closing stage is tests/test_closing_stage.py's
    done.fit(two_patterns, plan=RefinementPlan(stages=plan.stages[:2],
                                               intermediate_ftol=None,
                                               closing_window_tol=None))
    for h in (0, 1):
        assert (ref.fitted_structures[h].model_dump()
                == done.fitted_structures[h].model_dump())
        assert (ref.fitted_instruments[h].model_dump()
                == done.fitted_instruments[h].model_dump())


def test_a_recorded_joint_fit_is_one_run(two_patterns, tmp_path):
    """Every fit records itself, and a joint fit is one job (WP-1403)."""
    was = runs.set_enabled(True)
    try:
        structure, instruments = perturbed_inputs()
        ref = MultiHistogramRefinement(structure, instruments)
        result = ref.fit(two_patterns, plan="mccusker_default",
                         telemetry=tmp_path, label="joint LaB6")
    finally:
        runs.set_enabled(was)
    (run,) = runs.discover(tmp_path)
    assert run.status is not None and run.status.state == "done"
    assert run.status.rwp == pytest.approx(result.statistics.rwp)
    assert run.meta is not None and run.meta.label == "joint LaB6"
    summary = (run.path / runs.SUMMARY_FILE).read_text(encoding="utf-8")
    assert summary == str(result)
    # the live view draws one pattern, so a joint run writes no picture
    assert not (run.path / runs.SNAPSHOT_FILE).exists()


# ---------------------------------------------------------------- the report --
def test_each_histogram_gets_its_own_report(two_patterns):
    """Layers 0-2 per histogram, off that histogram's model and curves."""
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    with pytest.raises(RuntimeError, match="fit"):
        ref.report(0)
    result = ref.fit(two_patterns, plan="mccusker_default")
    _plot(result, "joint_report_layers")
    with pytest.raises(IndexError):
        ref.report(2)
    for h in (0, 1):
        report = ref.report(h, plan="mccusker_default")
        assert report.layer1_available
        assert report.unmatched == []       # one phase, every peak ticked
        assert report.rwp == result.histograms[h].statistics.rwp
        # the background section reads this histogram's own screen, which
        # the joint result carries ``hist.<h>.``-scoped
        mine = {k.split(".", 2)[2]: v for k, v in
                result.identifiability.background_absorption.items()
                if k.startswith(f"hist.{h}.")}
        assert mine
        assert (result.for_histogram(h).identifiability.background_absorption
                == mine)
        assert report.background.worst_absorption == max(mine.values())


def test_a_cancelled_second_fit_leaves_the_first_report_alone(two_patterns):
    """The report reads what its own fit left, never the working table.

    A cancelled fit puts the table back where its stage found it and keeps
    the previous result, so a report reading the live table paired the
    second fit's values with the first fit's models.
    """
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    ref.fit(two_patterns, plan="mccusker_default")
    before = ref.report(0).model_dump()

    token = CancelToken()

    def hook(event):
        data = event["data"]
        if event["kind"] == "stage_start" and data["stage"] == "zero":
            token.cancel()       # read at the second stage's first evaluation

    with pytest.raises(RefinementCancelled):
        ref.fit(two_patterns, plan="mccusker_default", weights=[1.0, 4.0],
                events=hook, cancel=token)
    assert ref.report(0).model_dump() == before


def test_a_view_spells_its_own_rows_as_a_single_fit_does(two_patterns):
    """A per-histogram structural row reaches the report under its bare name.

    ``build_report`` looks parameters up by bare path (the moment arm's esds,
    Layer 2's freed-parameter rows), so a view carrying ``hist.1.…`` missed
    them, and carried histogram 0's rows beside its own.
    """
    biso = "phases.0.atoms.0.biso"
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(
        structure, instruments,
        sharing=SharingMap(per_histogram=["phases.*.atoms.*.biso"]))
    result = ref.fit(two_patterns, plan=RefinementPlan(stages=[
        Stage("scale+bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("zero", ["instrument.zero_shift"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("width", ["instrument.profile.w"]),
        Stage("b", [biso])]))
    assert result.status == "converged"
    assert all(hr.statistics.rwp < 0.12 for hr in result.histograms)
    _plot(result, "joint_report_view_rows")
    rows = {p.path: p for p in result.parameters}
    assert {f"hist.0.{biso}", f"hist.1.{biso}"} <= set(rows)
    for h in (0, 1):
        view = {p.path: p for p in result.for_histogram(h).parameters}
        assert view[biso] == rows[f"hist.{h}.{biso}"].model_copy(
            update={"path": biso})
        assert not [p for p in view if p.startswith("hist.")]
        assert "phases.0.cell.b" in view          # a shared (tied) row stays bare
    # a negative index counts from the end, and past either end is refused
    assert result.for_histogram(-1).parameters == result.for_histogram(1).parameters
    for bad in (2, -3):
        with pytest.raises(IndexError):
            result.for_histogram(bad)


@pytest.fixture(scope="module")
def size_patterns():
    """test_multi_histogram's WP-1131 pair: one 400 Å specimen, two λ."""
    return [_broadened("lor_size", LAMS[0], 3.0, 24.0, seed=1)[0],
            _broadened("lor_size", LAMS[1], 5.0, 42.0, seed=2)[0]]


def _size(block) -> float:
    (term,) = [t for t in block.terms if t.path.endswith("lor_size")]
    return term.value


def test_the_specimen_size_is_reported_once(size_patterns):
    """One specimen, one size: the same block in every histogram's report.

    Measured 2026-10-12: the joint fit reads 408.82(4.86) Å; the two solo
    arms read 408.71(8.05) and 409.20(6.43) Å.  The joint block is read off
    the shared column at histogram 0's λ, so both reports quote its
    coefficient, never histogram 1's λ-scaled copy.
    """
    structure, _ = _width_start(LAMS[0])
    instruments = [_width_start(lam)[1] for lam in LAMS]
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(size_patterns, plan=_width_plan("lor_size"))
    _plot(result, "joint_report_size")
    joint = result.microstructure[0]
    reports = [ref.report(h) for h in (0, 1)]
    for report in reports:
        (block,) = report.microstructure
        assert [t.coefficient for t in block.terms] == [
            t.coefficient for t in joint.terms]
        assert _size(block) == _size(joint)

    for h, (pattern, lam) in enumerate(zip(size_patterns, LAMS, strict=True)):
        s, ins = _width_start(lam)
        solo = Refinement(s, ins, history=False).fit(
            pattern, plan=_width_plan("lor_size"))
        solo.plot(OUT / f"joint_report_size_solo_h{h}.png")
        assert _size(joint) == pytest.approx(_size(solo.microstructure[0]),
                                             rel=0.005)


# ------------------------------------------- STAGE_PATH_NOT_FREE, jointly --
def _codes(result, code):
    return [d for d in result.diagnostics if d.code == code]


def _one_stage(patterns, turn_on, *, sharing=None):
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, sharing=sharing)
    return ref.fit(patterns, plan=RefinementPlan(stages=[
        Stage("only", ["phases.*.scale", *turn_on], max_iter=5)]))


@pytest.mark.parametrize("path, says", [
    # test_params_surface's four, on the same LaB6: B on 6f, La on 1a
    ("phases.0.atoms.1.x", "follows phases.0.atoms.1.dof.0"),
    ("phases.0.atoms.1.y", "is fixed by symmetry or by the model"),
    ("phases.0.atoms.0.z", "is fixed by symmetry or by the model"),
    ("phases.0.cell.b", "follows phases.0.cell.a"),
])
def test_a_joint_plan_naming_a_fixed_literal_says_so(two_patterns, path, says):
    """Issue #803: one finding per path, naming its stage and its histograms.

    The rows are shared, so both tables hold them fixed and the finding is
    one.  ``STAGE_FREED_NOTHING`` stays silent: the literal matched a row in
    both histograms, which is that check's "reached".
    """
    result = _one_stage(two_patterns, [path])
    assert path not in result.stages[0].freed
    (found,) = _codes(result, "STAGE_PATH_NOT_FREE")
    assert found.level == "warning" and found.where == [path]
    assert found.message == (f"Stage 'only' asked for {path}, which {says}, so "
                             "nothing was freed for it in every histogram.")
    if path == "phases.0.cell.b":
        assert found.suggestion.startswith("Free phases.0.cell.a instead")
    assert not _codes(result, "STAGE_PATH_UNKNOWN")
    assert not _codes(result, "STAGE_FREED_NOTHING")


@pytest.mark.parametrize("turn_on", [
    ["phases.0.atoms.1.dof.*"],
    ["phases.*.atoms.*.x"],
    ["instrument.geometry.sample_displacement"],
    ["phases.0.cell.a", "phases.0.cell.b"],
], ids=["dof-glob", "pattern", "instrument-literal", "tie-beside-source"])
def test_a_joint_plan_that_frees_what_it_names_stays_silent(two_patterns, turn_on):
    """#789's silence cases, jointly.  The fifth, a user's own tie, cannot
    arise: a joint fit has no tie verb."""
    result = _one_stage(two_patterns, turn_on)
    assert not _codes(result, "STAGE_PATH_NOT_FREE")


def test_a_per_histogram_row_is_reported_on_its_own_histogram(two_patterns):
    """A cell made per-histogram is one row per table.  A scoped literal
    addresses one of them, and a bare one both, as ``set_vary`` reads them."""
    sharing = SharingMap(per_histogram=["phases.0.cell.*"])
    scoped = _one_stage(two_patterns, ["hist.1.phases.0.cell.b"], sharing=sharing)
    (found,) = _codes(scoped, "STAGE_PATH_NOT_FREE")
    assert found.where == ["hist.1.phases.0.cell.b"]
    assert found.message.endswith("in histogram 1.")
    assert found.suggestion.startswith("Free hist.1.phases.0.cell.a instead")

    bare = _one_stage(two_patterns, ["phases.0.cell.b"], sharing=sharing)
    assert sorted(d.where[0] for d in _codes(bare, "STAGE_PATH_NOT_FREE")) == [
        "hist.0.phases.0.cell.b", "hist.1.phases.0.cell.b"]


# ------------------------------------------------------------ WP-2028 -----
# A joint fit's guards and findings read every histogram.  Each test below
# was run on main 12f459e5 first and failed there; the controls pass on both.

def _biso_fit(patterns, b0, b1, *, per_histogram=True):
    """A one-stage joint fit with La's B set to ``b0`` in histogram 0's start
    and ``b1`` in histogram 1's, per histogram unless ``per_histogram`` is
    off (then both must agree).  B is never freed, so the value the guard
    reads is the one set here."""
    structure, instruments = perturbed_inputs()
    other = structure.model_copy(deep=True)
    structure.phases[0].atoms[0].biso.value = b0
    other.phases[0].atoms[0].biso.value = b1
    sharing = (SharingMap(per_histogram=["phases.0.atoms.*.biso"])
               if per_histogram else None)
    ref = MultiHistogramRefinement([structure, other], instruments,
                                   sharing=sharing)
    return ref.fit(patterns, plan=RefinementPlan(stages=[
        Stage("only", ["phases.*.scale", "instrument.background.*"],
              max_iter=5)]))


@pytest.mark.parametrize("b0, b1, code, where", [
    # the WP's test: the bad value in histogram 1 alone
    (0.5, -0.5, "BISO_NEGATIVE", ["hist.1.phases.0.atoms.0.biso"]),
    (0.5, 60.0, "BISO_UNUSUALLY_LARGE", ["hist.1.phases.0.atoms.0.biso"]),
    # the positive arm: histogram 0 alone, which main already read
    (-0.5, 0.5, "BISO_NEGATIVE", ["hist.0.phases.0.atoms.0.biso"]),
    # both: one finding per path, so two here
    (-0.5, -0.4, "BISO_NEGATIVE", ["hist.0.phases.0.atoms.0.biso",
                                   "hist.1.phases.0.atoms.0.biso"]),
], ids=["negative-in-1", "large-in-1", "negative-in-0", "negative-in-both"])
def test_a_specimen_guard_fires_on_the_histogram_that_holds_the_value(
        two_patterns, b0, b1, code, where):
    result = _biso_fit(two_patterns, b0, b1)
    assert sorted(p for d in _codes(result, code) for p in d.where) == where
    for d in _codes(result, code):
        assert d.where[0] in d.message


def test_a_shared_biso_is_named_once_and_a_clean_pair_names_nothing(two_patterns):
    shared = _biso_fit(two_patterns, -0.5, -0.5, per_histogram=False)
    (found,) = _codes(shared, "BISO_NEGATIVE")
    assert found.where == ["phases.0.atoms.0.biso"]
    clean = _biso_fit(two_patterns, 0.5, 0.5)
    assert not _codes(clean, "BISO_NEGATIVE")
    assert not _codes(clean, "BISO_UNUSUALLY_LARGE")


def _shared_biso_two_cells(patterns, biso, cell1_scale):
    """A joint fit whose B is shared and whose cell is per histogram:
    histogram 1's cell is ``cell1_scale`` times histogram 0's along a, so its
    volume per atom, and with it the Lindemann bound, is larger."""
    structure, instruments = perturbed_inputs()
    other = structure.model_copy(deep=True)
    structure.phases[0].atoms[0].biso.value = biso
    other.phases[0].atoms[0].biso.value = biso
    other.phases[0].cell.a.value *= cell1_scale
    ref = MultiHistogramRefinement(
        [structure, other], instruments,
        sharing=SharingMap(per_histogram=["phases.0.cell.*"]))
    return ref.fit(patterns, plan=RefinementPlan(stages=[
        Stage("only", ["phases.*.scale", "instrument.background.*"],
              max_iter=5)]))


def test_a_shared_biso_is_tested_against_the_loosest_cell(two_patterns):
    """#1205 ruling: a B read against several cells fires only past the
    loosest bound, naming that histogram.  Histogram 0's cell alone would
    flag B = 20 here; histogram 1's larger cell admits it."""
    admitted = _shared_biso_two_cells(two_patterns, 20.0, 3.0)
    far = _shared_biso_two_cells(two_patterns, 20.0, 1.0)
    # the control: equal cells, histogram 0's bound is the bound, B is flagged
    assert _codes(far, "BISO_UNUSUALLY_LARGE")
    # a cell large enough that its bound admits the B: nothing fires
    assert not _codes(admitted, "BISO_UNUSUALLY_LARGE")
    past = _shared_biso_two_cells(two_patterns, 400.0, 1.5)
    (found,) = _codes(past, "BISO_UNUSUALLY_LARGE")
    assert found.where == ["phases.0.atoms.0.biso"]
    assert "loosest of 2" in found.message
    assert "histogram 1" in found.message


def test_a_joint_cell_driven_out_of_its_window_names_its_coefficient(
        two_patterns, monkeypatch):
    """The joint twin of ``refine._vars_driven_cell_escapes`` (review of #385
    finding 1).  A parametric cell is a dependent of its ``vars.`` columns,
    so the joint reset, which reads free cell columns, cannot see it walk.
    The walk is forced here: the solve's answer is moved 30 % along
    ``vars.a_0`` before the stage commits it, outside the ±15 % window."""
    import dataclasses

    import numpy as np

    from rietx import multi
    from rietx.schemas.parametric import CoordinateTable, ParametricEquation

    real = multi.run_multi_least_squares
    calls = []

    def walked(models, mtable, **kw):
        out = real(models, mtable, **kw)
        calls.append(kw.get("stage"))
        if len(calls) > 1:      # the first solve walks, nothing after it
            return out
        theta = np.array(out.theta, dtype=float)
        theta[mtable.free_paths.index("vars.a_0")] *= 1.3
        return dataclasses.replace(out, theta=theta)

    monkeypatch.setattr(multi, "run_multi_least_squares", walked)
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(
        structure, instruments,
        coordinates=CoordinateTable(columns={"T": [300.0, 500.0]},
                                    units={"T": "K"}),
        parametric=[ParametricEquation(name="a", target="phases.0.cell.a",
                                       basis="polynomial", terms=[[], ["T"]])])
    result = ref.fit(two_patterns, plan=RefinementPlan(stages=[
        Stage("only", ["phases.*.scale", "vars.*"], max_iter=3)]))
    (found,) = _codes(result, "CELL_RUNAWAY")
    assert "vars.a_0" in found.where
    assert {"hist.0.phases.0.cell.a", "hist.1.phases.0.cell.a"} <= set(found.where)
    assert "vars.a_0 drives" in found.message
    assert "not put back" in found.message


def test_a_joint_cell_inside_its_window_names_nothing(two_patterns):
    """The control: the same parametric fit, unwalked."""
    from rietx.schemas.parametric import CoordinateTable, ParametricEquation

    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(
        structure, instruments,
        coordinates=CoordinateTable(columns={"T": [300.0, 500.0]},
                                    units={"T": "K"}),
        parametric=[ParametricEquation(name="a", target="phases.0.cell.a",
                                       basis="polynomial", terms=[[], ["T"]])])
    result = ref.fit(two_patterns, plan=RefinementPlan(stages=[
        Stage("only", ["phases.*.scale", "vars.*"], max_iter=3)]))
    assert not _codes(result, "CELL_RUNAWAY")


def _vanished_phase_fit():
    """test_held_phase's series shape: pattern 0 lacks the second phase,
    pattern 1 has it, every phase path per histogram."""
    import rietx as rx
    from tests.test_held_phase import _absent_phase_inputs, _pattern_with_both_phases
    from tests.test_held_phase import synthesize as one_phase

    blind, ins = _absent_phase_inputs()
    seen = blind.model_copy(deep=True)
    seen.phases[1].scale.value = blind.phases[0].scale.value
    ref = rx.MultiHistogramRefinement(
        [blind, seen], [ins, ins.model_copy(deep=True)],
        sharing=SharingMap(per_histogram=["phases.*"]))
    result = ref.fit([one_phase(), _pattern_with_both_phases()],
                     plan=rx.RefinementPlan(stages=[
                         rx.Stage("scale_bkg", ["phases.*.scale",
                                                "instrument.background.*"]),
                         rx.Stage("cell", ["phases.*.cell.*"])]))
    return ref, result


@pytest.fixture(scope="module")
def vanished_phase_fit():
    return _vanished_phase_fit()


def test_a_hold_made_in_some_patterns_is_named_with_its_count(vanished_phase_fit):
    _, result = vanished_phase_fit
    assert result.stages[-1].held == ["hist.0.phases.1.cell.a"]
    (found,) = _codes(result, "PHASE_HELD_IN_PATTERNS")
    assert found.level == "info"
    assert found.where == ["hist.0.phases.1.cell.a"]
    assert found.value == 1.0
    assert "held in 1 of 2 patterns (histogram 0)" in found.message
    # the phase is seen by the joint fit, so the joint code stays silent
    assert not _codes(result, "PHASE_UNCONSTRAINED")


def test_a_fit_that_held_nothing_per_pattern_names_nothing(two_patterns):
    result = _one_stage(two_patterns, ["phases.*.cell.*"],
                        sharing=SharingMap(per_histogram=["phases.*"]))
    assert not _codes(result, "PHASE_HELD_IN_PATTERNS")


def test_a_histogram_view_keeps_its_reflections_and_structure_r(two_patterns):
    """WP-1986's gap: ``for_histogram`` copied ``ticks`` alone."""
    result = _one_stage(two_patterns, [])
    for h, hr in enumerate(result.histograms):
        view = result.for_histogram(h)
        assert hr.tick_hkl and view.tick_hkl == hr.tick_hkl
        assert hr.phase_agreement
        assert view.phase_agreement == hr.phase_agreement
    # the top level mirrors histogram 0, its ticks and their labels together
    assert result.ticks == result.histograms[0].ticks
    assert result.tick_hkl == result.histograms[0].tick_hkl


def test_a_histogram_view_carries_the_fit_findings_that_name_it(vanished_phase_fit):
    """A finding scoped to histogram h sits beside h's own; histogram 1's
    view does not carry histogram 0's hold."""
    _, result = vanished_phase_fit
    zero = [d.code for d in result.for_histogram(0).diagnostics]
    one = [d.code for d in result.for_histogram(1).diagnostics]
    assert zero.count("PHASE_HELD_IN_PATTERNS") == 1
    assert "PHASE_HELD_IN_PATTERNS" not in one


def test_a_stage_that_freed_nothing_in_a_histogram_reaches_its_view(two_patterns):
    """``STAGE_FREED_NOTHING``'s ``value`` is the histogram's index."""
    from rietx.schemas.instrument import BackgroundChebyshev

    structure, instruments = perturbed_inputs()
    # a fourth term on histogram 0 alone, so the literal reaches only it
    instruments[0].background = BackgroundChebyshev.with_terms(4)
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(two_patterns, plan=RefinementPlan(stages=[
        Stage("only", ["instrument.background.c3"], max_iter=3)]))
    (top,) = _codes(result, "STAGE_FREED_NOTHING")
    assert top.value == 1.0
    assert not [d for d in result.for_histogram(0).diagnostics
                if d.code == "STAGE_FREED_NOTHING"]
    assert [d for d in result.for_histogram(1).diagnostics
            if d.code == "STAGE_FREED_NOTHING"] == [top]


def test_a_fit_level_finding_appears_once_in_every_view(two_patterns):
    """The FIT findings a reader of one pattern must see
    (``SCALE_B_INSEPARABLE``, ``PARAMETRIC_OUT_OF_RANGE``,
    ``PARAMETRIC_FORM_REJECTED``, ``STAGE_PATH_UNKNOWN``) are copied once
    into each view, never once per histogram."""
    result = _one_stage(two_patterns, ["phases.0.no_such_path"])
    (top,) = _codes(result, "STAGE_PATH_UNKNOWN")
    for h in range(2):
        mine = [d for d in result.for_histogram(h).diagnostics
                if d.code == "STAGE_PATH_UNKNOWN"]
        assert mine == [top]


# ------------------------------------------- WP-2028, review round 1 -----

def test_a_phase_held_in_every_pattern_is_unconstrained_not_held_in_patterns():
    """Two patterns, neither showing phase 1, its structure per histogram:
    ``PHASE_UNCONSTRAINED`` says it, and ``PHASE_HELD_IN_PATTERNS`` (a hold
    in *some* patterns) does not repeat it (review of #1128, item 1)."""
    import rietx as rx
    from tests.test_held_phase import _absent_phase_inputs
    from tests.test_held_phase import synthesize as one_phase

    blind, ins = _absent_phase_inputs()
    ref = rx.MultiHistogramRefinement(
        [blind, blind.model_copy(deep=True)], [ins, ins.model_copy(deep=True)],
        sharing=SharingMap(per_histogram=["phases.*"]))
    result = ref.fit([one_phase(), one_phase()], plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"])]))
    assert result.stages[-1].held        # the control: something was held
    assert _codes(result, "PHASE_UNCONSTRAINED")
    assert not _codes(result, "PHASE_HELD_IN_PATTERNS")
    for h in range(2):
        assert not [d for d in result.for_histogram(h).diagnostics
                    if d.code == "PHASE_HELD_IN_PATTERNS"]


def _hold_stub(held, ridge, n):
    from types import SimpleNamespace as NS
    last = NS(held=held, scale_b_held=ridge, name="cell")
    table = NS(parametric=[], n_histograms=n,
               _owner=lambda p: int(p.split(".")[1]) if p.startswith("hist.")
               else None)
    structure = NS(phases=[NS(name="A"), NS(name="B")])
    return [last], table, structure


@pytest.mark.parametrize("leaf, ridge_phases, fires", [
    ("adp.1", {0}, False),      # an anisotropic column the ridge took
    ("biso", {0}, False),       # the isotropic one, as before
    ("u12", {0}, False),
    ("adp.1", set(), True),     # control: not a ridge hold
    ("cell.a", {0}, True),      # control: a ridge hold takes displacements only
])
def test_the_ridge_exclusion_reads_the_displacement_columns_refine_does(
        leaf, ridge_phases, fires):
    from rietx.multi import _per_pattern_hold_diagnostics

    held = [f"hist.0.phases.0.atoms.0.{leaf}"]
    stages, table, structure = _hold_stub(held, ridge_phases, 3)
    assert bool(_per_pattern_hold_diagnostics(stages, table, structure)) is fires


def test_an_adp_site_is_scoped_by_the_columns_that_move_it():
    """``adp.k`` is what a joint fit frees; ``u11`` merely follows it (review
    of #1128, item 3)."""
    from types import SimpleNamespace as NS

    from rietx.multi import _row_shared, _specimen_path

    per_adp = NS(sharing=SharingMap(per_histogram=["phases.*.atoms.*.adp.*"]))
    assert _specimen_path(per_adp, 1, "phases.0.atoms.0") == "hist.1.phases.0.atoms.0"
    plain = NS(sharing=SharingMap())
    assert _specimen_path(plain, 1, "phases.0.atoms.0") == "phases.0.atoms.0"
    # a follower row is its source's, not its own name's
    u11 = NS(path="phases.0.atoms.0.u11",
             tie=NS(terms=(("phases.0.atoms.0.adp.0", 1.0),)))
    assert not _row_shared(per_adp, u11)
    assert _row_shared(plain, u11)
    assert _row_shared(plain, NS(path="phases.0.cell.a", tie=None))


def test_an_occupancy_above_one_in_one_histograms_copy_is_named(two_patterns):
    """Review of #1128, item 4: ``OCCUPANCY_ABOVE_ONE`` read histogram 0."""
    structure, instruments = perturbed_inputs()
    other = structure.model_copy(deep=True)
    structure.phases[0].atoms[0].occ.value = 0.5
    other.phases[0].atoms[0].occ.value = 1.4

    def fit(sharing):
        ref = MultiHistogramRefinement(
            [structure.model_copy(deep=True), other.model_copy(deep=True)],
            instruments, sharing=sharing)
        return ref.fit(two_patterns, plan=RefinementPlan(stages=[
            Stage("occ", ["phases.*.scale", "instrument.background.*",
                          "phases.0.atoms.0.occ"], max_iter=2)]))

    own = fit(SharingMap(per_histogram=["phases.0.atoms.*.occ"]))
    (found,) = _codes(own, "OCCUPANCY_ABOVE_ONE")
    assert found.where == ["hist.1.phases.0.atoms.0.occ"]
    assert "histogram 1" in found.message


# --------------------------------------- WP-2028, review round 2 (item 7) --

def _blind_pattern_fit(*, free_cell: bool):
    """The vanished-phase pair with pattern 0 cut to 3-4°, where no line of
    either phase lies, so pattern 0 holds both scales (WP-1958, #1103) while
    pattern 1 sees both: the joint fit sees every phase."""
    import rietx as rx
    from tests.test_held_phase import (
        _absent_phase_inputs,
        _pattern_with_both_phases,
    )
    from tests.test_held_phase import synthesize as one_phase

    blind, ins = _absent_phase_inputs()
    seen = blind.model_copy(deep=True)
    seen.phases[1].scale.value = blind.phases[0].scale.value
    ref = rx.MultiHistogramRefinement(
        [blind, seen], [ins, ins.model_copy(deep=True)],
        sharing=SharingMap(per_histogram=["phases.*"]))
    stages = [rx.Stage("scale_bkg", ["phases.*.scale",
                                     "instrument.background.*"])]
    if free_cell:
        stages.append(rx.Stage("cell", ["phases.*.cell.*"]))
    return ref.fit([one_phase(), _pattern_with_both_phases()],
                   plan=rx.RefinementPlan(stages=stages),
                   two_theta_limits=[(3.0, 4.0), None])


@pytest.fixture(scope="module")
def scale_only_hold():
    return _blind_pattern_fit(free_cell=False)


def test_a_scale_held_in_one_pattern_is_named_once_with_its_pattern(
        scale_only_hold):
    """Review of #1128, round 2, item 7: #1103's ``PHASE_UNCONSTRAINED`` is
    silent while another pattern sees the phase, and this record dropped
    ``.scale`` rows, so nothing said pattern 0 held only a scale."""
    result = scale_only_hold
    assert result.stages[-1].held == ["hist.0.phases.0.scale",
                                      "hist.0.phases.1.scale"]
    assert not _codes(result, "PHASE_UNCONSTRAINED")
    found = _codes(result, "PHASE_HELD_IN_PATTERNS")
    assert [d.where for d in found] == [["hist.0.phases.0.scale"],
                                        ["hist.0.phases.1.scale"]]
    for d in found:
        assert d.value == 1.0
        assert "held in 1 of 2 patterns (histogram 0)" in d.message
        assert "own scale keeps the value handed in" in d.message
        assert "structure" not in d.message
    # the pattern that holds it is the one whose fraction is absent
    assert all(x.weight_fraction is None
               for x in result.for_histogram(0).qpa.phases)
    assert all(x.weight_fraction is not None
               for x in result.for_histogram(1).qpa.phases)


def test_a_scale_and_its_structure_held_together_are_one_finding_per_phase():
    result = _blind_pattern_fit(free_cell=True)
    found = _codes(result, "PHASE_HELD_IN_PATTERNS")
    assert [d.where for d in found] == [
        ["hist.0.phases.0.cell.a", "hist.0.phases.0.scale"],
        ["hist.0.phases.1.cell.a", "hist.0.phases.1.scale"]]
    for d in found:
        assert "structure (1 row)" in d.message
        assert "own scale keeps the value handed in" in d.message


@pytest.mark.parametrize("held, n, fires", [
    (["hist.0.phases.0.scale"], 2, True),
    (["hist.0.phases.0.scale", "hist.1.phases.0.scale"], 2, False),  # every pattern
    (["phases.0.scale"], 2, False),                  # shared: PHASE_UNCONSTRAINED's
    (["hist.0.phases.0.scale", "hist.1.phases.0.cell.a"], 3, True),  # union of patterns
])
def test_the_scale_rows_count_toward_the_patterns_a_phase_was_held_in(
        held, n, fires):
    from rietx.multi import _per_pattern_hold_diagnostics

    stages, table, structure = _hold_stub(held, set(), n)
    found = _per_pattern_hold_diagnostics(stages, table, structure)
    assert bool(found) is fires
    if fires and held[-1].startswith("hist.1"):
        assert found[0].value == 2.0 and len(found) == 1
