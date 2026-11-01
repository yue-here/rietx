"""The reachability walk over the derived public surface (WP-2006, part of #1058).

Run by hand, never by pytest (no ``test_`` prefix, so it is not collected)::

    .venv/bin/python -m tests.reachability_walk                 # writes docs/wp/2006-batch/
    .venv/bin/python -m tests.reachability_walk --out DIR

For every entry of ``tests.api_surface.derive_surface()`` it records which
sources mention the entry, and derives one state.  **It collates.  The table rules
nothing and removes nothing**: a removed entry fails ``test_manual_api.py``'s
partition until it is documented as removed, and the compatibility promise stages
every break, so any removal is the maintainer's ruling and a WP of its own.

**Sources** (one column each).  Only code is read, never prose:

* ``examples``     ``examples/**`` (``.py``, ``.md``, ``.ipynb`` as text)
* ``skill``        ``docs/skill/rietx/**`` (the committed copies under ``.claude/`` and
                   ``.agents/`` are byte copies and are not read twice)
* ``gui_py``       ``src/rietx/gui/**.py``, the Python side of the GUI
* ``gui_ts``       ``gui/src/**`` ``.ts`` and ``.svelte`` outside ``*.test.ts`` and ``test-*``,
                   which is where the TypeScript calls into the Python side
* ``manual_part1`` ``docs/manual/using/**`` (Part 1 of the old manual, still on ``main``
                   until WP-1986 retires the tree)
* ``manual_new``   ``docs/docs/**`` (the new manual: guides, reference, concepts, theory),
                   hand-written pages only; ``_generated`` and ``_build`` are not read
                   because the generated API pages list every name by construction
* ``src_code``     the rest of ``src/rietx`` outside the entry's own defining file, code
                   only (docstrings and comments removed), ``rietx/__init__.py`` excluded
                   because it re-exports every top-level name
* ``src_doc_ex``   a docstring example in ``src`` (``>>>`` lines and fenced blocks)
* ``tests``        ``tests/**`` except this file, ``api_surface.py`` and
                   ``test_manual_api.py``, which read every name by construction

**How a mention is resolved.**  Text, not imports.  A markdown file contributes only
its code spans and fenced blocks (an English word such as ``fit`` or ``label`` is not a
call).  A Python file contributes its code without docstrings and comments.  An entry
``X`` (class, function, constant, module function) is mentioned when the identifier
``X`` occurs in a source file.  A member ``Owner.m`` is mentioned with one of three
evidences, strongest first:

* ``q``  the literal ``Owner.m`` (or ``Owner(…, m=``-free qualified form) occurs;
* ``u``  the member name ``m`` is the last component of exactly one entry on the surface,
         and ``m`` occurs as an identifier in the file;
* ``f``  ``Owner`` (or a rietx subclass of it) and ``m`` both occur in the same file.

A cell holds ``evidence:number-of-files``.  **Transitive reach** is a second pass over
types: a class that a *reached* field or method names in its annotation or signature is
"reached (via entry)", and so is the base class of a reached class and the type
a reached function returns; reaching a class does not reach its members, they need
a mention of their own, and a member nobody mentions passes no type on.

**What it cannot see**: an entry used through ``getattr`` with a built string, through
``model_dump``/JSON keys whose spelling differs from the field name, through a
variable whose type no file names (``result.statistics.rwp`` is seen only by the
unique-name or co-occurrence rule), a name that is also an ordinary identifier
(``name``, ``value``, ``label`` count as mentioned wherever they occur, so ``u`` and
``f`` hits over-count generic names), a method reached only by inheritance in a file
that names neither class, a notebook output, and anything a user types in the GUI's
console.  The states are therefore an upper bound on "reached" for generic names and
a lower bound for dynamically spelled ones; the hand checks in the batch's
``reachability.md`` quote five entries of each state.

**States**: ``reached`` (an examples/skill/gui/manual mention); ``reached (via entry)``
(only through the type pass); ``tests only``; ``docstring example only`` (a ``src``
docstring example is the sole mention, a judgement call listed apart); ``unreached``
(everything else, including entries used only inside ``src`` code, which ``src_code``
shows).
"""

from __future__ import annotations

import argparse
import ast
import csv
import inspect
import io
import re
import tokenize
import typing
from collections import defaultdict
from pathlib import Path

