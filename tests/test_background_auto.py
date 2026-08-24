"""v0.2 background subsystem: diagnostics, auto-selection, P-spline
co-refinement, and the background↔structure correlation guardrail — plus
(WP-1055) the background evidence that guardrail now reaches the report by."""

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.background import (
    auto_background,
    diagnose,
    peak_mask,
    select_arpls_lambda,
    select_chebyshev_order,
)
from rietx.background.models import bspline_design_matrix, second_difference_matrix
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import BackgroundChebyshev, BackgroundPSpline
from tests.test_schemas import make_lab6

WAVELENGTH = 1.5405929


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _peaky_pattern(*, background, seed=5, lo=15.0, hi=110.0, step=0.02,
                   structure=None, instrument=None):
    """LaB6 pattern on a prescribed analytic background, Poisson-noised."""
    structure = structure or make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = instrument or rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    tt = np.arange(lo, hi, step)
    grid = rx.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + background(model.tt)
    rng = np.random.default_rng(seed)
    return rx.PatternData(two_theta=model.tt.tolist(),
                          intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def _flat_bkg(tt):
    return np.full_like(tt, 120.0)


def _air_scatter_bkg(tt):
    return 60.0 + 6000.0 / tt


def _hump_bkg(tt):
    return 80.0 + 400.0 * np.exp(-0.5 * ((tt - 32.0) / 7.0) ** 2)


# ----------------------------------------------------------------------
# diagnostics
# ----------------------------------------------------------------------
def test_diagnostics_flat_background():
    data = _peaky_pattern(background=_flat_bkg)
    d = diagnose(data, wavelength=WAVELENGTH)
    assert d.n_points == len(data.two_theta)
    assert d.n_peaks > 5
    assert 0.0 < d.peak_fraction < 0.5           # peaks are a minority of channels
    assert d.signal_to_background > 1.0
    assert d.air_scatter_gain < 0.3
    assert d.amorphous_hump_score < 0.05
    assert d.contamination == []                 # synthesized without Kβ/W


def test_diagnostics_detect_air_scatter_and_hump():
    """The two shape signatures must be separable, not just both 'nonzero':
    air scatter is explained by the 1/x column, a hump is not."""
    air = diagnose(_peaky_pattern(background=_air_scatter_bkg))
    hump = diagnose(_peaky_pattern(background=_hump_bkg))

    assert air.air_scatter_gain > 0.3
    assert air.amorphous_hump_score < 0.05       # 1/x explains it fully

    assert hump.amorphous_hump_score > 0.05
    assert hump.amorphous_hump_score > 10 * air.amorphous_hump_score


def _dope_ghost(data, lam_parent, lam_ghost, *, height=0.12):
    """Add a ghost of the strongest peak at a second wavelength's position."""
    from scipy.signal import find_peaks

    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    idx, _ = find_peaks(y, height=np.percentile(y, 99.5), distance=20)
    parent = tt[idx[np.argmax(y[idx])]]
    s = np.sin(np.radians(parent / 2.0)) * lam_ghost / lam_parent
    ghost = 2.0 * np.degrees(np.arcsin(s))
    y = y + height * y.max() * np.exp(-0.5 * ((tt - ghost) / 0.05) ** 2)
    return rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist()), ghost


def test_diagnostics_flag_kbeta_ghost():
    """Inject a Kβ ghost of the strongest LaB6 line and check it is flagged."""
    data = _peaky_pattern(background=_flat_bkg)
    doped, ghost = _dope_ghost(data, WAVELENGTH, 1.3922340)

    flags = diagnose(doped, wavelength=WAVELENGTH).contamination
    kb = [f for f in flags if f.kind == "kbeta" and abs(f.two_theta - ghost) < 0.2]
    assert kb, f"Kβ ghost at {ghost:.2f}° not flagged; got {flags}"


