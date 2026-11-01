# WP-1968 — the picker offers no line the data cannot support

Milestone: unscheduled · Status: ✅ 2026-11-01 — every task landed; measured silicon (11-BM SRM 640c) flags no weak line, so the flat-silicon control stays synthetic as a documented limit
Track: What fires, and what stays silent
Depends on: 1909 soft (the 1σ floor this bar succeeds, and its census)

## Goal

`pick_peaks` tests each weak component against a bar the pattern sets for
itself, and says how many false lines to expect among those it keeps. Two
components closer than the data can resolve are reported as one line.

## Context

**Source.** Issue #934 (2026-10-13), corrected by its reporter the same day.
It names two behaviours. The group fit keeps extra components, and the 5σ
detection bar carries no expected count of false lines, so a user cannot tell
three junk lines from three weak real ones. The proposal has three parts:

- (a) A second component in a group only past ΔBIC ≥ 6 *and* a resolvability
  bound at the fitted SNR. Otherwise one line, with σ widened to cover the
  split.
- (b) A Benjamini–Hochberg bar per pattern (q = 0.01), reported as
  `PEAK_EXPECTED_FALSE_LINES`, with a null-pattern test.
- (c) The filters every benchmark harness writes by hand (an intensity floor,
  a width cap, the bound hit) as flags with a diagnostic each, kept in the
  list and left out of the search's driven set.

The correction places the two parts. On #916's flat synthetic Si the extra
components are re-seeds in groups of their own, on tail maxima 1.8–2.6 FWHM
from a line, at I/σ_I 1.6–2.6. That is (b)'s target. The 0.012°-apart splits
belong to #728's flat-topped arm (each line three copies 0.012° apart), and
that is (a)'s.

**Checked against the tree at `ee589bab`.** `pick_peaks` is
`indexing/pick.py:49`, `fit_group` is `indexing/peakfit.py:442`, and the 5σ
detection bar is `PEAK_MIN_HEIGHT_SIGMA` at `indexing/peaks.py:478`. The
issue's reproducer (#916's flat Si, seed 1, 12.1–60°, `pick_peaks` with
`Instrument.debye_scherrer(0.825739)`) picks 23 components here, 17 usable
(the issue says 18). One silicon line carries two usable components within
one fitted FWHM (0.023°). Four usable components sit more than 1.5 FWHM from
every silicon line. The window was the median fitted FWHM, so the per-line
counts differ from the issue's in detail. The defect reproduces in kind.

**Decided 2026-10-14** (the maintainer, answering the PR-review batch): yes to
(a) and (b), as PRs #948 and #947 build them. The maintainer also gave a free
hand on the picker beyond them ("go buck wild on the peak picker"), so (c) and
the driven-set exclusion are welcome as follow-ups. The PRs' questions,
answered:

