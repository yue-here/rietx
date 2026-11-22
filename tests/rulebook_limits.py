"""The always-loaded rulebooks' size limits: a budget and a ceiling in bytes (WP-2233).

    python -m tests.rulebook_limits     # the report, against this change's base

**What is limited.**  Every committed `CLAUDE.md`, `AGENTS.md` and
`docs/ROADMAP.md`: the documents a session loads before it reads anything it
chose.  Each costs its size on every request of every session.  Bytes are
counted, because reflowing a paragraph changes its line count and not its cost.

**Two numbers per file**, as `tests/skill_caps.py` has them.  The *ceiling*
fails any tree, `main` included, in `tests/test_docs_consistency.py`.  The
*budget* fails only a change that grows a file past it, and is compared here,
in CI's lint job, against the table **as the base has it**.  So a change
cannot raise the budget it is measured against.

**A raise is visible, not prevented.**  A change whose budget or ceiling is
above the base's prints a warning, and fails unless it touches only this file
and `docs/milestones/process.md` § The caps diary.  A raise is then a change
of its own, which says so in its title, and the content it makes room for
arrives in the next change.  Nothing here can tell who merges it: every pull
request comes from one account (the WP's "What this holds").

**Limits are read from source text by AST**, the base's with `git show`, never
by import, as `tests/audit_delta.py` reads its tables.  The base is
`skill_caps.base()`: `HEAD^1` on a pull request.  A pull request whose base is
not in the checkout fails, since a missing base must not read as no limit.  A
document the base's table lacks is held to `NEW_BUDGET` and `NEW_CEILING`.

**The pins.**  Each budget was pinned at the file's bytes on 2026-11-21, so
every listed file is closed to growth: an addition pays for itself with a
cut.  WP-2009's content pass re-pins them downward, and a cut needs no
separate change.  Each ceiling is the budget plus twice the most that one day
of `main`'s merges added to that file in the 30 days to 2026-11-21, the rule
`skill_caps.REFERENCE_GAP_BYTES` was measured by.  A file that no merge grew
in that window takes `REFERENCE_GAP_BYTES` itself.  The line-count caps these
replace, and their diary, are `docs/milestones/process.md` § The caps diary.

Stdlib only, so CI's lint job can run it.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from dataclasses import dataclass

from tests.skill_caps import ROOT, _git, base, changed_files, rev_exists

REL = "tests/rulebook_limits.py"
DIARY = "docs/milestones/process.md"

#: (budget, ceiling) in bytes per always-loaded document.  Gaps from the
#: 30-day worst day of growth on main, doubled: CLAUDE.md 418, ROADMAP 1636,
#: gui/CLAUDE.md 693, indexing 1503, io 1344, tests 306; none for AGENTS.md
#: and src/rietx/gui/CLAUDE.md.
LIMITS: dict[str, tuple[int, int]] = {
    "AGENTS.md": (2_009, 4_009),
    "CLAUDE.md": (86_787, 87_623),
    "docs/ROADMAP.md": (52_042, 55_314),
    "gui/CLAUDE.md": (45_159, 46_545),
    "src/rietx/gui/CLAUDE.md": (155, 2_155),
    "src/rietx/indexing/CLAUDE.md": (27_747, 30_753),
    "src/rietx/io/CLAUDE.md": (55_732, 58_420),
    "tests/CLAUDE.md": (19_733, 20_345),
}

#: Where a rulebook the base's table lacks enters: a short subsystem
#: rulebook, about 2 000 tokens, with the reference gap above it.
NEW_BUDGET = 8_000
NEW_CEILING = NEW_BUDGET + 2_000

WHERE_IT_GOES = (
    "Cut, or move the text to the WP file or the milestone record: a rulebook "
    "holds standing rules, and the evidence behind one goes to the WP that "
    "measured it (docs/ROADMAP.md § Session protocol, rule 4).")


def documents() -> list[str]:
    """Every committed always-loaded document, by repo-relative path."""
    found = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "*CLAUDE.md", "AGENTS.md", "docs/ROADMAP.md"],
        capture_output=True, encoding="utf-8", check=True).stdout.split()
    return sorted(found)


def limits_in(source: str) -> dict[str, tuple[int, int]]:
    """``LIMITS`` as a version of this file writes it, read by AST."""
    for node in ast.parse(source).body:
        target = (node.target if isinstance(node, ast.AnnAssign)
                  else node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == "LIMITS":
            return {k: tuple(v) for k, v in ast.literal_eval(node.value).items()}
    return {}


def size(text: str) -> int:
    return len(text.encode("utf-8"))


def ceiling_failures(limits: dict[str, tuple[int, int]] = LIMITS) -> list[str]:
    """Every document over its ceiling, or with no row: the tree-wide check."""
    out = []
    for rel in documents():
        if rel not in limits:
            out.append(f"{rel} is an always-loaded document with no row in {REL} "
                       f"LIMITS. Add one at the entry default, ({NEW_BUDGET}, "
                       f"{NEW_CEILING}).")
            continue
        now = size((ROOT / rel).read_text(encoding="utf-8"))
        budget, ceiling = limits[rel]
        if now > ceiling:
            out.append(f"{rel} is {now} B against its ceiling of {ceiling} B "
                       f"(budget {budget} B). Take at least {now - budget} B back "
                       f"out. {WHERE_IT_GOES}")
    return out


@dataclass(frozen=True)
class Row:
    rel: str
    before: int | None          # bytes at the base, None for a new file
    now: int
    limit: tuple[int, int]      # this change's (budget, ceiling)
    base_limit: tuple[int, int]  # the base's, or the entry default

    @property
    def delta(self) -> int:
        return self.now - (self.before or 0)

    @property
    def over_budget(self) -> bool:
        """Grown, and past the base's budget: the one growth failure."""
        return self.now > self.base_limit[0] and self.delta > 0

    @property
    def raised(self) -> bool:
        return self.limit[0] > self.base_limit[0] or self.limit[1] > self.base_limit[1]


