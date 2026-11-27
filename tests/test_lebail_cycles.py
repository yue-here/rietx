"""WP-2316: a Le Bail stage extracts its intensities once per least-squares cycle.

The established programs extract between the cycles of one refinement
(``docs/practice.md`` § Structure-free fitting), and rietx follows them: an
extraction at a stage's start, then one inside the solve after every accepted
iteration, ``Stage.lebail_cycles`` accelerated cycles each time
(``least_squares._LeBailRefresh``, ``lm.minimize``'s ``refresh``).  It replaced
WP-1542's partition settled to a tolerance at a frozen model.

The fixture is issue #740's pattern as filed: synthetic Pnma LaMnO₃, CW neutron
2.4 Å, FWHM 0.5°, so its reflections overlap densely above 90° and its true cell
and true structure are known.  The yardstick is the true structure's Rwp on the
pattern and the true cell, never a run of many cycles (B11 of WP-2002).

The domain tests over real families are ``test_an_extraction_at_the_answer_meets_its_bar``
and ``test_the_answer_does_not_read_the_count``.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import LEBAIL_INTENSITY_FLOOR, _accelerated_partition, compile_model
from rietx.optimize import lm
from rietx.optimize.cancel import CancelToken, RefinementCancelled
from rietx.optimize.least_squares import _cancel_check
from rietx.params.vector import ParameterTable
from rietx.refine import PAWLEY_SEED_CYCLES
from rietx.schemas.plan import CLOSING_WINDOW_TOL, StageSpec
from rietx.schemas.results import StageResult
from rietx.sequential import _collapse
from rietx.strategy.staged import Stage, resolve_plan
from tests.test_auto_background_seed import _neutron, _phase

GRID = np.arange(10.0, 150.0, 0.1)
LIMITS = (10.0, 150.0)
TRUE_CELL = {"a": 5.74, "b": 7.69, "c": 5.54}
CYCLES = Stage("x", []).lebail_cycles
REFERENCE_CYCLES = 100

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
def shipped(pattern):
    return _fit(pattern)


def test_the_cell_of_a_fit_is_the_true_one(shipped):
    """The evidence the ruling asked for is a known answer, never more cycles.
    The settled partition WP-2316 replaced landed within 6.3 ppm here."""
    ppm = _cell_ppm(shipped[1])
    assert max(abs(v) for v in ppm.values()) < 8.0
    _plot(shipped[1], "lebail_cycles_shipped.png")


def test_a_fit_reaches_the_true_structure(pattern, shipped):
    true = _refinement(pattern).fit(
        pattern, plan=rx.RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"])]),
        telemetry=False)
    assert shipped[1].statistics.rwp < 1.01 * true.statistics.rwp


def test_every_stage_converges_rather_than_spending_its_budget(shipped):
    """One plain cycle an iteration ran every stage of this pattern to its
    budget: a partition moves a little a plain cycle where peaks overlap."""
    assert all(stage.status == "converged" for stage in shipped[1].stages)


def _richardson_lucy(n=30, spacing=1.2):
    """Gaussians closer than their width, so plain repetition slows to a crawl."""
    grid = np.linspace(-3.0, n * spacing + 3.0, 400)
    shape = np.exp(-0.5 * (grid[:, None] - spacing * np.arange(n)) ** 2)
    data = shape @ (1.0 + 50.0 * np.random.default_rng(3).random(n))
    mass = shape.sum(axis=0)

    def cycle(x):
        curve = shape @ x
        new = x * (shape.T @ (data / curve)) / mass
        return new, float((data * np.log(curve)).sum() - curve.sum())

    return cycle, np.full(n, float(data.mean())), mass


def test_the_acceleration_changes_the_path_and_never_the_fixed_point():
    cycle, start, mass = _richardson_lucy()
    plain = start
    for _ in range(20_000):
        plain, _ = cycle(plain)
    fast = _accelerated_partition(cycle, start, 2_000, mass)
    assert np.abs(mass * (fast - plain)).sum() <= 1e-4 * (mass * plain).sum()
    slow = start
    for _ in range(2_000):
        slow, _ = cycle(slow)
    assert np.abs(mass * (slow - plain)).sum() > 10 * np.abs(mass * (fast - plain)).sum()


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 5, 6, 7, 100])
def test_the_count_is_the_cycles_run(n):
    cycle, start, mass = _richardson_lucy()
    calls = []

    def counted(x):
        calls.append(1)
        return cycle(x)

    _accelerated_partition(counted, start, n, mass)
    assert len(calls) == n


def test_the_likelihood_never_falls_across_an_accepted_round():
    cycle, start, mass = _richardson_lucy()
    seen = []

    def watched(x):
        new, like = cycle(x)
        seen.append(like)
        return new, like

    settled = _accelerated_partition(watched, start, 90, mass)
    # a round is three calls, and its first is the likelihood it starts from
    assert np.all(np.diff(seen[::3]) >= 0.0)
    assert cycle(settled)[1] >= seen[0]


def test_an_extrapolation_that_lands_below_zero_stays_on_the_floor():
    cycle, start, mass = _richardson_lucy()
    seen = []

    def watched(x):
        seen.append(x.min())
        return cycle(x)

    _accelerated_partition(watched, start, 300, mass)
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
    assert model.lebail_update(table.decode(table.x0()), n_cycles=2000, accelerate=True) == 2000
    assert cp.hkl_intensity[i511] / cp.hkl_intensity[i333] == pytest.approx(3.7, rel=1e-10)


@pytest.mark.parametrize("accelerate", [False, True])
@pytest.mark.parametrize("cycles", [0, 1, 3, 7])
def test_an_update_runs_exactly_the_count(pattern, cycles, accelerate):
    model, values = _model(pattern)
    assert model.lebail_update(values, n_cycles=cycles, accelerate=accelerate) == cycles


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
        model.lebail_update(values, n_cycles=CYCLES, accelerate=True, check=check)
    assert len(reads) == 5
    assert np.array_equal(model.phases[0].hkl_intensity, before)


def test_a_fit_hands_its_cancel_to_the_partition(pattern, monkeypatch):
    """The first extraction runs before the solve, so it is the first thing to
    read it."""
    def no_solve(*args, **kwargs):
        raise AssertionError("the partition ran through a set token")

    monkeypatch.setattr(sys.modules["rietx.refine"], "run_least_squares", no_solve)
    token = CancelToken()
    token.cancel()
    with pytest.raises(RefinementCancelled):
        _refinement(pattern).fit(pattern, mode="lebail", plan=_plan(), cancel=token,
                                 telemetry=False)


def test_the_stage_records_its_initial_and_its_in_solve_cycles(shipped):
    """Every extraction runs the whole count, so the in-solve sum is a multiple."""
    for stage in shipped[1].stages:
        first, inside = stage.lebail_cycles_run
        assert first == CYCLES
        assert inside % CYCLES == 0 and 0 < inside


def test_a_rietveld_stage_ran_no_partition_and_a_pawley_seed_ran_one(pattern):
    plan = rx.RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"])])
    rietveld = _refinement(pattern).fit(pattern, plan=plan, telemetry=False)
    assert all(s.lebail_cycles_run == [] for s in rietveld.stages)
    pawley = _refinement(pattern).fit(pattern, mode="pawley", plan=plan, telemetry=False)
    assert [s.lebail_cycles_run for s in pawley.stages][0] == [PAWLEY_SEED_CYCLES]
    assert all(s.lebail_cycles_run == [] for s in pawley.stages[1:])


def test_a_pawley_stage_may_ask_for_fewer_seed_cycles_than_the_ceiling(pattern):
    plan = rx.RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"],
                                           lebail_cycles=0)])
    result = _refinement(pattern).fit(pattern, mode="pawley", plan=plan, telemetry=False)
    assert result.stages[0].lebail_cycles_run == [0]


def test_the_pawley_answer_does_not_read_its_seed_count(pattern, monkeypatch):
    """Why the seed stays at three cycles: the joint solve refines the intensities
    anyway, so a longer seed costs a validation fit and buys nothing.  The
    stage's count is the seed's ceiling, so it is raised past both."""
    plan = resolve_plan("profile_only", "pawley")
    plan = dataclasses.replace(plan, stages=[dataclasses.replace(s, lebail_cycles=300)
                                             for s in plan.stages])
    ref = _refinement(pattern)
    three = ref.fit(pattern, mode="pawley", plan=plan, telemetry=False)
    intensities = ref._model.phases[0].hkl_intensity
    monkeypatch.setattr(sys.modules["rietx.refine"], "PAWLEY_SEED_CYCLES", 300)
    ref = _refinement(pattern)
    settled = ref.fit(pattern, mode="pawley", plan=plan, telemetry=False)
    assert settled.stages[0].lebail_cycles_run == [300]
    assert np.abs(ref._model.phases[0].hkl_intensity - intensities).max() <= 1e-6 * intensities.max()
    rows = {p.path: p for p in settled.parameters}
    for row in three.parameters:
        if row.stderr_uncorrected:
            assert abs(row.value - rows[row.path].value) <= 0.1 * row.stderr_uncorrected, row.path


class _Rising:
    """A refresh that raises S by more than a step can take back: the residual's
    second row is out of the step's reach and grows a call."""

    def __init__(self):
        self.target, self.drift, self.calls, self.restored = 0.0, 1.0, 0, False
        self._kept = (self.target, self.drift)

    def __call__(self, x):
        self.calls += 1
        self.target += 1.0
        self.drift += 1.0

    def keep(self):
        self._kept = (self.target, self.drift)

    def restore(self):
        self.target, self.drift = self._kept
        self.restored = True


