"""What a WP session's tokens cost, and what lanes would save or did save.

A *lane* is a subagent that does one checklist item while the main session
waits, then checks the diff and commits it (`/wp-start` step 6c).  This script reads
Claude Code's transcripts under ~/.claude/projects and answers three ways:

    python3 .claude/hooks/session_usage.py context SESSION_ID   # the main context now
    python3 .claude/hooks/session_usage.py lanes SESSION_ID     # measure a session that ran lanes
    python3 .claude/hooks/session_usage.py baseline [--u N] [--mo N] [--d N]

The session id is the name of the session's scratchpad directory.  `baseline`
reads every WP session of this repository on this machine (a session that made
a `WP-NNNN:` commit), splits each at its WP commits into items, and replays the
items under lane policies.  `lanes` measures a session that dispatched lanes,
whose dispatches carry the description `lane: <item> ~N` and whose decisions
carry a line `lanes: keep|lane <item> ~N`.  It prints the three numbers the
replay had to assume (what a lane re-reads, how many main requests a lane
costs, what it leaves in the main context), so `baseline --u --mo --d` can be
re-run with them.

Requests are de-duplicated by message id, because one API response is written
as several lines.  Every model is priced at its family's current generation
(PRICES), so an August session on Opus 5 is a counterfactual bill at Opus 5.5
rates.  The record is `docs/milestones/process.md` § Lanes within a WP.
Stdlib only, like the other scripts here.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import statistics
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = Path.home() / ".claude" / "projects"
# $/MTok: input, output, cache read, 5-minute cache write, 1-hour cache write.
PRICES = {
    "opus": (4.00, 20.00, 0.20, 5.00, 8.00),
    "sonnet": (2.00, 10.00, 0.20, 2.50, 4.00),
    "haiku": (1.00, 5.00, 0.10, 1.25, 2.00),
}
BYTES_PER_TOKEN = 2.5       # through Read, line numbers included (process.md)
WP_FILE_TOKENS = 6_300      # the median WP file, 15.7 KB, which every lane reads
LANE_BASE = 64_000          # an Opus 5.5 agent's first request here (median)
DISPATCH_OUT = 2_000        # output tokens the main session spends on one dispatch prompt
COMMIT = re.compile(r"git (?:-C \S+ )?commit")
WP_MSG = re.compile(r"WP-(\d{4}):")
# A line of its own, though markdown may wrap it: `/wp-start` step 6c shows the
# form in backticks, and a bullet, quote or bold copy of it is still the decision.
DECISION = re.compile(r"^[ \t>*_`-]*lanes: (keep|lane) (.+?) ~(\d+)\b", re.M)
LANE_PREFIX = "lane:"
EDITS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
BASH_CLASSES = (
    ("pytest", r"pytest"),
    ("git diff/show/log", r"git (-C \S+ )?(diff|show|log)"),
    ("grep/rg", r"(^|\| *|&& *)(grep|rg) "),
    ("cat/sed/awk/head", r"(^|\| *|&& *)(cat|sed|awk|head|tail) "),
)


def family(model: str) -> str:
    return next((k for k in PRICES if k in model), "opus")


@dataclass
class Request:
    ts: str
    model: str
    inp: int
    read: int
    write5: int
    write1h: int
    out: int

    @property
    def context(self) -> int:
        return self.inp + self.read + self.write5 + self.write1h

    def parts(self) -> tuple[float, float, float]:
        """Dollars of cache reads, of writes (input included) and of output."""
        i, o, r, w5, w1 = PRICES[family(self.model)]
        return (self.read * r / 1e6,
                (self.inp * i + self.write5 * w5 + self.write1h * w1) / 1e6,
                self.out * o / 1e6)

    def cost(self) -> float:
        return sum(self.parts())


@dataclass
class Transcript:
    path: Path
    requests: list = field(default_factory=list)      # Request, by time
    msg_context: dict = field(default_factory=dict)   # message id -> its request's context
    reads: list = field(default_factory=list)         # (ts, path, bytes) per Read
    edits: list = field(default_factory=list)         # (ts, path, bytes) per edit
    commits: list = field(default_factory=list)       # ts of each WP commit
    agents: list = field(default_factory=list)        # dicts: ts, description, msg, agent_id
    decisions: list = field(default_factory=list)     # (ts, keep|lane, item, estimate)
    fill: Counter = field(default_factory=Counter)    # bytes entering the context, by source


def _bash_class(cmd: str) -> str:
    return next((name for name, pat in BASH_CLASSES if re.search(pat, cmd)), "bash other")


def parse(path: Path, sidechain: bool = False) -> Transcript:
    """Read one transcript.  A main transcript skips sidechain lines; an
    agent's own transcript is all sidechain, so it is read with `sidechain`."""
    t = Transcript(Path(path))
    pending: dict = {}
    by_use: dict = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("isSidechain") and not sidechain:
            continue
        m = e.get("message")
        if not isinstance(m, dict):
            continue
        ts = e.get("timestamp", "")
        blocks = m.get("content") if isinstance(m.get("content"), list) else []
        if m.get("role") == "assistant":
            mid = m.get("id")
            u = m.get("usage")
            if isinstance(u, dict) and mid not in t.msg_context:
                cc = u.get("cache_creation") or {}
                w5 = cc.get("ephemeral_5m_input_tokens", 0) or 0
                w1 = cc.get("ephemeral_1h_input_tokens", 0) or 0
                rest = (u.get("cache_creation_input_tokens", 0) or 0) - w5 - w1
                if rest > 0:   # no split recorded: the main session writes at 1 h, an agent at 5 min
                    w5, w1 = (w5 + rest, w1) if sidechain else (w5, w1 + rest)
                req = Request(ts, m.get("model", ""), u.get("input_tokens", 0) or 0,
                              u.get("cache_read_input_tokens", 0) or 0, w5, w1,
                              u.get("output_tokens", 0) or 0)
                t.requests.append(req)
                t.msg_context[mid] = req.context
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    text = b.get("text", "")
                    t.fill["(model) text"] += len(text)
                    t.decisions += [(ts, a, item.strip(), int(n)) for a, item, n in DECISION.findall(text)]
                if b.get("type") != "tool_use":
                    continue
                name, inp, uid = b.get("name"), b.get("input") or {}, b.get("id")
                t.fill["(model) tool inputs"] += len(json.dumps(inp))
                kind = name
                if name == "Read":
                    pending[uid] = ("Read", ts, inp.get("file_path", ""))
                    continue
                if name in EDITS:
                    t.edits.append((ts, inp.get("file_path", ""), len(json.dumps(inp))))
                elif name == "Bash":
                    cmd = inp.get("command", "")
                    kind = _bash_class(cmd)
                    if COMMIT.search(cmd) and WP_MSG.search(cmd):
                        t.commits.append(ts)
                elif name in ("Agent", "Task"):
                    by_use[uid] = dict(ts=ts, description=inp.get("description", ""),
                                       msg=mid, agent_id=None)
                    t.agents.append(by_use[uid])
                pending[uid] = (kind, ts, None)
        else:
            for b in blocks:
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                kind, used_at, fpath = pending.pop(b.get("tool_use_id"), ("?", ts, None))
                body = b.get("content")
                size = len(body) if isinstance(body, str) else len(json.dumps(body))
                t.fill[kind] += size
                if kind == "Read":
                    t.reads.append((used_at, fpath, size))
                if b.get("tool_use_id") in by_use and isinstance(e.get("toolUseResult"), dict):
                    by_use[b["tool_use_id"]]["agent_id"] = e["toolUseResult"].get("agentId")
    t.requests.sort(key=lambda r: r.ts)
    t.commits.sort()
    return t


