# WP-2006 part 1: the reachability walk

`reachability.csv` is written by `.venv/bin/python -m tests.reachability_walk` (run by hand; not collected by pytest), one row per entry of
`tests/api_surface.py::derive_surface()`. This page is not generated: its counts and lists were read off the CSV by ad hoc queries, and no script in the repo reproduces them. **The table rules nothing and removes nothing.**
The script's docstring says how a mention is resolved and what it cannot see.

## Count

`derive_surface()` returns **2267** entries (the WP counted 2 238; 29 entries were added on `main` since):

* `BackgroundChoice` and its 10 fields (11 entries): `air_scatter`, `air_scatter_gain`, `air_scatter_trigger`, `amorphous_hump_score`, `background`, `hump_trigger`, `kind`, `knot_step_deg`, `seed_level`, `selection`;
* `BackgroundSelection` and its 6 fields (7): `diagnostics`, `method`, `n_masked_channels`, `scores`, `selected`, `stopped_by_whiteness`;
* `CandidateScore` and its 3 fields (4): `bic`, `complexity`, `durbin_watson`;
* `NodeAction.correlation_guard`;
* `phase_support_sigma` on `NodeAction`, `PlanSpec` and `RefinementPlan`;
* `RefinedParameter.interval` and `RefinedParameter.stderr_uncorrected`;
* `StageResult.cell_reset`.

Two derived states, because the first one the brief names is vacuous:

* `state` (every source the brief lists: examples, skill, GUI, manual Part 1, via another reached entry):
  {'reached': 2239, 'reached (via entry)': 3, 'tests only': 21, 'unreached': 3, 'docstring example only': 1}.
  Almost everything is "reached" because `tests/test_manual_api.py` partitions the whole surface into documented,
  excluded-with-a-reason or deferred, so the manual mentions every name by construction, and the skill's `api*.md` is
  generated from a selection. That is the brief's falsifier ("nearly everything reached"): the resolution rule counted
  documentation as use.
* `state_use` counts only *use* sources (`examples/`, hand-written skill pages, `gui/` TypeScript and the GUI's Python
  side) plus the type pass, and puts a name found only in the manual or the generated skill index in its own state,
  `documented only`: {'reached (via entry)': 79, 'documented only': 1156, 'reached': 1005, 'tests only': 23, 'unreached': 3, 'docstring example only': 1}.

By kind, `state_use`: {('docstring example only', 'field'): 1, ('documented only', 'attribute'): 7, ('documented only', 'class'): 43, ('documented only', 'field'): 989, ('documented only', 'function'): 3, ('documented only', 'member'): 114, ('reached', 'attribute'): 24, ('reached', 'class'): 83, ('reached', 'constant'): 3, ('reached', 'field'): 697, ('reached', 'function'): 40, ('reached', 'member'): 158, ('reached (via entry)', 'class'): 79, ('tests only', 'class'): 2, ('tests only', 'field'): 21, ('unreached', 'field'): 2, ('unreached', 'member'): 1}.

Where the manual's Part 1 lives: `docs/manual/using/` (25 pages) is still on `main` after WP-1986's PR #1054; the new
manual is `docs/docs/` (guides, reference, concepts, theory). Both are read, in separate columns (`manual_part1`,
`manual_new`); `_generated` and `_build` are not.

## The WP's positive check

`IndexingEvidence`, `CaveatEvidence`, `CandidateEvidence`: **reproduced on the direct columns.** None has a mention in
`examples/`, in `gui/` (TypeScript or Python side) or in `src/` outside its own defining module (`schemas/indexing.py`,
where `candidate_evidence()` builds them). Their CSV rows:

* `IndexingEvidence`: skill `api.md` (generated index), manual Part 1 and the new manual (`manual_new`), and one hit in `tests/`. None of those is use. It is `reached (via entry)` under
  `state_use` because `IndexingResult.evidence()` returns it and that method is itself used (examples, GUI `Peaks.svelte`,
  skill). So "used by nothing in src, examples or gui" holds as a statement about *named* use; the type is reachable as
  the return type of a method that is used.
* `CaveatEvidence`, `CandidateEvidence`: manual Part 1 only: `documented only`.
* The WP says the latter two are "tests only". **Stale or inexact**: no file under `tests/` names either of them
  (the walk skips `test_manual_api.py` and `api_surface.py`, which read every name, so that is not the cause).

## Candidates for the maintainer, by `state_use`

* `tests only` (23): AntiBumpRestraint, AntiBumpRestraint.atom_i, AntiBumpRestraint.atom_j, AntiBumpRestraint.min_distance, AntiBumpRestraint.op_index, AntiBumpRestraint.sigma, AntiBumpRestraint.translation, AntiBumpRestraint.weight, BodyTorsion.angle, BodyTorsion.axis, BodyTorsion.name, BodyTorsion.vary, RigidBody.name, RigidBody.riding, RigidBody.rotation_vary, TetherRestraint, TetherRestraint.atom_i, TetherRestraint.atom_j, TetherRestraint.max_distance, TetherRestraint.op_index, TetherRestraint.sigma, TetherRestraint.translation, TetherRestraint.weight. All are in the rigid-body restraint and body classes
  (`AntiBumpRestraint`, `TetherRestraint`, `BodyTorsion`, `RigidBody` fields), mentioned only in `tests/`.
* `docstring example only` (1): BodyOrigin.x (judgement call: a `src` docstring example is the only mention).
* `unreached` (3): BodyOrigin.values, BodyOrigin.y, BodyOrigin.z. `src_code` shows a hit for each, from a *generic* member name (`.y`, `.z`,
  `.values`) that belongs to other classes (`Atom.y`): the evidence is `f` (co-occurrence), the weakest level.
* `documented only` (1156): in the manual or generated skill index and nowhere else. 989 of them are
  fields. Not a removal list: the manual documents what the partition forces it to. The CSV carries where each is
  mentioned.

## Hand checks (the brief's falsifier test)

Five of each state were read off the CSV and spot-verified in the tree:

* reached: `StageResult.blocked_by_hold` (`examples/guides/hold.py:26`), `Project.live_dir` (`src/rietx/gui/session.py:1693`),
  `ExtinctionCandidate.refuted`, `SeriesResult.failures`, `SequentialRefinement.failures_`.
* reached (via entry): `Capabilities` (via `capabilities`), `Hit` (via `Coverage.refused`), `DeadChannelRun` (via
  `PatternDiagnostics.dead_channels`), `SearchPresetCapability`, `ReflectionState`.
* documented only: `PlanCapability.when_to_use` (checked: only `gui/src/App.test.ts`, which is excluded, besides the
  manual), `SharingMap.per_histogram`, `GsasHistogram.wavelengths`, `ExtinctionCandidate.symbol`,
  `SphericalHarmonicTexture.coefficients`.
* tests only: `AntiBumpRestraint` (`tests/test_magnetic.py`, `test_one_sided_restraints.py`), `RigidBody.name`,
  `RigidBody.riding`, `TetherRestraint.op_index`, `TetherRestraint.weight`.
* unreached: the three `BodyOrigin` entries above; there are only three, so all three were read.

## What the walk cannot see, and the known over-counts

Text, not imports and not types. A member whose name is common (`name`, `value`, `label`, `refuted`) is counted as
mentioned wherever the identifier occurs in a file that also names the owner (`f`) or, if the name is unique on the
surface, anywhere (`u`); both over-count. The reverse error: a field used only through `model_dump`, a JSON key with
another spelling, a `getattr` with a built string, a notebook output or a user's console command is missed. The `f` and
`u` evidence counts are in the CSV cells (`evidence:files`) so a reader can discount them.
