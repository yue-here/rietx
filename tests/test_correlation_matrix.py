"""The full correlation matrix on the result, and its export (WP-1990).

Unit tests for the packing first; then one real fit, shared by the tests that
need it, which is the LaB6 pattern of ``test_high_correlation_dedup.py`` under
the default plan (about a second).  It holds the three claims the field makes:
it is the matrix the solver handed the guard, the pairs quoted elsewhere are
its entries bit for bit, and it survives a JSON round trip.  The joint-fit
``None`` is asserted in ``test_joint_report.py``, on the fit that file already
pays for.
"""

from __future__ import annotations

import csv

import numpy as np
import pytest
from pydantic import ValidationError

from rietx.io.exporters import correlation_table_csv, write_correlation_table
from rietx.schemas.common import Provenance
from rietx.schemas.results import (
    CorrelationMatrix,
    Identifiability,
    RefinementResult,
    Statistics,
    _cap_high_correlation,
)

PATHS = ["phases.0.scale", "phases.0.cell.a", "instrument.zero_shift"]
SQUARE = np.array([[1.0, -0.25, 0.5],
                   [-0.25, 1.0, np.nan],
                   [0.5, np.nan, 1.0]])


def test_a_square_packs_to_its_lower_triangle_and_back():
    c = CorrelationMatrix.from_square(PATHS, SQUARE)
    # row by row, diagonal included: (0,0) (1,0) (1,1) (2,0) (2,1) (2,2)
    assert c.lower == [1.0, -0.25, 1.0, 0.5, None, 1.0]
    np.testing.assert_array_equal(c.matrix(), SQUARE)
    assert c.rho("phases.0.cell.a", "phases.0.scale") == -0.25
    assert c.rho("phases.0.scale", "phases.0.cell.a") == -0.25
    assert c.rho("phases.0.cell.a", "instrument.zero_shift") is None


def test_each_entry_is_read_from_the_upper_half_the_guard_reads():
    """A correlation formed in floating point is symmetric to an ulp, and
    the guard reads ``corr[i, j]`` with i < j: the packed entry is that one."""
    m = np.array([[1.0, 0.3], [0.30000000000000004, 1.0]])
    assert CorrelationMatrix.from_square(PATHS[:2], m).lower[1] == 0.3


def test_a_triangle_that_does_not_fit_its_paths_is_refused():
    with pytest.raises(ValidationError, match="holds 6 entries, not 5"):
        CorrelationMatrix(paths=PATHS, lower=[1.0, 0.0, 1.0, 0.0, 1.0])
    with pytest.raises(ValueError, match="over 3 paths"):
        CorrelationMatrix.from_square(PATHS, np.eye(2))


def test_a_path_that_was_not_free_is_named():
    c = CorrelationMatrix.from_square(PATHS, SQUARE)
    with pytest.raises(KeyError, match="phases.0.atoms.0.biso"):
        c.rho("phases.0.scale", "phases.0.atoms.0.biso")


def test_the_table_is_a_labelled_square_with_blank_undetermined_cells(tmp_path):
    c = CorrelationMatrix.from_square(PATHS, SQUARE)
    out = tmp_path / "rho.csv"
    write_correlation_table(c, out)
    rows = list(csv.reader(out.open(newline="", encoding="utf-8")))
    assert rows[0] == ["path", *PATHS]
    assert [r[0] for r in rows[1:]] == PATHS
    assert rows[1][1:] == ["1", "-0.25", "0.5"]
    assert rows[2][1:] == ["-0.25", "1", ""]
    # no blank line between rows (the \r\r\n of WP-1002)
    assert out.read_bytes().count(b"\r\n") == len(PATHS) + 1

    tsv = tmp_path / "rho.tsv"
    write_correlation_table(c, tsv)
    assert tsv.read_text(encoding="utf-8").splitlines()[0].split("\t")[0] == "path"


def _bare_result(identifiability=None) -> RefinementResult:
    return RefinementResult(
        status="converged", mode="rietveld", parameters=[],
        statistics=Statistics(rwp=0.1, rp=0.08, rexp=0.05, chi2=4.0, gof=2.0,
                              n_points=100, n_free_parameters=3),
        provenance=Provenance(package_version="0.0.0+test"),
        identifiability=identifiability)


def test_a_result_that_carries_no_matrix_is_refused_by_name():
    with pytest.raises(ValueError, match="not measured"):
        correlation_table_csv(_bare_result())
    with pytest.raises(ValueError, match="not measured"):
        correlation_table_csv(_bare_result(Identifiability()))


