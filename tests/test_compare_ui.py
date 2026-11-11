"""``rietx compare`` — the settings-comparison UI.

The load-bearing test here is the **anti-drift** one: the UI's standards must
be the acceptance suites' protocols, not merely similar to them, or every
number it shows is incomparable with the recorded acceptance values (the
"adopting the protocol, not just the numbers" rule in CLAUDE.md).  It is a
field-by-field structural comparison and costs milliseconds — no refinement
runs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import compare_app
from rietx._about import STATE_DIR_ENV
from rietx.schemas.instrument import (
    HUMP_FWHM_MIN,
    BackgroundChebyshev,
    BackgroundFixedPlusChebyshev,
)
from rietx.viz import compare as cmp
from rietx.viz import theme

from .test_acceptance_qpa_roundrobin import DATA as QARR_DATA
from .test_acceptance_qpa_roundrobin import (
    brucite_phase,
    corundum_phase,
    fluorite_phase,
    qarr_instrument,
    qpa_plan,
    zincite_phase,
)
from .test_acceptance_srm660c import _nist_calibrated_plan, build_srm_inputs

DATA_DIR = QARR_DATA.parent


# ----------------------------------------------------------------------
# anti-drift: the UI's protocols are the acceptance protocols
# ----------------------------------------------------------------------
def _dump(model) -> dict:
    return json.loads(model.model_dump_json())


@pytest.mark.parametrize("key, phase_fn", [
    ("corundum", corundum_phase),
    ("zincite", zincite_phase),
    ("fluorite", fluorite_phase),
    ("brucite", brucite_phase),
])
def test_qarr_standards_match_the_acceptance_builders(key, phase_fn):
    """Same phase, same instrument, same staged plan as the round-robin suite."""
    if not QARR_DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    inputs = cmp.STANDARD_BY_KEY[key].build(DATA_DIR)

    # the phase: identical apart from the seeded scale (seed_scales runs in both,
    # but the UI seeds inside build(), so compare everything else)
    got, want = _dump(inputs.structure.phases[0]), _dump(phase_fn())
    got["scale"] = want["scale"] = None
    assert got == want

    assert _dump(inputs.instrument) == _dump(qarr_instrument())
    assert [(s.name, list(s.turn_on), s.seed, s.strain_seed)
            for s in inputs.plan.stages] == \
           [(s.name, list(s.turn_on), s.seed, s.strain_seed)
            for s in qpa_plan().stages]


def test_srm660c_standard_matches_the_acceptance_builder():
    """The NIST protocol — zero held, displacement refined — must be identical."""
    if not (DATA_DIR / "nist_srm660c_100a.cif").exists():
        pytest.skip("SRM 660c dataset not present")
    data, structure, instrument = build_srm_inputs()
    inputs = cmp.STANDARD_BY_KEY["srm660c"].build(DATA_DIR)

    assert _dump(inputs.structure) == _dump(structure)
    assert _dump(inputs.instrument) == _dump(instrument)
    assert np.allclose(inputs.data.two_theta, data.two_theta)
    assert [(s.name, list(s.turn_on), s.seed, s.strain_seed)
            for s in inputs.plan.stages] == \
           [(s.name, list(s.turn_on), s.seed, s.strain_seed)
            for s in _nist_calibrated_plan().stages]
    # the calibrated-goniometer plan: zero_shift must never be freed
    freed = {g for s in inputs.plan.stages for g in s.turn_on}
    assert "instrument.zero_shift" not in freed
    assert "instrument.geometry.sample_displacement" in freed


# ----------------------------------------------------------------------
# registry consistency
# ----------------------------------------------------------------------
def test_capillary_only_variants_are_gated_by_geometry():
    """A flat-plate correction on a capillary (and vice versa) is a schema error,
    so the catalog must never offer the pairing in the first place."""
    for standard in cmp.STANDARDS:
        offered = {v.key for v in cmp.VARIANTS if v.applies_to(standard)}
        if standard.geometry == "debye_scherrer":
            assert "roughness_suortti" not in offered
            assert "roughness_pitschke" not in offered
            assert "flat_plate" not in offered
            assert "absorption" in offered
            assert "capillary_displacement" in offered
        else:
            assert "absorption" not in offered
            assert "capillary_displacement" not in offered
            assert "roughness_suortti" in offered
            assert "flat_plate" in offered


def test_lab6_capillary_standard_matches_the_acceptance_builder():
    """The WP-0508 capillary protocol, pinned to the suite that measures it."""
    if not (DATA_DIR / "11BM_LaB6_660a.fxye").exists():
        pytest.skip("11-BM SRM 660a dataset not present")
    from tests.test_acceptance_capillary import (
        LIMITS,
        _instrument,
        _plan,
        _structure,
    )

    inputs = cmp.STANDARD_BY_KEY["lab6_capillary"].build(DATA_DIR)
    assert _dump(inputs.structure) == _dump(_structure())
    # the acceptance declares the capillary and lets the estimator fill µR in;
    # the UI leaves it off in the baseline and the *variant* sets it, so compare
    # everything except the two capillary fields
    got, want = _dump(inputs.instrument), _dump(_instrument(capillary=True))
    for field in ("mu_r", "capillary_radius_mm", "packing_fraction"):
        got["geometry"][field] = want["geometry"][field] = None
    assert got == want
    assert inputs.two_theta_limits == LIMITS
    assert [(s.name, list(s.turn_on)) for s in inputs.plan.stages] == \
           [(s.name, list(s.turn_on)) for s in _plan().stages]


def test_fap_standard_matches_the_acceptance_builder():
    """The cross-code protocol, pinned to the suite that measures it.

    Sharper here than for the other standards: every field of this one is
    *GSAS's* choice rather than ours — its doublet, its held Caglioti terms,
    its 130° exclusion, its declined dispersion — so a drift would not read as
    wrong, it would read as a different code being compared against.
    """
    if not (DATA_DIR / "FAP.XRA").exists():
        pytest.skip("GSAS-II LabData tutorial dataset not present")
    from tests.test_acceptance_fap import _gsas_protocol_plan, build_fap_inputs

    data, structure, instrument = build_fap_inputs()
    inputs = cmp.STANDARD_BY_KEY["fap"].build(DATA_DIR)

    assert _dump(inputs.structure) == _dump(structure)
    assert _dump(inputs.instrument) == _dump(instrument)
    assert inputs.data.excluded_regions == data.excluded_regions
    assert np.array_equal(inputs.data.intensity, data.intensity)
    assert inputs.two_theta_limits is None
    assert [(s.name, list(s.turn_on)) for s in inputs.plan.stages] == \
           [(s.name, list(s.turn_on)) for s in _gsas_protocol_plan().stages]
    assert inputs.plan.intermediate_ftol == _gsas_protocol_plan().intermediate_ftol


def test_every_standard_declares_which_of_its_files_is_the_measurement():
    """``pattern`` is what a project built from a standard opens, and
    ``reader_options`` is the reader *call* — a pdCIF with a ``_meas`` and a
    ``_calc`` block is a different pattern depending on ``block``.  Both are
    checked against ``build``'s own answer rather than trusted."""
    from rietx.io.readers import read_pattern

    for std in cmp.STANDARDS:
        if not std.available(DATA_DIR):
            continue
        assert std.pattern in std.files, std.key
        declared = read_pattern(DATA_DIR / std.pattern,
                                **{k: v for k, v in std.reader_options})
        built = std.build(DATA_DIR).data
        assert np.array_equal(np.asarray(declared.two_theta),
                              np.asarray(built.two_theta)), std.key
        assert np.array_equal(np.asarray(declared.intensity),
                              np.asarray(built.intensity)), std.key


