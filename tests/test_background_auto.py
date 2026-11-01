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
OUT = Path(__file__).parent / "output"


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _peaky_pattern(*, background, seed=5, lo=15.0, hi=110.0, step=0.02,
                   structure=None, instrument=None, scale=3e-4):
    """LaB6 pattern on a prescribed analytic background, Poisson-noised.

    ``scale`` is how well counted it is.  The default leaves the strongest line
    a few hundred counts over the background, which is enough for every shape
    question here and is **not** enough to read a contamination off: a leak is
    reported jointly over several strong parents (WP-1442), and at this scale
    only the top two parents' ghost images clear 5σ at all.  The ghost tests
    therefore ask for 3e-3, where all eight do.
    """
    structure = structure or make_lab6()
    structure.phases[0].scale.value = scale
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
    """Add the pattern's whole image at a second wavelength, at ``height``.

    Every reflection gets one, because a leak is a property of the beam: the
    same fraction of Kβ reaches the detector whichever plane diffracted it.
    Doping the strongest line alone was what these tests used to do, and since
    WP-1442 that is deliberately not evidence of a contamination — the rule
    asks how many strong parents agree, and one cannot.  Returns the ghost
    position of the strongest line, which is the one the assertions name.
    """
    from scipy.signal import find_peaks

    from rietx.background.diagnostics import background_envelope

    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    net = np.maximum(y - background_envelope(tt, y), 0.0)
    # the parent angle whose ghost images onto each channel
    s = np.sin(np.radians(tt / 2.0)) * lam_parent / lam_ghost
    ok = (s < 1.0)
    parent_of = np.full_like(tt, np.nan, dtype=float)
    parent_of[ok] = 2.0 * np.degrees(np.arcsin(s[ok]))
    inside = ok & (parent_of >= tt[0]) & (parent_of <= tt[-1])
    add = np.zeros_like(y)
    add[inside] = height * np.interp(parent_of[inside], tt, net)

    idx, _ = find_peaks(y, height=np.percentile(y, 99.5), distance=20)
    parent = tt[idx[np.argmax(y[idx])]]
    ghost = 2.0 * np.degrees(
        np.arcsin(np.sin(np.radians(parent / 2.0)) * lam_ghost / lam_parent))
    return (rx.PatternData(two_theta=tt.tolist(), intensity=(y + add).tolist()),
            ghost)


def test_one_stray_line_is_not_a_contamination():
    """The regression this WP exists for: a single match is a coincidence.

    Before WP-1442 each ghost match was its own finding, so any weak line that
    happened to fall near one strong line's Kβ position was flagged and dropped
    from ``usable()``.  On seventeen patterns collected behind a graphite
    monochromator, where no Kβ can reach the detector, that fired at exactly
    the rate a made-up wavelength did.
    """
    from scipy.signal import find_peaks

    data = _peaky_pattern(background=_flat_bkg, scale=3e-3)
    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    idx, _ = find_peaks(y, height=np.percentile(y, 99.5), distance=20)
    parent = tt[idx[np.argmax(y[idx])]]
    ghost = 2.0 * np.degrees(np.arcsin(
        np.sin(np.radians(parent / 2.0)) * 1.3922340 / WAVELENGTH))
    y = y + 0.12 * y.max() * np.exp(-0.5 * ((tt - ghost) / 0.05) ** 2)
    one = rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    assert diagnose(one, wavelength=WAVELENGTH).contamination == []

    # the same pattern with every line doped is a leak, and is reported
    whole, _ = _dope_ghost(data, WAVELENGTH, 1.3922340)
    assert diagnose(whole, wavelength=WAVELENGTH).contamination


def test_diagnostics_flag_kbeta_ghost():
    """Inject a Kβ leak into LaB6 and check the finding, not just the flag."""
    from rietx.background.diagnostics import GHOST_MIN_PARENTS

    data = _peaky_pattern(background=_flat_bkg, scale=3e-3)
    doped, ghost = _dope_ghost(data, WAVELENGTH, 1.3922340, height=0.12)

    flags = diagnose(doped, wavelength=WAVELENGTH).contamination
    kb = [f for f in flags if f.kind == "kbeta" and abs(f.two_theta - ghost) < 0.2]
    assert kb, f"Kβ ghost at {ghost:.2f}° not flagged; got {flags}"

    # the finding is joint, and every flag of it carries the same evidence
    all_kb = [f for f in flags if f.kind == "kbeta"]
    assert kb[0].n_parents >= GHOST_MIN_PARENTS
    assert kb[0].n_parents <= kb[0].n_parents_searched
    assert len({f.leak_ratio for f in all_kb}) == 1
    assert len({f.n_parents for f in all_kb}) == 1
    assert kb[0].leak_ratio == pytest.approx(0.12, rel=0.5)
    # one flag per ghost line, whatever the parents
    assert len({round(f.two_theta, 6) for f in all_kb}) == len(all_kb)


def test_a_ghost_is_found_down_to_the_ratio_window_the_check_accepts():
    """The ghost the check exists for is the *small* one, and the census bar
    is not the ghost bar.

    A filtered tube leaks Kβ well under the 0.14 an unfiltered one carries,
    and ``GHOST_RATIO_RANGE`` says so: a ghost is accepted from 0.005 of its
    parent upwards.  ``diagnose``'s peak census takes a dynamic-range floor at
    ``SAMPLING_HEIGHT_FRACTION`` = 0.03, six times higher, so reading that one
    bar as the candidate bar deletes every ghost in the window the ratio test
    declares.

    The fixture is a well-counted pattern, because that is where the two bars
    part: on a 200-count background 5σ is about 70 and the σ bar binds first,
    while here it is 7 against a census floor of 2206.  It carries eight lines
    rather than three, because since WP-1442 the finding is joint and three
    parents cannot reach ``GHOST_MIN_PARENTS``.  Each is doped at 1 %, which is
    what a filtered tube leaks.
    """
    from rietx.background.diagnostics import (
        GHOST_MIN_PARENTS,
        GHOST_RATIO_RANGE,
        SAMPLING_HEIGHT_FRACTION,
    )

    tt = np.arange(10.0, 90.0, 0.02)
    y = np.full_like(tt, 200.0)
    sg = 0.12 / 2.3548
    lines = ((28.44, 100000.0), (33.00, 80000.0), (37.60, 65000.0),
             (42.10, 58000.0), (47.30, 50000.0), (51.80, 40000.0),
             (56.12, 30000.0), (62.40, 26000.0))
    for p, a in lines:
        y = y + a * np.exp(-0.5 * ((tt - p) / sg) ** 2)
    for p, a in lines:
        g = 2.0 * np.degrees(np.arcsin(
            np.sin(np.radians(p / 2.0)) * 1.3922340 / WAVELENGTH))
        y = y + 0.01 * a * np.exp(-0.5 * ((tt - g) / sg) ** 2)
    ghost = 2.0 * np.degrees(np.arcsin(
        np.sin(np.radians(28.44 / 2.0)) * 1.3922340 / WAVELENGTH))
    y = np.random.default_rng(0).poisson(y).astype(float)
    doped = rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    flags = diagnose(doped, wavelength=WAVELENGTH).contamination
    kb = [f for f in flags if f.kind == "kbeta" and abs(f.two_theta - ghost) < 0.05]
    assert kb, f"1 % Kβ ghost at {ghost:.2f}° not flagged; got {flags}"
    assert kb[0].n_parents >= GHOST_MIN_PARENTS
    assert kb[0].intensity_ratio > GHOST_RATIO_RANGE[0]
    assert kb[0].intensity_ratio < SAMPLING_HEIGHT_FRACTION  # the bar it clears
    assert kb[0].leak_ratio < SAMPLING_HEIGHT_FRACTION


