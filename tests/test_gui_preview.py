"""WP-2125 — ``POST /api/preview``, the pattern at values nobody has applied.

Each of the three evaluation paths is chosen where it should be and agrees
with a fresh compile at the values and the last fit's peak cut (WP-2226); at
the head's values the answer is the fit's own curve; nothing is written; the
refusals are
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
from rietx.model.forward import WINDOW_AREA_TOL, compile_model, recorded_window_tol
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


def _fit_cut(project) -> float:
    """The window fraction the last fit's last stage ran at, read off its
    result rather than through the preview's own reading of the tree."""
    return recorded_window_tol(project.refinement.result_.stages[-1].window_area_tol)


def _fresh(project, edits: dict[str, float]):
    """A compile at the edited values from scratch, at the last fit's peak
    cut, and its curve there."""
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
                          two_theta_limits=project.doc.two_theta_limits,
                          window_area_tol=_fit_cut(project))
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
@pytest.mark.parametrize("name", ["fap", "nac"])
def test_at_the_base_values_the_answer_is_frozen_and_the_last_fit(name, request):
    """The preview compiles at the last fit's peak cut, so before a slider
    moves it draws the fit's own curve and Rwp bit for bit (WP-2226). At
    compile_model's default 0.1 % the curve sat 0.13 % of the strongest peak
    off on fap and the Rwp header 0.13 points."""
    project = request.getfixturevalue(name)
    assert _fit_cut(project) == WINDOW_AREA_TOL
    answer = preview.evaluate(project, {"values": {}})
    assert answer.header["evaluated"] == "frozen"
    res = project.refinement.result_
    assert np.array_equal(answer.arrays["y_calc"], np.asarray(res.y_calc))
    assert answer.header["rwp"] == res.statistics.rwp


@pytest.mark.parametrize("name", ["fap", "nac"])
def test_the_scale_slider_stays_frozen_and_exact(name, request):
    project = request.getfixturevalue(name)
    scale = preview._base(project).values["phases.0.scale"]
    for factor in (0.5, 2.0):
        evaluated, err = _err_sigma(project, {"phases.0.scale": scale * factor})
        assert evaluated == "frozen"
        assert err < 1e-9


def test_a_zero_shift_of_one_fwhm_is_rewindowed(fap, nac):
    """A peak moved inside its frozen window is cut off-centre at 2 %, which
    drifted 0.42-1.26 σ from a fresh compile (WP-2226), so a moved window is
    rewindowed. What is left on fap, 0.0175 σ, is the frozen reflection list
    at the range edge, which no window rule changes."""
    for project, bar in ((fap, 0.05), (nac, 1e-9)):
        zero = preview._base(project).values["instrument.zero_shift"]
        evaluated, err = _err_sigma(
            project, {"instrument.zero_shift": zero + _fwhm(project)})
        assert evaluated == "rewindowed"
        assert err < bar


def test_a_cell_edit_is_rewindowed_and_exact(nac):
    a = preview._base(nac).values["phases.0.cell.a"]
    evaluated, err = _err_sigma(nac, {"phases.0.cell.a": a * 1.0005})
    assert evaluated == "rewindowed"
    assert err < 1e-9


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


def _magnetic_base(size: float) -> preview._Base:
    """A base over the MnF₂ magnetic model, with no project behind it."""
    from tests.test_magnetic_width import _mnf2, _state

    model, table, values = _state(_mnf2(size=size, strain=size))
    sized = preview.forward.window_sizing
    return preview._Base(
        key=(), table=table, stored=[e.value for e in table.entries],
        values=values, model=model, positions=preview._positions(model, values),
        sized=sized(model, values), sized_mag=sized(model, values, component=1),
        lebail=None)


def test_a_magnetic_width_off_zero_is_recompiled():
    """The compile builds no magnetic family at zero widths, so neither the
    frozen windows nor ``rewindow`` can draw the widened magnetic peaks."""
    base = _magnetic_base(0.0)
    assert not base.model.mag_split(0)
    assert preview._choose(base, base.values) == "frozen"
    values = {**base.values, "phases.0.magnetic_lor_size": 0.05}
    assert preview._choose(base, values) == "recompiled"


def test_a_magnetic_family_outgrown_is_recompiled():
    """``rewindow`` keeps the magnetic family's windows, so a width that grows
    past them needs a compile."""
    base = _magnetic_base(0.01)
    assert base.model.mag_split(0)
    assert preview._choose(base, base.values) == "frozen"
    values = {**base.values, "phases.0.magnetic_lor_size": 1.0}
    assert preview._choose(base, values) == "recompiled"


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


