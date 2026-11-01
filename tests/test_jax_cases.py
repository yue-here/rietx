"""The jax job's selection and its guard (``tests/jax_cases.py``, WP-2019).

The selection is read off each case's code, so most rows here feed it sources
and fake items and pin which of them reach jax.  The guard is the half that
fails loudly: a case skipping for want of jax that the selection cannot see
would otherwise run on no per-push leg.  End-to-end rows run a real
collection, and a real run of the guard where jax does not import.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import jax_cases
from tests.conftest import pytest_make_collect_report, pytest_runtest_makereport

ROOT = Path(__file__).resolve().parents[1]
JAX_SKIP = "Skipped: could not import 'jax': No module named 'jax'"


def _src(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


# ------------------------------------------------- rule (b): a function's code
@pytest.mark.parametrize("body", [
    'pytest.importorskip("jax")',
    "import jax.numpy as jnp",
    "from jax import numpy",
    "return jax.jacfwd(f)",
    'xp = resolve_backend("jax+fp32")',
    'class _Xp:\n        name = "jax"',
    'out = f"jax {x}"',
])
def test_a_function_whose_body_names_jax_reaches_it(body):
    assert jax_cases.names_jax(f"def test_x():\n    {body}\n")


def test_an_argument_default_naming_jax_reaches_it():
    assert jax_cases.names_jax('def test_x(name="jax"):\n    return name\n')


def test_a_parametrize_decorator_is_not_read_so_its_torch_row_is_not_selected():
    """The jax row is reached through its parameter value, rule (a)."""
    assert not jax_cases.names_jax(_src('''
        @pytest.mark.parametrize("name", ["jax", "torch"])
        def test_x(name):
            assert name
    '''))


def test_a_docstring_or_comment_naming_jax_does_not_reach_it():
    """``test_batched_forward`` says it avoids installing jax in a docstring."""
    assert not jax_cases.names_jax(_src('''
        def test_x():
            """jax autodiff is not used here."""
            # jax neither
            "jax, a bare string statement, is another docstring"
            return 1
    '''))


@pytest.mark.parametrize("body", [
    "import jaxtyping", 'return "jaxtyping"', 'return "a jax string"',
    "return jax_backend", 'from rietx.backend.jax_backend import f',
])
def test_a_name_that_only_begins_with_or_contains_jax_does_not_reach_it(body):
    assert not jax_cases.names_jax(f"def test_x():\n    {body}\n")


def test_an_indented_method_is_read_like_a_function():
    assert jax_cases.names_jax('    def test_x(self):\n        import jax\n')


# --------------------------------------------- rule (c): what runs at import
@pytest.mark.parametrize("source", [
    'import pytest\njax = pytest.importorskip("jax")',
    'pytest.importorskip("jax.numpy")',
    "import jax",
    "try:\n    import jax\nexcept ImportError:\n    jax = None",
    'class TestX:\n    jax = pytest.importorskip("jax")',
])
def test_a_module_that_imports_or_skips_on_jax_at_import_reaches_it(source):
    """Each source begins with something other than jax, or rule (a) would
    send this case to the jax job for its parameter."""
    assert jax_cases.module_names_jax(source + "\n")


@pytest.mark.parametrize("source", [
    'METHODS = {"jax": 1, "torch": 2}',
    'def test_x():\n    pytest.importorskip("jax")',
    'pytest.importorskip("jaxtyping")',
    '"""jax is named in this docstring."""',
    "check = lambda: __import__('jax')",
])
def test_a_module_constant_or_a_def_naming_jax_does_not_select_the_module(source):
    """``test_cross_backend``'s ``METHODS`` reaches its jax rows through (a)."""
    assert not jax_cases.module_names_jax(source + "\n")


# --------------------------------------------------------- reaches(item)
def _plain():
    return 1


def _fixture_that_skips_without_jax():
    pytest.importorskip("jax")


def _item(path, *, params=None, function=_plain, fixtures=()):
    """A collected case as ``reaches`` reads one."""
    return SimpleNamespace(
        callspec=None if params is None else SimpleNamespace(params=params),
        function=function,
        fixturenames=[name for name, _ in fixtures],
        _fixtureinfo=SimpleNamespace(name2fixturedefs={
            name: (SimpleNamespace(func=fn),) for name, fn in fixtures}),
        path=path)


@pytest.fixture
def plain_module(tmp_path):
    path = tmp_path / "test_plain.py"
    path.write_text("def test_x():\n    pass\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(("params", "selected"), [
    ({"name": "jax"}, True), ({"method": "jax+fp32", "config": "toy"}, True),
    ({"name": "torch"}, False), ({"name": "jaxtyping"}, False),
    ({"name": 3, "other": None}, False), ({}, False),
])
def test_a_parametrization_value_naming_jax_selects_the_case(plain_module, params,
                                                             selected):
    assert jax_cases.reaches(_item(plain_module, params=params)) is selected


def test_a_fixture_defined_under_tests_that_skips_without_jax_selects_the_case(
        plain_module):
    item = _item(plain_module, fixtures=[("needs_jax", _fixture_that_skips_without_jax)])
    assert jax_cases.reaches(item)


