"""Row 4: suite_alarms' own firing_table/differences with brucite's start scale nudged.

usage: row4_repro.py WORKTREE KBRUCITE   (scale x (1 + k e-14); every other standard unnudged)
"""
import sys

sys.path.insert(0, sys.argv[1])
import rietx as rx  # noqa: E402
from rietx.viz import compare  # noqa: E402
from tests import suite_alarms  # noqa: E402

kb = int(sys.argv[2])
data_dir = compare.default_data_dir()
out = {}
for standard in compare.STANDARDS:
    if not standard.available(data_dir):
        continue
    inputs = standard.build(data_dir)
    if standard.key == "brucite":
        inputs.structure.phases[0].scale.value *= (1 + kb * 1e-14)
    ref = rx.Refinement(inputs.structure, inputs.instrument, history=False)
    out[standard.key] = ref.fit(inputs.data, plan=inputs.plan, telemetry=False,
                                two_theta_limits=inputs.two_theta_limits)
measured = suite_alarms.firing_table(out)
moved = suite_alarms.differences(suite_alarms.load_pin(), measured)
print(f"brucite k={kb:+d}: {len(moved)} moved")
for m in moved:
    print("  ", m)
b = out["brucite"]
for p in b.parameters:
    if p.path.split(".")[-1] in ("lor_size", "lor_strain", "gauss_size", "gauss_strain", "w", "x", "y"):
        print(f"   {p.path} {p.value!r} plain esd {p.stderr_uncorrected!r}")
print("   brucite rwp", repr(b.statistics.rwp))
