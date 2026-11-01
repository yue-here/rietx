"""The real-k door and the (magnetic) superspace group of an irrep (WP-1992 commit B).

* **The door** (`representation/irreps.py`): the nine lines of WP-1992's
  spgrep check (recorded in the WP's handover log) as unit tests.  spgrep
  0.7.0's G_k at an irrational λ is the oracle (dev-only, names end in
  ``_oracle``); the hand rule (Rᵀd = ±d, Rᵀr ∓ r ∈ L*) is the
  reference for G_{k,−k}, where spgrep's ``real=True`` declines on six of the
  nine lines and is never used.  Two planted controls: a near-rational λ must
  not snap, and dropping the factor system must change the irreps.
* **The irrep's group** (`representation/incommensurate.py`): the N = 1 rule
  against Stokes & Campbell (2022) Tables 1-2 over P222(0,0,γ) (group-level
  pins: they pass with the shift's sign wrong); SrFeO₃'s six MSSGs (Gallego
  et al. 2016, *J. Appl. Cryst.* **49**, 1941, Fig. 6, read from the page
  image); the polar-axial internal-shift sign pin on P4 and P6₃; CaFe₄As₃'s Pnma (0,λ,0) at the group level.
"""

from __future__ import annotations

import cmath
import dataclasses
import math
from fractions import Fraction as F

import numpy as np
import pytest

from rietx.crystallography.representation import incommensurate as inc
from rietx.crystallography.representation import irreps as ir
from rietx.crystallography.superspace import (
    SuperspaceTransform,
    equivalent,
    magnetic_superspace_groups,
    maximal_subgroup,
    parse_symbol,
    symbol,
)
from rietx.crystallography.superspace.operators import _inverse3

H, T = F(1, 2), F(1, 3)

#: The nine lines of the step-0 spike: (space group, line, irrational λ,
#: |P_k|, small-irrep dimensions), as measured there and printed in its table.
LINES = [
    ("P n m a", "(0,0,γ)", 1 / math.sqrt(5), 4, [1, 1, 1, 1]),
    ("P n m a", "(1/2,0,γ)", 1 / math.sqrt(5), 4, [1, 1, 1, 1]),
    ("P n m a", "(0,γ,0)", (math.sqrt(5) - 1) / 4, 4, [1, 1, 1, 1]),
    ("P 63/m m c", "(0,0,γ)", 1 / math.sqrt(7), 12, [1, 1, 1, 1, 2, 2]),
    ("P 63/m m c", "(1/3,1/3,γ)", 1 / math.sqrt(7), 6, [1, 1, 2]),
    ("I 4/m m m", "(α,α,0)", 1 / math.sqrt(11), 4, [1, 1, 1, 1]),
    ("I 4/m m m", "(0,0,γ)", 1 / math.sqrt(11), 8, [1, 1, 1, 1, 2]),
    ("P n m a", "(0,1/2,γ)", 1 / math.sqrt(5), 4, [2]),
    ("P 4/n c c", "(1/2,1/2,γ)", 1 / math.sqrt(5), 8, [1, 1, 1, 1, 2]),
]


def _hand(sg, q, *, pm):
    """The hand rule of the step-0 spike, independent of the door's code:
    Rᵀd = d (or −d) and Rᵀr ∓ r ∈ L*, on gemmi's representatives."""
    from rietx.crystallography.superspace import ModulationVector

    qv = ModulationVector.parse(q)
    g = ir._resolve(sg)
    cens = ir._centrings(g)
    keep = []
    for i, op in enumerate(g.operations().sym_ops):
        r = ir._op_rotation(op)
        rt = [lambda v: tuple(sum(F(int(r[a][b])) * v[a] for a in range(3)) for b in range(3))][0]
        for eps in ((1, -1) if pm else (1,)):
            if all(rt(tuple(F(x) for x in d)) == tuple(eps * F(x) for x in d) for d in qv.free) \
                    and ir._is_reciprocal_lattice_vector(
                        tuple(a - eps * b for a, b in zip(rt(qv.rational), qv.rational)), cens):
                keep.append(i)
                break
    return tuple(keep)


