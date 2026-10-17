"""The structure-solution engine's kernels (``rietx-kernels`` 1.4.0, #562)
against the numpy expressions they replace.

The kernels are reached through ``model.compiled``'s three entry points, which
nothing in rietx calls yet.  So each oracle is written here, in numpy, as the
engine computes it:

* the **orbit sums** S_j(h) = Σ_m exp(2πi (Q·x_j + HT)) call ``cos`` and
  ``sin``, numpy's own vectorised routines on one side and the C library's on
  the other, and numpy sums the images pairwise where the kernel runs a loop.
  So the bar is **1e-13 relative**, to the sum's largest possible magnitude
  (the site's image count), since a sum near zero has no relative error of its
  own;
* the **one-site move** F_new = F_old + a_j·(S_j,new − S_j,old) is held to a
  full recompute after a chain of moves, at the same bar on |F|'s bound
  Σ_j |a_j|·m_j;
* the **contact term** is summed term for term as the kernel writes it, so
  every term is the same IEEE operations on the same doubles, and only the
  order of the sum differs: the kernel's runs left to right, numpy's pairwise.
  Every term is non-negative, so the order cannot cancel anything, and the bar
  is the bound on recursive summation of n non-negative terms, **n·ε of the
  total**, n the image pairs the replica visits.  It is a property of the sum,
  never a tolerance on a term; a flat 1e-14 failed on F d -3 m, whose
  replicas visit 2 × 10⁶ pairs and land 4.6e-14 apart.

The data is synthetic: public space groups from gemmi and random coordinates.
"""

from __future__ import annotations

import sys
import types

import gemmi
import numpy as np
import pytest

from rietx._about import COMPILED_ENV
from rietx.model import compiled

rk = pytest.importorskip("rietx_kernels")

HAS_SOLVE = all(callable(getattr(rk, n, None)) for n in compiled.SOLVE_NAMES)
needs_solve = pytest.mark.skipif(
    not HAS_SOLVE,
    reason=f"rietx-kernels {rk.__version__} predates the solve kernels (1.4.0)")

ORBIT_BAR = 1e-13
EPS = np.finfo(np.float64).eps

GROUPS = {
    "P 1 21/c 1": (7.0, 8.0, 9.0, 90.0, 101.0, 90.0),
    "P n m a": (10.2, 6.1, 4.8, 90.0, 90.0, 90.0),
    "I 41/a m d:2": (6.6, 6.6, 6.0, 90.0, 90.0, 90.0),
    "P 63/m m c": (5.5, 5.5, 9.0, 90.0, 90.0, 120.0),
    "F d -3 m:2": (8.4, 8.4, 8.4, 90.0, 90.0, 90.0),
    "P -1": (5.1, 6.3, 7.2, 81.0, 95.0, 103.0),
}


@pytest.fixture(autouse=True)
def _restore_switch():
    was = compiled.set_enabled(None)
    yield
    compiled.set_enabled(was)


# -- synthetic structures ------------------------------------------------------
def _orbits(sg: str, xyz: np.ndarray) -> list:
    """Each site's coset representatives (R, t), one per distinct image."""
    ops = list(gemmi.SpaceGroup(sg).operations())
    out = []
    for x in xyz:
        seen, rs, ts = [], [], []
        for op in ops:
            R = np.array(op.rot, dtype=float) / gemmi.Op.DEN
            t = np.array(op.tran, dtype=float) / gemmi.Op.DEN
            img = (R @ x + t) % 1.0
            if any(np.allclose((img - s + 0.5) % 1.0 - 0.5, 0, atol=1e-9) for s in seen):
                continue
            seen.append(img)
            rs.append(R)
            ts.append(t)
        out.append((np.array(rs), np.array(ts)))
    return out


def _metric(cell) -> np.ndarray:
    a, b, c, *ang = cell
    ca, cb, cg = np.cos(np.radians(ang))
    return np.array([[a * a, a * b * cg, a * c * cb],
                     [a * b * cg, b * b, b * c * ca],
                     [a * c * cb, b * c * ca, c * c]])


