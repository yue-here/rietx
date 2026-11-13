"""WP-1418 M-8, K1a: the k-grid, its scores, the null and the equivalents.

Every arm below can fail, and each negative control has a positive arm beside it
(issue #795's verification table, V1-V8).  Synthetic Pnma (5.74 × 7.70 × 5.54 Å,
LaMnO₃-like), CW neutrons at λ 2.41 Å over 10-140°, a 0.12° match radius and a
±5° band unless a test says otherwise: those are the caller's explicit arguments
here, since the module has no defaults for them.  Satellite positions come from
the package's own exact generator.

Interpretation, written before the runs:

* V1 enumeration: every point of the (1/n)³ cube (over one cell of e·Z³ ⊂ L*)
  maps through ``star``/``canonical_kvector`` to exactly one representative, and
  the per-stratum orders agree with ``little_group``.  Fails if the reduction
  forgets the centring (F m m m) or −k (P 2₁ 2₁ 2₁): those two private switches
  must make the same check fail.
* V2 arithmetic: P(X ≥ n) equals the brute-force sum over all 2^N outcomes to
  1e-12; a p perturbed by 1e-3 must not.  The hand case p = 2r/2b holds exactly.
* V3 invariance: a k and every structural equivalent score identically; a
  non-equivalent k with the same matched count does not.
* V4 planted k against the null: all ten planted satellites matched and the
  score above the null's 99th percentile on the 1/64 grid; without satellites,
  the misfit-only lists stay under it about as often as chance allows.
* V6 partner: x ↔ z on a pseudo-tetragonal cell is listed with the code; a
  clearly orthorhombic cell lists nothing and emits nothing.
* V7 budget: a cut names exactly the strata left; no budget leaves none.
* V8 no decision inside: no ``k``/``best``/``top`` on a grid record, and the
  extent arguments have no defaults.
"""

from __future__ import annotations

import inspect
import itertools
from fractions import Fraction as F

import numpy as np
import pytest

from rietx.crystallography.representation.irreps import (
    canonical_kvector,
    equivalent_kvectors,
    little_group,
    star,
)
from rietx.crystallography.satellites import (
    lattice_two_theta,
    reciprocal_lattice_mask,
    satellite_d_spacings,
)
from rietx.crystallography.symmetry import get_spacegroup
from rietx.indexing.ambiguity import chance_rate
from rietx.indexing.engines import Budget
from rietx.indexing.kvector import (
    KGridPositions,
    KGridScores,
    KNull,
    KParent,
    KPeaks,
    _kgrid_strata,
    _poisson_binomial_tail,
    _structural_class,
    kgrid_null,
    kgrid_positions,
    kgrid_strata,
    kvector_equivalents,
    score_kgrid,
    score_kvector,
)

CELL = (5.74, 7.70, 5.54, 90.0, 90.0, 90.0)
LAMBDA = 2.41
RADIUS = 0.12
BAND = 5.0
PNMA = KParent("P n m a", CELL, LAMBDA, 10.0, 140.0)
K_LINE = (F(0), F(18, 64), F(0))            # 0.28125, the grid point nearest 0.28
K_GENERAL = (F(11, 64), F(0), F(20, 64))    # (0.172, 0, 0.3125), near (0.17, 0, 0.31)


def _two_theta(d):
    return np.degrees(2.0 * np.arcsin(LAMBDA / (2.0 * np.asarray(d))))


def _sat(parent, k):
    """Satellite 2θ of k through the public generator, in range, distinct."""
    d = satellite_d_spacings(parent.space_group, parent.cell, parent.wavelength,
                             parent.two_theta_max, [k], parent.two_theta_min)[0]
    tt = np.unique(_two_theta(d))
    return tt[(tt >= parent.two_theta_min) & (tt <= parent.two_theta_max)]


def _nuclear(parent):
    return lattice_two_theta(parent.group, parent.cell, parent.wavelength,
                             parent.two_theta_max, parent.two_theta_min)


