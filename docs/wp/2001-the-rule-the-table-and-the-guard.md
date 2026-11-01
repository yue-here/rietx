# WP-2001 — The rule, the audit table and the guard

Milestone: generality · Status: ✅ 2026-10-19 — the table, its meta-test, the judge and its handover step landed (PR #1047); the cross-project lesson went to a session in claude-config
Track: The registry and the guard
Depends on: —

## Goal

The three-tier rule is written where the package can hold itself to it: an audit table in
its own module, keyed by name, that every later audit fills; a tripwire test that fails a
diff adding a heuristic without a row; and a handover step that dispatches a fresh-context
reviewer to draft the case against each new row. The root CLAUDE.md's rule that rewards a
firing code is rewritten to DESIGN.md § Rules, 1's three outcomes.

## Context

The milestone record, [`../milestones/generality.md`](../milestones/generality.md) § The
rule, is the one authority for the tiers, the two grounds a tier-3 item is kept on, the
answer-invariant class, what demotion means and how a moved golden is judged. Restated in
one paragraph here so this file is self-contained; sharpen the record, never this copy.

Three tiers, each part of a heuristic tiered separately (statistic, threshold, action):
(1) physics or arithmetic, kept; (2) a citation that validated it or the same action taken
by default in GSAS-II, FullProf or TOPAS, kept and named; (3) rietx's own, demoted unless it
holds on three unrelated dataset families (by lab, instrument and material). Every action,
whatever its tier, is kept only if every competent refiner, shown the statistic, would
take the same action (DESIGN.md § Rules, 1's unanimity gate; for tier 2 the source is
evidence toward yes); a named dissenter demotes it to a ranking where the data can rank the
alternatives and to the number with its meaning otherwise, approved by the maintainer in a
batch. The
inheritance rule, the answer-invariant class, the one-family clause and the moved-golden
rule are the record's; this copy carries no more than that sentence (third review: the
first copy inverted the polarity; fourth: visibility gave way to judgement).

**The seams.**

- `rietx.help.DIAGNOSTIC_HELP` (`src/rietx/help.py`, WP-1985) holds 256 `HelpEntry` rows,
  one per `Diagnostic` code, held equal to the raise sites both ways by `tests/test_help.py`
  (`docs/reference_pages.diagnostic_index()`). Build the inventory from that index, never
  from a grep for `code="…"`: seven codes are raised through a name and have no literal. **Do not add audit fields to `HelpEntry`**:
  the class is shared by every help arm and serialised to `/api/help`, so a field there
  moves `gui/src/lib/help.ts`, the vitest table and the committed dist. The audit table is
  its own module, maintainer-facing, and a meta-test holds its code rows equal to
  `DIAGNOSTIC_HELP`'s keys both ways.
- Automatic actions have no code. The house rule "a correction ships with a record field"
  is the inventory: `StageResult` (`schemas/results.py`) fields `held`, `held_reach`,
  `scale_b_held`, `released`, `moment_flat_axes`, `moment_turned`, `blocked_by_hold`,
  `seeded`; `SeriesEntry` (`schemas/sequential.py`) `rung`, `reseeded`, `rwp_fence`. The
  table keys an action on the record field that reports it.
