"""A diagnostic's level under a purpose, derived rather than authored (WP-2037).

Clause 2 of ``docs/milestones/generality.md`` § The rule: a level is the
response a reader owes, and whether it is owed depends on what the reader will
quote.  ``rietx.schemas.results.level_under`` derives it from the diagnostic's
``where`` paths and the purpose table (``rietx.purposes``), falling back on the
code's audited ``scope`` where the diagnostic names no path.

The four codes are the ones the skill's worked default on FAP returned on
2026-10-23 (``docs/wp/2037-attention/examples.md``), built here as records so
the table below is the whole claim and no fit is needed.
"""

from __future__ import annotations

import pytest

from rietx.purposes import PURPOSES
from rietx.schemas.common import Diagnostic
from rietx.schemas.results import level_under


def _d(code: str, where: list[str], level: str = "warning") -> Diagnostic:
    return Diagnostic(level=level, code=code, message="m", where=where)


FAP = {
    "SITE_SNAPPED_TO_SPECIAL_POSITION": _d("SITE_SNAPPED_TO_SPECIAL_POSITION",
                                           ["phases.0.atoms.0"]),
    "FLOOR_HIT": _d("FLOOR_HIT", ["phases.0.extinction"]),
    "RESOLUTION_UNCONSTRAINED": _d("RESOLUTION_UNCONSTRAINED",
                                   ["instrument.profile.u", "instrument.profile.v",
                                    "instrument.profile.w"]),
    "PATTERN_UNDERSAMPLED": _d("PATTERN_UNDERSAMPLED", []),
}

#: The purposes each FAP code is a warning under; ``info`` under every other.
#: A whole site bears on every number read from its atoms (structure, the
#: fraction its multiplicity sets, a moment it carries); extinction on the
#: intensities a structure, a fraction and a moment are read from; the instrument widths
#: on a size, a strain and a calibration; undersampling by its audited scope.
#: ``series`` follows every free path, so every warning is one there.
WARNING_UNDER = {
    "SITE_SNAPPED_TO_SPECIAL_POSITION": {"structure", "qpa", "magnetic", "series"},
    "FLOOR_HIT": {"structure", "qpa", "magnetic", "series"},
    "RESOLUTION_UNCONSTRAINED": {"microstructure", "calibration", "series"},
    "PATTERN_UNDERSAMPLED": {"qpa", "structure", "microstructure", "calibration",
                             "magnetic", "series"},
}


@pytest.mark.parametrize("code", sorted(FAP))
def test_each_fap_code_is_a_warning_exactly_where_its_purpose_reads_it(code):
    got = {p for p in PURPOSES if level_under(FAP[code], p) == "warning"}
    assert got == WARNING_UNDER[code]
    assert all(level_under(FAP[code], p) == "info" for p in set(PURPOSES) - got)


def test_no_warning_on_fap_touches_a_cell():
    """examples.md § 3: every row is ``info`` under ``cell``."""
    assert {level_under(d, "cell") for d in FAP.values()} == {"info"}


def test_an_error_is_an_error_and_an_info_an_info_for_every_purpose():
    err = _d("FLOOR_HIT", ["phases.0.extinction"], level="error")
    note = _d("FLOOR_HIT", ["phases.0.cell.a"], level="info")
    for purpose in PURPOSES:
        assert level_under(err, purpose) == "error"
        assert level_under(note, purpose) == "info"


def test_a_code_with_no_path_and_no_scope_keeps_its_level_everywhere():
    """WP-1076: a pairing nobody checked must not read as "not your concern"."""
    unscoped = _d("DATA_SUPPORT_LOW", [])
    assert {level_under(unscoped, p) for p in PURPOSES} == {"warning"}


def test_a_where_that_names_no_parameter_is_read_as_no_path():
    """A label in ``where`` is not a path, so the code's scope decides."""
    labelled = _d("PATTERN_UNDERSAMPLED", ["fluorapatite"])
    assert level_under(labelled, "qpa") == "warning"
    assert level_under(labelled, "cell") == "info"
    assert level_under(_d("DATA_SUPPORT_LOW", ["Ca1"]), "cell") == "warning"


