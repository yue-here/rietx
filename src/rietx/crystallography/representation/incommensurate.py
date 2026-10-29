"""The (magnetic) superspace group of an irrep at an incommensurate k.

:func:`.irreps.little_group_on_line` gives the small irreps of G_k for k on a
declared line, k = r + Σλ_j d_j.  This module turns one of them into the
(3+1)D superspace groups an order parameter transforming by it can have:
one group for a one-dimensional irrep (the N = 1 rule), one per
order-parameter direction (OPD) class otherwise (Perez-Mato, Ribeiro,
Petříček & Aroyo, 2012, *J. Phys.: Condens. Matter* **24**, 163201, §§ 3-4,
eqs (16)-(19); Gallego et al. 2016, *J. Appl. Cryst.* **49**, 1941, § 4).
The ``kind`` flag is :data:`.order_parameter.ORDER_PARAMETER_KINDS`'s:
``"magnetic"`` gives time reversal the −1 a moment carries, so every result
contains {1′|000½} and is a magnetic superspace group; ``"displacive"`` gives
it +1 and the result is a superspace group.

**The rule, written once (:func:`operation_matrix`).**  On rietx's Bloch
side (:mod:`.irreps` convention 3, D({E|a}) = e^{−2πik·a}; ψ the coefficients
of e^{+2πik·R}, never flipped) a field Σ c_i ψ_i + c.c. is carried by the
(3+1)D operation (g, θ, δ) onto itself iff

    e^{2πi(δ − k·v)} c = Γ(g, θ) c,

Γ(g, θ) = θ D(g) for ε = +1 and the antilinear c ↦ θ B̄_g c̄ for ε = −1
(g ψ = ψ̄ B_g, B_g the intertwiner from the k arm to the −k arm, Perez-Mato's
eq. (19) block A on our side), δ the operation's internal translation in the
lattice basis of :mod:`rietx.crystallography.superspace` and δ − k·v the
section-phase increment of de Wolff, Janssen & Janner (1981) eq. (3.2).
It is Perez-Mato's invariance equation (17) with his block θ D_T(R)
e^{+2πik·t} read as our D\\*(g) — his S(k) multiplies e^{−2πik·R}, our ψ
e^{+2πik·R} — and his τ₀ is our δ.  For a one-dimensional irrep it gives e^{2πiδ} = θ e^{2πik·v} D(g), the
N = 1 rule of his pp. 15-16 (an internal translation ½ where θ D_T(R) = −1),
and the 1/3, 1/4 and 1/6 shifts of polar-axial groups with their sign.

**OPDs as isotropy subgroups.**  The real order-parameter space ℂ^N carries
the finite group of (g, θ, δ) with δ on a 1/24 grid; every stabiliser is
gauge-fixed by an internal-origin shift (which moves the δ of the ε = −1
operations by 2t) and classes are taken under conjugation, so Gallego's "one
subgroup per conjugacy class" count is comparable.  The q family of each
group is the full subspace its point operations allow (q R = ε q), as the
printed symbols write it — C2/m1′(α0γ), P11′(αβγ).
"""

from __future__ import annotations

import cmath
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from .irreps import (
    LittleGroup,
    SmallIrrep,
    _is_reciprocal_lattice_vector,
    extended_little_group_on_line,
    little_group_on_line,
    small_irreps_of,
)
from .order_parameter import ORDER_PARAMETER_KINDS

#: Internal-translation grid of the isotropy search, 1/24.  The commensurate
#: part of q takes components 0, ½, ⅓, ⅔, so the internal translations of a
#: group's operations (0, ½, ⅓, ¼, ⅙, and the M·v cross terms of centred and
#: screw operations, which can leave the grid in principle) are searched on 1/24
#: only.  That no stabiliser needs another δ is measured, not derived:
#: ``test_the_isotropy_search_finds_the_same_groups_on_a_finer_delta_grid``
#: runs the search at 24 and at 72 and compares the groups found.
DELTA_GRID = 24

