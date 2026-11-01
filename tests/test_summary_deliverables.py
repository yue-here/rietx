"""The four deliverables WP-2037 adds to ``summary(deliverable=…)``: ``cell``,
``microstructure``, ``calibration``, ``magnetic``.

Each block is a projection of fields the result already carries, so these
tests check which rows print and what an absent measurement says, never a
re-derivation of the numbers.  One fit is shared (the termination view's
synthetic LaB6, about two seconds); the cases it cannot reach — a moment, a
held cell, ``RESOLUTION_UNCONSTRAINED`` — are the same result with fields
edited, since each row reads a field and nothing else.
"""

from __future__ import annotations

import copy

import pytest

from rietx.purposes import PURPOSES
from rietx.schemas.common import Diagnostic
from rietx.schemas.results import DELIVERABLES, RefinedParameter
from tests.test_termination_view import _fit, _series_result

pytestmark = pytest.mark.xdist_group("summary-deliverables")

NEW = ("cell", "microstructure", "calibration", "magnetic")


@pytest.fixture(scope="module")
def fitted():
    ref, result = _fit()
    return ref, result, ref.report()


def _rows(fitted, deliverable, **update) -> str:
    """The deliverable block for the shared fit's result with ``update``
    applied, on a copy so the module's fit is never edited."""
    ref, result, report = fitted
    view = copy.copy(ref)
    view.result_ = result.model_copy(update=update)
    return "\n".join(view._deliverable_lines(deliverable, report))


def test_the_deliverables_are_the_purpose_table():
    assert DELIVERABLES == tuple(PURPOSES)
    assert set(NEW) <= set(DELIVERABLES)


@pytest.mark.parametrize("deliverable", NEW)
def test_each_new_deliverable_prints_its_own_block(fitted, deliverable):
    ref, _result, report = fitted
    text = ref.summary(deliverable=deliverable, report=report)
    assert f"  deliverable: {deliverable}\n" in text


def test_an_unknown_deliverable_is_refused_naming_all_eight(fitted):
    ref, _result, report = fitted
    with pytest.raises(ValueError, match="unknown deliverable") as err:
        ref.summary(deliverable="cells", report=report)
    for name in PURPOSES:
        assert repr(name) in str(err.value)


def test_cell_prints_the_refined_cell_its_ties_and_the_exchange_rows(fitted):
    text = _rows(fitted, "cell")
    assert "phases.0.cell: a = 4.15660" in text
    assert "(b, c tied)" in text and "Å³" in text
    assert "exchangeability:" in text


def test_cell_says_when_no_cell_parameter_refined(fitted):
    _ref, result, _report = fitted
    held = [p for p in result.parameters if ".cell." not in p.path]
    text = _rows(fitted, "cell", parameters=held, identifiability=None)
    assert "no cell parameter refined" in text
    assert "identifiability: not measured on this result" in text


def test_microstructure_prints_each_phases_readings(fitted):
    text = _rows(fitted, "microstructure")
    assert "PhaseMicrostructure:" in text and "phases.0.lor_size" in text


def test_microstructure_is_not_quotable_under_resolution_unconstrained(fitted):
    """The caveat heads the block and the readings stay beneath it: a
    withheld verdict leaves its statistic (DESIGN.md § Rules, 1)."""
    _ref, result, _report = fitted
    ru = Diagnostic(level="warning", code="RESOLUTION_UNCONSTRAINED", message="m",
                    where=["instrument.profile.u"])
    text = _rows(fitted, "microstructure", diagnostics=[*result.diagnostics, ru])
    caveat = "size and strain: not quotable (RESOLUTION_UNCONSTRAINED)"
    assert caveat in text and "PhaseMicrostructure:" in text
    assert text.index(caveat) < text.index("PhaseMicrostructure:")


def test_microstructure_says_when_nothing_measured_it(fitted):
    text = _rows(fitted, "microstructure", microstructure=[])
    assert "microstructure: not measured on this result" in text


