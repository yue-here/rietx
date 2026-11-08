# WP-2122 — The mark's bar redrawn, and the header lockup set on the type

Milestone: unscheduled · Status: ✅ 2026-11-08 — square-ended stem-thick bar; both headers set the lockup on the baseline and x-height to 0.01 px; the favicon parses as XML again
Track: The repo's own process
Depends on: —

## Goal

The mark's bar has square ends and is as thick as the wordmark's stem. In both headers
(the manual's and the landing page's) the bar's top edge sits on the wordmark's baseline,
the smaller (Kα2) peak tops out on the x-height, and the ink gap between bar and `r` is
one x-height.

## Context

Yue approved every value here on 2026-11-08 (from a spec written outside the repo,
restated below in full), so the work actions it as specified.

**What Yue decided.**

1. The bar's ends are square: the rect loses `rx="1.5"`.
2. The bar is as thick as the wordmark's stem: 3.1 units of the 32-unit box, up from 3.
3. In the header lockup the bar's top edge sits on the text baseline. The mark is scaled so
   the Kα2 peak tops out on the x-height. The gap is one x-height of ink.
4. Peak heights stay as drawn. Yue declined redrawing Kα2 at the physical 1:2 ratio.

**The new mark** (32-unit viewBox; only the rect changes; its top stays at y=25.5, so the
bottom moves from 28.5 to 28.6):

```svg
<path d="M2 26 C7 26 9 23 11.5 3.5 C14 23 16 26 21 26 Z"/>
<path d="M17 26 C20 26 21.5 24 23 13 C24.5 24 26 26 29 26 Z"/>
<rect x="1.5" y="25.5" width="29" height="3.1"/>
```

Files: `docs/landing/src/favicon.svg` is the authority (WP-2021).
`docs/docs/_templates/rietx-brand.html` and `docs/landing/src/shell.html` hold inline
copies, held equal by `tests/test_manual.py::test_the_site_draws_one_mark`. A grep of the
tree on 2026-11-08 (`11.5 3.5`, worktrees excluded) found no fourth copy.

**The lockup.** Instrument Sans SemiBold, wdth 100. Lengths in em of the wordmark's type,
px at the header's 16.8 px in brackets. Font metrics assumed by the spec: x-height 0.510,
SemiBold stem 0.1267, `r` left side bearing 0.0667 — to be confirmed against the served
font (task 1).

- Scale: 0.0408 em per mark unit; the 32-unit box is 1.306 em (21.93 px), down from 22 px.
- Vertical: unit y=25.5 on the baseline, so the box's bottom is 0.265 em (4.46 px) below
  it. Today `align-items: center` leaves the bar 0.03-0.15 em below the baseline.
- Bar thickness: 3.1 units = 0.1265 em (2.13 px), the stem.
- Gap: ink gap from the bar's right end (x=30.5) to the `r` stem is 0.51 em (8.57 px).
  Less the box's right margin (1.5 units, 1.03 px) and the `r` side bearing (1.12 px):
  0.382 em (6.42 px) between box and text, down from `gap: 9px`.
- Kα1 tops out at 0.90 em; the mark's ink spans −0.127 to +0.90 em.

CSS: `docs/docs/_static/custom.css` (`.rietx-brand`, `.rietx-brand .rietx-mark`; the
wordmark is a `<p>` at 1.05rem inside the `<a>`, so an em on the svg resolves against the
`<a>`) and `docs/landing/src/shell.html` (`.brand`, `.brand svg`).

The tier of each rule this WP adds: none. It adds no flag, threshold, default or
automatic action.

## Non-goals

- Redrawing the peak heights (Yue declined the 1:2 Kα2 ratio, decision 4).
- The GUI's own icon or any other surface outside the two site headers and the favicon.

## Tasks

- [x] Measure the served font (`_static/fonts/`) with fontTools: x-height, SemiBold stem,
  `r` left side bearing; recompute the lockup if they differ, keeping the four rules
- [x] Redraw the bar in the favicon and both inline copies; favicon comment if it describes the bar
- [x] Re-set both headers' lockup CSS
- [x] Measure the built pages at 16.8 px in both themes: bar top on baseline, Kα2 tip on
  x-height, error in px; look at the favicon at 16 and 32 px and the header at desktop and 390 px
