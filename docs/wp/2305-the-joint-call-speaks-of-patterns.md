# WP-2305 — The joint call speaks of patterns and is named a joint refinement

Milestone: series · Status: ✅ 2026-11-25 — refine_joint, JointRefinement, pattern.N., PR #1838
Depends on: —

## Goal

The joint call and everything a user reads about it use one word for one measured dataset:
pattern. Its public names follow the literature's term, joint refinement. A name or a path
prefix a caller wrote before the change raises, naming its replacement.

## Context

**The rulings.** The maintainer ruled on 2026-11-23 that the joint fit's `hist.N.` dot-path
scope becomes `pattern.N.`, with the old prefix refused ("Rename, with refusal", recorded first
in WP-2300). He then handed the rest of the joint call's naming to Claude the same day: "you
make the calls. I don't care about sunk costs here, only about building the best api." The
calls below are settled by Claude under that instruction and DESIGN Rules 4 and 5.

**What changes for a caller.**

| Today | After |
|---|---|
| `rx.refine_multi(...)` | `rx.refine_joint(...)` |
| `rx.MultiHistogramRefinement` | `rx.JointRefinement` |
| `rietx.multi` (the module the manual cites) | `rietx.joint` |
| `hist.0.instrument.zero_shift` | `pattern.0.instrument.zero_shift` |
| "histogram" in docstrings, the manual, `help.py` and diagnostic messages | "pattern" |

The pairs then read as one family: `Refinement` and `refine`, `SequentialRefinement` and
`refine_sequential`, `JointRefinement` and `refine_joint`.

**Grounds.**

- *Name follows the literature's term* (Rule 5, conflicts). "Joint refinement" is the
  literature's phrase for fitting several patterns in one least-squares problem, as in joint
  X-ray and neutron refinement. "Multi-histogram" is GSAS's word and "multi-pattern" FullProf's
  (`NPATT`, `docs/practice.md` § Sequential refinement), each one program's keyword. rietx's
  manual already calls it the joint fit (`guides/joint.md`, `reference/joint.md`), and the
  series milestone calls it the joint call.
- *One idea, one spelling* (Rule 5, convention). The declaration's field is `per_pattern`
  (WP-2300), both calls take `PatternData`, and the series speaks of patterns. Keeping
  "histogram" in the joint call alone would break the convention in one place.
- *The likeliest misuse after a rename is the old name* (Rule 4). A removed name raises
  `AttributeError` naming its replacement, as NumPy 2.0 did for the names NEP 52 cut. A path
  or glob starting with `hist.` raises naming `pattern.`, because a plan glob that matches
  nothing is silent, so an old `"hist.*.instrument.*"` would otherwise free nothing without a
  word.
- *Cost.* No stored file holds a joint path: a joint fit keeps no history or project
  (`multi.py`, "a joint fit keeping no history"). On `bacb7d58b` the prefix had 338 uses
  across source, manual, examples and tests, and "histogram" 1 304 in the source, most in
  docstrings. Callers are few and in direct contact.

**Out of scope.** Internal names that no user types (`params/multi.py`, `MultiParameterTable`,
private helpers) follow only where the manual cites them. WP-2300's `Declaration` replaces
`SharingMap`, so this WP does not rename it.

**Order.** Before WP-2300, so the declaration is written once in the new names.

**Tier.** No heuristic is added; `_audit` gains no row. Diagnostic messages change wording,
so they are reader output and checked blind in the PR.

## Non-goals

- The declaration object (WP-2300).
- Verbs on a joint fit (WP-2103).
- Any change to what a joint fit computes: every number is bit-identical.

## Tasks

- [x] `refine_joint`, `JointRefinement` and the module `rietx.joint`; the old names raise
      `AttributeError` naming the new ones (a module `__getattr__`), with a test.
- [x] `hist.N.` → `pattern.N.` wherever a path is built, parsed or documented; a path or glob
      starting with `hist.` raises naming `pattern.`, with a test through a plan glob,
      `set_vary`, and a result lookup.
- [x] "histogram" → "pattern" in public docstrings, `help.py`, diagnostic messages, the manual,
      examples and the skill. `docs/contracts/schema.md` records the path change.
