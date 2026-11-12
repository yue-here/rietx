# WP-1209 — Peaks table: numbers, columns, flags

Milestone: v1.2 · Status: ✅ 2026-08-27 — shipped; the threshold measured, the trap recorded
Depends on: WP-1201, WP-1203

## Goal

The peak table reads like a peak table: intensities as a relative scale,
positions to a sensible number of digits, degenerate lines shown as such, a
`use` column of its own, and flags as short labels whose meaning is one click
away.

## Context

Six notes from the user, one cause each (2026-08-25):

- **"Intensities of 1e-17, 1e-21."** The picker fits areas with a native
  lower bound of exactly `0.0` (`indexing/peakfit.py:343-362`); on the
  certified corundum pattern two components refine to 2.1e-49 and 5.5e-19
  (`indexing/pick.py:163-168`). Such a line is flagged `no_intensity`
  (`pick.py:194-195`, `BOUND_HIT_RTOL`) and is unusable, but the table still
  prints `Number(p.intensity.toPrecision(3))` (`Peaks.svelte:578`).
- **"Ten or more decimal places."** `formatValue` (`lib/table.ts:279-311`)
  chooses `places = -floor(log10(esd))` clamped to 12, so a tiny esd gives
  twelve decimals.
- **"Two theta positions in chips."** The 2θ cell renders value and esd as
  `formatValue` + `formatEsd`; with an esd ≥ 1° the places clamp to 0 and a
  line at 35.09° with the measured degenerate σ of 111° prints `35(111)`
  (`Plot.svelte:417-420` records the 111°; the whisker is capped at 3×FWHM
  on the plot, never in the table).
- **"Chips are different sizes."** `Peaks.svelte:989` `.chip` (10px) and
  `:1039` `.note` (12px) collided. WP-1201 fixed the mechanism: a chip's size
  is the register's (`--text-xs`, `app.css`), the panel declares no `.chip`
  rule and a literal `font-size` in its `<style>` fails `lib/style.test.ts`,
  and a tone is a member of one app-wide vocabulary (`note` the default, `ok`,
  `warn`, `bad`, `accent`) returned by `lib/peaks.ts`'s `flagTone` /
  `caveatTone` / `confidenceTone`. **A chip is a fact and never acts**: a verb
  on a chip sits beside it in a `.tagged` wrapper. This WP owns the flags
  cell, and a new flag colour is a call to a tone function, never a
  `.chip.<something>` rule.
- **"On/off should be its own column."** The use-for-indexing checkbox is
  the first item of the unnamed actions cell with `↻` and `×`
  (`Peaks.svelte:587-591`); it POSTs `use_for_indexing`, and checking
  **strips every unusable flag** (`gui/peaks.py:188-191`).
- **"Remove the flags text description."** Flags render as bare tokens
  (`Peaks.svelte:605-609`); the fitter's diagnostics render as a strip of
  `code` + `message` (`:569-579`). The vocabulary is `PeakFlag`
  (`schemas/indexing.py:428-442`), thirteen values. Since WP-1203 **a flag's
  meaning is already rendered**: every chip in the flags column and every
  `PEAK_*` code in the strip is a `<Help>` term over `rietx.help`'s
  `peak_flags` (13) and `peak_diagnostics` (12) arms, so what this WP owes is
  the *label* — the short words on the chip — not a second explanation.
  Changing what a flag means is an edit to `help.py`.
- **The panel's authored `title=` budget is 12** (`lib/help.test.ts`, failing
  both ways). Three of the twelve are the peak table's — the add-at-2θ box,
  the `σ assumed` chip, the `origin` chip — and nine are the indexing result's
  (WP-1211). Describing one properly means a corpus arm keyed by a live
  vocabulary, the way `search_fields` was added in 1203; `origin` is
  `ObservedPeak.origin`'s `Literal`, and the σ-assumed chip is the list-level
  `PEAK_SIGMA_ASSUMED`. The 21 search-control fields are done
  (`searchHelp(field)`).

Rules: flagging, never dropping (`schemas/indexing.py:424-427`,
`pick.py:155-160`); the `.rxt` peaks block's only editable columns are
`2theta` and `flags`; `usable` derives from flags only.

