"""WP-1018 — peak picking, and above all the **σ pull calibration**.

The gate this file exists for is :func:`test_sigma_pull_calibration`: every
tolerance the indexing engines will use is a multiple of the σ(2θ) that
``pick_peaks`` reports, so a σ of the wrong *scale* silently mis-weights every
line downstream.  A pull ensemble is the only way to check it — fit many noise
realisations of a pattern whose peak positions are known exactly, and ask
whether ``(2θ_fit − 2θ_true)/σ_fit`` is a standard normal.  Rwp, χ² and eyeball
overlays cannot see a σ that is uniformly 40 % too small.

The truth in that ensemble comes from **the package's own forward model** rather
than from the fitter's, which is the whole point: ``compile_model`` puts each
emission line at its own Bragg angle with its own Lorentz-polarisation factor,
its own Caglioti width and its own FCJ smear, and the group fitter shares one
width across the pair, ties the Kα2 amplitude to the Kα1 one, and holds the
background at a rolling low quantile.  Every one of those is an approximation the
pull test prices.

The rest of the file is one test per defect this WP found by running it (see the
WP handover log), because none of the five was visible by reading the code.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rietx import Instrument, PatternData, pick_peaks
from rietx.crystallography.lattice import d_spacings
from rietx.indexing.diagnostics import peak_diagnostics
from rietx.indexing.peakfit import GroupFit, _fit_at, _GroupModel, fit_group
from rietx.indexing.peaks import (
    Detection,
    PeakGroup,
    _debiased_envelope,
    _secondary_line_two_theta,
    detect_peaks,
    predicted_fwhm,
)
from rietx.indexing.pick import _not_separable
from rietx.model.corrections import lorentz_polarization
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.indexing import (
    PEAK_ASSUMED_ESD_DEG,
    PEAK_MIN_USABLE_LINES,
    PEAK_UNUSABLE_FLAGS,
    ObservedPeak,
    PeakList,
    q_esd_of_two_theta,
    q_of_two_theta,
)
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_schemas import make_lab6

OUT = __import__("pathlib").Path(__file__).parent / "output"

TT_LO, TT_HI, STEP = 20.0, 90.0, 0.02
#: Lab profile coefficients: FWHM ≈ 0.076-0.14° over the range.  Not the
#: ``ProfileTCHZ`` default, which is a *synchrotron* line (W = 1e-3 deg², FWHM ≈
#: 0.03°) and is wrong on lab data by an order of magnitude (WP-1028).
LAB_UVWXY = dict(u=0.004, v=-0.002, w=0.004, x=0.02, y=0.0)


# ----------------------------------------------------------------------
# Synthetic patterns from the package's own forward model
# ----------------------------------------------------------------------
def _instrument(radiation: str = "CuKa", *, synchrotron: bool = False,
                axial: tuple[float, float] = (0.0, 0.0)) -> Instrument:
    if synchrotron:
        ins = Instrument.debye_scherrer(wavelength=1.5405929)
    else:
        ins = Instrument.bragg_brentano(radiation=radiation)
    for name, value in LAB_UVWXY.items():
        getattr(ins.profile, name).value = value
    ins.geometry.axial_sl.value, ins.geometry.axial_hl.value = axial
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (200.0, -20.0, 5.0)])
    return ins


def _forward(instrument: Instrument, *, scale: float = 3e-3,
             tt_lo: float = TT_LO, tt_hi: float = TT_HI):
    """(noise-free counts, grid, true Kα1 positions) for a LaB6 pattern.

    The positions are Bragg's law on the *same* cell the forward model compiled,
    with no zero shift or displacement declared, so they are exact rather than
    fitted — which is what a pull ensemble needs.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = scale
    tt = np.arange(tt_lo, tt_hi, STEP)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))

    ph = structure.phases[0]
    cell = (ph.cell.a.value, ph.cell.b.value, ph.cell.c.value,
            ph.cell.alpha.value, ph.cell.beta.value, ph.cell.gamma.value)
    d = d_spacings(model.phases[0].reflections.hkl, *cell)
    s = instrument.source.lines[0].wavelength.value / (2.0 * d)
    truth = 2.0 * np.degrees(np.arcsin(s[s < 1.0]))
    truth = np.sort(truth[(truth > tt_lo + 0.5) & (truth < tt_hi - 0.5)])
    # distinct reflections may share a d (cubic 300/221) — one peak, one truth
    truth = truth[np.concatenate([[True], np.diff(truth) > 1e-6])]
    return y, np.asarray(model.tt), truth


def _noisy(y_true: np.ndarray, grid: np.ndarray, seed: int) -> PatternData:
    rng = np.random.default_rng(seed)
    y = rng.poisson(np.maximum(y_true, 1.0)).astype(float)
    return PatternData(two_theta=grid.tolist(), intensity=y.tolist())


def _pulls(instrument: Instrument, y_true, grid, truth, seeds) -> dict:
    """Fit every seed's realisation and collect the position pulls."""
    pull, matched, extra = [], [], 0
    for seed in seeds:
        obs = pick_peaks(_noisy(y_true, grid, seed), instrument).usable()
        found = 0
        for p in obs:
            k = int(np.argmin(np.abs(truth - p.two_theta)))
            if abs(truth[k] - p.two_theta) < 0.5 * p.fwhm and p.two_theta_esd > 0:
                pull.append((p.two_theta - truth[k]) / p.two_theta_esd)
                found += 1
            else:
                extra += 1
        matched.append(found)
    a = np.array(pull)
    return {"pull": a, "mean": float(a.mean()), "std": float(a.std(ddof=1)),
            "n": len(a), "per_pattern": float(np.mean(matched)), "extra": extra}