- [x] Tests: `tests/test_manual.py`, `tests/test_landing.py`
- [x] Skill: none — the mark is not something an agent driving rietx reads

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_landing.py -n auto --dist loadgroup
```

Plus the measured baseline and x-height errors in the handover entry, each under 0.5 px.

## References

Instrument Sans (OFL), `docs/docs/_static/fonts/`.

## Handover log

- **2026-11-08** — closed. The site's mark now has a square-ended bar as thick as the
  wordmark's stem. In both headers the mark is set on the text: the bar's top edge is the
  baseline, the smaller peak reaches the x-height, and one x-height of ink separates bar and
  word. Measured in Chromium, every one of those errors is 0.01 px or less. In passing, the
  favicon turned out to have been invalid XML since WP-2021 (22 Oct), because its comment
  held a double hyphen. No browser drew it on either page for 17 days. It parses now, and
  the mark test fails on the old file.

  *Done.* Bar redrawn in `favicon.svg` and both inline copies (`rx` dropped, height 3 →
  3.1). The lockup's lengths are three tokens in `docs/landing/src/tokens.css`
  (`--mark-unit` = 0.510/12.5 em, `--mark-drop` = 6.5 units, `--mark-gap` = 0.510 em less
  1.5 units less 0.0667 em). Both headers read them: `align-items: baseline` puts the svg's
  bottom on the text baseline, and `position: relative; top: var(--mark-drop)` lowers it.
  In the manual pydata sizes the brand link to the bar's height, so baseline alignment put
  the lockup at the top of the bar. The link now takes its content's height, and
  `.bd-header__inner` holds the bar at `--pst-header-height`, since the brand was all that
  had given it its 56 px. `test_the_site_draws_one_mark` now parses the favicon with
  `ElementTree` first; it failed on the old file with its own message.

  *Measured.* Served font (Fontsource 5.3.0 woff2, wght 600, fontTools): x-height 0.510,
  stem 0.1267, `r` left side bearing 0.0667 em, the spec's numbers, so nothing was
  recomputed. Google Fonts' copy on the landing page reads the same through canvas
  `measureText`. Chromium (playwright, chromium-1223) at 16.8 px, light and dark, 1280 and
  390 px wide, both pages: bar top − baseline 0.00 px; Kα2 tip − x-height −0.01 px; ink gap
  − x-height −0.01 px; bar 2.124 px against a 2.129 px stem; Kα1 tip 0.898 em; box 21.93 px.
  Lockup ink centred in the bar to +0.46 px (landing) and −0.36 px (manual). No horizontal
  scroll at 390 px. Favicon drawn at 16 and 32 px, DSF 1 and 2, light and dark.
  `tests/test_manual.py` + `tests/test_landing.py`: 102 passed. Fast suite (`-m "not slow"`, `[dev]`
  venv, darwin/arm64, no other suite running): 14338 passed, 416 skipped, 32 xfailed, in
  about 9 min. No test was added (one existing test gained a check), so passed+skipped
  should not move. The full suite did not run: the branch is docs, CSS and one test, and
  moves no measured number.

  *Review.* `/code-review high --fix`: the lockup's lengths were spelled in both
  stylesheets with nothing holding them equal, so they moved to `tokens.css` (fixed,
  re-measured unchanged). Skipped: the manual's brand link is now about 31 px tall
  instead of 56 px. That matches the landing page's 29 px and is above WCAG 2.2's 24 px
  target minimum. No other SVG is committed, so the XML guard stays on the favicon.

  *Gotchas.* An XML comment may not hold `--`, and a regex-read test cannot see it. The
  desktop app's browser pane runs no `requestAnimationFrame` while hidden, so a probe
  awaiting one times out. Only Chromium was measured; Safari and Firefox were not.

  *Next.* None in this WP. The maintainer reviews PR #1465.
- **2026-11-08** — created. No open WP owns the mark: WP-2021, which made the favicon its
  authority, is ✅, and WP-1986 (🔄) is about the guides.
