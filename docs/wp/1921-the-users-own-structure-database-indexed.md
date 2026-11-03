# WP-1921 — the user's own structure database, indexed: is this phase or this cell already known?

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: —
Priority: P3 2026-10-08 — a workaround covers it (the person finds the CIF by hand), and the agent's "is it already known?" check has a named use but no measured cost yet

## Goal

`rietx.refdb` (or the module the maintainer names) builds a local index over
structure files the user already holds and answers three lookups: by formula
and space group, by element set, and by reduced cell. Every answer is a
pointer back into the user's own file, and the package ships no data.

## Context

Issue #813 (mustachefeeling, 2026-10-07) proposes an index builder in four
stages: 1a (`build`, `find`, `cif` over CIF sources), 1b (`find(cell=)` and
`analogues()`), 2 (pattern records from vendor peak-list exports), and 3
(`candidates()`, search-match). This WP takes 1a and 1b. Stage 3 is the
fenced item: ROADMAP § v2+ "Solution" names search-match phase
identification, with the guillemot study's 36-cell screen as its prior art.
Stage 2 exists to feed stage 3.

**The use.** WP-1510's motivating session had the formula, two candidate
cells and an isostructural analogue's CIF in the person's first two
messages. An agent that can ask "is this cell already known?" before
indexing or solving saves that exchange. WP-1515 records a measured caution
from the same session: transplanting the analogue's coordinates did worse
than a blind start. So `analogues()` earns its place as a source of cells and
structure types first. A starting model from it is a hypothesis to test.

**Checked against the tree at 5d1f5f67.** Every piece the issue composes
with exists:
- `crystallography/cif.py` `structure_from_cif`, the full read `cif()` hands
  to.
- `indexing/reduce.py`: `reduce_cell`, `reduced_af`, `equal_reduced_many`,
  `same_lattice`, `CELL_EQUALITY_RELATIVE` = 5e-3, `NIGGLI_EPS_RELATIVE` =
  1e-5. A cell lookup uses indexing's own equality test.
- `Refinement.summary(deliverable="phase_id")` (`refine.py:4999`) and
  `IndexingResult.unmatched_observed_two_theta` (`schemas/indexing.py:1029`).
  These are stage 3's inputs and stay unused here.
- `_about.STATE_DIR_NAME` and `STATE_DIR_ENV`. `$HOME/.rietx` is the
  per-user state the GUI keeps. The working directory's `.rietx/` is run
  telemetry, and its retention deletes by age and size. An index under the
  per-user one is outside that retention.
- Six `tests/data/cod_*.cif` under COD's public-domain dedication, with
  their README rows.

**The prototype's numbers** (the issue's, on one licensed export of 200 809
CIFs, Apple M4, gemmi 0.7.5; none is about an entry's content): build 14.6 s
at 4 workers; index 44 MB with search fields and pointers only; 88 files
(0.044 %) needing a scalar fallback with no sites; `cif()` 0.014 ms after a
405 ms first call; `find(formula=)` 0.2 ms median; Niggli reduction of every
cell 0.2 s. Phase keys at 0.5 % cell tolerance: 149 373 for 136 727
(formula, space group) pairs.

**Licence hygiene is the design** (issue § Licence hygiene, kept here):
- The index stores search fields and a pointer (file, member or offset) and
  the source's sha256. It never stores CIF text. A test asserts no
  `_atom_site` text reaches it.
- The index is written where the user says, by default under the per-user
  state directory. Nothing is written inside the package or the repo.
- Fixtures are COD only, as WP-1324 kept ICSD 18318 out of the tree.
- Proprietary binary databases are read only through the vendor's own
  export. A native decoder is a non-goal.
- Prior art: COD's own tooling and pymatgen's structure matching. Check each
  one's licence before reading its code. A GPL source is concepts only
  (root CLAUDE.md § Licensing).

### Inherited

