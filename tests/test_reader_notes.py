"""A reader's repairs reach the fit's diagnostics (WP-2304).

``read_pattern`` used to report what it repaired or noticed only into a list
the caller passed, so a file whose intensities were rescaled, or whose σ was
withheld or constant, was fitted with no word in ``result.diagnostics``.  The
notes now ride on ``PatternData.diagnostics`` and every fit hands them on,
once per code.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import Refinement
from rietx.schemas.common import Diagnostic
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_readers import write_ras
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_SCALE,
    TRUE_W,
    TRUE_ZERO,
    WAVELENGTH,
    synthesize,
)
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"

#: the module fixture ``truth`` is shared, so the module keeps to one worker
pytestmark = pytest.mark.xdist_group("reader-notes")

#: scale and background alone: the notes are what is under test, not the fit
PLAN = RefinementPlan(stages=[Stage(
    name="scale", turn_on=["phases.*.scale", "instrument.background.*"])])


def _models():
    """LaB6 at the synthetic truth but for its scale, which the plan frees."""
    structure = make_lab6()
    for c in ("a", "b", "c"):
        getattr(structure.phases[0].cell, c).value = TRUE_A
    structure.phases[0].scale.value = TRUE_SCALE * 1.8
    instrument = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    instrument.zero_shift.value = TRUE_ZERO
    instrument.profile.w.value = TRUE_W
    instrument.background = BackgroundChebyshev.with_terms(3)
    return structure, instrument


def _save(result, name: str) -> None:
    pytest.importorskip("matplotlib")
    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

    plot_result(result, path=str(OUT / name))


@pytest.fixture(scope="module")
def truth() -> rx.PatternData:
    return synthesize()


def _xye(path: Path, tt, y, sig) -> Path:
    path.write_text("\n".join(f"{a:.5f} {b:.4f} {c:.4f}"
                              for a, b, c in zip(tt, y, sig)) + "\n",
                    encoding="utf-8")
    return path


def _scaled(data, tmp_path):
    # a rate under a "counts" label and no counting time: σ is withheld
    rows = [(f"{a:.5f}", f"{b / 7.3:.4f}", "1.0")
            for a, b in zip(data.tt(), data.y())]
    return write_ras(tmp_path / "rate.ras", rows)


def _constant(data, tmp_path):
    return _xye(tmp_path / "flat.xye", data.tt(), data.y(),
                np.full(data.y().size, 10.0))


def _nonpositive(data, tmp_path):
    sig = np.sqrt(np.maximum(data.y(), 1.0))
    sig[700] = 0.0
    return _xye(tmp_path / "zero.xye", data.tt(), data.y(), sig)


FILES = {"PATTERN_INTENSITY_SCALED": _scaled,
         "PATTERN_SIGMA_CONSTANT": _constant,
         "PATTERN_SIGMA_NONPOSITIVE": _nonpositive}


def _codes(diagnostics) -> list[str]:
    return [d.code for d in diagnostics]


@pytest.mark.parametrize("code", sorted(FILES))
def test_a_repair_read_without_a_list_reaches_the_fit_once(code, truth, tmp_path):
    """The acceptance: no ``diagnostics=`` list, and the code is still on the
    result, exactly once."""
    data = rx.read_pattern(FILES[code](truth, tmp_path))
    assert code in _codes(data.diagnostics)

    structure, instrument = _models()
    result = Refinement(structure, instrument, history=False).fit(data, plan=PLAN)
    _save(result, f"reader_notes_{code.lower()}.png")
    assert _codes(result.diagnostics).count(code) == 1


def test_a_passed_list_still_gets_the_same_notes(truth, tmp_path):
    found: list[Diagnostic] = []
    data = rx.read_pattern(_constant(truth, tmp_path), diagnostics=found)
    assert found == data.diagnostics
    assert _codes(found) == ["PATTERN_SIGMA_CONSTANT"]


def test_the_fit_owns_the_dead_channel_question(truth):
    """A dead cell is judged on the channels the fit fits, so the reader's copy
    is never handed on: a caller who excluded the interval would otherwise be
    told to exclude it again."""
    note = Diagnostic(level="warning", code="PATTERN_DEAD_CHANNELS",
                      message="2 channel(s) at 10.000-10.005° measure 0.1% of "
                              "the local background.",
                      where=["10.000-10.005"])
    data = truth.model_copy(update={"diagnostics": [note]})
    structure, instrument = _models()
    result = Refinement(structure, instrument, history=False).fit(data, plan=PLAN)
    assert "PATTERN_DEAD_CHANNELS" not in _codes(result.diagnostics)


def test_a_series_carries_each_patterns_own_notes(truth, tmp_path):
    flat = rx.read_pattern(_constant(truth, tmp_path))
    plain = truth
    structure, instrument = _models()
    series = rx.refine_sequential([flat, plain], structure, instrument,
                                  plan=PLAN)
    first, second = series.entries
    assert _codes(first.diagnostics).count("PATTERN_SIGMA_CONSTANT") == 1
    assert "PATTERN_SIGMA_CONSTANT" not in _codes(second.diagnostics)


def test_a_joint_fit_carries_each_patterns_own_notes(truth, tmp_path):
    flat = rx.read_pattern(_constant(truth, tmp_path))
    structure, instrument = _models()
    _, other = _models()
    result = rx.refine_joint([flat, truth], structure, [instrument, other],
                             plan=PLAN)
    first, second = result.patterns
    assert _codes(first.diagnostics).count("PATTERN_SIGMA_CONSTANT") == 1
    assert "PATTERN_SIGMA_CONSTANT" not in _codes(second.diagnostics)


def test_advice_already_taken_is_not_handed_on(truth, tmp_path):
    """A note whose advice the caller followed before fitting stays with the
    file: σ set to ``None`` after ``PATTERN_SIGMA_CONSTANT``, and an axis
    note whose interval at or below 0° holds no fitted channel."""
    flat = rx.read_pattern(_constant(truth, tmp_path))
    assert "PATTERN_SIGMA_CONSTANT" in _codes(flat.diagnostics)
    flat.sigma = None
    axis = Diagnostic(level="warning", code="PATTERN_X_AXIS_IMPLAUSIBLE",
                      message="the x axis starts at 0°.", where=["-0.001-0.001"])
    data = flat.model_copy(update={"diagnostics": [*flat.diagnostics, axis]})
    structure, instrument = _models()
    result = Refinement(structure, instrument, history=False).fit(data, plan=PLAN)
    codes = _codes(result.diagnostics)
    assert "PATTERN_SIGMA_CONSTANT" not in codes
    assert "PATTERN_X_AXIS_IMPLAUSIBLE" not in codes


def test_a_lossless_repair_stays_with_the_file(truth, tmp_path):
    """A scan stored backwards, with one point written twice, is the same
    measurement once repaired: the notes stay on the pattern and the fit
    repeats neither."""
    tt, y = truth.tt(), truth.y()
    sig = np.sqrt(np.maximum(y, 1.0))
    order = np.sort(np.r_[np.arange(tt.size), 300])[::-1]  # point 300 twice
    data = rx.read_pattern(_xye(tmp_path / "backwards.xye", tt[order],
                                y[order], sig[order]))
    assert {"PATTERN_SCAN_REVERSED", "PATTERN_DUPLICATE_POINTS"} <= set(
        _codes(data.diagnostics))

    structure, instrument = _models()
    result = Refinement(structure, instrument, history=False).fit(data, plan=PLAN)
    codes = _codes(result.diagnostics)
    assert "PATTERN_SCAN_REVERSED" not in codes
    assert "PATTERN_DUPLICATE_POINTS" not in codes


@pytest.mark.parametrize("how", ["poisson", "excluded"])
def test_a_point_back_in_the_fit_settles_the_nonpositive_note(how, truth,
                                                              tmp_path):
    """The note says its points are left out of the fit; once the caller
    weights them at the Poisson σ, or excludes them, none is."""
    data = rx.read_pattern(_nonpositive(truth, tmp_path))
    assert "PATTERN_SIGMA_NONPOSITIVE" in _codes(data.diagnostics)
    if how == "poisson":
        data.nonpositive_sigma = "poisson"
    else:
        at = float(truth.tt()[700])
        data.excluded_regions = [(at - 0.001, at + 0.001)]

    structure, instrument = _models()
    result = Refinement(structure, instrument, history=False).fit(data, plan=PLAN)
    assert "PATTERN_SIGMA_NONPOSITIVE" not in _codes(result.diagnostics)


def test_an_assigned_sigma_settles_a_withheld_sigma_note(truth, tmp_path):
    """Three notes say σ was withheld and the Poisson σ used; a σ the caller
    assigns settles each.  The GSAS counter note also doubts the intensity
    scale, which no σ settles, so it stays."""
    data = rx.read_pattern(_scaled(truth, tmp_path))
    rate = next(n for n in data.diagnostics
                if n.code == "PATTERN_INTENSITY_SCALED")
    zeros = np.zeros(truth.y().size)
    none = rx.read_pattern(_xye(tmp_path / "nosig.xye", truth.tt(), truth.y(),
                                zeros)).diagnostics
    assert _codes(none) == ["PATTERN_SIGMA_NONPOSITIVE"]
    weight = Diagnostic(level="info", code="PATTERN_WEIGHT_UNUSABLE",
                        message="_pd_proc_ls_weight holds 3 negative weight(s).",
                        where=["_pd_proc_ls_weight"])
    counters = Diagnostic(level="warning", code="PATTERN_INTENSITY_SCALED",
                          message="the STD bank's counter numbers run 1 to 20.",
                          where=["intensity", "sigma"])
    data = data.model_copy(update={
        "diagnostics": [*data.diagnostics, *none, weight, counters]})
    data.sigma = list(np.sqrt(np.maximum(data.y(), 1.0)) / 7.3)

    structure, instrument = _models()
    result = Refinement(structure, instrument, history=False).fit(data, plan=PLAN)
    kept = list(result.diagnostics)
    assert counters in kept
    assert rate not in kept
    assert "PATTERN_SIGMA_NONPOSITIVE" not in _codes(kept)
    assert "PATTERN_WEIGHT_UNUSABLE" not in _codes(kept)


def test_a_varying_sigma_settles_the_constant_sigma_note(truth, tmp_path):
    flat = rx.read_pattern(_constant(truth, tmp_path))
    assert "PATTERN_SIGMA_CONSTANT" in _codes(flat.diagnostics)
    flat.sigma = list(np.sqrt(np.maximum(flat.y(), 1.0)))

    structure, instrument = _models()
    result = Refinement(structure, instrument, history=False).fit(flat, plan=PLAN)
    assert "PATTERN_SIGMA_CONSTANT" not in _codes(result.diagnostics)
