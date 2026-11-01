"""The skill eval suite's instrument agrees with itself and with the harness (WP-1905).

Nothing here runs a model. What it pins is everything a round would otherwise
discover at its own expense: a case whose fixture is missing, a grader the
harness would refuse to load, a built plugin carrying a tree other than the one
handed in, a prompt `PROTOCOL.md` does not register, and a read-out
(`readout.py`) that scores, bills or decides other than the way it registers.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from fractions import Fraction
from pathlib import Path

import pytest

from tests.eval_skill import build as B
from tests.eval_skill import readout as R
from tests.eval_skill_placement import runner as placement

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[1]
TREE = REPO / "docs" / "skill" / "rietx"
PROTOCOL = B.HERE / "PROTOCOL.md"
#: WP-1904's result documents: real harness output, kept with the pilot.
PILOT = REPO / "docs" / "wp" / "1904-eval" / "pilot"
#: The eval sandbox exists on macOS and Linux only, so its scaffolds run under
#: `bash` with a POSIX `PATH`, and the paths it records start at a POSIX root,
#: which a Windows path never does.
POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="the eval sandbox is POSIX-only")

#: `claude plugin eval`'s vocabulary (https://code.claude.com/docs/en/plugin-evals,
#: § Eval suite reference, read 2026-10-04). An unknown prompt.md key is an
#: error there, so it is one here.
PROMPT_KEYS = {"schema_version", "name", "description", "tags", "plugins", "runs",
               "expected_outcome", "model", "max_turns", "timeout_seconds",
               "allowed_tools", "append_system_prompt", "env"}
COMMON = {"type", "weight", "arm"}
GRADER_KEYS = {
    "regex": {"pattern", "flags", "match", "target"},
    "tool_used": {"tool", "input_match", "min", "max"},
    "tool_order": {"before", "after"},
    "file_exists": {"path", "exists"},
    "llm": {"criteria", "focus"},
    "baseline": {"baseline_file", "criteria"},
}
VIEWS = {"last_message", "trace", "files", "mock_calls"}


def _front(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = re.fullmatch(r"---\n(.*?)\n---\n?(.*)", text, flags=re.S)
    assert m, f"{path}: no frontmatter"
    return (yaml.safe_load(m.group(1)) or {}), m.group(2).strip()


def _cases() -> list[Path]:
    return B.cases()


def _id(case: Path) -> str:
    return str(case.relative_to(B.CASES))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """A whole build, with the placement episode stubbed: running its fit is
    the slow test's business, and every other layout fact is the same."""
    def stub(dest: Path, python: Path) -> None:
        dest.mkdir(parents=True)
        for name in (*placement.DATA_FILES, "fit.py", "fit_output.txt"):
            (dest / name).write_text(f"stub {name}\n", encoding="utf-8")

    out = tmp_path_factory.mktemp("plugin") / "p"
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(B.EPISODES, "placement", stub)
        stamp = B.build(TREE, out, python=Path("/opt/venv/bin/python"))
    return out, stamp


def test_the_case_set_is_not_empty_and_names_are_unique():
    names = [c.name for c in _cases()]
    assert "fap-judge" in names
    assert len(names) == len(set(names)), "the harness keys its report on the name"


@pytest.mark.parametrize("case", _cases(), ids=_id)
def test_every_prompt_parses_and_says_which_role_it_plays(case):
    meta, body = _front(case / "prompt.md")
    assert set(meta) <= PROMPT_KEYS, set(meta) - PROMPT_KEYS
    assert body, "an empty prompt"
    assert str(meta.get("description", "")).startswith(B.ROLES), (
        f"description must open with one of {B.ROLES}")
    assert 1 <= meta.get("runs", 3) <= 50
    assert meta.get("timeout_seconds", 300) <= 3600 and meta.get("max_turns", 10) <= 200


@pytest.mark.parametrize("case", _cases(), ids=_id)
def test_every_grader_is_one_the_harness_loads(case):
    graders = sorted((case / "graders").glob("*.md"))
    assert graders, "a case without a grader fails to load"
    for g in graders:
        meta, body = _front(g)
        kind = meta.get("type")
        assert kind in GRADER_KEYS, f"{g.name}: type {kind!r}"
        assert set(meta) <= COMMON | GRADER_KEYS[kind], f"{g.name}: {set(meta)}"
        assert meta.get("arm") in (None, "with-only", "both"), g.name
        assert meta.get("weight", 1) > 0, g.name
        view = meta.get("target" if kind == "regex" else "focus", "last_message")
        if isinstance(view, dict):
            assert view.get("source") == "file" and view.get("path"), g.name
        else:
            assert view in VIEWS, f"{g.name}: {view!r}"
        if kind == "regex":
            re.compile(meta["pattern"])  # the harness's is JavaScript; these are the shared subset
        if kind == "tool_used":
            if "input_match" in meta:
                re.compile(meta["input_match"])
            assert meta.get("min", 1) <= meta.get("max", 10**9), g.name
        if kind == "llm":
            assert body or meta.get("criteria"), f"{g.name}: a rubric with no criteria"


