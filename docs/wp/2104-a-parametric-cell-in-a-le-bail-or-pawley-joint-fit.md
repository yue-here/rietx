# WP-2104 — a parametric cell in a Le Bail or Pawley joint fit

Milestone: parametric · Status: 🔄 2026-11-12 — claimed by ghostshift runner (MacBook-Air-c4aacd)
Depends on: 1325 soft (the joint path has landed, and its open tasks are separate); 1964 soft (an equation on the cell)
Priority: P2 2026-11-04 — a feature the open milestone was opened for: a cell series is often fitted before a structure is known or trusted

## Goal

A joint fit in `mode="lebail"` or `mode="pawley"` can share a parametric equation on the
cell, with each pattern's intensities its own.

## Context

`MultiHistogramRefinement.fit` raises `NotImplementedError` for any mode but
`rietveld` (`multi.py:1426`). The stated reason is that "a joint fit of them is just
independent single-pattern fits". That was true with nothing shared. It stops being true
the moment a cell is tied across patterns, because the shared coefficients then couple
every pattern. A cell as a function of temperature is the commonest case, and it is the
case that needs no structure model.

Two different seams sit behind the one refusal:

- **Le Bail** alternates: `Refinement._fit_lebail_alternation` partitions intensities
  and then refines. Here each histogram partitions its own, and the shared step runs
  between partitions.
- **Pawley** holds intensities as an off-table θ block
  (`model.forward.PawleyBlock`, appended in `run_least_squares`). A joint fit has many
  such blocks. `optimize/blocked.py`'s per-pattern blocks are the natural home, and the
  count of intensities per pattern is what the measurement must find out.

The rest of the joint path says the same thing in two rows of `multi.py`'s diagnostic
table (`ABSENT`, "a joint fit is Rietveld-only"). Those rows change with this WP.

### Measured (2026-11-12), and which mode lands

Pawley lands and Le Bail does not, settled by Claude under the 2026-11-05 ruling
(Pawley is the structure-free direction, and Le Bail work stays minimal). Le Bail's
joint arm would be a new partition seam between solves, so its cost was not measured:
measuring it means building it.

The Pawley arm, on `tests/test_parametric_series.pawley_ramp` (LaB6, a(T) on a line,
4 200 points and 19 reflections a pattern, zero and profile shared), through
`docs/wp/2104-measure/pawley_scaling.py`. The machine was shared with other runners
(load average 28-30), so wall clock is a range of one run each and the iteration counts
are the comparable numbers.

| run | free columns | iterations | wall clock |
|---|---|---|---|
| 10 single Pawley fits, each with its own cell, zero and profile | per fit, 19 intensities and its own rows | 440 in all | 3.2 s in all |
| joint, N = 10, dense layout | 228 (190 intensities) | 82 | 8.7-9.4 s |
| joint, N = 10, blocked layout | 228 | 80 | 3.4 s |
| joint, N = 100, blocked (chosen unasked) | 2 208 (1 900 intensities) | 67 | 83 s |

The blocked step holds at N = 100. Its dense twin would be a 7.4 GB Jacobian; the
blocked run peaked at 1.05 GB of physical footprint, against 1.03 GB at N = 10, so the
n × n normal matrix (39 MB at n = 2 208) is not yet what limits it. The intensities are
each histogram's own columns of `optimize/blocked.py`'s arrow, so no new solver path
was needed. At N = 100 the slope landed 0.27 esd and the intercept 0.70 esd from the
truth.

## Non-goals

- A joint Pawley with intensities shared across patterns.
- Restraints on Pawley intensities beyond the existing equal-split rows.

## Tasks

- [x] Measure first: on a synthetic ramp of 10 patterns, what does Le Bail alternation
  through the joint path cost against N single fits, and does Pawley's blocked step
  hold at N = 100? Decide whether one mode lands first, and write it here.
  (§ Measured: Pawley lands; its blocked step holds at N = 100.)
- [x] Lift the refusal for the mode or modes built. A joint fit with nothing shared in
  these modes keeps a message saying it is N single fits.
- [x] `multi.py`'s diagnostic rows, and `force-fix` of intensity paths under
  `mode_fixed` across histograms.
- [ ] A cross-backend config, if a new derivative path appears.
- [ ] Manual: `reference/joint.md`, `reference/parametric.md`.
- [ ] Skill: the series reference's row.

## Acceptance

A Pawley or Le Bail joint fit shares a parametric cell over a synthetic ramp. Over 12
pinned seeds, the coefficients of a(T) have a mean z-score under 0.5 in size. If only one
mode lands, this file says so, and 2108's second route waits on the Pawley arm.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_parametric_series.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95.
- WP-1325 § Scalable solver, WP-1125 (the Pawley block), WP-0308.

## Handover log

- **2026-11-04** — Filed on the opening of the milestone. No open WP owned it. It split
  from 2103 because it reaches the solver and has a measurement in front of it. Next:
  the measurement.
