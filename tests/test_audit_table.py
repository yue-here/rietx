"""WP-2001 — the generality audit table, held equal to the tree both ways.

``rietx._audit`` is the table, and its docstring says what each kind of row
is and why the growth guard in the suite reads no git.  A failure here
prints the row to add or change.  A new item enters with its tier and
evidence, never at ``unaudited``: ``UNAUDITED_BASELINE`` lists the rows still
waiting for their audit, and CI's ``tests/audit_delta.py`` fails a name new
to the table that arrives there.  An edit to the table goes to the
``generality-review`` agent, from ``/wp-handover`` step 7 on a WP branch and
``/pr-review`` on an outside pull request.

A code row also carries the response its reader owes it (WP-2037), held to
every raise site's level, and ``rietx.purposes`` the table a code's level
under a purpose is derived from; ``RESPONSE_BASELINE`` lists the code rows
still without a response.
"""

from __future__ import annotations

import datetime
import fnmatch
import importlib.util
import pathlib
import re
import typing

import pytest

from rietx import _audit, purposes

ROWS = {row.name: row for row in _audit.ROWS}
ROOT = pathlib.Path(__file__).resolve().parent.parent

#: The purposes WP-2037 opened the table with.  A new purpose is one row in
#: ``rietx.purposes.PURPOSES`` and one name here.
PURPOSE_NAMES = ("phase_id", "qpa", "structure", "series", "cell", "microstructure",
                 "calibration", "magnetic")


@pytest.fixture(scope="module")
def walked():
    return {"code": dict.fromkeys(_audit.codes()), "constant": _audit.constants(),
            "default": _audit.defaults(), "suggestion": _audit.suggestions()}


