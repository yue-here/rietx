"""WP-1021/1022/1023 — the search engines, and the properties they must have.

Three things are being tested here and they are not the same kind of claim:

* **recovery** — a known cell comes back, ranked first, from a synthetic peak
  list.  This is the engines' basic job and it is checked per crystal system,
  because cost and failure mode both depend on the metric degrees of freedom;
* **the guards** — the corner-exactness of the Q bounds, the reflection ceiling
  firing *instead of* allocating, an unfinished search reporting itself
  unfinished.  These are the properties the engines' honesty rests on, and each
  of them replaces a measured failure;
* **the shared surface** — the registry, the setting-freedom derivation, the
  pivot form the θ parameterisation assumes.

Wall clock per system is in each WP's handover log; the domain bounds here are
declared narrowly on purpose, because domain size is exactly what an exhaustive
search costs (measured: a monoclinic search over d ∈ [6, 18] Å completes in
~84 s and the same search over d ∈ [2, 18] Å does not finish in 90).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.crystallography.symmetry import generate_reflections
from rietx.indexing.dichotomy import (
    _inside_domain,
    _pivots,
    _q_bounds,
    axis_swaps,
    search_dichotomy,
)
from rietx.indexing.engines import (
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_SEARCH_LINES,
    ENGINE_POOL_MULTIPLE,
    MAX_PREDICTED_REFLECTIONS,
    SYSTEM_ORDER,
    Budget,
    SearchSpec,
    engine_descriptions,
    engine_names,
    get_engine,
    indexes_the_search_lines,
    predicted_reflection_count,
    reflection_ceiling_ok,
    search_line_order,
    trial_hkl,
)
from rietx.indexing.qspace import af_from_cell, design_matrix, metric_basis
from rietx.schemas.indexing import METRIC_DOF, PeakList

LAM = 1.5405929

#: (space group, cell, 2θ_max, d-axis bounds, volume bound) per system.  The
#: cells are the ones ``tests/test_indexing_core.py`` uses, so a failure here and
#: there points at the same lattice.
CASES: dict[str, tuple] = {
    "cubic": ("P m -3 m", (4.1566,) * 3 + (90.0,) * 3, 90.0, (2.0, 12.0), 1500.0),
    "tetragonal": ("P 4/m m m", (3.7842, 3.7842, 9.5146, 90.0, 90.0, 90.0),
                   70.0, (2.0, 12.0), 1500.0),
    "hexagonal": ("P 6/m m m", (9.4166, 9.4166, 6.8745, 90.0, 90.0, 120.0),
                  60.0, (2.0, 14.0), 1500.0),
    "trigonal": ("P -3 m 1", (4.7591, 4.7591, 12.9894, 90.0, 90.0, 120.0),
                 70.0, (2.0, 16.0), 1500.0),
    "orthorhombic": ("P m m m", (7.0, 8.0, 9.0, 90.0, 90.0, 90.0),
                     45.0, (2.0, 12.0), 1500.0),
    "monoclinic": ("P 1 2/m 1", (8.875, 16.408, 7.137, 90.0, 93.84, 90.0),
                   35.0, (6.0, 18.0), 1500.0),
}


def synthetic_peaks(system: str, *, esd_deg: float = 0.005,
                    impurities: tuple[float, ...] = (),
                    sg: str | None = None, cell: tuple | None = None,
                    two_theta_max: float | None = None) -> tuple[PeakList, tuple]:
    """A peak list from a known cell — exact positions, declared σ.

    Positions are exact rather than noisy on purpose: an engine that cannot
    recover a cell from perfect positions has a *search* problem, and mixing in
    noise would confuse that with a tolerance problem.  σ is declared because the
    tolerance model is per line, and ``PeakList.from_positions`` marks every line
    ``sigma_assumed`` so nothing downstream can quote this σ as measured.
    """
    group, true_cell, tt_max, _bounds, _vol = CASES[system]
    group = sg or group
    true_cell = cell or true_cell
    refl = generate_reflections(group, true_cell, LAM,
                               two_theta_max or tt_max)
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    tt = np.sort(np.concatenate([tt, np.asarray(impurities, dtype=np.float64)]))
    return PeakList.from_positions(tt, LAM, two_theta_esd=esd_deg), true_cell


#: Wall-clock budget declared per system, seconds.  A **runaway guard, not a
#: timer.**  The recovery tests assert ``search_complete[system]``, which is a
#: statement about the metric *domain* being exhausted; tying it to a budget the
#: machine can miss turns a correctness assertion into a performance one, and the
#: performance claim belongs in the WP handover logs quoted as a range (CLAUDE.md:
#: "quote wall clock as a range, never as a figure").
#:
#: Found the hard way, 2026-07-30: at 180 s both monoclinic rows **failed in the
#: full suite and passed serially**.  The searches take ~85-105 s alone on a 10-core
#: M4, so 180 s is barely a 2× margin, and under ``-n auto`` with the rest of the
#: suite competing they exceeded it, reported themselves incomplete — correctly —
#: and failed an assertion about exhaustiveness for a reason that had nothing to do
#: with the domain.  Any future case whose serial time is a large fraction of its
#: budget wants a row here rather than a flake.
BUDGET_SECONDS: dict[str, float] = {"monoclinic": 900.0}
#: Budget for the systems that finish in under a second.  Left far above their cost
#: for the same reason: it is there to stop a runaway, not to time anything.
DEFAULT_TEST_BUDGET = 180.0


def spec_for(system: str, **overrides) -> SearchSpec:
    """A search spec for a synthetic list, with **σ_sys declared as zero**.

    Not inherited: these peak lists carry *exact* positions, so the systematic
    allowance an engine assumes for real data
    (``engines.DEFAULT_UNKNOWN_SHIFT_DEG``, 0.05° 2θ) is pure looseness here and it
    changes what the tests measure — with it on, the dominant-row case below finds a
    22 Å junk cell instead of correctly finding nothing.  Declaring the physics
    rather than riding a default is the rule
    (``DESIGN.md`` §Testing & validation policy); the real-data behaviour of that
    default is measured in its own test.
    """
    _sg, _cell, _tt, (min_d, max_d), vol = CASES[system]
    kwargs = dict(systems=(system,), min_d_axis=min_d, max_d_axis=max_d,
                  max_volume=vol, shift_allowance_deg=1e-9,
                  budget_seconds=BUDGET_SECONDS.get(system, DEFAULT_TEST_BUDGET))
    kwargs.update(overrides)
    return SearchSpec(**kwargs)


def assert_same_lattice(found: tuple, true_cell: tuple, *, atol: float = 2e-3):
    """The found cell is the true lattice, up to a setting change.

    Compared as **sorted axis lengths plus volume**, not element by element: the
    engines quotient the search by the axis permutations a system's setting
    freedom allows (``axis_swaps``), so the monoclinic truth legitimately comes
    back as its a↔c partner and an element-wise comparison would fail on a
    correct answer.
    """
    from rietx.crystallography.lattice import cell_volume

    assert np.allclose(np.sort(found[:3]), np.sort(true_cell[:3]), atol=atol), (
        f"{found} against {true_cell}")
    assert cell_volume(*found) == pytest.approx(cell_volume(*true_cell),
                                                rel=1e-3)


# ----------------------------------------------------------------------
# The shared surface
# ----------------------------------------------------------------------
def test_the_engine_registry_is_live_and_described():
    """WP-1024's agent schema quotes this registry, so a registered engine must
    be resolvable and must say what it is for."""
    assert "dichotomy" in engine_names()
    for name in engine_names():
        assert callable(get_engine(name))
        assert len(engine_descriptions()[name]) > 20, name
    with pytest.raises(ValueError, match="unknown indexing engine"):
        get_engine("dicvol")


@pytest.mark.parametrize("engine", sorted(engine_names()))
def test_every_engine_hands_the_merge_a_pool_not_the_reported_cap(engine,
                                                                  monkeypatch):
    """WP-1046 — an engine truncates to :meth:`SearchSpec.engine_pool`, never to
    the cap the *answer* reports.

    The defect this pins is not that the number was small, it is that it was
    applied by the wrong layer.  ``rank_candidates`` ranks with Borda, a
    rank-sum over the pool being ranked, so a unit's ordering is a function of
    what else that unit happened to find; truncating there let a longer search
    *lose* a candidate the consensus panel rates highly — measured on
    bethanechol set F, rank 1 at 5 s and absent at 30 s.  A conformance test
    over the live registry rather than three copies, because the way this
    returns is a new engine written from an old one.
    """
    import sys

    from rietx.indexing import engines as eng

    fn = get_engine(engine)
    module = sys.modules[fn.__module__]
    seen: list[int | None] = []
    real = eng.rank_candidates

    def spy(cands, peaks, **kw):
        seen.append(kw.get("max_candidates"))
        return real(cands, peaks, **kw)

    monkeypatch.setattr(module, "rank_candidates", spy)
    peaks, _cell = synthetic_peaks("cubic")
    spec = spec_for("cubic", budget_seconds=2.0, max_candidates=3)
    fn(peaks, spec=spec)
    assert seen == [spec.engine_pool()] == [3 * ENGINE_POOL_MULTIPLE]


def test_the_pool_is_the_reported_cap_times_the_multiple():
    """One knob, two numbers derived from it — and the derivation is the
    spec's, so no engine can invent its own."""
    assert SearchSpec().max_candidates == DEFAULT_MAX_CANDIDATES
    assert SearchSpec().engine_pool() == DEFAULT_MAX_CANDIDATES * \
        ENGINE_POOL_MULTIPLE
    assert SearchSpec(max_candidates=1).engine_pool() == ENGINE_POOL_MULTIPLE


def test_metric_basis_is_in_the_echelon_form_the_theta_box_assumes():
    """Every system's basis has one exclusive pivot per row.

    The θ parameterisation reads each dimension's physical bound off its pivot
    column; if ``adp_basis`` ever returned a rotated basis this would silently
    become a loose bounding box — correct answers, an order of magnitude slower —
    so it is asserted rather than assumed.
    """
    for system in METRIC_DOF:
        basis = metric_basis(system)
        piv = _pivots(basis)
        assert len(piv) == METRIC_DOF[system]
        assert len({p for p, _v in piv}) == len(piv)


def test_axis_swaps_are_derived_from_the_subspace():
    """Which axis permutations are a setting change is a property of the system,
    and the derivation must reproduce the crystallography.

    Orthorhombic and triclinic admit all three adjacent exchanges; monoclinic
    b-unique admits only a↔c, which is the one that fixes β; the tied systems
    admit them trivially because their metrics are already equal there.
    """
    assert axis_swaps(metric_basis("orthorhombic")) == [(0, 1), (0, 2), (1, 2)]
    assert axis_swaps(metric_basis("triclinic")) == [(0, 1), (0, 2), (1, 2)]
    assert axis_swaps(metric_basis("monoclinic")) == [(0, 2)]


