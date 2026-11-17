"""Where an improvement lives (WP-1339, issue #219): the cumulative Δχ²
between two fits and its share on the reflections a symmetry-lowering splits.

Every pattern here is synthetic: one fcc Cu phase (a = 3.615 Å, a textbook
value) at λ = 0.4139 Å, Poisson-sampled from the package's own forward model.
The nested pair is cubic ``F m -3 m`` against tetragonal ``I 4/m m m``
(fcc → bct, a_t = a_c/√2), both under one plan, so the tetragonal fit frees
exactly ``phases.0.cell.c`` more and :func:`rietx.report.compare_freed` can
price it.  Issue #219's laboratory pair is not in the repo (the WP's NiO
acceptance waits on permission to ship the pattern); these are the
constructed pair the WP's acceptance names in its place.

Two specimens, each able to fail the other's assertion:

* **genuine** — the specimen *is* tetragonal (c/(a√2) − 1 = 1.5e-3).  The
  improvement has to land on the split reflections.
* **absorbed** — the specimen is cubic, with a reflection-dependent peak shift
  neither model holds: {hhh} pushed up by 0.04° and {h00} down, the sign
  pattern a deformation fault gives an fcc metal (Warren, B. E., 1969,
  *X-ray Diffraction*, Addison-Wesley, ch. 13).  The tetragonal cell can move
  {hhh} against {h00}, which a cubic cell cannot, so it wins on ΔBIC (at
  N/f² as well as at raw N) with a well-determined c — while splitting the
  {h00}-type reflections the specimen does not split, which makes those
  windows *worse*.  That is #219's shape: global statistics for the richer
  model, its gain anti-localised with respect to the freedom it adds.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.report import (
    compare_freed,
    cumulative_chi2,
    cumulative_delta_chi2,
    split_localisation,
)
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase, Structure

pytestmark = pytest.mark.xdist_group("localisation")

WL = 0.4139
A = 3.615
GRID = np.arange(6.0, 32.0 + 1e-9, 0.004)
PEAK = 3.0e3            # counts at the strongest peak, above background
GENUINE_TET = 1.5e-3    # c/(a√2) − 1 of the tetragonal specimen
SHIFT = 0.04            # deg 2θ, the absorbed specimen's {hhh}/{h00} shift
OUT = Path(__file__).parent / "output"


def _cell(a, c, vary):
    return Cell(a=Parameter(value=a, vary=vary, min=0.97 * a, max=1.03 * a),
                b=Parameter(value=a),
                c=Parameter(value=c, vary=vary, min=0.97 * c, max=1.03 * c),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def _cu():
    return Atom(label="Cu", species="Cu", x=Parameter(value=0.0),
                y=Parameter(value=0.0), z=Parameter(value=0.0),
                biso=Parameter(value=0.5, min=0.0, max=10.0))


def _cubic(scale, vary=True):
    return Phase(name="cubic", space_group="F m -3 m", cell=_cell(A, A, vary),
                 atoms=[_cu()],
                 scale=Parameter(value=scale, min=0.0, transform="softplus"))


def _tetragonal(scale, tet, vary=True):
    # volume-preserving to first order, so the seed sits beside the cubic cell
    a_t = A * (1.0 - tet / 3.0) / math.sqrt(2.0)
    c_t = A * (1.0 + 2.0 * tet / 3.0)
    return Phase(name="tetragonal", space_group="I 4/m m m",
                 cell=_cell(a_t, c_t, vary), atoms=[_cu()],
                 scale=Parameter(value=scale, min=0.0, transform="softplus"))


def _instrument():
    ins = rx.Instrument.debye_scherrer(wavelength=WL)
    ins.source.dispersion = None
    ins.profile.w.value = 2.0e-3
    ins.profile.x.value = 5.0e-3
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (300.0, -40.0, 10.0)])
    return ins


def _two_theta(h, k, ell):
    return 2.0 * math.degrees(math.asin(WL * math.sqrt(h * h + k * k + ell * ell) / (2.0 * A)))


def _specimen(phase, shifts=None, seed=20261011):
    """Counts from ``phase``, each reflection in ``shifts`` moved by its value.

    The shift is a smooth displacement field s(2θ), a Gaussian bump of
    0.15° about each named reflection (they are ≥ 1.5° apart here), applied
    as y(2θ) = y₀(2θ − s) on a 0.0005° grid, so a peak moves without
    changing shape.
    """
    s = Structure(phases=[phase])
    ins = _instrument()
    y0 = rx.Refinement(s, ins, history=False).predict(GRID)
    s.phases[0].scale.value *= PEAK / float(np.max(y0) - np.min(y0))
    if shifts:
        fine = np.arange(GRID[0] - 1.0, GRID[-1] + 1.0, 0.0005)
        yf = rx.Refinement(s, ins, history=False).predict(fine)
        field = sum(d * np.exp(-0.5 * ((GRID - _two_theta(*hkl)) / 0.15) ** 2)
                    for hkl, d in shifts.items())
        y = np.interp(GRID - field, fine, yf)
    else:
        y = rx.Refinement(s, ins, history=False).predict(GRID)
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 0.0)).astype(float)
    data = rx.PatternData(two_theta=GRID.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())
    return data, float(s.phases[0].scale.value)


PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("cell", ["phases.*.cell.*", "instrument.zero_shift"]),
    rx.Stage("width", ["instrument.profile.w", "instrument.profile.x"]),
])


def _fit(phase, data, stem):
    ref = rx.Refinement(Structure(phases=[phase]), _instrument(), history=False)
    result = ref.fit(data, plan=PLAN)
    # obs/calc/diff for inspection (tests/output/, gitignored)
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"localisation_{stem}.png"))
    return ref, result


def _pair(stem, data, scale):
    cubic = _fit(_cubic(0.9 * scale), data, f"{stem}_cubic")
    tetra = _fit(_tetragonal(0.9 * scale, 1e-3), data, f"{stem}_tetragonal")
    return cubic, tetra


@pytest.fixture(scope="module")
def genuine():
    data, scale = _specimen(_tetragonal(1.0, GENUINE_TET, vary=False))
    return _pair("genuine", data, scale)


@pytest.fixture(scope="module")
def absorbed():
    shifts = {(1, 1, 1): SHIFT, (2, 2, 2): SHIFT, (2, 0, 0): -SHIFT,
              (4, 0, 0): -SHIFT, (2, 2, 0): SHIFT / 2, (3, 1, 1): -SHIFT / 2}
    data, scale = _specimen(_cubic(1.0, vary=False), shifts)
    return _pair("absorbed", data, scale)


def _tetragonality(result):
    v = {p.path: p.value for p in result.parameters}
    return v["phases.0.cell.c"] / (v["phases.0.cell.a"] * math.sqrt(2.0)) - 1.0


# ----------------------------------------------------------------------
# ask (1): the cumulative Δχ²
# ----------------------------------------------------------------------
def test_cumulative_delta_chi2_is_the_difference_of_the_two_fits_cumulatives(genuine):
    (_, cubic), (_, tetra) = genuine
    prof = cumulative_delta_chi2(cubic, tetra)
    expect = cumulative_chi2(tetra) - cumulative_chi2(cubic)
    np.testing.assert_allclose(prof.cumulative, expect, rtol=0, atol=1e-9 * abs(expect[-1]))
    assert prof.two_theta == cubic.two_theta
    assert prof.n_points == len(cubic.two_theta)
    # the last value is the raw χ² difference each fit's statistics carry
    raw = [r.statistics.chi2 * (r.statistics.n_points - r.statistics.n_free_parameters)
           for r in (cubic, tetra)]
    assert prof.total == pytest.approx(raw[1] - raw[0], rel=1e-9)
    assert prof.total < 0.0          # the tetragonal model fits the tetragonal specimen better


def test_quantiles_are_equal_count_runs_whose_shares_sum_to_one(genuine):
    (_, cubic), (_, tetra) = genuine
    prof = cumulative_delta_chi2(cubic, tetra, n_quantiles=10)
    assert len(prof.quantiles) == 10
    counts = [q.n_points for q in prof.quantiles]
    assert sum(counts) == prof.n_points and max(counts) - min(counts) <= 1
    assert sum(q.share for q in prof.quantiles) == pytest.approx(1.0, abs=1e-12)
    assert sum(q.delta_chi2 for q in prof.quantiles) == pytest.approx(prof.total, rel=1e-12)
    edges = [(q.two_theta_min, q.two_theta_max) for q in prof.quantiles]
    assert all(lo <= hi for lo, hi in edges)
    assert all(edges[i][1] < edges[i + 1][0] for i in range(len(edges) - 1))


def test_a_fit_against_itself_has_no_delta_and_no_share(genuine):
    (_, cubic), _ = genuine
    prof = cumulative_delta_chi2(cubic, cubic)
    assert prof.total == 0.0 and not any(prof.cumulative)
    assert all(q.share is None for q in prof.quantiles)
    loc = split_localisation(cubic, cubic)
    # the cubic model splits nothing of its own
    assert loc.n_split_families == 0 and loc.split_share is None
    assert loc.split_point_share == 0.0


def test_two_patterns_are_refused(genuine, absorbed):
    (_, cubic), _ = genuine
    (_, other), _ = absorbed
    with pytest.raises(ValueError, match="different intensities"):
        cumulative_delta_chi2(cubic, other)
    cut = cubic.model_copy(update={"two_theta": cubic.two_theta[1:],
                                   "y_obs": cubic.y_obs[1:]})
    with pytest.raises(ValueError, match="2θ grids"):
        split_localisation(cubic, cut)


def test_different_sigma_is_refused_like_different_intensities(genuine):
    """σ depends on the declared model (a measured background widens it at
    compile, WP-1309), so two fits of one pattern can disagree at every channel
    by 1/σ_b² − 1/σ_a² with no model change behind it."""
    (_, cubic), (_, tetra) = genuine
    wider = tetra.model_copy(update={"sigma": [1.3 * v for v in tetra.sigma]})
    with pytest.raises(ValueError, match="weight the channels differently"):
        cumulative_delta_chi2(cubic, wider)
    with pytest.raises(ValueError, match="weight the channels differently"):
        split_localisation(cubic, wider)


@pytest.mark.slow
def test_compare_run_stores_the_package_cumulative(monkeypatch):
    """``rietx compare``'s record is what the package computes for the run's own
    result, and equals the lines ``run`` used to hold wherever σ > 0 (``sig()``
    puts √max(y, 1) at a σ ≤ 0, the old line 1.0)."""
    import rietx.report.localisation as loc
    from rietx.viz import compare as cmp

    from .test_compare_ui import DATA_DIR, QARR_DATA

    if not QARR_DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    seen = {}
    real = loc.cumulative_chi2

    def tap(result):
        seen["result"] = result
        return real(result)

    monkeypatch.setattr(loc, "cumulative_chi2", tap)
    record = cmp.run("zincite", "baseline", data_dir=DATA_DIR)
    result = seen["result"]
    assert record.n_points == len(record.two_theta) == len(result.two_theta)
    y_obs, y_calc = np.asarray(result.y_obs), np.asarray(result.y_calc)
    expect = (y_obs - y_calc) / result.sig()
    assert np.array_equal(record.delta, expect)
    assert np.array_equal(record.cumulative_chi2, np.cumsum(expect ** 2))
    sigma = np.asarray(result.sigma)
    assert (sigma > 0.0).all()
    assert np.array_equal(record.delta, (y_obs - y_calc) / sigma)


# ----------------------------------------------------------------------
# ask (2): the share on the split reflections
# ----------------------------------------------------------------------
def test_a_genuine_split_puts_its_improvement_on_the_split_reflections(genuine):
    (_, cubic), (_, tetra) = genuine
    assert _tetragonality(tetra) == pytest.approx(GENUINE_TET, rel=0.1)
    loc = split_localisation(cubic, tetra)
    assert loc.higher_phase == "cubic" and loc.lower_phase == "tetragonal"
    # {200}, {220}, {311}, {400}… split under fcc → bct; {111}, {222} do not
    split = {tuple(h) for f in loc.families if f.splits for h in f.hkls}
    unsplit = {tuple(h) for f in loc.families if not f.splits for h in f.hkls}
    assert (2, 0, 0) in split and (2, 2, 0) in split
    assert (1, 1, 1) in unsplit and (2, 2, 2) in unsplit
    assert loc.n_unmatched == 0
    assert loc.total < 0.0
    # more than half the gain on under a twentieth of the points
    assert loc.split_point_share < 0.05
    assert loc.split_share > 0.5
    assert loc.split_share > 10 * loc.split_point_share
    shares = (loc.split_share, loc.unsplit_share, loc.elsewhere_share)
    assert sum(shares) == pytest.approx(1.0, abs=1e-12)
    assert sum(f.n_points for f in loc.families) >= loc.split_point_share * loc.n_points


def test_an_absorbed_improvement_wins_on_delta_bic_and_loses_on_the_split_reflections(absorbed):
    """Issue #219's shape on a constructed pair: the richer model wins on every
    global statistic, with a well-determined extra parameter, and the
    reflections that parameter splits fit *worse*."""
    (ref_c, cubic), (ref_t, tetra) = absorbed
    freed = compare_freed(ref_c, ref_t)
    assert [p.path for p in freed.freed] == ["phases.0.cell.c"]
    assert freed.delta_bic > 10.0                     # at N/f², not only raw N
    assert freed.delta_bic_raw_n > 100.0
    assert abs(freed.freed[0].t_ratio) > 3.0
    loc = split_localisation(cubic, tetra)
    assert loc.total < 0.0                            # the tetragonal fit is better overall
    assert loc.split_share < 0.0                      # and worse where it splits
    assert loc.unsplit_share > 1.0                    # the gain lives on {hhh}
    # (111) alone gains more than the whole pattern does
    (f111,) = [f for f in loc.families if [1, 1, 1] in f.hkls]
    assert not f111.splits and f111.delta_chi2 < loc.total


def test_the_window_can_be_given_and_widens_the_point_share(genuine):
    (_, cubic), (_, tetra) = genuine
    narrow = split_localisation(cubic, tetra, half_width=0.02)
    wide = split_localisation(cubic, tetra, half_width=0.3)
    assert narrow.split_point_share < wide.split_point_share
    for f in narrow.families:
        assert f.window[1] - f.window[0] == pytest.approx(f.spread + 0.04, abs=1e-12)


def test_an_ambiguous_phase_is_refused_by_name(genuine):
    (_, cubic), (_, tetra) = genuine
    with pytest.raises(ValueError, match="no indexed ticks for phase 'nope'"):
        split_localisation(cubic, tetra, lower_phase="nope")
    two = tetra.model_copy(update={"ticks": {**tetra.ticks, "other": tetra.ticks["tetragonal"]},
                                   "tick_hkl": {**tetra.tick_hkl,
                                                "other": tetra.tick_hkl["tetragonal"]}})
    with pytest.raises(ValueError, match="lower_phase="):
        split_localisation(cubic, two)
    assert split_localisation(cubic, two, lower_phase="other").n_split_families > 0


# ----------------------------------------------------------------------
# review of #904: doublets and coincident reflections (hand-built ticks)
# ----------------------------------------------------------------------
def _with_ticks(result, ticks, hkl):
    return result.model_copy(update={"ticks": {"p": ticks}, "tick_hkl": {"p": hkl}})


def test_a_doublet_is_matched_within_one_emission_line(genuine):
    """A child tick belongs to the parent's image in the *same* line.  At 20°
    the two lines of a parent reflection sit 0.1° apart, so Kα1's upper child
    (+0.06) is nearer the parent's Kα2 tick (+0.10) than its own (0.00)."""
    (_, cubic), (_, tetra) = genuine
    t0 = _two_theta(2, 0, 0)        # on a real peak, so the local width is measured
    parent = _with_ticks(cubic, [t0, t0 + 0.1], [[2, 0, 0], [2, 0, 0]])
    child = _with_ticks(tetra, [t0 - 0.04, t0 + 0.06, t0 + 0.06, t0 + 0.16],
                        [[2, 0, 0], [0, 0, 2], [2, 0, 0], [0, 0, 2]])
    loc = split_localisation(parent, child)
    assert [f.emission_line for f in loc.families] == [0, 1]
    for f in loc.families:
        assert f.n_assigned == 2 and f.splits
        assert f.spread == pytest.approx(0.10, abs=1e-9)
    assert loc.n_split_families == 2 and loc.n_unmatched == 0


