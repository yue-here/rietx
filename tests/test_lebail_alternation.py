"""WP-1323: the Le Bail alternation has a stop rule, and the package owns it.

The pattern is 11-BM LaB6 + cBN, Le Bail scaffolds, ``profile_only``.  It is the
in-tree stand-in for issue #210's multi-phase lab pattern.  It shows three
shapes depending on where the cells start.  At +0.48 % pass 2 comes back
*worse* than pass 1 (``WORSE_START``).  At -0.15 % the passes converge.  At +2 %
they never settle.

The fast tests fit 5.1-25° (``LIMITS``), under half the range the hand loop
used, and a fit costs a quarter to a fifth of one at 5.1-50° (WP-1547).  The
three shapes hold there.  The converging one starts at -0.15 %, because +0.4 %
sits on an edge at 5.1-25°: WP-1936's step for ``u`` and ``v`` turns it into a
worse-pass start.  -0.15 % converges with or without that step on macOS, and
without it on Linux.  How many passes it takes depends on the platform, so its
test asserts the shape and not the count.  A start of +0.6 % or more diverges at
5.1-25° whatever the
loop does.  Every Rwp the fast tests pin was measured at 5.1-25°.

The worse-pass start was +0.3 % until WP-1938, which refines every width in
its own units and makes LM the default driver.  Under TRF, from +0.45 % to
+0.52 % pass 1 reads 13.847 % and pass 2 13.865 %.  That pass 1 sits where
Γ_G² is under the clamp at the high-angle reflections (U = -0.0032).  LM holds
Γ_G² ≥ 1e-8 at every reflection (D7, D8), so it stops short of that point.
Under LM, from +0.20 % to +0.52 % pass 1 reads 13.918-13.920 % and pass 2
13.932 %.  +0.10 % and +0.56 % converge instead (macOS arm64, ``[dev]``), so
``WORSE_START`` is the middle of that range.  The one
``slow`` test keeps 5.1-50° (``WIDE_LIMITS``), where its pins were measured.

At 5.1-50° the per-pass numbers were re-measured in WP-1930.  Its floor seed
started ``instrument.profile.y`` off its softplus floor, where it had stayed,
and every pass came down by about 3 percentage points of Rwp: the exact cells'
pass 1 read 16.821 % before and 14.220 % after.

The tests that only read a fit share it through a module fixture, each pinned
to one worker by its ``xdist_group``.  A history, a run directory and an event
callback each leave the fit bit-identical: Rwp and every parameter were equal
with and without them at +0.3 % and +0.4 % (WP-1547).
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

import rietx as rx
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.plan import PlanSpec
from rietx.schemas.structure import lebail_scaffold
from rietx.strategy.staged import resolve_plan

DATA = Path(__file__).parent / "data"
PATTERN = DATA / "11BM_LaB6_cBN_mg2044.xye"
LIMITS = (5.1, 25.0)
WIDE_LIMITS = (5.1, 50.0)
CODE = "LEBAIL_ALTERNATION_STOPPED"
#: Rwp is quoted from a converged fit, whose stopping point moves with the
#: platform's libm.  The spread below was measured under TRF.  Before WP-1930 the exact-cell pass 1 at 5.1-50° read
#: 0.168210 on macOS arm64 and 0.168236-0.168238 on Linux x86-64 (CI,
#: py3.11/3.12 and jax), a spread of 2.8e-5.  The bar is 3.6 times that, and it
#: holds on every leg for each pass a test keeps.  A discarded pass is asserted
#: by order only, since +0.3 %'s pass 2 at 5.1-50° spread 1.5e-4 across
#: platforms.
RWP_PLATFORM_SPREAD = 1e-4
#: the cell start whose pass 2 comes back worse than pass 1 (module docstring)
WORSE_START = 1.0036
#: the Rwp of that start's kept pass 1 under LM, identical to six digits
#: across starts nudged by 1e-14 (0.138471 from +0.48 % under TRF)
WORSE_KEPT_RWP = 0.139185


@pytest.fixture(scope="module")
def pattern():
    if not PATTERN.exists():
        pytest.skip("11-BM LaB6+cBN dataset not present")
    return rx.read_pattern(PATTERN)


def _refinement(cell_scale: float, history: bool = False) -> rx.Refinement:
    lab6 = lebail_scaffold("P m -3 m", [4.1569 * cell_scale] * 3 + [90.0] * 3,
                           name="LaB6")
    cbn = lebail_scaffold("F -4 3 m", [3.6165 * cell_scale] * 3 + [90.0] * 3,
                          name="cBN")
    ins = rx.Instrument.debye_scherrer(wavelength=0.41368)
    ins.source.dispersion = None
    ins.profile.w.value = 2e-5
    ins.profile.x.value = 2e-3
    ins.background = BackgroundChebyshev.with_terms(8)
    return rx.Refinement(rx.Structure(phases=[lab6.phases[0], cbn.phases[0]]),
                         ins, history=history)


def _plan(passes: int, **fields):
    return dataclasses.replace(resolve_plan("profile_only", "lebail"),
                               lebail_passes=passes, **fields)


def _fit(ref, data, passes: int, limits=LIMITS, **fields):
    return ref.fit(data, mode="lebail", plan=_plan(passes, **fields),
                   two_theta_limits=limits, telemetry=False)


def _stop(result):
    found = [d for d in result.diagnostics if d.code == CODE]
    assert len(found) == 1
    return found[0]


def _plot(result, name):
    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / name))


@pytest.fixture(scope="module")
def exact(pattern):
    """Exact cells at a cap of 3 passes, with no history."""
    ref = _refinement(1.0)
    return ref, _fit(ref, pattern, 3)


@pytest.fixture(scope="module")
def worse(pattern):
    """``WORSE_START`` cells with a history: pass 1 kept, pass 2 discarded."""
    ref = _refinement(WORSE_START, history=True)
    # the declared stages' passes; the closing stage is tests/test_closing_stage.py's
    return ref, _fit(ref, pattern, 8, closing_window_tol=None)


@pytest.fixture(scope="module")
def converging(pattern, tmp_path_factory):
    """-0.15 % cells recorded to a run directory.  The run state is read from
    ``status.json`` at each pass's ``fit_start`` and ``fit_end``."""
    from rietx import runs
    root = tmp_path_factory.mktemp("lebail-runs")
    states = []

    def on_event(e):
        if e["kind"] in ("fit_start", "fit_end"):
            status = [p / "status.json" for p in root.iterdir() if p.is_dir()]
            if status and status[0].exists():
                states.append(json.loads(status[0].read_text(encoding="utf-8"))["state"])

    was = runs.set_enabled(True)
    try:
        result = rx.Refinement.fit(_refinement(0.9985), pattern, mode="lebail",
                                   plan=_plan(8), two_theta_limits=LIMITS,
                                   telemetry=str(root), events=on_event)
    finally:
        runs.set_enabled(was)
    return result, root, states


