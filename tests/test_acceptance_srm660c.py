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

import rietx as rx

DATA = Path(__file__).parent / "data"
A_REFERENCE = 4.156780       # CIF block cell at 20.85 °C
DISP_REFERENCE = -0.07877    # mm, from the CIF spec block

#: the fitted result is ``srm660c_baseline`` in tests/conftest.py, shared with
#: test_acceptance_dispersion and test_backend_jax; every consumer carries this
#: group or a second worker refits it
pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("srm660c")]


def build_srm_inputs():
    """(data, structure, instrument) for the NIST protocol — plain function so
    other suites (test_backend_jax.py) can rebuild the identical state."""
    path = DATA / "nist_srm660c_100a.cif"
    if not path.exists():
        pytest.skip("SRM 660c dataset not present")
    data = rx.read_pdcif(path, block="_meas")

    structure = rx.Structure(phases=[rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.1568),
        atoms=[
            # Uiso from the CIF cell block: La 0.0045, B 0.0035 Å² (B = 8π²U)
            rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                    biso=rx.Parameter(value=0.355, min=0.0, max=25.0)),
            rx.Atom(label="B", species="B", x=rx.Parameter(value=0.198),
                    y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5),
                    biso=rx.Parameter(value=0.276, min=0.0, max=25.0)),
        ],
        scale=rx.Parameter(value=1e-4, min=0.0, transform="softplus"),
    )])

    instrument = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.profile.w.value = 2e-3
    instrument.profile.x.value = 5e-3
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.025
    from rietx.schemas.instrument import BackgroundChebyshev
    instrument.background = BackgroundChebyshev.with_terms(6)
    # Dispersion DECLINED explicitly (WP-1001 made it the package default).
    # This is the absolute anchor and the frozen dispersion-OFF baseline that
    # test_acceptance_dispersion.py measures its ON arm against, so the
    # setting has to be stated here rather than inherited — the whole value of
    # that comparison is that exactly one thing differs between the two arms.
    # Measured either way, the cell does not move (4.156895 Å on 1.7.0,
    # 4.156882 Å since WP-1938's Γ_G² inequality); what moves is Rwp
    # (8.661 → 8.640 % on 1.7.0) and B(La)/B(B) (~12 % / ~22 %).
    instrument.source.dispersion = None
    return data, structure, instrument


def _nist_calibrated_plan() -> rx.RefinementPlan:
    """lab_bragg_brentano minus the zero error (calibrated goniometer)."""
    plan = rx.RefinementPlan(stages=[
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
    # WP-1123: the shipped convergence schedule, named rather than inherited.
    # Every stage but the last stops at 1e-6 and the last at the solver's own
    # 1e-9, which is what a user's own run does — so these numbers are the
    # ones the package actually produces.  None here would converge every
    # stage; measured cost of the schedule on this protocol is <= 0.02 esd.
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3   # WP-2002: the shipped closing stage, named rather than inherited
    return plan


def test_srm660c_lab6_rietveld(srm660c_baseline):
    _data, ref, result = srm660c_baseline

    assert result.status == "converged"
    assert result.statistics.rwp < 0.10
    assert result.statistics.gof < 2.5

    a = ref.fitted_structure.phases[0].cell.a.value
    a_err = result.parameter("phases.0.cell.a").stderr
    # the reported esd carries the Bérar-Lelann serial-correlation inflation
    # (BL ≈ 2.82 here, so ~21e-6 vs the raw χ²·(JᵀJ)⁻¹ ~7.4e-6) — WP-0407 fixed
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
    report = rx.build_report(result)
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
    from rietx.viz.plots import plot_for_vlm, plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "srm660c_fit.png"))
    plot_result(result, path=str(out / "srm660c_fit_lowangle.png"),
                two_theta_range=(20.6, 22.2))
    plot_result(result, path=str(out / "srm660c_fit_highangle.png"),
                two_theta_range=(147.5, 150.9))
    plot_for_vlm(result, full, path=str(out / "srm660c_vlm.png"))


def test_srm660c_extinction_does_no_harm(srm660c_baseline):
    """WP-0506 does-no-harm: freeing primary extinction on a fine-powder
    standard must refine it small and must not degrade the fit or bias the
    cell.  SRM 660c is a NIST line-profile standard — genuine extinction is
    negligible — so this is the guard against extinction absorbing unrelated
    residual (the unmodelled FPA-territory aberrations here).

    The stage is warm-extended onto the shared baseline instead of re-running
    the whole plan with it appended.  Same computation — ``run_stage`` restores
    the cumulative free set at the converged values before freeing the stage's
    globs — and verified as such on this dataset before landing, then
    re-measured on the 1.7.0 tree: warm-extend Rwp 0.086678434456, a
    4.15689552151728, ext 5.0e-10; whole plan Rwp 0.086678434458, a
    4.15689552247627.  Rwp agrees to 2e-12 and a to 1e-9 Å, not to the last
    digit, the extinction having converged to a different point on its
    flat floor."""
    data, ref_base, _baseline = srm660c_baseline

    ref = ref_base.branch()
    result = ref.run_stage(
        data, rx.Stage("extinction", ["phases.*.extinction"], seed=1e-3))

    assert result.status == "converged"
    # the fit is not degraded (adding a parameter can only help Rwp, but the
    # cell must not move out of the v0.2 acceptance band under the new freedom)
    assert result.statistics.rwp < 0.10
    a = ref.fitted_structure.phases[0].cell.a.value
    assert abs(a - A_REFERENCE) < 2e-4, f"extinction biased the cell to a={a:.6f}"
    # extinction refines back from its 1e-3 seed to exactly 0, its lower bound
    # (≈ 2e-10 under softplus): the data drove it to zero rather than letting
    # it absorb residual
    ext = ref.fitted_structure.phases[0].extinction.value
    assert ext < 1e-2, f"extinction refined non-negligible ({ext:.3g}) on SRM 660c"