def _solve(refresh, max_nfev=200):
    def residual(x):
        return np.array([x[0] - refresh.target, refresh.drift])

    return lm.minimize(residual, lambda x: np.array([[1.0], [0.0]]), np.array([5.0]),
                       lo=np.array([-np.inf]), hi=np.array([np.inf]), refresh=refresh,
                       max_nfev=max_nfev)


class _Settling(_Rising):
    """A refresh that raises S on every call while it settles: the target and
    the unreachable row halve their distance to 1 a call, so S climbs to its
    limit from below."""

    def __call__(self, x):
        self.calls += 1
        self.target = 0.5 * (self.target + 1.0)
        self.drift = 0.5 * (self.drift + 1.0)


def test_a_refresh_that_raises_s_converges_at_the_fixed_point():
    """A converged stage returns the fixed point, never the lowest S it held:
    the extraction raises a likelihood, not S (WP-2316)."""
    refresh = _Settling()
    out = _solve(refresh)
    assert out.status == 1 and refresh.calls > lm._CONVERGED_RUNS
    assert not refresh.restored
    assert out.x[0] == pytest.approx(1.0, abs=1e-4)


def test_a_refresh_that_never_settles_returns_the_lowest_state_unconverged():
    """A walk ends on the budget, status 0, at the lowest S the solve held."""
    refresh = _Rising()
    out = _solve(refresh, max_nfev=40)
    assert out.status == 0 and out.termination == "max_nfev"
    assert refresh.restored and (refresh.target, refresh.drift) == (0.0, 1.0)
    assert out.x[0] == pytest.approx(0.0) and out.cost == pytest.approx(0.5)


