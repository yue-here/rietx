# WP-2008 — The skill slimmed to the API, the feedback surface and sourced traps

Milestone: generality · Status: ⬜
Track: The prose
Depends on: 2001, 2002, 2003, 2004 (2005, 2006, 2007 soft: those three move few skill rows)
Priority: P3 2026-10-18 — down a rung from P2: nothing here can start until the audits have ruled; lifts when 2002–2004 close

## Goal

The skill does two things and nothing else: it makes an agent know the API and the
feedback surface accurately, so the first call is right and no token goes on
rediscovering a field; and it names the traps and exceptions, each with a source outside
rietx's own runs, that a strong agent would not bring to mind unprompted. Every row
measured on rietx's test data is cut, and what the package should act on enters the audit
table to be judged there; every row
that restates a verdict becomes the number; the total falls by a large fraction and the
caps are re-landed at the new sizes. Contested cuts are measured on `tests/eval_skill`
before they land.

## Context

The rule is `../milestones/generality.md` § The rule. The skill is the second source of
overfit the open ranked, after the runner's actions: 61 000 words across `SKILL.md` and 19
`references/` files, the largest `surprises.md` (5 570 words), `judging.md` (5 546),
`series.md` (5 308), `api.md` (4 592), `diagnostics-indexing.md` (4 277). It is read whole
per task shape on every call, so a row measured on one dataset and phrased as a rule costs
tokens on every fit as well as steering the agent wrong.

**The seams.** Root CLAUDE.md § skill and WP-1330/1338: a rule goes in the cheapest place
that holds it (the package's own output first, a reference row keyed on a name the agent
holds, a routing row for a task shape, the body last). Every row written from runs is
tagged `(Measured: …)` or `(Hypothesis: …)`; 130 lines carry one today (145 tags). `tests/skill_caps.py`
has a ceiling per file and a budget that fails growth. `rietx skill --install . --copy`
re-syncs the two committed copies. `tests/test_docs_consistency.py` fails a diagnostic
code without a row; `test_skill.py` a verb the index omits; `test_skill_cli.py` a copy out
of sync.

**The skill's role** (DESIGN.md § Rules, 3; the fourth review, the maintainer's
words). It exists to save tokens: an agent that knows the API and
the feedback surface accurately makes the right first call and reads the result without
guessing. It is not prescriptive. A row that says what to *conclude* from a number is
frozen reasoning, ages with every model generation, and costs tokens on every call; it is
the overfit this milestone is about, written as prose. What earns a place beyond the
vocabulary is a trap or an exception a strong agent would not bring to mind, with a source
outside rietx's runs: a convention two codes swap (GSAS and FullProf's X/Y labels), a
documented reader behaviour (GSAS-II concatenates multi-range scans), a published
collinearity (Williamson–Hall over a narrow 2θ range), a guideline (McCusker 1999 on
observations and reflections), and established workflow practice in rietx's terms (the
order of a refinement, McCusker 1999 § 2, which a strong agent knows in outline and not
as stage globs). The skill shrinks as the manual improves, and shrinks further as the
manual reaches the corpora models train on; no agent needs a skill for GitHub, and the
aim is that none needs one for rietx beyond its traps.

**Four kinds of row.** Each row is sorted as one of: (a) API or feedback vocabulary, what a
call takes and what a field means, kept; (b) a sourced trap, exception or piece of
established practice, kept with its source named; (c) a heuristic measured on rietx's
own data, cut; (d) a verdict restated, rewritten to the number the package states.
A `(Measured: …)` tag marks a row as kind (c) by default; it survives only by acquiring a
source. A kind (c) row the package should act on is a new heuristic in the package: it
enters the audit table as a `suggestion` and faces both grounds there, and never lands
as a rule in `help.py` prose (DESIGN.md § Rules, 3 cuts such a rule wherever it is
written). Where the harness shows agents need what a cut row said, the package carries
it by that route or by a pointer to the manual, and the row still goes (the record
§ Decisions: a slower task is repaired by a pointer from the package, never by a row). The generated `api-<shape>.md` files are
kind (a) by construction and are not read by hand.

**Three conditions, from the maintainer's acceptance of the fourth review's reading.**

