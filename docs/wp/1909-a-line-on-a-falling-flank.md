# WP-1909 — a line on a falling flank, at a third of its own esd

Milestone: unscheduled · Status: ✅ 2026-11-03 — PR #1380; the 1σ floor (#741) is the repair, the census rules out the envelope, leftovers in issue #1382
Track: What fires, and what stays silent
Depends on: —

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

### The census (task 2), 2026-11-03

On `origin/main` `5d7622d6` (`[dev]` venv, macOS arm64), so #880's alias
step, #947's `weak_line` and #948's `width_capped` and merged splits had all
merged. Every arm is a full `pick_peaks` on the default range (the silicon on
10-110°); the probe patches `pick.PEAK_NO_INTENSITY_SIGMA` and
`peaks._debiased_envelope`. *Base* is the floor off (only the zero-bound test);
**(a)** the shipped 1σ floor, so `main` itself; **(b)** the floor off and a
SNIP envelope (`background.estimators.snip`, half-window half of
`ENVELOPE_WINDOW_DEG`) under the same median debias; **(ab)** both. Counts are
`usable()`. A component "moves" when no component of the other arm sits within
0.01°.

| pattern | base | (a) | (b) | (ab) | what (a) removes (2θ, I/σ_I) |
|---|---|---|---|---|---|
| 16 IUCr round-robin lab lists | 785 | 782 | 806 | 803 | cpd-2 101.10° (0.89), magnetite 62.07° (0.90), zircon 118.34° (0.16) |
| SRM 660c | 30 | 30 | 32 | 32 | none |
| 11-BM NAC | 263 | 262 | 248 | 248 | 10.92° (0.15) |
| silicon, steep | 8 | 8 | 8 | 8 | none: the four flank components are `width_capped` too |
| silicon, gentle | 10 | 10 | 10 | 10 | none |

Per round-robin list, base / (a) / (b): brucite 28/28/30, corundum 46/46/47,
cpd-1a 30/30/30, 1b 65/65/66, 1c 39/39/44, 1d 55/55/56, 1e 67/67/67,
1f 58/58/61, 1g 61/61/63, 1h 69/69/67, cpd-2 74/73/77, cpd-4 75/75/76,
fluorite 17/17/17, magnetite 18/17/17, zincite 27/27/32, zircon 56/55/56.

- **(a) removes only what it was built to remove**: four components over the 20
  patterns, each under I/σ_I 0.9.
- **(b) is not a local repair.** It moves components on all 16 lists, from
  one line shifted 0.011° (cpd-1a) to 12 out and 12 in (zircon). It adds 5
  lines at I/σ_I 2.9-10.5 to zincite and 7 to cpd-1c, and on NAC it takes 18
  off (I/σ_I 0.15-9.2) for 5 new ones. It would also move the refinement's
  width census, the q-screen and the extinction test, which share
  `_debiased_envelope`. On
  the steep fixture it removes nothing that (a) and `width_capped` have not
  already removed.
- **The merge made the choice.** #741 shipped (a), and the maintainer merged
  it on 2026-10-07; this table is the evidence the task owed that choice. The
  recommendation is to keep (a) and not build (b): (b) buys nothing on the
  fixture and moves dozens of real components. So task 4 (the width census,
  if the envelope changed) is moot.

## Non-goals

- `PEAK_MIN_HEIGHT_SIGMA` itself, and the ghost screen's threshold (WP-1447).
- Duplicate copies of one line (`duplicate_line`, WP-1510, landed).
- The gentle control's 111 components and the cubic I grade, above.

## Tasks

- [x] The fixture: the issue's generator under `tests/`, and a test that
      counts usable lines below 28° on the steep pattern (3 today, red).
      *Landed in #741:* `tests/_synthetic_silicon.py`,
      `tests/test_peak_picking_flank.py`.
- [x] Measure repairs (a) and (b) on the fixture and on the 16 IUCr
      round-robin lab lists, SRM 660c and 11-BM NAC: usable counts per
      pattern and which components each removes. Record the table here and
      take the choice to the maintainer. *2026-11-03:* § The census above;
      the maintainer's merge of #741 chose (a).
- [x] Land the chosen repair, with the threshold's measured basis in its
      docstring, `INDEXING_THRESHOLDS_VERSION` bumped, and the mirrors above.
      *Landed in #741* (1.7's "Also in 1.7" clause). It adds no `PeakFlag`,
      so the one mirror is `no_intensity`'s `help.py` entry, which #741
      rewrote. *2026-11-03:* the docstring's census re-measured under 1.12.
