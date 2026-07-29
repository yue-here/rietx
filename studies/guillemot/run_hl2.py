"""HL2-1 — the one pattern in the collection with no accompanying information.

No .inp, no formula, no sample metadata, no sibling folder that names it.  The
2theta grid is bit-identical to FeSb_19RBM.xy and MnSb_34.xy (5.01436 ...
89.99116, 5086 points), so it is the same Cu Kalpha laboratory diffractometer
and nothing else is known.

Three attempts at an identification, all recorded here rather than hidden:

1. `index_hl2.py` — pair-seeded autoindexing over cubic / tetragonal /
   hexagonal metrics.  Best solution indexes 68 % of the observed peak
   intensity; the identical code recovers MnSb_34's true cell (a = 4.1417,
   c = 5.7803) at 82 %, so 68 % is a failure, not a threshold effect.
2. `match_hl2.py` — a 36-phase screen over the chemistry the rest of the
   collection is made of plus everyday laboratory phases.  Nothing scores
   convincingly; the leaders are simply the candidates with the most predicted
   lines.
3. the same screen over phase *pairs and triples*: the best three-phase
   combination indexes 67 % of the intensity with 104 predicted lines against
   74 observed peaks, which is chance-level.

74 resolvable reflections with no two-parameter metric behind them says
multiphase and/or low symmetry.  So what is delivered here is (a) the extracted
peak table, which is what a database search actually needs, and (b) a Pawley
whole-pattern fit on the best-scoring hexagonal cell — a *description* of the
peak shapes and positions, explicitly NOT evidence for that cell: with this
many reflections in range a Pawley fit has a free intensity per reflection and
would fit almost any metric.
"""
from __future__ import annotations

import numpy as np
from common import EX, OUT, P, atom, hex_cell, summarise
from index_hl2 import LAM, peak_list

import pxrdref as pr

NAME = "HL2-1"
FILE = "HL2-1_2.xy"
LO, HI = 8.0, 90.0
AXIAL = 10.0 / 2 / 217.5
KA2 = 0.346183 / 0.653817

#: best hexagonal metric from index_hl2.py (66 % of observed intensity)
CELL_A, CELL_C = 5.5626, 21.8218


def build():
    ph = pr.Phase(
        name="HL2-1 (unidentified)", space_group="P 6/m m m",
        cell=hex_cell(CELL_A, CELL_C),
        # Pawley: the structural content is inert (one free intensity per
        # reflection), but the Laue class still sets how many there are, so
        # take the highest hexagonal symmetry the metric allows
        atoms=[atom("X1", "Fe", 0.0, 0.0, 0.0)],
        scale=P(value=1.0, min=0.0, transform="softplus"))
    inst = pr.Instrument.bragg_brentano(radiation="CuKa", ka2_ratio=KA2,
                                        monochromator_two_theta=90.0)
    inst.profile.w.value = 5e-3
    inst.profile.x.value = 5e-3
    inst.geometry.axial_sl.value = AXIAL
    inst.geometry.axial_hl.value = AXIAL
    return pr.Structure(phases=[ph]), inst


def write_peak_table(path):
    pos, prom, tt, y, net, bkg = peak_list(EX / NAME / FILE)
    d = LAM / (2 * np.sin(np.radians(pos / 2)))
    rel = prom / prom.max()
    np.savetxt(path, np.column_stack([pos, d, rel]),
               fmt="%10.4f %10.5f %8.4f",
               header="HL2-1 extracted peaks (Cu Ka1 1.540596 A)\n"
                      "2theta_deg  d_Angstrom  I_rel")
    return pos, prom, tt, y, bkg


def main():
    from pxrdref.background import auto_background

    pos, prom, tt, y, bkg = write_peak_table(OUT / f"{NAME}_peaks.txt")
    print(f"{NAME}: {len(pos)} resolvable peaks, "
          f"d = {LAM / (2 * np.sin(np.radians(pos.max() / 2))):.4f} - "
          f"{LAM / (2 * np.sin(np.radians(pos.min() / 2))):.4f} A "
          f"-> wrote {OUT / f'{NAME}_peaks.txt'}")

    # --- annotated raw pattern ---------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(4, 1, figsize=(13, 11))
    for ax, (lo, hi) in zip(axes, [(5, 25), (25, 45), (45, 65), (65, 90)]):
        m = (tt >= lo) & (tt <= hi)
        ax.plot(tt[m], y[m], lw=0.7, color="#1f5fa8")
        ax.plot(tt[m], bkg[m], lw=0.6, ls="--", color="#999999")
        sel = (pos >= lo) & (pos <= hi)
        top = y[m].max()
        for p in pos[sel]:
            ax.axvline(p, color="#c23b22", lw=0.4, alpha=0.55)
            dsp = LAM / (2 * np.sin(np.radians(p / 2)))
            ax.annotate(f"{dsp:.3f}", (p, top * 0.97), rotation=90,
                        fontsize=5.5, ha="center", va="top", color="#7a2018")
        ax.set_xlim(lo, hi)
        ax.set_ylabel("counts")
    axes[0].set_title(f"{NAME} — unidentified; {len(pos)} extracted peaks "
                      f"labelled with d (A), Cu Ka")
    axes[-1].set_xlabel(r"2$\theta$ (deg)")
    fig.tight_layout()
    fig.savefig(OUT / f"{NAME}_peaks.png", dpi=120)
    print(f"  wrote {OUT / f'{NAME}_peaks.png'}")

    # --- Pawley description -------------------------------------------------
    data = pr.read_pattern(EX / NAME / FILE).crop(LO, HI)
    structure, inst = build()
    inst.background = auto_background(data, kind="chebyshev", wavelength=LAM)
    ref = pr.Refinement(structure, inst)
    result = ref.fit(data, mode="pawley", plan="pawley_default")
    n_refl = len(result.ticks.get("HL2-1 (unidentified)", []))
    print(summarise(NAME + " [Pawley, P6/mmm hex a=5.56 c=21.82]", result, ref,
                    {"reflections in range": n_refl,
                     "observed peaks": len(pos),
                     "caveat": "one free intensity per reflection — this Rwp "
                               "is a peak-shape description, not evidence for "
                               "the cell"}))
    result.plot(path=str(OUT / f"{NAME}_pawley_fit.png"))
    np.savetxt(OUT / f"{NAME}_obs_calc_diff.txt",
               np.column_stack([result.two_theta, result.y_obs, result.y_calc,
                                np.asarray(result.y_obs) - np.asarray(result.y_calc)]),
               header="2theta y_obs y_calc y_diff")
    return result, ref


if __name__ == "__main__":
    main()