@pytest.mark.parametrize("case", [c for c in _cases() if (c / B.INPUTS).exists()], ids=_id)
def test_every_fixture_source_exists(case):
    rows = B.parse_inputs((case / B.INPUTS).read_text(encoding="utf-8"))
    assert rows
    for verb, source, _ in rows:
        if verb == "copy":
            assert (REPO / source).is_file(), source
        elif verb == "episode":
            assert source in B.EPISODES


def test_inputs_refuse_what_they_cannot_read():
    assert B.parse_inputs("copy a/b.txt as c.txt\n# note\nepisode placement\nempty d.xy\n") == [
        ("copy", "a/b.txt", "c.txt"), ("episode", "placement", ""), ("empty", "", "d.xy")]
    for bad in ("cp a b", "copy a b c", "episode nowhere", "copy", "empty", "empty a b"):
        with pytest.raises(ValueError, match="line 1"):
            B.parse_inputs(bad)


def test_a_committed_case_cannot_carry_what_build_writes(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "prompt.md").write_text("---\n---\nhi\n", encoding="utf-8")
    (tmp_path / "x" / "fixture.sh").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="written by build"):
        B.cases(tmp_path)


def test_the_trigger_set_is_balanced_and_scored_in_both_arms():
    """Tier 0: half should fire and half are near-misses that should not, each
    graded by whether `Skill` was called and nothing else (agentskills.io's
    description recipe). `arm: both`, or a two-arm run would drop the grader."""
    roles = {}
    for case in (B.CASES / "trigger").iterdir():
        meta, _ = _front(case / "prompt.md")
        role = next(r for r in B.ROLES if meta["description"].startswith(r))
        roles.setdefault(role, []).append(case.name)
        graders = list((case / "graders").glob("*.md"))
        assert len(graders) == 1, case.name
        g, _ = _front(graders[0])
        assert g["type"] == "tool_used" and g["tool"] == "Skill" and g["arm"] == "both"
        # Only rietx counts, in the grader as in readout's `fired`: one pattern.
        assert g.get("input_match") == R.FIRED.pattern, case.name
        if role == "Should fire.":
            assert g.get("min", 1) >= 1 and "max" not in g, case.name
        else:
            assert role == "Should not fire." and g["min"] == g["max"] == 0, case.name
    assert {r: len(v) for r, v in roles.items()} == {"Should fire.": 10, "Should not fire.": 10}


#: A file name as a tier-0 prompt gives one: `quartz.xy`, `structure.cif`.
FILE_NAME = re.compile(r"\b[A-Za-z][\w-]*\.[a-z]{2,4}\b")


@pytest.mark.parametrize("case", sorted((B.CASES / "trigger").iterdir()), ids=lambda c: c.name)
def test_every_file_a_trigger_prompt_names_starts_empty_in_its_workspace(case):
    """PROTOCOL.md § Amendment 1.2: a prompt naming a file the workspace lacks
    measures the workspace, so each name is an `empty` row of the case's inputs."""
    _, body = _front(case / "prompt.md")
    rows = B.parse_inputs((case / B.INPUTS).read_text(encoding="utf-8")) \
        if (case / B.INPUTS).exists() else []
    assert sorted(FILE_NAME.findall(body)) == sorted(n for v, _, n in rows if v == "empty")
    assert all(v == "empty" for v, _, _ in rows), "tier 0 is handed names, never data"


@POSIX_ONLY
def test_an_empty_input_scaffolds_an_empty_file(built, tmp_path):
    out, _ = built
    case = out / "evals" / "trigger" / "fire-quartz-rietveld"
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["bash", str(case / "fixture.sh")], cwd=ws, check=True, env={"PATH": "/usr/bin:/bin"})
    assert [(p.name, p.stat().st_size) for p in ws.iterdir()] == [("quartz.xy", 0)]