#: Relative rank cut of the SVD in :func:`_null` (the fixed subspaces of the
#: order-parameter space): a singular value counts as zero below
#: ``LINE_ATOL * max(1, s[0])``.  Nothing else reads it: the eigenvalue test of
#: :func:`_true_stabiliser` and :func:`_frac` use their own 1e-7.
LINE_ATOL = 1e-8


def _frac(x: float, *, what: str) -> Fraction:
    f = Fraction(x % 1).limit_denominator(DELTA_GRID * 6)
    if abs(float(f) - (x % 1)) > 1e-7 and abs(abs(float(f) - (x % 1)) - 1) > 1e-7:
        raise ValueError(f"{what} {x!r} is not a rational internal translation")
    return f % 1


@dataclass(frozen=True, eq=False)
class LineOrderParameter:
    """One small irrep of G_k on a line, with the extended group acting on it.

    ``extended`` is G_{k,−k} (:func:`.irreps.extended_little_group_on_line`)
    with ``epsilons``; ``gamma[j]`` is the 3D action of its j-th operation on
    the coefficient vector c: ``(matrix, antilinear)``, D(g) for ε = +1 and
    B_g (c ↦ B_g c̄) for ε = −1.
    """

    irrep: SmallIrrep
    extended: LittleGroup
    epsilons: tuple[int, ...]
    gamma: tuple
    m_rows: tuple
    kind: str

    @property
    def dimension(self) -> int:
        return self.irrep.dimension

    @property
    def q(self):
        return self.extended.line


def _ops(little: LittleGroup):
    return [(tuple(tuple(int(x) for x in row) for row in r), tuple(t))
            for r, t in zip(little.rotations, little.translations)]


def _compose(a, b):
    ra, va = a
    rb, vb = b
    r = tuple(tuple(sum(ra[i][k] * rb[k][j] for k in range(3)) for j in range(3))
              for i in range(3))
    v = tuple(sum(ra[i][k] * vb[k] for k in range(3)) + va[i] for i in range(3))
    return r, v


def _inverse(a):
    r, v = a
    from ..superspace.operators import _inverse3

    inv = _inverse3([[Fraction(x) for x in row] for row in r])
    ri = tuple(tuple(int(inv[i][j]) for j in range(3)) for i in range(3))
    vi = tuple(-sum(ri[i][k] * v[k] for k in range(3)) for i in range(3))
    return ri, vi


def _locate(ops, centrings, elem):
    """(index, lattice vector a) with elem = {E|a}·ops[index]."""
    r, v = elem
    for i, (ri, vi) in enumerate(ops):
        if ri == r:
            a = tuple(v[k] - vi[k] for k in range(3))
            if not any(all((a[k] - c[k]).denominator == 1 for k in range(3)) for c in centrings):
                raise AssertionError("an element off the group's lattice")
            return i, a
    raise AssertionError("an element outside the group")


