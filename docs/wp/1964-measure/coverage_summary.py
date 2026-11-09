import json
import sys

import numpy as np

for path in sys.argv[1:]:
    rows = [json.loads(line) for line in open(path)]
    ok = [r for r in rows if "error" not in r]
    print(path.rsplit("/", 1)[-1], "n", len(rows), "errors", len(rows) - len(ok),
          "converged", sum(r["status"] == "converged" for r in ok),
          "form rejected", sum(bool(r["form"]) for r in ok),
          "wall", f"{min(r['wall'] for r in ok):.1f}-{max(r['wall'] for r in ok):.1f}",
          "f", f"{min(r['f2'] for r in ok):.2f}-{max(r['f2'] for r in ok):.2f}")
    keys = [k for k in ok[0] if k not in ("case", "seed", "status", "wall", "f2", "form")]
    for k in keys:
        z = np.array([r[k][2] for r in ok if r[k] is not None])
        raw = np.array([r[k][2] * r["f2"] for r in ok if r[k] is not None])
        print(f"  {k:5s} n={len(z)} cover2={np.sum(np.abs(z) < 2)} "
              f"raw cover2={np.sum(np.abs(raw) < 2)} "
              f"mean z={z.mean():+.2f} sd z={z.std(ddof=1):.2f} max|z|={np.abs(z).max():.1f}")