def test_fap_judge_quotes_the_placement_rubric():
    """One authority for the four rubric items: the placement runner's."""
    graders = B.CASES / "fap-judge" / "graders"
    for name, text in placement.RUBRIC.items():
        meta, body = _front(graders / f"{name}.md")
        assert meta == {"type": "llm", "focus": "last_message"}
        assert body.endswith(text), name
    _, body = _front(B.CASES / "fap-judge" / "prompt.md")
    assert body.startswith(placement.PROMPT)


def _flat(text: str) -> str:
    """Whitespace-flattened with blockquote marks dropped, so a prompt quoted
    over wrapped `>` lines or in a table cell still compares: the placement
    round's rule (`tests/eval_skill_placement/test_placement.py`)."""
    return " ".join(re.sub(r"^> ?", "", text, flags=re.M).split())


@pytest.mark.parametrize("case", _cases(), ids=_id)
def test_the_protocol_quotes_every_prompt(case):
    """The registration quotes each prompt as written, `@PYTHON@` included:
    a prompt changed after registration fails here until an amendment quotes
    the new one."""
    _, body = _front(case / "prompt.md")
    assert _flat(body) in _flat(PROTOCOL.read_text(encoding="utf-8")), (
        f"PROTOCOL.md does not quote {_id(case)}'s prompt")


def _graders(case: Path) -> list[dict]:
    """A case's graders as a result document carries them (`cases[].graders`:
    name, type, weight, and every other key under `config`)."""
    out = []
    for g in sorted((case / "graders").glob("*.md")):
        meta, _ = _front(g)
        out.append({"name": g.stem, "type": meta["type"], "weight": meta.get("weight", 1),
                    "config": {k: v for k, v in meta.items() if k not in ("type", "weight")}})
    return out


@pytest.mark.parametrize("case", [c for c in _cases() if c.parent == B.CASES], ids=_id)
def test_the_protocol_states_each_cases_tolerance(case):
    """§ The decision rule's table is what `readout` computes from the graders,
    so a reweighted grader fails here until the table moves with it."""
    kept = R.comparable(_graders(case))
    weights = [g["weight"] for g in kept]
    t = Fraction(min(weights)) / Fraction(sum(weights))
    names = ", ".join(f"{g['name']} {g['weight']}" for g in kept)
    row = f"| `{case.name}` | {names} | {sum(weights)} | {t} |"
    assert row in PROTOCOL.read_text(encoding="utf-8").splitlines()
    assert R.tolerance(_graders(case)) == pytest.approx(float(t))


def test_readout_tells_the_trigger_roles_apart_as_the_cases_declare_them():
    for case in (B.CASES / "trigger").iterdir():
        meta, _ = _front(case / "prompt.md")
        want = "fire" if meta["description"].startswith("Should fire.") else "quiet"
        assert R.tier0(_graders(case)) == want, case.name
    assert all(R.tier0(_graders(c)) is None for c in _cases() if c.parent == B.CASES)


