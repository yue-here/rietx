# WP-2122 — The mark's bar redrawn, and the header lockup set on the type

Milestone: unscheduled · Status: 🔄 2026-11-08 — claimed by @yue-here
Track: The repo's own process
Depends on: —
Priority: P4 2026-11-08 — brand drawing; changes no number and no decision

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
- [ ] Re-set both headers' lockup CSS
- [ ] Measure the built pages at 16.8 px in both themes: bar top on baseline, Kα2 tip on
  x-height, error in px; look at the favicon at 16 and 32 px and the header at desktop and 390 px
- [ ] Tests: `tests/test_manual.py`, `tests/test_landing.py`
- [ ] Skill: none — the mark is not something an agent driving rietx reads

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_landing.py -n auto --dist loadgroup
```

Plus the measured baseline and x-height errors in the handover entry, each under 0.5 px.

## References

Instrument Sans (OFL), `docs/docs/_static/fonts/`.

## Handover log

- **2026-11-08** — created. No open WP owns the mark: WP-2021, which made the favicon its
  authority, is ✅, and WP-1986 (🔄) is about the guides.