@pytest.mark.parametrize("anode", ["CrKa", "FeKa", "CoKa", "CuKa", "MoKa", "AgKa"])
def test_kbeta_check_follows_the_anode(anode):
    """The ghost sits at the *anode's* Kβ, so the check has to be per anode.

    Before WP-0507 this returned [] for anything but Cu — an empty list that
    reads as "clean".
    """
    from rietx.background.diagnostics import _KBETA

    ins = rx.Instrument.bragg_brentano(radiation=anode)
    lam = ins.source.lines[0].wavelength.value
    data = _peaky_pattern(background=_flat_bkg, instrument=ins, lo=5.0, hi=125.0)
    doped, ghost = _dope_ghost(data, lam, _KBETA[anode])

    flags = diagnose(doped, wavelength=lam).contamination
    kb = [f for f in flags if f.kind == "kbeta" and abs(f.two_theta - ghost) < 0.2]
    assert kb, f"{anode} Kβ ghost at {ghost:.2f}° not flagged; got {flags}"
    # and the *wrong* anode's Kβ is not what was matched
    other = _KBETA["CuKa" if anode != "CuKa" else "CoKa"]
    assert abs(ghost - 2.0 * np.degrees(np.arcsin(
        np.sin(np.radians(kb[0].parent_two_theta / 2.0)) * other / lam))) > 0.5


def test_tungsten_contamination_is_checked_off_cu():
    """W Lα1 comes off the filament, not the target, so it is anode-independent
    — unlike Kβ, which is why the two are looked up differently."""
    from rietx.background.diagnostics import _W_LA1

    ins = rx.Instrument.bragg_brentano(radiation="CoKa")
    lam = ins.source.lines[0].wavelength.value
    data = _peaky_pattern(background=_flat_bkg, instrument=ins, lo=25.0, hi=125.0)
    doped, ghost = _dope_ghost(data, lam, _W_LA1, height=0.05)

    flags = diagnose(doped, wavelength=lam).contamination
    w = [f for f in flags if f.kind == "tungsten_la" and abs(f.two_theta - ghost) < 0.2]
    assert w, f"W Lα1 ghost at {ghost:.2f}° not flagged; got {flags}"


def test_unknown_wavelength_is_not_checked_rather_than_clean():
    from rietx.background import identify_anode

    assert identify_anode(1.5405929) == "CuKa"
    assert identify_anode(1.788996) == "CoKa"
    assert identify_anode(0.4139090) is None      # 11-BM: no characteristic Kβ
    assert identify_anode(1.6) is None            # between Co and Fe, unclaimed

    data = _peaky_pattern(background=_flat_bkg)
    doped, _ = _dope_ghost(data, WAVELENGTH, 1.3922340)
    assert diagnose(doped, wavelength=0.4139090).contamination == []


# ----------------------------------------------------------------------
# auto-selection
# ----------------------------------------------------------------------
def test_peak_mask_keeps_background_channels():
    data = _peaky_pattern(background=_flat_bkg)
    tt, y, s = data.tt(), data.y(), data.sig()
    keep = peak_mask(tt, y, s)
    assert 0.5 < keep.mean() < 1.0
    # masked-out channels are the bright ones
    assert y[~keep].mean() > y[keep].mean()


def test_chebyshev_order_selection_flat_vs_structured():
    flat = select_chebyshev_order(_peaky_pattern(background=_flat_bkg))
    assert flat.method == "chebyshev_order"
    assert 2 <= flat.selected <= 6           # a constant needs almost nothing
    assert flat.n_masked_channels > 1000
    assert flat.scores

    humpy = select_chebyshev_order(_peaky_pattern(background=_hump_bkg))
    # a Gaussian hump needs genuinely more terms than a flat line
    assert humpy.selected > flat.selected


def test_chebyshev_selection_minimises_bic():
    sel = select_chebyshev_order(_peaky_pattern(background=_hump_bkg))
    assert sel.selected == min(sel.scores, key=lambda s: s.bic).complexity


