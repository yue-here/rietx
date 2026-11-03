# WP-2013 — Stale text in the code that the manual move found

Milestone: unscheduled · Status: ✅ 2026-11-03 — every line corrected or struck; of the five behaviour questions, 1 and 2 ruled and built, 5 ruled and folded into WP-1925, 3 and 4 WP-2007's
Track: The repo's own process
Depends on: —

## Goal

Every docstring, comment and message below says what the code does today. The new manual's
Reference pages already state the code's behaviour; these are the copies left in the code.

## Context

WP-1986's 8th session (2026-10-20) moved the old manual's reference half into
`docs/docs/reference/`, and each lane checked its tables against the code. The text below
disagreed with the code it sits in. Behaviour defects and unwritten fields went to their
owners' `### Inherited` (1322, 1334, 1341, 1911, 1933, 1947, 1995, 2006, 2008); what is left
here changes no behaviour. Re-check each against the tree before editing, since a queued
finding goes stale (memory `queued-wp-findings-go-stale`).

- `refine.py:2076-2081`: the `RuntimeError` before a first fit says "construct it with
  history=True (the default)", and fires on a `history=True` refinement too.
- `refine.py:1760`: `NoPhasesError`'s docstring cites the agent envelope WP-1303 removed.
- `refine.py:4360`: says Le Bail intensities are frozen for a run; they are re-extracted
  around every stage (`refine.py:3913-3915,4231-4232`).
- `schemas/instrument.py:1941`: `HumpComponent.position` "Required — there is no default";
  it defaults to 0.0.
- `report/schemas.py:746,881,890,1148` and `report/layer2.py:1241`, with the comments at
  `tests/test_report_apply.py:424,449` and `tests/test_fitreport_layers.py:906`: quoted
  figures re-measured 2026-10-20 as 16.16 against 16.31 (χ² 16.93), a pore-proxy ratio of
  2.89, LaB₆ Rwp 0.0768 and 0.0138.