- [x] Goldens and the cross-backend matrix unchanged in value; the joint acceptance tests pass.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_manual_api.py tests/test_help.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python -m tests.reader_output
```

## References

- [`../milestones/series.md`](../milestones/series.md) § The rules (1, 2).
- WP-2300 § Context, "The names".
- NumPy NEP 52 (2023), the removed-name error (`docs/practice.md` § How an API meets a
  caller's mistake).

## Handover log

- **2026-11-25** — built by a ghostshift runner (Claude), PR #1838.
  The joint call now has the literature's name and the series' word. A caller
  writes `rietx.refine_joint` or `rietx.JointRefinement` (module `rietx.joint`),
  reads `result.patterns[h]` and `result.for_pattern(h)`, and scopes a
  per-pattern row as `pattern.1.instrument.zero_shift`. Every old spelling a
  caller could still type raises and names its replacement, so an old script
  fails at its first old name rather than running a plan that frees nothing.
  No number a joint fit computes moved. WP-2300 can now write the declaration
  in these names.

  *Done.*
  - Task 1: `rietx.multi` → `rietx.joint`, `refine_multi` → `refine_joint`,
    `MultiHistogramRefinement` → `JointRefinement`. The old top-level names
    raise `AttributeError` naming the new ones (`_TOP_LEVEL_HINTS`), and
    `src/rietx/multi.py` is a stub whose import raises `ModuleNotFoundError`
    naming `rietx.joint` (declared in `_audit.NOT_WALKED`).
  - Task 2: `hist.N.` → `pattern.N.` wherever a path is built, parsed or
    documented, including two segment parsers that compared `parts[0] ==
    "hist"` (`help.undeclared_opt_in`, `refine._owner_words`) and the manual's
    diagnostics routing (`docs/reference_pages.py` named `rietx/multi`).
    `schemas.common.refuse_retired_scope` raises on a path or glob starting
    with `hist.`, naming its `pattern.` spelling, from `JointRefinement.fit`
    (every stage's `turn_on`/`turn_off`, before anything runs),
    `MultiParameterTable.set_vary` and `RefinementResult.parameter` (as a
    `KeyError`).
  - Task 3: "histogram" → "pattern" in docstrings, `help.py`, diagnostic
    messages, the manual, examples and the skill, and in the public names that
    carried the word: `RefinementResult.patterns`, `PatternResult`,
    `for_pattern`, `StageResult.unreached_patterns`,
    `JointRefinement.n_patterns`, `report(pattern=)`, the event data keys
    `patterns`/`pattern_index`, `capabilities().features["joint_refinement"]`.
    A result JSON written before still opens (`results._fold_renamed`), and
    `_nearmiss.RENAMED_WORDS` answers `result.histograms` with `patterns`.
    `docs/contracts/schema.md` records it under 0.62. GSAS's own "histogram"
    (its readers, their help entries, `GsasModel.histograms`, the GSAS-II
    switching page) is unchanged, as is `SharingMap.per_histogram`, which
    WP-2300 replaces.
  - Tutorial 05's committed output quoted the series' pointer to the joint
    call; that one token is patched in place. A rebuild on this machine moved
    every Rwp in the notebook by a few 1e-4, which is not this change's.

  *Settled by Claude at the maintainer's instruction (2026-11-23, DESIGN Rules 4 and 5):*
  1. The public names that carried "histogram" are renamed too, beyond the
     WP's table (`RefinementResult.patterns`, `PatternResult`, `for_pattern`,
     `unreached_patterns`, `n_patterns`, `report(pattern=)`, the feature flag
     `joint_refinement`). Grounds: the WP's goal, one word for one dataset
     across the surface. Alternative: keep them as internal-looking names; they
     are typed by every joint caller, so they are surface.
  2. Old result JSON opens through a read-time fold of the two renamed fields,
     as `_migrate_v1_2_n_background_peaks` did for its rename. Alternative:
     refuse it under `extra="forbid"`; the repo's rule is that old documents
     open.
  3. The joint fit's event `data` keys are renamed without an
     `EVENT_SCHEMA_VERSION` bump, since `data` is an open dict by declaration
     (`history/events.py`). Alternative: bump to "4".
  4. The old module is kept as a raising stub rather than deleted, so
     `import rietx.multi` names `rietx.joint` instead of a bare
     `ModuleNotFoundError`. Alternative: delete it and let the top-level hint
     cover only `rx.multi`.
  5. Commits: tasks 1-3 landed as one commit, because one sweep renamed the
     same lines for all three.

  *Measured.* All on the worktree's `[dev]` venv, darwin/arm64, on this branch with
  main merged (`17dc90f27`, docs-only from main).
  - Fast selection (`-m "not slow"`): 15742 passed, 452 skipped, 30 xfailed,
    3 failed, 9:25. The three were this branch's: a stub docstring citing
    `rietx.multi` (`test_code_references`), the GUI help-key fixture not yet
    committed, and the holder-cell guide's quoted column one character short
    for `pattern.N.vars.height`. Fixed; the three files then gave 57 passed.
    Another session's pytest may have shared the machine; this rung does not
    check.
  - Full suite, through ghostshift's `serial.py` queue (it waited 2501 s for
    the lock, so nothing else ran beside it): 16705 passed, 463 skipped,
    49 xfailed, 1 xpassed, 0 failed, 59:06. The goldens, the cross-backend
    matrix and the joint acceptance rows are in it, so task 4 is ticked.
  - Added tests: 9 cases in `tests/test_multi_histogram.py`, 1.30 s together
    (`tests.added_test_times`, local junit); the slowest is the reopen test at
    1.22 s, on the module's existing fit fixture. No exact passed+skipped
    delta against a base was measured: no base run on this machine.

  *Reader output.* `python -m tests.reader_output` exited 0: the standard
  single fit prints the same text. The joint fit's own messages changed wording
  only (histogram → pattern, `hist.` → `pattern.`); the PR body lists them for
  the blind check.

  *Review.* `/code-review high --fix` found six. Five fixed: `docs/VALIDATION.md`
  regenerated; a pre-rename joint result now has its `hist.N.` paths respelled on
  read (`results._rescope_legacy_paths`), without which `for_pattern` kept every
  pattern's rows; `rietx events --help`'s "termination histogram" restored (a
  count, which the sweep had renamed); the manual names `KeyError` for a result
  lookup; root CLAUDE.md names `joint.py`. Declined: `_audit.py` rows cite
  stale line numbers in `joint.py`, stale already in main's `multi.py`, and
  fixing them means re-auditing each row. A blind reader-output check (a fresh
  subagent given the message diff) found no junk added; it flagged
  `SharingMap(per_histogram=…)` beside "per-pattern" in four messages as
  half-renamed, which WP-2300's declaration replaces.

  *Generality* (the `generality-review` judge, pasted unedited):

  > **The 11 rows whose evidence or response text changed** (PARAMETRIC_OUT_OF_RANGE and its
  > .suggestion, PEAK_EQUATION_SHARED_ACROSS_WAVELENGTHS, SIZE_NORMALISED_ACROSS_WAVELENGTHS and
  > its .suggestion, STAGE_FREED_NOTHING and its .suggestion, rietx.indexing.fom.RESOLUTION_FWHM,
  > RefinementResult.qpa, StageResult.collapsed, StageResult.released). **Verdict: holds.** No
  > tier, ambiguity, value or response changed, and nothing in the change argues for either side.
  > The only defect is line numbers that were already stale before this branch. [...table: each
  > row decides what it decided before; PARAMETRIC_OUT_OF_RANGE stays `caller`, re-searched on
  > this tree: refine_joint/JointRefinement appear outside joint.py only in exports, capability
  > lists, docstrings and messages; RESOLUTION_FWHM's "histograms" now reads "patterns", the same
  > datasets reworded.] Stale line numbers, which this branch did not cause: the rows cite
  > `joint.py:2316-2322`, `2249-2300`, `2539-2584`, `2334-2336`, `2293-2298` and `2579-2582`;
  > those codes are raised at lines 3521, 3394 and 3995, and main's `multi.py` already had them
  > at 3140-3591. Would change the verdict: a tier, ambiguity or value edit hidden in these rows.
  > The diff shows none.
  >
  > **OTHER_RECORD_FIELDS: RefinementResult.histograms → .patterns, StageResult.unreached_histograms
  > → .unreached_patterns.** **Verdict: holds.** These are field renames, and each field still
  > only records what happened. Would change the verdict: a rename that also changed what the
  > field holds.
  >
  > **WALKED: "multi.py" → "joint.py" (2003).** **Verdict: holds.** The same code moved to a new
  > file, and it keeps its audit owner. `joint.py` has no module-level numeric constant today.
  >
  > **NOT_WALKED: "multi.py".** **Verdict: holds.** The file decides nothing: a docstring and one
  > `raise ModuleNotFoundError(...)`. Would change the verdict: anything added to the stub beyond
  > the raise.
  >
  > **Flagged outside the table: schemas.common.refuse_retired_scope.** **Verdict: holds, and no
  > row is needed.** It is a refusal of a retired name, and Rule 4 asks for exactly this. A
  > raised exception is none of the table's five kinds of row. Ambiguity kind 1: no live
  > dot-path starts with `hist.`, so the refusal cannot reject a valid path. Scope gap, not a
  > tier question: the check matches only a leading `hist.`. A path given to other joint verbs
  > (ties, `set_values`, holds), or a glob such as `*hist.0*`, does not reach these three sites.
  > Would change the verdict: a live dot-path or user variable that legitimately begins with
  > `hist.`.

  Author's note on the scope gap: a joint fit has no tie, `set_values` or hold verb yet
  (WP-2103 adds them), so the three sites are every entry a caller's path reaches today.
  WP-2103's verbs should call `refuse_retired_scope` too; noted in its `### Inherited`.
  The judge's table rows were condensed where marked `[...]` to keep the entry readable;
  no verdict or finding was dropped.

  *Gotchas.* A `hist.` regex over source also hits a variable named `hist`
  with an attribute (`hist.statistics`); eleven test files had one, restored by
  a token-level pass. "Patterns" already meant globs in several messages, so
  `STAGE_FREED_NOTHING`'s help, the `unreached_patterns` help and the
  reference page now say "globs" where they meant globs.

  *Next:* WP-2300's declaration, written in these names (noted in its
  `### Inherited`), and WP-2103's path-taking verbs call
  `refuse_retired_scope` (noted in its `### Inherited`).

- **2026-11-23** — filed by Claude at the maintainer's instruction to make the joint call's
  naming calls. The `hist.` rename moves here from WP-2300, which recorded it first, since it
  is one change with the class, function, module and prose renames and touches the same
  files. Facts checked on `bacb7d58b`.

  *Next:* the build, before WP-2300's.