- *Agents do not browse a manual.* An agent reads what the harness loads and then what is
  one step from where it is: a docstring, `help()`, an error, a diagnostic's explanation,
  the first search hit. It opens a manual page when something fails or when it is pointed
  at one. Nobody has measured this on rietx. So the first task is the measurement: one
  registered `eval_skill` round with the skill removed and the manual installed, counting
  manual reads and outcomes against the current skill, before any cut.
- *The manual must be reachable from inside the package.* Each class of rows cut has a
  pointer from the package's own output (a `help.py` entry, a `Diagnostic.explanation`,
  the API index) to the manual section that holds the explanation, and a page is
  readable without a browser. Where that needs code beyond a URL in an existing field (a
  `rietx docs <name>` verb, say), it is a follow-up WP filed from here, and the cut that
  needs it waits. A cut that makes a task class slower is repaired by a pointer from the
  package and never by a row back in the skill.
- *The vocabulary is generated, never written.* Training corpora teach a model the
  concepts and the shape of the API, years late and version-blind; rietx changes monthly.
  So kind (a) rests on the generated index and on the package's own `help`, and a
  hand-written vocabulary row is a candidate for generation or for cutting.

**The structure is on the table too.** The skill is one body plus one reference per task
shape (WP-1338), read whole per shape. That was sized for a skill that carried
heuristics. With kinds (c) and (d) gone, several references may empty, and the right
shape may be a body, the generated index and one file of traps. Decided by the
measurement above and by the token count per call, and the maintainer rules on the
shape in the batch.

