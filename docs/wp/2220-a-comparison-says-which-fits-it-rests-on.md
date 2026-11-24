# WP-2220 — A nested comparison says which fits it rests on, and which freed columns carried information

Milestone: unscheduled · Status: ✅ 2026-11-23 — PR #1717 merged on 2026-11-21 with both of Yue's rulings built; a comparison says which fits it rests on
Track: What fires, and what stays silent
Depends on: — (2076 soft: its extinction-screen nesting finding fences that caller out; 2053 soft: the same stationary-point t)

## Goal

`FreedComparison` (and the outcome of `predict_then_verify` and `rigid_body_misfit`) carries
how each of its two fits ended and whether the fuller fit's χ² sits at or below the restricted
one's. Each `FreedParameter` says whether it ended on a bound and why its t-ratio is absent.
A reader of the comparison alone can then tell a ΔBIC built on an unconverged or singular pair
from one built on two optimised fits.

## Context

Issues #1685 and #1686 (mustachefeeling, 2026-11-18), both on the comparison object WP-1417
built for #270. WP-1417 is closed (✅ 2026-09-27), so this is a new WP rather than a fold.

**What the comparison is.** `report.compare_freed(restricted, full)` takes two fits the caller
ran, a restricted one and one that frees more parameters. It returns ΔBIC charged at N_eff =
N/f² (f the restricted fit's `esd_inflation`), the same at raw N, and each freed parameter's
t = (value − held_at)/esd. There is deliberately no verdict field (`FreedComparison`'s
docstring, on `RivalComparison`'s precedent). Code at 7a4a6cd20:
`src/rietx/report/layer2.py:237` (`compare_freed`), `:277` (`_freed_comparison`; `n_added` at
`:309`, the t-ratios at `:349-352`, ΔBIC at `:358-364`); `src/rietx/report/schemas.py:1250`
(`FreedParameter`), `:1268` (`FreedComparison`), `:1472` (`VerificationOutcome`).

**#1685: neither fit's status is read.** A fuller fit that stopped on `max_iter` gives a ΔBIC
that can have either sign. A fuller nested fit whose χ² lands above the restricted one has not
reached its minimum, and nothing checks that either. Reproduced on 7a4a6cd20 (macOS arm64,
this worktree's venv) with the issue's own script, digit for digit:

| fuller fit | status | χ²_full − χ²_restricted | ΔBIC (N_eff) | La Biso t |
|---|---|---|---|---|
| run to convergence | `converged` | −447.1 | +269.1 | −19.1 |
| `max_iter=1`, Biso started at 4 | `max_iter` | +4374.9 | −1956.0 | +16.4 |

The result knows (`status='max_iter'`, `STAGE_MAX_ITER`), the comparison does not. Status alone
is not the whole test. The LM driver calls a slow-descent stop `converged` (`optimize/lm.py`,
#222), and a budget stop can land on the optimum (the reporter's `max_iter=2` from Biso = 8
stops at the converged χ², 5410.1). So the reporter proposes recording both statuses and a
χ² ordering flag, and flagging without refusing. Precedent for the ordering test:
`report/distortion.py:462-470` restarts when the restricted χ² sits below the full one.

**#1686: a freed column with no information is charged and not named.** A freed block whose
leading parameter ends on its zero bound leaves the others with zero columns: `esd=None`,
`t_ratio=None`, no reason. When the leading parameter ends just off its bound, a position can
end on its own bound with a large t that is no Wald number. Reproduced on 7a4a6cd20 with the
issue's script (a `PeakComponent` declared at area 0 over a pattern with no extra peak, area,
centre and fwhm freed):

| seed | χ²_full vs χ²_restricted | ΔBIC | centre | area | fwhm | full fit's own codes |
|---|---|---|---|---|---|---|
| 1 | equal to the last digit | −25.06 (= −3 ln N_eff) | esd None, t None | t 0.0 | esd None, t None | `EXTRA_PEAK_NO_INTENSITY`, `FLOOR_HIT` |
| 7 | −4.9 | −21.28 | 46.5 on its upper bound, t +8.5 | t 1.6 | t 0.34 | `BOUND_HIT` |

The ΔBIC errs on the safe side (nominal k over-charges), so the verdict is not wrong. What is
missing is what the reader is told.

**Authorities to read, never re-derive.** `RefinedParameter.at_bound` is a projection of
`staged.bound_findings` (CLAUDE.md, WP-1076/1434/1929), so a `FreedParameter.at_bound` reads
the fuller fit's row and stays set-equal to it. A zero column's absence of esd comes from
`statistics.normal_covariance` dropping it (`ParameterTable.unmeasured_rows`); WP-2219 (⬜)
moves which parameters lose their esd, so a `t_reason` here quotes whichever authority marks
the row. A new diagnostic code takes its `_audit` row, its `help.py` entry and its skill row.

**Three other ΔBIC callers compare two refits** (#1685's list, checked at 7a4a6cd20):
`predict_then_verify` (`layer2.py:1136`; accepts on a > 1 % χ² gain at `:1183` and attaches
`_freed_comparison`); `rigid_body_misfit` (`report/body_misfit.py:395-438`; Hamilton and ΔBIC
from both arms, no status read); the extinction screen (`indexing/extinction.py:1520-1528`).
The first two are this WP's. The extinction screen is fenced below.

**This changes what a fit returns.** The new fields and any new code are reader output, so they
go to the maintainer before merge (the maintainer's standing rule). Their names sit on `rietx.report`'s
public surface.

## Non-goals

- **The extinction screen.** WP-2076 measured that its class fit sits below the absence-free
  reference on every certified row (corundum, FAP, PbSO₄, Si: class χ² below reference χ²), so
  an ordering flag copied there would fire on every answer the suite certifies. Its ordering
  question is WP-2076's. A pointer is in that WP's Inherited.
- Refusing a comparison. Both issues propose flagging only, since a budget stop can sit on the
  optimum.
- Charging ΔBIC at the identified count. `n_identified` sits beside `n_added`; `delta_bic` stays
  charged at `n_added`.

## Tasks

- [x] `FreedComparison` records both fits' `status` and a χ² ordering flag (full ≤ restricted
      within the solver's ftol). Pin both rows of #1685's table.
- [x] A diagnostic on the comparison when either fit is not `converged` or the ordering fails,
      with its `_audit` row (tier: named practice for the ordering, since a nested optimum
      cannot rise), `help.py` and skill rows.
- [x] `FreedParameter.at_bound`, projected from the fuller fit's `RefinedParameter.at_bound`
      and pinned set-equal; a reason string where `t_ratio` is `None`. Pin both seeds of
      #1686's table.
- [x] `n_identified` beside `n_added`: freed columns that are live and off their bounds.
- [x] `predict_then_verify` and `rigid_body_misfit` take the same fields. A trial that stopped
      on its budget reads as not judged, never as a rejection (#1685 proposal 3).
- [x] Tests (unit, on the two synthetic scripts from the issues) + obs/calc/diff PNGs to
      `tests/output/`
- [x] Skill: the `compare_freed` reference row says to read the status and ordering fields
      before quoting a ΔBIC.

## Acceptance

Both issues' scripts print the new fields: the `max_iter` arm says it is unconverged and
unordered, seed 1 says two of three freed columns carry no information, seed 7 marks the centre
at its bound. Every existing `compare_freed` number is unchanged.

```sh
.venv/bin/python -m pytest tests/test_compare_freed.py tests/test_body_misfit.py -q
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Schwarz, G. (1978). Estimating the dimension of a model. *Ann. Stat.* **6**, 461-464.
- Hamilton, W. C. (1965). Significance tests on the crystallographic R factor. *Acta Cryst.*
  **18**, 502-510.
- Issues #1685, #1686; related #270 (WP-1417), #222, #538, #831, #1008, #1010 (WP-2053).

## Handover log

- **2026-11-23 (close, and a repair)** — closed by a ghostshift runner (batch
  close-2026-11-23, PR #1815), on a `main` that includes #1717.

  A reader of a ΔBIC comparison can now tell when it rests on a fit that stopped short, and
  which freed parameters carried no information. Both of Yue's 2026-11-20 rulings are built:
  the new fields and the `COMPARISON_UNCONVERGED` warning belong, and the ordering margin is
  2 cost units. Every task is ticked, and the work goes out with v1.13. This entry is also a
  repair. The session-start scan flagged the WP because one commit landed after the WP file
  was last touched, so the entry below reconstructs it.

  - *Checked before closing*: all seven tasks ticked. `gh pr view 1717` shows it merged on
    2026-11-21 at 00:37 UTC (merge commit a3c3acdc7). The one Inherited entry (WP-2219: a
    freed column can lack an esd because it lies on a discarded direction) is consumed:
    `report.layer2`'s `t_reason` names `COVARIANCE_DIRECTION_DISCARDED` in that case.
  - *Changed by this close*: Status ✅, the `Priority:` line removed (P2, so no release is
    owed), the consumed `### Inherited` section deleted, and the narrative moved to
    `docs/milestones/v1.13.md`.
  - *Siblings re-checked*: the 2026-11-20 entry left two unconverted. The magnetic search's
    ΔBIC now reads both fits' status (`MagneticTrial.fit_status` and the reference's, since
    #592), so that one is stale. `report.distortion.distortion_block_tests` still triggers
    its restart at `FTOL` relative on the data χ². That is a distortion-mode decision, Mike's
    since 2026-11-22, so it went to WP-1419's `### Inherited`.

  Next: none.

- **2026-11-21 (reconstructed post hoc)** — one commit after the 2026-11-20 entry, ced4338ef,
  from the session that ran PR #1717 to merge. Its message says CI run 44839377449 failed two
  tree-wide checks that the touched-area selection missed. `tests/silence.py` gained
  `COMPARISON_UNCONVERGED`'s pair. Stub fits through `_chi2_ordered` and
  `_comparison_unconverged` fire on a budget stop, a cost 2.001 over and a short restricted
  fit. They stay silent below, level and 1.999 over. `tests/data/gui/help_keys.json` gained
  the new help key. The diff is two test files, 42 lines added. The commit records no counts,
  and the PR merged at 00:37 UTC the same night.

- **2026-11-20** — both rulings made; the ordering margin is now 2 cost units (ghostshift
  runner). Main merged in at 8112e3b09 with no conflicts.

  *Ruled by Yue, 2026-11-20.* (A) Approved: every new field
  (`FreedComparison.status_restricted`/`status_full`/`chi2_ordered`/`n_identified`/
  `diagnostics`, `FreedParameter.at_bound`/`t_reason`, `VerificationOutcome.accepted:
  bool | None`, `BodyMisfitRow.status_body`/`status_released`/`chi2_ordered`, `fires:
  bool | None`) and the `COMPARISON_UNCONVERGED` warning belong, as PR #1717 describes them.
  (B) The ordering margin is option (iii): an absolute margin of 2, in units of the minimised
  cost (data χ² plus any restraint and penalty rows), replacing the relative
  `optimize.lm.FTOL` = 1e-9. `chi2_ordered` is True when the fuller fit's minimised cost is at
  most the restricted fit's plus 2. Grounds: the margin is then in the units ΔBIC is read in,
  and 2 is the lower edge of the "positive evidence" band of Kass & Raftery (1995, J. Am.
  Stat. Assoc. 90, 773), so an excess the margin hides cannot change a verdict. It sits far
  above measured stopping noise (1.1e-7 relative, about 0.0006 χ² units on the #1685
  fixture) until χ² reaches about 10⁷, the known limit. Rejected: 1e-9 relative (below the
  measured stopping noise between independently fitted arms); 1e-3 relative (GSAS-II's stop;
  about 6 χ² units on that fixture, already "strong" evidence, so it can hide a verdict
  flip); dropping the ordering warning.

  *Done.* `report.layer2.NESTED_COST_MARGIN = 2.0`, its docstring citing Kass & Raftery and
  stating the known limit; `_chi2_ordered` adds it to the restricted cost, and
  `compare_freed`, `predict_then_verify` and `rigid_body_misfit` all reach it there. Its
  `_audit` row is tier 2 (quoted from the literature), and `COMPARISON_UNCONVERGED`'s row no
  longer names FTOL. The warning now reads "ended at a cost more than 2 above the restricted
  fit's" in place of "ended at a higher cost than the restricted fit". Docstrings
  (`FreedComparison`, `BodyMisfitRow`, the 1.15 → 1.16 note), the `help.py` entry, the
  `diagnostics.md` skill row (copies re-synced) and the manual rows in
  `reference/comparison.md` say 2 in place of FTOL. One test added,
  `test_the_ordering_margin_is_two_cost_units_at_any_scale`: an excess of 1.999 and 2.0 is
  ordered, 2.001 is not, at a cost of 100 and of 10⁶, and on the stage-less fallback.

  *Measured* (macOS arm64, this worktree's `[dev]` venv, Python 3.12). #1685's script reads
  as before: ΔBIC +264.1 converged, −1941.3 on the `max_iter` arm, which sits 4365 cost units
  above the restricted fit and still reads unordered. Gates on the final tree: the touched-area
  selection (`tests/test_compare_freed.py`, `tests/test_body_misfit.py`,
  `tests/test_audit_table.py`, `tests/test_help.py`, `tests/test_skill.py`,
  `tests/test_docs_consistency.py`, `tests/test_manual_api.py`, `-n 4 --dist loadgroup`) 320
  passed; ruff clean; `ruff format --check examples/tutorials` clean; `tests.skill_caps`
  exit 0 (`diagnostics.md` +275 bytes, 1633 under its budget); Vale 0 errors, no warning on a
  line written here; `tests.reader_output` exit 0. The fast selection was not run locally.

  *Not generalised.* `distortion_block_tests` still compares at `FTOL` relative
  (`report/distortion.py`), a restart test outside this WP's diff; WP-2220's ruling names
  only `chi2_ordered`.

  Next: CI on PR #1717, then merge.

- **2026-11-19** — all seven tasks landed, PR #1717 (ghostshift runner). A reader of a ΔBIC
  comparison can now tell when it rests on a fit that stopped short. The comparison carries
  both fits' statuses, says whether the fuller fit's χ² sits at or below the restricted one,
  and adds a warning when either test fails. Each freed parameter says whether it ended on a
  bound and why its t-ratio is missing, and a count of the measured columns sits beside the
  count charged. The two experiments built on the same comparison, trying a suggestion and
  testing a rigid body, now answer "not judged" where a short fit could flip their verdict,
  instead of a rejection. Nothing is refused, and no number on a pair of converged fits moved.
  The PR waits on the maintainer: it changes what a comparison returns.

  *Done.* `FreedComparison.status_restricted`/`status_full`/`chi2_ordered`/`n_identified`/
  `diagnostics`; `FreedParameter.at_bound`/`t_reason`; `COMPARISON_UNCONVERGED` with its
  `_audit` rows, `help.py` entry, skill rows (`diagnostics.md`, `judging.md`) and manual rows
  (`reference/comparison.md`); `VerificationOutcome.accepted` and `BodyMisfitRow.fires` become
  `bool | None`; `BodyMisfitRow` gains both arms' status and `chi2_ordered`;
  `THRESHOLDS_VERSION` 1.15 → 1.16. Helpers `layer2._chi2_ordered`, `_comparison_unconverged`
  and `_judged` are the one authority for all three callers.

  *Measured* (macOS arm64, this worktree's `[dev]` venv, Python 3.12). The issues' scripts no
  longer reproduce digit for digit: main moved after 7a4a6cd20, and #1685's converged arm now
  reads ΔBIC +264.1 (was +269.1), its `max_iter` arm −1941.3 with χ² 4365 above the restricted
  one. The shape is unchanged. #1686 seed 1: `n_identified` 0 of 3 (centre and fwhm "no
  gradient", area on its zero bound); seed 7: centre on its bound at 46.5 with t +28.1 (was
  +8.5), `n_identified` 2. Ordering tolerance probe: refitting a converged fit's own free set
  from its answer moved χ² by 0 on four LaB₆ seeds and by −1.1e-7 relative on the correlated
  fixture, never upward, so `FTOL` (1e-9) does not fire on converged pairs there.
  Gates: touched-area selection (`tests/test_compare_freed.py`, `tests/test_body_misfit.py`, `tests/test_audit_table.py`, `tests/test_help.py`, `-n 4 --dist loadgroup`) 91 passed on the final code; earlier the same plus `test_skill.py`, `test_skill_cli.py`, `test_docs_consistency.py` all passed; ruff clean; Vale 0 errors (one warning on line 225 of `reference/comparison.md`, not written here); `tests.reader_output` exit 0. Eight tests added (seven in `test_compare_freed.py`, one in `test_body_misfit.py`), none marked slow. The local fast selection did not run: it queued 25 min behind another runner's slow suite on the machine lock and was cancelled, so CI's fast matrix is the first full fast run.

  *Review* (`/code-review high --fix`, 8 findings). Fixed: a diverged trial now stays a
  rejection rather than "not judged"; `BodyMisfitRow`'s new fields are required, not defaulted
  to an answer; the warning's last sentence no longer claims the ΔBIC "can have either sign"
  where the verdict stands; a zero esd no longer counts towards `n_identified`; the rigid-body
  test asserts which arm was short. Declined: the FTOL tolerance (probed above, no drift
  upward); `distortion.py` calling `_chi2_ordered` (outside this diff, its algebra is the same
  test); "rolled back" wording on an in-place trial (predates this WP); `n_identified`
  counting an untested bound (`at_bound` None) as off its bound, since every freed row of a fit
  with a guard report is tested and the alternative zeroes the count on every replayed result.

  *Settled for you* (each could have gone the other way):
  - The new diagnostic is tier 1 (arithmetic), not tier 2 as task 2 proposed. Settled by
    Claude under `docs/milestones/generality.md` § The rule, tier 1: "deterministic from the
    model"; a model containing another cannot fit worse at its optimum. Alternative: tier 2,
    citing `distortion.py`'s restart as practice.
  - "Not judged" is `None` on the existing verdict field (`accepted`, `fires`), not a new
    `judged` flag beside a `False`. Settled by Claude under root CLAUDE.md's WP-1076 rule ("the
    honest empty state is `None`") and `RefinedParameter.at_bound`'s precedent. Alternative:
    keep `bool` and add a field, which leaves `False` reading as a rejection.
  - The verdict rule follows the bias direction: a short fuller fit leaves a pass standing, a
    short restricted fit leaves a fail standing. Settled by Claude under the nested-optimum
    argument; the WP named only the first half. Alternative: every short fit gives `None`.
  - `COMPARISON_UNCONVERGED` fires on any short fit, even where the verdict stands. Settled by
    Claude on one rule over a rule with exceptions (DESIGN.md Rule 5). Alternative: fire only
    where the verdict is `None`.

  *After the judge.* The ordering test first read the data χ²; the judge showed that a fuller
  model with restraint or penalty rows can trade data misfit against them, so two true optima
  can sit in either order there. It now reads the last stage's `StageResult.cost_final`, what the solver
  minimised, for which the nested inequality is exact. Settled by Claude under arithmetic
  (generality tier 1); the alternative, skipping the test where restraints are active, loses
  the check on restrained fits.

  *Generality* (the `generality-review` judge, 2026-11-19, on the branch before the
  ordering moved to the minimised cost. Verdicts and their one-line grounds are the judge's
  words; its seven-question tables are condensed here by the author, so read a summary as
  the author's):

  - **`COMPARISON_UNCONVERGED` (code row, tier 1, ambiguity 1, warning): weak.** For the
    status test, the case for acting is stronger. For the χ² ordering test, the evidence does
    not carry the row's "arithmetic" claim or its tolerance, and the author's own probe points
    against the tolerance. Ambiguity: "a model that contains another cannot fit worse at its
    optimum" is true of the minimised objective S (data plus restraint and penalty rows); the
    test read the data χ² alone, so with soft restraints, a P-spline background or Pawley's
    equal-split rows two true optima can have data χ²_full above χ²_restricted. Tier: the
    tolerance is FTOL × 1 and FTOL's row is tier 3, so the threshold part inherits tier 3,
    untiered. Families: two synthetic materials from one source. Would change the verdict:
    independently fitted nested pairs with a dead freed parameter, with and without active
    restraints, silent; or a row that limits the claim and tiers its tolerance.
    *Author:* the ordering now reads `cost_final`, the minimised S, so the restraint route is
    closed by construction; the row's evidence now names the tolerance as inherited tier 3
    and waiting on the maintainer.
  - **`COMPARISON_UNCONVERGED.suggestion` (tier 1, ambiguity 1): holds.** The remedy is cheap,
    and starting the fuller fit from the restricted fit's values guarantees the ordering.
  - **`report.layer2._judged` (not visible to the table): holds.** The bias-direction argument
    is arithmetic, every branch checked against the nested-optimum argument, and withholding
    costs one rerun. Its converged-but-unordered branch inherits the FTOL weakness; there the
    reason text "more iterations could still gain" fits a restart from the other fit's values
    better than more iterations.
  - **`optimize.lm.FTOL` as the ordering tolerance (1e-9 relative): weak.** FTOL bounds the
    per-iteration relative decrease, not the gap to the optimum; the probe's −1.1e-7 shows a
    converged fit stopped at least 1.1e-7 above its optimum, 110× the tolerance, and "never
    upward" holds by construction for a refit started at the answer, so it tests the
    `predict_then_verify` shape and not independently fitted arms. GSAS-II's default stop is
    1e-3 relative (`docs/practice.md:139`). No test asserts the margin. Tier 3, unapproved for
    this use. Would change the verdict: independently fitted pairs across three families
    silent at 1e-9, or a tolerance in esd or χ²_red units with its own evidence.
    *Author:* not settled; it is a threshold over a fit metric, the family the 2026-11-16
    reversal escalates, so it is the maintainer's question below.
  - **Skill rows (`judging.md`, `diagnostics.md`): holds.** They name a code and a field; the
    boundary rule has a source in the repository (Self & Liang 1987, cited at
    `optimize/statistics.py:488`). They are stricter than the manual ("quote neither number").

  *Questions for the maintainer* (reader output, waits before merge). (1) The new fields and
  the warning, in PR #1717's "What a reader receives". The 2026-11-16 reversal ("a field, and
  the caller decides") is about tuned thresholds over fit metrics; the status half has none, so
  the warning was kept as task 2 asked. (2) The ordering margin. It is the solver's stopping
  tolerance, 1e-9 relative, reused unvaried; the judge rated it weak, since a converged fit was
  measured stopping 1.1e-7 above its own optimum. Inside `compare_freed`'s usual shape (fuller
  fit branched from the restricted answer) it cannot fire falsely, because the solver accepts
  only downhill steps. Between independently fitted arms it could. Options: keep 1e-9; take
  GSAS-II's 1e-3 stop; or state it in χ²_red units. If you prefer fields only, delete the
  diagnostic and its rows.

  *Not generalised.* `distortion_block_tests` and the magnetic search's ΔBIC
  (`strategy/magnetic.py`) also read no solver status; the extinction screen stays fenced to
  WP-2076. Magnetic-path decisions are Mike's.

  Next: the maintainer reads the reader-output section of PR #1717 and rules on the warning;
  then merge.

- **2026-11-19** — created, from the 2026-11-19 issue triage (PR #1697; issues #1685, #1686). A reader of
  a ΔBIC comparison cannot yet tell when it rests on a fit that never finished, or when it
  charges parameters that carried no information. Checked against the tree at 7a4a6cd20: both
  issues' scripts reproduce digit for digit on macOS arm64; `_freed_comparison` reads no
  `status`, and `FreedParameter` has no `at_bound` or reason field. No open WP owns it: WP-1417
  built the object and is closed; WP-1998 and WP-2115 own the suggestion score, not the
  comparison; WP-2076 owns the extinction screen's nesting and is fenced out above. Combined
  because both edit the same two schema classes and one builder, with the same fixture style.
  Next: task 1.
