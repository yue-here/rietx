# WP-1009 — Project text document: format + parser

Milestone: v1.0 · Status: ✅ 2026-07-30
Track: The human GUI
Depends on: WP-1004, WP-1005

## Goal

A line-oriented text rendering of the project (`.rxt`) with a single
server-side parser: `render(session state) → text` and `parse(text) → delta +
errors`, deltas applied as the same public verbs the forms use. The format
lands **before** the editor pane (WP-1013) so it is settled independently of
CodeMirror.

## Context

- **A line-oriented DSL, not TOML/YAML** — those lose the aligned columns
  that rectangular selection exists to bulk-edit, and their parse errors
  don't speak dot-paths. `@` marks vary (TOPAS muscle memory); bare value =
  fixed; blocks scope dot-path prefixes; `#` comments round-trip. Example:

  ```
  rxt 1
  project "NAC 11-BM"
  pattern "11BM_NAC.fxye"            # sha256 9f3ac2…  45,001 pts  3.0–155.0°
  mode rietveld
  limits 3.0 60.0

  phase 0 "NAC"                      # Ia-3d, cubic: b,c tied to a
    cell.a         @ 10.251285       min 10.1  max 10.4
    scale          @ 1.234e-6
    atoms.0.biso   @ 0.52            # Na
    atoms.1.biso     0.61            # Al  (fixed)

  instrument
    zero_shift     @ 0.00210
    background.c*  @                 # glob line: frees c0..c5

  plan mccusker_default
  stage cell     free phases.*.cell.*                       max_iter 100
  ```

- Locked/tied entries render as read-only annotations (`cell.b = tied
  cell.a`); editing one is an apply error **naming the tie** — same message
  the WP-1004 verb raises, surfaced with a 1-based line number. Glob lines
  are bulk-edit sugar, normalised to per-parameter flags on the next render
  (canonical output never emits them). Unknown keys are errors
  (`extra="forbid"` spirit).
- Deltas are applied as WP-1004's public verbs (`set_vary`, the set-value
  verb, plan PUT), so a text apply shows up in the console as API calls and
  in history as nodes — identical to a form edit. All-or-nothing: any error
  in the delta applies none of it.
- `src/rietx/gui/textdoc.py` carries `FORMAT_VERSION` (the `rxt 1` line);
  WP-1017 injects it into the manual as a fenced constant, so a format bump
  that misses the manual fails the build.
- **The parser lives only in Python.** The frontend gets a regex highlighter
  and no grammar (WP-1013), so there is no dual-parser drift to test.
- Server routes: `GET/PUT /api/textdoc` on the WP-1008 skeleton — GET
  returns `{text, revision}`; PUT takes `{text, base_revision,
  validate_only}` and CAS-rejects (409) a stale `base_revision`. The sync
  state machine on top is WP-1013's; this WP only guarantees the primitive.

### Inherited

From **WP-1004**: locked/tied refusal messages come from the verbs — quote
them, don't restate them, so the two surfaces cannot disagree.

From **WP-1005** (project container, landed 2026-07-30) — the sketch above is
missing one line and mis-sources two others:

- **`excluded 7.5 8.0 / 24.0 25.2` (or equivalent) must be in the format.**
  Excluded regions are protocol — CLAUDE.md's rule is to mirror another code's
  excluded regions or not compare Rwp at all — and they are in **neither** the
  pattern file **nor** `RefinementState`, so a history node cannot say what was
  excluded when it ran and the fingerprint does not change when they do. The
  project document is the only record (`ProjectDoc.excluded_regions`), which
  makes the text view the only place a human will ever *see* them. Apply through
  `Project.set_excluded_regions`, which is one verb precisely so the document and
  the `PatternData` cannot disagree. (Whether `RefinementState` should carry them
  is parked in WP-1003's `### Inherited`; the text document needs them either
  way.)
- The `pattern` comment should quote `DataRef`, which already has every field the
  sketch invents: `sha256`, `n_points`, `two_theta_range`, plus **`has_sigma`** —
  worth rendering, since "weights from the file's esd column" vs "Poisson
  fallback" is a correctness property of the fit that is otherwise invisible. And
  a pdCIF's **`block`** must render (it is in `DataRef.options`): the same file
  reads as a different pattern without it.
