"""Geometrical ambiguity — enumerated and **reported, never resolved**.

A powder pattern carries only the *length* of each reciprocal vector, so distinct
lattices can produce calculated patterns with identical line positions (Mighell,
A. D. & Santoro, A. (1975), *J. Appl. Cryst.* **8**, 372-374).  No amount of
counting statistics separates them: the information is absent from the
measurement, not buried in noise.  This module therefore does three things and
stops.

1. **Enumerate** the derivative lattices of index 2-4 exactly, as integer
   matrices in Hermite normal form.  The closed sets have 7, 13 and 35 members —
   which is a *self-check*, not a comment: :func:`hnf_matrices` reproduces those
   counts in ``tests/test_indexing_reduce.py``, so an enumeration bug shows up as
   a count mismatch rather than as a silently missing partner.
2. **Test** each against the observed lines, and keep only those that explain
   them as well as the parent does.  A derivative lattice that predicts extra
   lines *where lines were observed to be absent* is excluded by the data; one
   whose extra lines fall outside the measured range, or wherever nothing was
   looked for, is not — and that distinction is the whole content of the report.
3. **Say what would break the tie.**  ``discriminating_reflections`` carries the
   hkl and the 2θ where the partner and the parent differ, so the report is
   actionable rather than merely honest — the structural twin of Layer 2's
   "extend the fit range".

A setting change is *not* an ambiguity: derivative lattices that Niggli-reduce to
the parent are dropped, which is what keeps this question distinct from dedup
(``reduce.same_lattice``).

**Step 2's exclusion was stated here from the start and not implemented until
WP-1024, and the gap was not cosmetic.**  A superlattice's reciprocal lattice
strictly *contains* the parent's, so it indexes every observed line exactly and
ties the parent on every forward-looking figure — which meant the original screen
(compare ``n_indexed``, compare the mean discrepancy) reported **every** derivative
lattice as a partner: measured, 28 partners for a certified cubic cell on exact
synthetic positions, 20-35 across systems.  The consequence is one rank up: WP-1024's
confidence gate refuses ``high`` to any candidate with an ambiguity partner, so the
indexer could never have answered at all.  And the answer was already in the
docstring — a doubled cubic cell predicts lines at half the parent's d-spacings,
those lines are *not there*, and their absence is data.  ``predicted_seen_fraction``
exists one module over for exactly this reason; this is the same measurement asked
about one lattice instead of a ranking.

The exclusion is **asymmetric on purpose** and the asymmetry is what makes it
sound: it tests the partner's *extra* predictions, never the parent's own absent
ones.  A correct lattice routinely predicts reflections nothing is observed at
(space-group extinctions, not yet determined while indexing runs, and lines too weak to
detect — the truth showed 56.5 % of its own predicted lines in this repo's §D
data), so a symmetric rule would exclude the truth first.  What the data can rule
out is a line a *rival* lattice needs and the parent does not.

**Why excluding a supercell is crystallography and not convenience.**  A 2a cell
whose odd reflections are *identically* zero is not a lattice statement at all: a
structure with no superlattice intensity has the a-translation, so the lattice
*is* the a-lattice and the 2a cell is a cell choice.  Indexing determines the
lattice, so the small cell is the answer and the supercell is not a rival
hypothesis about it.  What this exclusion genuinely gets wrong is the *weak*
case — a partially-ordered superstructure whose superlattice reflections are
non-zero but below the peak picker's detection floor.  That case is not lost,
it moves: the whole-profile Le Bail validation (WP-1024's
``predicted_but_absent``) asks the same question of the **pattern** rather than of
the peak list, where a line an order below the detection threshold still shows,
and ``discriminating_reflections`` says where to count longer.  Read a partner
list, therefore, as "positions alone cannot separate these", never as "no
supercell is possible".
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import product

import numpy as np

from ..schemas.indexing import AmbiguityPartner, q_of_two_theta
from .fom import MATCH_SIGMA, match_lines, predicted_lines
from .reduce import (
    BRAVAIS_OBLIQUITIES,
    _basis_change,
    reduce_cell,
    same_lattice,
)

#: Highest derivative-lattice index enumerated.  A fence, recorded rather than
#: attempted: the HNF count grows (7, 13, 35 at index 2, 3, 4) and so does the
#: chance that a high-index partner is a numerical coincidence rather than a
#: geometrical one.  Mighell & Santoro's tabulated cases are low-index.
MAX_AMBIGUITY_INDEX = 4
#: How much worse a partner's mean |ΔQ| may be than the parent's and still count
#: as explaining the data equally well.  Not a statistical threshold — it is a
#: deliberately *permissive* screen, because the cost of reporting a partner that
#: is in fact distinguishable is a caller checking one extra reflection, while the
#: cost of missing one is a cell quoted with a confidence it has not earned.
#: Permissive is safe **because the absence test is not**: this comparison decides
#: whether a partner explains the observed lines, and
#: :func:`extras_absent_in_range` decides whether the data refute it.  Before that
#: second test existed this slack was the only screen, and a screen that a
#: superlattice passes by construction is not one.
AMBIGUITY_DISCREPANCY_SLACK = 1.5
#: Most discriminating reflections listed per partner.  The strongest evidence is
#: at low angle (where lines are sparse and well resolved), so the list is the
#: lowest-2θ differences rather than a sample.
MAX_DISCRIMINATING = 6
#: How far past the measured 2θ range a partner's reflections are predicted, as a
#: factor on ``two_theta_max``.  Needed because a *surviving* partner is by
#: definition one whose extra lines inside the range all coincide with observed
#: ones — so its discriminating reflections lie **outside** the range, and
#: predicting only as far as the data reach would leave every ambiguity report
#: with nothing actionable in it.  1.5 rather than the physical limit (2θ → 180°)
#: because "collect 50 % further" is advice a diffractometer can take, and the
#: reflections just past the edge are the cheapest ones to go and look for.
AMBIGUITY_EXTEND_FACTOR = 1.5


def hnf_matrices(index: int) -> list[np.ndarray]:
    """Every sublattice of Z³ of the given index, as an upper-triangular HNF.

        H = [[a, b, c], [0, d, e], [0, 0, f]],  a·d·f = index,
        0 ≤ b < d,  0 ≤ c < f,  0 ≤ e < f

    which enumerates each sublattice exactly once (Hermite normal form is
    canonical).  Counts: 7, 13, 35 for index 2, 3, 4.
    """
    if index < 1:
        raise ValueError("index must be a positive integer")
    out: list[np.ndarray] = []
    for a in range(1, index + 1):
        if index % a:
            continue
        rest = index // a
        for d in range(1, rest + 1):
            if rest % d:
                continue
            f = rest // d
            for b, c, e in product(range(d), range(f), range(f)):
                out.append(np.array([[a, b, c], [0, d, e], [0, 0, f]],
                                    dtype=np.int64))
    return out


def transform_cell(cell: tuple[float, ...], matrix: np.ndarray
                   ) -> tuple[float, float, float, float, float, float]:
    """The cell of the lattice whose basis is ``matrix @ basis``.

    Works on the metric rather than on cell parameters: G' = H·G·Hᵀ, which is
    exact for any integer H and needs no Cartesian realisation of the basis.
    """
    from ..crystallography.lattice import direct_metric_tensor
    from .qspace import af_from_gstar, cell_from_af

    g = np.asarray(direct_metric_tensor(*cell), dtype=np.float64)
    h = np.asarray(matrix, dtype=np.float64)
    g_new = h @ g @ h.T
    return cell_from_af(af_from_gstar(np.linalg.inv(g_new)))


def derivative_cells(cell: tuple[float, ...], *,
                     max_index: int = MAX_AMBIGUITY_INDEX):
    """(index, H, cell) for every derivative lattice that is not the parent.

    Both directions are generated: ``H`` gives a **superlattice** in direct space
    (a larger cell, denser reciprocal lattice) and its inverse-transpose analogue
    the **sublattice**.  Only the direct-space superlattices are enumerated here
    and the sublattice case is reached by running the same enumeration from the
    partner's point of view, which is what an engine does when it proposes both.
    Partners reducing to the parent are dropped — that is a setting change, i.e.
    dedup's business, not ambiguity's.
    """
    from .qspace import af_from_cell

    parent_af = af_from_cell(cell)
    out = []
    for index in range(2, max_index + 1):
        for h in hnf_matrices(index):
            try:
                child = transform_cell(cell, h)
            except (ValueError, np.linalg.LinAlgError):
                continue
            equal, _ = same_lattice(parent_af, af_from_cell(child))
            if equal:
                continue
            out.append((index, h, child))
    return out


def extras_absent_in_range(q_extra: np.ndarray, q_obs: np.ndarray,
                           q_esd: np.ndarray, q_lo: float, q_hi: float, *,
                           k_sigma: float = MATCH_SIGMA) -> int:
    """How many of a partner's **extra** predictions land in the measured range
    with no observed line there.

    Any one of them excludes the partner: it needs a reflection the pattern
    demonstrably does not have.  The window is the *observed* line's own σ, the
    same reversal :func:`~rietx.indexing.fom.predicted_seen_fraction` makes —
    the precision belongs to the measurement, so it stays attached to the
    observation even when the loop runs the other way.
    """
    extra = np.asarray(q_extra, dtype=np.float64)
    inside = extra[(extra >= q_lo) & (extra <= q_hi)]
    if not len(inside):
        return 0
    obs = np.asarray(q_obs, dtype=np.float64)
    if not len(obs):
        return int(len(inside))
    sig = np.maximum(np.asarray(q_esd, dtype=np.float64), 1e-300)
    d = np.abs(inside[:, None] - obs[None, :])
    j = np.argmin(d, axis=1)
    seen = d[np.arange(len(inside)), j] <= k_sigma * sig[j]
    return int(np.count_nonzero(~seen))


def ambiguity_partners(cell: tuple[float, ...], system: str, centring: str,
                       q_obs: np.ndarray, q_esd: np.ndarray, wavelength: float,
                       two_theta_max: float, *,
                       two_theta_min: float = 0.0,
                       max_index: int = MAX_AMBIGUITY_INDEX,
                       k_sigma: float = MATCH_SIGMA,
                       cancel=None,
                       ) -> list[AmbiguityPartner] | None:
    """Derivative lattices this data cannot distinguish from ``cell``.

    The test is empirical rather than taxonomic, and it is two-sided:

    * the partner must **explain** the observed lines at least as well as the
      parent — at least as many indexed, a mean discrepancy no more than
      :data:`AMBIGUITY_DISCREPANCY_SLACK` times worse;
    * and the data must not **refute** it — a single extra prediction inside the
      measured 2θ range with no observed line at it (:func:`extras_absent_in_range`)
      drops the partner, because that is a reflection the pattern says is not
      there.

    Only the second half distinguishes a genuine geometrical ambiguity from an
    ordinary supercell (see the module docstring for what happened without it).

    What makes a surviving entry useful is ``discriminating_reflections`` — and
    note where they now are: a partner that survived has no absent extras *inside*
    the range, so the lines that would settle it lie **outside** it, up to
    :data:`AMBIGUITY_EXTEND_FACTOR`·``two_theta_max`` (or below
    ``two_theta_min``).  The report is therefore literally "collect here and
    look", the structural twin of Layer 2's "extend the fit range".

    ``cancel`` is read before each derivative cell, so a stop waits one
    child's work rather than the whole sweep (#895, WP-1924).  On #780's
    monoclinic cell the sweep is 0.9 s of CPU and its slowest child 47 ms.  A
    sweep the token stops returns ``None``, never the partners found so far:
    a partial list reads as a complete answer, and an empty one as "no
    partners".
    """
    from ..crystallography.lattice import cell_volume

    obs = np.asarray(q_obs, dtype=np.float64)
    esd = np.asarray(q_esd, dtype=np.float64)
    tt_ext = min(float(two_theta_max) * AMBIGUITY_EXTEND_FACTOR, 179.0)
    q_lo = float(q_of_two_theta(np.array([max(two_theta_min, 0.0)]),
                                wavelength)[0])
    q_hi = float(q_of_two_theta(np.array([two_theta_max]), wavelength)[0])
    _hkl, q_parent = predicted_lines(cell, system, centring, wavelength, tt_ext)
    q_parent_in = q_parent[q_parent <= q_hi]
    idx_parent, dq_parent = match_lines(obs, esd, q_parent_in)
    n_parent = int(np.count_nonzero(idx_parent >= 0))
    base = dq_parent[np.isfinite(dq_parent)]
    mean_parent = float(np.mean(base)) if len(base) else float("inf")
    tol = float(np.median(esd)) if len(esd) else 0.0

    out: list[AmbiguityPartner] = []
    for index, h, child in derivative_cells(cell, max_index=max_index):
        if cancel is not None and bool(cancel):
            return None
        try:
            hkl_c, q_child = predicted_lines(child, "triclinic", "P", wavelength,
                                             tt_ext)
        except (ValueError, RuntimeError):
            continue
        in_range = q_child <= q_hi
        idx_c, dq_c = match_lines(obs, esd, q_child[in_range])
        n_child = int(np.count_nonzero(idx_c >= 0))
        finite = dq_c[np.isfinite(dq_c)]
        mean_child = float(np.mean(finite)) if len(finite) else float("inf")
        if n_child < n_parent:
            continue
        # Floored at the median σ(Q), exactly as ``m20`` floors its ⟨ΔQ⟩ and for
        # the same reason: a discrepancy below the measurement precision is not
        # knowable.  Without the floor this comparison is a ratio of fp noise on
        # exact positions (both means ~1e-16), so which partner survives depends
        # on summation order rather than on the data.
        if not (mean_child <= AMBIGUITY_DISCREPANCY_SLACK * max(mean_parent,
                                                                tol, 1e-300)):
            continue
        extra = _extra_mask(q_child, q_parent, tol)
        if extras_absent_in_range(q_child[extra], obs, esd, q_lo, q_hi,
                                  k_sigma=k_sigma):
            continue                      # refuted by the absent reflections
        refl, tt = _discriminating(hkl_c[extra], q_child[extra], q_lo, q_hi,
                                   wavelength)
        out.append(AmbiguityPartner(
            cell=child, transformation=[[int(v) for v in row] for row in h],
            index=index, system="triclinic",
            volume=float(cell_volume(*child)),
            discriminating_reflections=refl, discriminating_two_theta=tt))
    return out


def _extra_mask(q_child: np.ndarray, q_parent: np.ndarray,
                tol: float) -> np.ndarray:
    """Which of the partner's predictions the parent does not share.

    Tolerance is the *median* observed σ(Q): a difference smaller than the data's
    own precision would not settle anything, so a prediction that close to a
    parent line is the same line and not an extra.
    """
    return _nearest_gap(q_child, q_parent) > max(tol, 1e-12)


def _nearest_gap(q: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Each ``q``'s distance to the nearest ``ref``, ``inf`` when there is none.

    By binary search, as ``fom.match_lines`` does: a full distance matrix is
    extras × parent lines, which at 0.41 Å on a 10 Å cell is ~10⁹ entries
    (WP-1449, 11-BM NAC).
    """
    q = np.asarray(q, dtype=np.float64)
    if not len(ref):
        return np.full(len(q), np.inf)
    ref = np.sort(np.asarray(ref, dtype=np.float64))
    right = np.searchsorted(ref, q)
    left = np.clip(right - 1, 0, len(ref) - 1)
    right = np.clip(right, 0, len(ref) - 1)
    return np.minimum(np.abs(q - ref[left]), np.abs(q - ref[right]))


