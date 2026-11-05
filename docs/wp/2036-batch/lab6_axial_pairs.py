"""LaB6's two start rows at 1e-14 nudges of the w start: every arm pair, unordered and
with the axial pair ordered (2026-11-02).

usage: python lab6_axial_pairs.py <repo root> floor|tolerance
"""
import itertools
import sys

sys.path.insert(0, sys.argv[1])
import rietx as rx  # noqa: E402
import rietx.model.forward as fwd  # noqa: E402
from rietx.model import compiled  # noqa: E402
from tests import test_window_domain as w  # noqa: E402
from tests.test_staged_start_invariance import _axial_pair_ordered  # noqa: E402

row = sys.argv[2]
compiled.set_enabled(True)
KS = [0, 1, -1, 3, -3, 7, -7]
arms = {}
for arm in ("a", "b"):
    for k in KS:
        data, st, ins, plan, kw = w._protocol("lab6")
        if row == "floor":
            fwd.AXIAL_SIZING_FLOOR = 0.02 if arm == "a" else 0.05
        elif arm == "b":
            plan.intermediate_ftol = None
        ins.profile.w.value = ins.profile.w.value * (1 + k * 1e-14)
        res = rx.Refinement(st, ins, history=False).fit(data, plan=plan, **kw)
        arms[(arm, k)] = w._rows(res)
raw, ordered = [], []
for ka, kb in itertools.product(KS, KS):
    a, b = arms[("a", ka)], arms[("b", kb)]
    raw.append(w._shift(a, b, background=False)[0])
    ordered.append(w._shift(_axial_pair_ordered(a), _axial_pair_ordered(b), background=False))
print(f"{row}: {len(raw)} pairs, unordered over 0.1 esd {sum(r > 0.1 for r in raw)}, "
      f"max {max(raw):.3f}; ordered max {max(o[0] for o in ordered):.4f} on {max(ordered)[1]}")
