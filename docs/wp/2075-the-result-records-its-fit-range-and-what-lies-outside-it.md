# WP-2075 — The result records its fit range, and what lies outside it

Milestone: unscheduled · Status: 🔄 2026-11-09 — tasks 1-4, 6 and 7 landed in PR #1480; task 5 and four rulings wait on the maintainer
Track: What fires, and what stays silent
Depends on: — (2005 soft: `LOW_ANGLE_UNMODELLED`'s retext points at this field)
Priority: P3 2026-10-31 — a fact the result says less about than it could: the caller chose the cut, but after it nothing in the result says a cut happened or what it removed (42 % of the counts on the issue's planted case, 22.5 % on SRM 1976a)

## Goal

A `RefinementResult` says which part of its file it fitted: the file's range, the limits asked
for and applied, the excluded regions, and the counts on each side. Beside it, a short set of
facts about what lies outside each cut: its share of the counts, its level and slope against
the fitted range, the largest peak-like feature there, and any reflection straddling a range end.

## Context

**Source.** Issue #1219 (mustachefeeling, 2026-10-29), the first of a series of report-only
proposals (#1215-#1218).

**Checked against the tree at d87c8cc91.**
- `RefinementResult` (`schemas/results.py`) has no limits, excluded-region or file-range field.
  The fitted channels are on it (`two_theta`), so the fitted ends can be read off; nothing else.
- The history node does carry the limits (`schemas/history.py:295`,
  `RefinementState.two_theta_limits`), and `project.json` the excluded regions (WP-1033). The
  result alone, as dumped by `model_dump(mode="json")`, carries neither.
- `Refinement.summary()` prints `excluded:` (`refine.py:6362`) and no limits.
- The pdCIF writer (`io/cif/powder.py:172-181`) writes `_pd_meas_2theta_range_*` and
  `_pd_proc_2theta_range_*`, but only when handed the pattern.
- The recipe reader already names a `fit_range` (`io/recipe.py:207`, `payload.fit_range`).
- The whole-pattern DW (`optimize/statistics.py:998`) and the Bérar–Lelann factor (`:1003`,
  `berar_lelann_factor`) run over the fitted array as one sequence, so a channel below an
  excluded band is paired with the first above it. `report/background._pooled_durbin_watson`
  already drops such pairs for the background mask.

**Why the record matters** (the issue's measurement, not re-run). Synthetic cubic perovskite,
capillary, a planted low-angle rise (20× mean background at 5°, 3° decay), cut at 9-22°, three
seeds each. Cut at 9-16°: `LOW_ANGLE_UNMODELLED` fires 12/12 and suggests raising the limit to
22.6°. Cut at 22°: silent 3/3, χ²_red 0.98-1.00, the multi-scale residual scan under its null;
42 % of the file's counts lie below the cut and nothing says so. A limit at the centre of the
last reflection: χ²_red 1.00, half of (420) outside, nothing says so. On public data: SRM 1976a
(limits 20-118.6° of a file starting at 5.50°) has 22.5 % of its counts below 20°, level 2.8× the
in-range median; 11-BM LaB6 660a (2-60° of 0.50-67.0°) has 4.0 % outside and an 11.6σ feature at
62.8° above the upper limit. WP-1517's row 6 saw the same from an agent: it cut past a strong
line and nothing reported it.

**Prior art.** pdCIF separates measured and processed ranges and records excluded regions as
text; rietx's writer follows it. GSAS-II, FullProf and TOPAS keep limits and exclusions in the
project or input file, not in a fit-quality report (the issue's recall; not re-read in triage).
None reports what the cut removed, as far as checked.

**Tiers and rules.** Chunk 1 restates the caller's own act: tier `caller`, a new
`_audit.ROWS` row. Chunk 2 computes facts with no null and no threshold, gated on nothing:
Rule 1's third kind. Its reporting windows (1° at a cut, 3 FWHM for a straddling reflection,
the running-minimum width for "peak-like") are tier 3 and need the maintainer's dated approval.
`fit()` is the only place the full `PatternData` is at hand (`report()` holds no pattern), so
chunk 2 is computed there.

**Decisions for the maintainer.**
- A new `RefinementResult` field is a stored-format change (`SCHEMA_VERSION`).
- Whether `fit_range` shares one type with `ProjectDoc.two_theta_limits` and the recipe's
  `fit_range` (the issue's question 1).
- Task 5 moves every esd on a fit with an excluded region (f multiplies every esd); goldens
  move. Only if wanted.

### Inherited

(none)

## Non-goals

- `LOW_ANGLE_UNMODELLED`'s suggestion and help text: WP-2005 (a `suggestion=` site, in its
  batch).
- Any new diagnostic code, threshold or change to what is fitted.
- The residual-structure rows at a cut's edge (#1215): the residual-structure WP.

## Tasks

- [x] `RefinementResult.fit_range`: file range and point count, limits requested and applied,
      excluded regions declared and applied, counts in the file and in the fitted channels.
      JSON round-trip; `_audit` row at tier `caller`; `SCHEMA_VERSION` as ruled. (2026-11-09:
      `schemas.results.FitRange`, built by `report.fit_range.fit_range_record` in `_fit_pass`;
      the schema rule is WP-1117's, so it joins 0.61, the version in flight since v1.11 shipped
      0.60; `tests/test_fit_range.py`.)
- [x] `summary()`'s protocol block prints one line from it (in place of, or beside,
      `excluded:`, as ruled). (2026-11-09: beside it, the reversible choice, until ruled;
      `FitRange.line()`; the NAC termination golden gains the line.)
- [x] Chunk 2 facts, computed in `fit()`, on `fit_range` or a sibling field: per excluded band
      and range end, the share of counts outside, level and slope ratio against the in-range
      median, the largest peak-like feature beyond, the fitted background's slope at the edge,
      reflections predicted in excluded bands, reflections within 3 FWHM of a range end with
      the fraction of profile outside, and `signal_cutoffs` where the caller ran it.
      (2026-11-09: on `fit_range.outside`, one `OutsideSpan` per unfitted stretch,
      `report.fit_range.describe_outside`; "peak-like" is the excess over
      `background_envelope`, whose window is already ruled, so no third window; the two
      reporting windows `CUT_WINDOW_DEG` and `STRADDLE_FWHM` enter at tier 3 awaiting approval.
      Not done: `signal_cutoffs`, since `fit()` has no channel that says the caller ran it — to
      the follow-up issue.)
- [x] The pdCIF writer reads the range from the result when no pattern is handed.
      (2026-11-09: `io/cif/powder.py`, the measured count and range and the unfitted
      stretches from `fit_range`; no `_inc`, the grid not being at hand.)
- [ ] Optional, only if ruled: DW and the Bérar–Lelann factor per contiguous fitted run, as
      `_pooled_durbin_watson` already does; goldens re-pinned under the root rule.
- [x] Tests: the issue's C7 cut at 22° and C8 limit at the (420) centre; a fit with no limits
      prints equal ranges; SRM 1976a and 11-BM LaB6 660a with their acceptance limits.
      (2026-11-09: `tests/test_fit_range.py` — C7 at all five cuts, C8 at 0 and −0.5 FWHM;
      one row each in `test_acceptance_srm1976a_texture.py` and `test_acceptance_capillary.py`
      on the suites' own fits.)
- [x] Skill: the reference row for `fit_range` if an agent reads it to judge a cut; else none.
      (2026-11-09: none. `summary()` prints the range line, and the package's own output is
      the cheapest place that holds it, WP-1338.)

## Acceptance

C7 at every cut reports the excluded band's share and level; C8 at 0 and −0.5 FWHM reports the
straddling reflection; a clean uncut fit reports file range = fitted range and nothing else;
the field round-trips through JSON.

```sh
.venv/bin/python -m pytest tests/test_result_rows.py tests/test_summary_deliverables.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

pdCIF dictionary (`_pd_meas_2theta_range_*`, `_pd_proc_2theta_range_*`,
`_pd_proc_info_excluded_regions`); Durbin & Watson 1950/1951; Bérar & Lelann 1991, J. Appl.
Cryst. 24, 1. Issue #1219; WP-1517 row 6; WP-1033 (the fitted mask).

## Handover log

- **2026-11-09** — ghostshift runner, PR #1480; follow-ups in issue #1481.
  A fit's result now says which part of its file it fitted. It records the file's range, the limits
  and excluded regions as asked and as applied, and the counts on each side. For every stretch the
  fit left out, it also records that stretch's share of the counts, its level and slope against the
  fitted range, its largest excess over the background envelope, and the reflections the model put in
  it or across its edge. `summary()` prints one line from it. The pdCIF writer reads it when no pattern
  is handed. The issue's cases come out as #1219 measured them. On family A cut at 22°, 44 % of the
  counts lie below the cut, at 1.3× the in-range median at the cut and 20× at the file's start. A
  limit at the (420) centre puts 47 % of that reflection outside. SRM 1976a has 22.5 % below 20°.
  11-BM LaB6 660a has an 11.6σ feature at 62.8°. Nothing reads any of it to decide anything.

  *Done.* `schemas.results.FitRange` / `OutsideSpan` / `ReflectionOutside` (schema 0.61, WP-1117's
  rule, beside the other 0.61 entries); `report/fit_range.py` (`fit_range_record`, chunk 1;
  `describe_outside` + `model_reflections`, chunk 2); `Refinement._attach_fit_range`, called by
  `fit`'s pass and by `run_stage` (the review found `run_stage` dropped the record); the summary line
  beside `excluded:`; `io/cif/powder.py`; `_audit` rows: `RefinementResult.fit_range` (action,
  `caller`), `report.fit_range.CUT_WINDOW_DEG` = 1.0 and `STRADDLE_FWHM` = 3.0 (tier 3, `grounds`
  written, `approved` absent). The record also carries the two widths it was read with
  (`cut_window_deg`, `straddle_fwhm`), from the generality review's finding 7. "Peak-like" is the
  excess over `background_envelope`, whose window is already ruled, so it adds no third window.
  WP-2005's `### Inherited` names the field for its retext. Nothing of `LOW_ANGLE_UNMODELLED` changed.

  *Measured* (arm64 Mac, `[dev]` venv). The lane's own family-A pattern (perovskite from
  `tests/planted_series.py`, capillary, λ 1.5406 Å, 5-130° at 0.01°, seed 7) gives these below-span
  values per cut:

  | Cut | Share | At cut | Far | Slope (/°) |
  |---|---|---|---|---|
  | 9° | 0.268 | 7.89 | 19.35 | 0.271 |
  | 11° | 0.323 | 4.71 | 19.41 | 0.245 |
  | 13° | 0.358 | 3.05 | 19.48 | 0.182 |
  | 16° | 0.392 | 1.92 | 19.55 | 0.100 |
  | 22° | 0.437 | 1.32 | 19.69 | 0.053 |

  - C8: `fraction_outside` of (420) is 0.471 at its centre and 0.862 at −0.5 FWHM.
  - SRM 1976a: share 0.225, at the cut 2.80×, far 5.71×, slope at the cut −0.013/° (flat to falling; not asserted).
  - LaB6 660a: below share 0.0097; above share 0.030, peak 11.6σ at 62.82°, 2 reflections listed.
  - Cost: 20 000 reflections across 6 spans on a 72 500-channel file take 0.05 s (review probe).

  Tests:
  - `tests/test_fit_range.py`: 16 tests.
  - `tests/test_exporters.py`: +1.
  - One row each in `test_acceptance_srm1976a_texture.py` and `test_acceptance_capillary.py` (slow).
  - Fast selection, arm64 Mac, `[dev]`, through `serial.py` and `testslot.sh` (alone, `-n 4`) at
    f1713917a: 5 failed, 14355 passed, 415 skipped, 32 xfailed in 10:13.
    - One failure is red by design (Gotchas).
    - The other four were this branch's misses, fixed in cbc6af89b and re-run file by file green:
      the help entry, the API partition (38 names deferred), the stale skill API index, and the
      validation-matrix rows for the two acceptance tests.
    - No `main` baseline was measured, so the added-test delta is CI's to read.
    - The full selection did not run. Pearl was not answering, and only the two acceptance rows
      above could move, run on their own: 1 passed each.
  - CI lint, run locally: ruff, `tests.skill_caps`, `tests.skill_surface` and `tests.audit_delta`
    all exit 0 (3 rows added, 0 new at `unaudited`). Vale shows 0 errors. `tests.reader_output`
    exits 0.

  Lanes: one, `lane: tests C7 C8 SRM LaB6 ~25` (22 tool uses). `session_usage.py lanes` found no lane
  dispatch in this session's transcript, so no trial row went to `process.md`.

  *Review.* `/code-review` could not be pointed at this worktree from a ghostshift runner, so an Opus
  subagent reviewed the branch diff. It found:
  - (1) a cut-free result without its pattern lost `_pd_meas_2theta_range_inc`: fixed.
  - (2) `run_stage` dropped the record: fixed.
  - (3) `reflections_searched` is approximate: documented.
  - (4) `_pd_meas_number_of_points` may exceed the loop's rows: documented.
  - (7) ratios on a non-positive reference: now `None`.
  - (8) declared peaks are not listed: documented.
  - Declined: (5) and (6). These were to carry channel indices from chunk 1 to chunk 2 and to share
    `_runs` with `io/cif/powder.py`. Both are simplifications with no effect on behaviour.

  *Generality* (the judge's verdicts, condensed; its full tables are in the PR body):
  - `RefinementResult.fit_range` **holds** at `caller`.
  - `CUT_WINDOW_DEG` **weak**. It found no failure case, and a fixed 1° is a fraction of a FWHM on
    11-BM but 1-3 FWHM on a broad neutron or nanocrystalline pattern, where one reflection's flank sets
    the level and slope. It was also not on the record; it now is.
  - `STRADDLE_FWHM` **holds**, and could move to tier 1 once the cap is recorded (done) and a
    completeness test exists. It noted the listing ignores intensity; that went to #1481.
  - "Peak-like" **fails as worded**. The raw envelope is biased low, and the largest of N channels
    reads several σ on a featureless span. The docstring now says it is a location, not a detection.
    The debiased envelope went to #1481.

  *Gotchas.*
  - `test_audit_table.py::test_an_audited_row_carries_its_evidence` is red by design until the
    maintainer writes `approved` on the two tier-3 rows. Never revert them to `unaudited`.
  - Past a range end, the model generates reflections only within `REFLECTION_MARGIN_DEG`, so an
    empty list there means nothing further out (#1481 item 2).

  *Questions for the maintainer* (also in the PR body):
  - (a) The dated approval, or a retier, for `CUT_WINDOW_DEG` and `STRADDLE_FWHM`.
  - (b) Should the summary line replace `excluded:`? It now sits beside it.
  - (c) Should `fit_range` share one type with `ProjectDoc.two_theta_limits` and the recipe's
    `fit_range`? It now uses plain tuples (#1219 question 1).
  - (d) Task 5, DW and the Bérar-Lelann factor per contiguous fitted run, moves every esd on a fit
    with an excluded region. It is not built, as the WP says, only if ruled.

  Next: the maintainer's rulings, in this order:
  1. (a), which turns the one red test green.
  2. (b) and (c), each a small edit.
  3. Task 5, only if ruled, with goldens re-pinned.

  Then #1481's items. Item 2 (reflections over the whole span) is the cheapest, and the one an agent
  judging a cut would most miss.

- **2026-10-31** — created from the issue triage (#1219). No open WP owns a fit-range record:
  WP-1033 (✅) made limits and exclusions selectable and owns `project.fitted_mask`; WP-1517 (⬜)
  measures steers and names this case without a home; WP-2005 takes only the
  `LOW_ANGLE_UNMODELLED` retext.
