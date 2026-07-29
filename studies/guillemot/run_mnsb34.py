"""MnSb_34_impure — Cu Kalpha lab pattern, no .inp of its own.

What the folder gives is the name.  Everything else is inferred:

* The 2theta grid (5.01436 ... 89.99116, 5086 points) is bit-identical to
  FeSb_19RBM.xy and HL2-1_2.xy, so it is the same lab diffractometer; take the
  FeSb .inp's instrument settings (LP_Factor(90), Simple_Axial_Model(!,10),
  fixed la doublet).
* The main phase indexes as NiAs-type MnSb, P6_3/mmc: d(110) = 2.0704 -> a =
  4.1408, d(002) = 2.8931 -> c = 5.7862, which then predicts (101) 3.048 and
  (102) 2.2517 against observed 3.0495 and 2.2518.  Atom positions and the
  partially-occupied 2d interstitial come from the sibling synchrotron .inp.
* "impure": the leftover lines are at d = 3.1139 (3.4 % of the strongest) and
  2.1537 (1.2 %).  Rhombohedral Sb (A7, R-3m, a = 4.3084, c = 11.2740) puts
  its two strongest reflections at exactly 3.111 (012) and 2.154 (110).  The
  sibling synchrotron .inp carries a commented-out `phase_name Sb` block in
  space group 166, which is the same identification.
"""
from __future__ import annotations

import numpy as np
from common import EX, OUT, P, StephensStrain, atom, hex_cell, summarise

import pxrdref as pr

NAME = "MnSb_34_impure"
FILE = "MnSb_34.xy"
LO, HI = 15.0, 90.0          # below ~15 deg the holder/air scatter dominates
AXIAL = 10.0 / 2 / 217.5
KA2 = 0.346183 / 0.653817


def build(*, with_sb: bool = True, stephens: bool = True):
    mnsb = pr.Phase(
        name="MnSb", space_group="P 63/m m c", cell=hex_cell(4.1408, 5.7862),
        atoms=[atom("Mn1", "Mn", 0.0, 0.0, 0.0, biso=0.5),
               atom("Mn2", "Mn", 1 / 3, 2 / 3, 0.75, biso=0.5, occ=0.07),
               atom("Sb1", "Sb", 1 / 3, 2 / 3, 0.25, biso=0.5)],
        scale=P(value=1e-3, min=0.0, transform="softplus"))
    if stephens:
        # the host lines are anisotropically broadened: 00l stays sharp while
        # hk0 does not.  Seeded on the isotropic ray of the allowed subspace.
        mnsb.microstrain = StephensStrain.isotropic(1000.0, mnsb.cell, vary=False)
    phases = [mnsb]
    if with_sb:
        phases.append(pr.Phase(
            name="Sb", space_group="R -3 m :H", cell=hex_cell(4.3084, 11.2740),
            atoms=[atom("Sb2", "Sb", 0.0, 0.0, 0.23349, biso=0.5)],
            scale=P(value=1e-5, min=0.0, transform="softplus")))
    inst = pr.Instrument.bragg_brentano(radiation="CuKa", ka2_ratio=KA2,
                                        monochromator_two_theta=90.0)
    inst.profile.w.value = 5e-3
    inst.profile.x.value = 5e-3
    inst.geometry.axial_sl.value = AXIAL
    inst.geometry.axial_hl.value = AXIAL
    return pr.Structure(phases=phases), inst