def _discriminating(hkl_extra: np.ndarray, q_extra: np.ndarray, q_lo: float,
                    q_hi: float, wavelength: float):
    """The partner's extra predictions **outside** the measured range, nearest
    edge first.

    Inside the range there are none to report — an extra in range with nothing
    observed at it already excluded the partner, and one *with* a line at it is
    not discriminating.  So this is the "measure further" list, ordered by how far
    the diffractometer would have to go: the reflections just past the edge are
    the cheapest evidence, exactly as the lowest-angle ones were before the
    exclusion moved the question outward.
    """
    outside = (q_extra < q_lo) | (q_extra > q_hi)
    hkl_keep, q_keep = np.asarray(hkl_extra)[outside], q_extra[outside]
    # distance past whichever edge it sits beyond, in Q — a total order over both
    # directions, so a low-angle partner line is not ranked behind every
    # high-angle one merely because Q is small there
    beyond = np.where(q_keep > q_hi, q_keep - q_hi, q_lo - q_keep)
    order = np.argsort(beyond)[:MAX_DISCRIMINATING]
    hkl_keep, q_keep = hkl_keep[order], q_keep[order]
    tt = np.degrees(2.0 * np.arcsin(np.clip(wavelength * np.sqrt(q_keep) / 2.0,
                                            -1.0, 1.0)))
    return ([tuple(int(v) for v in row) for row in hkl_keep],
            [float(v) for v in tt])


