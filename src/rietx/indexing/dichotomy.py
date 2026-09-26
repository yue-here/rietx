"""Engine A — successive dichotomy: an **exhaustive** branch-and-bound search
whose silence is evidence.

*Sources*: Louër, D. & Louër, M. (1972), *J. Appl. Cryst.* **5**, 271-275;
Boultif, A. & Louër, D. (1991), **24**, 987-993 and (2004), **37**, 724-731;
Altomare *et al.* (2019), International Tables Vol. H ch. 3.4 §3.4.3.1.5.
**Papers only** — no DICVOL code was read or ported (CLAUDE.md licensing fence).

The method divides a parameter domain into 2ⁿ subdomains, discards any that
*provably* cannot contain a solution, and recurses.  What makes it worth having
next to two cheaper engines is the contrapositive: when it completes a domain
and finds nothing, no cell of that symmetry within those bounds fits the peak
list.  That is why :attr:`~rietx.indexing.engines.EngineResult.search_complete`
is not decoration — an unfinished search has said nothing at all, and the two
cases must not look alike downstream.

**It searches A..F, not (a, b, c, α, β, γ), and that is the whole design.**  Q is
*linear* in the metric (``qspace.py``), so over an axis-aligned box the extremes
of Q(hkl) are attained **exactly at box corners** — one signed dot product per
reflection, no interval arithmetic over trigonometric functions, no monotonicity
case analysis for the cross terms, and the bound is *tight* rather than merely
valid.  The literature formulation works in direct space and switches to
reciprocal space for triclinic precisely because the direct expression becomes
unmanageable; in A..F that case split does not exist.

**The box lives in the symmetry subspace, so its dimension is the metric DOF.**
``metric_basis(system)`` is imported rather than tabulated (1 cubic … 6
triclinic), and the coordinates θ are read off the basis's **pivot** structure:
each basis row has a leading component no other row touches, so θ_j is one A..F
component divided by that pivot — which is what lets a physical bound on a
d-spacing become a bound on θ with no per-system table.

Three prunes run per box, cheapest first:

1. **the metric cone** — the box's induced interval for det G* must intersect the
   volume band, and a box whose diagonal A..F interval is entirely non-positive
   is not a lattice;
2. **line matching** — for each observed line in increasing Q, some trial hkl's
   [Q_min, Q_max] over the box must reach it within k·σ_eff; more than
   ``n_unindexed`` misses and the box is impossible.  Both are *monotone* under
   bisection (a child's intervals are subsets of its parent's), which is what
   makes the pruning sound rather than merely plausible;
3. **the reflection ceiling** at every leaf, before any enumeration
   (``engines.reflection_ceiling_ok`` — the measured 1.6 PiB guard).

**Tolerated unindexed lines are the single most valuable option here** — it is
DICVOL06's own reported gain.  Without them one impurity line prunes the box
containing the truth and the engine returns nothing, *confidently*, which is the
one failure this milestone exists to prevent.  Raising the count past the default
manufactures cells: each extra tolerated line is one more coincidence a wrong
metric is allowed to have.
"""

from __future__ import annotations

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import PeakList
from .engines import (
    SYSTEM_ORDER,
    Budget,
    EngineCandidate,
    EngineResult,
    SearchSpec,
    assign_lines,
    dedup_candidates,
    effective_shift_allowance,
    incomplete_diagnostic,
    indexes_the_search_lines,
    provisional_payload,
    rank_candidates,
    refine_with_shift,
    reflection_ceiling_ok,
    register_engine,
    search_line_order,
    search_volume_ceiling,
    shift_allowance_diagnostic,
    trial_hkl,
)
from .qspace import (
    cell_from_af,
    centring_allows,
    design_matrix,
    metric_basis,
    refine_candidate,
    sigma_effective,
)

#: Largest |cos| allowed for a reciprocal cell angle, i.e. the obliquity bound of
#: the search domain.  cos 30° — reciprocal angles from 30° to 150°, which covers
#: every reduced cell with room to spare, and is reported as a *bound of the
#: search* rather than a claim about lattices: a cell more oblique than this is
#: outside the domain and its absence from the results means nothing.
MAX_ANGLE_COSINE = np.cos(np.radians(30.0))
#: Bisections a single box may undergo before the search gives up on it.  A
#: termination guarantee, not a tuning knob: the acceptance test is a Q-width
#: threshold, and a pathological σ (a peak list of assumed zeros) would otherwise
#: never reach it.  60 halvings is 1e-18 of the domain — unreachable in practice.
MAX_DEPTH = 60
#: Assign-refine passes a leaf may take before its assignment is declared
#: unstable and the candidate is reported as it stands.  Four: a converging
#: candidate settles in two, and a candidate still oscillating at four is one
#: whose assignment the data does not determine.
MAX_ASSIGN_PASSES = 4
#: Factor the match window is tightened by per annealing pass — see
#: :func:`_accept`.  Four: it takes the window from a coarse box's width to the
#: per-line σ in the four passes above, and a gentler schedule costs a solve per
#: leaf for no measured gain.
ANNEAL_FACTOR = 4.0
#: Fraction of the median gap between neighbouring observed lines below which a
#: box's induced Q width is fine enough to refine rather than bisect.  See the
#: comment at its use: this is a *stopping* rule, not a tolerance, and the
#: exhaustiveness guarantee does not depend on it.
ACCEPT_SPACING_FRAC = 0.25
#: Top-level grid step in a principal d-spacing (Å) — IT-H ch. 3.4 §3.4.3.1.5.
AXIS_STEP = 0.4
#: Top-level grid step in a reciprocal cell angle (degrees), same source.
ANGLE_STEP_DEG = 5.0
#: Hard cap on the trial hkl set, before any box filtering.  Sized so the initial
#: (n_hkl, m) signed-dot-product pass stays under a few tens of MB; a search that
#: needs more indices than this is a dominant-zone case, which WP-1022 reports
#: rather than brute-forces.
MAX_TRIAL_HKL = 200_000
#: Grid cells the breadth-first pass may hold at once.  Overflowing it returns
#: ``search_complete = False`` rather than silently truncating: a grid that did not
#: finish has not covered its domain, and "nothing found" must not be able to mean
#: "nothing looked at".
MAX_GRID_CELLS = 400_000
#: Raw leaves held before an intermediate dedup pass.  Bounds memory on a
#: degenerate search (a wildly over-tolerant peak list can accept thousands of
#: near-identical boxes) without changing the answer.
DEDUP_EVERY = 2_000


