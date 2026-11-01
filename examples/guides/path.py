"""The fits behind `docs/docs/guides/path.md`: is a series trajectory the chain's or the data's?

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: seven synthetic LaB6 patterns from `_lab6_ramp.py` beside this script,
made from a known cell at each temperature.
"""

# guide: start

from _lab6_ramp import TEMPERATURES, TRUE_A, ramp, simulate, starting_model

import rietx as rx

patterns = ramp()
series = rx.refine_sequential(patterns, *starting_model(), plan="mccusker_default",
                              x=TEMPERATURES, x_label="T (K)", direction="both")

print([d.code for d in series.diagnostics])
forward = series.trajectory("phases.0.cell.a")
backward = series.backward.trajectory("phases.0.cell.a")
gap = max(abs(f - b) / e for f, b, e in zip(forward.value, backward.value, forward.stderr))
print(f"largest forward-backward gap: {gap:.2f} esd")
# guide: end

# guide: jump start
jumped = list(patterns)
jumped[4] = simulate(TRUE_A[4] * 1.015, seed=15)  # the 700 K cell 1.5 % larger
series = rx.refine_sequential(jumped, *starting_model(), plan="mccusker_default",
                              x=TEMPERATURES, x_label="T (K)", verify_steps=3)

for s in series.steps[:4]:
    cold = "not refitted" if s.cold_ratio is None else f"cold pair {s.cold_ratio:.2f}x"
    print(f"{s.path} {s.labels[0]}->{s.labels[1]}  {s.step:+.5f}  "
          f"{s.size_esd:,.0f} esd  {cold}")
for entry in series:
    print(f"{entry.label}  {entry.rung}")
# guide: jump end

top = series.steps[:4]
assert [s.path for s in top] == [
    "phases.0.cell.a", "phases.0.cell.b", "phases.0.cell.c", "phases.0.cell.a"]
assert [s.indices for s in top] == [(3, 4)] * 3 + [(4, 5)]
assert [round(s.step, 5) for s in top] == [0.06454] * 3 + [-0.0604]
assert [round(s.size_esd) for s in top] == [15790] * 3 + [-14110], [s.size_esd for s in top]
assert [round(s.cold_ratio, 2) for s in top[:3]] == [1.00] * 3 and top[3].cold_ratio is None
assert sum(s.cold_ratio is not None for s in series.steps) == 3
assert [e.rung for e in series] == [
    "cold", "warm", "warm", "warm", "warm_staged", "cold", "warm"]
# a 1.5 % jump, because 2 % and 3 % left which warm start broke to rounding (WP-2002,
# 2026-10-23).  Since the last declared stage converges (WP-2045) the 800 K warm start,
# the step back down, fails at Rwp 0.941 in all of ten starts nudged by 1e-14, while the
# 700 K one's first attempt read anywhere from 0.04 to 0.95 (Accelerate, 2026-10-25), so
# the page quotes a bound for the 800 K attempt alone
assert series.entries[4].rwp_warm is not None and series.entries[5].rwp_warm > 0.9
# the rescued 700 K fit ends at 0.039494, 6e-6 from where a third decimal flips, so the
# page quotes two
assert all(abs(r - 0.040) < 0.001 for r in series.rwp[4:6]), series.rwp[4:6]
assert gap < 0.005
