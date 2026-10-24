"""The picker's bound hits, each named with its bound and value, and the
false-discovery floor's edge (issue #934 (c), WP-1968).

The group fit has three kinds of bound (``peakfit._GroupModel.bounds``), and
each already raises a flag: a position half the window's seed FWHM from its
seed (``position_at_bound``), an intensity at zero (``no_intensity``, which
also carries the 1σ floor) and a width at five times the seed FWHM
(``width_capped``).  The lower width bound is a positivity floor and raises
none: one width there is a pure Gaussian or Lorentzian line.  What was missing
is the diagnostic that says which bound and what value.  The intensity floor
set by the false-discovery bar is ``weak_line`` (#947); here its diagnostic
names each flagged component's I/σ_I against the bar.

Interpretation table, written before the tests were (each arm can fail):

| arm | must read if it works | reading if it is broken |
|---|---|---|
| #916's flat Si (seed 1, 12.1–60°): census | 20 picked, 16 usable, ``[1,1,1,2,1,3,1,1,1,1,1]``, and the flag counts main's own picker gives (``position_at_bound`` 7, ``no_intensity`` 3, ``weak_line`` 5, ``width_capped`` 1) | a diagnostic change moved a flag or ``usable()`` |
| the same: ``PEAK_POSITION_AT_BOUND`` | lists exactly the 7 flagged components, each with ±0.5 × its window's seed FWHM; ``info``, value 0 (every one is unusable or under the bar) | absent, a component missed, or a bound that is not its window's |
| a position named one FWHM off a strong line (``fit_peaks``) | flagged, the bound from **its own** window (not detection's group of the same index), ``info`` (Yue's ruling: never a warning), value 1, the count still offered | the bound read from the wrong window, or the offered count lost |
| the same position named on the line (control) | no flag, no diagnostic | a clean line reported at its bound |
| ``PEAK_NO_INTENSITY``: an empty named position on its zero bound, one under 1σ, and the reproducer's three | each entry says which: ``I = …, at the zero bound`` or ``I/σ_I … < 1``; value = the count on the bound | the two causes conflated |
| ``PEAK_WIDTH_CAPPED`` on the reproducer | the one capped hump, with its FWHM and 5 × its window's seed FWHM | a value missing |
| the floor's edge: planted I/σ_I just under and just over the bar | the one under is flagged and named with its I/σ_I and the bar; the one over is not | the edge on the wrong side, or a value missing |

Synthetic data only: silicon through the package's own forward model with
Poisson noise (#916's flat reproducer, the generator in ``test_peak_fdr``).
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import ndtri

import rietx as rx
from rietx.indexing import peak_diagnostics
from rietx.indexing.peaks import Detection
from rietx.indexing.pick import flag_weak_lines, pick_peaks_with_state
from rietx.schemas.indexing import (
    PEAK_FDR_Q,
    PEAK_POSITION_BOUND_FWHM,
    PEAK_WIDTH_BOUND_FACTORS,
    ObservedPeak,
    PeakList,
    q_of_two_theta,
)
from tests.test_peak_fdr import LAM, RANGE, _si_lines, _silicon

pytestmark = pytest.mark.xdist_group("peak_bounds")


@pytest.fixture(scope="module")
def flat_si(tmp_path_factory):
    """#916's flat reproducer, picked once: the data, the default
    instrument the issue used, and ``pick_peaks_with_state``'s answer."""
    data = _silicon(tmp_path_factory.mktemp("si"), steep=False, hi=62.0)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    pl, det, _ = pick_peaks_with_state(data, ins, two_theta_range=RANGE)
    return data, ins, pl, det


def _one(pl: PeakList, code: str):
    hits = [d for d in pl.diagnostics if d.code == code]
    assert len(hits) == 1, [d.code for d in pl.diagnostics]
    return hits[0]


def _flagged(pl: PeakList, flag: str) -> list[ObservedPeak]:
    return [p for p in pl.peaks if flag in p.flags]