class _Case:
    """Frozen orbit tables for one group and a few random sites."""

    def __init__(self, sg: str, n_sites: int = 4, n_refl: int = 150, n_rep: int = 3,
                 seed: int = 0, special: bool = False):
        rng = np.random.default_rng(seed)
        base = rng.uniform(0, 1, (n_sites, 3))
        if special:          # a site on the origin, where most groups shrink its orbit
            base[0] = 0.0
        self.base = base
        self.ops = _orbits(sg, base)
        r = np.arange(-7, 8)
        g = np.stack(np.meshgrid(r, r, r, indexing="ij"), -1).reshape(-1, 3)
        g = g[np.abs(g).sum(1) > 0]
        h = g[rng.choice(len(g), n_refl, replace=False)].astype(np.float64)
        rot = np.concatenate([R for R, _ in self.ops])
        tra = np.concatenate([t for _, t in self.ops])
        counts = np.array([len(R) for R, _ in self.ops], dtype=np.int64)
        self.img_hi = np.cumsum(counts)
        self.img_lo = self.img_hi - counts
        self.Q = np.ascontiguousarray(np.einsum("nk,mkc->nmc", h, rot))
        self.HT = np.ascontiguousarray(h @ tra.T)
        self.xyz = (base[None] + rng.normal(0, 0.05, (n_rep, n_sites, 3))) % 1.0
        # a_j(h): positive, falling with |h|, as occ·f(s)·T(s) does
        s2 = (h * h).sum(1)
        self.amp = np.stack([(4 + j) * np.exp(-0.01 * (1 + j) * s2)
                             for j in range(n_sites)], axis=1)
        self.counts = counts
        self.cell = GROUPS[sg]
        self.rng = rng

    def p1(self, xyz_r: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Every atom of the cell for one replica, and the site each is."""
        pos = [(np.einsum("mij,j->mi", R, xyz_r[j]) + t) % 1.0
               for j, (R, t) in enumerate(self.ops)]
        site = np.concatenate([[j] * len(R) for j, (R, _) in enumerate(self.ops)])
        return np.concatenate(pos), site.astype(np.int64)


# -- the numpy oracles -----------------------------------------------------------
def _orbit_sums_numpy(c: _Case, xyz: np.ndarray, atoms) -> tuple[np.ndarray, np.ndarray]:
    """The engine's numpy expression: (R, len(atoms), N)."""
    n_rep, n = xyz.shape[0], c.Q.shape[0]
    s_re = np.empty((n_rep, len(atoms), n))
    s_im = np.empty_like(s_re)
    for ja, j in enumerate(atoms):
        lo, hi = c.img_lo[j], c.img_hi[j]
        q = c.Q[:, lo:hi, :]
        arg = (q[None, :, :, 0] * xyz[:, j, None, None, 0]
               + q[None, :, :, 1] * xyz[:, j, None, None, 1]
               + q[None, :, :, 2] * xyz[:, j, None, None, 2]
               + c.HT[None, :, lo:hi])
        ph = 2.0 * np.pi * arg
        s_re[:, ja] = np.cos(ph).sum(axis=2)
        s_im[:, ja] = np.sin(ph).sum(axis=2)
    return s_re, s_im


def _clash_numpy(pos, site_of, moved, G, r0, sigma, w_same, reach=1) -> np.ndarray:
    """Term for term as the kernel sums it: the minimum image d − ⌊d + ½⌋,
    the 27 cells around it, the metric form in the kernel's association, and
    an atom against itself in its own cell left out.  ``reach`` > 1 widens the
    cells to (2·reach + 1)³, the sum a thin cell needs and the kernel refuses."""
    span = range(-reach, reach + 1)
    shifts = np.array([(i, j, k) for i in span for j in span for k in span],
                      dtype=np.float64)
    own = len(shifts) // 2
    out = np.zeros(pos.shape[0])
    for r in range(pos.shape[0]):
        e = 0.0
        for a in np.flatnonzero(site_of == moved[r]):
            d = pos[r] - pos[r, a]
            d = d - np.floor(d + 0.5)
            x = d[:, None, :] + shifts[None]
            x0, x1, x2 = x[..., 0], x[..., 1], x[..., 2]
            q = (G[0, 0] * x0 * x0 + G[1, 1] * x1 * x1 + G[2, 2] * x2 * x2
                 + 2.0 * (G[0, 1] * x0 * x1 + G[0, 2] * x0 * x2 + G[1, 2] * x1 * x2))
            dist = np.where(q > 0.0, np.sqrt(np.maximum(q, 0.0)), 0.0)
            rr = r0[site_of[a], site_of][:, None]
            ov = np.where(dist < rr, (rr - dist) / sigma, 0.0)
            ov[a, own] = 0.0
            w = np.where(site_of == moved[r], w_same, 1.0)[:, None]
            e += float(np.sum(w * ov * ov))
        out[r] = e
    return out


def _orbit_err(got, want, counts_of_rows) -> float:
    """Largest difference over each row's bound, its image count."""
    scale = np.asarray(counts_of_rows, dtype=float)[None, :, None]
    return float((np.abs(got - want) / scale).max())


# -- the orbit sums ----------------------------------------------------------------
@needs_solve
@pytest.mark.parametrize("sg", GROUPS)
@pytest.mark.parametrize("special", [False, True])
def test_the_orbit_sums_agree_with_numpy(sg, special):
    c = _Case(sg, special=special, seed=len(sg))
    atoms = np.arange(len(c.ops))
    compiled.set_enabled(True)
    got = compiled.solve_orbit_sums(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi, atoms)
    assert got is not None
    want = _orbit_sums_numpy(c, c.xyz, atoms)
    for g, w in zip(got, want):
        assert g.shape == w.shape
        assert _orbit_err(g, w, c.counts) < ORBIT_BAR


@needs_solve
def test_a_subset_of_sites_lands_on_the_full_call_s_bits():
    """``atoms`` picks and orders the rows, repeats allowed: each output row
    is that site's, computed alone, so its bits cannot depend on the list."""
    c = _Case("P n m a", n_sites=5)
    compiled.set_enabled(True)
    full = compiled.solve_orbit_sums(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi, np.arange(5))
    pick = np.array([3, 0, 3])
    part = compiled.solve_orbit_sums(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi, pick)
    for f, p in zip(full, part):
        assert np.array_equal(p, f[:, pick])


@needs_solve
@pytest.mark.parametrize("sg", ["P 1 21/c 1", "F d -3 m:2"])
def test_the_one_site_sums_are_the_full_sums_row(sg):
    """One site per replica is the same loop over the same images, so it is the
    full call's row for that site to the bit, and numpy's to the bar."""
    c = _Case(sg, n_rep=5)
    which = c.rng.integers(0, len(c.ops), 5)
    compiled.set_enabled(True)
    one = compiled.solve_orbit_sums_one(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi, which)
    full = compiled.solve_orbit_sums(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi,
                                     np.arange(len(c.ops)))
    want = _orbit_sums_numpy(c, c.xyz, np.arange(len(c.ops)))
    for o, f, w in zip(one, full, want):
        rows = np.arange(5)
        assert np.array_equal(o, f[rows, which])
        err = np.abs(o - w[rows, which]) / c.counts[which][:, None]
        assert float(err.max()) < ORBIT_BAR


@needs_solve
def test_a_chain_of_one_site_moves_stays_on_the_full_recompute():
    """F_new = F_old + a_j·(S_j,new − S_j,old), applied 200 times in each of
    four replicas, against F summed afresh from every site's orbit sums."""
    c = _Case("I 41/a m d:2", n_sites=4, n_rep=4)
    compiled.set_enabled(True)
    xyz = c.xyz.copy()
    every = np.arange(len(c.ops))
    s_re, s_im = compiled.solve_orbit_sums(c.Q, c.HT, xyz, c.img_lo, c.img_hi, every)
    f_re = np.einsum("rjn,nj->rn", s_re, c.amp)
    f_im = np.einsum("rjn,nj->rn", s_im, c.amp)
    rows = np.arange(xyz.shape[0])
    for _ in range(200):
        j = c.rng.integers(0, len(c.ops), xyz.shape[0])
        xyz[rows, j] = (xyz[rows, j] + c.rng.normal(0, 0.03, (len(rows), 3))) % 1.0
        n_re, n_im = compiled.solve_orbit_sums_one(c.Q, c.HT, xyz, c.img_lo, c.img_hi, j)
        a = c.amp[:, j].T
        f_re += a * (n_re - s_re[rows, j])
        f_im += a * (n_im - s_im[rows, j])
        s_re[rows, j], s_im[rows, j] = n_re, n_im
    t_re, t_im = compiled.solve_orbit_sums(c.Q, c.HT, xyz, c.img_lo, c.img_hi, every)
    bound = (np.abs(c.amp) * c.counts[None, :]).sum(1)[None, :]
    assert float((np.abs(f_re - np.einsum("rjn,nj->rn", t_re, c.amp)) / bound).max()) < ORBIT_BAR
    assert float((np.abs(f_im - np.einsum("rjn,nj->rn", t_im, c.amp)) / bound).max()) < ORBIT_BAR


# -- the contact term --------------------------------------------------------------
def _clash_case(sg, n_rep=4, seed=0):
    c = _Case(sg, n_sites=4, n_rep=n_rep, seed=seed)
    pos, site_of = zip(*(c.p1(c.xyz[r]) for r in range(n_rep)))
    pos = np.ascontiguousarray(np.array(pos))
    r0 = c.rng.uniform(1.6, 3.0, (len(c.ops), len(c.ops)))
    moved = c.rng.integers(0, len(c.ops), n_rep).astype(np.int64)
    return pos, site_of[0], moved, _metric(c.cell), 0.5 * (r0 + r0.T)


@needs_solve
@pytest.mark.parametrize("sg", GROUPS)
@pytest.mark.parametrize("w_same", [0.5, 1.0])
def test_the_contact_term_agrees_with_numpy(sg, w_same):
    pos, site_of, moved, G, r0 = _clash_case(sg, seed=len(sg))
    compiled.set_enabled(True)
    got = compiled.solve_clash(pos, site_of, moved, G, r0, 0.1, w_same)
    want = _clash_numpy(pos, site_of, moved, G, r0, 0.1, w_same)
    assert (want > 0).any(), "no contact closer than r0, so nothing was compared"
    n_pairs = np.bincount(site_of)[moved] * pos.shape[1] * 27
    assert (np.abs(got - want) <= n_pairs * EPS * want).all()


@needs_solve
def test_an_atom_meets_its_own_images_and_never_itself():
    """One atom in a 2 Å cubic cell with r0 = 2.5 Å: its six face neighbours
    are its own translation images at 2 Å, each (0.5/0.1)² = 25 at weight
    w_same, and the next shell (2.83 Å) is beyond r0.  Counting the atom
    against itself would add (2.5/0.1)² = 625."""
    compiled.set_enabled(True)
    pos = np.full((1, 1, 3), 0.3)
    got = compiled.solve_clash(pos, np.zeros(1, np.int64), np.zeros(1, np.int64),
                               4.0 * np.eye(3), np.full((1, 1), 2.5), 0.1, 0.5)
    assert got is not None and got[0] == pytest.approx(0.5 * 6 * 25.0, rel=1e-14)


def _thin(axis: int, x: float, r0: float = 3.4):
    """One atom in a cell whose ``axis`` is r0/x long, the other two 6 Å, so
    that r0·√(G*_kk) = x on that axis: the 27 cells around a minimum image
    hold every contact closer than r0 exactly while x < 3/2."""
    lengths = [6.0, 6.0, 6.0]
    lengths[axis] = r0 / x
    G = np.diag(np.square(lengths))
    one = np.zeros(1, np.int64)
    return np.full((1, 1, 3), 0.3), one, one, G, np.full((1, 1), r0)


@needs_solve
@pytest.mark.parametrize("axis", [0, 1, 2])
def test_a_thin_cell_past_the_27_cells_is_refused_by_name(axis):
    """r0·√(G*_kk) = 2.125 along one axis: the atom's images two cells away,
    at 3.2 Å, are closer than r0 = 3.4 Å and outside the 27 cells, so the
    sum the kernel would return misses them.  The numpy oracle over 5³ cells
    shows the contacts it would miss; the kernel refuses rather than answer.
    #1016's ``site_clash`` makes the same refusal at the same bound."""
    pos, site_of, moved, G, r0 = _thin(axis, 2.125)
    near = _clash_numpy(pos, site_of, moved, G, r0, 0.1, 0.5)
    full = _clash_numpy(pos, site_of, moved, G, r0, 0.1, 0.5, reach=2)
    assert full[0] > near[0], "the 27 cells miss nothing here, so nothing is tested"
    compiled.set_enabled(True)
    with pytest.raises(ValueError, match="r0 up to 3.4 Å reaches past the 27 cells"):
        compiled.solve_clash(pos, site_of, moved, G, r0, 0.1, 0.5)


@needs_solve
@pytest.mark.parametrize("axis", [0, 1, 2])
def test_a_cell_just_inside_the_bound_is_served_whole(axis):
    """r0·√(G*_kk) = 1.49: the second neighbour along the axis sits at
    2·r0/1.49 > r0, so the 27 cells hold every contact, the kernel answers,
    and its answer is the wider sum's."""
    pos, site_of, moved, G, r0 = _thin(axis, 1.49)
    full = _clash_numpy(pos, site_of, moved, G, r0, 0.1, 0.5, reach=2)
    compiled.set_enabled(True)
    got = compiled.solve_clash(pos, site_of, moved, G, r0, 0.1, 0.5)
    assert full[0] > 0 and got[0] == pytest.approx(full[0], rel=1e-14)


@needs_solve
def test_a_sheared_cell_is_bounded_by_its_plane_spacing_not_its_axis():
    """√(G*_kk) is the inverse plane spacing, which a shear shrinks below
    the axis length: two 2.5 Å axes at γ = 20° have planes 0.86 Å apart, so
    r0 = 2.2 Å reaches 2.6 spacings and is refused, though a test on the
    axis length alone would pass it (2.2/2.5 = 0.88).  The image at
    2·(a − b), 1.74 Å away, lies two cells out on both axes, and the 5³-cell
    oracle shows the 27 cells missing it."""
    a, b, c, gam = 2.5, 2.5, 6.0, np.radians(20.0)
    G = np.array([[a * a, a * b * np.cos(gam), 0.0],
                  [a * b * np.cos(gam), b * b, 0.0],
                  [0.0, 0.0, c * c]])
    one = np.zeros(1, np.int64)
    pos, r0 = np.full((1, 1, 3), 0.3), np.full((1, 1), 2.2)
    near = _clash_numpy(pos, one, one, G, r0, 0.1, 0.5)
    full = _clash_numpy(pos, one, one, G, r0, 0.1, 0.5, reach=2)
    assert full[0] > near[0], "the 27 cells miss nothing here, so nothing is tested"
    compiled.set_enabled(True)
    with pytest.raises(ValueError, match="reaches past the 27 cells"):
        compiled.solve_clash(pos, one, one, G, r0, 0.1, 0.5)


# -- the pool --------------------------------------------------------------------
@needs_solve
def test_a_split_call_lands_on_the_inline_bits(monkeypatch):
    """Reflections and replicas are disjoint rows, so a four-worker split must
    not move a bit; the suite runs one kernel thread a worker and would
    otherwise never split."""
    c = _Case("P 63/m m c", n_rep=6)
    pos, site_of, moved, G, r0 = _clash_case("P 63/m m c", n_rep=6)
    every = np.arange(len(c.ops))
    which = c.rng.integers(0, len(c.ops), 6)
    compiled.set_enabled(True)

    def calls():
        return [*compiled.solve_orbit_sums(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi, every),
                *compiled.solve_orbit_sums_one(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi, which),
                compiled.solve_clash(pos, site_of, moved, G, r0, 0.1, 0.5)]

    monkeypatch.setattr(compiled, "_THREAD_MIN_NS", float("inf"))
    want = calls()
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=4)
    real, submitted = pool.submit, []
    monkeypatch.setattr(pool, "submit", lambda *a: submitted.append(a) or real(*a))
    monkeypatch.setattr(compiled, "_POOL", pool)
    monkeypatch.setattr(compiled, "_POOL_WORKERS", 4)
    monkeypatch.setattr(compiled, "_THREAD_MIN_NS", 0.0)
    try:
        got = calls()
    finally:
        pool.shutdown()
    assert len(submitted) >= 3 * 2, "a call never reached the pool"
    for g, w in zip(got, want):
        assert np.array_equal(g, w)


