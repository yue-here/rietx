"""Readings of a speed setting's error, from results/*.json.

python analyse.py > tables.txt   (and results/summary.json)

Units: every departure is in the reported (Berar-Lelann-inflated) esd of the
*reference setting's unnudged* fit, per parameter.  Phase fractions enter as
W[name] over their own esd.

Readings, for a candidate setting S against reference setting R on one fixture:
  naive   max_p |v_S(none) - v_R(none)| / e_p
  floor   per parameter F_p = max_k |v_R(k) - v_R(none)| / e_p over K nudges;
          floor_sub = max_p max(0, d_p - F_p); floor_cmp passes iff d_p <= max(0.1, F_p) for all p
  paired  K pairs (S,k)/(R,k) with the same nudge seed k; a pair counts only when
          both land in the same basin (basins: single-linkage clusters of R's answers);
          shift_k = max_p |v_S(k) - v_R(k)| / e_p; paired = max over counted pairs
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
sys.path.insert(0, str(HERE.parent / "convnoise"))
from analyse_single import family  # noqa: E402

BAR = 0.1
NO_BKG = False
ANCHORED = re.compile(r"\.atoms\.\d+\.dof\.")
FIXTURES = ["srm660c", "fap", "nac", "cpd1a", "bigcell"]


def load():
    runs = {}
    for f in RES.glob("*__*__*.json"):
        if f.name.startswith("series_"):
            continue
        r = json.loads(f.read_text())
        runs[(r["fixture"], r["setting"], r["seed"])] = r
    # a held path leaves RefinementResult.parameters (WP-1999), so the injected
    # coordinate is rebuilt: the first fit of a 'refit' run is the plain shipped
    # fit from the same seed, and the set moved the coordinate by moved_esd x esd
    for (fx, S, s), r in runs.items():
        inj = r.get("inject")
        if inj and inj["esd_path"] not in r["params"]:
            first = runs[(fx, "ref", s)]["params"][inj["esd_path"]][0]
            r["params"][inj["esd_path"]] = [first + inj["moved_esd"] * inj["esd"], inj["esd"], None]
            r["rebuilt"] = inj["esd_path"]
    return runs


def vec(rec):
    # an atom's coordinate DOF is a step from where its fit began (anchored,
    # WP-1333): judged across fits through the coordinate rows, never the DOF
    keep = {p: x for p, x in rec["params"].items() if not ANCHORED.search(p)
            and not (NO_BKG and "background" in p)}
    v = {p: x[0] for p, x in keep.items()}
    e = {p: x[1] for p, x in keep.items()}
    for name, (w, we) in rec.get("qpa", {}).items():
        v[f"W[{name}]"], e[f"W[{name}]"] = w, we
    return v, e


def dep(a, b, esd):
    """per-parameter |a-b|/esd over the shared, measured parameters."""
    out = {}
    for p, e in esd.items():
        if e and np.isfinite(e) and p in a and p in b:
            out[p] = abs(a[p] - b[p]) / e
    return out


def worst(d):
    if not d:
        return 0.0, ""
    p = max(d, key=d.get)
    return d[p], p


def basins(answers, esd, tol=0.5):
    """Single-linkage clusters (max-norm in esd) of a list of value dicts."""
    n = len(answers)
    lab = list(range(n))

    def find(i):
        while lab[i] != i:
            lab[i] = lab[lab[i]]
            i = lab[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if worst(dep(answers[i], answers[j], esd))[0] < tol:
                lab[find(i)] = find(j)
    roots = sorted({find(i) for i in range(n)}, key=lambda r: [find(i) for i in range(n)].index(r))
    return [roots.index(find(i)) for i in range(n)]


def centres(answers, labels):
    k = max(labels) + 1
    cs = []
    for c in range(k):
        mem = [a for a, l in zip(answers, labels) if l == c]
        cs.append({p: float(np.mean([m[p] for m in mem])) for p in mem[0]})
    return cs


def discriminators(cs, esd, thr=1.0):
    ps = set()
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            d = dep(cs[i], cs[j], esd)
            ps |= {p for p, z in d.items() if z > thr}
    return sorted(ps)


def assign(a, cs, esd, disc):
    if len(cs) == 1:
        return 0
    sub = {p: esd[p] for p in disc}
    return int(np.argmin([worst(dep(a, c, sub))[0] for c in cs]))


def reference_of(fixture, setting):
    if setting.startswith("cw") and not setting.startswith("cwNone"):
        return "cw1e-3"
    if setting == "cwNone":
        return "cw1e-3"
    return "ref"


def readings(runs, fx, S, R, K=5, seeds=None):
    seeds = seeds or [str(k) for k in range(K)]
    rnone = runs[(fx, R, "none")]
    vR, eR = vec(rnone)
    vS, _ = vec(runs[(fx, S, "none")])
    d_naive = dep(vS, vR, eR)
    naive, naive_p = worst(d_naive)
    # floor from R's nudged reruns
    rk = [vec(runs[(fx, R, s)])[0] for s in seeds if (fx, R, s) in runs]
    sk = [vec(runs[(fx, S, s)])[0] if (fx, S, s) in runs else None for s in seeds]
    F = defaultdict(float)
    for a in rk:
        for p, z in dep(a, vR, eR).items():
            F[p] = max(F[p], z)
    sub = {p: max(0.0, z - F[p]) for p, z in d_naive.items()}
    floor_sub, floor_sub_p = worst(sub)
    cmp_fail = {p: z for p, z in d_naive.items() if z > max(BAR, F[p])}
    # basins from R's answers: none + every available seed (up to 20 for ref)
    all_R = [vR] + [vec(runs[(fx, R, s)])[0] for s in map(str, range(20)) if (fx, R, s) in runs]
    lab = basins(all_R, eR)
    cs = centres(all_R, lab)
    disc = discriminators(cs, eR)
    shifts, split, counted = [], 0, 0
    shift_p = ""
    for a, b in zip(sk, rk):
        if a is None:
            continue
        la, lb = assign(a, cs, eR, disc), assign(b, cs, eR, disc)
        if la != lb:
            split += 1
            continue
        counted += 1
        z, p = worst(dep(a, b, eR))
        shifts.append(z)
        if z == max(shifts):
            shift_p = p
    return {
        "naive": naive, "naive_p": naive_p,
        "floor_max": max(F.values()) if F else 0.0,
        "floor_sub": floor_sub, "floor_sub_p": floor_sub_p,
        "floor_cmp_pass": not cmp_fail,
        "floor_glob": max(0.0, naive - (max(F.values()) if F else 0.0)),
        "paired_max": max(shifts) if shifts else float("nan"),
        "paired_med": float(np.median(shifts)) if shifts else float("nan"),
        "paired_min": min(shifts) if shifts else float("nan"),
        "paired_p": shift_p, "pairs": counted, "split": split,
        "n_basins_R": len(cs),
    }


def m1(runs, out):
    print("## M1 floor vs K (reference = shipped plan; reported esd of the unnudged fit)\n", file=out)
    fams = ["cell", "zero/disp", "profile", "Biso/coords", "scale", "background", "W"]
    summary = {}
    for fx in FIXTURES:
        if (fx, "ref", "none") not in runs:
            continue
        vR, eR = vec(runs[(fx, "ref", "none")])
        per_seed = []
        for s in range(20):
            r = runs.get((fx, "ref", str(s)))
            if r is None:
                continue
            d = dep(vec(r)[0], vR, eR)
            fam = defaultdict(float)
            for p, z in d.items():
                f = "W" if p.startswith("W[") else family(p)
                fam[f] = max(fam[f], z)
            per_seed.append((s, worst(d), dict(fam), r["chi2"]))
        print(f"### {fx}: n nudges = {len(per_seed)}", file=out)
        print("| K | max (all) | P90 of per-seed worst | " + " | ".join(f"max {f}" for f in fams) + " |", file=out)
        print("|---" * (3 + len(fams)) + "|", file=out)
        summary[fx] = {}
        for K in (3, 5, 10, 20):
            sel = per_seed[:K]
            if len(sel) < K:
                continue
            w = [x[1][0] for x in sel]
            fm = {f: max(x[2].get(f, 0.0) for x in sel) for f in fams}
            summary[fx][K] = {"max": max(w), "p90": float(np.percentile(w, 90)), **fm}
            print(f"| {K} | {max(w):.3g} | {np.percentile(w, 90):.3g} | "
                  + " | ".join(f"{fm[f]:.2g}" for f in fams) + " |", file=out)
        print("", file=out)
        # basins
        ans = [vR] + [vec(runs[(fx, "ref", str(s))])[0] for s, *_ in per_seed]
        chis = [runs[(fx, "ref", "none")]["chi2"]] + [x[3] for x in per_seed]
        lab = basins(ans, eR)
        cs = centres(ans, lab)
        dof = runs[(fx, "ref", "none")]["n_points"] - runs[(fx, "ref", "none")]["n_free"]
        print(f"basins: {len(cs)}; members {[lab.count(c) for c in range(len(cs))]} "
              f"(unnudged in basin {lab[0]})", file=out)
        for c in range(len(cs)):
            cc = [x for x, l in zip(chis, lab) if l == c]
            print(f"  basin {c}: chi2_red {np.mean(cc):.6f} (S = {np.mean(cc) * dof:.2f}), "
                  f"spread within {max(cc) - min(cc):.2e}", file=out)
        if len(cs) > 1:
            d = dep(cs[0], cs[1], eR)
            top = sorted(d.items(), key=lambda t: -t[1])[:8]
            print("  separating (|centre0 - centre1| / esd): " +
                  ", ".join(f"{p} {z:.2f}" for p, z in top), file=out)
            within = []
            for c in range(len(cs)):
                mem = [a for a, l in zip(ans, lab) if l == c]
                for a in mem:
                    within.append(worst(dep(a, cs[c], eR))[0])
            print(f"  largest within-basin departure from its centre: {max(within):.2e} esd", file=out)
            n_gt = {t: sum(1 for z in d.values() if z > t) for t in (0.1, 0.3, 1.0)}
            print(f"  params moving between basins by >0.1/0.3/1 esd: {n_gt}", file=out)
        print("", file=out)
    return summary


SETTINGS = ["ftol1e-6", "gsas", "ftol1e-3", "ftol1e-2", "ftol1e-1", "cw1e-2", "cw1e-1", "cwNone"]


def verdict(x):
    return "pass" if x <= BAR else "FAIL"


def m2(runs, out, K=5):
    print(f"## M2 readings (K = {K} nudges/pairs; bar {BAR} esd)\n", file=out)
    print("| setting | fixture | ref | naive (param) | floor max | floor_sub | floor_cmp | floor_glob (naive - max floor) | paired max / median (param) | pairs used / split |", file=out)
    print("|---|---|---|---|---|---|---|---|---|---|", file=out)
    allr = {}
    for S in SETTINGS:
        for fx in FIXTURES:
            R = reference_of(fx, S)
            if (fx, S, "none") not in runs or (fx, R, "none") not in runs:
                continue
            r = readings(runs, fx, S, R, K)
            allr[(S, fx)] = r
            print(f"| {S} | {fx} | {R} | {r['naive']:.3g} {verdict(r['naive'])} ({r['naive_p']}) | "
                  f"{r['floor_max']:.2g} | {r['floor_sub']:.3g} {verdict(r['floor_sub'])} | "
                  f"{'pass' if r['floor_cmp_pass'] else 'FAIL'} | "
                  f"{r['floor_glob']:.3g} {verdict(r['floor_glob'])} | "
                  f"{r['paired_max']:.3g} / {r['paired_med']:.3g} {verdict(r['paired_max'])} ({r['paired_p']}) | "
                  f"{r['pairs']} / {r['split']} (R basins {r['n_basins_R']}) |", file=out)
    print("", file=out)
    return allr


def m3(runs, out):
    print("## M3 injected error on bigcell (reference = 'refit', the same two-step fit with nothing held)\n", file=out)
    inj = sorted({S for (f, S, s) in runs if f == "bigcell" and S.startswith("refit@")})
    print("| injection | K | naive (param) | floor_sub | floor_cmp | floor_glob | paired max / min (param) | pairs used / split | injected param: naive, F_p, paired per pair |", file=out)
    print("|---|---|---|---|---|---|---|---|---|", file=out)
    for S in inj:
        if ("bigcell", S, "none") not in runs:
            continue
        for K in (5, 10):
            r = readings(runs, "bigcell", S, "refit", K)
            esd_path = S.split("@")[3]
            vR, eR = vec(runs[("bigcell", "refit", "none")])
            dn = abs(vec(runs[("bigcell", S, "none")])[0][esd_path] - vR[esd_path]) / eR[esd_path]
            Fp = max(abs(vec(runs[("bigcell", "refit", str(k))])[0][esd_path] - vR[esd_path]) / eR[esd_path]
                     for k in range(K))
            pp = []
            for k in range(K):
                a, b = runs.get(("bigcell", S, str(k))), runs.get(("bigcell", "refit", str(k)))
                if a and b:
                    pp.append((vec(a)[0][esd_path] - vec(b)[0][esd_path]) / eR[esd_path])
            moved = [runs[("bigcell", S, s)]["inject"]["moved_esd"] for s in ["none"] + [str(k) for k in range(K)]
                     if ("bigcell", S, s) in runs]
            print(f"| {S.split('@')[3]} +{S.split('@')[2]} | {K} | {r['naive']:.3g} {verdict(r['naive'])} ({r['naive_p']}) | "
                  f"{r['floor_sub']:.3g} {verdict(r['floor_sub'])} | {'pass' if r['floor_cmp_pass'] else 'FAIL'} | "
                  f"{r['floor_glob']:.3g} {verdict(r['floor_glob'])} | "
                  f"{r['paired_max']:.3g} / {r['paired_min']:.3g} {verdict(r['paired_max'])} ({r['paired_p']}) | "
                  f"{r['pairs']} / {r['split']} | {dn:.3g}, {Fp:.3g}, [{', '.join(f'{x:+.3f}' for x in pp)}]; "
                  f"set moved it {min(moved):.4f}-{max(moved):.4f} |", file=out)
    print("", file=out)


def m4(runs, out):
    print("## M4 direction of cell moves under the window settings (paired, same basin)\n", file=out)
    print("| setting | fixture | param | n pairs | n positive | median shift/esd | min | max |", file=out)
    print("|---|---|---|---|---|---|---|---|", file=out)
    for S in ["cw1e-2", "cw1e-1", "cwNone"]:
        for fx in FIXTURES:
            R = "cw1e-3"
            if (fx, R, "none") not in runs:
                continue
            vR, eR = vec(runs[(fx, R, "none")])
            cells = [p for p in vR if ".cell." in p]
            for p in cells:
                sh = []
                for s in ["none"] + [str(k) for k in range(10)]:
                    a, b = runs.get((fx, S, s)), runs.get((fx, R, s))
                    if a is None or b is None:
                        continue
                    va, vb = vec(a)[0], vec(b)[0]
                    if p in va and p in vb:
                        sh.append((va[p] - vb[p]) / eR[p])
                if not sh:
                    continue
                sh = np.array(sh)
                print(f"| {S} | {fx} | {p} | {len(sh)} | {(sh > 0).sum()} | {np.median(sh):.3g} | "
                      f"{sh.min():.3g} | {sh.max():.3g} |", file=out)
    print("", file=out)
    # SRM 660c against the certificate
    cert, ucert = 4.156882, 0.000021
    fx, p = "srm660c", "phases.0.cell.a"
    rows = []
    for (f, S, s), r in runs.items():
        if f != fx or S in ("ref", "cw1e-3"):
            continue
        R = reference_of(fx, S)
        b = runs.get((fx, R, s))
        if b is None:
            continue
        va, vb = vec(r)[0][p], vec(b)[0][p]
        e = vec(runs[(fx, R, "none")])[1][p]
        rows.append((S, s, (va - vb) / e, abs(va - cert) > abs(vb - cert), va, vb, e))
    vref = vec(runs[(fx, "ref", "none")])[0][p]
    eref = vec(runs[(fx, "ref", "none")])[1][p]
    print(f"SRM 660c a: shipped answer {vref:.7f} A, esd {eref:.2e} A ({eref / vref * 1e6:.2f} ppm); "
          f"certificate {cert} ({ucert / cert * 1e6:.1f} ppm); answer - cert = "
          f"{(vref - cert) / cert * 1e6:+.1f} ppm = {(vref - cert) / eref:+.1f} esd = "
          f"{(vref - cert) / ucert:+.2f} u_cert\n", file=out)
    for lo, hi, name in [(0, 1e-9, "zero"), (1e-9, 0.1, "inside 0.1 esd"), (0.1, 1e9, "outside 0.1 esd")]:
        sel = [x for x in rows if lo <= abs(x[2]) < hi] if name != "zero" else [x for x in rows if x[2] == 0]
        if name == "zero":
            print(f"moves of exactly zero: {len(sel)}", file=out)
            continue
        nf = sum(1 for x in sel if x[3])
        print(f"moves {name}: {len(sel)}, further from certificate {nf} ({nf / max(len(sel), 1):.0%}); "
              f"signs +{sum(1 for x in sel if x[2] > 0)}/-{sum(1 for x in sel if x[2] < 0)}", file=out)
    print("", file=out)
    by_s = defaultdict(list)
    for x in rows:
        by_s[x[0]].append(x)
    for S, xs in sorted(by_s.items()):
        z = np.array([x[2] for x in xs])
        print(f"  {S}: n {len(z)}, shift/esd median {np.median(z):+.3g} range [{z.min():+.3g}, {z.max():+.3g}], "
              f"further {sum(1 for x in xs if x[3])}", file=out)
    print("", file=out)


def main():
    runs = load()
    out = sys.stdout
    which = sys.argv[1:] or ["m1", "m2", "m3", "m4"]
    summ = {}
    if "m1" in which:
        summ["m1"] = m1(runs, out)
    if "m2" in which:
        global NO_BKG
        for K in (5, 10):
            r = m2(runs, out, K)
            summ[f"m2_K{K}"] = {f"{a}|{b}": v for (a, b), v in r.items()}
        NO_BKG = True
        print("### the same, background coefficients excluded (K = 5)\n", file=out)
        r = m2(runs, out, 5)
        summ["m2_K5_nobkg"] = {f"{a}|{b}": v for (a, b), v in r.items()}
        NO_BKG = False
    if "m3" in which:
        m3(runs, out)
    if "m4" in which:
        m4(runs, out)
    (RES / "summary.json").write_text(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
