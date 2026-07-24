"""v0.2 acceptance: NIST SRM 660c LaB6 certification data (CuKα lab data).

Real measured data from the NIST divergent-beam diffractometer (DBD): CuKα
doublet, graphite post-monochromator, R = 217.5 mm, 20.3-150.9° 2θ in 24
stitched scan regions (Cline et al., 2020, Powder Diffr. 35, certification
paper; data block ``…_100a_meas`` of tests/data/nist_srm660c_100a.cif).

Protocol: the DBD is angle-calibrated, so — exactly as in the NIST
certification analyses — the zero error is *held at 0* and the specimen
displacement refines instead (their FPA fits refine displacement and
attenuation, never a zero offset).  LaB6 is effectively opaque to CuKα, so
transparency is also held at 0.

Reference values (see tests/data/README.md):
* the CIF's own recomputed cell for this data block, a = 4.156780 Å at
  20.85 °C (the certificate value 4.156826(8) Å applies at 22.5 °C);
* the CIF's recorded specimen displacement, −0.07877 mm;
* Hölzer et al. (1997): integrated CuKα2/Kα1 intensity ratio ≈ 0.52.

Measured v0.2 result (recorded 2026-07-22, also in docs/milestones/v0.2.md):
a = 4.156895(25) Å (Δ = +1.15e-4 = +28 ppm; the esd is Bérar-Lelann-inflated,
raw χ²·(JᵀJ)⁻¹ esd 7.4e-6 × BL 3.38 — WP-0407), Rwp = 8.7 %, GoF = 1.87,
displacement −0.0801 mm (1.3 µm from NIST's), Kα2/Kα1 = 0.513.  The ±2e-4
cell band below is *interim*: the remaining bias is the unmodelled
equatorial (flat-specimen) divergence, tube tails and monochromator
passband — fundamental-parameters territory, fenced for v2.  Certificate-
level ±8e-6 accuracy is explicitly not claimed by this test.
"""

from pathlib import Path

import pytest

import pxrdref as pr

DATA = Path(__file__).parent / "data"
A_REFERENCE = 4.156780       # CIF block cell at 20.85 °C
DISP_REFERENCE = -0.07877    # mm, from the CIF spec block

pytestmark = pytest.mark.slow


def build_srm_inputs():
    """(data, structure, instrument) for the NIST protocol — plain function so
    other suites (test_backend_jax.py) can rebuild the identical state."""
    path = DATA / "nist_srm660c_100a.cif"
    if not path.exists():
        pytest.skip("SRM 660c dataset not present")
    data = pr.read_pdcif(path, block="_meas")

    structure = pr.Structure(phases=[pr.Phase(
        name="LaB6", space_group="P m -3 m", cell=pr.Cell.cubic(4.1568),
        atoms=[
            # Uiso from the CIF cell block: La 0.0045, B 0.0035 Å² (B = 8π²U)
            pr.Atom(label="La", species="La", x=pr.Parameter(value=0.0),
                    y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                    biso=pr.Parameter(value=0.355, min=0.0, max=25.0)),
            pr.Atom(label="B", species="B", x=pr.Parameter(value=0.198),
                    y=pr.Parameter(value=0.5), z=pr.Parameter(value=0.5),
                    biso=pr.Parameter(value=0.276, min=0.0, max=25.0)),
        ],
        scale=pr.Parameter(value=1e-4, min=0.0, transform="softplus"),
    )])

    instrument = pr.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.profile.w.value = 2e-3
    instrument.profile.x.value = 5e-3
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.025
    from pxrdref.schemas.instrument import BackgroundChebyshev
    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, structure, instrument


@pytest.fixture(scope="module")
def srm_inputs():
    return build_srm_inputs()