#: How far two candidates' fitted volumes may sit from an exact integer ratio
#: and still be tried as parent and derivative.  A **prefilter on a pair**, not a
#: verdict: :func:`_derivative_transform` decides, and it decides on the
#: reduced metrics (:func:`_same_reduced_metric`).  One per cent because the two
#: cells are independent fits of the same lattice — measured on the round-robin
#: brucite pattern (WP-1446), the a × 2 supercell's volume sits 6 ppm from 4×
#: the truth's, so a per cent is four orders of slack on what it has to admit
#: while still cutting the pair list from N² to the few that can be related.
_DERIVATIVE_VOLUME_RTOL = 1e-2


def _derivative_transform(parent_cell: tuple[float, ...],
                          child_cell: tuple[float, ...], *,
                          max_index: int = MAX_AMBIGUITY_INDEX
                          ) -> np.ndarray | None:
    """``H`` with ``child`` = the index-n superlattice ``H`` makes of ``parent``.

    ``None`` when no such H exists at or below ``max_index``.  The two cells are
    **independent fits**, so the comparison is between the reduced forms
    (:func:`_same_reduced_metric`) rather than a band in Q — measured on brucite (WP-1446), the parent's predicted lines sit
    a median 7.0e-5 in Q from the supercell's against a median σ(Q) of 6.8e-5, so
    a line-position test is not separable at this data's own precision while the
    lattice test is exact to the fitting difference.

    The volume ratio prefilters the pair (:data:`_DERIVATIVE_VOLUME_RTOL`) because
    ``det H`` **is** that ratio, so a pair whose volumes are not in integer
    proportion cannot be related by any H and needs no enumeration.

    **The enumeration runs in the child's frame, and that is not a detail.**
    The comparison is between *reduced* forms, so an H passing it says only that
    ``lattice(H·parent)`` and ``lattice(child)`` are the same lattice — the
    child's own fitted basis is then ``U·H·parent`` for some unimodular ``U``,
    and ``H⁻¹`` applied to *that* basis gives ``H⁻¹UH·parent``, a lattice of the
    parent's volume that need not be the parent's.  Since
    :func:`_parent_coordinates` maps the child's reflections through exactly that
    product, the test is run the way it is used: ``transform_cell(child, H⁻ᵀ)``
    is required to reduce to the parent, and ``Hᵀ`` is returned.  The transposed
    HNF set is the complete one for that direction (the row form is canonical
    under *left* multiplication by a unimodular matrix, its transpose under
    *right*), so nothing is lost by asking the question from this side.  Asked
    from the parent's side instead, a child reported in a permuted setting —
    ``(2a, a, a)`` for a doubled cubic cell rather than ``(a, a, 2a)`` — takes
    the first H in the list and hands the test an ``(2a, a, a/2)`` lattice,
    whose extras are a different set; measured (WP-1446), the same supercell was
    refuted in one setting and cleared in the other.
    """
    from ..crystallography.lattice import cell_volume
    from .qspace import af_from_cell
    from .reduce import reduced_af

    v_parent = float(cell_volume(*parent_cell))
    v_child = float(cell_volume(*child_cell))
    if v_parent <= 0.0 or v_child <= 0.0:
        return None
    ratio = v_child / v_parent
    index = int(round(ratio))
    if index < 2 or index > max_index:
        return None
    if abs(ratio - index) > _DERIVATIVE_VOLUME_RTOL * index:
        return None
    target = reduced_af(af_from_cell(parent_cell))
    for h in hnf_matrices(index):
        ht = np.ascontiguousarray(h.T)
        try:
            candidate = transform_cell(
                child_cell, np.linalg.inv(np.asarray(ht, dtype=np.float64)))
            equal = _same_reduced_metric(reduced_af(af_from_cell(candidate)),
                                         target)
        except (ValueError, np.linalg.LinAlgError):
            continue
        if equal:
            return ht
    return None


