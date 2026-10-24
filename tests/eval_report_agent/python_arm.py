"""Workspace builder for the python-capable arm (PROTOCOL.md 2.0, WP-1064).

The arm answers report-vs-tools-vs-package empirically: the agent gets the
**whole** python surface and the **whole** manual, and the usage mining
(``mine_transcripts``) records which pulls it reached for.  One arm — there
is deliberately no report-off python arm; a crippled package tests a package
nobody ships.

Each workspace ``<workspace_dir>/<eid>/`` holds:

- ``episode.json`` — the identical fixed request core the JSON arms get
  (pydantic JSON round-trip *is* the library-native form; the agent loads it
  through the schemas and drives the package directly — no shim);
- ``skill/`` — the agent skill tree, **verbatim and complete**, in *every*
  python cell: it ships with the package, so it is part of the surface being
  tested, never a treatment.  A directory since WP-1304, and the whole of it:
  handing over the body without its reference files would be testing a
  surface nobody ships;
- ``prompt.md`` — the v2 answer contract plus ``final_result.json``, the
  workspace rules and the budget.

There is **no condition marker and no shim**: the condition audit is N/A in
this arm by design, and the enforcement that remains — read nothing outside
the workspace, no network, the script-run cap — is the transcript audit's
(PROTOCOL.md 2.0 § Audit; the mining fields are in ``mine_transcripts``).

Two placement rules are structural, not advisory, and both are verified
rather than assumed:

- the **workspace lives outside the repo tree** — "no repo checkout
  reachable" starts with not building the workspace inside one;
- rietx is installed **non-editable into a venv outside the repo tree**,
  and the check is where imports *resolve*, not how the install was spelled
  — the worktree-venv lesson (tests/CLAUDE.md § Quoting numbers): a venv
  whose ``rietx`` resolves into a checkout measures the tree, not the
  package.

Usage::

    python -m tests.eval_report_agent.python_arm \\
        --workspace ~/eval-ws/python__sonnet --truth TRUTH \\
        --venv ~/eval-venvs/rietx-eval --only N1 C1 W1 W2
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from tests.eval_report_agent import build_fixtures as bf
from tests.eval_report_agent.scorer import NEXT_ACTIONS, VERDICTS

REPO_ROOT = Path(__file__).resolve().parents[2]

#: hard cap on fit-bearing script runs, enforced by the transcript audit —
#: the shim's ``MAX_CALLS`` with no shim to refuse; the prompt advertises 6
MAX_SCRIPT_RUNS = 8


def _inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return False
    return True


def verify_interpreter(python: Path) -> Path:
    """Where ``import rietx`` resolves under this interpreter — refused if
    inside the repo tree (an editable install, or a venv built in a
    checkout).  Returns the resolved package path."""
    out = subprocess.run(
        [str(python), "-c", "import rietx; print(rietx.__file__)"],
        capture_output=True, text=True, check=True)
    resolved = Path(out.stdout.strip()).resolve()
    if _inside_repo(resolved):
        raise ValueError(
            f"rietx resolves inside the repo tree ({resolved}); the arm "
            "requires a non-editable install into a venv outside it — the "
            "agent must be handed the package, never the checkout")
    return resolved


def ensure_venv(venv: Path) -> Path:
    """The arm's interpreter: created non-editable on first use, verified on
    every use.  Returns the interpreter path."""
    if _inside_repo(venv):
        raise ValueError(
            f"venv {venv} is inside the repo tree; build it outside "
            "(PROTOCOL.md 2.0 § The python-capable arm)")
    python = venv / "bin" / "python"
    if not python.exists():
        subprocess.run(["uv", "venv", "--python", "3.12", str(venv)],
                       check=True)
        subprocess.run(["uv", "pip", "install", "--python", str(python),
                        str(REPO_ROOT)], check=True)
    verify_interpreter(python)
    return python


_PROMPT = """\
# Episode {eid} — powder XRD refinement (python)

You are operating the `rietx` Rietveld refinement package directly, as an
installed python library, through this interpreter:

    {python}

This directory is your workspace.  **Work only inside it**: read no other
path on this machine, and do not use the network — the session is audited,
and a transcript that reaches outside invalidates the run.

- `episode.json` — the fixed inputs (structure, instrument, pattern), as the
  package's own JSON schemas.  It is mostly bulk pattern arrays — do not
  read it whole; load it through the schemas:

      import json
      import rietx as rx

      ep = json.load(open("episode.json"))
      structure = rx.Structure.model_validate(ep["structure"])
      instrument = rx.Instrument.model_validate(ep["instrument"])
      data = rx.PatternData.model_validate(ep["pattern"])

  `ep["mode"]` is the refinement mode; if `ep` carries `"two_theta_limits"`,
  pass it to `fit`.  These inputs are the episode: the pattern is fixed, and
  the models are your starting point.  How you refine — plans, stages, what
  you free or hold, model corrections you have evidence for — is yours.