# ----------------------------------------------------------------------
# The gate
# ----------------------------------------------------------------------
#: Noise realisations per configuration.  The WP asked for 200 groups, which is
#: ample for the ``std`` bar and **not enough for the mean one**: with a pull std
#: of 1 the standard error of the mean over 200 groups is 0.07, half the 0.15 bar
#: itself, so a 200-group subsample of this very ensemble wanders to -0.15 while
#: the converged value is -0.08.  100 patterns × 13 reflections puts the standard
#: error at 0.03, and :func:`test_sigma_pull_calibration` asserts that margin
#: rather than trusting it — a bar within noise of the estimate is not a gate.
PULL_PATTERNS = 100


@pytest.mark.parametrize("label,instrument", [
    # A single emission line prices the estimator, the window truncation and the
    # frozen background.  Measured: +0.03.
    ("synchrotron", _instrument(synchrotron=True)),
    # The Cu Kα doublet prices the constrained pair on top, and it is the case
    # that carries a residual bias: -0.08 ± 0.03, i.e. 2e-5° — a fortieth of a
    # channel, 1/4000 of a FWHM.  Four candidate mechanisms were measured and
    # *excluded*: the rolling-quantile background (handing the fit the exact
    # background moves it by 0.02), the neighbours' unmodelled tails (cropping to
    # one isolated reflection keeps it), the per-line Caglioti width the fitter
    # shares (generating truth with per-line widths changes nothing), and the
    # Poisson weight taken from the noisy data rather than the model (nothing).
    # In isolation — exact background, exact seed — the same doublet fit is
    # unbiased to ±0.02 over 400 realisations, so what is left is in the
    # detection-seeded window, not in the estimator.
    ("lab Cu Kα doublet", _instrument()),
])
def test_sigma_pull_calibration(label, instrument):
    """**The gate the whole downstream tolerance model rests on.**

    ~1300 fitted lines per configuration, from fixed-seed Poisson realisations of
    a forward-model LaB6 pattern.  ``std`` is the calibration proper: it is the
    ratio of the *actual* scatter of the position estimator to the σ this package
    reports, so 1.0 means a "2σ" statement downstream really is one.
    """
    mean_bar = 0.15                 # WP-1018's pre-measurement prediction
    y_true, grid, truth = _forward(instrument)
    got = _pulls(instrument, y_true, grid, truth,
                 range(1000, 1000 + PULL_PATTERNS))

    assert got["n"] >= 200, f"{label}: only {got['n']} matched lines"
    se = got["std"] / np.sqrt(got["n"])
    assert 3.0 * se < mean_bar, (
        f"{label}: standard error of the mean pull is {se:.3f}, so a "
        f"{mean_bar} bar cannot distinguish a bias from sampling — raise "
        "PULL_PATTERNS rather than the bar")
    assert got["per_pattern"] >= 0.9 * len(truth), (
        f"{label}: {got['per_pattern']:.1f} of {len(truth)} reflections found "
        "per pattern — detection is losing lines, so the pull ensemble is "
        "conditioned on the easy ones")
    assert abs(got["mean"]) < mean_bar, (
        f"{label}: mean pull {got['mean']:+.3f} — a *bias*, which no amount of "
        "counting removes and which σ cannot report")
    assert 0.85 <= got["std"] <= 1.20, (
        f"{label}: pull std {got['std']:.3f} — the reported σ(2θ) is "
        f"{'optimistic' if got['std'] > 1.2 else 'pessimistic'} by "
        f"{abs(got['std'] - 1.0) * 100:.0f} %, so every tolerance downstream is "
        "mis-scaled by the same factor")


def test_pull_calibration_writes_overlays():
    """Per-group overlays to ``tests/output/`` — Rwp hides locally-bad fits, and
    a pull statistic hides a group that fitted the wrong feature."""
    import matplotlib.pyplot as plt

    instrument = _instrument()
    y_true, grid, truth = _forward(instrument)
    data = _noisy(y_true, grid, 1000)
    det = detect_peaks(data, instrument)
    peaks = pick_peaks(data, instrument)

    OUT.mkdir(exist_ok=True)
    n = min(6, len(det.groups))
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, group in zip(np.ravel(axes)[:n], det.groups[:n]):
        s = slice(group.i0, group.i1)
        x = det.two_theta[s]
        ax.plot(x, det.intensity[s], "k.", ms=3, label="obs")
        ax.plot(x, det.envelope[s], "g-", lw=0.8, label="frozen background")
        m = _GroupModel(det, group, instrument, group.n, group.seed_fwhm)
        m.freeze(group.seed_two_theta)
        fit = _fit_at(det, group, instrument, group.seed_two_theta)
        if fit.n:
            p = m.pack(fit.gamma_g, fit.gamma_l, fit.two_theta, fit.intensity)
            ax.plot(x, det.envelope[s] + m.model(p), "r-", lw=1.0, label="calc")
            for tt in fit.two_theta:
                ax.axvline(tt, color="r", ls=":", lw=0.8)
        for tt in truth[(truth > x[0]) & (truth < x[-1])]:
            ax.axvline(tt, color="b", ls="--", lw=0.8)
        ax.set_title(f"group {group.n} comp, χ²_red {fit.chi2_red:.2f}",
                     fontsize=9)
        ax.set_xlabel("2θ (°)")
    fig.suptitle("WP-1018 per-group fits — blue dashed = forward-model truth")
    fig.tight_layout()
    fig.savefig(OUT / "peak_picking_groups.png", dpi=110)

    fig2, ax = plt.subplots(figsize=(11, 4))
    ax.plot(det.two_theta, det.intensity, "k-", lw=0.5, label="obs")
    ax.plot(det.two_theta, det.envelope, "g-", lw=0.8, label="envelope")
    for p in peaks.usable():
        ax.axvline(p.two_theta, color="r", ls=":", lw=0.6)
    ax.set_yscale("log")
    ax.set_xlabel("2θ (°)")
    ax.set_title(f"{len(peaks.usable())} usable lines of {len(truth)} "
                 "reflections; red = fitted positions")
    ax.legend(fontsize=8)
    fig2.tight_layout()
    fig2.savefig(OUT / "peak_picking_pattern.png", dpi=110)
    assert (OUT / "peak_picking_groups.png").exists()


