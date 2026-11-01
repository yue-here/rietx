"""Does the data support it: the observation count and the parameter split.

McCusker, Von Dreele, Cox, Louër & Scardi (1999) §9 says the Rietveld
algorithm's N — the number of profile steps — is not the number of
observations, and that only the integrated intensities of individual
reflections are.  Everything here pins that count against something the test
can state independently of the implementation:

* the count is the reflection list **minus what the grid did not measure**, so
  a range end that walks past a reflection steps it down by exactly the number
  of reflections it passed, and an excluded region punched over a peak removes
  that peak whether or not it sits between ``tt_min`` and ``tt_max``;
* a **Kα doublet does not double it** — the ``RefinementResult.ticks`` lesson
  the other way up.  Ticks carry every emission line, and a census that
  counted them would report twice the observations a doublet pattern holds;
* the ratio is against **structural** free parameters, so a plan that refines
  only the profile and the background leaves it undefined rather than
  flattering.

The exact-arithmetic anchor is a **cubic** cell, where (300)/(221) and
(411)/(330) are distinct reflections at identical 2θ.  §9 calls that pair one
observation and the raw count calls it two: the gap this file measures is the
one the effective count exists to close.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.background.diagnostics import sampling_steps_per_fwhm
from rietx.model.forward import compile_model
from rietx.optimize.statistics import (
    STRUCTURAL_PARAMETER_GLOB,
    count_unique_reflections,
    data_support,
    effective_observations,
    measured_mask,
    structural_free_paths,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_BKG,
    TRUE_SCALE,
    TRUE_W,
    TRUE_ZERO,
    WAVELENGTH,
    synthesize,
)
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"


def _save(result, name: str) -> None:
    """Write an obs/calc/diff PNG (skipped if matplotlib is unavailable)."""
    pytest.importorskip("matplotlib")
    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

    plot_result(result, path=str(OUT / name))


def _lab6(*, radiation: str | None = None):
    """LaB6 at the synthetic truth.

    ``radiation=None`` is the single-line synchrotron instrument the synthetic
    pattern was generated with; a name selects the lab preset, so ``"CuKa"``
    and ``"CuKa1"`` differ in **nothing but the second emission line** — the
    only difference the doublet test is allowed to have.
    """
    s = make_lab6()
    for c in ("a", "b", "c"):
        getattr(s.phases[0].cell, c).value = TRUE_A
    s.phases[0].scale.value = TRUE_SCALE
    if radiation is None:
        ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
        ins.profile.w.value = TRUE_W
    else:
        ins = Instrument.bragg_brentano(radiation=radiation)
        ins.profile.w.value = 0.005
    ins.zero_shift.value = TRUE_ZERO
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in TRUE_BKG])
    return s, ins


def _compiled(structure, instrument, tt: np.ndarray, *,
              excluded: list[tuple[float, float]] | None = None):
    """A model compiled on a bare grid, plus the decoded values at rest."""
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.ones_like(tt).tolist(),
                        excluded_regions=excluded or [])
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    return model, table.decode(table.x0())


def _arrays(pattern: PatternData):
    """``(2θ, y, σ)`` — what :func:`sampling_steps_per_fwhm` takes."""
    return pattern.tt(), pattern.y(), pattern.sig()


def _tick_positions(model, values, ip: int = 0) -> np.ndarray:
    """Every emission line's peak position for phase ``ip`` — what ``ticks``
    carries, and the number the census must *not* reproduce on a doublet."""
    rows = [np.asarray(pos, dtype=np.float64)
            for pos, _w1, _w2, _i in model.phase_peaks(ip, values)]
    return np.concatenate(rows)


# --------------------------------------------------------------------------
# measured_mask — the criterion, on its own
# --------------------------------------------------------------------------

def test_measured_mask_reads_half_a_fwhm_either_side():
    """Half the peak's own FWHM, at both edges, on a uniform grid."""
    tt = np.arange(10.0, 20.0, 0.01)      # last channel 19.99
    fwhm = np.full(6, 0.20)                # half-width criterion: 0.10°
    pos = np.array([15.0,          # dead centre
                    10.0, 9.92,    # at the low edge, and 0.08° = 0.4·FWHM out
                    19.99, 20.07,  # the same either side
                    9.80])         # 1.0·FWHM out — the top is off the grid
    got = measured_mask(tt, pos, fwhm)
    assert got.tolist() == [True, True, True, True, True, False]


def test_measured_mask_is_false_off_the_ewald_sphere():
    """A non-finite position is not measured, and is not an error either."""
    tt = np.arange(10.0, 20.0, 0.01)
    got = measured_mask(tt, np.array([np.nan, np.inf, 15.0]), np.full(3, 0.2))
    assert got.tolist() == [False, False, True]


# --------------------------------------------------------------------------
# the count
# --------------------------------------------------------------------------

