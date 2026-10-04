"""WP-1301 — a phase the data cannot see is *held* for the stage, not bounded.

The mechanism WP-1110 shipped bounds the symptom: an invisible phase's cell
gets a per-stage window, so it walks quietly instead of running to 39 293 Å.
It still walks, and the solver still spends its budget walking it — measured on
a real in-situ ramp, 27 % of a 34.7 min run went into a CaF₂ cell while the
phase was absent, and reproducing the agent's own 13 sub-onset patterns took
1638 iterations with the bounds it had added and did not finish in 13 minutes
without them.

So the flat direction is removed rather than fenced: at stage compile, every
free structural parameter of a phase below ``PHASE_SUPPORT_SIGMA`` is held for
that stage. The phase's **scale stays free**, which is how it can still appear;
if it does appear while the stage solves, the hold is lifted and the stage
solves once more so the phase is refined in the pattern where it appears rather
than one later.

``tests/test_absent_phase.py`` holds the window's own tests and the fixtures
this file reuses; here the subject is the hold, its record and its message.
The counter-example — a supported trace phase, which must never be held — is in
``tests/test_acceptance_qpa_roundrobin.py``, because it reads that suite's
shared fixture and xdist unions the ``xdist_group`` marks on an item.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Refinement
from rietx.model.forward import PHASE_SUPPORT_SIGMA, compile_model
from rietx.params.vector import ParameterTable
from rietx.refine import _unsupported_phase_paths
from rietx.schemas.plan import PlanSpec, StageSpec
from rietx.schemas.structure import Structure
from tests.test_absent_phase import _absent_phase_inputs
from tests.test_refine_synthetic import TRUE_A, synthesize
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("held-phase")

OUT = __import__("pathlib").Path(__file__).parent / "output"


@pytest.fixture(scope="module")
def held_fit():
    """The absent-phase fixture, refined under the default plan."""
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    return ref, ref.fit(synthesize(), plan="mccusker_default")


# ----------------------------------------------------------------------
# what is held
# ----------------------------------------------------------------------
def test_the_hold_is_the_measurement_projected_not_a_second_opinion(held_fit):
    """``StageResult.held`` is set-equal to the paths the rule names.

    One measurement (``CompiledModel.phase_support``) projected onto the record,
    the way ``staged.bound_findings`` feeds both ``BOUND_HIT`` and ``at_bound``
    (WP-1076).  Re-deriving the set here would pass whatever the code did.
    """
    ref, result = held_fit
    held = {p for stage in result.stages for p in stage.held}
    assert held, "the absent phase's structural parameters were never held"

    # the same question asked of the same authority, on the fit's own model
    model = compile_model(ref.structure, ref.instrument, synthesize(),
                          mode="rietveld")
    table = ParameterTable(ref.structure, ref.instrument)
    table.set_vary(sorted(held), True)
    assert set(_unsupported_phase_paths(model, table)) == held


def test_the_phases_own_scale_is_never_held(held_fit):
    """Holding it would make the hold permanent, which it must never be.

    A phase reaches the pattern only through ``scale × |F|² × profile``, so the
    scale is the one direction that is *not* flat when the phase is invisible —
    and the only way it can climb back out of the noise.
    """
    _, result = held_fit
    for stage in result.stages:
        assert not [p for p in stage.held if p.endswith(".scale")], stage.name


def test_only_the_invisible_phase_is_held(held_fit):
    """The phase that is really there refines exactly as it did before."""
    ref, result = held_fit
    for stage in result.stages:
        assert all(p.startswith("phases.1.") for p in stage.held), stage.name
    assert result.statistics.rwp < 0.05
    assert ref.structure.phases[0].cell.a.value == pytest.approx(TRUE_A, abs=2e-4)


def test_a_held_value_is_the_one_that_was_handed_in(held_fit):
    """Not a walk that stopped somewhere; the number the caller gave.

    Under the window alone the same fit left this cell at 4.78 Å — inside the
    physical range, and still not a measurement.  Held, it is bit-for-bit the
    5.2 Å the fixture declared, which is the only value a reader can interpret.
    """
    ref, _ = held_fit
    assert ref.structure.phases[1].cell.a.value == 5.2


def test_held_and_freed_are_disjoint(held_fit):
    """The two together say exactly what refined in each stage."""
    _, result = held_fit
    for stage in result.stages:
        assert not set(stage.freed) & set(stage.held), stage.name


def test_a_held_parameter_is_not_reported_as_a_refined_one(held_fit):
    """``RefinementResult.parameters`` is what the fit measured.

    A held path was not in the free vector, has no esd and moved nowhere, so it
    is absent rather than present with a number beside it.
    ``PHASE_UNCONSTRAINED`` still names it in ``where``.
    """
    _, result = held_fit
    held = {p for stage in result.stages for p in stage.held}
    reported = {p.path for p in result.parameters}
    assert held and not (held & reported)


def test_the_hold_does_not_survive_into_the_working_state(held_fit):
    """A hold is one stage's answer about the data, not an edit to the plan.

    If it leaked into the recorded free set, the phase would stay unrefined in
    the very pattern where it appears — the failure the release rule exists to
    prevent, one call further out.
    """
    ref, result = held_fit
    held = {p for stage in result.stages for p in stage.held}
    rows = {r.path: r for r in ref.parameters()}
    for path in held:
        assert rows[path].vary, f"{path} came back fixed"


# ----------------------------------------------------------------------
# a fit with nothing to hold
# ----------------------------------------------------------------------
def test_a_visible_phase_is_never_held():
    """Nothing changes for a fit whose phases the data can see.

    The empty lists are written on every stage, so an empty one means "nothing
    was held", never "nobody looked" (WP-1076's honest empty state).
    """
    structure = make_lab6()
    ref = Refinement(structure, _absent_phase_inputs()[1], history=False)
    result = ref.fit(synthesize(), plan="mccusker_default")
    assert result.statistics.rwp < 0.05
    for stage in result.stages:
        assert stage.held == [] and stage.released == [], stage.name
    assert not [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]


# ----------------------------------------------------------------------
# what it reports
# ----------------------------------------------------------------------
def test_the_diagnostic_says_what_the_run_did_about_it(held_fit):
    """``PHASE_UNCONSTRAINED`` keeps its code and gains the account.

    Before this the same fit reported "N of its parameters were refined against
    it", which was true and left the caller to guess whether the values were
    worth anything.  Now the message names the stages that held them, and the
    paths are in ``where`` either way — a held value is what you handed in, a
    refined one moved in a flat direction, and neither is a result.
    """
    _, result = held_fit
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    finding = fired[0]
    assert finding.value < PHASE_SUPPORT_SIGMA
    assert "were held for" in finding.message or "was held for" in finding.message
    held = {p for stage in result.stages for p in stage.held}
    assert held <= set(finding.where)
    # the stages it names are the stages that held, in the order they ran
    named = [s.name for s in result.stages if s.held]
    tail = finding.message.split("stage")[-1]
    assert all(name in tail for name in named)
    assert tail.index(named[0]) < tail.index(named[-1])


def test_the_message_counts_what_it_names(held_fit):
    """The count in the sentence is the length of ``where``, not a guess."""
    _, result = held_fit
    finding = next(d for d in result.diagnostics
                   if d.code == "PHASE_UNCONSTRAINED")
    assert f"its {len(finding.where)} structural parameter" in finding.message


# ----------------------------------------------------------------------
# the cost
# ----------------------------------------------------------------------
def test_the_flat_column_is_gone_from_the_solve(held_fit):
    """The point of holding rather than bounding: no column to search.

    A bounded flat direction is still a column of the Jacobian and still costs
    a trust-region evaluation per iteration; a held one is not in θ at all.
    Asserted on the free count the last stage solved with, which is the number
    the solver actually paid for.
    """
    _, result = held_fit
    held = {p for stage in result.stages for p in stage.held}
    free = {p.path for p in result.parameters if p.vary}
    assert held and not (held & free)
    assert np.isfinite(result.statistics.rwp)


@pytest.mark.slow
def test_the_held_fit_is_drawn_for_inspection(held_fit):
    """Rwp hides locally-bad fits; the picture is the check that does not.

    The held phase contributes nothing to draw — that is what "held" means —
    so what this shows is the other half: the phase that *is* there, fitted
    with the flat direction removed from the solve.
    """
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_result

    _, result = held_fit
    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "held_phase.png"))
    plt.close("all")
    assert (OUT / "held_phase.png").exists()


# ----------------------------------------------------------------------
# the limit case: no line of the phase in the fitted range
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def no_reflection_fit():
    """NIST SRM 660c LaB₆ fitted where the certification data has no peak.

    That dataset is measured in windows around its own reflections, so the
    interval 22.5-29.5° reduces to 41 points at 29.1-29.5° — real data, real
    counts, and no line of LaB₆ anywhere in it (the 100 sits at 21.4°, the 110
    at 30.4°).  A single-phase fit of a phase the range cannot see.
    """
    import rietx as rx
    from tests.test_acceptance_srm660c import (
        _nist_calibrated_plan,
        build_srm_inputs,
    )

    data, structure, instrument = build_srm_inputs()
    ref = rx.Refinement(structure, instrument, history=False)
    return ref, ref.fit(data, plan=_nist_calibrated_plan(),
                        two_theta_limits=(22.5, 29.5))


def test_no_reflection_in_range_is_reported_rather_than_silent(no_reflection_fit):
    """rietx 1.0.1 crashed here; then it converged and said nothing.

    Measured on ``main`` before this: ``converged``, Rwp 0.334, and the only
    diagnostic ``DISPERSION_NEGLECTED`` — a fit that refined a cell, two Biso
    and a profile against no reflection at all and reported success.  A
    contributor's campaign brief spent a paragraph telling its agents to work
    around the state by hand.
    """
    _, result = no_reflection_fit
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    assert "no reflection of phase 0" in fired[0].message
    assert "LaB6" in fired[0].message


def test_the_zero_line_case_is_the_limit_of_support_not_a_second_test():
    """``phase_line_counts`` is zero exactly where nothing can be measured.

    A different statement from a small ``phase_support`` and worth separating:
    a phase whose scale is at its floor may appear in the next pattern of a
    series, one with no line in the window will not, whatever the specimen
    does.  Read off the frozen windows, so a reflection generated just outside
    the fitted ends counts as the absence it is.
    """
    from tests.test_acceptance_srm660c import build_srm_inputs

    data, structure, instrument = build_srm_inputs()
    blind = compile_model(structure, instrument, data, mode="rietveld",
                          two_theta_limits=(22.5, 29.5))
    seeing = compile_model(structure, instrument, data, mode="rietveld",
                           two_theta_limits=(29.5, 32.0))
    assert int(blind.phase_line_counts()[0]) == 0
    assert int(seeing.phase_line_counts()[0]) > 0


def test_the_blind_range_holds_everything_but_the_scale(no_reflection_fit):
    """Held, not refined: a single-phase model gets the rule too.

    The phase count never entered it — "the data cannot see this phase" is a
    measurement on the phase, and a lone phase under the noise is exactly as
    unmeasurable as one of six.
    """
    ref, result = no_reflection_fit
    held = {p for stage in result.stages for p in stage.held}
    assert "phases.0.cell.a" in held
    assert not [p for p in held if p.endswith(".scale")]
    # the cell is the value the protocol declared, to the digit
    assert ref.structure.phases[0].cell.a.value == 4.1568


# ----------------------------------------------------------------------
# the ramp: a phase that appears part-way through
# ----------------------------------------------------------------------
#: the in-situ ramp of the 2026-08-26 agent run, regenerated here from the same
#: CIF rather than shipped as data.  NAC (COD 1000236) on a lab Cu Kα doublet,
#: its cell expanding through a first-order step at 430 °C, and a CaF₂ phase
#: that is absent below the step and grows above it.  The refinement is told
#: none of that: it starts from the room-temperature cell, a flat background
#: and a nominal scale, which is what makes the sub-onset patterns a flat
#: direction rather than a bad guess.
RAMP_T_TRANSITION = 430.0
RAMP_A0 = 10.2570
RAMP_CAF2_A = 5.4631
RAMP_GRID = np.arange(15.0, 60.0 + 1e-9, 0.05)


def _ramp_a(temperature: float) -> float:
    if temperature <= RAMP_T_TRANSITION:
        return RAMP_A0 * (1 + 8.0e-6 * (temperature - 25.0))
    return RAMP_A0 * (1 + 8.0e-6 * (RAMP_T_TRANSITION - 25.0) + 1.6e-3
                      + 1.10e-5 * (temperature - RAMP_T_TRANSITION))


def _ramp_caf2_weight(temperature: float) -> float:
    if temperature <= RAMP_T_TRANSITION:
        return 0.0
    return min(1.0, (temperature - RAMP_T_TRANSITION) / 90.0)


def _caf2_phase(scale: float, a: float = RAMP_CAF2_A):
    import rietx as rx

    return rx.Phase(
        name="CaF2", space_group="F m -3 m", cell=rx.Cell.cubic(a),
        atoms=[
            rx.Atom(label="Ca", species="Ca2+", x=rx.Parameter(value=0.0),
                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                    biso=rx.Parameter(value=0.6, min=0.0, max=25.0)),
            rx.Atom(label="F", species="F1-", x=rx.Parameter(value=0.25),
                    y=rx.Parameter(value=0.25), z=rx.Parameter(value=0.25),
                    biso=rx.Parameter(value=0.9, min=0.0, max=25.0)),
        ],
        scale=rx.Parameter(value=scale, min=0.0, transform="softplus"))


def _ramp_instrument():
    import rietx as rx
    from rietx.schemas.instrument import BackgroundChebyshev

    ins = rx.Instrument.bragg_brentano(radiation="CuKa",
                                       monochromator_two_theta=26.6)
    ins.profile.u.value, ins.profile.v.value = 0.010, -0.005
    ins.profile.w.value, ins.profile.x.value = 0.050, 0.030
    ins.background = BackgroundChebyshev.with_terms(4)
    return ins


def _ramp_host():
    from pathlib import Path

    import rietx as rx

    s = rx.Structure.from_cif(
        str(Path(__file__).parent / "data" / "cod_1000236.cif"))
    s.phases[0].name = "NAC"
    return s


def _ramp_patterns(temperatures, seed: int = 20260826, grid=None):
    """Poisson-sampled patterns from the package's own forward model.

    ``grid`` defaults to the coarse one these tests fit; the runaway
    reproduction passes the run's own 0.02° grid so its iteration counts are
    comparable with the measured baselines.
    """
    import rietx as rx

    grid = RAMP_GRID if grid is None else grid

    truth = _ramp_host()
    truth.phases[0].scale.value = 6.0e-5
    truth.phases.append(_caf2_phase(0.0))
    ins = _ramp_instrument()
    ins.background.coefficients[0].value = 260.0
    ins.background.coefficients[1].value = -70.0
    ins.background.coefficients[2].value = 25.0
    rng = np.random.default_rng(seed)
    out = []
    for temperature in temperatures:
        truth.phases[0].cell.a.value = _ramp_a(temperature)
        truth.phases[1].scale.value = 4.0e-4 * _ramp_caf2_weight(temperature)
        y = rx.Refinement(truth, ins).predict(grid)
        counts = rng.poisson(np.maximum(y, 0.0)).astype(float)
        out.append(rx.PatternData(
            two_theta=grid.tolist(), intensity=counts.tolist(),
            sigma=np.sqrt(np.maximum(counts, 1.0)).tolist()))
    return out


def _ramp_start(caf2_a: float = RAMP_CAF2_A, bounds=(5.30, 5.60),
                scale: float = 1.0e-7):
    """The starting model, with the user cell bounds the agent added.

    Those bounds are why ``cell_window`` could not save this run: a finite
    stored bound is the caller's claim and suppresses the window on that side
    (``params.vector.cell_window``), so the safeguard was switched off by the
    very thing that was meant to replace it.
    """
    s = _ramp_host()
    s.phases[0].scale.value = 3.0e-5
    s.phases.append(_caf2_phase(scale, a=caf2_a))
    for atom in s.phases[1].atoms:
        atom.biso.vary = False
    if bounds is not None:
        for edge in (s.phases[1].cell.a, s.phases[1].cell.b, s.phases[1].cell.c):
            edge.min, edge.max = bounds
    return s


def _ramp_agent_plan():
    """The four-stage plan the agent's call declared, verbatim.

    ``refit="single"`` collapses it into one stage per pattern, which is what
    puts the scale and the cell in the same solve.
    """
    import rietx as rx

    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile_w", ["instrument.profile.w"]),
        rx.Stage("profile_x", ["instrument.profile.x"]),
    ])


def _collapsed_plan():
    """The one stage ``refit="single"`` collapses the agent's plan into.

    Scale and cell free together — which is why "hold only when the scale is
    not free this stage" was rejected: it would miss the shape the run ran.
    """
    import rietx as rx

    return rx.RefinementPlan(stages=[rx.Stage(
        "all", ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
                "instrument.profile.w", "instrument.profile.x"])])


@pytest.fixture(scope="module")
def released_fit():
    """One pattern at 700 °C — the phase is there — from a 1.2 % wrong cell."""
    import rietx as rx

    data = _ramp_patterns([700.0])[0]
    ref = rx.Refinement(_ramp_start(caf2_a=5.40), _ramp_instrument(),
                        history=False)
    return ref, ref.fit(data, plan=_collapsed_plan())


def test_a_phase_that_appears_mid_stage_is_released_and_refined(released_fit):
    """The hold must not cost the pattern where the phase first appears.

    The stage starts with CaF₂ at 1e-7 — invisible, so its cell is held — and
    the scale climbs while the stage solves.  The hold is then lifted and the
    stage solves once more, so the cell is measured here rather than one
    pattern later.  From a seed 1.2 % away it lands within 20 ppm of the truth.
    """
    ref, result = released_fit
    stage = result.stages[0]
    assert stage.released == ["phases.1.cell.a"]
    assert stage.held == [], "the hold was lifted, so nothing stayed held"
    a = ref.structure.phases[1].cell.a.value
    assert a == pytest.approx(RAMP_CAF2_A, rel=1e-4), f"CaF2 a = {a}"
    assert result.statistics.rwp < 0.06


def test_the_release_is_bounded_at_one_second_solve(released_fit):
    """Never a third: the cost of a wrong hold is one stage's budget.

    Both solves are counted where the budget is read, and ``cost_initial`` is
    still the cost the stage started at — a stage is one record whatever
    happened inside it.
    """
    _, result = released_fit
    stage = result.stages[0]
    assert stage.cost_final < stage.cost_initial
    assert stage.n_iterations > 0
    # one stage, one record, whether or not it solved twice
    assert len(result.stages) == 1


def test_a_released_phase_raises_no_warning_about_itself(released_fit):
    """``PHASE_UNCONSTRAINED`` is for a phase the data cannot see.

    This one could be seen, in the end, and its parameters are measurements —
    so firing here would teach a reader to ignore the code.  What happened is
    on the record (``StageResult.released``), not in a warning.
    """
    _, result = released_fit
    assert not [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]


@pytest.fixture(scope="module")
def ramp_series():
    """Four patterns straddling the 430 °C onset, chained as the run was."""
    from rietx.sequential import SequentialRefinement

    temps = [400.0, 425.0, 445.0, 475.0]
    runner = SequentialRefinement(_ramp_start(), _ramp_instrument(),
                                  carry=["phases.0.*", "instrument.*"])
    series = runner.fit(_ramp_patterns(temps), x=temps,
                        labels=[f"{t:.0f}C" for t in temps],
                        plan=_collapsed_plan(), refit="single")
    return temps, runner, series


def test_the_phase_is_refined_in_the_pattern_where_it_appears(ramp_series):
    """Not one pattern later, which is what a hold-and-rerun rule would cost.

    445 °C is the first pattern with any CaF₂ in it (truth scale 6.7e-5).  Its
    cell is measured there — 5.4624 Å against the true 5.4631 — while the two
    patterns below the onset hold theirs at the value handed in.
    """
    temps, runner, series = ramp_series
    below = [e for e, t in zip(series.entries, temps) if t < 430.0]
    above = [e for e, t in zip(series.entries, temps) if t > 430.0]
    assert len(below) == 2 and len(above) == 2

    for entry in below:
        paths = {p.path for p in entry.parameters}
        assert "phases.1.cell.a" not in paths, entry.label
        assert "PHASE_UNCONSTRAINED" in [d.code for d in entry.diagnostics]
    for entry in above:
        row = next(p for p in entry.parameters if p.path == "phases.1.cell.a")
        assert row.value == pytest.approx(RAMP_CAF2_A, rel=1e-3), entry.label
        assert not [d for d in entry.diagnostics
                    if d.code == "PHASE_UNCONSTRAINED"]


def test_below_the_onset_the_cell_is_where_it_was_put(ramp_series):
    """The measured alternative: 5.30000 Å (a bound) and 5.59898 Å.

    Both of those came out of the same chain on ``main`` — one pinned at the
    user's own lower bound with ``BOUND_HIT``, the other most of the way to the
    upper one — and neither is a fluorite cell.  Held, the value is the 5.4631
    the caller declared, which is the only number a reader can interpret.
    """
    temps, runner, _ = ramp_series
    for structure, temperature in zip(runner.fitted_structures, temps):
        if temperature < 430.0:
            assert structure.phases[1].cell.a.value == RAMP_CAF2_A


def test_the_stream_says_what_was_held_and_when():
    """``held``/``released`` ride the existing kinds, and the alignment holds.

    Open-dict fields on ``stage_start``/``stage_end``, so
    ``EVENT_SCHEMA_VERSION`` does not move — the additivity rule in
    ``history/events.py``.  The resumed solve emits its **own**
    ``stage_start``, because ``eval.values`` is declared to align with
    ``stage_start.free_paths`` and the second solve's free vector is longer
    than the first's; a reader aligns on the most recent one.
    """
    import rietx as rx
    from rietx.history.events import EVENT_SCHEMA_VERSION

    seen: list[dict] = []
    data = _ramp_patterns([700.0])[0]
    ref = rx.Refinement(_ramp_start(caf2_a=5.40), _ramp_instrument(),
                        history=False)
    ref.fit(data, plan=_collapsed_plan(), events=seen.append)

    assert {e["v"] for e in seen} == {EVENT_SCHEMA_VERSION}
    starts = [e["data"] for e in seen if e["kind"] == "stage_start"]
    ends = [e["data"] for e in seen if e["kind"] == "stage_end"]
    assert len(starts) == 2 and len(ends) == 1, "one stage, solved twice"
    assert starts[0]["held"] == ["phases.1.cell.a"]
    assert starts[1]["released"] == ["phases.1.cell.a"]
    assert starts[1]["held"] == [] and starts[1]["freed"] == ["phases.1.cell.a"]
    assert len(starts[1]["free_paths"]) == len(starts[0]["free_paths"]) + 1
    assert ends[0]["released"] == ["phases.1.cell.a"]
    assert ends[0]["held"] == []

    # every eval aligns with the stage_start that preceded it
    current = None
    for event in seen:
        if event["kind"] == "stage_start":
            current = event["data"]["free_paths"]
        elif event["kind"] == "eval" and "values" in event["data"]:
            assert len(event["data"]["values"]) == len(current)


def test_a_held_stage_streams_the_hold_without_a_release():
    """The ordinary case: one ``stage_start`` per stage, ``released`` empty."""
    import rietx as rx

    seen: list[dict] = []
    structure, ins = _absent_phase_inputs()
    rx.Refinement(structure, ins, history=False).fit(
        synthesize(), plan="mccusker_default", events=seen.append)
    starts = [e["data"] for e in seen if e["kind"] == "stage_start"]
    ends = [e["data"] for e in seen if e["kind"] == "stage_end"]
    assert len(starts) == len(ends) == 5
    assert [d["held"] for d in ends[2:]] == [["phases.1.cell.a"]] * 3
    assert all(d["released"] == [] for d in ends)


# ----------------------------------------------------------------------
# the mirror: a phase that looks visible at stage start and collapses
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def collapsed_fit():
    """A sub-onset pattern with CaF₂ seeded the way the agent seeded it.

    ``phase_support`` measures the *modelled* contribution, so a phase seeded
    at scale 1e-4 is well above the noise at stage start whatever the specimen
    contains: nothing is held, and the flat direction opens only as the solve
    drives that scale to nothing.  This is the shape the ramp ran — 68 patterns
    with CaF₂ re-seeded at 1e-4 for every one of them.
    """
    import rietx as rx

    data = _ramp_patterns([300.0])[0]
    ref = rx.Refinement(_ramp_start(scale=1.0e-4, bounds=None),
                        _ramp_instrument(), history=False)
    return ref, ref.fit(data, plan=_collapsed_plan())


def test_a_phase_that_collapses_mid_stage_is_held_and_put_back(collapsed_fit):
    """The hold's mirror, and the half a start-of-stage test cannot see.

    Measured on ``main`` over the ramp's 13 sub-onset patterns, this shape
    walks the CaF₂ cell to 1.73 Å, 8.99 Å and 20.34 Å with esds of 1e11 to
    1e24 — and with the start-of-stage hold alone, to −6.49 Å.  The restore is
    invisible to the data by the very measurement that licences the hold: a
    phase under 1σ contributes under 1σ wherever its peaks sit, since the peak
    height is ``scale × |F|² × profile`` and the cell only moves them.
    """
    ref, result = collapsed_fit
    stage = result.stages[0]
    assert stage.held == ["phases.1.cell.a"]
    assert stage.released == []
    # the collapse case of ``test_held_and_freed_are_disjoint``: this stage's
    # globs *did* free the cell, and the record must not go on saying so once
    # the value has been put back and the path held
    assert not set(stage.freed) & set(stage.held)
    assert ref.structure.phases[1].cell.a.value == RAMP_CAF2_A
    assert "phases.1.cell.a" not in {p.path for p in result.parameters}


def test_the_collapse_is_reported_as_the_flat_direction_it_is(collapsed_fit):
    """``PHASE_UNCONSTRAINED``, naming the stage that held it."""
    _, result = collapsed_fit
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1
    assert "held for stage all" in fired[0].message
    assert fired[0].where == ["phases.1.cell.a"]


def test_the_host_phase_is_fitted_either_way(collapsed_fit):
    """The hold costs the phase that *is* there nothing."""
    ref, result = collapsed_fit
    assert result.statistics.rwp < 0.06
    assert ref.structure.phases[0].cell.a.value == pytest.approx(
        _ramp_a(300.0), rel=2e-4)


# ----------------------------------------------------------------------
# the run that paid for all of this
# ----------------------------------------------------------------------
#: the run's own grid, 15-60° at 0.02° — used only by the reproduction below,
#: so its iteration counts are comparable with the measured baselines
RAMP_RUN_GRID = np.arange(15.0, 60.0 + 1e-9, 0.02)

#: the wall-clock **runaway guard** for that reproduction.  Not a timer: the
#: unbounded chain it reproduces was killed after 13 minutes on ``main``
#: without finishing, so anything of this order means the flat direction is
#: back, and a machine slow enough to fail it honestly would fail the whole
#: suite's budgets too (tests/CLAUDE.md § Running).  The chain takes 9-17 s
#: alone and tripped a 60 s guard on five of five full runs under load
#: (WP-1420), so 300 s keeps the margin over the runaway's 13+ minutes.
RAMP_RUNAWAY_GUARD_S = 300.0

#: iterations the same 13 patterns took on ``main`` **with** the ±2.5 % cell
#: bounds the agent added after the fact — the bounded baseline this replaces.
#: Measured 2026-08-27 at 1638; re-measured on this tree's machine at 1342
#: bounded and 2164 unbounded, which is the honest comparison (the same chain,
#: the same commit, one flag apart).  The assertion is against the *unbounded*
#: number, because the point is that no bound is needed.
RAMP_MAIN_UNBOUNDED_ITERATIONS = 2164


@pytest.mark.slow
def test_the_ramp_reproduction_no_longer_runs_away():
    """The 13 sub-onset patterns, the agent's exact call, no user bounds.

    On ``main`` this chain does not finish in 13 minutes without the bounds,
    and finishes wrong with them: every CaF₂ cell lands on a bound or halfway
    to one, with esds of 1e15.  There is no CaF₂ in any of these patterns —
    the phase appears at 430 °C and the hottest here is 149 °C — so the honest
    answer for its cell is the 5.4631 Å the model was handed, and that is what
    every pattern reports.

    Three properties, none of them an Rwp comparison: the chain finishes inside
    a runaway guard, it costs fewer iterations than the unbounded baseline, and
    no pattern reports a CaF₂ cell at all.
    """
    import time

    import rietx as rx

    temperatures = list(np.linspace(25.0, 720.0, 68)[:13])
    assert max(temperatures) < RAMP_T_TRANSITION, "these are the sub-onset ones"
    patterns = _ramp_patterns(temperatures, grid=RAMP_RUN_GRID)

    started = time.perf_counter()
    series = rx.refine_sequential(
        patterns, _ramp_start(bounds=None, scale=1.0e-4), _ramp_instrument(),
        carry=["phases.0.*", "instrument.*"],
        x=temperatures, x_label="T (C)",
        labels=[f"{t:.0f}C" for t in temperatures],
        plan=_ramp_agent_plan(), refit="single")
    elapsed = time.perf_counter() - started

    assert elapsed < RAMP_RUNAWAY_GUARD_S, f"{elapsed:.1f}s"
    iterations = sum(e.n_iterations for e in series.entries)
    assert iterations < RAMP_MAIN_UNBOUNDED_ITERATIONS, iterations
    for entry in series.entries:
        paths = {p.path for p in entry.parameters}
        assert "phases.1.cell.a" not in paths, entry.label
        assert "PHASE_UNCONSTRAINED" in [d.code for d in entry.diagnostics]

    # and the aggregation is untouched: it reads `where`, which now carries the
    # held paths, so the chain still says the thing no per-pattern code can
    persistent = [d for d in series.diagnostics
                  if d.code == "SEQUENTIAL_PERSISTENT_FINDING"]
    assert len(persistent) == 1
    assert persistent[0].where == ["phases.1.cell.a"]
    assert "13 of 13" in persistent[0].message


@pytest.mark.slow
def test_no_cell_leaves_the_physical_range_in_that_chain():
    """The failure WP-1110 met twice: cells at ≈39 293 Å and ≈40 000 Å.

    Reduced but not removed by the window, and removed here — the value never
    moves, so there is nothing to leave the range.  Asserted on the fitted
    models rather than the entries, because a held parameter is (rightly)
    absent from the entry's parameter list and the model is where a chain's
    next warm start would read it from.
    """
    from rietx.sequential import SequentialRefinement

    temperatures = list(np.linspace(25.0, 720.0, 68)[:5])
    runner = SequentialRefinement(_ramp_start(bounds=None, scale=1.0e-4),
                                  _ramp_instrument(),
                                  carry=["phases.0.*", "instrument.*"])
    runner.fit(_ramp_patterns(temperatures, grid=RAMP_RUN_GRID),
               x=temperatures, labels=[f"{t:.0f}C" for t in temperatures],
               plan=_ramp_agent_plan(), refit="single")
    for structure in runner.fitted_structures:
        assert structure.phases[1].cell.a.value == RAMP_CAF2_A
        host = structure.phases[0].cell.a.value
        assert 10.0 < host < 10.5, host
# ----------------------------------------------------------------------
# every mode, and the joint path
# ----------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_an_intensity_model_holds_a_phase_with_no_line_in_range(mode):
    """The rule is one rule; the intensity modes reach it by the same test.

    ``phase_support`` is measured on the modelled contribution whatever builds
    it, so in ``lebail``/``pawley`` it reads the extracted per-hkl intensities.
    With no reflection in the fitted range there is nothing to extract, the
    contribution is identically zero, and the cell is held exactly as in
    Rietveld — the scale, which those modes force-fix anyway, is not the reason.
    """
    import rietx as rx
    from tests.test_acceptance_srm660c import build_srm_inputs

    data, structure, instrument = build_srm_inputs()
    plan = rx.RefinementPlan(stages=[
        rx.Stage("bkg", ["instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
    ])
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(data, mode=mode, plan=plan, two_theta_limits=(22.5, 29.5))

    assert result.stages[-1].held == ["phases.0.cell.a"]
    assert ref.structure.phases[0].cell.a.value == 4.1568
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1 and "no reflection of phase 0" in fired[0].message


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_an_extracted_phase_is_not_unsupported_and_is_not_held(mode):
    """Where the modes legitimately differ, and why that is the same rule.

    A Rietveld phase reaches the pattern through ``scale × |F|² × profile``, so
    an absent one collapses to a flat direction.  Under an intensity model its
    per-hkl intensities are *fitted*, so it takes a share of whatever lies
    under its predicted peaks and its cell keeps a live gradient: the phase is
    not one the data cannot see, it is one the model can always place.  The
    hold therefore does not fire, and that is the measurement rather than an
    exception to it — reading it as "absent" is what ``PAWLEY_OVERLAP_UNRESOLVED``
    and the Le Bail warnings in the protocol are for.
    """
    import rietx as rx

    structure, ins = _absent_phase_inputs()
    plan = rx.RefinementPlan(stages=[
        rx.Stage("bkg", ["instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
    ])
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(synthesize(), mode=mode, plan=plan)
    assert all(stage.held == [] for stage in result.stages)


def test_the_joint_path_holds_a_phase_no_histogram_can_see():
    """A joint fit's authority is every histogram, not any one of them.

    ``_freeze_cell_windows_multi``'s rule, one tier up: a phase invisible in one
    pattern may be plain in another, and a shared cell is then measured by the
    fit that pools them.  Only a phase below support in **all** of them is a
    flat direction — and until now the joint path was the one runner that never
    said so at all, since it never built the diagnostic.
    """
    import rietx as rx

    structure, ins = _absent_phase_inputs()
    ref = rx.MultiHistogramRefinement(structure, [ins, ins.model_copy(deep=True)])
    result = ref.fit([synthesize(), synthesize()], plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
    ]))

    assert result.stages[-1].held == ["phases.1.cell.a"]
    assert ref.mtable.structures[0].phases[1].cell.a.value == 5.2
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1 and "was held for stage cell" in fired[0].message


def test_the_joint_hold_needs_every_histogram_to_be_blind():
    """One histogram that can see the phase is enough to refine it jointly.

    Asserted on the predicate rather than on a fit, because the state it turns
    on — one histogram's scale up, the other's at its floor — is one a joint
    fit reaches only through a specimen that differs between patterns, and the
    rule has to hold before any of that is arranged.
    """
    from rietx.model.forward import compile_model as _compile
    from rietx.multi import _joint_unsupported_phases
    from rietx.params.multi import MultiParameterTable

    structure, ins = _absent_phase_inputs()
    pattern = synthesize()
    mtable = MultiParameterTable(structure, [ins, ins.model_copy(deep=True)])
    model = _compile(structure, ins, pattern, mode="rietveld")
    assert _joint_unsupported_phases([model, model], mtable) == {1}

    # raise the absent phase's scale in the *second* histogram only: it is a
    # per-histogram column, and the joint fit can now see the phase
    entry = next(e for e in mtable.tables[1].entries
                 if e.path == "phases.1.scale")
    entry.value = structure.phases[0].scale.value
    mtable.tables[1]._rebuild()   # a fixed entry's value lives in the offsets
    mtable._rebuild_columns()
    assert _joint_unsupported_phases([model, model], mtable) == set()


@pytest.mark.slow
def test_the_blind_range_and_the_collapse_are_drawn_for_inspection(
        no_reflection_fit, collapsed_fit):
    """Two pictures the numbers cannot replace.

    The blind range is a fit with **no peak in it at all** — the picture is
    what makes that obvious, where Rwp 0.334 and a `converged` status do not.
    The collapse is the opposite: a good fit of the phase that is there, with
    the phase that is not contributing nothing, and the check is that the
    difference curve carries no unmodelled line where CaF₂ would sit.
    """
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    _, blind = no_reflection_fit
    plot_result(blind, path=str(OUT / "held_phase_blind_range.png"))
    _, collapsed = collapsed_fit
    plot_result(collapsed, path=str(OUT / "held_phase_collapsed.png"))
    plot_result(collapsed, path=str(OUT / "held_phase_collapsed_zoom.png"),
                two_theta_range=(26.0, 40.0))
    plt.close("all")
    for name in ("held_phase_blind_range", "held_phase_collapsed",
                 "held_phase_collapsed_zoom"):
        assert (OUT / f"{name}.png").exists()


def test_a_later_stage_re_decides_the_hold_rather_than_inheriting_it():
    """The lift, and what it costs to forget it.

    A hold is lifted at the *start of the next stage*, not at the end of the
    one that took it — the free set a stage ends with is the set its solve
    used, and the esd map, the guard and ``n_free`` are all indexed by it.  So
    the next stage re-frees what was held and asks the measurement again.

    Without that lift the hold is permanent in everything but name: staging is
    cumulative, so a cell freed in stage 1 is meant to keep refining in stage 2
    whose ``turn_on`` never mentions it, and a phase that has appeared in the
    meantime would stay unrefined for the rest of the run.  Here stage 1 holds
    the cell (the scale is fixed at 1e-7 and cannot rescue it), stage 2 frees
    the scale alone, and the cell must come back a measurement.
    """
    import rietx as rx

    data = _ramp_patterns([700.0])[0]
    ref = rx.Refinement(_ramp_start(caf2_a=5.40, bounds=None),
                        _ramp_instrument(), history=False)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("cell_bkg", ["phases.*.cell.*", "instrument.background.*"]),
        rx.Stage("scale", ["phases.*.scale"]),
    ]))

    first, second = result.stages
    assert first.held == ["phases.1.cell.a"], "stage 1 could not see the phase"
    assert second.released == ["phases.1.cell.a"], "stage 2 never got it back"
    assert "phases.1.cell.a" in {p.path for p in result.parameters}
    assert ref.structure.phases[1].cell.a.value == pytest.approx(
        RAMP_CAF2_A, rel=1e-3)


# ----------------------------------------------------------------------
# WP-1342 — the freeze asks what a column moves, not what it is called
# ----------------------------------------------------------------------
# The hold exists to remove a *flat direction*.  Flatness is a property of the
# column, and until this WP the test for it was a property of the column's
# **name**: ``_unsupported_phase_paths`` kept the free paths starting
# ``phases.{ip}.``.  Drive the same cell through a named variable (WP-1119) and
# the only free name is ``vars.A``, which matches nothing — so the freeze
# reported that it had done its job, on a set it could not see into.
def _tied_absent(source: float = 5.2) -> Refinement:
    """The absent-phase fixture with phase 1's cell driven by ``vars.A``."""
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    ref.add_variable("A", source, min=1.0, max=20.0)
    ref.tie("phases.1.cell.a", "vars.A")
    return ref


