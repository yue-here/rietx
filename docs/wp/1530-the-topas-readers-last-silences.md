# WP-1530 — the TOPAS reader's last silences: a macro-opened dataset, a line it does not know, a held background

Milestone: unscheduled · Status: ✅ 2026-11-02 — all three silences closed; the unread-call report is drawn from the Technical Reference's index, and a macro-opened dataset names its file (PR #1316)
Track: Coming from another code
Depends on: — (1433 soft: the same reader, its `STR(...)` and `#if` work landed in PR #587)

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

- [x] The unread-call allowlist from the Technical Reference's macro and
      function index: `LP_Factor`, `Rp_Peak` and similar real library macros
      are reported today as unread. Model-bearing ones get registry rows
      (REPORTED), the rest join the allowlist. 2026-11-02, from version 9's
      Table 3-1 and §22.1; `Rp_Peak` is in neither and stays reported
- [x] `data_files` for a macro-opened dataset (`RAW(a)` gives `n_datasets` 2 and
      `data_files` `[]`), and one source for the data-macro list in
      `_UNSEEN_DATASETS` and `_DATASET_MACROS`. 2026-11-02

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

- **2026-11-02** — The TOPAS reader's "called and not read" report now names only what is outside the TOPAS Technical Reference. Before, it also listed real library macros such as `LP_Factor(26.4)`, so a user could not tell a typo from a standard call. Every equation function and every standard macro the reference lists now has a place: the reader reads it, a registry row names what is lost, or it is on a short list of macros that state nothing about the model. A dataset opened by a data-file macro (`RAW(a)`) now names its file in `data_files`, where it read `[]`. This changes what `read_topas_inp` returns, so the PR waits for the maintainer under the reader-output rule.

  **Done.** The source is the version 9 reference (topas-academic.com/technical_reference, read 2026-11-02): Table 3-1 for the functions and §22.1 ("Standard macros – TOPAS.INC") for the macros. `coverage.EQUATION_FUNCTIONS` (57 names) replaces the old hand list, which held ten names TOPAS does not have (`Atan`, `Floor`, `Pow`, `Log10`, …); a call to one of those is now reported, which is right, since TOPAS would stop on it. `coverage.STANDARD_MACROS` (the 97 §22.1 macros that take arguments) is the completeness oracle, and a test holds that each has a place. New registry rows, all REPORTED: "emission profile" (the 15 §22.1.3 macros the reader does not read into `anode`, such as `CuKa4_Holzer`), "cell mass, volume and weight percent" (`MVW`), the 12 §22.1.9 bond-length penalty macros on the restraints row, and `Cylindrical_I_Correction`/`Cylindrical_2Th_Correction` on the specimen-corrections row. Read by name, no longer reported: `LP_Factor`, `Radius`, `STR`, the `A1`-`A3` coordinate macros (also wrongly reported before) and the six TOF profile macros. `coverage.MODEL_FREE_MACROS` holds six: `Decompose`, the three absorption and density reporters, `Gauss`, `Lorentzian`. `_DATASET_MACROS` is the one data-macro list: the openers, the scan, `data_files` and the `for`-loop refusal all read it, and `SCR` and `SHELX_HKL4` join it from §22.1.1. `data_files` takes one entry per opener in file order, a macro's first argument as written.

  **Settled by Claude.** (1) `RAW(a)` records `a`, not `a.raw`: §22.1.1 says the argument is `path_no_ext`, and which extension the macro adds is in its body, which this reader does not have; io/CLAUDE.md § Metadata forbids inventing a convention. The alternative, appending the macro's name as the extension, would make the entry openable directly. (2) `BRML` and `SST` stay data macros, though version 9 does not list them; they came from the macro index #616's reporter quoted, and dropping them would undo #616 for those files. (3) The Holzer-style emission macros get a REPORTED row rather than a read into `anode`, as the task specified; reading them is the better end state but changes `anode`. (4) A bare `xdd` path is one token on the opener's line. The old rest-of-line read made `xdd d.xy x_calculation_step 0.01` a file of that whole name, and the token read reached the next line's keyword.

  **Measured.** `tests/test_projects_topas.py`: 543 tests at the base, 713 here, 170 added (154 of them one parametrized row per reference name). Fast selection on this branch before main was merged in (`.venv`, `[dev]`, macOS arm64, alone under the shift's suite lock): 13414 passed, 310 skipped, 32 xfailed, 2 failed, 9:08. One failure was this change: `examples/switching.py` pinned two `TOPAS_FEATURES_NOT_IMPORTED` on the file rietx's own writer produces, and the second was the false "LP_Factor(…) called and not read". It now pins one, and `test_examples.py -k switching` passes. The other, `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`, is this machine's Jupyter kernel spec pointing at a deleted venv. No baseline was taken, so the fast delta is checked through the one file. The 8 added test functions cost 0.17 s together (`tests.added_test_times`, local junit). `python -m tests.reader_output`: unchanged, exit 0 (it diffs a standard fit's printed text, which no TOPAS read reaches). No lanes; the session stayed under 150K.

  **Review pass.** `/code-review high --fix` made three fixes: a bare macro path may hold one level of parentheses, `_DATASET_OPENERS` takes the shared tuple, and the manual's `unread_calls` row names the allowlist. I added two more from its findings: the bare `xdd` path stays on its line, and the `data_files` comment says the list is not indexed by dataset (an opener naming no file, such as `xdd_sum`, adds nothing). Declined, as outside this WP or a public-shape change: making `data_files` dataset-indexed with `None` gaps; an `xdd yobs_eqn …` on one line still records `yobs_eqn`; and a bare macro path containing `word (` still reports `word` as an unread call.

  **Generality.** No audit-table change and no new code; the lists are transcriptions of a specification, so the judge was not dispatched.

  **Not generalised.** `Rp_Peak` is in no index of version 9, so it is still reported. Macros the reference names only in its prose (`Robust_Refinement`, `Get_modulated_sites`, `Point`) are not in the oracle, and a call to one reads as unread. Reading `MVW`'s third argument as `weight_percent` is a one-line read left for whoever next needs it. Next: none in this WP; it closes here.

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
