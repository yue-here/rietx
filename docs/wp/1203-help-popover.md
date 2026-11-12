# WP-1203 — The help popover: one mechanism across the panels

Milestone: v1.2 · Status: ✅ 2026-08-26 — one popover over the corpus, and 51 authored tooltips left, counted
Depends on: WP-1201 (the registers), WP-1202 (the corpus)

## Goal

Hovering any entity that has help shows the help cursor; a click opens one
popover with the entry's title, description, unit, default, typical range and
a link into the manual. `title=` survives only on buttons, as a verb phrase.

## Context

User decision (2026-08-25): **cursor-only**, no visible mark before hover
(the alternatives offered were a dotted underline and a ⓘ glyph). The user's
own words: "on cursor-over things such as headings, should have cursor changes
to question mark + cursor, and on click shows a clear description of that
entity's role in the refinement, with good default values or common ranges".

Findings:

- No popover, tooltip or help component exists; `cursor: help`,
  `aria-describedby`, `popover` and `role="tooltip"` have zero hits in
  `gui/src`. `title=` counts per panel: Peaks 41, Series 23, Model 16,
  History 10, Plot 10, Params 9, Plan 9, Report 9, App 9, Structure3D 8,
  Console 2, Text 2; plus `lib/controls.ts` 22 and `lib/wizard.ts` 17 as
  `title:` props.
- Where the corpus lands (WP-1202): a `ParameterRow` carries `help_key`, the
  family glob, **not** the entry — inlining one on every row measured 3.4x the
  `/api/params` payload (20.8 kB → 70.0 kB on the NAC example) against 40.7 kB
  for the whole registry fetched once. `GET /api/help` serves the arms;
  `help_key` is `None` only when no family claims the path, never "nobody
  looked". Fetch it once at startup like `/api/capabilities`: it needs no
  project and is not behind the in-flight 409.
- The arms and their key vocabularies: `parameters` (a list, grouped by entry,
  each carrying every glob that reaches it), `peak_flags` (13, `PeakFlag`),
  `peak_diagnostics` (12 `PEAK_*` codes), `stage_fields` (9 `StageSpec`
  fields), `reader_options` (2), `instrument_fields` (11, the union of
  `INSTRUMENT_PRESETS`), `plans` (7, each carrying `modes`) and — added here —
  `search_fields` (21, `IndexingControls` flattened one level). Six fields per
  entry: `title`, `description`, `unit`, `default`, `typical`, `anchor`.
- Panels where a term needs help: Params (parameter names), Model (field
  labels, atom columns, the wizard's fields), Plan (stage fields, the preset),
  Peaks (flag chips, table headers, the search controls), Report (statistic
  names), History (Rwp, GoF, action names), Series (status chips), Plot
  (residual and scale knobs). Panel headings too.
- Two meta-tests already pin that fields carry a `title`
  (`wizard.test.ts:178-207`, `controls.test.ts:55-60`): they become "carry a
  help key that resolves in the corpus". Their target set is ready — every
  `INSTRUMENT_PRESETS` field and every `StageSpec` field has an entry, crossed
  both ways — so the converted test can pass on day one.
- jsdom traps recorded in `gui/CLAUDE.md`: no `ResizeObserver`, no
  `DragEvent` (filled in `test-setup.ts`); a popover positioned from
  `getBoundingClientRect` gets zeros there, so position logic is a pure
  function in `lib/help.ts` and asserted on numbers.

Design:

- `gui/src/panels/Help.svelte`: `<Help for="phases.*.cell.a">term</Help>`
  wraps the term in a `<span class="help">` (`cursor: help`, no decoration);
  click opens the single app-level popover (one instance mounted in `App`,
  fed through a store: anchor rect + entry). Esc, click-away and a second
  click close it. Keyboard: the span is focusable and Enter opens it.
- `lib/help.ts`: `resolve(key)` over the params rows and the `/api/help`
  arms; `place(anchor, viewport, size)` returns the popover position (below
  the anchor, flipped above when it would leave the viewport, clamped
  horizontally).
- The popover body: title, description, `unit`, `default`, `typical`, and
  `in the manual →` to the entry's anchor. **Decided on arrival** (WP-1202
  handed this WP the choice): an `anchor` becomes `page.html#heading-id`
  relative to the manual root, and `GET /api/help` carries `docs_url` beside
  the arms so no frontend spells the site's address. Measured: 30 distinct
  anchors, every one on exactly one page of the built manual, so the change
  was mechanical and `test_every_anchor_resolves_in_the_built_manual` now
  checks the page as well as the id.
