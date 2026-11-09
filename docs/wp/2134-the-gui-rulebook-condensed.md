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
- [x] `gui/CLAUDE.md` rewritten: rules only, grouped by the file a session
  edits, duplicates merged, contradictions with the code fixed.
- [x] A cheap test for what the rulebook names, named in the rulebook.
- [x] `SIZE_CAPS` lowered to landed + 1, with a diary row in the test and a
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

Each rule below is visual (colour, type, component or layout) and stays in
`gui/CLAUDE.md` with its wording unchanged in substance until the GUI style guide
takes it. The style-guide WP moves each one, leaves a pointer if a code rule still
needs it, and decides any conflict with the guide's own sources with the maintainer.
Headings are `gui/CLAUDE.md`'s sections; the WP in brackets holds the evidence.

House style and help:

1. One token layer and nine registers; size, padding and radius belong to the register (1201).
2. The register table: what each of the nine means (1201).
3. Three type steps; secondary is `.muted`; mono is a family; the five chip tones (1201).
4. The theme is three-way and resolved once, stamped as `data-theme` (1029).
5. A `.pick` row carries its own hover background (1204).
6. A register's width is the call site's (1206).
7. A placeholder is a word, never a plausible number (1206).
8. Chrome is not a palette: plot marks take `--plot-*` tokens 0.13 OKLab apart; no free
   hue is left for a further quantity-carrying mark (1210, 1211).
9. State rides on the mark's shape, never a second colour; a non-data mark never borrows
   `--muted` (1210).
10. A mark carrying no quantity takes chrome ink: the pointer line is solid `--fg` (1213).
11. Only the Rwp badge may be green (1217).
12. Two cascade traps: state selectors' specificity, inherited `text-transform` (1201).
13. A `ch` column holds only at one font and one size (1217).
14. A `td` that is not `display: table-cell` is not a cell (1209).
15. GUI prose is written under `/yue-docs-style` (1201).
16. What a name means is a `rietx.help` entry reached through `<Help>` (1203).
17. `title=` is what is left over (1203).
18. A term is a focusable `<span role="button">` named by its children (1203).
19. A chip's words are the corpus's short label (1209).
20. No mute fields (1032, 1203).

Elsewhere in the rulebook:

21. Shell: overflow wraps and never truncates, the header included (1034).
22. Shell: a column that must not lose gets a flex basis, not a share (1034).
23. Plot: a tick has its own band between pattern and residual (1032).
24. Plot: hiding a curve is by exception (1032).
25. Plot: the hover readout is a strip, never a box, and its shape never follows the
    pointer (1213).
26. Plot: prose takes `−`, numbers take `-` (1213).
27. Plot: shading spans every pane's height and is clipped to the measured extent (1033).
28. Plot: an armed range gesture shows `col-resize` (1044).
29. Plot: candidate lines are drawn under everything (1211).
30. Peaks: a scanned column's places are fixed (1209).
31. Model: a form's column count is a promise; a cell is a `subgrid` (1216).
32. Structure viewer: the look is crystallography's (projection, edges, bonds, ellipses)
    (1015).
33. Structure viewer: distinguishability is a property of the set drawn; OKLab phase
    palette and CPK anchors (1029).
34. Structure viewer: the cell frame takes `--accent` (1462).
35. History: lanes are half a palette in each place (1217).
36. History: a difference is given twice, the percentage of |a|, at three significant
    figures (1217).

## Handover log

- **2026-11-09** — created. No open WP owns a consolidation of the GUI
  rulebook: the gui-overhaul WPs (2123-2133) each add rules to it, and none
  condenses it.