# ---------------------------------------------------------------------------
# the door
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sg, q, lam, order, dims", LINES)
def test_line_little_group_matches_the_hand_rule_and_its_irreps_the_step0_table(
        sg, q, lam, order, dims):
    lg = ir.little_group_on_line(sg, q, lambdas=lam)
    assert lg.indices == _hand(sg, q, pm=False) and lg.order == order
    assert not lg.has_minus_k
    irr = ir.small_irreps_of(lg)
    assert sorted(x.dimension for x in irr) == dims
    ext, eps = ir.extended_little_group_on_line(sg, q)
    assert ext.indices == _hand(sg, q, pm=True) and ext.order == 2 * order
    assert eps.count(-1) == order
    assert len(ir.star_on_line(sg, q)) * order == len(ir._resolve(sg).operations().sym_ops)


@pytest.mark.parametrize("sg, q, lam, order, dims", LINES)
def test_line_little_group_and_characters_oracle(sg, q, lam, order, dims):
    """spgrep 0.7.0 is the G_k oracle at an irrational λ: the same operations
    by index, and the same characters once each representative's lattice
    shift (gemmi's conventional v against the primitive one) is put back."""
    spgrep = pytest.importorskip("spgrep")
    lg = ir.little_group_on_line(sg, q, lambdas=lam)
    rots, trans = ir.primitive_operations(sg)
    m = ir.primitive_basis(sg)
    kconv = lg.k_value
    kprim = np.array([sum(float(m[i][j]) * kconv[j] for j in range(3)) for i in range(3)])
    irr_sp, mapping = spgrep.get_spacegroup_irreps_from_primitive_symmetry(
        rots, np.array([[float(c) for c in t] for t in trans]), kprim)
    assert tuple(int(x) for x in mapping) == lg.indices
    # a = v_conv − Mᵀ v_prim, so D_spgrep = e^{+2πik·a} D_ours
    phase = []
    for i, idx in enumerate(lg.indices):
        vp = trans[idx]
        back = tuple(sum(m[r][c] * vp[r] for r in range(3)) for c in range(3))
        a = [float(lg.translations[i][c] - back[c]) for c in range(3)]
        phase.append(cmath.exp(2j * math.pi * float(np.dot(kconv, a))))
    ours = sorted(tuple(np.round(np.array(phase) * np.einsum("gii->g", x.matrices), 6) + 0.0)
                  for x in ir.small_irreps_of(lg))
    theirs = sorted(tuple(np.round(np.einsum("gii->g", d), 6) + 0.0) for d in irr_sp)
    assert len(ours) == len(theirs)
    assert all(np.allclose(a, b, atol=1e-6) for a, b in zip(ours, theirs))


def test_planted_snap_is_refused_by_construction():
    """λ = ½ + 1e-10 on Pnma (0,0,λ): the declared line keeps its order-4
    group, where the rational point ½ has order 8 — and where a float
    tolerance (spgrep's, measured in step 0) would have snapped."""
    lg = ir.little_group_on_line("P n m a", "(0,0,γ)", lambdas=0.5 + 1e-10)
    assert lg.order == 4
    assert ir.little_group("P n m a", (0, 0, H)).order == 8
    ir.small_irreps_of(lg)


def test_planted_snap_oracle():
    """Positive arm of the control above: spgrep snaps at the same float."""
    spgrep = pytest.importorskip("spgrep")
    rots, trans = ir.primitive_operations("P n m a")
    _, mapping = spgrep.get_spacegroup_irreps_from_primitive_symmetry(
        rots, np.array([[float(c) for c in t] for t in trans]), np.array([0, 0, 0.5 + 1e-10]))
    assert len(mapping) == 8


def test_planted_dropped_factor_system_changes_the_irreps():
    """Pnma (0,½,λ): the projective factor system gives one 2-D irrep; the
    ordinary irreps of the co-group (ω ≡ 1) are four 1-D ones."""
    lg = ir.little_group_on_line("P n m a", "(0,1/2,γ)", lambdas=1 / math.sqrt(5))
    assert [x.dimension for x in ir.small_irreps_of(lg)] == [2]
    ordinary = ir.small_irreps_of(lg, factor=np.ones((lg.order, lg.order)))
    assert sorted(x.dimension for x in ordinary) == [1, 1, 1, 1]