- `title=` audit. Measured inventory: 151 `title=` in the components — 58 on
  `<button>`, 93 not (29 `<label>`, 30 `<span>`, 8 `<th>`, 5 `<p>`, 5
  `<input>`, 4 `<td>`, 3 `<option>`, 3 `<Splitter>`, 5 `<div>`) — plus 21
  authored `title:` strings in `lib/controls.ts` and 11 in `lib/wizard.ts`.
  **Decided on arrival**, against this WP's "expects none": 18 of the 93 are
  not authored prose at all, so the rule is *what a title may be* rather than
  *where it may sit*. A `title=` survives on a `<button>` as a verb phrase,
  and on anything else only where it reveals a value the layout truncated
  (6 sites: `project.path`, `node.api_call`, `row.path`, two `dof.path`).
  The 12 carrying a sentence the **server** wrote (`held_because`,
  `refuted_reason`, `maturity.message`) become `<Help text={…}>`, which is
  what makes App's `⚠ not a fit yet` chip keyboard-reachable — the debt
  WP-1201 left here. The vitest is therefore: no `title=` string literal
  outside a `<button>`, and no authored `title:` prose in `lib/*.ts`.

## Non-goals

- No help *content*, with one exception taken on arrival: entries are
  WP-1202's, and a missing entry renders the popover with the title and a
  "not yet described" line and is a test failure there, not here. The
  exception is the `search_fields` arm — WP-1202 covered no indexing search
  setting, so `lib/controls.ts`'s 21 strings had nowhere to go and the task
  below could not be done. They were **moved**, not rewritten.
- No wizard prose rewrite (WP-1205), no peaks flag labels (WP-1209): those
  WPs *use* this component.

## Tasks

- [x] The corpus side the client depends on: `anchor` gains its page,
      `GET /api/help` gains `docs_url`, and the `search_fields` arm lands
      with its both-ways cross and a default crossed against the schema.
- [x] `lib/help.ts` (`resolve`, `place`) + `help.test.ts` on the placement
      numbers and the resolution order, plus `tests/test_gui_help.py` and the
      committed key set every literal `<Help for=…>` is crossed against.
- [x] `Help.svelte` + the single popover in `App.svelte`; the help cursor
      and the popover styled on WP-1201's tokens. Params is wired as its
      first consumer, and the header chip's owed debt is paid.
- [x] Wire every term the corpus covers: Params (paths, held rows), Model
      (cell edges, atom columns, the wizard's preset fields, the instrument
      editor, reader options), Plan (stage fields, the preset), Peaks (flags,
      diagnostics, the 21 search controls). `lib/controls.ts` and
      `lib/wizard.ts` now *derive* a corpus key from each field's own name
      rather than carrying prose; `lib/model.ts`'s `Field` gains `help` and
      keeps `title` as a named escape. Both title meta-tests retargeted.
- [x] The `title=` audit as a **counted budget** rather than a ban: 51
      authored literals remain, per file, each fails both ways. Report
      statistics, series settings, indexing result columns and the 3D drawing
      thresholds are vocabularies the corpus does not describe, and they
      arrive with the WPs that own those panels.
- [x] Browser pass: the popover on Params, Plan, Model and Peaks, light and
      dark, flip and clamp exercised at a 760 px window, keyboard open and
      close measured; one defect found and fixed (the parameter row's width
      budget). Committed dist rebuilt.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_dist.py -q
