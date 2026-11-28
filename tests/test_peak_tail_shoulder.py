"""A tail shoulder on its position bound is not offered as a line (WP-2120).

A component carrying both ``axial_tail`` (a weak group-mate on a much stronger
line's axial-divergence tail side) and ``position_at_bound`` (the fit pushed it
from detection's seed to its position bound) is flagged
``tail_shoulder`` and leaves ``usable()``.  Neither flag alone does.

Interpretation table, written before the tests were (each arm can fail):

| arm | must read if it works | reading if it is broken |
|---|---|---|
| the 16 IUCr round-robin lab patterns | ``tail_shoulder`` on exactly the components carrying both flags; none usable; 8 of them would otherwise be usable (no other unusable flag, no other group's usable copy), each 0.6-1.0 fitted FWHM below a usable group-mate 4-14x its area | the flag missing from the conjunction, raised without it, or a usable line taken that is not a shoulder of its mate |
| the same, the other flags | every component carrying only one of the two is still usable unless another flag says otherwise | the rule widened to ``axial_tail`` or ``position_at_bound`` alone |
| SRM 1976a on an X'Pert (a second instrument family) | the two shoulders at 52.53 deg and 76.84 deg flagged and unusable; a usable component still holds each mate's line, 52.57 deg and 76.88 deg | the rule fails to carry to a narrower-line instrument, or takes the strong line |
| the same shoulder **named** (``fit_peaks``, a negative arm) | ``axial_tail`` and ``position_at_bound`` both raised, ``tail_shoulder`` not, and the line usable: the judgement is detection's, never made on a caller's positions | the flag reaching named positions |
| fluorite.prn: the picture | ``tests/output/peaks_tail_shoulder_fluorite.png`` with the 46.92 deg shoulder under the fluorite (220) line | — |
| synthetic, a pure axial tail (the negative arm) and no tail (its control) | no component below a strong line without the tail; with it, shoulders 0.6-1.0 FWHM below and 4-14x weaker, some taken by the rule | a shoulder with no tail in the data, or the rule taking none (or all) of the tail's shoulders |
| synthetic, a real weak line planted below a strong one (the positive arm) | at 0.62 and 0.95 FWHM below, the real line carries ``axial_tail`` and stays usable; at 0.75 FWHM, where the tail's shoulder sits, the rule takes it | the rule widened to ``axial_tail`` alone (the two kept lines go), or the measured cost gone unexplained |

Real data for the first four rows: the round robin (``tests/data/qarr``) and
SRM 1976a (``tests/data/srm1976a_corundum_xpert.xy``), each with its
acceptance suite's own instrument.  WP-2120's handover carries the lattice
distances behind the choice; this file pins the flag's logic and the census
it moved.  The last two rows are synthetic (fluorite through the package's
own forward model); WP-2120's findings carry the full sweep they sample.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.symmetry import generate_reflections
from rietx.indexing.pick import pick_peaks_with_state
from rietx.model.forward import PAWLEY_OVERLAP_FWHM_FRAC
from rietx.schemas.indexing import PEAK_UNUSABLE_FLAGS
from tests.peak_pictures import draw_pick

pytestmark = pytest.mark.xdist_group("peak_tail_shoulder")


def _qarr_pick(name: str):
    from tests.test_acceptance_qpa_roundrobin import DATA, qarr_instrument
    path = DATA / name
    if not path.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(path)
    ins = qarr_instrument()
    return (data, ins, *pick_peaks_with_state(data, ins))


def _mate(fits, p):
    """The strongest component of ``p``'s group: its position, area, FWHM."""
    fit = fits[p.group]
    k = int(np.argmax(fit.intensity))
    return float(fit.two_theta[k]), float(fit.intensity[k]), float(fit.fwhm)


