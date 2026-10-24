#!/usr/bin/env python3
"""The open issues, cross-referenced against the tree: ``/issue-review``'s first act.

Three network calls and one ``git log``, then everything else is local. One
file per open issue lands in the output directory (title, dates, author,
labels, the cross-references, the body, every comment), and one table goes to
stdout. The skill reads the files and works from the table.

Why a script rather than the ``gh`` calls written into the skill: the triage
of 2026-09-15 lost 16 of 21 issue bodies to ``gh issue view --comments``,
which prints the comments and drops the body, and then spent four retries on
the worktree guard, which refuses a ``for`` loop over numbers and a shell
variable in a path. One plain ``python3`` command is the shape the guard
accepts, and the cross-references are what the skill's placing step needs on
every issue anyway.

The cross-references, each a column of the table:

* **WPs citing it**, with each WP's status glyph. The citation is the triage
  record. Every WP file names the issues it answers as ``#N``, the triage's
  own audit greps for exactly that, and ``wp_claim.py`` reads the same text
  to connect a contributor's PR to a WP. So an issue no WP or ROADMAP line
  cites has not been triaged, and the table says ``untriaged``.
* **Open PRs citing it**, forks included, through ``wp_claim.open_prs``: the
  fix may be in flight on someone else's machine.
* **Merged PRs and commits on ``origin/main`` citing it.** A fix lands
  without its issue closing more often than not: a closing keyword written in
  backticks closes nothing (``/wp-handover`` step 11), and WP-1310 filed
  three defects of which two had been fixed before it was written. Issue
  state is no evidence either way, so the table carries the evidence. A
  reference that touched only the planning record (``PLACEMENT``: WP files,
  the ROADMAP, milestone and release records, ``.claude/``, a ``CLAUDE.md``,
  and the test file that holds the ROADMAP's size cap) is a *placement*,
  since a triage PR cites every issue it files, and goes to the per-issue
  file rather than this column. With placements counted, 65 of 86 open
  issues carried a "landed" reference on 2026-09-21 and the column said
  nothing. A manual or skill change is not a placement: for a docs issue it
  is the fix. Merge commits are skipped, since the PR they merge is a
  reference of its own and ``--name-only`` lists no files for them.

Issue and pull-request numbers share one sequence on GitHub, so ``#408`` in a
merge commit's subject can never be an open issue's number, and the ``#N``
regex needs no disambiguation.

Stdlib only, run with ``python3`` from PATH, like the hooks it sits beside: it
runs before the round's venv exists. Every ``gh`` failure is a sentence, never
an empty table, since "no PRs" and "could not look" must not read alike.

Usage::

    python3 .claude/skills/issue-review/backlog.py OUT_DIR [N ...]

``OUT_DIR`` is spelled out (the guard refuses a variable in a path); with
issue numbers given, only those are written and tabulated, though every open
issue is still fetched, since ``gh issue list`` cannot filter by number.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple, Optional

_HOOKS = str(Path(__file__).resolve().parents[2] / "hooks")  # appended, never
if _HOOKS not in sys.path:  # inserted: a loose script must not shadow stdlib
    sys.path.append(_HOOKS)
import wp_claim  # noqa: E402  (a sibling hook, not a package)

ISSUE_RE = wp_claim._ISSUE_RE  # ``#N`` with a word boundary, the one spelling
STATUS_RE = re.compile(r"^Milestone:.*?Status:\s*(\S)", re.MULTILINE)
UNTRIAGED = "untriaged"
# The maintainer and the recurring contributor (Michael Gaultois).  An issue or
# PR by anyone else is named to the maintainer before any public act on it,
# here and in `/pr-review`, which reads this list (2026-10-11).
KNOWN_AUTHORS = frozenset({"yue-here", "mustachefeeling"})
# Paths a placement touches and a fix does not.  A prefix matches a directory
# or a whole file; the suffix is every CLAUDE.md.
PLACEMENT = (
    "docs/wp/",
    "docs/ROADMAP.md",
    "docs/DESIGN.md",
    "docs/milestones/",
    "docs/releases/",
    ".claude/",
    "tests/test_docs_consistency.py",
)


class Issue(NamedTuple):
    number: int
    title: str
    author: str
    created: str  # YYYY-MM-DD
    updated: str
    labels: tuple
    body: str
    comments: tuple  # (author, timestamp, body)
    url: str


class Reference(NamedTuple):
    """Something on GitHub or on ``origin/main`` whose text cites issues."""

    kind: str  # "open PR", "merged PR", "commit"
    label: str  # "#385 (mustachefeeling)", "PR #292 (2026-09-10)", "5c9a72e2 2026-09-18 WP-1434: …"
    cited: frozenset  # the issue numbers its text names
    placement: bool = False  # touched nothing outside PLACEMENT


class Row(NamedTuple):
    issue: Issue
    wps: tuple  # (wp, glyph), sorted by WP
    roadmap: bool  # docs/ROADMAP.md names it (a fence, or a row's evidence)
    open_prs: tuple  # labels
    landed: tuple  # merged PR and commit labels outside PLACEMENT, merged PRs first
    placed: tuple  # the placements: the triage record, kept out of the table

    @property
    def triaged(self) -> bool:
        return bool(self.wps) or self.roadmap


# --------------------------------------------------------------------------- #
# Pure: the cross-reference and its renderings.  Tested without a network.
# --------------------------------------------------------------------------- #


def cited_numbers(text: str) -> frozenset:
    """Every ``#N`` in *text*, as ints, on the hook's own regex."""
    return frozenset(int(n) for n in ISSUE_RE.findall(text or ""))


