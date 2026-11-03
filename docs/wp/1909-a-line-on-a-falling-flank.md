# WP-1909 — a line on a falling flank, at a third of its own esd

Milestone: unscheduled · Status: 🔄 2026-11-03 — claimed by @mustachefeeling
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-05 — a defect that fires wrongly: three unflagged false lines cost the indexer the true cell, and cropping the range is the workaround; indexing is a path few fits run

## Goal

`pick_peaks` does not offer the engines a line its own group fit measures at
a fraction of its esd, and on a background that falls threefold within a few
degrees the issue's synthetic silicon indexes to cubic F 5.431 Å again.

## Context

**Source.** Issue #718 (2026-10-05), with a synthetic generator: silicon,
Cu Kα1/Kα2, 10-110° at 0.0167°, Poisson noise (seed 1), and two backgrounds.
The control is a gentle exponential; the defect is a sigmoid falling from
~2300 to ~800 counts over 11-22°:
`780 + 1500/(1 + exp((2θ − 16.8)/2.6)) + 300·exp(−(2θ − 10)/80)`. Silicon has
no reflection below 28.4°, so every line there is false. The generator is in
the issue body; copy it into the test fixture, not into `src/`.

**Measured on `32ef5a6`** (`[dev]` venv, Linux, the issue's code verbatim):

| run | usable | below 28° | top of `index_pattern(preset="quick")` |
|---|---|---|---|
| gentle control | 10 | 0 | trigonal R 3.841/9.38 `low`; cubic F 5.431 5th, 8/10 |
| steep | 11 | 3 | tetragonal P 3.841/5.410 `low`, the only candidate |
| steep, those 3 flagged unusable | 8 | 0 | cubic F 5.431 first, 8/8 |
| steep, cropped to 25-110° | 8 | 0 | cubic F 5.431 first, 8/8 |

Each search finished in 5-40 s, against the preset's 120 s ceiling, on a
machine other triage scripts were also using, so the ceiling did not bind.
The three false lines sit at 15.92, 16.48 and 16.88° with I/σ_I 0.33, 0.36
and 0.38. Their flags are `position_at_bound`, none and none, so all three
are usable. A fourth component at 15.83° carries `duplicate_line`.

**The mechanism.** Detection thresholds `z = max(net, 0)/σ` at
`PEAK_MIN_HEIGHT_SIGMA` = 5 with `net = y − _debiased_envelope(tt, y)`
(`src/rietx/indexing/peaks.py:444-459`, `_candidates`). That envelope is
`background_envelope` (`src/rietx/background/diagnostics.py:685`, a 3° rolling
10th percentile, knots at window centres, edges extrapolated since WP-1028
§(i)) plus **one global** offset, `median(y − env)`. A low quantile over 3° of
a steep fall lands on the window's low end, so the envelope sits under the
background at the window centre. Measured against the generator's true
background: 2.8-3.0σ under it at the three false lines, 0.6σ on the gentle
control. A 5σ bar therefore acts as about 2σ on the flank.

**Why nothing flags them.** `_prune_shoulders` (`indexing/peakfit.py:510`)
ΔBIC-tests only *shoulder* seeds, by a deliberate asymmetry its docstring
gives; a *maximum* that clears detection is never reconsidered.
`no_intensity` (`indexing/pick.py:334`) fires only at the zero intensity bound
(`BOUND_HIT_RTOL`), and these components are above it with I/σ_I ≈ 0.35. The
sibling rule is in `src/rietx/indexing/CLAUDE.md` ("a component that refines
onto its zero intensity bound is not a line"): this is the same claim at a
significance rather than at a bound.

**What the envelope also feeds.** `_candidates` is shared with
`width_census`, which the refinement path reads (`refine.py:8464`,
`refinement_width_diagnostics`), and the envelope is the group fitter's
additively held background (`peakfit.py:148-159`). `background_envelope`
itself also feeds `background.diagnostics` (`:857`, `:1176`, `:1432`). A change
to `_debiased_envelope` moves picking and the refinement's width census; a
change to `background_envelope` moves the pattern diagnostics as well.

**Two repairs, neither chosen.** (a) An I/σ_I test on each component, its
bar measured, as a flag in `PEAK_UNUSABLE_FLAGS` (flagged, never dropped:
`pick.peaks_of_group`'s docstring says why). It catches any mechanism that
leaves a maximum its fit cannot see. The risk is a real weak line, which
low-symmetry indexing needs. (b) An envelope that follows a steep flank: a
slope correction, a window narrowed where the envelope's own slope is large,
or SNIP (`rietx.background`, Ryan et al. 1988). It removes the cause here and
nothing else. The maintainer chooses after both are measured.

**Seen in passing, not this WP.** The gentle control is not clean either: the
111 line carries two more usable components at 28.60° and 28.77° (its Kα2 is
at ≈28.52°), and cubic F ranks fifth there behind tetragonal I and trigonal R
descriptions of the same lattice. In the cleaned runs a cubic I 7.681 Å cell
is graded `medium` at rank 3 while the true cubic F is `low`
(`predicted_but_absent`, the diamond glide).

**Rules that bind the work.** `INDEXING_THRESHOLDS_VERSION` (now "1.7",
`schemas/indexing.py:102`) bumps if `pick_peaks`' answer can move. A new
`PeakFlag` has the mirrors WP-1510 listed for `duplicate_line`: `help.py`,
`help_keys.json`, `gui/src/lib/rxt.ts` with a rebuilt dist, the manual's flag
table, and the regenerated skill `api.md`. `tests/test_acceptance_indexing.py`
runs before close, since the peak list feeds every engine.

### Inherited

- **2026-10-14, from the issue triage: issue #934 is filed as WP-1968, and
  its PR #947 moves this WP's census baseline.** #947 tests each component's
  I/σ_I against a per-pattern Benjamini–Hochberg bar and flags a component
  under it `weak_line`, reported and left in `usable()`. That is the 1σ
  floor's per-pattern successor on the same statistic. #948 (WP-1968 too)
  merges unresolved splits and flags `width_capped`, both unusable, and moves
  the 16 round-robin lists from 789 to 782 usable components. The census here
  should say which of the two had merged on the tree it ran on.

- **2026-10-11, from the issue triage: issue #878 is in PR #880 (theirs),
  and it moves this WP's census baseline.** A sibling false line by another
  mechanism. `_drop_kalpha2_aliases` compares two channel maxima against
  0.3 FWHM, and where a FWHM spans under ~3.3 channels the sampling error
  exceeds the tolerance, so a resolved Kα2 maximum survives as a line. PR
  #880 (fork, head `fix/878-alias-step`) adds one sampling step in both
  alias checks and moves two pins: IUCr CPD corundum 2 → 1 `no_intensity`
  phantoms, and cpd-4 77 → 76 usable lines (146.13°, the Kα2 of corundum's
  145.21°). SRM 660c is unchanged per the PR. The census task here takes
  its "before" from whichever tree it runs on, so say whether #880 had
  merged. Read against `f11e22d3`: the PR does not bump
  `INDEXING_THRESHOLDS_VERSION`, though 1.7 was bumped for a `usable()`
  change of the same size (cpd-4 78 → 77). That is `/pr-review`'s to raise.

- **2026-10-07, from WP-1545: a reproducible synthetic fixture.**
  `examples/tutorials/03_peaks_indexing_lebail.py` synthesises aragonite
  (Cu Kα, 10-80°, seed 0) and calls `pick_peaks` with a default instrument.
  Of 59 usable lines, 5 sit more than 0.03° from every reflection of the
  refined true cell, all weak (areas 9-39 against a strongest line of about
  2200): 26.619° (0.33° from the nearest), 53.371° (0.18°), 79.334°, 56.202° and
  46.013°. The index of that list ranks the truth first with
  `indexed_fraction_low` (50/59). If this WP's census needs a pattern whose
  truth is known exactly, this one is.

## Non-goals

- `PEAK_MIN_HEIGHT_SIGMA` itself, and the ghost screen's threshold (WP-1447).
- Duplicate copies of one line (`duplicate_line`, WP-1510, landed).
- The gentle control's 111 components and the cubic I grade, above.

## Tasks

- [ ] The fixture: the issue's generator under `tests/`, and a test that
      counts usable lines below 28° on the steep pattern (3 today, red).
- [ ] Measure repairs (a) and (b) on the fixture and on the 16 IUCr
      round-robin lab lists, SRM 660c and 11-BM NAC: usable counts per
      pattern and which components each removes. Record the table here and
      take the choice to the maintainer.
- [ ] Land the chosen repair, with the threshold's measured basis in its
      docstring, `INDEXING_THRESHOLDS_VERSION` bumped, and the mirrors above.
- [ ] If the envelope changed: the refinement width census on the same
      patterns, before and after.
- [x] Tests, with obs/calc/diff PNGs to `tests/output/`. *2026-11-03:* the
      tests are #741's `tests/test_peak_picking_flank.py`; the PNGs go through
      `tests/indexing_gallery.py` (`silicon_steep_peaks`, `silicon_steep`:
      peak list, candidates, Le Bail obs/calc/diff), and the index row now
      asserts cubic F first rather than present.
- [ ] Skill: none beyond the new flag's `help.py` entry, which is where an
      agent reads a flag (WP-1338's cheapest place); a `references/` row only
      if the flag needs a judgement the entry cannot carry.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_peak_picking.py tests/test_indexing*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

On the steep fixture no usable line sits below 28°, and
`index_pattern(preset="quick")` ranks cubic F a = 5.431 Å first. The
round-robin table shows which real lines, if any, the repair removed.

## References

- Ryan, C. G. et al. (1988). *Nucl. Instrum. Meth.* B34, 396 — SNIP, as
  `rietx.background.estimators` cites it.
- Issue #718; WP-1028 §(i) (the edge extrapolation, the same family);
  WP-1110 item 14 (`no_intensity`); WP-1510 (`duplicate_line`).

## Handover log

- **2026-10-12** — PR #880 merged from outside as `f47c728e` and closed #878.
  This WP's census baseline has moved under it. `pick_peaks` now drops a
  resolved Kα2 maximum it used to keep as a line wherever a FWHM spans fewer
  than about 3.3 channels. The Kα2 alias screen compares two channel maxima,
  so it now allows one sampling step beyond its 0.3 FWHM
  (`indexing.peaks._alias_tolerance`).
  - *Measured, by the PR.* cpd-4 offers 76 usable lines where it offered 77.
    The corundum list loses one `no_intensity` component (2 → 1). A Cu Kα rock
    salt at a 0.02° step goes from 7 of 9 lines indexed to all 9.
    `INDEXING_THRESHOLDS_VERSION` is 1.9, since #907 (WP-1923) took 1.8 the
    same day.
  - *Gated* on the same four-PR stack as WP-1322's entry of today (stack
    `0e4b7e25` on main `f22e9a7c`; main `f47c728e` content-identical after the
    merges). The slow suite included `tests/test_acceptance_indexing.py`, with
    #907's indexing changes in place.
  - *Gotchas.* The census task's baseline is now main `f47c728e` or later.
    Any count taken before it includes the aliases #880 removes.
  - *Not done.* The 1σ floor's threshold clause landed ("Also in 1.7" in
    `schemas/indexing.py`). Its line in `indexing/CLAUDE.md`, which the
    2026-10-07 entry named, has not: that file never mentions
    `PEAK_NO_INTENSITY_SIGMA`.
  - *Next:* the dossier line, then the census and the PNGs.

- **2026-10-07** — PR #741 merged from outside as `ccd2e298` and closed #718.
  Gated together on a nine-PR stack replayed onto `main` at `f99fab05` (stack
  `16a95cef`, macOS arm64, `[dev,jax]`). The whole suite gave 8912 passed, 113
  skipped and 2 failed. Both failures fail identically on bare `main`: the
  `toy_anomalous` golden (#760) and
  `test_the_reduction_map_takes_a_to_f_where_the_reduction_does`. After the
  last merge, `main` at `a65dca1a` is content-identical to the gated tree.
  That run includes `tests/test_acceptance_indexing.py`.
  - `pick_peaks` flags a component whose intensity is under 1σ of its own esd
    `no_intensity` (`PEAK_NO_INTENSITY_SIGMA`). The `PeakFlag` comment names
    the floor.
  - On 11-BM NAC the floor removes nine of 276 usable lines. The 20-of-100
    low-Q search pool then reaches deeper, and a third candidate survives:
    cubic P at 10.2512/√2 Å. It indexes 177 of 267 lines (I: 219), ranks last
    and stays `low`.
    `test_short_wavelength_data_is_indexed_by_the_engines_that_enumerate_nothing`
    now admits that one candidate and no other.
  - Not done. `INDEXING_THRESHOLDS_VERSION` stays `"1.7"`, which is
    unreleased; its history entry owes a clause for the 1σ floor, and
    `indexing/CLAUDE.md` owes its dossier line. Task 2's table of repairs (a)
    and (b) across the IUCr lists is not recorded here, and neither are the
    width census or the PNGs. The tasks stay unticked until each is checked
    against its wording.
  - Next: the threshold history clause and the dossier line.

- **2026-10-05** — created, from the 2026-10-05 issue triage (issue #718).
  Checked against the tree at 32ef5a6: the issue's generator reproduces the
  three false lines (I/σ_I 0.33-0.38) and the lost cubic cell; flagging the
  three or cropping to 25-110° restores cubic F 5.431 Å to first. No open WP
  owns it: WP-1447 is the ghost screen's `GHOST_MIN_PARENTS`, not detection;
  WP-1510 (🔄, PR #690 merged, every task landed) took duplicate copies of
  real lines; WP-1511 compares supplied cells by Le Bail; WP-1542 is the Le
  Bail background protocol. WP-1018 and WP-1028, which built picking and the
  edge repair, are ✅. *Next:* task 1.
