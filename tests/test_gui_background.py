"""``GET /api/background``: the background curve and its band (WP-2129).

The band is the esd of the background curve through the whole covariance
(``gui/background.py``'s docstring has the derivation). These tests hold it to
an independent computation (a plain inverse of the normal matrix and the
background's own design rows), to the two consequences a reader relies on
(a held term carries no variance; a free parameter that trades against the
background widens it), to the absent-rather-than-zero rule, and to the route's
contract: nothing written, 409 while a run is in flight, packed on the wire.
The ``hold`` arm of ``PATCH /api/params`` is the hold verb the tab presses.
"""

from __future__ import annotations

import hashlib
import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import numpy as np
import pytest

from rietx.examples import build_example
from rietx.gui import GuiSession, background, build_server, preview
from rietx.gui.session import GuiError
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.optimize.statistics import berar_lelann_factor
from rietx.schemas.instrument import BackgroundPSpline
from rietx.viz.packed import MEDIA_TYPE, unpack

pytestmark = pytest.mark.xdist_group("gui-background")


@pytest.fixture(scope="module")
def fap(tmp_path_factory):
    project = build_example("fap", tmp_path_factory.mktemp("background-fap"))
    project.fit()
    return project


def _unfitted(tmp_path_factory, name="fap"):
    return build_example(name, tmp_path_factory.mktemp(f"background-{name}"))


def _independent(project) -> np.ndarray:
    """f·√(gᵀ Cov g) with Cov a plain inverse and g the design rows."""
    model = preview._base(project).model
    table = background._free_table(project)
    x = table.x0()
    jac = _make_jacobian(model, table)(x)
    resid = _make_residual(model, table)(x)
    n = len(model.tt)
    chi2 = resid[:n] @ resid[:n] / (n - jac.shape[1])
    cov = chi2 * np.linalg.inv(jac.T @ jac)
    g = np.zeros((n, len(table.free_paths)))
    for k, path in enumerate(table.free_paths):
        if path in model.bkg_paths:
            g[:, k] = model.bkg_design[model.bkg_paths.index(path)]
    return berar_lelann_factor(resid[:n]) * np.sqrt(np.einsum("ni,ij,nj->n", g, cov, g))