- `skill/SKILL.md` — the package's operating protocol, with its reference
  files in `skill/references/`, verbatim and complete.
- Budget: plan on at most 6 fit-bearing script runs — a script run counts
  once however many fits it performs; the hard cap is {max_runs}, enforced
  by the session audit.  Run at least one fit — an answer with no
  refinement behind it scores zero.
{deliverable_section}
When you are done, write two files in this directory.

`final_result.json` — the `RefinementResult` you stand behind, exactly as
the package serialises it:

    from pathlib import Path
    Path("final_result.json").write_text(result.model_dump_json())

`answer.json`:

    {{"verdict": "<one of the five below>",
      "next_action": "<one of the six below>",
      "caveats": ["<zero or more short statements of limitations you would
                   attach to the delivered result>"],
      "summary": "<a few sentences: what you concluded and why>"}}

Verdict meanings — pick exactly one:

{verdict_glossary}

Next-action meanings — the single best next step, pick exactly one:

{next_action_glossary}

Work from the numbers.  A good fit is necessary but not sufficient:
parameters compensating for each other can look converged, so prefer the
verdict the evidence supports over the one that ends the episode.
"""


def render_prompt(eid: str, *, python: str,
                  deliverable: str | None = None) -> str:
    """The python-arm prompt: same answer contract and glossaries as the
    JSON arms (one authority — the scorer's vocabularies, `build_fixtures`'
    meanings), plus the two-file deliverable and the audit-enforced rules."""
    deliverable_section = ""
    if deliverable is not None:
        deliverable_section = bf._DELIVERABLE_SECTION.format(
            text=bf.DELIVERABLES[deliverable])
    return _PROMPT.format(
        eid=eid, python=python, max_runs=MAX_SCRIPT_RUNS,
        deliverable_section=deliverable_section,
        verdict_glossary=bf._glossary(bf.VERDICT_MEANINGS, VERDICTS),
        next_action_glossary=bf._glossary(bf.NEXT_ACTION_MEANINGS,
                                          NEXT_ACTIONS))


def write_workspaces(workspace_dir: Path, truth_dir: Path, *, python: str,
                     only: list[str] | None = None,
                     skill_src: Path | None = None) -> list[Path]:
    """Write python-arm workspaces + the truth tree; returns the dirs.

    The truth records are byte-identical to the JSON arms' — one truth tree
    serves the whole round, whichever arm built it last.

    ``skill_src`` is the skill tree to copy, this checkout's by default.  A
    round whose arms are two builds of the package (2.3) passes each build's
    own tree, since the skill ships in the wheel beside the code it describes.
    """
    if _inside_repo(workspace_dir):
        raise ValueError(
            f"workspace {workspace_dir} is inside the repo tree; the arm "
            "requires no repo checkout reachable — build it outside "
            "(PROTOCOL.md 2.0 § The python-capable arm)")
    wanted = tuple(only or bf.EPISODE_IDS)
    episodes = bf.assemble_episodes(wanted)
    if skill_src is None:
        skill_src = REPO_ROOT / "docs" / "skill" / "rietx"
    if not (skill_src / "SKILL.md").is_file():
        raise ValueError(f"{skill_src} holds no SKILL.md; not a skill tree")
    workspace_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for eid in wanted:
        ep = episodes[eid]
        wdir = workspace_dir / eid
        wdir.mkdir(exist_ok=True)
        (wdir / "episode.json").write_text(
            json.dumps(ep["core"], indent=1) + "\n", encoding="utf-8")
        skill_dst = wdir / "skill"
        if skill_dst.exists():
            shutil.rmtree(skill_dst)
        shutil.copytree(skill_src, skill_dst)
        (wdir / "prompt.md").write_text(
            render_prompt(eid, python=python,
                          deliverable=ep["truth"].get("deliverable")),
            encoding="utf-8")
        (truth_dir / f"{eid}.json").write_text(
            json.dumps(ep["truth"], indent=1) + "\n", encoding="utf-8")
        written.append(wdir)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True,
                        help="directory to write episode workspaces into "
                             "(outside the repo tree)")
    parser.add_argument("--truth", type=Path, required=True,
                        help="scorer-side truth tree (outside the agent's "
                             "reach)")
    parser.add_argument("--venv", type=Path, required=True,
                        help="the arm's venv (outside the repo tree); "
                             "created non-editable on first use, verified "
                             "on every use")
    parser.add_argument("--only", nargs="*", choices=bf.EPISODE_IDS,
                        help="subset of episodes (default: all nine)")
    parser.add_argument("--skill", type=Path, default=None,
                        help="the skill tree to copy into each workspace "
                             "(default: this checkout's docs/skill/rietx)")
    args = parser.parse_args(argv)
    python = ensure_venv(args.venv)
    written = write_workspaces(args.workspace, args.truth,
                               python=str(python), only=args.only,
                               skill_src=args.skill)
    for wdir in written:
        print(wdir)


if __name__ == "__main__":
    main()