def test_door_refusals():
    with pytest.raises(ValueError, match="little_group_on_line"):
        ir.as_kvector((0, 0, 1 / math.sqrt(5)))
    lg = ir.little_group_on_line("P 63/m m c", "(0,0,γ)")
    with pytest.raises(ValueError, match="lambdas"):
        ir.factor_system(lg)
    ext, _ = ir.extended_little_group_on_line("P n m a", "(0,0,γ)", lambdas=0.3)
    with pytest.raises(ValueError, match="G_k"):
        ir.factor_system(ext)
    # the commensurate door and its constants are unchanged
    assert ir.K_MAX_DENOMINATOR == 64 and ir.K_FLOAT_TOL == 1e-9


def test_superspace_does_not_import_representation():
    """The line rule lives in superspace/ and representation/ imports it,
    never the reverse: one criterion, one dependency direction."""
    import ast
    import pathlib

    import rietx.crystallography.superspace as ss

    root = pathlib.Path(ss.__file__).parent
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
                assert not any("representation" in n for n in names), path


# ---------------------------------------------------------------------------
# the rule, and N = 1
# ---------------------------------------------------------------------------
def test_the_action_is_a_homomorphism_of_superspace_operations():
    """(g, θ, δ) ↦ its matrix on the order parameter composes as the
    superspace product (θ₁θ₂, δ_c = M_a·v_b + ε_aδ_b + δ_a), ε = −1 cosets
    and a rational part of q included."""
    rng = np.random.default_rng(1)
    for sg, q in (("P m -3 m", "(γ,γ,γ)"), ("P n m a", "(0,1/2,γ)"), ("P 63/m m c", "(0,0,γ)"),
                  ("P 63/m m c", "(1/3,1/3,γ)"), ("I 4/m m m", "(0,0,γ)")):
        for irr in inc.line_irreps(sg, q, [1 / math.sqrt(7)]):
            lop = inc.line_order_parameter(irr)
            n = len(lop.epsilons)
            for _ in range(30):
                a = (int(rng.integers(n)), int(rng.choice((1, -1))), F(int(rng.integers(24)), 24))
                b = (int(rng.integers(n)), int(rng.choice((1, -1))), F(int(rng.integers(24)), 24))
                ab = inc._reduce(lop, inc.superspace_operation(lop, *a)
                                 * inc.superspace_operation(lop, *b))
                assert np.allclose(inc.operation_matrix(lop, *a) @ inc.operation_matrix(lop, *b),
                                   inc.operation_matrix(lop, *ab), atol=1e-8)


def test_an_irrep_paired_with_another_at_minus_k_is_refused_by_name():
    """Pnma (½,0,γ): g₀ ∈ G_{k,−k} carries each 1-D irrep's −k image onto a
    different one (S1 ↔ S4, S2 ↔ S3), so the real order parameter is
    D ⊕ D′; refused rather than built as if it were 2N-dimensional."""
    for irr in inc.line_irreps("P n m a", "(1/2,0,γ)", [1 / math.sqrt(7)]):
        with pytest.raises(NotImplementedError, match="different small irrep"):
            inc.line_order_parameter(irr)


def test_n1_rule_over_p222_is_in_the_commit_a_list():
    """Every 1-D magnetic irrep of P222 at (0,0,γ) gives an MSSG that the
    enumerator over its maximal subgroup returns (Stokes & Campbell 2022
    Table 2); the isotropy route gives the same single group.  Group-level
    only: in P222 every shift is 0 or ½."""
    irr = inc.line_irreps("P 2 2 2", "(0,0,γ)", [1 / math.sqrt(5)])
    got = set()
    for x in irr:
        lop = inc.line_order_parameter(x)
        g = inc.n1_superspace_group(lop)
        iso = inc.isotropy_superspace_groups(lop)
        assert len(iso) == 1 and equivalent(iso[0].group, g)
        listed = magnetic_superspace_groups(maximal_subgroup(g), types=(2, 4))
        assert sum(equivalent(g, m) for m in listed) == 1
        got.add(symbol(g))
        disp = inc.n1_superspace_group(inc.line_order_parameter(x, kind="displacive"))
        assert not disp.is_magnetic and equivalent(disp, maximal_subgroup(g))
    assert got == {"P222.1'(0,0,γ)000s", "P222.1'(0,0,γ)00ss"}