def _same_reduced_metric(red_a: np.ndarray, red_b: np.ndarray) -> bool:
    """``same_lattice``'s relative test, with the angles banded on the metric.

    :func:`~rietx.indexing.reduce.equal_reduced` compares A..F component by
    component, so an off-diagonal term at a right angle compares fp noise with
    fp noise (1e-16 against −7e-18) and calls the same lattice two
    (``indexing/CLAUDE.md``: near 90° that test is arbitrarily tight).  Here the
    pairing missed every orthogonal parent a transformation had written with
    noise, the cubic F and I cells over a doubled P among them (WP-1449).  So
    each off-diagonal term is held to the same relative bound on the two
    diagonal terms it couples, √(G*ᵢᵢ·G*ⱼⱼ) — never on the largest diagonal,
    which on an elongated cell lets a short-axis pair's angle drift by a degree
    and still pair.  Dedup keeps ``same_lattice`` as it is.
    """
    from .qspace import _AF_INDEX
    from .reduce import CELL_EQUALITY_RELATIVE

    a, b = np.asarray(red_a, dtype=np.float64), np.asarray(red_b, dtype=np.float64)
    scale = np.maximum(np.abs(a), np.abs(b))
    for p, (i, j) in enumerate(_AF_INDEX[3:], start=3):
        scale[p] = max(scale[p], float(np.sqrt(scale[i] * scale[j])))
    return bool(np.all(np.abs(a - b) <= CELL_EQUALITY_RELATIVE * scale))