def test_every_variant_is_reachable_from_some_standard():
    reachable = {v.key for s in cmp.STANDARDS for v in cmp.VARIANTS
                 if v.applies_to(s)}
    assert reachable == {v.key for v in cmp.VARIANTS}


def test_catalog_lists_availability_and_applicable_variants():
    cat = cmp.catalog(DATA_DIR)
    assert {s["key"] for s in cat["standards"]} == {s.key for s in cmp.STANDARDS}
    nac = next(s for s in cat["standards"] if s["key"] == "nac")
    assert "absorption" in nac["variants"]
    assert "roughness_suortti" not in nac["variants"]


def test_variants_are_pure_with_respect_to_the_registry():
    """Applying a variant must not mutate the shared plan objects.

    Several variants append to ``inputs.plan.stages``; if ``build`` returned a
    module-level plan instead of a fresh one, a run would silently inherit the
    previous variant's extra stages and every comparison after the first would
    be against the wrong thing.
    """
    if not QARR_DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    build = cmp.STANDARD_BY_KEY["corundum"].build
    baseline_stages = [s.name for s in build(DATA_DIR).plan.stages]
    dirty = build(DATA_DIR)
    cmp.VARIANT_BY_KEY["roughness_suortti"].apply(dirty)
    cmp.VARIANT_BY_KEY["extinction"].apply(dirty)
    assert [s.name for s in dirty.plan.stages] != baseline_stages
    assert [s.name for s in build(DATA_DIR).plan.stages] == baseline_stages


