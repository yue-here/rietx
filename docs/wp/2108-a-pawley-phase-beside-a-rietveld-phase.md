# WP-2108 — a Pawley phase beside a Rietveld phase

Milestone: parametric · Status: ✅ 2026-11-15 — declared peaks with formula centres fit the holder; no new surface (PR #1572)
Depends on: 1964 (the first task tries equations on declared peaks); 2104 soft (its Pawley arm, if the second route is taken)

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

## Non-goals

- Le Bail for one phase beside Rietveld, unless the measurement shows it is the same
  work. Alternation between partitions is a different loop.
- Phase fractions for a holder. It has none, and QPA says so.

## Tasks

- [x] **Try declared peaks first**, once 1964's grammar lands. Write Stinton & Evans's
  holder with five `PeakComponent`s whose centres come from a shared cell and height. If
  it recovers the truth at acceptable cost, write the recipe, add it to the manual, and
  close this WP with the rest of the list unticked and struck.
  Done 2026-11-15: `examples/guides/holder_cell.py` and `docs/docs/guides/holder_cell.md`.
- [ ] ~~If not, say what stopped it, then list every reader of `mode` and how Pawley's block
  sizes when only some phases own one.~~ Not needed: declared peaks express the holder.
- [ ] ~~The surface: a field on `Phase` or a per-phase map on `fit`. It is a name on the
  main surface and may be a stored-format change, so it goes to the maintainer.~~ Not needed: declared peaks express the holder.
- [ ] ~~The forward model, the Jacobian, the statistics' reflection count and
  `PAWLEY_OVERLAP_UNRESOLVED` per phase.~~ Not needed: declared peaks express the holder.
- [ ] ~~QPA refuses a fraction for that phase by name, and the report says why.~~ Not needed: declared peaks express the holder.
- [ ] ~~A joint fit: the holder's cell shared or per pattern, its intensities per pattern.
  This needs 2104's Pawley arm.~~ Not needed for the Phase route. Whether a joint fit
  can share the offset through declared peaks is untested; see the handover entry.
- [ ] ~~Manual and skill.~~ Not needed: declared peaks express the holder.

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

- **2026-11-15 (a ghostshift runner)** — A sample holder of a known crystal can be fitted
  beside a Rietveld phase today, with nothing new in the package. Each holder reflection is
  a declared peak whose centre is a formula of one holder lattice parameter and one height
  offset, and each line's area and width refine freely. On synthetic fluorapatite over a
  textured aluminium holder this recovers both cells, the sample's coordinates and the
  offset, while the holder fitted as an aluminium phase misses its own cell by about 30 esd.
  So the Phase-mode route (a mode field on `Phase`, a per-phase Pawley block) is not
  needed, and the stored-format question it would have sent to the maintainer never arises.

  *Done.* Guide `docs/docs/guides/holder_cell.md` with its script
  `examples/guides/holder_cell.py` (one seed, every quoted number asserted), linked from
  the guides index and `holder.md`. Slow test `tests/test_holder_cell.py`: the milestone's
  12-seed bar. Task 1 ticked, tasks 2-7 struck as the task said. The `### Inherited` note
  from WP-2104 is deleted: both readers it named (`multi._joint_mode_fixed`,
  `_build_result`'s QPA gate) matter only to the Phase route.

  *Measured* (darwin/arm64, `[dev]` venv). The centre formula, Bragg's law for Kα1 plus the
  zero shift plus −(2s/R)·cosθ at the holder's height, reproduces rietx's own tick
  positions for an aluminium phase at that height to 3e-14°. Twelve seeds (100-111) of
  fluorapatite (height 0.040 mm, zero 0.012°) over aluminium 0.120 mm lower with a
  March-Dollase r = 0.55 along [111], 15-90° 2θ, plan `mccusker_structural` with the zero
  stage freeing `vars.zero`/`vars.height` and the `extra_components` stage, renamed
  `holder`, moved second and freeing `vars.a_holder`/`vars.offset`. Mean z of the truth,
  declared arm: fluorapatite a −0.08, c −0.15, mean coordinate z +0.06, holder a −0.24,
  offset +0.25, height −0.09, zero −0.09; standard deviation of each 0.78-0.90; GoF
  1.00-1.03. Holder as a phase: holder a −30.5 mean (sd 1.2), fluorapatite unharmed (a −0.12,
  c −0.19), GoF 1.17-1.18. One fit 2-5 s. Holding the holder cell at its known value takes
  the height's esd from 0.022 to 0.012 mm on the guide's seed. A declared line's Kα2 image
  sits at the Bragg image of its Kα1 centre, while a phase shifts each wavelength; the two
  differ by 1.6-2.5e-4° here, about a tenth of a line centre's esd, and the simulation drew
  the holder as a phase, so the 12-seed result includes that mismatch.

  *Gotchas.* No preset frees a `vars.*` column or, in `mccusker_structural`, the specimen
  displacement, so the recipe edits the plan; without that the variables stay at their
  starting values and nothing says so. A formula reads only variables, so the zero shift and
  the displacement are tied to variables first. The holder stage must come before the zero
  stage, or the zero shift and the height refine against unmodelled holder counts.

  *Not tried.* A joint fit sharing the offset across patterns (Stinton & Evans share it across
  data sets). `MultiHistogramRefinement` has no `tie`, but takes `variables=` and
  `ParametricEquation(basis="expression")`, which may express it per pattern; unmeasured.

  *Review.* `/code-review high --fix` found eight. Taken: the test module's `xdist_group`,
  the page's Kα2 bound (now 0.00025°), the script docstring's pointer, and the phase arm's
  stage found by name. For its finding that a signed mean over atoms cancels a +3σ atom
  against a −3σ one, the test now also bounds each seed's rms coordinate z at 1.6 (measured
  0.84 average, 1.11 most). Declined: merging the test with the script (the script fits at
  import, so the test cannot import it), a guard for an unmeasured esd (no seed has one), and
  declaring dispersion in the script (no guide script does; the test declares it). No
  heuristic was added, so the generality judge did not run. The skill is unchanged: the
  recipe is a manual page an agent reaches from `holder.md`.

  *Gates run here* (darwin/arm64, `[dev]`): `tests/test_holder_cell.py` and the two holder
  guide rows of `tests/test_examples.py`, 4 passed; `tests/test_docs_consistency.py` 26
  passed; ruff clean; Vale clean on the new page; `sphinx -W` green; `python -m
  tests.reader_output` exit 0 (unchanged). The local fast suite did not run: it waited
  about 2 h behind other sessions' suites on the machine-wide queue and was withdrawn, so
  CI's fast suite is the gate. The fast selection gains one test (the new guide row); the
  slow test is outside it. No full suite: the change is a guide, a script and a slow test.

  Next: none in this WP. If a user asks for the joint form, try `variables=` plus an
  expression equation per holder line in a new WP.

- **2026-11-04** — Filed from reading Stinton & Evans (2007). No open WP owned it: 2104
  shares a cell across patterns under one mode, and a search of the index for mixed
  Pawley found nothing. A clean-context review then pointed at `PeakComponent`, so the
  first task now tests that route, and the priority fell to P3. Nothing is built. Next:
  wait for 1964's grammar, then try declared peaks.
