"""Sequential (in-situ / parametric) refinement of a series — WP-0505.

Two synthetic series carry these tests, both built from the LaB6 model that
``test_refine_synthetic`` uses:

``thermal_series``
    a clean linear cell expansion — the only place where the *true* trajectory
    is known, so it is where the trajectory machinery is actually validated.
``jump_series``
    a nearly flat series with one step far larger than its own scatter, which
    is what the discontinuity fence exists to find.

The chain's fences (reseed, discontinuity, path dependence) never alter a
fitted value, so every test here asserts on the reported diagnostics and on
values that were fitted independently of them.
"""

import json

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.instrument import BackgroundChebyshev
from pxrdref.schemas.results import RefinedParameter, Statistics
from pxrdref.schemas.sequential import SeriesEntry, SeriesResult
from pxrdref.sequential import (
    SequentialRefinement,
    _better,
    _carry_into,
    _collapse,
    _discontinuity_diagnostics,
    _labels_for,
    _path_dependence_diagnostics,
    _reseed_needed,
    refine_sequential,
)
from tests.test_schemas import make_lab6

WAVELENGTH = 0.4139
A0 = 4.15660
TRUE_ZERO = 0.008
TRUE_W = 2.5e-4
TRUE_SCALE = 5e-4
TRUE_BKG = [40.0, -6.0, 1.5]

#: fractional cell expansion per step of the thermal series.  0.05 % shifts a
#: 20° peak by ~0.01°, comparable with the ~0.016° FWHM here, so successive
#: patterns are within each other's capture range — a series a warm start can
#: legitimately walk.
RAMP = 5e-4
#: temperatures the ramp is labelled with (the series coordinate)
TEMPERATURES = [300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0]


def _simulate(a: float, *, seed: int, biso: float = 0.4) -> pr.PatternData:
    """One pattern of the series at cell edge ``a``, with Poisson noise."""
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = a
    for atom in structure.phases[0].atoms:
        atom.biso.value = biso
    structure.phases[0].scale.value = TRUE_SCALE
    ins = pr.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in TRUE_BKG])

    tt = np.arange(3.0, 24.0, 0.005)
    blank = pr.PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return pr.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _start_models():
    """The starting model: cell 0.1 % off, no zero shift, flat background."""
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = A0 * 1.001
    structure.phases[0].scale.value = TRUE_SCALE * 1.5
    ins = pr.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = 0.0
    ins.profile.w.value = TRUE_W * 1.5
    ins.background = BackgroundChebyshev.with_terms(3)
    return structure, ins


@pytest.fixture(scope="module")
def thermal_patterns():
    """A 7-pattern ramp: a expands linearly by RAMP per step."""
    return [_simulate(A0 * (1.0 + RAMP * k), seed=11 + k)
            for k in range(len(TEMPERATURES))]


@pytest.fixture(scope="module")
def thermal_series(thermal_patterns):
    structure, ins = _start_models()
    return refine_sequential(thermal_patterns, structure, ins,
                             x=TEMPERATURES, x_label="T (K)",
                             labels=[f"{int(t)}K" for t in TEMPERATURES],
                             plan="mccusker_default")


@pytest.fixture(scope="module")
def jump_patterns():
    """Six patterns at one cell, then a step 20× the series' own scatter.

    The step (2e-3 Å) is far below the peak capture range, so *both* the warm
    and the cold fit find it easily — the discontinuity fence is about the
    trajectory, not about whether an individual fit succeeded.
    """
    flat = [_simulate(A0, seed=31 + k) for k in range(3)]
    stepped = [_simulate(A0 + 2e-3, seed=41 + k) for k in range(3)]
    return flat + stepped


# -- the trajectory: recovered against a known truth ----------------------

