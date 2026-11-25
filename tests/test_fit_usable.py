"""WP-1336: the fit says when it is unusable (issues #243 and #249).

Two channels, each owed a test.  ``status`` is the optimiser's exit and
``diagnostics`` is the quality channel, and ``RefinementResult.usable`` reads
both — so the #243 reproduction, which converges at an Rwp past
``MODEL_FAR_FROM_DATA``, must read ``usable is False`` while its ``status``
still says ``converged``.  And the indexing width census now runs on the fit:
a broad pattern fitted with a narrow declared instrument and no size or strain
terms names the width with ``PEAK_WIDTH_LAW_MISMATCH``, and the same pattern
with the size term freed does not.
"""

import dataclasses
from pathlib import Path
from typing import get_args

import numpy as np
import pytest

import rietx as rx
from rietx import Instrument, PatternData, Refinement
from rietx.indexing.peaks import detect_peaks, predicted_fwhm, width_census
from rietx.model.forward import PHASE_SUPPORT_SIGMA, compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Diagnostic, Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_schemas import make_lab6

DATA = Path(__file__).parent / "data"
WAVELENGTH = 0.4139
TRUE_A = 4.15660
TRUE_W = 2.5e-4
#: the specimen broadening the synthetic carries: a Lorentzian size term of
#: 0.1° (FWHM coefficient of 1/cosθ), against an instrument whose own lines are
#: √W ≈ 0.016° wide — a factor of ~6 at the census lines
BROAD_LOR_SIZE = 0.1

PLAN_NO_WIDTHS = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=30),
    rx.Stage("cell", ["phases.*.cell.*", "instrument.zero_shift"], max_iter=30),
])
PLAN_WITH_SIZE = rx.RefinementPlan(stages=[
    *PLAN_NO_WIDTHS.stages,
    rx.Stage("size", ["phases.*.lor_size"], max_iter=30),
])


def _lab6(lor_size: float = 0.0):
    structure = make_lab6()
    phase = structure.phases[0]
    for axis in (phase.cell.a, phase.cell.b, phase.cell.c):
        axis.value = TRUE_A
    phase.scale.value = 5e-4
    phase.lor_size.value = lor_size
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = TRUE_W
    return structure, ins


def _broad_pattern(lor_size: float) -> PatternData:
    structure, ins = _lab6(lor_size)
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 1.5)])
    tt = np.arange(3.0, 24.0, 0.005)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _fit(data: PatternData, plan, *, lor_size_seed: float = 0.0):
    structure, ins = _lab6(lor_size_seed)
    ins.background = BackgroundChebyshev.with_terms(3)
    return Refinement(structure, ins).fit(data, plan=plan)


def _width_rows(result):
    return [d for d in result.diagnostics if d.code == "PEAK_WIDTH_LAW_MISMATCH"]


@pytest.fixture(scope="module")
def broad():
    return _broad_pattern(BROAD_LOR_SIZE)


# -- #249: the width census reaches the refinement path ----------------------

def test_a_narrow_declared_instrument_on_broad_data_names_the_width(broad):
    result = _fit(broad, PLAN_NO_WIDTHS)
    rows = _width_rows(result)
    assert len(rows) == 1, [d.code for d in result.diagnostics]
    row = rows[0]
    assert row.level == "warning"
    assert row.value is not None and row.value >= 3.0   # data broader than the model
    assert row.where[0] == "phases.0"
    # the only width channels that existed before stay silent here, which is
    # what made the case invisible: no size or strain term was refined
    assert not {"SIZE_UNUSUALLY_SMALL", "STRAIN_UNUSUALLY_LARGE"} & {
        d.code for d in result.diagnostics}


def test_freeing_the_size_term_on_the_same_data_silences_it(broad):
    """The positive arm: the comparator is the *fitted* widths, so a model
    that can broaden and did is not told its instrument is wrong."""
    result = _fit(broad, PLAN_WITH_SIZE, lor_size_seed=0.02)
    assert not _width_rows(result), [d.message for d in _width_rows(result)]


