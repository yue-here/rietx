"""Real-data acceptance for anomalous scattering (WP-0504).

This module tests a *prediction that was registered before it was run*, which
is why it is worth reading rather than just running.

The v0.3 QPA acceptance (`test_acceptance_qpa_roundrobin.py`,
`docs/milestones/v0.3.md`) recorded a stable, signed bias on the eight IUCr
round-robin sample-1 mixtures — zincite low by 2.7 wt % on average, corundum
high by 1.7, fluorite high by 1.0, worst |ΔW| = 5.13 wt % — and attributed it
to untreated microabsorption, while flagging that fluorite's *positive* sign
did not fit that story.

Neglected dispersion predicts all three signs, fluorite included, with no free
parameters.  At Cu Kα, Zn sits just below its K edge (f′ = −1.55) while Al and
Ca sit above theirs, so the Bragg power of each phase is mis-scaled by a
different factor — measured on these exact phase definitions as 1.0542
(corundum), 0.8441 (zincite), 1.0728 (fluorite).  A fitted scale absorbs that,
and QPA divides one phase's scale by another's, so W_p ∝ w_p·r_p renormalised.
Subtracting that from the v0.3 numbers takes their RMS from 2.26 to 0.83 wt %.

So: refit all eight under the *identical* protocol with dispersion on, and see
whether the bias goes away.  Measured numbers are in the tests below and in the
WP-0504 handover log.

The other two specimens are controls of different kinds:

* **zincite alone** (`qarr/zincite.prn`) — the non-centrosymmetric case, where
  the Friedel-averaged |A|² + |B|² is not the representative's own |F|².
* **SRM 660c LaB₆** — the absolute cell anchor.  f′ = −1.38 and f″ = 9.03
  nearly cancel in |f|² there (net −1.0 % on the Bragg power), so it is the
  *quiet* case by construction, and `a` must not move at all: dispersion
  changes intensities, never peak positions.
"""

from __future__ import annotations

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.schemas.instrument import Dispersion
from tests.test_acceptance_qpa_roundrobin import (
    DATA,
    OUT,
    SAMPLE1,
    WEIGHED,
    _fractions_pct,
    corundum_phase,
    fluorite_phase,
    qarr_instrument,
    qpa_plan,
    seed_scales,
    zincite_phase,
)

pytestmark = pytest.mark.slow

NAMES = ("corundum", "zincite", "fluorite")

#: the v0.3 measured wt-% errors, dispersion off (milestones/v0.3.md).  Frozen
#: here as the *baseline this WP is measured against* — not re-derived, so a
#: change to the fitting protocol that moves them shows up as a surprise.
V03_ERRORS = {
    "cpd-1a": (+0.61, -0.57, -0.04), "cpd-1b": (-0.12, -0.02, +0.14),
    "cpd-1c": (+1.26, -1.72, +0.47), "cpd-1d": (+1.85, -3.87, +2.02),
    "cpd-1e": (+2.21, -2.32, +0.12), "cpd-1f": (+3.17, -5.13, +1.96),
    "cpd-1g": (+2.39, -3.91, +1.52), "cpd-1h": (+2.17, -3.72, +1.54),
}


def _require_data():
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")


def _fit_anomalous(sample: str, phases: list[pr.Phase], *,
                   plan: pr.RefinementPlan, tag: str):
    """The round-robin protocol, unchanged except for the dispersion block."""
    data = pr.read_pattern(DATA / f"{sample}.prn")
    structure = pr.Structure(phases=phases)
    ins = qarr_instrument()
    ins.source.dispersion = Dispersion()
    seed_scales(structure, ins, data)
    ref = pr.Refinement(structure, ins)
    result = ref.fit(data, plan=plan)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"disp_{tag}.png"))
    result.plot(path=str(OUT / f"disp_{tag}_lowangle.png"),
                two_theta_range=(15.0, 60.0))
    import matplotlib.pyplot as plt
    plt.close("all")
    return ref, result


