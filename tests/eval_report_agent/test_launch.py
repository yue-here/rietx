"""Unit tests for the 2.3 cell launcher: what reaches the cell, never a model
call."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.eval_report_agent import launch as la
from tests.eval_report_agent.mine_transcripts import cell_of
from tests.eval_report_agent.python_arm import REPO_ROOT


def test_the_cell_environment_carries_nothing_of_the_launching_session():
    """OLDPWD names the launching checkout and the messaging socket reaches
    the launching session: neither survives, and a repo venv on PATH is
    refused rather than handed on."""
    parent = {"HOME": "/h", "USER": "u", "PATH": "/usr/bin:/bin",
              "OLDPWD": str(REPO_ROOT), "CLAUDE_EFFORT": "xhigh",
              "CLAUDE_CODE_MESSAGING_SOCKET": "/tmp/s.sock",
              "VIRTUAL_ENV": str(REPO_ROOT / ".venv")}
    env = la.clean_env(parent)
    assert set(env) == {"HOME", "USER", "PATH", "LANG"}
    with pytest.raises(ValueError, match="inside the repo tree"):
        la.clean_env({**parent, "PATH": f"{REPO_ROOT / '.venv' / 'bin'}:/bin"})


def test_the_command_keeps_user_settings_out_and_names_the_cell(tmp_path):
    ws = tmp_path / "RUNS" / "python__sonnet" / "N1"
    cmd = la.command(ws, model="sonnet", effort="medium", session="s")
    assert cmd[cmd.index("--setting-sources") + 1] == "project,local"
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert cmd[cmd.index("--effort") + 1] == "medium"
    assert cell_of(cmd[2]) == ("python", "sonnet", "N1")


def test_the_mined_transcript_counts_each_tool_call_once():
    """2.3's record: the session file repeats an assistant message as a wire
    row, and mining both counted a/C1's 11 tool calls as 21."""
    use = {"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}
    rows = [{"type": "assistant", "message": {"role": "assistant",
                                              "content": [use]}},
            {"type": la.WIRE_ROW, "message": {"role": "assistant",
                                              "content": [use]}}]
    raw = "\n".join(json.dumps(r) for r in rows) + "\n"
    kept = [json.loads(x) for x in la.minable(raw).splitlines()]
    assert [r["type"] for r in kept] == ["assistant"]


def test_a_record_above_a_workspace_is_refused(tmp_path):
    ws = tmp_path / "RUNS" / "python__sonnet" / "N1"
    ws.mkdir(parents=True)
    (ws / "prompt.md").write_text("p\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sits above workspace"):
        la._check(ws, tmp_path)
    assert la._check(ws, tmp_path / "record") == "N1"
    with pytest.raises(ValueError, match="names no RUNS"):
        la._check(Path(tmp_path), tmp_path / "record")