def _pivots(basis: np.ndarray) -> list[tuple[int, float]]:
    """(column, value) of each basis row's leading entry, checked exclusive.

    ``adp_basis`` returns an exact integer nullspace in echelon form, so each
    row's pivot column is touched by no other row and θ_j = af[pivot]/value
    exactly.  That is an implementation detail of the nullspace routine rather
    than a promise, so it is **verified here** and raises if it ever stops
    holding — the alternative (a silently loose bounding box) would still return
    correct cells while quietly costing an order of magnitude in search time,
    which is the kind of regression no test notices.
    """
    out: list[tuple[int, float]] = []
    for row in np.asarray(basis, dtype=np.float64):
        nz = np.flatnonzero(np.abs(row) > 1e-12)
        if not len(nz):
            raise ValueError("metric_basis returned a zero row")
        out.append((int(nz[0]), float(row[nz[0]])))
    cols = [p for p, _v in out]
    if len(set(cols)) != len(cols):
        raise ValueError(f"metric_basis rows share a pivot column ({cols}); the "
                         "θ parameterisation assumes echelon form")
    for j, (p, _v) in enumerate(out):
        others = np.delete(np.asarray(basis, dtype=np.float64), j, axis=0)
        if len(others) and np.any(np.abs(others[:, p]) > 1e-12):
            raise ValueError(f"metric_basis column {p} is not exclusive to its "
                             "pivot row; the θ parameterisation assumes echelon "
                             "form")
    return out


def axis_swaps(basis: np.ndarray) -> list[tuple[int, int]]:
    """Which pairs of A..F diagonal components a **setting change** may exchange.

    Permuting the axes of a cell gives a different description of the *same*
    lattice, and a search that does not quotient by it pays for every permutation
    twice over — measured on an orthorhombic list, the six permutations of
    (7, 8, 9) came back as six separate candidates, each fitted slightly
    differently and none of them merged, because they are genuinely different
    A..F vectors.

    Which permutations are available is **derived, not tabulated**: a permutation
    P is a setting change of this system exactly when it maps the metric subspace
    to itself (G* → P·G*·Pᵀ stays in the span).  Orthorhombic and triclinic admit
    all six, monoclinic b-unique only a↔c (which fixes β), and the tied systems
    admit them trivially.  The returned pairs are the *adjacent* exchanges, which
    is all a canonical ordering needs.
    """
    out: list[tuple[int, int]] = []
    b = np.asarray(basis, dtype=np.float64)
    for i, j in ((0, 1), (0, 2), (1, 2)):
        order = [0, 1, 2]
        order[i], order[j] = order[j], order[i]
        if _preserves_subspace(b, order):
            out.append((i, j))
    return out


def _preserves_subspace(basis: np.ndarray, order: list[int]) -> bool:
    """Does permuting the axes by ``order`` map the A..F subspace to itself?"""
    from .qspace import af_from_gstar, gstar_from_af

    p = np.eye(3)[order]
    for row in basis:
        g = gstar_from_af(row)
        moved = af_from_gstar(p @ g @ p.T)
        coef, *_ = np.linalg.lstsq(basis.T, moved, rcond=None)
        if not np.allclose(basis.T @ coef, moved, atol=1e-9):
            return False
    return True


def _initial_box(basis: np.ndarray, spec: SearchSpec
                 ) -> tuple[np.ndarray, np.ndarray]:
    """The θ-space domain: d-spacing bounds on the diagonal, obliquity on the rest.

    ``A = 1/d(100)²`` and its two partners are bounded by the principal
    d-spacings, and each off-diagonal by Cauchy-Schwarz,
    ``|2G*_ij| ≤ 2√(G*_ii G*_jj) ≤ 2·cos_max/d_min²``.

    One **setting** restriction is applied and it is what keeps monoclinic
    affordable: when a system has exactly one off-diagonal degree of freedom, it
    is taken non-negative.  Every monoclinic lattice has a b-unique setting with
    β ≥ 90°, and 2G*₁₃ ≥ 0 is exactly that choice (measured: the same cell at
    β = 93.84° and 86.16° gives E = +2.12e-3 and −2.12e-3), so the half-domain is
    complete rather than merely cheaper.  With more than one free off-diagonal —
    triclinic — no such choice exists and every sign orthant is searched.
    """
    piv = _pivots(basis)
    a_hi = 1.0 / spec.min_d_axis ** 2
    a_lo = 1.0 / spec.max_d_axis ** 2
    n_off = sum(1 for p, _v in piv if p >= 3)
    lo = np.zeros(len(piv))
    hi = np.zeros(len(piv))
    for j, (p, v) in enumerate(piv):
        if p < 3:
            lo[j], hi[j] = a_lo / v, a_hi / v
        else:
            bound = 2.0 * MAX_ANGLE_COSINE * a_hi / v
            lo[j] = 0.0 if n_off == 1 else -bound
            hi[j] = bound
    return lo, hi


def _test_box(m: np.ndarray, lo: np.ndarray, hi: np.ndarray, basis: np.ndarray,
              q_hi: float, det_band: tuple[float, float],
              swaps: list[tuple[int, int]], lo_search: np.ndarray,
              hi_search: np.ndarray, n_unindexed: int,
              ) -> tuple[np.ndarray, float, bool] | None:
    """Every prune, in cost order.  ``None`` if the box is impossible.

    Returns ``(surviving trial rows, induced Q width, assignment is unique)``.
    Shared by the grid pass and the dichotomy so the two phases cannot come to
    different conclusions about the same box — which is the whole reason the
    prunes live in a function rather than inline in each loop.
    """
    q_min, q_max = _q_bounds(m, lo, hi)
    keep = q_min <= q_hi
    if not keep.all():
        m, q_min, q_max = m[keep], q_min[keep], q_max[keep]
    if not len(q_min):
        return None

    af_lo, af_hi = _af_interval(basis, lo, hi)
    if np.any(af_hi[:3] <= 0.0):
        return None
    # A box lying entirely in "A < B" holds no cell this search needs to report:
    # permuting the axes is a setting change, so an equivalent description with
    # A ≥ B exists and some other box holds it.  A box that *straddles* the
    # constraint is kept — the test is a prune, not a projection — so completeness
    # is untouched.
    for a, b in swaps:
        if af_hi[a] < af_lo[b]:
            return None
    det_lo, det_hi = _det_interval(af_lo, af_hi)
    if det_hi < det_band[0] or det_lo > det_band[1]:
        return None

    # one (lines × reflections) pass answers all three remaining questions: how
    # many lines nothing can reach (the prune), which reflections can reach
    # anything (what the children inherit), and whether any line still has two
    # candidates (the stopping rule).  Vectorised rather than a per-line loop with
    # an early exit — measured, the loop's numpy call overhead cost more than the
    # exits saved.
    hit = (q_min[None, :] <= hi_search[:, None]) & (q_max[None, :]
                                                    >= lo_search[:, None])
    if len(hi_search) - int(np.count_nonzero(hit.any(axis=1))) > n_unindexed:
        return None

    # A reflection that cannot reach *any* line over this box cannot reach one
    # over a sub-box either — the intervals only shrink — so it is dropped for the
    # children rather than re-tested.  This is what keeps the per-box cost from
    # being set by the whole trial set: measured on an orthorhombic search, 2.7 ms
    # per box against 20 µs once the set collapses.  It is also why the *width* is
    # measured over the reflections that reach a line: the trial set holds
    # high-index reflections whose Q sweeps the whole domain, and measuring the box
    # by those forces depth nothing needs.
    relevant = hit.any(axis=0)
    n_reachable = int(np.count_nonzero(relevant))
    counts = hit.sum(axis=1)
    if not _assignment_possible(hit, n_reachable, counts, len(hi_search),
                                n_unindexed):
        return None
    width = float(np.max((q_max - q_min)[relevant])) if n_reachable else 0.0
    # **The box is small enough when the indexing inside it is unique** — no
    # observed line has two candidate reflections — not when some width crosses a
    # threshold.  The width test alone does not terminate: a high-index reflection
    # has a large ‖m‖, so its Q interval stays wide long after the assignment has
    # stopped being ambiguous, and the search bisects past its own depth cap.
    unique = bool(len(hit)) and int(np.max(counts)) <= 1
    return m[relevant], width, unique