def line_order_parameter(irrep: SmallIrrep, *, kind: str = "magnetic") -> LineOrderParameter:
    """The extended group's action on ``irrep``'s order parameter.

    ``irrep`` is a small irrep of a little group built by
    :func:`.irreps.little_group_on_line` with its λ values.  For the ε = −1
    coset the intertwiner B₀ of one coset operation g₀ solves
    B₀ D(h) = D(g₀hg₀⁻¹)\\* B₀ for h ∈ G_k and is normalised by B̄₀B₀ = D(g₀²);
    the rest are B_{g₀h} = B₀ D(h).  Refused when no such B₀ exists (the
    irrep is not paired with its −k image by G_{k,−k}, so its real order
    parameter is larger than 2N).

    The extended group and its intertwiner B_g are Perez-Mato, Ribeiro,
    Petříček & Aroyo (2012), *J. Phys.: Condens. Matter* **24**, 163201,
    eqs (16)-(19) (B on our side of their block A, eq. (19)).
    """
    if kind not in ORDER_PARAMETER_KINDS:
        raise ValueError(f"kind is one of {ORDER_PARAMETER_KINDS}, not {kind!r}")
    little = irrep.little
    if little.line is None:
        raise ValueError("the irrep is not one of a line point's little group")
    from ..superspace.operators import line_rule

    ext, eps = extended_little_group_on_line(little.spacegroup, little.line, little.lambdas)
    k = little.k_value
    cens = little.centrings
    small = _ops(little)
    big = _ops(ext)
    d = irrep.matrices

    def dmat(elem):
        i, a = _locate(small, cens, elem)
        return np.exp(-2j * np.pi * float(np.dot(k, [float(x) for x in a]))) * d[i]

    gamma = [None] * len(big)
    neg = [j for j, e in enumerate(eps) if e == -1]
    for j, e in enumerate(eps):
        if e == 1:
            gamma[j] = (dmat(big[j]), False)
    if neg:
        g0 = big[neg[0]]
        g0i = _inverse(g0)
        n = irrep.dimension
        rows = []
        for h in small:
            conj = dmat(_compose(_compose(g0, h), g0i))
            dh = dmat(h)
            # B dh − conj(conj_mat) B = 0, vectorised (row-major vec(B))
            rows.append(np.kron(np.eye(n), dh.T) - np.kron(np.conj(conj), np.eye(n)))
        a = np.vstack(rows)
        _, sv, vh = np.linalg.svd(a)
        null = vh[np.abs(np.concatenate([sv, np.zeros(vh.shape[0] - len(sv))])) < 1e-8]
        if len(null) != 1:
            raise NotImplementedError(
                "G_{k,-k} pairs this irrep's -k image with a different small irrep "
                "D' = (D^g0)* (no intertwiner B with B D(h) = D(g0 h g0^-1)* B), so its "
                "real order parameter spans D + D', 4N-dimensional; not built here")
        b0 = null[0].conj().reshape(n, n)
        sq = np.conj(b0) @ b0
        target = dmat(_compose(g0, g0))
        ratio = np.trace(sq @ np.conj(target).T) / n
        if abs(ratio.imag) > 1e-8 or ratio.real <= 0:
            raise NotImplementedError(
                "the coset intertwiner squares to −D(g₀²): the irrep is "
                "pseudoreal across k and −k, which doubles its order parameter")
        b0 = b0 / np.sqrt(ratio.real)
        for j in neg:
            h = _compose(g0i, big[j])
            # g ψ = ψ̄ B_g carries Σ c ψ + c.c. to coefficients B̄_g c̄
            gamma[j] = (np.conj(b0 @ dmat(h)), True)
    m_rows = []
    for r, _ in big:
        rule = line_rule([list(row) for row in r], little.line)
        m_rows.append(tuple(int(x) for x in rule[1]))
        if not _is_reciprocal_lattice_vector(rule[1], cens):  # pragma: no cover
            raise AssertionError("G_{k,-k} operation with M off L*")
    return LineOrderParameter(irrep, ext, eps, tuple(gamma), tuple(m_rows), kind)


def operation_matrix(lop: LineOrderParameter, j: int, theta: int, delta) -> np.ndarray:
    """The real (2N × 2N) matrix of the (3+1)D operation (g_j, θ, δ) on the
    order parameter (Re c, Im c): c ↦ e^{−2πi(δ − k·v)} Γ(g_j, θ)[c], the
    module docstring's rule.  A fixed vector is an order parameter the
    operation leaves invariant.

    Perez-Mato, Ribeiro, Petříček & Aroyo (2012), *J. Phys.: Condens. Matter*
    **24**, 163201, eq. (17), the invariance equation; the section phase
    δ − k·v is de Wolff, Janssen & Janner (1981), *Acta Cryst.* A**37**, 625,
    eq. (3.2).
    """
    mat, anti = lop.gamma[j]
    sign = theta if lop.kind == "magnetic" else 1
    v = lop.extended.translations[j]
    kv = float(np.dot(lop.extended.k_value, [float(x) for x in v]))
    lin = sign * cmath.exp(-2j * np.pi * (float(delta) - kv)) * mat
    re, im = lin.real, lin.imag
    if anti:
        return np.block([[re, im], [im, -re]])
    return np.block([[re, -im], [im, re]])