def _planted(parent, k, n, seed, *, sigma=0.02, spurious=0):
    """The n lowest-angle satellites of k off the nuclear windows, with noise."""
    rng = np.random.default_rng(seed)
    nuc = _nuclear(parent)
    pos = _sat(parent, k)
    off = pos[np.min(np.abs(pos[:, None] - nuc[None, :]), axis=1) > RADIUS][:n]
    obs = off + rng.normal(0.0, sigma, len(off))
    if spurious:
        obs = np.concatenate([obs, rng.uniform(parent.two_theta_min, parent.two_theta_max,
                                               spurious)])
    return np.sort(np.clip(obs, parent.two_theta_min, parent.two_theta_max))


def _exclude(parent):
    return [(x, RADIUS) for x in _nuclear(parent)]


# ============================================================ V1 enumeration

def _cube(sg, n):
    """Every k = j/n over one cell of e·Z³ ⊂ L*, k ≡ 0 excluded."""
    e = next(e for e in range(1, 7)
             if reciprocal_lattice_mask(sg, e * np.eye(3, dtype=np.int64)).all())
    for j in itertools.product(range(n * e), repeat=3):
        k = tuple(F(x, n) for x in j)
        if not equivalent_kvectors(sg, k, (0, 0, 0)):
            yield k


def _brute_force_problems(sg, n, strata):
    """Every way the strata fail to partition the cube into classes."""
    problems = []
    owner = {}
    for st in strata:
        for r in st.kvectors:
            for arm in set(star(sg, r)) | set(star(sg, tuple(-c for c in r))):
                c = canonical_kvector(sg, arm)
                held = owner.setdefault(c, r)
                if held != r:
                    problems.append(f"{held} and {r} are one class (both reach {c})")
    by_kind_cube: dict[tuple[int, int], set] = {}
    for k in _cube(sg, n):
        c = canonical_kvector(sg, k)
        if c not in owner:
            problems.append(f"{k} maps to no representative")
            continue
        lg = little_group(sg, k)
        rots = np.array([np.asarray(r).T - np.eye(3) for r in lg.rotations]).reshape(-1, 3)
        n_free = 3 - int(np.linalg.matrix_rank(rots))
        by_kind_cube.setdefault((lg.order, n_free), set()).add(owner[c])
    by_kind_strata: dict[tuple[int, int], int] = {}
    for st in strata:
        key = (st.little_group_order, st.n_free)
        by_kind_strata[key] = by_kind_strata.get(key, 0) + st.n_points
    counted = {key: len(v) for key, v in by_kind_cube.items()}
    if counted != by_kind_strata:
        problems.append(f"per-stratum counts {by_kind_strata} against the cube's {counted}")
    return problems


@pytest.mark.parametrize("symbol,n", [
    ("P n m a", 4), ("P n m a", 6), ("P n m a", 8),
    ("I 4/m m m", 4), ("I 4/m m m", 6), ("I 4/m m m", 8),
    ("F m m m", 4), ("F m m m", 6), ("F m m m", 8),
    ("P 21 21 21", 6), ("R -3 m", 6), ("F m -3 m", 4), ("P 6/m m m", 6), ("C 1 2/m 1", 4),
])
def test_every_cube_point_maps_to_exactly_one_representative(symbol, n):
    sg = get_spacegroup(symbol)
    strata = kgrid_strata(symbol, denominator=n)
    assert _brute_force_problems(sg, n, strata) == []


@pytest.mark.parametrize("symbol,n", [("P n m a", 6), ("I 4/m m m", 4), ("F m m m", 4)])
def test_each_stratum_order_is_the_little_groups_at_every_member(symbol, n):
    sg = get_spacegroup(symbol)
    for st in kgrid_strata(symbol, denominator=n):
        for k in st.kvectors:
            lg = little_group(sg, k)
            assert lg.order == st.little_group_order, (st, k)
            assert lg.indices == st.operation_indices, (st, k)
        # the locus is what P_k fixes: a fixed component never moves
        for c, fixed in enumerate(st.fixed_components):
            if fixed and st.n_points > 1:
                assert len({k[c] for k in st.kvectors}) <= 2 * n


