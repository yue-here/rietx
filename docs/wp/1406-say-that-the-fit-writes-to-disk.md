# WP-1406 — say that the fit writes to disk

Milestone: unscheduled · Status: ⬜
Depends on: 1403 (the behaviour being documented); 1405 (the sentence the skill
body carries); 1402 (the break being recorded)

## Goal

The track's behaviour changes are written down where each audience reads: a
library user learns that a fit now writes to disk and how to stop it, a person
learns what `rietx watch` shows them, and an agent learns the one fact that
changes how it handles an exception. WP-1403 is not shippable without this.

## Context

Three audiences, three registers, and the house rule that a session's findings
go to three different destinations (WP-1330): a rule an agent *driving* rietx
needs goes in the skill, a rule for *changing* the package goes in a CLAUDE.md,
and a measurement goes in a WP handover. This WP places the first two; WP-1404
already placed the third.

### One clause in the root CLAUDE.md is falsified

> The **run state is not an event** — `EventKind` is closed, so a run's status
> travels beside the stream and `live/events.jsonl` stays the one thing `watch`
> tails.

The **rule** survives exactly: state beside the stream, never an `EventKind`,
and WP-1401's cross-process liveness is that rule carried one rank out. The
**sentence** does not: `watch` reads a run's metadata, its status and its
snapshot as well. Edit it in this change, or the rulebook describes code that
does not exist. Keep the reason, which is the part that matters.

### The manual

- **`using/cli.md`** § `rietx watch` (around line 115) — the no-argument mode,
  the run list, what each liveness word means and especially that **abandoned**
  is a third answer rather than a rounding, the cancel button and what it does
  to the other process, the read-only serving flag. The `rietx --help` block near
  line 16 is a hand-kept copy of `cli.py`'s string: update it too. Nothing
  crosses those two today; a one-line guard would be cheap, but it is not this
  WP's job — note it and move on.
- **`using/files.md`** (around line 187) — the `.rex` tree gains the run
  directories, and a new subsection covers the working directory's `.rietx/`
  with the sentence no test can enforce: it is unrelated to `$HOME/.rietx` and
  **no env var moves it**. Then, plainly, **what a run directory contains** —
  every free parameter's value at every recorded evaluation, and no pattern
  bytes. A reader on a shared filesystem is entitled to that in the manual and
  not in a WP file.
- **`using/refining.md`** § Watching a run (around line 561) — `telemetry=`, the
  env switch, retention by age and size, and the sentence a library user will be
  annoyed not to find: *a fit now writes to disk by default, and here is how to
  stop it.* Put it early in the section, not in a note at the end. Sizes are
  quoted from WP-1404's measured ranges and from nowhere else.
- **`using/compatibility.md`** — the `fit.html` break and the change to
  `<project>/live/`'s contents. The promise is a preview and anything may change
  in any release, but every break is recorded.
- Part 2 is untouched: this track adds no physics, so no equation and no fenced
  constant moves.

### The skill

Its body takes only what holds for **every** fit, and it is capped. Exactly one
new fact qualifies:

> A human may be watching, and may stop you. A `RefinementCancelled` you did not
> request is not a bug in your call: the completed stages are kept, and
> `.completed_stages` and `.node_id` say where the work stands.

That changes error handling in every fit, which is the test for a body line. Per
WP-1330 a body addition is **paid for by a named cut**, and the cap moves only in
a commit that says so — so name the cut in the commit message, not in a comment.

Everything else is a reference behind one routing row, keyed by the situation
rather than the feature: *a human is watching this session, or you need to hand
one a window onto a long run*. It covers how to point a human at the watcher,
what a run directory holds, and how to read a run back afterwards. Every row
carries its `(Measured: …)` or `(Hypothesis: …)` tag, and the file opens with the
header `tests/test_skill.py` pins. A routing row is likewise paid for by a cut.

Then `rietx skill --install . --copy` re-syncs the two committed copies, or they
drift.

### What deliberately does not happen

- **No `capabilities()` surface flag.** "Can this build record runs?" always
  answers yes — there is no optional dependency behind it — so a flag would be a
  literal `True` in disguise, which `_features()` forbids by construction, and
  `_SURFACE_FLAGS` exists because a derived flag rots silently
  (`features["indexing"]` was `False` for its whole life). Write the refusal
  down; adding one is the reflex.
- **No seventh versioned contract.** The run layout is a second process's
  contract, which argues for an arm; nothing negotiates over it and WP-1006's
  own precedent is that a contract nothing has exercised is an untested guess,
  which argues against. Defer until the layout has survived a release, and say so
  here rather than leaving it unasked.

### Two WPs to close out

- **WP-1322's Task 2** — the `history` defaults asymmetry decision — is
  discharged by WP-1403, which removed its premise. Record that in 1322, dated,
  and leave its Task 1 (the terminal-shaped post-hoc aggregator over an event
  log) untouched: it is a different surface for a different moment, and it is a
  contributor's offered PR.
- **WP-1133** (a diagnostic names the rendered view that shows it) now has a
  rendered view to name. Note it in that WP's `### Inherited` rather than
  claiming it here.

## Non-goals

- **No code.** If a docs session finds a behaviour that cannot be written down
  honestly, that is a bug report against the WP that shipped it, not a fix here.
- **No screenshots in the manual for the watcher**, unless WP-1401's page turns
  out to need them. `make_screenshots.py` drives the GUI; extending it to a
  second server is its own decision.
- **No skill body sentence about `telemetry=` or the watcher's existence.** An
  agent does not need to know the plumbing; it needs to know the exception can
  arrive unasked. Resist the second sentence.

## Tasks

- [ ] The root CLAUDE.md clause, edited to keep the rule and drop the false half.
- [ ] `using/cli.md` (both the section and the `--help` block) and
      `using/files.md`.
- [ ] `using/refining.md`, with the writes-to-disk sentence early and the sizes
      quoted from WP-1404.
- [ ] `using/compatibility.md`: the `fit.html` break and the `live/` change.
- [ ] The skill body sentence, **with its cut named in the commit message**.
- [ ] The `references/` file and its routing row, with the pinned header and the
      measurement tags; then `rietx skill --install . --copy`.
- [ ] WP-1322's Task 2 recorded as discharged, dated; WP-1133's `### Inherited`
      noted.
- [ ] Record the two deliberate refusals — no surface flag, no seventh contract
      — where a later session will find them, which is here and in the module
      docstring, not in a commit message alone.
- [ ] Skill: this WP **is** the skill task for the track.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_manual.py tests/test_skill.py tests/test_docs_consistency.py tests/test_help.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

`-W` green is not a rendered page: open the built HTML for the changed pages and
look at them, per the manual's own rule that a paragraph which printed its own
TeX passes every check a build can make.

## References

- WP-1330 — three destinations for what a session learns; a reference per task
  shape behind a situation row; a body addition paid for by a cut.
- WP-1117 — the manual's coverage partition, and the compatibility page's
  preview status.
- WP-1067 — a WP that adds physics adds its equation to Part 2. This one adds
  none, which is why Part 2 is untouched.
- WP-1037 — `_SURFACE_FLAGS`, and the derived flag that was wrong for its whole
  life.
- WP-1322 — Task 2, discharged here.

## Handover log

- **2026-09-13** — created. Placed last in the track but it is not optional
  decoration: WP-1403 changes what every `fit()` does to a user's filesystem, and
  a behaviour change nobody wrote down is the thing the few-users policy exists
  to prevent. The hardest editorial judgement is the skill body — exactly one
  sentence qualifies, and the pressure to add a second explaining the watcher
  should be refused.
