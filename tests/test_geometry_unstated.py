"""WP-2015: the declared geometry picks the plan, and a geometry can be unstated.

Four claims, each asked where it is decided.  A hand-built geometry is
``unstated`` and a stored one without the key is still the capillary it was
written as (the schema).  The default plan frees the specimen displacement
with the zero on a Bragg-Brentano instrument and nothing geometry-specific
anywhere else (``resolve_plan``).  A fit on an unstated geometry says so
(``GEOMETRY_UNSTATED``).  And the result lists the instrument facts the fit
held at the package's own value (``RefinementResult.assumed_instrument``).
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.common import STORED_DOCUMENT
from rietx.schemas.instrument import (
    DEBYE_SCHERRER_POLARIZATION,
    EmissionLine,
    Geometry,
    Instrument,
    Source,
)
from rietx.strategy.staged import PLAN_PRESETS, resolve_plan
from tests.test_fitreport_layers import _truth

_OUT = pathlib.Path(__file__).parent / "output"
_DISPLACEMENT = "instrument.geometry.sample_displacement"


def _hand_built() -> Instrument:
    return Instrument(source=Source(lines=[EmissionLine(wavelength=1.5405929)]))


# ------------------------------------------------------------------ the schema
def test_a_hand_built_geometry_is_unstated_and_every_preset_states_one():
    assert Geometry().kind == "unstated"
    assert _hand_built().geometry.kind == "unstated"
    assert Instrument.bragg_brentano().geometry.kind == "bragg_brentano"
    assert Instrument.debye_scherrer(1.0).geometry.kind == "debye_scherrer"
    assert (Instrument.flat_plate_transmission().geometry.kind
            == "flat_plate_transmission")


@pytest.mark.parametrize("field", ["mu_t", "thickness_mm"])
def test_a_flat_specimen_quantity_needs_a_flat_geometry(field):
    """Reflection and transmission apply different factors, so an unstated
    geometry cannot say which one a declared µt means."""
    with pytest.raises(ValueError, match="geometry is unstated"):
        Geometry(**{field: 0.3})


def test_a_stored_document_without_the_key_reads_as_the_capillary_it_was():
    """Every writer writes ``kind``, so only a hand-written file omits it,
    and when it was written an omission meant ``debye_scherrer``."""
    stored = _hand_built().model_dump(mode="json")
    del stored["geometry"]["kind"]
    assert (Instrument.model_validate(stored, context=STORED_DOCUMENT)
            .geometry.kind == "debye_scherrer")
    del stored["geometry"]
    assert (Instrument.model_validate(stored, context=STORED_DOCUMENT)
            .geometry.kind == "debye_scherrer")
    # a caller's own dict is a construction, so it is unstated
    assert Instrument.model_validate(stored).geometry.kind == "unstated"


def test_an_instrument_profile_written_without_a_kind_opens_as_a_capillary(tmp_path):
    """A profile file of the kind a pre-WP-2015 hand or another tool wrote:
    the instrument with no ``kind`` key, read by the stored-document reader."""
    from rietx.io.instrument_profile import load_instrument_profile, save_instrument_profile

    path = tmp_path / "old_profile.json"
    save_instrument_profile(Instrument.debye_scherrer(0.4139), path)
    document = json.loads(path.read_text(encoding="utf-8"))
    holder = document.get("instrument", document)
    holder["geometry"].pop("kind")
    path.write_text(json.dumps(document), encoding="utf-8")
    assert load_instrument_profile(path).geometry.kind == "debye_scherrer"


# ------------------------------------------------------------------ the plan
def _turn_on(plan) -> set[str]:
    return {glob for stage in plan.stages for glob in stage.turn_on}


@pytest.mark.parametrize("mode", ["rietveld", "lebail", "pawley"])
def test_bragg_brentano_frees_the_displacement_with_the_zero(mode):
    """The default name under every mode it runs as, the Le Bail and Pawley
    substitutions included (issue #1233's two structure-free presets)."""
    plan = resolve_plan("mccusker_default", mode, "bragg_brentano")
    stage = next(s for s in plan.stages if "instrument.zero_shift" in s.turn_on)
    assert _DISPLACEMENT in stage.turn_on
    assert stage.name == "zero_disp"
    # the ruling's fence: a calibrated instrument's Kα2 ratio and axial terms
    # stay where the caller put them, so this is not lab_bragg_brentano
    globs = _turn_on(plan)
    assert not any("lines" in g or "axial" in g for g in globs), globs


@pytest.mark.parametrize("geometry", [None, "unstated", "debye_scherrer",
                                      "flat_plate_transmission"])
@pytest.mark.parametrize("mode", ["rietveld", "lebail", "pawley"])
def test_every_other_geometry_runs_the_name_as_it_stands(geometry, mode):
    """B7: with no Bragg-Brentano geometry declared, nothing geometry-specific
    is freed, so the plan is the preset's own, stage for stage."""
    plain = resolve_plan("mccusker_default", mode)
    assert resolve_plan("mccusker_default", mode, geometry) == plain
    assert _DISPLACEMENT not in _turn_on(plain)


@pytest.mark.parametrize("mode", ["rietveld", "lebail", "pawley"])
def test_a_stored_bragg_brentano_default_is_still_named_by_its_preset(mode):
    """The GUI menu and the ``.rxt`` ``plan`` line read the name back off the
    stored spec, which on Bragg-Brentano carries the displacement the bare
    preset lacks: given the project's mode and geometry it is still found."""
    spec = rx.PlanSpec.from_plan(
        resolve_plan("mccusker_default", mode, "bragg_brentano"))
    assert spec.preset_name(mode, "bragg_brentano") == "mccusker_default"


def test_a_plan_object_is_run_as_given():
    """Only a name is resolved: a caller's plan object, the preset's included,
    is the caller's statement and gains nothing."""
    plan = PLAN_PRESETS["mccusker_default"]()
    assert resolve_plan(plan, "rietveld", "bragg_brentano") is plan


# ------------------------------------------------------------------ a fit
@pytest.fixture(scope="module")
def lab():
    return _truth(lo=20.0, hi=100.0, step=0.04, axial=0.0)


def _fit(structure, ins, data, stem, plan="mccusker_default"):
    from rietx.viz.plots import plot_result

    ref = rx.Refinement(structure, ins)
    result = ref.fit(data, plan=plan)
    _OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(_OUT / f"wp2015_{stem}.png"))
    return result