def test_predicted_reflection_count_matches_the_generator_it_guards():
    """The ceiling must count the same box ``generate_reflections`` allocates.

    A guard computed a different way drifts from the thing it guards, so the two
    are pinned together: the generator enumerates ±(floor(a/d_min) + 1) per axis.
    """
    cell = (7.0, 8.0, 9.0, 90.0, 90.0, 90.0)
    d_min = LAM / (2.0 * np.sin(np.radians(45.0)))
    expected = 1
    for axis in cell[:3]:
        expected *= 2 * (int(np.floor(axis / d_min)) + 1) + 1
    assert predicted_reflection_count(cell, LAM, 90.0) == expected


def test_the_reflection_ceiling_refuses_instead_of_allocating():
    """The measured crash guard: a runaway cell asked the generator for 1.6 PiB.

    A 500 Å cell is refused *without* enumeration — the count is arithmetic on the
    cell, so the guard costs nothing and never touches memory.
    """
    assert reflection_ceiling_ok((7.0, 8.0, 9.0, 90.0, 90.0, 90.0), LAM, 90.0)
    runaway = (500.0, 500.0, 500.0, 90.0, 90.0, 90.0)
    assert predicted_reflection_count(runaway, LAM, 90.0) > MAX_PREDICTED_REFLECTIONS
    assert not reflection_ceiling_ok(runaway, LAM, 90.0)


def test_trial_hkl_keeps_one_friedel_mate_and_obeys_the_centring():
    hkl = trial_hkl(2, "P")
    assert not np.any(np.all(hkl == 0, axis=1))
    # no ±pair survives together
    keys = {tuple(int(v) for v in h) for h in hkl}
    assert not any(tuple(-v for v in k) in keys for k in keys)
    for centring, rule in (("I", lambda h: (h.sum(axis=1) % 2 == 0)),
                           ("F", lambda h: ((h[:, 0] + h[:, 1]) % 2 == 0)
                            & ((h[:, 1] + h[:, 2]) % 2 == 0)),
                           ("R", lambda h: ((-h[:, 0] + h[:, 1] + h[:, 2]) % 3
                                            == 0))):
        sub = trial_hkl(3, centring)
        assert len(sub) < len(trial_hkl(3, "P"))
        assert rule(sub).all(), centring


def test_every_centring_is_a_subset_of_the_primitive_trial_set():
    """The shortcut that lets one grid pass cover every centring of a system.

    ``search_dichotomy`` searches the *union* of a system's admissible centrings
    once and re-scores each leaf per centring, instead of running the whole grid
    and dichotomy again per centring.  That is sound only because a centred trial
    set is a strict **subset** of the primitive one: a centred box has fewer
    reflections with which to reach the same lines, so its line-matching test is
    strictly harder and every box surviving it survives the primitive test.
    Asserted here rather than left as folklore in a docstring, because the whole
    completeness claim of the engine rests on it.
    """
    from rietx.indexing.engines import CENTRINGS
    from rietx.indexing.qspace import centring_allows

    primitive = trial_hkl(6, "P")
    assert centring_allows(primitive, "P").all()
    for system, centrings in CENTRINGS.items():
        for centring in centrings:
            allowed = centring_allows(primitive, centring)
            assert allowed.sum() <= len(primitive), (system, centring)
            # a subset *of the same enumeration*, not merely a smaller count
            direct = {tuple(int(v) for v in h) for h in trial_hkl(6, centring)}
            assert direct == {tuple(int(v) for v in h)
                              for h in primitive[allowed]}, (system, centring)


def test_a_centring_that_fits_the_trial_cap_keeps_its_search():
    """One shared pass means one shared trial set, and the cap now sees the union.

    Since "P" admissible makes the union every hkl, a naive shared pass would
    lose the *centred* searches that used to run in their own pass whenever the
    primitive set overflows :data:`MAX_TRIAL_HKL` — a cubic F set is a quarter
    of P's, so there is a band of ``max_index`` where F fits and P does not.
    The widest sets are dropped until the rest fit, and the drop is reported as
    an incomplete search rather than silently.
    """
    from rietx.indexing import dichotomy as D
    from rietx.indexing.engines import effective_shift_allowance
    from rietx.indexing.qspace import sigma_effective

    peaks, _cell = synthetic_peaks("cubic")
    spec = spec_for("cubic")
    # the trial set is sized on the whole pattern, exactly as _search_one does
    allowance, _assumed = effective_shift_allowance(spec, None)
    sigma = sigma_effective(peaks.q_esd(), peaks.two_theta(), peaks.wavelength,
                            allowance)
    n = D._max_index(spec, float(peaks.q().max() + spec.k_sigma * sigma.max()))
    sizes = {c: int(len(trial_hkl(n, c))) for c in ("P", "I", "F")}
    assert sizes["F"] < sizes["I"] < sizes["P"], sizes

    original = D.MAX_TRIAL_HKL
    try:
        # a cap admitting I and F but not P: the primitive search is dropped
        D.MAX_TRIAL_HKL = sizes["I"] + 1
        kept = D.search_dichotomy(peaks, spec=spec)
        # and one admitting nothing at all
        D.MAX_TRIAL_HKL = sizes["F"] - 1
        none_fit = D.search_dichotomy(peaks, spec=spec)
    finally:
        D.MAX_TRIAL_HKL = original

    # dropping any centring means the domain was not covered, and it says so
    assert kept.search_complete["cubic"] is False
    assert none_fit.search_complete["cubic"] is False
    # the centrings that fitted were still searched — the system does not go
    # dark just because the primitive set overflowed
    found = {c.centring for c in kept.candidates}
    assert found and "P" not in found, found
    assert not none_fit.candidates
    # and it names the cap, since a larger budget would change nothing (WP-1449:
    # 11-BM NAC explored 0 boxes in 0.26 s and was reported as a 300 s timeout)
    for res in (kept, none_fit):
        diag = next(d for d in res.diagnostics
                    if d.code == "INDEX_SEARCH_INCOMPLETE")
        assert "size cap on cubic" in diag.message, diag.message
        assert "within" not in diag.message, diag.message
        assert "budget_seconds" not in diag.suggestion, diag.suggestion
    # and with no cap in the way the primitive cell is the one ranked first
    full = D.search_dichotomy(peaks, spec=spec)
    assert full.search_complete["cubic"] is True
    assert full.candidates[0].centring == "P"


def test_a_box_is_refused_when_its_lines_cannot_take_distinct_reflections():
    """Hall's condition, which ``hit.any(axis=1)`` alone does not check.

    Indexing maps lines to reflections **injectively** — one hkl has one Q — so a
    box whose surviving trial set holds fewer reflections than there are lines to
    explain cannot index the pattern, however happily each individual line finds
    *something* to point at.  The weak test is satisfied by letting the lines
    share, and measured on the bethanechol monoclinic domain it refused 342 boxes
    of 692 294 (0.0 %) while this one refuses 89.9 % of what reaches it.
    """
    from rietx.indexing.dichotomy import _assignment_possible

    # five lines, but only three reflections between them: every line finds
    # something (the weak test is satisfied) and no injective map exists
    hit = np.ones((5, 3), dtype=bool)
    counts = hit.sum(axis=1)
    assert hit.any(axis=1).all(), "the weak test must be happy with this box"
    assert not _assignment_possible(hit, 3, counts, 5, n_unindexed=0)
    # the same shortfall is tolerable when two lines may go unindexed
    assert _assignment_possible(hit, 3, counts, 5, n_unindexed=2)

    # forced singletons colliding is a violation at |S| = 2 even when the total
    # reflection count is ample — DICVOL91's own rejection rule
    hit = np.zeros((4, 9), dtype=bool)
    hit[0, 0] = hit[1, 0] = True            # two lines, one forced reflection
    hit[2, 1:5] = hit[3, 5:9] = True
    counts = hit.sum(axis=1)
    assert not _assignment_possible(hit, 9, counts, 4, n_unindexed=0)

    # and a box that genuinely admits a matching is never refused
    hit = np.eye(4, 9, dtype=bool)
    assert _assignment_possible(hit, 9, hit.sum(axis=1), 4, n_unindexed=0)


