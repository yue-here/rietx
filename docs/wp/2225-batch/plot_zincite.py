"""Zincite: the shipped first fit against a shipped re-fit of it (closing stage on, today's default)."""
import warnings
import numpy as np
warnings.simplefilter("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rietx.refine import Refinement
from rietx.viz import compare
from rietx.viz.plots import plot_result

std = next(s for s in compare.STANDARDS if s.key == "zincite"); dd = compare.default_data_dir()
inp = std.build(dd)
ref = Refinement(inp.structure, inp.instrument, history=False)
r1 = ref.fit(inp.data, plan=std.build(dd).plan, two_theta_limits=inp.two_theta_limits)
r2 = ref.fit(inp.data, plan=std.build(dd).plan, two_theta_limits=inp.two_theta_limits)
out = "tests/output/"
plot_result(r1, path=out + "zincite_first_fit.png", title=f"zincite, shipped first fit, Rwp {r1.statistics.rwp:.5f}")
plot_result(r2, path=out + "zincite_refit.png", title=f"zincite, shipped re-fit, Rwp {r2.statistics.rwp:.5f}")
tt = np.array(r1.two_theta); yo = np.array(r1.y_obs)
d1 = yo - np.array(r1.y_calc); d2 = yo - np.array(r2.y_calc)
s = np.array(r1.sigma)
# the five strongest peaks' neighbourhoods, plus the lowest-angle one
order = np.argsort(np.array(r1.y_calc))[::-1]
centres = []
for i in order:
    if all(abs(tt[i] - c) > 2.0 for c in centres):
        centres.append(tt[i])
    if len(centres) == 6:
        break
centres = sorted(centres)
fig, axes = plt.subplots(2, len(centres), figsize=(3.0 * len(centres), 5.5), sharex="col",
                         gridspec_kw={"height_ratios": [3, 2]})
for j, c in enumerate(centres):
    m = (tt > c - 0.6) & (tt < c + 0.6)
    a, b = axes[0, j], axes[1, j]
    a.plot(tt[m], yo[m], ".", ms=3, color="0.2", label="observed")
    a.plot(tt[m], np.array(r1.y_calc)[m], "-", lw=1, color="C0", label="first fit")
    a.plot(tt[m], np.array(r2.y_calc)[m], "--", lw=1, color="C3", label="re-fit")
    b.plot(tt[m], d1[m] / s[m], "-", lw=1, color="C0")
    b.plot(tt[m], d2[m] / s[m], "--", lw=1, color="C3")
    b.axhline(0, color="0.6", lw=0.5)
    a.set_title(f"{c:.2f}°", fontsize=9)
    b.set_xlabel("2θ (°)")
axes[0, 0].set_ylabel("counts"); axes[1, 0].set_ylabel("(obs − calc)/σ")
axes[0, 0].legend(fontsize=7, frameon=False)
fig.suptitle(f"zincite peaks: first fit (Rwp {r1.statistics.rwp:.5f}) vs re-fit (Rwp {r2.statistics.rwp:.5f}), closing stage on", fontsize=10)
fig.tight_layout(); fig.savefig(out + "zincite_first_vs_refit_peaks.png", dpi=150)
# where the χ² difference lives, cumulative
w1 = (d1 / s) ** 2; w2 = (d2 / s) ** 2
fig, ax = plt.subplots(figsize=(8, 3))
ax.plot(tt, np.cumsum(w1 - w2), color="C2")
ax.set_xlabel("2θ (°)"); ax.set_ylabel("cumulative χ²(first) − χ²(re-fit)")
fig.tight_layout(); fig.savefig(out + "zincite_cumulative_dchi2.png", dpi=150)
print("chi2 sums", w1.sum(), w2.sum(), "centres", [round(c, 2) for c in centres])
