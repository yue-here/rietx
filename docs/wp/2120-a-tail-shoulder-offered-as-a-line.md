# WP-2120 — a tail shoulder on its position bound is offered as a line

Milestone: unscheduled · Status: 🔄 2026-11-16 — class 1 landed with synthetic arms (#1579); its approval and reach, and class 2's edge bar, wait on the maintainer
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-06 — false lines reach the engines at full weight, but no case yet moves a cell or costs an indexing row

## Goal

`pick_peaks` does not offer the engines, as a usable line, a component that is the
low-angle tail of a stronger line, or one that a re-seed put at its window's edge to fit a
neighbouring group's tail. Either it is flagged unusable, or this WP records why it stays.

## Context

**Source.** WP-2055's task 1 (2026-11-06, `a84379aac`, `[dev]`, macOS arm64), which asked
why 24 usable components on the 16 IUCr round-robin patterns end on their position bound.
WP-2055 decided the picker keeps the line shape it holds, so these two classes are what is
left, and no open WP owns them: WP-1968 (the false-line bar) and WP-1977 (Layer 0's flank
lobes) are closed, and WP-1909 is the background-flank envelope.

**Class 1, the tail shoulder.** Of the 24, eight are shoulders on the low-angle side of a
4–23× stronger line in the same group. Seven of the eight also carry `axial_tail` and sit
0.076–0.144° from any Kα1 line of their pattern's phases, so the nearest lattice line is the
strong neighbour itself: fluorite 46.918°, sample-1/2 copies at 46.90–46.95°, zircon 43.645°
and 67.674°, brucite 68.034°. Freeing the bound moves all seven further from the lattice. The
eighth (cpd-1f 68.763°, no `axial_tail`) moves onto a lattice line when freed. Declaring each
pattern's Rietveld-fitted Kα2 weight makes all seven `not_separable`, but that weight is not
available before indexing.

**Class 2, the window-edge re-seed.** Two of the 24 (cpd-1b 86.482°, cpd-1c 56.821°) sit
0.5 seed FWHM outside their window's first point. Over all 16 patterns, 120 of 1056
components sit within 0.25 FWHM of a window edge or outside it. All 120 are re-seeds,
56 already carry `duplicate_line`, and 53 are usable.

**Where.** `_axial_tail` and `_flags_for` in `indexing/pick.py`; `PEAK_UNUSABLE_FLAGS` and
`PEAK_UNDRIVEN_FLAGS` in `schemas/indexing.py`; `reseed_candidate` and `_fit_at`'s
`reseed_at` in `indexing/peakfit.py`. `axial_tail` is deliberately out of
`PEAK_UNUSABLE_FLAGS` (WP-1043: 11 unverified usable components on six other lab patterns),
so class 1 asks about the **conjunction** with `position_at_bound`, never about
`axial_tail` alone. WP-2055's harness (direction test, lattice distances, window edges) was
kept outside the tree, in ghostshift scratch. *Superseded in part
2026-11-16:* that directory is gone, and task 1's findings below come from a new harness.

**Tier.** Making a flag combination unusable is a new judgement. It is measured on one
diffractometer only (the round robin), so the first task is a second family: the other
real lab patterns in `tests/data/` (SRM 660c, the FAP pattern, the certified corundum).
A change to `usable()` moves what every engine is driven by, so it runs
`tests/test_acceptance_indexing.py` and goes to the maintainer as a reader-output change.
Tier of what landed (2026-11-16): class 1's action (`tail_shoulder` in `PEAK_UNUSABLE_FLAGS`)
is a new judgement, **tier 3, awaiting the maintainer's dated approval**. It was measured
on three unrelated lab families (the round robin, SRM 660c, SRM 1976a), with fluorapatite as
a fourth that has no case. The reference is the phases' lattice lines, and every family is
development data. It adds no number: its two flags' constants are the ones already in use,
and the `_audit` table has no row for a flag vocabulary.

### Findings, task 1 (2026-11-16, `bc77a934e`, `[dev]`, macOS arm64)

WP-2055's harness was no longer on disk, so a new one measured both classes. It runs
`pick_peaks` on each pattern with its acceptance suite's own instrument. The lattice is the
Kα1 lines of the pattern's phases (the round-robin start cells, the SRM 660c and SRM 1976a
certified cells, the GSAS fluorapatite cell). Each pattern's offset
z + s·cosθ + t·tanθ is fitted on its strong, unflagged, matched lines (I/σ_I ≥ 20). The
residual rms of those lines is 0.002–0.022° on the round robin, 0.0012° on SRM 660c, 0.006°
on fluorapatite and 0.0022° on SRM 1976a. Distances below are after that offset. The second
family is three unrelated lab instruments: SRM 660c (NIST, graphite monochromator,
R = 217.5 mm), the GSAS-II fluorapatite tutorial pattern, and SRM 1976a on an X'Pert with an
X'Celerator (R = 240 mm). The "certified corundum" this WP named is read as SRM 1976a. SRM
676a is `qarr/corundum.prn`, which is the round robin itself.

