# The GUI style guide

This guide states how `rietx gui` looks and behaves, and why.
Read it before you change how anything in the GUI looks or responds.
It holds rules and their motives.
The values are in code: colours in `src/rietx/viz/theme.py`, generated into `gui/src/tokens.css`, and sizes, spacing and component drawings in `gui/src/app.css`.
The guide names those tokens and never restates a value.
Where the code still holds the first GUI's value, the rule gives the target and the milestone piece that moves it (`docs/milestones/gui-overhaul.md`).

The design was worked out in twelve rounds of prototypes that the maintainer reviewed on screen, 6 to 8 November 2026.
The prototype is a mockup, so many elements in it are unfinished.
Complete an unfinished element by the rule for its kind.
Where no rule covers it, follow the principles below in order.
Where two rules disagree, or a rule is unclear, ask the maintainer before you build: visual questions go to the maintainer first.

## How to read the markers

Each rule ends with a marker in brackets.

- `[Yue 2026-11-07]` means the maintainer stated the rule or its motive on that date.
- `[inferred]` means Claude inferred the motive from the rulings, the site and common practice. A WP number after it names the first GUI's work the rule comes from. The maintainer approved this way of writing the guide on 2026-11-09 and reads it once.
- `[open Bn]` means the rule waits on item Bn in its WP's § Questions to the maintainer.
- `provisional` after a date means the maintainer chose the rule for now, and a later review may revisit it.

## Principles

1. The website and the manual are the reference for the visual language. [Yue 2026-11-06]
2. Show less. The maintainer disliked the first GUI's information overload, its dense rows, its boxes and chips with no clear purpose, and controls whose purpose was unclear. [Yue 2026-11-06]
3. A style element communicates one thing, and that thing is the same throughout the interface. Size, padding and radius belong to a register (a named kind of control or label, with one drawing), never to the place it is used. [Yue, WP-1201]
4. No click moves the layout unless it asks to. Expanding, collapsing, switching a tab and jumping ask. Editing a value, ticking a box, holding a term, choosing a type and dragging a slider do not. [Yue 2026-11-07]
5. No permanent explanatory text. Lines such as "Read it top to bottom" read as AI prose. Explanations live in tooltips, the help popover and each panel's ? box. [Yue 2026-11-07, repeated 2026-11-08]
6. What a screen shows follows the crystallographer's conventions: one atom per row, typeset space groups, rietx's own plot conventions. [Yue 2026-11-06, 2026-11-07]
7. How a screen behaves follows common software practice where diffraction has none: autosave, undo, Esc, context menus, panel toggles, recovery copies. [Yue 2026-11-09, on drafts; inferred as a general rule]
8. Every choice ships a default that suits most phases. A setting most users would change means the default is wrong. [Yue, WP-1462]
9. Where the prototype and a rule disagree, the rule wins. The prototype is a mockup of the real thing. [Yue 2026-11-09]

## Colour

The default theme is the site's palette: warm neutrals, an orange accent, an orange calculated curve and a grey difference curve.
Each chrome token takes the site's value for the same job. [Yue 2026-11-06, 2026-11-09; WP-2200]
Other established themes (Solarized light and dark, Monokai and others) come later, as further palettes in `theme.py`. [Yue 2026-11-06, 2026-11-09]

