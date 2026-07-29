"""WPEM benchmark case 6 — Ru-substituted Mn oxide, the paper's Fig. 3b.

The paper's headline for this case is Rp = 1.447 %, Rwp = 3.129 %, obtained by
"screening candidate Ru site occupations in a 3 x 3 supercell model" and
deposited as CCDC 2530452.

Two things about the shipped CASES output need saying before any comparison:

* Its ``LatticeConstances`` file is a **cubic** a = 9.40851 A phase plus a
  tetragonal a = 4.41115, c = 3.04844 A phase — bixbyite (Mn,Ru)2O3 plus
  rutile RuO2 in their *ordinary* cells, not a 3 x 3 supercell (which would be
  ~28 A).  The paper's own text meanwhile calls the parent "orthorhombic
  Mn2O3", which the shipped cubic cell is not.
* The run is dated 2023-06-16, three years before the deposition it is
  attributed to.

So this run does what the shipped data actually supports: a two-phase Rietveld
of bixbyite (Mn,Ru)2O3 + rutile RuO2, with Ru refined onto the two bixbyite Mn
sites as a substitutional occupancy.  It cannot reproduce a supercell ordering
search, and does not claim to.
"""

from __future__ import annotations

import numpy as np
from bench import Timer, cif, fit_to_fixed_point, lab_plan, load, plot, record, show, show_report

import pxrdref as pr

CASE = "mnru"
WPEM_REF = {
    "source": "arXiv 2602.16372 Fig. 3b text; CASES LatticeConstances_2023.6.16",
    "rp_percent": 1.447, "rwp_percent": 3.129,
    "cases_cells": {"(Mn,Ru)2O3": {"a": 9.40851},
                    "RuO2": {"a": 4.41115, "c": 3.04844}},
    "method": "whole-pattern decomposition; the paper attributes the result to "
              "a 3x3 supercell ordering search (CCDC 2530452) that the shipped "
              "cells do not correspond to",
}


def main() -> None:
    data = load(f"{CASE}/intensity.csv")
    tt = np.asarray(data.two_theta)
    print(f"Mn-Ru oxide: {len(tt)} points, {tt[0]:.2f}-{tt[-1]:.2f} deg")

    bixbyite = cif("bixbyite").phases[0]
    bixbyite.name = "(Mn,Ru)2O3"
    bixbyite.cell.a.value = 9.4085
    # Ru substitutes on both octahedral Mn sites.  Occupancies are *tied* to a
    # single refined Ru fraction below rather than freed independently: two
    # site occupancies against one composition is one parameter reported twice.
    for atom in list(bixbyite.atoms):
        if atom.species.startswith("Mn"):
            bixbyite.atoms.append(pr.Atom(
                label=atom.label.replace("Mn", "Ru"), species="Ru",
                x=pr.Parameter(value=atom.x.value),
                y=pr.Parameter(value=atom.y.value),
                z=pr.Parameter(value=atom.z.value),
                occ=pr.Parameter(value=0.10, vary=False),
                biso=pr.Parameter(value=0.5, min=0.0, max=25.0)))
            atom.occ = pr.Parameter(value=0.90, vary=False)
    bixbyite.scale = pr.Parameter(value=1e-4, min=0.0, transform="softplus")

    ruo2 = cif("ruo2").phases[0]
    ruo2.name = "RuO2"
    ruo2.cell.a.value = 4.4911
    ruo2.cell.c.value = 3.1064
    ruo2.scale = pr.Parameter(value=1e-5, min=0.0, transform="softplus")

    structure = pr.Structure(phases=[bixbyite, ruo2])
    instrument = pr.Instrument.bragg_brentano(radiation="CuKa")
    instrument.background = pr.background.auto_background(data, kind="chebyshev")

    ref = pr.Refinement(structure, instrument)
    with Timer() as t_lb:
        lb, lb_passes = fit_to_fixed_point(
            ref, data, mode="lebail",
            plan=lab_plan(structural=False, preferred_orientation=False),
            label="LeBail")
    show(lb, "Le Bail (fixed pt)")

    with Timer() as t_rv:
        rv, rv_passes = fit_to_fixed_point(
            ref, data, mode="rietveld",
            plan=lab_plan(preferred_orientation=False), label="Rietveld")
    show(rv, "Rietveld")
    show_report(rv, top=5)

    fitted = ref.fitted_structure
    for phase in fitted.phases:
        print(f"  {phase.name:12s} a={phase.cell.a.value:.5f} "
              f"c={phase.cell.c.value:.5f}")
    if rv.qpa:
        for q in rv.qpa.phases:
            print(f"    wt% {q.name:12s} {q.weight_fraction * 100:6.2f}")

    rec = record(CASE, "CASES/Mn-Ru2O3/intensity.csv", data, rv, fitted,
                 mode="rietveld", seconds=t_lb.seconds + t_rv.seconds,
                 reference=WPEM_REF,
                 notes=[
                     "Two-phase bixbyite Ia-3 + rutile model, matching the "
                     "cells in the shipped CASES output; no supercell ordering "
                     "search is attempted.",
                     "Ru occupancy held at 0.10 on both bixbyite Mn sites "
                     "(occupancy is degenerate with scale and Biso).",
                     f"Le Bail fixed point in {lb_passes} passes "
                     f"(Rwp={lb.statistics.rwp * 100:.3f}%); Rietveld in "
                     f"{rv_passes}.",
                 ])
    rec.wavelengths = [float(line.wavelength) for line in instrument.source.lines]
    rec.reference["lebail"] = {"rwp_percent": lb.statistics.rwp * 100,
                               "rp_percent": lb.statistics.rp * 100,
                               "n_free": lb.statistics.n_free_parameters}
    rec.save()
    plot(rv, CASE, zooms=[(20, 40), (40, 60)])
    print(f"  saved results/{CASE}.json")


if __name__ == "__main__":
    main()
