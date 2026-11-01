"""The fits behind `docs/docs/guides/series.md`: a temperature series, chained.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: seven synthetic LaB6 patterns from `_lab6_ramp.py` beside this script,
made from a known cell at each temperature.
"""

# guide: start

from _lab6_ramp import TEMPERATURES, ramp, starting_model

import rietx as rx

patterns = ramp()  # seven patterns, 300 K to 900 K
structure, instrument = starting_model()

series = rx.refine_sequential(patterns, structure, instrument, plan="mccusker_default",
                              x=TEMPERATURES, x_label="T (K)")
print(series)
# guide: end

# guide: trajectory start
a = series.trajectory("phases.0.cell.a")
print(a)
# guide: trajectory end

# guide: rungs start
for entry in series:
    print(f"{entry.label}  {entry.rung:<5} {entry.n_iterations:3d} evaluations")
# guide: rungs end

from _lab6_ramp import TRUE_A  # noqa: E402

# Every fitted edge lies within 2 esd of the edge its pattern was made from.
assert max(abs(v - t) / e for v, t, e in zip(a.value, TRUE_A, a.stderr)) < 2
assert [f"{v:.6f}" for v in a.value] == [
    "4.156594", "4.158673", "4.160762", "4.162839", "4.164911", "4.166985", "4.169066"]
assert [round(e * 1e6) for e in a.stderr] == [4] * 7
assert [d.code for d in series.diagnostics] == ["SEQUENTIAL_PERSISTENT_FINDING"] * 2
assert [f"{r:.4f}" for r in series.rwp] == [
    "0.0409", "0.0409", "0.0399", "0.0405", "0.0406", "0.0402", "0.0404"]
assert [e.rung for e in series] == ["cold"] + ["warm"] * 6
assert [e.n_iterations for e in series] == [38] + [15] * 6
# The page says a persistent finding needs five patterns or more.
from rietx.sequential import MIN_POINTS_FOR_PERSISTENCE  # noqa: E402

assert MIN_POINTS_FOR_PERSISTENCE == 5
