"""A plan that frees a magnetic width keeps the closing stage by default (#1850).

Ruled on #1708 (2026-11-19), before WP-2222 turned the closing stage off by
default: **a plan whose stages free ``magnetic_lor_size`` or
``magnetic_lor_strain`` keeps the closing stage at ``CLOSING_WINDOW_TOL``**,
as ``strategy.magnetic._close`` does, and an explicit
``closing_window_tol=None`` still turns it off.  The ground is
``MAGNETIC_SIZING_FLOOR``'s audit row: a width freed from zero is drawn on
windows sized at the 0.1° floor, which is safe "behind the closing stage
only".

The claim under test is the one the ruling buys: **with the closing stage the
answer does not depend on how the plan was staged.**  The three-step preset
and a one-stage plan freeing the same globs, both as a caller builds them,
land within the ruled start-test bar of the closing-stage answer.  The bar is
0.1 plain esd (``stderr_uncorrected``), the larger of the two arms' esds, on
every row but the background: the staged start test's bar (WP-2002, the sixth
round's Q2, ruled 2026-10-21; ``tests/test_staged_start_invariance.py``
``ESD_BAR``), stated before these fits were run.

**The control can fail.**  The one-stage plan with ``closing_window_tol=None``
passed explicitly runs no closing stage and must land outside the bar.  On
``main`` before this change both default arms ran that way, and #1850's
repro put the moment 0.10 esd (preset) and 0.22 esd (one stage, the
inflated esd) from the closing-stage answer.
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.plan import CLOSING_WINDOW_TOL, PlanSpec
from rietx.strategy.staged import (
    CLOSING_STAGE_NAME,
    MAGNETIC_WIDTH_STAGE_PATHS,
    PLAN_PRESETS,
    Stage,
    frees_magnetic_width,
)
from tests.test_magnetic import LAMBDA_CW
from tests.test_magnetic_width import SIZE, _mnf2

#: the ruled bar for a staged plan's start test, in plain esd (WP-2002, the
#: sixth round's Q2, 2026-10-21); the same number as
#: ``test_staged_start_invariance.ESD_BAR``
ESD_BAR = 0.1

_WIDTH_GLOBS = sorted({g for s in MAGNETIC_WIDTH_STAGE_PATHS for g in s})


def _one_stage(**kw) -> rx.RefinementPlan:
    """Every glob the preset frees, in one stage, as a caller writes it."""
    return rx.RefinementPlan(stages=[Stage("all_at_once", list(_WIDTH_GLOBS))], **kw)


# ======================================================== the plan's default

def test_the_preset_keeps_the_closing_stage():
    plan = PLAN_PRESETS["magnetic_width"]()
    assert plan.closing_window_tol == CLOSING_WINDOW_TOL
    assert plan.run_stages()[-1].name == CLOSING_STAGE_NAME
    assert plan.stage_window_tols()[-1] == CLOSING_WINDOW_TOL


@pytest.mark.parametrize("glob", [
    "phases.*.magnetic_lor_size", "phases.*.magnetic_lor_strain",
    "phases.1.magnetic_lor_size", "phases.*.magnetic_lor_*",
    "hist.0.phases.0.magnetic_lor_strain", "phases.*"])
def test_any_glob_reaching_a_magnetic_width_keeps_it(glob):
    plan = rx.RefinementPlan(stages=[Stage("w", [glob])])
    assert frees_magnetic_width([glob])
    assert plan.closing_window_tol == CLOSING_WINDOW_TOL


@pytest.mark.parametrize("name", ["mccusker_default", "mccusker_structural",
                                  "magnetic_structural", "profile_only"])
def test_a_plan_freeing_no_magnetic_width_keeps_the_wp2222_default(name):
    plan = PLAN_PRESETS[name]()
    assert not frees_magnetic_width(g for s in plan.stages for g in s.turn_on)
    assert plan.closing_window_tol is None
    assert plan.closing_stage() is None


def test_an_explicit_none_still_turns_it_off():
    plan = _one_stage(closing_window_tol=None)
    assert plan.closing_window_tol is None
    assert plan.closing_stage() is None
    assert replace(PLAN_PRESETS["magnetic_width"](),
                   closing_window_tol=None).closing_stage() is None


def test_a_stage_added_in_place_is_read_when_the_plan_is():
    """``plan.stages.append`` is the documented way to extend a preset
    (``examples/nac_11bm.py``), so the default is read off the stages the
    plan holds when asked, never frozen when it was built."""
    plan = PLAN_PRESETS["mccusker_default"]()
    assert plan.closing_window_tol is None
    plan.stages.append(Stage("magnetic_width", ["phases.*.magnetic_lor_size"]))
    assert plan.closing_window_tol == CLOSING_WINDOW_TOL
    assert plan.run_stages()[-1].name == CLOSING_STAGE_NAME
    plan.closing_window_tol = None              # an explicit choice sticks
    plan.stages.append(Stage("again", ["phases.*.magnetic_lor_strain"]))
    assert plan.closing_window_tol is None


def test_the_mirror_carries_the_value_both_ways_and_resolves_an_omitted_one():
    plan = PLAN_PRESETS["magnetic_width"]()
    spec = PlanSpec.from_plan(plan)
    assert spec.closing_window_tol == CLOSING_WINDOW_TOL
    assert PlanSpec.model_validate_json(spec.model_dump_json()) == spec
    assert spec.to_plan() == plan
    assert spec.preset_name() == "magnetic_width"
    # an omitted value is the plan's default, read off the stages
    assert PlanSpec(stages=spec.stages).closing_window_tol == CLOSING_WINDOW_TOL
    bare = {"stages": [s.model_dump() for s in spec.stages]}
    assert PlanSpec.model_validate(bare).closing_window_tol == CLOSING_WINDOW_TOL
    # an explicit null is a value and survives JSON as itself
    off = PlanSpec(stages=spec.stages, closing_window_tol=None)
    assert PlanSpec.model_validate_json(off.model_dump_json()).closing_window_tol is None
    assert off.to_plan().closing_stage() is None
    # and a nuclear plan's default is still None
    assert PlanSpec.from_plan(PLAN_PRESETS["mccusker_default"]()).closing_window_tol is None


# ======================================================== the answer (#1850)

@lru_cache(maxsize=1)
def _data_and_instrument():
    """#1850's repro: MnF₂ drawn at magnetic size 0.30° and 4.60 μ_B, seed 1343."""
    ph = _mnf2(size=SIZE)
    ph.scale.value = 0.02
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    ins.background = rx.BackgroundChebyshev.with_terms(2)
    ins.background.coefficients[0].value = 20.0
    tt = np.arange(8.0, 140.0, 0.05)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    y = np.asarray(rx.Refinement(rx.Structure(phases=[ph]),
                                 ins.model_copy(deep=True)).predict(blank))
    rng = np.random.default_rng(1343)
    data = rx.PatternData(two_theta=tt.tolist(), intensity=(
        y + rng.normal(0.0, np.sqrt(np.maximum(y, 1.0)))).tolist())
    return data, ins


