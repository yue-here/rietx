# WP-2007 batch, part 1: the inventory, the proposed tiers, the clash table

What this folder holds: WP-2007's tasks 1, 3 and 4 done, and task 2's tiers *proposed*. **No row of the
audit table moved.** Every tier here is this WP's reading for the maintainer's batch (task 5), never a
ruling. It follows WP-2006's and WP-2005's part 1 (`../2006-batch/`, `../2005-batch/`).

| File | What it is |
|---|---|
| `inventory.json` | One row per code (raise sites with level, enclosing function, guarding conditions and the module constants that function names; files; suggestion sites; tests naming it), per module-level number in `indexing/`, `solve/` and `schemas/indexing.py` (value, shape, comment above it, citations in it, every function or class body reading it, whether the audit walk sees it), per default at the two seats, the suggestion rows, and the eight B13 constants pending hand-over. Each code, constant and default carries the hand-written judgement and its current tier. Made by `collate_inventory.py`. |
| `judgements.json` | The only hand-written input. Per code: the condition in words, the kind of ambiguity (DESIGN.md § Rules, 1), a proposed tier for each part (statistic, threshold, action), the families it was measured on, the evidence and, where one is owed, a question. Per constant and default: role, what it decides, measured on, proposed tier, evidence, question. |
| `collate_inventory.py` | Derives the rest from the tree and refuses an item with no judgement, a judgement for an item the tree no longer has, a tier or role outside its vocabulary, and a text cut short (WP-2006's rule). `--skeleton` prints what a judgement reads. |
| `clashes.md` | Task 4: grading × gating × the `best_or_none` gates, eleven clashes (K1-K11), each with `file:line`, two measured on the Mac. |

Run it with `.venv/bin/python docs/wp/2007-batch/collate_inventory.py`.

## The counts, at `94a35558b` (2026-11-16)

- **50 codes**, not the WP's 48, at 60 raise sites: 45 `unaudited`, 3 tier 3, 2 tier 1. Kind: 26 the
  data settle, 18 the data can rank, 6 the data cannot settle. Proposed, by part: statistic 29 tier 1,
  9 tier 2, 12 tier 3; threshold 3 / 4 / 32 (11 have none); action 12 tier 1, 36 tier 3, 2 `caller`.
  50 suggestion rows (47 `unaudited`), tiered with their code.
- **188 module-level numbers**, not 76: 163 the audit walk sees (148 `unaudited`, 7 tier 1, 2 tier 2,
  6 tier 3) and 25 it cannot (dicts, lists, enumerations; mostly crystallographic tables, plus
  `engines.SEARCH_PRESET_INFO`, `svd.CONTROL` and `schemas.indexing.METRIC_DOF`). Proposed: 54 tier 1,
  20 tier 2, 102 tier 3, 12 invariant. Two names the walk drops are recorded by hand in the default rows:
  `engines.DEFAULT_SEARCH_PRESET = "quick"` (under `index_pattern:preset`) and `workflow.VALIDATION_MODE
  = "pawley"` (under `index_pattern:validate`). `engines.SEARCH_PRESETS` holds names, not numbers, so the
  120 s is `QUICK_TOTAL_BUDGET_SECONDS`'s row. `fom.FOM_N` (an alias of `PEAK_MIN_USABLE_LINES`) and
  `ambiguity.UNCANCELLABLE_METRIC_RTOL` (a sine of `reduce.BRAVAIS_OBLIQUITIES`) hold no literal and are
  kept because the walk sees them.
- **32 defaults** at `index_pattern` and `SearchSpec`: 31 `unaudited`. Proposed: 14 tier 3, 10 `caller`,
  3 tier 2, 3 tier 1, 2 `n/a` (`spec` and `quality` hand off to other rows; whether `n/a` is allowed
  there is a question).
- **One action row** (`PeakList.instrument_undeclared`, tier 1). **Eight B13 constants**
  (`background.diagnostics`' seven `GHOST_*` and `_ANODE_MATCH_TOL`; `_KBETA` is a dict, which the walk cannot see, so it has no row) stay
  WP-2002's until the maintainer rules the hand-over; they are listed, not judged.
- **Fewer than the WP's names.** `Z_INTEGER_TOLERANCE` and `INDEX_Z_NOT_INTEGER` are gone (WP-2030,
  PR #1237, `schemas/indexing.py:218`). Of PR #1016's six `solve/chemistry.py` constants none is in the
  tree; `OCCUPANCY_MAX_DENOMINATOR` and `_CELLS27` are.

## Task 3: `best_or_none()` is called on six default paths

The WP asks to confirm that no default path calls it. **It does not hold.** `IndexingResult.best_or_none`
(`schemas/indexing.py:2245`) is called by the result's own text display (`_verdict_lines`, `:2231`,
printing `CELL:` or `NO CELL`), by `index_diagnostics`, which raises `INDEX_ABSTAINED` on every run it
returns `None` (`indexing/diagnostics.py:893`, a report), by `workflow._emit_end`'s `index_end` event (`workflow.py:1211`, its
`cell` and `abstained` fields), by the CLI's exit code (`cli.py:374`) and by the GUI's `picked` row and
adopt label (`gui/session.py:2593`, `:2836`). `ExtinctionScreen.best_or_none` (`:2614`) is called by
the GUI's extinction route (`gui/session.py:2803`), which badges the class. None of them applies a cell
or a class unasked: since WP-2124 (ruling B, 2026-11-08) every row can be adopted. They present a
first-kind pick on top of a second-kind ranking. The approved grounds of `EXTINCTION_SCREEN_UNRELIABLE`
(`_audit.py:684`, "no default path calls the pick") are therefore out of date (clash K7).

The gate's margin. For cells there is no number: the pick needs exactly one candidate at `high` and no
ambiguity partner, and `high` needs zero caveats, so the margin is "every engine that ran found it,
validated, nothing refuting or capping". The gate's own rule is arithmetic over the grade (proposed tier
1); what it inherits is the tiers of the caveats and of `MIN_AGREEMENT`. It abstains on two `high` cells
the data separate (K10). For extinction classes the margin is `DECISIVE_DELTA_BIC` behind the
`REFERENCE_NET_RWP_MAX` gate.

## What the walk cannot see

- A number inside a function body (an inline literal). This inventory reads module level only; the
  constants each raising function names are listed per code, the literals are not.
- A rule expressed as a set of strings: `INDEX_REFUTING_CAVEATS` (which caveats refute and which cap) is
  judged under `INDEX_MIN_INDEXED_FRACTION`'s evidence and in `clashes.md`.
- Readers are found by name, so a constant reached through an alias (`FOM_N`) is listed under the alias.
- The proposals come from four read-only agents, one per slice, each told the rule, the tier
  vocabulary and the held-out fence; this session checked a sample against the tree (Z_INTEGER_TOLERANCE's
  removal, the caveat builder at `consensus.py:640-700`, the practice survey's windows, every
  `best_or_none` call site). The 89 questions they and the review raised ride in `judgements.json`.