def _assignment_possible(hit: np.ndarray, n_reachable: int, counts: np.ndarray,
                         n_lines: int, n_unindexed: int) -> bool:
    """Hall's condition, in the two forms that cost nothing to check.

    ``hit.any(axis=1)`` — "can *some* reflection reach each line" — is the
    weakest necessary condition there is, and measured on the bethanechol
    monoclinic domain it is very nearly vacuous: it killed **342 boxes of
    692 294**, 0.0 %.  An indexing is an *injective* map from lines to
    reflections (one hkl has one Q, so two resolved lines cannot both be it),
    so the box must admit a matching, and Hall's theorem says a matching needs
    ``|N(S)| ≥ |S|`` for every set ``S`` of lines.  Two instances of that are
    already sitting in the ``hit`` matrix:

    * **S = every line.**  ``|N(S)|`` is the number of reflections that reach
      anything, i.e. ``relevant.sum()`` — which the caller computes anyway.  On
      the same domain this alone refuses **89.9 %** of the boxes that reach it,
      because the surviving trial set collapses to ~16 reflections while 20
      lines still have to be explained, and the weak test is happy for the 20 to
      share.
    * **S = the lines with exactly one candidate.**  Those assignments are
      forced, so two such lines pointing at the *same* reflection is a violation
      at ``|S| = 2`` — DICVOL91's own rejection rule.  Worth 29.8 % on its own,
      mostly overlapping the first.

    Both are *necessary*, never sufficient, so this refuses boxes and never
    accepts one.  Soundness under bisection is the same argument the rest of the
    prunes rest on — a child's Q intervals are subsets of its parent's, so
    ``|N(S)|`` only shrinks and a box refused here has no sub-box that recovers.
    """
    if n_reachable < n_lines - n_unindexed:
        return False
    forced = counts == 1
    n_forced = int(np.count_nonzero(forced))
    if n_forced > 1:
        distinct = len(np.unique(np.argmax(hit[forced], axis=1)))
        if distinct < n_forced - n_unindexed:
            return False
    return True


def _push_children(stack: list, children: list, m: np.ndarray,
                   lo_search: np.ndarray, hi_search: np.ndarray,
                   n_unindexed: int, depth: int) -> None:
    """Test each child, drop the impossible ones, and push **best last**.

    A LIFO stack explores its *first* child last, so with a plain push order the
    search's own ordering is an accident of iteration.  On a 4-D monoclinic domain
    that is fatal rather than merely untidy: the grid holds ~1.6 million cells,
    one of them contains the answer, and depth-first order reached 11.9 million
    boxes in 240 s without visiting it.

    The ordering key is **how determined a box is**, not how big or how deep: the
    number of search lines nothing can reach (fewer is better), then the total
    number of (line, reflection) pairs that could match.  A box containing a real
    cell has about one candidate reflection per line; a box that survives on
    coincidence has many, because its intervals are still wide enough to reach
    everything.  Pruning here rather than on the next pop also means an impossible
    child never enters the stack.
    """
    scored = []
    for child_lo, child_hi in children:
        q_min, q_max = _q_bounds(m, child_lo, child_hi)
        hit = (q_min[None, :] <= hi_search[:, None]) & (q_max[None, :]
                                                        >= lo_search[:, None])
        misses = len(hi_search) - int(np.count_nonzero(hit.any(axis=1)))
        if misses > n_unindexed:
            continue
        # the cheap half of Hall's condition only: this child is about to be
        # pushed, popped and fully tested anyway, so all that is bought here is
        # the push, and the counting reduction is already paid for by ``hit``
        if int(np.count_nonzero(hit.any(axis=0))) < len(hi_search) - n_unindexed:
            continue
        scored.append((misses, int(hit.sum()), child_lo, child_hi))
    scored.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    for _misses, _pairs, child_lo, child_hi in scored:
        stack.append((child_lo, child_hi, m, depth))


def _pivot_of(basis: np.ndarray, af_index: int) -> int | None:
    """Which θ dimension carries this A..F component, or None if none does."""
    for j, (p, _v) in enumerate(_pivots(basis)):
        if p == af_index:
            return j
    return None


#: Paired diagonal A..F components of each off-diagonal one — the Cauchy-Schwarz
#: partners, read off ``qspace._AF_INDEX``: D = 2G*₂₃ pairs (B, C), E = 2G*₁₃ pairs
#: (A, C), F = 2G*₁₂ pairs (A, B).
_OFFDIAG_PARTNERS: dict[int, tuple[int, int]] = {3: (1, 2), 4: (0, 2), 5: (0, 1)}


