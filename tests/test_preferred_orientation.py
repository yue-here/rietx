"""March-Dollase preferred orientation (WP-0307).

Physics: a single-axis intensity multiplier P_hkl(r) averaged over the frozen
symmetry orbit (``model/preferred_orientation.py``); r = 1 is the identity.
The tetragonal rutile cell gives a clean, identifiable c-axis texture signal —
cubic LaB6 barely shows single-axis PO because its 48-fold orbit averages the
directional signature away, which is itself the reason PO matters for low-
symmetry platy phases and is checked here as a physics fact, not tuned around.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, Parameter, PatternData
from rietx.model.forward import compile_model
from rietx.model.preferred_orientation import (
    cos2_alpha,
    march_dollase_and_dr,
    march_dollase_factors,
    march_term,
    march_term_and_dr,
    orbit_layout,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.structure import MARCH_R_MIN, PreferredOrientation
from tests.test_coordinates import make_rutile

OUT = Path(__file__).parent / "output"


def _po(axis, r, *, vary=False):
    return PreferredOrientation(
        axis=axis, r=Parameter(value=r, vary=vary, min=0.0, transform="softplus"))


# -- schema ------------------------------------------------------------


def test_po_defaults_off_and_round_trips():
    from rietx.schemas.structure import Phase

    phase = make_rutile().phases[0]
    assert phase.preferred_orientation is None  # opt-in

    phase.preferred_orientation = _po((0, 0, 1), 1.0)
    r = phase.preferred_orientation.r
    # min is MARCH_R_MIN, not 0.0: the March factor divides by r
    # (WP-1028 §(e)); no ceiling since WP-2002
    assert r.value == 1.0 and r.vary is False
    assert (r.min, r.max) == (MARCH_R_MIN, np.inf)

    phase.preferred_orientation.r.value = 0.8
    phase.preferred_orientation.r.vary = True
    back = Phase.model_validate_json(phase.model_dump_json())
    assert back.preferred_orientation.axis == (0, 0, 1)
    assert back.preferred_orientation.r.value == pytest.approx(0.8)
    assert back.preferred_orientation.r.vary is True


def test_po_axis_zero_rejected():
    with pytest.raises(ValueError, match="no direction"):
        PreferredOrientation(axis=(0, 0, 0))


# -- parameter wiring --------------------------------------------------


def test_po_param_wiring_and_routing():
    """r enters θ under ``phases.*.preferred_orientation.r``, decodes back, is
    *not* claimed by the structural (dof/adp) analytic-column regex, but *is*
    claimed by the dedicated March-Dollase column regex."""
    from rietx.optimize.least_squares import _PO_PATH, _STRUCTURAL_PATH

    s = make_rutile()
    s.phases[0].preferred_orientation = _po((0, 0, 1), 0.8)
    table = ParameterTable(s, Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["*"], False)
    assert table.set_vary(["phases.*.preferred_orientation.r"], True) == \
        ["phases.0.preferred_orientation.r"]
    assert table.decode(table.x0())["phases.0.preferred_orientation.r"] == pytest.approx(0.8)

    assert _STRUCTURAL_PATH.match("phases.0.preferred_orientation.r") is None
    assert _PO_PATH.match("phases.0.preferred_orientation.r") is not None
    # a phase without a PO block registers no such path, so the glob is safe
    t2 = ParameterTable(make_rutile(), Instrument.debye_scherrer(wavelength=1.5406))
    assert t2.set_vary(["phases.*.preferred_orientation.r"], True) == []


# -- physics -----------------------------------------------------------


def _rutile_orbits():
    from rietx.crystallography.symmetry import reflection_orbits

    s = make_rutile()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    tt = np.arange(15.0, 90.0, 0.02)
    pat = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    m = compile_model(s, ins, pat, mode="rietveld")
    refl = m.phases[0].reflections
    orbits = reflection_orbits(refl.spacegroup, refl.hkl)
    return refl, orbits


def test_march_factor_is_identity_at_r_one():
    """P_hkl ≡ 1 for every reflection at r = 1, any cell — the no-correction case."""
    refl, orbits = _rutile_orbits()
    members, seg, counts = orbit_layout(orbits)
    gstar = np.diag([1.0 / 4.5937**2, 1.0 / 4.5937**2, 1.0 / 2.9587**2])
    P = march_dollase_factors(members, seg, counts, np.array([0, 0, 1]), gstar, 1.0)
    assert np.allclose(P, 1.0, atol=1e-14)


def test_orbit_layout_counts_match_multiplicity():
    """The frozen orbit sizes equal the reflection multiplicities — the same
    set ``generate_reflections`` counts, reused rather than recomputed."""
    refl, orbits = _rutile_orbits()
    _members, _seg, counts = orbit_layout(orbits)
    assert np.array_equal(counts, refl.multiplicity)


def test_cos2_alpha_orthogonal_known():
    """cos²α on a cube (G* = I): (100)⊥(001) → 0, parallel → 1, (101)@45° → ½."""
    gstar = np.eye(3)
    members = np.array([[1, 0, 0], [0, 0, 1], [1, 0, 1]])
    c2 = cos2_alpha(members, np.array([0, 0, 1]), gstar)
    assert c2 == pytest.approx([0.0, 1.0, 0.5])


def test_march_term_derivative_matches_fd():
    c2 = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    for r in (0.6, 0.85, 1.0, 1.3, 2.0):
        _, dterm = march_term_and_dr(c2, r)
        h = 1e-7
        fd = (march_term(c2, r + h) - march_term(c2, r - h)) / (2 * h)
        assert dterm == pytest.approx(fd, rel=1e-5, abs=1e-9)


def test_march_dollase_and_dr_matches_fd_over_orbits():
    refl, orbits = _rutile_orbits()
    members, seg, counts = orbit_layout(orbits)
    gstar = np.diag([1.0 / 4.5937**2, 1.0 / 4.5937**2, 1.0 / 2.9587**2])
    axis = np.array([0, 0, 1])
    for r in (0.6, 1.0, 1.5):
        _P, dP = march_dollase_and_dr(members, seg, counts, axis, gstar, r)
        h = 1e-7
        fd = (march_dollase_factors(members, seg, counts, axis, gstar, r + h)
              - march_dollase_factors(members, seg, counts, axis, gstar, r - h)) / (2 * h)
        assert dP == pytest.approx(fd, rel=1e-5, abs=1e-8)


def test_axial_reflections_enhanced_below_one_suppressed_above():
    """With the axis = [001], (00l) reflections (scattering vector ∥ axis) are
    *enhanced* for r < 1 and *suppressed* for r > 1; equatorial (hk0) move the
    opposite way.  This is the platy-in-reflection-geometry convention, checked
    on the factor itself rather than assumed from the sign of r."""
    refl, orbits = _rutile_orbits()
    members, seg, counts = orbit_layout(orbits)
    gstar = np.diag([1.0 / 4.5937**2, 1.0 / 4.5937**2, 1.0 / 2.9587**2])
    hkl = refl.hkl
    axial = np.array([h[0] == 0 and h[1] == 0 for h in hkl])   # (00l)
    equat = np.array([h[2] == 0 for h in hkl])                 # (hk0)
    assert axial.any() and equat.any()
    P_lo = march_dollase_factors(members, seg, counts, np.array([0, 0, 1]), gstar, 0.6)
    P_hi = march_dollase_factors(members, seg, counts, np.array([0, 0, 1]), gstar, 1.6)
    assert np.all(P_lo[axial] > 1.0) and np.all(P_hi[axial] < 1.0)
    assert np.all(P_lo[equat] < 1.0) and np.all(P_hi[equat] > 1.0)


# -- forward-model integration -----------------------------------------


def _rutile_model(po=None, scale=8e-3):
    s = make_rutile()
    s.phases[0].scale.value = scale
    if po is not None:
        s.phases[0].preferred_orientation = po
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    tt = np.arange(15.0, 90.0, 0.02)
    pat = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(s, ins, pat, mode="rietveld")
    table = ParameterTable(s, ins)
    return model, table.decode(table.x0())


def test_forward_po_r_one_is_identity():
    """A phase carrying a PO block with r = 1 is bit-identical to one without."""
    m_no, v_no = _rutile_model(po=None)
    m_po, v_po = _rutile_model(po=_po((0, 0, 1), 1.0))
    assert np.array_equal(m_po.evaluate(v_po), m_no.evaluate(v_no))


def test_forward_po_changes_axial_and_equatorial_intensities():
    """r < 1 lifts the (00l) family and drops (hk0), visibly, in the pattern."""
    m_no, v_no = _rutile_model(po=None)
    m_po, v_po = _rutile_model(po=_po((0, 0, 1), 0.6))
    peaks_no = m_no.phase_peaks(0, v_no)[0][3]
    peaks_po = m_po.phase_peaks(0, v_po)[0][3]
    hkl = m_no.phases[0].reflections.hkl
    axial = np.array([h[0] == 0 and h[1] == 0 for h in hkl])
    ratio = peaks_po / np.where(peaks_no > 0, peaks_no, 1.0)
    assert np.all(ratio[axial] > 1.0), "axial reflections should be enhanced at r<1"


# -- staged plan -------------------------------------------------------


def test_mccusker_structural_frees_po_after_displacement_before_extinction():
    from rietx.strategy.staged import RefinementPlan

    names = [s.name for s in RefinementPlan.mccusker_structural().stages]
    assert "preferred_orientation" in names
    assert names.index("biso") < names.index("preferred_orientation")
    assert names.index("preferred_orientation") < names.index("extinction")
    po = next(s for s in RefinementPlan.mccusker_structural().stages
              if s.name == "preferred_orientation")
    # the spherical-harmonics texture is the same effect and frees beside it (WP-1960)
    assert po.turn_on == ["phases.*.preferred_orientation.r", "phases.*.texture.*"]


# -- analytic Jacobian -------------------------------------------------


def test_jacobian_po_column_matches_fd():
    from rietx.optimize.least_squares import _make_jacobian, _make_residual

    s = make_rutile()
    s.phases[0].scale.value = 8e-3
    s.phases[0].preferred_orientation = _po((0, 0, 1), 0.75, vary=True)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    grid = np.arange(15.0, 90.0, 0.02)
    pat = PatternData(two_theta=grid.tolist(), intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(s, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.preferred_orientation.r"], True)
    model = compile_model(s, ins, pat, mode="rietveld", moving_paths=set(table.moving_paths))

    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    c = table.free_paths.index("phases.0.preferred_orientation.r")
    h = 1e-6 * max(1.0, abs(theta[c]))
    tp = theta.copy()
    tp[c] += h
    col_fd = (residual(tp) - r0) / h
    err = np.linalg.norm(J[:, c] - col_fd) / np.linalg.norm(col_fd)
    assert err < 5e-3, f"analytic r column vs FD mismatch ({err:.2e})"


def test_jacobian_structural_columns_carry_the_po_factor():
    """The hidden-Jacobian guard: with PO on, the analytic coordinate/ADP
    columns must be multiplied by P (they miss by ~25 % at r = 0.75 otherwise).
    Checked together with extinction on, against a full-model finite
    difference."""
    from rietx.optimize.least_squares import _make_jacobian, _make_residual
    from tests.test_aniso_adp import make_aniso_rutile

    s = make_aniso_rutile()
    s.phases[0].scale.value = 1e-3
    s.phases[0].preferred_orientation = _po((0, 0, 1), 0.75, vary=True)
    s.phases[0].extinction.value = 1.5
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    grid = np.arange(12.0, 90.0, 0.02)
    pat = PatternData(two_theta=grid.tolist(), intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(s, ins)
    table.set_vary(["*"], False)
    free = ["phases.0.preferred_orientation.r", "phases.0.atoms.1.dof.0",
            "phases.0.atoms.0.adp.0", "phases.0.atoms.1.adp.1",
            "phases.0.extinction", "phases.0.scale", "phases.0.cell.a", "phases.0.cell.c"]
    for p in free:
        assert table.set_vary([p], True), p
    model = compile_model(s, ins, pat, mode="rietveld", moving_paths=set(table.moving_paths))

    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    for c, path in enumerate(table.free_paths):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        col_fd = (residual(tp) - r0) / h
        scale = np.linalg.norm(col_fd)
        assert scale > 0, f"{path}: dead FD column"
        err = np.linalg.norm(J[:, c] - col_fd) / scale
        assert err < 5e-3, f"{path}: analytic vs FD mismatch ({err:.2e})"


# -- end-to-end recovery + correlation ---------------------------------


def _synthesize_textured_rutile(axis, r_true, *, seed=7, scale=3e-2, bkg=20.0):
    s = make_rutile()
    s.phases[0].scale.value = scale
    s.phases[0].preferred_orientation = _po(axis, r_true)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    tt = np.arange(15.0, 90.0, 0.02)
    pat = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(s, ins, pat, mode="rietveld")
    table = ParameterTable(s, ins)
    y = model.evaluate(table.decode(table.x0())) + bkg
    rng = np.random.default_rng(seed)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def _po_plan(with_po: bool):
    from rietx.strategy.staged import RefinementPlan, Stage

    stages = [
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile_w", ["instrument.profile.w"]),
        Stage("biso", ["phases.*.atoms.*.biso"]),
    ]
    if with_po:
        stages.append(Stage("po", ["phases.*.preferred_orientation.r"]))
    return RefinementPlan(stages=stages)


def test_injected_po_is_recovered_within_esds():
    from rietx import Refinement
    from rietx.viz.plots import plot_result

    axis, r_true = (0, 0, 1), 0.5   # strong platy texture
    pattern = _synthesize_textured_rutile(axis, r_true)

    s = make_rutile()
    s.phases[0].scale.value = 3e-2
    s.phases[0].preferred_orientation = _po(axis, 1.0, vary=False)  # starts at identity
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    ref = Refinement(s, ins, history=False)
    result = ref.fit(pattern, plan=_po_plan(with_po=True))
    assert result.status == "converged"

    r = result.parameter("phases.0.preferred_orientation.r")
    assert r.stderr is not None and r.stderr > 0
    assert r.value == pytest.approx(r_true, abs=max(4 * r.stderr, 0.02 * r_true)), \
        f"recovered r={r.value:.4f}±{r.stderr:.4f}, truth {r_true}"
    assert abs(r.value - 1.0) > 5 * r.stderr  # resolved as textured, not just fitted

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "po_rutile_fit.png"))


def test_a_texture_below_the_old_floor_is_accepted_and_refines():
    """WP-2002, the B9 ruling: March r keeps only its pole floor.

    Before 1.10 the floor was 0.15, so a stated r of 0.1 was clipped to 0.15 on
    construction and a refinement could not go below it.  A pressed clay or
    mica plate can need less.  Measured 2026-10-20 (darwin/arm64, ``[dev]``):
    from the identity, r = 0.1 comes back as 0.10012 ± 0.00018, off its bound.
    """
    from rietx import Refinement

    stated = PreferredOrientation(axis=(0, 0, 1), r=Parameter(value=0.1, vary=True))
    assert stated.r.value == 0.1 and stated.r.min == MARCH_R_MIN < 0.15

    axis, r_true = (0, 0, 1), 0.1
    pattern = _synthesize_textured_rutile(axis, r_true)
    s = make_rutile()
    s.phases[0].scale.value = 3e-2
    s.phases[0].preferred_orientation = _po(axis, 1.0, vary=False)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    result = Refinement(s, ins, history=False).fit(pattern, plan=_po_plan(with_po=True))
    assert result.status == "converged"
    r = result.parameter("phases.0.preferred_orientation.r")
    assert r.value < 0.15 and r.at_bound is not True
    assert r.value == pytest.approx(r_true, abs=max(4 * r.stderr, 0.02 * r_true))


def test_po_is_identifiable_from_scale_and_biso():
    """r, scale and Biso all rescale intensity, but r carries an axis-angle
    signature the other two lack, so on a well-sampled pattern it stays
    identifiable and the pairwise guard does not flag it spuriously."""
    from rietx.optimize.least_squares import run_least_squares
    from rietx.strategy.staged import check_guards

    pattern = _synthesize_textured_rutile((0, 0, 1), 0.6)
    s = make_rutile()
    s.phases[0].scale.value = 3e-2
    s.phases[0].preferred_orientation = _po((0, 0, 1), 0.8)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    table = ParameterTable(s, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.preferred_orientation.r", "phases.0.scale",
                    "phases.0.atoms.*.biso"], True)
    model = compile_model(s, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    outcome = run_least_squares(model, table, max_iter=60)

    free = table.free_paths
    ir = free.index("phases.0.preferred_orientation.r")
    corr = np.asarray(outcome.correlation)
    worst = max(abs(corr[ir, j]) for j in range(len(free)) if j != ir)
    assert worst < 0.9, f"PO should be identifiable here, |ρ|max={worst:.2f}"
    guard = check_guards(table, outcome, threshold=0.9)
    assert not any(any("preferred_orientation" in p for p in c.paths)
                   for c in guard.high_correlations)


# -- Layer-1 texture diagnostic ----------------------------------------


def _detect_texture(pattern):
    from rietx import Refinement

    s = make_rutile()
    s.phases[0].scale.value = 3e-2
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    ref = Refinement(s, ins, history=False)
    ref.fit(pattern, plan=_po_plan(with_po=False))   # converge WITHOUT PO
    return ref.report().texture


def test_layer1_texture_identifies_the_injected_axis():
    """Refine a strongly-textured rutile pattern *without* a PO correction, then
    the Layer-1 diagnostic points at the injected [001] axis with the right r —
    even though the uncorrected fit is immature (texture is why), so the rest of
    Layer 1 abstains."""
    from rietx.crystallography.lattice import reciprocal_metric_tensor
    from rietx.report.texture import _equivalent

    pattern = _synthesize_textured_rutile((0, 0, 1), 0.5)
    texture = _detect_texture(pattern)
    assert len(texture) == 1
    tx = texture[0]
    assert tx.detected, f"texture not detected (r2={tx.r2:.2f})"
    assert tx.r2 > 0.9
    assert tx.march_coefficient == pytest.approx(0.5, abs=0.1)

    # the identified axis is [001] or a symmetry-equivalent of it
    refl, orbits = _rutile_orbits()
    members, seg, counts = orbit_layout(orbits)
    gstar = reciprocal_metric_tensor(4.5937, 4.5937, 2.9587, 90.0, 90.0, 90.0)
    assert _equivalent(tx.best_axis, (0, 0, 1), gstar, members, seg, counts, tol=1e-6)
    # and the best axis clearly beats the nearest non-equivalent alternative
    assert tx.r2 - tx.runner_up_r2 > 0.05


def test_layer1_texture_quiet_on_an_untextured_pattern():
    """A texture-free rutile pattern reports detected = False with r ≈ 1 — no
    *detection* is manufactured from noise.  Since WP-1054 ``best_axis`` stays
    populated as evidence (the axis the failed detection scored highest), so
    the quiet answer is ``detected=False`` at r ≈ 1, never a nulled axis."""
    pattern = _synthesize_textured_rutile((0, 0, 1), 1.0)  # r=1 ⇒ no texture
    texture = _detect_texture(pattern)
    assert len(texture) == 1
    tx = texture[0]
    assert not tx.detected
    assert tx.best_axis is not None      # evidence, not a verdict (WP-1054)
    assert tx.march_coefficient == pytest.approx(1.0, abs=0.1)


# -- Le Bail / Pawley: no calculated intensities to correct ------------


def test_texture_diagnostic_is_rietveld_only():
    """Le Bail intensities are empirical, so there is nothing to compare against
    — the diagnostic returns nothing rather than a spurious axis."""
    from rietx.report.texture import analyse_texture

    s = make_rutile()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    tt = np.arange(15.0, 90.0, 0.02)
    y = np.abs(np.sin(tt)) * 100 + 50
    pat = PatternData(two_theta=tt.tolist(), intensity=y.tolist())
    model = compile_model(s, ins, pat, mode="lebail")
    table = ParameterTable(s, ins)
    assert analyse_texture(model, table.decode(table.x0())) == []
