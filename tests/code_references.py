"""Every name, path and test a comment or docstring cites, checked against the tree (WP-2233).

    python -m tests.code_references             # every miss, with file and line
    python -m tests.code_references --delta     # allowlist names new against the base

**Why.**  Agents read comments as true.  A comment that cites a deleted
function sends the next session looking for it, or rebuilding the old design
around it.  The manual has this guard (`tests/test_manual_api.py`), and so do
the rulebooks (`tests/test_docs_consistency.py`).  This is the guard for the
library's own prose: every ``#`` comment and every string statement (module,
class and function docstrings, and ``#:``-style attribute docstrings) under
``src/rietx``.

**What is checked.**  Three kinds of citation:

- *Role targets*: ``:func:`x```, ``:class:``, ``:data:``, ``:meth:``, ``:attr:``,
  ``:mod:``, ``:exc:``, ``:obj:`` and ``:const:``.  Whitespace is stripped first,
  because a target wraps across comment lines, then a ``Title <target>`` form is
  read for its target.
- *Dotted rietx literals*: a double-backtick span ``a.b`` whose first segment is
  ``rietx``, ``rx`` or a top-level module or package of rietx.
- *Repo paths and test IDs*: a token with a ``/`` and a file extension, or a
  ``::``.  It resolves against the citing file's package and each parent, the
  repo root, ``src/rietx``, ``src`` and ``tests``.  A test ID's node must be a
  function or class in that file.

**Resolution order** for a name, the first that answers wins:

1. absolute from ``rietx.``;
2. relative to the citing module, then each parent package;
3. a builtin, or an importable top-level module;
4. an attribute, annotation, pydantic field or ``self.`` assignment of a class
   defined in the citing module.

Step 4 is looser than Sphinx's Python domain, which uses the enclosing class.
An attribute of a class is any name its body or MRO defines, any pydantic
field, and any ``self.<name> =`` in its methods, read from source by AST.  A
module that fails to import (an optional backend) is read by AST for its
top-level names instead.

**Not checked**: ``docs/contracts/``, whose version notes name removed things
on purpose, and any comment's reasoning or quoted numbers.

**The allowlist** (`ALLOWLIST`) holds names a comment cites that are not rietx
code: foreign vocabulary, a field of another program's file, a name in a
quoted message.  Each entry carries its reason.  It is read by AST at the base
by ``--delta``, which fails a change that adds a name the base lacked and
edits anything else: an entry is reviewed by name in a change of its own,
since a count would let a change delete one to buy room for another
(`tests/audit_delta.py`'s rule).

The module imports nothing outside the stdlib at load; resolution imports
rietx on first use.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import io
import re
import subprocess
import sys
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "rietx"

#: Names and paths cited in comments that are not rietx code, each with why.
#: Keyed by the citation as the miss report prints it.  ``--delta`` fails a
#: change that adds a key the base lacked.
ALLOWLIST: dict[str, str] = {
    "spgrep/__init__.py": "a file of the spgrep package, which sets a spglib flag",
    "ase/utils/__init__.py": "a file of the ASE package, cited for its colour table",
    "studies/guillemot/out/audit_full.txt": "kept at the guillemot-study tag, off main",
    "Data0/Profile0.txt": "a member of a Rigaku .rasx archive",
    "live/events.jsonl": "a file inside a .rex project directory",
    "src/powderline/rietx/": "a directory of the upstream powderline repository",
    "powderline/topas/conversions.py": "a file of the upstream powderline repository",
    "easydiff/conversions.py": "a file of the upstream easydiff repository",
    "``background.single_peaks``": "a key of the powderline recipe JSON, not rietx code",
    "bin/serial.py": "ghostshift's queue script, in the claude-config repository",
}

ROLE = re.compile(
    r":(?:py:)?(?P<role>func|class|data|meth|attr|mod|exc|obj|const):`(?P<target>[^`]+)`")
LITERAL = re.compile(r"``(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)(?:\(\))?``")
#: A path: segments joined by ``/``, ending in a file extension or a ``/``,
#: optionally followed by a ``::`` test node.
PATH = re.compile(
    r"(?<![\w./:<-])(?P<path>(?:[\w.-]+/)+(?:[\w-]+(?:\.[\w-]+)*\.[A-Za-z]\w*)?)"
    r"(?:::(?P<node>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)?))?")
#: A test ID with no directory: ``test_x.py::test_y``.
BARE_TEST = re.compile(
    r"(?<![\w./-])(?P<path>test_\w+\.py)::(?P<node>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)?)")
URL = re.compile(r"\b[a-z][a-z+.-]*://\S+")
#: The extensions a path citation must carry to be checked.  A bare ``a/b``
#: in prose is a ratio or an alternative ("obs/calc", "and/or").
PATH_EXTS = frozenset({
    "py", "md", "json", "jsonl", "toml", "yml", "yaml", "txt", "cfg", "ini",
    "ts", "js", "mjs", "svelte", "css", "html", "rs", "cif", "rxt", "sh", "dat",
    "csv", "npz", "npy", "xy", "xye", "fxye", "prm", "raw", "brml", "xrdml",
    "rasx", "png", "svg", "ipynb", "lock",
})
#: Top-level directories a directory citation (``tests/eval_x/``) is checked under.
PATH_ROOTS = ("src/", "tests/", "docs/", "gui/", "kernels/", "examples/", ".claude/",
              ".github/")


@dataclass(frozen=True)
class Miss:
    file: str     # repo-relative
    line: int
    kind: str     # "role", "literal", "path"
    cited: str    # the citation as checked

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.kind} {self.cited}"


# --- prose extraction ---------------------------------------------------------


@dataclass(frozen=True)
class Block:
    file: str
    line: int     # the block's first line
    text: str

    def line_of(self, offset: int) -> int:
        return self.line + self.text.count("\n", 0, offset)


def blocks(path: Path) -> Iterator[Block]:
    """Every comment block and string statement in one file of this tree."""
    yield from source_blocks(path.relative_to(ROOT).as_posix(),
                             path.read_text(encoding="utf-8"), _tree(path))


def source_blocks(rel: str, source: str, tree: ast.Module | None = None) -> Iterator[Block]:
    """Every comment block and string statement in one source file.

    Consecutive ``#`` lines join into one block with the markers stripped, so
    a citation wrapped across lines reads whole.  A string statement is any
    expression statement that is a string literal: docstrings and attribute
    docstrings alike.
    """
    run: list[str] = []
    start = prev = 0
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type != tokenize.COMMENT:
            continue
        row = tok.start[0]
        text = re.sub(r"^#:? ?", "", tok.string)
        if run and row == prev + 1:
            run.append(text)
        else:
            if run:
                yield Block(rel, start, "\n".join(run))
            run, start = [text], row
        prev = row
    if run:
        yield Block(rel, start, "\n".join(run))
    for node in ast.walk(tree if tree is not None else ast.parse(source)):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            yield Block(rel, node.lineno, node.value.value)


def source_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


# --- name resolution ----------------------------------------------------------


def module_name(rel: str) -> str:
    return rel.removeprefix("src/").removesuffix(".py").replace("/", ".").removesuffix(
        ".__init__")


_MISSING = object()


@cache
def _import(name: str):
    """The module, ``None`` if there is no such module, or an AST stand-in when
    the module exists but will not import here."""
    if not name or "__main__" in name.split("."):
        return None
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name and (name == exc.name or name.startswith(exc.name + ".")):
            return None
        return _ast_module(name)
    except Exception:
        return _ast_module(name)


class _AstModule:
    """A module read for its top-level names, for one that will not import."""

    def __init__(self, names: set[str]):
        self.names = names


def _ast_module(name: str):
    if not name.startswith("rietx"):
        return None
    base = ROOT / "src" / Path(*name.split("."))
    for path in (base.with_suffix(".py"), base / "__init__.py"):
        if path.is_file():
            return _AstModule(_top_level_names(path))
    return None


def _top_level_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in _tree(path).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                names.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


@cache
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


@cache
def _self_assignments(path: Path) -> dict[str, frozenset[str]]:
    """Each class's qualified name in a file, with every ``self.<name>`` its
    own methods assign."""
    out: dict[str, frozenset[str]] = {}

    def visit(body, prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                qual = f"{prefix}{node.name}"
                out[qual] = frozenset(
                    n.attr for n in ast.walk(node)
                    if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and n.value.id == "self" and isinstance(n.ctx, ast.Store))
                visit(node.body, qual + ".")

    visit(_tree(path).body, "")
    return out


def _self_attributes(cls: type) -> frozenset[str]:
    """Names assigned as ``self.<name>`` anywhere in a class's own source."""
    module = getattr(cls, "__module__", "") or ""
    if not module.startswith("rietx"):
        return frozenset()
    base = ROOT / "src" / Path(*module.split("."))
    for path in (base.with_suffix(".py"), base / "__init__.py"):
        if path.is_file():
            return _self_assignments(path).get(cls.__qualname__, frozenset())
    return frozenset()


