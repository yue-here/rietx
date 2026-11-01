"""Mine a kept agent-eval record for what the agents actually read (WP-1063).

Round 2 graded *outcomes* (``scorer.py``) and left the mechanism to be read
out of thirty transcripts by hand.  This reads it deterministically instead,
around the distinction the outcome grid could not make:

- **probed** — the agent's own query names a field (the ``jq`` or ``python -c``
  that reaches into ``response['report']['identifiability']``).  Going to look.
- **delivered** — the field's text came back in a tool result, i.e. entered the
  agent's context.  Having it.
- **voiced** — the agent's own prose names it: assistant text blocks, and the
  ``answer.json`` it wrote.  Saying it.

The three come apart, and that is the point.  An agent that never printed the
identifiability section was never misled by the exchange clause; one that
printed it and never mentioned it was not persuaded by it; and a trajectory
nobody probed was paid for and unread.  Two caveats ride with every count
here and belong in any sentence quoting them:

- **quoting is reading, not benefiting** (round 1: E7 quoted the report
  verbatim and was wrong with it) — no surface here measures usefulness;
- whether ``voiced`` is a floor or a measure depends on whether the record
  keeps thinking blocks, so that is **measured per record**
  (``thinking_text_chars``), never asserted: round 2's transcripts carried 0
  characters across all 30 (a floor); round 3 keeps them.  Thinking is not a
  ``voiced`` surface — it is the agent reasoning, not saying — so the counts
  do not change with it; only the caveat does.

Counts, never percentages — round 2 was N = 30 across 15 condition×model
cells; round 3 is N = 28 across 8.

The token vocabulary is quoted from the live schemas (``FIELD_TOKENS``,
``ActionKind``), never invented here: a renamed field must break this module
loudly rather than count zero for ever — the derived-flag rot of WP-1037, one
directory over.

Usage::

    python -m tests.eval_report_agent.mine_transcripts eval-runs/2026-08-13-round2
    python -m tests.eval_report_agent.mine_transcripts RECORD --json mined.json

The record is gitignored and may simply be absent (``eval-runs/README.md``):
that is reported as a message and exit 2, never a traceback.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import get_args

import pydantic

from rietx.report import schemas as report_schemas
from rietx.report.schemas import (
    ActionKind,
    ExchangeFinding,
    FitReport,
    IdentifiabilityEvidence,
    StageReport,
    SuggestedAction,
)
from rietx.schemas import results as result_schemas
from tests.eval_report_agent.run_refine import ALLOWED_OVERLAY_KEYS

#: the three surfaces, in the order a fact travels through a transcript
SURFACES = ("probed", "delivered", "voiced")

#: report/evidence tokens we count, each pinned to the live model field it
#: names.  Pairs, not bare strings, so ``test_mine_transcripts`` can fail on a
#: rename instead of the miner silently counting zero.  ``background`` joined
#: for round 3 (WP-1064): the python arm's "read the evidence tables?"
#: question needs both halves of the WP-1055/1056 evidence counted
FIELD_TOKENS: dict[str, tuple[type[pydantic.BaseModel], str]] = {
    "exchangeable": (ExchangeFinding, "exchangeable"),
    "identifiability": (FitReport, "identifiability"),
    "background": (FitReport, "background"),
    "lebail_gap": (FitReport, "lebail_gap"),
    "soft_modes": (IdentifiabilityEvidence, "soft_modes"),
    "worst_absorption": (StageReport, "worst_absorption"),
    "confidence": (SuggestedAction, "confidence"),
    # 2.2 (WP-1107): did any transcript voice WP-1106's field — the
    # ``execution`` pair's read-out (d)
    "execution": (SuggestedAction, "execution"),
}

#: every citation token: the fields above plus the whole action vocabulary
TOKENS: tuple[str, ...] = tuple(FIELD_TOKENS) + tuple(get_args(ActionKind))

def _pull_tokens() -> dict[str, tuple[object, str, str]]:
    """The python arm's sanctioned pulls (WP-1064), each pinned to the live
    attribute it names — the FIELD_TOKENS rule for callables, so a renamed
    surface breaks the miner loudly.  ``method`` tokens are matched as
    attribute calls (``.report(``) because the bare words are everyday
    prose; ``function`` tokens are distinctive enough to match by name,
    which also catches the ``import`` that precedes a call."""
    import rietx.report as report_pkg
    from rietx.history.tree import RefinementTree
    from rietx.refine import Refinement

    return {
        "report": (Refinement, "report", "method"),
        "suggest": (Refinement, "suggest", "method"),
        "branch": (Refinement, "branch", "method"),
        "compare": (RefinementTree, "compare", "method"),
        "predict_then_verify": (report_pkg, "predict_then_verify",
                                "function"),
        "compare_rivals": (report_pkg, "compare_rivals", "function"),
    }


PULL_TOKENS = _pull_tokens()

#: the pair of paths whose ridge WP-1059 measured, as the *episode* declares
#: them (``TRUTH/<ep>.json`` ``watch``), never as this module assumes them
RIVAL_GROUPS = ("cause", "absorber")

#: the episodes WP-1059's "seven of twenty" counted.  E8 is a position episode
#: too and its both-free cells are reported beside these, but it is **not** in
#: the denominator: its planted cause *is* the absorber path, so the default
#: plan frees that rival legitimately and a both-free E8 state is not the same
#: event.  Reproducing the published 7/20 is this module's self-check
WP1059_POSITION_EPISODES = ("E2", "R1")

#: the episode id admits a trailing letter since 2.0 (``E8p``, ``J1P``,
#: ``J1S``); ``python`` is a condition like any other here — the arm's cells
#: are named the same way.  A condition name admits single underscores since
#: 2.2 (``report_stat``, ``report_noexec``) — the cell separator stays the
#: double underscore, which no condition name may contain.  A path separator
#: is ``/`` or a run of backslashes: a Windows launcher writes ``\``, and a
#: transcript is read as raw JSONL, where that arrives escaped as ``\\``
_SEP = r"(?:/|\\+)"
_CELL_RE = re.compile(
    rf"RUNS{_SEP}(?P<condition>[a-z]+(?:_[a-z]+)*)__(?P<model>[A-Za-z0-9.\-]+)"
    rf"{_SEP}(?P<episode>[A-Z]\d+[A-Za-z]?)")

#: an agent asking for the trajectory, or a rung's text arriving: the response
#: key itself, plus the word a prompt and an agent would use for one rung
_TRAJECTORY_WORDS = ("trajectory", "rung")

#: the WP-1056 exchange clause as **round 2 delivered it**, frozen on purpose.
#: This is not a quotation of the live :func:`identifiability_clause` and must
#: never become one: the record cannot change and WP-1063 rewords the live
#: sentence, so a miner that tracked the code would score the old record zero
#: and call that a finding
CLAUSE_PHRASE = "exchangeable with the held"

#: the WP-1065 license's anchor as the 2.2 round delivers it (PROTOCOL.md 2.2
#: read-out (a): *in-context* is this text on the delivered or voiced
#: surface, never a word-match on ``answer.json`` summaries).  Unlike
#: :data:`CLAUSE_PHRASE` this one must match the **live** sentence while its
#: round runs, so ``test_mine_transcripts`` pins it against a rendered
#: clause — a later WP that rewords the license breaks that pin loudly, and
#: the successor freezes this phrase for the archived records before quoting
#: the new sentence
LICENSE_PHRASE = "the data has chosen"


def rung_only_fields() -> frozenset[str]:
    """Field names carried by :class:`StageReport` and by no other model in
    either schema module — the marker that some delivered text is a *rung*
    rather than the final report or the result.

    Derived from the live models, so a field that migrates onto ``FitReport``
    stops being a marker by itself.  Both modules are walked, not just their
    top-level containers — which is also why the set moves with the schemas:
    ``stage`` was disqualified by being an ``IterationRecord`` field too,
    until WP-1003 deleted that never-populated class and ``stage`` became
    rung-only by this same derivation, no exclusion list either way.  What
    keeps ``actions`` usable is the JSON form every marker is matched in
    (:func:`_as_json`) — ``"actions"`` cannot match inside
    ``"suggested_actions"``.
    """
    elsewhere: set[str] = set()
    for module in (report_schemas, result_schemas):
        for obj in vars(module).values():
            if (inspect.isclass(obj) and issubclass(obj, pydantic.BaseModel)
                    and obj is not StageReport):
                elsewhere |= set(obj.model_fields)
    return frozenset(set(StageReport.model_fields) - elsewhere)


RUNG_MARKERS = rung_only_fields()


class MissingRecord(Exception):
    """The round record is absent or not a round record — said, not raised at
    the user as a traceback (``main`` renders it and exits 2)."""


# ----------------------------------------------------------------------
# the transcript, as an ordered stream
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Event:
    """One thing that happened, at its ordinal position in the transcript."""

    index: int
    surface: str
    kind: str          # "text" | "tool_use:<name>" | "tool_result"
    text: str
    inputs: dict = field(default_factory=dict)   # tool_use input, verbatim
    #: the call's own id on a ``tool_use``, the id it answers on a
    #: ``tool_result`` — how a result is tied to the question that asked it
    tool_id: str | None = None


def _blocks(line: dict) -> tuple[str, list]:
    """(role, content blocks) for a transcript line; ("", []) for the
    attachment and summary lines that carry no message."""
    message = line.get("message")
    if not isinstance(message, dict):
        return "", []
    content = message.get("content")
    if isinstance(content, str):
        return message.get("role", ""), [{"type": "text", "text": content}]
    return message.get("role", ""), content if isinstance(content, list) else []


def _result_text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    return json.dumps(content)


def read_events(path: Path) -> list[Event]:
    """The transcript as an ordered event stream, surfaces assigned.

    A ``Write`` of ``answer.json`` is the agent's own prose (it is the answer
    it was asked to write), so it lands in ``voiced``; every other tool input
    is a query the agent made, so it lands in ``probed``.
    """
    events: list[Event] = []
    for index, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not raw.strip():
            continue
        line = json.loads(raw)
        role, blocks = _blocks(line)
        for block in blocks:
            kind = block.get("type")
            if role == "assistant" and kind == "text":
                events.append(Event(index, "voiced", "text", block["text"]))
            elif role == "assistant" and kind == "tool_use":
                inputs = block.get("input") or {}
                target = str(inputs.get("file_path", ""))
                surface = ("voiced" if target.endswith("answer.json")
                           else "probed")
                events.append(Event(index, surface, f"tool_use:{block['name']}",
                                    json.dumps(inputs), inputs,
                                    block.get("id")))
            elif kind == "tool_result":
                events.append(Event(index, "delivered", "tool_result",
                                    _result_text(block), {},
                                    block.get("tool_use_id")))
    return events


def _thinking_chars(path: Path) -> int:
    """Characters of thinking carried by one transcript — measured, because
    whether ``voiced`` is a floor (round 2: 0 across all 30) or has the
    reasoning beside it (round 3 keeps thinking) is a property of the record,
    not of this module."""
    if not path.exists():
        return 0
    total = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        _role, blocks = _blocks(json.loads(raw))
        total += sum(len(b.get("thinking", "")) for b in blocks
                     if isinstance(b, dict) and b.get("type") == "thinking")
    return total


def cell_of(text: str) -> tuple[str, str, str] | None:
    """``(condition, model, episode)`` from the workspace path the runner put
    in the prompt — or None when the transcript names no cell, and None when
    it names more than one, which is a record problem to report rather than a
    tie to break."""
    found = {m.group("condition", "model", "episode")
             for m in _CELL_RE.finditer(text)}
    return found.pop() if len(found) == 1 else None


# ----------------------------------------------------------------------
# counting
# ----------------------------------------------------------------------
def _loose(token: str) -> re.Pattern[str]:
    """The token as anyone would write it — prose, a shell command, a python
    subscript.  ``\\b`` makes each field name match itself only: ``lebail_gap``
    does not match a rung's ``lebail_gap_ratio`` (``_`` is a word character),
    which is right — they are different fields."""
    return re.compile(rf"\b{re.escape(token)}\b")


def _as_json(token: str) -> re.Pattern[str]:
    """The token as JSON: a quoted key (``"identifiability":``) or a quoted
    value (``"kind": "add_impurity_phase"``).

    What makes this the right rule for ``delivered`` is measured, not
    stylistic.  The §5/§6 manual excerpts inside every report-on prompt name
    the whole action vocabulary in prose, so a loose count scored 24 of 30
    cells on ``add_impurity_phase`` before the package had sent anything — it
    was counting the agent's own reading material.  No token in this
    vocabulary appears double-quoted anywhere in a prompt (checked across the
    round); in a response every one of them does.
    """
    return re.compile(rf'"{re.escape(token)}"')


_PROBE_RES = {token: _loose(token) for token in TOKENS}
_DELIVERED_RES = {token: _as_json(token) for token in TOKENS}
_RUNG_RES = {marker: _as_json(marker) for marker in RUNG_MARKERS}
_CLAUSE_RE = re.compile(re.escape(CLAUSE_PHRASE))
_LICENSE_RE = re.compile(re.escape(LICENSE_PHRASE))

#: a pull as the agent's own code would spell it: methods as attribute calls,
#: module functions by their (distinctive) names — which also catches the
#: import that precedes a call
_PULL_RES = {
    token: re.compile(rf"\.{re.escape(token)}\s*\(" if kind == "method"
                      else rf"\b{re.escape(token)}\b")
    for token, (_owner, _name, kind) in PULL_TOKENS.items()}

#: one *fit-bearing* script run: a probed event whose payload performs a
#: solve.  Counted per event (a script that fits five times is one run) —
#: the python arm's budget counter, PROTOCOL.md 2.0 § The python-capable arm.
#: A third alternative matched the JSON envelope's one call until WP-1303
#: deleted it; a python-arm agent now has only these two ways to solve.
_FIT_RE = re.compile(r"\.fit\s*\(|\.run_stage\s*\(")

#: audit candidates (PROTOCOL.md 2.0 § Audit): deterministic pointers for
#: the human audit, never verdicts — matched over *probed* payloads only
#: (the agent's own commands; delivered text legitimately contains any of
#: these words).  ``eval_harness`` exempts ``run_refine``, the one sanctioned
#: entry point; the sibling ``.condition.json`` is its own pattern because
#: reading it is exactly the leak the 2.0 relocation exists to close
AUDIT_PATTERNS: dict[str, re.Pattern[str]] = {
    "condition_marker": re.compile(r"\.condition\.json"),
    "truth_tree": re.compile(r"\bTRUTH/"),
    "eval_harness": re.compile(r"eval_report_agent[/.](?!run_refine)"),
    "repo_docs": re.compile(r"\bdocs/"),
    "network": re.compile(r"\bhttps?://|\bcurl\b|\bwget\b"),
}


def _res_for(surface: str) -> dict[str, re.Pattern[str]]:
    """Delivery is data arriving, so it is matched in JSON form; probing and
    voicing are the agent using the name, so they are matched loosely."""
    return _DELIVERED_RES if surface == "delivered" else _PROBE_RES


def citations(events: list[Event]) -> dict[str, dict[str, int]]:
    """Per token, occurrences on each surface."""
    counts = {token: dict.fromkeys(SURFACES, 0) for token in TOKENS}
    for event in events:
        for token, rx in _res_for(event.surface).items():
            hits = len(rx.findall(event.text))
            if hits:
                counts[token][event.surface] += hits
    return counts


def first_index(events: list[Event], surface: str,
                rx: re.Pattern[str]) -> int | None:
    """Transcript position of the first event on ``surface`` matching ``rx``."""
    for event in events:
        if event.surface == surface and rx.search(event.text):
            return event.index
    return None


def _json_objects(text: str) -> list[dict]:
    """Every JSON object embedded anywhere in a string, decoded.

    Brace-scan plus ``raw_decode``: it finds an object wherever it sits in a
    shell command, and never mistakes a brace inside a string for one.
    """
    decoder = json.JSONDecoder()
    objects: list[dict] = []
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(value, dict):
            objects.append(value)
    return objects


def _payloads(event: Event) -> list[str]:
    """The strings a tool call actually carried.

    A ``Write``'s overlay is the ``content`` *value* — escaped inside the
    serialized input, where no brace scan can reach it — so the values are
    scanned, not the dump.  A ``Bash`` heredoc is the ``command`` value, and
    falls out of the same rule.
    """
    if event.inputs:
        return [v for v in event.inputs.values() if isinstance(v, str)]
    return [event.text]


def overlay_writes(events: list[Event]) -> list[tuple[int, dict]]:
    """``(transcript index, overlay)`` for every event that wrote an overlay.

    An event counts when it names ``overlay.json`` and carries a JSON object
    whose keys are within the shim's own allow-list (imported, not restated).
    Tool-agnostic on purpose: ``Write``, ``echo >`` and a heredoc all read the
    same way — measured necessary, one of the seven ridge cells wrote its
    overlay with ``cat > overlay.json << 'EOF'``.
    """
    writes: list[tuple[int, dict]] = []
    for event in events:
        if event.surface == "delivered" or "overlay.json" not in event.text:
            continue
        for payload in _payloads(event):
            found = next((obj for obj in _json_objects(payload)
                          if set(obj) <= ALLOWED_OVERLAY_KEYS), None)
            if found is not None:
                writes.append((event.index, found))
                break
    return writes


def _reaches(glob: str, watched: str) -> bool:
    """Whether a ``turn_on`` glob and a watch glob name the same parameter.

    Either may be the wildcard side (``instrument.geometry.*`` freeing a
    literal watched path; a literal free matching a watched ``phases.*.cell.*``
    group), so both directions are tried.
    """
    return fnmatch(watched, glob) or fnmatch(glob, watched)


def overlay_frees(overlay: dict, globs: list[str]) -> bool:
    """Whether an explicit-stage overlay frees anything in ``globs``.

    ``plan`` as a *preset name* answers False: which paths a preset frees is
    not in the overlay, and guessing it here would put a number in the ridge
    column that the record does not contain.
    """
    plan = overlay.get("plan")
    if not isinstance(plan, dict):
        return False
    for stage in plan.get("stages") or ():
        if not isinstance(stage, dict):
            continue
        for glob in stage.get("turn_on") or ():
            if any(_reaches(str(glob), watched) for watched in globs):
                return True
    return False


# ----------------------------------------------------------------------
# the record
# ----------------------------------------------------------------------
@dataclass
class Cell:
    condition: str
    model: str
    episode: str
    transcript: Path
    events: list[Event]
    card: dict | None
    truth: dict | None
    meta_model: str | None
    notes: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.condition}__{self.model}/{self.episode}"


def read_record(root: Path) -> list[Cell]:
    """Load one round record into cells, or say what is missing."""
    if not root.exists():
        raise MissingRecord(
            f"no round record at {root} — records are gitignored and may have "
            "been deleted (eval-runs/README.md); nothing here depends on one")
    transcripts = sorted((root / "transcripts").glob("agent-*.jsonl"))
    if not transcripts:
        raise MissingRecord(
            f"{root} has no transcripts/agent-*.jsonl — not a round record, "
            "or kept without its transcripts")
    cards = {}
    scorecards = root / "scorecards.json"
    if scorecards.exists():
        cards = {(c["cell"], c["episode"]): c
                 for c in json.loads(scorecards.read_text(encoding="utf-8"))}
    cells: list[Cell] = []
    for path in transcripts:
        text = path.read_text(encoding="utf-8")
        named = cell_of(text)
        if named is None:
            cells.append(Cell("?", "?", "?", path, [], None, None, None,
                              ["transcript names no single cell"]))
            continue
        condition, model, episode = named
        meta_path = path.with_suffix(".meta.json")
        meta_model = None
        if meta_path.exists():
            meta_model = json.loads(
                meta_path.read_text(encoding="utf-8")).get("model")
        truth_path = root / "TRUTH" / f"{episode}.json"
        truth = (json.loads(truth_path.read_text(encoding="utf-8"))
                 if truth_path.exists() else None)
        cell = Cell(condition, model, episode, path, read_events(path),
                    cards.get((f"{condition}__{model}", episode)), truth,
                    meta_model)
        if meta_model is not None and meta_model != model:
            cell.notes.append(
                f"meta.json model {meta_model!r} != workspace model {model!r}")
        if cell.card is None:
            cell.notes.append("no scorecard for this cell")
        if truth is None:
            cell.notes.append("no truth record for this episode")
        cells.append(cell)
    return cells


# ----------------------------------------------------------------------
# the three questions
# ----------------------------------------------------------------------
def ridge_row(cell: Cell) -> dict:
    """Did this cell free both rivals, and what did it know when it did?

    ``both_free`` is read from the scorecard's truth-declared watch groups
    (the shim's log, one derivation up) — the same statistic WP-1059 counted.
    The ordering is read from the transcript: the first overlay that frees
    both, against the first *delivery* and first *voicing* of the exchange
    clause.  ``clause_delivered_before`` is what the agent had; the voiced
    column is what it said it had, and the two are not the same measurement.
    """
    watch = (cell.card or {}).get("watch") or {}
    both_free = all(watch.get(group) for group in RIVAL_GROUPS)
    row = {
        "both_free": bool(both_free),
        "ridge_overlay_index": None,
        "clause_delivered_index": None,
        "clause_voiced_index": None,
        "clause_delivered_before": None,
        "clause_voiced_before": None,
    }
    groups = ((cell.truth or {}).get("watch") or {})
    globs = [g for group in RIVAL_GROUPS for g in groups.get(group, ())]
    if globs:
        for index, overlay in overlay_writes(cell.events):
            if all(overlay_frees(overlay, list(groups.get(group, ())))
                   for group in RIVAL_GROUPS):
                row["ridge_overlay_index"] = index
                break
    row["clause_delivered_index"] = first_index(cell.events, "delivered",
                                                _CLAUSE_RE)
    row["clause_voiced_index"] = first_index(cell.events, "voiced", _CLAUSE_RE)
    ridge = row["ridge_overlay_index"]
    if ridge is not None:
        for surface in ("delivered", "voiced"):
            seen = row[f"clause_{surface}_index"]
            row[f"clause_{surface}_before"] = seen is not None and seen < ridge
    return row


def rung_row(cell: Cell) -> dict:
    """Was the trajectory asked for, did a rung come back, was it named?

    Three distinct events, and keeping them apart is the point — a trajectory
    the condition delivered, an agent never asked for and a rung whose text
    never entered context are three different failures, and only the first is
    the package's:

    - ``probed`` — the agent's own query names the key or a rung;
    - ``answered`` — a result **answering that query**, tied to it by
      ``tool_use_id`` rather than by adjacency.  Necessary, not fussiness: one
      cell filtered the trajectory through its own ``jq`` projection
      (``{stage, rwp, abstained_reason}``), so real rung content arrived
      carrying no marker field at all;
    - ``marker`` — rung content proper, by a field name only a rung has.
    """
    words = re.compile("|".join(_TRAJECTORY_WORDS))
    marker = None
    for event in cell.events:
        if event.surface == "delivered" and any(rx.search(event.text)
                                                for rx in _RUNG_RES.values()):
            marker = event.index
            break
    asked = {event.tool_id for event in cell.events
             if event.surface == "probed" and event.tool_id
             and words.search(event.text)}
    answered = next((event.index for event in cell.events
                     if event.surface == "delivered"
                     and event.tool_id in asked), None)
    return {
        "trajectory_rungs": (cell.card or {}).get("trajectory_rungs"),
        "probed_index": first_index(cell.events, "probed", words),
        "answered_index": answered,
        "marker_index": marker,
        "voiced_index": first_index(cell.events, "voiced", words),
    }


def usage_row(cell: Cell) -> dict:
    """The pull record (WP-1064): which sanctioned surfaces the agent's own
    code reached for, as first-probed transcript indices (None = never), plus
    the fit-bearing script-run count the python arm's budget is audited
    against.  Mined for every cell — a JSON cell scores zero everywhere,
    which is itself the control."""
    row = {token: first_index(cell.events, "probed", rx)
           for token, rx in _PULL_RES.items()}
    row["fit_bearing_runs"] = sum(
        1 for event in cell.events
        if event.surface == "probed"
        and any(_FIT_RE.search(payload) for payload in _payloads(event)))
    return row


def license_row(cell: Cell) -> dict:
    """The 2.2 in-context fact (PROTOCOL.md 2.2 read-out (a)): first indices
    at which the WP-1065 license text entered context (``delivered``) or the
    agent's own prose (``voiced``).  The 2.1 finding this measures again:
    delivered-in-the-response is not delivered-to-the-model when the agent
    pipes the response to a file and greps the statistics back."""
    return {
        "delivered_index": first_index(cell.events, "delivered", _LICENSE_RE),
        "voiced_index": first_index(cell.events, "voiced", _LICENSE_RE),
    }


def swap_rows(cell: Cell) -> list[dict]:
    """The 2.2 swap-state fact (PROTOCOL.md 2.2 audit): every overlay that
    frees exactly one rival — the swap shape — and whether it also freed the
    cell, because a decisive ratio measured cell-held answers a different
    question than the registered tie (``python__sonnet`` N1, 2.1: 1.277 for
    the wrong rival on a cell-held state).

    Explicit stage lists only, ``overlay_frees``'s rule — a preset name
    carries no path list, and the swap the clause teaches is an explicit
    plan by construction.  A python cell's swaps live in its scripts;
    ``compare_rivals``' first probe (``usage_row``) is their minable shadow.
    """
    groups = ((cell.truth or {}).get("watch") or {})
    cause = list(groups.get("cause", ()))
    absorber = list(groups.get("absorber", ()))
    if not cause or not absorber:
        return []
    rows = []
    for index, overlay in overlay_writes(cell.events):
        frees_cause = overlay_frees(overlay, cause)
        frees_absorber = overlay_frees(overlay, absorber)
        if frees_cause == frees_absorber:
            continue
        rows.append({
            "overlay_index": index,
            "freed": "cause" if frees_cause else "absorber",
            "cell_free": overlay_frees(overlay, ["phases.*.cell.*"]),
        })
    return rows


def audit_row(cell: Cell) -> list[dict]:
    """Audit candidates: probed events matching a forbidden-surface pattern.

    Pointers for the human audit, never verdicts — the python arm reads its
    *own* agent skill legitimately, and a flagged event may quote a
    path without opening it.  What a flag buys is that nobody has to re-read
    thirty transcripts to find the three worth reading.
    """
    flags = []
    for event in cell.events:
        if event.surface != "probed":
            continue
        for name, rx in AUDIT_PATTERNS.items():
            if any(rx.search(payload) for payload in _payloads(event)):
                flags.append({"pattern": name, "index": event.index})
    return flags


def mine(root: Path) -> dict:
    """Every per-cell row plus the record-level self-checks."""
    cells = read_record(root)
    rows = []
    for cell in cells:
        rows.append({
            "cell": cell.name,
            "condition": cell.condition,
            "model": cell.model,
            "episode": cell.episode,
            "transcript": cell.transcript.name,
            "n_events": len(cell.events),
            "citations": citations(cell.events),
            "ridge": ridge_row(cell),
            "rungs": rung_row(cell),
            "usage": usage_row(cell),
            "license": license_row(cell),
            "swaps": swap_rows(cell),
            "audit_flags": audit_row(cell),
            "verdict": (cell.card or {}).get("verdict"),
            "passed": (cell.card or {}).get("passed"),
            "notes": cell.notes,
        })
    named = [row for row in rows if row["episode"] != "?"]
    position = [row for row in named
                if row["episode"] in WP1059_POSITION_EPISODES]
    voiced_chars = sum(len(e.text) for cell in cells for e in cell.events
                       if e.surface == "voiced" and e.kind == "text")
    thinking_chars = sum(_thinking_chars(cell.transcript) for cell in cells)
    by_episode: dict[str, int] = {}
    for row in named:
        by_episode.setdefault(row["episode"], 0)
        by_episode[row["episode"]] += int(row["ridge"]["both_free"])
    return {
        "record": str(root),
        "n_transcripts": len(rows),
        "n_cells_named": len({row["cell"] for row in named}),
        "voiced_text_chars": voiced_chars,
        "thinking_text_chars": thinking_chars,
        "position_cells": len(position),
        "position_cells_both_free": sum(1 for row in position
                                        if row["ridge"]["both_free"]),
        "both_free_by_episode": dict(sorted(by_episode.items())),
        "notes": [note for row in rows for note in row["notes"]],
        "rows": rows,
    }


# ----------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------
def _table(header: list[str], body: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines)


def render(mined: dict) -> str:
    """The counts tables, as markdown for a handover entry."""
    rows = [row for row in mined["rows"] if row["episode"] != "?"]
    thinking = mined["thinking_text_chars"]
    thinking_note = (f"{thinking} of thinking"
                     if thinking else
                     "no thinking blocks kept — `voiced` is a floor")
    out = [f"# Mined: {mined['record']}", "",
           f"{mined['n_transcripts']} transcripts, "
           f"{mined['n_cells_named']} named cells, "
           f"{mined['voiced_text_chars']} characters of assistant text "
           f"({thinking_note}).", "",
           "## Citations — cells (of "
           f"{len(rows)}) with at least one occurrence", ""]
    body = []
    for token in TOKENS:
        counts = [sum(1 for row in rows if row["citations"][token][surface])
                  for surface in SURFACES]
        if any(counts):
            body.append([f"`{token}`"] + [str(c) for c in counts])
    out += [_table(["token", *SURFACES], body), "",
            "## Citations by condition — cells with ≥1 *delivered*", ""]
    conditions = sorted({row["condition"] for row in rows})
    body = []
    for token in TOKENS:
        counts = [sum(1 for row in rows
                      if row["condition"] == c
                      and row["citations"][token]["delivered"])
                  for c in conditions]
        if any(counts):
            body.append([f"`{token}`"] + [str(c) for c in counts])
    out += [_table(["token", *conditions], body), ""]
    if "off" in conditions:
        out += ["The `off` column is the ambiguity control: a token it scores "
                "on is a name the *result* carries too (`identifiability`, "
                "`soft_modes` — `RefinementResult.identifiability`), not "
                "evidence that a report reached an arm denied one.", ""]
    out += ["## The ridge: cells that freed both rivals", "",
            f"{mined['position_cells_both_free']} of "
            f"{mined['position_cells']} cells on "
            f"{', '.join(WP1059_POSITION_EPISODES)} (the episodes WP-1059 "
            "counted).  Both-free by episode: "
            + ", ".join(f"{ep} {n}"
                        for ep, n in mined["both_free_by_episode"].items())
            + ".", ""]
    body = []
    for row in rows:
        ridge = row["ridge"]
        if not ridge["both_free"]:
            continue
        body.append([
            row["cell"],
            str(ridge["ridge_overlay_index"]),
            str(ridge["clause_delivered_index"]),
            str(ridge["clause_voiced_index"]),
            {True: "yes", False: "no", None: "—"}[ridge["clause_delivered_before"]],
            {True: "yes", False: "no", None: "—"}[ridge["clause_voiced_before"]],
        ])
    out += [_table(["cell", "both-free overlay", "clause delivered",
                    "clause voiced", "had it first", "said it first"], body),
            "", "## Trajectory: probed, delivered, voiced", ""]
    body = []
    for row in sorted(rows, key=lambda r: r["cell"]):
        rungs = row["rungs"]
        body.append([
            row["cell"],
            str(rungs["trajectory_rungs"]),
            str(rungs["probed_index"]),
            str(rungs["answered_index"]),
            str(rungs["marker_index"]),
            str(rungs["voiced_index"]),
        ])
    out += [_table(["cell", "rungs shipped", "probed", "answered",
                    "rung content", "voiced"], body), ""]
    out += ["## License in context (2.2) — first index (— = never), and "
            "swap-shaped overlays as freed(cell held/free)", ""]
    body = []
    for row in sorted(rows, key=lambda r: r["cell"]):
        fmt = {None: "—"}
        swaps = "; ".join(
            f"{s['freed']}({'cell free' if s['cell_free'] else 'cell held'})"
            for s in row["swaps"]) or "—"
        body.append([
            row["cell"],
            fmt.get(row["license"]["delivered_index"],
                    str(row["license"]["delivered_index"])),
            fmt.get(row["license"]["voiced_index"],
                    str(row["license"]["voiced_index"])),
            swaps,
        ])
    out += [_table(["cell", "license delivered", "license voiced", "swaps"],
                   body), ""]
    python_rows = [row for row in rows if row["condition"] == "python"]
    if python_rows:
        out += ["## Python-arm pulls — first probed index (— = never)", ""]
        body = []
        for row in sorted(python_rows, key=lambda r: r["cell"]):
            usage = row["usage"]
            body.append([row["cell"]]
                        + [str(usage[t]) if usage[t] is not None else "—"
                           for t in PULL_TOKENS]
                        + [str(usage["fit_bearing_runs"])])
        out += [_table(["cell", *PULL_TOKENS, "fit runs"], body), ""]
    flagged = [(row["cell"], flag) for row in rows
               for flag in row["audit_flags"]]
    if flagged:
        out += ["## Audit candidates — probed events to spot-check "
                "(pointers, not verdicts)", ""]
        out += [f"- {cell}: `{flag['pattern']}` at event {flag['index']}"
                for cell, flag in flagged] + [""]
    if mined["notes"]:
        out += ["## Record notes", ""] + [f"- {n}" for n in mined["notes"]] + [""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path,
                        help="a round directory under eval-runs/")
    parser.add_argument("--json", type=Path, default=None,
                        help="also write the per-cell rows here")
    args = parser.parse_args(argv)
    try:
        mined = mine(args.record)
    except MissingRecord as exc:
        print(f"mine_transcripts: {exc}", file=sys.stderr)
        return 2
    if args.json is not None:
        args.json.write_text(json.dumps(mined, indent=1), encoding="utf-8")
    sys.stdout.write(render(mined))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
