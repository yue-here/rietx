"""WP-2125 — ``POST /api/preview``, the pattern at values nobody has applied.

Each of the three evaluation paths is chosen where it should be and agrees
with a fresh compile at the values; nothing is written; the refusals are
``set_values``' own; the route 409s while a run is in flight. The fixtures
are the shipped ``fap`` (one phase, axial divergence on) and ``nac`` (two
phases, no axial term) examples, each fitted once with its default plan.
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
from rietx.gui import GuiSession, build_server, preview
from rietx.gui.session import GuiError
from rietx.model.forward import compile_model
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import PeakComponent
from rietx.viz.packed import MEDIA_TYPE, unpack

pytestmark = pytest.mark.xdist_group("gui-preview")


def _fitted(tmp_path_factory, name: str):
    project = build_example(name, tmp_path_factory.mktemp(f"preview-{name}"))
    project.fit()
    return project


@pytest.fixture(scope="module")
def fap(tmp_path_factory):
    return _fitted(tmp_path_factory, "fap")


@pytest.fixture(scope="module")
def nac(tmp_path_factory):
    return _fitted(tmp_path_factory, "nac")


def _fresh(project, edits: dict[str, float]):
    """A compile at the edited values from scratch, and its curve there."""
    r = project.refinement
    structure = r.structure.model_copy(deep=True)
    instrument = r.instrument.model_copy(deep=True)
    table = r._working_table()
    for e in table.entries:
        if e.path in edits:
            e.value = edits[e.path]
    table.refresh_ties()
    table.apply_to_models(structure, instrument)
    model = compile_model(structure, instrument, project.data, mode=project.doc.mode,
                          two_theta_limits=project.doc.two_theta_limits)
    return model, np.asarray(model.evaluate(table.decode(table.x0())))


def _err_sigma(project, edits: dict[str, float]) -> tuple[str, float]:
    """Which path the preview took, and its largest error against a fresh
    compile in units of the pattern's σ."""
    answer = preview.evaluate(project, {"values": edits})
    model, ref = _fresh(project, edits)
    y = answer.arrays["y_calc"]
    assert len(y) == len(ref)
    return answer.header["evaluated"], float(np.max(np.abs(y - ref) / model.sigma))


def _fwhm(project) -> float:
    base = preview._base(project)
    return float(np.median(base.model.phase_peaks(0, base.values)[0][1]))


# ---------------------------------------------------------------- evaluate_parts
@pytest.mark.parametrize("name", ["fap", "nac"])
def test_evaluate_parts_total_is_evaluate_bit_for_bit(name, request):
    project = request.getfixturevalue(name)
    base = preview._base(project)
    y, y_bkg, parts = base.model.evaluate_parts(base.values)
    assert np.array_equal(y, base.model.evaluate(base.values))
    assert np.array_equal(y_bkg, base.model.background(base.values))
    assert len(parts) == len(project.refinement.structure.phases)
    for ip, part in enumerate(parts):
        assert np.array_equal(part, base.model.phase_component(ip, base.values))


def test_evaluate_parts_keeps_the_association_with_a_declared_peak(fap):
    r = fap.refinement
    instrument = r.instrument.model_copy(deep=True)
    instrument.extra_components = [PeakComponent(
        center=Parameter(value=27.0, min=26.6, max=27.4, unit="deg"),
        area=Parameter(value=5.0, min=0.0, unit="counts*deg"))]
    model = compile_model(r.structure, instrument, fap.data, mode=fap.doc.mode,
                          two_theta_limits=fap.doc.two_theta_limits)
    from rietx.params.vector import ParameterTable

    table = ParameterTable(r.structure, instrument)
    values = table.decode(table.x0())
    assert model.peak_components
    y, _, _ = model.evaluate_parts(values)
    assert np.array_equal(y, model.evaluate(values))


# ---------------------------------------------------------------- the three paths
def test_at_the_base_values_the_answer_is_frozen_and_the_last_fit(fap):
    answer = preview.evaluate(fap, {"values": {}})
    assert answer.header["evaluated"] == "frozen"
    ref = np.asarray(fap.refinement.result_.y_calc)
    y = answer.arrays["y_calc"]
    # the closing compile the result came from, at the values it ended on
    assert np.max(np.abs(y - ref)) <= 1e-9 * np.max(np.abs(ref))
    _, fresh = _fresh(fap, {})
    assert np.max(np.abs(y - fresh)) <= 1e-9 * np.max(np.abs(fresh))
    assert answer.header["rwp"] == pytest.approx(fap.refinement.result_.statistics.rwp, rel=1e-9)


