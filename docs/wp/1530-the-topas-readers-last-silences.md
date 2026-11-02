# WP-1530 — the TOPAS reader's last silences: a macro-opened dataset, a line it does not know, a held background

Milestone: unscheduled · Status: 🔄 2026-11-02 — claimed by @yue-here (ghostshift runner); #616, #651 and #652 landed, the allowlist and macro `data_files` remain
Track: Coming from another code
Depends on: — (1433 soft: the same reader, its `STR(...)` and `#if` work landed in PR #587)
Priority: P2 2026-10-02 — two of the three are a model built wrong with nothing said, on a reader path few fits run

## Goal

`read_topas_inp` says something wherever it builds a model that differs from
the file. A dataset opened by a data-file macro counts as a dataset. A line
it does not recognise is reported. A held `bkg` list reports its length and
whether it was refined.

## Context

Three reports from one contributor (mustachefeeling), all found by comparing
rietx against an independent refinement program. Each was reproduced at
`ca9bda29` in the 2026-10-02 triage. The reader is
`src/rietx/io/projects/topas.py`; the coverage registry is
`src/rietx/io/projects/coverage.py`, whose docstring states the stance this
WP extends: "the stance is **declared per construct** and the default is
never silence".

### A macro-opened dataset is not counted (issue #616)

`_DATASET_OPENERS` (`topas.py:2223`) is `xdd`, `xdd_scr`, `xdd_sum`,
`TOF_XYE` and `TOF_GSAS`. The reference's macro index lists `RAW`, `XDD`,
`XY`, `XYE`, `DAT`, `BRML` and `SST` among the macros that expand to `xdd`.
A file opening two datasets with `RAW(a)` and `RAW(b)` reads as
`n_datasets 0`, both phases carry `dataset = None`, and `to_structure` builds
the two specimens' phases into one `Structure` (weight percents 60 + 70 in
the reproduction). The same file with `xdd "a.xy"` / `xdd "b.xy"` gives
`n_datasets 2`, and `to_structure` refuses, as it should.

The fix the reporter proposes, counting the `xdd`-stating data macros as
openers, changes single-macro files too: their phases become dataset 0
rather than `None`. That is why PR #595 did not make it. Measure what that
moves in the corpus before choosing. The reporter's corpus has one file
that opens two datasets this way, and it carries one phase, so the defect is
latent there.

### A line the reader does not know is dropped (issue #651)

A call to a macro the file never defines, or a misspelt keyword
(`lor_fwhmm 0.1`), is dropped. No diagnostic fires, `coverage.partial` stays
`False`, and the phase builds. Both rows are indistinguishable from the
control. TOPAS itself stops on such a line ("unknown or misplaced keyword").
The registry can only report constructs it has a row for, so an unknown
identifier falls through.

The reporter's four options:

1. report every call `name(` that is neither defined in the file nor read
   or reported by the reader, as `TOPAS_FEATURES_NOT_IMPORTED`. The wording
   "called and not read" is true whether the macro is a typo or the user's
   own include;
2. also report unknown bare identifiers in keyword position, against the
   §5.1 keyword tree already transcribed for `PHASE_SCOPE`. This needs the
   grammar to tell a keyword from a parameter name in value position;
3. refuse either, which would refuse a valid file calling a user's macro;
4. leave it, and state the limit in `coverage.py`'s docstring.

*Decided 2026-10-02 (issue triage; the maintainer accepted the recommendation):* option 1 plus
option 4's docstring sentence for bare identifiers. Option 1 keys on
`name(`, so its false positives are bounded, and it covers the case seen
in practice (a peak-shape macro defined in an include).

### A held `bkg` list reads `None` (issue #652)

PR #658 fixed the miscount (an esd-annotated list read 1). The held list
was left open. `bkg ! c0 c1 …` holds the whole list and gives
`background_terms = None`. The manual (`docs/manual/using/files.md`) calls
the field "how many background coefficients were refined". The options are
to keep `None` and document it, to return the length and add a separate
`background_refined: bool | None` beside it (as phases carry `vary`), or to
return `0`.

*Decided 2026-10-02 (issue triage; the maintainer accepted the recommendation):* the length plus
`background_refined`, the one option that loses no information. The
manual's wording changes with it.

## Non-goals

- `STR(...)` and `#if`: WP-1433.
- Species spellings in foreign files: WP-1527.
- A TOF dataset beyond the refusal PR #595 landed: neutron TOF is fenced at
  v2+ behind issue #193.

## Tasks

- [x] Macro-opened datasets (#616): counted, 2026-10-03. `tests/data/` holds no
      `.inp`, so the corpus measurement is the private map's and was not made;
      what it moves is stated in `_DATASET_OPENERS`' comment (a lone macro's
      phase is dataset 0, not `None`)
