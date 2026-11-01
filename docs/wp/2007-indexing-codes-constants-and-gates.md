# WP-2007 — Indexing: its codes, constants and gates

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2001
Priority: P3 2026-10-19 — 2001 closed, so nothing blocks it; provisional by declaration, so a verdict here already carries a caveat; several sessions

## Goal

Indexing's 48 diagnostic codes and 76 module-level constants are in the audit table with
a tier, its grading and gating rules sorted by the same rule, and the graded benchmark
run once on the final tree with its ranking unchanged or improved.

## Context

The rule is `../milestones/generality.md` § The rule. `src/rietx/indexing/CLAUDE.md`
(340 lines) auto-loads with the subtree and is the dossier; this file does not restate it.

**Why its own WP.** 16 000 lines, 48 codes, 76 constants the open's count had not
included, an hour-long benchmark (`python -m tests.bethanechol_benchmark`, run alone) and
a rule in root CLAUDE.md: run `tests/test_acceptance_indexing.py` before closing anything
that touches an engine, because a ranking regression once sat under 115 green fast tests
(WP-1030).

**What the ethos already says here.** "Never a confident singleton": `IndexingResult` has
no `.cell`, only a gated `best_or_none()`; the extinction symbol is what a powder
measures, and `determine_extinction_symbol` returns ranked classes each carrying a list.
Memory `agent-first-design-thesis`: gates report evidence, never refuse (fluorite indexed
at −5 ppm after a refusal). DESIGN.md § Rules, 1 names indexing and extinction symbols as
its examples of the second kind: the package enumerates the hypotheses, scores each with
its evidence and presents the ranking. So the questions this WP asks are narrower than
the others': which of the grading thresholds (the figure of merit bands, the `quick` preset's budgets,
the shortlist's cut) are de Wolff's and Smith–Snyder's, which are the engines' own
published defaults, and which are rietx's; and whether any gate still *refuses* rather
than reports.

**Families.** The acceptance suite's datasets and `tests/indexing_gallery.py`'s `DATASETS`
/ `TRUTHS` are the families; count by lab, instrument and material. The benchmark is a
ranking over one population and is the regression gate, not a family.

### Inherited

