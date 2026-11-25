"""Project one agent session into a trail: one line per tool call, and its bill.

    python tests/eval_agent_surface/trail.py TRANSCRIPT.jsonl [TRACE.jsonl]

The transcript is the harness's session log; the trace is what
`rietx_surface_trace.py` appended from inside that run's own interpreters.  The
table this prints answers most of a round's questions on its own, which is why
the 2026-08-27 audit could interrogate a 3.9 MB transcript for ~40 k tokens
without reading it (maintainer memory `agent-surface-audit-insitu-ramp` § How
to interrogate a run).  It was a scratch script then and is committed now,
because the two rules below are the whole reason the numbers came out right and
neither survives being remembered.

**Usage is summed once per `message.id`, last record wins.** A thinking block
and its tool_use are two records of *one* API call sharing an id: the audit's
first pass summed per record and over-counted cache reads by 151/90 — 23.9 M
against the true 14.6 M, which is the difference between "a document cost 17 %
of the run" and a number that means nothing.

**Fit seconds come from the trace, never from the command head.** What ran a
fit is a fact about a process, not about the first line of a shell command: a
driver script says `python driver.py`, a backgrounded job says `nohup … &`, and
`python -c` leaves nothing in `argv` at all.  The shim times the call inside
the process that made it, so all three are counted here and none of them could
be counted by grepping commands — which is exactly what the campaign's
projection had to do.

Nothing here is specific to one round: it reads a transcript and a trace, and
the round's own scorer says what the numbers mean.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Calls whose elapsed seconds are *refinement*, as opposed to reading, judging
# or plotting.  R1 sets a run's wall clock against this sum and R7 counts Bash
# calls per entry in it.
FIT_CALLS = frozenset({
    "refine", "refine_sequential", "refine_joint", "replay",
    "Refinement.fit", "Refinement.run_stage", "SequentialRefinement.fit",
})


def load(path: str | Path) -> list[dict]:
    """JSONL, tolerant of a truncated last line (a live session is appended to)."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _stamp(row: dict) -> float | None:
    text = row.get("timestamp")
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


@dataclass
class Call:
    """One tool call: when it started, how long it took, and what came back."""

    index: int
    tool: str
    head: str
    offset: float | None = None
    duration: float | None = None
    # `None` until the result arrives, never a defaulted answer: a session can
    # end with a call in flight (the pilot's bare run left a backgrounded chain
    # running), and `error = False` there would say "this did not fail" about
    # something nothing has checked.
    out_chars: int | None = None
    error: bool | None = None

    def line(self) -> str:
        off = f"{self.offset:7.1f}" if self.offset is not None else "      ?"
        dur = f"{self.duration:6.1f}" if self.duration is not None else "     ?"
        size = f"{self.out_chars:8d}" if self.out_chars is not None else "       ?"
        flag = "   " if self.error is False else ("ERR" if self.error else " ? ")
        return f"{self.index:4d} {off} {dur} {size} {flag} {self.tool:<10} {self.head[:88]}"


@dataclass
class Usage:
    """The bill, summed once per API call."""

    api_calls: int = 0
    input_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output_tokens: int = 0
    wall_seconds: float | None = None
    models: Counter = field(default_factory=Counter)

    @property
    def mean_context(self) -> float:
        return (self.input_tokens + self.cache_read + self.cache_write) / self.api_calls if self.api_calls else 0.0


