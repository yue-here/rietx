# WP-2210 — fit statistics in the action bar

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — built; PR #1518 waits for the maintainer's look and three visual questions
Depends on: 2123
Priority: P3 2026-11-10 — a view over what the fit already knows: with the graphs hidden, reopening them shows the numbers

## Goal

While the graphs are hidden, the action bar shows the fit's Rwp and GoF, and the
"not a fit yet" judgement, beside Refine. While the graphs show, the statistics stay on the
graph title line, where WP-2123 put them. One home per layout, and a statistic appearing
moves nothing.

## Context

### Where the statistics are today

WP-2123 (the layout shell, merged as PR #1476) moved Rwp, GoF and the `⚠ not a fit yet`
chip from the header to the graph title line (`gui/src/App.svelte`, `.gtitle .stats`; its
settled call 2). The title line is part of the graph column, so hiding the graphs hides the
three with it. A person who hides the graphs to see the whole atom table can press Refine
and cannot see whether Rwp improved. WP-2123's handover left this as its item (6), a visual
call with no ruling behind it: back in the header while the graphs are hidden, or in the
action bar beside Refine.

The numbers come from two `$derived` values in `App.svelte`, `rwp` and `gof`: the result's
statistics, or the run frame's only while a run is in flight (WP-1034's rule that a
statistic outlives the thing it describes). The judgement is `result.maturity`, the
report's own gate (`MATURITY_MAX_RWP`), quoted and never re-derived (WP-1029 item c). Its
message is reached through `<Help>` (WP-1203).

The action bar is `gui/src/panels/ActionBar.svelte`: the refine choice, then a group held to
the right holding the pending slot, Revert, Apply and the filled Refine. It ends the model
panel, and moves to the foot of the graph column while the model panel is hidden (WP-2123's
settled call 12). Every width in it is reserved, so where the row breaks depends on the
panel's width alone and never on a click.

### The ruling

On 2026-11-09 the maintainer ruled on six briefs. Brief 5 asked where Rwp, GoF and the
"not a fit yet" chip go while the graph column is collapsed, with four options: (A) back in
the header while the graphs are hidden; (B) in the action bar beside Refine while the graphs
are hidden; (C) always in the action bar, off the title line; (D) nothing. The brief
recommended B on the ground that the header is ruled a bar whose contents never change,
while the action bar already moves on a collapse click; B also puts the number next to the
button that changes it. The ruling: "Rwp/GoF/chip with the graphs hidden: try the action bar
beside Refine (B)." `gui/STYLE.md` § Layout and panels records it: "While the graphs are
hidden it also carries Rwp and GoF beside Refine. [Yue 2026-11-09, "try B"]". The word "try"
makes the merge wait on the maintainer's look (milestone acceptance row 10).

The prototypes never drew this: the prototype's title line carries the fit's Rwp, and
nothing shows it with the graphs hidden. So the piece is built from the guide's rules, and
each visual choice no rule settles is listed in the handover for the maintainer.

### Rules from `gui/STYLE.md` that bind the build

- Principle 4: no click moves the layout unless it asks to. A collapse click asks, so the
  statistics appearing in the bar on that click is allowed. A fit finishing does not ask,
  so the numbers and the judgement appearing after a run must move nothing: the slot is
  reserved at its widest, as WP-2123 reserved the pending slot.
- Components, "Fact": a grade, a flag or a state is words, in a state colour where the tone
  is a judgement, with no border; `.chip` goes as its panel is redrawn. So "not a fit yet"
  is words in `--bad`, drawn the same way in both homes (principle 3).
- Colour: no number is judged by colour; Rwp and GoF are plain numbers.
- Components: a glyph appears only as text, such as ⌘ in a shortcut, so the `⚠` goes.
- Numbers: plain from 0.01 to below 10 000. Rwp and GoF keep the title line's three
  decimals.
- A placeholder is a word, never a plausible number.

### Tier

No rule here is a heuristic in the sense of `docs/milestones/generality.md` § The rule:
nothing reads the data or decides for a fit. The judgement shown is the report's
`maturity`, quoted.

### Calls settled by Claude

Each is reversible and waits for the maintainer's look at the PR.

