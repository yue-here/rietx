"""Raw-pattern overview and a top-40 peak list for each guiLLeMot example.

The first thing run on the folder, before any model: it is what showed that
FeSb and MnSb_34 need a low-angle cut, that KD1-2_5 is one enormous (002) plus
a dozen weak lines, and that HL2-1 has far too many reflections for a single
high-symmetry phase.
"""
from __future__ import annotations

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from common import EX, OUT, require_data  # noqa: E402
from scipy.ndimage import minimum_filter1d, uniform_filter1d  # noqa: E402
from scipy.signal import find_peaks  # noqa: E402

import pxrdref as pr  # noqa: E402

SETS = {
    "FeSb_19RBM": ("FeSb_19RBM/FeSb_19RBM.xy", 1.540596),
    "HL2-1": ("HL2-1/HL2-1_2.xy", 1.540596),
    "KD1-2_5_NaCoO2": ("KD1-2_5_NaCoO2/KD1-2_5-90_30min.xy", 1.540596),
    "MnSb_33_BM": ("MnSb_33_BM/MnSb_33_BM.xye", 0.824323338),
    "MnSb_34_impure": ("MnSb_34_impure/MnSb_34.xy", 1.540596),
}


def main() -> None:
    require_data()
    fig, axes = plt.subplots(len(SETS), 1, figsize=(12, 3 * len(SETS)))
    for ax, (name, (rel_path, lam)) in zip(axes, SETS.items()):
        d = pr.read_pattern(EX / rel_path)
        tt, y = d.tt(), d.y()
        ax.plot(tt, y, lw=0.6)
        ax.set_title(f"{name}  ({len(tt)} pts, {tt[0]:.2f}-{tt[-1]:.2f} deg, lam={lam})")
        ax.set_yscale("log")
        bkg = uniform_filter1d(minimum_filter1d(y, 201), 201)   # crude, for finding only
        net = y - bkg
        pk, props = find_peaks(
            net, prominence=max(net.max() * 0.01, 3 * np.sqrt(np.median(y))), distance=5)
        ax.plot(tt[pk], y[pk], "rv", ms=4)
        order = np.argsort(props["prominences"])[::-1]
        imax = props["prominences"].max()
        print(f"\n===== {name} =====  top peaks (2theta, d, rel-I)")
        for i in sorted(pk[order][:40].tolist()):
            j = list(pk).index(i)
            dsp = lam / (2 * np.sin(np.radians(tt[i] / 2)))
            print(f"  {tt[i]:8.3f}  {dsp:8.4f}  {props['prominences'][j] / imax:6.3f}")
    fig.tight_layout()
    fig.savefig(OUT / "raw_overview.png", dpi=110)
    print("\nwrote", OUT / "raw_overview.png")


if __name__ == "__main__":
    main()
