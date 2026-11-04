# WP-2104 — a parametric cell in a Le Bail or Pawley joint fit

Milestone: parametric · Status: ⬜
Depends on: 1325 (the joint path); 1964 soft (an equation on the cell)
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

## Non-goals

- A joint Pawley with intensities shared across patterns.
- Restraints on Pawley intensities beyond the existing equal-split rows.

## Tasks

- [ ] Measure first: on a synthetic ramp of 10 patterns, what does Le Bail alternation
  through the joint path cost against N single fits, and does Pawley's blocked step
  hold at N = 100? Decide whether one mode lands first, and write it here.
- [ ] Lift the refusal for the mode or modes built. A joint fit with nothing shared in
  these modes keeps a message saying it is N single fits.
- [ ] `multi.py`'s diagnostic rows, and `force-fix` of intensity paths under
  `mode_fixed` across histograms.
- [ ] A cross-backend config, if a new derivative path appears.
- [ ] Manual: `reference/joint.md`, `reference/parametric.md`.
- [ ] Skill: the series reference's row.

## Acceptance

A Pawley or Le Bail joint fit sharing a parametric cell over a synthetic ramp, on one
pinned seed, recovers the known a(T) within 2 esd of the slope.

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
