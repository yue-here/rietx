"""Distinct solutions, under the equivalences of the group (#562 S2a; WP number pending).

Two coordinate sets describe one crystal structure when an isometry that maps
the space group onto itself takes one onto the other: the **Euclidean
normaliser** N(G) (International Tables for Crystallography Vol. A, Hahn ed.,
2005, Part 15).  Its elements are the alternative origins of the group, the
alternative orientations of the axes the metric allows, and, where G has no
inversion of its own, the enantiomorph: x ↦ −x with a shift.  The powder
pattern cannot tell any of these apart (without anomalous scattering, not
even the enantiomorph, by Friedel's law), so a search finds each of them as
often as any other, and clustering by coordinates alone would split one
answer into up to [N(G) : G] "distinct" ones.

**The equivalence set is derived from the group, never listed.**
:func:`equivalences` searches the affine maps (P, p) with P an integer
unimodular matrix of entries in {−1, 0, 1} that is an isometry of this cell
(PᵀGP = G to 1e-6 relative) and p on the 1/24 grid
(:data:`~rietx.crystallography.site_classes.GRID`, gemmi's ``Op.DEN``), and
keeps those that conjugate every operation of G into G modulo the lattice and
its centring: (P, p)(R, t)(P, p)⁻¹ = (PRP⁻¹, P·t + p − PRP⁻¹·p).  The
continuous part, the origin shifts along a polar axis, is
:func:`~rietx.crystallography.wyckoff.floating_origin_basis`, the package's one
authority for it, and is fitted rather than enumerated.  The elements are
reduced modulo G (two that differ by an operation of G are one), so
:attr:`Equivalence.index` is [N(G) : G] on this metric: 8 for P2₁/c and
16 for P2₁2₁2₁ on a general metric, as Part 15 tabulates them (P 1 2/m 1 and
P m m m with halved translations), and 4 for I2₁3 (I a -3 d).  A metric with
extra symmetry (a monoclinic cell with a = c) admits more, and they are found
because they are isometries of this cell.  ``enantiomers=False`` keeps only
det P = +1, for a pattern with anomalous contrast.

**Alignment** (:func:`align`).  For each element n, every atom of one
solution is compared with the nearest image, under every operation of G and
every lattice translation, of every atom of the other's same species after n;
atoms are paired one to one per species by least total squared distance
(Hungarian assignment, :func:`scipy.optimize.linear_sum_assignment`), and on a
polar group the shift along the free directions is the mean displacement,
iterated.  The distance is Cartesian through the metric, the minimum image
taken first and the 27 neighbouring cells searched after it (the order
:mod:`~rietx.solve.chemistry` fixes).  The result is the least RMSD over the
elements, with the largest single deviation beside it.  Pairing by species
rather than by label makes a fragment's own symmetry (acridine's mirror) and
the swap of two same-species sites invisible, as they are to the data.

**Clusters** (:func:`cluster`) are formed greedily in order of J: a solution
joins the first cluster whose leader is within the caller's ``tol`` (Å), or
starts one.  **Ranking** (:func:`rank`) returns the clusters as a list with
their evidence — χ²_data, χ²/χ²_floor, the raw clash term, the seeds that
found each, the spread inside it, the margin to the next — and **no
structure**: a candidate is coordinates and evidence, never a model to refine
from without reading the list.

**No grade, and no threshold of the package's own** (#1224: a machinery
change adds no tier-3 number).  The rules #562's amendments name — a cluster
one seed found, a rival within a margin of the leader's χ²_data, and the
prior-off control arm (amendment (c)) — are verdicts on this evidence, and
they land with their constants beside the solve entry point.  What the
control rule reads is here: given the clustering of the control seeds, run
with every prior at zero weight, each entry carries its RMSD from the
control's best leader and that leader's χ²_data, so a wrong structure that
satisfies its prior perfectly shows as a lower χ²_data somewhere else.

Nothing here is exported from :mod:`rietx`.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..crystallography.site_classes import GRID
from ..crystallography.symmetry import _group_arrays, group_key
from ..crystallography.wyckoff import floating_origin_basis
from ..optimize import lapack

_ISOMETRY_RTOL = 1e-6
_CELLS27 = np.array(list(itertools.product((-1, 0, 1), repeat=3)), dtype=np.float64)


# ----------------------------------------------------------------------
# the normaliser
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Equivalence:
    """The group's equivalences on one cell: its operations, the normaliser's
    coset representatives modulo G, and the continuous origin shifts."""

    rot: np.ndarray          # (|G|, 3, 3) the group's operations (centring included)
    tran: np.ndarray         # (|G|, 3)
    elements: tuple[tuple[np.ndarray, np.ndarray], ...]   # (P, p) per coset of G
    floating: np.ndarray     # (k, 3) continuous origin-shift basis
    g: np.ndarray            # metric

    @property
    def index(self) -> int:
        """[N(G) : G] on this metric (the continuous part not counted)."""
        return len(self.elements)


def _in_lattice(v: np.ndarray, centrings: np.ndarray) -> np.ndarray:
    """Whether each row of v (…, 3) is a lattice vector, centring included."""
    ok = np.zeros(v.shape[:-1], dtype=bool)
    for c in centrings:
        d = v - c
        ok |= np.all(np.abs(d - np.round(d)) < 1e-9, axis=-1)
    return ok


def _centrings(rot: np.ndarray, tran: np.ndarray) -> np.ndarray:
    """The pure translations of the group modulo ℤ³ (the zero vector first)."""
    eye = np.all(np.abs(rot - np.eye(3)) < 1e-12, axis=(1, 2))
    t = np.mod(tran[eye], 1.0)
    t[np.abs(t - 1.0) < 1e-9] = 0.0
    uniq = [np.zeros(3)]
    for v in t:
        if not any(np.allclose(v, w, atol=1e-9) for w in uniq):
            uniq.append(v)
    return np.array(uniq)


def _unimodular() -> np.ndarray:
    vals = np.array(list(itertools.product((-1, 0, 1), repeat=9)),
                    dtype=np.float64).reshape(-1, 3, 3)
    return vals[np.abs(np.round(np.linalg.det(vals))) == 1]


_UNIMODULAR = None


def equivalences(group, g: np.ndarray, *, enantiomers: bool = True) -> Equivalence:
    """The Euclidean normaliser of ``group`` on metric ``g``, modulo the group
    (module docstring)."""
    global _UNIMODULAR
    if _UNIMODULAR is None:
        _UNIMODULAR = _unimodular()
    _ops, rot, tran = _group_arrays(group_key(group))
    rot, tran = np.asarray(rot), np.asarray(tran)
    g = np.asarray(g, dtype=np.float64)
    cen = _centrings(rot, tran)
    floating = np.asarray(floating_origin_basis(group), dtype=np.float64).reshape(-1, 3)
    # isometries of the cell
    cand = _UNIMODULAR
    iso = np.einsum("nji,jk,nkl->nil", cand, g, cand)
    keep = np.all(np.abs(iso - g) <= _ISOMETRY_RTOL * np.abs(g).max(), axis=(1, 2))
    cand = cand[keep]
    if not enantiomers:
        cand = cand[np.round(np.linalg.det(cand)) > 0]
    rkeys = {tuple(np.round(r).astype(int).ravel()) for r in rot}
    by_r: dict[tuple, list[np.ndarray]] = {}
    for r, t in zip(rot, tran, strict=True):
        by_r.setdefault(tuple(np.round(r).astype(int).ravel()), []).append(t)
    # a grid of origin shifts, the floating directions excluded
    free = np.zeros(3, dtype=bool)
    for v in floating:
        nz = np.abs(v) > 0
        if nz.sum() != 1:
            raise NotImplementedError(
                f"the floating origin direction {v.tolist()} is not a cell axis (a "
                "rhombohedral-axes polar group); equivalences() fits shifts along axes only")
        free |= nz
    axes = [np.zeros(1) if free[i] else np.arange(GRID) / GRID for i in range(3)]
    grid = np.array(list(itertools.product(*axes)))
    found: list[tuple[np.ndarray, np.ndarray]] = []
    for p_m in cand:
        p_inv = np.linalg.inv(p_m)
        raw = np.einsum("ij,mjk,kl->mil", p_m, rot, p_inv)
        conj = np.round(raw)
        if (np.abs(raw - conj).max() > 1e-9
                or any(tuple(c.astype(int).ravel()) not in rkeys for c in conj)):
            continue
        live = grid
        for r_c, t in zip(conj, tran, strict=True):
            # (P,p)(R,t)(P,p)⁻¹ has translation P·t + p − R′·p, which must be
            # one of the group's translations for R′, modulo the lattice
            img = (p_m @ t)[None, :] + live - live @ r_c.T
            ok = np.zeros(len(live), dtype=bool)
            for t_g in by_r[tuple(r_c.astype(int).ravel())]:
                ok |= _in_lattice(img - t_g, cen)
            live = live[ok]
            if not len(live):
                break
        for p in live:
            found.append((p_m, p))
    elements = _reduce(found, rot, tran, cen, free)
    return Equivalence(rot=rot, tran=tran, elements=tuple(elements), floating=floating, g=g)


def _reduce(found, rot, tran, cen, free):
    """One element per coset n·G: n₂ ~ n₁ iff n₁⁻¹n₂ = (P₁⁻¹P₂, P₁⁻¹(p₂ − p₁))
    is an operation of G modulo the lattice and the floating shifts (the
    components along the ``free`` axes dropped)."""
    keyed: dict[tuple, list[np.ndarray]] = {}
    for r, t in zip(rot, tran, strict=True):
        keyed.setdefault(tuple(np.round(r).astype(int).ravel()), []).append(t)
    reps: list[tuple[np.ndarray, np.ndarray]] = []
    for p_m, p in found:
        same = False
        for q_m, q in reps:
            q_inv = np.linalg.inv(q_m)
            r = np.round(q_inv @ p_m)
            ts = keyed.get(tuple(r.astype(int).ravel()))
            if ts is None:
                continue
            dt = np.asarray(ts) - (q_inv @ (p - q))[None, :]
            dt[:, free] = 0.0
            if _in_lattice(dt, cen).any():
                same = True
                break
        if not same:
            reps.append((p_m, p))
    return reps


# ----------------------------------------------------------------------
# alignment
# ----------------------------------------------------------------------
def _pair_d2(eq: Equivalence, xa: np.ndarray, xb: np.ndarray):
    """Squared distance (n_a, n_b) from each a to the nearest image of each b,
    and the displacement a − image (n_a, n_b, 3) in fractions."""
    imgs = np.einsum("mij,bj->bmi", eq.rot, xb) + eq.tran            # (n_b, m, 3)
    d = imgs[None] - xa[:, None, None, :]                            # image − a
    d = d - np.floor(d + 0.5)
    dd = d[..., None, :] + _CELLS27                                  # (a, b, m, 27, 3)
    q = np.einsum("...i,ij,...j->...", dd, eq.g, dd)
    flat = q.reshape(q.shape[0], q.shape[1], -1)
    k = np.argmin(flat, axis=2)
    d2 = np.take_along_axis(flat, k[..., None], axis=2)[..., 0]
    vec = dd.reshape(q.shape[0], q.shape[1], -1, 3)
    disp = -np.take_along_axis(vec, k[..., None, None], axis=2)[:, :, 0, :]
    return d2, disp


def _match(eq: Equivalence, xa, xb, species):
    """Per-species one-to-one pairing; (Σd², deviations (n,), mean displacement)."""
    d2, disp = _pair_d2(eq, xa, xb)
    dev = np.zeros(len(xa))
    shift = np.zeros(3)
    for sp in set(species):
        idx = np.flatnonzero(np.asarray(species) == sp)
        rows, cols = linear_sum_assignment(d2[np.ix_(idx, idx)])
        dev[idx[rows]] = np.sqrt(np.maximum(d2[idx[rows], idx[cols]], 0.0))
        shift += disp[idx[rows], idx[cols]].sum(axis=0)
    return float(np.sum(dev * dev)), dev, shift / len(xa)


@dataclass(frozen=True)
class Alignment:
    """The best match of b onto a: RMSD (Å), the largest single deviation,
    and the normaliser element that gave it."""

    rmsd: float
    max_dev: float
    element: int


def align(eq: Equivalence, xa: np.ndarray, xb: np.ndarray, species) -> Alignment:
    """``xb`` aligned onto ``xa`` (both (n, 3), one species list) under every
    equivalence of the group (module docstring)."""
    xa = np.asarray(xa, dtype=np.float64)
    xb = np.asarray(xb, dtype=np.float64)
    best = Alignment(np.inf, np.inf, -1)
    fl = eq.floating
    for k, (p_m, p) in enumerate(eq.elements):
        y = xb @ p_m.T + p
        ss, dev, shift = _match(eq, xa, y, species)
        if len(fl):
            for _ in range(4):
                # the shift along the floating directions only
                coef, *_ = lapack.lstsq(fl.T, shift, rcond=None)
                y = y + fl.T @ coef
                ss, dev, shift = _match(eq, xa, y, species)
        rmsd = float(np.sqrt(ss / len(xa)))
        if rmsd < best.rmsd:
            best = Alignment(rmsd, float(dev.max()), k)
    return best


# ----------------------------------------------------------------------
# clusters and the ranked list
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Solution:
    """One polished state: its coordinates and terms, and which seed found it."""

    xyz: np.ndarray          # (n_atoms, 3)
    j: float
    chi2: float
    clash: float
    seed: int


@dataclass
class Cluster:
    leader: Solution
    members: list[Solution] = field(default_factory=list)
    spread: float = 0.0      # largest member RMSD from the leader, Å

    @property
    def seeds(self) -> tuple[int, ...]:
        return tuple(sorted({m.seed for m in self.members}))


def cluster(solutions, eq: Equivalence, species, *, tol: float) -> list[Cluster]:
    """Greedy clusters in order of J (module docstring); ``tol`` is the RMSD
    (Å) after alignment within which a solution joins a leader."""
    if not tol > 0.0:
        raise ValueError(f"tol {tol} must be a positive RMSD in Å")
    out: list[Cluster] = []
    for s in sorted(solutions, key=lambda s: s.j):
        for c in out:
            a = align(eq, c.leader.xyz, s.xyz, species)
            if a.rmsd <= tol:
                c.members.append(s)
                c.spread = max(c.spread, a.rmsd)
                break
        else:
            out.append(Cluster(leader=s, members=[s]))
    return out


@dataclass(frozen=True)
class RankedSolution:
    """One cluster in the ranked list, with its evidence and no grade.

    No structure: ``xyz`` and ``labels`` are the leader's coordinates, to be
    read beside the rest of the list.  ``control_rmsd_ang`` is this leader's
    RMSD (Å) from the control arm's best leader and ``control_chi2_data``
    that leader's χ²_data, both ``None`` when no control was given."""

    rank: int
    labels: tuple[str, ...]
    species: tuple[str, ...]
    xyz: np.ndarray
    chi2_data: float
    chi2_ratio: float
    clash_raw: float
    j: float
    seeds: tuple[int, ...]
    n_members: int
    spread_ang: float
    margin_to_next: float | None     # (χ²_next − χ²)/χ², None for the last
    control_rmsd_ang: float | None
    control_chi2_data: float | None


