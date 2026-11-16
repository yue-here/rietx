"""A tail shoulder on its position bound is not offered as a line (WP-2120).

A component carrying both ``axial_tail`` (a weak group-mate on a much stronger
line's axial-divergence tail side) and ``position_at_bound`` (the fit pushed it
to its position bound, so the data fixed no position for it) is flagged
``tail_shoulder`` and leaves ``usable()``.  Neither flag alone does.

Interpretation table, written before the tests were (each arm can fail):

| arm | must read if it works | reading if it is broken |
|---|---|---|
| the 16 IUCr round-robin lab patterns | ``tail_shoulder`` on exactly the components carrying both flags; none usable; 8 of them would otherwise be usable (no other unusable flag, no other group's usable copy), each 0.6-1.0 fitted FWHM below a usable group-mate 4-14x its area | the flag missing from the conjunction, raised without it, or a usable line taken that is not a shoulder of its mate |
| the same, the other flags | every component carrying only one of the two is still usable unless another flag says otherwise | the rule widened to ``axial_tail`` or ``position_at_bound`` alone |
| SRM 1976a on an X'Pert (a second instrument family) | the two shoulders at 52.53 deg and 76.84 deg flagged and unusable; a usable component still holds each mate's line, 52.57 deg and 76.88 deg | the rule fails to carry to a narrower-line instrument, or takes the strong line |
| the same shoulder **named** (``fit_peaks``, a negative arm) | ``axial_tail`` and ``position_at_bound`` both raised, ``tail_shoulder`` not, and the line usable: the judgement is detection's, never made on a caller's positions | the flag reaching named positions |
| fluorite.prn: the picture | ``tests/output/peaks_tail_shoulder_fluorite.png`` with the 46.92 deg shoulder under the fluorite (220) line | — |

Real data only: the round robin (``tests/data/qarr``) and SRM 1976a
(``tests/data/srm1976a_corundum_xpert.xy``), each with its acceptance suite's
own instrument.  WP-2120's handover carries the lattice distances behind the
choice; this file pins the flag's logic and the census it moved.
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
