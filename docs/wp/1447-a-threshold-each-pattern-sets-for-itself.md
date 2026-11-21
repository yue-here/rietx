# WP-1447 — a threshold each pattern sets for itself

Milestone: unscheduled · Status: 🔄 2026-11-16 — the control and its p-value landed (#1609); whether
the screen reads them by default, and with which numbers, waits on the
maintainer (#1615)
Track: What fires, and what stays silent
Depends on: — (1442 soft)
Priority: P3 2026-09-23 — a threshold that works on copper and is not the pattern's own

## Goal

The contamination screen's threshold comes from the pattern in front of it
rather than from a constant calibrated on sixteen copper patterns.

## Context

Filed 2026-09-22 with the maintainer, who chose **not** to build it now: the
fixed bar measured at zero false findings over 2 656 control draws, so this is
an improvement in *provenance* rather than a fix. Everything below was measured
while deciding that, on `75ac934a`.

**What ships today.** `background.diagnostics.GHOST_MIN_PARENTS = 5`: a
contamination is reported only when five of the eight strongest reflections
carry a line at their predicted Kβ (or W Lα) position at one common ratio.

**How 5 was set.** Against a control that asks the same question at wavelengths
which are not an emission line of anything, so any agreement is coincidence.
2 656 draws (16 round-robin patterns × 166 wavelengths): the control's maximum
is **4**, none reaches 5, and the real Kβ reaches 2 on the worst of them. An
injected Kβ image scores at least 6 at r = 0.10 across six hosts. One count of
margin on each side.

**Why the number is still soft.** Three reasons, all measured.

- Every one of those patterns is Cu Kα laboratory data from one round-robin
  plus one NIST set, because the bundled corpus has no other anode the check
  even runs on. Nothing says the coincidence rate is the same on a different
  instrument, and a per-pattern control would not need it to be.
- The rate is a strong function of how many candidates the pattern offers. On
  the ungated channel census the same bar of 5 was crossed by chance on 6 of
  16 fixtures; it works only because WP-1442 narrowed the pool with a
  prominence gate. That is the bar depending on something other than the rule.
- Per pattern the control's own maximum runs from 1 (fluorite, 17 usable
  lines) to 4 (brucite, cpd-1b, cpd-2). A single constant is the worst case
  applied to every pattern, so sparse patterns are screened far more strictly
  than their own data require.

**The control has to exclude a band, and this is the part to carry.** Above
≈0.98·λ(Kα1) a made-up wavelength puts the predicted companion on top of its
own parent, where it matches the parent's own Kα2 partner. That is
self-matching, not coincidence: inside that band alone the control's mean rises
from 0.50 to 3.95 and its maximum from 4 to 8. A first calibration that swept
into it reported a false rate of 1.3 % and had to be withdrawn. The real ghost
ratios sit at 0.904 (Kβ) and 0.958 (W Lα), well clear. WP-1442's handover
names the script that draws the control against the ratio, which shows the
band as a wall at the right-hand edge of an otherwise flat line.

**What it costs.** Measured: fitting the 16 peak lists takes 496 ms each; 40
control wavelengths on top of an existing line list take **1.4 ms**, 0.29 % of
the fit they ride on. 200 draws is ~7 ms, ~1.4 %. The control reuses the
candidate list, so there is no second peak fit.

**The form.** A Monte Carlo permutation test rather than a maximum, because a
maximum over N draws grows with N and would make the threshold a function of
how many draws were taken. p = (1 + #{control ≥ observed}) / (1 + K), report
when p ≤ α. At K = 199 the smallest achievable p is 0.005.

## Non-goals

- Changing what the screen looks for, the ratio window, or the prominence gate
  on the candidate pool. All three are WP-1442's and measured.
- Removing `GHOST_MIN_PARENTS`. A floor under the adaptive threshold is still
  wanted, or a pattern whose control never reaches 2 could report on two
  agreeing reflections.

## Tasks

- [x] The control, deterministic: a fixed grid of ratios excluding the
      near-unity band and a margin around each real ghost ratio, derived from
      the anode rather than hard-coded, since the exclusions move with λ.
      *`_ghost_control_ratios`: `k` ratios over the admitted part of a `span`,
      each exclusion an exact interval per parent around five anode-derived
      positions (the parent, its Kα partner either side, Kβ, W Lα) one
      matching window wide; no margin or grid step is a new number. The
      near-unity band is cleared on the 16 round-robin patterns, not in
      general: see the PR review in the 2026-11-16 entry.*
- [ ] The permutation p-value, with K and α named constants carrying their
      measured basis, and a floor so a degenerate control cannot lower the bar
      below what a reader would accept as evidence.
      *Machinery landed: `ghost_p_value`, `ghost_control` → `GhostControl`
      (`p_value`, and `decide(alpha=, floor=)`). K, α, the span and the floor
      are the caller's arguments, not named defaults, and the screen does not
      read them: a named default is a new `_audit` row, and a tier-3
      `approved` date is the maintainer's (ruled 2026-11-01). The measured
      recommendation and the question are in the 2026-11-16 entry.*
- [ ] Re-measure WP-1442's whole table under it: the 17 monochromated patterns
      (must stay silent), the six-host injection ladder (the floor may move —
      report where it lands rather than assuming it improves), the demo
      notebook's pattern, the BT-1 neutron pattern, `FAP.XRA`.
- [ ] The cost on the shortest fit, not the typical one (root CLAUDE.md's rule
      for a per-stage charge, and the same argument applies here).
- [ ] `INDEXING_THRESHOLDS_VERSION` if the answer of `pick_peaks` can move, and
      the manual and skill rows that quote a fixed "five of the eight".

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_peak_picking.py
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- WP-1442 (the screen, the control, and every number above).
- North, B. V., Curtis, D. & Sham, P. C. (2002), *Am. J. Hum. Genet.* **71**,
  439-441, doi:10.1086/341527 — the (r+1)/(K+1) Monte Carlo p-value, and why
  the naive r/K is biased. Erratum: (2003), *Am. J. Hum. Genet.* **72**,
  498-499, doi:10.1086/346173.
- Davison, A. C. & Hinkley, D. V. (1997), *Bootstrap Methods and their
  Application*, §4.4 — Monte Carlo tests.
- Hölzer et al. (1997), *Phys. Rev. A* **56**, 4554, Table VI — the 0.14 an
  unfiltered tube leaks, which is what the floor has to catch.

## Handover log

### 2026-11-16 — the control and its p-value, built and not switched on

Each pattern can now be screened against its own coincidences. A caller hands
the screen's peak list to a new function and gets back, for each ghost search,
how many strong reflections agree at the real Kβ or W Lα position, the same
count at about two hundred made-up wavelengths that no line can sit at, and
how rare the real count is among them. On the sixteen round-robin patterns the
real wavelength is never rare (smallest p 0.125), and an injected Kβ image at
10 % is always the rarest (p = 0.005, the floor of the test). The screen itself
is unchanged and no picked peak moves, because the level, the number of
wavelengths and the floor beside it are the maintainer's to set. One case shows
why the floor matters: on zircon with a Kβ image, the W Lα search gathers three
parents at p = 0.005 on a line that is not there.

*Premise* (checked first, on `bc77a934e`): `GHOST_MIN_PARENTS = 5` is still a
fixed constant in the screen, and `ghost_searches` (WP-1445) now skips a
declared monochromator, which the round-robin fixtures do not declare. Still
open: the maintainer chose on 2026-09-22 not to build this, with "a pattern
from a different instrument class" as the trigger to revisit. The session took
up tasks 1-2. This entry builds the machinery and leaves the
default to the maintainer, which keeps that decision where it was.

*Done*:
- Task 1: `_ghost_control_ratios`. The exclusions are exact intervals in
  ratio, one per parent and per line, around five positions read off the
  anode table: the parent, its Kα partner either side, Kβ and W Lα1. Each is
  one matching window wide, using the list's own largest esd. No margin, band
  edge or grid step is a new number.
- Task 2, the machinery only: `ghost_p_value` (North, Curtis & Sham 2002),
  `ghost_control` → `GhostControl` (`p_value`, `decide(alpha=, floor=)`). A
  control ratio is compared only where it searched at least as many parents as
  the real ratio did, so ratios whose companions fall off the range cannot
  make the observation look rare. `_ghost_parent_rank` is factored out of
  `_ghost_candidates` with no change in behaviour. Task 2 stays unticked:
  K, α, span and floor are arguments, not named constants.
- 13 tests in `test_background_auto.py` (14 with the review's limit row,
  below). Each control has a positive arm:
  removing the self exclusions fails 7 of them. The near-unity row checks that
  a naive sweep reaches ≥ 5 on the fitted list before asserting the control
  stays at ≤ 2.

*Measured* (`[dev]` venv, macOS arm64; throwaway scripts, not committed, ~60
lines each over `_ghost_candidates`/`_ghost_consensus` and `pick_peaks`):

| arm (16 patterns, k=199, span 0.80-1.0) | census pool | fitted list |
|---|---|---|
| clean, Kβ: smallest p | 0.145 | 0.125 |
| clean, W Lα: smallest p | 0.210 | 0.270 |
| Kβ image r=0.05: p ≤ 0.01 | 16/16 (brucite, magnetite at 3 parents) | 15/16 (magnetite 2, p 0.035) |
| Kβ image r=0.10 / 0.15: p | 0.005 on all | 0.005 on all |

- **The near-unity wall, measured again:** a naive sweep of the fitted list
  has a chance mean of 0.55 in the bulk, 2.03 in 0.990-0.995 and 4.35 above,
  with a maximum of 8. It starts at about 0.99, not 0.98. The census pool
  shows no wall at all. Admitted control ratios ≥ 0.95 reach at most 2 on
  both paths. This is measured on these 16 patterns, not derived (review,
  below): the parent and its Kα partner can never be candidates, since their
  intensity ratios lie outside `GHOST_RATIO_RANGE`. What the parent's own
  exclusion removes is weak flank lines 0.11-0.18° below each parent, one
  matching window away.
- **Cost:** `ghost_control` at k=199 takes 6.8-7.6 ms on fluorite's 18-line
  list and 8.1-8.5 ms on cpd-4's 113 lines (macOS arm64, five runs each).
- **Zircon, Kβ image 0.10, fitted:** the W Lα search reaches 3 at p = 0.005
  against a control maximum of 2. The fixed bar is silent on it.

*Gates*, on cb8ca426d (Linux x86_64, the workstation's `rietx-py312` venv):
- Canary: 223 passed (background_auto, peak_picking, audit_table, help,
  docs_consistency; `-n 4`).
- Fast suite (`-m "not slow"`, `-n 4`): 14864 passed, 280 skipped, 32 xfailed,
  0 failed, in 25:34 beside co-tenants. Main was not re-measured, so the +13
  is not checked against a baseline here.
- The 13 added cases cost 6.5 s in that run, led by the zircon row at 3.5 s
  (one `pick_peaks`).
- On the Mac (`[dev]`, arm64): `reader_output` exit 0 (unchanged), ruff
  clean, `test_manual_api` 19, `test_audit_table` 23, `test_capabilities` 43
  and `test_docs_consistency` 26 passed.
- No slow selection: no engine or acceptance path is touched.

*Review*: a read-only subagent in the worktree (the runner rules forbid
`/code-review`).
- Applied: `span` must be finite (an unbounded span filled the control with
  free zeros); control ratios are matched by parents searched; the exclusion
  window takes the list's own largest esd instead of the cap; `k` validation;
  and docstring corrections (what the control cannot exclude, the p-value as a
  rank over a correlated grid, cost, a truncated comment).
- Recorded, not fixed: W Lα2, the Kβ image of a Kα2 component, and a leak's
  images of non-parent lines are not excluded. Two test rows sit with zero
  margin: corundum at its bar of 2, and zircon's W Lα with 3 against 2. Both
  passed on Linux x86_64.
- PR review (#1609), the known limit: the near-unity wall is closed on these
  16 patterns by where their flank lines sit, not by derivation. Eight
  parents between 24° and 33°, each with a 10 % line 0.20° below it, reach 8
  at admitted control ratios (9 of 199 reach ≥ 5). With a real Kβ image at
  10 % added, the fixed bar reports the leak and `decide(alpha=0.01,
  floor=5)` does not: p = 0.015, since the control's maximum is also 8. A
  loss of power, not a false alarm, on a pattern whose strongest lines sit
  in a narrow low-angle band. Pinned by
  `test_flank_lines_outside_the_exclusions_reopen_the_wall`; it bears on
  the #1615 decision. Not fixed here: one route excludes companions within
  one window of any placed line that itself lies within one window of a
  parent (the screen's own window, no new number); another bounds the
  span's upper end per pattern.
- *Generality*: no `_audit.py` change, and no number added to a default
  path. Every new knob is a required argument, so the judge was not
  dispatched.

*Gotchas*: the census pool does not show the near-unity wall that the fitted
list does, so a test of the control has to use the fitted list to fail.

Next: the maintainer's answer on #1615 (option (a): floor 5, α 0.01, K 199,
span 0.80-1.0, which moves no answer measured here but loses the
narrow-band leak above; or a lower floor). Then
wire it into `_ghost_screen` with named constants and audit rows, and work
tasks 3-5 in order. Task 3's table decides whether task 5's version bump is
owed.

### 2026-09-22 — filed, deliberately not built

The contamination screen reports only when five of the eight strongest
reflections agree. Five was measured, against a control that asks the same
question at wavelengths which cannot exist, and it separates cleanly: the
control never reaches 5 in 2 656 draws, and a real leak at 10 % scores at least
6. What it does not have is generality — every pattern behind it is copper
laboratory data from one instrument class, and the rate depends on how many
candidate peaks the pattern offers, which varies by a factor of five across the
corpus. Letting each pattern run its own control removes both dependences and
costs about 1.4 % of the peak fitting already being done.

The maintainer's call was to keep the constant and file this, on the grounds
that zero false findings in 2 656 draws is what the threshold was asked for.
Revisit it when a pattern from a different instrument class arrives, which is
the condition the evidence does not cover.

*Gotcha worth more than the rest*: the control is only fair away from Kα1. The
first calibration swept to 0.997·λ(Kα1), where the predicted companion sits on
its own parent, and reported a false rate of 1.3 % that does not exist. Any
re-measurement here inherits that trap.
