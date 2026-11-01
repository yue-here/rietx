"""The audit table's rows a change adds, changes or deletes, for the judge (WP-2014).

    python -m tests.audit_delta         # the report, against this change's base

**Why at review.**  `tests/test_audit_table.py` holds the table equal to the
tree and reads no git (`rietx._audit`'s docstring says why).  So it cannot see
what a change did to the table.  A row can arrive with its author's tier, and a
value can be retuned under the tier it had.  Neither touches the baseline.  So
CI's lint job prints every row a change adds, renames, changes or deletes, and
`/pr-review` hands that list to the `generality-review` judge.

**Both tables are read from source text by AST**, so the base revision is read
with `git show` and never imported.  Seven names are read: `ROWS`,
`UNAUDITED_BASELINE`, `WALKED`, `NOT_WALKED`, `DEFAULT_SEATS`, `RECORD_SCHEMAS`
and `OTHER_RECORD_FIELDS`.  One missing at the base reads as empty.  A row's value
that `ast.literal_eval` cannot read, such as ``float("inf")``, is compared as
its source text.

**A rename** pairs a deleted row with an added row of the same kind, the same
value and the same leaf.  A default's leaf is the part after ``:``.  A
suggestion's is the last dot component of the name before ``.suggestion``.
Every other leaf is the last dot component, so a code's leaf is its whole name
and a renamed code never pairs.  A constant moved between modules is therefore
a rename, and a constant or code given a new leaf is a new name.  Pairs are made
one to one, in sorted order.

**It fails on one thing**: a name new to `ROWS` at ``unaudited``.  A count
would fail honest growth, a row the judge returns to ``unaudited``.  A count
would also let a change delete one unaudited row to buy room for another.  Three
new names are exempt: the added half of a rename, a constant in a file the
base's `WALKED` did not cover, and a default at a seat new to `DEFAULT_SEATS`.
Opening a walk over existing code enters its rows for the audit that owns them.
So the last two hold only where the base already defined the constant, or the
seat's function or class.  A module new in the change is placed in `WALKED`,
and its numbers still need their tiers.  Every other delta is a report.

Stdlib only, like `skill_caps`, whose base revision and git helpers it reuses
(`RIETX_CAPS_BASE` overrides the base for both).
"""

from __future__ import annotations

import ast
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import NamedTuple

from tests.skill_caps import ROOT, _git, base, rev_exists
from tests.skill_surface import _cut, _module_assignments

TABLE = "src/rietx/_audit.py"
UNAUDITED = "unaudited"
#: The kinds whose rows store a value; `rietx._audit._VALUED`.
VALUED = ("constant", "default", "suggestion")


class Source(str):
    """A value `ast.literal_eval` cannot read, kept as its source text."""

    def __repr__(self) -> str:
        return str(self)


@dataclass(frozen=True)
class Row:
    """One ``Row(...)`` of `ROWS` as written: `rietx._audit.Row`'s fields, in
    its order and with its defaults, and the line the call starts on."""

    name: str
    kind: str
    tier: object = UNAUDITED
    ambiguity: object = None
    evidence: str = ""
    grounds: str = ""
    approved: object = None
    value: object = None
    response: object = None
    responds: str = ""
    scope: tuple = ()
    line: int = 0


FIELDS = ("name", "kind", "tier", "ambiguity", "evidence", "grounds", "approved", "value",
          "response", "responds", "scope")


class Table(NamedTuple):
    rows: dict[str, Row]
    baseline: frozenset[str]
    walked: dict[str, object]
    not_walked: dict[str, object]
    seats: dict[str, object]
    schemas: frozenset[str]
    other_fields: frozenset[str]


# -- the table, from source text -----------------------------------------

def _value(node: ast.expr) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return Source(ast.unparse(node))


def _row(call: ast.Call) -> Row:
    given = dict(zip(FIELDS, call.args))
    given.update((kw.arg, kw.value) for kw in call.keywords if kw.arg)
    return Row(**{k: _value(v) for k, v in given.items()}, line=call.lineno)


