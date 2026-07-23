"""Multi-histogram joint refinement (WP-0308).

Synthesize two LaB6 patterns of the *same* crystal at two wavelengths, refine
them jointly, and check the shared cell is recovered — better than either
pattern alone — with per-histogram Rwp reported separately.  A second test
corrupts one histogram and checks its own Rwp exposes it rather than the pooled
number masking it.
"""

from pathlib import Path

import numpy as np
import pytest

from pxrdref import (
    Instrument,
    MultiHistogramRefinement,
    Parameter,
    PatternData,
    Refinement,
    refine_multi,
)
from pxrdref.model.forward import compile_model
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.instrument import BackgroundChebyshev
from tests.test_schemas import make_lab6

TRUE_A = 4.15660
OUT = Path(__file__).parent / "output"


def synthesize(wavelength: float, tt_lo: float, tt_hi: float, *,
               scale: float, zero: float, bkg: list[float],
               step: float = 0.005, seed: int = 7) -> PatternData:
    """A single-wavelength Debye-Scherrer LaB6 pattern with known parameters."""
    structure = make_lab6()
    for k in ("a", "b", "c"):
        getattr(structure.phases[0].cell, k).value = TRUE_A
    structure.phases[0].scale.value = scale
    ins = Instrument.debye_scherrer(wavelength=wavelength)
    ins.zero_shift.value = zero
    ins.profile.w.value = 3e-4
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=v) for v in bkg])

    tt = np.arange(tt_lo, tt_hi, step)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def perturbed_inputs():
    """Shared structure (cell off by ~0.1 %) + two fresh instruments to refine."""
    structure = make_lab6()
    for k in ("a", "b", "c"):
        getattr(structure.phases[0].cell, k).value = TRUE_A + 0.004
    ins0 = Instrument.debye_scherrer(wavelength=0.41390)
    ins0.background = BackgroundChebyshev.with_terms(3)
    ins1 = Instrument.debye_scherrer(wavelength=0.71070)
    ins1.background = BackgroundChebyshev.with_terms(3)
    return structure, [ins0, ins1]


@pytest.fixture(scope="module")
def two_patterns() -> list[PatternData]:
    return [
        synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]


def _single_cell_esd(pattern: PatternData, wavelength: float) -> float:
    """esd(a) from refining one histogram alone (for the joint-vs-single check)."""
    structure = make_lab6()
    for k in ("a", "b", "c"):
        getattr(structure.phases[0].cell, k).value = TRUE_A + 0.004
    ins = Instrument.debye_scherrer(wavelength=wavelength)
    ins.background = BackgroundChebyshev.with_terms(3)
    res = Refinement(structure, ins, history=False).fit(pattern, plan="mccusker_default")
    return res.parameter("phases.0.cell.a").stderr


def test_joint_recovers_shared_cell(two_patterns):
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(two_patterns, plan="mccusker_default")

    assert result.status == "converged"
    assert len(result.histograms) == 2

    # per-histogram Rwp is reported separately and both fit well
    for h, hist in enumerate(result.histograms):
        assert hist.statistics.rwp < 0.12, f"hist {h} Rwp {hist.statistics.rwp}"
        OUT.mkdir(exist_ok=True)
        result.for_histogram(h).plot(OUT / f"multihist_joint_h{h}.png")

    # the shared cell is one refined number, recovered within esds
    a = ref.fitted_structures[0].phases[0].cell.a.value
    a_esd = result.parameter("phases.0.cell.a").stderr
    assert a_esd is not None and a_esd > 0
    assert a == pytest.approx(TRUE_A, abs=max(5 * a_esd, 5e-5))

    # …and every histogram's structure carries the *same* shared cell
    assert ref.fitted_structures[1].phases[0].cell.a.value == pytest.approx(a, rel=1e-12)
    # cubic tie still holds inside the shared structure
    assert ref.fitted_structures[0].phases[0].cell.b.value == pytest.approx(a, rel=1e-12)

    # joint esd beats either histogram alone (two measurements of one quantity)
    esd_single = [_single_cell_esd(two_patterns[0], 0.41390),
                  _single_cell_esd(two_patterns[1], 0.71070)]
    assert a_esd < min(esd_single), f"joint {a_esd} vs singles {esd_single}"

    # per-histogram scales are genuinely independent columns (different values)
    s0 = result.parameter("hist.0.phases.0.scale").value
    s1 = result.parameter("hist.1.phases.0.scale").value
    assert s0 != s1
    # provenance records the (unit) weighting explicitly
    assert "histogram_weights" in result.provenance.notes


def test_bad_histogram_shows_in_its_own_rwp(two_patterns):
    # corrupt the second pattern with a large unmodelled impurity peak: the
    # shared model can still fit histogram 0, so a pooled Rwp would understate
    # the damage — the per-histogram Rwp must expose it.
    good = two_patterns[0]
    tt = np.asarray(two_patterns[1].two_theta)
    y = np.asarray(two_patterns[1].intensity, dtype=float)
    y = y + 4000.0 * np.exp(-0.5 * ((tt - 20.0) / 0.05) ** 2)
    bad = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    structure, instruments = perturbed_inputs()
    result = refine_multi([good, bad], structure, instruments, plan="mccusker_default")

    r_good = result.histograms[0].statistics.rwp
    r_bad = result.histograms[1].statistics.rwp
    assert r_good < 0.12
    assert r_bad > 2.0 * r_good, f"bad hist Rwp {r_bad} did not stand out from {r_good}"
    # the pooled number sits below the bad histogram's own — i.e. it *would*
    # have masked it without the per-histogram breakdown
    assert result.statistics.rwp < r_bad

    OUT.mkdir(exist_ok=True)
    for h in range(2):
        result.for_histogram(h).plot(OUT / f"multihist_bad_h{h}.png")


def test_rietveld_only():
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    dummy = PatternData(two_theta=[1.0, 2.0], intensity=[1.0, 1.0])
    with pytest.raises(NotImplementedError):
        ref.fit([dummy, dummy], mode="lebail")