class _Exploding(_Rising):
    """A refresh whose third call leaves the residual not finite."""

    def __call__(self, x):
        super().__call__(x)
        if self.calls == 3:
            self.drift = np.nan


def test_a_refresh_that_leaves_the_residual_not_finite_stops_the_solve():
    """No LinAlgError: the solve stops, status −1, at its lowest state."""
    refresh = _Exploding()
    out = _solve(refresh)
    assert out.status == -1 and out.termination == "non_finite_residual"
    assert refresh.restored and np.isfinite(out.cost)
    assert out.x[0] == pytest.approx(0.0) and out.cost == pytest.approx(0.5)


def test_an_old_node_cherry_picks_the_default_count(pattern):
    """A node written before WP-2316 extracted between solves, a count no stage
    runs any more, so a cherry-pick takes today's default; a new node's own
    count is what its cherry-pick runs."""
    old = rx.NodeAction(kind="stage")
    assert (old.lebail_extraction, old.lebail_cycles) == ("between_solves", 3)
    ref = _refinement(pattern)
    ref.fit(pattern, mode="lebail", plan=rx.RefinementPlan(stages=[
        Stage("bkg", ["instrument.background.*"], max_iter=10, lebail_cycles=4)]),
        telemetry=False)
    picked = ref.history.order[-1]
    action = ref.history[picked].action
    assert (action.lebail_extraction, action.lebail_cycles) == ("per_iteration", 4)
    assert ref.cherry_pick(picked, pattern).stages[-1].lebail_cycles_run[0] == 4
    stored = action.model_dump(mode="json")
    for key in ("lebail_extraction", "lebail_tol"):
        stored.pop(key)
    stored["lebail_cycles"] = 25_000
    object.__setattr__(ref.history[picked], "action", rx.NodeAction.model_validate(stored))
    assert ref.cherry_pick(picked, pattern).stages[-1].lebail_cycles_run[0] == CYCLES


