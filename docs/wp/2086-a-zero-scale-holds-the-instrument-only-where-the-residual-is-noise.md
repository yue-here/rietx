# WP-2086 — A zero scale holds the instrument only where the residual is noise

Milestone: unscheduled · Status: ✅ 2026-11-04 — an instrument hold at an answer needs Hill & Flack's d ≥ Q
Track: What fires, and what stays silent
Depends on: —

## Goal

The hold WP-2049 added at a stage's answer, of the instrument terms that reach the
pattern only through phase peaks, applies where the frame is blank and not where the
phase's peaks missed. A real phase can then use its zero shift and widths to reach
its peaks, as it could on 1.10.0, and a blank frame stays held and bit-identical.

## Context

**Ruled by Yue 2026-11-04: take the check.** WP-2049 is closed, so this is a new WP
(`docs/wp/TEMPLATE.md`: what a closed WP's fix did not cover is a new WP). Ruled
alternative: ship as is. It lost because main fails on a tutorial's worked example and
on a plain single fit that 1.10.0 reaches, and it gained only the three FAP fits below.
The ruling assumed the check restores 1.10.0's reach. The second handover entry measures that
over 100 noise draws on both platforms, and it holds as a rate.

**The defect.** On a frame where every phase reads as unseen at a stage's answer,
`refine._unsupported_phase_paths` held the zero shift, the displacement and the widths
as well as the cell, reasoning that those columns are flat. That reasoning holds on a
blank frame. It is false when the peaks merely missed: the scale goes to zero and the
real peaks stay in the residual. On tutorial 05's 2 % step, on its noise draw, the first warm solve took
the scale to 2.47σ on both 1.10.0 and main. On 1.10.0 a second solve kept the zero
shift and U..Y free, U climbed to 6 deg², the scale reached 83σ, and the closing stage
freed the cell to 4.2482 Å. Main held them, had only scale and background left, and
stayed at 2.09σ. So the warm rung failed and the ladder ended at Rwp 0.998,
`SEQUENTIAL_UNRECOVERED`. Single fits were not spared: on the same noise draw LaB₆ 2 % off
went from Rwp 0.0405 on the true cell to 0.934 with `MODEL_FAR_FROM_DATA`. Over 100 draws the
loss on `main` is a rate, in the second handover entry.

**The discriminator was measured before the fix** (`~/.cache/ghostshift/rietx/wp-2049/`
`step/disc.jsonl`, not committed). The Durbin-Watson d at the answer: 40 blank draws,
240 triggers, d 1.94-2.05 against Q 1.89-1.91; misplaced fits d 0.02-0.12. A real empty
Kapton capillary reads d 0.43-1.04, under Q, so its hump counts as signal, and χ² there
is 0.83-2.0, which is why χ² could not be the test. Hill & Flack's Q is the threshold:
the paper's 0.1 % point, read from the paper, never tuned.

**What it costs, and it was the price of the ruling.** Three real FAP fits that main
gets right go back to failing as on 1.10.0, at Rwp about 0.69 reading `converged`:
`lab_bragg_brentano` at +1.5 % and −3 %, and `mccusker_default` at −3 %. They gain
`mccusker_default` at +3 %, which main fails. The FAP family's silent failures are
folded into WP-2017, with the evidence.

A second cost surfaced in review. A blank frame with structure in its residual, a hump
the background cannot follow or rebinned noise, reads under Q and keeps its instrument
free, as on 1.10.0. See the handover.

## Non-goals

- `MODEL_FAR_FROM_DATA` on background-subtracted Rwp. It is WP-2017's, folded there
  from this WP, and its threshold and reader output are the maintainer's calls.
- A budget on a failed fit. See the handover's cost numbers.
- `docs/releases/1.11.0.md` and the tutorial notebooks: PR #1400 owns the notes.

## Tasks

- [x] The check in the single runner and per histogram in the joint one, sharing
      `optimize.statistics.durbin_watson` with `compute_statistics`.
- [x] Decide the channels d is read over, and test it.
- [x] Tests, each failing without the check, with plots looked at.
- [x] The audit row, the Theory equation, the rule, the practice survey.
- [x] Remeasure the failed fit's cost on its worst rows, alone.
- [x] The reach matrix on the final tree against 1.10.0's stored results.
- [x] A lasting 2 % jump in a series, main against the check.
- [x] Rule 1: say where the d that declined the hold is read.
- [x] Fold the silent failures.
- [x] Measure the rescue under perturbation and over noise draws, on macOS and Linux.
- [x] Pin what is robust: the decision, and only those outcomes measured at 100 %.

## Acceptance

`.venv/bin/python -m pytest tests/test_instrument_hold_noise.py tests/test_held_phase.py -n auto --dist loadgroup`
passes on macOS and Linux, and over 100 noise draws the rates of reaching the cell match
1.10.0's within 3 in 100 and stay at or above `main`'s.

## References

- Hill, R. J. & Flack, H. D. (1987). J. Appl. Cryst. 20, 356-361.
- Theil, H. & Nagar, A. L. (1961). J. Am. Stat. Assoc. 56, 793-806.
- `docs/practice.md` § Testing the residual for serial correlation.
- WP-2049's file, for the hold this narrows.

## Handover log

- **2026-11-04** — A frame where every phase reads as unseen now holds its instrument only if the residual is noise, by Hill and Flack's published 0.1 % test. A phase whose peaks merely missed can use its zero shift and widths again, so tutorial 05's 2 % step and a plain fit 2 % off reach their answers as they did on 1.10.0. All 119 fits of the reach table match 1.10.0 verdict for verdict. That includes the price Yue accepted: three FAP fits main got right fail again at Rwp about 0.69 reading `converged`, and a failed fit takes about 6 minutes where main took about 4 seconds. A blank frame with structure in its residual also stays unheld, and no real blank frame has yet been seen to pass.

  *Done.* `optimize.statistics` gains `durbin_watson`, `durbin_watson_q`, `HILL_FLACK_Z` and `residual_is_noise`, and `compute_statistics` and the background order scan read the one `durbin_watson`. `refine._peak_columns_flat_at_answer` is the gate, and `multi._rehold_multi` calls it per histogram. Audit row, Theory equation (`est-dw-q`), the concepts page, `help.py`'s `PHASE_UNCONSTRAINED` entry, the rule in the root CLAUDE.md and the practice survey are in. The silent failures are folded into WP-2017.

  *Measured* (macOS arm64, `[dev]`, Python 3.12, compiled tier).

  *Check on against off.* A single LaB6 fit at +2 %: Rwp 0.0405 at a 4.1628387 against 0.9336 at 4.0812. Tutorial 05's chain: warm rung at Rwp 0.0390 against cold at 0.9982. A blank frame: identical, d 1.9566 at or above Q 1.906, instrument held. A joint fit of one misplaced and one blank histogram: Rwp 0.0564, cell 4.1628387, the blank histogram's zero and U..Y held, the misplaced histogram's zero free, against Rwp 0.9162 and a cell about 7800 ppm short. d on the declining answers read 0.119 against Q 1.906-1.909.

  *Reach table.* 119 fits from displaced starts, re-run on this tree against 1.10.0's stored rows. Verdict-identical on all 119: 55 reach the answer, 52 fail with an error, 12 fail silently. Main reads 53, 56 and 10. Against main this tree loses FAP `lab_bragg_brentano` at +1.5 % and −3 %, and `mccusker_default` at −3 %. It gains FAP `mccusker_default` at +3 %, and on LaB₆ the 2 % start under `mccusker_default` cold and warm, the 2 % start under `mccusker_structural`, and the 0.2° zero start.

  *A lasting jump in a series* (`mccusker_default`, tutorial 05's fixture, 6 frames before and 6 after, warm chain). At 2 %, 50 K a frame and seed 100: 6 of 6 frames after the jump fit on main and on this tree, the jump frame on `warm_staged` in both. One seed is no evidence here, since the outcome turns on the noise, so a scan ran 8 sizes from 1 to 3 %, 2 frame spacings and 3 seeds, 288 frames after a jump. Fit, quarantined and failed: main 244, 44, 0; this tree 264, 24, 0. By size, quarantined out of 36: at 2 % main 1, here 0; 2.1 % 6 and 0; 2.2 % 8 and 1; 2.5 % 9 and 3; 3 % 20 and 20. No frame failed silently on either tree. Every failed frame is a quarantine, which seeds no successor, so a chain that loses the jump frame goes on missing until a rung recovers.

  *Failed-fit cost, alone on the machine* (only busy python, load average 3-5). FAP `lab_bragg_brentano` +5 %: 333-348 s here, 3.6-3.7 s on main, 43 s stored for 1.10.0. FAP `mccusker_default` −3 %: 390-395 s here, 3.4 s on main, 293 s stored for 1.10.0. So the 610 s of the diagnosis was load and the effect is real. The first row spends 1024 evaluations at about 0.33 s each, 623 of them in the roughness stage at its iteration cap. The second spends 262 at about 1.5 s. The widths have walked to tens of degrees (U 64 deg²) or the zero shift to −500 446°, so each evaluation covers the whole pattern for every reflection. The first row fails on main too, in seconds. The second succeeds on main at Rwp 0.0909. No budget was added: a budget is a design call and the fit is failing either way.

  *Channels.* d is read over the fitted channels with the record's own arithmetic, one bridged pair per excluded gap, so `Statistics.durbin_watson` is the number tested. Worst placement, each excision on a peak maximum, bridged against pooled: LaB₆ with 15 gaps moved d by +0.446 and kept 1.36 from Q, FAP with about 60 by +0.21 (1.63), NAC with 55 by +0.26 (1.67). Pooling would need a new adjacency field on `CompiledModel` and the number tested would leave the record.

  *Blank frames that decline.* The empty Kapton capillary reads d 0.43-1.04. Eight structured frames (2 Kapton, 6 synthetic humps) kept the instrument free, 6 identical to the held fit at scale 0 and 2 refining, for example zero 0.0048 ± 0.0255°. Rebinned noise reads the same, as the judge predicted: a blank frame smoothed by (¼, ½, ¼) reads d 0.64-0.68, a two-channel box 0.96-1.02, against Q 1.91, 3 seeds each. Four of those 6 stay at zero and identical to the held fit. Two refine, at zero −0.0029 ± 0.0016° and U 0.20 deg², and −0.0002 ± 0.0029° and U 0.38 deg². So a rebinned blank frame behaves as on 1.10.0 and never reaches the hold.

  *A weak phase.* LaB₆ at +2 % with its peaks 2.5 to 3700 times the background: where the phase stayed misplaced d stayed under Q, 0.14 to 1.85 against 1.91. At 38 times the background the fit found the cell (d 1.97, a 4.15660). The review's sweep of the same fixture agrees: d 0.12-1.24 over scale 5e-4 to 1e-6.

  *Q.* On white noise of 3000-22 000 points, not fitted, P 12-34, d < Q fires 0.17-0.41 % of the time. P is `len(table.free_paths)`, as the paper defines it, so a flat column of an unseen phase counts. That overstates Q at small N/P and always errs toward declining.

  *Where the d that declined is read.* A fit that ended at that answer: `result.statistics.durbin_watson`, printed as `DW`, with `n_points` and `n_free_parameters` beside it. A fit that went on from it: that stage's history node, `metrics.statistics`. Both are pinned by test. Nothing new is printed or returned. Q and the check's outcome are on no field, and a `history=False` fit that recovers keeps no d from the declining stage. Closing either needs a new field, which is reader output, so it stays out.

  *Reader output.* `python -m tests.reader_output`: unchanged against the merge-base. One help sentence changed, `PHASE_UNCONSTRAINED`'s in `help.py`, which also reaches the manual's generated reference.

  *Review.* `/code-review high --fix` found 9 and fixed 5. Q ≥ 4 now reads as nothing to test, the manual and help state the lineless case and that a background misfit also reads low, the test instruments declare `Dispersion()`, two test refinements gained their plot, and the order scan calls the shared d, bit-identical above a residual of 1e-150. Declined: the real-blank-frame finding, which is the ruling's scope and is recorded above; P as an effective rank, a design change against "never tuned"; one evaluation per stage spent on d, negligible beside the significance read at the same point.

  *Gotchas.* Read a manual's equation from the rendered page. pdftotext split the braces of FullProf's eq. 3.20 off its line, and this session first recorded QD as a different formula. The judge caught it against the printed numbers. A 2 % jump's outcome turns on the noise seed, so quote a scan and never one chain.

  *Gates* (macOS arm64, `[dev]`, Python 3.12, `53b231add`, which is `origin/main` plus this branch; main had not moved at the last fetch). ruff clean. Fast selection: 13828 passed, 319 skipped, 36 xfailed in 7:35, one run. This branch adds 24 cases in 16 test functions, 11.44 s together on that run, in `tests/test_instrument_hold_noise.py`, and removes none, with no new skip. None joins the slow tail. Full suite, through the shift's queue, nothing else running: 14744 passed, 332 skipped, 53 xfailed, 1 failed in 32:30. The failure is `tests/test_pair_diagnostic_class.py::test_the_two_site_winner_finds_each_site_its_own_moment`, which is not this WP's. Run alone it fails the same way on this tree and on `origin/main`'s source, to the same digits (0.6994957343907221 against 3.5), so `main` fails it on this Mac. The Linux nightly of 2026-11-03 passed it. `tests.reader_output`: unchanged.

  *Generality* (the judge's report, unedited, written while the 119-fit matrix was still running).

  ## `rietx.optimize.statistics.HILL_FLACK_Z` (constant, tier 2, value 3.0902)

  **Verdict: holds, but one clause of the row is false and needs correcting.** The case for the constant is stronger. The number is the paper's, and FullProf's printed output supports it better than the row says.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "gates only the instrument half of StageResult.held" (row `evidence`) | It sets where Q (the Durbin-Watson threshold) falls. Q decides whether the zero shift and peak widths are held. The caller did not ask for it. | Agrees |
  | 2. Which kind | The field is not required on a constant. | It is a threshold under a first-kind action. The row points to `StageResult.held` for the rule's tier. | Agrees |
  | 3. Case against | none given | The paper uses Q to report serial correlation and to judge esds, never to gate an action. It also says the source of the correlation "is not perceived per se from the test and must be deduced from other considerations" (Hill & Flack 1987, read in `/Users/yue/Zotero yue-here/storage/MUC693I9/`). That limits the action, not the number. No rival number found. | Weak case |
  | 4. Case for | "Q is the 0.1 % significance point of d, tested there on real X-ray and neutron Rietveld residuals" (row) | Confirmed in the paper: four specimens (CaF2, PbSb2O6, corundum, PbSO4) and Q printed with 3·0902. Φ⁻¹(0.999) = 3.09023. | Strong |
  | 5. Tier and source | Tier 2. "FullProf 8.20 prints a Q by default with the second term undoubled (docs/practice.md)" (row). `docs/practice.md`: "N − P 5723 and 5277 give the printed 1.9301 and 1.9277 to the digit". | Tier 2 holds on the paper. **The FullProf clause is contradicted by its own numbers.** In `/Users/yue/Code/rietx-bench/runs/20261011-162539-calibrate-pbso4-xray/fullprof/default/calibrate3/pbso4.sum`, lines 40, 107 and 113 give P = 34, N−P+C = 5723 and DW-exp 1.9301. With C = 0, N = 5757. The paper's doubled form, 2[5756/5723 − 3.0901/√5759], gives 1.9301. The undoubled form gives 1.9708. Line 118 reads 5275 in this file, not 5277; the doubled form still gives the printed 1.9277, and the undoubled form gives 1.9701. The undoubled form would need N near 1440 to match, and this file has 5999 points. So FullProf's output is the paper's Q at z = 3.0901. The "forty times" false-alarm paragraph in `docs/practice.md` describes the formula as typed, not FullProf's output. I did not read the FullProf manual, whose PDF text I could not extract. The GSAS-II line `GSASIIstrMath.py:4995` is confirmed, and it computes d only. RIETAN eq. 4.32 was not checked. | Tier holds; evidence clause fails |
  | 5, invariant | Not an invariant row. | `tests/test_instrument_hold_noise.py::test_q_is_the_papers_equation_2` and `::test_q_is_the_point_it_claims_on_white_noise` pin it. | Good |
  | 6. Families | Tier 2 needs none. The paper's four specimens are cited. | The paper's four are not rietx data, so they are independent of this package. They support "d below Q means model deficiency". They do not support "d above Q means blank frame". | Enough for the number |
  | 7. Record | "never printed" (`docs/practice.md`) | d, N and P are on `Statistics`. Q is on no field. | See the third item |

  Evidence that would change the verdict: a reading of FullProf's source or a different `.sum` file showing a printed value that fits the undoubled form and not the paper's.

  Author's answer: the judge is right and my reading was wrong. The manual's eq. 3.20 carries braces pdftotext split off the line, so QD is the paper's Q. The row and `docs/practice.md` are corrected, and the false-alarm paragraph is gone.

  ## `rietx.schemas.results.StageResult.held` (action, tier 3, ambiguity 1, changed)

  **Verdict: weak. The narrowing has the stronger evidence, but the row no longer describes what the code does and leaves out its own failures.**

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides; what the caller must now decide | "that instrument hold at an answer also needs d >= Q" (row `evidence`) | The hold (fixing zero shift, displacement and U..Y for the stage) now needs d ≥ Q, or no phase line in the fitted range. Below Q the caller sees freely refined instrument terms on a frame with no seen phase. The caller must judge whether those numbers mean anything. | Accurate |
  | 2. Which kind | `ambiguity=1` | The hold stays first kind, and narrowing it moves it closer to unanimity. But `grounds` still says no competent refiner "lets a frame no phase is seen in refine the instrument terms". The package now does exactly that below Q. | Sentence is stale |
  | 3. Case against keeping a hold | None given for the hold itself in this change; "on by default, which no program does" (row `grounds`) | No dissenter found for a white residual with every phase unseen. Yue's recorded series practice (instrument held through a series) points the same way. | None found |
  | 4. Case for acting where the hold is now removed (d below Q) | "held there, LaB6 2 % off ended at Rwp 0.93 and 19 600 ppm, free at 0.0405 on its cell" (row). WP-2086 (this work package), Context: "Three real FAP fits that main gets right go back to failing". | The FAP cost is real and **is missing from the row**. In `/Users/yue/.cache/ghostshift/rietx/wp-2049/step/reach_main.jsonl` against `reach_fix.jsonl`: `lab_bragg_brentano` at +1.5 % goes from Rwp 0.090, a = 9.3684 Å, 3.6 s, to Rwp 0.693, a = 9.103 Å, 49 s. At −3 % it goes from 0.090 to 0.691, a = 9.745 Å. `mccusker_default` at −3 % goes from 0.091, 5.5 s, to 0.688, 517 s. Both of those end further from 9.37 Å than they started. Against that, `mccusker_default` at +3 % improves from 0.690 to 0.097. All read `converged`. Blank frames also pay. In `blank_fix.jsonl`, 2 of the 8 structured blank frames (2 Kapton, 6 synthetic humps) walked: `lab6_blank_hump20_2` reads zero 0.0048 ± 0.0255°, U 0.125 deg², at 157 iterations against 44. These logs may predate the final tree, and the final matrix is still running. | Case for keeping the hold is real but smaller; row must state it |
  | 5. Tier and source | Tier 3. "was ruled by the maintainer 2026-11-04 (WP-2086)" (`grounds`), with `approved="2026-11-01"` unchanged. | Tier 3 is right: no program holds these terms (`grounds`, not rechecked). The date field does not match the ruling the grounds cite. I saw that ruling only as text in the WP file. | Maintainer's to confirm |
  | 6. Families | "20 noise frames stayed bit-identical" (row). The dispatch names LaB6 synthetic, FAP lab, NAC synchrotron and the Kapton frame. | Hold-fires side: **no real frame.** The blank frames are rietx's own Poisson draws, two recipes, one family. The one real blank frame, Kapton, declines. Hold-declines side: FAP (GSAS-II tutorial, lab) and NAC plus Si plus Kapton (all APS 11-BM, so one instrument). That is two real laboratories plus synthetic, all development data. The reference is truth by construction, or the cross-code value for FAP, which only verifies. The six of the 20 frames I compared match to every printed digit. The committed test covers 4 cases. | Three-family ground not met on the hold side |
  | 7. Record | Row is keyed on the field. | `StageResult.held` and `PHASE_UNCONSTRAINED` (the diagnostic naming held phases) say it fired. No field says it declined. See the third item. | Half covered |

  Evidence that would change the verdict: rewritten `grounds` covering the d < Q case, the FAP losses and hump walks in `evidence`, and a real blank frame from a second instrument on which the hold fires.

  Author's answer: `grounds` and `evidence` are rewritten to cover the d < Q case, the FAP losses and the structured blank frames. The `approved` field is the maintainer's, so it stays and goes to him. No real blank frame has passed, and none was on hand from a second instrument, so that gap stands, and a decline falls back to 1.10.0's behaviour.

  ## The one-sided decision d ≥ Q gating the instrument hold (`refine._peak_columns_flat_at_answer`, also per histogram in `multi.py`; not visible to the table)

  **Verdict: weak. The evidence that d catches missed strong peaks is overwhelming. The evidence that d can recognise a real blank frame is absent.**

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | `_peak_columns_flat_at_answer` docstring: "the residual is noise and nothing is left for them to find" | It decides whether a frame with every phase unseen is blank or holds missed peaks. d measures lag-1 correlation only, so "nothing is left" overstates what it shows. | Slightly over-worded |
  | 2. Which kind | Inside the `ambiguity=1` row. Help text: "either the model missed the peaks or the background cannot follow the data". | Fair. Hold is first kind. A decline makes no claim of cause, which fits the paper's warning quoted in the first item. Declining also leaves what the plan asked for free, so it is no action. | Agrees |
  | 3. Case against | "A real empty Kapton capillary reads d 0.43-1.04, under Q, so its hump counts as signal" (WP Context) | Three gaps. (a) In `disc.jsonl`, `kapton_empty_bk12` reads χ²red 0.834 with d 1.04. Excess hump signal should raise χ², so correlated noise is a live explanation. 11-BM merges and rebins channels (my recall, unmeasured). If so, a truly blank frame from rebinned or area-detector data reads below Q whatever the background, and the hold never fires there. The paper names this class: "it is the intensity observations themselves that are correlated". A competent refiner would still fix the instrument on that frame, which is the case for a hold where d is below Q. (b) A weak misplaced phase is unmeasured. Measured misplaced fits are all strong, d 0.02-0.12. My estimate: a missed signal under about 3.4/√N of the residual χ² passes as noise, about 7 % at N = 4200. Undersampled peaks pass more easily, and the paper shows d rising toward 2 as steps widen. (c) The stage-start route through `tried` carries a passed hold onward without re-reading d. | Real, unmeasured |
  | 4. Case for | "misplaced fits d 0.02-0.12" (WP). Blank frames "d 1.94-2.05 against Q 1.89-1.91". | Confirmed in `disc.jsonl`: FAP 0.046-0.057, NAC 0.031, Si under an LaB6 model 0.022. Gap to Q is about 1.8 on the misplaced side. Blank-side margin is thin, as a 0.1 % test must be. Without the check: Rwp 0.93, 19 600 ppm; tutorial 05 quarantined; joint fit 7800 ppm (`tests/test_instrument_hold_noise.py`). A bad decline returns 1.10.0's behaviour, so the test errs safely. Kapton lost nothing: scale reached zero and the numbers match the held fit. | Strong |
  | 5. Tier and source | Statistic and threshold tier 2. "So rietx's use of the threshold is its own" (`docs/practice.md`). | Statistic: tier 2, GSAS-II checked, FullProf prints it (see first item). Threshold: tier 2 for its number. As a gate it is rietx's own, tier 3 inside `held`. The claim that no program gates on it comes from the survey; I did not recheck it. **Not an invariant.** | Consistent |
  | P as `len(table.free_paths)` | Dispatch: flat columns of unseen phases count, so Q is overstated at small N/P. | The paper says P is "the number of least-squares parameters estimated", so this follows the text. Effect in `disc.jsonl`: P 5 to 9 moves Q 0.0028, against a spread of d near 0.038 at N = 2834. My arithmetic, unmeasured: N = 500 with P 30 against 5 moves Q 0.107, a false decline near 3 % rather than 0.1 %. It always errs toward declining. | Accept; small and safe |
  | Fitted channels, bridged pairs | Test docstring: "fifteen such pairs moved d by 0.45 with 1.36 still to go to Q (the WP's record)" | The WP record is not written yet, so that claim has no source. The direction is safe on measured fits: the margin holds. `test_a_real_line_in_an_excluded_region_does_not_decline_the_hold` covers the masked line. N ≤ P + 1 or Q ≥ 4 returns "noise", so the hold fires untested, opposite to the check's safe direction. It looks unreachable on real patterns. | Needs handover entry |
  | 6. Families | LaB6 synthetic, FAP lab, NAC synchrotron, Kapton (dispatch) | Count as for `held`: two real laboratories plus synthetic, all development data. Reach matrix (119 fits from displaced starts) is unfinished. | Not met on hold side; pending |
  | 7. Record | "A declined hold leaves d on the record" (`_peak_columns_flat_at_answer` docstring) | d and N are on `Statistics`, and a stage's d is on its history node. Gaps: Q and the check's outcome are on no field. `n_free_parameters` is the last stage's, so Q recomputed from it may differ from the Q read at the deciding stage. With `history=False`, a fit that recovers keeps no d from the declining stage. | Partly met |

  Evidence that would change the verdict: a real blank frame reaching d ≥ Q at any background order, a measurement of d on rebinned noise, and a misplaced weak phase series showing where d crosses Q.

  Author's answer: two of those three are measured above, under *Blank frames that decline* and *A weak phase*. Correlated noise does decline the hold, as the judge predicted, and a weak misplaced phase stayed under Q in every case that stayed misplaced. The first is unmeasured. The record's gaps stand, since closing them needs a new field, which is reader output.

  *Next.* This is PR #1406. PR #1400 owns the release notes and drops the failure note after this merges. `examples/tutorials/05_sequential_fits.ipynb`'s stored outputs still show `SEQUENTIAL_UNRECOVERED` on the jump and need the rebuild #1400 carries. The tutorial's prose stays true. WP-2017 owns the silent failures. A real blank frame passing the test, from a second instrument, is the evidence still owed.

- **2026-11-04, the Linux failure** — CI run 41839775116 failed three of this file's tests on Linux, so the 2 % rescue was measured properly. The check holds up, and the first entry's claim was too strong. Reach past about 1.5 % is a rate that depends on the noise draw, on every version. The check restores 1.10.0's rate and beats `main`'s where the hold fires. A test may pin the decision and may not pin one fit's landing.

  *What failed.* The fixture's noise draw, seed 14, happens to sit near a basin edge. A perturbation of 1e-14 relative on the start W lands elsewhere on 2-5 % of plain fits and about 40 % of the excluded-region fit. Identical installs flipped between attempts: four attempts on GitHub's Linux runners read Rwp 0.0405, 0.9358, 0.0405 and 0.0405 at no perturbation. So `test_a_single_fit_two_percent_off_reaches_its_cell` was pinning a draw from a distribution. Python's version is not the variable.

  *Recovery over 100 noise draws.* The fixture's pattern redrawn with seeds 101-200, one fit each, on three trees. "Reached" is Rwp under 0.06 with the cell within 100 ppm, or for a chain the jump frame's Rwp under 0.06. Figures are Linux x86-64 on Python 3.11. Python 3.14 and macOS arm64 agree within 3 in 100, so the rates do not depend on the platform.

  | Start error | Single: `main` | Single: here | Single: 1.10.0 | Chain step: `main` | Chain step: here | Chain step: 1.10.0 |
  |---|---|---|---|---|---|---|
  | 1.5 % | 98 | 98 | 98 | 100 | 100 | 100 |
  | 1.75 % | 95 | 95 | 95 | 100 | 100 | 100 |
  | 2 % | 92 | 93 | 93 | 90 | 99 | 98 |
  | 2.25 % | 62 | 85 | 85 | 58 | 81 | 80 |
  | 2.5 % | 24 | 38 | 37 | 16 | 42 | 41 |
  | 3 % | 3 | 4 | 4 | 17 | 26 | 27 |

  On macOS only: a start 2 % high in the cell reaches it in 59, 74 and 75 of 100 single fits (`main`, here, 1.10.0), and 88, 100 and 100 on a chain. With two excluded regions at 2 %: 85, 90 and 90. Up to 1.25 % every single fit reached its cell, and chains reached it in 98-100 of 100.

  Against `main`, draw by draw, on the rows from 2 % this tree gained 1 to 26 fits per row and lost 0 or 1. Up to 1.5 % the two are bit-identical on every draw, because the hold never fires. So the check buys reach, and 1.10.0 is its measure: rates within 3 in 100 on every row. The gain sits at 2.25-3 % and on a chain's step, and a plain single fit at 2 % gains 1 in 100. The first entry's headline, a plain LaB₆ fit at +2 %, describes seed 14. `main` reaches 92 of 100 other draws.

  *Under perturbation.* 141 groups of one fit repeated with W moved by k·1e-14. A group is one case, start error and noise seed. On Linux 3.11, 7 of the 141 are mixed here, 1 on `main` and 4 on 1.10.0. So most draws are settled and a few sit on an edge. Seed 14 at 2 %: 129 of 132 here, 0 of 132 on `main`, 132 of 132 on 1.10.0. At 1.75 % seed 14 reaches its cell on no version, 0-3 %, where 95 of 100 other draws do. With the excluded regions at 2 % seed 14 reads 56-60 % here, 100 % on `main` and 99-100 % on 1.10.0. That one row is worse here than on `main`, and over 100 draws of the same fixture it is the reverse, 90 against 85.

  *Linux.* 1.10.0 recovers: 132 of 132 on the plain fit and on tutorial 05's step, on Python 3.11 and 3.14. The check's tutorial step reads 132 of 132 on both, and the verbatim tutorial script took the 700 K fit on `warm` at Rwp 0.0390 in 12 of 12 attempts across Python 3.11, 3.13 and 3.14. The 800 K fit that follows it took `warm_staged` in 7 of those 12, so the prose "Every pattern after the first took its values from the plain `warm` attempt" holds for the 700 K pattern and not reliably for the next. `tests/test_tutorials.py` pins no value here. It asserts that the notebook runs clean.

  *The 119 fits.* "Verdict-identical to 1.10.0 on all 119" was a true sentence about one fit per row on this Mac, and it is weak evidence. Each row is one draw, and it says nothing about a rate. The 39 rows at the edge were repeated with W perturbed, at 7 starts on LaB₆ and NAC and 3 on FAP, whose failed walks run for minutes. At no perturbation this tree and 1.10.0 agree on all 39. Whether a row reaches its answer changes with rounding on 2 rows of the 39 on `main` and 2 here, and on none on 1.10.0. Here that is LaB₆ `mccusker_default` at +2 % (6 of 7) and FAP `mccusker_default` at +3 % (2 of 3). That second row was listed as a gain over `main`, and it stands as one: `main` reaches it 0 of 3 times and 1.10.0 3 of 3. On `main` the two rows are FAP `lab_bragg_brentano` at −3 % (2 of 3) and LaB₆ `mccusker_structural` at +2 % (1 of 7). The three FAP rows the ruling paid for stay lost: here they reach 0 of 9 starts, and `main` reaches 8 of 9. Four FAP walks here and four on 1.10.0 hit this probe's 900 s cap under load and count as failures. The other 33 rows read the same at every start on all three trees.

  *No small fix.* None found, and none tried. The fit stays at scale zero through the first four stages, and the `profile` stage then runs 90-150 iterations until the widths overlap real peaks. The path is sensitive to rounding because the gradient on the cell is proportional to a scale near zero. A fix would have to change how the fit starts from a lost phase, which is a new method and out of scope here. Any other rounding-level difference between machines would still reach it.

  *Tests.* `test_a_phase_whose_peaks_missed_keeps_its_instrument_free` replaces the single-fit outcome: it reads the decision at the `zero`, `cell` and `profile_w` stages, before the walk starts. `test_the_peaks_still_read_as_structure_past_an_excluded_region` drops its Rwp and cell asserts. `test_a_fit_that_goes_on_leaves_the_declining_d_on_its_history_node` drops the assert on the final d. `test_the_tutorials_step_is_reached_warm` and `test_a_joint_fit_with_one_misplaced_and_one_blank_histogram` keep their outcomes, because both recovered 61 of 61 perturbed starts on macOS and on Linux 3.11 and 3.14, and 0 of 61 on `main`. 1.10.0 reads 100 % on the first and 5-11 % on the joint fit. With the check taken out all six tests that move a fit fail, on this tree.

  *Gates* (macOS arm64, `[dev]`, Python 3.12). ruff clean. Fast selection on the tree before this entry's last edit: 13828 passed, 319 skipped, 36 xfailed in 9:23, with other probes running. That is the first entry's count, since this session renamed tests and added none. The full suite was not rerun: the only source change is the text of an audit row's `evidence`, which moves no number. `tests.reader_output` was not rerun for the same reason. The manual's concepts page gained two sentences of rates. Scripts, logs and the full table: `~/.cache/ghostshift/rietx/wp-2086-split/` (`table.md`, `seedtab.txt`), not committed. The Linux numbers came from throwaway runs 41843278368, 41845319908, 41845440268 and 41847377132 on a deleted branch.

  *Next.* PR #1400 carries the release notes and the tutorial's rebuild. The notes may say tutorial 05's 2 % step works again and that 1.11 matches 1.10's rate of reaching a cell. They should not say a single fit 2 % off is restored. The tutorial's "Every pattern after the first" sentence needs narrowing to the 700 K pattern, which supersedes the first entry's "The tutorial's prose stays true". This session's first-entry *Next* otherwise stands.