@pytest.mark.parametrize("sg, n_free", [("P 1 21/c 1", 2), ("P 1 2/m 1", 2), ("P -1", 3)])
def test_n1_route_widens_q_to_the_groups_family_like_the_isotropy_route(sg, n_free):
    """A line declared (0,0,γ) in a group whose point operations allow a wider
    q family (Pérez-Mato et al. 2012, the printed symbols: P12_1/c1(α,0,γ),
    P-1(αβγ)) gives one group by either route: same q, same operators, a
    symbol that parses back to it."""
    checked = 0
    for x in inc.line_irreps(sg, "(0,0,γ)", [1 / math.sqrt(7)]):
        lop = inc.line_order_parameter(x)
        n1 = inc.n1_superspace_group(lop)
        iso = inc.isotropy_superspace_groups(lop)
        assert len(iso) == 1
        assert n1.q == iso[0].group.q
        assert len(n1.q.free) == n_free
        assert equivalent(n1, iso[0].group)
        assert equivalent(parse_symbol(symbol(n1)), n1)
        checked += 1
    assert checked


# ---------------------------------------------------------------------------
# the polar-axial internal-shift sign pin
# ---------------------------------------------------------------------------
def _orbit_amplitudes(lop, r1, m0):
    """A rietx Bloch-side field transforming by the irrep (projection over
    G_k onto a general orbit), and its full-position amplitudes A_μ — the
    coefficients of e^{+2πi x̄₄}, x̄₄ = k·(l + r_μ) (Perez-Mato 2012 eq. (1);
    Petříček et al. 2010 eq. (10))."""
    little = lop.irrep.little
    k = little.k_value
    out = []
    for i, r in enumerate(little.rotations):
        r = np.asarray(r, dtype=float)
        pos = r @ r1 + np.array([float(x) for x in little.translations[i]])
        field = np.conj(lop.irrep.matrices[i][0, 0]) * (np.linalg.det(r) * r @ m0)
        out.append((i, pos, field * cmath.exp(-2j * math.pi * float(k @ pos))))
    return out


@pytest.mark.parametrize("sg", ["P 4", "P 63"])
def test_polar_axial_internal_shift_sign(sg):
    """The door's δ against Perez-Mato 2012 eq. (5) on amplitudes: for each
    operation of G_k mapping atom 1 to atom μ, A_μ e^{2πiδ} = θ det(R) R A_1.
    On P4 (D(4) = ±i, a ¼ shift, no screw part) and P6₃ (⅓ and ⅙ shifts with
    the k·v of the 6₃ screw) it holds with the door's sign, and a planted
    sign flip fails it on every irrep with a shift other than 0 or ½.  The
    groups from D and D* are equivalent (q → −q), which is why the group-level
    pins cannot see this."""
    r1 = np.array([0.13, 0.27, 0.31])
    m0 = np.array([0.4, -0.7, 0.55])
    flipped_fail = 0
    for irr in inc.line_irreps(sg, "(0,0,γ)", [1 / math.sqrt(7)]):
        lop = inc.line_order_parameter(irr)
        amps = _orbit_amplitudes(lop, r1, m0)
        a1 = amps[0][2]
        sign_bad = False
        for i, _, a_mu in amps:
            delta = inc.internal_translation(lop, i)
            r = np.asarray(irr.little.rotations[i], dtype=float)
            assert np.allclose(a_mu * cmath.exp(2j * math.pi * float(delta)),
                               np.linalg.det(r) * r @ a1, atol=1e-9)
            sign_bad |= not np.allclose(a_mu * cmath.exp(-2j * math.pi * float(delta)),
                                        np.linalg.det(r) * r @ a1, atol=1e-9)
        flipped_fail += sign_bad
        conj = inc.n1_superspace_group(lop)
        assert equivalent(conj, parse_symbol(symbol(conj)))
    assert flipped_fail == {"P 4": 2, "P 63": 4}[sg]


