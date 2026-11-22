# WP-2237 — The decision machinery: fewer calls reach the maintainer, and each ruling is reused

Milestone: unscheduled · Status: 🔄 2026-11-22 — new routing rules approved and applied to the 47 pending lines; the register, the queue token, Rule 1's word and the printout cap are not built
Track: The repo's own process
Depends on: 2009 soft (owns the rulebook cleanup this plan feeds)
Priority: P2 2026-11-21 — the maintainer's attention is the scarcest resource in the workflow, and 11 settled calls were reversed in three weeks

## Goal

A call reaches the maintainer only when it needs him, and arrives with enough to decide.
A ruling he makes is recorded once, with its scope, where the next session that settles a
call reads it. No always-loaded text grows to get there.

## Context

The maintainer's framing, 2026-11-21: "human attention is the most expensive resource in
our workflow"; "if it's clear that thinking more resolves the issue cleanly, think more and
only bring it to me if it's unresolvable"; "tbh I don't read the consent lines. They don't
have enough information to be useful anyway".

**The eleven reversals, sorted by what was written at the time** (memory
`settled-decision-reversals.md`, plus two from 2026-11-21 not yet logged):

| Cause | n | Cases |
|---|---|---|
| A written rule gave his answer; the session did not apply it | 3 | WP-2003 summary line, WP-1944 extinction warning, WP-2080 1.25 retry |
| The rule was unclear | 2 | origin choice by corpus count (Rule 1's "the data"), the scan ruling stretched from the symbol ruling |
| A direction call settled instead of brought | 2 | WP-1964 scope, TOPAS parity |
| An error of fact | 2 | dark palette pick, WP-2224 warm refit (2.25 esd) |
| A value not yet written | 2 | WP-2231 help box and plot preview |

Six of the eleven add a verdict the reader cannot audit: a warning, a retry, a summary
line or a guessed default on a threshold or a reading rietx chose. `docs/DESIGN.md` § Why
this package exists already states the value they break, and no always-loaded file
carries it. Text rules read sometimes lost three times; checks that refuse held (root
CLAUDE.md +99/−97 lines in a month under its 995 cap).

**Rulings, 2026-11-21.**
- "too much information is as bad as not enough. if everything is highlighted, nothing
  is." So a removed verdict leaves its number in a field, printed nowhere new, and a batch
  summary appears only when it says what no single result can (his 2026-11-03 tally edge).
- "consider when your suggestions include adding more lines to any of our prose, and if
  that's the best way to achieve that aim. A larger context also means less attention to
  any one thing." So every part below prefers a check, a cap or a replacement to a new
  line, and text a step needs lives where only that step reads it (memory
  `prose-additions-cost-attention.md`).
- WP-2009 owns the rulebook cleanup (the maintainer, same day); this WP hands it inputs
  and edits none of the five CLAUDE.md files.

**Ruled 2026-11-22.** Tier 3 eased (option B of the brief): a tier-3 code, action or
default row keeps his dated approval; a tier-3 constant or suggestion row is approved by
the `generality-review` judge's `holds`, recorded `approved_by="checked"`, and any other
verdict goes to him. Grounds: 166 tier-3 rows, 111 of them constants, and none of his
reversals was a constant's value. Built in `generality.md` § The rule and § Acceptance,
`_audit.Row.approved_by` with its test, and the judge's brief.

**Ruled 2026-11-22.** The routing rules: he approved the paste text (the middle set,
generalised for every project, with the user-surface trigger kept). The rietx-only
triggers stay in rietx's records: the reversal log's escalated areas, the tier-3 rule
above, and printed-output changes, now settled per PR with a blind check and read by
him once per release (`docs/RELEASING.md` step 2; `/pr-review` 6c and `/wp-handover`
step 11 changed to match).

## Plan

Each part names its prose cost. "Step-only" means read only by the step that needs it.

1. **Settle and check, instead of consent lines.** Claude settles a clear call a rule sends
   the maintainer; a fresh checker agent (`.claude/agents/decision-check.md`) given the
   evidence and not the conclusion reviews it; agreement is recorded "settled by Claude,
   checked", disagreement goes to him. Exclusions by direction: adding or keeping a
   thresholded warning or action goes to him; demoting one to a field under his 2026-11-03
   and 2026-11-16 rulings does not. Tier-3 keeps (generality § Acceptance, the dated
   approval) still go to him, in a batch, as before-and-after output. One checked call in
   ten goes to him at random, so the reversal log keeps a sample. Deletion stays a
   trigger. *Prose:* the global instructions' consent-line clause is replaced (net
   shrink); the checker's prompt is step-only.