def test_no_variant_moves_the_channels_a_standard_fits():
    """WP-1461, D8: the page draws every variant over one x.

    It takes the Δχ² panel as a plain subtraction, variant minus reference,
    channel for channel, where the plotly page interpolated one onto the
    other. That is right only while every variant fits the same channels, and
    the channels are the data and the 2θ limits. So a variant may change the
    model and nothing else. The page also refuses a variant whose grid differs
    (`compare-core.mjs`'s `sameGrid`), but that is a message, and this is the
    reason it never shows.
    """
    checked = 0
    for std in cmp.STANDARDS:
        if not std.available(DATA_DIR):
            continue
        base = std.build(DATA_DIR)
        for variant in cmp.VARIANTS:
            if not variant.applies_to(std):
                continue
            inputs = std.build(DATA_DIR)
            variant.apply(inputs)
            where = f"{std.key} / {variant.key}"
            assert inputs.two_theta_limits == base.two_theta_limits, where
            assert np.array_equal(np.asarray(inputs.data.two_theta),
                                  np.asarray(base.data.two_theta)), where
            assert np.array_equal(np.asarray(inputs.data.intensity),
                                  np.asarray(base.data.intensity)), where
            checked += 1
    if not checked:
        pytest.skip("no standard's data is present")


def test_stephens_variant_frees_strain_inside_the_broadening_stage():
    """Not in a stage of its own: a microstrain block locks ``lor_strain``, so a
    later stage would leave the isotropic width unrefined until several
    correlated patterns turn on at once."""
    if not QARR_DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    inputs = cmp.STANDARD_BY_KEY["brucite"].build(DATA_DIR)
    n_before = len(inputs.plan.stages)
    cmp.VARIANT_BY_KEY["stephens"].apply(inputs)
    assert len(inputs.plan.stages) == n_before          # extended, not appended
    stage = next(s for s in inputs.plan.stages if s.name == "sample_broadening")
    assert "phases.*.microstrain.dof.*" in stage.turn_on
    assert stage.strain_seed > 0.0
    assert inputs.structure.phases[0].microstrain is not None


def test_texture_variant_declares_order_four_and_frees_it_last():
    """WP-1960: no axis to guess, and a stage of its own after the structure,
    the place the March-Dollase variant frees r."""
    if not QARR_DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    inputs = cmp.STANDARD_BY_KEY["brucite"].build(DATA_DIR)
    cmp.VARIANT_BY_KEY["texture"].apply(inputs)
    assert inputs.plan.stages[-1].name == "texture"
    assert inputs.plan.stages[-1].turn_on == ["phases.*.texture.*"]
    (phase,) = inputs.structure.phases
    assert phase.texture.order == 4
    assert phase.preferred_orientation is None


# ----------------------------------------------------------------------
# decimation
# ----------------------------------------------------------------------
def test_hump_variant_declares_a_broad_peak_and_frees_it_late():
    """A stage of its own, appended: a free *position* over a pattern whose
    peaks are not yet placed hunts whatever misfit the wrong zero and cell are
    producing, so this cannot ride in ``scale_bkg`` the way the P-spline
    variant's coefficients do.

    The width matters as much as the stage: the declared peak must be broad
    enough that ``HUMP_TOO_NARROW`` is not the variant's own doing.
    """
    if not (DATA_DIR / "11BM_NAC.fxye").exists():
        pytest.skip("11-BM NAC dataset not present")
    inputs = cmp.STANDARD_BY_KEY["nac"].build(DATA_DIR)
    n_before = len(inputs.plan.stages)
    cmp.VARIANT_BY_KEY["hump"].apply(inputs)

    assert len(inputs.plan.stages) == n_before + 1
    stage = inputs.plan.stages[-1]
    assert stage.name == "extra_components"
    assert stage.turn_on == ["instrument.extra_components.*"]

    peaks = inputs.instrument.extra_components
    assert len(peaks) == 1
    lo, hi = inputs.two_theta_limits or (None, None)
    tt = np.asarray(inputs.data.two_theta)
    lo = float(tt.min()) if lo is None else lo
    hi = float(tt.max()) if hi is None else hi
    assert lo < peaks[0].position.value < hi
    assert peaks[0].fwhm.value >= HUMP_FWHM_MIN
    assert peaks[0].height.value > 0.0
    # the baseline must not carry it — the variant is the only difference
    assert cmp.STANDARD_BY_KEY["nac"].build(DATA_DIR).instrument.extra_components \
        == []


