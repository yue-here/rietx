# WP-2075 — The result records its fit range, and what lies outside it

Milestone: unscheduled · Status: ⬜
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

- [ ] `RefinementResult.fit_range`: file range and point count, limits requested and applied,
      excluded regions declared and applied, counts in the file and in the fitted channels.
      JSON round-trip; `_audit` row at tier `caller`; `SCHEMA_VERSION` as ruled.
- [ ] `summary()`'s protocol block prints one line from it (in place of, or beside,
      `excluded:`, as ruled).
- [ ] Chunk 2 facts, computed in `fit()`, on `fit_range` or a sibling field: per excluded band
      and range end, the share of counts outside, level and slope ratio against the in-range
      median, the largest peak-like feature beyond, the fitted background's slope at the edge,
      reflections predicted in excluded bands, reflections within 3 FWHM of a range end with
      the fraction of profile outside, and `signal_cutoffs` where the caller ran it.
- [ ] The pdCIF writer reads the range from the result when no pattern is handed.
- [ ] Optional, only if ruled: DW and the Bérar–Lelann factor per contiguous fitted run, as
      `_pooled_durbin_watson` already does; goldens re-pinned under the root rule.
- [ ] Tests: the issue's C7 cut at 22° and C8 limit at the (420) centre; a fit with no limits
      prints equal ranges; SRM 1976a and 11-BM LaB6 660a with their acceptance limits.
- [ ] Skill: the reference row for `fit_range` if an agent reads it to judge a cut; else none.

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

- **2026-10-31** — created from the issue triage (#1219). No open WP owns a fit-range record:
  WP-1033 (✅) made limits and exclusions selectable and owns `project.fitted_mask`; WP-1517 (⬜)
  measures steers and names this case without a home; WP-2005 takes only the
  `LOW_ANGLE_UNMODELLED` retext.
