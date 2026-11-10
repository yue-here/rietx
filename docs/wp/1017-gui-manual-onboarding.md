# WP-1017 — GUI manual, in-app help, onboarding

Milestone: v1.2 · Status: ✅ 2026-08-28 — three chapters in Part 1, the routes
and the panels partitioned, generated light/dark screenshots, a derived
first-run checklist, and the GUI's beta status lifted (its routes stay
provisional)
Depends on: WP-1201…WP-1217 (last in v1.2: the chapters describe panels those
WPs settle, and the beta declaration lifts here)

## Goal

The GUI is documented where the theory manual lives, helps from inside the
app, and onboards a first-year PhD student without a wizard that hides the
real UI.

## Re-scoped 2026-08-25: the manual, and the mechanism that keeps it true

Deferred on 2026-08-14 because the GUI kept moving (eight sessions had
written "three sentences in this manual are now wrong" into the mailbox
below). It returns as the **last** WP of v1.2, after the seventeen panel WPs
(1201-1217) settle what it describes. Two things changed in the scope.

**The manual gets a sync mechanism, not only chapters.** The user's ask:
"we need a method of keeping all the manuals in sync with the code". Prose
about behaviour cannot be checked mechanically; names, vocabularies,
constants and pictures can, and the chapters are written so that everything
checkable is checked:

- **Descriptions have one authority.** Every parameter, flag, stage field
  and wizard field is described in the help corpus (`rietx.help`, WP-1202);
  the GUI popover renders it and `docs/manual/using/glossary.md` is
  generated from it. A chapter links to a glossary entry; it never restates
  one.
- **Routes are partitioned.** Every route in `gui/server.ROUTES` is named in
  a GUI chapter or excluded with a reason, the `tests/api_surface.py`
  pattern; a new route fails the partition until documented.
- **Panel and tab names are a corpus.** vitest writes `tests/data/gui/
  panels.json` from the live tab strip and pytest asserts every chapter
  names each, the fnmatch mechanism in the other direction.
- **The `.rxt` grammar quotes the parser.** `FORMAT_VERSION` and
  `VALUE_DIGITS` are fenced constants; the keyword table is injected from
  `textdoc._KEYWORDS`, already pinned to `lib/rxt.ts`.
- **Screenshots are generated.** `docs/manual/make_screenshots.py` drives
  playwright over the shipped example projects (WP-1204), light/dark pairs,
  the `make_figures.py` rule; a test asserts every screenshot a chapter
  references is one the script produces, so a moved control is a stale
  picture the build can name.

**In-app help is not this WP's any more.** The `static/help.json` and
tooltip wiring the original scope carried landed as the corpus (1202) and
the popover (1203); what remains here is the "learn more" anchors' dead-link
guard being green over the finished chapters, and the first-run checklist.

The mailbox was left for the session that picked this up, per its own rule:
prune it against the running app, not against the notes. That was done on
2026-08-28 and the result is § The mailbox, consumed.

## Context

- **Inside `docs/manual/`** — same Sphinx/MyST/furo tree, same `-W`, same
  guards (`tests/test_manual.py`); a separate doc root would need its own
  guard set for no benefit. Three layered chapters matching the audience
  gradient:
  - `gui-quickstart.md` — install (`pip install rietx[gui]`) → open →
    fit → read the report.
  - `gui-guide.md` — panel by panel, including *when to branch* (the
    history worktree is the differentiator; teach the workflow, not just
    the buttons).
  - `gui-power.md` — the **normative `.rxt` text-format spec**,
    keyboard/palette, and the console-to-script transition — the API-echo
    story as the on-ramp to the Python API.
- The manual's anti-divergence rules apply and are executable
  (`tests/test_manual.py`): fenced constants are MyST substitutions
  injected from the live package in `docs/manual/conf.py` — **the rxt
  format version becomes a fenced constant injected from
  `gui.textdoc.FORMAT_VERSION`**, so a format bump that misses the manual
  fails the build. A new fenced constant needs a `conf.py` line *and* a use
  in a chapter.
- In-app help: tooltips from `static/help.json`, each with a "learn more"
  anchor into the built manual; `tests/test_gui_help.py` asserts every
  anchor exists (dead-link guard, same spirit as `test_manual.py`).
- First run: a **non-modal progressive checklist** (Load pattern → Load
  structure → Check instrument → Run → Read the report) — never a modal
  wizard; state in `ProjectDoc.ui`.

### The mailbox, consumed

The `### Inherited` fifteen sessions wrote into this file was pruned to a
verified surface list on arrival (2026-08-28) and then **consumed by the
chapters**: what the app does is in `using/gui-guide.md`, what a chapter has
to teach is in the chapters, and both are now held to the app by
`tests/test_gui_manual.py` rather than by a note. Nothing is owed to a
successor here.

## Non-goals

- No screencasts/video, no hosted docs decisions (that is WP-1003's
  release scope).
- No autodoc API reference (0604's decision stands — a rendered API
  reference is its own document with its own failure modes).
