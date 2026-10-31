"""Maximal subgroups generated from the operations (WP-1919).

:func:`~rietx.crystallography.representation.subgroups.maximal` builds every
maximal t- and k-subgroup from A1's theory, standardises each with spglib and
checks P⁻¹HP against that setting exactly.  What is pinned, and against what:

* **The reference set** (validation, DESIGN Rule 4).  Seventeen published
  entries of ITA A1 (Wondratschek & Müller 2011), each read off the page
  image: ch. 2.1 pp. 76, 78, 79 and 80; ch. 3.1 pp. 469 and 471; ch. 1.6
  p. 48.  Each is asserted **present with its (P, p)**, compared exactly up to
  the affine normaliser of H (:meth:`MaximalSubgroup.describes` rebuilds both
  in G's coordinates), with its conjugacy-class size where A1 states one.
  Never a count alone: under the transposed action every count passes too
  (root CLAUDE.md § Invariants).  The negative arm: A1's Pnma → P2₁2₁2₁ with
  its origin shift dropped, and P3₁12's C121 with Pᵀ for P, are found nowhere.
* **The isomorphic series** (verification).  The number of maximal subgroups
  of prime index p ≥ 5 (all isomorphic, A1 Lemma 1.2.8.2.2) against closed
  forms for eleven groups at p = 5 and 7: sublattice counts p² + p + 1 for
  P1, and the conjugate counts of A1 § 2.1.5 and § 3.1.5.1.
* **Maximality** (verification).  P4 with 2a, 2b and P4 with 5a, 5b are not
  maximal (an invariant lattice lies between); P4/m with 3a, 3b and P1 with
  2a are.
* **Setting invariance.**  Two settings of one type give the same multiset of
  (kind, index, type, class size).
* **All 230 types** at index ≤ 4: every subgroup standardises exactly (inside
  :func:`maximal`, which raises otherwise), is re-derived from its own symbol
  and (P, p) as maximal by :func:`is_maximal`, and every class is complete.
  3767 subgroups, 1104 t and 2663 k, about 15-30 CPU-s in all (a second or less for
  one group), so the sweep runs in the fast suite.

**Wyckoff positions and splittings** (the second half):

* **The reference set** (validation).  Splittings ITA A1 prints, quoted from the
  page images: ch. 1.6 pp. 47-49 (AlB₂ → ZrBeSi and CaIn₂, pyrite → PdS₂ and
  NiAsS, PdS₂ → PtGeSe, rutile → trirutile) and ch. 3.1 pp. 468 and 470 (Cmmm →
  Immm in two settings, and the closed forms of the I-4m2 and P4₂/n series at
  p = 3, 5, 7, the latter in both origin choices).  Each is computed in A1's own
  (P, p), so its labels compare exactly, and the subgroup is also one
  :func:`maximal` generates.
* **The frame map** (verification).  spglib labels atoms in its own frame; in
  the 17 Hall settings where that frame permutes letters, the letters agree
  with spglib's on its own standard cell, and differ without the map.
* **Slow, all 230 types** (about 3-4 CPU-min in all, so ``slow``, per group): the
  1731 positions, the same positions in each of the 530 Hall settings, and
  Σ m_H = m_G·|det P| on all 33 792 rows at index ≤ 4.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction

import gemmi
import pytest

from rietx.crystallography.representation import subgroups as S
from rietx.crystallography.representation.subgroups import MaximalSubgroup, is_maximal, maximal
from tests.subgroups_benchmark import standard_symbol

I3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
ZERO = (0, 0, 0)
H = Fraction(1, 2)


def diag(a, b, c):
    return ((a, 0, 0), (0, b, 0), (0, 0, c))


def cols(*columns):
    """P from its columns, the subgroup's axes a', b', c' in G's fractions."""
    return tuple(tuple(columns[j][i] for j in range(3)) for i in range(3))


@pytest.fixture(scope="module")
def lists():
    cache = {}

    def get(group, **kw):
        key = (group, tuple(sorted(kw.items())))
        if key not in cache:
            cache[key] = maximal(group, **kw)
        return cache[key]
    return get


def found(result, symbol, P, p) -> list[MaximalSubgroup]:
    return [s for s in result if s.describes(symbol, (P, p))]