**The tripwire does not reach prose.** 2001's guard walks `src/`; a heuristic written as a
skill row is invisible to it (2001's docstring says so). This WP's answer is the source
test in the tasks below (DESIGN.md § Rules, 4's test for a new skill row): a row outside
the generated API files that states a threshold, a verdict or a rule names a source
outside rietx's runs, or fails. A `(Measured: …)` tag is not a source. The test reads
tokens and cannot judge meaning, so it is weaker than the code guard, and is said to be.

**Measured before cut.** `tests/eval_skill` (WP-1905) asks whether a body change keeps
outcomes; a round is registered before it runs and its cells are a spend the maintainer
approves per session (memory `eval-spend-is-scoped-per-session`). A row the audit demotes
is cut; a row the agent is thought to need, whatever the table says, is a contested cut
and goes through the harness.

### Inherited

- **From WP-2037 (2026-10-24, second session, PR #1145): three verbs and a routing change.** New: `RefinementResult.summary(deliverable=, levels=)`, `RefinementResult.usable_under(levels)` and `rx.diagnostics_summary`. The last renders to a new `references/api-batch.md`; the body's §9c routing row links it, paid for by shortening that row's `[batch-operating]` label to `[operating]` (body 16 999 of 17 000 B). `references/batch.md` 9c.18 names the verb in one sentence. Every `summary()` takes `levels={code: allow|warn|deny}`; `usable` itself reads the result alone (Decision 6 there).
- **From WP-2002 (2026-10-20, PR #1050): skill rows that changed with a ruled verdict.** `CELL_RUNAWAY` (diagnostics.md, the cell now reset and held), `MOMENT_ANGLE_STATIONARY` (magnetic.md, the angle's profile interval), `QPA_FRACTION_UNDETERMINED` renamed `QPA_FRACTION_RANGE` (an info record, no threshold), `K_VECTOR_UNSEPARATED` and `MAGNETIC_SUBGROUP_PREFERRED` (N/f² and no R tie-break), `SIZE_UNUSUALLY_SMALL`, `STRAIN_UNUSUALLY_LARGE` and `PHASE_UNCONSTRAINED` (abstention.md), the new `OCCUPANCY_ABOVE_ONE`, and `auto_background`'s `.background` in SKILL.md. Read each against the table's row.
- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: `model_dump(mode="json")` is not JSON for an infinite bound.** `SKILL.md:44`, and `references/api.md:13` from `make_api_index.py:499`, say to dump an answer with `model_dump(mode="json")`. That returns a ±inf bound as a Python float, so `json.dumps` writes a bare `Infinity`, which a strict parser rejects; `model_dump_json()` writes the `"Infinity"` strings the schemas promise (measured, pydantic 2.14.1). It is harmless to an agent reading the dict in Python and wrong for one storing or sending JSON. `docs/docs/reference/programs.md` gives `model_dump_json()`. Root CLAUDE.md's integration-surface clause says the same and is the maintainer's to change.
- **2026-10-20, from [2014](2014-a-heuristic-meets-the-judge-on-every-path.md)'s filing: outside PRs bring skill rows too.** Nine of the twelve open outside PRs that touch `_audit.py` also edit `docs/skill/`, and some add verdicts: #941's `diagnostics-indexing.md` rows say "Keep this candidate; it caps, never refutes" (`INDEX_PREDICTED_BUT_ABSENT`) and "Quote the larger cell" (`INDEX_SUPERCELL_REFUTED`). A source check on thresholds and verdicts does not catch WP-2002's B12 class: a row telling agents to call a verb whose rows are tier `caller` makes that verb a default path (`profile_fraction` was one). Check each row that names a verb against the verb's tier. 2014 adds the class to `/pr-review`'s list of what outsiders miss; this WP owns the sweep.

## Non-goals

- Rewriting the skill's voice (1330 and 1985 settled it). The structure is in scope.
- The manual (`docs/manual/`, `docs/docs/`): 1986 is moving it; a chapter that quotes a
  demoted verdict is that WP's or a follow-up's. The manual is where a cut row's
  *explanation* lands if it is worth keeping for a human, never back into the skill.
- A `rietx docs` verb or any other code that reads a manual page from the package: a
  follow-up WP filed from here if the measurement shows a cut needs it.
- Adding a row for a new feature.

## Tasks

- [ ] The baseline measurement: one registered `eval_skill` round, the current skill
      against no skill with the manual installed, counting manual reads, calls to a
      correct answer and outcomes per task shape; the spend approved per session. Its
      table is the evidence every cut below is judged on.
- [ ] Inventory: every row of `SKILL.md` and the 19 references sorted into the four kinds,
      with, for (b), the source; for (c), the table row it rests on and the audit's
      ruling; for (d), the number the package states. Word count per file and per kind.
- [ ] Kind (c) cut, and where the package should act on it, entered in the audit table
      as a `suggestion` with its two grounds; kind (d) rewritten to the number; each file
      as its own commit so the handover can quote the cut per file.
- [ ] Kind (b) rows: each carries its source in the row; a trap with no source is kind
      (c). The source test (in `test_skill.py`): a row outside the generated API files that
      states a threshold, a verdict or a rule names a source token (a citation, a program
      name with the documented behaviour) or fails.
- [ ] The pointers: for each cut class, the package's own output names the manual section
      that holds the explanation; where a pointer needs code, the follow-up WP filed and
      the cut deferred.
- [ ] The contested list to the maintainer with a costed `eval_skill` round (rows the
      session believes agents still need, whatever their kind), and the structure
      question with the token count per call under each shape; run what is approved;
      land each cut with the pointer or package-side route its round showed it needs.
- [ ] Root CLAUDE.md § Invariants names the source test in one clause, since DESIGN.md
      § Rules, 4 places the mechanisms that enforce its tests there.
- [ ] The body re-measured against its 5 000-token budget and the caps in
      `tests/skill_caps.py` re-landed at the new sizes with their diary lines, so growth
      back toward today's size fails; `rietx skill --install . --copy` and the copies' test.
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: this WP *is* the skill; the handover quotes the word count before and after
      per file, the rows per kind, and the sources the kept traps cite.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_skill*.py tests/test_docs_consistency.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The record's row "the skill is the API, the feedback surface and sourced traps" is checked
by the source test on the final tree, and the handover quotes the total before and after:
the second review dropped "the total falls" as a bar, and the fourth review, from the north
star, puts it back, because the skill's role is now narrower than interpreting verdicts.

## References

- `docs/milestones/generality.md`; WP-1330, 1338, 1905, 1985; `tests/skill_caps.py`.

## Handover log

- **2026-10-18** — created, from the milestone's opening session. The acceptance row the
  first plan had here, "the skill's reference total falls", was dropped on the second
  review: a demoted verdict's meaning has to be interpreted somewhere, usually the skill,
  so the total may not fall and the right bar is the tag. The fourth review reversed
  that on the maintainer's statement of the skill's role (DESIGN.md § Rules, 3): the
  interpretation is the caller's, the skill carries vocabulary and sourced traps, and the
  total falls. The title changed from "read against the audit table" to match.
