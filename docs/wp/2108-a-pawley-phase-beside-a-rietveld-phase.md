# WP-2108 — a Pawley phase beside a Rietveld phase

Milestone: parametric · Status: ⬜
Depends on: 2104 soft (a joint fit's Pawley blocks)
Priority: P2 2026-11-04 — a feature the open milestone was opened for: the method's founding paper fits a sample holder this way, and no surface here can say it

## Goal

One fit holds a phase with a structure and a phase with no structure. The second has a
cell and free reflection intensities, and it still shares a cell or an instrument with
the rest.

## Context

Stinton & Evans (2007), example 1, fits a Prussian blue analogue and silicon by Rietveld
and the aluminium sample holder by Pawley, because texture spoils the holder's
intensities. The holder gives the sample height, and that is where the example's gain in
precision comes from. So this is a method and no TOPAS habit. The TOPAS archive states
`hkl_Is` at the start of a line 139 times and `xo_Is` 277 times, against 1601 for `str`
(`io/projects/topas.py`). That counts lines, so how many fits mix them is unmeasured.

rietx sets the mode per fit (`Refinement.fit(mode=...)`, `CompiledModel.mode`), and
`Phase` has no such field. So a structure-free phase cannot sit beside a structural one.
A `PeakComponent` declares one sharp peak, with no cell to tie its peaks together.

The seams are the ones `self.mode` reaches. `phase_peaks` picks the intensities, the
Pawley block is appended in `run_least_squares`, and `mode_fixed` force-fixes `.atoms.`
and `.scale`. Each of these reads the fit's mode today and must read the phase's.

## Non-goals

- Le Bail for one phase beside Rietveld, unless the measurement shows it is the same
  work. Alternation between partitions is a different loop.
- Phase fractions for a structure-free phase. It has none, and QPA says so.

## Tasks

- [ ] Measure first: list every reader of `mode`, and how Pawley's block sizes when only
  some phases own one. Write the list here.
- [ ] The surface: a field on `Phase` or a per-phase map on `fit`. It is a name on the
  main surface and may be a stored-format change, so it goes to the maintainer.
- [ ] The forward model, the Jacobian, the statistics' reflection count and `PAWLEY_OVERLAP_UNRESOLVED`
  per phase.
- [ ] QPA refuses a fraction for that phase by name, and the report says why.
- [ ] A joint fit: the holder's cell shared or per pattern, its intensities per pattern.
- [ ] Manual and skill.

## Acceptance

On a synthetic two-phase pattern with the second phase's intensities scrambled, the first
phase's structure and both cells are recovered within 2 esd on one pinned seed, and a
Rietveld fit of the same pattern is not.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95, § 4.1.
- Pawley, G. S. (1981). *J. Appl. Cryst.* 14, 357-361.
- WP-2104, WP-1125 (the Pawley block).

## Handover log

- **2026-11-04** — Filed from reading Stinton & Evans (2007). No open WP owned it: 2104
  shares a cell across patterns under one mode, and a search of the index for mixed
  Pawley found nothing. Nothing is built. Next: the list of `mode` readers.