def _head(block: dict) -> str:
    """The first line of what a tool call was asked to do."""
    args = block.get("input") or {}
    for key in ("command", "file_path", "pattern", "path", "prompt", "description"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().splitlines()[0]
    return ", ".join(sorted(args))[:88]


def tool_calls(rows: list[dict]) -> list[Call]:
    """One `Call` per tool_use, with its result's timing, size and error flag."""
    start = next((t for t in (_stamp(r) for r in rows) if t is not None), None)
    calls: dict[str, Call] = {}
    order: list[Call] = []
    for row in rows:
        if row.get("type") != "assistant":
            continue
        content = (row.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_use":
                continue
            began = _stamp(row)
            call = Call(index=len(order) + 1, tool=block.get("name", "?"),
                        head=_head(block),
                        offset=None if began is None or start is None else began - start)
            call._began = began  # noqa: SLF001 - local join key, not part of the record
            calls[block.get("id", "")] = call
            order.append(call)

    for row in rows:
        if row.get("type") != "user":
            continue
        content = (row.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_result":
                continue
            call = calls.get(block.get("tool_use_id", ""))
            if call is None:
                continue
            call.error = bool(block.get("is_error"))
            body = block.get("content")
            call.out_chars = len(body if isinstance(body, str) else json.dumps(body or ""))
            ended, began = _stamp(row), getattr(call, "_began", None)
            if ended is not None and began is not None:
                call.duration = ended - began
    return order


def usage(rows: list[dict]) -> Usage:
    """Sum the bill **once per `message.id`, last record wins**.

    Every record of one API call repeats that call's usage, so summing records
    multiplies it by however many content blocks the harness wrote out.  Taking
    the last record rather than the first is deliberate: a streamed call's
    earlier records can carry a partial `output_tokens`.
    """
    per_call: dict[str, dict] = {}
    models: dict[str, str] = {}
    for row in rows:
        if row.get("type") != "assistant":
            continue
        message = row.get("message") or {}
        ident = message.get("id")
        if not ident:
            continue
        if message.get("usage"):
            per_call[ident] = message["usage"]
        if message.get("model"):
            models[ident] = message["model"]

    stamps = [t for t in (_stamp(r) for r in rows) if t is not None]
    out = Usage(api_calls=len(per_call),
                wall_seconds=(max(stamps) - min(stamps)) if stamps else None,
                models=Counter(models.values()))
    for u in per_call.values():
        out.input_tokens += u.get("input_tokens", 0)
        out.cache_read += u.get("cache_read_input_tokens", 0)
        out.cache_write += u.get("cache_creation_input_tokens", 0)
        out.output_tokens += u.get("output_tokens", 0)
    return out


@dataclass
class Trace:
    """What the shim saw, from inside the run's own interpreters."""

    calls: Counter = field(default_factory=Counter)
    outer: Counter = field(default_factory=Counter)
    seconds: dict[str, float] = field(default_factory=dict)
    processes: int = 0
    exits: int = 0
    import_seconds: float = 0.0
    process_wall: float = 0.0
    kwargs: dict[str, Counter] = field(default_factory=dict)
    missing: set[str] = field(default_factory=set)

    @property
    def fit_seconds(self) -> float:
        """Refinement seconds, from where each fit ran (never from a command).

        Outermost calls only.  `rx.refine` *is* `Refinement.fit` one frame down
        and `refine_sequential` *is* `SequentialRefinement.fit`, so a sum over
        names counts every fit twice; `seconds` therefore holds `depth == 0`
        rows and nothing else.
        """
        return sum(v for k, v in self.seconds.items() if k in FIT_CALLS)

    @property
    def fit_calls(self) -> int:
        return sum(v for k, v in self.outer.items() if k in FIT_CALLS)

    @property
    def floor_share(self) -> float | None:
        """R8: import plus kernel load against the processes' whole wall clock.

        The denominator comes from `atexit`, which does not run under SIGKILL or
        `os._exit`: a backgrounded chain the agent killed contributes its
        `import_dt` to the numerator and nothing here, so the share is an
        **over**-estimate whenever `exits` is short of `processes`.  Reported
        rather than clamped — `render` says so — because a clamped share and a
        true one read alike.
        """
        return self.import_seconds / self.process_wall if self.process_wall else None


def trace(rows: list[dict]) -> Trace:
    out = Trace()
    for row in rows:
        event = row.get("event")
        if event == "call":
            name = row.get("name", "?")
            out.calls[name] += 1
            if not row.get("depth"):
                out.outer[name] += 1
                out.seconds[name] = out.seconds.get(name, 0.0) + float(row.get("dt") or 0.0)
            seen = out.kwargs.setdefault(name, Counter())
            for key in row.get("kwargs") or ():
                seen[key] += 1
            for key, value in (row.get("values") or {}).items():
                seen[f"{key}={value}"] += 1
        elif event == "import":
            out.processes += 1
            out.import_seconds += float(row.get("import_dt") or 0.0)
            out.missing.update(row.get("missing") or ())
        elif event == "exit":
            out.exits += 1
            out.process_wall += float(row.get("wall") or 0.0)
    return out


def render(rows: list[dict], trace_rows: list[dict] | None = None) -> str:
    calls = tool_calls(rows)
    bill = usage(rows)
    lines = ["   #  offset    dur    chars     tool       head",
             *(c.line() for c in calls), ""]

    by_tool = Counter(c.tool for c in calls)
    errors = sum(1 for c in calls if c.error)
    # A call whose result never arrived is neither, and folding it into "not
    # errored" is the defaulted `False` this module refuses one rank up.
    unknown = sum(1 for c in calls if c.error is None)
    lines.append(f"{len(calls)} tool calls "
                 f"({', '.join(f'{n} {t}' for t, n in by_tool.most_common())}), "
                 f"{errors} errored"
                 + (f", {unknown} unanswered" if unknown else ""))
    wall = f"{bill.wall_seconds / 60:.1f} min" if bill.wall_seconds else "?"
    lines.append(f"{bill.api_calls} API calls, {wall} wall, "
                 f"{bill.cache_read / 1e6:.2f} M cache-read, "
                 f"{bill.cache_write / 1e3:.0f} k cache-write, "
                 f"{bill.output_tokens / 1e3:.0f} k output, "
                 f"mean context {bill.mean_context / 1e3:.0f} k")
    if bill.models:
        lines.append("models: " + ", ".join(f"{m} ×{n}" for m, n in bill.models.most_common()))

    if trace_rows is not None:
        seen = trace(trace_rows)
        lines += ["", f"{seen.processes} traced interpreter starts, "
                      f"{sum(seen.calls.values())} traced calls"]
        lines.append(f"refinement {seen.fit_seconds:.1f} s in {seen.fit_calls} fit calls"
                     + (f" ({seen.fit_seconds / bill.wall_seconds:.1%} of wall)"
                        if bill.wall_seconds else ""))
        if seen.fit_calls:
            # Two decimals: one rounds a real ratio (37 Bash over 852 fits) to
            # `0.0`, which reads as "no Bash at all" — and the ratio is smallest
            # exactly where the surface worked.
            lines.append(f"{by_tool.get('Bash', 0) / seen.fit_calls:.2f} Bash calls per fit")
        if seen.floor_share is not None:
            lines.append(f"per-process floor {seen.import_seconds:.1f} s of "
                         f"{seen.process_wall:.1f} s ({seen.floor_share:.1%})"
                         + ("" if seen.exits >= seen.processes else
                            f" — OVERSTATED: {seen.processes - seen.exits} traced "
                            "process(es) left no exit row, so their wall clock is "
                            "missing from the denominator"))
        for name, n in sorted(seen.calls.items()):
            marks = seen.kwargs.get(name) or Counter()
            detail = " [" + ", ".join(k for k, _ in marks.most_common(6)) + "]" if marks else ""
            lines.append(f"    {name:<34} {n:4d}  {seen.seconds.get(name, 0.0):7.1f} s{detail}")
        if seen.missing:
            lines.append("targets that did not resolve: " + ", ".join(sorted(seen.missing)))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    trace_rows = load(argv[2]) if len(argv) > 2 else None
    print(render(load(argv[1]), trace_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
