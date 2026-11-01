"""The acceptance suites' diagnostics, pinned as alarm-management counts (WP-2037).

``tests/suite_alarms.py`` fits each standard of ``rietx.viz.compare.STANDARDS``
under its own protocol and reduces the fits through ``rx.diagnostics_summary``:
per standard, the codes that fired and their raised levels; over all of them,
each code's count of standards fired on and the warning rows a fit carries per
purpose.  ``tests/data/suite_alarms.json`` pins those numbers, so a change that
moves them is seen.

**The pin is a prompt, never a verdict.**  The standards are rietx's own data,
so a code firing on every standard may mean every standard has the fault.  A
high rate sends that code to the mechanical ground's test, a known truth where
it must fire and one where it must not.  It re-levels nothing by itself: a
rule whose only evidence is rietx's own test data is overfit in prose form
(DESIGN.md § Rules 3).  A mismatch is read, explained, and re-pinned with
``python -m tests.suite_alarms --write``.
"""

from __future__ import annotations

import pytest

from rietx.help import DIAGNOSTIC_HELP
from rietx.schemas.results import _NAMED_PURPOSES
from rietx.viz.compare import STANDARD_BY_KEY
from tests import suite_alarms


def test_the_pin_parses_and_names_only_live_codes_standards_and_purposes():
    pin = suite_alarms.load_pin()
    assert suite_alarms.REPIN in pin["comment"]
    assert set(pin["standards"]) <= set(STANDARD_BY_KEY), sorted(pin["standards"])
    codes = set(pin["n_results"]) | {c for fired in pin["standards"].values() for c in fired}
    assert codes, "the pin names no code: re-pin it"
    assert codes <= set(DIAGNOSTIC_HELP), sorted(codes - set(DIAGNOSTIC_HELP))
    assert all(set(levels.split(", ")) <= {"error", "warning", "info"}
               for fired in pin["standards"].values() for levels in fired.values())
    assert tuple(pin["warnings_per_result"]) == _NAMED_PURPOSES
    # each standard a code fired on is counted once in the aggregate
    for code, n in pin["n_results"].items():
        assert n == sum(code in fired for fired in pin["standards"].values()), code


def test_the_differences_name_the_code_and_the_standard_it_moved_on():
    pin = {"standards": {"fap": {"FLOOR_HIT": "warning"}},
           "n_results": {"FLOOR_HIT": 1}, "warnings_per_result": {"qpa": 1.0}}
    moved = {"standards": {"fap": {"FLOOR_HIT": "info", "BOUND_HIT": "error"}},
             "n_results": {"FLOOR_HIT": 1, "BOUND_HIT": 1},
             "warnings_per_result": {"qpa": 0.0}}
    assert suite_alarms.differences(pin, pin) == []
    assert suite_alarms.differences(pin, moved) == [
        "fap: BOUND_HIT absent -> error",
        "fap: FLOOR_HIT warning -> info",
        "all standards: BOUND_HIT fired on 0 -> 1",
        "all standards: warnings per result under qpa 1.0 -> 0.0",
    ]


@pytest.mark.slow
@pytest.mark.xdist_group("suite-alarms")
def test_the_standards_fire_what_the_pin_says():
    missing = suite_alarms.unavailable()
    if missing:
        pytest.skip(f"standards without their files: {missing}")
    measured = suite_alarms.firing_table(suite_alarms.collect())
    moved = suite_alarms.differences(suite_alarms.load_pin(), measured)
    assert not moved, (
        "the acceptance standards' diagnostics moved; read each change, say why in "
        f"the WP, then re-pin with {suite_alarms.REPIN}:\n  " + "\n  ".join(moved))
