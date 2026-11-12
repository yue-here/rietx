# WP-1014 — Import & in-GUI structure/instrument editing

Milestone: v1.0 · Status: ✅ 2026-07-30
Track: The human GUI
Depends on: WP-1008, WP-1010

## Goal

Data gets *into* a project from the browser: upload endpoints with
content-sniffed validated previews, an import wizard, atom-level structure
editing through the Wyckoff DOFs, and instrument forms.

## Context

- `POST /api/upload/pattern|cif|instrument` — bytes + filename →
  content-sniff via the existing readers → validated preview (echo back
  n_points/range/phases/λ before committing to the project):
  - `read_pattern` (`io/readers.py:21`) dispatches content-first: `.cif`
    suffix → pdCIF; `_looks_gsas` (regex `^BANK\s+\d+`, `:106`) → GSAS
    FXYE/STD incl. esd column; else 2-3 column ASCII. **`.XRA` has no
    dedicated parser** — GSAS-format files read via the `BANK` sniff; name
    the supported formats as xy/xye, GSAS (FXYE/STD), pdCIF, not by
    extension folklore.
  - `structure_from_cif` (`crystallography/cif.py:20`) with its
    `aniso: bool = False` keyword — the wizard's aniso opt-in checkbox
    mirrors the invariant that **reading a file must not silently change
    what a plan frees** (several test CIFs carry aniso loops).
  - `load_instrument_profile` (`io/instrument_profile.py:63`, top-level
    export) — everything arrives `vary=False`, per the calibrate → freeze →
    refine workflow.
- Import wizard: anode picker from `capabilities()` (WP-1007), wavelength /
  geometry forms, the aniso checkbox above.
- Structure editor: atoms add/remove/species/occupancy/Biso; **coordinates
  edited through the Wyckoff DOFs** (`phases.i.atoms.j.dof.k`,
  `crystallography/wyckoff.py`) so site-symmetry violations are
  *unrepresentable* rather than merely refused — the GUI edits the DOF
  values, and fully-fixed special positions render read-only (the table
  already raises on `vary=True` there). ADP editing follows the same shape
  one rank up (`adp.k` from `wyckoff.adp_basis`, absolute DOFs,
  out-of-subspace tensors raise).
- Instrument forms: profile (U V W X Y, S/L H/L), zero/displacement,
  background family, geometry block — all `PATCH /api/instrument` over the
  WP-1008 routes, one history node per edit.

### Inherited

From **WP-1013** (landed 2026-07-30): a structure or instrument edit commits an
`edit_model` node, which **moves the head**, which is the text pane's reload signal
— so an open text buffer will go *stale* the moment this WP's import or model
editor lands a change, and correctly so. Nothing to build: `lib/sync.ts` already
holds the edit and offers a re-read. What is worth knowing is that the head is now
load-bearing for three panels (parameters, report, text), so **a verb that changes
the model and does not commit a node leaves all three showing the previous state**.

Also: `panels/Stubs.svelte`'s "panels still owed" list is where this WP's row lives
(`Import / editing — WP-1014`); delete it when the panel lands, as 1013 did.

From **WP-1011** (landed 2026-07-30): the shell's empty state already points at
this WP by name ("Creating a project in the browser needs the import flow
(WP-1014)"), so that copy is what this panel replaces. Three carried facts:
**`ProjectDoc.ui` is live** and the frontend owns its keys — `{"simple": bool}`
is taken, set through `POST /api/project {ui: …}`, which persists on the verb, so
an import wizard's own state can join it the same way. **A model patch is a whole
validated model** (`PATCH /api/structure`), and a state refusal outranks body
validation — disable the form off the `state` frame rather than letting a user
retype a structure into a 409. And **non-finite floats cross the wire as strings**
(`"Infinity"`), since `JSON.parse` rejects Python's bare token — a `Parameter`'s
`min`/`max` in a structure payload will arrive as strings, so `lib/table.ts`'s
`num()` is what to read them with.

From **WP-1012** (landed 2026-07-30): **`add_impurity_phase` is this WP's
button.** It is one of the four `ActionKind`s `report/apply.py` classifies as
`advice`, and the note says why — "no phase is named yet, so there is nothing to
free … that is an `edit_model` move, and the search for a candidate is not
something this report can do for you". The report already hands over everything the
flow needs (the unindexed peaks' 2θ and height/σ, `two_theta_range` on the action,
and a plot the panel can already zoom to it), so wiring "identify this, then add
it" is an import-flow question rather than a report one. If this WP gives it a verb,
move the kind from `advice` to a new `how` in `RECIPES` — the split is a table with
a meta-test, not scattered conditionals.

One measured trap for the instrument form: **Layer 2 proposes Bragg-Brentano
aberrations whatever geometry is declared** — on a Debye-Scherrer instrument the
highest-confidence suggestion named `instrument.geometry.sample_transparency`,
which `params/vector.py` force-fixes off `bragg_brentano`. So a geometry change in
this editor silently changes which report suggestions are reachable, and the
`held_because` on those rows is what says so.

From the **v1.0 GUI plan** (2026-07-29): the FCJ corner at S/L = H/L with
both apertures started equal is a real parameterisation trap (identical
Jacobian columns, ρ = +1.000 — measured in WP-0601). The instrument form
should not *default* new instruments into S/L == H/L silently; keep the
shipped defaults but surface the correlation guard when it fires.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): **adopting an
indexed cell is a structure edit**, so it reuses this WP's editor and
`Refinement.edit(structure=…)` rather than inventing a path.
`indexing.structure_from_candidate` (WP-1024) produces a phase carrying a
**dummy atom** — required because `Phase._nonempty` raises on an empty atom
list, and inert because `_run_stage` force-fixes `.atoms.` in lebail mode. The
structure editor should make that atom's status legible (it is a placeholder,
not a site), which is the same note left in WP-1004 for the parameter surface.

