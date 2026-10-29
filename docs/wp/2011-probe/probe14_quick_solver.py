"""Probe 8's ``quick`` measurement, Pawley mode, under a chosen solver variant.

The go failed on probe 8 because one pseudo-symmetric NAC candidate's Pawley
fit took 377 s.  This reruns probe 8's cases with the solver switches a
probe snapshot carries (``lm.SPARSE_NORMAL``, ``lm.SPARSE_CACHE``,
``bccg.PRECONDITION``, ``bccg.EXACT_LU``) set from ``--variant k=v,...``.

    python probe14_quick_solver.py --variant SPARSE_NORMAL=1,... nac_default nac_all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe8_quick import run, sets  # noqa: E402

from rietx.optimize import bccg, lm  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="")
    ap.add_argument("--mode", default="pawley")
    ap.add_argument("names", nargs="+")
    args = ap.parse_args()
    mods = {"bccg": bccg}
    for key, value in (kv.split("=") for kv in args.variant.split(",") if "=" in kv):
        mod = lm
        if "." in key:
            prefix, key = key.split(".", 1)
            mod = mods[prefix]
        old = getattr(mod, key)
        setattr(mod, key, value == "1" if isinstance(old, bool) else type(old)(value))
    table = sets()
    for name in args.names:
        load, spec = table[name]
        rec = run(name, load, spec, args.mode)
        rec["variant"] = args.variant or "dense"
        print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    main()