def test_the_census_on_the_reproducer_does_not_move(flat_si):
    """Invariance control: this change adds diagnostics and moves no flag.
    Main's own census on this reproducer: 20 picked, 16 usable,
    ``[1,1,1,2,1,3,1,1,1,1,1]`` usable components within one FWHM of each
    silicon line.  Measured on main alone and on main with this change, the
    two agree.  (Until WP-2002 closed the picker's fits at the closing
    stage's wider peak windows, #1085, the pair was (23, 17) with 10, 5, 6 and
    2 flags; the wider windows let components that ended on a bound or on zero
    land elsewhere.)"""
    _, _, pl, _ = flat_si
    use = pl.usable()
    tt = np.array([p.two_theta for p in use])
    fw = np.array([max(p.fwhm, 0.025) for p in use])
    per = [int(np.sum(np.abs(tt - t) <= fw)) for t in _si_lines()]
    assert (len(pl.peaks), len(use)) == (20, 16)
    assert per == [1, 1, 1, 2, 1, 3, 1, 1, 1, 1, 1]
    counts = {f: len(_flagged(pl, f)) for f in
              ("position_at_bound", "no_intensity", "weak_line", "width_capped")}
    assert counts == {"position_at_bound": 7, "no_intensity": 3,
                      "weak_line": 5, "width_capped": 1}


def test_every_position_bound_hit_is_named_with_its_windows_bound(flat_si):
    _, _, pl, det = flat_si
    d = _one(pl, "PEAK_POSITION_AT_BOUND")
    moved = _flagged(pl, "position_at_bound")
    assert len(d.where) == len(moved) == 7
    for p, entry in zip(moved, d.where):
        r = PEAK_POSITION_BOUND_FWHM * det.groups[p.group].seed_fwhm
        z = p.intensity / p.intensity_esd
        assert entry == f"{p.two_theta:.4f}° (bound ±{r:.4f}°, I/σ_I {z:.1f})"
    # every one is unusable or under the false-discovery bar, so nothing is
    # offered at full weight from a position the fit did not choose
    assert all(not p.usable or "weak_line" in p.flags for p in moved)
    assert (d.level, d.value) == ("info", 0.0)


def test_a_named_position_off_a_line_is_a_bound_hit_and_on_it_is_not(tmp_path):
    """The positive arm and its control, through ``fit_peaks``.  The tuned
    instrument gives every window its own seed FWHM (0.0103–0.0119° over the
    range), so a bound read from detection's group of the same *index* — the
    fit's one window is index 0, detection's index 0 sits near 15° — is
    wrong by a measurable amount."""
    data = _silicon(tmp_path, steep=False, hi=62.0)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    pl, det, _ = pick_peaks_with_state(data, ins, two_theta_range=RANGE)
    line = max((p for p in pl.usable() if p.two_theta > 45.0),
               key=lambda p: p.intensity)
    r = PEAK_POSITION_BOUND_FWHM * det.groups[line.group].seed_fwhm
    assert abs(r - PEAK_POSITION_BOUND_FWHM * det.groups[0].seed_fwhm) > 5e-4

    on = rx.fit_peaks(data, ins, [line.two_theta], two_theta_range=RANGE)
    assert "position_at_bound" not in on.peaks[0].flags
    assert not [d for d in on.diagnostics if d.code == "PEAK_POSITION_AT_BOUND"]

    off = rx.fit_peaks(data, ins, [line.two_theta + line.fwhm],
                       two_theta_range=RANGE)
    (p,) = off.peaks
    assert "position_at_bound" in p.flags and p.usable
    assert p.two_theta == pytest.approx(line.two_theta + line.fwhm - r, abs=2e-3)
    d = _one(off, "PEAK_POSITION_AT_BOUND")
    assert d.where == [f"{p.two_theta:.4f}° (bound ±{r:.4f}°, "
                       f"I/σ_I {p.intensity / p.intensity_esd:.1f})"]
    assert (d.level, d.value) == ("info", 1.0)