def test_a_joint_fits_histogram_scope_is_read_through():
    scoped = _d("RESOLUTION_UNCONSTRAINED", ["hist.1.instrument.profile.u"])
    assert level_under(scoped, "microstructure") == "warning"
    assert level_under(scoped, "qpa") == "info"


def test_a_named_variable_bears_on_every_purpose():
    """A ``vars.`` name drives paths the record cannot show (WP-1342), so a
    finding on one is never read as outside a purpose."""
    driven = _d("FLOOR_HIT", ["vars.shared_b"])
    assert {level_under(driven, p) for p in PURPOSES} == {"warning"}


def test_an_unknown_purpose_is_refused_by_name():
    with pytest.raises(ValueError, match="'phase_id'"):
        level_under(FAP["FLOOR_HIT"], "cells")


# --- the view every renderer prints (clause 3) ----------------------------
#
# ``diagnostic_view`` is the one filter; ``_diagnostic_lines`` is its text
# form, the one ``Refinement.summary``, ``str(result)`` and
# ``SeriesResult.summary`` print.  The expected blocks are
# ``docs/wp/2037-attention/examples.md`` §§ 1-4 on the same four records, the
# snapped site still among them (its floor is a separate change) and
# ``FLOOR_HIT``'s ``qpa`` reading added.

def _view_lines(diagnostics, deliverable=None) -> list[str]:
    from rietx.schemas.results import _diagnostic_lines
    return _diagnostic_lines(diagnostics, deliverable)


def test_the_view_orders_by_level_and_prints_in_full_what_decides_the_purpose():
    from rietx.schemas.results import diagnostic_view

    err = _d("BOUND_HIT", ["phases.0.cell.a"], level="error")
    note = _d("CAPILLARY_OFFSET_UNAVAILABLE", ["instrument.geometry.goniometer_radius_mm"],
              level="info")
    stored = [note, *FAP.values(), err]
    rows = diagnostic_view(stored, "structure")
    assert [r.diagnostic.code for r in rows] == [
        "BOUND_HIT", "SITE_SNAPPED_TO_SPECIAL_POSITION", "FLOOR_HIT",
        "PATTERN_UNDERSAMPLED", "CAPILLARY_OFFSET_UNAVAILABLE", "RESOLUTION_UNCONSTRAINED"]
    assert [r.level for r in rows] == ["error", "warning", "warning", "warning", "info", "info"]
    assert [r.full for r in rows] == [True, True, True, True, False, False]

    # with no deliverable each row keeps its own level and only an error is full
    rows = diagnostic_view(stored)
    assert [r.diagnostic.code for r in rows] == [
        "BOUND_HIT", *FAP, "CAPILLARY_OFFSET_UNAVAILABLE"]
    assert [r.level for r in rows] == ["error", *["warning"] * 4, "info"]
    assert [r.full for r in rows] == [True, *[False] * 5]


@pytest.mark.parametrize("code", sorted(FAP))
def test_warning_under_names_each_purpose_but_series_in_table_order(code):
    """``series`` follows every path, so on one result it is no information."""
    from rietx.schemas.results import diagnostic_view

    (row,) = diagnostic_view([FAP[code]])
    assert row.warning_under == tuple(p for p in PURPOSES
                                      if p in WARNING_UNDER[code] and p != "series")
    assert all("series" not in r.warning_under
               for p in PURPOSES for r in diagnostic_view(list(FAP.values()), p))


def test_an_error_or_an_info_is_a_warning_under_nothing():
    from rietx.schemas.results import diagnostic_view

    rows = diagnostic_view([_d("FLOOR_HIT", ["phases.0.extinction"], level="error"),
                            _d("FLOOR_HIT", ["phases.0.extinction"], level="info")])
    assert [r.warning_under for r in rows] == [(), ()]


