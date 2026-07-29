"""Sensitivity and validation checks on the *non-refinement* scaffolding.

Four claims were made about the supporting tooling in the first report.  Three
were asserted rather than measured, and one (the autoindexer's verdict on
HL2-1) carries a conclusion.  This script measures all four.

A: the goniometer radius is an assumption, not a datum — how much does it cost?
B: the Sb structure was recalled from memory — does the starting value survive?
C: the indexer covers 2-parameter metrics only — would a single-phase
   orthorhombic compound be mistaken for the multiphase mess HL2-1 looks like?
D: the phase screen matches positions and ignores intensity — does it actually
   find a known answer?
"""
from __future__ import annotations

import index_hl2 as ix
import match_hl2 as mx
import numpy as np
import run_fesb
import run_mnsb34
from common import EX, P

import pxrdref as pr
from pxrdref.background import auto_background
from pxrdref.crystallography.symmetry import generate_reflections


def rule(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# --------------------------------------------------------------------------
# A. goniometer radius: assumed 217.5 mm (pxrd-refine's default).  The .inp
#    never states it.  R enters twice — the FCJ axial ratios derived from
#    Simple_Axial_Model(!axial, 10 mm), and the displacement aberration
#    Delta(2theta) = -(2s/R) cos(theta) — so vary it consistently in both.
# --------------------------------------------------------------------------
def check_a():
    rule("A. what a wrong goniometer radius costs (FeSb_19RBM)")
    data = pr.read_pattern(EX / run_fesb.NAME / f"{run_fesb.NAME}.xy").crop(
        run_fesb.LO, run_fesb.HI)
    print(f"{'R (mm)':>8} {'S/L = H/L':>10} {'Rwp':>8} {'a (A)':>12} {'c (A)':>12} "
          f"{'displ (mm)':>11} {'a shift':>10}")
    ref_a = None
    for radius in (180.0, 200.0, 217.5, 240.0, 280.0, 320.0):
        structure, inst = run_fesb.build()
        inst.geometry.goniometer_radius_mm = radius
        axial = 10.0 / 2 / radius
        inst.geometry.axial_sl.value = axial
        inst.geometry.axial_hl.value = axial
        inst.background = auto_background(data, kind="chebyshev",
                                          wavelength=inst.source.primary_wavelength)
        ref = pr.Refinement(structure, inst)
        res = ref.fit(data, plan=run_fesb.plan())
        ph = ref.fitted_structure.phases[0]
        a = ph.cell.a.value
        ref_a = a if ref_a is None else ref_a
        shift = "" if radius == 180.0 else f"{(a / ref_a - 1) * 1e6:+8.0f} ppm"
        print(f"{radius:8.1f} {axial:10.4f} {res.statistics.rwp * 100:7.3f}% "
              f"{a:12.6f} {ph.cell.c.value:12.6f} "
              f"{ref.fitted_instrument.geometry.sample_displacement.value:11.5f} "
              f"{shift:>10}")


# --------------------------------------------------------------------------
# B. the Sb impurity cell and z came from memory, not from a file or a
#    database.  Restart the two-phase fit from deliberately wrong values and
#    see whether the refinement recovers, or whether it just sits where it
#    was put.
# --------------------------------------------------------------------------
def check_b():
    rule("B. does the recalled Sb structure survive being wrong? (MnSb_34)")
    data = pr.read_pattern(EX / run_mnsb34.NAME / run_mnsb34.FILE).crop(
        run_mnsb34.LO, run_mnsb34.HI)
    print(f"{'start a':>9} {'start c':>9} {'start z':>8} | {'Rwp':>8} "
          f"{'final a':>10} {'final c':>11} {'final z':>9} {'Sb wt%':>9}")
    trials = [(4.3084, 11.2740, 0.23349, "recalled literature"),
              (4.2000, 11.2740, 0.23349, "a  -2.5 %"),
              (4.4000, 11.2740, 0.23349, "a  +2.1 %"),
              (4.3084, 10.9000, 0.23349, "c  -3.3 %"),
              (4.3084, 11.6500, 0.23349, "c  +3.3 %"),
              (4.3084, 11.2740, 0.20000, "z  -0.033"),
              (4.3084, 11.2740, 0.26629, "z from the .inp's dead block")]
    for a0, c0, z0, label in trials:
        s, i = run_mnsb34.build()
        sb = s.phases[1]
        # bounded to a physically plausible window: an unbounded cell on a
        # 1.7 wt% phase started 3 % wrong simply runs away (measured: the
        # reflection generator asked for 1.6 PiB).  Any refiner would set these.
        sb.cell = pr.Cell(a=P(value=a0, min=3.6, max=5.2),
                          b=P(value=a0, min=3.6, max=5.2),
                          c=P(value=c0, min=9.5, max=13.5),
                          alpha=P(value=90.0), beta=P(value=90.0),
                          gamma=P(value=120.0))
        sb.atoms[0].z.value = z0
        i.background = auto_background(data, kind="chebyshev",
                                       wavelength=i.source.primary_wavelength)
        ref = pr.Refinement(s, i, solver="lm")
        res = ref.fit(data, plan=run_mnsb34.plan())
        f = ref.fitted_structure.phases[1]
        w = next((q.weight_fraction for q in res.qpa.phases if q.name == "Sb"), float("nan"))
        print(f"{a0:9.4f} {c0:9.4f} {z0:8.5f} | {res.statistics.rwp * 100:7.3f}% "
              f"{f.cell.a.value:10.5f} {f.cell.c.value:11.5f} "
              f"{f.atoms[0].z.value:9.5f} {w * 100:8.2f}%   {label}")


# --------------------------------------------------------------------------
# C. the indexer solves Q = A*M + C*l^2 — cubic, tetragonal, hexagonal only.
#    Feed it the *exact* peak list of a single-phase orthorhombic compound and
#    see what it reports.  If it scores like HL2-1 did, then "no 2-parameter
#    metric indexes it" does not distinguish multiphase from low symmetry.
# --------------------------------------------------------------------------
def synth_peaks(sg, cell, *, lo=5.0, hi=90.0, merge=0.03):
    """Peak list a perfect experiment would give: allowed lines, merged when
    closer than `merge` deg, weighted by multiplicity (a stand-in for
    intensity, since the point of the test is positions)."""
    rs = generate_reflections(sg, cell, ix.LAM, hi, lo)
    tt = np.degrees(2 * np.arcsin(np.clip(ix.LAM / (2 * np.asarray(rs.d)), -1, 1)))
    mult = np.asarray(rs.multiplicity, dtype=float)
    order = np.argsort(tt)
    tt, mult = tt[order], mult[order]
    pos, wt = [], []
    for t, m in zip(tt, mult):
        if pos and t - pos[-1] < merge:
            wt[-1] += m
        else:
            pos.append(t)
            wt.append(m)
    return np.asarray(pos), np.asarray(wt)


def best_scores(pos, wt):
    q = ix.q_of(pos)
    out = {}
    Ns = sorted({h * h + k * k + ll * ll for h in range(6) for k in range(6)
                 for ll in range(6)} - {0})
    best = 0.0
    for i in np.argsort(wt)[::-1][:9]:
        for n in Ns:
            A = q[i] / n
            if A <= 1e-6:
                continue
            grid = np.array([A * m for m in Ns])
            ok = np.abs(q[:, None] - grid[None, :]).min(axis=1) < 0.004 * q
            best = max(best, wt[ok].sum() / wt.sum())
    out["cubic"] = best
    for system in ("tet", "hex"):
        found = ix.candidates(q, wt, "hex" if system == "hex" else "tet")
        out[system] = max((v[0] for v in found.values()), default=0.0)
    return out


def check_c():
    rule("C. would a single-phase LOW-SYMMETRY compound look like HL2-1?")
    cases = [
        ("MnSb            hexagonal  (known-good control)",
         "P 63/m m c", (4.1408, 4.1408, 5.7862, 90, 90, 120)),
        ("FeSb2           orthorhombic Pnnm",
         "P n n m", (5.8328, 6.5376, 3.1973, 90, 90, 90)),
        ("Sb2O3           orthorhombic Pccn",
         "P c c n", (4.9110, 12.4640, 5.4120, 90, 90, 90)),
        ("Mn3O4           tetragonal I41/amd (should pass)",
         "I 41/a m d :2", (5.7621, 5.7621, 9.4696, 90, 90, 90)),
        ("Na2CO3          monoclinic C2/m",
         "C 1 2/m 1", (8.9200, 5.2450, 6.0500, 90, 101.35, 90)),
    ]
    print(f"{'synthetic single-phase pattern':52s} {'peaks':>6} {'cubic':>7} "
          f"{'tet':>7} {'hex':>7}")
    for label, sg, cell in cases:
        pos, wt = synth_peaks(sg, cell)
        s = best_scores(pos, wt)
        print(f"{label:52s} {len(pos):6d} {s['cubic']:6.0%} {s['tet']:6.0%} "
              f"{s['hex']:6.0%}")
    pos, prom, *_ = ix.peak_list(EX / "HL2-1" / "HL2-1_2.xy")
    s = best_scores(pos, prom)
    print(f"{'HL2-1 (measured, for comparison)':52s} {len(pos):6d} "
          f"{s['cubic']:6.0%} {s['tet']:6.0%} {s['hex']:6.0%}")


# --------------------------------------------------------------------------
# D. the 36-phase screen matches positions and ignores structure factors.
#    Point it at a pattern whose answer is known and see whether the truth
#    comes out on top.  A screen that cannot find MnSb + Sb in MnSb_34 cannot
#    be read as evidence of absence in HL2-1.
# --------------------------------------------------------------------------
def check_d():
    rule("D. does the phase screen find a KNOWN answer? (MnSb_34 = MnSb + Sb)")
    pos, prom, *_ = ix.peak_list(EX / "MnSb_34_impure" / "MnSb_34.xy")
    rows = mx.screen(pos, prom)
    print(f"{'rank':>4} {'phase':24s} {'obs intensity indexed':>22s} "
          f"{'its lines seen':>15s} {'n lines':>8s}")
    for rank, (f_obs, f_calc, n, name, _) in enumerate(rows[:8], 1):
        mark = "  <-- truth" if name in ("MnSb (NiAs)", "Sb (A7)") else ""
        print(f"{rank:4d} {name:24s} {f_obs:21.1%} {f_calc:15.1%} {n:8d}{mark}")
    for rank, (f_obs, f_calc, n, name, _) in enumerate(rows, 1):
        if name in ("MnSb (NiAs)", "Sb (A7)") and rank > 8:
            print(f"{rank:4d} {name:24s} {f_obs:21.1%} {f_calc:15.1%} {n:8d}"
                  f"  <-- truth, ranked {rank}")


if __name__ == "__main__":
    check_c()
    check_d()
    check_b()
    check_a()