# -- the refusals ----------------------------------------------------------------
def _i64(*v):
    return np.array(v, dtype=np.int64)


@pytest.fixture
def orbit_call():
    c = _Case("P 1 21/c 1", n_sites=3, n_refl=20, n_rep=2)
    return dict(s_re=np.zeros((2, 3, 20)), s_im=np.zeros((2, 3, 20)), q=c.Q, ht=c.HT,
                xyz=np.ascontiguousarray(c.xyz), img_lo=c.img_lo, img_hi=c.img_hi,
                atoms=_i64(0, 1, 2), lo=0, hi=20)


ORBIT_DEFECTS = {
    "atom past the sites": (lambda c: c.update(atoms=_i64(0, 1, 3)), "atom 3 outside"),
    "negative atom": (lambda c: c.update(atoms=_i64(0, -1, 2)), "atom -1 outside"),
    "image end past the table": (lambda c: c.update(img_hi=_i64(4, 8, 13)),
                                 "image end 13 outside"),
    "images backwards": (lambda c: c.update(img_lo=_i64(0, 8, 8), img_hi=_i64(4, 4, 12)),
                         "run backwards"),
    "img_lo short": (lambda c: c.update(img_lo=_i64(0, 4)), "img_lo has 2"),
    "HT misshapen": (lambda c: c.update(ht=c["ht"][:, :-1].copy()), "HT has shape"),
    "Q not three wide": (lambda c: c.update(q=c["q"][..., :2].copy()), "Q has shape"),
    "xyz not three wide": (lambda c: c.update(xyz=c["xyz"][..., :2].copy()), "xyz has shape"),
    "Fortran-ordered HT": (lambda c: c.update(ht=np.asfortranarray(c["ht"])),
                           "HT must be C-contiguous"),
    "hi past the reflections": (lambda c: c.update(hi=21), "reflection range"),
    "lo past hi": (lambda c: c.update(lo=5, hi=4), "reflection range"),
    "output misshapen": (lambda c: c.update(s_im=np.zeros((2, 3, 21))), "s_im has shape"),
    "outputs share a plane": (lambda c: c.update(s_im=c["s_re"]), "two output planes"),
    "an input inside an output": (lambda c: c.update(
        xyz=c["s_re"].reshape(-1)[:18].reshape(2, 3, 3)), "shares memory with an input"),
    "read-only output": (lambda c: c["s_re"].setflags(write=False), "s_re must be writeable"),
}