#: Everything the cell stage below carries forward — staging is cumulative.
_CELL_PLAN_BASE = ["phases.*.scale", "instrument.background.*",
                   "instrument.profile.w", "instrument.zero_shift"]


def _cell_plan(*cell_globs: str) -> PlanSpec:
    """Scale, background, profile, then the cell — a plan that converges.

    Thick enough that the fits below are real ones (Rwp 0.0414, GoF 1.027,
    the present phase's cell 1.4 ppm from the truth), because a comparison
    between two badly-scaled fits is a comparison between two artefacts. The
    cell stage frees whatever glob it is given, which is the whole difference
    between the arms: one names the parameter, the other names the variable
    driving it.
    """
    return PlanSpec(stages=[
        StageSpec(name="scale_bkg",
                  turn_on=["phases.*.scale", "instrument.background.*"]),
        StageSpec(name="profile", turn_on=list(_CELL_PLAN_BASE)),
        StageSpec(name="cell",
                  turn_on=[*_CELL_PLAN_BASE, *cell_globs]),
    ])


def test_a_column_that_only_moves_an_unsupported_phase_is_held():
    """The arm that failed before this WP: same freeze, same phase, one tie.

    Measured on this fixture phase 1 contributes 0.0396σ, far under
    ``PHASE_SUPPORT_SIGMA``, and its cell is exactly as flat driven through
    ``vars.A`` as driven by its own column.  The hold must see it either way.
    """
    ref = _tied_absent()
    pattern = synthesize()
    model = compile_model(ref.structure, ref.instrument, pattern,
                          mode="rietveld")
    table = ref._prepare_table(restore=False)
    table.set_vary(["vars.A", "phases.0.cell.a"], True)

    support = model.phase_support(table.decode(table.x0()))
    assert support[1] < PHASE_SUPPORT_SIGMA, "the fixture stopped being absent"
    # the tied entry is not a column of θ and still moves while θ does
    assert "phases.1.cell.a" not in table.free_paths
    assert "phases.1.cell.a" in table.moving_paths

    assert _unsupported_phase_paths(model, table) == ["vars.A"]