def test_no_intensity_says_whether_the_bound_or_the_floor_put_it_there(
        flat_si):
    data, ins, pl, _ = flat_si
    d = _one(pl, "PEAK_NO_INTENSITY")
    empty = _flagged(pl, "no_intensity")
    assert d.where == [f"{p.two_theta:.4f}° (I/σ_I "
                       f"{p.intensity / p.intensity_esd:.2f} < 1)"
                       for p in empty]
    assert d.value == 0.0
    # two empty named positions: one the fit takes to its zero bound, one
    # that stays above it with an esd thousands of times its value.  The
    # closing stage's wider windows (#1085) moved the pair: 21.37 used to go
    # to zero and now keeps 0.33, while 22.5 now takes the zero bound.
    named = rx.fit_peaks(data, ins, [20.0, 22.5], two_theta_range=RANGE)
    d = _one(named, "PEAK_NO_INTENSITY")
    low, zero = named.peaks
    assert zero.intensity < 1e-10 < low.intensity
    assert d.where == [
        f"{low.two_theta:.4f}° (I/σ_I {low.intensity / low.intensity_esd:.2f} < 1)",
        f"{zero.two_theta:.4f}° (I = {zero.intensity:.3g}, at the zero bound)"]
    assert d.value == 1.0


def test_width_capped_names_each_width_and_its_bound(flat_si):
    _, _, pl, det = flat_si
    d = _one(pl, "PEAK_WIDTH_CAPPED")
    capped = _flagged(pl, "width_capped")
    f_hi = PEAK_WIDTH_BOUND_FACTORS[1]
    assert d.where == [
        f"{p.two_theta:.4f}° (FWHM {p.fwhm:.4f}°, Γ_G/Γ_L bound "
        f"{f_hi * det.groups[p.group].seed_fwhm:.4f}° each)" for p in capped]
    # the 15.4° hump was capped before the closing windows (#1085) widened
    # the picker's fits; the one at 25.1° still is
    assert [round(p.two_theta, 1) for p in capped] == [25.1]


def _peak(tt: float, i_over_s: float) -> ObservedPeak:
    q = float(q_of_two_theta(np.array(tt), LAM))
    return ObservedPeak(two_theta=tt, two_theta_esd=0.001, intensity=i_over_s,
                        intensity_esd=1.0, q=q, q_esd=1e-5, fwhm=0.05,
                        eta=0.5, group=0, n_in_group=1, chi2_red=1.0)


def test_the_false_discovery_floor_names_the_line_under_it_and_not_the_one_over():
    """Three strong lines and two planted at the floor's edge, m = 100 and
    q = 0.01: rank 4 passes at p ≤ 4e-4 (I/σ_I ≥ 3.353) and rank 5 at
    p ≤ 5e-4 (I/σ_I ≥ 3.291).  A line at 3.36 is the fourth discovery and
    sets the bar at 3.353; one at 3.28 fails rank 5 and is flagged."""
    x = np.linspace(10.0, 60.0, 50)
    det = Detection(x, x, x, x, [], 0.05, 0.05, 1.0, 0, np.zeros(0), 100.0)
    peaks = [_peak(20.0, 30.0), _peak(30.0, 30.0), _peak(40.0, 30.0),
             _peak(45.0, 3.36), _peak(50.0, 3.28)]
    flag_weak_lines(peaks, det)
    assert [p.flags for p in peaks] == [[], [], [], [], ["weak_line"]]
    pl = PeakList(peaks=peaks, wavelength=LAM, two_theta_min=10.0,
                  two_theta_max=60.0, source="fitted")
    d = _one(pl.model_copy(update={"diagnostics": peak_diagnostics(pl, det)}),
             "PEAK_EXPECTED_FALSE_LINES")
    bar = -ndtri(4 * PEAK_FDR_Q / 100.0)
    assert f"{bar:.2f}" == "3.35"
    assert d.where == [f"50.0000° (I/σ_I 3.28, bar {bar:.2f})"]