@needs_solve
def test_the_well_formed_orbit_call_is_accepted(orbit_call):
    rk.solve_orbit_sums(**orbit_call)
    assert orbit_call["s_re"].any() and orbit_call["s_im"].any()


@needs_solve
@pytest.mark.parametrize("defect", ORBIT_DEFECTS)
def test_one_orbit_defect_is_refused_by_name(orbit_call, defect):
    apply, says = ORBIT_DEFECTS[defect]
    apply(orbit_call)
    with pytest.raises(ValueError, match=says):
        rk.solve_orbit_sums(**orbit_call)


@needs_solve
def test_the_one_site_call_refuses_a_site_or_replica_count_it_cannot_hold(orbit_call):
    c = {k: v for k, v in orbit_call.items() if k != "atoms"}
    c.update(s_re=np.zeros((2, 20)), s_im=np.zeros((2, 20)))
    rk.solve_orbit_sums_one(**c, atom_of_rep=_i64(2, 0))
    with pytest.raises(ValueError, match="atom 3 outside"):
        rk.solve_orbit_sums_one(**c, atom_of_rep=_i64(3, 0))
    with pytest.raises(ValueError, match="atom_of_rep has 3 entries"):
        rk.solve_orbit_sums_one(**c, atom_of_rep=_i64(0, 1, 2))
    with pytest.raises(ValueError, match="s_re has shape"):
        rk.solve_orbit_sums_one(**{**c, "s_re": np.zeros((3, 20))}, atom_of_rep=_i64(2, 0))


