"""WP-1019 — the data-quality gate and the systematic-shift model.

Two things are being tested, and they are asymmetric on purpose.

The **gate** must abstain rather than hand a search data that cannot support
one — the same move Layer 1's maturity gate makes one rank down, and the
assertions are about *refusal*, not about accuracy.

The **shift screen** must name the physical cause when the angular range makes
the three causes separable, and must **decline to name one** when it does not,
while still measuring the magnitude.  That second half is the point: a
zero-point error, a displaced specimen and a transparent specimen are three
different physical faults with three different angular dependences, and every
program the 2004 benchmark paper surveys fits one constant "zeropoint" instead.
Naming the wrong cause is worse than naming none, because the correction is
applied to the wrong part of the instrument.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.crystallography.symmetry import generate_reflections
from rietx.indexing.diagnostics import quality_diagnostics
from rietx.indexing.quality import (
    _LAUE_ORBIT_FACTOR,
    _MAX_CENTRING,
    VOLUME_ENVELOPE_SLACK,
    assess_peak_list,
    fit_shift_model,
    shift_template_basis,
    template_collinearity,
    volume_envelope,
)
from rietx.report.schemas import SEPARABILITY_MIN_SS_RATIO
from rietx.schemas.indexing import (
    MAX_RELATIVE_SIGMA_Q,
    METRIC_DOF,
    MIN_LINES_PER_DOF,
    PEAK_MIN_USABLE_LINES,
    SHIFT_TEMPLATES,
    DataQualityReport,
    PeakList,
)

LAM = 1.5405929
#: a range over which cos θ, sin 2θ and a constant genuinely differ
WIDE = np.linspace(15.0, 130.0, 30)
#: and one over which they do not — the failure the screen must report
NARROW = np.linspace(10.0, 25.0, 20)


def _shifted(tt: np.ndarray, template: str, amplitude: float,
             noise: float = 0.0, seed: int = 0) -> np.ndarray:
    """Deviations produced by one template, with optional Gaussian scatter."""
    dev = amplitude * shift_template_basis(tt)[template]
    if noise:
        dev = dev + np.random.default_rng(seed).normal(0.0, noise, tt.shape)
    return dev


def _peak_list(tt: np.ndarray, *, esd: float = 0.005) -> PeakList:
    return PeakList.from_positions(tt, LAM, two_theta_esd=esd)


# ----------------------------------------------------------------------
# The shift screen
# ----------------------------------------------------------------------
@pytest.mark.parametrize("template,amplitude", [
    ("constant", 0.08),
    ("cos_theta", 0.10),
    ("sin_2theta", 0.06),
])
def test_shift_template_recovered_when_separable(template, amplitude):
    """Over a wide range the right cause wins and its coefficient is right.

    Amplitudes are the ~0.10° both bethanechol ICDD entries carry, which the 2004
    paper *hypothesised* was specimen displacement without a way to test it.
    """
    dev = _shifted(WIDE, template, amplitude, noise=0.004, seed=3)
    screen = fit_shift_model(WIDE, dev, 0.005)

    assert screen.best == template
    assert screen.separable
    assert screen.separability_ratio > SEPARABILITY_MIN_SS_RATIO
    best = next(t for t in screen.templates if t.name == template)
    assert abs(best.coefficient - amplitude) < 2.0 * best.stderr
    # σ_sys is what is left after the named cause: here, the injected scatter
    assert screen.sigma_sys_deg == pytest.approx(0.004, rel=0.5)


def test_shift_cause_is_not_claimed_when_templates_are_collinear():
    """The cell stands, the cause does not — with "competitive" doing real work.

    Over a short low-angle range the templates are collinear and the cause cannot
    be named.  The plan justified that with "the *cell* stands — all three
    templates remove the same amount at the sampled angles", and measuring it
    both ways is what makes the claim usable: over **all three** templates the
    predicted corrections differ by 0.046°, nearly half the injected 0.10° shift,
    which would be a 0.2 % cell error.  But ``sin_2theta`` is not competitive
    here — it fits worse than the ratio bar allows — and over the two that are,
    the spread is 0.0011°, about 1 % of the shift.  So the conclusion survives
    and the reasoning is narrowed: a template the data rejects is not a candidate
    cause, and the screen reports the spread instead of asserting the claim.
    """
    dev = _shifted(NARROW, "cos_theta", 0.10, noise=0.002, seed=5)
    screen = fit_shift_model(NARROW, dev, 0.005)

    assert not screen.separable
    assert screen.separability_ratio < SEPARABILITY_MIN_SS_RATIO
    assert screen.max_collinearity > 0.99

    basis = shift_template_basis(NARROW)
    competitive = [t for t in screen.templates
                   if t.residual_ss <= SEPARABILITY_MIN_SS_RATIO
                   * min(x.residual_ss for x in screen.templates)]
    assert len(competitive) == 2 and "sin_2theta" not in {
        t.name for t in competitive}
    predicted = np.array([t.coefficient * basis[t.name] for t in competitive])
    spread = float(np.max(predicted.max(axis=0) - predicted.min(axis=0)))
    assert screen.prediction_spread_deg == pytest.approx(spread, rel=1e-9)
    assert screen.prediction_spread_deg < 0.005, "the cell does not stand"

    all_three = np.array([t.coefficient * basis[t.name]
                          for t in screen.templates])
    assert float(np.max(all_three.max(axis=0) - all_three.min(axis=0))) > 0.02, (
        "including the rejected template overstates the risk — which is why "
        "the spread is taken over the competitive ones")

    codes = {d.code for d in _diagnostics_for(NARROW, dev)}
    assert "INDEX_SHIFT_MODEL_AMBIGUOUS" in codes
    assert "INDEX_SHIFT_DETECTED" not in codes


def test_prediction_spread_collapses_when_the_range_is_wide():
    """The same shift, separable: naming the cause then costs almost nothing."""
    wide = fit_shift_model(WIDE, _shifted(WIDE, "cos_theta", 0.10,
                                         noise=0.002, seed=5), 0.005)
    assert wide.separable
    assert wide.prediction_spread_deg == 0.0     # no rival is competitive


def _diagnostics_for(tt, dev):
    peaks = _peak_list(tt)
    report = assess_peak_list(peaks, reference_two_theta=tt - dev)
    return report.diagnostics


def test_separable_shift_reports_the_physical_cause_by_name():
    dev = _shifted(WIDE, "cos_theta", 0.10, noise=0.003, seed=7)
    d = next(x for x in _diagnostics_for(WIDE, dev)
             if x.code == "INDEX_SHIFT_DETECTED")
    assert "displacement" in d.message
    assert "sample_displacement" in d.message
    assert d.level == "warning"


def test_collinearity_falls_as_the_range_extends():
    """The separability geometry is knowable from the *angles alone*, before any
    shift is measured — which makes it a statement about the experiment."""
    got = [template_collinearity(np.linspace(10.0, hi, 25))
           for hi in (20.0, 40.0, 80.0, 140.0)]
    assert got == sorted(got, reverse=True)
    # measured: 1.0000 → 0.9987 → 0.9852 → 0.9646.  It never reaches a
    # comfortable number, and that is the honest reading — ``constant`` and
    # ``cos θ`` stay 0.96 collinear even over 10-140°, which is why
    # separability is decided on the residual-SS ratio against real data and not
    # on this geometry alone.
    assert got[0] > 0.999 and got[-1] < 0.97


def test_a_cell_error_is_not_offered_as_a_shift():
    """``tan_theta`` is deliberately absent from the basis.

    A tan θ deviation *is* a cell error, and offering it here would let the
    screen "explain" a shift by changing the very answer indexing is about to
    produce.  Injecting one must therefore fit badly rather than be attributed:
    the screen has no template for it, which is the correct answer.
    """
    assert set(shift_template_basis(WIDE)) == set(SHIFT_TEMPLATES)
    assert "tan_theta" not in SHIFT_TEMPLATES

    theta = np.radians(WIDE / 2.0)
    dev = 0.05 * np.tan(theta)          # a 0.05° cell-shaped deviation
    screen = fit_shift_model(WIDE, dev, 0.005)
    best = next(t for t in screen.templates if t.name == screen.best)
    assert best.r2 < 0.95, "a cell error was absorbed by a shift template"


def test_shift_screen_needs_a_reference_and_says_so_when_it_has_none():
    """With no cell there is nothing to deviate from, so the screen reports
    ``unavailable`` rather than a shift of zero it did not measure."""
    report = assess_peak_list(_peak_list(WIDE))
    assert report.shift is not None
    assert report.shift.source == "unavailable"
    assert report.shift.best is None
    assert report.shift.sigma_sys_deg == 0.0
    # but the separability geometry is still reported
    assert report.shift.max_collinearity > 0.0
    assert {d.code for d in report.diagnostics} & {"PEAK_POSITION_PRECISION"}

    declared = assess_peak_list(_peak_list(WIDE), sigma_sys_deg=0.01)
    assert declared.shift.sigma_sys_deg == 0.01
    assert declared.shift.source == "unavailable"     # declared, not measured


def test_reference_length_mismatch_is_an_error_not_a_broadcast():
    with pytest.raises(ValueError, match="one reference per usable line"):
        assess_peak_list(_peak_list(WIDE), reference_two_theta=WIDE[:5])


# ----------------------------------------------------------------------
# The gate
# ----------------------------------------------------------------------
def test_short_list_is_searchable_but_not_scorable():
    """WP-1043's split: six lines over-determine a cubic metric six-fold, so the
    list supports a *search* (in the systems ``MIN_LINES_PER_DOF`` admits) while
    the classical figures stay undefined — reported absent with reasons, never
    computed at a different N.  The pre-1043 gate abstained here, conflating the
    two preconditions; fluorite's 18 clean lines were refused the same way."""
    report = assess_peak_list(_peak_list(np.linspace(20.0, 60.0, 6)))
    assert report.supports_indexing
    assert report.abstained_reason is None
    assert report.systems_supported == ["cubic"]
    assert set(report.fom_undefined) == {"m20", "f_n"}
    for reason in report.fom_undefined.values():
        assert str(PEAK_MIN_USABLE_LINES) in reason
    codes = {x.code for x in report.diagnostics}
    assert "INDEX_DATA_INSUFFICIENT" not in codes
    d = next(x for x in report.diagnostics if x.code == "INDEX_PANEL_REDUCED")
    assert d.level == "warning"
    assert "cubic" in d.message