def test_polar_axial_shifts_are_printed_with_their_sign():
    shifts = {}
    for irr in inc.line_irreps("P 4", "(0,0,γ)", [1 / math.sqrt(7)]):
        lop = inc.line_order_parameter(irr)
        four = next(i for i, r in enumerate(irr.little.rotations)
                    if np.array_equal(r, [[0, -1, 0], [1, 0, 0], [0, 0, 1]]))
        shifts[complex(np.round(irr.matrices[four][0, 0], 9))] = (
            inc.internal_translation(lop, four), symbol(inc.n1_superspace_group(lop)))
    assert shifts[1j] == (F(1, 4), "P4.1'(0,0,γ)qs")
    assert shifts[-1j] == (F(3, 4), "P4.1'(0,0,γ)-qs")
    a, b = (parse_symbol(s) for _, s in (shifts[1j], shifts[-1j]))
    assert equivalent(a, b)              # D and D*: one group under q → −q


# ---------------------------------------------------------------------------
# SrFeO₃: Gallego et al. 2016 § 4 and Fig. 6
# ---------------------------------------------------------------------------
def _cell(columns):
    b = [[F(columns[j][i]) for j in range(3)] for i in range(3)]
    return SuperspaceTransform.build(_inverse3(b))


#: Gallego et al. 2016 Fig. 6 (p. 1951), read from the page image
#: (journal p. 1951, a 500-dpi crop): the symbol as printed,
#: (n, m), and the cells its setting may need from the cubic one.
_HEX = (((1, -1, 0), (0, 1, -1), (1, 1, 1)),)
#: b along each two-fold ⊥ [111], a in the mirror, c along a cubic axis:
#: a C-centred cell with q in its ac plane (the class representative's
#: two-fold may lie along any of the three)
_MONO = (((1, 1, 0), (1, -1, 0), (0, 0, 1)), ((0, 1, 1), (0, 1, -1), (1, 0, 0)),
         ((1, 0, 1), (-1, 0, 1), (0, 1, 0)))
_ID = (((1, 0, 0), (0, 1, 0), (0, 0, 1)),)
FIG6 = [
    ("R321'(00γ)t0s", (1, 0), _HEX),
    ("C2/m1'(α0γ)00s", (1, 0), _MONO),
    ("C2/m1'(α0γ)0ss", (1, 1), _MONO),
    ("C21'(α0γ)0s", (2, 1), _MONO),
    ("P-11'(αβγ)0s", (2, 1), _ID),
    ("P11'(αβγ)0s", (4, 2), _ID),
]


def _in_setting(group, cells, printed):
    """``group`` in the first cell where it is equivalent to ``printed``."""
    for cell in cells:
        try:
            g = group.transformed(_cell(cell))
            if equivalent(g, printed):
                return g
        except ValueError:
            # this orientation does not bring the two-fold onto b
            continue
    return None


@pytest.fixture(scope="module")
def srfeo3():
    """The SrFeO₃ order parameter's isotropy groups (built once per worker).

    **Consumers must carry** ``@pytest.mark.xdist_group("srfeo3-isotropy")``,
    or a second worker rebuilds it."""
    irr = inc.line_irreps("P m -3 m", "(γ,γ,γ)", [1 / math.sqrt(7)])
    # mLD3 by character: the 2-D small irrep of 3m; mLD2 the 1-D one odd under
    # the mirrors (the [111] component of an axial vector)
    ld3 = [x for x in irr if x.dimension == 2]
    mirrors = [i for i, r in enumerate(irr[0].little.rotations)
               if round(np.linalg.det(r)) == -1]
    ld2 = [x for x in irr if x.dimension == 1
           and all(abs(x.characters[i] + 1) < 1e-9 for i in mirrors)]
    assert len(ld3) == 1 and len(ld2) == 1 and len(mirrors) == 3
    primary = inc.line_order_parameter(ld3[0])
    return inc.isotropy_superspace_groups(primary), inc.line_order_parameter(ld2[0])