@pytest.fixture
def clash_call():
    pos, site_of, moved, G, r0 = _clash_case("P n m a", n_rep=3)
    return dict(out_e=np.zeros(3), pos=pos, site_of=site_of, moved=moved, g=G, r0=r0,
                sigma=0.1, w_same=0.5, lo=0, hi=3)


CLASH_DEFECTS = {
    "site past r0": (lambda c: c["site_of"].__setitem__(0, 4), "site 4 outside"),
    "negative site": (lambda c: c["site_of"].__setitem__(0, -1), "site -1 outside"),
    "moved site past r0": (lambda c: c.update(moved=_i64(0, 4, 1)), "moved site 4 outside"),
    "moved short": (lambda c: c.update(moved=_i64(0, 1)), "moved has 2 entries"),
    "site_of short": (lambda c: c.update(site_of=c["site_of"][:-1].copy()), "site_of has"),
    "r0 not square": (lambda c: c.update(r0=np.ones((4, 3))), "r0 has shape"),
    "g not 3 × 3": (lambda c: c.update(g=np.eye(2)), "g has shape"),
    "g not positive definite": (lambda c: c.update(g=np.diag([25.0, 25.0, -25.0])),
                                "g is not a positive-definite metric"),
    # a metric only half filled, whichever half: the loop reads the upper
    # triangle, the bound's cofactors read both
    "g upper triangle only": (lambda c: c.update(g=np.diag(np.diag(c["g"]))
                                                 + np.triu(np.ones((3, 3)), 1)),
                              "g is not a symmetric metric"),
    "g lower triangle only": (lambda c: c.update(g=np.diag(np.diag(c["g"]))
                                                 + np.tril(np.ones((3, 3)), -1)),
                              "g is not a symmetric metric"),
    "g not finite": (lambda c: c["g"].__setitem__((0, 0), np.nan),
                     "g is not a positive-definite metric"),
    "r0 not finite": (lambda c: c["r0"].__setitem__((0, 0), np.nan), "r0 holds NaN"),
    "zero sigma": (lambda c: c.update(sigma=0.0), "sigma 0"),
    "nan sigma": (lambda c: c.update(sigma=float("nan")), "sigma NaN"),
    "infinite w_same": (lambda c: c.update(w_same=float("inf")), "w_same inf"),
    "hi past the replicas": (lambda c: c.update(hi=4), "replica range"),
    "output misshapen": (lambda c: c.update(out_e=np.zeros(4)), "out has shape"),
    "output inside pos": (lambda c: c.update(out_e=c["pos"].reshape(-1)[:3]),
                          "shares memory with an input"),
}