def test_with_no_deliverable_every_row_is_one_line_and_the_rule_closes_it():
    """examples.md § 1."""
    assert _view_lines(list(FAP.values())) == [
        "  diagnostics: 4 rows, 0 errors; no deliverable given, so none is printed in full",
        "    SITE_SNAPPED_TO_SPECIAL_POSITION at phases.0.atoms.0: "
        "warning under qpa, structure, magnetic",
        "    FLOOR_HIT at phases.0.extinction: warning under qpa, structure, magnetic",
        "    RESOLUTION_UNCONSTRAINED at instrument.profile.u, .v, .w: "
        "warning under microstructure, calibration",
        "    PATTERN_UNDERSAMPLED: warning under qpa, structure, microstructure, calibration, "
        "magnetic",
        "    pass deliverable= to summary() for the rows that decide your purpose; "
        "every row is in result.diagnostics",
    ]


def test_under_structure_its_warnings_print_in_full_and_the_rest_one_line():
    """examples.md § 2."""
    assert _view_lines(list(FAP.values()), "structure") == [
        "  diagnostics under structure: 3 warnings, 0 errors, 1 info",
        "    warning[SITE_SNAPPED_TO_SPECIAL_POSITION]: m",
        "      at: phases.0.atoms.0",
        "    warning[FLOOR_HIT]: m",
        "      at: phases.0.extinction",
        "    warning[PATTERN_UNDERSAMPLED]: m",
        "    info: RESOLUTION_UNCONSTRAINED at instrument.profile.u, .v, .w "
        "(warning under microstructure, calibration)",
    ]


def test_under_cell_every_fap_row_is_one_line():
    """examples.md § 3, and § 4's microstructure counts."""
    lines = _view_lines(list(FAP.values()), "cell")
    assert lines[0] == "  diagnostics under cell: 0 warnings, 0 errors, 4 info"
    assert lines[1:] == [
        "    info: SITE_SNAPPED_TO_SPECIAL_POSITION at phases.0.atoms.0 "
        "(warning under qpa, structure, magnetic)",
        "    info: FLOOR_HIT at phases.0.extinction (warning under qpa, structure, magnetic)",
        "    info: RESOLUTION_UNCONSTRAINED at instrument.profile.u, .v, .w "
        "(warning under microstructure, calibration)",
        "    info: PATTERN_UNDERSAMPLED (warning under qpa, structure, microstructure, "
        "calibration, magnetic)",
    ]
    assert (_view_lines(list(FAP.values()), "microstructure")[0]
            == "  diagnostics under microstructure: 2 warnings, 0 errors, 2 info")


def test_an_error_prints_in_full_with_a_deliverable_or_without():
    err = Diagnostic(level="error", code="BOUND_HIT", message="a ran to its bound",
                     where=["phases.0.cell.a"], suggestion="widen it")
    full = ["    error[BOUND_HIT]: a ran to its bound", "      at: phases.0.cell.a",
            "      help: widen it"]
    bare = _view_lines([err, FAP["FLOOR_HIT"]])
    assert bare[0] == ("  diagnostics: 2 rows, 1 error; no deliverable given, "
                       "so only the error is printed in full")
    assert bare[1:4] == full
    assert bare[4] == ("    FLOOR_HIT at phases.0.extinction: "
                       "warning under qpa, structure, magnetic")
    cell = _view_lines([FAP["FLOOR_HIT"], err], "cell")
    assert cell[0] == "  diagnostics under cell: 0 warnings, 1 error, 1 info"
    assert cell[1:4] == full
    assert "only the errors are printed in full" in _view_lines([err, err])[0]


