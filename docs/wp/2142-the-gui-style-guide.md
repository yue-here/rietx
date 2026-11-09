# WP-2142 — The GUI style guide

Milestone: gui-overhaul · Status: 🔄 2026-11-09 — claimed by @yue-here
Depends on: —
Priority: P2 2026-11-09 — every later gui-overhaul piece is judged against it (ruled 2026-11-09)

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

- [ ] Claimed: this file, the index row, a draft PR.
- [x] `gui/STYLE.md`: rule, motive and marker per element, with the tests that check them named.
- [ ] `gui/CLAUDE.md`: the pointer line.
- [ ] A test that every token and test the guide names exists.
- [ ] The 59 questions, each settled or sent on, recorded below; the batch to the maintainer.
- [ ] `docs/milestones/gui-overhaul.md`: the unfiled pieces and the screenshot acceptance row;
      ROADMAP's sentence on the peak-mark colour.
- [ ] Skill: none. The skill is for an agent driving rietx; the guide governs changing the GUI.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_gui_manual.py tests/test_gui_style_guide.py
.venv/bin/python -m ruff check src tests examples
wc -w gui/STYLE.md   # well under the workshop draft's 9 400 words
```

## References

- Okabe, M. and Ito, K. (2008), *Color Universal Design*, the colour-blind-safe set behind
  `PHASE_COLOURS` and the peak-mark blue.
- Ottosson, B. (2020), *A perceptual color space for image processing* (OKLab), the distance the
  plot palette's floor is measured in.

## Handover log

- **2026-11-09** — created by a ghostshift runner on the maintainer's 2026-11-09 ruling. No open
  WP owns a style guide: WP-2134 lists the visual rules for it and fences them out of its own
  scope, and WP-2123 to 2133 each build one panel.
