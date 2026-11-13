"""Structure standardization S0: a phase's change of basis and its ITA standard setting.

Verification, not validation: exact operator lists,
per-reflection |F(hkl)|² invariance under every transform (h′ = Pᵀh), round
trips, the published rules' known answers (Parthé & Gelato 1984, *Acta Cryst.*
A40, 169, pp. 172–173), and spglib's ``std_lattice`` with the origin-2 Hall
number as a black-box cross-check.  Fixtures are COD files under
``tests/data`` and synthetic phases built here; no licensed database row.
"""

from __future__ import annotations

import itertools
from fractions import Fraction

import gemmi
import numpy as np
import pytest

from rietx.crystallography import setting as S
from rietx.crystallography.lattice import d_spacings
from rietx.crystallography.representation.subgroups import _from_operations, _standardise
from rietx.crystallography.structure_factor import compile_phase_sites, structure_factors_squared
from rietx.crystallography.symmetry import (
    ita_standard_setting,
    resolve_group,
    restate_in_hexagonal_axes,
)
from rietx.indexing.reduce import reduce_cell
from rietx.schemas.common import Parameter
from rietx.schemas.structure import AnisoU, Atom, Cell, Phase, Structure

DATA = __import__("pathlib").Path(__file__).parent / "data"


# ---------------------------------------------------------------- helpers

def _phase(symbol, cell, sites, *, aniso=False, ops=None):
    atoms = []
    for i, (species, xyz) in enumerate(sites):
        u = None
        if aniso:
            u = AnisoU.from_values((0.011 + 0.001 * i, 0.014, 0.017, 0.002, -0.003, 0.001))
        atoms.append(Atom(label=f"{species}{i + 1}", species=species,
                          x=Parameter(value=xyz[0]), y=Parameter(value=xyz[1]),
                          z=Parameter(value=xyz[2]), occ=Parameter(value=0.9),
                          biso=Parameter(value=0.4 + 0.1 * i), aniso=u))
    return Phase(name="t", space_group=symbol, symmetry_operations=ops,
                 cell=Cell(**{k: Parameter(value=v) for k, v in
                              zip(("a", "b", "c", "alpha", "beta", "gamma"), cell)}),
                 atoms=atoms)


def _six(phase):
    c = phase.cell
    return (c.a.value, c.b.value, c.c.value, c.alpha.value, c.beta.value, c.gamma.value)


def _f2(phase, hkl):
    hkl = np.asarray(hkl, dtype=np.int64)
    sites = compile_phase_sites(phase)
    six = _six(phase)
    xyz = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    occ = np.array([a.occ.value for a in phase.atoms])
    biso = np.array([a.biso.value for a in phase.atoms])
    uaniso, astar = None, None
    if sites.any_aniso:
        from rietx.crystallography.adp import reciprocal_axis_lengths
        uaniso = np.array([a.aniso.values() if a.aniso is not None else (0,) * 6 for a in phase.atoms])
        astar = np.asarray(reciprocal_axis_lengths(*six))
    return np.asarray(structure_factors_squared(hkl, d_spacings(hkl, *six), sites, xyz, occ,
                                                biso, uaniso, astar))


def _hkl_box(n=3):
    return [h for h in itertools.product(range(-n, n + 1), repeat=3) if any(h)]


def _assert_f2_invariant(old, new, P):
    """|F_new(Pᵀh)|² = det(P)²·|F_old(h)|² for every h whose image is integral."""
    Pf = np.array([[float(x) for x in row] for row in S._mat(P)])
    det = float(np.linalg.det(Pf))
    old_h, new_h = [], []
    for h in _hkl_box():
        hp = Pf.T @ np.array(h, dtype=float)
        if np.allclose(hp, np.rint(hp), atol=1e-9):
            old_h.append(h)
            new_h.append(np.rint(hp).astype(int))
    assert len(old_h) > 100
    f_old, f_new = _f2(old, old_h), _f2(new, new_h)
    assert np.max(f_old) > 1.0
    np.testing.assert_allclose(f_new, det ** 2 * f_old, rtol=1e-9, atol=1e-9 * np.max(f_old))


def _ops_key(phase):
    return _from_operations(resolve_group(phase.space_group, phase.symmetry_operations).operations()).key()


def _metric(six):
    from rietx.crystallography.lattice import direct_metric_tensor
    return np.asarray(direct_metric_tensor(*six))