def test_a_list_below_every_systems_support_abstains():
    """Abstention is about searchability: with fewer lines than
    ``MIN_LINES_PER_DOF`` in every system the metric is not over-determined
    anywhere, and that — not the scoring bar — is what refuses a search."""
    report = assess_peak_list(_peak_list(np.linspace(20.0, 60.0, 4)))
    assert not report.supports_indexing
    assert report.systems_supported == []
    assert "metric degree of freedom" in report.abstained_reason
    d = next(x for x in report.diagnostics if x.code == "INDEX_DATA_INSUFFICIENT")
    assert d.level == "error"
    # the scoring bar is also unmet, but abstention already says more, so the
    # reduced-panel warning stays out of the way
    assert not any(x.code == "INDEX_PANEL_REDUCED" for x in report.diagnostics)


def _fitted(tt: np.ndarray, esd: float) -> PeakList:
    """The same list, but declaring its σ **measured** — which is what makes the
    σ(Q)/Q abstention applicable at all (see the next test)."""
    pl = _peak_list(tt, esd=esd)
    return pl.model_copy(update={
        "source": "fitted",
        "peaks": [p.model_copy(update={
            "flags": [f for f in p.flags if f != "sigma_assumed"]})
            for p in pl.peaks]})


def test_imprecise_list_abstains_even_when_it_is_long():
    """Enough lines is not enough: an inflated σ makes candidate cells
    indistinguishable, and no tolerance can recover that."""
    coarse = _fitted(np.linspace(15.0, 130.0, 40), esd=0.5)
    report = assess_peak_list(coarse)
    assert report.relative_sigma_q_median > MAX_RELATIVE_SIGMA_Q
    assert not report.supports_indexing
    assert "σ(Q)/Q" in report.abstained_reason

    fine = _fitted(np.linspace(15.0, 130.0, 40), esd=0.005)
    assert assess_peak_list(fine).supports_indexing


