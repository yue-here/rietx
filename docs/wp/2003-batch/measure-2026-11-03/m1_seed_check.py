"""Confirm the carry arm really seeds: count pending reflection intensities at each pattern's start."""
import json
from common import *
from rietx.sequential import SequentialRefinement
from tests.test_sequential import A0, RAMP, _simulate, _start_models

patterns = [_simulate(A0 * (1 + RAMP * k), seed=11 + k) for k in range(8)]
out = {"env": env()}
for mode in ("lebail", "pawley"):
    for carry in (True, False):
        seen = []

        def hook(i, ref):
            seen.append(sum(len(r.intensity) for r in ref._pending_reflections))
        st, ins = _start_models()
        SequentialRefinement(st, ins, carry_hkl_intensities=carry).fit(patterns, mode=mode, constrain=hook)
        out[f"{mode}_carry{carry}"] = seen
        print(mode, carry, seen)
json.dump(out, open(f"{MEASURE}/m1_seed_check.json", "w"), indent=1)