def test_series_recovers_the_injected_thermal_expansion(thermal_series):
    """The headline: the fitted a(T) reproduces the injected linear ramp.

    Checked as a *slope*, not point by point: the series was generated with a
    constant fractional expansion per step, and recovering that coefficient is
    what an in-situ user takes away.
    """
    assert len(thermal_series) == len(TEMPERATURES)
    assert all(e.status == "converged" for e in thermal_series)

    traj = thermal_series.trajectory("phases.0.cell.a")
    x, value, sd = traj.arrays()
    assert traj.x_label == "T (K)"
    assert np.allclose(x, TEMPERATURES)
    assert np.all(np.isfinite(sd)) and np.all(sd > 0)

    # injected: a(T) = A0·(1 + RAMP·k), one k per 100 K
    truth = A0 * (1.0 + RAMP * np.arange(len(TEMPERATURES)))
    assert np.allclose(value, truth, atol=max(5 * float(sd.max()), 1e-4))

    slope = np.polyfit(x, value, 1)[0]
    expected = A0 * RAMP / 100.0          # Å per K
    assert slope == pytest.approx(expected, rel=0.05)


def test_tied_cell_edges_travel_with_the_series(thermal_series):
    """Cubic b, c are tied to a, so they must appear in every trajectory."""
    a = thermal_series.trajectory("phases.0.cell.a")
    for name in ("b", "c"):
        other = thermal_series.trajectory(f"phases.0.cell.{name}")
        assert len(other) == len(a)
        assert np.allclose(other.arrays()[1], a.arrays()[1])
    # ... and `paths()` keeps them: tied is not the same as undetermined
    assert "phases.0.cell.b" in thermal_series.paths()
    assert "phases.0.cell.b" not in thermal_series.paths(varied_only=True)