GENERAL = [("Fe", (0.1123, 0.2345, 0.3456)), ("O", (0.4321, 0.0712, 0.8123)),
           ("Si", (0.7311, 0.6122, 0.1891))]
MONO = (5.31, 7.42, 9.87, 90.0, 104.3, 90.0)


# ---------------------------------------------------------------- rule 2: the table

def test_ita_standard_setting_is_rule_two():
    """Parthé & Gelato 1984 p. 172 rule 2(a)-(c): b unique cell choice 1, hexagonal R, origin 2."""
    assert ita_standard_setting(14).xhm() == "P 1 21/c 1"
    assert ita_standard_setting(15).xhm() == "C 1 2/c 1"
    assert ita_standard_setting(167).xhm() == "R -3 c:H"
    assert ita_standard_setting(227).xhm() == "F d -3 m:2"
    assert ita_standard_setting(227, 1).xhm() == "F d -3 m:1"
    assert ita_standard_setting(129).xhm() == "P 4/n m m:2"
    with pytest.raises(ValueError, match="origin_choice"):
        ita_standard_setting(227, 3)
    from rietx.crystallography.superspace.generation import standard_setting
    assert all(standard_setting(n) is ita_standard_setting(n) for n in (2, 14, 48, 146, 227))


def test_enantiomorph_partners_are_itas_eleven_pairs():
    """The computed partners are ITA's eleven enantiomorphic pairs, each found from both ends."""
    pairs = {frozenset((n, S.enantiomorph_partner(n))) for n in range(1, 231)
             if S.enantiomorph_partner(n) is not None}
    assert pairs == {frozenset(p) for p in ((76, 78), (91, 95), (92, 96), (144, 145),
                                            (151, 153), (152, 154), (169, 170), (171, 172),
                                            (178, 179), (180, 181), (212, 213))}
    smaller = {n for p in pairs for n in p
               if S._screw_index(n) < S._screw_index(next(iter(p - {n})))}
    # rule 2(d): P4₁32 (213), not P4₃32 (212); P6₂ (171), not P6₄ (172)
    assert {76, 91, 92, 144, 151, 152, 169, 171, 178, 180, 213} == smaller


def test_standardise_takes_the_setting_by_hall_number():
    """subgroups._standardise: spglib's default is origin choice 1; the Hall argument gives 2."""
    group = _from_operations(gemmi.find_spacegroup_by_name("F d -3 m:1").operations())
    G = np.eye(3) * 81.0
    _, symbol1, (P1, p1) = _standardise(group, G)
    assert symbol1 == "F d -3 m:1" and group.transformed(P1, p1).key() == group.key()
    hall2 = S._hall_number("F d -3 m:2")
    _, symbol2, (P2, p2) = _standardise(group, G, 1, hall_number=hall2)
    target = _from_operations(gemmi.find_spacegroup_by_name("F d -3 m:2").operations())
    assert symbol2 == "F d -3 m:2"
    assert group.transformed(P2, p2).key() == target.key()
    assert all(abs(x) % Fraction(1, 4) == Fraction(1, 8) for x in p2)


# ---------------------------------------------------------------- change of basis

@pytest.mark.parametrize("P, p", [
    (((1, 0, 1), (0, 1, 0), (0, 0, 1)), (0, 0, 0)),                       # a, b, a + c
    (((0, 0, 1), (0, -1, 0), (1, 0, 0)), (Fraction(1, 4), 0, Fraction(1, 2))),
    (((2, 0, 0), (0, 1, 0), (0, 0, 1)), (0, 0, 0)),                       # a supercell
    (((-1, 0, 0), (0, -1, 0), (0, 0, -1)), (0, 0, 0)),                    # the mirror image
])
def test_change_basis_keeps_every_structure_factor(P, p):
    old = _phase("P 1 21/c 1", MONO, GENERAL, aniso=True)
    new = S.change_basis(old, P, p, allow_inversion=True)
    _assert_f2_invariant(old, new, P)
    G_old, Pf = _metric(_six(old)), np.array(P, dtype=float)
    np.testing.assert_allclose(_metric(_six(new)), Pf.T @ G_old @ Pf, rtol=1e-12, atol=1e-10)
    assert [a.label for a in new.atoms] == [a.label for a in old.atoms]
    assert [a.occ.value for a in new.atoms] == [a.occ.value for a in old.atoms]
    assert not any(a.x.vary or a.x.stderr is not None for a in new.atoms)
    det = round(np.linalg.det(Pf))
    assert new.scale.value == pytest.approx(old.scale.value / det ** 2)


