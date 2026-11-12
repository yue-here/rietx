# WP-1214 — Model: vary in the editor, and save instrument profile

Milestone: v1.2 · Status: ✅ 2026-08-28 — the flag beside the value, the profile saved, and the fourth held reason the marks never had
Depends on: WP-1201

## Goal

Refinement on/off flags can be set where crystallographers read the model
(the Model panel), through the same verb the parameter table uses; an
instrument profile can be saved from the GUI, not only loaded.

## Context

The user: "The natural place for crystallographers to set refinement on/off
flags is in Model panel, as the structure and instrument parameters are much
more readable there. Parameters is not a familiar interface." And: "Need a
GUI route for save instrument profile."

Findings (2026-08-25):

- `Model.svelte` has no vary control; its writes are `PATCH /api/params
  {values}` (`:416`), `PATCH /api/structure`, `PATCH /api/instrument`,
  `POST /api/structure/aniso` and the symmetry routes.
- `Params.svelte:253-269` renders the vary checkbox for `row.refinable` and,
  for a held row, no checkbox at all with `held_because` as the tooltip and
  the three reasons as three glyphs (WP-1011's rule). Per-row edits go as
  one `PATCH /api/params {values, vary}` with a console echo per path
  (`:118-126`); bulk goes by glob (`:111-114`). Server side `params_patch`
  applies `values` then each `vary` key (`session.py:567-595`), one
  `set_vary` node per key.
- `GET /api/structure` is `structure.model_dump()` (`session.py:740`), so
  every `Parameter` carries `vary`; `held_because` is a `ParameterRow`
  property only. `Model.svelte` already joins the params rows by path
  (`byPath`, `:326`; `heldReason()`, `:602-606`) and refetches `api.params()`
  in `load()` (`:364`). The missing piece is the widget and a `vary` key in
  the existing `api.patchParams` call.
- `save_instrument_profile` (`io/instrument_profile.py:40-63`) has no
  caller in `src/rietx/gui` or `gui/src`; the GUI only loads
  (`imports.py:340-356`, `Model.svelte:834-837, 1117-1120`). The export
  family (`server.py:274-277`, `session.export`, `session.py:2178-2212`) is
  **result-gated** (`_need_result`, 409 `NO_RESULT`) and writes under
  `exports/` (`_export_target`, path-confined); there is no download route.
- Format: tag `instrument_profile` (`_about.py:55`), version `"1"`; the
  writer zeroes displacement and transparency and drops the specimen terms.

Design: a `vary` toggle beside every editable value in Model (cell edges,
occ, Biso, DOFs, ADPs, the strain and size terms, every instrument field);
a held value shows the reason, no toggle (the WP-1011 rule); toggles
accumulate with the value edits and go in the same `PATCH`, one node per
path, echoed as `ref.set_vary(...)`. `POST /api/export/instrument_profile`
joins the family but is **model-gated** (`_need_project`, not
`_need_result`), writes `exports/<name>.json` via `save_instrument_profile`,
and the button sits beside `Load profile…` with the written path shown.

## Non-goals

- The structure table's shape (WP-1215), the instrument grid (WP-1216).
- A download route: exports stay files under the project, as today.

## Tasks

- [x] `Model.svelte`: the vary toggle on every editable field; held reason
      rendering shared with Params (`lib/table.ts` helper); the `vary` key
      in the apply; `model.test.ts` on the payload.
- [x] `POST /api/export/instrument_profile` (model-gated) + the button;
      `test_gui_server.py` round-trips save → `load_instrument_profile`
      with every `vary` false and the specimen terms cleared.
- [x] Manual: `using/model.md` (vary from the editor), `files.md` (the
      profile's save route).
- [x] Browser pass; dist.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "profile or vary"
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1011 (a held row gets no checkbox), WP-1014 (what the table owns).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**The refine flag where the model is read** (WP-1214, `Model.svelte`,
`lib/table.ts`, `session.export`). Four rules. **A flag is set beside the value
it is about**: the Model panel draws the parameter table's own vary control on
every value it shows, one `set_vary` node per path, in the *same* `PATCH
/api/params` as the value edits and **before** the model patches — a whole-model
PATCH carries whatever `vary` the model it was built from had, so a flag set
after that read is reverted by it. **The held marks are one vocabulary and there
were four**: `heldGlyph` is in `lib/table.ts` because two panels draw it, and the fourth
(`needs_held_cell`) had worn the mode-fixed mark since it arrived, the glyph being a ternary
whose last arm caught everything — so an unknown reason still draws a mark, an
empty box reading as a control that failed to render, and
`test_gui_server.py` reads the fields `ParameterRow.refinable` tests **and `lib/table.ts`'s
own branches**, so a sixth fails on both sides (it checked only python until WP-1435's `held`
tripped the wire with nothing behind it). **A field's parameter path is not always its model path prefixed** — `source.polarization` is `instrument.polarization` in θ — so
`Field.param` carries it and `fieldParam` is what every lookup asks; unprefixed,
that field rendered off the model, applied past `set_values`' bounds, and had no
row for a flag to act on. And **an export is gated on what it describes**:
`instrument_profile` is answered from the project where the rest of the family
needs a result, `_EXPORT_MODEL_ONLY` declaring the exception so the stricter
gate stays the default. One more browser trap and it is a width: a rule aimed at
the value reaches the control beside it, and `.cellrow input { width: 100% }`
drew the esd next to the box at zero width.

## Handover log

- **2026-08-28** — Refinement flags can be set where a crystallographer reads
  the model. Every value the Model panel shows now carries the parameter
  table's own vary control beside it, so choosing what to refine no longer
  means learning dot-paths and globs in a second panel; a value the model
  holds shows *why* in place of the box. Two things had to arrive with it: the
  phase's scale and its four sample-broadening terms, which had no control
  anywhere in the editor although one of them (`lor_size`) is the parameter
  most often freed by hand, and `Save profile…` beside the `Load profile…`
  that has been there since WP-1014 — the GUI could read a calibrated
  instrument and had no way to write one. Driving it in Chrome found two
  defects, and the first is a fact about the package rather than about this
  panel: a row can be held for **four** reasons and the interface has only
  ever drawn three, so every project's λ1 has been wearing the mode-fixed mark
  since `needs_held_cell` landed.

  **Done.** `Model.svelte` renders one `varyBox` snippet at five sites (the
  cell row, the new Phase grid, occ/Biso, the coordinate DOFs and ADP
  patterns, every instrument field); the flags accumulate in `varyEdits`
  keyed by *parameter* path and ride the same `PATCH /api/params` as the value
  edits, one `set_vary` node per path, echoed to the console as
  `ref.set_vary(…)`. That PATCH runs **before** the model patches, because a
  whole-model PATCH carries whatever `vary` the model it was built from had.
  `lib/table.ts` grew `heldGlyph`/`varyOf`/`varyEdit`, which `Params.svelte`
  now calls instead of its own copies. `lib/model.ts` grew `Field.param` (the
  parameter path where it is not the model path prefixed) and `phaseFields`.
  `POST /api/export/instrument_profile` joins the export family as the one
  member gated on the model rather than on a result (`_EXPORT_MODEL_ONLY`
  declares the exception, so the stricter gate stays the default), and
  `server.py` builds the family from `EXPORT_DEFAULTS` rather than from a
  second list of the kinds. Manual: `using/model.md` says the panel calls the
  same verb and that globs stay in the parameter panel; `using/files.md` says
  where the profile is written and why saving needs a model rather than a fit.
  Four rules in `gui/CLAUDE.md` (cap 879 → 902, reason beside it), and
  WP-1011's own three-reasons sentence amended in place.

  **The fourth held reason.** `ParameterRow` has had `needs_held_cell` — a
  free wavelength needs its histogram's cell held, since d = λ/(2 sin θ) fixes
  only the product — since free wavelengths landed, and `heldKind` never knew
  it. Params drew it as `·`, the mode-fixed mark, because the glyph was a
  ternary chain whose last arm caught everything; sharing that chain turned
  the wrong mark into **no mark at all**, which is what the browser showed and
  jsdom could not (a held row with an empty box reads as a control that failed
  to render). `heldKind` has a fourth state now, `≈` for a degeneracy rather
  than `=` for a tie — nothing derives the row, another free parameter merely
  makes it unmeasurable — an unknown reason still draws a mark, and
  `test_gui_server.py` reads the fields `ParameterRow.refinable` actually
  tests (by `ast`, not by substring: `locked` contains `lo` and the docstring
  contains `set_vary`), so a fifth fails there before it reaches a panel.

  **Measured** (darwin/arm64, `[dev]`, this worktree's own venv). Fast
  selection 3197 passed / 122 skipped in 164-339 s over three runs, the last
  on the reviewed tree, +2 python tests on the session's start; `tests/test_gui_server.py` 149 passed; vitest 537 → 551
  (+5 App, +4 `table.test.ts`, +4 `model.test.ts`, +1 `wizard.test.ts`),
  `svelte-check` 378 files 0 errors; the full selection did not run — this WP
  moves no measured number in the acceptance suites. In Chrome on the 11-BM
  NAC example (fit converged 1.59 s, Rwp 9.32 %): 37 boxes and 7 held marks
  across the two form columns, one toggle moves the structure column's height
  by **0 px** (943.359375 both sides), the footer counts the flags beside the
  values, Apply lands `phases.0.lor_size` free (n_free 25 after), and the
  profile writes to `exports/instrument_profile.json`. The only 4xx responses
  the page makes are the Peaks panel's pre-existing `/api/index/*` 409s.

  **Gotchas.** `source.polarization` is `instrument.polarization` in θ, which
  is why `Field.param` exists: unprefixed, that field rendered off the model,
  applied as a whole-model PATCH past `set_values`' bounds, and had no row for
  a flag to act on — a silent wrong routing, because a field the table does
  not have is an ordinary model field. A width rule aimed at values reaches
  the controls beside them: `.cellrow input { width: 100% }` gave the checkbox
  all 84 px of its line and drew the esd next to it at zero width, present in
  the DOM and invisible on screen. And the atom table's aniso checkbox is
  addressed by `data-aniso` now — "the first checkbox in the table" stopped
  being an address the day the flags arrived.

  **The review's four, and two of them behaviour.** `/code-review medium
  --fix` found and applied: (1) **a stale flag survives a head move and sends
  a node saying nothing** — `load()` keeps typed edits across a reload and a
  stale *value* edit drops itself, because `splitEdits` compares against the
  rendered value, while a flag had no such comparison; tick a box, let someone
  free the same path from the parameter panel, and Apply sent a `set_vary`
  whose hits are empty, which `Refinement.set_vary` still commits a node for
  (`refine.py:528`, verified). `varyPending` is that comparison, filtered
  against the live rows; `varyEdits` still backs the checkbox. (2) **`Save
  profile…` wrote the server's instrument, silently ignoring unapplied edits
  in the column above it** — a typed `W` nobody applied would be absent from
  the file with nothing said, and the file is what a whole lab's later samples
  load; the button now waits on `insPending` and says so. (3) The manual's
  own **"The three reasons a row is held"** chapter, four rows in its table
  since `needs_held_cell` landed — the same rot as the glyph, in a third
  place, and the sentence this WP added had said "three" too. (4) Two stale
  comments in `Params.svelte`. Nothing was declined.

  **Not done, deliberately.** The phase's *corrections* (extinction,
  preferred orientation, the Stephens block) get no control: each is declared
  per phase rather than always present, so offering one is offering to declare
  it, which is a model edit this form does not make. The instrument form shows
  no esds (WP-1216's call).

  Next: this WP is closed, so **[1215](1215-structure-table.md)** (the
  structure table's shape) — it inherits an atom table that now carries three
  checkboxes per row — then [1216](1216-instrument-form.md) and
  [1217](1217-history-graph-compare.md).

- **2026-08-25** — created from the v1.2 triage.
