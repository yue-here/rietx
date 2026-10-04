# WP-1504 — the figure surface measured with real agents

Milestone: rietview · Status: 🔄 2026-10-04 — option E run at N = 3: fixed 40/42 done against before 25/42; the maintainer's spot-check remains, then close
Depends on: 1501, 1502, 1503; 1529 soft (the next round)
Priority: P3 2026-10-04 — option E ran and found no new defect; the maintainer's spot-check of the fixed figures is all that remains

## Goal

A before-and-after measurement of whether an agent given only the skill can
make the figures a chemist asks for, on two models, with the tasks, the
harness and the scores committed. Its result decides what WP-1501 to 1503
keep and whether WP-1505's trigger has fired.

## Context

### Why a measurement, and why real agents

Three rules from earlier rounds bind this WP. An eval of usefulness to an
agent needs real agents, with model and effort as variables, and a
deterministic proxy measures nothing. A registered round is not
authorisation to run its cells: the session offers a costed menu and runs
what is picked. And a declared field with no reader is a claim, so which
numbers of `report` the agents read decides which stay.

The v1.3 round 1.1 cost $38.39 for eight cells and is the price anchor.

### The tasks

Stated as a chemist would, from the 21 phases in
`tests/data/polyhedra_phases.json`, every one COD-cited and so public:

1. Rutile's edge-sharing TiO₆ chains, seen down c.
2. One layer of gypsum with its water, seen edge-on.
3. Calcite's CO₃ groups alone, no Ca, no polyhedra.
4. NAC's AlF₆ octahedra as a 2×2×1 block.
5. LaB₆'s B₆ octahedra without the La–B sticks.
6. Fluorapatite down c for print, 17 cm at 300 dpi, with a legend.

### The conditions

- **Before**: the WP-1470 tree. The agent has `render_structure`, the
  dict, and the manual as it was. Cuts and extents must be done by hand.
- **After**: the WP-1503 tree.
- **Fixed**: WP-1529's merge, `1b837e03` (`PROTOCOL.md` § Amendment 1.3).
  Round B's three fixes: the skill names figures, no bare polyhedron centre
  outside the cell, and `dangling_bonds` counts `hidden=` stubs.
- Sonnet and Opus, at the default effort, three repeats each.
- The agent gets the skill and a shell, and nothing staged in its folder.

### The scores

- Done or not. An Opus judge reads the final picture against a rubric per
  task, and the maintainer spot-checks every "done".
- Renders taken, and the size of each.
- Tokens and wall time.
- Which fields of `report` were read, from the trace.
- Where the agent stalled, in one line per run.

### Where it lives

`docs/wp/1504-eval/` holds the harness, the rubric and the run log. A
condition is enforced in a shim, never in the prompt.

### Inherited

From **WP-1533** (2026-10-02). `FigureReport.stacked` is the part of
`hidden` that sits behind an atom of the same site, within a quarter of its
drawn radius. One cell down a cell axis reads 0.53 hidden and 0.53 stacked
on HKUST-1, 0.52 and 0.50 on ZSM-5, and 1.00 and 1.00 on YBa₂Cu₃O₇. NAC's
opening view reads 0.18 and 0.00. The skill's rule now reads
`hidden - stacked` and keeps a view the task named. `view="auto"` still
ranks by `hidden`, stacking included, so it prefers an oblique view to an
axis projection. Whether it should rank by occlusion is an agent question,
because the change moves every default `auto` pick. WP-1531 and WP-1533
also added `cell=`, `stick=`, `max_atoms=`, `fig.to_px`, the label overlap
counts and `cut["atoms"]`. A round run after their merge measures a
different surface from the fixed round.

From **WP-1536, 1537 and 1538** (filed 2026-10-02, queued). They add `.svg`,
`.pov` and `.glb` to `render_structure`'s `path=`, and an
`ambient_occlusion=` option. None has landed. A round run after any of them
measures a larger surface. Task 6 (fluorapatite for print) is the one an
agent could then answer with an SVG.

## Non-goals

- Running it in CI.
- A leaderboard or a published benchmark.
- Any figure on data without a peer-reviewed citation.

## Tasks