# ---------------------------------------------------------------- the reference set
#
# (G in A1's setting, H in A1's setting, P (rows), p, A1's class size, where).
# P's columns are A1's basis vectors a', b', c'; p is H's origin in G's system.
REFERENCE = [
    # ch. 2.1, Example 2.1.3.3.1, p. 78: the t-subgroups of Pmn2₁ (No. 31)
    ("P m n 21", "P 1 c 1", cols((0, 0, 1), (0, 1, 0), (-1, 0, -1)), ZERO, 1, "A1 p. 78, P1"),
    ("P m n 21", "P 1 m 1", cols((0, 0, 1), (1, 0, 0), (0, 1, 0)), ZERO, 1, "A1 p. 78, P2"),
    ("P m n 21", "P 1 1 21", I3, (Fraction(1, 4), 0, 0), 1, "A1 p. 78, P3"),
    # ch. 2.1, Example 2.1.3.3.2, p. 79: P3₁12 (No. 151) > three conjugate C121
    ("P 31 1 2", "C 1 2 1", ((0, -2, 0), (1, -1, 0), (0, 0, 1)), ZERO, 3, "A1 p. 79, P6"),
    ("P 31 1 2", "C 1 2 1", ((-1, 1, 0), (-1, -1, 0), (0, 0, 1)), (0, 0, Fraction(1, 3)), 3,
     "A1 p. 79, P4"),
    ("P 31 1 2", "C 1 2 1", ((1, 1, 0), (0, 2, 0), (0, 0, 1)), (0, 0, Fraction(2, 3)), 3,
     "A1 p. 79, P5"),
    # ch. 2.1, Example 2.1.4.3.1, p. 80: C222₁ (No. 20), [3] a' = 3a and b' = 3b
    ("C 2 2 21", "C 2 2 21", diag(3, 1, 1), ZERO, 3, "A1 p. 80, 3a, o"),
    ("C 2 2 21", "C 2 2 21", diag(3, 1, 1), (1, 0, 0), 3, "A1 p. 80, 3a, a"),
    ("C 2 2 21", "C 2 2 21", diag(3, 1, 1), (2, 0, 0), 3, "A1 p. 80, 3a, 2a"),
    ("C 2 2 21", "C 2 2 21", diag(1, 3, 1), ZERO, 3, "A1 p. 80, 3b, o"),
    ("C 2 2 21", "C 2 2 21", diag(1, 3, 1), (0, 1, 0), 3, "A1 p. 80, 3b, b"),
    ("C 2 2 21", "C 2 2 21", diag(1, 3, 1), (0, 2, 0), 3, "A1 p. 80, 3b, 2b"),
    # ch. 2.1, Example 2.1.3.2.1, p. 76: Pm-3m (No. 221) > three conjugate P4/mmm
    ("P m -3 m", "P 4/m m m", I3, ZERO, 3, "A1 p. 76"),
    # ch. 3.1, Example 3.1.3.1, p. 469: Fddd origin 1 → C12/c1, p = 1/8, 1/8, 1/8
    ("F d d d:1", "C 1 2/c 1", ((1, 0, -H), (0, -1, 0), (0, 0, -H)), (Fraction(1, 8),) * 3, 1,
     "A1 p. 469, Ex. 3.1.3.1"),
    # ch. 3.1, Example 3.1.3.2, p. 469: Pnma → P2₁2₁2₁, origin 0, 0, −1/4 in Pnma
    ("P n m a", "P 21 21 21", I3, (0, 0, Fraction(-1, 4)), 1, "A1 p. 469, Ex. 3.1.3.2"),
    # ch. 3.1, Example 3.1.5.1.3, p. 471: Pm-3m → Im-3m (2a, 2b, 2c), a class of four
    ("P m -3 m", "I m -3 m", diag(2, 2, 2), ZERO, 4, "A1 p. 471, origin 0,0,0"),
    ("P m -3 m", "I m -3 m", diag(2, 2, 2), (-1, 0, 0), 4, "A1 p. 471, origin -1,0,0"),
    ("P m -3 m", "I m -3 m", diag(2, 2, 2), (0, -1, 0), 4, "A1 p. 471, origin 0,-1,0"),
    ("P m -3 m", "I m -3 m", diag(2, 2, 2), (0, 0, -1), 4, "A1 p. 471, origin 0,0,-1"),
    # ch. 3.1, Example 3.1.5.2.1, p. 471: P-43m > three conjugate P-42m, c' along a, b, c
    ("P -4 3 m", "P -4 2 m", I3, ZERO, 3, "A1 p. 471, c' = c"),
    ("P -4 3 m", "P -4 2 m", cols((0, 1, 0), (0, 0, 1), (1, 0, 0)), ZERO, 3, "A1 p. 471, c' = a"),
    ("P -4 3 m", "P -4 2 m", cols((0, 0, 1), (1, 0, 0), (0, 1, 0)), ZERO, 3, "A1 p. 471, c' = b"),
    # ch. 1.6, Fig. 1.6.4.3, p. 48: AlB₂ P6/mmm → ZrBeSi and CaIn₂, both P6₃/mmc a, b, 2c
    ("P 6/m m m", "P 63/m m c", diag(1, 1, 2), ZERO, 1, "A1 p. 48, ZrBeSi"),
    ("P 6/m m m", "P 63/m m c", diag(1, 1, 2), (0, 0, -H), 1, "A1 p. 48, CaIn2"),
]


@pytest.mark.parametrize("group, symbol, P, p, size, where", REFERENCE,
                         ids=[r[5] for r in REFERENCE])
def test_each_published_subgroup_is_present_with_its_transformation(
        lists, group, symbol, P, p, size, where):
    hits = found(lists(group), symbol, P, p)
    assert len(hits) == 1, f"{where}: {symbol} under {P}, {p} is not in the list"
    assert hits[0].class_size == size
    assert is_maximal(group, symbol, (P, p))