# ----------------------------------------------------------------------
# The analytic group Jacobian
# ----------------------------------------------------------------------
def _fd_jacobian(m: _GroupModel, p: np.ndarray) -> np.ndarray:
    """Central differences on the residual, with a per-parameter step."""
    out = np.zeros((len(m.x), len(p)))
    for k in range(len(p)):
        h = 1e-6 * max(abs(p[k]), 1.0)
        lo, hi = p.copy(), p.copy()
        lo[k] -= h
        hi[k] += h
        out[:, k] = (m.residual(hi) - m.residual(lo)) / (2.0 * h)
    return out


def _toy_group(instrument: Instrument, positions, fwhm=0.09, area=2.0e4,
               bkg=200.0):
    """A synthetic window and the group model over it, no detection involved."""
    x = np.arange(min(positions) - 5 * fwhm, max(positions) + 5 * fwhm, STEP)
    env = np.full_like(x, bkg)
    grp = PeakGroup(i0=0, i1=len(x), seed_two_theta=np.asarray(positions,
                                                              dtype=float),
                    seed_fwhm=fwhm,
                    from_shoulder=np.zeros(len(positions), dtype=bool))
    det = Detection(x, env.copy(), np.sqrt(env), env, [grp], fwhm, fwhm, 1.0, 0,
                    np.zeros(0))
    m = _GroupModel(det, grp, instrument, len(positions), fwhm)
    m.freeze(np.asarray(positions, dtype=float))
    p = m.pack(0.8 * fwhm, 0.2 * fwhm, np.asarray(positions, dtype=float),
               np.full(len(positions), area))
    det.intensity[:] = env + m.model(p)
    det.sigma[:] = np.sqrt(np.maximum(det.intensity, 1.0))
    return det, grp, m, p


@pytest.mark.parametrize("label,instrument,positions", [
    ("synchrotron single line", _instrument(synchrotron=True), [40.0]),
    ("lab doublet", _instrument(), [40.0]),
    ("symmetric FCJ", _instrument(axial=(0.02, 0.02)), [30.0]),
    # S/L == H/L is a genuine corner of the FCJ profile (WP-0601), so the
    # asymmetric case is the one that exercises the general branch
    ("asymmetric FCJ", _instrument(axial=(0.03, 0.01)), [30.0]),
    ("overlapping pair", _instrument(), [40.0, 40.06]),
    ("true Voigt", _instrument(), [40.0]),
])
def test_group_jacobian_matches_finite_differences(label, instrument, positions):
    """Analytic Jacobian against central differences, column by column.

    Covers both cheap scalar finite differences the fitter takes on purpose (the
    (Γ_G, Γ_L) → (w₁, w₂) width map and the FCJ node vectors' motion with
    position) and the emission-line chain d(2θ_l)/d(2θ₀).
    """
    if label == "true Voigt":
        instrument = instrument.model_copy(deep=True)
        instrument.profile.shape = "voigt"
    _det, _grp, m, p = _toy_group(instrument, positions)
    ana, fd = m.jacobian(p), _fd_jacobian(m, p)
    scale = np.maximum(np.abs(fd).max(axis=0), 1e-12)
    err = np.abs(ana - fd).max(axis=0) / scale
    assert err.max() < 5e-5, f"{label}: worst column {err.argmax()} off {err.max():.2e}"


def test_recovered_positions_and_esds_on_a_clean_group():
    """A noiseless group fits its own truth to well inside a channel."""
    instrument = _instrument()
    det, grp, _m, _p = _toy_group(instrument, [40.0])
    fit = _fit_at(det, grp, instrument, np.array([40.02]))   # seeded off-truth
    assert fit.converged
    assert fit.two_theta[0] == pytest.approx(40.0, abs=1e-4)
    assert not fit.at_bound[0]


# ----------------------------------------------------------------------
# The doublet is a constrained pair: the reported position is Kα1
# ----------------------------------------------------------------------
def test_fitted_position_is_the_kalpha1_position():
    """Not the doublet centroid, which is the number a stripping method reports.

    The centroid of a Cu Kα pair sits ``weight/(1+weight)`` of the split above
    Kα1 — 0.026° at 30°, some 40σ on these lines — so the two answers are not
    within noise of each other, which is why this is a property test and not a
    tolerance.
    """
    instrument = _instrument()
    y_true, grid, truth = _forward(instrument)
    peaks = pick_peaks(_noisy(y_true, grid, 4242), instrument)
    lam = [ln.wavelength.value for ln in instrument.source.lines]
    w = instrument.source.lines[1].weight.value

    n_checked = 0
    for p in peaks.usable():
        k = int(np.argmin(np.abs(truth - p.two_theta)))
        if abs(truth[k] - p.two_theta) > 0.5 * p.fwhm:
            continue
        tt2 = float(_secondary_line_two_theta(np.array([truth[k]]), instrument)[0, 0])
        centroid = (truth[k] + w * tt2) / (1.0 + w)
        assert abs(p.two_theta - truth[k]) < 6.0 * p.two_theta_esd
        assert abs(p.two_theta - centroid) > 3.0 * p.two_theta_esd
        n_checked += 1
    assert n_checked >= 10
    assert lam[1] > lam[0]      # the alias is above its parent, always


