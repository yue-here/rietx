# WP-2084 — The SRM 660c protocol has two minima in the Gaussian widths, and the shipped start reaches the shallower

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-02 — a start-dependent answer on the absolute anchor's widths; the cell moves 0.18 esd between the two and nothing fires; a reader quotes u, v and w, which `RESOLUTION_UNCONSTRAINED` already says not to quote

## Goal

Either the NIST protocol on SRM 660c reaches one answer from every start and every
window setting the start tests try, or the result says that its widths sit in one of
two minima.

## Context

**Measured 2026-11-02** (WP-2012's session; macOS arm64, worktree venv `[dev]`, compiled
tier on, dispersion declined). WP-2012 made the NIST protocol
(`tests/test_acceptance_srm660c.py::_nist_calibrated_plan`) free S/L alone and hold H/L
at its declared 0.025. That removed the S/L ↔ H/L mirror, and the protocol still has
two minima:

| arm | χ²_red | u | v | w | S/L |
|---|---|---|---|---|---|
| shipped (`AXIAL_SIZING_FLOOR` 0.02), cold | 3.557722 | −0.000506 | 0.001733 | 0.000505 | 0.037039 |
| floor 0.05, cold | 3.549273 | −0.000547 | 0.001822 | 0.000463 | 0.037098 |
| floor 0.02, warm from the 0.05 answer | 3.549378 | −0.000554 | | | 0.037108 |

So at the shipped floor a deeper point exists and the shipped start misses it. The gap
is 0.24 % of χ², about 45 in absolute χ² over 5332 points. Between the two the cell
moves 0.18 plain esd and u, v and w 0.58, 0.54 and 0.42 (the larger of the two arms'
plain esds). The probe fitted `test_window_domain._protocol("lab6")` cold at each floor,
then refitted each answer under the other floor with the same plan. Every arm reports `RESOLUTION_UNCONSTRAINED`, `RESOLUTION_NOT_POSITIVE` and
`CONSTRAINT_ACTIVE`: the Gaussian width is on its Γ_G² ≥ 1e-8 cone somewhere in range,
which is where to look first.

**The same pair of minima was seen before and blamed on the axial mirror.**
`tests/test_seed_invariance.py::test_the_peak_width_start_does_not_change_the_answer`'s
docstring records starts with x at 0.02 or 0.03 landing 0.38 esd away in u at χ² 0.25 %
lower, 46.7 apart in absolute χ² (WP-2002's B10 lane, 2026-10-21). With both ratios free
the two were near mirror images in S/L and H/L. With H/L held the gap is the same size,
so the mirror rode along and does not cause it.

**What it fails.** `tests/test_staged_start_invariance.py`'s lab6 axial-floor row reads
0.582 plain esd on u against a 0.1 bar. WP-2012 marked it a non-strict xfail citing this
WP, non-strict because only one platform was measured and rounding has picked these
minima differently on Linux before (WP-2036).

## Tasks

- [ ] Find what separates the two minima: the Γ_G² cone's active rows, the FCJ node
      counts at each, or the windows. Start from the three arms above.
- [ ] Decide between a plan change that reaches the deeper minimum from the shipped start
      and a finding that says which minimum the fit is in. The deeper χ² is not by itself
      the evidence (root CLAUDE.md: never an Rwp comparison).
- [ ] Make the lab6 axial-floor row strict, or drop its mark.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_staged_start_invariance.py -k lab6
```

## Handover log

- **2026-11-02, filed by WP-2012's session.** No open WP owns the SRM 660c width minima:
  the index's open rows name WP-2080 (a warm series rung in a wrong basin, a different
  path) and WP-2072 (the Le Bail and Pawley cell), and neither covers the Rietveld
  protocol's widths.
