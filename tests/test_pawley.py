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

from rietx import Instrument, PatternData, Refinement
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import ParameterTable
from rietx.refine import replay
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_refine_synthetic import perturbed_models, synthesize
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"

TRUE_A = 4.15660  # matches tests.test_refine_synthetic


def _save(result, name: str) -> None:
    """Write an obs/calc/diff PNG (skipped if matplotlib is unavailable)."""
    pytest.importorskip("matplotlib")
    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

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
@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_the_emission_line_columns_match_fd_under_an_intensity_model(mode):
    """The Kα2 weight and the wavelength have refined under Le Bail and Pawley
    since WP-2002 (2026-10-20), so their analytic columns beside the per-hkl
    intensities are checked the way the intensity block's are: against central
    differences of the residual, on a Cu Kα doublet with the cell held.  The
    pattern is the Rietveld model's own, since against a blank one the
    extracted intensities are zero and every line column is noise (measured
    2026-10-20: 5e-10 and 3e-7 relative here, in all three modes)."""
    s, _ = _overlapped_lab6(w=8e-3)
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 8e-3
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (30.0, -4.0, 1.0)])
    tt = np.arange(20.0, 90.0, 0.02)
    empty = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    truth = ParameterTable(s, ins)
    y = compile_model(s, ins, empty, mode="rietveld").evaluate(truth.decode(truth.x0()))
    data = PatternData(two_theta=tt.tolist(), intensity=np.asarray(y).tolist())

    table = ParameterTable(s, ins)
    table.set_vary(["*"], False)
    paths = ("instrument.source.lines.1.weight", "instrument.source.lines.0.wavelength",
             "instrument.background.c0")
    for path in paths:
        assert table.set_vary([path], True), path
    model = compile_model(s, ins, data, mode=mode,
                          moving_paths=set(table.moving_paths))
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    if mode == "pawley":
        model.build_pawley_restraint()
        theta = np.concatenate([table.x0(), model.pawley_x0()])
    else:
        theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    for c, path in enumerate(table.free_paths):
        h = 1e-7 * max(1.0, abs(theta[c]))
        tp, tm = theta.copy(), theta.copy()
        tp[c] += h
        tm[c] -= h
        col_fd = (residual(tp) - residual(tm)) / (2 * h)
        scale = np.linalg.norm(col_fd)
        assert scale > 0, f"{path}: a dead column under {mode}"
        err = np.linalg.norm(J[:, c] - col_fd) / scale
        assert err < 1e-4, f"{path} under {mode}: analytic vs FD ({err:.2e})"
    assert r0.shape[0] == J.shape[0]


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
                          moving_paths=set(table.moving_paths))
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