# ----------------------------------------------------------------------
# sample 1a-1h: the pre-registered prediction
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def sample1_anomalous():
    _require_data()
    out = {}
    for sample in SAMPLE1:
        _, result = _fit_anomalous(
            sample, [corundum_phase(), zincite_phase(), fluorite_phase()],
            plan=qpa_plan(), tag=sample)
        out[sample] = result
    return out


@pytest.mark.parametrize("sample", SAMPLE1)
def test_sample1_fractions_beat_the_dispersion_free_fit(sample1_anomalous, sample):
    """Every mixture stays converged and inside a tolerance the v0.3 fit could
    not meet: 2.5 wt % for majors against the 6 wt % the participant spread
    justified there."""
    result = sample1_anomalous[sample]
    assert result.status == "converged"
    assert result.statistics.n_points == 7251
    assert result.statistics.rwp < 0.20
    assert result.statistics.gof < 2.0

    got = _fractions_pct(result)
    assert sum(got.values()) == pytest.approx(100.0, abs=1e-6)
    for name, w_true in WEIGHED[sample].items():
        assert abs(got[name] - w_true) < 2.5, \
            f"{sample} {name}: {got[name]:.2f} vs weighed {w_true:.2f}"


def test_the_microabsorption_shape_was_mostly_dispersion(sample1_anomalous):
    """The v0.3 signed bias collapses — which re-derives its explanation.

    WP-0310 asserted the shape (zincite low, corundum high, fluorite high) as a
    live test *specifically* so that "a change that breaks — or fixes — the
    physics fails loudly and prompts re-derivation".  This is that change, and
    the shape does not survive it: the mean signed errors come back near zero
    and the worst |ΔW| falls well below the 5.13 wt % of 1f zincite.

    What is left over is small enough that microabsorption — which is real, and
    which the round robin designed sample 1 to be mild in — is no longer the
    leading term.  Note that ``qpa_plan`` frees Biso, so the refinement can and
    does re-absorb part of the correction; the improvement below is what
    survives that.
    """
    err = {name: np.array([_fractions_pct(sample1_anomalous[s])[name]
                           - WEIGHED[s][name] for s in SAMPLE1])
           for name in NAMES}
    v03 = {name: np.array([V03_ERRORS[s][i] for s in SAMPLE1])
           for i, name in enumerate(NAMES)}

    # the systematic zincite deficit is gone
    assert abs(np.mean(err["zincite"])) < 1.0
    assert np.mean(v03["zincite"]) < -1.0          # the baseline it replaces
    # and every phase's RMS error improves
    for name in NAMES:
        rms_on = float(np.sqrt(np.mean(err[name] ** 2)))
        rms_off = float(np.sqrt(np.mean(v03[name] ** 2)))
        assert rms_on < rms_off, f"{name}: RMS {rms_on:.2f} not below {rms_off:.2f}"
    worst = max(abs(e) for es in err.values() for e in es)
    assert worst < 2.5, f"worst |dW| = {worst:.2f} wt %"