def test_one_pass_is_the_plain_fit_and_says_nothing(pattern):
    """``lebail_passes=1`` is every fit made before the field: no loop, no row."""
    plain = _refinement(1.0).fit(data=pattern, mode="lebail",
                                 plan="profile_only", two_theta_limits=LIMITS,
                                 telemetry=False)
    one = _fit(_refinement(1.0), pattern, 1)
    assert one.statistics.rwp == plain.statistics.rwp
    assert not [d for d in one.diagnostics if d.code == CODE]


@pytest.mark.xdist_group("lebail-worse")
def test_a_pass_that_comes_back_worse_stops_the_loop_and_pass_one_is_kept(worse):
    """``WORSE_START`` cells: 13.918 then a worse pass 2, and the loop sits at pass 1."""
    ref, result = worse
    stop = _stop(result)
    assert stop.level == "warning"
    assert "did not lower Rwp" in stop.message
    assert "Pass 1 of 2 was kept" in stop.message
    assert result.statistics.rwp == pytest.approx(WORSE_KEPT_RWP, abs=RWP_PLATFORM_SPREAD)
    assert stop.value == result.statistics.rwp
    # the per-pass table the message prints, read as numbers.  Pass 1 is the
    # kept answer and is pinned to RWP_PLATFORM_SPREAD, in per cent.  Pass 2
    # is the discarded one, and only its order is the claim.  It read 13.932
    # on macOS arm64 under LM.
    table = [float(v) for v in re.search(
        r"Rwp % per pass: ([\d., ]+)\)", stop.message).group(1).split(",")]
    assert len(table) == 2
    assert table[0] == pytest.approx(100 * WORSE_KEPT_RWP, abs=100 * RWP_PLATFORM_SPREAD)
    assert table[1] > table[0]
    assert CODE in str(result)              # the termination view carries it
    # the GUI's run record carries the verdict, since no panel shows a
    # result's diagnostics and a node cannot hold this one
    from rietx.gui.session import _summarize_refinement
    run = _summarize_refinement(result, None)
    assert run["lebail"]["stopped"] == stop.message
    assert run["lebail"]["level"] == "warning"
    # the kept pass is the one the Refinement answers from afterwards
    assert ref.result_ is result
    assert ref.report() is not None
    _plot(result, "lebail_alternation_worse.png")