def test_a_fixture_defined_outside_tests_is_not_read():
    """``resolve_backend`` compares its argument with "jax", and a case that
    requests a library function as a fixture does not reach jax for that."""
    from rietx.backend.api import resolve_backend

    assert jax_cases.names_jax(inspect.getsource(resolve_backend))
    item = _item(Path(__file__), fixtures=[("backend", resolve_backend)])
    assert not jax_cases.reaches(item)


def test_a_module_that_skips_without_jax_at_import_selects_every_case_in_it(tmp_path):
    path = tmp_path / "test_needs_jax.py"
    path.write_text('import pytest\n\njax = pytest.importorskip("jax")\n', encoding="utf-8")
    assert jax_cases.reaches(_item(path))


# ----------------------------------------------------------------- the guard
def test_the_guard_fails_a_jax_skip_outside_the_selection_and_says_how_to_fix_it():
    message = jax_cases.outside_selection(JAX_SKIP, False, "tests/test_x.py::test_y")
    assert message is not None
    assert message.startswith("tests/test_x.py::test_y skipped for want of jax")
    assert "tests/jax_cases.py does not select it" in message
    assert "no per-push leg would run it" in message
    assert 'importorskip("jax")' in message


@pytest.mark.parametrize(("reason", "selected"), [
    (JAX_SKIP, True),
    ("Skipped: could not import 'torch': No module named 'torch'", False),
    ("Skipped: needs jaxtyping", False),
    ("Skipped: dataset for state 'nac' not present", False),
])
def test_the_guard_passes_a_selected_case_and_a_skip_that_is_not_for_jax(reason, selected):
    assert jax_cases.outside_selection(reason, selected) is None


def test_a_skip_reason_is_read_off_either_shape_of_longrepr():
    assert jax_cases.skip_reason(("t.py", 3, JAX_SKIP)) == JAX_SKIP
    assert jax_cases.skip_reason(JAX_SKIP) == JAX_SKIP


def _report(outcome, longrepr, **extra):
    report = pytest.TestReport("tests/test_x.py::test_y", ("tests/test_x.py", 1, "test_y"),
                               {}, outcome, longrepr, "call")
    report.__dict__.update(extra)
    return report


def _wrapped(hook, *args, report):
    wrapper = hook(*args)
    next(wrapper)
    with pytest.raises(StopIteration) as done:
        wrapper.send(report)
    return done.value.value


@pytest.mark.parametrize(("params", "extra", "outcome"), [
    (None, {}, "failed"),                         # nothing in the case names jax
    ({"name": "jax"}, {}, "skipped"),             # the selection holds it
    (None, {"wasxfail": "jax"}, "skipped"),       # an xfail is not a skip
])
def test_the_runtest_guard_fails_only_a_jax_skip_the_selection_cannot_see(
        monkeypatch, plain_module, params, extra, outcome):
    """Run as if jax were absent, which is the only place the guard stands."""
    monkeypatch.setattr(jax_cases, "jax_importable", lambda: False)
    item = _item(plain_module, params=params)
    item.nodeid = "tests/test_x.py::test_y"
    report = _wrapped(pytest_runtest_makereport, item, None,
                      report=_report("skipped", ("t.py", 1, JAX_SKIP), **extra))
    assert report.outcome == outcome
    if outcome == "failed":
        assert "tests/jax_cases.py does not select it" in report.longrepr


def test_the_runtest_guard_stands_down_where_jax_imports(monkeypatch, plain_module):
    monkeypatch.setattr(jax_cases, "jax_importable", lambda: True)
    item = _item(plain_module)
    item.nodeid = "tests/test_x.py::test_y"
    report = _wrapped(pytest_runtest_makereport, item, None,
                      report=_report("skipped", ("t.py", 1, JAX_SKIP)))
    assert report.outcome == "skipped"


class _StubModule(pytest.Module):
    """A ``Module`` the hook's ``isinstance`` accepts, its node id set directly.

    pytest keeps the id under a private name that 9.2 renamed (``_nodeid`` to
    ``_id``), so the stub owns the property rather than writing either."""

    nodeid = property(lambda self: self.path.name)


def _module(path, *, jax_only=False, shard=None):
    module = object.__new__(_StubModule)
    module.config = SimpleNamespace(option=SimpleNamespace(shard=shard, jax_cases=jax_only))
    module.path = path
    return module


def _collect_skip(reason):
    return pytest.CollectReport("test_m.py", "skipped", ("test_m.py", 1, reason), [])


@pytest.mark.parametrize(("source", "outcome"), [
    ('import pytest\n\npytest.importorskip("jax")\n', "skipped"),
    ('import pytest\n\npytest.importorskip("".join(["j", "a", "x"]))\n', "failed"),
])
def test_a_module_skipped_at_import_for_jax_fails_unless_it_names_jax_at_import(
        monkeypatch, tmp_path, source, outcome):
    """The second spells the name at runtime, the route the selection cannot read."""
    monkeypatch.setattr(jax_cases, "jax_importable", lambda: False)
    path = tmp_path / "test_m.py"
    path.write_text(source, encoding="utf-8")
    report = _wrapped(pytest_make_collect_report, _module(path), report=_collect_skip(JAX_SKIP))
    assert report.outcome == outcome