2. **A rulings register.** `docs/rulings.md`, one self-contained line a ruling: date, his
   words, area, scope (which sibling cases it covers), link. Written when he rules,
   backfilled once from the ~270 markers in docs and the memory rulings. A test requires
   each new "Ruled by Yue" marker to have a row. *Prose:* step-only (the checker and a
   session bringing a call read it).
3. **Rulebook cleanup → WP-2009.** No input from here: the hindcast measured no gain from
   DESIGN's purpose paragraph in the always-loaded file, so it stays out. Rule 1's "the
   data" becomes "this pattern's data" (a replacement, untested: its case had leaked).
4. **One queue.** A structured `waits on Yue:` token in the existing Status line, read by
   `wp_index.py`, flagged when the file has a later ruling marker or its PR merged. First
   find why 5 of 12 such lines were stale on 2026-11-21. *Prose:* none.
5. **Think more before bringing.** A settled call records the options it weighed, and one
   of them is always the version that removes, demotes to a field or does nothing; the
   checker picks between them blind. The pre-bring questions (is the premise stale; does a
   later ruling cover it; across which fits and users does it act, and what does it do on
   clean ones; his question sequence; does a measurement's value change the pick) live in
   the checker's prompt, never in the doer's context, and route only by the written
   triggers. *Prose:* step-only. The global instructions' measurement sentence gains one
   clause, as a replacement.
6. **A cap on the printout.** A test caps the lines and diagnostics the standard fits
   print, as `tests/skill_caps.py` caps the skill; growth is paid by a cut or brought.

## The hindcast (2026-11-22)

Fourteen past calls (the eleven reversals' cases plus three where he chose the action or
the addition), his answers hidden, options shuffled. One Opus agent an arm predicted a
probability per option and a route (settle or bring). Arms: A, today's auto-loaded
context; P, A plus DESIGN's purpose paragraph; R, A plus DESIGN § Why and § Rules as they
stand; F, R with the Rule 1 edits and the pre-bring questions. Eight cases leaked: their
ruling was already in the auto-loaded context (root CLAUDE.md, the memory index, which
subagents received, or the recent-commit list). Six were clean: 1, 3, 7, 8, 9, 12.

| Arm | Top pick right, all 14 | Clean 6 | Mean p(his pick), clean | Brought to him |
|---|---|---|---|---|
| A | 13 | 5 | 0.59 | 11 |
| P | 12 | 4 | 0.58 | 9 |
| R | 13 | 5 | 0.62 | 8 |
| F | 14 | 6 (case 12 at 0.5) | 0.66 | 13 |

Read with care: one run an arm, six clean cases, and the cases were written by a session
that knew the answers. Three findings survive that.
1. **The arms differ by about one case, which is noise.** Rewording the rules buys nothing
   measurable, so the purpose paragraph and the DESIGN edits beyond Rule 1's word stay out.
2. **Shown both options side by side, today's context picks his answer** in 5 of the 6
   clean cases, though the sessions that made those calls did not. The failure was
   generating the options: the subtractive one was never written down. Hence part 5's
   rule that a settled call records it and a blind checker picks.
3. **The checklist in the doer's context made it bring 13 of 14**, including two calls a
   written ruling already settles. So the questions go in the checker's prompt, and
   routing follows the triggers alone.

Cost: four agents at about 105k tokens each, 425k in all against a 150k estimate; each
subagent starts at about 100k of auto-loaded context.

The hindcast cannot answer the plan's main question, whether fewer calls reach him: every
case was one he had ruled, so bringing it was correct, and no arm changed the routing rules.

## The routing test (2026-11-22)

Twenty-four real items brought to him between 2026-10-19 and 2026-11-17, gathered from the
WP rulings files, the shift logs and the shift decision files. Twelve he delegated or
approved as recommended (S); twelve he answered with a different pick or a new principle
(B). Each Opus agent saw the item as brought, with its recommendation, and chose settle
(with a pick) or bring. Two runs an arm, items in two orders. Arms: **T**, today's
instructions; **N**, the consent-line and approval-field triggers removed, the threshold
exclusion by direction, a pre-bring pass; **M**, N plus two triggers restored in plainer
words (a change to what a default does on every fit; reading a meaning into one of his
rules or amending one). The items quote private logs, so they live outside the repo.

| Arm | Brought (of 24) | Needless brings (S items) | Wrong settlements (B items) |
|---|---|---|---|
| T | 17-18 | 9 | 2 |
| N | 8-10 | 3 | 4 |
| M | 14-16 | 5-7 | 1-2 |

- The approval-field and printed-output triggers send most of the needless items: I5, I6,
  I9 and I11 leave under N and M.
- N's extra wrong settlements are all calls about a default plan or what one of his
  rules means (I13, I17, I19), where he answered with a new principle.
- M's remaining needless items share a trigger with real ones: what his rule means (I1,
  I2), a threshold-fired action (I4, I10), a stored format (I7, a hard trigger).
