# WP-2237 — The decision machinery: fewer calls reach the maintainer, and each ruling is reused

Milestone: unscheduled · Status: 🔄 2026-11-21 — plan consolidated with the maintainer; hindcast test run before any build
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

## Tasks

- [x] Hindcast test (above).
- [x] Routing test (above).
- [ ] Global-instructions paste text to the maintainer (another repo).
- [ ] The checker agent and the consent-line replacement (part 1, 5).
- [ ] The register, its backfill and its marker test (part 2).
- [ ] Rule 1's one-word replacement (part 3).
- [ ] The queue token (part 4), after measuring why the five went stale.
- [ ] The printout cap (part 6).
- [x] Log the two 2026-11-21 reversals in memory.

## Acceptance

Measured a month after landing, against the baselines here: 47 consent lines pending,
5 of 12 waits stale, 11 reversals in three weeks, root CLAUDE.md 995 lines. Items brought a
week fall; the share answered without a request for background rises; the reversal rate on
the audit sample stays under the pre-change rate; no wait is stale (a test).

## Handover log

- **2026-11-21** — filed from the reappraisal session. No open WP owns the decision
  workflow; WP-2009 owns the rulebook half and is in flight elsewhere.