#: Significance level of :func:`supercell_chance`.  A convention, not a fit
#: (WP-1449): over the acceptance corpus's finished searches every correct cell
#: tested as a child sat at p ≤ 0.0072 and every wrong one at p ≥ 0.27, and 0.01
#: falls between them without having been placed there.  The truth side is the
#: close one — a pseudo-tetragonal description of LaB6 over its half-volume
#: rival, 2 of 3 extras seen — and a truth read as refuted there would move
#: below a cell it already sits below.  Since thresholds version 1.7 that pair
#: reads *undecided*, every seen extra lying on a line the rival explains
#: (:meth:`SupercellEvidence.verdict`).
SUPERCELL_CHANCE_ALPHA = 0.01
#: Metric deviation up to which a lattice symmetry still counts when deciding
#: which reflections an extinction could cancel (:func:`lattice_point_group`):
#: the sine of the Bravais screen's loosest obliquity, 3°, so every symmetry that
#: screen could report is counted.  Loose on purpose.  A pseudo-symmetric
#: lattice's near-special reflections are set aside with the special ones, since
#: a space group of the higher symmetry could extinguish them too.
UNCANCELLABLE_METRIC_RTOL = float(np.sin(np.radians(max(BRAVAIS_OBLIQUITIES))))


@lru_cache(maxsize=1)
def _unit_unimodular() -> np.ndarray:
    """Every 3 × 3 integer matrix with entries in {−1, 0, 1} and det ±1."""
    w = np.array(list(product((-1, 0, 1), repeat=9)),
                 dtype=np.int64).reshape(-1, 3, 3)
    det = np.rint(np.linalg.det(w.astype(np.float64))).astype(np.int64)
    return w[np.abs(det) == 1]


def lattice_point_group(cell: tuple[float, ...], centring: str = "P", *,
                        rtol: float = UNCANCELLABLE_METRIC_RTOL,
                        ) -> tuple[np.ndarray, np.ndarray]:
    """``(W, M)``: the lattice's point symmetries, and the basis they act on.

    ``W`` holds integer matrices acting on the rows of the lattice's **primitive
    reduced** basis, and ``M`` takes the conventional cell to that basis
    (reduced rows = ``M`` · conventional rows), so a reflection's primitive
    indices are ``M·hkl``.  A matrix is a symmetry when it preserves the metric,
    ``W·G·Wᵀ = G``, each element to ``rtol`` of √(Gᵢᵢ·Gⱼⱼ).  The centring
    is consumed by the reduction, so a centred lattice's group comes out in its
    primitive frame.

    Found from the metric, not from the reported system, so a truth reported
    in a lower system still has its whole group.  The candidates are the
    {−1, 0, 1} matrices, searched on the Niggli-reduced basis.  That is enough
    there, and it is checked rather than cited: ``tests/test_indexing_reduce.py``
    recovers the order of every holohedry (2, 4, 8, 12, 16, 24, 48) over all
    fourteen Bravais lattices, the way :func:`hnf_matrices` checks its counts.
    """
    from ..crystallography.lattice import direct_metric_tensor

    reduced = reduce_cell(tuple(cell), centring)
    g = np.asarray(direct_metric_tensor(*reduced.cell), dtype=np.float64)
    w = _unit_unimodular()
    moved = np.einsum("nij,jk,nlk->nil", w, g, w)
    # each element against the lengths it couples, √(g_ii·g_jj): normalised by
    # the largest diagonal alone, a long axis swamps the short ones and every
    # {−1, 0, 1} mixing of them passes (720 "symmetries" on a 5 × 5 × 40 Å
    # tetragonal cell, 16 on a monoclinic 6 × 7 × 20 Å one)
    d = np.sqrt(np.diag(g))
    dev = np.max(np.abs(moved - g) / np.outer(d, d), axis=(1, 2))
    return w[dev <= rtol], _basis_change(reduced.change_of_basis)


def uncancellable(cell: tuple[float, ...], centring: str, hkl: np.ndarray, *,
                  rtol: float = UNCANCELLABLE_METRIC_RTOL) -> np.ndarray:
    """Which reflections no space-group extinction can remove.

    International Tables sorts reflection conditions into three kinds.
    *Integral* conditions come from the centring and act on every hkl.
    *Zonal* conditions come from glide planes and act only on reflections in the
    plane the glide's mirror fixes.  *Serial* conditions come from screw axes and
    act only on the row the axis fixes (*International Tables for
    Crystallography* Vol. A (2002), §2.2.13).  A space group's point group lies
    inside its lattice's, so a reflection that **no** symmetry of the lattice
    fixes can be extinguished by no space group of that lattice, whatever it
    turns out to be.  The centring is the lattice's own and is decided before
    this question: pass reflections the centring allows.

    ``True`` where no element of :func:`lattice_point_group` other than the
    identity fixes the reflection.  A symmetry ``W`` sends primitive indices
    ``k`` to ``W⁻¹k``, so the test is ``W·k = k`` over the group.
    """
    ops, m = lattice_point_group(cell, centring, rtol=rtol)
    identity = np.all(ops == np.eye(3, dtype=np.int64), axis=(1, 2))
    ops = ops[~identity].astype(np.float64)
    k = np.atleast_2d(np.asarray(hkl, dtype=np.float64)) @ m.T
    if not len(k) or not len(ops):
        return np.ones(len(k), dtype=bool)
    image = np.einsum("nij,mj->mni", ops, k)
    fixed = np.all(np.abs(image - k[:, None, :]) < 1e-6, axis=2)
    return ~np.any(fixed, axis=1)


