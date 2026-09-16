# WP-1314 — a Jana2020 project reader: .m50/.m40/.m41

Milestone: unscheduled · Status: ⬜
Depends on: 1118 (its first task — the model-format registry and the answer's shape)

## Goal

Reading a Jana2020 m-file triplet — `.m50` (cell, symmetry, structure
metadata), `.m40` (atomic parameters), `.m41` (powder profile/instrument
parameters) — returns the model it describes under the WP-1118 contract: the
`Structure`/`Instrument` pair plus the refine flags, carried faithfully or
refused by name, never silently defaulted. Jana is the remaining major
Rietveld code with no import route.

## Context

From issue #147 (filed in the #130 proposal channel as a list entry, scoped
here).

**The contract is WP-1118's, restated short.** The refine flags are the
payload, not the numbers: which parameters were free, which held, what was
excluded. A construct the reader does not carry is reported by name; one
that would change the answer is refused ("the stated-key rule the TOPAS
reader's five review rounds established"). The answer takes the same shape
as the sibling readers — whatever 1118's first task decides (model + vary
set, or a `Project`) — which is why that task gates this WP.

**The files are plain text and documented in Jana's own manuals.** That
makes this a spec-only format in the io/ sense: layouts written from
documentation with any source file closed, provenance in `ATTRIBUTION.md`.

**The honest difference, said at the top rather than discovered at
acceptance: validation inverts.** A bounded sweep of the archive that
grounded the TOPAS reader (606 solved `.inp`) and the FullProf reader (six
`.pcr`) found **zero** Jana m-files. So the evidence is: Jana2020's own
distributed example suite (licence checked per file before any vendoring;
synthetic fixtures otherwise), the `io/CLAUDE.md` perturbation-fuzz
discipline (`test_readers_robust.py`), and cross-code number checks against
published Jana refinements. Weaker than the siblings', and the WP says so.

**The refusal is the deliverable for Jana's speciality.** Modulated and
composite structures are what Jana is *for*, and superspace groups are a
schema rietx does not have — so an `.m50` declaring modulation is refused by
name, exactly as the TOPAS reader refuses magnetic space groups. A user with
such a file is told what they have, not handed a truncated model.

**The writer rides the reader's tables, later.** Issue #148 pairs each
writer with its reader so both land against one spec table; Jana's writer is
the lowest-priority of that family until this reader has fixed the tables.
It is this WP's final, explicitly-later task, and its consumer is the
handoff workflow (refine here, finish in Jana for modulated work / charge
flipping).

### Inherited

