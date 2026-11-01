"""Unit tests for the transcript miner (WP-1063).

Everything here runs against the committed two-cell record in
``fixture_round/`` (its README says what each cell is built to pin) or against
``tmp_path`` — no round record, no agent, no refinement.  The real record is
gitignored and deletable, so it can never be what tests the reader of it.

The rules under test are the ones the round taught, each of which had a
measured wrong answer before it:

- a token in **prompt prose** is not a delivery (the §5/§6 excerpts name the
  whole action vocabulary);
- an overlay is an overlay whether a ``Write`` payload or a Bash heredoc
  carried it;
- the trajectory is *answered* by ``tool_use_id``, not by adjacency, because
  an agent's own ``jq`` projection can strip every marker field out of a rung;
- voicing a word is not evidence of having been told it — three cells voiced
  ``exchangeable`` without the clause ever arriving, one of them in the arm
  that never had a report.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rietx.report.schemas import StageReport
from tests.eval_report_agent import mine_transcripts as mt

FIXTURE = Path(__file__).parent / "fixture_round"


@pytest.fixture(scope="module")
def mined() -> dict:
    return mt.mine(FIXTURE)


def _row(mined: dict, cell: str) -> dict:
    return next(r for r in mined["rows"] if r["cell"] == cell)


# ----------------------------------------------------------------------
# the vocabulary is quoted, never invented
# ----------------------------------------------------------------------
def test_every_field_token_names_a_live_field():
    """A renamed field must break the miner, not silently count zero — the
    derived-flag rot of WP-1037, one directory over."""
    for token, (model, name) in mt.FIELD_TOKENS.items():
        assert token == name
        assert name in model.model_fields, f"{model.__name__}.{name} is gone"


def test_action_vocabulary_is_the_live_one():
    from typing import get_args

    from rietx.report.schemas import ActionKind

    assert set(get_args(ActionKind)) <= set(mt.TOKENS)


def test_every_pull_token_names_a_live_surface():
    """The FIELD_TOKENS rule for callables (WP-1064): each python-arm pull
    token is pinned to the live attribute it names, so a renamed surface
    breaks the miner loudly instead of counting zero for ever."""
    for token, (owner, name, kind) in mt.PULL_TOKENS.items():
        assert token == name
        assert hasattr(owner, name), f"{owner}.{name} is gone"
        assert kind in ("method", "function")


def test_pull_matching_is_call_shaped_for_methods():
    """``report`` and ``branch`` are everyday words; only the attribute call
    counts.  Module functions match by their distinctive names, which also
    catches the import that precedes a call."""
    rx = mt._PULL_RES["report"]
    assert rx.search("rep = ref.report()")
    assert not rx.search("the report says")
    assert not rx.search("build_report(result)")
    assert mt._PULL_RES["compare_rivals"].search(
        "from rietx.report import compare_rivals")


def test_rung_markers_are_rung_only_and_non_empty():
    assert mt.RUNG_MARKERS
    assert mt.RUNG_MARKERS <= set(StageReport.model_fields)
    # ``stage`` was disqualified while IterationRecord existed; WP-1003
    # deleted that dead class, so the same derivation now admits it — the
    # assertion tracks the schemas, not a frozen list
    assert "stage" in mt.RUNG_MARKERS
    # ``actions`` survives because delivery is matched in JSON form
    assert "actions" in mt.RUNG_MARKERS
    assert mt._as_json("actions").search('"suggested_actions": []') is None
    assert mt._as_json("actions").search('"actions": []') is not None


# ----------------------------------------------------------------------
# surfaces
# ----------------------------------------------------------------------
def test_prompt_prose_is_not_a_delivery(mined):
    """Both fixture cells read a prompt naming ``add_impurity_phase`` and
    ``n_actions_vetoed`` in backticks; neither counts as the package having
    sent anything."""
    for cell in ("both__sonnet/E2", "report__haiku/E2"):
        counts = _row(mined, cell)["citations"]["add_impurity_phase"]
        assert counts["delivered"] == 0, cell


def test_delivered_counts_the_json_form(mined):
    row = _row(mined, "both__sonnet/E2")
    assert row["citations"]["exchangeable"]["delivered"] == 1
    assert row["citations"]["identifiability"]["probed"] == 1


def test_voiced_is_the_agents_own_prose(mined):
    """Assistant text and the ``answer.json`` it wrote, and nothing else."""
    assert _row(mined, "both__sonnet/E2")["citations"]["exchangeable"]["voiced"] == 2
    assert _row(mined, "report__haiku/E2")["citations"]["exchangeable"]["voiced"] == 1


def test_voicing_without_delivery_is_visible(mined):
    """The b cell says ``exchangeable`` out of its own head — no clause ever
    reached it.  A word-match eval would score that as reading the report."""
    row = _row(mined, "report__haiku/E2")
    assert row["citations"]["exchangeable"]["voiced"] == 1
    assert row["ridge"]["clause_delivered_index"] is None


# ----------------------------------------------------------------------
# the ridge
# ----------------------------------------------------------------------
def test_write_payload_overlay_is_found(mined):
    """The a cell's overlay is an escaped ``content`` string: a brace scan of
    the serialized tool input cannot reach it."""
    row = _row(mined, "both__sonnet/E2")["ridge"]
    assert row["both_free"] is True
    assert row["ridge_overlay_index"] is not None


def test_heredoc_overlay_is_found():
    """The b cell wrote its overlay with ``cat > … << 'EOF'`` — one of the
    seven real ridge cells did the same."""
    events = mt.read_events(
        FIXTURE / "transcripts" / "agent-fixture-b.jsonl")
    writes = mt.overlay_writes(events)
    assert len(writes) == 1
    assert mt.overlay_frees(writes[0][1], ["instrument.zero_shift"])
    assert not mt.overlay_frees(
        writes[0][1], ["instrument.geometry.sample_displacement"])


def test_clause_order_is_reported(mined):
    row = _row(mined, "both__sonnet/E2")["ridge"]
    assert row["clause_delivered_index"] < row["ridge_overlay_index"]
    assert row["clause_delivered_before"] is True
    assert row["clause_voiced_before"] is True


def test_one_rival_is_not_a_ridge(mined):
    assert _row(mined, "report__haiku/E2")["ridge"]["both_free"] is False


def test_a_preset_plan_claims_nothing():
    """Which paths a preset frees is not in the overlay, so the ridge column
    stays empty rather than being guessed."""
    assert not mt.overlay_frees({"plan": "lab_calibrate"},
                                ["instrument.zero_shift"])


def test_wildcard_reaches_a_watched_path():
    assert mt.overlay_frees(
        {"plan": {"stages": [{"turn_on": ["instrument.geometry.*"]}]}},
        ["instrument.geometry.sample_displacement"])


# ----------------------------------------------------------------------
# the trajectory
# ----------------------------------------------------------------------
def test_probe_is_answered_by_tool_use_id(mined):
    rungs = _row(mined, "both__sonnet/E2")["rungs"]
    assert rungs["probed_index"] is not None
    assert rungs["answered_index"] > rungs["probed_index"]
    assert rungs["marker_index"] is not None


def test_a_cell_with_no_trajectory_reports_none(mined):
    rungs = _row(mined, "report__haiku/E2")["rungs"]
    assert rungs == {"trajectory_rungs": None, "probed_index": None,
                     "answered_index": None, "marker_index": None,
                     "voiced_index": None}


# ----------------------------------------------------------------------
# the record itself
# ----------------------------------------------------------------------
def test_cells_are_named_and_agree_with_their_meta(mined):
    assert mined["n_transcripts"] == 2
    assert mined["n_cells_named"] == 2
    assert mined["notes"] == []


def test_thinking_is_measured_never_asserted(mined, tmp_path):
    """Whether ``voiced`` is a floor (round 2: 0 thinking characters) or has
    the reasoning kept beside it (round 3) is a property of the record; the
    header must say which was measured, not repeat round 2's."""
    assert mined["thinking_text_chars"] == 0
    assert "no thinking blocks kept" in mt.render(mined)
    t = tmp_path / "agent-x.jsonl"
    t.write_text(json.dumps({"message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "abcde"},
        {"type": "text", "text": "prose"}]}}) + "\n", encoding="utf-8")
    assert mt._thinking_chars(t) == 5
    kept = dict(mined, thinking_text_chars=5)
    assert "5 of thinking" in mt.render(kept)