def test_doublet_amplitude_carries_the_lorentz_polarization_ratio():
    """The held ratio is ``weight × Lp(2θ_Kα2)/Lp(2θ_Kα1)``, not ``weight``.

    Each line diffracts at its own Bragg angle, so it carries its own Lp — the
    forward model's own per-line treatment.  Ignoring it biased the fitted Kα1
    position by −2e-4° and the mean σ pull by −0.07 (WP-1018).
    """
    instrument = _instrument()
    _det, _grp, m, _p = _toy_group(instrument, [30.4])
    tt2 = float(_secondary_line_two_theta(np.array([30.4]), instrument)[0, 0])
    lp = lorentz_polarization(np.array([tt2, 30.4]),
                              instrument.source.polarization.value)
    want = instrument.source.lines[1].weight.value * float(lp[0] / lp[1])
    assert m.line_gain[0, 0] == 1.0                  # primary line is the unit
    assert m.line_gain[0, 1] == pytest.approx(want, rel=1e-12)
    assert m.line_gain[0, 1] < instrument.source.lines[1].weight.value


# ----------------------------------------------------------------------
# One test per defect found by running it
# ----------------------------------------------------------------------
def test_resolved_doublet_does_not_manufacture_lines():
    """Defect 1: at high angle the Kα2 *maximum* is its own detection.

    Each group is fitted independently *with its own full doublet*, so a
    surviving Kα2 detection comes back as a real line with real intensity.  The
    count is the assertion: one usable line per reflection, no more.
    """
    instrument = _instrument()
    y_true, grid, truth = _forward(instrument)
    data = _noisy(y_true, grid, 7)
    det = detect_peaks(data, instrument)
    peaks = pick_peaks(data, instrument)

    assert len(det.alias_two_theta) >= 8, "no Kα2 aliases recognised at all"
    assert len(peaks.usable()) <= len(truth) + 1
    codes = {d.code for d in peaks.diagnostics}
    assert "PEAK_KALPHA2_ALIAS" in codes
    # and the aliases really are at the predicted Kα2 positions
    pred = _secondary_line_two_theta(truth, instrument).ravel()
    for tt in det.alias_two_theta:
        assert np.min(np.abs(pred - tt)) < 0.05


def test_unresolved_kalpha2_shoulder_is_not_a_line():
    """Defect 5: the *unresolved* half of defect 1, and it is worse.

    Where the split is close to a FWHM the Kα2 has no maximum of its own, so the
    alias filter cannot see it — but it does have a curvature shoulder, which
    cleared the 5σ seeder, landed *outside* the half-FWHM grouping gap, formed a
    **singleton** group of its own, and came back as a line with an esd.  ΔBIC
    could not refuse it: a singleton is judged against "no peak at all", and
    there genuinely is intensity there.  Measured on the LaB6 110 line at
    30.387° (split 0.0775° against a 0.082° FWHM), it produced one extra line
    per pattern at ~30.46° and a −21 mean σ pull on that reflection.
    """
    instrument = _instrument()
    y_true, grid, truth = _forward(instrument, tt_lo=29.0, tt_hi=32.0)
    assert len(truth) == 1
    tt2 = float(_secondary_line_two_theta(truth, instrument)[0, 0])

    for seed in range(1000, 1006):
        data = _noisy(y_true, grid, seed)
        peaks = pick_peaks(data, instrument, two_theta_range=(29.0, 32.0))
        usable = peaks.usable()
        assert len(usable) == 1, (
            f"seed {seed}: {[round(p.two_theta, 3) for p in usable]} — the Kα2 "
            f"shoulder at {tt2:.3f}° came back as a line")
        assert usable[0].two_theta == pytest.approx(float(truth[0]), abs=2e-3)

    # with shoulders switched off entirely the answer must be the same line
    off = pick_peaks(_noisy(y_true, grid, 1000), instrument, shoulders=False,
                     two_theta_range=(29.0, 32.0))
    assert len(off.usable()) == 1


def test_shoulder_seeder_threshold_is_the_filters_own_noise():
    """Defect 2: differentiating twice amplifies white noise by ~1/step².

    A threshold written against the per-channel σ passed essentially every noise
    dip (hundreds of seeds on a three-peak pattern).  The Savitzky-Golay
    coefficient norm is the right noise scale, and on pure background the seeder
    must return nothing at all.
    """
    instrument = _instrument()
    tt = np.arange(20.0, 60.0, STEP)
    rng = np.random.default_rng(3)
    y = rng.poisson(np.full_like(tt, 400.0)).astype(float)
    data = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    det = detect_peaks(data, instrument)
    assert det.n_shoulder_seeds == 0, (
        f"{det.n_shoulder_seeds} curvature seeds on pure Poisson background")
    assert len(pick_peaks(data, instrument).usable()) == 0