@pytest.fixture(scope="module")
def raised():
    """Every code's raise sites, from ``docs/reference_pages.diagnostic_index``,
    the walk ``tests/test_help.py`` holds the help registry's codes to."""
    spec = importlib.util.spec_from_file_location(
        "_reference_pages", ROOT / "docs" / "reference_pages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.diagnostic_index()


def _site(raised, code: str) -> dict[str, set]:
    return raised.get(code, {"levels": set(), "files": set(), "where": set()})


#: What every failure that asks for a new row says after its count.
NEW_ROW = ("Give each a tier and the evidence for it, and state the kind of "
           "ambiguity where the row asks for one (docs/milestones/generality.md "
           "§ The rule; CONTRIBUTING.md § A heuristic needs its tier).  A name new to "
           "the table may not enter at 'unaudited', and CI's audit-delta step fails "
           "one that does.  Replace each '?', write the evidence, and paste:\n")


#: What a failure asking for a new code row adds (WP-2037).
NEW_CODE = ("A code also states its response (the level every raise site passes), one "
            "sentence on what the reader does, and, where no raise site passes a where, "
            "the purposes it bears on as its scope (rietx._audit's docstring).  ")


def _enter(missing: dict[str, object], kind: str) -> str:
    lines = "\n".join(_audit.row_source(name, kind, value)
                      for name, value in sorted(missing.items()))
    return (f"{len(missing)} {kind}(s) with no row in rietx._audit.ROWS.  "
            + (NEW_CODE if kind == "code" else "") + NEW_ROW + lines)


def test_row_names_are_unique():
    names = [row.name for row in _audit.ROWS]
    assert len(names) == len(set(names)), sorted(n for n in set(names) if names.count(n) > 1)


def test_every_row_is_well_formed():
    for row in _audit.ROWS:
        assert row.kind in _audit.KINDS, row
        # True == 1, so membership alone would admit a bool as tier 1
        assert row.tier in _audit.TIERS and not isinstance(row.tier, bool), row
        if row.ambiguity is not None:
            assert row.ambiguity in (1, 2, 3) and not isinstance(row.ambiguity, bool), row
            assert row.kind in ("code", "action", "default", "suggestion"), (
                f"{row.name}: ambiguity is stated on code, action, default and suggestion rows")
        if row.kind in ("code", "action"):
            assert row.value is None, f"{row.name}: a {row.kind} row stores no value"
        if row.approved is not None:
            datetime.date.fromisoformat(row.approved)
        assert row.response is None or row.response in _audit.RESPONSES, (
            f"{row.name}: response {row.response!r} is none of {_audit.RESPONSES}")
        assert isinstance(row.responds, str) and isinstance(row.scope, tuple), row
    from rietx.schemas.common import Diagnostic

    levels = typing.get_args(Diagnostic.model_fields["level"].annotation)
    assert set(_audit.RESPONSES) == set(levels), "a response is a Diagnostic level"


@pytest.mark.parametrize("kind", ["code", "constant", "default", "suggestion"])
def test_rows_of_each_walked_kind_are_the_tree_both_ways(kind, walked):
    """A new code, constant, default or suggestion site fails until it has a row."""
    live = walked[kind]
    rows = {name: row for name, row in ROWS.items() if row.kind == kind}
    missing = {name: live[name] for name in live.keys() - rows.keys()}
    assert not missing, _enter(missing, kind)
    gone = sorted(rows.keys() - live.keys())
    assert not gone, (f"{kind} rows naming nothing in the tree; delete each row and its "
                      f"UNAUDITED_BASELINE line, or rename it if the item moved: {gone}")


@pytest.mark.parametrize("kind", ["constant", "default", "suggestion"])
def test_a_valued_row_holds_the_live_value(kind, walked):
    """A retune fails, so the row's audit reopens with it."""
    moved = [f"{name}: table {row.value!r}, tree {walked[kind][name]!r}"
             for name, row in ROWS.items()
             if row.kind == kind and name in walked[kind]
             and not _audit.same(row.value, walked[kind][name])]
    assert not moved, (f"{kind} value(s) changed; update each row's value, and its "
                       "tier if the evidence was measured at the old one:\n"
                       + "\n".join(moved))


def test_every_record_field_is_an_action_row_or_declared_other():
    """A new field on a record schema (StageResult, SeriesEntry, RefinementResult,
    Statistics) fails until placed."""
    fields = set(_audit.record_fields())
    actions = {name for name, row in ROWS.items() if row.kind == "action"}
    assert not actions - fields, f"action rows naming no record field: {sorted(actions - fields)}"
    assert not actions & _audit.OTHER_RECORD_FIELDS, sorted(actions & _audit.OTHER_RECORD_FIELDS)
    stale = _audit.OTHER_RECORD_FIELDS - fields
    assert not stale, f"OTHER_RECORD_FIELDS names no field: {sorted(stale)}"
    new = sorted(fields - actions - _audit.OTHER_RECORD_FIELDS)
    assert not new, ("record field(s) neither an action row nor in OTHER_RECORD_FIELDS.  "
                     "A field reporting what the package did on its own is an action.  "
                     + NEW_ROW
                     + "\n".join(_audit.row_source(name, "action") for name in new))


def test_the_indexing_records_are_walked():
    """#1123's follow-up: the lab-source check decides what a peak list records,
    so the walk reaches IndexingResult and PeakList and that field is an action."""
    assert {"rietx.schemas.indexing.IndexingResult",
            "rietx.schemas.indexing.PeakList"} <= set(_audit.RECORD_SCHEMAS)
    row = ROWS["rietx.schemas.indexing.PeakList.instrument_undeclared"]
    assert (row.kind, row.tier) == ("action", 1)


def test_an_audited_row_carries_its_evidence():
    """Self-certification is the failure the table exists against, so a tier
    names its source; tier 3, and a tier-2 action, also carry the two-ground
    answer and the maintainer's dated approval."""
    for row in _audit.ROWS:
        if row.tier == "unaudited":
            continue
        assert row.evidence, f"{row.name}: tier {row.tier!r} with no evidence"
        if row.kind in _audit._STATES_AMBIGUITY:
            assert row.ambiguity is not None, (
                f"{row.name}: an audited {row.kind} row states its kind under "
                "DESIGN.md § Rules, 1")
        if row.tier == 3 or (row.tier == 2 and row.kind == "action"):
            assert row.grounds and row.approved, (
                f"{row.name}: tier {row.tier} {row.kind} needs grounds and approved")


def test_every_unaudited_row_is_on_the_baseline():
    """The growth guard's local half: a row at 'unaudited' is one still
    waiting for its audit.  CI's audit-delta step is the half that can tell a
    new name from an old one."""
    baseline = set(_audit.UNAUDITED_BASELINE)
    off = sorted(row.name for row in _audit.ROWS
                 if row.tier == "unaudited" and row.name not in baseline)
    assert not off, ("row(s) at 'unaudited' not on UNAUDITED_BASELINE.  A name new to the "
                     "table enters with its tier and evidence, and CI's audit-delta step "
                     "fails one that enters at 'unaudited'.  A row that moved to a new name "
                     f"takes its baseline line with it: {off}")


def test_the_baseline_shrinks_as_rows_are_audited():
    """Every baseline name is a row still at 'unaudited', so auditing a row
    means deleting its baseline line."""
    baseline = _audit.UNAUDITED_BASELINE
    assert list(baseline) == sorted(set(baseline)), "UNAUDITED_BASELINE is sorted and unique"
    orphan = sorted(name for name in baseline if name not in ROWS)
    assert not orphan, f"baseline name(s) with no row: {orphan}"
    audited = sorted(name for name in baseline if ROWS[name].tier != "unaudited")
    assert not audited, f"audited row(s) still on UNAUDITED_BASELINE; delete: {audited}"


def test_every_code_row_off_the_response_baseline_carries_a_response():
    """The response column's growth guard (WP-2037): a code row with no
    response is one still waiting for it, so a code new to the table enters
    with one."""
    baseline = set(_audit.RESPONSE_BASELINE)
    off = sorted(row.name for row in _audit.ROWS
                 if row.kind == "code" and row.response is None and row.name not in baseline)
    assert not off, ("code row(s) with no response and not on RESPONSE_BASELINE.  "
                     + NEW_CODE + "A row that moved to a new name takes its baseline line "
                     f"with it: {off}")


def test_the_response_baseline_shrinks_as_responses_are_given():
    """Every name on it is a code row still without a response, so giving a
    code its response means deleting its baseline line."""
    baseline = _audit.RESPONSE_BASELINE
    assert list(baseline) == sorted(set(baseline)), "RESPONSE_BASELINE is sorted and unique"
    orphan = sorted(name for name in baseline if name not in ROWS)
    assert not orphan, f"RESPONSE_BASELINE name(s) with no row: {orphan}"
    other = sorted(name for name in baseline if ROWS[name].kind != "code")
    assert not other, f"RESPONSE_BASELINE lists code rows alone: {other}"
    given = sorted(name for name in baseline if ROWS[name].response is not None)
    assert not given, f"row(s) with a response still on RESPONSE_BASELINE; delete: {given}"


def test_a_response_is_the_level_every_raise_site_passes(raised):
    """A code's response equals the literal ``level=`` at every raise site,
    read off ``docs/reference_pages.diagnostic_index``.  A level computed at run
    time, a second level, or one the walk cannot see fails: where two
    consequences differ they are two codes, never a threshold between levels
    (``docs/milestones/generality.md`` § The rule, "Attention is a cost").

    Measured when the column opened (2026-10-24): of 257 codes, 20 raise at
    more than one level or a computed one, and 8 more only through a helper
    whose level the walk cannot read.  Each stays on ``RESPONSE_BASELINE``
    until it is split into one code per consequence or raised where its level
    can be read."""
    wrong = []
    for row in _audit.ROWS:
        if row.response is None:
            continue
        levels = _site(raised, row.name)["levels"]
        if levels != {row.response}:
            seen = sorted("set at run time" if lv == "" else lv for lv in levels)
            wrong.append(f"{row.name}: response {row.response!r}, raise sites "
                         f"{', '.join(seen) or 'with no level the walk can read'}")
    assert not wrong, ("response(s) that are not the level every raise site passes.  Give "
                       "the row the level its sites raise at; where two consequences "
                       "genuinely differ, split the code in two, never a threshold "
                       "between levels:\n" + "\n".join(wrong))


def test_a_response_says_what_the_reader_does_and_a_warning_what_it_guards():
    """Every response carries its sentence, and a ``warning`` one names a
    result number or a plan outcome: a warning is owed before quoting a result
    number of a purpose, or where the plan did not reach what it asked.  A
    lexical tripwire, not a reading: it checks for one stem of
    ``rietx.purposes.RESULT_NUMBERS`` or ``PLAN_OUTCOMES`` in the lower-cased
    sentence, and an agreement index is not a result number."""
    stems = purposes.RESULT_NUMBERS + purposes.PLAN_OUTCOMES
    for row in _audit.ROWS:
        if row.response is None:
            assert not row.responds, f"{row.name}: a responds sentence with no response"
            continue
        assert row.responds.strip(), f"{row.name}: response {row.response!r} with no sentence"
        if row.response == "warning":
            assert any(stem in row.responds.lower() for stem in stems), (
                f"{row.name}: a warning's sentence names the result number to hold back "
                f"or the plan outcome it reports; none of {stems} in {row.responds!r}")


def test_a_code_no_raise_site_locates_declares_its_scope(raised):
    """A code's level under a purpose is its response where a ``where`` path
    matches the purpose's globs, so a record with no ``where`` declares the
    purposes it bears on in ``scope``.  A code with neither fails rather than
    reading ``info`` everywhere: a pairing nobody checked must not read as
    "not your concern" (WP-1076).  One site without a ``where`` is enough to
    need it, and a site the walk cannot see counts as one."""
    for row in _audit.ROWS:
        if row.kind != "code":
            assert row.response is None and not row.scope, (
                f"{row.name}: response and scope are a code row's alone")
            continue
        if row.response is None:
            assert not row.scope, f"{row.name}: a scope comes with a response"
            continue
        where = _site(raised, row.name)["where"]
        if where != {True}:
            how = ("no raise site the walk can read" if not where
                   else "a raise site passing no where")
            assert row.scope, (f"{row.name}: {how}, and no scope.  Name the purposes of "
                               f"rietx.purposes.PURPOSES it bears on, or ('all',)")
        if row.scope:
            assert len(set(row.scope)) == len(row.scope), f"{row.name}: scope repeats"
            assert row.scope == ("all",) or set(row.scope) <= set(purposes.PURPOSES), (
                f"{row.name}: scope {row.scope} names a purpose not in rietx.purposes."
                "PURPOSES, or 'all' beside others")


def test_the_purpose_table_names_live_paths_and_cites_its_physics():
    """Each purpose's globs match a live parameter family of
    ``rietx.help.PARAMETER_HELP`` (a family's ``*`` read as one index or
    name), and each row cites what couples its numbers to those paths."""
    from rietx.help import PARAMETER_HELP

    assert set(purposes.PURPOSES) == set(PURPOSE_NAMES), (
        "rietx.purposes.PURPOSES and PURPOSE_NAMES name different purposes: "
        f"{sorted(set(purposes.PURPOSES) ^ set(PURPOSE_NAMES))}.  A new purpose is one row "
        "there and one name here")
    families = [family.replace("*", "0") for family in PARAMETER_HELP]
    for name, purpose in purposes.PURPOSES.items():
        assert isinstance(purpose.depends, tuple) and purpose.depends, name
        assert not any("[" in glob for glob in purpose.depends), (
            f"{name}: no brackets in a path glob (fnmatch reads them as a class)")
        dead = [glob for glob in purpose.depends
                if not any(fnmatch.fnmatchcase(path, glob) for path in families)]
        assert not dead, f"{name}: glob(s) matching no parameter family: {dead}"
        assert len(purpose.why.split()) >= 8, f"{name}: why is a sentence of physics"
        assert re.search(r"\b(19|20)\d\d\b|WP-\d{4}|\b[a-z_]+\.[A-Za-z_]+", purpose.why), (
            f"{name}: why cites a paper's year, a WP or the module measuring it")


def test_every_top_level_entry_is_walked_or_declared_out():
    """A new module or directory fails until it is placed, so the walk's reach
    is decided when a file is made."""
    package = pathlib.Path(_audit.__file__).parent
    entries = {p.name for p in package.iterdir() if p.name != "__pycache__"
               and (p.suffix == ".py" or (p.is_dir() and any(p.rglob("*.py"))))}
    whole = {e for e in _audit.WALKED if "/" not in e}
    part = {e.split("/")[0] for e in _audit.WALKED if "/" in e} - whole
    out = set(_audit.NOT_WALKED)
    assert all("/" not in e for e in out), "NOT_WALKED names top-level entries"
    assert not whole & out, f"walked and declared out at once: {sorted(whole & out)}"
    assert not part - out, ("an entry the walk covers in part declares in NOT_WALKED why "
                            f"the rest is out: {sorted(part - out)}")
    unplaced = sorted(entries - whole - out)
    assert not unplaced, (
        f"top-level entries neither walked nor declared out: {unplaced}.  Add each to "
        "_audit.WALKED with the audit WP that owns its rows, or to _audit.NOT_WALKED with "
        "the reason no module-level number in it can move a fitted value, a verdict, how "
        "a file is read, or what another program computes from a file rietx writes")
    assert not out - entries, f"NOT_WALKED names nothing in the package: {sorted(out - entries)}"
    assert all(_audit.NOT_WALKED.values()), "every NOT_WALKED entry gives its reason"


def test_the_declared_scope_resolves():
    package = pathlib.Path(_audit.__file__).parent
    for entry, owner in _audit.WALKED.items():
        assert (package / entry).exists(), entry
        assert 2002 <= owner <= 2007, (entry, owner)
    for seat, owner in _audit.DEFAULT_SEATS.items():
        assert callable(_audit.resolve(seat)), seat
        assert 2002 <= owner <= 2007, (seat, owner)


def test_a_printed_row_names_the_item_and_fails_until_filled():
    """The line a failure prints evaluates to a row naming the item, with its
    value; every slot it leaves for the author fails a test above unfilled,
    so it cannot be pasted as it stands."""
    for row in _audit.ROWS:
        printed = eval(_audit.row_source(row.name, row.kind, row.value).rstrip(","),
                       {"Row": _audit.Row})
        assert (printed.name, printed.kind) == (row.name, row.kind)
        assert _audit.same(printed.value, row.value), row.name
        assert printed.tier not in _audit.TIERS, row.name
        assert printed.evidence == "", row.name
        if row.kind in _audit._STATES_AMBIGUITY:
            assert printed.ambiguity not in (1, 2, 3), row.name
        if row.kind == "code":
            assert printed.response not in _audit.RESPONSES, row.name
            assert printed.responds == "", row.name
        else:
            assert printed.response is None and printed.responds == "", row.name
