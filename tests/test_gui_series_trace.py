"""WP-1317: the series trace's vocabulary, written once and read from the result.

``rietx.gui.series.TRACE_VOCABULARY`` is the one statement of what the trace
draws.  These tests hold the three places that quote it to it: :func:`trace`,
which reads each row's source off a :class:`SeriesResult` and nothing else; the
library, which must still write every code the table names; and the GUI quickstart,
whose table must list the same rows, both ways.  The panel draws what the route
serves, and ``gui/src/lib/series.test.ts`` covers that half.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rietx import help as rx_help
from rietx.gui.series import OTHER_MARK, TRACE_VOCABULARY, result_payload, trace
from rietx.schemas.common import Diagnostic
from rietx.schemas.results import Statistics
from rietx.schemas.sequential import (
    SeriesEntry,
    SeriesFailure,
    SeriesResult,
    SeriesStep,
)

REPO = Path(__file__).resolve().parents[1]
GUIDE = REPO / "docs" / "docs" / "start" / "gui-quickstart.md"
SEQUENTIAL = REPO / "src" / "rietx" / "sequential.py"

CODES = [row["key"] for row in TRACE_VOCABULARY if row["key"].isupper()]


def _stats(rwp: float) -> Statistics:
    return Statistics(rwp=rwp, rp=rwp, rexp=0.05, gof=rwp / 0.05, chi2=1.0,
                      n_points=100, n_free_parameters=3)


def _entry(i: int, **kw) -> SeriesEntry:
    return SeriesEntry(index=i, label=f"T{300 + 10 * i}", x=300.0 + 10 * i,
                       statistics=_stats(0.05 + 0.001 * i), **kw)


def _verdict(code: str, where: list[str]) -> Diagnostic:
    return Diagnostic(level="warning", code=code, where=where, message=code)


def _series() -> SeriesResult:
    """Five patterns: a reseed at 1, a failure at 2, a run above the fence from
    3, an unknown per-pattern code at 4, and series-level rows naming none."""
    entries = [
        _entry(0),
        _entry(1, reseeded=True, diagnostics=[
            Diagnostic(level="info", code="HIGH_CORRELATION", message="ρ"),
            Diagnostic(level="warning", code="HIGH_CORRELATION", message="ρ"),
            Diagnostic(level="warning", code="BOUND_HIT", message="b")]),
        _entry(3), _entry(4),
    ]
    return SeriesResult(
        entries=entries, x_label="T",
        failures=[SeriesFailure(index=2, label="T320", exception="LinAlgError()")],
        n_failed=1,
        diagnostics=[
            _verdict("SEQUENTIAL_RESEED", ["T310"]),
            _verdict("SERIES_PATTERN_FAILED", ["T320"]),
            _verdict("SEQUENTIAL_UNRECOVERED", ["T330"]),
            _verdict("SEQUENTIAL_UNRECOVERED", ["T340"]),
            _verdict("SOME_FUTURE_CODE", ["T340"]),
            # series-level: a path, and nothing — neither marks a pattern
            _verdict("SEQUENTIAL_PERSISTENT_FINDING", ["phases.0.cell.a"]),
            _verdict("SEQUENTIAL_CANCELLED", []),
        ],
        steps=[
            SeriesStep(path="phases.0.cell.a", labels=("T330", "T340"),
                       indices=(3, 4), step=0.01, size_esd=40.0),
            SeriesStep(path="phases.0.cell.a", labels=("T300", "T310"),
                       indices=(0, 1), step=0.001, size_esd=4.0),
            SeriesStep(path="phases.0.scale", labels=("T300", "T310"),
                       indices=(0, 1), step=0.1, size_esd=None),
        ],
    )


def test_every_pattern_is_a_point_in_index_order_a_failure_included():
    got = trace(_series(), coordinates=[300.0, 310.0, 320.0, 330.0, 340.0])
    assert [p["index"] for p in got["points"]] == [0, 1, 2, 3, 4]
    assert got["x_label"] == "T"
    failed = got["points"][2]
    # placed by the staged member's coordinate, since a failure has no entry
    assert failed == {"index": 2, "label": "T320", "x": 320.0, "status": "failed",
                      "rwp": None, "marks": ["SERIES_PATTERN_FAILED"],
                      "findings": []}
    # without the members' coordinates it still has its place, and no x
    assert trace(_series())["points"][2]["x"] is None


def test_a_series_verdict_marks_the_pattern_its_where_names():
    marks = {p["index"]: p["marks"] for p in trace(_series())["points"]}
    assert marks == {0: [], 1: ["SEQUENTIAL_RESEED"], 2: ["SERIES_PATTERN_FAILED"],
                     3: ["SEQUENTIAL_UNRECOVERED"],
                     # an unknown code is drawn, not dropped: the codes are open
                     4: ["SEQUENTIAL_UNRECOVERED", "SOME_FUTURE_CODE"]}
    assert OTHER_MARK not in {row["mark"] for row in TRACE_VOCABULARY}


def test_a_verdict_on_an_unlabelled_pattern_is_found_by_its_index():
    """``schemas.sequential._pattern_name`` is the fences' own key: the label,
    or the index where there is none."""
    series = SeriesResult(
        entries=[SeriesEntry(index=0), SeriesEntry(index=1)],
        diagnostics=[_verdict("SEQUENTIAL_RESEED", ["1"])])
    assert [p["marks"] for p in trace(series)["points"]] == [[], ["SEQUENTIAL_RESEED"]]


@pytest.mark.parametrize("patterns", [
    # two labels alike
    {"entries": [SeriesEntry(index=0, label="T300"), SeriesEntry(index=1, label="T300")]},
    # a label alike to an unlabelled pattern's index, which its fences write
    {"entries": [SeriesEntry(index=0, label="1"), SeriesEntry(index=1)]},
    # a fitted pattern and a failed one
    {"entries": [SeriesEntry(index=0, label="T300")],
     "failures": [SeriesFailure(index=1, label="T300", exception="E()")]},
], ids=["two-labels", "label-and-index", "entry-and-failure"])
def test_two_patterns_under_one_name_are_refused(patterns):
    """A fence names its pattern only by that name, so the trace would mark
    whichever it met first (#1395's review). Refused, naming both, from a
    constructor and from a stored document alike."""
    with pytest.raises(ValueError, match=r"both named .* \(pattern 0\) and .* \(pattern 1\)"):
        SeriesResult(**patterns)
    stored = {key: [p.model_dump(mode="json") for p in rows]
              for key, rows in patterns.items()}
    with pytest.raises(ValueError, match="Give each pattern its own label"):
        SeriesResult.model_validate(stored)


def test_a_backward_chain_failure_does_not_mark_a_fitted_pattern_failed():
    """``direction="both"`` puts the backward chain's ``SERIES_PATTERN_FAILED``
    in the reported diagnostics, naming a pattern whose forward fit stands."""
    series = SeriesResult(
        entries=[_entry(0), _entry(1)],
        diagnostics=[_verdict("SERIES_PATTERN_FAILED", ["T310"])])
    assert [p["marks"] for p in trace(series)["points"]] == [[], []]


def test_a_patterns_findings_are_its_own_codes_at_their_worst_level():
    findings = trace(_series())["points"][1]["findings"]
    assert findings == [{"code": "BOUND_HIT", "level": "warning"},
                        {"code": "HIGH_CORRELATION", "level": "warning"}]


def test_the_largest_step_is_each_paths_first_measured_row():
    steps = trace(_series())["largest_steps"]
    # the scale's only row has no esd, so it has no size and no largest step
    assert steps == {"phases.0.cell.a": {"indices": [3, 4], "size_esd": 40.0,
                                         "cold_ratio": None}}


def test_the_route_serves_the_trace_beside_the_answer():
    payload = result_payload(_series(), None, running=False, curves=[True] * 4)
    assert payload["trace"] == trace(_series())
    assert [row["key"] for row in payload["trace"]["vocabulary"]] == [
        row["key"] for row in TRACE_VOCABULARY]


def test_the_vocabulary_names_codes_the_library_writes_and_explains():
    """A declared name is a claim (root ``CLAUDE.md``): a row for a code no
    fence writes any more would draw a mark that can never appear."""
    source = SEQUENTIAL.read_text(encoding="utf-8")
    for code in CODES:
        assert f'"{code}"' in source, f"{code} is not written by rietx.sequential"
        assert code in rx_help.DIAGNOSTIC_HELP, f"{code} has no help entry"
    marks = [row["mark"] for row in TRACE_VOCABULARY]
    assert len(set(marks)) == len(marks), "two rows share a mark"


def _guide_rows() -> dict[str, str]:
    """The GUI quickstart's trace table, as key → label."""
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("### The trace")
    end = text.find("\n## ", start)
    rows = {}
    for line in text[start:end].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and (m := re.fullmatch(r"`([A-Za-z_]+)`", cells[0])):
            rows[m.group(1)] = cells[1]
    return rows


def test_the_guide_lists_the_vocabulary_both_ways():
    rows = _guide_rows()
    assert set(rows) == {row["key"] for row in TRACE_VOCABULARY}, (
        "the GUI quickstart's trace table and rietx.gui.series.TRACE_VOCABULARY "
        "disagree")
    for row in TRACE_VOCABULARY:
        assert rows[row["key"]] == row["label"], row["key"]