- No restating theory — the GUI chapters link into the existing theory
  chapters rather than duplicating equations.

## Tasks

- [x] `gui-quickstart.md` + toctree wiring; builds `-W`-clean.
- [x] `gui-guide.md` — panel by panel, when-to-branch workflow section.
- [x] `gui-power.md` — normative `.rxt` spec with `FORMAT_VERSION` as a
      fenced constant (conf.py line + chapter use), keyboard/palette table,
      console-to-script story.
- [x] `static/help.json` + tooltip wiring + "learn more" anchors;
      `tests/test_gui_help.py` dead-link guard. **Landed elsewhere**: the
      corpus is WP-1202's `rietx.help` served at `GET /api/help` (not a
      `static/help.json`), the popover is WP-1203, and the dead-link guard is
      `test_help.py::test_every_anchor_resolves_in_the_built_manual`, which
      checks each anchor against the *built* HTML. What was owed here was that
      it stays green over the finished chapters, and it does — the anchors
      point into Part 2, which these chapters did not move.
- [x] First-run progressive checklist (non-modal), persisted dismissal.
- [x] Route partition test (`server.ROUTES` documented or excluded with a
      reason) and the panel-name corpus (vitest writes, pytest reads).
- [x] `docs/manual/make_screenshots.py` over the shipped examples +
      the referenced-screenshot test; light/dark pairs committed.
- [x] The glossary and every `{ref}` to it from the chapters; lift the beta
      declaration in README and `using/compatibility.md`. The glossary is
      generated from `rietx.help` in `conf.py` (WP-1202); the chapters link it
      rather than restating an entry. Beta lifted in README, `using/cli.md`
      (whose admonition said the GUI "is not documented here", which is no
      longer true) and `using/compatibility.md` — where the entry now says the
      **routes** are provisional rather than the application, since it is the
      wire that still moves.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_gui_help.py \
    tests/test_gui_manual.py tests/test_manual_api.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-0604's manual architecture (fenced constants, `*Source:*` lines,
  cited-bib guard) — the machinery these chapters extend.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**The manual is held to this app, and two of its vocabularies by test**
(WP-1017, `docs/docs/**/gui-*.md`, `tests/test_gui_manual.py`). The GUI is
documented and no longer beta; its **routes stay provisional by declaration**,
which is the half of that status the chapters did not retire. Four rules.
**Routes and panel names are partitioned** the way `tests/api_surface.py`
partitions the call surface — every route documented in a chapter or excluded
with a written reason, every tab in the strip named — and each tightens **both
ways**, so a chapter naming a route the server does not serve fails too: that is
WP-1037's bug pointed at the reader. **Where no python object knows the fact,
the authorities swap**: nothing here knows the panels exist, so the strip is
data in `lib/tabs.ts`, `tabs.test.ts` writes `tests/data/gui/panels.json` and
pytest reads it — the fnmatch mechanism run backwards, and it keeps the python
suite node-free. **A screenshot is generated**, by `docs/docs/
make_screenshots.py` driving this server in-process over a shipped example;
that script is the one authority for how each was taken, its `SHOTS` table is
what a chapter may reference, and a picture is judged by **looking at it** —
never by a digest, which a re-render breaks. Note `*.png` in `.gitignore` has
swallowed a committed image family three times now, so the negation is asserted
rather than remembered. And **a first-run aid states what is true, not what was
remembered**: the checklist's steps are derived from the project, so an undone
fit un-ticks `Run`, and only the dismissal is persisted — nothing is written
when the last step completes, because a surprise write is the wrong thing to do
during a first session.

## Handover log

