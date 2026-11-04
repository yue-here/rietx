"""The forward pass of a ``direction="both"`` series, readable at the halfway
point, and the movement ranking a trajectory plot needs (issue #218, WP-1317).

Two asks, one per half of this file.  ``SequentialRefinement.forward_`` is the
forward chain's ``SeriesResult``, published where WP-1333 already publishes
``results_``/``trees_``/``failures_`` — after the forward chain and before the
backward walk starts — so a caller watching the run (an ``events=`` callback,
the GUI's poll) can judge the trajectory while the second half is still
fitting.  ``SeriesResult.moved_paths`` ranks paths by how far each moved against
its own esd, so every caller of ``plot_trajectory`` stops inventing that
ranking.
"""

import math
from pathlib import Path

import pytest

from rietx.schemas.results import RefinedParameter
from rietx.schemas.sequential import SeriesEntry, SeriesResult
from rietx.sequential import SequentialRefinement
from rietx.strategy import staged
from rietx.viz.plots import plot_result, plot_trajectory
from tests.test_sequential import A0, RAMP, _simulate, _start_models

#: one stage, a handful of evaluations: these tests are about *when* the
#: forward result exists, not about what it fitted
_CHEAP = staged.RefinementPlan(stages=[
    staged.Stage("quick", ["phases.*.scale", "phases.*.cell.*"], max_iter=5)])


@pytest.fixture(scope="module")
def ramp():
    return [_simulate(A0 * (1 + RAMP * i), seed=900 + i) for i in range(3)]


# ------------------------------------------------------------ forward_ ---
def test_the_forward_result_is_readable_while_the_backward_pass_runs(ramp):
    """The halfway point, read from inside the run.

    The first backward ``fit_start`` is the earliest moment the backward walk
    exists; by then the forward ``SeriesResult`` must be on the runner, whole,
    with the forward chain's diagnostics and none of the comparison's.
    """
    structure, ins = _start_models()
    runner = SequentialRefinement(structure, ins)
    seen: dict = {}

    def watch(event):
        data = event["data"]
        if (event["kind"] == "fit_start" and data.get("series_pass") == "backward"
                and "forward" not in seen):
            seen["forward"] = runner.forward_
            seen["result"] = runner.result_
            # the issue's one line, at the halfway point
            seen["moved"] = runner.forward_.moved_paths(6, min_sigma=0.0)

    series = runner.fit(ramp, plan=_CHEAP, labels=["a", "b", "c"],
                        direction="both", events=watch)

    mid = seen["forward"]
    assert isinstance(mid, SeriesResult)
    # the forward chain alone: it claims no comparison, so a reader cannot take
    # an empty gap list on it for a check that ran and found nothing
    assert mid.direction == "forward"
    assert mid.backward is None
    assert mid.direction_gaps is None
    assert mid.labels == ["a", "b", "c"]
    assert not any(d.code.startswith("SEQUENTIAL_PATH_")
                   for d in mid.diagnostics)
    # and nothing has claimed to be the run's answer yet
    assert seen["result"] is None

    # the run's answer is the same chain, now with the comparison on it
    assert series.direction == "both" and series.backward is not None
    assert [e.model_dump() for e in series.entries] == [
        e.model_dump() for e in mid.entries]
    # the snapshot is not rewritten under its reader when the run finishes
    assert runner.forward_ is mid
    assert mid.direction == "forward" and mid.backward is None
    assert not any(d.code.startswith("SEQUENTIAL_PATH_")
                   for d in mid.diagnostics)
    # every forward-chain diagnostic it held is still on the answer
    final = [d.model_dump() for d in series.diagnostics]
    assert all(d.model_dump() in final for d in mid.diagnostics)
    assert "phases.0.cell.a" in seen["moved"]

    # obs/calc/diff PNGs to tests/output/ (gitignored), and the forward
    # trajectory as it stood at the halfway point
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_trajectory(mid, seen["moved"],
                    path=str(out / "series_forward_pass_trajectory.png"))
    for k, result in enumerate(runner.results_):
        plot_result(result, path=str(out / f"series_forward_pass_p{k}.png"))


def test_a_one_direction_run_publishes_no_forward_pass(ramp):
    """``forward_`` names the halfway point, and a forward run has none.

    The peer of ``backward_``, which is ``None`` unless a verification pass ran.
    """
    structure, ins = _start_models()
    runner = SequentialRefinement(structure, ins)
    series = runner.fit(ramp[:2], plan=_CHEAP)

    assert runner.forward_ is None
    assert runner.backward_ is None
    assert runner.result_ is series
    assert series.direction == "forward"


