"""WP-1045 — one indexing control surface, two chairs, held by meta-test.

``SearchSpecSpec`` (the pydantic twin of the frozen ``SearchSpec``) lives in
``schemas/indexing.py`` and every chair consumes it: the project document
embeds it (``ProjectDoc.indexing``, which is what the GUI form edits and the
index run reads), and ``index_pattern`` is called with what it maps to.  These
tests are the bijection: a field added to one view and not the other fails
here, not in a user's hands.  There were three chairs until WP-1303 — the JSON
request re-exported the same model (the ``StageSpec`` precedent) — and the
bijection is what said the three could not disagree; deleting a chair removes a
consumer, never the rule.

The GUI form's own half lives in ``gui/src/lib/peaks.test.ts``, replaying the
committed corpus this file writes (``tests/data/gui/index_controls.json``) —
the ``test_gui_fnmatch`` mechanism: python owns the vocabulary, TS proves it
renders it.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from rietx.indexing.engines import (
    CENTRINGS,
    SEARCH_PRESETS,
    SYSTEM_ORDER,
    SearchSpec,
    engine_names,
)
from rietx.schemas.indexing import (
    SHIFT_TEMPLATES,
    IndexingControls,
    SearchSpecSpec,
)

# ----------------------------------------------------------------------
# the bijection: SearchSpecSpec ↔ SearchSpec
# ----------------------------------------------------------------------
#: model fields that are deliberately *not* ``SearchSpec`` fields, each with
#: the reason it rides the model anyway.  Grow this only with a reason.
MODEL_EXTRAS = {
    # an ``index_pattern`` kwarg, not a spec field: the preset *fills in*
    # total_budget_seconds, and recording which name governed the ceiling is
    # the run's job (``spec_notes["preset"]``), not the spec's
    "preset",
}


def test_searchspecspec_mirrors_searchspec_field_for_field():
    """The ``ParameterRow``/``Entry`` pin one surface over: pinned by
    ``dataclasses.fields``, so a field added to either side fails until the
    other has it (or names itself in ``MODEL_EXTRAS`` with a reason)."""
    spec_fields = {f.name for f in dataclasses.fields(SearchSpec)}
    model_fields = set(SearchSpecSpec.model_fields)
    assert model_fields - spec_fields == MODEL_EXTRAS
    assert spec_fields - model_fields == set(), (
        "SearchSpec grew a field the control surface cannot state")


#: one non-default value per model field — ``to_spec`` must carry every one.
#: A field added to the model without a row here fails the coverage assert.
_ROUND_TRIP = {
    "systems": ["tetragonal", "cubic"],
    "centrings": {"cubic": ["P", "I"]},
    "min_d_axis": 2.5,
    "max_d_axis": 11.0,
    "min_volume": 20.0,
    "max_volume": 900.0,
    "n_unindexed": 1,
    "n_search_lines": 18,
    "k_sigma": 2.5,
    "shift_allowance_deg": 0.03,
    "shift_template": "constant",
    "budget_seconds": 12.0,
    "total_budget_seconds": 77.0,
    "preset": "quick",
    "max_candidates": 7,
    "seed": 3,
    "prior_cells": [(4.76, 4.76, 12.99, 90.0, 90.0, 120.0)],
    "prior_spacegroups": ["R -3 c"],
}


def test_to_spec_carries_every_field():
    assert set(_ROUND_TRIP) == set(SearchSpecSpec.model_fields), (
        "a model field has no round-trip row — add one, or to_spec can drop "
        "it silently")
    spec = SearchSpecSpec(**_ROUND_TRIP).to_spec()
    assert spec == SearchSpec(
        systems=("tetragonal", "cubic"), centrings={"cubic": ("P", "I")},
        min_d_axis=2.5, max_d_axis=11.0, min_volume=20.0, max_volume=900.0,
        n_unindexed=1, n_search_lines=18, k_sigma=2.5,
        shift_allowance_deg=0.03, shift_template="constant",
        budget_seconds=12.0, total_budget_seconds=77.0,
        max_candidates=7, seed=3,
        prior_cells=((4.76, 4.76, 12.99, 90.0, 90.0, 120.0),),
        prior_spacegroups=("R -3 c",))


def test_the_models_defaults_are_the_dataclasss_defaults():
    """Two default sets is a drift channel; one line closes it."""
    assert SearchSpecSpec().to_spec() == SearchSpec()
    assert IndexingControls().search == SearchSpecSpec()


# ----------------------------------------------------------------------
# the bijection: IndexingControls ↔ index_pattern's signature
# ----------------------------------------------------------------------
#: ``index_pattern`` parameters that are *call-time inputs*, not settings a
#: chair stores: the data itself, plumbing, and facts another authority owns.
CALL_TIME_INPUTS = {
    "peaks", "data", "instrument",   # the data itself
    "quality",                       # a precomputed report, an optimisation
    "shift_from_pairs",              # the screen's own switch, not a control
    "events", "cancel",              # plumbing
    "two_theta_limits",              # the project document owns this fact
}
#: parameters the controls reach through ``search`` rather than by name
VIA_SEARCH = {"spec", "preset"}
#: controls-field → index_pattern parameter
CONTROL_TO_KWARG = {
    "engines": "engines",
    "validate_candidates": "validate",
    "check_top": "check_top",
    # the specimen's chemistry, a search setting since the 2026-11-02 ruling
    # (WP-2030): it records each candidate's formula units and steers nothing
    "formula": "formula",
    "temperature": "temperature",
}


def test_indexing_controls_cover_index_pattern():
    from rietx.indexing.workflow import index_pattern

    params = set(inspect.signature(index_pattern).parameters)
    assert params == CALL_TIME_INPUTS | VIA_SEARCH | set(
        CONTROL_TO_KWARG.values()), (
        "index_pattern's signature moved; the control surface (and this "
        "test's declared exceptions) must move with it")
    assert set(IndexingControls.model_fields) == (
        {"search"} | set(CONTROL_TO_KWARG))


# ----------------------------------------------------------------------
# the project document
# ----------------------------------------------------------------------
def test_the_project_document_round_trips_the_controls():
    from rietx.schemas.project import ProjectDoc

    doc = ProjectDoc(indexing=IndexingControls(
        search=SearchSpecSpec(**_ROUND_TRIP), engines=["svd"],
        validate_candidates=False, check_top=2, formula="C7H6O2",
        temperature=100.0))
    back = ProjectDoc.model_validate_json(doc.model_dump_json())
    assert back.indexing == doc.indexing

    # a document written before WP-1045 has no key — defaults, not a refusal
    old = json.loads(ProjectDoc().model_dump_json())
    old.pop("indexing")
    assert ProjectDoc.model_validate(old).indexing == IndexingControls()


# ----------------------------------------------------------------------
# the vocabulary validators quote the live registries
# ----------------------------------------------------------------------
@pytest.mark.parametrize("bad,where", [
    ({"systems": ["cubbic"]}, "cubic"),
    ({"centrings": {"cubic": ["R"]}}, "P, I, F"),
    ({"centrings": {"cubic": []}}, "empty"),
    ({"centrings": {"nonagonal": ["P"]}}, "unknown crystal system"),
    ({"shift_template": "cos"}, "cos_theta"),
    ({"preset": "fast"}, "quick"),
])
def test_a_wrong_vocabulary_member_is_refused_with_the_live_list(bad, where):
    with pytest.raises(ValueError, match=where):
        SearchSpecSpec(**bad)


def test_a_wrong_engine_is_refused_with_the_live_list():
    with pytest.raises(ValueError, match="dichotomy"):
        IndexingControls(engines=["dicvol"])


# ----------------------------------------------------------------------
# the specimen's formula (WP-2030 part 3): refused in the CLI's words
# ----------------------------------------------------------------------
#: one row per refusal ``rietx index`` makes: its flags, and the controls
#: block a project file or the GUI form would carry for the same input
_FORMULA_REFUSALS = [
    (["--formula", "Qq2"], {"formula": "Qq2"}),
    (["--formula", "CuSO4.5H2O"], {"formula": "CuSO4.5H2O"}),
    (["--formula", "ZnO", "--temperature", "0"],
     {"formula": "ZnO", "temperature": 0.0}),
    (["--formula", "ZnO", "--temperature", "-5"],
     {"formula": "ZnO", "temperature": -5.0}),
    (["--formula", "ZnO", "--temperature", "inf"],
     {"formula": "ZnO", "temperature": math.inf}),
    (["--formula", "ZnO", "--temperature", "nan"],
     {"formula": "ZnO", "temperature": math.nan}),
    (["--temperature", "100"], {"temperature": 100.0}),
]


def _cli_refusal(flags: list[str], capsys) -> str:
    """The sentence ``rietx index`` refuses ``flags`` with.  It refuses before
    the pattern is read, so the path need not exist."""
    from rietx.cli import main

    with pytest.raises(SystemExit) as stop:
        main(["index", "never-read.xy", "--wavelength", "1.5405929", *flags])
    assert stop.value.code == 2
    return capsys.readouterr().err.rsplit("rietx index: error: ", 1)[1].strip()


def _model_refusal(exc: ValidationError) -> str:
    return str(exc.errors()[0]["msg"]).removeprefix("Value error, ")


@pytest.mark.parametrize("flags,controls", _FORMULA_REFUSALS)
def test_the_controls_refuse_a_formula_in_the_clis_words(flags, controls,
                                                         capsys):
    """One validator, ``check_formula_input``, so the project file and the
    GUI form refuse what the CLI refuses, sentence for sentence."""
    with pytest.raises(ValidationError) as refused:
        IndexingControls(**controls)
    assert _model_refusal(refused.value) == _cli_refusal(flags, capsys)


def _a_project(root: Path):
    import rietx as rx
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import perturbed_models, synthesize

    structure, instrument = perturbed_models()
    file = _write_xye(root.parent / f"{root.stem}.xye", synthesize())
    return rx.Project.create(root, pattern=file, structure=structure,
                             instrument=instrument)


def test_a_project_file_keeps_the_formula_and_refuses_a_bad_one(tmp_path,
                                                                capsys):
    import rietx as rx
    from rietx.project import PROJECT_JSON

    project = _a_project(tmp_path / "formula.rex")
    doc_path = project.path / PROJECT_JSON

    # a file written before the fields existed has no key: it opens with no
    # formula, and opening it leaves its bytes alone
    raw = json.loads(doc_path.read_text(encoding="utf-8"))
    assert raw["indexing"].pop("formula") is None
    assert raw["indexing"].pop("temperature") is None
    doc_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    before = doc_path.read_bytes()
    old = rx.Project.open(project.path)
    assert old.doc.indexing == IndexingControls()
    assert doc_path.read_bytes() == before

    # both fields stored, both read back
    old.doc.indexing = IndexingControls(formula="C7H6O2", temperature=100.0)
    old.save()
    back = rx.Project.open(project.path).doc.indexing
    assert (back.formula, back.temperature) == ("C7H6O2", 100.0)

    # a hand-edited bad value is refused on load, in the CLI's words
    for flags, controls in (_FORMULA_REFUSALS[2], _FORMULA_REFUSALS[-1]):
        raw = json.loads(doc_path.read_text(encoding="utf-8"))
        raw["indexing"].update({"formula": None, "temperature": None,
                                **controls})
        doc_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        with pytest.raises(ValidationError) as refused:
            rx.Project.open(project.path)
        assert _model_refusal(refused.value) == _cli_refusal(flags, capsys)


@pytest.mark.xdist_group("search-controls-chairs")
def test_the_gui_index_run_passes_the_formula(tmp_path, monkeypatch, capsys):
    """The form's block reaches ``index_pattern`` as the CLI hands it over:
    unset is no formula at 298 K, and a set pair arrives as stored.  The GUI's
    settings verb refuses a bad pair with the CLI's sentence."""
    import time

    import rietx.indexing.workflow as workflow
    from rietx.crystallography.atomic_volume import TABLE_TEMPERATURE
    from rietx.gui import GuiSession
    from rietx.gui.session import GuiError

    calls: list[dict] = []

    class Captured(Exception):
        pass

    def capture(*_args, **kwargs):
        calls.append(kwargs)
        raise Captured

    monkeypatch.setattr(workflow, "index_pattern", capture)
    session = GuiSession(_a_project(tmp_path / "gui.rex"),
                         state_dir=tmp_path / "state")

    def index_once() -> dict:
        session.run({"kind": "index"})
        deadline = time.monotonic() + 60.0
        while session.run_state()["state"] != "idle":
            assert time.monotonic() < deadline, "index run did not finish"
            time.sleep(0.05)
        return calls[-1]

    try:
        unset = index_once()
        assert (unset["formula"], unset["temperature"]) == (
            None, TABLE_TEMPERATURE)

        session.project_patch({"indexing": {"formula": "C7H6O2"}})
        only_formula = index_once()
        assert (only_formula["formula"], only_formula["temperature"]) == (
            "C7H6O2", TABLE_TEMPERATURE)

        session.project_patch({"indexing": {"formula": "C7H6O2",
                                            "temperature": 120.0}})
        both = index_once()
        assert (both["formula"], both["temperature"]) == ("C7H6O2", 120.0)

        flags, controls = _FORMULA_REFUSALS[-1]
        with pytest.raises(GuiError) as refused:
            session.project_patch({"indexing": controls})
        assert str(refused.value) == _cli_refusal(flags, capsys)
        # the refused block was not kept
        assert session.project_doc()["doc"]["indexing"]["temperature"] == 120.0
    finally:
        session.close()


