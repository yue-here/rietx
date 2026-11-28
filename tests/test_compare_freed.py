"""``compare_freed``: ΔBIC of a freed parameter, with its t-ratio beside it (WP-1417).

Issue #270's shape on a real fit.  The layers suite's LaB6 truth pattern is
generated with a Lorentzian width, and the model is fitted without one, at
counts high enough that the misfit dominates the noise.  The residual is then
serially correlated (Durbin-Watson ≈ 0.1, Bérar-Lelann f ≈ 6), which is the
premise raw-N ΔBIC gets wrong: it calls a Biso the esd puts within 2σ of its
held value decisive, and N/f² does not.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.optimize.statistics import effective_sample_size
from rietx.report import compare_freed
from tests.test_fitreport_layers import _truth

# both module fixtures are shared by several tests (tests/CLAUDE.md § Shared
# fixtures and xdist groups)
pytestmark = pytest.mark.xdist_group("compare-freed")

BASE = ["phases.*.scale", "instrument.background.*", "instrument.zero_shift",
        "phases.*.cell.*"]


def _fit(structure, ins, data, extra=()):
    ref = rx.Refinement(structure, ins)
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", BASE[:2]),
        rx.Stage("all", BASE + list(extra))]))
    return ref


def _freed(ref, data, path):
    trial = ref.branch()
    trial.run_stage(data, rx.Stage("add", [path]), telemetry=False)
    return compare_freed(ref, trial)


@pytest.fixture(scope="module")
def correlated():
    structure, ins, data = _truth(step=0.005, count_scale=3000.0)
    start = ins.model_copy(deep=True)
    start.profile.x.value = 0.0          # the data's Lorentzian, left out
    return _fit(structure, start, data, extra=["instrument.profile.w"]), data


def test_the_fixture_is_as_correlated_as_the_issue_s_patterns(correlated):
    ref, _ = correlated
    stats = ref.result_.statistics
    assert stats.durbin_watson < 0.5
    assert stats.esd_inflation > 4.0


def test_a_parameter_within_two_sigma_is_decisive_at_raw_n_and_not_at_n_eff(
        correlated):
    ref, data = correlated
    c = _freed(ref, data, "phases.0.atoms.1.biso")
    [p] = c.freed
    assert p.path == "phases.0.atoms.1.biso" and p.held_at == 0.5
    assert abs(p.t_ratio) < 2.0
    assert c.delta_bic_raw_n > 10.0      # #270: raw N blesses it
    assert c.delta_bic < 0.0
    assert c.n_effective == pytest.approx(
        effective_sample_size(c.n_points, c.esd_inflation))
    # the sums, not the reduced Statistics.chi2: the reduced pair's ratio
    # would carry (N − P_f)/(N − P_r), −1 of raw-N ΔBIC here
    r = ref.result_
    d = (np.asarray(r.y_obs) - np.asarray(r.y_calc)) / r.sig()
    assert c.chi2_restricted == pytest.approx(float(d @ d), rel=1e-9)
    # one parameter: the pair agree, ΔBIC ≈ t² − ln N_eff
    assert c.delta_bic == pytest.approx(p.t_ratio ** 2 - math.log(c.n_effective),
                                        abs=1.0)


def test_a_needed_parameter_stays_decisive(correlated):
    ref, data = correlated
    c = _freed(ref, data, "instrument.profile.u")
    [p] = c.freed
    assert abs(p.t_ratio) > 4.0
    assert c.delta_bic > 10.0


@pytest.fixture(scope="module")
def truth():
    return _truth()


def test_a_coordinate_dof_is_measured_on_its_coordinate_row(truth):
    """The DOF is a step from where its own fit began (WP-1333), so a fuller
    fit started from another coordinate reports another step for one answer."""
    structure, ins, data = truth
    held = structure.model_copy(deep=True)
    held.phases[0].atoms[1].x.value = 0.205
    restricted = _fit(held, ins.model_copy(deep=True), data)
    elsewhere = structure.model_copy(deep=True)
    elsewhere.phases[0].atoms[1].x.value = 0.21
    full = _fit(elsewhere, ins.model_copy(deep=True), data,
                extra=["phases.*.atoms.*.dof.*"])

    c = compare_freed(restricted, full)
    [p] = c.freed
    assert p.path == "phases.0.atoms.1.dof.0"
    x = full.result_.parameter("phases.0.atoms.1.x")
    assert p.t_ratio == pytest.approx((x.value - 0.205) / x.stderr, rel=1e-9)
    assert p.held_at == pytest.approx(-0.005, abs=1e-12)


def test_what_is_not_nested_is_refused(truth):
    structure, ins, data = truth
    ref = _fit(structure, ins.model_copy(deep=True), data)
    trial = ref.branch()
    trial.run_stage(data, rx.Stage("add", ["phases.0.atoms.1.biso"]),
                    telemetry=False)
    with pytest.raises(ValueError, match="nothing added"):
        compare_freed(ref, ref)
    with pytest.raises(ValueError, match="not nested"):
        compare_freed(trial, ref)
    # another pattern on the same grid, as two members of a series are
    s2, i2, other = _truth(seed=18)
    elsewhere = _fit(s2, i2, other, extra=["phases.0.atoms.1.biso"])
    with pytest.raises(ValueError, match="different intensities"):
        compare_freed(ref, elsewhere)
    # a moved value drops the result, so held values are never read off a
    # table that has left its fit
    ref.set_values({"instrument.zero_shift": 0.05})
    with pytest.raises(RuntimeError, match="run a fit on the restricted"):
        compare_freed(ref, trial)


# --- WP-2220: which fits a comparison rests on (#1685), and which freed
# columns carried information (#1686).  The two issues' own synthetic scripts.

def _lab6(biso_la=None):
    la = dict(label="La", species="La", x=rx.Parameter(value=0.0),
              y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))
    if biso_la is not None:
        la["biso"] = rx.Parameter(value=biso_la)
    return rx.Structure(phases=[rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.1566, vary=True),
        scale=rx.Parameter(value=4e-4),
        atoms=[rx.Atom(**la),
               rx.Atom(label="B", species="B", x=rx.Parameter(value=0.1993),
                       y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))])])


def _lab6_instrument(extra=()):
    from rietx.schemas.instrument import BackgroundChebyshev

    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.u.value, ins.profile.w.value, ins.profile.x.value = 3e-3, 4e-3, 6e-3
    ins.background = BackgroundChebyshev(
        coefficients=[rx.Parameter(value=v) for v in (80.0, 0.0, 0.0, 0.0)])
    ins.extra_components = list(extra)
    return ins


def _poisson(structure, seed):
    tt = np.arange(18.0, 125.0, 0.02)
    y = np.maximum(rx.Refinement(structure, _lab6_instrument()).predict(tt), 1.0)
    yobs = np.random.default_rng(seed).poisson(y * 60.0) / 60.0
    return rx.PatternData(two_theta=tt.tolist(), intensity=yobs.tolist(),
                          sigma=np.sqrt(y / 60.0).tolist())


def _plot(result, name):
    from pathlib import Path

    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / f"compare_freed_{name}.png"))


BISO = "phases.0.atoms.0.biso"


@pytest.fixture(scope="module")
def biso_pair():
    """#1685: La Biso held at 0.6 against a truth of 0.5, then freed twice."""
    data = _poisson(_lab6(0.5), 17)
    ref = _fit(_lab6(0.6), _lab6_instrument(), data)
    arms = {}
    for label, start, max_iter in (("converged", None, 100), ("max_iter", 4.0, 1)):
        full = ref.branch()
        if start is not None:
            full.set_values({BISO: start})
        full.run_stage(data, rx.Stage("free_biso", BASE + [BISO], max_iter=max_iter),
                       telemetry=False)
        arms[label] = full
    _plot(arms["max_iter"].result_, "1685_max_iter")
    return ref, arms