def _nist_calibrated_plan() -> pr.RefinementPlan:
    """lab_bragg_brentano minus the zero error (calibrated goniometer)."""
    return pr.RefinementPlan(stages=[
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("disp", ["instrument.geometry.sample_displacement"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        pr.Stage("lines_axial", ["instrument.source.lines.*.weight",
                                 "instrument.geometry.axial_sl",
                                 "instrument.geometry.axial_hl"]),
        pr.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])


def test_srm660c_lab6_rietveld(srm_inputs):
    data, structure, instrument = srm_inputs
    ref = pr.Refinement(structure, instrument)
    result = ref.fit(data, plan=_nist_calibrated_plan())

    assert result.status == "converged"
    assert result.statistics.rwp < 0.10
    assert result.statistics.gof < 2.5

    a = ref.fitted_structure.phases[0].cell.a.value
    a_err = result.parameter("phases.0.cell.a").stderr
    # the reported esd carries the Bérar-Lelann serial-correlation inflation
    # (BL ≈ 3.38 here, so ~25e-6 vs the raw χ²·(JᵀJ)⁻¹ ~7.4e-6) — WP-0407 fixed
    # the placement bug that used to cancel BL out of the reported physical esd
    assert a_err is not None and 1.5e-5 < a_err < 5e-5
    assert result.statistics.esd_inflation is not None
    assert 1.5 < result.statistics.esd_inflation < 6.0
    # interim accuracy band — see module docstring for the honest breakdown
    assert abs(a - A_REFERENCE) < 2e-4

    ins = ref.fitted_instrument
    # zero stayed pinned; displacement lands on NIST's value to ~10 µm
    assert ins.zero_shift.value == 0.0
    assert abs(ins.geometry.sample_displacement.value - DISP_REFERENCE) < 0.01
    # refined Kα2/Kα1 close to the Hölzer integrated ratio
    assert 0.45 < ins.source.lines[1].weight.value < 0.56
    # axial ratios in the physically plausible window for the DBD
    assert 0.005 < ins.geometry.axial_sl.value < 0.1
    assert 0.005 < ins.geometry.axial_hl.value < 0.1

    # FitReport must digest stitched-region lab data
    report = pr.build_report(result)
    assert report.summary
    assert report.n_regions_total > 10

    # Layers 1-2 on real data: the residual systematics here are unmodelled
    # FPA-territory aberrations, so the honest output is low-confidence,
    # non-separable trends — never a confident wrong singleton
    full = ref.report(plan=_nist_calibrated_plan())
    assert full.layer1_available, full.abstained_reason
    assert any(a.gates_passed for a in full.attribution)
    for trend in full.trends:
        if not trend.separable:
            for action in full.suggested_actions:
                assert action.confidence < 0.5

    # fit plots for visual inspection (tests/output/, gitignored):
    # full pattern + the two regions where the new physics shows — the FCJ
    # low-angle tail on 100 and the resolved Kα doublet at high angle
    from pxrdref.viz.plots import plot_for_vlm, plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "srm660c_fit.png"))
    plot_result(result, path=str(out / "srm660c_fit_lowangle.png"),
                two_theta_range=(20.6, 22.2))
    plot_result(result, path=str(out / "srm660c_fit_highangle.png"),
                two_theta_range=(147.5, 150.9))
    plot_for_vlm(result, full, path=str(out / "srm660c_vlm.png"))


def test_srm660c_extinction_does_no_harm(srm_inputs):
    """WP-0506 does-no-harm: freeing secondary extinction on a fine-powder
    standard must refine it small and must not degrade the fit or bias the
    cell.  SRM 660c is a NIST line-profile standard — genuine extinction is
    negligible — so this is the guard against extinction absorbing unrelated
    residual (the unmodelled FPA-territory aberrations here)."""
    data, structure, instrument = srm_inputs
    plan = _nist_calibrated_plan()
    plan.stages.append(pr.Stage("extinction", ["phases.*.extinction"], seed=1e-3))

    ref = pr.Refinement(structure, instrument)
    result = ref.fit(data, plan=plan)

    assert result.status == "converged"
    # the fit is not degraded (adding a parameter can only help Rwp, but the
    # cell must not move out of the v0.2 acceptance band under the new freedom)
    assert result.statistics.rwp < 0.10
    a = ref.fitted_structure.phases[0].cell.a.value
    assert abs(a - A_REFERENCE) < 2e-4, f"extinction biased the cell to a={a:.6f}"
    # extinction refines back *below* its 1e-3 seed (measured ≈ 2e-10): the
    # data actively drove it to zero rather than letting it absorb residual
    ext = ref.fitted_structure.phases[0].extinction.value
    assert ext < 1e-2, f"extinction refined non-negligible ({ext:.3g}) on SRM 660c"
