# WP-2005 — `refine.py`'s codes and its inline literals

Milestone: generality · Status: 🔄 2026-11-09 — part 1 (the inventory, no tiers) in PR #1486; part 2 waits on the maintainer's answer on the gate after 2004
Track: The audits
Depends on: 2002
Priority: P3 2026-10-23 — 2002 closed, its last item touching no code here; codes, not actions; a verdict here is a flag the caller reads, and the workaround is to read past it

## Goal

Each of the 61 diagnostic codes raised in `src/rietx/refine.py` is in the audit table with
a tier, and each inline literal that gates one (about 30) is either a named constant in the
table or recorded as tier 1. A tier-3 verdict that fails either ground is demoted: its
`level` drops to `info`, or, where the threshold was its trigger, the code becomes an
`info` record with no threshold (the record § Demotion).

## Context

The rule is `../milestones/generality.md` § The rule. 2002 owns the *actions* in this file
and lands first; this WP owns the codes, which are what an agent reads.

`refine.py` is 9 587 lines and raises 61 codes (`grep -o 'code="[A-Z0-9_]*"'`, 2026-10-18).
Each has an explanation in `rietx.help.DIAGNOSTIC_HELP` (WP-1985) and a `level`. The
open's count found about 30 inline numeric literals in comparisons, two named by the
second review: `< 0.7` in the flat-plate thickness test (`ABSORPTION_PLATE_THICKNESS`,
~line 6819) and `>= 2.0` further down (~line 8467). An inline literal is invisible to
2001's tripwire, which walks module-level constants, so this WP lifts each that gates a
verdict into a named constant with its value in the table, or records why it is tier 1 (a
count, a dimension, a physical limit).

*Superseded in part, 2026-11-09 (part 1, at `5ae35232c`):* `refine.py` is 12 241 lines and
raises 69 codes, so with the five below the WP covers 74. Of 34 numeric literals in the
raising functions and the same-file functions they call, 5 are thresholds, 4 of them in
`refine.py`: the two above (now ~lines 8889 and 10696), the two-FWHM edge of the low-angle
region (~10672) and the half of sin θ_min that sets `ROUGHNESS_OUTSIDE_REGIME`'s info band
(~11905). The other 29 are units, arithmetic, counts, listing caps and numerical floors.
`2005-batch/README.md` has the counts and what the walk cannot see.

**Five codes no seam names come here too**, since each is raised beside a fit rather than
in a reader or a report: `BACKGROUND_ORDER_AT_CAP` (`background/select.py`),
`BRINDLEY_OUTSIDE_REGIME` and `MICROABSORPTION_SKIPPED` (`optimize/qpa.py`),
`DECLARED_RANGE_RESTORED` and `DECLARED_RANGE_NOT_RESTORED` (`schemas/migrate.py`). The
four in `strategy/` are 2002's.

**Families.** The size-flag thresholds are calibrated on one 1 213-record archive (~line
9069): many files, one population, one family. Count by lab, instrument and material.

**What the caller reads.** Every code carries an explanation (WP-1985), and under
DESIGN.md § Rules, 3 that explanation is what teaches the reader, agent or person. 70 of
the tree's codes are not mentioned in the agent skill, and under the skill's role (the
record § Decisions) that is no defect. Whether the skill routes a code is no evidence for
its tier.

### Inherited

