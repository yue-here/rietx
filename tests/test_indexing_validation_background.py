"""The validation fit's background follows the data, so a band is not lines (WP-2113).

Issue #1382: on forward-modelled silicon under a background falling from ~2300
to ~800 counts over 11-22°, the true cubic F cell's whole-pattern validation
left 72 ``unmatched_observed`` lines under the instrument's four Chebyshev
terms, 56 of them below silicon's first line at 28.4°.  Layer 0 reads every
local maximum of a Δ/σ ≥ 5 band as a peak, so ``INDEX_IMPURITY_LINES`` reported
dozens of impurity lines on a pure phase.  The validation now sizes a Chebyshev
background with ``auto_background(kind="chebyshev")``; these tests hold the
band at zero, the switch-off at the old count (the arm that shows the first
test can fail), and six planted impurity lines, two on the band, still counted.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.indexing.workflow import _size_validation_background, validate_by_lebail
from rietx.schemas.indexing import CellCandidate
from rietx.schemas.instrument import BackgroundChebyshev, BackgroundPSpline
from tests._synthetic_silicon import A_SI, silicon_pattern

OUT = Path(__file__).parent / "output"
FIRST_SI_LINE = 28.0      # Si 111 is at 28.44°; nothing real lies below this
LIMITS = (10.0, 110.0)
INSTRUMENT = rx.Instrument.bragg_brentano(radiation="CuKa")
#: (2θ, peak counts) of the planted impurity: FWHM 0.06°, two on the band
PLANTED = ((20.0, 1500.0), (24.0, 1000.0), (35.0, 1500.0), (41.0, 800.0),
           (52.0, 600.0), (63.0, 400.0))

# the module fixtures are shared by every test here: pin the module
pytestmark = pytest.mark.xdist_group("indexing-validation-background")


def _planted(data: rx.PatternData) -> rx.PatternData:
    tt = np.asarray(data.two_theta)
    add = np.zeros_like(tt)
    for t0, height in PLANTED:
        u = (tt - t0) ** 2 / 0.06 ** 2
        add += height * (0.4 / (1 + 4 * u) + 0.6 * np.exp(-4 * np.log(2) * u))
    y = np.asarray(data.intensity) + np.random.default_rng(2).poisson(add)
    return rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0)).tolist())


@pytest.fixture(scope="module")
def steep():
    return silicon_pattern("steep")


@pytest.fixture(scope="module")
def candidate():
    af = 1.0 / A_SI ** 2
    return CellCandidate(cell=(A_SI,) * 3 + (90.0,) * 3, cell_esd=(1e-4,) * 6,
                         system="cubic", centring="F", lattice_group="F m -3 m",
                         volume=A_SI ** 3, volume_esd=1e-3,
                         af=(af,) * 3 + (0.0,) * 3, n_indexed=8, n_lines=8,
                         chi2_red=1.0)


def _validate(candidate, data, **kw):
    peaks = rx.pick_peaks(data, INSTRUMENT, two_theta_range=LIMITS)
    return validate_by_lebail(candidate, data, INSTRUMENT, peaks=peaks,
                              two_theta_limits=LIMITS, with_result=True, **kw)


def test_the_steep_band_is_not_read_as_unmatched_lines(steep, candidate):
    validation, result = _validate(candidate, steep)
    below = [t for t in validation.unmatched_observed_two_theta if t < FIRST_SI_LINE]
    assert below == [], below
    assert validation.background_terms is not None
    assert validation.background_terms > len(INSTRUMENT.background.coefficients)
    from rietx.viz import plot_validation

    OUT.mkdir(exist_ok=True)
    plot_validation(validation, result,
                    path=str(OUT / "indexing_silicon_steep_validation_sized.png"))


def test_the_declared_background_still_reads_the_band(steep, candidate):
    """The positive arm: switched off, the four declared terms leave the band
    in the residual and the count is the issue's, so the test above can fail."""
    validation, _ = _validate(candidate, steep, size_background=False)
    below = [t for t in validation.unmatched_observed_two_theta if t < FIRST_SI_LINE]
    assert len(below) >= 40, len(below)
    assert validation.background_terms == len(INSTRUMENT.background.coefficients)


def test_a_planted_impurity_line_stays_reported(steep, candidate):
    validation, result = _validate(candidate, _planted(steep))
    found = validation.unmatched_observed_two_theta
    missed = [t0 for t0, _ in PLANTED if not any(abs(t - t0) < 0.1 for t in found)]
    assert missed == [], (missed, found)
    from rietx.viz import plot_validation

    OUT.mkdir(exist_ok=True)
    plot_validation(validation, result,
                    path=str(OUT / "indexing_silicon_steep_planted_validation.png"))


def test_sizing_keeps_a_declared_background(steep):
    """Never fewer terms than declared, the declared starts kept; another kind
    of background is the caller's and comes back as it was."""
    wide = INSTRUMENT.model_copy(deep=True)
    wide.background = BackgroundChebyshev.with_terms(20)
    wide.background.coefficients[0].value = 1234.0
    assert _size_validation_background(wide, steep, LIMITS) is wide

    sized = _size_validation_background(INSTRUMENT, steep, LIMITS)
    n = len(sized.background.coefficients)
    assert n > len(INSTRUMENT.background.coefficients)
    assert len(INSTRUMENT.background.coefficients) == 4, "the input is never mutated"
    with warnings.catch_warnings():
        # the steep band takes the scan to its cap (BACKGROUND_ORDER_AT_CAP)
        warnings.simplefilter("ignore", UserWarning)
        chosen = rx.auto_background(steep, kind="chebyshev", two_theta_limits=LIMITS)
    assert n == len(chosen.background.coefficients)

    spline = INSTRUMENT.model_copy(deep=True)
    spline.background = BackgroundPSpline.for_range(*LIMITS, knot_step_deg=8.0)
    assert _size_validation_background(spline, steep, LIMITS) is spline