def test_change_basis_clears_the_scales_esd_and_expression():
    old = _phase("P 1 21/c 1", MONO, GENERAL)
    old = old.model_copy(update={"scale": old.scale.model_copy(
        update={"stderr": 0.01, "expr": "2 * x"})})
    new = S.change_basis(old, ((2, 0, 0), (0, 1, 0), (0, 0, 1)))
    assert new.scale.value == pytest.approx(old.scale.value / 4)
    assert new.scale.stderr is None and new.scale.expr is None


def test_change_basis_round_trip_is_exact():
    old = _phase("P 1 21/c 1", MONO, GENERAL, aniso=True)
    P, p = ((1, 0, 1), (0, -1, 0), (1, 0, 0)), (Fraction(1, 2), Fraction(1, 4), 0)
    new = S.change_basis(old, P, p)
    Q = S._inv(S._mat(P))
    back = S.change_basis(new, Q, tuple(-x for x in S._mv(Q, tuple(Fraction(v) for v in p))))
    # the intermediate setting is no table entry, so it carried its list, and the list stays
    assert back.space_group == old.space_group and _ops_key(back) == _ops_key(old)
    np.testing.assert_allclose(_six(back), _six(old), rtol=1e-12)
    for a, b in zip(old.atoms, back.atoms):
        d = (np.array([a.x.value, a.y.value, a.z.value]) - [b.x.value, b.y.value, b.z.value] + 0.5) % 1 - 0.5
        assert np.max(np.abs(d)) < 1e-12
        np.testing.assert_allclose(a.aniso.values(), b.aniso.values(), atol=1e-14)


def test_change_basis_names_the_new_setting_or_carries_the_list():
    old = _phase("P 1 21/c 1", MONO, GENERAL)
    swapped = S.change_basis(old, ((0, 0, 1), (0, -1, 0), (1, 0, 0)))
    assert swapped.space_group == "P 1 21/a 1" and swapped.symmetry_operations is None
    doubled = S.change_basis(old, ((1, 0, 0), (0, 1, 0), (0, 0, 3)))
    assert doubled.symmetry_operations is not None
    assert "[unnamed in a,b,3c;0,0,0]" in doubled.space_group
    _assert_f2_invariant(old, doubled, ((1, 0, 0), (0, 1, 0), (0, 0, 3)))


def _gemmi_r_to_h():
    """Q with x_hex = Q·x_rh: gemmi's basis operation of the :R entry, inverted (as restate uses it)."""
    op = gemmi.find_spacegroup_by_name("R -3 c:R").basisop.inverse()
    return tuple(tuple(Fraction(v, op.DEN) for v in row) for row in op.rot)


def test_change_basis_reproduces_restate_in_hexagonal_axes():
    """The general change of basis gives what the R → H special case gives."""
    hexagonal = _phase("R -3 c:H", (5.0355, 5.0355, 13.7471, 90, 90, 120),
                       [("Fe", (0, 0, 0.35530)), ("O", (0.3059, 0, 0.25))])
    Q = _gemmi_r_to_h()
    rhombohedral = S.change_basis(hexagonal, Q)       # x_hex = Q·x_rh
    assert rhombohedral.space_group == "R -3 c:R"
    _assert_f2_invariant(hexagonal, rhombohedral, Q)
    restated, moved = restate_in_hexagonal_axes(rhombohedral, "test")
    assert moved
    ours = S.change_basis(rhombohedral, S._inv(S._mat(Q)))
    assert ours.space_group == restated.space_group
    np.testing.assert_allclose(_six(ours), _six(restated), atol=1e-9)
    np.testing.assert_allclose(_six(ours), _six(hexagonal), atol=1e-9)
    assert ours.scale.value == pytest.approx(restated.scale.value, rel=1e-12)
    for a, b in zip(ours.atoms, restated.atoms):
        d = (np.array([a.x.value, a.y.value, a.z.value]) - [b.x.value, b.y.value, b.z.value] + 0.5) % 1 - 0.5
        assert np.max(np.abs(d)) < 1e-12