- **2026-09-16, from [1118](1118-foreign-model-files.md): the registry has a
  binary member now, and two of its rules are yours to inherit.** The GSAS-II
  `.gpx` reader went in first in `PROJECT_FORMATS`, because every other sniff
  decodes the head with `errors="ignore"` and meets a binary file as text with
  its bytes dropped. Two rules landed in `io/CLAUDE.md` with it and neither is
  about pickles. **A binary format's sniff is not its magic bytes**: 11 of 34
  real `.gpx` files carry no protocol header, so the test is "opens as one *and*
  names one of its own labels", and a Jana `.m50` claimed on a first line should
  expect the same kind of exception from its own writer. And **every schema
  object a conversion builds is built in one place, inside one guard**, so a
  pydantic `ValidationError` cannot reach a caller naming a `Parameter` instead
  of the file — `gsas2.to_structure` closes the class `read_gsas_prm` opened,
  and a `.m40` full of real refined values will find the same edges (a negative
  displacement parameter, an occupancy outside the schema's range).

- **2026-09-15 (2nd session), from [1118](1118-foreign-model-files.md): one
  vendor's several file kinds read a record through one function, and
  `io/CLAUDE.md` now says so.** A `.prm` and a `.EXP` are both GSAS, and their
  instrument records are the same records under different four-character keys.
  This package parsed three of them two ways for a milestone. The corpus hid
  it, because a whitespace split is right only while two optional fields stay
  blank. GSAS's grammar now lives in `io/projects/gsas.py`, public, and the
  `.prm` reader a package away calls it. **Staying outside the registry is
  about dispatch and never about parsing**, which is the clause aimed straight
  at a `.m50`/`.m40`/`.m41` trio: however this WP decides to claim the set, the
  three files want one Jana grammar module between them. Second rule from the
  same session, and the one no test runs: **a refusal's reason can expire**. A
  parser's reads are tested and its refusals are prose, so "no file establishes
  this" sat in the `.prm` doublet refusal long after the file establishing it
  had been committed. Audit the refusals whenever the parser gets sharper.

- **2026-09-15, from [1118](1118-foreign-model-files.md): the registry has a
  third member, and it moved a seam a Jana reader will meet.**
  `ProjectFormat.reports_at` is no longer two-valued — the GSAS `.EXP` reader
  repairs both while parsing and while building, so it declares `"both"`, and
  either single value would have dropped one channel in silence. Decide which
  end a `.m50`/`.m40` reader repairs at **before** writing it, and note that the
  meta-test now partitions both ways, so a channel that exists and is not
  declared fails rather than going quiet. Two smaller things worth copying: a
  fixed-format record is read by **column** and never by splitting on
  whitespace (a blank optional field re-assigns every token after it), and a
  sniff measures the head's **bytes**, because `head()` decodes UTF-8 with
  `errors="ignore"` and drops any byte that is not valid UTF-8.

- **2026-09-13, from [1118](1118-foreign-model-files.md): the registry this WP
  was gated on exists, and a Jana reader now has four things to fill in rather
  than a shape to invent.** `io/projects/registry.py` holds `PROJECT_FORMATS`,
  an ordered tuple whose order is behaviour, reached through
  `read_project_model`, which dispatches on **content**. A new member declares
  `name`/`title`/`extensions`/`sniff`, a `carries` list saying in words what the
  file holds beyond a structure, a `reports_at` of `"read"` or `"build"` saying
  which call takes a caller's diagnostics list, and its `matches`/`read`/
  `to_structure` callables; `refuses` stays `None` unless the format is
  recognised in order to be declined. Four consequences for this WP. (1) The
  answer stays the format's **own** model — a `JanaModel` beside `TopasModel` —
  never a shape shared across formats with a blank where a file is silent, which
  is the rule that decided the registry. (2) A `.m50`/`.m40`/`.m41` trio is a
  file *set* and no member declares a sniff for one, so how the trio is claimed
  is this WP's first question and the registry does not answer it: `matches`
  takes one path. (3) The member's `read` must be a top-level `rx.` export, and
  that fires two documentation gates the moment it lands —
  `tests/test_manual_api.py` on the public surface (`rietx.io.projects` is
  declared provisional, so the models inherit that tier, but the verb still
  needs a Part 1 chapter row) and `tests/test_skill.py` on
  `docs/skill/make_api_index.py`'s `SECTIONS`. (4) `io/CLAUDE.md` § Project
  readers now carries three further rules, all of which govern this reader.

- **2026-09-01, from [1118](1118-foreign-model-files.md): the package this
  reader belongs in now exists, and so do the two rules that govern it.**
  `src/rietx/io/projects/` landed with the TOPAS `.inp` reader (PR #98) — one
  module per format, exporting only format-named entry points, with the
  model→`Structure` conversion kept *module-level* (`projects.topas.to_structure`)
  precisely so a sibling format's `to_structure` cannot shadow it through the
  package export. `src/rietx/io/CLAUDE.md` § Project readers carries the two
  standing rules to follow here: **derive the obligations from the specification
  and use real files only to corroborate** (three of the TOPAS reader's six
  grammar corrections were invisible to any archive sweep, so a sweep-and-fix
  loop finds one dialect's bugs and never the silent ones), and **a project
  reader refuses where a pattern reader would repair**, because its output is a
  whole model and a caller cannot see which part came from the file.
  The mechanism both rest on is worth copying rather than reinventing:
  `io/projects/coverage.py` declares one **stance** per construct of the format
  (read / ignored / reported / refused) with the argument for it, and its scope
  table is partitioned by test against the format's own keyword tree, so a
  construct with no stance fails rather than being dropped in silence.
  **What has still not landed is the thing this WP depends on**: there is no
  `PROJECT_FORMATS` registry beside `PATTERN_FORMATS` and no `capabilities()`
  arm — `read_topas_inp` is reached by importing it, and whether these readers
  become top-level `rx.` exports is still open. 1118's first task, unchanged.

## Non-goals

- **Not single-crystal projects, not `.m90` data files.** Powder protocol
  only; the pattern goes through `read_pattern` as ever.
- **Not superspace/modulated support** — refused by name; a schema for it is
  nobody's current plan.
- **Not Rietica or XND** — issue #196 widens the family beyond the majors;
  recorded on [1118](1118-foreign-model-files.md), deliberately unscheduled.
- **Not the registry design** — 1118's first task owns the shape this
  plugs into.

## Tasks

- [ ] Spec tables for `.m50`/`.m40`/`.m41` from the Jana documentation
      (source files closed; `ATTRIBUTION.md` row), with the refusal list
      (modulation, composites, magnetic) written first.
- [ ] The reader: triplet → model + refine flags under the 1118 contract,
      every uncarried construct named in diagnostics.
- [ ] Fixtures: Jana-distributed examples licence-checked per file, else
      synthetic; perturbation fuzz in `test_readers_robust.py`'s arm;
      cross-check against at least one published Jana refinement's numbers.
- [ ] `capabilities()` model-format arm entry, skill routing-row widening
      (SKILL.md byte budget — see 1118's Inherited), manual section,
      provenance rows.
- [ ] Later, after the tables have settled: the `.m50/.m40/.m41` writer,
      naming what did not cross (issue #148's pairing).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_reader_mfile.py tests/test_readers_robust.py   # first module is new, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: a distributed-example triplet round-trips to a model whose protocol
matches its published refinement field for field; a modulated `.m50` refuses
naming modulation; fuzzed files refuse naming the file, never a parser
exception.

The shipping PR carries `Closes #147`.

## References

- Issue #147; issue #148 (the writer pairing); issue #196 (the family
  boundary).
- Petříček, V., Dušek, M. & Palatinus, L. (2014), *Z. Kristallogr.* **229**,
  345 — Jana2006/2020; the m-file layouts are in its documentation.
- [1118](1118-foreign-model-files.md) — the contract, licence fences, and
  registry this reader plugs into.

## Handover log

- **2026-09-01** — created, from issue #147 (2026-09-01 triage). Settled:
  the contract and the refusal list; blocked on 1118's first task for the
  answer's shape; first own item is sourcing the distributed examples and
  their licence status.