- [x] The harness: a shim per condition, the six task prompts, the rubric,
  the trace parser for `report` reads. `docs/wp/1504-eval/`: `PROTOCOL.md`
  (registered 2026-10-01), `run.py`, `fig_trace.py`, and
  `reference_figures.py` for checking the judge before it scores a run.
- [x] A costed menu to the maintainer before any cell runs. `run.py --menu`;
  2026-10-01 the maintainer picked J (the judge on the reference figures)
  and A (the gypsum pilot, after, one run per model).
- [x] The before round, on the picked cells. Round B, 2026-10-01: one run
  of every cell under 1.2, interleaved with the after round.
- [x] The after round, on the same cells. Round B, the same 28-run batch.
- [x] The table in this file's handover, and one line per `report` field:
  read or never read. For round B, in the 2026-10-01 round B entry.
- [x] The cuts pushed into 1501 to 1503's `### Inherited`, and 1505's
  trigger rated. Superseded in part, 2026-10-01: 1501-1503 are closed and
  take no `### Inherited`, so round B's three fixes are filed as WP-1529.
  1505's trigger rated 2026-10-01 after the fixed round: not fired (the
  round C entry).
- [x] The fixed condition: amendment 1.3, `run.py prepare ROOT fixed`, and
  the two inherited checks on `reference_figures.py`'s helpers.
- [x] The fixed round, on the picked cells. 2026-10-01: the maintainer
  picked B, one run of each of the 14 fixed cells; 13 done.

## Acceptance

- Every run's picture, trace and score are in `docs/wp/1504-eval/`.
- The handover states, per task and model, done or not before and after,
  with renders and tokens as ranges.

```sh
.venv/bin/python docs/wp/1504-eval/run.py --menu
```

## References

- The v1.3 record, round 1.1, for the harness pattern and the cost.
- The agent skill's `references/api-figure.md`.

## Handover log

### 2026-10-04 (round E) — before against fixed at N = 3

The direction round C showed holds at three runs a cell. With the fixed
surface, agents finished 40 of 42 figure tasks. On the surface before
WP-1501-1503 they finished 25 of 42. Fluorapatite went from 0 of 6 to 6 of 6.
The one fixed miss is the agent's, not the package's: it turned off boundary
images, left bonds pointing into empty space, and did not re-read the report
that counts them. So this round found no new defect in the figure surface,
which is what WP-1505's trigger waited on. The maintainer picked option E on
2026-10-03, and it cost $21.28 against the menu's $13-33.

*Measured* (darwin, `claude-sonnet-5-5` and `claude-opus-5-5`, protocol 1.3,
repeats 2 and 3 of every `before` and `fixed` cell, so 56 runs; done-rates
recomputed from the committed `score.json` files):

| | before | fixed |
|---|---|---|
| Sonnet, N = 3 | 9/21 | 19/21 |
| Opus, N = 3 | 16/21 | 21/21 |
| both | 25/42 | 40/42 |

- By task, both models (k/6), before → fixed: rutile 3 → 6, chains 5 → 6,
  gypsum 2 → 4, calcite 6 → 6, nac 3 → 6, lab6 6 → 6, fap 0 → 6.
- Round B's single `before` run undercounted that condition (Sonnet 2/7 in
  repeat 1, 7/14 in repeats 2-3). The gap to `fixed` holds at N = 3.
- Routes: the rietx skill was invoked in 42/42 fixed runs and 4/42 before.
  Sonnet on `before` drew by hand in 11 of 21 runs. `keep` was called in
  30/42 fixed runs.
- `fig.report` reads, of 42 fixed runs: the whole report 42, `empty` 9,
  `hidden` 6, `dangling_bonds` 6, `hidden_atoms` 3; `label_overlaps`, `cut`,
  `note` and `warnings` never.
- Spend: agents $16.60, judge $4.69. Agent time 50.0 min; 68 min wall,
  serial. The 56 run records are 9.0 MB, and `runs/` is now 16 MB.
- The ten misses: nine are `before` runs, in classes round B named
  (fluorapatite's bare P ×4, `hidden=` stubs, the 1.2 block wording) or drawn
  by hand (×3). The tenth is gypsum-fixed-sonnet-3: `boundary=False` on an
  `extent` block, `report.dangling_bonds` 48 against 0 at the default,
  reproduced by script. `references/api-figure.md` states the behaviour and
  the agent read it. No verdict is disputed; two are marginal
  (gypsum-before-sonnet-3, nac-before-sonnet-2).

*Done.* The 56 runs, committed under `runs/`. The `render_structure`
docstring now says what `api-figure.md` says, that `boundary=False` keeps
the bonds to the images it leaves out. WP-1505's trigger re-rated (its
Inherited and Priority line). The round ran as a lane from a cleanup session.

