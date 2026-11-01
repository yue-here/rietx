# WP-2060 — the likelihood interval where an esd cannot be read as one

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-26 — two wrong statements with nothing fired: a weak modulus beside a zeroed angle covers 0.83 at a nominal 0.95, and a modulus on a dead column reads ± 10⁴ μ_B while `profile_interval` returns a zero-width interval; both on the magnetic path few fits run

## Goal

A modulus whose site's angles left the covariance, and a modulus sitting on its dead column at m = 0, each carry a likelihood interval that covers, and `profile_interval` never returns a zero-width interval for a parameter the data barely constrain. Whether the interval runs by default on bound rows of the kinds people quote as limits (phase scale, occupancy, moment modulus) is ruled and, if yes, done.

## Context

**Where it came from.** Issue #1075 (2026-10-20, an outside contributor): a coverage study on simulated data (known truth, Poisson noise, N = 200-500 replicates per cell, main `afce00a4`, macOS arm64, numpy, LM). Its repro 1 (the FCJ apertures) went to WP-1955; this WP carries the rest.

**What exists.** `Refinement.profile_interval(data, path)` (`strategy/parameter_interval.py`) pins a value, refits everything else (`trial.run_stage(..., Stage("interval:…", []), **trial._plan_settings)`), and walks each side outward by 1, 2, 4, … esd until Δχ² passes the χ²₁ cut scaled by χ²_red·f², then solves the end to a thousandth of an esd. WP-2002's B2 ruling (option 2, 2026-10-19, `docs/wp/2002-batch/rulings.md:86-95`) runs it automatically on the answer stage for each moment angle the stationary-angle test zeroes, and keeps that test's effect on the other esds. `RefinedParameter.interval` carries the result. `_auto_intervals` (refine.py:2343) is the switch a trial clears.

**The reporter's coverage (nominal 95 %), as measured on `afce00a4`:**

| row | truths | Wald (value ± 1.96 esd) | profile | flat-prior posterior |
|---|---|---|---|---|
| interior control (cell a) | — | 0.978 | 0.978 | 0.978 |
| minor-phase scale, `min=0` | 0, 1σ, 2σ | 0.99, 0.99, 0.99 | 0.99, 0.975, 0.99 | 0.935, 0.975, 0.98 |
| O occupancy, `max=1` | 1.00, 0.97 | 0.985, 0.98 | 0.985, 0.98 | 0.985, 0.98 |
| one magnetic site, m = 0 | — | **0.745** on the 98 fits with a usable esd | none (zero-width) | 0.975 |
| width `profile.y`, W 30 % too large | at 1σ | 1.00 | **0.74** | 1.00 |

