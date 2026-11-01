"""Row 2: what entry 87 (the blank frame) carries at each of the two outcomes."""
import sys

sys.path.insert(0, sys.argv[1])
import rietx as rx  # noqa: E402
from tests import planted_series as ps  # noqa: E402

k = int(sys.argv[2])
series = ps.generate(248, seed=0)


@ps.numpy_path
def refine():
    structure, ins = ps.cubic_model(series.temperature[0])
    structure.phases[0].cell.a.value *= (1 + k * 1e-14)
    return rx.refine_sequential(series.patterns, structure, ins, x=series.temperature,
                                x_label="T (K)", labels=series.labels, plan="mccusker_default")


res = refine()
e = res.entries[87]
print(f"k={k:+d} entry 87 status={e.status} rung={getattr(e, 'rung', None)} reseeded={e.reseeded} "
      f"rwp={e.statistics.rwp!r}")
for p in e.parameters:
    print(f"   {p.path} {p.value!r} esd={p.stderr!r} at_bound={getattr(p, 'at_bound', None)}")
for d in e.diagnostics:
    if d.level != "info" or d.code.startswith("PHASE"):
        print(f"   {d.level} {d.code} {d.where} {d.message[:300]}")