def _resolve(dotted: str) -> None:
    """Walk ``result.a.b`` through the schema's declared fields, so a name
    that exists only on a populated result still has to be declared."""
    import typing

    from pydantic import BaseModel

    cls = RefinementResult
    for attr in dotted.split(".")[1:]:
        assert cls is not None and attr in cls.model_fields, (
            f"{dotted}: {attr!r} is not a field of {getattr(cls, '__name__', cls)}")
        ann = cls.model_fields[attr].annotation
        models = [a for a in (typing.get_args(ann) or (ann,))
                  if isinstance(a, type) and issubclass(a, BaseModel)]
        cls = models[0] if models else None


def test_the_omitted_rows_suggestion_names_a_field_that_exists():
    """The defect WP-1990 was filed for: the suggestion said
    ``result.identifiability`` carried a full correlation matrix, and it
    carried five pairs.  Each omitted-count row must now name the matrix by
    its field, and every attribute it names must be declared."""
    import re

    diags = [_corr_diag(f"a{i}", f"b{i}", 0.9 + i * 0.001) for i in range(12)]
    rows = [d for d in _cap_high_correlation(diags)
            if d.code.endswith("_OMITTED")]
    assert rows
    for row in rows:
        named = re.findall(r"result(?:\.\w+)+", row.suggestion)
        assert "result.identifiability.correlation" in named, row.suggestion
        for dotted in named:
            _resolve(dotted)


def _corr_diag(a: str, b: str, rho: float):
    from rietx.schemas.common import Diagnostic

    return Diagnostic(level="warning", code="HIGH_CORRELATION",
                      message=f"{a} ~ {b} (ρ={rho:+.3f})", where=[a, b], value=rho,
                      suggestion="consider fixing one of the correlated parameters")


# --- one real fit ----------------------------------------------------------


@pytest.fixture(scope="module")
def lab6_fit():
    """The default plan on the dedup file's LaB6 pattern, with the outcome
    the answer's guard was handed captured on the way past."""
    import importlib

    import rietx as rx
    from rietx.schemas.instrument import Instrument
    from tests.test_high_correlation_dedup import _lab6_pattern
    from tests.test_schemas import make_lab6

    # ``rietx.refine`` the attribute is the function; the module is imported
    refine_mod = importlib.import_module("rietx.refine")
    seen = []
    real = refine_mod.check_guards

    def spy(table, outcome, *args, **kw):
        seen.append((list(table.free_paths), outcome.correlation))
        return real(table, outcome, *args, **kw)

    mp = pytest.MonkeyPatch()
    mp.setattr(refine_mod, "check_guards", spy)
    try:
        ref = rx.Refinement(make_lab6(),
                            Instrument.debye_scherrer(wavelength=1.5406),
                            history=False)
        result = ref.fit(_lab6_pattern())
    finally:
        mp.undo()
    return ref, result, seen[-1]


def test_the_field_is_the_solvers_matrix_at_the_answer(lab6_fit):
    _, result, (free, solver_corr) = lab6_fit
    c = result.identifiability.correlation
    assert c.paths == free
    # nothing on this fit is unresolved (WP-2050), so the projection is the
    # identity and the field is the solver's matrix, entry for entry
    assert None not in c.lower
    assert c == CorrelationMatrix.from_square(free, solver_corr)


def test_every_pair_quoted_elsewhere_is_an_entry_bit_for_bit(lab6_fit):
    _, result, _ = lab6_fit
    c = result.identifiability.correlation
    for pair in result.identifiability.top_correlations:
        assert c.rho(pair.path_a, pair.path_b) == pair.rho
    for d in result.diagnostics:
        if d.code == "HIGH_CORRELATION":
            assert c.rho(*d.where) == d.value


def test_the_matrix_survives_a_json_round_trip(lab6_fit):
    _, result, _ = lab6_fit
    back = RefinementResult.model_validate_json(result.model_dump_json())
    assert back.identifiability.correlation == result.identifiability.correlation


def test_a_refinement_writes_its_matrix_in_one_call(lab6_fit, tmp_path):
    ref, result, _ = lab6_fit
    out = tmp_path / "rho.csv"
    ref.write_correlation_table(out)
    rows = list(csv.reader(out.open(newline="", encoding="utf-8")))
    paths = result.identifiability.correlation.paths
    assert rows[0] == ["path", *paths]
    m = np.array([[float(v) for v in r[1:]] for r in rows[1:]])
    np.testing.assert_allclose(m, result.identifiability.correlation.matrix(),
                               rtol=1e-7, atol=1e-8)