def _class_has(cls: type, attr: str) -> bool:
    for c in getattr(cls, "__mro__", (cls,)):
        if attr in vars(c) or attr in getattr(c, "__annotations__", {}):
            return True
        if attr in (getattr(c, "model_fields", None) or {}):
            return True
        if attr in getattr(c, "__dataclass_fields__", {}):
            return True
        if attr in getattr(c, "__slots__", ()):
            return True
        if c.__module__ != "builtins" and attr in _self_attributes(c):
            return True
    return False


def _walk(obj, attrs: list[str]) -> bool:
    """Whether ``obj.a.b…`` names something.  Past a pydantic field or an
    instance attribute nothing more is checked: the field's type is not walked."""
    for a in attrs:
        if isinstance(obj, _AstModule):
            return a in obj.names
        if isinstance(obj, type(sys)):
            # a module: its namespace, then a submodule, then its lazy
            # ``__getattr__``, which builds a near-miss message on a miss
            nxt = vars(obj).get(a, _MISSING)
            if nxt is _MISSING:
                nxt = _import(f"{obj.__name__}.{a}") or _MISSING
        else:
            nxt = _MISSING
        if nxt is _MISSING:
            try:
                nxt = getattr(obj, a, _MISSING)
            except Exception:
                nxt = _MISSING
        if nxt is not _MISSING:
            obj = nxt
            continue
        if isinstance(obj, type) and _class_has(obj, a):
            return True
        return False
    return True