def _taken(pl) -> list:
    """``tail_shoulder`` components that would be usable without it: no other
    unusable flag, and no usable component of another group holding the line
    (it would then be that line's ``duplicate_line`` copy, cpd-2 89.04°)."""
    out = []
    for p in pl.peaks:
        if "tail_shoulder" not in p.flags:
            continue
        rest = set(p.flags) - {"tail_shoulder", "weak_line"}
        tol = PAWLEY_OVERLAP_FWHM_FRAC * p.fwhm
        copy = any(q.usable and q.group != p.group
                   and abs(q.two_theta - p.two_theta) <= tol for q in pl.peaks)
        if not rest & PEAK_UNUSABLE_FLAGS and not copy:
            out.append(p)
    return out


@pytest.mark.slow   # 16 real patterns picked, ~8 s; the two rows below keep the fast tier's arms
def test_the_flag_is_exactly_the_conjunction_on_the_round_robin():
    from tests.test_acceptance_qpa_roundrobin import DATA
    names = sorted(f.name for f in DATA.glob("*.prn"))
    if len(names) != 16:
        pytest.skip("IUCr QPA round-robin dataset not present")
    taken = []
    for name in names:
        _, _, pl, _, fits = _qarr_pick(name)
        for p in pl.peaks:
            both = {"axial_tail", "position_at_bound"} <= set(p.flags)
            assert ("tail_shoulder" in p.flags) == both, (name, p.two_theta, p.flags)
        taken += [(name, p, _mate(fits, p)) for p in _taken(pl)]
    assert len(taken) == 8, [(n, round(p.two_theta, 3)) for n, p, _ in taken]
    for name, p, (tt_m, i_m, fwhm) in taken:
        below = (tt_m - p.two_theta) / fwhm
        assert 0.6 <= below <= 1.0, (name, p.two_theta, below)
        assert 4.0 <= i_m / p.intensity <= 14.0, (name, p.two_theta, i_m / p.intensity)


def test_a_second_instrument_family_loses_the_shoulders_and_keeps_their_lines():
    from tests.test_acceptance_srm1976a_texture import PATTERN, _instrument
    if not PATTERN.exists():
        pytest.skip("SRM 1976a pattern not present")
    data = rx.read_pattern(PATTERN)
    pl, _, _ = pick_peaks_with_state(data, _instrument())
    for shoulder, line in ((52.527, 52.569), (76.836, 76.878)):
        p = min(pl.peaks, key=lambda q: abs(q.two_theta - shoulder))
        assert abs(p.two_theta - shoulder) < 0.005
        assert "tail_shoulder" in p.flags and not p.usable, p.flags
        # the line itself is still offered (at 76.88° by one of two groups
        # that fitted it; the other copy is ``duplicate_line``)
        held = [m for m in pl.peaks if m.usable and abs(m.two_theta - line) < 0.005]
        assert held and all("tail_shoulder" not in m.flags for m in held)
    codes = {d.code: d for d in pl.diagnostics}
    assert "(tail_shoulder) and are excluded from usable()" in codes["PEAK_AXIAL_TAIL"].message
    # the census moved by those two alone: 61.13° is a third ``tail_shoulder``,
    # but another group's usable component holds its line, so it was a
    # ``duplicate_line`` copy and unusable before
    assert len(_taken(pl)) == 2, [round(p.two_theta, 3) for p in _taken(pl)]


def test_the_fluorite_shoulder_is_drawn_under_its_line():
    data, ins, pl, det, fits = _qarr_pick("fluorite.prn")
    lam = pl.wavelength
    rs = generate_reflections("F m -3 m", (5.4631,) * 3 + (90.0,) * 3, lam,
                              pl.two_theta_max)
    truth = np.degrees(2.0 * np.arcsin(lam / (2.0 * np.asarray(rs.d))))
    path = draw_pick("tail_shoulder_fluorite", data, ins, pl, det, fits,
                     truth=truth, zoom=(46.4, 47.6),
                     title="fluorite.prn: the 46.92° tail shoulder below (220), "
                           "flagged tail_shoulder and unusable")
    assert path.exists()
    p = min(pl.peaks, key=lambda q: abs(q.two_theta - 46.918))
    assert "tail_shoulder" in p.flags and not p.usable


