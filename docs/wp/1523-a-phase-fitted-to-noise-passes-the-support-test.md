# WP-1523 — A phase fitted to noise passes the support test

Milestone: unscheduled · Status: 🔄 2026-10-04 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: — (1420 soft: the same hold, in a chain)
Priority: P2 2026-09-29 — a frame with no phase in it reports that phase's cell with an esd and no `PHASE_UNCONSTRAINED`, depending on where the fit started; a path few fits run

## Goal

A phase the pattern does not contain is held, and named by
`PHASE_UNCONSTRAINED`, whatever the fit started from. A phase fitted to noise
no longer counts as one the data can see.

## Context

Found by WP-1469 on issue #481's blank frame: every phase scale 0, so the
pattern is background and Poisson noise alone. The frame is pattern 7 of the
issue's script, and the reproduction under References rebuilds it from the
same RNG stream.

**One ordinary fit, no chain.** The blank was fitted cold with
`mccusker_default` from two starts, 2026-09-29 at `a651a7d` (Linux x86_64,
Python 3.12, `[dev]`):

| start | cell held in stages | cell reported | scale | `PHASE_UNCONSTRAINED` |
|---|---|---|---|---|
| pattern 0's fitted models (scale 5e-4) | `cell` only, released at `profile_w` | 4.14990 ± 0.0016 Å, 0.0085 Å off the ramp | 3.1e-8 ± 2.4e-8 | no |
| the issue's unfitted models (scale 7.5e-4) | `cell`, `profile_w`, `profile` | absent (held) | 1.7e-8 ± 2.5e-8 | yes |

**Why.** `CompiledModel.phase_support` is each phase's strongest modelled
point in σ of the observation noise, and `PHASE_SUPPORT_SIGMA` is 1.0
(`model/forward.py`). At the first row's answer the blank phase's support is
**2.14σ**, while its scale is 1.3σ from zero: a scale fitted to noise lifts
the strongest point above one σ, so the phase reads as seen.
`_released_phases` (`refine.py`) releases a held column when any phase it
moves rises above that threshold at the stage's landing values, and the
diagnostic reads the same vector. Which side of 1σ a noise fit lands on
depends on the start, which is the flicker.

Relevant rules, restated:

- **Root CLAUDE.md, "A phase the data cannot see is a flat direction"
  (WP-1301).** A phase is held for the stage rather than bounded, and its
  support is re-measured at the answer. A phase that appeared is released;
  one that collapsed while solving is restored and held. `phase_support` is
  the one authority for both the bound and the diagnostic, so a change to
  what "seen" means changes both together.
- **The threshold's docstring calls 1σ "not a tuned fraction"**: it says the
  comparison is against the counting statistics the phase competes with. The
  finding here is that a single-point statistic is exceeded by a fit to pure
  noise. Before changing the number, ask what the right statistic is: the
  scale's own significance, a multi-point measure, or the strongest point
  judged against what noise alone produces.

**A second failure mode of the same statistic is already on record**, in
WP-1339's Inherited (issue #219): a phase collinear with another, absent from
the specimen, read 0.65σ, 197σ or 54-56σ support depending only on its seed,
and at 57σ took the misfit with no `PHASE_UNCONSTRAINED`. That is the ridge
case; this one is the noise case. Both say `phase_support` depends on where
the fit landed, and a replacement statistic should be checked against both.

**Why a new WP rather than a fold.** 1420 owns the hold inside a chain and
fences out "`PHASE_SUPPORT_SIGMA`, or the package deciding whether a phase is
present" in its Non-goals, which is this WP's whole subject. 1339 owns the
localisation statistic and carries the #219 finding only as context.

### Decided 2026-10-04: the scale's marginal significance, at 3σ

**A phase is seen when its scale is 3σ from zero by its marginal esd**, the
esd taken over every column that can move with it: the stage's free columns
and the phase's own held structural columns. Three is
`indexing.workflow.ABSENT_SIGMA`, the multiple of its propagated σ a line's
net intensity must reach to count as present. `PHASE_SUPPORT_SIGMA` cited that
constant as "the same footing" while testing one point's height at 1σ.

**Why no statistic of the modelled curve can do it.** Under the null the
phase's cell, widths and displacements are unidentified, so the fit chooses
them to match the noise (Davies 1977, a nuisance parameter present only under
the alternative). Any function of the fitted curve is then inflated by that
choice. The scale's marginal esd counts the same freedom to first order.

Issue #481's frame at `origin/main` 69a1afc7, re-drawn over seeds (`[dev]`,
macOS arm64). Twenty blank fits (seeds 100-109, each from the two starts of
the table above) and sixteen weak real phases. Each count is the fits whose
phase read as seen, with the fit run under the rule named:

| Planted scale | max(y/σ) ≥ 1, today | ‖y/σ‖₂ ≥ 3 | Marginal z at the answer, either run | Cell error when refined |
|---|---|---|---|---|
| 0 (blank), 20 fits | 9 released, cell off up to 0.02 Å | 6 released, one cell off 0.24 Å | 0.00-2.75 | — |
| 3e-8, 8 fits | 6 | 6 | 0.0-3.4 | ≤ 1.1e-3 Å |
| 6e-8, 8 fits | 6 | 6 | 0.0-3.3 | up to 4.2e-3 Å |
| 1.2e-7, 8 fits | 8 | 8 | 4.2-5.0 | ≤ 1.2e-3 Å |
| 2.5e-7, 8 fits | 8 | 8 | 9.4-11.9 | ≤ 3e-4 Å |

