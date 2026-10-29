"""(3+1)D magnetic superspace groups: θ, {1′|000½}, the groups over a
superspace group, their symbols (WP-1992, N-W2's group half).

Every pin is printed, with its page, and none comes from the ISO(3+d)D tables
(which may not be redistributed, and were not opened):

* Stokes & Campbell (2022), *Acta Cryst.* A**78**, 364: Table 1 (p. 366, the
  primings of P222(0,0,γ)000: 8 tried, 4 "none", 3 groups), Table 2 (p. 366,
  16 anti-translations, 9 inequivalent, with the printed equivalences), Table
  3 (p. 367, I222(0,0,γ)000: 16 tried, 8 "none", 6 groups), the p. 365
  example P222.1′_I(0,0,γ)00s0 and Fig. 4 (p. 369, the group only:
  20.1.15.3.m34.2 A2₁′2′2(0,0,γ)000);
* Perez-Mato, Ribeiro, Petříček & Aroyo (2012), *J. Phys.: Condens. Matter*
  **24**, 163201: Table 1 (manuscript p. 8, the four cards of
  P-11′(αβγ)0s), eq. (20) and the parity consequence (p. 17);
* the symbol grammar with one phase letter per generator plus one for 1′
  (Stokes & Campbell 2022 p. 366; Campbell, Stokes, Perez-Mato &
  Rodríguez-Carvajal 2022, *Acta Cryst.* A**78**, 99, § 3).
"""

from __future__ import annotations

from fractions import Fraction as F

import pytest

from rietx.crystallography.representation.order_parameter import ORDER_PARAMETER_KINDS
from rietx.crystallography.superspace import (
    IDENTITY,
    IDENTITY_PRIME,
    N_MAGNETIC_SUPERSPACE_GROUPS_D1,
    N_MAGNETIC_SUPERSPACE_TYPES_D1,
    SuperspaceGroup,
    SuperspaceOperator,
    equivalent,
    family,
    magnetic_canonical_key,
    magnetic_superspace_groups,
    magnetic_symbol,
    maximal_subgroup,
    parse_symbol,
    superspace_groups,
    symbol,
)
from rietx.crystallography.superspace.magnetic import (
    _space_counts,
    anti_translation_candidates,
    count_magnetic_superspace_groups,
    primed_candidates,
    theta_of,
)

H, Q = F(1, 2), F(1, 4)


@pytest.fixture(scope="module")
def p222():
    return parse_symbol("P222(0,0,γ)000")


@pytest.fixture(scope="module")
def i222():
    return parse_symbol("I222(0,0,γ)000")


def _classes(pairs):
    """The partition of the candidates' keys into equivalence classes."""
    by_key: dict = {}
    for key, g in pairs:
        by_key.setdefault(magnetic_canonical_key(g), set()).add(key)
    return {frozenset(v) for v in by_key.values()}


# ---------------------------------------------------------------------------
# θ on the operator
# ---------------------------------------------------------------------------
def test_theta_composes_as_the_product_and_survives_inverse_and_strings():
    a = SuperspaceOperator.from_xyz("-x1,x2,-x3+1/2,-x4,-1")
    b = SuperspaceOperator.from_xyz("x1+1/2,-x2,-x3,-x4,-1")
    assert (a * b).theta == 1 and (a * a).theta == 1
    assert (a * IDENTITY).theta == -1
    assert a.inverse().theta == -1 and (a * a.inverse()) == IDENTITY
    assert a.xyz() == "-x1,x2,-x3+1/2,-x4,-1"
    assert IDENTITY.xyz() == "x1,x2,x3,x4"                   # N-W1's form unchanged
    assert IDENTITY.xyz(magnetic=True) == "x1,x2,x3,x4,+1"   # magCIF's
    assert a != a.prime() and a.prime().prime() == a
    assert hash(a) != hash(a.prime())


def test_theta_outside_plus_minus_one_is_refused():
    with pytest.raises(ValueError, match="theta"):
        SuperspaceOperator(IDENTITY.rotation, IDENTITY.translation, 1, (0, 0, 0), F(0), 0)
    with pytest.raises(ValueError, match="theta"):
        SuperspaceOperator(IDENTITY.rotation, IDENTITY.translation, 1, (0, 0, 0), F(0), 2)