def superspace_operation(lop: LineOrderParameter, j: int, theta: int, delta):
    """The (3+1)D operation (g_j, θ, δ) as a
    :class:`~rietx.crystallography.superspace.SuperspaceOperator`: R, v from
    the extended group, ε, M from the line rule."""
    from ..superspace.operators import SuperspaceOperator

    ext = lop.extended
    r = tuple(tuple(int(x) for x in row) for row in ext.rotations[j])
    return SuperspaceOperator(r, tuple(Fraction(x) % 1 for x in ext.translations[j]),
                              lop.epsilons[j], lop.m_rows[j], Fraction(delta) % 1, int(theta))


def internal_translation(lop: LineOrderParameter, j: int, theta: int = 1) -> Fraction:
    """δ of an ε = +1 operation for a one-dimensional irrep: the N = 1 rule,
    e^{2πiδ} = θ e^{2πik·v} D(g) (Perez-Mato et al. 2012 pp. 15-16, on our
    side; module docstring)."""
    if lop.dimension != 1 or lop.epsilons[j] != 1:
        raise ValueError("the N = 1 rule is for an ε = +1 operation of a 1-D irrep")
    mat, _ = lop.gamma[j]
    sign = theta if lop.kind == "magnetic" else 1
    v = lop.extended.translations[j]
    kv = float(np.dot(lop.extended.k_value, [float(x) for x in v]))
    phase = cmath.phase(sign * cmath.exp(2j * np.pi * kv) * complex(mat[0, 0])) / (2 * np.pi)
    return _frac(phase, what="internal translation")


def _family(lop: LineOrderParameter, rotations_eps):
    """The q family a set of point operations allows: q_r kept, the free
    part the integer subspace {f : f R = ε f}."""
    from ..superspace.generation import _nullspace
    from ..superspace.operators import ModulationVector

    rows = []
    for r, e in rotations_eps:
        for j in range(3):
            rows.append([Fraction(r[i][j] - (e if i == j else 0)) for i in range(3)])
    basis = _nullspace(rows, 3) if rows else [[Fraction(int(i == j)) for j in range(3)]
                                              for i in range(3)]
    free = []
    for b in basis:
        den = 1
        for x in b:
            den = den * x.denominator // np.gcd(den, x.denominator)
        f = [int(x * den) for x in b]
        if next(x for x in f if x) < 0:
            f = [-x for x in f]
        free.append(tuple(f))
    if len(free) == 1 and lop.q.free and tuple(lop.q.free[0]) != free[0]:
        # one direction: keep the caller's spelling of it
        d = tuple(lop.q.free[0])
        if any(x * y for x, y in zip(d, free[0])):
            free = [d]
    return ModulationVector(tuple(lop.q.rational), tuple(free))


def _group_of(lop: LineOrderParameter, elements):
    from ..superspace.operators import _IDENTITY_R, SuperspaceGroup, SuperspaceOperator

    ops = [superspace_operation(lop, j, t, dl) for j, t, dl in elements]
    cen = [SuperspaceOperator(_IDENTITY_R, tuple(c), 1, (0, 0, 0), Fraction(0))
           for c in lop.extended.centrings]
    seen = {}
    for o in ops:
        seen[o.rotation] = o.epsilon
    q = _family(lop, list(seen.items()))
    return SuperspaceGroup.from_operations(q, ops + cen)


def n1_superspace_group(lop: LineOrderParameter):
    """The N = 1 rule (Perez-Mato et al. 2012 pp. 15-16): every operation of
    the grey extended little group survives, the ε = +1 ones with
    :func:`internal_translation`, a first ε = −1 one with δ = 0 (the internal
    origin), the rest by the product.  Magnetic: X + {1′|000½}X; displacive:
    the superspace group X."""
    if lop.dimension != 1:
        raise ValueError("the N = 1 rule is for a one-dimensional irrep; use "
                         "isotropy_superspace_groups")
    elements = [(j, 1, internal_translation(lop, j)) for j, e in enumerate(lop.epsilons)
                if e == 1]
    neg = [j for j, e in enumerate(lop.epsilons) if e == -1]
    if neg:
        elements.append((neg[0], 1, Fraction(0)))
    g = _group_of(lop, elements)
    if lop.kind == "magnetic":
        g = g.with_time_reversal_shift()
    return g


