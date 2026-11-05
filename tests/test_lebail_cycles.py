"""WP-1542 task 7: a Le Bail partition repeats until the intensities stop moving.

The ruling is B11 of WP-2002 (``docs/wp/2002-batch/rulings.md``, 2026-10-19).
The fixture is issue #740's pattern as filed: synthetic Pnma LaMnO₃, CW neutron
2.4 Å, FWHM 0.5°, so its reflections overlap densely above 90° and its true cell
and true structure are known.  The ruling's yardstick is the true structure's
Rwp on the pattern, never a run of many cycles.

The domain test over real families is ``test_the_tolerance_meets_its_bar``.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import LEBAIL_INTENSITY_FLOOR, _settled_partition, compile_model
from rietx.optimize.cancel import CancelToken, RefinementCancelled
from rietx.optimize.least_squares import _cancel_check
from rietx.params.vector import ParameterTable
from rietx.refine import PAWLEY_SEED_CYCLES
from rietx.schemas.plan import StageSpec
from rietx.sequential import _collapse
from rietx.strategy.staged import Stage, resolve_plan
from tests.test_auto_background_seed import _neutron, _phase

GRID = np.arange(10.0, 150.0, 0.1)
LIMITS = (10.0, 150.0)
TRUE_CELL = {"a": 5.74, "b": 7.69, "c": 5.54}
CODE = "LEBAIL_CYCLES_AT_CAP"
TOL, CAP = Stage("x", []).lebail_tol, Stage("x", []).lebail_cycles
REFERENCE_CAP = 100_000

pytestmark = pytest.mark.xdist_group("lebail-cycles")


@pytest.fixture(scope="module")
def pattern() -> rx.PatternData:
    truth = rx.Refinement(rx.Structure(phases=[_phase(1.0)]), _neutron())
    y = np.asarray(truth.predict(GRID)) + 300.0 + 2.0 * GRID
    y = np.maximum(y + np.random.default_rng(1).normal(
        scale=np.sqrt(np.maximum(y, 1.0))), 0)
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


def _refinement(data: rx.PatternData) -> rx.Refinement:
    ins = _neutron()
    ins.background = rx.auto_background(data, two_theta_limits=LIMITS, seed=True).background
    return rx.Refinement(rx.Structure(phases=[_phase(1.0)]), ins)


def _plan(**fields):
    plan = resolve_plan("profile_only", "lebail")
    return dataclasses.replace(plan, stages=[dataclasses.replace(s, **fields)
                                             for s in plan.stages])


def _fit(data, **fields):
    ref = _refinement(data)
    return ref, ref.fit(data, mode="lebail", plan=_plan(**fields), telemetry=False)


def _cell_ppm(result) -> dict[str, float]:
    values = {p.path: p.value for p in result.parameters}
    return {axis: (values[f"phases.0.cell.{axis}"] - true) / true * 1e6
            for axis, true in TRUE_CELL.items()}


def _model(data, *, mode="lebail"):
    ref = _refinement(data)
    table = ParameterTable(ref.structure, ref.instrument)
    model = compile_model(ref.structure, ref.instrument, data, mode=mode,
                          moving_paths=set(table.moving_paths))
    return model, table.decode(table.x0())


def _plot(result, name):
    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / name))


@pytest.fixture(scope="module")
def fixed_three(pattern):
    return _fit(pattern, lebail_cycles=3, lebail_tol=0.0)


@pytest.fixture(scope="module")
def settled(pattern):
    return _fit(pattern)


def test_the_cell_of_a_settled_fit_is_the_true_one_and_three_cycles_miss_it(
        fixed_three, settled):
    """The evidence the ruling asked for is a known answer, never more cycles."""
    three, now = _cell_ppm(fixed_three[1]), _cell_ppm(settled[1])
    assert max(abs(v) for v in three.values()) > 30.0
    assert max(abs(v) for v in now.values()) < 8.0
    _plot(fixed_three[1], "lebail_cycles_three.png")
    _plot(settled[1], "lebail_cycles_settled.png")


def test_a_settled_fit_reaches_the_true_structure_and_three_cycles_do_not(
        pattern, fixed_three, settled):
    true = _refinement(pattern).fit(
        pattern, plan=rx.RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"])]),
        telemetry=False)
    assert fixed_three[1].statistics.rwp > 1.3 * true.statistics.rwp
    assert settled[1].statistics.rwp < 1.01 * true.statistics.rwp


def test_the_loop_stops_once_a_plain_cycle_moves_no_more_than_the_tolerance(pattern):
    """The share is rebuilt here from the intensities, on one more plain cycle."""
    tol = 1e-3
    model, values = _model(pattern)
    run, _ = model.lebail_update(values, n_cycles=10_000, tol=tol)
    area = sum(np.bincount(line.first, weights=line.w_line * line.mass,
                           minlength=model.phases[0].hkl_intensity.size)
               for line in model._partition_terms(values)[0])
    before = model.phases[0].hkl_intensity.copy()
    assert model.lebail_update(values, n_cycles=1) == (1, None)
    after = model.phases[0].hkl_intensity
    assert 1 < run < 10_000
    assert (area * np.abs(after - before)).sum() <= tol * (area * after).sum()


def _richardson_lucy(n=30, spacing=1.2):
    """Gaussians closer than their width, so plain repetition slows to a crawl."""
    grid = np.linspace(-3.0, n * spacing + 3.0, 400)
    shape = np.exp(-0.5 * (grid[:, None] - spacing * np.arange(n)) ** 2)
    data = shape @ (1.0 + 50.0 * np.random.default_rng(3).random(n))
    mass = shape.sum(axis=0)

    def cycle(x):
        curve = shape @ x
        new = x * (shape.T @ (data / curve)) / mass
        share = float((mass * np.abs(new - x)).sum() / (mass * new).sum())
        return new, share, float((data * np.log(curve)).sum() - curve.sum())

    return cycle, np.full(n, float(data.mean())), mass


def test_the_acceleration_changes_the_path_and_never_the_fixed_point():
    cycle, start, mass = _richardson_lucy()
    plain, moved, n_plain = start, 1.0, 0
    while moved > 1e-7:
        plain, moved, _ = cycle(plain)
        n_plain += 1
    fast, n_fast, met = _settled_partition(cycle, start, 100_000, 1e-7, mass)
    assert met
    assert n_fast * 5 < n_plain
    assert np.abs(mass * (fast - plain)).sum() <= 1e-4 * (mass * plain).sum()


@pytest.mark.parametrize("cap", [1, 2, 3, 4, 5, 6, 7, 100])
def test_the_loop_never_runs_past_its_cap(cap):
    cycle, start, mass = _richardson_lucy()
    calls = []

    def counted(x):
        calls.append(1)
        return cycle(x)

    _, run, met = _settled_partition(counted, start, cap, 1e-14, mass)
    assert run == len(calls) == cap
    assert not met


@pytest.mark.parametrize("cap", [1, 2])
def test_a_cycle_on_the_cap_that_meets_the_tolerance_is_settled(pattern, cap):
    """The count alone cannot say this: a run at the cap may have met the test."""
    model, values = _model(pattern)
    assert model.lebail_update(values, n_cycles=cap, tol=1e6) == (1, True)
    model, values = _model(pattern)
    assert model.lebail_update(values, n_cycles=cap, tol=1e-30) == (cap, False)
    _, start, mass = _richardson_lucy()
    shares = iter([1.0, 0.0])

    def last_meets(x):
        return x, next(shares), 0.0

    assert _settled_partition(last_meets, start, 2, 1e-3, mass)[1:] == (2, True)


def test_the_likelihood_never_falls_across_an_accepted_round():
    cycle, start, mass = _richardson_lucy()
    seen = []

    def watched(x):
        new, share, like = cycle(x)
        seen.append(like)
        return new, share, like

    settled, run, _ = _settled_partition(watched, start, 90, 1e-14, mass)
    # a round is three calls, and its first is the likelihood it starts from
    assert np.all(np.diff(seen[::3]) >= 0.0)
    assert run == 90 and cycle(settled)[2] >= seen[0]


def test_an_extrapolation_that_lands_below_zero_stays_on_the_floor():
    cycle, start, mass = _richardson_lucy()
    seen = []

    def watched(x):
        seen.append(x.min())
        return cycle(x)

    _settled_partition(watched, start, 300, 1e-14, mass)
    assert min(seen) >= LEBAIL_INTENSITY_FLOOR


def test_an_exact_overlap_keeps_the_ratio_it_started_with():
    """In a cubic cell 333 and 511 sit at one 2θ, so no data can split them.
    Extrapolating must not start to."""
    phase = rx.Phase(name="c", space_group="P m -3 m", scale=rx.Parameter(value=1.0),
                     cell=rx.Cell(a=rx.Parameter(value=14.0), b=rx.Parameter(value=14.0),
                                  c=rx.Parameter(value=14.0), alpha=rx.Parameter(value=90.0),
                                  beta=rx.Parameter(value=90.0), gamma=rx.Parameter(value=90.0)),
                     atoms=[rx.Atom(label="Fe", species="Fe", x=rx.Parameter(value=0.0),
                                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))])
    structure, ins = rx.Structure(phases=[phase]), _neutron()
    truth = rx.Refinement(structure, ins)
    grid = np.arange(10.0, 150.0, 0.1)
    data = rx.PatternData(two_theta=grid.tolist(),
                          intensity=(np.asarray(truth.predict(grid)) + 100.0).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="lebail",
                          moving_paths=set(table.moving_paths))
    cp = model.phases[0]
    hkl = [tuple(sorted(np.abs(row))) for row in cp.reflections.hkl.tolist()]
    i333, i511 = hkl.index((3, 3, 3)), hkl.index((1, 1, 5))
    cp.hkl_intensity = np.full(len(hkl), 10.0)
    cp.hkl_intensity[i511] = 37.0
    run, _ = model.lebail_update(table.decode(table.x0()), n_cycles=2000, tol=1e-9)
    assert run > 3
    assert cp.hkl_intensity[i511] / cp.hkl_intensity[i333] == pytest.approx(3.7, rel=1e-10)


def test_a_reflection_falling_to_the_floor_does_not_hold_the_loop_open(pattern):
    """Its own relative change stays large long after the pattern has settled,
    so the test weights by the counts a reflection lays on the pattern."""
    model, values = _model(pattern)
    run, _ = model.lebail_update(values, n_cycles=CAP, tol=TOL)
    assert run > 3
    before = model.phases[0].hkl_intensity.copy()
    model.lebail_update(values, n_cycles=1)
    after = model.phases[0].hkl_intensity
    assert run < CAP
    assert float(np.max(np.abs(after - before) / before)) > 10 * TOL


@pytest.mark.parametrize("cycles", [0, 1, 3, 7])
def test_tolerance_zero_runs_exactly_the_count(pattern, cycles):
    model, values = _model(pattern)
    assert model.lebail_update(values, n_cycles=cycles, tol=0.0) == (cycles, None)


def test_a_cancel_stops_a_partition_between_cycles_and_changes_nothing(pattern):
    model, values = _model(pattern)
    before = model.phases[0].hkl_intensity.copy()
    token = CancelToken()
    reads = []

    def check():
        reads.append(1)
        if len(reads) == 5:
            token.cancel()
        _cancel_check(token, "s")()

    with pytest.raises(RefinementCancelled):
        model.lebail_update(values, n_cycles=CAP, tol=TOL, check=check)
    assert len(reads) == 5
    assert np.array_equal(model.phases[0].hkl_intensity, before)


def test_a_fit_hands_its_cancel_to_the_partition(pattern, monkeypatch):
    """The partition runs before the solve, so it is the first thing to read it."""
    def no_solve(*args, **kwargs):
        raise AssertionError("the partition ran through a set token")

    monkeypatch.setattr(sys.modules["rietx.refine"], "run_least_squares", no_solve)
    token = CancelToken()
    token.cancel()
    with pytest.raises(RefinementCancelled):
        _refinement(pattern).fit(pattern, mode="lebail", plan=_plan(), cancel=token,
                                 telemetry=False)


def test_the_stage_records_each_partition_it_ran(settled):
    for stage in settled[1].stages:
        assert len(stage.lebail_cycles_run) == 2
        assert all(1 <= n < CAP for n in stage.lebail_cycles_run)
    first = settled[1].stages[0]
    assert first.lebail_cycles_run[0] > settled[1].stages[-1].lebail_cycles_run[-1]


def test_a_rietveld_stage_ran_no_partition_and_a_pawley_seed_ran_one(pattern):
    plan = rx.RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"])])
    rietveld = _refinement(pattern).fit(pattern, plan=plan, telemetry=False)
    assert all(s.lebail_cycles_run == [] for s in rietveld.stages)
    pawley = _refinement(pattern).fit(pattern, mode="pawley", plan=plan, telemetry=False)
    assert [s.lebail_cycles_run for s in pawley.stages][0] == [PAWLEY_SEED_CYCLES]
    assert all(s.lebail_cycles_run == [] for s in pawley.stages[1:])
    assert all(s.lebail_settled is None for s in rietveld.stages + pawley.stages)


def test_a_pawley_stage_may_ask_for_fewer_seed_cycles_than_the_ceiling(pattern):
    plan = rx.RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"],
                                           lebail_cycles=0)])
    result = _refinement(pattern).fit(pattern, mode="pawley", plan=plan, telemetry=False)
    assert result.stages[0].lebail_cycles_run == [0]


def test_the_pawley_answer_does_not_read_its_seed_count(pattern, monkeypatch):
    """Why the seed stays at three cycles: the joint solve refines the intensities
    anyway, so a longer seed costs a validation fit and buys nothing."""
    plan = resolve_plan("profile_only", "pawley")
    three = _refinement(pattern).fit(pattern, mode="pawley", plan=plan, telemetry=False)
    monkeypatch.setattr(sys.modules["rietx.refine"], "PAWLEY_SEED_CYCLES", 300)
    settled = _refinement(pattern).fit(pattern, mode="pawley", plan=plan, telemetry=False)
    assert settled.stages[0].lebail_cycles_run == [300]
    rows = {p.path: p for p in settled.parameters}
    for row in three.parameters:
        if row.stderr_uncorrected:
            assert abs(row.value - rows[row.path].value) <= 0.1 * row.stderr_uncorrected, row.path


def test_a_cap_that_cut_the_last_partition_short_says_so(pattern):
    _, result = _fit(pattern, lebail_cycles=5)
    found = [d for d in result.diagnostics if d.code == CODE]
    assert len(found) == 1
    assert found[0].level == "warning"
    assert "5" in found[0].message
    assert found[0].suggestion
    assert result.stages[-1].lebail_settled is False


def test_a_count_the_caller_fixed_says_nothing(fixed_three, settled):
    assert not [d for d in fixed_three[1].diagnostics if d.code == CODE]
    assert not [d for d in settled[1].diagnostics if d.code == CODE]
    assert fixed_three[1].stages[-1].lebail_settled is None
    assert settled[1].stages[-1].lebail_settled is True


def test_an_old_node_replays_its_fixed_three_cycles(pattern):
    """A node written before the field carries neither number, so the frozen
    defaults are what it ran."""
    assert (rx.NodeAction(kind="stage").lebail_cycles,
            rx.NodeAction(kind="stage").lebail_tol) == (3, 0.0)
    ref = _refinement(pattern)
    ref.fit(pattern, mode="lebail", plan=rx.RefinementPlan(stages=[
        Stage("bkg", ["instrument.background.*"], max_iter=10, lebail_cycles=4,
              lebail_tol=0.0)]), telemetry=False)
    picked = ref.history.order[-1]
    assert ref.history[picked].action.lebail_tol == 0.0
    result = ref.cherry_pick(picked, pattern)
    assert result.stages[-1].lebail_cycles_run == [4, 4]


def test_the_settings_cross_every_copy_of_a_stage():
    stage = Stage("s", ["phases.*.cell.*"], lebail_cycles=11, lebail_tol=2e-3)
    assert (StageSpec.from_stage(stage).lebail_cycles,
            StageSpec.from_stage(stage).lebail_tol) == (11, 2e-3)
    back = StageSpec.from_stage(stage).to_stage()
    assert (back.lebail_cycles, back.lebail_tol) == (11, 2e-3)
    plan = rx.RefinementPlan(stages=[stage])
    closing = plan.run_stages()[-1]
    assert (closing.lebail_cycles, closing.lebail_tol) == (11, 2e-3)
    warm = _collapse(plan).stages[0]
    assert (warm.lebail_cycles, warm.lebail_tol) == (11, 2e-3)


def test_a_collapsed_plan_keeps_a_stop_whichever_stage_held_it():
    """The collapsed cap is the plan's largest.  Taking the tolerance of a last
    stage that fixed its count would run that whole cap in plain cycles."""
    fixed = Stage("fixed", [], lebail_cycles=3, lebail_tol=0.0)
    warm = _collapse(rx.RefinementPlan(stages=[Stage("a", []), fixed])).stages[0]
    assert (warm.lebail_cycles, warm.lebail_tol) == (CAP, TOL)
    warm = _collapse(rx.RefinementPlan(stages=[fixed, fixed])).stages[0]
    assert (warm.lebail_cycles, warm.lebail_tol) == (3, 0.0)


def test_the_two_mirrors_of_a_stage_default_agree():
    spec, stage = StageSpec(name="x", turn_on=[]), Stage("x", [])
    assert (spec.lebail_cycles, spec.lebail_tol) == (stage.lebail_cycles, stage.lebail_tol)


def _issue_740(scale):
    truth = rx.Refinement(rx.Structure(phases=[_phase(scale)]), _neutron())
    y = np.asarray(truth.predict(GRID)) + 300.0 + 2.0 * GRID
    y = np.maximum(y + np.random.default_rng(1).normal(scale=np.sqrt(np.maximum(y, 1.0))), 0)
    data = rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())
    ins = _neutron()
    ins.background = rx.auto_background(data, two_theta_limits=LIMITS, seed=True).background
    return data, rx.Structure(phases=[_phase(scale)]), ins, None


def _corundum():
    from tests.test_acceptance_srm676a import DATA, qarr_instrument
    p = rx.Parameter
    ins = qarr_instrument()
    ins.profile.w.value = 0.01
    phase = rx.Phase(
        name="corundum", space_group="R -3 c:H",
        cell=rx.Cell(a=p(value=4.7588, min=1.0), b=p(value=4.7588, min=1.0),
                     c=p(value=12.992, min=1.0), alpha=p(value=90.0), beta=p(value=90.0),
                     gamma=p(value=120.0)),
        atoms=[rx.Atom(label="X", species="Al", x=p(value=0.0), y=p(value=0.0), z=p(value=0.0))],
        lor_size=p(value=0.02, min=0.0))
    return rx.read_pattern(DATA / "corundum.prn"), rx.Structure(phases=[phase]), ins, None


def _nac():
    from tests.test_acceptance_nac import LIMITS as nac_limits
    from tests.test_acceptance_nac import build_nac_inputs
    data, structure, ins = build_nac_inputs()
    return data, structure, ins, nac_limits


def _fap():
    from tests.test_acceptance_fap import build_fap_inputs
    return (*build_fap_inputs()[:3], None)


def _lamno3():
    from rietx.schemas.instrument import BackgroundChebyshev
    root = Path(__file__).parent / "data"
    ins = rx.Instrument.constant_wavelength_neutron(1.5403, fwhm_deg=0.5)
    ins.background = BackgroundChebyshev.with_terms(6)
    return (rx.read_pattern(root / "gsas2_bt1_lamno3_50K.gsas"),
            rx.Structure.from_cif(str(root / "gsas2_bt1_lamno3.cif")), ins, None)


FAMILIES = {
    "issue-740": lambda: _issue_740(1.0),           # peaks 1100 times the pedestal
    "issue-740-weak": lambda: _issue_740(0.02),     # peaks 22 times it
    "corundum": _corundum,                          # lab, Cu Kα doublet
    "fap": _fap,                                    # lab, 329 reflections
    "nac": _nac,                                    # synchrotron
    "lamno3": _lamno3,                              # real neutron, 296 reflections
}


def _domain_fit(family, tol):
    data, structure, ins, limits = FAMILIES[family]()
    ref = rx.Refinement(structure, ins)
    plan = resolve_plan("profile_only", "lebail")
    plan = dataclasses.replace(plan, stages=[
        dataclasses.replace(s, lebail_cycles=REFERENCE_CAP if tol < TOL else CAP, lebail_tol=tol)
        for s in plan.stages])
    fitted = ref.fit(data, mode="lebail", plan=plan, two_theta_limits=limits, telemetry=False)
    return ref, fitted, data, limits


@pytest.mark.slow
@pytest.mark.parametrize("family", FAMILIES)
def test_the_tolerance_meets_its_bar(family):
    """Bar 1 of ``tests/test_window_domain.py``: at the fit's own answer, a partition
    stopped at the tolerance against one carried on to a tenth of it, in units of
    each point's σ.  The cap holds twice the dearest partition.

    The first partition here is not a formality.  ``ref._model`` is the result's
    fresh compile, and ``_final_compile`` carries the intensities onto its windows
    unpartitioned, so a one-channel window change splits a near-overlap differently
    (1.6 σ on #740's pattern, 2 cycles on the frozen compile and 611 on this one).
    That gap is the compile's and no tolerance closes it."""
    ref, result, _, _ = _domain_fit(family, TOL)
    _plot(result, f"lebail_cycles_{family}.png")
    model = ref._model
    table = ParameterTable(ref.structure, ref.instrument)
    values = table.decode(table.x0())
    model.lebail_update(values, n_cycles=CAP, tol=TOL)
    shipped = np.asarray(model.evaluate(values))
    model.lebail_update(values, n_cycles=REFERENCE_CAP, tol=TOL * 0.1)
    assert (np.abs(shipped - np.asarray(model.evaluate(values))) / model.sigma).max() <= 0.1
    assert max(n for stage in result.stages for n in stage.lebail_cycles_run) * 2 <= CAP
    assert all(stage.lebail_settled for stage in result.stages)


@pytest.mark.slow
@pytest.mark.parametrize("family", [f for f in FAMILIES if f != "lamno3"])
def test_the_answer_does_not_read_the_tolerance(family):
    """Bar 2 of ``tests/test_window_domain.py``: 0.1 plain esd off the background,
    each arm polished by the same all-free fits, because on the weak #740 pattern
    the plan alone ends 0.4 esd apart at two settled tolerances.  LaMnO₃ takes
    minutes a fit here, so its arm is the WP's measurement and not a test row."""
    arms = []
    for tol in (TOL, TOL * 1e-1):
        ref, result, data, limits = _domain_fit(family, tol)
        for _ in range(3):
            stage = Stage("all", [p.path for p in result.parameters],
                          lebail_cycles=REFERENCE_CAP, lebail_tol=tol)
            result = ref.fit(data, mode="lebail", plan=rx.RefinementPlan(stages=[stage]),
                             two_theta_limits=limits, telemetry=False)
        arms.append({p.path: (p.value, p.stderr_uncorrected) for p in result.parameters})
    shipped, tight = arms
    for path, (value, esd) in shipped.items():
        if ".background." not in path and esd:
            assert abs(value - tight[path][0]) <= 0.1 * esd, path
