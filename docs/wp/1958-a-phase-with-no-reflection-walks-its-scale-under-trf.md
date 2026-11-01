# WP-1958 — A phase with no reflection in range walks its scale under TRF

Milestone: unscheduled · Status: ✅ 2026-10-31 — merged from outside as PR #1103 (in 1.10.0) and its follow-ups as PR #1176 (in 1.11)
Track: What fires, and what stays silent
Depends on: —

## Goal

A phase whose fitted range holds none of its reflections keeps the scale it
was given, under every solver, and the QPA reads no fraction off it.

## Context

Found by WP-1534 (2026-10-04) and re-measured by WP-1523 (2026-10-13), which
closed without an owner for it.

WP-1534's four-phase fixture (`tests/test_scale_b_ridge.py`) fitted over
25-33° Cu Kα leaves bcc Fe no reflection. Under `solver="trf"`, two
scale-and-background stages take Fe's scale from 1e-4 to 164.7, and the QPA
then reads iron at 99.99 wt%. `PHASE_UNCONSTRAINED` fires, in its third
wording ("no reflection of phase N lies in the fitted range"), and
`QPA_ESD_UNAVAILABLE` withholds the esds, but the fraction stands. Under the
default LM driver the scale stays at its start and QPA reads iron at
0.61 wt%, which is the start value, not a measurement either.

Repro: the fixture's `_models(START_SCALES)` on `np.arange(25, 33, 0.01)`,
plan `[Stage("s", BIG), Stage("s2", BIG)]`, `solver="trf"`.

**Why.** The support hold (WP-1301, `refine._hold_unsupported_phases`) holds
an unseen phase's structural paths and "never its scale, the one direction
that is not flat". That rests on the scale having a column. With no
reflection in range it has none: the column is identically zero, so TRF's
step along it is unconstrained by the data, while LM's damped step leaves it
in place.

Relevant rules, restated:

- **Root CLAUDE.md, "A phase the data cannot see is a flat direction"
  (WP-1301).** A flat direction is held for the stage rather than bounded.
- **"A direction the data does not move has no esd rather than a small one"**
  (WP-1110 item 14): the covariance already drops the zero column; the QPA
  marks its block unmeasured. The fraction is the open half.

## Non-goals

- Whether a phase is seen at all: WP-1523's significance, closed.

## Tasks

- [x] Reproduce under `solver="trf"` and the default LM in a test, and
      record the scale and the fraction at each stage.
- [x] Decide: hold the scale of a phase with no reflection in range, or have
      the QPA report no fraction for it. Record the choice and what moves on
      `tests/test_scale_b_ridge.py` and `tests/test_qpa.py`.
- [x] Land it, with a test under both solvers.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_scale_b_ridge.py tests/test_qpa.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1534's fixture, `tests/test_scale_b_ridge.py`; WP-1523's 2026-10-13
  handover entry, Findings.
- #954, the public report of this defect.

## Handover log

- **2026-10-31** (close, ghostshift batch, PR #1287) — closed. A phase with no reflection in the fitted range keeps the scale it was given under both solvers and has no weight fraction. The other fractions are relative to the phases seen in range, and the report says so. Nothing is owed: every task landed in PR #1103, and its follow-ups in PR #1176.
  *Done*: the two PRs' handover entries below are the record. This session only closed the bookkeeping: ✅, the `Priority:` line and the consumed `### Inherited` section deleted (it held the #954 decision, built by #1103), and the narrative moved to the v1.11 record.
  *Checked against the tree and `gh`*: #1103 (`594d7beb`) is in the `v1.10.0` tag and #1176 (`0a6142c3`) is not, so it ships in 1.11 (`docs/releases/1.11.0.md` carries its notes). The WP's status line asked for the v1.10 record. That release is cut, and protocol rule 5 names the record of the release in flight, so the narrative went to v1.11 and says #1103 shipped in 1.10.0. Acceptance: `tests/test_scale_b_ridge.py` and `tests/test_qpa.py`, run with `-m "not slow"` beside `test_satellites.py` and `test_rigid_body_special.py`: 200 passed, 2 warnings (macOS arm64, worktree `.venv` `[dev]`, Python 3.12, nothing else running).
  *What it does not do*: no release is owed. The WP was P3.

- **2026-10-31** (`/pr-review`) — the follow-ups merged from outside as PR #1176 (`0a6142c3`) after two rounds: the QPA trajectory's basis flag, a variable-held scale's message, joint scales tied to one variable, and the missing-radius advice. Round 2 closed the review's gap: `_constant_link_reach` (`multi.py`) blocks every coefficient of a link whose basis is not constant, so a + b·T on a scale over one wide and one narrow scan leaves the narrow scan's phase unmeasured, and a test pins it. `references/series.md` gains a measured bullet on `qpa_trajectory` and `basis_changes`. Gated in a stack of seven on `main` `d87c8cc9` (tree `21beeca9`, Mac arm64, Python 3.12, `[dev,jax]`): full suite 13 427 passed, 230 skipped, 48 xfailed, 0 failed; GUI, ruff and the `-W` manual build clean. #1257 stayed out on a hung CI job, and `main` after the six merges equals the checked six-PR tree `86997f50`. Two follow-ups from the PR's description wait to be placed: a test that the covariance read is exact, and `PARAMETRIC_TARGET_UNSEEN` on scale targets.

- **2026-10-24** — PR #1103 merged (`594d7beb`, review round 3), by `/pr-review`.
  *Done*: every task. A phase with no reflection in the fitted range keeps the
  scale it was given and has no weight fraction. The round-2 review added the
  case where a stage held the scale and a refined zero shift brings a line in by
  the answer. `QuantitativePhaseAnalysis.unmeasured_held` names that case, and
  `NodeMetrics.held_scale_phases` lets `replay` quote it the same way.
  Every text (summary row, CSV caveat, `MICROABSORPTION_SKIPPED`,
  `PHASE_UNCONSTRAINED`) reads its cause from that set.
  *Measured*: the whole suite on main `99b00b82` with this PR and four others
  stacked (macOS arm64, `[dev,jax]`): 12 063 passed, 3 failed, none of them this
  PR's; the fast selection on the final stack `bb654fd0`: 11 655 passed.
  *Gotchas*: the `RefinementResult.qpa` audit row's evidence first said a held
  scale's column "is zero"; at the answer it need not be, and the maintainer's
  commit `b6103ead` on the branch rewords it. #1128 (WP-2028) rebases onto this
  merge; both edit the joint report's `_phase_support_diagnostics` call.
  *Not done*: round 2's three read-only observations (a `vars.` variable's reach
  in the message, per-histogram scales tied to one variable, the radii wording)
  stay with the contributor as follow-ups.
  Next: close the WP, moving the 2026-10-22 narrative to the v1.10 record.

