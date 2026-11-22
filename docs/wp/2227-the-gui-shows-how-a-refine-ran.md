# WP-2227 — The GUI shows how a refine ran: in one stage or in stages

Milestone: gui-overhaul · Status: 🔄 2026-11-22 — built at `/next` (PR #1776); the maintainer's look at the three states waits
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

## Rulings

**Yue, 2026-11-22**, on the options in `2227-screenshots/` (the brief is the handover entry of
the same date):

1. **Where the feedback shows: (b) and (c).** Beside Rwp on the Pattern graph's title line
   ("One stage: the model had converged", "In stages: …", "In stages: the one-stage re-fit
   diverged"), and a Console comment after each fit carrying the plan line
   `Refinement.summary()` prints.
2. **The Plan tab after a one-stage re-fit: (a).** One stand-in row after the stages, drawn like
   the closing stage. The stage rows keep their counts and leave Rwp blank.
3. **A staged run for a released parameter: (a).** Name it in words where the feedback sits:
   "In stages: Atom position shift was held".
4. **The action bar keeps "Staged plan, 6 stages"** (consent line, no objection).
5. **The status bar during a re-fit reads the title line's words**, not the internal stage name
   `warm_refit (1/1)` (consent line, no objection).

## Tasks

- [x] Draw the options in the workshop and take them to Yue. Drawn 2026-11-22 over the real
      `/next` page rather than in the frozen workshop (`2227-screenshots/`); not decided.
- [x] Serve how the last run went on the run and result routes, from one authority.
- [x] Build the chosen view at `/next`, and drop `refit="stages"` from the run route.
- [x] A vitest per state (one stage, staged for a released parameter, fallback) and a browser
      screenshot of each, light and dark.
- [x] The GUI chapter names the view: listed in WP-2214 § Tests and the manual, for the swap,
      since the manual stays unchanged until then (Yue, 2026-11-22, on WP-2211).

## Acceptance

`npm --prefix gui test`, `tests/test_gui_server.py`, `tests/test_gui_manual.py`, and Yue's look
at the three states.

## Handover log

### 2026-11-22 (2nd session) — built at `/next` on the rulings (PR #1776)

The rebuilt GUI at `/next` now says how each Refine ran, in words beside Rwp on the Pattern
graph, in the status bar while it runs, in a Console comment and in the Plan tab. Refine there
now takes the library's default, so a second Refine on a converged model runs one stage. On the
`fap` example that one stage took 0.167-0.180 s where the staged re-fit took 0.424-0.426 s, and
both landed at Rwp 9.2498 %. Today's page `/` still runs in stages until the swap. The Show
choice moved from the title line into the legend, because on the title line it cut the new
words at 1440 px.

*Done.* All five rulings above, built (tasks 2-5).
- Server (`gui/session.py`): the run frame and `GET /api/result` carry `how`
  (`ran`, `reason`, `plan_line`, plus `released`/`families` or `diverged`), read once at the
  fit's end off `Refinement._refit_how` by `_how_ran`. The plan line is
  `Refinement._plan_line()`, factored out of `summary()` with its text unchanged.
  `GET /api/plan/resolve` gains `one_stage` (the re-fit's node, aligned to `_collapse(plan)` by
  `_aligned_rwp`). The run route takes an optional `refit` from the body and validates it
  against `REFIT_MODES`. `strategy.refit.WARM_REFIT_STAGE` names the one stage for the stream.
- `/next`: `next/howran.ts` turns `how` into words; `Pattern.svelte` shows them after GoF and
  hides them over a preview; `Frame.svelte` puts them in the status bar and the plan line in the
  Console; `Plan.svelte` draws the stand-in row. `/` sends `refit: "stages"`.
- The Show choice is a vertical pair in the graph's left gutter, under the main pane's curve
  labels, shown only while a preview is in hand (the maintainer's fallback, WP-2231 § Rulings 10).
- Pictures: `2227-screenshots/` § As built, 19 PNGs (three states light and dark, the Plan row,
  the Console, the status bar, both Show layouts at 1440 and 1000 px).
- WP-2231 § Rulings 9 and 10 record its Questions 1 and 2 as answered.
- WP-2214 § Tests and the manual gains a two-line note naming this view for the swap's manual
  rewrite. WP-2214 is closed, and `closed_wp_writes.py` flags it. It stays there on purpose: the
  brief asked for it in WP-2214 as WP-2211 did, and the swap's manual rewrite has no open WP.

*Measured* (arm64 Mac, worktree `.venv` `[dev]` + playwright, node v24).
- `fap` through the GUI route, server elapsed: first fit 0.626-0.631 s (staged); re-fit with
  `refit: "stages"` 0.424-0.426 s, 6 stages; default re-fit 0.167-0.180 s, 1 stage; Rwp
  9.2498 % for both re-fits. Freeing a held Biso: 7 stages, Rwp 9.2314 %. A forced rejection:
  7 stages, 0.78-1.0 s.
- Title line at 1440 × 900 with a preview up: the Show toggle on the line left 311 px for words
  needing 437-497 px (cut); in the legend, 494 px (not cut). At 1000 × 640 the graph panel is
  about 215 px and the line is cut in both layouts, as before this PR.
- Fast selection (`-m "not slow"`, through the shift's serial gate): 15301 passed, 433
  skipped, 32 xfailed. One test added: `test_a_refine_says_how_it_ran_on_the_run_and_result_routes`,
  1.64 s in this run (local junit), not in the slow tail.
- vitest: 941 passed in 54 files (7 added: 5 in `next/howran.test.ts`, one each in
  `Plan.test.ts` and `Preview.test.ts`). svelte-check: 0 errors. Browser files (`tests/*_browser.py`): 178
  passed. `tests.reader_output`: exit 0, unchanged. CI's vale steps: exit 0. ruff clean.
- `/code-review high --fix` found 8 and fixed 4, all in `gui/session.py` (commit `10618d9f1`):
  `diverged` now reads the last discarded stage node, as `WARM_REFIT_REJECTED` does; the closing
  stage keeps the one-stage words in the status bar; a cancelled or failed fit carries no `how`;
  the Plan row reuses `_stage_rwp`. Declined: Le Bail pass progress under the words (a wording
  call for Yue), the kept last result (one superseded result), a possible overlap of the Show
  pair with the difference label on a short window (not reproduced), and a committed corpus for
  the two-member `how` vocabulary (gui/CLAUDE.md's corpus rule; arguable at two members).
- Generality: no trigger. The branch leaves `_audit.py`, the rulebooks and the skill alone and
  adds no fitting heuristic.

*Gotchas.*
- A test that fits twice and expects stages now passes `refit: "stages"`
  (`test_running_the_same_plan_twice_shows_the_second_run`).
- `rietx.refine` the module is shadowed by the function at `rietx.refine`; a test patching
  `_rejected` imports it with `importlib.import_module("rietx.refine")`.

*Settled by Claude* (for the PR's reviewer to reverse):
1. `/` keeps Refine in stages until the swap (`refit: "stages"`). Grounds: the 2026-11-19
   ruling that a user must see which way a run went, which `/` cannot show, and WP-2214's
   "nothing on the default page changes until the swap". Alternative: both pages take the
   default, as task 3 reads literally.
2. The Show choice is a vertical pair under the curve labels, with "Show" above it. Grounds: the
   gutter is 112 px and a side-by-side pair needs about 137 px. Alternative: a row in the plot's
   top margin.
3. "diverged" only when the one stage diverged, "was discarded" when an error-level code
   rejected it. Grounds: `schemas.sequential._rejected` rejects on either.
4. A first fit reads "In stages". Grounds: the 2026-11-19 ruling asks every run to say which.
5. `_refit_how` stays private and the server reads it, as it reads `_head_id`. Alternative: a
   public `Refinement.refit_how`, a top-level API decision.
6. More than two released families read "A, B and N more were held", for room.

Next: Yue looks at `2227-screenshots/` § As built, the acceptance's last item. If #1775
(WP-2212's Console) merges first, the Console comment moves to its line kinds. When both are
settled, close this WP.

- **2026-11-22** — Task 1 is drawn and nothing is decided. Each option for the three questions
  is drawn over the real rebuilt page on the `fap` example, light and dark, in
  `docs/wp/2227-screenshots/` (PR #1770). Its README lists every picture. Drawing them turned up
  two facts about today's page. After a one-stage re-fit the Plan tab shows every stage's Rwp
  blank. While one runs, the status bar shows the internal stage name `warm_refit (1/1)`. A
  fourth question came up: the action bar's "Staged plan, 6 stages" would then run one stage.
  Next: Yue answers the four items below; then task 2 (serve how the run went) and task 3 (build
  the chosen view).

  **Brief for Yue.** Four items need a judgement. Items 1 to 3 are visual questions, which go
  to Yue by the 2026-11-06 ruling. Item 4 names a control on the main window.

  *Why it matters (all four).* Since WP-2224, a second `fit` of a model that its last fit
  converged frees everything the plan frees, all at once, in one stage. On the eight comparison
  standards that costs 0.15-0.27 of a staged re-fit's evaluations and lands within 0.045 esd of
  the staged answer. It runs the stages instead in two cases: the plan frees something the last
  fit held, or the one stage diverges and is thrown away. Yue ruled on 2026-11-19 that a user
  must see which happened. Until then the GUI runs every Refine in stages, so every GUI re-fit
  pays the staged cost. The fit's numbers are right either way. Importance: moderate.

  *Aim.* A GUI user who never opens the Console can tell from the window how the last Refine
  ran, and why when it was not the quick path. This serves the installer audience, who do not
  read Python.

  *Practice* (`docs/practice.md` § How a program reports the way a refinement ran). TOPAS,
  GSAS-II and FullProf do not stage, so none has a view to copy. Each reports a run as its
  agreement indices, with the cycle log one step away. GSAS-II also adds one Notebook line per
  accepted run ("LS Refinement: Rw = …, GOF = …"; source read). TOPAS and FullProf are recall or
  an earlier survey. Profex with BGMN stages by itself; whether its panel names the step is not
  checked. Nothing here departs from practice, because practice is silent.

  1. **Where the feedback shows.**
     - (a) The Plan tab only (`ladder-row-*`, `ladder-span-one`). It is seen only when the Plan
       tab is in front. The Parameters tab is in front by default.
     - (b) Beside Rwp on the Pattern graph's title line (`title-*`): "One stage: the model had
       converged", "In stages: Atom position shift was held". It is on screen whichever model
       tab is in front. With the graphs hidden, the action bar already carries Rwp and GoF
       (ruling of 2026-11-09), so the words would follow them there. The longest phrase fills
       the title line at 1440 px, so a narrower window cuts it with an ellipsis and shows it
       whole on hover (`gui/STYLE.md`).
     - (c) The Console only (`console-all`): after each `ref.fit(...)` line, a comment carries
       the plan line `Refinement.summary()` prints. Alone it misses the WP's goal, since the
       Console starts hidden.
     - (d) Several: (b) or (a), plus (c). The Console line is a small addition beside either.
     - Whatever is chosen, the status bar's text during the run changes from `warm_refit (1/1)`
       (`status-today`) to plain words, as Yue's 2026-11-19 ruling on coined names asks.
     - Dropped: the status bar after the run, because the 2026-11-11 ruling keeps it empty at
       rest; a pop-up notice, because it is gone before a person looks back.
     - Lean: (b) with (c), because the title line is on screen at every Refine.
  2. **The Plan tab after a one-stage re-fit** (state one only).
     - (a) One row stands in (`ladder-row-one`). A block after the stages reads "One stage",
       "Free Everything above, at once", 20 free, Rwp 9.25 %. The stage rows keep their counts
       and show no Rwp. The block reuses the closing stage's drawing.
     - (b) One Rwp spans the rows (`ladder-span-one`). A bracket joins the six stages with
       Rwp 9.25 % and "all six at once" at its middle. The bracket is a drawing the GUI has
       nowhere else.
     - (c) Nothing changes (`ladder-blank-one`): every stage's Rwp stays blank, and the
       feedback lives elsewhere (item 1). Blank Rwps read as stages that never ran.
     - Dropped: showing the earlier staged run's Rwp per stage. A stage's Rwp is its own
       history node's (WP-1208), and those numbers describe a different run.
     - Lean: (a), because it reuses a block the tab already draws and keeps the Rwp column
       meaning "this stage ran".
  3. **Whether a staged run names what the last fit held** (state released; the fallback's
     reason is drawn alongside in `title-fallback` and `ladder-row-fallback`).
     - (a) Name it in words where the feedback sits (`title-released-named`): "In stages: Atom
       position shift was held". The words are the family's help title. `summary()` lists the
       twelve paths, which would not fit.
     - (b) Mark its chip in the Plan tab and name it in the tooltip (`ladder-row-released`): an
       accent ring and dot on "Atom position shift". It works only in the Plan tab.
     - (c) Do not name it (`title-released-unnamed`): "In stages". The Console's line carries
       the paths.
     - Lean: (a). The case is a person who added a stage and then sees a slower Refine, and the
       name answers why at once.
  4. **The action bar's choice "Staged plan, 6 stages".** Once the GUI re-fits in one stage,
     this choice will run one stage on a converged model. Consent line: I will keep the label,
     because the plan is still the recipe and item 1's feedback says how it ran, unless you
     prefer "Plan, 6 stages".

  *Settled by Claude*, most consequential first:

  1. The options are drawn over the real page by editing its DOM in a scratch probe, rather
     than as standalone HTML pages. Grounds: Yue's 2026-11-10 ruling that a visual question
     shows the whole window with the region boxed. The alternative was a hand-built page from
     the tokens, which would drift from the real Plan tab.
  2. The released state frees atom positions (twelve paths in one family) rather than one
     parameter. Grounds: it is the common next step after a first staged fit, and it tests
     naming a family. The alternative was a single parameter such as the zero shift.
  3. The words in the pictures are placeholders in plain words (Yue's 2026-11-19 ruling). The
     final text is a reader-output change and comes back to Yue with task 3.
  4. WP-2231's § Questions 1 is left as it is, since that WP is in flight on another branch.

  *Measured* (real fits of `fap`, the R4 build at `49bacf929`, macOS arm64). A one-stage re-fit
  ran 5 iterations with 20 free and landed at Rwp 9.2498 %, the same as the staged fit to four
  digits. The plan plus a positions stage ran in seven stages because it frees twelve atom
  coordinates the last fit held, and ended at Rwp 9.2314 %. The fallback's 45.21 % is
  illustrative: no real fit has triggered it.

  *Gotchas.* The probe serves a `git archive` of the R4 branch with `PYTHONPATH`, and patches
  that copy's run route to pass `refit` from the request; the repository's run route still
  passes `refit="stages"`. Theme is switched by emulating the system colour scheme, since
  `/api/settings` holds only the front end's own keys.

- **2026-11-19** — Filed by the WP-2224 session from Yue's rulings on its four questions. No
  open WP owned the work (fold check above). Nothing built.