def test_the_build_carries_the_tree_it_was_handed(built):
    out, stamp = built
    assert B.tree_sha256(out / "skills" / "rietx") == B.tree_sha256(TREE) == stamp["tree_sha256"]
    manifest = json.loads((out / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == B.PLUGIN_NAME
    assert json.loads((out / B.STAMP).read_text(encoding="utf-8")) == stamp
    assert sorted(stamp["cases"]) == sorted(_id(c) for c in _cases())


@POSIX_ONLY
def test_the_build_writes_the_interpreter_and_the_scaffold(built, tmp_path):
    out, _ = built
    for rel in map(_id, _cases()):
        prompt = (out / "evals" / rel / "prompt.md").read_text(encoding="utf-8")
        assert B.PYTHON_MARK not in prompt
        assert not (out / "evals" / rel / B.INPUTS).exists()
    judge = out / "evals" / "fap-judge"
    assert "/opt/venv/bin/python" in (judge / "prompt.md").read_text(encoding="utf-8")
    assert yaml.safe_load((judge / "case.yaml").read_text(encoding="utf-8")) == {
        "schema_version": "1.1", "name": "fap-judge",
        "context": {"scaffold_script": "fixture.sh"}}
    # The scaffold runs in an empty workspace with no variable naming the case.
    ws = tmp_path / "ws"
    ws.mkdir()
    subprocess.run(["bash", str(judge / "fixture.sh")], cwd=ws, check=True, env={"PATH": "/usr/bin:/bin"})
    assert sorted(p.name for p in ws.iterdir()) == sorted(
        (*placement.DATA_FILES, "fit.py", "fit_output.txt"))


def test_a_body_swaps_only_the_body(tmp_path):
    body = tmp_path / "SKILL.md"
    body.write_text("---\nname: rietx\ndescription: x\n---\nshort\n", encoding="utf-8")
    stamp = B.build(TREE, tmp_path / "p", body=body, only=["no-case-matches"])
    assert (tmp_path / "p" / "skills" / "rietx" / "SKILL.md").read_bytes() == body.read_bytes()
    assert stamp["tree_sha256"] != B.tree_sha256(TREE) and stamp["cases"] == []
    for ref in (TREE / "references").iterdir():
        assert (tmp_path / "p" / "skills" / "rietx" / "references" / ref.name).read_bytes() \
            == ref.read_bytes()


def test_a_relative_interpreter_is_written_absolute(tmp_path, monkeypatch):
    """The run's workspace and the episode's cwd are not this one, so a
    relative `--python` would name nothing in either."""
    monkeypatch.chdir(tmp_path)
    stamp = B.build(TREE, tmp_path / "p", python=Path("venv/bin/python"), only=["none"])
    assert stamp["python"] == str(tmp_path / "venv" / "bin" / "python")


@POSIX_ONLY
def test_an_interpreter_either_arm_cannot_start_is_named(tmp_path):
    """macOS's sandbox denies `/Users` and `/tmp`, and grants the plugin root to
    the with-skill arm alone (2026-10-06: two void runs, then a void baseline
    arm), so only an interpreter outside all three serves both arms."""
    out = Path("/opt/build")
    assert B.unreachable(Path("/opt/rietx-eval/bin/python"), out) == []
    for denied in (out / "runtime" / "bin" / "python", Path("/Users/Shared/v/bin/python"),
                   Path("/private/tmp/v/bin/python"), Path.home() / "v" / "bin" / "python"):
        assert B.unreachable(denied, out), denied


@POSIX_ONLY
def test_a_base_interpreter_under_tmp_is_named(tmp_path):
    link = tmp_path / "python"
    link.symlink_to("/private/tmp/somewhere/python3.12")
    assert any("its base" in w for w in B.unreachable(link, Path("/opt/build")))


def test_venv_and_python_are_one_choice(tmp_path):
    with pytest.raises(SystemExit, match="pass one"):
        B.build(TREE, tmp_path / "p", python=Path("/opt/venv/bin/python"), venv=tmp_path / "v")


def test_venv_refuses_to_clear_a_directory_that_is_not_one(tmp_path):
    keep = tmp_path / "v"
    keep.mkdir()
    (keep / "notes.txt").write_text("not a venv", encoding="utf-8")
    with pytest.raises(SystemExit, match="left alone"):
        B._runtime(keep)
    assert (keep / "notes.txt").exists()


def test_venv_refuses_to_clear_the_running_venv():
    with pytest.raises(SystemExit, match="own venv"):
        B._runtime(Path(sys.prefix))


def test_a_build_that_fails_part_way_can_be_cleared(tmp_path, monkeypatch):
    def fail(venv):
        raise subprocess.CalledProcessError(1, "uv")

    monkeypatch.setattr(B, "_runtime", fail)
    out = tmp_path / "p"
    with pytest.raises(subprocess.CalledProcessError):
        B.build(TREE, out, venv=tmp_path / "v", only=["fap-fit"])
    B._clear(out)
    assert not out.exists()


def test_venv_writes_its_interpreter_into_every_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "_runtime", lambda venv: venv / "bin" / "python")
    out = tmp_path / "p"
    stamp = B.build(TREE, out, venv=tmp_path / "v", only=["fap-fit"])
    assert stamp["python"] == str(tmp_path / "v" / "bin" / "python")
    assert stamp["python"] in (out / "evals" / "fap-fit" / "prompt.md").read_text(encoding="utf-8")


def test_the_build_clears_only_its_own_output(tmp_path):
    keep = tmp_path / "mine"
    keep.mkdir()
    (keep / "notes.txt").write_text("not a build", encoding="utf-8")
    with pytest.raises(SystemExit, match="left alone"):
        B.build(TREE, keep, only=["none"])
    assert (keep / "notes.txt").exists()
    B.build(TREE, tmp_path / "p", only=["none"])
    B.build(TREE, tmp_path / "p", only=["none"])  # its own stamp: cleared and rebuilt


def test_the_suite_stays_out_of_the_wheel_and_the_sdist():
    cfg = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["build"]["targets"]
    assert cfg["wheel"]["packages"] == ["src/rietx"]
    assert "/tests" in cfg["sdist"]["exclude"]
    assert not any("eval_skill" in str(v) for v in cfg["wheel"].get("force-include", {}).values())


@pytest.mark.slow
def test_the_placement_episode_builds_and_fires_its_codes(tmp_path):
    """The real episode, fit and all: `build_episode` refuses an output missing
    a scored code, so this is also the guard that the episode still says what
    the rubric grades."""
    B.build(TREE, tmp_path / "p", only=["fap-judge"])
    files = tmp_path / "p" / "evals" / "fap-judge" / "files"
    out = (files / "fit_output.txt").read_text(encoding="utf-8")
    assert all(f" {c} " in out for c in placement.EPISODE_CODES)


# --- readout.py: the read-outs and the decision rule, on documents built here --

def _g(name: str, kind: str = "regex", weight: float = 1, **config) -> dict:
    return {"name": name, "type": kind, "weight": weight, "config": config}


def test_the_comparable_set_drops_what_a_two_arm_run_drops():
    graders = [_g("fired", "tool_used", tool="Skill"), _g("ref", target="trace", arm="with-only"),
               _g("quiet", "tool_used", tool="Skill", arm="both", min=0, max=0),
               _g("rubric", "llm", weight=2, focus="last_message"), _g("cell", weight=3)]
    assert [g["name"] for g in R.comparable(graders)] == ["quiet", "rubric", "cell"]
    assert R.tolerance(graders) == pytest.approx(1 / 6)
    alone = graders[:2]  # every grader excluded: the harness then scores them all
    assert R.comparable(alone) == alone
    run = {"graders": [{"name": n, "passed": p} for n, p in
                       (("fired", True), ("ref", True), ("quiet", False), ("rubric", True),
                        ("cell", False))]}
    assert R.run_score(run, graders) == pytest.approx(2 / 6)
    run["graders"].pop()  # a comparable grader the run does not report: unscored, not failed
    assert R.run_score(run, graders) is None


def test_the_comparable_score_is_the_harness_score_wherever_both_arms_ran():
    seen = 0
    for path in sorted(PILOT.glob("*.json")):
        doc = R.load(path)
        if doc["suite"]["ablation"] != "with-without":
            continue
        for case in doc["cases"]:
            for run in (r for runs in case["arms"].values() for r in runs):
                assert R.run_score(run, case["graders"]) == pytest.approx(run["score"]), path.name
                seen += 1
    assert seen == 12


def test_an_ablation_none_run_is_rescored_over_the_comparable_graders():
    """PROTOCOL.md § The score a comparison reads: the harness scored the
    with-only `skill_fired` here, because nothing is dropped under
    `--ablation none`; the comparison reads the two-arm score."""
    fit = next(c for c in R.load(PILOT / "compressed-sonnet-r2.json")["cases"]
               if c["name"] == "fap-fit")
    timed_out = fit["arms"]["with"][1]
    assert timed_out["error"] and timed_out["score"] == pytest.approx(2 / 8)
    assert R.run_score(timed_out, fit["graders"]) == pytest.approx(1 / 7)


def _trace(tmp_path: Path, rows: list[dict]) -> str:
    """Where the harness keeps one: ``<run>/out/trace.jsonl``."""
    path = tmp_path / "claude-eval-x" / "out" / "trace.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(path)


_BILL = {"input_tokens": 10, "cache_read_input_tokens": 100,
         "cache_creation_input_tokens": 1000, "output_tokens": 1}


def _use(ident: str, name: str, **args) -> dict:
    return {"type": "assistant", "message": {"id": f"msg-{ident}", "usage": _BILL, "content": [
        {"type": "tool_use", "id": ident, "name": name, "input": args}]}}


def _said(text: str) -> dict:
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "1", "content": [{"type": "text", "text": text}]}]}}


