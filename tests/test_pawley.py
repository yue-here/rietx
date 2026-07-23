"""Pawley mode: per-hkl intensities refined as parameters (Pawley, 1981).

Two structures on purpose:
* synchrotron LaB6 (λ = 0.4139, 3–24°) — clean, well-separated peaks; Pawley
  and Le Bail must agree on the cell within esds and reach comparable Rwp.
* Cu-Kα LaB6 out to 110° — the cubic cell has *accidental* exact degeneracies
  (h²+k²+l² equal for distinct orbits, e.g. (221)/(300)); the split of such a
  pair is unconstrained by the data, so Pawley must recover their *summed*
  intensity while reporting the individual values as unresolved.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pxrdref import Instrument, PatternData, Refinement
from pxrdref.model.forward import compile_model
from pxrdref.optimize.least_squares import _make_jacobian, _make_residual
from pxrdref.params.vector import ParameterTable
from pxrdref.refine import replay
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.instrument import BackgroundChebyshev
from tests.test_refine_synthetic import perturbed_models, synthesize
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"

TRUE_A = 4.15660  # matches tests.test_refine_synthetic


def _save(result, name: str) -> None:
    """Write an obs/calc/diff PNG (skipped if matplotlib is unavailable)."""
    pytest.importorskip("matplotlib")
    OUT.mkdir(exist_ok=True)
    from pxrdref.viz.plots import plot_result

    plot_result(result, path=str(OUT / name))


# --------------------------------------------------------------- clean pattern
def test_pawley_matches_lebail_cell_on_clean_pattern():
    """On well-separated peaks the two whole-pattern methods must agree: same
    cell within esds, comparable Rwp.  Pawley additionally reports esds."""
    pattern = synthesize()

    s_lb, ins_lb = perturbed_models()
    lebail = Refinement(s_lb, ins_lb, history=False).fit(pattern, mode="lebail")

    s_pw, ins_pw = perturbed_models()
    ref = Refinement(s_pw, ins_pw)
    pawley = ref.fit(pattern, mode="pawley")

    assert pawley.status == "converged"
    assert pawley.mode == "pawley"
    # free intensities ⇒ Pawley fits at least as well as Le Bail
    assert pawley.statistics.rwp < 0.06
    assert pawley.statistics.rwp <= lebail.statistics.rwp * 1.2

    a_pw = ref.fitted_structure.phases[0].cell.a.value
    a_lb = lebail.parameter("phases.0.cell.a").value
    a_err = pawley.parameter("phases.0.cell.a").stderr
    assert a_err is not None and a_err > 0, "Pawley must report a cell esd"
    assert a_pw == pytest.approx(TRUE_A, abs=2e-4)
    assert a_pw == pytest.approx(a_lb, abs=max(5 * a_err, 2e-4))

    _save(pawley, "pawley_lab6_clean.png")


# ------------------------------------------------------------- overlapped pair
def _overlapped_lab6(a: float = TRUE_A, *, scale: float = 5e-4, w: float = 5e-3
                     ) -> tuple:
    s = make_lab6()
    for c in ("a", "b", "c"):
        getattr(s.phases[0].cell, c).value = a
    s.phases[0].scale.value = scale
    ins = Instrument.debye_scherrer(wavelength=1.5406)  # Cu: reach high-angle overlaps
    ins.profile.w.value = w
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (30.0, -4.0, 1.0)])
    return s, ins


def _synth_overlapped(seed: int = 3):
    """A noisy Cu-LaB6 pattern plus the *true* per-reflection intensities."""
    s, ins = _overlapped_lab6()
    tt = np.arange(15.0, 110.0, 0.03)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(s, ins, blank, mode="rietveld")
    table = ParameterTable(s, ins)
    values = table.decode(table.x0())
    y = model.evaluate(values)
    inten_true = model.phase_peaks(0, values)[0][3]
    d = model.phases[0].reflections.d
    rng = np.random.default_rng(seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    pattern = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())
    return pattern, np.asarray(inten_true), np.asarray(d)


def test_pawley_recovers_overlapped_sum_and_flags_split():
    pattern, inten_true, d_true = _synth_overlapped()
    # the (221)/(300) accidental degeneracy near 2θ = 67.5°
    d_pair = 1.3855
    true_pair = [k for k in range(len(d_true)) if abs(d_true[k] - d_pair) < 1e-3]
    true_sum = float(inten_true[true_pair].sum())
    assert len(true_pair) == 2, "expected an exact two-fold degeneracy"

    s, ins = _overlapped_lab6(a=4.160, w=1e-2)  # perturbed start
    ref = Refinement(s, ins, history=False)
    result = ref.fit(pattern, mode="pawley")
    model = ref._model

    assert result.status == "converged"
    assert result.statistics.gof < 1.3  # fitting to the noise floor

    # the pair was detected as an overlapped group
    assert model.pawley.groups, "no overlap groups detected"

    # locate the same pair in the refined model and check the *sum* is right
    d = model.phases[0].reflections.d
    idx = [k for k in range(len(d)) if abs(d[k] - d_pair) < 1e-3]
    Ivec, stderr = model.pawley_x0(), np.asarray(model.pawley.stderr)
    refined_sum = float(Ivec[idx].sum())
    assert refined_sum == pytest.approx(true_sum, rel=0.06), (
        f"summed overlapped intensity off: {refined_sum:.2f} vs {true_sum:.2f}")

    # ...while the individual split is NOT resolved: each esd is a large
    # fraction of its own value (the equal-split restraint kept it honest)
    rel = stderr[idx] / np.maximum(Ivec[idx], 1e-9)
    assert float(rel.min()) > 0.3, f"split reported too confidently (rel esd {rel})"

    # ...and it comes back flagged, naming the reflections
    flagged = [dg for dg in result.diagnostics
               if dg.code == "PAWLEY_OVERLAP_UNRESOLVED"]
    assert flagged, "overlapped split was not flagged unresolved"
    named = " ".join(w for dg in flagged for w in dg.where)
    assert "(2, 2, 1)" in named and "(3, 0, 0)" in named

    _save(result, "pawley_lab6_overlapped.png")


# --------------------------------------------------------------- history
def test_pawley_history_round_trip_restores_intensities_and_esds():
    """A Pawley node stores refined intensities *and* their esds under
    kind='pawley_refined'; replaying it reproduces the fit exactly, and the
    stored intensities are load-bearing (stripping them wrecks the fit)."""
    import copy

    pattern = synthesize()
    s, ins = perturbed_models()
    ref = Refinement(s, ins)
    result = ref.fit(pattern, mode="pawley")
    tree = ref.history

    node = tree[tree.head]
    assert node.state.mode == "pawley"
    rs = node.state.reflections
    assert rs and rs[0].kind == "pawley_refined" and rs[0].varied
    assert rs[0].stderr is not None
    assert len(rs[0].stderr) == len(rs[0].intensity) == len(rs[0].hkl)

    # replay recompiles at the node's end-of-stage values, so it can differ
    # from the as-optimised metric by the documented staleness gap (see
    # NodeMetrics) — a loose tolerance, not exact equality
    good = replay(tree, node.id, pattern)
    assert good.statistics.rwp == pytest.approx(result.statistics.rwp, rel=1e-3)

    stripped = copy.deepcopy(tree)
    stripped.nodes[node.id].state.reflections = []
    bad = replay(stripped, node.id, pattern)
    assert bad.statistics.rwp > good.statistics.rwp * 1.05, (
        "clearing the hkl→I map barely changed Rwp; the Pawley restore path "
        "is not doing anything")


# --------------------------------------------------------------- Jacobian
def test_pawley_intensity_jacobian_matches_fd():
    """The intensity block is exactly linear, so its analytic columns must
    match finite differences of the augmented residual to machine precision —
    same check style as test_jacobian, extended over the intensity tail and
    the overlap-restraint rows."""
    s, ins = _overlapped_lab6(w=8e-3)
    tt = np.arange(20.0, 90.0, 0.05)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())

    table = ParameterTable(s, ins)
    table.set_vary(["*"], False)
    for path in ("phases.0.cell.a", "instrument.background.c0",
                 "instrument.background.c1"):
        assert table.set_vary([path], True), path
    model = compile_model(s, ins, blank, mode="pawley",
                          free_paths=set(table.free_paths))
    # realistic intensities + the restraint rows must be live for the check
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    model.build_pawley_restraint()

    n_table = len(table.free_paths)
    theta = np.concatenate([table.x0(), model.pawley_x0()])
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)

    assert J.shape == (len(r0), len(theta))
    # spot-check every table column and a sample of intensity columns
    cols = list(range(n_table)) + list(range(n_table, len(theta), 3))
    for c in cols:
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        col_fd = (residual(tp) - r0) / h
        col_an = J[:, c]
        scale = np.linalg.norm(col_fd)
        if scale == 0:
            continue  # out-of-range reflection: dead column, nothing to check
        err = np.linalg.norm(col_an - col_fd) / scale
        assert err < 5e-3, f"column {c}: analytic vs FD mismatch ({err:.2e})"


# --------------------------------------------------------------- guards
def test_pawley_never_frees_structure_or_scale():
    pattern = synthesize()
    s, ins = perturbed_models()
    ref = Refinement(s, ins, history=False)
    result = ref.fit(pattern, mode="pawley")
    freed = {p for stage in result.stages for p in stage.freed}
    assert not any(p.endswith(".scale") for p in freed)
    assert not any(".atoms." in p for p in freed)
    assert not any(".source.lines." in p for p in freed)