def test_dropping_the_centring_fails_the_brute_force_check():
    """Negative control: reduce modulo Z³ instead of the F lattice's L*."""
    sg = get_spacegroup("F m m m")
    problems = _brute_force_problems(sg, 4, _kgrid_strata(sg.xhm(), 4, centred=False))
    assert problems, "the check cannot see a reduction that ignores the centring"
    assert any("maps to no representative" in p for p in problems), problems[:3]


def test_dropping_minus_k_fails_the_brute_force_check():
    """Negative control: P 2₁ 2₁ 2₁ has no inversion, so +Rᵀ alone splits k from −k."""
    sg = get_spacegroup("P 21 21 21")
    problems = _brute_force_problems(sg, 6, _kgrid_strata(sg.xhm(), 6, minus_k=False))
    assert problems, "the check cannot see a reduction that ignores −k"
    assert any("are one class" in p for p in problems), problems[:3]


def test_fmmm_x_points_are_three_stars_and_100_is_011():
    """#1071's known answer: (1,0,0) ≡ (0,1,1) on F, and the three X points differ."""
    sg = get_spacegroup("F m m m")
    assert equivalent_kvectors(sg, (1, 0, 0), (0, 1, 1))
    strata = kgrid_strata("F m m m", denominator=2)
    reps = [k for st in strata for k in st.kvectors]
    xs = [(F(1), F(0), F(0)), (F(0), F(1), F(0)), (F(0), F(0), F(1))]
    assert all(x in reps for x in xs)
    assert len({frozenset(star(sg, x)) for x in xs}) == 3
    assert (F(0), F(1), F(1)) not in reps


def test_the_pnma_grid_at_1_64_holds_33_cubed_minus_gamma():
    """The brief's cost line counts 33³ = 35 937 points on [0, ½]³; Γ is not a k."""
    strata = kgrid_strata("P n m a", denominator=64)
    assert sum(st.n_points for st in strata) == 33 ** 3 - 1
    reps = [k for st in strata for k in st.kvectors]
    assert all(F(0) <= c <= F(1, 2) for k in reps for c in k)
    assert [st.kind for st in strata] == ["point"] + ["line"] * 3 + ["plane"] * 3 + ["general"]


def test_the_denominator_is_required_and_bounded():
    with pytest.raises(TypeError):
        kgrid_strata("P n m a")  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="K_MAX_DENOMINATOR"):
        kgrid_strata("P n m a", denominator=65)


# ======================================================== V2 the arithmetic

def _brute_tail(p, n):
    total = 0.0
    for bits in itertools.product((0, 1), repeat=len(p)):
        if sum(bits) >= n:
            total += float(np.prod([pi if b else 1.0 - pi for pi, b in zip(p, bits)]))
    return total


def test_the_poisson_binomial_tail_is_exact():
    rng = np.random.default_rng(3)
    for big_n in range(1, 13):
        p = rng.uniform(0.0, 0.9, size=big_n)
        for n in range(big_n + 1):
            got = float(_poisson_binomial_tail(p[None, :], np.array([n]))[0])
            want = _brute_tail(p, n)
            assert got == pytest.approx(want, rel=1e-12, abs=0.0), (big_n, n)
    # negative control: one p off by 1e-3 is seen at this precision
    p = rng.uniform(0.05, 0.9, size=8)
    wrong = p.copy()
    wrong[3] += 1e-3
    got = float(_poisson_binomial_tail(wrong[None, :], np.array([5]))[0])
    assert abs(got - _brute_tail(p, 5)) > 1e-12 * _brute_tail(p, 5)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_a_scores_p_value_is_the_tail_of_its_own_p(seed):
    pk = _planted(PNMA, K_GENERAL, 6, seed, spurious=3)
    s = score_kvector(pk, PNMA, K_LINE, radius=RADIUS, band_deg=BAND)
    assert s.n_peaks == len(pk)
    assert s.p_value == pytest.approx(_brute_tail(s.p, s.n_matched), rel=1e-12)
    assert s.score == pytest.approx(-np.log10(s.p_value), rel=1e-14)