PLUGIN = "/srv/plug"


def _episode(ws: Path, base: str = f"{PLUGIN}/skills/rietx") -> list[dict]:
    return [
        {"type": "system", "subtype": "init", "cwd": str(ws)},
        _use("1", "Skill", skill="rietx-skill-eval:rietx"),
        _use("1", "Skill", skill="rietx-skill-eval:rietx"),  # one API call, two records
        _said(f"Base directory for this skill: {base}\n# rietx"),
        _use("2", "Read", file_path=f"{PLUGIN}/skills/rietx/references/diagnostics.md"),
        _use("3", "Bash", command=f"/opt/venv/bin/python {ws}/fit.py > {ws}/out.txt 2>/dev/null"),
        _use("4", "Read", file_path=f"{PLUGIN}/evals/fap-fit/graders/cell_a.md"),
        _use("5", "Read", file_path="/home/u/rietx/docs/skill/rietx/SKILL.md"),
        _use("6", "Bash", command="/opt/venv/bin/python -c "
             "'import rietx.skill as s; print(s.skill_path())'"),
    ]


@POSIX_ONLY
def test_a_trace_gives_tokens_the_route_and_its_leaks(tmp_path):
    ws = tmp_path / "claude-eval-x" / "work"
    path = _trace(tmp_path, _episode(ws))
    facts = R.trace_facts(path, arm="with", plugin=PLUGIN, python="/opt/venv/bin/python")
    assert facts["trace"] == "read"
    assert facts["tokens"] == 6 * 1111 and facts["output_tokens"] == 6  # once per message.id
    assert facts["fired"] and facts["opened"] == ["diagnostics.md"]
    assert facts["skill_dir"] == f"{PLUGIN}/skills/rietx" and facts["held"] is True
    # The loaded skill, the workspace, the interpreter and /dev are not leaks;
    # the answer key, the checkout's copy and the package's route to one are.
    assert facts["leaks"] == [f"Read: {PLUGIN}/evals/fap-fit/graders/cell_a.md",
                              "Read: /home/u/rietx/docs/skill/rietx/SKILL.md",
                              "Bash: rietx.skill", "Bash: skill_path"]

    without = R.trace_facts(path, arm="without", plugin=PLUGIN, python="/opt/venv/bin/python")
    assert without["held"] is False  # a skill fired with no plugin loaded
    assert f"Read: {PLUGIN}/skills/rietx/references/diagnostics.md" in without["leaks"]

    elsewhere = _trace(tmp_path / "b", _episode(ws, base="/root/.claude/skills/rietx"))
    assert R.trace_facts(elsewhere, arm="with", plugin=PLUGIN)["held"] is False

    # Another skill loading first neither fires rietx nor voids the run.
    other = [_use("0", "Skill", skill="dataviz"),
             _said("Base directory for this skill: /opt/cc/skills/dataviz"), *_episode(ws)]
    first = R.trace_facts(_trace(tmp_path / "d", other), arm="with", plugin=PLUGIN)
    assert first["skill_dir"] == f"{PLUGIN}/skills/rietx" and first["held"] is True
    assert not R.trace_facts(_trace(tmp_path / "e", other[:2]), arm="without")["fired"]


