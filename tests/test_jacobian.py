"""Analytic coordinate-DOF Jacobian columns vs plain finite differences.

Same tolerance style as ``test_v02_core.test_analytic_jacobian_matches_fd``:
relative column error < 5·10⁻³ and direction cosine > 0.99999.  Covers a
special position whose constraint reduces the free count (rutile O, one DOF
moving x and y together) and a general position (P2₁/c, three DOFs).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import (
    _column_extras,
    _fd_typicals,
    _make_jacobian,
    _make_residual,
)
from rietx.params.vector import FLOOR_SEEDS, VAR_PREFIX, AffineTie, ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from tests.test_coordinates import make_rutile


def make_p21c_toy() -> Structure:
    """One heavy atom on the fixed 2a inversion centre, one C on general 4e."""
    return Structure(phases=[Phase(
        name="toy",
        space_group="P21/c",
        cell=Cell(
            a=Parameter(value=5.2), b=Parameter(value=6.4),
            c=Parameter(value=7.8), alpha=Parameter(value=90.0),
            beta=Parameter(value=105.0), gamma=Parameter(value=90.0),
        ),
        atoms=[
            Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="C", species="C", x=Parameter(value=0.23),
                 y=Parameter(value=0.31), z=Parameter(value=0.42)),
        ],
    )])


def _state(structure, wavelength=1.5406, tt=(10.0, 90.0, 0.02)):
    structure.phases[0].scale.value = 1e-3
    ins = Instrument.debye_scherrer(wavelength=wavelength)
    ins.profile.w.value = 1e-2
    grid = np.arange(*tt)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    return structure, ins, pattern


def _check_columns(structure, free_paths, ties=(), *, instrument=None):
    structure, ins, pattern = _state(structure)
    if instrument is not None:
        ins = instrument
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path, tie in ties:
        table.set_tie(path, tie)
    table.refresh_ties()
    for path in free_paths:
        assert table.set_vary([path], True), path
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))

    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    for c, path in enumerate(table.free_paths):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        col_fd = (residual(tp) - r0) / h
        col_an = J[:, c]
        scale = np.linalg.norm(col_fd)
        assert scale > 0, f"{path}: dead FD column — test state is degenerate"
        err = np.linalg.norm(col_an - col_fd) / scale
        assert err < 5e-3, f"{path}: analytic vs FD column mismatch ({err:.2e})"
        cos = float(col_an @ col_fd) / (np.linalg.norm(col_an) * scale)
        assert cos > 0.99999, f"{path}: column direction off (cos={cos:.6f})"


def test_special_position_dof_column_matches_fd():
    # one DOF moving x and y together through the [1, 1, 0] row; mixed with
    # other analytic families to catch cross-column indexing mistakes
    _check_columns(make_rutile(), [
        "phases.0.atoms.1.dof.0", "phases.0.cell.a", "phases.0.scale",
        "phases.0.atoms.1.biso", "instrument.zero_shift",
    ])


def test_general_position_dof_columns_match_fd():
    _check_columns(make_p21c_toy(), [
        "phases.0.atoms.1.dof.0", "phases.0.atoms.1.dof.1",
        "phases.0.atoms.1.dof.2", "phases.0.scale",
    ])


def test_constrained_adp_dof_columns_match_fd():
    """Rutile: three ADP patterns per site, one of them the U11 = U22 tie.

    Freeing coordinate and ADP DOFs together also checks that the two
    analytic families do not cross-index each other's constraint rows.
    """
    from tests.test_aniso_adp import make_aniso_rutile

    _check_columns(make_aniso_rutile(), [
        "phases.0.atoms.0.adp.0", "phases.0.atoms.0.adp.1",
        "phases.0.atoms.0.adp.2", "phases.0.atoms.1.adp.0",
        "phases.0.atoms.1.dof.0", "phases.0.scale",
    ])


def test_general_position_adp_columns_match_fd():
    """All six components free on a P2₁/c general site, monoclinic cell —
    nothing here is protected by an orthogonal metric or a symmetric R."""
    from rietx.schemas.structure import AnisoU

    toy = make_p21c_toy()
    toy.phases[0].atoms[1].aniso = AnisoU.from_values(
        [0.012, 0.017, 0.009, 0.0018, -0.0031, 0.0007])
    _check_columns(toy, [f"phases.0.atoms.1.adp.{k}" for k in range(6)]
                   + ["phases.0.atoms.1.dof.0", "phases.0.cell.beta"])


def test_adp_dof_absent_in_lebail_jacobian():
    from tests.test_aniso_adp import make_aniso_rutile

    structure, ins, pattern = _state(make_aniso_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.0.adp.0"], True)
    model = compile_model(structure, ins, pattern, mode="lebail",
                          moving_paths=set(table.moving_paths))
    J = _make_jacobian(model, table)(table.x0())
    assert np.allclose(J[:, 0], 0.0)


def test_free_count_reflects_site_symmetry():
    rutile = make_rutile()
    _, ins, _ = _state(rutile)
    table = ParameterTable(rutile, ins)
    assert table.set_vary(["phases.0.atoms.*.dof.*"], True) == ["phases.0.atoms.1.dof.0"]

    toy = make_p21c_toy()
    table = ParameterTable(toy, Instrument.debye_scherrer(wavelength=1.5406))
    assert table.set_vary(["phases.0.atoms.*.dof.*"], True) == [
        "phases.0.atoms.1.dof.0", "phases.0.atoms.1.dof.1", "phases.0.atoms.1.dof.2"]


def test_dof_absent_in_lebail_jacobian():
    """In Le Bail mode a coordinate DOF has no intensity effect: its FD
    column is zero and the analytic branch must not fire spuriously."""
    structure, ins, pattern = _state(make_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.1.dof.0"], True)
    model = compile_model(structure, ins, pattern, mode="lebail",
                          moving_paths=set(table.moving_paths))
    J = _make_jacobian(model, table)(table.x0())
    assert np.allclose(J[:, 0], 0.0)


# ------------------------------------------------- user ties (WP-1070)
def _column(structure, free_paths, path, ties=()):
    """The analytic column for ``path``, with ``ties`` declared on the table.

    Returned rather than compared to finite differences on purpose: the check
    below is *additivity*, which is exact and independent of the branch that
    produced any of the three columns.  An FD reference could not separate a
    gated column from an un-gated one at the step size the fallback itself
    uses — it **is** that finite difference.
    """
    structure, ins, pattern = _state(structure)
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for tied, tie in ties:
        table.set_tie(tied, tie)
    table.refresh_ties()
    for p in free_paths:
        assert table.set_vary([p], True), p
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    theta = table.x0()
    return _make_jacobian(model, table)(theta)[:, table.free_paths.index(path)]


def test_a_tie_makes_one_column_carry_both_dependents():
    """∂y/∂θ with b₁ ← b₀ is ∂y/∂b₀ + ∂y/∂b₁, and the column must be the sum.

    Exact by the chain rule at coefficient 1, and measurable one column at a
    time by freeing each Biso alone — so this says the tie is *carried*, not
    merely that the column looks plausible.  The peak-chain branch handles it
    because it re-derives from ``table.decode``; the assertion is what would
    fail if a branch computed only the path it was named for.
    """
    tie = [("phases.0.atoms.1.biso", AffineTie.identity("phases.0.atoms.0.biso"))]
    b0 = _column(make_rutile(), ["phases.0.atoms.0.biso"], "phases.0.atoms.0.biso")
    b1 = _column(make_rutile(), ["phases.0.atoms.1.biso"], "phases.0.atoms.1.biso")
    tied = _column(make_rutile(), ["phases.0.atoms.0.biso"],
                   "phases.0.atoms.0.biso", ties=tie)
    assert np.linalg.norm(b1) > 0.01 * np.linalg.norm(b0), "degenerate test state"
    # 3.1e-8 measured; the floor is the peak chain's own per-reflection FD, and
    # a dropped dependent would be 20-30 % of the column, not 1e-5 of it
    assert np.allclose(tied, b0 + b1, rtol=0, atol=1e-5 * np.abs(b0 + b1).max())


def test_a_tie_across_phases_keeps_the_far_phases_contribution():
    """The phases re-derived are the ones C touches, not the ones the path names.

    ``_peak_chain_column`` reads its ``affected`` list off the free path's own
    ``phases.N.`` prefix.  A tie into another phase moves that phase's scalars
    through ``decode`` all the same, so a column built from the prefix alone
    comes back missing the far phase entirely — silently, since nothing about
    the near phase is wrong.
    """
    def two_phase():
        both = make_rutile()
        both.phases.append(make_p21c_toy().phases[0])
        both.phases[1].scale.value = 1e-3
        return both

    tie = [("phases.1.atoms.1.biso", AffineTie.identity("phases.0.atoms.0.biso"))]
    near = _column(two_phase(), ["phases.0.atoms.0.biso"], "phases.0.atoms.0.biso")
    far = _column(two_phase(), ["phases.1.atoms.1.biso"], "phases.1.atoms.1.biso")
    tied = _column(two_phase(), ["phases.0.atoms.0.biso"],
                   "phases.0.atoms.0.biso", ties=tie)
    assert np.linalg.norm(far) > 0.01 * np.linalg.norm(near), "degenerate test state"
    assert np.allclose(tied, near + far, rtol=0, atol=1e-5 * np.abs(near + far).max())


def test_a_tie_beyond_a_branchs_reach_falls_back_and_stays_exact():
    """A tie between background coefficients leaves the background branch.

    y is exactly linear in the Chebyshev coefficients, so the tied column has a
    closed form — the *sum* of the two design rows — which the branch that
    writes one design row cannot produce.  The gate sends the column to the
    whole-model FD fallback instead, and that decodes through C like the
    residual does.
    """
    structure, ins, pattern = _state(make_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_tie("instrument.background.c1",
                  AffineTie.identity("instrument.background.c0"))
    table.refresh_ties()
    assert table.set_vary(["instrument.background.c0"], True)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    column = _make_jacobian(model, table)(table.x0())[:, 0]
    n0 = list(model.bkg_paths).index("instrument.background.c0")
    n1 = list(model.bkg_paths).index("instrument.background.c1")
    both = -(model.bkg_design[n0] + model.bkg_design[n1]) / model.sigma
    assert np.allclose(column[:len(both)], both, rtol=1e-4)
    # and the un-gated branch really would have been wrong here
    one = -model.bkg_design[n0] / model.sigma
    assert not np.allclose(one, both, rtol=1e-2)


def test_a_cross_atom_dof_tie_matches_finite_differences():
    """Two general-position atoms moving together: outside one atom's rows.

    ``_structural_column`` reads the coefficients of *one* atom's x/y/z off C,
    so a tie between two atoms' displacement DOFs reaches past it.  Nothing
    here is protected by symmetry — P2₁/c general sites, monoclinic cell.
    """
    toy = make_p21c_toy()
    toy.phases[0].atoms.append(Atom(
        label="N", species="N", x=Parameter(value=0.61),
        y=Parameter(value=0.18), z=Parameter(value=0.77)))
    _check_columns(toy, ["phases.0.atoms.1.dof.0", "phases.0.scale"],
                   ties=[("phases.0.atoms.2.dof.0",
                          AffineTie.identity("phases.0.atoms.1.dof.0"))])


def test_column_extras_is_empty_without_a_tie_and_names_one_with():
    """The dispatch input itself: empty everywhere an unconstrained model looks.

    That emptiness is what keeps every existing model on exactly the branch it
    took before the gate — the derived ties are the reason the list is *not*
    empty in general, and they stay on their own branches because each declares
    the reach it covers.
    """
    structure, ins, _ = _state(make_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.0.biso", "phases.0.cell.a"], True)
    extras = dict(zip(table.free_paths, _column_extras(table), strict=True))
    assert extras["phases.0.atoms.0.biso"] == []
    # a derived tie is not a special case: tetragonal b←a shows up the same way
    assert extras["phases.0.cell.a"] == ["phases.0.cell.b"]

    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie.identity("phases.0.atoms.0.biso"))
    extras = dict(zip(table.free_paths, _column_extras(table), strict=True))
    assert extras["phases.0.atoms.0.biso"] == ["phases.0.atoms.1.biso"]


def test_p21c_general_site_has_all_six_adp_and_three_coord():
    """The toy structure really exercises the general-position path."""
    from rietx.crystallography.wyckoff import site_constraints

    sc = site_constraints("P21/c", (0.23, 0.31, 0.42))
    assert sc.coord_basis.tolist() == np.eye(3, dtype=int).tolist()
    fixed = site_constraints("P21/c", (0.0, 0.0, 0.0))
    assert fixed.coord_basis.shape == (0, 3)


# -- the free-set mask on the profile bases (WP-1109) ---------------------

def _masked_pair(free_paths):
    """(masked J, unmasked J) for a free set, plus the mask's own verdict."""
    from rietx.optimize.least_squares import _intensity_only

    structure, ins, pattern = _state(make_p21c_toy())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in free_paths:
        assert table.set_vary([path], True), path
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    bkg_cols = {p: n for n, p in enumerate(model.bkg_paths)}
    claimed = all(_intensity_only(p, bkg_cols) for p in table.free_paths)
    theta = table.x0()
    j_masked = _make_jacobian(model, table)(theta)
    return j_masked, theta, model, table, claimed


