"""The PyInstaller hook rietx ships for itself (WP-1950, issue #898).

What can be checked without PyInstaller: the entry point PyInstaller looks
for is declared and resolves, it names a directory holding the hook, and the
hook asks for each of the four things a freeze cannot see by following
imports. The freeze itself (a one-fit script on the compiled tier, stamping
the installed version, recording where ``RIETX_RUNS_DIR`` says) was run by
hand and is recorded in WP-1950's handover log, with the same script frozen
from a tree without the hook as its control.
"""

from __future__ import annotations

import ast
import tomllib
from importlib.metadata import entry_points
from pathlib import Path

import pytest

import rietx
from rietx.__pyinstaller import get_hook_dirs

ROOT = Path(__file__).resolve().parents[1]
GROUP = "pyinstaller40"
TARGET = "rietx.__pyinstaller:get_hook_dirs"


def _hook() -> Path:
    (directory,) = get_hook_dirs()
    return Path(directory) / "hook-rietx.py"


def test_pyproject_declares_the_entry_point_pyinstaller_reads():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["entry-points"][GROUP] == {"hook-dirs": TARGET}


def test_the_installed_entry_point_resolves_to_the_hook():
    """What PyInstaller does at analysis time, short of PyInstaller: find the
    group, load the function, and look for ``hook-<package>.py`` there."""
    found = [e for e in entry_points(group=GROUP) if e.value == TARGET]
    if not found:
        pytest.skip("this install predates the entry point: reinstall rietx "
                    "(uv pip install -e \".[dev]\") so its dist-info carries it")
    (point,) = found
    assert point.load() is get_hook_dirs
    assert _hook().is_file()
    assert Path(get_hook_dirs()[0]).is_absolute()


def test_the_hook_package_imports_nothing_from_pyinstaller():
    """``rietx.__pyinstaller`` is importable on an install without PyInstaller,
    which is every install: only the hook file, run inside a build, may."""
    source = (Path(get_hook_dirs()[0]) / "__init__.py").read_text(encoding="utf-8")
    assert "PyInstaller" not in "".join(
        ast.unparse(n) for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Import | ast.ImportFrom))


def test_the_hook_asks_for_what_a_freeze_cannot_see():
    """Data files, every submodule, the kernel wheel and the dist-info: each
    absent from a freeze that follows imports alone (the hook's docstring)."""
    tree = ast.parse(_hook().read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert {"collect_data_files", "collect_submodules", "copy_metadata"} <= called
    names = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
             for t in n.targets if isinstance(t, ast.Name)}
    assert {"hiddenimports", "datas"} <= names
    constants = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)}
    assert "rietx_kernels" in constants
    import rietx.model.compiled as compiled
    assert "import rietx_kernels" in Path(compiled.__file__).read_text(encoding="utf-8")


def test_the_hook_leaves_out_what_the_wheel_leaves_out():
    """An editable install has the ``CLAUDE.md`` rulebooks inside the package,
    and ``collect_data_files`` would take them; the wheel excludes them."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel_excludes = project["tool"]["hatch"]["build"]["targets"]["wheel"]["exclude"]
    tree = ast.parse(_hook().read_text(encoding="utf-8"))
    (call,) = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Name) and n.func.id == "collect_data_files"]
    assert [k.arg for k in call.keywords] == ["excludes"]
    (excluded,) = [ast.literal_eval(n.value) for n in ast.walk(tree)
                   if isinstance(n, ast.Assign) and ast.unparse(n.targets[0])
                   == ast.unparse(call.keywords[0].value)]
    assert "**/CLAUDE.md" in wheel_excludes
    assert set(wheel_excludes) <= set(excluded)


def test_the_static_directories_the_hook_collects_are_inside_the_package():
    """``collect_data_files`` takes only files under the package, so a page
    directory that moved outside it would leave a frozen app without it."""
    package = Path(rietx.__file__).resolve().parent
    from rietx.viz.chart import CHART_DIR
    from rietx.watch import STATIC_DIR as WATCH_STATIC
    for directory in (Path(CHART_DIR), Path(WATCH_STATIC)):
        assert directory.resolve().is_relative_to(package), directory
