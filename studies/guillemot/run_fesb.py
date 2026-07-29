"""FeSb_19RBM — NiAs-type Fe(1+x)Sb, Cu Kalpha lab data.

Model transcribed from the accompanying TOPAS input (FeSb_19RBM.inp):
  P6_3/mmc (194), a = 4.11384, c = 5.15722
  Fe1  2a (0,0,0)        occ 1
  Fe2  2d (1/3,2/3,3/4)  occ 0.278  <- interstitial site, refined
  Sb1  2c (1/3,2/3,1/4)  occ 1
  one *shared* Biso for all three sites (TOPAS `total_beq`);
  10-term Chebyshev background; LP_Factor(90) -> constant polarisation;
  Simple_Axial_Model(!axial, 10) -> axial divergence FIXED, not refined;
  la/lo/lh fixed emission doublet with Ka2/Ka1 = 0.34618/0.65382 = 0.5295;
  start_X 29 (everything below 29 deg 2theta is discarded — that is where the
  air/holder scatter dominates, see the raw pattern).

pxrdref has no user-level equality tie between two parameters, so the shared
Biso is emulated by a fixed-point loop: refine with only Fe1's Biso free, copy
it onto the other two sites, refit.  Three cycles is well past convergence.
"""
from __future__ import annotations

import numpy as np
from common import EX, OUT, P, atom, hex_cell, summarise

import pxrdref as pr

NAME = "FeSb_19RBM"
LO, HI = 29.0, 90.0          # start_X 29 in the .inp
AXIAL = 10.0 / 2 / 217.5     # Simple_Axial_Model(!axial, 10 mm) -> (L/2)/R
KA2 = 0.346183 / 0.653817    # the .inp's fixed la weights


def build():
    ph = pr.Phase(
        name="FeSb", space_group="P 63/m m c", cell=hex_cell(4.11384, 5.15722),
        atoms=[atom("Fe1", "Fe", 0.0, 0.0, 0.0, biso=1.1),
               atom("Fe2", "Fe", 1 / 3, 2 / 3, 0.75, biso=1.1, occ=0.278),
               atom("Sb1", "Sb", 1 / 3, 2 / 3, 0.25, biso=1.1)],
        scale=P(value=1e-3, min=0.0, transform="softplus"))
    # LP_Factor(90): TOPAS's constant-polarisation case, K = 1/(1+cos^2 90) = 1
    inst = pr.Instrument.bragg_brentano(radiation="CuKa", ka2_ratio=KA2,
                                        monochromator_two_theta=90.0)
    inst.profile.w.value = 5e-3
    inst.profile.x.value = 5e-3
    inst.geometry.axial_sl.value = AXIAL     # held fixed, as in the .inp
    inst.geometry.axial_hl.value = AXIAL
    return pr.Structure(phases=[ph]), inst


def plan():
    """The .inp's own refinement list, in McCusker order.  No axial stage and
    no emission-weight stage: the .inp holds both fixed (`!axial`, literal
    `la` values), and freeing them here drives |rho| > 0.98 against the
    specimen displacement."""
    return pr.RefinementPlan(stages=[
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        # the .inp comments out Zero_Error and refines Specimen_Displacement;
        # with the cell free the two are near-degenerate, so follow it exactly
        pr.Stage("disp", ["instrument.geometry.sample_displacement"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        pr.Stage("biso", ["phases.0.atoms.0.biso"]),   # tied: see module docstring
        pr.Stage("occ", ["phases.0.atoms.1.occ"]),
    ])


def main():
    from pxrdref.background import auto_background

    data = pr.read_pattern(EX / NAME / f"{NAME}.xy").crop(LO, HI)
    structure, inst = build()
    inst.background = auto_background(data, kind="chebyshev",
                                      wavelength=inst.source.primary_wavelength)
    print(f"{NAME}: {len(data.two_theta)} points {LO}-{HI} deg, "
          f"Chebyshev order {len(inst.background.coefficients)}")

    ref = pr.Refinement(structure, inst)
    previous = None
    for cycle in range(12):                     # shared-Biso fixed point
        result = ref.fit(data, plan=plan())
        ph = ref.fitted_structure.phases[0]
        b = ph.atoms[0].biso.value
        print(f"  cycle {cycle}: Rwp={result.statistics.rwp * 100:.4f}%  "
              f"Biso={b:.5f}  occ(Fe2)={ph.atoms[1].occ.value:.5f}")
        for a in ph.atoms[1:]:
            a.biso.value = b
        ref.structure = ref.fitted_structure
        ref.instrument = ref.fitted_instrument
        if previous is not None and abs(b - previous) < 1e-3:
            break
        previous = b

    ph = ref.fitted_structure.phases[0]
    topas = {"a": 4.113838, "c": 5.157225, "occ(Fe2)": 0.27786,
             "Biso": 1.12307, "Rwp": 0.040953}
    ours = {"a": ph.cell.a.value, "c": ph.cell.c.value,
            "occ(Fe2)": ph.atoms[1].occ.value, "Biso": ph.atoms[0].biso.value,
            "Rwp": result.statistics.rwp}
    cmp = "\n      ".join(
        f"{k:9s} {ours[k]:11.6f}   TOPAS {topas[k]:11.6f}   "
        f"{(ours[k] / topas[k] - 1) * 1e2:+7.2f}%" for k in topas)

    print(summarise(NAME, result, ref, {"vs TOPAS FeSb_19RBM.out": "\n      " + cmp}))
    for path in ("phases.0.cell.a", "phases.0.cell.c", "phases.0.atoms.1.occ",
                 "phases.0.atoms.0.biso"):
        p = result.parameter(path)
        print(f"  esd {path} = {p.value:.6f} +/- "
              f"{'n/a' if p.stderr is None else f'{p.stderr:.6f}'}")
    result.plot(path=str(OUT / f"{NAME}_fit.png"))
    from pxrdref.viz.plots import plot_for_vlm
    plot_for_vlm(result, ref.report(plan=plan()), path=str(OUT / f"{NAME}_panels.png"))
    np.savetxt(OUT / f"{NAME}_obs_calc_diff.txt",
               np.column_stack([result.two_theta, result.y_obs, result.y_calc,
                                np.asarray(result.y_obs) - np.asarray(result.y_calc)]),
               header="2theta y_obs y_calc y_diff")
    return result, ref


if __name__ == "__main__":
    main()
