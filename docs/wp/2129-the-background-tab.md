# WP-2129 — the Background tab

Milestone: gui-overhaul · Status: 🔄 2026-11-09 — filed and started by a ghostshift runner
Depends on: 2123, 2125 (the shell it draws in, and the preview route whose compile cache it reuses)
Priority: P2 2026-11-09 — piece 5 of the gui-overhaul milestone, the last of the five

## Goal

The graph column gains a Background tab. It draws the observed pattern greyed, the background
curve at the working state's values, and a shaded band showing where that curve may move when the
free parameters refine. The band comes from rietx's own covariance, served by a new route. A
Chebyshev background offers a hold on each term, through the existing hold verb, and a P-spline
background shows its smoothness λ and lets the person edit it.

## Context

### The designs, and the rulings they rest on

The maintainer reviewed the background preview on screen in the design rounds of 2026-11-06 to
2026-11-08. The prototypes are not published, so each design this WP builds is restated here with
its ruling.

1. **The background is one group with an interactive preview.** Ruled 2026-11-06 (first Parameters
   review): "Individual background coefficients are meaningless to switch. Background is one group
   with an interactive preview: greyed data, the curve, and a shaded band for how it might move
   with the active parameters refining." So the Parameters panel offers no switch per coefficient;
   the background is one group there, and the per-term control lives in this tab.
2. **The band shows where the curve may change, and may be exaggerated.** Ruled 2026-11-07 (second
   Parameters review): "Background bands show where the curve may change when terms are held, and
   may be exaggerated." The prototype drew the band at ±3 esd and offered "Band drawn" at ×1, ×5
   and ×20. The GUI rulebook's caption rule applies (an exaggeration is not a probability), so the
   level and the multiplier are stated separately.
3. **The background preview is a graph tab.** Ruled 2026-11-07 (third review): it "should probably
   be a tab in the main panel, along with peaks." The fourth review put the graphs on the left in
   tabs, each with a title line saying what it shows (WP-2123, designs 1 and 2).
4. **A held Chebyshev term keeps its value from the previous cycle.** Ruled 2026-11-07 (third
   review): "the idea was that a held term keeps its value from the previous cycle (not from the
   click)." rietx's `Refinement.hold` (WP-1435) does exactly this. It leaves the stored value where
   the last cycle put it and blocks every later free, a plan's included. It records a `set_hold`
   node, so a hold is undone with History's checkout or with `unhold`.
5. **The points background is deferred.** Ruled 2026-11-07 (third review): it "needs more UI work,
   deferred until the GUI goes into the main repo". rietx has no such background type, and a new one
   is a stored-format change the milestone record lists as waiting on the maintainer. Not here.
6. **No click moves the layout unless it asks to** (interaction rule 8, adopted 2026-11-08). Holding
   a term and editing λ ask for no layout change, so the layout browser test covers this tab.
7. **No permanent explanatory text** (sixth review, 2026-11-07). What the band means lives in a
   tooltip, never in a line under the plot.

### What the band is

The prototype computed its band in JavaScript from matrices exported by a script: the background
basis, the structural Jacobian columns at the converged fit, and their normal matrix. It solved the
free background terms and the free structural parameters together, then drew ±3 esd of the curve
from the background block of the inverse. Here the server computes the same quantity in rietx, so
there is one copy of the statistics.

The band is the esd of a derived quantity, the background curve y_b(2θ) at each fitted channel,
taken through the whole covariance. That is the manual's estimation chapter, `est-derived` over
`est-cov`:

- J is the full weighted Jacobian at the working state's values, from the solver's own
  `_make_jacobian`, with every residual row the solver sees, P-spline penalty rows included. The
  free set is the working one: the ticked rows, less held rows and less what the intensity mode
  force-fixes. So a held term has no column and carries no variance.
- Cov = χ²_red · (JᵀJ)⁻¹ through `statistics.normal_factors`, the equilibrated guarded solve every
  esd in the package uses, with χ²_red over the data rows.
- g_k(2θ) = ∂y_b(2θ)/∂θ_k, by central difference of `CompiledModel.background` through the table's
  decode. The background is linear in its coefficients, so the difference is exact there. A column
  that does not reach the background has g = 0 and drops out.