@pytest.mark.parametrize("name", ["fap", "nac"])
def test_the_scale_slider_stays_frozen_and_exact(name, request):
    project = request.getfixturevalue(name)
    scale = preview._base(project).values["phases.0.scale"]
    for factor in (0.5, 2.0):
        evaluated, err = _err_sigma(project, {"phases.0.scale": scale * factor})
        assert evaluated == "frozen"
        assert err < 1e-9


def test_a_zero_shift_of_one_fwhm_is_frozen_within_a_twentieth_of_sigma(fap, nac):
    for project in (fap, nac):
        zero = preview._base(project).values["instrument.zero_shift"]
        evaluated, err = _err_sigma(
            project, {"instrument.zero_shift": zero + _fwhm(project)})
        assert evaluated == "frozen"
        assert err < 0.05


def test_a_cell_edit_is_frozen_within_a_twentieth_of_sigma(nac):
    a = preview._base(nac).values["phases.0.cell.a"]
    evaluated, err = _err_sigma(nac, {"phases.0.cell.a": a * 1.0005})
    assert evaluated == "frozen"
    assert err < 0.05


def test_a_width_that_grows_the_windows_is_rewindowed_and_exact(fap):
    w = preview._base(fap).values["instrument.profile.w"]
    evaluated, err = _err_sigma(fap, {"instrument.profile.w": 4 * w})
    assert evaluated == "rewindowed"
    assert err < 1e-9


def test_a_lorentzian_size_from_zero_is_rewindowed_and_exact(nac):
    evaluated, err = _err_sigma(nac, {"phases.0.lor_size": 0.02})
    assert evaluated == "rewindowed"
    assert err < 1e-9


def test_axial_divergence_switched_on_is_rewindowed_and_exact(nac):
    """The frozen model has no FCJ nodes at S/L = 0, so a frozen answer would
    miss the asymmetry outright (516-834 σ, the WP's § Measured)."""
    assert preview._base(nac).values["instrument.geometry.axial_sl"] == 0.0
    evaluated, err = _err_sigma(nac, {"instrument.geometry.axial_sl": 0.025})
    assert evaluated == "rewindowed"
    assert err < 1e-9


def test_a_zero_shift_past_the_reflection_margin_is_recompiled_and_exact(fap):
    zero = preview._base(fap).values["instrument.zero_shift"]
    evaluated, err = _err_sigma(fap, {"instrument.zero_shift": zero + 1.0})
    assert evaluated == "recompiled"
    assert err < 1e-9


# ---------------------------------------------------------------- the answer
def test_the_phases_and_background_sum_to_the_total(nac):
    answer = preview.evaluate(nac, {"values": {}})
    names = answer.header["phases"]
    assert names == [ph.name for ph in nac.refinement.structure.phases]
    assert len(names) == 2
    total = answer.arrays["y_background"] + sum(
        answer.arrays[f"phase_{i}"] for i in range(len(names)))
    np.testing.assert_allclose(total, answer.arrays["y_calc"], rtol=1e-12, atol=1e-9)
    assert set(answer.header["ticks"]) >= set(names)
    for name in names:
        assert len(answer.header["tick_hkl"][name]) == len(answer.header["ticks"][name])


def test_the_values_header_names_the_tied_dependents(fap):
    a = preview._base(fap).values["phases.0.cell.a"]
    answer = preview.evaluate(fap, {"values": {"phases.0.cell.a": a + 1e-4}})
    assert answer.header["values"] == {"phases.0.cell.a": a + 1e-4,
                                       "phases.0.cell.b": a + 1e-4}