```

The title vitest is green; the browser pass shows one popover style on every
panel.

## References

- WP-1032: `title=` as the only help mechanism and the no-mute-fields rule
  this WP retargets.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

Two rules for anything a person reads here (v1.2, WP-1201/1202/1203):
**GUI prose is written under `/yue-docs-style`** (help entries, wizard lines,
empty states, error text), and **what a name *means* is an entry in
`rietx.help` reached through `<Help>`; `title=` is what is left over.** The
popover is WP-1203 (`Help.svelte`, `lib/help.ts`, one instance in `App`), with
six rules. A key is **`arm:name`**: the arms' vocabularies overlap, so a
bare key would resolve by declaration order; each is crossed against
`tests/data/gui/help_keys.json`. A field inventory **derives** its key from the
field's own name where the arm is keyed by the same vocabulary (`controls.ts`,
`wizard.ts`) and carries it as **data** where it is not (`lib/model.ts`). `<Help
text=…>` is for a sentence the **server** wrote (`held_because`, a refutation, a
maturity message), which no corpus can hold because it is about one row rather
than one name. What may still be a `title=` is a **value the layout truncated**,
or a verb phrase on a `<button>`, never authored prose — `lib/help.test.ts`
holds that to an exact per-file count failing both ways, so the debt stays
countable and its list cannot outlive it. And a term is a `<span
role="button">` because it wraps running text: sound only while it stays
focusable, answers Enter and Space, and is **hittable** — a flex item's
automatic minimum is its content size, which left `.path` at zero width in a
340 px sidebar (v1.2's record has the numbers). It is **named by its
children, never by an `aria-label`**, which renames the `<label>` or `<th>`
enclosing it; `aria-haspopup="dialog"` carries the role hint instead, and the
popover **takes focus**, a `role="dialog"` nobody is in announcing nothing.

## Handover log

### 2026-08-26 — one place to ask what a name means, and a countable list of where you still cannot

A person using the GUI can now click almost any name and be told what it is:
what the quantity means, its unit, the schema's own default, a range to compare
their number against, and a link to the chapter with the equation. Hovering
shows a question-mark cursor and nothing else, which was the decision at the
milestone opening. It works from the keyboard, which the old `title=`
mechanism never did — and one message had been *out* of reach since WP-1201
moved the header's "not a fit yet" badge off a button. What it does not cover is
named rather than hidden: 51 explanations are still hover-only tooltips,
counted per file by a test, because they describe report statistics, series
settings, indexing result columns and 3D drawing thresholds, and the corpus has
no vocabulary for any of those yet. Those arrive with the WPs that own those
panels; the mechanism is now waiting for them.

**Two decisions taken against this WP's own written design**, both because the
measurement said so, and both offered to the maintainer first (no answer, so
the recommendation stands and is recorded here).

- The WP said "no help content: entries are WP-1202's", and also "move
  `lib/controls.ts` titles into corpus keys". Those contradict: WP-1202 covered
  no indexing search setting, so those 21 strings had nowhere to go. The
  `search_fields` arm landed here. The prose is the form's own, **moved**, not
  rewritten — the form was the only place several of those measurements were
  written down.
- The WP said a vitest should grep for `title=` on non-button elements "and
  expect none". Measured inventory: 151 attributes, 58 on `<button>`, and 18 of
  the other 93 are not authored prose at all — 6 reveal a value a narrow column
  truncated, 12 carry a sentence the *server* wrote. A ban would have deleted
  working behaviour and forced `held_because` to be re-rendered through a
  popover everywhere it appears. The rule is therefore about *what a title may
  be*, and the guard is a **counted budget** rather than a ban.

**Done.**

- `HelpEntry.anchor` is `page.html#heading-id` (WP-1202 left this WP the
  choice); `GET /api/help` carries `docs_url` beside the arms so no frontend
  spells the site's address. `test_every_anchor_resolves_in_the_built_manual`
  now checks the pair — an id on some *other* page used to pass.
