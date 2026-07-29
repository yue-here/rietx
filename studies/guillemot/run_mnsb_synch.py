"""MnSb_33_BM — NiAs-type Mn(1+x)Sb, Diamond I11 synchrotron capillary data.

Everything comes from MnSb_33_BM_synchrotron.inp:

  lambda = 0.824323338 A (I11_wavelength, held), zero = 0.01713 (held)
  capillary: capdia 0.49 mm -> R = 0.245 mm, packing_density 0.15,
             muR(15 keV) = 1.27331442, Cylindrical_I_Correction applied
  P6_3/mmc (194), a = 4.130757, c = 5.765880
  Mn1  2a (0,0,0)       occ 1        beq 0.3 (held)
  Mn2  2d (1/3,2/3,3/4) occ 0.07164  beq 0.3 (held)   <- interstitial, refined
  Sb1  2c (1/3,2/3,1/4) occ 1        beq -0.48465     <- refined, and negative
  CS_L 560.9 nm; CS_G off; Stephens_hexagonal(s400, s004, s202)

This is the one pattern in the collection that exercises the corrections
pxrdref was built for: Rouse cylindrical absorption at a mu*R the .inp itself
computes, and Stephens anisotropic strain on a hexagonal Laue class.  The
data file carries its own esd column, so the weights are the measured ones.
"""
from __future__ import annotations

import numpy as np
from common import EX, OUT, P, StephensStrain, atom, hex_cell, summarise

import pxrdref as pr
from pxrdref.crystallography import stephens

NAME = "MnSb_33_BM"
FILE = "MnSb_33_BM.xye"
LAMBDA = 0.824323338
MU_R = 1.27331442        # the .inp's own muR_15keV
CAP_R = 0.49 / 2         # capdia / 2, mm
PACKING = 0.15


def build(*, stephens_strain: bool = True, mu_r: float | None = MU_R,
          shape: str = "tchz_pv"):
    cell = hex_cell(4.130757, 5.765880)
    ph = pr.Phase(
        name="Mn1+xSb", space_group="P 63/m m c", cell=cell,
        atoms=[atom("Mn1", "Mn", 0.0, 0.0, 0.0, biso=0.3),
               atom("Mn2", "Mn", 1 / 3, 2 / 3, 0.75, biso=0.3, occ=0.07164),
               atom("Sb1", "Sb", 1 / 3, 2 / 3, 0.25, biso=0.3)],
        scale=P(value=1e-2, min=0.0, transform="softplus"))
    if stephens_strain:
        # seeded on the isotropic ray of the allowed subspace; a block at
        # S == 0 has unbounded d(sqrt)/dS, which is what strain_seed exists for
        ph.microstrain = StephensStrain.isotropic(300.0, cell, vary=False)
    inst = pr.Instrument.debye_scherrer(LAMBDA, polarization=0.99,
                                        capillary_radius_mm=CAP_R,
                                        packing_fraction=PACKING, mu_r=mu_r)
    inst.profile.shape = shape
    inst.profile.w.value = 2e-4
    inst.profile.x.value = 1e-3
    inst.geometry.axial_sl.value = 0.003
    inst.geometry.axial_hl.value = 0.003
    return pr.Structure(phases=[ph]), inst