@pytest.mark.parametrize("path,intensity_only", [
    ("phases.0.scale", True),
    ("phases.0.extinction", True),
    ("phases.2.atoms.3.biso", True),
    ("phases.0.atoms.1.dof.0", True),
    ("phases.0.atoms.1.adp.2", True),
    ("phases.0.atoms.1.occ", True),
    ("phases.0.preferred_orientation.r", True),
    ("instrument.source.lines.1.weight", True),
    ("instrument.polarization", True),
    ("instrument.background.c3", True),        # never touches a peak at all
    # the load-bearing half: every one of these moves or reshapes a peak, so
    # letting one into the allow-list would skip bases its column needs
    ("phases.0.cell.a", False),
    ("phases.0.cell.beta", False),
    ("instrument.zero_shift", False),
    ("instrument.profile.w", False),
    ("instrument.profile.x", False),
    ("phases.0.lor_size", False),
    ("phases.0.gauss_strain", False),
    ("phases.0.microstrain.dof.0", False),
    ("instrument.geometry.sample_displacement", False),
    ("instrument.geometry.sample_transparency", False),
    ("instrument.geometry.axial_sl", False),
    # a name nothing recognises falls through to the full bases, which is the
    # safe side: this is what makes a *new* parameter cost work, never
    # correctness
    ("instrument.something.invented.later", False),
])
def test_intensity_only_claim_matches_the_families(path, intensity_only):
    """The claim ``_INTENSITY_ONLY`` makes, family by family — asked of the
    predicate directly, because it is a statement about a path's *name* and
    holds whether or not a given instrument has that parameter to free."""
    from rietx.optimize.least_squares import _intensity_only

    bkg = {f"instrument.background.c{n}": n for n in range(6)}
    assert _intensity_only(path, bkg) is intensity_only


