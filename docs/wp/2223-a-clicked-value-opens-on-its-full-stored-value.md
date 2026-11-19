# WP-2223 — A clicked value opens on its full stored value, and an unchanged one is no edit

Milestone: gui-overhaul · Status: ✅ 2026-11-19 — both editors open on the full value, PR #1709
Depends on: 2218 (the Interactive tab and the Parameters panel at `/next`)

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

- **2026-11-19** — Built and closed, PR #1709.

  A value clicked in the GUI now opens on what is stored, to the last digit, in the
  Parameters panel and in the Interactive tab, on both pages. Leaving the text as it opened
  records nothing. Before, Enter on an unchanged Interactive value moved it by its 13th digit
  and recorded an edit. One behaviour changed on purpose: typing a cell's drawn digits into the
  Parameters editor, `4.1568` over a stored `4.15678`, is now an edit, since it is a different
  number from the one the editor showed. The drawn numbers are unchanged.

  - *Done*: `lib/numslot.ts:editText` is `String(v)` and serves both editors.
    `lib/interactive.ts:parseTyped` reads through `readNumber`; its old 12-digit text is
    `plainText`, kept for today's page's "Last fit" line and range fields. Each editor stores
    the text it opened on and returns early when Enter or a click away leaves it unchanged.
    `lib/table.ts:editState` gained `against: "stored"`, used by both Params panels, so the
    pending count and Apply's payload compare a typed number with the stored float. The
    Model form keeps `"drawn"`, since it still opens on the rounded value. Today's page's
    range fields keep their 12-digit text, and an end left as shown keeps the slider's value,
    the rule `/next` already had. The manual's two passages and the gui rulebook's line say
    so, and a release-note fragment is staged (`docs/releases/unreleased/1709.changed.md`).
  - *Review* (`/code-review high --fix`, 8 findings): 3 fixed. `setRange` did not record
    the applied text as shown, so after one range change, typing the old end back was read as
    "as shown" and moved nothing; fixed in both Interactive panels (the `/next` copy had it
    since WP-2218), with a regression case. Also the docstring's e-form example and a blank
    line. Declined: the early return compares with the text as opened even if a head move
    changed the value meanwhile (the rule as ruled); an empty opened text closes without a
    refusal (a non-finite value has no slider); a multi-cell selection opens blank ("Mixed")
    unless the stored values are equal, where it used to match on the drawn digits (opening
    on stored values is the ruling, and blank is honest); the range bookkeeping is copied in
    both Interactive panels (today's page goes at the swap); the editor opens wider for a long
    value (still clamped to the window).
  - *Fixed on the way*: a re-export of `editText` through `lib/interactive.ts` made rolldown
    emit a shared `rolldown-runtime.js` chunk with a modulepreload in `index.html`; the panels
    import from `lib/numslot.ts` directly. Two browser cases typed a digit after End to make
    an edit; at full precision that digit can sit past the double's last one, which is the
    same number, so they type it after Home. `reference/gui-guide.md` stood 12 characters
    under the manual's 50 000 cap, so the two passages were cut to fit (49 999).
  - *Measured* (macOS arm64, worktree `.venv` `[dev]` plus playwright 1.65.2, Python 3.12):
    fast suite on the final tree 15029 passed, 425 skipped and 32 xfailed in 9:38, through the
    shift's serial lock. Playwright makes the browser files run inside it. The added python
    test is the browser case `test_a_clicked_value_opens_on_its_full_value_and_enter_on_it_is_no_edit`,
    1.78 s in the junit file. Vitest 864 of 864, 7 more than WP-2218's last 857 (5 in
    `next/editbox.test.ts`, 1 each in `App.test.ts` and `lib/table.test.ts`). svelte-check 0
    errors in 460 files. Ruff and CI's Vale steps clean. Every browser file by glob (`tests/*_browser.py`), serially: 173 passed, one more than WP-2218's 172.
    The browser case fails with the editor text cut back to 12 digits (the Parameters cell
    `phases.0.scale` opened as `0.0000130672077598` against a stored 1.3067207759799018e-05),
    and so do two of the four vitest mount cases.
  - *Generality*: no flag, threshold or automatic action; `tests.audit_delta` reports no row
    changed. The judge was not dispatched.
  - *Next*: none here. The follow-on for WP-2218's background holds is WP-2224.

- **2026-11-19** — filed by the ghostshift runner for the edit-box ruling. No open WP owns the
  GUI's editor text: WP-2218 is the R3 build and waits only on Yue's look, and 2211 and 2212
  are the History table and the console.