def _fit(plan: rx.RefinementPlan):
    data, ins = _data_and_instrument()
    start = _mnf2()                     # every fit starts from width 0
    start.scale.value = 0.02
    res = rx.Refinement(rx.Structure(phases=[start]), ins.model_copy(deep=True),
                        history=False).fit(data, plan=plan)
    rows = {p.path: (p.value, p.stderr_uncorrected) for p in res.parameters}
    return res, rows


@lru_cache(maxsize=1)
def _reference():
    """The closing-stage answer: the preset with the closing stage asked for."""
    return _fit(replace(PLAN_PRESETS["magnetic_width"](),
                        closing_window_tol=CLOSING_WINDOW_TOL))[1]


def _worst(rows, ref):
    """Largest |Δ| over the larger of the two plain esds, background excluded."""
    worst = (0.0, None)
    for path, (value, e1) in rows.items():
        if path.startswith("instrument.background.") or path not in ref:
            continue
        v0, e0 = ref[path]
        esds = [e for e in (e0, e1) if e is not None and np.isfinite(e) and e > 0.0]
        if esds:
            worst = max(worst, (abs(value - v0) / max(esds), path), key=lambda t: t[0])
    return worst


@pytest.mark.parametrize("build", [
    pytest.param(lambda: PLAN_PRESETS["magnetic_width"](), id="preset"),
    pytest.param(_one_stage, id="one-stage")])
def test_the_answer_does_not_depend_on_how_the_plan_was_staged(build):
    res, rows = _fit(build())
    assert res.stages[-1].name == CLOSING_STAGE_NAME
    assert res.stages[-1].window_area_tol == CLOSING_WINDOW_TOL
    worst, path = _worst(rows, _reference())
    assert worst <= ESD_BAR, f"{worst:.3f} plain esd on {path} (bar {ESD_BAR})"


def test_the_bar_fails_without_the_closing_stage():
    """The control: the same one-stage plan with the closing stage declined
    lands outside the bar, so the comparison above can fail."""
    res, rows = _fit(_one_stage(closing_window_tol=None))
    assert res.stages[-1].name != CLOSING_STAGE_NAME
    worst, path = _worst(rows, _reference())
    assert worst > ESD_BAR, f"{worst:.3f} plain esd on {path}: the control did not fail"