def test_a_converged_ordered_pair_carries_no_finding(biso_pair):
    ref, arms = biso_pair
    c = compare_freed(ref, arms["converged"])
    assert (c.status_restricted, c.status_full) == ("converged", "converged")
    assert c.chi2_ordered and c.chi2_full < c.chi2_restricted
    assert c.diagnostics == []
    assert c.delta_bic > 0 and c.n_identified == 1
    [p] = c.freed
    assert p.at_bound is False and p.t_reason is None and p.t_ratio < 0


def test_a_budget_stop_above_the_restricted_optimum_is_flagged(biso_pair):
    """The issue's second row: ΔBIC has the wrong sign, and now says why."""
    ref, arms = biso_pair
    c = compare_freed(ref, arms["max_iter"])
    assert c.status_full == "max_iter" and c.status_restricted == "converged"
    assert not c.chi2_ordered and c.chi2_full > c.chi2_restricted
    assert c.delta_bic < 0
    [d] = c.diagnostics
    assert d.code == "COMPARISON_UNCONVERGED" and d.level == "warning"
    assert d.value == pytest.approx(c.chi2_full - c.chi2_restricted)
    assert "'max_iter'" in d.message and "a cost more than 2 above" in d.message
    assert d.where == [BISO]
    # flagged, never refused: the numbers are still there to read
    assert c.freed[0].t_ratio is not None


