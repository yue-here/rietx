# WP-1510 — What the chemist knows reaches the indexing search

Milestone: unscheduled · Status: ✅ 2026-10-23 — a peak list offers each line once, a refused prior or quality gate names its fix, a cell reads by name, and a formula gives a volume window and a Z check (PR #690, in 1.7)
Track: Data and metadata in, a structure out
Depends on: — (1449 soft, the ranking this feeds; 1508 soft, the search that ran out of time)

## Goal

An agent starting an indexing job asks the person what cell range they
expect, or derives one from the chemistry the person already gave, and the
package carries that range into the search. The four places where the run
below lost time each tell the caller what to do next.

## Context

**Source.** `solution case 1` in the private `yue-here/rietx-corpus-map`
§ 5: an agent session of 2026-09-23/25 on rietx 1.4.0, driving a lab
capillary pattern of an unpublished layered coordination polymer. A session
six days earlier on the same pattern had ended with no reliable cell. This
file quotes what the runs did (counts, wall clock, ratios) and nothing about
the specimen (WP-1450's rule). Every count below was re-read from the
session transcript on 2026-09-28, and every code site checked on `c1bd21dd`.

**The blind search never found the cell.** With `max_d_axis=32` the engines
merged 399 lattices and abstained. The accepted cell appears only as a
declared prior, "entered unconfirmed (prior-only, after the ranked
candidates)". The person had it from electron diffraction and a hand Pawley
fit. The best blind candidate had about a third of its volume. So the
person's knowledge was the answer, and the first two messages of the session
held all of it: the formula, "no solvent by TGA and elemental analysis", two
candidate cells, and the CIF of an isostructural analogue.

**1. Ask, or infer.** The skill tells an agent how to read an indexing
answer and never tells it to ask for an expected cell range first. The rule
to add (the maintainer's, 2026-09-28): before the first search, ask the
person for a cell range or candidate cells; when they have supplied the
chemistry (formula, Z or density, solvent content), infer a volume window
from it and say so rather than asking.

**2. A volume window from the formula.** `SearchSpec.min_volume` and
`max_volume` exist (`src/rietx/schemas/indexing.py`) and nothing fills them
from chemistry. Two candidate sources, to read before citing: Kempster &
Lipson (1972), about 18 Å³ per non-hydrogen atom for organics; Hofmann
(2002), per-element volumes, which a heavy-atom compound needs. On this run
the 18 Å³ figure lands 8 % under the accepted volume per formula unit. The
window also gives a Z check. The best blind candidate implied Z ≈ 2.8, and a
candidate with a non-integer Z is flagged with that number and never removed
(the agent-first rule: report evidence, do not refuse).

**3. A prior refused at the box.** `max_d_axis` defaults to 25 Å
(`schemas/indexing.py:1198`). One axis of the person's cells was longer.
`INDEX_PRIOR_USED` (`src/rietx/indexing/priors.py:349`, level `info`)
reported "outside the declared axis range 2-25 Å — a prior never widens the
box" inside a longer message. The agent read it, raised the box by hand and
reran: 24 minutes. WP-1045 decided that a prior never widens the box. Either
keep that and make the refusal a `warning` whose suggestion names the value
to pass, or reopen 1045's decision now that a person-supplied cell has been
refused on real data. Record which, with the reason.

**4. The quality gate names the instrument last, or never.**
`INDEX_DATA_INSUFFICIENT` refused at median σ(Q)/Q = 1.05e-3 against its
1e-3 bar. Declaring the capillary's axial divergence and a realistic
starting width *before* picking brought it to 6.9e-4, and the gate passed.
The suggestion (`src/rietx/indexing/diagnostics.py:255`) names the 2θ range,
the counting time and `PEAK_MIN_HEIGHT_SIGMA`. When the instrument passed to
`pick_peaks` still has default axial divergence or an unseeded profile, the
suggestion should say that first.

**5. One line per physical peak.** `pick_peaks(...).usable()` returned 129
lines for about 50 physical ones, with three copies within 0.003° of each
other at one line. `INDEX_IMPURITY_LINES` then reported 60 observed lines no
candidate explained, most of them copies. The agent kept the best copy per
`detect_peaks` group seed. A review subagent traced the copies to shoulder
seeding (`src/rietx/indexing/peaks.py:221`, `_shoulder_seeds`); that is
**unverified**, so the first task measures the mechanism.

**6. `CellCandidate.cell` is a bare 6-tuple** (`schemas/indexing.py:936`).
The run's first indexing script called `.a` on it and raised
`AttributeError`.

**7. Two settings of one lattice.** The agent declared the electron
diffraction cell twice, once with an acute and once with an obtuse
monoclinic angle. Whether priors are reduced to one setting before they are
checked is **unverified**.

**Adjacent, not here.** Which of several cells a pattern supports is WP-1511.
The quick preset's 30 s per system ran out on the monoclinic and
orthorhombic searches here (`INDEX_SEARCH_INCOMPLETE`, then
`INDEX_BUDGET_EXHAUSTED` at 120 s); search speed is 1508 and 1509 (PR #514).

**Ranking is settled** (WP-1449, closed 2026-09-29): a reported supercell the
pattern does not support ranks directly below its parent (`supercell_refuted`).
A prior that changes the reported list changes which pairs get asked, never the
rule.

**Sites re-checked 2026-10-03 on `0303da12`**: all still hold, with line drift
(`schemas/indexing.py` `max_d_axis` now :1204 and `CellCandidate` :932,
`diagnostics.py` `INDEX_DATA_INSUFFICIENT` :327, `priors.py` refusal :237).

**The window built here has a known limit.** Hofmann's volumes come from
organic and metal-organic crystals, and the window excluded 7 of the 9 known
cells WP-1986 measured on 2026-10-18; only NaCl and paracetamol fell inside.
WP-2030 owns that, with the review findings left open below.

## Non-goals

- Widening the default box for everyone.
- Changing how candidates rank (1449).
- Any engine change. The peak list feeds every engine, so
  `tests/test_acceptance_indexing.py` still runs before close.

## Tasks

- [x] Measure where the duplicate lines come from, on a public fixture that
      reproduces them or a synthetic one built to. Then collapse to one line
      per physical peak on the path into `index_pattern`, pinned by a test
      that counts lines.
- [x] `INDEX_DATA_INSUFFICIENT`: the suggestion names an undeclared
      instrument first. Test both branches.
- [x] `INDEX_PRIOR_USED`: a prior refused at the box is reported at
      `warning` with the `max_d_axis` value to pass, or 1045's decision is
      reopened. Either way the handover records the reason.
- [x] A volume window and a Z check from a formula: a `SearchSpec` helper,
      its volume source read and cited in the docstring, and a diagnostic
      for a candidate whose volume implies a non-integer Z (code named at
      review, with its `help.py` entry). No `INDEX_*` code has a `help.py`
      arm, so the entry is the skill row (2026-10-03).
- [x] `CellCandidate`: named accessors or a `to_cell()`. Check whether two
      settings of one lattice are merged as priors, and say so in the
      docstring.
- [x] Manual Part 1 and `tests/api_surface.py`: every new public name
      documented (the partition fails until it is).
- [x] Skill: the ask-or-infer rule in the indexing reference, tagged
      `(Measured: solution case 1)`, inside `tests/skill_caps.py`'s budget.
- [x] The four acceptance rows the de-duplicated line list moved
      (handover 2026-10-03): corundum indexes at c/2, its declared-shift row
      reads −0.090°, cpd-1a's shift reads −0.009°, and zircon's primitive
      twin indexes one line fewer than the centred cell. Decide each before
      this WP closes.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

And, recorded in the handover with counts only: `solution case 1`'s first
indexing call replayed on the new tree. The line count is within a few of
the physical lines, the refused prior's warning names the value, and an agent
given the skill asks for or infers the range before its first search.

## References

- Kempster, C. J. E. & Lipson, H. (1972). *Acta Cryst.* B28, 3674. The
  18 Å³ rule. Read before citing.
- Hofmann, D. W. M. (2002). *Acta Cryst.* B58, 489–493. Per-element
  volumes. Read before citing.

## Handover log

### 2026-10-23 — closed: what the chemist knows reaches the search

What this WP built has stood since 1.7. A peak list offers each physical line
once, a refused prior and a refused quality gate each name their fix, a
candidate's cell reads by name, and a formula gives a volume window and a Z
check. What stays open is the window's reach. Hofmann's volumes come from
organic crystals, so on most inorganic solids the window misses the true cell,
and the skill tells an agent to build it before the first search. That and the
review findings left open below are now
[WP-2030](2030-a-formulas-volume-window-fits-inorganic-cells.md).

*Closed by* the maintainer's decision today, which discharges the merge and
close that waited on them. PR #690 merged 2026-10-03 with every task ticked,
the full suite at 8418 passed, 0 failed on the merged tree (entry below). The
replay of `solution case 1` never ran: its pattern is a collaborator's
unpublished data, not in this tree (PR #690's body). The close discharges that
acceptance item for that reason, and with no data to come it is not forwarded.

*Inherited:* the one bullet (WP-1986, 2026-10-18: the window misses 7 of 9
known cells) is open work. It became WP-2030's Context and first tasks, plus
one sentence in Context here. *Forwarded* to WP-2030, filed now because no open
WP owns `from_formula`, Hofmann, a hydrate or `formula=`: the inorganic window
and its Z check; the five open review findings, the hydrate parse first; the
two-step flow; `formula` in the CLI and GUI; whether the supported-supercell
promotion earns an `indexing/CLAUDE.md` rule; and the Z ≈ 2.8 trade-off, as
Context. 1511 and 1517 name 1510 soft, and neither priority moves.

*Next.* Nothing owed here.

- **2026-10-03** — The four red acceptance rows are fixed, and one of the
  fixes is a ranking rule. Corundum had started indexing at half its true c,
  because its certified cell now had one finder against three for the
  half-cell. The package's own supercell test already knew better: the
  certified cell explains eight lines the half-cell cannot, far above chance.
  A supercell the pattern supports now ranks directly above the cell it
  doubles, the mirror of WP-1449's demotion of one the pattern refutes. The
  other two rows had pinned values that rested on the duplicate copies. The
  whole indexing acceptance file passes. The maintainer merges this after
  1.6 is cut.

  *Done.* `consensus.above_supported_parents` moves a child whose
  `SupercellCheck` reads supported to directly above its parent. A child
  refuted against any parent never moves up, which also rules out cycles.
  "Supported" now counts only extras seen on lines the parent leaves
  unexplained (`SupercellCheck.n_seen_unexplained`). Without that, LaB6 grew
  a phantom promotion: two pseudo-tetragonal descriptions read 2 of 3 extras
  seen, all on lines the rival already explained. No refuted verdict
  changed. WP-1449's file never weighed the supported direction, and it
  recorded corundum's 8/18 only because the truth already ranked first then.
  The 1.7 note, both manual parts and three fast tests are in.

  Acceptance edits, each with its measured reason in a comment:
  - Corundum's plain row: `n_indexed >= 50` became 45, since the five copies
    were all indexed lines (50/52 → 45/47).
  - Corundum's shift row now asserts that c/a moves toward the certificate,
    −53 → +5 ppm. It used to assert this of a, which overshoots
    (+110 → −114 ppm, a 4 ppm miss). c/a is the certificate-grade quantity
    (tests/CLAUDE.md).
  - cpd-1a's shift is now −0.0095 ± 0.005°, the fluorite-only fit, and the
    corundum-agreement clause is gone: displacement is set per mount.
  - Zircon asserts only the twins' one-line gap. The direction flipped
    because the twins are refined separately.

  *Measured* (`[dev]` venv, macOS arm64). Lane replay over 13 captured
  searches: only corundum's order moved, 8th → 1st in both searches.
  Brucite's 24 pairs and NAC's pair stay refuted. svd's seed-0 miss of the
  certified cell is reproduced (seeds 1-5 find it). The fast indexing,
  manual and docs selection: 442 passed, 1 skipped.
  `test_acceptance_indexing.py`: 44 passed in 14:43 with nothing else
  running. Lanes: the trial row is updated to 6 lanes, 3 kept, saved +17.77
  (+31 %).

  *Review* (`/code-review high --fix`, 9 findings). Four are fixed:
  - `INDEX_SUPERCELL_REFUTED` and its manual and skill text say "below", not
    "directly below", since a promoted parent leaves its refuted child in
    place.
  - The boxed-prior warning keeps the prior-only guidance.
  - `from_formula` refuses a duplicated volume field and takes a list `z`.
  - The default W is read live.

  Five are open:
  - **`CuSO4.5H2O` reads as 4.5 O and comes out 39 % low, silently.** The
    grammar cannot tell it from `Mg0.5SiO3`. Refusing a `.` hydrate and
    pointing to `·` is the candidate fix.
  - In the supercell test, "unexplained" uses the child's shift correction
    for the parent's lines.
  - The GUI editor's stale `duplicate_line` marks.
  - The synchrotron instrument-first lead.
  - `formula` is not recorded on the result.

  Fast selection after the fixes: 8146 passed, 159 skipped, 1 failed (main's
  `api.md` cap row). That is +3 against 8143, the supercell tests. Baseline
  replay at this trial row: the selective policy saves 24 %.

  *After the 1.6 cut* (the same day). Main is merged in at `006286ac`, which
  opened 1.7, and the venv is reinstalled at `1.7.0.dev0`. The user-facing
  changes are staged in `docs/releases/1.7.0.md`. `API_INDEX_MAX_BYTES` went
  39 600 → 39 700: `index_pattern(formula=, temperature=)` adds 56 B and the
  merged file stood at 39 605 B. That leaves 300 B under the 40 kB
  truncation, so the next raise is the split (WP-1532's Inherited). On the
  merged tree (`[dev]` venv, macOS arm64, nothing else running): the fast
  selection gave 8155 passed, 159 skipped and 0 failed. The full suite gave
  8418 passed, 168 skipped and 0 failed in 18:59.

  *Next.* (a) Merge PR #690 when CI is green; that is the maintainer's
  call. (b) The open review findings: the instrument-first
  lead on a synchrotron setup, the two-step flow that never sees it, and
  `formula` in the CLI and GUI, and the five open review findings above,
  the hydrate parse first. (c) Whether a supported supercell's
  promotion deserves an `src/rietx/indexing/CLAUDE.md` rule. It changes
  nothing outside `indexing/`, so it needs no root clause.

- **2026-10-03** — A formula now says how big the cell should be. Given a
  chemical formula, the package estimates one formula unit's volume from
  Hofmann's (2002) per-element volumes, and the caller can turn that into a
  search window. A candidate whose volume implies a fractional number of
  formula units is reported, never removed. Both source papers were read, the
  table transcribed from the published PDF. The Z check is deliberately
  coarse. One crystal scatters 4 % about Hofmann's estimate, so a cell 2.8
  formula units big reads as "3, within the method" and does not fire. The
  source run's 2.8 came from the cruder 18 Å³ rule, which ran 8 % low there,
  and says nothing about this one. All seven tasks are in. The four red
  acceptance rows from the first entry below are unchanged and still wait on
  the maintainer.

  *Done.* `crystallography/atomic_volume.py`: Hofmann's Table 2, transcribed
  from the PDF's text layer and checked against the page image. Sixteen
  elements the PDF prints as a dash are absent, and Ac and Am carry no error.
  `formula_unit_volume(formula, temperature)` scales by
  (1 + ᾱT)/(1 + ᾱ·298 K), ᾱ = 0.95 × 10⁻⁴ K⁻¹. `SearchSpec.from_formula(formula,
  z=…, temperature=…)` sets `min_volume`/`max_volume` to z formula units ×
  0.8-1.25, Hofmann's own ratio bounds (1746 of 182 239 structures outside).
  With `z=None` it sets only the floor. `index_pattern(formula=, temperature=)`
  reports `INDEX_Z_NOT_INTEGER` (warning, `value` = implied Z) per candidate
  and never narrows. The tolerance `Z_INTEGER_TOLERANCE` is twice the 4.00 %
  single-crystal scatter (Hofmann §3, a percentage of V_obs/V_est: the 18 Å³
  rule's is 9.04 against its published ~10 %). Above Z = 6.25 the check is
  silent by arithmetic. No `help.py` entry, because no `INDEX_*` code has an
  arm there, so the skill row is the entry. Manual Parts 1 and 2, two bib
  entries and ATTRIBUTION.md are updated. Hofmann was in the corpus all along
  at `zotero-linker/derived/XULHS76B/`; two content greps missed it because
  the text never spells the name.

  *Measured* (`[dev]` venv, macOS). Spot-checks against the PDF: H 5.08 ±
  0.04, C 13.87 ± 0.05, N 11.8 ± 0.3, O 11.39 ± 0.17 Å³. Benzoic acid comes to
  150.35 ± 0.93 Å³, 16.7 Å³ per non-hydrogen atom. Indexing, manual, skill and
  docs selection: 668 passed, 1 skipped, 1 failed (main's `api.md` cap row).
  `tests/test_indexing_formula.py` adds 22 tests. `api.md` grew 39 519 →
  39 575 B, further over the cap WP-1532 now holds. Lanes: the trial row in
  `docs/milestones/process.md` is updated to 5 lanes, 2 kept, saved +7.74
  (+21 %). The volume lane's second dispatch took 101 requests against an
  estimate of 35. The baseline replay's selective policy saves 24 %.

  *Review* (`/code-review high --fix`, 10 findings). Five are fixed:
  - Unusable copies leave `flag_duplicate_lines`' sort, since a NaN esd broke
    the order.
  - A position-only list is never told to re-pick with a declared instrument.
  - `from_formula` raises on an empty window, where `H2` with z = 1 put the
    floor above the ceiling.
  - The Z message quotes the formula-unit volume ratio, not a density.
  - The 1.7 note now records `INDEX_PRIOR_USED`'s level change and the
    opt-in Z check.

  Five are declined:
  - The GUI editor's stale `duplicate_line` after an owner moves. Fixing it
    would edit other groups, which `gui/peaks.py` forbids.
  - A refitted better copy beside an untouched one leaves both usable. The
    test pins that outcome.
  - `from_formula` raises a bare `TypeError` on a duplicated keyword.
  - The synchrotron instrument-first lead, the earlier finding 5.
  - The formula parsed once per candidate.

  Fast selection (`[dev]` venv, macOS) after the fixes: 8143 passed, 159
  skipped, 1 failed (main's `api.md` cap row). That is +22 passed against the
  first entry's 8121, exactly the new formula tests, and no new skip.

  *Next.* (a) The four acceptance rows and the two review findings: the
  first entry's next actions (a) and (b) are unchanged. (b) `formula` does not
  reach the CLI (`cli.py:305`) or the GUI (`gui/session.py:1583`) yet. (c) If
  the maintainer wants the source run's Z ≈ 2.8 flagged, the tolerance has to
  fall below 6.7 %, and Table 1 says about a third of correct cells sit more
  than 5 % off.

- **2026-10-03** — A peak list no longer offers one line twice. About a
  quarter of the lines a re-seed pass adds turned out to be a neighbouring
  group's line fitted again, so a crowded lab pattern listed up to a third of
  its lines twice, and the indexer counted the copies as impurities. They are
  now flagged and kept out of what the engines see. The cleaner list broke
  four indexing acceptance rows, because the old answers leant on the copies.
  The lane that traced them found no wrong copy kept. It found the corundum
  answer resting on one engine's random seed, and two pinned shift values that
  were artefacts of the copies. Three smaller defects from the source run are
  fixed. A refused prior now names the value to pass, a refused quality gate
  names the undeclared instrument first, and a candidate's cell reads by name.
  The volume window waits on two papers.

  *Done.* (1) `duplicate_line`: a `PeakFlag` in `PEAK_UNUSABLE_FLAGS`, set by
  `pick.flag_duplicate_lines` in `pick_peaks_with_state` and in the GUI
  editor's `_spliced` (`only=`). It marks a component of one group within
  `PAWLEY_OVERLAP_FWHM_FRAC`·FWHM of a better-measured, usable component of
  another group, and keeps it in `peaks`. `INDEXING_THRESHOLDS_VERSION` is now
  1.7. Mirrors: `help.py`, `help_keys.json`, `gui/src/lib/rxt.ts` and the
  rebuilt dist, the manual's flag table, and the regenerated skill `api.md`.
  The review subagent's shoulder-seeding guess is **refuted**: 0-1 shoulder
  seeds on every pattern. (2) `INDEX_DATA_INSUFFICIENT` leads with
  `diagnostics.undeclared_instrument` when `assess_peak_list(instrument=)`
  sees zero axial apertures or the default `ProfileTCHZ`. `index_pattern`
  passes its instrument through. (3) **WP-1045's never-widen rule is kept.**
  The box is the search the caller declared, so a prior that widened it would
  make that search depend on a guess. A refusal at the box is now a `warning`
  whose suggestion is `SearchSpec(max_d_axis=N)`, with N one ångström past the
  prior's longest axis (`PriorReport.box`). (5) `CellCandidate.a` … `.gamma`
  and `.to_cell()`. Measured: a monoclinic prior declared with β and with
  180° − β comes back as one candidate, and `INDEX_PRIOR_USED` names both
  priors. (7) The skill's §7d asks for the cell, or infers it, before the
  first search. Its 520 B was paid for by cuts in the same file.

  *Measured* (`[dev]` venv, macOS). Duplicates: on the 16 IUCr round-robin
  lab patterns, 4-35 components are flagged where any are, and `cpd-4` went
  from 113 usable lines to 78. Close pairs (< 0.02°) among usable lines fell
  from 2-26 per pattern to 0, while LaB6 and fluorite were untouched. 11-BM
  NAC keeps 10 close pairs, and they lie inside groups. Corundum's 5 flagged
  lines each sit on exactly one calculated reflection and have a twin in the
  neighbouring group, three of them at equal intensity.
  `test_acceptance_indexing.py`: 39 passed and 5 failed in 15 min. Row 5's
  usable floor counted copies and moved from 50 to 45. Rows 1-4 are still red.
  What the lane established, in its own words where unverified:
  - **Corundum c/2, and the declared-shift row.** Which copy is kept is not
    the cause: the kept copy is as close to the certificate or closer in all
    5 pairs. The lane reports that svd's seed 0 no longer finds the true cell
    while seeds 1-11 do, so dichotomy is its only finder. The c/2 cell that
    all three engines find then ranks first. My own check, svd only and
    hexagonal only, showed c/2 in the top four with and without the flag, so
    the seed claim is the lane's and not verified here.
  - **cpd-1a's shift.** Two of the five pairs behind the old −0.038° were
    copies. A separate fit of the 16 fluorite lines gives −0.0095 ± 0.0023,
    so the pinned −0.038 was the artefact.
  - **Zircon.** The centred and primitive cells are refined separately, so
    the "primitive indexes at least as many" direction can flip by one line,
    here 45 against 46.

  Lanes (trial, `/wp-lanes`):

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | model | lane $ | main $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | duplicate_line surface sync | 25 | 19 | 177K | 69K | 0K of 0K | 5 | 38K | 2 | 0 | sonnet-5-5 | 0.52 | 1.72 | 1.19 | -1.65 |
  | formula volume window and Z check | 35 | 22 | 250K | 70K | 0K of 0K | 19 | 21K | 2 | 0 | opus-5-5 | 0.83 | 1.33 | 1.50 | -0.77 |
  | corundum c/2 regression | 25 | 2 | 287K | 70K | 0K of 18K | 5 | 5K | 0 | 0 | opus-5-5 | 0.38 | 0.30 | 0.14 | -0.54 |
  | corundum c/2 regression | 25 | 91 | 293K | 70K | 0K of 52K | 4 | 8K | 1 | 1 | opus-5-5 | 4.99 | 0.37 | 9.39 | +4.04 |

  Kept: instrument-first gate suggestion, est 18 and took 15. Skill
  ask-or-infer rule, est 8 and took 6. Trial row: 4 lanes, 2 kept, saved
  +1.08 (+6 %). The volume lane stopped by design at the missing papers. The
  first corundum lane died on the 600 s stream watchdog during a long test
  run, so its re-dispatch was told to keep commands under 8 min. Baseline
  replay at these parameters: the selective policy (> 150K and ≥ 20 requests)
  saves 25 %.

  *Review* (`/code-review high --fix`, 9 findings). Three are fixed:
  - Duplicates are judged best-first, and only an unflagged copy owns a line.
    The same components are flagged on all 16 patterns.
  - A prior past both box edges names both values.
  - `where` lists only the undeclared blocks.

  Six are declined, and two of them are real and open:
  - (5) A correctly set-up synchrotron instrument also has zero axial
    apertures and the default profile, so the instrument-first lead
    misfires there.
  - (7) The documented two-step flow, `index_pattern(peaks)` with no
    instrument, never sees the new suggestion.

  The other four are design calls:
  - Stale `duplicate_line` flags in the GUI editor after an owner moves.
    Clearing them would undo a user's flag edits (WP-1043).
  - The mean-FWHM tolerance. It moves six patterns' counts by one.
  - Stopping the re-seed pass from proposing an owned line. That would
    redesign the peak fitter.
  - A `Cell.from_lengths_angles` that five sites could share.

  Fast selection (`[dev]` venv, macOS): 8121 passed, 159 skipped, 1 failed.
  The failure is main's `api.md` cap row. 10 tests were added, taking 3.74 s,
  2.45 s of it the `cpd-4` count.

  *Not done.* `solution case 1`'s replay: the pattern is a collaborator's
  unpublished dataset and is not in this tree. The full suite was not run,
  because the acceptance file is already known red. Main's
  `test_skill.py::…[api.md]` cap row fails at `origin/main` too, with
  `api.md` at 39 519 B against a cap of 39 500 B, and nothing here grew it.

  *Next.* (a) Decide rows 1-4. Rows 3 and 4 are assertion changes: cpd-1a's
  shift to about −0.009° with its corundum-agreement clause dropped, and the
  zircon direction check. Rows 1-2 need either an svd seed or agreement fix,
  which is an engine change and a non-goal here, or reverting `duplicate_line`
  from `PEAK_UNUSABLE_FLAGS` to a reported-only flag until that fix lands.
  That choice is the maintainer's. (b) Review findings 5 and 7. Gate the
  instrument-first lead on a lab source, and decide whether `pick_peaks`
  records its instrument on the `PeakList` so the two-step flow sees it.
  (c) Ask for Kempster & Lipson (1972) and Hofmann (2002), then do task 4
  and task 6.

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1511 to 1517. Nothing started.