def test_arpls_lambda_selection_returns_evidence():
    sel = select_arpls_lambda(_peaky_pattern(background=_hump_bkg))
    assert sel.method == "arpls_lambda"
    assert sel.selected in [10.0 ** e for e in range(4, 11)]
    assert sel.scores and all(s.durbin_watson >= 0 for s in sel.scores)


def test_auto_background_shapes_to_pattern():
    flat = auto_background(_peaky_pattern(background=_flat_bkg), wavelength=WAVELENGTH)
    assert isinstance(flat, BackgroundPSpline)
    assert flat.air_scatter.value == 0.0 and not flat.air_scatter.vary

    air = auto_background(_peaky_pattern(background=_air_scatter_bkg), wavelength=WAVELENGTH)
    assert air.air_scatter.vary, "1/x term should switch on for air scatter"

    cheb = auto_background(_peaky_pattern(background=_hump_bkg), kind="chebyshev")
    assert isinstance(cheb, BackgroundChebyshev)
    assert len(cheb.coefficients) >= 4


# ----------------------------------------------------------------------
# P-spline mechanics
# ----------------------------------------------------------------------
def test_bspline_partition_of_unity():
    tt = np.linspace(10.0, 90.0, 501)
    design = bspline_design_matrix(tt, np.linspace(10.0, 90.0, 17))
    np.testing.assert_allclose(design.sum(axis=0), 1.0, atol=1e-10)
    assert design.shape[0] == 17 + 2
    assert np.all(design >= -1e-12)


def test_pspline_schema_validates_coefficient_count():
    with pytest.raises(ValueError, match="coefficients"):
        BackgroundPSpline(breakpoints=[10.0, 20.0, 30.0],
                          coefficients=[rx.Parameter(value=0.0)] * 3)


def test_second_difference_matrix():
    d2 = second_difference_matrix(5)
    assert d2.shape == (3, 5)
    # annihilates constants and linear ramps, not curvature
    np.testing.assert_allclose(d2 @ np.ones(5), 0.0, atol=1e-12)
    np.testing.assert_allclose(d2 @ np.arange(5.0), 0.0, atol=1e-12)
    assert np.any(np.abs(d2 @ (np.arange(5.0) ** 2)) > 1.0)


def test_penalty_rows_enter_the_residual():
    data = _peaky_pattern(background=_flat_bkg)
    structure = make_lab6()
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.background = BackgroundPSpline.for_range(15.0, 110.0, knot_step_deg=10.0,
                                                 lambda_smooth=4.0)
    # a live air term, so its (softplus-transformed) column is exercised too
    ins.background.air_scatter = rx.Parameter(value=50.0, vary=True, min=0.0,
                                              transform="softplus")
    model = compile_model(structure, ins, data)
    table = ParameterTable(structure, ins)

    assert model.bkg_penalty is not None
    n_coef = len(ins.background.coefficients)
    assert model.bkg_penalty.shape == (n_coef - 2, n_coef + 1)  # +1: air column

    values = table.decode(table.x0())
    # zero coefficients → zero penalty; curvature → nonzero
    np.testing.assert_allclose(model.penalty_residual(values), 0.0, atol=1e-12)
    curved = dict(values)
    for n in range(n_coef):
        curved[f"instrument.background.c{n}"] = float(n) ** 2
    pen = model.penalty_residual(curved)
    np.testing.assert_allclose(pen, np.sqrt(4.0) * 2.0)  # D₂ of n² is 2

    from rietx.optimize.least_squares import _make_jacobian, _make_residual
    table.set_vary(["*"], False)
    table.set_vary(["instrument.background.*"], True)
    residual = _make_residual(model, table)
    theta = table.x0()
    r0 = residual(theta)
    assert len(r0) == len(model.tt) + n_coef - 2

    # background columns are exact (linear model + linear penalty) on both
    # blocks.  Compared against *central* differences: with |r| ~ 2e5 at peak
    # channels, forward differences at h ~ 1e-6 lose ~5e-5 to fp64
    # cancellation — larger than the quantity being checked.
    J = _make_jacobian(model, table)(theta)
    for c in range(len(theta)):
        h = 1e-4 * max(1.0, abs(theta[c]))
        e = np.zeros_like(theta)
        e[c] = h
        fd = (residual(theta + e) - residual(theta - e)) / (2.0 * h)
        np.testing.assert_allclose(J[:, c], fd, rtol=1e-5,
                                   atol=1e-6 * max(np.abs(fd).max(), 1e-12))