- `mode`, `limits` and `plan` come from `ProjectDoc` (the *next* run's settings),
  not from the head node (what a *past* run used). The two legitimately differ,
  and rendering the wrong one would show a user a plan they did not select.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): **reserve a
`peaks` block in `FORMAT_VERSION` now**, so WP-1027 fills it in without a
format bump. Two properties settle its design. Peaks are **not refinable
parameters**, so they carry **no `@` marker** — that absence is the visual
distinction from every other block. And only two of its columns are editable
on apply: `2theta` (which becomes a `move_peak` + group refit) and `flags`
(a `set_peak_flags`); esd, fwhm and intensity are *derived* and are
regenerated on the next render, so an edit to them must be rejected rather
than silently discarded. Sketch:

```
peaks 20                              # pick_peaks(min_sigma=5.0, shape=tchz)
  #      2theta      esd     fwhm         I    flags
   0     8.4712   0.0009   0.0812     10420
   1    10.7743   0.0011   0.0834      3310   impurity
```

From **WP-1008** (GUI server, landed 2026-07-30): `GET/PUT /api/textdoc` are
**already reserved** in `gui.session.RESERVED_ROUTES` and answer 404 naming this
WP, so filling them in is adding two entries to `gui.server.ROUTES` and two
methods to `GuiSession` — no routing work. Three things that shape the format:

- **The preset a project chose is not stored.** `ProjectDoc.plan` is an expanded
  `PlanSpec` with no name, so `GET /api/plan` *derives* `preset` by comparing the
  stored spec against all seven registry presets (`gui.session._matching_preset`,
  `null` for an edited plan). If the text document wants to render `plan:
  mccusker_default` rather than eight stage blocks, quote that helper — do not
  add a name field to the document, which would be a second authority that can
  disagree with the stages beside it.
- **Selecting a preset expands it through the mode**, because `Project.fit`
  passes `doc.plan` verbatim: `mccusker_default` under `lebail` stores
  `profile_only`'s stages. A text document round-trip must not "helpfully"
  re-collapse that back to the name the user typed.
- **Settings persist on the verb, not on Save** (the GUI writes `project.json`
  on every settings mutation), so a text-document edit that changes settings
  should behave the same way rather than waiting for a save the UI never shows.

## Non-goals

- No editor, no CodeMirror, no sync engine (WP-1013).
- No three-way merge — CAS conflict is a 409, full stop.
- No reading `.rxt` as a project interchange format (the project *is* the
  `.rex/` dir; the text pane is a view).

## Tasks

- [x] `src/rietx/gui/textdoc.py`: `FORMAT_VERSION`, `render`,
      `parse → (delta, errors)` with 1-based line numbers on every error.
- [x] Delta application through the WP-1004 verbs, all-or-nothing;
      locked/tied refused with the verb's own message + line number.
- [x] `GET/PUT /api/textdoc` with CAS revisions on the WP-1008 server.
- [x] `tests/test_textdoc.py`: round-trip fixed point (`render → parse →
      changes` is empty), hypothesis on the numeric half, every error carrying
      a line number, glob expansion on `fnmatch`. **Comments are *not*
      preserved** — see the handover log; the sketch in Context said they
      round-trip and that turned out to require a second authority.
- [x] *(found here)* `Refinement.parameters(mode=…)` + `Project.parameters()` —
      a Le Bail project's atom rows were reporting `mode_fixed=False`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_textdoc.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Profex/TOPAS-jEdit lineage: continuous validation, explicit apply.
- Parameter path conventions: dot-separated, fnmatch globs, no brackets
  (CLAUDE.md Conventions).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **text document** (WP-1009, `gui/textdoc.py`, `rxt 1`) is the line-oriented
