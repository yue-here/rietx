# WP-2134 — The GUI rulebook keeps rules, and its evidence moves out

Milestone: unscheduled · Status: ✅ 2026-11-10 — `gui/CLAUDE.md` condensed to 662 lines, merged in #1511; moving its 36 visual rules is a gui-overhaul owed item
Track: The repo's own process
Depends on: —

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
- [x] `main` merged and the open PRs' additions folded in.
- [x] Skill: none. The skill is for an agent driving rietx; this file is for
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

### What `gui/STYLE.md` covers of these (checked 2026-11-10)

WP-2142's style guide merged before this WP (#1514). The 36 rules above stay in
`gui/CLAUDE.md` in this PR. Each was read against `gui/STYLE.md` at `384a3a4b2`:

- **Covered** (STYLE.md states the rule; the rulebook copy can go, leaving a pointer
  where a code rule needs it): 1 (principle 3 and `lib/style.test.ts`), 7, 8 (minus
  "no free hue is left"), 15, 16, 19, 24, 25, 26, 27, 32, 34.
- **Covered, and STYLE.md departs from the rulebook** (the move takes STYLE.md's
  version; each departure is marked by the maintainer there): 9 (the peak layer keeps
  one state colour, red, `provisional`), 11 (STYLE.md: no number is judged by colour,
  the Rwp badge included), 21 (the graph title now ellipsises before a control wraps;
  tab labels still never shorten), 23 (ticks sit in their own band at the foot, never
  on the difference axis).
- **Partly covered** (the move merges the rulebook's mechanism into STYLE.md's rule):
  2 (the Components table replaces the nine-register table as the target set), 3
  (type steps as roles; `.chip` and `.pill` go, so the chip tones go with them), 4
  (three theme choices; the `data-theme` stamp is a code rule and stays here), 10
  (the `--fg` ring; the pointer line is not named), 17 and 18 (a tooltip is a verb
  phrase; the help term's markup is not named), 30 (number slots fixed under a
  sweep), 31 (one value-box width per panel; the subgrid mechanism is not named), 33
  (phase order; the OKLab spacing and CPK anchors are not named).
- **Not covered** (STYLE.md says nothing; the style-guide move decides with the
  maintainer whether each is style or code): 5, 6, 12, 13, 14, 20, 22, 28, 29, 35, 36.
  Of these, 12, 13, 14 and 22 are CSS traps a code session meets, and likely stay
  here as code rules.

## Handover log

- **2026-11-10, close** — closed. PR #1511 merged on 2026-11-10, so the rulebook a session
  loads under `gui/` is 662 lines on `main`, against 1068 before. Its first "Next" item, the
  fold of the five PRs' rules, landed in that PR. The second, moving the 36 visual rules into
  `gui/STYLE.md`, has no WP of its own.

  *Leftovers, and where each went.* The 36 visual rules: an item in
  `docs/milestones/gui-overhaul.md` § Owed to the port, which points at this file's coverage
  list above, because the move needs the maintainer for the departures and the uncovered rules.
  Extending `test_gui_rulebook_paths_resolve` to the other rulebooks (root, `tests/`, `io/`,
  `indexing/`) was declined at review as a follow-up. No open WP owns rulebook checks and the
  milestone is the GUI's, so it is not carried; it stays recorded in the entry below. The
  failure this WP saw on `main`,
  `test_indexing_reduce.py::test_a_monoclinic_cell_is_re_set_to_the_conventional_setting[P]`,
  did not reproduce on 2026-11-10: both cases passed at `ddabab7d3` (arm64 macOS, worktree
  `[dev]` venv). The narrative went to `docs/milestones/v1.12.md`.

  Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
  Next: none here.

- **2026-11-10** — `main` merged, and every rule the five GUI PRs added in the
  meantime is folded in. The rulebook is 662 lines. #1487 and #1488 added nothing
  to it. #1498 and #1502 added six standing rules: the start screen's three and
  the File menu's three. Each is now a bullet of § Model, and their two paragraphs
  moved verbatim to WP-2131's and WP-2133's `## Moved from gui/CLAUDE.md`. #1514's
  pointer to `gui/STYLE.md` sits in the header. The § Shell bullet on mounting
  `Model` once took WP-2131's wording: it had named `panels/Model.svelte`'s
  `openPath()`, which the tree no longer has (the path test checks only
  `file:symbol`, so it could not see the possessive form). The 36 visual rules
  were checked against `gui/STYLE.md` and not moved; the coverage is above.
  - *Measured* (`wc`, 4 bytes a token): 662 lines, 44 703 bytes, about 11 180
    tokens, against main's 1068 lines. Cap 1068 → 663 (landed + 1).
  - *Next*: (1) The GUI style guide takes the 36 rules above, by the coverage
    list: drop the covered ones here, merge the partly covered ones, and ask the
    maintainer about the departures and the uncovered ones (visual questions go
    to the maintainer). No WP owns that move yet. (2) Then close this WP.