def test_every_p_is_chance_rates_covered_measure_in_its_band():
    pk = _planted(PNMA, K_GENERAL, 10, 4, spurious=4)
    s = score_kvector(pk, PNMA, K_GENERAL, radius=RADIUS, band_deg=BAND)
    sat = _sat(PNMA, K_GENERAL)
    for i, x in enumerate(pk):
        lo, hi = max(10.0, x - BAND), min(140.0, x + BAND)
        want = chance_rate(sat, np.full(len(sat), RADIUS), lo, hi, k_sigma=1.0)
        assert s.p[i] == pytest.approx(want, abs=1e-12)
        near = np.min(np.abs(sat - x))
        assert (i in s.matched) == (near <= RADIUS)
        assert abs(s.offsets_deg[i]) == pytest.approx(near, abs=1e-12)


def test_one_window_inside_its_band_has_p_two_r_over_two_b():
    band = 0.5
    sat = _sat(PNMA, K_LINE)
    gaps = np.diff(sat)
    i = next(i for i in range(1, len(sat) - 1)
             if gaps[i - 1] > band + RADIUS and gaps[i] > band + RADIUS
             and sat[i] - band > 10.0)
    s = score_kvector([sat[i]], PNMA, K_LINE, radius=RADIUS, band_deg=band)
    assert s.p[0] == pytest.approx(2 * RADIUS / (2 * band), abs=1e-12)
    assert s.matched == (0,)


def test_harmonics_two_is_the_first_order_score_of_2k():
    pk = _planted(PNMA, K_GENERAL, 8, 5, spurious=2)
    two = tuple(2 * c for c in K_GENERAL)
    a = score_kvector(pk, PNMA, K_GENERAL, radius=RADIUS, band_deg=BAND, harmonics=(2,))
    b = score_kvector(pk, PNMA, two, radius=RADIUS, band_deg=BAND)
    assert a.p == pytest.approx(b.p, abs=1e-12)
    assert a.n_matched == b.n_matched
    both = score_kvector(pk, PNMA, K_GENERAL, radius=RADIUS, band_deg=BAND, harmonics=(1, 2))
    assert both.n_positions >= max(a.n_positions, b.n_positions)
    assert all(x >= y - 1e-12 for x, y in zip(both.p, a.p))


def test_widths_and_tags_ride_along_and_change_nothing():
    pk = _planted(PNMA, K_LINE, 6, 6)
    bare = score_kvector(pk, PNMA, K_LINE, radius=RADIUS, band_deg=BAND)
    dressed = score_kvector(KPeaks(two_theta=tuple(pk), fwhm=(0.3,) * len(pk),
                                   tags=("persists_above",) * len(pk)),
                            PNMA, K_LINE, radius=RADIUS, band_deg=BAND)
    assert dressed.p == bare.p and dressed.score == bare.score
    assert dressed.peaks.fwhm == (0.3,) * len(pk)


def test_bad_inputs_are_refused():
    with pytest.raises(ValueError, match="outside"):
        score_kvector([5.0], PNMA, K_LINE, radius=RADIUS, band_deg=BAND)
    with pytest.raises(ValueError, match="k = 0"):
        score_kvector([30.0], PNMA, (1, 0, 0), radius=RADIUS, band_deg=BAND)
    with pytest.raises(ValueError, match="harmonics"):
        score_kvector([30.0], PNMA, K_LINE, radius=RADIUS, band_deg=BAND, harmonics=(0,))