view of a project — settings, plan, and every parameter row, where `@` frees and a
bare value holds. `render` → `parse` → `changes` → `apply`, and the rule that
makes it safe is that **a delta is diffed against the live project, never against
the old text**: an untouched document emits no verbs, a read-only field is an
error only when it *differs* (so everything can be shown without a "look, don't
touch" syntax), and a typed number is compared to the **rendered** value, which is
what lets values render lossily at 12 significant digits. Everything applies
through the same verbs a form calls — same history nodes — and every refusal is
the verb's own words (`held_because`, `TieSpec.describe`) with a line number
attached, never restated. Three grammar facts are load-bearing: a `tie` renders
**last** on its line (it contains spaces, so `=` runs to end-of-line); column
widths are **per block** (a fixed width made the renderer emit
`polarization 0.99min 0`, which its own parser refused); and a **stage line's
keys are derived from `StageSpec`** (`textdoc.STAGE_KEYS`), never listed, so a
new field on the schema reaches the renderer, the parser and — via
`test_textdoc`'s pin against `model_fields` — `lib/rxt.ts` too. Listed, it was
the same tuple in two places, and a field missing from both is not a rendering
gap but a value dropped on every save. An added key is not a `FORMAT_VERSION`
bump, on the events precedent: no line's *meaning* changed. Comments parse but do not
survive a re-render, on purpose: storing one would be a second authority.

## Handover log

- **2026-07-30 — complete.** 20 tests in `tests/test_textdoc.py`, fast suite
  1117 passed / 107 skipped in 20 s (numpy-only `[dev]` venv), ruff clean, and
  the routes exercised over real HTTP: `GET /api/textdoc` → 2738 bytes +
  revision, `PUT` with a value and a mode edit → `["ref.set_values({…})",
  "project.doc.mode = 'lebail'"]`, a replayed `PUT` → 409 `STALE_REVISION`, and
  an edit to a locked row → 400 `TEXTDOC_INVALID` with a line number per
  problem.

  **The design decision the WP did not have:** a delta is computed **against the
  live project, never against the old text**. `parse` is pure syntax; `changes`
  compares to `Refinement.parameters()` and `ProjectDoc`. Three things follow,
  and they are why the format needs no read-only syntax: an untouched document
  produces *no* verbs (which is what makes an editor pane safe to leave open), a
  field nobody can change can still be *shown* — it errors only when it actually
  differs — and values can render at 12 significant digits (lossy!) without an
  apply perturbing anything, because a typed number is compared against the
  **rendered** current value rather than the stored one.

  **Two renderer bugs its own round-trip test caught**, both of which would have
  shipped a document this module could not read back:

  1. A fixed 36-column value field collided with the first annotation on a long
     path — `polarization                   0.99min 0` — and the parser refused
     `'0.99min'` as an unknown annotation. Column widths are now per block.
  2. A tie rendered before the bounds swallowed them: `= 0.1993 +
     1·phases.0.atoms.1.dof.0` contains spaces, so `=` has to run to
     end-of-line. `tie` is last in `_ANNOTATION_ORDER`, and that ordering is now
     a grammar rule with a comment saying so.

  **A defect one layer down, found by needing the surface.** A Le Bail project's
  `.atoms.` rows came back `mode_fixed=False`: `Refinement._mode` is what the
  last stage *ran* in (`"rietveld"` before the first run) while the document says
  what the next run will use — so a client would have rendered the mandatory
  dummy atom's `biso` as editable, the exact trap that flag was added for.
  `Refinement.parameters(mode=…)` takes an override and `Project.parameters()`
  supplies `doc.mode`; `GuiSession.params()` and the renderer both go through it.

  **Deviations from the Context sketch, both deliberate:**

  - **Comments do not round-trip.** The document is regenerated from state on
    every read, so keeping a user's comment would mean storing it — in
    `project.json` (a second authority for something nothing else reads) or in
    the history (which would make a comment a refinement move). Comments parse
    and are ignored; a test pins that, and WP-1013 is told so its editor can
    warn before a re-render.
  - **`guard <x>` was added** to the plan section: `PlanSpec.correlation_guard`
    is part of the plan, and a document that omitted it would silently reset it
    to the default whenever a stage line was edited.

  Other decisions: the `plan` line names a preset and the `stage` lines *are*
  the plan, so **editing both at once is refused** rather than resolved by
  precedence (silently discarding the lines a user is looking at is the worse
  failure); a bad `phase 7` block **suppresses its own rows' errors**, because
  one mistyped index otherwise buries its own fix under twenty "unknown
  parameter" lines; and `PlanSpec.preset_name()` is now a schema method, so the
  GUI's plan editor and this renderer cannot disagree about what "custom" means.

  **Not done:** the reserved `peaks` block is recognised and refused with its
  owner (`RESERVED_BLOCKS`), with the intended column layout and the two
  editable columns recorded in the module docstring — WP-1027 fills it in
  without a format bump.

- **2026-07-29** — created from the v1.0 GUI plan.