def test_pspline_refines_a_curved_background():
    """The co-refined penalized spline must follow a hump the Chebyshev
    default cannot, without eating the Bragg peaks."""
    data = _peaky_pattern(background=_hump_bkg, seed=9)
    structure = make_lab6()
    structure.phases[0].scale.value = 1.5e-4
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 2e-3
    ins.profile.x.value = 4e-3
    ins.background = auto_background(data, wavelength=WAVELENGTH)

    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(data, plan="lab_bragg_brentano")
    assert result.status == "converged"
    # Rwp bottoms out at the Poisson noise floor here (Rexp ≈ 0.078 on this
    # background-dominated pattern), so GoF is the meaningful criterion
    assert result.statistics.gof < 1.6
    assert result.statistics.rwp < 0.12

    # the fitted background must track the truth, not swallow peak area
    tt = np.asarray(result.two_theta)
    truth = _hump_bkg(tt)
    fitted = np.asarray(result.y_background)
    assert np.median(np.abs(fitted - truth)) < 0.12 * np.median(truth)
    # scale must survive: a background that ate the peaks would shrink it
    assert ref.fitted_structure.phases[0].scale.value == pytest.approx(3e-4, rel=0.25)


# ----------------------------------------------------------------------
# guardrail
# ----------------------------------------------------------------------
def _absorption_fit(background, *, broad=0.0):
    """The absorption setup, keeping the refinement so ``report()`` works.

    Same data every time (flat background, seed 4, 15-70°) so two backgrounds
    fitted to it are comparable channel for channel — which is what makes the
    WP-1055 Rwp inversion an inversion rather than two unrelated numbers.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    structure.phases[0].lor_size.value = broad
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    data = _peaky_pattern(background=_flat_bkg, lo=15.0, hi=70.0, seed=4,
                          structure=structure.model_copy(deep=True),
                          instrument=ins.model_copy(deep=True))
    ins.background = background
    plan = rx.RefinementPlan(stages=[
        rx.Stage("all", ["phases.*.scale", "instrument.background.c*",
                         "phases.*.atoms.*.biso"]),
    ])
    ref = rx.Refinement(structure, ins, history=False)
    return ref, ref.fit(data, plan=plan)


def _absorption_setup(background, *, broad=0.0):
    return _absorption_fit(background, broad=broad)[1]


def test_background_absorption_guard_fires_on_slack_background():
    """A 1°-knot *unpenalized* spline against broad peaks is the textbook
    degenerate case: locally flexible enough to imitate the peaks themselves.
    Pairwise ρ stays ~0.2 there (each of ~60 coefficients contributes little),
    so the guard must use the block-projection R² instead."""
    slack = BackgroundPSpline.for_range(15.0, 70.0, knot_step_deg=1.0,
                                        lambda_smooth=0.0)
    result = _absorption_setup(slack, broad=0.15)
    codes = {d.code for d in result.diagnostics}
    assert "BACKGROUND_ABSORPTION" in codes, f"guard silent; got {codes}"
    msg = next(d for d in result.diagnostics if d.code == "BACKGROUND_ABSORPTION")
    assert "biased" in (msg.suggestion or "")
    assert msg.where and msg.where[0].endswith((".biso", ".scale"))


def test_background_absorption_guard_silent_for_sane_backgrounds():
    for bkg in (BackgroundChebyshev.with_terms(6),
                BackgroundPSpline.for_range(15.0, 70.0, knot_step_deg=8.0,
                                            lambda_smooth=1.0)):
        result = _absorption_setup(bkg)
        codes = {d.code for d in result.diagnostics}
        assert "BACKGROUND_ABSORPTION" not in codes, f"false positive on {bkg.kind}"


def test_penalty_rows_suppress_absorption():
    """The smoothness penalty is what makes the spline unable to eat peaks —
    the whole reason it rides in the least squares rather than being a
    pre-subtracted curve.  Same knots, λ=0 vs λ=1e4."""
    from rietx.optimize.least_squares import run_least_squares
    from rietx.optimize.statistics import background_absorption

    def max_r2(lam):
        structure = make_lab6()
        structure.phases[0].scale.value = 3e-4
        structure.phases[0].lor_size.value = 0.15
        ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
        ins.profile.w.value = 3e-3
        ins.profile.x.value = 5e-3
        data = _peaky_pattern(background=_flat_bkg, lo=15.0, hi=70.0, seed=4,
                              structure=structure.model_copy(deep=True),
                              instrument=ins.model_copy(deep=True))
        ins.background = BackgroundPSpline.for_range(15.0, 70.0, knot_step_deg=1.0,
                                                     lambda_smooth=lam)
        table = ParameterTable(structure, ins)
        table.set_vary(["*"], False)
        table.set_vary(["phases.*.scale", "instrument.background.c*",
                        "phases.*.atoms.*.biso"], True)
        model = compile_model(structure, ins, data, moving_paths=set(table.moving_paths))
        outcome = run_least_squares(model, table)
        return max(background_absorption(outcome.jac, table.free_paths).values())

    unpenalized, penalized = max_r2(0.0), max_r2(1e4)
    assert unpenalized > 0.3, f"expected a degenerate case, got R²={unpenalized:.3f}"
    assert penalized < 0.15, f"penalty failed to suppress absorption (R²={penalized:.3f})"
    assert penalized < 0.4 * unpenalized


# ----------------------------------------------------------------------
# WP-1055 — background evidence in the FitReport
# ----------------------------------------------------------------------
_OUT = Path(__file__).parent / "output"

_SLACK = BackgroundPSpline.for_range(15.0, 70.0, knot_step_deg=1.0,
                                     lambda_smooth=0.0)


def _plot(result, stem):
    """obs/calc/diff PNGs to tests/output/ (gitignored), full range + a
    low-angle zoom — house convention: Rwp hides locally-bad fits."""
    from rietx.viz.plots import plot_result

    _OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(_OUT / f"{stem}.png"))
    plot_result(result, path=str(_OUT / f"{stem}_zoom.png"),
                two_theta_range=(15.0, 40.0))


def _biso_rms_error(result, truth=0.5):
    b = [p.value for p in result.parameters if p.path.endswith(".biso")]
    return float(np.sqrt(np.mean([(v - truth) ** 2 for v in b])))


def test_over_flexible_background_is_flagged_while_rwp_improves():
    """The pinned inversion, and the reason this section exists.

    Two backgrounds over the *same* broad-peak data, both converged.  The
    1°-knot unpenalized spline wins on Rwp **and** GoF and is 2.6× further
    from the truth (measured 2026-08-12: Rwp 0.08852 vs 0.08969, GoF 1.022 vs
    1.025, Biso 0.958/0.000 vs 0.691/0.327 against a truth of 0.5/0.5, RMS
    error 0.480 vs 0.182 — with one displacement parameter driven onto its
    bound).  Every statistic an agent reads says the wrong fit is the better
    one; only the projection says otherwise, which is the v0.5 rule that a
    correction's evidence is never an Rwp comparison.
    """
    from rietx.report.schemas import BACKGROUND_ABSORPTION_NOTABLE

    slack_ref, slack = _absorption_fit(_SLACK, broad=0.15)
    ref_ref, reference = _absorption_fit(BackgroundChebyshev.with_terms(6),
                                         broad=0.15)

    assert slack.statistics.rwp < reference.statistics.rwp, (
        f"the inversion is the test: {slack.statistics.rwp:.5f} vs "
        f"{reference.statistics.rwp:.5f}")
    assert slack.statistics.gof < reference.statistics.gof
    assert _biso_rms_error(slack) > 2 * _biso_rms_error(reference), (
        _biso_rms_error(slack), _biso_rms_error(reference))

    bg = slack_ref.report().background
    assert bg is not None and bg.absorption
    assert bg.worst_absorption > BACKGROUND_ABSORPTION_NOTABLE, bg
    assert bg.worst_absorption_path.endswith((".biso", ".scale"))
    # the section is evidence: every screened pair travels, not just the fired
    assert len(bg.absorption) > 1
    assert bg.worst_absorption == max(bg.absorption.values())

    report = slack_ref.report()
    assert "block projection R²" in report.summary
    action = report.action("decrease_background_flexibility")
    assert action.active and action.confidence == pytest.approx(
        bg.worst_absorption, abs=1e-3)
    assert "biases" in action.rationale and "QPA" in action.rationale
    # not a stage: the paths would be the background's own, which every plan
    # already frees — the veto would grey it out for the wrong reason
    assert action.parameter_paths == []

    # and the correct background says nothing at all
    good = ref_ref.report()
    assert good.background.worst_absorption < BACKGROUND_ABSORPTION_NOTABLE
    assert "block projection R²" not in good.summary
    assert [a.kind for a in good.suggested_actions
            if a.kind.endswith("_background_flexibility")] == []

    _plot(slack, "wp1055_over_flexible")
    _plot(reference, "wp1055_over_flexible_reference")


def test_stiff_background_reports_the_misfit_between_the_peaks():
    """The other direction, structurally invisible before this section.

    A Gaussian hump fitted with a 2-term Chebyshev.  Layer 0's regions are
    peak clusters, so between-peak misfit lands in no region entry and its
    only prior trace was the unexplained remainder of "top 15 regions carry
    X %".  Measured 2026-08-12: off-region χ²_red 12.6 over 3164 channels at
    Durbin-Watson d 0.19, against 0.97/2.00 on the converged control — while
    the block absorption reads 0.02, i.e. the two failure modes do not
    contaminate each other's statistic.
    """
    from rietx.report.schemas import OFF_REGION_CHI2_RED_HIGH, OFF_REGION_DW_LOW

    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    ins.background = BackgroundChebyshev.with_terms(2)
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(_peaky_pattern(background=_hump_bkg, seed=9),
                     plan=rx.RefinementPlan(stages=[rx.Stage(
                         "all", ["phases.*.scale", "instrument.background.c*",
                                 "phases.*.atoms.*.biso"])]))
    report = ref.report()
    bg = report.background

    assert bg.off_region_chi2_reduced > 4 * OFF_REGION_CHI2_RED_HIGH, bg
    assert bg.off_region_durbin_watson < 0.5 * OFF_REGION_DW_LOW, bg
    assert bg.off_region_points > 1000
    # the absorption statistic must stay quiet: this background is too stiff
    # to imitate anything, which is the whole point of measuring both
    assert bg.worst_absorption < 0.1, bg

    assert "systematic, not noise" in report.summary
    action = report.action("increase_background_flexibility")
    assert action.active and 0.0 < action.confidence <= 0.6
    assert "amorphous hump" in action.rationale
    assert "add_impurity_phase" in action.alternatives
    assert action.parameter_paths == []

    # the rival, both ways: a residual running this high clears the 5σ peak
    # floor on noise alone, so the impurity call must name the background
    impurity = report.action("add_impurity_phase")
    assert "increase_background_flexibility" in impurity.alternatives
    assert "between-peak shape" in impurity.rationale

    _plot(result, "wp1055_too_stiff")


def test_background_pair_is_published_and_never_a_summary_trigger():
    """The pair is context, and the measurement says it cannot be more.

    Every background-dominated pattern crosses any useful threshold on it —
    measured, a *converged* clean lab fit reads background share 0.93 and
    background-subtracted Rwp 3.9× the raw one — so a summary trigger there
    would be a sentence on every lab fit.  It is published unconditionally
    and quoted nowhere in the summary.
    """
    ref, result = _absorption_fit(BackgroundChebyshev.with_terms(6))
    bg = ref.report().background

    assert bg.rwp == pytest.approx(result.statistics.rwp)
    assert bg.rwp_background_subtracted == pytest.approx(
        result.statistics.rwp_background_subtracted)
    assert bg.rwp_background_subtracted > 2 * bg.rwp, bg
    assert 0.5 < bg.background_share < 1.0, bg

    summary = ref.report().summary
    assert "background-subtracted" not in summary
    assert "flattered" not in summary
    # and the share of χ² between the peaks: published, and *not* a detector —
    # on a converged fit most channels are off-region, so it reads high
    assert bg.off_region_chi2_share > 0.5, bg
    assert bg.off_region_chi2_reduced == pytest.approx(1.0, abs=0.3), bg


def test_off_region_durbin_watson_is_pooled_within_runs():
    """Never differenced across an excised peak region.

    Two off-region runs of a perfectly smooth ramp, with a large jump between
    them where the peak region was cut out.  Bridging the gap would add that
    one jump to the numerator and report the residual as far less correlated
    than it is; pooling within runs sees only the ramp.
    """
    from rietx.report.background import _pooled_durbin_watson

    delta = np.concatenate([np.arange(1.0, 6.0), np.full(4, 0.0),
                            np.arange(101.0, 106.0)])
    mask = np.zeros(delta.size, dtype=bool)
    mask[:5] = mask[9:] = True

    d, n_pairs = _pooled_durbin_watson(delta, mask)
    assert n_pairs == 8                       # 4 + 4, never the bridging pair
    denom = float(delta[mask] @ delta[mask])
    assert d == pytest.approx(8.0 / denom)    # eight unit steps, no jump
    bridged = float(np.diff(delta[mask]) @ np.diff(delta[mask])) / denom
    assert bridged > 100 * d, "the bridging pair would dominate"

    # too few adjacent channels to difference is None, not a fabricated 2.0
    lone = np.zeros(delta.size, dtype=bool)
    lone[0] = lone[6] = True
    assert _pooled_durbin_watson(delta, lone)[0] is None


def test_identifiability_carries_the_quiet_measurements_too():
    """A fired/not-fired bit is a verdict; 0.46-against-0.08 is evidence.

    The sane background trips no guard, and the same numbers the guard
    screened must still reach the result — otherwise a consumer cannot tell
    "measured and fine" from "never measured", which is exactly the
    distinction ``Identifiability = None`` is reserved for.
    """
    from rietx.strategy.staged import BACKGROUND_ABSORPTION_GUARD

    result = _absorption_setup(BackgroundChebyshev.with_terms(6))
    assert "BACKGROUND_ABSORPTION" not in {d.code for d in result.diagnostics}

    ident = result.identifiability
    assert ident is not None and ident.background_absorption
    assert all(r2 <= BACKGROUND_ABSORPTION_GUARD
               for r2 in ident.background_absorption.values()), ident
    assert any(p.endswith(".scale") for p in ident.background_absorption)

    # and it survives the JSON round trip the agent surface takes
    from rietx.schemas.results import RefinementResult
    back = RefinementResult.model_validate_json(result.model_dump_json())
    assert back.identifiability.background_absorption == \
        ident.background_absorption