def test_change_basis_refuses_by_name():
    old = _phase("P 1 21/c 1", MONO, GENERAL)
    with pytest.raises(ValueError, match="allow_inversion"):
        S.change_basis(old, ((-1, 0, 0), (0, -1, 0), (0, 0, -1)))
    with pytest.raises(ValueError, match="not a lattice translation"):
        S.change_basis(old, ((Fraction(1, 2), 0, 0), (0, 1, 0), (0, 0, 1)))
    with pytest.raises(ValueError, match="singular"):
        S.change_basis(old, ((1, 0, 0), (1, 0, 0), (0, 0, 1)))
    from rietx.schemas.structure import PreferredOrientation
    po = old.model_copy(update={"preferred_orientation": PreferredOrientation(axis=(0, 0, 1))})
    with pytest.raises(ValueError, match="preferred_orientation"):
        S.change_basis(po, ((0, 0, 1), (0, -1, 0), (1, 0, 0)))


def test_change_basis_carries_an_explicit_operation_list_in_order():
    sg = gemmi.find_spacegroup_by_name("P 1 21/c 1")
    listed = [op.triplet() for op in sg.operations()][::-1]
    old = _phase("P 1 21/c 1", MONO, GENERAL, ops=listed)
    new = S.change_basis(old, ((0, 0, 1), (0, -1, 0), (1, 0, 0)))
    assert new.space_group == "P 1 21/a 1"
    assert new.symmetry_operations[-1] == "x,y,z"
    _assert_f2_invariant(old, new, ((0, 0, 1), (0, -1, 0), (1, 0, 0)))


# ---------------------------------------------------------------- rule 2 cases

def _restated(phase, P, p=(0, 0, 0)):
    return S.change_basis(phase, P, p)


def test_pbnm_goes_to_pnma_on_the_cod_fixture():
    """LaMnO₃ (GSAS-II tutorial, Pnma) restated as Pbnm comes back in Pnma with its own cell."""
    pnma = Structure.from_cif(DATA / "gsas2_bt1_lamno3.cif").phases[0]
    pbnm = _restated(pnma, ((0, 1, 0), (0, 0, 1), (1, 0, 0)))
    assert pbnm.space_group == "P b n m"
    r = S.standard_setting(pbnm)
    assert r.symbol == "P n m a" and not r.inverted
    np.testing.assert_allclose(_six(r.phase), _six(pnma), rtol=1e-12)
    assert _ops_key(r.phase) == _ops_key(pnma)
    _assert_f2_invariant(pbnm, r.phase, r.P)


def test_p21n_goes_to_p21c_on_the_cod_fixture():
    """Paracetamol (COD 2104364, P 1 21/n 1): the symbol is rule 2's; the cell keeps β ≥ 90°."""
    ph = Structure.from_cif(DATA / "cod_2104364.cif", aniso=True).phases[0]
    r = S.standard_setting(ph)
    assert r.symbol == "P 1 21/c 1" and r.phase.space_group == "P 1 21/c 1"
    assert r.phase.cell.beta.value >= 90.0
    assert "Parthé & Gelato 1985" in r.cell_rule
    vol = np.sqrt(np.linalg.det(_metric(_six(ph))))
    assert np.sqrt(np.linalg.det(_metric(_six(r.phase)))) == pytest.approx(vol, rel=1e-12)
    _assert_f2_invariant(ph, r.phase, r.P)


def test_origin_choice_one_goes_to_two():
    spinel = _phase("F d -3 m:1", (8.39,) * 3 + (90.0,) * 3,
                    [("Fe", (0.0, 0.0, 0.0)), ("Cr", (0.625, 0.625, 0.625)),
                     ("O", (0.387, 0.387, 0.387))])
    r = S.standard_setting(spinel)
    assert r.symbol == "F d -3 m:2"
    assert all(abs(x) % Fraction(1, 4) == Fraction(1, 8) for x in r.p)
    fe = r.phase.atoms[0]
    assert {round(fe.x.value * 8) % 2, round(fe.y.value * 8) % 2} == {1}   # 8a of origin 2: x = 1/8 + n/4
    _assert_f2_invariant(spinel, r.phase, r.P)
    assert S.standard_setting(spinel, origin_choice=1).symbol == "F d -3 m:1"
    tetragonal = _phase("P 4/n m m:1", (4.0, 4.0, 6.0, 90, 90, 90),
                        [("Fe", (0, 0, 0)), ("Se", (0, 0.5, 0.2668))])
    r = S.standard_setting(tetragonal)
    assert r.symbol == "P 4/n m m:2"
    _assert_f2_invariant(tetragonal, r.phase, r.P)