- Settings offers the theme as three choices: Match system, Light and Dark. Match system is the default. Light and dark are built first. Named themes such as Solarized come later, and Settings lists them after the three. [Yue 2026-11-09]
- A colour is chosen by its job, never by its look. [Yue 2026-11-06, adopting the site's rule]
- The chrome tokens are `--fg`, `--bg`, `--panel`, `--hover`, `--line`, `--line-strong`, `--muted`, `--accent`, `--accent-ink`, `--ok`, `--warn` and `--bad`. A page's extra role (a focus ring, a sunken track, a tinted cell) is a `color-mix` over them. A site role enters as a token only when a register reads it and no mix gives it, as the accent's text role, the control border and the hover ground did. [inferred, WP-1429, WP-2200]
- The accent marks things and sets no running words. It marks the current tab's underline, the focus ring, a ticked box's tick, a selection on a plot, and the calculated curve. Text that the accent would colour, such as a link, takes the accent's text role, `--accent-ink`. [Yue 2026-11-06 for the curve; inferred, from the site, for the rest]
- The state colours (`--ok`, `--warn`, `--bad`) mean states and nothing else. A warning is ochre, so it never reads as the brand. An info state joins them when a panel first needs one. [inferred, from the site]
- No number is judged by colour. Rwp and GoF are plain numbers, and no row turns green because a value moved. [inferred, WP-1217]
- Every text colour clears 4.5:1 against each ground it sits on, and the accent clears 3:1 as a mark. `tests/test_gui_palette.py` measures each pair. [inferred, from the site]
- A plot mark takes a `--plot-*` token of its own, and every plot colour stays at least the floor in `tests/test_gui_palette.py` from every other one. The pairs under it are named there with their measured distance and may only improve. The dashed background is one of them, since its dash carries what its colour cannot. [inferred, WP-1210, WP-2200]
- Phases take `--phase-0` onwards in order, with the most legible first. A single phase's ticks are neutral ink. [inferred, WP-1029]
- `rietx watch` and `rietx compare` read the same `theme.py`, so they change colour with the GUI. Their layout is outside this guide. [inferred, WP-1429]

## Type

- Words are set in Instrument Sans. Greek letters come from IBM Plex Sans, because Instrument Sans has none. Numbers and code are set in IBM Plex Mono. [Yue 2026-11-06]
- Numbers are mono so digits line up and a changing value never shifts the text around it. [inferred]
- Space-group symbols are typeset in a serif face, with italics, subscripts and overbars, and take no comma. [Yue 2026-11-06, 2026-11-07]
- Identifiers that are words, such as Wyckoff letters, use the text face. [Yue 2026-11-07]
- Every font is served by the app itself. No built file names a remote host, which `tests/test_gui_dist.py` checks. [inferred, WP-1010]
- A type size is a role. Each step names what it sets (prose and controls, secondary text, headings), and steps scale with density once the Settings dialog piece adds it. `gui/src/lib/style.test.ts` fails a size that is not a step. [Yue, WP-1201, for the principle; inferred for the roles]
- Headings are sentence case app-wide, with weight setting them apart. No heading, column head or label is uppercase or tracked. Today's `h2, h3` rule in `app.css` is uppercase, and the sentence-case piece moves it. [Yue 2026-11-06, 2026-11-09; inferred for column heads]
- A selected item never changes weight. A bolder word is wider, so it re-wraps its line and moves what is under it. Today's `.tab.on` sets a heavier weight, and the piece that next touches tabs drops it. [inferred, from principle 4 and the site]
- Held rows fold into one line in the crystallographer's notation, such as `a = b = c, α = β = γ = 90°`, built from the symmetry. Only rows that cannot be freed fold. [Yue 2026-11-06]

## Spacing and density

- Density has three stops: reading, default and compact. The default sits between the other two. Row height, bar heights and type size move together, and Settings offers the choice. [Yue 2026-11-06]
- Until the Settings dialog piece adds density tokens, spacing uses `--s1`, `--s2` and `--s3`, and every control's padding is two of them. [inferred, WP-1201]
- Bars earn their height. No bar is empty and no bar is crowded. The graph title shares a row with the view's controls, and the action bar is one row. [Yue 2026-11-07]
- Space separates groups. A gap sits above each group and each table. Rows inside a section carry no rules, and a rule sits above a group or a table. [Yue 2026-11-07]
- A family of parameters for one effect is a group, and a single parameter is a row. Groups follow the refinement order. [Yue 2026-11-07]
- Labels share one left edge. Disclosure chevrons hang in a gutter, so group names and labels align and children indent once. [Yue 2026-11-07]
- Every scalar value box in a panel has one width, so units form one column. A box is wide enough for every value it can hold. [Yue 2026-11-07, 2026-11-08]
- A checkbox keeps clear space from the column on its left. [Yue 2026-11-07]

## Components

The drawings live in `gui/src/app.css`. Each kind below means one thing (principle 3).

| Kind | Means | How it is drawn | Source |
|---|---|---|---|
| Primary button | The one action of a view (Apply and refine, Create) | Filled in the accent's text role (`--accent-ink`), inked in `--panel`. One per view | [Yue 2026-11-06] |
| Button | Any other action | Outlined in the strong rule (`--line-strong`) with ink text, the hover ground (`--hover`) on hover | [Yue 2026-11-06] |
| Icon button | An action whose icon is familiar | No border at rest, a border on hover. A word beside it where the icon is unfamiliar | [inferred] |
| Segmented choice | One of N views or modes | A sunken track with one raised option, so a choice never looks like an action (`.segmented`) | [Yue 2026-11-07] |
| Tab | One of N panels | A word over a rule. The current word is ink over an accent underline | [inferred, from the site] |
| Checkbox | A parameter refines | A pale accent tint with an accent tick. It sits by the parameter it controls, never by a follower | [Yue 2026-11-07] |
| Padlock | A parameter is held | A cell with a checkbox cell's geometry, so locking moves no number. No column heading | [Yue 2026-11-07] |
| Editable value | A number you can change | A tinted cell, the whole cell the target. Its editor floats over the cell and shows the whole number | [Yue 2026-11-07] |
| Dialog field | A value typed into a form | A bordered box, because it is a control. The label column fits the longest label | [inferred; Yue 2026-11-08 on the overlapping label] |
| Link | Go somewhere | The accent's text role (`--accent-ink`), underlined where it sits in running text | [inferred, from the site] |
| Help term | An explanation is one click away | The help cursor and no other mark. A click opens the term's `rietx.help` entry | [inferred, WP-1203] |
| Fact | A grade, a flag, a state | Words, in a state colour where the tone is a judgement, with no border. A bordered box is a control, so `.chip` and `.pill` go as their panels are redrawn | [inferred, from principle 2 and the site] |

- A tooltip says what a click does, as a verb phrase. It appears after a short hover and at once on keyboard focus, with any shortcut on a second line. [inferred]
- A menu takes no heading that restates the button that opened it. Submenus open on hover, click or the arrow key. A menu of checkboxes stays open while you tick. [Yue 2026-11-07, 2026-11-08]
- Floating layers (popovers, menus, editors, dialogs) share one drawing: the panel ground, a hairline and one shadow. A shadow means "floats above the page", so nothing in the page's flow takes one, except the raised segmented option. [inferred]
- Settings and New project are modal dialogs. New project is one dialog with no steps. [inferred]
- A disclosure stays open when something else is clicked, and keeps its state when the panel redraws. A section never folds itself. [Yue 2026-11-06, 2026-11-08]
- Every control shows the accent focus ring on keyboard focus. [inferred, from the site]
- Hover styles apply only where the device hovers, because a touch screen keeps the hover on the last thing tapped. [inferred, from the site]
- Motion is limited to a short fade or turn on a disclosure or tooltip, and none under a reduced-motion setting. [inferred, from the site]
- Icons are one stroked SVG set in the site's stroke. Each is even and fits its box. A glyph appears only as text, such as ⌘ in a shortcut. [Yue 2026-11-08 on the cog; inferred for the set]

## Layout and panels

- Graphs sit on the left in tabs: Pattern, Peaks, Background and Structure. The model sits on the right in tabs: Parameters, Interactive, Plan and Text. The right-hand tabs switch mode, and two modes never show together. [Yue 2026-11-07]
- The top bar holds, left to right, the graphs toggle, the workflow menu, the project name (which opens the File menu), Settings and the model toggle. The status bar holds the console toggle at its left. The bars never change, so no toggle moves. [Yue 2026-11-07 on the shape; inferred for the fixed bars]
- Both side panels collapse, each from a button on its own side that never moves. Graphs and model cannot both be hidden. [Yue 2026-11-07]
- The panels resize as in VS Code. The atom table is fully visible by default. [Yue 2026-11-07]
- Below a width computed from the panels' minimums, the window is one column, graphs above the model. The page never scrolls sideways. [Yue 2026-11-07]
- The graphs carry a title saying what they show, so a preview never reads as a changed fit. [Yue 2026-11-07]
- The graph title gives way before the view's controls do: it shrinks with an ellipsis and shows the whole text on hover. No control wraps while the title can still shrink. This departs from the first GUI's rule that overflow wraps and never truncates. [Yue 2026-11-09]
- The action bar holds Revert, Apply, the one-cycle or staged-plan choice, and Apply and refine. While the graphs are hidden it also carries Rwp and GoF beside Refine. [Yue 2026-11-07; Yue 2026-11-09, "try B"]
- The bottom panel holds Console (the Python the window runs) and History (with Compare and Restore). The status bar toggles it, and it starts hidden. [Yue 2026-11-07 for both views; inferred for one shared panel]
- Workflows (peaks and indexing, series, structure solution, rigid bodies) are entries in the workflow menu, never tabs. A workflow keeps the window and shows its steps across the model panel. [Yue 2026-11-07]
- An element of the first GUI (tooltips and manual links, hkl highlighting, the history panel) comes over one at a time, each checked with the maintainer. [Yue 2026-11-07]

## Interaction

Claude inferred rules 1 to 12 from the rulings on background points and peak picking, and the maintainer adopted them on 2026-11-08.

1. Objects placed on a plot share one grammar. Click empty space to add one, click one to select it, drag to move it. Delete removes the selection, and Option-click removes one at once. [Yue 2026-11-08]
2. Esc backs out of the gesture in progress. During a drag it puts the object back, and the dragged mark follows the pointer until then. Right after a drag, while the object is still selected, the first Esc takes the move back. Otherwise Esc clears the selection. [Yue 2026-11-08]
3. Where people place many objects in a row (peaks, background points), a click places one and nothing opens. Where they place one object and then set it up, the new object is selected. An object's bar of actions opens when you select it and closes on ×, Esc or a click elsewhere. [Yue 2026-11-08]
4. The plot shows what takes part, and the list holds everything. An object left out leaves the plot and stays in the list as a greyed row whose tickbox brings it back. A left-out region, such as an excluded 2θ range, stays on the plot as shading, because its position is the information. [Yue 2026-11-08]
5. The list and the plot point at the same thing. A row click frames its object on the plot, with a dotted line where the object has no mark. A click on a mark brings its row into view. [Yue 2026-11-08]
6. Navigation uses the common gestures. Drag a box to zoom, double-click to show everything, scroll sideways to pan. Double-click does nothing else. [Yue 2026-11-08]
7. A control never covers what it is about. The view leaves room above the data for marks and the selection bar. [Yue 2026-11-08]
8. No click moves the layout unless it asks to (principle 4). [Yue 2026-11-08]
9. Hover previews the click. A dashed outline shows where a click would place something, and a mark shows the danger colour while Option is held over it. [Yue 2026-11-08]
10. Every edit can be undone. [Yue 2026-11-08]
11. Ask when the program cannot tell which of several things you mean, and offer the candidates. An action aimed at one object happens at once. An action that reaches past what you pointed at warns first, unless undo can bring the work back. [Yue 2026-11-08]
12. Right-click opens a context menu holding the object's bar actions, and Delete there acts at once. This replaces the first GUI's right-click that removed a peak. [Yue 2026-11-08]

- Modifier keys keep one meaning each: Option removes, Shift extends a range, and ⌘ (Ctrl elsewhere) adds to a selection. [inferred, from the rounds on selection and peaks]
- Selecting several values and typing one number sets them all. A selection of differing values reads "Mixed". [Yue 2026-11-07 asked for it; inferred for the word]
- Work saves itself, and there is no Save command. ⌘S answers with a short "Saved". [Yue 2026-11-07]
- An edit is pending until Apply. Pending edits survive a close or a crash in a recovery copy kept in rietx's state directory, apart from the project, as editors such as VS Code keep theirs. [Yue 2026-11-09]
- A preview keeps the last fit's scale, so the comparison never moves. [Yue 2026-11-07]
- A window on a plot, such as an averaging width, is set by dragging it on the plot, with a typed field kept in step. [Yue 2026-11-08]
- A slider keeps one number format while you drag it, and clicking its number opens it for typing. Its range and units live in a pop-up opened from the parameter's name, and a slider may have a non-linear scale. [Yue 2026-11-07]
- A value may be a typed expression. Typing "=" shows a visible formula mode with a list of names, and the value's popover has an "=" button that opens it. [Yue 2026-11-08]
- A value near one of its limits shows it by text colour and a small mark on the limit's side, wherever the value appears. [Yue 2026-11-08]
- `tests/test_gui_layout_browser.py` checks principle 4. It clicks every control and compares element boxes before and after. A check clicks as a person does, through real pointer events, because a scripted click can reach a control a person cannot. [Yue 2026-11-07; inferred for the method]

## Numbers and words on screen

- Numbers are aligned on the decimal point. A number from 0.01 up to below 10 000 is written plain, and one outside that range in scientific notation. Atom-table numbers are always plain. [Yue 2026-11-07 for scientific by default; Yue 2026-11-09 for the range]
- Switching a number between plain and scientific moves nothing. Each number slot reserves room for an exponent, and the slots come from the last fit, never from an edit. [Yue 2026-11-07; inferred for the slots]
- Units follow the value, on the number side, in one column. Sliders are the exception: their units live in the range pop-up. [Yue 2026-11-07]
- Groups such as cell parameters align on the decimal point. [Yue 2026-11-06]
- No caption or readout restates what the plot shows. [Yue 2026-11-07]
- Labels are few and plain, in sentence case, and use the field's term: "user variables" for the values a person defines. [Yue 2026-11-08 for the name; inferred for the rest]
- A placeholder is a word, such as `default`, never a plausible number. [inferred, WP-1206]
- No tab label is shortened. [inferred, WP-1034]
- What a name means is a `rietx.help` entry, and a short label comes from that entry's label field. [inferred, WP-1203, WP-1209]
- Text in prose takes the minus sign −, and a number a person may copy takes the hyphen-minus -. [inferred, WP-1213]
- Any sentence the GUI shows (help, empty states, error text) is written under the house documentation style, in British spelling. [inferred, WP-1201]

## Plots

- The pattern follows rietx's plot conventions in the GUI's colours. Observed points are crosses, sized by how densely they sit, and always clearly visible. The calculated curve is a solid line. The difference sits below on its own axis, in esd, over a band of ±3 esd. Reflection ticks are lenses in their own band at the foot, one row per phase, and never on the difference axis. [Yue 2026-11-07; inferred, WP-1032, for the band]
- Every curve and the data can be hidden and shown. Their labels sit in a right-hand gutter and act as the switches. A hidden curve is not remembered, so a curve a later build adds arrives drawn. [Yue 2026-11-07; inferred, WP-1032]
- A preview is drawn in the accent, and the last fit turns grey only while a preview exists. [inferred]
- No gridlines, no title inside the plot, no shadow. [Yue 2026-11-07, adopting rietx's plot conventions]
- Every curve and mark stays inside the plot area at any zoom. Nothing is drawn into the axis margins. [inferred, WP-2200]
- A legend puts its symbols in one column on the left, with the labels aligned after them. A colour key goes in empty space inside the plot, never in a margin of its own. [Yue 2026-11-08]
- The hover readout is a strip under the plot, never a box that follows the pointer. [inferred, WP-1213]
- Shading for an excluded region spans every pane and stops at the measured range. [inferred, WP-1033]
- Peak marks are lenses that echo the reflection ticks, larger and higher above the peak. A used peak's mark is filled and an unused one has no mark on the pattern. They are blue, the complement of the orange fits, and the picked peaks' fitted curve is a second tone of that blue, because it shares the pane with the calculated curve. [Yue 2026-11-08; Yue 2026-11-09 on the colour; inferred, WP-1210, for the fitted curve]
- A selected mark is drawn larger, with a ring in the text ink (`--fg`). Red, the danger colour, marks only a peak no line explains, and it is the layer's only state colour. Orange stays the fit's alone. [Yue 2026-11-09, provisional]
- A colour scale is perceptually uniform, and a residual map uses a diverging scale centred on zero. [inferred]
- The 3D structure follows crystallography's drawing: its projection, cell edges, bonds and ellipsoids. The cell frame takes the accent, because a hairline vanishes in a scene. [inferred, WP-1015, WP-1462]
- A drawn colour is checked on the rendered result, because a chart can paint something other than the option it was handed. [inferred]

## Checks

These tests hold the rules a machine can check cheaply. A new rule that a machine can check gets a test here.

- `tests/test_gui_palette.py`: the token values and the generated `gui/src/tokens.css`, the plot palette's floor, every text colour's contrast on its grounds, and the ink on the primary fill.
- `tests/test_gui_layout_browser.py`: no click moves the layout, collapse buttons stay where they were, and a phone-width window never scrolls sideways.
- `gui/src/lib/style.test.ts`: no panel sets a register's size, padding or radius, and no size falls outside the steps.
- `tests/test_gui_dist.py`: no built file names a remote host, so every font is the app's own.
- `tests/test_gui_style_guide.py`: this guide names only tokens and tests that exist, carries a marker on every rule, and restates no colour or pixel value.

Where the prototype drew a panel fully, the PR that ports it puts its screenshot beside the prototype's at the same window size. That comparison is for review, not a pixel test (`docs/milestones/gui-overhaul.md` § Acceptance).
