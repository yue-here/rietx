"""Satellites at G ± k: where a commensurate propagation vector puts intensity.

A phase that orders with a propagation vector **k** scatters at Q = H ± k for
every vector H of its nuclear *reciprocal lattice*.  This module builds that
reflection list and the small enumerated set of candidate k the report arm
ranks.  It knows nothing about moments, form factors or magnetic symmetry: a
satellite is a **position**, which is the whole content of WP-1326, and what
makes the magnetic hypothesis testable before a single moment is stated.

Two rules from the FullProf manual (Rodríguez-Carvajal, J. (1993). *Physica B*
**192**, 55; *FullProf manual* § Propagation vectors, eqs 3.47-3.54) that a
naive generator gets wrong, and both are enforced here by construction:

1. **k and −k are one vector exactly when 2k is a reciprocal-lattice vector,
   and that test respects centring.**  On a C lattice (½, 0, 0) and (−½, 0, 0)
   are distinct, because (1, 0, 0) violates h + k = 2n; (0, 0, ½) is single
   because (0, 0, 1) is a reciprocal-lattice point.  The test is
   :func:`~rietx.crystallography.magnetic.irreps.equivalent_kvectors`, which
   reduces modulo the **true** reciprocal lattice through the primitive basis
   rather than componentwise modulo 1 — that is where the centring enters.
2. **H runs over the reciprocal lattice, not over the allowed reflections.**
   Centring conditions say which H exist and are kept; a glide or a screw axis
   is a condition on the *nuclear structure factor* and says nothing about
   where a satellite may sit, so those absences are **not** applied.  A
   generator that applies them drops real satellites — see
   :func:`satellite_reflections` and the negative control in
   ``tests/test_satellites.py``.

**Multiplicity is enumerated, never computed from a formula.**  The satellite
multiplicity is the number of distinct Q in the orbit of H + m·k under the
Laue group (Friedel mates merged, reciprocal-space action Rᵀ — root
``CLAUDE.md``).  The tempting formula |Laue orbit of H| × |star of k| is an
upper bound and is wrong whenever two operations land on the same Q: the pair
(RᵀH, Rᵀk) is *correlated*, both being images under the same R.  Root
``CLAUDE.md``'s rule for a neighbour search applies for the same reason —
enumerate and check by orbit counting.

**Exactness.**  k is carried as exact ``Fraction``s and every orbit is merged
on integer codes: with q the least common denominator of k, q·Q is an integer
vector, Rᵀ is integral, so the whole dedup is exact integer arithmetic and
cannot depend on a tolerance.  Only the d-spacings are floating point.

**The candidate set is enumerated, not searched, and the enumeration is a
pluggable generator** (issue #257 A1).  :func:`zone_boundary_candidates` is
the default WP-1326 fixes — {0, ½}³ minus the origin, plus the two
third-order points on a hexagonal or trigonal lattice — reduced to one
representative per **star**, since every arm of a star generates the identical
satellite list.  A successor that scans the special points and lines of the
Brillouin zone (Wills, A. S. (2009). *Z. Kristallogr. Suppl.* **30**, 39;
Hinuma, Y., Pizzi, G., Kumagai, Y., Oba, F. & Tanaka, I. (2017). *Comput.
Mater. Sci.* **128**, 140) drops in as another
:data:`CandidateGenerator` without touching the arm.

**Labels are positional and by the plain vector** (issue #257 A2).  The CDML
k-label (Aroyo, M. I., Orobengoa, D., de la Flor, G., Tasci, E. S.,
Perez-Mato, J. M. & Wondratschek, H. (2014). *Acta Cryst.* A**70**, 126) is
what MAGNDATA, ISODISTORT and k-SUBGROUPSMAG speak, and it needs the
per-Bravais-lattice k-label tables — a data source of its own, deferred here
exactly as ``magnetic/irreps.py`` deferred the irrep labels rather than
inventing a scheme that would look like CDML and disagree with it.
:func:`cdml_label` is the hook, and it returns ``None`` until those tables
land.

Non-goals, refused by name rather than approximated: an incommensurate k (a
superspace problem, ``as_propagation_vector``), a refinable k, more than one k
on a phase, and k = 0 (:func:`check_propagation_vector` — the satellites then
coincide with the nuclear lines, which is a degeneracy and not a model).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction

import gemmi
import numpy as np

from .lattice import d_spacings
from .magnetic.irreps import (
    K_MAX_DENOMINATOR,
    KVector,
    as_kvector,
    equivalent_kvectors,
    star,
)
from .symmetry import (
    MAX_HKL_GRID_POINTS,
    OperatorGroup,
    ReflectionSet,
    get_spacegroup,
    rotation_matrices,
)

__all__ = [
    "KCandidate",
    "CandidateGenerator",
    "as_propagation_vector",
    "check_propagation_vector",
    "minus_k_is_k",
    "reciprocal_lattice_mask",
    "satellite_reflections",
    "satellite_d_spacings",
    "satellite_orbit",
    "merge_satellites",
    "zone_boundary_candidates",
    "cdml_label",
    "format_kvector",
]


# --------------------------------------------------------------------------
# the propagation vector itself
# --------------------------------------------------------------------------

def _resolve(space_group):
    """A group object from a symbol, a number-as-string, or a group itself.

    Passes an :class:`~rietx.crystallography.symmetry.OperatorGroup` through
    unchanged.  That is what lets the report arm score candidate k on an
    operation-list phase (it passes ``reflections.operations``); it does
    **not** make a *declared* k on such a phase supported.  A bracketed label
    with a k is refused at the schema, and three places would need the list
    before it could be served: ``_k_is_usable`` in ``schemas/structure.py``,
    ``compile_model``'s ``satellite_reflections(phase.space_group, …)``, and
    :func:`merge_satellites`, which rebuilds the set without ``operations``
    (review follow-up on #468).
    """
    if isinstance(space_group, (gemmi.SpaceGroup, OperatorGroup)):
        return space_group
    return get_spacegroup(str(space_group))


def as_propagation_vector(k) -> KVector:
    """Three exact rationals from any accepted spelling of k.

    Thin wrapper over
    :func:`~rietx.crystallography.magnetic.irreps.as_kvector`, kept as its own
    name because *this* is the door a phase's declared vector comes through
    and the refusal it raises is the WP's non-goal: a component that is not a
    rational of denominator ≤ ``K_MAX_DENOMINATOR`` is an incommensurate k,
    which is a superspace problem this rung fences rather than approximates.
    """
    return as_kvector(k)


def format_kvector(k) -> str:
    """``"(0, 0, 1/2)"`` — the plain-vector label (issue #257 A2)."""
    return "(" + ", ".join(str(c) for c in as_propagation_vector(k)) + ")"


def check_propagation_vector(space_group, k) -> KVector:
    """Validate a phase's k and return it as exact rationals.

    Raises ``ValueError`` for an incommensurate component (through
    :func:`as_propagation_vector`) and for **k ≡ 0 modulo the reciprocal
    lattice**, which is not a modelling choice this rung can serve: every
    satellite would sit exactly on a nuclear line, so a Le Bail extraction
    absorbs the whole of the magnetic intensity into the nuclear intensities
    and the hypothesis is untestable by this route.  The report arm says the
    same thing about a *residual* that sits on nuclear lines
    (:mod:`rietx.report.satellites`); this refusal is about a *declaration*,
    where the duplicate reflection list would be an exact degeneracy in the
    parameter vector.
    """
    sg = _resolve(space_group)
    kk = as_propagation_vector(k)
    if equivalent_kvectors(sg, kk, (0, 0, 0)):
        raise ValueError(
            f"propagation vector {format_kvector(kk)} is a reciprocal-lattice "
            f"vector of {sg.xhm()!r}, "
            "i.e. k = 0: every satellite would coincide with a nuclear "
            "reflection, so the two intensities are not separable by a powder "
            "measurement and the reflection list would be exactly duplicated. "
            "A k = 0 magnetic structure is tested by comparing this pattern "
            "with one of the same specimen above its ordering temperature, "
            "not by declaring a propagation vector")
    return kk


def minus_k_is_k(space_group, k) -> bool:
    """True when −k ≡ k, i.e. when 2k is a vector of the reciprocal lattice.

    The FullProf manual's ±k rule (Rodríguez-Carvajal, J. (1993). *Physica B*
    **192**, 55, § Propagation vectors), and it is **centring-aware** because
    the reciprocal lattice is: on a C lattice (½, 0, 0) has 2k = (1, 0, 0),
    which violates h + k = 2n and is therefore *not* a reciprocal-lattice
    vector, so +k and −k are two vectors; (0, 0, ½) has 2k = (0, 0, 1), which
    is one, so they are the same vector.
    """
    kk = as_propagation_vector(k)
    return equivalent_kvectors(space_group, tuple(-c for c in kk), kk)


def _centring_rows(sg: gemmi.SpaceGroup) -> np.ndarray:
    """Centring translations of the lattice as exact 24ths, shape (c, 3) int."""
    return np.array([[int(x) for x in t] for t in sg.operations().cen_ops],
                    dtype=np.int64)


def reciprocal_lattice_mask(space_group, hkl: np.ndarray) -> np.ndarray:
    """Which integer *hkl* are vectors of the group's **reciprocal lattice**.

    The reciprocal lattice of a centred direct lattice is the sublattice of
    the integer grid obeying the centring condition — h + k = 2n on C, all
    indices of one parity on F, −h + k + l = 3n on R (hexagonal axes).  This
    is the *whole* of what is applied to a satellite: a glide or screw absence
    is a condition on the nuclear structure factor, and a satellite has no
    nuclear structure factor to be absent from (module docstring).

    Exact: the test is (24·h)·c ≡ 0 mod 24 with gemmi's centring translations
    in 24ths, so it is integer arithmetic with no tolerance anywhere.
    """
    sg = _resolve(space_group)
    h = np.asarray(hkl, dtype=np.int64)
    cen = _centring_rows(sg)
    den = gemmi.Op.DEN
    return np.all((h @ cen.T) % den == 0, axis=1)


# --------------------------------------------------------------------------
# generating the satellites
# --------------------------------------------------------------------------

def _laue_images(sg: gemmi.SpaceGroup) -> np.ndarray:
    """(2M, 3, 3) integer Rᵀ and −Rᵀ — the Laue action on a reciprocal index.

    A real-space x' = Rx + t sends h to Rᵀh (root ``CLAUDE.md``), and a powder
    merges Friedel mates because d(Q) = d(−Q); {Rᵀ} is a group but is not the
    same *set* as {R} outside orthogonal settings, so the transpose is
    load-bearing and not cosmetic.
    """
    rot = np.rint(np.transpose(rotation_matrices(sg), (0, 2, 1))).astype(np.int64)
    return np.concatenate([rot, -rot], axis=0)


def satellite_orbit(space_group, hkl, m: int, k) -> np.ndarray:
    """The distinct Q of one satellite's Laue orbit, as exact q·Q integers.

    ``hkl`` is the parent reciprocal-lattice vector H, ``m`` the order (±1),
    ``k`` the propagation vector.  Returned rows are **q·Q** with q the least
    common denominator of k, so the caller divides by ``q`` to read physical
    indices; the integer form is what makes the dedup exact.  ``len`` of the
    result is the satellite multiplicity, by enumeration (module docstring).
    """
    sg = _resolve(space_group)
    kk = as_propagation_vector(k)
    q = _common_denominator(kk)
    base = (q * np.asarray(hkl, dtype=np.int64)
            + int(m) * np.array([int(c * q) for c in kk], dtype=np.int64))
    images = np.einsum("mij,j->mi", _laue_images(sg), base)
    uniq = sorted({tuple(int(v) for v in im) for im in images})
    return np.array(uniq, dtype=np.int64)


def _common_denominator(k: KVector) -> int:
    q = 1
    for c in k:
        q = q * c.denominator // math.gcd(q, c.denominator)
    return int(q)


def lattice_two_theta(space_group,
                      cell: tuple[float, float, float, float, float, float],
                      wavelength: float, two_theta_max: float,
                      two_theta_min: float = 0.0) -> np.ndarray:
    """Sorted 2θ of every **reciprocal-lattice point** in range.

    The k = 0 case of :func:`satellite_reflections`, and it exists because k = 0
    is the one hypothesis a propagation vector cannot express (it is refused —
    :func:`check_propagation_vector`) and the one the report arm must still be
    able to see.  Centring conditions are applied; glide and screw absences are
    **not**, for the reason they are not applied to a satellite either.

    That distinction is what makes this diagnostic rather than decorative.  A
    k = 0 magnetic structure has its magnetic intensity at Q = H, so it lands
    on the nuclear lines — where a nuclear misfit also lands, and the two look
    alike.  But its magnetic structure factor is an axial vector, and its
    absence rule for a glide or screw can be the complement of the nuclear one
    (Gallego, S. V., Tasci, E. S., de la Flor, G., Perez-Mato, J. M. & Aroyo,
    M. I. (2012). *J. Appl. Cryst.* **45**, 1236, §§ 4.1.1, 4.3.2), so it can
    put intensity at reciprocal-lattice points where the assumed group's
    nuclear structure factor is identically zero.  So can a nuclear group
    lower than the one assumed, λ/2 contamination and an impurity line; the
    report arm names all four (:mod:`rietx.report.satellites`).  Measured on
    the GSAS-II
    ``Magnetic-II`` Cr₂WO₆ data (P 4₂/mnm, 4 K against a converged 150 K
    nuclear model): the two strongest residual peaks are (0 0 1) at 15.62° and
    (1 0 2) at 44.45°, both systematically absent and both reciprocal-lattice
    points.
    """
    sg = _resolve(space_group)
    d_min = wavelength / (2.0 * np.sin(np.radians(two_theta_max / 2.0)))
    bounds = [int(np.floor(cell[i] / d_min)) + 1 for i in range(3)]
    n_grid = np.prod([2 * b + 1 for b in bounds])
    if n_grid > MAX_HKL_GRID_POINTS:
        raise ValueError(
            f"refusing to enumerate the reciprocal lattice for cell "
            f"a={cell[0]:g}, b={cell[1]:g}, c={cell[2]:g} Å at "
            f"d_min={d_min:.4g} Å: {n_grid:.2e} grid points "
            f"(limit {MAX_HKL_GRID_POINTS:.0e}).")
    grids = np.meshgrid(*[np.arange(-b, b + 1) for b in bounds], indexing="ij")
    hkl = np.column_stack([g.ravel() for g in grids]).astype(np.int64)
    hkl = hkl[~np.all(hkl == 0, axis=1)]
    hkl = hkl[reciprocal_lattice_mask(sg, hkl)]
    d = d_spacings(hkl, *cell)
    keep = d >= d_min * 0.999
    if two_theta_min > 0.0:
        d_max = wavelength / (2.0 * np.sin(
            np.radians(max(two_theta_min, 1e-3) / 2.0)))
        keep &= d <= d_max * 1.001
    d = d[keep]
    if len(d) == 0:
        return np.zeros(0)
    s = wavelength / (2.0 * d)
    tt = np.degrees(2.0 * np.arcsin(np.clip(s, -1.0, 1.0)))
    return np.unique(np.round(tt, 9))


def _d_min(wavelength: float, two_theta_max: float) -> float:
    return wavelength / (2.0 * np.sin(np.radians(two_theta_max / 2.0)))


def _parent_grid(sg, cell, wavelength: float, two_theta_max: float, *,
                 apply_structure_absences: bool = False) -> np.ndarray:
    """Every parent H a satellite in range can have, as an (n, 3) int array.

    **Independent of k**: |Q_i| <= |a_i| / d_min bounds the satellite index,
    and H = Q − m·k adds at most one to each component since |k_i| < 1 after
    canonicalisation (a non-canonical k is caught by the d filter, which runs
    on Q).  So one grid serves every candidate k of a phase, which is what
    :func:`satellite_d_spacings` shares and why the report arm's cost does not
    grow with the number of candidates it scores (review item 4 on #468).
    """
    d_min = _d_min(wavelength, two_theta_max)
    a, b, c = cell[0], cell[1], cell[2]
    hmax = int(np.floor(a / d_min)) + 2
    kmax = int(np.floor(b / d_min)) + 2
    lmax = int(np.floor(c / d_min)) + 2
    n_grid = (2 * hmax + 1) * (2 * kmax + 1) * (2 * lmax + 1)
    if n_grid > MAX_HKL_GRID_POINTS:
        raise ValueError(
            f"refusing to enumerate satellites for cell a={a:g}, b={b:g}, "
            f"c={c:g} Å at d_min={d_min:.4g} Å (λ={wavelength:g} Å, "
            f"2θ_max={two_theta_max:g}°): index ranges ±{hmax}, ±{kmax}, "
            f"±{lmax} span {n_grid:.2e} grid points "
            f"(limit {MAX_HKL_GRID_POINTS:.0e}).")

    rng = [np.arange(-n, n + 1) for n in (hmax, kmax, lmax)]
    H, K, L = np.meshgrid(*rng, indexing="ij")
    parents = np.column_stack([H.ravel(), K.ravel(), L.ravel()]).astype(np.int64)
    keep = reciprocal_lattice_mask(sg, parents)
    if apply_structure_absences:
        ops = sg.operations()
        try:
            absent = np.asarray(ops.systematic_absences(parents), dtype=bool)
        except (AttributeError, TypeError):  # pragma: no cover - old gemmi
            absent = np.array([ops.is_systematically_absent(list(map(int, h)))
                               for h in parents])
        keep &= ~absent
    return parents[keep]


#: the two satellite orders this rung enumerates, in the order they are tried
#: when a representative is split back into (H, m)
_ORDERS = (1, -1)


def _satellite_orbits(sg, cell, parents: np.ndarray, kk: KVector,
                      wavelength: float, two_theta_max: float,
                      two_theta_min: float):
    """One representative per Laue orbit of the satellites H ± k in range.

    Returns ``(reps_q, mult, d_reps, q, k_int)`` with ``reps_q`` the q·Q rows,
    in the order the orbits were first met; ``None`` when nothing is in range.
    The orbit merge is exact integer arithmetic (module docstring).  Two
    things make it cheap without changing a bit of it: the Laue images are
    taken **once each** — a Laue group always contains −1, so the Friedel
    half of ``_laue_images`` repeats the first and the max over images and the
    count of distinct images are the same over the set — and an image's code
    is one integer product per operation, ``q_rows @ (Rᵀᵀ·w)``, rather than a
    materialised (ops, rows, 3) array.  Integer products are exact, so the
    codes are the same integers either way.
    """
    q = _common_denominator(kk)
    k_int = np.array([int(c * q) for c in kk], dtype=np.int64)
    d_min = _d_min(wavelength, two_theta_max)
    q_rows = np.concatenate([q * parents + m * k_int for m in _ORDERS], axis=0)
    # (0, 0, 0) can never be reached — k is not a reciprocal-lattice vector
    # (check_propagation_vector) — so no row needs dropping the way the
    # nuclear enumeration drops the origin.
    d = d_spacings(q_rows.astype(np.float64) / q, *cell)
    in_range = d >= d_min * 0.999
    if two_theta_min > 0.0:
        d_max = wavelength / (2.0 * np.sin(np.radians(max(two_theta_min, 1e-3) / 2.0)))
        in_range &= d <= d_max * 1.001
    q_rows, d = q_rows[in_range], d[in_range]
    if len(q_rows) == 0:
        return None

    images_op = _laue_images(sg)
    base = (int(np.abs(images_op).sum(axis=2).max())
            * int(np.abs(q_rows).max()) + 1)
    radix = 2 * base + 1
    ops = np.unique(images_op.reshape(len(images_op), 9), axis=0).reshape(-1, 3, 3)
    # code(x) = ((x0 + base)·radix + (x1 + base))·radix + x2 + base, linear in
    # x, so code(R·q) = q·(Rᵀ·w) + const with w = (radix², radix, 1)
    w = np.array([radix * radix, radix, 1], dtype=np.int64)
    offset = base * (radix * radix + radix + 1)
    code = (np.transpose(ops, (0, 2, 1)) @ w) @ q_rows.T + offset
    rep_code = code.max(axis=0)
    ordered = np.sort(code, axis=0)
    n_distinct = 1 + (np.diff(ordered, axis=0) != 0).sum(axis=0)

    # One row per orbit.  The representative is the largest **enumerated** row
    # of the orbit, not the largest image: unlike the nuclear case, only the
    # enumerated rows are in H ± k form.  Rᵀ mixes the components, so the
    # largest image of (2h, 2k, 2l+1) can be (2h', 2k'+1, 2l'), a satellite of
    # a different parent along a different axis, which cannot be split back
    # into (H, m) against the declared k.  Restricting the choice to the
    # enumerated rows keeps it well defined and lexicographically canonical.
    own_code = q_rows @ w + offset
    by_own = np.argsort(-own_code, kind="stable")
    first = np.sort(np.unique(rep_code[by_own], return_index=True)[1])
    sel_idx = by_own[first]
    # orbit-stabiliser, the invariant ``site_orbit`` asserts one rank over: an
    # orbit under a group of order |G| has |G|/|stabiliser| members, so the
    # count must divide |G|.  Unreachable by construction — these *are* the
    # distinct images of one point — which is exactly why it is worth
    # asserting: it is the invariant, not a defensive check.
    bad = np.flatnonzero(len(ops) % n_distinct[sel_idx] != 0)
    if len(bad):
        raise ValueError(
            f"ORBIT_NOT_A_MULTIPLICITY: satellite orbit of size "
            f"{int(n_distinct[sel_idx][bad[0]])} under a Laue group of order "
            f"{len(ops)} (Friedel included) in {sg.xhm()!r}; a "
            "multiplicity is |G|/|stabiliser| and must divide |G|")
    return (q_rows[sel_idx], n_distinct[sel_idx].astype(np.int64), d[sel_idx],
            q, k_int)


def satellite_reflections(sg_symbol,
                          cell: tuple[float, float, float, float, float, float],
                          wavelength: float,
                          two_theta_max: float,
                          k,
                          two_theta_min: float = 0.0,
                          *,
                          apply_structure_absences: bool = False) -> ReflectionSet:
    """The symmetry-unique satellites Q = H ± k in range, one row per orbit.

    Mirrors :func:`~rietx.crystallography.symmetry.generate_reflections` step
    for step — enumerate, keep what is in range, merge Laue orbits with
    Friedel mates, one representative each with its orbit size — with two
    deliberate differences, which are the WP's two rules:

    * the enumeration runs over H of the **reciprocal lattice**
      (:func:`reciprocal_lattice_mask`), so glide and screw absences are not
      applied.  ``apply_structure_absences=True`` applies them and is the
      **negative control**, never a mode: it reproduces the naive generator so
      a test can measure what the naive generator loses;
    * both orders m = ±1 are enumerated and merged by orbit, which is what
      makes the ±k rule fall out rather than be asserted.  When 2k is a
      reciprocal-lattice vector the two sets coincide exactly and the merge
      returns one of each; when it is not, they do not and it returns both.

    ``hkl`` on the returned set is the **parent** H and ``satellite_order``
    the m, so a satellite is an integer object in the record while its peak
    sits at the rational index ``ReflectionSet.index`` = H + m·k.  A
    representative that can be written with m = +1 is, so the sign is
    canonical rather than an artefact of enumeration order.
    """
    sg = _resolve(sg_symbol)
    kk = check_propagation_vector(sg, k)
    parents = _parent_grid(sg, cell, wavelength, two_theta_max,
                           apply_structure_absences=apply_structure_absences)
    orbits = _satellite_orbits(sg, cell, parents, kk, wavelength,
                               two_theta_max, two_theta_min)
    if orbits is None:
        return ReflectionSet(
            hkl=np.zeros((0, 3), dtype=np.int64),
            multiplicity=np.zeros(0, dtype=np.int64),
            d=np.zeros(0, dtype=np.float64), spacegroup=sg.xhm(),
            satellite_order=np.zeros(0, dtype=np.int64),
            propagation_vector=tuple(float(x) for x in kk))
    reps_q, mult, d_reps, q, k_int = orbits

    # split each representative q·Q back into (H, m): prefer m = +1, so the
    # stored sign does not depend on which image won the max above
    hkl = np.zeros_like(reps_q)
    order = np.zeros(len(reps_q), dtype=np.int64)
    todo = np.ones(len(reps_q), dtype=bool)
    for m in _ORDERS:
        rest = reps_q - m * k_int
        fits = todo & np.all(rest % q == 0, axis=1)
        hkl[fits] = rest[fits] // q
        order[fits] = m
        todo &= ~fits
    if todo.any():  # pragma: no cover - unreachable: every row was built as H ± k
        row = reps_q[np.flatnonzero(todo)[0]]
        raise RuntimeError(
            f"satellite representative {row.tolist()} (in {q}ths) is not "
            f"H ± k for the declared k {format_kvector(kk)}")

    sort = np.argsort(-d_reps)
    return ReflectionSet(hkl=hkl[sort], multiplicity=mult[sort], d=d_reps[sort],
                         spacegroup=sg.xhm(), satellite_order=order[sort],
                         propagation_vector=tuple(float(x) for x in kk))


def satellite_d_spacings(space_group,
                         cell: tuple[float, float, float, float, float, float],
                         wavelength: float, two_theta_max: float,
                         ks: Sequence, two_theta_min: float = 0.0
                         ) -> list[np.ndarray]:
    """``satellite_reflections(…, k).d`` for every k in ``ks``, sharing one grid.

    The report arm scores positions, so it needs each candidate's orbit
    d-spacings and nothing of the (H, m) split; and the parent grid is
    independent of k (:func:`_parent_grid`), so it is built **once**.  Each
    array is bit-identical to what :func:`satellite_reflections` returns for
    that k — same grid, same orbit merge, same representative, same order —
    which ``tests/test_satellites.py`` asserts.
    """
    sg = _resolve(space_group)
    parents = _parent_grid(sg, cell, wavelength, two_theta_max)
    out: list[np.ndarray] = []
    for k in ks:
        kk = check_propagation_vector(sg, k)
        orbits = _satellite_orbits(sg, cell, parents, kk, wavelength,
                                   two_theta_max, two_theta_min)
        if orbits is None:
            out.append(np.zeros(0, dtype=np.float64))
            continue
        d_reps = orbits[2]
        out.append(d_reps[np.argsort(-d_reps)])
    return out


def merge_satellites(nuclear: ReflectionSet, sat: ReflectionSet) -> ReflectionSet:
    """One reflection list carrying both, sorted by descending d.

    The compiled phase gets **one** array per quantity because everything
    downstream — the frozen windows, the FCJ node counts, the Le Bail
    partition, the Pawley block, the tick list, the observation count — is
    written over "the phase's reflections" and a satellite is one of those
    (WP-1326 § Seams).  What distinguishes them is ``satellite_order``, which
    the structure-factor path reads to contribute exactly zero there.

    ``sat`` is built by :func:`satellite_reflections` and is kept as its own
    object by the caller, so the second set is still a
    :class:`~rietx.crystallography.symmetry.ReflectionSet` frozen beside the
    nuclear one; this is the merge, not a replacement for it.
    """
    if len(sat) == 0:
        return nuclear
    hkl = np.concatenate([nuclear.hkl.astype(np.int64), sat.hkl.astype(np.int64)])
    mult = np.concatenate([nuclear.multiplicity, sat.multiplicity])
    d = np.concatenate([nuclear.d, sat.d])
    order = np.concatenate([np.zeros(len(nuclear), dtype=np.int64),
                            sat.satellite_order.astype(np.int64)])
    sort = np.argsort(-d, kind="stable")
    return ReflectionSet(hkl=hkl[sort], multiplicity=mult[sort], d=d[sort],
                         spacegroup=nuclear.spacegroup,
                         extra=dict(nuclear.extra),
                         satellite_order=order[sort],
                         propagation_vector=sat.propagation_vector)


# --------------------------------------------------------------------------
# the candidate set (issue #257 A1, A2)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class KCandidate:
    """One candidate propagation vector, with the labels a reader can use.

    ``name`` is **positional** and deterministic (``k1``, ``k2``, …, in the
    generator's own order); ``vector`` is the plain-vector spelling, which is
    the label a user can always check; ``cdml`` is the CDML k-label and is
    ``None`` until the per-Bravais-lattice tables land (:func:`cdml_label`).
    ``origin`` names the generator that produced it, so a ranked list from a
    different candidate set says where it came from.
    """

    k: KVector
    name: str
    vector: str
    origin: str
    cdml: str | None = None

    @property
    def label(self) -> str:
        """What a report prints: the CDML label where there is one, else the vector."""
        return self.vector if self.cdml is None else f"{self.cdml} {self.vector}"


#: A candidate generator takes a space group and returns labelled k's.  Made a
#: function from day one (issue #257 A1) so the successor rung — a search over
#: every special point and line of the Brillouin zone, then a general-k grid —
#: drops into the report arm without touching it.
CandidateGenerator = Callable[[object], Sequence[KCandidate]]

#: The third-order points WP-1326 adds on a hexagonal or trigonal lattice, in
#: conventional reciprocal coordinates.  Two literals rather than a rule, and
#: that is the WP's choice: this rung enumerates, it does not search.
_TRIGONAL_POINTS = ((Fraction(1, 3), Fraction(1, 3), Fraction(0)),
                    (Fraction(1, 3), Fraction(1, 3), Fraction(1, 2)))


def cdml_label(space_group, k) -> str | None:
    """The CDML k-label of ``k``, or ``None`` — the deferred hook (#257 A2).

    MAGNDATA, ISODISTORT and k-SUBGROUPSMAG all speak these labels (Aroyo,
    M. I., Orobengoa, D., de la Flor, G., Tasci, E. S., Perez-Mato, J. M. &
    Wondratschek, H. (2014). *Acta Cryst.* A**70**, 126), so a report that
    carried them would let a user cross-check directly.  They need the
    per-Bravais-lattice k-label tables, which are a data source of their own
    and are **not** derivable from the operations alone — the same reason
    :mod:`rietx.crystallography.magnetic.irreps` labels its irreps
    positionally.  Returning ``None`` rather than inventing a scheme is the
    deliberate choice: a made-up label would look like CDML and disagree
    with it.
    """
    return None


def zone_boundary_candidates(space_group) -> tuple[KCandidate, ...]:
    """The enumerated candidate set WP-1326 fixes — the default generator.

    {0, ½}³ minus the origin, plus (⅓, ⅓, 0) and (⅓, ⅓, ½) on a hexagonal or
    trigonal lattice, reduced to **one representative per star**.  The star
    reduction is not a convenience: every arm of a star generates the
    identical satellite list (the enumeration merges over the whole Laue
    group), so keeping all of them would put exact ties in a ranking that is
    supposed to be read.

    Seven on a triclinic P lattice; three on P m -3 m, where the six face and
    edge points collapse onto two stars.  **Centring does not reduce the
    count**: every difference of two members of {0, ½}³ has a half-integer
    component and so is never a reciprocal-lattice vector, whatever the
    centring — which is what the WP's "fewer distinct ones under centring"
    would need.  What does reduce it is the point group, through the star.
    """
    sg = _resolve(space_group)
    half = (Fraction(0), Fraction(1, 2))
    raw: list[KVector] = [(h, kk, ll) for h in half for kk in half for ll in half
                          if not (h == 0 and kk == 0 and ll == 0)]
    if sg.crystal_system_str() in ("hexagonal", "trigonal"):
        raw.extend(_TRIGONAL_POINTS)
    out: list[KCandidate] = []
    seen: set[frozenset[KVector]] = set()
    for kk in raw:
        arms = frozenset(star(sg, kk))
        if arms in seen:
            continue
        seen.add(arms)
        out.append(KCandidate(
            k=kk, name=f"k{len(out) + 1}", vector=format_kvector(kk),
            origin="zone_boundary", cdml=cdml_label(sg, kk)))
    return tuple(out)


def check_candidate_denominators(candidates: Sequence[KCandidate]) -> None:
    """Raise if a generator returned a k this package cannot serve.

    A generator is a caller's function (issue #257 A1), so the arm validates
    what it gets rather than trusting it: every component must be a rational
    of denominator at most ``K_MAX_DENOMINATOR``, which is the commensurate
    fence, and no candidate may be k = 0.
    """
    for cand in candidates:
        for comp in cand.k:
            if comp.denominator > K_MAX_DENOMINATOR:
                raise ValueError(
                    f"candidate {cand.name} = {cand.vector} has a component "
                    f"with denominator {comp.denominator} > "
                    f"{K_MAX_DENOMINATOR}: this rung is commensurate only")
        if all(c == 0 for c in cand.k):
            raise ValueError(
                f"candidate {cand.name} is k = 0, which puts every satellite "
                "on a nuclear line and cannot be scored (see "
                "check_propagation_vector)")