def test_the_largest_observed_d_is_not_a_bound_on_the_axes_at_low_symmetry():
    """Why Louër & Louër's Table 1 parameter floors are **not** implemented.

    Their "a ≥ d₁ − Δd₁" reads the largest observed spacing as a floor on the
    largest axis, and the paper prints columns for cubic, tetragonal, hexagonal
    and orthorhombic only.  The omission is not an oversight: those forms are
    diagonal, so Q(hkl) ≥ min(A, B, C) and the largest spacing really is a
    principal one.  Add a cross term and it stops being true — an oblique cell
    inside this search's own obliquity bound puts its largest spacing on (101),
    above *every* principal spacing, so the floor would exclude the true cell.

    Adopting the rows the paper does print would be sound, and buys nothing:
    the engine's line-matching test uses a complete trial set with corner-exact
    bounds, which is strictly stronger, and measured on the bethanechol domain
    it accounts for 0.0 % of box deaths.
    """
    from rietx.indexing.dichotomy import MAX_ANGLE_COSINE
    from rietx.indexing.qspace import cell_from_af, design_matrix

    af = np.array([1.0, 0.5, 1.0, 0.0, -1.7, 0.0])
    # the cell is inside the domain the search declares, not a pathology
    assert abs(af[4]) <= 2.0 * MAX_ANGLE_COSINE * np.sqrt(af[0] * af[2])
    cell_from_af(af)                     # and it is a real lattice

    hkl = trial_hkl(3, "P")
    q = design_matrix(hkl) @ af
    q = q[q > 1e-9]
    d_largest = 1.0 / np.sqrt(q.min())
    principal = [1.0 / np.sqrt(design_matrix(np.array([h])) @ af)[0]
                 for h in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    assert d_largest > max(principal), (d_largest, principal)


def test_budget_expires_and_a_cancel_token_short_circuits_it():
    from rietx.optimize.cancel import CancelToken

    assert not Budget(30.0).expired()
    assert not Budget(0.0).expired(), "zero seconds means no deadline, not none left"
    token = CancelToken()
    budget = Budget(30.0, token)
    assert not budget.expired()
    token.cancel()
    assert budget.expired()


# ----------------------------------------------------------------------
# Dichotomy: the bound the whole engine rests on
# ----------------------------------------------------------------------
def test_dichotomy_q_bounds_are_attained_at_the_box_corners():
    """**The claim the engine is built on**: over a box in A..F the extremes of
    Q(hkl) are at corners, so the bound is exact rather than conservative.

    Checked both ways — no sampled point may fall outside the computed interval,
    and the interval must be *tight*, i.e. the extremes over the sampled corners
    reach it.  A merely valid bound would still index correctly while pruning far
    less, which no recovery test would notice.
    """
    rng = np.random.default_rng(1021)
    for system in ("orthorhombic", "monoclinic", "triclinic"):
        basis = metric_basis(system)
        m = design_matrix(trial_hkl(3, "P")) @ basis.T
        n = basis.shape[0]
        lo = rng.uniform(0.005, 0.02, size=n)
        hi = lo + rng.uniform(0.001, 0.01, size=n)
        q_min, q_max = _q_bounds(m, lo, hi)
        # every interior point is inside the interval
        for _trial in range(50):
            theta = lo + rng.uniform(size=n) * (hi - lo)
            q = m @ theta
            assert np.all(q >= q_min - 1e-12), system
            assert np.all(q <= q_max + 1e-12), system
        # and the interval is attained: the corner extremes reach both ends
        corners = np.array(np.meshgrid(*[[lo[j], hi[j]] for j in range(n)],
                                       indexing="ij")).reshape(n, -1).T
        q_corners = corners @ m.T
        assert np.allclose(q_corners.min(axis=0), q_min, atol=1e-12), system
        assert np.allclose(q_corners.max(axis=0), q_max, atol=1e-12), system


def test_the_volume_prune_contains_every_lattice_in_the_box():
    """The determinant bound may be loose; it may **never** exclude the answer.

    ``_det_interval`` intersects two valid bounds — interval arithmetic on the
    expanded determinant, and A·B·C·det R with every correlation clipped to the
    domain's obliquity — because neither dominates: the correlation form carries
    the diagonal spread twice, so it is looser on a box already narrow in its
    off-diagonals, and the expansion is the one that goes useless when the
    off-diagonals are wide.  An intersection is only sound if *both* are, so
    every sampled interior point's det G* must land inside.

    Points violating the cone are excluded from the check on purpose: they are
    excluded from the *search* too (``_initial_box``, ``_stage_edges`` and
    ``_inside_domain`` all enforce it), so a bound that cuts them cuts nothing
    reportable.
    """
    from rietx.indexing.dichotomy import (
        MAX_ANGLE_COSINE,
        _af_interval,
        _det_interval,
    )
    from rietx.indexing.qspace import gstar_from_af

    rng = np.random.default_rng(1030)
    for system in ("orthorhombic", "monoclinic", "triclinic"):
        basis = metric_basis(system)
        n = basis.shape[0]
        for _case in range(40):
            lo = rng.uniform(0.004, 0.05, size=n)
            hi = lo + rng.uniform(1e-4, 0.03, size=n)
            af_lo, af_hi = _af_interval(basis, lo, hi)
            if np.any(af_hi[:3] <= 0.0):
                continue
            det_lo, det_hi = _det_interval(af_lo, af_hi)
            for _trial in range(40):
                theta = lo + rng.uniform(size=n) * (hi - lo)
                af = basis.T @ theta
                if np.any(af[:3] <= 0.0):
                    continue
                cone = [abs(af[p]) <= 2.0 * MAX_ANGLE_COSINE
                        * np.sqrt(af[i] * af[j])
                        for p, (i, j) in ((3, (1, 2)), (4, (0, 2)), (5, (0, 1)))]
                if not all(cone):
                    continue
                det = float(np.linalg.det(gstar_from_af(af)))
                assert det_lo - 1e-15 <= det <= det_hi + 1e-15, (
                    system, det, (det_lo, det_hi))


def test_the_duplicate_leaf_hash_resolves_every_axis_equally():
    """A leaf's identity must be relative **per component**, not to the largest one.

    WP-1026: ``_box_key`` divided A..F by ``max|af|``, so on a cell with a long axis
    — where C = 1/c\\*² is an order of magnitude below A — a 0.1 % grid on the
    largest component was a ~1 % grid on the smallest.  Two leaves whose c differed
    by 0.4 % hashed the same and the second was **skipped before being refined**.
    Measured on the certified corundum pattern that skipped leaf was the one holding
    the certificate's c, and the leaf refined in its place gave c +2799 ppm.

    The property is the one the anisotropy broke: perturbing *any* component by
    several grid steps **on that component's own scale** must change the key,
    whatever the other components' magnitudes.  For a diagonal that scale is the
    component itself; for an off-diagonal — which is legitimately zero here, and
    has no relative scale of its own — it is the Cauchy-Schwarz bound its partners
    set, the same scale ``_inside_domain`` measures it against.
    """
    from rietx.indexing.dichotomy import _OFFDIAG_PARTNERS, _SAME_BOX_RTOL, _box_key

    # a long-axis cell: A/C ≈ 10, the regime that made the old key anisotropic
    af = np.asarray(af_from_cell(
        (4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0)), dtype=np.float64)
    assert af[0] / af[2] > 5.0, "this cell no longer exercises the anisotropy"
    assert _box_key(af) == _box_key(af), "the key is not a function"
    for p in range(6):
        moved = af.copy()
        if p < 3:
            moved[p] *= 1.0 + 20.0 * _SAME_BOX_RTOL
        else:
            i, j = _OFFDIAG_PARTNERS[p]
            moved[p] += 20.0 * _SAME_BOX_RTOL * np.sqrt(af[i] * af[j])
        assert _box_key(moved) != _box_key(af), (
            f"component {p} moved 20 grid steps and hashed the same")
    # the certified c and the cell 0.4 % away from it are different leaves
    cert = af_from_cell((4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0))
    other = af_from_cell((4.759355, 4.759355, 12.99231 * 1.004, 90.0, 90.0, 120.0))
    assert _box_key(cert) != _box_key(other)
    # and the grid stays *crude*: a cell a tenth of a step away is the same leaf
    # or the neighbouring one (a straddle refines twice and merges later, which
    # is the right failure for a performance filter) — never further
    near = np.asarray(af, dtype=np.float64) * (1.0 + 0.1 * _SAME_BOX_RTOL)
    assert max(abs(a - b) for a, b in zip(_box_key(near), _box_key(af))) <= 1


def test_dichotomy_only_reports_cells_inside_the_domain_it_searched():
    """A refined cell may wander out of the domain, and one did — β = 174° with a
    49 Å axis.  Reporting it would carry none of the exhaustiveness the engine
    exists to provide, so it is rejected on *scope*, not quality."""
    spec = spec_for("monoclinic")
    assert _inside_domain(af_from_cell(CASES["monoclinic"][1]), spec)
    assert not _inside_domain(af_from_cell(
        (49.2384, 2.9893, 49.3784, 90.0, 174.0036, 90.0)), spec)
    assert not _inside_domain(af_from_cell(
        (1.5, 8.0, 9.0, 90.0, 90.0, 90.0)), spec)


# ----------------------------------------------------------------------
# Dichotomy: recovery
# ----------------------------------------------------------------------
@pytest.mark.parametrize("system", ["cubic", "tetragonal", "hexagonal",
                                    "trigonal", "orthorhombic"])
def test_dichotomy_recovers_a_known_cell(system):
    """Rank 1 must be the truth, not merely present in the list.

    Ranking is the FoM panel's Borda count (``engines.rank_candidates``), and the
    candidates below the truth are its own derivative lattices — supercells index
    every observed line *exactly* and lose only on ``predicted_seen_fraction``.
    That is a geometrical ambiguity for WP-1024 to report, not a failure here.
    """
    peaks, cell = synthetic_peaks(system)
    result = search_dichotomy(peaks, spec=spec_for(system))
    assert result.candidates, f"{system}: no candidate at all"
    assert result.search_complete[system], f"{system}: budget expired"
    assert_same_lattice(result.candidates[0].cell, cell)
    assert result.candidates[0].n_indexed == result.candidates[0].n_lines


@pytest.mark.slow
def test_dichotomy_recovers_a_monoclinic_cell():
    """The 4-D case, and the one that pins the cost statement.

    Marked slow because it is ~80 s: the grid is (range/0.4)³ × angle slabs, so
    the *declared axis range* is what an exhaustive monoclinic search costs.  Over
    d ∈ [6, 18] Å it completes; over d ∈ [2, 18] Å the same search does not finish
    in 90 s and reports itself incomplete rather than reporting nothing found.
    """
    peaks, cell = synthetic_peaks("monoclinic")
    result = search_dichotomy(peaks, spec=spec_for("monoclinic"))
    assert result.candidates
    assert result.search_complete["monoclinic"]
    assert_same_lattice(result.candidates[0].cell, cell)


def test_dichotomy_finds_a_centred_lattice_with_its_centring():
    """A body- or face-centred lattice is found *as* one.

    This is why the search enumerates centrings rather than metrics alone: an
    F-centred cubic lattice's primitive cell is rhombohedral, so a cubic-subspace
    search that assumed P would never see NaCl at all.
    """
    peaks, cell = synthetic_peaks("cubic", sg="F m -3 m",
                                  cell=(5.6402,) * 3 + (90.0,) * 3)
    result = search_dichotomy(peaks, spec=spec_for("cubic"))
    assert result.candidates
    best = result.candidates[0]
    assert best.centring == "F"
    assert_same_lattice(best.cell, cell)


@pytest.mark.parametrize("n_impurity", [1, 2])
def test_dichotomy_tolerates_impurity_lines(n_impurity):
    """DICVOL06's own reported gain, checked at the default ``n_unindexed = 2``.

    Without tolerated unindexed lines a single impurity line prunes the box that
    contains the truth and the engine returns nothing *confidently* — which is
    the failure this milestone exists to prevent, so the negative half is
    asserted too: at ``n_unindexed = 0`` the same list loses the answer.
    """
    # mid-gap positions, checked against the true line list: an "impurity" that
    # lands within a FWHM of a real line is not an impurity, it is a duplicate,
    # and the first version of this test used 23.4° — 0.1° from the (100) line —
    # so the strict half passed for the wrong reason.
    impurities = (13.96, 21.06)[:n_impurity]
    peaks, cell = synthetic_peaks("tetragonal", impurities=impurities)
    result = search_dichotomy(peaks, spec=spec_for("tetragonal"))
    assert result.candidates, f"{n_impurity} impurities lost the cell"
    assert_same_lattice(result.candidates[0].cell, cell)

    strict = search_dichotomy(peaks, spec=spec_for("tetragonal", n_unindexed=0))
    assert not any(
        np.allclose(np.sort(c.cell[:3]), np.sort(cell[:3]), atol=2e-3)
        for c in strict.candidates), (
        "with no tolerated unindexed lines the impurity should prune the truth")


def test_an_unfinished_search_says_so_rather_than_reporting_nothing_found():
    """``search_complete`` is what makes a *negative* result mean anything.

    An exhaustive engine that finishes and finds nothing has said "no such cell";
    the same engine stopped by its budget has said nothing at all, and the two
    must not look alike.
    """
    peaks, _cell = synthetic_peaks("orthorhombic")
    result = search_dichotomy(peaks, spec=spec_for(
        "orthorhombic", min_d_axis=2.0, max_d_axis=20.0, max_volume=8000.0,
        budget_seconds=0.5))
    assert not result.complete
    codes = [d.code for d in result.diagnostics]
    assert "INDEX_SEARCH_INCOMPLETE" in codes
    message = next(d for d in result.diagnostics
                   if d.code == "INDEX_SEARCH_INCOMPLETE")
    assert "not evidence" in message.message
    # the clock stopped it, so the clock is what it names and what it offers
    assert "within 0.5 s per system" in message.message
    assert message.suggestion.startswith("raise budget_seconds")


def test_a_restricted_search_reports_only_the_systems_it_searched():
    """The engine never concludes anything about systems it did not look at —
    WP-1022's withdrawn-claim lesson, one level down: a low score under a
    restricted search is not evidence about the sample."""
    peaks, _cell = synthetic_peaks("orthorhombic")
    result = search_dichotomy(peaks, spec=spec_for(
        "orthorhombic", systems=("cubic", "tetragonal")))
    assert result.systems_searched == ("cubic", "tetragonal")
    assert set(result.search_complete) == {"cubic", "tetragonal"}
    assert "orthorhombic" not in result.search_complete


@pytest.mark.parametrize("engine", sorted(engine_names()))
def test_a_system_never_started_is_never_claimed(engine):
    """WP-1037: ``systems_searched`` means *started*, not *requested*.

    Before this, an engine whose token was already set still 'searched' every
    system — each one entered, given an instantly-expired budget, and recorded
    as a zero-second incomplete search — so a run stopped early was
    indistinguishable from one truncated after real work.  A pre-set token now
    claims nothing, which is the engine-level half of the three-state reading
    (searched / truncated / not reached) the workflow reports."""
    from rietx.indexing.engines import get_engine
    from rietx.optimize.cancel import CancelToken

    peaks, _cell = synthetic_peaks("cubic")
    token = CancelToken()
    token.cancel()
    result = get_engine(engine)(peaks, spec=spec_for("cubic"), cancel=token)
    assert result.systems_searched == ()
    assert result.search_complete == {}
    assert result.candidates == []


def test_the_probe_cost_is_visible_in_the_stats():
    """WP-1037's task-0 profile found the dominant-zone probe about a third of
    the worst case and absent from every stat.  When it runs, it now reports
    its seconds; when the search found candidates, it does not run and the key
    is absent — so the key's presence *is* the record that it ran."""
    from rietx.indexing.trial_error import search_trial_error

    peaks, _cell = synthetic_peaks("cubic")
    # a volume ceiling below the true cell's leaves nothing to find, cheaply:
    # the search dies at the volume gate and so do the probe's wider rungs
    barren = search_trial_error(peaks, spec=spec_for("cubic", max_volume=20.0))
    assert not barren.candidates
    assert "probe.seconds" in barren.stats

    found = search_trial_error(peaks, spec=spec_for("cubic"))
    assert found.candidates
    assert "probe.seconds" not in found.stats


# ----------------------------------------------------------------------
# Trial and error (WP-1022)
# ----------------------------------------------------------------------
def test_the_index_table_is_distinct_design_rows_not_distinct_hkl():
    """Q sees hkl only through ``design_matrix(hkl) @ basis.T``, so equal rows are
    one trial label.

    In a cubic cell every reflection with h²+k²+l² = 9 is one label, not three, and
    since the enumeration goes as (labels)ⁿ that collapse is worth one to two
    orders of magnitude.  Asserted against the invariant computed independently.
    """
    from rietx.indexing.trial_error import index_table

    rows, hkl, truncated = index_table(metric_basis("cubic"), "P", 2)
    assert not truncated
    invariants = {int(h @ h) for h in trial_hkl(2, "P")}
    assert len(rows) == len(invariants)
    assert len(hkl) == len(rows)
    # and they arrive smallest first, which is what makes a truncation sensible
    norms = np.linalg.norm(rows, axis=1)
    assert np.all(np.diff(norms) >= -1e-12)


def test_allowed_labels_is_the_corner_bound_applied_per_line():
    """A label whose whole reachable Q range misses a line cannot be its index.

    Same exact bound WP-1021 prunes boxes with, which is why it is not a heuristic:
    the lowest line can only carry small-‖m‖ labels, because a large one would need
    an axis longer than ``max_d_axis``.
    """
    from rietx.indexing.dichotomy import _initial_box
    from rietx.indexing.trial_error import allowed_labels, index_table

    system = "orthorhombic"
    basis = metric_basis(system)
    spec = spec_for(system)
    lo, hi = _initial_box(basis, spec)
    rows, _hkl, _t = index_table(basis, "P", 2)

    peaks, cell = synthetic_peaks(system)
    q = np.sort(peaks.q())
    low = allowed_labels(rows, float(q[0]), lo, hi)
    high = allowed_labels(rows, float(q[-1]), lo, hi)
    assert len(low) < len(high), "the lowest line must admit the fewest labels"
    # the truth is never excluded: its own label reaches its own line
    af = af_from_cell(cell)
    theta, *_ = np.linalg.lstsq(basis.T, af, rcond=None)
    for label in low:
        reach = float(rows[label] @ theta)
        assert reach > 0.0


def test_the_base_pool_must_reach_a_line_with_a_cross_term():
    """**The measured reason `BASE_POOL_MIN` is 8 and not 6.**

    The monoclinic test cell's six lowest reflections are 010, 100, 020, 110, 001,
    011 — every one has h·l = 0, so the E column of the exact system is identically
    zero and *no* 4-subset of them determines β.  A pool of six cannot index this
    cell at all, and it fails by returning partial cells with the right b axis
    rather than by returning nothing, which is the worse failure of the two.
    """
    from itertools import combinations as _combinations

    from rietx.indexing.trial_error import BASE_POOL_MIN

    basis = metric_basis("monoclinic")
    peaks, cell = synthetic_peaks("monoclinic")
    _sg, true_cell, tt_max, _b, _v = CASES["monoclinic"]
    refl = generate_reflections("P 1 2/m 1", true_cell, LAM, tt_max)
    q = 1.0 / np.asarray(refl.d) ** 2
    order = np.argsort(q)
    rows = design_matrix(np.asarray(refl.hkl)[order]) @ basis.T

    assert np.all(rows[:6, 3] == 0.0), "the six lowest lines carry no cross term"
    assert not any(abs(np.linalg.det(rows[list(base)])) > 1e-12
                   for base in _combinations(range(6), 4)), (
        "a six-line pool is singular for every base set")
    assert any(abs(np.linalg.det(rows[list(base)])) > 1e-12
               for base in _combinations(range(8), 4)), (
        "an eight-line pool determines the metric")
    assert BASE_POOL_MIN >= 8


@pytest.mark.parametrize("system", ["cubic", "tetragonal", "hexagonal",
                                    "trigonal", "orthorhombic"])
def test_trial_error_recovers_a_known_cell(system):
    """The exact n×n solve, ranked on the same panel dichotomy is ranked on."""
    from rietx.indexing.trial_error import search_trial_error

    peaks, cell = synthetic_peaks(system)
    result = search_trial_error(peaks, spec=spec_for(system))
    assert result.candidates, f"{system}: no candidate at all"
    assert result.search_complete[system]
    assert_same_lattice(result.candidates[0].cell, cell)


@pytest.mark.slow
def test_trial_error_recovers_a_monoclinic_cell():
    """~90 s: the 4-D case, recovered as the a↔c setting partner of the truth."""
    from rietx.indexing.trial_error import search_trial_error

    peaks, cell = synthetic_peaks("monoclinic")
    result = search_trial_error(peaks, spec=spec_for("monoclinic"))
    assert result.candidates
    assert result.search_complete["monoclinic"]
    assert_same_lattice(result.candidates[0].cell, cell)


def test_trial_error_is_deterministic_and_order_invariant():
    """Seed-free by construction, so the same list must give the same answer —
    and the *set* of candidates must not depend on the order the lines arrived in.

    Order invariance is the sharper of the two: the base sets come from
    ``combinations`` over the lines sorted by Q, so a shuffled peak list must sort
    to the same pool.  A reduced cell is compared rather than the raw one, because
    a permuted input may legitimately produce a different *setting*.
    """
    from rietx.indexing.reduce import reduced_af
    from rietx.indexing.trial_error import search_trial_error

    peaks, _cell = synthetic_peaks("tetragonal")
    spec = spec_for("tetragonal")
    first = search_trial_error(peaks, spec=spec)
    again = search_trial_error(peaks, spec=spec)
    assert [c.cell for c in first.candidates] == [c.cell for c in again.candidates]

    rng = np.random.default_rng(1022)
    shuffled = PeakList(
        peaks=[peaks.peaks[i] for i in rng.permutation(len(peaks.peaks))],
        wavelength=peaks.wavelength, two_theta_min=peaks.two_theta_min,
        two_theta_max=peaks.two_theta_max, source=peaks.source)
    out_of_order = search_trial_error(shuffled, spec=spec)
    keys = {tuple(np.round(reduced_af(c.fit.af), 6)) for c in first.candidates}
    other = {tuple(np.round(reduced_af(c.fit.af), 6))
             for c in out_of_order.candidates}
    assert keys == other


def test_trial_error_survives_an_impurity_among_the_base_lines():
    """Its own failure mode, and the mitigation that is not shared with dichotomy.

    One impurity among the base lines poisons the *exact* solve — there is no
    tolerance in it to absorb the line.  Leave-k-out is implicit in
    ``combinations``, so some base set of size n misses the impurity, and the
    full-list check then rejects every metric fitted to it.
    """
    from rietx.indexing.trial_error import search_trial_error

    peaks, cell = synthetic_peaks("tetragonal", impurities=(13.96,))
    result = search_trial_error(peaks, spec=spec_for("tetragonal"))
    assert result.candidates, "an impurity among the base lines lost the cell"
    assert_same_lattice(result.candidates[0].cell, cell)


def test_the_within_engine_dedup_key_carries_the_scale_and_the_centring():
    """``engines.solution_key`` — the two ways a lazier key loses a real answer.

    Both engines were born with one of these and both cost a real answer.  The
    scale half was measured in ``svd`` (WP-1040): a one-dimensional metric is
    ``(A, A, A, 0, 0, 0)``, so hashing ``af / max|af|`` maps *every* cubic cell to
    one key, the first random start on the volume ladder blocks all the rest, and
    a clean synthetic cubic pattern returned **0 candidates from 72 starts that
    included the truth**.  The centring half was measured on 11-BM NAC.  This is
    the unit statement; the engine-level cost of each is the test below, which is
    where the two compound.
    """
    from rietx.indexing.engines import solution_key
    from rietx.indexing.qspace import af_from_cell

    # scale: two cubic metrics differing only in scale are different hypotheses,
    # and a scale-*invariant* key maps every cubic cell to one entry
    small = af_from_cell((4.0, 4.0, 4.0, 90.0, 90.0, 90.0))
    large = af_from_cell((8.0, 8.0, 8.0, 90.0, 90.0, 90.0))
    assert solution_key(small, "P") != solution_key(large, "P")
    # ...but a change far below the grid is still the same solution, which is the
    # whole point of a pre-filter
    same = af_from_cell((4.0 * (1 + 1e-6),) * 3 + (90.0, 90.0, 90.0))
    assert solution_key(small, "P") == solution_key(same, "P")

    # centring: identical axes, two centrings, two lattices
    assert solution_key(small, "P") != solution_key(small, "I")


def test_a_body_centred_cubic_list_survives_the_engines_own_dedup():
    """The measured cost of the two defects above, on a lattice that has both.

    A cubic **I** list is the case where they compound, and the compounded failure
    is silent and confident: the engine returns exactly **one** candidate, cubic
    **P** with a = 6.2/√2, which indexes 15 of the 17 lines and is not the answer.

    Measured on this list (a = 6.2 Å, ``I m -3 m``, 17 lines), by substitution:

    | key | candidates | first | true I present |
    |---|---|---|---|
    | scale-invariant, no centring | 1 | P a = 4.3841 | **no** |
    | scale-invariant, with centring | 2 | I a = 6.2000 | yes |
    | scale-dependent, no centring | 4 | **P a = 6.2000** | **no** |
    | both (shipped) | 8 | I a = 6.2000 | yes |

    Row three is the 11-BM NAC failure in miniature — the same axes described as
    P, which predicts reflections the I lattice does not and the pattern lacks.
    Row one is why the cubic case is the one to test: a one-dimensional metric is
    where scale invariance is total rather than merely lossy.
    """
    from rietx.indexing.trial_error import search_trial_error

    peaks, cell = synthetic_peaks("cubic", sg="I m -3 m",
                                  cell=(6.2, 6.2, 6.2, 90.0, 90.0, 90.0))
    result = search_trial_error(peaks, spec=spec_for("cubic"))
    assert len(result.candidates) > 1, (
        "one candidate from a cubic search is the scale-invariant key collapsing "
        "the whole system onto a single entry")
    best = result.candidates[0]
    assert best.centring == "I", (
        f"the body-centred description was discarded for {best.centring}: the "
        "dedup key does not carry the centring")
    assert_same_lattice(best.cell, cell)
    assert best.n_indexed == best.n_lines


def _long_axis_peaks(c: float, crop: float, tt_max: float) -> PeakList:
    """A tetragonal pattern whose low-angle lines are cropped away — a = 4 Å."""
    refl = generate_reflections("P 4/m m m", (4.0, 4.0, c, 90.0, 90.0, 90.0),
                                LAM, tt_max)
    tt = np.sort(np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d)))))
    return PeakList.from_positions(tt[tt >= crop], LAM, two_theta_esd=0.005)


