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

import numpy as np
import pytest

from pxrdref import Instrument
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
from pxrdref.crystallography.symmetry import get_spacegroup, rotation_matrices
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.structure import (
    Atom,
    Cell,
    Phase,
    StephensStrain,
    Structure,
)

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
