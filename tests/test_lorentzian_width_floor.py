"""Γ_L ≥ 0 held by LM, with Y free to go negative (WP-2002, 2026-10-23).

Y lost its floor of 0 on the maintainer's ruling of 2026-10-23: what must stay
non-negative is the Lorentzian width Γ_L = X/cosθ + Y·tanθ, not Y.  LM holds
it at every reflection of the frozen list, those just past the data included
(the joint runner too since the 9th session), as a linear inequality inside
the step (``least_squares.lorentzian_width_inequalities``), the twin of the
Γ_G² rows ``test_gaussian_width_floor.py`` tests.  TRF holds no inequality,
and ``RESOLUTION_NOT_POSITIVE`` reports the instrument's Γ_L going negative.

Two synthetic LaB₆ patterns at 11-BM's wavelength.  One is drawn with
x = 0.02°, y = −0.03°, whose width stays positive over the range: LM finds the
negative Y the old floor forbade.  The other is drawn with a narrow Gaussian
and fitted with U held at 0.05 deg², too broad at high angle, so the fit
wants a negative Lorentzian width at the top of the range.

obs/calc/diff PNGs of the LM fits go to ``tests/output/``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
import rietx.optimize.least_squares as ls
from rietx import Instrument, PatternData, Refinement
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import TCHZ_BOUNDS, BackgroundChebyshev
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"
WAVELENGTH = 0.4139
TOP = 24.0
_B = ["phases.0.scale", "instrument.background.*"]


def _models(profile: dict, *, true: bool):
    structure = make_lab6()
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    for name, value in profile.items():
        getattr(ins.profile, name).value = value
    if true:
        ins.background = BackgroundChebyshev(coefficients=[Parameter(value=40.0)])
    else:
        ins.background = BackgroundChebyshev.with_terms(1)
    return structure, ins


def _pattern(profile: dict) -> PatternData:
    structure, ins = _models(profile, true=True)
    tt = np.arange(3.0, TOP, 0.005)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _fit(pattern, start: dict, free: str, solver: str = "lm"):
    structure, ins = _models(start, true=False)
    plan = rx.RefinementPlan(stages=[
        rx.Stage(name="scale", turn_on=_B),
        rx.Stage(name="profile",
                 turn_on=_B + [f"instrument.profile.{n}" for n in free])])
    ref = Refinement(structure, ins, solver=solver, history=False)
    return ref, ref.fit(pattern, plan=plan)


def _gamma_l(ref, result, *, past_data: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """2θ and the instrument Γ_L at every tick inside the measured range, or at
    every tick the result carries with ``past_data``."""
    p = ref.instrument.profile
    tt = np.asarray([x for ticks in result.ticks.values() for x in ticks])
    if not past_data:
        tt = tt[tt <= max(result.two_theta)]
    th = np.radians(0.5 * tt)
    return tt, p.x.value / np.cos(th) + p.y.value * np.tan(th)


def _draw(result, stem: str) -> None:
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{stem}.png"))
    plot_result(result, path=str(OUT / f"{stem}_zoom.png"), two_theta_range=(21.0, 24.0))


def test_y_has_no_floor_of_its_own():
    assert TCHZ_BOUNDS["y"][0] < 0.0 <= TCHZ_BOUNDS["x"][0]


def test_lm_finds_a_negative_y_that_x_carries():
    """Drawn at x = 0.02°, y = −0.03°: Γ_L stays above 0.0139° over the
    range, so no row binds.  LM lands 1.1 % from the drawn Y (Poisson noise)."""
    pattern = _pattern({"w": 2.5e-5, "x": 0.02, "y": -0.03})
    ref, result = _fit(pattern, {"w": 2.5e-5}, "wxy")
    _draw(result, "lorentzian_width_negative_y_lm")
    p = ref.instrument.profile
    assert p.y.value == pytest.approx(-0.03, rel=3e-2)
    assert p.x.value == pytest.approx(0.02, rel=3e-2)
    _, gamma_l = _gamma_l(ref, result)
    assert np.all(gamma_l > 0.0)
    assert not any(d.code == "CONSTRAINT_ACTIVE" for d in result.diagnostics)


@pytest.fixture(scope="module")
def too_broad():
    """Drawn with Γ_G = 0.01° and Γ_L = 0.03/cosθ − 0.12·tanθ; fitted with
    U held at 0.05 deg², which broadens the top of the range by 0.05°."""
    pattern = _pattern({"w": 1e-4, "x": 0.03, "y": -0.12})
    return pattern, {"u": 0.05, "w": 1e-4, "x": 0.03, "y": -0.12}


def test_without_the_rows_the_fit_wants_a_negative_width(too_broad, monkeypatch):
    """The trap the rows exist for: it must be reachable, or the test below
    proves nothing."""
    pattern, start = too_broad
    monkeypatch.setattr(ls, "lorentzian_width_inequalities", lambda m, t, x: [])
    ref, result = _fit(pattern, start, "xy")
    tt, gamma_l = _gamma_l(ref, result)
    assert gamma_l[np.argmax(tt)] < -1e-3


def test_lm_holds_the_lorentzian_width_at_zero_at_the_high_angle_end(too_broad):
    pattern, start = too_broad
    ref, result = _fit(pattern, start, "xy")
    _draw(result, "lorentzian_width_rows_lm")
    tt, gamma_l = _gamma_l(ref, result, past_data=True)
    scale = float(np.max(np.abs(gamma_l)))
    assert np.all(gamma_l >= -1e-9 * scale)
    # the row carried load: the highest listed reflection, past the data's end,
    # sits on its face, and the data's own last reflections stay above it
    assert gamma_l[np.argmax(tt)] == pytest.approx(0.0, abs=1e-9 * scale)
    assert np.max(tt) > max(result.two_theta)
    assert ref.instrument.profile.y.value < 0.0
    assert any(d.code == "CONSTRAINT_ACTIVE" for d in result.diagnostics)


def test_trf_reports_the_negative_width_it_cannot_hold(too_broad):
    """TRF holds no inequality, so the guard names the Lorentzian width."""
    pattern, start = too_broad
    ref, result = _fit(pattern, start, "xy", solver="trf")
    _, gamma_l = _gamma_l(ref, result)
    assert gamma_l.min() < 0.0
    found = [d for d in result.diagnostics if d.code == "RESOLUTION_NOT_POSITIVE"]
    assert [d.where for d in found] == [["instrument.profile.x", "instrument.profile.y"]]
    assert "Lorentzian" in found[0].message
    assert found[0].value < 0.0


def _joint_gamma_l(pattern, start: dict) -> list[np.ndarray]:
    """Each histogram's instrument Γ_L over the measured range, after a joint
    fit of ``pattern`` twice that frees each histogram's X and Y."""
    from rietx.multi import MultiHistogramRefinement

    structure, ins = _models(start, true=False)
    ref = MultiHistogramRefinement(structure, [ins, ins.model_copy(deep=True)])
    ref.fit([pattern, pattern], plan=rx.RefinementPlan(stages=[
        rx.Stage(name="scale", turn_on=_B),
        rx.Stage(name="profile", turn_on=_B + ["instrument.profile.x",
                                               "instrument.profile.y"])]))
    th = np.radians(0.5 * np.asarray(pattern.two_theta))
    return [p.profile.x.value / np.cos(th) + p.profile.y.value * np.tan(th)
            for p in ref.fitted_instruments]


