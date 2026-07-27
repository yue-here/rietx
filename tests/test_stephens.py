"""Stephens (1999) anisotropic strain: the rank-4 symmetry-allowed subspace.

The reference values are Stephens' Table 1 (J. Appl. Cryst. 32, 281): the
number of independent S_HKL per Laue class, and the published monomial
combinations for the high-symmetry classes.  Two property tests check the
algebra independently of any table — every basis vector must be *exactly*
fixed by every operator (integer arithmetic, no tolerance), and the dimension
must equal the character-theory count ⟨χ₄(R)⟩ for the degree-4 symmetric power
of the reciprocal-space action.

The isotropic limit gets its own test: M² lies in the allowed subspace for
*every* group by construction, and evaluating it must return exactly 1/d⁴.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pxrdref import Instrument, PatternData, Refinement
from pxrdref.crystallography.lattice import d_spacings
from pxrdref.crystallography.stephens import (
    S_EXPONENTS,
    S_NAMES,
    isotropic_coefficients,
    monomial_matrix,
    sigma2_m,
    stephens_basis,
    strain_basis,
    strain_width_deg,
)
from pxrdref.crystallography.symmetry import (
    generate_reflections,
    get_spacegroup,
    rotation_matrices,
)
from pxrdref.model.forward import compile_model
from pxrdref.optimize.least_squares import _make_jacobian, _make_residual
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.structure import (
    Atom,
    Cell,
    Phase,
    StephensStrain,
    Structure,
)
from pxrdref.strategy.staged import RefinementPlan, Stage
from pxrdref.viz.plots import plot_result

OUT = Path(__file__).parent / "output"

# (space group, Laue class, number of independent S_HKL) — Stephens Table 1
DIMENSIONS = [
    ("P m -3 m", "m-3m", 2),
    ("F d -3 m", "m-3m", 2),
    ("P m -3", "m-3", 2),
    ("P 6/m m m", "6/mmm", 3),
    ("P 6_3/m m c", "6/mmm", 3),
    ("P 6/m", "6/m", 3),
    ("P -3 m 1", "-3m1", 4),
    ("P -3 1 m", "-31m", 4),
    ("R -3 c", "-3m", 4),
    ("P -3", "-3", 5),
    ("P 4/m m m", "4/mmm", 4),
    ("I 4_1/a m d", "4/mmm", 4),
    ("P 4/m", "4/m", 5),
    ("P m m m", "mmm", 6),
    ("P b c a", "mmm", 6),
    ("P 1 2/m 1", "2/m", 9),
    ("P 1 21/c 1", "2/m", 9),
    ("P -1", "-1", 15),
    ("P 1", "-1", 15),
]


@pytest.mark.parametrize("symbol,laue,dim", DIMENSIONS)
def test_dimension_matches_stephens_table1(symbol, laue, dim):
    assert len(stephens_basis(symbol)) == dim, laue


def test_component_names_track_exponents():
    assert len(S_EXPONENTS) == 15
    assert all(sum(e) == 4 for e in S_EXPONENTS)
    assert S_NAMES[0] == "s400" and S_NAMES[-1] == "s004"
    assert len(set(S_NAMES)) == 15


@pytest.mark.parametrize("symbol", [s for s, _, _ in DIMENSIONS])
def test_basis_vectors_are_exactly_invariant(symbol):
    """Property: f(Rᵀh) = f(h) for every operator, on integer hkl, exactly."""
    basis = stephens_basis(symbol)
    rots = np.rint(rotation_matrices(get_spacegroup(symbol))).astype(np.int64)
    rng = np.random.default_rng(0)
    hkl = rng.integers(-4, 5, size=(40, 3))
    mono = monomial_matrix(hkl)
    for row in basis:
        base = mono @ row.astype(np.float64)
        for r in rots:
            imaged = monomial_matrix(hkl @ r) @ row.astype(np.float64)
            assert np.array_equal(imaged, base)


@pytest.mark.parametrize("symbol,laue,dim", DIMENSIONS)
def test_dimension_matches_character_count(symbol, laue, dim):
    """dim = ⟨χ₄(R)⟩ over the group, from the cycle-index (Molien) character
    of the 4th symmetric power — an independent count of the same subspace."""
    rots = np.rint(rotation_matrices(get_spacegroup(symbol))).astype(np.int64)
    uniq = {tuple(r.T.ravel().tolist()): r.T for r in rots}
    total = 0.0
    for m in uniq.values():
        p = [float(np.trace(np.linalg.matrix_power(m, n))) for n in range(1, 5)]
        # Newton's identity for the complete homogeneous symmetric polynomial
        # h₄ of the eigenvalues = χ of the 4th symmetric power
        h = [1.0, p[0]]
        h.append((h[1] * p[0] + p[1]) / 2.0)
        h.append((h[2] * p[0] + h[1] * p[1] + p[2]) / 3.0)
        h.append((h[3] * p[0] + h[2] * p[1] + h[1] * p[2] + p[3]) / 4.0)
        total += h[4]
    assert round(total / len(uniq)) == dim


def _named(row):
    return {S_NAMES[i]: int(v) for i, v in enumerate(row) if v}


def test_published_patterns_cubic_and_hexagonal():
    """The combinations Stephens tabulates for m-3m and 6/mmm."""
    cubic = [_named(r) for r in stephens_basis("P m -3 m")]
    assert {"s220": 1, "s202": 1, "s022": 1} in cubic
    assert {"s400": 1, "s040": 1, "s004": 1} in cubic

    hexagonal = [_named(r) for r in stephens_basis("P 6/m m m")]
    assert {"s400": 1, "s310": 2, "s220": 3, "s130": 2, "s040": 1} in hexagonal
    assert {"s202": 1, "s112": 1, "s022": 1} in hexagonal
    assert {"s004": 1} in hexagonal


def test_orthorhombic_basis_is_the_six_even_monomials():
    rows = [_named(r) for r in stephens_basis("P m m m")]
    assert sorted(rows, key=lambda d: sorted(d)) == sorted(
        [{n: 1} for n in ("s400", "s040", "s004", "s220", "s202", "s022")],
        key=lambda d: sorted(d))


def test_basis_is_deterministic():
    a = stephens_basis("P 1 21/c 1")
    b = strain_basis(rotation_matrices(get_spacegroup("P 1 21/c 1")))
    assert np.array_equal(a, b)
    assert np.array_equal(a, stephens_basis("P 1 21/c 1"))


# ----------------------------------------------------------------------
# the isotropic limit
# ----------------------------------------------------------------------
CELLS = [
    (4.1568, 4.1568, 4.1568, 90.0, 90.0, 90.0),      # cubic  (LaB6)
    (3.142, 3.142, 4.766, 90.0, 90.0, 120.0),        # hexagonal (brucite)
    (9.4, 9.4, 6.9, 90.0, 90.0, 120.0),              # hexagonal (apatite)
    (5.1, 8.3, 12.7, 90.0, 103.4, 90.0),             # monoclinic
    (5.1, 8.3, 12.7, 87.0, 103.4, 96.0),             # triclinic
]


@pytest.mark.parametrize("cell", CELLS)
def test_isotropic_coefficients_reproduce_one_over_d4(cell):
    """σ²(M) at the isotropic limit must be exactly (ε·M)² = ε²/d⁴."""
    rng = np.random.default_rng(1)
    hkl = rng.integers(-5, 6, size=(60, 3))
    hkl = hkl[~np.all(hkl == 0, axis=1)]
    s = isotropic_coefficients(cell, microstrain=1.0)
    got = sigma2_m(monomial_matrix(hkl), s)
    d = d_spacings(hkl, *cell)
    assert np.allclose(got, 1.0 / d**4, rtol=1e-12)


@pytest.mark.parametrize("symbol,cell", [
    ("P m -3 m", CELLS[0]), ("P -3 m 1", CELLS[1]), ("P 6_3/m", CELLS[2]),
    ("P 1 21/c 1", CELLS[3]), ("P -1", CELLS[4]),
])
def test_isotropic_limit_lies_in_the_allowed_subspace(symbol, cell):
    """M² is a Laue invariant for *every* group, so the isotropic seed is
    reachable exactly — this is what makes it a legal starting point."""
    basis = stephens_basis(symbol).astype(np.float64)
    s = isotropic_coefficients(cell, microstrain=2000.0)
    coef, *_ = np.linalg.lstsq(basis.T, s, rcond=None)
    assert np.allclose(basis.T @ coef, s, atol=1e-9 * max(abs(s).max(), 1.0))


@pytest.mark.parametrize("cell", CELLS)
def test_isotropic_width_is_the_plain_tan_theta_law(cell):
    """At the isotropic limit Λ is the same for every reflection: it *is* the
    ``lor_strain`` column, which is why the two may not refine together."""
    rng = np.random.default_rng(2)
    hkl = rng.integers(-5, 6, size=(50, 3))
    hkl = hkl[~np.all(hkl == 0, axis=1)]
    d = d_spacings(hkl, *cell)
    lam = strain_width_deg(monomial_matrix(hkl), isotropic_coefficients(cell, 1500.0), d)
    assert np.allclose(lam, lam[0], rtol=1e-12)
    # ΔM/M = 1500e-6 ⇒ Λ = (180/π)·1500e-6 deg
    assert lam[0] == pytest.approx(np.degrees(1500e-6), rel=1e-12)


def test_zero_coefficients_give_zero_width_not_nan():
    """An all-zero block must be the exact identity (no broadening, no NaN);
    it is rejected at the point someone tries to *refine* it, not here."""
    hkl = np.array([[1, 0, 0], [1, 1, 1], [2, 0, 2]])
    d = d_spacings(hkl, *CELLS[0])
    lam = strain_width_deg(monomial_matrix(hkl), np.zeros(15), d)
    assert np.all(np.isfinite(lam))
    assert np.all(lam < 1e-12)


# ----------------------------------------------------------------------
# schema + parameter-table wiring
# ----------------------------------------------------------------------
def make_cell(cell6) -> Cell:
    a, b, c, al, be, ga = cell6
    return Cell(a=Parameter(value=a, min=0.1), b=Parameter(value=b, min=0.1),
                c=Parameter(value=c, min=0.1), alpha=Parameter(value=al),
                beta=Parameter(value=be), gamma=Parameter(value=ga))


def brucite(strain: StephensStrain | None = None, **kw) -> Phase:
    """Mg(OH)₂, P-3m1 — the acceptance material (4 Stephens DOFs)."""
    cell = make_cell(CELLS[1])
    return Phase(name="brucite", space_group="P -3 m 1", cell=cell,
                 atoms=[Atom(label="Mg", species="Mg", x=Parameter(value=0.0),
                             y=Parameter(value=0.0), z=Parameter(value=0.0)),
                        Atom(label="O", species="O", x=Parameter(value=1 / 3),
                             y=Parameter(value=2 / 3), z=Parameter(value=0.22))],
                 microstrain=strain, **kw)


def table_for(phase: Phase) -> ParameterTable:
    return ParameterTable(Structure(phases=[phase]), Instrument.bragg_brentano())


def test_absent_block_adds_no_paths():
    paths = {e.path for e in table_for(brucite()).entries}
    assert not any(".microstrain" in p for p in paths)


def test_dofs_and_ties_follow_the_laue_basis():
    t = table_for(brucite(StephensStrain.isotropic(1000.0, make_cell(CELLS[1]))))
    paths = [e.path for e in t.entries]
    assert [p for p in paths if p.startswith("phases.0.microstrain.dof.")] == [
        f"phases.0.microstrain.dof.{k}" for k in range(4)]  # P-3m1 → 4
    assert t.free_paths == [f"phases.0.microstrain.dof.{k}" for k in range(4)]
    # every component is either tied to the DOFs or locked at zero
    for name in S_NAMES:
        e = next(e for e in t.entries if e.path == f"phases.0.microstrain.{name}")
        assert (e.tie is not None) or (e.locked and e.value == 0.0)


def test_decode_round_trips_the_isotropic_coefficients():
    block = StephensStrain.isotropic(1750.0, make_cell(CELLS[1]))
    t = table_for(brucite(block))
    values = t.decode(t.x0())
    got = np.array([values[f"phases.0.microstrain.{n}"] for n in S_NAMES])
    assert np.allclose(got, np.array(block.values()), rtol=1e-10)


def test_lor_strain_is_locked_by_a_microstrain_block():
    t = table_for(brucite(StephensStrain.isotropic(1000.0, make_cell(CELLS[1]))))
    e = next(e for e in t.entries if e.path == "phases.0.lor_strain")
    assert e.locked
    assert t.set_vary(["phases.*.lor_strain"], True) == []


def test_refining_lor_strain_alongside_a_block_is_rejected():
    with pytest.raises(ValueError, match="exactly degenerate"):
        brucite(StephensStrain.isotropic(1000.0, make_cell(CELLS[1])),
                lor_strain=Parameter(value=0.01, min=0.0, vary=True,
                                     transform="softplus"))


def test_out_of_subspace_coefficients_raise():
    s = list(StephensStrain.isotropic(1000.0, make_cell(CELLS[1])).values())
    s[S_NAMES.index("s013")] += 500.0  # not an allowed P-3m1 pattern
    with pytest.raises(ValueError, match="not compatible with the lattice symmetry"):
        table_for(brucite(StephensStrain.from_values(s, vary=True)))


def test_refining_an_all_zero_block_raises():
    with pytest.raises(ValueError, match="isotropic limit"):
        table_for(brucite(StephensStrain.from_values([0.0] * 15, vary=True)))
    # ... but an all-zero block that nobody frees is legal: it is the identity
    table_for(brucite(StephensStrain.from_values([0.0] * 15)))


def test_write_back_and_json_round_trip():
    structure = Structure(phases=[brucite(
        StephensStrain.isotropic(1200.0, make_cell(CELLS[1])))])
    before = np.array(structure.phases[0].microstrain.values())
    inst = Instrument.bragg_brentano()
    t = ParameterTable(structure, inst)
    theta = t.x0()
    theta[0] *= 1.5
    t.commit(theta)
    t.apply_to_models(structure, inst, stderr={"phases.0.microstrain.s400": 42.0})
    written = np.array(structure.phases[0].microstrain.values())
    assert not np.allclose(written, before)
    assert structure.phases[0].microstrain.s400.stderr == 42.0

    revived = Structure.model_validate_json(structure.model_dump_json())
    assert np.allclose(np.array(revived.phases[0].microstrain.values()), written)


# ----------------------------------------------------------------------
# forward model
# ----------------------------------------------------------------------
def _pattern(lo=10.0, hi=110.0, step=0.02) -> PatternData:
    grid = np.arange(lo, hi, step)
    return PatternData(two_theta=grid.tolist(),
                       intensity=np.zeros_like(grid).tolist())


def _compiled(strain: StephensStrain | None, *, free: list[str] | None = None):
    structure = Structure(phases=[brucite(strain)])
    structure.phases[0].scale.value = 1e-2
    inst = Instrument.debye_scherrer(wavelength=1.5406)
    inst.profile.w.value = 5e-3
    table = ParameterTable(structure, inst)
    table.set_vary(["*"], False)
    for path in free or []:
        assert table.set_vary([path], True), path
    model = compile_model(structure, inst, _pattern(), mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table


def test_absent_and_zero_blocks_are_bit_identical():
    """Λ ≡ 0 must cost exactly nothing: an opt-in correction that perturbs the
    off state is not opt-in."""
    m_none, t_none = _compiled(None)
    m_zero, t_zero = _compiled(StephensStrain.from_values([0.0] * 15))
    y_none = m_none.evaluate(t_none.decode(t_none.x0()))
    y_zero = m_zero.evaluate(t_zero.decode(t_zero.x0()))
    assert np.array_equal(y_none, y_zero)


def test_widths_become_direction_dependent():
    """(00l) broadens on its own when only s004 is raised — the whole point:
    two reflections at nearly the same 2θ get different widths."""
    cell = make_cell(CELLS[1])
    iso = np.array(StephensStrain.isotropic(500.0, cell).values())
    aniso = iso.copy()
    aniso[S_NAMES.index("s004")] *= 30.0

    widths = {}
    for tag, s in (("iso", iso), ("aniso", aniso)):
        model, table = _compiled(StephensStrain.from_values(s))
        values = table.decode(table.x0())
        _pos, gamma, _eta, _i = model.phase_peaks(0, values)[0]
        hkl = model.phases[0].reflections.hkl
        widths[tag] = {tuple(h): float(g) for h, g in zip(hkl, gamma)}

    # 00l picks up the extra strain; hk0 does not (l = 0 kills every monomial
    # carrying l, and s004 is the pure l⁴ pattern).  The strain law is ∝ tanθ,
    # so the *ratio* grows with angle — assert the sense everywhere and the
    # magnitude where the law has room to act.
    ratios = []
    for h, w in widths["aniso"].items():
        if h[0] == 0 and h[1] == 0:
            assert w > widths["iso"][h], h
            ratios.append(w / widths["iso"][h])
        elif h[2] == 0:
            assert w == pytest.approx(widths["iso"][h], rel=1e-12), h
    assert max(ratios) > 1.5


def test_analytic_jacobian_columns_match_finite_differences():
    dofs = [f"phases.0.microstrain.dof.{k}" for k in range(4)]
    model, table = _compiled(
        StephensStrain.isotropic(900.0, make_cell(CELLS[1])), free=dofs)
    assert table.free_paths == dofs
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    for c, path in enumerate(dofs):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        col_fd = (residual(tp) - r0) / h
        scale = np.linalg.norm(col_fd)
        assert scale > 0, f"{path}: dead FD column"
        col_an = jac[:, c]
        assert np.linalg.norm(col_an - col_fd) / scale < 5e-3, path
        cos = float(col_an @ col_fd) / (np.linalg.norm(col_an) * scale)
        assert cos > 0.99999, f"{path}: direction off (cos={cos:.6f})"


def _brucite_coef(microstrain: float) -> np.ndarray:
    basis = stephens_basis("P -3 m 1").astype(np.float64)
    coef, *_ = np.linalg.lstsq(
        basis.T, isotropic_coefficients(CELLS[1], microstrain), rcond=None)
    return coef


def _strain_from_coef(coef, *, vary: bool = True) -> StephensStrain:
    basis = stephens_basis("P -3 m 1").astype(np.float64)
    return StephensStrain.from_values(basis.T @ np.asarray(coef), vary=vary)


#: index of the pure l⁴ pattern in the P-3m1 basis — the one that broadens 00l
#: and nothing else, so scaling it alone makes an unambiguous injection
_L4_ROW = next(k for k, row in enumerate(stephens_basis("P -3 m 1"))
               if _named(row) == {"s004": 1})


# ----------------------------------------------------------------------
# seeding and the positivity guard
# ----------------------------------------------------------------------
def test_seed_puts_a_freed_zero_block_on_the_isotropic_ray():
    t = table_for(brucite(StephensStrain.from_values([0.0] * 15)))
    dofs = t.set_vary(["phases.*.microstrain.dof.*"], True)
    assert len(dofs) == 4
    # the softplus seed cannot reach identity-transform DOFs — that is exactly
    # why seed_stephens exists
    assert t.seed_softplus(dofs, 1e-3) == []
    assert sorted(t.seed_stephens(dofs, 1200.0)) == sorted(dofs)
    values = t.decode(t.x0())
    got = np.array([values[f"phases.0.microstrain.{n}"] for n in S_NAMES])
    assert np.allclose(got, isotropic_coefficients(CELLS[1], 1200.0), rtol=1e-9)


def test_seed_never_overwrites_a_deliberate_starting_model():
    t = table_for(brucite(StephensStrain.isotropic(300.0, make_cell(CELLS[1]))))
    before = t.decode(t.x0())
    assert t.seed_stephens(t.free_paths, 5000.0) == []
    assert t.decode(t.x0()) == before


def test_guard_flags_coefficients_outside_the_physical_cone():
    from pxrdref.refine import _guard_diagnostics
    from pxrdref.strategy.staged import GuardReport, check_stephens_positive

    good = _brucite_coef(600.0)
    model, table = _compiled(_strain_from_coef(good, vary=False))
    assert check_stephens_positive(table, model) == []
    assert check_stephens_positive(table, None) == []

    # drive the l⁴ pattern strongly negative: σ²(M) for 00l goes below zero
    bad = good.copy()
    bad[_L4_ROW] = -50.0 * abs(good[_L4_ROW])
    model, table = _compiled(_strain_from_coef(bad, vary=False))
    flagged = check_stephens_positive(table, model)
    assert len(flagged) == 1 and flagged[0].startswith("phases.0.microstrain")

    diags = _guard_diagnostics(GuardReport(nonpositive_strain=flagged))
    assert [d.code for d in diags] == ["STEPHENS_STRAIN_NOT_POSITIVE"]
    assert diags[0].where == ["phases.0.microstrain"]


def test_out_of_cone_reflections_get_zero_width_not_nan():
    """The masked √ must not poison the pattern: an unphysical σ² is a
    diagnostic, and the peaks it touches simply lose their strain broadening."""
    bad = _brucite_coef(600.0)
    bad[_L4_ROW] = -50.0 * abs(bad[_L4_ROW])
    model, table = _compiled(_strain_from_coef(bad, vary=False))
    y = model.evaluate(table.decode(table.x0()))
    assert np.all(np.isfinite(y))


# ----------------------------------------------------------------------
# injection → recovery
# ----------------------------------------------------------------------
@pytest.mark.parametrize("symbol,cell6", [
    ("P m -3 m", CELLS[0]), ("P -3 m 1", CELLS[1]), ("P 6_3/m", CELLS[2]),
    ("P 1 21/c 1", CELLS[3]), ("P -1", CELLS[4]),
])
def test_dof_magnitudes_stay_above_the_shared_fd_step_floor(symbol, cell6):
    """The 10⁻¹² Å⁻⁴ unit convention exists so that ``h = 1e-6·max(1, |θ|)``
    stays a *relative* step.  Physical Å⁻⁴ values (~10⁻⁸) would be differenced
    with a step 100× their own size, and the columns above would be garbage.
    Checked on the DOFs the optimiser actually sees, over cells from 3 to 13 Å."""
    basis = stephens_basis(symbol).astype(np.float64)
    s = isotropic_coefficients(cell6, microstrain=1000.0)
    coef, *_ = np.linalg.lstsq(basis.T, s, rcond=None)
    assert np.abs(coef).max() > 1.0, symbol


def _lambda(structure) -> dict[tuple[int, int, int], float]:
    """Λ(hkl) of a structure's phase 0, keyed by hkl — the observable the
    injection test compares (the S_HKL themselves are basis-dependent)."""
    phase = structure.phases[0]
    hkl = generate_reflections(phase.space_group, phase.cell.lengths_angles(),
                               1.5406, two_theta_max=120.0).hkl
    lam = strain_width_deg(monomial_matrix(hkl),
                           np.array(phase.microstrain.values()),
                           d_spacings(hkl, *phase.cell.lengths_angles()))
    return {tuple(int(v) for v in h): float(w) for h, w in zip(hkl, lam)}


def _synthetic(structure, inst, *, seed=17) -> PatternData:
    grid = _pattern(15.0, 120.0, 0.02)
    model = compile_model(structure, inst, grid, mode="rietveld")
    table = ParameterTable(structure, inst)
    y = model.evaluate(table.decode(table.x0())) + 40.0
    rng = np.random.default_rng(seed)
    noisy = rng.poisson(np.maximum(y, 1.0) * 20.0) / 20.0
    return PatternData(two_theta=model.tt.tolist(), intensity=noisy.tolist(),
                       sigma=np.sqrt(np.maximum(y, 1.0) / 20.0).tolist())


def _injection_state(coef):
    structure = Structure(phases=[brucite(_strain_from_coef(coef))])
    structure.phases[0].scale.value = 3e-2
    inst = Instrument.debye_scherrer(wavelength=1.5406)
    inst.profile.w.value = 3e-3
    return structure, inst


def test_injected_anisotropy_is_recovered():
    """Inject a 12× broadening of 00l alone, start from the right *isotropic*
    level, and check the refinement finds the direction — the whole model in
    one assertion, and the one that would fail if the basis, the width law or
    the Jacobian were wrong."""
    truth_coef = _brucite_coef(600.0)
    truth_coef[_L4_ROW] *= 12.0
    truth, inst = _injection_state(truth_coef)
    data = _synthetic(truth, inst)
    want = _lambda(truth)

    start, start_inst = _injection_state(_brucite_coef(600.0))
    ref = Refinement(start, start_inst, history=False)
    result = ref.fit(data, plan=RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("microstrain", ["phases.*.microstrain.dof.*"]),
    ]))
    assert result.status == "converged"
    got = _lambda(ref.fitted_structure)

    # the injected direction is found, not just the level
    assert got[(0, 0, 2)] == pytest.approx(want[(0, 0, 2)], rel=0.10)
    assert got[(1, 0, 0)] == pytest.approx(want[(1, 0, 0)], rel=0.10)
    # Λ ∝ √Σ, so scaling the l⁴ pattern 12× separates the two directions by √12
    assert got[(0, 0, 2)] / got[(1, 0, 0)] == pytest.approx(np.sqrt(12.0), rel=0.15)
    weighted = max(abs(got[h] - want[h]) / want[h] for h in want)
    assert weighted < 0.25, weighted

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "stephens_injection_fit.png"))


def test_isotropic_start_does_not_invent_anisotropy():
    """Negative control: a genuinely isotropic specimen must come back
    isotropic.  Λ is one number for every hkl when the S sit on the M² ray, so
    any spurious spread here is the fit reading noise as direction."""
    truth, inst = _injection_state(_brucite_coef(700.0))
    data = _synthetic(truth, inst, seed=23)
    start, start_inst = _injection_state(_brucite_coef(700.0))
    ref = Refinement(start, start_inst, history=False)
    ref.fit(data, plan=RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("microstrain", ["phases.*.microstrain.dof.*"]),
    ]))
    got = np.array(list(_lambda(ref.fitted_structure).values()))
    assert got.std() / got.mean() < 0.15