# ========================================================== V3 invariance

def test_every_structural_equivalent_scores_identically():
    pk = _planted(PNMA, K_GENERAL, 10, 7, spurious=2)
    ref = score_kvector(pk, PNMA, K_GENERAL, radius=RADIUS, band_deg=BAND)
    eq = kvector_equivalents(PNMA, K_GENERAL, tol=0.01)
    spellings = [r.k for r in eq.rows if r.relation != "partner"]
    spellings.append(tuple(c + d for c, d in zip(K_GENERAL, (1, -2, 3))))  # k + G
    spellings.append(tuple(1 - c for c in K_GENERAL))                       # G − k
    assert len(spellings) >= 6
    for k in spellings:
        s = score_kvector(pk, PNMA, k, radius=RADIUS, band_deg=BAND)
        assert s.p == pytest.approx(ref.p, abs=1e-12), k
        assert s.score == pytest.approx(ref.score, rel=1e-12), k


def test_a_centred_equivalent_scores_identically():
    fmmm = KParent("F m m m", (5.6, 6.1, 7.3, 90, 90, 90), LAMBDA, 10.0, 140.0)
    pk = _planted(fmmm, (F(1), F(0), F(0)), 6, 8, spurious=2)
    a = score_kvector(pk, fmmm, (1, 0, 0), radius=RADIUS, band_deg=BAND)
    b = score_kvector(pk, fmmm, (0, 1, 1), radius=RADIUS, band_deg=BAND)
    c = score_kvector(pk, fmmm, (0, 1, 0), radius=RADIUS, band_deg=BAND)
    assert a.p == b.p and a.score == b.score
    assert a.p != c.p  # another X point is another star


def test_a_non_equivalent_k_with_the_same_count_scores_differently():
    """The score is not a function of the count: two classes matching as many
    peaks differ in coverage, so in score.  Random off-nuclear peaks, where
    counts saturate, give many such pairs."""
    rng = np.random.default_rng(9)
    nuc = _nuclear(PNMA)
    x = rng.uniform(10.0, 140.0, 400)
    pk = np.sort(x[np.min(np.abs(x[:, None] - nuc[None, :]), axis=1) > RADIUS][:8])
    grid = score_kgrid(pk, PNMA, kgrid_strata("P n m a", denominator=16),
                       radius=RADIUS, band_deg=BAND)
    top = int(grid.n_matched.max())
    rivals = [r for r in grid.rows if r.n_matched == top]
    assert len(rivals) >= 2, "no two classes share a count: the control is empty"
    a, b = rivals[0], rivals[1]
    assert not equivalent_kvectors(PNMA.group, a.k, b.k)
    sa = score_kvector(pk, PNMA, a.k, radius=RADIUS, band_deg=BAND)
    sb = score_kvector(pk, PNMA, b.k, radius=RADIUS, band_deg=BAND)
    assert sa.p != sb.p
    assert len({round(r.score, 9) for r in rivals}) > 1


# ================================================ the grid: rows, order, budget

def test_each_grid_row_is_score_kvector_of_its_k():
    pk = _planted(PNMA, K_GENERAL, 8, 10, spurious=2)
    strata = kgrid_strata("P n m a", denominator=8)
    grid = score_kgrid(pk, PNMA, strata, radius=RADIUS, band_deg=BAND)
    assert [r.k for r in grid.rows] == [k for st in strata for k in st.kvectors]
    for r in grid.rows[::7]:
        s = score_kvector(pk, PNMA, r.k, radius=RADIUS, band_deg=BAND)
        assert r.score == pytest.approx(s.score, rel=1e-12, abs=1e-12)
        assert r.matched == s.matched and r.n_positions == s.n_positions
        assert canonical_kvector(PNMA.group, r.k) in r.equivalents