def test_rhombohedral_axes_go_to_hexagonal():
    hexagonal = _phase("R -3 c:H", (5.0355, 5.0355, 13.7471, 90, 90, 120),
                       [("Fe", (0, 0, 0.35530)), ("O", (0.3059, 0, 0.25))])
    rhombohedral = _restated(hexagonal, ((Fraction(2, 3), Fraction(-1, 3), Fraction(-1, 3)),
                                         (Fraction(1, 3), Fraction(1, 3), Fraction(-2, 3)),
                                         (Fraction(1, 3), Fraction(1, 3), Fraction(1, 3))))
    r = S.standard_setting(rhombohedral)
    assert r.symbol == "R -3 c:H"
    np.testing.assert_allclose(_six(r.phase), _six(hexagonal), rtol=1e-12)
    _assert_f2_invariant(rhombohedral, r.phase, r.P)


def test_centred_triclinic_goes_to_the_niggli_p1bar():
    p1bar = _phase("P -1", (5.1, 6.2, 7.3, 81.0, 76.0, 69.0), GENERAL)
    c1bar = _restated(p1bar, ((1, 1, 0), (-1, 1, 0), (0, 0, 1)))
    assert c1bar.space_group == "C -1"
    r = S.standard_setting(c1bar)
    assert r.symbol == "P -1" and r.cell_rule.startswith("R3a")
    niggli = reduce_cell(_six(p1bar)).cell
    np.testing.assert_allclose(_six(r.phase), niggli, rtol=1e-9)
    _assert_f2_invariant(c1bar, r.phase, r.P)


def test_larger_screw_enantiomorph_is_inverted():
    """Rule 2(d) and p. 174: P3₂21 is standardized in P3₁21 as its mirror image, recorded."""
    quartz = _phase("P 32 2 1", (4.916, 4.916, 5.4054, 90, 90, 120),
                    [("Si", (0.4697, 0.0, 2 / 3)), ("O", (0.4135, 0.2669, 0.7858))])
    r = S.standard_setting(quartz)
    assert r.inverted and r.symbol == "P 31 2 1"
    assert r.transform_text == "-a,-b,-c;0,0,0"
    for a, b in zip(quartz.atoms, r.phase.atoms):
        d = (np.array([a.x.value, a.y.value, a.z.value]) + [b.x.value, b.y.value, b.z.value] + 0.5) % 1 - 0.5
        assert np.max(np.abs(d)) < 1e-12
    _assert_f2_invariant(quartz, r.phase, r.P)
    kept = S.standard_setting(quartz, smaller_screw=False)
    assert not kept.inverted and kept.symbol == "P 32 2 1"


# ---------------------------------------------------------------- rule 3

def test_triclinic_cell_is_niggli():
    ph = _phase("P 1", (9.1, 5.2, 7.3, 99.0, 104.0, 111.0), GENERAL)
    r = S.standard_setting(ph)
    red = reduce_cell(_six(r.phase))
    assert red.already_reduced
    a, b, c = _six(r.phase)[:3]
    assert a <= b <= c
    _assert_f2_invariant(ph, r.phase, r.P)


def test_monoclinic_p_without_glide_gets_the_reset_cell():
    ph = _phase("P 1 21 1", (9.87, 7.42, 5.31, 90.0, 75.7, 90.0), GENERAL)
    tilted = _restated(ph, ((1, 0, 0), (0, 1, 0), (1, 0, 1)))
    r = S.standard_setting(tilted)
    assert r.cell_rule.startswith("R3b: reset")
    a, _, c, _, beta, _ = _six(r.phase)
    assert (a, c, beta) == pytest.approx((5.31, 9.87, 104.3), abs=1e-9)
    _assert_f2_invariant(tilted, r.phase, r.P)


@pytest.mark.parametrize("symbol, n", [("P 21 21 21", 6), ("P m m m", 6), ("P n m a", 1),
                                       ("C m c m", 1), ("C m m m", 2), ("P b c a", 3),
                                       ("F d d d:2", 6), ("I b a m", 2), ("P 21 21 2", 2)])
def test_orthorhombic_relabellings_from_the_normaliser(symbol, n):
    """Rule 3(c): six relabellings for a cubic affine normaliser, two for a tetragonal one."""
    found = S.orthorhombic_relabellings(symbol)
    assert len(found) == n
    assert found[0][0] == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    key = _from_operations(gemmi.find_spacegroup_by_name(symbol).operations()).key()
    group = _from_operations(gemmi.find_spacegroup_by_name(symbol).operations())
    for P, p in found:
        assert S._det(P) == 1 and group.transformed(P, p).key() == key


