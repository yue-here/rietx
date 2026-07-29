"""The two figures for the tooling-audit report, rendered for both themes.

Palette: categorical slots 1-3 of the validated default (blue / orange / aqua),
light and dark steps, validated all-pairs in both modes against this report's
own card surfaces (#ffffff / #151b23).  The light-mode aqua sits at 2.82:1, so
the relief rule applies — every bar carries a visible value label and the same
numbers appear as a table in the report body.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from common import OUT

THEME = {
    "light": dict(surface="#ffffff", ink="#121821", muted="#5A6473",
                  grid="#E9EEF3", rule="#D9E0E8",
                  s1="#2a78d6", s2="#eb6834", s3="#1baf7a", band="#EDF1F6"),
    "dark": dict(surface="#151b23", ink="#E4E9F0", muted="#93A0B1",
                 grid="#242D38", rule="#2E3846",
                 s1="#3987e5", s2="#d95926", s3="#199e70", band="#1E2733"),
}

# ---- measured in audit_tools.check_a (single pass, Biso untied, so the six
# ---- rows differ only by the assumed radius) ------------------------------
A_TOPAS = 4.113838
RADIUS = np.array([180.0, 200.0, 217.5, 240.0, 280.0, 320.0])
A_FIT = np.array([4.113698, 4.113526, 4.113403, 4.113274, 4.113108, 4.112995])
ESD_PPM = 0.000264 / A_TOPAS * 1e6          # our own 1 sigma on a, in ppm

# ---- measured in audit_tools.check_c: best score over the tetragonal and
# ---- hexagonal searches --------------------------------------------------
BARS = [
    ("MnSb  P6₃/mmc", 100, "high"),
    ("Mn₃O₄  I4₁/amd", 82, "high"),
    ("HL2-1  measured", 69, "unknown"),
    ("FeSb₂  Pnnm", 60, "low"),
    ("Sb₂O₃  Pccn", 53, "low"),
    ("Na₂CO₃  C2/m", 50, "low"),
]
GROUP = {"high": ("cubic / tetragonal / hexagonal", "s1"),
         "low": ("orthorhombic / monoclinic", "s3"),
         "unknown": ("HL2-1, symmetry unknown", "s2")}


def style(ax, t):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["rule"])
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=t["muted"], labelsize=9, length=3, width=0.8)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(t["muted"])


def fig_radius(mode):
    t = THEME[mode]
    ppm = (A_FIT / A_TOPAS - 1) * 1e6
    fig, ax = plt.subplots(figsize=(7.4, 4.0), dpi=170)
    fig.patch.set_facecolor(t["surface"])
    style(ax, t)

    ax.axhspan(-ESD_PPM, ESD_PPM, color=t["band"], zorder=0)
    ax.axhline(0, color=t["muted"], lw=1.0, ls=(0, (5, 3)), zorder=1)
    ax.grid(axis="y", color=t["grid"], lw=0.7, zorder=0)
    ax.set_axisbelow(True)

    ax.plot(RADIUS, ppm, "-", lw=2.0, color=t["s1"], zorder=3)
    ax.plot(RADIUS, ppm, "o", ms=8, color=t["s1"],
            markeredgecolor=t["surface"], markeredgewidth=2, zorder=4)
    # the one radius that was actually assumed
    i = int(np.where(RADIUS == 217.5)[0][0])
    ax.plot([217.5], [ppm[i]], "o", ms=15, mfc="none", mec=t["s2"], mew=2.0, zorder=5)

    ax.annotate("assumed 217.5 mm\n(pxrd-refine default)", (217.5, ppm[i]),
                textcoords="offset points", xytext=(14, 20), fontsize=9,
                color=t["s2"], ha="left")
    ax.annotate(f"{ppm[0]:+.0f} ppm", (RADIUS[0], ppm[0]),
                textcoords="offset points", xytext=(9, 6), fontsize=9.5,
                color=t["ink"], ha="left", va="bottom")
    ax.annotate(f"{ppm[-1]:+.0f} ppm", (RADIUS[-1], ppm[-1]),
                textcoords="offset points", xytext=(10, 0), fontsize=9.5,
                color=t["ink"], ha="left", va="center")
    ax.annotate("TOPAS value", (327, 5), fontsize=9, color=t["muted"],
                va="bottom", ha="left")
    ax.annotate("our 1σ on a", (327, -ESD_PPM + 6), fontsize=9, color=t["muted"],
                va="bottom", ha="left")

    ax.set_xlabel("assumed goniometer radius  R (mm)", color=t["muted"], fontsize=10)
    ax.set_ylabel("refined a  −  TOPAS a   (ppm)", color=t["muted"], fontsize=10)
    ax.set_title("A wrong goniometer radius moves the cell further than the "
                 "codes disagree",
                 color=t["ink"], fontsize=11.5, loc="left", pad=12)
    ax.set_xlim(172, 385)
    ax.set_xticks([180, 200, 220, 240, 260, 280, 300, 320])
    fig.tight_layout()
    p = OUT / f"audit_radius_{mode}.png"
    fig.savefig(p, facecolor=t["surface"])
    plt.close(fig)
    return p


def fig_indexer(mode):
    t = THEME[mode]
    fig, ax = plt.subplots(figsize=(7.4, 4.0), dpi=170)
    fig.patch.set_facecolor(t["surface"])
    style(ax, t)

    ys = np.arange(len(BARS))[::-1]
    for y, (label, val, grp) in zip(ys, BARS):
        ax.barh(y, val, height=0.62, color=t[GROUP[grp][1]], zorder=3)
        ax.text(val + 1.6, y, f"{val}%", va="center", fontsize=10,
                color=t["ink"])
    ax.set_yticks(ys)
    ax.set_yticklabels([b[0] for b in BARS], fontsize=9.5)
    ax.set_xlim(0, 116)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlim(0, 116)
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.grid(axis="x", color=t["grid"], lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel("share of peak intensity indexed by the best two-parameter metric",
                  color=t["muted"], fontsize=10)
    ax.set_title("The indexer cannot tell HL2-1 apart from a single "
                 "low-symmetry phase",
                 color=t["ink"], fontsize=11.5, loc="left", pad=12)

    handles = [plt.Rectangle((0, 0), 1, 1, color=t[slot])
               for _, (name, slot) in GROUP.items()]
    leg = ax.legend(handles, [name for name, _ in GROUP.values()],
                    loc="lower right", frameon=False, fontsize=9,
                    handlelength=1.1, handleheight=1.1, borderpad=0.2,
                    labelspacing=0.5)
    for txt in leg.get_texts():
        txt.set_color(t["muted"])
    fig.tight_layout()
    p = OUT / f"audit_indexer_{mode}.png"
    fig.savefig(p, facecolor=t["surface"])
    plt.close(fig)
    return p


if __name__ == "__main__":
    for mode in ("light", "dark"):
        print(fig_radius(mode), fig_indexer(mode))