- **2026-08-28** — **the GUI has a manual, and the manual has guards that fail
  when the app moves.** A person who has never opened `rietx gui` can now read
  three chapters and know what the screen is for: how to get from nothing to a
  fit they have read, what each of the nine panels does and why it behaves as
  it does, and — the part the screen cannot say about itself — when to branch
  the history, why only one of the two knob strips under the plot changes the
  answer, and why an edit empties the plot on purpose. The GUI stopped being a
  beta feature with it. What this cost is a set of mechanisms rather than
  prose: the eight sessions that wrote "three sentences in this manual are now
  wrong" into the mailbox below were not writing badly, they were writing
  against a moving target with nothing to catch the drift, so the routes and
  the panels are now partitioned like the call surface and the screenshots are
  generated by a script that is their one authority. A control that moves now
  fails a test.

  **Done** — all eight checklist items. Three chapters in Part 1
  (`gui-quickstart`, `gui-guide`, `gui-power`), between `cli` and `agents`, so
  they inherit `test_manual_api.py`'s name resolution and executed-block guards
  rather than needing a doc root of their own. `tests/test_gui_manual.py` is
  the new guard file: the 77 routes are documented-or-excluded and the
  partition tightens both ways (a chapter naming a route the server does not
  serve fails too), every tab in the live strip is named in a chapter, every
  referenced screenshot is one the script declares and every declared one is
  committed and shown, and nothing gitignores them. The tab strip moved to
  `gui/src/lib/tabs.ts` as data so `tabs.test.ts` can write the corpus python
  reads. `docs/manual/make_screenshots.py` drives the real server in-process
  over the `fap` example, 18 committed light/dark pictures. The first-run
  checklist is a non-modal strip whose steps are derived from the project, with
  only its dismissal persisted. Beta lifted in README, `using/cli.md` and
  `using/compatibility.md` — narrowed rather than dropped: the **routes** stay
  provisional, since the wire is what still moves.

  **Measured** (this worktree's own `[dev]` venv, numpy-only, darwin/arm64,
  nothing else running — `pgrep` checked): fast selection **3206 → 3216
  passed, 122 skipped** in 2:10, the baseline being WP-1217's own figure on
  this machine. Exactly +10, which is the 10 tests `test_gui_manual.py` adds,
  all passing and no new skip. vitest **583 → 591** in 22 files: +2 for the
  panel corpus, +5 for the checklist's mount tests, +1 for the review pass's
  regression. `svelte-check` 378 → 381 files, 0 errors. **The full selection was not run**: this WP touches
  docs, `gui/`, the committed dist and tests, and no physics, which is
  `tests/CLAUDE.md`'s stated exemption. Screenshots are 2.7 MB after the
  script's own 256-colour quantise, from 5.2 MB — checked by looking at them,
  not by a digest, which is `gui/CLAUDE.md`'s rule for a picture.

  **The review pass** raised eleven and ten were real. Seven landed as offered
  (a lexicographic sort that made "newest chromium" mean oldest, an unguarded
  `shot.tab` that would block for 30 s, a route table crediting `/api/settings`
  with the recent list, a shot-name prefix match, a leaked descriptor, a server
  left running on a mid-pass failure, a dead spec lookup). The best of them was
  this WP's own thesis turned on it: the Rwp maturity threshold was typed as a
  literal `0.35` in two chapters while `MATURITY_MAX_RWP` is its authority, so
  it is a substitution now. **One fix was moved rather than taken** —
  `reportSeen = false` was put in `readUi()` on the grounds that it runs on a
  project load and nothing else, and it does not: `moved()` calls it on every
  head move, so reading the report and then checking a node out un-ticked the
  step just finished. The bug was real (the flag survived into a different
  project); the reset belongs beside `tab = "params"`, and a regression test
  drives a real checkout, made to fail against the misplacement first. The
  eleventh is declined and recorded: "a column of nine tabs" is a literal count
  in two chapters, the corpus guards the labels but not the count, and there is
  no injection mechanism for TypeScript data in the manual — a tenth panel
  would leave both sentences wrong with everything green.

  **Gotchas for whoever is next.** The screenshot script needs `playwright`
  installed by hand (deliberately not in `[dev]` — nothing else wants it and no
  docs build runs it) and drives whatever chromium is already in playwright's
  cache, since a revision mismatch is the normal state of this machine. Its
  `SHOTS` table is the declaration the tests read; adding a picture means
  adding a row *and* showing it in a chapter, and both directions fail. Two
  traps are recorded in the code because they cost real time here: `*.png` in
  `.gitignore` swallowed the whole screenshots directory — the third committed
  image family that rule has eaten, now a test rather than a comment — and the
  driver's phase field started as three independent booleans, which let one
  shot match two passes and be photographed twice, the committed file being the
  wrong screen entirely.

  **Next**: v1.2 is complete — this was its last WP. The milestone record wants
  finishing with its measured acceptance block, and then v1.3 (agents and
  programs, 1301-1307) opens with the version bump, which is the order the
  ROADMAP already states. Nothing in this WP blocks either.

- **2026-08-25** — re-scoped as the last WP of v1.2 (the GUI milestone):
  the chapters keep their shape, the sync mechanism above is added, and
  in-app help moved to WP-1202/1203. Milestone field, Depends line and the
  ROADMAP row (now in § v1.2) synced. The mailbox is untouched on purpose.
  Next: nothing until 1201-1217 land.
- **2026-08-14** — **deferred past the public release** (user decision): the
  GUI ships as a beta feature and gets its manual once the panels settle.
  Done: Status line, milestone field and the ROADMAP row moved to a new
  "Post-v1.0" section (shared with 1067, whose § Floor still gates the
  release); § Deferred added above with the grounds and the two hand-offs. Next: nothing here until post-release — the successor is
  [1067](1067-user-api-manual.md), which carries the README's beta
  declaration and the one-line `rietx gui` mention, and 1003, whose
  `### Inherited` now records that this WP no longer blocks the freeze.
  Gotcha for whoever returns: the mailbox below was accurate on 2026-08-06 and
  has not been re-read since; treat every "this sentence is now wrong" entry as
  itself possibly wrong, and prune against the running app rather than against
  the notes.
- **2026-07-29** — created from the v1.0 GUI plan.