def test_orthorhombic_cell_is_ordered_where_the_normaliser_allows():
    ph = _phase("P 21 21 21", (7.1, 9.2, 5.3, 90, 90, 90), GENERAL)
    r = S.standard_setting(ph)
    assert _six(r.phase)[:3] == pytest.approx((5.3, 7.1, 9.2))
    _assert_f2_invariant(ph, r.phase, r.P)
    ph = _phase("C m m m", (9.2, 7.1, 5.3, 90, 90, 90), GENERAL)
    r = S.standard_setting(ph)
    assert r.symbol == "C m m m" and _six(r.phase)[:3] == pytest.approx((7.1, 9.2, 5.3))
    ph = _phase("P b c a", (9.2, 5.3, 7.1, 90, 90, 90), GENERAL)
    r = S.standard_setting(ph)
    assert r.symbol == "P b c a" and _six(r.phase)[:3] == pytest.approx((5.3, 7.1, 9.2))
    ph = _phase("P n m a", (9.2, 5.3, 7.1, 90, 90, 90), GENERAL)
    assert _six(S.standard_setting(ph).phase)[:3] == pytest.approx((9.2, 5.3, 7.1))


# Parthé & Gelato (1985) Acta Cryst. A41, 142: the best cell for cell choice 1.  Their three
# demonstrations (p. 147): input cell, best cell, the pqrs t of the one-step matrix
# (a' = pa + qc, b' = tb, c' = ra + sc), and the origin shift of Table 2 added to the
# transformed coordinates (x'' = P⁻¹x + s, so p = -P·s in the module's convention).
PG1985_DEMOS = [
    pytest.param("C 1 2/c 1", (25.04, 3.935, 29.53, 90, 122.0, 90), (25.04, 3.935, 26.746, 110.56),
                 (-1, 0, 1, 1, -1), (Fraction(1, 4), Fraction(1, 4), 0), id="chlorobenzophenone-C2/c"),
    pytest.param("C 1 c 1", (16.27, 5.632, 13.23, 90, 134.8, 90), (16.27, 5.632, 11.68, 126.5),
                 (-1, 0, 1, 1, -1), (0, Fraction(1, 4), 0), id="afwillite-Cc"),
    pytest.param("P 1 2/c 1", (8.96, 4.49, 14.62, 90, 145.43, 90), (8.85, 4.49, 10.17, 124.30),
                 (-1, -1, 2, 1, 1), (0, 0, 0), id="sylvanite-P2/c"),
]


def _pqrst(P):
    return (P[0][0], P[2][0], P[0][2], P[2][2], P[1][1])


@pytest.mark.parametrize("symbol, cell, best, pqrst, shift", PG1985_DEMOS)
def test_monoclinic_best_cell_is_the_papers_demonstration(symbol, cell, best, pqrst, shift):
    """PG 1985 p. 147: the matrix (Figs. 3(a), 4(a)), the best cell and Table 2's origin shift, as printed."""
    ph = _phase(symbol, cell, GENERAL, aniso=True)
    r = S.standard_setting(ph)
    assert r.symbol == symbol and r.cell_rule.startswith("R3b: best cell")
    assert _pqrst(r.P) == pqrst
    assert all(r.P[i][j] == 0 for i, j in ((0, 1), (1, 0), (1, 2), (2, 1)))
    s = tuple(Fraction(x) for x in shift)
    assert r.p == tuple(-x for x in S._mv(r.P, s))
    a, b, c, _, beta, _ = _six(r.phase)
    assert (a, b, c) == pytest.approx(best[:3], abs=0.006)
    assert beta == pytest.approx(best[3], abs=0.01)
    _assert_f2_invariant(ph, r.phase, r.P)
    again = S.standard_setting(r.phase)
    assert again.P == S._mat(S._I3) and all(x == 0 for x in again.p)


def test_monoclinic_framed_matrix_needs_its_origin_shift():
    """Table 1 (p. 146): for Cc and C2/c a matrix with r odd keeps the symbol only with the shift."""
    for symbol in ("C 1 c 1", "C 1 2/c 1"):
        group = _from_operations(gemmi.find_spacegroup_by_name(symbol).operations())
        P = S._mat(((-1, 0, 1), (0, -1, 0), (0, 0, 1)))
        assert group.transformed(P, S._zero()).key() != group.key()
        assert group.transformed(P, S._origin_keeping(symbol, P)).key() == group.key()
    group = _from_operations(gemmi.find_spacegroup_by_name("C 1 2/m 1").operations())
    assert group.transformed(P, S._zero()).key() == group.key()   # no glide: no shift (Table 1)


