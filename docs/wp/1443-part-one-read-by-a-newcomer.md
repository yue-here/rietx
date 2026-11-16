# WP-1443 — Part 1 read by a newcomer: eleven passages, one word, and the version the manual describes

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Track: The repo's own process
Depends on: — (1409 is the shape)
Priority: P3 2026-09-23 — twelve passages a newcomer stopped on; the text is wrong in words, never in a number

## Goal

A crystallographer who is not a programmer reads Part 1 in order and is never
stopped by a passage that assumes a later chapter, a word the text has not
defined, a claim that something "raises" with nothing named, or a verb the
release they installed does not have.

## Context

A newcomer (issues #395–#404, #406, #407, filed 2026-09-19/20 against the
hosted manual) read Part 1 linearly and reported every place it stopped them.
WP-1409 made Part 1 read like a manual for a reader who already knew the
package; this is the same pass for one who does not. Every passage below was
located in the sources on `origin/main` at `4ee4e7f5` (2026-09-21) and is
still there. Screenshots are on the issues; the sources are quoted here so the
WP is self-contained.

**The eleven passages.**

1. **#395 — `docs/manual/using/data.md:37-43`, the `Parameter` example.** The
   block ends `assert width.transform == "softplus" and width.min == 0.0`. The
   reader took the `assert` for part of the parameter definition. It is the
   manual's own test: Part 1's python blocks execute under
   `tests/test_manual_api.py`, and an `assert` is how a block checks itself.
   The fix keeps the check and stops it reading as API: show what
   `Parameter.positive` set, as a comment carrying the printed value, and move
   the assertion to where the reader cannot mistake it (a `{note}`, or the
   test's own hidden block form if the manual has one; check `conf.py` and the
   other chapters for the convention before inventing one).
2. **#396 — `data.md:96-98`.** "every weighted quantity in the package divides
   by the result: the objective {eq}`est-obj`, every renderer's difference
   curve, both GUI windows." A list without a verb. Say which three things
   divide by σ, in a sentence each.
3. **#397 — `data.md:147`.** "no shipped plan frees both" names plans before
   the chapter that introduces them (`concepts.md`), and "shipped" reads as
   software jargon. Two fixes: the sentence links forward to the plan
   section of `concepts.md` by anchor; and "shipped" is replaced
   throughout Part 1 (`grep -n shipped docs/manual/using/*.md`: 9 hits at
   `4ee4e7f5`, in `data.md`, `model.md:51`, `refining.md:150`,
   `results.md:617`, `gui-quickstart.md`, `gui-power.md:214`,
   `compatibility.md:137`) by "built-in" for a plan or preset and "included"
   for an example project. Not every hit is the same sense; read each.
4. **#398 — `data.md:193` and `concepts.md:41`.** "`vary=True` on such a
   coordinate raises." Name what: the exception class and the message's first
   clause, as the other refusals in Part 1 do. Both passages say it and both
   need the name.
5. **#399 — `data.md:328`.** "for a single histogram" is the first use of
   *histogram* the reader met, undefined. Define it at first use (one pattern
   in a fit; GSAS's word, kept because the joint-fit chapter needs a word for
   "one of several") and check the glossary carries it (`help.py` generates
   `using/glossary.md`; a glossary entry is a `help.py` entry).
6. **#400 — `concepts.md:49`, "Why the groups correlate".** The figure's
   y-axis reads "effect, normalised at mid-range" and the text never says
   effect on *what*. It is the shift of a peak's position per unit of the
   parameter. Say so in the paragraph and on the axis. The figure is drawn by
   `docs/manual/make_figures.py`, the one authority, and the committed
   light/dark pair is regenerated from it.
7. **#401 — `concepts.md:124`.** "A restraint is the other thing:" reads as
   odd. Rephrase: a restraint is the other way to bring knowledge into the
   fit, and it works by adding an observation rather than removing a
   parameter.
8. **#402 — `concepts.md:200-202`, the tied-biso worked example.** The reader
   reconstructed the argument correctly and said it took sitting and
   thinking. Write the reasoning out in the order they reconstructed it: the
   three oxygens are chemically alike, so one displacement parameter is a
   sensible model; the constraint returns a smaller esd; Rwp moved by 0.05 %
   of itself, which is neither for nor against the constraint. Then the
   check that must come first, which the existing next paragraph already
   carries.
