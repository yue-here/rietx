"""WP-1320: a phase fraction the pattern cannot fix.

A trace phase's scale trades against its width.  Broadened far enough, its
peaks become a hump the background shares, and its scale can then grow at
almost no χ² cost, so the χ² surface along that ridge can hold separate basins
at one χ², each with ordinary curvature and a tight esd.  The fit reports
whichever it reached, and the esd — the curvature *there* — cannot see the
other.  Issue #203 measured it on a lab in-situ pattern (1.41 ± 0.65 wt%
against basins at 0 %, ~1.5 % and 98.7 % within 0.011 pp of Rwp); that data
is not in the repository, so the fixture here is synthetic.

**The fixture.**  LaB₆ with a trace of CaF₂ under lab Cu Kα, plus a 10-count
amorphous hump that the fitted six-term Chebyshev cannot follow.  A stiff
background is what recruits a phase smeared into a hump as extra background,
which is what puts the absurd basin at the same χ² as the true one.  The
**control** drops the hump and carries five times the CaF₂, the shape of
#203's 200 °C pattern: one minimum.

**Verified before anything asserts on it** — the width profile is first run by
hand, with public verbs only (``branch``, ``set_vary``, ``set_values``,
``run_stage``), at a sharp width, a barrier width and a hump-sized width, so
the fixture's two basins are established independently of the probe that the
second half of the module tests (``Refinement.profile_fraction``).  The
numbers ``docs/skill/rietx/references/judging.md`` § "a trace phase's esd
describes one basin" and the manual's QPA chapter quote are this module's.
"""

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import Instrument, PatternData
from rietx.model.forward import compile_model
from rietx.model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.fraction import FractionProfile
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.fraction_profile import WIDTH_TERMS, width_value
from rietx.strategy.staged import RefinementPlan, Stage

pytestmark = pytest.mark.xdist_group("qpa-multimodal")

OUT = Path(__file__).parent / "output"
TWO_THETA = np.arange(15.0, 100.0, 0.02)
TRUE_BACKGROUND = (200.0, -60.0, 20.0)
#: (height in counts, centre and FWHM in degrees 2θ) — an amorphous hump
HUMP = (10.0, 30.0, 15.0)
TRACE_SCALE = 2e-6          # CaF₂ at ~1 wt% of the crystalline content
CONTROL_SCALE = 1e-5        # five times more, and no hump: one basin
FITTED_BACKGROUND_TERMS = 6
AXIS = "phases.1.lor_strain"
#: the Δχ² for one parameter at 95 %, before the χ²_red·f² scaling
DCHI2_95 = 3.84
FREE = ["phases.*.scale", "phases.*.cell.*", "instrument.background.*",
        "instrument.zero_shift", "instrument.profile.w", "phases.*.lor_strain"]
PLAN = RefinementPlan(stages=[
    Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    Stage("cell", ["phases.*.cell.*", "instrument.zero_shift"]),
    Stage("width", FREE),
])


def _p(value: float) -> Parameter:
    return Parameter(value=value)


def _models(trace_scale: float, n_background: int) -> tuple[Structure, Instrument]:
    lab6 = Phase(name="LaB6", space_group="P m -3 m", cell=Cell.cubic(4.1566),
                 atoms=[Atom(label="La", species="La", x=_p(0.0), y=_p(0.0), z=_p(0.0)),
                        Atom(label="B", species="B", x=_p(0.1993), y=_p(0.5), z=_p(0.5))])
    caf2 = Phase(name="CaF2", space_group="F m -3 m", cell=Cell.cubic(5.4631),
                 atoms=[Atom(label="Ca", species="Ca2+", x=_p(0.0), y=_p(0.0), z=_p(0.0)),
                        Atom(label="F", species="F1-", x=_p(0.25), y=_p(0.25), z=_p(0.25))])
    structure = Structure(phases=[lab6, caf2])
    structure.phases[0].scale.value = 1e-3
    structure.phases[1].scale.value = trace_scale
    structure.phases[0].lor_strain.value = 0.02
    structure.phases[1].lor_strain.value = 0.05
    instrument = Instrument.bragg_brentano(radiation="CuKa")
    coefficients = list(TRUE_BACKGROUND) + [0.0] * (n_background - len(TRUE_BACKGROUND))
    instrument.background = BackgroundChebyshev(
        coefficients=[_p(v) for v in coefficients])
    return structure, instrument


