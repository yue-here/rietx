"""Which cases the jax job runs: the ones whose code names jax, read off the code.

The per-push jax job used to run the whole fast tier with ``[dev,jax]``
installed, and jax changes the outcome of a few files only: 73 cases skip
without it, and one module skips at import (WP-2019).  So the job runs
``--jax-cases``, and ``conftest.pytest_collection_modifyitems`` keeps the
cases that reach jax.  A case reaches jax when any of three things holds:

(a) a parametrization value is a string naming jax: ``"jax"`` or
    ``"jax+fp32"``, never ``"jaxtyping"``;
(b) its test function, or a fixture it requests that is defined under
    ``tests/``, names jax in its code: the name ``jax``, an import of jax, or
    a string such as ``importorskip("jax")`` takes.  Decorators are not read,
    so ``@pytest.mark.parametrize("name", ["jax", "torch"])`` selects the jax
    row alone, through (a).  Nor are docstrings or comments;
(c) its module imports jax, or calls ``importorskip("jax")``, in code that
    runs at import: outside every def, class bodies included.  A module-level
    *data* constant naming jax does not select the whole module, since (a)
    already reaches the rows built from it.

The selection is derived and never listed: a hand-kept list of files rots
silently, as ``features["indexing"]`` did (WP-1037).  Derived, it can still miss
a case whose route to jax runs through a helper it does not read.  So the
guard in ``conftest``, active wherever jax does not import, fails a case that
skips for want of jax while this module does not select it.  Every other leg
lacks jax, so no per-push leg would run that case, and the guard turns that
silence red.  The fix it names is to name jax in the test itself.
"""

from __future__ import annotations

import ast
import functools
import importlib.util
import inspect
import re
import textwrap
from collections.abc import Iterator
from pathlib import Path

TESTS = Path(__file__).resolve().parent
#: a string naming jax: ``"jax"``, ``"jax+fp32"``, ``"jax.numpy"``, not ``"jaxtyping"``
NAMES_JAX = re.compile(r"^jax(?![A-Za-z0-9_])")
#: a skip reason saying jax was missing: ``could not import 'jax': ...``
SKIPS_FOR_JAX = re.compile(r"\bjax\b")
_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


@functools.cache
def jax_importable() -> bool:
    """Whether jax can be found here, which is when the guard stands down."""
    return importlib.util.find_spec("jax") is not None


@functools.cache
def _text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def _is_docstring(node: ast.AST) -> bool:
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str))


def _imports_jax(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(NAMES_JAX.match(alias.name) for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return not node.level and bool(node.module) and bool(NAMES_JAX.match(node.module))
    return False


def _walk(nodes: list[ast.AST], *, into_defs: bool) -> Iterator[ast.AST]:
    """Every node under ``nodes``, bare string statements left out, and what
    nested defs and lambdas hold too only when ``into_defs``."""
    stack = list(reversed(nodes))
    while stack:
        node = stack.pop()
        if _is_docstring(node) or (not into_defs and isinstance(node, _DEFS)):
            continue
        yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def names_jax(source: str) -> bool:
    """Whether a function's code names jax: rule (b) on one ``def``.

    Its body and its argument defaults are read; its decorators are not."""
    tree = ast.parse(textwrap.dedent(source))
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    if not defs:
        return False
    fn = defs[0]
    nodes: list[ast.AST] = [*fn.body, *fn.args.defaults,
                            *(d for d in fn.args.kw_defaults if d is not None)]
    for node in _walk(nodes, into_defs=True):
        if isinstance(node, ast.Name) and node.id == "jax":
            return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and NAMES_JAX.match(node.value):
            return True
        if _imports_jax(node):
            return True
    return False


def module_names_jax(source: str) -> bool:
    """Whether a module imports jax, or skips without it, at import: rule (c).

    What runs at import is every statement outside a def, class bodies
    included, since a class body runs when the module does."""
    for node in _walk(ast.parse(source).body, into_defs=False):
        if _imports_jax(node):
            return True
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            first = node.args[0]
            if name == "importorskip" and isinstance(first, ast.Constant) \
                    and isinstance(first.value, str) and NAMES_JAX.match(first.value):
                return True
    return False


@functools.cache
def module_reaches(path: str | Path) -> bool:
    """Rule (c) for a module file, cached per path."""
    text = _text(str(path))
    return "jax" in text and module_names_jax(text)


@functools.cache
def _code_reaches(code) -> bool:
    if "jax" not in _text(code.co_filename):
        return False
    return names_jax(inspect.getsource(code))


def function_reaches(fn) -> bool:
    """Rule (b) for one function, cached per code object."""
    fn = inspect.unwrap(getattr(fn, "__func__", fn))
    code = getattr(fn, "__code__", None)
    if code is None:
        return False
    try:
        return _code_reaches(code)
    except (OSError, TypeError, SyntaxError):
        return False


@functools.cache
def _file_under_tests(filename: str) -> bool:
    return Path(filename).resolve().is_relative_to(TESTS)


def _under_tests(fn) -> bool:
    fn = inspect.unwrap(getattr(fn, "__func__", fn))
    code = getattr(fn, "__code__", None)
    return code is not None and _file_under_tests(code.co_filename)


def reaches(item) -> bool:
    """Whether a collected case reaches jax by rule (a), (b) or (c)."""
    callspec = getattr(item, "callspec", None)
    if callspec is not None and any(isinstance(v, str) and NAMES_JAX.match(v)
                                    for v in callspec.params.values()):
        return True
    fn = getattr(item, "function", None)
    if fn is not None and function_reaches(fn):
        return True
    info = getattr(item, "_fixtureinfo", None)
    for name in getattr(item, "fixturenames", ()):
        for fixturedef in (info.name2fixturedefs.get(name, ()) if info else ()):
            if _under_tests(fixturedef.func) and function_reaches(fixturedef.func):
                return True
    path = getattr(item, "path", None)
    return path is not None and module_reaches(path)


def skip_reason(longrepr) -> str:
    """The text of a skip report's ``longrepr``: ``(path, line, "Skipped: ...")``."""
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2])
    return str(longrepr)


def guard(longrepr, selected, node) -> str | None:
    """Both hooks' guard on one skip report of ``node``: its failure text, or ``None``.

    It stands only where jax cannot be found, and ``selected`` (a callable, so
    the code is read only for a skip naming jax) says whether the selection
    holds the skipped case or module."""
    reason = skip_reason(longrepr)
    if not SKIPS_FOR_JAX.search(reason) or jax_importable():
        return None
    return outside_selection(reason, selected(), node.nodeid)


def outside_selection(reason: str, selected: bool, what: str = "this case") -> str | None:
    """The guard's failure text, or ``None`` when the skip is not the guard's business.

    A skip whose reason names jax, on a case this module does not select, would
    run on no per-push leg: the jax job runs the selection alone, and every
    other leg lacks jax."""
    if selected or not SKIPS_FOR_JAX.search(reason):
        return None
    return (
        f"{what} skipped for want of jax ({reason.strip()}), and tests/jax_cases.py "
        "does not select it.  The per-push jax job runs only the cases that reach "
        "jax and every other leg lacks jax, so no per-push leg would run it.  Name "
        "jax where tests/jax_cases.py reads: a parameter value such as \"jax\", or "
        "pytest.importorskip(\"jax\") or `import jax` in the test, in a fixture "
        "defined under tests/, or at the module's top level.")
