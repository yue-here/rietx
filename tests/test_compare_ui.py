"""``pxrdref compare`` — the settings-comparison UI.

The load-bearing test here is the **anti-drift** one: the UI's standards must
be the acceptance suites' protocols, not merely similar to them, or every
number it shows is incomparable with the recorded acceptance values (the
"adopting the protocol, not just the numbers" rule in CLAUDE.md).  It is a
field-by-field structural comparison and costs milliseconds — no refinement
runs.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from dataclasses import asdict

import numpy as np
import pytest

from pxrdref import compare_app
from pxrdref.viz import compare as cmp

from .test_acceptance_qpa_roundrobin import DATA as QARR_DATA
from .test_acceptance_qpa_roundrobin import (
    brucite_phase,
    corundum_phase,
    fluorite_phase,
    qarr_instrument,
    qpa_plan,
    zincite_phase,
)
from .test_acceptance_srm660c import build_srm_inputs

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
            assert "absorption" in offered
        else:
            assert "absorption" not in offered
            assert "roughness_suortti" in offered


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
    idx = cmp._decimation_index(tt, [peaks], 2000)

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
    assert np.array_equal(cmp._decimation_index(tt, [tt], 4000), np.arange(50))


# ----------------------------------------------------------------------
# the server
# ----------------------------------------------------------------------
@pytest.fixture
def server(monkeypatch):
    """A live server whose refinements are stubbed — the HTTP plumbing under
    test here, not the physics (which ``test_compare_runs_a_real_standard``
    covers)."""
    calls: list[tuple[str, str]] = []

    def fake_run(standard, variant, *, data_dir=None, max_points=4000):
        calls.append((standard, variant))
        n = 64
        tt = np.linspace(10.0, 70.0, n)
        delta = np.sin(np.arange(n)) * (0.5 if variant != "baseline" else 1.0)
        return cmp.RunRecord(
            standard=standard, variant=variant, status="converged", seconds=0.01,
            rwp=0.1, rp=0.08, gof=1.2, chi2=1.4, n_free=10, n_points=n,
            durbin_watson=1.9, esd_inflation=1.5,
            two_theta=tt.tolist(), y_obs=tt.tolist(), y_calc=tt.tolist(),
            y_background=np.zeros(n).tolist(), delta=delta.tolist(),
            cumulative_chi2=np.cumsum(delta ** 2).tolist())

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


def _post_json(url: str, payload: dict):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as fh:
        return json.loads(fh.read())


def test_server_serves_the_page_and_the_catalog(server):
    base, _ = server
    page = _get(base + "/").decode()
    assert "<title>pxrdref" in page and "plot-cum" in page
    catalog = json.loads(_get(base + "/api/catalog"))
    assert {s["key"] for s in catalog["standards"]} == {s.key for s in cmp.STANDARDS}


def test_server_runs_caches_and_reports(server):
    base, calls = server
    assert _post_json(base + "/api/run",
                      {"standard": "corundum",
                       "variants": ["baseline", "extinction"]})["queued"]

    url = base + "/api/state?standard=corundum&variants=baseline,extinction"
    for _ in range(200):
        state = json.loads(_get(url))
        if len(state["records"]) == 2 and not state["busy"]:
            break
    assert set(state["records"]) == {"baseline", "extinction"}
    assert state["records"]["baseline"]["status"] == "converged"
    assert state["log"]

    # cached: a second request for the same pairs must not re-run anything
    n_before = len(calls)
    _post_json(base + "/api/run",
               {"standard": "corundum", "variants": ["baseline", "extinction"]})
    json.loads(_get(url))
    assert len(calls) == n_before


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
        assert len(record.two_theta) == len(record.delta) > 100
        assert asdict(record)["cumulative_chi2"][-1] > 0.0

    def biso_o(record):
        return next(p["value"] for p in record.parameters
                    if p["path"] == "phases.0.atoms.1.biso")

    assert abs(disp.rwp - base.rwp) < 0.005          # Rwp barely moves…
    assert biso_o(base) < 0.1                        # …and B(O) is absorbing f′
    assert biso_o(disp) > 0.3                        # …until dispersion is on
    assert "DISPERSION_NEGLECTED" in {d["code"] for d in base.diagnostics}
    assert "DISPERSION_NEGLECTED" not in {d["code"] for d in disp.diagnostics}