@dataclass(frozen=True, eq=False)
class IsotropySuperspaceGroup:
    """One OPD class: its (magnetic) superspace group, the stabiliser as
    (operation index, θ, δ), and the dimension of its fixed order-parameter
    subspace (Gallego et al. 2016 Fig. 6's n)."""

    group: object
    stabiliser: frozenset
    dimension: int
    basis: np.ndarray


def _null(m: np.ndarray, tol: float = LINE_ATOL) -> np.ndarray:
    if m.size == 0:
        return np.eye(m.shape[1])
    _, s, vh = np.linalg.svd(m)
    rank = int(np.sum(s > tol * max(1.0, s[0] if len(s) else 1.0)))
    return vh[rank:].T


def _key(basis: np.ndarray) -> tuple:
    p = basis @ basis.T
    return tuple(np.round(p, 6).ravel() + 0.0)


def _elements(lop: LineOrderParameter):
    thetas = (1, -1) if lop.kind == "magnetic" else (1,)
    out = []
    for j in range(len(lop.epsilons)):
        for t in thetas:
            for s in range(DELTA_GRID):
                d = Fraction(s, DELTA_GRID)
                out.append(((j, t, d), operation_matrix(lop, j, t, d)))
    return out


def _gauge(lop, stab) -> frozenset:
    """Fix the internal origin: shift every ε = −1 δ so the first ε = −1
    element (by operation index, θ) has δ = 0 (de Wolff 1981 p. 635)."""
    neg = sorted((j, t, d) for j, t, d in stab if lop.epsilons[j] == -1)
    if not neg:
        return frozenset(stab)
    c = neg[0][2]
    return frozenset((j, t, (d - c) % 1 if lop.epsilons[j] == -1 else d) for j, t, d in stab)


def _reduce(lop, op):
    ext = lop.extended
    for j, r in enumerate(ext.rotations):
        if tuple(tuple(int(x) for x in row) for row in r) == op.rotation:
            a = tuple(op.translation[k] - ext.translations[j][k] for k in range(3))
            if any(all((a[k] - c[k]).denominator == 1 for k in range(3))
                   for c in ext.centrings):
                return j, op.theta, op.delta % 1
    raise AssertionError("a conjugate outside the extended group")  # pragma: no cover


def _class_key(lop, stab) -> tuple:
    best = None
    for j in range(len(lop.epsilons)):
        g = superspace_operation(lop, j, 1, 0)
        gi = g.inverse()
        conj = frozenset(_reduce(lop, g * superspace_operation(lop, *e) * gi) for e in stab)
        key = tuple(sorted(_gauge(lop, conj)))
        if best is None or key < best:
            best = key
    return best


def _true_stabiliser(lop: LineOrderParameter, x: np.ndarray):
    """The stabiliser of the point x: every (g, θ) with e^{2πik·v}Γ(g, θ)x a
    unit multiple e^{2πiδ} of x; δ is exact for ε = +1 and read as a float for
    ε = −1, whose δ moves with the internal origin."""
    n = lop.dimension
    c = x[:n] + 1j * x[n:]
    thetas = (1, -1) if lop.kind == "magnetic" else (1,)
    out = []
    for j, (mat, anti) in enumerate(lop.gamma):
        v = lop.extended.translations[j]
        kv = float(np.dot(lop.extended.k_value, [float(t) for t in v]))
        base = mat @ (np.conj(c) if anti else c)
        for t in thetas:
            sign = t if lop.kind == "magnetic" else 1
            w = sign * cmath.exp(2j * np.pi * kv) * base
            rho = np.vdot(c, w) / np.vdot(c, c)
            if abs(abs(rho) - 1) < 1e-7 and np.allclose(w, rho * c, atol=1e-7):
                d = (cmath.phase(rho) / (2 * np.pi)) % 1
                out.append((j, t, d if anti else _frac(d, what="internal translation")))
    return out