def test_coincident_parent_reflections_are_one_family(genuine):
    """333 and 511 of a cubic parent sit at one 2θ: one family carrying both,
    never a second row reporting ``splits=False`` for want of a child."""
    (_, cubic), (_, tetra) = genuine
    t0 = _two_theta(2, 0, 0)
    parent = _with_ticks(cubic, [t0, t0], [[3, 3, 3], [5, 1, 1]])
    child = _with_ticks(tetra, [t0 - 0.03, t0 + 0.03], [[3, 3, 3], [5, 1, 1]])
    loc = split_localisation(parent, child)
    (fam,) = loc.families
    assert sorted(map(tuple, fam.hkls)) == [(3, 3, 3), (5, 1, 1)]
    assert fam.n_assigned == 2 and fam.splits and loc.n_split_families == 1


def test_a_family_straddling_the_range_end_keeps_its_in_range_child(genuine):
    """A parent just below the first channel still owns the child above it.
    Skipping every out-of-range parent counted that child nowhere: neither in
    a family nor in ``n_unmatched`` (#904's review)."""
    (_, cubic), (_, tetra) = genuine
    lo = cubic.two_theta[0]
    t0 = _two_theta(2, 0, 0)        # a real peak, so the local width is measured
    # distinct child labels: a repeated hkl is read as a second emission line
    parent = _with_ticks(cubic, [lo - 0.004, t0], [[2, 0, 0], [2, 2, 0]])
    child = _with_ticks(tetra, [lo - 0.012, lo + 0.004, t0],
                        [[2, 0, 0], [0, 0, 2], [2, 2, 0]])
    loc = split_localisation(parent, child)
    fam, whole = loc.families
    assert not whole.splits
    assert fam.n_assigned == 2 and fam.splits and fam.spread == pytest.approx(0.016)
    assert fam.window[0] < lo and fam.n_points >= 1
    assert loc.n_split_families == 1 and loc.n_unmatched == 0
    assert loc.split_point_share > 0.0