Number policy (in `lib/peaks.ts`, pure, tested): intensity shown as
`I/Imax × 100` at one decimal (a `no_intensity` or `fit_failed` line shows
`—`); 2θ at 4 places with the esd in parentheses only when esd < 1°, else
the value alone and the flag says why; `d` at 4 places. `formatValue` gains
the esd ≥ 1 guard for every caller (History and Params included). The
threshold was triaged at 0.1° and measured to 1° in the browser pass: on
corundum 51 of 62 esds are under 0.01°, 8 in [0.01, 0.1), one real
asymmetric line at 0.105° (printed bare beside a neighbour's `(875)`), and the
two degenerate ones at 1e17° and 1e49°; the widest FWHM is 0.35°, so a
degree is wider than any peak.

## Non-goals

- The peak layer on the plot (WP-1210), candidates (WP-1211).
- Changing what the picker fits or flags.
- Re-styling the search form. WP-1201's browser pass saw its twelve centring
  toggles all engaged by default, twelve filled accent buttons, which is what
  `button.on` says and is loud. Whether a defaults-on multi-select wants a
  quieter engaged state is a decision for `app.css`, not `Peaks.svelte`, and
  it belongs to whichever WP next touches that form.

## Tasks

- [x] `lib/peaks.ts`: `formatIntensity`, `formatPosition`; `formatValue`
      guard; `peaks.test.ts` pins the corundum cases (2.1e-49, 5.5e-19,
      σ = 111°, a 1e-13 esd).
- [x] Table: columns `# · 2θ · d · I (rel) · flags · use · actions`; the
      `use` checkbox in its own header column; `origin` chip in its own tone.
- [x] Flags as labels from the corpus (`at bound`, `Kβ ghost`, `W ghost`,
      `not separable`, `shoulder`, `σ assumed`, `no intensity`, …) with the
      code and sentence in the popover; the diagnostics strip folded into a
      count chip that expands.
- [x] Browser pass on the corundum example after Pick peaks; dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_peaks.py -q
```

## References

- WP-1018 (peak picking), WP-1027 (the panel), WP-1110 item 14 (the
  degenerate esds the pseudo-inverse used to truncate).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**The peak table's numbers and chips** (WP-1209, `lib/peaks.ts`, `lib/table.ts`,
`panels/Peaks.svelte`). Four rules. **A column is scanned, so its places are
fixed**: 2θ at four with the esd in the last place (`formatPosition`), I as
`I/Imax × 100` over the strongest *measured* line (`formatIntensity`, `—` under
`no_intensity`/`fit_failed`), and an esd from 1° up is not printed — wider than
any peak, it is a flat direction, and the row's flag says why. **An esd that has
swallowed its value is not a precision** (`esdSwallowsValue`: ≥ 1 and larger
than the value): `formatValue` then shows the value at its own precision and
`formatEsd` writes `±110` beside it, where `35(111)` was printed for a 2θ with a
degenerate σ; `12346(56)` keeps the convention, and this holds for every caller.
**A chip's words are the corpus's**: `HelpEntry.label` is the short form, the
chip is a `<Help>` term saying `labelFor(corpus, key)`, and the popover restores
the name a label hid (`Name · position_at_bound`) — so `peak_flags` and
`peak_origins` carry a label on every entry, held by `test_help.py` to three
words and unique. And **a `td` that is not `display: table-cell` is not a cell**:
two adjacent flex/inline-flex `td`s are wrapped into *one* anonymous cell, so a
class shared with a flex label put the chips under the intensity in a column
headed by nothing — found in Chrome, invisible to jsdom, and why the intensity
column is `.rel` rather than the form's `.num`.

## Handover log

### 2026-08-27 — closed: the peak table reads like a peak table

A crystallographer who picks peaks now reads the table the way a PDF card
reads: intensities on a 0-100 relative scale with a dash where the fitter's
number is not a measurement, positions at four places with the uncertainty in
the last place, one column that is the person's own decision, and flags as
two-word labels whose meaning and code are one click away. It cost one
convention: wherever an uncertainty is larger than the value it qualifies, in
every table of this app, the parentheses are abandoned and the number is
written beside the value as ±. And it ruled out the triage's own threshold:
0.1° hid the uncertainty of a real line on the first pattern it met, and the
measured boundary is a degree, wider than any peak.

*Done.* `lib/peaks.ts` `intensityScale`/`formatIntensity` (I/Imax × 100 at
one decimal over the strongest *measured* line; `—` under `no_intensity` or
`fit_failed`, both names held to the corpus vocabulary) and `formatPosition`
(four places, esd in the last place below `POSITION_ESD_MAX_DEG` = 1°, `(0)`
under half a unit). `lib/table.ts` `esdSwallowsValue` (esd ≥ 1 and larger
than the value): `formatValue` then shows the value at its esd-less precision
and `formatEsd` writes ` ±110` (2 s.f., exponential from 1e6) — Params, Model
and History inherit it. `rietx.help`: `HelpEntry.label`, thirteen flag
labels, the `peak_origins` arm keyed by `ObservedPeak.origin` both ways,
`test_help.py` holding the two chip arms to a label each (≤ 3 words, unique)
and every other arm to none; `help_keys.json` +4, `lib/help.ts` `ARMS` +1,
`labelFor(corpus, key)`, the glossary's seventh field and its arm table. The
popover shows `Name · <code>` only for a labelled entry. `Peaks.svelte`: seven
columns (`# · 2θ · d · I (rel) · flags · use · actions`), `App` passes
`corpus` down, the origin chip and the σ-assumed chip are corpus terms
(`peak_origins:<origin>`, `peak_diagnostics:PEAK_SIGMA_ASSUMED`), the
authored-title budget 12 → 10, the diagnostics strip folded into
`details.notes` whose summary carries the count as a chip toned by the
loudest level. `gui/CLAUDE.md` takes four rules (cap 733 → 753); root
CLAUDE.md's "`typical` is the only authored field" becomes `typical` and
`label`.

*Measured* (`[dev]` only — no jax, no torch — python 3.12.12, numba 0.67.0,
darwin/arm64; vitest under node):

- vitest **461 → 467 passed**, 21 files: +4 `peaks.test.ts` (the numbers, the
  vocabulary pin), +1 `table.test.ts` (the guard), +1 `help.test.ts`
  (`labelFor`); the App-level peaks-tab test was extended, not added.
  `svelte-check` 0 errors. Dist rebuilt, digest `be85b9b15f3f` (after the
  review's fixes), `test_gui_dist.py` 13 passed.
- Fast selection (`-m "not slow"`, `-n auto --dist loadgroup`, run once on
  the final tree before the docs-only close edits): **3138 passed / 117
  skipped**, 2:07. No same-machine baseline was run on `origin/main`; the
  diff against it adds exactly two `def test_` (both in `test_help.py`) and
  removes none, and no skip is new. `ruff` clean; `sphinx -W` clean;
  `test_manual_api.py` 13 passed; `test_gui_peaks.py` 9 passed.
- The full suite did not run: nothing here moves a measured number (a GUI
  table, a corpus field, a display threshold).
- Browser, Chrome for Testing 1223 at 1400 × 900, a project built from
  `tests/data/qarr/corundum.prn` through the `corundum` compare standard
  (there is no corundum *example* — the `qarr` data fence, WP-1204): 62
  lines picked, 52 usable, 47 flag chips; 2θ esds 51 under 0.01°, 8 in
  [0.01, 0.1), one real asymmetric line at 0.1048°, two degenerate at
  3.7e17° and 3.9e49° (intensities 5.5e-19 and 2.1e-49); widest FWHM 0.348°.
  Table 511 px wide in a 531 px panel, no horizontal scroll, both themes.
  The popover on `not separable` reads its sentence and `Name not_separable`.

*Gotchas.*

- **A `td` that is not `display: table-cell` is not a cell.** The intensity
  cell first wore `.num`, which this panel already uses for the search form's
  labels (`display: inline-flex`); the browser wrapped it and the flex
  `td.flags` beside it into one anonymous cell — chips under the number, in a
  column headed by nothing, numbers in the form's muted grey. jsdom cannot
  see it; the class is `.rel` now. `td.flags` and `td.acts` are still flex
  and survive only because each has a real cell on both sides.
- The 0.1° threshold was wrong by measurement, not by argument: row 43
  (σ = 0.1048°, flag `asymmetric`) printed bare beside row 48's `(875)`. At 1°
  it prints `(1048)`, which reads oddly and is true.
- The count chip sits *inside* the `<summary>` — the chip is the fact and the
  summary acts, which is 1201's rule read narrowly; if a reviewer reads it as a
  chip that acts, the count goes to plain text with the tone on the summary.
- The `.rxt` peaks block still writes the raw area (`%.6g`, so `2.1e-49`): it
  is the data view and its `I` column is not editable. Left alone.
- The four 409s in the console at boot are the shell's `GET /api/report`,
  `/api/result`, `/api/index/result`, `/api/index/extinction` on a project
  with no fit; the 404 is unrelated. Neither is this panel's.
- Two things the session's tooling refused and the workaround: a heredoc
  script and a `for` loop over `curl` are "too complex" for the worktree gate
  — write the script to the scratchpad and run it by path; `cd gui &&` is
  refused by the no-top-level-cd hook — `(cd gui && npx vitest run …)`.

*Reviewed.* `/code-review medium --fix` ran **after** the PR was opened, not
before it: this session was served the pre-#158 handover checklist from the
stale main checkout (skills load from the launch directory, and that
checkout was four merges behind `origin/main`), so the step was missed and
run late, still ahead of the tree that merges. Eight findings. Six fixed and
committed, each edge pinned by a test: the popover's `Name` row only where
the label *differs* from the name (`excluded` labelled `excluded` hid
nothing); `formatEsd` rounds to two figures before choosing the exponential
form (999 999 printed seven digits); `formatPosition` treats an esd that
rounds up to 10 000 units of the fourth place as over the gate; the panel
comment quoted 0.1° after the constant moved; the `label` docstring said
"no code reads it" while `labelFor` and `helpCode` do, and its `None`
sentence contradicted the test; the glossary never rendered a label (it
prints `Chip \`at bound\`` now, 13 of them). Two declined: the count chip
inside the notes' `<summary>` (the gotcha above stands — the chip is the
fact, the summary acts); and `INTENSITY_UNMEASURED_FLAGS` as a TypeScript
literal, where `gui/CLAUDE.md`'s rule wants a server-served set beside
`unusable_flags` — a schema-and-wire change, filed into 1213's `### Inherited`
for the next consumer of `formatIntensity` rather than widened into this PR.

Next, in order: **WP-1210** (the peak layer), which inherits the
`peak_origins` labels for telling a placed line from a fitted one and the
`td` trap; **WP-1211** owes the Peaks panel's remaining ten authored titles,
nine of them the candidate table's; **WP-1213** should read a hovered line
through `formatPosition`, not the plot's whisker. Nothing in this WP is left
open.

- **2026-08-25** — created from the v1.2 triage.