def _resolve_from(base: str, parts: list[str]) -> bool | None:
    """Resolve ``parts`` under the module ``base``: ``None`` when no prefix of
    it is a module, else whether the longest module prefix holds the rest."""
    for k in range(len(parts), -1, -1):
        name = ".".join(x for x in (base, *parts[:k]) if x)
        mod = _import(name)
        if mod is not None:
            return _walk(mod, parts[k:])
    return None


def _defined_classes(module: str) -> list[type]:
    mod = _import(module)
    if mod is None or isinstance(mod, _AstModule):
        return []
    return [v for v in vars(mod).values()
            if isinstance(v, type) and getattr(v, "__module__", "") == module]


def resolve(dotted: str, citing_module: str) -> bool:
    """Whether a cited name exists, by the module docstring's order."""
    name = re.sub(r"\(\)$", "", dotted.lstrip("~!.").strip())
    if "…" in name or ".." in name:
        return True  # an elided name, not a citation
    parts = name.split(".")
    if parts[0] == "rx":
        parts[0] = "rietx"
    if not all(p.isidentifier() for p in parts):
        return False
    # 1. absolute from rietx
    if parts[0] == "rietx":
        return bool(_resolve_from("", parts))
    # 2. relative to the citing module and each parent package
    segs = citing_module.split(".")
    for i in range(len(segs), 0, -1):
        if _resolve_from(".".join(segs[:i]), parts):
            return True
    # 3. a builtin, or an importable top-level module
    if len(parts) == 1 and hasattr(builtins, parts[0]):
        return True
    if parts[0] != "rietx" and _import(parts[0]) is not None and not parts[0].startswith(
            "rietx"):
        if _resolve_from("", parts):
            return True
    # 4. an attribute of a class defined in the citing module
    if len(parts) <= 2 and any(
            _class_has(c, parts[-1]) for c in _defined_classes(citing_module)):
        return True
    # 5. a top-level name of any rietx module, walked from there
    return any(_resolve_from(module, parts) for module in top_level_index().get(parts[0], ()))


@cache
def top_level_index() -> dict[str, tuple[str, ...]]:
    """Every name defined at the top level of a rietx module, with its modules.

    Step 5 of the order: a role written ``:meth:`ParameterTable.decode``` in a
    module that does not import ``ParameterTable`` still names live code, and
    this check asks only that.  Imports are not definitions, so they are left
    out.
    """
    index: dict[str, list[str]] = {}
    for path in source_files():
        tree = _tree(path)
        names = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        for name in names:
            index.setdefault(name, []).append(module_name(path.relative_to(ROOT).as_posix()))
    return {k: tuple(v) for k, v in index.items()}