def test_count_steps_down_as_the_range_end_passes_reflections():
    """The count is the reflection list minus what the grid did not measure.

    Walking the upper limit down past each reflection must drop the count by
    exactly the number of reflections passed — including the *pair* at one 2θ,
    which leaves together and takes two observations with it.
    """
    structure, instrument = _lab6()
    full = np.arange(3.0, 26.0, 0.005)
    model, values = _compiled(structure, instrument, full)
    ticks = np.sort(_tick_positions(model, values))
    inside = ticks <= full[-1]
    assert count_unique_reflections(model, values) == int(inside.sum())
    # the reflection left out sits well past the last channel, so this pins the
    # count rather than the knife edge of the half-FWHM allowance
    assert ticks[~inside].min() - full[-1] > 0.1

    # cut only where a gap of >0.1° opens, so half a FWHM (widths here are
    # ≪0.05°) cannot reach back over the limit and no coincident pair is split
    cuts = [k for k in range(2, len(ticks))
            if ticks[k] - ticks[k - 1] > 0.10]
    assert len(cuts) >= 4
    for cut_after in cuts[::max(len(cuts) // 4, 1)]:
        hi = float(ticks[cut_after - 1] + 0.05)
        m, v = _compiled(structure, instrument, np.arange(3.0, hi, 0.005))
        assert count_unique_reflections(m, v) == cut_after


def test_a_kalpha_doublet_does_not_double_the_count():
    """Ticks carry every emission line; observations do not (WP-1071).

    The Kα2 companion is the same reflection measured a second time.  A census
    reading ``ticks`` would report 2× here — which is the bug this asserts is
    absent, in the same shape as the Layer-0 impurity bug that made ``ticks``
    carry both lines in the first place.
    """
    single_s, single_i = _lab6(radiation="CuKa1")
    double_s, double_i = _lab6(radiation="CuKa")
    # the same lab instrument either way, so the only difference is the Kα2
    # line; the range starts below the first reflection and ends in open
    # pattern, so no reflection is half-in at an edge on either line set
    tt = np.arange(15.0, 90.0, 0.01)

    m1, v1 = _compiled(single_s, single_i, tt)
    m2, v2 = _compiled(double_s, double_i, tt)
    n1 = count_unique_reflections(m1, v1)
    n2 = count_unique_reflections(m2, v2)

    assert len(_tick_positions(m2, v2)) == 2 * len(_tick_positions(m1, v1))
    assert n2 == n1 > 0


def test_an_excluded_region_removes_the_reflections_under_it():
    """WP-1033's fitted-mask rule: an excluded peak was not observed.

    ``tt_min``/``tt_max`` cannot answer this — the removed reflections sit in
    the middle of the range — so a census reading the ends would count them.
    """
    structure, instrument = _lab6()
    tt = np.arange(3.0, 26.0, 0.005)
    model, values = _compiled(structure, instrument, tt)
    ticks = np.sort(_tick_positions(model, values))
    base = count_unique_reflections(model, values)

    lo, hi = ticks[3] - 0.1, ticks[5] + 0.1      # three reflections inside
    n_inside = int(((ticks >= lo) & (ticks <= hi)).sum())
    assert n_inside == 3

    cut, cut_values = _compiled(structure, instrument, tt,
                                excluded=[(float(lo), float(hi))])
    assert count_unique_reflections(cut, cut_values) == base - 3


def test_the_raw_count_over_counts_a_coincident_pair():
    """Two reflections at one 2θ are one observation and are counted as two.

    §9's own example, and the reason the effective count exists.  Stated as a
    test so the raw number is never mistaken for the paper's observation count.
    """
    structure, instrument = _lab6()
    model, values = _compiled(structure, instrument, np.arange(3.0, 26.0, 0.005))
    pos = np.sort(_tick_positions(model, values))
    coincident = int(np.count_nonzero(np.diff(pos) < 1e-9))
    assert coincident > 0
    assert count_unique_reflections(model, values) > len(pos) - coincident


# --------------------------------------------------------------------------
# the effective count — Altomare et al. (1995)
# --------------------------------------------------------------------------

def test_a_coincident_pair_is_one_effective_observation():
    """Altomare's Fig. 1, on a cubic cell that has the pair for real.

    Every LaB6 reflection here is isolated except the exact coincidences, so
    M_ind must come out at the raw count minus one per coincident pair — an
    integer, and the arithmetic anchor for everything below.
    """
    structure, instrument = _lab6()
    model, values = _compiled(structure, instrument, np.arange(3.0, 26.0, 0.005))
    pos = np.sort(_tick_positions(model, values))
    pos = pos[pos <= model.tt[-1]]
    n_extra = int(np.count_nonzero(np.diff(pos) < 1e-9))
    assert n_extra >= 2                       # (300)/(221), (411)/(330), …

    raw = count_unique_reflections(model, values)
    assert effective_observations(model, values) == pytest.approx(
        raw - n_extra, abs=1e-9)


def test_overlap_drives_the_effective_count_down_monotonically():
    """A severely overlapped pattern's effective count sits well below its raw
    one, and nothing else moved: same cell, same range, same reflections.

    Lorentzian size broadening is the lever because it widens the peaks without
    touching their positions or the reflection list, so M_ind is the only thing
    in the table that can move.
    """
    structure, instrument = _lab6(radiation="CuKa")
    tt = np.arange(15.0, 140.0, 0.01)
    got = []
    for lor_size in (0.0, 2.0, 5.0, 15.0):
        s, ins = _lab6(radiation="CuKa")
        s.phases[0].lor_size.value = lor_size
        model, values = _compiled(s, ins, tt)
        raw = count_unique_reflections(model, values)
        got.append((raw, effective_observations(model, values)))

    raws = {r for r, _ in got}
    assert len(raws) == 1                     # the raw count cannot see overlap
    eff = [e for _, e in got]
    assert eff == sorted(eff, reverse=True)   # monotone in the broadening
    assert eff[0] / raws.pop() > 0.8          # sharp: nearly every line counts
    assert eff[-1] < 0.2 * eff[0]             # merged: the pattern is one hump
    assert structure is not None


def test_the_effective_count_never_exceeds_the_raw_one():
    """M_ind ≤ M by construction — every contribution is a fraction of 1."""
    for lor_size in (0.0, 1.0, 6.0):
        structure, instrument = _lab6(radiation="CuKa")
        structure.phases[0].lor_size.value = lor_size
        model, values = _compiled(structure, instrument,
                                  np.arange(15.0, 140.0, 0.01))
        raw = count_unique_reflections(model, values)
        eff = effective_observations(model, values)
        assert 0.0 < eff <= raw + 1e-9


def test_an_excluded_region_removes_effective_observations_too():
    """The integral runs over fitted channels, so an exclusion costs both
    counts — and the effective one cannot fall by more than the raw one."""
    structure, instrument = _lab6()
    tt = np.arange(3.0, 26.0, 0.005)
    model, values = _compiled(structure, instrument, tt)
    ticks = np.sort(_tick_positions(model, values))
    lo, hi = float(ticks[3] - 0.1), float(ticks[5] + 0.1)

    cut, cut_values = _compiled(structure, instrument, tt, excluded=[(lo, hi)])
    assert (count_unique_reflections(cut, cut_values)
            == count_unique_reflections(model, values) - 3)
    assert (effective_observations(cut, cut_values)
            == pytest.approx(effective_observations(model, values) - 3, abs=1e-9))


def test_no_reflection_measured_gives_none_not_zero():
    """Nothing to estimate says ``None``, never 0.0.

    Zero effective observations is a claim about a pattern; no measured
    reflection is the absence of one, and the two must not arrive as the same
    number.  Driven through the census directly because a fit range holding no
    reflection at all does not reach here — ``compile_model`` raises on the
    empty reflection list first, one rank up and outside this WP.
    """
    from rietx.optimize.statistics import _effective_from_census

    structure, instrument = _lab6()
    model, _values = _compiled(structure, instrument,
                               np.arange(3.0, 26.0, 0.005))
    assert _effective_from_census(model, []) is None


# --------------------------------------------------------------------------
# steps per FWHM — McCusker §2
# --------------------------------------------------------------------------

def _sampled(step: float, w: float, *, seed: int = 7) -> PatternData:
    """A noisy LaB6 pattern at a chosen step size and Gaussian width, so the
    steps-per-FWHM answer is known before it is measured."""
    structure, instrument = _lab6()
    instrument.profile.w.value = w
    tt = np.arange(3.0, 24.0, step)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0))
                       .astype(float).tolist())


