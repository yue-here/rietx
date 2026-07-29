"""WPEM benchmark case 4 — Ti-15Nb thin film, three phases, the paper's Fig. 2d.

WPEM reports Rp = 5.033 %, Rwp = 9.005 %, and
  beta  (bcc) a = 3.2345(9)
  alpha (hcp) a = 2.9977(8)  c = 4.6817(3)
  alpha'(hcp) a = 2.9785(4)  c = 4.7768(3)
with phase fractions beta : alpha : alpha' = 5.49 : 48.32 : 46.19 %.

There is **no ground truth** for this case — the fractions are WPEM's own
estimate from integrated component intensities.  What can be checked is
whether an independent code, using a structural model and Hill-Howard scales,
lands in the same place.

The hard part is not the fit, it is the *identifiability*: alpha and alpha' are
both hcp Ti with cells differing by well under a percent, so their reflections
overlap almost everywhere.  That is precisely the regime where AGENT_PROTOCOL
§3 says a number can be produced without being measured, so this run reports
the alpha/alpha' scale correlation alongside the fractions.

A rolled/sputtered thin film is also strongly textured, so every phase carries
a March-Dollase axis: (1 1 0) for bcc and (0 0 2) for hcp, the usual fibre
textures.
"""

from __future__ import annotations

import numpy as np
from bench import Timer, cif, fit_to_fixed_point, lab_plan, load, plot, record, show, show_report

import pxrdref as pr

CASE = "ti15nb"
WPEM_REF = {
    "source": "arXiv 2602.16372 Fig. 2d + CASES LatticeConstances/MassFraction files",
    "rp_percent": 5.033, "rwp_percent": 9.005,
    "cells": {"beta": {"a": 3.2345},
              "alpha": {"a": 2.9977, "c": 4.6817},
              "alpha_prime": {"a": 2.9785, "c": 4.7768}},
    "fractions_percent": {"beta": 5.496, "alpha": 48.317, "alpha_prime": 46.187},
    "method": "phase fractions from integrated intensities of the decomposed "
              "component profiles; no atomic structure, no ground truth",
}
# WPEM's notebook starting cells, and the cells this run actually starts from.
#
# Starting where WPEM starts does not work here, and the reason is a real
# difference between the two methods rather than a tuning detail.  WPEM's
# alpha start (a = 2.9064) is 3.0 % from its own refined answer (2.9977) and
# its alpha' start (c = 4.675) is 2.1 % from 4.7768.  Its EM peak centres are
# free to migrate under a Bragg constraint, so it walks there.  pxrdref freezes
# each reflection's evaluation window at stage compile (the frozen-per-stage
# discreteness invariant, which is what keeps the residual smooth for the
# analytic Jacobian), and a 3 % cell error at 35 deg 2theta displaces a peak by
# ~0.6 deg — an order of magnitude outside its window.  Run cold from WPEM's
# cells, the Le Bail lands at Rwp = 7225 % with every profile term on a bound.
# AGENT_PROTOCOL §1 states the precondition ("the starting cell is within ~1 %")
# and Layer 2 is designed to say `reindex_or_recheck_cell` rather than report a
# small shift.  So the phase *metric* is taken as given here — from WPEM's
# refined cells — and what is being benchmarked is everything downstream of it:
# the intensities, the phase fractions and whether alpha/alpha' are separable.
WPEM_START = {"beta": (3.282, 3.282), "alpha": (2.9064, 4.6667),
              "alpha_prime": (2.93, 4.675)}
START = {"beta": (3.2345, 3.2345), "alpha": (2.9977, 4.6817),
         "alpha_prime": (2.9785, 4.7768)}


def hcp(name: str, a: float, c: float, nb_fraction: float) -> pr.Phase:
    phase = cif("ti_alpha").phases[0]
    phase.name = name
    phase.cell.a.value = a
    phase.cell.c.value = c
    phase.atoms[0].species = "Ti"
    phase.atoms[0].occ = pr.Parameter(value=1.0 - nb_fraction, vary=False)
    phase.atoms.append(pr.Atom(
        label="Nb1", species="Nb",
        x=pr.Parameter(value=1 / 3), y=pr.Parameter(value=2 / 3),
        z=pr.Parameter(value=0.25),
        occ=pr.Parameter(value=nb_fraction, vary=False),
        biso=pr.Parameter(value=0.5, min=0.0, max=25.0)))
    phase.preferred_orientation = pr.schemas.PreferredOrientation(axis=(0, 0, 2))
    phase.scale = pr.Parameter(value=1e-3, min=0.0, transform="softplus")
    return phase