@pytest.mark.xdist_group("srfeo3-isotropy")
def test_srfeo3_has_six_mssgs_with_figure6_degrees_of_freedom(srfeo3):
    groups, secondary = srfeo3
    assert len(groups) == 6
    got = sorted((g.dimension, inc.fixed_dimension(secondary, g.stabiliser)) for g in groups)
    assert got == sorted(nm for _, nm, _ in FIG6)
    assert all(g.group.magnetic_type == 4 for g in groups)       # all hold {1′|000½}


def test_line_atol_sits_in_a_gap_of_the_relative_singular_values(monkeypatch):
    """The audit row for ``LINE_ATOL`` rests on this: over these cases the
    relative singular values ``_null`` cuts split into a dropped cluster and a
    kept one with no value between them, so any tolerance in the gap returns
    the same subspaces.  (Cases: the isotropy groups of every irrep of
    P n m a at (0,0,γ) and P m -3 m at (γ,γ,γ); not a proof for other lines.)"""
    seen = []
    real = inc._null

    def recording(m, tol=inc.LINE_ATOL):
        if m.size:
            sv = np.linalg.svd(m, compute_uv=False)
            seen.extend(float(x) / max(1.0, float(sv[0])) for x in sv)
        return real(m, tol)

    monkeypatch.setattr(inc, "_null", recording)
    for sg, q in [("P n m a", "(0,0,γ)"), ("P m -3 m", "(γ,γ,γ)")]:
        for irr in inc.line_irreps(sg, q, [1 / math.sqrt(7)]):
            inc.isotropy_superspace_groups(inc.line_order_parameter(irr))
    dropped = [x for x in seen if x <= inc.LINE_ATOL]
    kept = [x for x in seen if x > inc.LINE_ATOL]
    assert dropped and kept
    assert max(dropped) < 1e-12 and min(kept) > 1e-3


def _cut_and_groups(lops):
    """The relative singular values ``_null`` cuts over the isotropy search of
    each order parameter, and the groups found (order-free: the irreps' order
    follows their λ-dependent characters)."""
    seen = []
    real = inc._null

    def recording(m, tol=inc.LINE_ATOL):
        if m.size:
            sv = np.linalg.svd(m, compute_uv=False)
            seen.extend(float(x) / max(1.0, float(sv[0])) for x in sv)
        return real(m, tol)

    inc._null = recording
    try:
        groups = sorted(sorted((len(g.group), g.dimension, tuple(sorted(g.stabiliser)))
                               for g in inc.isotropy_superspace_groups(lop)) for lop in lops)
    finally:
        inc._null = real
    return np.sort(seen), groups


def test_line_atol_gap_does_not_move_with_lambda_near_a_rational():
    """The second-λ control #1060's review asked for.  λ enters the matrices
    ``_null`` sees through k·v, so a λ a hair off a rational is where the gap
    above could close.  It cannot: v ↦ e^{2πiλd·v} is a character of G_k
    (dR = d), so on the ε = +1 operations it cancels against D(g)'s
    factor-system phase, and on the ε = −1 ones (dR = −d) it is one common
    phase, an internal-origin shift and the same orthogonal similarity on
    every matrix.  So the relative singular values are λ-free to rounding:
    at ½ and ½ + 1e-10 as at 1/√7 here, and on the nine ``DELTA_GRID``
    lines at ½, ⅓, ¼ and ± 1e-10, 1e-8, 1e-6 none falls in [1e-14, 6.5e-2).

    Positive arm: build the irreps at λ and apply k·v at λ + ε, a phase the
    character no longer cancels.  It puts singular values between πε/4 and
    πε in front of ``_null``.  At ε = 1e-10 they are cut and the groups
    stand; at 1e-7 they are kept, no fixed point survives and the search
    finds no group for any irrep.  So the recording sees a λ phase where
    there is one, and ``LINE_ATOL`` decides between the two answers (the
    change falls between ε = 5e-9 and 1e-8; from ε ≈ 2e-7 ``_frac``'s own
    1e-7 refuses the δ instead)."""
    sg, q, lam = "P n m a", "(0,0,γ)", 1 / math.sqrt(7)
    base = [inc.line_order_parameter(i) for i in inc.line_irreps(sg, q, [lam])]
    s_ref, g_ref = _cut_and_groups(base)
    assert s_ref[s_ref <= inc.LINE_ATOL].max() < 1e-13
    assert s_ref[s_ref > inc.LINE_ATOL].min() > 1e-2
    for near in (0.5, 0.5 + 1e-10):
        s, g = _cut_and_groups([inc.line_order_parameter(i)
                                for i in inc.line_irreps(sg, q, [near])])
        assert g == g_ref, near
        assert len(s) == len(s_ref) and np.abs(s - s_ref).max() < 1e-12, near

    def phase_off(eps):
        ext, _ = ir.extended_little_group_on_line(sg, q, [lam + eps])
        return _cut_and_groups([dataclasses.replace(lop, extended=ext) for lop in base])

    s, g = phase_off(1e-10)
    band = s[(s > 1e-13) & (s < 1e-2)]
    assert len(band) and band.max() < inc.LINE_ATOL
    assert g == g_ref
    s, g = phase_off(1e-7)
    band = s[(s > 1e-13) & (s < 1e-2)]
    assert len(band) and band.min() > inc.LINE_ATOL
    assert all(g_ref) and not any(g)