@needs_solve
def test_the_well_formed_clash_call_is_accepted(clash_call):
    rk.solve_clash(**clash_call)
    assert clash_call["out_e"].any()


@needs_solve
@pytest.mark.parametrize("defect", CLASH_DEFECTS)
def test_one_clash_defect_is_refused_by_name(clash_call, defect):
    apply, says = CLASH_DEFECTS[defect]
    apply(clash_call)
    with pytest.raises(ValueError, match=says):
        rk.solve_clash(**clash_call)


# -- the contract ----------------------------------------------------------------
def _calls():
    c = _Case("P -1", n_sites=2, n_refl=10, n_rep=2)
    pos, site_of, moved, G, r0 = _clash_case("P -1", n_rep=2)
    return [lambda: compiled.solve_orbit_sums(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi,
                                              np.arange(2)),
            lambda: compiled.solve_orbit_sums_one(c.Q, c.HT, c.xyz, c.img_lo, c.img_hi,
                                                  _i64(0, 1)),
            lambda: compiled.solve_clash(pos, site_of, moved, G, r0, 0.1, 0.5)]


def test_the_switch_sends_every_solve_call_to_the_numpy_path(monkeypatch):
    """``RIETX_COMPILED=0`` and ``set_enabled(False)`` both decline all three,
    so the engine's caller runs the numpy expression it carries."""
    monkeypatch.setenv(COMPILED_ENV, "0")
    compiled.set_enabled(None)
    assert not compiled.enabled()
    assert [f() for f in _calls()] == [None, None, None]
    monkeypatch.delenv(COMPILED_ENV)
    compiled.set_enabled(False)
    assert [f() for f in _calls()] == [None, None, None]


