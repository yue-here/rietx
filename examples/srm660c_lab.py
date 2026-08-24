"""v0.2 walkthrough: laboratory Bragg-Brentano refinement of NIST SRM 660c.

Exercises everything the v0.2 milestone added, on real CuKα lab data:
per-line Kα1/Kα2 dispersion, FCJ axial asymmetry, specimen displacement,
the analytic Jacobian, Bérar-Lelann esds, automatic background selection,
all three FitReport layers, the VLM montage and the interactive HTML viewer.

Data: NIST SRM 660c certification profiles (tests/data/nist_srm660c_100a.cif,
`…_meas` block).  Protocol follows NIST's own certification analyses: the
goniometer is angle-calibrated, so the zero point is held at 0 and the
specimen displacement refines instead.
"""

from pathlib import Path

import rietx as rx
from rietx.background import auto_background, diagnose

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
OUT = Path(__file__).resolve().parent

#: La and B Uiso from the CIF's cell block, as Biso = 8π²·Uiso
_ATOMS = [("La", "La", 0.0, 0.0, 0.0, 0.355), ("B", "B", 0.198, 0.5, 0.5, 0.276)]


def build_model():
    structure = rx.Structure(phases=[rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.1568),
        atoms=[rx.Atom(label=lab, species=sp,
                       x=rx.Parameter(value=x), y=rx.Parameter(value=y),
                       z=rx.Parameter(value=z),
                       biso=rx.Parameter(value=b, min=0.0, max=25.0))
               for lab, sp, x, y, z, b in _ATOMS],
        scale=rx.Parameter(value=1e-4, min=0.0, transform="softplus"))])

    # graphite (002) post-monochromator at 2θ_m ≈ 26.6° sets the polarization
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa",
                                              monochromator_two_theta=26.6)
    instrument.profile.w.value = 2e-3
    instrument.profile.x.value = 5e-3
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.025
    return structure, instrument


def nist_protocol_plan() -> rx.RefinementPlan:
    """lab_bragg_brentano minus the zero point (calibrated goniometer)."""
    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("disp", ["instrument.geometry.sample_displacement"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile_w", ["instrument.profile.w"]),
        rx.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        rx.Stage("lines_axial", ["instrument.source.lines.*.weight",
                                 "instrument.geometry.axial_sl",
                                 "instrument.geometry.axial_hl"]),
        rx.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])


def main() -> None:
    data = rx.read_pdcif(DATA / "nist_srm660c_100a.cif", block="_meas")
    print(f"pattern: {len(data.two_theta)} points, "
          f"{data.two_theta[0]:.2f}-{data.two_theta[-1]:.2f} deg, "
          f"sigma from file: {data.sigma is not None}")

    # --- what does the raw pattern look like, before any model?
    diag = diagnose(data, wavelength=1.5405929)
    print(f"\ndiagnostics: {diag.n_peaks} peaks ({diag.peak_density_per_deg:.2f}/deg), "
          f"S/B {diag.signal_to_background:.1f}, hump {diag.amorphous_hump_score:.3f}, "
          f"air-scatter gain {diag.air_scatter_gain:.3f}")
    for flag in diag.contamination:
        print(f"  contamination: {flag.kind} at {flag.two_theta:.3f} deg "
              f"({flag.intensity_ratio:.1%} of its {flag.parent_two_theta:.3f} parent)")

    structure, instrument = build_model()
    instrument.background = auto_background(data, kind="chebyshev")
    print(f"background: auto-selected Chebyshev order "
          f"{len(instrument.background.coefficients)}")

    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, plan=nist_protocol_plan())

    phase = ref.fitted_structure.phases[0]
    a = phase.cell.a.value
    a_err = result.parameter("phases.0.cell.a").stderr
    stats = result.statistics
    print(f"\nRietveld: status={result.status}  Rwp={stats.rwp:.4f}  "
          f"GoF={stats.gof:.2f}  DW={stats.durbin_watson:.2f}")
    print(f"          a = {a:.6f} +/- {a_err:.6f} A   "
          f"(NIST recomputed 4.156780 for this dataset; "
          f"{(a / 4.156780 - 1) * 1e6:+.0f} ppm)")
    print(f"          esds carry the Berar-Lelann factor "
          f"{stats.esd_inflation:.2f} (raw esd {a_err / stats.esd_inflation:.2e})")
    geom = ref.fitted_instrument.geometry
    print(f"          displacement {geom.sample_displacement.value:+.4f} mm "
          f"(CIF records -0.07877), Ka2/Ka1 "
          f"{ref.fitted_instrument.source.lines[1].weight.value:.3f} "
          f"(Holzer integrated 0.52)")
    for d in result.diagnostics:
        print(f"          [{d.level}] {d.code}: {d.message}")

    # --- FitReport, all three layers (needs the compiled model → ref.report())
    report = ref.report(plan=nist_protocol_plan())
    print(f"\nFitReport: {report.summary}")
    if report.abstained_reason:
        print(f"  Layer 1 abstained: {report.abstained_reason}")
    else:
        gated = [r for r in report.attribution if r.gates_passed]
        print(f"  Layer 1: {len(gated)}/{len(report.attribution)} regions readable")
        for region in gated[:3]:
            terms = ", ".join(f"{c.kind} {c.value:+.4g}"
                              for c in region.coefficients if c.significant)
            print(f"    {region.two_theta_lo:7.3f}-{region.two_theta_hi:7.3f} deg: "
                  f"{terms or 'nothing significant'}")
        for trend in report.trends:
            if trend.templates:
                best = max(trend.templates, key=lambda t: t.r2)
                verdict = ("separable" if trend.separable else
                           f"NOT separable (ratio {trend.separability_ratio:.2f})")
                print(f"    {trend.observable} trend -> {best.name} "
                      f"[{trend.misfit_share:.0%} of chi2], {verdict}")
    print("  Layer 2 suggested actions:")
    for action in report.suggested_actions[:5]:
        mark = " " if action.active else "x"
        print(f"    [{mark}] {action.confidence:.2f} {action.kind}"
              f"{'  vetoed: ' + action.vetoed_by if action.vetoed_by else ''}")
    if not report.suggested_actions:
        print("    (none — the remaining misfit is not attributable to a "
              "refinable parameter)")

    print("\nHistory (every stage is a restorable checkpoint):")
    print(ref.history.summary())

    # --- outputs
    try:
        from rietx.viz.plots import plot_for_vlm
        result.plot(path=str(OUT / "srm660c_fit.png"),
                    wavelength=ref.fitted_instrument.source.primary_wavelength)
        plot_for_vlm(result, report, path=str(OUT / "srm660c_vlm.png"))
        print("\nwrote examples/srm660c_fit.png and srm660c_vlm.png")
        from rietx.viz import write_html
        write_html(result, str(OUT / "srm660c_fit.html"))
        print("wrote examples/srm660c_fit.html (interactive, self-contained)")
    except ImportError:
        print("\n(install '[viz]' for plots and the HTML viewer)")


if __name__ == "__main__":
    main()