def test_ordering_alone_fires_where_status_says_converged():
    """The LM driver calls a slow-descent stop ``converged`` (#222), so the
    ordering is tested whatever the status, and either status alone fires."""
    from rietx.report.layer2 import _comparison_unconverged

    d = _comparison_unconverged("converged", "converged", 100.0, 101.0, False,
                                where=["x"])
    assert d is not None and "status" not in d.message and d.value == 1.0
    d = _comparison_unconverged("max_iter", "converged", 101.0, 100.0, True,
                                where=["x"])
    assert d is not None and "restricted fit stopped" in d.message
    assert _comparison_unconverged("converged", "converged", 101.0, 100.0, True,
                                   where=["x"]) is None


def test_the_ordering_margin_is_two_cost_units_at_any_scale():
    """The margin is absolute, in the units ΔBIC is read in (ruled
    2026-11-20): an excess just under 2 is ordered, just over is not, on a
    small cost and on a large one alike, and on the stage-less fallback."""
    from types import SimpleNamespace as NS

    from rietx.report.layer2 import NESTED_COST_MARGIN, _chi2_ordered

    assert NESTED_COST_MARGIN == 2.0

    def staged(cost):
        return NS(stages=[NS(cost_final=cost)])

    def bare(chi2_red, n_points, n_free):
        return NS(stages=[], statistics=NS(chi2=chi2_red, n_points=n_points,
                                           n_free_parameters=n_free))

    for base in (100.0, 1.0e6):
        assert _chi2_ordered(staged(base), staged(base + 1.999))
        assert _chi2_ordered(staged(base), staged(base + 2.0))
        assert not _chi2_ordered(staged(base), staged(base + 2.001))
        assert _chi2_ordered(staged(base), staged(base - 50.0))
    # no stage recorded: the data sums, Σw·Δ² = χ²_red·(N − P), are compared
    assert _chi2_ordered(bare(1.0, 101, 1), bare(101.999 / 99, 101, 2))
    assert not _chi2_ordered(bare(1.0, 101, 1), bare(102.001 / 99, 101, 2))


def test_a_verdict_short_fits_could_flip_is_not_judged():
    """The bias decides: a short fuller fit understates the gain, a short
    restricted one overstates it (WP-2220 task 5)."""
    from rietx.report.layer2 import _judged

    assert _judged(True, "converged", "converged", True) == (True, None)
    assert _judged(False, "converged", "converged", True) == (False, None)
    # a pass with the fuller fit short stands: more iterations only gain more
    assert _judged(True, "converged", "max_iter", False) == (True, None)
    assert _judged(False, "converged", "max_iter", True)[0] is None
    # a diverged trial is a failure, not a budget stop: its fail stands
    assert _judged(False, "converged", "diverged", True) == (False, None)
    assert _judged(False, "converged", "converged", False)[0] is None
    assert _judged(True, "max_iter", "converged", True)[0] is None
    assert _judged(False, "max_iter", "converged", True) == (False, None)