@pytest.mark.xdist_group("lebail-converging")
def test_a_converging_run_is_not_cut_short_and_ends_at_a_fixed_point(converging):
    """-0.15 % cells: each pass lower than the last until two are level.

    The shape is the claim, and the pass it stops on is not.  The path splits by
    platform from pass 3: macOS read 18.810, 14.150, 13.949, 13.933, 13.932,
    and Linux 18.810, 14.150, 13.927, 13.908, 13.905, 13.905 (PR #857's CI).
    PR #855's pin at 5.1-50° split the same way, pass 6 against pass 5.
    """
    from rietx.refine import LEBAIL_CONVERGED_REL
    result, _, _ = converging
    stop = _stop(result)
    assert stop.level == "info"
    assert "fixed point" in stop.message
    table = [float(v) for v in re.search(
        r"Rwp % per pass: ([\d., ]+)\)", stop.message).group(1).split(",")]
    assert len(table) >= 4                       # not cut short
    assert all(b < a for a, b in zip(table[:-2], table[1:-1]))
    assert table[-1] <= table[-2] * (1 + LEBAIL_CONVERGED_REL) + 1e-3  # level, in %
    kept = int(re.search(r"Pass (\d+) of", stop.message).group(1))
    assert kept in (len(table) - 1, len(table))
    # 0.139321 on macOS and 0.139050 on Linux: a spread of 2.7e-4, so the bar
    # is 1e-3, wider than RWP_PLATFORM_SPREAD, which a single pass carries
    assert result.statistics.rwp == pytest.approx(0.1392, abs=1e-3)
    _plot(result, "lebail_alternation_converged.png")


def test_the_cap_is_a_cap_and_says_it_truncated(pattern):
    """Two passes of a run that was still falling: truncated, not finished."""
    result = _fit(_refinement(0.9985), pattern, 2)
    stop = _stop(result)
    assert stop.level == "warning"
    assert "cap of 2 passes" in stop.message
    assert "Pass 2 of 2 was kept" in stop.message


@pytest.mark.slow       # ~40-80 s: the +2 % start wanders through four passes
def test_the_state_the_loop_keeps_is_the_state_a_hand_loop_would_continue_from(pattern):
    """Restoring the best pass must not hand the next ``fit`` a start the hand
    loop never had.  Seeding the restored intensities does exactly that: the
    +2 % start measured 254.09 % against the loop's 194.56 % on pass 4
    (194.55 % under LM).  So the next fit's Rwp is the loop's pass 4, read
    off the stop message.

    The wander's numbers are not pinned, and nor is which pass it keeps.
    Since WP-1953's held column scale they depend on the start: the kept pass
    read 155.22 % from the exact +2 % and 177.80 % from starts 1e-14 either
    side.  Since WP-2002 a cell that runs past 15 % is reset to its stage
    start rather than clamped at the edge, and the cell stage here does run
    away (``CELL_RUNAWAY``), so the wander kept pass 2 of 3 where it kept
    pass 3 of 4.  What is asserted is the invariant: the result is the kept
    pass, and the next fit continues from it as the hand loop would."""
    ref = _refinement(1.02)
    result = _fit(ref, pattern, 8, limits=WIDE_LIMITS)
    stop = _stop(result)
    kept, ran = (int(v) for v in re.search(
        r"Pass (\d+) of (\d+) was kept", stop.message).groups())
    assert kept < ran, stop.message      # a later pass exists to continue to
    per_pass = [float(v) / 100.0 for v in re.search(
        r"Rwp % per pass: ([\d., ]+)\)", stop.message).group(1).split(", ")]
    assert result.statistics.rwp == pytest.approx(per_pass[kept - 1], abs=1e-5)
    nxt = ref.fit(pattern, mode="lebail", plan="profile_only",
                  two_theta_limits=WIDE_LIMITS, telemetry=False)
    assert nxt.statistics.rwp == pytest.approx(per_pass[kept], abs=1e-5)
    _plot(result, "lebail_alternation_wander_kept.png")


@pytest.mark.xdist_group("lebail-worse")
def test_the_passes_mark_their_history_nodes_and_the_head_stands_in_the_kept_one(worse):
    """Pass 1 kept, pass 2 discarded: the notes say which nodes are whose."""
    ref, _ = worse
    tree = ref.history
    notes = {i: tree.nodes[i].notes for i in tree.order}
    assert notes[tree.order[0]] == {}                    # the root is no pass's
    one = [n for n in notes.values() if n.get("lebail_pass") == "1"]
    two = [n for n in notes.values() if n.get("lebail_pass") == "2"]
    assert one and two
    assert all(n.get("lebail_kept") == "1 of 2" for n in one)
    assert all(n.get("lebail_discarded") == "true" for n in two)
    assert "lebail_discarded" not in tree.nodes[tree.head].notes
    assert tree.nodes[tree.head].notes["lebail_pass"] == "1"