1. (#947) `weak_line` is reported and stays in `usable()` for now. Leaving it
   out of the search's driven set (`engines.search_line_order`) follows
   WP-1969.
2. (#947) The look-elsewhere count is one trial per FWHM of scan
   (∫ d2θ / FWHM), not one per channel. Channels inside one line are not
   independent tests.
3. (#948) The resolvability rule reuses `PEAK_SATELLITE_MAX_RATIO` (0.25) for
   its comparable-area gate.
4. (#948) `width_capped` makes a component unusable.

**WP-1909 is the neighbour.** It landed a fixed floor on the same statistic
(`PEAK_NO_INTENSITY_SIGMA`, the `no_intensity` flag) and still owes a census
of usable counts on the round-robin lists. #947's bar is that floor's
per-pattern successor, so the census baseline moves when #947 merges. WP-1909
fences the detection bar out, and #947 leaves it at 5σ and tests the fitted
I/σ_I instead.

**Rules that bind the work.** `INDEXING_THRESHOLDS_VERSION` bumps when
`pick_peaks`' answer can move. A new `PeakFlag` has the mirrors WP-1510
listed for `duplicate_line`: `help.py`, `tests/data/gui/help_keys.json`,
`gui/src/lib/rxt.ts` with a rebuilt dist, the manual's flag table, and the
regenerated skill `api.md`. `tests/test_acceptance_indexing.py` runs before
close, since the peak list feeds every engine.

## Non-goals

- The steep-flank envelope, and the 1σ floor's census (WP-1909).
- The ghost screen's threshold (WP-1447).
- The search's acceptance rule (WP-1969).

## Tasks

- [x] **Decision (maintainer):** the issue's (a)-(c), whole or in part,
      recorded as `Decided YYYY-MM-DD:` here and answered on #934.
      *Decided 2026-10-14: (a) and (b) as PRs #948 and #947 build them, and
      a free hand beyond (Context).*
- [x] Review and merge PR #947 (part b).
- [x] Review and merge PR #948 (part a).
- [x] Follow-up, after WP-1969: keep `weak_line` and the other reported
      flags in the list, and leave them out of the search's driven set, as
      the issue's (c) asks. *PR #1048, `weak_line` only; why
      `position_at_bound` stays driven is in the 2026-10-21 entry.*
- [x] Tests, with obs/calc/diff PNGs to `tests/output/`, and
      `tests/test_acceptance_indexing.py` green. *PR #1179.*
- [x] Skill: the new flags' and code's `help.py` entries (both PRs add
      them), which is where an agent reads a flag; a `references/` row only
      where a flag needs a judgement the entry cannot carry.

## Acceptance

On #916's flat Si every usable component sits within one FWHM of a silicon
line. On #728's flat-topped arm each line keeps one usable component. On the
round-robin lists, usable counts move only by the components the PRs' tables
name.

```sh
.venv/bin/python -m pytest tests/test_peak_picking.py tests/test_peak_picking_flank.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #934 (body, and its same-day correction); PRs #947 and #948.
- Benjamini, Y. & Hochberg, Y. (1995). *J. R. Stat. Soc. B* 57, 289: the
  false-discovery rate.
- Miller, C. J. et al. (2001). *AJ* 122, 3492, and Hopkins, A. M. et al.
  (2002). *AJ* 123, 1086: the false-discovery rate in source detection.
- den Dekker, A. J. & van den Bos, A. (1997). *JOSA A* 14, 547: resolution,
  a survey (Sparrow's criterion).

## Handover log

- **2026-11-01** (ghostshift runner, PR #1303, closed) — The question WP-2002 left here is answered, and the answer is a limit rather than a second test. The only measured silicon in the tree, APS 11-BM's SRM 640c scan, gives the picker nothing to flag: no component falls under the false-discovery bar, every usable component sits on a silicon line, and the list indexes to the true cell with or without the driven-set exclusion. So the evidence that the exclusion is needed on flat silicon stays synthetic, and the test now says so with the numbers. The measured scan cannot settle the question either way, because its peaks stand about 15 times higher above the background than the synthetic draw's. The maintainer's go of 2026-11-01 (ghostshift record) chose this branch for that outcome.
  *Measured* (macOS arm64, `[dev]`, Python 3.12, compiled tier on; scripts and JSON in the runner's scratch, not committed). Cubic search, `n_unindexed=2`, `preset="full"`, as the test runs it.

  | pattern | components | usable | `weak_line` | usable > 1.5 FWHM off a line | driven, flagged / stripped | truth rank, flagged / stripped |
  |---|---|---|---|---|---|---|
  | #916 synthetic, 2 % windows | 23 | 18 | 7 | 3 | 11 / 18 | 1 / no cell |
  | #916 synthetic, closing windows | 20 | 15 | 4 | 1 | 11 / 15 | 1 / 1 |
  | `11BM_Si640c.xy`, #916's d-range (6.03-28.92° at 0.412359 Å) | 19 | 11 | 0 | 0 | 11 / 11 | 1 / 1 |
  | `11BM_Si640c.xy`, whole scan (2-50°, 30 lines) | 45 | 30 | 0 | 0 | 20 / 20 | 1 / 1 |

  The synthetic rows reproduce WP-2002's finding (7 against 4 weak components, the stripped control indexing only at the closing windows). The synthetic weak re-seeds sit 2.1-2.6 FWHM from a line at I/σ_I 1.3-2.3. On the measured d-range the 8 unusable components are axial-tail shoulders 0.9-1.2 FWHM from a line (`not_separable`) and two `unresolved_split` halves. The usable ones sit at I/σ_I 22 or more. Peak-to-background is about 2600 measured (251 500 counts on ~95) against about 170 synthetic (1.3e6 on 7700). The pick PNGs (`tests/output/peaks_wp1968_si640c*.png`, whole range and zooms at 7.5° and 21.4°) were read by eye: every true line carries one unflagged usable tick, and the flagged ticks sit on the lines' tails.
  *Done*: `tests/test_indexing_driven_set.py` records the limit in the flat-silicon test's comment and in the module docstring. No assertion and no source file changed, so the picker's output does not move. Inherited pruned: its one open entry (WP-2002's question) is answered above; the #993 and #947/#948 entries were already consumed by their merges. Priority was P2, so no release is owed.
  *Gates*: see the PR body for the fast-suite counts and `python -m tests.reader_output`.
  *Next*: none in this WP. A measured silicon pattern at a lab diffractometer's counting level (peak-to-background near 170) would decide whether the exclusion is needed on measured data; the tree has none, and the local-only data root holds no silicon either. #934 is the maintainer's to close.

- **2026-10-31** (ghostshift close-batch, PR #1287, not closed) — all six tasks are ticked and landed (#947, #948, #993, #1048, #1179 and the help entries). One inherited question is still open, and it says it is this WP's to decide. The WP-2002 session found that the flat-silicon control in `test_916s_flat_silicon_is_driven_by_its_own_lines` only shows the driven-set exclusion is needed when the silicon pattern is drawn at the 2 % windows. Drawn at the closing stage's windows (full peak tails), the picker flags 3 fewer `weak_line` components, and the stripped control then indexes. So the evidence that the `weak_line` exclusion is needed on #916's flat silicon rests on the truncated tails of a synthetic draw. The test already says so in a comment and draws at `WINDOW_AREA_TOL`.
  *Checked against main `1314c69ea`*: the test still draws at `WINDOW_AREA_TOL` (`tests/test_indexing_driven_set.py`, line 145) and no entry in this log answers the question. Not measured here: whether a real flat-silicon pattern (the #916 data) flags extra weak components, which is what would show the exclusion is needed on a measured pattern.
  *Next*: decide, with that measurement, whether the exclusion's control is kept on the synthetic draw as a documented limit, or rebuilt on measured silicon. Then close: ✅, delete `Priority:` and `### Inherited`, narrative to the v1.11 record. #934 is the maintainer's to close.

- **2026-10-26** — PR #1179 (the PNG task, by @mustachefeeling) merged as
  `6ecf7fa3`. `tests/peak_pictures.draw_pick` draws what `pick_peaks` fitted:
  each group's fitted profile over the frozen envelope, through
  `peakfit.group_profile`, never a refit. Under it go (obs − calc)/σ and one
  tick row per flag (`weak_line`, `unresolved_split`, `width_capped`,
  `position_at_bound`). Five arms of `test_peak_fdr.py`,
  `test_peak_resolvability.py` and `test_peak_bounds.py` switch to
  `pick_peaks_with_state` and leave `tests/output/peaks_*.png`. No assertion
  moves. Read by eye at review: on #728's steep arm the flank components sit
  in the capped, split and at-bound rows, and every silicon line keeps one
  unflagged component. Two nits went to the review as follow-ups: `zoom` has
  no caller, and a usable peak with a flag outside the four rows is counted
  as both "unflagged" and "other". Gated in a stack with #1178 on `main`
  `c0e32ab2` (tree `1b644447`, which `main` equals after both merges). The
  fast suite gave 11 937 passed, 199 skipped, 32 xfailed, and the whole
  `-m slow` suite gave 417 passed, 14 skipped, 15 xfailed,
  `test_acceptance_indexing.py` among them (macOS arm64, `[dev,jax]`,
  Python 3.12.10, alone). *Next:* the close (the milestone record's line
  and ✅); #934 is the maintainer's to close.

- **2026-10-25** — PR #993 (#934 (c), by @mustachefeeling) merged at round 6,
  landing in `fe4cbcc3` through #939's head. `pick_peaks` names every bound
  its group fit ends on: `PEAK_POSITION_AT_BOUND` and `PEAK_NO_INTENSITY`
  are new (info, tier 1), and the `where` entries of those two,
  `PEAK_WIDTH_CAPPED` and `PEAK_EXPECTED_FALSE_LINES` carry each line's bound
  and value. No flag, threshold or `usable()` moves. Both codes have help
  entries and their `response` rows. The review's sync commit `72d9884c` put
  the picker's thresholds note under C3's 1.12 (#941) and moved the release
  bullet to `docs/releases/1.11.0.md`. Gate: as WP-1956's 2026-10-25 entry.
  *Next:* the PNG task.

- **2026-10-21** — PR #1048 (outside contributor, #934 part (c)) merged as
  `7c177d01`. A line flagged `weak_line` stays in `usable()` and is still
  scored, but `engines.search_line_order` no longer draws it into the lines
  a search is driven by, which are the lines an accepted cell must index.
  The set of such flags is `schemas.indexing.PEAK_UNDRIVEN_FLAGS`. Below
  `engines.DRIVEN_MIN_LINES` (6, the triclinic metric's parameter count)
  unflagged lines, the strongest flagged ones are driven again. On #916's
  flat synthetic silicon the driven set falls from 17-18 lines to the 11
  silicon lines. A cubic search with a declared `n_unindexed=2` goes from no
  cell to the truth first, and an all-systems search moves the truth from
  sixth (or absent) to fourth or fifth. No indexing-acceptance list drives a
  `weak_line` line, so none moved. It rides the 1.11
  `INDEXING_THRESHOLDS_VERSION` already staged. `position_at_bound` stays
  driven: on the real acceptance lists 2-10 usable components carry it alone,
  at I/σ_I up to 29, so leaving them out would be a guess.
  **Known limit, ruled 2026-10-21 (no opt-out for now).** A superstructure
  whose extra lines are all flagged `weak_line` now indexes as its subcell,
  with those lines listed in the candidate's `unindexed_two_theta`. No trial
  cell is generated from them. The ruling rests on practice: indexers are fed
  the most reliable lines, and a superstructure is indexed by its subcell
  first. A real list that loses its supercell this way reopens it.
  Follow-up from the review: `search_line_order` casts its index array to
  `int64` where the wasm32 rule asks for `intp`; harmless today.
  Gated on `main` `5a99ba92` with the PR merged (`a513c4f0`, content-identical
  to `main` after the merge): fast suite 11051 passed, 120 skipped,
  3 xfailed. A superset tree with #1086's test files gave 324 passed,
  12 skipped, 1 xfailed on the whole `-m slow` suite, `test_acceptance_indexing.py`
  included (macOS arm64, `[dev,jax]`, Python 3.12.10). *Next:* the PNG and
  skill tasks, then close; #934 is the maintainer's to close.
- **2026-10-15** — PR #948 (part a) merged as `54526f82`. Both parts of #934
  are now in. `pick_peaks` merges two comparable components closer than
  Sparrow's limit (`unresolved_split`), and flags a group whose width runs into
  its bound (`width_capped`). Both flags leave `usable()`, and a merged line's
  σ(2θ) is widened to reach its splits. `ObservedPeak.two_theta_esd_fit` keeps
  the fit's own σ for the duplicate ranking. The judgements run once, on
  detection's accepted fit, so `fit_peaks` and the peak editor fit named
  positions exactly. The merge is transitive by measurement: no chain of three
  on the 16 round-robin patterns, while an outer-pair bound breaks #728's
  flat-top arm. Combined with #947, #728's steep-background arm has 17 usable
  components, 4 under the false-discovery bar, where #947 alone flagged 24 of
  37. The field adds no `SCHEMA_VERSION` bump, the same open question as #940's
  round 1. Gated in a stack with the other on `main` `e517bb64` (tree `a66be65c`). The fast suite gave 10688 passed, 120 skipped, 2 xfailed, and the whole `-m slow` suite gave 319 passed, 12 skipped (macOS arm64, `[dev,jax]`, Python 3.12.10). *Next:* the follow-up after WP-1969 (keep reported flags out
  of the driven set), then close; #934 is the maintainer's to close.
- **2026-10-15** — PR #947 (part b) merged as `1eb58a5f`. `pick_peaks` now
  tests each component's I/σ_I by Benjamini–Hochberg over the pattern's
  resolution elements. A component under the bar is flagged `weak_line` and
  stays usable, and `PEAK_EXPECTED_FALSE_LINES` gives the bar and the
  expected noise count, worded as a lower bound. Round 2 fixed both round-1
  items. The peak editor re-marks every component on each edit, so flags and
  diagnostic agree. The trial count skips excluded bands, through
  `TRIAL_GAP_STEPS`. #947 took `INDEXING_THRESHOLDS_VERSION` 1.10 and the
  committed dist, so #948 (part a) rebases, renumbers and rebuilds. Its
  round 2 is otherwise clean. Gated in the stack on tree `2268e525` (counts
  in WP-1343's entry of today), `test_acceptance_indexing.py` green among
  them. *Next:* #948 after its rebase.
- **2026-10-14** — created, from the 2026-10-14 issue triage (issue #934).
  Checked against the tree at `ee589bab`: every symbol the issue names exists
  where cited, and its reproducer gives 17 usable lines with five extra
  components (Context). No open WP owns it. WP-1909 holds one false-line
  mechanism (a steep flank) and fences the detection bar out. WP-1447's
  threshold is the ghost screen's. The maintainer decided it the same day
  (Context). *Next:* the reviews of PRs #947 and #948.
