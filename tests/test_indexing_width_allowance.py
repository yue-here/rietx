"""The search allowance from the data (indexing chunk C6).

When no shift is declared or measured, the search used to add a constant
0.05° 2θ to every line's σ — two to six FWHM on a high-resolution pattern.  A
picked list now supplies its own: the lower-quartile fitted FWHM, capped at
that 0.05°.  The shift is still unmeasured, so ``INDEX_SHIFT_ALLOWANCE`` still
fires and still caps the grade; what moves is the window.

Interpretation table, written before the tests were run:

==============================  ======================================  ======================================
behaviour                       positive arm (must read)                negative / control arm (must read)
==============================  ======================================  ======================================
the window follows the widths   a picked list of 0.02° lines: the       a position-only list (assumed widths)
                                allowance is its lower-quartile FWHM,   and a lab list (0.2° lines) both stay
                                and the diagnostic says it came from    at 0.05°; a declared or pair-measured
                                the widths                              allowance wins over the widths
end to end (slow)               synthetic Si twin of T5, FWHM 0.021°:   —
                                the truth is rank 1 with no shift and
                                with a 100 µm displacement the pair
                                screen cannot name
==============================  ======================================  ======================================
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.indexing.engines import (
    DEFAULT_UNKNOWN_SHIFT_DEG,
    SearchSpec,
    effective_shift_allowance,
    match_window,
    shift_allowance_diagnostic,
    width_allowance,
)
from rietx.schemas.indexing import PeakList, ShiftScreen

LAM = 0.825739


def _picked(fwhm: np.ndarray) -> PeakList:
    """A list as a picker would hand it over: measured widths, source fitted."""
    tt = np.linspace(12.5, 58.0, len(fwhm))
    plain = PeakList.from_positions(tt, LAM, intensity=np.linspace(100, 10, len(tt)),
                                    two_theta_esd=0.001)
    peaks = [p.model_copy(update={"fwhm": float(w), "flags": []})
             for p, w in zip(plain.peaks, fwhm)]
    return plain.model_copy(update={"peaks": peaks, "source": "fitted"})


def test_a_high_resolution_list_sizes_its_own_window():
    rng = np.random.default_rng(3)
    fwhm = np.concatenate([np.full(15, 0.021) + rng.normal(0, 5e-4, 15),
                           np.full(5, 0.11)])      # the picker's broad junk
    peaks = _picked(fwhm)
    expected = float(np.quantile(fwhm, 0.25))
    assert width_allowance(peaks) == pytest.approx(expected)
    allowance, assumed = effective_shift_allowance(SearchSpec(), None, peaks)
    assert allowance == pytest.approx(expected) and assumed
    # the junk sets nothing: the window is the narrow lines', not the median's
    assert allowance < 0.025
    diag = shift_allowance_diagnostic(allowance)
    assert diag.code == "INDEX_SHIFT_ALLOWANCE"
    assert "widths" in diag.message
    # and the window the panel ranks in is the one the search matched in
    w = match_window(peaks, SearchSpec())
    from rietx.indexing.qspace import sigma_effective
    assert np.allclose(w, sigma_effective(peaks.q_esd(), peaks.two_theta(), LAM,
                                          expected))


def test_lists_without_measured_widths_or_with_lab_widths_keep_the_old_bound():
    plain = PeakList.from_positions(np.linspace(12.5, 58.0, 20), LAM)
    assert width_allowance(plain) is None
    assert effective_shift_allowance(SearchSpec(), None, plain) == (
        DEFAULT_UNKNOWN_SHIFT_DEG, True)
    lab = _picked(np.full(20, 0.2))
    assert effective_shift_allowance(SearchSpec(), None, lab) == (
        DEFAULT_UNKNOWN_SHIFT_DEG, True)
    assert "assumed bound" in shift_allowance_diagnostic(
        DEFAULT_UNKNOWN_SHIFT_DEG).message


def test_a_declared_or_measured_allowance_outranks_the_widths():
    peaks = _picked(np.full(20, 0.02))
    assert effective_shift_allowance(SearchSpec(shift_allowance_deg=0.04), None,
                                     peaks) == (0.04, False)

    class Quality:
        shift = ShiftScreen(n_lines=20, allowance_deg=0.031, source="measured")

    assert effective_shift_allowance(SearchSpec(), Quality(), peaks) == (0.031,
                                                                         False)


SI_CIF = ("data_Si\n_cell_length_a 5.4311\n_cell_length_b 5.4311\n"
          "_cell_length_c 5.4311\n_cell_angle_alpha 90\n_cell_angle_beta 90\n"
          "_cell_angle_gamma 90\n_space_group_IT_number 227\n"
          "_symmetry_space_group_name_H-M 'F d -3 m'\nloop_\n_atom_site_label\n"
          "_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n"
          "_atom_site_fract_z\n_atom_site_B_iso_or_equiv\nSi1 Si 0.125 0.125 0.125 0.5\n")


@pytest.mark.slow
@pytest.mark.parametrize("displacement_mm", [0.0, 0.1])
def test_a_synchrotron_twin_is_indexed_in_its_own_window(tmp_path,
                                                         displacement_mm):
    """F2's T5 arms on a synthetic Si twin (λ 0.8257 Å, FWHM ≈ 0.021°): the pair
    screen cannot name a shift on its 11 lines, so the window is the widths'
    (~0.02°, against 0.05°), and the truth is still rank 1 — with no shift, and
    with a 100 µm displacement (−0.052° at low angle) the window must span."""
    import rietx as rx
    from rietx.indexing import index_pattern

    cif = tmp_path / "si.cif"
    cif.write_text(SI_CIF, encoding="utf-8")
    structure = rx.Structure.from_cif(str(cif))
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    tt = np.round(np.arange(12.088, 62.0, 0.004), 3)
    shift = -np.degrees(2.0 * displacement_mm * np.cos(np.radians(tt / 2)) / 217.5)
    y = rx.Refinement(structure, ins, history=False).predict(two_theta=tt - shift)
    obs = np.random.default_rng(1).poisson(y / y.max() * 1.3e6 + 7700.0)
    data = rx.PatternData(two_theta=list(tt), intensity=list(obs.astype(float)),
                          sigma=list(np.sqrt(np.maximum(obs, 1.0))))
    limits = (12.1, 60.0)
    peaks = rx.pick_peaks(data, ins, two_theta_range=limits)

    allowance, assumed = effective_shift_allowance(SearchSpec(), None, peaks)
    assert assumed and 0.015 < allowance < 0.03, allowance
    res = index_pattern(peaks, data=data, instrument=ins, two_theta_limits=limits,
                        spec=SearchSpec(systems=("cubic",), budget_seconds=60.0),
                        preset="full")
    assert res.engine_stats["dichotomy.shift_allowance_deg"] == pytest.approx(
        allowance, abs=1e-5)
    best = res.candidates[0]
    assert best.centring == "F" and abs(best.cell[0] - 5.4311) < 0.01, (
        [(c.centring, c.cell[0]) for c in res.candidates[:3]])


def test_a_narrow_window_does_not_refute_a_superstructure_the_list_cannot_see():
    """The supercell check's power reads the search's assumed bound, never the
    widths' window (#951's baseline; its null reads the seen test's own windows
    since #1263).  An F-centred cubic list a superstructure leaves after a
    weak-line filter: six all-even lines and one all-odd (331), FWHM 0.010°.  Its a/2 P cell indexes six of seven; the true
    a cell's two uncancellable extras over it, (531) and (731), are below the
    filter.  At the widths' window p₀ ≈ 0.03 and "0 of 2 seen" read *refuted*,
    which sank the true cell under its subcell; at the assumed 0.05° the test
    has no power (p₀² ≥ α) and the pair stays *undecided*, as on main."""
    from rietx.indexing import index_pattern

    lam, a = 0.40, 10.0
    hkl = [(2, 2, 2), (4, 0, 0), (3, 3, 1), (4, 4, 0), (6, 2, 2), (4, 4, 4),
           (8, 0, 0)]
    tt = [float(np.degrees(2 * np.arcsin(lam * np.sqrt(sum(h * h for h in x))
                                         / (2 * a)))) for x in hkl]
    inten = [100.0, 32.0, 4.5, 54.0, 51.0, 13.0, 9.0]
    plain = PeakList.from_positions(tt, lam, intensity=inten,
                                    two_theta_esd=0.0005)
    peaks = plain.model_copy(update={
        "peaks": [p.model_copy(update={"fwhm": 0.010, "flags": []})
                  for p in plain.peaks], "source": "fitted"})
    assert effective_shift_allowance(SearchSpec(), None, peaks)[0] < 0.011

    res = index_pattern(peaks, spec=SearchSpec(systems=("cubic",)),
                        preset="quick")
    rank = {(c.centring, round(c.cell[0], 1)): i
            for i, c in enumerate(res.candidates)}
    assert ("F", 10.0) in rank and ("P", 5.0) in rank, sorted(rank)
    truth = res.candidates[rank[("F", 10.0)]]
    verdicts = {(k.parent_centring, round(k.parent_cell[0], 1)): k.verdict
                for k in truth.supercell_checks or []}
    assert verdicts.get(("P", 5.0)) == "undecided", verdicts
    assert rank[("F", 10.0)] < rank[("P", 5.0)], sorted(rank, key=rank.get)
