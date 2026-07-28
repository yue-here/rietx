"""v0.5 acceptance: cylindrical (capillary) absorption on real 11-BM data.

WP-0501 shipped the Rouse, Cooper, York & Chakera (1970) cylinder correction
with algorithm-level evidence only — the fit against the published table and
against a quadrature of ITC eq. (6.3.3.4), plus the Biso bias measured on
synthetic data.  What it could not do was run it on a real capillary pattern,
because ``tests/data`` had none with a **stated bore and specimen**, the two
things µR needs.  WP-0508 found one.

Dataset: ``11BM_LaB6_660a.fxye`` — NIST SRM 660a LaB6 measured at APS 11-BM,
λ = 0.4131280 Å from the accompanying ``.prm``, 132 992 points, 295.0 K.  The
file's own header names the specimen (``sample_name, "SRM 660a"``) and records
``comment1, "robotic collection"``, i.e. the mail-in robot, whose standard
container is a 0.8 mm Kapton tube of **ID 0.0320″ = 0.81 mm** (Cole-Parmer
#95820-06, quoted on the beamline's Supplies and Tools page).  Composition ×
R = 0.405 mm × packing gives µR = 0.47-0.81, inside the Rouse fit's µR ≤ 1.

**What this suite asserts, and what it deliberately does not.**

The Rouse factor is *exactly* a constant times exp(c·sin²θ) — a Debye-Waller
shape — so applying it to a model with a free phase scale and free displacement
parameters is an exact reparameterisation.  The prediction is therefore sharp
and one-sided: **Rwp and the cell cannot move, and every Biso must shift by
exactly ``equivalent_delta_biso(µR, λ)``.**  A correction that improved Rwp here
would be evidence that it is wrong, not that it works.

Two things this suite must *not* claim, both recorded in tests/data/README.md:

* **The cell is not an anchor.**  The header says
  ``# Calibration from: /data/oct09/11bmb_3843.calib`` — λ was calibrated at the
  beamline against LaB6, so refining a LaB6 cell against it is circular.  It
  lands 16 ppm from the SRM 660a certificate (4.1569162(97) Å at 22.5 °C, with
  this scan at 295.0 K), which is quotable as consistency and nothing more.
  The absolute cell anchors stay SRM 660c and SRM 676a.
* **The absolute Biso is not a reference value.**  Neglected anomalous
  dispersion (WP-0504; La at 30 keV, K edge 38.9 keV, f′ = −1.22) moves B(La)
  by −0.044 Å², 2.6× the absorption effect and in the opposite direction.  Two
  independent biases land on the same parameters, so only the *difference*
  measured here is attributable to absorption — which is why the last test
  re-measures the identity with dispersion switched on.

Measured 2026-07-28 (2-60° 2θ, 116 001 points, µR = 0.674):
Rwp 0.0884883 → 0.0884884, a 4.1568496 → 4.1568496 (−7.9e-12 Å),
B(La) 0.453890 → 0.470545 and B(B) 0.205395 → 0.222049, both +0.0166542 Å²
against a predicted 0.0166542.
"""

from pathlib import Path

import pytest

import pxrdref as pr
from pxrdref.schemas.instrument import BackgroundChebyshev, Dispersion

DATA = Path(__file__).parent / "data"
WAVELENGTH = 0.4131280           # .prm ICONS, the beamline's own calibration
LIMITS = (2.0, 60.0)
#: documented 11-BM mail-in container: 0.81 mm ID Kapton ⇒ R = 0.405 mm
CAPILLARY_RADIUS_MM = 0.405
#: nobody measures this; 0.3-0.6 is a tapped powder.  The acceptance is built so
#: that its *conclusion* does not depend on the value — only the predicted shift
#: does, and that is compared against the correction's own prediction.
PACKING_FRACTION = 0.5
#: SRM 660a certificate, 22.5 °C (k = 2 uncertainty 9.7e-6 Å).  Consistency
#: reference only — see the module docstring on why it cannot be an anchor.
A_CERTIFICATE = 4.1569162

pytestmark = pytest.mark.slow


def _structure() -> pr.Structure:
    structure = pr.Structure.from_cif(str(DATA / "cod_1000055.cif"))
    phase = structure.phases[0]
    phase.scale = pr.Parameter(value=1e-4, min=0.0, transform="softplus")
    for atom in phase.atoms:
        atom.biso = pr.Parameter(value=0.3, min=0.0, max=5.0)
    return structure


def _instrument(*, capillary: bool, dispersion: bool = False) -> pr.Instrument:
    """The 11-BM preset, with the capillary declared or not.

    ``capillary=True`` goes through the *estimator* (composition → µ → µR)
    rather than setting µR directly, so the acceptance covers that path too.
    """
    instrument = pr.Instrument.debye_scherrer(
        wavelength=WAVELENGTH,
        capillary_radius_mm=CAPILLARY_RADIUS_MM if capillary else None,
        packing_fraction=PACKING_FRACTION,
    )
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = BackgroundChebyshev.with_terms(8)
    if dispersion:
        instrument.source.dispersion = Dispersion()
    return instrument


def _plan() -> pr.RefinementPlan:
    plan = pr.RefinementPlan.mccusker_default()
    plan.stages.append(pr.Stage("biso", ["phases.*.atoms.*.biso"]))
    return plan


def _fit(*, capillary: bool, dispersion: bool = False):
    if not (DATA / "11BM_LaB6_660a.fxye").exists():
        pytest.skip("11-BM SRM 660a dataset not present")
    data = pr.read_pattern(DATA / "11BM_LaB6_660a.fxye")
    ref = pr.Refinement(_structure(), _instrument(capillary=capillary,
                                                  dispersion=dispersion))
    result = ref.fit(data, plan=_plan(), two_theta_limits=LIMITS)
    return ref, result