def test_calibration_lists_the_instrument_terms_and_flags_a_refined_cell(fitted):
    text = _rows(fitted, "calibration")
    assert "instrument.zero_shift" in text and "instrument.profile.w" in text
    assert "instrument.background." not in text
    # names the phase rather than ordering it held: an internal standard's
    # sample refines its own cell while the standard's is held
    assert "cell refined on phases.0:" in text and "Refinement.hold" in text
    assert "a sample's may refine" in text


def test_calibration_with_the_cell_held_says_so(fitted):
    _ref, result, _report = fitted
    held = [p for p in result.parameters if ".cell." not in p.path]
    assert "cell: held on every phase" in _rows(fitted, "calibration", parameters=held)


def test_magnetic_says_when_the_fit_refined_no_moment(fitted):
    assert "moment: none refined on this fit" in _rows(fitted, "magnetic")


def test_magnetic_prints_the_moment_rows_and_the_stage_holds(fitted):
    _ref, result, _report = fitted
    site = "phases.0.atoms.0"
    moments = [RefinedParameter(path=f"{site}.moment.dof0", value=3.09, stderr=0.01),
               RefinedParameter(path=f"{site}.moment.dof1", value=0.95, stderr=0.02)]
    last = result.stages[-1].model_copy(update={
        "held": [f"{site}.moment.dof2"],
        "moment_flat_axes": {site: [0.57735, 0.57735, 0.57735]},
        "moment_turned": [site]})
    text = _rows(fitted, "magnetic", parameters=[*result.parameters, *moments],
                 stages=[*result.stages[:-1], last])
    assert f"{site}.moment.dof0  3.090(10)" in text
    assert f"held, not measured: {site}.moment.dof2" in text
    assert f"{site}: azimuth held about [0.577, 0.577, 0.577]" in text
    assert "turned onto the meridian" in text


def test_cell_reads_only_the_exchange_rows_that_name_a_cell(fitted):
    """A cell is decided by what trades against it, so a Biso row that the
    structure block would lead with is left out of the cell block."""
    from rietx.schemas.results import ExchangeRow

    _ref, result, _report = fitted
    rows = [ExchangeRow(held="phases.0.atoms.0.biso", r2=0.99,
                        partners={"phases.0.scale": 0.9}),
            ExchangeRow(held="instrument.geometry.sample_displacement", r2=0.98,
                        partners={"phases.0.cell.a": 0.9, "instrument.zero_shift": 0.8})]
    ident = result.identifiability.model_copy(update={"exchangeability": rows})
    cell = _rows(fitted, "cell", identifiability=ident)
    assert "exchangeability: 1 row(s) naming a cell path" in cell
    assert "sample_displacement ~" in cell and "biso ~" not in cell
    structure = _rows(fitted, "structure", identifiability=ident)
    assert "exchangeability: 2 row(s)" in structure and "biso ~" in structure


@pytest.mark.parametrize("deliverable", NEW)
def test_a_series_refuses_each_new_deliverable_naming_refinement_summary(deliverable):
    with pytest.raises(ValueError, match="decided on one pattern") as err:
        _series_result().summary(deliverable=deliverable)
    assert f"Refinement.summary(deliverable={deliverable!r})" in str(err.value)


def test_the_summary_and_the_bare_result_print_the_one_view(fitted):
    """WP-2037 clause 3 on a real fit: ``summary(deliverable=…)`` prints the
    view under that purpose, ``str(result)`` the view with none, and both are
    the one text form."""
    from rietx.schemas.results import _diagnostic_lines

    ref, result, report = fitted
    assert result.diagnostics, "the shared fit stopped producing any — pick another"
    under = "\n".join(_diagnostic_lines(result.diagnostics, "structure"))
    assert under.startswith("  diagnostics under structure: ")
    assert f"\n{under}\n" in ref.summary(deliverable="structure", report=report)
    bare = "\n".join(_diagnostic_lines(result.diagnostics))
    assert "no deliverable given" in bare.splitlines()[0]
    assert f"\n{bare}\n" in str(result)
    assert f"\n{bare}\n" in ref.summary(report=report)