def test_a_correctly_declared_instrument_is_silent():
    result = _fit(_broad_pattern(0.0), PLAN_NO_WIDTHS)
    assert not _width_rows(result), [d.message for d in _width_rows(result)]


def test_the_refinement_census_is_the_indexing_census(broad):
    """One census, two callers: ``width_census`` must measure what
    ``detect_peaks`` measures on the same channels, or the two paths would
    quote different widths for one pattern under one code."""
    structure, ins = _lab6()
    det = detect_peaks(broad, ins)
    tt, y, sig = broad.tt(), broad.y(), broad.sig()
    census = width_census(tt, y, sig, predicted_fwhm(tt, ins))
    assert census is not None
    positions, measured = census
    assert measured == det.fwhm_measured
    assert len(positions) == 12


# -- a phase the data cannot see is not a width candidate (#585 follow-up) ----

#: the major phase's specimen broadening for the two-phase case: the census
#: reads 0.065° against the declared instrument's 0.016°, a factor of 4
MAJOR_LOR_SIZE = 0.06
#: the minor phase's seeded (or runaway) size term — wide enough to land
#: within WIDTH_MISMATCH_RATIO of the census, which is what made it a decoy
MINOR_LOR_SIZE = 0.1
PLAN_MAJOR_ONLY = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.0.scale", "instrument.background.*"], max_iter=30),
    rx.Stage("cell", ["phases.0.cell.*", "instrument.zero_shift"], max_iter=30),
])


def _fit_with_minor(data: PatternData, minor_scale: float):
    """LaB6 with nothing free to widen it, beside a second cubic phase that
    carries ``MINOR_LOR_SIZE`` and is held at ``minor_scale``.  Returns the
    result and each phase's ``phase_support`` at the returned values."""
    structure, ins = _lab6()
    minor = make_lab6().phases[0]
    minor.name = "minor"
    for axis in (minor.cell.a, minor.cell.b, minor.cell.c):
        axis.value = 5.1
    minor.scale.value = minor_scale
    minor.lor_size.value = MINOR_LOR_SIZE
    structure.phases.append(minor)
    ins.background = BackgroundChebyshev.with_terms(3)
    ref = Refinement(structure, ins)
    result = ref.fit(data, plan=PLAN_MAJOR_ONLY)
    model = compile_model(ref.fitted_structure, ref.fitted_instrument, data,
                          mode="rietveld")
    table = ParameterTable(ref.fitted_structure, ref.fitted_instrument)
    return result, model.phase_support(table.decode(table.x0()))


@pytest.fixture(scope="module")
def four_times_broad():
    return _broad_pattern(MAJOR_LOR_SIZE)


def test_an_invisible_phase_does_not_silence_the_width_warning(four_times_broad):
    """Yue's case on #585: the major phase is 4x too narrow, and a minor phase
    at its scale floor carries a size term whose width lands near the census.
    Its width explains no line of the data, so it must not be the "closest
    phase" that silences the warning.  On main before the fix this fit
    returned no ``PEAK_WIDTH_LAW_MISMATCH`` at all."""
    result, support = _fit_with_minor(four_times_broad, minor_scale=1e-12)
    assert support[1] < PHASE_SUPPORT_SIGMA <= support[0]
    rows = _width_rows(result)
    assert len(rows) == 1, [d.code for d in result.diagnostics]
    (row,) = rows
    assert row.where[0] == "phases.0"
    assert row.value is not None and row.value >= 3.0


def test_a_visible_minor_phase_still_takes_part(four_times_broad):
    """The positive arm: the filter is support, not rank.  The same minor
    phase at a scale the data can see is a candidate as before, and its
    width, inside WIDTH_MISMATCH_RATIO of the census, keeps the fit silent."""
    result, support = _fit_with_minor(four_times_broad, minor_scale=1e-6)
    assert support[1] >= PHASE_SUPPORT_SIGMA
    assert not _width_rows(result), [d.message for d in _width_rows(result)]


# -- #243: status and diagnostics read one way about one solve ----------------

