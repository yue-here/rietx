# WP-2079 — a non-finite count or σ in a pattern file is dropped, and the reader says so

Milestone: unscheduled · Status: ✅ 2026-11-03 — every pattern reader drops a non-finite row and says so; message text approved by Yue (PR #1359)
Track: What fires, and what stays silent
Depends on: —

## Goal

Every pattern reader drops a row whose count, σ or 2θ is NaN or ±inf, and
says which rows it dropped by their 2θ range. No non-finite value reaches a
`PatternData`.

## Context

**The report (issue #1187).** `read_pattern` passes non-finite counts and σ
through, and no diagnostic names them. The reporter's file is
`PLANTED_nan_block_from_1023q_1p5K.dat` from #1162: a real ILL D1B `XYDATA`
file with counts and σ written `NaN` on 60 channels (2θ 30.79-36.69°). On
`main` at `1612e5ae`, `rx.read_pattern(path, diagnostics=d)` returned 1280
points, 60 NaN intensities and 60 NaN σ. Its only diagnostic was
`PATTERN_DEAD_CHANNELS`, for two other channels at 128.6°. Neither the
readers (`src/rietx/io/`) nor `PatternData` tests a value for being finite
(the issue's read, not re-checked here). NaN is how a normalisation by a zero
monitor or efficiency comes out, so a real file can carry it.

**The rule this meets.** A reader may repair a file only where it can say
that it did, and only where the deviation is a report rather than a
contradiction (root CLAUDE.md; `src/rietx/io/CLAUDE.md` § What a reader may
repair). A NaN states "no value here", so dropping its row invents nothing.
`PATTERN_ROWS_DROPPED` already reports dropped rows in the xy reader
(`io/formats/xy.py`). `base.pattern_data()` is the boundary every reader
crosses (`io/CLAUDE.md` § Refusals), so one check there covers every format.

**Decided.** Settled 2026-11-01 by Claude under the io rulebook's
reader-repair rule: drop the non-finite rows with a warning naming the 2θ
range, through the existing `PATTERN_ROWS_DROPPED` path, and check ±inf and
every reader format. The alternative was to refuse the whole file. That
would block a real ILL D1B file over 60 dead channels. The new message
changes what a read prints, so it goes to the maintainer before merge (the
reader-output rule; `python -m tests.reader_output`).

**Practice.** GSAS-II 5.8.4 zeroes such a point's weight, silently
(`imports/G2pwd_xye.py:200-201`; read 2026-11-01, not run). FullProf and
TOPAS were not checked.

**Owner check.** No open WP owns a finite-value check across readers.
WP-1952 (the xy reader's skip report) asks in its task 1 whether a `nan` or
`inf` value is a dropped row, for xy alone. Its file is being edited by an
open PR (#1279), so this was filed apart rather than folded. A session on
either WP reads the other's state first: the two share `PATTERN_ROWS_DROPPED`
and `tests/test_readers_robust.py`.

## Non-goals

- The xy reader's other silent drops (a text row inside the data, a decimal
  comma, an inline comment): WP-1952.
- σ ≤ 0 and its floor (`schemas.pattern._floor_sigma`): WP-1952 § Inherited.
- Carrying reader diagnostics into the GUI: WP-1522.

## Tasks

- [x] Measure what a fit does today with the reporter's file: does it raise,
      return NaN, or return a number? Record it here. It sets how loud the
      new message must be. **It returns, silently.** On `main` at `62724a30f`,
      a default `fit()` of a hand-written Co₃O₄ model (Fd-3m origin 2,
      a = 8.084 Å, u = 0.2632, neutron λ = 2.52 Å, 2θ 10-128°) ended all six
      stages `diverged`, with Rwp and χ² NaN, every esd `None` and every value
      still at its start (a = 8.084). No exception and no warning were raised.
      The same fit of the real `1023q_1p5K.dat` converged at Rwp 0.0724,
      a = 8.0695(23) Å. So the message is a `warning`.
- [x] Drop every row with a non-finite 2θ, count or σ in `base.pattern_data()`,
      reported by `PATTERN_ROWS_DROPPED` with the count and the 2θ range of
      the dropped rows. A wholly non-finite file raises, naming the file.
      Landed one call earlier, in `base.ascending` (`base.finite_rows`); see
      the 2026-11-03 entry for why.
- [x] Tests in `tests/test_readers_robust.py`: NaN and ±inf in each column,
      through every entry of `io.readers.PATTERN_FORMATS` that can carry a
      float (a synthetic writer per format where one exists), and #1162's
      planted file. Every existing fixture reads with the same arrays and no
      new diagnostic. The planted file's assertion is in
      `tests/test_d1b_co3o4_quench.py`, beside the other planted files.
- [x] The reader-output approval for the new message text, before merge.
- [x] Skill: the diagnostics reference row for `PATTERN_ROWS_DROPPED`, if its
      meaning widens. Nothing else expected.

## Acceptance

The planted D1B file reads 1220 points with one `PATTERN_ROWS_DROPPED`
naming 30.79-36.69°. No reader returns a non-finite value.

```sh
.venv/bin/python -m pytest tests/test_readers_robust.py tests/test_readers.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #1187 (the report) and #1162 (the planted file).

## Handover log

- **2026-11-03 (2nd)** — Ruled by Yue 2026-11-03: the reader-output text
  in PR #1359's "What a reader receives" is approved as written. That
  covers the `PATTERN_ROWS_DROPPED` message, its suggestion, the refusal of
  a file with no finite point, and the help title change ("Some rows were
  not read as data"). Task 4 is ticked and the WP closes. Ghostshift
  runner session.

  *Done.* Merged `origin/main` at `cef9aef7c`, which brings PR #1279
  (WP-1952: the `XYDATA` `INTER` multipliers applied, and the caller's
  `axis=` on `xy`). Git merged it with no conflict, and none of the
  approved text changed. Both new paths already reach the drop, because
  `read_xy` applies the multipliers and the declared axis before it calls
  `ascending`. Two tests pin that: an `XYDATA` file under `INTER 1 2` with a
  NaN count drops the row and scales the rest, and a headerless bank read
  with `axis="tof"` names its dropped row as "flight time 2064 µs". No code
  changed.

  *Measured* (`[dev]` venv, darwin/arm64). test_readers_robust +
  test_readers + test_d1b_co3o4_quench + test_tof_axis, `-n auto`: 543
  passed, 1 skipped.

- **2026-11-03** — Every pattern reader now drops a point whose 2θ, count or
  σ is NaN or infinite, and says which points by their 2θ. Before, one such
  point reached the fit, and the fit came back with every statistic NaN and
  nothing moved, with no error and no warning. The reporter's D1B file now
  reads as 1 220 points and fits. A file with no finite point is refused. One
  approval is left, the maintainer's, for the new message text (task 4).
  Ghostshift runner session, PR #1359.

  *Done.* `base.finite_rows` runs first inside `base.ascending`.
  `base.pattern_data` has no diagnostics channel and runs after `ascending`,
  which refused a NaN 2θ first with a wrong message ("does not run in one
  direction"). Every reader calls `ascending` immediately before
  `pattern_data`, so the check moved one call earlier. `pattern_data` now
  refuses any non-finite value as a backstop. Siblings closed: a NaN count
  failed `base.integral` and withheld σ from a whole `.ras`, `.rasx` or
  `.udf` scan; GSAS's σ ≤ 0 filter dropped a NaN or −∞ esd silently; a NaN
  `.brml` absorber made `sigma_from_scaled` raise without naming the file;
  the Rigaku attenuator and brml absorber notes and four scan listers
  printed NaN. Kept as they were: pdCIF's σ = +∞, its zero-weight marker
  (`keep_infinite_sigma=True`), and Bruker RAW's refusal of a non-finite
  float32, which is its stride gate.

  *Measured* (`[dev]` venv, darwin/arm64). Task 1's numbers are above. After
  the change the planted file's fit converges at Rwp 0.0404 over 1 120
  points, a = 8.0698(17) Å, against 1 180 points before. `-n auto`, reader
  files only: test_readers_robust + test_readers + test_d1b_co3o4_quench
  345 passed, 1 skipped with the drop and none of the new tests; 424
  passed, 1 skipped at the end (+79 tests added, all passes). Fast
  selection at `e424a622f`, alone on the lock: 13 677 passed, 319 skipped,
  34 xfailed, 2 failed. One was `src/rietx/io/CLAUDE.md` over its line cap,
  fixed after by compressing the rule and raising the cap 565 → 571 with a
  ledger entry (`test_docs_consistency.py` then 25 passed). The other is
  `test_display.py`'s kernel test, which fails on this machine because its
  `python3` kernel spec points at a deleted venv; unrelated. The added tests
  cost 0.31 s together in that run (`tests.added_test_times`). `python -m tests.reader_output`: unchanged against `62724a30f`,
  because the LaB6 standard fit has no NaN.

  *Review.* `/code-review high --fix` found ten. Fixed: the brml absorber,
  the unit vote, the attenuator and absorber notes, the scan listers, a
  double conversion, a derivable argument, and the verb for one point.
  Declined: a finiteness check in the `PatternData` validator (old stored
  results must open; settled by Claude under the old-files rule in memory);
  an all-NaN esd column and one null pdCIF weight, which still fall back to
  Poisson σ, unreported (designed earlier; io/CLAUDE.md now says so). The
  review's `keep=` mask, which kept a finite count on a dropped row out of
  the Rigaku unit vote, was reverted on the generality judge's counter-case:
  84.3047 on such a row is the rate a real `.ras` stored under "counts".

  *Generality* (the `generality-review` judge's report, condensed; see its last line):

  > **`PATTERN_ROWS_DROPPED.suggestion` (suggestion row, value 1 → 2), and the new drop it rides on.** **Verdict: holds.** The case for acting is stronger. Excluding a point that carries no number from the fit is arithmetic, and GSAS-II's xye importer does the same. Three points are weak. The suggestion explains only the NaN case. The measured cost is quoted in four places but recorded in none of the WP's own handover entries. And the code row is still `unaudited` with nothing filled in.
  >
  > 1 What it decides: the action is a decision on every read; it removes the row, so the point count and file indexing change, and it raises when no row is left; the suggestion names one cause and one check and prescribes nothing that changes the answer (clear). 2 Kind: the drop is kind 1, there is no value to fit; the suggestion's cause is kind 3, it reports and stops, which is right for kind 3; the row states neither kind (none given). 3 Case against: no refiner fits a NaN; the open choice is representation only, drop the row or keep it at zero weight (GSAS-II, and rietx's pdCIF path), same χ². The cause sentence is half the arithmetic: 0/0 gives NaN, a zero monitor under non-zero counts gives ±inf, and the suggestion fires on ±inf and on a non-finite 2θ too (none found against the drop; suggestion text partly inaccurate). 4 Case for: a fit that fails silently with NaN statistics, severe; quoted in four places, but task 1 unchecked and no handover entry records the run (strong, measurement not yet recorded). 5 Tier: GSAS-II 5.8.4 `G2pwd_xye.py:170-201` read, not run: NaN count or σ → y = 0 at weight 0, silently; a +inf count with finite σ becomes 1.8e308 at weight 1/σ²; a NaN 2θ passes through. One importer only; FullProf, TOPAS, RIETAN-FP, BGMN, MAUD, EasyDiffraction not checked. Survey not in `docs/practice.md`. The drop fits tier 1; the suggestion has a precedent in `PATTERN_NET_HAS_BACKGROUND.suggestion` (tier 1, ambiguity 3) (not proposed by the author). 6 Families: one real file (ILL D1B), development data; synthetic per-reader files; no threshold, so the three-family ground does not apply; the zero-monitor cause is unverified on any file (none needed for the drop; cause unverified). 7 What says it fired: `PATTERN_ROWS_DROPPED` (warning), count in `value`, 2θ intervals in `where`, `["two_theta"]` when the 2θ is non-finite; the level is unaudited, still on `RESPONSE_BASELINE` (present). Evidence that would change the verdict: a refiner or program whose default fits, or refuses, a file over a NaN point.
  >
  > **(a) pdCIF passes `keep_infinite_sigma=True`.** **Verdict: holds.** The exempted σ = +∞ is the reader's own internal marker and never reaches the pattern. Kind 1 (the dictionary's weight 0, and 1/√0 = ∞). gemmi reads a literal `inf` as a null, so a file cannot put +∞ into an esd column. Without the exemption every zero-weight point would be dropped and misreported, losing `excluded_regions` and `PATTERN_ZERO_WEIGHT_EXCLUDED`. Tier 1. Fired: `PATTERN_ZERO_WEIGHT_EXCLUDED` and `excluded_regions`. Would change: a pdCIF route where +∞ comes from a file's own su column.
  >
  > **(b) Bruker RAW keeps refusing a non-finite value.** **Verdict: holds.** It keeps an existing refusal and adds no action. Documentation incomplete: bruker_raw.py:705-707 also refuses a v3 per-point 2θ, which is float64, with no cause named, while the stated reason ("float32") covers only the count case, and the manual line names only "a non-finite count". Kind 1. No real file is cited either way. Tier 1. Fired: a `ValueError` naming the file. Would change: a correctly read Bruker RAW file holding a NaN count or 2θ.
  >
  > **(c) `base.integral` ignores non-finite values; `sigma_by_arithmetic` takes `keep=`.** **Verdict: weak.** Ignoring NaN in the counts test holds (kind 1). The `keep=` mask, which stops a finite count on a dropped row from voting on the unit, faces a named counter-case: the test planted 84.3047 on the dropped row, the value io/CLAUDE.md cites as real evidence of a `.ras` storing a rate under a "counts" label, and asserted `PATTERN_INTENSITY_SCALED` stays silent. The change moves toward silence. No real file supports it; nothing says the row was left out of the unit test. Would change: a real Rigaku file with a non-finite 2θ on a row whose count is non-integral.
  >
  > **(d) GSAS's σ ≤ 0 channel filter keeps non-finite esds for the report.** **Verdict: holds.** A drop that used to be silent is now reported. Sibling gap: gsas.py:607 `sigma = … if np.any(sig > 0) else None` still turns an all-NaN esd column into Poisson σ with no report.
  >
  > **(e) `sigma_from_scaled` returns NaN σ for a non-finite scale.** **Verdict: weak.** The action is stronger than refusing the file, but the report names the wrong column: a `.brml` NaN absorber is reported as "a NaN σ", and the suggestion says "check the reduction" for instrument output (root CLAUDE.md, a message that names its discriminator makes the same claim). A −∞ factor also now passes. Would change: a message naming the absorber or scale column.
  >
  > **(f) `pattern_data` refuses any non-finite value.** **Verdict: holds.** A backstop raise for a reader bug; no default path reaches it; pdCIF's σ = ∞ is replaced before the call.
  >
  > (Condensed by the author from the judge's tables to their verdicts, crux and evidence lines, since the tables ran to 9 kB; no verdict was changed.)

  *Answers.* (c): `keep=` reverted, so a finite count votes whatever its 2θ
  (test `test_a_finite_count_on_a_dropped_row_still_votes_on_the_unit`).
  Suggestion text: widened to "NaN or infinity". Row 4 and the practice
  survey: recorded above and in `docs/practice.md`. (b): the manual's line
  now says "a non-finite count or 2θ". (d): left, recorded in io/CLAUDE.md as
  unreported. (e): left. The row is still dropped and placed by 2θ, and
  naming the source column would need a per-reader argument for one
  synthetic case.

  *Gotchas.* gemmi reads `inf` in a CIF as a null, so a pdCIF can only carry
  NaN. Bruker RAW cannot reach the drop at all.

  *Settled by Claude.* The check's location (`ascending`, not
  `pattern_data`), under the io rulebook's "one place it lives" rule for
  `ascending`. Practice: GSAS-II re-read and recorded in `docs/practice.md`
  § A NaN or infinite value in a pattern file.

  *Next:* the maintainer approves or rewords the message (task 4, PR #1359's
  "What a reader receives"). Then close the WP.

- **2026-11-02** — created by a ghostshift runner from the 2026-11-01
  decision briefs (§C item 1), to give #1187 an owner. No WP cited it. The
  closest owner, WP-1952, covers the xy reader alone and is being edited by
  PR #1279. Filed in PR #1317. Nothing was run; every number above is the
  issue's. *Next:* task 1.
