"""The suite's own invocation is a contract, and one clause of it fails silently.

``@pytest.mark.xdist_group`` is read by exactly one distribution mode.  Under
``--dist load`` (which is what a bare ``-n`` selects) the marks are inert, the
shared session fixtures rebuild per worker, and the wall-clock budgets start
measuring how the tests were dealt — with nothing going red either way.  So
``conftest.pytest_configure`` refuses that combination, and this file is the
"make the guard fail on purpose once" half of it (``tests/CLAUDE.md`` § Guards
that go quiet instead of red).

The option matrix is asserted against the hook directly rather than through a
subprocess for every row, because what the hook branches on is two values that
xdist has already resolved by ``pytest_configure`` time — measured: no ``-n``
gives ``(None, "no")``, ``-n 0`` gives ``(0, "no")``, ``-n 2`` gives
``(2, "load")``, and ``-n 2 --dist loadgroup`` gives ``(2, "loadgroup")``.  One
end-to-end row then confirms the refusal is a real ``UsageError`` with the real
message, since a hook that raises the right exception into a harness that
swallows it would pass every unit row here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.conftest import REQUIRED_DIST, pytest_configure

ROOT = Path(__file__).resolve().parents[1]


def _config(numprocesses, dist):
    return SimpleNamespace(option=SimpleNamespace(numprocesses=numprocesses, dist=dist))


# (numprocesses, dist) as xdist resolves them, and whether the guard may pass.
@pytest.mark.parametrize(
    ("numprocesses", "dist", "allowed"),
    [
        (None, "no", True),               # no -n: serial, no groups to keep
        (0, "no", True),                  # -n 0: explicitly serial
        (2, REQUIRED_DIST, True),         # the documented parallel invocation
        (2, "load", False),               # a bare -n: the silent case
        (1, "load", False),               # one worker, still the mode that ignores
        (2, "loadscope", False),          # deals a group's members apart too
        (2, "loadfile", False),           # ... and so does this one
        (2, "no", False),                 # workers without a distribution mode
    ],
)
def test_the_guard_admits_exactly_the_invocations_that_read_the_marks(
    numprocesses, dist, allowed
):
    config = _config(numprocesses, dist)
    if allowed:
        assert pytest_configure(config) is None
        return
    with pytest.raises(pytest.UsageError) as excinfo:
        pytest_configure(config)
    message = str(excinfo.value)
    # The message has to name the fix, or it only says that something is wrong.
    assert f"--dist {REQUIRED_DIST}" in message
    assert "xdist_group" in message
    assert "silent" in message


def test_a_missing_xdist_leaves_the_guard_inert():
    """Without xdist neither option exists, and the suite still has to run.

    ``[dev]`` installs xdist, so this row is about the ``--no-deps`` and distro
    installs the package supports elsewhere (``model/compiled.py``'s soft
    import of the kernel wheel is the same bargain) — the hook reads both
    options through ``getattr`` for this reason.
    """
    assert pytest_configure(SimpleNamespace(option=SimpleNamespace())) is None


def test_the_guard_refuses_a_real_bare_dash_n_run():
    """End-to-end: a real ``-n 2`` must exit on a usage error, not run green."""
    pytest.importorskip("xdist", reason="the refusal needs the option to exist")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-n", "2", "--collect-only",
         "tests/test_suite_config.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == pytest.ExitCode.USAGE_ERROR, proc.stdout[-2000:]
    assert f"--dist {REQUIRED_DIST}" in proc.stderr + proc.stdout


def test_the_documented_parallel_invocation_is_accepted():
    """The other half: the command CLAUDE.md gives must reach collection."""
    pytest.importorskip("xdist", reason="the invocation under test needs xdist")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-n", "2", "--dist", REQUIRED_DIST,
         "--collect-only", "tests/test_suite_config.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == pytest.ExitCode.OK, (proc.stdout + proc.stderr)[-2000:]