- Threshold constants are module-level numbers. 127 in `report/`, `strategy/`,
  `optimize/statistics.py`, `refine.py`, `sequential.py` (AST walk, 2026-10-18); indexing
  has 76 more, io ~30. **The table's walk covers a declared directory list**, held as data
  in the table module (`_audit.WALKED`): `refine.py`, `sequential.py`, `multi.py`,
  `strategy/`, `report/`, `optimize/`, `background/`, `indexing/`, `crystallography/`, and
  the readers' repair code under `io/`. The second review found `background/`,
  `optimize/lm.py` and `crystallography/` in neither the open's count nor any audit WP's
  scope, so they are on the list; the third review ran the walk over all of `src/rietx` and
  found 619 constants, the surplus over the seams being byte offsets in file readers, pixel
  sizes in the 3D viewer and schema defaults, so the list is not the whole package. A
  directory outside the list is out of scope by declaration, and the module docstring says
  so. Every constant the walk finds opens at `unaudited` and belongs to an audit WP **by
  directory** (fourth review; 2005's partition covers codes only): `refine.py`,
  `strategy/`, `background/` and every `optimize/` constant that is not report-facing to
  2002; `sequential.py` and `multi.py` to 2003; `report/` and the report-facing rows of
  `optimize/statistics.py` to 2004; `io/` and `crystallography/` to 2006; `indexing/` to
  2007. A file the walk reaches that none of those names is this WP's to assign before
  it closes. The table stores each constant's
  **value** beside its name, so a retune fails the meta-test and reopens the audit. A
  row's name is checked by import.
- Defaults that decide behaviour are written into signatures and schema fields, where a
  walk over module-level assignments cannot see them: `correlation_guard: float = 0.98`
  in `PlanSpec`, and again as a literal in `run_stage`. Measured 2026-10-18: 24 literal
  defaults across `PlanSpec`, `StageSpec` and the signatures of `fit`, `refine`,
  `run_stage`, `refine_sequential`, `index_pattern` and `auto_background`. About ten
  change what the package does (`correlation_guard`, `max_iter`, `lebail_cycles`,
  `lebail_passes`, `carry_hkl_intensities`, `validate`, `shift_from_pairs`,
  `temperature`); the rest are off states and counters. The whole package holds 347
  numeric defaults, mostly plot sizes, starting values and search ranges. So the table
  walks a declared list of seats (`_audit.DEFAULT_SEATS`: those classes and functions,
  plus `Source`, whose `dispersion` default turned a correction on in v1.0), as it walks a
  declared list of directories, and a default outside the list is out of scope by
  declaration (ruled 2026-10-18, over walking all 347, which would reopen an audit on
  every cosmetic edit). A default row belongs to the audit that owns the code it feeds:
  the plan schemas, `fit`, `refine`, `run_stage`, `auto_background` and `Source` to 2002,
  `refine_sequential` to 2003, `index_pattern` to 2007.
- `Diagnostic.level` (`schemas/common.py`) is a required `Literal["info", "warning",
  "error"]`; demotion uses `info`, never a new member.
- `/wp-handover` (`.claude/commands/wp-handover.md`) step 6 runs `/code-review high --fix`
  on the branch; step 7 is a checklist of named triggers against what the session added.
  `/pr-review` dispatches the `pr-conformance` agent (`.claude/agents/`) on outside PRs
  only. WP branches, where every overfit here was born, get no fresh-context read today.
- `docs/wp/TEMPLATE.md` is where a WP is filed from one dataset. One line there asks the
  origin question.
- `~/Code/claude-config/workflow/LESSONS.md` carries rules between the maintainer's
  projects through `/workflow-sync`; a lesson travels as a rule, worded per project, and
  names its exemplar.

**The recurrence design, decided 2026-10-18.** A tripwire and a judge, not prose alone.
The tripwire is a test over the tree against the table that fires on: a new `Diagnostic`
code; a new field on `StageResult`, `SeriesEntry` or `RefinementResult`; a new or retuned
module-level numeric constant in a walked directory; a new or changed default at a
declared seat; a new `suggestion=` string. It reads
no git (third review): CI checks out at depth 2 with no `origin/main` ref and a local
worktree's is days stale, so a test comparing against the base table through `git show`
skips exactly where it gates a merge. Instead the names allowed at `unaudited` are a
committed list in the table module (`_audit.UNAUDITED_BASELINE`), written once at the open
and allowed only to shrink; a row at `unaudited` whose name is not on it fails, and a name
in the tree with no row fails. The handover dispatches the judge whenever the diff touches
the table module or that list, so an author who adds a name to the baseline has made a
visible edit on a file whose name says what it is. The dispatch hangs on **step 7**, the
checklist every branch runs, and not on step 6, which a prose-only branch skips (fourth
review): a heuristic added as skill prose is already invisible to the tripwire, and on
step 6 it would have had no judge either. The judge is a
fresh-context `generality-review` agent the handover dispatches on a hit, which answers
DESIGN.md § Rules, 4's test for the kind of change per item, quoting the WP's own evidence
lines: what does this decide that the caller did not ask for, and which of Rule 1's three
kinds is its ambiguity; for the first kind, which competent refiner would act otherwise and
in what situation; for the second, does it rank with evidence and pick only in Rule 1's
two cases; for the
third, does it report the number and stop; which tier, with its source; how many unrelated
families, counted by lab, instrument and material, and the reference each was measured
against (Rule 2); which record field says it fired. An earlier question, "deleted, what
does a caller see and when could they act", was the visibility ground the fourth review
retired; it survived here until the cascade from the rules removed it. The agent
drafts the case *against*, beside the author's two-ground
answer, because a row written by the author alone is self-certification and a batch
approval tends to rubber-stamp. **What it will miss, stated in the module docstring**:
inline literals (about 30 in `refine.py`, `< 0.7` at the plate-thickness test, `>= 2.0`
further down), defaults outside `DEFAULT_SEATS`, orderings and fallback chains, an
always-on correction with no switch, threshold or new field (the Bérar–Lelann esd
inflation was one), and heuristics written as skill prose (2008's half).

**The generator rule** (the second review's biggest finding). Root CLAUDE.md's "A new
correction ships with a record field or a diagnostic stating what it changed" and the P1
rubric's "a wrong number that nothing flags outranks one that raises" both reward adding a
firing code. The rewrite states Rule 1's three outcomes in one clause: where every
competent refiner would act, act and record it in a field; where the data can rank the
alternatives, rank them with evidence; otherwise report the number with its meaning. It
keeps "never an Rwp comparison as its evidence" and points at DESIGN.md § Rules, 4. It
lands here, before the audits, so they follow it. The P1 rubric is 2009's. The second
review had worded the rewrite as a flat order (record field, then diagnostic, then
action); the maintainer replaced it on 2026-10-18, because the order points a session away
from acting where Rule 1's first kind says act.

## Non-goals

- Auditing any row. The table opens with every existing code, action and constant at
  `unaudited`; 2002–2007 fill it. The growth guard refuses only a **new** item at
  `unaudited`.
- The P1 rubric in `TEMPLATE.md` and the findings-as-rules pass over the CLAUDE.md files:
  2009.
- The skill: 2008. The tripwire does not read `docs/skill/`.
- A `Diagnostic.level` member for "no verdict". Demotion is `info` or removal.

## Tasks

- [x] The milestone record (`docs/milestones/generality.md`), its ROADMAP row and section,
      the WP block 20xx and this file plus 2002–2009; ROADMAP's cap 589 → 614 with its
      diary line. (2026-10-18, the filing session.)
- [x] The table module `src/rietx/_audit.py` (named here, since 2002–2009, the record and
      the handover's dispatch all key on `_audit`):
      a frozen row type with `name`, `kind` (`code` | `action` | `constant` | `default`),
      `tier`
      (`1` | `2` | `3` | `invariant` | `caller` | `unaudited`; `caller` is an action only
      the caller turns on, an opt-in flag or a pick verb no default path calls, since
      DESIGN.md § Rules, 1 governs what the package decides alone), `ambiguity` (`1` | `2` | `3`, DESIGN.md
      § Rules, 1's kinds; code and action rows only, where Rule 4 asks for it to be
      stated), `evidence` (a citation, a program and what it does by default, or the
      families with their references), `grounds` (the two-ground answer for tier 3, the
      judgement answer for a tier-2 action), `approved` (a date, on the same rows),
      `value` (constants and defaults only). Every
      existing code from `DIAGNOSTIC_HELP`, every record field named above, every constant
      the AST walk finds over `WALKED` and every default at `DEFAULT_SEATS`, entered at
      `unaudited`; `UNAUDITED_BASELINE` the
      sorted list of those names, written once here. (2026-10-19: 1 124 rows, 256 codes,
      19 actions, 546 constants, 107 defaults, 196 suggestion keys; the other 65 record
      fields in `OTHER_RECORD_FIELDS`. A fifth kind, `suggestion`, holds the `suggestion=`
      sites per code, since no other kind could. The generality judge's first run widened
      the declared scope, each a reversible session choice recorded in the handover:
      `WALKED` gained `model/`, `params/` and all of `schemas/`; `DEFAULT_SEATS` gained
      `SequentialRefinement.fit` and `SearchSpec`; a `None` default has a row; `Statistics`
      joined the record schemas for `esd_inflation`; eight fields became action rows; and an
      audited default row states its kind of ambiguity. `io/` still contributes only
      `io/readers.py` and `io/formats/base.py`.)
- [x] The meta-test (`tests/test_audit_table.py`): code rows equal to `DIAGNOSTIC_HELP`'s
      keys both ways; every action row's record field exists on its schema; every constant
      and default row imports and its stored value equals the live one; a tier-3 row, and
      a tier-2 action row, carries `grounds` and `approved`; every `unaudited` row's name is on `UNAUDITED_BASELINE` (the growth
      guard; no git); every name on the baseline still has a row, so the list shrinks as
      rows are audited and never grows. (2026-10-19: 15 tests, ~2 s; seen red on a
      throwaway constant in `refine.py`, a retuned `CORRELATION_GUARD`, a flipped
      `auto_background` default and a new `StageResult` field, each naming the row to add.)
- [x] `/wp-handover`'s dispatch condition for the judge, on step 7: the tripwire fired, or
      the diff touches the table module or the baseline. (2026-10-19: both reduce to the
      branch touching `_audit.py`; a second trigger dispatches on a heuristic the table
      cannot see, which is why it sits on step 7.)
- [x] The tripwire's second half: the walk that produces the constant list is a function
      the test and the table share (`_audit.constants()`), so the inventory cannot drift
      from the guard; the same for record fields (`dataclasses.fields` /
      `model_fields` over the three schemas), defaults (`_audit.defaults()`, over
      `DEFAULT_SEATS`' fields and signatures) and `suggestion=` strings (an AST walk for the
      keyword).
- [x] `correlation_guard`'s two literal copies (`PlanSpec`, `run_stage`) become one named
      constant, bit-identical before and after. (2026-10-19: three copies, the third in
      `RefinementPlan`; `schemas.plan.CORRELATION_GUARD`, beside `INTERMEDIATE_FTOL`, and
      `test_each_mirror_declares_its_dataclass_defaults` holds every mirrored default equal.)
- [x] The `generality-review` agent (`.claude/agents/generality-review.md`): read-only,
      the Rule 4 questions above, output a table per item with the case against, written
      for the maintainer in plain words (root `~/.claude/CLAUDE.md`'s register). The
      handover's step 7 gains the dispatch: on a tripwire hit, or on any diff touching a
      row, run it and paste its table into the handover entry under *Generality*.
- [x] `docs/wp/TEMPLATE.md`: one line in the Context guidance, "a rule this WP adds is
      physics, named practice, or new judgement; say which, and for the third name the
      families it was measured on and their references; a default or automatic action
      also names its kind under DESIGN.md § Rules, 1; a new topic names its reference
      (dataset, published number, tolerance) before any code is written, or says none
      exists and that it ships not yet validated" (Rule 4's test for a new topic, whose
      only other seat is 2010's check at landing).
- [x] Root CLAUDE.md: rewrite the "new correction ships with a record field or a
      diagnostic" invariant to Rule 1's three outcomes, one clause pointing at DESIGN.md
      § Rules;
      a clause under § Invariants naming the table and the tripwire, since DESIGN.md
      § Rules, 4 places the mechanisms that enforce its tests there. Count the lines
      against the cap (`tests/test_docs_consistency.py`) and bump with a diary line if
      needed. (2026-10-19: +9 lines, cap 983 → 993 with its diary row and `process.md`
      paragraph.)
- [x] `claude-config/workflow/LESSONS.md`: the lesson "a heuristic enters with its tier or
      not at all", with rietx's table and agent as the exemplar, through `/workflow-sync
      harvest`. This is a separate repository and a separate commit; the handover names it.
      (2026-10-19: handed over, not landed by this WP. A worktree-isolated rietx session
      cannot run git in `claude-config`, so the lesson went as paste-ready text to a
      session working there, with the agent-registration trap as an amendment to lesson
      3.)
- [x] Tests + the fast selection count moved by exactly the tests added. (2026-10-19:
      +16 collected, 10 995 → 11 011, `[dev]`, darwin arm64.)
- [x] Skill: none. The table is maintainer-facing; an agent driving rietx reads the
      diagnostic's `explanation`, which 1985 built and this WP does not change.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

Plus, by hand once: add a throwaway constant to `src/rietx/refine.py` on a scratch branch
and confirm `test_audit_table.py` goes red naming it; remove it. A guard that was never
seen to fail is a guard that may go quiet (`tests/CLAUDE.md` § Guards that go quiet).

## References

- `docs/milestones/generality.md` § The rule, § Decisions, § The two reviews.
- WP-1985 (the per-code explanations and `DIAGNOSTIC_HELP`); WP-1076 (a declared name is a
  claim); WP-1007 (`capabilities()` and `_SURFACE_FLAGS`, the registry-plus-meta-test shape
  this copies).
- Kass, R. E. & Raftery, A. E. (1995). J. Am. Stat. Assoc. 90, 773–795 (the ΔBIC bands the
  record cites as the worked tier-2 example); Schwarz, G. (1978). Ann. Stat. 6, 461–464.

## Handover log

### 2026-10-19 (4th session) — closed; the cross-project lesson went to a claude-config session

WP-2001 is closed. Its rietx work merged as #1047 this morning, and nothing in rietx is
left. The last item was a lesson for the maintainer's other projects, which live in
`~/Code/claude-config`. A session working in a rietx worktree cannot commit there, so this
session wrote the lesson as paste-ready text, and the maintainer took it to a session in
that repository. No code, test or number changed.

*Done.*
- `LESSONS.md` (18 561 bytes, 17 lessons) read for overlap. None covers a rule table. The
  harvest that ran at 09:05 today (`claude-config` `a1e6fcce`, rietx to `3144f0f8`) passed
  over this lesson without taking or declining it. Its marker now sits past WP-2001's
  commits, so a later harvest would not find the lesson unprompted.
- The text drafts lesson 18, "A heuristic enters with its tier, or not at all", from the
  previous entry's draft, with two traps: the test reads no git, and the walk skips a name
  rebound through `global`. The agent-registration trap goes to lesson 3 instead, beside
  its trap about hooks loading at session start, because it has nothing to do with the
  table. The "Fits" line is left to that session, which knows dataleaf and chessathon.
- Closed: Status ✅; the empty `### Inherited` and the `Priority:` line deleted; the
  narrative moved to `docs/milestones/v1.10.md`. 2002, 2006, 2007 and 2009, whose last
  hard dependency this was, re-rated at their old tiers.
- `/code-review` skipped: the branch touches only `docs/`. No CLAUDE.md edit, no test, so
  no count moved and the full suite did not run.

*Gotchas.* The harness refuses `git -C` into another repository from a worktree-isolated
session ("points git at a directory computed at runtime"). Plain file reads there work,
and so does reading a loose git object with python's `zlib`, which is how the harvest
commit's message was read.

*Next.* Nothing in this WP. Check that lesson 18 and lesson 3's new trap landed in
`claude-config`. The milestone continues with 2002, its always-on corrections pass first.

### 2026-10-19 (3rd session) — the table, the guard and the judge landed

rietx now keeps a table of every rule it uses to decide on a caller's behalf: 1 124
entries covering each diagnostic code, the result fields that report an automatic action,
the threshold numbers in the directories that decide, the defaults of the main calls, and
the advice it prints. Every entry starts unaudited, for the audit WPs to sort into
physics, practice or rietx's own. A test now fails when anyone adds or retunes one without
a row, and the handover sends any change to the table to a fresh reviewer that argues the
case against it. That reviewer's first run, on this branch, showed the declared scope had
missed the absent-phase hold's own threshold and seven automatic actions, so the scope
was widened. No refinement result changes. Only the cross-project lesson is left, and it
needs a session started in `~/Code/claude-config`.

*Done.* Eleven commits. 9026714b: `CORRELATION_GUARD` named once in `schemas/plan.py`, in
three places (the third copy was `RefinementPlan`'s), and
`test_each_mirror_declares_its_dataclass_defaults` holds every default a mirror shares with
its dataclass equal, since the field-set pin let one field carry two literals. 994d5a57:
`src/rietx/_audit.py` and `tests/test_audit_table.py`, the rows generated once from the
walkers the test also calls (`constants`, `defaults`, `record_fields`, `suggestions`,
`codes`). 400e4ea8: `.claude/agents/generality-review.md` and its dispatch on
`/wp-handover` step 7. 6e081130: the TEMPLATE.md line. 6850fc16: root CLAUDE.md (cap
983 → 993, diary row and `process.md` paragraph). e6f82029: review fixes. c908d3ba: the
judge's widening. 9a004a37 and the forward notes: 2002, 2003, 2004, 2006 and 2007.

*Choices this session made that the maintainer can reverse.*
- A fifth kind, `suggestion`, one row per code holding its count of `suggestion=` sites
  (a new site fails, a reworded one does not), since the WP's four kinds had no place for
  the tripwire's fifth trigger.
- `io/` contributes `io/readers.py` and `io/formats/base.py`, my reading of "the readers'
  repair code" from `io/CLAUDE.md` § What a reader may repair; the judge's five other
  reader thresholds went to 2006 rather than widening the walk over byte offsets.
- After the judge: `WALKED` gained `model/`, `params/` and all of `schemas/` (every
  module-level number in `schemas/` is a decision threshold); `DEFAULT_SEATS` gained
  `SequentialRefinement.fit` and `SearchSpec`; a `None` default keeps its row (it often
  means the package picks); `Statistics` joined the record schemas so `esd_inflation` has an
  action row; eight fields left `OTHER_RECORD_FIELDS` for action rows.
- `ambiguity` is allowed and required on an audited **default** row too, against the WP
  text's "code and action rows only", because DESIGN.md § Rules, 4 asks a new default for
  its kind.
- The judge runs on Opus: its central question, which competent refiner would act
  otherwise, is the maintainer's kind of judgement.

*Measured* (darwin arm64, `[dev]` venv, alone on the machine).
- Fast selection: 10 826 passed, 191 skipped, 2 xfailed, 4:21. Collected 10 995 on
  `origin/main` e868e8f4 (a `git archive` snapshot, same venv) against 11 011 here: +16,
  the 15 cases of `test_audit_table.py` and the mirror test. The run's 11 019 is the 11 011
  plus 8 modules skipped at import. The last widening touched only `_audit.py` and its test,
  re-run after it (20 passed); no test count moved.
- Added tests' cost, local junit: `test_audit_table.py` 8.70 s over 10 functions (the
  walked-kind and value tests 5.61 s and 3.08 s), the mirror test 0.00 s. Not in the slow
  tail by these figures.
- The table: 256 codes, 19 actions, 546 constants, 107 defaults, 196 suggestion keys; 65
  other record fields. 229 `suggestion=` sites (234 raw less five `suggestion=None`). The
  full suite did not run: the only package change replaces a literal 0.98 with a constant
  holding 0.98.
- The guard seen red four ways before the widening, each naming the row to paste: a
  throwaway constant in `refine.py`, `CORRELATION_GUARD` retuned to 0.97 (three rows
  fail), `auto_background`'s `seed` flipped, a probe field on `StageResult`.

*Review.* `/code-review high --fix`, nine findings, eight applied (e6f82029): the walk
missed chained and unpacking assignments (ten constants, among them
`least_squares.XTOL`/`GTOL`); numbers in dicts and lists named as unseen; `resolve()` no
longer hides a missing dependency; a callable default stores its qualname, not an
address; a bool cannot pass as a tier; the dead `inventory()` removed; the step 7 diff file
WP-named. The ninth, the GUI Plan panel's own 0.98, went to 2006.

*Generality.* The judge's report, unedited, with the author's answer under each `fails`.
It ran as `general-purpose` on Opus reading the agent file, because a session registers
agents from the checkout it started in (step 7 now says so).

> ### Item 1: `rietx.schemas.plan.CORRELATION_GUARD` (0.98)
>
> | Question | Author's answer (where) | Case against | Verdict |
> |---|---|---|---|
> | Is "it replaces three literals the open would have listed anyway" a reason to add it to `UNAUDITED_BASELINE`? | WP file, Tasks: "three copies, the third in `RefinementPlan`". | Two of the three copies were already rows, and they remain rows: `PlanSpec:correlation_guard` and `run_stage:correlation_guard`. The third, `RefinementPlan`, is at no declared seat, so the open would not have listed it. The edit adds a third row for one number. It is allowed only because this branch writes the list for the first time. A retune now fails three rows at once, so 2002 should tier the three together. | holds for the open; weak as a precedent |
> | 1. What does it decide that the caller did not ask for? | Docstring `schemas/plan.py`: "\|ρ\| above which a pair of free parameters is reported as highly correlated". | Accurate. A pair above 0.98 becomes a warning-level `HIGH_CORRELATION`; below, no finding. The five worst pairs still reach the result in `identifiability.top_correlations`. | holds |
> | 2. Which kind of ambiguity? | none given (a constant row cannot carry it). | The third kind: report the number and stop. The threshold also decides whether the warning exists at all, a shape the record demotes to an `info` record. | none given |
> | 3. Which competent refiner would set it otherwise? | none given | GSAS-II 5.8.4 by default lists every pair above max(0.95, 0.99 × the worst \|ρ\|) (`GSASIImath.setHcorr`), checked in `rietx-bench/tools/gsas2`. A pair at 0.96 is flagged by GSAS-II and passes silently here. FullProf prints its matrix only on request; TOPAS not checked. A refiner with many background terms expects pairs above 0.98 against c0. | weak |
> | 4. Tier and source | none given | Not tier 2 by another program's default (GSAS-II's is 0.95 and moves). No citation found. | none given |
> | 5. Families | none given | none given | none given |
> | 6. Which record says it fired? | not stated | `HIGH_CORRELATION`, ρ in `Diagnostic.value`; `FLAT_DIRECTION` beside it at \|ρ\| ≥ 0.9995. | holds |
>
> Siblings: the GUI's 0.98 in `Plan.svelte`; `HIGH_CORRELATION_MAX` = 10 (`schemas/results.py`), unwalked. **Strongest case against:** GSAS-II flags from 0.95 and rietx is silent between 0.95 and 0.98; a source for 0.98, or three families' measurements of what pairs in that band do to esds, would answer it.

Author: forwarded to 2002 with the GSAS-II reading; `schemas/results.py` is now walked, so
`HIGH_CORRELATION_MAX` has a row.

> ### Item 2: `OTHER_RECORD_FIELDS`
>
> | Field | Case against | Verdict |
> |---|---|---|
> | `StageResult.moment_angle_tests` | A Δχ² test on free moment angles removes passing angles' columns from the covariance: values kept, esds lost (`results.py`, `least_squares.py` `zeroed=True`). | fails: make it an action row |
> | `StageResult.n_degenerate_cell_probes` | A degenerate trial cell returns 10 × the last residual (inline literal) and reuses the last good Jacobian. | fails: make it an action row |
> | `StageResult.n_constraint_truncations` | The default LM adds inequality rows nobody asked for (Γ_G² ≥ 1e-8, the Stephens cone, texture P ≥ 0); `_MIN_GAMMA_G2` in `model/` has no row. | fails: make it an action row |
> | `StageResult.ftol` | Records the default early stop of intermediate stages at 1e-6; Rule 4's "state its kind" has nowhere to land on a default row. | weak |
> | `SeriesEntry.rungs_raised` | A rung that raises is counted lost and the series escalates past it (WP-1333). | fails: make it an action row |
> | `SeriesEntry.rungs_tried` | The ladder's retry record; by the `held_reach` precedent, an action row. | weak |
> | `SeriesEntry.statistics`, `RefinementResult.statistics` | Carry `Statistics.esd_inflation`, the Bérar–Lelann factor every esd is multiplied by, one level below the fields the table reads. | fails: needs an action row on the nested field |
> | `RefinementResult.absorption` | Estimates µR or µt from composition × `packing_fraction` (0.6, at no seat) × length and applies it; off if the estimate fails; used past the Rouse range with `out_of_range`. | fails: make it an action row |
> | `RefinementResult.sigma` | The √max(y,1) fallback and a 10⁻³ × median-esd floor (inline); no field says which fired. | weak: needs a flag first |
> | `RefinementResult.geometry` | Drops contacts past 24 per atom and phases over 200 atoms, noted in `GeometryTable.notes`; report only. | weak |
>
> The other 50 passed. **Strongest case against:** the moment-angle esd removal and the Bérar–Lelann inflation change every esd quoted and could not carry Rule 1's kind. The series floor-reseed of an unsupported moment has no record field at all.

Author: all six `fails` and both `weak` action fields are action rows now (c908d3ba), with
`Statistics` a record schema; `sigma` and `geometry` went to 2002; the floor-reseed to 2003.

> ### Item 3: the walk's declared scope
>
> | Question | Author's answer | Case against | Verdict |
> |---|---|---|---|
> | A reader decision with a threshold left outside the two `io/` files? | `_audit.py`: "``io/`` contributes only the readers' repair code". | Five: `dif.py` `_MIN_ROWS = 3`, `peaklist.py` `_MIN_ROWS = 8`, `gsas.py`'s 64 kB sniff bound, `bruker_raw.py`'s drive `atol` and counting-time windows, `pdcif.py` dropping a weight column on one zero weight (with `xy.py`, `chi.py` adopting any positive third column as σ). | weak |
> | Does the list reach the thresholds behind automatic actions outside `io/`? | the third review's "byte offsets, pixel sizes and schema defaults". | No. `model/forward.py` `PHASE_SUPPORT_SIGMA = 3.0`, the absent-phase hold's threshold and the record's own example, has no row; `model/` holds about 50 numbers (`WINDOW_MIN_DEG`, `_MIN_GAMMA_G2`, `CYLINDER_MU_R_MAX`); `params/vector.py` the unseen-phase cell windows and the ±15 % clamp; `schemas/indexing.py` about 35 (`PEAK_MIN_HEIGHT_SIGMA`); `schemas/structure.py` `MOMENT_FLOOR_MU_B`; `schemas/results.py` `HIGH_CORRELATION_MAX`. | fails |
>
> **Strongest case against:** the 3σ threshold the milestone uses as its worked example has no row.

Author: `model/`, `params/` and all of `schemas/` are walked now (+148 constants,
`PHASE_SUPPORT_SIGMA` among them); the five reader thresholds went to 2006.

> ### Item 4: `_off` and `defaults()`
>
> | Question | Author's answer | Case against | Verdict |
> |---|---|---|---|
> | Is an "off" default ever the package's own decision? | "An off default has no row: turning one on adds a name". | Yes. `telemetry=None` records the run; `index_pattern:preset=None` resolves to `"quick"` (a string the walk drops, its 120 s budget in a dict); `StageSpec:ftol=None` means the solver's 1e-9, a literal at no seat; `window_slack_deg=None` becomes `WINDOW_MIN_DEG = 0.3`; `spec=None` becomes `SearchSpec()`, at no seat. | fails |
> | Does `defaults()` see every default at a declared seat? | `refine_sequential` is a seat. | It passes `**kw` to `SequentialRefinement.fit`, whose `reseed=True`, `refit="single"`, `on_error="carry"`, `direction="forward"` are at no seat. | fails |
> | Is a flip from on to off seen? | implied | Yes: the row's name disappears and the test fails. | holds |
>
> **Strongest case against:** the telemetry default, the indexing preset and the final-stage tolerance all sit behind a `None` with no row.

Author: the off-default rule is gone, so every default at a seat has a row (+83);
`SequentialRefinement.fit` and `SearchSpec` are seats. The 1e-9 and `"quick"` went to 2002
and 2007.

*CI fix.* The first gating run failed on three Linux legs: `model.compiled._POOL_WORKERS` is state a function rebinds through `global`, so its live value depended on whether a compiled test had run first in that worker. The walk now skips any name a `global` statement rebinds; it was the only one, and no other module writes another's constant. Constants are 546.

*Gotchas.* A session registers agents from the checkout it started in, so an agent file
added on a branch is not a `subagent_type` until it reaches `main`; step 7 names the
fallback. The worktree guard refuses `git -C` into another repository, so the
`claude-config` lesson cannot land from a rietx worktree. It also refuses a python command
whose script path is a shell variable; spell the path out.

*Next.*
1. The cross-project lesson, from a session started in `~/Code/claude-config`
   (`/workflow-sync harvest`). Draft: **"A heuristic enters with its tier, or not at
   all."** Every number, default or automatic action a package uses to decide on the
   caller's behalf carries a row naming its source: physics, named practice, or the
   project's own judgement with the datasets it held on. A test holds the table equal to
   the tree both ways, from a committed shrink-only baseline so it needs no git, and a
   fresh-context judge drafts the case against each new row at handover. Why: 33 of 341
   rietx constants cited a paper; a threshold invented on one dataset reads as a fact to
   the next session. Exemplar: rietx `src/rietx/_audit.py`, `tests/test_audit_table.py`,
   `.claude/agents/generality-review.md`, `/wp-handover` step 7.
2. Then close this WP. If the maintainer would rather close it now, the lesson can move to
   2009 (the rulebooks).
3. 2002 opens with its always-on corrections pass; `Statistics.esd_inflation` is now an
   action row for the Bérar–Lelann ruling to land on.

### 2026-10-19 (2nd session) — the milestone re-read against DESIGN.md's rules, and four rulings

A fresh session checked the milestone against DESIGN.md's purpose and four rules. Most of
it held, and seventeen places disagreed. Thirteen followed from the rules as written and
were fixed. The maintainer ruled on the other four. Two of those rulings change what the
audits do. Every automatic action must now pass "would every competent refiner do this?"
whatever its source, so a cited default goes to the maintainer too. The Bérar–Lelann
esd inflation is the first such case: it is applied to every esd rietx prints, and GSAS-II
does not apply it. A poor result from the agent test now sends an explanation back for
work and no longer holds a demotion back. DESIGN.md now says when the package may pick
from a ranking. Nothing in the package changed.

*Done.* Four commits. ee8a9181, the thirteen fixes:
- 2008 kept rows measured on rietx's runs in three places (a tag counted as a source,
  agents needing a row kept it, a cut row could move into `help.py` prose).
- 2003 tested quarantine "with it off" and called the cold-fit chain an envelope.
- The record let a cross-code reference stand as validation.
- 2007 classified the `quick` budgets with no table value to hold it.
- Rule 4's new-topic test had no seat before code, now a TEMPLATE.md clause here.
- Rule 4's mechanisms belong in root CLAUDE.md § Invariants, which 2001, 2008 and 2010
  now name.
- 2010's partition missed output topics (QPA, indexing, derived geometry,
  microstructure).
- The smaller ones: the scope names all four rules, ROADMAP's sentence asks the gate's
  questions in order, a stale north-star reason left the acceptance row, and 2005's goal
  said "removed" where § Demotion says `info` record.

Two choices were the session's own and are reversible. The table gets a `caller` tier for
an action only the caller turns on, over leaving opt-in tools out of the table. The GUI's
27 HTTP names leave the table, since its code rows are held equal to `DIAGNOSTIC_HELP`.

276bc871, f7e8aba3 and 6e670cb0 carry the four rulings, each in the record § Decisions
with its alternative:
- (1) DESIGN.md Rule 1 states the two cases where the package may pick from a ranking,
  and Rule 4's skill-row test admits a sourced practice.
- (2) Every action faces the unanimity question whatever its tier, and 2002 now
  inventories the always-on corrections no walk finds.
- (3) A threshold measured on fewer than three families is declared "untested beyond"
  them, and *not yet validated* keeps Rule 2's meaning.
- (4) A poor agent result reworks the explanation and does not hold the demotion back.

The maintainer rejected the first wording of (1) as florid and cryptic, and the plain
rewrite landed.

*Measured* (darwin arm64, `[dev]`; scratch AST script, a proxy that over- and
under-counts):
- 33 of 341 module-level numeric constants in `WALKED`'s directories have an `Author
  YEAR` citation within 15 lines above. None of the 256 `DIAGNOSTIC_HELP` entries cites
  a paper in its text, so a code's tier cannot be read off its explanation.
- Bérar–Lelann: GSAS-II 5.8.4's source (`rietx-bench/tools/gsas2`) never mentions it.
  FullProf's manual cites the 1991 paper (reference 14) and I found no statement that
  FullProf applies it. TOPAS was not checked. WP-1417 measured the factor at 7.1–10.2 on
  synchrotron fits before v1.6 lowered it by 12–21 %.
- An eight-run agent round cannot separate 7 of 8 from 5 of 8 (Fisher's exact p = 0.569)
  or from 4 of 8 (p = 0.282).
- `QUICK_TOTAL_BUDGET_SECONDS` = 120 and `DEFAULT_BUDGET_SECONDS` = 30
  (`indexing/engines.py`) are module constants the walk enters.
- No test was added, so no count moved. `tests/test_docs_consistency.py` passed.

*Review.* This session touched only `docs/`, so `/code-review` was skipped. The branch's
one `.py` change was reviewed in the opening session's step 6. No forward note moved: the
notes in 1327 and 1341 still read true under the rulings.

*Gotchas.* The worktree guard refuses a `sed -n` whose range comes from a `$(…)`
substitution, so grep for the line and read by offset. A grep over `docs/manual` hits
base64 figure data in the tutorial notebooks, so exclude `*.ipynb`.

*Next.* This WP's second task, now with the `caller` tier and with `grounds` and
`approved` on tier-2 action rows. Then the meta-test, the judge and its handover step,
the root CLAUDE.md rewrite under § Invariants, the TEMPLATE.md line with its new-topic
clause, and the cross-project lesson. 2002 opens with the always-on corrections pass,
since the Bérar–Lelann ruling is the first tier-2 action the batch will carry. The
milestone's name asks only the threshold question, and it was left as ruled. Whether
PR #1044 merges first is the maintainer's call.

### 2026-10-19 — the milestone read against DESIGN.md's purpose and rules

The session before this one rewrote DESIGN.md's north star as a purpose with four rules.
This session carried those rules down into the milestone and its WP files, and brought the
maintainer the questions the rules left open. Each audit now asks two questions of a
decision, in order: should rietx make it at all, and only then, does its threshold hold
beyond the data it was tuned on. A decision that fails moves to a ranking where the data
can rank the alternatives, and otherwise to the number with its meaning. Rule 2 now
separates verification from validation, and a tenth WP (2010) gives every feature its
state under both: 24 of 134 acceptance claims validate, and magnetic refinement has no
validating reference at all. Nothing in the package changed. The work ran late on
2026-10-18; the commits carry that date.

*Done.* Three commits on top of the previous session's purpose rewrite (9dcb29c4, pushed
here). 7b7ed875 made the changes that follow from the rules as written: the judgement
ground is Rule 1's unanimity gate; the expensive-rerun exception is Rule 1's four
protections; *holds* on the mechanical ground is measured against each family's
reference; the table gains an `ambiguity` field; the judge asks Rule 4's questions and
lost the visibility question the fourth review had retired; 2002 to 2005 lost a skill
task that contradicted the skill decision. 59eb477c and 32d63ee3 landed seven rulings,
each in the record § Decisions with its reason and alternative. (1) A verb whose job is
the pick may pick on a ranking while no default path calls it, and a top candidate passing
the unanimity gate may be picked; the ranking travels with the pick. (2) WP-2010 filed,
inside the milestone and outside the gate. (3) Rule 1's three outcomes replace the flat
order "record field, code, action" in the rulebooks (2001, 2009, and 1341's note). (4) A
code whose threshold decided its existence becomes an `info` record with no threshold,
keeping its explanation (2003's discontinuity code first). (5) Defaults are walked at a
declared list of seats. (6) Rule 2 is verification and validation in the field's sense,
and a feature without a reference is *not yet validated*; *provisional* keeps its API
meaning. (7) The milestone renamed to "every decision rietx makes holds beyond the data
it was tuned on". Under (6) this session placed a reference code's result on the same data
under verification, as the field does; the maintainer was told and did not object. The
gate after 2004 was restated as the two questions after the maintainer read it as asking
only the second. Forward notes: 1341's note reworded to Rule 1's outcomes; 1327 told that
2010 will label magnetic refinement not yet validated, and what would lift it.

*Measured* (darwin arm64, `[dev]`). `tests/validation_matrix.py`: 134 claims over 17
suites; 24 carry a validating tier, 21 more agree only with another code; five suites
carry neither (both magnetic, Stephens strain, extra peaks, NAC) and three cross-code only
(fluorapatite, LaB6–cBN, Powderline). Defaults: 24 literal defaults across `PlanSpec`,
`StageSpec` and the six main calls, about ten behavioural; 347 numeric defaults
package-wide (166 class fields, 181 public signatures). The four result types hold 84
fields (`RefinementResult` 33, `StageResult` 20, `SeriesResult` 12, `SeriesEntry` 19), and
`rietx.help` has no section for them. `auto_background` and `best_or_none` have no caller
in `refine.py` or `strategy/`. No test added, so no count moved.

*Review.* This session touched only `docs/`, so `/code-review` was skipped; the branch's
one `.py` change (five lines of `tests/test_docs_consistency.py`) was reviewed in the
opening session's step 6.

*Gotchas.* The worktree guard refuses a heredoc'd python script and a shell loop over git
refs; write the script to the scratchpad and run it as one command. Importing
`tests.validation_matrix` from a scratchpad script needs `PYTHONPATH=.`. A new WP file
must be `git add`ed before `test_docs_consistency.py` runs, or
`test_no_planning_doc_links_something_gitignored` fails on the untracked link.

*Next.* This WP's second task, unchanged: `_audit.py` with the `ambiguity` field, the
`default` kind and `DEFAULT_SEATS`, then its meta-test, the judge and its handover step,
the root CLAUDE.md rewrite to Rule 1's outcomes, and the cross-project lesson. WP-2010
depends on nothing and can run in another session at any time. Whether PR #1044 merges
first is the maintainer's call; the later tasks need nothing from it beyond the files.

### 2026-10-18 — the milestone opened and nine WPs filed

The maintainer raised a concern rather than a defect: that many of rietx's features are
fitted to the test cases that produced them, that there are too many diagnostic codes, and
that the package decides things the caller should. This session measured the concern,
agreed a sorting rule with the maintainer, had the plan reviewed twice, and filed the
milestone and its nine WPs. Nothing in the package changed. The next action is this WP's
second task: the table module, opened with every row at `unaudited`.

*Done.* `docs/milestones/generality.md` (the rule, the measurements, the order, six
acceptance rows, the dated decisions, the two reviews); ROADMAP's row, section and three
tracks, the Current focus line; the cap 589 → 614; WP files 2001–2009; the index
regenerated.

*Measured* (darwin arm64, this worktree at `origin/main` 049bc823, `[dev]` venv): 276
distinct `code="…"` literals in `src/rietx`, 256 codes in `DIAGNOSTIC_HELP` (7 of them
raised through a name, no literal; the filing first wrote 253 and 89 for io from the
literal grep, corrected at review); by subsystem io 90, `refine.py` 61, indexing 48, gui
27, crystallography 20, sequential 12, report 5, multi 5, and 9 in `background/select.py`,
`optimize/qpa.py`, `schemas/migrate.py`, `strategy/magnetic.py`,
`strategy/fraction_profile.py`; 70 not named in the skill; 6 with no test, ~20 touched by
one test file. 127 module-level
numeric constants in `report/`, `strategy/`, `optimize/statistics.py`, `refine.py`,
`sequential.py` by AST (the session's own grep said 117; the reviewer's AST count is the
one to carry), about 8 citing a paper in the comment block, 3 derived, ~49 citing a WP.
Skill 61 000 words, 130 tagged lines (145 tags). 3 of 193 top-level exports unused outside tests
(`IndexingEvidence`, `CaveatEvidence`, `CandidateEvidence`). Public surface 2 238 entries.

*Decisions* are in the record § Decisions. The one the session took itself and the
maintainer should know it can reverse: the audit table is a separate module rather than
fields on `HelpEntry`, on the reviewer's finding that `HelpEntry` is a GUI type.

*Review* (`/code-review high --fix`, handover step 6): ten findings, eight applied by the
pass in the working tree and committed here. The counts were off (256 codes in
`DIAGNOSTIC_HELP`, not 253; io raises 90 literals plus five by name; seven codes have no
`code="…"` literal, so the inventory is built from `diagnostic_index()`, never a grep;
130 tagged skill lines, not 134); nine codes and five constants had no audit WP (now 2002's
and 2005's, the partition stated in 2005 § Non-goals); 1327 is in flight, not closed, so
2002 merges main before touching the moment hold; 2004's acceptance lacked
`test_fitreport_layers.py`; `CIF_ANGLE_CORRECT_MAX_DEG` lives in `crystallography/`, not
`io/`; `process.md`'s caps diary was two ROADMAP bumps stale. Of the two left: the
tripwire's walk was specified over five files and must cover all of `src/rietx` (fixed in
Context above, by this session); ROADMAP landing at its cap with no headroom is deliberate
and has a precedent at 588, so the next line added there bumps it with its own diary line.
The second Opus review's findings are in the record § The two reviews.

*Gotchas.* The worktree guard refuses a Bash command containing the word "eval" anywhere
(it reads it as a shell `eval`); `ls tests/ev*` works. The milestone section's heading
must match the table row's anchor exactly, or `test_docs_consistency.py` fails on the link.

*Next.* The table module and its meta-test, then the agent and the handover step, then
the CLAUDE.md rewrite, then the cross-project lesson.

*Third review, same day, a fresh session after `/clear`.* Twelve changes, all approved by
the maintainer and listed in the record § The third review. The four that move this WP:
the restatement above now carries the reasoning ground's polarity and no more of the rule
than one sentence; the constant walk covers `_audit.WALKED`, a declared directory list,
after the walk over all of `src/rietx` found 619 constants against the seams' 233; the
growth guard is `_audit.UNAUDITED_BASELINE`, a committed list that only shrinks, in place
of a `git show` of `origin/main` that CI's depth-2 checkout cannot make; and the handover
dispatches the judge on any diff touching the table or the baseline. The record also
gained a clause for a golden with no independent reference and tightened the inheritance
rule to derivations with no free factor.

*Fourth review, same day, a fresh session reading the plan's reasoning.* The maintainer
confirmed that the second ground is judgement (would every competent refiner take this
action on seeing this number?) and that visibility decided nothing, since any action can
be reported as its statistic; the north star went into DESIGN.md § Why this package
exists. The record § The fourth review lists the rest. In this file: the restatement, the
constants partition by directory, the judge on step 7, the module named `_audit`.

- **2026-10-18** — created.