From **WP-1008** (GUI server, landed 2026-07-30):

- `POST /api/upload/{pattern,cif,instrument}` are **reserved** and 404 naming
  this WP; adding them is entries in `gui.server.ROUTES` plus methods on
  `GuiSession`. Note they are the only routes in the surface that will not take
  JSON, so the body-reading helper (`Handler._body`) needs a sibling for
  multipart or raw bytes.
- `GuiSession.project_new` already takes **server-side paths** — `pattern` a
  path, `structure` either an inline dict or `{"cif": path, "aniso": …,
  "phase_name": …}`, `instrument` an inline dict. `_as_structure` /
  `_as_instrument` are the two places sniffing plugs into.
- **`instrument` is required and refusing it is deliberate**: `Instrument()` does
  not validate (no default `source`), and defaulting an anode would put a
  wavelength nobody chose into every refined cell. An import flow must ask.
  Reading a CIF passes `aniso=False` unless asked, for the CLAUDE.md reason —
  reading a file must not silently change what a plan frees.
- Whole-model `PATCH /api/structure` / `PATCH /api/instrument` already exist and
  record an `edit_model` node with an optional `label`; they replace a validated
  model rather than merging fields, so in-GUI editing can build on them without
  a field-patch protocol.

## Non-goals

- **Space-group editing — hard fence.** Re-import a CIF instead.
  `structure_from_cif` is the only symmetry-derivation path and symmetry UI
  is bottomless. Wyckoff DOFs and typed atom fields only.
- No CIF writing from the editor (export routes already exist).
- No occupancy constraint editor (site-fraction ties across atoms) — v2
  with rigid bodies.

## Tasks

- [x] Upload endpoints: bytes → sniff → validated preview → commit-to-
      project step (two-phase, so a bad file never half-lands).
- [x] Import wizard: pattern → structure → instrument flow; anode picker
      from capabilities; aniso opt-in checkbox wired to
      `structure_from_cif(aniso=)`.
- [x] Structure editor: atom table (add/remove/species/occupancy/Biso),
      coordinate editing via DOFs, locked positions read-only, aniso ADP
      editing via `adp_basis` patterns.
- [x] Instrument forms + PATCH wiring; each edit a history node.
- [x] `tests/test_gui_server.py`: upload-sniffing rows for `.xye`, FXYE,
      pdCIF and an aniso-loop CIF asserting the opt-in (aniso absent unless
      checked).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- CLAUDE.md: site-symmetry DOF and ADP conventions; instrument ⊕ sample
  split (calibrate/freeze/refine).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**Import and model editing** (WP-1014, `src/rietx/gui/imports.py`,
`gui/src/panels/Model.svelte`, `gui/src/lib/{model,wizard}.ts`) is how data gets
*in* from a browser and how the model is edited once it is. Its founding rule is a
split: **if the parameter table has the path, the parameter table owns it** — a
cell edge, an occupancy, a Biso, a profile term, a coordinate DOF go through
`PATCH /api/params`, where the tie/lock/mode/bound rules already live, while a
species, a label, an atom added or removed, a geometry, a wavelength or a
background family go as a whole validated model, because each changes what the
table *contains*. Coordinates are therefore never typed as x/y/z (they are affine
ties onto `…dof.k`); the editor offers the DOFs, so a site-symmetry violation is
unrepresentable rather than refused, and a fully fixed special position gets no
coordinate control at all — `GET /api/structure`'s **`sites` arm** is what says
which is which, deliberately without the Wyckoff letter (spglib per atom on a
route that refetches on every head move). Uploads are **two-phase** — a file is
staged and read before anything is created, and only an opaque token crosses back,
never a path — and they are the one route family whose body is not JSON (raw
bytes; filename and reader options in the query string, `UPLOAD_ROUTES`). Two
previews are judgements rather than descriptions: a pattern names the *reader*
that claimed it in the reader's own words, and a CIF's `aniso_available` is
**measured** by reading it a second time with `aniso=True`. A pattern preview
also carries an `instrument_hint` — the anode and goniometer radius its header
already states, matched **server-side** (`imports.suggest_instrument`) because
deciding that 1.5418 Å is a Cu doublet is a physics judgement against the
package's radiation table, and a client-side match would be a second copy of that
table in TypeScript; a header whose name and wavelength disagree sends **null**,
and the form is then left alone, because a wrong pre-fill looks like it was read.
The scan picker splits the same way for a different reason: `scan_count` rides
along in the preview's metadata from the read that already happened, while
*labelling* the scans costs a second walk of the ranges, so it is its own route
(`GET /api/upload/pattern/scans`) fetched when someone opens the control. `POST
/api/structure/aniso` exists because both directions are physics
(`AnisoU.isotropic` on, U_eq → Biso off). Three browser-only traps are recorded in
code: `structuredClone` **throws on a Svelte 5 `$state` proxy** (use
`lib/model.ts:clone`), a verb's refusal and a panel's load error **must not share
one field** (the reload after a failed apply wiped it), and `axialWarning` stays
silent on the S/L = H/L pair that is 0-and-held, because that is the shipped
default and a warning on every fresh lab instrument is a warning nobody reads.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. Reader dispatch and the
  `aniso=` keyword verified against the tree the same day.