- Every arm settles I21 wrong: six of six agents read root CLAUDE.md's "a row the format
  states two ways is refused rather than chosen" as covering a `.pcr` bare R symbol, which
  he ruled read-and-notify on 2026-11-03 (WP-1911). An input for WP-2009.

Cost: the gathering agent 311k tokens, six routing agents about 112k each; about 1.0M in
all against a 0.5M estimate.

**His batch sentence, added (2026-11-22).** In the parent session he asked to "rule on any
clear-cut ones, think about any hard ones and only bring me the ones that really need my
attention", and far fewer items reached him. Arms NY and MY open N and M with that request
as a standing rule (check each call against the design rules, ethos and intended users;
rule on the clear-cut ones; think a hard one through; bring only what really needs his
attention), in place of "Settle every call you can". Two runs an arm, same items.

| Arm | Brought (of 24) | Needless brings | Wrong settlements |
|---|---|---|---|
| NY | 9-10 | 3-4 | 2-4 (I17, I21; I13, I18 in one run) |
| MY | 13-14 | 5-6 | 2-3 (I18, I21; I13 in one run) |

- The sentence moves nothing beyond run-to-run noise. The drop in brings comes from
  removing the approval-field trigger, which N and M already do; his batch request worked
  the same way, by waiving that trigger for the batch.
- Two wrong settlements are not routing errors: I21 is the rulebook misread every arm
  makes, and I18 is a pick error between two settle options in every arm with a settle.
  Without them, wrong settlements by routing are T 1, N 2-3, NY 1-2, M 0, MY 0-1.
- I13 was scored right where the pick named the Geometry.kind preset, which his answer
  built, and wrong where it kept tier 3 pending a comparison.

Cost: four agents at about 114k tokens each, 457k against a 450k estimate.

## The first blind check (2026-11-22)

Applied to PR #1768 (WP-2009), whose last step was the maintainer's read of every
reworded rule. The author's reading and this session's both found no change of meaning.
A fresh Opus agent given the diff without either reading found one rule deleted outright
and six changed instructions, plus a wrong fact and a dropped pointer; all were real and
are fixed on that branch (96120fa8d). It cost 239k tokens. The check caught what a read by
the doer did not, which is the case for part 1's checker; it did not need to be a saved
agent definition, since the dispatch prompt carried the question.

## The 47 consent lines under the new rules (2026-11-22)

The 47 lines pending on 2026-11-21 were triaged under the rules ruled above. Claude settled
33 outright and 3 in part, and a fresh agent checked them blind. Eleven went to the
maintainer: six tier-3 approvals, two public posts and three rulings. He answered "All as
recommended". The blind check changed two outcomes. On the CIF angle within 1e-3° of its
symmetry value, it chose to leave the angle as stored over the proposed snap. On
`PHASE_UNCONSTRAINED`, it found the cited precedent wrong. Each outcome is written in its
own record: `docs/wp/2005-batch/rulings.md`, WP-2006 and WP-2020 § Rulings, and
`docs/milestones/generality.md` and `series.md`. The collation cost 195k tokens, the check
141k and the recording 156k.