def segments(t: Transcript) -> list[tuple[int, list[int]]]:
    """(index, contexts) for each non-empty item, the requests between WP commits.

    A request belongs to the item whose commit it precedes or makes; the index
    is the item's position among all items, so per-item facts line up."""
    groups: list[list[int]] = [[] for _ in range(len(t.commits) + 1)]
    for r in t.requests:
        groups[bisect.bisect_left(t.commits, r.ts)].append(r.context)
    return [(k, g) for k, g in enumerate(groups) if g]


def carried(t: Transcript) -> list[float]:
    """Per item, the tokens a lane would re-read that the main session held.

    Files the item edits without reading them itself, which an earlier item
    read (largest earlier read of each).  Code read earlier only to understand
    the problem is invisible here; the replay's `u` stands for it."""
    n = len(t.commits) + 1
    reads: list[dict] = [{} for _ in range(n)]
    edits: list[set] = [set() for _ in range(n)]
    for ts, f, size in t.reads:
        d = reads[bisect.bisect_left(t.commits, ts)]
        d[f] = max(d.get(f, 0), size)
    for ts, f, _ in t.edits:
        edits[bisect.bisect_left(t.commits, ts)].add(f)
    out, earlier = [], {}
    for k in range(n):
        out.append(sum(earlier[f] for f in edits[k] if f in earlier and f not in reads[k]) / BYTES_PER_TOKEN)
        for f, size in reads[k].items():
            earlier[f] = max(earlier.get(f, 0), size)
    return out


