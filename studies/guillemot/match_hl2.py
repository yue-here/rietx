"""Candidate-phase screen for HL2-1.

The pair-seeded indexer (index_hl2.py) finds no two-parameter metric that
indexes HL2-1, which is what a multiphase mixture looks like.  So instead of
indexing, screen the observed peak list against a library of cells drawn from
(a) the chemistry the rest of this collection is made of — Fe, Mn, Co, Na, Sb,
O — and (b) the phases that turn up on any laboratory diffractometer.

Score: the fraction of observed peak *prominence* that has a symmetry-allowed
line of the candidate within tolerance, reported alongside how many lines the
candidate predicts (a big cell indexes everything and means nothing) and the
fraction of the candidate's own predicted lines that are actually seen.
"""
from __future__ import annotations

import numpy as np
from common import EX
from index_hl2 import LAM, peak_list

from pxrdref.crystallography.symmetry import generate_reflections

TOL_DEG = 0.12

#: name -> (space group, (a, b, c, alpha, beta, gamma))
LIBRARY = {
    # --- what the rest of the collection is made of -----------------------
    "FeSb (NiAs)":        ("P 63/m m c", (4.1138, 4.1138, 5.1572, 90, 90, 120)),
    "MnSb (NiAs)":        ("P 63/m m c", (4.1408, 4.1408, 5.7862, 90, 90, 120)),
    "CoSb (NiAs)":        ("P 63/m m c", (3.8660, 3.8660, 5.1880, 90, 90, 120)),
    "NiSb (NiAs)":        ("P 63/m m c", (3.9460, 3.9460, 5.1350, 90, 90, 120)),
    "Sb (A7)":            ("R -3 m :H", (4.3084, 4.3084, 11.2740, 90, 90, 120)),
    "FeSb2 (marcasite)":  ("P n n m", (5.8328, 6.5376, 3.1973, 90, 90, 90)),
    "Mn2Sb (Cu2Sb)":      ("P 4/n m m :2", (4.0780, 4.0780, 6.5570, 90, 90, 90)),
    "CoSb2":              ("P 1 21/c 1", (6.5073, 6.3879, 6.5400, 90, 117.6, 90)),
    "CoSb3 (skutterudite)": ("I m -3", (9.0385, 9.0385, 9.0385, 90, 90, 90)),
    "Na3Sb":              ("P 63/m m c", (5.3550, 5.3550, 9.4960, 90, 90, 120)),
    "NaSb":               ("P 1 21/c 1", (6.8000, 6.3400, 12.4800, 90, 117.6, 90)),
    "Na0.74CoO2 (P2)":    ("P 63/m m c", (2.8322, 2.8322, 10.9169, 90, 90, 120)),
    "NaCoO2 (O3)":        ("R -3 m :H", (2.8880, 2.8880, 15.6000, 90, 90, 120)),
    # --- oxides of the same metals ---------------------------------------
    "Fe2O3 hematite":     ("R -3 c :H", (5.0356, 5.0356, 13.7489, 90, 90, 120)),
    "Fe3O4 magnetite":    ("F d -3 m :2", (8.3960, 8.3960, 8.3960, 90, 90, 90)),
    "FeO wuestite":       ("F m -3 m", (4.3260, 4.3260, 4.3260, 90, 90, 90)),
    "MnO manganosite":    ("F m -3 m", (4.4448, 4.4448, 4.4448, 90, 90, 90)),
    "Mn3O4 hausmannite":  ("I 41/a m d :2", (5.7621, 5.7621, 9.4696, 90, 90, 90)),
    "Mn2O3 bixbyite":     ("I a -3", (9.4091, 9.4091, 9.4091, 90, 90, 90)),
    "CoO":                ("F m -3 m", (4.2612, 4.2612, 4.2612, 90, 90, 90)),
    "Co3O4":              ("F d -3 m :2", (8.0840, 8.0840, 8.0840, 90, 90, 90)),
    "Sb2O3 senarmontite": ("F d -3 m :2", (11.1520, 11.1520, 11.1520, 90, 90, 90)),
    "Sb2O3 valentinite":  ("P c c n", (4.9110, 12.4640, 5.4120, 90, 90, 90)),
    "Sb2O4 cervantite":   ("P n a 21", (5.4360, 4.8100, 11.7600, 90, 90, 90)),
    # --- metals and everyday laboratory phases ---------------------------
    "Fe (bcc)":           ("I m -3 m", (2.8665, 2.8665, 2.8665, 90, 90, 90)),
    "Mn (alpha)":         ("I -4 3 m", (8.9125, 8.9125, 8.9125, 90, 90, 90)),
    "Co (hcp)":           ("P 63/m m c", (2.5071, 2.5071, 4.0695, 90, 90, 120)),
    "Cu":                 ("F m -3 m", (3.6149, 3.6149, 3.6149, 90, 90, 90)),
    "Al (holder)":        ("F m -3 m", (4.0495, 4.0495, 4.0495, 90, 90, 90)),
    "Si standard":        ("F d -3 m :2", (5.4309, 5.4309, 5.4309, 90, 90, 90)),
    "NaCl":               ("F m -3 m", (5.6402, 5.6402, 5.6402, 90, 90, 90)),
    "MgO":                ("F m -3 m", (4.2120, 4.2120, 4.2120, 90, 90, 90)),
    "Al2O3 corundum":     ("R -3 c :H", (4.7587, 4.7587, 12.9929, 90, 90, 120)),
    "graphite":           ("P 63/m m c", (2.4640, 2.4640, 6.7110, 90, 90, 120)),
    "ZnO":                ("P 63 m c", (3.2495, 3.2495, 5.2069, 90, 90, 120)),
    "Na2CO3":             ("C 1 2/m 1", (8.9200, 5.2450, 6.0500, 90, 101.35, 90)),
}


def lines(sg, cell, lo=5.0, hi=90.0):
    rs = generate_reflections(sg, cell, LAM, hi, lo)
    d = np.asarray(rs.d)
    return np.degrees(2 * np.arcsin(np.clip(LAM / (2 * d), -1, 1)))


def screen(pos, prom, lo=5.0, hi=90.0):
    rows = []
    for name, (sg, cell) in LIBRARY.items():
        try:
            tt = lines(sg, cell, lo, hi)
        except Exception as exc:            # noqa: BLE001 - report, don't stop
            rows.append((0.0, 0.0, 0, name, f"ERROR {exc}"))
            continue
        if tt.size == 0:
            continue
        gap_obs = np.abs(pos[:, None] - tt[None, :]).min(axis=1)
        hit_obs = gap_obs < TOL_DEG
        gap_calc = np.abs(tt[:, None] - pos[None, :]).min(axis=1)
        hit_calc = gap_calc < TOL_DEG
        rows.append((prom[hit_obs].sum() / prom.sum(), hit_calc.mean(),
                     int(tt.size), name, ""))
    return sorted(rows, reverse=True)


def main():
    pos, prom, *_ = peak_list(EX / "HL2-1" / "HL2-1_2.xy")
    print(f"HL2-1: {len(pos)} observed peaks, tolerance {TOL_DEG} deg 2theta\n")
    print(f"{'phase':24s} {'obs intensity indexed':>22s} {'its lines seen':>15s} "
          f"{'n lines':>8s}")
    for f_obs, f_calc, n, name, err in screen(pos, prom):
        print(f"{name:24s} {f_obs:21.1%} {f_calc:15.1%} {n:8d}  {err}")


if __name__ == "__main__":
    main()
