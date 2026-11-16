# WP-1447 — a threshold each pattern sets for itself

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
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

- [ ] The control, deterministic: a fixed grid of ratios excluding the
      near-unity band and a margin around each real ghost ratio, derived from
      the anode rather than hard-coded, since the exclusions move with λ.
- [ ] The permutation p-value, with K and α named constants carrying their
      measured basis, and a floor so a degenerate control cannot lower the bar
      below what a reader would accept as evidence.
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
  439-441 — the (r+1)/(K+1) Monte Carlo p-value, and why the naive r/K is
  biased.
- Davison, A. C. & Hinkley, D. V. (1997), *Bootstrap Methods and their
  Application*, §4.4 — Monte Carlo tests.
- Hölzer et al. (1997), *Phys. Rev. A* **56**, 4554, Table VI — the 0.14 an
  unfiltered tube leaks, which is what the floor has to catch.

## Handover log

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