def test_published_conjugates_fall_in_one_class(lists):
    for group, symbol in [("P 31 1 2", "C 1 2 1"), ("P -4 3 m", "P -4 2 m")]:
        rows = [r for r in REFERENCE if r[0] == group and r[1] == symbol]
        classes = {found(lists(group), symbol, r[2], r[3])[0].conjugacy_class for r in rows}
        assert len(classes) == 1
    # C222₁: the 3a triplet and the 3b triplet are two classes (A1 p. 80's two braces)
    c = [found(lists("C 2 2 21"), "C 2 2 21", r[2], r[3])[0].conjugacy_class
         for r in REFERENCE if r[0] == "C 2 2 21"]
    assert len(set(c[:3])) == 1 and len(set(c[3:])) == 1 and c[0] != c[3]


def test_pm3m_has_two_im3m_classes_of_four(lists):
    """A1 p. 471: "two subgroups Im-3m (2a, 2b, 2c) with index 4 are listed",
    each one of a set of four conjugates."""
    im3m = [s for s in lists("P m -3 m") if s.number == 229]
    assert Counter(s.conjugacy_class for s in im3m).most_common() and \
        sorted(Counter(s.conjugacy_class for s in im3m).values()) == [4, 4]
    assert all(s.index == 4 and s.kind == "k" for s in im3m)


def test_the_alb2_hettotypes_are_not_conjugate(lists):
    """A1 p. 48: ZrBeSi and CaIn₂ are both P6₃/mmc on a, b, 2c, and different
    subgroups of AlB₂'s P6/mmm by their origins."""
    zr = found(lists("P 6/m m m"), "P 63/m m c", diag(1, 1, 2), ZERO)[0]
    ca = found(lists("P 6/m m m"), "P 63/m m c", diag(1, 1, 2), (0, 0, -H))[0]
    assert zr.conjugacy_class != ca.conjugacy_class


def test_pmmm_has_eight_fmmm_subgroups(lists):
    """A1 p. 80: "the eight maximal subgroups of the type Fmmm, No. 69, of
    space group Pmmm" (one entry in IT A, eight in A1), on the index-2
    sublattice a' = 2a, b' = 2b, c' = 2c, F-centring (p. 80, list (1)(vii))."""
    fmmm = [s for s in lists("P m m m") if s.number == 69]
    assert len(fmmm) == 8
    assert all(s.index == 2 and s.basis == "2a,2b,2c" for s in fmmm)
    assert len({s.conjugacy_class for s in fmmm}) == 8  # index 2: each normal


def test_cmcm_three_cells_name_one_subgroup(lists):
    """A1 p. 471, Example 3.1.6.1: Cmcm's P112₁/m with the cell a, ½(−a+b), c,
    or ½(a−b), b, c, or ½(a−b), ½(a+b), c: one subgroup, three bases."""
    cells = [cols((1, 0, 0), (-H, H, 0), (0, 0, 1)), cols((H, -H, 0), (0, 1, 0), (0, 0, 1)),
             cols((H, -H, 0), (H, H, 0), (0, 0, 1))]
    hits = {id(found(lists("C m c m"), "P 1 1 21/m", P, ZERO)[0]) for P in cells}
    assert len(hits) == 1


def test_isomorphic_entries_on_demand(lists):
    """F4₁32 →(i27) F4₁32 with 3b, −3a, 3c and no origin shift (A1 p. 469);
    Cmc2₁'s a, b, 5c has no conjugates (A1 p. 471, Ex. 3.1.5.1.2); rutile's
    P4₂/mnm has an isomorphic subgroup of index 3 and none of index 2 (A1
    p. 48, trirutile)."""
    f = found(lists("F 41 3 2", index=27), "F 41 3 2", cols((0, 3, 0), (-3, 0, 0), (0, 0, 3)), ZERO)
    assert len(f) == 1 and f[0].kind == "k"
    c = found(lists("C m c 21", index=5), "C m c 21", diag(1, 1, 5), ZERO)
    assert len(c) == 1 and c[0].class_size == 1
    assert not any(s.number == 136 for s in lists("P 42/m n m", index=2))
    assert any(s.number == 136 for s in lists("P 42/m n m", index=3))


def test_a_wrong_origin_or_a_transposed_basis_is_found_nowhere(lists):
    """The positive arm of the comparison: A1's Pnma → P2₁2₁2₁ needs its
    0, 0, −¼, and without it the group is not a subgroup at all; P3₁12's
    C121 with Pᵀ for P is a C121 but not one of these."""
    assert not found(lists("P n m a"), "P 21 21 21", I3, ZERO)
    with pytest.raises(ValueError, match="not a subgroup"):
        is_maximal("P n m a", "P 21 21 21", (I3, ZERO))
    P6 = ((0, -2, 0), (1, -1, 0), (0, 0, 1))
    P6t = tuple(tuple(P6[j][i] for j in range(3)) for i in range(3))
    assert not found(lists("P 31 1 2"), "C 1 2 1", P6t, ZERO)


# ---------------------------------------------------------------- series and maximality