def test_masked_jacobian_is_bit_identical_on_an_intensity_only_stage():
    """The mask's claim: with only intensities free, ∂pos/∂p, ∂Γ/∂p and ∂η/∂p
    are identically zero, so dropping the partials they multiply removes a
    multiply by zero.  Bit-identical, not close — an ``allclose`` check here
    would pass for a mask that dropped a term the column needed."""
    free = ["phases.0.scale", "phases.0.atoms.1.biso",
            "instrument.background.c0", "instrument.background.c1"]
    j_masked, theta, model, table, claimed = _masked_pair(free)
    assert claimed
    j_full = np.zeros_like(j_masked)
    # rebuild the same Jacobian with the mask denied: patch the model's own
    # derivative_bases so the caller's request for lean bases is ignored
    original = type(model).derivative_bases

    def always_full(self, values, intensities=None, axial_derivs=True,
                    profile_derivs=True):
        return original(self, values, intensities, axial_derivs=axial_derivs,
                        profile_derivs=True)

    type(model).derivative_bases = always_full
    try:
        j_full = _make_jacobian(model, table)(theta)
    finally:
        type(model).derivative_bases = original
    assert np.array_equal(j_masked, j_full)


def test_a_wrong_intensity_only_claim_raises_and_names_the_path():
    """The gate on the gate.  ``_INTENSITY_ONLY`` is a claim about what a
    parameter *name* reaches, and the failure mode of a wrong one is a column
    that comes back short rather than an error — the same shape the whole-model
    FD fallback exists to prevent.  So the scalars ``_peak_chain_column``
    finite-differences anyway are checked against the claim, and a mismatch
    raises.  Forced here by masking a stage that genuinely moves peaks."""
    structure, ins, pattern = _state(make_p21c_toy())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    assert table.set_vary(["phases.0.cell.a"], True)
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    original = type(model).derivative_bases

    def always_lean(self, values, intensities=None, axial_derivs=True,
                    profile_derivs=True):
        return original(self, values, intensities, axial_derivs=False,
                        profile_derivs=False)

    type(model).derivative_bases = always_lean
    try:
        with pytest.raises(AssertionError, match=r"phases\.0\.cell\.a"):
            _make_jacobian(model, table)(table.x0())
    finally:
        type(model).derivative_bases = original