@pytest.mark.parametrize(("step", "w"), [
    (0.005, 2.5e-4),    # 3.2 nominal steps per FWHM — undersampled
    (0.002, 2.5e-4),    # 7.9 — inside the band
    (0.005, 4.0e-3),    # 12.6 — oversampled
    (0.002, 4.0e-3),    # 31.6 — heavily oversampled
])
def test_steps_per_fwhm_tracks_the_step_size_it_was_collected_at(step, w):
    """The measurement is checked against a width that was *set*, not fitted.

    √W is the Gaussian FWHM the pattern was generated with, so √W/step is the
    nominal answer; the measured one runs a few per cent high because the
    instrument's Lorentzian X and Y broaden the peak beyond the Gaussian part.
    """
    got, n = sampling_steps_per_fwhm(*_arrays(_sampled(step, w)))
    nominal = np.sqrt(w) / step
    assert n >= 10
    assert nominal <= got <= 1.1 * nominal


def test_the_prominence_floor_is_a_floor_and_not_a_tuning():
    """5σ and 20σ must give the same answer, or the number is fitted to its
    own threshold rather than measured (the guard on the guard)."""
    from rietx.background import diagnostics as diag

    pattern = _sampled(0.005, 2.5e-4)
    at5, n5 = sampling_steps_per_fwhm(*_arrays(pattern))
    old = diag.SAMPLING_PROMINENCE_SIGMA
    try:
        diag.SAMPLING_PROMINENCE_SIGMA = 20.0
        at20, n20 = sampling_steps_per_fwhm(*_arrays(pattern))
    finally:
        diag.SAMPLING_PROMINENCE_SIGMA = old
    assert (at20, n20) == (at5, n5)


def test_without_the_prominence_floor_a_strong_peak_reads_as_undersampled():
    """The measured failure the floor exists for: noise on a 10⁵-count peak's
    own top puts several 5σ maxima across it, and the median width collapses
    below one step — the *opposite* answer on a pattern that is merely noisy."""
    from scipy.signal import find_peaks, peak_widths

    from rietx.background.diagnostics import background_envelope

    pattern = _sampled(0.005, 4.0e-3)     # 12.6 nominal: comfortably sampled
    tt, y, sigma = _arrays(pattern)
    net = y - background_envelope(tt, y)
    z = np.where(net > 0, net, 0.0) / sigma
    bare, _ = find_peaks(z, height=5.0, distance=3)
    kept, _ = find_peaks(z, height=5.0, distance=3, prominence=5.0)
    assert len(bare) > len(kept)

    measured, _ = sampling_steps_per_fwhm(tt, y, sigma)
    unfiltered = float(np.median(
        peak_widths(np.maximum(net, 0.0), bare, rel_height=0.5)[0]))
    assert unfiltered < measured
    assert measured > 10.0


def test_diagnose_reports_the_same_number_as_the_function():
    """One authority: ``PatternDiagnostics.steps_per_fwhm`` is the shared
    measurement, not a second one taken on the same pattern."""
    from rietx.background.diagnostics import diagnose

    pattern = _sampled(0.002, 2.5e-4)
    got = diagnose(pattern)
    expected, n = sampling_steps_per_fwhm(*_arrays(pattern))
    assert got.steps_per_fwhm == expected
    assert got.n_peaks_measured == n


def test_a_featureless_pattern_measures_nothing_and_says_so():
    """No resolved peak means no answer, reported as ``None`` rather than as a
    zero that would read as catastrophic undersampling."""
    tt = np.arange(5.0, 60.0, 0.02)
    rng = np.random.default_rng(3)
    flat = PatternData(two_theta=tt.tolist(),
                       intensity=rng.poisson(np.full(tt.shape, 200.0))
                       .astype(float).tolist())
    got, n = sampling_steps_per_fwhm(*_arrays(flat))
    assert got is None and n == 0


