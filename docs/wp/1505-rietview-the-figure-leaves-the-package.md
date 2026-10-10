# WP-1505 — rietview: the figure leaves the package

Milestone: rietview · Status: ⬜
Depends on: 1504
Priority: P3 2026-10-04 — was P4: the trigger's second clause fired (WP-1504's rounds C and E, no new defect on one surface)

## Goal

`rietview` on PyPI: `build`, the masks, `render_structure`, the scene rules
and their corpus, adapters for a rietx `Structure`, pymatgen and ASE, and
its own `SKILL.md`. It needs numpy and gemmi, numba optional. rietx depends
on it and re-exports `rx.viz.render_structure`, and the GUI's structure
route calls it. Nothing on rietx's surface moves.

## Context

### The name, decided 2026-09-27

The maintainer chose `rietview`. It was free on PyPI, conda-forge and
GitHub repository search that day, as were `rietfig` and `rietviz`. The
naming survey behind the choice:

- PyPI normalises `-`, `_` and `.` to one project name, so only the import
  name differs between `rietx-view` and `rietx.view`.
- `rietx.view` as a second distribution needs `rietx` to be a namespace
  package with an empty `__init__`, and rietx's `__init__` carries the
  surface. pymatgen's add-ons and diffpy's dotted names work that way and
  carry the install-order bugs.
- `rietx-view` follows `pytest-cov`: a plugin that depends on the brand.
  Here the brand depends on the package, the other direction.
- `rietx-core` and `jaxlib` name a package nobody imports directly.
- An independent name is the honest signal for a package others install on
  its own. `rietview` keeps the brand and says the field; `view` promises
  interaction the package does not have, and the maintainer accepted that.

The import name equals the distribution name.

### The trigger

Either of two facts, recorded in this file when it lands:

- A user, or an agent task, wants the figure without the refinement.
- WP-1504's two rounds show the surface unchanged between them.

Until then the code stays in rietx, where the eval harness, the 21-phase
corpus, the browser parity row and the compiled-tier switch already live.

### The measured cost of the split

WP-1501's import-boundary pin names what `viz/figure3d` and
`gui/structure3d` take from rietx: `_about` (the data package name),
`viz.theme` (the colour tokens), `model.compiled` (the numba pool and the
switch), `crystallography.adp` and `crystallography.symmetry` (the basis,
U* and orbit expansion, both gemmi over numpy). `build()` also reads the
pydantic `Structure` field by field in `_expand`, and writes each site's
parameter dot-path (`"path": "phases.0.atoms.3"`) so a GUI click reaches
the parameter table. The dot-path belongs to the adapter. Nothing else in
the list is rietx's by nature.

### Design

- **Plain-data input.** `build()` takes cell, symmetry operations and
  sites as fractional position, species, occupancy, Uiso and optional
  Uij. `rietview.adapters.rietx(structure, phase)` builds it and adds the
  dot-path as an extra field the renderer ignores; `pymatgen` and `ase`
  adapters are ten lines each.
- **Theme.** `render_structure(tokens=)`, with rietview's own light and
  dark pair as the default and rietx passing its own. Two products, two
  palettes. rietx's rule that its three browser surfaces share one set of
  values is unchanged.
- **Compiled tier.** A small numba shim with the same soft import and
  fallback, and `RIETVIEW_COMPILED=0`.
- **The scene corpus ships in rietview's wheel**, and rietx's vitest reads
  it from the installed package, so the GUI's `buildScene` stays held
  equal to the renderer.
- **The Svelte viewer stays in rietx.** It is a panel of the GUI.
- **History.** `git filter-repo` scoped to `src/rietx/viz/figure3d`,
  `src/rietx/gui/structure3d.py`, their tests and data, so the new repo
  carries the commits that made it. The rewrite is scoped to those paths
  and never touches rietx's main.