*Deviations, recorded rather than amended.* The Claude Code version moved
during the round. Repeat 1 of every cell ran on 2.1.286, the version
PROTOCOL.md names. Runs 1-36 of this round ran on 2.1.288 and runs 37-56 on
2.1.289, after an auto-update at 23:13 UTC; each transcript's `version`
field says so. And `run.py:492`'s regex for skill files read needs the whole
path in one token, so it misses `cd …/references; cat api-figure.md`. The
scores' `skills.files` is a lower bound: a transcript search finds
`api-figure.md` in 42 of 42 fixed runs, where the score counts 36.

*Next:* (1) the maintainer spot-checks the fixed figures,
`open docs/wp/1504-eval/runs/*-fixed-*/figure.png`. (2) Then close: the result
for 1501-1503 is in their Inherited from round B, and E changes none of it.

### 2026-10-01 (round C) — the fixed condition, one run a cell

With WP-1529's three fixes in place, agents finished 13 of the 14 figure
tasks, against 9 of 14 on the previous surface and 6 of 14 on the original.
Every run now opened the rietx skill and drew with rietx. Under round B,
Sonnet drew by hand in 8 of 14 runs. Fluorapatite failed in all four earlier
runs. Both Opus runs there failed on rietx's own bare phosphorus, and both
Sonnet runs drew by hand. On `fixed` it passed on both models. This is
still one run a cell. And the condition changed two things at once: the
skill's description, which decides the route, and the drawing itself. So it
is a strong direction. The N = 3 option on the menu is what would make it a
result. The round cost $5.05.