def test_an_abstention_names_an_undeclared_instrument_first():
    """The picker holds the instrument it was given, so a default axial
    aperture and the synchrotron default profile widen every esd it fits.
    Declaring both is a re-pick, the cheapest remedy, so it leads (WP-1510)."""
    from rietx import Instrument
    from rietx.schemas.common import Parameter
    from rietx.schemas.instrument import ProfileTCHZ

    coarse = _fitted(np.linspace(15.0, 130.0, 40), esd=0.5)
    bare = Instrument.bragg_brentano()
    bare = bare.model_copy(update={"profile": ProfileTCHZ()})
    d = next(x for x in assess_peak_list(coarse, instrument=bare).diagnostics
             if x.code == "INDEX_DATA_INSUFFICIENT")
    assert d.suggestion.startswith("Declare the instrument")
    assert "axial_sl" in d.suggestion and "ProfileTCHZ" in d.suggestion
    assert "instrument.profile" in d.where

    # only what is still at default is located
    axial = bare.model_copy(update={
        "geometry": bare.geometry.model_copy(update={
            "axial_sl": Parameter(value=0.03, min=0.0, max=0.2),
            "axial_hl": Parameter(value=0.03, min=0.0, max=0.2)})})
    d = next(x for x in assess_peak_list(coarse, instrument=axial).diagnostics
             if x.code == "INDEX_DATA_INSUFFICIENT")
    assert "instrument.profile" in d.where
    assert "instrument.geometry" not in d.where

    declared = bare.model_copy(update={
        "geometry": bare.geometry.model_copy(update={
            "axial_sl": Parameter(value=0.03, min=0.0, max=0.2),
            "axial_hl": Parameter(value=0.03, min=0.0, max=0.2)}),
        "profile": ProfileTCHZ(w=Parameter(value=0.004, min=0.0))})
    for ins in (declared, None):
        d = next(x for x in assess_peak_list(coarse, instrument=ins).diagnostics
                 if x.code == "INDEX_DATA_INSUFFICIENT")
        assert d.suggestion.startswith("Extend the 2θ range")
        assert "instrument.profile" not in d.where