def test_a_symbol_in_rhombohedral_axes_is_refused_by_name():
    """Pm-3m at (γ,γ,γ): the isotropy group is an R lattice on rhombohedral
    axes (the parent's cubic cell), and symbols are written in hexagonal
    axes.  It used to fail an assertion about a generator."""
    lop = inc.line_order_parameter(inc.line_irreps("P m -3 m", "(γ,γ,γ)", [1 / math.sqrt(7)])[0])
    group = inc.isotropy_superspace_groups(lop)[0].group
    with pytest.raises(ValueError, match="rhombohedral axes"):
        symbol(group)


@pytest.mark.slow
def test_isotropy_groups_of_a_centred_parent_print_a_symbol_that_names_them_or_refuse():
    """I4₁/amd at (0,0,γ), the two-dimensional irreps: some isotropy groups
    are I-centred with their axes along the parent's diagonals, a setting no
    table has.  Their symbol used to read C222₁(0,0,γ)00s, whose parse is
    another group; each now round-trips, or is refused by name."""
    named = refused = 0
    for irr in inc.line_irreps("I 41/a m d", "(0,0,γ)", [1 / math.sqrt(7)]):
        if irr.dimension != 2:
            continue
        for iso in inc.isotropy_superspace_groups(inc.line_order_parameter(irr)):
            try:
                text = symbol(iso.group)
            except ValueError as err:
                assert "tabulated setting" in str(err)
                refused += 1
                continue
            assert equivalent(parse_symbol(text), iso.group), text
            named += 1
    assert named and refused


@pytest.mark.xdist_group("srfeo3-isotropy")
def test_srfeo3_groups_are_figure6s_printed_groups(srfeo3):
    """Each printed group is one of the six, up to equivalence, after the
    change of cell its setting needs; SrFeO₃'s published group (MAGNDATA
    #1.1.26, https://cryst.ehu.es/magndata/) R321′(00γ)t0s is the trigonal
    one with one mLD3 parameter."""
    groups, secondary = srfeo3
    matched = []
    for text, nm, cells in FIG6:
        printed = parse_symbol(text)
        hits = [g for g in groups if _in_setting(g.group, cells, printed) is not None]
        assert len(hits) == 1, text
        g = hits[0]
        assert (g.dimension, inc.fixed_dimension(secondary, g.stabiliser)) == nm, text
        matched.append(id(g))
    assert len(set(matched)) == 6


@pytest.mark.parametrize("row", [
    pytest.param(r, id=r[0], marks=[pytest.mark.xdist_group("srfeo3-isotropy")]
                 + ([pytest.mark.slow] if r[0].startswith("P") else []))
    for r in FIG6])
def test_srfeo3_groups_are_in_the_commit_a_lists(srfeo3, row):
    """The bridge: each OPD's group is one the enumerator returns over its
    maximal subgroup (two independent routes, compared in a setting where q
    lies along the axes).  The triclinic pair is ``slow``: with q general
    their equivalence orbits run over GL(3, ℤ)'s small matrices (~1-2 min
    each on the Mac)."""
    groups, _ = srfeo3
    text, _, cells = row
    printed = parse_symbol(text)
    std = next(x for x in (_in_setting(g.group, cells, printed) for g in groups)
               if x is not None)
    listed = magnetic_superspace_groups(maximal_subgroup(std), types=(2, 4))
    assert sum(equivalent(std, m) for m in listed) == 1, text