- [x] If the envelope changed: the refinement width census on the same
      patterns, before and after. *Moot:* the envelope did not change.
- [x] Tests, with obs/calc/diff PNGs to `tests/output/`. *2026-11-03:* the
      tests are #741's `tests/test_peak_picking_flank.py`; the PNGs go through
      `tests/indexing_gallery.py` (`silicon_steep_peaks`, `silicon_steep`:
      peak list, candidates, Le Bail obs/calc/diff), and the index row now
      asserts cubic F first rather than present.
- [x] Skill: none beyond the new flag's `help.py` entry, which is where an
      agent reads a flag (WP-1338's cheapest place); a `references/` row only
      if the flag needs a judgement the entry cannot carry. *No new flag:*
      `no_intensity`'s `help.py` entry carries the floor (#741).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_peak_picking.py tests/test_peak_picking_flank.py tests/test_indexing*.py -n auto --dist loadgroup -m "not slow"
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

- **2026-11-03** — closed, PR #1380 (a ghostshift runner, one session).
  The repair this WP asked for had already shipped in #741. What this session
  adds is the evidence for it. Measured on today's tree, the 1σ floor takes
  out four components across 18 real patterns, each under I/σ_I 0.9. The
  other repair, an envelope that follows the flank, would have changed dozens
  of real lines on the round-robin lists and taken 15 net off NAC, so it is
  ruled out. The steep pattern now indexes to cubic F first, and the test
  asserts that and draws it. What is left belongs to other consumers and is
  in issue #1382.
  - *Done.* § The census (task 2). The dossier line on the zero-bound
    bullet of `src/rietx/indexing/CLAUDE.md`, cap 361 → 366.
    `PEAK_NO_INTENSITY_SIGMA`'s docstring re-measured under 1.12. The flank
    test draws `silicon_steep_peaks` and `silicon_steep` through
    `tests/indexing_gallery.py` (new `synthetic` tier, kept off the
    scoreboard), asserts cubic F first, and asserts `no_intensity` on
    *every* flank component. Tasks 1, 3 and 6 were ticked as #741's work,
    and task 4 as moot. `### Inherited` was deleted: #880, #947 and #948
    are all merged and the census says so, and the aragonite fixture was
    not needed once the silicon's truth was exact.
  - *Measured.* The census probe is a scratch script patching
    `pick.PEAK_NO_INTENSITY_SIGMA` and `peaks._debiased_envelope`, outside
    the repo. Fast suite (`-m "not slow"`, `[dev]` venv, macOS arm64,
    alone through ghostshift's serial queue, main unmoved at `5d7622d6`):
    13717 passed, 318 skipped, 34 xfailed, in 8:11. In that run's junit the
    flank file costs about 4.5 s, of which 3.9 s is the index row with its
    Le Bail refit and its PNGs. Slow rows run:
    `test_magnetites_correct_cell_is_ranked_first_and_graded_below_its_rival`
    and `test_the_phantom_lines_are_what_had_blocked_it`, 2 passed. The rest
    of `tests/test_acceptance_indexing.py` was not run, because no engine
    or picker code changed: in `src/` the diff is a docstring and a
    CLAUDE.md line. `python -m tests.reader_output` exited 0. No test was
    added, so passed+skipped should not move.
  - *Review.* `/code-review high --fix`, with seven fixes applied in
    `c29501402`. The dossier line had named the background diagnostics as
    a consumer of `_debiased_envelope`; they read `background_envelope`,
    and the real co-consumers are the width census, `screen.py` and
    `extinction.py`. Declined: dropping the gallery's Le Bail refit (it is
    the obs/calc/diff panel task 5 asked for), and sharing one
    `pick_peaks` across the flank tests (about 0.2 s).
  - *Generality.* Not dispatched: `_audit.py` is untouched, and no
    threshold, flag or action was added.
  - *Gotchas.* On the steep pattern the floor is now one of two flags. Since
    #948 all four flank components are `width_capped` as well, so a test
    of the floor alone has to check `no_intensity` itself, which this one
    now does.
  - *Next:* none here. Issue #1382: Layer 0 reads the Pawley validation's
    background misfit on the flank as 72 unmatched observed peaks, and the
    gentle control ranks trigonal R above cubic F.

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