def test_rows_keep_the_callers_order_whatever_the_peaks():
    strata = kgrid_strata("P n m a", denominator=8)
    reordered = tuple(reversed(strata))
    a = score_kgrid(_planted(PNMA, K_LINE, 8, 11), PNMA, reordered, radius=RADIUS, band_deg=BAND)
    b = score_kgrid(_planted(PNMA, K_GENERAL, 9, 12), PNMA, reordered, radius=RADIUS, band_deg=BAND)
    assert [r.k for r in a.rows] == [r.k for r in b.rows]
    assert a.strata_searched == tuple(s.name for s in reordered)
    # never sorted by score
    assert not np.all(np.diff(a.scores) <= 0)


class _FlipAfter:
    """A cancel token that turns true on its (n+1)-th reading."""

    def __init__(self, n):
        self.n = n

    def __bool__(self):
        self.n -= 1
        return self.n < 0


def test_a_cut_budget_names_exactly_the_strata_left():
    strata = kgrid_strata("P n m a", denominator=8)
    names = tuple(s.name for s in strata)
    pk = _planted(PNMA, K_LINE, 6, 13)
    cut = score_kgrid(pk, PNMA, strata, radius=RADIUS, band_deg=BAND,
                      budget=Budget(3600.0, cancel=_FlipAfter(3)))
    assert cut.strata_searched == names[:3]
    assert cut.strata_left == names[3:]
    assert cut.budget_expired and cut.budget_seconds == 3600.0
    assert {r.stratum for r in cut.rows} == set(names[:3])
    full = score_kgrid(pk, PNMA, strata, radius=RADIUS, band_deg=BAND)
    assert full.strata_left == () and not full.budget_expired
    assert full.strata_searched == names
    null = kgrid_null(pk, PNMA, strata, radius=RADIUS, band_deg=BAND,
                      exclude=_exclude(PNMA), n_shuffles=3, percentile=99, seed=1,
                      budget=Budget(3600.0, cancel=_FlipAfter(2)))
    assert null.strata_left == names[2:] and null.strata_searched == names[:2]


def test_positions_built_once_give_the_same_rows():
    strata = kgrid_strata("P n m a", denominator=8)
    pk = _planted(PNMA, K_LINE, 7, 14)
    built = kgrid_positions(PNMA, strata)
    a = score_kgrid(pk, PNMA, strata, radius=RADIUS, band_deg=BAND)
    b = score_kgrid(pk, PNMA, built, radius=RADIUS, band_deg=BAND)
    assert [(r.k, r.score) for r in a.rows] == [(r.k, r.score) for r in b.rows]
    with pytest.raises(ValueError, match="harmonics"):
        score_kgrid(pk, PNMA, built, radius=RADIUS, band_deg=BAND, harmonics=(2,))


# ================================================================ the null

def test_the_null_is_reproducible_and_avoids_the_exclusion_windows():
    strata = kgrid_strata("P n m a", denominator=8)
    pk = _planted(PNMA, K_LINE, 8, 15)
    exclude = _exclude(PNMA)
    kw = dict(radius=RADIUS, band_deg=BAND, exclude=exclude, n_shuffles=12, percentile=99)
    a = kgrid_null(pk, PNMA, strata, seed=5, **kw)
    b = kgrid_null(pk, PNMA, strata, seed=5, **kw)
    c = kgrid_null(pk, PNMA, strata, seed=6, **kw)
    assert a.sample == b.sample and a.shuffles == b.shuffles
    assert a.sample != c.sample
    centres = np.array([x for x, _ in exclude])
    for row in a.shuffles:
        assert len(row) == len(pk)
        assert np.all(np.min(np.abs(np.asarray(row)[:, None] - centres[None, :]), axis=1)
                      >= RADIUS)
    assert a.threshold == pytest.approx(np.percentile(a.sample, 99))
    # each sample member is the grid maximum of its own shuffle
    g = score_kgrid(a.shuffles[0], PNMA, strata, radius=RADIUS, band_deg=BAND)
    assert a.sample[0] == pytest.approx(g.scores.max(), rel=1e-12)
    assert a.max_matched[0] == g.n_matched.max()