def test_fixed_curve_scale_variant_covers_the_range_it_will_be_asked_about():
    """The curve is the pattern's own baseline, so it spans the fit by
    construction — and that is the property worth pinning, because a curve
    shorter than the fitted range is now a refusal rather than a silent clamp
    (WP-1309).  A variant that made ``compile_model`` raise would be a row
    nobody could run.

    The scale is what the row is for: free, seeded at one, floored at zero so a
    double-counted curve cannot reach the s − 1 that would hide it.
    """
    if not (DATA_DIR / "11BM_NAC.fxye").exists():
        pytest.skip("11-BM NAC dataset not present")
    inputs = cmp.STANDARD_BY_KEY["nac"].build(DATA_DIR)
    cmp.VARIANT_BY_KEY["fixed_curve_scale"].apply(inputs)

    bkg = inputs.instrument.background
    assert isinstance(bkg, BackgroundFixedPlusChebyshev)
    assert bkg.scale.vary is True
    assert bkg.scale.value == 1.0 and bkg.scale.min == 0.0
    assert bkg.fixed_source and "arPLS" in bkg.fixed_source

    tt = np.asarray(inputs.data.two_theta)
    lo, hi = inputs.two_theta_limits or (float(tt.min()), float(tt.max()))
    assert len(bkg.fixed_two_theta) == len(tt)
    assert bkg.fixed_two_theta[0] <= lo and bkg.fixed_two_theta[-1] >= hi
    # a baseline rather than the data: positive everywhere, and nowhere near
    # the peak tops (arPLS rides through the noise, so it is not below every
    # single channel and must not be asserted to be)
    curve = np.asarray(bkg.fixed_intensity)
    y = np.asarray(inputs.data.intensity)
    assert np.all(curve > 0.0)
    assert curve.max() < 0.1 * y.max()

    # the baseline must not carry it — the variant is the only difference
    assert isinstance(cmp.STANDARD_BY_KEY["nac"].build(DATA_DIR).instrument.background,
                      BackgroundChebyshev)


def test_capillary_displacement_variant_frees_the_pair_with_the_zero_shift():
    """Beside ``zero_shift``, not in a stage of its own (WP-1073).

    The three span {1, sin2θ, cos2θ}, so freeing the offsets a stage later
    would let the zero shift converge onto whichever of them it can imitate
    and then hold it there — the comparison would be measuring the stage
    order, not the correction.  The variant also has to *supply* R where the
    standard declares none: eq (4) divides by it, so without one the two
    parameters cannot be freed at all.
    """
    if not (DATA_DIR / "11BM_NAC.fxye").exists():
        pytest.skip("11-BM NAC dataset not present")
    inputs = cmp.STANDARD_BY_KEY["nac"].build(DATA_DIR)
    n_before = len(inputs.plan.stages)
    cmp.VARIANT_BY_KEY["capillary_displacement"].apply(inputs)
    assert len(inputs.plan.stages) == n_before          # extended, not appended
    assert inputs.instrument.geometry.goniometer_radius_mm
    stage = next(s for s in inputs.plan.stages
                 if "instrument.zero_shift" in s.turn_on)
    assert "instrument.geometry.capillary_offset_along_beam" in stage.turn_on
    assert "instrument.geometry.capillary_offset_across_beam" in stage.turn_on


# ----------------------------------------------------------------------
# decimation
# ----------------------------------------------------------------------
def test_decimation_keeps_peak_tops_and_the_endpoints():
    """Plain striding would decide "which fit is better" by which variant
    happened to be sampled at a maximum, so the index must keep per-bucket
    extrema of every curve."""
    tt = np.linspace(10.0, 80.0, 20_000)
    peaks = np.zeros_like(tt)
    for centre in (20.0, 33.3, 47.7, 61.1):
        peaks += np.exp(-0.5 * ((tt - centre) / 0.02) ** 2)
    idx = cmp.decimation_index(tt, [peaks], 2000)

    assert len(idx) <= 2200 and len(idx) > 100
    assert idx[0] == 0 and idx[-1] == len(tt) - 1
    assert np.all(np.diff(idx) > 0)
    # every peak top survives
    assert peaks[idx].max() == pytest.approx(peaks.max(), rel=1e-12)
    for centre in (20.0, 33.3, 47.7, 61.1):
        near = np.abs(tt[idx] - centre) < 0.05
        assert peaks[idx][near].max() > 0.9


def test_decimation_is_the_identity_below_the_budget():
    tt = np.linspace(0.0, 1.0, 50)
    assert np.array_equal(cmp.decimation_index(tt, [tt], 4000), np.arange(50))


