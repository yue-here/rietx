"""WP-1523 — a phase is seen when its scale is 3σ from zero against counting noise.

Issue #481's blank frame is background and Poisson noise alone, yet a fit to it
used to report LaB6's cell with an esd and no ``PHASE_UNCONSTRAINED``, or hold
it, depending only on where the fit started.  The old test read one point's
height at 1σ, and a scale fitted to noise lifts that point past it.  The new
one has two halves:

* ``CompiledModel.phase_support`` is the screen, ‖y_p/σ‖₂ over the fitted
  range.  It is the scale's conditional z, so it bounds the full test from
  above, and a phase under ``PHASE_SUPPORT_SIGMA`` there is unseen.
* ``refine._answer_significance`` takes scale / esd(scale) where the screen
  passes: the esd from (JᵀWJ)⁻¹ with no χ²_red or Bérar-Lelann factor,
  marginal over every column that moves the peaks (displacements,
  occupancies and other phases' scales left out), with a held phase's
  columns freed for the measurement.

The frame is rebuilt here from the issue script's RNG stream (seed 11,
patterns 0-7 drawn in order), and both starts are the issue's: pattern 0's
fitted models, and the unfitted models the script began from.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.indexing.workflow import ABSENT_SIGMA
from rietx.model.forward import PHASE_SUPPORT_SIGMA, compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import Dispersion
from rietx.schemas.structure import StephensStrain

pytestmark = pytest.mark.xdist_group("phase-significance")

_refine = __import__("sys").modules["rietx.refine"]
OUT = Path(__file__).parent / "output"

WAVELENGTH, A0, RAMP = 0.4139, 4.15660, 6.4e-5
BLANK = 7
TT = np.arange(3.0, 24.0, 0.005)


def _lab6(a: float, scale: float | None = None) -> rx.Phase:
    phase = rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(a, vary=True),
        atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
               rx.Atom(label="B", species="B", x=rx.Parameter(value=0.1993),
                       y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))])
    if scale is not None:
        phase.scale.value = scale
        for atom in phase.atoms:
            atom.biso.value = 0.4
    return phase


def _instrument(zero: float, w: float, background) -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    # declared, not inherited: the records below were measured with it on
    ins.source.dispersion = Dispersion()
    ins.zero_shift.value, ins.profile.w.value = zero, w
    for c, v in zip(ins.background.coefficients, background, strict=False):
        c.value = v
    return ins


def _draw(phase: rx.Phase, rng) -> rx.PatternData:
    y = rx.Refinement(rx.Structure(phases=[phase]),
                      _instrument(0.008, 2.5e-4, (40.0, -6.0, 1.5))).predict(TT)
    return rx.PatternData(two_theta=TT.tolist(),
                          intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def _unfitted() -> tuple[rx.Structure, rx.Instrument]:
    return (rx.Structure(phases=[_lab6(A0 * 1.001, 7.5e-4)]),
            _instrument(0.0, 3.75e-4, (0.0, 0.0, 0.0)))


@pytest.fixture(scope="module")
def issue_481():
    """Patterns 0 and 7 of the issue's ramp, and pattern 0's fitted models."""
    rng = np.random.default_rng(11)
    patterns = [_draw(_lab6(A0 * (1 + RAMP * k), 0.0 if k == BLANK else 5e-4), rng)
                for k in range(BLANK + 1)]
    first = rx.Refinement(*_unfitted(), history=False)
    first.fit(patterns[0], plan="mccusker_default")
    starts = {"fitted": lambda: (first.fitted_structure, first.fitted_instrument),
              "unfitted": _unfitted}
    return patterns, starts


def _fit(structure, instrument, pattern, monkeypatch, plan="mccusker_default",
         events=None):
    """Fit, recording ``(screen, significance)`` at every stage's answer.

    A stage that releases or collapses a phase solves twice and records twice.
    ``events``, a list, collects the fit's event stream.  The fit's
    obs/calc/diff plot goes to ``tests/output/``, named for the calling test.
    """
    from rietx.viz.plots import plot_result
    record: list[tuple[float, float]] = []
    inner = _refine._answer_significance

    def spy(model, table, outcome, held, reach, backend, **kw):
        out = inner(model, table, outcome, held, reach, backend, **kw)
        screen = model.phase_support(table.decode(outcome.theta))
        record.append((round(float(screen[0]), 2), round(float(out[0]), 2)))
        return out

    monkeypatch.setattr(_refine, "_answer_significance", spy)
    result = rx.Refinement(structure, instrument, history=False).fit(
        pattern, plan=plan,
        events=None if events is None else events.append)
    OUT.mkdir(exist_ok=True)
    name = (os.environ["PYTEST_CURRENT_TEST"].split("::")[-1]
            .split(" ")[0].split("@")[0])
    plot_result(result, path=str(OUT / f"phase_significance_{name}.png"))
    return result, record


def _assert_unseen(result, record):
    assert "phases.0.cell.a" not in {p.path for p in result.parameters}
    (finding,) = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert finding.value < PHASE_SUPPORT_SIGMA
    assert any("phases.0.cell.a" in st.held for st in result.stages)
    assert record and all(z < PHASE_SUPPORT_SIGMA for _, z in record), record


def _assert_prior_holds(result, events, path="phases.0.cell.a"):
    """Each stage after one that ended with ``path`` held starts with it held.

    Such a stage then solves once, or twice if its answer releases the path.
    The check is conditional on where each answer landed, so it asserts what
    the code does with a reading and not which side of 3σ a solver endpoint
    falls on, which can differ between platforms.  These plans seed no row
    of the phase, which would drop its prior.  Returns how many stages it
    checked.
    """
    starts: dict[int, list[dict]] = {}
    for event in events:
        if event["kind"] == "stage_start":
            starts.setdefault(event["data"]["index"], []).append(event["data"])
    checked = 0
    for k in range(2, len(result.stages) + 1):
        if path not in result.stages[k - 2].held:
            continue
        stage = result.stages[k - 1]
        assert path in starts[k][0]["held"], stage.name
        assert len(starts[k]) == (2 if path in stage.released else 1), stage.name
        checked += 1
    return checked


def _assert_seen(result):
    a = {p.path: p for p in result.parameters}.get("phases.0.cell.a")
    assert a is not None and a.stderr is not None
    assert abs(a.value - A0) < 1e-3
    assert "PHASE_UNCONSTRAINED" not in {d.code for d in result.diagnostics}


@pytest.mark.parametrize("start", ["fitted", "unfitted"])
def test_the_blank_frame_holds_its_cell_from_either_start(issue_481, start,
                                                         monkeypatch):
    """Both rows of the WP's table, which used to disagree.

    Before WP-1523 the fitted start released the cell at ``profile_w`` and
    reported 4.14990 ± 0.0016 Å with no finding, while the unfitted start held
    it.  Each stage's answer, as ``(screen, significance)``, measured
    2026-10-04 (macOS arm64, ``[dev]``):

    * fitted: (1.04, 1.04), (1.06, 1.06), (2.33, 2.33), (2.40, 2.40),
      (2.62, 2.62)
    * unfitted: (0.17, 0.17), (0.16, 0.16), (1.49, 1.49), (1.50, 1.50),
      (1.97, 1.97)

    The screen stays under 3σ at every stage of this frame, so the full test
    is never needed; the next test is a frame where it is.
    """
    patterns, starts = issue_481
    _assert_unseen(*_fit(*starts[start](), patterns[BLANK], monkeypatch))


def test_a_blank_frame_past_the_screen_is_judged_by_its_marginal_z(
        issue_481, monkeypatch):
    """Seed 107 of the WP's sweep: noise alone lifts the screen past 3σ.

    Each stage's answer, as ``(screen, significance)``, measured 2026-10-12
    (macOS arm64, ``[dev]``): (2.24, 2.24), (2.50, 2.50), (2.50, 2.50),
    (3.25, 2.61), (3.64, 1.44).

    At the ``profile_w`` answer the cell is held and the screen passes, so
    the held cell is freed for the measurement (2.61).  The ``profile`` stage
    starts from that reading as well as the screen, so it holds the cell from
    its start, frees it again for the measurement at its answer (1.44), and
    solves once.  With the screen alone the cell refined from the
    ``profile`` start, its scale read 1.44σ at the answer, and the stage put
    the cell back and solved a second time: 41 iterations against 18.
    """
    _, starts = issue_481
    pattern = _draw(_lab6(A0, 0.0), np.random.default_rng(107))
    events: list[dict] = []
    result, record = _fit(*starts["unfitted"](), pattern, monkeypatch,
                          events=events)
    assert any(s >= PHASE_SUPPORT_SIGMA for s, _ in record), record
    _assert_unseen(result, record)
    _assert_prior_holds(result, events)


def test_a_later_stage_starts_from_the_answer_before_it(issue_481, monkeypatch):
    """The stage-start hold reads the previous answer, not the screen alone.

    The same blank under ``mccusker_structural``.  From ``profile_w`` on the
    screen reads 3.25σ to 3.64σ at each answer while the marginal z stays
    between 0.62σ and 2.61σ.  With
    the screen alone each of the seven stages from ``profile`` on freed the
    cell, chased the noise, put the cell back and solved again: 18 solves
    for 11 stages and 233 iterations, measured 2026-10-12 (macOS arm64,
    ``[dev]``).  Read beside the previous answer, each of those stages holds
    the cell from its start: 11 solves and 59 iterations, and the finding
    reads 0.62σ either way.

    The assertions read the mechanism (:func:`_assert_prior_holds`), since
    the readings sit 0.39σ to 2.4σ under the threshold on one platform.
    """
    _, starts = issue_481
    pattern = _draw(_lab6(A0, 0.0), np.random.default_rng(107))
    events: list[dict] = []
    result, record = _fit(*starts["unfitted"](), pattern, monkeypatch,
                          plan="mccusker_structural", events=events)
    _assert_unseen(result, record)
    assert _assert_prior_holds(result, events) >= 1


@pytest.mark.parametrize("start", ["fitted", "unfitted"])
def test_a_weak_real_phase_is_still_refined(issue_481, start, monkeypatch):
    """A planted scale of 2.5e-7, 1/2000 of the ramp's, is seen from both starts.

    It is never held, and its cell lands 1.37e-4 Å from the planted one from
    either start.  Each stage's answer, as ``(screen, significance)``,
    measured 2026-10-04 (macOS arm64, ``[dev]``):

    * fitted: (19.63, 19.53), (19.63, 19.53), (19.64, 19.53), (19.74, 17.75),
      (19.79, 10.17)
    * unfitted: (2.53, 2.53), (4.09, 4.05), (19.04, 18.91), (19.74, 17.74),
      (19.79, 12.29)
    """
    _, starts = issue_481
    pattern = _draw(_lab6(A0, 2.5e-7), np.random.default_rng(200))
    result, record = _fit(*starts[start](), pattern, monkeypatch)
    _assert_seen(result)
    assert record[-1][1] >= PHASE_SUPPORT_SIGMA


def test_a_held_phase_that_appears_is_released(issue_481, monkeypatch):
    """The release path: held at the stage start, freed for the measurement.

    One stage frees scale, background and cell from a scale of 1e-10, so the
    cell is held at the start.  At the answer the held cell is freed to take
    the scale's esd, the phase passes, and the stage solves again.
    Each answer, as ``(screen, significance)``, measured 2026-10-04 (macOS
    arm64, ``[dev]``): (19.63, 19.53) with the held cell freed for the
    measurement, then (19.63, 19.53) after the second solve.
    """
    from rietx.schemas.plan import PlanSpec, StageSpec

    structure = rx.Structure(phases=[_lab6(A0, 1e-10)])
    instrument = _instrument(0.008, 2.5e-4, (40.0, -6.0, 1.5))
    pattern = _draw(_lab6(A0, 2.5e-7), np.random.default_rng(200))
    # the declared stage's release; the closing stage is tests/test_closing_stage.py's
    plan = PlanSpec(stages=[StageSpec(
        name="all", turn_on=["phases.*.scale", "instrument.background.*",
                             "phases.*.cell.*"])], closing_window_tol=None)
    result, record = _fit(structure, instrument, pattern, monkeypatch, plan=plan)
    (stage,) = result.stages
    assert stage.released == ["phases.0.cell.a"] and not stage.held
    assert record[0][1] >= PHASE_SUPPORT_SIGMA
    _assert_seen(result)


def test_a_phase_the_prior_holds_is_released_when_the_answer_sees_it(
        monkeypatch):
    """The prior can only hold, and its hold is asked again at the answer.

    The prior is forced to zero here for a phase the data plainly shows, so
    the stage holds the cell from its start although the screen passes.  At
    the answer the held cell is freed for the measurement, the phase passes,
    and the stage solves again with the cell free: the release path the
    previous test takes from a screen hold.
    """
    from rietx.schemas.plan import PlanSpec, StageSpec

    inner = _refine._hold_unsupported_phases
    monkeypatch.setattr(_refine, "_hold_unsupported_phases",
                        lambda model, table, prior=None, seeded_phases=(), **kw:
                        inner(model, table, np.zeros(1), **kw))
    structure = rx.Structure(phases=[_lab6(A0, 2.5e-7)])
    instrument = _instrument(0.008, 2.5e-4, (40.0, -6.0, 1.5))
    pattern = _draw(_lab6(A0, 2.5e-7), np.random.default_rng(200))
    # the declared stage's release; the closing stage is tests/test_closing_stage.py's
    plan = PlanSpec(stages=[StageSpec(
        name="all", turn_on=["phases.*.scale", "instrument.background.*",
                             "phases.*.cell.*"])], closing_window_tol=None)
    result, record = _fit(structure, instrument, pattern, monkeypatch, plan=plan)
    (stage,) = result.stages
    assert stage.released == ["phases.0.cell.a"] and not stage.held
    assert record[0][0] >= PHASE_SUPPORT_SIGMA
    assert record[0][1] >= PHASE_SUPPORT_SIGMA
    _assert_seen(result)


def test_a_phase_both_readings_pass_that_collapses_is_put_back(monkeypatch):
    """The collapse branch, reached with a prior that passed.

    Two stages on a phase the data plainly shows, its cell started 5e-4
    relative off.  The first stage frees scale and background, the second
    the cell too.  The previous answer and the screen both read far over 3σ,
    so the cell is free at the second stage's start.  Its first answer is
    then made to read 0σ: a collapse.  The cell goes back to the value the
    stage started from, is held, and the stage solves once more.  Forced, so
    the restore is exercised whatever a platform's solver does.
    """
    from rietx.schemas.plan import PlanSpec, StageSpec
    from rietx.viz.plots import plot_result

    cell = "phases.0.cell.a"
    answers: list[float] = []
    entering: list[float] = []
    significance = _refine._answer_significance
    solve = _refine.run_least_squares

    def collapse_once(model, table, outcome, held, reach, backend, **kw):
        out = significance(model, table, outcome, held, reach, backend, **kw)
        answers.append(table.decode(outcome.theta)[cell])
        if len(answers) == 2:
            out = np.array(out, dtype=np.float64)
            out[0] = 0.0
        return out

    def recording(model, table, *args, **kwargs):
        entering.append(table.decode(table.x0())[cell])
        return solve(model, table, *args, **kwargs)

    monkeypatch.setattr(_refine, "_answer_significance", collapse_once)
    monkeypatch.setattr(_refine, "run_least_squares", recording)
    base = ["phases.*.scale", "instrument.background.*"]
    # the declared stages' collapse; the closing stage is tests/test_closing_stage.py's
    plan = PlanSpec(stages=[StageSpec(name="scale", turn_on=base),
                            StageSpec(name="cell",
                                      turn_on=[*base, "phases.*.cell.*"])],
                    closing_window_tol=None)
    ref = rx.Refinement(rx.Structure(phases=[_lab6(A0 * 1.0005, 2.5e-7)]),
                        _instrument(0.008, 2.5e-4, (40.0, -6.0, 1.5)),
                        history=False)
    events: list[dict] = []
    result = ref.fit(_draw(_lab6(A0, 2.5e-7), np.random.default_rng(200)),
                     plan=plan, events=events.append)
    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "phase_significance_collapse.png"))

    starts = [e["data"] for e in events
              if e["kind"] == "stage_start" and e["data"]["index"] == 2]
    assert len(starts) == 2 and cell not in starts[0]["held"]
    assert len(entering) == 3
    start = entering[1]
    assert abs(answers[1] - start) > 1e-4, "the first solve left the cell"
    assert entering[2] == start, "put back before the second solve"
    assert ref.structure.phases[0].cell.a.value == start
    stage = result.stages[1]
    assert stage.held == [cell] and not stage.released
    assert cell not in stage.freed


def test_the_threshold_is_the_indexing_presence_test():
    """One number means one thing: a phase and a line are present at 3σ."""
    assert PHASE_SUPPORT_SIGMA == ABSENT_SIGMA


# Issue #219's ridge, compacted: cubic Cu at 0.4139 Å, modelled as the parent
# plus an ``I 4/m m m`` subgroup the specimen does not contain, its cell split
# off the group-subgroup identity by a seed.  The two scales are collinear.
CU_A, CU_TT = 3.615, np.arange(4.0, 32.0 + 1e-9, 0.02)


def _cu_phase(name, space_group, a, c, scale, *, vary):
    cell = rx.Cell(a=rx.Parameter(value=a, vary=vary, min=0.95 * a, max=1.05 * a),
                   b=rx.Parameter(value=a),
                   c=rx.Parameter(value=c, vary=vary, min=0.95 * c, max=1.05 * c),
                   alpha=rx.Parameter(value=90.0), beta=rx.Parameter(value=90.0),
                   gamma=rx.Parameter(value=90.0))
    atom = rx.Atom(label="Cu", species="Cu", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                   biso=rx.Parameter(value=0.5, min=0.0, max=10.0))
    phase = rx.Phase(name=name, space_group=space_group, cell=cell, atoms=[atom],
                     scale=rx.Parameter(value=scale, min=0.0),
                     lor_strain=rx.Parameter(value=1e-4 if vary else 0.0, min=0.0,
                                             max=0.5, vary=vary))
    if not vary:  # the specimen: 3000 ppm of isotropic Stephens strain
        phase.microstrain = StephensStrain.isotropic(3000.0, phase.cell, vary=False)
    return phase


def _cu_instrument():
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = Dispersion()  # declared: the sweep ran with it on
    ins.profile.w.value, ins.profile.x.value = 2.0e-3, 5.0e-3
    for c, v in zip(ins.background.coefficients, (400.0, -60.0, 20.0), strict=False):
        c.value = v
    return ins


def _ridge(seed: int, delta: float = 1e-3):
    """A cubic Cu pattern and the two-phase model of it, split by ``delta``."""
    truth = _cu_phase("Cu", "F m -3 m", CU_A, CU_A, 1.0, vary=False)
    y = rx.Refinement(rx.Structure(phases=[truth]), _cu_instrument(),
                      history=False).predict(CU_TT)
    scale = 4.0e4 / float(np.max(y) - np.min(y))
    truth.scale.value = scale
    y = rx.Refinement(rx.Structure(phases=[truth]), _cu_instrument(),
                      history=False).predict(CU_TT)
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 0.0)).astype(float)
    pattern = rx.PatternData(two_theta=CU_TT.tolist(), intensity=counts.tolist(),
                             sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())
    a_t = CU_A * (1.0 - delta / 2.0) / np.sqrt(2.0)
    model = rx.Structure(phases=[
        _cu_phase("parent", "F m -3 m", CU_A, CU_A, 0.9 * scale, vary=True),
        _cu_phase("subgroup", "I 4/m m m", a_t, CU_A * (1.0 + delta), 0.3 * scale,
                  vary=True)])
    return model, pattern


RIDGE_PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("cell", ["phases.*.cell.*"]),
    rx.Stage("strain", ["phases.*.lor_strain"])])


@pytest.mark.parametrize("seed", [2002, 2003])
def test_a_collinear_partner_does_not_hold_the_only_real_phase(seed):
    """Two phases that draw one pattern are exchangeable, not absent.

    Marginal over the partner's scale (ρ −1.000) each reads under 3σ, so the
    hold took whichever the start left weaker.  On these seeds that was the
    parent, the specimen's only phase: its cell and strain held, and
    ``PHASE_UNCONSTRAINED`` called it unseen (seeds 2000-2011 here: these two;
    9 of 15 fits under #219's own two-pass protocol).  Conditional on the
    partner's scale it reads tens of σ, and ``HIGH_CORRELATION`` names the
    pair.  All twelve seeds pass under the rule.
    """
    model, pattern = _ridge(seed)
    result = rx.Refinement(model, _cu_instrument(), history=False).fit(
        pattern, plan=RIDGE_PLAN)
    held = {p for st in result.stages for p in st.held}
    assert not {p for p in held if p.startswith("phases.0.")}, held
    unseen = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert not any(w.startswith("phases.0.") for d in unseen for w in d.where)
    assert "phases.0.cell.a" in {p.path for p in result.parameters}
    assert any(d.code == "HIGH_CORRELATION"
               and {"phases.0.scale", "phases.1.scale"} <= set(d.where)
               for d in result.diagnostics)


def test_only_the_partner_scales_leave_the_marginal():
    """A column moving only another phase's scale is left out, a displacement
    beside it or not; one moving this phase's scale too stays, and so does
    every other kind of column."""
    free = ["phases.0.scale", "phases.1.scale", "phases.1.cell.a", "vars.s",
            "phases.0.atoms.0.biso", "vars.k"]
    reach = {"vars.s": ["phases.0.scale", "phases.1.scale"],
             "vars.k": ["phases.0.atoms.0.biso", "phases.2.scale"]}
    assert _refine._significance_columns(free, [], reach, 0) == [
        "phases.0.scale", "phases.1.cell.a", "vars.s"]
    assert _refine._significance_columns(free, [], reach, 1) == [
        "phases.1.scale", "phases.1.cell.a", "vars.s"]


@pytest.fixture(scope="module")
def lab6_model():
    """A compiled LaB6 phase at the ramp's own scale, and its values."""
    structure = rx.Structure(phases=[_lab6(A0, 5e-4)])
    ins = _instrument(0.008, 2.5e-4, (40.0, -6.0, 1.5))
    pattern = _draw(structure.phases[0], np.random.default_rng(3))
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0())


