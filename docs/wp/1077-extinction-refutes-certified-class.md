# WP-1077 — The extinction screen refutes a certified class

Milestone: 1.0.x · Status: ✅ 2026-08-18 — **the evidence was wrong, and the fix
is in the test.** Both refuting positions sit on the low-angle flank of a strong
allowed line; at the same offsets, *sham* positions carrying no reflection of any
kind clear the same 3σ test on 40-50 % of probes (up to 24.7σ, low-angle flank
only — the unmodelled axial tail), and freeing the FCJ asymmetry improves Rwp
without removing the refutation. So testability gains a third clause
(`extinction._model_is_quiet`): a forbidden position counts only where the
class's **own** fitted pattern leaves the window below the test's own detection
threshold, which makes even a total failure of a neighbour's tail insufficient to
refute. The screen now returns `R - c -` = {R 3 c, R -3 c} at ΔBIC −218 with five
testable positions all absent. `n_testable` is `int | None`, `None` until
`screened`, because the answer needs that fit
Depends on: — (found by WP-1067's `using/indexing.md` session, 2026-08-17)

## Goal

Establish what the intensity at corundum's forbidden positions actually is, and
either fix the absence test or record why the refutation is correct. Either way
the package gains the acceptance row that would have caught this: a rhombohedral
glide case, on real laboratory data, with an impurity in it.

## Context

**The measurement.** `determine_extinction_symbol` rejects the class the
specimen's certificate names. On the bundled IUCr round-robin corundum pattern
(`tests/data/qarr/corundum.prn`, NIST SRM 676a, α-Al₂O₃, **R -3 c**, Cu Kα,
7251 points over 5–150°), given the certified cell (a = 4.759355 Å,
c = 12.99231 Å, trigonal *R*) and `tests/test_acceptance_qpa_roundrobin.py`'s
`qarr_instrument()`:

| Protocol | `profile_rwp` | `R - c -` | verdict |
|---|---|---|---|
| whole range, declared widths | 0.287 | 5 of 15 testable forbidden positions carry intensity | refuted |
| 20–90°, widths from `workflow.seed_widths` | 0.149 | 2 of 9, first (2, 0, 5) at 56.919° | refuted, ΔBIC **−251** |

`ExtinctionScreen.best_or_none()` returns `R - - -` in both runs, whose members
are R 3, R -3, R 3 2, R 3 m and R -3 m. **The certified group is not in that
list.** This is not the package abstaining, which is what its design is for; it
is a wrong answer, and it is reachable from the workflow
`docs/AGENT_PROTOCOL.md` §7d prescribes.

Improving the shared profile fit halves the count and does not remove it, so
"the profile was badly modelled" is at most part of the story.

**Reproduction** (the exact script the numbers came from is not committed —
rebuild it; it is ~40 lines):

```python
data = rx.read_pattern(QARR / "corundum.prn")            # tests/data/qarr
ins = qarr_instrument()                                  # dispersion declined
peaks = rx.pick_peaks(data, ins)
seeded, _ = rietx.indexing.workflow.seed_widths(ins, peaks)
cand = CellCandidate(cell=(4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0),
                     cell_esd=(1e-4,) * 6, system="trigonal", centring="R",
                     lattice_group=fom.lattice_group("trigonal", "R"), volume=254.9)
screen = rx.determine_extinction_symbol(data, cand, seeded,
                                        two_theta_limits=(20.0, 90.0))
```

**What is already known about this specimen.** The same pattern's default
`index_pattern` run reports **49 `unmatched_observed`** lines against its own
top candidate, and `PEAK_NOT_SEPARABLE` / `PEAK_AXIAL_TAIL` /
`PEAK_KALPHA2_RESIDUAL` all fire on its peak list (8 / 11 / 1 components). So an
impurity line or an artefact landing on a forbidden position is a live
hypothesis, and `docs/AGENT_PROTOCOL.md` §7e already tells an operator to make
exactly that cross-check by hand. What it does not do is stop the screen from
answering.

**The mechanism, and which half is under test.** `src/rietx/indexing/`
`extinction.py` ranks classes by ΔBIC and Hamilton against the absence-free
reference, then applies the direct absence test at each class's own *testable*
forbidden positions, read against that class's own calculated pattern
(`workflow.absent_reflections`, with `ABSENT_SIGMA` and `ABSENT_WINDOW_FWHM`).
**One-sided refutation is deliberate and is not what this WP re-opens**
(`schemas/indexing.py`, `ExtinctionCandidate.refuted`): a class asserts
absences, so intensity at a position it forbids contradicts it, and ΔBIC cannot
buy that back. The question here is whether the *evidence* is sound — whether
those positions are testable in the sense the field claims (inside the range,
and separable from every line the class still allows) and whether the intensity
read there belongs to the reflection at all.

**No test covers this shape.** `tests/test_extinction_symbol.py` has three
real-answer rows: a synthetic monoclinic P 2₁/c, FAP (hexagonal, `P 63 - -`,
passes) and 11-BM NAC (cubic *I*, absence-free answer, passes). None is
rhombohedral, none is a glide on real laboratory data, and none carries an
impurity. Root CLAUDE.md's rule applies directly here: **choose an acceptance
dataset by space group**, the way SRM 660c (P m -3 m) was chosen to prove that
`predicted_but_absent` counts against the lattice group.

**Two rules from `tests/CLAUDE.md` bind the new row.** An eval's expected answer
is a measurement, so decide what the data supports *before* reading the grid;
and a wall-clock budget in a test is a runaway guard, never a timer (the screen
costs ~2–3 s here plus the profile fit).

## Non-goals

- **Not a re-opening of one-sided refutation.** If the evidence turns out to be
  sound, the finding is that this specimen violates its own class at two
  positions, and the answer is to say so in the chapter — not to let ΔBIC
  outvote a violated absence.
- **No new diagnostic without evidence.** If the absence test is admitting a
  position it should not, the fix is in the test, not a warning bolted beside it.
- **Not the indexing surface's stability tier** — that is
  [1078](1078-indexing-provisional.md).

## Tasks

- [x] Reproduce and **look at the pattern** — done, and the picture is the
      answer: both loud positions sit on the *low-angle flank* of a strong
      allowed line (2.76 and 1.49 FWHM below (1,1,6) and (3,0,0)), where the
      model's flank is visibly under the data. It is an axial tail, not an
      impurity: the peak list flags `axial_tail` on 11 components and
      `asymmetry_unmodelled` on 18, and the picker resolves the tail of each
      neighbour into its own flagged peaks 0.16-0.39° away.
- [x] Check the testability half — this is where it fails. `testable_mask` asks
      a question about *positions* and is blind to what is **in** the window;
      both flagged positions are separable by `_overlap_groups` and both windows
      are filled by a neighbour's tail.
- [x] Decide: **the evidence is wrong, and the fix is in the test** — the first
      of the three. The refutation is a measurement of the profile model.
- [x] Acceptance row in `tests/test_extinction_symbol.py`: two rows, the answer
      and the sham-probe control. **Neither is `slow` and neither carries a
      budget** — the screen costs 0.32 s here against FAP's 2.30 s setup, so a
      budget would be the load sensor `tests/CLAUDE.md` warns about. The module's
      existing `xdist_group("extinction-symbol")` covers them.
- [x] Docs: the chapter's two measured blocks, `AGENT_PROTOCOL.md` §7e's row and
      its point 3, `docs/releases/1.0.2.md` (§ What changed and § Upgrading — the
      headline "computes what 1.0.1 computed" is now true of a refinement and not
      of this call), and the rule in `src/rietx/indexing/CLAUDE.md`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction_symbol.py -q
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup   # engine-adjacent
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_docs_consistency.py
.venv/bin/python -m ruff check src tests examples
```

The extinction screen sits on top of the Le Bail path, so a change in
`extinction.py` or `workflow.absent_reflections` can move a measured number:
run the full suite once on the final tree.

## References

- WP-1067's 2026-08-17 handover entry — where this was measured, and the rest
  of that session's corundum numbers.
- `src/rietx/schemas/indexing.py`, `ExtinctionCandidate` and `ExtinctionScreen`
  docstrings — the one-sided rule, and what `best_or_none` requires.
- `src/rietx/indexing/CLAUDE.md` — "read `predicted_but_absent` as *this cell
  predicts lines the pattern lacks*", and why acceptance datasets are chosen by
  space group.
- `docs/AGENT_PROTOCOL.md` §7e — the operator-facing reading of
  `EXTINCTION_FORBIDDEN_INTENSITY`, including the impurity cross-check.

## Handover log

- **2026-08-18** — **closed.** All five tasks ticked; the WP's `### Inherited`
  never existed, so nothing was pruned. Venv `[dev]` only (no jax/torch),
  Python 3.12.12, macOS/arm64 — every number below is from that.

  **Reproduced first, and the Context table's numbers mostly hold.** Counts
  match exactly (5 of 15 testable over the whole range, 2 of 9 over 20-90°);
  `profile_rwp` re-measures at **0.270** for the whole-range arm, not 0.287.
  The 20-90° arm is 0.1492. Neither arm's answer depended on that.

  **The mechanism, in three measurements.** (1) *Where the loud positions are*:
  (2,0,5) at 56.919° sits 2.76 FWHM below the allowed (1,1,6) at 57.429°, and
  (2,0,−7) at 67.840° sits 1.49 FWHM below (3,0,0) at 68.135°. Both on the
  **low-angle** flank. (2) *The sham-probe control*, the decisive one: probing at
  fixed offsets from every allowed line, at positions where no reflection of any
  kind is predicted, the same 3σ test fires on

  | offset | −3.0 | −2.76 | −2.0 | −1.49 | −1.0 | +1.0 | +1.49 | +2.0 | +2.76 | +3.0 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | median σ | 1.66 | 2.26 | 2.99 | 2.51 | 2.36 | −1.04 | 0.05 | 0.27 | 0.05 | 0.11 |
  | frac > 3σ | 0.28 | 0.40 | 0.50 | 0.46 | 0.41 | 0.00 | 0.03 | 0.00 | 0.02 | 0.04 |
  | max σ | 13.2 | 16.8 | 22.2 | 24.7 | 16.5 | 1.5 | 4.6 | 2.8 | 4.2 | 3.6 |

  — loud below a line, silent above it, which names the unmodelled axial tail
  and nothing else. (3) *The profile is not the repair*: freeing FCJ
  `axial_sl` takes `profile_rwp` 0.1492 → 0.1440 and leaves one position
  refuting; freeing both `axial_sl` and `axial_hl` takes it to 0.1391 and both
  come back.

  **The discriminating statistic** is the class's own predicted intensity in the
  window, in units of the same propagated σ. Over the ten forbidden lines of
  `R -3 c` in 20-90°: the two loud ones carry **20.0** and **25.7** σ of
  neighbour tail; the seven the screen already read as absent carry 0.2, 0.7,
  2.7, 3.4, 2.0, 8.2 and 1.1; the tenth was already untestable. Requiring that
  number below `k_sigma` leaves five testable, all absent.

  **After.** 20-90° seeded: `best_or_none()` → `R - c -` = {`R 3 c:H`,
  `R -3 c:H`}, conditions `0kl: l = 2n` / `h0l: l = 2n` / `h-hl: l = 2n`,
  n_absent 10, n_testable 5, n_present 0, ΔBIC −218.37, class Rwp 0.1441 against
  the absence-free 0.1478, 35 lines over 3501 points.
  `EXTINCTION_GROUPS_NOT_SEPARABLE` names the centro/non-centro pair, which is
  the doctrine's cleanest real-data instance.

  **What is still wrong, and it is on purpose.** The whole-range declared-width
  arm still refutes (4 of 13). Its fitted FWHM comes out ~32 % too wide
  (0.247° at 60° against 0.188°), and at 56.929° the *observed* excess is
  +26.9σ against 0.27σ of predicted tail — a gross profile mismatch, not a
  tail. No calibration of the absence test reaches that (inflating σ by the
  fit's own gof 3.05 still leaves it at 8.8σ), so `profile_rwp` remains the
  field that separates the two, and both the chapter and §7e now say so with
  this pair as the measurement.

  **Counts.** `tests/test_extinction_symbol.py` 30 → **32 passed**, both new and
  both passes, **no new skips** — the whole of this session's delta, since the
  only other test file touched is a one-line repair (below) that adds nothing.
  `tests/test_acceptance_indexing.py` 44 passed, 25:29 — the engine-adjacent
  check the WP's acceptance block asks for, no ranking regression. Full suite on
  the final tree, **measured**: 1 failed / 2520 passed / 126 skipped, ~24 min
  (a range, not a figure — the same tree's indexing acceptance alone took 25:29
  on this machine today). The one failure is the WP-1076 leftover below; its file
  re-ran green afterwards (13 passed, 3:11), so the tree stands at **2521 passed
  / 126 skipped** by arithmetic rather than by a second full run, which is a
  bookkeeping question and CI's job.
  Fast selection (`-m "not slow"`, the handover gate): **2413 passed / 117
  skipped**, ~4 min. vitest 407 (one new assertion, no new test). `ruff` clean,
  sphinx `-W` clean. All on `[dev]`, Python 3.12.12, macOS/arm64.

  On the ±N check: this tree has no local baseline to difference against (CI's
  job), so the evidence for "+2 passed, 0 new skips" is the file-level
  measurement — `test_extinction_symbol.py` went 30 → 32, and the only other
  test file touched, `test_acceptance_sequential.py`, is `slow` and gained no
  test, so it is outside the fast selection and adds nothing to the full one.

  **The full suite found one failure and it was not this WP's.**
  `test_acceptance_sequential.py::test_series_exports` asserted
  `header[:3] == ["index", "label", "index"]` — the *pre*-WP-1076 header. 1076
  (commit `086fb387`, already on main) made the axis column fall back to `x`
  when `x_label` is already a column name and did not update this row, which is
  `@pytest.mark.slow` and therefore invisible to the fast suite that gated 1076's
  close. Repaired here rather than filed forward: it is one stale expectation
  with an unambiguous right answer, and left alone it would have reddened the
  nightly `full` job. This branch touches nothing under `sequential`/`series` —
  `git diff origin/main...HEAD --name-only` is the check.

  **CLAUDE.md audit.** One file edited, `src/rietx/indexing/CLAUDE.md`, and the
  rule went into § The governing rule rather than the rule list — it is doctrine
  (an answer must not rest on a null model that is not silent), not a war story,
  and the numbers live in `extinction.py`'s docstring. The file was at exactly
  its 280-line cap, so the two WP-1046 paragraphs were compressed to pay for it;
  every clause dropped was checked for a second copy first — the 5 s/30 s set-F
  timings and the "same defect in a cheaper disguise" reasoning are in v1.0.md
  § "1046 closed", the "cheap orthorhombic / expensive monoclinic" sentence is
  v1.0.md:893, and "single-digit harvests" is v1.0.md:4256 and 1046's own file.
  Nothing was deleted to fit.

  **Two things deliberately not done**, each a candidate for a successor.
  `determine_extinction_symbol` still only seeds widths when the caller passes
  `peaks=`; seeding from the data when it can would repair the whole-range arm's
  real defect, and `seed_widths` is already a no-op on a calibrated instrument,
  so it looks cheap — but it moves the shared pre-fit under FAP and NAC and is a
  behaviour change this WP did not scope. And `ExtinctionCandidate.n_present`
  keeps `int = 0`, so an unscreened class still says "no forbidden position
  carries intensity" about a question nobody asked; that is WP-1076's rule and
  1076 passed over it too.

- **2026-08-18** — created, from WP-1067's measurement. Nothing run here yet;
  every number above came from that session's ad-hoc script, so the first task
  is to reproduce them from something committed.
