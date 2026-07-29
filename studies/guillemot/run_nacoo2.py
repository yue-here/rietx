"""KD1-2_5_NaCoO2 — P2-type Na_x CoO2, Cu Kalpha lab data.

The folder ships no .inp, but `examples/NaCoO2/example_refinement_NaCoO2.inp`
is unmistakably its partner: it refines a P6_3/mmc Na_0.74CoO2 and writes
`Out_CIF_STR("KD1-2_riet_01.cif")` — the KD1-2 stem of this pattern.  Its
`xdd NaCoO2_CuKa_XRD.xy` names a file that is not in the repo; this is the only
NaCoO2 CuKa pattern there is.  Model taken from that .inp:

  P6_3/mmc (194), a = 2.832224, c = 10.916868
  Co1  2a (0,0,1/2)          occ 1.00  beq 0.27
  Na1  2b (0,0,1/4)          occ 0.23  beq 1.30
  Na2  2d (2/3,1/3,1/4)      occ 0.51  beq 1.30
  O1   4f (1/3,2/3,z=0.0913) occ 1.00  beq 0.54     <- z refined
  March-Dollase preferred orientation about (0 0 1), r seeded 0.5
  6-term Chebyshev background; LP_Factor(!,90); Simple_Axial_Model(!axial,10);
  Specimen_Displacement(height, 0) refined; ionic form factors Co3+/Na1+/O2-.

The pattern is one enormous (002) plus about a dozen weak reflections — a
strongly textured layered platelet.  Two of the .inp's refinable parameters do
not survive that: the Na site occupancies and the four Biso.  Both are measured
below rather than asserted.
"""
from __future__ import annotations

import numpy as np
from common import EX, OUT, P, PreferredOrientation, atom, hex_cell, summarise

import pxrdref as pr
from pxrdref.schemas.instrument import BackgroundChebyshev

NAME = "KD1-2_5_NaCoO2"
FILE = "KD1-2_5-90_30min.xy"
AXIAL = 10.0 / 2 / 217.5
KA2 = 0.346183 / 0.653817


def build():
    ph = pr.Phase(
        name="Na0.74CoO2", space_group="P 63/m m c",
        cell=hex_cell(2.832224, 10.916868),
        atoms=[atom("Co1", "Co3+", 0.0, 0.0, 0.5, biso=0.27),
               atom("Na1", "Na1+", 0.0, 0.0, 0.25, biso=1.3, occ=0.23),
               atom("Na2", "Na1+", 2 / 3, 1 / 3, 0.25, biso=1.3, occ=0.51),
               atom("O1", "O2-", 1 / 3, 2 / 3, 0.0913, biso=0.54)],
        scale=P(value=1e-3, min=0.0, transform="softplus"),
        preferred_orientation=PreferredOrientation(
            axis=(0, 0, 1), r=P(value=0.5, min=0.0, transform="softplus")))
    inst = pr.Instrument.bragg_brentano(radiation="CuKa", ka2_ratio=KA2,
                                        monochromator_two_theta=90.0)
    inst.profile.w.value = 5e-3
    inst.profile.x.value = 5e-3
    inst.geometry.axial_sl.value = AXIAL
    inst.geometry.axial_hl.value = AXIAL
    return pr.Structure(phases=[ph]), inst