def test_the_vanished_fields_of_a_stored_stage_and_result_are_dropped(shipped):
    spec = StageSpec.model_validate({"name": "x", "turn_on": [], "lebail_tol": 1e-7})
    assert "lebail_tol" not in spec.model_dump()
    stored = shipped[1].stages[0].model_dump(mode="json")
    stored["lebail_settled"] = True
    assert "lebail_settled" not in StageResult.model_validate(stored).model_dump()


def test_the_settings_cross_every_copy_of_a_stage():
    stage = Stage("s", ["phases.*.cell.*"], lebail_cycles=11)
    assert StageSpec.from_stage(stage).lebail_cycles == 11
    assert StageSpec.from_stage(stage).to_stage().lebail_cycles == 11
    plan = rx.RefinementPlan(stages=[stage])
    assert plan.run_stages()[-1].lebail_cycles == 11
    assert _collapse(plan).stages[0].lebail_cycles == 11


def test_a_collapsed_plan_runs_the_largest_count():
    fixed = Stage("fixed", [], lebail_cycles=3)
    assert _collapse(rx.RefinementPlan(stages=[Stage("a", []), fixed])).stages[0].lebail_cycles \
        == CYCLES
    assert _collapse(rx.RefinementPlan(stages=[fixed, fixed])).stages[0].lebail_cycles == 3


def test_the_two_mirrors_of_a_stage_default_agree():
    assert StageSpec(name="x", turn_on=[]).lebail_cycles == Stage("x", []).lebail_cycles == 10


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



def _domain_fit(family, cycles):
    data, structure, ins, limits = FAMILIES[family]()
    ref = rx.Refinement(structure, ins)
    plan = resolve_plan("profile_only", "lebail")
    # measured behind the closing stage, declared since WP-2222
    plan = dataclasses.replace(plan, closing_window_tol=CLOSING_WINDOW_TOL, stages=[
        dataclasses.replace(s, lebail_cycles=cycles) for s in plan.stages])
    fitted = ref.fit(data, mode="lebail", plan=plan, two_theta_limits=limits, telemetry=False)
    return ref, fitted, data, limits


@pytest.mark.slow
@pytest.mark.parametrize("family", list(FAMILIES))
def test_an_extraction_at_the_answer_meets_its_bar(family):
    """Bar 1 of ``tests/test_window_domain.py``: at the fit's own answer, the
    shipped curve against one whose extraction is carried on for
    ``REFERENCE_CYCLES`` more cycles, in units of each point's σ.  The answer is
    the joint fixed point to the solve's ftol, so what is left is the
    intensities' share of that stop.

    ``ref._model`` is the result's fresh compile, and ``_final_compile`` carries
    the intensities onto its windows, so the reference is taken on that
    compile from the intensities it carries."""
    ref, result, _, _ = _domain_fit(family, CYCLES)
    _plot(result, f"lebail_cycles_{family}.png")
    assert all(stage.status == "converged" for stage in result.stages)
    model = ref._model
    table = ParameterTable(ref.structure, ref.instrument)
    values = table.decode(table.x0())
    shipped = np.asarray(model.evaluate(values))
    model.lebail_update(values, n_cycles=REFERENCE_CYCLES, accelerate=True)
    assert (np.abs(shipped - np.asarray(model.evaluate(values))) / model.sigma).max() <= 0.1


@pytest.mark.slow
@pytest.mark.parametrize("family", [f for f in FAMILIES if f != "lamno3"])
def test_the_answer_does_not_read_the_count(family):
    """Bar 2 of ``tests/test_window_domain.py``: 0.1 plain esd off the background
    between the shipped count and ``REFERENCE_CYCLES``, each arm polished by the
    same all-free fits.  LaMnO₃ takes minutes a fit here, so its arm is the WP's
    measurement and not a test row."""
    arms = []
    for cycles in (CYCLES, REFERENCE_CYCLES):
        ref, result, data, limits = _domain_fit(family, cycles)
        for _ in range(3):
            stage = Stage("all", [p.path for p in result.parameters], lebail_cycles=cycles)
            result = ref.fit(data, mode="lebail", plan=rx.RefinementPlan(stages=[stage]),
                             two_theta_limits=limits, telemetry=False)
        arms.append({p.path: (p.value, p.stderr_uncorrected) for p in result.parameters})
    shipped, reference = arms
    for path, (value, esd) in shipped.items():
        if ".background." not in path and esd:
            assert abs(value - reference[path][0]) <= 0.1 * esd, path