def test_the_untied_answer_is_unchanged():
    """The control, and the reason the change is safe: no tie, same answer.

    Every free column reaches exactly itself when nothing is tied onto it, so
    the reach test degenerates to the prefix test it replaced.
    """
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    pattern = synthesize()
    model = compile_model(ref.structure, ref.instrument, pattern,
                          mode="rietveld")
    table = ParameterTable(ref.structure, ref.instrument)
    table.set_vary(["phases.*.cell.a"], True)

    assert _unsupported_phase_paths(model, table) == ["phases.1.cell.a"]


def test_a_column_reaching_a_supported_phase_is_never_held():
    """The several-phase decision, and the measurement behind it.

    One variable driving both cells is **not** a flat direction: phase 0 gives
    it real gradient, so holding it would freeze a direction the data can see.
    Measured on this fixture, holding it leaves the present phase's cell at the
    4.20 Å seed — 10 441 ppm from the truth, Rwp 0.9589 — against 4.156594 Å at
    −1 ppm and Rwp 0.0416 with the column free.  So the rule is *all*, never
    *any*: hold the column only when everything it moves belongs to a phase the
    data cannot see.
    """
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    ref.add_variable("A", 4.20, min=1.0, max=20.0)
    ref.tie_equal(["phases.0.cell.a", "phases.1.cell.a"], source="vars.A")

    pattern = synthesize()
    model = compile_model(ref.structure, ref.instrument, pattern,
                          mode="rietveld")
    table = ref._prepare_table(restore=False)
    table.set_vary(["vars.A"], True)

    support = model.phase_support(table.decode(table.x0()))
    assert support[0] >= PHASE_SUPPORT_SIGMA > support[1], "fixture moved"
    assert _unsupported_phase_paths(model, table) == []


