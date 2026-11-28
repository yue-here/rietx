"""Tables for part 1 from results/single_*.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DECLARED = {"srm660c": 7, "fap": 6, "nac": 6, "cpd1a": 8, "bigcell": 11}
FAMS = ["cell", "zero/disp", "profile", "Biso/coords", "scale", "background", "other"]


def family(path: str) -> str:
    if ".cell." in path:
        return "cell"
    if "zero_shift" in path or "displacement" in path or "transparency" in path:
        return "zero/disp"
    if ".atoms." in path:
        return "Biso/coords"
    if path.endswith(".scale"):
        return "scale"
    if "background" in path:
        return "background"
    if ("profile" in path or "lor_" in path or "gauss_" in path or "axial" in path
            or "lines." in path or "microstrain" in path):
        return "profile"
    return "other"


def last_stage(run, n_decl):
    calls = run["calls"]
    return calls[n_decl - 1:]


def table(fixture: str, out=sys.stdout):
    d = json.loads((HERE / "results" / f"single_{fixture}.json").read_text())
    runs = d["runs"]
    ref = next(r for r in runs if r["stop"] == "ftol1e-9" and r["seed"] is None)
    dof = ref["n_points"] - ref["n_free"]
    S_ref = ref["chi2"] * dof
    chi2r = ref["chi2"]
    n_decl = DECLARED[fixture]
    rows = []
    worst_par = {}
    for r in runs:
        tag = r["stop"] if r["seed"] is None else f"nudge{r['seed']}"
        dep = {f: 0.0 for f in FAMS}
        arg = {f: "" for f in FAMS}
        for p, (v, e, eu) in ref["params"].items():
            if p not in r["params"] or not e:
                continue
            z = abs(r["params"][p][0] - v) / e
            f = family(p)
            if z > dep[f]:
                dep[f], arg[f] = z, p
            worst_par.setdefault(tag, {})[p] = (z, r["params"][p][0] - v, e)
        qdep = 0.0
        for name, (w, we) in ref["qpa"].items():
            if w is None or not we or name not in r["qpa"] or r["qpa"][name][0] is None:
                continue
            qdep = max(qdep, abs(r["qpa"][name][0] - w) / we)
        last = last_stage(r, n_decl)
        dS = r["chi2"] * (r["n_points"] - r["n_free"]) - S_ref
        rows.append({"stop": tag, "nfev_last": sum(c["nfev"] for c in last),
                     "njev_last": sum(c["njev"] for c in last),
                     "nfev_total": sum(c["nfev"] for c in r["calls"]),
                     "n_calls": len(r["calls"]), "n_stages": len(r["stages"]),
                     "dS": dS, "dS_over_chi2r": dS / chi2r, "dep": dep, "arg": arg,
                     "qpa_dep": qdep, "maxshift": r["max_shift_over_esd"],
                     "terms": [c["termination"] for c in last]})
    print(f"\n## {fixture}: N-P = {dof}, chi2_red = {chi2r:.4f}, S = {S_ref:.1f}, "
          f"esd_inflation = {ref['esd_inflation']:.3f}, n_free = {ref['n_free']}", file=out)
    print("| stop | evals last stage (J) | evals total | ΔS | ΔS/χ²_red | "
          + " | ".join(FAMS[:-1]) + " | phase frac | max shift/esd |", file=out)
    print("|" + "---|" * (len(FAMS) + 6), file=out)
    for row in rows:
        print(f"| {row['stop']} | {row['nfev_last']} ({row['njev_last']}) | {row['nfev_total']} | "
              f"{row['dS']:.3g} | {row['dS_over_chi2r']:.3g} | "
              + " | ".join(f"{row['dep'][f]:.2g}" for f in FAMS[:-1])
              + f" | {row['qpa_dep']:.2g} | "
              + (f"{row['maxshift']:.2g}" if row['maxshift'] is not None else "-") + " |",
              file=out)
    return rows, worst_par, ref


if __name__ == "__main__":
    for fx in sys.argv[1:]:
        rows, worst, ref = table(fx)
        for row in rows:
            if row["n_calls"] != row["n_stages"] + (1 if fx == "cpd1a" else 0):
                print("  calls/stages mismatch", row["stop"], row["n_calls"], row["n_stages"])
            print("  ", row["stop"], "worst:", {f: row["arg"][f] for f in FAMS if row["dep"][f] > 0.05},
                  "terms", row["terms"])


def lm_table(fixture, out=sys.stdout):
    """ΔS on the solver's own frozen model (last solve), and the recompile gap."""
    d = json.loads((HERE / "results" / f"single_{fixture}.json").read_text())
    runs = d["runs"]
    ref = next(r for r in runs if r["stop"] == "ftol1e-9" and r["seed"] is None)
    chi2r = ref["chi2"]
    s_lm_ref = 2 * ref["calls"][-1]["cost"]
    s_rep_ref = ref["chi2"] * (ref["n_points"] - ref["n_free"])
    print(f"\n{fixture}: S_reported - S_solver at the reference = {s_rep_ref - s_lm_ref:.4g} "
          f"({(s_rep_ref - s_lm_ref) / chi2r:.3g} chi2_red)", file=out)
    for r in runs:
        tag = r["stop"] if r["seed"] is None else f"nudge{r['seed']}"
        s_lm = 2 * r["calls"][-1]["cost"]
        s_rep = r["chi2"] * (r["n_points"] - r["n_free"])
        print(f"  {tag}: dS_solver {s_lm - s_lm_ref:.3g} ({(s_lm - s_lm_ref) / chi2r:.3g} chi2_red); "
              f"dS_reported {s_rep - s_rep_ref:.3g}; recompile gap {s_rep - s_lm:.3g}", file=out)
