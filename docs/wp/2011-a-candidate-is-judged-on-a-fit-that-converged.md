# WP-2011 — a candidate is judged on a fit that converged

Milestone: unscheduled · Status: 🔄 2026-10-28 — go decided under the maintainer's delegation: Pawley validation, cheapest first, a 15 % reserve; NAC's true cell now validates under `quick`; ready for review (PR #1191)
Track: What fires, and what stays silent
Depends on: 1956 (PR #941 takes the missing count off this fit and edits the same two functions)
Priority: P2 2026-10-27 — `INDEX_IMPURITY_LINES` fires on a true cell's stalled fit, and notebook 03 works around it; #941 landed for WP-1956 on 2026-10-25, the condition the P3 rung waited on

## Goal

The indexer's whole-pattern check fits each candidate by Pawley, so the Rwp
and the unmatched-peak count it reports come from a converged fit. If the
re-measurement on the tree with WP-1956 merged shows the reported fit no longer
matters, this WP closes 🛑 with the numbers.

## Context

**The check.** `validate_by_lebail` (`src/rietx/indexing/workflow.py:334`)
fits a candidate's absence-free lattice group to the whole pattern with the
cell held, through the four stages of `validation_plan` (`:256`: background,
one shift, `w`, then `u v x y`), in **one** Le Bail pass. Its docstring says
"Le Bail rather than Pawley is a cost choice, not a discrimination one"
(`:377`). Measured 2026-10-18, that is false both ways: the two discriminate
differently, and Pawley costs the same below ~450 reflections.

**Why one Le Bail pass stalls.** Le Bail's extracted intensities are frozen
inside each least-squares run, so intensities and profile converge only by
alternating whole passes (WP-1323's context; `RefinementPlan.lebail_passes`).
Pawley refines them in the same solve (`model.forward.PawleyBlock`, WP-0306).

**Measured 2026-10-18** (tree 544245ca, arm64, `[dev]` venv, compiled kernels
on, another session live on the machine; the two modes ran interleaved, so
read ratios, not seconds). The probe is `2011-probe/` beside this file: it
replays `validate_by_lebail` with the fit's `mode` as the only variable, and
reproduced the shipped function's Rwp and counts to the digit before its
Pawley twin was read. Run from the worktree root,
`.venv/bin/python docs/wp/2011-probe/probe_lebail_vs_pawley.py all`, then
`probe2_… seeds|scale|truths`, `probe3_plain_fits.py`, `probe4_lebail_passes.py`;
outputs go to `$WP2011_OUT` (default: the temp dir).

*Wrong cells.* Synthetic LaB6 (`tests/test_indexing_consensus.py`'s pattern,
true background 29.7 counts), ranges over noise seeds 11-15; magnetite's P
rival from the indexer's own run (`tests/data/qarr/magnetit.prn`).

| candidate | refl. | bkg, Le Bail | bkg, Pawley | missing, Le Bail | missing, Pawley |
|---|---|---|---|---|---|
| true LaB6 | 28 | 27.6–27.7 | 28.5–28.6 | 0 | 0 |
| doubled | 153 | 26.0–26.3 | 28.4–28.6 | 112–123 | 121–123 |
| a×√5 | 204 | 20.4–20.9 | 28.5–28.7 | 12–44 | 167 |
| a +1 % | 30 | −1.2 to −0.3 | 29.2–29.4 | 0 | 19–30 |
| magnetite P rival | 163 | −5.8 | 13.8 | 0 | 3 |

The Le Bail background falls with the wrongness of the cell; Pawley's stays
within 2 counts of the truth on every LaB6 candidate. On the magnetite rival
Pawley's fitted intensities at the phantom positions are 0–2 against 50–743 for
real lines, but `absent_reflections` still reads 3 of 163: its 3σ test over
±0.5 FWHM reads a background a few counts under the data as intensity
(`debug_absent.py`). That is WP-1956's input problem, not this WP's.

*True cells, real data* (each cell refined once by an ordinary Le Bail fit from
its literature value, then judged by both modes):

| dataset | refl. | missing LB / P | unmatched LB / P | Rwp LB / P |
|---|---|---|---|---|
| SRM 660c | 30 | 0 / 0 | 15 / 13 | 0.099 / 0.093 |
| NAC | 837 | 0 / 20 | 184 / 170 | 0.155 / 0.126 |
| FAP | 216 | 5 / 7 | 76 / 5 | 0.210 / 0.079 |
| corundum | 85 | 11 / 7 | 43 / 10 | 0.223 / 0.138 |
| brucite | 43 | 2 / 2 | 9 / 11 | 0.172 / 0.167 |
| zincite | 36 | 4 / 4 | 11 / 7 | 0.124 / 0.105 |
| zircon | 98 | 6 / 5 | 60 / 11 | 0.267 / 0.147 |
| fluorite | 18 | 0 / 0 | 4 / 4 | 0.190 / 0.179 |
| magnetite | 52 | 3 / 3 | 4 / 4 | 0.210 / 0.180 |

On SRM 660c, FAP, corundum and zircon the Le Bail pass leaves a width on its
floor (`FLOOR_HIT`: `y`, and `w` too on zircon); FAP's peaks lose their
Lorentzian tails, and those tails are the 76 unmatched peaks. Pawley's fits hit
no floor. NAC's 20 are false: I2₁3 has no absences beyond the centring (283
positions either way), and they are real reflections the published structure
makes weak (0.03–1.5× the median intensity, all above 40° 2θ). Pawley's
background (300.2) matches a Rietveld fit with that structure (302.9); Le
Bail's (278.1) is low, and that is the only reason it passes them
(`debug_nac.py`).

*Converged Le Bail is ruled out* (`lebail_passes` 5 and 10, `probe4_…`). The
a×√5 and +1 % cells did not move; the magnetite rival's background fell from
−5.8 to −21.7. On true cells corundum stayed at Rwp 0.221 after 10 passes (Pawley
0.138 in one), FAP reached 0.110 in 5.6 s (Pawley 0.079 in 0.46 s), NAC took
16.6 s (Pawley 5.3 s). Slower than one Pawley pass everywhere.

*Cost* (one pass each; seconds over 2-3 repeats):

| reflections | Le Bail | Pawley | ratio |
|---|---|---|---|
| 18–216 (the lab cells) | 0.05–0.7 | 0.04–0.5 | 0.7–1.7, mixed |
| 442 | 0.45–0.47 | 0.44–0.46 | 1.0 |
| 837 (NAC, 11-BM) | 1.8–1.9 | 5.3–5.8 | 3.1 |
| 978 | 0.98–1.04 | 1.58–1.63 | 1.6 |
| 1823 | 1.85–1.98 | 7.84–7.98 | 4.1 |

`engines.MEASURED_VALIDATION_SECONDS` (`engines.py:2376`, 0.6-44 s) prices
validation in `estimate_ceiling` and under the quick preset's slices, and it was
measured for Le Bail.

**What WP-1956 changes first.** Decided 2026-10-14 and built by PR #941 (open,
round 2): with a peak list, `predicted_but_absent` comes from a
candidate-independent line screen (`indexing/screen.py`) and no longer reads
this fit; the count caps rather than refutes; the fit keeps the forward
question (`unmatched_observed`, hence `INDEX_IMPURITY_LINES`) and an Rwp for a
reader, and gains `freeze_profile` (a shared declared profile, off by default:
SRM 660c at Rwp 0.57 frozen against 0.10 free, #941's measurement). Without a
peak list the count is still this fit's (`absent_source="fitted_background"`).
So after #941 this WP reaches: the unmatched count and `INDEX_IMPURITY_LINES`
on true cells; the Rwp a reader sees, in the result and the GUI's candidate
row; the no-peak-list path, where NAC's 20 would still appear; and
`validation_failed`. Notebook 03 already works around the first two ("the
indexer's own quick Le Bail fit, whose Rwp in the candidate's row is poor. A
poor fit leaves many peaks unmatched").

**A declared name is a claim** (root CLAUDE.md): `validate_by_lebail`,
`LeBailValidation`, `CellCandidate.lebail`, `lebail_rwp` and
`INDEX_IMPURITY_LINES`'s "after a whole-pattern Le Bail fit" would all name a
fit that is no longer Le Bail. The field's term for both methods is whole
powder pattern decomposition (Le Bail 2005).

**Practice.** Kariuki *et al.* (1999) tested cell hypotheses with Le Bail fits
in a genetic-algorithm indexer, "faster than with the Pawley method" (as cited
by Le Bail 2005, §VI p.321; checked 2026-10-18). Le Bail (2005, §IV.B
p.318; this file said §II.B until 2026-10-27): the method "requires as good
starting cell and profile parameters as the Rietveld method itself", and a
wrong candidate is a bad start. **Checked 2026-10-27** (WP-2062's survey,
`docs/practice.md` § Structure-free fitting): GSAS-II re-extracts once per
least-squares iteration (`GSASIIstrMath.py:4808`), FullProf once per cycle
(ran), and TOPAS, RIETAN-FP and MAUD inside the refinement too, where rietx
re-extracts only between runs. So the gap above may be rietx's Le Bail
rather than the method; WP-2062 carries that as its decision 0. TOPAS
defaults to Pawley. No paper compares the two as cell validators.

### Re-measured 2026-10-27, on the tree with #941

`probe5_after_941.py` calls the shipped `validate_by_lebail` and swaps only
the fit's mode, by wrapping `Refinement.fit`. Tree `feae4c75` (main after
#941), arm64, `[dev]` venv, compiled kernels on. Another session's suite held
about ten cores throughout, so the seconds below are ratios at best.

*True cells, the indexer's path* (picked peaks, widths free; the cells are
probe 2's, refined once by an ordinary Le Bail fit):

| dataset | refl. | unmatched LB / P | Rwp LB / P | width on its floor, LB / P |
|---|---|---|---|---|
| SRM 660c | 30 | 15 / 13 | 0.099 / 0.093 | — / — |
| NAC | 837 | 184 / 170 | 0.155 / 0.126 | — / — |
| FAP | 216 | 13 / 5 | 0.140 / 0.079 | — / — |
| corundum | 85 | 21 / 12 | 0.172 / 0.137 | `w` / — |
| brucite | 43 | 9 / 11 | 0.172 / 0.167 | — / — |
| zincite | 36 | 11 / 7 | 0.124 / 0.105 | — / — |
| zircon | 98 | 44 / 11 | 0.225 / 0.147 | `w` / — |
| fluorite | 18 | 4 / 4 | 0.190 / 0.179 | — / — |
| magnetite | 52 | 4 / 4 | 0.210 / 0.180 | — / — |

The absent count is identical under both modes on every row with a peak
list: it is the line screen's since #941, as designed. Le Bail improved
since 10-18 on FAP (76 unmatched with `y` on its floor, now 13 with no
floor), corundum (43 → 21) and zircon (60 → 44); the tree moved under it
(#941's width seeding, WP-2002's edge margin and emission lines), and this
probe did not separate which. Pawley's corundum count moved 10 → 12.

*Wrong cells, the indexer's path:*

| candidate | refl. | unmatched LB / P | Rwp LB / P | background LB / P |
|---|---|---|---|---|
| LaB6 doubled | 153 | 0 / 0 | 0.354 / 0.164 | 25.6 / 28.4 |
| LaB6 a×√5 | 204 | 4 / 4 | 0.850 / 0.233 | 19.1 / 28.5 |
| LaB6 +1 % | 28 | 22 / 23 | 1.008 / 0.503 | 27.4 / 29.2 |
| magnetite P rival | 163 | 25 / 2 | 0.646 / 0.174 | −7.3 / 13.8 |

(LaB6 true background 29.7; its true cell reads Rwp 0.234 / 0.164.) The
magnetite rival indexes every line the true F cell does, so its unmatched
count should equal the truth's 4: Pawley's 2 is near it, Le Bail's 25 is
its sunk background. Pawley's Rwp ties the doubled cell to the truth
(0.164 both) and puts the P rival at 0.174 against 0.180: a converged
decomposition of a cell predicting every reflection of the truth's fits at
least as well.
**So the rival/truth Rwp gap the acceptance rows pinned (> 2×) was the
stall.** Two rows assert it (`test_acceptance_indexing.py`: magnetite's,
now inverted to < 1.05×, and the calibrated LaB6's a·√2 rivals). The second
stands under Pawley: an a·√2 cubic cell misses the truth's lines whose index
sum doubled is not a sum of three squares, (321) among them, so its fit is
worse for the lattice's sake and still reads over twice the truth's Rwp.

*No peak list* (`absent_source="fitted_background"`, reached only by a
direct call): Pawley's honest background reads more absences on wrong
cells (+1 % 0 → 14, a×√5 59 → 167, magnetite rival 0 → 3) and on two true
cells (NAC 0 → 20, the weak real reflections § Context names; FAP 4 → 7),
fewer on corundum (11 → 7) and zircon (8 → 5).

*`freeze_profile=True`*: frozen is worse than free under both modes
(SRM 660c Rwp 0.575 / 0.456 against 0.099 / 0.093), so it stays off.
Frozen Pawley is the more stable of the two (FAP unmatched 164 / 31).

*Notebook 03's candidate* (aragonite, the tutorial's search): Pawley
validates it at Rwp 0.044 with 0 unmatched, where the tutorial's own two
Le Bail passes reach 0.053. The `INDEX_IMPURITY_LINES` the notebook used to
explain away no longer fires.

*Cost* (`probe6_cost.py`: the acceptance suite's searches, `preset="full"`,
with every candidate the indexer validated timed under both modes, order
alternating; machine load 50-100 from another session's suite, so ratios
only):

| dataset | fits | reflections | Pawley / Le Bail, median (range) |
|---|---|---|---|
| corundum | 4 | 43-122 | 0.91 (0.23-1.11) |
| zincite | 3 | 36-84 | 0.89 (0.86-1.19) |
| zircon | 3 | 98-197 | 1.24 (1.23-2.37) |
| FAP | 3 | 216-364 | 0.97 (0.77-4.02) |
| SRM 660c | 10 | 30-71 | 1.04 (0.92-1.54) |
| magnetite | 2 | 52-163 | 1.00 (0.98-1.03) |
| NAC | 2 | 837, 1668 | 2.6, 12.6 (19.4 s against 7.5; 107 s against 8.5) |

cpd-1a, whose one 44 s fit set `MEASURED_VALIDATION_SECONDS`' top, returned
no candidate on this tree, so nothing of it was validated. On corundum's c/2
subcell candidates one Le Bail pass ran away (Rwp 5.5-6.2, one at
`max_iter`) where Pawley reached 0.38. On 10-18, idle, NAC's 837 cost 3.1×
and 1823 cost 4.1×, so the load inflates Pawley's large fits more than Le
Bail's. `probe7_idle_cost.py` re-timed them; the machine was quiet (load 5)
for its first run only, and that run's wrapper timed Pawley in both columns
(fixed in `81f8e37e`), so its early readings are Pawley's quiet costs:
NAC's 837 reflections 5.3-5.5 s, and the 1668 of its primitive description
25.0-25.5 s in two repeats before the load came back (the third took 109 s,
and the FAP and corundum readings after it are loaded too). The corrected
run met load 23-56:

| case | refl. | Le Bail s | Pawley s |
|---|---|---|---|
| NAC, I | 837 | 5.7-10.3 | 15.7-22.7 |
| NAC, P | 1668 | 4.1-7.6 | 32.9-88.6 |
| FAP | 216 | 0.85-0.87 | 0.64-0.69 |
| corundum | 85 | 0.20-0.21 | 0.24 |

So on a quiet machine Pawley costs about 3× at 837 reflections (Le Bail
1.8 s on 10-18) and about 5× at 1668, and a shared machine multiplies that
again. **What this means for a user**: under `preset="full"` a large
synchrotron pattern's validation takes longer and still completes. Under the
default `quick` preset each validation fit draws a slice of a whole-run
ceiling, and a slice that expires leaves its candidate `not_validated`,
which caps the grade at `medium`. So on a large low-symmetry pattern under
`quick`, Pawley can validate fewer candidates than Le Bail did. Not
measured: that needs `index_pattern` under `quick` on a large pattern in
both modes, on a quiet machine. The bethanechol benchmark runs `full` and
cannot see it. `MEASURED_VALIDATION_SECONDS` keeps its value (0.6, 44.0),
which brackets the quiet NAC fits; its comment says so.

**The provisional go (Claude, 2026-10-27, maintainer away).** Criterion: on
the path the indexer runs, does the Pawley fit answer the forward question
(is there a reflection under every observed peak) better? Evidence above:
no true cell leaves a width on its floor, the impurity count on true cells
falls (zircon 44 → 11, FAP 13 → 5, corundum 21 → 12; brucite +2), and a
nested rival's count becomes right. Against it: the Rwp cue a reader saw
on supercells is gone, and the fit costs more on large patterns
(§ Cost below). What reverses it: the acceptance suite losing a ranking,
or the bethanechol benchmark validating fewer candidates than `main`.
**Acceptance bar, read honestly:** FAP 5, zircon 11 and no `FLOOR_HIT` meet
it; corundum's 12 misses "at most 11" by one. That bar was Pawley's own
10-18 worst (5, 10, 11) with no margin.

### Re-measured 2026-10-28, under `quick`

Tree `938a635e` (this branch), arm64, `[dev]` venv, compiled kernels on.
Load average 3-7 on ten cores; one other Claude session was open and idle,
and no suite ran.

**The bethanechol benchmark cannot see this question.** It hands
`index_pattern` a position-only `PeakList` and no pattern
(`tests/bethanechol_benchmark.py`, `run_one`), so no candidate is ever
validated, in either mode. The acceptance bar "validates no fewer
candidates than on `main`" was empty there from the start.

*`quick` in both modes* (`probe8_quick.py`). `index_pattern` as a first
click runs it, with only `workflow.VALIDATION_MODE` swapped, so the
extinction screen's own Le Bail fits are the same in both columns. "acc."
is the acceptance suite's spec with the per-unit budget left at its
default; "default" is `SearchSpec()`, every system. Validated counts the
candidates whose record is not `None`.

| case | spec | validated, Le Bail / Pawley | ceiling hit | seconds, LB / P |
|---|---|---|---|---|
| 11-BM NAC | acc. (cubic) | 2 / 2 | no | 90 / 112 |
| 11-BM NAC | acc., all seven systems | **3 / 0** | yes | 123 / 123 |
| 11-BM NAC | default | **1 / 0** | yes | 123 / 125 |
| FAP | acc. | 3 / 3 | no | 20 / 22 |
| FAP | default | 3 / 3 | yes | 119 / 121 |
| SRM 660c | acc. | 10 / 10 | no | 32 / 32 |
| corundum | acc. | 4 / 4 | yes | 117 / 116 |
| zincite | acc. | 3 / 3 | no | 12 / 12 |
| zircon | acc. | 3 / 3 | no | 20 / 20 |
| zircon | default | 3 / 3 | yes | 119 / 120 |
| magnetite | acc. | 2 / 2 | no | 3 / 3 |

So the condition the maintainer set for merging fails on NAC. When the
search runs to the ceiling, it stops `VALIDATION_RESERVE_FRACTION` (8 %,
9.6 s) early, a reserve sized for three Le Bail fits of 1.9 s. Three
Pawley fits of NAC-sized cells cannot finish in it, and every slice
expired. On the lab patterns the counts are equal. What a user sees on NAC
under Pawley: no candidate row carries an Rwp or an unmatched count, and
`INDEX_BUDGET_EXHAUSTED` names the unvalidated candidates. The grades did
not move: every NAC candidate read `low` in both modes, below the
`medium` cap an unvalidated candidate takes. Two runs ended a validation
at `max_iter`: Le Bail's on corundum's c/2 subcell (Rwp 5.5) and Pawley's
on FAP's 525 Å³ rival (Rwp 0.356).

*Why, and whether a larger reserve helps* (`probe10_reserve.py`). The
candidates NAC's default-spec search checks when it runs to completion
(`preset="full"`), each validated with no deadline (load 4-5):

| candidate | reflections | Le Bail s | Pawley s |
|---|---|---|---|
| tetragonal P, 269 Å³ | 1241 | 1.5 | 11.2 |
| orthorhombic P, 135 Å³ | 1223 | 1.4 | 11.5 |
| monoclinic P, 135 Å³ | 2224 | 2.4 | **379** |

All three are wrong subcells of NAC's I cell, and all three Pawley fits
converged. Pawley's cost rises far faster than the reflection count: ×1.8
in reflections costs ×33 in seconds. The LM driver's exact BVLS step stops
at 128 columns (`lm.BVLS_MAX_COLUMNS`), so above it the cost is elsewhere.
`probe11_profile.py` profiled two of them under `cProfile`:

| candidate | reflections | seconds | last stage's iterations | projected CG, s a call | dense JᵀJ, s a call |
|---|---|---|---|---|---|
| orthorhombic P | 1223 | 12.0 | 10 | 0.08 | 0.23 |
| monoclinic P, β 90.003° | 2224 | 377 | 89 | 2.4 | 0.81 |

In the monoclinic fit, projected CG took 246 s (65 %) and forming the
dense normal matrix 83 s (22 %). The monoclinic cell is the orthorhombic
one with β freed by 0.003°, so nearly every reflection has a partner
within a fraction of a width. A pseudo-symmetric description of this kind
is a routine member of an indexing shortlist. Its intensity block is
nearly singular, and the solve needs nine times the iterations at thirty
times the cost each. Both factors are solver properties: the normal
matrix is formed dense although each intensity column is nonzero only
under its own peak, and CG's cost tracks the conditioning. Neither is
fixed here.

The reserve, swept under `quick` and Pawley:

| case | 0.08 | 0.2 | 0.3 | 0.4 |
|---|---|---|---|---|
| NAC default: validated | 0 | 1 | 1 | 1 |
| NAC all seven: validated | 0 | 2 | 3 | 3 |
| NAC default: systems searched | 5 | 4 | 4 | 4 |
| corundum: validated / systems | 4 / 4 | 4 / 4 | 4 / 4 | 3 / 3 |
| FAP default: run seconds | 121 | 107 | 97 | 84 |
| zircon default: run seconds | 119 | 105 | 93 | 81 |

A larger reserve buys NAC's cubic I its validation from 0.2 (Rwp 0.126).
It never validates the whole shortlist, because one 2224-reflection fit
outlasts any slice. On the lab patterns the reserve goes unused: the runs
end that much earlier with the same answer, and at 0.4 corundum loses its
tetragonal search and one validated rival. So raising the reserve is no
fix.

*The three Pawley constants on the validation's readings*
(`probe9_constants.py`, ruling 3's sweep). The shipped validation, peak-list
path, on the fourteen cells of probe 5 (nine real true cells; synthetic
LaB6's truth and its doubled, a×√5 and +1 % cells; magnetite's P rival),
fifteen runs a variant since magnetite's truth runs twice, varying one thing
at a time:

| variant | unmatched count or status moved | largest Rwp move |
|---|---|---|
| `PAWLEY_OVERLAP_FWHM_FRAC` 0.25 | none of 15 runs | 0 |
| `PAWLEY_OVERLAP_FWHM_FRAC` 1.0 | none | 1e-4 (FAP) |
| `PAWLEY_OVERLAP_LAMBDA` 0.1 | none | 0 |
| `PAWLEY_OVERLAP_LAMBDA` 10 | none | 7e-4 (corundum, 0.1371 → 0.1378) |
| intensity and σ ÷ max count | none | **0.098 (synthetic LaB6 truth)**, else ≤ 2e-4 |

The overlap fraction does change which reflections are grouped (zircon
12, 24 and 30 grouped reflections at 0.25, 0.5 and 1.0). The readings do
not follow. On the scaled patterns the off-data floor binds: the ridge's
scale falls to 0.005-0.09 on NAC, FAP, corundum and zircon and to 0 on
LaB6's wrong cells, and none of their readings moved. The audit rows were
re-grounded on this (ruling 3).

**A unit dependence the floor does not explain.** Synthetic LaB6's true
cell validates at Rwp 0.164 on counts and 0.262 with the pattern and σ
divided by the maximum count (2721). χ² is the same function in both, and
Le Bail reads 0.2339 and 0.2338. The Pawley fit's widths differ (`u`
1e-5 against −4.3e-4, `y` −1.9e-4 against −1.3e-3), and the divergence
starts in the zero-shift stage. Against an intensity factor *f*: Rwp
0.164 for *f* ≥ 1, 0.171 at 0.1, 0.266 at 0.01 and 0.001, and at 1e-4 the
last stage ends at `max_iter` (Rwp 0.200). Ruled out: the off-data floor
(no off-data reflection in this fit; the floor at 1e-12 reads the same),
the LM driver's curvature probe (disabled, the same), and the re-picked
peak list (the base list reads the same). Not found. It belongs to
WP-2062, where Pawley becomes the structure-free default: a Pawley fit
whose answer depends on the intensity units is wrong on count-rate and
normalised exports. On the nine real true cells no scaled reading moved by
more than 2e-4.

**Found on the way.** `validate_by_lebail` raises numpy's `ValueError:
array of sample points is empty` (`screen.fwhm_at`) when handed a peak list
with no usable peak. The picker returns one on a pattern divided by its
maximum with no σ column, where the Poisson fallback √max(y, 1) puts every
point under the noise. `index_pattern` stops before validating on such a
list, so only a direct call reaches it. For WP-1956's screen, unfixed here.

### Option (c) probed 2026-10-28: a sparse, preconditioned Pawley solve

The maintainer asked for option (c) to be tested, and for the ways to make
Pawley cheaper to be assessed. Indexing may be a little looser than
Rietveld. Probes 12-15 ran against a scratch patch of this branch
(`probe12_switches.patch`), on a quiet machine, macOS arm64, `[dev]`, 11-BM
NAC every second point (59 498 points). Times are single runs.

*The 2224-reflection monoclinic candidate* (`probe12_sparse.py`):

| variant | seconds | last-stage iterations | CG products | Rwp | unmatched / absent |
|---|---|---|---|---|---|
| dense (as shipped) | 376 | 89 | 417 821 | 0.12591 | 170 / 16 |
| A = JᵀJ formed sparse | 163 | 62 | 298 381 | 0.12591 | 170 / 16 |
| sparse + incomplete-LU preconditioned CG | 39.8 | 13 | 3 266 | 0.12592 | 170 / 16 |
| the same, sparsity pattern read once a stage | 37.5 | 13 | 3 266 | 0.12592 | 170 / 16 |
| the same, exact LU instead of incomplete | 57.7 | 15 | 3 233 | 0.12591 | 170 / 16 |
| merge each 0.5-FWHM overlap group into one intensity | 15.8 | 8 | 701 | 0.1362 | 170 / 16 |
| merge at 0.1 FWHM | 30.4 | 15 | 9 325 | 0.13219 | 170 / 16 |
| merge at 0.02 FWHM | 85.7 | 16 | 59 941 | 0.12634 | 170 / 16 |

J is 2.5 % nonzero and JᵀJ 8 %. Each intensity column spans about 1411
points (±0.7°: the 0.3° capture slack plus k·Γ at the start widths). Formed
sparse, A costs less to build and each Hessian product 2.2× less. That alone
does not fix the solve: each step still spends about 4000 CG products,
close to the 2n budget, so the steps are poor and the last stage needs 62-89
iterations. Preconditioning fixes the conditioning. With it a step takes
about 120 products and the stage 13 iterations. The incomplete LU is
scipy's `spilu` at its defaults (drop tolerance 1e-4, fill factor 10), so it
adds no constant. The exact LU fills in and costs more. Lin & Moré (1999),
the method `projected_cg` follows, precondition the same way with an
incomplete Cholesky factor. Refactoring on every change of the free set
(1543 factorisations) and once per step solve (49) gave the same answer in
37.5 s and 34.2 s; the second worsened one stage's steps (11 iterations
against 2), so the lane kept the paper's policy.

Merging changes the model: a group's members are forced to an equal split.
Coarse merges are fastest and move Rwp; tight ones barely help, because
the near-singular pairs are not the only ill-conditioning.

*Do the cheaper solves change a verdict?* (`probe13_variants.py`, probe 5's
cells: nine real true cells, synthetic LaB6's truth and three wrong cells,
magnetite's truth and its P rival.) Preconditioned sparse: every Rwp to four
decimals, unmatched count, absent count and status identical on all 15 runs,
and on NAC's 1223- and 1241-reflection candidates. Merging at 0.5 FWHM: one
reading moved, zircon's unmatched 11 → 12 (Rwp 0.1474 → 0.1508); Rwp moved by
under 1e-3 on magnetite's two cells and FAP; nothing else moved. On NAC's true
cubic I cell merging cuts 849 columns to 299 at an unchanged Rwp: most of the
cut is exact coincidences, distinct reflections at one d-spacing. Dropping the
esds changed nothing and saved up to 6.5 s of the monoclinic fit's 37.

*Well-conditioned fits do not gain.* Preconditioned and sparse, the
orthorhombic candidate took 12.2 s against 12.0 dense, the tetragonal 12.6
against 11.1, and NAC's true cell 7.4 against 5.9. Below about 1000 columns
Apple's dense BLAS forms JᵀJ about as fast as the sparse product, and the
factorisations cost more than they save.

*Under `quick` the fast solve does not rescue the go* (`probe14_quick_solver.py`,
the sparse preconditioned variant): NAC default spec and all seven systems
each still validate **0** of 12 candidates. The search leaves its 9.6 s
reserve, split among the checked candidates, so a slice is 2-3 s. Every NAC
candidate's Pawley fit costs more than that, the true cell included, and Le
Bail's 1.4-2.4 s fits inside it.

*Where the true cell's 5.8 s goes* (`probe15_profile_true.py`, dense, 837
reflections, 849 columns): forming JᵀJ 2.17 s (37 %, 20 builds), building
the dense J 1.10 s, recompiling the model at each of four stages 0.95 s
(`generate_reflections` 0.89 s of it, for a cell the plan holds), the esds
and residual angles 0.77 s, the step solves 0.35 s.

*Assessment*, by what each buys on NAC and what it costs:

- **Sparse, preconditioned step solve** (built by this session's lane). Fixes
  the pseudo-symmetric outlier 10× with no reading moved, and serves
  WP-2062's Rietveld-grade Pawley as much as indexing. Alone it does not
  make `quick` validate NAC.
- **Normal equations from the window pattern.** The lane builds A from the
  frozen windows instead of a dense product, which should take most of the
  2.17 s off a well-conditioned fit. Not yet measured in the tree.
- **No esds in a validation fit** (0.77 s of 5.8). A validation reads none.
  Needs a way through `fit` to `run_least_squares(compute_uncertainties=…)`.
- **Reflections generated once for a held cell** (0.89 s). Every stage of a
  validation recompiles the same cell. A cache keyed on cell, group and range
  would also serve the extinction screen's per-class fits.
- **Merge exact coincidences** (indexing-grade). An intensity per distinct
  d-spacing loses nothing the data can resolve: NAC's true cell 849 → 299
  columns, Rwp unchanged. Merging near-coincidences at 0.5 FWHM is faster
  still and moved one of 15 verdicts.
- **A dense J never built** (1.1 s, and 1.1 GB a build on the 2224
  candidate). The largest remaining cost after the above, and the widest
  change: every consumer of `LSQOutcome.jac` reads a dense array.
- **The reserve.** Ruled out at a fixed fraction in probe 10, while one fit
  cost 377 s. With that fit at 37 s, a reserve sized to the shortlist's
  measured cost may be worth re-measuring.

*On the tree* (commit e39b8c19d, built by a lane from the prototype). A
Pawley stage above the BVLS cut gathers its intensity block over the frozen
window pattern into CSC, and `projected_cg` preconditions a sparse H with
`spilu` at scipy's defaults, refactored when the free set changes. Past
`PAWLEY_SPARSE_DENSITY` (0.05 of the block nonzero) the stage keeps the
dense build: banded sparse products break even with BLAS there, at 5995 ×
343 and at 59 498 × 2224, and FAP.XRA's closing stage sits at 0.38 on its
1e-3 windows. Measured:

| case | dense | tree | readings |
|---|---|---|---|
| NAC monoclinic, 2224 reflections | 376 s | 34.1 s | Rwp 0.12591 → 0.12592, 170 / 16 |
| NAC tetragonal, 1241 | 11.1 s | 10.5 s | unchanged |
| NAC orthorhombic, 1223 | 12.0 s | 8.9 s | unchanged |
| NAC true cubic I, 837 | 6.0 s | 4.8 s | unchanged |
| probe 5's other 14 cells | 0.07-0.57 s | 0.07-0.65 s | unchanged, all 14 |
| FAP.XRA Pawley fit, 343 columns | 1.1 s | 1.3-1.4 s | Rwp 0.0786244 both |

`index_pattern` under `quick` on NAC, both modes, quiet machine
(`probe8_quick.py` on the tree):

| case | Le Bail validated | Pawley validated |
|---|---|---|
| NAC default spec | 0 of 12 (probe 8: 1) | 0 of 12 |
| NAC all seven systems | 2 of 12 (probe 8: 3) | 0 of 12 |

So the go's condition still fails. Le Bail's count moved between two runs of
the same tree under the wall-clock ceiling. Neither mode validated NAC's true
cubic I cell in this run, which sits second on both shortlists.

## Non-goals

- The missing count's inputs and the grade (WP-1956).
- The extinction screen's per-class Le Bail fits (`extinction.py:756`, `:866`;
  WP-1910 in flight): a sibling, unmeasured, with a shared profile of its own.
- The GUI's adopt-a-candidate Le Bail fit, and the tutorials' ordinary Le Bail.
  Measured for whoever takes the tutorials: `profile_only` Le Bail converged
  more slowly than `pawley_default` on three lab patterns over three passes
  (corundum 0.234 → 0.179 with `y` still on its floor, Pawley 0.152 → 0.139;
  FAP 0.130 → 0.085 against 0.083 → 0.078; zircon 0.184 → 0.172 against
  0.172 → 0.149; `probe3_plain_fits.py`).
- A refinement's Le Bail background left at its seed (WP-1542).

## Tasks

- [x] Re-measure on the tree with #941 merged: the probe adapted to its
      signatures, both modes, the true and wrong cells above and the
      no-peak-list path, plus `freeze_profile=True` under each mode
      (`probe5_after_941.py`, § Re-measured 2026-10-27).
- [x] **Decision (maintainer):** go or no-go, recorded as `Decided
      YYYY-MM-DD:`. Built provisionally as a go on 2026-10-27 while the
      maintainer was away; § Re-measured 2026-10-27 has the case and what
      reverses it. **Decided 2026-10-28, conditionally:** measure `quick` on
      NAC and a bethanechol set in both modes first, and merge if no
      candidate goes unvalidated. **The condition failed** (§ Re-measured
      2026-10-28): Pawley validated none of NAC's candidates where Le Bail
      validated one to three, and the bethanechol benchmark never validates.
      So the PR did not merge, and the go is back with the maintainer, with
      probes 10 and 11's cause and options. **Decided 2026-10-28 (3rd
      session), under the maintainer's delegation** ("consider a user's needs
      … use your best judgement"): **go**, with validation cheapest first and
      a 15 % reserve, which validates NAC's true cell under `quick` (the 2026-10-29
      handover entry).
- [x] Option (c), asked for 2026-10-28: the Pawley step solve in sparse form,
      its projected CG preconditioned by an incomplete LU above the BVLS cut,
      and A built from the frozen window pattern (probes 12-15, § Option (c)
      probed). Then `quick` on NAC again. *Done 2026-10-28* (§ Option (c)
      probed, "On the tree"): 376 s → 34 s on the outlier, no reading moved
      on 15 cells, and `quick` on NAC still validates 0 of 12 under Pawley.
      One new tier-3 row, `PAWLEY_SPARSE_DENSITY`, rests on the B10 class
      ruling and needs the maintainer's confirmation. *Confirmed 2026-10-28
      (3rd session)* under the delegation, once its unmeasured case was built.
- [x] Option (f), asked for 2026-10-28 (3rd session): spend `quick`'s
      validation reserve differently. Measured (probes 16-21): no schedule
      helped, because on NAC the reserve was spent before validation began
      (filed as WP-2063). Built: fits cheapest first on the run's clock, and
      the reserve 8 → 15 %.
- [x] The case the generality review called unmeasured: an ill-conditioned
      Pawley stage past `PAWLEY_SPARSE_DENSITY` (probe 17). Built: the dense
      step's exact Cholesky factor, shifted where singular, and a projected
      search (Lin & Moré 1999), lane-implemented.
- [x] **Decision (maintainer):** the names above, kept with the mode recorded
      on the validation record or renamed to the field's term, staged in the
      release record either way (ROADMAP rule 6). Built provisionally as
      *kept, mode recorded* (`LeBailValidation.mode`). **Decided 2026-10-28:**
      kept for now; the rename is decided inside WP-2062, so the names break
      once.
- [x] Switch `validate_by_lebail`'s fit to `mode="pawley"`, record the mode on
      the validation record, and rewrite the `:377` paragraph with the numbers.
- [x] **Decision (maintainer, with the generality review):** the three tier-3
      Pawley constants (`PAWLEY_OVERLAP_FWHM_FRAC`, `PAWLEY_OVERLAP_LAMBDA`,
      `PAWLEY_OFF_DATA_SCALE_FLOOR`, `_audit.py:1868-1890`) are kept on the
      grounds "opt-in Pawley mode". The switch puts Pawley on every
      `index_pattern` call that validates, so for that path the ground no
      longer holds. Re-ground them (the validation reads Rwp and the
      unmatched count, and neither depends on how an overlapped group is
      split) or re-tier them. Not edited here: a tier-3 ground needs the
      maintainer's dated approval. The generality review (2026-10-27, in the
      handover entry) adds that `PAWLEY_OVERLAP_FWHM_FRAC` was already on a
      default path before this branch: the peak picker reads it
      (`indexing/pick.py:492-565`, `indexing/peaks.py:42, 308`). It rated
      the first two **weak** (mechanism plausible, no sweep on the
      validation's readings) and the off-data floor **cannot tell** (it may
      bind on a pattern scaled to a maximum of 1). **Decided 2026-10-28:**
      sweep, then re-ground. Swept (§ Re-measured 2026-10-28, probe 9): no
      unmatched count or status moved under any variant, and all three rows
      now name the default path, the sweep and the 2026-10-28 approval, tier
      3 and values unchanged.
- [x] Re-measure `MEASURED_VALIDATION_SECONDS` under Pawley, and run
      `python -m tests.bethanechol_benchmark` alone against `main`'s count of
      validated candidates (the large monoclinic cost case). *Half done
      2026-10-27:* re-timed (§ Cost), value kept with a comment. The
      benchmark was not run: it needs two runs of tens of minutes alone on a
      machine other sessions kept loading, it records no `main` count to
      compare with, and under its `preset="full"` every checked candidate is
      validated whatever the fit costs. The risk § Cost names is under
      `quick`, so the measurement owed is `index_pattern` under `quick` on a
      large pattern (NAC, a bethanechol set) in both modes, quiet machine.
      *Done 2026-10-28* (probes 8, 10, 11): the benchmark passes no pattern
      and so validates nothing in either mode, and the `quick` measurement
      is in § Re-measured 2026-10-28. `MEASURED_VALIDATION_SECONDS`' top
      (44 s) does not bracket Pawley's 377 s on NAC's monoclinic subcell;
      left until the go is decided, since the fix decides the number.
- [x] Tests: `test_le_bail_validation_separates_the_failure_modes` (its +1 %
      row asserts 0 missing, which is Le Bail's blindness; Pawley reads
      19-30), the magnetite acceptance row's regenerated negative background,
      `tests/test_acceptance_indexing.py` green; obs/calc/diff PNGs to
      `tests/output/`. Acceptance 44 passed, 0 skipped, 0 failed (20 min,
      `[dev]`, arm64, other sessions intermittently loading the machine);
      the calibrated LaB6 row's a·√2 rivals still read > 2× the truth's Rwp
      under Pawley, so that assertion stands.
- [x] Skill and docs: the `INDEX_IMPURITY_LINES` row in
      `docs/skill/rietx/references/diagnostics-indexing.md` if its meaning
      moves, `docs/manual/using/indexing.md` (now `docs/docs/reference/indexing.md`
      and `indexing-evidence.md`), and notebook 03's sentence about the quick fit's
      poor Rwp (edit `examples/tutorials/03_*.py`, never the `.ipynb`). The
      notebook's candidate now validates at Rwp 0.044 with 0 unmatched peaks,
      so its `INDEX_IMPURITY_LINES` paragraph went.

## Acceptance

FAP, corundum and zircon's true cells validate with no `FLOOR_HIT` and at most
11 unmatched peaks (one-pass Le Bail today: 76, 43, 60); every row of the
indexing acceptance suite keeps its ranking; the bethanechol benchmark
validates no fewer candidates than on `main`.

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m tests.bethanechol_benchmark
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Pawley, G. S. (1981). *J. Appl. Cryst.* **14**, 357-361.
- Le Bail, A., Duroy, H. & Fourquet, J. L. (1988). *Mater. Res. Bull.* **23**, 447-452.
- Le Bail, A. (2005). *Powder Diffr.* **20**, 316-326, doi:10.1154/1.2135315 —
  §IV.C compares the two; §VI cites Kariuki *et al.* (1999).
- Peterson, V. K. (2005). *Powder Diffr.* **20**, 14-17 (Le Bail against
  Rietveld cells in low-symmetry systems; abstract only).
- WP-0306 (Pawley mode), WP-1043 (the retracted "constrained validator"
  claim), WP-1323 (the alternation), WP-1956 and PR #941.

## Handover log

### 2026-10-29 — the go, decided: Pawley validates NAC's true cell under `quick` (3rd session, begun 2026-10-28)

The indexer now checks its shortlist with a Pawley fit by default, and on the
heavy synchrotron pattern that blocked the go, NAC's true cell gets checked
in the default 120 s run, which no fit reached before. The obstacle was
never the fit's speed alone: the time kept for validation was being spent,
before validation began, on ranking work the search does after its clock
fires. Validation now runs cheapest candidate first and keeps 15 % of the
run instead of 8 %, and Pawley's solver no longer stalls on candidates
whose reflections come in near-coincident pairs, lab or synchrotron. The
cost is about 9 s less search on a heavy pattern; on NAC's default spec the
orthorhombic system is no longer reached. The maintainer delegated the go
and the two constants ("consider a user's needs … use your best judgement").

*Done* (commits 7014d0bb1, db7e7875d, e0c4f479b, f64957f07, 70a6bd578):
- A dense Pawley step past `PAWLEY_SPARSE_DENSITY` is preconditioned by its
  free block's exact Cholesky factor, shifted where singular (Lin & Moré
  1999, ICFS Algorithm 3.1, α_S = 10⁻³, checked in the paper), and takes Lin
  & Moré's subspace step: CG on the face ignoring the bounds, then a
  projected search that puts every variable carried past a bound on it at
  once. The sparse ILU path keeps the cut-and-restart step (lane).
- Under a ceiling, validation fits run in ascending `validation_size`
  (reflections in the lattice group over the range), each on the run's
  clock; the equal slice and its `INDEX_BUDGET_EXHAUSTED` wording are gone.
  `preset="full"` keeps rank order.
- `VALIDATION_RESERVE_FRACTION` 0.08 → 0.15, out of the unaudited baseline
  at tier 3; `PAWLEY_SPARSE_DENSITY` confirmed. Both under the delegation.
- WP-2063 filed: the FoM panel scored after the search's stop.

*Measured* (macOS arm64, `[dev]`, one run per cell, nothing else running;
probes 16-22 in `docs/wp/2011-probe/`):
- Where NAC's 9.6 s went (probe 19): the last trial_error unit returned
  4.1 s past the search's stop, then consensus took 6.5 s, so the first fit
  started at 120.95 s. Profiled (probes 20, 21): `rank_candidates`' panel
  scoring is 4.9 s of consensus's 5.8 s and 3.6 s of the unit's overrun.
- Schedules replayed on measured costs (probe 18): with no clock left, none
  helps NAC; on six lab sets equal slices already validated everything.
  Leader-first fails on NAC regardless: its leader costs 9-15 s.
- `quick`, cheapest first, Pawley (probe 16, final tree):

| dataset | 8 % | 15 % | 20 % |
|---|---|---|---|
| NAC, default spec | no fit started | truth ✓ (1 of 2) | truth ✓ (2 of 2) |
| NAC, all systems | truth's fit cut | truth ✓ (1 of 2) | truth ✓ (2 of 3) |
| zircon, FAP, corundum, LaB6 | all checked ✓ | same | same |

  Lab searches covered the same systems at every reserve; NAC's default spec
  lost orthorhombic at 15 and 20 %. Le Bail at 8 %, cheapest first: NAC
  truth ✓ on both specs. Pawley fits on NAC cost 5-15 s, Le Bail 1.2-1.9 s.
- The dense path's ill-conditioned case (probe 17, lane): zircon described as
  monoclinic P, β = 90.03° (601 columns, 6 % dense), 12.1 → 8.7 s, largest
  solve 1204 → 157 products, total 16 851 → 1 274; corundum as monoclinic C
  (576 columns), 1154 → 128 and 12 654 → 787. Rwp, unmatched and absent
  unchanged on both. FAP.XRA's Pawley fit (probe 22): Rwp 0.0786244, stage
  iterations [2, 8, 6, 9, 9, 7] on every path. NAC's monoclinic candidate
  unchanged (sparse path).
- Lanes (`session_usage.py lanes`): two lanes, saved $15.17 (+26 %); trial
  row in `docs/milestones/process.md`; selective policy at 300-450K peak:
  −5 %.

- Tests, on `origin/main` merged in (7cbec0332), macOS arm64, `[dev]`,
  nothing else running: fast 11 877 passed, 272 skipped, 32 xfailed, 1
  failed (8:44); full 12 288 passed, 283 skipped, 47 xfailed, 1 failed
  (39:03). Both totals are +4 on the 2nd session's, this session's four
  added cases (two of `test_under_a_ceiling_validation_runs_cheapest_first`,
  two in `test_bccg.py`); no new skip. The one failure in each is WP-2035's
  reduce case from the local hypothesis database (its `### Inherited`),
  failing on the base too. Added tests' cost (local junit): the ceiling test
  5.2 s a case (it runs a small dichotomy search and two fits; the file's
  other cases do the same), the rest under 0.3 s.
- Replayed at the measured 15 % clock (7.3 s left on NAC, probe 18's
  policies on probe 16's costs): equal slices in rank order validate
  nothing on either spec; cheapest first validates the true cell on both.

*Review* (`/code-review high --fix 4b8bb73d9..HEAD`): eight findings, five
fixed in 3efa7a1ae (sizing runs only with clock left and is guarded, a
candidate it cannot size sorts last; the skill's indexing reference said
"equal slice", re-synced; `_factor` copies once per shifted try;
`_CHOLESKY_SHIFTS`' arithmetic is 2³⁸; the probe switch is labelled).
Declined: sharing `structure_from_candidate`'s symbol choice (a signature
change for one line), rewriting the 8 % paragraph above the 15 % one (it is
the old value's record), and keeping `ceiling_hit` (removed on purpose; the
1.11.0 note records it).

*Generality* (judge, condensed; full text in the session transcript):
- `_CHOLESKY_SHIFT` **holds** (paper confirms 10⁻³ and the doubling; the
  row's scaling sentence was wrong, fixed). `_CHOLESKY_SHIFTS` **holds**
  (off-by-one in the arithmetic, fixed). The solver's fallback chain
  **holds** (no dense Rietveld stage past 128 columns measured; nothing
  records which branch ran).
- `PAWLEY_SPARSE_DENSITY` **weak**: the constant's comment contradicted the
  row (fixed); the cut now also chooses the step algorithm, and the sparse
  side keeps the singular-face weak case; the approval is a delegation.
  *Author*: the comment now says both; the weak case is WP-2062's.
- `VALIDATION_RESERVE_FRACTION` **weak**: one run per cell, one discriminating
  pattern, one ceiling (at a caller's 60 s, 15 % is the old 9 s); the margin
  on NAC is ~7 s for a 5 s fit. *Author*: agreed; WP-2063 is the fix that
  makes the reserve cover validation alone, and its re-measure is where the
  value gets repeated runs.
- Cheapest-first order **weak**: no replay at 15 % (now given above), the
  leader goes unvalidated on NAC, and size is not cost when a candidate is
  ill-conditioned. *Author*: the objective (most fits) is a choice; on NAC
  the leader is a wrong subcell, and the order is in the reference manual.
- `_PRECONDITION_DENSE` **holds** as rowless; weak as code (labelled now).

*Gotchas*:
- `build_nac_inputs()[::2]` in probes 8-16 slices the returned *tuple*
  (data, structure, instrument) to (data, instrument); NAC is 59 498 points
  either way.
- Under the default preset a `total_budget_seconds=None` is filled with
  120 s; a test wanting no ceiling passes `preset="full"`.
- The sparse ILU path still spends its whole budget on a singular face (FAP
  as monoclinic C, 944 columns, 1882 of 1888 products, 12 s); a shifted ILU
  fixed it offline and slowed FAP.XRA's real fit, so it is not in (WP-2062
  inherits it).

*Next*: review and merge PR #1191 (the maintainer's). Then WP-2063 can
lower the reserve if the panel's cost is bounded, and WP-2062 picks up the
remaining Pawley costs.

### 2026-10-28 (2nd session) — option (c) built: a sparse, preconditioned Pawley solve

A Pawley fit of a pseudo-symmetric candidate no longer takes six minutes.
The cost was conditioning, not size: each bounded step solve spent nearly its
whole budget and the fit needed 89 iterations. With the normal matrix formed
sparse and the step preconditioned, the same fit takes 34 s and every
reading is unchanged, on it and on 15 other cells. That does not rescue the
go. Under `quick` a validation slice is 2-3 s, every NAC Pawley fit costs
more, and NAC still validates 0 of 12 candidates under Pawley. Le Bail
validated 0 and 2 in the same runs, and neither mode reached the true cell.
The maintainer's options are in PR #1191's body.

*Done.*
- First, outside this WP, at the maintainer's request: pytest 9.2.0 (released
  2026-10-27) broke nine fast tests on `main`. PR #1203 (branch
  `tests-pytest-9-2`, not merged) fixes the six API breaks and pins
  `pytest<9.2`. pytest-xdist 3.8.0 groups cases through a private node-id
  attribute that 9.2 renamed (pytest-xdist#1386, fixed upstream, unreleased),
  so every `xdist_group` mark was ignored. `conftest` now fails a marked case
  whose group did not take. `main`'s own CI went red on this at 10:24.
- Probes 12-15 and `probe12_switches.patch` (§ Option (c) probed): a sparse
  JᵀJ, ILU and exact-LU preconditioners, merges at three fractions, no esds,
  `quick` with the fast solve, and a profile of the true cell.
- The solve in the tree, by a lane from the prototype (e39b8c19d), with the
  review's two fixes (36abef33c) and the judge's corrections (bb384fcf8).
  Seven tests added across `test_pawley`, `test_bccg` and `test_lm_solver`.
- Forward notes: WP-2062 (Pawley's re-measured cost and the remaining
  levers) and WP-2035 (a second failing near-right-angle reduce case, below).

*Measured.* macOS arm64, Python 3.12.10, `[dev]`, pytest 9.1.1 (the venv was
downgraded to the pin), quiet machine unless named.
- The tables in § Option (c) probed, including "On the tree".
- Fast selection, `origin/main` (`1fae8887`) merged into this branch: 1
  failed, 11 873 passed, 272 skipped, 32 xfailed (8:09). The total 12 146 is
  `main`'s 12 139 plus the 7 tests this branch adds over it (this session's 5
  and the 2026-10-27 session's 2). The lane's run before the merge: 11 874
  passed, 272 skipped. The one failure is
  `test_indexing_reduce.py::test_the_exact_image_holds_with_one_angle_within_epsilon_of_90[P]`,
  a hypothesis example found this run. It fails on a snapshot of this WP's
  base too, so it is WP-2035's (its `### Inherited` has the example).
- Added tests' cost, this run's junit: 0.93 s over 7, the largest
  `test_indexing_consensus.py::test_the_validation_fits_a_supercell_as_well_as_its_parent`
  0.44 s; per file `test_indexing_consensus` 0.44, `test_pawley` 0.30,
  `test_lm_solver` 0.11, `test_bccg` 0.08. None joins the slow tail.
- Full selection, same merged tree, run once, alone: 1 failed, 12 284
  passed, 283 skipped, 47 xfailed (30:32). The one failure is the same
  reduce case. Every acceptance suite passed, `test_acceptance_indexing.py`,
  `test_acceptance_fap.py`'s Pawley-past-the-cut row and
  `test_acceptance_nac.py` among them. The bethanechol benchmark was not run:
  it validates nothing in either mode (§ Re-measured 2026-10-28).
- Lanes (`session_usage.py lanes`):

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | model | lane $ | main $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | sparse-pawley-solve | 35 | 99 | 314K | 75K | 0K of 55K | 10 | 17K | 4 | 0 | opus-5-5 | 8.57 | 0.94 | 12.97 | +3.40 |

  Actual/estimated requests 2.83. Baseline, selective policy (lane when main
  > 150K and item ≥ 20 requests): −14 % across 296 sessions.

*Review* (`/code-review high --fix 6f0f65fa6..HEAD`, eight findings, two
fixed). Fixed: a sparse diagonal write a + (v − a) missed v by an ulp in 0.4
% of entries, now exact; a switch between preconditioned and plain CG
directions mixed two r·z quantities in β, now a restart. Declined, with
reasons: the tail pattern is derived a second time from `cp.batch` rather
than emitted by its writer (a refactor outside this diff; one test checks
completeness); factorisations are not counted against the product budget
(the policy was measured and kept); single-run timings quoted as figures
(the runs were single, a range would invent numbers); and three minor costs
(the pattern sorted before the density test, a sparse A densified per
crossed trial, D·A·D rebuilt per inner trial), none on the measured hot
spot.

*Generality* (generality-review agent, unedited verdict lines; full tables
in the session transcript, summarised here per item):
- `PAWLEY_SPARSE_DENSITY` (tier 3, 0.05): **weak**. "The row borrows an
  approval that the B10 ruling did not give", and past 0.05 "the stage gets
  the old unpreconditioned CG as well as the dense build", while the evidence
  measures build cost only. "Would change the verdict: the maintainer's own
  dated confirmation, plus either a measured ill-conditioned Pawley stage
  past 0.05 or a dense side that is preconditioned too." *Author:* the row's
  grounds now say the confirmation is pending and its date is the author's;
  the comment and evidence now say the CG is unpreconditioned past the cut.
- `spilu` at scipy's defaults: **holds**; gap: a scipy retune would move the
  solve path unseen, and an incomplete LU is not the paper's symmetric
  incomplete Cholesky. Would change: lifting the two values into constants.
- Refactor on every free-set change: **holds** (one family; 34.2 against
  37.5 s is within run-to-run spread).
- The numpy and BVLS-cut gates: **holds**, tier 1.
- Fallbacks: **holds**; gaps: the r·z ≤ 0 branch is untested, and nothing
  records that the preconditioner dropped out.

*Gotchas.*
- The worktree's branch is `wp2011-pcg`, pushed to
  `wp2011-pawley-validation` (PR #1191), because that local name is checked
  out in `glowing-weaving-quail`.
- The probe switches exist only in `probe12_switches.patch`; probes 12-15
  run against a `git archive` copy with it applied.
- Under `quick` the counts move between runs of one tree (Le Bail 1 → 0 and 3
  → 2 within a day). Compare modes in one sitting.

*Next.* The maintainer rules on PR #1191's options. If (c′) alone: split the
solve into its own PR, which also needs the density row confirmed. If (b):
measure the cutover's threshold before landing it. If (f): measure a reserve
that validates the top-ranked candidate first, under Pawley, on NAC, before
any other speed work, because it decides whether (g)'s levers are needed for
the go at all.

- **2026-10-28** — The maintainer ruled overnight: measure `quick`, then
  merge if no candidate goes unvalidated; rename inside WP-2062; sweep and
  re-ground the three Pawley constants. The names and the constants are
  done. The go's condition failed, so the PR stays a draft.

  *Done.* Probe 8: `index_pattern` under `quick` in both modes on eleven
  dataset and spec cases. Equal validated counts on every lab pattern; on
  11-BM NAC with every system searched, Pawley validated none where Le Bail
  validated one to three. Probe 9: the three constants swept on the
  fourteen cells; no unmatched count or status moved, so the rows in
  `_audit.py` were re-grounded to the default path and dated 2026-10-28,
  tier and values unchanged. Probe 10: Pawley's unbounded cost on NAC's
  checked shortlist (377 s at 2224 reflections), and a reserve sweep showing
  a larger reserve is no fix. Probe 11: the 377 s is 89 LM iterations of
  projected CG and dense JᵀJ on a pseudo-symmetric monoclinic subcell.
  Forward notes to WP-2062.

  *Measured.* macOS arm64, Python 3.12.10, `[dev]` venv built today,
  compiled kernels on, load 3-7 on ten cores with one idle Claude session
  beside. Fast selection on the branch (main had not moved since
  `2cf63737`): 11 859 passed, 10 failed, 272 skipped, 32 xfailed (8:47, no
  other suite running). The total, 11 869 passed + failed, equals
  yesterday's green run; this session added no tests, so
  `added_test_times` has nothing to report. **None of the ten is this
  branch's.** The venv resolved pytest 9.2.0, where CI's last `main` run had
  9.1.1. Six fail on 9.2 directly: `pytest.approx` refuses nested tuples
  (`test_projects_fullprof` ×2, `test_diagnostics_summary` ×1), and
  `Module._id` is gone (`test_jax_cases` ×3). Three in `test_gui_peaks`
  pass serially and fail under `-n 4` on an `origin/main` snapshot too,
  probably the same upgrade, not separated. `test_body_misfit`'s empty PNG
  passed on rerun. The next CI run that resolves pytest 9.2 should go red
  on every branch; no WP owns this, and none was filed. Full suite not
  run: the code change is three audit rows' text.

  *Review.* `/code-review high --fix` over `938a635e..` (this session's
  range; the branch had a high review on 2026-10-27) found 10 items, no
  runtime defect, and fixed 7 (`c5779243`). The worst was the floor row
  claiming no Rwp moved by more than 2e-4 under scaling, which LaB6's
  0.098 contradicts. It also found that `PAWLEY_OVERLAP_FWHM_FRAC` reaches
  a third default path, the line screen's testable mask
  (`extinction.testable_mask` → `_overlap_groups`), which probe 9's frac
  sweep moved with the fit and no absent count followed. The other fixes
  were the cell count (14, not 13) and probes that now restore what they
  patch. Declined: a dead `_scaled(sigma=False)` branch (minor), and
  "the rows cite a default path whose go is undecided". The rows ship only
  with this branch, so a no-go drops them with the switch.

  *Generality* (the `generality-review` agent, unedited; the author's
  answer under each verdict short of *holds*):

  #### `rietx.model.forward.PAWLEY_OVERLAP_FWHM_FRAC` (0.5)

  **weak** (was weak on 2026-10-27). On the indexer's validation fit, the case for keeping 0.5 is now measured and strong. The row also keeps the value on the peak picker's path, though. That path is unswept, and the package's own `fom.py` records a measured case against using 0.5 for a picker question.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "On two default paths: the peak picker's duplicate and unresolved flags, and since WP-2011 every index_pattern validation, where an overlapped group gets an equal-split restraint and is flagged PAWLEY_OVERLAP_UNRESOLVED" (`_audit.py:1892-1895`; WP-2011 is this branch, which made the indexer check each candidate cell with a Pawley fit) | The validation half is right. The picker half does more than set flags. At `indexing/peaks.py:308` the value is the gap below which a curvature shoulder is not seeded as a peak at all. At `pick.py:565` it is the distance below which a component from another fitting group is flagged `duplicate_line`. That flag is in `PEAK_UNUSABLE_FLAGS` (`schemas/indexing.py:810-813`), so the component leaves the line list the search engines and the line screen read. `pick.py:497` sets the report-only `unresolved_shoulder` flag. So on every `index_pattern` call given a pattern, this value decides which observed lines the search sees. | stated; the picker's effect is understated |
  | 2. Kind of ambiguity | none (a constant row needs no `ambiguity` field) | Validation fit: how intensity splits inside an unresolved group is kind 3. The package regularises the split, flags it, and the validation never reads it. Picker: "these two components are one line" is a kind-1 claim resting on a threshold. | consistent for the validation; the picker's claim is untested |
  | 3. Case against | "The peak picker's use (indexing/pick.py, peaks.py) is not swept" (`_audit.py:1891`) | **Validation path:** none found in the measurements. GSAS-II's dissent stands: it ties only reflections that overlap exactly by symmetry (\|Δd\|/d < 1e-4) and leaves near-overlaps free (`docs/practice.md:355, 372-374`, from this repository's survey). The sweep's 0.25 moves toward that choice and changed nothing. Frac 0 itself was not run. **Picker path:** `fom.py:479-489` reads "0.5 is where least squares stops apportioning intensity, while a *picker* separates two equal components only from about one FWHM (Rayleigh 1879; Sparrow 1916)". It also records a measurement: at 0.5, a true cell with a 0.9-FWHM split was refuted. That is why `RESOLUTION_FWHM` is 1.0. So the package's own measured reasoning puts a picker's resolution near 1 FWHM. Meanwhile the picker seeds shoulders, and calls fitted pairs resolved, from 0.5. That is a tension, not a measured failure of the picker. **Cost:** not read. Probe 11 traced the 377 s fit on 11-BM NAC's monoclinic subcell to a nearly singular intensity block (WP § Re-measured 2026-10-28). Grouping shapes that block. That cell is not among the 13. Probe 9 records seconds per run (`probe9_constants.py:109`), and the WP quotes none. Under `quick` (the indexer's default preset, which runs under a whole-run time ceiling), a slower fit can leave a candidate unvalidated. | real on the picker half; cost unmeasured |
  | 4. Case for | "The validation reads the group's sum, which the restraint leaves free, and its readings did not move over 0.25-1.0" (`_audit.py:1895-1896`) | Borne out. Probe 9 (`docs/wp/2011-probe/probe9_constants.py`, the sweep the maintainer ruled for): at 0.25, no unmatched count (observed peaks the cell does not explain) or status (converged, failed, diverged; failed or diverged refutes the cell) moved in any of 14 runs, and Rwp moved by 0. At 1.0, none moved and Rwp moved by 1e-4 (FAP). The sweep did reach the mechanism: zircon grouped 12, 24 and 30 reflections at 0.25, 0.5 and 1.0, and the readings did not follow. The restraint rows sum to zero, so the group total stays free (`forward.py:3316-3323`). **Picker:** "a quarter to a third of the re-seeded components were such copies, 27 of the 116 on cpd-4" (`pick.py:522-524`). That shows the duplicate test catching real copies at 0.5. It is a count at one value, not a sweep. | strong for the validation; one point for the picker |
  | 5. Tier | tier 3, kept at 0.5 (WP-2011 ruling 3, 2026-10-28) | Tier 3 is right. RIETAN-FP's hybrid step uses a rule in FWHM fractions (`RWID`), but its default is still not in `docs/practice.md`, and I found no tier-2 source. Not `invariant`: on an opt-in Pawley refinement the value decides which splits are restrained and flagged. No test pins the validation's insensitivity to it. `tests/` mentions the name once, in a comment (`test_peak_picking.py:1017`). | tier 3 holds |
  | 6. Families and reference | "SRM 660c, 11-BM NAC, GSAS-II FAP, six CPD pure phases, synthetic LaB6's truth and three wrong cells, CPD magnetite's P rival" (`_audit.py:1887-1889`) | **True cells: four real families.** NIST SRM 660c (NIST lab), 11-BM NAC (APS synchrotron), FAP (GSAS-II tutorial lab pattern), and the CPD round robin (one instrument, six materials, counted once). **Wrong cells:** synthetic LaB6 (rietx's generator) and one real family (CPD magnetite). **Reference:** which cell is true is known. No reading moved, so the gate's verdict stays where the truth puts it. That shows the value is inert on this path; it does not validate 0.5. The unmatched counts have no independent reference, because their level belongs to the specimen (WP-1041). The mechanical ground asks for a stated case where the value fails: **none given**. **Picker:** one value, measured on the IUCr round-robin lab patterns and NAC. | passes three families for the validation; the picker has no sweep |
  | 7. What records that it fired | none given | Validation: unchanged since the last review. `PAWLEY_OVERLAP_UNRESOLVED` stays on the fit's `RefinementResult`, which the indexer discards. Picker: each `ObservedPeak` carries its `duplicate_line` and `unresolved_shoulder` flags, so its use is recorded. | recorded on the picker; not on the validation |

  What would change the verdict: the picker's three uses swept at 0.25 and 1.0 on the same families, reading the usable line count and the indexer's ranked candidates. Probe 9 left the picker at 0.5, because `pick.py` and `peaks.py` import their own copy of the name. Or the maintainer ruling that the picker's use gets its own constant and row.

  *Author:* agreed. The picker's sweep is outside this WP: it moves which
  lines every search sees, a WP-2007 (indexing audit) question. The row
  says the picker is unswept. The review pass meanwhile found a third
  path, the line screen's testable mask, now named in the row.

  #### `rietx.model.forward.PAWLEY_OVERLAP_LAMBDA` (1.0)

  **holds** (was weak). The case for keeping 1.0 is stronger. The sweep named last time ran over two decades on four real families and moved no unmatched count or status. Time under `quick` is the one reading it did not report.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "the weight acts only on directions the data do not constrain, and the group sum stays free" (`_audit.py:1906-1908`) | λ weights the equal-split rows and also the off-data ridge (a penalty pulling toward zero the intensities of reflections centred just past the scan's end; `forward.py:3322, 3331`). The probe says so (`probe9_constants.py:13-14`). The row's grounds name only the split. | stated; the ridge half is omitted |
  | 2. Kind of ambiguity | none (constant row) | Split weight: kind 3, a regulariser on a direction the data cannot settle. Ridge: holding it at all is kind 1, since no refiner wants an intensity off the data running to 1e8. | consistent |
  | 3. Case against | none given | No surveyed program uses an equal-split soft weight. GSAS-II's only intensity penalty, on negative intensities, has weight 0 by default (`docs/practice.md:355`). That is a dissent by absence, and the sweep shows the readings do not depend on it over 0.1-10. Cost is unread, as under the first item: λ conditions the intensity block probe 11 blamed for the 377 s fit. | weak case; cost unmeasured |
  | 4. Case for | "0.1 and 10 move no unmatched count or status, and Rwp by at most 7e-4 (CPD corundum at 10)" (`_audit.py:1903-1905`) | Matches the probe 9 table: at 0.1 the Rwp moved 0; at 10, corundum went 0.1371 → 0.1378. The evidence keeps WP-1459's failure without the ridge: a (6 0 2) intensity reached 1.45e8 against a median of 81, and solves ended at up to 769× the Rwp (`forward.py:3297-3301`). | strong |
  | 5. Tier | tier 3 (WP-2011 ruling 3, 2026-10-28) | No tier-2 source found. No test pins the readings' insensitivity. | tier 3 holds |
  | 6. Families and reference | "the 13 cells PAWLEY_OVERLAP_FWHM_FRAC's row names" (`_audit.py:1903`) | Same as the first item: four real true-cell families, one real wrong-cell family, plus synthetic LaB6. Same reference: the readings are inert against known truth, which verifies and does not validate. Stated failure: λ → 0 for the ridge, on one synthetic fluorapatite case (issue #440). | passes three families |
  | 7. What records that it fired | none given | `PAWLEY_OVERLAP_UNRESOLVED` and `PAWLEY_OFF_DATA_RIDGED` stay on the discarded `RefinementResult`. `LeBailValidation` carries neither on the success path. | nothing records it on this path |

  What would change the verdict: the seconds probe 9 already recorded, or a timed validation of NAC's 2224-reflection monoclinic subcell at λ 0.1 and 10. Either would show whether λ moves the fit's cost enough to change what validates under `quick`.

  *Author:* the grounds now name the ridge (`c5779243`).

  #### `rietx.model.forward.PAWLEY_OFF_DATA_SCALE_FLOOR` (1.0)

  **holds** (was cannot tell). The case for keeping 1.0 is stronger. The floor bound on three real families, with the ridge 11-200× wider than designed, and no unmatched count or status moved. Two sentences of the row misstate the measurement and need correcting before approval.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "binds only where that intensity is under 1 or absent" (`_audit.py:1870-1871`) | Correct (`forward.py:3328`). The ridge's width comes from the seeded intensities at build time (`pawley_x0`, `forward.py:3314`). Where the floor binds, the ridge is wider than designed by 1 / (largest on-data intensity). | holds |
  | 2. Kind of ambiguity | none (constant row) | Holding the ridge is kind 1. The floor's value is rietx's own. | consistent |
  | 3. Case against | none given | The floor is an absolute number in intensity units, so whether it binds depends on the units of the user's file. That is a unit dependence by construction. Probe 9 tried one scale (÷ the maximum count). Patterns in still smaller units would widen the ridge further, and none was measured. The WP's intensity-factor scan on synthetic LaB6's true cell suggests something else breaks first: that fit reaches `max_iter` at a factor of 1e-4, in a fit with no off-data reflection. No program in `docs/practice.md` has an off-data ridge. | plausible, measured at one scale |
  | 4. Case for | "the ridge's scale fell to 0.005-0.09 on 11-BM NAC, GSAS-II FAP and CPD corundum and zircon, and to 0 on two synthetic LaB6 wrong cells, so the floor bound; no validation's unmatched count or status moved" (`_audit.py:1872-1877`) | Matches the WP. It answers the scaled-pattern check named last time. The "0" is after the probe's four-decimal rounding (`probe9_constants.py:114`), so it means below 5e-5 or exactly zero. Either way the floor bound by at least 2e4×, and nothing moved. **Two misstatements.** (a) Evidence: "nor its Rwp by more than 2e-4". As written this covers every validation, and it is false: synthetic LaB6's true cell went 0.164 → 0.262 under the same scaling (WP § "A unit dependence the floor does not explain"). The WP shows that cell has no off-data reflection and reads the same with the floor at 1e-12, so the floor did not cause it. The row must say this, or it reads cleaner than measured. (b) Grounds: "where every validation fit carries off-data reflections". The same cell has none. | strong; two sentences to correct |
  | 5. Tier | tier 3 (WP-2011 ruling 3, 2026-10-28) | No program default or citation exists. No test pins the result. | tier 3 holds |
  | 6. Families and reference | NAC, FAP, CPD corundum and zircon, synthetic LaB6 (`_audit.py:1874-1877`) | The floor bound on exactly three real families: NAC (APS synchrotron), FAP (GSAS-II lab) and CPD (corundum, zircon). That meets the bar and does not exceed it. SRM 660c and the other CPD phases are not reported as binding. Every real case is a true cell. The floor bound on a wrong cell only in synthetic LaB6. Same reference as the other two items: the readings are inert against known truth. The failure case (no ridge, WP-1459) sits in λ's row and `forward.py`'s docstring, not this row. | passes three families, at the bar |
  | 7. What records that it fired | none given | `PAWLEY_OFF_DATA_RIDGED` (info) stays on the discarded `RefinementResult`. Nothing reaches the validation record. | nothing records it on this path |

  What would change the verdict: a real pattern in much smaller units, where the floor binds by 1e4× or more and status or the unmatched count moves. Or a real wrong cell where the floor binds and its status moves.

  *Author:* both sentences corrected (`c5779243`).

  *Gotchas.* (1) The bethanechol benchmark never validates: it passes
  `index_pattern` no pattern. (2) A Pawley validation depends on the
  intensity units below a maximum of a few hundred counts (synthetic LaB6,
  Rwp 0.164 → 0.262 at ÷2721); the cause is not found and not the
  off-data floor. (3) `validate_by_lebail` raises numpy's empty-array
  `ValueError` on a peak list with no usable peak (`screen.fwhm_at`). (4)
  Probe 5's `fit_mode` swaps the extinction screen's fits too; probes 8 and
  10 swap `workflow.VALIDATION_MODE` alone. (5) This session worked the
  branch from a second worktree while the 2026-10-27 session sat idle in
  its own; that worktree's checkout is now behind the remote branch.

  *Next.* (1) The maintainer's go, among five options (the PR body has the
  brief): merge as built and accept an unvalidated NAC shortlist under
  `quick`; Pawley with a reflection-count cutover to Le Bail (recommended,
  threshold measured before landing); a sparse Pawley intensity solve
  first (solver work, a WP of its own); WP-2062's decision 0 (a
  per-iteration Le Bail) first; or no-go. (2) Before `gh pr ready`: the
  pytest 9.2 breakage above, or CI's matrix goes red for reasons not this
  branch's. (3) WP-2062, once the go is decided.

- **2026-10-27** — The indexer now checks each candidate cell with a Pawley
  fit instead of one Le Bail pass. It was built provisionally while the
  maintainer was away, so the go, the names and the Pawley constants' grounds
  are still theirs to rule on. On the path the indexer runs, no true cell
  leaves a peak width on its lower bound any more. The count of observed
  lines with no reflection falls on true cells (zircon 44 → 11, FAP 13 → 5,
  corundum 21 → 12), so `INDEX_IMPURITY_LINES` fires less often on a correct
  cell, and tutorial 03 no longer has to explain one away. Two things moved
  the other way. A cell that predicts every reflection of the truth now reads
  about the truth's Rwp, so Rwp never separates a supercell; the old gap was
  the stalled fit's. And a large synchrotron pattern validates 3-5× slower on
  a quiet machine (11-BM NAC). Whether that leaves candidates unvalidated
  under the default `quick` preset is the one thing not measured.

  *Done.* `validate_by_lebail` runs `mode="pawley"` (`workflow.VALIDATION_MODE`)
  and writes `LeBailValidation.mode` (schema 0.60, thresholds 1.12; default
  `"lebail"` for older records). Docstrings, the module's detector table, the
  diagnostics' Rwp advice, `help.py` (incl. `lebail_cycles`, which said Pawley
  ignores the setting that seeds it), the CLI, the manual
  (`reference/indexing.md`, `indexing-evidence.md`, `cli.md`,
  `start/first-fit.md`), the skill rows, the GUI toggle label (dist rebuilt,
  vitest 590 passed), `plot_validation`'s labels, tutorial 03 and its
  notebook, the indexing rulebook and the 1.11 staged notes. Tests: the +1 %
  row now expects absences; new `test_the_validation_fits_a_supercell_as_well_as_its_parent`
  and `test_the_validation_record_names_its_fit_on_every_path`; the magnetite
  acceptance row regenerates Le Bail's bought background by an explicit Le Bail
  fit and pins Pawley's as positive, and its rival Rwp bar inverts to < 1.05×.
  WP-2062 filed at the maintainer's request (Pawley as the structure-free
  default, site by site), with the seven-program practice survey saved to
  `docs/practice.md`.

  *Measured* (all in § Re-measured 2026-10-27 above; macOS arm64, Python
  3.12.10, `[dev]` venv). Fast selection on the tree merged with `main` at
  `2cf63737`: 11 869 passed, 272 skipped, 32 xfailed, 0 failed (6:56, quiet
  machine). Against this morning's run on the bare branch (11 864 passed,
  272 skipped) the +5 is this branch's one later test plus WP-2034's two
  parametrised tests (four cases); skips unchanged. The two added tests cost
  0.46 s together (`tests.added_test_times`, local junit). Indexing acceptance
  on the bare branch: 44 passed, 0 skipped, 0 failed (20:22, other sessions
  loading the machine intermittently). Full suite on the same merged tree:
  12 280 passed, 283 skipped, 47 xfailed, 0 failed (29:02; no other suite
  running at its start, Spotlight indexing on three cores).

  *Review.* `/code-review high --fix` found 9 items, none a wrong result:
  help, CLI and docstring text still naming Le Bail, and
  `INDEX_PREDICTED_BUT_ABSENT`'s help quoting the stalled fit's 0.379 against
  0.216. It fixed 7 (`6d90765c`). Declined: re-deriving
  `VALIDATION_RESERVE_FRACTION` (needs the `quick` measurement below), and
  projecting `mode` into `CandidateEvidence` (a public field; it belongs with
  the maintainer's names decision).

  *Gotchas.* (1) Probe 7's first run timed Pawley in both columns, because
  after the switch the validation passes `"pawley"` and the wrapper rewrote
  only `"lebail"` (fixed `81f8e37e`); probes 5 and 6 imported the module
  before the switch. (2) Pawley's large fits slow down far more than Le
  Bail's on a shared machine (NAC's 1668 reflections: 25 s quiet, 33-107 s
  loaded, against Le Bail's 4-9 s), so quote no Pawley seconds without the
  load. (3) Le Bail itself improved on this tree since 10-18 (FAP 76 → 13
  unmatched, no floor); something on `main` moved it and this session did
  not separate what. (4) The bethanechol benchmark runs `preset="full"`,
  where every checked candidate validates whatever it costs, so it cannot
  see the `quick` risk.

  *Generality* (the `generality-review` agent, unedited; the author's answer
  under each verdict short of *holds*):

  #### Item 1: the validation fit's mode, Le Bail → Pawley (`rietx.indexing.workflow.VALIDATION_MODE = "pawley"`)

  **holds.** The case for acting is stronger. A candidate judged on a fit that stalled with a width on its floor is judged on an artefact, and the measurements show it. The cost case is real but not measured: under the default `quick` preset a slower fit can leave more candidates unvalidated.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "Pawley rather than Le Bail, because one Le Bail pass does not converge" (`workflow.py`, `validate_by_lebail` docstring) | Every `index_pattern` call given data now judges each shortlisted cell by a Pawley fit. No argument lets the caller choose: `VALIDATION_MODE` is a module string. The fit moves four things: `rwp`, `unmatched_observed` (observed peaks with no calculated reflection nearby, which raises `INDEX_IMPURITY_LINES`), `status`, and fit time. `index_pattern` always passes its peak list (`workflow.py:1070-1073`). So the absent-line count comes from the line screen (the candidate-independent check PR #941 added) and never from this fit. The fit therefore reaches the confidence gate only two ways. A `failed` or `diverged` status becomes `validation_failed`, which refutes the cell (`consensus.py:644-645`). A time slice that runs out leaves `not_validated`, which caps the grade at `medium` (`workflow.py:1078-1083`). | stated in part. The author never names these two routes to the gate. |
  | 2. Kind of ambiguity | **none given**. No row exists, and the WP gives only a criterion: "does the Pawley fit answer the forward question … better?" (WP § Re-measured, "The provisional go") | There are two parts. (a) "Judge a cell on a converged fit" is kind 1: I found no competent refiner who would judge a cell on a fit stopped with `w` on its floor. (b) "Pawley rather than a converged Le Bail" is a method default inside an existing action. The programs differ on it. | **none given** (finding) |
  | 3. Case against | WP § Re-measured, Cost: "on a large low-symmetry pattern under `quick`, Pawley can validate fewer candidates than Le Bail did. Not measured." Also: "the Rwp cue a reader saw on supercells is gone." | **Dissenters:** FullProf has Le Bail only. RIETAN-FP and MAUD steer Le Bail first. Kariuki et al. (1999) chose Le Bail to test cell hypotheses because it was faster (`docs/practice.md` § Structure-free fitting). All of them re-extract the intensities every cycle, so they dissent in favour of a *converged* Le Bail, not rietx's one pass. The author measured rietx's converged Le Bail (5 and 10 passes) as no better and slower. The WP itself warns the defect may be rietx's Le Bail rather than the method (WP-2062's decision 0, WP lines 133-135). A per-iteration Le Bail built there would reopen the choice on cost alone. **Cost:** on a quiet machine Pawley took 3× as long at 837 reflections and 5× at 1668 (WP § Cost). The `quick` effect on `not_validated` counts is unmeasured, and the bethanechol benchmark was not run. The lost supercell Rwp cue is no cost: it came from the stall. | real dissent, answered only against rietx's Le Bail. Cost unmeasured. |
  | 4. Case for | "no true cell leaves a width on its floor, the impurity count on true cells falls (zircon 44 → 11, FAP 13 → 5, corundum 21 → 12; brucite +2), and a nested rival's count becomes right" (WP, The provisional go) | Borne out by the tables. On synthetic LaB6 the Pawley background sits within 2 counts of the true 29.7 on every candidate. Le Bail's sinks to 19.1 under the a·√5 cell. Under magnetite's primitive rival, the Le Bail background is −7.3 counts with 25 unmatched peaks. Pawley gives +13.8 and 2, and the true F cell's count of 4 is what the rival should read. Doing nothing costs a true cell a spurious `INDEX_IMPURITY_LINES`. Tutorial 03 had to explain one away; under Pawley its candidate validates at Rwp 0.044 with 0 unmatched. | strong |
  | 5. Tier | "TOPAS defaults to Pawley … GSAS-II … defaults to neither" (WP § Practice, citing `docs/practice.md`) | I checked only `docs/practice.md`, in this repository. That survey read TOPAS from a public copy of Technical Reference v5 §8 p.84, "not re-read by the lead". Pawley is inside the range of practice: TOPAS's default, MAUD's second step, and BGMN's Pawley-type mode. Tier 2 for the method default. The action "validate at all" is the existing row `rietx.indexing.workflow.index_pattern:validate` (`_audit.py:3597`), still `unaudited` and on `UNAUDITED_BASELINE`. No row records the mode. | tier 2 on the survey's word. The table cannot see it. |
  | 6. Families and reference | The nine true cells and four wrong cells (WP tables) | **True cells:** four laboratory/instrument families. NIST SRM 660c (NIST lab, Cu). 11-BM NAC (APS synchrotron). FAP (the GSAS-II tutorial lab pattern). The CPD round robin's pure phases: one Philips instrument and six materials (corundum, brucite, zincite, zircon, fluorite, magnetite). **Wrong cells:** synthetic LaB6 from rietx's own generator, plus one real family (CPD magnetite). **References:** the synthetic background (29.7) is a known truth. The magnetite rival's expected count of 4 follows from lattice containment. The true-cell unmatched counts have no independent reference, since their level belongs to the specimen (WP-1041). So "falls" gives a direction, not a distance to a reference. **Stated failures:** corundum at 12 misses the author's own bar of 11. Brucite goes 9 → 11. Without a peak list, NAC goes 0 → 20 false absences. Rwp numbers appear but carry none of the weight, which Rule 4 requires. | holds for true cells. Real wrong-cell evidence is one family. |
  | 7. What records that it fired | `LeBailValidation.mode` (diff, `schemas/indexing.py`) | `mode="pawley"` on every validation record. The summary line prints "Pawley Rwp". The `INDEX_IMPURITY_LINES` message names the mode. `INDEXING_THRESHOLDS_VERSION` carries a 1.12 note. | holds |

  What would change the verdict: `index_pattern` under `quick` on a large pattern (NAC, a bethanechol set), on a quiet machine, in both modes, counting `not_validated` and `validation_failed`. A second possibility is WP-2062 landing a per-iteration Le Bail that converges like Pawley at lower cost.

  *Author:* agreed on both gaps; the `quick` measurement is this entry's next action (2), and the two routes to the gate are now named here.

  #### Item 2a: `rietx.model.forward.PAWLEY_OVERLAP_FWHM_FRAC` (0.5)

  **weak.** The case for keeping the value is plausible but unmeasured. The written ground "Opt-in Pawley mode" is now false. It was already false before this branch, because the indexer's peak picker reads this constant on the default path.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "Re-ground them (the validation reads Rwp and the unmatched count, and neither depends on how an overlapped group is split) or re-tier them" (WP Tasks, the third Decision) | It sets which reflections count as "strongly overlapped". Those groups get the equal-split restraint and the `PAWLEY_OVERLAP_UNRESOLVED` flag. Since this branch that happens in every validation fit. **Before this branch too:** `indexing/pick.py` (`_unresolved` :492-497, `flag_duplicate_lines` :517, :565) and `indexing/peaks.py:42, :308` import it. There it decides which picked components are flagged duplicate or unresolved, on `index_pattern`'s default peak-picking path. | the ground is wrong on two default paths, not one |
  | 2. Kind of ambiguity | Not stated; a constant row needs none | The split inside an unresolved group is kind 3: the data cannot settle it. The package regularises the split and flags it. The validation does not read the split. | consistent |
  | 3. Case against | none given | GSAS-II ties only reflections overlapped exactly by symmetry (\|Δd\|/d < 1e-4) and leaves near-overlaps free. TOPAS states no rule (`docs/practice.md`). That is a named dissent from restraining at 0.5 FWHM. Within 0.5 FWHM the data still weakly prefer a split, so the soft restraint can move the profile, and with it Rwp, by a small amount. Nobody measured how much. The picker's use, which shapes the line list the search sees, is not measured here either. | dissent exists. Effect unmeasured. |
  | 4. Case for | the mechanism in the Tasks quote | The restraint rows sum to zero, so the group's total intensity stays free (`forward.py:3268-3271`). Rwp and `unmatched_observed` depend mostly on that total. RIETAN-FP's hybrid step sets reflections within `RWID` × FWHM equal, a precedent for an FWHM-fraction rule. The survey does not give `RWID`'s default. | plausible by mechanism. **none given** as measurement. |
  | 5. Tier | tier 3, "second pass owed", approved 2026-10-19 under B12 (a dated ruling batch) (`_audit.py:1876-1882`) | Tier 2 is reachable only if RIETAN-FP's `RWID` default is checked; I could not find it in this repository. The rare-feature clause does not apply: Pawley now runs on every indexing call. | tier 3 stands. Its ground does not. |
  | 6. Families | "LaB6 only (synchrotron and Cu) … never swept" (`_audit.py:1877-1878`) | One family. The mechanical ground asks for three. | fails the mechanical ground |
  | 7. What records that it fired | — | `PAWLEY_OVERLAP_UNRESOLVED` is info level on the `RefinementResult`. `validate_by_lebail` copies none of the fit's diagnostics into `LeBailValidation` (`workflow.py:548-556`), so on the indexer's path nothing records it. | nothing records it on this path |

  What the row needs: grounds naming both default paths (the picker, already; the validation, since WP-2011). It also needs either a sweep (0.25 and 1.0) reading `rwp`, `unmatched_observed` and `status` on the nine true cells and four wrong cells, or the judgement ground answered for a default path. What would change the verdict: that sweep showing the three readings do not move.

  *Author:* agreed; the row is not edited (a tier-3 ground is the maintainer's), and the picker's prior use is recorded in § Tasks.

  #### Item 2b: `rietx.model.forward.PAWLEY_OVERLAP_LAMBDA` (1.0)

  **weak.** The case for keeping it rests on a sound mechanism with no measurement on the path it now sits on.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | as 2a | The weight of the equal-split restraint, scaled by each group's mean intensity. It now applies in every validation fit. | as stated |
  | 2. Kind | Not stated | As 2a: it regularises a split the data cannot settle. | consistent |
  | 3. Case against | none given | No surveyed program uses an equal-split soft weight. GSAS-II's only intensity penalty (on negative intensities) has weight 0 by default (`docs/practice.md`). The effect on the validation's readings is unmeasured. | dissent by absence. Unmeasured. |
  | 4. Case for | "the weight acts only on directions the data do not constrain, and the group sum stays free" (`_audit.py:1887-1888`) | True by construction (`forward.py:3300-3307`). Each penalty term is of order (relative split error)², about 1 unit of χ² at a 100 % error, small against a pattern's data χ². That is my own estimate, not a measurement. | plausible. **none given** as measurement. |
  | 5. Tier | tier 3, approved 2026-10-19 | No tier-2 source found. | tier 3. The ground needs rewording. |
  | 6. Families | "synthetic LaB6 and FAP only; second pass owed" (`_audit.py:1886`) | Two families at most, one of them synthetic. | fails the mechanical ground |
  | 7. What records that it fired | — | As 2a: nothing reaches the indexing record. | nothing records it |

  What would change the verdict: λ at 0.1 and 10 leaving the validation's `rwp`, `unmatched_observed` and `status` unchanged on the same thirteen cells.

  *Author:* agreed; as 2a, left to the maintainer's ruling with the sweep named.

  #### Item 2c: `rietx.model.forward.PAWLEY_OFF_DATA_SCALE_FLOOR` (1.0)

  **cannot tell.** Of the three constants, this one can most plausibly move the gate on the indexer's path. Neither side has measurements there.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | as 2a | The smallest allowed width of the ridge that pulls toward zero the intensities of reflections centred past the end of the scan. Every validation fit generates reflections 0.5° past the scan (`REFLECTION_MARGIN_DEG`), so the ridge acts in every one. The floor binds only where the phase's largest on-data intensity is under 1 (`forward.py:3312`). | as stated |
  | 2. Kind | Not stated | Holding the ridge at all is kind 1: nobody wants an off-data intensity running to 1e8. The floor's value is rietx's own. | — |
  | 3. Case against | none given | The indexer takes data on any scale, so the floor can bind here. A pattern exported normalised to a maximum of 1, or as count rates, plausibly has Pawley intensities under 1. I could not establish the intensity units from the code I read. Where the floor binds, the ridge is looser than designed. The docstring's failure without a ridge was solves ending at up to 769× the Rwp (`forward.py:3283-3285`). On this path that means `status`, and a `diverged` status becomes the refuting `validation_failed`. | an untested case on a default path |
  | 4. Case for | "acts only on reflections outside the data, whose intensity nothing constrains" (`_audit.py:1873-1874`) | True, and on ordinary count data the floor never binds. | holds on count data |
  | 5. Tier | tier 3, "no stated source" (`_audit.py:1869-1871`) | `docs/practice.md` lists no program with an off-data ridge. GSAS-II, MAUD and BGMN only bound intensities. | tier 3 |
  | 6. Families | "WP-1459 (outside PR #453)" | One synthetic fluorapatite case (issue #440). | fails the mechanical ground |
  | 7. What records that it fired | — | `PAWLEY_OFF_DATA_RIDGED` (info) stays on the fit's `RefinementResult`, which the indexer discards. | nothing records it on this path |

  What the row needs: the same re-grounding as 2a. What would change the verdict: the nine true cells validated with the pattern divided by its maximum, showing whether the floor binds and whether `status` or `unmatched_observed` moves.

  *Author:* agreed; the scaled-pattern check (every true cell divided by its maximum) belongs beside the `quick` measurement in next action (2).

  #### Item 3a: the `INDEX_MULTIPLE_SOLUTIONS` suggestion (`diagnostics.py`) and its row in `abstention.md`

  **holds.** The case for the new wording is stronger, since the old text pointed readers at an artefact. It should name the field that answers its own condition.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "Compare their figure-of-merit panels, and their lebail.rwp where neither lattice contains the other" (`diagnostics.py`, `index_diagnostics`) | Advice only. When two candidates both reach `high`, the reader compares Rwp only for a pair that is not nested. | as stated |
  | 2. Kind | The code row is `unaudited` (`_audit.py:654`). The suggestion row's site count of 1 is unchanged. | Kind 2: rival cells ranked by evidence, and the reader picks. | consistent |
  | 3. Case against | none given | (a) The condition needs the reader to know whether one lattice contains the other, and the text names no field that says so. `supercell_checks`' `relation` does (`diagnostics-indexing.md`'s `INDEX_SUPERCELL_REFUTED` row). Rule 4 asks that the next call need no rerun. (b) "Contains" reads backwards to a crystallographer. In real space a supercell's lattice, or a decentred P description of an F lattice, is *contained in* its parent's. What contains is its set of reflections. (c) `diagnostics-indexing.md` (§ around line 337) calls the whole-profile numbers "never a thing to score on". That tension predates the branch, and the branch narrows it. | wording and a missing field |
  | 4. Case for | "a containing cell fits at least as well" (`abstention.md` row) | This is arithmetic: a converged fit with a free intensity at every position the parent has cannot fit worse. Measured at 0.164/0.164 for doubled LaB6 (synthetic) and 0.174/0.180 for magnetite's P rival (CPD). For non-nested pairs Rwp still separates: the +1 % metric reads 0.503 against 0.164, and the calibrated LaB6 a·√2 rivals read over 2× (acceptance suite). TOPAS's indexing GUI refines each solution and reports Rwp (`docs/practice.md`, not checked by me). | strong |
  | 5. Tier | — | The containment rule is tier 1 (arithmetic, given a converged fit). Comparing rival cells' Rwp is TOPAS practice, on the survey's word. | tier 1 and 2 |
  | 6. Families | — | Arithmetic needs none. Two families illustrate it (synthetic LaB6, CPD magnetite). | holds |
  | 7. What records that it fired | — | The `INDEX_MULTIPLE_SOLUTIONS` code. | holds |

  What would change the verdict: a converged fit where a nested cell reads a clearly worse Rwp than its parent, which would make the condition wrong rather than just unclear.

  *Author:* fixed in `2c828657`: "where neither cell predicts every reflection of the other (supercell_checks says)", in the diagnostic, the help entry and the skill row.

  #### Item 3b: the `INDEX_PREDICTED_BUT_ABSENT` suggestion (`diagnostics.py`, `candidate_diagnostics`)

  **holds.** The case for the change is stronger: the old text quoted an Rwp gap that the stalled fit made. The new sentence slightly overstates.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "lebail.rwp cannot separate them: a converged fit of a cell that contains another's lattice matches its Rwp (0.164 against 0.164 for a doubled LaB6 cell)" | Advice only. It tells the reader not to use Rwp to set an oversized cell against the smaller cell. | as stated |
  | 2. Kind | Code row: tier 3, ambiguity 2, approved 2026-10-21 (`_audit.py:657-668`) | The suggestion changes the advice, not the code's capping action. | consistent |
  | 3. Case against | none given | (a) "Matches" is too strong. The magnetite rival reads *lower* (0.174 against 0.180). "Fits at least as well", the workflow docstring's own wording, is accurate. (b) The 0.164 pair is rietx's synthetic fixture, and the text does not say so. (c) The same backwards reading of "contains" as 3a. (d) An oversized cell that does not contain the truth's reflections is separated by Rwp (LaB6 a·√5: 0.233 against 0.164). The opening clause, "the smaller cell that indexes the same lines", limits the advice to the nested case, so this holds. | wording |
  | 4. Case for | the old text's numbers were the stall's (WP § Re-measured: "So the rival/truth Rwp gap the acceptance rows pinned (> 2×) was the stall") | Keeping "Read the count beside lebail.rwp … 0.379 against 0.216" would steer readers to an artefact. The new text agrees with the skill row "Do not check this with Rwp" (`diagnostics-indexing.md:21`). | strong |
  | 5. Tier | — | Tier 1 (arithmetic). | holds |
  | 6. Families | — | One synthetic family quoted; CPD magnetite agrees. | holds for arithmetic |
  | 7. What records that it fired | — | The `INDEX_PREDICTED_BUT_ABSENT` code. | holds |

  What would change the verdict: none expected. The fixes are wording: "at least as well", "synthetic", and containment stated as reflection sets.

  *Author:* all three wording fixes made in `2c828657`, here and at every other site that used the phrase.

  #### Item 4: `rietx.schemas.indexing.LeBailValidation.mode`

  **holds as neither an action row nor an `OTHER_RECORD_FIELDS` entry.** The case against an action row is stronger, because the field is provenance. That leaves item 1's action with no row anywhere, which the maintainer should place.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "A record written before then carries no key and was a Le Bail fit, which is what the default reads" (field comment, `schemas/indexing.py`) | It decides nothing. It records which decomposition ran. Its default decides only how an old record reads. | as stated |
  | 2. Kind | — | Not applicable. It is the record of item 1's action. | — |
  | 3. Case against an action row | none given | Every record written by this release reads `"pawley"`, so the field never varies within a release. It is provenance, like `RefinementResult.mode`, which is listed in `OTHER_RECORD_FIELDS` (`_audit.py:452`). The indexing schemas are not in `RECORD_SCHEMAS` (`_audit.py:225-230`). Adding `LeBailValidation` would force its ~15 other fields into rows or `OTHER_RECORD_FIELDS`, a scope change for WP-2007's audit (the work package that owns the indexing rows), not for this branch. | strong |
  | 4. Case for an action row | none given | generality.md § The rule: "a kept action leaves a record field". Item 1 is an automatic action the table cannot see, and this field is the only place a row could be keyed. Without one, a later change of `VALIDATION_MODE` fails no audit test. | real, but a row here is the wrong seat |
  | 5. The default and its writer | Writer: `validate_by_lebail` (author's dispatch) | Both production constructors pass `mode=VALIDATION_MODE` (`workflow.py:516`, `:556`). The `"lebail"` default is reached only by records written before schema 0.60, where it is true. That meets WP-1076's rule (a field's empty state must not read as an answer nobody computed). No test reads a keyless old record and asserts `"lebail"`, or asserts the failed path's mode. Only the success path is pinned (`test_indexing_consensus.py:833`, `test_acceptance_indexing.py:1655`). | holds. Two pins are missing. |
  | 6. Families | — | Not applicable. | — |
  | 7. What records that it fired | — | The field itself. | holds |

  What would change the verdict: a maintainer ruling to bring the indexing schemas into `RECORD_SCHEMAS`. Otherwise, record item 1 in the evidence of `rietx.indexing.workflow.index_pattern:validate` when WP-2007 audits that row.

  *Author:* both pins added in `2c828657` (`test_the_validation_record_names_its_fit_on_every_path`); the row's seat is left to WP-2007, and a forward note goes there.

  *Next.* (1) The maintainer's three rulings in § Tasks: the go, the names
  and the Pawley constants' grounds. The first decides whether this PR
  merges at all. (2) Measure `index_pattern` under `quick` on a large
  pattern (NAC, a bethanechol set) in both modes on a quiet machine,
  counting `not_validated` and `validation_failed`. It decides whether the
  go needs a fallback for large patterns, or whether WP-2062's decision 0 (a
  Le Bail that re-extracts every iteration) should come first. (3) The
  bethanechol benchmark, only if the maintainer still wants the `full`
  count. (4) WP-2062's five decisions, decision 0 first.

- **2026-10-19** — created, not started. A session asked why the indexer and
  the tutorials use Le Bail rather than Pawley, measured both in the indexer's
  check (§ Context), and @yue-here chose to switch the check to Pawley after
  WP-1956 lands rather than before, since #941 moves the missing count off this
  fit and edits the same two functions. No open WP owns the fit's mode:
  WP-1956 owns the missing count and its inputs, WP-1910 the extinction
  screen's fits, WP-1542 a refinement's Le Bail background, and WP-1323 (✅)
  the alternation. *Next:* when #941 merges, the first task.