def test_the_c_26_crop_28_construction_is_indexed_at_the_base_table():
    """**It was never a dominant zone**, and for two years the suite said it was.

    This construction — c = 26 Å cropped at 28° 2θ — was the fixture for
    ``INDEX_DOMINANT_ZONE``, asserting the exact solve finds nothing because the
    lowest observed lines carry indices outside the base table.  The premise was
    false.  Instrumenting the base search (WP-1041) shows it reaches **five**
    metrics of the truth's shape at indices ≤ 2, and the truth among them, from
    base labels (020) and (02-1); what the search returned was nothing, because a
    junk cell at a = 4.1812, c = 27.1561 — the same *shape* to within the dedup
    grid — was solved first, claimed the key, **failed scoring, and still blocked
    every later metric of that shape**, the truth included.  ``seen.add`` runs
    before ``_score``, so a rejected candidate poisoned its whole scale family.

    So the diagnostic had been firing on a dedup artefact rather than on the index
    table, which is the shape of failure CLAUDE.md already names one rank down: *a
    performance filter fails with a wrong answer.*  With the key carrying the
    scale (``engines.solution_key``) the truth comes back indexing **78 of 78**,
    and the genuine dominant-row case now lives in its own row below.
    """
    from rietx.indexing.trial_error import search_trial_error

    peaks = _long_axis_peaks(26.0, 28.0, 70.0)
    spec = SearchSpec(systems=("tetragonal",), max_d_axis=34.0,
                      max_volume=1500.0, budget_seconds=DEFAULT_TEST_BUDGET,
                      shift_allowance_deg=1e-9)
    result = search_trial_error(peaks, spec=spec)

    assert result.candidates, "the base table does reach this cell — it was the "\
        "dedup key that hid it"
    best = result.candidates[0]
    assert_same_lattice(best.cell, (4.0, 4.0, 26.0, 90.0, 90.0, 90.0))
    assert best.n_indexed == best.n_lines
    assert not [d for d in result.diagnostics if d.code == "INDEX_DOMINANT_ZONE"]