@pytest.mark.parametrize("anode", ["CrKa", "FeKa", "CoKa", "CuKa", "MoKa", "AgKa"])
def test_kbeta_check_follows_the_anode(anode):
    """The ghost sits at the *anode's* Kβ, so the check has to be per anode.

    Before WP-0507 this returned [] for anything but Cu — an empty list that
    reads as "clean".
    """
    from rietx.background.diagnostics import _KBETA

    ins = rx.Instrument.bragg_brentano(radiation=anode)
    lam = ins.source.lines[0].wavelength.value
    data = _peaky_pattern(background=_flat_bkg, instrument=ins,
                          lo=5.0, hi=125.0, scale=3e-3)
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
    data = _peaky_pattern(background=_flat_bkg, instrument=ins,
                          lo=25.0, hi=125.0, scale=3e-3)
    doped, ghost = _dope_ghost(data, lam, _W_LA1, height=0.05)

    flags = diagnose(doped, wavelength=lam).contamination
    w = [f for f in flags if f.kind == "tungsten_la" and abs(f.two_theta - ghost) < 0.2]
    assert w, f"W Lα1 ghost at {ghost:.2f}° not flagged; got {flags}"


# ----------------------------------------------------------------------
# WP-1442: the ghost search against the patterns where it cannot be right
# ----------------------------------------------------------------------
def _monochromated():
    """The round-robin pure phases, all behind a graphite monochromator.

    ``tests/data/README.md`` records the optics: a diffracted-beam curved
    graphite monochromator removes Kβ, and W Lα1 with it.  Neither line can
    reach the detector on any of these, so every flag on them is a false one
    and the true answer is known without a reference value.
    """
    from tests.test_acceptance_qpa_roundrobin import DATA as QARR

    files = sorted(QARR.glob("*.prn"))
    if not files:
        pytest.skip("IUCr QPA round-robin dataset not present")
    return files


def _ghost_pool(data):
    """What ``diagnose`` hands the contamination check, with its σ and net."""
    from scipy.signal import find_peaks, peak_prominences

    from rietx.background.diagnostics import (
        GHOST_RATIO_RANGE,
        SAMPLING_PROMINENCE_SIGMA,
        background_envelope,
    )

    mask = data.in_range_mask()
    tt, y, sigma = data.tt()[mask], data.y()[mask], data.sig()[mask]
    net = y - background_envelope(tt, y)
    pos = np.where(net > 0, net, 0.0)
    bar = np.maximum(5.0 * sigma,
                     GHOST_RATIO_RANGE[0] * float(np.percentile(pos, 99.9)))
    cand, _ = find_peaks(pos, distance=3, height=bar)
    keep = cand[peak_prominences(pos, cand)[0]
                >= SAMPLING_PROMINENCE_SIGMA * sigma[cand]]
    return tt, net, sigma, keep


def test_no_ghost_is_found_where_no_ghost_can_exist():
    """Every round-robin pattern, at its real wavelength, reports nothing.

    Before WP-1442 the seventeen monochromated fixtures — these sixteen and
    SRM 660c — carried 52 Kβ and 16 W Lα flags through ``diagnose`` and 20
    through the fitted list, each of which dropped a real reflection from
    ``usable()``.  This row walks the sixteen the round-robin ships.
    """
    for path in _monochromated():
        d = diagnose(rx.read_pattern(path), wavelength=1.54056)
        assert d.contamination == [], f"{path.name}: {d.contamination}"


def test_the_real_wavelength_beats_a_made_up_one():
    """The control that gives the corpus above its teeth.

    A screen that flags at the same rate whatever wavelength it is fed has
    measured nothing.  Replacing Kβ by 26 values that cannot be an emission
    line, the consensus count must stay under ``GHOST_MIN_PARENTS`` for all of
    them — the margin, rather than the flag count, is what says the answer
    above was not luck.  Measured: the chance consensus tops out at 4.
    """
    from rietx.background.diagnostics import (
        GHOST_MATCH_K,
        GHOST_MIN_PARENTS,
        GHOST_TOL_DEG,
        _ghost_candidates,
        _ghost_consensus,
    )

    worst = 0
    for path in _monochromated():
        data = rx.read_pattern(path)
        tt, net, sigma, keep = _ghost_pool(data)
        lo, hi = float(tt[0]), float(tt[-1])
        for fake in np.linspace(0.80, 0.995, 26) * WAVELENGTH:
            cands, _ = _ghost_candidates(
                tt[keep], net[keep], None, sigma[keep], fake / WAVELENGTH,
                lo, hi, tol_deg=GHOST_TOL_DEG, k_sigma=GHOST_MATCH_K)
            support = _ghost_consensus(cands)[0]
            worst = max(worst, support)
            assert support < GHOST_MIN_PARENTS, (
                f"{path.name}: a made-up λ={fake:.4f} Å gathered {support} "
                f"parents, at or over the bar of {GHOST_MIN_PARENTS}")
    assert worst <= 4                       # the number the bar was set above


@pytest.mark.parametrize("host", ["corundum.prn", "zincite.prn"])
def test_an_injected_leak_comes_back_with_its_ratio(host):
    """The other half: the screen still finds a leak that is really there.

    A Kβ image of the whole pattern is added at 10 %, which is what a tube with
    a failed filter does.  ``leak_ratio`` is the finding's, fitted across the
    supporting parents, so it is the number that has to come back — the
    per-line ``intensity_ratio`` of a weak line on a strong one's flank is
    worth much less.  The two hosts are round-robin phases that carry no Kβ,
    so the clean pattern is the same test's null.
    """
    from rietx.background.diagnostics import GHOST_MIN_PARENTS
    from tests.test_acceptance_qpa_roundrobin import DATA as QARR

    if not (QARR / host).exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    base = rx.read_pattern(QARR / host)
    assert diagnose(base, wavelength=1.54056).contamination == []

    doped, _ = _dope_ghost(base, 1.54056, 1.3922340, height=0.10)
    flags = [f for f in diagnose(doped, wavelength=1.54056).contamination
             if f.kind == "kbeta"]
    assert flags, f"{host}: a 10 % Kβ leak was not found"
    assert flags[0].n_parents >= GHOST_MIN_PARENTS
    assert flags[0].leak_ratio == pytest.approx(0.10, rel=0.35)


def test_a_line_with_no_position_is_neither_parent_nor_candidate():
    """``FAP.XRA``'s degenerate fits, the fixture the esd cap was written for.

    Two unresolved-shoulder fits at 64.330° come back with position esds of
    1 961° and 11 390°, and a line with no intensity at 105.788° with 4.2e15°.
    The matching window is ``max(floor, 3·√(σ_g² + σ_p²))``, so uncapped those
    three matched every parent and supplied 32 of that pattern's 35 raw
    matches.  An esd past :data:`GHOST_TOL_DEG` is not a loose position, it is
    no position.
    """
    from rietx.background.diagnostics import (
        GHOST_ESD_MAX_DEG,
        contamination_flags_from_peaks,
    )
    from rietx.indexing.pick import pick_peaks

    path = Path(__file__).parent / "data" / "FAP.XRA"
    if not path.exists():
        pytest.skip("FAP.XRA not present")
    data = rx.read_pattern(path)
    peaks = pick_peaks(data, rx.Instrument.bragg_brentano(radiation="CuKa"))
    esd = np.array([p.two_theta_esd for p in peaks.peaks])
    assert (esd > GHOST_ESD_MAX_DEG).sum() >= 3      # the fixture still bites

    flags = contamination_flags_from_peaks(
        np.array([p.two_theta for p in peaks.peaks]),
        np.array([p.intensity for p in peaks.peaks]), esd, 1.54056,
        tt_range=(float(data.two_theta[0]), float(data.two_theta[-1])))
    assert flags == []
    assert not [p for p in peaks.peaks
                if {"ghost_kbeta", "ghost_tungsten"} & set(p.flags)]


