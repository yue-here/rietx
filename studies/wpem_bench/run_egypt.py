"""WPEM benchmark case 5 — ancient Egyptian make-up, five phases, Fig. 4.

Synchrotron powder pattern, lambda = 0.96270 A, 5-75 deg 2theta, 7000 points,
of a cosmetic powder containing gypsum, phosgenite, cerussite, galena and
laurionite (Walter et al., 1999, Nature 397, 483).

The paper reports mass fractions 12.53 / 18.53 / 32.02 / 9.69 / 27.23 % for
gypsum / phosgenite / cerussite / galena / laurionite.  **The shipped CASES
output disagrees with the paper on two of the five**: its
``MassFraction_estimate`` file reads 12.66 / 22.28 / 34.19 / 1.68 / 29.20,
i.e. galena 1.68 % where the paper says 9.69 %.  Its refined galena cell also
comes back a = 5.979 A against the paper's 5.9388 A and a literature 5.9362 A,
a +0.7 % error on a cubic lattice parameter.  Both reference values are carried
here so the comparison does not have to pick one.

Structures are the same COD entries WPEM started from — its notebook's starting
cells reproduce COD 2300259 / 9009573 / 9008411 / 9008250 to every printed
digit — plus COD 9008694 for galena.
"""

from __future__ import annotations

import numpy as np
from bench import (
    Timer,
    cif,
    fit_to_fixed_point,
    load,
    plot,
    record,
    seed_background,
    seed_profile,
    show,
    show_report,
)

import pxrdref as pr

CASE = "egypt"
WAVELENGTH = 0.96270
PHASES = ["gypsum", "phosgenite", "cerussite", "galena", "laurionite"]
WPEM_REF = {
    "source": "arXiv 2602.16372 Fig. 4 text; CASES MassFraction/LatticeConstances files",
    "paper_mass_percent": {"gypsum": 12.53, "phosgenite": 18.53,
                           "cerussite": 32.02, "galena": 9.69,
                           "laurionite": 27.23},
    "cases_mass_percent": {"gypsum": 12.658, "phosgenite": 22.279,
                           "cerussite": 34.186, "galena": 1.677,
                           "laurionite": 29.199},
    "paper_cells": {
        "gypsum": {"a": 5.6800, "b": 15.2144, "c": 6.5303, "beta": 118.4841},
        "phosgenite": {"a": 8.1600, "c": 8.8834},
        "cerussite": {"a": 5.1794, "b": 8.4922, "c": 6.1418},
        "galena": {"a": 5.9388},
        "laurionite": {"a": 9.7002, "b": 4.0200, "c": 7.1108},
    },
    "method": "whole-pattern decomposition; mass fractions from component "
              "integrated intensities",
}
PO_AXES = {"gypsum": (0, 2, 0), "phosgenite": (0, 0, 1), "cerussite": (0, 1, 0),
           "galena": (1, 0, 0), "laurionite": (1, 0, 0)}


def main() -> None:
    data = load(f"{CASE}/intensity.csv")
    tt = np.asarray(data.two_theta)
    print(f"Egyptian make-up: {len(tt)} points, {tt[0]:.2f}-{tt[-1]:.2f} deg, "
          f"lambda={WAVELENGTH} A")

    phases = []
    for name in PHASES:
        phase = cif(name).phases[0]
        phase.name = name
        # Hydrogen contributes ~nothing to X-ray scattering and its CIF
        # positions here are placeholders; drop it rather than refine it.
        phase.atoms = [a for a in phase.atoms if a.species.rstrip("+-0123456789") != "H"]
        phase.preferred_orientation = pr.schemas.PreferredOrientation(axis=PO_AXES[name])
        phase.scale = pr.Parameter(value=1e-4, min=0.0, transform="softplus")
        phases.append(phase)
        print(f"  {name:12s} {phase.space_group:12s} "
              f"a={phase.cell.a.value:.4f} b={phase.cell.b.value:.4f} "
              f"c={phase.cell.c.value:.4f} {len(phase.atoms)} sites")
    structure = pr.Structure(phases=phases)

    # Synchrotron, monochromatic: no Ka2, no flat-plate aberration.
    instrument = pr.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    instrument.profile.w.value = 2e-3
    instrument.profile.x.value = 2e-3
    seed_profile(data, instrument)
    instrument.background = pr.background.auto_background(data, kind="chebyshev")
    seed_background(data, instrument)

    plan = pr.RefinementPlan(stages=[
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("zero", ["instrument.zero_shift"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        pr.Stage("sample_profile", ["phases.*.lor_size", "phases.*.lor_strain"]),
        pr.Stage("biso", ["phases.*.atoms.*.biso", "phases.*.atoms.*.adp.*"]),
        pr.Stage("preferred_orientation", ["phases.*.preferred_orientation.r"]),
    ])

    ref = pr.Refinement(structure, instrument)
    # --- no Le Bail stage, and that absence is a measured result.
    # pxrdref's Le Bail extraction partitions max(y_obs - y_bkg, 0) *per phase*
    # with no mechanism to arbitrate two phases claiming the same channel, so on
    # a multiphase pattern the phases inflate each other without bound.  Measured
    # across this benchmark, the failure tracks the phase count exactly:
    #   1 phase  (PbSO4)      Le Bail converges, Rwp 8.6 %
    #   1 phase  (Tb2BaCoO5)  converges, Rwp 17.3 %
    #   2 phases (NaCl/Li2CO3) Rwp 1924 %
    #   2 phases (Mn-Ru)       Rwp 1769-9281 %
    #   3 phases (Ti-15Nb)     Rwp 2.6e5 %
    # and it survives seeding both the profile widths and the background.  A
    # structural model ties intensities to atoms and has no such freedom, so
    # Rietveld is the only route here.  See REPORT.md 4.1(g).

    with Timer() as t_rv:
        rv, rv_passes = fit_to_fixed_point(ref, data, mode="rietveld",
                                           plan=plan, label="Rietveld")
    show(rv, "Rietveld")
    show_report(rv, top=5)

    fitted = ref.fitted_structure
    if rv.qpa:
        print(f"  {'phase':12s} {'pxrdref wt%':>14s} {'paper':>8s} {'CASES':>8s}")
        for q in rv.qpa.phases:
            sigma = q.weight_fraction_stderr or 0.0
            print(f"  {q.name:12s} {q.weight_fraction * 100:8.2f} +/-{sigma * 100:4.2f} "
                  f"{WPEM_REF['paper_mass_percent'][q.name]:8.2f} "
                  f"{WPEM_REF['cases_mass_percent'][q.name]:8.2f}")

    rec = record(CASE, "CASES/EgyptianMakeup/WPEMfitting/intensity.csv", data,
                 rv, fitted, mode="rietveld",
                 seconds=t_rv.seconds, reference=WPEM_REF,
                 notes=[
                     "Paper and shipped CASES mass fractions disagree "
                     "(galena 9.69% vs 1.68%); both are recorded.",
                     "H sites dropped from gypsum and laurionite — negligible "
                     "X-ray scattering, placeholder CIF positions.",
                     f"Rietveld reached its fixed point in {rv_passes} passes.",
                 ])
    rec.wavelengths = [WAVELENGTH]
    rec.save()
    plot(rv, CASE, zooms=[(5, 20), (20, 35), (35, 50)])
    print(f"  saved results/{CASE}.json")


if __name__ == "__main__":
    main()