# --------------------------------------------------------------------------
# the two diagnostic codes
# --------------------------------------------------------------------------

def test_undersampling_is_flagged_and_good_sampling_is_not():
    """``PATTERN_UNDERSAMPLED`` fires below five steps and stays silent above
    it, including well above ten — the band's upper end costs beam time, not
    validity, so it is reported and never flagged."""
    structure, instrument = _lab6()
    ref = Refinement(structure, instrument, history=False)
    coarse = ref.fit(_sampled(0.005, 2.5e-4), plan="mccusker_default")
    _save(coarse, "data_support_undersampled.png")

    structure, instrument = _lab6()
    fine = Refinement(structure, instrument, history=False).fit(
        _sampled(0.002, 4.0e-3), plan="mccusker_default")
    _save(fine, "data_support_oversampled.png")

    assert "PATTERN_UNDERSAMPLED" in {d.code for d in coarse.diagnostics}
    assert "PATTERN_UNDERSAMPLED" not in {d.code for d in fine.diagnostics}


def test_the_ratio_diagnostic_grades_against_the_papers_two_part_band():
    """``DATA_SUPPORT_LOW`` is a warning below three, information between
    three and five, and absent above — "at least three and preferably five",
    read off the *effective* ratio because that is the one the band is about.
    """
    from rietx.optimize.statistics import OBS_PER_PARAMETER_MIN, OBS_PER_PARAMETER_PREFERRED
    from rietx.refine import _data_support_diagnostics
    from rietx.schemas.results import DataSupport

    structure, instrument = _lab6()
    model, _values = _compiled(structure, instrument,
                               np.arange(3.0, 26.0, 0.005))
    seen = {}
    for ratio in (1.5, 4.0, 8.0):
        support = DataSupport(
            n_unique_reflections=20, n_effective_observations=ratio * 4,
            n_structural_parameters=4, observations_per_parameter=5.0,
            effective_observations_per_parameter=ratio)
        found = [d for d in _data_support_diagnostics(support, model)
                 if d.code == "DATA_SUPPORT_LOW"]
        seen[ratio] = found[0].level if found else None
    assert seen == {1.5: "warning", 4.0: "info", 8.0: None}
    assert OBS_PER_PARAMETER_MIN == 3.0
    assert OBS_PER_PARAMETER_PREFERRED == 5.0


def test_neither_code_gates_anything():
    """Both are evidence: the fit that raised them converged, kept its
    parameters, and carries the numbers on the result either way."""
    structure, instrument = _lab6()
    result = Refinement(structure, instrument, history=False).fit(
        _sampled(0.005, 2.5e-4), plan="mccusker_structural")

    assert result.status == "converged"
    assert "PATTERN_UNDERSAMPLED" in {d.code for d in result.diagnostics}
    assert result.data_support is not None
    assert result.data_support.n_effective_observations > 0
    assert result.statistics.rwp < 0.5


# --------------------------------------------------------------------------
# the parameter split and the ratio, on a real fit
# --------------------------------------------------------------------------

def test_a_profile_plan_frees_no_structural_parameter():
    """The ratio is about structural parameters, so a profile/background plan
    leaves it ``None`` rather than reporting a flattering number against the
    eleven free parameters it did refine."""
    pattern = synthesize()
    structure, instrument = _lab6()
    result = Refinement(structure, instrument, history=False).fit(
        pattern, plan="mccusker_default")
    _save(result, "data_support_profile_plan.png")

    ds = result.data_support
    assert ds is not None
    assert ds.n_structural_parameters == 0
    assert ds.observations_per_parameter is None
    assert result.statistics.n_free_parameters > 0
    assert ds.n_unique_reflections < result.statistics.n_points


def test_the_ratio_counts_only_the_atom_paths():
    """Structural = ``phases.*.atoms.*``: coordinate DOFs, occupancies, Biso
    and ADP DOFs, and nothing the peak *positions* determine."""
    pattern = synthesize()
    structure, instrument = _lab6()
    ref = Refinement(structure, instrument, history=False)
    result = ref.fit(pattern, plan="mccusker_structural")
    _save(result, "data_support_structural_plan.png")

    ds = result.data_support
    assert ds is not None
    varied = [p.path for p in result.parameters if p.vary]
    atom_paths = [p for p in varied if ".atoms." in p]
    assert ds.n_structural_parameters == len(atom_paths) > 0
    assert ds.n_structural_parameters < result.statistics.n_free_parameters
    assert ds.observations_per_parameter == pytest.approx(
        ds.n_unique_reflections / ds.n_structural_parameters)

    import fnmatch
    assert all(fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB) for p in atom_paths)
    assert not any(fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB)
                   for p in varied if ".atoms." not in p)


def test_the_glob_reaches_every_kind_of_atom_parameter():
    """Coordinate DOF, occupancy, Biso and ADP DOF all match, and the cell,
    profile, background and scale do not — the split the docstring claims."""
    import fnmatch

    inside = ["phases.0.atoms.1.dof.0", "phases.0.atoms.1.occ",
              "phases.2.atoms.11.biso", "phases.0.atoms.0.adp.3"]
    outside = ["phases.0.cell.a", "phases.0.scale", "phases.0.extinction",
               "phases.0.preferred_orientation.r", "phases.0.lor_size",
               "phases.0.microstrain.dof.0", "instrument.profile.w",
               "instrument.background.c2", "instrument.zero_shift"]
    assert all(fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB) for p in inside)
    assert not any(fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB) for p in outside)