def test_background_envelope_debias_is_unbiased_on_flat_counts():
    """Defect 4: ``background_envelope`` is a rolling *low* quantile.

    It sits ≈1.28σ below the mean for flat Poisson counts, which turns a nominal
    5σ detection threshold into ≈3.7σ.  The debiased envelope must land on the
    true level to a fraction of σ — and it is the envelope, not just ``net``,
    that has to be corrected, because the envelope is also the fitter's
    additively-held background.
    """
    tt = np.arange(20.0, 60.0, STEP)
    rng = np.random.default_rng(11)
    level = 400.0
    y = rng.poisson(np.full_like(tt, level)).astype(float)

    from rietx.background import background_envelope
    raw = background_envelope(tt, y)
    fixed = _debiased_envelope(tt, y)
    sigma = np.sqrt(level)

    assert (level - float(np.median(raw))) / sigma > 0.8       # biased low
    assert abs(float(np.median(fixed)) - level) < 0.2 * sigma  # and corrected


def test_singleton_shoulder_must_earn_its_parameters():
    """Defect 3: a shoulder seed that lands alone faced no test at all.

    ``_prune_shoulders`` must reject a component seeded on a feature that is not
    there, against the no-peak-at-all hypothesis.
    """

    instrument = _instrument()
    fwhm = 0.09
    x = np.arange(39.0, 41.0, STEP)
    env = np.full_like(x, 400.0)
    rng = np.random.default_rng(5)
    y = rng.poisson(env).astype(float)          # background only
    grp = PeakGroup(i0=0, i1=len(x), seed_two_theta=np.array([40.0]),
                    seed_fwhm=fwhm, from_shoulder=np.array([True]))
    det = Detection(x, y, np.sqrt(np.maximum(y, 1.0)),
                    _debiased_envelope(x, y), [grp], fwhm, fwhm, 1.0, 1,
                    np.zeros(0))
    assert fit_group(det, grp, instrument).n == 0

    # a real line at the same place, seeded the same way, survives
    det2, grp2, _m, _p = _toy_group(instrument, [40.0])
    grp2.from_shoulder[:] = True
    assert fit_group(det2, grp2, instrument).n == 1


# ----------------------------------------------------------------------
# Q propagation, `from_positions`, and the list-level diagnostics
# ----------------------------------------------------------------------
def test_q_esd_matches_a_central_difference():
    """σ(Q) is the exact derivative — the π/90 the docstring warns about.

    Half of that constant is the θ = (2θ)/2 chain and half the degree
    conversion, and applying only one of the two is a factor-of-two error in
    every downstream weight.
    """
    lam = 1.5405929
    tt = np.array([5.0, 20.0, 47.3, 90.0, 140.0])
    h = 1e-6
    fd = (q_of_two_theta(tt + h, lam) - q_of_two_theta(tt - h, lam)) / (2 * h)
    got = q_esd_of_two_theta(tt, np.ones_like(tt), lam)
    assert np.allclose(got, np.abs(fd), rtol=1e-7)


@settings(max_examples=40, deadline=None)
@given(st.lists(st.floats(min_value=5.0, max_value=150.0), min_size=1,
                max_size=30, unique_by=lambda v: round(v, 3)),
       st.floats(min_value=0.5, max_value=2.5))
def test_from_positions_round_trip(positions, wavelength):
    """``from_positions`` is the form an external list arrives in.

    Round-trip through JSON as well: Q is a *derived* field with a validator, so
    a list that cannot be rebuilt from its own serialisation would fail exactly
    where a project file is reloaded.
    """
    tt = np.array(sorted(positions))
    pl = PeakList.from_positions(tt, wavelength)

    assert [p.two_theta for p in pl.peaks] == pytest.approx(sorted(tt))
    assert pl.source == "positions"
    assert all("sigma_assumed" in p.flags for p in pl.peaks)
    assert all(p.two_theta_esd == PEAK_ASSUMED_ESD_DEG for p in pl.peaks)
    assert pl.usable() == pl.peaks          # assumed σ is still evidence
    assert np.allclose(pl.q(), q_of_two_theta(tt, wavelength))
    assert np.allclose([p.d for p in pl.peaks], pl.q() ** -0.5)

    again = PeakList.model_validate_json(pl.model_dump_json())
    assert again.q() == pytest.approx(pl.q())
    assert {d.code for d in peak_diagnostics(pl)} >= {"PEAK_SIGMA_ASSUMED"}


def test_q_must_not_drift_from_two_theta():
    """The derived field is self-guarding: a hand-built peak with a stale Q is an
    error at construction, not a silently mis-indexed pattern later."""
    ok = dict(two_theta=30.0, two_theta_esd=0.01, intensity=1.0,
              intensity_esd=0.1, fwhm=0.1, eta=0.5, group=0, n_in_group=1,
              chi2_red=1.0)
    lam = 1.54
    q = float(q_of_two_theta(np.array(30.0), lam))
    good = ObservedPeak(q=q, q_esd=1e-4, **ok)
    PeakList(peaks=[good], wavelength=lam, two_theta_min=20.0,
             two_theta_max=40.0)
    bad = ObservedPeak(q=q * 1.01, q_esd=1e-4, **ok)
    with pytest.raises(ValueError, match="carries q ="):
        PeakList(peaks=[bad], wavelength=lam, two_theta_min=20.0,
                 two_theta_max=40.0)


