"""The origin restraint of a polar phase, as residual rows of its own (WP-1912).

In a polar group (P 6₃ m c, P 4 m m, Cc, P 1, …) the whole structure can
shift along each direction the group's rotations all leave alone
(``crystallography.wyckoff.floating_origin_basis``) without changing any
intensity, so a stage freeing every coordinate along one has an exactly flat
direction.  ``Phase.floating_origin = "centroid"`` fixes it the way Flack &
Schwarzenbach (1988) do: one pseudo-observation per floating direction p,

    Z_p = Σₙ aₙ·Δ_pᵀ(xₙ − xₙ⁰) = 0                                     (eq 9)

with Δ_p orthonormal in fractional components (eq 1) and xₙ⁰ the coordinates
at the start of the solve, so the row adds nothing to the gradient there.  The
restrained solve then satisfies eq 9 exactly at any weight (eq 11 and the
paragraph after it), and only the covariance depends on the aₙ.  They solve

    aₘ·Σ_{n≠m} aₙ = bₘ,   bₘ = Σ_{ij} A_{im,jm}Ω_{ij} / Σᵢ Ω_ii           (eq 21, A1)

which zeroes each atom's Ω-collapsed off-diagonal sum in A′ = A + Σ_p t_p t_pᵀ
(eq 20), so the restrained normal matrix is as nearly diagonal as it can be
along the floating directions.  Here A is the **data** rows' normal matrix,
so bₘ = Σ_p ‖√w ⊙ ∂y/∂(site m moved alone by Δ_p)‖² / P, measured by central
difference at the stage's start (:func:`site_curvatures`).

Three rules carry the rest of the package's invariants:

* **a row block of its own**, ``origin_restraint`` in ``model.rows``, never
  the soft-restraint block, whose √c_w would silence the rows at c_w = 0 and
  free the origin again;
* **frozen per solve** — Δ, aₙ, x⁰ and the row count are built before a
  least-squares run (:func:`compile_origin`) and never move inside it;
* **linear**, so the partials are the constant matrix :attr:`CompiledOrigin.matrix`,
  chained through C like ``restraints.restraint_partials`` and exact at any step.

Reference: Flack, H. D. & Schwarzenbach, D. (1988). On the use of
least-squares restraints for origin fixing in polar space groups. *Acta Cryst.*
A44, 499-506 (eqs 1, 9, 11, 20, 21 and the Appendix's A1, A5, A6, A7).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..backend import get_backend

#: the central-difference step, in fractional coordinates, of the curvature bₘ.
#: The data rows are smooth in a coordinate, so the O(h²) truncation is ~1e-10
#: of the curvature at 1e-5, far inside the 1e-3 the Appendix solves eq 21 to
ORIGIN_FD_STEP = 1e-5

#: the Appendix's convergence level for the (A6) iteration: "about five
#: iterations are sufficient to reach convergence at the 0.1% level".  Iterated
#: past it (to :data:`A6_STEP_RTOL`) because each pass is O(N); this is the
#: level :attr:`CentroidSolve.converged` reports eq 21 against.
A6_RTOL = 1e-3
#: the relative step at which the (A6) iteration stops
A6_STEP_RTOL = 1e-12
#: the cap on (A6) passes.  Measured: 10-14 on random positive sets, 65 at a
#: (Σb − 2b_r)/b_r margin of 0.03.  On the 1200 realisable (A5) failures of
#: ``tests/test_floating_origin.py`` it is reached by 389 at a clip of 1e-3 and
#: 498 at the shipped 1e-4 (2026-10-21), and the sum solve meets eq 21 on all.
A6_MAX_ITER = 2000

#: how far below Σ_{n≠r} bₙ a dominant curvature is clipped when (A5) has no
#: solution, relatively: the restraint is then the near-limit of a hold on that
#: site, which is what a structure with one overwhelming scatterer wants anyway.
#: The light sites' z esds sit up to ε·14 from the hold's: 1.40 % at 1e-3
#: against the 1 % bar, 0.14 % here, over 1200 realisable failures, at about
#: 1 ms more per solve (WP-2002, the seventh round's Q2).
A5_CLIP = 1e-4


@dataclass(frozen=True)
class CentroidSolve:
    """The coefficients aₙ of eq 21, with how they were reached."""

    #: one coefficient per site, in the order the curvatures were given
    a: np.ndarray
    #: the index whose curvature (A5) made infeasible and was clipped, or None
    clipped: int | None
    #: eq 21 holds to :data:`A6_RTOL` (always ``True`` for N ≤ 2)
    converged: bool
    #: (A6) passes taken (0 where no iteration is needed)
    iterations: int


def centroid_coefficients(b) -> CentroidSolve:
    """Solve aₘ·Σ_{n≠m} aₙ = bₘ for aₙ ≥ 0 (Flack & Schwarzenbach 1988, eq 21).

    The (A6) iteration of the Appendix,

        a_r² = (N−2)·b_r² / ((N−1)·(Σb − 2b_r + v_r)),
        v_r = Σ_{m≠r} (a_m − Σ_{n≠r} a_n/(N−1))²,

    started from v_r = 0.  A real solution exists iff Σb − 2b_r > 0 for every r
    (A5).  Three cases the paper leaves open, decided on WP-1912:

    * a site with bₘ = 0 (nothing it scatters moves) gets aₘ = 0 and leaves
      the system, since eq 21 then holds for it at any value of the others;
    * N = 2 has b₁ = b₂ identically (each row of A sums to zero, eq 8), so
      eq 21 fixes only the product: a₁ = a₂ = √b̄, which makes A′ diagonal;
      N = 1 takes a = √b, the hold's limit;
    * (A5) failing, which can only happen to the largest bᵣ, clips it to just
      under the bound, (1 − ε)·Σ_{n≠r} bₙ with ε = :data:`A5_CLIP`.  Where the
      remaining sites are themselves lopsided that can fall below L, the lower
      edge every other (A5) row needs, and the clip is then
      Σ_{n≠r} bₙ − ε·(Σ_{n≠r} bₙ − L), inside both.

    Where (A6) ends short of :data:`A6_RTOL` (it stalls when (A5) holds by a
    margin far below the clip's, two heavy sites beside a light one) the
    same equations are solved through their sum instead
    (:func:`_solve_by_sum`), and the better of the two is kept.
    """
    b = np.maximum(np.asarray(b, dtype=np.float64), 0.0)
    a = np.zeros_like(b)
    pos = np.flatnonzero(b > 0.0)
    n = len(pos)
    if n == 0:
        return CentroidSolve(a, None, True, 0)
    if n <= 2:
        a[pos] = np.sqrt(b[pos].mean())
        return CentroidSolve(a, None, True, 0)
    bp = b[pos].copy()
    clipped = None
    r = int(np.argmax(bp))
    if bp.sum() - 2.0 * bp[r] <= 0.0:
        rest = bp.sum() - bp[r]
        # b_s − Σ_{n≠r,s} b_n for every other s: each (A5) row bounds b_r below
        lower = max(0.0, float(np.max(2.0 * np.delete(bp, r) - rest)))
        bp[r] = (1.0 - A5_CLIP) * rest
        if bp[r] <= lower:
            bp[r] = rest - A5_CLIP * (rest - lower)
        clipped = int(pos[r])
    total = bp.sum()
    v = np.zeros(n)
    ap = np.zeros(n)
    k = 0
    # a margin Σb − 2bₘ that rounds to zero divides by it; the NaN that
    # leaves is caught below, so numpy is not asked to warn about it
    with np.errstate(divide="ignore", invalid="ignore"):
        for k in range(1, A6_MAX_ITER + 1):
            nxt = np.sqrt((n - 2) * bp ** 2
                          / ((n - 1) * (total - 2.0 * bp + v)))
            s, q = nxt.sum(), float(nxt @ nxt)
            mean = (s - nxt) / (n - 1)
            v = np.maximum((q - nxt * nxt) - (n - 1) * mean * mean, 0.0)
            step = float(np.max(np.abs(nxt - ap) / nxt))
            ap = nxt
            if not step >= A6_STEP_RTOL:  # converged, or NaN: stop either way
                break
    resid = _eq21_residual(ap, bp)
    if not resid < A6_RTOL:
        # (A6) stalls where (A5) holds by a hair without failing — two
        # dominant sites beside a light one, [5, 5, 1e-3] met eq 21 to 32 %
        # after the cap — and returns NaN where Σb − 2bₘ rounds to zero.
        # The same equations solved through their one shared unknown instead
        polished = _solve_by_sum(bp)
        if polished is not None:
            fit = _eq21_residual(polished, bp)
            if np.isfinite(fit) and not resid <= fit:
                ap, resid = polished, fit
    a[pos] = ap
    return CentroidSolve(a, clipped, bool(resid < A6_RTOL), k)


def _eq21_residual(a: np.ndarray, b: np.ndarray) -> float:
    """max |aₘ·Σ_{n≠m} aₙ − bₘ| / bₘ, NaN where ``a`` is not finite."""
    with np.errstate(invalid="ignore"):
        return float(np.max(np.abs(a * (a.sum() - a) - b) / b))


def _solve_by_sum(b: np.ndarray) -> np.ndarray | None:
    """Eq 21 as one equation in S = Σa: aₘ(S − aₘ) = bₘ makes each aₘ a root
    of t² − S·t + bₘ, so a given S fixes every aₘ up to the branch.

    The small root 2bₘ/(S + √(S² − 4bₘ)) is taken by every site, or by every
    site but the largest bᵣ, which may take the large one, S minus it; S ≥
    2√bᵣ either way.  All-small is strictly decreasing in S, so it has one
    root if it starts non-negative at 2√bᵣ; else the large branch's sum
    rises from below zero to (Σ_{n≠r}bₙ − bᵣ)/S > 0, which is (A5).  Either
    root is bracketed and found by Brent's method.  ``None`` where no bracket
    is found (never, while (A5) holds).
    """
    from scipy.optimize import brentq

    r = int(np.argmax(b))
    s0 = 2.0 * math.sqrt(float(b[r]))

    def small(s, bb):
        # S² − 4b as (S − 2√b)(S + 2√b): exactly zero at S = 2√b, where the
        # unfactored form leaves a rounding residue whose root outweighs a
        # light site's whole term and moves the bracket
        root = 2.0 * np.sqrt(bb)
        disc = np.maximum((s - root) * (s + root), 0.0)
        return 2.0 * bb / (s + np.sqrt(disc))

    def every_small(s):
        return float(small(s, b).sum()) - s

    def one_large(s):
        return float(np.delete(small(s, b), r).sum() - small(s, b[r]))

    if every_small(s0) >= 0.0:
        h, hi = every_small, max(s0, math.sqrt(2.0 * float(b.sum()))) * 1.01
    else:
        h, hi = one_large, s0 * 2.0
        for _ in range(200):
            if h(hi) > 0.0:
                break
            hi *= 2.0
        else:
            return None
    if not h(hi) * h(s0) <= 0.0:
        return None
    s = brentq(h, s0, hi, xtol=1e-300, rtol=4 * np.finfo(float).eps)
    out = small(s, b)
    if h is one_large:
        out[r] = s - out[r]
    return out


def orthonormal_directions(axes) -> np.ndarray:
    """Δ_p, orthonormal in fractional components (eq 1), spanning ``axes``.

    The rows of ``floating_origin_basis`` are integer and need not be
    orthogonal in every setting; QR keeps their span and their sign.
    """
    m = np.asarray(axes, dtype=np.float64).T
    q, r = np.linalg.qr(m)
    return (q * np.sign(np.diag(r))).T


@dataclass(frozen=True)
class OriginPhaseRows:
    """One phase's share of the restraint: what the diagnostic says it did."""

    phase: int
    space_group: str
    #: the integer floating directions this solve restrains
    axes: tuple[tuple[int, int, int], ...]
    #: the site labels, in row order, and their base paths
    labels: tuple[str, ...]
    sites: tuple[str, ...]
    #: the measured curvatures bₙ and the solved coefficients aₙ
    b: np.ndarray
    a: np.ndarray
    #: the label whose curvature (A5) clipped, or None
    clipped: str | None
    converged: bool


@dataclass(frozen=True)
class CompiledOrigin:
    """The frozen restraint: rows = ``matrix @ (x − x0)`` over :attr:`paths`."""

    #: the coordinate rows the restraint reads (``…atoms.j.x`` or a body
    #: origin's), one column of :attr:`matrix` each
    paths: tuple[str, ...]
    #: (rows × paths): row p of phase i holds aₙ·Δ_p on site n's x, y, z
    matrix: np.ndarray
    #: the coordinates at the start of the solve
    x0: np.ndarray
    phases: tuple[OriginPhaseRows, ...]

    @property
    def n_rows(self) -> int:
        return int(self.matrix.shape[0])


def origin_residual(compiled: CompiledOrigin, values: dict):
    """Σₙ aₙ·Δ_pᵀ(xₙ − xₙ⁰), one row per floating direction (eq 9; traceable).

    The difference is taken before the product, so a large aₙ does not cancel
    two O(1) coordinates against each other; the frozen matrix is the *left*
    operand of ``xp.matmul`` and x⁰ is lifted, never a bare numpy constant
    left of an operator against a θ-derived value (root CLAUDE.md).
    """
    xp = get_backend()
    x = xp.stack([values[p] for p in compiled.paths])
    return xp.matmul(compiled.matrix,
                     x - xp.asarray(compiled.x0, dtype=np.float64))


def origin_partials(compiled: CompiledOrigin, table) -> np.ndarray:
    """∂row/∂p_phys as (rows × n_entries): :attr:`CompiledOrigin.matrix`, scattered.

    Constant, since the rows are linear; the caller chains it through C (and a
    body's derived rows) exactly as it chains ``restraint_partials``.
    """
    out = np.zeros((compiled.n_rows, len(table.entries)), dtype=np.float64)
    for k, path in enumerate(compiled.paths):
        out[:, table._paths[path]] += compiled.matrix[:, k]
    return out


def site_curvatures(model, values: dict, phase: int,
                    members: list[tuple[int, ...]], directions: np.ndarray,
                    *, step: float = ORIGIN_FD_STEP) -> np.ndarray:
    """bₘ = Σ_p ‖√w ⊙ ∂y/∂(site m moved alone by Δ_p)‖² / P (eq 21's right side).

    The data rows alone, by central difference: each site's atoms (one, or a
    rigid body's) are moved by ±h·Δ_p in fractional coordinates and the
    weighted pattern differenced, 2·N·P forward evaluations.  Σ_{ij}
    A_{im,jm}Ω_{ij} is Σ_p Δ_pᵀA_{mm}Δ_p by eq 3, and a shift along Δ_p is
    allowed at every site (the axis is fixed by every stabiliser), so this is
    the paper's sum over the refined variables (its [111] example included).
    """
    sqrt_w = 1.0 / model.sigma
    out = np.zeros(len(members), dtype=np.float64)
    for m, atoms in enumerate(members):
        for d in directions:
            ys = []
            for sign in (1.0, -1.0):
                shifted = dict(values)
                for j in atoms:
                    for c, comp in enumerate("xyz"):
                        if d[c] != 0.0:
                            path = f"phases.{phase}.atoms.{j}.{comp}"
                            shifted[path] = values[path] + sign * step * d[c]
                ys.append(np.asarray(model.evaluate(shifted), dtype=np.float64))
            col = sqrt_w * (ys[0] - ys[1]) / (2.0 * step)
            out[m] += float(col @ col)
    return out / len(directions)


def compile_origin(model, table) -> CompiledOrigin | None:
    """The origin restraint for the solve about to run, or ``None``.

    Built where a stage's free set is final, from ``table.origin_slides()``:
    one row per direction those columns can slide a ``"centroid"`` phase
    along, over every site of the phase (each moves under the shift).  A
    Rietveld-only construction, since Le Bail and Pawley force-fix every
    coordinate and so slide nothing.  A phase whose sites scatter nothing the
    data sees (every bₙ zero) gets no row: there is no centroid to weight.
    """
    if model.mode != "rietveld":
        return None
    slides = table.origin_slides()
    if not slides:
        return None
    values = table.decode(table.x0())
    phases = table.origin_phases
    paths: list[str] = []
    blocks: list[tuple[np.ndarray, list[str]]] = []
    records: list[OriginPhaseRows] = []
    for ip, axes in sorted(slides.items()):
        rec = phases[ip]
        delta = orthonormal_directions(axes)
        bases = list(rec.sites)
        labels = [rec.sites[s][0] for s in bases]
        b = site_curvatures(model, values, ip, [rec.sites[s][1] for s in bases],
                            delta)
        solve = centroid_coefficients(b)
        if not solve.a.any():
            continue
        cols = [f"{s}.{c}" for s in bases for c in "xyz"]
        block = np.zeros((len(delta), len(cols)), dtype=np.float64)
        for n in range(len(bases)):
            block[:, 3 * n:3 * n + 3] = solve.a[n] * delta
        keep = [k for k in range(len(cols)) if block[:, k].any()]
        blocks.append((block[:, keep], [cols[k] for k in keep]))
        paths.extend(cols[k] for k in keep)
        records.append(OriginPhaseRows(
            phase=ip, space_group=rec.space_group, axes=tuple(axes),
            labels=tuple(labels), sites=tuple(bases), b=b, a=solve.a,
            clipped=None if solve.clipped is None else labels[solve.clipped],
            converged=solve.converged))
    if not records:
        return None
    paths = list(dict.fromkeys(paths))
    col = {p: k for k, p in enumerate(paths)}
    matrix = np.zeros((sum(bl.shape[0] for bl, _ in blocks), len(paths)))
    row = 0
    for bl, names in blocks:
        for k, name in enumerate(names):
            matrix[row:row + bl.shape[0], col[name]] = bl[:, k]
        row += bl.shape[0]
    return CompiledOrigin(
        paths=tuple(paths), matrix=matrix,
        x0=np.array([float(values[p]) for p in paths], dtype=np.float64),
        phases=tuple(records))
