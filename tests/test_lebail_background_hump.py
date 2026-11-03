"""WP-1542: a Le Bail background under a broad hump, from a seed and from SNIP.

The fixture is the Pnma pattern of ``test_auto_background_seed.py`` (CW
neutron, 2.4 Å, 0.1° step, FWHM 0.5°, a pedestal of 300 + 2·(2θ) counts) with a
broad Gaussian hump added under the peaks: 600 counts high at 50°, σ = 6°.
Without the hump it is that file's pedestal pattern, noise draw included.

Measured on macOS arm64, ``[dev]``, one Le Bail pass of ``profile_only`` from
the true cell and widths (Rwp; background over the truth at 50°):

=====================================  ========  ==========
protocol                               hump      no hump
=====================================  ========  ==========
P-spline, every coefficient at 0       10.13 %   5.71 %
P-spline, ``seed=True``                9.37 %    4.76 %
the seed, then five background stages  6.32 %    4.33 %
P-spline co-refined from a SNIP start  6.26 %    4.32 %
SNIP held under a 4-term Chebyshev     4.41 %    4.28 %
the true background held               4.07 %    —
=====================================  ========  ==========

Under the seed the background at 50° ends at 0.83 of the truth, and at 0.87
for every protocol that co-refines it.  Held from SNIP it ends at 0.97.  The
Le Bail intensities are partitioned against the background a stage starts
from and then held for its solve, so each stage closes about half of the
background's remaining distance (0.35, 0.64, 0.76, 0.81, 0.84 of the truth at
50° across the first five stages).  Where peaks crowd, the counts the
background has not reached go to the reflections: in
``tests/output/lebail_hump_seed_zoom.png`` the three reflections at 49-54° are
drawn at about twice the observed height, with the hump beneath them.

The SNIP window matters.  At 15 points (three peak FWHMs) the held curve
keeps the hump.  At 60 points, the width of the hump itself, SNIP clips the
hump too and the fit ends at Rwp 20.9 %, worse than any seed.

Not ``slow``: the four fits take about a second together, and the rest of the
module's setup is drawing its six PNGs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.background import diagnose, snip
from rietx.background.auto import HUMP_TRIGGER
from tests.test_auto_background_seed import _neutron, _phase

GRID = np.arange(10.0, 150.0, 0.1)
LIMITS = (10.0, 150.0)
HUMP_HEIGHT, HUMP_CENTRE, HUMP_SIGMA = 600.0, 50.0, 6.0
#: the fixture's peak FWHM in channels (0.5° on a 0.1° step)
FWHM_POINTS = 5


def _true_background(hump: bool) -> np.ndarray:
    b = 300.0 + 2.0 * GRID
    if hump:
        b = b + HUMP_HEIGHT * np.exp(-0.5 * ((GRID - HUMP_CENTRE) / HUMP_SIGMA) ** 2)
    return b


def _pattern(hump: bool) -> rx.PatternData:
    truth = rx.Refinement(rx.Structure(phases=[_phase(0.02)]), _neutron())
    y = np.asarray(truth.predict(GRID)) + _true_background(hump)
    y = np.maximum(y + np.random.default_rng(1).normal(
        scale=np.sqrt(np.maximum(y, 1.0))), 0)
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


def _snip_held(data: rx.PatternData, half_window: int):
    """The skill's protocol: a SNIP estimate held, a 4-term Chebyshev on top."""
    est = snip(np.asarray(data.intensity), half_window)
    return rx.BackgroundFixedPlusChebyshev.from_pattern(
        rx.PatternData(two_theta=data.two_theta, intensity=est.tolist()),
        source="snip")


def _fit(data: rx.PatternData, background, name: str, hump: bool, zoom: bool = False):
    ins = _neutron()
    ins.background = background
    ref = rx.Refinement(rx.Structure(phases=[_phase(0.02)]), ins)
    result = ref.fit(data, mode="lebail", plan="profile_only", telemetry=False)
    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / f"lebail_hump_{name}.png"))
    if zoom:
        plot_result(result, path=str(out / f"lebail_hump_{name}_zoom.png"),
                    two_theta_range=(30.0, 70.0))
    widths = {p.path.rsplit(".", 1)[-1]: (p.value, p.stderr) for p in result.parameters
              if p.path.startswith("instrument.profile.")}
    ratio = (np.interp(HUMP_CENTRE, result.two_theta, result.y_background)
             / np.interp(HUMP_CENTRE, GRID, _true_background(hump)))
    return result.statistics.rwp, float(ratio), widths


@pytest.fixture(scope="module")
def hump() -> rx.PatternData:
    return _pattern(True)


@pytest.fixture(scope="module")
def fits(hump):
    flat = _pattern(False)
    seeded = rx.auto_background(hump, two_theta_limits=LIMITS, seed=True).background
    return {
        "seed": _fit(hump, seeded, "seed", True, zoom=True),
        "snip": _fit(hump, _snip_held(hump, 3 * FWHM_POINTS), "snip", True, zoom=True),
        "snip_wide": _fit(hump, _snip_held(hump, 60), "snip_wide", True),
        "no_hump": _fit(flat, rx.auto_background(
            flat, two_theta_limits=LIMITS, seed=True).background, "no_hump", False),
    }


@pytest.mark.xdist_group("lebail-hump")
def test_from_a_seed_part_of_the_hump_goes_to_the_reflections(fits):
    rwp_seed, at_centre, _ = fits["seed"]
    rwp_snip, _, _ = fits["snip"]
    # 0.83 of the truth at the centre, and Rwp 9.37 % against 4.41 %
    assert at_centre < 0.9
    assert rwp_seed > 1.5 * rwp_snip


def _widths_off(widths, flat) -> list[str]:
    """The widths further than two combined esds from the no-hump fit's."""
    assert widths and widths.keys() == flat.keys()
    return [name for name, (value, esd) in widths.items()
            if abs(value - flat[name][0]) > 2.0 * np.hypot(esd or 0.0, flat[name][1] or 0.0)]


@pytest.mark.xdist_group("lebail-hump")
def test_snip_held_keeps_the_hump_and_the_no_hump_widths(fits):
    """The width bar is coarse: the esds are as large as the widths, so the
    seeded fit's X (0.048 ± 0.046) passes it too.  It catches a gross failure,
    the 60-point window below, and the background ratio carries the rest."""
    _, at_centre, widths = fits["snip"]
    assert 0.93 < at_centre < 1.07  # 0.966
    assert _widths_off(widths, fits["no_hump"][2]) == []


@pytest.mark.xdist_group("lebail-hump")
def test_a_snip_window_as_wide_as_the_hump_clips_the_hump_too(fits):
    # 20.9 % at 60 points against 4.41 % at 15, and X 0.33 against 0
    rwp, at_centre, widths = fits["snip_wide"]
    assert rwp > 2.0 * fits["snip"][0]
    assert at_centre < 0.8
    assert "x" in _widths_off(widths, fits["no_hump"][2])


@pytest.mark.xdist_group("lebail-hump")
def test_the_hump_score_sees_the_hump_and_not_the_pedestal(hump):
    # 0.23 against 0.032; the trigger is 0.05
    assert diagnose(hump).amorphous_hump_score > HUMP_TRIGGER
    assert diagnose(_pattern(False)).amorphous_hump_score < HUMP_TRIGGER
