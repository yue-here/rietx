# WP-2003 generality review, 2026-11-03 (sixth session: the batch's rulings landed)

The `generality-review` judge's verdicts on the sixth session's audit-table change, condensed
from its report by the session (one row per item; the judge's tables carried seven questions
each). No item `fails`. The author's answer follows each `weak`. Evidence the judge found stale
was corrected in `b6e73fd`.

## Heuristics the table cannot see

| Item | Verdict | The judge's reason | What would change it |
|---|---|---|---|
| The joint fit's support hold (`multi._joint_answer_significance`: each histogram takes the smaller of the screen and the joint marginal z) | **weak** | Every refiner would act on the blank frame's cell, reported at 4.1517 ± 0.0168 Å. But the 10 moved records are not listed with their sizes; one synthetic family; the measurement drops the caller's histogram weights, and the docstring said it was the solve's own matrix; three other joint readers (`_parametric_unseen`, the form test, `_freeze_cell_windows_multi`) still read the screen alone. | The 10 moved records with sizes, and a weighted test or a corrected docstring. |
| `_same_objective` and `_better` (S where the objectives match, Rwp otherwise) | **weak** | S is right by definition where the objective is shared. The Rwp fallback fires exactly when σ differs, and Rwp under differing σ ranks nothing either (root CLAUDE.md). Two rungs' S may also differ by window truncation, about 6e-5 relative, unmeasured as a tie-breaker. "Left Claude's to settle" is Claude's sentence. Nothing records which criterion decided. | The fallback on one shared σ (or "not comparable"), and a maintainer line on the `max_iter` tie. |
| `_prefer` tests `_rejected` before truncation | holds | Consent line (1); never acts on the default path, since truncation needs `first_rung_factor`. `_rejected` covers every future `error`-level code. | — |

Author's answers:

- *Joint hold.* The docstring now says the histogram weights are set to one, so a phase is judged against each pattern's counting noise whatever weight the caller gave its histogram. That is the single fit's question, and support is a fact about the data. The 10 moved records go to the maintainer in PR #1310. The three screen readers stay in WP-2003's Next, each needing its own measurement.
- *S then Rwp.* Agreed that the fallback compares two weightings. On the one family measured (CPD, 22 forced attempts) σ never differed, so no case on disk reaches it. It stays the WP's open item beside C2's rung tiers.

## Added rows

| Item | Verdict | The judge's reason |
|---|---|---|
| `SEQUENTIAL_PATH_CHECK_NOT_RUN` (+ suggestion) | holds | Reports a check the caller asked for that did not run; consent line (3). |
| `SeriesEntry.rwp_over_median` | holds (ruled) | Field only, ruled 2026-11-03 with its cost (planted's unmodelled phase and WP-2081's pattern 3 now unmarked) in the brief. |
| `SeriesResult.code_counts` | holds | Brief 4. |
| `SeriesResult.direction_gaps` | holds | Consent (2). |
| `SeriesResult.steps` | holds (note) | C4's demotion of `SEQUENTIAL_DISCONTINUITY` was Claude's settlement and never went to the maintainer. |

## Changed rows

| Item | Verdict | The judge's reason |
|---|---|---|
| `PHASE_HELD_IN_PATTERNS`, `SEQUENTIAL_PATH_CHECK_INCOMPLETE` (+ suggestion), the two `.suggestion` rows of RESEED and UNRECOVERED, `SERIES_PATTERN_FAILED`, `StageResult.held`/`.released`/`.collapsed`, `SeriesEntry.floored`, `.reseeded`, `.seeded_from`, `NOISE_FLOOR_REL`, `fit:direction`, `fit:verify_steps`, `fit:on_error`, `fit:plan`, `fit:reseed_factor`, `refine_sequential:carry` | holds | Pointer or wording updates, or ruled. |
| `SEQUENTIAL_RESEED` | holds, evidence weak | Its firings were all under the removed fence; this tree's are the path guide's 800 K pattern, the magnetic blank frame and tut05-broken scan12. The ruled trigger names WP-2080's GoF step, not yet in the code. |
| `SEQUENTIAL_UNRECOVERED` | holds, one open | The fifth session's open question stands: `_rejected`'s error half is mostly `MODEL_FAR_FROM_DATA`'s Rwp > 0.8 gate, unmeasured on a low-count series under a right model (forwarded to WP-2005). |
| `SeriesEntry.rung` | **weak** | Its approval date covers the q2 order only; the S/Rwp criterion and the `max_iter` tie are Claude's settlement. The batch's dissent is not in the row. |
| `FIRST_RUNG_SAMPLES` | **weak** | The 2026-11-03 sweep shows no dependence on the sample count at factor 1.0 or 1.5, so 3 rests on a failure measured on the quantity C3 replaced. Low stakes: never on a default path. |
| `fit:first_rung_factor` | holds, evidence weak | The evidence quoted main's T087 number without its direction and without this tree's. |
| `fit:reseed` | holds, wording weak | "Unfinished" misdescribes the trigger, and the grounds did not say that none of the seven programs restarts a pattern by itself. |
| `refine_sequential:carry_hkl_intensities` | **weak** | No program carries the intensities by default, and carrying costs evaluations on planted (+10 % Le Bail, +30 % Pawley). No measured benefit. Approved by the maintainer. |

Author's answers:

- *`SeriesEntry.rung`.* The row already says which half was ruled and which settled. The criterion goes to the maintainer with C2's rung tiers, the WP's next item.
- *`FIRST_RUNG_SAMPLES`.* Agreed that the sweep cannot separate 1, 2 and 3. The maintainer approved 3 on a consent line that quoted that sweep. It is read only inside the opt-in.
- *Evidence rows.* Corrected in `b6e73fd`: the first-rung row now gives T087's direction and this tree's measurement; reseed's grounds drop "unfinished" and name the practice gap; `SEQUENTIAL_RESEED` names this tree's firings.
- *`carry_hkl_intensities`.* The grounds now say no program carries by default and that it costs evaluations on planted. The maintainer ruled with those numbers in the brief.

## Deleted rows and bookkeeping

| Item | Verdict | The judge's reason |
|---|---|---|
| `SEQUENTIAL_RWP_OUTLIER`, `SEQUENTIAL_PATH_DEPENDENT`, `SEQUENTIAL_PERSISTENT_FINDING` (+ suggestions), `PATH_DEPENDENCE_SIGMA`, `MIN_POINTS_FOR_PERSISTENCE`, `SeriesEntry.rwp_fence`, `RESEED_FACTOR` | holds | Ruled (briefs 2 and 4, consent 2, C1). |
| `FIRST_RUNG_FACTOR` | holds | Removal rests on Claude's C3 settlement, which never went to the maintainer; it changes what a fit returns by at most 4.8e-7 esd on this tree. |
| `UNAUDITED_BASELINE` (25 removed, none added), `RECORD_SCHEMAS` + `SeriesResult` | holds | — |
| `OTHER_RECORD_FIELDS` + 13 `SeriesResult` fields | **weak** for `relative_paths` and `angle_paths` | The inventory calls `sequential._relative_paths` a tier-1 arithmetic action (it leaves those DOFs out of the step and gap scans), so now that `SeriesResult` is a record schema these two report an action and belong as tier-1 action rows. |

Author's answer: *`relative_paths`, `angle_paths`.* Agreed. Moving them to tier-1 action rows is in WP-2003's Next, beside C11.
