"""rietx's flight-time forward model against TOPAS's, on a synthetic bank.

The corroboration Yue's ruling on yue-here/rietx issue #193 puts in this cut,
in CI: ``tests/data/tof/topas_synthetic/`` holds a synthetic two-phase bank
(``spec.json``), the ``.inp`` that ``rietx.io.projects.topas_tof.from_tof``
wrote for it, and the ``Y_calc`` TOPAS v6 computed from that input as a black
box.  Synthetic input, no measured data; the directory's README has the
program, the date and the hashes.

Three claims, each with the arm that could fail it:

* **the input is this tree's**: regenerating the ``.inp`` from ``spec.json``
  reproduces the vendored file byte for byte, so the comparison is of the
  model this tree would write and not of a stale one;
* **the curves agree** to 1.5e-3 of the maximum, the residual TOPAS's own
  exponential truncation leaves (measured 1.26e-3 and 1.05e-3);
* **the comparison can see an error**: DIFA's sign flipped, or α and β swapped,
  on the rietx side each miss by more than 0.1 of the maximum.

And, from ``tests/data/tof/topas_stack/``: TOPAS's un-weighted two-exponential
peak stack (``push_peak`` … ``add_pop_1st_2nd_peak``) is the same pulse to
the same bar, while the stack with ``scale_top_peak 3`` is not — the reason
``io/projects/topas_tof.py`` reads the first and refuses the second.
"""

from __future__ import annotations

import gzip
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

KIT = Path(__file__).resolve().parent / "data" / "tof" / "topas_synthetic"
CASES = ("type1", "type3")

#: max |TOPAS − rietx| / max(TOPAS).  TOPAS truncates each convolution
#: exponential at 1e-3 of its height and renormalises, which leaves ~1e-3 at
#: the peaks; measured 1.26e-3 (type 1) and 1.05e-3 (type 3) on this grid.
TOLERANCE = 1.5e-3
#: what a planted error must exceed, a factor ~70 above the bar and ~3-8
#: below what the two plants measured (0.37-0.86)
PLANT_FLOOR = 0.1


@pytest.fixture(scope="module")
def generator():
    """``generate.py``, imported without leaving bytecode in ``tests/data``."""
    spec = importlib.util.spec_from_file_location("topas_synthetic_generate",
                                                  KIT / "generate.py")
    module = importlib.util.module_from_spec(spec)
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    return module


def _topas(case: str) -> np.ndarray:
    with gzip.open(KIT / f"{case}_ycalc.txt.gz", "rt", encoding="ascii") as f:
        return np.loadtxt(f)


def _rietx(generator, structure, instrument) -> np.ndarray:
    from rietx.model.forward_tof import compile_tof_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    x = generator.grid()
    model = compile_tof_model(structure, instrument,
                              PatternData(tof=x.tolist(), intensity=[1.0] * len(x)))
    table = ParameterTable(structure, instrument)
    return np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64)


def _miss(topas: np.ndarray, y: np.ndarray) -> float:
    return float(np.max(np.abs(topas[:, 1] - y)) / np.max(topas[:, 1]))


@pytest.mark.parametrize("case", CASES)
def test_the_vendored_input_is_what_this_tree_writes(case, generator, tmp_path):
    generator.main(tmp_path)
    assert (tmp_path / f"{case}.inp").read_bytes() == (KIT / f"{case}.inp").read_bytes()


@pytest.mark.parametrize("case", CASES)
def test_rietx_reproduces_the_topas_ycalc(case, generator):
    topas = _topas(case)
    np.testing.assert_allclose(topas[:, 0], generator.grid(), rtol=0, atol=1e-9)
    structure, instrument = generator.models(case)
    assert _miss(topas, _rietx(generator, structure, instrument)) <= TOLERANCE


@pytest.mark.parametrize("case", CASES)
def test_a_planted_difa_sign_or_rate_swap_is_seen(case, generator):
    topas = _topas(case)
    structure, instrument = generator.models(case)
    flipped = instrument.model_copy(deep=True)
    flipped.source.difa.value = -flipped.source.difa.value
    assert _miss(topas, _rietx(generator, structure, flipped)) > PLANT_FLOOR

    swapped = instrument.model_copy(deep=True)
    p = swapped.source.profile_tof
    (p.alpha0.value, p.alpha1.value, p.beta0.value, p.beta1.value) = (
        p.beta0.value, p.beta1.value, p.alpha0.value, p.alpha1.value)
    assert _miss(topas, _rietx(generator, structure, swapped)) > PLANT_FLOOR


# ------------------------------------------------- the peak stack (topas_stack/)

STACK = KIT.parent / "topas_stack"


def _stack_rates(inp: str) -> tuple[float, float, float]:
    """(α, β, σ) as the ``.inp`` states them: ``exp_conv_const c`` is a rate
    −ln(0.001)/c, late for c > 0 (measured), and ``pv_fwhm`` a Gaussian FWHM."""
    import math
    import re

    text = (STACK / inp).read_text(encoding="ascii")
    rates = {}
    for c in map(float, re.findall(r"exp_conv_const\s+(-?[\d.]+)", text)):
        rates["late" if c > 0 else "early"] = math.log(1000.0) / abs(c)
    fwhm = float(re.search(r"pv_fwhm\s+([\d.]+)", text)[1])
    return rates["early"], rates["late"], fwhm / math.sqrt(8.0 * math.log(2.0))


def _stack_topas(name: str) -> np.ndarray:
    with gzip.open(STACK / f"{name}.txt.gz", "rt", encoding="ascii") as f:
        return np.loadtxt(f)


def test_the_unweighted_peak_stack_is_rietxs_back_to_back_pulse():
    """TOPAS's ``push_peak`` stack of one rise and one decay is the pulse rietx
    computes, to the fixture's bar; it is not the equal-weight sum."""
    from rietx.model.profiles.tof import back_to_back_gaussian

    alpha, beta, sigma = _stack_rates("stack_P.inp")
    assert (alpha, beta, sigma) == pytest.approx((0.2, 0.03, 10.0), rel=1e-12)
    topas = _stack_topas("stack_P_stack")
    dt = topas[:, 0] - 20000.0
    model = 1000.0 * np.asarray(back_to_back_gaussian(dt, alpha, beta, sigma))
    assert _miss(topas, model) <= TOLERANCE
    # the reading the old refusal assumed, two unit-area pulses summed, is far off
    from rietx.model.profiles.tof import back_to_back_gaussian as h
    rise = h(dt, alpha, 1e6, sigma)      # β → ∞: the rise member alone
    decay = h(dt, 1e6, beta, sigma)      # α → ∞: the decay member alone
    assert _miss(topas, 1000.0 * (np.asarray(rise) + np.asarray(decay))) > PLANT_FLOOR


def test_a_weighted_peak_stack_is_not_the_pulse():
    """The positive arm: ``scale_top_peak 3`` on one member is a different kind
    — TOPAS's peak misses the pulse by far more than the bar."""
    from rietx.model.profiles.tof import back_to_back_gaussian

    alpha, beta, sigma = _stack_rates("stack_PW.inp")
    topas = _stack_topas("stack_PW_stack_w3")
    model = 1000.0 * np.asarray(back_to_back_gaussian(
        topas[:, 0] - 20000.0, alpha, beta, sigma))
    assert _miss(topas, model) > PLANT_FLOOR
