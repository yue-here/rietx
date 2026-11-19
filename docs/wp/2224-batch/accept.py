"""WP-2224 § Acceptance on the eight comparison standards.

For each standard: a first fit with its plan, then from that answer a second
``fit`` with the same plan under the default (``refit="single"``) and, from the
same answer again, under ``refit="stages"``.  Reported per standard: the
stages each ran, the largest gap of the one-stage answer from the first fit's
in units of the first fit's esd, and the evaluations of the one stage over
the staged re-fit's.

  accept.py [closing]

With no argument every plan keeps its own closing stage (the default before
WP-2222); ``closing=off`` sets ``closing_window_tol=None`` on every plan.
Run with RIETX_TELEMETRY=0.
"""
import sys
import time
import warnings

from rietx.refine import Refinement
from rietx.viz import compare

warnings.simplefilter("ignore")
DATA = compare.default_data_dir()
OFF = len(sys.argv) > 1 and sys.argv[1] == "closing=off"


def plan_of(std):
    plan = std.build(DATA).plan
    if OFF:
        plan.closing_window_tol = None
    return plan


def evals(res):
    return sum(s.n_iterations for s in res.stages)


for std in compare.STANDARDS:
    if not std.available(DATA):
        print(std.key, "missing")
        continue
    inputs = std.build(DATA)
    kw = dict(two_theta_limits=inputs.two_theta_limits)
    ref = Refinement(inputs.structure, inputs.instrument)
    first = ref.fit(inputs.data, plan=plan_of(std), **kw)
    t0 = time.perf_counter()
    one = ref.fit(inputs.data, plan=plan_of(std), **kw)
    t_one = time.perf_counter() - t0
    ref.checkout(first.node_id)
    t0 = time.perf_counter()
    staged = ref.fit(inputs.data, plan=plan_of(std), refit="stages", **kw)
    t_staged = time.perf_counter() - t0
    ref_p = {p.path: p for p in first.parameters}
    gaps = sorted(((abs(p.value - ref_p[p.path].value) / ref_p[p.path].stderr, p.path)
                   for p in one.parameters
                   if p.path in ref_p and ref_p[p.path].stderr), reverse=True)
    sgaps = sorted(((abs(p.value - ref_p[p.path].value) / ref_p[p.path].stderr, p.path)
                    for p in staged.parameters
                    if p.path in ref_p and ref_p[p.path].stderr), reverse=True)
    fell = any(d.code == "WARM_REFIT_REJECTED" for d in one.diagnostics)
    print(f"{std.key:15} first {first.status} rwp {first.statistics.rwp:.5f} | "
          f"one {[s.name for s in one.stages]} {one.status} rwp {one.statistics.rwp:.5f} "
          f"fell_back={fell} max gap {gaps[0][0]:.3f} esd ({gaps[0][1]}) | "
          f"staged max gap {sgaps[0][0]:.3f} esd ({sgaps[0][1]}) | "
          f"evals {evals(one)}/{evals(staged)} = {evals(one) / evals(staged):.2f} | "
          f"seconds {t_one:.2f}/{t_staged:.2f}", flush=True)