- **2026-11-03, from the issue triage (#1330): S3 of the standardization
  proposal lands here, as `analogues()`'s identity test.** #1330 proposes two
  levels for "is this the same entry?". First an invariant key: space-group
  number, the Wyckoff sequence with the species on each position, the reduced
  formula and the Pearson symbol. Then a normaliser-aware `compare(a, b)` inside
  each bucket, returning the transform and the largest displacement in Å. The
  tolerance verdict is a heuristic and needs an `_audit` row. Exact equality of
  standardized coordinates is not enough, because Γ-minimal coordinates are
  discontinuous (Parthé & Gelato 1984, Tables 7–8). Checked against the tree at
  62724a30f: `compare` exists in substance. `rietx.solve.cluster.equivalences`
  builds the Euclidean normaliser on a metric, and `align(eq, xa, xb, species)`
  returns `Alignment(rmsd, max_dev, element)`. Its `max_dev` is the largest
  displacement in Å and `element` indexes the transform. It pairs atoms one to
  one per species, so two entries with different atom counts need the key's
  bucket first. Build on it rather than writing a second comparer. The
  standardization itself (S0 in PR #1332, S1 and S2 in
  [2085](2085-a-phase-in-its-standardized-description.md)) is a soft
  prerequisite: the key's Wyckoff sequence reads off a standardized phase.

- **Decided 2026-10-16 (maintainer, from the issue triage, #990): search-match
  stays behind the v2+ fence.** #990's request to unfence it is declined for
  now, and this WP stays at lookup (stages 1a and 1b). Task 1's question (1)
  is answered: stage 3 does not leave the fence.

- **2026-10-16, from the issue triage (#813): the reporter split stage 3 out
  as #990 (their comment of 2026-10-15), and ROADMAP now names #990 at the v2+
  fence; WP-1921 does not.** #990 proposes search-match (`candidates()`) as
  its own WP, sourced from the user's CIFs, a local COD mirror or this index
  "when one exists". It makes WP-1921's task 1 question (1), "does stage 3
  leave the fence or does the module stop at lookup", a question #990 owns
  (its question 1 asks "own WP or this WP's stage 3"). The reporter's reading:
  WP-1921 can stay at lookup (stages 1a and 1b). ROADMAP.md line 555 records
  #990 as held for the maintainer, 2026-10-16. Nothing in the tree moved (no
  `refdb`, `landed references: none`, checked at `2c94d848`). Task 1 question
  (1) should point at #990 and be answered with it.

## Non-goals

- `candidates()`, search-match against a pattern (stage 3). It stays behind
  the § v2+ "Solution" fence unless the maintainer moves it.
- Pattern records and peak-list adapters (stage 2), until stage 3 is decided.
- Any shipped or downloaded database, and any network call.
- Structure solution from an analogue. That is WP-1515's to scope.

## Tasks

- [ ] **Decision (maintainer):** #813's three questions. (1) Does stage 3
      leave the fence, or does the module stop at lookup? (2) Is it
      top-level `rietx.refdb` with a default index path, `rietx.io.refdb`,
      or a required `out=`? (3) Is the phase key's cell tolerance
      `CELL_EQUALITY_RELATIVE` (5e-3)?
- [ ] 1a: `StructureRecord`, the phase key, and triage with its reasons;
      adapters for a CIF directory, a zip of CIFs and a multi-block CIF;
      `build`, `find(formula=, sg=, elements=)`, `cif()`
- [ ] 1a tests on 20-50 COD CIFs: no `_atom_site` text in the index, a
      rebuild is idempotent, a moved source file is reported
- [ ] 1b: `find(cell=)` through `indexing.reduce`, timed on the fixture set
- [ ] 1b: `analogues()` with a structure-type match (Pearson symbol and
      Wyckoff sequence) and a radius tolerance. The issue's MgTiO₃ (an
      ilmenite) among BaTiO₃'s one-swap analogues is the test it must pass
- [ ] Each fixture's README row: COD entry, citation, licence
- [ ] Skill: a routing row for "a phase or cell that may already be known"
      in a new `references/` shape file, and the entry points in a generated
      `api-<shape>.md` (never `api.md`)

## Acceptance

On the COD fixture set, `find` returns every entry the fixture declares for
each query, `find(cell=)` agrees with `equal_reduced_many` on every pair, and
the index file contains no structure text.

```sh
.venv/bin/python -m pytest tests/test_refdb.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Crystallography Open Database (Gražulis et al. 2009, *J. Appl. Cryst.*
  **42**, 726-729), public-domain dedication.
- Shannon, R. D. (1976). *Acta Cryst.* A **32**, 751-767.
- WP-1510 (the session's chemist knowledge), WP-1515 (structure solution,
  the analogue measurement), WP-1324 (ICSD kept out of the tree).

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #813).
  Checked against the tree at 5d1f5f67: `structure_from_cif`, the
  `indexing.reduce` cell equality, the per-user state directory and six COD
  fixtures all exist; no index over a structure collection exists. No open
  WP owns it: WP-1510 (🔄) feeds what the chemist knows into indexing,
  WP-1515 (⬜) scopes solution, WP-1511 (⬜) checks a cell against one
  powder, and search-match sits in § v2+. Next: the maintainer's decision.
