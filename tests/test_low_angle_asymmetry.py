"""WP-2056: ``LOW_ANGLE_ASYMMETRY_UNCALIBRATED`` — the lowest lines are magnetic.

Issue #1090's point 2.  On a constant-wavelength neutron pattern whose lowest
seen lines are all magnetic-only, no nuclear line in the sample checks the
axial asymmetry where it is largest.  The finding reports each such line's
centroid shift and decides nothing.

The arms, on the synthetic CrSBr k = (0, 0, 1/2) pattern of
``tests/_synthetic_crsbr.py`` (λ 2.449 Å; the magnetic (0 0 1) of the a,b,2c
child at 8.9°, the first nuclear line, (0 0 2), at 17.8°):

- **positive**: the truth is drawn with S/L = H/L = 0.03 and fitted with the
  asymmetry at 0.  The lowest line's shift is negative (the observed line
  sits low) by many esds.
- **null, same geometry**: no asymmetry in the truth or the model.  The finding
  still fires, because what fires it is the geometry, and the shift is inside
  three esds of zero.  This is the arm that fails if the shift were biased.
- **silent**: the same pattern fitted from 12°, above the magnetic line, so
  the lowest seen line is nuclear; and the paramagnetic pattern fitted with no
  magnetic component at all.

The real-data case (Ba₂FeSbSe₅ on G4.1 at 1.5 K) is asserted beside its
fixture, in ``tests/test_magnetic_series.py``.  PNGs of the lowest lines go to
``tests/output/`` (gitignored), stems ``low_angle_asymmetry_*``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.report.magnetic import _line_shifts
from rietx.strategy.staged import PLAN_PRESETS
from tests import _synthetic_crsbr as G

pytestmark = pytest.mark.xdist_group("low-angle-asymmetry")

CODE = "LOW_ANGLE_ASYMMETRY_UNCALIBRATED"
SEED = 2056
ASYMMETRY = 0.03


def _truth(asymmetry: float) -> rx.PatternData:
    ins = G.instrument()
    ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = asymmetry
    ref = rx.Refinement(rx.Structure(phases=[G.child_phase()]), ins)
    mean = np.asarray(ref.predict(G.blank()), dtype=float)
    counts = np.random.default_rng(SEED).poisson(mean).astype(float)
    return rx.PatternData(two_theta=G.TWO_THETA.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())


def _fit(data, limits=None):
    ref = rx.Refinement(G.start_structure(), G.instrument())
    G.apply_ties(ref)
    plan = rx.RefinementPlan(stages=[PLAN_PRESETS["magnetic_width"]().stages[0]])
    res = ref.fit(data, plan=plan, two_theta_limits=limits)
    return ref, res


def _lowest(ref):
    """The lowest seen line's (position, shift, esd), read the way the finding reads it."""
    model, values = ref._model, ref._answer["values"]
    r = np.asarray(model.y_obs) - np.asarray(model.evaluate(values))
    _, pos, _, frac, shift, esd, _ = _line_shifts(model, values, r,
                                                 np.asarray(model.sigma))[0]
    return pos, frac, shift, esd


def _draw(res, stem):
    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(res, path=str(out / f"low_angle_asymmetry_{stem}.png"),
                two_theta_range=(6.0, 20.0))


@pytest.fixture(scope="module")
def arms():
    out = {"positive": _fit(_truth(ASYMMETRY)), "null": _fit(_truth(0.0))}
    out["above"] = _fit(_truth(ASYMMETRY), limits=(12.0, 130.0))
    nuc = rx.Refinement(rx.Structure(phases=[G.nuclear_phase()]), G.instrument())
    out["paramagnetic"] = (nuc, nuc.fit(G.pattern("paramagnetic"), plan=rx.RefinementPlan(
        stages=[rx.Stage("nuclear", ["phases.*.scale", "instrument.background.c*"])])))
    for stem in ("positive", "null"):
        _draw(out[stem][1], stem)
    return out


def _findings(res):
    return [d for d in res.diagnostics if d.code == CODE]


def test_an_asymmetry_the_model_lacks_shows_as_a_negative_shift_at_the_magnetic_line(arms):
    ref, res = arms["positive"]
    pos, frac, shift, esd = _lowest(ref)
    assert pos == pytest.approx(8.9, abs=0.1) and frac == pytest.approx(1.0)
    assert shift < -3.0 * esd, (shift, esd)
    (d,) = _findings(res)
    assert d.level == "info"
    assert d.value == pytest.approx(shift)
    assert d.where == ["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"]
    assert "(0 0 1) " in d.message and "1 magnetic-only line of phase 0 does" in d.message
    assert "not determinable from this sample's nuclear lines" in d.message
    assert "held at 0" in d.message and "predicts" in d.message


def test_with_no_asymmetry_anywhere_the_geometry_still_fires_and_the_shift_is_noise(arms):
    ref, res = arms["null"]
    pos, _, shift, esd = _lowest(ref)
    assert pos == pytest.approx(8.9, abs=0.1)
    assert abs(shift) < 3.0 * esd, (shift, esd)
    (d,) = _findings(res)
    assert d.value == pytest.approx(shift)


def test_a_nuclear_lowest_line_and_a_pattern_with_no_moment_are_silent(arms):
    ref, res = arms["above"]
    pos, frac, _, _ = _lowest(ref)
    assert pos > 12.0 and frac < 0.05
    assert not _findings(res)
    assert not _findings(arms["paramagnetic"][1])