# ---------------------------------------------------------------------------
# CaFe₄As₃: Pnma, k = (0, λ, 0), group level
# ---------------------------------------------------------------------------
def test_cafe4as3_extended_group_relates_what_g_k_leaves_free():
    """Perez-Mato 2012 pp. 21-24: representation analysis over G_k leaves a
    free phase per Fe site; G_{k,−k} adds the inversion (ε = −1), which maps
    every 4c (x,¼,z) site into its own G_k orbit and so ties each site's phase
    to the one internal origin — in every 1-D irrep's MSSG.  The 4-vs-7
    parameter count is the subspace function's pin (next session)."""
    q = "(0,γ,0)"
    lg = ir.little_group_on_line("P n m a", q, lambdas=0.375 + 1e-3 * math.sqrt(2))
    ext, eps = ir.extended_little_group_on_line("P n m a", q)
    inv = [i for i, r in enumerate(ext.rotations) if np.array_equal(r, -np.eye(3))]
    assert len(inv) == 1 and eps[inv[0]] == -1
    assert not any(np.array_equal(r, -np.eye(3)) for r in lg.rotations)
    for site in ((0.11, 0.25, 0.32), (0.27, 0.25, 0.61), (0.38, 0.25, 0.09), (0.46, 0.25, 0.83)):
        x = np.array(site)
        orbit = {tuple(np.round((np.asarray(r) @ x + [float(t) for t in v]) % 1, 9))
                 for r, v in zip(lg.rotations, lg.translations)}
        image = tuple(np.round((-x + [float(t) for t in ext.translations[inv[0]]]) % 1, 9))
        assert len(orbit) == 4 and image in orbit
    for irr in ir.small_irreps_of(lg):
        g = inc.n1_superspace_group(inc.line_order_parameter(irr))
        assert any(o.rotation == ((-1, 0, 0), (0, -1, 0), (0, 0, -1)) and o.epsilon == -1
                   for o in g.operations)


@pytest.mark.slow
def test_the_isotropy_search_finds_the_same_groups_on_a_finer_delta_grid(monkeypatch):
    """The audit row for ``DELTA_GRID`` rests on this: the candidate subspaces
    of the isotropy search come from operations whose δ lie on the 1/24 grid
    alone, so a group needing another δ never becomes a candidate and is left
    out unannounced (reading the δ of the groups that *are* found cannot see
    it).  72 holds the cross products ⅓·⅓ and ⅓·⅙ (it adds 1/8, 1/9, 1/18 and
    1/36); the search at 24 and at 72 must return the same groups, irrep by
    irrep, over these nine lines.  Not a proof for other parents or lines."""
    lines = [("P n m a", "(0,0,γ)"), ("P n m a", "(0,γ,0)"),
             ("P 63/m m c", "(0,0,γ)"), ("P 63/m m c", "(1/3,1/3,γ)"),
             ("C m c a", "(0,0,γ)"), ("I 41/a m d", "(0,0,γ)"),
             ("R -3 m", "(0,0,γ)"), ("F d -3 m", "(0,0,γ)"),
             ("P 31 2 1", "(0,0,γ)")]

    def found():
        out = []
        for sg, q in lines:
            for irr in inc.line_irreps(sg, q, [1 / math.sqrt(7)]):
                gs = inc.isotropy_superspace_groups(inc.line_order_parameter(irr))
                out.append(sorted((len(g.group), g.dimension, tuple(sorted(g.stabiliser)))
                                  for g in gs))
        return out

    at_24 = found()
    monkeypatch.setattr(inc, "DELTA_GRID", 72)
    at_72 = found()
    assert sum(map(len, at_24)) > 0
    assert at_24 == at_72

    # positive arm: a grid that lacks thirds does lose groups
    monkeypatch.setattr(inc, "DELTA_GRID", 4)
    assert found() != at_24
