"""Iteration budgets a converging fit never reaches (WP-2002, batch item B11).

Three numbers bound how much work one stage may do.  ``StageSpec.max_iter``
(100) is multiplied by ``NFEV_PER_ITERATION`` (4) into the only cap either
driver applies, a budget of residual evaluations (400).  Inside the default LM
driver, ``_INNER_MAX`` (18) caps the damped trials one outer iteration may try
before it declares that nothing downhill exists.  Each is meant as a runaway
guard: a fit that converges finishes well inside it, so the answer does not
depend on its value.  This file tests that claim under both drivers, LM (the
default) and TRF (``solver="trf"``), and asserts how far inside each budget the
fit stays.

Measured on 2026-10-21 (macOS arm64, worktree venv ``[dev]``, compiled tier
on, dispersion declined) on nine configurations from four laboratories and
instruments, each fitted under the shipped schedule (every stage but the last
at a relative cost decrease of 1e-6): NIST SRM 660c LaB6 and the GSAS-II
fluorapatite tutorial, each under its acceptance protocol and under the
default plan; the CPD round robin's CSIRO instrument (cpd-1a, cpd-1a under the
default plan, pure corundum, and cpd-1a with zircon, a phase not in the
sample); and 11-BM NAC, its Le Bail pass included.  The largest use of each
budget over every stage, and the margin it leaves:

====================================  ==========================  ==========================
budget                                LM: largest use (margin)    TRF: largest use (margin)
====================================  ==========================  ==========================
evaluations, 400 a stage              49 (8.2x), corundum         47 (8.5x), corundum
iterations against max_iter = 100     48 (2.1x), corundum         46 (2.2x), corundum
evaluations per iteration, 4          1.39 (2.9x), cpd-1a+zircon  1.79 (2.2x), cpd-1a
LM trials in one iteration, 18        9 (2.0x), see below         (no such loop)
====================================  ==========================  ==========================

The per-iteration rate is the stage's evaluations after the first, over its
iterations, for stages of five iterations or more.  A stage of two to four
iterations that ends at its minimum spends several rejected trials in its last
one and reads up to 3.5 a stage, at under 30 evaluations.  The LM trial count
is the largest number of damped trials one outer iteration tried.  An
iteration that took a step tried at most 6 (3.0x).  A stage's last iteration,
which finds no step, tried up to 9 (2.0x), so 2x is the margin.  No stage ever
ran its trials out: every LM stage ended on three small steps (``ftol_runs``)
or on a predicted decrease below the fp64 floor (``exhausted_fp64``).

The iteration row is not asserted.  Neither driver counts iterations, so a
stage that runs past ``max_iter`` iterations at one evaluation each is not
stopped until it has spent 400 evaluations.  With every stage converged to
1e-9 (``intermediate_ftol=None``), a stage ran 110 iterations under LM on
cpd-1a under the default plan, and converged.

Two readings the table does not cover, both off the shipped schedule:

- With every stage converged to 1e-9, one stage did hit the budget.  On cpd-1a
  with zircon under LM, the absent zircon's scale stays above the hold's
  threshold, its cell walks, and ``lines_axial`` spends 400 evaluations in 298
  iterations at λ up to 2.3e4 (``STAGE_MAX_ITER``).  The next stage converges
  at 323 of 400.  That is the guard catching a flat direction, as designed,
  but it means the margin under that schedule is 1.2x on a converging stage.
- A single all-free stage at 1e-9, the shape ``run_stage`` runs, used up to
  107 evaluations in 98 iterations (LM, the same zircon fit, polished): 3.7x on
  evaluations, 1.0x on iterations.

The test fits cpd-1a under its QPA protocol, which exercises every budget at
or near its worst: a 45-iteration ridge walk in the cell stage, LM trials up
to 6 in ``lines_axial``, and TRF's highest rejection rate in ``biso``.  On
cpd-1a the margins are 8.7x (LM) and 9.1x (TRF) on evaluations, 3.3x and 2.2x
on the rate, and 3.0x on LM trials in a stepping iteration.  The asserted
margins are 4x on evaluations, about half the measured one, so a platform's
few extra iterations cannot fail it and a doubling of the ridge walk does;
1.5x on the rate, since TRF's measured 2.2x was taken on darwin/arm64 alone and
2x would leave it 12 % to spare (1.79 against 2) for another platform's
rejected trials; and 2x on LM trials.  The invariance tests refit with each budget cut to its asserted
margin and require the same answer to the last bit.

The tolerance half of this file's name has no test.  WP-2002's B7 asked for
the intermediate tolerance (1e-6 against 1e-9) to move no non-degenerate
parameter by more than 0.03 of its plain esd, with the same held set.  On
cpd-1a it moved the trace corundum's scale, cell and Biso by 0.033 (LM) and
0.074 (TRF) of an esd, and with zircon added the hold fired in one schedule
and not the other, so the item went back to the maintainer unasserted.

Made to fail once each, on 2026-10-21, by editing a margin and reverting it.
With ``EVALUATION_MARGIN`` at 10, the first test fired on LM's ``zero_disp``
at 41 evaluations against a limit of 40, and the budget cut to 10 iterations
(40 evaluations) stopped ``zero_disp`` and ``cell`` at ``max_iter`` under LM
and ``cell`` under TRF, so the second test fired too.  With ``RATE_MARGIN`` at
4, the first test fired on LM's ``lines_axial`` at 1.22 evaluations an
iteration against 1, and on TRF's ``sample_broadening`` at 1.38.  With
``TRIAL_MARGIN`` at 4, it fired on LM's ``lines_axial`` at 6 trials against
4.5.  The cut to 4 trials an iteration also moved the answer: ``lines_axial``
stopped after 5 evaluations instead of 29, so the third test fired.  The
trial cap's margin therefore lies between 18/4 and 18/2.

Dispersion is **declined**, inherited from ``qarr_instrument`` and restated
below.  The compiled tier is switched on explicitly, since the counts were
measured on it.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import rietx as rx
from rietx.model import compiled
from rietx.optimize import lm
from rietx.optimize.least_squares import NFEV_PER_ITERATION
from tests.test_acceptance_qpa_roundrobin import (
    DATA,
    corundum_phase,
    fluorite_phase,
    qarr_instrument,
    qpa_plan,
    seed_scales,
    zincite_phase,
)

lsq = importlib.import_module("rietx.optimize.least_squares")

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("budget-margins")]

OUT = Path(__file__).parent / "output"
#: the shipped ``StageSpec.max_iter``, and the evaluation budget it makes
MAX_ITER = rx.Stage("x", []).max_iter
#: how far inside each budget the fit must stay (measured margins in the
#: module docstring: 8.7x, 2.2x, 2.0x on cpd-1a)
EVALUATION_MARGIN = 4
RATE_MARGIN = 1.5
TRIAL_MARGIN = 2
#: a stage shorter than this spends its last iteration's rejected trials
#: over too few accepted ones for a rate to mean anything
MIN_ITERATIONS_FOR_RATE = 5


class _Meter:
    """Count, per solve, the evaluations and LM trials of each outer iteration.

    One record per driver call.  An iteration starts at each Jacobian
    evaluation; the residual evaluations after it are that iteration's trials.
    LM's curvature probes evaluate the residual too, but ``nfev`` leaves them
    out, so the meter does as well.
    """

    def __init__(self):
        self.solves: list[dict] = []
        self._bucket = None
        self._probing = 0

    def _new_solve(self, max_nfev):
        rec = {"max_nfev": int(max_nfev), "iterations": []}
        self.solves.append(rec)
        return rec

    def _iteration(self, rec):
        self._bucket = {"evaluations": 0, "trials": 0}
        rec["iterations"].append(self._bucket)

    def _count_eval(self):
        if self._bucket is not None and not self._probing:
            self._bucket["evaluations"] += 1

    def install(self, mp: pytest.MonkeyPatch) -> None:
        meter = self
        minimize, solve_step = lm.minimize, lm._solve_step
        curvature, trf = lm._measured_curvature, lsq.least_squares

        def lm_minimize(residual, jacobian, x0, **kw):
            rec = meter._new_solve(kw["max_nfev"])
            meter._bucket = None

            def res(x):
                r = residual(x)
                meter._count_eval()
                return r

            def jac(x):
                meter._iteration(rec)
                return jacobian(x)

            out = minimize(res, jac, x0, **kw)
            rec["iterations"].pop()     # the Jacobian at the returned point
            rec["nfev"] = int(out.nfev)
            rec["termination"] = out.termination
            meter._bucket = None
            return out

        def lm_solve_step(*a, **k):
            if meter._bucket is not None:
                meter._bucket["trials"] += 1
            return solve_step(*a, **k)

        def lm_curvature(*a, **k):
            meter._probing += 1
            try:
                return curvature(*a, **k)
            finally:
                meter._probing -= 1

        def trf_least_squares(fun, x0, jac=None, **kw):
            rec = meter._new_solve(kw["max_nfev"])
            meter._bucket = None

            def f(x):
                r = fun(x)
                meter._count_eval()
                return r

            def j(x, *a):
                meter._iteration(rec)
                return jac(x, *a)

            out = trf(f, x0, jac=j, **kw)
            # scipy evaluates J at each accepted point, the last one included
            while rec["iterations"] and rec["iterations"][-1]["evaluations"] == 0:
                rec["iterations"].pop()
            rec["nfev"] = int(out.nfev)
            rec["termination"] = int(out.status)
            meter._bucket = None
            return out

        mp.setattr(lm, "minimize", lm_minimize)
        mp.setattr(lm, "_solve_step", lm_solve_step)
        mp.setattr(lm, "_measured_curvature", lm_curvature)
        mp.setattr(lsq, "least_squares", trf_least_squares)


@pytest.fixture(scope="module", autouse=True)
def _compiled_tier_on():
    was = compiled.set_enabled(True)
    yield
    compiled.set_enabled(was)


def _fit(solver: str, *, max_iter: int | None = None, inner_max: int | None = None,
         tag: str | None = None):
    path = DATA / "cpd-1a.prn"
    if not path.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(path)
    structure = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase()])
    ins = qarr_instrument()
    ins.source.dispersion = None
    seed_scales(structure, ins, data)
    plan = qpa_plan()
    assert plan.intermediate_ftol == 1e-6   # the shipped schedule
    if max_iter is not None:
        for stage in plan.stages:
            stage.max_iter = max_iter
    meter = _Meter()
    with pytest.MonkeyPatch.context() as mp:
        meter.install(mp)
        if inner_max is not None:
            mp.setattr(lm, "_INNER_MAX", inner_max)
        result = rx.Refinement(structure, ins, history=False, solver=solver).fit(
            data, plan=plan)
    if tag is not None:
        OUT.mkdir(exist_ok=True)
        result.plot(path=str(OUT / f"budget_margins_cpd1a_{tag}.png"))
        import matplotlib.pyplot as plt

        plt.close("all")
    # one driver call per stage: no hold fires on cpd-1a, so no second solve
    assert len(meter.solves) == len(result.stages)
    for stage, solve in zip(result.stages, meter.solves):
        assert solve["nfev"] == stage.n_iterations, stage.name
        assert solve["nfev"] == 1 + sum(i["evaluations"] for i in solve["iterations"])
    return result, meter


@pytest.fixture(scope="module")
def shipped():
    return {solver: _fit(solver, tag=solver) for solver in ("lm", "trf")}


def _answer(result):
    return {p.path: p.value for p in result.parameters}


@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_a_converging_fit_stays_inside_every_budget(shipped, solver):
    result, meter = shipped[solver]
    budget = MAX_ITER * NFEV_PER_ITERATION
    for stage, solve in zip(result.stages, meter.solves):
        assert stage.status == "converged", stage.name
        assert solve["max_nfev"] == budget
        # evaluations: the budget max_iter sets, through NFEV_PER_ITERATION
        assert solve["nfev"] <= budget / EVALUATION_MARGIN, (
            f"{solver} {stage.name}: {solve['nfev']} evaluations against a "
            f"limit of {budget / EVALUATION_MARGIN:g}")
        # the rate NFEV_PER_ITERATION prices
        n_it = len(solve["iterations"])
        if n_it >= MIN_ITERATIONS_FOR_RATE:
            rate = (solve["nfev"] - 1) / n_it
            assert rate <= NFEV_PER_ITERATION / RATE_MARGIN, (
                f"{solver} {stage.name}: {rate:.2f} evaluations an iteration "
                f"against {NFEV_PER_ITERATION / RATE_MARGIN:g}")
        if solver == "lm":
            trials = max(i["trials"] for i in solve["iterations"])
            assert trials <= lm._INNER_MAX / TRIAL_MARGIN, (
                f"lm {stage.name}: {trials} trials in one iteration against "
                f"{lm._INNER_MAX / TRIAL_MARGIN:g}")
            assert solve["termination"] != "no_descent", stage.name


@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_the_answer_is_the_same_with_the_evaluation_budget_cut_to_its_margin(
        shipped, solver):
    """Every stage at ``max_iter`` = 100 / ``EVALUATION_MARGIN`` reaches the
    same answer, bit for bit, at the same per-stage evaluation counts."""
    result, _meter = shipped[solver]
    cut, _ = _fit(solver, max_iter=MAX_ITER // EVALUATION_MARGIN)
    assert [s.status for s in cut.stages] == ["converged"] * len(cut.stages), (
        [(s.name, s.status, s.n_iterations) for s in cut.stages])
    assert [s.n_iterations for s in cut.stages] == [s.n_iterations for s in result.stages]
    assert _answer(cut) == _answer(result)


def test_the_answer_is_the_same_with_lm_trials_cut_to_their_margin(shipped):
    """LM with ``_INNER_MAX`` = 18 / ``TRIAL_MARGIN`` trials an iteration
    reaches the same answer, bit for bit."""
    result, _meter = shipped["lm"]
    cut, meter = _fit("lm", inner_max=lm._INNER_MAX // TRIAL_MARGIN)
    assert [s.n_iterations for s in cut.stages] == [s.n_iterations for s in result.stages]
    assert _answer(cut) == _answer(result)
    assert all(s["termination"] != "no_descent" for s in meter.solves)
