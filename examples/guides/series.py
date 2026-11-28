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
assert series.diagnostics == []
assert [(c.code, c.path, c.count, c.level) for c in series.code_counts] == [
    ("CAPILLARY_OFFSET_UNAVAILABLE", "instrument.geometry.goniometer_radius_mm", 7, "info"),
    ("PATTERN_UNDERSAMPLED", None, 7, "warning")]
assert [f"{r:.4f}" for r in series.rwp] == [
    "0.0412", "0.0411", "0.0400", "0.0407", "0.0408", "0.0405", "0.0406"]
assert [e.rung for e in series] == ["cold"] + ["warm"] * 6
# Moved with WP-2222 (closing stage off by default, 2026-11-19): 38 -> 35 and 15 -> 12.
assert [e.n_iterations for e in series] == [34, 10, 9, 10, 9, 10, 10]  # [35] + [12] * 6 before WP-2317 R6 (2026-11-28)