def test_two_cells_naming_one_workspace_is_reported():
    """A transcript that names two cells is a record problem to say out loud,
    never a tie to break."""
    assert mt.cell_of("RUNS/both__sonnet/E2 and RUNS/off__haiku/R1") is None
    assert mt.cell_of("RUNS/both__sonnet/E2 twice RUNS/both__sonnet/E2") == (
        "both", "sonnet", "E2")


def test_round_three_cell_names_parse():
    """2.0 ids carry a trailing letter (E8p, J1P, J1S), and ``python`` is a
    condition like any other in a workspace path."""
    assert mt.cell_of("RUNS/python__sonnet/E8p/prompt.md") == (
        "python", "sonnet", "E8p")
    assert mt.cell_of("RUNS/off__haiku/J1P/episode.json") == (
        "off", "haiku", "J1P")


def test_projection_condition_cell_names_parse():
    """2.2 condition names carry single underscores (``report_stat``,
    ``report_noexec``); the cell separator stays the double underscore, which
    no condition name may contain."""
    assert mt.cell_of("RUNS/report_stat__sonnet/N1/prompt.md") == (
        "report_stat", "sonnet", "N1")
    assert mt.cell_of("RUNS/report_noexec__haiku/C1/episode.json") == (
        "report_noexec", "haiku", "C1")


