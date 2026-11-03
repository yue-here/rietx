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
gaps = series.direction_gaps
print(f"{len(gaps)} gaps, the largest {abs(gaps[0].gap_esd):.2f} esd")
a = next(g for g in gaps if g.path == "phases.0.cell.a" and g.label == "p004")
print(f"cell.a at {a.label}: {a.forward:.5f} vs {a.backward:.5f} "
      f"({a.forward_rung}/{a.backward_rung})")
# guide: end
gap = max(abs(g.gap_esd) for g in gaps if g.gap_esd is not None)

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
assert [round(s.size_esd) for s in top] == [15810] * 3 + [-14062], [s.size_esd for s in top]
assert [round(s.cold_ratio, 2) for s in top[:3]] == [1.00] * 3 and top[3].cold_ratio is None
assert sum(s.cold_ratio is not None for s in series.steps) == 3
assert [e.rung for e in series] == ["cold"] + ["warm"] * 6
# a 1.5 % jump, because 2 % and 3 % left which warm start broke to rounding (WP-2002,
# 2026-10-23).  Until WP-2003 C3 the first-rung bound (3.0 by default then) cut both
# warm starts beside the step, the 700 K one rescued warm_staged and the 800 K one
# cold; with no bound, the default since, both converge warm (86 and 188 evaluations,
# darwin arm64, 2026-11-02), so nothing escalates and no rwp_warm is kept
assert all(e.rwp_warm is None for e in series)
# the 700 K fit ends at 0.039494, 6e-6 from where a third decimal flips, so the
# page quotes two
assert all(abs(r - 0.040) < 0.001 for r in series.rwp[4:6]), series.rwp[4:6]
assert gap < 0.005
assert len(gaps) == 91 and (a.forward_rung, a.backward_rung) == ("warm", "warm")
assert round(a.forward, 5) == round(a.backward, 5) == 4.16491