def is_placement(paths: list) -> bool:
    """True when every path is in the planning record; False on an empty list."""
    return bool(paths) and all(
        p.startswith(PLACEMENT) or p.endswith("CLAUDE.md") for p in paths
    )


def wp_statuses(root: Path) -> dict:
    """Each WP's status glyph, off its ``Milestone: … · Status: <glyph>`` line."""
    out: dict = {}
    for path in sorted((root / "docs" / "wp").glob("[0-9][0-9][0-9][0-9]-*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = STATUS_RE.search(text)
        out[path.name[:4]] = m.group(1) if m else "?"
    return out


def cross_reference(
    issues: list,
    citations: dict,
    statuses: dict,
    roadmap_cited: frozenset,
    references: list,
) -> list:
    """One ``Row`` per issue, in issue-number order."""
    rows = []
    for issue in sorted(issues, key=lambda i: i.number):
        n = issue.number
        wps = tuple(
            (wp, statuses.get(wp, "?"))
            for wp, cited in sorted(citations.items())
            if n in cited
        )
        open_prs = tuple(r.label for r in references if r.kind == "open PR" and n in r.cited)
        landed, placed = [], []
        for kind in ("merged PR", "commit"):
            for r in references:
                if r.kind == kind and n in r.cited:
                    (placed if r.placement else landed).append(r.label)
        rows.append(Row(issue, wps, n in roadmap_cited, open_prs, tuple(landed), tuple(placed)))
    return rows


def _age(created: str, today: Optional[date] = None) -> int:
    today = today or date.today()
    y, m, d = (int(x) for x in created.split("-"))
    return (today - date(y, m, d)).days


def table(rows: list, today: Optional[date] = None) -> str:
    """The backlog, one line an issue, in the order the skill ranks from."""
    head = f"{'#':>4}  {'age':>4}  {'by':<16} {'c':>2}  {'labels':<14} {'WPs':<30} {'open PR':<22} landed"
    lines = [head]
    for r in rows:
        i = r.issue
        wps = " ".join(f"{wp} {g}" for wp, g in r.wps) or (
            "ROADMAP" if r.roadmap else UNTRIAGED
        )
        if r.wps and r.roadmap:
            wps += " +ROADMAP"
        labels = ",".join(i.labels) or "-"
        prs = " ".join(r.open_prs) or "-"
        landed = "; ".join(r.landed[:3]) or "-"
        if len(r.landed) > 3:
            landed += f" (+{len(r.landed) - 3} more in the file)"
        lines.append(
            f"{i.number:>4}  {_age(i.created, today):>4}  {i.author[:16]:<16} "
            f"{len(i.comments):>2}  {labels[:14]:<14} {wps[:30]:<30} {prs[:22]:<22} {landed}"
        )
    return "\n".join(lines)


def summary(rows: list, prs: tuple = ()) -> str:
    """The three counts a round quotes, the lists behind two of them, and every
    open issue or PR whose author is outside :data:`KNOWN_AUTHORS`."""
    untriaged = [r.issue.number for r in rows if not r.triaged]
    landed = [r.issue.number for r in rows if r.landed]
    in_pr = [r.issue.number for r in rows if r.open_prs]
    fmt = lambda ns: " ".join(f"#{n}" for n in ns) or "none"  # noqa: E731
    others = [f"#{r.issue.number} {r.issue.author}" for r in rows
              if r.issue.author not in KNOWN_AUTHORS]
    others += [f"PR #{pr.number} {pr.author}" for pr in prs if pr.author not in KNOWN_AUTHORS]
    return "\n".join(
        [
            f"{len(rows)} open; {len(untriaged)} untriaged; {len(landed)} with a landed "
            f"reference; {len(in_pr)} cited by an open PR",
            f"untriaged: {fmt(untriaged)}",
            f"landed reference: {fmt(landed)}",
            f"not by {' or '.join(sorted(KNOWN_AUTHORS))}: {', '.join(others) or 'none'}",
        ]
    )


def issue_file(row: Row) -> str:
    """The per-issue file: the record the skill reads instead of the thread."""
    i = row.issue
    wps = ", ".join(f"WP-{wp} {g}" for wp, g in row.wps) or "none"
    if row.roadmap:
        wps += " (+ docs/ROADMAP.md)"
    parts = [
        f"# #{i.number} — {i.title}",
        "",
        f"url: {i.url}",
        f"by {i.author} · opened {i.created} · updated {i.updated} · "
        f"labels: {', '.join(i.labels) or '-'} · comments: {len(i.comments)}",
        f"cited by: {wps}",
        f"open PRs citing it: {', '.join(row.open_prs) or 'none'}",
        f"landed references (touched code): {'; '.join(row.landed) or 'none'}",
        f"placements (planning record only): {'; '.join(row.placed) or 'none'}",
        "",
        "## Body",
        "",
        i.body.strip() or "(empty)",
        "",
    ]
    if i.comments:
        parts += ["## Comments", ""]
        for author, at, body in i.comments:
            parts += [f"### {author} · {at}", "", body.strip(), ""]
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Network and git: thin, each failing into a sentence that says why.
# --------------------------------------------------------------------------- #


def gh_json(root: Path, *args: str, timeout: int) -> tuple:
    """``(parsed, None)`` or ``(None, reason)``: gh's own stderr, kept.

    ``wp_claim._gh`` drops stderr, which is right for a hook that must stay
    quiet and wrong for a table someone is about to work from: a rate limit,
    a 502 on a 1.3 MB query and a missing login all read as "could not list"
    without it.

    One retry, because the merged-PR call runs 50 s and the connection was
    reset by the peer on three of three runs inside this script and none of
    four outside it (2026-09-21): a transient, and a blank column costs the
    round more than a second minute does.
    """
    why = "gh: not run"
    for _attempt in range(2):
        try:
            proc = subprocess.run(
                ["gh", *args], cwd=root, capture_output=True, encoding="utf-8", errors="replace",
                timeout=timeout,
            )
        except OSError as exc:
            return None, f"gh: {exc}"
        except subprocess.TimeoutExpired:
            why = f"gh: no answer in {timeout} s"
            continue
        if proc.returncode != 0:
            first = (proc.stderr.strip().splitlines() or ["exit " + str(proc.returncode)])[0]
            why = f"gh: {first[:160]}"
            continue
        try:
            return json.loads(proc.stdout), None
        except ValueError as exc:
            return None, f"gh: unparsable answer ({exc})"
    return None, why + " (twice)"


def fetch_issues(root: Path) -> tuple:
    """``(issues, None)`` or ``(None, reason)``."""
    raw, why = gh_json(
        root, "issue", "list", "--state", "open", "--limit", "500", "--json",
        "number,title,body,author,createdAt,updatedAt,labels,comments,url",
        timeout=180,
    )
    if raw is None:
        return None, why
    issues = []
    for item in raw:
        comments = tuple(
            (
                (c.get("author") or {}).get("login", "?"),
                c.get("createdAt", ""),
                c.get("body") or "",
            )
            for c in item.get("comments") or []
        )
        issues.append(
            Issue(
                number=int(item["number"]),
                title=item.get("title", ""),
                author=(item.get("author") or {}).get("login", "?"),
                created=(item.get("createdAt") or "")[:10],
                updated=(item.get("updatedAt") or "")[:10],
                labels=tuple(lab.get("name", "") for lab in item.get("labels") or []),
                body=item.get("body") or "",
                comments=comments,
                url=item.get("url", ""),
            )
        )
    return issues, None


def merged_pr_references(root: Path) -> tuple:
    """The newest merged PRs as references; a linked closing issue counts as cited.

    200 rows reach back to 2026-08-22 on 2026-09-21, past the oldest open
    issue; ``files`` doubles the call (27 s to 52-58 s, measured) and is what
    tells a placement from a landing, so it stays.
    """
    raw, why = gh_json(
        root, "pr", "list", "--state", "merged", "--limit", "200", "--json",
        "number,title,body,mergedAt,closingIssuesReferences,files", timeout=240,
    )
    if raw is None:
        return None, why
    refs = []
    for item in raw:
        cited = set(cited_numbers(f"{item.get('title', '')}\n{item.get('body') or ''}"))
        cited |= {int(c["number"]) for c in item.get("closingIssuesReferences") or []}
        paths = [f.get("path", "") for f in item.get("files") or []]
        refs.append(
            Reference(
                "merged PR",
                f"PR #{item['number']} ({(item.get('mergedAt') or '')[:10]})",
                frozenset(cited),
                is_placement(paths),
            )
        )
    return refs, None


def open_pr_references(prs: Optional[list]) -> tuple:
    """From ``wp_claim.open_prs``, whose issue parsing ``/wp-start`` already trusts."""
    if prs is None:
        return None, "gh: could not list the open pull requests"
    return [
        Reference("open PR", f"#{pr.number} ({pr.author})", frozenset(pr.issues))
        for pr in prs
    ], None


def commit_references(root: Path, since: str) -> list:
    """Commits on ``origin/main`` since *since* whose message cites an issue."""
    proc = subprocess.run(
        ["git", "log", "origin/main", f"--since={since}", "--name-only",
         "--format=%x1e%h%x1f%P%x1f%as%x1f%s%x1f%b%x1f"],
        cwd=root, capture_output=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        return []
    return parse_commit_log(proc.stdout)


def parse_commit_log(text: str) -> list:
    """``--name-only`` records into references, merge commits skipped."""
    refs = []
    for record in text.split("\x1e"):
        fields = record.split("\x1f")
        if len(fields) < 6:
            continue
        sha, parents, day, subject, body, files = (f.strip() for f in fields[:6])
        if len(parents.split()) > 1:
            continue
        cited = cited_numbers(f"{subject}\n{body}")
        if cited:
            paths = [p for p in files.splitlines() if p]
            refs.append(
                Reference("commit", f"{sha} {day} {subject[:60]}", cited, is_placement(paths))
            )
    return refs


def main(argv: list) -> int:
    if len(argv) < 2:
        print(__doc__.split("Usage::")[1].strip(), file=sys.stderr)
        return 2
    out_dir = Path(argv[1])
    only = {int(a.lstrip("#")) for a in argv[2:]}
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True,
        encoding="utf-8", errors="replace",
    )
    root = Path(top.stdout.strip() or ".").resolve()

    issues, why = fetch_issues(root)
    if issues is None:
        print(f"could not list the issues ({why}): is `gh` installed, logged in and online?")
        return 1
    if only:
        missing = sorted(only - {i.number for i in issues})
        if missing:
            print("not open: " + " ".join(f"#{n}" for n in missing))
        issues = [i for i in issues if i.number in only]
    if not issues:
        print("no open issues")
        return 0

    references: list = []
    notes = []
    prs = wp_claim.open_prs(root)
    for name, (got, why) in (
        ("open PRs", open_pr_references(prs)),
        ("merged PRs", merged_pr_references(root)),
    ):
        if got is None:
            notes.append(f"could not list the {name} ({why}); that column is blank, not empty")
        else:
            references += got
    oldest = min(i.created for i in issues)
    references += commit_references(root, oldest)

    roadmap = root / "docs" / "ROADMAP.md"
    roadmap_cited = cited_numbers(
        roadmap.read_text(encoding="utf-8", errors="replace") if roadmap.exists() else ""
    )
    rows = cross_reference(
        issues, wp_claim.wp_issue_citations(root), wp_statuses(root), roadmap_cited, references
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (out_dir / f"{row.issue.number}.md").write_text(issue_file(row), encoding="utf-8")

    print(table(rows))
    print()
    print(summary(rows, tuple(prs or ())))
    for note in notes:
        print(note)
    print(f"files: {out_dir}/<N>.md, one per issue above")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