def chance_rate(q_obs: np.ndarray, q_esd: np.ndarray, q_lo: float, q_hi: float,
                *, k_sigma: float = MATCH_SIGMA) -> float:
    """p₀ — the share of ``[q_lo, q_hi]`` lying inside some observed line's window.

    The rate at which a position nothing was ever at still reads as *seen*: a
    reflection placed uniformly in the range lands inside the union of the
    windows with exactly this probability.  The windows are the ones
    :func:`supercell_chance` counts a line as seen with, ``k_sigma`` × σ(Q) about
    each observed line, so the null and the count ask one question.  Overlapping
    windows are counted once, and each is clipped to the range.

    Over the acceptance corpus it runs from 0.007 (zincite) to 0.152
    (corundum) under each search's own window (WP-1449).  The higher it is, the
    less a seen line says, and a test against it has less power by
    construction.
    """
    width = float(q_hi) - float(q_lo)
    if not width > 0.0:
        raise ValueError(f"empty Q range [{q_lo}, {q_hi}]")
    obs = np.asarray(q_obs, dtype=np.float64)
    half = k_sigma * np.maximum(np.asarray(q_esd, dtype=np.float64), 0.0)
    lo = np.clip(obs - half, q_lo, q_hi)
    hi = np.clip(obs + half, q_lo, q_hi)
    order = np.argsort(lo, kind="stable")
    covered, run_lo, run_hi = 0.0, None, None
    for a, b in zip(lo[order], hi[order]):
        if run_hi is None or a > run_hi:
            if run_hi is not None:
                covered += run_hi - run_lo
            run_lo, run_hi = a, b
        else:
            run_hi = max(run_hi, b)
    if run_hi is not None:
        covered += run_hi - run_lo
    return float(covered / width)


@dataclass(frozen=True)
class SupercellEvidence:
    """What :func:`supercell_chance` measured for one parent and one child.

    The counts are over **lines**, distinct positions, as every count in
    :mod:`~rietx.indexing.extinction` is: two reflections at one 2θ are one
    observation.
    """

    #: how many of the parent's primitive cells one of the child's holds
    index: int
    #: one hkl per extra line, in the child's own setting.  An extra is a line
    #: the child's class allows inside the range, at a position the parent's
    #: lattice predicts nothing.
    extra_hkl: tuple[tuple[int, int, int], ...]
    #: each extra line's Q = 1/d² (Å⁻²), from the child's own metric
    extra_q: tuple[float, ...]
    #: whether each extra line sits inside some observed line's window
    extra_seen: tuple[bool, ...]
    #: the chance rate, :func:`chance_rate` over the same range and windows
    p0: float
    #: one-sided binomial P(X ≥ n_seen) for X ~ B(n_extra, p0): the probability
    #: of seeing at least this many extras had the child's extra lines not
    #: existed.  1.0 when there are no extras.
    p_value: float
    #: whether each extra is seen on an observed line the **parent's** lattice
    #: leaves unexplained, no parent line inside that line's window.  ``None``
    #: means not counted, and then every seen extra counts.
    extra_seen_unexplained: tuple[bool, ...] | None = None
    #: the same binomial over those extras alone, at the same p₀
    p_value_unexplained: float | None = None
    #: how the parent relates to the child: ``"sublattice"`` (the parent is an
    #: index-2-to-4 sublattice, ``index`` set) or ``"containment"`` (every
    #: observed line the parent indexes, the child indexes, and the child's
    #: line set is the denser; ``index`` 0).  C3's ``screen.containment_evidence``
    #: writes the second; :func:`supercell_chance` always the first.
    relation: str = "sublattice"

    @property
    def n_extra(self) -> int:
        return len(self.extra_q)

    @property
    def n_seen(self) -> int:
        return int(sum(self.extra_seen))

    @property
    def n_seen_unexplained(self) -> int:
        if self.extra_seen_unexplained is None:
            return self.n_seen
        return int(sum(self.extra_seen_unexplained))

    @property
    def p_floor(self) -> float:
        """The p-value had **every** extra been seen, p₀ⁿ — the most this test
        could have said for the child on these data."""
        return float(self.p0 ** self.n_extra)

    def verdict(self, alpha: float = SUPERCELL_CHANCE_ALPHA) -> str:
        """``"supported"``, ``"refuted"`` or ``"undecided"``.

        *supported*: the extras seen on lines the parent leaves unexplained are
        more than chance gives at level ``alpha``, so the larger cell is a
        lattice statement the data make.  *refuted*: the extras are seen **no
        more often than chance** — ``n_seen ≤ n_extra · p0``, counting every
        seen one — and the test had the power to say otherwise.  *undecided*:
        everything between, in two forms.  Even every extra seen could not
        have reached ``alpha`` (:attr:`p_floor` ≥ ``alpha``) — no extra in
        range, or too few against a high chance rate — which is not measured,
        so it is not a refutation: a child with no extra line in range is the
        geometrical ambiguity :func:`ambiguity_partners` reports, not a cell
        the data reject.  Or the extras are seen above chance but not
        significantly so (thresholds 1.11, C3): a non-significant test does
        not establish the null (Altman & Bland 1995, *BMJ* **311**, 485).
        Measured reason for the middle band: SRM 676a's own cell as a child of
        its c/2 subcell reads 8 of 18 extras seen at p₀ = 0.21 at the
        resolution (expected 3.7, p = 0.019), which the two-band rule called
        refuted; every wrong cell measured sits at or below n·p₀.

        The two directions count differently, each the conservative way for
        what it moves (WP-1510).  An extra seen on a line the parent already
        explains is evidence of nothing about the larger cell.  So it cannot
        support the child, and it still protects the child from refutation.  A
        child seen beyond chance only through the parent's own lines is
        *undecided*.  That happens on a pseudo-symmetric description, whose
        extras sit beside the parent's lines: two tetragonal descriptions of
        LaB6 read 2 of 3 extras seen over its half-volume rival (p = 0.0072),
        and all 4 seen extras lie on lines the rival explains.  The same p₀
        is the null for both counts, which is conservative for support, since a
        random position lands on an unexplained line no more often than on any.
        """
        p_unexplained = (self.p_value if self.p_value_unexplained is None
                         else self.p_value_unexplained)
        if p_unexplained < alpha:
            return "supported"
        if self.p_floor < alpha and self.n_seen <= self.n_extra * self.p0:
            return "refuted"
        return "undecided"