def _decimation_by_loop(tt, curves, max_points):
    """The implementation before WP-1413, kept as the oracle, not as history.

    Three consumers read the index set — the comparison UI, the GUI's window
    route, and the snapshot — so "faster and nearly the same" is a regression
    and not a trade-off (WP-1413).  This is the bucket loop verbatim, before
    that WP vectorised it.
    """
    n = len(tt)
    if n <= max_points:
        return np.arange(n)
    n_buckets = max(max_points // 2, 1)
    edges = np.linspace(0, n, n_buckets + 1, dtype=int)
    keep = {0, n - 1}
    for y in curves:
        for a, b in zip(edges[:-1], edges[1:]):
            if b > a:
                keep.add(a + int(np.argmin(y[a:b])))
                keep.add(a + int(np.argmax(y[a:b])))
    return np.array(sorted(keep))


def _decimation_cases():
    """(name, tt, curves, max_points) over what a real payload can contain.

    The awkward ones are the point: ``argmin`` keeps the *first* index
    attaining a tie, which a segmented scan has to reproduce deliberately, and
    flat counts, staircases and signed zeros are all ties at scale.  NaN is
    here because ``argmin`` returns its first occurrence while a running
    ``minimum`` propagates it, so the two disagree unless the NaN path is
    written for.
    """
    rng = np.random.default_rng(1413)
    cases = []
    for n in (10, 3999, 4000, 4001, 4165, 7251, 22003):
        tt = np.linspace(5.0, 120.0, n)
        cases.append((f"noise n={n}", tt, [rng.normal(size=n)], 4000))

    n = 22003
    tt = np.linspace(5.0, 120.0, n)
    flat = np.ones(n)
    counts = rng.integers(0, 5, size=n).astype(float)
    stair = np.repeat(np.arange(n // 50 + 1), 50)[:n] * 1.0
    zeros = np.where(rng.random(n) < 0.5, -0.0, 0.0)
    y_obs = rng.gamma(2.0, 30.0, size=n)
    y_calc = y_obs + rng.normal(scale=1.0, size=n)
    delta = rng.normal(size=n)
    nan = y_obs.copy()
    nan[[3, 500, 9000, n - 2]] = np.nan
    inf = y_obs.copy()
    inf[[7, 800]] = np.inf
    inf[[9, 900]] = -np.inf

    cases += [
        ("every value identical", tt, [flat], 4000),
        ("integer-valued counts", tt, [counts], 4000),
        ("integer dtype", tt, [rng.integers(0, 5, size=n)], 4000),
        ("a staircase", tt, [stair], 4000),
        ("signed zeros", tt, [zeros], 4000),
        ("monotone", tt, [np.arange(n) * 1.0], 4000),
        # the snapshot's own three curves, and the budgets around the edges
        ("the snapshot's three curves", tt, [y_obs, y_calc, delta], 4000),
        ("budget of 1", tt, [y_obs, y_calc, delta], 1),
        ("budget of 3", tt, [y_obs, y_calc, delta], 3),
        ("budget of 100", tt, [y_obs, y_calc, delta], 100),
        ("no curves at all", tt, [], 4000),
        ("a python list", tt, [list(y_obs)], 4000),
        ("NaN alone", tt, [nan], 4000),
        ("NaN beside clean curves", tt, [y_obs, nan, delta], 4000),
        ("every value NaN", tt, [np.full(n, np.nan)], 4000),
        ("infinities", tt, [inf], 4000),
    ]
    return cases


@pytest.mark.parametrize("name,tt,curves,max_points", _decimation_cases(),
                         ids=lambda v: v if isinstance(v, str) else "")
def test_decimation_is_the_loop_it_replaced(name, tt, curves, max_points):
    """Element for element, not merely the same length or the same picture.

    WP-1413 replaced 2000 buckets of python with a segmented scan for 8.8-11.9×
    on the three bench patterns.  A plot that disagreed with the comparison UI
    about which points it drew would be a picture of a different fit, so the
    acceptance is equality against the old implementation.
    """
    fast = cmp.decimation_index(tt, curves, max_points)
    slow = _decimation_by_loop(tt, curves, max_points)
    assert np.array_equal(fast, slow), name
    assert fast.dtype == slow.dtype


@pytest.mark.parametrize("filename", ["11BM_NAC.fxye", "11BM_Si640c.xy",
                                      "mg090.fxye", "qarr/cpd-2.prn"])
def test_decimation_is_the_loop_it_replaced_on_real_patterns(filename):
    """The same equality on measured 2θ grids rather than on ``linspace``.

    Synthetic noise ties almost never; a real counting experiment ties
    constantly, and a file whose intensities are integers ties in every flat
    stretch of background.  Those are exactly the buckets where a segmented
    scan and ``argmin`` can pick different indices.
    """
    path = DATA_DIR / filename
    if not path.exists():
        pytest.skip(f"{filename} not present")
    data = rx.read_pattern(path)
    tt = np.asarray(data.two_theta, dtype=np.float64)
    y = np.asarray(data.intensity, dtype=np.float64)
    # a stand-in for the snapshot's three curves: the pattern, something
    # smooth through it, and the weighted difference the fit minimises
    smooth = np.convolve(y, np.ones(21) / 21.0, mode="same")
    delta = (y - smooth) / np.sqrt(np.maximum(y, 1.0))

    for curves in ([y], [y, smooth, delta]):
        fast = cmp.decimation_index(tt, curves, 4000)
        slow = _decimation_by_loop(tt, curves, 4000)
        assert np.array_equal(fast, slow), filename


# ----------------------------------------------------------------------
# the server
# ----------------------------------------------------------------------
N_FAKE = 64


def _fake_record(standard, variant, *, fail=False):
    if fail:
        return cmp.RunRecord.failed(standard, variant, status="failed",
                                    error="RuntimeError: x < y & worse",
                                    seconds=0.01)
    tt = np.linspace(10.0, 70.0, N_FAKE)
    delta = np.sin(np.arange(N_FAKE)) * (0.5 if variant != "baseline" else 1.0)
    return cmp.RunRecord(
        standard=standard, variant=variant, status="converged", seconds=0.01,
        rwp=0.1, rp=0.08, gof=1.2, chi2=1.4, n_free=10, n_points=N_FAKE,
        durbin_watson=1.9, esd_inflation=1.5,
        two_theta=tt, y_obs=100.0 + tt, y_calc=99.0 + tt,
        y_background=np.full(N_FAKE, 5.0), delta=delta,
        cumulative_chi2=np.cumsum(delta ** 2),
        ticks={"corundum": [20.0, 35.5, 52.25]},
        tick_hkl={"corundum": [[0, 1, 2], [1, 0, 4], [0, 2, -4]]},
        diagnostics=[{"level": "info", "code": "X", "where": [],
                      "message": "a < b", "suggestion": ""}],
        parameters=[{"path": "phases.0.cell.a", "value": 4.759, "stderr": 1e-4}])


@pytest.fixture
def server(monkeypatch):
    """A live server whose refinements are stubbed — the HTTP plumbing under
    test here, not the physics (which ``test_compare_runs_a_real_standard``
    covers). A variant named ``fails`` comes back as a failed fit."""
    calls: list[tuple[str, str]] = []

    def fake_run(standard, variant, *, data_dir=None,
                 max_points=cmp.CURVES_CEILING):
        calls.append((standard, variant))
        return _fake_record(standard, variant, fail=variant == "fails")

    monkeypatch.setattr(cmp, "run", fake_run)
    state = compare_app._State(DATA_DIR)
    import http.server

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), compare_app._handler(state))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield base, calls
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=10) as fh:
        return fh.read()