@pytest.mark.parametrize("symbol, cell, best", [
    pytest.param("I 1 a 1", (11.68, 5.632, 13.23, 90, 98.7, 90), ("C 1 c 1", 16.27, 5.632, 11.68, 126.5),
                 id="afwillite-Ia-cell-choice-3"),
    pytest.param("P 1 2/n 1", (8.85, 4.49, 8.96, 90, 110.36, 90), ("P 1 2/c 1", 8.85, 4.49, 10.17, 124.30),
                 id="sylvanite-P2/n-cell-choice-2"),
])
def test_monoclinic_other_cell_choices_reach_the_same_best_cell(symbol, cell, best):
    """PG 1985 p. 150 (footnote): the fully reduced cells of two demonstrations, in cell choices 3 and 2."""
    ph = _phase(symbol, cell, GENERAL)
    r = S.standard_setting(ph)
    assert r.symbol == best[0]
    a, b, c, _, beta, _ = _six(r.phase)
    assert (a, b, c) == pytest.approx(best[1:4], abs=0.006)
    assert beta == pytest.approx(best[4], abs=0.02)
    _assert_f2_invariant(ph, r.phase, r.P)


def _orbit(phase, xyz):
    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    return [np.array(op.apply_to_xyz(list(xyz))) % 1.0 for op in sg.operations()]


def test_monoclinic_sc2fesi2_reduced_a_cell_goes_to_the_best_c_cell():
    """PG 1985 Table 3 (p. 151), ref. (a): A 1 2/m 1 (cell choice 2) to C 1 2/m 1 with a > c, all sites 4(i).

    Atoms agree with the paper's best-cell column up to their own orbit and one origin
    shift of C2/m's normaliser (0 or ½ along each axis), the choice rule 4 (S1) makes.
    """
    a_cell = [("Sc", (0.1731, 0, 0.0002)), ("Sc", (0.6077, 0, 0.1856)), ("Fe", (0.1305, 0, 0.2720)),
              ("Si", (0.0652, 0, 0.6433)), ("Si", (0.3766, 0, 0.5109))]
    c_cell = [(-0.0002, 0, 0.3269), (0.1856, 0, 0.1077), (0.2720, 0, 0.6305), (0.3567, 0, 0.4348),
              (0.4891, 0, 0.1234)]
    ph = _phase("A 1 2/m 1", (9.414, 3.9912, 9.916, 90, 118.15, 90), a_cell)
    r = S.standard_setting(ph)
    assert r.symbol == "C 1 2/m 1"
    assert _six(r.phase) == pytest.approx((9.916, 3.9912, 9.414, 90, 118.15, 90), abs=1e-9)
    group = _from_operations(gemmi.find_spacegroup_by_name("C 1 2/m 1").operations())
    shifts = [d for d in itertools.product((0, Fraction(1, 2)), repeat=3)
              if group.transformed(S._mat(S._I3), d).key() == group.key()]
    assert len(shifts) == 8

    def matches(d):
        for atom, want in zip(r.phase.atoms, c_cell):
            x = np.array([atom.x.value, atom.y.value, atom.z.value]) - np.array([float(v) for v in d])
            if not any(np.max(np.abs((y - np.array(want) + 0.5) % 1 - 0.5)) < 2e-4 for y in _orbit(r.phase, x)):
                return False
        return True

    assert any(matches(d) for d in shifts)
    _assert_f2_invariant(ph, r.phase, r.P)


@pytest.mark.parametrize("centred", [False, True])
def test_monoclinic_best_cell_is_the_shortest_the_symbol_allows(centred):
    """Brute force over every basis with entries in [-6, 6] that keeps the symbol (Table 1 parities)."""
    rng = np.random.default_rng(1985 + centred)
    allowed = []
    for p, q, r_, s in itertools.product(range(-6, 7), repeat=4):
        if abs(p * s - q * r_) == 1 and ((q % 2 == 0 and s % 2 == 1) if centred else (p % 2 == 1 and r_ % 2 == 0)):
            allowed.append((p, q, r_, s))
    M = np.array(allowed)
    for _ in range(300):
        six = (rng.uniform(3, 15), 6.0, rng.uniform(3, 15), 90.0, rng.uniform(90.5, 165.0), 90.0)
        G = _metric(six)
        P = S._best_monoclinic(G, centred)
        p, q, r_, s, t = _pqrst(P)
        assert abs(t) == 1 and S._det(P) == 1 and s > 0
        assert (q % 2 == 0 and s % 2 == 1) if centred else (p % 2 == 1 and r_ % 2 == 0)
        Pf = np.array([[float(x) for x in row] for row in P])
        Gp = Pf.T @ G @ Pf
        assert Gp[0, 2] <= 1e-9                                   # beta' non-acute
        G2 = G[np.ix_((0, 2), (0, 2))]
        la = np.einsum("ni,ij,nj->n", M[:, :2], G2, M[:, :2]).min()
        lc = np.einsum("ni,ij,nj->n", M[:, 2:], G2, M[:, 2:]).min()
        assert Gp[0, 0] <= la + 1e-7 and Gp[2, 2] <= lc + 1e-7