def test_a_line_with_no_position_never_reaches_a_consumer():
    """The same three lines, one rank out: they leave ``usable()`` as well.

    The ghost screen stopping at them is not enough.  Every consumer that
    matches positions builds a ±kσ window, so a line whose σ spans the axis
    matches whatever it is compared against — the one at 64.330° carries
    ±1 961°, which is 17× the whole measured range, and while it was usable the
    indexed apatite cell sat 1 376 ppm off the certified one.

    ``unresolved_shoulder`` is deliberately *not* an unusable flag, on the
    stated grounds that such a line is "still evidence, just less precise
    evidence, and their σ already says so".  That holds while σ is finite and a
    consumer can act on it.  This is the companion for when it is not.
    """
    from rietx.indexing.pick import pick_peaks
    from rietx.schemas.indexing import (
        PEAK_POSITION_ESD_MAX_DEG,
        PEAK_UNUSABLE_FLAGS,
    )

    assert "position_unmeasured" in PEAK_UNUSABLE_FLAGS

    path = Path(__file__).parent / "data" / "FAP.XRA"
    if not path.exists():
        pytest.skip("FAP.XRA not present")
    data = rx.read_pattern(path)
    peaks = pick_peaks(data, rx.Instrument.bragg_brentano(radiation="CuKa"))

    flagged = [p for p in peaks.peaks if "position_unmeasured" in p.flags]
    assert flagged, "the fixture no longer carries an unlocated line"
    assert all(p.two_theta_esd >= PEAK_POSITION_ESD_MAX_DEG for p in flagged)
    assert not [p for p in peaks.usable() if "position_unmeasured" in p.flags]

    # and nothing merely *imprecise* was caught with them: the bar is the axis,
    # not the peak's width, so a line uncertain by a degree still counts
    # (the one such line on this pattern, at 65.69 deg with intensity 0.39 of its
    # own esd, is now unusable for the other reason, PEAK_NO_INTENSITY_SIGMA, so
    # the test looks at the components, not at what is still usable)
    kept = [p for p in peaks.peaks
            if p.two_theta_esd > p.fwhm and "position_unmeasured" not in p.flags]
    assert kept, (
        "every line whose esd exceeds its own width went, which is a wider "
        "rule than this one and needs its own measurement")
    assert max(p.two_theta_esd for p in kept) < 1.0