def _collection(node: ast.expr | None) -> object:
    if isinstance(node, ast.Call):                   # frozenset({...}), frozenset()
        node = node.args[0] if node.args else None
    return () if node is None else ast.literal_eval(node)


def read_table(text: str) -> Table:
    """The rows and declarations of ``_audit.py``'s source ``text``."""
    found = dict(_module_assignments(ast.parse(text, filename=TABLE)))
    rows = found.get("ROWS")
    calls = rows.elts if isinstance(rows, ast.Tuple) else []
    return Table(
        rows={r.name: r for r in (_row(c) for c in calls if isinstance(c, ast.Call))},
        baseline=frozenset(_collection(found.get("UNAUDITED_BASELINE"))),
        walked=dict(_collection(found.get("WALKED")) or {}),
        not_walked=dict(_collection(found.get("NOT_WALKED")) or {}),
        seats=dict(_collection(found.get("DEFAULT_SEATS")) or {}),
        schemas=frozenset(_collection(found.get("RECORD_SCHEMAS"))),
        other_fields=frozenset(_collection(found.get("OTHER_RECORD_FIELDS"))),
    )


# -- the deltas -----------------------------------------------------------

def leaf(row: Row) -> str:
    """The part of a row's name a rename keeps (module docstring)."""
    if row.kind == "default":
        return row.name.partition(":")[2]
    name = row.name.removesuffix(".suggestion") if row.kind == "suggestion" else row.name
    return name.rpartition(".")[2]


def _rename_key(row: Row) -> tuple[str, str, str]:
    return row.kind, leaf(row), repr(row.value)


def _files(constant: str) -> tuple[str, str]:
    """The two files ``rietx.a.b.NAME`` can live in, relative to the package."""
    stem = "/".join(constant.split(".")[1:-1])
    return f"{stem}.py", f"{stem}/__init__.py"


def _walked_by(walked: Mapping[str, object], path: str) -> list[str]:
    return sorted(e for e in walked if path == e or path.startswith(e + "/"))


def opened_by(row: Row, before: Table, after: Table,
              existed: Callable[[Row], bool]) -> str | None:
    """The walk entry or seat new to the table that ``row`` entered with, if
    any, where ``existed`` says the base already held the code it names."""
    via = None
    if row.kind == "constant":
        paths = _files(row.name)
        now = sorted({e for p in paths for e in _walked_by(after.walked, p)})
        if now and not any(_walked_by(before.walked, p) for p in paths):
            via = now[0]
    elif row.kind == "default":
        seat = row.name.partition(":")[0]
        if seat in after.seats and seat not in before.seats:
            via = seat
    return via if via is not None and existed(row) else None


NEW_UNAUDITED, ADDED, OPENED = "new at 'unaudited'", "added", "opened"
RENAMED, CHANGED, DELETED = "renamed", "changed", "deleted"
_TITLES = {
    NEW_UNAUDITED: "New to the table at 'unaudited' (FAILS)",
    ADDED: "Added",
    OPENED: "Entered with a walk entry or seat new to the table",
    RENAMED: "Renamed",
    CHANGED: "Changed",
    DELETED: "Deleted",
}
_ORDER = {why: i for i, why in enumerate(_TITLES)}


@dataclass(frozen=True)
class Delta:
    why: str                 # a key of _TITLES
    row: Row                 # the head's row; the base's for a deletion
    old: Row | None = None   # the base's row, for a change or a rename
    via: str = ""            # the new walk entry or seat, for OPENED

    @property
    def fails(self) -> bool:
        return self.why == NEW_UNAUDITED


def changed_fields(old: Row, new: Row) -> list[str]:
    """The fields other than the name that differ between two rows."""
    return [f for f in FIELDS[1:] if repr(getattr(old, f)) != repr(getattr(new, f))]


def _always(row: Row) -> bool:
    return True