def _parent_coordinates(parent_cell: tuple[float, ...], parent_centring: str,
                        child_cell: tuple[float, ...], child_centring: str, *,
                        max_index: int = MAX_AMBIGUITY_INDEX,
                        ) -> tuple[np.ndarray, int] | None:
    """``(T, index)``: ``T @ hkl`` is integral exactly when the child's reflection
    ``hkl`` is a point of the parent's reciprocal lattice.

    Both cells go to their **primitive** reduced forms first, so the centring of
    either is consumed before :func:`_derivative_transform` looks for ``H``.
    Asked of the conventional cells, a P description of a centred truth has the
    truth's volume and no ``H`` at all, while it is the index-2 (I) or index-3
    (R) superlattice of the centred lattice.  With ``M`` the child's
    conventional-to-primitive change of basis, a reflection's primitive indices
    are ``M·hkl`` and its parent coordinates ``H⁻¹·M·hkl``, and the test is
    exact integer arithmetic rather than a coincidence in Q.
    """
    try:
        rp = reduce_cell(tuple(parent_cell), parent_centring)
        rc = reduce_cell(tuple(child_cell), child_centring)
    except (ValueError, RuntimeError):
        return None
    h = _derivative_transform(rp.cell, rc.cell, max_index=max_index)
    if h is None:
        return None
    m = _basis_change(rc.change_of_basis)
    t = np.linalg.solve(np.asarray(h, dtype=np.float64), m)
    return t, int(round(abs(float(np.linalg.det(np.asarray(h, dtype=float))))))


def _integral(x: np.ndarray) -> np.ndarray:
    """Rows of ``x`` that are integer vectors, to a tolerance far below one
    index step — ``T`` has denominators of at most 3·4."""
    return np.all(np.abs(x - np.rint(x)) < 1e-6, axis=-1)