# --------------------------------------------------------------------------
# a sigma column smaller than root-y (WP-1415, issues #274 and #275)
# --------------------------------------------------------------------------

#: Monitor factor m of the synthetic below.  The declared intensity is m×raw
#: and the declared σ is m×√raw, so σ/√y = √m — 0.289 at this value, which is
#: the median the ILL D1B file of both issues carries.  The noise is drawn
#: from the raw counts, so **σ is correct**; that is the whole point, and it
#: is why neither issue asks for the σ column to be replaced.
D1B_MONITOR = 0.0835


def _monitor_normalised(monitor: float = D1B_MONITOR, *, seed: int = 0,
                        dead: tuple[int, ...] = ()) -> PatternData:
    """A CW-neutron-shaped pattern whose σ is right and smaller than √y.

    A big flat incoherent background, as constant-wavelength neutron data has,
    at the level issue #274's own table implies: the refinement with the dead
    channels excluded puts the background near 35 000 at 128.6°, and the live
    channel there reads σ = 55.145, with 0.289·√35158 = 54.2.

    ``dead`` plants issue #274's own pair at those indices — y = 3 and 5 with
    σ = 1.000 and 1.414, Poisson of nothing beside a background three decades
    above.
    """
    tt = np.arange(5.0, 128.85, 0.1)
    rng = np.random.default_rng(seed)
    base = 35000.0 / monitor
    raw = base * (1.0 + 0.25 * 60.0 / np.maximum(tt, 2.0)
                  + 0.08 * np.exp(-0.5 * ((tt - 35.0) / 22.0) ** 2))
    pos = np.linspace(13.0, 122.8, 13) + 1.6 * np.sin(np.arange(13) * 2.3)
    amp = (1.2 * base) * np.array(
        [1.0, .55, .30, .80, .18, .42, .09, .25, .13, .34, .07, .16, .05])
    for p, a in zip(pos, amp):
        raw = raw + a * np.exp(-0.5 * ((tt - p) / (1.1 / 2.3548)) ** 2)

    counts = rng.poisson(np.maximum(raw, 1.0)).astype(float)
    y = monitor * counts
    sigma = monitor * np.sqrt(np.maximum(counts, 1.0))
    for k, i in enumerate(dead):
        y[i], sigma[i] = ((3.0, 1.0), (5.0, 1.414))[k % 2]
    return PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                       sigma=sigma.tolist())


def test_the_sampling_answer_does_not_move_when_only_the_declared_sigma_does():
    """The invariant the second floor buys, and the defect it closes.

    Scaling σ alone leaves the pattern untouched, so any change in the answer
    is the measurement reading the declared precision rather than the
    experiment.  What the peak finder thresholds in the background is the
    envelope's own tracking error, which is a fraction of the intensity and
    does not shrink when the counting improves.
    """
    tt, y, sig = _arrays(_monitor_normalised())
    answers = [sampling_steps_per_fwhm(tt, y, sig * s)
               for s in (1.0, 0.5, 0.289, 0.15, 0.05)]
    steps = [a[0] for a in answers]
    assert all(s is not None for s in steps)
    assert max(steps) / min(steps) == pytest.approx(1.0, abs=1e-9)
    # and it is the right answer: 1.1° FWHM at 0.1° steps, by construction
    assert steps[0] == pytest.approx(11.0, rel=0.05)
    assert all(a[1] == 13 for a in answers)       # the 13 lines, at every scale


def test_the_census_counts_the_same_lines_whatever_sigma_is_declared():
    """``n_peaks`` is the count ``_contamination_flags`` searches for ghosts
    among, so a census that counted noise made that search a lottery.

    The bar under test is the scale dependence, not the over-count: this
    census keeps no prominence bar, so a strong peak's own noisy top still
    carries more than one maximum and 13 lines come back as 27.  That is what
    a *count* is for, and what ``_median_steps_per_fwhm`` uses
    ``SAMPLING_PROMINENCE_SIGMA`` to avoid.  What must not happen is the count
    moving because the file declared a different σ.
    """
    from rietx.background.diagnostics import background_envelope, diagnose

    data = _monitor_normalised()
    tt, y, sig = _arrays(data)
    net = np.where((y - background_envelope(tt, y)) > 0,
                   y - background_envelope(tt, y), 0.0)
    counts = []
    for scale in (1.0, 0.5, 0.289, 0.15, 0.05):
        from scipy.signal import find_peaks

        from rietx.background.diagnostics import SAMPLING_HEIGHT_FRACTION
        floor = SAMPLING_HEIGHT_FRACTION * float(np.percentile(net, 99.9))
        idx, _ = find_peaks(net, distance=3,
                            height=np.maximum(5.0 * sig * scale, floor))
        counts.append(len(idx))
    assert len(set(counts)) == 1
    assert counts[0] < 3 * 13            # 27, against 79-201 before the floor

    got = diagnose(data)
    assert got.n_peaks == counts[0]
    assert got.steps_per_fwhm == pytest.approx(11.0, rel=0.05)


def test_a_dead_cell_is_named_with_its_interval_and_what_it_outvotes():
    """Issue #274's pair, planted at its own numbers four channels from the
    top of the range — the position that matters, because the envelope
    extrapolates to the data edge and a dropout there drags it negative."""
    from rietx.background.diagnostics import dead_channels

    data = _monitor_normalised(dead=(1235, 1236))
    tt, y, sig = _arrays(data)
    runs = dead_channels(tt, y, sig)
    assert len(runs) == 1
    run = runs[0]
    assert run.n_channels == 2
    assert (run.two_theta_min, run.two_theta_max) == pytest.approx((128.5, 128.6))
    assert run.level_fraction < 0.01
    assert run.weight_ratio > 1000.0