1. Settled by Claude, reversible, **open visual question 1**: the statistics sit right of
   Refine, as the bar's last group, so the number is next to the button that changes it.
   No ruling or prototype settles the side. Alternatives: between Apply and Refine (splits
   the two related buttons), or left of the pending slot (keeps the buttons at the bar's
   right end, three slots from Refine).
2. Settled by Claude, reversible, **open visual question 2**: before any fit the bar reads
   `Rwp — GoF —`, so the labels stand still and only the numbers arrive. The dash is the
   prototype's history table's mark for an absent Rwp, and `gui/STYLE.md` asks for a word or
   mark, never a plausible number. Alternative: an empty reserved slot, as the pending
   count's is.
3. Settled on `gui/STYLE.md` § Components ("Fact": words, in a state colour, with no
   border; `.chip` goes as its panel is redrawn), § Colour (no number is judged by colour)
   and § Components (a glyph only as text): the judgement reads `not a fit yet` in `--bad`
   with no border and no `⚠`, in both homes, and the Rwp beside it is no longer turned
   `--warn`. Alternative: keep the chip on the title line and words in the bar, which draws
   one fact two ways (principle 3).
4. Settled on `gui/STYLE.md` § Type (words in the text face, numbers mono): the labels
   `Rwp` and `GoF` are in the text face, the numbers mono. The title line had set both mono.
5. Settled by Claude, reversible: in the bar each number has a slot as wide as its widest
   plain value (`9999.999%`, `9999.999`), and the judgement's words keep their room
   invisibly while the fit is mature, so a fit finishing moves nothing (principle 4, and
   WP-2123's reserved pending slot). The title line reserves nothing, because its statistics
   are held right and a slot there only added a gap. Cost: about 13 characters of blank
   room at the bar's right end while the fit is mature.
6. Settled by Claude, reversible: the bar quotes the fit alone, never a preview's Rwp, since
   the title line is what tells a preview from a fit (§ Layout and panels). With the graphs
   hidden, a slider preview therefore shows no Rwp anywhere. Alternative: the preview's Rwp
   in the bar, labelled as a preview.

## Non-goals

- The header. It is ruled a bar whose contents never change.
- A preview's Rwp in the bar. The title line is what tells a preview from a fit (STYLE
  § Layout and panels), so the bar quotes the fit alone.
- The status bar and the bottom panel, designed but not filed.
- No new route.

## Tasks

- [x] One component draws the fit's statistics (`panels/FitStats.svelte`): Rwp, GoF and the
  report's judgement as words in `--bad`, its message one click away through `<Help>`. The
  title line uses it while the graphs show.
- [x] The action bar carries it beside Refine while the graphs are hidden, in a slot
  reserved at its widest content, so a fit finishing moves nothing.
- [x] Vitest: the bar shows the statistics only while the graphs are hidden, and the
  judgement is words, not a chip. Browser: the slot holds its longest content, a refine with
  the graphs hidden moves nothing, and the shell sweep runs with the graphs hidden too.
- [x] The GUI chapters say where the statistics are in each layout; the dist rebuilt;
  screenshots beside the prototype's at the same window size for the PR.
- [x] Skill: none. The agent skill drives the python API, and no route changes.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_peaks_browser.py tests/test_watch_browser.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The layout-shift test reports no unasked-for movement with the graphs hidden, including
through a refine, and the maintainer has looked at the bar on screen (milestone acceptance
row 10).

## References

- The maintainer's ruling of 2026-11-09 on brief 5, restated above.
- `gui/STYLE.md` § Layout and panels, § Components, § Colour.
- WP-2123's settled calls 2 and 12 and its handover item (6).

## Handover log

### 2026-11-10 — built; PR #1518 waits for the maintainer's look

With the graphs hidden, the action bar now carries the fit's Rwp, GoF and the report's
"not a fit yet" judgement right of Refine. With the graphs shown they stay on the graph
title line. So a person who hides the graphs to read the atom table still sees what a
refine did, and nothing on screen moves when a fit finishes. The judgement is now plain
words in the danger colour in both places, where it was a bordered chip with a warning
glyph. Two visual choices no rule settles wait for the maintainer, with screenshots (see
*Open visual questions*).