@pytest.mark.parametrize(("source", "reason", "outcome"), [
    ('import pytest\n\npytest.importorskip("jax")\n', JAX_SKIP, "skipped"),
    ("import pytest\n\npytest.importorskip('torch')\n", "Skipped: no torch", "passed"),
])
def test_jax_cases_leaves_out_a_module_skipped_at_import_that_it_does_not_select(
        tmp_path, source, reason, outcome):
    """Such a module has no item to deselect, and the jax job would count
    every browser file's skip as its own without this."""
    path = tmp_path / "test_m.py"
    path.write_text(source, encoding="utf-8")
    report = _wrapped(pytest_make_collect_report, _module(path, jax_only=True),
                      report=_collect_skip(reason))
    assert report.outcome == outcome


# -------------------------------------------------------------- end to end
def _pytest(*args, cwd=ROOT):
    return subprocess.run([sys.executable, "-m", "pytest", *args], cwd=cwd,
                          capture_output=True, encoding="utf-8",
                          timeout=600)  # a runaway guard: these collect, or run four stubs


def _collected(*extra):
    proc = _pytest("--collect-only", *extra, "tests/test_cross_backend.py",
                   "tests/test_rotation.py", "tests/test_capabilities.py")
    assert proc.returncode == pytest.ExitCode.OK, (proc.stdout + proc.stderr)[-2000:]
    return {line for line in proc.stdout.splitlines() if "::" in line}


def test_a_real_collection_keeps_the_jax_rows_and_leaves_the_rest():
    """End-to-end, so the option, the hook and real parametrize ids are read.

    Every agreement-matrix row is kept exactly when its method is a jax one,
    and of the other two files, the cases that name jax in their code."""
    whole, kept = _collected(), _collected("--jax-cases")
    assert kept < whole
    matrix = {n for n in whole if "::test_jacobian_matches_analytic[" in n}
    assert matrix
    for node in matrix:
        method = node.split("[", 1)[1].split("-", 1)[0]
        assert (node in kept) is bool(jax_cases.NAMES_JAX.match(method)), node
    assert {"tests/test_rotation.py::test_jacobian_matches_jax_autodiff_and_stays_finite_at_zero",
            "tests/test_capabilities.py::test_every_backend_appears_with_its_flags"} <= kept
    assert not {n for n in kept if "test_rotation.py::test_jacobian_near_pi" in n}
    assert "tests/test_capabilities.py::test_every_solver_mode_and_plan_appears" not in kept


GUARDED = {
    "test_cases.py": '''
        import pytest

        NAME = "".join(["j", "a", "x"])


        def _needs():
            pytest.importorskip(NAME)


        def test_skips_through_a_helper():
            _needs()


        def test_skips_naming_it():
            pytest.importorskip("jax")
    ''',
    "test_module_spelled.py": '''
        import pytest

        pytest.importorskip("".join(["j", "a", "x"]))


        def test_x():
            pass
    ''',
    "test_module_named.py": '''
        import pytest

        pytest.importorskip("jax")


        def test_x():
            pass
    ''',
}


@pytest.mark.skipif(jax_cases.jax_importable(), reason="the guard stands down where jax imports")
def test_a_real_run_fails_each_jax_skip_the_selection_cannot_see(tmp_path):
    """The conftest loaded as a plugin over files outside the tree, so the
    wiring is the real one: a case and a module whose skip names jax through
    a runtime-built name fail, and the two that name it skip."""
    for name, source in GUARDED.items():
        (tmp_path / name).write_text(_src(source), encoding="utf-8")
    proc = _pytest("-p", "tests.conftest", "--continue-on-collection-errors", "-rfEs",
                   "-p", "no:cacheprovider", str(tmp_path), f"--rootdir={tmp_path}")
    out = proc.stdout + proc.stderr
    assert proc.returncode == pytest.ExitCode.TESTS_FAILED, out[-3000:]
    assert "1 failed, 2 skipped, 1 error" in out, out[-3000:]
    # A summary line is the node id, then " - " and the message: whole where
    # `CI` is set (pytest stops truncating there), cut to the terminal or
    # dropped elsewhere.  So read the node id alone, and count the message in
    # the long-form sections, which print it once each either way.
    lines = out.splitlines()
    heads = [line.split(" - ", 1)[0] for line in lines]
    assert any(head.startswith("FAILED") and head.endswith("test_cases.py::test_skips_through_a_helper")
               for head in heads), out[-3000:]
    assert any(head.startswith("ERROR") and head.endswith("test_module_spelled.py")
               for head in heads), out[-3000:]
    body = [line for line in lines if not line.startswith(("FAILED", "ERROR"))]
    assert sum(line.count("tests/jax_cases.py does not select it") for line in body) == 2