def bcc(name: str, a: float, nb_fraction: float) -> pr.Phase:
    phase = cif("ti_beta").phases[0]
    phase.name = name
    phase.cell.a.value = a
    phase.atoms[0].species = "Ti"
    phase.atoms[0].occ = pr.Parameter(value=1.0 - nb_fraction, vary=False)
    phase.atoms.append(pr.Atom(
        label="Nb1", species="Nb",
        x=pr.Parameter(value=0.0), y=pr.Parameter(value=0.0),
        z=pr.Parameter(value=0.0),
        occ=pr.Parameter(value=nb_fraction, vary=False),
        biso=pr.Parameter(value=0.5, min=0.0, max=25.0)))
    phase.preferred_orientation = pr.schemas.PreferredOrientation(axis=(1, 1, 0))
    phase.scale = pr.Parameter(value=1e-4, min=0.0, transform="softplus")
    return phase


def main() -> None:
    data = load(f"{CASE}/intensity.csv")
    tt = np.asarray(data.two_theta)
    print(f"Ti-15Nb: {len(tt)} points, {tt[0]:.2f}-{tt[-1]:.2f} deg")

    # Nb partitions to the bcc phase in Ti-Nb; the martensitic hcp phases are
    # Nb-lean.  Occupancies are *held*, not refined — site occupancy and
    # preferred orientation both rescale specific hkl (AGENT_PROTOCOL §3).
    structure = pr.Structure(phases=[
        bcc("beta", START["beta"][0], nb_fraction=0.30),
        hcp("alpha", *START["alpha"], nb_fraction=0.05),
        hcp("alpha_prime", *START["alpha_prime"], nb_fraction=0.15),
    ])

    instrument = pr.Instrument.bragg_brentano(radiation="CuKa")
    # A cold-rolled alloy film has broad peaks; the default w = 1e-3 deg^2
    # (FWHM ~ 0.03 deg) builds evaluation windows far narrower than the real
    # lines, which is the second half of the cold-start failure described above.
    instrument.profile.w.value = 2e-2
    instrument.profile.x.value = 1e-1
    instrument.background = pr.background.auto_background(data, kind="chebyshev")

    # No Le Bail stage here, and that is itself a result.  Le Bail partitions
    # observed intensity between reflections; with three phases whose lines
    # coincide to within a peak width there is nothing to partition *on*, and
    # the extraction runs away — Rwp = 2.6e5 %, every profile term on a bound.
    # AGENT_PROTOCOL §3 lists exactly this ("overlapped reflection intensities
    # (Pawley/Le Bail): the sum is determined, the split is not").  So the
    # structural model, which ties intensities to atoms, is the only handle.
    ref = pr.Refinement(structure, instrument)
    with Timer() as t_rv:
        rv, rv_passes = fit_to_fixed_point(
            ref, data, mode="rietveld", plan=lab_plan(), label="Rietveld/free-cell")
    show(rv, "Rietveld (free cell)")
    show_report(rv, top=5)

    fitted = ref.fitted_structure
    for phase in fitted.phases:
        print(f"  {phase.name:12s} a={phase.cell.a.value:.5f} "
              f"c={phase.cell.c.value:.5f}")
    free_cells = {p.name: {"a": p.cell.a.value, "c": p.cell.c.value}
                  for p in fitted.phases}
    free_fracs = {q.name: q.weight_fraction * 100
                  for q in (rv.qpa.phases if rv.qpa else [])}

    # --- second run: the same model with all three cells HELD at WPEM's
    # refined metric, so the only question left is how the intensity divides.
    # This is what puts an esd on the alpha/alpha' split.
    held = pr.Structure(phases=[
        bcc("beta", START["beta"][0], nb_fraction=0.30),
        hcp("alpha", *START["alpha"], nb_fraction=0.05),
        hcp("alpha_prime", *START["alpha_prime"], nb_fraction=0.15),
    ])
    for phase in held.phases:
        for axis in ("a", "b", "c"):
            getattr(phase.cell, axis).vary = False
    held_plan = pr.RefinementPlan(stages=[
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("zero", ["instrument.zero_shift"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.x",
                             "instrument.profile.y"]),
        pr.Stage("sample_profile", ["phases.*.lor_size", "phases.*.lor_strain"]),
        pr.Stage("biso", ["phases.*.atoms.*.biso"]),
        pr.Stage("preferred_orientation", ["phases.*.preferred_orientation.r"]),
    ])
    instrument2 = pr.Instrument.bragg_brentano(radiation="CuKa")
    instrument2.profile.w.value = 2e-2
    instrument2.profile.x.value = 1e-1
    instrument2.background = pr.background.auto_background(data, kind="chebyshev")
    ref2 = pr.Refinement(held, instrument2)
    with Timer() as t_held:
        rv_held, held_passes = fit_to_fixed_point(
            ref2, data, mode="rietveld", plan=held_plan, label="Rietveld/held-cell")
    show(rv_held, "Rietveld (cells held)")

    held_fracs, held_sigmas = {}, {}
    print(f"  {'phase':12s} {'held-cell wt%':>18s} {'free-cell':>10s} {'WPEM':>8s}")
    for q in (rv_held.qpa.phases if rv_held.qpa else []):
        sigma = (q.weight_fraction_stderr or 0.0) * 100
        held_fracs[q.name] = q.weight_fraction * 100
        held_sigmas[q.name] = sigma
        print(f"  {q.name:12s} {q.weight_fraction * 100:10.2f} ± {sigma:5.2f} "
              f"{free_fracs.get(q.name, float('nan')):10.2f} "
              f"{WPEM_REF['fractions_percent'][q.name]:8.2f}")

    rec = record(CASE, "CASES/Ti-15Nb_three phase/intensity.csv", data, rv,
                 fitted, mode="rietveld",
                 seconds=t_rv.seconds + t_held.seconds,
                 reference=WPEM_REF,
                 notes=[
                     "Cells seeded from WPEM's REFINED values, not its starting "
                     "values: a cold start from the latter (alpha a 3.0% off) "
                     "diverges to Rwp=7225% because the frozen evaluation "
                     "windows cannot reach the peaks.",
                     "No Le Bail stage: with three phases whose lines coincide "
                     "the intensity partition is indeterminate and the "
                     "extraction runs away (Rwp 2.6e5%).",
                     "Nb site occupancies HELD (beta 0.30, alpha 0.05, "
                     "alpha' 0.15); occupancy and preferred orientation both "
                     "rescale specific hkl and cannot be refined together here.",
                     "No ground truth exists for this case — WPEM's fractions "
                     "are an estimate, not a reference value.",
                     f"Free-cell Rietveld reached its fixed point in "
                     f"{rv_passes} passes; held-cell in {held_passes}.",
                 ])
    rec.wavelengths = [float(line.wavelength) for line in instrument.source.lines]
    rec.reference["wpem_start_cells"] = WPEM_START
    rec.reference["cold_start_from_wpem_cells"] = {
        "lebail_rwp_percent": 7224.8,
        "outcome": "diverged; zero_shift and every profile term on a bound",
    }
    rec.reference["free_cell_run"] = {
        "rwp_percent": rv.statistics.rwp * 100,
        "rp_percent": rv.statistics.rp * 100,
        "cells": free_cells, "weight_percent": free_fracs,
    }
    rec.reference["held_cell_run"] = {
        "rwp_percent": rv_held.statistics.rwp * 100,
        "rp_percent": rv_held.statistics.rp * 100,
        "n_free": rv_held.statistics.n_free_parameters,
        "weight_percent": held_fracs, "weight_percent_esd": held_sigmas,
    }
    rec.save()
    plot(rv, CASE, zooms=[(34, 45), (52, 60), (68, 80)])
    plot(rv_held, f"{CASE}_held", zooms=[(34, 42)])
    print(f"  saved results/{CASE}.json")


if __name__ == "__main__":
    main()