def test_an_assumed_sigma_may_not_refuse_to_index():
    """WP-1026: the precision abstention is a statement about *measured* data.

    ``MAX_RELATIVE_SIGMA_Q`` says these lines are too imprecise to tell nearby
    cells apart.  On a ``from_positions`` list there is nothing to say that from:
    every σ is :data:`PEAK_ASSUMED_ESD_DEG`, chosen by this package, so refusing
    on it quotes an assumed precision as a measured one — the inverse of the
    mistake the whole module is built to avoid.

    The pair below is the same 2θ list twice, differing **only** in whether its σ
    is declared measured.  It is not a hypothetical: at 4.9° 2θ the assumed 0.02°
    is 0.8 % of the angle, so all ten sets of the published bethanechol benchmark
    failed this test — including the synchrotron set whose published M(20) is 197.
    """
    tt = np.linspace(15.0, 130.0, 40)
    assumed = _peak_list(tt, esd=0.5)
    assert assumed.source == "positions"
    report = assess_peak_list(assumed)

    assert report.relative_sigma_q_median > MAX_RELATIVE_SIGMA_Q  # still reported
    assert report.supports_indexing                               # but has no vote
    # the caller is still told: the figure has its own diagnostic, and every line
    # carries the flag that says where its σ came from
    assert "PEAK_POSITION_PRECISION" in {d.code for d in report.diagnostics}
    assert all("sigma_assumed" in p.flags for p in assumed.peaks)

    # …and the identical list with a *measured* σ of the same size does abstain
    assert not assess_peak_list(_fitted(tt, esd=0.5)).supports_indexing


