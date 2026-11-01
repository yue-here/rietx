"""Row 4: per-standard warning counts under a 1e-14 relative nudge to one start value.

usage: row4_probe.py WORKTREE STANDARD[,STANDARD...] K[,K...] [TARGET [MAG]]
TARGET: 'cell_a' (phases.0.cell.a, default) or 'scale' (phases.0.scale), each
multiplied by (1 + k*MAG); MAG defaults to 1e-14
"""
import sys
from collections import Counter

sys.path.insert(0, sys.argv[1])
import rietx as rx  # noqa: E402
from rietx.viz import compare  # noqa: E402

keys = sys.argv[2].split(",")
ks = [int(k) for k in sys.argv[3].split(",")]
target = sys.argv[4] if len(sys.argv) > 4 else "cell_a"
MAG = float(sys.argv[5]) if len(sys.argv) > 5 else 1e-14
data_dir = compare.default_data_dir()

for key in keys:
    st = compare.STANDARD_BY_KEY[key]
    for k in ks:
        inputs = st.build(data_dir)
        if target == "cell_a":
            p = inputs.structure.phases[0].cell.a
            p.value = p.value * (1 + k * MAG)
        elif target == "scale":
            p = inputs.structure.phases[0].scale
            p.value = p.value * (1 + k * MAG)
        else:
            raise SystemExit(f"unknown TARGET {target!r}: 'cell_a' or 'scale'")
        ref = rx.Refinement(inputs.structure, inputs.instrument, history=False)
        r = ref.fit(inputs.data, plan=inputs.plan, telemetry=False,
                    two_theta_limits=inputs.two_theta_limits)
        warn = [d for d in r.diagnostics if d.level == "warning"]
        wpr = rx.diagnostics_summary([r]).warnings_per_result
        c = Counter(d.code for d in warn)
        print(f"{key} {target} k={k:+d} rwp={r.statistics.rwp:.12f} nwarn={len(warn)} "
              f"wpr_cal={wpr.get('calibration')} codes={dict(sorted(c.items()))}", flush=True)
        for d in warn:
            if d.code in ("HIGH_CORRELATION", "FLAT_DIRECTION", "FLOOR_HIT", "BOUND_HIT"):
                print(f"   {d.code} {d.where} {d.message[:90]}", flush=True)