def supercell_chance(parent_cell: tuple[float, ...], parent_centring: str,
                     child_cell: tuple[float, ...], child_centring: str,
                     q_obs: np.ndarray, q_esd: np.ndarray, *,
                     child_hkl: np.ndarray | None = None,
                     q_range: tuple[float, float] | None = None,
                     k_sigma: float = MATCH_SIGMA,
                     max_index: int = MAX_AMBIGUITY_INDEX,
                     ) -> SupercellEvidence | None:
    """Are ``child``'s extra lines seen more often than chance would put them?

    ``None`` when ``child`` is not a superlattice of ``parent`` of index 2 to
    ``max_index``, or there is no range to count in.  Otherwise the counts and
    p-value :meth:`SupercellEvidence.verdict` reads.

    **The extras are the ones no extinction can cancel.**  WP-1446 asked this
    question of the child's whole lattice, and it cannot be answered there.  A
    space-group extinction removes a correct cell's lines exactly as an
    oversized cell lacks them.  SRM 676a's own cell is an index-2 superlattice of
    a c/2 subcell the search returns beside it, and ``R -3 c``'s c-glide leaves
    most of its lattice extras absent, so the lattice count reads 9 of 34 seen
    at p₀ = 0.152 (p = 0.062) and would demote the certified cell.  Asking under
    the child's extinction class separates the two, but the screen's class moves
    with the 2θ range on every truth with extinctions measured (WP-1449).  So by
    default only :func:`uncancellable` reflections are counted, the ones no
    space group of the child's lattice can extinguish: 8 of 18 on corundum
    (p = 0.0029), the same count ``R - c -`` gives.  ``child_hkl`` overrides the
    list; the child's lattice reflections reproduce WP-1446's instrument.

    **The count is judged against chance, never against a bar.**  An extra is
    *seen* when it sits inside some observed line's window, ``k_sigma`` × σ(Q),
    and a position no line is at is seen at the rate p₀ :func:`chance_rate`
    measures over the same windows.  A phantom supercell's extras are seen at
    about p₀; a real superstructure's more often.  The one-sided binomial p is
    the chance of at least ``n_seen`` of ``n_extra`` at p₀.  Pass ``q_esd`` as the
    window the search matched with (``engines.match_window``): the question is
    whether a line would have been claimed as indexed.

    **Support asks a narrower count than refutation** (WP-1510).  Each seen
    extra is also asked whether the line it sits on is one the parent explains,
    a line of the parent's lattice in the parent's own metric inside that
    line's window.  The binomial over the extras seen on unexplained lines is
    ``p_value_unexplained``, and :meth:`SupercellEvidence.verdict` reads it for
    *supported*.  An extra seen on a parent line says nothing about the larger
    cell, and on a pseudo-symmetric child that is where the seen extras are.

    **What counts as an extra.**  A counted reflection whose parent coordinates
    are not integral (:func:`_parent_coordinates`), inside ``q_range``
    (default: the observed lines' own span), and farther than the median σ(Q)
    from every line of the parent's lattice — a prediction that close to a
    parent line is the same line as far as these data resolve
    (:func:`_extra_mask`).  The parent's lines are its **lattice**'s: a child
    line where the parent's lattice predicts one says nothing about the larger
    cell.  Reflections the child's centring forbids are dropped rather than
    trusted.

    Measured 2026-09-27 on ten finished acceptance searches (WP-1449's Context
    holds the table): the correct cells tested as a child read p = 0.0029
    (corundum), 0.0072 and 0.0012 (pseudo-tetragonal descriptions of LaB6),
    and every wrong child p ≥ 0.27.  EXPO's WRIP20 is the precedent for
    ordering on what extinctions can explain, scoring each cell under its most
    probable extinction symbol (Altomare, Cuocci, Moliterni & Rizzi (2019),
    *International Tables* Vol. H ch. 3.4, eq. 3.4.5); this asks the question
    before any symbol is known.
    """
    from scipy.stats import binom

    from .fom import LINE_COINCIDENCE_RTOL
    from .qspace import af_from_cell, centring_allows, design_matrix, trial_hkl

    obs = np.asarray(q_obs, dtype=np.float64)
    esd = np.asarray(q_esd, dtype=np.float64)
    # a window per observed line is the contract, as in extras_absent_in_range
    if not len(obs) or len(esd) != len(obs):
        return None
    q_lo, q_hi = ((float(np.min(obs)), float(np.max(obs))) if q_range is None
                  else (float(q_range[0]), float(q_range[1])))
    if not q_hi > q_lo:
        return None
    frame = _parent_coordinates(parent_cell, parent_centring, child_cell,
                                child_centring, max_index=max_index)
    if frame is None:
        return None
    t, index = frame
    af = af_from_cell(tuple(child_cell))
    tol = max(float(np.median(esd)), 1e-12)

    # the parent's lattice lines, enumerated in the child's own metric so a true
    # coincidence is exact: Q(h00) = A·h² and d(100) ≤ a bound every index
    q_edge = q_hi + tol
    n_max = int(np.ceil(max(tuple(child_cell)[:3]) * np.sqrt(q_edge))) + 1
    lattice = trial_hkl(n_max, child_centring)
    q_lattice = design_matrix(lattice) @ af
    parent_line = _integral(lattice @ t.T) & (q_lattice <= q_edge)
    q_parent = q_lattice[parent_line]

    # which observed lines the parent explains: one of its lattice lines, in its
    # **own** metric, inside that line's window.  The child's metric is right
    # for asking whether a reflection is an extra and wrong here, since a
    # pseudo-symmetric child moves the parent's lines off the observed ones.
    # Out to the widest window past the range, so a line near the top is asked
    # against every parent line that could explain it
    q_top = q_hi + k_sigma * float(np.max(esd))
    n_top = int(np.ceil(max(tuple(parent_cell)[:3]) * np.sqrt(q_top))) + 1
    hkl_p = trial_hkl(n_top, parent_centring)
    q_own = design_matrix(hkl_p) @ af_from_cell(tuple(parent_cell))
    explained = _nearest_gap(obs, q_own[q_own <= q_top]) <= k_sigma * esd

    if child_hkl is None:
        hkl, q = lattice, q_lattice
    else:
        hkl = np.asarray(child_hkl, dtype=np.int64).reshape(-1, 3)
        hkl = hkl[~np.all(hkl == 0, axis=1)]
        hkl = hkl[centring_allows(hkl, child_centring)]
        q = design_matrix(hkl) @ af if len(hkl) else np.zeros(0)
    slack = LINE_COINCIDENCE_RTOL
    keep = ((~_integral(hkl @ t.T)) & (q >= q_lo * (1.0 - slack))
            & (q <= q_hi * (1.0 + slack)))
    hkl, q = hkl[keep], q[keep]
    if child_hkl is None and len(hkl):
        # asked of the in-range extras only: the lattice is the whole cube of
        # indices, and the symmetry test is operators × reflections
        free = uncancellable(child_cell, child_centring, hkl)
        hkl, q = hkl[free], q[free]
    if len(q):
        apart = _extra_mask(q, q_parent, tol)
        hkl, q = hkl[apart], q[apart]
    order = np.argsort(q, kind="stable")
    hkl, q = hkl[order], q[order]
    if len(q) > 1:
        distinct = np.ones(len(q), dtype=bool)
        distinct[1:] = np.diff(q) > LINE_COINCIDENCE_RTOL * q[1:]
        hkl, q = hkl[distinct], q[distinct]

    hit = (np.abs(q[:, None] - obs[None, :]) <= k_sigma * esd[None, :]
           if len(q) else np.zeros((0, len(obs)), dtype=bool))
    seen = np.any(hit, axis=1)
    alone = np.any(hit & ~explained[None, :], axis=1)
    p0 = chance_rate(obs, esd, q_lo, q_hi, k_sigma=k_sigma)
    rate = min(max(p0, 0.0), 1.0)
    n = len(q)

    def tail(k: int) -> float:
        return 1.0 if n == 0 else float(binom.sf(k - 1, n, rate))

    return SupercellEvidence(
        index=index,
        extra_hkl=tuple(tuple(int(v) for v in row) for row in hkl),
        extra_q=tuple(float(v) for v in q),
        extra_seen=tuple(bool(v) for v in seen),
        p0=p0, p_value=tail(int(np.count_nonzero(seen))),
        extra_seen_unexplained=tuple(bool(v) for v in alone),
        p_value_unexplained=tail(int(np.count_nonzero(alone))))


__all__ = ["AMBIGUITY_DISCREPANCY_SLACK", "AMBIGUITY_EXTEND_FACTOR",
           "MAX_AMBIGUITY_INDEX",
           "MAX_DISCRIMINATING", "SUPERCELL_CHANCE_ALPHA", "SupercellEvidence",
           "UNCANCELLABLE_METRIC_RTOL", "ambiguity_partners", "chance_rate",
           "derivative_cells", "extras_absent_in_range", "hnf_matrices",
           "lattice_point_group", "reduce_cell", "supercell_chance",
           "transform_cell", "uncancellable"]