*Measured* (darwin, Claude Code 2.1.286, `claude-sonnet-5-5` and
`claude-opus-5-5`, N = 1 a cell, protocol 1.3; `run.py table`, fixed rows
only; before and after are the round B entry's):

| task | model | done | renders | looks | tokens (k) | minutes | $ |
|---|---|---|---|---|---|---|---|
| rutile | sonnet | 1/1 | 2 | 1 | 207 | 0.3 | 0.14 |
| rutile | opus | 1/1 | 2 | 1 | 176 | 0.3 | 0.24 |
| chains | sonnet | 1/1 | 4 | 2 | 357 | 0.5 | 0.20 |
| chains | opus | 1/1 | 4 | 4 | 291 | 0.7 | 0.33 |
| gypsum | sonnet | 0/1 | 4 | 2 | 317 | 0.5 | 0.19 |
| gypsum | opus | 1/1 | 11 | 4 | 417 | 1.3 | 0.41 |
| calcite | sonnet | 1/1 | 4 | 2 | 209 | 0.3 | 0.15 |
| calcite | opus | 1/1 | 3 | 2 | 243 | 0.5 | 0.27 |
| nac | sonnet | 1/1 | 5 | 2 | 358 | 0.6 | 0.20 |
| nac | opus | 1/1 | 5 | 3 | 410 | 0.8 | 0.37 |
| lab6 | sonnet | 1/1 | 6 | 3 | 579 | 1.2 | 0.32 |
| lab6 | opus | 1/1 | 2 | 2 | 311 | 0.7 | 0.36 |
| fap | sonnet | 1/1 | 4 | 2 | 321 | 0.6 | 0.22 |
| fap | opus | 1/1 | 5 | 4 | 490 | 1.1 | 0.44 |

- Done by model: Sonnet 2/7 before, 4/7 after, 6/7 fixed. Opus 4/7, 5/7,
  7/7.
- The rietx skill was invoked in 14 of 14 fixed runs, and
  `references/api-figure.md` read in 13. Every run called
  `render_structure` (2-11 renders), and 10 of 14 called `keep`.
- The one miss, gypsum on Sonnet: the outer rows of water had O bonded to
  one H. Every other criterion passed.
- `fig.report`, in how many of the 14 fixed runs each field was read: the
  whole report printed in 14; `hidden` 1, `hidden_atoms` 1, `empty` 2;
  `dangling_bonds`, `label_overlaps`, `cut`, `note` and `warnings` never.
  As in round B, agents print the report whole.
- Spend: agents $3.85, judge $1.20, 9.3 minutes of agent time.
- The record grew 2.6 MB for 14 runs (about 186 KB a run), and `runs/` is
  6.9 MB.
- I looked at all 14 figures on one contact sheet and disputed no verdict.
  That is not the protocol's spot check, which is the maintainer's.

*Done.* Amendment 1.3 in `PROTOCOL.md`: the `fixed` condition at `1b837e03`,
1.2's runs pooled with 1.3's (`POOLED`), each condition's references drawn
apart, and option E on the menu. `prepare ROOT fixed` passed its instrument
check. The inherited note is folded into Context and Tasks and deleted.

The inherited checks, answered in the amendment:
- `without_bare_centres` no longer changes any picture on `fixed`. The dict
  still holds the 2, 4 and 8 bare centres, and the renderer leaves them out.
- `carbonate_groups` still does. `keep` of all but Ca leaves 96 O, 60 of
  them in no carbonate.
- Calcite drew 8 bare Ca on the after surface (132 atoms drawn against 124),
  which corrects amendment 1.2's "none".
- All seven right reference figures are pixel-identical between `after` and
  `fixed`. Four defaults changed, and each still misses a criterion the fix
  does not touch, so the judge check stands without being asked again.

*WP-1505's trigger, rated: not fired.* Its second clause wants the surface
unchanged between this WP's rounds, and round B led to WP-1529 changing it.
Its first wants a real user or agent task, and these tasks are the round's.
A round on `fixed` that finds no new defect would be the first pair of
rounds with the surface unchanged between them. Recorded in 1505's
`### Inherited`.

*Gotchas.*
- `fixed` changes the route and the drawing together. Rutile on Sonnet failed
  with 0 renders before and after, and passed with 2 on `fixed`, so the route
  is most of it. N = 1 cannot separate the two.
- The worktree guard refuses a heredoc. Edits to `run.py` went through a
  scratchpad script.

Next, in order. (1) The maintainer spot-checks the 13 dones, at
`runs/*-fixed-*/figure.png`. (2) Pick from `run.py --menu`: E runs before
against fixed at N = 3 (56 runs, $13-33 measured), which is the
result-bearing comparison. Or close the WP on N = 1 as a direction, if that
is enough for 1501-1503's keep-or-cut decision. (3) If E runs and turns up no
new defect, re-rate 1505's trigger from that.

- **2026-10-01** (round B, same session) — Every cell has now run once under
  1.2: 28 runs at $11.19, 37 minutes of agent time. With the new surface the
  agents finished more of the tasks, 9 of 14 against 6 of 14 before. That is
  one run a cell, so it is a direction and not yet a result. Three things
  look solid already. The rietx skill almost never reaches a figure task,
  because its description speaks only of refinement. Sonnet drew by hand in
  matplotlib in 8 of 14 runs and finished one task that way. And both Opus
  runs on fluorapatite failed on a defect
  in rietx itself: one cell draws phosphorus atoms without their tetrahedra.

  *Measured* (darwin, Claude Code 2.1.286, `claude-sonnet-5-5` and
  `claude-opus-5-5`, N = 1 a cell, interleaved before and after):

  | task | model | condition | done | renders | looks | tokens (k) | minutes | $ |
  |---|---|---|---|---|---|---|---|---|
  | rutile | sonnet | before | 0/1 | 0 | 1 | 76 | 0.6 | 0.08 |
  | rutile | sonnet | after | 0/1 | 0 | 1 | 83 | 0.4 | 0.08 |
  | rutile | opus | before | 0/1 | 3 | 7 | 375 | 2.1 | 0.52 |
  | rutile | opus | after | 1/1 | 2 | 2 | 379 | 1.8 | 0.42 |
  | chains | sonnet | before | 0/1 | 0 | 1 | 83 | 0.5 | 0.09 |
  | chains | sonnet | after | 1/1 | 0 | 3 | 158 | 0.8 | 0.13 |
  | chains | opus | before | 1/1 | 2 | 2 | 302 | 1.7 | 0.36 |
  | chains | opus | after | 1/1 | 4 | 4 | 274 | 1.1 | 0.29 |
  | gypsum | sonnet | before | 0/1 | 0 | 3 | 129 | 1.6 | 0.13 |
  | gypsum | sonnet | after | 0/1 | 0 | 5 | 347 | 1.2 | 0.28 |
  | gypsum | opus | before | 0/1 | 7 | 5 | 431 | 2.0 | 0.48 |
  | gypsum | opus | after | 1/1 | 2 | 2 | 296 | 1.2 | 0.37 |
  | calcite | sonnet | before | 1/1 | 5 | 5 | 308 | 1.6 | 0.20 |
  | calcite | sonnet | after | 1/1 | 4 | 3 | 243 | 0.5 | 0.16 |
  | calcite | opus | before | 1/1 | 3 | 2 | 489 | 1.8 | 0.50 |
  | calcite | opus | after | 1/1 | 1 | 1 | 184 | 0.8 | 0.23 |
  | nac | sonnet | before | 0/1 | 2 | 2 | 300 | 1.1 | 0.21 |
  | nac | sonnet | after | 1/1 | 5 | 3 | 296 | 0.9 | 0.20 |
  | nac | opus | before | 1/1 | 3 | 3 | 563 | 1.6 | 0.58 |
  | nac | opus | after | 0/1 | 6 | 5 | 481 | 1.8 | 0.49 |
  | lab6 | sonnet | before | 1/1 | 2 | 2 | 414 | 1.6 | 0.27 |
  | lab6 | sonnet | after | 1/1 | 2 | 2 | 348 | 0.9 | 0.22 |
  | lab6 | opus | before | 1/1 | 4 | 4 | 509 | 2.0 | 0.47 |
  | lab6 | opus | after | 1/1 | 3 | 3 | 408 | 1.7 | 0.43 |
  | fap | sonnet | before | 0/1 | 0 | 2 | 251 | 1.0 | 0.20 |
  | fap | sonnet | after | 0/1 | 0 | 3 | 211 | 1.0 | 0.21 |
  | fap | opus | before | 0/1 | 3 | 4 | 360 | 1.8 | 0.55 |
  | fap | opus | after | 0/1 | 5 | 4 | 692 | 2.1 | 0.61 |

  Done, by model and condition: Sonnet 2/7 before and 4/7 after; Opus 4/7
  before and 5/7 after. Every Opus run used `render_structure`, and 3 of 7
  Sonnet runs in each condition did. The judge cost $2.42 for 28 verdicts.

  `fig.report`'s fields, in how many of the 14 after-runs the agent read
  each:
  - `hidden`: 1
  - `hidden_atoms`: never read
  - `dangling_bonds`: 1
  - `label_overlaps`: never read
  - `empty`: 1
  - `cut`: never read
  - `note`: never read
  - `warnings`: 1
  - the whole report printed: 10 (Opus 7, Sonnet 3)

  So agents print the report and read it, rather than pick fields. Field-level
  "never read" therefore says little: a printed report puts every field in
  front of the agent.

  *Routes.* The skill was opened in 5 of 28 runs. Its description reads
  "Refine powder diffraction data … whenever a task involves a powder pattern,
  a CIF to fit against one …", the same in both trees, and names no figure.
  Opus found the figure functions by listing the package and reading
  `figure3d`'s source and signatures. Sonnet drew by hand in 8 runs, 4 of
  them after loading Claude Code's built-in `dataviz` skill, and finished one
  of those 8 (chains, after). On the after surface: `view="auto"` in 6 runs,
  `keep` in 9, `build(extent=)` in 6. The stall lines (R6) are derived from
  each score's route and the judge's reasons, and marked so.

  *Why runs failed.* The "polyhedra are whole" check failed or was unclear in
  9 of 13 not-done runs. In both Opus fluorapatite runs it caught the bare P
  that rietx's own single cell draws. Three hand-drawn runs were clipped by
  the frame. Two runs failed only on "unclear" for a task criterion (gypsum
  edge-on, NAC's block), and both used the renderer.

  *Gotchas.* The record is 4.4 MB for 28 runs (about 157 KB a run), so C's
  further 56 runs would add about 9 MB.

  Next, in order. (1) Item 6, which needs the maintainer. The evidence points
  at three rietx changes before any further round: name figures in the
  skill's description; stop a single cell drawing bare centres, or give a
  verb that removes them; and let `dangling_bonds` count `hidden=` stubs. Each
  would change what the round measures, so C on the current trees answers a
  question about a surface that is about to change. (2) Rate 1505's trigger
  from this table, or after C. (3) A round after those fixes would need its
  own commit pinned as a third condition.

  The maintainer chose to fix first, and the three fixes are filed as
  WP-1529. This WP waits on it: the next round runs on 1529's merge as a
  third condition, and the before and after records here stay as they are.
- **2026-10-01** (after the handover below, same session) — Amendment 1.2 is
  written. At the maintainer's question, the round now tests expansion beyond
  one cell properly, and it checks two figure defects nothing caught before.
  The new seventh task asks for one rutile chain, four cells long, seen from
  the side. Every figure is now also checked for bonds ending in empty space,
  and for atoms drawn without their polyhedron. The second check found that
  one cell of rutile or fluorapatite already draws such bare atoms, and that
  the figure's report cannot see a stub left by `hidden=`. No run has used
  1.2 yet, and the judge must be checked again before one does.

  *Measured* (after surface, `[dev]`, darwin): `hidden=("Ca",)` leaves the O
  half of every Ca–O bond drawn while `report.dangling_bonds` reads 0. One
  cell draws 2 Ti bare in rutile and 4 P bare in fluorapatite, and 0 in NAC,
  gypsum, calcite and LaB₆. `keep` drops a polyhedron missing a corner and
  never draws part of one. One rutile chain by `component(via="edges")` and
  `keep` gives 4 Ti and 4 octahedra, and `complete=True` adds 22 bare Ti.
  The figures are in `PROTOCOL.md` § Amendment 1.2.

  *Done.* `run.py`: the `chains` task, two common criteria, the judge's
  `--setting-sources`, `PROTOCOL_VERSION` 1.2, pilot costs beside the prior
  in the menu. `reference_figures.py`: rutile and fluorapatite drop their
  bare centres, calcite keeps whole carbonate groups, and chains is new.
  `fig_trace.py`: comments only, copied into both venvs. The 1.1 pilot moved
  to `pilot-1.1/`, and the 1.1 judge check to `references-1.1.json`.

  *Gotchas.* Two findings belong to item 6, the cuts. No verb removes bare
  centres and no report field counts them. And `dangling_bonds` is blind to
  `hidden=` stubs by its own docstring. Both may be rietx defects rather than
  agent errors, and the round will show whether agents trip on them.

  The maintainer then picked J. The judge agreed on 12 of 14 ($1.16), and the
  two misses were "unclear" on right figures. Down c, NAC's block has one
  square outline and shows no cell count. Fluorapatite's flat legend swatches
  match no shaded sphere. Both criteria were reworded, and NAC's reference
  moved to the opening view (`PROTOCOL.md` § 1.2's judge check). The re-check
  of those four agreed, for $0.32. So the judge agrees on 14 of 14 under 1.2
  ($1.48), and the session's spend is $5.27.

  Next: bring `run.py --menu` to the maintainer for A (the 1.2 pilot) or B.
- **2026-10-01** — The harness for the figure round is built and checked end
  to end, and no round has run yet. The Opus judge reads a picture as the
  rubric needs: it passed all six right reference figures and failed all six
  defaults. The first pilot found that a user-level figure skill on the
  maintainer's machine can take a run off rietx entirely. So every run now
  launches without user-level skills (amendment 1.1). Under 1.1 the gypsum
  pilot split. Opus drew the layer with the new extent and cut verbs in under
  a minute for $0.25. Sonnet never opened the rietx skill and drew it by hand
  in matplotlib. That is one run each, so it is a question for the round and
  not yet an answer.

  *Done.* Items 1 and 2. `docs/wp/1504-eval/`: `PROTOCOL.md` (registered,
  then amendment 1.1), `run.py`, `fig_trace.py`, `reference_figures.py`,
  `references.json`, `pilot-1.0/`, `runs/`. Both conditions are prepared at
  `~/rietx-agent-runs/2026-10-01-wp1504-figure` (before `5304b85a`, after
  `97c1d9cc`), and each passed `prepare`'s instrument check. The maintainer
  picked J + A from the menu, then A again under 1.1.

  *Measured* (darwin, Claude Code 2.1.286, `claude-sonnet-5-5` and
  `claude-opus-5-5`; the harness's own venv `[dev]`):
  - Judge check (J): 12 of 12 agree with the reference, $1.30.
  - Pilot under 1.0, kept apart and pooled with nothing: Sonnet not done
    ($0.21, 0.8 min, no render, loaded `yue-figure-style` first and never
    imported rietx); Opus done ($1.42, 5.3 min, 11 renders, loaded `rietx`
    and `yue-figure-style`).
  - Two Haiku probes of `--setting-sources project,local`, $0.03: the six
    user-level skills drop out, while the workspace's `rietx`, the built-ins
    (`dataviz` among them) and the user `CLAUDE.md` still load.
  - Pilot under 1.1 (`run.py table`):

    | task | model | condition | done | renders | looks | tokens (k) | minutes | $ |
    |---|---|---|---|---|---|---|---|---|
    | gypsum | sonnet | after | 0/1 | 0 | 4 | 191 | 1.0 | 0.20 |
    | gypsum | opus | after | 1/1 | 4 | 2 | 233 | 0.8 | 0.25 |

    The Opus run read `hidden`, `dangling_bonds` and `empty`, and printed the
    whole report three times. Judging the two cost $0.15.
  - Spend this session: $3.79 (judge check $1.30, pilot 1.0 $1.86 with
    judging, probes $0.03, pilot 1.1 $0.60 with judging).
  - Lane trial (`/wp-lanes`): no lane dispatched, because context passed
    150K only after the harness item had begun. Kept items: harness estimated
    45 requests, took 48 (decided at 128K); pilot-1.1 estimated 5, took 5.
    The main session ran 91 requests, peaked at 282K and cost $7.90.
  - Fast selection on the final tree (`[dev]`, darwin): 7311 passed, 159
    skipped, 8:17 with no check for another session's suite. No test was
    added, and `tests.added_test_times` agrees: zero. The full selection did
    not run, because nothing here can move a measured number: the harness
    lives under `docs/wp/` and pytest never collects it.

  *Gotchas.*
  - `render_structure(hidden=("La",))` drops La but leaves the B half of
    every La–B bond as a stub. `keep(g, select(g, element="B"))` drops both.
    It is a candidate for item 6's list, and for a skill line if the round's
    agents trip on it.
  - Relaunching a run name under a new protocol first double-counted it: the
    trace is per condition, and both launches logged under the bare name. A
    launch now keys its rows by run and session, read inside the session's
    window.
  - The menu's per-run price is still the prior until a model has two 1.1
    runs. The 1.1 pilot's $0.20 and $0.25 sit well under it.
  - The committed record runs about 140 KB a run (figure at 800 px, trace,
    trail), so option C adds about 10 MB to the repository.
  - A trail's last lines (refinement seconds, per-process floor) are round
    1.1's read-outs and mean nothing here. Each `score.json` holds this
    round's.

  *Review* (`/code-review high --fix`): ten findings, seven fixed in one
  commit. The fixes cover first reads from a process killed before its exit
  row, path containment in place of a string prefix, a judge verdict compared
  case-blind, two guards, and `check()` now holding the launch flags to
  `PROTOCOL.md`. None moved a committed score. Three were declined, each
  needing an amendment. (1) The judge launches without `--setting-sources`.
  All 16 judge sessions so far used `Read` alone and invoked no skill, so
  every verdict on record stands. (2) Two comments in `fig_trace.py` are
  stale: `_short` records a rotation in full, and `RIETX_FIG_RUN` now holds
  `run@session`. The prepared venvs hold a copy of the shim, so editing it
  would part the record from what ran. (3) The registered text says
  `RIETX_FIG_RUN` names the run.

  Next: write amendment 1.2 before any more runs: the judge gains
  `--setting-sources project,local`, and the two shim comments and the
  `RIETX_FIG_RUN` wording are corrected. The flag changes the judge's launch,
  so offer J again ($1.30) with the menu. Then bring `run.py --menu` to the
  maintainer. B (one repeat of
  every cell, 24 runs) comes before C, because N = 1 per cell already says
  whether Sonnet bypassing the skill is general or a gypsum quirk. Then the
  table, one line per `report` field, and the cuts.
- **2026-09-27** — filed from the session that closed WP-1470. Next: wait
  for 1503; then write the harness and bring the menu.
