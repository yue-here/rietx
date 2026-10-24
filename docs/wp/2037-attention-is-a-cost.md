# WP-2037 — Attention is a cost: two channels, a response per code, relevance by purpose

Milestone: generality · Status: ✅ 2026-10-24 — closed: diagnostics print by purpose, a caller's per-code levels with usable_under, the batch aggregate and suite metric, the silence harness; the agent round did not fire the tripwire
Track: The registry and the guard
Depends on: 2001

## Goal

The generality record carries a fifth aim beside its four: rietx must not flood a user
or an agent with noise, because attention spent on noise lowers the quality of the
refinement. Four clauses in § The rule and § Demotion give it teeth: a number lives in a
field and a diagnostic earns its place by telling fits apart; a code's level is the
response it requires, and whether it applies is derived from the caller's declared
purpose; the default view prints by level and refuses to guess a purpose; the caller may
set a code's level. The audit table has a response column with its tests, the summary
and the other three renderers share one filter, the deliverable vocabulary covers the
goals, and a batch aggregate serves pipelines and the suite metric alike.

## Context

The rule is [generality § The rule](../milestones/generality.md#the-rule) and
§ Demotion; the decision line is [DESIGN § Rules](../DESIGN.md#rules), 1. The proposal
this WP files was written 2026-10-23 in three drafts, reviewed adversarially against
both, and ruled on by the maintainer the same day (§ Decisions below). Its worked
before/after examples are in [`2037-attention/examples.md`](2037-attention/examples.md),
with every *before* block measured on `main` that day.

**Why.** DESIGN.md § Rules 1 prices a rerun ("a caller pays in tokens and a fit in
seconds") and not reading. Under-alerting costs as much as flooding: the one measurement
on agents says they stop on a stated criterion seven times in eight and never without
one (the v1.3 round, the record § The rule). This aim adds the cost of reading to the
rule and moves the decision line nowhere.

**Who reads, and for what.** The package has no single reader and no single response.
Goals: phase identification; a cell as the result; QPA; structure (coordinates,
occupancies, ADPs); microstructure; instrument calibration; a series; magnetic
structure; indexing; publication, which needs the caveats; teaching; method development.
Users: an agent over one pattern (the design's first user); an agent or script over
hundreds of fits, where the consumer is a filter; an expert who will disagree with a
level; a student who needs the explanation; a GUI user; an instrument scientist. The
same finding is nothing for one goal and fatal for another: `RESOLUTION_UNCONSTRAINED`
is irrelevant to a QPA fraction and voids a size claim; `FLOOR_HIT` on extinction is
irrelevant to a cell and matters to an ADP. So a message's level is a property of the
code *under a purpose*, and that property is physics: which result numbers depend on
the thing the diagnostic names.

**What the tree does today** (measured on `main`, 2026-10-23, the skill's worked
default on FAP, `examples/skill_worked_default.py`):

- `Diagnostic.level` (`schemas/common.py`) has three values. Raise sites: 117 `info`,
  161 `warning`, 7 `error`. Two readers act on a level: `RefinementResult.usable` reads
  `error` alone; `SeriesResult` splits `warning` from the rest. Nothing treats `info` as
  quieter.
- `Refinement.summary()` (`refine.py`) prints every diagnostic at every level under one
  header, "N unresolved", through `schemas/results._diagnostic_lines`, which
  `str(result)` shares. The skill's § 4 says "Act on each `d.suggestion`". So an `info`
  record is shown as unresolved and acted on.
- `summary(deliverable=)` knows `DELIVERABLES = ("phase_id", "qpa", "structure",
  "series")` (`schemas/results.py`) and refuses to infer a purpose, by design. Cell,
  microstructure, calibration and magnetic have no name, though the skill's § 4b table
  has a microstructure row.
- § Demotion rules (2026-10-18) that a demoted verdict becomes an `info` record that
  fires on every run it applies to. Under the readers above, every demotion from 2003 on
  adds a row the agent is told to act on.
- `rietx._audit.Row` tiers a code's statistic, threshold and action. No field says what
  a reader does on seeing it; no test holds a code's level to anything; no test holds a
  code silent where its fault is absent. No per-code override, no aggregate over a batch
  of independent fits (the series aggregate `SEQUENTIAL_PERSISTENT_FINDING` exists).
- The worked default returns four warnings and no `info` (the run's one `info`,
  `BACKGROUND_ORDER_AT_CAP`, is a `UserWarning` from `auto_background`). `summary()`
  prints 3 829 characters, `summary(deliverable="structure")` 4 114. One warning is a
  snap of 3.3e-11 in a fractional coordinate (`SITE_SNAPPED_TO_SPECIAL_POSITION`,
  `crystallography/cif.py`, no magnitude floor), the CIF's own rounding. One is
  `FLOOR_HIT` on an extinction the plan freed on a lab powder. `RESOLUTION_UNCONSTRAINED`
  is right and irrelevant to a structure. Only `PATTERN_UNDERSAMPLED` bears on what the
  worked default quotes.

The noise today is in level and relevance, not volume, and § Demotion as written adds
volume with every demotion.

### The rule: four clauses

Written into `generality.md` § The rule and § Demotion, with the fifth aim beside the
four in § Scope.

**1. Two channels.** A number lives in a result field and costs nothing until read. A
diagnostic is a message, and it earns its place by telling one fit from another: it
fires on some fits, stays silent on others, and a careful refiner does something
different when it fires. A demotion moves the statistic into a record field, with its
explanation in `rietx.help` keyed to that field, and emits no diagnostic that fires on
every run. The field channel is a structured record the CIF writer, the report and the
GUI read; never a dump.

This reverses the shape ruled on 2026-10-18 and answers the evidence that ruling cited.
GSAS-II and TOPAS print the largest shift/esd every cycle, which is tier-2 practice for
*printing a statistic*. They print it to a log; neither puts it in a list the reader is
told to resolve. A record field plus a line in the full report is the same practice in
rietx's shape, and a row under "unresolved" is not. The ruling chose its shape over
building a help seat for result fields; this clause builds the seat.

**2. Level is the required response, and relevance is derived from the purpose.** The
flight-deck definitions, one purpose at a time:

- `error`: do not read the values. `usable` reads it already. Unchanged, and never keyed
  on purpose: an unusable fit is unusable for every purpose.
- `warning`: act before quoting a result number of this purpose, or the plan did not
  reach what it asked. A result number is a cell, a fraction, a coordinate, an ADP, a
  size; an agreement index is not one.
- `info`: awareness. Nothing to do for this purpose.

Two tables carry it, and neither is authored per code per purpose. The code's audit row
gains one **response** column (`warning`, `error` or `info`) with one sentence on what
the reader does; one response per code, magnitude in the message; where two
consequences genuinely differ, two codes, never a threshold between levels. A
**purpose** declares the parameter paths its result numbers depend on, as globs in one
table of about eight rows, each citing the physics that couples the number to the path
(`cell`: `phases.*.cell.*`, `instrument.zero_shift` and the position corrections that
exchange with them, per `report.identifiability`; `qpa`: scales, occupancies, Biso,
texture, background and specimen absorption, the skill § 3 group and WP-1055;
`microstructure`: the profile and sample-broadening terms, WP-1131; and so on).

A diagnostic's level under a purpose is then **computed**: its response where any of its
`where` paths matches the purpose's globs, `info` elsewhere. A code that carries no
`where` (`PATTERN_UNDERSAMPLED`, a convergence failure) declares its scope in its audit
row: the purposes it bears on, or `all`. A code with neither is a test failure, never
`info` by default. WP-1076's rule: a pairing nobody checked must not read as "not your
concern". It is also why the tables stay small: 285 codes times eight purposes is not
written by hand, and a new purpose is one row.

**3. The default view prints by level, and with no purpose it says so.** Under a
deliverable, the text summary prints errors and the warnings for that purpose in full,
and the rows that are `info` for it as one line each, code and paths only. With no
deliverable, it prints the errors in full and for every other row one line naming the
code, its paths and the purposes it is a warning under. The header says how to see
more: *pass `deliverable=` for the rows that decide your purpose; every row is in
`result.diagnostics`*. That sentence is the reading rule, carried by the output itself
(WP-1338: a feature's guidance takes the cheapest place that holds it, the package's
own output first), so the skill names only the field. This is the summary's existing
refusal to infer a purpose, applied to its diagnostics. The GUI shows the same ordering
with the `info` rows collapsed beside their help text; nothing is hidden from the
student or the expert. The "N unresolved" header goes.

**4. The audited response is a default, and the caller may set it.** A per-code override
on `summary()` and in settings (the settings half superseded, Decision 6), in the compiler's allow-warn-deny form. The audited
default is one table row; the override is the audit's caller class and needs no tier.
The expert who disagrees with a response and the pipeline that treats one code as
blocking both get what they want without touching the default.

### What makes the rule survive

- **The response column** in `_audit.Row` and the purpose table beside it. A meta-test
  holds the declared response equal to every raise site of that code, fails a `warning`
  row whose sentence names no result number or plan outcome, and fails a code with no
  `where` and no declared scope.
- **A test of silence.** For each warning code, a fixture where it must fire and one
  where it must not. The mechanical ground already asks this of every flag and nothing
  enforces it; Rust's `#[expect]` is the form.
- **The help seat for result fields** (`help.py`), with both-way tests, first. Clause 1
  cannot land without it.
- **One filter function** every renderer calls: the text summary, `str(result)`, the
  HTML, the GUI panel. The GUI change means a rebuilt dist (`gui/CLAUDE.md`).
- **The deliverable vocabulary** extended: `cell`, `microstructure`, `calibration`,
  `magnetic` beside the four, each with its deciding rows in `_deliverable_lines`;
  `magnetic` kept separate because its numbers depend on different paths.
- **A batch aggregate**: one function over a list of results giving the firing rate per
  code, warnings per fit per purpose and the bad-actor Pareto. The pipeline user's
  triage and the audit's prompt, written once.
- **The two FAP bugs, separately.** The snap floor derived from the file's own printed
  precision (a shift below half the last printed digit is the file's rounding), tier 1
  beside `CIF_ANGLE_CORRECT_MAX_DEG`. `FLOOR_HIT` on a freed extinction is a plan
  question, handed to 2004.

The 248 unaudited code rows are not re-levelled here. WP-2004 to 2007 fill the response
column as they tier each code, under the tests this WP installs, so WP-2003's first
demotion already follows clause 1.

**The tier of each rule this WP adds** (written 2026-10-24, second session; the template
line the filing left out). The purpose table's rows are physics, tier 1: each says which
parameters a result number depends on, citing the coupling. The caller override is the
`caller` class: an empty map by default, so the package decides nothing until a caller
names a code. The batch aggregate decides nothing and reports numbers (DESIGN § Rules 1,
kind 3). The silence registry is a test, not a runtime rule. None adds a threshold.

### How it is measured

- **Alarm-management metrics over the acceptance suites, as a prompt and never a
  verdict.** Firing rate per code, warnings per fit per purpose and the Pareto over the
  suites' fits, pinned in a meta-test so a change that moves them is seen. The suites
  are rietx's own data, so a code firing on every acceptance fit may mean every
  acceptance fit has the fault. A high rate sends the code to the mechanical ground's
  test, a known truth where it must fire and one where it must not. It re-levels nothing
  by itself (DESIGN.md § Rules 3: a rule whose only evidence is rietx's own test data is
  overfit in prose form).
- **Before and after on four families**: the worked default on FAP, NAC on 11-BM, a CPD
  QPA fit, a magnetic fixture. Rows by level and purpose in `result.diagnostics`, lines
  printed by `summary()` with and without a deliverable. Characters are not the metric.
- **One registered agent run** on `tests/eval_report_agent`, current view against the
  split view, a smoke check named as one (eight runs cannot tell seven of eight from five
  of eight). A worse result reverts clause 3's quiet default and keeps the ordering;
  clauses 1, 2 and 4 stand either way.

### Practice drawn on

ISA-18.2 / EEMUA 191 alarm management (an alarm is a condition requiring operator
response; a master alarm database with cause, consequence, corrective action, priority;
health measured by rate, time in flood and the bad-actor Pareto, and a person
rationalises what the metrics find). FAA AC 25.1322 (warning, caution and advisory by
required crew response; silence means normal). Google's Tricorder (a "not useful" signal
per finding; an analyser over about ten percent is switched off). Clang and Rust
(on-by-default warnings need near-zero false positives; allow/warn/deny; `#[expect]`).
PEP 565 (a deprecation warning shown by audience). checkCIF (four levels; the C level
grew into noise). Clinical decision support (overrides of 49-96 %, roughly halved by
tiering into interruptive and non-interruptive; van der Sijs 2006, Paterno 2009).

### Decisions (the maintainer, 2026-10-23)

1. The four clauses adopted; the fifth aim goes into `generality.md` beside the four.
2. Scope: the milestone's § Scope says a redesign is a follow-up WP; this one lands
   inside the milestone, before WP-2003, because § Demotion's current shape makes every
   demotion from 2003 on add a row to the view this WP changes.
3. Clause 3's quiet default lands with the ordering now; the registered agent run is the
   tripwire.
4. The deliverable vocabulary: the four names above.
5. The softening of unanimity for a recorded, cheap-to-undo default is deferred to its
   own brief, [WP-2038](2038-the-softening-a-brief-not-a-change.md); it reopens the
   fourth review for a reason unrelated to attention.
6. (2026-10-24) Clause 4's "in settings" is dropped. `usable` stays a function of the
   stored result alone, and a caller's map reaches the yes/no reading through
   `result.usable_under(levels)`. Reason: `usable` is a property with no argument, so it
   could see a map only through a per-user file, and one stored result would then read
   usable on one machine and not on another; the structure solver's trial cost
   (`solve/cost.py`) reads `usable` too. Linters keep such a map per project, never per
   user (Rust's `[lints]`, pytest's `filterwarnings`; recalled). Chosen over the map in
   `~/.rietx/settings.json`, over storing the map on the result at fit time, and over
   stopping at `summary(levels=)`.

## Non-goals

- Re-levelling the 248 unaudited codes: 2004 to 2007, under this WP's column and tests.
- The chain's own demotions and the discontinuity record's shape: 2003, which follows
  clause 1 once this lands.
- The skill's rewrite: 2008. This WP changes one sentence of § 4 (Tasks).
- The softening: 2038.
- A new purpose for indexing, which is a different result type with its own summary.

## Tasks

- [x] The record: the fifth aim in `generality.md` § Scope; the four clauses in § The
      rule and § Demotion, the 2026-10-18 "fires on every run" shape reversed with the
      log-versus-list answer written beside it; the acceptance row below added to
      § Acceptance; the decisions above dated into § Decisions.
- [x] The help seat for result fields in `help.py`, crossed both ways against the live
      result schemas (`tests/test_help.py`'s pattern), with `rx.explain("<Type>.<field>")`.
- [x] `_audit.Row.response` and `Row.scope`, the purpose table (one module, about eight
      rows with their physics), and the three meta-tests (response equals every raise
      site; a `warning` sentence names a result number or plan outcome; no `where` and
      no scope fails). Existing rows enter with `response` unset and a shrink-only
      baseline, so 2004-2007 fill it as they tier.
- [x] The derived level: one function `level_under(diagnostic, purpose)` in
      `schemas/results.py` (or beside `Diagnostic`), unit-tested on the four FAP codes.
- [x] One filter function and the four renderers: `summary()`, `str(result)`, the HTML
      (`viz`), the GUI diagnostics panel (collapsed `info` beside help; rebuilt dist;
      `npm --prefix gui test`). The "N unresolved" header replaced; the no-deliverable
      line and the `deliverable=` sentence as in `2037-attention/examples.md` § 1.
- [x] `DELIVERABLES` extended with `cell`, `microstructure`, `calibration`, `magnetic`,
      each with its deciding rows in `_deliverable_lines`, the skill § 4b table and
      `SeriesResult.summary`'s refusal text updated.
- [x] The caller override: `summary(levels={code: "allow"|"warn"|"deny"})`, the same map
      in settings, `usable` reading a caller's `deny`; one `caller` row in the table.
      *Superseded in part 2026-10-24 (Decision 6):* no settings file; a caller's `deny`
      reaches `result.usable_under(levels)`, and `usable` reads the result alone.
- [x] The batch aggregate: `rx.diagnostics_summary(results, deliverable=)` (firing rate
      per code, warnings per fit, Pareto); the suite metric built on it and pinned as a
      meta-test over the acceptance suites' collected diagnostics.
- [x] A test of silence per warning code that has a fixture today, and the harness for
      the rest (a registry a code's silence fixture is added to; absence listed, not
      failed, until 2004-2007 fill it).
- [x] The snap floor from the file's printed precision in `crystallography/cif.py`,
      tier 1, with the FAP case silent and a real snap still firing.
- [x] Before/after counts on the four families in the handover; the agent run
      registered, run once, reported beside the v1.3 baseline.
- [x] `FLOOR_HIT` on a freed extinction handed to 2004 as an `### Inherited` entry (done
      at filing; keep it current).
- [x] Tests + PNGs; the fast count moved by exactly the tests added.
- [x] Skill: § 4's "Act on each `d.suggestion`" becomes *declare your purpose with
      `ref.summary(deliverable=…)` and act on the warnings it prints under it;
      `result.diagnostics` holds every row*; the § 4b table gains the new deliverable
      names. Nothing else; the reading rule lives in the output.

## Acceptance

Every code carries a declared response held to its raise sites, a scope where it
carries no path, and a silence fixture where it is a warning; the default view prints no
row outside its purpose in full and names the purposes a row is a warning under; the
suite metrics and the four-family counts are in the handover with the agent-run rate
beside the v1.3 baseline.

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -q
.venv/bin/python -m pytest tests/test_summary_levels.py tests/test_summary_deliverables.py tests/test_termination_view.py tests/test_display.py -q   # the filter, the derived level, the override (2026-10-24: test_results.py never existed)
.venv/bin/python examples/skill_worked_default.py                                # the FAP before/after, by eye against 2037-attention/examples.md
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
npm --prefix gui test && npm --prefix gui run check
```

## References

- `docs/milestones/generality.md` § The rule, § Demotion, § The fourth review;
  `docs/DESIGN.md` § Rules 1, 3, 4.
- ISA-18.2 (2016), *Management of Alarm Systems for the Process Industries*; EEMUA 191.
- FAA AC 25.1322-1 (2010), flight-deck alerting.
- Sadowski et al. 2018, *Lessons from building static analysis tools at Google*, CACM.
- PEP 565; the Rust reference, lint levels and `#[expect]`.
- van der Sijs et al. 2006, JAMIA 13:138; Paterno et al. 2009, JAMIA 16:40.
- WP-1076 (a declared name is a claim), WP-1338 (the cheapest place), WP-1302 (the
  termination view), WP-1985 (the help seat for codes).

## Handover log

- **2026-10-24** — the agent round recorded, the last task. The tripwire of Decision 3 did
  not fire, so the quiet default stands. Eight agents on Sonnet fitted the same four problems,
  four with the old view and four with the quiet one. Every one of the eight stopped on a
  criterion the package states, and the quiet arm passed 4 of 4 against 3 of 4. At four
  cells an arm this catches a collapse and nothing finer, so it says the quiet view did not
  break agents, not that it helps them.

  *Measured* (round 2.3 of `tests/ev*_report_agent/PROTOCOL.md`, registered at `5d8796917`
  10:58 before the first cell at 11:03, outcome at `35b9c7605`, branch
  `agent-round-quiet-view-407bde`, not yet merged here; `claude-sonnet-5-5`, effort pinned,
  episodes N1, C1, W1, W2). Arm a was rietx at `5d64a86`, arm b at `4bfde33d7`.

  | read-out | arm a (old view) | arm b (quiet view) | v1.3 baseline |
  |---|---|---|---|
  | stopped on a criterion the package states | 4 of 4 | 4 of 4 | 7 of 8 (another harness) |
  | verdict passed (`scorer.py`) | 3 of 4 | 4 of 4 | — |
  | called `summary(deliverable=…)` | 3 of 4 | 4 of 4 | — |

  The registered "worse" was a drop of 2 or more on either of the first two rows. A blind
  Sonnet classifier and the round's author agreed on every stop class. a/N1 failed by
  overclaiming `converged` on the zero-against-displacement tie. Eight cells spent 4.56 M
  tokens, 4.14 M of them cache reads ($2.25 at list price). The record (streams, scorecards,
  `cells.json`) is outside the repo at `~/rietx-agent-rounds/r-2026-10-24-record/`. The
  round's own § "After the run" lists five defects, none touching what a cell saw. One is
  that every cell wrote a scratch file to `/tmp`. Read by the rule's letter, that drops the
  W1 pair, and the three pairs left give the same answer. The maintainer's user-level
  CLAUDE.md reaches every cell in both arms.

  **Closed** the same day, on the maintainer's word: `agent-round-quiet-view-407bde` merged
  here, so the round's registration and `launch.py` land with #1145; the narrative is in
  v1.10's record; the user-facing changes of both sessions are staged in the 1.10.0 notes,
  part 1's for the first time (its session had not staged them). No `### Inherited` remains.
  Next is WP-2003, the maintainer's order.

- **2026-10-24** — second session, three of the five remaining tasks and the judge's open
  items; the agent round runs in its own session.
  A caller can now set a code's level per call, quieting it, raising it or making it
  blocking. A result reopened from a project can print its diagnostics under a purpose, and
  a pipeline asks `usable_under` with its own blocking codes. `usable` itself still means
  the same on every machine, because the maintainer dropped the settings file (Decision 6).
  A batch's diagnostics can be counted in one call, and the eight comparison standards' counts are
  pinned. Every code the audit declares a warning now has a test that it fires on its fault
  and stays silent beside it. The counts say where the noise is: three codes make 87 % of
  the standards' warning rows, and none has an audited response yet. On cpd-1a, 49 of 57
  warnings still print in full under `qpa`, so the view stays loud until WP-2005 audits
  them. Not done: the registered agent round, the tripwire of Decision 3.

  *Done* (each item ticked in its commit): the judge's open items and the in-call half of
  the override (`98116ae20`: `magnetic` reads the nuclear-intensity terms; the
  `PATTERN_UNDERSAMPLED` scope gains `magnetic`; the reading rule names `summary()`;
  `RefinementResult.summary(deliverable=, levels=)`; `levels=` on the three summaries and
  `diagnostic_view`; `Refinement.summary` a declared seat owned by 2004, with five rows).
  The batch aggregate and the suite metric came from a lane, with the skill entry moved to a
  new `api-batch.md` (`0c2695a1a`). Every notebook was rebuilt and four stale sentences were
  reworded (`6efaddac2`). The silence harness came from a lane (`4bfde33d7`).
  `usable_under` and Decision 6, the record's clause 4 amended (`83ab9b020`). The review's
  fixes (`756fa18bd`). The forward references, and main merged (`8a45fdee4`; WP-2040's
  tutorial links conflicted in three scripts, theirs kept where it covered the same
  staleness, every notebook rebuilt on the merged sources). The WP's acceptance block had
  named `tests/test_results.py`, which never existed; corrected. Inherited pruned: WP-2040's
  note on stale tutorial outputs, consumed by the two rebuilds, whose 18 flagged cells were
  reread.

  *Decisions this session made, for the maintainer to reverse.*
  - A bare result gained `summary(deliverable=)`, rather than the rule naming
    `Refinement.summary`, so the rule is followable on a reopened result.
  - An override never lowers an error, an unknown code or word is refused, and the header
    counts the rows the map set.
  - The skill entry for the aggregate goes in `api-batch.md`, per root CLAUDE.md, not in
    `api.md`. It is paid for by shortening the body's §9c link label `[batch-operating]` to
    `[operating]`: body 16 999 of 17 000 B.
  - The suite metric runs over `rietx.viz.compare.STANDARDS`, which root CLAUDE.md calls the
    acceptance suites' protocols.
  - The new seat's owner is 2004: the seat-owner test admits 2002-2007, and the summary is
    the report's seam.
  - The lanes' choices:
    - `pareto` lists only codes with a warning row;
    - the suite collects by fitting directly, since a `RunRecord` holds dicts;
    - a warning code is any code with one raise site at `warning` (131 codes; 123 if all
      sites must be);
    - one pair per code, so `SITE_SNAPPED_TO_SPECIAL_POSITION`'s orbit-snap site keeps its
      firing case in `tests/test_symmetry_orbits.py:193`;
    - `FLOOR_HIT`'s pair tests the decision rule, not a solve.

  *Measured* (`[dev]` venv, darwin/arm64, compiled tier on).
  - Four families, before (`5d64a86`) and after (`4bfde33d7`). Rows are raised levels;
    lines are those of the printed diagnostics section.

    | family | warning rows | `str(result)` lines | under its purpose |
    |---|---|---|---|
    | FAP worked default | 4 → 3 | 12 → 5 | 12 → 7 (`structure`) |
    | NAC 11-BM | 0 (1 info) | 4 → 3 | 4 → 2 (`structure`) |
    | cpd-1a | 57 → 57 | 97 → 37 | 97 → 81 (`qpa`) |
    | Cr₂WO₆ magnetic | 1 → 1 | 10 → 5 | — → 7 (`magnetic`, new) |

    cpd-1a's 57 rows are 24 `HIGH_CORRELATION`, 22 `FLAT_DIRECTION`, 9 `FLOOR_HIT`, 1
    `SPACE_GROUP_SETTING_ASSUMED` and 1 `DISPERSION_NEGLECTED`; 49 are warnings under
    `qpa`. The scripts are in the scratchpad (`fam/families.py`, `fam/table.py`), not the
    tree.
  - The suite metric over the eight standards. `DISPERSION_NEGLECTED` fired on 7,
    `FLOOR_HIT` on 5, `HIGH_CORRELATION` and `FLAT_DIRECTION` on 4. The fits carry 77
    warning rows at their raised level, 9.6 a fit. The Pareto runs 44 % (`HIGH_CORRELATION`),
    69 % and 87 % (`FLOOR_HIT`). Warnings per fit by purpose run 7.5 (`phase_id`) to 9.375
    (`calibration`). The collect takes 13-14 s, with another session's suite running.
  - `python -m tests.silence`: 122 of 131 warning codes have no pair, and 9 do.
  - Fast selection on the branch tip before the merge (`4bfde33d7`): 11 447 passed, 265
    skipped, 27 xfailed, none failed, in 8:14, beside another session's pytest, with
    `JUPYTER_PREFER_ENV_PATH=1` (Gotchas). On the merged tree (`8a45fdee4`, main through `6fe7a5bbb`): 11 450 passed, 265 skipped, 27 xfailed, none failed, 13:15. Main moved by about 30 commits during the handover, so the branch was merged again (`fd32512d2`, main through `269e93ca3`): 11 630 passed, 265 skipped, 27 xfailed, none failed, 9:50, same venv and switch; the suite-metric slow test still matches its pin there. No base was
    measured, so the +N check is the added-test tool's count: 26 added test functions, 5.93 s in all (`tests/test_silence.py` 3.45 s for 4, its listed half 1.5 s of that for the raise-site walk; `tests/test_termination_view.py` 2.41 s for 3, each a small fit; every other file under 0.1 s); none joins the slow tail.
  - The full selection did not run: nothing here moves a fitted number. The suite metric's
    slow test ran once (13.6 s), and the tutorial, landing and example tests ran on the
    rebuilt notebooks (107 passed).
  - Lanes:

    | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | model | lane $ | main $ | in-session $ | saved $ |
    |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
    | batch-aggregate | 35 | 89 | 307K | 96K | 17K of 219K | 46 | 76K | 6 | 0 | opus-5-5 | 6.34 | 4.45 | 12.15 | +0.57 |
    | silence-harness | 25 | 50 | 383K | 95K | 0K of 0K | 4 | 13K | 1 | 0 | opus-5-5 | 3.25 | 0.52 | 7.36 | +3.47 |

    Kept here: judge-items (est 15) and the in-call override (est 15). The tool counts them
    as 0 kept. Actual/estimated requests were 2.27. Selective policy row:
    `lane when main > 150K and item >= 20 requests | 266 | +7%`.

  *Code review* (`high --fix 99b00b82e..HEAD`), six findings. Four were fixed in
  `756fa18bd`:
  - the aggregate built a view per purpose per result, and now reads `warning_under` off
    one;
  - the invariance test could raise `StopIteration` on a warning-free fit;
  - the pin spelled the distribution name;
  - the `summary:plan` row did not say that `None` applies no strategy veto.

  Two were declined. The header counts a `warn` on a row already raised as a warning, which
  is literally true and harmless. The deliverable note bypasses the notebook wrapper, which
  `_repr_html_` never reaches.

  *Gotchas.*
  - A user-level Jupyter kernel spec on this Mac (`~/Library/Jupyter/kernels/python3`)
    points at a deleted venv. The two kernel tests in `tests/test_display.py` fail without
    `JUPYTER_PREFER_ENV_PATH=1`, on any branch.
  - The suite pin was written on darwin/arm64. A correlation at threshold on Linux would turn
    the nightly red, naming the code that moved.
  - `Refinement.report()` writes `Statistics.identifiability_clause` into the result, the
    declared cross-document write of WP-1108. So the invariance test compares everything
    but that.
  - `build.py --check` never compares outputs, so a display change needs a rebuild and a
    reread of the cells it lists (WP-2040's note).
  - A one-line `SEQUENTIAL_PERSISTENT_FINDING` hides which code persisted. Forwarded to 2003.

  *Generality* (the `generality-review` judge on the branch at `756fa18bd`, before the
  merge: each verdict and would-change line verbatim, its tables condensed to their findings;
  the author's answer follows each `weak`; no item `fails`).

  **`Refinement.summary:deliverable`: weak.** The case for printing more by default is stronger on the evidence. The tier rests on a test that answers a different question: the test shows the fit's result is unchanged, but the choice this default makes is how much of the diagnostics the reader sees. Would change the verdict: the row citing Decision 3 and the pending agent run as its grounds, or the run itself reported beside the v1.3 baseline.
  *Author:* the row now cites Decision 3 and the owed run; the run is Next (1).

  **`Refinement.summary:plot`: holds.** Would change the verdict: a plot path whose writing touches the fit's state.

  **`Refinement.summary:plan`: weak.** Its evidence described the mechanism wrongly: with `plan=None` the plan-stage veto is skipped but the free-path veto stands (`report/__init__.py:487`, `:529`), and the default ignores the plan the last `fit()` ran (`self._last_plan`, `refine.py:4932`), which the same summary prints as the protocol run. Would change the verdict: the evidence corrected to "no plan-stage veto; the free-path veto stands", and the reason for ignoring `_last_plan` written into the row. Better still, a test showing the printed suggestions under both.
  *Author:* evidence corrected, with the stale-`_last_plan` reason; whether `None` should mean `_last_plan` is a report decision, forwarded to 2004.

  **`Refinement.summary:report`: holds.** Would change the verdict: a summary built with `report=None` that prints differently from one given `ref.report(plan=...)` under the same plan.

  **`Refinement.summary:levels`: holds for the default**, citation wrong: "never lowers an error" is a choice inside the switch, and clause 4 does not say it. Would change the verdict: a default path (GUI route, `fit`, `build_report`) passing `levels=`.
  *Author:* the row now names the rule as this WP's choice, put to the maintainer (3b).

  **`PATTERN_UNDERSAMPLED` scope gains `magnetic`: holds.** Would change the verdict: a magnetic fit on disk where an undersampled pattern left the moment within its esd of a reference value.

  **3a. `PURPOSES["magnetic"]`: holds, two gaps**: the cell and rigid bodies are left out with no written reason (rigid bodies are missing from `qpa` too, so `RIGID_BODY_MISFIT` reads `info` under both). Would change the verdict: a written reason for leaving out the cell and rigid bodies, or a magnetic fit where a cell- or rigid-body-path code read `info` and a refiner would have acted.

  **3b. The override rule: weak.** The case against the "never lower an error" half is stronger than the change admits. The record's clause 4 says the caller may set the audited response, and an error is an audited response. `MODEL_FAR_FROM_DATA`, the one error a fit raises, fires on Rwp > 0.8 alone on a tier-3 threshold (`_audit.py:2259`); inferred, a well-fitted pattern averaging under about 1.6 counts a channel crosses it, and its caller cannot `allow` it, while a refused `allow` is dropped in silence. Would change the verdict: a dated ruling that clause 4 excludes errors, written into the record. Alternatively, a refused `allow` that raises or is reported rather than ignored, or `MODEL_FAR_FROM_DATA`'s threshold shown not to fire on a well-fitted low-count pattern.
  *Author:* put to the maintainer at this handover (allow an error, refuse it loudly, or keep it ignored); the low-count `MODEL_FAR_FROM_DATA` case is 2005's threshold.

  **3c. `usable_under`: holds.** Would change the verdict: a package reader other than the caller found calling `usable_under`.

  **3d. `RefinementResult.summary(deliverable=)`: holds, seat missing**: its defaults and `SeriesResult.summary`'s new `levels=None` are not in `DEFAULT_SEATS`, though `print(result)` is the more-read path. Would change the verdict: none on the behaviour. The table gap closes by seating `rietx.schemas.results.RefinementResult.summary` and `rietx.schemas.sequential.SeriesResult.summary`.

  **3e. `rx.diagnostics_summary`: holds.** Ranking by rows lets a pair-keyed code dominate, but `n_results` rides beside it. Would change the verdict: a field added that turns a rate into a verdict, for example a "noisy code" flag above a fraction.

  **3f. The suite metric: holds as a prompt**, but the eight standards are four families (the four `qarr` round-robin pure phases share one instrument; NAC and the LaB₆ capillary are both 11-BM), so "fired on 4/8" is one family. Would change the verdict: a family key per standard in the pin, so a rate reads "1 of 4 families" where that is the truth.

  **3g. The silence registry: holds as a harness**: it verifies rather than validates, its fixtures sit far from the thresholds, and the enforced half left out errors. Would change the verdict: the enforced half widened to `response="error"`, a sentence saying a pair verifies and does not meet the mechanical ground, and a silent fixture placed near each threshold.
  *Author:* the enforced half now covers `error` and the docstring says a pair verifies; fixtures near each threshold are left to the audit that tiers each code.

  **Next**, in order:
  1. The agent round's result from [its session](#local_346f1fb3-fdd7-48da-ace8-6aa909d0fef0)
     (`agent-round-2037`, branch `agent-round-quiet-view`; it registers in
     `tests/ev*_report_agent/PROTOCOL.md` before running and touches nothing here). Record
     its rates beside the v1.3 baseline. A worse result than its registered threshold
     reverts clause 3's quiet default and keeps the ordering (Decision 3). Merge its branch
     here only on the maintainer's word.
  2. Tick task 11 and close (✅), moving the narrative to v1.10's record.
  3. Then WP-2003, the maintainer's order.

- **2026-10-24** — first session (began 2026-10-23), nine of the fourteen tasks.
  A fit's diagnostics now print by what they mean for the caller's purpose. With no
  purpose declared, `print(result)` and `ref.summary()` print errors in full and every
  other row as one line naming the purposes it is a warning under, closed by a sentence
  saying how to see more; under `deliverable=` the rows that bear on that purpose print in
  full and the rest are one line each. Which purposes a row bears on is derived from the
  parameters its `where` names and a table of eight purposes' parameter dependencies,
  never written per code, and a code the audit has not yet given a response keeps its
  warning under every purpose, so the view grows quieter only as 2004-2007 audit each
  code. The record's demotion shape is reversed (a demoted statistic is a field whose
  explanation now has a seat in `rietx.help`), FAP's rounding snap is gone, and four new
  deliverables exist. Not done: the caller override, the batch aggregate, the silence
  harness, the four-family counts and the registered agent run that is clause 3's
  tripwire, which has not been made.

  *Done* (each item ticked in its commit): the record (`a34a491`); the result-field help,
  89 entries keyed `Type.field` with `rietx.help.explain` answering them (`78ecfd0`;
  `rx.explain` was not added as a top-level export, `rietx.help.explain` being the
  spelling the skill already cites; the arm got its own manual page,
  `reference/result-fields.md`, because on `settings.md` it broke the page cap); the
  response column, `RESPONSE_BASELINE`, `rietx.purposes` and the meta-tests (`7faeb38`);
  `level_under` (`72fc68a`, `cbc036d`); the view and its four renderers (`b6d3430`;
  `write_html` renders no diagnostics, so the HTML renderer is the notebook form); the
  deliverables (`1583796`); the snap floor (`e6d90c0`, `00a7f69`); the skill's § 4
  sentence (`66feba2`); tutorial 02, its notebook and the landing panel (`1174cbf`); the
  `hold` guide (`79bb977`); the review's fixes (`af9fbfe`) and the generality review's
  (`386516c`); main merged (`db69b83`). No `### Inherited` to prune; the Findings named
  no file that had moved since `5d64a86`.

  *Decisions this session made, for the maintainer to reverse if wrong.* `qpa` depends on
  extinction and the cell (W = S·ZMV) where the mock-up's did not; `PATTERN_UNDERSAMPLED`'s
  scope is `qpa, structure, microstructure, calibration`, wider than the mock-up's two,
  because undersampled peaks fix widths poorly (McCusker et al. 1999 §2 is the
  five-steps bar the tree cites); `structure` reads the atoms' coordinates, occupancies
  and ADPs and the cell, not a moment; a `vars.` path bears on every purpose (WP-1342);
  `series` follows every path and is left out of the printed "warning under" list, where
  it would say nothing on a single result; and the view derives a level only for a code
  with a response (the generality review's finding). **WP-2039 (#1143) merged the same
  day** with every notebook form one `<pre>` carrying each code's explanation as
  `means:`; the two hold together in `db69b83`: a notebook prints the view's rows, every
  row with its `means:`, so a notebook still explains each code while `print` stays one
  line a row.

  *Measured* (`[dev]` venv, Linux x86-64 cloud container, 4 cores, nothing else running):
  the fast selection on the final tree (`386516c`, main merged at `db69b83`) gives `1
  failed, 11386 passed, 277 skipped, 27 xfailed` in 40 min, the one failure being
  `test_examples.py::…[moment]`, which fails here without this branch too. No base was
  measured on this machine, so the +N check is the added-tests tool's own count: 52 added
  cases, 7.2 s in all (`tests/test_summary_deliverables.py` 3.6 s for 15,
  `test_audit_table.py` 3.4 s for 6, every other file under 0.2 s), none near the tail.
  The full selection did not run: the change moves FAP's Ca1 by 3.3e-11, and the slow
  FAP acceptance is the nightly's. Vitest 590 passed, svelte-check clean.
  20 of 257 codes raise at more than one level or a computed one and 8 more through a
  helper `diagnostic_index` cannot read; all 28 stay on the baseline until split. The FAP
  tutorial fit prints, with no deliverable: `diagnostics: 3 rows, 0 errors; no
  deliverable given, so none is printed in full`, then `FLOOR_HIT at
  phases.0.extinction: warning under qpa, structure`, `RESOLUTION_UNCONSTRAINED at
  instrument.profile.u, .v, .w: warning under microstructure, calibration`,
  `PATTERN_UNDERSAMPLED: warning under qpa, structure, microstructure, calibration`, and
  the reading rule; before, four rows in full under "4 unresolved" (examples.md § 1). The
  snap floor moved the `hold` guide's free-fit cell on this machine from 348.5 to 351.9
  ppm (macOS read 281 and 324). Lanes:

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | main $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | help-seat | 35 | 131 | 240K | 83K | 0K of 32K | 57 | 117K | 20 | 0 | 9.14 | 5.49 | 18.81 | +1.66 |
  | deliverables | 30 | 82 | 407K | 83K | 0K of 1K | 14 | 18K | 3 | 0 | 4.99 | 1.43 | 12.52 | +5.87 |
  | filter-renderers | 45 | 136 | 430K | 84K | 0K of 10K | 23 | 66K | 1 | 0 | 18.82 | 2.89 | 21.43 | -0.77 |
  | landing-tutorial | 20 | 35 | 496K | 115K | 0K of 0K | 22 | 22K | 3 | 0 | 2.74 | 2.61 | 5.39 | -0.02 |

  Kept: snap-floor (est 15, 42 requests at 278K), level-under (est 10, 8 at 395K). The
  audit-column lane (est 30) ran and is absent from the tool's table. Actual/estimated
  requests 2.77; the selective policy's row: `lane when main > 150K and item >= 20
  requests | 3 | -9%`.

  *Gotchas.* The GUI's collapsed rows were checked under jsdom only (no playwright in
  the container). Notebooks other than 02 still carry the old "N unresolved" outputs;
  `build.py` refreshes them and no test compares outputs. `examples/guides/moment.py`
  fails on this machine with and without this branch (`steps[0][0]` = 0.1034 against
  `< 0.10`), handed to WP-2036's Inherited. A container restart mid-session stopped one
  lane, which resumed from its transcript.

  *Generality* (the `generality-review` judge on the branch at `db69b83`: the first section's
  table verbatim, every verdict and would-change line verbatim, the other tables condensed
  to their findings; the author's answer follows each `weak`):

  ### `rietx.crystallography.cif.CIF_PRINTED_ROUNDING` (constant, tier 1, 0.5), with the reader action it gates

  **holds.** The case for acting is stronger. Inside a file's own printed rounding, the snapped value and the printed one are the same number as far as the file can say. In the stated space group the site cannot sit anywhere else.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | "a snap onto a special position that moves every coordinate of a site by no more than that is the file's own rounding … and is not reported" (cif.py comment on the constant) | Two things change. (a) `_read_rounded_sites_on_position` rewrites the stored x, y, z onto the special position and records nothing. (b) `_snap_to_stated_multiplicity` still moves the site but drops it from `SITE_SNAPPED_TO_SPECIAL_POSITION`. The move is bounded twice: the orbit tolerance `SITE_TOL` = 1e-4 in (a), or `CIF_STATED_MULTIPLICITY_SNAP_TOL` = 1e-3 plus the file's own stated multiplicity in (b), and in both cases half the last printed digit. The multiplicity was already the special one before this change. So no fitted number moves. What goes is the report, plus a stored-coordinate change below the file's own precision. | — |
  | 2. Kind | Tier 1, "Arithmetic, not a choice" (row evidence) | Kind 1 is right, and so is tier 1 for the 0.5. A constant row states no `ambiguity`, and none is required. | holds |
  | 3. Case against | none given | I tried to name a dissenter. Someone testing a small displacement off a special position would refine in the lower group, where the site is not special, so this never applies to them. Within the stated group, a site 3.3e-11 off a special position is an orbit of coincident atoms, which is physically impossible. One limit the row does not state: a file written by **truncating** rather than rounding has the interval [print, print + 1 digit), not ±0.5. Such a file errs toward *still reporting* (2/3 truncated to 0.6666 is 6.7e-5 off, past 5e-5), so the failure is safe. | none found |
  | 4. Case for | the FAP case: Ca1 `0.3333333333` snapped 3.3e-11 and warned (WP Context; examples.md § 1) | Strong. One of the four warnings the worked default printed was rounding. | strong |
  | 5. Tier and source | Tier 1. Evidence cites `_within_printed_rounding`, computed in exact decimal, and `tests/test_cif_stated_columns.py` | The three tests exist and the last covers the tie (1/8 printed `0.12`) and the lattice translation. Scope: only CIF input gets this. The fit-time check still fires on a structure from a GSAS `.EXP`, a TOPAS file or code that prints `0.33333`, since no printed digits exist there. | holds |
  | 6. Families | tests on `tests/data/fluorapatite.cif` and edits of it | One file, with synthetic variants. A tier-1 item needs no families. | n/a |
  | 7. Record of firing | "is not reported" (constant comment) | No field and no diagnostic record the rewrite. Defensible here, because the move is inside the file's own precision; it matches the `CIF_ANGLE_CORRECT_MAX_DEG` precedent. A move past rounding still fires `SITE_SNAPPED_TO_SPECIAL_POSITION`. | holds |

  Would change the verdict: a CIF on disk whose writer truncates its coordinates, or a real site the reader silences that the source says is off the position.

  ### `FLOOR_HIT`: `response="warning"` and its sentence

  **holds.** The response copies the level every raise site already passes. The sentence matches the code's help text. The tier stays `unaudited` and the name stays on `UNAUDITED_BASELINE`. (Case against, weak: on FAP the floor is extinction on a lab powder at ρ = +0.057, yet it reads as a warning under qpa and structure; the rule puts magnitude in the message rather than in a level, so this is the rule's cost, not a defect of the row; WP-2004 has inherited it.)

  Would change the verdict: a raise site that passes another level, or one that passes no `where`.

  ### `PATTERN_UNDERSAMPLED`: response, sentence, `scope=("qpa","structure","microstructure","calibration")`

  **weak.** The response copies the raise site. But the scope leaves out two purposes the row's own sentence covers (`magnetic`, whose moment is intensity-derived, and `series`, which the purpose table says follows every path). The reason given for widening the scope is not in the row and does not match the section this repository cites (McCusker 1999 §2 in `background/diagnostics.py:221`, not §3). And the sentence asks more than practice does: FAP sits at 4.6 steps per FWHM, yet GSAS-II's own converged fit of it is quoted from.

  Would change the verdict: `"magnetic"` and `"series"` added to the scope (or a stated reason each is left out), and the §3 citation written into the row and checked against the paper.

  *Author:* `series` now reads every code (`386516c`); the sentence now says what the help says, "read … as less certain than its esd, and re-collect … where it must be quotable" (`386516c`); the citation is §2, corrected above; `magnetic` is next action (1), because it changes tutorial 02's printed line.

  ### `RESOLUTION_UNCONSTRAINED`: response and sentence

  **holds.** It copies the raise site and its suggestion. One gap: under the calibration purpose the sentence's advice ("calibrate the instrument on a standard first") is circular; that follows from one sentence per code.

  Would change the verdict: a calibration fit on disk where this fires and the printed advice is followed.

  ### `SITE_SNAPPED_TO_SPECIAL_POSITION`: response and sentence

  **holds.** It copies both raise sites. `where` = `phases.i.atoms.j` matches qpa, structure and magnetic once the globs are cut to that path's depth, and not cell, phase_id, microstructure or calibration: the right split for a multiplicity.

  Would change the verdict: a raise site whose `where` keeps a bare atom label.

  ### `WALKED` gains `"purposes.py": 2004`

  **holds.** Walking it costs nothing and catches any number added later. Today it holds no module-level number, so the walk sees none of its real heuristics; those are judged under the purpose table.

  ### `RESPONSE_BASELINE` (new, 253 names, shrink-only)

  **holds as a baseline.** A new column opening on existing rows. 257 code rows minus the 4 given responses = 253. One side effect, judged under `level_under`: baseline codes that carry a `where` already get levels derived per purpose, with no one having checked them.

  ### `rietx.purposes.PURPOSES`

  **weak.** Each row cites physics, but four rows break the logic another row uses, each turning a real warning into `info`: (a) `structure` leaves out the cell (`CELL_RUNAWAY` reads info under structure; distances depend on the cell); (b) `magnetic` keeps the scale but leaves out extinction, Biso/ADPs and occupancy, which `qpa`'s own `why` says trade against the scale; (c) `calibration` leaves out the phase broadening that adds to the instrument widths; (d) `cell` leaves out axial divergence; weaker, (e) `qpa` leaves out coordinates and DOFs, which also set |F|². Nothing checks that the table is *complete*. No program in `docs/practice.md` keys levels to a declared purpose (not checked against the programs).

  Would change the verdict: the cell glob added to `structure`, scale-trading terms added to `magnetic`, phase broadening added to `calibration` (or a written physics reason for each omission), and the before-and-after counts on the four families.

  *Author:* (a), (c), (d) and (e) landed in `386516c`; (b) is next action (1), with the tutorial rebuild it forces.

  ### `schemas.results.level_under`

  **weak.** The fallbacks are careful, but it already demotes codes nobody has given a response (`CELL_RUNAWAY` printed `info: …` under `deliverable="structure"`), contradicting its own WP-1076 sentence, and it reads a code with a declared scope as `info` under `series`.

  Would change the verdict: the derivation limited to codes with a response, or every `where`-carrying baseline code checked, plus `series` handled for scoped codes.

  *Author:* both landed in `386516c`: a code still on `RESPONSE_BASELINE` keeps its warning under every purpose, and `series` reads every code.

  ### `diagnostic_view` / `_diagnostic_lines`: the no-deliverable view prints every warning on one line

  **weak.** This demotes what is shown. The case for showing more is the stronger side, and the WP's own tripwire has not been run: (a) agents stopped on a stated criterion seven times in eight, never without one, and the quiet view stops stating it; (b) the magnitude is withheld from the print; (c) the closing sentence says "pass deliverable=", but `RefinementResult.__str__` and a result read back from a project accept no such argument; (d) the registered agent run Decision 3 calls the tripwire has not been made. The rounding row that half the case for quiet rested on is now gone through `CIF_PRINTED_ROUNDING`.

  Would change the verdict: the registered `tests/eval_report_agent` run comparing the current view with the split view, plus a deliverable-aware print on `RefinementResult` itself.

  *Author:* the quiet default is the maintainer's 2026-10-23 ruling with the agent run as its tripwire (Decision 3); (c) is next action (1); the run is next action (4) and needs the maintainer's approval of its spend.

  ### `Refinement.summary(deliverable=…)`: the four new deliverable blocks

  **weak.** The cell and magnetic blocks only print fields the result already has. The microstructure block replaced every size and strain reading with "not quotable" whenever `RESOLUTION_UNCONSTRAINED` fired, and the calibration block told any fit whose cell refined to hold it, which is wrong for an internal-standard calibration.

  Would change the verdict: the calibration line limited to the standard's own phase, and the microstructure block printing its readings under the caveat rather than in place of them.

  *Author:* both landed in `386516c`: the readings print under the caveat, and the calibration line names the phases whose cell refined and says a sample's may.


  **Next**, in order: (1) the judge's open items, done with one rebuild of tutorial 02
  and its landing panel because each changes what it prints: `magnetic` gains the terms
  that trade with the scale (extinction, ADPs, occupancy), `PATTERN_UNDERSAMPLED`'s scope
  gains `magnetic`, and the reading rule must be followable on a bare result, which has
  no `deliverable=` (a `RefinementResult` view method, or a rule naming
  `Refinement.summary`); (2) the caller override, task 7, small; (3) the silence harness
  and the batch aggregate, tasks 9 and 8, the aggregate run over the acceptance suites
  being the suite metric; (4) the four-family before/after counts and the registered
  agent run on `tests/eval_report_agent` (task 11), whose spend the maintainer approves
  before it is made; (5) task 13's count check.
- **2026-10-23** — created from the proposal ruled on that day. No open WP owns the
  view: 2003 owns the chain's demotions and takes the shape this sets, 2004 the report's
  codes, 2008 the skill, none the summary's rendering, the level column or the purpose
  key. Companion: `2037-attention/examples.md`, the before blocks measured on `main`
  (5d64a86) with the skill's worked default on FAP.