def _stage_edges(basis: np.ndarray, piv: list[tuple[int, float]],
                 lo: np.ndarray, hi: np.ndarray, stage: int) -> np.ndarray:
    """Grid edges for one θ dimension of one box, in the literature's own steps.

    A diagonal dimension is gridded at :data:`AXIS_STEP` in **d**, not in θ —
    equal steps in d are what IT-H specifies and they put the fine sampling where
    the metric is sensitive (θ = 1/d², so a 0.4 Å step at d = 3 Å spans 30× the θ
    interval it does at d = 18 Å).

    An off-diagonal dimension is gridded at :data:`ANGLE_STEP_DEG` of reciprocal
    angle over **this box's own** Cauchy-Schwarz bound, |2G*ᵢⱼ| ≤ 2√(G*ᵢᵢ·G*ⱼⱼ),
    and that is the difference between an affordable 4-D search and an impossible
    one.  Gridding it over the *global* bound instead — √(A_max·C_max), i.e. both
    axes at their shortest — hands most cells an E range they cannot physically
    reach, and nothing prunes them, because the constraint is a cone rather than a
    box.  Since the grid is staged, A and C are already narrowed by the time E is
    cut, so the bound is available for free.  Measured on a monoclinic domain: the
    E axis goes from 18 slabs everywhere to 1-3 in most cells.
    """
    p, v = piv[stage]
    if p < 3:
        d_hi = 1.0 / np.sqrt(max(lo[stage] * v, 1e-12))
        d_lo = 1.0 / np.sqrt(max(hi[stage] * v, 1e-12))
        n = max(int(np.ceil((d_hi - d_lo) / AXIS_STEP)), 1)
        d_edges = np.linspace(d_hi, d_lo, n + 1)
        edges = np.sort(1.0 / (d_edges ** 2 * v))
        edges[0], edges[-1] = lo[stage], hi[stage]
        return edges

    i, j = _OFFDIAG_PARTNERS[p]
    _af_lo, af_hi = _af_interval(basis, lo, hi)
    bound = 2.0 * MAX_ANGLE_COSINE * np.sqrt(max(af_hi[i] * af_hi[j], 0.0)) / v
    edge_lo, edge_hi = max(lo[stage], -bound), min(hi[stage], bound)
    if edge_hi <= edge_lo:
        return np.array([])
    n_full = max(int(np.ceil(2.0 * (90.0 - np.degrees(np.arccos(
        min(MAX_ANGLE_COSINE, 1.0)))) / ANGLE_STEP_DEG)), 1)
    n = max(int(np.ceil(n_full * (edge_hi - edge_lo) / (2.0 * max(bound, 1e-30)))), 1)
    return np.linspace(edge_lo, edge_hi, n + 1)


def _q_bounds(m: np.ndarray, lo: np.ndarray, hi: np.ndarray
              ) -> tuple[np.ndarray, np.ndarray]:
    """[Q_min, Q_max] of every trial hkl over the box — **exact**, at the corners.

    Q = m·θ is linear, so the extremes over an axis-aligned box are attained at a
    corner and are read off componentwise: a positive coefficient takes the low
    edge for the minimum and the high edge for the maximum.  No corner is
    enumerated (there are 2ⁿ) and no bound is conservative.
    """
    pos = m > 0.0
    q_min = np.where(pos, m * lo, m * hi).sum(axis=1)
    q_max = np.where(pos, m * hi, m * lo).sum(axis=1)
    return q_min, q_max


def _af_interval(basis: np.ndarray, lo: np.ndarray, hi: np.ndarray
                 ) -> tuple[np.ndarray, np.ndarray]:
    b = basis.T                                   # (6, m)
    pos = b > 0.0
    return (np.where(pos, b * lo, b * hi).sum(axis=1),
            np.where(pos, b * hi, b * lo).sum(axis=1))


def _imul(x: tuple[float, float], y: tuple[float, float]) -> tuple[float, float]:
    p = (x[0] * y[0], x[0] * y[1], x[1] * y[0], x[1] * y[1])
    return min(p), max(p)


def _isq(x: tuple[float, float]) -> tuple[float, float]:
    """[lo, hi]² as an interval — **0 is the minimum when it straddles zero**.

    ``_imul(x, x)`` treats the two factors as independent and returns a negative
    lower bound for an interval containing 0, which is not a square of anything.
    """
    lo, hi = x
    if lo <= 0.0 <= hi:
        return 0.0, max(lo * lo, hi * hi)
    return min(lo * lo, hi * hi), max(lo * lo, hi * hi)


def _rho_interval(x_lo: float, x_hi: float, y: tuple[float, float],
                  z: tuple[float, float]) -> tuple[float, float]:
    """The off-diagonal as a **correlation**, clipped to the domain's obliquity."""
    c = float(MAX_ANGLE_COSINE)
    if y[0] <= 0.0 or z[0] <= 0.0:
        return -c, c
    small = 2.0 * np.sqrt(y[0] * z[0])       # smallest denominator → largest |ρ|
    big = 2.0 * np.sqrt(y[1] * z[1])
    lo = x_lo / small if x_lo < 0.0 else x_lo / big
    hi = x_hi / small if x_hi > 0.0 else x_hi / big
    return max(lo, -c), min(hi, c)


