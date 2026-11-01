"""#1123's follow-ups: what a formula input refuses and what it reads.

``rietx index`` refuses an unreadable formula, a temperature that is not a
positive finite number of kelvin, and a ``--temperature`` that would change
nothing, as usage errors before it reads the pattern.  ``D`` reads as H, and
a non-finite temperature is refused wherever a formula's volume is computed.
"""

from __future__ import annotations

import math

import pytest

from rietx.crystallography.atomic_volume import formula_unit_volume
from rietx.indexing.engines import SearchSpec


@pytest.fixture
def no_pattern_read(monkeypatch):
    """The pattern is never opened: every refusal below comes before it."""
    import rietx.io.readers as readers

    def refuse(*_args, **_kwargs):
        raise AssertionError("the pattern was read before the refusal")

    monkeypatch.setattr(readers, "read_pattern", refuse)


@pytest.mark.parametrize("extra,named", [
    (["--formula", "CuSO4.5H2O"], "reads two ways"),
    (["--formula", "Qq2"], "not an element"),
    (["--formula", "ZnO", "--temperature", "0"], "positive, finite"),
    (["--formula", "ZnO", "--temperature", "-5"], "positive, finite"),
    (["--formula", "ZnO", "--temperature", "inf"], "positive, finite"),
    (["--formula", "ZnO", "--temperature", "nan"], "positive, finite"),
    (["--temperature", "100"], "give --formula too"),
])
def test_the_cli_refuses_a_bad_formula_input_as_a_usage_error(
        extra, named, no_pattern_read, capsys):
    from rietx.cli import main

    with pytest.raises(SystemExit) as stop:
        main(["index", "pattern.xy", "--wavelength", "1.5405929", *extra])
    assert stop.value.code == 2
    err = capsys.readouterr().err
    assert "rietx index: error:" in err
    assert named in err
    assert "Traceback" not in err


@pytest.mark.parametrize("formula,as_hydrogen", [
    ("C6D6", "C6H6"),
    ("CD3OD", "CH3OH"),
    ("CuSO4·5D2O", "CuSO4·5H2O"),
])
def test_deuterium_reads_as_hydrogen(formula, as_hydrogen):
    assert formula_unit_volume(formula) == formula_unit_volume(as_hydrogen)


def test_a_full_stop_deuterate_still_reads_two_ways():
    # D2O is on the adduct list, so its full stop is refused as H2O's is
    with pytest.raises(ValueError, match="reads two ways"):
        formula_unit_volume("CuSO4.5D2O")


@pytest.mark.parametrize("temperature", [math.inf, -math.inf, math.nan, 0.0, -1.0])
def test_a_temperature_that_is_not_positive_finite_kelvin_is_refused(temperature):
    with pytest.raises(ValueError, match="positive, finite"):
        formula_unit_volume("C7H6O2", temperature)
    with pytest.raises(ValueError, match="positive, finite"):
        SearchSpec.from_formula("C7H6O2", z=4, temperature=temperature)