def test_a_native_info_row_says_so_on_its_one_line():
    note = _d("CAPILLARY_OFFSET_UNAVAILABLE", ["instrument.geometry.goniometer_radius_mm"],
              level="info")
    assert _view_lines([note])[1] == (
        "    CAPILLARY_OFFSET_UNAVAILABLE at instrument.geometry.goniometer_radius_mm: info")
    assert _view_lines([note], "qpa")[1] == (
        "    info: CAPILLARY_OFFSET_UNAVAILABLE at instrument.geometry.goniometer_radius_mm")


def test_paths_print_their_shared_prefix_once():
    from rietx.schemas.results import _compress_paths

    assert _compress_paths(["instrument.profile.u", "instrument.profile.v"]) == \
        "instrument.profile.u, .v"
    # only a sibling shortens; a deeper path, or another branch, prints whole
    assert _compress_paths(["phases.0.cell.a", "instrument.zero_shift",
                            "instrument.geometry.sample_displacement",
                            "instrument.geometry.sample_transparency"]) == \
        ("phases.0.cell.a, instrument.zero_shift, "
         "instrument.geometry.sample_displacement, .sample_transparency")
    assert _compress_paths(["Ca1", "Ca2"]) == "Ca1, Ca2"


def test_zero_diagnostics_is_one_line_under_any_deliverable():
    """WP-1302: the section is present on every fit, empty or not."""
    assert _view_lines([]) == ["  diagnostics: none"]
    assert _view_lines([], "structure") == ["  diagnostics: none"]


def test_the_view_refuses_an_unknown_deliverable_naming_all_eight():
    from rietx.schemas.results import diagnostic_view

    for call in (lambda: diagnostic_view(list(FAP.values()), "cells"),
                 lambda: _view_lines([], "cells")):
        with pytest.raises(ValueError, match="unknown deliverable 'cells'") as err:
            call()
        assert all(repr(p) in str(err.value) for p in PURPOSES)


def test_a_code_still_on_the_response_baseline_keeps_its_level_everywhere():
    """Its pairings are unchecked until an audit gives it a response, so a
    path it names is not read as a claim about which purposes it reaches
    (WP-1076; the generality review of 2026-10-24 found CELL_RUNAWAY read as
    info under structure before this rule)."""
    from rietx import _audit
    assert "CELL_RUNAWAY" in _audit.RESPONSE_BASELINE
    runaway = _d("CELL_RUNAWAY", ["phases.0.cell.a"])
    assert {level_under(runaway, p) for p in PURPOSES} == {"warning"}


# ---------------------------------------------------------------- clause 4
def _result(diagnostics):
    from rietx.schemas.common import Provenance
    from rietx.schemas.results import RefinementResult, Statistics
    return RefinementResult(
        status="converged", mode="rietveld", parameters=[], diagnostics=diagnostics,
        statistics=Statistics(rwp=0.1, rp=0.08, rexp=0.05, chi2=4.0, gof=2.0,
                              n_points=100, n_free_parameters=5),
        provenance=Provenance(package_version="0.0.0+test"))


def _lines_with(diagnostics, deliverable, levels):
    from rietx.schemas.results import _diagnostic_lines
    return _diagnostic_lines(diagnostics, deliverable, levels=levels)


def test_a_callers_levels_replace_the_audited_level_under_every_purpose():
    """``allow`` quiets a code to info, ``warn`` makes it a warning under every
    purpose, ``deny`` an error; the header counts the rows the map set."""
    from rietx.schemas.results import _NAMED_PURPOSES, diagnostic_view

    levels = {"FLOOR_HIT": "allow", "RESOLUTION_UNCONSTRAINED": "deny",
              "PATTERN_UNDERSAMPLED": "warn"}
    for deliverable in (None, "structure", "cell"):
        rows = {r.diagnostic.code: r
                for r in diagnostic_view(list(FAP.values()), deliverable, levels)}
        assert rows["FLOOR_HIT"].level == "info" and not rows["FLOOR_HIT"].full
        assert rows["RESOLUTION_UNCONSTRAINED"].level == "error"
        assert rows["RESOLUTION_UNCONSTRAINED"].full
        assert rows["PATTERN_UNDERSAMPLED"].level == "warning"
        assert rows["PATTERN_UNDERSAMPLED"].warning_under == _NAMED_PURPOSES
        assert rows["SITE_SNAPPED_TO_SPECIAL_POSITION"].override is None
    lines = _lines_with(list(FAP.values()), None, levels)
    assert lines[0] == ("  diagnostics: 4 rows, 1 error; 3 set by levels=; "
                        "no deliverable given, so only the error is printed in full")
    assert lines[1] == "    error[RESOLUTION_UNCONSTRAINED]: m"
    assert "    FLOOR_HIT at phases.0.extinction: info" in lines
    assert "    PATTERN_UNDERSAMPLED: warning under every purpose" in lines
    assert ("    info: FLOOR_HIT at phases.0.extinction"
            in _lines_with(list(FAP.values()), "structure", levels))