def test_the_ghost_screen_is_drawn_for_inspection():
    """The picture the counts stand on, on a pattern with a known answer.

    Corundum came behind a graphite monochromator, so every mark in the top
    panel is a false one: those are the candidates the position and ratio
    windows admit, which is one per flag under the pre-WP-1442 rule, and each
    dropped a real reflection from ``usable()``.  The bottom panel is the same
    pattern with a 10 % Kβ image of itself added, and the marks are the finding
    the joint rule reports.  Rendered and looked at, not just written.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from rietx.background.diagnostics import (
        GHOST_MATCH_K,
        GHOST_TOL_DEG,
        _ghost_candidates,
        background_envelope,
    )
    from tests.test_acceptance_qpa_roundrobin import DATA as QARR

    if not (QARR / "corundum.prn").exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    lam, lam_kb = 1.54056, 1.3922340
    base = rx.read_pattern(QARR / "corundum.prn")
    doped, _ = _dope_ghost(base, lam, lam_kb, height=0.10)

    # the ungated census pool, which is what the rule saw before this WP
    tt = base.tt()
    y = base.y()
    net = y - background_envelope(tt, y)
    sigma = base.sig()
    pos = np.where(net > 0, net, 0.0)
    from scipy.signal import find_peaks
    bar = np.maximum(5.0 * sigma, 0.005 * float(np.percentile(pos, 99.9)))
    cand, _ = find_peaks(pos, distance=3, height=bar)
    old, _ = _ghost_candidates(
        tt[cand], net[cand], None, sigma[cand], lam_kb / lam,
        float(tt[0]), float(tt[-1]),
        tol_deg=GHOST_TOL_DEG, k_sigma=GHOST_MATCH_K)
    old_tt = sorted(float(tt[cand][ig]) for _, ig, _ in old)
    now = [f.two_theta for f in diagnose(doped, wavelength=lam).contamination
           if f.kind == "kbeta"]

    OUT.mkdir(exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(6.9, 5.2), sharex=True, sharey=True)
    hi = float(np.percentile(y, 99.98)) * 1.12
    for ax, (label, marks, colour) in zip(axes, [
            ("monochromated, no Kβ reaches the detector", old_tt, "#b2182b"),
            ("the same pattern, 10 % Kβ leak added", now, "#2166ac")]):
        ax.plot(tt, y, ".", ms=1.2, color="#222222", rasterized=True)
        for m in marks:
            ax.plot([m, m], [-0.085 * hi, -0.020 * hi], "-", lw=1.6,
                    color=colour, solid_capstyle="round", clip_on=False)
        ax.set_ylim(-0.10 * hi, hi)
        ax.set_xlim(float(tt[0]), float(tt[-1]))
        ax.spines[["top", "right"]].set_visible(False)
        ax.text(1.012, 0.97, label, transform=ax.transAxes, va="top",
                ha="left", fontsize=9, color=colour, wrap=True)
        ax.text(1.012, 0.10, f"{len(marks)} marked", transform=ax.transAxes,
                va="top", ha="left", fontsize=9, color=colour)
    axes[0].set_ylabel("Intensity (counts)", fontsize=9)
    axes[1].set_xlabel("2θ (°),  Cu Kα1 λ = 1.54056 Å", fontsize=9)
    for ax in axes:
        ax.tick_params(labelsize=9)
    fig.subplots_adjust(right=0.63, hspace=0.12)
    fig.savefig(OUT / "ghost_search_corundum.png", dpi=180,
                bbox_inches="tight")
    plt.close(fig)

    assert (OUT / "ghost_search_corundum.png").exists()
    assert old_tt, "the pre-WP-1442 rule flagged nothing here, so the top panel is empty"
    assert now, "the injected leak was not found, so the bottom panel is empty"

    # the control curve: what the same rule answers at wavelengths that cannot
    # be an emission line.  A real answer has to stand clear of this.
    from scipy.signal import peak_prominences

    from rietx.background.diagnostics import (
        GHOST_MIN_PARENTS,
        SAMPLING_PROMINENCE_SIGMA,
        _ghost_consensus,
    )

    gated = cand[peak_prominences(pos, cand)[0]
                 >= SAMPLING_PROMINENCE_SIGMA * sigma[cand]]
    lams = np.linspace(0.80, 0.995, 60) * lam

    def support(sel, lam_g):
        cs, _ = _ghost_candidates(
            tt[sel], net[sel], None, sigma[sel], lam_g / lam,
            float(tt[0]), float(tt[-1]),
            tol_deg=GHOST_TOL_DEG, k_sigma=GHOST_MATCH_K)
        return _ghost_consensus(cs)[0]

    fig, ax = plt.subplots(figsize=(6.9, 3.0))
    for sel, colour, label, marker in (
            (cand, "#b2182b", "pool before the prominence gate", "o"),
            (gated, "#2166ac", "pool as shipped", "s")):
        ax.plot(lams, [support(sel, float(g)) for g in lams], marker, ms=3.4,
                color=colour, alpha=0.85)
        ax.plot([lam_kb], [support(sel, lam_kb)], marker, ms=8.5,
                color=colour, markerfacecolor="white", markeredgewidth=1.6)
        ax.text(1.012, {"o": 0.95, "s": 0.72}[marker], label,
                transform=ax.transAxes, va="top", ha="left", fontsize=9,
                color=colour)
    ax.axhline(GHOST_MIN_PARENTS, color="#444444", lw=0.9, dashes=(4, 3))
    ax.text(1.012, 0.40, f"bar, {GHOST_MIN_PARENTS} parents",
            transform=ax.transAxes, va="top", ha="left", fontsize=9,
            color="#444444")
    ax.text(1.012, 0.20, "open marks: the real Kβ", transform=ax.transAxes,
            va="top", ha="left", fontsize=9, color="#444444")
    ax.set_xlabel("ghost wavelength (Å);  only 1.3922 Å is a real line",
                  fontsize=9)
    ax.set_ylabel("supporting parents", fontsize=9)
    ax.set_ylim(-0.4, 8.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
    fig.subplots_adjust(right=0.62)
    fig.savefig(OUT / "ghost_search_control.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    assert (OUT / "ghost_search_control.png").exists()


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
# counting coverage — how many observations stand behind each channel
# ----------------------------------------------------------------------
#
# The measure and its two constants were set from two NIST BT-1
# constant-wavelength neutron patterns (3.00-166.25° at 0.05°, 3266 points,
# σ from the file, plateau v = 0.837 and 0.826).  Both show the same ladder in
# σ²/max(y, 1) — ≈5× below 8°, ≈2.2-2.6×
# out to ≈15°, tapering to 1× by ≈55°, then a step back to ≈2.2× inside one
# channel at 161.30° — and neither pattern's plateau contains a region at all.
# Those files live on the maintainer's archive drive and not in this repo, so
# they are provenance for the numbers here and nothing is read from them: every
# fixture below is synthetic, with the inflation put in on purpose.


def _coverage_pattern(*, inflate=(), spikes=(), lo=5.0, hi=150.0, step=0.05,
                      peak_deg=30.0, sigma_jitter=0.1, seed=3):
    """Counts with a **measured** σ column and a prescribed coverage map.

    Built the way the instrument builds it, as an exposure: a channel covered
    for a fraction 1/k of the reference exposure reports the same *rate* and a
    σ that is √k larger relative to it, so σ²/max(y, 1) = k there and 1 in the
    bulk.  ``inflate`` is ``(2θ_lo, 2θ_hi, k)`` windows.

    ``sigma_jitter`` is what makes the false-positive guard mean something: the
    real σ column is not exactly √C (detector efficiencies, monitor
    normalisation), and 10 % per-channel jitter on σ is 20 % on the ratio.
    ``spikes`` multiplies σ on single channels, which is the shape of every
    above-threshold excursion measured in the real plateau.
    """
    # rounded rather than np.arange: the window bounds below are compared
    # against this grid, and 2900 accumulated steps of 0.05 put the last
    # channel 3e-13 past ``hi``, outside its own window
    tt = np.round(lo + step * np.arange(int(round((hi - lo) / step)) + 1), 6)
    rng = np.random.default_rng(seed)
    mu = 500.0 + 4000.0 * np.exp(-0.5 * ((tt - peak_deg) / 0.3) ** 2)
    exposure = np.ones_like(tt)
    for w_lo, w_hi, k in inflate:
        exposure[(tt >= w_lo) & (tt <= w_hi)] = 1.0 / k
    counts = rng.poisson(mu * exposure).astype(float)
    y = counts / exposure
    sigma = np.sqrt(np.maximum(counts, 1.0)) / exposure
    sigma *= 1.0 + sigma_jitter * rng.standard_normal(len(tt))
    for pos, factor in spikes:
        sigma[int(np.argmin(np.abs(tt - pos)))] *= factor
    return rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                          sigma=np.abs(sigma).tolist())


def test_counting_coverage_finds_the_thin_ends():
    """A known 5× window at the low end and a 2.2× one at the high end — the
    two levels the BT-1 patterns show — come back with their own bounds and
    their own inflation.

    The bounds are resolved to within the smoothing window and no better: a
    median over ``COVERAGE_SMOOTH_DEG`` crosses the threshold when half the
    window is inside the step, so an interior boundary sits half a window in
    while a boundary at the pattern's own edge does not move.
    """
    from rietx.background import counting_coverage
    from rietx.background.diagnostics import COVERAGE_SMOOTH_DEG

    data = _coverage_pattern(inflate=[(5.0, 20.0, 5.0), (140.0, 150.0, 2.2)])
    regions, plateau = counting_coverage(data.tt(), data.y(),
                                        np.asarray(data.sigma))
    assert plateau == pytest.approx(1.0, abs=0.05)
    assert [r.edge for r in regions] == ["low", "high"], regions

    low, high = regions
    assert low.two_theta_min == 5.0
    assert low.two_theta_max == pytest.approx(20.0, abs=COVERAGE_SMOOTH_DEG)
    assert low.inflation == pytest.approx(5.0, rel=0.15)
    assert low.n_channels == pytest.approx(15.0 / 0.05, rel=0.1)

    assert high.two_theta_min == pytest.approx(140.0, abs=COVERAGE_SMOOTH_DEG)
    assert high.two_theta_max == pytest.approx(150.0, abs=1e-9)
    assert high.inflation == pytest.approx(2.2, rel=0.15)

    # model-free: the Bragg peak at 30° is in neither region and makes none of
    # its own — v is a property of σ against y, not of the pattern's shape
    assert all(not (r.two_theta_min <= 30.0 <= r.two_theta_max) for r in regions)


def test_counting_coverage_silent_on_clean_measured_sigma():
    """The false-positive guard, and the more important of the two.

    Uniform coverage with 10 % jitter on σ and four single-channel σ spikes big
    enough to put the raw ratio at 3× — which is what the real plateau does
    (every excursion above the threshold there is exactly one channel long).
    Nothing may be reported, and the plateau must still say the check ran.
    """
    from rietx.background import counting_coverage

    data = _coverage_pattern(spikes=[(40.0, 1.8), (70.0, 1.8), (95.0, 1.8),
                                     (120.0, 1.8)])
    regions, plateau = counting_coverage(data.tt(), data.y(),
                                        np.asarray(data.sigma))
    assert regions == []
    assert plateau == pytest.approx(1.0, abs=0.05)

    # the spikes are real in the unsmoothed statistic — the guard is the
    # smoothing, not the absence of anything to smooth
    v = np.asarray(data.sigma) ** 2 / np.maximum(data.y(), 1.0)
    assert v.max() / plateau > 2.5


def test_counting_coverage_declines_a_poisson_fallback_sigma():
    """Empty because the statistic carries **no information**, not because it
    was measured and found nothing.

    Under σ = √max(y, 1) the ratio is identically 1 by construction, so an
    answer computed from it would describe the fallback rather than the
    experiment.  ``sigma=None`` is how this module already spells "not
    measured" (:func:`sampling_steps_per_fwhm`), and ``coverage_plateau``
    ``None`` is what separates *not checkable* from *checked and uniform*.
    """
    from rietx.background import counting_coverage
    from rietx.background.diagnostics import COVERAGE_INFLATION_THRESHOLD

    counts = _coverage_pattern(inflate=[(5.0, 20.0, 5.0)])
    bare = rx.PatternData(two_theta=counts.two_theta,
                          intensity=np.round(counts.y()).tolist())
    assert bare.sigma is None
    assert counting_coverage(bare.tt(), bare.y(), None) == ([], None)

    d = diagnose(bare)
    assert d.coverage_regions == []
    assert d.coverage_plateau is None

    # and the reason: handed the fallback array explicitly, the ratio is a
    # constant 1 — degenerate, so the emptiness above is structural rather than
    # a threshold that happened not to fire
    ratio = bare.sig() ** 2 / np.maximum(bare.y(), 1.0)
    np.testing.assert_allclose(ratio, 1.0, atol=1e-12)
    assert COVERAGE_INFLATION_THRESHOLD > 1.0
    regions, plateau = counting_coverage(bare.tt(), bare.y(), bare.sig())
    assert regions == [] and plateau == pytest.approx(1.0)


def test_counting_coverage_names_an_interior_region():
    """A dead detector is not the bank running out at the end of its range.

    Both are thin coverage and the ratio cannot tell them apart, but the causes
    are different — one is the ordinary geometry of a multi-detector
    instrument, the other is a fault or a stitched scan — so ``edge`` says
    which shape was seen and leaves the reading to the caller.
    """
    from rietx.background import counting_coverage
    from rietx.background.diagnostics import COVERAGE_SMOOTH_DEG

    data = _coverage_pattern(inflate=[(70.0, 80.0, 3.0)])
    regions, plateau = counting_coverage(data.tt(), data.y(),
                                        np.asarray(data.sigma))
    assert [r.edge for r in regions] == ["interior"], regions
    assert regions[0].two_theta_min == pytest.approx(70.0, abs=COVERAGE_SMOOTH_DEG)
    assert regions[0].two_theta_max == pytest.approx(80.0, abs=COVERAGE_SMOOTH_DEG)
    assert regions[0].inflation == pytest.approx(3.0, rel=0.15)
    # a 10° window inside the middle half does not move the plateau it is
    # measured against
    assert plateau == pytest.approx(1.0, abs=0.05)


def test_counting_coverage_survives_degenerate_patterns():
    """No pattern makes it raise, and two of these are declared behaviour.

    A pattern with no σ and one whose σ is all zeros have no plateau to compare
    against, so they answer ``None`` rather than guessing.  A window of **zero
    intensity** with a finite σ does report a region, and that is the caveat
    the docstring declares rather than a claim about detector count: max(y, 1)
    in the denominator makes v large wherever the counts collapse, which is a
    different phenomenon wearing the same statistic.
    """
    from rietx.background import counting_coverage

    data = _coverage_pattern()
    tt, y, sigma = data.tt(), data.y(), np.asarray(data.sigma)

    assert counting_coverage(tt, y, None) == ([], None)
    assert counting_coverage(tt[:2], y[:2], sigma[:2]) == ([], None)
    assert counting_coverage(tt, y, np.zeros_like(sigma)) == ([], None)

    nan_y, nan_sigma = y.copy(), sigma.copy()
    nan_y[100:120] = np.nan
    nan_sigma[900:905] = np.nan
    regions, plateau = counting_coverage(tt, nan_y, nan_sigma)
    assert plateau == pytest.approx(1.0, abs=0.05)
    assert regions == [], "a non-finite channel makes no claim"

    zeroed = y.copy()
    zeroed[-400:] = 0.0
    regions, _ = counting_coverage(tt, zeroed, sigma)
    assert [r.edge for r in regions] == ["high"], (
        "declared caveat: collapsing counts inflate v too")


def test_diagnose_reports_the_same_coverage_as_the_function():
    """One authority, the shape ``steps_per_fwhm`` already has: ``diagnose``
    must be a call to :func:`counting_coverage`, not a second opinion."""
    from rietx.background import counting_coverage

    data = _coverage_pattern(inflate=[(5.0, 20.0, 5.0), (140.0, 150.0, 2.2)])
    regions, plateau = counting_coverage(data.tt(), data.y(),
                                        np.asarray(data.sigma))
    d = diagnose(data)
    assert d.coverage_plateau == plateau
    assert d.coverage_regions == regions


def test_counting_coverage_on_the_bundled_patterns_that_fire():
    """The measure fires on real bundled patterns, and none is a plain
    detector-bank falloff — so the reading is documented rather than left for a
    caller to rediscover (the manual carries the causes; this pins the numbers).

    The synthetic fixtures above set the *constants*; this pins what the measure
    actually reports on the σ-bearing patterns shipped in ``tests/data``, so a
    later change that moves a boundary or a level has to say so here.  The 11-BM
    ends rise smoothly (an analyser bank tapering, not a quantised step) and the
    SRM 660c ladder is non-monotonic (a counting schedule, not a detector count);
    ``edge`` locates each and does not claim its cause.
    """
    from rietx.background import counting_coverage

    data_dir = Path(__file__).parent / "data"

    def _fire(name):
        data = rx.read_pattern(str(data_dir / name))
        assert data.sigma is not None, f"{name} has no σ column to read"
        return counting_coverage(data.tt(), data.y(), data.sig())

    # 11-BM: one high-angle region each, ≈2.8× the plateau, smooth taper.
    for name, lo_deg in (("11BM_NAC.fxye", 46.0), ("11BM_LaB6_660a.fxye", 53.0)):
        regions, plateau = _fire(name)
        assert [r.edge for r in regions] == ["high"], (name, regions)
        assert regions[0].two_theta_min == pytest.approx(lo_deg, abs=1.0), name
        assert regions[0].inflation == pytest.approx(2.8, rel=0.1), name

    # SRM 660c: a broad low region and two interior ones — the interior pair is
    # threshold-crossing chatter, the low one the counting schedule.
    regions, plateau = _fire("nist_srm660c_100a.cif")
    assert [r.edge for r in regions] == ["low", "interior", "interior"], regions
    low = regions[0]
    assert low.two_theta_min == pytest.approx(20.3, abs=0.5)
    assert low.two_theta_max == pytest.approx(62.5, abs=1.0)
    assert low.inflation == pytest.approx(5.5, rel=0.1)
    assert regions[1].inflation == pytest.approx(2.74, rel=0.1)
    assert regions[2].inflation == pytest.approx(1.58, rel=0.1)

    # and silent where σ is measured but coverage is uniform — the control that
    # keeps the three above from being "fires on everything".
    clean = rx.read_pattern(str(data_dir / "panalytical_attenuator.xrdml"))
    assert clean.sigma is not None
    regions, plateau = counting_coverage(clean.tt(), clean.y(), clean.sig())
    assert regions == [], regions
    assert plateau is not None


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


def _at_cap(sel):
    return [d for d in sel.diagnostics if d.code == "BACKGROUND_ORDER_AT_CAP"]


def test_a_scan_that_returns_its_cap_says_so():
    """Issue #833 / WP-1931's acceptance line: on 11-BM Si 640c at the default
    cap the scan never meets the Durbin-Watson stop and returns 16, so the code
    fires, naming the cap and the last d.  On ``main`` it returned 16 in
    silence."""
    data = rx.read_pattern(Path(__file__).parent / "data" / "11BM_Si640c.xy").crop(8.0, 30.0)
    sel = select_chebyshev_order(data)
    assert sel.selected == 16 and not sel.stopped_by_whiteness
    (hit,) = _at_cap(sel)
    d_last = sel.scores[-1].durbin_watson
    assert hit.value == d_last and d_last < 1.8
    assert "16 terms" in hit.message and f"{d_last:.3f}" in hit.message

    # a synthetic hump the scan needs 15 terms for, capped at 6: the same code
    humpy = _peaky_pattern(background=_hump_bkg)
    capped = select_chebyshev_order(humpy, max_order=6)
    assert capped.selected == 6 and not capped.stopped_by_whiteness
    assert _at_cap(capped)


def test_an_order_the_scan_chose_carries_no_cap_code():
    """The two ways a scan chooses: the whiteness stop ends it (the synthetic
    hump at the default cap stops at 15 of 16), or BIC turns over inside the
    cap without it (11-BM LaB₆ 660a, 4-30°, picks 31 of 32, #833's table)."""
    stopped = select_chebyshev_order(_peaky_pattern(background=_hump_bkg))
    assert stopped.stopped_by_whiteness and stopped.selected < 16
    assert not stopped.diagnostics

    lab6 = rx.read_pattern(Path(__file__).parent / "data" / "11BM_LaB6_660a.fxye").crop(4.0, 30.0)
    interior = select_chebyshev_order(lab6, max_order=32)
    assert not interior.stopped_by_whiteness and interior.selected < 32
    assert not interior.diagnostics


def test_auto_background_hands_the_cap_code_to_its_caller():
    """``auto_background`` returns a background, so the selection's code
    reaches the caller as a warning that starts with it, and a chosen order
    raises none."""
    humpy = _peaky_pattern(background=_hump_bkg)
    with pytest.warns(UserWarning, match=r"^info\[BACKGROUND_ORDER_AT_CAP\]: "):
        auto_background(rx.read_pattern(
            Path(__file__).parent / "data" / "11BM_Si640c.xy"), kind="chebyshev",
            two_theta_limits=(8.0, 30.0))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cheb = auto_background(humpy, kind="chebyshev").background
    assert len(cheb.coefficients) == 15


def test_arpls_lambda_selection_returns_evidence():
    sel = select_arpls_lambda(_peaky_pattern(background=_hump_bkg))
    assert sel.method == "arpls_lambda"
    assert sel.selected in [10.0 ** e for e in range(4, 11)]
    assert sel.scores and all(s.durbin_watson >= 0 for s in sel.scores)


def test_auto_background_shapes_to_pattern():
    flat = auto_background(_peaky_pattern(background=_flat_bkg), wavelength=WAVELENGTH).background
    assert isinstance(flat, BackgroundPSpline)
    assert flat.air_scatter is None, "a declined air term is absent, not zero (WP-1454)"

    air = auto_background(_peaky_pattern(background=_air_scatter_bkg), wavelength=WAVELENGTH).background
    assert air.air_scatter.vary, "1/x term should switch on for air scatter"

    cheb = auto_background(_peaky_pattern(background=_hump_bkg), kind="chebyshev").background
    assert isinstance(cheb, BackgroundChebyshev)
    assert len(cheb.coefficients) >= 4


def test_auto_background_returns_the_scores_beside_its_pick():
    """The pick travels with the scores it was made on (WP-2002, B12).

    Each choice is the one its score and trigger name, and the model is the
    one the verb built before it returned the scores: the knots
    ``for_range`` lays at that step, and the air term only past its trigger.
    """
    from rietx.background.auto import (
        _KNOT_STEP_HUMPY_DEG,
        _KNOT_STEP_SMOOTH_DEG,
        AIR_SCATTER_TRIGGER,
        HUMP_TRIGGER,
    )

    for shape in (_flat_bkg, _air_scatter_bkg, _hump_bkg):
        data = _peaky_pattern(background=shape)
        diag = diagnose(data, wavelength=WAVELENGTH)
        choice = auto_background(data, diagnostics=diag)
        assert choice.kind == "pspline"
        assert choice.amorphous_hump_score == diag.amorphous_hump_score
        assert choice.hump_trigger == HUMP_TRIGGER
        assert choice.air_scatter_gain == diag.air_scatter_gain
        assert choice.air_scatter_trigger == AIR_SCATTER_TRIGGER
        humpy = diag.amorphous_hump_score > HUMP_TRIGGER
        assert choice.knot_step_deg == (_KNOT_STEP_HUMPY_DEG if humpy
                                        else _KNOT_STEP_SMOOTH_DEG)
        assert choice.air_scatter == (diag.air_scatter_gain > AIR_SCATTER_TRIGGER)
        assert choice.air_scatter == (choice.background.air_scatter is not None)
        built = BackgroundPSpline.for_range(diag.two_theta_min, diag.two_theta_max,
                                            knot_step_deg=choice.knot_step_deg,
                                            lambda_smooth=1.0)
        assert choice.background.breakpoints == built.breakpoints
        assert choice.selection is None and choice.seed_level is None

    humpy = _peaky_pattern(background=_hump_bkg)
    cheb = auto_background(humpy, kind="chebyshev")
    scan = select_chebyshev_order(humpy)
    assert cheb.kind == "chebyshev"
    assert cheb.selection == scan
    assert len(cheb.background.coefficients) == int(scan.selected)
    assert cheb.amorphous_hump_score is None and cheb.knot_step_deg is None
    assert cheb.air_scatter is None


def test_auto_background_knots_span_the_fitted_range():
    """The knots cover the channels a fit under the same limits uses and no
    others (WP-1454): a coefficient past the fitted range has no data, only
    the penalty, and extends the curve wherever its slope points."""
    data = _peaky_pattern(background=_flat_bkg)
    whole = auto_background(data, wavelength=WAVELENGTH).background
    assert whole.breakpoints[0] == pytest.approx(data.two_theta[0])
    assert whole.breakpoints[-1] == pytest.approx(data.two_theta[-1])

    limited = auto_background(data, wavelength=WAVELENGTH, two_theta_limits=(30.0, 70.0)).background
    tt = np.asarray(data.two_theta)
    fitted = tt[(tt >= 30.0) & (tt <= 70.0)]
    assert limited.breakpoints[0] == pytest.approx(fitted[0])
    assert limited.breakpoints[-1] == pytest.approx(fitted[-1])

    # caller-supplied diagnostics over the whole file: the knots still stop at the limits
    kept = auto_background(data, diagnostics=diagnose(data, wavelength=WAVELENGTH),
                           two_theta_limits=(30.0, 70.0)).background
    assert kept.breakpoints[0] >= 30.0 and kept.breakpoints[-1] <= 70.0


def test_auto_background_refuses_limits_it_cannot_use():
    data = _peaky_pattern(background=_flat_bkg)
    with pytest.raises(ValueError, match="inverted"):
        auto_background(data, two_theta_limits=(70.0, 30.0))
    with pytest.raises(ValueError, match="fewer than the 10 a fit needs"):
        auto_background(data, two_theta_limits=(200.0, 210.0))
    # two channels: enough for a PatternData, not for ``diagnose`` or a fit
    tt = np.asarray(data.two_theta)
    with pytest.raises(ValueError, match="leave 2 fitted channels"):
        auto_background(data, two_theta_limits=(tt[10], tt[11]))
    # caller's diagnostics over a range the limits do not reach
    elsewhere = diagnose(data.crop(20.0, 30.0), wavelength=WAVELENGTH)
    with pytest.raises(ValueError, match="does not overlap"):
        auto_background(data, diagnostics=elsewhere, two_theta_limits=(50.0, 70.0))


def test_an_undeclared_air_term_raises_no_background_correlation_rows():
    """Every preset frees ``instrument.background.*`` and a plan replaces the
    vary flags, so an air term held at 0 was refined anyway.  Inside a fine
    spline's span its 1/(2θ) column is one flat direction, which the guard
    reported once per pair of background columns (WP-1454).  Absent, there is
    no path for the glob to free.  The declared arm is the failure reproduced,
    so this test can still go red: more rows than the spline has coefficients
    is one degeneracy counted many times."""
    data = _peaky_pattern(background=_flat_bkg, lo=20.0, hi=60.0)
    seed = float(np.percentile(data.intensity, 5))

    def background_rows(air):
        ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
        ins.profile.w.value = 3e-3
        ins.profile.x.value = 5e-3
        bkg = BackgroundPSpline.for_range(20.0, 60.0, knot_step_deg=2.0,
                                          lambda_smooth=1e-4)
        for c in bkg.coefficients:
            c.value = seed
        bkg.air_scatter = air
        ins.background = bkg
        structure = make_lab6()
        structure.phases[0].scale.value = 3e-4
        result = rx.Refinement(structure, ins, history=False).fit(
            data, plan="profile_only", telemetry=False)
        return len(bkg.coefficients), [
            d for d in result.diagnostics
            if d.code in ("HIGH_CORRELATION", "FLAT_DIRECTION")
            and all(p.startswith("instrument.background.") for p in d.where)]

    assert BackgroundPSpline.for_range(20.0, 60.0).air_scatter is None
    _, rows = background_rows(None)
    assert rows == [], [d.where for d in rows]
    n_coef, flooded = background_rows(
        rx.Parameter(value=0.0, min=0.0, transform="softplus"))
    assert len(flooded) > n_coef


def test_the_penalty_is_equally_stiff_in_any_intensity_unit():
    """Multiply y, σ and the phase scale by k: the fitted background divided by
    k is the same curve (WP-1454).  The bar is the spread the same fit shows
    when restarted from another start, measured here rather than chosen, and
    the old intensity-unit rows are the arm that must fail it.

    Measured 2026-09-24 (``[dev]``, Linux x86-64): restart spread 4.9e-3 of the
    curve's maximum, k = 1e-3 and 1e3 within 2.7e-4 and 3.1e-9 of k = 1; the
    old rows 7.4e-2 at 1e-3 and 0.56 at 1e3, a straight line at Rwp 0.36.
    """
    base = _peaky_pattern(background=_hump_bkg, lo=20.0, hi=60.0)
    sig = base.sig()

    def fitted_background(k, units="dimensionless", restart=False):
        data = base.model_copy(update={
            "intensity": list(np.asarray(base.intensity) * k),
            "sigma": list(sig * k)})
        ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
        ins.profile.w.value = 3e-3
        ins.profile.x.value = 5e-3
        bkg = BackgroundPSpline.for_range(20.0, 60.0, knot_step_deg=2.0)
        bkg.lambda_units = units
        seed = float(np.percentile(data.intensity, 5)) * (1.3 if restart else 1.0)
        for c in bkg.coefficients:
            c.value = seed
        ins.background = bkg
        structure = make_lab6()
        structure.phases[0].scale.value = 3e-4 * k * (0.8 if restart else 1.0)
        result = rx.Refinement(structure, ins, history=False).fit(
            data, plan="profile_only", telemetry=False)
        return np.asarray(result.y_background) / k

    reference = fitted_background(1.0)
    size = np.abs(reference).max()
    spread = np.abs(fitted_background(1.0, restart=True) - reference).max() / size
    for k in (1e-3, 1e3):
        moved = np.abs(fitted_background(k) - reference).max() / size
        assert moved < spread, (k, moved, spread)

    old = fitted_background(1.0, units="intensity")
    moved = np.abs(fitted_background(1e3, units="intensity") - old).max() / size
    assert moved > spread, (moved, spread)


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
    # D₂ of n² is 2, weighed against the data's own weight per coefficient
    scale = np.sqrt(len(model.tt) / n_coef) / np.median(model.sigma)
    np.testing.assert_allclose(pen, np.sqrt(4.0) * 2.0 * scale)
    # the pre-WP-1454 rows, which a golden declares
    ins.background.lambda_units = "intensity"
    old = compile_model(structure, ins, data).penalty_residual(curved)
    np.testing.assert_allclose(old, np.sqrt(4.0) * 2.0, rtol=0, atol=0)
    ins.background.lambda_units = "dimensionless"

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
    ins.background = auto_background(data, wavelength=WAVELENGTH).background

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
    assert "R²=" in msg.message
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
        return max(background_absorption(
            outcome.jac, table.free_paths, frozenset()).values())

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

    assert "the residual is systematic" in report.summary
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


_UNSCREENED = {
    # Le Bail and Pawley force-fix every target the screen asks about
    "lebail": ("lebail", ["instrument.background.c*", "phases.*.cell.*"]),
    "pawley": ("pawley", ["instrument.background.c*", "phases.*.cell.*"]),
    # a Rietveld answer stage with a block and no target, then the reverse
    "rietveld_no_target": ("rietveld", ["instrument.background.c*",
                                        "phases.*.cell.*"]),
    "rietveld_no_background": ("rietveld", ["phases.*.scale",
                                            "phases.*.atoms.*.biso"]),
}


@pytest.mark.parametrize("arm", sorted(_UNSCREENED))
def test_an_absorption_screen_with_nothing_to_screen_reads_not_measured(arm):
    """``None``, never 0.0, wherever the screen had no target or no block.

    WP-1465 (issue #451): the table came back ``{}`` in all four arms and its
    headline read ``worst_absorption = 0.0`` — "the background absorbs
    nothing", a measurement nobody made, on every Le Bail and Pawley report.
    The same data as ``_absorption_fit``, so the Rietveld arm that *does*
    screen (the pair test above) is the control.
    """
    mode, paths = _UNSCREENED[arm]
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    data = _peaky_pattern(background=_flat_bkg, lo=15.0, hi=70.0, seed=4,
                          structure=structure.model_copy(deep=True),
                          instrument=ins.model_copy(deep=True))
    ins.background = BackgroundChebyshev.with_terms(6)
    ins.background.coefficients[0].value = 120.0
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(data, mode=mode,
                     plan=rx.RefinementPlan(stages=[rx.Stage("all", paths)]))

    # the result's own record: measured, and empty
    assert result.identifiability is not None
    assert result.identifiability.background_absorption == {}

    report = ref.report()
    bg = report.background
    assert bg.absorption is None, bg
    assert bg.worst_absorption is None and bg.worst_absorption_path is None
    assert "decrease_background_flexibility" not in {
        a.kind for a in report.suggested_actions}
    assert "block projection R²" not in report.summary
    # the trajectory rung projects the same None
    assert report.for_stage("all").worst_absorption is None
    if mode == "rietveld":
        assert ("background.absorption: not measured"
                in ref.summary(deliverable="qpa", report=report))
    _plot(result, f"wp1465_unscreened_{arm}")


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


# ----------------------------------------------------------------------
# signal cutoffs — an end of the range the instrument was not seeing
# through.  The real-data provenance (a private constant-wavelength neutron
# PSD scan; NIST BT-1 for the coverage measure) is in ``signal_cutoffs``'
# docstring; nothing here reads a drive.
# ----------------------------------------------------------------------
_LEVEL = 1.0e8
#: σ²/y constant across the range, as on the private neutron PSD scans these
#: cases are shaped after.
_VARIANCE_PER_COUNT = 2.0e4


def _cw_pattern(*, lo=5.0, hi=150.0, step=0.05, seed=3, peaks=(
        (25.0, 3.0), (48.0, 1.5), (77.0, 2.2), (112.0, 1.2), (138.0, 0.9))):
    """``(two_theta, y)`` for a flat-background pattern with broad peaks.

    Shaped after a constant-wavelength neutron scan rather than built by the
    forward model: these cases are about the *ends of the range*, so the peaks
    exist only to make the interior level a realistic mixture of peak and
    background, and a compiled model would tie the case to the profile code.
    """
    tt = np.arange(lo, hi + 0.5 * step, step)
    y = np.full_like(tt, _LEVEL)
    for centre, height in peaks:
        y += height * _LEVEL * np.exp(-0.5 * ((tt - centre) / 0.5) ** 2)
    rng = np.random.default_rng(seed)
    return tt, y * (1.0 + 0.01 * rng.standard_normal(tt.size))


def _sigma_like_the_file(y):
    """σ with σ²/y constant — what makes the precision penalty derivable."""
    return np.sqrt(_VARIANCE_PER_COUNT * np.maximum(y, 1.0))


def _collapse(tt, y, *, at, edge, floor=0.02, deg=0.5):
    """Taper ``y`` beyond ``at`` towards ``floor``, e-folding over ``deg``.

    A factor of 50 in ≈2°, then a floor — the trailing shape of the private
    neutron PSD scan ``signal_cutoffs`` documents.
    """
    x = (tt - at) if edge == "high" else (at - tt)
    taper = np.where(x > 0.0, np.maximum(np.exp(-x / deg), floor), 1.0)
    return y * taper


def test_signal_cutoff_finds_a_trailing_cliff():
    """The archetype: a level that collapses near the end and stays down.

    The boundary reported is the *onset*, not the floor, so it must land on
    the last channel that was still at level — within a channel or two of
    where the taper was applied.
    """
    from rietx.background.diagnostics import signal_cutoffs

    tt, clean = _cw_pattern()
    y = _collapse(tt, clean, at=130.0, edge="high")
    got = signal_cutoffs(tt, y, _sigma_like_the_file(y))

    assert len(got) == 1, got
    cut = got[0]
    assert cut.edge == "high"
    assert abs(cut.two_theta - 130.0) < 0.1, cut     # 0.05° step: two channels
    assert cut.floor_fraction < 0.05, cut            # the floor, not the cliff
    # what a trim at this boundary would drop, and it is most of the tail
    assert cut.n_channels == int(np.sum(tt > cut.two_theta))
    assert 350 < cut.n_channels < 420, cut


def test_signal_cutoff_is_silent_on_clean_patterns():
    """The false-positive guard, and the one that matters most.

    A pattern whose ends are at its own interior level has no cutoff, and
    neither does one whose background merely *falls* across the range — the
    1/x air-scatter shape is the near miss, since it is highest at the end
    this measure looks at.
    """
    from rietx.background.diagnostics import signal_cutoffs

    tt, y = _cw_pattern()
    assert signal_cutoffs(tt, y, _sigma_like_the_file(y)) == []

    for background in (_flat_bkg, _air_scatter_bkg, _hump_bkg):
        data = _peaky_pattern(background=background)
        assert signal_cutoffs(data.tt(), data.y()) == [], background.__name__


def test_signal_cutoff_ignores_an_interior_gap():
    """A collapse that does not reach an end of the range is not a cutoff.

    Same depth and more than the same width as the trailing case above — a
    dead detector or an excised region, whose handling is an excluded region
    and not a fit range.  Reaching the first or last channel is the whole
    difference, so it is asserted against the case that only differs there.
    """
    from rietx.background.diagnostics import signal_cutoffs

    tt, y = _cw_pattern()
    gap = (tt > 60.0) & (tt < 68.0)
    y = np.where(gap, 0.02 * y, y)
    assert signal_cutoffs(tt, y, _sigma_like_the_file(y)) == []


def test_signal_cutoff_finds_a_leading_cliff():
    """The low end, which on real data is a beamstop rather than a detector.

    Reported the same way and with the opposite ``edge``; the count is the
    channels *below* the boundary, so the two edges' ``n_channels`` mean the
    same thing for a caller trimming to them.
    """
    from rietx.background.diagnostics import signal_cutoffs

    tt, clean = _cw_pattern()
    y = _collapse(tt, clean, at=12.0, edge="low")
    got = signal_cutoffs(tt, y, _sigma_like_the_file(y))

    assert len(got) == 1, got
    cut = got[0]
    assert cut.edge == "low"
    assert abs(cut.two_theta - 12.0) < 0.1, cut
    assert cut.n_channels == int(np.sum(tt < cut.two_theta))


def test_signal_cutoff_survives_a_strong_peak_in_the_last_channels():
    """A pattern ending *on* a peak reports nothing.

    The failure this guards is the mirror of the measure's own logic: the
    interior level is a median over the middle, a peak at the last channel
    sits far above it, and a rule keyed on "different from the interior"
    rather than on "collapsed below it" would fire here.
    """
    from rietx.background.diagnostics import signal_cutoffs

    tt, y = _cw_pattern(peaks=((25.0, 3.0), (149.8, 4.0)))
    assert signal_cutoffs(tt, y, _sigma_like_the_file(y)) == []


def test_signal_cutoff_relative_error_is_the_level_re_expressed():
    """``relative_error_ratio`` is derived, and the test is that arithmetic.

    With σ²/y constant, σ/y = √(σ²/y)/√y, so the region's precision penalty is
    1/√``floor_fraction`` and carries no information the level did not.  It is
    reported because it is the number the person who took the data reads, and
    asserted here so that a later reader cannot mistake it for a second
    observation.  Absent σ it is ``None``, not the Poisson identity.
    """
    from rietx.background.diagnostics import signal_cutoffs

    tt, clean = _cw_pattern()
    y = _collapse(tt, clean, at=130.0, edge="high")

    cut = signal_cutoffs(tt, y, _sigma_like_the_file(y))[0]
    assert cut.relative_error_ratio == pytest.approx(
        1.0 / np.sqrt(cut.floor_fraction), rel=0.05)

    assert signal_cutoffs(tt, y)[0].relative_error_ratio is None


def test_signal_cutoff_degenerate_inputs_return_nothing():
    """Every degenerate input is an empty list, and one of them is a *decision*.

    A pattern with no live interior — dead but for a narrow band — comes back
    empty rather than reporting itself as one long cutoff: the threshold is a
    fraction of the pattern's own middle, so a collapse that consumed the
    middle takes the reference down with it.  Silence where the evidence is
    gone is the direction to fail in, and the alternative (a cutoff over the
    whole range) is not an answer a caller could use.
    """
    from rietx.background.diagnostics import signal_cutoffs

    two_points = np.array([10.0, 140.0])
    assert signal_cutoffs(two_points, np.array([1.0, 1.0e8])) == []

    tt, y = _cw_pattern()
    assert signal_cutoffs(tt, np.zeros_like(tt)) == []          # nothing at all
    assert signal_cutoffs(tt, np.full_like(tt, 3.0)) == []      # flat and low

    holed = y.copy()
    holed[[0, 17, 200, -1]] = np.nan
    assert signal_cutoffs(tt, holed) == []                      # NaN opens no run
    # and closes none either: the same cliff, with holes in it, is the same cut
    cliff = _collapse(tt, y, at=130.0, edge="high")
    cliff[[0, 500, 2100, -1]] = np.nan
    assert signal_cutoffs(tt, cliff)[0].two_theta == pytest.approx(130.0, abs=0.1)

    # dead but for a narrow live band: the reference went with the middle
    assert signal_cutoffs(tt, np.where((tt > 70.0) & (tt < 85.0), y, 0.01 * y)) == []


def test_diagnose_carries_the_cutoffs_and_the_others_still_read_the_range():
    """``diagnose`` reports the cutoff; it does not re-measure anything on the
    trimmed range, and the docstring's ordering claim is the reason.

    Asserted both ways: the field arrives, and the other fields still describe
    the range they were handed — the same pattern cropped to the reported
    boundaries is a *different* answer, which is what makes reading the cutoffs
    first the caller's job rather than a silent step.
    """
    from rietx.background.diagnostics import diagnose

    tt, clean = _cw_pattern()
    y = _collapse(tt, clean, at=130.0, edge="high")
    data = rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                          sigma=_sigma_like_the_file(y).tolist())

    diag = diagnose(data)
    assert [c.edge for c in diag.signal_cutoffs] == ["high"]
    assert abs(diag.signal_cutoffs[0].two_theta - 130.0) < 0.1
    assert diag.signal_cutoffs[0].relative_error_ratio is not None

    trimmed = diagnose(data.crop(float(tt[0]), diag.signal_cutoffs[0].two_theta))
    assert trimmed.signal_cutoffs == []
    assert trimmed.amorphous_hump_score < 0.5 * diag.amorphous_hump_score

    # and the whole object survives the JSON round trip an agent takes
    from rietx.background.diagnostics import PatternDiagnostics
    assert PatternDiagnostics.model_validate_json(
        diag.model_dump_json()).signal_cutoffs == diag.signal_cutoffs


