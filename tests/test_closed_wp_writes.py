"""`.claude/hooks/closed_wp_writes.py`: lines a branch adds to a closed WP (WP-1994).

The hook is stdlib-only and lives outside the package, so it is loaded by path
and driven against tmp_path git fixtures, like `test_workflow_hooks.py`.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from rietx.refine import _git_env

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "closed_wp_writes", ROOT / ".claude" / "hooks" / "closed_wp_writes.py"
)
hook = importlib.util.module_from_spec(_spec)
sys.modules["closed_wp_writes"] = hook
_spec.loader.exec_module(hook)


def _wp(number: str, status: str, body: str = "") -> str:
    return (f"# WP-{number} — a title\n\nMilestone: unscheduled · Status: {status}\n"
            f"Depends on: —\n\n## Goal\n\nSomething.\n\n## Handover log\n\n"
            f"- **2026-07-01** — created.\n{body}")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=wp@test", "-c", "user.name=wp",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout


@pytest.fixture(autouse=True)
def _no_git_env(monkeypatch):
    """A git hook running the suite exports GIT_DIR: left in, the fixture's
    `add -A` and `commit` would land in the real repository."""
    for key in set(os.environ) - set(_git_env()):
        monkeypatch.delenv(key)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    wp = root / "docs" / "wp"
    wp.mkdir(parents=True)
    (wp / "0001-closed.md").write_text(_wp("0001", "✅ 2026-07-02"), encoding="utf-8")
    (wp / "0002-open.md").write_text(_wp("0002", "⬜"), encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _write(root: Path, name: str, text: str) -> None:
    (root / "docs" / "wp" / name).write_text(text, encoding="utf-8")


def test_a_note_appended_to_a_closed_wp_is_reported(repo):
    _write(repo, "0001-closed.md", _wp("0001", "✅ 2026-07-02",
                                     "\n### Inherited\n\n- From WP-0009: do the thing.\n"))
    found = hook.scan(repo, "main")
    assert [w.file for w in found] == ["0001-closed.md"]
    assert found[0].glyph == "✅"
    assert found[0].lines == ("### Inherited", "- From WP-0009: do the thing.")


def test_a_note_in_prose_is_reported_too(repo):
    """WP-1907's note to 1903 was a handover-log line, not a heading."""
    _write(repo, "0001-closed.md", _wp("0001", "✅ 2026-07-02",
                                     "- **2026-07-09** — WP-0009 found two bugs here.\n"))
    assert [w.file for w in hook.scan(repo, "main")] == ["0001-closed.md"]


def test_a_committed_write_is_reported_against_the_base(repo):
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, "0001-closed.md", _wp("0001", "✅ 2026-07-02", "- a note\n"))
    _git(repo, "commit", "-q", "-am", "note")
    assert [w.file for w in hook.scan(repo, "main")] == ["0001-closed.md"]


def test_a_wp_closed_upstream_after_the_fork_is_reported(repo):
    """The mailbox race: the owner closes it on main while this branch writes."""
    _git(repo, "checkout", "-q", "-b", "feature")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "0002-open.md", _wp("0002", "✅ 2026-07-09", "- closed, all done\n"))
    _git(repo, "commit", "-q", "-am", "close 0002")
    _git(repo, "checkout", "-q", "feature")
    _write(repo, "0002-open.md", _wp("0002", "⬜", "\n### Inherited\n\n- a note\n"))
    base = _git(repo, "merge-base", "HEAD", "main").strip()
    assert hook.scan(repo, base) == []
    found = hook.scan(repo, base, "main")
    assert [(w.file, w.glyph) for w in found] == [("0002-open.md", "✅")]


def test_a_renamed_closed_wp_is_compared_with_its_old_name(repo):
    _git(repo, "mv", "docs/wp/0001-closed.md", "docs/wp/0001-retitled.md")
    _write(repo, "0001-retitled.md", _wp("0001", "✅ 2026-07-02", "- a note\n"))
    assert [w.file for w in hook.scan(repo, "main")] == ["0001-retitled.md"]


def test_a_rename_sweep_adds_nothing(repo):
    _write(repo, "0001-closed.md",
           _wp("0001", "✅ 2026-07-02").replace("Something.", "Something else."))
    assert hook.scan(repo, "main") == []


def test_reopening_a_closed_wp_is_not_reported(repo):
    _write(repo, "0001-closed.md", _wp("0001", "🔄 2026-07-09", "- reopened: more work\n"))
    assert hook.scan(repo, "main") == []


def test_an_open_wp_and_a_new_wp_are_not_reported(repo):
    _write(repo, "0002-open.md", _wp("0002", "⬜", "\n### Inherited\n\n- a note\n"))
    _write(repo, "0003-new.md", _wp("0003", "✅ 2026-07-09", "- closed on arrival\n"))
    assert hook.scan(repo, "main") == []


def test_closing_ones_own_wp_is_not_reported(repo):
    """The closing session's entry lands while the base still says open."""
    _write(repo, "0002-open.md", _wp("0002", "✅ 2026-07-09", "- closed, all done\n"))
    assert hook.scan(repo, "main") == []


def test_net_added_counts_only_the_growth_of_a_hunk():
    old = "a\nb\nc\n"
    assert hook.net_added(old, "a\nB\nc\n") == []
    assert hook.net_added(old, "a\nB\nB2\nc\n") == ["B2"]
    assert hook.net_added(old, "a\nb\nc\n\nd\n") == ["d"]


def test_the_handover_command_runs_it():
    """The script is only as good as the step that runs it."""
    text = (ROOT / ".claude" / "skills" / "wp-handover" / "SKILL.md").read_text(encoding="utf-8")
    runs = re.findall(r"`python3 (\S+closed_wp_writes\.py)`", text)
    assert runs, "no step in /wp-handover runs closed_wp_writes.py"
    assert all((ROOT / run).resolve() == Path(hook.__file__).resolve() for run in runs)
