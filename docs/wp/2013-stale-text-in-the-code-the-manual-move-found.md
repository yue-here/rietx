# WP-2013 — Stale text in the code that the manual move found

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P3 2026-10-20 — text only, no behaviour moves; each line misleads the next reader of the code

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

### Inherited

- **From WP-1986 (2026-10-22, PR #1099), the indexing reference's lanes.** Text only, each
  found writing `docs/docs/reference/{peaks,indexing,extinction}.md` against the code:
  - An unchecked ambiguity search is called *capping* at `indexing/consensus.py:111-117`,
    `:419-424`, `:560-561` and `indexing/workflow.py:568-571`, `:989-992`; the code writes
    `geometric_ambiguity` for it (`consensus.py:627-632`), which is in
    `INDEX_REFUTING_CAVEATS`, so it grades `low`. Whether the *code* should cap instead is
    WP-2007's (its `### Inherited`); fix the words to whichever that rules.
  - `schemas/indexing.py:1899-1901`: `IndexingResult.fom_panel_disagrees` "caps" every
    candidate; `fom_panel_disagrees` refutes.
  - `schemas/indexing.py:1567-1572`: `SearchSpecSpec.budget_seconds` still says "a default
    two-engine … 2x7x30 s"; three engines run.
  - `indexing/quality.py:409-412`: `assess_peak_list`'s docstring says `PEAK_SIGMA_ASSUMED`
    "still fires" for a position list; neither it nor `PeakList.from_positions` emits it
    (only `indexing/diagnostics.py:88` `peak_diagnostics` does, called by the GUI and
    `pick_peaks`). Unconfirmed through `index_pattern`'s own diagnostics — trace that first.

## Tasks

- [ ] Each line above corrected, or struck with the reason it no longer applies.

## Acceptance

```sh
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## Handover log

- **2026-10-20** — filed by WP-1986's 8th session from its lanes' reports. No open WP owns
  docstring wording across these modules: 2005 walks `refine.py`'s codes and literals and
  2006 the readers' codes, both for thresholds rather than text.
