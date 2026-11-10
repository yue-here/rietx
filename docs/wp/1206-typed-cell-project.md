# WP-1206 — A project without a CIF, part 1: a typed cell

Milestone: v1.2 · Status: ✅ 2026-08-26 — a symbol and the free cell parameters are a project
Depends on: WP-1205

## Goal

The wizard's structure step offers "type a cell": a space-group symbol and the
cell parameters that *setting* leaves free (not six — see the first task)
become the Le Bail scaffold the indexing Adopt button already builds, and the
project opens in `lebail` mode.

## Context

- `blocked()` refuses without a CIF (`lib/wizard.ts:235`); `Structure.phases`
  must be non-empty and each `Phase` needs at least one atom
  (`schemas/structure.py:435-439, 475-480`). A Le Bail phase carries a
  mandatory dummy atom whose paths are `mode_fixed` (root CLAUDE.md, the
  parameter surface).
- The indexing panel's Adopt lands a candidate "as a Le Bail scaffold that
  flips the mode" (`gui/CLAUDE.md` WP-1027; the verb is in `session.py`'s
  adopt path, with the space-group choice a convention the user makes).
  That builder is the one to reuse; this WP factors it into one function
  rather than writing a second.
- A prior space-group symbol is validated **server-side and refused in
  gemmi's words** (WP-1045); the same rule applies to the typed symbol.
- A refused cell/symmetry pair is a `ParameterTable.__init__` raise
  (a fixed angle disagreeing with its symmetry is refused, not normalised).

## Non-goals

- Pattern-only projects (WP-1207).
- Indexing from the wizard: a user with no cell picks peaks and indexes
  after creating the project.

## Tasks