- **2026-10-27, from WP-2011: the indexer's validation fit is Pawley, and no row
  records its mode.** `rietx.indexing.workflow.VALIDATION_MODE` (`"pawley"`) is a
  module string, so the walk cannot see it; `LeBailValidation.mode` records it per
  candidate. The generality review of that branch rated the switch *holds* (tier 2 on
  `docs/practice.md`'s survey: TOPAS defaults to Pawley) and put its seat here: record
  it in the evidence of `rietx.indexing.workflow.index_pattern:validate` when this WP
  audits that row, unless the maintainer brings the indexing schemas into
  `RECORD_SCHEMAS`. The three tier-3 Pawley constants' ground ("opt-in Pawley mode")
  no longer holds on `index_pattern`'s path, and `PAWLEY_OVERLAP_FWHM_FRAC` was already
  read by the peak picker (WP-2011 § Tasks holds the ruling owed).

- **2026-10-23, from [1510](1510-what-the-chemist-knows-reaches-the-search.md) (closed):
  `Z_INTEGER_TOLERANCE` and `INDEX_Z_NOT_INTEGER` (`_audit.py:1155`, `:625`) rest on a
  volume that misses inorganic cells.** On fluorapatite's true cell the implied Z is 1.14, so
  the code fires on the right answer. The window misses 7 of 9 known cells measured
  (WP-2030's table). Hofmann's citation reaches organic and metal-organic crystals only.
  [2030](2030-a-formulas-volume-window-fits-inorganic-cells.md) owns the rule.
- **From WP-2002 (2026-10-21, 4th session): tier 2 names seven programs.** `docs/milestones/generality.md` § The rule's tier 2 now reads "by default in an established Rietveld program": GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and EasyDiffraction, the list rietx-bench runs (the maintainer's instruction). A row resting on a program default names the programs it checked and what each does; a program doing otherwise by default is a dissenter, one without the feature is neither. What each does on peak windows, staging, roughness starts, width limits, dispersion, solver, mode and background seed is in `docs/wp/2002-batch/practice.md`; where each program's manual or source sits is in the maintainer's memory (`foreign-code-sources-on-disk`), and rietx-bench's `tools/` holds BGMN, MAUD, RIETAN-FP and EasyDiffraction's environment beside GSAS-II and FullProf.
- **From WP-2001 (2026-10-19, PR #1047).** The table is `src/rietx/_audit.py`; this WP's rows are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2007, plus the codes and suggestion rows of its subsystem. Auditing a row means giving it a tier and evidence in place and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array is audited here by hand: `indexing.engines.SEARCH_PRESETS` holds the `quick` 120 s budget that way.
- **From WP-2001's generality judge (2026-10-19).** `index_pattern`'s `preset=None` resolves to `DEFAULT_SEARCH_PRESET = "quick"`, a string the walk drops (numbers only), so WP-1042's default has a row only as the `None` it starts from. `SearchSpec` is now a seat, since `spec=None` resolves to it.
- **From [2014](2014-a-heuristic-meets-the-judge-on-every-path.md)'s filing (2026-10-20): this WP owns `src/rietx/solve/`** (direct-space structure solution), the maintainer's ruling. It holds two module-level numbers today (`solve/cost.py`), and open PR #1016 adds `solve/chemistry.py` with six: `CLASH_FRACTION = 0.8`, `CLASH_SIGMA_ANG = 0.1`, `PRIOR_SHARE_MAX = 0.25`, `DEFAULT_CN = 6`, `INVENTORY_TOL = 0.05`, `PEAK_COUNTS = 1e4`. 2014 adds `"solve": 2007` to `WALKED`; until then these numbers are outside the table. The twelve open outside PRs touching the table (2014 § Context lists them) add indexing rows of their own, tiered at `/pr-review` before they merge, so some of this WP's rows arrive already ruled.
- **From [2014](2014-a-heuristic-meets-the-judge-on-every-path.md)'s close (2026-10-20, PR #1070).** `"solve": 2007` is in `WALKED`, and `solve/cost.py`'s `NAMED_REFLECTIONS = 5` and `NUISANCE_RCOND = 1e-12` entered at `unaudited` on the baseline: they are this WP's to tier. PR #1016's six `solve/chemistry.py` constants now trip `tests/test_audit_table.py` once it rebases, and CI's new `tests/audit_delta.py` step fails any of them entered at `unaudited`, so they arrive through `/pr-review` step 6b with proposed tiers.

- **From WP-2002 (2026-10-19, PR #1050).** 2002's batch class B13 proposes handing 9 `background.diagnostics` constants to this WP, pending the maintainer's ruling: the seven `GHOST_*`, `_ANODE_MATCH_TOL` and `_KBETA`. `flag_ghosts` drops a flagged line from `PeakList.usable()` (`indexing/pick.py` ~55, 96, 191), which is an action, so their tiers are this WP's.
- **From WP-1986 (2026-10-22, PR #1099), writing the indexing reference.** Two gate behaviours to rule on while tiering. (1) A candidate the ambiguity search never reached gets `geometric_ambiguity` (`indexing/consensus.py:627-632`), a refuting caveat, so under a binding whole-run ceiling every unreached candidate grades `low`; seven comments in `consensus.py`/`workflow.py` call that case *capping*, and `src/rietx/indexing/CLAUDE.md` § The scheduler says the streamed lists treat it as capping. Which is meant decides the wording WP-2013 fixes. (2) `VALIDATION_RESERVE_FRACTION` (`indexing/engines.py:2293-2309`) is there so the first click's shortlist arrives validated, and a default `index_pattern` on the bundled fluorapatite (2026-10-22, Linux `[dev]`, 130.7 s) validated none of its 12 candidates; the default qarr corundum run (121.3 s) entered four systems and ranked the certified R cell first.

- 2026-10-26 issue triage: #1059 is the outside contributor's (mustachefeeling) claim on this WP. It starts after the gate ruling and after their open indexing PRs land, and runs `tests.bethanechol_benchmark` alone before and after. Checked against the tree at c0e32ab29: status ⬜, nothing started.

## Non-goals

- Engine changes, a new engine, the narrowing and prior-counting items parked in ROADMAP
  (1046 § 4).
- `IndexingEvidence` and the two unreached companions: 2006's table rules on them.
- The extinction screen's use of `_run_stage`: 2002.

## Tasks

- [ ] Inventory: 48 codes and 76 constants with raise site, condition, what it grades or
      gates, and the dataset it was measured on (the dossier names most).
- [ ] Tier each per part; de Wolff (1968) M₂₀, Smith & Snyder (1979) F_N and each engine's
      published defaults are tier 2; the rest on evidence. The `quick` preset is a
      default, and its budgets (`QUICK_TOTAL_BUDGET_SECONDS`, `DEFAULT_BUDGET_SECONDS`)
      decide what the shortlist can contain, so they are not answer-invariant: state the
      preset's kind under DESIGN.md § Rules, 1 and tier the budgets like any constant.
      Rule 1's token clause is the case for a bounded first search; the case against is a
      cell the bound leaves off the list.
- [ ] `best_or_none()`: a first-kind pick on a second-kind ranking (the record § A pick
      on top of a ranking). Confirm no default path calls it, and tier its gate as the
      margin that makes the top candidate unanimous.
- [ ] The clash table: grading × gating × the `best_or_none` gate.
- [ ] The batch to the maintainer; rulings dated into the table.
- [ ] Approved demotions; a gate that refused now reports.
- [ ] `tests/test_acceptance_indexing.py` green and the benchmark run once alone on the
      final tree, its ranking recorded against the last nightly's.
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: `references/diagnostics-indexing.md` (4 277 words) rows re-tagged per the
      table.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no indexing/ row at unaudited
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -q
.venv/bin/python -m tests.bethanechol_benchmark                  # alone; ranking vs the nightly
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- `docs/milestones/generality.md`; `src/rietx/indexing/CLAUDE.md`; WP-1030, 1037–1042,
  1046.
- de Wolff, P. M. (1968). J. Appl. Cryst. 1, 108–113; Smith, G. S. & Snyder, R. L. (1979).
  J. Appl. Cryst. 12, 60–65.

## Handover log

- **2026-10-18** — created, from the milestone's opening session, split out of the
  readers' WP on the second review's sizing.