- **2026-11-09** — The GUI rulebook a session loads under `gui/` is now about
  half its size and says only what to do. Every story, measurement and example
  it held is still in the repository, verbatim, in the WP file each rule names,
  so nothing was lost. Six rules no longer matched the code and now do. A new
  test turns a renamed file or symbol under a rule into a red test instead of a
  silent stale rule. The visual rules kept their wording and are listed above
  for the GUI style guide. Not done: the five open GUI PRs that edit the
  rulebook had not merged when this was opened, so their lines are not folded in
  yet.
  - *Measured* (`wc`, 4 bytes a token): before (origin/main `4c55b9011`) 1059
    lines, 78 154 bytes, about 19 540 tokens. After 642 lines, 43 361 bytes,
    about 10 840 tokens: −39 % lines, −45 % bytes. With #1490 folded at the
    merge of `main`: 644 lines, 43 507 bytes, about 10 880 tokens. Cap
    1060 → 645 (landed + 1).
  - *Where the material went*: 41 paragraphs, verbatim, to a `## Moved from
    gui/CLAUDE.md` section before the handover log of 37 closed WP files (1 298
    lines, 88 760 bytes): 1008, 1009, 1010, 1011, 1012, 1013, 1014, 1015 (2),
    1016 (2), 1017, 1027 (2), 1029, 1032, 1033, 1034, 1035, 1044, 1045, 1201,
    1203, 1204, 1205, 1206, 1207, 1208, 1209, 1210, 1211, 1212, 1213, 1214, 1215,
    1216, 1217, 1425, 1429, 1462 (2). These are records of the closed WPs'
    own rules, never requests for work (`closed_wp_writes.py` lists all 37). Not
    moved: the old header (superseded by the new one), and the browser-driving
    paragraph, whose content the new § Tests keeps in substance. Deleted as
    stated elsewhere: "there is no read-only way to open a project" (root
    CLAUDE.md § Project), the run state not being an event (root § Telemetry),
    where the theme lives (root § Conventions), the series keys (root § Series);
    each is now a pointer. The in-flight WPs' clauses (2003, 2124, 2126, 2127)
    and 2030's were kept as rules and not copied into their WP files, whose
    branches are live.
  - *Contradictions with the tree, fixed in the rulebook*: (1) the node floor
    "≥ 20.12" is stale; `gui/package-lock.json`'s strictest `engines` is jsdom
    30's `^22.22.2 || ^24.15.0 || >=26`, and the rule now says to read it there;
    (2) "the header's `Split | Full` is the only control" was replaced by
    WP-2123's two collapse buttons (`App.svelte` `hideGraphs`/`hideModel`);
    (3) "five keys on every event" is four on every event plus
    `series_rung`/`series_cold` on a restart (`sequential.py`); (4) the theme
    microtask is `lib/pattern.ts`'s `retheme`, no longer in `Plot.svelte`;
    (5) the boolean `hasProject` effect key is in `panels/Series.svelte`, not
    `Model.svelte`; (6) the drag test "in `App.test.ts`" no longer exists, so
    the pointer went. Method: `git grep` of every backticked name in the old
    file (all but plotly-era names resolve) and targeted reads of about forty
    claims. A clear from that method is weaker than a finding: the other rules
    were checked for their names only.
  - *Audit*: a Sonnet agent read the old file against the new one, unanchored on
    this session's, and listed 16 thin or missing rules; 12 were rules and went
    back in, 4 were rationale. `/code-review high --fix` on the new test found
    substring symbol matching, unchecked directories and a dead condition; all
    fixed in `bb8b68614`. Declined: checking bare file names (ambiguous by
    design), globs, and the other rulebooks (root, `tests/`, `io/`, `indexing/`
    use bare names the check cannot resolve; extending it is a follow-up, not
    done here).
  - *Tests* (`[dev]` venv, darwin/arm64, run alone through ghostshift's
    `serial.py`, on the branch before `main` was merged): fast selection 14375
    passed, 417 skipped, 32 xfailed, 1 failed, in 9:54.
    `test_gui_rulebook_paths_resolve` is the one test added, and it passes. The
    failure is `test_indexing_reduce.py::test_a_monoclinic_cell_is_re_set_to_the_conventional_setting[P]`.
    It fails alone too, and this branch changes no `src/` file, so it belongs to
    the base on this machine, not to this WP. No full suite: the change is
    docs and one docs test, and it moves no measured number. After the review's
    fixes, `test_docs_consistency.py` 26 passed and `test_gui_manual.py` 10
    passed. Baseline counts not re-measured on main (`tests/CLAUDE.md` § Running).
  - *Generality*: not dispatched; the branch touches no `_audit.py` row and adds
    no heuristic.
  - *Gotchas*: the cap counts lines only, so keep lines at 100 columns or under;
    the rewrite has none longer. `test_gui_rulebook_paths_resolve` checks only
    paths written with a directory, so write `lib/plot.ts`, never `plot.ts`.
  - *Next*: (1) #1490 merged during the handover and is folded: its Adopt
    sentence went into § Peaks and indexing's Adopt bullet, and its coverage
    sentence became a bullet of its own. When #1498, #1502, #1487 and #1488
    have merged, merge `main` here and fold what each added under these rules.
    #1498 and #1502 rewrite Browse and `Model` in § Model and § Shell, and add
    the start screen and the File menu as bullets there. #1502 also raises the
    cap to 1067, which conflicts with 645: keep 645 plus what the folded rules
    add. #1487 and #1488 added nothing to the rulebook when this was written.
    Then tick the merge task and close the WP. (2) The GUI
    style-guide WP takes the 36 rules listed above. No WP for it exists yet.
- **2026-11-09** — created. No open WP owns a consolidation of the GUI
  rulebook: the gui-overhaul WPs (2123-2133) each add rules to it, and none
  condenses it.