@cache
def class_attribute_names() -> frozenset[str]:
    """Every attribute name any rietx class defines, by `_class_has`'s reading.

    For a literal such as ``model.y_obs``, whose first word is a module's name
    and also a variable's: a literal that resolves as no module path passes
    when every part after the first is an attribute of some rietx class (or a
    base it inherits, pydantic's included).
    """
    out: set[str] = set()
    for module in {m for mods in top_level_index().values() for m in mods}:
        for cls in _defined_classes(module):
            for c in cls.__mro__:
                if c is not object:
                    out.update(vars(c))
                    out.update(getattr(c, "__annotations__", {}))
                    out.update(getattr(c, "model_fields", None) or {})
                    out.update(_self_attributes(c))
    return frozenset(out)


@cache
def rietx_top_names() -> frozenset[str]:
    """``rietx``, ``rx`` and every top-level module or package of rietx."""
    names = {"rietx", "rx"}
    for p in SRC.iterdir():
        if p.suffix == ".py":
            names.add(p.stem)
        elif (p / "__init__.py").is_file():
            names.add(p.name)
    names.discard("__init__")
    return frozenset(names)


# --- path resolution ----------------------------------------------------------


def _path_bases(citing: str) -> list[Path]:
    """Where a path in ``citing`` may be relative to: its own package and each
    parent, then the repo root, ``src/rietx``, ``src`` and ``tests``."""
    out = []
    here = (ROOT / citing).parent
    while here != ROOT and ROOT in here.parents:
        out.append(here)
        here = here.parent
    return [*out, ROOT, SRC, ROOT / "src", ROOT / "tests", ROOT / "docs" / "docs",
            ROOT / "gui" / "src", ROOT / "gui"]


@cache
def _committable() -> tuple[frozenset[str], frozenset[str]]:
    """The files and directories a commit of this tree would hold.

    Read from git, never the disk: a build output or a run's file exists in a
    working checkout and not in CI's, so a disk check passes here and fails
    there.  Untracked files that are not ignored count, as a commit would
    take them."""
    files = frozenset(subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True, encoding="utf-8", check=True).stdout.splitlines())
    dirs = frozenset(str(p) for f in files for p in Path(f).parents if str(p) != ".")
    return files, dirs


def in_tree(path: Path) -> str | None:
    """``"file"`` or ``"dir"`` if a commit of this tree holds ``path``."""
    try:
        rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None
    files, dirs = _committable()
    return "file" if rel in files else "dir" if rel in dirs else None


@cache
def generated(rel: str) -> bool:
    """Whether ``.gitignore`` covers ``rel``: something a build or a run writes,
    named by a rule rather than cited as a file in the tree."""
    return subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", rel.rstrip("/")],
        capture_output=True).returncode == 0


