"""Staged plan against fewer stages, on the comparison standards.

Arms (the plan each fit runs):
  shipped        the standard's staged plan, closing stage on (the default)
  staged         the same stages, no closing stage
  single         one stage freeing every glob the plan frees, no closing stage
  single+2pc     that one stage, then a re-solve recompiled at 2 % windows
  single+close   that one stage, then the default closing stage (0.1 % windows)
  two            positions first (scale, background, zero, displacement, cell),
                 then everything; no closing stage
  two+2pc        the same, then a re-solve recompiled at 2 % windows
  staged:I,F     the staged plan, no closing stage, intermediate ftol I and
                 the last stage's ftol F
  single:F       the one stage at ftol F, no closing stage

Starts: the standard's own; cell lengths scaled by +0.1, -0.1 and +0.3 %;
profile W and X times 4 and over 4; "warm" (the models a shipped fit has just
converged); "edit" (converged without the plan's last stage, which the timed
fit then frees).

  probe.py OUT.jsonl [standards,comma] [starts;semicolon] [arms;semicolon]

One JSON line per fit, appended to OUT.jsonl.  Fits run one at a time.  The
"own", "warm" and "edit" starts keep the faster of two runs.  Run it with
RIETX_TELEMETRY=0.  WP-2224 § Measured has the results; summarise.py reduces
the JSON lines to summary.txt.
"""
import json
import sys
import time
import warnings

from rietx.refine import Refinement
from rietx.strategy.staged import RefinementPlan, Stage
from rietx.viz import compare

warnings.simplefilter("ignore")
OUT = sys.argv[1]
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else None
REPEATS = 2

POSITION = ("phases.*.scale", "instrument.background", "instrument.zero_shift",
            "instrument.geometry.sample_displacement", "phases.*.cell")


def _all(plan: RefinementPlan) -> Stage:
    globs = list(dict.fromkeys(g for s in plan.stages for g in s.turn_on))
    return Stage("all", globs,
                 max_iter=max(s.max_iter for s in plan.stages),
                 seed=max(s.seed for s in plan.stages),
                 strain_seed=max(s.strain_seed for s in plan.stages))


def single(plan: RefinementPlan, closing) -> RefinementPlan:
    return RefinementPlan(stages=[_all(plan)], closing_window_tol=closing)


def two(plan: RefinementPlan, closing) -> RefinementPlan:
    first = [g for s in plan.stages for g in s.turn_on
             if g.startswith(POSITION)]
    first = list(dict.fromkeys(first))
    return RefinementPlan(stages=[Stage("positions", first), _all(plan)],
                          closing_window_tol=closing)


def arm_plan(arm: str, plan: RefinementPlan) -> RefinementPlan:
    if arm == "shipped":
        return plan
    if arm == "staged":
        plan.closing_window_tol = None
        return plan
    if arm == "single":
        return single(plan, None)
    if arm == "single+2pc":
        return single(plan, 2e-2)
    if arm == "single+close":
        return single(plan, plan.closing_window_tol)
    if arm == "two":
        return two(plan, None)
    if arm == "two+2pc":
        return two(plan, 2e-2)
    if arm.startswith("staged:"):       # staged:<intermediate ftol>,<final ftol>
        inter, final = (float(x) for x in arm[7:].split(","))
        plan.closing_window_tol = None
        plan.intermediate_ftol = inter
        plan.stages[-1].ftol = final
        return plan
    if arm.startswith("single:"):       # single:<ftol>, no closing stage
        out = single(plan, None)
        out.stages[-1].ftol = float(arm[7:])
        return out
    raise KeyError(arm)


def perturb(start: str, inputs) -> None:
    if start in ("own", "warm", "edit"):
        return
    if start.startswith("cell"):
        f = 1.0 + float(start[4:]) / 100.0
        for phase in inputs.structure.phases:
            for ax in ("a", "b", "c"):
                getattr(phase.cell, ax).value *= f
        return
    if start.startswith("w"):
        f = float(start[2:])
        f = f if start[1] == "x" else 1.0 / f
        inputs.instrument.profile.w.value *= f
        inputs.instrument.profile.x.value *= f
        return
    raise KeyError(start)


ARMS = ("shipped", "staged", "single", "single+2pc", "single+close", "two", "two+2pc")
STARTS = ("own", "warm", "cell+0.1", "cell+0.3", "cell-0.1", "wx4", "w/4")
if len(sys.argv) > 3 and sys.argv[3]:
    STARTS = tuple(sys.argv[3].split(";"))
if len(sys.argv) > 4 and sys.argv[4]:
    ARMS = tuple(sys.argv[4].split(";"))


def one(std, start, arm, data_dir):
    inputs = std.build(data_dir)
    perturb(start, inputs)
    ref = Refinement(inputs.structure, inputs.instrument, history=False)
    kw = dict(two_theta_limits=inputs.two_theta_limits)
    if start == "warm":
        ref.fit(inputs.data, plan=std.build(data_dir).plan, **kw)
    if start == "edit":      # converge without the plan's last stage, then free it
        pre = std.build(data_dir).plan
        pre.stages = pre.stages[:-1]
        pre.closing_window_tol = None
        ref.fit(inputs.data, plan=pre, **kw)
    plan = arm_plan(arm, std.build(data_dir).plan)
    t0 = time.perf_counter()
    try:
        res = ref.fit(inputs.data, plan=plan, **kw)
        err = None
    except Exception as exc:  # a failed arm is a finding
        res, err = None, f"{type(exc).__name__}: {exc}"[:300]
    return time.perf_counter() - t0, res, err


data_dir = compare.default_data_dir()
with open(OUT, "a", encoding="utf-8") as fh:
    for std in compare.STANDARDS:
        if ONLY and std.key not in ONLY:
            continue
        if not std.available(data_dir):
            print("missing", std.key, flush=True)
            continue
        for start in STARTS:
            for arm in ARMS:
                best = None
                for _ in range(REPEATS if start in ("own", "warm", "edit") else 1):
                    got = one(std, start, arm, data_dir)
                    if best is None or got[0] < best[0]:
                        best = got
                dt, res, err = best
                row = {"standard": std.key, "start": start, "arm": arm,
                       "seconds": dt, "error": err}
                if res is not None:
                    st = res.statistics
                    row.update(
                        status=res.status, rwp=st.rwp, gof=st.gof, chi2=st.chi2,
                        n_free=st.n_free_parameters,
                        nfev=[s.n_iterations for s in res.stages],
                        cost0=res.stages[0].cost_initial,
                        stage_names=[s.name for s in res.stages],
                        stage_status=[s.status for s in res.stages],
                        codes=sorted({d.code for d in res.diagnostics
                                      if d.level in ("warning", "error")}),
                        params={p.path: [p.value, p.stderr] for p in res.parameters},
                    )
                fh.write(json.dumps(row, default=str) + "\n")
                fh.flush()
                print(std.key, start, arm, f"{dt:.2f}s",
                      err or f"{res.status} rwp={res.statistics.rwp:.5f} "
                             f"nfev={sum(s.n_iterations for s in res.stages)}",
                      flush=True)
