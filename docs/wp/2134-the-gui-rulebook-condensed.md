# WP-2134 — The GUI rulebook keeps rules, and its evidence moves out

Milestone: unscheduled · Status: 🔄 2026-11-09 — claimed by ghostshift runner
Track: The repo's own process
Depends on: —
Priority: P4 2026-11-09 — process: no number moves, but every GUI session pays the file's size

## Goal

`gui/CLAUDE.md` holds standing rules only, each stated once with its
identifiers and anchor, grouped so a session finds the rule for the file it is
editing. Every derivation, measurement story, worked example and per-WP history
it carried lives in the WP file it came from, and the cap in
`tests/test_docs_consistency.py` is lowered to the landed size plus headroom.

## Context

Asked for by the maintainer on 2026-11-09: "condense the gui claude.md and make
it more robust, based on our previously successful attempts to condense
claude.md file by removing useless stuff (moving examples and references out
etc)".

- **The file**: on origin/main at `4c55b9011` it is 1059 lines, 78 154 bytes,
  about 19 500 tokens at 4 bytes a token, loaded whole by every session working
  under `gui/` or `src/rietx/gui/`. Its cap is 1060.
- **The method** is the root file's: WP-1031 (1142 → 601 lines) and WP-1060
  (→ 553), recorded in `docs/milestones/process.md` § The rule. A line enters an
  always-loaded rulebook only as a standing rule a stranger needs in six months,
  evidence compressed to one clause plus a pointer (protocol rule 4). Never
  delete facts to fit a cap: move narrative to the WP file or the milestone
  record. Delete only what is already stated elsewhere, and say where.
- **Visual style is out of scope for rewriting.** A separate GUI style guide is
  about to be written and will hold the visual rules (colours, typography,
  components, layout) with their motives. This WP keeps those rules' wording and
  lists each one under § Visual-style rules for the style guide, so the
  style-guide WP can take them.
- **Concurrent edits**: open PRs #1490, #1498, #1487, #1488 and #1502 edit
  `gui/CLAUDE.md` and merge first. Their additions are folded into the condensed
  file under the same rules at the handover's merge of `main`.
- The tier of each rule this WP adds: none. It moves and restates rules; the one
  new test checks names, not a heuristic.

## Non-goals

- No code behaviour changes. A rule that contradicts the code is fixed in the
  rulebook, against the tree.
- No rewrite of the visual-style rules' substance (see Context).
- `src/rietx/gui/CLAUDE.md` stays the pointer it is.

## Tasks

- [x] Claimed.
- [x] Inventory the file: each paragraph sorted into standing rule, evidence or
  duplicate; each rule verified against the tree.
- [x] Evidence moved verbatim to the WP files it came from (a `## Moved from
  gui/CLAUDE.md` section in each), duplicates deleted with where they live.
- [ ] `gui/CLAUDE.md` rewritten: rules only, grouped by the file a session
  edits, duplicates merged, contradictions with the code fixed.
- [ ] A cheap test for what the rulebook names, named in the rulebook.
- [ ] `SIZE_CAPS` lowered to landed + 1, with a diary row in the test and a
  paragraph in `docs/milestones/process.md` § `gui/CLAUDE.md`.
- [ ] `main` merged and the open PRs' additions folded in.
- [ ] Skill: none. The skill is for an agent driving rietx; this file is for
  changing the GUI.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_gui_manual.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## Visual-style rules for the style guide

Filled in by the rewrite task.

## Handover log

- **2026-11-09** — created. No open WP owns a consolidation of the GUI
  rulebook: the gui-overhaul WPs (2123-2133) each add rules to it, and none
  condenses it.