import rietx
from tests.api_surface import (
    Entry,
    _annotated_types_of,
    derive_surface,
    is_rietx,
    reachable_types,
)

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "rietx"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^```[^\n]*\n(.*?)^```", re.S | re.M)
SOURCES = ("examples", "skill", "gui_py", "gui_ts", "skill_index", "manual_part1", "manual_new")
#: Sources where a name is *used*.  The other three *document* it: the manual's coverage
#: partition (tests/test_manual_api.py) puts every name of the surface in the manual or in a
#: named exclusion by construction, and the skill's api*.md is generated from a selection,
#: so a mention there cannot tell a used name from a dead one.
USE_SOURCES = ("examples", "skill", "gui_py", "gui_ts")
DOC_SOURCES = ("skill_index", "manual_part1", "manual_new")
TESTS_SKIP = {"api_surface.py", "test_manual_api.py", "reachability_walk.py"}


class Source:
    """The code text of every file of one source, and its identifier index."""

    def __init__(self) -> None:
        self.text: dict[str, str] = {}
        self.idents: dict[str, set[str]] = defaultdict(set)  # identifier -> files

    def add(self, rel: str, text: str) -> None:
        self.text[rel] = text
        for ident in set(IDENT.findall(text)):
            self.idents[ident].add(rel)