def test_a_trace_that_cannot_be_read_says_so_rather_than_zero(tmp_path):
    assert R.trace_facts(None, arm="with")["trace"] == "missing"
    gone = R.trace_facts(str(tmp_path / "gone.jsonl"), arm="with")
    assert gone["tokens"] is gone["leaks"] is gone["opened"] is None
    unread = R.trace_facts(_trace(tmp_path, [{"type": "system", "cwd": "/w"}]), arm="with")
    assert unread["trace"] == "unread" and unread["tokens"] is None
    # A bare message is lifted into the transcript shape, one API call a row.
    bare = [{"role": "assistant", "usage": _BILL, "content": [
        {"type": "tool_use", "id": "1", "name": "Skill", "input": {"skill": "rietx"}}]}] * 2
    lifted = R.trace_facts(_trace(tmp_path / "c", bare), arm="with")
    assert lifted["trace"] == "read" and lifted["tokens"] == 2 * 1111 and lifted["fired"]


def _doc(model: str, cases: dict, *, ablation: str = "with-without", root=None,
         partial: bool = False) -> dict:
    """A result document in the harness's shape. ``cases`` maps a name to
    (graders, the with arm's runs, the without arm's runs or `None`), a run
    being the pass/fail of each grader in order."""
    out = []
    for name, (graders, with_runs, without_runs) in cases.items():
        arms = {arm: [{"score": None, "costUsd": 0.1, "judgeCostUsd": 0.02, "durationSeconds": 30,
                       "turns": 4, "error": None, "tracePath": None, "skippedPaidGraders": False,
                       "graders": [{"name": g["name"], "passed": p}
                                   for g, p in zip(graders, passes)]} for passes in runs]
                for arm, runs in (("with", with_runs), ("without", without_runs)) if runs}
        out.append({"name": name, "graders": graders, "arms": arms})
    return {"claudeVersion": "2.1.289", "partial": partial, "partialReason": None,
            "costUsd": 1.0, "durationSeconds": 60, "cases": out,
            "suite": {"modelOverride": model, "judgeModel": "sonnet", "ablation": ablation,
                      "threshold": 1, "concurrency": 1, "root": root}}


GRADERS = [_g("a"), _g("b", weight=2), _g("c")]  # t = 1/4
ALL, NONE = [True] * 3, [False] * 3