def test_pure_time_reversal_and_the_internal_half_translation_are_distinct():
    """(1′|0000) and (1|000½) are distinct operations even where a first-
    harmonic model cannot tell them apart (Perez-Mato 2012 p. 17)."""
    shift = SuperspaceOperator.from_xyz("x1,x2,x3,x4+1/2")
    assert IDENTITY_PRIME != shift
    assert IDENTITY_PRIME.is_anti_translation and shift.is_translation
    g = parse_symbol("P222(0,0,γ)000")
    assert not equivalent(g.grey(), g.with_time_reversal_shift())


# ---------------------------------------------------------------------------
# the group: θ in the closure
# ---------------------------------------------------------------------------
def test_g_with_both_signs_and_no_1prime_is_refused_or_read_as_grey():
    """Planted: {2z|0}, θ = +1 and θ = −1 together.  Given as representatives
    it is refused ("one per point operation"); closed from generators it
    contains 1′ and is read as the grey group."""
    two = SuperspaceOperator.from_xyz("-x1,-x2,x3,x4")
    with pytest.raises(ValueError, match="one per point operation"):
        SuperspaceGroup.from_operations("(0,0,γ)", [two])  # positive arm: fine
        SuperspaceGroup(SuperspaceGroup.from_operations("(0,0,γ)", [two]).q,
                        (IDENTITY, two, two.prime()))
    g = SuperspaceGroup.from_operations("(0,0,γ)", [two, two.prime()])
    assert IDENTITY_PRIME in g.centerings and g.magnetic_type == 2


def test_closure_compares_theta():
    """A set whose products need (2z, θ = +1) but which lists (2z, θ = −1)
    without 1′ does not close: N-W1's reduction would have merged them."""
    two_x = SuperspaceOperator.from_xyz("x1,-x2,-x3,-x4")
    two_y = SuperspaceOperator.from_xyz("-x1,x2,-x3,-x4")
    two_z = SuperspaceOperator.from_xyz("-x1,-x2,x3,x4")
    q = parse_symbol("P222(0,0,γ)000").q
    SuperspaceGroup(q, (IDENTITY, two_x, two_y.prime(), two_z.prime()))  # P22′2′
    with pytest.raises(ValueError, match="do not close"):
        SuperspaceGroup(q, (IDENTITY, two_x, two_y, two_z.prime()))


def test_magnetic_strings_round_trip(p222):
    g = magnetic_superspace_groups(p222, types=(4,))[0]
    again = SuperspaceGroup.from_operations(g.q, list(g.xyz()))
    assert set(again.all_operations()) == set(g.all_operations())
    assert all(x.endswith((",+1", ",-1")) for x in g.xyz())


# ---------------------------------------------------------------------------
# Stokes & Campbell 2022 Tables 1-3
# ---------------------------------------------------------------------------
def test_table1_p222_primings(p222):
    rows = primed_candidates(p222)
    assert len(rows) == 8
    none = {signs for signs, g in rows if g is None}
    # 2'22, 22'2, 222' and 2'2'2' are "none"
    assert none == {(-1, 1, 1), (1, -1, 1), (1, 1, -1), (-1, -1, -1)}
    got = magnetic_superspace_groups(p222, types=(1, 3))
    assert [g.symbol for g in got] == [
        "P222.1(0,0,γ)000", "P22'2'(0,0,γ)000", "P2'2'2(0,0,γ)000"]


def test_table1_p22p2p_and_p2p2p2_differ_because_q_is_along_z(p222):
    g = {signs: x for signs, x in primed_candidates(p222) if x is not None}
    assert equivalent(g[(1, -1, -1)], g[(-1, 1, -1)])        # P22′2′ ≡ P2′22′
    assert not equivalent(g[(1, -1, -1)], g[(-1, -1, 1)])    # P22′2′ ≢ P2′2′2