def plan(*, free_na_occ: bool = False, free_biso: bool = False):
    stages = [
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("disp", ["instrument.geometry.sample_displacement"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        # NB no phase lor_size/lor_strain/gauss_* stage.  With no line-profile
        # standard for this diffractometer the instrument<->sample width split
        # is unidentifiable: freeing both gives rho = 1.000 between
        # instrument.profile.w and phases.0.gauss_size (measured).  The TOPAS
        # .inp makes the mirror-image choice — CS_L/CS_G/Strain_L/Strain_G with
        # no Caglioti terms at all — which is the same single set of widths.
        # texture before the structural parameters: r rescales intensity in a
        # hkl-dependent way that Biso/occ would otherwise absorb
        pr.Stage("texture", ["phases.*.preferred_orientation.r"]),
        pr.Stage("oxygen_z", ["phases.*.atoms.3.dof.*"]),
    ]
    if free_biso:
        stages.append(pr.Stage("biso", ["phases.*.atoms.*.biso"]))
    if free_na_occ:
        stages.append(pr.Stage("na_occ", ["phases.0.atoms.1.occ",
                                          "phases.0.atoms.2.occ"]))
    return pr.RefinementPlan(stages=stages)


def fit(data, *, terms=None, biso0=None, **kw):
    from pxrdref.background import auto_background
    s, i = build()
    if biso0 is not None:
        for a in s.phases[0].atoms:
            a.biso.value = biso0
    i.background = (auto_background(data, kind="chebyshev",
                                    wavelength=i.source.primary_wavelength)
                    if terms is None else BackgroundChebyshev.with_terms(terms))
    ref = pr.Refinement(s, i)
    return ref.fit(data, plan=plan(**kw)), ref


def main():
    data = pr.read_pattern(EX / NAME / FILE)
    result, ref = fit(data)
    print(f"{NAME}: {len(data.two_theta)} points "
          f"{data.two_theta[0]:.2f}-{data.two_theta[-1]:.2f} deg, "
          f"auto Chebyshev order {len(ref.instrument.background.coefficients)}")
    print(summarise(NAME, result, ref))
    for path in ("phases.0.cell.a", "phases.0.cell.c",
                 "phases.0.preferred_orientation.r", "phases.0.atoms.3.dof.0"):
        p = result.parameter(path)
        if p is not None:
            print(f"  esd {path} = {p.value:.6f} +/- "
                  f"{'n/a' if p.stderr is None else f'{p.stderr:.6f}'}")
    print(f"  O1 z = {ref.fitted_structure.phases[0].atoms[3].z.value:.5f} "
          f"(.inp start 0.09130)")

    result.plot(path=str(OUT / f"{NAME}_fit.png"))
    from pxrdref.viz.plots import plot_for_vlm
    plot_for_vlm(result, ref.report(plan=plan()), path=str(OUT / f"{NAME}_panels.png"))
    np.savetxt(OUT / f"{NAME}_obs_calc_diff.txt",
               np.column_stack([result.two_theta, result.y_obs, result.y_calc,
                                np.asarray(result.y_obs) - np.asarray(result.y_calc)]),
               header="2theta y_obs y_calc y_diff")

    # --- check 1: are the .inp's refinable Na occupancies supported? ---------
    print("\n--- check 1: free the two Na site occupancies (the .inp declares them) ---")
    res2, ref2 = fit(data, free_na_occ=True)
    ph2 = ref2.fitted_structure.phases[0]
    print(f"  Rwp {result.statistics.rwp * 100:.3f}% -> {res2.statistics.rwp * 100:.3f}%")
    for k in (1, 2):
        p = res2.parameter(f"phases.0.atoms.{k}.occ")
        print(f"  occ({ph2.atoms[k].label}) = {p.value:.4f} +/- "
              f"{'n/a' if p.stderr is None else f'{p.stderr:.4f}'}")
    print(f"  total Na = {ph2.atoms[1].occ.value + ph2.atoms[2].occ.value:.4f} "
          f"(.inp holds 0.7400)")

    # --- check 2: are the four Biso determinable? ---------------------------
    print("\n--- check 2: free all four Biso from four different starts ---")
    for b0 in (0.0, 0.27, 1.0, 3.0):
        res, r = fit(data, biso0=b0, free_biso=True)
        ph = r.fitted_structure.phases[0]
        print(f"  start {b0:4.2f} -> Rwp {res.statistics.rwp * 100:.4f}%  "
              f"Biso {[round(a.biso.value, 3) for a in ph.atoms]}  "
              f"r={ph.preferred_orientation.r.value:.4f}")

    # --- check 3: background order (auto vs the .inp's 6 terms) -------------
    print("\n--- check 3: background order ---")
    for terms in (6, 10, None):
        res, r = fit(data, terms=terms)
        n = len(r.instrument.background.coefficients)
        ph = r.fitted_structure.phases[0]
        print(f"  {n:2d} Chebyshev terms -> Rwp {res.statistics.rwp * 100:.4f}%  "
              f"a={ph.cell.a.value:.5f} c={ph.cell.c.value:.5f} "
              f"r={ph.preferred_orientation.r.value:.4f}")
    return result, ref


if __name__ == "__main__":
    main()