Moduli beside zeroed stationary angles (`test_stationary_moment_angle`'s two-site set, N = 400): the weak site (Mn2, 0.7 μ_B) covers **0.830 [0.790, 0.866]** with the conditional esd and 0.973 with the profile; 67 of 68 misses have the estimate above the truth, along the m·cos φ valley. The full covariance (zeroing off) covers by being 100-500× wider.

What it says: where the flag fires and the model is right, every rule covers, so a default interval on scale or occupancy adds information and fixes no coverage. On a width at a floor under a misspecified model the profile is the one that misleads (0.74), which is why widths, FCJ apertures and Biso keep the flag alone. The two cells that fail are moment cells.

**Re-measured in the 2026-10-26 triage on `c0e32ab29`** (the reporter's repro 2, unchanged but for the current API): seeds 3, 4 and 8 each end `converged` with m = −4.9e-7 ± 1.24e5, −5.9e-7 ± 1.74e4, −4.2e-7 ± 1.52e4 μ_B, `at_bound` False, no diagnostic in `result.diagnostics`, and `profile_interval` returns [v, v] with `fit_is_minimum=True` after 10 refits. `FitReport.magnetic` does say `supported=False` (|m| under 3 esd). The mechanism: intensity goes as m², so the modulus column vanishes at m = 0 and the esd-scaled walk cannot find the end. The same zero-width answer appears on the FCJ axial ratio at 0 (#1075's repro 1, WP-1955): `profile_interval("instrument.geometry.axial_sl")` returns [0.0, 0.0] with `fit_is_minimum=True` while one TRF stage drops χ² by ~1 200 χ²_red·f². So the step fix here is the class, and WP-1955's column fix does not make it unnecessary.

**Phase scale's profile changes its free set.** `profile_interval`'s pinned refits are stages, and a stage re-decides WP-1301's hold of a phase the data cannot see from the pinned values. Pinning a weak phase's scale higher makes it look supported, so its cell is freed. The reporter measured `fit_is_minimum=False` on 5-19 % of such fits with the lowest point 1.2-2.7 (up to 6.4) χ²_red·f² below the fit, while a TRF refit from the fit moves nothing. Read from the code at `c0e32ab29` (`parameter_interval.py:209-236`): each refit is `trial.run_stage`, so the hold is re-measured per point; not re-run.

**Tier.** A default interval on a bound row is a new automatic action (DESIGN § Rules 1 and 4), and its trigger is new judgement: name the families. The moduli-beside-zeroed-angles rule follows from B2's own ruling (its effect on the other esds), so it re-opens B2's consequence and needs the maintainer. A modulus flag for "esd orders above the value" is tier 1 if stated as a fact (the column is dead at m = 0, Hamilton 1965's linearisation does not hold there).

### Inherited

## Non-goals

- The FCJ aperture stall (#1075's repro 1): WP-1955.
- Intervals on widths, FCJ apertures and Biso by default: the reporter's own measurement says the profile misleads there under a misspecified model.
- Posterior sampling: fenced (ROADMAP § v2+, Estimation).
- The two-site cant exchange (#1075 § 4): an identifiability question for WP-1418.

## Tasks

- [ ] Rule with the maintainer: default intervals on bound rows of phase scale, occupancy and moment modulus (yes / no / modulus only), and whether a modulus beside a zeroed angle takes the interval by default or `MOMENT_ANGLE_STATIONARY` says its modulus is conditional and points at `profile_interval`.
- [ ] `profile_interval` holds the fit's own free set along its path: a pinned refit freezes WP-1301's held paths as the fit held them.
- [ ] `profile_interval`'s first step from the profile's curvature when the esd is orders above the value, and a modulus profile kept at m ≥ 0; never a zero-width interval where the walk found no end.
- [ ] A modulus on its dead column says so in `result.diagnostics` (or the existing `supported=False` verdict reaches the result), with its `_audit` row.
- [ ] Whatever the ruling turns on, with its `_audit` rows.
- [ ] Tests (unit/property; acceptance if this WP carries it) + obs/calc/diff PNGs to `tests/output/`: repro 2's three seeds give a non-degenerate interval containing 0; the two-site weak modulus covers on a small replicate set; a phase-scale profile keeps the held cell held.
- [ ] Skill: a reference row keyed by `RefinedParameter.interval` and the modulus code in `references/magnetic.md`; no body rule.

## Acceptance

Repro 2's seeds 3, 4 and 8 give intervals of non-zero width that contain m = 0; a phase-scale profile over a held phase reports `fit_is_minimum=True` where a TRF refit from the fit moves nothing; every shipped fixture with no moment is bit-identical.

```sh
.venv/bin/python -m pytest tests/test_parameter_interval.py tests/test_magnetic.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Hamilton, W. C. (1965). *Acta Cryst.* **18**, 502–510.
- Issue #1075 and its two repro scripts; WP-1929 (the stationary-angle test); WP-2002 B2 (`docs/wp/2002-batch/rulings.md`).

## Handover log

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1075). Checked against the tree at c0e32ab29: repro 2 reproduces on seeds 3, 4 and 8 (m ≈ −5e-7 ± 1.5e4 to 1.2e5 μ_B, `converged`, no diagnostic, `profile_interval` [v, v]); `FitReport.magnetic` says `supported=False`; `profile_interval`'s refits are `run_stage` calls that re-decide WP-1301's hold. No open WP owns it: WP-2002 (B2's intervals) and WP-1929 (the stationary test) are closed, WP-1955 owns only the FCJ column, and WP-2004 tiers `report/` codes and does not touch `profile_interval`. *Next:* the ruling.