def _det_interval(af_lo: np.ndarray, af_hi: np.ndarray
                  ) -> tuple[float, float]:
    """Interval bound on det G* over the box, for the volume prune.

    V = (det G*)^(−1/2), so a volume band [V_min, V_max] is the det band
    [1/V_max², 1/V_min²], and the bound must be conservative in the direction
    that costs search time rather than the one that excludes the answer.

    **It is bounded through the correlation form, not the expanded determinant,
    and that is what makes the volume window prune at all.**  Writing
    G* = D^½ R D^½ with D the diagonal gives det G* = A·B·C·det R, so the
    off-diagonals enter only as ρᵢⱼ = G*ᵢⱼ/√(G*ᵢᵢG*ⱼⱼ) — which the search domain
    already bounds by :data:`MAX_ANGLE_COSINE` (``_initial_box``, ``_stage_edges``
    and ``_inside_domain`` all enforce it, so a box's cone-violating corners hold
    nothing this search may report).  Interval arithmetic on the *expanded*
    determinant throws that coupling away: it evaluates −B·(E/2)² with E at the
    **domain's** maximum while A and C are at this **box's**, and the term then
    swamps A·B·C.  Measured over the bethanechol monoclinic domain (d ∈ [5, 20],
    V ∈ [800, 1200]) the expanded form gives det ∈ [−4.80e−5, 6.40e−5] against a
    band of [6.94e−7, 1.56e−6] — det_lo < 0, so "this cell is too small" could
    never fire at any grid stage, which is the whole of WP-1030's opening
    diagnosis.  The correlation form gives [3.91e−9, 6.40e−5] on the same box and
    ABC·[1 − cos²ϑ, 1] on a monoclinic one, and it fires.

    Note this is a *tightening*, not a reordering: the coupling is available
    whether or not the off-diagonals have been cut yet, so the grid keeps the
    staging that lets ``_stage_edges`` narrow the off-diagonal axis from 18 slabs
    to 1-3 using the same Cauchy-Schwarz bound.

    **Both forms are computed and intersected, because neither dominates.**  The
    correlation form carries the diagonal spread twice — once in A·B·C and again
    in ρ's denominator — so on a box narrow in the off-diagonals but not yet in
    the diagonals it is *looser* than the expansion, and using it alone was
    measured to take the bethanechol grid from 298 k boxes to 441 k even while
    cutting the top-stage grid.  The expansion is tight there and useless where
    the cone matters; the intersection of two valid bounds is valid and is at
    least as tight as either.
    """
    a = (float(af_lo[0]), float(af_hi[0]))
    b = (float(af_lo[1]), float(af_hi[1]))
    c = (float(af_lo[2]), float(af_hi[2]))
    # off-diagonals: A..F carries 2·G*, so halve
    d23 = (0.5 * float(af_lo[3]), 0.5 * float(af_hi[3]))
    d13 = (0.5 * float(af_lo[4]), 0.5 * float(af_hi[4]))
    d12 = (0.5 * float(af_lo[5]), 0.5 * float(af_hi[5]))
    diag = _imul(_imul(a, b), c)
    cross_d = _imul(_imul(d12, d13), d23)
    t3, t4, t5 = (_imul(a, _isq(d23)), _imul(b, _isq(d13)), _imul(c, _isq(d12)))
    lo = diag[0] + 2.0 * cross_d[0] - t3[1] - t4[1] - t5[1]
    hi = diag[1] + 2.0 * cross_d[1] - t3[0] - t4[0] - t5[0]

    # the same determinant through det G* = A·B·C·det R, where the domain's
    # obliquity bound clips every ρ
    r23 = _rho_interval(float(af_lo[3]), float(af_hi[3]), b, c)
    r13 = _rho_interval(float(af_lo[4]), float(af_hi[4]), a, c)
    r12 = _rho_interval(float(af_lo[5]), float(af_hi[5]), a, b)
    s23, s13, s12 = _isq(r23), _isq(r13), _isq(r12)
    cross_r = _imul(_imul(r12, r13), r23)
    det_r = (1.0 + 2.0 * cross_r[0] - s23[1] - s13[1] - s12[1],
             1.0 + 2.0 * cross_r[1] - s23[0] - s13[0] - s12[0])
    c_lo, c_hi = _imul(diag, det_r)
    return max(lo, c_lo), min(hi, c_hi)


def _max_index(spec: SearchSpec, q_max: float) -> int:
    """Largest |h| a trial set needs: Q ≥ A_min·h² for the principal directions.

    With A ≥ 1/max_d² the bound is h ≤ max_d·√Q_max — the same statement as
    "d(h00) ≥ d_min", which is why it is exact rather than a margin.
    """
    return int(np.ceil(spec.max_d_axis * np.sqrt(max(q_max, 1e-12)))) + 1


def search_dichotomy(peaks: PeakList, *, spec: SearchSpec | None = None,
                     quality=None, cancel=None, progress=None) -> EngineResult:
    """Exhaustive branch-and-bound over the metric domain, system by system.

    ``quality`` is a :class:`~rietx.schemas.indexing.DataQualityReport`; its
    per-system Smith volume envelope becomes the default ``max_volume``, and its
    ``shift.allowance_deg`` the systematic floor added to every line's σ.  Pass
    it whenever one exists — the alternative is a hard-coded tolerance, which is
    exactly what per-line σ replaced.
    """
    spec = spec or SearchSpec()
    q_all = peaks.q()
    tt_all = peaks.two_theta()
    allowance, assumed = effective_shift_allowance(spec, quality)
    sigma = sigma_effective(peaks.q_esd(), tt_all, peaks.wavelength, allowance)
    tt_max = float(peaks.two_theta_max)

    search = search_line_order(peaks, spec)
    q_search, tol_search = q_all[search], spec.k_sigma * sigma[search]

    systems = [s for s in SYSTEM_ORDER if s in spec.systems]
    result = EngineResult(engine="dichotomy")
    if len(q_all) < 2:
        result.diagnostics.append(Diagnostic(
            level="error", code="INDEX_DATA_INSUFFICIENT",
            message="a lattice cannot be constrained by fewer than two lines",
            where=[f"{len(q_all)} usable lines"],
            suggestion="run assess_peak_list before searching"))
        return result

    incomplete: list[str] = []
    capped: list[str] = []
    raw: list[EngineCandidate] = []
    for system in systems:
        # a system this engine never *started* is not claimed: it stays out of
        # ``systems_searched`` and ``search_complete``, which is what lets the
        # workflow report "not reached" as a third state distinct from
        # "truncated" (WP-1037) — an entered system with an expired token would
        # otherwise record 0 s of work as if it had been searched
        if cancel is not None and bool(cancel):
            break
        result.systems_searched += (system,)
        if progress is not None:
            progress.start(f"dichotomy:{system}", engine="dichotomy",
                           system=system)
        budget = Budget(spec.budget_seconds, cancel)
        basis = metric_basis(system)
        vol_max = search_volume_ceiling(spec, quality, system)
        found, (n_boxes, n_rows), complete = _search_one(
            basis, system, spec.centrings_for(system), spec, budget, q_all,
            sigma, q_search, tol_search, peaks.wavelength, tt_max,
            spec.min_volume, vol_max, search, tt_all)
        raw.extend(found)
        if len(raw) > DEDUP_EVERY:
            raw = dedup_candidates(raw)
        result.search_complete[system] = complete
        result.stats[f"{system}.seconds"] = round(budget.elapsed, 3)
        result.stats[f"{system}.boxes"] = float(n_boxes)
        result.stats[f"{system}.rows_per_box"] = round(n_rows / max(n_boxes, 1), 1)
        if not complete:
            # a unit its budget did not stop hit a size cap, where more
            # time changes nothing (``incomplete_diagnostic``)
            (incomplete if budget.expired() else capped).append(system)
        if progress is not None:
            progress.end(f"dichotomy:{system}", engine="dichotomy",
                         system=system, n_candidates=len(found),
                         complete=complete,
                         provisional=provisional_payload(found))

    # the hand-off pool, not the reported cap (WP-1046): truncating here to the
    # number the answer reports made this Borda — over *this* unit's harvest —
    # decide what consensus was allowed to rank
    result.candidates = rank_candidates(raw, peaks, k_sigma=spec.k_sigma,
                                        n_unindexed=spec.n_unindexed,
                                        max_candidates=spec.engine_pool(),
                                        q_match=sigma)
    result.stats["candidates.raw"] = float(len(raw))
    if len(result.candidates) >= spec.engine_pool():
        for system in result.systems_searched:
            result.stats[f"{system}.pool_capped"] = 1.0
    result.stats["shift_allowance_deg"] = round(allowance, 5)
    if assumed:
        result.diagnostics.append(shift_allowance_diagnostic(allowance))
    if incomplete or capped:
        result.diagnostics.append(
            incomplete_diagnostic("dichotomy", incomplete, spec.budget_seconds,
                                  capped))
    return result


