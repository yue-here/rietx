# WP-2142 — The GUI style guide

Milestone: gui-overhaul · Status: ✅ 2026-11-10 — `gui/STYLE.md` merged in #1514, approved with B1-B4 ruled; moving the 36 visual rules into it is an owed item
Depends on: —

## Goal

`gui/STYLE.md` states, for each element of the GUI's look and behaviour, the rule, its motive,
and whether the maintainer stated the motive or Claude inferred it. A session completing a panel
the prototypes left unfinished can do it from the guide alone. The workshop's 59 open visual
questions are each settled or sent to the maintainer, and the milestone lists the pieces the
design rounds drew that no WP builds yet.

## Context

### The rulings this rests on

The maintainer ruled on 2026-11-09, on how the port is accepted:

> a consistent style that hews very close to the workshop version. This should be achieved by
> means of a relatively concise style guide ... and also the first instance of the gui. Please
> try to infer my intentions for any design elements, and if they are inconsistent or unclear,
> then bring them to me. the idea is not to burn lots of tokens copying but to understand the
> motivations behind why those design choices were made. there will be lots of incomplete
> elements in the workshop as it is a mockup of the real thing. it will need to be completed,
> and in a style consistent with the overall design.

"The first instance of the gui" is today's `rietx gui`. The same day the maintainer approved
three changes to how the guide works ("those changes are reasonable"):

1. **Values live in code.** Colour values are `src/rietx/viz/theme.py` tokens, and the shared
   component styles are in `gui/src/app.css`. The guide holds motives, names tokens and never
   restates a value. A rule a machine can check cheaply gets a test, named in the guide.