def plan(*, stephens_strain: bool = True):
    """The .inp's list, with two forced substitutions.

    (1) TOPAS holds a fully calibrated I11 instrument function and refines only
    sample terms (CS_L + Stephens).  Without that calibration file the split is
    unidentifiable here, so the *instrument* U V W X carry the resolution and
    the phase's lor_size is left at zero — freeing both gives rho = -1.000
    between them (measured).
    (2) instrument.profile.y is held at zero whenever a Stephens block refines:
    y is a tan(theta) Lorentzian term and the isotropic direction of the
    Stephens subspace is *identically* that column, so the two are degenerate
    by construction.  pxrdref locks the phase's own lor_strain for exactly this
    reason; the instrument's y is outside its reach, so it is held here.
    """
    profile = ["instrument.profile.u", "instrument.profile.v",
               "instrument.profile.x"]
    if not stephens_strain:
        profile.append("instrument.profile.y")
    stages = [
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        # a capillary has no displacement aberration in this package's model;
        # zero_shift stands in for the .inp's Capillary_Offset_Cos_2Th_mm
        pr.Stage("zero", ["instrument.zero_shift"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", profile),
        pr.Stage("axial", ["instrument.geometry.axial_sl",
                           "instrument.geometry.axial_hl"]),
    ]
    if stephens_strain:
        stages.append(pr.Stage("stephens", ["phases.*.microstrain.dof.*"],
                               strain_seed=300.0))
    stages += [
        # TOPAS holds both Mn beq at 0.3 and refines only Sb; mirror that
        pr.Stage("biso", ["phases.0.atoms.2.biso"]),
        pr.Stage("occ", ["phases.0.atoms.1.occ"]),
    ]
    return pr.RefinementPlan(stages=stages)


def run(data, *, solver="trf", stephens_strain=True, mu_r=MU_R, shape="tchz_pv",
        label=""):
    from pxrdref.background import auto_background
    s, i = build(stephens_strain=stephens_strain, mu_r=mu_r, shape=shape)
    i.background = auto_background(data, kind="chebyshev", wavelength=LAMBDA)
    ref = pr.Refinement(s, i, solver=solver)
    res = ref.fit(data, plan=plan(stephens_strain=stephens_strain))
    if label:
        print(f"  {label:34s} Rwp={res.statistics.rwp * 100:7.4f}%  "
              f"GoF={res.statistics.gof:6.2f}  "
              f"a={ref.fitted_structure.phases[0].cell.a.value:.6f}  "
              f"Biso(Sb)={ref.fitted_structure.phases[0].atoms[2].biso.value:+.4f}")
    return res, ref


def main():
    data = pr.read_pattern(EX / NAME / FILE)
    print(f"{NAME}: {len(data.two_theta)} points "
          f"{data.two_theta[0]:.3f}-{data.two_theta[-1]:.3f} deg, "
          f"file esds present: {data.sigma is not None}")

    s0, i0 = build()
    print(f"  Stephens DOFs derived for P6_3/mmc: "
          f"{sum(1 for v in s0.phases[0].microstrain.values() if abs(v) > 1e-9)} "
          f"non-zero of 15 S_HKL on the isotropic ray")
    print(f"  muR: .inp computes {MU_R:.5f}; pxrdref's own estimate from "
          f"composition+geometry = {pr.estimate_mu_r(*build(mu_r=None))}")

    result, ref = run(data)
    print(summarise(NAME, result, ref))

    ph = ref.fitted_structure.phases[0]
    topas = {"a": 4.130757, "c": 5.765880, "occ(Mn2)": 0.07164,
             "Biso(Sb)": -0.48465, "Rwp": 0.0845233}
    ours = {"a": ph.cell.a.value, "c": ph.cell.c.value,
            "occ(Mn2)": ph.atoms[1].occ.value, "Biso(Sb)": ph.atoms[2].biso.value,
            "Rwp": result.statistics.rwp}
    print("  vs TOPAS MnSb_33_BM_synchrotron.inp:")
    for k in topas:
        print(f"      {k:10s} {ours[k]:11.6f}   TOPAS {topas[k]:11.6f}")
    for path in ("phases.0.cell.a", "phases.0.cell.c", "phases.0.atoms.1.occ",
                 "phases.0.atoms.2.biso"):
        p = result.parameter(path)
        print(f"  esd {path} = {p.value:.6f} +/- "
              f"{'n/a' if p.stderr is None else f'{p.stderr:.6f}'}")

    # Stephens block, reported as physical widths rather than raw coefficients:
    # pxrdref's S_HKL multiply the literal monomials and are in 1e-12 A^-4,
    # while TOPAS folds symmetry multiplicities in, so the numbers are not
    # comparable term by term — the FWHM per reflection is.
    mstr = ph.microstrain
    if mstr is not None:
        print("  Stephens S_HKL (1e-12 A^-4, literal-monomial convention):")
        print("     " + "  ".join(f"{n}={v:.1f}" for n, v in
                                  zip(stephens.S_NAMES, mstr.values()) if abs(v) > 1e-6))
        a, c = ph.cell.a.value, ph.cell.c.value
        hkls = np.array([(1, 0, 0), (0, 0, 2), (1, 0, 1), (1, 1, 0), (1, 0, 3),
                         (2, 0, 0), (0, 0, 4)])
        h, k, ll = hkls[:, 0], hkls[:, 1], hkls[:, 2]
        d = 1.0 / np.sqrt(4 * (h**2 + h * k + k**2) / (3 * a**2) + ll**2 / c**2)
        w = stephens.strain_width_deg(stephens.monomial_matrix(hkls),
                                      np.asarray(mstr.values()), d)
        print("     Lorentzian strain FWHM, the tan(theta) coefficient in deg:")
        for hkl, dd, ww in zip(hkls.tolist(), d, np.ravel(w)):
            print(f"       {tuple(hkl)}  d={dd:.5f} A   Lambda={ww:.5f} deg")

    result.plot(path=str(OUT / f"{NAME}_fit.png"))
    from pxrdref.viz.plots import plot_for_vlm
    plot_for_vlm(result, ref.report(plan=plan()), path=str(OUT / f"{NAME}_panels.png"))
    np.savetxt(OUT / f"{NAME}_obs_calc_diff.txt",
               np.column_stack([result.two_theta, result.y_obs, result.y_calc,
                                np.asarray(result.y_obs) - np.asarray(result.y_calc)]),
               header="2theta y_obs y_calc y_diff")

    # --- what each correction actually bought -------------------------------
    print("\n--- controls (Rwp is NOT the right judge of either of these) ---")
    run(data, stephens_strain=False, label="no Stephens strain")
    run(data, mu_r=0.0, label="no capillary absorption (muR=0)")
    run(data, solver="lm", label="solver=lm (strain cone as inequality)")
    run(data, shape="voigt", label="true Voigt peak shape")
    return result, ref


if __name__ == "__main__":
    main()