def _get_with_type(url: str) -> tuple[bytes, str]:
    with urllib.request.urlopen(url, timeout=10) as fh:
        return fh.read(), fh.headers["Content-Type"]


def _post_json(url: str, payload: dict):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as fh:
        return json.loads(fh.read())


def _strict(body: bytes):
    """JSON as a browser's ``JSON.parse`` reads it: a bare ``NaN`` is an error."""
    def refuse(name):
        raise ValueError(f"{name} is not JSON, and JSON.parse throws on it")
    return json.loads(body, parse_constant=refuse)


def _ran(base: str, standard: str, variants: list[str]) -> dict:
    _post_json(base + "/api/run", {"standard": standard, "variants": variants})
    url = (base + f"/api/state?standard={standard}&variants=" + ",".join(variants))
    for _ in range(200):
        state = _strict(_get(url))
        if len(state["records"]) == len(variants) and not state["busy"]:
            return state
    raise AssertionError(f"never finished: {state}")


def test_server_serves_the_page_and_the_catalog(server):
    base, _ = server
    page = _get(base + "/").decode()
    assert "<title>rietx" in page and 'id="figure"' in page
    catalog = json.loads(_get(base + "/api/catalog"))
    assert {s["key"] for s in catalog["standards"]} == {s.key for s in cmp.STANDARDS}


def test_the_page_is_files_and_draws_with_the_vendored_chart(server):
    """WP-1461: every file the page loads comes out of the installed package,
    as what it is, and none of it is plotly.

    The page and the chart module are served byte for byte from where the
    wheel keeps them, so the page draws with no network and no optional
    dependency. ``/plotly.js`` was this server's until the page moved to the
    chart module, and is gone with ``viz/plotlyjs.py``.
    """
    from rietx.viz.chart import CHART_DIR, CHART_FILES

    base, _ = server
    page = _get(base + "/").decode()
    served = {**{n: (compare_app.STATIC_DIR / n, t)
                 for n, t in compare_app.STATIC_FILES.items() if n != "index.html"},
              **{n: (CHART_DIR / n, t) for n, t in CHART_FILES.items()}}
    for name, (path, kind) in served.items():
        body, content_type = _get_with_type(f"{base}/{name}")
        assert body == path.read_bytes(), name
        assert content_type == kind, name
        # every one of them is something the page itself asks for
        assert f'"/{name}"' in page or f"'./{name}'" in (
            compare_app.STATIC_DIR / "compare.mjs").read_text(encoding="utf-8"), name
    assert "plotly" not in page.lower()
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base + "/plotly.js")
    assert exc.value.code == 404


def test_the_page_links_the_tokens_and_the_server_emits_them(server):
    """One stylesheet for three surfaces, out of the installed package (WP-1429).

    This page had a literal copy of six of the GUI's chrome tokens, light and
    dark, so a retuned `--accent` moved the GUI and left this page on the old
    one.  The copy is gone: the page links the route and the route renders
    `viz/theme.py`, which is also what `gui/src/tokens.css` is generated from.
    """
    base, _ = server
    page = _get(base + "/").decode()
    assert 'href="/tokens.css"' in page
    assert _get(base + theme.CSS_ROUTE).decode() == theme.tokens_css()