def deltas(before: Table, after: Table,
           existed: Callable[[Row], bool] = _always) -> list[Delta]:
    """Every row the change added, renamed, changed or deleted.  ``existed``
    says whether the base defined the code a row names (`defined_at`)."""
    deleted = sorted(before.rows.keys() - after.rows.keys())
    out = []
    for name in sorted(after.rows.keys() - before.rows.keys()):
        row = after.rows[name]
        pair = next((d for d in deleted
                     if _rename_key(before.rows[d]) == _rename_key(row)), None)
        if pair is not None:
            deleted.remove(pair)
            out.append(Delta(RENAMED, row, before.rows[pair]))
        elif via := opened_by(row, before, after, existed):
            out.append(Delta(OPENED, row, via=via))
        else:
            out.append(Delta(NEW_UNAUDITED if row.tier == UNAUDITED else ADDED, row))
    out += [Delta(DELETED, before.rows[name]) for name in deleted]
    out += [Delta(CHANGED, after.rows[name], before.rows[name])
            for name in sorted(before.rows.keys() & after.rows.keys())
            if changed_fields(before.rows[name], after.rows[name])]
    return sorted(out, key=lambda d: (_ORDER[d.why], d.row.name))


_DECLARED = (("UNAUDITED_BASELINE", "baseline"), ("OTHER_RECORD_FIELDS", "other_fields"),
             ("WALKED", "walked"), ("NOT_WALKED", "not_walked"), ("DEFAULT_SEATS", "seats"),
             ("RECORD_SCHEMAS", "schemas"))


def declarations(before: Table, after: Table) -> list[tuple[str, str, list[str]]]:
    """``(declaration, "added" | "removed" | "changed", names)`` for each list or
    dict the change touched; a dict's entry changes where its value does."""
    out = []
    for label, field in _DECLARED:
        a, b = getattr(before, field), getattr(after, field)
        both = a.keys() & b.keys() if isinstance(a, dict) else set()
        for verb, names in (("added", set(b) - set(a)), ("removed", set(a) - set(b)),
                            ("changed", {k for k in both if a[k] != b[k]})):
            if names:
                out.append((label, verb, sorted(names)))
    return out


# -- the report -----------------------------------------------------------

def _describe(row: Row, code: Callable[[str], str]) -> str:
    bits = [f"{code(row.name)} ({row.kind})", f"tier {row.tier}"]
    if row.ambiguity is not None:
        bits.append(f"ambiguity {row.ambiguity}")
    if row.kind in VALUED:
        bits.append(f"value {code(repr(row.value))}")
    if row.response is not None:
        bits.append(f"response {row.response}")
    if row.approved:
        bits.append(f"approved {row.approved}")
    text = ", ".join(bits)
    return f"{text}: {_cut(row.evidence)}" if row.evidence.strip() else text


def _how_it_moved(d: Delta, code: Callable[[str], str]) -> list[str]:
    out = []
    if d.why == RENAMED:
        out.append(f"from {code(d.old.name)}")
    if d.via:
        where = "the walk's new entry" if d.row.kind == "constant" else "the new seat"
        out.append(f"with {where} {code(d.via)}")
    for f in changed_fields(d.old, d.row) if d.old else ():
        a, b = getattr(d.old, f), getattr(d.row, f)
        if f == "evidence":
            out.append("evidence changed")
        elif f in ("grounds", "responds"):
            out.append(f"{f} changed: {_cut(b) or '(none)'}")
        elif f == "value":
            out.append(f"value {code(repr(a))} → {code(repr(b))}")
        else:
            out.append(f"{f} {a} → {b}")
    return out