def test_a_column_that_moves_the_phases_own_scale_is_never_held():
    """The scale rule survives the rewrite, and falls out of it.

    A phase reaches the pattern only through ``scale × |F|² × profile``, so the
    scale is the one direction that is not flat when the phase is invisible.
    Under the reach test that needs no special case: a column moving
    ``phases.1.scale`` moves something the data can see.
    """
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    ref.add_variable("S", structure.phases[1].scale.value, min=0.0, max=1.0)
    ref.tie("phases.1.scale", "vars.S")

    pattern = synthesize()
    model = compile_model(ref.structure, ref.instrument, pattern,
                          mode="rietveld")
    table = ref._prepare_table(restore=False)
    table.set_vary(["vars.S"], True)
    assert _unsupported_phase_paths(model, table) == []


def test_the_absent_cell_stops_walking_through_its_tie():
    """The fit-level cost, and what the record said about it.

    Unheld, the variable walked the absent cell 5.2 → 3.35512 Å while the two
    fits agreed on Rwp to 1.7e-15 — the flat direction costs nothing at all to
    travel, which is why no Rwp comparison can find this — and
    ``StageResult.held`` was empty throughout.
    """
    ref = _tied_absent()
    result = ref.fit(synthesize(), plan=_cell_plan("vars.*"), telemetry=False)

    held = {p for stage in result.stages for p in stage.held}
    assert "vars.A" in held, "the freeze still cannot see the tie"
    assert ref.structure.phases[1].cell.a.value == 5.2
    assert [r.value for r in ref.parameters() if r.path == "vars.A"] == [5.2]