**The census has moved since WP-2055.** The round robin now has 31 usable components on their
position bound, where WP-2055 counted 24. Class 1 is still eight components, but brucite 71.800°
now carries `axial_tail` in place of cpd-1f 68.763°. Class 2's counts are unchanged:
120 of 1056 components, 56 of them `duplicate_line` and 53 usable.

**Class 1** (usable ∧ `axial_tail` ∧ `position_at_bound`):

| family | n | above the FDR bar | sits below its strong mate by | ratio | distance to the lattice |
|---|---|---|---|---|---|
| round robin | 8 | 8 | 0.75–0.95 FWHM | 4.1–13.7× | 0.070–0.142° (seven); 0.011° (brucite 71.800°) |
| SRM 660c | 1 | 0 (`weak_line`) | 0.82 FWHM | 6.1× | 0.038° |
| SRM 1976a | 2 | 2 | 0.62–0.75 FWHM | 4.0–6.7× | 0.038, 0.039° |
| fluorapatite | 0 | — | — | — | — |

In 10 of the 11 the nearest lattice line is the strong mate's own line. The mate sits on that
line (|Δ| ≤ 0.050°) and the component sits below it on the tail side. Nothing in the phase list
puts a line at the component, so in all ten it is a tail by attribution. The eleventh is brucite
71.800°, which is 0.011° from brucite (112). A Rietveld fit of `brucite.prn` (the round-robin QPA
protocol with texture, Rwp 18 %) gives (112) 0.25 % of (201)'s intensity, but the component is
24 % of its mate. So the component's area is about 100 times what the line under it can supply.
By position it is on the lattice, and by intensity it is the (201) tail. In degrees the distances
scale with the line width: the shoulders sit 0.62–0.95 fitted FWHM below their mate in every
family. That gives 0.07–0.14° on the round robin (FWHM 0.11–0.23°) and 0.04° on the
narrow-line instruments (FWHM 0.05–0.07°). The acceptance's 0.07° is therefore a round-robin
number. On SRM 1976a the same tails sit inside it.

**Class 2** (usable re-seeds within 0.25 seed FWHM of their window's edge, or outside it):

| family | usable | above FDR | outside the window | ≥ 0.07° off the lattice | a neighbouring group holds the same lattice line | on the lattice, held by no neighbour |
|---|---|---|---|---|---|---|
| round robin | 53 | 46 | 29 | 43 | 35 | 7 |
| SRM 660c | 0 | — | — | — | — | — |
| SRM 1976a | 1 | 1 | 0 | 1 | 1 | 0 |
| fluorapatite | 4 | 2 | 4 | 2 | 3 | 0 |

The window edge does separate the false lines from the true ones on the round robin. Of the
usable components above the bar there, 38 of 46 edge re-seeds are ≥ 0.07° off the lattice,
against 28 of 97 inner re-seeds and 62 of 628 detected components. But six of the 46 are on a
lattice line that no other group holds. Taking class 2 out would lose those six lines. The
second family has three such components in all, too few to measure the rule on.

### Findings, the synthetic arms (2026-11-16, `470e6cf0b`, `[dev]`, macOS arm64)

The generality judge rated class 1's action `weak` because nothing showed that the rule
spares a real line. So a positive arm and a negative arm were built on a synthetic
pattern. Fluorite (Fm-3m, a = 5.4631 Å) is drawn by `Refinement.predict` on the round-robin
instrument, with a real axial divergence (FCJ, S/L = H/L), Lorentzian x = 0.04 and
Caglioti widths that give fitted FWHMs of 0.12-0.16° (the round robin has 0.11-0.23°).
The strongest line is 10⁴ counts on a background of 30, with Poisson noise from fixed seeds.
The pattern is picked with the round-robin instrument itself, which declares no axial
divergence, as the real lab files do. Distances are in the fitted FWHM of the strong line's
group, the census's measure. The harness is outside the tree (ghostshift scratch
`wp-2120/arm/`). Two rows of it are tests (`tests/test_peak_tail_shoulder.py`).

