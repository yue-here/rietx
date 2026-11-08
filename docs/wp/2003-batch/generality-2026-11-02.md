# WP-2003 generality review, 2026-11-02 (fifth session: C1, C2 q5, C3)

The `generality-review` judge's verdicts on the fifth session's audit-table change, condensed
from its report by the session (one row per item; the judge's tables carried seven questions
each). No item `fails`. The author's answer follows each `weak`.

| Item | Verdict | The judge's reason | What would change it |
|---|---|---|---|
| `SeriesEntry.rwp_over_median` (added, tier 1, kind 3) | **weak** | A sound record, but § Demotion asks a demoted statistic for "every candidate, largest first … one line naming the field" in the full report; `SeriesResult.summary` has that line for `series.steps` (C4) and none for this field, the plot no longer marks the point, and it is now the only trace of planted's unmodelled phase. Filed as kind `action` though it reports no action by default (`OTHER_RECORD_FIELDS` is the module's seat for such a field). | A summary line naming the largest ratios, plus an agent run on planted that finds the phase from this field. |
| `SEQUENTIAL_RESEED` → 3, warning; suggestion → 1 | holds | Reports the package's own restart; silence pair in place. Every firing count quoted was taken under the removed fence. | Firing counts per family on the final tree. |
| `SEQUENTIAL_UNRECOVERED` → 3, warning; suggestion → 1 | holds | Fires on the one known-broken pattern (tut05-broken scan12, Rwp 0.969 on every rung), silent where nothing failed. | A family where a converged pattern carrying an error-level code is still a sound measurement. |
| `SeriesEntry.reseeded` → 3; `seeded_from` evidence | holds | Records of acts. `seeded_from`'s tier (3 in the table, "tier 1, a record" in batch C2) is the 2026-10-26 judge's open disagreement, still unresolved. | scan13's values with and without the quarantine against the clean series. |
| `fit:reseed` → 3 (True) | holds, narrowly | No program restarts a pattern by itself; the one firing on the final tree (scan12) buys nothing, three rungs at one Rwp. The grounds' word "unfinished" is wrong now, `max_iter` triggering nothing. No field says *which* trigger fired. | A measured rescue on a real family under the final default. |
| `fit:reseed_factor` → caller (1.25 → None) | holds | The case against a default fence is measured; every rescue it had on disk is caught by q5 or no longer happens. | A converged warm fit with no error code, high against the median, wrong against a validating reference and fixed by a cold start. |
| `fit:first_rung_factor` → caller (3.0 → None) | holds | Not invariant at 3.0. The row's headline omits that removing the bound moved T087 *away* from the planted truth in the batch's measurement (0.00597 bounded against −0.0231(48) unbounded, truth 0.006), and the final tree's T087 distance is not given. | T087's scale and zero shift against the truth on the final tree, with and without 3.0. |
| `FIRST_RUNG_SAMPLES` → 3 | **weak** | Its evidence (16 against 17 evaluations at one sample; the 1.29 calibration) is of the summed rung, which C3 replaced with the dearest stage; two samples were never tried; the batch's alternative (a caller argument) was not taken. | The sample-size failure re-measured on the dearest-stage quantity at 1, 2 and 3 samples on three families, or the count made a caller argument. |
| `RESEED_FACTOR` deleted | holds | As `fit:reseed_factor`. | A lost rescue on the final tree. |
| `SEQUENTIAL_RWP_OUTLIER` (+ suggestion) deleted | **weak** | The letter of § Demotion is followed (its threshold decided whether the code existed), but it was already a kind-3 report that told planted's fault from its null twin (fired from T134, zero on the null and on CPD, and alone marked the transition planted alone), and its replacement is not surfaced. `docs/practice.md`'s rietx row is stale. | A ranked summary line for `rwp_over_median` and an agent run that finds the phase from it. |
| `SeriesEntry.rwp_fence` deleted | holds | Replaced; an old document's key is dropped at read. | — |
| `FIRST_RUNG_FACTOR` deleted | holds | As `fit:first_rung_factor`. | — |
| `schemas.sequential._rejected` (not a row) | holds on judgement, **weak** on record | The package's own `error` level says "do not read the values" and a warm start reads them. But today the only error-level code a refinement raises is `MODEL_FAR_FROM_DATA`, Rwp > 0.8 alone, so the predicate brings back an absolute Rwp gate, the shape C1 removed: a low-count series under a right model with Rexp near 0.8 would be quarantined (none on disk; the test plan `_CHEAP` had to be widened for exactly this). Every future error-level code becomes a chain trigger. `MODEL_FAR_FROM_DATA_RWP`'s row (tier 3, approved 2026-10-19) does not name the chain as a consumer. | A measured low-count series showing whether `MODEL_FAR_FROM_DATA` fires under a right model, and the threshold's row naming the chain. |
| `_cut_by_bound` / `_stage_peak` (not rows) | holds | Consistency fixes inside an opt-in, each tested; stage names are matched without a uniqueness check. | Duplicate stage names reaching `_cut_by_bound`. |

**The author's answers to the four `weak`s.**

- `rwp_over_median` and the removed outlier code: agreed, and it is the next commit's work, not
  a re-rule. § Demotion's ranked line is owed (`SeriesResult.summary` naming the largest ratios,
  as it names `series.steps`), and the agent run on planted is the harness's to schedule.
  Moving the row to `OTHER_RECORD_FIELDS` rides that commit.
- `FIRST_RUNG_SAMPLES`: agreed that its evidence is stale. It is read only inside an opt-in no
  default path reaches, so the re-measurement waits for a caller who uses the bound; the batch's
  other option (a caller argument) is the cheaper fix if one does.
- `_rejected`'s record: the forward note to WP-2005 (`### Inherited`, 2026-11-02) asks that
  `MODEL_FAR_FROM_DATA_RWP`'s row name the chain; the low-count case is unmeasured and is the
  dissent the maintainer should weigh.
- `docs/practice.md`: every rietx row naming the fence, the outlier code or the bound is
  updated (the series-restart table row, the defaults paragraph and the sources row).