def _synthesize(trace_scale: float, hump) -> PatternData:
    structure, instrument = _models(trace_scale, len(TRUE_BACKGROUND))
    blank = PatternData(two_theta=TWO_THETA.tolist(),
                        intensity=np.zeros_like(TWO_THETA).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    tt = np.asarray(model.tt)
    if hump is not None:
        height, centre, fwhm = hump
        y = y + height * np.exp(-4.0 * np.log(2.0) * ((tt - centre) / fwhm) ** 2)
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist())


def _fitted(trace_scale: float, hump):
    data = _synthesize(trace_scale, hump)
    ref = rx.Refinement(*_models(trace_scale, FITTED_BACKGROUND_TERMS))
    result = ref.fit(data, plan=PLAN, telemetry=False)
    return ref, result, data


@pytest.fixture(scope="module")
def multimodal():
    return _fitted(TRACE_SCALE, HUMP)


@pytest.fixture(scope="module")
def control():
    return _fitted(CONTROL_SCALE, None)


def _data_chi2(result) -> float:
    """The data's own χ², Σ w·Δ² — ``statistics.chi2`` is reduced."""
    st = result.statistics
    return st.chi2 * (st.n_points - st.n_free_parameters)


def _cut(result) -> float:
    """95 % Δχ² scaled by the calibration every esd already carries."""
    st = result.statistics
    return DCHI2_95 * st.chi2 * st.esd_inflation ** 2


def _pinned(ref, data, values):
    """The docs' width profile, on a branch: (value, W, χ², result) per value."""
    trial = ref.branch()
    trial.set_vary([AXIS], False)
    rows = []
    for value in values:
        trial.set_values({AXIS: value})
        r = trial.run_stage(data, rx.Stage("width_pin", []), telemetry=False)
        rows.append((value, r.qpa.phases[1].weight_fraction, _data_chi2(r), r))
    return rows


def test_the_trace_fixture_has_two_basins_at_one_chi2(multimodal):
    """A sharp basin and a hump basin, both admissible, a barrier between."""
    ref, result, data = multimodal
    sharp, barrier, hump = _pinned(ref, data, [0.03, 10.0, 80.0])
    best = min(sharp[2], barrier[2], hump[2], _data_chi2(result))
    cut = _cut(result)
    assert sharp[2] - best <= cut
    assert hump[2] - best <= cut
    assert barrier[2] - best > cut, "no barrier: one ridge, not two basins"
    assert sharp[1] < 0.03 < 0.5 < hump[1], (sharp[1], hump[1])
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "qpa_multimodal_fit.png"))
    hump[3].plot(path=str(OUT / "qpa_multimodal_hump_basin.png"))


def test_the_fit_reports_the_sharp_basin_with_a_tight_esd_and_no_finding(multimodal):
    """The premise: a confident point, and nothing that points at the phase."""
    _, result, _ = multimodal
    row = result.qpa.phases[1]
    # 0.0119 ± 0.0039 on data drawn at the declared stages' windows; drawn at the
    # closing stage's (WP-2002), nearer the 0.0069 the fixture holds
    assert row.weight_fraction == pytest.approx(0.0093, abs=0.0005)
    # 0.0053 before #674: the esd carries eqs (10)-(12)'s factor, 0.74× the run-sum's here
    assert row.weight_fraction_stderr == pytest.approx(0.0033, abs=0.0005)
    naming = [d.code for d in result.diagnostics
              if any("CaF2" in w or w.startswith("phases.1.") for w in d.where)]
    assert not naming, naming