**The negative arm: a pure tail** (the strong lines alone, 20 seeds × the six strong lines
below 90°):

| S/L = H/L | components below a strong line | usable but for the rule | taken by the rule | still usable (`axial_tail` alone) | where they sit |
|---|---|---|---|---|---|
| 0 (control) | 0 | — | — | — | — |
| 0.03 | 25 | 19 | 5 | 14 | 0.72-0.85 FWHM below, 5.8-12.9× weaker |
| 0.05 | 66 | 27 | 15 | 12 | 0.69-2.29 FWHM, 4.3-25× |
| 0.07 | 84 | 23 | 0 | 23 | 0.84-2.61 FWHM, 4.1-18× |

With no tail in the data, nothing sits below a strong line. At S/L = 0.03 the tail leaves
shoulders exactly where the real ones sit (0.62-0.95 FWHM, 4-14×, task 1), so that setting
is the one most like the lab data. There the rule takes 5 of the 19 shoulders. The other
14 sit at the same place, but their fits did not reach the position bound, so they stay usable.

**The positive arm: a real line.** A second fluorite phase with cell a(1 + ε), at 1/r of
the host's scale, puts a real lattice line below each strong line. ε takes 40 values
from 0.0006 to 0.016, with 3 seeds each, and every strong line below 90° is read. A planted
line is *kept* if a usable component lies within min(sep/2, 0.5 FWHM) of it. It is *taken
by the rule* if the component there carries `tail_shoulder` and no other unusable flag.
*Other* means unusable for another flag (`unresolved_split`, `not_separable`), and
*not separated* means no component there.

| S/L = H/L | 0.6-1.0 FWHM below, r = 5-14: kept / taken / other / not separated | same band, r = 25: kept / taken | 1.0-3.5 FWHM, r = 5-14: kept / taken | 2.0-3.5 FWHM, r = 25: kept / taken |
|---|---|---|---|---|
| 0 | 130 / 3 / 16 / 184 | 10 / 0 | 761 / 0 | 78 / 8 |
| 0.03 | 96 / 16 / 41 / 171 | 17 / 1 | 731 / 0 | 85 / 3 |
| 0.05 | 49 / 1 / 86 / 188 | 1 / 6 | 704 / 1 | 73 / 10 |

At r = 3 the rule took nothing at any separation (sweeps at S/L 0 and 0.05), because
`axial_tail` needs the mate 4× stronger.

What the two arms say (no bar set here):