def replay(t: Transcript, lane_if, u: float, mo: int = 5, d: int = 8_000,
           redo: float = 0.0, extra: int = 3, tally: Counter | None = None) -> float:
    """Reads and writes of one session in dollars, with the items `lane_if(M, n)`
    picks sent to lanes.  M is the counterfactual main context at the item's
    start and n the item's measured request count.

    A kept item pays its measured growth on top of M.  A laned item runs from
    LANE_BASE + its carried files + the WP file + u, plus `extra` orientation
    requests; the main session pays `mo` requests at M, writes `d` tokens and
    carries them, and spends one dispatch prompt.  With nothing laned, the read
    term is every request's context at the read price, so it is the session's
    own cache reads plus what each request wrote.  Writes are modelled as each
    item's growth, so idle-gap rewrites are left out."""
    _, out, r, w5, w1 = PRICES["opus"]
    segs, rk = segments(t), carried(t)
    total, m = 0.0, segs[0][1][0]
    for j, (k, seg) in enumerate(segs):
        a = seg[0]
        grow = max(0, max(seg) - a)
        step = (segs[j + 1][1][0] if j + 1 < len(segs) else seg[-1]) - a
        if lane_if(m, len(seg)):
            base = LANE_BASE + rk[k] + WP_FILE_TOKENS + u
            lane = (sum(base + max(0, c - a) for c in seg) + extra * base) * r + (base + grow) * w5
            total += lane * (1 + redo) + mo * m * r + d * w1 + DISPATCH_OUT * out
            m += d
            if tally is not None:
                tally["laned"] += 1
        else:
            total += sum(m + c - a for c in seg) * r + grow * w1
            m += step
    return total / 1e6


# -- finding transcripts -------------------------------------------------------

def _repo_dirs() -> list[Path]:
    """This repository's project directories: the main checkout's and its worktrees'."""
    common = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute",
                             "--git-common-dir"], capture_output=True, encoding="utf-8", errors="replace").stdout.strip()
    slug = re.sub(r"[/.]", "-", str(Path(common).parent))
    return [p for p in PROJECTS.glob(slug + "*")
            if p.name == slug or p.name.startswith(slug + "--claude-worktrees-")]


def subagent_dirs(main: Path) -> list[Path]:
    """Where the agents of the session whose transcript is ``main`` were written.

    Beside ``main`` until the session enters a worktree.  After that its own
    transcript stays where it started while its agents land under the
    worktree's project directory, so a lane session that enters its tree
    second, as /wp-start says to, found none of its five lanes (WP-1531).
    """
    dirs = [main.parent / main.stem / "subagents"]
    dirs += [d for d in PROJECTS.glob(f"*/{main.stem}/subagents") if d not in dirs]
    return [d for d in dirs if d.is_dir()]


def find_main(session_id: str) -> Path:
    hits = sorted(PROJECTS.glob(f"*/{session_id}.jsonl"), key=lambda p: p.stat().st_size)
    if not hits:
        sys.exit(f"no transcript {session_id}.jsonl under {PROJECTS}")
    return hits[-1]


def wp_sessions() -> list[Transcript]:
    """Every main transcript here that made a WP commit and 20+ requests.  A
    session that moved into a worktree is filed twice; the larger copy wins."""
    files: dict = {}
    for d in _repo_dirs():
        for p in d.glob("*.jsonl"):
            if p.stat().st_size > files.get(p.name, (0, None))[0]:
                files[p.name] = (p.stat().st_size, p)
    out = [parse(p) for _, p in files.values()]
    return sorted((t for t in out if t.commits and len(t.requests) >= 20),
                  key=lambda t: t.requests[0].ts)