def test_monoclinic_best_cell_round_trips():
    ph = _phase("C 1 2/c 1", (25.04, 3.935, 29.53, 90, 122.0, 90), GENERAL, aniso=True)
    r = S.standard_setting(ph)
    Pinv = S._inv(r.P)
    back = S.change_basis(r.phase, Pinv, tuple(-x for x in S._mv(Pinv, r.p)))
    np.testing.assert_allclose(_six(back), _six(ph), atol=1e-12)
    for x, y in zip(back.atoms, ph.atoms):
        d = np.array([x.x.value - y.x.value, x.y.value - y.y.value, x.z.value - y.z.value])
        assert np.max(np.abs((d + 0.5) % 1 - 0.5)) < 1e-12
        np.testing.assert_allclose(x.aniso.values(), y.aniso.values(), atol=1e-12)


# ---------------------------------------------------------------- the whole step

FIXTURES = ["cod_1000236.cif", "cod_1000055.cif", "cod_9003308.cif", "fluorapatite.cif",
            "gsas2_bt1_lamno3.cif", "cod_2104364.cif", "cod_4003235.cif", "cod_9007744.cif",
            "cod_1567181.cif"]


@pytest.mark.parametrize("name", FIXTURES)
def test_standard_setting_is_idempotent_and_keeps_f2(name):
    ph = Structure.from_cif(DATA / name).phases[0]
    r = S.standard_setting(ph)
    assert r.phase.space_group == r.symbol == ita_standard_setting(r.number).xhm()
    _assert_f2_invariant(ph, r.phase, r.P)
    again = S.standard_setting(r.phase)
    assert again.P == S._mat(S._I3) and all(x == 0 for x in again.p)


@pytest.mark.parametrize("name", FIXTURES)
def test_spglib_std_lattice_with_the_origin_two_hall_agrees(name):
    """Black box: spglib's std_lattice in the same setting is our cell, or the same lattice."""
    import spglib

    ph = Structure.from_cif(DATA / name).phases[0]
    r = S.standard_setting(ph)
    sg = resolve_group(ph.space_group, ph.symmetry_operations)
    lattice = np.linalg.cholesky(_metric(_six(ph)))
    positions, numbers = [], []
    for k, atom in enumerate(ph.atoms):
        x0 = np.array([atom.x.value, atom.y.value, atom.z.value])
        seen = []
        for op in sg.operations():
            y = (np.array(op.rot, dtype=float) / op.DEN @ x0 + np.array(op.tran, dtype=float) / op.DEN) % 1
            if not any(np.max(np.abs((y - s + 0.5) % 1 - 0.5)) < 1e-4 for s in seen):
                seen.append(y)
        positions += seen
        numbers += [k + 1] * len(seen)
    data = spglib.get_symmetry_dataset((lattice, positions, numbers), symprec=1e-3,
                                       hall_number=S._hall_number(r.symbol))
    assert data is not None and int(data.number) == r.number
    Gs = np.asarray(data.std_lattice) @ np.asarray(data.std_lattice).T
    Go = _metric(_six(r.phase))
    if not np.allclose(Gs, Go, rtol=1e-6, atol=1e-6):
        assert np.sqrt(np.linalg.det(Gs)) == pytest.approx(np.sqrt(np.linalg.det(Go)), rel=1e-6)
        red_s = reduce_cell(tuple(np.r_[np.sqrt(np.diag(Gs)), [
            np.degrees(np.arccos(Gs[i, j] / np.sqrt(Gs[i, i] * Gs[j, j]))) for i, j in ((1, 2), (0, 2), (0, 1))]]))
        np.testing.assert_allclose(red_s.cell, reduce_cell(_six(r.phase)).cell, rtol=1e-6)
