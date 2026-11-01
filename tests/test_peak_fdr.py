"""The peak list's null: a per-pattern false-discovery threshold and the
expected number of false lines it reports (``weak_line``,
``PEAK_EXPECTED_FALSE_LINES``; issue #934, design F2 § 4 C1).

Interpretation table, written before the tests were (each arm can fail):

| arm | must read if the threshold works | reading if it is broken |
|---|---|---|
| BH arithmetic (hand-built p-values) | k* = 4 of 6; the step-up keeps a p-value above its own rank's bar when a later rank passes | a step-down or a per-line bar: the wrong count |
| null pattern, flat and sloped (T11) | 0 usable lines; ``PEAK_EXPECTED_FALSE_LINES`` value 0, bar at the Bonferroni q/m | any usable line on a line-free pattern |
| #728's steep-background silicon (T3) | every true line keeps exactly one unflagged component; ≤ 2 off-lattice components escape the flag (26 off-lattice usable, none flagged, before) | junk unflagged (threshold on the wrong statistic) or a true line flagged (threshold too high) |
| F2's M3 clean silicon | 0 off-lattice unflagged (3 before), no silicon line flagged | the same |
| the flag is reported, not refused | every ``weak_line`` component stays in ``usable()`` | refusing real weak lines: measured, five indexing-acceptance rows move |
| planted lines at I/σ_I 8–60 (control) | all ten usable, none flagged; the diagnostic reports q × 10 | a real, detected line is flagged: the bar is above what detection itself demands |
| a named position (``fit_peaks``) | never flagged ``weak_line``, no diagnostic | a person's claim is overruled by a detection statistic |

Synthetic data only: silicon (F d -3 m, a = 5.4311 Å) through the package's own
forward model with Poisson noise, the generator of #728's public reproducer and
of F2's M3 measurement, and Gaussian lines on a flat background.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import ndtr, ndtri

import rietx as rx
from rietx.indexing.peaks import Detection, fdr_screen
from rietx.indexing.pick import flag_weak_lines, pick_peaks_with_state
from rietx.schemas.indexing import PEAK_FDR_Q, ObservedPeak
from tests.peak_pictures import draw_pick

LAM = 0.825739
SI_CIF = ("data_Si\n_cell_length_a 5.4311\n_cell_length_b 5.4311\n_cell_length_c 5.4311\n"
          "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
          "_space_group_IT_number 227\n_symmetry_space_group_name_H-M 'F d -3 m'\n"
          "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
          "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
          "Si1 Si 0.125 0.125 0.125 0.5\n")
RANGE = (12.1, 60.0)


def _si_lines(lo: float = RANGE[0], hi: float = RANGE[1]) -> np.ndarray:
    """2θ of every allowed Si reflection at λ = 0.825739 Å in [lo, hi]."""
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
    return t[(t > lo) & (t < hi)]


def _silicon(tmp_path, *, steep: bool, hi: float, seed: int = 1,
             window_area_tol: float | None = None) -> rx.PatternData:
    """Silicon drawn by ``predict``, at the closing stage's windows, or at
    ``window_area_tol`` when one is given."""
    path = tmp_path / "si.cif"
    path.write_text(SI_CIF, encoding="utf-8")
    s = rx.Structure.from_cif(str(path))
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    tt = np.round(np.arange(12.088, hi, 0.004), 3)
    if window_area_tol is None:
        y = rx.Refinement(s, ins, history=False).predict(two_theta=tt)
    else:
        from rietx.model.forward import compile_model
        from rietx.params.vector import ParameterTable

        grid = rx.PatternData(two_theta=list(tt), intensity=[0.0] * len(tt))
        model = compile_model(s, ins, grid, window_area_tol=window_area_tol)
        table = ParameterTable(s, ins)
        y = np.asarray(model.evaluate(table.decode(table.x0())))
    y = y / y.max() * 1.3e6
    bg = 7700 + (16000 * np.exp(-(tt - 12) / 6) if steep else 0.0)
    obs = np.random.default_rng(seed).poisson(y + bg).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))


def _count(pl: rx.PeakList, truth: np.ndarray) -> tuple[list[int], int]:
    """Usable components the false-discovery bar did not flag, within one FWHM
    of each true line, and those farther than 1.5 FWHM from every true line
    (off-lattice)."""
    use = [p for p in pl.usable() if "weak_line" not in p.flags]
    tt = np.array([p.two_theta for p in use])
    fw = np.array([max(p.fwhm, 0.025) for p in use])
    per = [int(np.sum(np.abs(tt - t) <= fw)) for t in truth]
    off = int(sum(1 for t, w in zip(tt, fw) if np.min(np.abs(truth - t)) > 1.5 * w))
    return per, off


def _diag(pl: rx.PeakList):
    hits = [d for d in pl.diagnostics if d.code == "PEAK_EXPECTED_FALSE_LINES"]
    assert len(hits) == 1, [d.code for d in pl.diagnostics]
    return hits[0]


def _peak(i_over_s: float, *, origin="fitted", flags=()) -> ObservedPeak:
    return ObservedPeak(two_theta=20.0, two_theta_esd=0.001, intensity=i_over_s,
                        intensity_esd=1.0, q=0.1, q_esd=1e-5, fwhm=0.05, eta=0.5,
                        group=0, n_in_group=1, chi2_red=1.0, flags=list(flags),
                        origin=origin)


def _detection(n_trials: float) -> Detection:
    x = np.linspace(10.0, 20.0, 50)
    return Detection(x, x, x, x, [], 0.05, 0.05, 1.0, 0, np.zeros(0), n_trials)


def test_the_threshold_is_benjamini_hochberg_step_up_over_the_patterns_trials():
    # m = 100, q = 0.01: rank k passes at p ≤ k·1e-4.  I/σ 10, 5, 4, 3.5 pass
    # (3.5 → p = 2.3e-4 ≤ 4e-4); 3 and 2 fail.
    peaks = [_peak(z) for z in (3.0, 10.0, 2.0, 4.0, 5.0, 3.5)]
    s = fdr_screen(peaks, _detection(100.0))
    assert (s.n_tested, s.n_kept) == (6, 4)
    assert s.weak == (0, 2)
    assert s.z_threshold == pytest.approx(-ndtri(4 * PEAK_FDR_Q / 100.0))
    assert s.expected_false == pytest.approx(4 * PEAK_FDR_Q)
    # the step-up: ranks 2 and 3 sit above their own bars (2e-4, 3e-4) and are
    # kept because rank 4 passes; a per-line or step-down rule drops them
    z = [float(-ndtri(p)) for p in (1e-5, 2.9e-4, 3.5e-4, 3.9e-4)]
    s = fdr_screen([_peak(v) for v in z], _detection(100.0))
    assert (s.n_kept, s.weak) == (4, ())
    assert ndtr(-z[1]) > 2 * PEAK_FDR_Q / 100.0


def test_what_the_screen_tests_and_what_it_leaves_alone():
    det = _detection(1000.0)
    peaks = [_peak(50.0), _peak(1.5), _peak(1.5, origin="manual"),
             _peak(1.5, flags=["no_intensity"]), _peak(1.5, flags=["weak_line"])]
    s = fdr_screen(peaks, det)
    # a person's position and a line already unusable for another reason are
    # not hypotheses; a line already flagged weak_line is, so the screen reads
    # the same before and after it has flagged
    assert s.n_tested == 3 and s.weak == (1, 4)
    # m is never smaller than the number tested
    assert fdr_screen(peaks, _detection(1.0)).n_trials == 3.0
    # the editor's restriction: the bar is the whole list's, the marks are only
    # the refitted group's
    flag_weak_lines(peaks, det, only={4})
    assert "weak_line" not in peaks[1].flags and peaks[4].flags == ["weak_line"]


@pytest.mark.parametrize("slope", [0.0, 2.0])
def test_a_line_free_pattern_keeps_no_line_and_says_so(slope):
    tt = np.round(np.arange(12.088, 62.0, 0.004), 3)
    mu = 7700.0 * (1.0 + slope * (tt - tt[0]) / (tt[-1] - tt[0]))
    obs = np.random.default_rng(3).poisson(mu).astype(float)
    data = rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    pl = rx.pick_peaks(data, ins, two_theta_range=RANGE)
    d = _diag(pl)
    assert pl.peaks == [] and d.value == 0.0
    # nothing kept, so the bar is the Bonferroni one a first line would need
    m = float(d.message.split(" over ")[1].split()[0])
    assert f"I/σ_I ≥ {-ndtri(PEAK_FDR_Q / m):.2f}" in d.message


def test_steep_background_junk_fails_the_patterns_bar_and_no_true_line_does(tmp_path):
    """#728 arm c2: a background falling 3× over 12–23° under synthetic
    silicon.  Before the resolvability rule (#934) 37 usable components, 24 of
    them more than 1.5 FWHM from every silicon line at I/σ_I 1.0–1.5 (maxima on
    the flank the envelope under-tracks), all 24 flagged; the two left
    unflagged are I/σ_I 7.4 re-seeds that absorb a background misfit, which no
    statistical threshold reaches.  With it most flank components leave
    usable() as width_capped before the bar sees them: 17 usable,
    4 of them below the bar."""
    truth = _si_lines()
    data = _silicon(tmp_path, steep=True, hi=102.1161)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    pl, det, fits = pick_peaks_with_state(data, ins, two_theta_range=RANGE)
    draw_pick("fdr_steep_silicon", data, ins, pl, det, fits, truth=truth,
              title="#728 arm c2: silicon on a background falling 3x over 12-23 deg")
    per, off = _count(pl, truth)
    assert per == [1] * len(truth)
    assert off <= 2
    d = _diag(pl)
    weak = [p for p in pl.peaks if "weak_line" in p.flags]
    kept = [p for p in pl.usable() if "weak_line" not in p.flags]
    assert len(weak) >= 3 and d.value == pytest.approx(PEAK_FDR_Q * len(kept))
    # reported, not refused: every flagged component is still offered
    assert all(p.usable for p in weak)


def test_tail_maxima_on_a_clean_pattern_fail_the_bar(tmp_path):
    """F2's M3 arm: clean synthetic silicon (flat 7700 counts, strongest line
    1.3e6).  18 usable: three off-lattice maxima on strong lines' tails and
    four tail re-seeds within a FWHM of a silicon line (0.018–0.070° from it,
    in groups of their own), all at I/σ_I 1.4–2.6, against ≥ 371 for every
    silicon line.  All seven are flagged."""
    truth = _si_lines()
    data = _silicon(tmp_path, steep=False, hi=62.0)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    pl, det, fits = pick_peaks_with_state(data, ins, two_theta_range=RANGE)
    draw_pick("fdr_flat_silicon", data, ins, pl, det, fits, truth=truth,
              title="#916's flat silicon: tail maxima under the false-discovery bar")
    per, off = _count(pl, truth)
    assert per == [1] * len(truth) and off == 0
    kept = [p for p in pl.usable() if "weak_line" not in p.flags]
    assert len(kept) == len(truth)


def test_planted_lines_detection_found_are_never_refused():
    """The control: ten Gaussian lines on a flat 2000-count background, eight
    at I/σ_I ≈ 60 and two at ≈ 8.  A line detection's own 5σ found and the fit
    measured is far above the bar (≈ 3.5 here); flagging one would mean the
    threshold is stricter than detection."""
    tt = np.round(np.arange(10.0, 70.0, 0.01), 3)
    pos = [14.0, 19.0, 23.5, 28.0, 33.0, 38.5, 44.0, 49.0, 54.5, 60.0]
    hts = [3000.0] * 8 + [400.0, 400.0]
    y = 2000.0 + sum(h * np.exp(-0.5 * ((tt - p) / (0.08 / 2.3548)) ** 2)
                     for h, p in zip(hts, pos))
    obs = np.random.default_rng(5).poisson(y).astype(float)
    data = rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))
    pl = rx.pick_peaks(data, rx.Instrument.debye_scherrer(wavelength=1.5406))
    assert len(pl.usable()) == 10
    assert not any("weak_line" in p.flags for p in pl.peaks)
    assert min(p.intensity / p.intensity_esd for p in pl.usable()) > 6.0
    assert _diag(pl).value == pytest.approx(10 * PEAK_FDR_Q)


def test_a_named_position_is_never_held_to_the_detection_bar():
    tt = np.round(np.arange(10.0, 40.0, 0.01), 3)
    y = 2000.0 + 3000.0 * np.exp(-0.5 * ((tt - 20.0) / 0.034) ** 2)
    obs = np.random.default_rng(2).poisson(y).astype(float)
    data = rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))
    pl = rx.fit_peaks(data, rx.Instrument.debye_scherrer(wavelength=1.5406),
                      [20.0, 30.0])
    assert not any("weak_line" in p.flags for p in pl.peaks)
    assert "PEAK_EXPECTED_FALSE_LINES" not in {d.code for d in pl.diagnostics}


def test_the_flag_follows_the_bar_in_both_directions():
    det = _detection(1000.0)
    peaks = [_peak(50.0), _peak(1.5, flags=["weak_line"]), _peak(40.0, flags=["weak_line"])]
    # ``only`` fences what may be touched either way; without it a stale flag on
    # a line that now clears the bar is cleared and a missing one is set
    flag_weak_lines(peaks, det, only={0, 1})
    assert peaks[1].flags == ["weak_line"] and peaks[2].flags == ["weak_line"]
    flag_weak_lines(peaks, det)
    assert peaks[2].flags == [] and peaks[1].flags == ["weak_line"]


def _two_group_pattern():
    tt = np.round(np.arange(10.0, 70.0, 0.01), 3)
    pos = [14.0, 19.0, 23.5, 28.0, 33.0, 38.5, 44.0, 49.0, 54.5, 60.0]
    y = 2000.0 + sum(3000.0 * np.exp(-0.5 * ((tt - p) / (0.08 / 2.3548)) ** 2)
                     for p in pos)
    obs = np.random.default_rng(5).poisson(y).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1))))


def test_an_edit_re_marks_every_line_and_the_diagnostic_names_what_is_flagged():
    """Yue's review of #947, item 1: the one-group refit used to add the flag
    only inside the refitted group, so a stale flag elsewhere survived the edit
    and the diagnostic named a line the list no longer flagged."""
    from rietx.gui.peaks import _spliced
    from rietx.indexing.pick import pick_peaks_with_state
    pl, det, _ = pick_peaks_with_state(
        _two_group_pattern(), rx.Instrument.debye_scherrer(wavelength=1.5406))
    assert not any("weak_line" in p.flags for p in pl.peaks)
    stale = pl.peaks[-1]
    stale.flags = [*stale.flags, "weak_line"]
    g = pl.peaks[0].group
    assert stale.group != g
    out = _spliced(pl, g, [p for p in pl.peaks if p.group == g], det)
    assert not any("weak_line" in p.flags for p in out.peaks)
    flagged = {f"{p.two_theta:.4f}°" for p in out.peaks if "weak_line" in p.flags}
    assert set(_diag(out).where) == flagged
    # deleting a group moves the bar too, and must re-mark as well
    stale = out.peaks[-1]
    stale.flags = [*stale.flags, "weak_line"]
    gone = _spliced(out, g, [], det)
    assert not any("weak_line" in p.flags for p in gone.peaks)


def test_an_excluded_band_adds_no_trials():
    """Yue's review of #947, item 2: the removed channels leave one large step,
    which the sum divided by one FWHM and counted as 15°/FWHM trials never
    searched."""
    from rietx.indexing.peaks import detect_peaks
    data = _two_group_pattern()
    ins = rx.Instrument.debye_scherrer(wavelength=1.5406)
    full = detect_peaks(data, ins).n_trials
    data.excluded_regions = [(30.0, 45.0)]
    cut = detect_peaks(data, ins).n_trials
    # the width law is nearly flat over 10-70°, so removing 15° of the 60°
    # takes about a quarter of the trials; the old sum took almost none
    assert 0.70 < cut / full < 0.80