def test_series_axis_defaults_to_the_pattern_index(thermal_patterns):
    """No coordinate given ⇒ the axis is the index, and x_label says so."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:2], structure, ins)
    assert series.x_label == "index"
    assert series.x == [0.0, 1.0]
    assert series.labels == ["p000", "p001"]


def test_labels_are_made_unique():
    """Labels become history file names, so duplicates cannot be tolerated."""
    blank = [pr.PatternData(two_theta=[1.0, 2.0], intensity=[1.0, 1.0])
             for _ in range(3)]
    assert _labels_for(blank, ["a", "a", "b"]) == ["a", "a_1", "b"]
    with pytest.raises(ValueError, match="labels has 2 entries"):
        _labels_for(blank, ["a", "b"])


# -- warm-start mechanics -------------------------------------------------

def test_carry_globs_move_only_matching_paths():
    """`carry` is per-parameter, and a narrow glob must not break a tie."""
    start_s, start_i = _start_models()
    fitted_s, fitted_i = _start_models()
    for name in ("a", "b", "c"):
        getattr(fitted_s.phases[0].cell, name).value = A0 * 1.02
    fitted_i.profile.w.value = 9e-4
    fitted_i.zero_shift.value = 0.02

    _carry_into(start_s, start_i, (fitted_s, fitted_i), ["instrument.profile.*"])
    assert start_i.profile.w.value == pytest.approx(9e-4)
    assert start_i.zero_shift.value == pytest.approx(0.0)      # not carried
    assert start_s.phases[0].cell.a.value == pytest.approx(A0 * 1.001)

    # carrying only `cell.a` must still leave b and c equal to it: the cubic
    # tie is re-derived from its source rather than left at the old value
    _carry_into(start_s, start_i, (fitted_s, fitted_i), ["phases.*.cell.a"])
    cell = start_s.phases[0].cell
    assert cell.a.value == pytest.approx(A0 * 1.02)
    assert cell.b.value == pytest.approx(cell.a.value)
    assert cell.c.value == pytest.approx(cell.a.value)


def test_collapse_unions_the_plans_turn_on_globs():
    plan = pr.RefinementPlan.mccusker_structural()
    single = _collapse(plan)
    assert len(single.stages) == 1
    for stage in plan.stages:
        for glob in stage.turn_on:
            assert glob in single.stages[0].turn_on
    # seeds survive the compression, so the protocol is the same one
    assert single.stages[0].seed == max(s.seed for s in plan.stages)


def test_refit_single_agrees_with_refit_stages(thermal_patterns):
    """The compressed refit reaches the same cell — it is a speed knob, not a
    different protocol.  The iteration counts are reported, never asserted:
    which one is cheaper is a measurement (see the WP acceptance)."""
    patterns = thermal_patterns[:4]
    staged = refine_sequential(*(patterns, *_start_models()), refit="stages")
    single = refine_sequential(*(patterns, *_start_models()), refit="single")

    a_staged = np.asarray(staged.trajectory("phases.0.cell.a").value)
    a_single = np.asarray(single.trajectory("phases.0.cell.a").value)
    sd = np.nanmax(staged.trajectory("phases.0.cell.a").arrays()[2])
    assert np.allclose(a_staged, a_single, atol=5 * sd)
    print(f"\niterations: stages={staged.n_iterations} single={single.n_iterations}")


# -- the reseed fence -----------------------------------------------------

def test_reseed_decision_uses_the_median_not_the_previous():
    """One bad pattern must not ratchet the threshold and let its successors
    through, which is exactly what comparing against the previous Rwp would do."""
    good = _fake_result(0.10)
    assert not _reseed_needed(good, [], 1.25)
    assert not _reseed_needed(good, [0.09, 0.10, 0.11], 1.25)
    assert _reseed_needed(_fake_result(0.30), [0.09, 0.10, 0.11], 1.25)
    # a single outlier already accepted does not move a median
    assert _reseed_needed(_fake_result(0.30), [0.09, 0.10, 0.11, 0.90], 1.25)
    # divergence always reseeds, whatever the Rwp
    assert _reseed_needed(_fake_result(0.01, status="diverged"), [0.10], 1.25)


def test_better_prefers_convergence_then_rwp():
    assert _better(_fake_result(0.10), _fake_result(0.20))
    assert not _better(_fake_result(0.20), _fake_result(0.10))
    # a converged fit beats a diverged one even at a worse Rwp
    assert _better(_fake_result(0.30), _fake_result(0.05, status="diverged"))


def test_reseed_records_both_fits_and_emits_a_diagnostic(thermal_patterns):
    """End-to-end through the reseed branch, forced by a threshold no fit can
    clear (any Rwp above the running median triggers it).  What is asserted is
    the *bookkeeping*: the kept fit is the better one, the rejected warm Rwp is
    still reported, and the iterations of both count against the series."""
    structure, ins = _start_models()
    series = SequentialRefinement(structure, ins).fit(
        thermal_patterns[:3], reseed_factor=1.0)
    assert len(series) == 3
    for entry in series:
        if entry.reseeded:
            assert entry.rwp_warm is not None
            assert entry.statistics.rwp <= entry.rwp_warm
    reseeded = [e for e in series if e.reseeded]
    codes = [d.code for d in series.diagnostics]
    assert codes.count("SEQUENTIAL_RESEED") == len(reseeded)
    if reseeded:
        assert all("did not come from its neighbour" in d.suggestion
                   for d in series.diagnostics if d.code == "SEQUENTIAL_RESEED")


def test_a_well_behaved_series_reseeds_nothing(thermal_series):
    assert not any(e.reseeded for e in thermal_series)
    assert "SEQUENTIAL_RESEED" not in [d.code for d in thermal_series.diagnostics]


# -- the discontinuity fence ---------------------------------------------

def test_discontinuity_is_flagged_and_the_value_is_left_alone(jump_patterns):
    structure, ins = _start_models()
    series = refine_sequential(jump_patterns, structure, ins)
    jumps = [d for d in series.diagnostics
             if d.code == "SEQUENTIAL_DISCONTINUITY"
             and d.where == ["phases.0.cell.a"]]
    assert len(jumps) == 1
    assert "either the specimen genuinely changed" in jumps[0].suggestion

    # nothing was smoothed: the fitted step is still the injected one
    value = np.asarray(series.trajectory("phases.0.cell.a").value)
    assert value[3] - value[2] == pytest.approx(2e-3, abs=3e-4)


def _synthetic_series(path: str, values, stderr) -> SeriesResult:
    return SeriesResult(entries=[
        SeriesEntry(index=k, label=f"p{k}", parameters=[
            RefinedParameter(path=path, value=v, stderr=s)])
        for k, (v, s) in enumerate(zip(values, stderr, strict=True))])


def test_an_inert_parameter_cannot_carry_a_discontinuity():
    """Regression for a measured false positive, and for why the σ test alone
    cannot catch it: a softplus coefficient dying on its floor has dp/du → 0,
    so its esd collapses *with* its value and every step is formally
    astronomically significant.  ``instrument.profile.y`` on the synthetic ramp
    came back with a median step of 4e-16, one step of 1.3e-11 and σ ≈ 4e-55."""
    inert = _synthetic_series(
        "instrument.profile.y",
        [1e-16, 2e-16, 1.3e-11, 1.4e-11, 1.5e-11, 1.6e-11],
        [4e-55] * 6)
    assert _discontinuity_diagnostics(inert) == []

    # the same shape at a physical magnitude is still reported
    real = _synthetic_series(
        "phases.0.cell.a",
        [4.1566, 4.15661, 4.15962, 4.15963, 4.15964, 4.15965],
        [1e-5] * 6)
    assert [d.code for d in _discontinuity_diagnostics(real)] == [
        "SEQUENTIAL_DISCONTINUITY"]


def test_path_dependence_ignores_numerically_identical_chains():
    """Two chains agreeing to 1e-60 are agreeing, whatever the σ ratio says."""
    forward = _synthetic_series("instrument.profile.y",
                                [2.2e-74, 1e-60, 1e-60], [1e-70] * 3)
    backward = _synthetic_series("instrument.profile.y",
                                 [2.1e-60, 1e-60, 1e-60], [1e-70] * 3)
    assert _path_dependence_diagnostics(forward, backward) == []

    moved = _synthetic_series("phases.0.cell.a", [4.1566, 4.1570, 4.1574],
                              [1e-5] * 3)
    shifted = _synthetic_series("phases.0.cell.a", [4.1576, 4.1570, 4.1574],
                                [1e-5] * 3)
    assert [d.code for d in _path_dependence_diagnostics(moved, shifted)] == [
        "SEQUENTIAL_PATH_DEPENDENT"]


def test_a_uniform_ramp_is_not_a_discontinuity(thermal_series):
    """A steady trend has every step at the median step, so the robust test
    passes it — which is the point of measuring against the series' own scatter
    rather than against the esds (in a real ramp every step is many σ)."""
    assert "SEQUENTIAL_DISCONTINUITY" not in [d.code
                                              for d in thermal_series.diagnostics]


# -- the path-dependence fence -------------------------------------------

@pytest.mark.slow
def test_forward_and_backward_chains_agree_on_a_clean_series(thermal_patterns):
    """Each pattern of a well-conditioned series reaches its own minimum
    whichever neighbour it started from, so no parameter is path-dependent."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:5], structure, ins,
                               direction="both")
    assert series.direction == "both"
    assert [d.code for d in series.diagnostics
            if d.code == "SEQUENTIAL_PATH_DEPENDENT"] == []
    # the backward chain is kept, and reported in series order
    assert [e.index for e in series.entries] == [0, 1, 2, 3, 4]