def _current(**kw) -> dict:
    return _doc("haiku", {"x": (GRADERS, [ALL] * 3, [NONE] * 3)}, **kw)


def _pair(runs, *, model="haiku", graders=GRADERS, partial=False) -> dict:
    candidate = _doc(model, {"x": (graders, runs, None)}, ablation="none", partial=partial)
    return R.compare(R.summarise(_current()), R.summarise(candidate))


def test_compare_holds_within_one_graders_worth_and_fails_past_it():
    exact = _pair([[False, True, True]] * 3)  # the weight-1 grader lost in every run: Δ = -t
    assert exact["verdict"] == "holds"
    assert exact["rows"][0]["delta"] == pytest.approx(-1 / 4)
    assert exact["rows"][0]["vs_none"] == pytest.approx(3 / 4)  # against today's without arm
    assert exact["rows"][0]["tokens"] == (None, None)  # no trace kept: unknown, not zero
    past = _pair([ALL, [True, False, True], [True, False, True]])  # weight 2, twice: Δ = -1/3
    assert past["verdict"] == "fails" and past["rows"][0]["loses"]


def test_compare_decides_nothing_it_cannot_pair():
    short = _pair([[True, False, True]] * 2)  # a loss, but at N = 2
    assert short["verdict"] == "undecided" and short["rows"][0]["why"] == ["candidate N = 2 of 3"]
    assert _pair([ALL] * 3, model="sonnet")["verdict"] == "undecided"
    assert _pair([ALL] * 3, partial=True)["verdict"] == "undecided"
    differ = _pair([[True, True]] * 3, graders=GRADERS[:2])
    assert differ["verdict"] == "undecided" and "graders differ" in differ["rows"][0]["why"]
    # A loss across two models is no loss the rule can read.
    lost = [[True, False, False]] * 3
    assert _pair(lost)["verdict"] == "fails"
    assert _pair(lost, model="sonnet")["verdict"] == "undecided"
    assert _pair(lost, partial=True)["verdict"] == "undecided"
    # A case reported with no graders is unscored, not a crash.
    assert R.run_score({"graders": []}, []) is None


def test_compare_drops_a_void_run_and_suspects_the_judge_where_the_skill_fired():
    current = R.summarise(_current())
    candidate = R.summarise(_doc("haiku", {"x": (GRADERS, [[True, True, False]] * 3, None)},
                                 ablation="none"))
    for run in candidate["cases"][0]["arms"]["with"]:
        run["fired"] = True
    out = R.compare(current, candidate)
    assert out["verdict"] == "holds" and out["rows"][0]["suspect_judge"]
    candidate["cases"][0]["arms"]["with"][0]["held"] = False
    assert R.compare(current, candidate)["verdict"] == "undecided"


def test_tier0_reads_a_fire_rate_and_a_quiet_rate():
    fire = [_g("fired", "tool_used", tool="Skill", arm="both")]
    quiet = [_g("fired", "tool_used", tool="Skill", arm="both", min=0, max=0)]
    doc = _doc("haiku", {"f": (fire, [[True], [True], [False]], None),
                         "q": (quiet, [[True]] * 3, None)}, ablation="none")
    assert R.tier0_rates(R.summarise(doc)) == {"fire": (2, 3), "quiet": (3, 3)}


def test_the_cli_shows_a_round_beside_its_build_and_exits_on_the_rule(tmp_path, capsys):
    (tmp_path / B.STAMP).write_text(json.dumps(
        {"skill_sha256": "a" * 64, "tree_sha256": "b" * 64, "python": "/opt/venv/bin/python"}), encoding="utf-8")
    cur, cand = tmp_path / "cur.json", tmp_path / "cand.json"
    current = _current(root=str(tmp_path))
    current["cases"][0]["arms"]["with"][0]["score"] = 0.5  # a harness that disagrees
    cur.write_text(json.dumps(current), encoding="utf-8")
    cand.write_text(json.dumps(_doc("haiku", {"x": (GRADERS, [[True, False, False]] * 3, None)},
                                    ablation="none", root=str(tmp_path))), encoding="utf-8")
    assert R.main(["show", str(cur)]) == 0
    shown = capsys.readouterr().out
    assert f"build: SKILL.md {'a' * 12}, tree {'b' * 12}" in shown
    assert "TRACE x with run 1: missing" in shown  # reported, never dropped
    assert "SCORE x with run 1: comparable 1.000 against the harness's 0.500" in shown
    assert "SCORE x with run 2" not in shown
    assert R.main(["compare", str(cur), str(cand)]) == 1
    decided = capsys.readouterr().out
    assert "rule: fails (x)" in decided and "note: A/A: both rounds ran one tree" in decided
    assert f"note: both rounds name one plugin directory, {tmp_path}" in decided
    with pytest.raises(SystemExit):
        R.main(["compare", str(cur)])