def _centre_volume(basis: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """Unit-cell volume at a box's centre, or ``inf`` if that is not a lattice.

    Used only to *order* the search (smallest cell first), so a box whose centre
    happens to fall outside the metric cone sorts last rather than raising.
    """
    try:
        return float(np.prod(cell_from_af(basis.T @ (0.5 * (lo + hi)))[:3]))
    except ValueError:
        return float("inf")


def _search_one(basis: np.ndarray, system: str, centrings: tuple[str, ...],
                spec: SearchSpec,
                budget: Budget, q_all: np.ndarray, sigma: np.ndarray,
                q_search: np.ndarray, tol_search: np.ndarray, wavelength: float,
                tt_max: float, vol_min: float, vol_max: float,
                search_lines: np.ndarray, tt_all: np.ndarray,
                ) -> tuple[list[EngineCandidate], tuple[int, int], bool]:
    """One system, **every admissible centring in one pass**: grid, then dichotomy.

    **The grid is searched once per system, not once per centring**, and that is
    a completeness argument rather than an optimisation.  ``centring_allows``
    makes each centred trial set a strict *subset* of the primitive one (asserted
    in ``tests/test_indexing_engines.py``), so a centred box has strictly fewer
    reflections with which to reach the same lines: the centred line-matching
    test is harder, every box surviving it survives the primitive test, and **the
    centred pass can therefore find no metric the primitive pass misses**.  All
    the separate pass ever contributed was the *scoring* — which centring's
    reflections explain the pattern — and that is recovered by re-running the
    assign-and-refine step of :func:`_accept` under each admissible centring at
    the leaves, where there are ~10² boxes rather than ~10⁶.  Measured on the
    bethanechol monoclinic domain, dropping the redundant pass is a clean 2× on
    monoclinic and 4× on orthorhombic, for no change in what is reported.

    The two phases are not a refactor of one loop, they are the fix for a measured
    failure.  Running grid subdivision and bisection in one depth-first stack means
    the search dives to a leaf through the *first* grid cell it likes and explores
    that cell's entire bisection subtree — which in 4-D is effectively unbounded —
    before it ever looks at the second cell.  Measured on a monoclinic domain: 11.9
    million boxes in 240 s without once visiting the grid cell that contained the
    answer, even when the volume shell was narrowed to the one holding it.

    Phase 1 completes the grid: every dimension is cut at the literature's steps
    (0.4 Å, 5°), with all the prunes applied *between* dimensions so an impossible
    slab never spawns the 45 children of the next axis.  It is breadth-first, so it
    terminates having seen every surviving cell — which is what makes the grid a
    guarantee rather than a preference.  Phase 2 bisects those survivors, best
    first, depth-first inside each.

    A frontier cap (:data:`MAX_GRID_CELLS`) keeps phase 1's memory bounded, and
    hitting it returns ``search_complete = False`` — an overflowed grid has not
    covered its domain, and that must not look like "nothing there".
    """
    lo0, hi0 = _initial_box(basis, spec)
    # two trial sets, and the distinction is load-bearing.  The *recursion* is
    # driven by the search lines only, so its set stops at their highest Q and
    # every box test stays cheap; **assignment and scoring use every usable
    # line**, so an accepted cell is judged on the whole pattern.  Sharing one
    # search-sized set instead was measured: a tetragonal cell that indexes all
    # 55 lines came back reporting 20 of 55, tying it with every supercell.
    q_hi_search = float(q_search.max() + tol_search.max())
    q_hi_all = float(q_all.max() + spec.k_sigma * sigma.max())
    # the search sees the **union** of the admissible centrings' reflections —
    # the smallest set that can miss no candidate — and each centring keeps its
    # own mask for the leaves.  With "P" admissible the union is every hkl, which
    # is what makes the single pass cover the centred ones.
    hkl_all = trial_hkl(_max_index(spec, q_hi_all), "P")
    masks = {c: centring_allows(hkl_all, c) for c in centrings}
    # **A centring whose own set fits the cap keeps its search when the union
    # does not.**  Sharing one pass means sharing one trial set, so the cap now
    # applies to the union — and the union of an admissible "P" is every hkl.
    # Dropping the whole system there would lose the centred searches that used
    # to run in their own pass (a cubic F set is a quarter of P's, so there is a
    # band of ``max_index`` where F fits and P does not), so the widest sets are
    # dropped until the rest fit, and what is dropped is reported by returning
    # ``complete = False`` exactly as an overflow always has.
    complete_union = True
    order = sorted(masks, key=lambda c: -int(masks[c].sum()))
    while order and int(np.logical_or.reduce(
            [masks[c] for c in order]).sum()) > MAX_TRIAL_HKL:
        order.pop(0)
        complete_union = False
    if not order:
        return [], (0, 0), False
    masks = {c: masks[c] for c in order}
    union = np.logical_or.reduce(list(masks.values()))
    hkl_all = hkl_all[union]
    dm_all = design_matrix(hkl_all)
    # each centring's (hkl, design) pair is sliced **once**, not once per leaf:
    # the arrays are tens of thousands of rows and _accept is called per leaf per
    # centring, so slicing inside that loop cost 3× the whole search when it was
    # first written this way
    per_centring = {c: (hkl_all[mask[union]], dm_all[mask[union]])
                    for c, mask in masks.items()}
    centring_rows = {c: mask[union] for c, mask in masks.items()}
    m_all = dm_all @ basis.T
    root_min, _root_max = _q_bounds(m_all, lo0, hi0)
    search_set = np.flatnonzero(root_min <= q_hi_search)
    m_full = m_all[search_set]
    # each centring's own view of the *recursion* set, for the leaf-level replay
    # of the pass it no longer gets — see the loop in phase 2
    m_search = {c: m_full[rows[search_set]] for c, rows in centring_rows.items()}
    q_hi = q_hi_search

    det_band = (1.0 / max(vol_max, 1e-6) ** 2, 1.0 / max(vol_min, 1e-6) ** 2)
    # **Where to stop bisecting is not the same question as the measurement
    # tolerance**, and conflating them was measured to break the 4-D search
    # outright.  Exhaustiveness comes from the *pruning*, which is exact however
    # coarse the leaves are; acceptance only has to leave a box whose centre the
    # assign-refine loop can polish onto the true cell.  Requiring the box to
    # resolve a line to its own 3σ instead forces ~15 halvings per dimension —
    # depth 60 in monoclinic, the cap — so the leftmost branch never terminates
    # and **zero** leaves were reached in 445 000 boxes.  The right scale is the
    # gap between neighbouring observed lines: below a quarter of it a line cannot
    # be confused with its neighbour, which is all the refinement needs.
    spacing = (float(np.median(np.diff(np.sort(q_search))))
               if len(q_search) > 1 else 0.0)
    tol_accept = max(float(np.min(tol_search)), ACCEPT_SPACING_FRAC * spacing)

    # the stack holds the box's *surviving trial rows*, not indices into the
    # parent set: a child that filters nothing then reuses its parent's array
    # instead of paying a fancy-index copy, and the copy was 30 % of the loop
    lo_search = q_search - tol_search
    hi_search = q_search + tol_search
    swaps = [(_pivot_of(basis, i), _pivot_of(basis, j))
             for i, j in axis_swaps(basis)]
    swaps = [(a, b) for a, b in swaps if a is not None and b is not None]
    found: list[EngineCandidate] = []
    seen: set[tuple[int, ...]] = set()
    n_boxes = 0
    n_rows = 0
    complete = True

    # ---- phase 1: the grid, breadth-first, one dimension at a time ----
    piv = _pivots(basis)
    frontier = [(lo0, hi0, m_full)]
    for stage in range(len(piv)):
        nxt: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for lo, hi, m in frontier:
            if budget.expired():
                return found, (n_boxes, n_rows), False
            n_boxes += 1
            n_rows += len(m)
            kept = _test_box(m, lo, hi, basis, q_hi, det_band, swaps, lo_search,
                             hi_search, spec.n_unindexed)
            if kept is None:
                continue
            m_kept, _width, _unique = kept
            edges = _stage_edges(basis, piv, lo, hi, stage)
            for a, b in zip(edges[:-1], edges[1:]):
                child_lo, child_hi = lo.copy(), hi.copy()
                child_lo[stage], child_hi[stage] = a, b
                nxt.append((child_lo, child_hi, m_kept))
            if len(nxt) > MAX_GRID_CELLS:
                complete = False
                break
        frontier = nxt
        if not complete:
            break

    # ---- phase 2: dichotomy inside each surviving grid cell ----
    # **Smallest cell first, and that is the volume-shell idea done once.**  The
    # literature searches volume shells of 400 Å³ so that a small cell is reported
    # early; iterating shells here was measured to be a trap, because the grid pass
    # is nearly *shell-independent* (its top stages leave whole dimensions
    # undetermined, so the volume interval is too wide to prune) and would be paid
    # again per shell — eight shells × ~70 s of grid on a monoclinic domain, with
    # the shell containing the answer last.  Ordering the survivors by volume gives
    # the same "cheap answers first" property for one grid pass.
    stack = [(lo, hi, m, 0)
             for _v, _i, lo, hi, m in sorted(
                 ((_centre_volume(basis, lo, hi), i, lo, hi, m)
                  for i, (lo, hi, m) in enumerate(frontier)), reverse=True)]
    while stack:
        if budget.expired():
            return found, (n_boxes, n_rows), False
        lo, hi, m, depth = stack.pop()
        n_boxes += 1
        n_rows += len(m)
        kept = _test_box(m, lo, hi, basis, q_hi, det_band, swaps, lo_search,
                         hi_search, spec.n_unindexed)
        if kept is None:
            continue
        m, width, unique = kept

        if unique or width <= tol_accept or depth >= MAX_DEPTH:
            theta = 0.5 * (lo + hi)
            key = _box_key(basis.T @ theta)
            if key in seen:
                continue
            seen.add(key)
            for centring, (hkl_c, dm_c) in per_centring.items():
                # **The centred pass is replayed here, and one box is enough.**
                # Dropping the per-centring *search* must not also drop its
                # per-centring *pruning*: a leaf reached by the union set has
                # not shown that the centred trial set can reach these lines.
                # Measured on SRM 660c, skipping this put a pseudo-cubic
                # trigonal R description of the LaB6 lattice **above** the
                # certified cubic cell — a lower-symmetry description indexes
                # two more lines because the off-lattice tail components fit
                # it.  Testing the leaf alone is *equivalent* to having run the
                # whole centred search: every prune in :func:`_test_box` is
                # monotone under bisection, so a box that survives implies
                # every ancestor survived, and leaf survival is exactly "the
                # centred search would have reached here".
                if _test_box(m_search[centring], lo, hi, basis, q_hi, det_band,
                             swaps, lo_search, hi_search,
                             spec.n_unindexed) is None:
                    continue
                cand = _accept(basis, system, centring, spec, theta,
                               hkl_c, dm_c, q_all, sigma,
                               wavelength, tt_max, vol_min, vol_max, width,
                               search_lines, tt_all)
                if cand is not None:
                    found.append(cand)
            continue

        # bisect the dimension that moves Q most — the one whose own width, times
        # the largest coefficient any surviving reflection gives it, dominates the
        # box's Q extent.  Splitting the widest *parameter* instead would spend
        # levels on a direction the data cannot see.
        if not len(m):
            continue
        span = (hi - lo) * np.max(np.abs(m), axis=0)
        j = int(np.argmax(span))
        mid = 0.5 * (lo[j] + hi[j])
        left_hi, right_lo = hi.copy(), lo.copy()
        left_hi[j] = mid
        right_lo[j] = mid
        _push_children(stack, [(lo, left_hi), (right_lo, hi)], m, lo_search,
                       hi_search, spec.n_unindexed, depth + 1)
    return found, (n_boxes, n_rows), complete and complete_union


#: Relative grid on which a converged box's A..F is hashed to see whether that
#: cell has already been refined.  A **pre**-filter, deliberately crude: the real
#: dedup is WP-1020's χ² equality on the Niggli-reduced form, which runs later on
#: far fewer candidates.  All this avoids is refining the same cell once per
#: sibling leaf — measured, that was 9.8 s of a 15 s orthorhombic run when it was
#: a linear scan over the accepted list, and a hash makes it constant time.  Two
#: cells straddling a grid boundary are refined twice and merged later, which is
#: the right failure for a performance filter to have.
_SAME_BOX_RTOL = 1e-3


def _box_key(af: np.ndarray) -> tuple[int, ...]:
    """A converged box's identity, **on each component's own scale**.

    The grid has to be relative *per component*, not relative to the largest one,
    and dividing every component by ``max|af|`` — which this did before WP-1026 —
    is a silent precision loss on exactly the axis a powder pattern determines
    least well.  A = 1/a\\*² for a long axis is an order of magnitude below A for a
    short one, so a grid 0.1 % of the largest component is a **1 %** grid on the
    smallest, and two leaves whose long axis differs by 0.5 % hash the same.  The
    first is refined and the second is skipped — not merged, *skipped*, before any
    fit exists to merge.

    Measured on the certified corundum pattern (SRM 676a, a = 4.7594, c = 12.9923):
    the whole trigonal-R domain converged to **11 leaves, 3 of them skipped**, and
    one of the three was the leaf holding the certified c.  The leaf that was
    refined instead sat 0.4 % away in c and gave the answer the acceptance suite
    had recorded as "what an uncalibrated lab pattern costs" — c **+2799 ppm**,
    with a right to −64 ppm because a is where the grid was fine.  It was neither
    an absorbed shift nor the tolerance: it was this hash.

    So each diagonal component gets a **logarithmic** bin of fixed ratio (a
    relative grid is what "the same cell" means), and each off-diagonal a linear
    bin scaled by the geometric mean of its Cauchy-Schwarz partners
    (:data:`_OFFDIAG_PARTNERS`) — the same scale ``_inside_domain`` bounds it by,
    and the only one available for a component that is legitimately zero.
    """
    a = np.asarray(af, dtype=np.float64)
    if not np.all(np.isfinite(a)) or np.any(a[:3] <= 0.0):
        return (0,) * len(a)
    step = float(np.log1p(_SAME_BOX_RTOL))
    key = [int(np.floor(np.log(v) / step)) for v in a[:3]]
    for p, (i, j) in _OFFDIAG_PARTNERS.items():
        scale = float(np.sqrt(a[i] * a[j])) * _SAME_BOX_RTOL
        key.append(int(np.floor(a[p] / scale)) if scale > 0.0 else 0)
    return tuple(key)


def _inside_domain(af: np.ndarray, spec: SearchSpec) -> bool:
    """Is this refined metric still inside the domain the search covered?

    The refinement is free to move, and it does: an accepted box near the obliquity
    bound refined out to β = 174° with a 49 Å axis, a cell no part of the domain
    contains.  Reporting it would be worse than useless — the engine's *whole*
    contract is that it covered a stated domain, so a cell outside it carries none
    of the exhaustiveness the engine exists to provide, and a caller cannot tell
    which is which.  Rejecting it here is not a quality filter but a scope one.
    """
    d = np.zeros(3)
    for i in range(3):
        if af[i] <= 0.0:
            return False
        d[i] = 1.0 / np.sqrt(af[i])
    if np.any(d < spec.min_d_axis * (1.0 - 1e-6)) or np.any(
            d > spec.max_d_axis * (1.0 + 1e-6)):
        return False
    for p, (i, j) in ((3, (1, 2)), (4, (0, 2)), (5, (0, 1))):
        bound = 2.0 * MAX_ANGLE_COSINE * np.sqrt(af[i] * af[j])
        if abs(af[p]) > bound * (1.0 + 1e-6):
            return False
    return True


def _accept(basis: np.ndarray, system: str, centring: str, spec: SearchSpec,
            theta: np.ndarray, hkl: np.ndarray, dm: np.ndarray,
            q_all: np.ndarray, sigma: np.ndarray, wavelength: float,
            tt_max: float, vol_min: float, vol_max: float,
            width: float, search_lines: np.ndarray,
            two_theta: np.ndarray) -> EngineCandidate | None:
    """Turn a converged box into a refined candidate, or reject it.

    Assign, refine, repeat — with the match window **annealed** from the box's own
    resolution down to the measurement's, then held at σ until the assignment
    stops changing.  Each half of that schedule fixes a failure that was measured
    here:

    * *starting at the box's width.*  A leaf's centre is uncertain by half the
      box's induced Q width, which is many σ.  On a cubic list the box holding the
      true cell had a centre 2.6σ off, so a 3σ window assigned **zero** lines and
      the candidate was dropped — the search had found the answer and the
      acceptance step threw it away.
    * *annealing rather than jumping.*  Assigning once at the wide window locks in
      whichever near-neighbour reflection each line happened to be closest to, and
      refining on that lands in a local optimum: on an orthorhombic list the truth
      came back as (7.0002, 7.9972, 9.0002) indexing 57 of 88 lines, which then
      lost the ranking to an exact supercell indexing all 88.  Tightening by 4× a
      pass lets each refinement correct the assignment before the window closes on
      it — the same reason a staged refinement plan exists one rank up.

    The χ² bar is ``k_sigma²`` and it is not arbitrary: every assigned line is
    within k·σ by construction, so k² is the largest reduced χ² an honest
    assignment can reach, and a leaf above it has matched lines to reflections
    that do not explain them.
    """
    af = basis.T @ theta
    try:
        cell = cell_from_af(af)
    except ValueError:
        return None
    fit = None
    previous: bytes | None = None
    boot = 0.5 * width / max(spec.k_sigma, 1e-12)
    schedule = [boot * ANNEAL_FACTOR ** -i for i in range(MAX_ASSIGN_PASSES)]
    for extra, floor in enumerate(schedule + [0.0, 0.0]):
        if not reflection_ceiling_ok(cell, wavelength, tt_max):
            return None
        line_index, assigned = assign_lines(
            q_all, np.maximum(sigma, floor), hkl, af, k_sigma=spec.k_sigma,
            design=dm)
        if len(line_index) < basis.shape[0] + 1:
            return None
        key = line_index.tobytes()
        if key == previous and extra >= len(schedule):
            break
        previous = key
        try:
            fit = refine_candidate(q_all[line_index], sigma[line_index], assigned,
                                   system=system)
        except (ValueError, np.linalg.LinAlgError):
            return None
        af, cell = fit.af, fit.cell
    if fit is None:
        return None
    volume = fit.volume
    if not (vol_min <= volume <= vol_max):
        return None
    if not _inside_domain(fit.af, spec):
        return None
    if fit.chi2_red > spec.k_sigma ** 2:
        return None
    if not indexes_the_search_lines(line_index, search_lines, spec.n_unindexed):
        return None
    fit = refine_with_shift(fit, spec, system, q_all, sigma, two_theta,
                            wavelength, line_index, assigned)
    return EngineCandidate(fit=fit, system=system, centring=centring,
                           engine="dichotomy", hkl=assigned,
                           line_index=line_index, n_lines=len(q_all))


register_engine(
    "dichotomy", search_dichotomy,
    "exhaustive branch-and-bound over the metric domain; slow, and the only "
    "engine whose failure to find a cell is evidence that none exists within "
    "the bounds searched")

__all__ = ["MAX_ANGLE_COSINE", "MAX_DEPTH", "MAX_TRIAL_HKL", "search_dichotomy"]