def test_the_record_and_the_diagnostic_name_the_phase_behind_the_column():
    """A held column is not a phase path, and the report is about a phase.

    ``StageResult.held`` records the column the verb acted on; ``held_reach``
    records what that column also stopped, which is how ``PHASE_UNCONSTRAINED``
    still finds the phase to talk about.  Without it the message would go
    silent on exactly the fits this WP repairs.
    """
    ref = _tied_absent()
    result = ref.fit(synthesize(), plan=_cell_plan("vars.*"), telemetry=False)

    stage = next(s for s in result.stages if s.held)
    assert stage.held == ["vars.A"]
    assert stage.held_reach == {"vars.A": ["phases.1.cell.a", "phases.1.cell.b",
                                           "phases.1.cell.c"]}

    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    assert "was held for" in fired[0].message
    # the column, because that is the declaration a caller can lift — and one
    # finding about the phase, not one per parameter the column drove, because
    # `where` is what the series keys its persistent-finding aggregation on
    assert fired[0].where == ["vars.A"]


def test_held_reach_carries_the_derived_ties_a_hold_also_stopped():
    """It is about the column, not about the caller: symmetry ties count too.

    Holding a cubic ``a`` stops ``b`` and ``c`` with it, and a reader of the
    record should not have to know the crystal system to learn that. The map
    is ``column_reach`` restricted to what was held, minus each column itself —
    so a column that moved nothing else is absent rather than mapped to an
    empty list, and the union with ``held`` is every value this stage froze.
    """
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthesize(), plan="mccusker_default", telemetry=False)

    stage = next(s for s in result.stages if s.held)
    assert stage.held == ["phases.1.cell.a"]
    assert stage.held_reach == {"phases.1.cell.a": ["phases.1.cell.b",
                                                    "phases.1.cell.c"]}
    for other in result.stages:
        assert set(other.held_reach) <= set(other.held), other.name


