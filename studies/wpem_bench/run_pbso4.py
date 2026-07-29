"""WPEM benchmark case 1 — PbSO4 (anglesite), the paper's Fig. 2a.

WPEM reports Rp = 3.023 %, Rwp = 7.124 %, a = 8.4852(7), b = 5.4015(6),
c = 6.9642(0) Å, from a whole-pattern *decomposition*: its notebook passes
only ``Lattice_constants = [[8.48527, 5.40156, 6.9642, 90, 90, 90]]`` and lets
each of the 383 reflection pairs carry its own (γ, σ, Δ, w) — no atoms.

Here the same raw pattern is refined structurally, in the order
AGENT_PROTOCOL §2 prescribes:

  1. Le Bail (structure-free) to a fixed point — cell, zero, displacement and
     profile without any structural assumption.
  2. Rietveld from that state, with the lab flat-plate physics (Kα2 ratio, FCJ
     axial divergence) and then coordinates, displacement parameters and
     preferred orientation.

Setting note: COD 9015524 is anglesite in the **Pbnm** setting, whose
(a, b, c) = (c, a, b) of the Pnma setting everyone quotes.  The refined cell is
mapped back to Pnma before comparison.
"""

from __future__ import annotations

import numpy as np
from bench import (
    Timer,
    cif,
    fit_to_fixed_point,
    lab_plan,
    load,
    plot,
    record,
    seed_background,
    seed_profile,
    show,
    show_report,
)

import pxrdref as pr

CASE = "pbso4"
WPEM_REF = {
    "source": "arXiv 2602.16372 Fig. 2a; cell in the standard Pnma setting",
    "rp_percent": 3.023, "rwp_percent": 7.124,
    "a": 8.4852, "b": 5.4015, "c": 6.9642,
    "cases_lattice_file": {"a": 8.486, "b": 5.4032, "c": 6.96378},
    "method": "whole-pattern decomposition, per-reflection free (gamma, sigma, "
              "Delta, w); no atomic structure",
    # Counted from WPEM's own shipped WPEMPeakParas file: 766 rows (383
    # reflections x 2 emission lines), with 766 distinct weights, 764 distinct
    # Lorentz-Gauss mixings, 761 distinct Lorentzian widths and 703 distinct
    # Gaussian variances.  The peak centres follow the cell through Bragg's law
    # and are not counted; 766 x 4 is the free peak block.
    "wpem_free_parameters": 766 * 4,
    "wpem_free_parameters_note":
        "766 peaks x (w, Delta, gamma, sigma^2), counted from WPEMPeakParas; "
        "excludes the 3 cell parameters and the 1000-anchor background",
}
# Literature anglesite for an outside anchor (COD 9015524, Antao 2012, Pnma
# setting): a = 8.48024, b = 5.39754, c = 6.95802 Å.
LITERATURE = {"a": 8.48024, "b": 5.39754, "c": 6.95802}


def pnma_from_pbnm(cell: dict) -> dict:
    """Pbnm (a,b,c) -> Pnma (b,c,a): the same lattice, standard axis names."""
    return {"a": cell["b"], "b": cell["c"], "c": cell["a"]}


def main() -> None:
    data = load(f"{CASE}/intensity.csv")
    tt = np.asarray(data.two_theta)
    print(f"PbSO4: {len(tt)} points, {tt[0]:.2f}-{tt[-1]:.2f} deg")

    structure = cif("pbso4_anglesite")
    phase = structure.phases[0]
    phase.name = "PbSO4"
    phase.preferred_orientation = pr.schemas.PreferredOrientation(axis=(0, 0, 1))
    print(f"  model: {phase.space_group}, {len(phase.atoms)} sites, "
          f"a={phase.cell.a.value:.4f} b={phase.cell.b.value:.4f} "
          f"c={phase.cell.c.value:.4f} (Pbnm setting)")

    instrument = pr.Instrument.bragg_brentano(radiation="CuKa")
    # Chebyshev, order chosen by the package's masked-channel BIC + Durbin-Watson
    # rule.  Deliberately *not* the P-spline: on this pattern the auto P-spline
    # takes 53 coefficients whose neighbours correlate at rho > 0.99 and whose
    # block absorbs R^2 = 0.56 of a Biso column — the exact failure mode
    # CLAUDE.md's background invariant is about.
    seed_profile(data, instrument)
    instrument.background = pr.background.auto_background(data, kind="chebyshev")
    seed_background(data, instrument)

    ref = pr.Refinement(structure, instrument)

    # --- stage A: Le Bail, structure-free, to a fixed point
    with Timer() as t_lb:
        lb, lb_passes = fit_to_fixed_point(
            ref, data, mode="lebail",
            plan=lab_plan(structural=False, preferred_orientation=False),
            label="LeBail")
    show(lb, "Le Bail (fixed pt)")
    ref.history.tag(lb.node_id, "lebail")

    # --- stage B: Rietveld from the Le Bail cell/profile
    with Timer() as t_rv:
        rv, rv_passes = fit_to_fixed_point(
            ref, data, mode="rietveld", plan=lab_plan(), label="Rietveld")
    show(rv, "Rietveld")
    show_report(rv)

    fitted = ref.fitted_structure
    pbnm = {k: float(getattr(fitted.phases[0].cell, k).value) for k in ("a", "b", "c")}
    pnma = pnma_from_pbnm(pbnm)
    print(f"  cell (Pnma):  a={pnma['a']:.5f}  b={pnma['b']:.5f}  c={pnma['c']:.5f}")
    print(f"  WPEM       :  a={WPEM_REF['a']:.5f}  b={WPEM_REF['b']:.5f}  "
          f"c={WPEM_REF['c']:.5f}")
    print(f"  COD 9015524:  a={LITERATURE['a']:.5f}  b={LITERATURE['b']:.5f}  "
          f"c={LITERATURE['c']:.5f}")

    rec = record(CASE, "CASES/PbSO4/intensity.csv", data, rv, fitted,
                 mode="rietveld", seconds=t_lb.seconds + t_rv.seconds,
                 reference=WPEM_REF,
                 notes=[
                     "COD 9015524 is the Pbnm setting; PbSO4_pnma below is the "
                     "standard-setting map (b,c,a) used for comparison.",
                     f"Le Bail to a fixed point in {lb_passes} passes: "
                     f"Rwp={lb.statistics.rwp * 100:.3f}% "
                     f"Rp={lb.statistics.rp * 100:.3f}% "
                     f"nfree={lb.statistics.n_free_parameters}",
                     f"Rietveld reached its fixed point in {rv_passes} passes.",
                 ])
    rec.wavelengths = [float(line.wavelength) for line in instrument.source.lines]
    rec.cells["PbSO4_pnma"] = pnma
    rec.reference["literature_pnma"] = LITERATURE
    rec.reference["lebail"] = {
        "rwp_percent": lb.statistics.rwp * 100,
        "rp_percent": lb.statistics.rp * 100,
        "n_free": lb.statistics.n_free_parameters,
    }
    rec.save()
    plot(rv, CASE, zooms=[(20, 35), (40, 55), (100, 130)])
    print(f"  saved results/{CASE}.json")


if __name__ == "__main__":
    main()