def test_a_wheel_without_the_solve_kernels_still_serves_the_rest(monkeypatch):
    """A 1.3 wheel lacks the three, and nothing in rietx calls them yet, so it
    loads whole, the model, figure and indexer kernels run, and only the solve
    entry points decline.  Their caller raises :data:`KERNEL_FLOOR` to 1.4 and
    moves them into :data:`KERNEL_NAMES`."""
    import rietx_kernels as real

    fake = types.ModuleType("rietx_kernels")
    for name in ("__version__", "KERNEL_ABI", *compiled.KERNEL_NAMES):
        setattr(fake, name, getattr(real, name))
    fake.__version__ = "1.3.0"
    monkeypatch.setattr(compiled, "_KERNELS", None)
    monkeypatch.setattr(compiled, "_UNAVAILABLE", None)
    monkeypatch.setitem(sys.modules, "rietx_kernels", fake)
    assert not set(compiled.SOLVE_NAMES) & set(compiled.KERNEL_NAMES)
    assert compiled.available() and compiled.unavailable() is None
    compiled.set_enabled(True)
    assert compiled.dichotomy_kernels() is not None
    assert [f() for f in _calls()] == [None, None, None]


@needs_solve
def test_the_solve_kernels_load_when_the_wheel_has_them():
    compiled.set_enabled(True)
    got = [f() for f in _calls()]
    assert all(g is not None for g in got)