def _gauge_float(lop, stab) -> frozenset:
    """:func:`_gauge` for a stabiliser whose ε = −1 δ are floats; after the
    shift they are exact rationals."""
    neg = sorted((j, t, d) for j, t, d in stab if lop.epsilons[j] == -1)
    c = neg[0][2] if neg else 0.0
    out = []
    for j, t, d in stab:
        if lop.epsilons[j] == -1:
            d = _frac(float(d) - float(c), what="gauge-fixed internal translation")
        out.append((j, t, d))
    return frozenset(out)


def isotropy_superspace_groups(lop: LineOrderParameter, *, seed: int = 0
                               ) -> list[IsotropySuperspaceGroup]:
    """One (magnetic) superspace group per class of order-parameter
    directions: the isotropy subgroups of the order parameter under
    (g, θ, δ) (module docstring), one per conjugacy class, largest group
    first.  Candidate subspaces are the fixed spaces of the δ-grid operations
    and their intersections; one is kept when the full stabiliser of a generic
    point in it — ε = −1 internal translations read continuously — fixes
    exactly it.  For a one-dimensional irrep there is one, the N = 1 rule's
    group (:func:`n1_superspace_group`).

    Isotropy subgroups of the order parameter, one per conjugacy class:
    Perez-Mato, Ribeiro, Petříček & Aroyo (2012), *J. Phys.: Condens. Matter*
    **24**, 163201, §§ 3-4; Gallego, Tasci, de la Flor, Perez-Mato & Aroyo
    (2016), *J. Appl. Cryst.* **49**, 1941, § 4.
    """
    elems = _elements(lop)
    dim = 2 * lop.dimension
    eye = np.eye(dim)
    spaces = {}
    for _, m in elems:
        b = _null(m - eye)
        if b.shape[1]:
            spaces.setdefault(_key(b), b)
    frontier = list(spaces.values())
    while frontier:
        new = []
        for a in frontier:
            for b in list(spaces.values()):
                inter = _null(np.vstack([eye - a @ a.T, eye - b @ b.T]))
                if inter.shape[1]:
                    k = _key(inter)
                    if k not in spaces:
                        spaces[k] = inter
                        new.append(inter)
        frontier = new
    rng = np.random.default_rng(seed)
    found = {}
    for basis in sorted(spaces.values(), key=lambda b: b.shape[1]):
        x = basis @ rng.normal(size=basis.shape[1])
        stab = _true_stabiliser(lop, x)
        fix = _null(np.vstack([operation_matrix(lop, j, t, d) - eye for j, t, d in stab]))
        if fix.shape[1] != basis.shape[1]:
            continue
        g_stab = _gauge_float(lop, stab)
        ck = _class_key(lop, g_stab)
        if ck not in found:
            gfix = _null(np.vstack([operation_matrix(lop, j, t, d) - eye for j, t, d in g_stab]))
            found[ck] = (g_stab, gfix)
    out = []
    for g_stab, basis in found.values():
        group = _group_of(lop, sorted(g_stab))
        out.append(IsotropySuperspaceGroup(group, g_stab, basis.shape[1], basis))
    out.sort(key=lambda x: (-len(x.group), x.dimension))
    return out


def fixed_dimension(lop: LineOrderParameter, stabiliser) -> int:
    """The dimension of ``lop``'s order-parameter subspace a stabiliser (from
    another irrep's :func:`isotropy_superspace_groups`) leaves fixed — the
    secondary degrees of freedom m of Gallego et al. 2016 Fig. 6."""
    dim = 2 * lop.dimension
    mats = [operation_matrix(lop, j, t, d) - np.eye(dim) for j, t, d in stabiliser]
    return int(_null(np.vstack(mats)).shape[1])


def line_irreps(space_group, q, lambdas) -> tuple[SmallIrrep, ...]:
    """The small irreps of G_k on a line, convenience for
    :func:`line_order_parameter`."""
    return small_irreps_of(little_group_on_line(space_group, q, lambdas))


__all__ = [
    "DELTA_GRID",
    "LINE_ATOL",
    "IsotropySuperspaceGroup",
    "LineOrderParameter",
    "fixed_dimension",
    "internal_translation",
    "isotropy_superspace_groups",
    "line_irreps",
    "line_order_parameter",
    "n1_superspace_group",
    "operation_matrix",
    "superspace_operation",
]
