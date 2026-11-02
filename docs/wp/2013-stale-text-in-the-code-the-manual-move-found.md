# WP-2013 — Stale text in the code that the manual move found

Milestone: unscheduled · Status: ✅ 2026-11-02 — every line corrected or struck; five behaviour questions left for the maintainer
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

  Next: none on this WP. WP-2007 holds items 3 and 4.

- **2026-10-20** — filed by WP-1986's 8th session from its lanes' reports. No open WP owns
  docstring wording across these modules: 2005 walks `refine.py`'s codes and literals and
  2006 the readers' codes, both for thresholds rather than text.
