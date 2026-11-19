# WP-2223 — A clicked value opens on its full stored value, and an unchanged one is no edit

Milestone: gui-overhaul · Status: 🔄 2026-11-19 — claimed by @yue-here (ghostshift runner)
Depends on: 2218 (the Interactive tab and the Parameters panel at `/next`)
Priority: P2 2026-11-19 — Enter on an unchanged slider value moves the value by its 13th digit and records an edit nobody made

## Goal

A click on a value box in the Interactive tab or the Parameters panel opens an editor holding
the value as stored, to its last digit. Leaving that editor without typing a change records no
edit. The drawn numbers stay as they are.

## Context

**The ruling.** Yue asked on 2026-11-19 how a value drawn as ×10ⁿ looks once clicked, and ruled
"go with best practice". The lead chose the spreadsheet model: Excel and Google Sheets draw a
cell rounded and open its editor on the full stored value. Here that is the shortest text that
reads back as the same double, JavaScript's `String(v)`: up to 17 significant figures, in
e-form where JavaScript prints one (`2.7725887222397814e-7`) and plain where it prints plain.

**What the editors open on today.**

- The Interactive slider's value box (`gui/src/next/Interactive.svelte` `startTyping`, and the
  same code in `gui/src/panels/Interactive.svelte`, still mounted by `gui/src/App.svelte` as
  today's page) opens on `lib/interactive.ts` `editText`, 12 significant figures. Enter runs
  `parseTyped`, which reads the text with `Number`, so a value with more than 12 significant
  figures comes back different and `set` records it as an edit. `parseTyped` also refuses
  `1.5×10⁻³`, which the range pop-up's From and To read through `readNumber`.
- The Parameters panel's editor (`gui/src/next/Params.svelte` and `gui/src/panels/Params.svelte`
  `currentText`/`commit`) opens on `lib/numslot.ts` `editText`, the value at the digits its
  esd allows. A text equal to that is no edit (WP-1009's rule), so the editor never shows more
  digits than the cell.

`numslot.ts` `editText` has no caller outside the two Params panels. The `.rxt` document
renders its own numbers on the server (`src/rietx/gui/textdoc.py`, 12 significant figures)
and is not touched here.

**The rule.** An editor's text is compared with the text it opened on. The same text is no
edit, whatever the rounding; a different text is read and compared with the stored value.
This is WP-1009's rule applied to the opened text in place of the drawn one.

**The tier of each rule this WP adds.** None: no flag, threshold or automatic action. The
editor's text is display.

## Non-goals

- The drawn numbers: the slider's mantissa slots, the Parameters cells, and the old page's
  "Last fit" line keep their digits.
- The `.rxt` document's number format.
- What the Parameters editor accepts as typed text. The server reads what it is sent.

## Tasks

- [x] `lib/numslot.ts` `editText` gives the full stored value to both editors;
      `parseTyped` reads through `readNumber`; both Interactive panels and both Params panels
      record no edit for an unchanged text. Vitest for each.
- [x] Browser case at `/next`, by real clicks: a ×10ⁿ value opens on its full text, Enter
      records nothing; `1.5×10⁻³` typed into a slider's box is a pending edit at 0.0015.
- [x] Dist rebuilt; the manual's GUI chapters checked for a sentence about the editor's text.
- [x] Skill: none. The skill drives the python API, not the GUI.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py -k "full_value" -p no:randomly
```

## Handover log

- **2026-11-19** — filed by the ghostshift runner for the edit-box ruling. No open WP owns the
  GUI's editor text: WP-2218 is the R3 build and waits only on Yue's look, and 2211 and 2212
  are the History table and the console.