# -- reporting surfaces ---------------------------------------------------

def test_series_result_json_round_trip(thermal_series):
    text = thermal_series.model_dump_json()
    back = SeriesResult.model_validate(json.loads(text))
    assert len(back) == len(thermal_series)
    assert back.x_label == thermal_series.x_label
    assert back.labels == thermal_series.labels
    assert (back.trajectory("phases.0.cell.a").value
            == thermal_series.trajectory("phases.0.cell.a").value)
    # summaries, not curves: a series must never carry N patterns of y_obs
    assert "y_obs" not in text


def test_write_csv(thermal_series, tmp_path):
    out = tmp_path / "series.csv"
    thermal_series.write_csv(out, paths=["phases.0.cell.a"])
    lines = out.read_text().strip().splitlines()
    assert lines[0].split(",") == ["index", "label", "T (K)", "status", "rwp",
                                   "gof", "phases.0.cell.a",
                                   "phases.0.cell.a_esd"]
    assert len(lines) == len(thermal_series) + 1
    assert lines[1].split(",")[1] == "300K"


def test_plot_trajectory_writes_a_png(thermal_series, tmp_path):
    import matplotlib.pyplot as plt

    out = tmp_path / "trajectory.png"
    thermal_series.plot(["phases.0.cell.a", "instrument.profile.w"], path=out)
    plt.close("all")
    assert out.exists() and out.stat().st_size > 5_000


