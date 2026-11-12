# WP-2108 — a Pawley phase beside a Rietveld phase

Milestone: parametric · Status: ⬜
Depends on: 1964 (the first task tries equations on declared peaks); 2104 soft (its Pawley arm, if the second route is taken)
Priority: P3 2026-11-04 — a declared peak with an equation on its centre may already express this, so its first task decides whether any new surface is needed

## Goal

A user fits a sample holder beside a sample. The holder's peaks follow a cell, their
intensities are free, and a constant height offset separates it from the sample.

## Context

Stinton & Evans (2007), example 1, fits a Prussian blue analogue and silicon by Rietveld
and the aluminium sample holder by Pawley, because texture spoils the holder's
intensities. A constant height offset between sample and holder is shared across the
data sets. The holder gives the sample height, and that is where the example's gain in
precision comes from. So this is a method and no TOPAS habit. The TOPAS archive states
`hkl_Is` at the start of a line 139 times and `xo_Is` 277 times, against 1601 for `str`
(`io/projects/topas.py`). That counts lines, so how many fits mix them is unmeasured.

There are two routes.

**Declared peaks.** `PeakComponent` already names a sample holder as its use, carries
every emission line, and its docstring says why it is deliberately no phase: a `Phase` is
crystallographic, and a cell-less one breaks every consumer. A peak's position is a free
centre with no cell behind it. If 1964 lets an equation set that centre from a shared
cell and height, the holder needs no new surface, and the docstring's decision stands.

**A phase in Pawley mode.** rietx sets the mode per fit (`Refinement.fit(mode=...)`,
`CompiledModel.mode`), and `Phase` has no such field. `phase_peaks` picks the intensities,
the Pawley block is appended in `run_least_squares`, and `mode_fixed` force-fixes
`.atoms.` and `.scale`. Each of these would read the phase's mode. This route has a cell
already, and it costs a field on the main surface.

### Inherited

- **From WP-2104, 2026-11-12: the joint Pawley arm has landed, under one mode per
  fit.** `refine_multi(mode="pawley")` compiles every pattern in that mode, and each
  Pawley model owns one intensity block placed after the table's columns
  (`least_squares._joint_aux_slices`). Two readers assume one mode for the whole fit
  and need a per-phase answer here. `multi._joint_mode_fixed` drops a column by what it
  moves in every pattern. `MultiHistogramRefinement._build_result` computes phase
  fractions only when `model.mode == "rietveld"`, so a holder phase beside a Rietveld
  phase would lose the Rietveld phase's fraction too.

## Non-goals

- Le Bail for one phase beside Rietveld, unless the measurement shows it is the same
  work. Alternation between partitions is a different loop.
- Phase fractions for a holder. It has none, and QPA says so.

## Tasks

- [ ] **Try declared peaks first**, once 1964's grammar lands. Write Stinton & Evans's
  holder with five `PeakComponent`s whose centres come from a shared cell and height. If
  it recovers the truth at acceptable cost, write the recipe, add it to the manual, and
  close this WP with the rest of the list unticked and struck.
- [ ] If not, say what stopped it, then list every reader of `mode` and how Pawley's block
  sizes when only some phases own one.
- [ ] The surface: a field on `Phase` or a per-phase map on `fit`. It is a name on the
  main surface and may be a stored-format change, so it goes to the maintainer.
- [ ] The forward model, the Jacobian, the statistics' reflection count and
  `PAWLEY_OVERLAP_UNRESOLVED` per phase.
- [ ] QPA refuses a fraction for that phase by name, and the report says why.
- [ ] A joint fit: the holder's cell shared or per pattern, its intensities per pattern.
  This needs 2104's Pawley arm.
- [ ] Manual and skill.

## Acceptance

On a synthetic series with a second phase of scrambled intensities, over 12 pinned seeds,
the first phase's structure, both cells and a constant height offset between the two have
a mean z-score under 0.5 in size. The same fit with the second phase treated as a
structure misses the truth, and the fixture is built so that it does: enough of its peaks
overlap the first phase's.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95, § 4.1.
- Pawley, G. S. (1981). *J. Appl. Cryst.* 14, 357-361.
- WP-1103 (declared peaks), WP-2104, WP-1125 (the Pawley block).

## Handover log

- **2026-11-04** — Filed from reading Stinton & Evans (2007). No open WP owned it: 2104
  shares a cell across patterns under one mode, and a search of the index for mixed
  Pawley found nothing. A clean-context review then pointed at `PeakComponent`, so the
  first task now tests that route, and the priority fell to P3. Nothing is built. Next:
  wait for 1964's grammar, then try declared peaks.