def test_single_line_list_abstains_without_dividing_by_zero():
    report = assess_peak_list(_peak_list(np.array([30.0])))
    assert not report.supports_indexing
    assert report.volume_envelope == {}
    assert np.isnan(report.sigma_two_theta_median)


def test_enough_lines_is_system_dependent():
    """20 lines is 20× over-determined for cubic and 3.3× for triclinic, which
    is why the report lists *which systems* the data can support rather than
    answering yes or no."""
    report = assess_peak_list(_peak_list(np.linspace(15.0, 130.0, 20)))
    assert report.lines_per_dof["cubic"] == 20.0
    assert report.lines_per_dof["triclinic"] == pytest.approx(20 / 6)
    assert "cubic" in report.systems_supported
    assert "triclinic" not in report.systems_supported
    for system, dof in METRIC_DOF.items():
        assert (system in report.systems_supported) == (
            20 / dof >= MIN_LINES_PER_DOF)


def test_assumed_sigma_is_reported_as_unmeasured():
    report = assess_peak_list(_peak_list(WIDE))
    assert report.source == "positions"
    d = next(x for x in report.diagnostics if x.code == "PEAK_POSITION_PRECISION")
    assert "were assumed" in d.message
    assert "pick_peaks" in d.suggestion


def test_report_round_trips_through_json():
    report = assess_peak_list(_peak_list(WIDE),
                              reference_two_theta=WIDE - _shifted(WIDE, "constant", 0.05))
    again = DataQualityReport.model_validate_json(report.model_dump_json())
    assert again.shift.best == report.shift.best
    assert again.lines_per_dof == report.lines_per_dof
    assert again.volume_envelope == report.volume_envelope
    assert set(again.volume_envelope) == set(METRIC_DOF)
    assert (again.volume_envelope["cubic"]
            > 90.0 * again.volume_envelope["triclinic"])


# ----------------------------------------------------------------------
# Volume envelope
# ----------------------------------------------------------------------
@pytest.mark.parametrize("sg,cell,system", [
    ("P m -3 m", (4.1566, 4.1566, 4.1566, 90.0, 90.0, 90.0), "cubic"),
    ("F d -3 m", (5.4309, 5.4309, 5.4309, 90.0, 90.0, 90.0), "cubic"),
    ("R -3 c", (4.7591, 4.7591, 12.9894, 90.0, 90.0, 120.0), "trigonal"),
    ("P 6_3/m", (9.4166, 9.4166, 6.8745, 90.0, 90.0, 120.0), "hexagonal"),
    ("I 4_1/a m d", (3.7842, 3.7842, 9.5146, 90.0, 90.0, 90.0), "tetragonal"),
    ("P 1", (7.0, 8.0, 9.0, 85.0, 95.0, 100.0), "triclinic"),
])
def test_volume_envelope_contains_the_true_volume(sg, cell, system):
    """Smith's (1977) envelope is a *bound*, and the one failure it must never
    have is excluding the true cell.

    d₂₀ comes from the package's own reflection generator, so the test measures
    the envelope against the same line list an engine would see.
    """
    from rietx.crystallography.lattice import cell_volume

    refl = generate_reflections(sg, cell, LAM, 160.0)
    d = np.sort(refl.d)[::-1]
    n = min(PEAK_MIN_USABLE_LINES, len(d))
    envelope = volume_envelope(float(d[n - 1]), n, system)
    assert envelope > cell_volume(*cell), (
        f"{sg}: envelope {envelope:.0f} Å³ excludes the true "
        f"{cell_volume(*cell):.0f} Å³")