2. **Each motive is marked** as stated by the maintainer (with the ruling's date) or inferred
   by Claude. The maintainer reads the guide once.
3. **Screenshots side by side.** Where the prototype drew a panel fully, each later PR puts its
   screenshot beside the prototype's at the same window size. This is a review aid in the
   milestone's acceptance, not a pixel test.

The guide lives in its own file, read on demand by a session that changes how something looks,
and `gui/CLAUDE.md` gets one pointer line.

### The sources

The design was worked out in twelve rounds of prototypes, 2026-11-06 to 2026-11-08, in a private
folder nobody else can open. No repo file cites it; the guide restates each rule and its motive.
The sources were its visual-language draft (twelve interaction rules adopted by the maintainer on
2026-11-08, 22 principles quoted from the site, manual and figure rules, a token census and 59
open questions), its handover with every round's rulings, its four per-round decision records,
and the maintainer's rulings as kept in session memory. `gui/CLAUDE.md`'s 36 visual-style rules
(listed by WP-2134, PR #1511) are the first GUI's half.

### Known conflicts this WP resolves or sends on

- **The palette.** Ruled 2026-11-06: one default theme consistent with the site (warm neutrals,
  orange accent, orange calculated curve, grey difference curve), and established themes
  (Solarized, Monokai and others) through theme machinery. `theme.py` still holds the first
  GUI's blue and red. The site accent sits 0.072 OKLab from today's `--plot-calc` and 0.045 from
  `--warn`, under the plot palette's 0.13 floor, so the plot palette moves with the chrome. The
  guide states the target. The palette piece builds it.
- **Sentence-case headings app-wide** (ruled 2026-11-09). Today's `h2, h3` rule in `app.css` is
  uppercase; the guide states the target, and the change is a row of its own.
- **The peak-mark colour.** Okabe-Ito blue was chosen as the complement of orange fits, so it
  waits for the palette piece (ruled 2026-11-09).

### The tier of each rule this WP adds

None in the package. The guide states design rules for the GUI; the one test added checks that
the guide's named tokens and tests exist, which is a name check, not a heuristic.

## Non-goals

- No change to any colour, size or component. Each lands in the piece that builds it.
- `gui/CLAUDE.md` takes one pointer line and nothing else, because six open PRs edit it (#1511
  condenses it). Moving its 36 visual rules out is a follow-up once #1511 lands.
- The website, manual and figures keep their own rules; the workshop questions about them are
  out of this guide's scope and are recorded as such below.
- No WP is filed for the unfiled pieces; the milestone lists them.

## Tasks

- [x] Claimed: this file, the index row, a draft PR.
- [x] `gui/STYLE.md`: rule, motive and marker per element, with the tests that check them named.
- [x] `gui/CLAUDE.md`: the pointer line.
- [x] A test that every token and test the guide names exists.
- [x] The 59 questions, each settled or sent on, recorded below; the batch to the maintainer.
- [x] `docs/milestones/gui-overhaul.md`: the unfiled pieces and the screenshot acceptance row;
      ROADMAP's sentence on the peak-mark colour.
- [x] Skill: none. The skill is for an agent driving rietx; the guide governs changing the GUI.

## The workshop's 59 questions

The workshop's visual-language draft (2026-11-06) ended with 59 questions it settled none of.
Its handover said the list "still needs revising against the rulings". Each is placed below:
**ruling** means a later ruling answers it, **motive** means a stated motive or written rule
settles it (marked inferred in the guide), **scope** means it is about the website, manual or
figures and outside this guide, **B** means it went to the maintainer.

| Q | Question, in short | Placed | Answer |
|---|---|---|---|
| 1 | Does the GUI adopt the site's colour tokens? | ruling 2026-11-06 | Yes: one default theme consistent with the site. § Colour |
| 2 | Where do the values live? | ruling 2026-11-09 | `theme.py` tokens and `app.css`; the guide names them |
| 3 | Do `rietx watch` and `rietx compare` follow? | motive (WP-1429) | They read `theme.py`, so their colours follow; their layout is outside the milestone |
| 4 | Where does the guide live? | ruling 2026-11-09 | In rietx, in its own file: `gui/STYLE.md` |
| 5 | Does the accent survive the plots? | ruling 2026-11-06, 2026-11-09 | The curve palette moves with it: orange calculated, grey difference |
| 6 | Chips, given "a bordered box is a control"? | motive | A fact is words with no border; `.chip` goes as panels are redrawn |
| 7 | The same for `.pill` | motive; ruling 2026-11-09 (B) | Plain numbers; fit statistics sit in the action bar |
| 8 | Filled buttons? | ruling 2026-11-06 | One filled primary per view in the accent's text role |
| 9 | Does "one style element, one meaning" stand? | ruling (WP-1201) | Yes; the registers are redrawn, the style test stays |
| 10 | How many control kinds? | motive | The guide's components table, one meaning each |
| 11 | How is a selected item shown? | motive (no click moves layout) | Colour and a bar or underline, never weight |
| 12 | Uppercase small labels? | ruling 2026-11-09 | Sentence case app-wide; column heads inferred the same |
| 13 | Do links look like links? | motive (site) | The accent's text role, underlined in running text |
| 14 | Which radii? | motive (site is the reference) | The site's set, as values in `app.css` |
| 15 | Do state colours follow the site? | ruling 2026-11-06 | The site's four, info included |
| 16 | Two-state or three-state theme control? | B2 | Two written rules disagree |
| 17 | Where does a Tauri app store the theme? | motive (WP-1438) | `settings.json` in the state dir, the theme's one home |
| 18 | Does the header wrap? | B1 | A ruled bar design and a first-GUI rule disagree |
| 19 | Motion? | motive (site) | A short fade or turn on disclosures and tooltips; none under reduced motion |
| 20 | A focus ring on every control? | motive (site) | Yes, the accent ring on keyboard focus |
| 21 | Shadows? | motive | One shadow, for floating layers only |
| 22 | Density? | ruling 2026-11-06 | Three stops, default between reading and compact |
| 23 | When is a box allowed? | motive (site; ruling 2026-11-06 on boxes) | A box means a control or a floating layer |
| 24 | How is an affordance signalled? | motive | One signal per meaning, in the components table |
| 25 | How much shows by default? | ruling 2026-11-07 | Graph and model tabs, workflows as a menu, no permanent text |
| 26 | Fields, selects, checkboxes? | ruling 2026-11-07; motive for dialog fields | Tinted value cells, tint-and-tick boxes, bordered dialog fields |
| 27 | Editable numbers in a table? | ruling 2026-11-07 | Tinted cells, the whole cell the target |
| 28 | The table in the GUI? | ruling 2026-11-07 | Density-scaled rows, no inner rules, aligned decimals, one unit column |
| 29 | Which faces? | ruling 2026-11-06 | Instrument Sans, Plex Mono, self-hosted |
| 30 | Greek? | ruling 2026-11-06 | From IBM Plex Sans |
| 31 | When is mono used? | ruling 2026-11-06 | For numbers and code |
| 32 | How many type steps; does the test stay? | motive (WP-1201) | Steps are named roles scaled by density; the test stays |
| 33 | Icons or glyphs? | motive (site); ruling 2026-11-08 on the cog | One stroked SVG set |
| 34 | How is run state shown? | ruling 2026-11-09 (B) | As text in the action bar and status bar |
| 35 | Modals, popovers, palette? | motive | One floating-layer drawing |
| 36 | The site's top bar and wordmark? | ruling 2026-11-07, 2026-11-08 | No brand in the working bar; the wordmark is on the start screen |
| 37 | The empty state's voice? | ruling 2026-11-07, 2026-11-08 | Few plain words; no explanatory prose |
| 38 | History lanes and the 3D frame? | motive (WP-1217, WP-1462) | Kept; the palette piece re-measures the lanes |
| 39 | The window floor? | ruling 2026-11-07 | One column below a computed width; a Tauri minimum is that milestone's |
| 40 | Gridlines? | ruling 2026-11-07 | None, as in rietx's plot conventions |
| 41 | One set of curve colours? | ruling 2026-11-06, 2026-11-07 | The site's, in rietx's conventions |
| 42 | Landing animation phase colours | scope | The landing page's |
| 43 | Figure type face and size | scope; motive for the GUI | Chart text takes the GUI's face and steps |
| 44 | `make_figures.py` titles and hexes | scope | The manual's |
| 45 | A figure's light ground | scope | Figures' |
| 46 | Do captions say what to conclude? | scope | The GUI shows no captions |
| 47 | The figure skill's web preset | scope | Figures' |
| 48 | How far "a bordered box is a control" reaches | scope; motive for the GUI | In the GUI it holds everywhere (Q23) |
| 49 | Is a code block flat? | scope | The site's |
| 50 | Small-label table heads in the manual | scope | The manual's |
| 51 | Syntax colours as tokens | scope | The site's; the `.rxt` highlighter reads GUI tokens |
| 52 | One set of font files for site and manual | scope | The site's |
| 53 | H1 sizes | scope | The site's |
| 54 | Which ground is hover? | scope; motive for the GUI | The GUI's hover ground is the one the palette piece adds |
| 55 | `--accent-soft`'s job | scope | The site's |
| 56 | Is the hover guard universal? | scope; motive for the GUI | In the GUI, hover styles apply only where the device hovers |
| 57 | Are the bar's controls one height? | scope | The site's |
| 58 | A mark for agent-only material in the manual | scope | The manual's |
| 59 | One source for the card border | scope | The site's |

Count: 22 by ruling, 17 by motive, 18 outside the guide's scope (four of them with a GUI half
settled by motive), 2 to the maintainer.

## Questions to the maintainer

Sent as one batch on 2026-11-09. The maintainer answered all four the same day, and the guide
marks each `[Yue 2026-11-09]`.

- **B1** (workshop Q18). The graph title shrinks with an ellipsis, the whole title on hover,
  before the view's controls wrap. The bars approved on 2026-11-07 work this way. The first GUI's
  rule (WP-1034) says overflow wraps and never truncates, the header included. Proposed: keep the
  ellipsis for that one title. *Ruled 2026-11-09*: yes.
- **B2** (workshop Q16). The site's theme button argues in writing for two states; `theme.py`
  argues for a third, "follow the system". Proposed: Settings offers follow the system, light,
  dark and the named themes. *Ruled 2026-11-09*: yes, as Match system (the default), Light and
  Dark. Light and dark are built first; named themes such as Solarized come later, after the three.
- **B3**. Where numbers switch to scientific notation. Claude's reading of "scientific by
  default", unconfirmed: plain from 0.01 to below 10 000, scientific outside, atom-table numbers
  always plain. Proposed: keep it. *Ruled 2026-11-09*: yes.
- **B4**. How a selected plot mark, and a mark no line explains, are shown. Round 11 drew both in
  colour (the accent, the danger colour). The first GUI's rule (WP-1210) puts state on a mark's
  shape so the palette stays separable, and the accent will also be the calculated curve's hue.
  *Ruled 2026-11-09, for now*: Claude's option (b). A selected mark is drawn larger, with a ring in the
  text ink. Red marks only a peak no line explains and is the layer's only state colour; orange
  stays the fit's. The guide marks the rule provisional, so a later review can revisit it.

Settled under a stated motive and listed for the maintainer to reverse if wrong: facts drawn as
words without chips or pills; Rwp and GoF with no green; selection never by weight; reflection
ticks at the foot of the plot (rietx's convention) where the first GUI put them between pattern
and difference; right-click opening a context menu where the first GUI removed a peak.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_gui_manual.py tests/test_gui_style_guide.py
.venv/bin/python -m ruff check src tests examples
wc -w gui/STYLE.md   # well under the workshop draft's 11 192 words
```

## References

- Okabe, M. and Ito, K. (2008), *Color Universal Design*, the colour-blind-safe set behind
  `PHASE_COLOURS` and the peak-mark blue.
- Ottosson, B. (2020), *A perceptual color space for image processing* (OKLab), the distance the
  plot palette's floor is measured in.

## Handover log

### 2026-11-10 — closed; the 36 rules wait as an owed item

PR #1514 merged on 2026-11-10, after the maintainer read `gui/STYLE.md` and approved it ("looks
good") with B1-B4 ruled. Every later piece of the port is judged against it. Two pieces of work
it named stay open, and both now sit in the milestone record where the next piece will see them.

- *Leftovers, and where each went.* Moving `gui/CLAUDE.md`'s 36 visual rules into the guide
  (this WP's non-goal, WP-2134's "Next") went to `docs/milestones/gui-overhaul.md` § Owed to the
  port, citing WP-2134's coverage list. Renaming the rules that describe a role the palette
  piece adds, once its tokens exist (the gotcha below), went into that piece's row in § Designed,
  not yet filed. The rules settled under a stated motive were read with the guide at its
  approval. Declined at review and not carried: adding the new test to `ci.yml`'s docs-job list,
  since the workflow file was outside this WP. The narrative went to `docs/milestones/v1.12.md`.
- Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
- Next: none here. The palette piece is first in the milestone's order and most of § Colour
  waits on it.

### 2026-11-09 — the guide written, four questions sent

The GUI now has a style guide, `gui/STYLE.md`, that a session changing how anything looks reads
first. It gives each rule its motive and says whether the maintainer stated it (with the date)
or Claude inferred it, so a panel the prototypes left unfinished can be completed by the motive
instead of by copying the prototype. It is 3 908 words against the workshop draft's 11 192 (186
lines, 22 450 bytes against 658 lines, 66 374 bytes). The workshop's 59 open questions are all
placed: 22 by a later ruling, 17 by a stated motive, 18 outside the GUI, 2 sent on. Four rules
wait on the maintainer (B1-B4 above), and nothing in the GUI's code or colours changed.

- *Done*: the guide; the pointer line in `gui/CLAUDE.md` (cap 1060 → 1061);
  `tests/test_gui_style_guide.py` (four checks: named tokens are declared, named files exist,
  every rule ends with a marker, no hex or pixel value restated), each made to fail once on a
  planted mutation; the 59-question table and the batch above; the milestone's eleven unfiled
  pieces and acceptance rows 11-12; ROADMAP's sentence moving the peak-mark colour from WP-2130 to
  the palette piece.
- *Measured*: OKLab distance between the site's accent and danger colours, 0.114 light and 0.080
  dark, under the plot floor of 0.13 (B4's case), through `rietx.gui.structure3d._oklab`. Fast
  suite on the final tree, `[dev]` venv, macOS arm64, alone under ghostshift's serial lock:
  14 379 passed, 418 skipped, 32 xfailed. The four added tests take 0.01 s together.
- *Review*: `/code-review high --fix` found ten; nine were fixed in one commit (B2's rule had no
  marker; the contrast rule claimed a test that covers only ink on the accent fill; the token scan
  read CSS comments; four test-strictness gaps; a stale milestone heading; the cap comment).
  Declined: adding the new test to `ci.yml`'s docs-job list. It only stats the milestone file
  rather than reading it, and the workflow file is outside this WP.
- *Not done, by the non-goals*: `gui/CLAUDE.md`'s 36 visual rules (listed in WP-2134, PR #1511)
  stay where they are. Once #1511 merges, a follow-up moves each into the guide or points at it.
  WP-2134's file exists only on that branch, so no `### Inherited` note could be left there.
- *Gotchas*: the guide may name only tokens that exist, so a rule about a role the palette piece
  will add describes it in words. When that piece lands it should rename those rules to the new
  tokens; the test then holds them.
- *Next*: the maintainer answers B1-B4 (the batch went as one message). Each answer replaces an
  `[open Bn]` marker with `[Yue <date>]`. Then the palette piece, which most of § Colour waits on.

- **2026-11-09** — the maintainer answered B1-B4 the same day. A ghostshift runner replaced the
  four `[open Bn]` markers in `gui/STYLE.md` with `[Yue 2026-11-09]` and restated each rule to
  match. B4 is marked provisional ("go with yours for now"). `tests/test_gui_style_guide.py` is
  unchanged: it accepts `[open Bn]` as a marker for future questions and counts none.
- **2026-11-09** — created by a ghostshift runner on the maintainer's 2026-11-09 ruling. No open
  WP owns a style guide: WP-2134 lists the visual rules for it and fences them out of its own
  scope, and WP-2123 to 2133 each build one panel.