def test_the_hold_reaches_every_pattern_of_a_chain():
    """WP-1441's exposure: the tie is re-declared per pattern, so the miss was.

    A tie could once be declared only on a single ``Refinement``, so a freeze
    that could not see it cost one answer. ``constrain=(index, ref)`` puts the
    declaration on every pattern of a chain, which multiplies the exposure by
    the chain's length and hides it where nobody reads an individual fit.

    There is no CaF₂ in any of these patterns, so the honest answer for its
    cell is the 5.4631 Å the model was handed, on every one of them. Measured
    with the name test restored, the same chain returns 5.30422, 5.38679,
    5.57821, 5.39074 and 5.59999 Å — a 0.296 Å spread for a phase that is not
    there, two of them on the caller's own bound — while every Rwp sits within
    1e-5 of the held arm's, three of the five patterns report no diagnostic at
    all, and the chain-level finding is absent. That walk is not monotone, so
    it reads as a trajectory rather than as a fault, and ``direction="both"``
    cannot separate it from a real one because both directions carry the tie.
    """
    import rietx as rx
    from rietx.sequential import SequentialRefinement

    # five, which is `MIN_POINTS_FOR_PERSISTENCE`: the chain-level sentence is
    # half of what this arm is for, and below that the aggregation declines
    temperatures = [25.0, 60.0, 95.0, 130.0, 165.0]
    assert max(temperatures) < RAMP_T_TRANSITION, "these are the sub-onset ones"

    def constrain(index, ref):
        ref.add_variable("caf2_a", RAMP_CAF2_A, min=5.30, max=5.60)
        ref.tie("phases.1.cell.a", "vars.caf2_a")

    # the collapsed stage, plus the glob that frees the caller's own variable —
    # without it the tie is declared and nothing ever frees what drives it
    plan = rx.RefinementPlan(stages=[rx.Stage(
        "all", ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
                "instrument.profile.w", "instrument.profile.x", "vars.*"])])
    runner = SequentialRefinement(_ramp_start(bounds=None),
                                  _ramp_instrument(),
                                  carry=["phases.0.*", "instrument.*"])
    series = runner.fit(_ramp_patterns(temperatures), x=temperatures,
                        labels=[f"{t:.0f}C" for t in temperatures],
                        plan=plan, refit="single", constrain=constrain)

    for entry, structure in zip(series.entries, runner.fitted_structures,
                                strict=True):
        # the value is the one handed in, on every pattern — not a walk that
        # stopped somewhere, and not a number anybody may quote
        assert structure.phases[1].cell.a.value == RAMP_CAF2_A, entry.label
        assert "vars.caf2_a" not in {p.path for p in entry.parameters}
        assert "PHASE_UNCONSTRAINED" in [d.code for d in entry.diagnostics]

    # and the chain says the thing no per-pattern finding can
    persistent = [d for d in series.diagnostics
                  if d.code == "SEQUENTIAL_PERSISTENT_FINDING"]
    assert len(persistent) == 1
    assert persistent[0].where == ["vars.caf2_a"]
    assert "5 of 5" in persistent[0].message


