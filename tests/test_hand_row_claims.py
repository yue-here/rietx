"""Two hand rows' claims of invariance, pinned where WP-2017 group N measured them.

The hand rows carry no ``_audit`` row; WP-2017 group N measured each claim
(``docs/wp/2017-batch/group_n_summary.md``, 2026-11-16, workstation x86_64,
compiled tier on, one kernel thread) and pins here the two that held.

**The Le Bail/Pawley intensity seed.** ``compile_model`` starts every reflection
of a fresh compile at max(median y_obs, 1), and a recompile carries matched
reflections, so the seed reaches the first stage and every reflection that
enters later.  Seeds ×0.01, ×100 and a lognormal shape (σ 1) moved no row that
is not a background coefficient by more than 1.4e-4 plain esd on FAP, NAC and
LaB6 under ``mccusker_default()``, against a 0.1 bar; LaB6's Le Bail rows were
bit-identical at ×0.01 and ×100.  The arm wraps ``refine.compile_model`` and
counts what it rewrote, so a seed that never reached the fit fails here.

**``refine._FLAT_AXIS_TEST_DIRECTIONS``.** Which two generic directions stack
the SVD did not change the axis held or the answer on #599's case (R-3m:R,
a = 4 Å, α = 70°), single and joint: the same row held, the axis within
1.5e-6°, the moment rows within 1.8e-15 (the patterns are noise-free, so an
esd there is a rounding-scale number and the bar is absolute).  The spy on
``_flat_rotation_axis`` must see the replaced pair, or the arm measured
nothing.  On the tetragonal cousin the probe is never called (the column test
holds the azimuth), which is why it is not a case here.
"""

from __future__ import annotations

import importlib
import math

import numpy as np
import pytest

import rietx as rx

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("hand-row-claims")]

refine = importlib.import_module("rietx.refine")


def _shift(cur, ref) -> float:
    """Largest |Δ| over the larger plain esd, rows that are not background."""
    worst = 0.0
    for path, (value, e1) in cur.items():
        if path.startswith("instrument.background.") or path not in ref:
            continue
        v0, e0 = ref[path]
        esds = [e for e in (e0, e1) if e is not None and math.isfinite(e) and e > 0.0]
        if esds:
            worst = max(worst, abs(value - v0) / max(esds))
    return worst


def _seed_fit(family: str, mode: str, factor: float):
    counts = {"rewritten": 0}
    original = refine.compile_model

    def wrapped(*args, **kwargs):
        model = original(*args, **kwargs)
        if factor != 1.0 and model.mode in ("lebail", "pawley"):
            for cp in model.phases:
                if cp.hkl_intensity is not None:
                    cp.hkl_intensity = cp.hkl_intensity * factor
                    counts["rewritten"] += len(cp.hkl_intensity)
        return model

    plan = rx.RefinementPlan.mccusker_default()
    if family == "nac":
        from tests.test_acceptance_nac import LIMITS, build_nac_inputs

        data, st, ins = build_nac_inputs()
        kw = {"two_theta_limits": LIMITS}
        plan.closing_window_tol = None      # the NAC protocol's own Le Bail pass
    else:
        from tests.test_window_domain import _protocol

        data, st, ins, _plan, kw = _protocol(family)
    refine.compile_model = wrapped
    try:
        result = rx.Refinement(st, ins, history=False).fit(data, mode=mode, plan=plan, **kw)
    finally:
        refine.compile_model = original
    rows = {p.path: (p.value, p.stderr_uncorrected) for p in result.parameters}
    return rows, counts["rewritten"]


@pytest.mark.parametrize("family", ["fap", "nac", "lab6"])
@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_the_lebail_and_pawley_intensity_seed_leaves_the_answer(family, mode):
    shipped, none = _seed_fit(family, mode, 1.0)
    assert none == 0
    for factor in (0.01, 100.0):
        rows, rewritten = _seed_fit(family, mode, factor)
        assert rewritten > 0, "the seed arm never reached a compile"
        assert set(rows) == set(shipped)
        assert _shift(rows, shipped) <= 0.1, (family, mode, factor)


def _flat_fit(case: str, pair: np.ndarray):
    seen: list[np.ndarray] = []
    original, shipped = refine._flat_rotation_axis, refine._FLAT_AXIS_TEST_DIRECTIONS

    def spy(model, values, base):
        seen.append(np.array(refine._FLAT_AXIS_TEST_DIRECTIONS))
        return original(model, values, base)

    truth, start = (1.5, 2.0, 3.0), (3.0, 0.2, 0.2)
    refine._FLAT_AXIS_TEST_DIRECTIONS, refine._flat_rotation_axis = pair, spy
    try:
        if case == "joint":
            from tests.test_joint_flat_moments import _joint

            _ref, result = _joint("R -3 m:R", truth, start)
        else:
            from tests.test_magnetic import _fit, _rhombohedral

            _ref, result = _fit(_rhombohedral(truth), _rhombohedral(start))
    finally:
        refine._FLAT_AXIS_TEST_DIRECTIONS, refine._flat_rotation_axis = shipped, original
    last = result.stages[-1]
    rows = {p.path: p.value for p in result.parameters if ".moment." in p.path}
    axis = np.asarray(next(iter(last.moment_flat_axes.values())))
    return list(last.held), axis, rows, seen


def _pairs():
    shipped = np.array(refine._FLAT_AXIS_TEST_DIRECTIONS, dtype=np.float64)
    k = np.array([1.0, 2.0, 3.0]) / math.sqrt(14.0)
    a = math.radians(30.0)
    turned = np.array([refine._rotate(s, k, a) for s in shipped])
    rng = np.random.default_rng(2017)
    special = [np.asarray(v, float) / np.linalg.norm(v) for v in (
        [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [1, -1, 0], [1, 0, 1], [1, 0, -1],
        [0, 1, 1], [0, 1, -1], [1, 1, 1], [1, 1, -1], [1, -1, 1], [-1, 1, 1])]
    drawn: list[np.ndarray] = []
    while len(drawn) < 2:
        v = rng.normal(size=3)
        v /= np.linalg.norm(v)
        if all(math.degrees(math.acos(min(1.0, abs(float(v @ s))))) >= 5.0 for s in special):
            drawn.append(v)
    return shipped, {"rot30": turned, "rng": np.array(drawn)}


@pytest.mark.parametrize("case", ["single", "joint"])
def test_the_flat_axis_test_directions_leave_the_hold_and_the_answer(case):
    shipped, arms = _pairs()
    held0, axis0, rows0, seen0 = _flat_fit(case, shipped)
    assert seen0 and np.allclose(seen0[0], shipped)
    for name, pair in arms.items():
        held, axis, rows, seen = _flat_fit(case, pair)
        assert seen and all(np.allclose(s, pair) for s in seen), name
        assert held == held0, (name, held, held0)
        cos = abs(float(axis @ axis0)) / float(np.linalg.norm(axis) * np.linalg.norm(axis0))
        assert math.degrees(math.acos(min(1.0, cos))) < 1e-3, name
        assert set(rows) == set(rows0)
        assert max(abs(rows[k] - rows0[k]) for k in rows) < 1e-12, name