def test_short_list_is_a_result_not_an_exception():
    """A short list comes back carrying ``PEAK_LIST_TOO_SHORT`` — a *warning*
    since WP-1043, because the twenty-line bar belongs to the figures of merit
    only: the list is searchable (over the systems its line count supports)
    and merely cannot be scored against published thresholds."""
    instrument = _instrument()
    y_true, grid, truth = _forward(instrument, tt_lo=20.0, tt_hi=45.0)
    peaks = pick_peaks(_noisy(y_true, grid, 21), instrument)
    assert 0 < len(peaks.usable()) < PEAK_MIN_USABLE_LINES
    assert len(truth) < PEAK_MIN_USABLE_LINES
    d = next(d for d in peaks.diagnostics if d.code == "PEAK_LIST_TOO_SHORT")
    assert d.level == "warning"
    assert "searched but not scored" in d.message


def test_synchrotron_width_default_on_lab_data_is_reported():
    """The ``ProfileTCHZ`` default (W = 1e-3 deg², FWHM ≈ 0.03°) is a
    *synchrotron* line; inherited on lab data it lands near a factor of 13, and
    the caller is told rather than having it silently absorbed."""
    truthy = _instrument()
    truthy.profile.w.value = 0.02      # FWHM ≈ 0.19°, an ordinary lab line
    truthy.profile.x.value = 0.06
    y_true, grid, _truth = _forward(truthy)
    data = _noisy(y_true, grid, 31)

    default = Instrument.bragg_brentano()        # profile left at its default
    det = detect_peaks(data, default)
    assert det.fwhm_measured / det.fwhm_predicted > 3.0
    assert det.width_scale > 3.0
    codes = {d.code for d in peak_diagnostics(pick_peaks(data, default), det)}
    assert "PEAK_WIDTH_LAW_MISMATCH" in codes


def test_predicted_fwhm_is_the_instruments_own_law():
    """Detection, the fitter's seeds and ``compile_model``'s windows must not
    disagree about how wide a peak is."""
    instrument = _instrument()
    tt = np.array([20.0, 60.0, 120.0])
    got = predicted_fwhm(tt, instrument)
    assert np.all(np.diff(got) > 0)              # widens with angle here
    assert got[0] == pytest.approx(0.0733, abs=5e-3)


def test_contamination_line_is_flagged_not_subtracted():
    """A Kβ ghost leaves ``usable()`` but stays in ``peaks`` with its reason.

    Stripping is never the alternative: it redistributes the counting noise, so
    what is left has neither the position nor the σ it appears to have.
    """
    instrument = _instrument()
    y_true, grid, truth = _forward(instrument)
    # a Kβ ghost of the strongest line, at ~1/500 of it
    lam_kb = 1.392234
    parent = float(truth[np.argmax([y_true[np.argmin(np.abs(grid - t))]
                                    for t in truth])])
    tt_ghost = 2 * np.degrees(np.arcsin(lam_kb / instrument.source.lines[0].wavelength.value
                                        * np.sin(np.radians(0.5 * parent))))
    fwhm = float(predicted_fwhm(np.array([tt_ghost]), instrument)[0])
    peak_h = float(y_true[np.argmin(np.abs(grid - parent))])
    y = y_true + 0.06 * peak_h * np.exp(
        -0.5 * ((grid - tt_ghost) / (fwhm / 2.355)) ** 2)

    peaks = pick_peaks(_noisy(y, grid, 77), instrument)
    ghosts = [p for p in peaks.peaks if "ghost_kbeta" in p.flags]
    assert ghosts, f"no Kβ ghost flagged at {tt_ghost:.2f}°"
    assert all(not p.usable for p in ghosts)
    assert ghosts[0] not in peaks.usable()
    assert "PEAK_CONTAMINATION_LINE" in {d.code for d in peaks.diagnostics}


def test_unmodelled_axial_asymmetry_is_flagged():
    """FCJ is applied at the *declared* apertures.  Pick a pattern that has real
    axial asymmetry with an instrument that declares none and the odd-cubic
    residual projection must say so — an unmodelled one-sided aberration biases
    the centroid in one direction, which σ cannot see."""
    asymmetric = _instrument(axial=(0.05, 0.02))
    y_true, grid, _truth = _forward(asymmetric)
    data = _noisy(y_true, grid, 99)

    declared_none = _instrument(axial=(0.0, 0.0))
    peaks = pick_peaks(data, declared_none)
    flagged = [p for p in peaks.peaks if "asymmetry_unmodelled" in p.flags]
    assert flagged, "no line flagged asymmetric"
    assert "PEAK_ASYMMETRY_UNMODELLED" in {d.code for d in peaks.diagnostics}

    # declared correctly, the same pattern is clean
    honest = pick_peaks(data, asymmetric)
    assert len([p for p in honest.peaks
                if "asymmetry_unmodelled" in p.flags]) < len(flagged)


def test_excluded_regions_and_range_crop_compose():
    """``two_theta_range`` crops on top of ``excluded_regions``, and excluded
    channels are *removed*: a window straddling a gap has no meaningful frozen
    background."""
    instrument = _instrument()
    y_true, grid, _truth = _forward(instrument)
    noisy = _noisy(y_true, grid, 5)
    data = PatternData(two_theta=noisy.two_theta, intensity=noisy.intensity,
                       excluded_regions=[(40.0, 50.0)])
    peaks = pick_peaks(data, instrument, two_theta_range=(25.0, 70.0))
    tt = peaks.two_theta()
    assert tt.min() > 25.0 and tt.max() < 70.0
    assert not np.any((tt > 40.0) & (tt < 50.0))

    with pytest.raises(ValueError, match="needs a pattern, not a window"):
        pick_peaks(data, instrument, two_theta_range=(60.0, 60.1))