def test_the_sparse_pawley_normal_equations_are_the_dense_ones(monkeypatch):
    """WP-2011: above the BVLS cut a Pawley stage builds JᵀJ from a pattern
    read once off the compiled windows and the restraint.  Every nonzero of
    the intensity tail must sit inside it, or A drops a term with nothing to
    say so, and A and b must be the dense ones.  Fluorapatite out to 130° in
    Cu Kα carries several hundred intensities, past the 128-column cut."""
    from scipy import sparse

    from rietx import Structure
    from rietx.optimize import least_squares as ls_mod
    from rietx.optimize import lm
    from rietx.optimize.least_squares import (
        _pawley_normal_equations,
        _pawley_tail_pattern,
    )

    s, ins = Structure.from_cif(str(FAP_CIF)), _fap_instrument(True)
    s.phases[0].scale.value = 2e-3
    tt = np.arange(15.0, 130.0, 0.01)
    blank = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    t0 = ParameterTable(s, ins)
    y = np.random.default_rng(11).poisson(np.maximum(
        compile_model(s, ins, blank).evaluate(t0.decode(t0.x0())), 1.0))
    pattern = PatternData(two_theta=tt.tolist(), intensity=y.astype(float).tolist())
    table = ParameterTable(s, ins)
    table.set_vary(["*"], False)
    for path in ("phases.0.cell.a", "phases.0.cell.c", "instrument.profile.w",
                 "instrument.background.c0", "instrument.background.c1"):
        assert table.set_vary([path], True), path
    model = compile_model(s, ins, pattern, mode="pawley",
                          moving_paths=set(table.moving_paths))
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    model.build_pawley_restraint()
    assert model.pawley.restraint is not None

    n_table = len(table.free_paths)
    theta = np.concatenate([table.x0(), model.pawley_x0()])
    assert len(theta) > lm.BVLS_MAX_COLUMNS
    Jh = _make_jacobian(model, table)(theta)
    r = _make_residual(model, table)(theta)
    A, b = _pawley_normal_equations(model, n_table)(Jh, r)
    assert sparse.issparse(A)
    assert A[n_table:, n_table:].shape == (model.pawley.n, model.pawley.n)

    # the pattern is complete: every nonzero of the tail sits inside it
    row, indptr = _pawley_tail_pattern(model)
    inside = np.zeros((Jh.shape[0], model.pawley.n), dtype=bool)
    inside[row, np.repeat(np.arange(model.pawley.n), np.diff(indptr))] = True
    tail = Jh[:, n_table:]
    assert np.count_nonzero(tail) and not np.any(tail[~inside])

    A_dense, b_dense = Jh.T @ Jh, -(Jh.T @ r)
    np.testing.assert_allclose(A.toarray(), A_dense, rtol=0.0,
                               atol=1e-12 * float(np.max(np.abs(A_dense))))
    np.testing.assert_allclose(b, b_dense, rtol=0.0,
                               atol=1e-12 * float(np.max(np.abs(b_dense))))

    # past the density cut the stage keeps the dense build
    density = len(row) / (Jh.shape[0] * model.pawley.n)
    assert density <= ls_mod.PAWLEY_SPARSE_DENSITY
    monkeypatch.setattr(ls_mod, "PAWLEY_SPARSE_DENSITY", 0.5 * density)
    assert _pawley_normal_equations(model, n_table) is None


# --------------------------------------------------------------- guards
def test_pawley_never_frees_structure_or_scale():
    pattern = synthesize()
    s, ins = perturbed_models()
    ref = Refinement(s, ins, history=False)
    result = ref.fit(pattern, mode="pawley")
    freed = {p for stage in result.stages for p in stage.freed}
    assert not any(p.endswith(".scale") for p in freed)
    assert not any(".atoms." in p for p in freed)


def test_the_emission_lines_refine_under_both_intensity_models():
    """One intensity per reflection is drawn through every line at its weight,
    so the doublet ratio is a shape the per-hkl intensities cannot absorb, and
    a wavelength refines against a held cell (WP-2002, 2026-10-20).  Until then
    ``mode_fixed_path`` force-fixed every ``.source.lines.`` path."""
    from rietx.refine import mode_fixed_path

    for mode in ("lebail", "pawley"):
        for path in ("instrument.source.lines.1.weight",
                     "instrument.source.lines.0.wavelength"):
            assert not mode_fixed_path(path, mode), (path, mode)
        assert mode_fixed_path("phases.0.scale", mode)


# ------------------------------------------- a reflection centred off the data
FAP_CIF = Path(__file__).parent / "data" / "fluorapatite.cif"
FAP_TT = np.arange(15.0, 75.0, 0.01)


def _fap_instrument(true_background: bool) -> Instrument:
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.profile.w.value = 4e-3
    ins.background = (BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (200.0, -30.0, 10.0)])
        if true_background else BackgroundChebyshev.with_terms(3))
    return ins