def test_phase_support_is_the_integrated_norm(lab6_model):
    """The screen is ‖y_p/σ‖₂ over the fitted range, the scale's conditional z."""
    model, values = lab6_model
    sigma = np.asarray(model.sigma, dtype=np.float64)
    y = np.asarray(model.phase_component(0, values), dtype=np.float64)
    assert model.phase_support(values)[0] == pytest.approx(
        float(np.linalg.norm(y / sigma)), rel=1e-12)


def test_each_reflection_reads_its_own_window_norm(lab6_model):
    """The batched planes against one profile per window, and the phase above
    every one of its reflections, since every contribution is non-negative."""
    model, values = lab6_model
    cp = model.phases[0]
    sigma = np.asarray(model.sigma, dtype=np.float64)
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    rows = model.reflection_support(0, values)
    for il, (pos, gamma, eta, intensity) in enumerate(model.phase_peaks(0, values)):
        for k in range(len(pos)):
            prof = model._reflection_profile(cp, il, k, pos[k], gamma[k], eta[k],
                                             sl, hl)
            if prof is None:
                assert rows[il][k] == 0.0
                continue
            i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
            want = np.linalg.norm(intensity[k] * np.asarray(prof) / sigma[i0:i1])
            assert rows[il][k] == pytest.approx(float(want), rel=1e-9, abs=1e-12)
    best = max(float(np.max(r)) for r in rows)
    assert 0.0 < best <= model.phase_support(values)[0]
