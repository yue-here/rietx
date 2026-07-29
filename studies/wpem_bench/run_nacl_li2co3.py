"""WPEM benchmark case 3 — NaCl / Li2CO3 weighed mixtures, the paper's Fig. 2e.

**The only case in the paper with external ground truth.**  Three binary
powders were weighed to nominal NaCl mass fractions of 90 / 40 / 50 %.  WPEM
recovers 91.8 / 40.7 / 47.5 % from integrated component intensities.

Here the same three raw patterns get a two-phase Rietveld refinement and the
weight fractions come from Hill & Howard (1987) Z·M·V scales, which is a
different estimator: it uses the *structure* (cell mass and volume) rather than
integrated peak areas alone, so it needs no calibration constant.

Protocol notes that matter for a fair comparison:

* WPEM held one or both cells **fixed** in two of the three fits (the notebooks
  pass ``'fixed'`` on the 10 % and 50 % runs) and used a Kα1/Kα2-averaged
  single wavelength on those two (``Ave_Waves=True``).  This run refines both
  cells on all three and keeps the real doublet throughout, which is the
  harder setting; the cells are reported so the difference is visible.
* Li2CO3 is strongly platy on (0 0 2), so a March-Dollase axis is declared for
  it.  NaCl gets one on (1 0 0) — cubic halite cleaves on {100}.
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

CASE = "nacl_li2co3"
# Paper Fig. 2e: inferred NaCl mass % against the weighed nominal.
WPEM_REF = {
    "source": "arXiv 2602.16372 Fig. 2e + CASES MassFraction_estimate files",
    "nacl_percent": {"10": 91.829, "40": 40.656, "50": 47.540},
    "paper_nacl_percent": {"10": 91.8, "40": 40.7, "50": 47.5},
    "method": "mass fraction from integrated component intensities of the "
              "decomposed profiles",
}
NOMINAL_NACL = {"10": 90.0, "40": 40.0, "50": 50.0}


def build(tag: str) -> tuple[pr.Structure, pr.Instrument]:
    nacl = cif("nacl")
    nacl.phases[0].name = "NaCl"
    nacl.phases[0].preferred_orientation = pr.schemas.PreferredOrientation(axis=(1, 0, 0))
    li2co3 = cif("li2co3")
    li2co3.phases[0].name = "Li2CO3"
    li2co3.phases[0].preferred_orientation = pr.schemas.PreferredOrientation(axis=(0, 0, 2))
    structure = pr.Structure(phases=[nacl.phases[0], li2co3.phases[0]])
    for phase in structure.phases:
        phase.scale = pr.Parameter(value=1e-3, min=0.0, transform="softplus")
    data = load(f"{CASE}/{tag}/intensity.csv")
    instrument = pr.Instrument.bragg_brentano(radiation="CuKa")
    seed_profile(data, instrument)
    instrument.background = pr.background.auto_background(data, kind="chebyshev")
    seed_background(data, instrument)
    return structure, instrument


def run(tag: str) -> None:
    data = load(f"{CASE}/{tag}/intensity.csv")
    tt = np.asarray(data.two_theta)
    print(f"\n=== NaCl/Li2CO3 nominal {NOMINAL_NACL[tag]:.0f} wt% NaCl: "
          f"{len(tt)} points, {tt[0]:.2f}-{tt[-1]:.2f} deg")

    structure, instrument = build(tag)
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
        rv, rv_passes = fit_to_fixed_point(
            ref, data, mode="rietveld", plan=lab_plan(), label="Rietveld")
    show(rv, "Rietveld")
    show_report(rv, top=4)

    fitted = ref.fitted_structure
    wf = {q.name: q.weight_fraction * 100 for q in rv.qpa.phases} if rv.qpa else {}
    sigma = {q.name: (q.weight_fraction_stderr or 0.0) * 100
             for q in rv.qpa.phases} if rv.qpa else {}
    print(f"  NaCl wt%:  pxrdref {wf.get('NaCl', float('nan')):.2f}"
          f" +/- {sigma.get('NaCl', 0.0):.2f}   "
          f"WPEM {WPEM_REF['nacl_percent'][tag]:.2f}   "
          f"weighed {NOMINAL_NACL[tag]:.1f}")

    rec = record(f"{CASE}_{tag}", f"CASES/StandardSample/{tag}percent/intensity.csv",
                 data, rv, fitted, mode="rietveld",
                 seconds=t_rv.seconds,
                 reference={**WPEM_REF,
                            "nominal_nacl_percent": NOMINAL_NACL[tag],
                            "wpem_nacl_percent": WPEM_REF["nacl_percent"][tag]},
                 notes=[
                     "Both cells refined and the Cu Ka doublet kept; WPEM held "
                     "cells fixed and used an averaged wavelength on the 10% "
                     "and 50% runs.",
                     f"Rietveld reached its fixed point in {rv_passes} passes.",
                 ])
    rec.wavelengths = [float(line.wavelength) for line in instrument.source.lines]
    rec.save()
    plot(rv, f"{CASE}_{tag}", zooms=[(20, 40), (40, 60)])
    print(f"  saved results/{CASE}_{tag}.json")


def main() -> None:
    for tag in ("10", "40", "50"):
        run(tag)


if __name__ == "__main__":
    main()