# --- the floors and the model watch (WP-1907) --------------------------------

_FIRE = [_g("fired", "tool_used", tool="Skill", arm="both")]
_QUIET = [_g("fired", "tool_used", tool="Skill", arm="both", min=0, max=0)]


def _tier0_round() -> dict:
    return R.summarise(_doc("haiku", {"f": (_FIRE, [[True], [True], [False]], None),
                                      "q": (_QUIET, [[True]] * 3, None)}, ablation="none"))


def test_floors_fail_only_a_case_below_its_floor():
    round_ = _tier0_round()
    lines, below = R.check_floors(round_, {"haiku": {"f": 2, "q": 3}})
    assert below == [] and lines[0] == "model haiku, tier 0: fire rate 2/3, quiet rate 3/3"
    lines, below = R.check_floors(round_, {"haiku": {"f": 3, "gone": 1}})
    assert below == ["f"]
    assert "gone: has a floor and is not in this round" in lines  # said, never failed
    assert lines[-1] == "floors: 1 below (f)"
    # Another model's floors are not this round's.
    lines, below = R.check_floors(round_, {"sonnet": {"f": 3}})
    assert below == [] and any(line.startswith("no floors recorded for haiku yet") for line in lines)


def test_an_errored_run_counts_against_no_floor():
    round_ = _tier0_round()
    round_["cases"][0]["arms"]["with"][2]["passed"] = None   # f: pass, pass, errored
    lines, below = R.check_floors(round_, {"haiku": {"f": 3}})
    assert below == [] and any("2/3 passed, 1 errored, floor 3" in line for line in lines)
    round_["cases"][0]["arms"]["with"][1]["passed"] = False  # f: pass, fail, errored
    assert R.check_floors(round_, {"haiku": {"f": 3}})[1] == ["f"]


def test_the_floors_cli_exits_on_a_case_below_and_starts_with_none_recorded(tmp_path, capsys):
    assert R.load(R.FLOORS) == {}  # PROTOCOL.md § Floors: the first real run records them
    result, floors = tmp_path / "r.json", tmp_path / "floors.json"
    result.write_text(json.dumps(_doc("haiku", {"f": (_FIRE, [[True], [False], [False]], None)},
                                      ablation="none")), encoding="utf-8")
    assert R.main(["floors", str(result)]) == 0
    assert "no floors recorded for haiku yet" in capsys.readouterr().out
    floors.write_text(json.dumps({"haiku": {"f": 2}}), encoding="utf-8")
    assert R.main(["floors", str(result), "--floors", str(floors)]) == 1
    assert "f                          1/3 passed, floor 2  BELOW" in capsys.readouterr().out


_PAGE = """<a href="/claude-haiku-4-5-system-card">card</a>
<code>claude-haiku-4-5-20251001</code> <code>anthropic.claude-haiku-4-5-20251001-v1:0</code>
<code>claude-haiku-4-5@20251001</code> <code>claude-sonnet-5-5</code> <code>claude-opus-5-5</code>"""


def test_the_model_watch_reads_haiku_and_sonnet_ids_without_their_noise():
    from tests.eval_skill import model_watch as W

    found = W.model_ids(_PAGE)
    assert found == {"claude-haiku-4-5", "claude-haiku-4-5-20251001", "claude-sonnet-5-5"}
    assert W.new_ids(found, W.seen_ids("# note\nclaude-haiku-4-5\n\nclaude-sonnet-5-5  # x\n")) == [
        "claude-haiku-4-5-20251001"]
    seen = W.seen_ids(W.SEEN.read_text(encoding="utf-8"))
    assert seen and all(W.model_ids(s) == {s} for s in seen), "the seeded list reads as IDs"


def test_the_model_watch_fails_on_a_page_with_no_id_and_reports_new_ones(tmp_path, monkeypatch, capsys):
    from tests.eval_skill import model_watch as W

    out = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert W.main(page="<html>moved</html>") == 1  # a dead watch is red, never quiet
    assert not out.exists()
    assert W.main(page=_PAGE + " claude-sonnet-9") == 0
    assert out.read_text(encoding="utf-8") == "new=claude-sonnet-9\n"
    assert "new: claude-sonnet-9" in capsys.readouterr().out
