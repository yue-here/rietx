# WP-2227 — The GUI shows how a refine ran: in one stage or in stages

Milestone: gui-overhaul · Status: ⬜
Depends on: 2224 (the re-fit rule)
Priority: P2 2026-11-19 — a ruling of Yue's waiting on the GUI; the rebuild's Plan tab (R4 of WP-2214) is where it lands

## Goal

Refine in the GUI gets the library's default. A second Refine on a model the last fit
converged runs one stage, and a Refine that frees something the last fit held runs in stages.
The person sees which happened, and why, without opening the Console.

## Context

WP-2224 made a second `fit` of a converged model run one stage, `warm_refit`. It runs the
plan in stages instead when the plan frees a parameter the converged fit held, and when the
one stage is rejected (`WARM_REFIT_REJECTED`). `Refinement.summary()` states which of the
three happened in its plan line.

Yue ruled on 2026-11-19: "it should be clear to users whether the run is staged or single",
and "there should be visual feedback in the gui". Visual design is Yue's (memory: visual
questions go to Yue), and the rebuild's designs are drawn in the GUI workshop first.

Today's GUI passes `refit="stages"` on every Refine (`src/rietx/gui/session.py`, the `call`
closure in the run route). The reason: after a one-stage re-fit no history node matches a
rung of the plan on screen, so the Plan tab's Rwp column goes blank (`gui/CLAUDE.md` § Parameters
and plan, "A stage's Rwp is its history node's").

What the server can already say, with no new library field:

- `RefinementResult.stages`: one stage named `warm_refit`, or the plan's stages.
- `Refinement._refit_how`: `"single"`, `"fallback"`, or the list of paths released. It is
  private. A route needs it public, or reads the same facts off the stage names and the
  diagnostics.
- The `refit_discarded` note on the nodes of a rejected one-stage fit, and `refit_key` /
  `refit_frees` on an accepted answer's node.

Fold check: no open WP owns this. R4 (the Plan tab at `/next`) is a row of WP-2214's table and
has no WP yet. Today's Plan panel is deleted at the swap, so the work belongs at `/next`.

## Questions for Yue (before any building)

1. Where the feedback shows: the Plan tab's ladder, the status bar beside Rwp, the Console
   line, or several.
2. What a one-stage re-fit's ladder looks like: one row standing in for the plan's stages, or
   the plan's rows with one Rwp spanning them.
3. Whether a Refine that runs staged for a released parameter names that parameter on screen.

## Tasks

- [ ] Draw the options in the workshop and take them to Yue.
- [ ] Serve how the last run went on the run and result routes, from one authority.
- [ ] Build the chosen view at `/next`, and drop `refit="stages"` from the run route.
- [ ] A vitest per state (one stage, staged for a released parameter, fallback) and a browser
      screenshot of each, light and dark.
- [ ] The GUI chapter names the view.

## Acceptance

`npm --prefix gui test`, `tests/test_gui_server.py`, `tests/test_gui_manual.py`, and Yue's look
at the three states.

## Handover log

- **2026-11-19** — Filed by the WP-2224 session from Yue's rulings on its four questions. No
  open WP owned the work (fold check above). Nothing built.
