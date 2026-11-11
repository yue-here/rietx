# WP-2215 — the frame: the rebuild's first piece, served at `/next`

Milestone: gui-overhaul · Status: 🔄 2026-11-11 — filed from WP-2214's piece R1; the page, its bars and panels first
Depends on: 2214 (the rebuild's plan and inventory)
Priority: P2 2026-11-11 — a feature the open milestone was opened for: every later piece of the rebuild mounts in this frame

## Goal

The rebuilt GUI gets its frame, as a second page of the same build. `rietx gui --new` opens
the browser at `/next`; `/` stays today's GUI, unchanged. The frame is what every later piece
mounts in: the top bar, the status bar, the two side panels and the bottom panel with their
toggles and sashes, the workflow menu, the File menu, Settings, the command palette and the
keys, one menu component every later piece uses, the start screen, New project and the
recovery offer, and the Console. It is judged whole beside the prototype at 1440 × 900, light
and dark.

## Context

WP-2214 is the plan. Its § The pieces names R1 and the inventory rows it owns: 1-24 (top bar,
action bar), 147-151 (the Console in the bottom panel) and 212-242 (start screen, New project,
File menu, keys, palette). Its § Two front ends, one server fixes the shape: `gui/next.html`
with its code under `gui/src/next/`, beside `gui/index.html` and `gui/src/App.svelte`, both
importing `gui/src/lib`, `gui/src/api.ts` and `gui/src/tokens.css`, both written into the
committed dist, one session behind both pages. The maintainer's five rulings of 2026-11-11 are
recorded in WP-2214 § Questions; R1 is bound by two of them. The status bar's right half holds
the report's count of findings only, never the mode or the σ source (question 3). Each piece of
chrome text on WP-2214's audit list is settled while its piece is built and listed in the PR
(question 4).

How the frame reads, restated from the prototype (WP-2214 § What the prototype is): a top bar
holding, left to right, the graphs toggle, the workflow menu, the project name that opens the
File menu, a gap, Settings and the model toggle. Below it the graphs on the left and the model
on the right, each with a tab strip ending in a `?` box, split by a sash. The action bar ends
the model panel. Under both, the bottom panel (Console, History), hidden at first. Along the
foot, the status bar, with the console toggle at its left. The bars never change shape, so no
toggle moves (`gui/STYLE.md` § Layout and panels).

What it carries from closed work (WP-2214 § What happens to the open GUI pull requests):

- from #1521 (WP-2206, WP-2207), `lib/statusbar.ts` with its tests, the Console's Copy and
  Follow, the bottom panel's sized pane, and the first-run-moves-nothing browser case;
- from #1524 (WP-2204), `lib/workflows.ts` with its tests, and the placeholder screen's content;
- from branch `wp2213-the-graph-window` (head eaabe834f), `panels/Menu.svelte` and
  `lib/portal.ts`;
- from #1522 (WP-2201), the `style.test.ts` guard against uppercase and tracked headings. The
  new page's stylesheet starts in sentence case.

## Tasks

- [ ] The page: `gui/next.html` and `gui/src/next/`, a second entry of the Vite build; the
  server serves it at `/next`; `rietx gui --new` opens the browser there; the manual's route
  partition lists `/next` among the exclusions with its reason. `/` is unchanged.
- [ ] The frame: top bar, status bar, the graphs and model columns with their tab strips,
  their collapse toggles (⌘1, ⌘2) and the sash, the bottom panel with the Console (⌘J); the
  run state and Stop in the status bar (⌘.).
- [ ] One menu component and the workflow menu on it.
- [ ] The File menu and the project name, mounted from today's `FileMenu`.
- [ ] Settings (⌘,): theme as Match system, Light, Dark; the About line with the version.
- [ ] The command palette (⌘K) and the keys (rows 228-240), with `?` listing them.
- [ ] The start screen, New project and the recovery offer mounted in the frame.
- [ ] The action bar (rows 18-24) as the model panel's foot.
- [ ] `gui/CLAUDE.md` gains a `gui/src/next/` line; the `style.test.ts` sentence-case guard
  covers `gui/src/next/`.
- [ ] Screenshots of each screen beside the prototype's, light and dark, at 1440 × 900, under
  `docs/wp/2215-screenshots/` (the prototype's own stay in the runner's scratch).

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_dist.py tests/test_gui_manual.py
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py   # local: CI runs no browser test
```

The piece closes when every task is ticked and the maintainer has looked at its screens beside
the prototype's (WP-2214 § How the maintainer reviews).

## References

- [WP-2214](2214-the-gui-rebuild-plan-and-inventory.md), the plan and the inventory; `gui/STYLE.md`;
  `gui/CLAUDE.md`; the milestone record `docs/milestones/gui-overhaul.md`.

## Handover log

- **2026-11-11** — filed by a ghostshift runner from WP-2214's piece R1, the last task of that
  WP, which closes with it. No open WP owned the frame: WP-2214's plan names it as the first
  piece and leaves it to be filed. The number was checked against `origin/main`, the remote
  branches and the open pull requests.
