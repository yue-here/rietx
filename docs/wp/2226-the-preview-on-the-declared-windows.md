# WP-2226 — The preview on the declared windows

Milestone: unscheduled · Status: ✅ 2026-11-21 — the preview draws at the last fit's peak cut and rewindows any moved window (option A)
Track: A long run is not one fit
Depends on: 2222 (the closing stage off by default)

## Goal

A GUI preview that starts from the last fit draws the curve that fit
measured. At the fit's own values the residual pane and the Rwp header do not
move when the preview opens.

## Context

**Why it moved.** The GUI preview (`gui/preview.py`, WP-2125 and WP-2128)
compiles at `compile_model`'s windows, which drop 1e-3 of each peak's area
(`CLOSING_WINDOW_TOL`). Until WP-2222 a default fit ended on a closing stage at
the same windows, so the preview at the fit's values reproduced the fit to
1e-9. Since WP-2222 a default fit ends on the declared stages' 2 % windows
(`forward.WINDOW_AREA_TOL`). The preview then differs from the fit by the
tails: up to 0.13 % of the strongest peak on the fluorapatite example (26
counts on 20 310), and the Rwp header in its third digit. Yue accepted that
shift on 2026-11-19 (WP-2222 § Context, ruling 3) and asked for this
follow-up.

**Why the preview was not moved to 2 % in WP-2222.** Its three branches
(frozen, rewindowed, recompiled) test whether a frozen window is still big
enough, and the thresholds were measured at 1e-3 windows. At 2 % the same
estimates missed by up to 1.3 σ, against the 1e-9 the tests ask of a
rewindowed or recompiled answer.

**What to decide first.** Either the preview compiles at the window the last
fit's last stage ran at (`StageResult.window_area_tol`, which every stage
records), or it stays at 1e-3 and the curves route draws at 1e-3 too. The
first keeps the fit's numbers on screen. The second keeps the preview's
accuracy where it was measured. Both are a reader-output change and go to
Yue before merge.

**The tier of each rule this WP adds.** One default: which window fraction
the preview compiles at. It is named practice under either option, since
every program draws the curve its own calculation made at one peak cut
(`docs/practice.md` § How far a peak is computed). Its kind of ambiguity is
"every competent refiner would act" (DESIGN § Rules, 1). It is measured on
the two shipped examples the preview's tests use, `fap` (lab) and `nac`
(synchrotron), against a fresh compile at the same values.

### Inherited

