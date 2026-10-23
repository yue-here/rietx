"""(3+1)D superspace operators, generation, equivalence, symbols, sections (N-W1).

Each pin is a number or a table printed in a paper, with its page, so a wrong
algebra cannot pass by agreeing with itself:

* **counts** — 775 (3+1)D groups from the 230 basic groups (Yamamoto, Janssen,
  Janner & de Wolff 1985, *Acta Cryst.* A41, 528, p. 529; Stokes, Campbell &
  van Smaalen 2011, *Acta Cryst.* A67, 45, p. 47), 24 Bravais classes
  (Stokes 2011 p. 49), four over P222 (Stokes & Campbell 2022, *Acta Cryst.*
  A78, 364, p. 369), and the per-group counts Stokes 2011 Table 9's numbers
  imply (p. 54);
* **de Wolff's pedigree** P4 → P4/n → P4/nbm in the class W^{P4/mmm}
  (de Wolff, Janssen & Janner 1981, *Acta Cryst.* A37, 625, § 6, pp. 635-636);
* **symbols** — Stokes 2011 Table 9's eleven ITC-C exceptions, with the
  8-nicer / 3-not-strict split § 5.2.5 states, and symbols printed in five
  papers;
* **equivalence** — Yamamoto 1985 § 2's I2cb, whose re-indexed bottom line
  is the symbol of a non-equivalent group;
* **sections** — Orlov, Palatinus & Chapuis 2008, *J. Appl. Cryst.* 41,
  1182, Tables 1 and 3 (pp. 1183, 1185): the 3D group of every (q, t₀) class.

The 775 count and the 24 classes take about a minute each and are ``slow``;
the per-group pins are the fast arm of the same generator.  The ISO(3+d)D
tables were not used, not even as an oracle: every number here is from print.
"""

from __future__ import annotations

import random
from fractions import Fraction as F
from itertools import product

import numpy as np
import pytest

from rietx.crystallography.superspace import (
    IDENTITY,
    ITC_C_EXCEPTIONS,
    N_BRAVAIS_CLASSES_D1,
    N_SUPERSPACE_GROUPS_D1,
    ModulationVector,
    SuperspaceGroup,
    SuperspaceOperator,
    SuperspaceTransform,
    bravais_classes,
    canonical_key,
    catalogue,
    count_superspace_groups,
    equivalent,
    family_orbits,
    generate,
    parse_symbol,
    standardised,
    superspace_groups,
    symbol,
    symbol_candidates,
)
from rietx.crystallography.superspace.symbols import _eit, _expected, _positions, _setting_of


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------
def test_operator_string_round_trips_and_carries_m_epsilon_delta():
    op = SuperspaceOperator.from_xyz("-x1,x2,-x3+1/2,x1-x4+1/2")
    assert op.rotation == ((-1, 0, 0), (0, 1, 0), (0, 0, -1))
    assert op.translation == (F(0), F(0), F(1, 2))
    assert (op.m, op.epsilon, op.delta) == ((1, 0, 0), -1, F(1, 2))
    assert SuperspaceOperator.from_xyz(op.xyz()) == op
    # the Stokes (x,y,z,t) spelling reads to the same operation
    assert SuperspaceOperator.from_xyz("-x,y,-z+1/2,x-t+1/2") == op


def _augmented(op):
    return op.matrix


def test_composition_is_the_augmented_matrix_product_mod_one():
    """Stokes 2011 eqs (3)-(8): __mul__ against the 5×5 product of eq. (1)."""
    rng = random.Random(7)
    groups = [g for n in (16, 62, 85, 125, 141, 194) for g in superspace_groups(n)]
    for _ in range(300):
        g = rng.choice(groups)
        a, b = rng.choice(g.all_operations()), rng.choice(g.all_operations())
        prod = a * b
        want = _augmented(a) @ _augmented(b)
        assert np.allclose(np.asarray(prod.rotation), want[:3, :3])
        assert np.allclose(np.asarray(prod.m), want[3, :3])
        assert prod.epsilon == int(want[3, 3])
        got_t = np.array([float(x) for x in prod.translation] + [float(prod.delta)])
        d = got_t - np.r_[want[:3, 4], want[3, 4]]
        assert np.allclose(d - np.round(d), 0, atol=1e-12)