def test_a_callers_allow_never_lowers_an_error():
    """Clause 1: an unusable fit is unusable for every purpose and every reader."""
    from rietx.schemas.results import diagnostic_view

    bound = _d("BOUND_HIT", ["phases.0.cell.a"], level="error")
    (row,) = diagnostic_view([bound], "cell", {"BOUND_HIT": "allow"})
    assert (row.level, row.full, row.override) == ("error", True, None)


def test_a_callers_levels_refuse_an_unknown_code_or_word():
    from rietx.schemas.results import diagnostic_view

    with pytest.raises(ValueError, match="unknown diagnostic code.*FLOOR_HITT"):
        diagnostic_view(list(FAP.values()), None, {"FLOOR_HITT": "allow"})
    with pytest.raises(ValueError, match="unknown level.*'ignore'.*'allow', 'warn', 'deny'"):
        diagnostic_view(list(FAP.values()), None, {"FLOOR_HIT": "ignore"})


def test_a_bare_result_can_follow_the_reading_rule():
    """The rule ``str(result)`` closes on names ``summary()``, and a bare
    result has one taking ``deliverable=``: the generality review's (c)."""
    from rietx.schemas.results import DIAGNOSTICS_READING_RULE, RESULT_DELIVERABLE_NOTE

    result = _result(list(FAP.values()))
    assert str(result) == result.summary()
    assert DIAGNOSTICS_READING_RULE in str(result)
    text = result.summary(deliverable="structure").splitlines()
    assert "  diagnostics under structure: 3 warnings, 0 errors, 1 info" in text
    assert "    warning[FLOOR_HIT]: m" in text
    assert f"    {RESULT_DELIVERABLE_NOTE}" in text
    assert DIAGNOSTICS_READING_RULE not in "\n".join(text)
    with pytest.raises(ValueError, match="unknown deliverable"):
        result.summary(deliverable="cells")
    assert "error[FLOOR_HIT]" in result.summary(levels={"FLOOR_HIT": "deny"})


def test_usable_under_a_callers_deny_and_never_above_usable():
    """Clause 4, ruled 2026-10-24: a denied code makes the fit unusable to
    the caller who denied it, ``usable`` itself reads nothing but the result,
    and an override never lifts an error."""
    result = _result(list(FAP.values()))
    assert result.usable and result.usable_under({})
    assert not result.usable_under({"FLOOR_HIT": "deny"})
    assert result.usable, "usable is the result's own reading, never the caller's"
    assert result.usable_under({"FLOOR_HIT": "allow", "PATTERN_UNDERSAMPLED": "warn"})

    bound = _result([_d("MODEL_FAR_FROM_DATA", [], level="error")])
    assert not bound.usable and not bound.usable_under({"MODEL_FAR_FROM_DATA": "allow"})
    stopped = _result(list(FAP.values())).model_copy(update={"status": "max_iter"})
    assert not stopped.usable_under({})
    with pytest.raises(ValueError, match="unknown diagnostic code"):
        result.usable_under({"FLOOR_HITT": "deny"})