def test_the_residuals_are_the_curves_route_s_at_the_last_fit(fap):
    """At the last fit's values the three residuals are the curves route's,
    over the same σ (WP-2128), bit for bit since the preview compiles at the
    fit's own peak cut (WP-2226), so the residual pane does not move when a
    preview starts from there."""
    answer = preview.evaluate(fap, {"values": {}})
    res = fap.refinement.result_
    raw = np.asarray(res.y_obs) - np.asarray(res.y_calc)
    sig = np.asarray(res.sig())
    assert np.array_equal(answer.arrays["delta_raw"], raw)
    np.testing.assert_allclose(answer.arrays["delta"], answer.arrays["delta_raw"] / sig,
                               rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(answer.arrays["cumulative_chi2"],
                               np.cumsum(answer.arrays["delta"] ** 2), rtol=1e-6)
    # and the Rwp in the header is taken over the same σ
    sig = answer.arrays["delta_raw"] / answer.arrays["delta"]
    y = answer.arrays["y_calc"] + answer.arrays["delta_raw"]
    rwp = np.sqrt(np.sum((answer.arrays["delta_raw"] / sig) ** 2) / np.sum((y / sig) ** 2))
    assert rwp == pytest.approx(answer.header["rwp"], rel=1e-9)


def test_the_values_header_names_the_tied_dependents(fap):
    a = preview._base(fap).values["phases.0.cell.a"]
    answer = preview.evaluate(fap, {"values": {"phases.0.cell.a": a + 1e-4}})
    assert answer.header["values"] == {"phases.0.cell.a": a + 1e-4,
                                       "phases.0.cell.b": a + 1e-4}


def test_the_values_header_names_a_formula_tie_s_row(tmp_path_factory):
    """A row a user formula writes is a derived row rather than an affine
    tie, and it moves with the variable it reads."""
    project = build_example("nac", tmp_path_factory.mktemp("preview-formula"))
    r = project.refinement
    biso = preview._base(project).values["phases.0.atoms.0.biso"]
    r.add_variable("half_b", biso / 2)
    r.tie("phases.0.atoms.0.biso", expression="2*half_b")
    answer = preview.evaluate(project, {"values": {"vars.half_b": biso / 2 + 0.1}})
    assert answer.header["values"]["phases.0.atoms.0.biso"] == pytest.approx(biso + 0.2)


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
    cut = _fit_cut(project)
    project.refinement.set_values({"instrument.zero_shift": 0.001})
    second = preview.evaluate(project, {"values": {}})
    assert second.header["head"] == project.refinement._head_id != first.header["head"]
    assert preview._base(project).values["instrument.zero_shift"] == 0.001
    assert second.header["evaluated"] == "frozen"
    # a head that is no stage (an applied slider) keeps the stage's cut above it
    assert preview._base(project).window_area_tol == cut


def test_a_fit_ending_at_another_cut_is_drawn_at_it_after_a_reopen(tmp_path_factory):
    """A last stage run at 0.1 % windows, as a closing stage runs, is drawn at
    0.1 %, and the cut is read off the history, so a reopened project, which
    carries no result, still draws the fit's curve (WP-2226)."""
    from rietx import Stage
    from rietx.project import Project

    project = _fitted(tmp_path_factory, "fap")
    result = project.run_stage(Stage("close", ["phases.0.scale"]),
                               window_area_tol=1e-3)
    assert result.stages[-1].window_area_tol == 1e-3
    reopened = Project.open(project.path)
    assert reopened.refinement.result_ is None
    base = preview._base(reopened)
    assert base.window_area_tol == 1e-3 == base.model.window_area_tol
    answer = preview.evaluate(reopened, {"values": {}})
    assert answer.header["evaluated"] == "frozen"
    assert np.array_equal(answer.arrays["y_calc"], np.asarray(result.y_calc))
    assert answer.header["rwp"] == result.statistics.rwp


def test_a_tree_with_no_stage_is_drawn_at_the_declared_cut(tmp_path_factory):
    project = build_example("fap", tmp_path_factory.mktemp("preview-unfitted"))
    assert preview._base(project).model.window_area_tol == WINDOW_AREA_TOL


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


def test_the_structure_graph_draws_unapplied_values_and_writes_nothing(fap, tmp_path):
    """``POST /api/structure3d`` draws the cell a slider holds (WP-2218), through
    the preview's own refusal, and leaves the project as it found it."""
    session = GuiSession(fap, state_dir=tmp_path)
    r = fap.refinement
    before = _digest(fap.path)
    models = (r.structure.model_dump_json(), r.instrument.model_dump_json())
    a = preview._base(fap).values["phases.0.cell.a"]
    now = session.structure3d(0)
    grown = session.structure3d(0, body={"values": {"phases.0.cell.a": a * 1.01}})
    # hexagonal: b follows a, so the volume grows by 1.01² and c stays
    assert grown["volume"] == pytest.approx(now["volume"] * 1.01 ** 2, rel=1e-9)
    assert grown["lattice"][2] == pytest.approx(now["lattice"][2], rel=1e-12)
    assert session.structure3d(0, body={"values": {}})["volume"] == pytest.approx(
        now["volume"], rel=1e-12)
    with pytest.raises(GuiError, match="unknown parameter path"):
        session.structure3d(0, body={"values": {"phases.0.nope": 1.0}})
    assert _digest(fap.path) == before
    assert (r.structure.model_dump_json(), r.instrument.model_dump_json()) == models
    session._state = "running"
    try:
        with pytest.raises(GuiError) as excinfo:
            session.structure3d(0, body={"values": {}})
        assert excinfo.value.status == 409
        # the drawing of the working state stays open mid-run
        assert session.structure3d(0)["volume"] == pytest.approx(now["volume"])
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
        assert set(answer.arrays) == {"two_theta", "y_calc", "y_background", "phase_0",
                                      "delta", "delta_raw", "cumulative_chi2"}
        assert len(answer.arrays["y_calc"]) == len(answer.arrays["two_theta"])

        status, _, raw = post({"values": {"phases.0.cell.b": 9.4}})
        assert status == 400
        assert json.loads(raw)["error"]["where"] == ["phases.0.cell.b"]
    finally:
        httpd.shutdown()
        httpd.server_close()