@pytest.mark.parametrize("sg,cell,system", [
    ("R -3 c", (4.7591, 4.7591, 12.9894, 90.0, 90.0, 120.0), "trigonal"),
    ("P 1", (7.0, 8.0, 9.0, 85.0, 95.0, 100.0), "triclinic"),
])
def test_the_search_ceiling_survives_an_incomplete_line_list(sg, cell, system):
    """The raw envelope is a mean line, and missing lines are the ordinary case.

    The guard above feeds a *complete* generated list (p = 1) and is therefore
    blind to Smith's own calibration: his fit averages 10.6 % discrepancy with
    deviations to 29 % **low**, and a list missing weak lines pushes its
    twentieth line deeper in d, shrinking d₂₀³.  Measured here at p = 0.6
    (keep six lines in ten, deterministically) the raw envelope *excludes* the
    certified corundum-setting cell — 0.94× its volume — so until WP-1045 an
    engine defaulting to the raw envelope pruned the true cell before scoring
    it.  ``search_volume_ceiling`` is the fix: the envelope enters the search
    only through ``VOLUME_ENVELOPE_SLACK``, while a caller's own
    ``max_volume`` passes verbatim (explicit narrowing is the caller's act,
    recorded in ``spec_notes``, never "corrected").
    """
    from types import SimpleNamespace

    from rietx.crystallography.lattice import cell_volume
    from rietx.indexing.engines import (
        DEFAULT_VOLUME_CEILING,
        SearchSpec,
        search_volume_ceiling,
    )

    refl = generate_reflections(sg, cell, LAM, 160.0)
    d = np.sort(refl.d)[::-1]
    kept = d[(np.arange(len(d)) % 10) < 6]
    n = min(PEAK_MIN_USABLE_LINES, len(kept))
    raw = volume_envelope(float(kept[n - 1]), n, system)
    truth = cell_volume(*cell)
    assert raw < truth, (
        f"{sg}: the raw envelope ({raw:.0f} Å³) no longer excludes the true "
        f"{truth:.0f} Å³ at p = 0.6 — this test needs a case where the trap "
        "is real, or it pins nothing")

    quality = SimpleNamespace(volume_envelope={system: raw})
    ceiling = search_volume_ceiling(SearchSpec(), quality, system)
    assert ceiling == pytest.approx(VOLUME_ENVELOPE_SLACK * raw)
    assert ceiling > truth, (
        f"{sg}: ceiling {ceiling:.0f} Å³ still excludes the true {truth:.0f}")

    # a declared max_volume is the caller's own act — verbatim, no slack
    declared = search_volume_ceiling(
        SearchSpec(max_volume=123.0), quality, system)
    assert declared == 123.0
    # and with no evidence at all, the generous default
    assert search_volume_ceiling(SearchSpec(), None, system) == (
        DEFAULT_VOLUME_CEILING)


def test_triclinic_envelope_constant_is_smiths():
    """13.39·d₂₀³ at N = 20 — the two published constants, not their product."""
    assert volume_envelope(1.0, 20, "triclinic") == pytest.approx(13.3929, rel=1e-4)
    # cubic: Laue 24 × worst-case F centring 4
    assert volume_envelope(1.0, 20, "cubic") == pytest.approx(
        24.0 * 4.0 * 13.3929, rel=1e-4)
    # an extinction symbol (WP-1025) tightens it; the default is the loosest
    assert volume_envelope(1.0, 20, "cubic", centring_multiplicity=1) < (
        volume_envelope(1.0, 20, "cubic"))
    assert _MAX_CENTRING["triclinic"] == 1 and _MAX_CENTRING["hexagonal"] == 1
    with pytest.raises(ValueError):
        volume_envelope(0.0, 20)


