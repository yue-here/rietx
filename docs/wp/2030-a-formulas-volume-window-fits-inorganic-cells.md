# WP-2030 — A formula's volume window fits inorganic cells, and a hydrate parses

Milestone: unscheduled · Status: 🔄 2026-11-06 — parts 1 and 2 merged from outside (PRs #1123, #1253, #1237) and the stale `duplicate_line` marks fixed (PR #1344); part 3, the GUI formula as two optional `IndexingControls` fields, merged from outside (PR #1351, 2026-11-06); closing #1121 is the maintainer's
Track: Data and metadata in, a structure out
Depends on: — (1510 soft, closed 2026-10-23: the window, the Z check and the review findings this carries)
Priority: P2 2026-10-23 — a defect that fires wrongly: the skill sends an agent through `SearchSpec.from_formula` before its first search, and the window excludes the true cell of 7 of 8 inorganic solids measured (fluorapatite abstained where the unwindowed search ranked the truth first); indexing is a path few fits run

## Goal

`SearchSpec.from_formula` gives a window that holds the true cell of an
inorganic solid as well as an organic one, or says that it cannot, and
`INDEX_Z_NOT_INTEGER` stays silent on a true inorganic cell. A hydrate
written `CuSO4.5H2O` is read as a hydrate or refused, never read silently as
4.5 O. Each review finding WP-1510 left open is fixed or declined with its
reason.

## Context

**What exists** (WP-1510, PR #690, shipped in 1.7).
`crystallography/atomic_volume.py` holds Hofmann's (2002) Table 2, and
`formula_unit_volume(formula, temperature)` sums it.
`SearchSpec.from_formula(formula, z=…, temperature=…)`
(`indexing/engines.py:419`) sets
`min_volume`/`max_volume` to z formula units × `VOLUME_RATIO_BOUNDS` =
(0.8, 1.25), Hofmann's 25 % boundary (1746 of 182 239 structures lie outside
it, § 3). With `z=None` it sets only the floor.
`index_pattern(formula=, temperature=)` reports `INDEX_Z_NOT_INTEGER` (warning, `value` = the implied
Z) per candidate and never narrows. Its tolerance `Z_INTEGER_TOLERANCE` is
2 × `VOLUME_SCATTER` = 0.08 (`indexing/diagnostics.py:503`), so above
Z = 6.25 it is silent by arithmetic.

**The window misses most inorganic cells.** Measured by WP-1986's session on
2026-10-18 with `SearchSpec.from_formula(formula, z=…)` against each known
cell. The figure is the window's midpoint over the true volume, at each
cell's true z (the four the entry left blank were re-measured 2026-10-23):

| formula | z | midpoint / true V | true cell |
|---|---|---|---|
| NaCl | 4 | 1.18 | inside |
| C8H9NO2 (paracetamol) | 4 | 1.05 | inside |
| CaF₂ | 4 | 1.69 | outside |
| Al₂O₃ | 6 | 2.74 | outside |
| ZnO | 2 | 2.17 | outside |
| Ca5P3O12F (fluorapatite) | 2 | 1.81 | outside |
| LaB₆ | 1 | 1.96 | outside |
| Si | 8 | 1.91 | outside |
| Na2Ca3Al2F14 (NAC) | 8 | 3.22 | outside |

The midpoint is 1.025 × z × V_est, so the truth lies inside only while the
ratio is between 0.82 and 1.28 (arithmetic on the shipped bounds). Every miss
is an overestimate, so the floor is what excludes the truth. LaB₆ holds one
formula unit, so even `z=None`'s floor sits about 1.5× above its true cell
(0.8 × 1.96 / 1.025). On the shipped fluorapatite pattern
(`src/rietx/data/examples/FAP.XRA`) the windowed search took 127 s, ranked
only cells of 1000-1050 Å³ and abstained. The same search unwindowed put the
true 523.6 Å³ cell first. `INDEX_Z_NOT_INTEGER` rests on the same volume, so
on fluorapatite's true cell it implies Z = 1.14 and fires.

**The source says so.** Hofmann's table is fitted to organic and
metal-organic crystals. He found 496 structures overestimated by 25-75 %,
often highly ionic with small cells, and says the volumes may not apply to
inorganic substances (§ 3 (iii)). `atomic_volume.py`'s docstring records
this, yet `from_formula` applies the table to any formula. The skill
recommends it twice: § 7d of `docs/skill/rietx/references/diagnostics-indexing.md`
("Before the first search, ask for the cell or infer it"), and
`references/abstention.md`, which sets `max_volume` from it for a large
monoclinic or hexagonal search. An agent that follows either gets a wrong lead,
and nothing tells it so.

**The Z tolerance's trade-off** (WP-1510, 2026-10-03). One crystal scatters
4 % about Hofmann's estimate, so the source run's Z ≈ 2.8 reads as "3, within
the method" and does not fire. Flagging it would need a tolerance under
6.7 %, and Hofmann's Table 1 puts about a third of correct cells more than
5 % off. Nobody has asked for that change.

**The hydrate parse.** `_parse_formula` (`atomic_volume.py:154`) splits an
adduct on `·`, `•` or `*`, and a count may be decimal. So `CuSO4.5H2O` reads
as 4.5 O and comes out 39 % low, silently, and the grammar cannot tell it
from `Mg0.5SiO3` (WP-1510's review, 2026-10-03). The review's candidate fix:
refuse a `.` hydrate and point to `·`.

**The rest of WP-1510's review, still open** (sites checked 2026-10-23):
- `IndexingResult` (`schemas/indexing.py:1861`) records no formula, so a
  reopened result cannot say which formula its Z check read. `formula` does
  not reach the CLI (`cli.py:343`, the `index_pattern` call) or the GUI
  (`gui/session.py:1618`).
- `INDEX_DATA_INSUFFICIENT` leads with an undeclared instrument
  (`diagnostics.undeclared_instrument`, `indexing/diagnostics.py:338`) when
  the axial apertures are zero or the profile is the default `ProfileTCHZ`. A
  correctly set-up synchrotron instrument has both, so the lead misfires
  there. And the documented two-step flow, `index_pattern(peaks)` with no
  instrument, never sees the lead: `PeakList` (`schemas/indexing.py:881`) does
  not record the instrument it was picked with.
- The supercell test (`ambiguity.supercell_chance`, `:708`) judges which
  observed lines the parent explains (`explained`, `:814`) with the child's
  shift correction applied to the parent's lines. That count drives
  `consensus.above_supported_parents` (`:324`), which ranks a supported child
  directly above its parent. Whether the promotion earns a rule in
  `src/rietx/indexing/CLAUDE.md` was left open; the rulebook records only the
  refuted direction (WP-1449). 1510's lane replay over 13 captured searches
  moved only corundum's order, 8th → 1st.
- The GUI peak editor's `duplicate_line` marks go stale when the owning
  component moves. `gui/peaks.py`'s `_spliced` (`:525`) re-flags only the
  edited group (`flag_duplicate_lines(merged, only=…)`). 1510 declined it
  twice: clearing other groups' flags would undo a user's flag edits
  (WP-1043), and `gui/peaks.py` forbids editing other groups. Its last entry
  still listed it open.

**Tiers** ([generality § The rule](../milestones/generality.md#the-rule)).
Hofmann's volumes and the 0.8-1.25 boundary are tier 2 for organic and
metal-organic crystals, cited (Hofmann 2002, § 3). The citation does not
reach past that population. Any rule deciding which formulas the table
serves, and any window or volume source for the rest, is tier 3 unless a
cited inorganic source carries it. Tier 3 means at least three unrelated
families, each checked against its certified or published cell
(`tests/data/README.md`). The window removes cells from the search, so it is
an action. Name its kind before choosing (DESIGN § Rules, 1): a narrowing
that can exclude the truth on a formula its source does not cover is not one
every competent refiner would make. `Z_INTEGER_TOLERANCE`'s factor 2 is
tier 3 over a tier-2 scatter. `INDEX_Z_NOT_INTEGER` is a flag, so the
mechanical ground asks that it fire on a cell of non-integer Z and stay
silent on true cells. A refusal of an ambiguous formula string is tier 1.
Gating the instrument lead on a lab source is tier 1 if it reads the declared
source. `VOLUME_RATIO_BOUNDS` (WP-2006's walk) and `Z_INTEGER_TOLERANCE` and
`INDEX_Z_NOT_INTEGER` (WP-2007's) sit at `unaudited` in
`src/rietx/_audit.py`. A value changed here updates its row, and a name new
to the table arrives tiered (CI's `tests/audit_delta.py`).

## Non-goals

- Replacing Hofmann's table for organic and metal-organic formulas, where the
  window held (paracetamol 1.05; benzoic acid 16.7 Å³ per non-hydrogen atom,
  WP-1510).
- Letting the Z check narrow or remove candidates. It reports (1510's
  agent-first rule).
- Widening the default box, any engine change, or ranking beyond the
  supercell count (1449, 1511).
- Replaying `solution case 1`: its pattern is a collaborator's unpublished
  data and is not in this tree.

## Tasks

- [x] Re-measure the table above on this tree, at the true z and at
      `z=None`, adding any inorganic standard in `tests/data/` it lacks.
      Pin it in `tests/test_indexing_formula.py`.
- [x] Decide the inorganic rule from that measurement. Candidates: a
      ceiling-only window outside Hofmann's population, since every measured
      miss is an overestimate; a cited inorganic volume source; or the window
      kept with a warning. Record the choice, the rejected options and why in
      the handover. Test that every measured true cell lies inside its window.
- [x] (withdrawn, not met: no test can do both; see the 2026-10-30 entry) `INDEX_Z_NOT_INTEGER`: silent on every measured true cell, still firing
      on an injected cell of non-integer Z.
- [x] Fluorapatite: `from_formula("Ca5P3O12F", z=2)` holds the 523.6 Å³ cell,
      and the windowed search on `FAP.XRA` ranks it where the unwindowed one
      does.
- [x] Hydrate: `CuSO4.5H2O` is refused, naming `·`, or read as a hydrate.
      `Mg0.5SiO3` still reads 0.5 Mg and `CuSO4·5H2O` is unchanged. Test all
      three.
- [x] `formula` and `temperature` recorded on `IndexingResult`, with the
      writer named (root CLAUDE.md: a declared name is a claim). `formula`
      reaches the CLI and the GUI's indexing call. (The result fields and the
      CLI landed in part 1. The GUI stores the formula in optional
      `formula`/`temperature` fields on `IndexingControls`, as the 2026-11-02
      rulings entry settled, built in part 3.)
- [x] The instrument-first lead fires only on a lab source. Decide whether
      `PeakList` records its instrument so `index_pattern(peaks)` sees the
      lead. Test both.
- [x] Supercell (superseded by #941, dropped from this PR; see item 6 of the 2026-10-23 entry): judge the parent's lines with the parent's own shift. Replay
      the captured searches and run the indexing acceptance. Then write or
      decline the supported-promotion rule in `src/rietx/indexing/CLAUDE.md`.
- [x] GUI: fix the stale `duplicate_line` marks or decline them, with the
      reason in the handover. (Fixed, with the two ghost marks, by a change
      rule that keeps a user's cleared mark; see the 2026-11-02 entry.)
- [x] Audit rows for every value changed or name added (tiers above).
- [x] Manual: `docs/docs/theory/indexing.md` and `reference/indexing.md`
      state the window's scope; a staged release note.
- [x] Skill: § 7d and `abstention.md` say when the window applies. Stay
      inside `tests/skill_caps.py`'s budget and re-sync the copies
      (`rietx skill --install . --copy`).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_skill.py -q
.venv/bin/python -m ruff check src tests examples
```

And: every true cell in the measured table lies inside its window (a test),
the windowed fluorapatite search ranks the 523.6 Å³ cell where the
unwindowed one does, and `CuSO4.5H2O` never reads as 4.5 O.

## References

- Hofmann, D. W. M. (2002). *Acta Cryst.* B58, 489–493. Per-element volumes;
  § 3 (iii) on inorganic substances. In the corpus at
  `zotero-linker/derived/XULHS76B/`.
- Kempster, C. J. E. & Lipson, H. (1972). *Acta Cryst.* B28, 3674. The 18 Å³
  rule, organic.
- A candidate inorganic source, read before citing: Jenkins, H. D. B.,
  Roobottom, H. K., Passmore, J. & Glasser, L. (1999). *Inorg. Chem.* 38,
  3609–3620. Formula-unit volumes from ion volumes.
- WP-1510 (closed 2026-10-23): the window, the Z check, the review findings.
  WP-1986's 2026-10-18 entry: the measurement above.
- #1121: the claim, and the plan of two PRs (the measurement and the fixes
  that need no ruling, then the window rule once it is chosen).

## Handover log

- **2026-11-06** (`/pr-review`) — part 3 merged from outside as PR #1351 (`544dff21`), adding to the contributor's own entry and ticks, which stand as written. `IndexingControls` now stores `formula` and `temperature`, and the GUI's Peaks panel sends them. The stored format changed, and the maintainer approved that on 2026-11-06 ("Yes, run #1351"). The 2026-11-02 entries say 1.10 and 1.11. The releases that apply are 1.11.0 and 1.12: 1.11.0 refuses any project 1.12 has saved. A bookkeeping sync (`f711a92e8`) kept both notes under schema 0.61, this PR's and WP-1542's, and rebuilt the dist. Merged tree, `[dev]`, macOS arm64: `-m slow` 939 passed, 19 skipped, 19 xfailed, 1 failed. The failure is `test_the_two_site_winner_finds_each_site_its_own_moment`, the Mac-only row of #1424 placed under WP-1418, which this PR's files do not reach. CI and the GUI build were green on that head. Closing #1121 and this WP stays the maintainer's. The PR carries no closing keyword.

- **2026-11-02** — Part 3 (#1121): the GUI stores the specimen's formula,
  built as the rulings entry below settled it. `IndexingControls.formula` and
  `.temperature` are `None` when unset. One function,
  `crystallography.atomic_volume.check_formula_input`, refuses what `rietx
  index` refuses, and the CLI and a model validator both call it. So a
  project file, an assignment and the GUI's settings verb refuse in the CLI's
  sentence. The GUI's index run passes both fields, unset reading as the CLI
  reads it: no formula, at `TABLE_TEMPERATURE` (298 K).
  `tests/test_search_controls.py` moves the two from `CALL_TIME_INPUTS` to
  `CONTROL_TO_KWARG`. The form puts both beside the volume limits, with the
  temperature box disabled until a formula is given. The candidate table gains
  a `Z` column (`formula_units`) when the run read a formula, its header
  explained by the formula's help entry, since no help arm covers
  `CellCandidate`. The dist is rebuilt. The manual's GUI guide § Indexing, the
  controls table of `reference/indexing.md` and the staged notes say so.

  *Decisions.* The CLI's sentence for a temperature without a formula lost its
  flag names so that one sentence serves every surface; neither form has
  shipped. `PROJECT_FORMAT_VERSION` is 1.6. `Project.save` writes every field,
  so a project this release saves carries both keys as null when unset, and
  1.10.0 refuses any project 1.11 has saved, not only one carrying a formula.
  That follows 1.10.0's note ("even where its value is null"); the narrower
  cost the ruling named would need the keys written only when set. The twin of
  `reference/indexing.md` sat at its 50 000-character cap, so three sentences
  of its controls subsection were tightened to pay for the two rows; the page
  needs a split before it grows again. No audit row: `IndexingControls` is
  not a default seat or a record schema, and `tests.audit_delta` reports no
  change.

  *Measured.* Fast suite on pearl at `b43573cb4` (main `e8d210278`; Linux,
  Python 3.12, `-n 8`): 13 729 passed, 171 skipped, 34 xfailed, 0 failed,
  479 s. Vitest 24 files, 593 passed; svelte-check 0 errors. Manual `-W`
  build, Vale (0 errors) and `tests.reader_output` (unchanged) clean. Each new
  or changed Python test fails on main's `src` (14 failed; the 6 passes are
  CLI cases whose words did not change), and `controls.test.ts` fails 3 of 10
  on main's `controls.ts`.

  *Next.* Closing #1121 is the maintainer's. `solve.chemistry.in_volume_window`
  is flagged separately and untouched here.

- **2026-11-02** (rulings, PR #1349) — Where the GUI stores the
  specimen's formula is settled: two optional fields, `formula` and
  `temperature`, on the search-controls block of the project file
  (`IndexingControls`), shown in the indexing form beside the volume limits.
  Nothing is built yet. The maintainer delegated the choice in chat on
  2026-11-02: "whatever is more consistent with our design ethos. don't worry
  about sunk cost, I don't think that many people are using indexing at the
  moment and we're doing a big rework anyway."

  *Settled by Claude under that delegation: option A* of the 2026-11-02
  brief below. Grounds. Root CLAUDE.md § Project: `project.json` holds
  settings (selected plan, mode, limits), and the formula is a search setting
  that sits beside the volume limits. The package already treats the formula
  as a run input (`index_pattern(formula=)`, `rietx index --formula`). The
  global rule to build the smallest thing, with no scaffolding for later,
  rules out option B's specimen block, whose other consumers do not exist.
  Option C loses the formula on every reopen. The maintainer waived the sunk
  cost and the forward-compatibility cost, which is that a 1.11 project file
  carrying a formula is refused by 1.10 (`extra="forbid"`).

  *Next* (the build, not done in this batch). (1) `IndexingControls` gains
  `formula: str | None` and `temperature: float | None`, each `None` when
  unset, with the CLI's validation (an unreadable formula and a temperature
  that is not a positive finite number of kelvin are refused, and a
  temperature without a formula is refused). (2) `gui/session.py`'s index run
  passes both to `index_pattern`. (3) `tests/test_search_controls.py` moves
  `formula` and `temperature` from `CALL_TIME_INPUTS` to the controls side of
  the bijection. (4) The form fields in `gui/src/lib/controls.ts` with their
  labels and titles, the committed corpus
  `tests/data/gui/index_controls.json`, a Z (`formula_units`) column in the
  candidate table, and a rebuilt dist (node >= 20.12). (5) The manual's GUI
  indexing chapter and a staged note. Then #1121 can close, which is the
  maintainer's act.

- **2026-11-02** (ghostshift runner, PR #1344) — The GUI's peak editor no longer leaves a
  line marked unusable after the line it was judged against moves. Two marks
  are judged against another group's line: a copy (`duplicate_line`) against
  the better-measured fit of the same peak, and a Kβ or tungsten ghost against
  its parent. An edit refits one group, and until now only that group's marks
  were recomputed, so moving or deleting a copy's owner left the copy withheld
  from the search, and moving a line onto another group's weaker fit left the
  peak offered twice. Each such mark on an untouched group now changes only
  where the picker's own judgement changed, so a mark a user cleared stays
  cleared. The GUI half of the formula task is not done: where the formula is
  stored is a stored-format choice, set out below for the maintainer.

  *Done.* (1) `gui/peaks.py`: `_spliced` judges the ghost and copy marks on
  the list before and after the edit, each on copies stripped of the mark
  (`_machine_marks`), and moves an untouched peak's mark only where the two
  judgements differ (`_follow_cross_group_marks`). A deleted group takes the
  same path. Ghosts are followed first, since a ghost owns no line. Task 9's
  2026-10-03 decline rested on two rules: a user's flag edits must survive
  (WP-1043), and the editor touches no other group. The change rule keeps the
  first, since an unchanged judgement never touches a flag. It narrows the
  second the way `weak_line` already did after the maintainer's review of
  #947 (item 1: a stale flag elsewhere must not survive an edit). Settled by
  Claude under that ruling and WP-1043's rule. (2) The sibling class:
  `ghost_kbeta` and `ghost_tungsten` are judged against a parent anywhere in
  the list, so they had the same defect and get the same rule.
  `kalpha2_residual` is judged against the strongest line of its own group, so
  it cannot go stale this way and is left alone. (3) `gui/CLAUDE.md` gains the
  rule: a new flag whose basis crosses groups joins
  `_follow_cross_group_marks`. (4) Staged note under 1.11.0 § Changed.
  (5) `### Inherited`: the 2026-10-26 triage entry is deleted; its "nothing
  merged" no longer holds, and the claim it records is in the Status line and
  the entries below.

  *Tests.* `tests/test_peak_editor_marks.py`, seven cases on a synthetic
  ten-line pattern. With the new function disabled, four fail (owner moved,
  owner's group deleted, a line moved onto a weaker fit, a ghost's parent
  moved). Two guards pass either way, as they should: a copy's mark and a
  ghost's mark that the user cleared stay cleared when an unrelated group is
  refitted. The seventh pins that a delete emptying a group hands the ghost
  screen the declared source (failed with the fix reverted).

  *Review* (`/code-review high --fix`). Accepted: `PeakEditor.remove`, on
  the path where a delete empties a group, now passes the instrument's
  source as a refit does, since that path re-judges ghosts and a neutron or
  monochromated beam must skip the Kβ search (WP-1445); the `gui/CLAUDE.md`
  rule was cut back under its 1060-line cap; the staged note's "stays
  cleared" now says through any edit that leaves the judgement alone (a
  mark the user cleared does return when the judgement itself flips on);
  the index regenerated; the ghost test checks the follow is per peak.
  Declined: reusing the after-judgement for the fresh group's own ghost
  marks (it could reorder flags on a peak with both ghost marks, and three
  screen runs per click cost little); storing a user's overrides as a
  human-owned fact in place of the change rule (a design change to the
  `peaks.json` contents, outside this task); the in-place mutation of the
  pre-edit list (`flag_weak_lines` already does it, and nothing holds an
  undo stack).

  *Generality.* No audit row and no judge dispatched. The change adds no
  threshold, constant or ordering of evidence: it applies the picker's
  existing ghost and copy rules to the untouched groups, and "ghosts first"
  is the order those rules already depend on (a ghost owns no line).

  *Measured.* Fast selection on this branch's final code tree (own `[dev]`
  venv, macOS arm64, Python 3.12; three other runners' suites on the machine,
  so the 43 min wall clock is a load figure): 13 513 passed, 314 skipped,
  34 xfailed, 2 failed. Neither failure touches this change. `test_display`'s
  kernel case fails on this Mac's Jupyter kernel spec, which points at a
  deleted venv. `test_site_classes`' unplaceable-species case tripped its 15 s
  runaway guard at 24 s under that load and passed when run alone. The seven
  added tests cost 2.2 s together (local junit). `tests.reader_output`:
  unchanged (exit 0). `test_docs_consistency.py` 25 passed; ruff clean.

  *Decision for the maintainer: where the GUI stores the specimen's formula.*
  Trigger: either stored option changes the project file's format, and the
  choice rests on how people use the indexing form, which nobody has watched.
  Why it matters: the formula gives each indexing candidate its number of
  formula units, Z (`formula_units`), and records which formula the run read.
  The API and `rietx index --formula` take it today; the GUI's indexing call
  passes none, so a GUI user never sees Z. The candidate table has no Z column
  yet, so every option below also adds one. Importance: minor. Aim, as I read
  it: a GUI user indexing an unknown gets the same evidence an API user gets.
  Options. (A) Two optional fields on the search-controls block of the project
  file (`IndexingControls.formula`, `.temperature`), shown in the form beside
  the volume limits. Remembered per project. A 1.11 project file with a
  formula then fails to open in 1.10, which `extra="forbid"` refuses; old
  files open unchanged. Undo: drop the fields with a migration. (B) A
  specimen block at the top of the project file, which later features could
  read too (the solve path's chemistry check takes a formula). Same costs,
  plus a new top-level name on the main surface, for consumers that do not
  exist yet. (C) Not stored: the form holds the formula and sends it with
  each indexing run. No format change; the formula is lost on reload and must
  be retyped after every reopen. (D) Do nothing: the formula stays an API and
  CLI input. Practice: GSAS-II 5.8.4's indexer takes no formula, and DICVOL06
  takes an optional density and formula weight (`docs/practice.md`, "A volume
  window from the formula, in indexing", checked); TOPAS not checked. No
  program stores a formula as an indexing setting, so every option departs
  from practice by offering it at all. Recommendation: A, a lean. The crux is
  whether the formula belongs to the run or to the specimen. The package puts
  it on `index_pattern` and on `rietx index`, and B builds for consumers that
  do not exist. C loses to A on retyping, which a person re-indexing after a
  peak edit would do every session. Evidence that people index several
  specimens of one chemistry from one project would favour B.

  *Next.* (1) The maintainer's choice above. (2) Then the form field, the Z
  column, the vitest corpus (`tests/data/gui/index_controls.json`) and a
  rebuilt dist; on A, `tests/test_search_controls.py` moves `formula` and
  `temperature` from its call-time inputs to the controls. (3) Closing #1121
  is the maintainer's once that lands.

- **2026-11-01** (`/pr-review`) — part 2 merged from outside as PR #1237 (`4505cbaf`), adding to the contributor's own 2026-10-30 entry and ticks, which stand as written. The formula's volume window is a ceiling only (Hofmann 2002, factor 1.25), and `VOLUME_RATIO_BOUNDS` is tier 2. `INDEX_Z_NOT_INTEGER` and `Z_INTEGER_TOLERANCE` are deleted. The test fired on true inorganic cells, whose ratio to the estimate runs 0.38 to 0.87, and the number survives as `formula_units`. `solve.chemistry` applies the ceiling too. The 2026-10-30 entry says `in_volume_window` "reads both edges" of the band. That was true when it was written and is not true now. The `Status:` line no longer says "claimed by @mustachefeeling", since part 2 landed. Issue #1121 stays open. The file's tasks leave two things for it: the GUI half of the `formula` task, which waits on the maintainer's choice between an `IndexingControls` field and a project-document field, and the stale `duplicate_line` marks. Closing #1121 is the maintainer's. What ran: the PR was replayed in a stack of nine with the other round's merges onto `main` `276fe91d` and run at `635d25e3` (Mac arm64, Python 3.12, `[dev,jax]`). Full suite 14 161 passed, 235 skipped, 50 xfailed, 0 failed. The manual `-W` build was green.

- **2026-10-31** (`/pr-review`) — #1123's follow-ups merged from outside as PR #1253 (`349ec37b`), three `WP-2030:` commits, after one round. Built from the round 1 to 3 lists: (a) `_audit.RECORD_SCHEMAS` walks `IndexingResult` and `PeakList`. `PeakList.instrument_undeclared` is an action row at tier 1, and the other 23 fields sit in `OTHER_RECORD_FIELDS`. The review held the row at tier 1, since it records only whether the geometry and profile blocks equal their defaults, on a source `lab_source` identifies as a lab tube. `CellCandidate`, which holds `LeBailValidation.mode`, is not walked, because the walk does not recurse into list fields. WP-2007 § Inherited leaves bringing the indexing schemas into the walk to the maintainer, so this is early. (b) `rietx index` refuses a formula it cannot read and a temperature that is not a positive finite number of kelvin as a usage error (exit 2, no traceback), before it reads the pattern. `--temperature` without `--formula` is refused. A run with no temperature still hands `index_pattern` 298 K. (c) `KNOWN_CELLS` reads each cell from its source. Halite comes from COD 9003308 (a = 5.6401 Å at 298.15 K; 5.6402 Å could not be sourced) and benzoic acid from COD 7252065, each vendored with a `tests/data/README.md` row. Si and corundum read the certificate's 22.5 °C (295.65 K). Nine rows import `indexing_gallery.TRUTHS` and four read their vendored CIFs. No pinned ratio moves past its 5e-4 bar (Si 0.53689 → 0.53701, corundum 0.37468 → 0.37476, halite 0.86595 → 0.86590). (d) `D` reads as H, so `C6D6`, `CD3OD` and `CuSO4·5D2O` read as their H forms, and `CuSO4.5D2O` is still refused as two-way. `temperature=inf` is refused in `formula_unit_volume` and `SearchSpec.from_formula`. Item (e), a solvate off the 13-molecule list (`ZnCl2.2C5H5N`) reading as a decimal, was left as is, with no issue opened. Round 3's line on the spaced sum (`"Mg1.5 H2 O"`) is in #1237, part 2, which is open. #1253 and #1237 touch adjacent hunks in `tests/test_indexing_formula.py` (the `KNOWN_CELLS` block above `MEASURED`) and `src/rietx/cli.py` (the `--formula` help), so the second to merge may need a hand merge. 15 of the 16 new cases in `tests/test_indexing_formula_input.py` fail on main's `src`. `tests.audit_delta` reports 1 added, 0 new at `unaudited`, no tier-3 row. No task is ticked. "Audit rows for every value changed or name added" gains one row and stays open. Still open: the window rule (#1121), the Z check, fluorapatite, the GUI half of `formula`, the `duplicate_line` marks, the manual's scope sentences and the skill. Gate (the six PRs of this round merged together onto main `766c3505d`; macOS arm64, `[dev,jax]`, Python 3.12): fast 12 884 passed, 223 skipped, 32 xfailed; slow 435 passed, 18 skipped, 16 xfailed, with one GUI-boot socket timeout under load that passed alone in 5 s; ruff and the `-W` manual build clean.

- **2026-10-30** (`/pr-review`) — part 1 merged from outside as PR #1123 (`a1ce786c`) after three rounds. The contributor's ticks, `Status:` decisions and the 2026-10-23 entry stand as written (ruled 2026-10-29), so this entry adds the merge record. Round 3 accepted `lab_lines()` matching Kα1, Kα2 and the weighted mean, so 1.5418 Å and 0.71073 Å read as lab sources. It withdrew the schema-number item: 0.60 stays, because `schemas/common.py` keeps main's number for a PR rebased over a bump. `027aacae` shortens the formula paragraph of `reference/indexing.md` to fit its twin cap. One gotcha is left, not blocking. With `\s*` allowed inside an adduct, a spaced CIF sum whose fractional count is followed by exactly an adduct's atoms at the end of the part (`"Mg1.5 H2 O"`) now refuses as two-way, where 1.10.0 read it one way. The refusal names its cause and such a sum is unlikely in a real file, so the regex stays. A line in the manual's spaced-sum sentence would stop it reading as a promise. The GUI half of the `formula` task is still open, as the 2026-10-23 entry says. Part 2 waits on the window rule (#1121). Gate (a stack of eleven PRs on main `b40bc994`, tree `307eff83`; macOS arm64, `[dev,jax]`, Python 3.12): 13 217 passed, 216 skipped, 48 xfailed, 0 failed, with ruff, the `-W` manual build and the GUI ladder green.

- **2026-10-30** — Part 2 of 2 (#1121): the window rule the maintainer chose
  on 2026-10-24 ("Option A, for every formula"), and what rests on it.

  *Decided (the maintainer, #1121).* A ceiling only, for every formula, tier
  2. Rejected: Jenkins et al. (1999) ion volumes (calibrated for lattice
  energies through a cube root; cation volumes for Li-Cs and Mg-Ba only; the
  oxide ion alone, 43 ± 15 Å³, exceeds the formula-unit volume of every dense
  oxide measured), a floor kept for carbon-bearing formulas (calcite 0.659
  and aragonite 0.610 would fall below it; Hofmann's own Table 3 lists metal
  formates at 0.75-0.78), and the window kept with a warning (it holds 1 of
  16 inorganic cells).

  *Done.* (1) `SearchSpec.from_formula` sets `max_volume` = z × V_est × 1.25
  and leaves `min_volume` at the 15 Å³ default (a caller may pass one); with
  `z=None` it narrows nothing. All 16 inorganic and 4 organic known cells lie
  inside their window (a test per cell); HKUST-1 (2.283) does not.
  `VOLUME_RATIO_BOUNDS` is tier 2. (2) Hofmann's band is worded as he means
  it in the docstrings and the manual: where he starts calling a structure
  unusual, about 1 % of the CSD past it (1746 of 182 239), typical scatter
  about 4 % (Fig. 1). (3) *The Z check (task 3), not met and withdrawn.*
  Against Hofmann's Table 3 a correct inorganic cell looks like a wrong Z:
  nine of the 16 sit below 0.57, his class (i). With no floor the volume
  bounds Z from one side only (Z ≥ V/(1.25 V_est)), so no whole-number test
  can be silent on true cells and fire on a wrong one, for any formula.
  `INDEX_Z_NOT_INTEGER`, `Z_INTEGER_TOLERANCE` and their rows are gone; the
  number is recorded as `CellCandidate.formula_units`, and
  `index_pattern:formula` is tier caller. This is not WP-2033's scope (its
  Non-goals name the search's Z check as 2030's). (4) Fluorapatite:
  `from_formula("Ca5P3O12F", z=2)` holds the 523.6 Å³ cell (fast test), and a
  slow acceptance row checks the windowed `FAP.XRA` search ranks it where the
  hand-ceilinged one does. (5) Skill § 7d and `abstention.md` say the window
  is a ceiling, `z=None` narrows nothing, `formula_units` is not grounds to
  drop a cell, and a framework without its pore contents sits above the
  ceiling (HKUST-1 2.28; `SiO2` meets it at FAU's framework density, 13.3 T
  per 1000 Å³ in the IZA database, so a less dense framework lies above).
  (6) `docs/practice.md`: GSAS-II 5.8.4 and DICVOL06 take the volume range
  from the user; neither estimates it from a formula.

  *Measured* (pearl, one pinned core per arm, preset full, monoclinic only,
  `max_d_axis` 20 Å, 900 s per engine × system; every search was cut by that
  budget, so a rank is what the search reached in it). Truth rank, window
  (floor and ceiling) / ceiling / no volume: bethanechol set E 1 / 1 / 1, set
  Aa not found in any arm, paracetamol (exact positions from COD 2104364's
  cell, 36 lines) 1 / 1 / 1. CPU: E 1807 / 1869 / 2035 s, Aa 1024 / 1069 /
  1963 s, paracetamol 1531 / 1833 / 2154 s (pearl's load varied 8-40 during
  the runs).

  *Not done, for a part 3.* `formula` in the GUI's indexing call (half of
  task 6): `tests/test_search_controls.py` files `formula` and `temperature`
  as call-time inputs, the specimen's chemistry, so a form field means
  either an `IndexingControls` field or a project-document field, a choice
  for the maintainer. The stale `duplicate_line` marks (task 9): not
  attempted. `solve.chemistry`'s `in_volume_window` still reads both edges
  of the band, so it reads `False` on a true inorganic cell; it is a
  reported flag in the solve path, outside this WP.

- **2026-10-23** — Part 1 of 2 (#1121): the measurement, and the fixes that
  need no ruling. The window holds the true cell of 1 of 16 inorganic solids
  and 4 of 5 organic or metal-organic ones; the window rule is the
  maintainer's choice, set out on #1121 with these numbers. A hydrate written
  with a full stop is refused, the result records its formula, the
  instrument lead reads the declared source. (The supercell item was
  superseded by #941 on rebase.)

  *Done.* (1) `tests/test_indexing_formula.py` pins 21 known cells, each
  with its source: 16 inorganic (the NIST certificates for LaB6, Si and
  corundum; NAC, fluorapatite, the five round-robin minerals, cBN, three
  GSAS-II tutorial cells and COD's YBCO; halite's 5.6402 Å) and 5 organic
  or metal-organic (paracetamol, benzoic acid from COD 7252065, bethanechol
  chloride, HKUST-1, a hybrid iodide). V_obs/V_est: 0.375-0.649 on 15
  inorganic cells, halite 0.866; 1.000-1.044 on four organic ones, HKUST-1
  2.283 (its formula leaves the pores' contents out, Hofmann § 3 (ii)). The
  window at the true Z holds halite and the four; at `z=None` the floor of
  one formula unit still excludes the three Z = 1 cells (LaB6, brucite,
  YBCO). **The Context table's NAC row uses z = 8; COD 1000236 gives Z = 4**,
  so its midpoint ratio is 1.61, not 3.22, and the cell is still outside.
  (2) `INDEX_Z_NOT_INTEGER` fires on 12 of the 16 inorganic true cells and
  is silent on every organic one; the four it spares imply the wrong whole
  number (Si 4.30 for 8). (3) `formula_unit_volume` refuses a full stop
  that reads both as a decimal count and as a hydrate's dot, naming `·`
  (tier 1: refusing an ambiguous string rather than guessing). What is refused is a
  decimal count of 1 or more straight after an element or a bracket and
  followed, past any whitespace, by one of the 13 adduct molecules that ends
  the part. Every other decimal reads as 1.10.0 read it: `Mg0.5SiO3`,
  `CuSO4·5H2O`, a spaced CIF formula and the doped oxides `Fe2.95O4`,
  `Li1.05Mn1.95O4` and `Ca9.5(PO4)6F2` are unchanged. A solvate whose molecule
  is not on the list (`ZnCl2.2C5H5N`) still reads as a decimal, as it did. (4) `IndexingResult.formula` and `.temperature`, written
  by `index_pattern` on both its paths (`None` with no formula), and
  `rietx index --formula --temperature`. (5) `diagnostics.lab_source` reads
  the declared source: a Kα doublet, or one line within 5e-4 Å of an
  anode's Kα1, Kα2 or weighted mean (`radiation=`'s value, GSAS-II's six
  decimals, a vendor header's 1.5418). The instrument lead fires only there. `PeakList` records the
  undeclared blocks (`instrument_undeclared`, written by `pick_peaks` and
  `fit_peaks`) rather than the whole instrument, and the record outranks
  an instrument handed in later. (6) *Dropped on the 2026-10-25 rebase:* the supercell change
  (`supercell_chance(parent_q_obs=)`) is not in this PR. C3 (#941) rewrote
  `consensus.supercell_checks` to ask containment on `screen_for`, which
  scores every candidate on its own `scored_positions`, so the parent is
  already read on its own shift correction. One audit row was owed and is
  there: `LAB_LINE_TOLERANCE_ANGSTROM` (tier 1, arithmetic: the six anodes'
  lines are at least 0.14 Å apart, so 5e-4 Å names one anode at most). The
  other new names are record fields on `IndexingResult` and `PeakList`,
  which `_audit.RECORD_SCHEMAS` does not walk, so the table cannot see them
  and "no row owed" there shows only that.

  *Measured* (own `[dev]` venv, macOS arm64, pearl offline). On the
  supercell change this PR dropped on the 2026-10-25 rebase, a replay of the
  22 consensus calls the indexing acceptance makes (100 parent-child pairs,
  20 candidates carrying a shift) moved no count, verdict or order; that
  measures the dropped change, and this PR touches no consensus code.
  `tests/test_acceptance_indexing.py`: 44 passed in 14:44, on the tree before
  the rebase. Fluorapatite on
  `FAP.XRA` (hexagonal and trigonal, preset full, the acceptance row's
  budgets): unwindowed 157 s, truth ranked 1; the shipped window
  (738-1153 Å³) 28 s, truth absent, the 1050 Å³ cells lead; a ceiling alone
  (15-1153 Å³) 36 s, truth ranked 1. Bethanechol sets Aa and E (monoclinic,
  20 Å axes, default budgets, every search budget-truncated): the window
  took 70 and 76 s, the ceiling alone 89 and 95 s, no volume 97 and 111 s;
  set E ranked the truth 8th windowed and 1st in both others, Aa nowhere.

  *Not done, for part 2.* The window rule (task 2) and what rests on it:
  the Z check (task 3; no tolerance silences it on every measured true cell
  and still fires on an injected Z = 2.5, since LaB6 and YBCO sit 48 % from
  1, so it needs the same population test the window does), the
  fluorapatite task (4), the audit rows the rule adds (10), the manual's
  scope sentences (11) and the skill (12). `formula` in the GUI's indexing
  call (half of task 6): it needs an `IndexingControls` field, so the form,
  its vitest corpus and a rebuilt dist, which belongs with task 9's GUI
  work. The stale `duplicate_line` marks (9): not attempted. Hofmann (2002)
  is not on this machine (the corpus path above is the maintainer's) and
  Jenkins et al. (1999) is closed; neither was read here.

  *Next.* The maintainer's choice of window rule on #1121, then part 2.
- **2026-10-23** — created by WP-1510's close, from its `### Inherited`
  (WP-1986's window measurement, 2026-10-18) and the review findings its
  2026-10-03 entries left open. No open WP owned `from_formula`, Hofmann, a
  hydrate or `formula=`, nor the instrument lead, the supercell count or the
  GUI marks (grep of `docs/wp`, 2026-10-23). Nothing built.