# ---------------------------------------------------------------- nothing written
def _digest(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_preview_writes_nothing(fap):
    r = fap.refinement
    before = _digest(fap.path)
    head = r._head_id
    models = (r.structure.model_dump_json(), r.instrument.model_dump_json())
    zero = preview._base(fap).values["instrument.zero_shift"]
    for edits in ({}, {"instrument.zero_shift": zero + 0.05},
                  {"instrument.profile.w": 0.01}, {"instrument.zero_shift": 1.0}):
        preview.evaluate(fap, {"values": edits})
    assert _digest(fap.path) == before
    assert r._head_id == head
    assert (r.structure.model_dump_json(), r.instrument.model_dump_json()) == models
    table = r._working_table()
    base = preview._base(fap)
    assert [e.value for e in table.entries] == base.stored


def test_the_cache_follows_the_head(tmp_path_factory):
    project = _fitted(tmp_path_factory, "nac")
    first = preview.evaluate(project, {"values": {}})
    assert first.header["head"] == project.refinement._head_id
    project.refinement.set_values({"instrument.zero_shift": 0.001})
    second = preview.evaluate(project, {"values": {}})
    assert second.header["head"] == project.refinement._head_id != first.header["head"]
    assert preview._base(project).values["instrument.zero_shift"] == 0.001
    assert second.header["evaluated"] == "frozen"


# ---------------------------------------------------------------- refusals
@pytest.mark.parametrize(("edits", "match"), [
    ({"instrument.nope": 1.0}, "unknown parameter path"),
    ({"phases.0.cell.b": 9.4}, "as an affine tie"),
    ({"phases.0.cell.alpha": 91.0}, "structurally fixed"),
    ({"instrument.profile.w": -1.0}, "outside its bounds"),
    ({"instrument.zero_shift": "0.1"}, "not a finite number"),
    ({"instrument.zero_shift": True}, "not a finite number"),
    ({"instrument.zero_shift": float("nan")}, "not a finite number"),
])
def test_a_refused_value_is_a_400_naming_the_path(fap, edits, match):
    with pytest.raises(GuiError, match=match) as excinfo:
        preview.evaluate(fap, {"values": edits})
    assert excinfo.value.status == 400
    assert excinfo.value.where == sorted(edits)


def test_the_refusal_sentences_are_set_values_own(fap):
    r = fap.refinement
    for edits in ({"phases.0.cell.b": 9.4}, {"instrument.profile.w": -1.0}):
        with pytest.raises(ValueError) as applied:
            r.set_values(edits)
        with pytest.raises(GuiError) as previewed:
            preview.evaluate(fap, {"values": edits})
        assert previewed.value.message == str(applied.value)


def test_a_preview_while_a_run_is_in_flight_is_a_409(fap, tmp_path):
    session = GuiSession(fap, state_dir=tmp_path)
    session._state = "running"
    try:
        with pytest.raises(GuiError) as excinfo:
            session.preview({"values": {"instrument.nope": 1.0}})
        assert excinfo.value.code == "RUN_IN_FLIGHT"
        assert excinfo.value.status == 409
    finally:
        session._state = "idle"


# ---------------------------------------------------------------- the wire
def test_one_round_trip_through_the_real_server(fap, tmp_path):
    session = GuiSession(fap, state_dir=tmp_path)
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02},
                     daemon=True).start()
    port = httpd.server_address[1]
    try:
        def post(body):
            conn = HTTPConnection("127.0.0.1", port, timeout=60)
            conn.request("POST", "/api/preview", body=json.dumps(body).encode(),
                         headers={"Host": f"127.0.0.1:{port}",
                                  "Content-Type": "application/json"})
            response = conn.getresponse()
            out = (response.status, response.getheader("Content-Type"), response.read())
            conn.close()
            return out

        status, kind, raw = post({"values": {"phases.0.scale": 1e-3}})
        assert status == 200 and kind.startswith(MEDIA_TYPE)
        answer = unpack(raw)
        assert answer.header["evaluated"] == "frozen"
        assert set(answer.arrays) == {"two_theta", "y_calc", "y_background", "phase_0"}
        assert len(answer.arrays["y_calc"]) == len(answer.arrays["two_theta"])

        status, _, raw = post({"values": {"phases.0.cell.b": 9.4}})
        assert status == 400
        assert json.loads(raw)["error"]["where"] == ["phases.0.cell.b"]
    finally:
        httpd.shutdown()
        httpd.server_close()