@pytest.mark.parametrize("at", [60, 600, 1235])
def test_a_dead_cell_is_found_anywhere_in_the_range(at):
    """Near either end and in the middle: the level a run is judged against
    must not be one the run itself pulled down."""
    from rietx.background.diagnostics import dead_channels

    tt, y, sig = _arrays(_monitor_normalised(dead=(at, at + 1)))
    runs = dead_channels(tt, y, sig)
    assert len(runs) == 1 and runs[0].n_channels == 2


def test_a_channel_that_honestly_counted_zero_is_not_a_dead_cell():
    """The distinction the σ column makes, and the reason this measure
    declines without one: a channel that counted nothing carries *less* weight
    than a live one, while a dead cell's esd fell with its intensity."""
    from rietx.background.diagnostics import dead_channels

    tt = np.arange(5.0, 60.0, 0.02)
    rng = np.random.default_rng(5)
    counts = rng.poisson(np.full(tt.shape, 4.0)).astype(float)
    sigma = np.sqrt(np.maximum(counts, 1.0))
    assert (counts == 0).any()                      # the case under test
    assert dead_channels(tt, counts, sigma) == []


def test_without_a_measured_sigma_the_census_declines_rather_than_guesses():
    """Under the Poisson fallback a dead cell and a zero count are the same
    two numbers, so answering at all would be reporting the fallback."""
    from rietx.background.diagnostics import dead_channels

    tt, y, _ = _arrays(_monitor_normalised(dead=(600, 601)))
    assert dead_channels(tt, y, None) == []


@pytest.mark.parametrize(("n", "found"), [(2, 1), (10, 1), (11, 0), (20, 0)])
def test_a_run_too_long_to_judge_is_declined_rather_than_fragmented(n, found):
    """Past ``CUTOFF_MIN_DEG`` the level estimate cannot survive the run, and
    the honest failure is silence.  The length test alone was not enough: it
    left a 1.9° dropout reported as a spurious *one-channel* run, because the
    collapsed level stopped the rest of it being flagged at all."""
    from rietx.background.diagnostics import dead_channels

    tt, y, sig = _arrays(_monitor_normalised(dead=tuple(range(600, 600 + n))))
    assert len(dead_channels(tt, y, sig)) == found


def test_a_dead_pair_at_the_literal_last_channel_is_found():
    """WP-1415, issue #274's second ask, measured on the real D1B file rather
    than the synthetic above: `300q-300K.dat` has nothing recorded past
    128.69°, so its trailing dead pair touches the *literal* end of the
    array, with no live channel beyond it to be "bounded" by.  Declining
    every edge-touching run, as this measure did before WP-1415, missed
    exactly the case issue #274 reported and quoted a stale ×14 `BOUND_HIT`
    count as the symptom instead.

    The criterion is unchanged — the same weight-ratio test the interior case
    uses — and the real files sit well clear of it on both sides: D1B's two
    edge pairs read a weight ratio of 1520-2286, 15-23× **above**
    ``DEAD_WEIGHT_RATIO_MIN``, while a private Mythen operando set's cliff
    edges, none of them a dead cell, read of order unity or below, nearly two
    orders of magnitude **below** it (private neutron PSD holds agree in
    direction; neither private set's figures are quoted).  This fixture plants the same pair at the synthetic's own last
    two channels."""
    from rietx.background.diagnostics import dead_channels

    n = len(np.arange(5.0, 128.85, 0.1))
    data = _monitor_normalised(dead=(n - 2, n - 1))
    tt, y, sig = _arrays(data)
    runs = dead_channels(tt, y, sig)
    assert len(runs) == 1
    run = runs[0]
    assert run.n_channels == 2
    assert run.two_theta_max == pytest.approx(float(tt[-1]))
    assert run.weight_ratio > 1000.0


def test_a_dead_pair_at_the_literal_first_channel_is_found():
    """The low-edge twin of the test above: a run touching index 0 has no
    live channel *before* it, only after, and is judged against that one
    side."""
    from rietx.background.diagnostics import dead_channels

    data = _monitor_normalised(dead=(0, 1))
    tt, y, sig = _arrays(data)
    runs = dead_channels(tt, y, sig)
    assert len(runs) == 1
    run = runs[0]
    assert run.n_channels == 2
    assert run.two_theta_min == pytest.approx(float(tt[0]))
    assert run.weight_ratio > 1000.0


def test_an_honestly_low_edge_is_not_a_dead_cell():
    """The negative control: a coverage cliff at an edge, whose neighbours
    fall *with* it, must not become a false positive once edge-touching runs
    are admitted.

    What separates the two is not the edge pair itself but its window.  The
    weight ratio is (median live σ within :data:`DEAD_LEVEL_WINDOW_DEG`)² over
    the run's σ², so with σ ∝ √y a pair at 1/k of its neighbours' level reads
    ≈ k whenever those neighbours are the interior — a two-channel *step*
    reads 50.09 at k = 50 and is reported from k = 100 on (the next test pins
    that).  A real cliff is a ramp: the channels before the pair are falling
    too, so the live σ it is weighed against is itself low.  This plants that
    shape: the last 60 channels fall geometrically to 1/10 of the interior,
    the last two a further factor 10 (1/100 overall, the same depth as the
    reported step), σ ∝ √y throughout.  The pair is still found low, so the
    weight-ratio test is what declines it — measured at 18.7, 5× under
    ``DEAD_WEIGHT_RATIO_MIN``.  With σ ∝ √y the floor is 1/``DEAD_LEVEL_FRACTION``
    (a channel is low only under a tenth of its level), so no √y synthetic
    reaches the real data's: a private Mythen operando set's cliff edges read
    of order unity or below, nearly two orders of magnitude under the
    threshold, against D1B's dead pairs 15-23× above it (private neutron PSD
    holds agree in direction; neither private set's figures are quoted)."""
    from rietx.background.diagnostics import (
        DEAD_WEIGHT_RATIO_MIN,
        dead_channels,
    )

    tt, y, sig = _arrays(_monitor_normalised())
    fall = np.ones(len(tt))
    fall[-60:] = np.geomspace(1.0, 0.1, 60)
    fall[-2:] *= 0.1
    y, sig = y * fall, sig * np.sqrt(fall)
    seen = dead_channels(tt, y, sig, weight_ratio_min=0.0)
    assert len(seen) == 1 and seen[0].two_theta_max == pytest.approx(tt[-1])
    assert seen[0].weight_ratio < DEAD_WEIGHT_RATIO_MIN / 4
    assert dead_channels(tt, y, sig) == []