def test_planted_theta_dropped_from_one_generator_changes_the_count(p222):
    """Negative control with its positive arm.  Positive: the enumerator
    finds three groups (above).  Planted: the prime on the z two-fold dropped
    — P22′2′ cannot be built and the count falls to two."""
    classes = {}
    for signs, g in primed_candidates(p222):
        if g is None:
            continue
        rotations = {o.rotation: o for o in g.operations}
        z = ((-1, 0, 0), (0, -1, 0), (0, 0, 1))
        rotations[z] = rotations[z].unprimed()
        try:
            bad = SuperspaceGroup(g.q, tuple(rotations.values()), g.centerings)
        except ValueError:
            continue
        key = magnetic_canonical_key(bad) if bad.is_magnetic else ("type1",)
        classes[key] = signs
    assert len(classes) == 2


def test_planted_bmsg_only_comparison_collapses_the_q_distinction(p222):
    """Planted: compare MSSGs by the family plus the multiset of primes
    (what a 3D-only comparison sees).  P22′2′ and P2′2′2 then collapse —
    the distinction Table 1 prints exists only because θ is compared on the
    operators with q."""
    from rietx.crystallography.superspace import canonical_key

    keys = set()
    for _, g in primed_candidates(p222):
        if g is not None:
            keys.add((canonical_key(family(g)),
                      tuple(sorted(o.theta for o in g.operations))))
    assert len(keys) == 2 and len(magnetic_superspace_groups(p222, types=(1, 3))) == 3


#: Table 2 (p. 366): the sixteen v and the classes it prints ("equivalent to").
TABLE2_CLASSES = {
    frozenset({(0, 0, 0, 0)}),                                        # m2.1
    frozenset({(H, 0, 0, 0), (0, H, 0, 0)}),                          # m4.1
    frozenset({(0, 0, H, 0), (0, 0, H, H)}),                          # m4.2
    frozenset({(0, H, H, 0), (H, 0, H, 0), (0, H, H, H), (H, 0, H, H)}),  # m5.2
    frozenset({(H, H, 0, 0)}),                                        # m5.1
    frozenset({(H, H, H, 0), (H, H, H, H)}),                          # m6.1
    frozenset({(0, 0, 0, H)}),                                        # m2.2
    frozenset({(H, 0, 0, H), (0, H, 0, H)}),                          # m4.3
    frozenset({(H, H, 0, H)}),                                        # m5.3
}


def test_table2_p222_anti_translations(p222):
    rows = anti_translation_candidates(p222)
    assert len(rows) == 16 and all(g is not None for _, g in rows)
    got = _classes((tuple(F(x) for x in v), g) for v, g in rows)
    want = {frozenset(tuple(F(x) for x in v) for v in c) for c in TABLE2_CLASSES}
    assert got == want and len(got) == 9
    syms = [g.symbol for g in magnetic_superspace_groups(p222, types=(2, 4))]
    assert len(syms) == 9 and "P222.1'(0,0,γ)0000" in syms and "P222.1'(0,0,γ)000s" in syms


#: Table 3 (p. 367), v in the I-centred SSG's coordinates.
TABLE3_NONE = {(3 * Q, Q, Q), (Q, 3 * Q, Q), (Q, Q, 3 * Q), (Q, Q, Q)}
TABLE3_CLASSES = {
    frozenset({(0, 0, 0, 0)}),                       # m50.1
    frozenset({(H, 0, 0, 0), (0, H, 0, 0)}),         # m52.2
    frozenset({(0, 0, H, 0)}),                       # m52.1
    frozenset({(0, 0, 0, H)}),                       # m50.2
    frozenset({(H, 0, 0, H), (0, H, 0, H)}),         # m52.4
    frozenset({(0, 0, H, H)}),                       # m52.3
}


def _mod_i(v):
    """v modulo the I lattice: the representative printed in Table 3."""
    cands = [tuple((v[i] + c) % 1 for i, c in enumerate(t)) + (v[3] % 1,)
             for t in ((0, 0, 0), (H, H, H))]
    printed = {tuple(F(x) for x in c) for cl in TABLE3_CLASSES for c in cl}
    hit = [c for c in cands if c in printed]
    return hit[0] if hit else min(cands)