@pytest.mark.slow
def test_a_dominant_row_is_raised_from_the_engines_own_experience():
    """``INDEX_DOMINANT_ZONE``, which WP-1019 measured a *census* cannot supply.

    The construction is the real condition rather than a mock of it: a tetragonal
    cell with c = 40 Å whose pattern is cropped at 33° 2θ, so the lines that would
    pin the short axis are outside the measured range and the lowest *observed*
    reflections carry large indices along one axis.  The exact solve then finds
    nothing at the base table — and the engine says *why* by re-running with a
    wider one and reporting that a cell appears only then.

    **The probe's cell is not the truth and the diagnostic does not claim it is.**
    Measured on the wider ``2θ_max`` variant of this construction, the wider table
    returns a = 8, c = 20 indexing 52 of 59 lines, where the truth is a = 4,
    c = 40.  The statement is about the *table* having been the binding
    constraint, which is exactly what a long axis does to a low-angle line's
    index; a cell that survives the probe is evidence about the search, not an
    answer.

    **Marked slow, and the budget margin stated rather than assumed.**  The
    ``c = 26`` construction is now indexed at the base table (the row above), so a
    genuine case needs a longer axis and a wider domain, and both cost.  The lever
    ``tests/CLAUDE.md`` prescribes when a budget fix makes something slow is
    narrowing the scope, never the budget, and that is what the numbers below are:
    measured serially, ``2θ_max`` 55° costs the probe **25 s of its 30 s cap**,
    46° costs **13 s**, and the domain cannot narrow further — at ``max_d_axis``
    45 the probe finds nothing at any rung, so the diagnostic never fires and the
    row would assert a silence for the wrong reason.  13 s against 30 is a 2.3×
    margin, which is thinner than the rule likes; the row is marked slow rather
    than run in the fast selection because of it, and the ladder's **three** rungs
    are the rest of its resilience — a truncated rung 3 is followed by rung 5 with
    a fresh budget and a wider table.
    """
    from rietx.indexing.trial_error import (
        BASE_INDEX_MAX,
        DOMINANT_ZONE_PROBE_LADDER,
        DOMINANT_ZONE_PROBE_SECONDS,
        search_trial_error,
    )

    peaks = _long_axis_peaks(40.0, 33.0, 46.0)
    spec = SearchSpec(systems=("tetragonal",), max_d_axis=52.0,
                      max_volume=1500.0,
                      budget_seconds=max(DEFAULT_TEST_BUDGET,
                                         DOMINANT_ZONE_PROBE_SECONDS),
                      shift_allowance_deg=1e-9)

    result = search_trial_error(peaks, spec=spec)
    assert not result.candidates, "the base table should not reach these indices"
    diag = [d for d in result.diagnostics if d.code == "INDEX_DOMINANT_ZONE"]
    assert diag, [d.code for d in result.diagnostics]
    assert f"up to {BASE_INDEX_MAX}" in diag[0].message
    assert "dichotomy" in (diag[0].suggestion or "")
    assert DOMINANT_ZONE_PROBE_LADDER[0] > BASE_INDEX_MAX


def test_the_two_engines_agree_on_the_same_list():
    """**Agreement between independent searches is the confidence** (WP-1024
    turns this into a gate; here it is checked to exist at all).

    The two engines share the Q-space core and nothing about how they search:
    dichotomy bounds Q over a box of metrics and never assumes an index, trial and
    error assumes indices and never bounds anything.  Landing on the same lattice
    is therefore evidence, which is the entire premise of the three-engine design.
    """
    from rietx.indexing.trial_error import search_trial_error

    for system in ("hexagonal", "orthorhombic"):
        peaks, cell = synthetic_peaks(system)
        a = search_dichotomy(peaks, spec=spec_for(system))
        b = search_trial_error(peaks, spec=spec_for(system))
        assert a.candidates and b.candidates, system
        assert_same_lattice(a.candidates[0].cell, cell)
        assert_same_lattice(b.candidates[0].cell, cell)
        assert a.candidates[0].engine == "dichotomy"
        assert b.candidates[0].engine == "trial_error"


def test_the_shift_allowance_is_assumed_declared_and_reported():
    """An assumed precision must never look like a measured one.

    ``effective_shift_allowance`` has three cases in priority order — declared by the
    caller, *measured* by the data-quality screen, or assumed — and only the third
    sets the "assumed" flag that puts ``INDEX_SHIFT_ALLOWANCE`` in the result.  This
    is the same rule ``PeakList.from_positions`` follows for σ(2θ), one level up.

    **What it reads from a measured screen is ``allowance_deg``, and WP-1038
    changed that**: the window is matched against *uncorrected* positions, so it
    must span the shift's own amplitude, not the scatter the template leaves.  A
    screen carrying only ``sigma_sys_deg`` is therefore not a usable measurement
    and falls through to the assumed value — which is the honest answer, since
    that field never was the window.
    """
    from rietx.indexing.engines import (
        DEFAULT_UNKNOWN_SHIFT_DEG,
        effective_shift_allowance,
        shift_allowance_diagnostic,
    )
    from rietx.schemas.indexing import ShiftScreen

    plain = SearchSpec()
    assert effective_shift_allowance(plain) == (DEFAULT_UNKNOWN_SHIFT_DEG, True)
    assert effective_shift_allowance(SearchSpec(shift_allowance_deg=0.02)) == (0.02, False)

    class _Q:
        shift = ShiftScreen(n_lines=20, sigma_sys_deg=0.011, allowance_deg=0.048,
                            source="measured")
    assert effective_shift_allowance(plain, _Q()) == (0.048, False)

    # both trusted sources are measurements; they differ in failure mode, not
    # in whether the number may be used (TRUSTED_SHIFT_SOURCES)
    class _Pairs:
        shift = ShiftScreen(n_lines=20, sigma_sys_deg=0.004, allowance_deg=0.077,
                            source="reflection_pairs")
    assert effective_shift_allowance(plain, _Pairs()) == (0.077, False)

    # the scatter alone is not the window: a screen that carries only the
    # residual σ has not measured what the search needs, and the 4.3× gap
    # between them is the difference between a cell and no cell on SRM 660c
    class _ScatterOnly:
        shift = ShiftScreen(n_lines=20, sigma_sys_deg=0.011, source="measured")
    assert effective_shift_allowance(plain, _ScatterOnly()) == (
        DEFAULT_UNKNOWN_SHIFT_DEG, True)

    # an *unavailable* screen is not a measurement, even when it carries a number
    class _Unavailable:
        shift = ShiftScreen(n_lines=20, sigma_sys_deg=0.011, allowance_deg=0.048,
                            source="unavailable")
    assert effective_shift_allowance(plain, _Unavailable()) == (
        DEFAULT_UNKNOWN_SHIFT_DEG, True)

    diag = shift_allowance_diagnostic(DEFAULT_UNKNOWN_SHIFT_DEG)
    assert diag.code == "INDEX_SHIFT_ALLOWANCE"
    assert "assumed" in diag.where[0]
    assert "shift_template" in (diag.suggestion or "")