def fap_series(n: int, span: int = 10) -> list[PatternData]:
    """Issue #440's synthetic fluorapatite series: patterns 0..n-1 of a
    ``span``-pattern ramp (cell +0.3 %, two coordinates and one Biso moving),
    Poisson counts, data ending at 74.99° with (6 0 2) centred at 75.44°."""
    from rietx import Structure

    out = []
    for k in range(n):
        s = Structure.from_cif(str(FAP_CIF))
        p, f = s.phases[0], k / (span - 1)
        at = {a.label: a for a in p.atoms}
        p.cell.a.value *= 1 + 3e-3 * f
        p.cell.c.value *= 1 + 3e-3 * f
        p.scale.value = 2e-3
        at["Ca2"].x.value += 0.02 * f
        at["O7"].z.value += 0.03 * f
        at["Ca1"].biso.value += 1.5 * f
        ins = _fap_instrument(True)
        m = compile_model(s, ins, PatternData(two_theta=FAP_TT.tolist(),
                                              intensity=[0.0] * len(FAP_TT)))
        t = ParameterTable(s, ins)
        y = np.random.default_rng(100 + k).poisson(
            np.maximum(m.evaluate(t.decode(t.x0())), 1.0))
        out.append(PatternData(two_theta=FAP_TT.tolist(),
                               intensity=y.astype(float).tolist()))
    return out


def test_pawley_intensity_centred_off_the_data_stays_bounded():
    """WP-1459 (issue #440): a reflection whose every line is centred past the
    last channel meets the data only through a tail, and as a free linear
    column it refined to 1.45e8 against a median of 81.  The list keeps it
    (the margin lets a stage move a reflection *onto* the data), flagged
    ``off_data`` and ridged toward zero; after a full plan no such intensity
    may exceed the phase median (measured: 26, 26 and 2e-4 against 81)."""
    from rietx import Structure

    ref = Refinement(Structure.from_cif(str(FAP_CIF)), _fap_instrument(False))
    result = ref.fit(fap_series(1)[0], mode="pawley", plan="pawley_default")
    assert result.status == "converged"
    model = ref._model
    cp = model.phases[0]
    hkl = [tuple(h) for h in cp.reflections.hkl.tolist()]
    off = cp.off_data
    assert off is not None and off[hkl.index((6, 0, 2))]
    # the flag is "no line centred on the data", read off the compile
    assert not off[(cp.tt_primary >= model.tt_min) & (cp.tt_primary <= model.tt_max)].any()
    assert sorted(model.pawley.off_data) == list(np.flatnonzero(off))
    median = float(np.median(cp.hkl_intensity))
    assert cp.hkl_intensity[off].max() <= median
    # one ridge row per off-data reflection, below the overlap rows
    R = model.pawley.restraint
    ridge = R[-int(off.sum()):]
    assert (np.count_nonzero(ridge, axis=1) == 1).all()
    assert sorted(np.flatnonzero(ridge.any(axis=0))) == list(np.flatnonzero(off))
    # ...and the result names them, once for the phase (the review of #453):
    # a caller exporting intensities must see which ones are the ridge's
    ridged = [dg for dg in result.diagnostics if dg.code == "PAWLEY_OFF_DATA_RIDGED"]
    assert len(ridged) == 1 and ridged[0].level == "info"
    name = ref.structure.phases[0].name
    assert ridged[0].where == [f"{name} {hkl[k]}" for k in np.flatnonzero(off)]
    assert f"{name} (6, 0, 2)" in ridged[0].where


def test_pawley_off_data_code_is_silent_when_every_reflection_is_on_the_data():
    """The same pattern cut at 73.5°, where no reflection falls in the list's
    margin past the last channel (the next line is at 74.19°): nothing is
    ridged, so ``PAWLEY_OFF_DATA_RIDGED`` must not fire."""
    from rietx import Structure

    p = fap_series(1)[0]
    tt = np.asarray(p.two_theta)
    keep = tt <= 73.5
    cut = PatternData(two_theta=tt[keep].tolist(),
                      intensity=np.asarray(p.intensity)[keep].tolist())
    ref = Refinement(Structure.from_cif(str(FAP_CIF)), _fap_instrument(False))
    result = ref.fit(cut, mode="pawley", plan="pawley_default")
    assert result.status == "converged"
    assert not ref._model.pawley.off_data
    assert not [dg for dg in result.diagnostics if dg.code == "PAWLEY_OFF_DATA_RIDGED"]