def test_the_null_needs_its_arguments():
    strata = kgrid_strata("P n m a", denominator=4)
    with pytest.raises(TypeError):
        kgrid_null([30.0], PNMA, strata, radius=RADIUS, band_deg=BAND,  # type: ignore[call-arg]
                   n_shuffles=10, percentile=99, seed=1)
    with pytest.raises(ValueError, match="whole"):
        kgrid_null([30.0], PNMA, strata, radius=RADIUS, band_deg=BAND,
                   exclude=[(75.0, 70.0)], n_shuffles=10, percentile=99, seed=1)


# ============================== the maintainer's condition (#795, 2026-11-11)

def test_grid_records_carry_their_step_strata_and_no_off_grid_claim():
    """Every grid-level record states its step, its strata, and no claim off the grid."""
    strata = kgrid_strata("P n m a", denominator=64)[:4]   # points and lines: cheap
    names = tuple(s.name for s in strata)
    pk = _planted(PNMA, K_LINE, 6, 16)
    grid = score_kgrid(pk, PNMA, strata, radius=RADIUS, band_deg=BAND)
    null = kgrid_null(pk, PNMA, strata, radius=RADIUS, band_deg=BAND,
                      exclude=_exclude(PNMA), n_shuffles=4, percentile=99, seed=2)
    for rec in (grid, null):
        assert rec.grid_step == 1 / 64
        assert set(rec.denominators) == {64}
        assert rec.strata_searched == names and rec.strata_left == ()
        assert "1/64" in rec.coverage and "No claim is made about any k off this grid" in rec.coverage
        assert "off the grid" in type(rec).__doc__
    cut = score_kgrid(pk, PNMA, strata, radius=RADIUS, band_deg=BAND,
                      budget=Budget(3600.0, cancel=_FlipAfter(1)))
    assert cut.strata_left == names[1:] and "3 stratum(s) left unsearched" in cut.coverage
    for st in strata:
        assert st.grid_step == 1 / 64 and st.denominator == 64


# ============================================ V8 no decision inside the records

def test_no_record_picks_a_row_and_no_extent_has_a_default():
    for cls in (KGridScores, KNull, KGridPositions):
        names = set(dir(cls)) | {f for f in getattr(cls, "__dataclass_fields__", {})}
        assert not names & {"k", "best", "top", "best_or_none", "row"}, cls
        for name, member in inspect.getmembers(cls, inspect.isfunction):
            if not name.startswith("_"):
                pytest.fail(f"{cls.__name__}.{name} is a method a row could come from")
    with pytest.raises(TypeError):
        score_kgrid([30.0], PNMA, kgrid_strata("P n m a", denominator=4),  # type: ignore[call-arg]
                    band_deg=BAND)
    for fn, required in ((kgrid_strata, {"denominator"}),
                         (score_kvector, {"radius", "band_deg"}),
                         (score_kgrid, {"radius", "band_deg"}),
                         (kgrid_null, {"radius", "band_deg", "exclude", "n_shuffles",
                                       "percentile", "seed"}),
                         (kvector_equivalents, {"tol"})):
        params = inspect.signature(fn).parameters
        for name in required:
            assert params[name].default is inspect.Parameter.empty, (fn.__name__, name)
        defaulted = {n for n, p in params.items() if p.default is not inspect.Parameter.empty}
        assert defaulted <= {"harmonics", "budget"}, (fn.__name__, defaulted)


# ===================================================== V6 the metric partner