- **From WP-2003 (2026-11-02, fifth session, PR #1310): every `error`-level code now drives a
  chain action.** Batch C2 question 5 landed `schemas.sequential._rejected`: a kept attempt
  that diverged *or carries any diagnostic at level `error`* escalates the series ladder and,
  still rejected after its last rung, is quarantined (seeds no successor, joins no median, makes
  no step). So each error-level code's threshold is now a trigger of a default series action,
  not only a message: `MODEL_FAR_FROM_DATA_RWP` (0.8, `refine.py:9684`, tier 3 on its own row)
  above all, which is what restored the path guide's 800 K rescue and quarantines tut05-broken's
  scan12. When this WP tiers a code's level or threshold, say in its row that lowering it to
  `warning` or moving the threshold changes what a series carries.
- **From WP-2037 (2026-10-24, second session, PR #1145): this WP's codes are the view's loudest, so their responses decide how quiet it gets.** Over the eight `rietx compare` standards' fits (darwin/arm64), `HIGH_CORRELATION` is 44 % of all warning rows, `FLAT_DIRECTION` takes the running total to 69 % and `FLOOR_HIT` to 87 %. On cpd-1a under `qpa`, 49 of 57 warnings still print in full, 24 of them `HIGH_CORRELATION` and 22 `FLAT_DIRECTION`, because a code still on `_audit.RESPONSE_BASELINE` stays a warning under every purpose. Giving each a response (and its `where`-derived purposes) is what quiets the view; each one given `response="warning"` adds its pair to `tests/silence.py` (`FLOOR_HIT` has one). `rx.diagnostics_summary` and `python -m tests.suite_alarms` re-measure the numbers.
- **From WP-2002 (2026-10-21, 4th session): tier 2 names seven programs.** `docs/milestones/generality.md` § The rule's tier 2 now reads "by default in an established Rietveld program": GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and EasyDiffraction, the list rietx-bench runs (the maintainer's instruction). A row resting on a program default names the programs it checked and what each does; a program doing otherwise by default is a dissenter, one without the feature is neither. What each does on peak windows, staging, roughness starts, width limits, dispersion, solver, mode and background seed is in `docs/practice.md`; where each program's manual or source sits is in the maintainer's memory (`foreign-code-sources-on-disk`), and rietx-bench's `tools/` holds BGMN, MAUD, RIETAN-FP and EasyDiffraction's environment beside GSAS-II and FullProf.
- **From WP-2002 (2026-10-20, PR #1050): `OCCUPANCY_ABOVE_ONE` is new** (`refine._occupancy_flag_diagnostics`, a warning when a refined occupancy exceeds 1, from the B9 ruling). With no significance gate it fires on counting noise about half the time on a freely refined full site (synthetic LaB6, 1.032 ± 0.025). Whether to gate it is with the maintainer; the message quotes the distance above 1 in esds.
- **From WP-2002 (2026-10-20, PR #1050): `HUMP_MIN_WIDTH_MULT` is a diagnostic threshold** (it gates `HUMP_TOO_NARROW`; it also floors a hump's width in the extinction screen, `indexing/extinction.py:737`), so it belongs with the other diagnostic-only constants handed here (B13). The suggestions of `SIZE_UNUSUALLY_SMALL` and `STRAIN_UNUSUALLY_LARGE` said a finite `Parameter.max` silences them; neither reads `max`, and both now say the flag changes nothing in the fit.
- **From WP-2002 (2026-10-19, PR #1050).** 2002's batch class B13 proposes handing 34 constants to this WP, pending the maintainer's ruling. Each is the threshold of a code raised in `refine.py` and gates no action. The list with each code is `2002-batch/batch.md` § The B13 hand-off table, and each row's provenance is in `2002-batch/inventory.json`. If WPs 2005-2007 are cancelled at the gate after 2004, these rows need another home.

- 2026-10-31, from the issue triage (issue #1215): `AIR_SCATTER_UNDECLARED`
  fires on clean data whose background is too stiff at the low edge. On a
  synthetic rutile Bragg–Brentano family (Cu Kα1 + Kα2, rietx's own forward
  model, no air scatter in the truth) it fires on 20/20 clean patterns under
  `auto_background`'s P-spline and on 0/20 under the truth's own 4-term
  Chebyshev: the 1/(2θ) column removes χ² because the spline cannot follow the
  low edge (#833's comment, WP-1931). The issue proposes a message that names
  the measurement ("a 1/(2θ)-shaped low-edge residual removes X % of χ²") and
  lists a background too stiff at the edge beside air scatter, and applies the
  unanimity test to the suggestion: a refiner whose spline is stiff at the
  edge would not declare air scatter. Checked against the tree at d87c8cc91:
  the code is raised at `refine.py:9715`; `AIR_SCATTER_UNDECLARED` and
  `AIR_SCATTER_UNDECLARED.suggestion` are both untiered in `_audit.ROWS`
  (lines 547, 4067) and on the baselines (4354-4355); its two constants
  `AIR_SCATTER_UNDECLARED_FRACTION` 0.005 and `_SCORE` 25.0 are rows
  2867-2868. The 20/20 count is the issue's, not re-run here. This bears on
  the code's tier and its suggestion row when this WP tiers it.

- 2026-10-31, from the issue triage (issue #1219): `LOW_ANGLE_UNMODELLED`'s
  suggestion has a dissenter and erases its own evidence. Shown a low-angle
  excess, competent refiners act three ways (model air scatter; cut a
  beam-stop tail; model and keep a real diffuse component), and the help entry
  already says the package does not choose between them. On a synthetic family
  with a planted low-angle rise (cubic perovskite capillary, rise 20× the mean
  background at 5°, 3° decay), the code fired on 12/12 fits cut at 9-16° and
  suggested "Raise the pattern's lower limit to 22.6°"; cut at 22°, it fell
  silent on 3/3, χ²_red read 0.98-1.00, and 42 % of the file's counts lay
  below the cut with nothing reporting it. WP-1517's row 6 records the same
  steer from an agent round: the agent cut past a strong line and nothing said
  so. The issue proposes keeping the statistic and message, dropping the
  `suggestion=`, adding the signed residual over the first 1°, and pointing at
  a new `result.fit_range` (the new WP); the help entry loses its "Raise the
  lower limit … or add the air-scatter term" sentence the same way. Checked
  against the tree at d87c8cc91: the suggestion is built at `refine.py` ~9636
  as quoted; `LOW_ANGLE_UNMODELLED` (`_audit.py:739`) and
  `LOW_ANGLE_UNMODELLED.suggestion` (4171) are untiered; the help text at
  `help.py` ~3037 carries the "Raise the lower limit" sentence. The 12/12 and
  3/3 counts are the issue's, not re-run here. The retext is a `suggestion=`
  site, so it goes in this WP's batch to the maintainer.

## Non-goals

- The holds, releases, seeds and bound tests: 2002.
- Codes raised elsewhere: `report/` 2004; `io/`, `crystallography/`, `gui/` 2006;
  `indexing/` 2007; `sequential.py` and `multi.py` 2003; `strategy/` 2002. The five
  named above are the whole remainder.
- Rewriting an explanation's text (1985's voice stays); only `level`, the threshold and
  whether the code exists.

## Tasks

- [x] Inventory: the 61 codes with raise site, `level`, the threshold or condition, the
      explanation's claim, the kind of ambiguity its verdict has (DESIGN.md § Rules, 1),
      and how many tests touch it. 74 codes on 2026-11-09: `2005-batch/inventory.json`.
- [ ] The inline literals: each lifted to a named constant (table row with value) or
      recorded tier 1 with the reason. The 29 tier-1 literals are recorded with their
      reasons in `2005-batch/judgements.json`; the 4 thresholds in `refine.py` wait for
      their tiers, since a new constant enters the table tiered. The fifth threshold
      refuses a Chebyshev scan in `background/select.py` and gates no code, so it stays.
- [ ] Tier each code per part, with evidence and families.
- [ ] The batch to the maintainer; rulings dated into the table.
- [ ] Approved demotions: `level` to `info`, or, where the threshold was the trigger, the
      code replaced by an `info` record with no threshold that states the number (the
      record § Demotion); the explanation's observation sentence updated where the verdict
      went; the release notes staged for every removed or renamed code.
- [ ] Goldens re-pinned only if no further from reference (a code change moves no number;
      a lifted literal must not either, pinned by a bit-identity check before and after).
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: none here. A code that keeps a verdict is explained by its
      `DIAGNOSTIC_HELP` entry (DESIGN.md § Rules, 3). List each skill row that names a
      demoted code, for 2008 (the record § Decisions, the skill's role).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- `docs/milestones/generality.md`; WP-1985; WP-1076 (a declared name is a claim).

## Handover log

- **2026-11-09** — part 1, the inventory, in PR #1486 (ghostshift runner, unattended).
  WP-2005 now has a measured inventory of what it audits, built from the tree by a script
  rather than counted by hand. It covers 74 codes, not 61. It also shows that the "about 30"
  inline literals were mostly units and arithmetic: only four literals in `refine.py` gate a
  verdict or its suggestion. So lifting literals into named constants is a four-row job, and
  the WP's weight is in tiering 64 unaudited codes. The inventory's first reading puts 59 of
  the 74 verdicts in the kind the data settle (an act recorded, a fact of the arithmetic, a
  published range), 4 in the kind the data can rank, and 11 in the kind the data cannot settle.
  Those 15 are where demotions would come from. Nothing was tiered, lifted or demoted.
  *Question for the maintainer*: the milestone puts a gate after 2004 (generality.md § The
  order: the maintainer decides on 2002–2004's counts whether 2005 to 2007 run). WP-2004 is
  still ⬜, so this session stopped at part 1, as WP-2006's part 1 did. Should part 2 (the tiers,
  the four lifts, the batch) wait for that gate, or go ahead now?
  *Done*: `docs/wp/2005-batch/` after `2006-batch/`. `collate_inventory.py` derives raise sites,
  levels, guarding conditions, the named constants each raising function and its same-file helpers read
  (with tier and value), the explanation's first sentence, the code's audit rows and the tests naming it.
  `judgements.json` holds the hand-written part: condition and kind of ambiguity per code,
  role per literal. The script refuses a code or literal with no judgement, a judgement for one
  that is gone, and a text cut short. The Context's 2026-10-18 counts are superseded in place,
  dated. Task 1 is ticked. On task 2, the 29 tier-1 literals are recorded with reasons; the 4
  thresholds are left, since a new constant in `refine.py` enters the table tiered
  (`tests/audit_delta.py`).
  *Measured* (at `5ae35232c`, darwin arm64, `.venv` `[dev]`, Python 3.12): 69 codes in
  `refine.py` (12 241 lines) plus the WP's five, at 78 raise sites; 64 codes `unaudited`, 8 tier
  1, 2 tier 3. 39 named constants read by a raising function or a helper it calls: 21 unaudited, 10
  tier 3, 4 tier 2, 3 tier 1, 1 invariant. Literals: 12 unit, 8 arithmetic, 3 count, 3 listing cap, 3 numerical floor, 5
  threshold. The four gating ones are `0.7` (`ABSORPTION_PLATE_THICKNESS`, ~8889), the 2σ
  channel test (`LOW_ANGLE_UNMODELLED`'s suggestion, ~10696), the two-FWHM low-angle edge
  (~10672) and the half of sin θ_min (`ROUGHNESS_OUTSIDE_REGIME`'s info band, ~11905). The fifth
  refuses a Chebyshev scan in `background/select.py`. Fast selection
  (`-m "not slow"`, `-n 2` through the Mac test gate, pearl not answering): 14 341 passed,
  415 skipped, 32 xfailed in 992 s, on `48acd5cd0`; the branch adds no test, and the review's
  fixes after it touched only `docs/wp/` (`tests/test_docs_consistency.py` 25 passed after them).
  *Review*: an Opus subagent reviewed the branch diff in place of `/code-review`, which cannot be
  pointed at a worktree from a ghostshift runner. It reproduced `inventory.json` byte for byte
  and re-derived every count. Its five should-fix findings were all taken (commit `cf2fa9d6e`):
  the walk now lists early-exit guards, resolves re-exported and attribute-read constants, reads
  helpers' constants and counts tests reaching a code through a same-file helper; one count in
  the README was wrong (ten, not four); `ABSORPTION_PLATE_THICKNESS` moved to kind 1 beside
  `ABSORPTION_THICKNESS_MATTERS`. Of its nits, five condition texts were corrected and the
  README's limits gained three; none was declined.
  *Not done, on purpose*: the WP's `### Inherited` was not pruned (wp-start step 5), because
  PR #1480 (WP-2075) adds an entry there and a prune would conflict with it. No tier, no
  `_audit` row, no `src/` change. No generality judge: the branch adds no row and no heuristic.
  *Gotchas*: guard codes take their thresholds from `strategy/staged.py` and `schemas/plan.py`,
  and `PATTERN_DEAD_CHANNELS` from `background/diagnostics.py`. The inventory's `note` names
  them, but `constants_read` sees only names read in the raising function's own file, one call
  deep. The kinds
  are this session's reading for part 2 to check, not rulings. Ten, every code already tiered, copy
  the ambiguity their audit row carries.
  Next: the maintainer's answer to the gate question. If part 2 goes ahead: tier each code per
  part (statistic, threshold, action) with families, starting with the 15 kind-2 and kind-3
  codes and the B13 constants they read. Then lift the four thresholds with their rows, pinned
  bit-identical before and after, and send the batch.

- **2026-10-18** — created, from the milestone's opening session, split out of 2002 on the
  second review's finding that one WP over 9 587 lines of actions *and* codes is too big
  for one session.
