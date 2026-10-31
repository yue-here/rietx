"""The report's one sentence on numbers no independent measurement validates.

WP-2010 (DESIGN.md § Rules, 2): a result that reports a number from a feature
with no independent measurement says so once, naming each such number, and the
state is read from ``rietx.features``.  The registry itself, and its bit held to
the validation matrix, are guarded in ``tests/test_validation_matrix.py``.
"""

from __future__ import annotations

from rietx.features import FEATURES, feature_of, parameters_without_independent_measurement
from rietx.report import build_report, not_independently_measured
from rietx.schemas.results import RefinedParameter
from tests.test_fitreport_layers import _result_for, _truth


def test_a_path_reaches_its_feature_through_its_help_family():
    assert feature_of("phases.0.atoms.2.biso") == "displacement_parameters"
    assert feature_of("phases.1.cell.a") == "lattice_metric"
    assert feature_of("phases.0.atoms.0.moment.dof0") == "magnetic_structure"
    # ``vars.*`` is a name the caller defines, not a feature, and a path no
    # family claims has none: neither is called validated or unvalidated
    assert feature_of("vars.k") is None
    assert feature_of("not.a.path") is None


def test_each_unvalidated_number_is_named_once_and_validated_ones_not_at_all():
    paths = ["phases.0.cell.a", "phases.0.atoms.0.biso", "phases.0.atoms.1.biso",
             "phases.0.atoms.0.biso", "phases.0.atoms.0.moment.dof0",
             "phases.0.scale", "vars.k"]
    groups = parameters_without_independent_measurement(paths)
    assert groups == {
        "displacement_parameters": ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"],
        "magnetic_structure": ["phases.0.atoms.0.moment.dof0"],
    }
    sentence = not_independently_measured(paths)
    assert sentence.count("phases.0.atoms.0.biso") == 1
    assert FEATURES["magnetic_structure"].title in sentence
    assert "phases.0.cell.a" not in sentence and "phases.0.scale" not in sentence


def test_a_report_of_validated_numbers_only_carries_no_sentence():
    """Absent, not a sentence saying everything is fine: the negative arm."""
    assert not_independently_measured(["phases.0.cell.a", "phases.0.scale",
                                       "instrument.zero_shift"]) == ""
    assert not_independently_measured([]) == ""


def test_the_derived_blocks_are_named_by_their_field():
    sentence = not_independently_measured([], geometry=True, microstructure=True)
    assert "FitReport.geometry" in sentence
    assert "FitReport.microstructure" in sentence


def test_the_report_carries_the_sentence_and_prints_it_once():
    """End to end through ``build_report``: the field is written from the
    result's own refined parameters, and ``str`` shows it on one line."""
    structure, ins, data = _truth()
    result, _, _ = _result_for(structure, ins, data)
    result.parameters = [
        RefinedParameter(path="phases.0.cell.a", value=4.1569, stderr=1e-5),
        RefinedParameter(path="phases.0.atoms.0.biso", value=0.2, stderr=0.01),
        RefinedParameter(path="instrument.profile.u", value=3e-3, stderr=1e-4),
    ]
    report = build_report(result)
    assert "phases.0.atoms.0.biso" in report.not_independently_measured
    assert "instrument.profile.u" in report.not_independently_measured
    assert "phases.0.cell.a" not in report.not_independently_measured
    printed = str(report).splitlines()
    assert sum(report.not_independently_measured in line for line in printed) == 1

    result.parameters = result.parameters[:1]
    assert build_report(result).not_independently_measured == ""