def test_the_page_is_stamped_with_the_theme_the_gui_stored(server, tmp_path,
                                                           monkeypatch):
    """Read at load, because this page has no poll to carry a change on.

    `system` is the *absence* of the attribute rather than a third value: the
    `prefers-color-scheme` block in `tokens.css` is what answers then, and no
    server can see the machine the page is open on.
    """
    base, _ = server
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    assert "<html>" in _get(base + "/").decode()          # nothing chosen
    (state / "settings.json").write_text(
        json.dumps({"ui": {"theme": "dark"}}), encoding="utf-8")
    assert '<html data-theme="dark">' in _get(base + "/").decode()
    (state / "settings.json").write_text(
        json.dumps({"ui": {"theme": "system"}}), encoding="utf-8")
    assert "<html>" in _get(base + "/").decode()


def test_the_only_colours_the_page_still_declares_are_the_ten_variant_hues():
    """What WP-1429 deliberately did not fold, named rather than left quiet.

    A variant's curve needs a *categorical* hue, and the GUI has none to lend:
    its one categorical set is the history graph's five lanes at 72°, and ten
    hues at one lightness and chroma cannot clear the 0.13 floor those five
    were chosen for.  Inventing a ten-colour palette is a WP of its own.

    The `#fff` that inked the filled button left with WP-2200: white on the
    orange accent is 2.06:1 on the dark theme, so the button takes `app.css`'s
    `--accent-ink` fill and `--panel` ink.
    """
    script = (compare_app.STATIC_DIR / "compare.mjs").read_text(encoding="utf-8")
    variant_hues = set(re.findall(r'"(#[0-9a-fA-F]{6})"',
                                  script.split("const COLORS")[1].split("]")[0]))
    assert len(variant_hues) == 10
    literal = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([\d.,\s%]*\)")
    found = set()
    for name in compare_app.STATIC_FILES:
        found |= set(literal.findall(
            (compare_app.STATIC_DIR / name).read_text(encoding="utf-8")))
    assert found - variant_hues == set(), sorted(found - variant_hues)


def test_server_runs_caches_and_reports(server):
    base, calls = server
    state = _ran(base, "corundum", ["baseline", "extinction"])
    assert set(state["records"]) == {"baseline", "extinction"}
    assert state["records"]["baseline"]["status"] == "converged"
    assert state["log"]

    # cached: a second request for the same pairs must not re-run anything
    n_before = len(calls)
    _ran(base, "corundum", ["baseline", "extinction"])
    assert len(calls) == n_before


def test_the_poll_carries_no_curves_and_the_curves_route_carries_every_channel(server):
    """D4: a variant's curves come once, packed, and never on the 700 ms poll.

    The poll carried every ready variant's curves on every tick, 2.96 MB
    for four variants of ``nac`` at 4000 points each, and 45.69 MB at every
    channel of ``lab6_capillary``. Without them it is tens of kB, and each
    variant's arrays arrive once through ``/api/curves`` as float64, every
    digit the fit computed, with the tick rows in the header beside them.
    """
    from rietx.viz.packed import unpack

    base, _ = server
    state = _ran(base, "corundum", ["baseline", "extinction"])
    for summary in state["records"].values():
        assert not set(summary) & {*cmp.CURVES, "ticks", "tick_hkl"}, sorted(summary)
    want = _fake_record("corundum", "extinction")
    body, kind = _get_with_type(
        base + "/api/curves?standard=corundum&variant=extinction")
    assert kind == "application/octet-stream"
    got = unpack(body)
    assert got.header == {"ticks": want.ticks, "tick_hkl": want.tick_hkl}
    assert sorted(got.arrays) == sorted(cmp.CURVES)
    for name in cmp.CURVES:
        assert np.array_equal(got.arrays[name], getattr(want, name)), name
        assert got.arrays[name].dtype == np.float64, name


def test_the_curves_route_has_nothing_before_a_fit_or_after_a_failed_one(server):
    base, _ = server
    for query in ("standard=corundum&variant=baseline",     # not run yet
                  "standard=nope&variant=baseline"):
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(base + "/api/curves?" + query)
        assert exc.value.code == 404, query
    _ran(base, "corundum", ["fails"])
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base + "/api/curves?standard=corundum&variant=fails")
    assert exc.value.code == 404


def test_a_failed_variant_polls_as_json_a_browser_reads(server):
    """A failed fit's statistics are NaN, and ``json.dumps`` writes a bare
    ``NaN`` that ``JSON.parse`` throws on. Before WP-1461 one failed variant
    stopped the page's every poll; now its numbers are ``null`` and its row
    shows the error."""
    base, _ = server
    state = _ran(base, "corundum", ["baseline", "fails"])
    failed = state["records"]["fails"]
    assert failed["error"] == "RuntimeError: x < y & worse"
    assert failed["rwp"] is None and failed["gof"] is None


def test_server_rejects_an_unknown_standard(server):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post_json(base + "/api/run", {"standard": "nope", "variants": ["baseline"]})
    assert exc.value.code == 400