def test_inverse_and_action():
    op = SuperspaceOperator.from_xyz("-x2,x1-x2,x3+1/3,-x1-x2+x4+1/3")
    assert op * op.inverse() == IDENTITY
    assert op.inverse() * op == IDENTITY
    x, x4 = op.act((0.1, 0.2, 0.3), 0.4)
    assert np.allclose(x, (-0.2, -0.1, 0.3 + 1 / 3))
    assert x4 == pytest.approx(-0.3 + 0.4 + 1 / 3)


def test_de_wolff_composition_rule_tau3_is_tau1_plus_eps1_tau2():
    """de Wolff 1981 § 6 (6.1): the phase increments t′ = εt + δ − q·s of a
    product compose as τ₃ = τ₁ + ε₁τ₂.  Unreduced products, q at a rational
    point of its family, so the identity is exact."""
    rng = random.Random(3)
    cases = [(n, g) for n in (16, 33, 62, 75, 85, 129, 143, 191) for g in superspace_groups(n)]
    for n, g in rng.sample(cases, 20):
        lam = [F(rng.randint(1, 97), 101) for _ in g.q.free]
        q = g.q.value(*lam)
        ops = g.all_operations()
        for _ in range(10):
            a, b = rng.choice(ops), rng.choice(ops)
            # unreduced composition: translations not taken mod 1
            s3 = tuple(sum(a.rotation[i][k] * b.translation[k] for k in range(3))
                       + a.translation[i] for i in range(3))
            d3 = sum(a.m[k] * b.translation[k] for k in range(3)) \
                + a.epsilon * b.delta + a.delta

            def tau(delta, s):
                return delta - sum(q[i] * s[i] for i in range(3))

            assert tau(d3, s3) == tau(a.delta, a.translation) \
                + a.epsilon * tau(b.delta, b.translation)


@pytest.mark.parametrize("text, why", [
    # a time-reversal field other than ±1 (θ = ±1 itself is read, WP-1992)
    ("x1,x2,x3,x4,0", "time-reversal field is \\+1 or -1"),
    ("x1,x2,x3,x4,2", "time-reversal field is \\+1 or -1"),
    ("x1,x2,x3,x4,-1'", "time reversal twice"),
    ("x1,x2,x3,x4,x5", "d > 1"),
    ("x1,x2,x3,x4,x5,-1", "d > 1"),
    ("x1,x2,x3,x5", "d > 1"),
    ("x1+x4,x2,x3,x4", "depends on x4"),
    ("x1,x2,x3,2x4", "epsilon"),
])
def test_operation_strings_refused_by_name(text, why):
    with pytest.raises(ValueError, match=why.replace(">", ">")):
        SuperspaceOperator.from_xyz(text)


@pytest.mark.parametrize("text, theta", [
    ("x1,x2,x3,x4,-1", -1), ("x1,x2,x3,x4,+1", 1), ("x1,x2,x3,x4+1/2,-1", -1),
    ("(x+1/2,-y,-z,-t)'", -1),
])
def test_time_reversal_is_read_where_n_w1_refused_it(text, theta):
    """The two θ rows N-W1 refused now parse (WP-1992); the neighbours θ = 0,
    θ = 2 and a fifth coordinate stay refused above."""
    op = SuperspaceOperator.from_xyz(text)
    assert op.theta == theta
    assert SuperspaceOperator.from_xyz(op.xyz(magnetic=True)) == op


def test_modulation_vector_spellings():
    assert ModulationVector.parse("(00γ)") == ModulationVector.parse("(0,0,g)")
    q = ModulationVector.parse("(½½γ)")
    assert q.rational == (F(1, 2), F(1, 2), F(0)) and q.free == ((0, 0, 1),)
    q = ModulationVector.parse("(0,0,1-γ)")
    assert q.rational == (0, 0, 1) and q.free == ((0, 0, -1),)
    assert ModulationVector.parse("(α,β,0)").dimension == 2
    assert q.contains((0, 0, F(2, 3))) == (F(1, 3),)


@pytest.mark.parametrize("text, why", [
    ("(α,0,0)(0,β,0)", "more than one"),
    ("(1/2,0,0)", "commensurate"),
])
def test_modulation_vector_refusals(text, why):
    with pytest.raises(ValueError, match=why):
        ModulationVector.parse(text)