def test_signal_cutoff_reports_one_boundary_per_edge():
    """A collapse with a bump inside it is one cutoff, not two.

    The real leading edge has this shape — a shadowed floor, then a broad bump
    at an angle no lattice plane could put one, then the climb — and there the
    bump stays under the threshold, so it is one run.  Built here to cross it:
    two runs at the same edge, and the answer is the innermost boundary,
    because whatever rose in between never got back to level and the usable
    range starts after the last of them.
    """
    from rietx.background.diagnostics import signal_cutoffs

    tt, clean = _cw_pattern()
    y = _collapse(tt, clean, at=12.0, edge="low")
    halo = 0.5 * _LEVEL * np.exp(-0.5 * ((tt - 7.0) / 0.6) ** 2)

    got = signal_cutoffs(tt, y + halo, _sigma_like_the_file(y + halo))
    assert [c.edge for c in got] == ["low"], got
    assert abs(got[0].two_theta - 12.0) < 0.2, got


def test_auto_background_hands_its_declared_source_to_the_screen(monkeypatch):
    """``source=`` reaches ``diagnose``; without it the screen gets ``None`` (WP-1539)."""
    from rietx.background import auto as auto_mod
    from rietx.schemas.instrument import NeutronSource

    seen = []
    real = auto_mod.diagnose

    def spy(data, **kw):
        seen.append(kw.get("source"))
        return real(data, **kw)

    monkeypatch.setattr(auto_mod, "diagnose", spy)
    data = _peaky_pattern(background=_flat_bkg)
    auto_background(data, wavelength=WAVELENGTH)
    neutron = NeutronSource(wavelength=WAVELENGTH)
    auto_background(data, wavelength=WAVELENGTH, source=neutron)
    assert seen[0] is None
    assert seen[1] is neutron