- **Release.** Built from the tag by a workflow, never by hand
  (`docs/RELEASING.md`'s one rule). rietx pins a floor and re-exports.
- **The skill.** rietview's own `SKILL.md` carries the figure checklist;
  rietx's `api-figure.md` becomes a pointer to it.

### Inherited

- **2026-10-10, from WP-1940 (4th session, PR #864).** The figure's numba path is
  deleted in that PR, so the rasteriser runs its numpy twin. `view="auto"`
  takes 1.30-1.36 s on the NAC cell at 400 px (92 ms on numba) and 22.6 s at
  3143 atoms (565 ms). The maintainer made the rasteriser port the next
  kernel release, `rietx-kernels` 1.1.0 (1940 § Decisions item 9). If this
  WP moves the figure first, the port goes with it. `model.compiled` is no
  longer imported by the figure (`tests/test_figure_boundary.py`).

- **2026-10-04, from WP-1504 round E: the trigger's second clause fired.**
  Rounds C and E ran the same pinned `fixed` surface (amendment 1.3), and E's
  56 runs found no new defect in it: 40 of 42 fixed runs done, the one miss
  the agent's. That is the pair the 2026-10-01 note below waited for, so the
  Priority line is P3 as its own rule says. WP-1536 to 1538 are still ⬜
  (PR #686 filed them), so nothing has changed the surface since; the note
  below on what each would change when it lands still holds.

- **From WP-1501 (2026-09-30).** The split's measured cost is pinned by
  `tests/test_figure_boundary.py`: `_about`, `viz.theme`, `model.compiled`,
  `crystallography.adp`, `crystallography.symmetry`, and the figure's one
  upward import of `gui.structure3d`. The new `viz/figure3d/cut.py` adds none
  but needs scipy (`scipy.sparse.csgraph`), so rietview's dependencies include
  it. `StructureFigure` gained `palette`, and the skill's `api-figure.md`
  carries the six cut verbs, so both move with the package.
- **From WP-1502 (2026-09-30).** The geometry dict gained `image`, `n_cell` and
  `extent`, and `build` gained `extent=` and its tiling (`_tile`), so the
  boundary `gui.structure3d` import now carries a block builder that needs
  nothing new. `cut.py` gained `periodicity` and reads `image` on every atom, so
  a geometry from before WP-1502 (a saved payload) raises `KeyError` in `keep`
  and `component`: rietview must either rebuild or say so. `test_figure_boundary.py`
  still passes unchanged.
- **From WP-1504 (2026-10-01).** The trigger is rated not fired. Its
  second clause wants the figure surface unchanged between 1504's rounds, and
  round B led to WP-1529 changing it (`viz/figure3d/scene.py`, `render.py`,
  `report.py` and the skill's description). The fixed round on 1529's merge
  finished 13 of 14 tasks with rietx's renderer in every run. A further round
  that finds no new defect would be the first pair with the surface unchanged
  between them, so re-rate then. The first clause is untouched, because the
  round's tasks are its own.
- **From WP-1536, 1537 and 1538 (filed 2026-10-02).** Three queued WPs add to
  the figure: `.svg`, `.pov` and `.glb` through `render_structure`'s `path=`
  suffix, and an `ambient_occlusion=` option drawn in both the PNG renderer
  and the GUI. Each one landing changes the surface the second trigger
  clause wants unchanged. Their writers are planned as new modules under
  `viz/figure3d/` using the standard library and numpy, and the occlusion pass
  uses `model.compiled`, which is already on the boundary list. So the split
  would carry them without a new import from rietx. `test_figure_boundary.py`
  is where to confirm that as each lands.
- **2026-10-10, from WP-1940 (3rd session).** numba leaves rietx at the
  kernel migration (1940 § Decisions item 8). The rasteriser then runs its
  numpy twin until 1940 ports it into the `rietx-kernels` wheel. Measured on
  one small structure, this Mac: 0.35 s at 1000 px against 0.05-0.08 s
  compiled, 1.17 s at 2000 px against 0.14-0.18 s. So Context's "a small
  numba shim" for rietview's compiled tier needs another answer: depend on
  `rietx-kernels`, or keep the numpy path. Whichever of 1505 and that port
  lands first decides which package the port belongs to.

## Non-goals

- Moving the Svelte viewer or any GUI code.
- A GUI or a CLI in rietview.
- Renaming `rx.viz.render_structure`.

## Tasks

- [ ] The trigger recorded here with its date and evidence.
- [ ] The repository, the name on PyPI, the workflow from `RELEASING.md`.
- [ ] Plain-data `build()` and the three adapters, with the dot-path in
  the rietx adapter.
- [ ] Theme and compiled-tier injection; the corpus in the wheel.
- [ ] `git filter-repo` over the named paths; the tests moved; rietx
  depending and re-exporting; the GUI route calling through.
- [ ] rietview's `SKILL.md`; rietx's `api-figure.md` pointing at it.
- [ ] The break staged in the open milestone's record and the release
  notes.

## Acceptance

- `pip install rietview` in a fresh venv draws NAC from a CIF with no
  rietx present.
- rietx's fast suite and `npm --prefix gui test` are green with rietview
  installed and the corpus read from the wheel.
- `rx.viz.render_structure(structure)` is bit-identical before and after.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
npm --prefix gui test && npm --prefix gui run check
```

## References

- PyPA packaging guide, *Packaging namespace packages*.
- PEP 503, name normalisation.
- `docs/RELEASING.md`.

## Handover log

- **2026-09-27** — filed from the session that closed WP-1470, the day the
  name was chosen. Next: nothing until the trigger; re-check the name is
  still free when it fires.
