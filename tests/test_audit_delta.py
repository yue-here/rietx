"""CI's audit-table delta (`tests/audit_delta.py`, WP-2014), on synthetic texts."""

from __future__ import annotations

import ast
import dataclasses

from tests import audit_delta as ad


def _table(*rows: str, baseline=(), walked=None, seats=None, other=(),
           not_walked=None) -> str:
    """An ``_audit.py`` text holding only what the reader reads."""
    text = (f"WALKED: dict[str, int] = {walked or {}!r}\n"
            f"DEFAULT_SEATS: dict[str, int] = {seats or {}!r}\n"
            "OTHER_RECORD_FIELDS: frozenset[str] = frozenset({"
            + ", ".join(repr(f) for f in sorted(other)) + "})\n"
            "ROWS: tuple[Row, ...] = (\n"
            + "".join(f"    {r}\n" for r in rows) + ")\n"
            f"UNAUDITED_BASELINE: tuple[str, ...] = {tuple(sorted(baseline))!r}\n")
    if not_walked is not None:
        text += f"NOT_WALKED: dict[str, str] = {not_walked!r}\n"
    return text


def _run(before: str, after: str):
    a, b = ad.read_table(before), ad.read_table(after)
    found = ad.deltas(a, b)
    return found, ad.failures(found), ad.report(found, ad.declarations(a, b), "a base")


def _whys(found) -> list[tuple[str, str]]:
    return [(d.why, d.row.name) for d in found]


def test_a_new_name_at_unaudited_fails_naming_its_row():
    before = _table('Row("KEPT", "code"),', baseline=["KEPT"])
    after = _table('Row("KEPT", "code"),', 'Row("NEW_CODE", "code"),',
                   baseline=["KEPT", "NEW_CODE"])
    found, bad, text = _run(before, after)
    assert _whys(found) == [(ad.NEW_UNAUDITED, "NEW_CODE")]
    (message,) = bad
    assert message.startswith("NEW_CODE (code) is new to rietx._audit.ROWS and arrives "
                              "at 'unaudited' (src/rietx/_audit.py:6).")
    assert "CONTRIBUTING.md § A heuristic needs its tier" in message
    assert "(FAILS)" in text
    assert "UNAUDITED_BASELINE added: NEW_CODE" in text


def test_a_new_name_with_its_tier_is_listed_and_passes():
    after = _table('Row("NEW_CODE", "code", tier=1, ambiguity=3, evidence="physics: x"),')
    found, bad, text = _run(_table(), after)
    assert _whys(found) == [(ad.ADDED, "NEW_CODE")] and bad == []
    assert "  NEW_CODE (code), tier 1, ambiguity 3: physics: x" in text


def test_a_rename_keeps_kind_leaf_and_value_and_passes():
    before = _table('Row("rietx.model.forward.SIGMA", "constant", value=3.0),',
                    'Row("rietx.refine.fit.suggestion", "suggestion", value=1),',
                    'Row("rietx.refine.Refinement.fit:seed", "default", value=0),')
    after = _table('Row("rietx.schemas.plan.SIGMA", "constant", value=3.0),',
                   'Row("rietx.strategy.fit.suggestion", "suggestion", value=1),',
                   'Row("rietx.refine.refine:seed", "default", value=0),')
    found, bad, text = _run(before, after)
    assert bad == []
    assert [(d.why, d.old.name, d.row.name) for d in found] == [
        (ad.RENAMED, "rietx.refine.Refinement.fit:seed", "rietx.refine.refine:seed"),
        (ad.RENAMED, "rietx.model.forward.SIGMA", "rietx.schemas.plan.SIGMA"),
        (ad.RENAMED, "rietx.refine.fit.suggestion", "rietx.strategy.fit.suggestion"),
    ]
    assert "    from rietx.model.forward.SIGMA" in text


def test_a_new_leaf_or_a_new_value_is_a_new_name():
    before = _table('Row("OLD_CODE", "code"),',
                    'Row("rietx.model.forward.SIGMA", "constant", value=3.0),',
                    'Row("rietx.model.forward.TOL", "constant", value=0.1),')
    after = _table('Row("NEW_CODE", "code"),',
                   'Row("rietx.model.forward.SIGMA_MAX", "constant", value=3.0),',
                   'Row("rietx.model.profile.TOL", "constant", value=0.2),')
    found, bad, _ = _run(before, after)
    assert _whys(found) == [
        (ad.NEW_UNAUDITED, "NEW_CODE"),
        (ad.NEW_UNAUDITED, "rietx.model.forward.SIGMA_MAX"),
        (ad.NEW_UNAUDITED, "rietx.model.profile.TOL"),
        (ad.DELETED, "OLD_CODE"),
        (ad.DELETED, "rietx.model.forward.SIGMA"),
        (ad.DELETED, "rietx.model.forward.TOL"),
    ]
    assert len(bad) == 3