@pytest.mark.xdist_group("lebail-exact")
def test_without_a_history_the_marking_writes_and_raises_nothing(exact):
    ref, _ = exact
    assert ref.history is None


def test_the_field_crosses_the_mirror_both_ways_and_refuses_zero():
    plan = _plan(5)
    spec = PlanSpec.from_plan(plan)
    assert spec.lebail_passes == 5
    assert spec.to_plan().lebail_passes == 5
    assert PlanSpec.model_validate(spec.model_dump(mode="json")).lebail_passes == 5
    with pytest.raises(ValueError):
        PlanSpec(stages=[], lebail_passes=0)


@pytest.mark.xdist_group("lebail-converging")
def test_an_alternation_is_one_run_directory_not_one_per_pass(converging):
    """``rietx watch`` lists a job once; a pass each drew N rows (WP-1403)."""
    result, root, _ = converging
    assert _stop(result).value == result.statistics.rwp
    # several passes before it settles, so a directory per pass would show
    dirs = [p for p in root.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    assert (dirs[0] / "meta.json").exists()


def test_a_cancel_in_a_later_pass_leaves_the_best_pass_standing(pattern):
    """Pass 1 is the best at ``WORSE_START``; a cancel during pass 2 restores it."""
    from rietx.optimize.cancel import CancelToken, RefinementCancelled
    ref = _refinement(WORSE_START)
    token = CancelToken()
    seen = []

    def on_event(e):
        kind = getattr(e, "kind", None) or (e.get("kind") if isinstance(e, dict) else None)
        if kind == "fit_start":
            seen.append(kind)
            if len(seen) == 2:
                token.cancel()
    # the declared stages' passes; the closing stage is tests/test_closing_stage.py's
    with pytest.raises(RefinementCancelled):
        ref.fit(pattern, mode="lebail", plan=_plan(8, closing_window_tol=None),
                two_theta_limits=LIMITS, telemetry=False, events=on_event, cancel=token)
    assert ref.result_ is not None
    assert ref.result_.statistics.rwp == pytest.approx(WORSE_KEPT_RWP,
                                                       abs=RWP_PLATFORM_SPREAD)


@pytest.mark.xdist_group("lebail-exact")
def test_the_refinement_records_the_cap_it_was_asked_for(exact):
    ref, result = exact
    assert ref._last_plan.lebail_passes == 3
    assert result is ref.result_


@pytest.mark.xdist_group("lebail-converging")
def test_a_pass_ending_is_not_the_run_ending(converging):
    """Each pass emits a ``fit_end``; a recorder that read "done" off the first
    told ``rietx watch`` the job had finished while passes 2..N still ran."""
    _, root, states = converging
    assert len(states) >= 4 and set(states) == {"running"}
    final = json.loads(next(root.glob("*/status.json")).read_text(encoding="utf-8"))
    assert final["state"] == "done"


def test_a_cancel_part_way_through_a_later_pass_restores_the_best_pass(pattern):
    """The in-flight pass's completed stages stand after a cancel, so the state
    is neither pass 1's nor its own end unless the loop puts it back."""
    from rietx.optimize.cancel import CancelToken, RefinementCancelled
    ref = _refinement(WORSE_START)
    token = CancelToken()
    fits, ends = [], []

    def on_event(e):
        if e["kind"] == "fit_start":
            fits.append(1)
        elif e["kind"] == "stage_end" and len(fits) == 2:
            ends.append(1)
            if len(ends) == 4:          # the cell is free by then
                token.cancel()
    # the declared stages' passes; the closing stage is tests/test_closing_stage.py's
    with pytest.raises(RefinementCancelled):
        ref.fit(pattern, mode="lebail", plan=_plan(8, closing_window_tol=None),
                two_theta_limits=LIMITS, telemetry=False, events=on_event, cancel=token)
    kept = ref.result_
    assert kept.statistics.rwp == pytest.approx(WORSE_KEPT_RWP, abs=RWP_PLATFORM_SPREAD)
    cell = {p.path: p.value for p in kept.parameters}["phases.0.cell.a"]
    assert ref.structure.phases[0].cell.a.value == pytest.approx(cell, abs=1e-9)