def test_a_windows_workspace_path_names_its_cell():
    """The launcher formats its prompt from the platform's own path, so on
    Windows the separator is ``\\``, and a transcript holds it JSON-escaped."""
    path = r"C:\Temp\RUNS\python__sonnet\N1"
    assert mt.cell_of(path) == ("python", "sonnet", "N1")
    assert mt.cell_of(json.dumps({"text": path})) == ("python", "sonnet", "N1")


def test_license_phrase_quotes_the_live_clause():
    """The 2.2 in-context anchor must match the sentence the round's package
    delivers (PROTOCOL.md 2.2 read-out (a)).  A later WP that rewords the
    license breaks this pin loudly, and the successor freezes the phrase for
    the archived records before quoting the new sentence — the
    :data:`~tests.eval_report_agent.mine_transcripts.CLAUSE_PHRASE`
    life cycle, one round on."""
    from rietx.report import identifiability_clause
    from rietx.report.schemas import ExchangeFinding, IdentifiabilityEvidence

    clause = identifiability_clause(IdentifiabilityEvidence(
        chi2_reduced=3.5, exchanges=[ExchangeFinding(
            held="instrument.geometry.sample_displacement", r2=0.9977,
            partner="instrument.zero_shift", partner_null=0.0,
            partner_value=0.03, partner_esd=0.001,
            partner_significance=30.0, exchangeable=True)]))
    assert clause is not None
    assert mt.LICENSE_PHRASE in clause
    assert mt._LICENSE_RE.search(clause)


def test_license_row_reports_never_on_the_fixture(mined):
    """The committed fixture predates the license sentence; its cells must
    read never-delivered, never-voiced — the miner reports the record, not
    the live package."""
    assert _row(mined, "report__haiku/E2")["license"] == {
        "delivered_index": None, "voiced_index": None}


def _probe(index, command):
    inputs = {"command": command}
    return mt.Event(index, "probed", "tool_use:Bash", json.dumps(inputs),
                    inputs)


def _overlay_probe(index, overlay):
    return _probe(index, "cat > overlay.json <<'EOF'\n"
                  + json.dumps(overlay) + "\nEOF")