- [x] Factor the Le Bail scaffold builder into one function, used by both.
      It was already one — `indexing.workflow.structure_from_candidate` — but
      keyed on a `CellCandidate`, which a typed cell is not. So the cell-plus-
      dummy-atom half moved to `schemas.structure.lebail_scaffold` (with
      `DUMMY_SPECIES`, re-exported from `workflow`) and the wrapper kept the one
      thing a candidate adds: the absence-free lattice-group default.
      Beside it, `crystallography.symmetry.free_cell_names` / `complete_cell`:
      the typed route takes the parameters the **setting leaves free** and fills
      the rest, so a contradicting `b` is unrepresentable rather than tied away
      in silence (WP-1014's coordinate-DOF rule, one parameter family over).
- [x] `project_new` accepts `structure: {space_group, cell}` beside
      `{upload}`; refusals in `get_spacegroup`'s / `complete_cell`'s words with
      `where`. `cell` is an **object keyed by parameter**, carrying the ones the
      setting leaves free — a determined one is refused, naming its source.
      `GET /api/spacegroup?space_group=` (project-free, beside `/api/help`) is
      where a form learns which those are; `symmetry.phase_facts` is now a thin
      wrapper over the new `symbol_facts`, so the two cannot disagree.
      `mode: "rietveld"` over a typed cell is **refused**, not overridden.
- [x] Wizard UI: a `.segmented` "CIF file | Type a cell" in the structure step;
      the symbol, then **the fields the setting leaves free** (not six — the
      server's `free_cell`); mode moved to `lebail` by the switch and
      `rietveld` disabled while it is in force; docs-style lines.
- [x] Tests: `test_gui_server.py` creates from a typed cell and fits Le Bail
      (LaB6 against the module's own synthetic pattern — corundum against it
      would assert nothing); corundum `R -3 c` carries the shape assertions and
      every refusal, each with `where`. Five vitest cases for the client half.
- [x] Manual: `using/quickstart.md` § Le Bail before Rietveld gains "With no
      structure at all" — the GUI route and `lebail_scaffold`, with the dummy
      atom explained and `indexing.md` named as the other way to the same
      scaffold. Browser pass: four defects, all fixed (below). Dist rebuilt.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "typed_cell or spacegroup_route"
.venv/bin/python -m pytest tests/test_wyckoff.py tests/test_schemas.py -q
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1027, WP-1045: the adopt path and the symbol validation rule.
- TOPAS's constrained-cell macros (`Tetragonal(a, c)`, `Rhombohedral(a, al)`)
  and GSAS-II's phase editor, which greys out the parameters a setting
  determines. Prior art for the shape only; both are concepts-only fences
  (TOPAS closed, GSAS-II inspected through its published behaviour).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**A project without a CIF** (WP-1206, `GET /api/spacegroup`,
`session._typed_cell_structure`, `lib/wizard.ts`) is the wizard's second answer
to step 2: a symbol and a cell, built into the same Le Bail scaffold Adopt lands
(`schemas.structure.lebail_scaffold`, shared with `structure_from_candidate`).
Four rules. The `structure` argument has **four forms told apart by disjoint
keys** — `phases`, `cif`/`upload`, `space_group` — and the typed one's `cell` is
an **object keyed by parameter carrying only what the setting leaves free**:
`crystallography.symmetry.free_cell_names` decides, the route serves it, and the
form draws the boxes it names, so a `b` under `P 4/m m m` is unrepresentable
rather than refused — WP-1014's coordinate-DOF rule one parameter family over,
and TOPAS's `Tetragonal(a, c)` shape (concept only). A determined parameter is
**refused, never tolerance-checked and never ignored**: a tolerance on a *length*
is a constant nothing else here needs, and ignoring is what a six-number route
does — under `P 4/m m m` a typed `b` was tied away by `ParameterTable` and the
number read back was never the one entered. `mode` is **refused at `rietveld`,
not overridden**, the form disabling the option so the refusal is unreachable —
Adopt sets the mode because there the caller chose a *candidate*; here they chose
a mode — and it is refused at **both** routes `_as_structure` serves, since a new
form added at that one boundary reaches every verb crossing it (`project_new` and
`PATCH /api/structure`, where a scaffold would otherwise leave a rietveld project
refining a dummy carbon). And two browser facts about drawing a form, both
invisible to jsdom: a
**register's width is the call site's** (`.segmented` is `display: flex`, so in a
block parent it stretches to the whole column — every other use in the app sits
in a flex row already), and a **placeholder that is a plausible number reads as a
value somebody filled in**, which is why the instrument form's say `default`, a
word; where there is no default to name, the honest placeholder is none.

## Handover log

- **2026-08-26 (2nd session)** — **Review round on PR #151, four findings, all
  real.** The interesting one is a class of bug rather than a slip: a new
  `structure` form added at `_as_structure` — the one boundary every model
  crosses — is thereby accepted by **every** verb crossing it, and `PATCH
  /api/structure` was taking the typed cell and leaving a `rietveld` project
  refining a dummy carbon, which is exactly the state `project_new`'s new
  refusal exists to make unreachable. Fixed there with `project_new`'s own
  sentence rather than by flipping the mode: `index_adopt` flips it because the
  caller there chose a *candidate*, while a caller replacing the whole model has
  said nothing about the mode. In lebail/pawley the swap is ordinary and goes
  through. The clause in `gui/CLAUDE.md` now names both routes (687 → 691), and
  that is the half a later WP adding a third form needs.

  The other three were unphysical numbers reaching too far. `Parameter` carries
  no positivity rule, so `{"cell": {"a": 0}}` validated fine and would have died
  at stage compile — verified against the pre-fix tree, `a=0` sails straight
  through `lebail_scaffold` — a long way from the box it was typed in, and the
  wizard's `blocked()` was *stricter than the server*. `"NaN"`/`"Infinity"`
  passed `float()` and then raised a raw pydantic `ValidationError` that escaped
  uncaught into `server.py`'s blanket handler as a **500 with an empty `where`**,
  not the addressable refusal the route promises. And the unknown-key check ran
  after the cell parse, so a typo'd key reported a cell complaint and sent the
  caller to the wrong field. `_typed_cell_structure` now has four refusals, each
  naming its own field, and the key check runs first.

  *Measured* (`[dev,jax]`, python 3.12.12, darwin/arm64). `test_gui_server.py` +
  `test_schemas.py` + `test_wyckoff.py` **232 passed** (230 before this round:
  +2 tests, one per new refusal group). Fast suite on the final tree **3074
  passed / 72 skipped**, 2m59s — 3072 + 2, the delta the two new tests predict,
  and with nothing red: the `tests/CLAUDE.md` cap failure recorded in the entry
  below was another session's uncommitted edit and has since left this shared
  checkout. `ruff` clean; `test_docs_consistency.py` green at the raised cap.

- **2026-08-26** — **Closed.** A project no longer needs a CIF: type a
  space-group symbol and a cell into step 2 of the wizard and you get a
  working `lebail` project, the same Le Bail scaffold the indexing panel's
  Adopt button has always landed. The thing worth knowing is what the form
  refuses to let you type. The plan said "six fields"; six fields is exactly
  what the *old* six-number path did, and under `P 4/m m m` a typed `b` is tied
  away by `ParameterTable`, so the number read back was never the one entered.
  The wire and the form therefore carry only what the **setting** leaves free,
  and the server is the one that says which those are.

  *Done.* `schemas.structure.lebail_scaffold` is the one scaffold builder,
  `DUMMY_SPECIES` moved beside it (re-exported from `indexing.workflow`) and
  `structure_from_candidate` kept only the absence-free lattice-group default.
  `crystallography.symmetry.free_cell_names` / `complete_cell` are new, checked
  over gemmi's whole table against operator-derived cells in both directions.
  `POST /api/project/new` takes a fourth `structure` form; `GET /api/spacegroup`
  is project-free beside `/api/help`; `gui.symmetry.phase_facts` became a
  wrapper over the new `symbol_facts`, so form and panel cannot drift.
  `gui/CLAUDE.md` 663 → 687 with the four rules, cap comment written.

  *Measured* (`[dev,jax]`, python 3.12.12, darwin/arm64, main checkout's venv).
  A project typed as `P m -3 m` / a = 4.160 against the module's synthetic LaB6
  pattern fits Le Bail to **Rwp 0.0414, GoF 0.79**, `a` back at 4.15660 ± 5e-4
  (`tests/output/gui_typed_cell.png`, looked at). Fast suite **3072 passed /
  72 skipped**, 2m26s — the run itself printed 3071 passed / 1 failed, and the
  failure is `test_always_loaded_docs_stay_under_their_pinned_caps[tests/
  CLAUDE.md]` from **another session's uncommitted edit** in this shared
  checkout, confirmed by stashing that one file. +10 python tests, matching
  `git diff origin/main -- tests/ | grep -c '^+def test_'` exactly; the three
  touched files went 220 → 230. `npm --prefix gui test` **454 passed** (448 at
  the branch point: +5 for the typed cell, +1 for `typedCellReady`);
  `npm --prefix gui run check` clean; `test_gui_dist.py` passes on dist
  `ffd6ddc127f9`; `ruff` clean; sphinx `-W` clean. And
  `tests/test_acceptance_indexing.py` **44 passed**, 19m50s — the guard
  `src/rietx/indexing/CLAUDE.md` asks for before closing anything near an
  engine; the scoreboard regenerates over all 16 datasets. Run alone — checked
  by the file-lock protocol `tests/CLAUDE.md` carried at the time, which main
  has since replaced with a `pgrep` **look** (observe rather than reserve, since
  a lock adds a release to forget). The claim the two protocols share is the one
  that matters for the number: no other suite was running beside it.

  *Decisions taken against the WP's own text, both deliberate.* (1) The `cell`
  argument is an **object keyed by parameter carrying the free ones**, not six
  numbers — with the reason above, plus TOPAS's macro shape as prior art. A
  determined parameter is **refused, never tolerance-checked**: checking would
  need a tolerance on a *length*, a constant nothing else in this package
  needs and nothing would justify. (2) `mode="rietveld"` over a typed cell is
  **refused, not overridden**. Adopt overrides because there the caller chose a
  *candidate*; here they chose a mode, and the form disables the option so the
  refusal is unreachable from the GUI.

  *Gotchas for whoever is next here.* The candidate path deliberately does not
  go through `complete_cell`: `refine_candidate` already solves inside the
  symmetry subspace, so rebuilding a candidate's cell from its free parameters
  would move every stored number in the indexing acceptance suite at the 1e-14
  level for nothing. That is pinned as a `model_dump` equality in
  `tests/test_schemas.py`, which is the test to read before touching either
  function. And the browser pass found four defects, three of them about
  drawing a *form* rather than about this feature — a register's width belongs
  to the call site, a numeric placeholder reads as a filled value, and
  `holds: {constraints}` reads badly under a triclinic symbol. The first two
  are now rules in `gui/CLAUDE.md`; the third is fixed only at this call site,
  since the Model panel's own `holds:` line is WP-1035's and predates this.

  *Next.* [WP-1207](1207-pattern-only-project.md), whose `### Inherited` now
  carries the seams this WP left it — the `StructureSource` union a third
  member joins, the disjoint-keys dispatch a `structure: null` branch has to be
  decided *before*, and the moved `_nonempty` line number its audit quotes.

- **2026-08-25** — created from the v1.2 triage.