def test_a_named_shoulder_is_the_callers_and_is_not_judged():
    from tests.test_acceptance_srm1976a_texture import PATTERN, _instrument
    if not PATTERN.exists():
        pytest.skip("SRM 1976a pattern not present")
    pl = rx.fit_peaks(rx.read_pattern(PATTERN), _instrument(), [52.48, 52.569])
    p = min(pl.peaks, key=lambda q: abs(q.two_theta - 52.51))
    assert p.origin == "manual"
    assert {"axial_tail", "position_at_bound"} <= set(p.flags), p.flags
    assert "tail_shoulder" not in p.flags and p.usable, p.flags


# ---------------------------------------------------------------------------
# The synthetic arms (WP-2120, 2026-11-16): fluorite drawn by the package's own
# forward model with a real axial divergence (FCJ, S/L = H/L), and picked with
# the round-robin instrument, which declares none, as the real lab files are.
# A pure tail is the negative arm; a real weak lattice line planted just below a
# strong one (a second fluorite phase at a(1 + eps), scale 1/r) is the positive
# arm.  Idealised structure, Poisson counts from fixed seeds, no data file read.
# ---------------------------------------------------------------------------

FLUORITE_A = 5.4631
#: the round robin's Kα1, and fluorite's strong lines below 90° 2θ
_HKL = ((1, 1, 1), (2, 2, 0), (3, 1, 1), (4, 0, 0), (3, 3, 1), (4, 2, 2))


def _kalpha1_line(a: float, hkl) -> float:
    from tests.test_acceptance_qpa_roundrobin import qarr_instrument
    lam = float(qarr_instrument().source.lines[0].wavelength.value)
    d = a / np.sqrt(sum(i * i for i in hkl))
    return float(np.degrees(2.0 * np.arcsin(lam / (2.0 * d))))


def _fluorite(a: float, ins) -> np.ndarray:
    from tests._synthetic_weak_lines import _cif, _structure
    cif = _cif("CaF2", 225, "F m -3 m", (a, a, a, 90, 90, 90),
               [("Ca1", "Ca", 0, 0, 0, 1, 0.5), ("F1", "F", 0.25, 0.25, 0.25, 1, 0.7)])
    tt = np.round(np.arange(20.0, 100.0, 0.02), 3)
    return tt, np.asarray(rx.Refinement(_structure(cif), ins,
                                        history=False).predict(two_theta=tt))


def _drawn(axial: float, *, eps: float = 0.0, ratio: float = 0.0):
    """The strong fluorite lines (strongest 1e4 counts on 30) with axial
    divergence ``axial``, plus, when ``ratio``, the planted phase."""
    from tests.test_acceptance_qpa_roundrobin import qarr_instrument
    ins = qarr_instrument()
    ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = axial
    ins.profile.u.value, ins.profile.v.value, ins.profile.w.value = 0.008, -0.004, 0.010
    ins.profile.x.value = 0.04
    tt, y = _fluorite(FLUORITE_A, ins)
    norm = y.max()
    if ratio:
        y = y + _fluorite(FLUORITE_A * (1.0 + eps), ins)[1] / ratio
    return tt, y / norm * 1e4 + 30.0


def _counts(tt, y, seed: int) -> rx.PatternData:
    obs = np.random.default_rng(seed).poisson(y).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1.0))))


def _below_strong(pl, fits):
    """Each component within 4 fitted FWHM below a strong fluorite line:
    (separation in FWHM, strong/component area, component)."""
    out = []
    for hkl in _HKL:
        t = _kalpha1_line(FLUORITE_A, hkl)
        strong = min(pl.peaks, key=lambda p: abs(p.two_theta - t))
        fw = float(fits[strong.group].fwhm)
        for p in pl.peaks:
            sep = (strong.two_theta - p.two_theta) / fw
            if p is not strong and 0.0 < sep < 4.0:
                out.append((sep, strong.intensity / p.intensity, p))
    return out


def _taken_by_the_rule(p) -> bool:
    """``tail_shoulder`` is the only flag keeping ``p`` out of ``usable()``."""
    rest = set(p.flags) - {"tail_shoulder", "weak_line"}
    return "tail_shoulder" in p.flags and not rest & PEAK_UNUSABLE_FLAGS