def test_swap_rows_classify_the_shape_and_the_cell_treatment():
    """A swap frees exactly one rival; both-free and neither-free overlays
    are not swaps, a preset name claims nothing, and the cell column is the
    2.1 lesson — a decisive ratio measured cell-held answered a different
    question than the registered tie (``python__sonnet`` N1: 1.277 for the
    wrong rival)."""
    disp = "instrument.geometry.sample_displacement"
    zero = "instrument.zero_shift"
    events = [
        _overlay_probe(0, {"plan": {"stages": [
            {"turn_on": [disp]}, {"turn_on": ["phases.0.cell.a"]}]}}),
        _overlay_probe(1, {"plan": {"stages": [{"turn_on": [zero]}]}}),
        _overlay_probe(2, {"plan": {"stages": [{"turn_on": [disp, zero]}]}}),
        _overlay_probe(3, {"plan": "lab_calibrate"}),
    ]
    cell = mt.Cell("report_stat", "sonnet", "C1", Path("x"), events,
                   card=None, meta_model=None,
                   truth={"watch": {"cause": [disp], "absorber": [zero]}})
    assert mt.swap_rows(cell) == [
        {"overlay_index": 0, "freed": "cause", "cell_free": True},
        {"overlay_index": 1, "freed": "absorber", "cell_free": False},
    ]


def test_usage_row_counts_pulls_and_fit_bearing_runs():
    """First-probed indices per pull surface; a script that fits five times
    is one fit-bearing run (the budget paces the loop, not the solver)."""
    events = [
        _probe(0, "python - <<'EOF'\nrep = ref.report()\n"
                  "for _ in range(5):\n    ref.fit(data)\nEOF"),
        _probe(1, "python - <<'EOF'\nfrom rietx.report import "
                  "compare_rivals\ncompare_rivals(ref, data, f)\nEOF"),
        _probe(2, "cat prompt.md"),
        mt.Event(3, "delivered", "tool_result",
                 "the report text mentioning ref.fit( in prose"),
    ]
    cell = mt.Cell("python", "sonnet", "N1", Path("t"), events, None, None,
                   None)
    usage = mt.usage_row(cell)
    assert usage["report"] == 0
    assert usage["compare_rivals"] == 1
    assert usage["suggest"] is None and usage["branch"] is None
    assert usage["fit_bearing_runs"] == 1     # one event, five fits


def test_audit_flags_point_at_probed_events_only():
    """Candidates for the human audit: the sibling marker, the truth tree,
    harness sources (``run_refine`` exempt — it is the sanctioned entry
    point), repo docs, the network.  Delivered text never flags."""
    events = [
        _probe(0, "cat ../N1.condition.json"),
        _probe(1, "ls TRUTH/"),
        _probe(2, ".venv/bin/python -m tests.eval_report_agent.run_refine EP"),
        _probe(3, "cat tests/eval_report_agent/scorer.py"),
        _probe(4, "curl https://example.org"),
        mt.Event(5, "delivered", "tool_result",
                 "see https://example.org and TRUTH/E1.json"),
    ]
    cell = mt.Cell("python", "sonnet", "N1", Path("t"), events, None, None,
                   None)
    flags = {(f["pattern"], f["index"]) for f in mt.audit_row(cell)}
    assert ("condition_marker", 0) in flags
    assert ("truth_tree", 1) in flags
    assert ("eval_harness", 3) in flags
    assert ("network", 4) in flags
    assert not any(index == 2 for _p, index in flags)   # run_refine sanctioned
    assert not any(index == 5 for _p, index in flags)   # delivered never flags


def test_missing_record_is_said_not_raised(tmp_path, capsys):
    assert mt.main([str(tmp_path / "nope")]) == 2
    assert "no round record" in capsys.readouterr().err


def test_a_directory_without_transcripts_is_said(tmp_path, capsys):
    (tmp_path / "transcripts").mkdir()
    assert mt.main([str(tmp_path)]) == 2
    assert "no transcripts" in capsys.readouterr().err


def test_render_and_json_round_trip(tmp_path, capsys):
    out = tmp_path / "mined.json"
    assert mt.main([str(FIXTURE), "--json", str(out)]) == 0
    text = capsys.readouterr().out
    assert "## The ridge: cells that freed both rivals" in text
    assert json.loads(out.read_text(encoding="utf-8"))["n_transcripts"] == 2