# ---------------------------------------------------------------------------
# group axioms on generated groups
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("number", [3, 5, 14, 16, 36, 62, 70, 88, 99, 125, 142, 150, 160,
                                    176, 186, 194])
def test_every_generated_group_is_a_group(number):
    for g in superspace_groups(number):
        ops = g.all_operations()
        assert len(ops) == len(set(ops)) == len(g)
        assert IDENTITY in ops
        have = set(ops)
        for a in ops:
            assert a.inverse() in have
        rng = random.Random(number)
        for _ in range(60):
            a, b, c = rng.choice(ops), rng.choice(ops), rng.choice(ops)
            assert (a * b) * c == a * (b * c)
            assert g._reduce(a * b) is not None
        # rebuilding from its own operations gives the same group
        again = SuperspaceGroup.from_operations(g.q, ops)
        assert set(again.all_operations()) == have


def test_a_non_closing_set_is_refused():
    """δ(2) = ¼ on a two-fold with ε = +1: its square is the identity with an
    internal translation ½, which no superspace group has."""
    ops = (IDENTITY, SuperspaceOperator.from_xyz("-x1,-x2,x3,x4+1/4"))
    with pytest.raises(ValueError, match="do not close"):
        SuperspaceGroup(ModulationVector.parse("(0,0,γ)"), ops)


def test_an_operation_inconsistent_with_q_is_refused():
    ops = (IDENTITY, SuperspaceOperator.from_xyz("-x1,-x2,x3,-x4"))
    with pytest.raises(ValueError, match="free direction"):
        SuperspaceGroup(ModulationVector.parse("(0,0,γ)"), ops)


def test_number_is_written_only_by_the_caller():
    """``SuperspaceGroup.number`` has one writer, the caller (#682 review,
    follow-up 1).  16.1.9.1 is P222(0,0,γ)000's four-part number as Stokes &
    Campbell 2022 (Acta Cryst. A78, 364, p. 366) quote it; it is carried
    verbatim, and nothing the package derives from the group invents one."""
    gens = ("-x1,-x2,x3,x4", "x1,-x2,-x3,-x4")
    g = SuperspaceGroup.from_operations("(0,0,γ)", gens, number="16.1.9.1")
    assert g.number == "16.1.9.1"
    assert SuperspaceGroup.from_operations("(0,0,γ)", gens).number is None
    assert g.transformed(SuperspaceTransform.build(s_eps=-1)).number is None
    assert all(h.number is None for h in superspace_groups(16))


# ---------------------------------------------------------------------------
# generation: counts from print
# ---------------------------------------------------------------------------
#: Basic groups whose total is fixed in print.  P222: the four FSSGs
#: 16.1.9.1, 16.1.9.2, 16.1.10.3, 16.1.11.4 (Stokes & Campbell 2022 p. 369).
#: The tetragonal rows: Stokes 2011 Table 9 (p. 54) numbers a group N.1.20.i
#: in class 20 = P4/mmm(½½γ), the last class a primitive tetragonal group has,
#: so i is that basic group's total.
PRINTED_TOTALS = {16: 4, 99: 6, 101: 4, 104: 3, 106: 3, 123: 6, 126: 3, 132: 4}

#: Lower bounds from the same table (classes 14 and 18 are not the last).
PRINTED_AT_LEAST = {35: 5, 36: 4, 37: 4, 42: 5}


@pytest.mark.parametrize("number, total", sorted(PRINTED_TOTALS.items()))
def test_printed_totals(number, total):
    assert count_superspace_groups([number])[number] == total


@pytest.mark.parametrize("number, least", sorted(PRINTED_AT_LEAST.items()))
def test_printed_lower_bounds(number, least):
    assert count_superspace_groups([number])[number] >= least


def test_de_wolff_pedigree_in_class_w_p4mmm():
    """de Wolff 1981 § 6, pp. 635-636: with q = (½½γ), P4 has two groups
    (75.20.1 with τ = 0, 75.20.2 with τ = ¼), P4/n one (85.20.3) and P4/nbm
    two (125.20.5/6), whose bottom lines are q1̄q1 and q1̄qs."""
    q = "(1/2,1/2,γ)"
    assert sorted(symbol(g) for g in generate("P 4", q)) == [
        "P4(1/2,1/2,γ)0", "P4(1/2,1/2,γ)q"]
    assert [symbol(g) for g in generate("P 4/n:2", q)] == ["P4/n(1/2,1/2,γ)q0"]
    assert sorted(symbol(g) for g in generate("P 4/n b m:2", q)) == [
        "P4/nbm(1/2,1/2,γ)q0q0", "P4/nbm(1/2,1/2,γ)q0qs"]