9. **#403 — "glob", 59 occurrences in `using/*.md`.** A reader who is not a
   programmer reads "glob" as jargon. The word stays, because it is the API's
   own (`turn_on` takes globs and `fnmatch` is the semantics), but it is
   defined at its first use in Part 1 with one example
   (`"phases.*.cell.*"` matches every cell parameter of every phase), the
   glossary carries it, and the sentence quoted in the issue
   (`concepts.md:287-290`) is rewritten so that "a stage whose `turn_on` glob
   matches your pinned parameter" reads as "a stage that turns on a pattern
   your parameter matches".
10. **#404 — `concepts.md:421-436`, the plan diagram, and the sentence under
    it.** Mermaid draws the `a --> b` edge between the two subgraphs at
    mid-height, so `mccusker_structural`'s chain appears to enter the
    default chain between `cell` and `W`. Redraw so the second chain
    visibly continues from `U, V, X, Y` (one chain of ten boxes with the
    boundary marked, or the edge from `E` to `F`). And "Every stage runs to
    convergence with everything above it still free" means that each stage
    adds its parameters to those already free and refines all of them;
    say that.
11. **#406 — the advice scattered through Part 1.** The reader found the
    harmonic-contamination rule of thumb (`refining.md`, the λ/n section)
    and asked for the advice to be findable in one place. The theory of
    each check stays where it is. What is added is one page, or one section
    of `refining.md`, keyed by *symptom* ("Rwp is fine and GoF is far from
    1", "a parameter reached its bound", "the difference curve has a
    derivative shape"), each row one sentence and a link to the passage
    that explains it. The agent skill's body already carries the judgement
    rules for a program; this is the human's index of the same, and it
    must not become a second copy of the skill.

**The version the manual describes (#407).** The reporter ran
`ref.hold("instrument.profile.v")` from the manual's own example
(`concepts.md:299`) and got `AttributeError: 'Refinement' object has no
attribute 'hold'`. Not a bug in the tree: `hold`/`unhold` landed with WP-1435
on 2026-09-18, after `v1.5.0` was tagged the same day (`git grep "def hold"
v1.5.0 -- src/rietx/refine.py` finds nothing), and PyPI's latest is 1.5.0.
The manual is built from `main` on every push (`.github/workflows/pages.yml`)
and its title carries the *development* version string, so a `pip install
rietx` reader is handed documentation of verbs their install lacks, with
nothing on the page saying so. Two fixes belong here, and the third is a
release. (a) `install.md` states that the hosted manual describes `main`,
names the last release, and gives the one-line install from git for a reader
who wants what the manual shows. (b) A verb or field newer than the last
release carries a one-line "since" note until that release exists; the
mechanism is whatever `conf.py` can derive from the dist version and the
release records (`docs/releases/`), never a hand-maintained list. (c) The
release itself is a `RELEASING.md` walk, decided at the triage batch, not
this WP's.

**Guards already in place.** `tests/test_manual_api.py` executes every Part 1
python block and resolves every dotted name and dot-path; `tests/test_manual.py`
scans the built HTML for unrendered math; `docs/manual/make_figures.py` is the
one authority for figures. The `yue-docs-style` and `yue-prose` skills carry
the register and the banned words; "simply", "just" and "easy" are not the
problem here, undefined words are.

### Inherited

- **2026-10-16, from the issue triage (#407): the reporter's symptom is gone
  from the release; the manual still does not say which version it
  describes.** `Refinement.hold` is in the `v1.6.0` tag (tagged 2026-10-04;
  `git grep "def hold" v1.6.0 -- src/rietx/refine.py` hits) and in every tag
  after it. No 1.5.1 was cut, so this file's "`docs/releases/1.5.1.md`" and "a
  1.5.1 release carrying `hold`" point at a release that does not exist; the
  `RELEASING.md` walk it mentions is moot for this issue. What is still open
  and still this WP's: `install.md` says nothing of the manual describing
  `main` or how to install it (its only version line is `{{ release }}` at
  line 79), no verb or field carries a "since" note (`git grep 'since [0-9]'`
  finds one unrelated row), and WP-1979 plans the versioned `/docs/<version>/`
  tree that would make the note unnecessary. Decide whether 1443's #407 task
  is paid by 1979 or by a short `install.md` paragraph in the meantime.
  Checked at origin/main 138d55dc.

- **2026-10-16, from the issue triage (#395): passage 1's quoted sentence is
  no longer in the tree, and the maintainer's public answer on #395 is
  stale.** WP-1938 D6 (`c7cadcc1`, schema 0.45 to 0.46) removed
  `Parameter.transform`. The block at `data.md:37-43` now ends `assert
  width.min == 0.0` with no output, and the prose says only that
  `Parameter.positive` "sets `min=0.0`". The reporter's confusion stands (an
  unexplained `assert` in an API example), but the task's wording (`assert
  width.transform == "softplus" and width.min == 0.0`, "show what
  `Parameter.positive` set") needs re-reading against the new block, and the
  comment on #395 said `Parameter.positive` "sets the softplus transform",
  which is now false. Same drift, smaller: `grep -w shipped docs/manual/using`
  finds 15 hits in 8 files, against this file's 9 in 7 (quickstart,
  `refining.md` x5 and `results.md` are new or moved). Checked at origin/main
  138d55dc; the other nine passages are still in `data.md`/`concepts.md`.

- **From WP-1975 (2026-10-15): the manual is to be rebuilt as a new tree beside the old one,
  with each old chapter retired once its content has been mined** (WP-1975 § F8, § H1). The
  layout is Start | Guides | Concepts | Reference | Theory | Switching. A fix made in an old
  `data.md` or `concepts.md` passage is lost when that chapter is retired, unless the new page
  that holds the content also gets it. Before starting, check how far the rebuild has got.
  Where a passage's content already has a home in the new tree, fix it there. These eleven
  passages are also a ready-made acceptance check for the new Start and Concepts pages.
- **From WP-1975 (2026-10-16): the rebuild is filed.** WP-1978 builds the new tree (Sphinx
  with pydata-sphinx-theme), WP-1983 writes Concepts, and WP-1986 mines the old chapters into
  Guides and retires them. Check those three for how far each has got.

## Non-goals

- Part 2, the theory chapters (1408 covered them, and the newcomer did not
  reach them).
- The agent skill's prose; the skill is for a program and is byte-capped.
- Renaming `turn_on` or any API name. The manual explains the words the API
  uses.
- Publishing 1.5.1. That is a release decision, recorded at the triage.

## Tasks

- [ ] Passages 1–5 (`data.md`, and `concepts.md:41`): the `Parameter` example
      shows its output, σ's three consumers get verbs, "shipped" leaves Part 1,
      the coordinate refusal is named, "histogram" is defined at first use and
      in the glossary.
- [ ] Passages 6–10 (`concepts.md`): the correlation figure names its effect
      (regenerate the pair from `make_figures.py`), the restraint sentence, the
      worked example's reasoning written out, "glob" defined once and the
      hold sentence rewritten, the plan diagram redrawn and its caption
      corrected.
- [ ] Passage 11: the symptom-keyed index of Part 1's advice, one row per
      check, linking rather than restating.
- [ ] #407: `install.md` says what the manual describes and how to install
      `main`; the "since" note derived from the dist version and the release
      records.
- [ ] `tests/test_manual_api.py` and `tests/test_manual.py` green; the
      `yue-prose` grep pass over every touched chapter, before and after.
- [ ] Skill: none. Every change is Part 1 prose for a human reader; the
      skill's body and `api.md` are untouched.

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_manual.py tests/test_help.py
.venv/bin/python -m ruff check src tests examples
grep -c shipped docs/manual/using/*.md   # 0 in the sense "built-in"
```

And the eleven issues read against the rebuilt pages, one by one, each
closed with the commit that answered it.

## References

Issues #395, #396, #397, #398, #399, #400, #401, #402, #403, #404, #406,
#407 (all LLongley94, 2026-09-19/20). WP-1409 (Part 1 reads like a manual),
WP-1435 (`hold`), `docs/RELEASING.md`, `docs/releases/1.5.1.md`.

## Handover log

- **2026-09-21** — created, from the 2026-09-21 issue triage (issues #395,
  #396, #397, #398, #399, #400, #401, #402, #403, #404, #406, #407). Checked
  against the tree at `4ee4e7f5`: every quoted passage is in the sources at the
  lines cited above; `hold` is on `main` and absent from `v1.5.0`, and PyPI's
  latest is 1.5.0, so #407 is version skew between the hosted manual and the
  release, not a defect in the verb. Next action: a session takes the tasks
  in order; the first two are one chapter each.