- `io/recipe.py:1285-1290` (the plan is up to nine stages, not one), `:1350-1356` (the
  order adds a `sample_broadening` stage), `:499-501` (`PatternData` has a TOF axis),
  `:674-676` (W's K edge is 69.5 keV, so "an order of magnitude below 74 keV" is false for W).
- `capabilities.py:232`: `reports_at` also takes `"both"`.
- `io/projects/registry.py:94-107` and `src/rietx/io/CLAUDE.md` § Project readers: a `.inp`
  reports at both read and build.
- `io/projects/topas.py:4003-4005`: `p<i>_magnetic_lor_*` do have a writer
  (`topas_input.py:761`).
- `optimize/cancel.py:38-40`: names a `wait` method `CancelToken` does not have.
- `sequential.py:21-22` ("three fences") and `multi.py:1073` ("Rietveld-only in v0.3").
- `schemas/fraction.py:24-32`: the controls' excess measures 0.22 and the fixture's 99.3.
- `tests/test_result_rows.py:97`: Rwp 0.1435 → 0.2163 now.
- `report/satellites.py:5`: names `using/refining.md`, which retires with the old tree
  (WP-1986); point it at `docs/docs/reference/magnetic.md`.
- `crystallography/cif.py`'s two-block message is 1933's; `rietx.help`'s `lebail_cycles`
  text is 1947's.

## Tasks

- [x] Each line above corrected, or struck with the reason it no longer applies.

## Acceptance

```sh
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## Handover log

- **2026-11-03** — the maintainer's answers to the questions this WP left,
  and the two small changes they asked for. A hump declared in code must now
  say where it is: `HumpComponent()` with no position raises, where it used to
  put the hump at 0° 2θ, below any measured range. A stored document that
  omits the position still opens at that old 0.0, so no file a user holds
  stops opening. The project-format registry no longer declares a "repairs
  reported at read" value that no format uses. The high-energy dispersion
  question became a ruling on WP-1925, which already owned it. Recorded in
  PR #1369, a ghostshift runner's branch carrying the 2026-11-02 rulings
  for WP-2013, 2045, 1933 and 1925. This WP stays closed: the entry records
  how its owed questions ended.

  *Rulings* (maintainer, 2026-11-02), against the five owed questions below:
  1. `HumpComponent.position` becomes required. The read-time fill of the
     old 0.0 is **settled by Claude under the old-files-open rule** (memory
     `rietx-few-users-in-direct-contact`).
  2. Drop `"read"` from `ProjectFormat.reports_at`. **Settled by Claude
     under the WP-1076 rule** (a declared member no code produces), no
     objection from the maintainer 2026-11-02.
  3. and 4. Unchanged, WP-2007's.
  5. File a WP to extend the f′/f″ table past 70 keV from a permissively
     licensed source, the recipe reader's message unchanged meanwhile.
     WP-1925 is that WP (filed 2026-10-08 from #792), so the ruling went
     into its task 2 rather than into a second file.

  *Done.* `reports_at` is `Literal["build", "both"]`. The read channel in
  `read_project_model` tests for `"both"`, and `ProjectModel.to_structure`
  always hands a list on, since both remaining values have a build channel.
  The capabilities comment, the two manual tables and the test stub follow.
  For the hump, a `mode="before"` validator refuses a missing `position`
  unless the validation runs under `schemas.common.STORED_DOCUMENT`, a
  pydantic context. A vanished field's validator cannot tell a document from
  a constructor call, and the context is how a reader says which it is. The
  readers that pass it are `migrate.STORED_DOCUMENT_READ_POINTS`:
  `history.store.read_records`, where a project's models live, and
  `load_instrument_profile`. `project.json` holds no model and an `.rxt`
  builds no component, so neither needs it. The field keeps its factory,
  because the factory declares the `deg` unit a caller's own `Parameter`
  inherits (`_InheritsDeclaredDefaults`). `help.py` quotes no default for it
  now, as for `PeakComponent.center`. The reference table says "required",
  schema 0.60's comment names the change, and the 1.11.0 notes stage the
  break and the dropped member. Four tests: a bare hump and a hump dict
  without `position` raise (fails on the old tree), a history line without
  it opens at 0.0 and stays editable, a hand-written instrument profile
  without it opens too, and each read point named passes the context.

  *Routed.* WP-2006's Inherited note on undeclared writers loses its
  `reports_at` half, marked there. WP-1925 gets the ruling and the findings.
  The recipe reader's `0.0` for a background peak with no position, a
  sibling of question 1, goes to WP-2006's Inherited, because changing it
  changes what `read_recipe` returns.

  *Review.* `/code-review high --fix` raised seven points. Four landed:
  `reading_stored_document` checks for a mapping, the read-point resolver
  fails by name, the API reference generator reads
  `HumpComponent._required_of_a_caller` so the manual no longer prints a
  0.0 default, and the profile read point has a behavioural test. Three were
  declined. The 0.0 fill records no `Diagnostic`, since `read_records` has no
  channel and only a hand-written file reaches the fill. The recipe sibling
  is routed as above. `ProjectFormatCapability.reports_at` stays typed `str`,
  because narrowing it changes the published schema type.

  *Generality.* Judge not dispatched: the branch leaves `_audit.py` alone,
  and the 0.0 fill migrates a stored value without adding a heuristic.

  *Closed-WP writes.* `closed_wp_writes.py` flags this entry. It is this
  WP's own record of how its owed questions ended, and every follow-up it
  names sits in an open WP (2006, 1925).

  *Gates*, on the branch with origin/main d0c4bded0 merged ([dev] venv,
  macOS arm64). The fast selection gave 13607 passed, 319 skipped,
  34 xfailed and 1 failed. The failure was this branch's: the sentence
  added to the hump position's help entry pushed the generated
  `reference/parameters` twin to 50 021 characters, over its 50 000 cap.
  The entry now says "no default value and no default bounds" in one
  sentence, and `test_manual.py` plus `test_help.py` then gave 89 passed.
  Collection of the fast selection is 13 953 against main's 13 949, the
  four tests added. They cost 0.01 s together. `tests.reader_output` exits
  0 (unchanged). `test_docs_consistency.py` 25 passed, ruff clean, and
  `session_start.py` raises no flag for the five WPs. Main then moved to
  e7f04f02a (WP-1952's reader change, WP-2066) and merged clean, so CI's
  run is the first on that tree.

  Next: none on this WP.

- **2026-11-02** — closed by a ghostshift runner. Every line the manual move flagged now says what
  the code does today, or is struck with its reason. No behaviour moved: what a standard fit prints
  is unchanged (`tests.reader_output` exit 0). Four of the WP's quoted re-measurements did not
  reproduce on this tree, so each figure written is this session's own measurement, dated
  2026-11-02. Five questions the text could not settle are left for the maintainer below.

  *Done*, one commit per group:
  - `refine.py`. A `history=True` refinement before its first fit now gets its own message ("the
    tree is built when the first fit runs"); `history=False` keeps the old one. `NoPhasesError`
    names the GUI server's error code instead of the deleted agent envelope. The Le Bail
    alternation says the intensities are frozen inside each stage's solve and re-extracted around
    it (`_run_stage`).
  - `HumpComponent.position` is described as a 0.0 placeholder below any measured range.
  - Report figures, re-measured: the `refine_cell` prediction is 16.16 against 16.30 observed
    (0.9 % low), total χ² 16.93, the one number stamped on nine actions (`report/schemas.py`,
    `report/layer2.py`, `tests/test_report_apply.py`). The pore proxy reads Rwp 0.0403, GoF 2.96,
    partition Rwp 0.0171, ratio 2.36, 82 % of χ² in 8 regions split 5+/3−, R² 0.01; the partition
    reaches 0.01706 by cycle 2. The clean LaB₆ partition is 0.0174 against Rwp 0.0137.
  - `io/recipe.py`: `_read_plan` describes the staged plan (up to nine stages plus `rest`); the
    stage table says it adds `sample_broadening`; the `PNT` refusal says the reader builds a 2θ
    pattern only and the `PXE` one that `PatternData` holds 2θ or a flight time
    (`tests/test_recipe.py`'s assertion follows); the dispersion decline says W's K edge is
    69.5 keV, 5 keV below the beam.
  - `reports_at`: a `.inp` is `"both"` in `registry.py`, `src/rietx/io/CLAUDE.md` and
    `capabilities.py`.
  - `topas.py` names `write_topas_inp` as the writer of `p<i>_magnetic_lor_*`; `CancelToken`'s
    docstring drops `wait`; `sequential.py` lists four fences; `multi.py`'s refusal drops "in v0.3".
  - `schemas/fraction.py`: the control lands at 0.47 of the 95 % half-width, the two-basin fixture
    at 118. `tests/test_result_rows.py`: the cap is 0.0012 Å, Rwp 0.1436 → 0.2169.
  - Inherited from WP-1986: the unenumerated-ambiguity comments in `consensus.py` and `workflow.py`
    and `src/rietx/indexing/CLAUDE.md` now say `geometric_ambiguity` refutes, so every streamed
    grade is `low`; `IndexingResult.fom_panel_disagrees` refutes; `budget_seconds` says three
    engines, 3×7×30 s; `assess_peak_list` says only `peak_diagnostics` emits `PEAK_SIGMA_ASSUMED`.

  *Struck*: `report/satellites.py` already pointed at `reference/refinement.md` (b5a3e5c44,
  WP-1986), which is where `HARMONIC_FRACTION` names magnetism. `cif.py`'s two-block message is
  WP-1933's and `lebail_cycles`' help text WP-1947's. The background pair in `LeBailGap`'s
  neighbour (`rwp_background_subtracted`, LaB₆ 0.0137 / 0.0490 / 0.0766, share 0.89) re-measured
  unchanged, so it was left; the WP's 0.0768 and 0.0138 did not reproduce.

  *Measured* (macOS arm64, `[dev]`, 2026-11-02, scripts outside the tree): the figures above. Not
  reproduced from the WP's 2026-10-20 list: pore-proxy ratio 2.89 (now 2.36), fraction-control
  excess 0.22 (now 0.47), fixture 99.3 (now 118), LaB₆ 0.0768/0.0138 (now 0.0766/0.0137).

  *Gates* (a second runner, on the tree with origin/main 1a648d3a9 merged): the fast selection gave
  13517 passed, 319 skipped, 34 xfailed (`[dev]` venv, macOS arm64). `tests/test_docs_consistency.py`
  first failed: the `reports_at` correction put `src/rietx/io/CLAUDE.md` at 566 lines against its
  565 cap. The bullet was reworded into one line fewer, with no fact dropped, and the file now
  passes 25 of 25. Ruff is clean, `session_start.py` exits 0, and `tests.reader_output` exits 0,
  unchanged against the merge-base. `/code-review high --fix` found eight issues in this branch's
  own rewrites or their siblings; seven were fixed in one commit, and the eighth is owed item 2.
  A second merge of main (WP-2082's prior-count lines) put `src/rietx/indexing/CLAUDE.md` at 363
  against its 361 cap. The streaming bullet now drops its WP-2007 pointer and its "unvalidated
  caps" clause, which the bullet's heading already covers. WP-2007's Inherited note still holds the
  cap-or-refute question. The fast selection was not rerun on that merge, whose overlap with this
  branch is three files of comments; CI runs it.

  *Owed to the maintainer* (each would change behaviour, a public name or a default, so the text
  now describes the code and the question waits):
  1. `HumpComponent.position` defaults to 0.0. Should it be required, as the old comment claimed?
  2. `ProjectFormat.reports_at`'s `"read"` member now has no producer (every format is `"build"`
     or `"both"`), the WP-1076 class.
  3. `index_pattern` on a `PeakList.from_positions` list emits no `PEAK_SIGMA_ASSUMED`; only a
     caller running `peak_diagnostics` sees it. Forwarded to WP-2007.
  4. Whether an unenumerated ambiguity should cap or refute is WP-2007's ruling; the words now
     describe refuting, so a ruling to cap changes them back.
  5. The recipe reader declines dispersion above the table's 70 keV band, which for W (K edge
     69.5 keV) at 74.5 keV drops f′ and f″ that are not small.

  Next: none on this WP. WP-2007 holds items 3 and 4. PR #1337 (the claim draft #1335 sits on the old branch name `wp-2013-stale-text`).

- **2026-10-20** — filed by WP-1986's 8th session from its lanes' reports. No open WP owns
  docstring wording across these modules: 2005 walks `refine.py`'s codes and literals and
  2006 the readers' codes, both for thresholds rather than text.