def test_a_row_returning_to_unaudited_is_listed_and_passes():
    before = _table('Row("CELL_RUNAWAY", "code", tier=3, ambiguity=1, evidence="WP-1110", '
                    'grounds="B8", approved="2026-10-19"),')
    after = _table('Row("CELL_RUNAWAY", "code"),', baseline=["CELL_RUNAWAY"])
    found, bad, text = _run(before, after)
    assert _whys(found) == [(ad.CHANGED, "CELL_RUNAWAY")] and bad == []
    assert ad.changed_fields(found[0].old, found[0].row) == [
        "tier", "ambiguity", "evidence", "grounds", "approved"]
    assert "tier 3 → unaudited; ambiguity 1 → None; evidence changed" in text


def test_a_response_given_to_a_code_is_listed_and_passes():
    """WP-2037's three fields are a report like any other change, never a failure."""
    before = _table('Row("PATTERN_UNDERSAMPLED", "code"),', baseline=["PATTERN_UNDERSAMPLED"])
    after = _table('Row("PATTERN_UNDERSAMPLED", "code", response="warning", '
                   'responds="do not quote a fraction", scope=("qpa",)),',
                   baseline=["PATTERN_UNDERSAMPLED"])
    found, bad, text = _run(before, after)
    assert _whys(found) == [(ad.CHANGED, "PATTERN_UNDERSAMPLED")] and bad == []
    assert ad.changed_fields(found[0].old, found[0].row) == ["response", "responds", "scope"]
    assert "PATTERN_UNDERSAMPLED (code), tier unaudited, response warning" in text
    assert ("response None → warning; responds changed: do not quote a fraction; "
            "scope () → ('qpa',)") in text


def test_a_deletion_and_a_retune_are_listed_and_pass():
    before = _table('Row("rietx.background.auto.HUMP_TRIGGER", "constant", value=0.05),',
                    'Row("GONE", "code", tier=1, ambiguity=1, evidence="physics"),')
    after = _table('Row("rietx.background.auto.HUMP_TRIGGER", "constant", value=0.04),')
    found, bad, text = _run(before, after)
    assert _whys(found) == [(ad.CHANGED, "rietx.background.auto.HUMP_TRIGGER"),
                            (ad.DELETED, "GONE")] and bad == []
    assert "value 0.05 → 0.04" in text
    assert "Deleted:\n  GONE (code), tier 1, ambiguity 1: physics" in text
    assert text.startswith("Audit table delta, measured against a base: 0 added, "
                           "0 renamed, 1 changed, 1 deleted, 0 new at 'unaudited'.")


def test_a_constant_in_a_file_the_base_did_not_walk_passes():
    before = _table(walked={"refine.py": 2002, "io/readers.py": 2006})
    after = _table('Row("rietx.solve.cost.NAMED_REFLECTIONS", "constant", value=5),',
                   'Row("rietx.io.formats.base.WIDTH", "constant", value=8),',
                   'Row("rietx.io.readers.NEW_STEP", "constant", value=0.5),',
                   'Row("rietx.refine.NEW_TOL", "constant", value=0.1),',
                   walked={"refine.py": 2002, "io": 2006, "solve": 2007})
    found, bad, text = _run(before, after)
    assert [(d.why, d.row.name, d.via) for d in found] == [
        (ad.NEW_UNAUDITED, "rietx.io.readers.NEW_STEP", ""),
        (ad.NEW_UNAUDITED, "rietx.refine.NEW_TOL", ""),
        (ad.OPENED, "rietx.io.formats.base.WIDTH", "io"),
        (ad.OPENED, "rietx.solve.cost.NAMED_REFLECTIONS", "solve"),
    ]
    assert len(bad) == 2
    assert "with the walk's new entry solve" in text
    assert "WALKED added: io, solve" in text and "WALKED removed: io/readers.py" in text


def test_a_default_at_a_new_seat_passes_and_at_an_old_one_fails():
    before = _table(seats={"rietx.refine.refine": 2002})
    after = _table('Row("rietx.refine.refine:new_flag", "default", value=False),',
                   'Row("rietx.solve.solve:budget", "default", value=60.0),',
                   seats={"rietx.refine.refine": 2002, "rietx.solve.solve": 2007})
    found, bad, text = _run(before, after)
    assert [(d.why, d.row.name, d.via) for d in found] == [
        (ad.NEW_UNAUDITED, "rietx.refine.refine:new_flag", ""),
        (ad.OPENED, "rietx.solve.solve:budget", "rietx.solve.solve"),
    ]
    assert len(bad) == 1
    assert "with the new seat rietx.solve.solve" in text