def rows(rev: str, base_limits: dict[str, tuple[int, int]]) -> list[Row]:
    out = []
    for rel in documents():
        shown = _git("show", f"{rev}:{rel}")
        before = size(shown.stdout) if shown.returncode == 0 else None
        out.append(Row(rel, before, size((ROOT / rel).read_text(encoding="utf-8")),
                       LIMITS.get(rel, (NEW_BUDGET, NEW_CEILING)),
                       base_limits.get(rel, (NEW_BUDGET, NEW_CEILING))))
    return out


def check(rev: str, how: str) -> tuple[list[str], list[str]]:
    """The failures and the warnings of this change against ``rev``."""
    shown = _git("show", f"{rev}:{REL}")
    if shown.returncode != 0:
        return [], [f"{REL} is new against {how}; its limits are in the diff"]
    found = rows(rev, limits_in(shown.stdout))
    failures, warnings = [], []
    for r in found:
        if r.over_budget:
            failures.append(
                f"{r.rel} is {r.now} B against the base's budget of {r.base_limit[0]} B, "
                f"and this change grew it by {r.delta} B. Take at least "
                f"{r.now - max(r.before or 0, r.base_limit[0])} B back out. {WHERE_IT_GOES}")
    raised = [r for r in found if r.raised]
    for r in raised:
        warnings.append(f"{r.rel}: limits raised from {r.base_limit} to {r.limit} B")
    others = sorted(changed_files(rev) - {REL, DIARY})
    if raised and others:
        failures.append(
            f"This change raises {len(raised)} limits and also edits "
            f"{', '.join(others[:5])}{', …' if len(others) > 5 else ''}. A raise is a "
            f"change of its own that touches only {REL} and {DIARY}.")
    return failures, warnings


def main() -> int:
    rev, how = base()
    if rev is None:
        print(f"rulebook limits: {how}")
        return 0
    if not rev_exists(rev):
        print(f"rulebook limits: {rev} is not in this checkout ({how}); "
              "the checkout needs fetch-depth: 2", file=sys.stderr)
        return 1
    failures, warnings = check(rev, how)
    github = bool(os.environ.get("GITHUB_ACTIONS"))
    for w in warnings:
        print(f"::warning file={REL}::{w}" if github else f"warning: {w}")
    for f in failures:
        print(f, file=sys.stderr)
    if not failures:
        print(f"rulebook limits: no rulebook grew past its budget against {how}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
