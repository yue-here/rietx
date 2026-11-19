"""WP-1535 — a direction the covariance discards must not read as measured.

``pinv`` drops an eigenvalue under ``PINV_RCOND × λmax`` and the direction comes
back at zero variance, so a combination of columns the data cannot move reports
the variance of what it *could* move.  A pair of such columns is already a
``FLAT_DIRECTION``; a combination of three has no pairwise ρ to show for it.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Refinement
from rietx.multi import MultiHistogramRefinement
from rietx.optimize.statistics import discarded_directions
from rietx.refine import _REVISABLE_CODES, _guard_diagnostics
from rietx.strategy.staged import (
    GuardFinding,
    GuardReport,
    RefinementPlan,
    Stage,
    check_discarded_directions,
)
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("discarded-direction")


def _jac(n=400, seed=0):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, 5))


def test_independent_columns_discard_nothing():
    n, touched = discarded_directions(_jac())
    assert n == 0 and len(touched) == 0


def test_a_sum_of_two_columns_is_a_combination_no_pair_shows():
    """c = a + b exactly: pairwise |ρ| is 0.71, the direction is not measured."""
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    jj = j.T @ j
    rho = jj / np.sqrt(np.outer(np.diag(jj), np.diag(jj)))
    assert np.abs(rho[np.triu_indices(5, 1)]).max() < 0.9  # no FLAT_DIRECTION
    n, touched = discarded_directions(j)
    assert n == 1
    assert list(touched) == [0, 1, 4]


def test_a_column_the_direction_barely_loads_on_is_not_touched():
    """The bar is the reported variance: a 1e-9 loading adds ~1e-18/cut, far
    under what the kept directions say, so column 3 is not named."""
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1] + 1e-9 * j[:, 3]
    n, touched = discarded_directions(j)
    assert n == 1
    assert list(touched) == [0, 1, 4]


def test_the_touched_set_does_not_depend_on_a_columns_units():
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    k = j * np.array([1.0, 1e6, 1.0, 1e-4, 1.0])
    assert list(discarded_directions(k)[1]) == [0, 1, 4]


def test_a_dead_column_is_not_this_findings_business():
    j = _jac()
    j[:, 2] = 0.0
    assert discarded_directions(j)[0] == 0


def test_a_pair_flat_direction_already_reported_adds_no_row():
    j = _jac()
    j[:, 4] = j[:, 0]
    free = [f"p{i}" for i in range(5)]
    flat = [GuardFinding.flat_direction("p0", "p4", 1.0)]
    assert check_discarded_directions(j, free, flat) == []
    (row,) = check_discarded_directions(j, free, [])
    assert row.code == "COVARIANCE_DIRECTION_DISCARDED"
    assert set(row.paths) == {"p0", "p4"}


def test_the_row_names_its_paths_and_the_diagnostic_carries_them():
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    free = [f"phases.0.q{i}" for i in range(5)]
    findings = check_discarded_directions(j, free, [])
    assert [f.paths for f in findings] == [("phases.0.q0", "phases.0.q1",
                                            "phases.0.q4")]
    diags = _guard_diagnostics(GuardReport(discarded_directions=findings))
    (d,) = [d for d in diags if d.code == "COVARIANCE_DIRECTION_DISCARDED"]
    assert d.where == ["phases.0.q0", "phases.0.q1", "phases.0.q4"]
    assert d.level == "warning"


def test_the_code_is_retaken_on_the_answer_stage_not_accumulated():
    """An earlier stage's cut is not the matrix the result's esds came from, and
    an unkeyed code is appended once per stage."""
    assert "COVARIANCE_DIRECTION_DISCARDED" in _REVISABLE_CODES


# ------------------------------------------------------------ WP-2219 -----
# A parameter a discarded direction touches reports no esd, in every runner.

def _three_way_zero(mode: str):
    """``zero_shift = za + zb + zc``, all three free: two exact directions, and
    pairwise |ρ| = 0.5, so no ``FLAT_DIRECTION`` covers them."""
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)
    for name in ("za", "zb", "zc"):
        ref.add_variable(name, 0.0, vary=True)
    ref.tie("instrument.zero_shift", {"vars.za": 1.0, "vars.zb": 1.0, "vars.zc": 1.0})
    plan = RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*",
                                         "vars.*"]),
        Stage(name="cell", turn_on=["phases.*.cell.*", "instrument.profile.w"]),
    ])
    return ref.fit(synthesize(), plan=plan, mode=mode)


@pytest.mark.parametrize("mode", ["rietveld", "pawley"])
def test_a_combination_the_data_cannot_see_has_no_esd(mode):
    """The three variables, and the tie built on them, report no esd; the cell
    beside them keeps its own.  A Pawley solve's intensity block is in the
    matrix the guard reads, so its finding is named too."""
    result = _three_way_zero(mode)
    rows = {p.path: p for p in result.parameters}
    for path in ("vars.za", "vars.zb", "vars.zc", "instrument.zero_shift"):
        assert rows[path].stderr is None, path
    assert rows["phases.0.cell.a"].stderr > 0.0
    (d,) = [d for d in result.diagnostics if d.code == "COVARIANCE_DIRECTION_DISCARDED"]
    assert set(d.where) == {"vars.za", "vars.zb", "vars.zc"}
    assert "no esd" in d.message


def test_a_joint_fit_gives_an_exact_pair_no_esd():
    """Two identical phases: each pattern's two scales are one quantity."""
    structure, ins = perturbed_models()
    twin = structure.phases[0].model_copy(deep=True)
    twin.name = "LaB6 twin"
    structure.phases.append(twin)
    data = synthesize()
    mr = MultiHistogramRefinement(structure, [ins, ins.model_copy(deep=True)])
    result = mr.fit([data, data], plan=RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"])]))
    rows = {p.path: p for p in result.parameters}
    for h in (0, 1):
        for ip in (0, 1):
            assert rows[f"hist.{h}.phases.{ip}.scale"].stderr is None
        assert rows[f"hist.{h}.instrument.background.c0"].stderr > 0.0