@cache
def _test_nodes(path: Path) -> frozenset[str]:
    """``name`` and ``Class::name`` for every function and class in a file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return frozenset()
    out = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
            if isinstance(node, ast.ClassDef):
                out.update(f"{node.name}::{m.name}" for m in node.body
                           if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return frozenset(out)


def resolve_path(path: str, node: str | None, citing: str) -> bool:
    for base in _path_bases(citing):
        for found in (base / path, (base / path).with_suffix(".md")):
            # a manual page is cited by its built name, ``theory/x.html``
            if in_tree(found) and (found == base / path or path.endswith(".html")):
                return node is None or node in _test_nodes(found)
    return generated(path) and node is None


def _checked_path(path: str) -> bool:
    """Whether a path-shaped token is a citation worth checking."""
    if any(c in path for c in "*{}<>…") or "/../" in path or "/.../" in path:
        return False
    if path.endswith("/"):
        return path.startswith(PATH_ROOTS)
    ext = path.rsplit(".", 1)[-1]
    return ext in PATH_EXTS


# --- the check ----------------------------------------------------------------


def misses_in(block: Block) -> Iterator[Miss]:
    citing = module_name(block.file)
    text = block.text
    for m in ROLE.finditer(text):
        target = re.sub(r"\s+", "", m.group("target"))
        target = re.sub(r"^.*<(.+)>$", r"\1", target)
        if not resolve(target, citing):
            yield Miss(block.file, block.line_of(m.start()), "role",
                       f":{m.group('role')}:`{target}`")
    for m in LITERAL.finditer(text):
        name = m.group("name")
        if name.split(".")[0] not in rietx_top_names():
            continue
        if name.rsplit(".", 1)[-1] in PATH_EXTS:
            continue  # a file name such as ``project.json``: the path check's
        if resolve(name, citing):
            continue
        parts = name.split(".")
        if parts[0] not in ("rietx", "rx") and set(parts[1:]) <= class_attribute_names():
            continue
        yield Miss(block.file, block.line_of(m.start()), "literal", f"``{name}``")
    text = URL.sub(lambda u: " " * len(u.group()), text)  # keeps offsets
    for pattern in (PATH, BARE_TEST):
        for m in pattern.finditer(text):
            path, node = m.group("path"), m.group("node")
            if pattern is PATH and not node and not _checked_path(path):
                continue
            if node and not path.endswith(".py"):
                continue
            if not resolve_path(path, node, block.file):
                cited = path + (f"::{node}" if node else "")
                yield Miss(block.file, block.line_of(m.start()), "path", cited)


def find_misses(files: list[Path] | None = None) -> list[Miss]:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    out = []
    for path in files if files is not None else source_files():
        for block in blocks(path):
            out.extend(misses_in(block))
    return sorted(set(out), key=lambda m: (m.file, m.line, m.cited))


def unallowed(misses: list[Miss]) -> list[Miss]:
    return [m for m in misses if m.cited not in ALLOWLIST]


# --- the allowlist against the base ------------------------------------------


def allowlist_names(source: str) -> set[str]:
    """The keys of ``ALLOWLIST`` in a version of this file, read by AST."""
    for node in ast.parse(source).body:
        target = (node.target if isinstance(node, ast.AnnAssign)
                  else node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == "ALLOWLIST" and isinstance(
                node.value, ast.Dict):
            return {ast.literal_eval(k) for k in node.value.keys if k is not None}
    return set()


REL = "tests/code_references.py"


def delta_main() -> int:
    """Fail an allowlist entry new against the base that shares its change.

    An entry exempts a citation from this check, so one added beside the
    comment it exempts could silence a stale rietx name with nobody reading
    it.  An addition is therefore a change of its own: it passes when the
    change touches no file but this one, and prints a warning either way.
    """
    from tests.skill_caps import _git, base, changed_files, rev_exists

    rev, how = base()
    if rev is None:
        print(f"code references: {how}")
        return 0
    if not rev_exists(rev):
        print(f"code references: {rev} is not in this checkout ({how}); "
              "the checkout needs fetch-depth: 2", file=sys.stderr)
        return 1
    shown = _git("show", f"{rev}:{REL}")
    if shown.returncode != 0:
        # the change that adds this file is read whole in its own diff
        print(f"code references: {REL} is new against {how}; every entry is in the diff")
        return 0
    before = allowlist_names(shown.stdout)
    added = sorted(set(ALLOWLIST) - before)
    if not added:
        print(f"code references: no allowlist entry new against {how}")
        return 0
    for name in added:
        print(f"::warning file={REL}::allowlist entry new against the base: {name} "
              f"({ALLOWLIST[name]})")
    others = sorted(changed_files(rev) - {REL})
    if not others:
        print(f"code references: {len(added)} allowlist entries new against {how}, "
              "in a change of their own")
        return 0
    print(f"{len(added)} allowlist entries are new against {how}, in a change that "
          f"also edits {len(others)} other files ({', '.join(others[:5])}"
          f"{', …' if len(others) > 5 else ''}):", file=sys.stderr)
    for name in added:
        print(f"  {name}: {ALLOWLIST[name]}", file=sys.stderr)
    print("An allowlist entry exempts a citation from the check that it names live "
          "code, so it lands in a change that touches only tests/code_references.py. "
          "Where the name was rietx code, rewrite the comment against the code it "
          "describes instead of allowlisting it.", file=sys.stderr)
    return 1


MESSAGE = (
    "A comment or docstring names code, a file or a test that is not in the tree. "
    "Rewrite it against the code it describes now; put the history in the WP file "
    "or the release notes. A name that is not rietx code (another program's keyword, "
    "a file field) goes in tests/code_references.py ALLOWLIST with its reason.")


def main(argv: list[str]) -> int:
    if "--delta" in argv:
        return delta_main()
    misses = unallowed(find_misses())
    for m in misses:
        print(m)
    if misses:
        print(f"\n{len(misses)} citations do not resolve. {MESSAGE}", file=sys.stderr)
        return 1
    print("code references: every citation resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
