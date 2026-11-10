# WP-2210 — fit statistics in the action bar

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — claimed by a ghostshift runner
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
- [ ] The GUI chapters say where the statistics are in each layout; the dist rebuilt;
  screenshots beside the prototype's at the same window size for the PR.
- [ ] Skill: none. The agent skill drives the python API, and no route changes.

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

- **2026-11-10** — filed by a ghostshift runner. No open WP owned the work: the milestone's
  "Designed, not yet filed" table listed it as "Fit statistics in the action bar", and
  WP-2123's handover left it to the maintainer's ruling rather than to its own checklist. Numbered from the milestone's 22xx block, as
  the shift lead assigned. Next: start the checklist.