@pytest.mark.parametrize("k", [100, 200, 400])
def test_an_edge_step_a_hundredfold_down_is_reported(k):
    """The boundary the control above declares, pinned rather than left a
    surprise: a two-channel *step* at the literal edge to 1/k of the interior,
    σ scaled by 1/√k — honest counting statistics, not a collapsed detector —
    has only interior neighbours in its window, so its weight ratio is ≈ k
    and from k = ``DEAD_WEIGHT_RATIO_MIN`` on it **is** reported as dead.
    The measure cannot tell such a step from a dead pair and does not claim
    to; what it separates is a step from a ramp."""
    from rietx.background.diagnostics import (
        DEAD_WEIGHT_RATIO_MIN,
        dead_channels,
    )

    tt, y, sig = _arrays(_monitor_normalised())
    y, sig = y.copy(), sig.copy()
    y[-2:] /= k
    sig[-2:] /= np.sqrt(k)
    runs = dead_channels(tt, y, sig)
    assert len(runs) == 1 and runs[0].n_channels == 2
    assert runs[0].weight_ratio >= DEAD_WEIGHT_RATIO_MIN
    assert runs[0].weight_ratio == pytest.approx(k, rel=0.01)


#: The synthetic LaB6's background, raised to the regime issue #274 reports.
#: A dead cell's damage is (σ_local/σ_dead)², and σ_local goes as √background,
#: so the *same* dead channel that outvotes 3000 live ones on a CW-neutron
#: pattern at 35 000 counts outvotes 2.4 on this suite's default LaB6 at 40.
#: Measured both ways; the low-background case is correctly silent, because
#: there the channel is a mild pull rather than a catastrophe.
DEAD_CHANNEL_BACKGROUND = [35000.0, -6.0, 1.5]