def test_a_family_wholly_outside_the_range_is_not_reported(genuine):
    """The other half of the rule above: no child in range, no row.  Nor is a
    parentless child past the range an unmatched one: the data cannot show it."""
    (_, cubic), (_, tetra) = genuine
    lo = cubic.two_theta[0]
    t0 = _two_theta(2, 0, 0)
    parent = _with_ticks(cubic, [lo - 0.05, t0], [[2, 0, 0], [2, 2, 0]])
    child = _with_ticks(tetra, [lo - 1.0, lo - 0.06, lo - 0.04, t0],
                        [[1, 0, 1], [2, 0, 0], [0, 0, 2], [2, 2, 0]])
    loc = split_localisation(parent, child)
    assert [f.hkls for f in loc.families] == [[[2, 2, 0]]]
    assert loc.n_unmatched == 0 and loc.split_share is None


def test_a_family_whose_children_all_lie_past_the_range_is_windowed_on_its_parent(genuine):
    """The mirror case: the parent in range, both children past its end.  The
    split is still read off the children, and the window stays on data."""
    (_, cubic), (_, tetra) = genuine
    hi = cubic.two_theta[-1]
    t0 = _two_theta(2, 0, 0)
    parent = _with_ticks(cubic, [t0, hi - 0.001], [[2, 2, 0], [2, 0, 0]])
    child = _with_ticks(tetra, [t0, hi + 0.012, hi + 0.03],
                        [[2, 2, 0], [2, 0, 0], [0, 0, 2]])
    loc = split_localisation(parent, child, half_width=0.005)
    whole, fam = loc.families
    assert fam.splits and fam.n_assigned == 2 and fam.n_points >= 1
    assert fam.window == pytest.approx((hi - 0.006, hi + 0.004))
    assert loc.split_share is not None and loc.split_point_share > 0.0
