"""What a report costs, and that cutting it moved no number (WP-1335).

Each saving here claims bit-identity with the code it replaced, so each test
holds the new path against the old one, kept here as the oracle where the old
one no longer exists in the package."""

import sys

import numpy as np
import pytest

import rietx.refine  # noqa: F401  (the module, which ``rietx.refine`` shadows)
from rietx import Instrument, PatternData, Refinement, RefinementPlan, Stage, Structure
from rietx.crystallography import satellites as crystal_satellites
from rietx.crystallography import stephens
from rietx.crystallography.symmetry import (
    get_spacegroup,
    reflection_orbits,
    rotation_matrices,
)
from rietx.history.aggregate import _summarize_run
from rietx.model.forward import compile_model
from rietx.model.preferred_orientation import (
    cos2_alpha,
    march_term,
    orbit_layout,
)
from rietx.optimize import lapack
from rietx.params.vector import ParameterTable
from rietx.report import strain as strain_mod
from rietx.report import texture as texture_mod
from tests.test_stephens import brucite

refine_mod = sys.modules["rietx.refine"]


def _brucite_model(lo: float, hi: float):
    """A brucite pattern drawn by the model itself over [lo, hi), plus noise."""
    structure = Structure(phases=[brucite()])
    structure.phases[0].scale.value = 3e-2
    inst = Instrument.debye_scherrer(wavelength=1.5406)
    inst.profile.w.value = 3e-3
    grid = np.arange(lo, hi, 0.02)
    blank = PatternData(two_theta=grid.tolist(), intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(structure, inst)
    values = table.decode(table.x0())
    y = compile_model(structure, inst, blank, mode="rietveld").evaluate(values) + 40.0
    rng = np.random.default_rng(5)
    data = PatternData(two_theta=grid.tolist(),
                       intensity=(rng.poisson(y * 20.0) / 20.0).tolist(),
                       sigma=np.sqrt(y / 20.0).tolist())
    return compile_model(structure, inst, data, mode="rietveld"), values


def _counting_lstsq(monkeypatch) -> list[tuple[int, int]]:
    shapes: list[tuple[int, int]] = []
    real = lapack.lstsq

    def counted(a, b, rcond=None):
        shapes.append(np.shape(a))
        return real(a, b, rcond=rcond)

    monkeypatch.setattr(lapack, "lstsq", counted)
    return shapes


def _live_count(model, values, weight) -> int:
    """``analyse_strain``'s own count, for the unguarded oracle."""
    _d, _g, _l, tan_theta, _c = strain_mod._components(model, values, 0)
    live = (np.sqrt(weight) > 1e-6 * max(float(np.sqrt(weight.max(initial=0.0))),
                                         1e-300)) \
        & np.isfinite(tan_theta[0]) & (tan_theta[0] > 0.0)
    return int(live.sum())


def test_a_phase_below_the_reflection_floor_costs_no_solve(monkeypatch):
    model, values = _brucite_model(15.0, 36.0)
    old_weight = strain_mod._strain_errors(model, values, 0)[1]
    shapes = _counting_lstsq(monkeypatch)
    (row,) = strain_mod.analyse_strain(model, values)
    assert shapes == []
    assert row.r2 == 0.0
    assert not row.detected
    # the count it records is the one the four-step path recorded
    assert row.n_reflections_used == _live_count(model, values, old_weight) < 6


def test_a_phase_above_the_floor_still_takes_every_gauss_newton_step(monkeypatch):
    model, values = _brucite_model(15.0, 120.0)
    shapes = _counting_lstsq(monkeypatch)
    strain_mod.analyse_strain(model, values)
    solves = [s for s in shapes if s[0] == len(model.tt)]
    assert len(solves) == strain_mod._GAUSS_NEWTON_ITERATIONS


def test_the_guard_changes_no_answer_above_the_floor():
    model, values = _brucite_model(15.0, 120.0)
    plain = strain_mod._strain_errors(model, values, 0)
    guarded = strain_mod._strain_errors(model, values, 0, min_reflections=6)
    assert all(np.array_equal(a, b) for a, b in zip(plain, guarded, strict=True))


def _score_axis_loop(f, w, cos2, seg, counts):
    """The one-r-at-a-time loop ``_score_axis`` replaced: the oracle."""
    W = float(w.sum())
    if W <= 0.0:
        return 1.0, 0.0
    fbar = float((w * f).sum() / W)
    base_ss = float((w * (f - fbar) ** 2).sum())
    if base_ss <= 0.0:
        return 1.0, 0.0
    best_r, best_ss = 1.0, base_ss
    for r in texture_mod._R_GRID:
        term = march_term(cos2, r)
        p = np.bincount(seg, weights=term, minlength=len(counts)) / counts
        denom = float((w * p * p).sum())
        if denom <= 0.0:
            continue
        s = float((w * f * p).sum() / denom)
        if s <= 0.0:
            continue
        ss = float((w * (f - s * p) ** 2).sum())
        if ss < best_ss:
            best_ss, best_r = ss, float(r)
    return best_r, 1.0 - best_ss / base_ss


@pytest.mark.parametrize("symbol", ["P -3 m 1", "I 21 3", "P 1 21/c 1"])
@pytest.mark.parametrize("block", [None, 7])
def test_the_blocked_texture_grid_scores_bit_identically(symbol, block, monkeypatch):
    if block is not None:
        # a block smaller than the grid, so the seams between blocks are tested
        monkeypatch.setattr(texture_mod, "_BLOCK_ELEMENTS", block)
    rng = np.random.default_rng(11)
    hkl = rng.integers(-5, 6, size=(60, 3))
    hkl = hkl[np.any(hkl != 0, axis=1)]
    members, seg, counts = orbit_layout(reflection_orbits(get_spacegroup(symbol), hkl))
    n = len(counts)
    f = 1.0 + 0.3 * rng.standard_normal(n)
    w = rng.random(n)
    gstar = np.diag([0.1, 0.1, 0.05])
    for axis in [(0, 0, 1), (1, 1, 0), (1, 2, 1)]:
        cos2 = cos2_alpha(members, np.array(axis), gstar)
        assert (texture_mod._score_axis(f, w, cos2, seg, counts)
                == _score_axis_loop(f, w, cos2, seg, counts))


def test_the_strain_basis_is_computed_once_and_handed_out_as_a_copy():
    rots = rotation_matrices(get_spacegroup("P 1 21/c 1"))
    first = stephens.strain_basis(rots)
    first[0, 0] += 99
    again = stephens.strain_basis(rots)
    assert not np.array_equal(first, again)
    stephens._BASIS_CACHE.clear()
    assert np.array_equal(stephens.strain_basis(rots), again)


def test_the_zone_boundary_candidates_are_one_tuple_per_group():
    first = crystal_satellites.zone_boundary_candidates("F m -3 m")
    assert crystal_satellites.zone_boundary_candidates(get_spacegroup("F m -3 m")) is first
    crystal_satellites._ZONE_BOUNDARY_CACHE.clear()
    assert crystal_satellites.zone_boundary_candidates("F m -3 m") == first


def _fit(stage_reports: bool, events: list[dict]):
    model, values = _brucite_model(15.0, 80.0)
    structure = Structure(phases=[brucite()])
    structure.phases[0].scale.value = 2e-2
    inst = Instrument.debye_scherrer(wavelength=1.5406)
    inst.profile.w.value = 3e-3
    data = PatternData(two_theta=model.tt.tolist(), intensity=model.y_obs.tolist(),
                       sigma=model.sigma.tolist())
    ref = Refinement(structure, inst, history=False)
    ref.fit(data, plan=RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("cell", ["phases.*.cell.*"]),
    ]), stage_reports=stage_reports, events=lambda e: events.append(e))
    return ref