def test_lean_bases_carry_the_same_omega_and_no_partials():
    """Ω is the same convolution either way; only the partials go missing, and
    they go missing as ``None`` so a consumer that forgot to check fails
    loudly rather than reading a zero."""
    structure, ins, pattern = _state(make_p21c_toy())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld")
    values = table.decode(table.x0())
    full = model.derivative_bases(values, None, axial_derivs=False)
    lean = model.derivative_bases(values, None, profile_derivs=False)
    assert full.entries and lean.entries
    for rows_f, rows_l in zip(full.entries, lean.entries, strict=True):
        assert len(rows_f) == len(rows_l)
        for f, s in zip(rows_f, rows_l, strict=True):
            assert f[:4] == s[:4]
            assert np.array_equal(f[4], s[4])          # Ω
            assert all(p is None for p in s[5:])       # every partial
            assert all(p is not None for p in f[5:8])  # ∂pos, ∂Γ, ∂η


def _scale_state(free=("phases.0.scale",)):
    """A compiled rutile state with ``free`` varied, plus its expansion point."""
    structure, ins, pattern = _state(make_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in free:
        assert table.set_vary([path], True), path
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    theta = table.x0()
    return model, table, theta, table.decode(theta)


@pytest.mark.parametrize("frac", [1.0, 1e-2, 1e-4])
def test_the_scale_column_is_exact_and_its_step_size_does_not_matter(frac):
    """∂y/∂scale is the phase's own contribution over the scale — exactly.

    The scale enters ``phase_peaks`` once, in ``base = scale · mult · |F|²``,
    and every factor after it — the March multiplier, the line weight, Lp,
    Sabine extinction (which reads the *raw* ``|F|²``), specimen absorption,
    surface roughness, the off-the-sphere mask — is independent of it.  So
    the intensity is linear in the scale and a difference quotient in
    *physical* space carries no truncation error at any step.

    That is why the step is a parameter here rather than a small constant: a
    check at one step could be passed by a wrong column whose error happened
    to sit under an FD tolerance, while agreement at a **100 % step** and at
    1e-4 together say the function is linear and the coefficient is right.
    The error grows as the step shrinks, which is cancellation and the
    signature of exactness, not of a bug.

    The peer of ``test_pawley_intensity_columns_are_exact_across_backends``,
    and the reason a θ-space FD is *not* the reference: the scale is a
    softplus of θ, so both the whole-model FD and the peak-chain FD carry the
    transform's curvature — they agree with each other to 1e-11 and with the
    truth to 5e-6 (WP-1121 § Findings 3).
    """
    from rietx.optimize.least_squares import _scale_column

    model, table, theta, values = _scale_state()
    bases = model.derivative_bases(values, None)
    column = _scale_column(model, bases, values, 0)

    s0 = values["phases.0.scale"]
    y0 = np.asarray(model.evaluate(values))
    moved = dict(values)
    moved["phases.0.scale"] = s0 * (1.0 + frac)
    quotient = (np.asarray(model.evaluate(moved)) - y0) / (s0 * frac)

    err = np.max(np.abs(column - quotient)) / np.max(np.abs(quotient))
    bar = {1.0: 1e-14, 1e-2: 1e-12, 1e-4: 1e-10}[frac]
    assert err < bar, f"step {frac:g}: {err:.3e}"


def test_a_dead_phase_takes_the_fd_path_rather_than_dividing_by_its_scale():
    """``scale == 0`` is reachable and the analytic column is 0/0 there.

    A scale is refined in its own units on a lower bound of 0 (WP-1938), so
    a phase the data do not support stops exactly on it.  The analytic
    column divides by the scale — and unlike a width, a zero scale does
    **not** make the derivative zero: it is the whole unscaled chain, which
    is exactly what lets a dead phase come back.  So the dispatcher tests the
    scale and the finite-difference path, which stays correct there, keeps
    the column.

    Three halves are asserted, because any one alone would pass for the
    wrong reason.  The fence is shown to be **load-bearing**: the analytic
    expression really does produce NaN at this state.  The column the
    dispatcher builds is shown to be a finite difference.  And it is the one
    the scale has anywhere else, since the model is linear in it: the phase
    at zero still has its pattern as a gradient.  Under softplus it was
    zeros, the slope having underflowed on both sides of the step.
    """
    from rietx.optimize.least_squares import (
        _fd_typicals,
        _make_jacobian,
        _scale_column,
        fd_step,
    )

    model, table, theta, _ = _scale_state()
    c = table.free_paths.index("phases.0.scale")
    live = _make_jacobian(model, table)(theta)[:, c]   # analytic, scale > 0
    theta = theta.copy()
    theta[c] = 0.0
    values = table.decode(theta)
    assert values["phases.0.scale"] == 0.0

    with np.errstate(invalid="ignore"):
        unfenced = _scale_column(model, model.derivative_bases(values, None),
                                 values, 0)
    assert np.isnan(unfenced).any(), \
        "the 0/0 the fence exists for did not arise: check the state, not it"

    column = _make_jacobian(model, table)(theta)[:, c]
    assert np.all(np.isfinite(column)), "the 0/0 fence let a NaN through"

    residual = _make_residual(model, table)
    h = fd_step(theta[c], _fd_typicals(table)[c])
    tp = theta.copy()
    tp[c] += h
    fd = (residual(tp) - residual(theta)) / h
    # the dispatcher's FD is the peak chain's, which differences the
    # per-reflection scalars rather than the whole model: the two agree to
    # rounding (equal while both were the softplus zeros)
    np.testing.assert_allclose(column, fd, rtol=0.0,
                               atol=1e-12 * np.max(np.abs(fd)))
    err = np.max(np.abs(column - live)) / np.max(np.abs(live))
    assert err < 1e-8, f"the column at zero is not the live one: {err:.3e}"


def test_a_width_is_stepped_by_its_unit_and_everything_else_by_one():
    """WP-1936: a width takes FLOOR_SEEDS' size for its unit.

    ``u``, ``v`` and ``w`` are deg² terms of a variance, so they are widths
    although ``u`` and ``v`` may go negative.  ``x`` is a deg row bounded at
    0, so it is a width, and so is ``y``, which has no floor of its own since
    2026-10-23 (WP-2002) and is named in ``_SIGNED_WIDTHS``.  Since WP-1938 every row is refined in
    its own units, so ``w`` and ``y`` take their unit's size too, where under
    softplus their θ was already logarithmic and kept 1.  The zero shift is
    in degrees, but it is an offset that may go negative, so it keeps 1.  So
    does the unitless cell.
    """
    structure = make_rutile()
    ins = Instrument.bragg_brentano()
    ins.profile.x = Parameter(value=1e-3, min=0.0, max=1.0, unit="deg")
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    paths = ["phases.0.cell.a", "instrument.zero_shift",
             *(f"instrument.profile.{n}" for n in "uvwxy")]
    for path in paths:
        assert table.set_vary([path], True), path
    typical = dict(zip(table.free_paths, _fd_typicals(table), strict=True))
    assert typical == {
        "phases.0.cell.a": 1.0, "instrument.zero_shift": 1.0,
        "instrument.profile.u": FLOOR_SEEDS["deg^2"],
        "instrument.profile.v": FLOOR_SEEDS["deg^2"],
        "instrument.profile.w": FLOOR_SEEDS["deg^2"],
        "instrument.profile.x": FLOOR_SEEDS["deg"],
        "instrument.profile.y": FLOOR_SEEDS["deg"]}


def test_a_variable_with_no_unit_is_stepped_by_the_width_it_drives():
    """A ``vars.*`` column is sized by its reach, never by its name.

    ``vars.U`` carries no unit, so read off its own row it would keep the step
    of 1.  It drives ``u`` at coefficient 2, so its size is half of ``u``'s.
    """
    table = ParameterTable(make_rutile(), Instrument.bragg_brentano())
    table.set_vary(["*"], False)
    table.add_parameter(f"{VAR_PREFIX}U", 0.0, vary=True, lo=-1.0, hi=1.0)
    table.set_tie("instrument.profile.u",
                  AffineTie(terms=((f"{VAR_PREFIX}U", 2.0),), const=0.0))
    table.refresh_ties()
    typical = dict(zip(table.free_paths, _fd_typicals(table), strict=True))
    assert typical == {f"{VAR_PREFIX}U": FLOOR_SEEDS["deg^2"] / 2.0}
