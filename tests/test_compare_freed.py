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

import pytest

import rietx as rx
from rietx.optimize.statistics import effective_sample_size
from rietx.report import compare_freed
from tests.test_fitreport_layers import _truth

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
    # a moved value drops the result, so held values are never read off a
    # table that has left its fit
    ref.set_values({"instrument.zero_shift": 0.05})
    with pytest.raises(RuntimeError, match="run a fit on the restricted"):
        compare_freed(ref, trial)