def _py_code(text: str) -> tuple[str, str]:
    """(code without docstrings and comments, the docstrings joined)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, ""
    doc_lines: set[int] = set()
    docs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                doc_lines.update(range(body[0].lineno, body[0].end_lineno + 1))
                docs.append(body[0].value.value)
    keep: list[str] = []
    lines = text.splitlines()
    try:
        comment_at = {t.start[0]: t.start[1] for t in
                      tokenize.generate_tokens(io.StringIO(text).readline)
                      if t.type == tokenize.COMMENT}
    except (tokenize.TokenError, IndentationError):
        comment_at = {}
    for i, line in enumerate(lines, 1):
        if i in doc_lines:
            continue
        if i in comment_at:
            line = line[: comment_at[i]]
        keep.append(line)
    return "\n".join(keep), "\n".join(docs)


def _docstring_examples(docs: str) -> str:
    """The lines of a docstring that are example code: ``>>>`` lines and fenced blocks."""
    out: list[str] = []
    fenced = False
    for line in docs.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or stripped.startswith((">>>", "...")):
            out.append(stripped)
    return "\n".join(out)


def _md_code(text: str) -> str:
    return "\n".join(FENCE.findall(text) + CODE_SPAN.findall(FENCE.sub("", text)))


def _ts_code(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(?<![:\"'])//.*$", "", text)


def _files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and p.suffix in suffixes
                  and not {"node_modules", "_build", "_generated", "__pycache__", "dist"}
                  & set(p.relative_to(root).parts)
                  and not p.name.startswith("._"))


def load_sources() -> tuple[dict[str, Source], Source, Source, dict[str, str]]:
    """The six user sources, the src-code index, the tests index, src docstring examples."""
    srcs = {name: Source() for name in SOURCES}

    def rel(p: Path) -> str:
        return p.relative_to(REPO).as_posix()

    for p in _files(REPO / "examples", (".py", ".md", ".ipynb", ".toml")):
        text = p.read_text(encoding="utf-8", errors="replace")
        srcs["examples"].add(rel(p), _py_code(text)[0] if p.suffix == ".py" else text)
    for p in _files(REPO / "docs" / "skill" / "rietx", (".md", ".py")):
        generated = p.name.startswith("api") and p.parent.name == "references"
        srcs["skill_index" if generated else "skill"].add(
            rel(p), _md_code(p.read_text(encoding="utf-8")))
    for p in _files(REPO / "gui" / "src", (".ts", ".svelte")):
        if p.name.endswith(".test.ts") or p.name.startswith("test-") or p.name.endswith(".d.ts"):
            continue
        srcs["gui_ts"].add(rel(p), _ts_code(p.read_text(encoding="utf-8")))
    for p in _files(REPO / "docs" / "manual" / "using", (".md",)):
        srcs["manual_part1"].add(rel(p), _md_code(p.read_text(encoding="utf-8")))
    for p in _files(REPO / "docs" / "docs", (".md",)):
        srcs["manual_new"].add(rel(p), _md_code(p.read_text(encoding="utf-8")))
    src_code, tests = Source(), Source()
    src_docs: dict[str, str] = {}
    for p in _files(SRC, (".py",)):
        code, docs = _py_code(p.read_text(encoding="utf-8"))
        if "gui" in p.relative_to(SRC).parts:
            srcs["gui_py"].add(rel(p), code)
        elif p.relative_to(SRC).as_posix() != "__init__.py":
            src_code.add(rel(p), code)
            src_docs[rel(p)] = _docstring_examples(docs)
            src_docs[rel(p) + "#prose"] = docs
    for p in _files(REPO / "tests", (".py",)):
        if p.name not in TESTS_SKIP:
            tests.add(rel(p), p.read_text(encoding="utf-8", errors="replace"))
    return srcs, src_code, tests, src_docs


def _member_types(cls: type, member: str) -> set[type]:
    """The rietx classes a field's annotation, or a method's signature, names."""
    try:
        hints = typing.get_type_hints(cls)
    except Exception:
        hints = {}
    if member in hints:
        found: set[type] = set()
        stack = [hints[member]]
        while stack:
            node = stack.pop()
            if inspect.isclass(node) and is_rietx(node):
                found.add(node)
            stack.extend(a for a in typing.get_args(node) if a is not None)
        return found
    func = inspect.getattr_static(cls, member, None)
    func = func.__func__ if isinstance(func, (classmethod, staticmethod)) else func
    func = func.fget if isinstance(func, property) else func
    return _annotated_types_of(func) if inspect.isfunction(func) else set()


def _subclass_names(classes: dict[str, type]) -> dict[str, set[str]]:
    """Owner name -> the names of itself and of every surface class that subclasses it."""
    out: dict[str, set[str]] = {name: {name} for name in classes}
    for name, cls in classes.items():
        for base in inspect.getmro(cls)[1:]:
            if base.__name__ in out:
                out[base.__name__].add(name)
    return out


class Walker:
    def __init__(self) -> None:
        self.surface = derive_surface()
        self.classes = reachable_types()
        self.family = _subclass_names(self.classes)
        self.srcs, self.src_code, self.tests, self.src_docs = load_sources()
        self.last_count: dict[str, int] = defaultdict(int)
        for name in self.surface:
            self.last_count[name.rsplit(".", 1)[-1]] += 1
        self.modules = {n for n in rietx.__all__ if inspect.ismodule(getattr(rietx, n))}

    # -- one entry against one Source ------------------------------------------------
    def hit(self, entry: Entry, source: Source, skip: set[str] = frozenset()) -> tuple[str, list[str]]:
        """(best evidence letter or "", the files that mention the entry)."""
        name = entry.name
        last = name.rsplit(".", 1)[-1]
        dotted = "." in name
        owner = name.rsplit(".", 1)[0] if dotted else None
        files = source.idents.get(last, set()) - skip
        if not files:
            return "", []
        if not dotted or (owner in self.modules and entry.kind == "function"):
            # a top-level name, or a function of an exported module, by its own name
            if dotted and self.last_count[last] > 1:
                q = [f for f in files if re.search(rf"\b{re.escape(owner)}\.{last}\b", source.text[f])]
                return ("q", sorted(q)) if q else ("", [])
            return "u", sorted(files)
        qualified = [f for f in files
                     if re.search(rf"\b{re.escape(owner)}\s*\.\s*{re.escape(last)}\b", source.text[f])]
        if qualified:
            return "q", sorted(qualified)
        if self.last_count[last] == 1:
            return "u", sorted(files)
        near: set[str] = set()
        for fam in self.family.get(owner, {owner}):
            near |= source.idents.get(fam, set())
        both = sorted(files & near)
        return ("f", both) if both else ("", [])

    def docstring_hit(self, entry: Entry, key: str, skip: set[str]) -> list[str]:
        last = entry.name.rsplit(".", 1)[-1]
        pat = re.compile(rf"\b{re.escape(last)}\b")
        return [f for f, t in self.src_docs.items()
                if f.endswith("#prose") == (key == "prose") and f not in skip
                and f.removesuffix("#prose") not in skip and pat.search(t)]

    def defining_file(self, entry: Entry) -> set[str]:
        mod = entry.module
        if not mod:
            return set()
        base = "src/" + mod.replace(".", "/")
        return {base + ".py", base + "/__init__.py"}

    # -- the walk --------------------------------------------------------------------
    def run(self) -> list[dict[str, str]]:
        rows: dict[str, dict[str, str]] = {}
        for name, entry in sorted(self.surface.items()):
            row: dict[str, str] = {"name": name, "kind": entry.kind, "owner": entry.owner or "",
                                   "module": entry.module or ""}
            refs: list[str] = []
            for col in SOURCES:
                ev, files = self.hit(entry, self.srcs[col])
                row[col] = f"{ev}:{len(files)}" if files else ""
                refs.extend(files[:1])
            skip = self.defining_file(entry)
            ev, files = self.hit(entry, self.src_code, skip)
            row["src_code"] = f"{ev}:{len(files)}" if files else ""
            ex = self.docstring_hit(entry, "ex", skip)
            row["src_doc_ex"] = str(len(ex)) if ex else ""
            ev, files = self.hit(entry, self.tests)
            row["tests"] = f"{ev}:{len(files)}" if files else ""
            if not any(row[c] for c in SOURCES):
                refs.extend(files[:2])
                refs.extend(self.hit(entry, self.src_code, skip)[1][:2])
            row["via"] = row["via_use"] = ""
            row["state"] = row["state_use"] = ""
            row["refs"] = ";".join(dict.fromkeys(refs))[:300]
            rows[name] = row
        self._transitive(rows, SOURCES, "state", "via")
        self._transitive(rows, USE_SOURCES, "state_use", "via_use")
        for row in rows.values():
            for key in ("state", "state_use"):
                if row[key]:
                    continue
                if key == "state_use" and any(row[c] for c in DOC_SOURCES):
                    row[key] = "documented only"
                else:
                    row[key] = ("tests only" if row["tests"] else
                                "docstring example only" if row["src_doc_ex"] else "unreached")
        return [rows[n] for n in sorted(rows)]

    def _transitive(self, rows: dict[str, dict[str, str]], cols: tuple[str, ...],
                    state: str, via: str) -> None:
        """Direct reach through `cols`, then the type edges: annotations of reached entries."""
        reached = {n for n, r in rows.items() if any(r[c] for c in cols)}
        for n in reached:
            rows[n][state] = "reached"
        edges: dict[str, set[str]] = defaultdict(set)
        for cname, cls in self.classes.items():
            for base in inspect.getmro(cls)[1:]:
                if base.__name__ in self.classes:
                    edges[cname].add(base.__name__)
        for name, entry in self.surface.items():
            if entry.kind == "function":
                obj = getattr(rietx, name, None)
                if obj is None and "." in name:
                    mod, fn = name.split(".", 1)
                    obj = getattr(getattr(rietx, mod, None), fn, None)
                if callable(obj):
                    edges[name] |= {t.__name__ for t in _annotated_types_of(obj)}
            elif entry.kind in {"field", "member"} and entry.owner in self.classes:
                edges[name] |= {t.__name__
                                for t in _member_types(self.classes[entry.owner],
                                                       name.rsplit(".", 1)[-1])}
        frontier = [n for n in reached if n in edges]
        while frontier:
            n = frontier.pop()
            for target in edges.get(n, ()):
                if target in rows and not rows[target][state]:
                    rows[target][state] = "reached (via entry)"
                    rows[target][via] = n
                    frontier.append(target)


COLUMNS = ["name", "kind", "owner", "module", *SOURCES, "src_code", "src_doc_ex", "tests",
           "state_use", "via_use", "state", "via", "refs"]


def write(rows: list[dict[str, str]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "reachability.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "wp" / "2006-batch")
    args = ap.parse_args()
    rows = Walker().run()
    write(rows, args.out)
    print(f"{len(rows)} entries")
    for key in ("state_use", "state"):
        counts: dict[str, int] = defaultdict(int)
        for r in rows:
            counts[r[key]] += 1
        print(f"{key} ({'use sources' if key == 'state_use' else 'every source'}):")
        for state, n in sorted(counts.items()):
            print(f"  {state}: {n}")


if __name__ == "__main__":
    main()