def test_a_gain_over_a_short_caller_fit_is_not_judged(biso_pair):
    """``predict_then_verify``: a caller's fit stopped on its budget may gain
    by continuing, so a pass over it is not judged (WP-2220)."""
    from rietx.report import predict_then_verify

    ref, _ = biso_pair
    data = _poisson(_lab6(0.5), 17)
    short = ref.branch()
    short.set_values({"phases.0.cell.a": 4.1586})
    short.run_stage(data, rx.Stage("all", BASE, max_iter=1), telemetry=False)
    assert short.result_.status == "max_iter"
    action = rx.SuggestedAction(kind="refine_biso", confidence=0.9,
                                rationale="test", parameter_paths=[BISO])
    out = predict_then_verify(short, data, action)
    assert out.observed_delta_chi2 > 0.01 * short.result_.statistics.chi2
    assert out.accepted is None
    assert "not judged" in out.reason and "caller's fit" in out.reason
    # and on the converged caller the same action is judged, and passes
    out = predict_then_verify(ref, data, action)
    assert out.accepted is True and out.reason.endswith("accepted")


PEAK = [f"instrument.extra_components.0.{n}" for n in ("area", "center", "fwhm")]


def _absent_peak(seed, **stage_kw):
    """#1686: a peak declared at area 0 over a pattern that has none."""
    from rietx.schemas.instrument import PeakComponent

    data = _poisson(_lab6(), seed)
    peak = PeakComponent(
        label="declared, absent",
        center=rx.Parameter(value=46.0, min=45.5, max=46.5, unit="deg"),
        area=rx.Parameter(value=0.0, min=0.0, unit="counts*deg"),
        fwhm=rx.Parameter(value=0.08, min=0.005, max=0.5, unit="deg"))
    ref = _fit(_lab6(), _lab6_instrument([peak]), data)
    full = ref.branch()
    full.run_stage(data, rx.Stage("peak", BASE + PEAK), telemetry=False, **stage_kw)
    _plot(full.result_, f"1686_seed{seed}")
    return full, compare_freed(ref, full)


def _projected(c, full):
    """``at_bound`` is the fuller fit's own row: set-equal, never re-tested."""
    rows = {p.path: p.at_bound for p in full.result_.parameters}
    return {p.path for p in c.freed if p.at_bound} == {
        p.path for p in c.freed if rows[p.path]}


def test_a_peak_the_fit_could_not_move_names_its_dead_columns():
    full, c = _absent_peak(1)
    assert c.chi2_full == c.chi2_restricted and c.diagnostics == []
    rows = {p.path.rsplit(".", 1)[1]: p for p in c.freed}
    assert rows["area"].at_bound is True and rows["area"].t_ratio == 0.0
    assert rows["area"].t_reason is None
    for name in ("center", "fwhm"):
        assert rows[name].esd is None and rows[name].t_ratio is None
        assert "no gradient" in rows[name].t_reason
    assert c.n_added == 3 and c.n_identified == 0
    assert _projected(c, full)


def test_a_position_on_its_bound_is_marked():
    # the absent peak's centre reaches its bound on the 1e-9 stop's crawl; the
    # shift test stops at its start, 46.0, so this fixture keeps the old stop
    # (WP-2317 R6)
    full, c = _absent_peak(7, shift_over_esd_tol=None)
    rows = {p.path.rsplit(".", 1)[1]: p for p in c.freed}
    assert rows["center"].value == pytest.approx(46.5)
    assert rows["center"].at_bound is True
    assert rows["center"].t_ratio is not None      # computed, and marked
    assert c.n_identified == 2
    assert _projected(c, full)