## Tasks

- [x] Hindcast test (above).
- [x] Routing test (above).
- [x] Global-instructions paste text to the maintainer (another repo); approved 2026-11-22.
- [x] Printed-output review moved to once per release.
- [x] The consent-line replacement (part 1): the paste text. The checker is a dispatch prompt, not a saved agent (§ The first blind check).
- [ ] Settled calls record the options weighed (part 5).
- [ ] The register, its backfill and its marker test (part 2).
- [ ] Rule 1's one-word replacement (part 3).
- [ ] The queue token (part 4), after measuring why the five went stale.
- [ ] The printout cap (part 6).
- [x] Log the two 2026-11-21 reversals in memory.
- [x] Tier-3 approval eased for constants and suggestions (ruled 2026-11-22).

## Acceptance

Measured a month after landing, against the baselines here: 47 consent lines pending,
5 of 12 waits stale, 11 reversals in three weeks, root CLAUDE.md 995 lines. Items brought a
week fall; the share answered without a request for background rises; the reversal rate on
the audit sample stays under the pre-change rate; no wait is stale (a test).

## Handover log

- **2026-11-22** — The maintainer's attention now goes only to calls that need it. His new
  standing rule, given as paste text for his own instructions file, has Claude settle every
  clear call a project rule sends him, with a fresh agent checking the batch blind and one
  in ten shown to him. Applied to the 47 lines that waited on him, it brought him 11, and he
  accepted all 11 as recommended. The first blind check, on WP-2009's rulebook rewrite, found
  seven meaning changes that two careful reads had missed, which is the evidence the checker
  earns its cost (about 240k tokens a check). Tier-3 approval is eased for constants and
  suggestions only, since none of his reversals concerned a constant's value.

  *Done.* Hindcast and routing tests recorded (§ The hindcast, § The routing test). The
  batch sentence he asked about adds nothing measurable; the drop in calls comes from the
  approval-field waiver. Ruling B: `_audit.Row.approved_by` (`"maintainer"` by default,
  `"checked"` only on a tier-3 constant or suggestion), held by `test_audit_table.py`, mirrored
  in `audit_delta.py`, and followed by the generality judge's agent file, CONTRIBUTING,
  `generality.md` and `/pr-review` 6b. Printed-output changes are settled per PR with a blind
  check and read once per release (`/pr-review` 6c, `/wp-handover` step 11,
  `docs/RELEASING.md` step 2). WP-2009's PR #1768 was fixed under the new check and merged.
  The 47 outcomes are written in the 2005 batch rulings, WP-2006, WP-2020 (parked),
  `generality.md` and `series.md`; the two public posts are on #1075 and #1214.

  *Measured.* No test was added (the new assertions sit in an existing test), so passed+skipped
  should not move. The fast selection did not run locally: another session's suite was
  running (17 pytest processes), so CI's run is the count. `test_docs_consistency.py` and
  `test_audit_table.py`: 80 passed (.venv, macOS arm64). `tests.audit_delta`: no row or
  declaration changed. Costs of the consent triage: 195k
  tokens collation, 141k check, 156k recording.

  *Review.* `/code-review high --fix` found two nits, both fixed (5b88870e3): the
  `approved_by` check now also covers unaudited rows, and the hindcast scorer reads UTF-8.

  *Gotchas.* `wp_index.py` rejects ⏸, so a parked WP stays 🔄 with "parked" in its Status
  text (WP-2020). The rietx-only triggers live in project records, never in the paste text,
  so other projects inherit only the generic rule.

  *Not done.* The register (part 2), the queue token (part 4), Rule 1's word (part 3), the
  printout cap (part 6) and the options record (part 5). The maintainer pastes the new section
  into his instructions file himself, and deletes the consent-list sentence there.

  Next: build the settled items in their own WPs' sessions (WP-2006's rows go with PR #1636's
  successor; the WP-1420 and WP-1453 Milestone headers move with PRs #1401 and #1594). Then
  decide whether part 2's register still pays now that rulings land in their own records: the
  month-on acceptance figures above decide it.

- **2026-11-21** — filed from the reappraisal session. No open WP owns the decision
  workflow; WP-2009 owns the rulebook half and is in flight elsewhere.