def test_a_held_column_is_released_when_its_phase_appears():
    """The release is the hold's other half, and it reads names too.

    ``released_fit``'s pattern, with the CaF₂ cell driven through a variable.
    The stage starts with the phase invisible, so the column is held; the scale
    climbs while the stage solves, and the hold must be lifted here rather than
    one pattern later. The release test could only ever see ``phases.1.`` in
    the held path's own name, so a held ``vars.caf2_a`` stayed held: measured,
    the cell sat at its 5.40 Å seed against 5.463026 Å, and Rwp 0.1939 against
    0.0550 — a hold this WP made possible and nothing could lift.
    """
    import rietx as rx

    data = _ramp_patterns([700.0])[0]
    ref = rx.Refinement(_ramp_start(caf2_a=5.40), _ramp_instrument(),
                        history=False)
    ref.add_variable("caf2_a", 5.40, min=5.0, max=6.0)
    ref.tie("phases.1.cell.a", "vars.caf2_a")
    plan = rx.RefinementPlan(stages=[rx.Stage(
        "all", ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
                "instrument.profile.w", "instrument.profile.x", "vars.*"])])
    result = ref.fit(data, plan=plan, telemetry=False)

    stage = result.stages[0]
    assert stage.released == ["vars.caf2_a"]
    assert stage.held == [], "the hold was lifted, so nothing stayed held"
    a = ref.structure.phases[1].cell.a.value
    assert a == pytest.approx(RAMP_CAF2_A, rel=1e-4), f"CaF2 a = {a}"
    assert result.statistics.rwp < 0.06