# ----------------------------------------------------------------------
# WP-1026 — a component the fit believes in as a shape and not as a line
# ----------------------------------------------------------------------
def test_shape_repair_is_flagged_not_reported_as_a_line():
    """The defect that stopped a certified pattern from indexing at all.

    ``fit_group``'s re-seed pass adds a component when ΔBIC prefers it, and ΔBIC
    asks whether the data prefer n+1 components to n — which is the same question
    as "is there a line here" only while the n-component model is *capable of
    fitting*.  Against a refuted model any extra component wins, so on a real
    laboratory profile the fitter bought one phantom per strong peak: ~1 FWHM
    below it, ~10 % of its area, carrying a small esd so it read downstream as a
    well-measured line.  Measured on the bundled qarr corundum pattern,
    ``detect_peaks`` returned 41 groups with **one seed each** and the fitter
    returned 63 components, and neither engine could index a cell that is
    certified.

    Reproduced here without any real data, by giving the fitter a model it cannot
    match: the pattern is generated *with* axial divergence and picked with an
    instrument that declares none.  That is exactly the real situation — a
    profile aberration the group model does not carry — and it is the mechanism
    rather than the particular aberration that is under test.
    """
    truth_ins = _instrument(axial=(0.04, 0.02))
    y_true, grid, truth = _forward(truth_ins, tt_lo=20.0, tt_hi=60.0)
    data = _noisy(y_true, grid, 4242)

    blind = _instrument(axial=(0.0, 0.0))         # the aberration is undeclared
    peaks = pick_peaks(data, blind)

    flagged = [p for p in peaks.peaks if "not_separable" in p.flags]
    assert flagged, "no shape-repair component was recognised at all"
    # every one of them is a weak satellite of a much stronger line…
    tt = np.array([p.two_theta for p in peaks.peaks])
    inten = np.array([p.intensity for p in peaks.peaks])
    for p in flagged:
        near = np.abs(tt - p.two_theta) < 1.5 * p.fwhm
        near &= tt != p.two_theta
        assert near.any() and inten[near].max() > 4.0 * p.intensity
    # …and none of them is offered as evidence of a lattice
    assert not (set(p.two_theta for p in flagged)
                & set(p.two_theta for p in peaks.usable()))
    # the component is *kept*, because it earns its place as shape: removing it
    # from the model would push the position of the line it sits on
    assert len(peaks.peaks) > len(peaks.usable())
    # and the real lines survive — this must not be a filter that eats the pattern
    matched = sum(1 for t in truth
                  if min(abs(p.two_theta - t) for p in peaks.usable()) < 0.05)
    assert matched >= len(truth) - 1


@pytest.mark.parametrize("axial", [(0.0, 0.0), (0.04, 0.02)])
def test_the_flag_never_fires_when_the_model_can_fit(axial):
    """The false-positive guard, and it is the half that decides the design.

    Same pattern, same fitter, same re-seed gate — but the instrument used to
    pick is the one the data were generated with, so the group model is capable
    of fitting.  Nothing may be flagged: on data the model can describe, an added
    component *is* evidence, and a rule that demoted it would be deleting lines.
    Measured over three noise realisations of each geometry: 6 components for
    6 reflections, median χ²_red 0.79-1.09, no flags at all — against 9-10
    components and 1-2 flags for the same pattern picked blind to its axial
    divergence (the test above).
    """
    ins = _instrument(axial=axial)
    y_true, grid, truth = _forward(ins, tt_lo=20.0, tt_hi=60.0)
    for seed in (4242, 7, 99):
        peaks = pick_peaks(_noisy(y_true, grid, seed), ins)
        flagged = [p.two_theta for p in peaks.peaks
                   if "not_separable" in p.flags]
        assert not flagged, f"seed {seed}: flagged {flagged} on a fit that works"
        assert len(peaks.usable()) == len(truth)


def test_the_refutation_condition_is_what_separates_shape_from_line():
    """Condition 3 alone, isolated: two fits identical but for their χ²_red.

    The behavioural tests above exercise the rule through the fitter, where all
    three conditions move together.  This one pins the discriminator itself, and
    it is the reason ``not_separable`` is not simply a tighter ΔBIC: the geometry
    of the component (a re-seeded satellite inside a stronger line's profile) is
    held *fixed*, and only whether the group's fit is refuted is varied.
    """
    def _fit(chi2_red: float) -> GroupFit:
        return GroupFit(
            group=None, n=2,
            two_theta=np.array([40.0, 40.10]),
            two_theta_esd=np.array([1e-3, 5e-3]),
            intensity=np.array([2.0e4, 2.0e3]),
            intensity_esd=np.array([1e2, 5e1]),
            gamma_g=0.07, gamma_l=0.02, fwhm=0.09, eta=0.3,
            chi2_red=chi2_red, converged=True,
            at_bound=np.zeros(2, dtype=bool), asymmetry_t=np.zeros(2),
            n_points=51, from_reseed=np.array([False, True]))

    dof = 51 - 2 - 4
    bar = 1.0 + 3.0 * np.sqrt(2.0 / dof)
    assert _not_separable(_fit(bar + 0.5), 1)      # refuted → shape, not a line
    assert not _not_separable(_fit(bar - 0.1), 1)  # fits → the component is a line
    # and the *stronger* group-mate is never flagged, whatever the fit quality
    assert not _not_separable(_fit(bar + 0.5), 0)