def _series(p: int) -> dict[str, int]:
    """Maximal subgroups of prime index p ≥ 5, all isomorphic (A1 § 2.1.5).

    P1: one per index-p sublattice of ℤ³, (p³ − 1)/(p − 1), all normal.  Where
    the origin is fixed along the enlargement, p conjugates (A1 § 3.1.5.1);
    where it floats (the unique axis of 2, 3, 4, 6), one.  In-plane tetragonal
    and hexagonal enlargements of index p exist only when p ≡ 1 mod 4
    (q² + r² = p) or mod 3 (q² + qr + r² = p), two lattices each (A1 Ex.
    2.1.5.2.2; A1 ch. 3.1 footnote 1).
    """
    four = 2 if p % 4 == 1 else 0
    three = 2 if p % 3 == 1 else 0
    return {
        "P 1": p * p + p + 1,
        "P -1": p * (p * p + p + 1),
        "P 1 2 1": 1 + (p + 1) * p,
        "P 1 2/m 1": p + (p + 1) * p,
        "P 4": 1 + four * p,
        "P 4/m": p + four * p,
        "P 3": 1 + three * p,
        "P -3": p + three * p,
        "P -6": p + three * p,
        "P 2 2 2": 3 * p,
        "P m m m": 3 * p,
    }


@pytest.mark.parametrize("p", [5, 7])
def test_the_isomorphic_series_counts_match_their_closed_forms(p):
    for group, count in _series(p).items():
        result = maximal(group, index=p)
        assert len(result) == count, group
        assert all(s.kind == "k" and s.index == p and s.prime == p for s in result)
        assert all(s.number == gemmi.SpaceGroup(group).number for s in result)


@pytest.mark.parametrize("group, P, expected", [
    ("P 4", diag(2, 2, 1), False),   # (a + b) + L' is invariant, between
    ("P 4", diag(5, 5, 1), False),   # 5 = 1² + 2²: two invariant lines over F₅
    ("P 4/m", diag(3, 3, 1), True),  # 3 ≡ 3 mod 4: F₃² is irreducible under the 4
    ("P 1", diag(2, 1, 1), True),
    ("P m -3 m", diag(2, 2, 2), False),
])
def test_maximality_is_decided_by_the_lattices_in_between(group, P, expected):
    assert is_maximal(group, group, (P, ZERO)) is expected


def test_a_supercell_keeps_only_the_subgroups_that_keep_its_translations():
    """P4 on 2a, 2b: its own lattice is not maximal, and the maximal
    k-subgroups keeping all its translations are the two P4 on the C-centred
    lattice a − b, a + b, at origins 0, 0, 0 and ½, ½, 0."""
    ks = maximal("P 4", kind="k", supercell=diag(2, 2, 1))
    assert len(ks) == 2 and all(s.number == 75 and s.index == 2 for s in ks)
    c_cell = cols((1, -1, 0), (1, 1, 0), (0, 0, 1))
    assert sum(s.describes("P 4", (c_cell, ZERO)) for s in ks) == 1
    assert sum(s.describes("P 4", (c_cell, (H, H, 0))) for s in ks) == 1
    assert not any(s.describes("P 4", (diag(2, 2, 1), ZERO)) for s in ks)
    assert all(s.kind == "t" for s in maximal("P 4", kind="t", supercell=diag(2, 2, 1)))
    with pytest.raises(ValueError, match="not a lattice vector"):
        maximal("C 2 2 21", supercell=((H, 0, 0), (0, 1, 0), (0, 0, 1)))


# ---------------------------------------------------------------- settings and structure

@pytest.mark.parametrize("one, two", [
    ("F d -3 m:1", "F d -3 m:2"),
    ("P n n n:1", "P n n n:2"),
    ("R -3 m:H", "R -3 m:R"),
    ("P 1 21/c 1", "P 1 1 21/b"),     # unique axis b against c
    ("P 1 21/c 1", "P 1 21/n 1"),     # cell choice 1 against 2
    ("C m c e", "C c m b"),
    ("P b a n:1", "P b a n:2"),
])
def test_two_settings_give_one_multiset(one, two):
    def multiset(group):
        return Counter((s.kind, s.index, s.number, s.class_size) for s in maximal(group))
    assert multiset(one) == multiset(two)


def test_index_two_subgroups_are_normal_and_t_subgroups_follow_the_point_group(lists):
    for group in ("P m -3 m", "P 6/m m m", "F d d d:1", "P n m a"):
        result = lists(group)
        assert all(s.class_size == 1 for s in result if s.index == 2)
        points = S._maximal_point_subgroups(frozenset(S._group_of(group).reps))
        assert sum(1 for s in result if s.kind == "t") == len(points)


def test_the_text_reads_like_a1(lists):
    s = found(lists("F d d d:1"), "C 1 2/c 1", ((1, 0, -H), (0, -1, 0), (0, 0, -H)),
              (Fraction(1, 8),) * 3)[0]
    assert s.basis == "a,-b,-1/2a-1/2c"
    assert str(s).startswith("[2] t C 1 2/c 1 (15)  a,-b,-1/2a-1/2c  origin ")


def test_the_arguments_are_checked():
    with pytest.raises(ValueError, match="kind must be"):
        maximal("P 1", kind="x")
    with pytest.raises(ValueError, match="singular"):
        maximal("P 1", supercell=diag(1, 1, 0))
    assert maximal("P 1", index=6) == ()  # not a prime power: no maximal subgroup
    assert {s.index for s in maximal("P m m m", kind="t")} == {2}