def test_a_pure_axial_tail_leaves_a_shoulder_the_rule_takes_in_part():
    """The negative arm, and its control.  Without axial divergence nothing
    sits below a strong line (3 seeds).  With S/L = H/L = 0.03 the unmodelled tail leaves
    shoulders where the real ones sit (0.6-1.0 FWHM below, 4-14x weaker), and
    the rule takes some of them, not all: on 20 seeds, 5 of the 19 that would
    be usable (macOS arm64 and Linux x86_64 alike; WP-2120's handover)."""
    from tests.test_acceptance_qpa_roundrobin import qarr_instrument
    tt, y = _drawn(0.0)
    for seed in range(500, 503):
        pl, _, fits = pick_peaks_with_state(_counts(tt, y, seed), qarr_instrument())
        assert not _below_strong(pl, fits), seed
    tt, y = _drawn(0.03)
    taken, left = [], []
    for seed in range(500, 520):
        pl, _, fits = pick_peaks_with_state(_counts(tt, y, seed), qarr_instrument())
        for sep, ratio, p in _below_strong(pl, fits):
            if "axial_tail" not in p.flags:
                continue
            if _taken_by_the_rule(p):
                taken.append((sep, ratio))
            elif p.usable:
                left.append((sep, ratio))
    assert (len(taken), len(left)) == (5, 14), (taken, left)
    for sep, ratio in taken + left:
        assert 0.6 <= sep <= 1.0 and 4.0 <= ratio <= 14.0, (sep, ratio)


def test_a_real_weak_line_below_a_strong_one_is_kept_or_taken_by_where_it_sits():
    """The positive arm: a second fluorite phase 0.165 % larger, at 1/5 of the
    host's scale, puts a real lattice line below every strong line.  In one
    pattern, the line 0.95 FWHM below (400) carries ``axial_tail`` and stays
    usable (the flag alone takes nothing), and the line 0.62 FWHM below (220)
    does too.  The line 0.75 FWHM below (311), where the pure tail's shoulder
    sits, is a real line the rule takes: the measured cost, 16 of 112 resolved
    planted lines at 0.6-1.0 FWHM and ratios 5-14 (WP-2120's open question)."""
    from tests.test_acceptance_qpa_roundrobin import qarr_instrument
    eps = 0.00165
    tt, y = _drawn(0.03, eps=eps, ratio=5.0)
    data = _counts(tt, y, 5)
    ins = qarr_instrument()
    pl, det, fits = pick_peaks_with_state(data, ins)
    seen = {}
    for hkl in ((2, 2, 0), (3, 1, 1), (4, 0, 0)):
        ts, tw = _kalpha1_line(FLUORITE_A, hkl), _kalpha1_line(FLUORITE_A * (1 + eps), hkl)
        strong = min(pl.peaks, key=lambda p: abs(p.two_theta - ts))
        assert strong.usable and abs(strong.two_theta - ts) < 0.03, strong
        fw = float(fits[strong.group].fwhm)
        p = min((q for q in pl.peaks if q is not strong),
                key=lambda q: abs(q.two_theta - tw))
        assert abs(p.two_theta - tw) < 0.2 * fw, (hkl, p.two_theta, tw)
        seen[hkl] = ((ts - tw) / fw, p)
    for hkl in ((2, 2, 0), (4, 0, 0)):
        sep, p = seen[hkl]
        assert "axial_tail" in p.flags and p.usable, (hkl, sep, p.flags)
    sep, p = seen[(3, 1, 1)]
    assert 0.7 < sep < 0.8 and _taken_by_the_rule(p), (sep, p.flags)
    tw = _kalpha1_line(FLUORITE_A * (1 + eps), (3, 1, 1))
    path = draw_pick("tail_shoulder_planted", data, ins, pl, det, fits,
                     truth=[_kalpha1_line(FLUORITE_A, (3, 1, 1)), tw], zoom=(55.2, 56.2),
                     title="synthetic fluorite + a real line 0.75 FWHM below (311): "
                           "taken as tail_shoulder")
    assert path.exists()