def test_table3_i222_anti_translations(i222):
    rows = anti_translation_candidates(i222)
    assert len(rows) == 16
    none = [v for v, g in rows if g is None]
    assert len(none) == 8
    # the 'none' rows are the ones with quarter components, both v₄
    ext = {tuple(min(((v[i] + t) % 1 for t in (0,)), default=0) for i in range(3))
           for v in none}
    i_equiv = {tuple(sorted({tuple((e[i] + t) % 1 for i in range(3)) for t in (0, H)}))
               for e in ext}
    want = {tuple(sorted({tuple((F(e[i]) + t) % 1 for i in range(3)) for t in (0, H)}))
            for e in TABLE3_NONE}
    assert i_equiv == want
    got = _classes((_mod_i(v), g) for v, g in rows if g is not None)
    assert got == {frozenset(tuple(F(x) for x in c) for c in cl) for cl in TABLE3_CLASSES}
    assert len(magnetic_superspace_groups(i222, types=(2, 4))) == 6


def test_p365_example_family_and_maximal_subgroup():
    """P222.1′_I(0,0,γ)00s0: the anti-translation (½,½,½,0)′ becomes a lattice
    translation in F (I222(0,0,γ)00s) and is dropped in X (P222(0,0,γ)00s),
    Stokes & Campbell 2022 p. 365."""
    g = parse_symbol("P222.1'_I(0,0,γ)00s0")
    assert g.magnetic_type == 4
    anti = [c for c in g.centerings if c.is_anti_translation]
    assert [(a.translation, a.delta) for a in anti] == [((H, H, H), F(0))]
    assert symbol(family(g)) == "I222(0,0,γ)00s"
    assert symbol(maximal_subgroup(g)) == "P222(0,0,γ)00s"
    assert symbol(g) == "P222.1'_I(0,0,γ)00s0"


# ---------------------------------------------------------------------------
# Stokes & Campbell 2022 Fig. 4, the group only
# ---------------------------------------------------------------------------
FIG4_GENERATORS = ["(x+1/2,-y,-z,-t)'", "(-x,y,-z,-t)'", "(-x+1/2,-y,z,t)", "x,y+1/2,z+1/2,t"]


def test_fig4_a21p2p2_closes_and_is_generated_over_its_family():
    g = SuperspaceGroup.from_operations("(0,0,γ)", FIG4_GENERATORS)
    assert len(g) == 8 and len(g.operations) == 4 and len(g.centerings) == 2
    assert g.magnetic_type == 3
    assert {(c.translation, c.delta) for c in g.centerings} == {
        ((0, 0, 0), 0), ((0, H, H), 0)}
    assert theta_of(g) == {
        ((1, 0, 0), (0, 1, 0), (0, 0, 1)): 1, ((1, 0, 0), (0, -1, 0), (0, 0, -1)): -1,
        ((-1, 0, 0), (0, 1, 0), (0, 0, -1)): -1, ((-1, 0, 0), (0, -1, 0), (0, 0, 1)): 1}
    assert magnetic_symbol(g) == "A2_1'2'2(0,0,γ)000"
    hits = [m for m in magnetic_superspace_groups(family(g), types=(3,)) if equivalent(m, g)]
    assert len(hits) == 1
    assert equivalent(parse_symbol("A2_1'2'2(0,0,γ)000"), g)


