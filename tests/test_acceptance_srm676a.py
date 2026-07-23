"""v0.3 acceptance: lab corundum against the NIST SRM 676a certified cell.

The certificate (04 Nov 2015 issue; lattice values 23 Apr 2012) is the
**absolute anchor**: a = 4.759355 ± 0.000080 Å, c = 12.99231 ± 0.00015 Å at
22.5 °C (k = 2), on the Hölzer (1997) Cu Kα1 wavelength scale — the same
scale the ``CuKa`` instrument preset ships.  Two honesty caveats, both from
the WP-0310 brief:

* NIST publishes **no raw 676a pattern**, so the fit runs on the IUCr
  round-robin's pure-corundum lab pattern (``qarr/corundum.prn``), whose
  provenance is *not* documented as SRM 676a.  It stands in as a lab corundum
  *specimen*; the certified cell anchors the comparison, not the specimen's
  identity.
* On an ordinary Bragg-Brentano pattern the {zero, displacement, cell} triple
  is decorrelated only by *holding* a certified cell (the ``lab_calibrate``
  lesson), which is exactly what a cell-accuracy test cannot do.  The
  practical absolute tolerance is therefore lab-realistic (6×10⁻⁴ relative),
  nowhere near the certificate's ~17 ppm, and the sharp certificate-grade
  assertion is the **axial ratio c/a** — uniform d-scale systematics (zero,
  displacement, wavelength convention) cancel in it, so it survives lab data
  unharmed.  The same shape-vs-magnitude reasoning as the v0.2 FAP test.

The certificate's other value — crystalline mass fraction 99.02 ± 1.11 %
(k = 2) — is an *amorphous* quantity, certified against an external silicon
series.  Amorphous/internal-standard quantification is a v2 fence and a
WP-0310 non-goal: ``RefinementResult.qpa`` reports fractions of the modelled
crystalline content (≡ 1 for a single phase, asserted below), and this suite
does not claim to test the 99.02 %.

**Measured result** (2026-07-24, recorded in docs/milestones/v0.3.md):
Rwp = 14.4 %, GoF = 1.61; a = 4.757866 Å (−313 ppm), c = 12.988632 Å
(−283 ppm), the two axes offset by the same relative amount (Δ within
3×10⁻⁵) ⇒ a uniform d-scale systematic of this uncalibrated instrument —
while **c/a = 2.729928 lands +30 ppm** from the certificate's 2.729846.
Refined Kα2/Kα1 = 0.43 (the graphite passband clips the 0.5 emission ratio),
Biso(Al) = 0.23, Biso(O) = 0.22 Å² — both physical.
"""

from pathlib import Path

import pytest

import pxrdref as pr

from .test_acceptance_qpa_roundrobin import (
    DATA,
    corundum_phase,
    qarr_instrument,
    qpa_plan,
    seed_scales,
)

pytestmark = pytest.mark.slow

A_CERT, A_CERT_U = 4.759355, 0.000080   # k = 2, 22.5 °C
C_CERT, C_CERT_U = 12.99231, 0.00015


def test_srm676a_corundum_cell_anchor():
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = pr.read_pattern(DATA / "corundum.prn")
    structure = pr.Structure(phases=[corundum_phase()])
    ins = qarr_instrument()
    seed_scales(structure, ins, data)

    ref = pr.Refinement(structure, ins)
    result = ref.fit(data, plan=qpa_plan())

    assert result.status == "converged"
    assert result.statistics.n_points == 7251
    assert result.statistics.rwp < 0.17
    assert result.statistics.gof < 2.0

    phase = ref.fitted_structure.phases[0]
    a, c = phase.cell.a.value, phase.cell.c.value
    da, dc = a / A_CERT - 1.0, c / C_CERT - 1.0
    # lab-realistic absolute band (uncalibrated zero/displacement — docstring)
    assert abs(da) < 6e-4 and abs(dc) < 6e-4
    # the offset must be a *uniform* d-scale, the same on both axes…
    assert abs(da - dc) < 1.5e-4
    # …which is why c/a carries the certificate-grade comparison: its k = 2
    # relative uncertainty is ~21 ppm, and the fit must land within a small
    # multiple of it (measured +30 ppm)
    assert (c / a) / (C_CERT / A_CERT) - 1.0 == pytest.approx(0.0, abs=1e-4)
    # hexagonal tie: b tracks a; symmetry-fixed angles never moved
    assert phase.cell.b.value == pytest.approx(a, rel=1e-12)
    assert phase.cell.gamma.value == 120.0

    # esds exist and are Bérar-Lelann inflated; the −313 ppm absolute offset
    # is a many-σ *systematic*, which is exactly why the absolute band above
    # is not the certificate's — never let an esd launder a systematic
    a_esd = result.parameter("phases.0.cell.a").stderr
    assert a_esd is not None and 0.0 < a_esd < 1e-3
    assert result.statistics.esd_inflation > 1.0

    # physical displacement parameters and a clipped-doublet Kα2 ratio
    assert 0.05 < phase.atoms[0].biso.value < 1.0
    assert 0.05 < phase.atoms[1].biso.value < 1.0
    ka2 = ref.fitted_instrument.source.lines[1].weight.value
    assert 0.35 < ka2 < 0.55

    # single modelled phase ⇒ the QPA convention (fractions of the modelled
    # crystalline content) makes this identically 1; the certificate's
    # 99.02 % amorphous complement is out of scope (docstring)
    assert result.qpa is not None and len(result.qpa.phases) == 1
    assert result.qpa.phases[0].weight_fraction == pytest.approx(1.0, abs=1e-12)

    from pxrdref.viz.plots import plot_for_vlm, plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "srm676a_fit.png"))
    plot_result(result, path=str(out / "srm676a_fit_lowangle.png"),
                two_theta_range=(24.0, 60.0))
    plot_result(result, path=str(out / "srm676a_fit_highangle.png"),
                two_theta_range=(120.0, 150.0))
    report = ref.report(plan=qpa_plan())
    plot_for_vlm(result, report, path=str(out / "srm676a_vlm.png"))
    import matplotlib.pyplot as plt
    plt.close("all")