def plan(*, stephens: bool = True):
    # instrument.profile.y (a tan(theta) Lorentzian) is held at zero whenever a
    # Stephens block refines — the isotropic direction of the Stephens subspace
    # is identically that column.
    profile = ["instrument.profile.u", "instrument.profile.v",
               "instrument.profile.x"]
    if not stephens:
        profile.append("instrument.profile.y")
    stages = [
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("disp", ["instrument.geometry.sample_displacement"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", profile),
    ]
    if stephens:
        stages.append(pr.Stage("stephens", ["phases.0.microstrain.dof.*"],
                               strain_seed=1000.0))
    stages += [
        # only the two fully-occupied MnSb sites: a free Biso on the
        # partially-occupied 2d interstitial is degenerate with its occupancy
        # (measured: it runs to the 10 A^2 bound and drags occ to 0.18), and the
        # 1.9 wt% Sb phase cannot support one either.  The synchrotron .inp
        # holds every Mn beq for the same reason.
        pr.Stage("biso", ["phases.0.atoms.0.biso", "phases.0.atoms.2.biso"]),
        pr.Stage("occ", ["phases.0.atoms.1.occ"]),
        # the Sb z is the only free coordinate in either structure
        pr.Stage("sb_z", ["phases.1.atoms.0.dof.*"]),
    ]
    return pr.RefinementPlan(stages=stages)


def run(data, *, with_sb=True, stephens=True, solver="lm", label=""):
    from pxrdref.background import auto_background
    s, i = build(with_sb=with_sb, stephens=stephens)
    i.background = auto_background(data, kind="chebyshev",
                                   wavelength=i.source.primary_wavelength)
    pl = plan(stephens=stephens)
    if not with_sb:
        pl.stages = [st for st in pl.stages if st.name != "sb_z"]
    ref = pr.Refinement(s, i, solver=solver)
    res = ref.fit(data, plan=pl)
    if label:
        print(f"  {label:28s} Rwp={res.statistics.rwp * 100:7.4f}%  "
              f"GoF={res.statistics.gof:6.2f}")
    return res, ref


def main():
    data = pr.read_pattern(EX / NAME / FILE).crop(LO, HI)
    print(f"{NAME}: {len(data.two_theta)} points {LO}-{HI} deg")

    result, ref = run(data)
    print(summarise(NAME, result, ref))
    for path in ("phases.0.cell.a", "phases.0.cell.c", "phases.1.cell.a",
                 "phases.1.cell.c", "phases.0.atoms.1.occ"):
        p = result.parameter(path)
        if p is not None:
            print(f"  esd {path} = {p.value:.6f} +/- "
                  f"{'n/a' if p.stderr is None else f'{p.stderr:.6f}'}")
    if result.qpa is not None:
        for q in result.qpa.phases:
            print(f"  QPA {q.name}: W = {q.weight_fraction * 100:.2f}"
                  f"{'' if q.weight_fraction_stderr is None else f' +/- {q.weight_fraction_stderr * 100:.2f}'} wt%"
                  f"   (Z*M = {q.cell_mass:.2f} g/mol, V = {q.cell_volume:.3f} A^3)")

    result.plot(path=str(OUT / f"{NAME}_fit.png"))
    from pxrdref.viz.plots import plot_for_vlm
    plot_for_vlm(result, ref.report(plan=plan()), path=str(OUT / f"{NAME}_panels.png"))
    stephens_report(ref)
    np.savetxt(OUT / f"{NAME}_obs_calc_diff.txt",
               np.column_stack([result.two_theta, result.y_obs, result.y_calc,
                                np.asarray(result.y_obs) - np.asarray(result.y_calc)]),
               header="2theta y_obs y_calc y_diff")

    print("\n--- controls ---")
    run(data, with_sb=False, label="MnSb alone (no Sb phase)")
    run(data, with_sb=True, label="MnSb + Sb")
    run(data, stephens=False, solver="trf", label="isotropic widths only")
    run(data, solver="trf", label="Stephens under TRF (guard only)")
    return result, ref




def stephens_report(ref):
    """The anisotropic block, as physical widths rather than raw coefficients."""
    from pxrdref.crystallography import stephens
    ph = ref.fitted_structure.phases[0]
    if ph.microstrain is None:
        return
    a, c = ph.cell.a.value, ph.cell.c.value
    hkls = np.array([(1, 0, 0), (0, 0, 2), (1, 0, 1), (1, 0, 2), (1, 1, 0),
                     (1, 0, 3), (2, 0, 0), (0, 0, 4)])
    h, k, ll = hkls[:, 0], hkls[:, 1], hkls[:, 2]
    d = 1.0 / np.sqrt(4 * (h**2 + h * k + k**2) / (3 * a**2) + ll**2 / c**2)
    w = np.ravel(stephens.strain_width_deg(stephens.monomial_matrix(hkls),
                                           np.asarray(ph.microstrain.values()), d))
    print("  Stephens Lorentzian strain FWHM (tan-theta coefficient, deg):")
    for hkl, dd, ww in zip(hkls.tolist(), d, w):
        print(f"     {tuple(hkl)}  d={dd:.5f} A   Lambda={ww:.5f} deg")

if __name__ == "__main__":
    main()