# -- reports ---------------------------------------------------------------------

def _q(xs, frac):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(frac * len(xs)))]


def _k(x):
    return f"{x / 1000:.0f}K"


POLICIES = (
    ("lane every item", lambda m, n: True),
    ("lane when main > 200K", lambda m, n: m > 200_000),
    ("lane when main > 150K and item >= 20 requests", lambda m, n: m > 150_000 and n >= 20),
)


def baseline(us: list[float], mo: int, d: int) -> None:
    ts = wp_sessions()
    reqs = [r for t in ts for r in t.requests]
    rd, wr, out = (sum(r.parts()[i] for r in reqs) for i in range(3))
    floor = sum(len(t.requests) * t.requests[0].context for t in ts) * PRICES["opus"][2] / 1e6
    print(f"{len(ts)} WP sessions, {ts[0].requests[0].ts[:10]} to {ts[-1].requests[-1].ts[:10]},"
          f" {len(reqs)} requests, {sum(len(segments(t)) for t in ts)} items")
    print(f"bill ${rd + wr + out:.0f}: cache reads {rd / (rd + wr + out):.0%},"
          f" writes and input {wr / (rd + wr + out):.0%}, output {out / (rd + wr + out):.0%}")
    print(f"reads if each request carried only its session's first context: {floor / rd:.0%} of actual")
    n = [len(t.requests) for t in ts]
    peak = [max(r.context for r in t.requests) for t in ts]
    first = [t.requests[0].context for t in ts]
    print(f"requests per session: median {statistics.median(n):.0f}, p10 {_q(n, .1)}, p90 {_q(n, .9)};"
          f" peak context median {_k(statistics.median(peak))};"
          f" first context {_k(statistics.median(first[:10]))} (first ten) to"
          f" {_k(statistics.median(first[-10:]))} (last ten)")
    items = [seg for t in ts for _, seg in segments(t)]
    grow = [max(s) - s[0] for s in items]
    print(f"per item: requests median {statistics.median([len(s) for s in items]):.0f}"
          f" p90 {_q([len(s) for s in items], .9)}; growth median {_k(statistics.median(grow))}"
          f" p90 {_k(_q(grow, .9))}; starting context median {_k(statistics.median([s[0] for s in items]))}")
    rk = [x for t in ts for x in carried(t)[1:]]
    print(f"carried files a lane would re-read: median {_k(statistics.median(rk))},"
          f" p90 {_k(_q(rk, .9))}")
    fill = sum((t.fill for t in ts), Counter())
    total = sum(fill.values())
    print("what fills the main context: " + ", ".join(
        f"{k} {v / total:.0%}" for k, v in fill.most_common(7)))
    bases: dict = {}
    for t in ts:
        for p in (p for d in subagent_dirs(t.path) for p in d.glob("*.jsonl")):
            a = parse(p, sidechain=True)
            if len(a.requests) >= 2:
                r0 = a.requests[0]
                bases.setdefault(r0.model.replace("claude-", ""), []).append((r0.context, r0.read))
    print("agent first request: " + ", ".join(
        f"{m} {_k(statistics.median(c for c, _ in v))} (n={len(v)},"
        f" {statistics.median(rd / c for c, rd in v):.0%} cached)"
        for m, v in sorted(bases.items()) if len(v) >= 5))

    ref = sum(replay(t, lambda m, n: False, 0) for t in ts)
    print(f"\nreplay (modelled reads and writes ${ref:.0f}; mo={mo}, d={_k(d)}),"
          " change by policy (negative is a saving):")
    print("| policy | items laned | " + " | ".join(f"u = {_k(u)}" for u in us) + " |")
    print("|---|---|" + "---|" * len(us))
    rows = list(POLICIES) + [
        ("  same, mo doubled and d = 20K", POLICIES[2][1], dict(mo=2 * mo, d=20_000)),
        ("  same, one lane in five redone", POLICIES[2][1], dict(redo=0.2)),
    ]
    for name, pol, *kw in rows:
        args = dict(mo=mo, d=d) | (kw[0] if kw else {})
        cells, tally = [], Counter()
        for j, u in enumerate(us):
            new = sum(replay(t, pol, u, **args, tally=tally if j == 0 else None) for t in ts)
            cells.append(f"{(new - ref) / ref:+.0%}")
        print(f"| {name} | {tally['laned']} | " + " | ".join(cells) + " |")
    u = us[len(us) // 2]
    print(f"\nby the session's peak context (selective policy, u = {_k(u)}; negative is a saving):")
    for lo, hi in ((0, 300_000), (300_000, 450_000), (450_000, 10**9)):
        sel = [t for t in ts if lo <= max(r.context for r in t.requests) < hi]
        a = sum(replay(t, lambda m, n: False, 0) for t in sel)
        b = sum(replay(t, POLICIES[2][1], u, mo=mo, d=d) for t in sel)
        # an empty band (a fresh container holds one session) has nothing to save
        change = f"{(b - a) / a:+.0%}" if a else "n/a"
        print(f"  {_k(lo)}-{_k(hi) if hi < 10**9 else 'up'}: {len(sel)} sessions, change {change}")
    _, o, r, w5, w1 = PRICES["opus"]
    print("\nitem length (requests) at which a lane pays, by main context:")
    for base in (80_000, 110_000):
        cells = []
        for m in (150_000, 200_000, 250_000, 300_000, 400_000, 500_000):
            fixed = base * (w5 + 3 * r) + mo * m * r + d * w1 + DISPATCH_OUT * o
            cells.append(f"{_k(m)}: {fixed / ((m - base) * r):.0f}")
        print(f"  lane base {_k(base)}  " + "  ".join(cells))


def measure_lanes(main: Path) -> dict:
    """Per lane and per kept item of one session that ran lanes, measured."""
    t = parse(main)
    subdirs = subagent_dirs(main)
    _, o, r, w5, w1 = PRICES["opus"]
    dispatches = sorted((a for a in t.agents if (a["description"] or "").startswith(LANE_PREFIX)),
                        key=lambda a: a["ts"])
    lanes, labels = [], Counter()
    for i, a in enumerate(dispatches):
        label = a["description"][len(LANE_PREFIX):].strip()
        est = re.search(r"~(\d+)\s*$", label)
        item = re.sub(r"\s*~\d+\s*$", "", label)
        path = next((p for p in (d / f"agent-{a['agent_id']}.jsonl" for d in subdirs)
                     if p.exists()), None)
        if not a["agent_id"] or path is None:
            continue
        sub = parse(path, sidechain=True)
        if not sub.requests:
            continue
        nxt = dispatches[i + 1]["ts"] if i + 1 < len(dispatches) else "~"
        end = min(next((c for c in t.commits if c > a["ts"]), "~"), nxt)
        window = [q for q in t.requests if a["ts"] < q.ts <= end]
        after = sum(1 for q in t.requests if q.ts > end)
        m = t.msg_context.get(a["msg"], 0)
        held = {f for ts, f, _ in t.reads if ts < a["ts"]}
        ctx = [q.context for q in sub.requests]
        base, grow = ctx[0], max(ctx) - ctx[0]
        carried_d = max(0, window[-1].context - m) if window else 0
        lane_cost = sum(q.cost() for q in sub.requests)
        main_cost = sum(q.cost() for q in window)
        in_session = (sum(m + c - base for c in ctx) * r + grow * w1
                      + sum(q.out for q in sub.requests) * o + grow * after * r) / 1e6
        laned = lane_cost + main_cost + carried_d * after * r / 1e6
        lanes.append(dict(
            item=item, estimate=int(est.group(1)) if est else None, requests=len(ctx),
            main_context=m, base=base, peak=max(ctx),
            reread=sum(b for _, f, b in sub.reads if f in held) / BYTES_PER_TOKEN,
            read=sum(b for *_, b in sub.reads) / BYTES_PER_TOKEN,
            main_requests=len(window), carried=carried_d,
            fixes=sum(1 for ts, *_ in t.edits if a["ts"] < ts <= end),
            redo=labels[item], model=sub.requests[0].model.replace("claude-", ""),
            lane_cost=lane_cost, main_cost=main_cost, in_session=in_session, saved=in_session - laned))
        labels[item] += 1
    kept = []
    for ts, action, item, est in t.decisions:
        if action != "keep":
            continue
        end = next((c for c in t.commits if c > ts), "~")
        kept.append(dict(item=item, estimate=est, requests=sum(1 for q in t.requests if ts < q.ts <= end),
                         main_context=max((q.context for q in t.requests if q.ts <= ts), default=0)))
    return dict(main=t, lanes=lanes, kept=kept)


def lanes_report(session_id: str) -> None:
    res = measure_lanes(find_main(session_id))
    t, lanes, kept = res["main"], res["lanes"], res["kept"]
    main_cost = sum(q.cost() for q in t.requests)
    lane_cost = sum(x["lane_cost"] for x in lanes)
    print(f"session {session_id}: main {len(t.requests)} requests, peak {_k(max(q.context for q in t.requests))},"
          f" ${main_cost:.2f}; {len(lanes)} lanes ${lane_cost:.2f}; {len(t.commits)} WP commits")
    if not lanes:
        print("no lane dispatches found (description must start with 'lane:')")
    else:
        print("\n| lane | est | requests | main at dispatch | lane base | re-read | main requests"
              " | left in main | main edits after | redo | model | lane $ | main $ | in-session $ | saved $ |")
        print("|---" * 15 + "|")
        for x in lanes:
            print(f"| {x['item']} | {x['estimate'] or '?'} | {x['requests']} | {_k(x['main_context'])}"
                  f" | {_k(x['base'])} | {_k(x['reread'])} of {_k(x['read'])} | {x['main_requests']}"
                  f" | {_k(x['carried'])} | {x['fixes']} | {x['redo']} | {x['model']}"
                  f" | {x['lane_cost']:.2f} | {x['main_cost']:.2f} | {x['in_session']:.2f} | {x['saved']:+.2f} |")
    if kept:
        print("\n| kept item | est | requests | main at decision |\n|---|---|---|---|")
        for x in kept:
            print(f"| {x['item']} | {x['estimate']} | {x['requests']} | {_k(x['main_context'])} |")
    if lanes:
        med = lambda key: statistics.median(x[key] for x in lanes)  # noqa: E731
        ratio = [x["requests"] / x["estimate"] for x in lanes + kept if x["estimate"]]
        ratio_txt = f"{statistics.median(ratio):.2f}" if ratio else "?"
        saved = sum(x["saved"] for x in lanes)
        print(f"\nmeasured: re-read median {_k(med('reread'))}, main requests per lane {med('main_requests'):.0f},"
              f" left in main {_k(med('carried'))}, actual/estimated requests {ratio_txt}")
        print(f"trial row: | {t.requests[0].ts[:10]} | {session_id[:8]} | {len(lanes)} | {len(kept)}"
              f" | {_k(med('reread'))} | {med('main_requests'):.0f} | {_k(med('carried'))} | {ratio_txt}"
              f" | {sum(x['fixes'] > 0 for x in lanes)} / {sum(x['redo'] > 0 for x in lanes)}"
              f" | {saved:+.2f} | {saved / (main_cost + lane_cost + saved):+.0%} |")
        print(f"replay with these: python3 .claude/hooks/session_usage.py baseline"
              f" --u {med('reread'):.0f} --mo {med('main_requests'):.0f} --d {med('carried'):.0f}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("context", "lanes"):
        sub.add_parser(name).add_argument("session_id")
    b = sub.add_parser("baseline")
    b.add_argument("--u", type=float, action="append",
                   help="tokens a lane re-reads beyond its edited files (repeatable; default 0, 20K, 40K)")
    b.add_argument("--mo", type=int, default=5, help="main-session requests per lane")
    b.add_argument("--d", type=int, default=8_000, help="tokens a lane leaves in the main context")
    args = ap.parse_args(argv)
    if args.cmd == "context":
        print(parse(find_main(args.session_id)).requests[-1].context)
    elif args.cmd == "lanes":
        lanes_report(args.session_id)
    else:
        baseline(args.u or [0, 20_000, 40_000], args.mo, args.d)


if __name__ == "__main__":
    main()
