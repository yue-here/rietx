"""The skill tree's size limits: a ceiling and a budget per capped file (WP-1338).

    python -m tests.skill_caps          # the report, against this change's base

**Two numbers per file, because two different things go wrong.**  The
*ceiling* is where an agent stops being able to read the file in one call,
and it fails on any tree.  The *budget* sits below it and fails only a change
that grows the file past it, measured against the change's base.  A file over
its budget is not broken; it is closed to growth, so the next addition pays for
itself with a cut or goes somewhere else.

**Why two, measured.**  Each pull request's CI sees its own merge with `main`
as it stood at push time, so two that pass alone can fail together (#247).
With one number the second author inherits a total they did not write, and
the cheapest way to pass is deleting someone else's prose: three attempts to
absorb 599 B once produced 36 209, 36 136 and then 37 083 B.  With a budget the
cut falls on whoever grows a file past it, while they are writing it, and the
gap between budget and ceiling absorbs the pull requests that merge together.
This is a disk quota's soft and hard limit.  A merge queue would remove the
race outright, and this repository's plan has none.

**The gap, measured over `main`'s merges 2026-08-28 to 2026-09-28.**  Close to
a cap, additions are small and concurrent ones are few: the most any 24 hours
added to `SKILL.md` across its growing merges was 990 B (2026-09-02; 796 B on
2026-09-17), and a reference row runs 400-600 B.  `REFERENCE_GAP_BYTES` is
twice that worst day.  Far from a cap a day can add 8 kB to one file, and no
gap absorbs that; the budget is what stops a file arriving at its ceiling that
way.

**The body's budget is the specification's, not a gap below its ceiling.**
agentskills.io recommends a body under 5 000 tokens, and every session that
loads the skill pays for the whole body.  So `SKILL_BUDGET_BYTES` is that
recommendation in bytes, the body sits over it, and the budget works as a
ratchet: while over, no change may grow it, which is the placement rule's
"paid for by a cut" (CONTRIBUTING.md § The agent skill) made mechanical.  The
body's budget counts the Markdown below the frontmatter, so a version bump in
`metadata` is never a growth.

**A generated file has a ceiling and no budget**: `api*.md` is one signature
per public name, its size a fact about the API, and an author cannot cut it.

Stdlib only, so CI's lint job can run the report before anything is installed
beyond it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "docs" / "skill" / "rietx"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCE_DIR = SKILL_DIR / "references"

#: A skill body is read whole on activation; the Read tool returned 66 kB on
#: the document this replaced, so the body is capped at half of it.
# Half the Read tool's ~66 kB cap, the derivation the line above states;
# 32_000 was that halving rounded down and WP-1131 rounded it up, in
# the commit that needed the 941 B — a fifth deliverable class (microstructure)
# in the body's own deliverable table, with its worked measurement in
# references/judging.md where the other four keep theirs.  The cost this cap
# governs — the fixed bytes every session that loads the skill pays — moves by
# 3 %, and the alternative was a deliverable whose row lived outside the table
# its peers are in, which is what the cap exists to protect against.
SKILL_MAX_BYTES = 33_000
#: agentskills.io/specification: "Keep your main SKILL.md under 500 lines."
SKILL_MAX_LINES = 500
#: agentskills.io/specification § Progressive disclosure: the body "< 5000
#: tokens recommended".  The body is denser than prose's usual 4 B a token:
#: in WP-1338's placement round its arrival added 9 300-9 600 tokens of
#: context to a haiku session for 32 277 B injected, about 3.4 B a token, so
#: 5 000 tokens is 17 000 B.
SKILL_BUDGET_BYTES = 17_000
#: Bash output above 40 kB is truncated to a ~2 kB preview, so a reference file
#: stays comfortably under that even when a session cats it rather than Reads.
#: 36_000 → 36_600 in the commit that needed the 571 B, on WP-1131's precedent
#: for ``SKILL_MAX_BYTES``: ``HOLD_BLOCKED_PLAN``'s row, which
#: ``test_docs_consistency.test_every_engine_diagnostic_code_has_a_protocol_row``
#: requires of every engine code, and ``diagnostics.md`` had 9 B of headroom.
#: The two tests are in tension and one had to give, and deleting another
#: code's measured guidance to fit a new one is the wrong direction.
#:
#: **That split happened** (WP-1415, 2026-09-21), so the cap has not moved
#: again and this note records the seam rather than asking for one. The
#: criterion was not size: the main table carries what a **fit** is likely to
#: say, and a code conditional on a quirk of the file you read goes to a
#: secondary doc. The eleven reader rows became §7i,
#: ``references/diagnostics-reading.md``, taking ``diagnostics.md`` from
#: 36 562 to 30 953 B. ``diagnostics-projects.md`` had recorded that those rows
#: stay in §7 on a different criterion, and that paragraph was corrected in the
#: same commit.
#:
#: So the next addition has room, and the rule for the one after it is the
#: criterion above rather than a byte count: ask which file a reader meets the
#: code in, and whether a fit is likely to say it.
#:
#: **The second split** (PR #385, 2026-09-25) applied that criterion when
#: ``CELL_RUNAWAY``'s row and main's growth took ``diagnostics.md`` to
#: 37 008 B. Seven of the eight series codes (``SERIES_PATTERN_FAILED``
#: and every ``SEQUENTIAL_*`` but ``SEQUENTIAL_PERSISTENT_FINDING``, whose
#: row was already in ``abstention.md``; 3 423 B) arrive on a ``SeriesResult`` and a
#: single fit never emits one, so they moved to a code table at the end of
#: §9b, ``references/series.md``, which already had its routing row, so
#: ``SKILL.md`` did not grow. ``diagnostics.md`` went to 33 789 B and
#: ``series.md`` from 25 685 to 29 545 B; one pointer row stays where the
#: rows stood.
REFERENCE_MAX_BYTES = 36_600
#: The gap below `REFERENCE_MAX_BYTES` that concurrent pull requests may fill
#: (module docstring: twice the worst measured day close to a cap).
REFERENCE_GAP_BYTES = 2_000
REFERENCE_BUDGET_BYTES = REFERENCE_MAX_BYTES - REFERENCE_GAP_BYTES
#: `api.md` is **generated** from the installed package, so its size is a fact
#: about the public API and not a thing an author chose.  The authored cap says
#: "stop writing, split the file", which is advice this file cannot take: the
#: whole of it is one signature per public name, and cutting a signature is
#: cutting the document three "explore the library" runs needed.  A public
#: keyword therefore pushes it over a bar that has nothing to do with the
#: decision that added the keyword — WP-1431's `label=` did, at 58 B of
#: headroom.  Raising `REFERENCE_MAX_BYTES` instead would hand
#: `diagnostics.md` room it had been denied, so the generated file gets its own
#: bar against the same 40 kB truncation.  39 000 → 39 500 (WP-1343): main
#: stood at 38 993 B, 7 B under, so any PR adding a public field failed here;
#: #524 adds 137 B (two `Phase` fields, a preset key, `'1.10'`).  39 500 → 39 600
#: (WP-1539): `auto_background(source=)` adds 49 B, and no signature in the index
#: can be cut for it.  39 600 → 39 700 for two additions that landed apart:
#: WP-1510's `index_pattern(formula=, temperature=)`, 56 B, and WP-1527's
#: `diagnostics=` on `write_topas_inp` and `write_fullprof_pcr`, 37 B, so a
#: writer can name the ion it wrote as its neutral atom.  Merged, the file is
#: 39 698 B, and the ceiling is 300 B under the 40 kB truncation, so the next
#: raise is the split.  A technique split (`api-magnetic.md`) is the
#: alternative, and the maintainer's call.
API_INDEX_MAX_BYTES = 39_700


@dataclass(frozen=True)
class Cap:
    """One capped file: its ceiling on the whole file, its budget (``None``
    for a generated file) on the part an author writes."""

    path: Path
    ceiling: int
    budget: int | None

    @property
    def rel(self) -> str:
        return self.path.relative_to(ROOT).as_posix()

    def budgeted_bytes(self, text: str) -> int:
        """The bytes the budget counts: the body's Markdown below its
        frontmatter, or a reference file whole."""
        if self.path == SKILL and text.startswith("---\n"):
            text = text.split("---\n", 2)[2]
        return len(text.encode("utf-8"))


def caps() -> list[Cap]:
    out = [Cap(SKILL, SKILL_MAX_BYTES, SKILL_BUDGET_BYTES)]
    for path in sorted(REFERENCE_DIR.glob("*.md")):
        if path.name.startswith("api"):
            out.append(Cap(path, API_INDEX_MAX_BYTES, None))
        else:
            out.append(Cap(path, REFERENCE_MAX_BYTES, REFERENCE_BUDGET_BYTES))
    return out


def _git(*args: str) -> subprocess.CompletedProcess:
    # UTF-8 explicitly: the working tree is read as UTF-8, and a locale
    # decode (cp1252 on Windows) would count the base's bytes differently.
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, encoding="utf-8")


def base() -> tuple[str | None, str]:
    """The revision a change is measured against, and how it was chosen.

    ``None`` means there is no change to measure: a push to `main`, where the
    gap is doing its job, or a checkout with no `main` to compare with.  On a
    pull request GitHub checks out its merge of the branch into the base, so
    ``HEAD^1`` is the base as it stood at push time (ci.yml's `changes` job
    reads it the same way, and needs `fetch-depth: 2` for the same reason).
    """
    forced = os.environ.get("RIETX_CAPS_BASE")
    if forced:
        return forced, f"RIETX_CAPS_BASE={forced}"
    if os.environ.get("GITHUB_ACTIONS"):
        if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
            return "HEAD^1", "the pull request's base"
        return None, "not a pull request, so there is no change to measure"
    found = _git("merge-base", "HEAD", "origin/main")
    if found.returncode != 0:
        return None, "no origin/main to measure against"
    return found.stdout.strip(), "the merge-base with origin/main"


def text_at(rev: str, cap: Cap) -> str | None:
    """The file as it stood at ``rev``, or ``None`` where it did not exist."""
    shown = _git("show", f"{rev}:{cap.rel}")
    return shown.stdout if shown.returncode == 0 else None


def rev_exists(rev: str) -> bool:
    return _git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").returncode == 0


@dataclass(frozen=True)
class Row:
    cap: Cap
    before: int | None     # budgeted bytes at the base, None for a new file
    now: int               # budgeted bytes in the working tree

    @property
    def delta(self) -> int:
        return self.now - (self.before or 0)

    @property
    def changed(self) -> bool:
        return self.delta != 0 or self.before is None

    @property
    def room(self) -> int | None:
        """The budget less what it counts, negative when over; ``None`` for a
        generated file, which has no budget."""
        return None if self.cap.budget is None else self.cap.budget - self.now

    @property
    def over_budget(self) -> bool:
        """Grown, and past the budget: the one condition the budget fails."""
        b = self.cap.budget
        return b is not None and self.now > b and self.delta > 0

    def cut_needed(self) -> int:
        """The least a change must take back out to pass."""
        return self.now - max(self.before or 0, self.cap.budget or 0)


def rows(rev: str) -> list[Row]:
    out = []
    for cap in caps():
        text = cap.path.read_text(encoding="utf-8")
        old = text_at(rev, cap)
        out.append(Row(cap, None if old is None else cap.budgeted_bytes(old),
                       cap.budgeted_bytes(text)))
    return out


def budget_failures(found: list[Row]) -> list[str]:
    return [
        f"{r.cap.rel} is {r.now} B against its budget of {r.cap.budget} B, and "
        f"this change grew it by {r.delta} B. Take at least {r.cut_needed()} B "
        "back out: cut your own addition, or move it where the placement rule "
        "(CONTRIBUTING.md § The agent skill) sends it"
        for r in found if r.over_budget]


def table(found: list[Row], how: str) -> str:
    """The Markdown report: every capped file this change touched."""
    lines = [f"**Skill size limits**, measured against {how}.", "",
             "| file | before | now | change | budget | left | ceiling |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    changed = [r for r in found if r.changed]
    for r in changed:
        budget = "—" if r.cap.budget is None else f"{r.cap.budget}"
        left = ("—" if r.room is None else f"{r.room}" if r.room >= 0
                else f"{-r.room} over")
        lines.append(f"| `{r.cap.rel.removeprefix('docs/skill/rietx/')}` | "
                     f"{'new' if r.before is None else r.before} | {r.now} | "
                     f"{r.delta:+d} | {budget} | {left} | {r.cap.ceiling} |")
    if not changed:
        lines.append("| no capped file changed | | | | | | |")
    lines += ["", "*before*, *now* and *left* count what the budget counts: the "
              "body below its frontmatter, a reference file whole."]
    return "\n".join(lines)


def main() -> int:
    rev, how = base()
    if rev is None:
        print(f"skill caps: {how}")
        return 0
    if not rev_exists(rev):
        print(f"skill caps: {rev} is not in this checkout ({how}); "
              "the checkout needs fetch-depth: 2", file=sys.stderr)
        return 1
    found = rows(rev)
    report = table(found, how)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(report + "\n")
    github = bool(os.environ.get("GITHUB_ACTIONS"))
    for r in found:
        if github and r.changed:
            level = "error" if r.over_budget else "notice"
            left = ("" if r.room is None else f", {r.room} B left in its budget"
                    if r.room >= 0 else f", {-r.room} B over its budget")
            print(f"::{level} file={r.cap.rel}::{r.delta:+d} B to {r.now} B{left}")
    failures = budget_failures(found)
    for f in failures:
        print(f, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