def test_an_incompatible_q_gives_no_group():
    """P4₂2₁2 with q = (½½γ): the 2₁ along a squares to a lattice translation
    with internal part ½, so closure has no solution."""
    assert generate("P 42 21 2", "(1/2,1/2,γ)") == []
    assert generate("P 4", "(α,0,0)") == []


@pytest.mark.slow
def test_775_superspace_groups_from_the_230_basic_groups():
    counts = count_superspace_groups()
    assert sum(counts.values()) == N_SUPERSPACE_GROUPS_D1 == 775
    # no (3+1)D group has a cubic basic group: no direction is invariant
    assert all(counts[n] == 0 for n in range(195, 231))


@pytest.mark.slow
def test_24_bravais_classes():
    classes = bravais_classes()
    assert len(classes) == N_BRAVAIS_CLASSES_D1 == 24
    # the hexagonal-lattice class only a trigonal holohedry keeps (de Wolff
    # 1981 Table 1) and the two of the I-centred and F-centred lattices
    for label in ("P-31m(1/3,1/3,γ)", "Immm(0,0,γ)", "I4/mmm(0,0,γ)",
                  "Fmmm(0,0,γ)", "Fmmm(0,1,γ)", "R-3m(0,0,γ)"):
        assert label in classes


@pytest.mark.slow
def test_catalogue_symbols_are_distinct_and_parse_back():
    groups = catalogue()
    assert len(groups) == 775
    symbols = [g.symbol for g in groups]
    assert len(set(symbols)) == 775
    for g in groups[::7]:
        back = parse_symbol(g.symbol)
        assert equivalent(back, g)
        assert symbol(back) == g.symbol


# ---------------------------------------------------------------------------
# symbols
# ---------------------------------------------------------------------------
def _find_description(conv: str):
    import re

    import gemmi

    hm, q = re.match(r"(.*?)(\(.*\))", conv).groups()
    sg = gemmi.find_spacegroup_by_name(hm.replace("_", ""))
    for members in family_orbits(sg, q):
        for g in members:
            printed, admissible = symbol_candidates(g)
            if printed == conv:
                return g, admissible
    raise AssertionError(f"no description prints as {conv}")


#: Stokes 2011 § 5.2.5: "For eight of these SSGs, our method found a 'nicer'
#: symbol. For the remaining three SSGs, our method could not obtain the
#: symbol in ITC-C without using EITs that did not strictly match."
NOT_STRICT = {"104.1.20.3", "106.1.20.3", "126.1.20.3"}


@pytest.mark.parametrize("conv", sorted(ITC_C_EXCEPTIONS))
def test_table9_exceptions(conv):
    """Stokes 2011 Table 9, p. 54: the conventions' spelling is what the
    printer reaches, ITC-C's is what :func:`symbol` returns, and ITC-C's is a
    strictly-matching candidate exactly for the eight 'nicer' cases."""
    itc, number = ITC_C_EXCEPTIONS[conv]
    g, admissible = _find_description(conv)
    assert symbol(g) == itc
    assert (itc in admissible) == (number not in NOT_STRICT)
    assert equivalent(parse_symbol(itc), parse_symbol(conv))


def test_table9_split_is_eight_and_three():
    assert len(ITC_C_EXCEPTIONS) == 11 and len(NOT_STRICT) == 3


