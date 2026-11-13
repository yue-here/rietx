"""WP-2080 task 5: the GoF step on WP-2003's nine families, the default arm against ``off``.

Reads two directories of ``docs/wp/2003-batch/measure_reseed.py`` records, run on one tree and one
machine (the platform-matched pair: ``--arm off`` and ``--arm status_nobound``, the package default
since WP-2003 C1/C3, with the GoF step in since WP-2080), and prints one table per family: every warm
pattern where the two arms' ladders or values differ, with the GoF ratio the step reads (the ``off``
arm keeps its first rung, so its GoF over the seed's is ``SeriesEntry.warm_gof_over_seed``), the
rungs each arm tried, their evaluations, and the worst |Δ|/esd of the default against ``off``
(``measure_reseed.worst``, ``off``'s esd), judged per pattern (WP-1124).

    python docs/wp/2080-batch/compare_arms.py <dir with *_off.json and *_status_nobound.json>
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "measure_reseed", HERE.parent / "2003-batch" / "measure_reseed.py")
M = importlib.util.module_from_spec(spec)
sys.modules["measure_reseed"] = M
spec.loader.exec_module(M)

FACTOR = 1.25
root = Path(sys.argv[1])
total_warm = total_fired = 0
for name in M.FAMILIES:
    a, b = root / f"{name}_off.json", root / f"{name}_status_nobound.json"
    if not (a.exists() and b.exists()):
        print(f"## {name}: missing\n")
        continue
    off, dflt = json.loads(a.read_text()), json.loads(b.read_text())
    skip = set(off.get("anchored_dof_paths") or [])
    po = {p["index"]: p for p in off["patterns"]}
    pd = {p["index"]: p for p in dflt["patterns"]}
    seed_gof, warm, fired, rows = None, 0, 0, []
    iters_off = sum(p["n_iterations"] for p in off["patterns"])
    iters_def = sum(p["n_iterations"] for p in dflt["patterns"])
    for p in off["patterns"]:       # walk order as stored
        q = pd.get(p["index"])
        ratio = None
        if seed_gof and p["rungs_tried"] and p["rungs_tried"][0] != "cold" and p.get("gof"):
            warm += 1
            ratio = p["gof"] / seed_gof
            fired += ratio > FACTOR
        if p["status"] != "diverged" and p.get("gof"):
            seed_gof = p["gof"]
        if q is None:
            rows.append(f"| {p['label']} | {ratio and f'{ratio:.3f}'} | {p['rungs_tried']} | (absent) | | | |")
            continue
        p["_skip"] = q["_skip"] = skip
        w, where, _ = M.worst(q, p)
        if q["rungs_tried"] != p["rungs_tried"] or (w is not None and w > M.DIFFER_ESD) or (ratio and ratio > FACTOR):
            rows.append(f"| {p['label']} | {ratio and f'{ratio:.3f}'} | {','.join(p['rungs_tried'])} → {','.join(q['rungs_tried'])} "
                        f"(kept {q['rung']}) | {p['n_iterations']} → {q['n_iterations']} | {p['gof']:.4g} → {q['gof']:.4g} "
                        f"| {w:.3g} ({where}) |" if w is not None else f"| {p['label']} | {ratio} | {q['rungs_tried']} | | | — |")
    total_warm += warm
    total_fired += fired
    print(f"## {name}: {warm} warm patterns, ratio > {FACTOR} on {fired}; evaluations off {iters_off}, default {iters_def}\n")
    if rows:
        print("| pattern | GoF / seed GoF (off) | rungs off → default | evaluations | GoF | worst Δ/esd (path) |")
        print("|---|---|---|---|---|---|")
        print("\n".join(rows))
    print()
print(f"TOTAL warm {total_warm}, ratio > {FACTOR} on {total_fired}")