def test_a_shift_template_is_fitted_only_after_a_candidate_survives():
    """``refine_with_shift`` corrects an accepted candidate, never the search.

    With a template it re-fits the surviving lines including the shift column;
    without one it is the identity.
    """
    from rietx.indexing.engines import refine_with_shift
    from rietx.indexing.qspace import refine_candidate, sigma_effective
    from rietx.indexing.quality import shift_template_basis
    from rietx.schemas.indexing import q_of_two_theta

    _sg, cell, tt_max, _b, _v = CASES["orthorhombic"]
    refl = generate_reflections("P m m m", cell, LAM, tt_max)
    hkl = np.asarray(refl.hkl)
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    shifted = tt + 0.06 * shift_template_basis(tt)["cos_theta"]
    q = q_of_two_theta(shifted, LAM)
    sigma = sigma_effective(np.full_like(q, 1e-5), shifted, LAM, 0.0)
    lines = np.arange(len(q))

    naive = refine_candidate(q, sigma, hkl, system="orthorhombic")
    assert refine_with_shift(naive, SearchSpec(), "orthorhombic", q, sigma,
                             shifted, LAM, lines, hkl) is naive

    fixed = refine_with_shift(naive, SearchSpec(shift_template="cos_theta"),
                              "orthorhombic", q, sigma, shifted, LAM, lines, hkl)
    assert fixed is not naive
    assert fixed.shift_coefficient == pytest.approx(0.06, rel=5e-3)
    assert np.allclose(fixed.cell, cell, atol=2e-4)
    assert max(abs(np.asarray(naive.cell[:3]) - np.asarray(cell[:3]))) > 1e-3


def test_a_declared_shift_template_is_not_adjudicated_by_chi_squared():
    """A declared template is the caller's physics — only identifiability refuses it.

    WP-1026: the accept rule was ``keep it if χ²_red improved``, which is backwards.
    The column always costs a degree of freedom while a cell that has *already*
    absorbed the shift into its axes cannot gain much χ² from it, so the test
    refused the correction exactly where it was needed.  Two consequences are
    asserted here.  On data with **no** shift the template is still fitted and comes
    back consistent with zero — reported, not silently declined — even though the
    extra column makes χ²_red slightly worse.  And when the assigned lines cannot
    support one more parameter the original fit is returned unchanged, because that
    is a statement about the design matrix rather than about the fit.
    """
    from rietx.indexing.engines import refine_with_shift
    from rietx.indexing.qspace import refine_candidate, sigma_effective
    from rietx.schemas.indexing import q_of_two_theta

    _sg, cell, tt_max, _b, _v = CASES["orthorhombic"]
    refl = generate_reflections("P m m m", cell, LAM, tt_max)
    hkl = np.asarray(refl.hkl)
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    q = q_of_two_theta(tt, LAM)
    sigma = sigma_effective(np.full_like(q, 1e-5), tt, LAM, 0.0)
    lines = np.arange(len(q))
    spec = SearchSpec(shift_template="cos_theta")

    clean = refine_candidate(q, sigma, hkl, system="orthorhombic")
    out = refine_with_shift(clean, spec, "orthorhombic", q, sigma, tt, LAM,
                            lines, hkl)
    assert out is not clean, "a declared template was declined on a statistic"
    assert out.shift_template == "cos_theta"
    assert abs(out.shift_coefficient) < 3.0 * max(out.shift_esd, 1e-9) + 1e-4
    assert np.allclose(out.cell, cell, atol=2e-4)

    # too few lines for the metric plus the shift column: not refusable on the
    # fit, refusable on the design
    n_free = metric_basis("orthorhombic").shape[0]
    few = np.arange(n_free + 1)
    assert refine_with_shift(clean, spec, "orthorhombic", q, sigma, tt, LAM,
                             few, hkl[few]) is clean


def test_systems_are_searched_highest_symmetry_first():
    """Search order is a cost statement, not a preference: 1 metric degree of
    freedom in cubic against 6 in triclinic."""
    dofs = [METRIC_DOF[s] for s in SYSTEM_ORDER]
    assert dofs == sorted(dofs), f"{SYSTEM_ORDER} is not in cost order: {dofs}"
    assert SYSTEM_ORDER[0] == "cubic"
    assert SYSTEM_ORDER[-1] == "triclinic"
    assert set(SYSTEM_ORDER) == set(METRIC_DOF)