def test_a_second_fit_does_not_leave_the_first_runs_forward_pass(ramp):
    """``result_``'s rule (WP-1333): this run's, or nothing."""
    structure, ins = _start_models()
    runner = SequentialRefinement(structure, ins)
    runner.fit(ramp[:2], plan=_CHEAP, direction="both")
    assert runner.forward_ is not None

    runner.fit(ramp[:2], plan=_CHEAP)
    assert runner.forward_ is None


def test_a_series_records_which_paths_are_steps_and_which_are_angles(ramp):
    """The facts ``moved_paths`` needs, written where they are known.

    A coordinate DOF is a step from where its fit began and a moment angle
    wraps, and nothing in an entry says which a path is; the run knows from its
    models, so it records both lists on the result it returns, on the backward
    chain and on the forward pass.  LaB6's boron sits on 6f with one free
    direction, so the step list is not empty; nothing here is magnetic, so the
    angle list is.
    """
    from rietx.sequential import _relative_paths

    structure, ins = _start_models()
    expected = sorted(_relative_paths(structure, ins))
    assert expected, "the fixture has no displacement DOF to record"
    runner = SequentialRefinement(structure, ins)
    series = runner.fit(ramp[:2], plan=_CHEAP, direction="both")

    for result in (series, series.backward, runner.forward_):
        assert result.relative_paths == expected
        assert result.angle_paths == []
    again = SeriesResult.model_validate_json(series.model_dump_json())
    assert again.relative_paths == expected and again.angle_paths == []
    # a document written before the fields reads "not recorded"
    assert SeriesResult().relative_paths is None


def test_a_tied_path_repeating_another_is_one_curve():
    """A cubic ``cell.b``/``cell.c`` follow ``cell.a`` exactly: one curve."""
    a = [(4.150, 1e-4), (4.152, 1e-4)]
    s = _series({"phases.0.cell.a": a, "phases.0.cell.b": a,
                 "phases.0.cell.c": a})
    assert s.moved_paths() == ["phases.0.cell.a"]


# --------------------------------------------------------- moved_paths ---
def _series(rows: dict[str, list[tuple[float, float | None]]], *,
            status: list[str] | None = None, qpa=None,
            relative=(), angles=()) -> SeriesResult:
    n = len(next(iter(rows.values())))
    entries = []
    for i in range(n):
        params = [RefinedParameter(path=p, value=v[i][0], stderr=v[i][1])
                  for p, v in rows.items()]
        entries.append(SeriesEntry(index=i, label=f"p{i}", parameters=params,
                                   status=(status[i] if status else "converged")))
    return SeriesResult(entries=entries, relative_paths=list(relative),
                        angle_paths=list(angles))


def test_moved_paths_ranks_movement_against_each_paths_own_esd():
    """The issue's case: a cell edge does not outrank a scale by its size.

    ``a`` moves 0.002 Å on an esd of 1e-4 (20σ); ``scale`` moves 1e-5 on an
    esd of 1e-6 (10σ); ``w`` moves 5e-4 on an esd of 2e-4 (2.5σ, under the
    3σ default); ``zero`` does not move at all.
    """
    s = _series({
        "phases.0.cell.a": [(4.150, 1e-4), (4.151, 1e-4), (4.152, 1e-4)],
        "phases.0.scale": [(5.00e-4, 1e-6), (5.05e-4, 1e-6), (4.95e-4, 2e-6)],
        "instrument.profile.w": [(2.5e-3, 2e-4), (3.0e-3, 2e-4), (2.7e-3, 2e-4)],
        "instrument.zero_shift": [(0.008, 1e-4)] * 3,
    })
    assert s.moved_paths() == ["phases.0.cell.a", "phases.0.scale"]
    assert s.moved_paths(1) == ["phases.0.cell.a"]
    assert s.moved_paths(min_sigma=2.0) == [
        "phases.0.cell.a", "phases.0.scale", "instrument.profile.w"]
    assert s.moved_paths(min_sigma=0.0)[-1] == "instrument.zero_shift"


def test_a_path_without_an_esd_is_not_ranked():
    """No esd, no scale to rank on — left out, never ranked as zero or ∞."""
    s = _series({
        "phases.0.cell.a": [(4.150, 1e-4), (4.152, 1e-4)],
        "phases.0.lor_size": [(0.0, None), (0.5, None)],
    })
    assert s.moved_paths(min_sigma=0.0) == ["phases.0.cell.a"]


