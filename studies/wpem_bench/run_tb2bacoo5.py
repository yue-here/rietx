"""WPEM benchmark case 2 — Tb2BaCoO5, the paper's Fig. 2b.

WPEM reports Rp = 6.175 %, Rwp = 10.107 %, a = 3.7571(0), b = 5.8255(8),
c = 11.5538(7) Å, again from a structure-free decomposition (131 reflection
pairs, each with its own free shape).

Tb2BaCoO5 is **not in COD**, so the Rietveld model is built here by cation
substitution into the Immm R2BaMO5 ("Nd2BaNiO5") structure type, taken from
COD 1001501 (Y2BaNiO5, Immm, Y 4j / Ba 2a / Ni 2c / O 8l / O 2d).  Tb replaces
Y and Co replaces Ni; the cell starts at WPEM's published values and the free
coordinates (Tb z, O1 y, O1 z) refine.  That substitution is the *whole*
structural assumption and it is stated rather than hidden: this case tests
whether a structural refinement can be driven from a structure-type analogue
when the exact compound has no deposited model.
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

CASE = "tb2bacoo5"
WPEM_REF = {
    "source": "arXiv 2602.16372 Fig. 2b",
    "rp_percent": 6.175, "rwp_percent": 10.107,
    "a": 3.7571, "b": 5.8255, "c": 11.5538,
    "cases_lattice_file": {"a": 3.7571, "b": 5.82668, "c": 11.55387},
    "method": "whole-pattern decomposition, per-reflection free shapes; "
              "no atomic structure",
}
# WPEM's own notebook starting cell.
START = {"a": 3.7560, "b": 5.8238, "c": 11.5518}


def build_structure() -> pr.Structure:
    """Y2BaNiO5 (COD 1001501) with Y -> Tb and Ni -> Co, at WPEM's start cell."""
    template = cif("y2banio5_template")
    phase = template.phases[0]
    phase.name = "Tb2BaCoO5"
    for atom in phase.atoms:
        if atom.species.startswith("Y"):
            atom.species = "Tb3+"
            atom.label = atom.label.replace("Y", "Tb")
        elif atom.species.startswith("Ni"):
            atom.species = "Co2+"
            atom.label = atom.label.replace("Ni", "Co")
    phase.cell.a.value = START["a"]
    phase.cell.b.value = START["b"]
    phase.cell.c.value = START["c"]
    return pr.Structure(phases=[phase])


def main() -> None:
    data = load(f"{CASE}/intensity.csv")
    tt = np.asarray(data.two_theta)
    print(f"Tb2BaCoO5: {len(tt)} points, {tt[0]:.2f}-{tt[-1]:.2f} deg")

    structure = build_structure()
    phase = structure.phases[0]
    print(f"  model: {phase.space_group}, {len(phase.atoms)} sites "
          f"({', '.join(a.species for a in phase.atoms)}) "
          f"from the Y2BaNiO5 structure type")

    instrument = pr.Instrument.bragg_brentano(radiation="CuKa")
    seed_profile(data, instrument)
    instrument.background = pr.background.auto_background(data, kind="chebyshev")
    seed_background(data, instrument)

    ref = pr.Refinement(structure, instrument)

    with Timer() as t_lb:
        lb, lb_passes = fit_to_fixed_point(
            ref, data, mode="lebail",
            plan=lab_plan(structural=False, preferred_orientation=False),
            label="LeBail")
    show(lb, "Le Bail (fixed pt)")
    ref.history.tag(lb.node_id, "lebail")

    with Timer() as t_rv:
        rv1, rv1_passes = fit_to_fixed_point(
            ref, data, mode="rietveld",
            plan=lab_plan(preferred_orientation=False), label="Rietveld/1-phase")
    show(rv1, "Rietveld (1 phase)")
    show_report(rv1, top=3)

    # --- stage C: act on Layer 0.
    # The single-phase report's unmatched-observed list came back
    # 23.82 / 23.94 / 24.08 / 24.20 / 27.78 deg — witherite 111 / 021 / 002 at
    # Cu Ka, i.e. unreacted BaCO3, the standard leftover of a Ba-bearing
    # solid-state synthesis.  Adding it is a refinement move like any other, so
    # it is recorded in the history DAG rather than done by editing the script.
    witherite = cif("witherite").phases[0]
    witherite.name = "BaCO3"
    witherite.scale = pr.Parameter(value=1e-5, min=0.0, transform="softplus")
    structure2 = ref.fitted_structure.model_copy(deep=True)
    structure2.phases.append(witherite)
    ref.edit(structure=structure2, label="add BaCO3 (witherite) impurity phase")

    with Timer() as t_rv2:
        rv, rv_passes = fit_to_fixed_point(
            ref, data, mode="rietveld",
            plan=lab_plan(preferred_orientation=False), label="Rietveld/+BaCO3")
    show(rv, "Rietveld (+BaCO3)")
    show_report(rv)
    if rv.qpa:
        for q in rv.qpa.phases:
            print(f"    wt% {q.name:12s} {q.weight_fraction * 100:6.2f}")

    fitted = ref.fitted_structure
    cell = fitted.phases[0].cell
    print(f"  cell:   a={cell.a.value:.5f}  b={cell.b.value:.5f}  c={cell.c.value:.5f}")
    print(f"  WPEM:   a={WPEM_REF['a']:.5f}  b={WPEM_REF['b']:.5f}  "
          f"c={WPEM_REF['c']:.5f}")

    rec = record(CASE, "CASES/Tb2BaCoO5/intensity.csv", data, rv, fitted,
                 mode="rietveld",
                 seconds=t_lb.seconds + t_rv.seconds + t_rv2.seconds,
                 reference=WPEM_REF,
                 notes=[
                     "Structure built by Y->Tb, Ni->Co substitution into "
                     "COD 1001501 (Y2BaNiO5, Immm); Tb2BaCoO5 has no COD entry.",
                     "BaCO3 (witherite, COD 9006838) added as a second phase "
                     "after the single-phase FitReport's Layer-0 unmatched list "
                     "landed on witherite 111/021/002.",
                     f"Le Bail fixed point in {lb_passes} passes "
                     f"(Rwp={lb.statistics.rwp * 100:.3f}%, "
                     f"Rp={lb.statistics.rp * 100:.3f}%, "
                     f"nfree={lb.statistics.n_free_parameters}); "
                     f"single-phase Rietveld in {rv1_passes} "
                     f"(Rwp={rv1.statistics.rwp * 100:.3f}%); "
                     f"two-phase Rietveld in {rv_passes}.",
                 ])
    rec.reference["single_phase"] = {
        "rwp_percent": rv1.statistics.rwp * 100,
        "rp_percent": rv1.statistics.rp * 100,
        "n_free": rv1.statistics.n_free_parameters,
    }
    rec.wavelengths = [float(line.wavelength) for line in instrument.source.lines]
    rec.reference["lebail"] = {
        "rwp_percent": lb.statistics.rwp * 100,
        "rp_percent": lb.statistics.rp * 100,
        "n_free": lb.statistics.n_free_parameters,
    }
    rec.save()
    plot(rv, CASE, zooms=[(15, 40), (40, 65)])
    print(f"  saved results/{CASE}.json")


if __name__ == "__main__":
    main()