@pytest.mark.parametrize("sg,cell,system", [
    ("P -1", (7.0, 8.0, 9.0, 85.0, 95.0, 100.0), "triclinic"),
    ("P 1 21/c 1", (7.0, 8.0, 9.0, 90.0, 95.0, 90.0), "monoclinic"),
    ("P n m a", (7.0, 8.0, 9.0, 90.0, 90.0, 90.0), "orthorhombic"),
    ("P 4/m m m", (7.0, 7.0, 9.0, 90.0, 90.0, 90.0), "tetragonal"),
    ("P 6/m m m", (7.0, 7.0, 9.0, 90.0, 90.0, 120.0), "hexagonal"),
    ("P m -3 m", (7.0, 7.0, 7.0, 90.0, 90.0, 90.0), "cubic"),
])
def test_laue_orbit_factor_is_the_generators_own_multiplicity(sg, cell, system):
    """The scaling is checked against ``generate_reflections``, not tabulated.

    The factor is the *maximal* Laue class of each system, deliberately: a lower
    Laue class inside the same system shows more distinct lines for the same
    volume, so its true cell is smaller than this bound — and a bound must err
    toward including the true cell.  Hence ``mean multiplicity / 2 ≤ factor``,
    with equality for the maximal class.
    """
    refl = generate_reflections(sg, cell, 0.7, 90.0)
    mean_mult = float(np.mean(refl.multiplicity))
    factor = _LAUE_ORBIT_FACTOR[system]
    assert mean_mult / 2.0 <= factor * 1.02
    assert mean_mult / 2.0 > 0.5 * factor


# ----------------------------------------------------------------------
# The dominant-zone census that is deliberately absent
# ----------------------------------------------------------------------
def test_dominant_zone_is_not_claimed_from_a_census():
    """A measured no-go, kept as a test so it cannot be silently re-added.

    This WP's plan said a dominant zone and a dominant row are "detectable in
    Q-space before any search".  They are not: a dominant zone is the statement
    that the low-angle lines satisfy a *two-dimensional* quadratic form, and a
    dominant row is an arithmetic progression k²B among the low Q values — each
    is a search, not a census.  The obvious census (Ito's most-repeated Q
    difference) was implemented and measured, and scored dominant-zone cells at
    +0.9σ and +0.8σ against a permutation null while scoring a *general*
    monoclinic cell at +3.3σ; against a uniform null a **cubic** list scores
    +15.6σ, because Q = A(h²+k²+l²) makes every difference a multiple of A.  So
    the report carries no such field and no ``INDEX_DOMINANT_ZONE`` code, and the
    detection is owed to the engines (WP-1021/1022) where a candidate zone exists.
    """
    report = assess_peak_list(_peak_list(WIDE))
    assert not hasattr(report, "dominant_significance")
    assert "INDEX_DOMINANT_ZONE" not in {d.code for d in report.diagnostics}


# ----------------------------------------------------------------------
# End to end, on a picked peak list rather than a synthetic one
# ----------------------------------------------------------------------
def test_gate_on_a_picked_lab_pattern():
    """The whole path: forward model → ``pick_peaks`` → the gate, with a known
    specimen displacement injected so the screen has something to attribute."""
    from rietx import pick_peaks
    from tests.test_peak_picking import _forward, _instrument, _noisy

    instrument = _instrument()
    y_true, grid, truth = _forward(instrument, tt_lo=20.0, tt_hi=130.0)
    peaks = pick_peaks(_noisy(y_true, grid, 2026), instrument)

    matched, refs = [], []
    for p in peaks.usable():
        k = int(np.argmin(np.abs(truth - p.two_theta)))
        if abs(truth[k] - p.two_theta) < 0.5 * p.fwhm:
            matched.append(p)
            refs.append(truth[k])
    assert len(matched) >= 15

    tt = np.array([p.two_theta for p in matched])
    esd = np.array([p.two_theta_esd for p in matched])
    # inject a specimen displacement on top of the fitted positions
    injected = 0.05
    dev = injected * shift_template_basis(tt)["cos_theta"]
    screen = fit_shift_model(tt, dev + (tt - np.array(refs)), esd)
    assert screen.best == "cos_theta"
    assert screen.separable
    best = next(t for t in screen.templates if t.name == "cos_theta")
    assert best.coefficient == pytest.approx(injected, abs=5e-3)

    report = assess_peak_list(peaks)
    assert report.source == "fitted"
    assert report.sigma_two_theta_median < 0.01
    assert report.relative_sigma_q_median < MAX_RELATIVE_SIGMA_Q
    assert report.supports_indexing == (len(peaks.usable())
                                        >= PEAK_MIN_USABLE_LINES)
    assert quality_diagnostics(report, peaks)