def test_the_movement_is_measured_on_points_that_are_measurements():
    """A diverged (quarantined) fit's values are not a measurement, so it moves
    nothing; a point whose own esd is missing moves nothing either."""
    s = _series({
        "phases.0.cell.a": [(4.150, 1e-4), (9.000, 1e-4), (4.150, 1e-4)],
        "phases.0.cell.c": [(4.160, 1e-4), (9.000, None), (4.160, 1e-4)],
    }, status=["converged", "diverged", "converged"])
    assert s.moved_paths(min_sigma=0.0) == ["phases.0.cell.a",
                                            "phases.0.cell.c"]
    assert s.moved_paths() == []


def test_a_step_path_is_not_ranked_and_an_angle_moves_modulo_a_turn():
    """The two facts the series recorded, used where the fences use them.

    A coordinate DOF's value is a step from where its fit began (WP-1333), so
    its spread is not a movement; a moment angle at +3.13 then −3.14 rad moved
    0.01 rad, not 6.27 (#604).
    """
    dof = "phases.0.atoms.0.dof.0"
    phi = "phases.0.atoms.0.moment.dof.1"
    s = _series({
        dof: [(0.0, 1e-4), (0.01, 1e-4), (-0.01, 1e-4)],
        phi: [(3.13, 0.01), (-3.14, 0.01), (3.12, 0.01)],
        "phases.0.atoms.0.x": [(0.10, 1e-4), (0.11, 1e-4), (0.10, 1e-4)],
    }, relative=[dof], angles=[phi])
    # x moved 0.01 on 1e-4 (100σ); φ's shortest covering arc is 3.12 →
    # 3.13 → −3.14 + 2π = 3.1432, 0.0232 rad on 0.01 (2.3σ)
    assert s.moved_paths(min_sigma=0.0) == ["phases.0.atoms.0.x", phi]
    assert s.moved_paths() == ["phases.0.atoms.0.x"]
    assert s.moved_paths(min_sigma=2.0 * math.pi / 0.01) == []
    assert s.moved_paths(min_sigma=2.2) == ["phases.0.atoms.0.x", phi]
    assert s.moved_paths(min_sigma=2.4) == ["phases.0.atoms.0.x"]


def test_a_weight_fraction_is_ranked_beside_the_parameters():
    """``qpa.<phase>`` carries a propagated esd, so it competes; an agreement
    index carries none and is never a candidate."""
    from rietx.schemas.results import (
        PhaseAgreement,
        PhaseQuantity,
        QuantitativePhaseAnalysis,
    )
    s = _series({"phases.0.cell.a": [(4.150, 1e-4), (4.1505, 1e-4)]})
    for e, (w, rb) in zip(s.entries, [(0.30, 4.0), (0.60, 9.0)], strict=True):
        e.qpa = QuantitativePhaseAnalysis(phases=[PhaseQuantity(
            name="LaB6", weight_fraction=w, weight_fraction_stderr=0.01,
            scale=1e-4, cell_mass=1.0, cell_volume=1.0, zmv=1.0)])
        e.phase_agreement = [PhaseAgreement(name="LaB6", r_bragg=rb)]
    assert s.moved_paths(min_sigma=0.0) == ["qpa.LaB6", "phases.0.cell.a"]


def test_moved_paths_returns_names_plot_trajectory_takes(tmp_path):
    """The issue's one line, run."""
    s = _series({
        "phases.0.cell.a": [(4.150, 1e-4), (4.151, 1e-4), (4.152, 1e-4)],
        "phases.0.scale": [(5.0e-4, 1e-6)] * 3,
    })
    paths = s.moved_paths(6)
    assert paths == ["phases.0.cell.a"]
    assert all(isinstance(p, str) for p in paths)
    fig = s.plot(paths, path=str(tmp_path / "moved.png"))
    assert fig is not None and (tmp_path / "moved.png").exists()


def test_moved_paths_refuses_a_meaningless_request():
    s = _series({"phases.0.cell.a": [(4.150, 1e-4), (4.151, 1e-4)]})
    with pytest.raises(ValueError, match="n"):
        s.moved_paths(0)
    with pytest.raises(ValueError, match="min_sigma"):
        s.moved_paths(min_sigma=-1.0)