- `search_fields`, 21 entries, `IndexingControls` flattened one level and
  crossed both ways against the document's own model. Its `default` is crossed
  against the schema rendered as JSON, which closes the hole WP-1202 named and
  left open (every other arm's default is prose restating a live constant).
- `lib/help.ts` (`resolve`, `place`, `manualUrl`, `paramKey`), `Help.svelte`,
  one popover in `App`, `.popover` in `app.css`, and `tests/test_gui_help.py`
  writing the committed key set `tests/data/gui/help_keys.json`.
- Wired: Params (paths, held rows), Model (cell edges, atom columns, wizard
  preset fields, instrument editor, reader options), Plan (stage fields, the
  preset), Peaks (13 flags, 12 diagnostics, 21 search controls).
- `ControlField` and `PresetField` carry no `title` at all and **derive** their
  key; `lib/model.ts`'s `Field` carries `help` as data plus `title` as an escape
  held to a named list of two (`geometry.kind`, `profile.shape`).
- One defect the browser found and jsdom cannot: the parameter row's width
  budget. Repaired as three widths with the reason beside them.

**Measured** (`[dev]`, darwin/arm64; main had not moved under the branch, so
these are the merged tree's).

- Fast suite **2980 passed / 72 skipped**, 5m14s. This WP adds exactly 7 python
  tests, verified by collection: `test_help.py` 18 → 20, new `test_gui_help.py`
  5. The rest of the move from WP-1202's 2814/117 is three PRs merged into main
  since that measurement, not this branch.
- vitest **441 passed** across 21 files, from 431 at the branch point: 16 in the
  new `lib/help.test.ts` were already counted at 431, then +7 popover tests in
  `App.test.ts` and +3 title-audit tests. `svelte-check` 377 files, 0 errors.
  `ruff` clean.
- No new skips. The full suite was **not** fired: no residual, Jacobian or
  solver code was touched, and no slow test pins anything this changed.
- The row budget, measured in Chrome before and after at 1400 / 1100 / 1000 /
  900 / 760 px: `.path` 159 / 45 / 7 / 0 / 0 px → 219 / 105 / 68 / 55 / 54 px;
  `.value` 152 px throughout → its declared 92.
- Corpus 92 → 113 entries, 7 → 8 arms. `/api/help` is 59 kB; the committed key
  set is 5 kB, which is why it carries names and not prose.

**Gotchas for the successor.**

- **A key is `arm:name` and a bare name is refused.** `seed` is a stage field
  *and* a search control; `preset` is a search control *and* a word a plan owns.
  A test asserts the collision is still real, so the rule cannot outlive its
  reason.
- **A parameter key is the family glob, never a path.** `resolve` does not run
  fnmatch — the server matched it and the row carries the answer in `help_key`.
  `parameters:phases.0.cell.b` deliberately resolves to nothing.
- **A scroll closes the popover, on purpose**, which bites a browser driver: a
  click issued while a smooth scroll is still settling closes what it just
  opened. Scroll, wait ~900 ms, then click. Two sessions' worth of confusing
  nulls came from that.
- **`Placement.flipped` has a reader for a reason.** A popover taller than the
  viewport clamps to the top margin, which is exactly where flipping would put
  it, so the flag is the only thing separating the two cases; it is on the
  popover as `data-flipped` and that is what a browser pass reads.
- The chromium binary is at `chrome-mac-arm64/Google Chrome for Testing.app`,
  not `Chromium.app`, in the cached playwright install.
- `.bounds` is now the parameter row's shrinking column (120 → 93 px at the
  sidebar floor). If a later WP wants it fixed-width again, the 44 px floor
  under `.path` is what has to move with it.

**Next: WP-1205**, the wizard's new-project defaults, which is the next row in
the v1.2 table and the first WP that *uses* this component rather than building
it. Its `### Inherited` now carries the two things it cannot read off the code:
that a preset field's help key is derived from its own name (so a field it adds
needs an `INSTRUMENT_FIELD_HELP` entry or it fails `test_help.py`, not a
`title=`), and that the wizard's remaining authored tooltips are inside a
counted budget. WP-1208 (Plan) and WP-1209-1213 (Peaks and the plot) carry the
same note about their own panels' counts.

- **2026-08-25** — created from the v1.2 triage.