# ----------------------------------------------------------------------
# WP-2030: the instrument lead reads the declared source
# ----------------------------------------------------------------------
def test_a_lab_source_is_read_off_the_declaration():
    from rietx import Instrument
    from rietx.indexing.diagnostics import lab_source

    assert lab_source(Instrument.bragg_brentano())                  # Cu Kα doublet
    assert lab_source(Instrument.bragg_brentano(radiation="MoKa1"))  # Kα1 alone
    assert lab_source(Instrument.debye_scherrer(wavelength=1.5405929))
    # a synchrotron line states no anode, and nor does a rounded one typed by hand
    assert not lab_source(Instrument.debye_scherrer(wavelength=0.4139090))
    assert not lab_source(Instrument.debye_scherrer(wavelength=1.5406))


def test_a_synchrotron_declaration_is_never_named_as_missing():
    """A correctly set-up synchrotron instrument has zero axial apertures and
    a narrow profile, the two defaults the lab lead names, so on such a source
    the lead would call a correct declaration missing (WP-1510's review)."""
    from rietx import Instrument

    coarse = _fitted(np.linspace(15.0, 130.0, 40), esd=0.5)
    sync = Instrument.debye_scherrer(wavelength=0.4139090)
    d = next(x for x in assess_peak_list(coarse, instrument=sync).diagnostics
             if x.code == "INDEX_DATA_INSUFFICIENT")
    assert d.suggestion.startswith("Extend the 2θ range")
    assert "instrument.profile" not in d.where


def test_the_list_records_what_it_was_picked_with():
    """``index_pattern(peaks)`` with no instrument is the documented two-step
    flow; the lead reaches it through the list's own record, which outranks an
    instrument handed in beside the list (WP-2030)."""
    from rietx import Instrument

    coarse = _fitted(np.linspace(15.0, 130.0, 40), esd=0.5)
    recorded = coarse.model_copy(update={"instrument_undeclared": {
        "instrument.profile": "instrument.profile is the default ProfileTCHZ"}})
    d = next(x for x in assess_peak_list(recorded).diagnostics
             if x.code == "INDEX_DATA_INSUFFICIENT")
    assert d.suggestion.startswith("Declare the instrument")
    assert "instrument.profile" in d.where

    # picked with everything declared: the record says so, and a bare
    # instrument handed in later does not override it
    clean = coarse.model_copy(update={"instrument_undeclared": {}})
    d = next(x for x in assess_peak_list(
        clean, instrument=Instrument.bragg_brentano()).diagnostics
        if x.code == "INDEX_DATA_INSUFFICIENT")
    assert d.suggestion.startswith("Extend the 2θ range")


def test_the_picker_writes_the_record():
    from pathlib import Path

    from rietx import Instrument
    from rietx.indexing import pick_peaks
    from rietx.io.readers import read_pattern

    data = read_pattern(Path(__file__).parent / "data" / "qarr" / "zincite.prn")
    data = data.model_copy(update={
        "two_theta": data.two_theta[:1500], "intensity": data.intensity[:1500],
        "sigma": None if data.sigma is None else data.sigma[:1500]})
    lab = pick_peaks(data, Instrument.bragg_brentano())
    assert set(lab.instrument_undeclared) == {"instrument.geometry",
                                              "instrument.profile"}
    sync = pick_peaks(data, Instrument.debye_scherrer(wavelength=1.5406))
    assert sync.instrument_undeclared == {}
    # a hand-built list has no picker, so no record
    assert PeakList.from_positions([20.0, 30.0], 1.5406).instrument_undeclared is None
