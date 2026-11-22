# WP-2232 — A size near no broadening is quoted as a bound

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 2060 soft (the profile interval and its one-sided cut)
Priority: P3 2026-11-21 — a well-crystallised sample is common; its size reads as a symmetric ± esd where the data give only a lower bound, and nothing says so

## Goal

A crystallite size or microstrain derived from a width coefficient near zero is reported with an
interval that covers. Where the data cannot exclude no broadening, a size reads as a lower bound
and a strain as an upper bound, never as value ± esd.

## Context

**Where it came from.** The maintainer's best-practice review of the width parametrisation
(2026-11-21, the session behind PR #1743). rietx refines sample broadening as coefficients that
enter the peak shape linearly: `gauss_size` and `gauss_strain` in deg² of Gaussian variance,
`lor_size` and `lor_strain` in deg of Lorentzian FWHM, all bounded at 0. FullProf, RIETAN-FP and
BGMN do the same (`docs/practice.md` § What a refined parameter is). The survey found the
parametrisation sound and kept it. This WP is the one gap it found.

**The mechanism.** `model/microstructure.py:_reading` converts a coefficient to a size or a strain
after the fit. It returns `at_zero` when the coefficient sits on its floor (line 85). Above the
floor it returns value ± a one-parameter esd (line 97): σ_c/c for a FWHM coefficient and
σ_v/(2v) for a variance, since the FWHM is √v. That linear propagation is exact for a derived
quantity of one parameter near its value. It fails near zero. As c or v approaches 0, the relative
esd grows without limit. The true interval is one-sided: a size's upper end can be infinite, and a
strain's lower end is 0. So a coefficient one or two esd above its floor gives a symmetric ± that
reaches into sizes the data exclude and hides the open end.

**What already exists.** `Refinement.profile_interval` (`refine.py:4885`,
`strategy/parameter_interval.py:399`) pins a value, refits the rest and walks until Δχ² crosses
its cut. It carries the one-sided ½χ²₀ + ½χ²₁ cut of Self & Liang (1987) for a parameter bounded
at its null value (`parameter_interval.py:7-26`). A profile interval on the coefficient maps
through the monotone conversion L = Kλ/c to an interval on the size, with no further refits.
Today it runs automatically only for moment angles (WP-1929, WP-2060).

**The caution from WP-2060.** Its coverage table measured the profile interval on a width,
`profile.y` with W 30 % too large: 0.74 against a nominal 0.95, where the Wald interval covered
1.00. So under a misspecified model the profile on a width can mislead, which is why WP-2060
left widths with the flag alone. This WP must measure coverage on width coefficients before
choosing a rule, on a correct and on a misspecified model.

**Practice.** GSAS-II refines size and mustrain directly and reads their esds off the refined
variable (`GSASIIstrIO.py:3530-3549`). TOPAS propagates a dependent parameter's esd through the
full covariance (Technical Reference §2.17). Neither reports a bound near no broadening (checked
in #1743's survey). Outside diffraction, MINUIT's MINOS and lme4's profiling are the standard
intervals near a boundary, and a variance at 0 is tested with the χ̄² mixture (Self & Liang 1987;
Stram & Lee 1994).

## Non-goals

- Changing the parametrisation. The coefficients stay (#1743's survey).
- A coefficient on its floor. It already reads `at_zero`.
- The moment and aperture cases. WP-2060 and WP-1955 own them.

## Tasks

- [ ] Coverage probe, registered before it runs: a synthetic family with known size near the
      instrument's resolution, and one with known strain near 0, at N ≥ 200 Poisson replicates per
      cell. Compare the delta-method interval, the profile interval on the coefficient mapped to
      size, and the one-sided bound from the χ̄² cut. Run each on a correct model and on one with
      the instrument width misstated by 30 %, as WP-2060's width cell did.
- [ ] Measure on real data: SRM 660c and 11-BM NAC with size and strain freed, printing each
      derived size, its esd and the profile interval.
- [ ] Choose the rule by its kind (DESIGN.md § Rules 1 and 4) from the probe. The maintainer
      approves any new default and the reader-output change.
- [ ] Implement the chosen rule in `microstructure.py`. A size whose interval reaches no
      broadening carries its lower bound and no ± esd. A strain likewise carries its upper bound.
- [ ] `help.py`, the manual's microstructure page, the skill's reference row, an `_audit` row for
      any threshold, and the reader-output diff (`python -m tests.reader_output`).

## Acceptance

On the coverage family, the reported interval covers at the nominal level within its binomial
band on the correct model, and the misspecified cell's coverage is stated beside it. A size whose
coefficient interval reaches 0 prints as a lower bound.

```sh
.venv/bin/python -m pytest tests/test_microstructure.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Langford, J. I. & Wilson, A. J. C. (1978). *J. Appl. Cryst.* 11, 102-113 (the Scherrer constant
  per width measure; 0.90 for the FWHM as a first approximation, size as the cube root of the
  crystallite volume).
- Self, S. G. & Liang, K.-Y. (1987). *J. Am. Statist. Assoc.* 82, 605-610.
- Stram, D. O. & Lee, J. W. (1994). *Biometrics* 50, 1171-1177.
- WP-2060 (the profile interval's coverage table and its width caution).

## Handover log

- **2026-11-21** — created from the maintainer's review of the width parametrisation
  (PR #1743). No open WP owns a derived size or strain near zero: WP-2060, now closed, left
  widths with the flag alone after its width coverage cell, and WP-2061 owns the hkl-dependent
  size shape, not its interval.