def test_fit_end_carries_the_rungs_cost_and_the_summary_counts_it():
    events: list[dict] = []
    ref = _fit(True, events)
    (end,) = [e for e in events if e["kind"] == "fit_end"]
    spent = end["data"]["stage_report_seconds"]
    assert spent > 0.0 and len(ref.stage_reports_) == 3
    summary = _summarize_run(None, events)
    assert summary.stage_report_seconds == spent
    assert "stage reports" in str(summary)


def test_a_fit_without_rungs_carries_no_cost_field():
    events: list[dict] = []
    _fit(False, events)
    (end,) = [e for e in events if e["kind"] == "fit_end"]
    assert "stage_report_seconds" not in end["data"]
    summary = _summarize_run(None, events)
    assert summary.stage_report_seconds is None
    assert "stage reports" not in str(summary)


def test_a_rung_built_without_the_geometry_search_is_the_same_rung(monkeypatch):
    """The rung's result skips the bond search, which no ``StageReport`` field
    reads; built with it, every rung is byte-for-byte the same."""
    lean = [r.model_dump_json() for r in _fit(True, []).stage_reports_]
    real = refine_mod._build_result

    def with_geometry(*args, **kwargs):
        kwargs["with_geometry"] = True
        return real(*args, **kwargs)

    monkeypatch.setattr(refine_mod, "_build_result", with_geometry)
    full = [r.model_dump_json() for r in _fit(True, []).stage_reports_]
    assert lean == full
