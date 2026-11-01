"""The picker's component count by resolvability (``unresolved_split``,
``width_capped``; issue #934, design F2 § 4 C2).

Interpretation table, written before the tests were (each arm can fail):

| arm | must read if the rule works | reading if it is broken |
|---|---|---|
| two equal Gaussian lines 0.6 FWHM apart (below Sparrow's 0.85) | one usable line per pair, its σ(2θ) reaching the partner; the partner ``unresolved_split`` | two precise positions the data cannot resolve |
| the same at 1.2 FWHM (control) | two usable lines per pair, nothing merged | a resolved pair merged: the limit is not Sparrow's |
| #728's flat-topped silicon (each line three copies 0.012° apart) | one unflagged usable line on ≥ 10 of 11 silicon lines (2–4 each before) | the split survives |
| #728's steep background | the flank components are ``width_capped``; ≤ 6 off-lattice usable (26 before; ≤ 4 was the bar written first, and 6 is what this rule alone leaves: two re-seeds absorbing a background misfit at I/σ_I 7.4, three tail components at I/σ_I 2.0–3.2 that C1's false-discovery bar flags, one at the extrapolated edge); every silicon line usable | junk survives, or a silicon line is capped |
| corundum (IUCr CPD, SRM 676a), 61.08° and 61.25°: two real reflections 1.08 FWHM apart at an area ratio of 0.63, the lower's Kα2 on the upper | both usable, neither merged; no ``width_capped`` anywhere on the pattern | the dip judged on fitted areas or with the Kα2 images: real lines merged (measured: both earlier forms merged them) |
| a merged line's extent in the duplicate screen | another group's copy within the extent is ``duplicate_line`` | a merged line and its copy both offered |

Synthetic data plus one public IUCr round-robin pattern.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.indexing.pick import flag_duplicate_lines, pick_peaks_with_state
from rietx.schemas.indexing import ObservedPeak
from tests.peak_pictures import draw_pick

LAM = 0.825739
SI_CIF = ("data_Si\n_cell_length_a 5.4311\n_cell_length_b 5.4311\n_cell_length_c 5.4311\n"
          "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
          "_space_group_IT_number 227\n_symmetry_space_group_name_H-M 'F d -3 m'\n"
          "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
          "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
          "Si1 Si 0.125 0.125 0.125 0.5\n")
RANGE = (12.1, 60.0)


def _si_lines() -> np.ndarray:
    out = set()
    for h in range(9):
        for k in range(h + 1):
            for ell in range(k + 1):
                par = {h % 2, k % 2, ell % 2}
                if (h, k, ell) == (0, 0, 0) or len(par) != 1:
                    continue
                if par == {0} and (h + k + ell) % 4:
                    continue
                s = LAM * np.sqrt(h * h + k * k + ell * ell) / (2 * 5.4311)
                if s < 1:
                    out.add(round(2 * np.degrees(np.arcsin(s)), 4))
    t = np.array(sorted(out))
    return t[(t > RANGE[0]) & (t < RANGE[1])]


def _silicon_728(tmp_path, *, steep: bool, split: float) -> rx.PatternData:
    """#728's public generator: synthetic silicon, each line ``split``-copied
    (a flat top) and optionally on a background falling 3× over 12–23°."""
    path = tmp_path / "si.cif"
    path.write_text(SI_CIF, encoding="utf-8")
    s = rx.Structure.from_cif(str(path))
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    tt = np.round(np.arange(12.088, 102.1161, 0.004), 3)
    ref = rx.Refinement(s, ins, history=False)
    y = sum(ref.predict(two_theta=tt + d) for d in ((-split, 0.0, split) if split else (0.0,)))
    y = y / y.max() * 1.3e6
    bg = 7700 + (16000 * np.exp(-(tt - 12) / 6) if steep else 0.0)
    obs = np.random.default_rng(1).poisson(y + bg).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))


def _pairs(sep_fwhm: float, fwhm: float = 0.05):
    data, centres = _pairs_data(sep_fwhm, fwhm)
    return rx.pick_peaks(data, rx.Instrument.debye_scherrer(wavelength=0.8)), centres


def _pairs_data(sep_fwhm: float, fwhm: float = 0.05):
    tt = np.round(np.arange(10.0, 40.0, 0.005), 3)
    s = fwhm / 2.3548
    centres = [15.0, 20.0, 25.0, 30.0, 35.0]
    y = np.full_like(tt, 500.0)
    for c in centres:
        for x in (c, c + sep_fwhm * fwhm):
            y = y + 20000.0 * np.exp(-0.5 * ((tt - x) / s) ** 2)
    obs = np.random.default_rng(4).poisson(y).astype(float)
    data = rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))
    return data, centres


def _in_pair(pl, c, sep, fwhm=0.05):
    return [p for p in pl.usable() if c - fwhm < p.two_theta < c + sep * fwhm + fwhm]


def test_a_pair_below_sparrows_limit_is_one_line_and_above_it_two():
    sep = 0.6
    pl, centres = _pairs(sep)
    for c in centres:
        line = _in_pair(pl, c, sep)
        assert len(line) == 1, [p.two_theta for p in line]
        # σ reaches the partner: a ±σ window covers both positions
        assert line[0].two_theta_esd >= 0.9 * sep * 0.05
    assert sum("unresolved_split" in p.flags for p in pl.peaks) == len(centres)
    sep = 1.2
    pl, centres = _pairs(sep)
    for c in centres:
        assert len(_in_pair(pl, c, sep)) == 2
    assert not any("unresolved_split" in p.flags for p in pl.peaks)


def test_flat_topped_lines_are_reported_once(tmp_path):
    """#728 arm c1: 34 usable components on 11 silicon lines before, 2–4 per
    line, the split ones 0.012° apart on a 0.020° fitted width at I/σ_I
    50–200 — well measured, and ΔBIC pays for every one.

    The usable count carries the flank components beside the eleven lines.
    It was 18 while a prediction drew 2 % windows, and is 20 since it draws
    every Lorentzian tail (WP-2002).  The flank components went from 7 to 9,
    and from 3 to 8 of them flagged ``weak_line``; the strongest fell from
    I/σ_I 10.4 to 4.5.  Each line still keeps exactly one."""
    truth = _si_lines()
    data = _silicon_728(tmp_path, steep=False, split=0.012)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    pl, det, fits = pick_peaks_with_state(data, ins, two_theta_range=RANGE)
    draw_pick("resolvability_flat_top", data, ins, pl, det, fits, truth=truth,
              title="#728 arm c1: each silicon line three copies 0.012 deg apart")
    use = pl.usable()
    tt = np.array([p.two_theta for p in use])
    per = [int(np.sum(np.abs(tt - t) <= 0.03)) for t in truth]
    assert sum(n == 1 for n in per) >= 10 and min(per) >= 1, per
    assert len(use) <= 20
    assert sum("unresolved_split" in p.flags for p in pl.peaks) >= 15


def test_a_steep_flank_is_capped_not_listed(tmp_path):
    """#728 arm c2: the components a 3× fall in background leaves on the flank
    fit to widths five times the pattern's own width law and more."""
    truth = _si_lines()
    data = _silicon_728(tmp_path, steep=True, split=0.0)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    pl, det, fits = pick_peaks_with_state(data, ins, two_theta_range=RANGE)
    draw_pick("resolvability_steep_flank", data, ins, pl, det, fits, truth=truth,
              title="#728 arm c2: the flank's components capped at five times the width law")
    use = pl.usable()
    tt = np.array([p.two_theta for p in use])
    assert all(np.any(np.abs(tt - t) <= 0.03) for t in truth)
    off = [t for t in tt if np.min(np.abs(truth - t)) > 0.04]
    assert len(off) <= 6, off
    assert sum("width_capped" in p.flags for p in pl.peaks) >= 100
    assert "PEAK_WIDTH_CAPPED" in {d.code for d in pl.diagnostics}