# ----------------------------------------------------------------------
# one real end-to-end run
# ----------------------------------------------------------------------
@pytest.mark.slow
def test_compare_runs_a_real_standard():
    """Zincite baseline vs +dispersion, the WP-0504 result in miniature.

    Rwp barely moves while B(O) goes from ~0.02 to ~0.43 Å² — a displacement
    parameter that had been spending itself on Zn's missing f′.  That is the
    shape of result this whole UI exists to make visible, so it is worth an
    assertion rather than a screenshot.
    """
    if not QARR_DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    base = cmp.run("zincite", "baseline", data_dir=DATA_DIR)
    disp = cmp.run("zincite", "dispersion", data_dir=DATA_DIR)

    for record in (base, disp):
        assert record.status == "converged" and record.error is None
        # every fitted channel, under the ceiling (WP-1461, D4)
        assert len(record.two_theta) == len(record.delta) == record.n_points > 100
        assert asdict(record)["cumulative_chi2"][-1] > 0.0
    # one x for both, so the page's Δχ² is a subtraction (D8)
    assert np.array_equal(base.two_theta, disp.two_theta)

    def biso_o(record):
        return next(p["value"] for p in record.parameters
                    if p["path"] == "phases.0.atoms.1.biso")

    assert abs(disp.rwp - base.rwp) < 0.005          # Rwp barely moves…
    assert biso_o(base) < 0.1                        # …and B(O) is absorbing f′
    assert biso_o(disp) > 0.3                        # …until dispersion is on
    assert "DISPERSION_NEGLECTED" in {d["code"] for d in base.diagnostics}
    assert "DISPERSION_NEGLECTED" not in {d["code"] for d in disp.diagnostics}


# ----------------------------------------------------------------------
# the page is files (WP-1461), checked as the watcher's are
# ----------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_CASES = Path(__file__).with_name("compare_core.test.mjs")


def _node() -> str:
    """Skipped where node is absent, like the rest of the javascript gates: a
    contributor without it is not the audience for these checks, and a hard
    failure would make ``pytest`` need a toolchain the package does not."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    return node


def test_the_page_files_parse_as_javascript():
    """The page was a python string until WP-1461, checked by extracting its
    script block, because a stray escape in a quoted page once cost the
    watcher a whole page while every test stayed green (WP-1402). As files,
    ``node --check`` reads them as the browser does."""
    node = _node()
    for name in compare_app.STATIC_FILES:
        if not name.endswith(".mjs"):
            continue
        done = subprocess.run([node, "--check", str(compare_app.STATIC_DIR / name)],
                              capture_output=True, text=True, check=False)
        assert done.returncode == 0, f"{name}:\n{done.stderr}"


def test_the_pure_half_is_unit_tested():
    """``node --test`` over ``compare-core.mjs``, and a count, since an empty file passes."""
    done = subprocess.run([_node(), "--test", "--test-reporter=tap", str(CORE_CASES)],
                          capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    assert done.returncode == 0, done.stdout + done.stderr
    match = re.search(r"^# pass (\d+)$", done.stdout, re.MULTILINE)
    assert match is not None, done.stdout
    assert int(match.group(1)) >= 8, done.stdout


def test_every_element_the_script_reaches_for_exists():
    """A page split across two files can ask for an id the other has not got,
    and then throws at load with every python test green. ``node --check``
    cannot see it, so the ids are compared (the watcher's test of the same
    name, WP-1430)."""
    script = (compare_app.STATIC_DIR / "compare.mjs").read_text(encoding="utf-8")
    page = (compare_app.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    declared = set(re.findall(r'id="([^"]+)"', page))
    wanted = set(re.findall(r"""\$\(['"]([^'"]+)['"]\)""", script))
    # built as 'head-' + key, so the pattern above cannot see them
    wanted |= {f"head-{key}" for key in ("cum", "diff", "fit")}
    # a guard that stops finding its own subject goes quiet rather than red
    assert len(wanted) > 12, f"the id helper moved; this reads $(): {wanted}"
    assert not wanted - declared, f"compare.mjs reaches for ids index.html has not: {wanted - declared}"


def test_the_pages_files_reach_a_fresh_clone():
    """``*.html`` in ``.gitignore`` took this page's ``index.html`` too, the
    eighth file it has swallowed. Ignored, the wheel would ship a compare page
    whose ``/`` is a 500 while every test here stays green, because the file
    exists on this machine. ``--no-index`` makes git read the rules at all
    (``tests/CLAUDE.md``)."""
    for name in compare_app.STATIC_FILES:
        path = (compare_app.STATIC_DIR / name).relative_to(REPO_ROOT)
        done = subprocess.run(["git", "check-ignore", "--no-index", str(path)],
                              capture_output=True, text=True, check=False,
                              cwd=REPO_ROOT)
        assert done.returncode == 1, f"{path} is gitignored: {done.stdout}"