- **Away from the tail's own position the rule spares real lines.** At 1.0-3.5 FWHM and the
  census's ratios (5-14×), it took 1 of 2197 resolved lines. In the 0.6-1.0 band it took 3 of
  133 with no tail in the data and 1 of 50 at S/L = 0.05. Half the planted lines in that band
  are not resolved at all (Sparrow's limit, which the rule cannot change).
- **Where the tail's shoulder sits, the rule cannot tell a real line from the tail.** At
  S/L = 0.03 it took 16 of the 112 resolved real lines in the band. Ten of those 16 are at
  0.7-0.8 FWHM and 5-7× weaker, against 6 kept there. At that same setting it takes 5 of the
  19 pure-tail shoulders. So at the lab-like setting, the rule took a real line in 14 % of
  cases and a tail shoulder in 26 %. That is weak discrimination, and it is a weak catch.
- **The rule has the reach of `axial_tail`, not the reach of the census.** It reaches 3.5
  FWHM and has no upper ratio. Very weak real lines (r = 25, beyond every census case) are
  taken at 2.0-3.5 FWHM: 21 of 257 resolved over the three settings.
- One structure, one line width, one count level, and only axial divergence as the tail's
  source. The negative arm's band matching the census is the evidence that this tail stands
  for the lab one.

## Non-goals

- The line shape the picker holds (Kα2 weight, apertures): decided in WP-2055.
- The flag's level (`info`, ruled 2026-10-21).

## Tasks

- [x] Measure both classes on a second instrument family: count `axial_tail` ∧
      `position_at_bound` usable components and their distance to the lattice, and the
      usable window-edge re-seeds and whether a neighbouring group already holds their line.
- [x] Decide, per class, whether it leaves `usable()`, is undriven only
      (`PEAK_UNDRIVEN_FLAGS`), or stays. Record as `Decided YYYY-MM-DD:`.
      **Decided 2026-11-16 (class 1): it leaves `usable()`.** A new flag, `tail_shoulder`,
      is raised on the conjunction and is in `PEAK_UNUSABLE_FLAGS`, while neither flag
      alone moves. The rule is no bar of ours: it combines two existing flags, and the
      acceptance above sets the outcome. Task 1 found every such component on three lab
      families to be its mate's own tail. Undriven-only was weighed and rejected: it keeps
      the shoulder in scoring, so every candidate would be charged for not indexing a
      "line" that is the strong line's tail. That is the case `PEAK_UNUSABLE_FLAGS`
      exists for (`not_separable`'s "a shape, not a line"). It is still a new judgement
      (tier 3) and a reader-output change, so it goes to the maintainer.
      **Not decided (class 2): it stays usable, and the question goes to the maintainer.**
      Placing it needs a bar the WP does not set: how near a window's edge a re-seed must
      sit (WP-2055's 0.25 seed FWHM was a census window, not a rule). On the round robin
      that bar would also take six on-lattice lines no other group holds. The second
      family has three such components, too few to measure on.
- [x] Land it, with `tests/test_acceptance_indexing.py` green.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.
- [x] Skill: the `axial_tail` or `PEAK_POSITION_AT_BOUND` reference row if what a reader
      should do changes; else none.

## Acceptance

On the 16 round-robin patterns, no usable component above the false-discovery bar is a tail
shoulder 0.07° or more from every lattice line, with no indexing acceptance row lost; or the
WP records why such a component stays usable.

```sh
.venv/bin/python -m pytest tests/test_peak_bounds.py tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Madsen, I. C. et al. (2001). *J. Appl. Cryst.* 34, 409 (the IUCr CPD round robin).
- WP-2055 (the census and the direction test); issue #1166.

## Handover log

- **2026-11-16 (review fix-ups, PR #1579)** — A second review found that the editor's
  *fresh* refit (`PeakEditor.refit(doc, g)` with no `n_components`, which runs `fit_group`
  and so judges) returns 9 of the 10 development shoulders to `usable()` with `axial_tail`
  alone. Seeded at its fitted position, the component converges 0.0001-0.057° away and off
  its bound (SRM 1976a 52.5267° → 52.5208°, 76.8362° → 76.8361°, re-checked here; only zircon
  67.67° comes back on its bound). The earlier answer "named positions are never judged" holds
  for add, move, remove and the `n_components` refit only. So the flag depends on detection's
  seed path, and "no position of its own" was a census reading, not a measurement: the docs
  now say "on the development data" and "on a list detection picked". No code changed and no
  test pins the fresh-refit path. **Open for Yue (with decision 1):** should a fresh refit keep
  the flag (a path-independent rule, such as `axial_tail` within the 0.6-1.0 FWHM band and
  4-14× ratio), or is the instability accepted and pinned by a test?
- **2026-11-16 (second session, PR #1579)** — Class 1 now has the synthetic positive arm the
  judge asked for, and a negative arm, so the rule's evidence can fail in either direction. A real weak lattice line
  planted below a strong one survives the rule wherever it does not sit on the tail's own
  shoulder. Of 2197 resolved real lines at 1.0-3.5 FWHM, 5-14× weaker, the rule took 1. Where
  the shoulder sits, it cannot tell the two apart. With the lab-like tail (S/L = H/L = 0.03, whose pure-tail shoulders fall in the census's
  0.6-1.0 FWHM, 4-14× band), the rule takes 16 of 112 resolved real lines in that band and
  5 of 19 pure-tail shoulders. No code changed. No bar was set and class 2 was not placed.
  *Done:* findings "the synthetic arms" above; two test rows in
  `tests/test_peak_tail_shoulder.py` (`470e6cf0b`): the negative arm with its no-tail control
  (5 taken, 14 left, all 0.6-1.0 FWHM and 4-14×), and the positive arm in one pattern (real
  lines 0.62 and 0.95 FWHM below kept with `axial_tail`, the 0.75 FWHM one taken), with
  `tests/output/peaks_tail_shoulder_planted.png`. Each fails if the rule is widened to
  `axial_tail` alone or dropped.
  *Measured:* sweep on macOS arm64 `[dev]` (harness in local scratch, not committed,
  about 7 min). Both new rows pass on Linux x86_64 too: the workstation's canary on `470e6cf0b`,
  `test_peak_tail_shoulder` + `test_audit_table` + `test_help` (`-m ""`, `-n 4`), 66 passed.
  Acceptance on the workstation, same tree: `test_peak_bounds` + `test_peak_tail_shoulder` +
  `test_acceptance_indexing` (`-m ""`, `-n 4`): 60 passed, 0 failed (this morning's 58 plus the two new
  rows). Ruff clean. `tests.reader_output` exit 0, unchanged. `test_docs_consistency` + the test file on macOS: 32 passed.
  *Questions for the maintainer* (not decided here):
  1. Does the tier-3 approval stand, given that at the lab-like tail the rule takes a real line
     in 14 % of resolved cases and a tail shoulder in 26 %?
  2. Should the rule's reach be narrowed to the census band? It inherits `axial_tail`'s
     3.5 FWHM and has no upper ratio, so it takes 21 of 257 resolved r = 25 lines at 2.0-3.5
     FWHM. Narrowing it is a bar.
  3. The rule catches 0-56 % of pure-tail shoulders, depending on the tail. The rest stay usable with
     `axial_tail` alone, as before this WP.
  4. Class 2's edge bar, as before. No `_audit` row was added: `_audit.py` is WP-2017's lane today.
  5. Is the rule's kind 1, an act, or kind 2, a choice a candidate cell can score? This is the judge's reading.
     If kind 2, undriven-only (`PEAK_UNDRIVEN_FLAGS`) is the tree's shape for it. The cost of keeping the 11 real
     shoulders usable was argued in task 2 but never measured.
  6. Who writes the `action` row for `tail_shoulder` (keyed on `ObservedPeak.flags`), and a
     test that sees `PEAK_UNUSABLE_FLAGS` membership: WP-2017, or the session that acts on 1?
  *Generality:* re-run on this tree (read-only subagent, the `generality-review`
  definition). Its two verdicts and their closing lines, verbatim. The full tables are in PR #1579's body.
  - item 1, `tail_shoulder` in `PEAK_UNUSABLE_FLAGS`: **`weak`.** "The new synthetic arms
    move the stronger evidence to the case against. The author's own positive arm shows that,
    in the band where the rule acts, it cannot tell a real line from a tail. The case for
    acting still rests on 11 components on development data, called tails because no lattice
    line lies under them, and no cost of leaving them usable has been measured." It reads the
    ambiguity as kind 2 (tail or lattice line, which a candidate cell can score), with
    `PEAK_UNDRIVEN_FLAGS` as the tree's kind-2 shape. It also notes that the tail-free control
    (S/L = 0) still loses 3 of 133 resolved real lines in the band, and 8 of 86 at r = 25,
    2.0-3.5 FWHM. *Would change it:* "a real pattern with a known weak line 0.6-1.0 FWHM below
    a line at least 4× stronger (a weighed minor phase, or synchrotron data) that the rule
    keeps, together with a measured indexing cost of leaving the 11 shoulders usable, would
    raise it toward `holds`. A real line taken on real data, or the S/L = 0 takes left
    standing on a tail-free instrument, would lower it toward `fails`."
  - item 2, the `_audit` row (none added): **`weak`** (was `fails`). "This morning's condition
    is met on the author's account: the approval is now asked for. The case against leaving
    the row out is still the stronger side." No kind of row in the table sees membership of
    `PEAK_UNUSABLE_FLAGS`, and no step names who writes the row. *Would change it:* "an
    `action` row keyed on the flag, with ambiguity, evidence naming the families and the
    synthetic case where the rule fails, grounds, and the date once ruled; or a named task in
    this WP's or WP-2017's *Next* to write that row, plus a test that sees
    `PEAK_UNUSABLE_FLAGS` membership."
  *Next:* the maintainer rules on 1-6. Then a session either keeps the rule, narrows its reach
  (with these arms as its test), demotes it to undriven, or withdraws it. It writes the `_audit` row the ruling
  names, then places class 2.

- **2026-11-16** — The picker no longer offers the engines a weak shoulder that sits on a strong
  line's axial-tail side and that its fit pushed to its position bound. Such a component is now
  flagged `tail_shoulder` and is unusable; either flag alone still leaves a line usable. On three
  unrelated lab instruments, every component this catches sits below its strong mate's own
  reflection. So the round robin's off-lattice shoulders leave the list (782 → 774 usable) with no
  indexing acceptance row lost. The window-edge re-seeds (class 2) are measured but not placed:
  that needs an edge bar the WP does not set, and the maintainer is asked for it in PR #1579. Both
  the tier-3 approval and the class-2 bar are the maintainer's.
  *Done:* tasks 1-5 (`8ccdda1cf`, `7524ce19e`, `6d906c4f4`, `aaa61b53e`, `c10c1ac97`). The flag
  is raised in `_flags_for` only on fits `fit_group` judged (`width_at_bound` not `None`), so
  `fit_peaks` and the peak editor never raise it on named positions, like `width_capped`. It
  is in `PEAK_UNUSABLE_FLAGS`, and `INDEXING_THRESHOLDS_VERSION` is 1.13. Also updated: the help
  entries, the `PEAK_AXIAL_TAIL` message (it counts the excluded ones), the manual's flag table,
  the skill row, the GUI vocabulary and dist, a release note, and `tests/test_peak_tail_shoulder.py`
  (4 rows, one `slow`).
  *Measured:* see Findings above. The Linux x86_64 workstation (shared, co-tenant), `[dev]`, `aaa61b53e`:
  `test_peak_bounds` + `test_peak_tail_shoulder` + `test_acceptance_indexing` (`-m ""`, `-n 4`) 58 passed, 0 failed (the 54 main rows plus 4 new). Main bc77a934e on the same machine: `test_peak_bounds` + `test_acceptance_indexing`
  54 passed. Fast suite (`-m "not slow"`, `-n 6`) on `aaa61b53e`: 14850 passed / 3 failed / 280 skipped / 32 xfailed. Three rows were fixed after it: the skill API index (`c10c1ac97`), and two flat-Si rows that count the usable or driven lines (`test_indexing_screen` 16 → 15; `test_indexing_driven_set`'s control now also offers the `tail_shoulder` back, so it keeps its 18 lines). Their three files were re-run locally on macOS arm64 `[dev]`: 212 passed. `tests.reader_output` exit 0 (unchanged).
  *Rows moved:* `test_peak_bounds`' flat-Si census goes from 16 to 15 usable. The removed
  component is 35.31°, 0.095° off its line, and `weak_line` goes from 5 to 4, because the
  false-discovery screen reads usable components only. In two LaB6 acceptance rows, SRM 660c's
  43.5° slot-swap tail is now `tail_shoulder`: the flag trim and the certificate probe agree, and
  the tight-window control keeps WP-1040's 0.0078° window by offering that component again. The same
  35.31° Si component moves `test_indexing_screen` (16 → 15 usable) and `test_indexing_driven_set`'s
  control, which offers it again.
  *Review:* a read-only review subagent (no `/code-review`, ghostshift rule) raised four points:
  - an editor refit drops the flag: now by contract, since named positions are never judged;
  - `fit_peaks` raised it on named positions: fixed by the judged-fit gate, and a test covers it;
  - a dead assertion: dropped;
  - stale table and version texts: fixed.

  *Generality* (judge's verdicts, unedited in substance):
  - item 1, the action: `weak`, for no positive arm (a genuine weak line planted 1-3 FWHM below
    a strong one), all-development families, and no dense or synchrotron pattern;
  - item 2, the `_audit` row: `fails` until the PR asks for the dated approval.

  Author's answer: the PR asks for it. The `PEAK_AXIAL_TAIL` code row is on
  `UNAUDITED_BASELINE`, and `_audit.py` is WP-2017's lane today, so no row was added here.
  The help entry names the families and says it is untested beyond them.
  *Gotchas:* `ObservedPeak.usable` is a property. WP-2055's harness is gone, and this session's
  is outside the tree (ghostshift scratch `wp-2120/census.py`).
  *Next:* (1) the maintainer rules the tier-3 approval, or asks for the synthetic positive arm
  first. (2) The maintainer sets class 2's edge bar, if any. Then a session places class 2 and
  closes the WP.

- **2026-11-06** — created from WP-2055's handover. No open WP owns either class: WP-1968
  and WP-1977 are closed, and WP-1909 is the background-flank envelope. *Next:* task 1.
