"""Unit tests for the python-arm workspace builder (WP-1064).

Synthetic-only builds (the real-data groups are the landing-state suite's to
exercise); no venv is created here — what is tested live is the *refusal*
half of the placement rules, including the one real interpreter always to
hand: the dev venv itself, which resolves rietx into the checkout and must
therefore be refused.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.eval_report_agent import build_fixtures as bf
from tests.eval_report_agent import python_arm as pa


def test_workspace_inside_the_repo_tree_is_refused(tmp_path):
    """"No repo checkout reachable" starts with not building the workspace
    inside one."""
    with pytest.raises(ValueError, match="inside the repo tree"):
        pa.write_workspaces(pa.REPO_ROOT / "eval-runs" / "ws",
                            tmp_path / "truth", python="p")


def test_venv_inside_the_repo_tree_is_refused():
    with pytest.raises(ValueError, match="inside the repo tree"):
        pa.ensure_venv(pa.REPO_ROOT / ".venv-eval")


def test_the_dev_venv_itself_would_be_refused():
    """The worktree-venv lesson (tests/CLAUDE.md § Quoting numbers) as a live
    check: this suite's own interpreter resolves rietx into the checkout —
    editable — which is exactly what the arm must never hand an agent."""
    with pytest.raises(ValueError, match="resolves inside the repo tree"):
        pa.verify_interpreter(Path(sys.executable))


def test_workspace_carries_the_core_the_manual_and_the_contract(tmp_path):
    """episode.json is byte-identical to the JSON arm's core; the manual is
    verbatim and complete (part of the surface, not a treatment); the prompt
    carries the v2 contract, the two-file deliverable and the budget — and
    no condition marker exists anywhere, the audit being N/A by design."""
    pa.write_workspaces(tmp_path / "ws", tmp_path / "truth",
                        python="/opt/eval-venv/bin/python",
                        only=["E1", "J1P"])
    e1 = tmp_path / "ws" / "E1"
    assert {p.name for p in e1.iterdir()} == {
        "episode.json", "skill", "prompt.md"}
    episodes = bf.build_episodes()
    assert (json.loads((e1 / "episode.json").read_text(encoding="utf-8"))
            == episodes["E1"]["core"])
    # the whole tree, byte for byte per file: a cell handed the body without
    # its reference files would be measuring a surface nobody ships (WP-1304)
    source = pa.REPO_ROOT / "docs" / "skill" / "rietx"
    shipped = e1 / "skill"
    assert ({p.relative_to(source) for p in source.rglob("*") if p.is_file()}
            == {p.relative_to(shipped) for p in shipped.rglob("*") if p.is_file()})
    for path in source.rglob("*"):
        if path.is_file():
            assert (shipped / path.relative_to(source)).read_bytes() == path.read_bytes()

    text = (e1 / "prompt.md").read_text(encoding="utf-8")
    assert "final_result.json" in text and "model_dump_json" in text
    assert "/opt/eval-venv/bin/python" in text
    assert "`assumption_wrong`" in text          # the v2 glossaries
    assert "`chemistry_or_contents`" in text
    assert f"hard cap is {pa.MAX_SCRIPT_RUNS}" in text
    assert "## Deliverable" not in text

    j1p = (tmp_path / "ws" / "J1P" / "prompt.md").read_text(encoding="utf-8")
    assert "## Deliverable" in j1p and "phase identification" in j1p

    # the truth tree is the same one the JSON arms grade against
    truth = json.loads((tmp_path / "truth" / "E1.json").read_text(
        encoding="utf-8"))
    assert truth == episodes["E1"]["truth"]
    assert not list((tmp_path / "ws").glob("*.condition.json"))


def test_a_build_s_own_skill_tree_is_the_one_copied(tmp_path):
    """2.3's arms are two builds of the package, and each workspace carries
    that build's skill rather than this checkout's; a directory with no
    SKILL.md is refused rather than copied as an empty skill."""
    tree = tmp_path / "other-skill"
    (tree / "references").mkdir(parents=True)
    (tree / "SKILL.md").write_text("# another build's body\n", encoding="utf-8")
    (tree / "references" / "api.md").write_text("rows\n", encoding="utf-8")
    pa.write_workspaces(tmp_path / "ws", tmp_path / "truth", python="p",
                        only=["E1"], skill_src=tree)
    shipped = tmp_path / "ws" / "E1" / "skill"
    assert ({p.relative_to(shipped) for p in shipped.rglob("*") if p.is_file()}
            == {Path("SKILL.md"), Path("references/api.md")})
    assert (shipped / "SKILL.md").read_text(encoding="utf-8") == (
        "# another build's body\n")
    with pytest.raises(ValueError, match="no SKILL.md"):
        pa.write_workspaces(tmp_path / "ws2", tmp_path / "truth", python="p",
                            only=["E1"], skill_src=tmp_path / "empty")


def test_unknown_episode_id_is_refused(tmp_path):
    with pytest.raises(ValueError, match="unknown episode id"):
        pa.write_workspaces(tmp_path / "ws", tmp_path / "truth",
                            python="p", only=["R1"])