def test_the_probe_tolerance_decides_no_subgroup(monkeypatch):
    """spglib's symprec only lets the probe be named; the exact check decides."""
    before = {g: maximal(g) for g in ("P 31 1 2", "F d d d:1", "P m -3 m")}
    S._standard.cache_clear()
    monkeypatch.setattr(S, "_PROBE_SYMPREC", 1e-3)
    assert {g: maximal(g) for g in before} == before


# ---------------------------------------------------------------- all 230 types

@pytest.mark.parametrize("number", range(1, 231))
def test_every_maximal_subgroup_of_index_at_most_four_standardises_exactly(number):
    group = standard_symbol(number)
    result = maximal(group)
    assert result
    sizes = Counter(s.conjugacy_class for s in result)
    for s in result:
        assert s.index <= S.MAX_INDEX
        assert sizes[s.conjugacy_class] == s.class_size  # every class is whole
        assert is_maximal(group, s.symbol, s.transform)


# ---------------------------------------------------------------- review round (#1189)

@pytest.mark.parametrize("group, p", [
    ("P -1", 29), ("P -1", 53),
    ("P 6/m m m", 17), ("P 6/m m m", 29), ("P -3 m 1", 29)])
def test_an_isomorphic_series_standardises_past_the_floor_of_the_denominator_bound(group, p):
    """The inversion centre of a p-fold supercell sits at 1/2p in the child's axes, a
    hexagonal origin at 3p: the old bound of 48 failed the first from p = 29 (the
    hexagonal p = 17 row is a non-regression: spglib's float happened to round).

    P-1 goes through ``supercell=`` (pa, b, c), as the review reproduced it:
    ``index=`` lists every one of the p² + p + 1 lattices with p complements each,
    some 150 000 subgroups at p = 53, where one lattice
    holds the same inversion centres at 1/2p.  That is what let the two P -1 rows
    leave the ``slow`` tier: under the old fixed 48, P -1 at p = 29 and P 6/m m m and
    P -3 m 1 at p = 29 all raise (no exact standard setting)."""
    if group == "P -1":
        result = maximal(group, supercell=diag(p, 1, 1), kind="k")
    else:
        result = maximal(group, index=p, kind="k")
    assert result
    assert all(s.index == p and s.prime == p and is_maximal(group, s.symbol, s.transform)
               for s in result)


def test_the_p_minus_1_supercell_of_index_29_gives_29_subgroups():
    result = maximal("P -1", supercell=((29, 0, 0), (0, 1, 0), (0, 0, 1)), kind="k")
    assert len(result) == 29  # the same as 5a and 13a give 5 and 13


def test_a_wrong_basis_answers_false_and_is_maximal_names_the_refusal():
    im3m = next(s for s in maximal("P m -3 m") if s.symbol.startswith("I m -3 m"))
    wrong = (diag(2, 1, 1), ZERO)  # its rebuilt operations are not integral in G's axes
    assert im3m.describes("I m -3 m", wrong) is False
    assert [s.describes("I m -3 m", wrong) for s in maximal("P m -3 m")].count(True) == 0
    with pytest.raises(ValueError, match="is not a subgroup of the group"):
        is_maximal("P m -3 m", "I m -3 m", wrong)


def test_a_float_origin_is_snapped_to_the_ratio_it_stands_for():
    s = next(s for s in maximal("P 31 1 2", kind="t")
             if s.symbol.startswith("C 1 2 1") and s.origin == "0,0,1/3")
    P, p = s.transform
    floats = (tuple(tuple(float(v) for v in r) for r in P), tuple(float(x) for x in p))
    assert p[2] == Fraction(1, 3) and floats[1][2] == 1 / 3
    assert s.describes(s.symbol, floats)  # the binary fraction of 1/3 matched nothing before
    assert not s.describes(s.symbol, (P, (0.0, 0.0, 0.0)))
    assert S._q(1 / 3) == Fraction(1, 3)
    with pytest.raises(ValueError, match="not a rational with denominator"):
        S._q(0.123456)


def test_max_index_and_index_are_checked_against_each_other_and_themselves():
    with pytest.raises(ValueError, match="cannot be combined"):
        maximal("P 1", max_index=9, index=5)
    with pytest.raises(ValueError, match="cannot be combined"):
        maximal("P 1", max_index=9, supercell=diag(2, 1, 1))
    for bad in (4.0, -3, 0, True):
        with pytest.raises(ValueError, match="positive integer"):
            maximal("P 1", index=bad)
    assert len(maximal("P 1", max_index=3)) == 3 ** 2 + 3 + 1 + 2 ** 2 + 2 + 1


def test_the_invariant_subspace_cache_holds_bases_not_spans():
    inversion = (((-1, 0, 0), (0, -1, 0), (0, 0, -1)),)
    found = S._invariant_subspaces(inversion, 13)
    assert len(found) == 1 + 183 + 183  # every line and plane of F_13^3 is invariant under -1
    assert all(isinstance(b, tuple) and len(b) <= 2 for b in found)  # never p^d vectors
    assert S._invariant_subspaces.cache_info().maxsize is not None