# ----------------------------------------------------------------------
# Which lines drive a search — WP-1039
# ----------------------------------------------------------------------
def test_the_search_is_driven_by_the_strongest_lines_in_q_order():
    """The rule is *rank by intensity, report in Q order* — both halves matter.

    The rank is what fixes a pattern that opens on background; the Q order is what
    every consumer downstream assumes, including ``trial_error``'s base-line pool,
    whose exact solve wants the lowest-Q lines of whatever the search was given.
    """
    tt = np.array([5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
    inten = np.array([1.0, 900.0, 2.0, 800.0, 3.0, 700.0])
    peaks = PeakList.from_positions(tt, LAM, intensity=inten)
    spec = SearchSpec(n_search_lines=3)

    sel = search_line_order(peaks, spec)
    assert len(sel) == 3
    q = peaks.q()
    assert np.all(np.diff(q[sel]) > 0), "the selection is not in Q order"
    # the three strongest are the 10/20/30° lines, and none of the weak ones
    assert np.allclose(np.sort(peaks.two_theta()[sel]), [10.0, 20.0, 30.0])


def test_a_position_only_list_selects_exactly_as_it_did_before_the_rule():
    """The bethanechol benchmark's invariance, asserted rather than hoped for.

    ``from_positions`` without intensities gives every line weight 1, so the
    intensity key is constant and the Q tiebreak decides — which is *identically*
    the ``argsort(q)[:n]`` this package used before WP-1039.  An assumed intensity
    may no more reorder a search than an assumed σ may refuse one, and every one
    of the ten published benchmark sets arrives this way.
    """
    tt = np.array([31.0, 6.238, 22.4, 13.171, 9.403, 6.712, 18.0])
    peaks = PeakList.from_positions(tt, LAM)          # no intensity=
    q = peaks.q()
    for n in (2, 4, len(tt), len(tt) + 5):
        sel = search_line_order(peaks, SearchSpec(n_search_lines=n))
        assert np.array_equal(sel, np.argsort(q)[:min(n, len(q))]), (
            f"n={n}: {sel} is not the first {n} in Q order")


def test_offering_more_lines_can_refute_the_true_cell():
    """**The published false-peak asymmetry does not transfer to this package**,
    and the reason is our acceptance rule rather than our enumeration.

    Oishi-Tomiyasu (2014) §3 argues a false line costs only computation, because
    there the enumeration's success is a *membership* test on Λ^obs and adding
    elements cannot break it.  :func:`indexes_the_search_lines` is not a
    membership test: it demands ``hit >= len(search) - n_unindexed``, an
    **absolute** budget over whatever the search was driven by.  So every foreign
    line admitted spends that budget, and past ``n_unindexed`` of them the true
    cell is refused — the truth is not out-competed, it is *rejected*.

    Measured on the real corpus (WP-1039): the qarr zircon list carries 16 foreign
    lines among 68, and raising N from 20 to 32 loses the certified lattice
    entirely rather than merely ranking it lower.  That is why this WP raised no
    count.
    """
    truth = np.arange(10)                    # the lines the true cell indexes
    n_unindexed = 2

    # a search driven by ten true lines plus two foreign ones: still accepted
    assert indexes_the_search_lines(truth, np.arange(12), n_unindexed)
    # one more foreign line and the *same* true cell is refused
    assert not indexes_the_search_lines(truth, np.arange(13), n_unindexed)


def test_the_base_pool_is_a_prefix_of_the_selected_search_lines():
    """``trial_error``'s exact solve must start from lines the *selection* kept.

    The pool used to be the lowest-Q lines of the whole list, which on a pattern
    opening on background is exactly the set the selection just declined — and an
    exact solve is poisoned by one bad base line.  Measured on SRM 660c: with the
    2θ-order pool only ``dichotomy`` finds the certified cell and the run reports
    ``engines_disagree``; with the pool drawn from the strongest-N selection both
    engines find it.
    """
    from rietx.indexing.trial_error import BASE_POOL_MIN

    tt = np.linspace(5.0, 60.0, 40)
    inten = np.ones_like(tt)
    inten[20:] = 1000.0                       # every strong line is high-angle
    peaks = PeakList.from_positions(tt, LAM, intensity=inten)

    spec = SearchSpec(n_search_lines=DEFAULT_SEARCH_LINES)
    sel = search_line_order(peaks, spec)
    pool = sel[:BASE_POOL_MIN]                      # what ``_search_system`` takes

    # the pool is the low-Q end **of the selection**…
    assert np.array_equal(pool, np.sort(sel)[:BASE_POOL_MIN])
    # …and on this list that is a different set from the low-Q end of the pattern,
    # which is what it used to be — the assertion is worthless without this half
    old_pool = np.argsort(peaks.q())[:BASE_POOL_MIN]
    assert not np.array_equal(np.sort(pool), np.sort(old_pool))
    assert peaks.two_theta()[pool].min() > tt[19], (
        "the pool is still drawn from lines the selection declined")


@pytest.mark.parametrize("engine", ["dichotomy", "trial_error"])
def test_weak_background_components_below_the_first_line_do_not_defeat_a_search(
        engine):
    """The NAC failure in miniature, end to end and on both engines.

    A synthetic cubic pattern with six weak components *below* its first
    reflection — the shape of a synchrotron list that opens on background at
    0.76° 2θ.  In 2θ order those six would be half the driven set, they index
    nothing, and the true cell is refused by ``indexes_the_search_lines`` for
    spending an absolute budget of ``n_unindexed = 2``.  Ranked by intensity they
    are never driven on at all, so the same list, the same tolerance and the same
    N recover the cell.

    **N is declared below the line count on purpose**, and that is the condition
    rather than a convenience: a selection rule can only decline what it is not
    obliged to take, so on a list no longer than N it does nothing at all.  The
    real corpus is the other way round — NAC offers 285 lines to a search driven
    by 20 — but the synthetic cubic list has 14, and the first version of this
    test set N = 20 over 20 lines and failed for exactly that reason.

    Both engines, because a selection rule that fixed only one would break the
    agreement that *is* this package's confidence.
    """
    peaks, cell = synthetic_peaks("cubic")
    tt = peaks.two_theta()
    # **Irregular on purpose, and a volume ceiling with it.**  The first version
    # spaced these evenly with ``linspace`` and dichotomy correctly returned the
    # *doubled* cell — evenly spaced components below the first line are exactly
    # what a doubled axis predicts, so the fixture had built a genuine supercell
    # ambiguity rather than background.  Supercell discrimination is the FoM
    # panel's job and is tested against it elsewhere; here it is a confound, so
    # the blips are non-commensurate and the search is capped below the doubled
    # cell's 574 Å³.
    junk = tt.min() - np.array([6.23, 4.91, 3.02, 2.37, 1.44, 1.09])
    assert junk.min() > 1.0

    both = np.concatenate([junk, tt])
    strength = np.concatenate([np.full(len(junk), 0.004), np.ones(len(tt))])
    contaminated = PeakList.from_positions(both, LAM, intensity=strength,
                                           two_theta_esd=0.005)
    spec = spec_for("cubic", n_search_lines=12, max_volume=300.0)

    # the rule declines every blip — assert it here so a regression in the
    # selection fails on its own terms rather than as a mysterious lost cell
    driven = contaminated.two_theta()[search_line_order(contaminated, spec)]
    assert not np.intersect1d(np.round(driven, 6), np.round(junk, 6)).size
    # …and in 2θ order half the driven set would be blips, which the absolute
    # budget of n_unindexed = 2 cannot absorb
    in_2theta_order = contaminated.two_theta()[np.argsort(contaminated.q())][:12]
    assert np.intersect1d(np.round(in_2theta_order, 6),
                          np.round(junk, 6)).size == 6

    result = get_engine(engine)(contaminated, spec=spec)
    assert result.candidates, f"{engine} lost the cell to six background blips"
    assert_same_lattice(result.candidates[0].cell, cell)


def test_the_rank_is_applied_within_a_bounded_low_q_pool():
    """``SEARCH_POOL_MULTIPLE`` is a **cost** bound, and it is load-bearing.

    Dichotomy sizes the trial set it tests each box against by the largest Q among
    the *driven* lines, so an unbounded intensity rank over a lab pattern running
    to 150° 2θ enlarges that set for every box in the recursion.  Measured on the
    qarr corundum trigonal search: 72 s unbounded against 26 s bounded, both
    ranking the certified cell first; over the whole indexing acceptance file,
    ~25 min against ~12.

    The two properties asserted here are the ones that make it safe.  A list no
    longer than the pool is selected exactly as the unbounded rule would select it
    — which is why SRM 660c's engine agreement survives the bound — and on a long
    list the driven set cannot reach past the pool's own Q ceiling.
    """
    from rietx.indexing.engines import SEARCH_POOL_MULTIPLE

    n = 10
    spec = SearchSpec(n_search_lines=n)

    # short list (<= pool): the bound is inert, and the strongest N win outright
    tt_short = np.linspace(20.0, 120.0, SEARCH_POOL_MULTIPLE * n)
    strong_high = np.arange(len(tt_short), dtype=float)      # strongest at high Q
    short = PeakList.from_positions(tt_short, LAM, intensity=strong_high)
    sel = search_line_order(short, spec)
    assert np.array_equal(np.sort(sel), np.sort(np.argsort(-strong_high)[:n]))

    # long list: the driven set stays inside the pool's Q ceiling
    tt_long = np.linspace(20.0, 150.0, 8 * n)
    long = PeakList.from_positions(tt_long, LAM,
                                   intensity=np.arange(len(tt_long), dtype=float))
    q = long.q()
    ceiling = np.sort(q)[SEARCH_POOL_MULTIPLE * n - 1]
    assert q[search_line_order(long, spec)].max() <= ceiling


# ----------------------------------------------------------------------
# WP-1040 — engine C, iterative SVD
#
# Its properties are not the other two engines': it is **stochastic**, it needs
# no tolerance to search with, and its silence is weaker evidence than an
# exhaustive engine's even when it completes.  So the rows below test recovery
# (the shared job), reproducibility (its own obligation), and the four rules the
# corpus measured against what the algorithm's structure would suggest.
# ----------------------------------------------------------------------
def assert_finds_lattice(result, true_cell: tuple, *, top: int = 4):
    """The truth is among the top candidates, compared as a **lattice**.

    ``assert_same_lattice`` above compares sorted axes plus volume, which is
    sound for the two engines that quotient their search by ``axis_swaps`` — a
    setting change there is a permutation.  It is **not** sound for this one:
    SVD-Index starts from random metrics and quotients by nothing, so it returns
    whichever setting the solve landed in, and a setting change is a shear rather
    than a permutation.  Measured on the synthetic monoclinic row, the correct
    answer came back as (11.010, 16.408, 8.875, β = 139.70°) — same b, volume
    1037.0 to four figures, and a sorted-axis comparison scores it a miss.  This
    is CLAUDE.md's rule verbatim, in the one place it bites hardest: *a candidate
    cell is a lattice, not a tuple*.
    """
    from rietx.indexing.qspace import af_from_cell as _af
    from rietx.indexing.reduce import same_lattice

    want = _af(tuple(true_cell))
    assert result.candidates, "no candidate at all"
    hits = [c for c in result.candidates[:top]
            if same_lattice(_af(tuple(c.cell)), want)[0]]
    assert hits, (f"none of the top {top} is the true lattice: "
                  f"{[tuple(round(v, 3) for v in c.cell) for c in result.candidates[:top]]}"
                  f" against {true_cell}")


@pytest.mark.parametrize("system", ["cubic", "tetragonal", "hexagonal",
                                    "trigonal"])
def test_svd_recovers_a_known_cell(system):
    """The basic job, per system, because cost goes with the metric's degrees of
    freedom and so does the number of random starts Coelho's Table 3 allots."""
    from rietx.indexing.svd import search_svd

    peaks, true_cell = synthetic_peaks(system)
    result = search_svd(peaks, spec=spec_for(system))
    assert_finds_lattice(result, true_cell, top=1)


@pytest.mark.slow
def test_svd_recovers_a_monoclinic_cell():
    """Four free metric parameters, 200 random starts per volume rung.  Marked
    slow for the same reason the other two engines' monoclinic rows are.

    ~84 s and ~9 000 calls to Table 1 on a 10-core M4, against the 900 s runaway
    guard ``spec_for`` declares — a margin, not a timer (``tests/CLAUDE.md``)."""
    from rietx.indexing.svd import search_svd

    peaks, true_cell = synthetic_peaks("monoclinic")
    result = search_svd(peaks, spec=spec_for("monoclinic"))
    assert_finds_lattice(result, true_cell)


def test_svd_is_reproducible_from_the_seed_it_reports():
    """**The obligation a stochastic engine has and the other two do not.**

    ``SearchSpec.seed`` travels into the result's stats precisely so a run can be
    repeated from what it reported, so the same seed must give the same answer —
    and it must do so across *processes*, which is what rules out ``hash()`` of a
    system name for the per-system stream (python salts string hashes per run, so
    the first version of this engine was irreproducible in exactly the way the
    seed exists to prevent).
    """
    from rietx.indexing.svd import search_svd

    peaks, _cell = synthetic_peaks("tetragonal")
    spec = spec_for("tetragonal", seed=7)
    a = search_svd(peaks, spec=spec)
    b = search_svd(peaks, spec=spec)
    assert a.stats["seed"] == 7.0
    assert [c.cell for c in a.candidates] == [c.cell for c in b.candidates]


def test_the_volume_window_brackets_the_truth_and_never_excludes_it():
    """WP-1040's own contribution: Coelho's N_c/N_o gate, read as a bound on
    **volume** rather than a per-trial verdict.

    N_c is proportional to V at fixed Q_max, system and centring, so one probe
    measures κ = N_c/V and the gate becomes ``V ∈ [N_o/3κ, 4N_o/κ]``.  Measured
    on all nine of the WP's corpus datasets it contains the true volume every
    time, and placing the ladder inside it is most of why the engine costs
    seconds.  The second assertion is the one that matters more: **a search bound
    may not exclude the true cell** (WP-1019's envelope lesson), so a probe that
    learns nothing must widen to everything rather than guess.
    """
    from rietx.crystallography.lattice import cell_volume
    from rietx.indexing.svd import volume_window

    for system in ("cubic", "tetragonal", "hexagonal", "trigonal"):
        peaks, true_cell = synthetic_peaks(system)
        spec = spec_for(system)
        q = peaks.q()[search_line_order(peaks, spec)]
        lo, hi = volume_window(len(q), system, "P", float(q.max()))
        v = cell_volume(*true_cell)
        assert lo <= v <= hi, f"{system}: {v:.1f} outside [{lo:.1f}, {hi:.1f}]"

    # no usable probe ⇒ no opinion, rather than a window that could exclude
    assert volume_window(20, "cubic", "P", 0.0) == (0.0, float("inf"))


def test_nc_counts_distinct_lines_because_an_hkl_count_refuses_the_truth():
    """Table 1's caption says N_c counts "hkl values"; §2's prose says
    "calculated d-spacings".  They disagree and only the prose can be right.

    A powder measures |g|, and a cubic lattice piles many hkl onto each d — so an
    hkl count inflates N_c by the coincidence multiplicity and the gate's
    ``N_c/N_o ≤ 4`` then refuses the *certified* cell outright.  This asserts the
    gap is real on a LaB6-like cell rather than trusting the reading.
    """
    from rietx.indexing.qspace import af_from_cell as _af
    from rietx.indexing.qspace import design_matrix as _dm
    from rietx.indexing.svd import NC_NO_HI, _predicted

    peaks, true_cell = synthetic_peaks("cubic")
    spec = spec_for("cubic")
    q = peaks.q()[search_line_order(peaks, spec)]
    basis = metric_basis("cubic")
    af = _af(true_cell)

    lines, _hkl = _predicted(af, basis, "P", float(q.max()))
    hkl_all = trial_hkl(int(np.ceil(true_cell[0] * np.sqrt(q.max()))) + 1, "P")
    q_all = _dm(hkl_all) @ af
    n_hkl = int(np.count_nonzero((q_all > 0.0) & (q_all <= q.max())))

    assert n_hkl > NC_NO_HI * len(q), "the trap this reading avoids is not present"
    assert len(lines) <= NC_NO_HI * len(q)
    assert len(lines) < n_hkl


def test_one_line_beyond_the_lattice_needs_the_trim_retry():
    """Rule 4, and the failure simulated data cannot show.

    The qarr corundum list opens at 5.17° 2θ where the pattern itself starts at
    5.00° — an edge artifact 3.9× beyond the longest d the lattice can produce.
    ``W = d_o⁴·|Δ2θ|·I_o`` then weights it ~10⁴ above the shortest line, the solve
    answers with a hugely elongated axis, and the N_c gate kills the call: 0
    convergences in 4000 random starts, against 3293 with that one line removed.
    Coelho's own impurity test places impurities within 1.5× the largest observed
    d, so it never reaches this case.

    Asserted here where it is deterministic — started **at** the truth, the loop
    cannot hold it with the wild line in and can with the trim budget on.
    """
    from rietx.indexing.qspace import af_from_cell as _af
    from rietx.indexing.reduce import same_lattice
    from rietx.indexing.svd import svd_iterate

    system = "cubic"
    _sg, true_cell, tt_max, _b, _v = CASES[system]
    # one line at three times the longest d the lattice allows
    peaks, _c = synthetic_peaks(system, impurities=(6.0,))
    spec = spec_for(system)
    sel = search_line_order(peaks, spec)
    q, tt = peaks.q()[sel], peaks.two_theta()[sel]
    inten, sig = peaks.intensity()[sel], peaks.q_esd()[sel]
    basis = metric_basis(system)
    af_true = _af(true_cell)

    loose = svd_iterate(af_true, q, tt, inten, basis, "P", LAM, sigma=sig,
                        trim=0)
    tight = svd_iterate(af_true, q, tt, inten, basis, "P", LAM, sigma=sig,
                        trim=1)
    assert tight.converged and same_lattice(tight.af, af_true)[0]
    assert not (loose.converged and same_lattice(loose.af, af_true)[0]), (
        "the wild line no longer breaks the unbudgeted loop — if the weighting "
        "changed, re-measure rule 4 rather than deleting this row")


# ----------------------------------------------------------------------
# WP-1040 task 3 — Coelho §2.3's zero-error column and §2.4's three passes
# ----------------------------------------------------------------------
def _shifted_case(system: str, ze: float):
    """A synthetic list with a constant zero error injected into every position.

    Injected in **2θ**, which is what a diffractometer zero error is; the column
    under test lives in Q, and whether those are the same statement to first
    order is the whole question.  Positions stay otherwise exact, so a failure
    here is the *model* and never the noise (``synthetic_peaks``).
    """
    peaks, true_cell = synthetic_peaks(system, esd_deg=1e-9)
    return (PeakList.from_positions(peaks.two_theta() + ze, LAM,
                                    two_theta_esd=1e-9), true_cell)


def test_the_zero_error_column_is_the_derivative_of_q_by_two_theta():
    """Coelho eq. (6) and ``q_of_two_theta`` must be the same first-order claim.

    Eq. (6) is derived by expanding ``sin²(θ + Ze·π/360)``, so its coefficient
    ``(π/360)·(4/λ²)·sin 2θ`` should be exactly ∂Q/∂(2θ) in degrees — the
    ``(π/90)·sin(2θ)/λ²`` that ``refine_candidate`` carries a note about, since
    ``4·π/360 = π/90`` and the classic slip is π/180.  Checked against a central
    difference rather than against the algebra, because the algebra is what is
    in doubt: they agree to 5e-10 relative over 10-90° 2θ.
    """
    from rietx.indexing.qspace import q_of_two_theta
    from rietx.indexing.svd import zero_error_column

    tt = np.linspace(10.0, 90.0, 9)
    h = 1e-5
    fd = (q_of_two_theta(tt + h, LAM) - q_of_two_theta(tt - h, LAM)) / (2 * h)
    assert zero_error_column(tt, LAM) == pytest.approx(fd, rel=1e-8)


@pytest.mark.parametrize("ze", [0.10, 0.05, -0.08])
def test_a_zero_error_is_absorbed_by_one_pass_and_removed_by_three(ze):
    """Rule 5: the column does not help the search converge, it makes a
    converged answer *correct*.

    Started **at** the truth so the search is out of the question and only the
    modelling is measured.  One pass has no way to express a shift, so it puts
    the shift into the axes — 3.5 % away from the true lattice at Ze = 0.10°,
    which every equality test in the package calls a different lattice — while
    §2.4's three passes return it to ~1e-4 and report the shift to about 1 %.

    This is the same fact the package states one rank up as *a cell found under
    a widened window has absorbed the shift* (``engines.refine_with_shift``,
    +1400 ppm measured on corundum).  Here it is the search's own inner loop
    rather than the acceptance fit, and the remedy is Coelho's, not ours.
    """
    from rietx.indexing.qspace import af_from_cell as _af
    from rietx.indexing.reduce import equal_reduced, reduced_af
    from rietx.indexing.svd import svd_iterate, svd_trial

    system = "monoclinic"
    peaks, true_cell = _shifted_case(system, ze)
    spec = spec_for(system)
    sel = search_line_order(peaks, spec)
    q, tt = peaks.q()[sel], peaks.two_theta()[sel]
    inten, sig = peaks.intensity()[sel], peaks.q_esd()[sel]
    basis = metric_basis(system)
    af_true = _af(true_cell)

    one = svd_iterate(af_true, q, tt, inten, basis, "P", LAM, sigma=sig)
    three = svd_trial(af_true, q, tt, inten, basis, "P", LAM, sigma=sig)

    # the shift is measured, and signed as eq. (6) signs it
    assert three.ze == pytest.approx(ze, rel=0.05)
    # and the lattice comes back with it
    assert equal_reduced(reduced_af(three.af), reduced_af(af_true))[0], (
        f"three passes left the lattice wrong at Ze = {ze}")
    assert not equal_reduced(reduced_af(one.af), reduced_af(af_true))[0], (
        "one pass no longer absorbs the shift — if the weighting or the "
        "acceptance changed, re-measure rule 5 rather than deleting this row")


def test_the_first_pass_carries_no_zero_error_and_no_impurity_cut():
    """§2.3 and §2.4 both turn on *ordering*, so the ordering is the assertion.

    Coelho's reason is one sentence used twice: Ze *"as returned by SVD is often
    too large … due to grossly incorrect hkl assignments in the early
    iterations"*, and the ``d_o²`` weighting *"reduces the chances of getting
    close to the correct solution"* if assigned immediately.  Both refinements
    are things a caller may only do once the assignment is roughly right, so
    with both switched off :func:`svd_trial` must be exactly one call to Table 1
    — not merely similar to one.
    """
    from rietx.indexing.qspace import af_from_cell as _af
    from rietx.indexing.svd import svd_iterate, svd_trial

    system = "tetragonal"
    peaks, true_cell = synthetic_peaks(system)
    spec = spec_for(system)
    sel = search_line_order(peaks, spec)
    q, tt = peaks.q()[sel], peaks.two_theta()[sel]
    inten, sig = peaks.intensity()[sel], peaks.q_esd()[sel]
    basis = metric_basis(system)
    af0 = _af((4.0, 4.0, 9.0, 90.0, 90.0, 90.0))

    one = svd_iterate(af0, q, tt, inten, basis, "P", LAM, sigma=sig)
    bare = svd_trial(af0, q, tt, inten, basis, "P", LAM, sigma=sig,
                     zero_error=False, cut_deg=None)
    assert bare.af.tolist() == one.af.tolist()
    assert (bare.converged, bare.iterations, bare.why, bare.ze) == (
        one.converged, one.iterations, one.why, 0.0)


def test_the_measured_zero_error_never_writes_the_reported_cell():
    """A shift measured **without an attribution** may size a window and nothing
    more — ``effective_shift_allowance``'s rule, applied to this engine's own number.

    Coelho's column is the ``constant`` template by construction, and WP-1038
    measured that ``constant`` and ``cos_theta`` concentrate within one pair of
    each other on real data: the magnitude is knowable and the cause is not.  So
    the engine reports its Ze in the stats and leaves the cell on the same
    footing as the other two engines' — shift-absorbed unless the *caller*
    declares a template, which is the one path ``refine_with_shift`` owns.

    Asserted as a **difference**, not as a threshold: both runs find the same
    lattice, and the question is only which of them still has the shift in its
    axes.  A binary "the plain one is not the true lattice" would be asserting
    that the absorbed error happens to exceed ``CELL_EQUALITY_RELATIVE``, which
    is a coincidence of this fixture's shift and this system's degrees of freedom
    rather than the rule under test — measured, a 0.05° shift on a 2-parameter
    tetragonal metric absorbs to well inside 0.5 %.
    """
    from rietx.indexing.svd import search_svd

    system = "tetragonal"
    injected = 0.05
    peaks, true_cell = _shifted_case(system, injected)
    plain = search_svd(peaks, spec=spec_for(system, shift_allowance_deg=0.06))
    declared = search_svd(peaks, spec=spec_for(system, shift_allowance_deg=0.06,
                                               shift_template="constant"))
    assert plain.candidates and declared.candidates

    # the engine measured a shift and said so, whether or not it was asked to
    for res in (plain, declared):
        ze = res.stats.get(f"{system}.ze_deg")
        assert ze == pytest.approx(injected, abs=0.02), res.stats

    # ...and only the run that declared a template has it in the cell
    assert plain.candidates[0].fit.shift_template is None
    assert declared.candidates[0].fit.shift_template == "constant"
    assert declared.candidates[0].fit.shift_coefficient == pytest.approx(
        injected, abs=0.01)
    assert_finds_lattice(declared, true_cell, top=1)

    def _off(cand):
        return max(abs(c / t - 1.0) for c, t in zip(cand.cell[:3],
                                                    true_cell[:3]))

    assert _off(declared.candidates[0]) < 0.2 * _off(plain.candidates[0]), (
        f"declared {_off(declared.candidates[0]):.2e} against plain "
        f"{_off(plain.candidates[0]):.2e} — the undeclared run is supposed to "
        "carry the shift in its axes, which is what INDEX_SHIFT_ALLOWANCE warns "
        "about and what refine_with_shift exists to undo")