def test_two_real_reflections_a_doublet_apart_stay_two_lines():
    """The control on real data.  At 61.08° and 61.25° corundum has two
    reflections 1.08 FWHM apart at an area ratio of 0.63; the lower one's Kα2
    lands on the upper, so the fitted curve has no dip.  Judged on fitted
    areas, or with the Kα2 images drawn, the pair was merged; judged as
    Sparrow asks — two equal Kα1 lines at that separation — it is resolved."""
    from tests.test_acceptance_qpa_roundrobin import DATA as QARR
    from tests.test_acceptance_qpa_roundrobin import qarr_instrument

    path = QARR / "corundum.prn"
    if not path.is_file():
        pytest.skip("IUCr round-robin corundum pattern not present")
    pl = rx.pick_peaks(rx.read_pattern(path), qarr_instrument())
    near = [p for p in pl.usable() if 61.0 < p.two_theta < 61.35]
    assert len(near) == 2, [(p.two_theta, p.flags) for p in near]
    assert not any("width_capped" in p.flags for p in pl.peaks)


def _peak(tt, group, esd=1e-3, flags=()):
    return ObservedPeak(two_theta=tt, two_theta_esd=esd, intensity=100.0,
                        intensity_esd=1.0, q=0.1, q_esd=1e-5, fwhm=0.05,
                        eta=0.5, group=group, n_in_group=2, chi2_red=1.0,
                        flags=list(flags))