- **2026-07-30 — landed; all five tasks done.** Three commits: the upload
  endpoints, their tests, the frontend.

  **Done.** `POST /api/upload/{pattern,cif,instrument}` are live
  (`gui/imports.py`, `UPLOAD_ROUTES` in `server.py`, `GuiSession.upload`); the
  import wizard *is* the empty state; the structure and instrument editors are a
  full-window **mode** beside the text pane; `POST /api/structure/aniso` is a new
  verb; `GET /api/structure` gained a `sites` arm. Python 1148 → 1164 fast-suite
  passes (skips unchanged at 107, so all sixteen are new tests, not converted
  skips); vitest 139 → 184. `app.js` 114.2 → 151.6 kB (40.4 → 51.3 kB gzip);
  boot-to-wizard-interactive **145 ms** measured in Chrome for Testing.

  **The founding decision, and it is the one to keep**: *if the parameter table
  has the path, the parameter table owns it.* Cell edges, occupancies, Bisos,
  profile terms and coordinate DOFs go through `PATCH /api/params`; species,
  labels, atoms added/removed, geometry, wavelengths and the background family go
  as a whole validated model. That is what stops this editor from becoming a
  second parameter table with its own copy of the tie/lock/bound rules — and it is
  why a cubic `b` refuses in `set_values`' own words rather than being written
  past its tie. Measured in the browser, one cell edit produced exactly one
  `PATCH /api/params` and no model patch; one species edit exactly one
  `PATCH /api/structure` and no `set_values`.

  **Four things worth carrying beyond this WP.**

  1. **A token crosses back, not a path.** Returning the staging path to the
     browser and taking it back would make every commit verb a path-traversal
     surface. Reader errors are scrubbed of the staging path too
     (`imports.scrub`), because gemmi quotes the path it was handed.
  2. **`aniso_available` is measured, not assumed** — the CIF is read a second
     time with `aniso=True` and the answer is whether any site came back with a
     tensor. `cod_1000236.cif` yes, `cod_1000055.cif` no. A checkbox offered on
     every CIF would be inert on most of them.
  3. **The species check moved to the boundary.** A `Structure` carrying `"D"`
     or `"Xx"` validates fine and fails at *stage compile*; `_as_structure` now
     refuses it naming the atom. A GUI-level judgement, not a schema change — the
     Python API still accepts it.
  4. **The FCJ note fires on the corner, not on the default.** WP-0601's
     S/L = H/L hazard is real, but both apertures default to **0**, where the
     correction is off; warning on every fresh lab instrument would be a warning
     nobody reads. `axialWarning` is silent for 0/0-and-held and speaks as soon
     as either is freed.

  **Two defects a real browser found and jsdom could not — the third session
  running of the same pattern.** (a) `structuredClone` **throws on a Svelte 5
  `$state` proxy** (`#<Object> could not be cloned`), so *Add atom* silently did
  nothing in Chrome while passing under vitest, which hands the same functions
  plain objects. `lib/model.ts:clone` is a JSON round trip now — exact here
  because every model in this panel arrived as JSON — and the vitest case added
  for it does fail with `DataCloneError` if you put `structuredClone` back.
  (b) `apply` reloads after a failure (a partial apply leaves the server
  half-ahead) and `load` cleared **the same variable** the refusal had just been
  written to, so an `UNKNOWN_SPECIES` 400 flashed and vanished. Split into
  `error` and `loadError` — WP-1013's wiped-squiggle bug in a new costume, and
  the general rule is worth stating: *two different facts must not share one
  field*.

  **Not built, deliberately.** No space-group editing (the WP's own hard fence);
  no drag-and-drop (a file input covers it and `DragEvent` is a jsdom gap);
  no Wyckoff *letter* in the `sites` arm — it needs `wyckoff.site_constraints`,
  which runs spglib per atom, on a route that refetches on every head move
  including one a `set_vary` made. The DOF counts and paths are what the editor
  acts on; the letter would be decoration bought with a symmetry search per
  keystroke. If WP-1015 wants it for the viewer, it should be its own route.

  **Gotcha for the next session on this panel**: the editors are mounted while
  hidden (so a typed species survives a look at the plot) and guarded by
  `active`, so the three GETs only fire while the pane is shown. If you add a
  fourth read, put it behind the same guard.