def _lab6_monitor_normalised(*, dead: tuple[int, ...] = (), seed: int = 0):
    """The suite's own LaB6 at a monitor-normalised σ, so the *fit* is real.

    ``_monitor_normalised`` above is a D1B-shaped pattern with peaks at
    arbitrary positions, which is all the model-free measures need.  A fit
    needs a pattern its model can actually describe, or the dead channels are
    not what the residual is made of.
    """
    structure, instrument = _lab6()
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in DEAD_CHANNEL_BACKGROUND])
    tt = np.arange(5.0, 120.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    clean = model.evaluate(table.decode(table.x0()))

    rng = np.random.default_rng(seed)
    raw = rng.poisson(np.maximum(clean / D1B_MONITOR, 1.0)).astype(float)
    y = D1B_MONITOR * raw
    sigma = D1B_MONITOR * np.sqrt(np.maximum(raw, 1.0))
    for k, i in enumerate(dead):
        y[i], sigma[i] = ((3.0, 1.0), (5.0, 1.414))[k % 2]
    return (PatternData(two_theta=model.tt.tolist(), intensity=y.tolist(),
                        sigma=sigma.tolist()), structure, instrument)


def test_dead_channels_reach_the_reader_and_the_fit(tmp_path):
    """Both channels the finding travels on, and the reason for the first: a
    dead cell reaches the person as parameters at their bounds several minutes
    later, and none of those is the cause."""
    from rietx.io.readers import read_pattern
    from rietx.schemas.common import Diagnostic

    data, _, _ = _lab6_monitor_normalised(dead=(2000, 2001))
    path = tmp_path / "lab6_monitor.xye"
    path.write_text("\n".join(
        f"{a:.4f} {b:.4f} {c:.4f}" for a, b, c
        in zip(data.tt(), data.y(), data.sig())) + "\n", encoding="utf-8")

    found: list[Diagnostic] = []
    reread = read_pattern(str(path), diagnostics=found)
    assert "PATTERN_DEAD_CHANNELS" in [d.code for d in found]
    assert reread.sigma is not None               # nothing was repaired
    assert reread.y()[2000] == pytest.approx(3.0)

    _, structure, instrument = _lab6_monitor_normalised()
    spoilt = Refinement(structure.model_copy(deep=True),
                        instrument.model_copy(deep=True),
                        history=False).fit(data, plan="mccusker_default")
    _save(spoilt, "data_support_dead_channels.png")
    assert "PATTERN_DEAD_CHANNELS" in {d.code for d in spoilt.diagnostics}

    # the issue's own comparison: the same refinement with the two channels
    # outside the range, which is what the finding asks the caller to do
    clean_data = data.model_copy(update={"excluded_regions": [
        (float(data.tt()[1999]), float(data.tt()[2002]))]})
    clean = Refinement(structure.model_copy(deep=True),
                       instrument.model_copy(deep=True),
                       history=False).fit(clean_data, plan="mccusker_default")
    _save(clean, "data_support_dead_channels_excluded.png")
    assert "PATTERN_DEAD_CHANNELS" not in {d.code for d in clean.diagnostics}

    # Two channels of 5750. Measured: Rwp 0.55345 against 0.00156, a factor of
    # 355, and the cell 342 ppm apart — while **both** fits report
    # ``converged``. That is what the code is for: the fit does not fail, it
    # answers, and the answer is wrong.
    assert spoilt.status == clean.status == "converged"
    assert spoilt.statistics.rwp > 100 * clean.statistics.rwp
    assert clean.statistics.gof == pytest.approx(1.0, abs=0.1)

    def cell_a(result):
        return next(p.value for p in result.parameters
                    if p.path == "phases.0.cell.a")

    assert cell_a(clean) == pytest.approx(TRUE_A, abs=1e-4)
    assert abs(cell_a(spoilt) - TRUE_A) > 10 * abs(cell_a(clean) - TRUE_A)


def test_the_interval_the_finding_quotes_really_excludes_the_run():
    """The message tells a caller to exclude ``(lo, hi)``, so ``(lo, hi)`` has
    to contain the channels it names.

    ``PatternData.in_range_mask`` compares the quoted bound against the stored
    double, and a bound rounded to *nearest* three decimals can land inside
    the run: a 0.1° grid built by accumulation puts a channel at
    64.99999999999979, which prints as ``65.000``.  Following the message
    verbatim then left that channel in the fit, which is the one outcome the
    finding exists to prevent.
    """
    from rietx.io.readers import _dead_channel_diagnostics

    data = _monitor_normalised(dead=(600, 601))
    diags = _dead_channel_diagnostics(data, "synthetic")
    assert len(diags) == 1
    lo, hi = (float(v) for v in diags[0].where[0].split("-"))
    assert f"({lo:.3f}, {hi:.3f})" in diags[0].suggestion

    excluded = data.model_copy(update={"excluded_regions": [(lo, hi)]})
    mask = excluded.in_range_mask()
    assert not mask[600] and not mask[601]
    # and it is not a wide cut: at most one live channel a side
    assert int((~mask).sum()) <= 4


# --------------------------------------------------------------------------
# what drives an atom, not what it is called (WP-2067, issue #1250)
# --------------------------------------------------------------------------

#: One public synthetic state per family that drives atoms, with the count by
#: hand: every free ``phases.*`` path except the cell and the scale (WP-2067's
#: table), and for the variables every ``vars.X`` tied to an atom entry.  The
#: name test counted 4, 3, 2 and 0.
_FAMILY_COUNTS = [
    # mode amplitudes reach x, y, z through affine rows of C: four Biso + one A
    ("_state_distortion_modes", 5),
    # a body reaches its atoms through a derived block: one free atom's three
    # DOFs + origin (3) + rotation (3) + two twists
    ("_state_bodies", 11),
    # the same on a site: two DOFs + origin (2) + one rotation
    ("_state_bodies_site", 5),
    # vars.B drives two Biso, vars.D a coordinate DOF; vars.S drives the scale
    ("_state_families_variable", 2),
]


def _cross_backend_state(name):
    from tests import test_cross_backend as tcb

    return getattr(tcb, name)()


@pytest.mark.parametrize("state, expected", _FAMILY_COUNTS)
def test_the_count_reads_what_a_column_reaches(state, expected):
    """A free column that reaches an atom entry counts, whatever its own path.

    Asserted through :func:`data_support` as the fit calls it, so the ratio
    the band is read against moves with the count: 15/5, 38/11, 17/5, 22/2.
    """
    model, table, _ = _cross_backend_state(state)
    ds = data_support(model, table.decode(table.x0()), table)
    assert ds.n_structural_parameters == expected
    assert ds.observations_per_parameter == pytest.approx(
        ds.n_unique_reflections / expected)


def test_a_variable_on_a_coordinate_dof_is_the_parameter_counted():
    """``vars.D`` tied to ``atoms.1.dof.0`` is the free column, and the DOF it
    drives is not free, so the name test counted neither (#1250's sibling).

    The negative arm sits in the same table: ``vars.S`` drives the phase scale,
    which §9 leaves out, so it is not counted however it is spelled.
    """
    _, table, _ = _cross_backend_state("_state_families_variable")
    assert "phases.0.atoms.1.dof.0" not in table.free_paths
    assert structural_free_paths(table) == ["vars.B", "vars.D"]


@pytest.mark.parametrize("state", ["_state_bodies", "_state_bodies_site"])
def test_a_body_frame_is_not_a_structural_parameter(state):
    """Through C the cell reaches every body atom, since the block reads it to
    turn Å into fractions, and it is still not counted: it is the block's
    ``frame_inputs``, which peak positions pay for (McCusker §9)."""
    _, table, _ = _cross_backend_state(state)
    cell = [p for p in table.free_paths if ".cell." in p]
    reach = table.column_reach()
    assert cell and all(any(".atoms." in q for q in reach[p]) for p in cell)
    assert not set(cell) & set(structural_free_paths(table))


@pytest.mark.parametrize("state", ["_state_families", "_state_families_tied"])
def test_plain_atoms_count_what_the_name_test_counted(state):
    """The positive arm: with no variable, mode or body, the reach test is the
    name test, path for path, so every plain-atom fit's record is unchanged."""
    import fnmatch

    _, table, _ = _cross_backend_state(state)
    assert structural_free_paths(table) == [
        p for p in table.free_paths
        if fnmatch.fnmatch(p, STRUCTURAL_PARAMETER_GLOB)]