- σ_b(2θ) = f · √(gᵀ Cov g), with f the Bérar-Lelann factor on the same residual, so the band
  carries the inflation every reported esd carries.

Because Cov is the inverse of the whole normal matrix, the band is marginal over every other free
parameter. A free scale or Biso that trades against the background widens it. That is the
prototype's "given what else is free", and it is what makes the band useful: it shows where the
data cannot tell the background from the structure.

Two readings a person needs, written into the tab's tooltip. The band is linearised at the current
values. Before a fit has converged it describes the curvature there, and nothing more. And it is
drawn at 3 esd times the chosen multiplier, so a band drawn at ×20 is a picture of the shape, not
of a probability.

The chapter's absent-rather-than-zero rule holds. With no free column reaching the background
there is nothing for the band to describe, and the route sends none. A free column the data does
not constrain (`normal_factors`' 1/d = 0) that reaches the background makes the band unmeasured,
and the route sends none, saying why.

### What exists, and what is missing

- `POST /api/preview` (WP-2125) caches a compile per working state in `gui/preview.py`, keyed on
  the history head, the mode, the limits and the excluded regions. The band reuses it.
- `Refinement.hold` and `unhold` exist; the GUI has no route to them on `main`. PR #1484 (WP-2126,
  open) adds a `hold` arm to `PATCH /api/params`. This WP adds the same arm, with the same contract
  (glob → `true` holds, `false` releases; releases before the vary flags, holds after), so the two
  merge to one.
- `PATCH /api/instrument` replaces the instrument model, which is how λ is edited. λ changes the
  penalty rows, so the band moves with it at the next fetch.
- The Model panel already sets the Chebyshev term count and the background family. Neither moves
  here.

### Tier

The band reads the fit and decides nothing, so it is no heuristic in the sense of
`docs/milestones/generality.md` § The rule. Its 3 esd and multipliers are drawing choices in the
client.

### Calls settled by Claude

No ruling covered these, so each took the smallest neutral option. Each is marked "settled by
Claude, reversible", with its alternative, and waits for the maintainer's review of the PR.

1. Settled by Claude, reversible: the band uses the working free set, the set "One cycle" refines.
   Alternative: the set the staged plan's stages would free.
2. Settled by Claude, reversible: the curve drawn is the background at the working state's values.
   The prototype's one-step prediction of the next cycle's curve is not drawn, since at a converged
   fit it is the same curve. Alternative: draw the linearised next-cycle curve too.

## Non-goals

- The points background (design 5).
- The background family and the Chebyshev term count, which stay in the Model panel.
- A zoom on this view.
- Any change to `panels/Params.svelte` (PR #1484 owns it).

## Tasks

- [x] `src/rietx/gui/background.py`: the band, cached per working state; `GuiSession.background`
  and `GET /api/background`; the `hold` arm on `PATCH /api/params`
- [x] Tests: the band against an independent normal-equations computation, held and unheld, a
  free scale widening it, absent with no free background term, the hold arm, the 409, nothing
  written by the GET
- [x] Client: `lib/background.ts` (pure drawing helpers), `panels/Background.svelte`, the graph tab
  and its title line, per-term holds and the λ field; vitest
- [x] Layout browser test over the Background tab, with real clicks
- [ ] Manual: the route and the tab in the GUI chapters, the band tied to the estimation
  chapter's derived-esd equation; screenshots where changed
- [ ] Skill: none expected; the agent skill drives the python API

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_background.py tests/test_gui_layout_browser.py tests/test_gui_manual.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- The maintainer's rulings of 2026-11-06 to 2026-11-08, restated above with their dates.
- Bérar & Lelann (1991), *J. Appl. Cryst.* **24**, 1-5: the esd inflation the band carries.
- McCusker et al. (1999), *J. Appl. Cryst.* **32**, 36-50: the whole covariance in a derived esd.
- Eilers & Marx (1996), *Stat. Sci.* **11**, 89-121: the P-spline penalty whose rows enter J.

## Handover log

- **2026-11-09** — filed by a ghostshift runner as piece 5 of the gui-overhaul milestone, which
  listed it as not yet filed. The number is 2129, the next free one after the shift's 2126-2128;
  the milestone record claims 22xx for these pieces, and 2125 already set the precedent. The branch
  stacks on WP-2123 (PR #1476) and WP-2125 (PR #1479), neither merged yet.