def _digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            h.update(str(path.relative_to(root)).encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def test_the_band_is_the_curve_s_esd_through_the_whole_covariance(fap):
    answer = background.answer(fap)
    esd = answer.arrays["band_esd"]
    assert answer.header["band_absent"] is None
    assert answer.header["n_background_free"] == 6
    assert answer.header["n_other_free"] > 0
    np.testing.assert_allclose(esd, _independent(fap), rtol=1e-7)
    # the curve the band is drawn about is the model's background at the head
    model = preview._base(fap).model
    table = background._free_table(fap)
    np.testing.assert_array_equal(answer.arrays["y_background"],
                                  model.background(table.decode(table.x0())))
    np.testing.assert_array_equal(answer.arrays["y_obs"], model.y_obs)


def test_the_header_quotes_the_terms_and_the_statistics(fap):
    header = background.answer(fap).header
    assert header["kind"] == "chebyshev"
    assert [t["path"] for t in header["terms"]] == [
        f"instrument.background.c{n}" for n in range(6)]
    assert all(t["vary"] and not t["held"] for t in header["terms"])
    assert header["esd_inflation"] >= 1.0 and header["chi2_red"] > 0
    assert header["head"] == fap.refinement._head_id


def test_a_held_term_has_no_column_and_all_held_is_absent(tmp_path_factory):
    project = _unfitted(tmp_path_factory)
    free = background.answer(project)
    project.refinement.hold("instrument.background.c3")
    held = background.answer(project)
    assert held.header["head"] != free.header["head"]
    assert held.header["n_background_free"] == free.header["n_background_free"] - 1
    assert next(t for t in held.header["terms"]
                if t["path"].endswith("c3"))["held"]
    np.testing.assert_allclose(held.arrays["band_esd"], _independent(project), rtol=1e-7)
    project.refinement.hold("instrument.background.*")
    none = background.answer(project)
    assert none.header["band_absent"] == "no free background term"
    assert "band_esd" not in none.arrays
    assert len(none.arrays["y_background"]) == len(none.arrays["two_theta"])


def test_a_free_scale_widens_the_band(tmp_path_factory):
    """Marginal against conditional: the same curvature with the phase scale's
    column in it can only widen the background block, so once the change in
    degrees of freedom is taken out with χ²_red the band grows everywhere."""
    project = _unfitted(tmp_path_factory)
    project.refinement.set_vary("phases.0.scale", True)
    marginal = background.answer(project)
    project.refinement.set_vary("phases.0.scale", False)
    conditional = background.answer(project)
    assert marginal.header["n_free"] == conditional.header["n_free"] + 1
    m2 = marginal.arrays["band_esd"] ** 2 / marginal.header["chi2_red"]
    c2 = conditional.arrays["band_esd"] ** 2 / conditional.header["chi2_red"]
    assert np.all(m2 >= c2 * (1 - 1e-9))
    assert np.median(m2 / c2) > 1.01


def test_a_stiffer_p_spline_narrows_the_band(tmp_path_factory):
    """The penalty rows are in J, so a larger λ constrains the curve more."""
    project = _unfitted(tmp_path_factory)
    r = project.refinement
    tt = preview._base(project).model.tt
    medians = []
    for lam in (1e-2, 1e4):
        instrument = r.instrument.model_copy(deep=True)
        instrument.background = BackgroundPSpline.for_range(
            float(tt[0]), float(tt[-1]), lambda_smooth=lam)
        r.edit(instrument=instrument)
        answer = background.answer(project)
        assert answer.header["kind"] == "pspline"
        assert answer.header["lambda_smooth"] == lam
        assert answer.header["lambda_units"] == "dimensionless"
        assert answer.header["band_absent"] is None
        medians.append(float(np.median(answer.arrays["band_esd"])))
    assert medians[1] < medians[0]


def test_the_band_writes_nothing(fap):
    r = fap.refinement
    before = _digest(fap.path)
    head = r._head_id
    models = (r.structure.model_dump_json(), r.instrument.model_dump_json())
    background._CACHE.pop(fap, None)
    background.answer(fap)
    assert _digest(fap.path) == before
    assert r._head_id == head
    assert (r.structure.model_dump_json(), r.instrument.model_dump_json()) == models


def test_the_band_while_a_run_is_in_flight_is_a_409(fap, tmp_path):
    session = GuiSession(fap, state_dir=tmp_path)
    session._state = "running"
    try:
        with pytest.raises(GuiError) as excinfo:
            session.background()
        assert excinfo.value.status == 409
    finally:
        session._state = "idle"


def test_the_hold_arm_holds_and_releases(tmp_path_factory, tmp_path):
    project = _unfitted(tmp_path_factory)
    session = GuiSession(project, state_dir=tmp_path)
    path = "instrument.background.c2"
    out = session.params_patch({"hold": {path: True}})
    assert out["changed"]["hold"] == {path: [path]}
    row = next(r for r in out["parameters"] if r["path"] == path)
    assert row["held"] and not row["vary"]
    assert project.refinement.history[project.refinement._head_id].action.kind == "set_hold"
    # release and free in one call: the release runs before the vary flag
    out = session.params_patch({"hold": {path: False}, "vary": {path: True}})
    row = next(r for r in out["parameters"] if r["path"] == path)
    assert not row["held"] and row["vary"]
    with pytest.raises(GuiError, match="instrument.background.c99") as excinfo:
        session.params_patch({"hold": {"instrument.background.c99": True}})
    assert excinfo.value.status == 400
    with pytest.raises(GuiError, match="'hold' map dot-path"):
        session.params_patch({"hold": ["instrument.background.c2"]})


def test_one_round_trip_through_the_real_server(fap, tmp_path):
    session = GuiSession(fap, state_dir=tmp_path)
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02},
                     daemon=True).start()
    port = httpd.server_address[1]
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=60)
        conn.request("GET", "/api/background", headers={"Host": f"127.0.0.1:{port}"})
        response = conn.getresponse()
        status, kind, raw = (response.status, response.getheader("Content-Type"),
                             response.read())
        conn.close()
        assert status == 200 and kind.startswith(MEDIA_TYPE)
        answer = unpack(raw)
        assert set(answer.arrays) == {"two_theta", "y_obs", "y_background", "band_esd"}
        assert json.loads(json.dumps(answer.header))["kind"] == "chebyshev"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_a_pending_hold_is_held_for_that_answer_alone(tmp_path_factory, tmp_path):
    """The rebuilt page's chips (WP-2218): the band a pending hold would give,
    the hold verb's own band to the digit, and nothing written."""
    project = _unfitted(tmp_path_factory)
    session = GuiSession(project, state_dir=tmp_path)
    head = project.refinement._head_id
    free = session.background()
    pending = session.background(["instrument.background.c3"])
    assert project.refinement._head_id == head
    assert pending.header["pending_holds"] == ["instrument.background.c3"]
    assert pending.header["head"] == free.header["head"]
    assert pending.header["n_background_free"] == free.header["n_background_free"] - 1
    # the committed state is what the terms report: the hold is pending
    assert not next(t for t in pending.header["terms"] if t["path"].endswith("c3"))["held"]
    project.refinement.hold("instrument.background.c3")
    applied = session.background()
    np.testing.assert_allclose(pending.arrays["band_esd"], applied.arrays["band_esd"], rtol=1e-12)
    with pytest.raises(GuiError, match="instrument.background.c99") as excinfo:
        session.background(["instrument.background.c3", "instrument.background.c99"])
    assert excinfo.value.status == 400
    # the refusal points at the path that is missing, never at every one sent
    assert excinfo.value.where == ["instrument.background.c99"]


