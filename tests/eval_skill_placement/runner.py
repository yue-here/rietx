"""Build, launch and score the skill-placement round (WP-1338).

    python tests/eval_skill_placement/runner.py build   <root>
    python tests/eval_skill_placement/runner.py prepare <root> <cell>
    python tests/eval_skill_placement/runner.py launch  <root> <cell>
    python tests/eval_skill_placement/runner.py score   <root>
    python tests/eval_skill_placement/runner.py grade   <root>

A **cell** is `<condition>-<model>-<rep>`, e.g. `grep-haiku-2`.  PROTOCOL.md is
the registration: what is asked, what differs between the two conditions, what
is read out and the rule the read-outs are held to.  This module is its
instrument, and `test_placement.py` holds the texts the two share equal.

**The condition is the skill body, and it is installed everywhere the agent can
find one.**  `build` makes one venv per condition from a *wheel* of this tree,
not an editable install, so the package's own copy of the skill sits in
site-packages rather than pointing back at a checkout; under `grep` that copy
is rewritten before `rietx skill --install` copies it into the workspace.  The
maintainer's checkout is still on the machine, so `score` reports every tool
call naming a path inside one (the `leak` column) rather than assuming none.

**Reach is read off what came back, never off what was asked.**  A row is
reached when a tool result holds its table marker, ``| `CODE` |``: a whole-file
Read, a Grep hit and a `sed` of the right lines all return it, and a Read that
stopped short of the row does not.  The marker appears in no other file the
workspace holds, since `fit_output.txt` names each code bare.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
REPO = HARNESS.parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tests.eval_agent_surface import trail  # noqa: E402
from tests.eval_agent_surface.runner import check_no_inherited_context  # noqa: E402

CONDITIONS = ("rows", "grep")
MODELS = {"haiku": "haiku", "sonnet": "sonnet", "opus": "opus"}
REPS = 3
#: A runaway guard, never a price: the round's pilot runs cost well under it.
BUDGET_USD = 6.0

DATA_FILES = ("FAP.XRA", "fluorapatite.cif")

#: Every code `fit_output.txt` prints, each with its row in
#: `references/diagnostics.md`.  `build` refuses an output missing one.
SCORED_CODES = (
    "FLAT_DIRECTION",
    "HIGH_CORRELATION",
    "BACKGROUND_ABSORPTION",
    "RESOLUTION_UNCONSTRAINED",
    "PATTERN_UNDERSAMPLED",
    "SITE_SNAPPED_TO_SPECIAL_POSITION",
)
#: Scored codes a build from today's tree no longer fires, each with why
#: (PROTOCOL.md § Amendment, 2026-10-24).  Round 1.1 scored them, and a re-run
#: of it builds from its own checkout, where they fire.
RETIRED_CODES = {
    "SITE_SNAPPED_TO_SPECIAL_POSITION": (
        "WP-2037: a site off its special position by no more than the CIF's own "
        "printed rounding is snapped without a warning"),
}
#: What `build_episode` requires `fit_output.txt` to fire.
EPISODE_CODES = tuple(c for c in SCORED_CODES if c not in RETIRED_CODES)

#: The routing rows the `grep` body drops: the two keyed by something the agent
#: already holds when it needs the row, a code or a field.
REMOVED_ROWS = (
    "| a `Diagnostic` fired and you need its row",
    "| §6 — something declined to answer",
)
#: What replaces them, inserted as its own paragraph above the routing table.
GREP_SENTENCE = (
    "**A name in front of you is its own index.** A `Diagnostic` code, a "
    "field or a verb has its row in one of these files, and `grep -rn NAME "
    "references/` finds it wherever it lives. A code's row says what it "
    "means, what to do and what you must not do."
)
TABLE_HEAD = "| When | Load | Manual page |"

# The prompt names no module, document, code or skill; the condition is the
# workspace.  PROTOCOL.md quotes both texts and `test_placement.py` holds them
# equal.
PROMPT = (
    "My colleague refined our fluorapatite pattern with `fit.py` and sent me "
    "what it printed, `fit_output.txt`. Which of the refined numbers can go in "
    "the paper as they stand, and what should they change before the next run?"
)
PREAMBLE = (
    "The python interpreter to use is {python}. "
    "The files are in {workspace}, which is your working directory."
)

#: The four rubric items, graded blind to condition (PROTOCOL.md § R3).
RUBRIC = {
    "zero_displacement": (
        "Does the answer say that instrument.zero_shift and "
        "instrument.geometry.sample_displacement are not measured by this fit "
        "(they cannot both be quoted, or neither can), and that one must be "
        "fixed at an independently known value, calibrated on a standard, or "
        "otherwise separated before either is reported?"),
    "cell_accuracy": (
        "Does the answer say the cell parameters a and c are compromised or "
        "not quotable as accurate/absolute values while zero shift and sample "
        "displacement are refined together (their correlation with the cell is "
        "0.99+), or that the cell needs the zero/displacement problem fixed "
        "first?"),
    "biso_background": (
        "Does the answer say that the displacement parameters (Biso), at least "
        "the one the background screen flagged, are not quotable because the "
        "24-term background can absorb them, and that the background should be "
        "made stiffer (fewer terms, or another stiffer model) before quoting "
        "them?"),
    "undersampled": (
        "Does the answer treat the undersampling (fewer than 5 steps per FWHM) "
        "as a data-collection limit, to be fixed by re-measuring with a finer "
        "step, rather than as something a refinement choice can fix?"),
}


def split(cell: str) -> tuple[str, str, int]:
    m = re.fullmatch(r"(rows|grep)-(haiku|sonnet|opus)-(\d+)", cell)
    if not m:
        raise SystemExit(f"unknown cell {cell!r}: <rows|grep>-<haiku|sonnet|opus>-<n>")
    return m.group(1), m.group(2), int(m.group(3))


def cells() -> list[str]:
    return [f"{c}-{m}-{r}" for m in MODELS for c in CONDITIONS
            for r in range(1, REPS + 1)]


def _run(*args: str, **kw) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        raise SystemExit(f"{args[0]} failed: {proc.stderr.strip()[:2000]}")
    return proc


def grep_body(body: str) -> str:
    """Today's body with `REMOVED_ROWS` dropped and `GREP_SENTENCE` above the
    table.  Refuses a body that no longer carries a row it is told to drop, so
    the condition cannot silently become "today's body plus a sentence"."""
    lines = body.split("\n")
    for prefix in REMOVED_ROWS:
        hits = [ln for ln in lines if ln.startswith(prefix)]
        if len(hits) != 1:
            raise SystemExit(f"expected one routing row starting {prefix!r}, "
                             f"found {len(hits)}")
    kept = [ln for ln in lines if not ln.startswith(REMOVED_ROWS)]
    at = kept.index(TABLE_HEAD)
    return "\n".join(kept[:at] + [GREP_SENTENCE, ""] + kept[at:])


def venv_python(root: Path, condition: str) -> Path:
    return root / "venvs" / condition / "bin" / "python"


def build(root: Path) -> None:
    check_no_inherited_context(root / "cells" / "x")
    for condition in CONDITIONS:
        venv = root / "venvs" / condition
        if venv.exists():  # built by an earlier call; the grep rewrite ran there
            continue
        _run("uv", "venv", "-q", "--python", "3.12", str(venv))
        python = venv / "bin" / "python"
        # A wheel, not `-e`: an editable install's skill_path() is the checkout.
        _run("uv", "pip", "install", "-q", "--python", str(python), f"{REPO}[viz]")
        where = Path(_run(str(python), "-c",
                          "import rietx.skill as s; print(s.skill_path())").stdout.strip())
        if "site-packages" not in str(where):
            raise SystemExit(f"{condition}: the skill resolves to {where}, not the wheel's copy")
        if condition == "grep":
            skill = where / "SKILL.md"
            skill.write_text(grep_body(skill.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"{condition}: {python}, skill at {where}")

    episode = root / "episode"
    if (episode / "fit_output.txt").exists():  # every cell copies this one output
        print(f"episode already built at {episode}")
        return
    print(build_episode(episode, venv_python(root, "rows")))


def build_episode(episode: Path, python: Path) -> str:
    """The episode every cell is handed, written into ``episode``: the two data
    files, the colleague's script as `fit.py`, and what it printed under
    ``python`` as `fit_output.txt`.  Refuses an output missing one of
    `EPISODE_CODES`.  WP-1905's skill eval stages its `fap-judge` case through
    this too."""
    episode.mkdir(parents=True, exist_ok=True)
    for name in DATA_FILES:
        shutil.copyfile(REPO / "tests" / "data" / name, episode / name)
    shutil.copyfile(HARNESS / "colleague_fit.py", episode / "fit.py")
    out = _run(str(python), "fit.py", cwd=episode,
               env={**os.environ, "RIETX_TELEMETRY": "0"}).stdout
    missing = [c for c in EPISODE_CODES if f" {c} " not in out]
    if missing:
        raise SystemExit(f"fit_output.txt does not fire {missing}:\n{out}")
    (episode / "fit_output.txt").write_text(out, encoding="utf-8")
    return out


def workspace(root: Path, cell: str) -> Path:
    return root / "cells" / cell


def prepare(root: Path, cell: str) -> None:
    condition, _, _ = split(cell)
    ws = workspace(root, cell)
    if ws.exists():
        raise SystemExit(f"{ws} exists — a cell is prepared once")
    ws.mkdir(parents=True)
    for name in (*DATA_FILES, "fit.py", "fit_output.txt"):
        shutil.copyfile(root / "episode" / name, ws / name)
    rietx_cli = venv_python(root, condition).parent / "rietx"
    _run(str(rietx_cli), "skill", "--install", str(ws), "--copy")
    for copy in (ws / ".claude" / "skills" / "rietx" / "SKILL.md",
                 ws / ".agents" / "skills" / "rietx" / "SKILL.md"):
        has = GREP_SENTENCE in copy.read_text(encoding="utf-8")
        if has != (condition == "grep"):
            raise SystemExit(f"{copy}: the installed body is not the {condition} body")


def launch(root: Path, cell: str) -> None:
    condition, model, _ = split(cell)
    ws = workspace(root, cell)
    record_path = root / "runs" / f"{cell}.json"
    if record_path.exists():
        raise SystemExit(f"{cell} has run")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    session = str(uuid.uuid4())
    prompt = PROMPT + "\n\n" + PREAMBLE.format(
        python=venv_python(root, condition), workspace=ws)
    # `project,local` leaves the user's own settings, CLAUDE.md and skills out
    # (PROTOCOL.md § Amendment 1.1): a user-level `rietx` skill shadows the
    # workspace's, and on the registration machine it points at a checkout.
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", MODELS[model],
         "--session-id", session, "--permission-mode", "bypassPermissions",
         "--setting-sources", "project,local",
         "--output-format", "json", "--max-budget-usd", str(BUDGET_USD)],
        cwd=ws, capture_output=True, text=True)
    record = {"cell": cell, "session_id": session, "returncode": proc.returncode,
              "stderr": proc.stderr[-4000:]}
    try:
        record["result"] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        record["stdout"] = proc.stdout[-8000:]
    record_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"{cell}: rc={proc.returncode} session={session}")


def transcript_for(session: str) -> Path | None:
    hits = sorted((Path.home() / ".claude" / "projects").glob(f"*/{session}.jsonl"))
    return hits[0] if hits else None


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text(b.get("text") or b.get("content") or "")
                         if isinstance(b, dict) else str(b) for b in content)
    return ""


def read_out(rows: list[dict]) -> dict:
    """R0-R2 and the leak check from one transcript (PROTOCOL.md § Read-outs)."""
    uses: dict[str, dict] = {}
    reached: dict[str, str] = {}
    skill_loaded = False
    leaks: list[str] = []
    opened: set[str] = set()
    for row in rows:
        content = (row.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                uses[block.get("id", "")] = block
                args = json.dumps(block.get("input") or {})
                if block.get("name") == "Skill" and "rietx" in args:
                    skill_loaded = True
                if "SKILL.md" in args:
                    skill_loaded = True
                if "/Code/rietx" in args:
                    leaks.append(args[:160])
                opened.update(re.findall(r"references/([a-z0-9-]+\.md)", args))
            elif block.get("type") == "tool_result":
                text = _text(block.get("content"))
                use = uses.get(block.get("tool_use_id", ""), {})
                for code in SCORED_CODES:
                    if code not in reached and f"| `{code}` |" in text:
                        reached[code] = use.get("name", "?")
    # Which body the Skill tool actually delivered: the harness names the
    # directory it loaded from, and only the grep body carries the sentence.
    everything = "\n".join(_text((r.get("message") or {}).get("content"))
                           for r in rows)
    base = re.search(r"Base directory for this skill: (\S+)", everything)
    return {"skill_loaded": skill_loaded, "reached": reached,
            "opened": sorted(opened), "leaks": leaks,
            "skill_dir": base.group(1) if base else None,
            "grep_body": GREP_SENTENCE[:40] in everything}


def condition_held(cell: str, out: dict, ws: Path) -> bool | None:
    """Whether the body the agent was handed is its cell's: ``None`` where no
    body was loaded, so there is nothing to hold (R0)."""
    if out["skill_dir"] is None:
        return None
    condition, _, _ = split(cell)
    # A path test, not a string prefix: `cells/grep-haiku-1` prefixes
    # `cells/grep-haiku-10`.
    return (Path(out["skill_dir"]).is_relative_to(ws)
            and out["grep_body"] == (condition == "grep"))


def score(root: Path) -> None:
    table = []
    for path in sorted((root / "runs").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        result = record.get("result") or {}
        transcript = transcript_for(record["session_id"])
        rows = trail.load(transcript) if transcript else []
        out = read_out(rows)
        bill = trail.usage(rows)
        table.append({
            "cell": record["cell"], **out,
            "condition_held": condition_held(record["cell"], out,
                                             workspace(root, record["cell"])),
            "answer": result.get("result", ""),
            "cost": result.get("total_cost_usd"), "turns": result.get("num_turns"),
            "minutes": round((result.get("duration_ms") or 0) / 60000, 2),
            "api_calls": bill.api_calls, "output_tokens": bill.output_tokens,
            "subtype": result.get("subtype"), "transcript": str(transcript),
        })
    (root / "scores.json").write_text(json.dumps(table, indent=1), encoding="utf-8")
    grades = _load_grades(root)
    print(f"{'cell':16s} held  reach  how                         $     turns  R3")
    for t in table:
        how = ",".join(sorted(set(t["reached"].values())))
        g = grades.get(t["cell"])
        r3 = "-" if g is None else str(sum(g.values()))
        held = {True: "y", False: "VOID", None: "-"}[t["condition_held"]]
        print(f"{t['cell']:16s} {held:5s} "
              f"{len(t['reached'])}/{len(SCORED_CODES)}   {how:26s} "
              f"{(t['cost'] or 0):5.2f} {t['turns'] or 0:6d}  {r3}"
              + ("  LEAK" if t["leaks"] else ""))


GRADER = (
    "You are grading one answer to this question, which a user asked about a "
    "Rietveld refinement of fluorapatite whose output they were sent:\n\n"
    "> " + PROMPT + "\n\nFor each rubric item, answer 1 if the answer clearly "
    "does what the item asks and 0 otherwise. Judge only what the answer says, "
    "not whether it is well written. Reply with a JSON object and nothing else, "
    "keys exactly: {keys}.\n\nRubric:\n{rubric}\n\nThe answer:\n\n<answer>\n"
    "{answer}\n</answer>"
)


def _load_grades(root: Path) -> dict[str, dict]:
    path = root / "grades.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def grade(root: Path) -> None:
    """R3, blind: the grader sees one answer and the rubric, never the cell."""
    table = json.loads((root / "scores.json").read_text(encoding="utf-8"))
    grades = _load_grades(root)
    judge = root / "judge"
    judge.mkdir(exist_ok=True)
    order = [t for t in table if t["cell"] not in grades and t["answer"]]
    random.Random(1338).shuffle(order)
    rubric = "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    for t in order:
        prompt = GRADER.format(keys=", ".join(RUBRIC), rubric=rubric,
                               answer=t["answer"])
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "json",
             "--max-budget-usd", "1"], cwd=judge, capture_output=True, text=True)
        # A grader call that failed, or replied without every key, is no
        # verdict: recorded as zeros it would never be retried.
        try:
            text = json.loads(proc.stdout).get("result", "")
            found = re.search(r"\{.*\}", text, re.S)
            verdict = json.loads(found.group(0)) if found else {}
        except json.JSONDecodeError:
            verdict = {}
        if proc.returncode != 0 or set(RUBRIC) - set(verdict):
            print(f"{t['cell']}: no usable verdict (rc={proc.returncode}); "
                  "left ungraded for the next call", file=sys.stderr)
            continue
        grades[t["cell"]] = {k: int(verdict[k]) for k in RUBRIC}
        (root / "grades.json").write_text(json.dumps(grades, indent=1), encoding="utf-8")
        print(t["cell"], grades[t["cell"]])


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    verb, root = argv[1], Path(argv[2]).resolve()
    if verb == "build":
        build(root)
    elif verb == "prepare":
        prepare(root, argv[3])
    elif verb == "launch":
        launch(root, argv[3])
    elif verb == "score":
        score(root)
    elif verb == "grade":
        grade(root)
    else:
        raise SystemExit(f"unknown verb {verb!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