# ---------------------------------------------------------------------------
# Perez-Mato 2012: eq. (20), Table 1 and the parity rule
# ---------------------------------------------------------------------------
def test_perez_mato_table1_p_1_1prime_cards():
    """Table 1 (manuscript p. 8), P-11′(αβγ)0s: {1|0000} +m, {-1|0000} +m,
    {1′|000½} −m, {-1′|000½} −m."""
    g = parse_symbol("P-1(α,β,γ)0").with_time_reversal_shift()
    assert set(g.xyz()) == {"x1,x2,x3,x4,+1", "-x1,-x2,-x3,-x4,+1",
                            "x1,x2,x3,x4+1/2,-1", "-x1,-x2,-x3,-x4+1/2,-1"}
    assert symbol(g) == "P-1.1'(α,β,γ)0s"
    assert equivalent(parse_symbol("P-1.1'(α,β,γ)0s"), g)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_time_reversal_shift_keeps_odd_moment_and_even_displacive_harmonics(n):
    """{1′|000½} multiplies the n-th harmonic of a moment by θe^{iπn} =
    −(−1)ⁿ and of a displacement by (−1)ⁿ (Perez-Mato 2012 p. 17)."""
    op = SuperspaceOperator.from_xyz("x1,x2,x3,x4+1/2,-1")
    assert op.harmonic_factor(n, kind="magnetic") == -((-1) ** n)
    assert op.harmonic_factor(n, kind="displacive") == (-1) ** n
    # so invariance keeps odd moment and even displacive harmonics only
    assert (op.harmonic_factor(n, kind="magnetic") == 1) == (n % 2 == 1)
    # positive arm: pure time reversal kills every moment harmonic, no displacive one
    assert IDENTITY_PRIME.harmonic_factor(n, kind="magnetic") == -1
    assert IDENTITY_PRIME.harmonic_factor(n, kind="displacive") == 1


def test_harmonic_factor_kinds_are_order_parameter_kinds():
    assert set(ORDER_PARAMETER_KINDS) == {"magnetic", "displacive"}
    with pytest.raises(ValueError, match="moves the site"):
        SuperspaceOperator.from_xyz("-x1,x2,x3,x4").harmonic_factor(1, kind="magnetic")


def test_with_time_reversal_shift_is_in_the_operator_list(p222):
    g = p222.with_time_reversal_shift()
    shift = SuperspaceOperator.from_xyz("x1,x2,x3,x4+1/2,-1")
    assert shift in g.all_operations() and IDENTITY_PRIME not in g.all_operations()
    assert g.magnetic_type == 4 and symbol(g) == "P222.1'(0,0,γ)000s"


# ---------------------------------------------------------------------------
# the symbol grammar (edit 15)
# ---------------------------------------------------------------------------
def test_000s_is_not_read_as_0000():
    """One phase letter per generator plus one for 1′: "000s" is {1′|000½}
    over P222(0,0,γ)000, "0000" is the grey group, and a parser with one
    letter per generator (three) builds the wrong type."""
    s = parse_symbol("P222.1'(0,0,γ)000s")
    z = parse_symbol("P222.1'(0,0,γ)0000")
    assert s.magnetic_type == 4 and z.magnetic_type == 2
    assert not equivalent(s, z)
    assert symbol(s) == "P222.1'(0,0,γ)000s" and symbol(z) == "P222.1'(0,0,γ)0000"
    with pytest.raises(ValueError, match="plus one for 1'"):
        parse_symbol("P222.1'(0,0,γ)000")


@pytest.mark.parametrize("text", [
    "P222.1(0,0,γ)000", "P22'2'(0,0,γ)000", "P2'2'2(0,0,γ)000",
    "P222.1'(0,0,γ)0000", "P222.1'_a(0,0,γ)0000", "P222.1'_c(0,0,γ)0000",
    "P222.1'_C(0,0,γ)0000", "P222.1'_I(0,0,γ)0000", "P222.1'_a(0,0,γ)000s",
    "P222.1'_C(0,0,γ)000s", "I222.1'_c(0,0,γ)000s", "A2_1'2'2(0,0,γ)000",
])
def test_symbols_round_trip(text):
    g = parse_symbol(text)
    assert g.symbol == text
    assert symbol(g) == text or (g.magnetic_type is None and text.endswith("000"))


@pytest.mark.parametrize("space_group, q", [
    ("C 2 2 21", "(1,0,γ)"),      # q → q + (0,0,1) shifts v4 by ½
    ("P 2", "(0,β,1/2)"),         # a 3D origin shift moves an ε = +1 δ
    ("A m m 2", "(1/2,0,γ)"),
])
def test_type4_symbol_parses_back_to_its_own_class(space_group, q):
    """Stokes & Campbell 2022 p. 366: the symbol names the class.  The 1′ letter
    is read in the spelling of X that the symbol parses to, not the caller's:
    over C222₁(1,0,γ) the two differ by q → q + (0,0,1) plus an internal
    shift, and the symbol of one class used to parse to its neighbour."""
    hits = 0
    for g in superspace_groups(space_group):
        if q not in symbol(g):
            continue
        classes = magnetic_superspace_groups(g, types=(4,))
        texts = [magnetic_symbol(m) for m in classes]
        assert len(set(texts)) == len(texts)
        for m, text in zip(classes, texts):
            assert equivalent(parse_symbol(text), m), text
            hits += 1
    assert hits