def _codes(result) -> set[str]:
    return {d.code for d in result.diagnostics}


def test_a_bragg_brentano_fit_frees_the_displacement_and_lists_what_it_assumed(lab):
    structure, ins, data = lab
    result = _fit(structure, ins.model_copy(deep=True), data, "bb")
    assert any(_DISPLACEMENT in s.freed for s in result.stages
               if s.name == "zero_disp")
    assert "GEOMETRY_UNSTATED" not in _codes(result)
    # the lab preset's Kα2 ratio, held by this plan, is the package's 0.5;
    # the polarisation is the monochromator's and so is not listed
    assert result.assumed_instrument == {"instrument.source.lines.1.weight": 0.5}


def test_an_unstated_fit_frees_nothing_geometric_and_says_so(lab):
    structure, ins, data = lab
    unstated = Instrument(source=ins.source.model_copy(deep=True),
                          profile=ins.profile.model_copy(deep=True),
                          background=ins.background.model_copy(deep=True))
    result = _fit(structure, unstated, data, "unstated")
    assert not any(_DISPLACEMENT in s.freed for s in result.stages)
    finding = next(d for d in result.diagnostics if d.code == "GEOMETRY_UNSTATED")
    assert finding.level == "warning"
    assert finding.where == ["instrument.geometry.kind",
                             "instrument.geometry.sample_displacement"]
    # a warning for the readers it names: whoever quotes a cell or a phase
    from rietx.schemas.results import level_under
    assert {level_under(finding, p) for p in ("cell", "phase_id")} == {"warning"}
    assert result.assumed_instrument["instrument.geometry.kind"] == "unstated"


def test_a_refined_fact_is_measured_and_never_listed():
    """The capillary preset's 0.99 is listed while held and gone once a stage
    frees it: the record reads the table's held entries, not the instrument."""
    structure, ins, data = _truth(lo=20.0, hi=60.0, step=0.04, axial=0.0)
    cap = Instrument.debye_scherrer(1.5405929)
    cap.profile = ins.profile.model_copy(deep=True)
    cap.background = ins.background.model_copy(deep=True)
    grid = np.asarray(data.two_theta)
    y = np.asarray(rx.Refinement(structure, cap).predict(grid))
    synthetic = rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist())
    plan = rx.RefinementPlan(stages=[rx.Stage("scale", ["phases.*.scale"])])
    held = _fit(structure, cap.model_copy(deep=True), synthetic, "cap_held", plan)
    assert held.assumed_instrument == {
        "instrument.polarization": DEBYE_SCHERRER_POLARIZATION}
    freed = _fit(structure, cap.model_copy(deep=True), synthetic, "cap_freed",
                 rx.RefinementPlan(stages=[rx.Stage(
                     "scale_k", ["phases.*.scale", "instrument.polarization"])]))
    assert freed.assumed_instrument == {}


def test_the_cif_writes_an_unstated_geometry_as_unknown(lab, tmp_path):
    from rietx.io.exporters import write_refinement_cif

    structure, ins, data = lab
    unstated = Instrument(source=ins.source.model_copy(deep=True),
                          profile=ins.profile.model_copy(deep=True),
                          background=ins.background.model_copy(deep=True))
    ref = rx.Refinement(structure, unstated)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"])]))
    path = tmp_path / "unstated.cif"
    write_refinement_cif(result, ref.fitted_structure, ref.fitted_instrument, path)
    text = path.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("_pd_instr_geometry"))
    assert line.split()[-1] == "?"


# ------------------------------------------------- every reader of the name
def test_the_report_resolves_the_name_as_the_fit_did(lab, monkeypatch):
    """``Refinement.report(plan=name)`` feeds the strategy veto the stages that
    ran, the geometry's displacement included, not the bare preset's."""
    import rietx.report

    structure, ins, data = lab
    ref = rx.Refinement(structure, ins.model_copy(deep=True))
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"])]))
    seen = {}
    monkeypatch.setattr(rietx.report, "build_report",
                        lambda result, *, plan, **kw: seen.setdefault("plan", plan))
    ref.report(plan="mccusker_default")
    assert _DISPLACEMENT in _turn_on(seen["plan"])


@pytest.mark.parametrize(("preset", "frees"), [("bragg_brentano", True),
                                               ("unstated", False)])
def test_a_project_stores_the_name_as_the_fit_would_run_it(tmp_path, preset, frees):
    """A project stores the expanded plan and runs it as an object, which no
    longer resolves, so the geometry is read when the name is stored."""
    from rietx.examples import examples_dir

    bb = Instrument.bragg_brentano(radiation="CuKa")
    ins = bb if preset == "bragg_brentano" else Instrument(source=bb.source)
    project = rx.Project.create(tmp_path / "p.rex", pattern=examples_dir() / "FAP.XRA",
                                instrument=ins, plan="mccusker_default")
    assert (_DISPLACEMENT in _turn_on(project.doc.plan.to_plan())) is frees
