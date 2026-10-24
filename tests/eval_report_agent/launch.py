"""Launch python-arm cells as headless Claude Code sessions (PROTOCOL.md 2.3).

The 2.x rounds ran each cell as a Workflow ``agent()`` call.  Such an agent
inherits the launching session's user-level skills, and a user-level
``rietx`` skill shadows the workspace's copy (tests/CLAUDE.md § Four eval
protocols), so 2.3 launches each cell as ``claude -p`` with
``--setting-sources project,local``, the route
``tests/eval_skill_placement/runner.py`` takes.  Two rules beyond that
runner's:

- **The environment is rebuilt, never inherited.**  A child of a running
  session inherits ``OLDPWD`` (the launching checkout), that session's
  messaging socket and its ``CLAUDE_EFFORT``, so the cell gets ``HOME``,
  ``USER``, ``LOGNAME``, ``SHELL``, ``LANG`` and ``PATH`` only, and a
  ``PATH`` entry inside the repo is refused rather than passed on.
- **The stream is the record.**  ``--output-format stream-json`` keeps the
  ``system/init`` event, which lists the model, skills and tools the cell
  was given: the evidence that its condition reached it.  The closing
  ``result`` event carries the tokens and the cost.

The session's own transcript is kept whole as ``launches/<eid>/session.jsonl``
and, without the rows that repeat each message as sent (``WIRE_ROW``), as
``transcripts/agent-<eid>.jsonl``, the layout ``mine_transcripts`` reads.
The record directory must not sit above any workspace, or a cell still
running could read a finished cell's transcript.

Usage::

    python -m tests.eval_report_agent.launch --record REC --model sonnet \\
        WS/RUNS/python__sonnet/N1 WS/RUNS/python__sonnet/C1
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from tests.eval_report_agent.mine_transcripts import cell_of
from tests.eval_report_agent.python_arm import _inside_repo

#: identical in every cell but for the path, which names the cell
#: (``RUNS/<condition>__<model>/<eid>``, ``mine_transcripts.cell_of``)
RUNNER = ("Your working directory is {workspace}. Read prompt.md there and "
          "carry out the episode it describes. Work only inside that "
          "directory: read nothing outside it.")

#: a runaway guard, never a price
BUDGET_USD = 15.0

KEPT_ENV = ("HOME", "USER", "LOGNAME", "SHELL", "LANG", "PATH")


def clean_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """The cell's environment: ``KEPT_ENV`` from ``environ``, nothing else."""
    environ = dict(os.environ if environ is None else environ)
    env = {k: environ[k] for k in KEPT_ENV if k in environ}
    for entry in env.get("PATH", "").split(os.pathsep):
        if entry and _inside_repo(Path(entry)):
            raise ValueError(f"PATH entry {entry} is inside the repo tree")
    env.setdefault("LANG", "en_US.UTF-8")
    return env


def command(workspace: Path, *, model: str, effort: str,
            session: str) -> list[str]:
    return ["claude", "-p", RUNNER.format(workspace=workspace),
            "--model", model, "--effort", effort, "--session-id", session,
            "--permission-mode", "bypassPermissions",
            "--setting-sources", "project,local",
            "--output-format", "stream-json", "--verbose",
            "--max-budget-usd", str(BUDGET_USD)]


def _check(workspace: Path, record: Path) -> str:
    named = cell_of(RUNNER.format(workspace=workspace))
    if named is None:
        raise ValueError(f"{workspace} names no RUNS/<condition>__<model>/<eid>")
    if not (workspace / "prompt.md").is_file():
        raise ValueError(f"{workspace} holds no prompt.md")
    if _inside_repo(workspace) or _inside_repo(record):
        raise ValueError("workspace and record must sit outside the repo tree")
    if workspace.resolve().is_relative_to(record.resolve()):
        raise ValueError(f"record {record} sits above workspace {workspace}")
    return named[2]


def transcript_for(session: str) -> Path | None:
    hits = sorted((Path.home() / ".claude" / "projects").glob(
        f"*/{session}.jsonl"))
    return hits[0] if hits else None


#: a session-transcript row repeating an assistant message as it was sent on
#: the wire (Claude Code 2.1.310): mined, it counts every tool call twice
WIRE_ROW = "api-request-blob"


def minable(raw: str) -> str:
    """The session transcript without its ``WIRE_ROW`` rows."""
    kept = [line for line in raw.splitlines()
            if line.strip() and json.loads(line).get("type") != WIRE_ROW]
    return "\n".join(kept) + "\n"


def launch(workspaces: list[Path], record: Path, *, model: str,
           effort: str) -> list[dict]:
    """Run every cell at once, wait for all, and record each.

    A cell's time is its ``result`` events' ``duration_ms``, never the
    launcher's clock, which reads a cell only once every earlier cell in the
    list has been collected (2.3, recorded post-hoc).  A session can carry
    more than one ``result``: it wakes when a background task it started
    ends after its answer.
    """
    eids = [_check(ws, record) for ws in workspaces]
    env = clean_env()
    running = []
    for ws, eid in zip(workspaces, eids):
        out = record / "launches" / eid
        if out.exists():
            raise ValueError(f"{out} exists: a cell is launched once")
        out.mkdir(parents=True)
        session = str(uuid.uuid4())
        cmd = command(ws, model=model, effort=effort, session=session)
        proc = subprocess.Popen(
            cmd, cwd=ws, env=env, stdin=subprocess.DEVNULL,
            stdout=open(out / "stream.jsonl", "w", encoding="utf-8"),
            stderr=open(out / "stderr.txt", "w", encoding="utf-8"))
        running.append((ws, eid, out, session, cmd, proc))
    rows = []
    for ws, eid, out, session, cmd, proc in running:
        returncode = proc.wait()
        row = {"episode": eid, "workspace": str(ws), "session_id": session,
               "command": cmd, "returncode": returncode}
        transcript = transcript_for(session)
        if transcript is not None:
            shutil.copyfile(transcript, out / "session.jsonl")
            dest = record / "transcripts" / f"agent-{eid}.jsonl"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(minable(transcript.read_text(encoding="utf-8")),
                            encoding="utf-8")
            dest.with_suffix(".meta.json").write_text(
                json.dumps({"model": model, "effort": effort,
                            "session_id": session}) + "\n", encoding="utf-8")
        row["transcript"] = str(transcript)
        (out / "launch.json").write_text(json.dumps(row, indent=1) + "\n",
                                         encoding="utf-8")
        rows.append(row)
        print(f"{eid}: rc={returncode} session={session}")
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspaces", nargs="+", type=Path)
    parser.add_argument("--record", type=Path, required=True,
                        help="where each cell's stream and transcript go "
                             "(outside the repo, above no workspace)")
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", default="medium")
    args = parser.parse_args(argv)
    launch(args.workspaces, args.record, model=args.model, effort=args.effort)


if __name__ == "__main__":
    main()