#: Symbols in print, (3+1)D or the non-magnetic family group of a grey
#: magnetic one (drop the 1′ and its trailing letter, Stokes & Campbell 2022
#: p. 366).  Sources: Orlov et al. 2008 Tables 1, 3 and Fig. 2 (pp. 1183-1185);
#: Stokes 2011 p. 51 (P42₁2); Stokes & Campbell 2022 Tables 1, 3 (p. 366-367);
#: Stokes, Campbell & Hatch 2007, Acta Cryst. A63, 365, p. 370; Gallego et
#: al. 2016, J. Appl. Cryst. 49, 1941, p. 1953; Perez-Mato et al. 2015, Annu.
#: Rev. Mater. Res. 45, 217, p. 238; Petříček et al. 2023, Z. Kristallogr.
#: 238, 271, p. 279; Yamamoto et al. 1985 § 2.
PRINTED_SYMBOLS = [
    "Pbnm(00γ)s00", "Amam(00γ)s00", "P6_3/mcm(00γ)00ss", "P6_3/mmc(00γ)00ss",
    "P42_12(0,0,γ)000", "P222(0,0,γ)000", "P222(0,0,γ)00s", "I222(0,0,γ)00s",
    "B112(00γ)s", "Fdd2(00γ)s0s", "I2_12_12_1(00γ)00s", "R3(00γ)t",
    "I4/mmm(00γ)00ss", "I4(00γ)q", "I422(00γ)q00", "Immm(00γ)s00",
    "P2_12_12_1(00γ)00s", "P321(00γ)000", "P422(½½γ)q00", "R32(00γ)t0",
    "R3c(00γ)00", "Pbam(α00)0s0", "C222(00γ)000", "C222(00γ)00s",
    "Cmm2(00γ)000", "Cmm2(00γ)0ss", "Cmm2(00γ)s0s", "Cmm2(00γ)ss0",
    "Cmmm(00γ)000", "Cmmm(00γ)0s0", "Cmmm(00γ)s00", "Cmmm(00γ)ss0",
    "P6(00γ)h", "P6(00γ)t", "P6/mmm(00γ)0000", "P6/mmm(00γ)00ss",
    "P6/mmm(00γ)s00s", "P6/mmm(00γ)s0s0", "P622(00γ)h00", "P622(00γ)t00",
    "P6mm(00γ)000", "P6mm(00γ)0ss", "P6mm(00γ)s0s", "P6mm(00γ)ss0",
    "I2cb(00γ)0s0",
]


def _normal(text: str) -> str:
    return (text.replace("(00γ)", "(0,0,γ)").replace("(½½γ)", "(1/2,1/2,γ)")
            .replace("(α00)", "(α,0,0)"))


@pytest.mark.parametrize("text", PRINTED_SYMBOLS)
def test_printed_symbols_parse_and_print_back(text):
    g = parse_symbol(text)
    assert symbol(g) == _normal(text)


def test_a_printed_symbol_that_is_admissible_but_not_the_nicest():
    """Gallego et al. 2016 p. 1953 print P3(⅓⅓γ)t (from P31′(⅓⅓γ)ts).  The
    one group over P3 with that q admits 0, t and t̄ (an integer translation
    moves τ by q_r·n = ⅓), and Stokes 2011 step 4 prints 0; the string still
    parses, to that group."""
    g = parse_symbol("P3(1/3,1/3,γ)t")
    printed, admissible = symbol_candidates(g)
    assert printed == "P3(1/3,1/3,γ)0"
    assert "P3(1/3,1/3,γ)t" in admissible
    assert len(generate("P 3", "(1/3,1/3,γ)")) == 1


@pytest.mark.parametrize("text, why", [
    ("Pbnm", "no modulation vector"),
    ("Pbnm(00γ)s00(α00)00", "second modulation vector"),
    # a type-2/4 symbol needs one letter per generator plus one for 1′
    ("Pbnm1'(00γ)s00", "one per generator plus one"),
    ("Pbnm(00γ)s0", "letters"),
    # an ε = −1 generator (the mirror normal to c, q ∥ c) always prints 0
    ("Pbnm(00γ)00s", "no superspace group"),
    ("Pbnm(00γ)x00", "cannot read"),
])
def test_symbol_refusals(text, why):
    with pytest.raises(ValueError, match=why):
        parse_symbol(text)


# ---------------------------------------------------------------------------
# equivalence
# ---------------------------------------------------------------------------
def _letters_as_read(group: SuperspaceGroup) -> list[str]:
    """The bottom line read naively: for each symbol generator, δ of the
    operation whose external intrinsic translation is the letter's, with q's
    free part taken as the irrational parameter (q_r = 0) — how a reader
    without the reflection conditions would read a symbol."""
    sg = _setting_of(group)
    out = []
    for pos in _positions(sg):
        vals = set()
        for op in group.all_operations():
            if op.rotation != pos.rotation:
                continue
            if op.epsilon == -1:
                vals.add(F(0))
                continue
            for n in product(range(2), repeat=3):
                v = tuple(op.translation[i] + n[i] for i in range(3))
                if _expected(pos, _eit(op.rotation, v), None):
                    vals.add(op.delta)
        assert len(vals) == 1
        out.append({F(0): "0", F(1, 2): "s"}[vals.pop()])
    return out


