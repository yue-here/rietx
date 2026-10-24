"""The diagnostics of a batch as counts (WP-2037, the batch aggregate).

``rx.diagnostics_summary`` takes every level from
``rietx.schemas.results.diagnostic_view``, so the expected counts below follow
from ``tests/test_summary_levels.py``'s table of where each FAP code is a
warning.  The batch is three hand-built results, so no fit is needed.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

import rietx as rx
from rietx.schemas.results import _NAMED_PURPOSES
from tests.test_summary_levels import FAP, _d, _result

BOUND = _d("BOUND_HIT", ["phases.0.cell.a"], level="error")
NOTE = _d("CAPILLARY_OFFSET_UNAVAILABLE", ["instrument.geometry.goniometer_radius_mm"],
          level="info")


def _batch():
    return [_result(list(FAP.values())),
            _result([FAP["FLOOR_HIT"], FAP["RESOLUTION_UNCONSTRAINED"]]),
            _result([FAP["FLOOR_HIT"], BOUND, NOTE])]


def _tallies(summary):
    return {t.code: (t.n_results, t.n_rows, t.n_error, t.n_warning, t.n_info)
            for t in summary.codes}


def test_each_code_is_counted_by_results_fired_on_and_rows_by_level():
    s = rx.diagnostics_summary(_batch())
    assert s.n_results == 3 and s.deliverable is None and s.levels == {}
    assert _tallies(s) == {
        "FLOOR_HIT": (3, 3, 0, 3, 0),
        "RESOLUTION_UNCONSTRAINED": (2, 2, 0, 2, 0),
        "BOUND_HIT": (1, 1, 1, 0, 0),
        "CAPILLARY_OFFSET_UNAVAILABLE": (1, 1, 0, 0, 1),
        "PATTERN_UNDERSAMPLED": (1, 1, 0, 1, 0),
        "SITE_SNAPPED_TO_SPECIAL_POSITION": (1, 1, 0, 1, 0),
    }
    # most results first, then most rows, then by name
    assert [t.code for t in s.codes] == list(_tallies(s))
    assert {t.code: t.rate for t in s.codes}["FLOOR_HIT"] == 1.0
    assert {t.code: t.rate for t in s.codes}["RESOLUTION_UNCONSTRAINED"] == pytest.approx(2 / 3)


def test_a_code_repeated_in_one_result_fires_on_it_once():
    s = rx.diagnostics_summary([_result([FAP["FLOOR_HIT"]] * 4), _result([])])
    (tally,) = s.codes
    assert (tally.n_results, tally.rate, tally.n_rows) == (1, 0.5, 4)


def test_the_pareto_ranks_the_warning_codes_and_its_cumulative_share_ends_at_one():
    s = rx.diagnostics_summary(_batch())
    assert [(p.code, p.n_warning) for p in s.pareto] == [
        ("FLOOR_HIT", 3), ("RESOLUTION_UNCONSTRAINED", 2),
        ("PATTERN_UNDERSAMPLED", 1), ("SITE_SNAPPED_TO_SPECIAL_POSITION", 1)]
    assert [p.share for p in s.pareto] == pytest.approx([3 / 7, 2 / 7, 1 / 7, 1 / 7])
    assert [p.cumulative for p in s.pareto] == pytest.approx([3 / 7, 5 / 7, 6 / 7, 1.0])
    assert s.pareto[-1].cumulative == 1.0
    # an error and an info carry no warning load, so they rank nowhere
    assert {"BOUND_HIT", "CAPILLARY_OFFSET_UNAVAILABLE"}.isdisjoint(p.code for p in s.pareto)


def test_with_no_deliverable_warnings_per_result_covers_every_named_purpose():
    """``series`` is left out: it follows every path, so it would count every
    warning (``DiagnosticRow``'s docstring)."""
    s = rx.diagnostics_summary(_batch())
    assert tuple(s.warnings_per_result) == _NAMED_PURPOSES
    assert s.warnings_per_result == pytest.approx({
        "phase_id": 0.0, "qpa": 5 / 3, "structure": 5 / 3, "cell": 0.0,
        "microstructure": 1.0, "calibration": 1.0, "magnetic": 5 / 3})


def test_under_a_deliverable_every_count_is_the_level_for_that_purpose():
    s = rx.diagnostics_summary(_batch(), deliverable="structure")
    assert s.deliverable == "structure"
    assert s.warnings_per_result == pytest.approx({"structure": 5 / 3})
    assert _tallies(s)["RESOLUTION_UNCONSTRAINED"] == (2, 2, 0, 0, 2)
    assert [(p.code, p.cumulative) for p in s.pareto] == pytest.approx([
        ("FLOOR_HIT", 0.6), ("PATTERN_UNDERSAMPLED", 0.8),
        ("SITE_SNAPPED_TO_SPECIAL_POSITION", 1.0)])
    cell = rx.diagnostics_summary(_batch(), deliverable="cell")
    assert cell.pareto == [] and cell.warnings_per_result == {"cell": 0.0}


@pytest.mark.parametrize("purpose", _NAMED_PURPOSES)
def test_a_count_agrees_with_the_printed_summary_header(purpose):
    """The one-filter rule: the aggregate and ``summary()`` read one view."""
    result = _batch()[0]
    header = next(line for line in result.summary(deliverable=purpose).splitlines()
                  if line.startswith(f"  diagnostics under {purpose}:"))
    printed = int(re.search(r"(\d+) warnings?", header).group(1))
    assert rx.diagnostics_summary([result], purpose).warnings_per_result[purpose] == printed


def test_a_callers_levels_move_a_codes_rows_and_are_echoed():
    levels = {"FLOOR_HIT": "allow", "BOUND_HIT": "allow",
              "CAPILLARY_OFFSET_UNAVAILABLE": "warn"}
    s = rx.diagnostics_summary(_batch(), levels=levels)
    assert s.levels == levels
    tallies = _tallies(s)
    assert tallies["FLOOR_HIT"] == (3, 3, 0, 0, 3)
    # an error is never lowered (clause 1)
    assert tallies["BOUND_HIT"] == (1, 1, 1, 0, 0)
    assert tallies["CAPILLARY_OFFSET_UNAVAILABLE"] == (1, 1, 0, 1, 0)
    assert "FLOOR_HIT" not in {p.code for p in s.pareto}
    # ``warn`` makes the info row a warning under every purpose
    assert s.warnings_per_result["cell"] == pytest.approx(1 / 3)


def test_an_unknown_deliverable_code_or_word_is_refused_even_on_an_empty_batch():
    with pytest.raises(ValueError, match="unknown deliverable 'cells'"):
        rx.diagnostics_summary([], deliverable="cells")
    with pytest.raises(ValueError, match="unknown diagnostic code.*FLOOR_HITT"):
        rx.diagnostics_summary([], levels={"FLOOR_HITT": "allow"})
    with pytest.raises(ValueError, match="unknown level.*'ignore'"):
        rx.diagnostics_summary(_batch(), levels={"FLOOR_HIT": "ignore"})


def test_an_empty_batch_gives_empty_tallies():
    for deliverable in (None, "qpa"):
        s = rx.diagnostics_summary([], deliverable)
        assert (s.n_results, s.codes, s.pareto, s.warnings_per_result) == (0, [], [], {})
    clean = rx.diagnostics_summary([_result([]), _result([])])
    assert clean.n_results == 2 and clean.codes == [] and clean.pareto == []
    assert set(clean.warnings_per_result.values()) == {0.0}


def test_any_object_carrying_diagnostics_is_a_result():
    s = rx.diagnostics_summary(iter([SimpleNamespace(diagnostics=[FAP["FLOOR_HIT"]])]))
    assert _tallies(s) == {"FLOOR_HIT": (1, 1, 0, 1, 0)}


def test_the_summary_survives_a_json_round_trip():
    s = rx.diagnostics_summary(_batch(), levels={"FLOOR_HIT": "deny"})
    back = rx.DiagnosticsSummary.model_validate_json(s.model_dump_json())
    assert back == s
    assert back.model_dump(mode="json")["codes"][0]["code"] == "FLOOR_HIT"


def test_the_printed_view_leads_with_its_header_and_the_pareto():
    lines = str(rx.diagnostics_summary(_batch())).splitlines()
    assert lines[0] == ("DiagnosticsSummary: 3 result(s), no deliverable, "
                        "rows at their raised level")
    assert lines[1].split() == ["code", "fired", "on", "warnings", "cumulative"]
    assert lines[2].split() == ["FLOOR_HIT", "3/3", "3", "43%"]
    assert lines[-2] == ("  fired with no warning row: BOUND_HIT 1/3, "
                         "CAPILLARY_OFFSET_UNAVAILABLE 1/3")
    assert lines[-1].startswith("  warnings per result: phase_id 0, qpa 1.7,")
    under = str(rx.diagnostics_summary(_batch(), "cell", {"FLOOR_HIT": "deny"})).splitlines()
    assert under[0] == ("DiagnosticsSummary: 3 result(s), under cell, "
                        "1 code(s) set by levels=")
    assert under[1] == "  no warning rows"
    assert str(rx.diagnostics_summary([])).splitlines()[-1] == "  no warning rows"