def test_the_joint_runner_holds_the_lorentzian_width_too(too_broad, monkeypatch):
    """The joint LM runner built no width rows, and the per-coefficient floor
    was what kept Γ_L ≥ 0 there (code review of WP-2002's 9th session).
    Without the rows the joint fit takes each histogram's Γ_L negative at the
    top of the range; with them neither goes below zero."""
    pattern, start = too_broad
    with monkeypatch.context() as m:
        m.setattr(ls, "_joint_width_inequalities", lambda models, mtable, x0: [])
        unheld = _joint_gamma_l(pattern, start)
    assert all(g.min() < 0.0 for g in unheld)
    for g in _joint_gamma_l(pattern, start):
        assert g.min() >= -1e-9 * np.max(np.abs(g))


def _rows_from(pattern, x: float, y: float):
    structure, ins = _models({"w": 1e-4, "x": x, "y": y}, true=False)
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(["instrument.profile.x", "instrument.profile.y"], True)
    return ls.lorentzian_width_inequalities(model, table, table.x0()), table.x0()


def test_a_start_left_on_every_rows_face_keeps_its_rows(too_broad):
    """X on its floor and Y followed to 0 put every row on its face, and a
    stage that ended there handed the next one no row, which then walked Y to
    −0.0137 with Γ_L negative everywhere: on the planted cooling ramp, 40
    warm-started patterns at Rwp 0.433 against 0.042 (WP-2003, X16).  A start
    violating its rows by more than rounding still builds none."""
    pattern, _ = too_broad
    (clear,), _ = _rows_from(pattern, 0.002, 0.0)
    (block,), x0 = _rows_from(pattern, 4e-22, -4e-21)
    assert (block.slack(x0) < 0.0).any()
    assert block.T.shape == clear.T.shape
    assert _rows_from(pattern, 0.0, -0.0137)[0] == []
