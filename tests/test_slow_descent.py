"""The slow-descent rule (WP-1334, issue #222): a stage stops once the rest of
its budget would buy less than one esd of travel, and says so.

The rule is ``optimize.lm.SLOW_DESCENT_ESD``'s.  A stage the rule stops ends
``slow_descent`` with status ``max_iter``, and ``STAGE_MAX_ITER`` names it as
cut by the rule rather than by the budget.

The crawls here are made by handing the driver a Jacobian ``f`` times too
large, so every Gauss-Newton step is ``1/f`` of the true one and the cost
falls at a steady, slow rate.  A floor of 1000 constant residual rows sets
χ²_red near 1, so the rule's threshold is about one unit of S.  Two shapes:

- **for nothing**: a gap of 10 above the floor at ``f`` = 1e4.  Run to its
  budget, it ends 1040.2 and is still crawling; the rule stops it at 281
  evaluations, 1041.2, giving up 0.97 against a χ²_red of 1.04.
- **a rescue**: a gap of 1e4 at ``f`` = 1e3.  It halves S over its
  budget, so every window lowers S by far more than χ²_red, and it runs to
  the budget as before.

Measured on 2026-11-03 (macOS arm64, worktree ``[dev]`` venv).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.optimize import lm
from rietx.refine import _max_iter_diagnostics
from rietx.schemas.results import StageResult

FLOOR_ROWS = 1000


def _crawl(f: float, gap: float):
    t = np.linspace(0.0, 1.0, 50)
    y = 2.0 * t + 1.0
    floor = np.ones(FLOOR_ROWS)
    w = np.sqrt(gap / t.size)

    def residual(x):
        return np.concatenate([w * (x[0] * t + x[1] - y), floor])

    def jacobian(x):
        J = np.zeros((t.size + FLOOR_ROWS, 2))
        J[: t.size, 0] = w * t * f
        J[: t.size, 1] = w * f
        return J

    return residual, jacobian


def _solve(f, gap, esd, monkeypatch, max_nfev=400):
    monkeypatch.setattr(lm, "SLOW_DESCENT_ESD", esd)
    residual, jacobian = _crawl(f, gap)
    return lm.minimize(residual, jacobian, np.zeros(2), lo=np.full(2, -np.inf),
                       hi=np.full(2, np.inf), max_nfev=max_nfev)


def test_a_crawl_for_nothing_stops_and_gives_up_less_than_an_esd(monkeypatch):
    spent = _solve(1e4, 10.0, None, monkeypatch)
    assert spent.termination == "max_nfev" and spent.nfev == 400

    cut = _solve(1e4, 10.0, 1.0, monkeypatch)
    assert cut.termination == "slow_descent"
    assert cut.status == 0, "a stop the rule makes is never convergence"
    # past the first whole window and well short of the budget
    assert 400 // lm._SLOW_DESCENT_WINDOW < cut.nfev < 400
    # the claim: what the rest of the budget bought is under chi2_red
    s_cut, s_spent = 2.0 * cut.cost, 2.0 * spent.cost
    chi2_red = s_spent / (FLOOR_ROWS + 50 - 2)
    assert 0.0 < s_cut - s_spent < chi2_red


def test_a_crawl_that_rescues_the_fit_still_runs(monkeypatch):
    off = _solve(1e3, 1e4, None, monkeypatch)
    on = _solve(1e3, 1e4, 1.0, monkeypatch)
    assert on.termination == off.termination == "max_nfev"
    assert on.nfev == off.nfev == 400
    np.testing.assert_array_equal(on.x, off.x)
    # it did rescue something: S fell by half, thousands of chi2_red
    residual, _ = _crawl(1e3, 1e4)
    r0 = residual(np.zeros(2))
    assert 2.0 * on.cost < 0.5 * float(r0 @ r0)


def test_a_stage_that_converges_inside_the_window_is_untouched(monkeypatch):
    off = _solve(1.0, 1.0, None, monkeypatch)
    on = _solve(1.0, 1.0, 1.0, monkeypatch)
    assert on.termination == off.termination != "slow_descent"
    np.testing.assert_array_equal(on.x, off.x)


@pytest.mark.parametrize("trace, fires", [
    # a steady crawl: 1e-3 of S per window of 100, chi2_red = 1
    ([(1, 1000.0), (101, 999.9), (150, 999.88)], True),
    # still falling by several chi2_red a window
    ([(1, 1000.0), (101, 990.0), (150, 985.0)], False),
    # before a whole window has passed, nothing is read
    ([(1, 1000.0), (90, 1000.0)], False),
])
def test_the_rule_reads_the_last_window_in_evaluations(trace, fires):
    at, s = [n for n, _ in trace], [v for _, v in trace]
    assert lm._descent_too_slow(at, s, at[-1], 400, n_dof=1000) is fires


def test_the_rule_switched_off_reads_nothing(monkeypatch):
    monkeypatch.setattr(lm, "SLOW_DESCENT_ESD", None)
    assert not lm._descent_too_slow([1, 101, 150], [1000.0, 1000.0, 1000.0],
                                    150, 400, n_dof=1000)


def _stage(name, termination):
    status = "converged" if termination == "ftol_runs" else "max_iter"
    return StageResult(name=name, status=status, n_iterations=400,
                       cost_initial=1.0, cost_final=1.0, termination=termination)


def test_stage_max_iter_says_which_stop_the_rule_made():
    [d] = _max_iter_diagnostics([_stage("scale", "ftol_runs"),
                                 _stage("biso", "slow_descent")])
    assert d.code == "STAGE_MAX_ITER"
    assert "'biso' stopped early" in d.message
    assert "budget." not in d.message

    [both] = _max_iter_diagnostics([_stage("biso", "slow_descent"),
                                    _stage("profile", "max_nfev")])
    assert "'profile' stopped on its iteration budget." in both.message
    assert "'biso' stopped early" in both.message

    # a record stored before the field reads as a budget stop, as it was
    [old] = _max_iter_diagnostics([_stage("profile", None)])
    assert old.message == "Stage 'profile' stopped on its iteration budget."