def test_a_merged_lines_copy_is_a_duplicate_anywhere_on_its_extent():
    # group 0 reports 20.000 with a merged component at 20.030; group 1 fitted
    # 20.035, outside half a FWHM of 20.000 but on the merged line
    peaks = [_peak(20.0, 0, esd=0.03), _peak(20.03, 0, flags=["unresolved_split"]),
             _peak(20.035, 1, esd=0.04)]
    flag_duplicate_lines(peaks)
    assert "duplicate_line" in peaks[2].flags
    assert "duplicate_line" not in peaks[0].flags
    # without the merge it is a line of its own, as before
    peaks = [_peak(20.0, 0, esd=0.03), _peak(20.035, 1, esd=0.04)]
    flag_duplicate_lines(peaks)
    assert not any("duplicate_line" in p.flags for p in peaks)


# --- review round 1 (yue-here, #948) ----------------------------------------

def _triples(sep_fwhm: float, fwhm: float = 0.05, n: int = 3):
    """Equal Gaussian lines ``sep_fwhm`` FWHM apart, ``n`` per cluster."""
    tt = np.round(np.arange(10.0, 30.0, 0.005), 3)
    s = fwhm / 2.3548
    y = np.full_like(tt, 500.0)
    for k in range(n):
        y = y + 20000.0 * np.exp(-0.5 * ((tt - (20.0 + k * sep_fwhm * fwhm)) / s) ** 2)
    obs = np.random.default_rng(4).poisson(y).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))


def _judged_group(data, ins):
    from rietx.indexing.peakfit import fit_group
    from rietx.indexing.peaks import detect_peaks

    det = detect_peaks(data, ins)
    group = max(det.groups, key=lambda g: g.n)
    return det, group, fit_group(det, group, ins)


def test_a_caller_named_pair_is_never_merged_and_a_broad_sample_never_capped():
    """``fit_peaks`` and the editor's ``fit_group_at`` fit exactly the
    caller's positions: the two judgements are detection's, and are not made
    there (#948 review item 3)."""
    data, centres = _pairs_data(0.6)
    ins = rx.Instrument.debye_scherrer(wavelength=0.8)
    named = [x for c in centres for x in (c, c + 0.03)]
    pl = rx.fit_peaks(data, ins, named)
    assert len(pl.peaks) == len(named)
    assert all("unresolved_split" not in p.flags and "width_capped" not in p.flags
               for p in pl.peaks)
    # the same pattern through detection *is* judged: the control arm
    pl = rx.pick_peaks(data, ins)
    assert any("unresolved_split" in p.flags for p in pl.peaks)


def test_an_unjudged_fit_says_so_rather_than_not_capped():
    """``width_at_bound`` and ``merged_into`` are ``None`` where nothing judged
    (the declared-name rule): never a ``False`` that reads "not capped"."""
    from rietx.indexing.peakfit import fit_group_at

    ins = rx.Instrument.debye_scherrer(wavelength=0.8)
    from rietx.indexing.peaks import detect_peaks
    det = detect_peaks(_triples(0.5, n=2), ins)
    g = det.groups[0]
    fit = fit_group_at(det, g, ins, g.seed_two_theta)
    assert fit.width_at_bound is None and fit.merged_into is None
    _det, _g, judged = _judged_group(_triples(0.5, n=2), ins)
    assert judged.width_at_bound is False and judged.merged_into is not None


def test_a_line_that_absorbed_a_split_is_ranked_by_its_own_esd():
    """Review item 1: the widened σ of a merged line must not demote it below
    another group's re-seeded copy of the same line."""
    real = _peak(20.0, 0, esd=0.05)             # widened to reach its split
    real.two_theta_esd_fit = 0.003
    split = _peak(20.03, 0, flags=["unresolved_split"])
    copy = _peak(20.002, 1, esd=0.01)
    peaks = [real, split, copy]
    flag_duplicate_lines(peaks)
    assert "duplicate_line" in copy.flags
    assert "duplicate_line" not in real.flags