- **2026-10-22** — built both halves of the #954 decision. A phase with no
  reflection in the fitted range now keeps the scale it was given under LM and
  TRF alike, single and joint fits, and has no weight fraction; the other
  fractions are fractions of the phases seen in range, and the finding, the
  QPA table and the text summary say so. On the WP's repro the TRF walk to
  164.7 and the 99.99 wt% iron are gone, and the three seen phases now carry
  esds, since the zero column no longer sits in their sum.
  *Done*: the support hold takes a lineless phase whole, scale included
  (`refine._lineless_phases`, read off `phase_line_counts`), whatever
  `phase_support_sigma` says, and never releases it; the joint runner's
  `_unseen` does the same per histogram. `_quantify_phases` drops the phase
  from the sum and from the esd block; `PhaseQuantity.weight_fraction` is
  `None` for it and `QuantitativePhaseAnalysis.unmeasured_phases` names it
  (schema 0.59, additive). `PHASE_UNCONSTRAINED`'s third wording says the
  scale was held and what the fractions are relative to. Brindley is skipped
  with its reason while a phase is unmeasured (its µ̄ needs every fraction); a
  lone phase seen is 1 with no esd; `profile_fraction` refuses an unmeasured
  phase; `qpa_trajectory` skips its patterns. A scale a `ValueRestraint`
  pulls is left free (the restraint gives it a column), and
  `phase_line_counts` counts a reflection a magnetic window (`win_mag`)
  brings into range, both from the generality review below.
  *Measured* (`main` 4ca36160, the repro): LM scale 1e-4, iron 0.61 wt%; TRF
  164.73, 99.99 wt%; `QPA_ESD_UNAVAILABLE` on both. Here both 1e-4 exactly,
  iron `None`, corundum/zincite/fluorite 72.44/3.68/23.88 wt% ± 0.40/0.16/0.35.
  Joint fit of two copies under TRF on `main`: 214.1 and 2.31, now 1e-4 each.
  What moved on the tests: `test_held_phase.py`'s blind-range test asserted
  the old rule (scale never held) and now asserts the new one; seven new
  functions (ten items) in `test_scale_b_ridge.py` (acceptance under both
  solvers, the seen phases' positive arm, iron with a reflection under TRF,
  `phase_support_sigma=None`, a restrained scale, a magnetic window, the joint
  hold) and four in `test_qpa.py`. The first batch failed on `main`'s `src`
  (8 of 10 run there). Fast selection on the final tree (Mac, worktree
  `.venv`, Python 3.12, `-n 4`): 11 039 passed, 191 skipped, 2 xfailed; the
  12 added items cost 3.3 s locally (`tests.added_test_times`).
  *Gotchas*: with `phase_support_sigma=None` a lineless phase is still held,
  which `PlanSpec`'s description, `RefinementPlan`'s comment, the skill row
  and the 1.10.0 note now say. `RefinementResult.qpa` moved from
  `OTHER_RECORD_FIELDS` to a tier-1 action row; the `StageResult.held` row
  carries the extension in its evidence.
  *Generality* (the judge ran on the first commit; answers below each):
  `StageResult.held` (changed evidence) **holds**; weak case against: a
  `ValueRestraint` on the scale, and a magnetic-only window, could give a
  "lineless" scale a column. Author: both fixed and tested.
  Lineless hold at any `phase_support_sigma` **holds on substance, record
  weak**: three declarations still said `None` holds nothing, no test ran
  `None`. Author: the three amended, a `None` test added.
  QPA leaving the phase out **weak**: Brindley over the seen phases assumed
  the unseen one absent (kind 3); a lone seen phase read 1.000 ± 0.000; the
  action had no row (`RefinementResult.qpa` declared in
  `OTHER_RECORD_FIELDS`); `qpa_trajectory` changes basis unflagged if a line
  crosses the range edge mid-series. Author: Brindley now skipped with its
  reason, the lone phase carries no esd, `qpa` moved to a tier-1 action row;
  the trajectory flag is left to the reviewer (a series rarely moves a line
  across its edge, and `PHASE_UNCONSTRAINED` fires on each such pattern).
  Next: review on the PR; closing moves this narrative to the v1.10 record.

- **2026-10-13** — filed from WP-1523's close. No open WP owns it: 1534 and
  1463 are closed, 1420 is about a held phase re-entering a chain, and 1523's
  own subject was whether a phase is seen, not a scale with no column. Next:
  task 1.