- **2026-11-21, issue triage (#1652 item 2): `Refinement.predict(grid)` is
  this WP's mechanism in the public API, and two paragraphs describe it
  wrongly.** A grid compiles at `compile_model`'s default windows (1e-3 of
  each peak's area left out), while a default fit measures its answer at the
  declared stages' 2 % windows. Checked at `c1033a0e8` on the fluorapatite
  tutorial (`FAP.XRA`, limits 15-130°, `[dev]`, darwin arm64), under both
  `mccusker_structural` (11 stages) and `mccusker_default` (5):
  `predict()` equals `result.y_calc` bit for bit, and `predict(result.two_theta)`
  differs from it on 5751 of 5751 channels. The largest difference is
  1.5-1.6e-3 of the strongest peak and the median 9e-5. `predict`'s own
  recipe, `compile_model(..., window_area_tol=recorded_window_tol(result.stages[-1].window_area_tol))`,
  reproduces `predict()` exactly (0 of 5751 channels differ), so the window
  cut is the whole cause. Two texts are stale:
  `docs/docs/reference/exports.md` § Evaluating the model ("36 of 4200
  channels … 8×10⁻⁶ of the peak height", and a cause about windows sized at a
  stage's start values), and the docstring's bold paragraph "After a default
  fit the two forms agree bit for bit" in `refine.py` `Refinement.predict`.
  The docstring's last paragraph, on the 2 % windows, is right. Ruling A
  above is about the GUI preview. Whether `predict(grid)` follows it is a
  reader-output change and comes to Yue. Today's docstring says the grid form
  is deliberately independent of what the object has fitted, so a
  never-fitted twin returns the same array, and that property is what
  following A would give up. Rewrite both paragraphs to whatever ships.
  The probe is the tutorial's own fit followed by `ref.predict()`,
  `ref.predict(result.two_theta)` and that recipe, compared channel by
  channel. Sibling: WP-1949's Context quotes the stale 36-of-4200 figure.

## Question for Yue: how much of each peak's tail the preview draws

**The decision.** When a person drags a slider in the Interactive tab, should
the preview draw each peak's tail as far out as the last fit did (2 % of the
peak's area left out), or as far as it does today (0.1 % left out)? It comes
to you because the WP says so: either choice changes the curve and the Rwp
the GUI shows a reader.

**Why it matters.** The Interactive tab is for fitting by hand. A person
moves a value, the plot redraws the calculated curve and the residual, and
the header shows the preview's Rwp beside "last fit". Its whole use is that
comparison: did my move help? So with the slider barely moved, the preview
must draw the fit's own curve. Today it does not. Since WP-2222 (the closing
stage off by default, 19 Nov) a default fit computes every peak out to the
point where 2 % of its area is left, as TOPAS does. The preview still
computes out to 0.1 %. The extra tail changes the curve by up to 0.13 % of
the strongest peak on the fluorapatite example (26 counts on 20 310).

What a user sees: on fluorapatite, nudge the scale by 1 %. The header reads
"Rwp 9.444 %, last fit 9.250 %", a jump of 0.19 points. The nudge itself
costs 0.03 points; the other 0.16 is the tail. On the NAC example the offset
runs the other way: the same nudge shows +0.014 points where it truly costs
+0.037. A person fine-tuning by hand is steered by a number that is mostly
the offset. A large move (a zero shift of a tenth of a peak width, +6 points)
swamps it. No fit's answer changes either way. Importance: minor.

**Aim.** Hand fitting in the GUI, for a user who watches the Rwp while
dragging: the number beside "last fit" should change only because of what
they moved.

**Options.** Measured on `fap` and `nac` (table in the 2026-11-21 handover
entry).

- *A. The preview draws at the last fit's tail cut.* It reads the fraction
  the fit's last stage recorded, so a fit that ended on a closing stage
  (`lab_calibrate`, a Pawley series) still draws at 0.1 %. With no fit yet,
  it uses 2 %, the cut a default fit will use. At the fit's values the curve
  and Rwp match the fit's bit for bit on both examples. The preview gets
  faster: 7-11 ms an answer on fap instead of 29-58 ms, and 20-25 ms
  instead of 0.49-0.52 s when the S/L slider (axial divergence) is switched
  on for NAC (machine heavily loaded, so these rank the options and do not
  time them).
  The cost is in code. At 2 % the preview's cheapest branch, which reuses the
  fit's peak windows unchanged, drifts up to 1.26 σ from a fresh calculation
  at the moved values. It sits about as far from the full-tail curve as a
  fresh 2 % calculation does (0.93-1.15× as far). It fails three of the
  preview's tests. The zero-shift and cell-edit tests allow 0.05 σ, and A
  drifts 0.42-1.26 σ there. The peak-width test expects a recomputed window,
  and A keeps the frozen one. Recomputing the windows whenever they move
  removes the drift (exact to 1.7e-13 σ, 3.5-10 ms, 18-24 ms with S/L on).
  I would settle that part myself. Undoable by reverting one change.
- *B. The preview stays at 0.1 %, and the fit's curve is redrawn at 0.1 %
  too.* The pane stops jumping, but the GUI then shows a curve and an Rwp the
  fit never computed. On fap the "last fit" Rwp would read 9.380 % in the
  GUI, while the result, its printed report, the history and any script or
  agent say 9.250 %. Either the header disagrees with the curve under it, or
  the GUI disagrees with every other surface. Each redraw also costs a
  compile, 70-98 ms. Undoable, but it adds a second calculated curve beside
  the result's.
- *C. Do nothing.* The 0.13 %-of-peak jump and the offset in the header
  stay, as you accepted on 19 Nov for the interim.

Dropped: making the preview always recompile from scratch. It gives A's
exactness, but a compile at 2 % alone costs 39-45 ms on fap and 63-78 ms on
nac, against A's 4-11 ms an answer.

**Practice.** No refinement program offers live sliders (`docs/practice.md`
§ A pattern recalculated while a control moves, recall). TOPAS, GSAS-II and FullProf each
draw the calculated curve from the same calculation, at the same peak cut,
that their refinement used (recall, not re-read). TOPAS cuts at
`ymin_on_ymax` 0.001 of each peak's height. For a Lorentzian that leaves out the same 2 % of area
(`docs/practice.md` § How far a peak is computed, checked against the
manual). So practice draws what the fit computed. A follows it; B departs
from it. In rietx itself, `compile_model`'s docstring already says that
redrawing a fit's own curve uses the fraction its last stage recorded, and
the curves route (the server call that sends the GUI the fit's curve) draws
the result's own numbers and computes none. A keeps
both conventions; B breaks the second.

**Recommendation.** A, a clear call. The crux is what the preview is for. It
exists to compare a moved value against the last fit, so it must agree with
that fit at zero movement. A does that on every surface at once. B buys 0.1 %
tails that the fit itself does not have. You ruled TOPAS's 2 % sufficient
on 19 Nov. B pays for them with two Rwps for one fit. What would flip
it: a hand-fitting use where the tails beyond 2 % matter more than agreement
with the fit, such as reading weak peaks sitting in a strong peak's tail. I
have not seen one.

## Ruling

**2026-11-21, Yue: A.** The preview draws each peak's tails to the cut the
last fit used, so before any move it shows exactly the fit's curve and Rwp.
The windows are recomputed on each move, since reusing the fit's windows
drifted up to 1.26σ from a fresh calculation.

## Tasks

- [x] Measure the preview's three branches at 2 % windows on `fap` and `nac`
      (the `tests/test_gui_preview.py` cases), and the shift at the base
      values under each option above. Probes and numbers in
      `docs/wp/2226-measure/`; the table is the 2026-11-21 handover entry.
- [x] Bring the choice to Yue with those numbers: § Question for Yue
      (2026-11-21). Yue ruled A the same day (§ Ruling).
- [x] Implement A, and restore exact agreement at the base values in
      `test_the_residuals_are_the_curves_route_s_at_the_last_fit` and
      `test_at_the_base_values_the_answer_is_frozen_and_the_last_fit`.
      `gui/preview.py` reads the cut off the head's nearest stage node
      (`_cut`), keys its cache on it, and rewindows whenever the sizing rule's
      windows differ from those at the head's values (`_resized`).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_preview.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## Handover log

- **2026-11-21 (implementation)** — option A built; the preview opens on
  the fit's own curve. PR #1751.

  A person who opens the Interactive tab after a fit now sees exactly the
  fit's curve, residual and Rwp until a slider moves. The two Rwp values in
  the header then differ only by what changed. This holds for a default fit
  (2 % windows), for a fit whose last stage ran at 0.1 % (as a closing stage
  does), and for a project reopened from disk, which carries no result. A
  slider that moves a peak's window now gets a resized window. That removed
  the 0.42-1.26 σ drift the measurement found, for 2-3 ms an answer on the
  examples.

  *Done.* Task 3. `src/rietx/gui/preview.py`: `_cut` reads the window area
  fraction and window slack off the nearest stage node at or above the head
  (`recorded_window_tol`; no stage gives `WINDOW_AREA_TOL`). The cache key
  carries the cut and every compile passes it, the recompile branch too.
  `_resized` replaces `_outgrown`: the frozen branch rewindows when the
  sizing rule's windows or node counts at the new values differ from the
  same rule's at the head's values. The comparison is against the rule at
  the head, never against the compile's own windows. Those come from the
  compile's width estimate, about 1 % apart, so comparing against them could
  rewindow at the head and lose the fit's curve. The magnetic family takes
  the same rule and recompiles, since `rewindow` keeps its windows. The slack
  rides with the fraction because `Refinement._final_compile` builds the
  result's curve with both. Manual: one sentence in the `/api/preview` row
  of `reference/gui-power.md`. The sentence was first written into
  `reference/gui-guide.md`, but that page sat at 49 999 characters against
  `test_manual.py`'s 50 000 cap. Splitting it is out of scope.
  Tests (`tests/test_gui_preview.py`): the base-values test runs on fap and
  nac and asserts `array_equal` against `result_.y_calc` and `==` on the
  Rwp. The residuals test asserts `delta_raw` bit for bit. The zero-shift
  and cell-edit tests now expect `rewindowed` (nac exact; fap zero shift
  under 0.05 σ). `_fresh` compiles at the fit's cut read off
  `result_.stages[-1]`, independent of `_cut`. New: a last stage at 1e-3
  then `Project.open` draws at 1e-3 and matches that result bit for bit; an
  unfitted tree compiles at `WINDOW_AREA_TOL`; a magnetic family shrunk or
  shifted recompiles. The cache test also asserts that a `set_value` head
  keeps the stage's cut.

  *Measured* (`[dev]` venv plus playwright 1.65.2, darwin/arm64, this
  worktree). Probe `~/.cache/ghostshift/rietx/wp-2226/neg.py`, not
  committed (shape of `docs/wp/2226-measure/nudge.py`), at load average
  2-3. With the cut forced back to 1e-3, the answer at the head differs from
  the fit on both examples (fap Rwp 9.380 % against 9.250 %, nac 9.292 %
  against 9.317 %). That is the guard failing on purpose; under A both are
  equal. Per answer, min to median of 7: fap scale ×1.01 frozen 2.3 ms,
  zero +0.1 FWHM rewindowed 3.2-3.3 ms; nac 1.2 ms and 1.9-2.0 ms. Nudge,
  preview Rwp minus the fit's: fap scale ×1.01 +0.029 points, nac +0.037,
  each the nudge's true cost.

  *Checks.* On the tree with main merged at `e71774ff8`. Fast selection
  through ghostshift's `serial.py`: 2 failed, 15 235 passed, 433 skipped,
  32 xfailed (12:46, beside other runners' work). With playwright
  installed, the browser files run inside the fast selection, so this total
  is not comparable with CI's, where they skip. The two failures:
  `test_manual.py`'s page-size contract, which my sentence in
  `gui-guide.md` broke and the move to `gui-power.md` fixed (13 passed on a
  rerun); and
  `test_gui_layout_browser.py::test_today_s_terms_box_leaves_no_stale_hold`,
  a WP-2229 background-terms test this branch does not touch, which passed
  in the browser run below. The browser glob (`tests/*_browser.py`, nine
  files, `-n 2`, in two commands): 104 + 72 = 176 passed, none failed.
  `tests/test_gui_preview.py`: 35 passed. Added tests, from the fast run's
  junit file: the reopen test 8.13 s (one fap fit plus one stage, under the
  suite's load); the other four added tests total 0.33 s. The reopen test is
  not marked `slow` because it is the one check that the cut is read off the
  tree. Ruff and CI's Vale steps: no errors. `tests.reader_output`: exit 0,
  unchanged.

  *Reviews.* `/code-review high --fix` found 8 issues. Fixed: the
  docstrings now say replay reads a stage node's cut and compiles any other
  node at the defaults; the manual claim was narrowed (then moved, above).
  Added on its finding and the judge's: the magnetic shrink-or-shift test.
  Declined: (1) a magnetic phase's position slider recompiles (about 40 ms)
  instead of rewindowing, because `forward.rewindow` keeps the magnetic
  family's windows, and teaching it to resize them is a change to `forward`
  for a rare case; (2) a merge head takes its first parent's cut, as
  `lineage` does, and a merged state has no single fit curve to match;
  (3) the cut in the cache key is redundant with the head id, but cheap,
  and it keeps a patched `WINDOW_AREA_TOL` from serving a stale base;
  (4) `_fresh` reads no slack, since `StageResult` records none, and every
  fixture uses the default; (5) the cut is stored twice on `_Base`, because
  the magnetic test helper builds a base with an empty key.

  *Generality* (the `generality-review` judge, unedited):

  ## `_cut` (src/rietx/gui/preview.py): which peak cut the preview computes at, and its fallback chain

  **holds.** The case for acting is stronger: the maintainer ruled this
  exact behaviour, the measured cost of not doing it is most of what the Rwp
  header shows, and I could name no competent refiner who would act
  otherwise in this situation.

  "Cut" here means the fraction of each peak's area left outside its
  evaluation window.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | It reads the cut off "the nearest stage node at or above the head". A tree with no stage takes `WINDOW_AREA_TOL` (2 %) and the default window slack (preview.py module docstring; `_cut` docstring). | It decides the area fraction and slack of every preview compile. There are three branches. (a) The head is a stage node: its recorded cut. (b) The head is not a stage, e.g. an applied slider, which is a `set_value` node: the nearest stage above it. (c) The tree has no stage: 2 % and a slack of 0.3°. | — |
  | 2. Kind of ambiguity | Kind 1, "every competent refiner would act" (WP file § Context, "The tier of each rule this WP adds"). | It is kind 1. The header puts the preview's Rwp beside the last fit's, and that difference measures the slider only if both are computed at one cut. That is arithmetic. | agrees |
  | 3. Case against | "a hand-fitting use where the tails beyond 2 % matter more than agreement with the fit, such as reading weak peaks sitting in a strong peak's tail. I have not seen one" (WP § Recommendation). | 2 % has a known accuracy cost. Against fully converged tails it is off by 0.71-2.15 σ at fixed parameters (the `forward.WINDOW_AREA_TOL` row in `_audit.py`). The fit carries the same cost, and Yue ruled TOPAS-level accuracy sufficient on 2026-11-19. Branch (c) departs from `compile_model`'s own default: when a caller passes no cut, `compile_model` uses the closing fraction, 0.1 % (`forward.py` docstrings of `WINDOW_AREA_TOL` and `recorded_window_tol`). The given reason is "the cut a default fit will use". That branch was part of option A as written in the brief Yue ruled on. No competent refiner who would act otherwise is named. | weak case |
  | 4. Case for | The old preview showed a fit's own curve wrong by up to 26 counts on a 20 310-count peak (0.128 %, 2.05 σ) on fap (the lab fluorapatite example). On fap a 1 % scale nudge read +0.194 Rwp points, of which +0.029 was the nudge. Under A the curve and Rwp match the fit bit for bit on fap and nac (the 11-BM NAC example). (WP handover 2026-11-21, tables; `nudge.py`.) | The numbers are quoted with their probes in `docs/wp/2226-measure/`. The tests now assert bit identity: `test_at_the_base_values_the_answer_is_frozen_and_the_last_fit` (fap, nac), `test_the_residuals_are_the_curves_route_s_at_the_last_fit`, and `test_a_fit_ending_at_another_cut_is_drawn_at_it_after_a_reopen`. The ruling is in the WP file: "2026-11-21, Yue: A". | strong |
  | 5. Tier and source | "named practice under either option, since every program draws the curve its own calculation made at one peak cut (`docs/practice.md` § How far a peak is computed)" (WP § Context). | That practice.md section lists each program's default cut. It does not record that a program draws its curve at its fit's cut. That claim is "recall, not re-read" (WP § Practice). The slider survey in practice.md (§ A pattern recalculated while a control moves) says no refinement program has live sliders (recall). So the tier-2 evidence is recall. The arithmetic ground in row 2 holds without it. | tier 2 rests on recall; tier 1 on arithmetic |
  | 6. Dataset families | fap (lab) and nac (synchrotron) (WP § Context). | That is two families, by instrument and material. Both are development data, being the preview's own test fixtures. The reference is a fresh compile at the same values, or the fit's own curve. Both references verify and neither validates (Rule 2). Nothing here sets a threshold, so the three-family test does not apply. The plan path is not tested directly: the reopen test makes its 0.1 % cut with `run_stage(..., window_area_tol=1e-3)`, not with a plan's closing stage such as `lab_calibrate`. | adequate for an identity |
  | 7. Record of what fired | none given | The cut used is not in the answer's header. The header carries `evaluated`, `head`, `rwp`, `values`, `phases`, `ticks` and `tick_hkl` (preview.py around line 340). Branch (c) in particular is invisible to the caller. A reader can work out (a) and (b) from the stage record. | finding |

  Would change the verdict: a hand-fitting case where tails beyond 2 %
  decide the answer, or a plan whose closing stage leaves no stage node
  carrying 0.1 %.

  Author: the header field is declined. No client reads it, which is the
  WP-1427 lesson about a field nothing reads, and branch (c) is a tree with
  no fit, where there is no fit curve to disagree with.

  ## `_resized` / `_choose`: rewindow whenever the sizing rule's windows or node counts change; recompile on a magnetic change

  **holds.** The case for acting is stronger. The old grow-only test was
  measured drifting up to 1.26 σ from a fresh compile, and the new rule has
  no free number in it.

  "Rewindow" here means recomputing each peak's window and FCJ node counts
  on the cached compile (FCJ: the axial-divergence quadrature). A recompile
  builds the whole model again.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | Rewindow "when the windows or node counts the compile's sizing rule gives at the new values differ from those it gives at the head's values". For the magnetic family, a difference recompiles (preview.py module docstring). | It decides which of three paths answers a slider move: frozen, rewindowed or recompiled. Before, only a grown window or node count triggered a rewindow. Now a shrink or a shift does too. On the magnetic family a shrink now recompiles. | — |
  | 2. Kind of ambiguity | none given. The WP's tier paragraph names only the cut. | It is kind 1, a numerical setting: it controls how exact the preview is, not what it decides. The ruling covers it: "The windows are recomputed on each move, since reusing the fit's windows drifted up to 1.26σ" (WP § Ruling). | none given; kind 1 by reading |
  | 3. Case against | none given | I found no competent refiner who would keep the stale windows. The only cost is time: a rewindow plus evaluation takes 3.5-10 ms, and 18-24 ms with S/L (axial divergence) switched on. A frozen answer takes 4-6 ms on nac. These timings were taken at load average 30-35 (WP handover). Two gaps remain. First, the magnetic shrink-recompiles path has no test: `test_a_magnetic_family_outgrown_is_recompiled` covers growth only. Second, a frozen answer equals a fresh compile only while the compile's own width estimate and the sizing rule round to the same window points. They agree to ~1 % only (`window_sizing` docstring), and that was measured only on the fap and nac cases. | none found |
  | 4. Case for | At 2 % "a frozen window that a peak has moved inside is cut off-centre. Reusing it drifted 0.42-1.26 σ from a fresh compile on a zero shift of one FWHM and on a 0.05 % cell edit" (preview.py docstring; WP handover table). | The handover's "A-exact" column backs this: 0 to 1.7e-13 σ, except 0.0175 σ on fap. That residual comes from the frozen reflection list at the range edge, not from windows. The tests are `test_a_zero_shift_of_one_fwhm_is_rewindowed` (bars 0.05 σ on fap, 1e-9 on nac), `test_a_cell_edit_is_rewindowed_and_exact` (1e-9) and `test_the_scale_slider_stays_frozen_and_exact`. | strong |
  | 5. Tier and source | none given | Read as a numerical setting, it is tier 1 under the 2026-10-19 rule for numerical settings: the tests above show the error stays under a stated bar. The rule tests exact equality (`array_equal`), so it has no threshold to tier. It sits inside practice (`docs/practice.md` § How far a peak is computed, checked). TOPAS rebuilds its peak buffer when a width moves past `aberration_range_change_allowed`. GSAS-II, MAUD and RIETAN-FP recompute every evaluation. | tier 1 by reading; not stated |
  | 6. Dataset families | fap and nac (WP handover). | Two families, both development data. The reference is a fresh compile at the same cut, which verifies only. There are no magnetic measurements at 2 %; the MnF₂ tests check which path is chosen, not accuracy. | adequate for an identity; magnetic untested |
  | 7. Record of what fired | The header's `evaluated` says `frozen`, `rewindowed` or `recompiled` (preview.py docstring). | Confirmed at preview.py line 340. | holds |

  Would change the verdict: a slider case where the compile's estimate and
  the sizing rule round to different window points, so that a frozen or
  rewindowed answer misses a fresh compile by more than its test's bar, or
  a measured magnetic shrink case.

  Author: the magnetic shrink test is added
  (`test_a_magnetic_family_shrunk_or_shifted_is_recompiled`).

  *Gotchas.* The fap zero-shift row keeps 0.0175 σ against a fresh compile.
  That is a fresh compile's reflection list at the range edge, which the
  preview's frozen list does not grow until `REFLECTION_MARGIN_DEG`. It is
  the same in every arm of the measurement. `refinement.result_` is `None`
  after `set_values`, so a test reading the fit's cut reads it before the
  edit. `reference/gui-guide.md` is 1 character under the manual's page
  cap, so a sentence added there needs a cut or a split.

  *Next.* Nothing in this WP; it closes with this PR. A magnetic phase's
  position sliders recompile rather than rewindow. That is recorded above
  and not filed, since the answer stays exact and costs about 40 ms.

- **2026-11-21 (ruling)** — Yue chose A after the shift's end-of-shift
  report. Next: task 3, from the 2026-11-21 entry's *Next* (2).

- **2026-11-21** — the preview measured at the fit's 2 % windows; the
  choice is with Yue.

  A preview drawn at the last fit's own tail cut reproduces that fit's curve
  and Rwp exactly, on both shipped examples, and answers 1.2-21× faster than
  today's preview (median to median: 1.2-1.5× on nac's frozen cases, 2-7× on
  fap, 21× with S/L switched on). Today's preview jumps by up to 0.13 % of the strongest
  peak the moment a slider moves. That jump is most of what a fine-tuning
  nudge shows in the Rwp header: on fluorapatite a 1 % scale nudge reads
  +0.194 points, of which +0.029 is the nudge. The one cost found is that
  the preview's cheapest branch drifts up to 1.26 σ from a fresh calculation
  at 2 %, and recomputing the windows on every move removes it for a few
  milliseconds. Nothing was implemented: § Question for Yue asks which
  option to build.

  *Done.* Tasks 1 and 2. Probes `measure.py` (both options, every test case),
  `measure2.py` (the rewindow variant, timings, the S/L split) and
  `nudge.py` (what a small nudge shows) in `docs/wp/2226-measure/`, with
  their JSON and text output. The run's load averages are saved beside them.
  `/code-review high --fix` ran over the branch. It corrected the speed-up
  range, the tests' bars A fails, the always-recompile cost and the
  rewindow timing in this entry and the brief, and pointed *Next* at the
  head node's record.

  *Measured* (`docs/wp/2226-measure/measure.py` and `measure2.py`, `[dev]`
  venv, darwin/arm64, this worktree). Both examples were fitted with their
  default plan, which ends on the `biso` stage at 2 % windows. `fap` is the
  lab fluorapatite: 5 750 points, strongest peak 20 310 counts. `nac` is the
  11-BM synchrotron pattern: 22 003 points, strongest peak 264 872 counts.
  "Status quo" is the preview as it stands (1e-3 windows). "A" points the
  preview's compiles at the fit's recorded fraction (2 %) and changes
  nothing else.

  At the fit's own values:

  | | fap | nac |
  |---|---|---|
  | status quo against the fit's curve | 26.0 counts, 0.128 % of the strongest peak, 2.05 σ | 9.8 counts, 0.0037 %, 0.68 σ |
  | Rwp, status-quo preview minus the fit's | +0.130 points (9.380 % against 9.250 %) | −0.025 points (9.292 % against 9.317 %) |
  | A against the fit's curve and Rwp | 0, bit for bit | 0, bit for bit |

  Per test case, the largest error in σ. "Own" is a fresh compile at the
  preview's own fraction, which is what the tests assert against. "A-exact"
  replaces A's frozen branch with a rewindow at the new values. The last
  column is how far a fresh 2 % compile sits from a fresh 1e-3 one, which is
  the truncation itself.

  | case | status quo: branch, vs own | A: branch, vs own | A-exact vs own | A vs 1e-3 | fresh 2 % vs 1e-3 |
  |---|---|---|---|---|---|
  | fap scale ×0.5, ×2 | frozen, 0 | frozen, 0 | 0 | 1.03, 4.10 | 1.03, 4.10 |
  | fap zero + 1 FWHM | frozen, 0.0175 | frozen, **1.26** | 0.0175 | 1.78 | 1.92 |
  | fap W ×4 | rewindowed, 0 | frozen, **1.00** | 0 | 2.19 | 1.90 |
  | fap zero + 1.0° | recompiled, 0 | recompiled, 0 | — | 1.40 | 1.40 |
  | nac scale ×0.5, ×2 | frozen, 0 | frozen, 0 | 0 | 0.34, 1.35 | 0.34, 1.35 |
  | nac zero + 1 FWHM | frozen, 0.036 | frozen, 0.42 | 0 | 0.67 | 0.67 |
  | nac cell a ×1.0005 | frozen, 0.036 | frozen, 0.43 | 1.7e-13 | 0.68 | 0.68 |
  | nac Lorentzian size 0.02 | rewindowed, 0 | rewindowed, 0 | 0 | 1.50 | 1.50 |
  | nac S/L 0.025 | rewindowed, 0 | rewindowed, 0 | 0 | 264 | 264 |

  The WP's "missed by up to 1.3 σ" is the fap zero-shift row (1.26 σ).
  Against the near-complete curve, A's frozen answer is 0.93-1.15× as far
  away as a fresh 2 % compile, so it loses nothing the fit's own windows do
  not. What it fails is the tests' bars against a fresh compile: 0.05 σ in
  the zero-shift and cell-edit tests (A gives 0.42-1.26 σ), and on fap W ×4
  the branch itself, which the test expects to be `rewindowed`. A-exact
  meets every bar the status quo meets; the fap zero-shift row's
  0.0175 σ is the frozen reflection list at the range edge, the same in
  every arm.

  Time per `preview.evaluate`, 15 repeats, min to median. The load average
  was 30-35 throughout (other runners on this machine), so these rank the
  arms and do not time them. fap: status quo 29-58 ms frozen and 66-86 ms
  recompiled; A 7-11 ms and 36-41 ms. nac: status quo 5-7 ms, the
  Lorentzian case 18-21 ms, the S/L case 486-521 ms; A 4-6 ms, 7-8 ms and
  20-25 ms. A-exact's rewindow plus evaluation is 3.5-10 ms, and 18-24 ms
  in the S/L case. One compile
  costs 90-98 ms at 1e-3 and 39-45 ms at 2 % on fap, 70-75 and 63-78 ms on
  nac.

  *Gotchas.* The nac S/L row's 264 σ (7.9 % of the strongest peak) is the
  declared stages' FCJ node rule (`profiles/fcj.py`), not the window. At
  1.99 % windows the closing node rule applies, and the gap to 1e-3 falls to
  0.25 σ (7.3e-5 of the peak). Every reflection sits at the declared rule's
  64-node cap there. S/L = 0.025 on an 11-BM pattern is the test's stress
  value and no real synchrotron setting, so this is noted and not filed.
  Under option A a preview of that slider draws what a declared stage
  computes.

  A small nudge (`nudge.py`), the preview's Rwp minus the last fit's:

  | | status quo | A |
  |---|---|---|
  | fap scale ×1.01 | +0.194 points | +0.029 |
  | fap zero + 0.1 FWHM | +6.237 | +6.134 |
  | nac scale ×1.01 | +0.014 | +0.037 |
  | nac zero + 0.1 FWHM | +9.359 | +9.370 |

  *Checks.* PR #1740. `tests/test_docs_consistency.py` and
  `tests/test_gui_preview.py`: 66 passed (`-n 4`, load average 29). The fast
  suite did not run: the branch changes only `docs/wp/`, and nothing imports
  the probes. Ruff and CI's vale steps: no errors. `tests.reader_output`:
  unchanged. No generality judge: the branch adds no heuristic, and the one
  default the brief proposes waits on the ruling.

  *Next.* (1) Yue rules on § Question for Yue. (2) Under A: read the cut
  from the head node's record, `recorded_window_tol(node.action.window_area_tol)`
  as `refine.replay` does, since the preview's base is keyed on
  `_head_id`. `result_` is `None` on a reopened project and stale after a
  checkout, so a reopened `lab_calibrate` project would otherwise preview at
  2 % against a 0.1 % curve. A head that is no stage (an applied slider is a
  `set_value` node) takes the nearest stage node above it, and a tree with
  none takes `WINDOW_AREA_TOL`. Add the cut to the preview's cache key. Make the
  frozen branch rewindow whenever a window sized at the new values differs
  from the frozen one. The "A-exact" column measured an unconditional
  rewindow, which bounds that rule's cost from above. Then task 3's two
  tests go back to exact agreement, and the other branch tests keep their
  bars against a fresh compile at the same cut. The zero-shift and cell-edit
  tests assert `frozen`, and under that rule they take `rewindowed`, so
  their branch assertions change with the code. Under B the curves route and the
  Rwp badge both change, and the brief's two-Rwp problem needs a design
  first. Under C, close the WP as no-go with the ruling.

- **2026-11-19** — filed by WP-2222's session after Yue accepted the shift
  and asked for a follow-up.