# ----------------------------------------------------------------------
# the GUI's half: the committed corpus the form test replays
# ----------------------------------------------------------------------
CORPUS = Path(__file__).parent / "data" / "gui" / "index_controls.json"


def test_the_form_corpus_quotes_the_live_registries():
    """Writes the corpus (the ``test_gui_fnmatch`` mechanism): python owns the
    field inventory and the vocabularies; ``gui/src/lib/peaks.test.ts``
    replays this file and fails if the form cannot state a field.  Committed,
    so a stale corpus shows up as a diff and CI needs no python-node bridge.
    """
    corpus = {
        "search_fields": list(SearchSpecSpec.model_fields),
        "control_fields": [n for n in IndexingControls.model_fields
                           if n != "search"],
        "enums": {
            "engines": list(engine_names()),
            "systems": list(SYSTEM_ORDER),
            "centrings": {k: list(v) for k, v in CENTRINGS.items()},
            "presets": sorted(SEARCH_PRESETS),
            "shift_templates": list(SHIFT_TEMPLATES),
        },
    }
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(corpus, indent=1, sort_keys=True) + "\n"
    if not CORPUS.exists() or CORPUS.read_text(encoding="utf-8") != text:
        CORPUS.write_text(text, encoding="utf-8")
    assert json.loads(CORPUS.read_text(encoding="utf-8")) == corpus