def test_qpa_trajectory(thermal_series):
    traj = thermal_series.qpa_trajectory("LaB6")
    assert len(traj) == len(thermal_series)
    # single phase ⇒ 100 wt % at every point
    assert np.allclose(traj.arrays()[1], 100.0)


# -- history --------------------------------------------------------------

def test_one_tree_per_pattern_cross_linked(thermal_patterns, tmp_path):
    """A tree is pinned to one pattern by its data fingerprint, so the series
    is N trees; the chain is recorded as notes on each root node."""
    structure, ins = _start_models()
    series = SequentialRefinement(structure, ins, history=tmp_path / "hist")
    series.fit(thermal_patterns[:3], labels=["t0", "t1", "t2"])

    for name in ("t0", "t1", "t2"):
        assert (tmp_path / "hist" / f"{name}.jsonl").exists()
    trees = series.trees_
    assert len({t.header.tree_id for t in trees}) == 3       # distinct patterns

    roots = [t.root for t in trees]
    assert "series_warm_start_node" not in roots[0].notes    # the cold start
    for k in (1, 2):
        assert roots[k].notes["series_position"] == str(k)
        assert roots[k].notes["series_warm_start_tree"] == trees[k - 1].header.tree_id
        assert roots[k].notes["series_warm_start_node"] is not None

    # each entry points at its own tree, and a reloaded log agrees
    reloaded = pr.RefinementTree.load(tmp_path / "hist" / "t1.jsonl")
    assert reloaded.header.tree_id == series.result_[1].tree_id
    assert reloaded.root.notes["series_label"] == "t1"


# -- Le Bail --------------------------------------------------------------

@pytest.mark.slow
def test_lebail_series_carries_extracted_intensities(thermal_patterns):
    """Le Bail intensities are path-dependent state outside θ; a series must
    carry them pattern to pattern rather than re-seeding flat every time."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:3], structure, ins,
                               mode="lebail")
    assert series.mode == "lebail"
    assert all(e.status == "converged" for e in series)
    assert all(e.qpa is None for e in series)      # Le Bail scales are degenerate

    a = np.asarray(series.trajectory("phases.0.cell.a").value)
    truth = A0 * (1.0 + RAMP * np.arange(3))
    assert np.allclose(a, truth, atol=2e-4)


# -- argument validation --------------------------------------------------

def test_argument_validation(thermal_patterns):
    structure, ins = _start_models()
    seq = SequentialRefinement(structure, ins)
    with pytest.raises(ValueError, match="at least one pattern"):
        seq.fit([])
    with pytest.raises(ValueError, match="refit must be"):
        seq.fit(thermal_patterns[:1], refit="nope")
    with pytest.raises(ValueError, match="direction must be"):
        seq.fit(thermal_patterns[:1], direction="sideways")
    with pytest.raises(ValueError, match="x has 2 entries"):
        seq.fit(thermal_patterns[:1], x=[1.0, 2.0])
    with pytest.raises(ValueError, match="unknown plan preset"):
        seq.fit(thermal_patterns[:1], plan="does_not_exist")


def _fake_result(rwp: float, *, status: str = "converged"):
    """A minimal RefinementResult standing in for a fit, for the guard units."""
    from pxrdref.schemas.common import Provenance
    from pxrdref.schemas.results import RefinementResult

    return RefinementResult(
        status=status, mode="rietveld", parameters=[],
        statistics=Statistics(rwp=rwp, rp=rwp, rexp=0.05, chi2=1.0, gof=1.0,
                              n_points=10, n_free_parameters=1),
        provenance=Provenance(package_version="test"))


def test_series_entry_lookup_helpers():
    entry = SeriesEntry(index=0, parameters=[
        RefinedParameter(path="phases.0.cell.a", value=4.0, stderr=1e-4)])
    assert entry.value("phases.0.cell.a") == 4.0
    assert entry.stderr("phases.0.cell.a") == pytest.approx(1e-4)
    assert entry.value("nope") is None and entry.stderr("nope") is None
