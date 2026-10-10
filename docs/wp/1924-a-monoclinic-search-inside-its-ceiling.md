# WP-1924 — A monoclinic search stays inside its ceiling and its memory

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: — (1520 soft, the same units' leaf cost; 1508 closed)
Priority: P2 2026-10-08 — a defect that fires wrongly: a declared ceiling overrun and a multi-GB peak on a clean 61-line monoclinic pattern, with the workaround of capping the volume and the systems by hand; the reporter's 9 GB and 25.8 GB are the reason it is not P3

## Goal

A monoclinic search of a clean pattern for a V ≈ 224 Å³ cell finishes inside a stated time and memory bound on a laptop. A declared `total_budget_seconds` holds to within one unit's slice, and the peak resident set is a number the docs state per engine.

## Context

**Issue #780 (mustachefeeling, 2026-10-06, Linux x86 WSL2, 1.7.0.dev0).** Synthetic lab pattern, 62 usable lines, V = 224 Å³, `SearchSpec(systems=("monoclinic",), max_volume=600, budget_seconds=900)`, `preset="full"`. `dichotomy` and `trial_error` report `INDEX_SEARCH_INCOMPLETE` at 900 s, only `svd` finds the lattice, wall 1967 s, peak RSS 9.0 GB. A second dataset (≈5300 Å³ hexagonal, private) reached 25.8 GB at 31 min.

**Measured on 2026-10-08** (5d1f5f67, `[dev]`, macOS arm64, numba on; `scratchpad` scripts `repro-780.py`, `mem-780.py`). Synthetic P 1 2/m 1, a = 4.541, b = 4.884, c = 10.198 Å, β = 98.22° (V = 224 Å³), 61 lines to 55° 2θ, `systems=("monoclinic",)`, `max_volume=600`, `preset="full"`, `validate=False`, ceilings 15-120 s. The slice cannot show the 900 s behaviour. It shows the shape:

| engine | ceiling | wall | peak RSS |
|---|---|---|---|
| dichotomy | 15 s | 16 s | 2.4 GB |
| dichotomy | 30 s | 32 s | 2.1 GB |
| dichotomy | 60 s | not recorded | 1.9 GB |
| trial_error | 60 s | 41 s | 0.44 GB |
| svd | 15 s | 19 s | 0.22 GB |
| svd | 30 s | 32 s | 0.28 GB |
| svd | 45 s | 56 s | 1.9 GB |
| svd | 60 s | 110 s, then 38 s | 2.5 GB, then 0.66 GB |
| all three | 120 s | 108 s | 2.6 GB |

Dichotomy reaches about 2 GB inside 15 s and then holds: a fast allocation, not growth with time. svd's peak varies by 4× between two runs of one setting and overran its ceiling by 50 s once and 11 s once. All three engines still return the lattice's reduced cell as candidate 0 (svd alone at 60 s) with `INDEX_SEARCH_INCOMPLETE` on dichotomy and trial_error. `tracemalloc` slows the run so far that the peak does not appear (200 MB traced, 0.5 GB RSS), so use RSS and a sampling profiler, not `tracemalloc`.

Not yet established: what dichotomy holds at 2 GB; whether the 9 GB is that allocation scaling with the 900 s budget or the candidate harvest `dedup_groups` describes (thousands of raw candidates per unit); whether svd's overrun is search, post-processing (supercell checks, Bravais opinion) or a deadline read at too coarse a boundary. The reporter's claim that published dichotomy implementations take seconds (Boultif & Louër 2004) is for a different algorithm's box budget and is not evidence about this one. `indexing/CLAUDE.md` already says the package is silent rather than slow, and "buy responsiveness with ordering and reporting, never by shrinking the box".

### Inherited

- **2026-10-10, from WP-1940 (4th session, PR #864).** The dichotomy traversal now
  runs on numpy alone: its numba twin is deleted. § Context's measurements
  were taken with numba on. On WP-1508's synthetic monoclinic list the numpy
  loop takes ~200 s where the compiled one took 10 s, so a box-bound monoclinic
  search spends far more of its ceiling in the traversal. Re-measure before
  building on those numbers. A compiled port would go into the
  `rietx-kernels` crate, held to the numpy loop leaf by leaf
  (`indexing/CLAUDE.md`).

## Non-goals

- Shrinking the metric box to buy speed (`indexing/CLAUDE.md`).
- The leaf cost of `refine_candidate` (WP-1520, gated on a count).
- The reporting of the candidate's setting (the 779 WP).

## Tasks

- [ ] Profile one dichotomy unit for memory with a sampling tool, not `tracemalloc`, on the monoclinic fixture above. Name the allocation, its size as a function of box count and of `max_volume`, and whether it is released.
- [ ] Do the same for svd's 0.2-2.5 GB spread, and find where the 11-50 s past the ceiling is spent.
- [ ] Fix what the profile names, keeping every finished search bit-identical (`python -m tests.unit_replay`, digests per platform; 1519's harness).
- [ ] Add a peak-RSS figure to `estimate_ceiling` or to the result's budget diagnostic if the profile shows it is predictable from the spec, so a caller can see it before a run.
- [ ] Tests: a bounded-memory guard that fails on the allocation, declared with its measured spread (a pass margin under 10× is a load sensor). Quote platform and extras with every count.
- [ ] Skill: the indexing reference row for a monoclinic or hexagonal search with a large volume bound (cap the volume, search one system at a time, read `INDEX_SEARCH_INCOMPLETE` per engine), tagged Measured or Hypothesis.

## Acceptance

```sh
.venv/bin/python /path/to/repro-780.py 120      # RSS and wall within the stated bound
.venv/bin/python -m pytest tests/test_indexing_scheduler.py tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Boultif & Louër (2004), *J. Appl. Cryst.* 37, 724 (DICVOL04).
- WP-1508, WP-1509, WP-1519 (the unit replay harness), WP-1520.

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #780). Checked against the tree at 5d1f5f67: `git log --since=2026-10-06 -- src/rietx/indexing` shows only #726, #747 and WP-1545 work, none on memory or the deadline; no PR cites #780. Reproduced as a bounded slice only (ceilings 15-120 s; the 900 s run and the 9 GB were not attempted): dichotomy 1.9-2.4 GB inside 15 s, svd up to 2.5 GB and past its ceiling by 11-50 s. No open WP owns it: 1520 is the leaf cost of `refine_candidate` and gated on a count, 1334 and 1335 are refinement stages and reports, 1508 is closed (the traversal compiled, memory never measured).