# ================================================================ Wyckoff positions (PR 2)
#
# The splittings ITA A1 prints, each quoted from the page as a literature value
# (page images viewed 2026-10-30): (name, G, H, P, p, {G label: H labels}).  A1's
# own (P, p) is passed, so the labels belong to it and compare exactly; the
# subgroup itself is also found by maximal() up to the normaliser.  For the two
# series rows A1 prints a closed form in p, evaluated here at p = 3, 5, 7.
Q = Fraction(1, 4)


def i4m2_series(p):
    """A1 Example 3.1.1.6.5 (p. 468): I-4m2 > I-4m2 (pa, pb, c), position 2a."""
    h = (p - 1) // 2
    return ("2a",) + ("8g",) * h + ("8i",) * h + ("16j",) * ((p - 1) * (p - 3) // 8)


def p42n_series(p, origin):
    """A1 Example 3.1.1.6.7 (p. 468): P4₂/n > P4₂/n (a, b, pc), position 2a, no origin
    shift: 2a for origin choice 1, and for choice 2 also 2a if p = 4n + 1 but 2b if
    p = 4n − 1; then (p − 1)/2 × 4f."""
    first = "2b" if origin == 2 and p % 4 == 3 else "2a"
    return (first,) + ("4f",) * ((p - 1) // 2)


SPLITTINGS = [
    # ch. 1.6, Fig. 1.6.4.3, p. 48: AlB₂ (Al 1a, B 2d) → ZrBeSi and → CaIn₂
    ("ZrBeSi", "P 6/m m m", "P 63/m m c", diag(1, 1, 2), ZERO,
     {"1a": ("2a",), "2d": ("2c", "2d")}),
    ("CaIn2", "P 6/m m m", "P 63/m m c", diag(1, 1, 2), (0, 0, -H),
     {"1a": ("2b",), "2d": ("4f",)}),
    # ch. 1.6, Fig. 1.6.4.1, p. 47: pyrite (Fe 4a, S 8c) → PdS₂, NiAsS; PdS₂ → PtGeSe
    ("PdS2", "P a -3", "P b c a", I3, ZERO, {"4a": ("4a",), "8c": ("8c",)}),
    ("NiAsS", "P a -3", "P 21 3", I3, ZERO, {"4a": ("4a",), "8c": ("4a", "4a")}),
    ("PtGeSe", "P b c a", "P b c 21", I3, (-Q, 0, 0), {"4a": ("4a",), "8c": ("4a", "4a")}),
    # ch. 1.6, Fig. 1.6.4.4, p. 49: rutile (Ti 2a, O 4f) → trirutile ZnSb₂O₆, a, b, 3c
    ("trirutile", "P 42/m n m", "P 42/m n m", diag(1, 1, 3), ZERO,
     {"2a": ("2a", "4e"), "4f": ("4f", "8j")}),
    # ch. 3.1, Example 3.1.4.4, p. 470: Cmmm 4k (0, 0, z) → 2 × 4i in either Immm with
    # 2c; in the Bmmm setting (4k at 0, y, 0, b doubled) the conventional Immm reads 2 × 4g
    ("Cmmm Immm o", "C m m m", "I m m m", diag(1, 1, 2), ZERO, {"4k": ("4i", "4i")}),
    ("Cmmm Immm c/2", "C m m m", "I m m m", diag(1, 1, 2), (0, 0, H), {"4k": ("4i", "4i")}),
    ("Bmmm Immm", "B m m m", "I m m m", diag(1, 2, 1), ZERO, {"4k": ("4g", "4g")}),
]
for _p in (3, 5, 7):
    SPLITTINGS += [
        (f"I-4m2 p={_p}", "I -4 m 2", "I -4 m 2", diag(_p, _p, 1), ZERO, {"2a": i4m2_series(_p)}),
        (f"P42/n:1 p={_p}", "P 42/n:1", "P 42/n:1", diag(1, 1, _p), ZERO,
         {"2a": p42n_series(_p, 1)}),
        (f"P42/n:2 p={_p}", "P 42/n:2", "P 42/n:2", diag(1, 1, _p), ZERO,
         {"2a": p42n_series(_p, 2)}),
    ]


@pytest.mark.parametrize("name, group, symbol, P, p, expected", SPLITTINGS,
                         ids=[r[0] for r in SPLITTINGS])
def test_each_published_splitting_is_reproduced_in_its_own_transformation(
        name, group, symbol, P, p, expected):
    result = S.wyckoff_splitting(group, (symbol, (P, p)))
    assert result.transform == (S._mat(P), tuple(S._q(x) for x in p))  # the labels' (P, p)
    for g_label, h_labels in expected.items():
        assert result[g_label] == h_labels, (name, g_label)
    # the subgroup is one maximal() generates, up to the affine normaliser
    det = abs(int(S._rational_determinant(S._mat(P))))
    pool = maximal(group) if det <= S.MAX_INDEX else maximal(group, supercell=P)
    assert len(found(pool, symbol, P, p)) == 1


def test_the_two_alb2_subgroups_split_2d_the_two_ways_a1_describes():
    """A1 p. 48: one subgroup keeps 6̄m2 and splits 2d, the other keeps 2d whole on 3m."""
    keep, split = (S.wyckoff_splitting("P 6/m m m", ("P 63/m m c", (diag(1, 1, 2), o)))
                   for o in ((0, 0, -H), ZERO))
    assert keep["2d"] == ("4f",) and split["2d"] == ("2c", "2d")
    four_f = next(w for w in S.wyckoff_positions("P 63/m m c").positions if w.label == "4f")
    assert four_f.site_order == 6 and len(four_f.directions) == 1  # 3m., z free


def test_a_maximal_subgroup_and_its_own_pair_give_one_splitting():
    for s in maximal("P 42/m n m"):
        assert S.wyckoff_splitting("P 42/m n m", s) == \
            S.wyckoff_splitting("P 42/m n m", (s.symbol, s.transform))


def test_a_splitting_names_the_transformations_its_labels_belong_to():
    s = next(s for s in maximal("P 6/m m m") if s.describes("P 63/m m c", (diag(1, 1, 2), ZERO)))
    result = S.wyckoff_splitting("P 6/m m m", s)
    assert result.transform == s.transform and result.group_transform == S._IDENTITY
    assert result.group == "P 6/m m m" and result.subgroup == s.symbol
    # a group in none of spglib's 530 Hall settings takes its letters through a (P, p)
    off = S.wyckoff_splitting("C 4 2 2", ("C 4 2 2", (diag(1, 1, 3), ZERO)))
    assert off.group_transform != S._IDENTITY
    assert off.group_transform == S.wyckoff_positions("C 4 2 2").transform
    with pytest.raises(KeyError):
        result["9z"]


def test_a_pair_that_is_not_a_subgroup_is_refused():
    with pytest.raises(ValueError, match="is not a subgroup of the group"):
        S.wyckoff_splitting("P m -3 m", ("I m -3 m", (diag(2, 1, 1), ZERO)))  # not integral
    with pytest.raises(ValueError, match="is not a subgroup of the group"):
        S.wyckoff_splitting("P n m a", ("P 21 21 21", (I3, ZERO)))  # A1's origin dropped
    # the transposed basis of a published subgroup (the Rᵀ trap) is refused too
    P = ((0, -2, 0), (1, -1, 0), (0, 0, 1))
    S.wyckoff_splitting("P 31 1 2", ("C 1 2 1", (P, ZERO)))
    with pytest.raises(ValueError, match="is not a subgroup of the group"):
        S.wyckoff_splitting("P 31 1 2", ("C 1 2 1", (tuple(zip(*P)), ZERO)))


@pytest.mark.parametrize("group", ["P m -3 m", "F d -3 m:2", "R -3 m:H", "R -3 m:R",
                                   "P 1 21/c 1", "C m c e", "P 63/m m c", "I 41/a m d:1"])
def test_each_position_is_what_its_point_and_directions_say(group):
    """An independent reading: :func:`site_constraints` (float site orbits, symmetry.py)
    gives each position's generic point the same multiplicity and free directions."""
    from rietx.crystallography.wyckoff import site_constraints

    table = S.wyckoff_positions(group)
    for w in table.positions:
        x = [float(v) for v in w.point]
        for d, t in zip(w.directions, (0.0137, 0.0213, 0.0291)):
            x = [xi + t * di for xi, di in zip(x, d)]
        sc = site_constraints(group, x)
        assert sc.multiplicity == w.multiplicity, (group, w.label)
        assert len(sc.coord_basis) == len(w.directions), (group, w.label)
    assert table.positions[-1].site_order == 1  # the general position comes last


def test_rhombohedral_axes_keep_the_letters_and_divide_the_multiplicities_by_three():
    hexagonal, rhombohedral = (S.wyckoff_positions(g) for g in ("R -3 m:H", "R -3 m:R"))
    assert [w.letter for w in hexagonal.positions] == [w.letter for w in rhombohedral.positions]
    assert [w.multiplicity for w in hexagonal.positions] == \
        [3 * w.multiplicity for w in rhombohedral.positions]
    assert rhombohedral.transform == S._IDENTITY  # a Hall setting of its own


# the 17 Hall settings in which spglib names a probe already in the setting through a
# normaliser element that permutes letters (measured 2026-10-30, spglib 2.8.0)
PERMUTED_FRAMES = [65, 68, 71, 73, 76, 79, 85, 88, 92, 96, 98, 100, 101, 102, 104, 106, 107]


@pytest.mark.parametrize("hall", PERMUTED_FRAMES)
def test_the_letters_follow_spglibs_frame_and_not_the_input_order(hall):
    """spglib labels an atom in its own standardised frame, so a letter belongs to the
    position holding the atom's image.  The check: spglib's letters on its *own*
    standard cell, where its frame is the identity, agree with ours coordinate by
    coordinate; and the positive arm, that taking the letters in the input order (no
    frame map) gives other letters in these settings."""
    import numpy as np
    import spglib

    table = S._hall_table(hall)
    positions, numbers = [], []
    for i in range(len(table.classes)):
        x = table.generic(i)
        orbit = sorted({S._frac_part(S._add(S._mv(W, x), w)) for W, w in table.ops})
        positions += [[float(v) for v in y] for y in orbit]
        numbers += [i + 1] * len(orbit)
    lattice = np.linalg.cholesky(S._metric(table.G))
    first = spglib.get_symmetry_dataset((lattice, positions, numbers), hall_number=hall)
    raw = [first.wyckoffs[numbers.index(i + 1)] for i in range(len(table.classes))]
    assert raw != [c[0] for c in table.classes]  # the frame map acts here
    again = spglib.get_symmetry_dataset(
        (first.std_lattice, first.std_positions, first.std_types), hall_number=hall)
    assert np.allclose(again.transformation_matrix, np.eye(3))
    for xyz, letter in zip(again.std_positions, again.wyckoffs):
        x = tuple(Fraction(float(v)).limit_denominator(10 ** 5) for v in xyz)
        assert table.classes[table.identify(x)][0] == letter


@pytest.mark.parametrize("hall", PERMUTED_FRAMES + [1, 2, 3, 62, 227, 304, 488, 523])
def test_site_constraints_names_the_letter_wyckoff_positions_gives(hall):
    """``site_constraints`` and ``wyckoff_positions`` name one letter for one site.

    The positive arm is the 17 settings whose spglib frame permutes letters: the
    letter ``site_constraints`` took from spglib in the input order belonged to
    another position there (measured 2026-10-31 on 8 of them: 16 of 54 wrong).
    The other Hall numbers are default settings, where the two always agreed.
    """
    from rietx.crystallography.wyckoff import site_constraints

    symbol = S._xhm_of_hall(hall)
    table = S._hall_table(hall)
    named = S.wyckoff_positions(symbol)
    assert named.transform == S._IDENTITY  # a Hall setting: the letters are the table's own
    for i, w in enumerate(named.positions):
        x = [float(v) for v in table.generic(i)]
        assert site_constraints(symbol, x).wyckoff == w.label, (symbol, w.label)


@pytest.mark.parametrize("group", ["P 42/n c m:2", "P n -3 m:2", "P -4 b 2", "P 4/m b m"])
def test_site_constraints_letter_on_a_line_off_the_axes(group):
    """Positions whose free direction is not an axis (x, 1/2 - x, z) have no exact
    rational form for a float point, so the letter is read with the tolerance."""
    from rietx.crystallography.wyckoff import site_constraints

    named = S.wyckoff_positions(group)
    pos = S._Positions(S._group_of(group))
    assert named.transform == S._IDENTITY
    table = pos.table
    for i, w in enumerate(named.positions):
        x = [float(v) for v in table.generic(i)]
        assert site_constraints(group, x).wyckoff == w.label, (group, w.label)


def test_a_splitting_prints_the_transform_g_s_own_labels_belong_to():
    """A group outside spglib's 530 Hall settings is lettered through (P, p); the printed
    table says which, and says nothing extra for a group that is in one."""
    off = "I 1 21 1"  # gemmi's setting, not a Hall one
    shown = str(S.wyckoff_splitting(off, maximal(off)[0]))
    assert S.wyckoff_splitting(off, maximal(off)[0]).group_transform != S._IDENTITY
    assert f"{off}'s labels: P = " in shown
    assert "'s labels" not in str(S.wyckoff_splitting("P m -3 m", maximal("P m -3 m")[0]))


# ---------------------------------------------------------------- all 230 types, slow

@pytest.mark.slow
def test_the_positions_of_the_230_types_number_1731():
    """ITA's total (ITA A, 2016, ch. 1.4), from the operations alone."""
    assert sum(len(S.wyckoff_positions(standard_symbol(n)).positions)
               for n in range(1, 231)) == 1731


@pytest.mark.slow
@pytest.mark.parametrize("number", range(1, 231))
def test_every_hall_setting_of_a_type_letters_its_positions_alike(number):
    """Setting invariance: each of the type's Hall settings (530 in all: unique axes,
    cell choices, origin choices, both rhombohedral axes) has the positions of its
    default setting, letter by letter, with the same site order and freedom."""
    def signature(hall):
        return sorted((c[0], c[3], len(c[5])) for c in S._hall_table(hall).classes)
    halls = S._halls_of(number)
    assert all(signature(h) == signature(halls[0]) for h in halls[1:])


@pytest.mark.slow
@pytest.mark.parametrize("number", range(1, 231))
def test_every_splitting_row_at_index_at_most_four_conserves_multiplicity(number):
    """Σ m_H = m_G·|det P| on every row, summed from the labels' own table entries."""
    group = standard_symbol(number)
    m_g = {w.label: w.multiplicity for w in S.wyckoff_positions(group).positions}
    for s in maximal(group):
        m_h = {w.label: w.multiplicity for w in S.wyckoff_positions(s.symbol).positions}
        det = abs(S._rational_determinant(s.transform[0]))
        result = S.wyckoff_splitting(group, s)
        assert [g for g, _ in result.rows] == list(m_g)
        for g, hs in result.rows:
            assert sum(m_h[h] for h in hs) == m_g[g] * det, (group, str(s), g, hs)