def test_shape_repair_reports_itself_rather_than_going_quiet():
    """A flag that removes lines from ``usable()`` must say so out loud.

    Every sibling flag in this module has a diagnostic — ``PEAK_UNRESOLVED_SHOULDER``,
    ``PEAK_CONTAMINATION_LINE``, ``PEAK_ASYMMETRY_UNMODELLED`` — and a new one
    that silently shrank the list would be exactly the behaviour the peak list is
    built to avoid.  Its suggestion names the *usual cause* rather than the
    symptom, because that is the actionable half: the third condition is that the
    group's fit is refuted, so a pattern full of these is normally a pattern whose
    instrument profile is mis-declared.
    """
    truth_ins = _instrument(axial=(0.04, 0.02))
    y_true, grid, _ = _forward(truth_ins, tt_lo=20.0, tt_hi=60.0)
    peaks = pick_peaks(_noisy(y_true, grid, 4242), _instrument(axial=(0.0, 0.0)))

    codes = {d.code for d in peaks.diagnostics}
    assert "PEAK_NOT_SEPARABLE" in codes
    d = next(x for x in peaks.diagnostics if x.code == "PEAK_NOT_SEPARABLE")
    assert d.level == "warning"
    assert d.where, "the flagged positions must travel with the count"
    assert "instrument profile" in d.suggestion

    # and it stays silent when nothing is flagged
    clean = pick_peaks(_noisy(*_forward(_instrument(), tt_lo=20.0, tt_hi=60.0)[:2],
                              seed=7), _instrument())
    assert "PEAK_NOT_SEPARABLE" not in {x.code for x in clean.diagnostics}


def test_not_separable_is_unusable_and_the_flag_set_says_so():
    """Flag semantics, pinned where the set is defined rather than inferred."""
    assert "not_separable" in PEAK_UNUSABLE_FLAGS
    peak = ObservedPeak(
        two_theta=30.0, two_theta_esd=0.01, intensity=10.0, intensity_esd=1.0,
        q=q_of_two_theta(np.array(30.0), 1.5406).item(), q_esd=1e-4,
        fwhm=0.1, eta=0.5, group=0, n_in_group=2, chi2_red=9.0,
        flags=["not_separable"])
    assert not peak.usable
    # …and it is *not* one of the "less precise, still evidence" flags
    assert "unresolved_shoulder" not in PEAK_UNUSABLE_FLAGS
    assert "sigma_assumed" not in PEAK_UNUSABLE_FLAGS


def test_a_component_at_its_zero_intensity_bound_locates_nothing():
    """WP-1110 item 14: ``no_intensity`` is unusable, and it is one test.

    A peak reaches its window only through ``intensity × profile``, so a
    component that refined onto its zero intensity bound has no gradient on its
    own position — the fitted 2θ is whatever the seed was.  The threshold is not
    a new one: it is the same ``at its bound`` test the refinement's
    ``BOUND_HIT`` uses, imported rather than restated.

    Unusable rather than merely reported, unlike the flags below it: those are
    lines a consumer might still judge real, and there is nothing left to judge
    here.
    """
    from rietx.strategy.staged import BOUND_HIT_RTOL

    assert "no_intensity" in PEAK_UNUSABLE_FLAGS
    peak = ObservedPeak(
        two_theta=30.0, two_theta_esd=3.9e49, intensity=2.1e-49,
        intensity_esd=85.0,
        q=q_of_two_theta(np.array(30.0), 1.5406).item(), q_esd=1e-4,
        fwhm=0.1, eta=0.5, group=0, n_in_group=2, chi2_red=1.0,
        flags=["no_intensity"])
    assert not peak.usable
    assert peak.intensity <= BOUND_HIT_RTOL


def test_the_phantom_components_of_a_real_pattern_are_flagged_and_excluded():
    """The corundum pattern that found this, end to end.

    Two of its 62 components refine to intensities of 2.1e-49 and 5.5e-19 with
    position esds of 1e+49 and 1e+17 degrees.  Before the covariance was
    equilibrated (WP-1110 item 14) those esds were truncated to 0.06° and both
    were offered to the engines as ordinary measured lines; the trial index
    built from them reached 3.1e+25 and the search raised.

    The assertion is that they are *in* the list and *out* of ``usable``, which
    is the whole point of flagging rather than dropping — a report can still say
    why each line went.
    """
    import rietx as rx
    from tests.test_acceptance_qpa_roundrobin import DATA as QARR
    from tests.test_acceptance_qpa_roundrobin import qarr_instrument

    path = QARR / "corundum.prn"
    if not path.is_file():
        pytest.skip("IUCr round-robin corundum pattern not present")
    data = rx.read_pattern(path)
    peaks = pick_peaks(data, qarr_instrument())

    flagged = [p for p in peaks.peaks if "no_intensity" in p.flags]
    assert len(flagged) == 2, [(p.two_theta, p.intensity) for p in flagged]
    assert all(p.intensity < 1e-15 for p in flagged)
    assert not any("no_intensity" in p.flags for p in peaks.usable())
    # they are the *only* thing this flag removed — 8 other components are
    # already unusable here for reasons of their own (ghosts, not_separable)
    keeps_without_the_flag = [
        p for p in peaks.peaks
        if not (set(p.flags) - {"no_intensity"}) & PEAK_UNUSABLE_FLAGS]
    assert len(keeps_without_the_flag) == len(peaks.usable()) + 2

    # and the point of removing them: every line offered to an engine now has a
    # position esd a lattice search can use.  The worst was 3.9e+49 degrees.
    assert max(p.two_theta_esd for p in peaks.usable()) < 1.0