def test_the_control_has_one_basin(control):
    """No hump and five times the trace: the hump-sized width is excluded."""
    ref, result, data = control
    # the sharp basin probed at the true width, 0.05: this trace's width is
    # measured, 0.070(22), and 0.03 sits 1.8 esd below it, at Δχ² 5.18 against
    # the cut's 5.12 (WP-2002)
    sharp, barrier, hump = _pinned(ref, data, [0.05, 10.0, 80.0])
    best = min(sharp[2], barrier[2], hump[2], _data_chi2(result))
    cut = _cut(result)
    assert sharp[2] - best <= cut
    assert barrier[2] - best > 10 * cut
    assert hump[2] - best > 10 * cut
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "qpa_multimodal_control_fit.png"))


# -- the probe: Refinement.profile_fraction ----------------------------------


def _basins(profile) -> int:
    """Runs of admissible grid points separated by inadmissible ones, per axis."""
    runs = 0
    for axis in profile.axes:
        flags = [p.admissible for p in profile.points if p.axis == axis]
        runs += sum(1 for i, a in enumerate(flags) if a and (i == 0 or not flags[i - 1]))
    return runs


@pytest.fixture(scope="module")
def multimodal_profile(multimodal):
    ref, _, data = multimodal
    before = {row.path: row.value for row in ref.parameters()}
    head = ref.history.head
    return ref.profile_fraction(data, "CaF2"), (before, head)


def test_the_profile_spans_both_basins_and_says_so(multimodal_profile):
    profile, _ = multimodal_profile
    assert profile.axes == [AXIS]
    assert _basins(profile) == 2
    assert profile.range_low < 0.02 and profile.range_high > 0.5
    assert profile.fit_admissible
    [finding] = profile.diagnostics
    assert finding.code == "QPA_FRACTION_RANGE"
    assert finding.level == "info"
    assert finding.where == ["phases.1.scale", AXIS]
    assert finding.value == profile.excess > 20
    assert f"{100 * profile.range_high:.3g} %" in finding.message


def test_the_control_profile_confirms_the_esd_and_states_it(control):
    """One basin, and every admissible fraction inside W ± 1.96 esd.

    The second half is the calibration claim: Δχ² scaled by χ²_red·f² is the
    esd's own scale, so a profile along a healthy minimum lands inside the
    interval the esd already quotes (0.47 of its half-width here).  The
    profile still states it, in the same info record the trace case gets:
    no threshold decides whether the record exists (WP-2002, B12).
    """
    ref, _, data = control
    profile = ref.profile_fraction(data, "CaF2")
    assert _basins(profile) == 1
    assert profile.excess < 1.0
    [finding] = profile.diagnostics
    assert finding.code == "QPA_FRACTION_RANGE"
    assert finding.level == "info"
    assert finding.value == profile.excess
    assert f"{100 * profile.range_low:.3g} %" in finding.message


def test_the_profile_moves_nothing(multimodal, multimodal_profile):
    """No accepted value moves anywhere the probe merely reports."""
    ref, result, _ = multimodal
    _, (before, head) = multimodal_profile
    assert ref.result_ is result
    assert {row.path: row.value for row in ref.parameters()} == before
    # the branch shares the tree, and a project reopens at its HEAD
    assert ref.history.head == head


def test_a_trial_carries_the_callers_declarations_with_or_without_history():
    """``_trial`` is ``branch`` without a history too — ties, variables, holds."""
    for history in (True, False):
        ref = rx.Refinement(*_models(CONTROL_SCALE, 3), history=history)
        ref.add_variable("w", 0.05)
        ref.tie("phases.1.lor_size", "phases.0.lor_size")
        ref.hold(["phases.0.cell.a"])
        trial = ref._trial()
        assert trial is not ref and trial.structure is not ref.structure
        assert set(trial._ties) == set(ref._ties) == {"phases.1.lor_size"}
        assert set(trial._variables) == set(ref._variables) == {"w"}
        assert trial._user_holds == ref._user_holds


