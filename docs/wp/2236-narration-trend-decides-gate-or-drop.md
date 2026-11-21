# WP-2236 — The narration trend, measured over six weeks, decides a gate or a drop

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: WP-2233
Priority: P4 2026-11-21 — bookkeeping that changes no number; not before 2027-01-02, when six weeks of weekly commits exist to measure

## Goal

A decision, recorded in this file, on whether comments that narrate history ("until WP-N",
"since WP-N") get a CI gate or the count is dropped, made from the trend
`tests/narration_count.py` measures over weekly commits of `main`.

## Context

**Why.** A comment that says what the code was before a WP is history, and history goes
stale in a way a pointer to the WP does not. WP-2233's ruling 1 (maintainer, 2026-11-21)
made narration **tracked, not gated**, for now: the trend is measured before any gate is
decided. WP-2233 built the counter and no CI step, so the trend has to be computed from
history.

**The counter.** `python -m tests.narration_count REV [REV…]` prints one table per revision:
per top-level package of `src/rietx`, the blocks matching `until WP-\d{4}`, `since WP-\d{4}`,
`before WP-\d{4}` and `(was|were) .{0,60} until`, and *any*. A block is one comment run or one
string statement, read as `tests/code_references.py` reads them. It reads each revision with
`git cat-file`, so any commit works. It takes about 4 s a revision.

**The baseline**, measured 2026-11-21 on WP-2233's branch (`[dev]` venv, macOS arm64): 158
blocks narrate. By pattern, 38 "until WP", 56 "since WP", 61 "before WP" and 13 "was …
until". The largest packages are `schemas` (18), `indexing` (17), `optimize` and `refine`
(16 each). `origin/main` before WP-2233 read 159.

**The method.** Pick the first-parent commit of `main` nearest each Monday from 2026-11-23,
`git rev-list --first-parent -1 --before=<date> origin/main`, and run the counter over them.
Normalise by the comment block count at each revision if the source grows fast, since a
flat count in a growing tree is a falling rate.

**The tier.** A gate on comment narration would be new judgement: no program surveyed has
one. Martin (2008, *Clean Code*, ch. 4) names "journal comments" as an anti-pattern, which is
practice for the direction, not for a threshold.

### Inherited

## Non-goals

- Rewriting the narrating comments: a gate's WP, if this one decides on a gate.
- Plain backtick names absent from the code, which WP-2233 left unchecked.

## Tasks

- [ ] Run the counter over the weekly commits from 2026-11-23 to the session's date, and
      record the table of *any* by week in the handover.
- [ ] Decide, with the numbers, among: a gate failing a change that adds a narrating block;
      a report in CI's lint job; dropping the counter. A gate or a drop is the maintainer's
      call (it changes the project's process), so bring it with the numbers.
- [ ] Skill: none. The skill drives rietx, and this is about the package's own comments.

## Acceptance

```sh
.venv/bin/python -m tests.narration_count $(git rev-list --first-parent -1 --before=2026-11-23 origin/main)
```

The handover records the weekly series and the maintainer's ruling.

## References

- Martin, R. C. (2008). *Clean Code*, ch. 4, Comments ("journal comments"). Prentice Hall.

## Handover log

- **2026-11-21** — created by WP-2233's session at its close, as WP-2233's task 6 asked.
  Fold check: no open WP owns comment narration. WP-2009 owns the rulebooks' content, not
  the code's comments.
