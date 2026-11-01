# WP-2014 — A heuristic meets the judge on every path into main

Milestone: generality · Status: ✅ 2026-10-20 — CI fails a new name at unaudited, every module walked or declared out, the judge on outside PRs and weighing both cases
Track: The registry and the guard
Depends on: 2001

## Goal

Every path by which a new or changed heuristic reaches main passes the generality judge.
That means an outside PR as well as a WP branch, a directory the audit table did not
watch as well as one it did, and a fix pushed after the handover. The judge also weighs
the case for an action that a branch removes or leaves to the caller, and reports a side
with no evidence as having none.

## Context

The rule is [generality § The rule](../milestones/generality.md#the-rule); the kinds of
ambiguity are [DESIGN § Rules](../DESIGN.md#rules), 1. WP-2001 built the guard:
`src/rietx/_audit.py` (one row per heuristic, with its tier), `tests/test_audit_table.py`
(the tripwire), `_audit.UNAUDITED_BASELINE` (the names allowed to stay at `unaudited`,
meant only to shrink) and the `generality-review` agent (`.claude/agents/`), which
`/wp-handover` step 7 dispatches on a branch that touches the table. The judge's first
real run was WP-2002's, on 242 rows (its branch's handover, 2026-10-20): five `fails` and
about eleven `weak`. Two of the fails were rows their author had marked `caller` that in
fact ran by default; one was an agent-skill instruction that made a verb a default path.

**What the filing session measured** (2026-10-20, `origin/main` at 5ecd4d70; re-measured
by an independent Opus review that parsed each PR head's table with `ast`):

- **Twelve open outside PRs touch `_audit.py`**, all from one contributor: #939, 941,
  993, 995, 996, 1005, 1006, 1013, 1014, 1015, 1043, 1048. They add 38 rows and 26
  allow-list names. The contributor chose the tier of 12 rows: 11 at tier 1 or
  `invariant`, the two kinds that need no approval, and one at tier 2. Example: #1048
  tiers `indexing.engines.DRIVEN_MIN_LINES = 6` as arithmetic, while the number is the
  floor below which flagged lines are taken back, which is an action. Nine of the twelve
  also edit `docs/skill/`; four edit a CLAUDE.md (three `indexing/`, one `io/`).
- **The walk misses directories that decide things.** `WALKED` lists the directories
  whose module-level numbers the table holds. Outside it, an AST count of module-level
  numbers finds `io/` 65 (the readers' byte offsets, mostly), `viz/` 44, `gui/` 31,
  `runs.py` 7, `backend/` 4, `_display.py` 3, `solve/` 2, `watch/` 2, and one each in
  `_nearmiss.py`, `compare_app/` and `history/`; 497 inside it. `solve/` (direct-space
  structure solution) holds `cost.py` today, and open PR #1016 adds `solve/chemistry.py`
  with `CLASH_FRACTION = 0.8`, `CLASH_SIGMA_ANG = 0.1`, `PRIOR_SHARE_MAX = 0.25`,
  `DEFAULT_CN = 6`, `INVENTORY_TOL = 0.05` and `PEAK_COUNTS = 1e4`, without touching the
  table.
- **The tripwire points contributors at the allow-list.** `tests/test_audit_table.py`
  says "Give each its tier, or add its name to the baseline for the judge to read", and
  `_audit.row_source` prints a paste-ready row at `unaudited`. `CONTRIBUTING.md` does not
  mention the table. No step of `/pr-review`, the `pr-conformance` agent, `/wp-start`,
  `/steward`, `/issue-review` or `.github/workflows/ci.yml` names the table or the judge.
- **The tripwire checks presence, never content.** A tier-3 row and a tier-2 action must
  carry `grounds` and `approved`; `approved` is a free string. An `invariant` row needs an
  invariance test that asserts its margin (§ The rule), and nothing checks that one exists.
- **CI can see a PR's base.** The lint job checks out at `fetch-depth: 2`, so HEAD^1 of
  GitHub's merge commit is the base; `tests/skill_caps.py` and `tests/skill_surface.py`
  already read it there. WP-2001's third review rejected a git read *inside the suite*
  because CI had no `origin/main` and a local one can be stale. Neither applies to HEAD^1
  in a lint step.
- **WP-2002's PR (#1050) conflicts on `_audit.py`** with #995, #1005 and #1015 (the
  review's `git merge-file` against 2df48c95); the other nine merge clean.

**Rulings (the maintainer, 2026-10-20).**

1. The open outside PRs are tiered at review before they merge. Their author is informed
   and agrees with the milestone's demotions.
2. WP-2007 (indexing) owns `solve/`.
3. The judge argues both sides, without manufacturing fairness: "I don't want a system in
   which a weak case given representation seems stronger than it is." The question for
   the case *for* an action is asked; a side with no evidence reads `none found` in one
   line; each item leads with its verdict and says which side's evidence is stronger.
   No slot is filled for symmetry.

**Why the CI step is not a count.** WP-2002's next session returns five or more rows to
`unaudited` on the judge's findings, an honest growth that a count would fail. A PR that
deletes an unaudited constant, for instance by inlining it out of the walk's sight, would
buy room for a new one. The rule instead: a name absent from the base's `ROWS` may not
arrive at `unaudited`; an existing row may return there.

**Why the CI step reports every delta.** The allow-list catches one of three paths in. A
row that arrives with its author's tier, and a retuned value under an existing tier,
change no baseline name. So the step prints every added, changed and deleted row (and any
`OTHER_RECORD_FIELDS` addition) to the run summary in `skill_surface`'s shape, and fails on
the one rule above. The printout is the item list `/pr-review` hands the judge.

**Why the judge needs the other side.** A tier-3 action costs a ruling from the
maintainer; marking it `caller` or turning it into a report costs nothing, and the judge
argued only against acting. So the cheap path for an author is to decide less, which
DESIGN § Rules, 1 counts as a cost to the caller. Measured in WP-2002: a lane applied
ruling B9 to the peak-position bounds, and the 11-BM NAC cell drifted 5129 ppm against
1117 ppm until the lead restored them.

- The tier of each rule this WP adds: none. It adds no heuristic to the package; its
  tests guard the table.

## Non-goals

- Tiering any row, the twelve PRs' included. `/pr-review` does that with this WP's step;
  the audits (2002–2007) own the existing rows.
- Linting inline literals. Ruff's `PLR2004` finds 88 float-literal comparisons in the
  walked directories (the review, ruff 0.16.7); WPs 2005–2007 are lifting such literals
  into named constants (WP-2002's ruling B14), so a lint waits for them.
- The priority rubric in `docs/wp/TEMPLATE.md`, and the rulebook findings: WP-2009.
- Skill rows: WP-2008. Both received this filing's notes in their `### Inherited`.
- A Stop hook requiring the judge's table. WP-2002's second session skipped the judge on
  148 rows, said so in its log, and the third ran it; the soft gate failed visibly.
- CODEOWNERS on the table: the maintainer authors the WP PRs and GitHub does not let an
  author approve their own.

## Tasks

- [x] **Messages and CONTRIBUTING.** `test_audit_table.py`'s failures and
      `_audit.row_source` point to a tier with its evidence and say a new name may not
      enter at `unaudited`. `CONTRIBUTING.md` gains a paragraph: every new code, record
      field, constant under `WALKED`, default at a seat and `suggestion=` site needs a row
      with a tier and evidence; the judge reads it at review; tier 3 waits for the
      maintainer's ruling. A comment to the contributor is drafted for the maintainer to
      post. This lands before the CI step, so the test and CI never disagree.
- [x] **The walk's partition.** Every top-level entry of `src/rietx` is in `WALKED` or in
      a declared not-walked set with its reason, held by a test (the shape of
      `OTHER_RECORD_FIELDS`: land in one or the other). `"solve": 2007` enters `WALKED`
      (ruling 2), with its rows at `unaudited` on the baseline. Each not-walked reason is
      listed in the handover for the maintainer; `_nearmiss.py` and `runs.py` need a look
      before they are declared out.
- [x] **The judge** (`.claude/agents/generality-review.md`). Accept a PR description and
      the CI step's printout where it now expects a WP file and handover entry. Add the
      question for a row that removes an action, demotes it, or leaves it to the caller
      (`caller`, a report-only code): would every competent refiner act anyway, and what
      does leaving it cost in calls, reruns or a number moved off its reference? Lead each
      item with its verdict; a side with no evidence is `none found` in one line (ruling
      3). An `invariant` row names the test asserting its margin, or the judge says it has
      none.
- [x] **The CI step.** `tests/audit_delta.py`, run in the lint job like `tests.skill_caps`:
      read the base's `_audit.py` at HEAD^1 by `ast` (the baseline is a literal tuple),
      print every row delta with its tier to the step summary, and fail only on a name new
      to `ROWS` at `unaudited`. Cases: a rename passes, a return to `unaudited` passes, a
      new unaudited name fails, a deletion and a retune are listed. It turns lint red on
      the twelve PRs at their next push, so it lands with the `/pr-review` pass over them,
      and the handover says which goes first.
- [x] **`/pr-review`.** A step beside conformance: when the CI printout lists row deltas,
      or a PR adds a module-level number under a not-walked directory, the session
      proposes a tier for each untiered row (as WP-2002's readers did), dispatches one
      `generality-review` per run over every PR's items, posts the proposed tiers as a
      review comment, and groups tier-3 rows by class into the end-of-run batch (WP-2002
      ruled 256 rows as 16 classes). After a ruling it writes `grounds` and `approved` to
      the branch (maintainer edits were allowed on every fork PR checked) or asks the
      contributor. The "classes outsiders miss" list gains two: a skill row telling agents
      to call a `caller` verb, and a one-dataset finding written into a CLAUDE.md as a rule.
- [x] **`/wp-start` step 7.** The restatement names the tier and the kind of ambiguity of
      each flag, threshold or automatic action the item adds. A WP filed before
      2026-10-19 that plans one writes the template's tier line first. No pause for the
      maintainer; the judge still decides at handover.
- [x] **`/steward`.** One line under Red CI: an edit to a row's tier, evidence or value,
      or to the allow-list, goes back through the judge before the push.
- [x] **Records.** `generality.md` § Acceptance's "a new heuristic cannot land unaudited"
      row names this WP beside 2001.
- [x] Skill: none; nothing here reaches an agent driving rietx.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_audit_delta.py tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
```

Plus two runs recorded in the handover: the CI step against one of the twelve PRs'
base and head, printing its deltas and failing on its new unaudited names; and the judge
on that PR's items, its table showing at least one `none found` side or saying why none
arose.

## References

- `docs/milestones/generality.md` § The rule, § Decisions with the maintainer (the
  2026-10-20 entry); `docs/DESIGN.md` § Rules, 1 and 4.
- WP-2001 (the guard); WP-2002's handover of 2026-10-20 on branch
  `wp2002-single-fit-actions` (the judge's first run, the B9 over-reach).
- `tests/skill_caps.py`, `tests/skill_surface.py` (the base read at HEAD^1).

## Handover log

### 2026-10-20 (2nd session) — the guard reaches outside PRs, unwalked directories and fixes after the handover; closed

Until today the audit table's guard worked only on the maintainer's own branches.
Its test told an outside contributor to put a new item on the list of rows still
waiting for their audit. Now a new row has to arrive with a tier and its evidence.
CI's lint job compares each pull request's table with main's, prints every row it
adds, changes or deletes, and fails a name that arrives at `unaudited`. Ten of the
twelve open contributor PRs fail it at their next push, on 26 names, which is the
point. The judge reads outside PRs and post-handover fixes too. It now argues the
case for an action a change removes as well as the case against one it adds, and
writes "none found" for a side with nothing behind it. Every top-level module is
walked or declared out with its reason. The judge's reading of those reasons put
nine more files under `io/` and `gui/` into the walk, and turned up a possible
silent occupancy rounding in the FullProf reader.

**Done** (PR #1070):

- Messages: `_audit.row_source` prints a row with `tier="?"`, `ambiguity="?"` where
  the kind needs one, and `evidence=""`, each failing a test until filled
  (`_audit.PENDING`). `test_audit_table.py`'s failures share one text (`NEW_ROW`)
  saying a new name may not enter at `unaudited`. `CONTRIBUTING.md` § A heuristic
  needs its tier. The comment to the contributor is in the PR's description.
- Partition: `_audit.NOT_WALKED` (17 entries, each with its reason) and
  `test_every_top_level_entry_is_walked_or_declared_out`. `WALKED` gained `solve`
  (2007, ruling 2), `project.py` (2002, no number today) and, after the judge, nine
  files under 2006: `io/formats/{dif,gsas,peaklist}.py`, `io/instrument_profile.py`,
  `io/projects/{fullprof,registry,topas_input}.py`, `gui/{imports,symmetry}.py`.
  38 constants entered at `unaudited` on the baseline (2 + 36); the constant count
  comment reads 584.
- The judge (`.claude/agents/generality-review.md`): takes a PR description and the
  CI printout, asks the case for acting (row 4) beside the case against (row 3),
  leads each item with its verdict and the stronger side, `none found` in one line,
  names an `invariant` row's margin test, and hears the scope declarations
  (`OTHER_RECORD_FIELDS`, `NOT_WALKED`, `WALKED`, `DEFAULT_SEATS`).
- CI step: `tests/audit_delta.py` in the lint job (laned). A rename pairs on kind,
  leaf and value; a constant or default entering with a new `WALKED` entry or seat
  passes only where the base already defined it; every other new name at
  `unaudited` fails with a `::error` on its line. Runs after an earlier lint step
  fails (`!cancelled()`).
- `/pr-review` step 6b, `/wp-start` step 7's tier line, `/steward`'s Red CI line,
  `/wp-handover` step 7's item list, root CLAUDE.md's audit bullet, generality
  § Acceptance's row.
- `/code-review high --fix`: 7 findings, 6 fixed in d9673a07 (a walk exemption
  over code the PR itself creates, the step skipped after a ruff failure, the
  judge not hearing the declarations, `RECORD_SCHEMAS` unreported, an empty
  `frozenset()` crashing, copied kind lists untied). The seventh, `gui`'s reason
  naming a number that decides, was left to me and is fixed by the walk above.

**Measured** (`[dev]` venv, darwin/arm64):

- Fast suite on the final tree: 10 851 passed, 191 skipped, 2 xfailed, 4:16 alone
  on the machine; the one failure in that run was the stale WP index, regenerated
  in step 8 and green after. Added: 17 tests (15 in `test_audit_delta.py`, 2 new
  names in `test_audit_table.py`, one replacing `test_row_source_round_trips`),
  0.13 s together, none near the tail. Full suite not run: the change cannot move
  a measured number (`_audit` is imported by tests alone).
- The twelve PRs, read by `tests/audit_delta`'s pure half against each merge base:
  38 rows added, 26 new at `unaudited`, 12 tiered by their author (11 at 1 or
  `invariant`, `indexing.screen.SCREEN_WINDOW_LINES` at 2). Lint fails 10; #1015 and
  #1048 pass. Matches the filing's count exactly.
- WP-2002's branch against its merge base: 7 added, 1 renamed
  (`PHASE_SUPPORT_SIGMA`, `model.forward` to `schemas.plan`), 234 changed, 9
  deleted, 0 failures. `_audit.py` merges clean with it (`git merge-tree`).
- Module-level numbers outside the walk before the judge (live values, tuples
  counted): `io` 79, `viz` 44, `gui` 32, `runs.py` 9, `backend` 4, `_display.py` 3,
  `history` 2, `solve` 2, `watch` 2, `_nearmiss.py` 1, `compare_app` 1. The
  filing's AST counts (io 65, gui 31, runs 7, history 1) left out tuples.
- Lanes (`session_usage.py lanes`): main 97 requests, peak 291K, $6.98; one lane.

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | model | lane $ | main $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | ci-step | 25 | 46 | 216K | 72K | 39K of 39K | 5 | 16K | 2 | 0 | opus-5-5 | 2.38 | 0.44 | 4.73 | +1.78 |

  Selective policy on the replay (u = 39K, mo = 5, d = 16K): lane when main > 150K
  and item ≥ 20 requests, 219 sessions, −10 %.

**Acceptance runs** (on #993, merge base 2df48c95, head e3b1b8ce):

1. The CI step: "4 added, 0 renamed, 0 changed, 0 deleted, 3 new at 'unaudited'",
   failing on `PEAK_NO_INTENSITY`, `PEAK_NO_INTENSITY.suggestion` and
   `PEAK_POSITION_AT_BOUND.suggestion`, and listing `PEAK_POSITION_AT_BOUND` at
   tier 1. Run through the pure half on `git show` texts, since the worktree held
   this branch.
2. The judge, from the edited prompt (general-purpose on Opus reading the agent
   file; this session had registered the old one): `PEAK_POSITION_AT_BOUND` weak
   (the statement is tier 1; its warning-or-info split rests on `PEAK_FDR_Q` and
   on open #951, and the row does not tier it); `PEAK_POSITION_AT_BOUND.suggestion`
   fails (a new name on the baseline; its "usually a seed on a tail" clause is
   rietx's own with no count); `PEAK_NO_INTENSITY` fails as entered, the case for a
   tier-1 record being stronger, its row 3 reading "Against the report itself:
   none found."; `PEAK_NO_INTENSITY.suggestion` fails ("there is no line there"
   after a 1σ non-detection is a kind-3 verdict). Checked at their lines: `weak_line`
   is absent from `PEAK_UNUSABLE_FLAGS` (`schemas/indexing.py:736`), and
   `test_peak_bounds.py:143` asserts `value == 0.0`.

**Generality** (the judge on this branch, before the nine files were walked; unedited):

**`rietx.solve.cost.NAMED_REFLECTIONS` and `rietx.solve.cost.NUISANCE_RCOND` (entered at `unaudited`, names added to `UNAUDITED_BASELINE`)**

**Verdict: holds.** The judge's rules name this baseline reason explicitly: a directory newly added to `WALKED` (the directories whose module-level numbers must each have a table row). I found no evidence against it.

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| Why on the baseline | WP-2014 ruling 2: "WP-2007 (indexing) owns `solve/`." Task 2: "`"solve": 2007` enters `WALKED` (ruling 2), with its rows at `unaudited` on the baseline." | The base's `WALKED` has no `solve` entry, and this diff adds it. The diff does not touch `solve/cost.py`, so both constants already exist on main. They are existing items entering the table, not new heuristics. `tests/audit_delta.py` (the new CI step that lists table changes) reports both as entering with a new walk entry and passes them. `test_a_constant_in_a_file_the_base_did_not_walk_passes` pins this exact name. | holds |
| 1. What it decides | none given (left to WP-2007) | `NUISANCE_RCOND = 1e-12` is the cutoff for the pseudo-inverse of the background-and-impurity normal matrix. Each column is rescaled to unit size first. Any direction with an eigenvalue below 1e-12 of the largest is dropped. `NAMED_REFLECTIONS = 5` is how many hkl labels a refusal message names before it says "and N more". | not judged (WP-2007's audit) |
| 2. Kind of ambiguity | none given | Not judged. | — |
| 3. Case against keeping them on the baseline | — | none found. Tiering them here would do WP-2007's audit inside WP-2014, which goes against the ruling. | — |
| 4. Case for | ruling 2, as above | The ruling is the case. A note for WP-2007: § The rule puts "a numerical floor such as `rcond`" at tier 1, and a message's length decides no answer. Both should be quick to audit. | holds |
| 5–7. Tier, families, record field | none given | Left to WP-2007's audit by the ruling. Not judged. | — |

Would change the verdict: a module-level number under `solve/` on this branch that is not on main's tree, or a ruling that WP-2014 tiers `solve/` itself.

**`"project.py": 2002` added to `_audit.WALKED`**

**Verdict: holds.** The case for walking the file is the stronger one. For the case against: none found.

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `_audit.py`, comment above `NOT_WALKED`: "An entry is walked where a module-level number in it could move a fitted value, a verdict, or how a file is read (WP-2014, which walked `solve` and `project.py`)." | `project.py` holds no module-level number today, so the entry adds no row. What it decides is that any future number there gets a row with a tier. | holds |
| 2. Kind of ambiguity | — | Does not apply. This is a scope declaration, not a heuristic. | — |
| 3. Case against | — | none found. It costs no audit work today. | — |
| 4. Case for | as row 1 | Code in `project.py` already decides things that fall inside the comment's own test. `fitted_mask` decides which channels the next run fits. `Project.open` picks the file's first GSAS bank for a project saved before banks were recorded. `Project.fit` and `Project.run_stage` take their `mode`, `two_theta_limits` and `telemetry` defaults from the project document. A number added beside any of these would move a fitted value or how a file is read. So a truthful reason for declaring the file out could not have been written. | holds |
| 5. Owner | `WALKED`: 2002 (the single-fit-actions audit) | 2002 is defensible: the fit wrapper's defaults are its seam. The reopen checks and the bank fallback read a file back, which is WP-2006's seam (readers, crystallography and GUI codes). | holds; 2006 also fits |
| 6. Families | — | Does not apply. | — |
| 7. What records it | — | `test_every_top_level_entry_is_walked_or_declared_out` and `test_the_declared_scope_resolves` hold the entry. | holds |

Would change the verdict: nothing I found. If the first number to land in `project.py` belongs to reading a file back, that would argue for owner 2006 instead of 2002.

**`_audit.NOT_WALKED` (every top-level entry the walk leaves out, each with a reason)**

**Verdict: weak.** The partition is sound, and 17 of the 19 reasons hold. The `io` and `gui` reasons do not cover module-level numbers that decide one of three things: how a file is read, whether a model edit is allowed, or what another program computes from a file rietx writes. For those numbers the case against declaring them out is stronger. One of them, `fullprof._OCCUPANCY_RTOL`, contradicts its own comment.

| Entry and numbers | Author's reason (`_audit.NOT_WALKED`) | What the numbers decide | Verdict |
|---|---|---|---|
| `io`: `projects.fullprof._OCCUPANCY_RTOL = 5e-3` | "translator tolerances that compare a value at the precision the other program prints it" | Decides whether a FullProf phase is built or refused. For each site, `to_structure` computes Occ×M_general/M_site. If every ratio is within 0.5 % of the largest, it writes `occ = 1.0` on every site and emits no diagnostic. The constant's own comment puts the file's rounding at "~2e-5". It also says "a real partial occupancy is refused rather than rounded off". The 5e-3 bar is 250× that rounding. A site at chemical occupancy 0.996 beside fully occupied sites is therefore built at 1.0 with nothing said. I read this from the code and did not run it. The same constant also gates the magnetic phase's Scale×f² match, which decides build or refuse. | reason fails |
| `io`: `projects.fullprof._DISPERSION_ATOL_E = 0.01` e; `_RHOMBOHEDRAL_LENGTH_RTOL = 1e-3`; `_RHOMBOHEDRAL_ANGLE_ATOL = 0.01°` | same | `_DISPERSION_ATOL_E` decides whether an X-ray `.pcr` that states f′/f″ is read or refused. When it is read, the fit uses rietx's Cromer–Liberman pair, not the file's. 0.01 e is 20× FullProf's three-decimal print step. Its comment sets it below the 0.45 e disagreement it cites for Fe at 1.85 Å. The rhombohedral pair decides whether a bare R symbol is read on rhombohedral axes (`:R`) or hexagonal axes (`:H`), which changes every site's multiplicity by a factor of 3. Both are safe by margin: the f′ error is at most 0.01 e, and the hexagonal cell's angles are 30° away. But neither is a print-precision comparison. The R-setting choice is a sibling of the one `crystallography/` makes, which the walk covers under 2006. | reason incomplete |
| `io`: writer defaults `projects.topas_input.CALC_POINTS_PER_FWHM = 16`, `projects.topas_input.DEFAULT_RADIUS_MM = 217.5`, `instrument_profile._PRM_CUTOFF = 0.001` (the author flagged the first two) | same | Each is a number rietx writes into another program's input file. `CALC_POINTS_PER_FWHM` sets TOPAS's `convolution_step`, the subdivision of TOPAS's calculation grid, so it moves what TOPAS computes from the file. Its docstring measured one case (`nacl_pspline`, TOPAS 6): a step of 1 left TOPAS 6.3e-2 of the peak away from rietx, and 16 points per FWHM brought that to 2.6e-3. `DEFAULT_RADIUS_MM` is claimed to cancel: "a convention of the file, not a measurement". That is a claim that the answer does not depend on it, and no test is named beside it. `_PRM_CUTOFF` is the peak-tail cutoff written into the PRCF header of a GSAS-I `.prm`, which GSAS-I uses when it computes. No source is given beside it. None of the three is a byte offset, field width, unit factor or print-precision tolerance. | reason incomplete |
| `io`: sniff bounds (the checks that decide which reader claims a file) `projects.registry.INP_SNIFF_BYTES = 65 536`, `formats.gsas._GSAS_TIME_MAP_SCAN_BYTES = 65 536`, `formats.dif._MIN_ROWS = 3`, `formats.peaklist._MIN_ROWS = 8` | same | Each decides which reader claims a file, and so how it is read. A TOPAS `.inp` whose first block opener sits past 64 kB is not recognised. A GSAS file whose step table pushes its first bank past 64 kB "stays unsniffed" (`io/CLAUDE.md`). Three hkl rows make a `.dif` a refused peak list. A `.pks` or `.udi` with fewer than eight plain numeric rows is refused, not read. The 4 kB window these extend, `formats.base.HEAD_BYTES`, is walked, because `io/formats/base.py` is in `WALKED`. A miss here refuses the file and does not misread it, so the stakes are low. | reason incomplete |
| `gui`: `imports.WAVELENGTH_RTOL = 5e-4` (author flagged) | "imports.WAVELENGTH_RTOL names a header's anode, and no two anodes lie within 13 %" | The reason covers only the wrong-anode side. The same bar decides the other branch of `suggest_instrument`. A header wavelength outside 5e-4 of every anode's Kα1, Kα2 and weighted mean is pre-filled as a single-wavelength `debye_scherrer` instrument: capillary geometry, no Kα2. If the file also names an anode, nothing is pre-filled. A Mo header written to two decimals, 0.71 Å, sits at least 9.6e-4 from every Mo candidate. I computed that from standard Mo values and did not read `_KA_DOUBLETS` this session. With no anode named, such a file is offered as a capillary at one wavelength. The person sees the pre-fill with its "why" sentence and can change it. If they accept it, every fitted value moves. A pre-fill is a suggestion the package prints, which the milestone counts as a heuristic. | reason incomplete |
| `gui`: `symmetry.ORBIT_COLLISION_TOL = 1e-3` (fractional), `symmetry.POSITION_TOL = 1e-6` | "the GUI server and 3D viewer: ports, payload caps and drawing tolerances" | Neither is a drawing tolerance. Each gates a model edit. `ORBIT_COLLISION_TOL` decides whether a space-group change is blocked or passed. The GUI blocks it (`blocked: true`) when sites merged by the new symbol have occupancies summing past 1. An over-occupied pair just outside 1e-3 is passed. Its comment ties the value to the 1e-3 that `crystallography.wyckoff.site_constraints` uses, in a directory the walk covers. `POSITION_TOL` decides whether a typed coordinate is refused as lying off the site's allowed directions. Its comment argues it from CIF print precision. Both have margin, since coordinates print to 1e-4 or finer. The point is that each is a verdict, and the reason does not name one. | reason incomplete |

**Case for the declaration as written.** The table's docstring records a walk over all of `src/rietx` that found 619 constants. It says the surplus is "byte offsets in file readers, pixel sizes in the 3D viewer and schema defaults". `io` alone holds 79 module-level numbers and `gui` holds 32 (from `unwalked.txt`), most of them format facts and drawing sizes. Walking either directory whole would bury the dozen decisions above under about 100 tier-1 rows. The mechanism already supports a cheaper fix: a partial entry such as `io/readers.py`, which the new partition test accepts while `io` stays declared out.

The other `io` numbers the author flagged fit the stated reason:
- `fullprof._USER_B_ATOL_FM` (1e-3 fm) matches the precision Sears prints b to.
- `fullprof._MAGNETIC_MATCH_ATOL` (1e-4) matches the precision a `.pcr` prints a cell, a coordinate and a B.
- `fullprof._CELL_TIE_MULTIPLIER_TOL` (1e-6) is a float guard on values that are equal by construction.
- `fullprof._NAM_WIDTH = 4` is a field width.
- `instrument_profile.INSTPRM_SHL_FLOOR` is GSAS-II's own floor, which the writer reports.
- `recipe.GSASII_DEFAULT_SIZE_UM` and `GSASII_DEFAULT_MICROSTRAIN` are GSAS-II's defaults, which the reader reports and declines.

**`runs.py`.** Its reason holds against the stated criterion. The reason does not list `MAX_DEPTH = 8` or `MAX_RUNS = 500`, which bound the run listing. The criterion itself leaves out one kind of action. `RETENTION_MAX_BYTES` (1 GiB) and `RETENTION_MIN_AGE_SECONDS` (7 days) decide which run records the package deletes without being asked. Whether that belongs in the milestone is the maintainer's call.

**Every other entry: none found.** These are `__init__.py`, `_about.py`, `_audit.py`, `_display.py`, `_nearmiss.py`, `backend`, `capabilities.py`, `cli.py`, `compare_app`, `data`, `examples.py`, `help.py`, `history`, `skill.py`, `viz` and `watch`. `_nearmiss.CUTOFF` only chooses which names a "did you mean" hint offers. `backend`'s two column bars back the `column_agreement` test metric, and `linalg64.py` has no runtime gate on them. I had no search tool, so I could not check for callers outside `linalg64.py` and `torch_backend.py`.

Would change the verdict, either of:
- Walk the files as partial entries under 2006: `io/projects/fullprof.py`, `io/projects/topas_input.py`, `io/instrument_profile.py`, `io/projects/registry.py`, `io/formats/gsas.py`, `io/formats/dif.py`, `io/formats/peaklist.py`, `gui/imports.py` and `gui/symmetry.py`.
- Or rewrite the `io` and `gui` reasons to name the sniff bounds, the writer defaults and the edit gates, each with why it needs no tier.

For `_OCCUPANCY_RTOL` in particular, the verdict would change with either a record that no file it reads carries a partial occupancy within 0.5 % of full, or a diagnostic whenever it rounds one.

The author's answer to `weak`: walked the nine files as partial entries under 2006
(057f479e), and narrowed the `io` and `gui` reasons to what is left.

**The not-walked reasons, for the maintainer** (`_audit.NOT_WALKED`): `__init__.py`,
`_about.py`, `_audit.py`, `capabilities.py`, `cli.py`, `examples.py`, `help.py`,
`skill.py` hold no number and decide nothing; `_display.py` print widths;
`_nearmiss.py` difflib's own 0.6 "did you mean" cutoff; `backend` two test bars and
a memory chunk size; `compare_app` a port; `data` bundled tables; `history` a printed
row count and a read chunk; `runs.py` telemetry (flush, retention by bytes and age,
Windows error codes); `viz` figure sizes, colours, point caps and the first 3D
view; `watch` timeouts and a cache lifetime; `io` and `gui` beyond the walked files,
byte offsets, field widths, unit factors, size caps, ports and drawing tolerances.

**Gotchas.** An agent type is registered when the session starts, so an edited
`.claude/agents/*.md` runs only through `general-purpose` told to read the file
(`/wp-handover` step 7 already says so). `tests/audit_delta.py` reads the base with
`git show`, so a local run needs `RIETX_CAPS_BASE` or an `origin/main`.

**Next**, in order:

1. The maintainer reviews and merges #1070, and posts the contributor comment from
   its description. This goes **before** the `/pr-review` pass, because step 6b and
   the CI step both need to be on main for the bench to run them.
2. `/pr-review all` over the twelve: step 6b proposes tiers for the 26 names and
   re-reads the 11 author-tiered rows at 1 or `invariant`, one judge for the run,
   tier-3 rulings batched by class.
3. Three calls for the maintainer, none blocking: whether retention in `runs.py`
   belongs in the milestone; `project.py`'s owner (2002 or 2006); and whether to
   keep the partial `io`/`gui` walk or list those nine files' numbers by hand.
4. WP-2006 audits the 36 new rows and checks `_OCCUPANCY_RTOL`; WP-2007 tiers the
   two `solve` rows (both in their `### Inherited`).

- **2026-10-20** — created, from a planning session on the maintainer's question whether
  the generality guard can reach the rest of the tooling. Checked against the tree at
  5ecd4d70 and against the twelve PRs' heads. No open WP owns it: 2001 is closed; 2009
  owns the rulebooks and the rubric, not the review commands or CI; 2007 owns `solve/`'s
  rows, not the walk's partition. The plan was reviewed twice: by the filing session, and
  by a fresh Opus agent given only the goal, the plan and its claims to verify. The second
  review added the partition, the messages, the new-name rule in place of a count, the
  three paths and the judge's other side, and corrected the filing session's PR count
  (twelve, not ten). Filing also wrote notes into 2007, 2008 and 2009. Next: `/wp-start`.