def test_the_editor_reads_a_bound_from_its_own_window(tmp_path):
    """The peak editor numbers its windows itself (``max(doc.groups) + 1``),
    so after a group is removed and another opened elsewhere the new window
    takes the removed one's number.  The bound a diagnostic prints must be the
    new window's, not detection's window of the same number — which here sits
    at 60°, where the seed FWHM is 0.0251° against 0.0209° at 20°."""
    from rietx.gui.peaks import PeakEditor
    data = _silicon(tmp_path, steep=False, hi=62.0)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    ed = PeakEditor(data, ins, two_theta_range=RANGE)
    doc = ed.pick()
    last = max(doc.groups)
    while any(p.group == last for p in doc.peaks.peaks):
        ed.remove(doc, next(i for i, p in enumerate(doc.peaks.peaks)
                            if p.group == last))
    assert last not in doc.groups
    ed.add(doc, 20.0)
    (new,) = [p for p in doc.peaks.peaks if abs(p.two_theta - 20.0) < 0.1]
    assert new.group == last
    own = doc.groups[last].seed_fwhm
    assert abs(own - ed.det.groups[last].seed_fwhm) > 1e-3
    i = doc.peaks.peaks.index(new)
    ed.flag(doc, i, flags=["position_at_bound"])
    d = _one(doc.peaks, "PEAK_POSITION_AT_BOUND")
    entry = next(e for e in d.where if e.startswith(f"{new.two_theta:.4f}°"))
    assert f"bound ±{PEAK_POSITION_BOUND_FWHM * own:.4f}°" in entry


def test_a_hand_set_no_intensity_does_not_print_a_false_comparison(flat_si):
    """The editor's ``set_flags`` can mark a strong line ``no_intensity``; the
    entry then says so, instead of printing ``I/σ_I 12 < 1``."""
    from rietx.gui.peaks import PeakDoc, set_flags
    _, _, pl, det = flat_si
    strong = max(pl.usable(), key=lambda p: p.intensity / p.intensity_esd)
    doc = PeakDoc(peaks=pl)
    i = pl.peaks.index(strong)
    set_flags(doc, i, flags=[*strong.flags, "no_intensity"])
    d = _one(doc.peaks.model_copy(update={
        "diagnostics": peak_diagnostics(doc.peaks, det)}), "PEAK_NO_INTENSITY")
    z = strong.intensity / strong.intensity_esd
    assert z > 3
    assert f"{strong.two_theta:.4f}° (I/σ_I {z:.2f}, marked by hand)" in d.where
    assert not any(f"I/σ_I {z:.2f} <" in e for e in d.where)
    assert "1 marked by hand" in d.message


def test_the_bound_and_no_intensity_texts_say_only_what_holds(flat_si):
    """Yue's #993 round 2: both texts must be true of every component they
    list, including one under 1σ and one marked by hand, and the bound's
    suggestion states the arithmetic and nothing of the line's position."""
    _, _, pl, det = flat_si
    b = _one(pl, "PEAK_POSITION_AT_BOUND")
    assert "usually a seed" not in b.suggestion
    assert "true optimum" not in b.suggestion
    for text in (b.message, b.suggestion):
        assert "lower bound" not in text and "optimum lies" not in text
        assert "the fit stopped on its" in text
    assert "the curvature there" in b.suggestion
    assert "how far past the bound the fit would have moved" in b.suggestion
    n = _one(pl, "PEAK_NO_INTENSITY")
    for text in (n.message, n.suggestion):
        assert "excluded from usable()" in text and "kept in peaks" in text
    assert "carry no intensity" not in n.message
    assert "there is no line" not in n.suggestion
    # round 3: "not measurements" is said of the zero bound only
    assert "zero bound has a 2θ and σ(2θ) that are not measurements" in n.suggestion
    assert "under its esd has a 2θ" not in n.suggestion
    # the three causes, each counted: the flat-Si census has the bound's and
    # the floor's, and none by hand
    assert "on the fit's zero-intensity bound" in n.message
    assert "PEAK_NO_INTENSITY_SIGMA" in n.message and "marked by hand" in n.message
    assert "marked by hand" in n.suggestion