def test_a_walk_or_seat_opened_over_new_code_exempts_nothing():
    """The exemption is for code the base already held: a module made in the
    change and placed in WALKED still enters its numbers with their tiers."""
    before = _table(seats={})
    after = _table('Row("rietx.newmod.CUTOFF", "constant", value=0.5),',
                   'Row("rietx.solve.cost.NAMED_REFLECTIONS", "constant", value=5),',
                   'Row("rietx.newmod.run:budget", "default", value=60.0),',
                   walked={"newmod.py": 2007, "solve": 2007},
                   seats={"rietx.newmod.run": 2007})
    a, b = ad.read_table(before), ad.read_table(after)
    found = ad.deltas(a, b, lambda row: not row.name.startswith("rietx.newmod."))
    assert [(d.why, d.row.name) for d in found] == [
        (ad.NEW_UNAUDITED, "rietx.newmod.CUTOFF"),
        (ad.NEW_UNAUDITED, "rietx.newmod.run:budget"),
        (ad.OPENED, "rietx.solve.cost.NAMED_REFLECTIONS"),
    ]
    assert len(ad.failures(found)) == 2


def test_defines_reads_assignments_definitions_and_imports():
    text = ("from .cost import misfit as score\nimport numpy\nLIMIT: int = 5\n"
            "def run(budget=60.0):\n    INNER = 1\nclass Spec:\n    pass\n")
    assert all(ad._defines(text, n) for n in ("score", "numpy", "LIMIT", "run", "Spec"))
    assert not any(ad._defines(text, n) for n in ("misfit", "INNER", "budget"))


def test_a_value_literal_eval_cannot_read_is_compared_as_its_text():
    row = 'Row("rietx.model.x.CAP", "constant", value=float("inf")),'
    table = ad.read_table(_table(row, 'Row("rietx.model.x.SPAN", "constant", '
                                      'value=(0.0, float("inf"))),'))
    assert repr(table.rows["rietx.model.x.CAP"].value) == "float('inf')"
    assert repr(table.rows["rietx.model.x.SPAN"].value) == "(0.0, float('inf'))"
    found, bad, text = _run(_table(row), _table(row.replace('"inf"', '"-inf"')))
    assert _whys(found) == [(ad.CHANGED, "rietx.model.x.CAP")] and bad == []
    assert "value float('inf') → float('-inf')" in text
    assert _run(_table(row), _table(row))[0] == []


def test_each_declaration_is_listed_and_one_absent_at_the_base_reads_empty():
    before = _table(baseline=["A", "B"], other=["S.f"], walked={"model": 2002})
    after = _table(baseline=["B", "C"], other=["S.f", "S.g"], walked={"model": 2003},
                   not_walked={"gui": "ports"})
    a, b = ad.read_table(before), ad.read_table(after)
    assert a.not_walked == {}
    assert ad.declarations(a, b) == [
        ("UNAUDITED_BASELINE", "added", ["C"]),
        ("UNAUDITED_BASELINE", "removed", ["A"]),
        ("OTHER_RECORD_FIELDS", "added", ["S.g"]),
        ("WALKED", "changed", ["model"]),
        ("NOT_WALKED", "added", ["gui"]),
    ]
    text = ad.report([], ad.declarations(a, b), "a base", markdown=True)
    assert "- `UNAUDITED_BASELINE` added: `C`" in text


def test_an_unchanged_table_prints_one_line():
    text = _table('Row("KEPT", "code"),', baseline=["KEPT"])
    _, bad, report = _run(text, text)
    assert bad == []
    assert report == "Audit table delta, measured against a base: no row or declaration changed."


def test_the_reader_agrees_with_the_import():
    """The AST read of the working tree's table against what it holds at import."""
    from rietx import _audit

    assert ad.FIELDS == tuple(f.name for f in dataclasses.fields(_audit.Row))
    assert ad.VALUED == _audit._VALUED
    assert {f.name: f.default for f in dataclasses.fields(_audit.Row)} == {
        f.name: f.default for f in dataclasses.fields(ad.Row) if f.name != "line"}

    def as_written(value: object) -> object:
        # the live value as the reader reads the text `_audit._literal` writes
        return ad._value(ast.parse(_audit._literal(value), mode="eval").body)

    text = (ad.ROOT / ad.TABLE).read_text(encoding="utf-8")
    table = ad.read_table(text)
    lines = text.splitlines()
    assert list(table.rows) == [row.name for row in _audit.ROWS]
    for row in _audit.ROWS:
        read = table.rows[row.name]
        for field in ad.FIELDS:
            assert _audit.same(getattr(read, field), as_written(getattr(row, field))), (
                row.name, field)
        assert lines[read.line - 1].lstrip().startswith(f'Row("{row.name}"'), row.name
    assert table.baseline == frozenset(_audit.UNAUDITED_BASELINE)
    assert table.walked == _audit.WALKED
    assert table.not_walked == _audit.NOT_WALKED
    assert table.seats == _audit.DEFAULT_SEATS
    assert table.schemas == frozenset(_audit.RECORD_SCHEMAS)
    assert table.other_fields == _audit.OTHER_RECORD_FIELDS


def test_an_empty_frozenset_reads_as_empty():
    text = _table().replace("frozenset({})", "frozenset()")
    assert "frozenset()" in text
    assert ad.read_table(text).other_fields == frozenset()