def test_yamamoto_1985_i2cb_reindexed_reads_as_the_other_group():
    """Yamamoto et al. 1985 § 2, p. 529: I2cb(00γ)0s0 re-indexed with
    q′ = (1−γ)c* has reflection condition h+k+l+m = 2n (a centring with an
    internal ½) and its c glide now carries no internal translation, so its
    bottom line reads as that of the *non-equivalent* I2cb(00γ)000."""
    g1 = parse_symbol("I2cb(00γ)0s0")
    g2 = parse_symbol("I2cb(00γ)000")
    h = g1.transformed(SuperspaceTransform.build(s_eps=-1, s_m=(0, 0, 1)))
    assert h.q.label() == "(0,0,1-γ)"
    assert any(c.delta == F(1, 2) for c in h.centerings)
    assert _letters_as_read(g1) == ["0", "s", "0"]
    assert _letters_as_read(h) == _letters_as_read(g2) == ["0", "0", "0"]
    assert equivalent(h, g1)
    assert not equivalent(h, g2)
    assert not equivalent(g1, g2)


def test_a_planted_internal_shift_on_epsilon_minus_one_is_normalised_away():
    """de Wolff 1981 p. 635: the τ of an ε = −1 element can be taken as zero
    by the internal origin; moving the origin by ⅙ plants ⅓ on every ε = −1
    operation and nothing on the others."""
    g = parse_symbol("Pbnm(00γ)s00")
    planted = g.transformed(SuperspaceTransform.build(s_delta=F(1, 6)))
    before = {o.rotation: o for o in g.operations}
    for o in planted.operations:
        shift = (o.delta - before[o.rotation].delta) % 1
        assert shift == (F(1, 3) if o.epsilon == -1 else 0)
    assert set(planted.all_operations()) != set(g.all_operations())
    assert equivalent(planted, g)
    assert standardised(planted).operations == standardised(g).operations


def test_an_internal_shift_on_epsilon_plus_one_is_not_removable():
    """The positive arm of the test above: an ε = +1 internal translation is
    origin-invariant (de Wolff 1981 eq. (3.8)), so changing the b glide's τ
    gives a different group."""
    g = parse_symbol("Pbnm(00γ)s00")
    other = parse_symbol("Pbnm(00γ)000")
    assert not equivalent(g, other)


def test_a_change_of_cell_and_q_plus_h_are_equivalences():
    """van Smaalen, Campbell & Stokes 2013 conclusions: a change of basic cell
    and q → q + H are equivalences.  Pbnm(00γ)s00 is a cab setting of Pnma;
    taken to Pnma's own axes, q lies along b and the group compares equal."""
    g = parse_symbol("Pbnm(00γ)s00")
    # (a', b', c') = (b, c, a) brings P b n m to P n m a
    to_pnma = SuperspaceTransform.build(((0, 1, 0), (0, 0, 1), (1, 0, 0)))
    h = g.transformed(to_pnma)
    assert h.q.label() == "(0,β,0)"
    assert equivalent(g, h)
    # q → q + c*: the same group with the 2₁ along c spelled s (as Gallego et
    # al. 2016 and Stokes et al. 2007 print P2₁2₁2₁(00γ)00s) or 0
    a = parse_symbol("P2_12_12_1(00γ)00s")
    (b,) = generate("P 21 21 21", "(0,0,γ)")
    assert symbol(b) == "P2_12_12_1(0,0,γ)000"
    assert equivalent(a, b)
    c = a.transformed(SuperspaceTransform.build(s_m=(0, 0, 1)))
    assert c.q.label() == "(0,0,1+γ)"
    # equal to b on every ε = +1 operation; the ε = −1 ones differ by an
    # internal-origin shift
    def plus(g):
        return {o.rotation: o.delta for o in g.operations if o.epsilon == 1}

    assert plus(c) == plus(b) and plus(a) != plus(b)