*Done*: `gui/src/panels/FitStats.svelte` draws the three for both homes;
`panels/ActionBar.svelte` takes it as a `stats` snippet and renders it as a third group
after the one Refine ends; `App.svelte` hands it in only while the graphs are hidden and
uses it on the title line, with `maturityMessage` derived once. The manual's GUI guide (the
header note and the action-bar table) and the quickstart say where the statistics are in
each layout. Dist rebuilt. Settled calls 1-6 above.

*Measured* (macOS arm64, worktree venv `[dev]` plus playwright 1.64.1, node 24.22.1):
vitest 719 passed (+2: the bar carries the statistics only while the graphs are hidden;
its slots are filled before a fit and while mature); svelte-check 0 errors. Every
`tests/*_browser.py` run locally, 155 passed: layout + gui 35, peaks + watch + compare 61,
html + rxplot + structure3d 59. The layout file went from 28 to 31 cases (+3: the shell
sweep from a graphs-hidden start, the slots against their widest values, a refine with the
graphs hidden). Fast suite on main merged in, queued alone through serial.py: 14622 passed, 410 skipped, 32 xfailed, 0 failed (playwright installed, so the browser files ran in it rather than skipping; the two added tests cost 2.77 s there, and the new graphs-hidden sweep case is a parameter of an existing test).
ruff clean. `python -m tests.reader_output` exit 0, unchanged against the merge-base.
With the graphs hidden the bar is one row down to an 810 px window; at 760 px it is two
rows and at 420 px three, with no sideways scroll at either. Before a synthetic project's
first fit, one cycle with nothing ticked puts Rwp at 1067 %, which is why the Rwp slot
holds four integer digits.

*Review* (`/code-review high --fix`): four fixes landed (the message derived once, a stale
markup comment, the quickstart's hopeless-fit note naming the bar, the browser test picking
each slot's widest value by class). The refine test now also asserts the judgement's words
swap in. Declined: a number of 10 000 or more neither turns scientific nor fits its slot
(open visual question 3); a slider preview with the graphs hidden shows no Rwp (settled
call 6); the `<Help>` popover can outlive its term when a fit turns mature under it, which
the title line already did before this WP and which lives in the shared popover.

*Found, not fixed*: the header's run pill reads `idle` before a project's first run and its
status after, and the controls right of it are held right, so that first run moves
`Simple | Advanced`, the theme and Cancel 35 px left. It is WP-2123's header, which no
piece has redrawn, so `test_a_refine_with_the_graphs_hidden_moves_nothing` compares the
landmarks below the header and says why. The status bar piece, which may take the pill,
is the natural owner.

*Not done*: the manual's screenshots were not regenerated. The title line's labels moved
from mono to the text face and nothing else on them changed.

*Open visual questions for the maintainer* (screenshots at 1280 × 720 in
`~/.cache/ghostshift/rietx/wp-2210/shots/`, the prototype's beside rietx's: `prototype-hidden-light.png`
and `rietx-hidden-light.png`, dark twins, `rietx-bar-not-a-fit-light.png`,
`rietx-bar-before-fit-light.png`, `rietx-hidden-not-a-fit-420.png` and `-760.png`; the
prototype draws no statistics with the graphs hidden):
1. Where in the bar: right of Refine (built), between Apply and Refine, or left of the
   pending slot.
2. Before a fit: `Rwp — GoF —` (built) or an empty reserved slot.
3. A Rwp or GoF of 10 000 or more: scientific in a wider slot, or left as it is (it grows
   the slot, a case not seen outside an unfitted model).

Next: the maintainer looks at the bar on screen and answers the three questions; then the
PR merges. A follow-up for the header pill's 35 px goes to whichever piece redraws the
header or adds the status bar.

- **2026-11-10** — filed by a ghostshift runner. No open WP owned the work: the milestone's
  "Designed, not yet filed" table listed it as "Fit statistics in the action bar", and
  WP-2123's handover left it to the maintainer's ruling rather than to its own checklist. Numbered from the milestone's 22xx block, as
  the shift lead assigned. Next: start the checklist.