def test_without_history_the_profile_still_moves_nothing(control):
    _, _, data = control
    ref = rx.Refinement(*_models(CONTROL_SCALE, FITTED_BACKGROUND_TERMS),
                        history=False)
    result = ref.fit(data, plan=PLAN, telemetry=False)
    before = {row.path: row.value for row in ref.parameters()}
    profile = ref.profile_fraction(data, "CaF2", fwhm=[0.0, 40.0])
    assert [p.fwhm for p in profile.points] == [0.0, 40.0]
    assert ref.result_ is result
    assert {row.path: row.value for row in ref.parameters()} == before


def test_the_profile_refuses_what_it_cannot_answer(control):
    ref, _, data = control
    with pytest.raises(ValueError, match="no phase named"):
        ref.profile_fraction(data, "CaF3")
    with pytest.raises(ValueError, match="not a width term"):
        ref.profile_fraction(data, 1, axes=["phases.1.scale"])
    with pytest.raises(ValueError, match="not a width term"):
        ref.profile_fraction(data, 1, axes=["phases.0.lor_strain"])
    with pytest.raises(RuntimeError, match="run a fit"):
        rx.Refinement(*_models(CONTROL_SCALE, 3)).profile_fraction(data, 1)
    narrow = rx.Refinement(*_models(CONTROL_SCALE, FITTED_BACKGROUND_TERMS))
    narrow.fit(data, plan=RefinementPlan(stages=[PLAN.stages[0]]), telemetry=False)
    with pytest.raises(ValueError, match="no width term of 'CaF2' is free"):
        narrow.profile_fraction(data, "CaF2")
    lebail = rx.Refinement(*_models(CONTROL_SCALE, FITTED_BACKGROUND_TERMS))
    lebail.fit(data, mode="lebail", telemetry=False, plan=RefinementPlan(
        stages=[Stage("bkg", ["instrument.background.*"])]))
    with pytest.raises(ValueError, match="'lebail' fit has none"):
        lebail.profile_fraction(data, "CaF2", axes=["phases.1.lor_strain"])
    with pytest.raises(ValueError, match="empty FWHM grid"):
        ref.profile_fraction(data, "CaF2", fwhm=[])
    with pytest.raises(ValueError, match="finite and non-negative"):
        ref.profile_fraction(data, "CaF2", fwhm=[0.0, float("inf")])
    tied = rx.Refinement(*_models(CONTROL_SCALE, FITTED_BACKGROUND_TERMS))
    tied.tie("phases.1.lor_size", "phases.0.lor_size")
    tied.fit(data, plan=RefinementPlan(stages=[PLAN.stages[0]]), telemetry=False)
    with pytest.raises(ValueError, match="tied to another parameter"):
        tied.profile_fraction(data, "CaF2", axes=["phases.1.lor_size"])


@pytest.mark.parametrize("term", WIDTH_TERMS)
def test_a_grid_width_is_the_phases_own_fwhm_at_the_mid_angle(term):
    """``width_value`` inverts the width laws the forward model evaluates."""
    theta, fwhm = 28.75, 0.7
    value = width_value(term, fwhm, theta)
    if term.startswith("lor_"):
        got = lorentzian_fwhm(theta, value if term == "lor_size" else 0.0,
                              value if term == "lor_strain" else 0.0)
    else:
        got = gaussian_fwhm(theta, 0.0, 0.0, 0.0,
                            gauss_size=value if term == "gauss_size" else 0.0,
                            gauss_strain=value if term == "gauss_strain" else 0.0)
    assert float(got) == pytest.approx(fwhm, rel=1e-12)


def test_the_profile_round_trips_through_json(multimodal_profile):
    profile, _ = multimodal_profile
    assert FractionProfile.model_validate_json(profile.model_dump_json()) == profile