def test_table2_spellings_name_their_class(p222):
    """Table 2's printed representatives (m4.1 _a, m5.2 _B, …) are other
    spellings of classes the enumerator labels differently; each parses to
    the class it names."""
    got = magnetic_superspace_groups(p222, types=(2, 4))
    for text in ("P222.1'_B(0,0,γ)0000", "P222.1'_b(0,0,γ)0000", "P222.1'_c(0,0,γ)000s"):
        g = parse_symbol(text)
        assert sum(equivalent(g, m) for m in got) == 1


# ---------------------------------------------------------------------------
# negative controls on the anti-translation
# ---------------------------------------------------------------------------
def test_anti_translation_with_2v_outside_the_lattice_is_refused(p222):
    with pytest.raises(ValueError, match="2v"):
        p222.with_anti_translation((Q, 0, 0, 0))
    with pytest.raises(ValueError, match="2v"):
        p222.with_anti_translation((0, 0, 0, F(1, 3)))
    p222.with_anti_translation((H, 0, 0, H))               # positive arm


def test_anti_translation_adding_translations_is_refused(i222):
    """Table 3's 'none': (¼,¼,¾,0) has 2v ∈ Λ but a two-fold maps it off
    itself modulo the I lattice."""
    with pytest.raises(ValueError, match="change the lattice"):
        i222.with_anti_translation((Q, Q, 3 * Q, 0))


def test_section_of_a_magnetic_group_is_refused(p222):
    with pytest.raises(ValueError, match="magnetic space group"):
        p222.grey().section((0, 0, H), 0)


# ---------------------------------------------------------------------------
# counts over whole basic groups (Stokes & Campbell 2022 p. 369, Table 6)
# ---------------------------------------------------------------------------
def test_p222_family_counts_from_the_web_interface_example():
    """p. 369: entering 16.1.9.1 shows "all 12 of the MSSGs listed in Table
    2" (sic: Tables 1 and 2), and 16.1 "all 40" over the four SSGs of P222.
    The fast count and the object path agree."""
    assert sum(_space_counts(16).values()) == 40
    by_ssg = [len(magnetic_superspace_groups(g)) for g in superspace_groups(16)]
    # the paper prints the 12 and the total of 40 (Stokes & Campbell 2022); the
    # 6 and 10 are this generator's own count, not a printed one
    assert sorted(by_ssg) == [6, 10, 12, 12] and sum(by_ssg) == 40


@pytest.fixture(scope="module")
def table6():
    """The whole d = 1 count, about a minute single-core on the Mac.

    **Consumers must carry** ``@pytest.mark.xdist_group("magnetic-table6")``,
    or a second worker rebuilds it."""
    counts = count_magnetic_superspace_groups()
    return tuple(sum(c[t] for c in counts.values()) for t in (1, 2, 3, 4))


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-table6")
def test_table6_types_1_to_3(table6):
    assert table6[:3] == N_MAGNETIC_SUPERSPACE_TYPES_D1[:3]
    assert sum(N_MAGNETIC_SUPERSPACE_TYPES_D1) == N_MAGNETIC_SUPERSPACE_GROUPS_D1


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-table6")
@pytest.mark.xfail(strict=True, reason=(
    "measured 4651 type-4 groups against the printed 4653 (WP-1992, open); the "
    "fast and object paths agree on every basic group, so the gap is in the "
    "shared equivalence or the candidate set — strict, so a fix turns it red"))
def test_table6_type_4(table6):
    assert table6[3] == N_MAGNETIC_SUPERSPACE_TYPES_D1[3]