# ----------------------------------------------------------------------
# the acceptance criterion: two chairs, identical controls, identical notes
# ----------------------------------------------------------------------
@pytest.mark.xdist_group("search-controls-chairs")
def test_gui_and_direct_runs_produce_identical_spec_notes(tmp_path):
    """The WP's acceptance sentence, run literally: the GUI chair (a project
    whose document carries the controls, the run reading them) and the direct
    chair (the same controls handed to ``index_pattern`` by a caller) make the
    same call, and the result's ``spec_notes`` — which since WP-1045 record
    every ``SearchSpec`` field — are byte-identical.

    The direct chair was the JSON request until WP-1303; what it asserts is
    unchanged, because the request never did anything to the controls but
    validate them into this same call (``IndexRequest`` → ``index_pattern``).
    """
    import time

    import rietx as rx
    from rietx.gui import GuiSession
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import perturbed_models, synthesize

    controls = {
        "search": {"systems": ["cubic"], "max_volume": 800.0,
                   "shift_allowance_deg": 1e-9, "budget_seconds": 20.0,
                   "total_budget_seconds": 60.0, "seed": 5},
        "validate_candidates": False,
    }

    pattern = synthesize()
    structure, instrument = perturbed_models()
    file = _write_xye(tmp_path / "chairs.xye", pattern)
    project = rx.Project.create(tmp_path / "chairs.rex", pattern=file,
                                structure=structure, instrument=instrument)
    session = GuiSession(project, state_dir=tmp_path / "state")
    try:
        session.project_patch({"indexing": controls})
        session.run({"kind": "index"})
        deadline = time.monotonic() + 120.0
        while session.run_state()["state"] != "idle":
            assert time.monotonic() < deadline, "index run did not finish"
            time.sleep(0.1)
        assert session.run_state()["run"]["status"] == "completed"
        gui_notes = session.index_result()["result"]["provenance"]["notes"]
    finally:
        session.close()

    # the same controls, validated through the same model and handed over as
    # the call they map to — a chair, not a shortcut: nothing here bypasses
    # ``SearchSpecSpec``, which is what makes the comparison meaningful
    spec = SearchSpecSpec(**controls["search"])
    answer = rx.index_pattern(
        None, data=pattern, instrument=instrument,
        spec=spec.to_spec(), preset=spec.preset,
        validate=controls["validate_candidates"])
    direct_notes = json.loads(answer.model_dump_json())["provenance"]["notes"]

    assert gui_notes == direct_notes