def test_a_pending_glob_hold_is_held_as_the_hold_verb_resolves_it(tmp_path_factory, tmp_path):
    """A pending hold may be a glob, as the hold verb takes one (WP-2218 review):
    the band is the one every matching path held gives, and a glob matching
    nothing is refused by name, as a missing path is."""
    project = _unfitted(tmp_path_factory)
    session = GuiSession(project, state_dir=tmp_path)
    paths = ["instrument.background.c4", "instrument.background.c5"]
    by_glob = session.background(["instrument.background.c[45]"])
    by_paths = session.background(paths)
    np.testing.assert_array_equal(by_glob.arrays["band_esd"], by_paths.arrays["band_esd"])
    assert by_glob.header["pending_holds"] == ["instrument.background.c[45]"]
    with pytest.raises(GuiError, match="phases.9") as excinfo:
        session.background(["phases.9.*"])
    assert excinfo.value.where == ["phases.9.*"]


def test_releasing_a_pending_hold_reuses_the_unheld_answer(tmp_path_factory, tmp_path, monkeypatch):
    """A chip pressed and released costs one band, not two (WP-2218 review):
    the answers at one working state are kept per set of holds."""
    project = _unfitted(tmp_path_factory)
    session = GuiSession(project, state_dir=tmp_path)
    calls = []
    real = background.band_esd
    monkeypatch.setattr(background, "band_esd", lambda *a: calls.append(1) or real(*a))
    free = session.background()
    session.background(["instrument.background.c3"])
    assert session.background() is free
    assert len(calls) == 2
    # a moved working state forgets them all
    project.refinement.hold("instrument.background.c2")
    session.background()
    assert len(calls) == 3


def test_a_type_switch_can_release_the_holds_it_redefines(tmp_path_factory, tmp_path):
    """The instrument edit's ``unhold`` and ``free`` arms (WP-2218 review): the
    Background graph's Type switch releases the Chebyshev's holds first and
    frees the new coefficients after, so the P-spline's ``c2`` starts free
    instead of held at zero under the old name, and so do the ``c6`` and up
    the Chebyshev never had. One refusal leaves everything as it was."""
    project = _unfitted(tmp_path_factory)
    session = GuiSession(project, state_dir=tmp_path)
    project.refinement.hold("instrument.background.c2")
    ins = session.instrument()["instrument"]
    spline = BackgroundPSpline.for_range(20.0, 120.0).model_dump(mode="json")
    head = project.refinement._head_id
    with pytest.raises(GuiError) as excinfo:
        session.instrument_patch({"instrument": {**ins, "background": spline},
                                  "unhold": ["instrument.background.c9"]})
    assert excinfo.value.where == ["unhold"]
    assert project.refinement._head_id == head
    assert project.refinement._user_holds == {"instrument.background.c2"}
    session.instrument_patch({"instrument": {**ins, "background": spline},
                              "unhold": ["instrument.background.*"],
                              "free": ["instrument.background.*"]})
    assert project.refinement._user_holds == set()
    # every coefficient free, c2 and those the Chebyshev never had alike
    rows = [r for r in project.parameters() if r.path.startswith("instrument.background.c")]
    assert len(rows) == len(spline["coefficients"])
    assert all(r.vary and not r.held for r in rows), [r.path for r in rows if not r.vary]


#: Fit ranges the rebuilt graph's Type switch builds a P-spline over: round
#: ones, a span of 12.5 and 22.5 (a half, which Python's round takes to even),
#: one under a step, and the long unround ends of a real pattern.
_RANGES = ((15.0, 130.0), (10.0, 11.0), (10.0, 22.5), (10.0, 27.5), (2.5, 7.5),
           (5.0012345678, 89.9876543211), (3.004, 149.996))
BACKGROUND_FIXTURE = Path(__file__).parent / "data" / "gui" / "background_cases.json"


def _background_corpus() -> dict:
    cases = []
    for lo, hi in _RANGES:
        spline = BackgroundPSpline.for_range(lo, hi).model_dump(mode="json")
        cases.append({"lo": lo, "hi": hi, "breakpoints": spline["breakpoints"],
                      "n_coefficients": len(spline["coefficients"]),
                      "lambda_smooth": spline["lambda_smooth"],
                      "lambda_units": spline["lambda_units"]})
    return {
        "_comment": (
            "Generated by tests/test_gui_background.py from "
            "BackgroundPSpline.for_range; consumed by gui/src/next/background.test.ts, "
            "which holds the rebuilt Background graph's Type switch equal to it. "
            "Do not hand-edit: run `.venv/bin/python -m pytest "
            "tests/test_gui_background.py` to regenerate."),
        "cases": cases,
    }


def test_the_committed_p_spline_corpus_is_current():
    """The Type switch builds a P-spline in TypeScript (WP-2218 review): Python
    owns the construction, so a committed corpus of it is what the vitest
    replays (gui/CLAUDE.md, the fnmatch mechanism). Regenerate and compare."""
    text = json.dumps(_background_corpus(), indent=1) + "\n"
    if not BACKGROUND_FIXTURE.is_file() or BACKGROUND_FIXTURE.read_text(encoding="utf-8") != text:
        BACKGROUND_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        BACKGROUND_FIXTURE.write_text(text, encoding="utf-8")
        raise AssertionError(
            f"{BACKGROUND_FIXTURE.relative_to(Path(__file__).parent.parent)} was stale and "
            "has been rewritten; commit it (the vitest replay reads the committed copy)")