def _bisos(ref) -> list[float]:
    return [atom.biso.value for atom in ref.fitted_structure.phases[0].atoms]


@pytest.fixture(scope="module")
def plain():
    return _fit(capillary=False)


@pytest.fixture(scope="module")
def corrected():
    return _fit(capillary=True)


def test_estimated_mu_r_matches_the_documented_capillary(corrected):
    """Composition → µ → µR through the estimator, at the documented bore."""
    _ref, result = corrected
    record = result.absorption
    assert record is not None, "no absorption record for a declared capillary"
    assert record.method == "rouse_cylinder"
    assert record.mu_r_source == "estimated"
    assert record.skipped is None
    assert not record.out_of_range, "µR left the Rouse fit's range"
    # 0.674 at packing 0.5; the plausible packing band 0.35-0.6 spans 0.47-0.81
    assert 0.60 < record.mu_r < 0.75, record.mu_r
    assert record.wavelength == pytest.approx(WAVELENGTH)

    # the public helper must agree with what the refinement resolved internally
    standalone = pr.estimate_mu_r(_structure(), _instrument(capillary=True))
    assert standalone == pytest.approx(record.mu_r, rel=1e-9)


def test_capillary_absorption_is_an_exact_reparameterisation(plain, corrected):
    """The whole content of the correction, on real data.

    Rwp and the cell are invariant to machine precision; every displacement
    parameter moves by exactly the predicted bias.  This is a stronger statement
    than "the fit got better" — the fit *cannot* get better, and each assertion
    below fails if the correction were applied with the wrong θ-dependence, the
    wrong sign, or (the WP-0501 trap) as A* = 1/A instead of A.
    """
    ref_a, res_a = plain
    ref_b, res_b = corrected
    assert res_a.status == "converged" and res_b.status == "converged"
    assert res_a.absorption is None, "absorption applied without a capillary"

    # 1. the fit is untouched
    assert res_b.statistics.rwp == pytest.approx(res_a.statistics.rwp, abs=1e-6)
    assert res_b.statistics.chi2 == pytest.approx(res_a.statistics.chi2, rel=1e-6)

    # 2. the cell is untouched — an absorption correction that moved a lattice
    #    parameter would be modelling an angular *shift*, which it is not
    a_plain = ref_a.fitted_structure.phases[0].cell.a.value
    a_corr = ref_b.fitted_structure.phases[0].cell.a.value
    assert a_corr == pytest.approx(a_plain, abs=1e-9)

    # 3. every Biso moves by the predicted bias, and by the *same* amount:
    #    A is a per-reflection intensity factor shared by all sites, so the
    #    shift is a property of (µR, λ) alone
    predicted = res_b.absorption.equivalent_delta_biso
    assert predicted > 0.0
    for label, b_plain, b_corr in zip(
            [atom.label for atom in ref_a.fitted_structure.phases[0].atoms],
            _bisos(ref_a), _bisos(ref_b)):
        assert b_corr - b_plain == pytest.approx(predicted, abs=1e-5), (
            f"B({label}) shifted by {b_corr - b_plain:.7f}, predicted {predicted:.7f}")

    # 4. and the sign is the one the physics demands: neglecting capillary
    #    absorption biases Biso *low*, so correcting it raises them
    assert all(c > p for p, c in zip(_bisos(ref_a), _bisos(ref_b)))

    from pxrdref.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(res_b, path=str(out / "capillary_lab6_660a_fit.png"))
    plot_result(res_b, path=str(out / "capillary_lab6_660a_lowangle.png"),
                two_theta_range=(5.0, 12.0))
    plot_result(res_b, path=str(out / "capillary_lab6_660a_highangle.png"),
                two_theta_range=(52.0, 60.0))


def test_fit_quality_and_the_circular_cell(corrected):
    """The fit itself is sound, and the cell agrees — circularly."""
    ref, result = corrected
    assert result.statistics.rwp < 0.10
    assert result.statistics.gof < 2.0
    a = ref.fitted_structure.phases[0].cell.a.value
    # 16 ppm measured.  The band is generous *on purpose*: this is not an
    # accuracy claim, it is a guard that the beamline calibration and our
    # wavelength scale have not silently diverged (see the module docstring).
    assert abs(a - A_CERTIFICATE) / A_CERTIFICATE < 1e-4

    report = pr.build_report(result)
    assert report.summary
    assert report.n_regions_total > 10


def test_the_absorption_shift_is_independent_of_dispersion():
    """Absorption and anomalous dispersion bias the same parameters, separately.

    Dispersion moves B(La) by −0.044 Å² here — 2.6× the absorption effect and
    the other way — so a suite that only ever measured absorption on a
    dispersion-free model could not tell an exact reparameterisation from one
    that happened to fit this particular model.  Re-measuring the identity on
    top of a *different* model is what makes "exact" mean exact.
    """
    ref_a, _res_a = _fit(capillary=False, dispersion=True)
    ref_b, res_b = _fit(capillary=True, dispersion=True)
    predicted = res_b.absorption.equivalent_delta_biso
    for b_plain, b_corr in zip(_bisos(ref_a), _bisos(ref_b)):
        assert b_corr - b_plain == pytest.approx(predicted, abs=1e-5)

    # and dispersion itself is doing something substantial and opposite on La,
    # which is what makes the check above non-trivial
    ref_nodisp, _ = _fit(capillary=False)
    b_la_disp, b_la_plain = _bisos(ref_a)[0], _bisos(ref_nodisp)[0]
    assert b_la_disp - b_la_plain < -2.0 * predicted, (
        f"dispersion moved B(La) by {b_la_disp - b_la_plain:.4f}, expected ≈ −0.044")
