"""Per-quantity jitter: max over neighbour steps of |dDelta|/esd(Delta), and max single dep."""
import json, sys
from pathlib import Path
import numpy as np
from analyse_series import quantities
d = json.loads((Path(__file__).parent / "results" / f"series_{sys.argv[1]}.json").read_text())
runs = d["runs"]; ref = next(r for r in runs if r["stop"] == "ftol1e-9" and r["seed"] is None)
keys = [k for k in sorted(quantities(ref["rows"][0])) if not k.endswith(".b") or "beta" in k]
print("| stop | " + " | ".join(keys) + " |"); print("|" + "---|" * (len(keys) + 1))
for r in runs:
    tag = r["stop"] if r["seed"] is None else f"nudge{r['seed']}"
    cells = []
    for k in keys:
        v0 = np.array([quantities(x)[k][0] for x in ref["rows"]]); e = np.array([quantities(x)[k][1] for x in ref["rows"]], float)
        v = np.array([quantities(x)[k][0] for x in r["rows"]])
        de = np.hypot(e[1:], e[:-1]); j = np.max(np.abs(np.diff(v) - np.diff(v0)) / de); s = np.max(np.abs(v - v0) / e)
        cells.append(f"{s:.2g} / {j:.2g}")
    print(f"| {tag} | " + " | ".join(cells) + " |")