- [x] Undefined calls and unknown keywords (#651), as decided
- [x] A held `bkg` list (#652), as decided, with `using/files.md`
- [x] Tests: the three reproductions in the issues, each with its positive arm
- [x] Skill: the `TOPAS_FEATURES_NOT_IMPORTED` row in
      `references/diagnostics-projects.md` stops implying a complete import
      when `coverage.partial` is `False`, if what lands makes that so

- [ ] The unread-call allowlist from the Technical Reference's macro and
      function index: `LP_Factor`, `Rp_Peak` and similar real library macros
      are reported today as unread. Model-bearing ones get registry rows
      (REPORTED), the rest join the allowlist
- [ ] `data_files` for a macro-opened dataset (`RAW(a)` gives `n_datasets` 2 and
      `data_files` `[]`), and one source for the data-macro list in
      `_UNSEEN_DATASETS` and `_DATASET_MACROS`

## Acceptance

Each issue's reproduction gives the corrected answer, and each positive arm
still passes.

```sh
.venv/bin/python -m pytest tests/test_projects_topas.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- TOPAS Technical Reference, § 5.1 (keyword tree) and the macro index (the
  data-file macros that state `xdd`). Paper and manual only; TOPAS is closed.

## Handover log

- **2026-10-03** — Three silences of the TOPAS `.inp` reader are closed. A file that opens its datasets with a data macro (`RAW(a)`, `XYE(b)`, …) now reads as that many datasets, so two specimens are no longer built into one structure. A call to a macro the file never defines is reported, where it was dropped without a word. A held `bkg` list now says how many coefficients it has and that none is refined. One piece is unfinished and is the next job. The "undefined call" report also lists real TOPAS library macros the reader has no row for (`LP_Factor`, for one), so it can name something that is not a typo. Only the reference's macro index can fix that.

  **Done.** #616: `_DATASET_MACROS` joins `_DATASET_OPENERS` and `_BLOCK`, matched only as a call so a bare `XY` is not one and `registry`'s claim pattern is unchanged. A lone macro's phase is dataset 0 now, not `None`. #652: `TopasModel.background_refined` beside `background_terms`; the `@`/`!` marker sticks until the other appears. #651: `Coverage.unread_calls` and a second `TOPAS_FEATURES_NOT_IMPORTED` diagnostic, with the bare-keyword limit stated in the field's comment. Manual rows and the skill row updated, three skill copies synced.

  **Measured.** The corpus measurement the task asked for was not made: `tests/data/` holds no `.inp`, and the corpus is the private map's. The effect is stated in the code instead (dataset 0 for a lone macro). Fast selection on this branch (`.venv`, `[dev]`, macOS arm64): 8074 passed, 159 skipped, after three manual-API failures from the undocumented new field, fixed and re-run green (192 in the manual, skill and docs files). The 17 tests this session added are all in `tests/test_projects_topas.py`; no pre-session baseline was taken, so the passed+skipped delta is not checked. The full selection did not run: nothing it measures (acceptance numbers) is reachable from the reader. No lanes were dispatched; the session never passed 150K before its last item.

  **Review pass.** `/code-review high --fix` made three fixes (a refusal message and a comment that contradicted the new opener, a no-op `replace` in a test). I applied one more from it: `Log10`, `Pow`, `Rand`, `Rad`, `Deg` and `Out_*`/`Create_*` calls are no longer unread, and the diagnostic no longer says TOPAS stops on an undefined one. Declined for now, and listed as the two new tasks: the reference-derived allowlist, `data_files` for macro datasets, and one source for the data-macro list.

  **Gotchas.** `_UNSEEN_DATASETS` still refuses a `for xdds` loop in a file with a macro dataset, though the dataset is now counted; no file exercises the expansion, so it was left. Next: take the two open tasks, starting with the allowlist, since it decides whether the second diagnostic is trustworthy; it needs the Technical Reference's macro index.

- **2026-10-02** — created, from the 2026-10-02 issue triage (issues #616,
  #651, #652). Checked against the tree at `ca9bda29`: #616's file reads
  `n_datasets 0` and builds both phases into one `Structure`, and its `xdd`
  control refuses; #651's undefined macro and misspelt keyword both give
  `partial=False` and no diagnostic; #652's annotated list now counts 5 (PR
  #658), and the held list still reads `None`. No open WP owns it: 1433 is
  scoped to `STR(...)` and `#if` and all its tasks have landed, and 1527 is
  species spellings. Next: the two decisions above, then the tasks in order.