The integrated norm ‖y/σ‖₂ is the scale's *conditional* z (everything else
held), and on the blank it reached 3.1-4.4 once a released cell had chased the
noise. Row 1 of the table above reads 2.06 marginal even after the chase. A
phase at 3e-8 to 6e-8 reads as unseen under the new rule. Its cell was off by
up to 1000 ppm when refined, so holding it is the honest answer.

**Where each reader gets it.** A Jacobian exists at a stage's answer and at the
end, and nowhere else.

- `phase_support` stays the cheap screen and becomes ‖y_p/σ‖₂, the
  conditional z. It bounds the marginal z from above, so a phase under 3σ
  there is unseen with no Jacobian. The stage-start hold and the cell window
  read it.
- At the answer the collapse and the release read the marginal z, and the
  release counts the held columns too, so a held cell cannot make the phase
  look better determined than it would be free.
- `PHASE_UNCONSTRAINED` and the width census read the final marginal z.
- `reflection_support` and `extra_peak_support` become the window norm
  against the same 3σ. That is `ABSENT_SIGMA`'s own test on a line.

*Revised the same day, from the landing's fixtures.* The rule above fixed
the blank frame and broke 12 fast tests in two ways. **The esd is taken
against counting noise**, from (JᵀWJ)⁻¹ with neither √χ²_red nor the
Bérar-Lelann factor. With both, a misfit anywhere made a present phase read as
absent: LaB₆ under two dead channels read 2865σ on the screen and 0.23σ by the
reported esd, and CaF₂ seeded 1.2 % off its cell read 6.74σ against 0.65σ.
**Displacement and occupancy columns are left out of the marginal**, because a
column that only rescales intensities says how the intensity splits between it
and the scale, not whether the phase is there. Kept in, the fluorite of
`tests/test_scale_b_ridge.py` read 153.7σ on the screen and 0.02σ marginal.
Three column sets were measured, each with the unscaled covariance:

| Set | Blank seen, of 20 | 3e-8 | 6e-8 | 1.2e-7 | 2.5e-7 | Misfit and ridge fixtures |
|---|---|---|---|---|---|---|
| scale and cell only | 4 | 6/8 | 6/8 | 8/8 | 8/8 | pass |
| every column but displacement and occupancy (**landed**) | 1 | 1/8 | 5/8 | 8/8 | 8/8 | pass |
| every column | 1 | 1/8 | 5/8 | 8/8 | 8/8 | ridge fails |

The one blank the landed set calls seen is seed 103 from the unfitted start,
its cell 13.4e-4 Å off.

**Not generalised, deliberately.** A joint fit (`multi.py`) keeps the screen
alone, because WP-1341 owns its report. Le Bail and Pawley fix the scale, so
the screen is all they read. The ridge case of WP-1339's Inherited (#219) is
for 1339. The marginal z is the statistic that could see it, and this WP does
not measure it there.

## Non-goals

- The chain-level consequences. 1469 already leaves a pattern above the Rwp
  fence out of the step scan, and 1420 owns a held phase re-entering a chain.
- Retuning `PHASE_SUPPORT_SIGMA` by eye. Whatever replaces the test is
  measured on the suite's absent-phase fixtures (`tests/test_absent_phase.py`,
  `tests/test_held_phase.py`) as well as on this frame.

## Tasks

- [x] Reproduce both rows in a test from a synthetic blank frame, and record
      the support and the scale significance at each stage's landing values
      (`tests/test_phase_significance.py`, each test's docstring).
- [x] Decide the statistic, recorded here with the measurement that chose it
      (§ Decided 2026-10-04). What moves on the fixtures is counted with the
      landing, in the handover entry.
- [x] Land it in `phase_support` (or beside it, as the one authority both
      consumers read), so the hold and `PHASE_UNCONSTRAINED` agree:
      `phase_support` is the screen, `refine._answer_significance` the test.
- [x] Tests: the blank frame holds its cell and fires `PHASE_UNCONSTRAINED`
      from both starts; a weak but real phase is still released.
- [x] Skill: the `PHASE_UNCONSTRAINED` row, if its meaning moves; otherwise
      "none", said here. It moved: `references/abstention.md`'s row states
      the 3σ significance, and `judging.md`'s QPA-scan note names the constant
      in place of "1σ".
- [ ] The stage-start hold reads the previous answer's significance, not the
      screen alone. Today a phase whose screen passes 3σ while its marginal z
      does not is freed at every stage start. It chases the noise, collapses,
      is restored and solves again, so it pays one extra solve per stage and
      can trip `CELL_RUNAWAY` on the way (review of 2026-10-04, item 4). Seed
      107 of the sweep shows it on the last stage of `mccusker_default`. A
      longer plan shows it per stage. Measure the solves saved, and count what
      moves on the absent-, held-phase and scale-B fixtures.

## Acceptance

Issue #481's blank frame, fitted alone from either start, reports no cell for
LaB6 and carries `PHASE_UNCONSTRAINED`; the suite's absent- and held-phase
tests pass unchanged or with each moved assertion justified here.

```sh
.venv/bin/python -m pytest tests/test_absent_phase.py tests/test_held_phase.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #481 (the ramp and its script); WP-1469's handover (where this was
  found); WP-1301 (the hold), WP-1458 (`phase_support` per emission line).
- The reproduction, run from the repo root:

  ```python
  # the issue's script to its first fit, then pattern 7 alone
  ref = rx.Refinement(first.fitted_structure, first.fitted_instrument)
  r = ref.fit(patterns[7], plan="mccusker_default")
  [(st.name, st.held, st.released) for st in r.stages]
  ```

## Handover log

- **2026-09-29** — created, from WP-1469's session. Both rows of the table
  measured at `a651a7d`; the support at the answer (2.14σ) was read by
  compiling the fitted models and calling `phase_support` on them. Next:
  task 1, then the decision in task 2, which is the whole WP.