def _nac(seeded: bool, n_stages: int | None = None):
    if not (DATA / "11BM_NAC.fxye").exists():
        pytest.skip("11-BM NAC dataset not present")
    data = rx.read_pattern(DATA / "11BM_NAC.fxye")
    structure = rx.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    ins = rx.Instrument.debye_scherrer(wavelength=0.413957)
    ins.background = BackgroundChebyshev.with_terms(6)
    if seeded:  # as examples/nac_11bm.py seeds it
        ins.profile.w.value = 2e-5
        ins.profile.x.value = 2e-3
    plan = rx.RefinementPlan.lab_sample_refine()
    if n_stages is not None:
        plan = dataclasses.replace(plan, stages=plan.stages[:n_stages])
    return Refinement(structure, ins).fit(
        data, mode="lebail", plan=plan, two_theta_limits=(2.0, 24.0))


def test_issue_243_reproduction_reads_unusable_while_converged():
    """The issue's script on the repo's own fixture.  ``status`` keeps its one
    meaning — the solver's exit — and the two channels agree through the
    documented reading: an error-level diagnostic makes the fit unusable.

    Three stages of the plan, not all six.  Unseeded, the fit is 150 % from
    the data by then, and every later stage wanders: a 1e-12 change to the
    FD step moved the final Rwp from 1.56 to 2243 and the last stage from
    22 to 112 iterations.  Linux py3.11 stopped on ``max_iter`` after #857.
    The first three stages reach Rwp 1.613518, ``converged`` and
    ``MODEL_FAR_FROM_DATA`` at every one of eight nudges (macOS arm64)."""
    result = _nac(seeded=False, n_stages=3)
    assert result.status == "converged"
    errors = {d.code for d in result.diagnostics if d.level == "error"}
    assert "MODEL_FAR_FROM_DATA" in errors
    assert result.usable is False


def test_the_seeded_profile_reads_usable():
    """The positive arm of the reproduction: the fixture is fine, and the same
    call seeded as the example seeds it is a fit the predicate passes."""
    result = _nac(seeded=True)
    assert result.status == "converged"
    assert result.usable is True
    assert not _width_rows(result), [d.message for d in _width_rows(result)]


# -- the predicate is an expression over the level vocabulary -----------------

def test_usable_reads_the_level_vocabulary_not_a_code_list(broad):
    """WP-1037's rule for a derived flag: the predicate names a *level*, so
    this checks the level it names is still a member of the live vocabulary
    (an authority the predicate never consults), and that every level and
    every status reads the way the docstring says."""
    levels = get_args(Diagnostic.model_fields["level"].annotation)
    assert "error" in levels
    base = _fit(broad, PLAN_WITH_SIZE, lor_size_seed=0.02)
    assert base.status == "converged"
    for level in levels:
        probe = base.model_copy(update={"diagnostics": [
            Diagnostic(level=level, code="ANY_NEW_CODE", message="")]})
        assert probe.usable is (level != "error"), level
    for status in ("max_iter", "diverged"):
        assert base.model_copy(update={"status": status}).usable is False


# -- the joint path owes it per pattern (joint.DIAGNOSTIC_SCOPES) ----------

def test_a_joint_fit_names_the_width_on_the_histogram_it_belongs_to(broad):
    """One broad pattern and one the declared instrument describes, sharing
    one LaB6 with no width term freed: the row lands on the broad pattern
    with the single fit's own message, and nowhere else."""
    structure, ins = _lab6()
    ins.background = BackgroundChebyshev.with_terms(3)
    joint = rx.refine_joint([broad, _broad_pattern(0.0)], structure,
                            [ins, ins.model_copy(deep=True)], plan=PLAN_NO_WIDTHS)
    per_hist = [_width_rows(h) for h in joint.patterns]
    assert [len(rows) for rows in per_hist] == [1, 0], [
        [d.code for d in h.diagnostics] for h in joint.patterns]
    assert not _width_rows(joint), "the census is the pattern's, never the fit's"
    (row,) = per_hist[0]
    assert row.where == ["phases.0", "instrument.profile"]
    # the single fit's question, asked of this pattern: same census, same
    # fitted widths, same row
    (single,) = _width_rows(_fit(broad, PLAN_NO_WIDTHS))
    assert row.message == single.message
    assert row.value == pytest.approx(single.value, rel=1e-6)