def test_the_pseudo_tetragonal_partner_is_listed_with_its_code():
    """a = 5.74, c = 5.54 Å: x ↔ z maps k onto a vector no symmetry relates to it."""
    k = (F(15, 64), F(7, 64), F(24, 64))
    eq = kvector_equivalents(PNMA, k, tol=0.08)
    partners = [r for r in eq.rows if r.relation == "partner"]
    swapped = canonical_kvector(PNMA.group, (k[2], k[1], k[0]))
    row = next(r for r in partners if swapped in _structural_class(PNMA.space_group, r.k))
    # one row per class of images, never one per arm of the partner's star
    classes = [_structural_class(PNMA.space_group, r.k) for r in partners]
    assert len(set(classes)) == len(classes)
    assert [d.code for d in eq.diagnostics] == ["K_SEARCH_PARTNER"] * len(partners)
    assert all(d.level == "info" for d in eq.diagnostics)
    assert row.metric_deviation == pytest.approx((5.74**2 - 5.54**2) / 5.54**2, rel=1e-6)
    image = tuple(sum(row.operation[i][j] * k[j] for j in range(3)) for i in range(3))
    assert canonical_kvector(PNMA.group, image) == row.k
    text = " ".join(d.message + (d.suggestion or "") for d in eq.diagnostics).lower()
    assert "right" not in text and "correct" not in text and "better" not in text


def test_a_clearly_orthorhombic_cell_has_no_partner_and_no_code():
    ortho = KParent("P n m a", (5.74, 7.70, 6.40, 90, 90, 90), LAMBDA, 10.0, 140.0)
    eq = kvector_equivalents(ortho, (F(15, 64), F(7, 64), F(24, 64)), tol=0.08)
    assert [r.relation for r in eq.rows if r.relation == "partner"] == []
    assert eq.diagnostics == ()
    # the structural rows are there either way: k and the seven other arms of its mmm star
    assert len([r for r in eq.rows if r.relation in ("k", "star")]) == 8


def test_minus_k_rows_appear_only_without_inversion():
    k = (F(1, 8), F(1, 4), F(3, 8))
    p212121 = KParent("P 21 21 21", CELL, LAMBDA, 10.0, 140.0)
    with_inv = kvector_equivalents(PNMA, k, tol=0.01)
    without = kvector_equivalents(p212121, k, tol=0.01)
    assert not [r for r in with_inv.rows if r.relation == "-k"]
    assert len([r for r in without.rows if r.relation == "-k"]) == 4
    assert not with_inv.minus_k_is_k


# ============================== V4/V5 the 1/64 grid: planted k against the null

@pytest.fixture(scope="module")
def pnma64():
    return kgrid_positions(PNMA, kgrid_strata("P n m a", denominator=64))


@pytest.mark.slow
@pytest.mark.xdist_group("kvector-pnma64")
def test_a_planted_line_k_scores_above_its_null(pnma64):
    """V4 positive: ten clean satellites of (0, 18/64, 0), all matched, above the 99 %."""
    pk = _planted(PNMA, K_LINE, 10, 17)
    s = score_kvector(pk, PNMA, K_LINE, radius=RADIUS, band_deg=BAND)
    assert s.n_matched == 10
    null = kgrid_null(pk, PNMA, pnma64, radius=RADIUS, band_deg=BAND,
                      exclude=_exclude(PNMA), n_shuffles=100, percentile=99, seed=20261112)
    assert s.score > null.threshold, (s.score, null.threshold)


@pytest.mark.slow
@pytest.mark.xdist_group("kvector-pnma64")
def test_counts_saturate_under_the_null_while_scores_do_not(pnma64):
    """V5, quantities only: the null's grid maximum matches most peaks by count."""
    pk = _planted(PNMA, K_GENERAL, 10, 18)
    s = score_kvector(pk, PNMA, K_GENERAL, radius=RADIUS, band_deg=BAND)
    null = kgrid_null(pk, PNMA, pnma64, radius=RADIUS, band_deg=BAND,
                      exclude=_exclude(PNMA), n_shuffles=40, percentile=99, seed=3)
    assert s.n_matched == 10
    assert np.median(null.max_matched) >= 9
    assert s.score > np.max(null.sample)
