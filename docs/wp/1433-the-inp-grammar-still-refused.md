# WP-1433 — the `.inp` grammar the reader still refuses: `STR(...)` and `#if`

Milestone: unscheduled · Status: ✅ 2026-10-03 — both constructs read (PR #587), shipped in 1.6.0; four `STR(...)` files stop at rigid bodies, which is WP-1514's
Track: Coming from another code
Depends on: — (WP-1118 closed 2026-09-16 and handed these two over; WP-1119
settled that neither needs an expression language)

## Goal

`read_topas_inp` reads the two constructs it refuses today. A file whose phases
open with `STR(...)` builds those phases. A file whose live text is chosen by
`#if` over `#prm` hash parameters reads the branch TOPAS read. Both live
entirely in `io/projects/topas.py`, and § Non-goals keeps WP-1118's fence: this
is not a TOPAS-compatible macro engine.

## Context

**Both refusals are correct, which is why they are a WP rather than a bug.** A
reader may decline a construct. It may not describe it as absent. Each refusal
below raises `TopasInpError` naming what it saw and counting it, so what is
missing is reach rather than honesty. The value is in the files: a refused file
is one nothing downstream has measured, so every incidence figure PR #98
recorded is a floor.

### `STR(...)` — issue #107, and an offer standing since 2026-09-01

Seven archive files open phases with the macro form `STR(R-3)` /
`STR(######, "#name#")`, which the line-based block split cannot see. PR #98
took the minimum honest fix: `_STR_MACRO` (`topas.py:1871`) raises, counting the
phases the file states, where the reader used to parse **zero phases** and let
`to_structure` answer that a Pawley or indexing-only `.inp` is legal and has
none.

Two counts are on record and they count different things. Issue #107 says five
archive files parse zero phases. PR #98's test names seven carrying the form:
`archive file 14`, `archive file 15`, `archive file 16`, `archive file 17` and
three variants of `archive file 18`. Settling that is a
pass over the private archive, and it is the first measurement here.

What is undecided is the shape of the fix. Expanding `STR(...)` as a special
case and growing a general macro pass are both open, and the reference is what
decides it (§ What the reference says below). WP-1119 removed the reason to
fear the second: it shipped `Refinement.add_variable` and deliberately no
expression string, so a macro pass here needs no expression language of rietx's
own.

The issue's filer offered either fix once told which, and the offer stood when
WP-1118 closed.

### `#if` over `#prm`, where the incidence is small and the files are the dear ones

`refuse_unevaluable_directives` refuses `#if`/`#elseif`, quoting the reference
on what they test. Two corpora disagree about the cost:

- The 606-file archive: **1 file**.
- The Durham workshop archive `zrmo2o8_vt.zip` (four `.inp`s): **three refuse**
  at their first `#if`, and they are the multi-pattern reel files. That shape is
  what all six agents of WP-1110's round named as the hardest part of the work.
  WP-1130 got its model by stripping the `#if`/`#endif` blocks in a scratchpad,
  which is a workaround no user should have to invent.

So this buys few files and the ones it buys are the expensive ones. Scope it to
deterministic integer conditions over `#prm`: `#if (#out pattern_count > 1)` and
the `Run_Number` guards are most of what these files use `#if` for.

### What the reference says, measured 2026-09-16

**The Technical Reference is public and fetchable, and an earlier note here that
no session had §19 was wrong.** `https://topas-academic.com/technical_reference`
returns the whole v8 reference as one 10.8 MB page, `curl` with no headers
beyond a user agent. `ATTRIBUTION.md`'s TOPAS row already cites §19's directive
list and §19.3.2's lattice macros with content, so the document was in hand all
along. Cite by directive name as well as by number: the fetched page numbers
`#m_unique` at §21.1.5 while the repo's rows cite §19, so the chapter numbering
moves between editions.

§19.1.2, *Pre-processor equations and `#prm`, `#if`, `#elseif`, `#out`*, is the
whole specification for the second half:

- A `#prm` is a **hash parameter**, evaluated at the pre-processor stage. The
  reference says it is "totally separate to parameters defined using `prm`" and
  unknown to the kernel. So `symbol_table` is the wrong table to reach for. The
  hash namespace is its own, and mixing the two would read a kernel parameter's
  value into a pre-processor condition.
- A `#prm` may be a function of other `#prm`s. Its value may be a number or a
  string.
- The form is `#if E;` … `[#elseif E;]` … `#endif`, and the reference's own
  worked example uses `And(space_group_number >= 75, space_group_number <= 142)`.
  So the condition grammar needs comparisons, `And`, and nothing like a full
  equation language to reach the archive's cases.
- `#out name` substitutes a `#prm`'s value into the pre-processed text at that
  point. The workshop files' `#out pattern_count` is this.
- **Not every condition is decidable, and the reference says so by example**:
  `#prm ran = Constant(Rand(0,1)); #if ran < 0.5;` is legal. A condition
  reaching `Rand` has no answer a reader can give, so it stays refused by name.
  That is the existing rule, narrowed rather than lifted.
- `#m_if`/`#m_elseif`/`#m_ifarg` are the macro-expansion-time family (§19.1.4).
  They are already refused as the `#m_*` class and stay that way unless the
  `STR(...)` decision needs them.

### The seam

`io/projects/topas.py`, and nothing above it. The pieces a change here meets:

- `refuse_unevaluable_directives` — the class refusal, stated once over the
  pre-processor rather than per file. Five rounds of this reader treated
  `#ifdef` as one more spelling before that rule landed.
- `resolve_ifdefs` / `_masked` — the `#ifdef`/`#ifndef` family, resolved by
  blanking dead branches, token-scanned rather than line-anchored. An `#if`
  evaluator joins this mechanism rather than adding a second one.
- `_STR_MACRO` — the refusal to replace.
- `symbol_table` / `_symbol_reads` / `_resolve` / `_arith` — kernel `prm`
  arithmetic. Read them for the shape and not for reuse, per § the reference
  above.
- `coverage.py` — one declared `Stance` per construct, with `SPEC` naming the
  edition each stance was written against. A construct that changes stance
  changes its row there too.

### Fences

TOPAS is closed source, so the reference is the specification and no code or
`Topas.inc` macro **body** may be reproduced, in code, comments, tests or docs
(`ATTRIBUTION.md`, `io/CLAUDE.md` § Adding a format step 2). The 606-file
archive is the maintainer's research data and is not redistributable, so a
fixture is synthesized inline with a comment naming the archive idiom it stands
for. The workshop zip is public at
`http://topas.webspace.durham.ac.uk/wp-content/uploads/sites/261/2026/04/zrmo2o8_vt.zip`
and is not committed either.

## Non-goals

- **Not a TOPAS-compatible engine.** No general equation evaluator, no
  `fit_obj`, no macro library. A construct with no model here is reported.
- **Not `#include`/`#ingest`/`#external_INP`.** No care with the bytes in hand
  recovers bytes that are somewhere else.
- **Not `#ifdef !name`.** The reference describes no `!` form, and the two
  readings are opposite, so it stays refused unless a later edition settles it.
- **Not the writer.** `write_topas_inp` writes no macro and does not learn to.
- **Not `to_structure`'s hkl-strain arm.** A `spherical_harmonics_hkl` block
  converts to `Phase.microstrain`, which WP-1118 fenced as a conversion with its
  own consequences (freeing it can make other phases `PHASE_UNCONSTRAINED`).

## Tasks

- [x] Re-measure the two `STR(...)` counts on the archive, and decide the shape
      of the fix against §19 with the reference's own words behind it. Write the
      decision in this file (#107).
- [x] `STR(...)` expands, and the files that carry it read their phases.
- [x] A `#prm` evaluator for `#if`/`#elseif`, scoped to deterministic integer
      conditions with `And` and the comparisons, refusing `Rand` and every
      string condition by name. `#out` substitutes where a condition needs it.
- [x] Re-measure PR #98's incidence floors once both land, and record what the
      reader still declines, in `coverage.py`'s stances and here.
- [x] Tests, with every fixture synthesized inline and its archive idiom named;
      obs/calc/diff PNGs for any refinement a fixture drives.
- [x] Skill: a row only if a new diagnostic code lands. These refusals raise
      rather than diagnose, and `SKILL.md`'s routing row already sends a foreign
      file to `references/api.md` § In.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_projects_topas.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The bar is files rather than tests. The `STR(...)` files build the phases they
state, and `d8_01612_vt_reel_02.inp` reads from the workshop archive as it
ships, at the model WP-1130 got from its stripped scratchpad copy.

## References

- Coelho, A. A., *TOPAS-Academic Technical Reference* (v8),
  `https://topas-academic.com/technical_reference` — §19.1.2 (`#prm`, `#if`,
  `#elseif`, `#out`), §19.1.4 (the `#m_*` family), §19.3.2 (the lattice macros),
  §1.2, §2.1, §5.1.
- Coelho, A. A. (2018), *J. Appl. Cryst.* **51**, 210 — TOPAS and
  TOPAS-Academic.
- Issue #107. [1118](1118-foreign-model-files.md) § Context (closed 2026-09-16),
  [1130](1130-background-reference.md) § The trigger dataset,
  [1110](1110-agent-surface-friction.md) § "Found by the round" item 19,
  [1119](1119-named-variables.md) § Decisions 4.

## Handover log

- **2026-10-03** — **Closed, by the maintainer's call.** The entry below left
  it open: every task is done, but four archive files the reader can now open
  stop at `to_structure` because they hold rigid bodies. That remainder is
  rigid bodies, not the `.inp` grammar, so it is forwarded to WP-1514's
  Inherited and this WP closes. Narrative moved to the v1.7 record.

- **2026-10-01** — Both halves landed from outside. `STR(sg)` and
  `STR(sg, name)` expand to the `str` block they open, and `#prm`, `#if`,
  `#elseif` and `#out` are evaluated in the same token pass and frame stack as
  `#ifdef`. *Done:* PR #587 (`6759a772`, three review rounds), merged as
  `38a6e249` by `/pr-review`.
  *Decision* (task 1, the shape of the `STR(...)` fix): a special case, not a
  macro pass. §19.3.12 documents `STR(sg)` by its effect, which is all a
  clean-room reader may use, and a general pass would need macro bodies that
  `ATTRIBUTION.md` fences. Every macro-opened phase in the archive is this one
  macro. The second argument is read as the phase name from the reference's own
  example inputs; no archive file this makes readable uses it.
  *Measured* by the contributor over the 462 of 606 archive `.inp` files that
  were present: the two `STR(...)` counts reconcile as 7 live calls, 5 with a
  real space group and 2 template slots. PR #98's floors moved read 385 → 390,
  refused 77 → 72, phases 625 → 629; `to_structure` stays at 269. The one `#if`
  archive file now passes the evaluation and refuses at `#ifdef !name`, a
  non-goal. On the public workshop zip, 3 of 4 files read where 1 did, and
  `reel_02` as shipped gives JSON byte-identical to its `#if`-stripped copy.
  New: `TOPAS_FIRST_RUN_READ` when `num_runs` states more than one run, and
  `coverage.PREPROCESSOR`, a stance table a test holds to the reader.
  *Still declined:* `Mod`, `Rand`, strings, `#ifdef !`, includes and `#m_*`
  refuse by name; four newly read files stop at `to_structure` as rigid bodies
  (WP-1514). *Gotchas* from review: Table 3-1's implied multiply (`x y` =
  `x*y`) refuses rather than ending a condition at its first name, and an
  unknown character refuses wherever the parser reaches it. Every task is
  ticked, but the acceptance bar is not met in full: the `STR(...)` files read
  their phases, and four of them stop at `to_structure` as rigid bodies.
  *Next:* the maintainer's call, close here or hold for WP-1514.

- **2026-09-16** — created as WP-1118 closed, taking the two task lines that
  outlived it. The session that filed it fetched the Technical Reference to
  check whether the `#if` half was blocked on a document nobody had, which is
  what WP-1118's last entry recorded. It is not: the reference is public, §19.1.2
  is the whole specification for `#prm`/`#if`, and its facts are in § Context
  above. Neither half is blocked on anything but a session.