def test_canonical_key_separates_basic_groups_with_equal_representatives():
    """Immm and Pmmm have identical coset representatives; the key carries the
    basic group's type, so their symmorphic groups do not collide."""
    a = generate("P m m m", "(0,0,γ)")[0]
    b = generate("I m m m", "(0,0,γ)")[0]
    assert canonical_key(a) != canonical_key(b)


# ---------------------------------------------------------------------------
# commensurate sections (Orlov et al. 2008)
# ---------------------------------------------------------------------------
def _t0_classes(n):
    """Orlov Tables 1, 3 columns: general, n/N, 1/4N, 1/2N, 3/4N (n = 0)."""
    return [F(1, 10 * n), F(0), F(1, 4 * n), F(1, 2 * n), F(3, 4 * n)]


#: (γ, the five section groups by International number) — Orlov 2008 Table 1
#: (Pbnm(00γ)s00, p. 1183) and Table 3 (Amam(00γ)s00, p. 1185), parity rows,
#: two or more γ per row.  P2₁ 4, Pn 7, P2₁/m 11, P2₁/n 14, P2₁2₁2₁ 19,
#: P2₁nm and Pn2₁m 31; Aa 9, A2/a 15, A2₁am 36, Pca2₁ 29, Pcam 57, Pcab 61,
#: Pna2₁ 33, Pnab 60, Pnam 62.
ORLOV = [
    ("Pbnm(00γ)s00", F(1, 3), (4, 11, 19, 11, 19)),
    ("Pbnm(00γ)s00", F(3, 5), (4, 11, 19, 11, 19)),
    ("Pbnm(00γ)s00", F(2, 3), (7, 14, 31, 14, 31)),
    ("Pbnm(00γ)s00", F(4, 5), (7, 14, 31, 14, 31)),
    ("Pbnm(00γ)s00", F(1, 4), (7, 14, 31, 14, 31)),
    ("Pbnm(00γ)s00", F(1, 6), (7, 14, 31, 14, 31)),
    ("Amam(00γ)s00", F(2, 3), (9, 15, 36, 15, 36)),
    ("Amam(00γ)s00", F(4, 5), (9, 15, 36, 15, 36)),
    ("Amam(00γ)s00", F(1, 4), (29, 57, 61, 57, 61)),
    ("Amam(00γ)s00", F(1, 2), (29, 57, 61, 57, 61)),
    ("Amam(00γ)s00", F(1, 3), (33, 60, 62, 60, 62)),
    ("Amam(00γ)s00", F(1, 1), (33, 60, 62, 60, 62)),
]


@pytest.mark.parametrize("text, gamma, want", ORLOV)
def test_orlov_sections(text, gamma, want):
    g = parse_symbol(text)
    got = tuple(g.section((0, 0, gamma), t0).number for t0 in _t0_classes(gamma.denominator))
    assert got == want


def _two_fold_axes(section):
    axes = set()
    for r, _ in section.operations:
        m = np.asarray(r)
        if round(np.linalg.det(m)) == 1 and np.trace(m) == -1:
            axes.add(int(np.argmax(np.diag(m))))
    return axes


def test_orlov_distinguishes_p21nm_from_pn21m_by_the_screw_axis():
    """Table 1's 1/4N column: P2₁nm for M even, N odd and Pn2₁m for M odd,
    N even — the same type, the two-fold along a or along b in the parent's
    basis ("the three-dimensional derivatives inherit the basis")."""
    g = parse_symbol("Pbnm(00γ)s00")
    assert _two_fold_axes(g.section((0, 0, F(2, 3)), F(1, 12))) == {0}
    assert _two_fold_axes(g.section((0, 0, F(1, 4)), F(1, 16))) == {1}


def test_section_depends_on_the_group_not_only_on_q():
    """The positive arm: Pbnm(00γ)000 at the same (q, t₀) gives other groups
    than Pbnm(00γ)s00, so the table rows are not a property of q alone."""
    g = parse_symbol("Pbnm(00γ)000")
    got = tuple(g.section((0, 0, F(1, 3)), t0).number for t0 in _t0_classes(3))
    assert got != (4, 11, 19, 11, 19)


def test_section_refuses_q_outside_the_family():
    g = parse_symbol("Pbnm(00γ)s00")
    with pytest.raises(ValueError, match="not a member"):
        g.section((F(1, 2), 0, F(1, 3)), 0)
