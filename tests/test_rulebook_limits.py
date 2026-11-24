"""The rulebook budgets held against the base (WP-2233): planted breaks.

The ceiling is checked on every tree in `tests/test_docs_consistency.py`.  This
file plants each failure the base comparison exists for, with the base's files
served from a dict in place of `git show`.
"""

from __future__ import annotations

import pytest

from tests import rulebook_limits as rl


class _Shown:
    def __init__(self, text: str | None):
        self.returncode = 0 if text is not None else 128
        self.stdout = text or ""


def _table(limits: dict[str, tuple[int, int]]) -> str:
    rows = "".join(f"    {k!r}: {v!r},\n" for k, v in limits.items())
    return f"LIMITS: dict[str, tuple[int, int]] = {{\n{rows}}}\n"


@pytest.fixture
def base(monkeypatch):
    """A base whose files are this tree's, unless a test replaces one."""
    files = {rel: (rl.ROOT / rel).read_text(encoding="utf-8") for rel in rl.documents()}
    files[rl.REL] = (rl.ROOT / rl.REL).read_text(encoding="utf-8")
    changed: set[str] = set()

    def show(_verb, spec):
        return _Shown(files.get(spec.split(":", 1)[1]))

    monkeypatch.setattr(rl, "_git", show)
    monkeypatch.setattr(rl, "changed_files", lambda rev: set(changed))
    return files, changed


def test_an_unchanged_tree_passes(base):
    assert rl.check("BASE", "a planted base") == ([], [])


def test_a_grown_rulebook_fails_against_the_base_budget(base):
    files, changed = base
    now = rl.size(files["tests/CLAUDE.md"])
    files["tests/CLAUDE.md"] = "a" * (now - 300)   # the base was 300 B smaller
    changed.add("tests/CLAUDE.md")
    base_table = {**rl.LIMITS, "tests/CLAUDE.md": (rl.LIMITS["tests/CLAUDE.md"][0] - 300,
                                                   rl.LIMITS["tests/CLAUDE.md"][1])}
    files[rl.REL] = _table(base_table)
    changed.add(rl.REL)
    failures, warnings = rl.check("BASE", "a planted base")
    grown = [f for f in failures if f.startswith("tests/CLAUDE.md")]
    assert len(grown) == 1 and "grew it by 300 B" in grown[0]
    assert "Cut, or move" in grown[0] and "raise" not in grown[0].lower()


def test_a_raise_inside_a_content_change_fails_and_warns(base):
    files, changed = base
    lowered = {**rl.LIMITS, "CLAUDE.md": (rl.LIMITS["CLAUDE.md"][0] - 10,
                                          rl.LIMITS["CLAUDE.md"][1])}
    files[rl.REL] = _table(lowered)
    changed.update({rl.REL, "src/rietx/refine.py"})
    failures, warnings = rl.check("BASE", "a planted base")
    assert warnings == [f"CLAUDE.md: limits raised from {lowered['CLAUDE.md']} to "
                        f"{rl.LIMITS['CLAUDE.md']} B"]
    assert any("raises 1 limits and also edits src/rietx/refine.py" in f for f in failures)


def test_a_raise_in_a_change_of_its_own_passes_with_a_warning(base):
    files, changed = base
    files[rl.REL] = _table({**rl.LIMITS, "CLAUDE.md": (1, 2)})
    changed.update({rl.REL, rl.DIARY})
    failures, warnings = rl.check("BASE", "a planted base")
    assert failures == [] and len(warnings) == 1


def test_a_document_the_base_table_lacks_is_held_to_the_entry_default(base):
    files, changed = base
    files[rl.REL] = _table({k: v for k, v in rl.LIMITS.items() if k != "CLAUDE.md"})
    failures, warnings = rl.check("BASE", "a planted base")
    # CLAUDE.md is far over NEW_BUDGET but did not grow; its row reads as a raise
    assert not [f for f in failures if f.startswith("CLAUDE.md is")]
    assert warnings == [f"CLAUDE.md: limits raised from {(rl.NEW_BUDGET, rl.NEW_CEILING)} "
                        f"to {rl.LIMITS['CLAUDE.md']} B"]


def test_the_change_that_adds_the_table_passes(base):
    files, _ = base
    files[rl.REL] = None
    assert rl.check("BASE", "a planted base") == (
        [], [f"{rl.REL} is new against a planted base; its limits are in the diff"])


def test_a_pull_request_with_no_base_fails(monkeypatch, capsys):
    monkeypatch.setattr(rl, "base", lambda: ("HEAD^1", "the pull request's base"))
    monkeypatch.setattr(rl, "rev_exists", lambda rev: False)
    assert rl.main() == 1
    assert "fetch-depth: 2" in capsys.readouterr().err
