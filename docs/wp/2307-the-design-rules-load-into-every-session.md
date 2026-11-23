# WP-2307 — The design rules load into every session

Milestone: unscheduled · Status: ✅ 2026-11-23 — the rules load into every session (#1809) and sit under the rulebook limits (#1812)
Track: The repo's own process
Depends on: —

## Goal

Every session and subagent changing rietx works with the design rules in its context.
The rules have one source, and its size is held like the rulebooks'.

## Context

`docs/DESIGN.md` loaded only when a session opened it. The root `CLAUDE.md` cites
"DESIGN.md § Rules" in several clauses and restated parts of Rule 1. A subagent, or a
session working a WP that links no DESIGN section, never saw the rules. Claude Code's
`@path` import loads a whole file into the importing `CLAUDE.md`'s context, so the key
part has to be a file of its own.

The key part is the top of DESIGN.md: the Why paragraph and § Rules, 13.6 kB (about
3.4k tokens a request). It moves to `docs/DESIGN-RULES.md`. DESIGN.md keeps both
headings as one-line pointers, so the text has one home and the 111 citations of
"DESIGN.md § Rules" still resolve.

Two of the maintainer's rulings, recorded until now only in a WP or in memory, join
the rules, because they govern the whole project:

- Rule 1: an input that leaves a choice open is surfaced, never settled by which
  reading is commoner (2026-11-21, WP-2006 § Rulings 23).
- Rule 5's *Direction*: the arithmetic-accuracy bar is the accuracy TOPAS, GSAS-II and
  FullProf deliver (2026-11-19 for TOPAS, generalised 2026-11-23), and Pawley is the
  structure-free method rietx leads with (2026-11-05, #1434; WP-2062).

Milestone directions stay in their records: the parametric milestone's audience and
TOPAS-parity ruling are in `docs/milestones/parametric.md`, the magnetic path's
authority in `docs/milestones/magnetic.md`.

**The limits.** `tests/rulebook_limits.py` holds every always-loaded document to a byte
budget. It finds them by name (`*CLAUDE.md`, `AGENTS.md`, `docs/ROADMAP.md`), so an
imported file escapes it. A new document above `NEW_BUDGET` (8 000 B) needs a row, a
row needs the file on the tree (`test_the_limits_table_names_every_always_loaded_document`),
and a row above the entry default must land alone. So the order is: the file and the
import first, then a change touching only `tests/rulebook_limits.py` and
`docs/milestones/process.md` that follows `@` imports and adds the row.

## Non-goals

- Moving any other DESIGN.md section into the loaded file.
- Rewriting the 111 citations of "DESIGN.md § Rules".

## Tasks

- [x] `docs/DESIGN-RULES.md` holds the Why paragraph and § Rules; DESIGN.md points to it.
- [x] The two rulings join Rules 1 and 5.
- [x] The root `CLAUDE.md` imports the file and pays for the line with a cut; `AGENTS.md`
      points other harnesses at it within its budget.
- [x] A fresh headless session and a subagent inside it each quote the new Rule 5
      bullet from loaded context, with no file read (2026-11-23).
- [x] `tests/rulebook_limits.py` counts a file an always-loaded document imports, with
      a row for `docs/DESIGN-RULES.md` and a diary entry, in a change of its own.
- [x] Close this WP in a change after the limits change merges, since that change may
      touch only its two files. Merge order: this branch's PR, then the limits PR,
      whose base is this branch until then (against main it fails the raise rule).
- [x] Skill: none; the rules govern changing the package, not driving it.

## Acceptance

`.venv/bin/python -m pytest tests/test_docs_consistency.py` green, and after the
limits change `python -m tests.rulebook_limits` reports the new file under its budget.

## Handover log

- **2026-11-23** — closed. The design rules reach every session and subagent, and their
  size is held like the rulebooks'. #1809 merged the move and the two rulings. #1812
  merged the limits change after its CI passed against main. It replaced #1810, closed
  unmerged, whose single commit had picked up the wrong message in a botched amend. The
  narrative is in the v1.13 record. Next: none. A rule that grows `DESIGN-RULES.md` now
  pays for itself with a cut, as the rulebooks' additions do.

- **2026-11-23** — handover. Every session and subagent now starts with the design rules
  in its context: why rietx exists and the five rules, which before loaded only when a
  session opened DESIGN.md. The rules still have one home, now `docs/DESIGN-RULES.md`,
  and DESIGN.md points to it. Two project-wide rulings that lived only in a WP or the
  maintainer's memory are now rules: the arithmetic-accuracy bar (what the established
  programs deliver) and Pawley as the structure-free method. It costs about 3.4k tokens
  on every request.

  *Ruled.* The maintainer approved both rule edits on 2026-11-23 ("Yes, both stand"):
  the accuracy split (§ Practice and § Conflicts now say their accuracy is the model's)
  and the ambiguity paragraph in Rule 1. All five rules stay whole in the loaded file,
  on the lean the brief gave (splitting them into loaded and unloaded parts invites a
  session to treat the unloaded part as optional; the saving was about 2 kB).

  *Done.* The move, the two rulings, the import, the AGENTS.md pointer, the path lists
  (CI's planning set, issue-review's placement list, the generality-review agent), and
  the limits change on its own branch (`wp2307-limits-follow-imports`: `documents()`
  follows `@` imports past code, up to five hops, to committed `.md` files only; a row
  at 13 680 B).

  *Measured.* A headless Haiku session started in this worktree, and a Haiku subagent
  it launched, each quoted the new Rule 5 bullet from loaded context with no file read.
  On this branch `tests/test_docs_consistency.py`, `test_audit_table.py`,
  `test_manual_api.py` and `test_rulebook_limits.py` gave 106 passed (`.venv`
  arm64 CPython 3.12, macOS 26). The limits branch passes `rulebook_limits.check`
  against this branch and fails it against main, as the raise rule intends. No test was
  added, so no count moved; the fast and full suites were not run, since nothing a
  fit computes changed.

  *Review.* `/code-review high --fix` on the limits branch: fixed two important finds
  (a double-backtick span and an indented fence each read as an import) and one nit
  (git's quoted non-ASCII paths, now read NUL-separated). Skipped two: only `.md`
  targets are followed, a stated narrowing since every import here is Markdown; and
  CI's docs-only job does not run `tests/test_rulebook_limits.py`, a gap that predates
  this WP (ROADMAP.md was already so placed) and that the lint job's size check covers.

  *Gotchas.* Filed as WP-2305, renumbered 2307 at handover: another session filed
  WP-2305 (the joint call's renames) on main the same day. The limits PR's base must stay this branch until this PR merges: retargeted
  to main early it fails the raise rule. It may touch only its two files, so it cannot
  tick its task here; the closing change does. A bare `@path` in a PR body mentions a
  GitHub user, so write it in backticks.

  Next: merge this PR; then the limits PR (GitHub retargets it to main); then a closing
  change ticks the last two tasks and marks the WP ✅.
- **2026-11-23** — a blind review found ten points. Fixed: the ambiguity paragraph
  went past the ruling (it now states the two ruled forms only); WP-2062 was described
  as done; the compounding cases were wider than WP-2222's three; § Practice and
  § Conflicts contradicted the accuracy direction; CI's planning set, issue-review's
  placement list and the generality-review agent still named DESIGN.md alone;
  `documents()` missed inline and nested imports and crashed on a path outside the
  repo; five prose faults. Left to the maintainer: whether every part of the five
  rules is key enough to load on every request (13.7 kB, about 3.4k tokens).
- **2026-11-23** — created. No open WP owns it: WP-2009 rewrote the rulebooks' content
  and WP-2233 set their limits, both without the design record.