def rank(clusters: list[Cluster], *, floor: float, labels, species,
         control: list[Cluster] | None = None,
         eq: Equivalence | None = None) -> list[RankedSolution]:
    """The ranked list, best χ²_data first among the prior-on clusters, with
    their evidence (module docstring).  ``control`` is the clustering of the
    prior-off seeds; ``eq`` is needed to compare each leader with its best."""
    cl = sorted(clusters, key=lambda c: c.leader.chi2)
    c0 = None
    if control:
        if eq is None:
            raise ValueError("comparing the control arm needs the equivalence set")
        c0 = min(control, key=lambda c: c.leader.chi2).leader
    out = []
    for i, c in enumerate(cl):
        s = c.leader
        nxt = cl[i + 1].leader.chi2 if i + 1 < len(cl) else None
        margin = None if nxt is None else (nxt - s.chi2) / s.chi2
        out.append(RankedSolution(
            rank=i + 1, labels=tuple(labels), species=tuple(species), xyz=s.xyz.copy(),
            chi2_data=s.chi2, chi2_ratio=s.chi2 / floor, clash_raw=s.clash, j=s.j,
            seeds=c.seeds, n_members=len(c.members), spread_ang=c.spread,
            margin_to_next=margin,
            control_rmsd_ang=None if c0 is None else align(eq, s.xyz, c0.xyz, species).rmsd,
            control_chi2_data=None if c0 is None else c0.chi2))
    return out


__all__ = ["Alignment", "Cluster", "Equivalence", "RankedSolution", "Solution", "align",
           "cluster", "equivalences", "rank"]
