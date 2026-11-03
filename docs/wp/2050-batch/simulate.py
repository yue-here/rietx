"""WP-2050: the guard fed statistics.resolved_correlation's matrix, in-process.

Wraps refine.check_guards so the guard reads the correlation with every
direction under FD_STEP^2 x |lambda|max projected out.  Prints per-standard
warning counts under 1e-14 scale nudges, with the rule off and on.
usage: simulate.py WORKTREE STANDARDS K[,K...] MODE(off|on)"""
import dataclasses
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, sys.argv[1])
import rietx as rx  # noqa: E402
from rietx.viz import compare  # noqa: E402

R = sys.modules["rietx.refine"]
keys = sys.argv[2].split(",")
ks = [int(k) for k in sys.argv[3].split(",")]
MODE = sys.argv[4]
orig = R.check_guards
log = []


def wrap(table, outcome, *a, **kw):
    if MODE == "on" and outcome.correlation is not None and outcome.jac is not None \
            and not outcome.n_aux:
        from rietx.optimize.least_squares import covariance_jacobian
        free = table.free_paths
        jac = covariance_jacobian(outcome, free)
        from rietx.optimize.statistics import resolved_correlation
        corr, member = resolved_correlation(outcome.correlation, jac)
        if member.any():
            log.append([free[i] for i in np.flatnonzero(member)])
        outcome = dataclasses.replace(outcome, correlation=corr)
    return orig(table, outcome, *a, **kw)


R.check_guards = wrap
data_dir = compare.default_data_dir()
for key in keys:
    st = compare.STANDARD_BY_KEY[key]
    if not st.available(data_dir):
        print(key, "unavailable")
        continue
    for k in ks:
        log.clear()
        inputs = st.build(data_dir)
        inputs.structure.phases[0].scale.value *= (1 + k * 1e-14)
        ref = rx.Refinement(inputs.structure, inputs.instrument, history=False)
        r = ref.fit(inputs.data, plan=inputs.plan, telemetry=False,
                    two_theta_limits=inputs.two_theta_limits)
        warn = [d for d in r.diagnostics if d.level == "warning"]
        c = Counter(d.code for d in warn)
        members = sorted({p.split(".")[-1] for m in log for p in m})
        print(f"{key} {MODE} k={k:+d} rwp={r.statistics.rwp:.10f} nwarn={len(warn)} "
              f"HC={c.get('HIGH_CORRELATION', 0)} FLAT={c.get('FLAT_DIRECTION', 0)} "
              f"members={members}", flush=True)
        for d in warn:
            if d.code == "HIGH_CORRELATION":
                print(f"    {d.message[:110]}", flush=True)