def test_a_column_held_for_two_absent_phases_is_reported_under_both():
    """One column, two flat phases, and a warning owed about each of them.

    ``_only_moves`` holds a column when *every* phase it moves is invisible,
    which one variable driving two absent cells satisfies — so the column is
    correctly held, and ``PHASE_UNCONSTRAINED`` is owed for both phases. Read
    by stopping at the first phase the column's names mention, the second one
    had nothing held, nothing free under its own prefix, and therefore no
    finding at all.
    """
    import rietx as rx

    structure, ins = _absent_phase_inputs()
    second = structure.phases[1].model_copy(deep=True)
    second.name = "absent2"
    ref = rx.Refinement(
        Structure(phases=[structure.phases[0], structure.phases[1], second]),
        ins, history=False)
    ref.add_variable("A", 5.2, min=1.0, max=20.0)
    ref.tie_equal(["phases.1.cell.a", "phases.2.cell.a"], source="vars.A")
    result = ref.fit(synthesize(), plan=_cell_plan("vars.*"), telemetry=False)

    stage = next(s for s in result.stages if s.held)
    assert stage.held == ["vars.A"]
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 2, [d.message for d in fired]
    assert {d.message.split()[1] for d in fired} == {"1", "2"}
    # the column, once per phase — never the six cell parameters it drove
    assert all(d.where == ["vars.A"] for d in fired)


@pytest.mark.slow
def test_the_tied_hold_is_drawn_for_inspection():
    """Rwp hides locally-bad fits; the picture is the check that does not.

    Two panels of the same fixture, drawn from the same plan: the cell driven
    by its own column, and driven through ``vars.A``. The held phase
    contributes nothing to draw — that is what "held" means — so what these
    show is that the phase which *is* there is fitted the same either way,
    which is the claim a Rwp equality alone cannot make.
    """
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    structure, ins = _absent_phase_inputs()
    plain = Refinement(structure, ins, history=False)
    untied = plain.fit(synthesize(), plan=_cell_plan("phases.*.cell.a"),
                       telemetry=False)
    # the present phase's cell is freed by its own column in both arms, so the
    # only difference between them is how the *absent* phase's cell is driven
    tied = _tied_absent().fit(
        synthesize(), plan=_cell_plan("vars.*", "phases.0.cell.a"),
        telemetry=False)

    for name, result in (("untied", untied), ("tied", tied)):
        plot_result(result, path=str(OUT / f"held_phase_reach_{name}.png"))
    plt.close("all")

    assert (OUT / "held_phase_reach_untied.png").exists()
    assert (OUT / "held_phase_reach_tied.png").exists()
    # the phase that is there is fitted identically either way — bit-identical
    # rather than close, which is the strongest form of "the repair costs the
    # converged fit nothing"; the arms differ only in what each one held
    assert tied.statistics.rwp == untied.statistics.rwp
    assert {p for s in untied.stages for p in s.held} == {"phases.1.cell.a"}
    assert {p for s in tied.stages for p in s.held} == {"vars.A"}