# ----------------------------------------------------------------------
# zincite alone — the non-centrosymmetric specimen
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def zincite_pair():
    """(off, on) results for pure ZnO under one protocol."""
    _require_data()
    out = []
    for anomalous in (False, True):
        data = pr.read_pattern(DATA / "zincite.prn")
        structure = pr.Structure(phases=[zincite_phase()])
        ins = qarr_instrument()
        if anomalous:
            ins.source.dispersion = Dispersion()
        seed_scales(structure, ins, data)
        ref = pr.Refinement(structure, ins)
        result = ref.fit(data, plan=qpa_plan())
        OUT.mkdir(exist_ok=True)
        result.plot(path=str(OUT / f"disp_zincite_{'on' if anomalous else 'off'}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")
        out.append((ref, result))
    return out


def test_zincite_cell_does_not_move(zincite_pair):
    """Dispersion is an intensity correction; it must not touch positions.

    ZnO ``P 63 m c`` is the case where the Friedel average genuinely differs
    from the representative |F|², so if the new structure-factor path leaked
    into the peak positions this is where it would show.
    """
    (ref_off, _), (ref_on, _) = zincite_pair
    off, on = ref_off.fitted_structure.phases[0], ref_on.fitted_structure.phases[0]
    assert on.cell.a.value == pytest.approx(off.cell.a.value, abs=1e-5)
    assert on.cell.c.value == pytest.approx(off.cell.c.value, abs=1e-5)


def test_zincite_oxygen_adp_becomes_physical(zincite_pair):
    """The result Rwp barely shows, and the reason this WP is a correctness one.

    With Zn's f′ = −1.55 neglected, Zn scatters ~10 % too strongly in the
    model, and the only way the refinement can rebalance the Zn:O contrast is
    to drive B(O) to its floor — it converges at 0.02 Å², which is not a
    displacement parameter, it is a parameter that has been used up absorbing a
    systematic.  With the correction applied it lands at a physical value.
    """
    (ref_off, res_off), (ref_on, res_on) = zincite_pair
    b_off = ref_off.fitted_structure.phases[0].atoms[1].biso.value
    b_on = ref_on.fitted_structure.phases[0].atoms[1].biso.value
    assert b_off < 0.1, f"expected the dispersion-free B(O) at its floor, got {b_off}"
    assert 0.2 < b_on < 1.2, f"B(O) = {b_on} is not a physical displacement"
    assert res_on.statistics.rwp <= res_off.statistics.rwp


# ----------------------------------------------------------------------
# SRM 660c LaB6 — the absolute anchor, and the quiet case
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def srm660c_pair():
    from tests.test_acceptance_srm660c import (
        _nist_calibrated_plan,
        build_srm_inputs,
    )

    out = []
    for anomalous in (False, True):
        data, structure, instrument = build_srm_inputs()
        if anomalous:
            instrument.source.dispersion = Dispersion()
        ref = pr.Refinement(structure, instrument)
        result = ref.fit(data, plan=_nist_calibrated_plan())
        OUT.mkdir(exist_ok=True)
        result.plot(path=str(OUT / f"disp_srm660c_{'on' if anomalous else 'off'}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")
        out.append((ref, result))
    return out


def test_srm660c_lattice_parameter_is_untouched(srm660c_pair):
    """The **absolute** cell anchor must not move: a = 4.156895 Å either way,
    to well inside its 25e-6 Å esd."""
    (ref_off, res_off), (ref_on, res_on) = srm660c_pair
    a_off = ref_off.fitted_structure.phases[0].cell.a.value
    a_on = ref_on.fitted_structure.phases[0].cell.a.value
    assert a_on == pytest.approx(a_off, abs=2e-6)
    assert res_on.statistics.rwp <= res_off.statistics.rwp + 1e-4


def test_srm660c_displacement_parameters_absorb_the_change(srm660c_pair):
    """LaB₆ is the quiet case by *net* Bragg power (−1.0 %, because f′ and f″
    partly cancel for La) and still redistributes between the two sites, since
    only La carries the correction.  Recorded as a characterisation, not a
    win: B(La) and B(B) are what shift, by about 12 % and 22 %."""
    (ref_off, _), (ref_on, _) = srm660c_pair
    off = ref_off.fitted_structure.phases[0].atoms
    on = ref_on.fitted_structure.phases[0].atoms
    assert abs(on[0].biso.value - off[0].biso.value) > 0.02   # La
    assert abs(on[1].biso.value - off[1].biso.value) > 0.05   # B
    assert all(0.1 < a.biso.value < 1.0 for a in on)


def test_the_neglect_diagnostic_clears_when_the_block_is_on(srm660c_pair):
    """End-to-end: the warning fires without the block and not with it."""
    (_, res_off), (_, res_on) = srm660c_pair
    assert "DISPERSION_NEGLECTED" in {d.code for d in res_off.diagnostics}
    assert "DISPERSION_NEGLECTED" not in {d.code for d in res_on.diagnostics}
