"""Reduce families.py's rows to the task-1 tables.

  families_summary.py OUT.jsonl [OUT.jsonl ...]

Per family, closing setting and arm: Rwp, χ² against the hold-off arm, iterations
(and rounds for opt2), the weight fractions, what was swapped or held, the profile, the
specimen widths on their floor, and for `+1` the largest shift of a reported parameter in
plain esd and in reported esd (the larger of the two, background rows apart, `tests.test_window_domain._shift`).
For the cpd-1a start pair, the largest shift between the Biso 0.5 and 1.5 ends per arm.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests.test_window_domain import _shift  # noqa: E402

rows = [json.loads(line) for f in sys.argv[1:] for line in open(f, encoding="utf-8")]
by = {(r["family"], r["closing"], r["arm"]): r for r in rows}


QUOTED = (".cell.", ".atoms.", ".scale")


def rv(r, k, quoted=False):
    return {p: (v[0], v[k]) for p, v in r["params"].items()
            if len(v) > k and (not quoted or any(q in p for q in QUOTED))}


def shift(a, b):
    """plain esd, then reported (Berar-Lelann inflated) esd, the unit of shifts.py,
    then reported esd over cell, atom and scale rows alone"""
    out = []
    for k in (1, 2):
        worst, path = _shift(rv(a, k), rv(b, k), background=False)
        out.append(f"{worst:.2f} ({path.split('.', 1)[-1] if path else '-'})")
    worst, path = _shift(rv(a, 2, True), rv(b, 2, True), background=False)
    out.append(f"quoted {worst:.2f} ({path.split('.', 1)[-1] if path else '-'})")
    return " / ".join(out)


for (fam, clos, arm), r in by.items():
    ref = by.get((fam, clos, "nohold"))
    dchi = (f"{100 * (r['chi2'] / ref['chi2'] - 1):+.2f}%" if ref else "-")
    q = " ".join(f"{k} {v[0]:.2f}±{(v[1] or 0):.2f}" for k, v in r["qpa"].items()) \
        if len(r["qpa"]) > 1 else ""
    prof = " ".join(f"{k}={v:.4g}" for k, v in r["profile"].items())
    floor = [p.replace("phases.", "") for p, v in r["specimen"].items() if v <= 0.0]
    line = (f"{fam:14s} {clos:4s} {arm:8s} Rwp {r['rwp']:.6f} chi2 vs hold-off {dchi:>7s} "
            f"it {r['iterations']:3d} {r['seconds']:5.1f}s")
    if "rounds" in r:
        line += f" rounds {r['rounds']} trace {[round(x, 6) for x in r['rwp_trace']]}"
    if arm.endswith("+1"):
        line += f" | re-fit shift {shift(r, by[(fam, clos, arm[:-2])])}"
    print(line)
    print(f"{'':28s}{q} | {prof} | floor {floor} | swapped {r['swapped']} "
          f"| codes {r['codes']}" + (f" | sigma2<0 {r['sigma2_negative']}" if "sigma2_negative" in r else ""))

print("\ncpd-1a, Biso 0.5 against 1.5, largest shift in plain esd")
for (fam, clos, arm), r in by.items():
    if fam == "cpd1a_b0.5" and ("cpd1a_b1.5", clos, arm) in by:
        print(f"  {clos:4s} {arm:8s} {shift(r, by[('cpd1a_b1.5', clos, arm)])}")
