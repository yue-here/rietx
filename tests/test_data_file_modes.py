"""No vendored data file carries the executable bit.

A file copied off a share or out of an archive keeps whatever mode it had
there, and git records it.  Twelve Ba₂FeSbSe₅ patterns reached ``main`` as
``100755`` that way (#1073), and the next two series PRs (#1162, #1163) brought
42 more.  Nothing reads the bit, so nothing went red: this test is the one
place that asks.  On a filesystem with no mode bits it passes vacuously, and
the Linux and macOS runs are the ones that can fail it.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = (ROOT / "tests" / "data", ROOT / "src" / "rietx" / "data")


_ANY_X = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def _executable(directory: Path, base: Path = ROOT) -> list[str]:
    return sorted(p.relative_to(base).as_posix() for p in directory.rglob("*")
                  if p.is_file() and os.stat(p).st_mode & _ANY_X)


def test_no_data_file_is_executable():
    offenders = [name for d in DATA_DIRS for name in _executable(d)]
    assert offenders == [], (
        "data files carry the executable bit; clear it with "
        "`git update-index --chmod=-x <file>` (or chmod -x and commit):\n  "
        + "\n  ".join(offenders))


@pytest.mark.skipif(os.name == "nt", reason="chmod sets no executable bit on Windows")
def test_the_mode_guard_can_actually_fail(tmp_path):
    (tmp_path / "pattern.xy").write_text("1 2\n", encoding="utf-8")
    assert _executable(tmp_path, tmp_path) == []
    os.chmod(tmp_path / "pattern.xy", 0o755)
    assert _executable(tmp_path, tmp_path) == ["pattern.xy"]
