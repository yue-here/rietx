"""cpd-1 series: the mean signed paired shift per quantity, against its scatter.

For each setting S and quantity p: d_k = (v_S(k) - v_R(k)) / esd_p over the 11
starts (unnudged + seeds 0-9).  mean_p, sd_p, se_p = sd_p/sqrt(n).  A setting's
systematic error on p is mean_p; its path scatter is sd_p.
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import analyse_series as AS  # noqa: E402
import analyse as A  # noqa: E402

runs = AS.load()
R = "ftol1e-9"
vR, eR = AS.flat(runs[(R, "none")])
seeds = ["none"] + [str(k) for k in range(10)]
for S in ("numpy", "ftol1e-6", "gsas"):
    for K in (5, 11):
        D = {}
        for s in seeds[:K]:
            a, b = AS.flat(runs[(S, s)])[0], AS.flat(runs[(R, s)])[0]
            for p, e in eR.items():
                if e and p in a and p in b:
                    D.setdefault(p, []).append((a[p] - b[p]) / e)
        rows = []
        for p, d in D.items():
            d = np.array(d)
            rows.append((abs(d.mean()), d.mean(), d.std(ddof=1), d.std(ddof=1) / np.sqrt(len(d)), p,
                         np.abs(d).max()))
        rows.sort(reverse=True)
        top = rows[0]
        n_sig = sum(1 for r in rows if r[0] > A.BAR and r[0] > 2 * r[3])
        worst_abs = max(r[5] for r in rows)
        print(f"{S:9s} K={K:2d}: largest |mean shift| {top[1]:+.3f} esd (sd {top[2]:.3f}, se {top[3]:.3f}) on {top[4]}; "
              f"quantities with |mean| > 0.1 and > 2 se: {n_sig}; largest single-pair |shift| {worst_abs:.3f}")