def report(found: list[Delta], declared: list[tuple[str, str, list[str]]], how: str,
           *, markdown: bool = False) -> str:
    """The deltas grouped by kind, the failing rows first, then the declarations."""
    code = (lambda s: f"`{s}`") if markdown else (lambda s: s)
    head = "**Audit table delta**" if markdown else "Audit table delta"
    if not found and not declared:
        return f"{head}, measured against {how}: no row or declaration changed."
    n = {why: sum(d.why == why for d in found) for why in _TITLES}
    lines = [f"{head}, measured against {how}: "
             f"{n[NEW_UNAUDITED] + n[ADDED] + n[OPENED]} added, {n[RENAMED]} renamed, "
             f"{n[CHANGED]} changed, {n[DELETED]} deleted, "
             f"{n[NEW_UNAUDITED]} new at 'unaudited'."]
    for why, title in _TITLES.items():
        group = [d for d in found if d.why == why]
        if group:
            lines += ["", f"{title}:"]
        for d in group:
            moved = "; ".join(_how_it_moved(d, code))
            if markdown:
                lines.append(f"- {_describe(d.row, code)}")
                lines += [f"  - {moved}"] if moved else []
            else:
                lines.append(f"  {_describe(d.row, code)}")
                lines += [f"    {moved}"] if moved else []
    if declared:
        lines.append("")
        lines += [f"{'- ' if markdown else ''}{code(label)} {verb}: "
                  + ", ".join(code(name) for name in names)
                  for label, verb, names in declared]
    return "\n".join(lines)


def failures(found: list[Delta]) -> list[str]:
    return [f"{d.row.name} ({d.row.kind}) is new to rietx._audit.ROWS and arrives at "
            f"'unaudited' ({TABLE}:{d.row.line}).  Give it a tier and the evidence for "
            "it (CONTRIBUTING.md § A heuristic needs its tier); a name new to the table "
            "may not enter at 'unaudited'"
            for d in found if d.fails]


# -- the tree and the base (impure) --------------------------------------

def _defines(text: str, name: str) -> bool:
    """Whether a module's source binds ``name`` at its top level."""
    tree = ast.parse(text)
    if any(bound == name for bound, _ in _module_assignments(tree)):
        return True
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if node.name == name:
                return True
        elif isinstance(node, ast.ImportFrom | ast.Import):
            if any((a.asname or a.name.rpartition(".")[2]) == name for a in node.names):
                return True
    return False


def defined_at(rev: str) -> Callable[[Row], bool]:
    """Whether ``rev`` defined the constant, or the seat's first attribute,
    that a row names.  The longest module path that exists is the one read,
    as an import resolves it."""
    texts: dict[str, str | None] = {}

    def text(rel: str) -> str | None:
        if rel not in texts:
            shown = _git("show", f"{rev}:src/rietx/{rel}")
            texts[rel] = shown.stdout if shown.returncode == 0 else None
        return texts[rel]

    def existed(row: Row) -> bool:
        parts = (row.name.partition(":")[0] if row.kind == "default" else row.name).split(".")
        for i in range(len(parts) - 1, 1, -1):
            stem = "/".join(parts[1:i])
            for rel in (f"{stem}.py", f"{stem}/__init__.py"):
                found = text(rel)
                if found is not None:
                    return _defines(found, parts[i])
        return False

    return existed


def main() -> int:
    rev, how = base()
    if rev is None:
        print(f"audit delta: {how}")
        return 0
    if not rev_exists(rev):
        print(f"audit delta: {rev} is not in this checkout ({how}); "
              "the checkout needs fetch-depth: 2", file=sys.stderr)
        return 1
    shown = _git("show", f"{rev}:{TABLE}")
    if shown.returncode != 0:
        print(f"audit delta: {TABLE} does not exist at {rev} ({how}), so there is "
              "no table to compare with")
        return 0
    before = read_table(shown.stdout)
    after = read_table((ROOT / TABLE).read_text(encoding="utf-8"))
    found = deltas(before, after, defined_at(rev))
    declared = declarations(before, after)
    print(report(found, declared, how))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(report(found, declared, how, markdown=True) + "\n")
    if os.environ.get("GITHUB_ACTIONS"):
        for d in found:
            if d.fails:
                print(f"::error file={TABLE},line={d.row.line}::{d.row.name} is new to "
                      "the audit table at 'unaudited'; give it a tier and its evidence")
    bad = failures(found)
    for f in bad:
        print(f, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
