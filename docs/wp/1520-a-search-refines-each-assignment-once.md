# WP-1520 — a search refines each line assignment once (gated: build only if assignments repeat)

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: — (1509 measured the cost and built the replay harness this reuses)
Priority: P3 2026-09-28 — cost only: the largest leaf cost left in every real 2-D unit (40-46 %), with an exact lever whose hit rate nobody has counted

## Goal

Answer "how often does an indexing search solve the same cell refinement
twice?" with a count, and if the answer is often, have each engine solve a
given line assignment once per unit and reuse the fit. Every finished search
stays bit-identical.

## Context

**What 1509 left.** After WP-1509, `qspace.refine_candidate` is the largest
cost in every real 2-D dichotomy unit. It is work a leaf needs, but it is not
known to be work a leaf needs *more than once*. Profile, serial, 50 Hz, `[dev]`,
Linux x86-64, 4 cores, py3.12, numba 0.67.0, numpy 2.5.3 on OpenBLAS 0.3.34:

| unit | wall | leaves | `refine_candidate` |
|---|---|---|---|
| brucite hexagonal | 106.7 s | 81 % | 42 % |
| brucite trigonal | 97.0 s | 86 % | 44 % |
| corundum hexagonal | 80.6 s | 85 % | 46 % |
| corundum trigonal | 82.7 s | 87 % | 46 % |
| corundum tetragonal | 236.5 s | 72 % | 40 % |

Real 4-D data is leaf-bound too once the traversal is compiled (WP-1508:
bethanechol set F's 30 s manual-mode unit spent 67 % in leaves). Trial and
error's synthetic monoclinic unit is 339.7 s after 1509, down from 346.5 s. Its
scoring sets are too small for 1509's index (2456 rows), so its `_score` loop is
where its time still goes.

**Why an exact memo exists.** Without a shift, `refine_candidate(q, q_esd, hkl,
system=…)` is one weighted `lstsq` plus `_covariance`, `cell_from_af` and
`cell_esds`. It is a pure function of its arguments, and inside one unit
`q_all` and `sigma` are fixed. So `(line_index.tobytes(), assigned.tobytes(),
system)` determines the fit. `refine_with_shift` is likewise pure in the fit,
the assignment and the unit's fixed inputs. A cache keyed that way returns
the same doubles by construction. No platform claim is involved, unlike
WP-1509's product and WP-1519's stack.

**Where repeats could come from** (read off the code, none counted):
- **`dichotomy._accept`'s anneal.** Up to `MAX_ASSIGN_PASSES` + 2 = 6 passes per
  leaf per centring. The early exit fires only after the schedule (`extra ≥ 4`)
  and compares `line_index` alone, so a schedule pass whose assignment did not
  change solves the same system again. The refinement reads the raw σ, never
  the pass's floor.
- **One leaf, several centrings**, where two centrings assign the same lines
  the same hkl.
- **Sibling leaves converging on one cell.** WP-1509 found 7000 raw candidates
  holding 761 distinct cells on bethanechol F's cut unit. But corundum's
  finished tetragonal unit held 4942 lattices in 5037 candidates, so this
  source varies by an order of magnitude between units.
- **`trial_error._score`.** Distinct exact solutions (`solution_key`) that
  settle onto one assignment by the second pass. **`svd`'s loop** runs three
  passes plus a final fit.

The count decides everything. If repeats are rare the cache is overhead, and
this closes 🛑 with the numbers, as WP-1508's gate did for the 2-D traversal.

**Traps.**
- **A shared fit must not be mutated downstream.** `CandidateFit` rides inside
  each `EngineCandidate`; `found_by` lives on the candidate, but check every
  writer before handing one object to two candidates, or hand out copies.
- **The key is the assignment, not the line set.** `_accept`'s exit compares
  `line_index` only; two passes can match the same lines to different hkl.
- **Memory.** A few KB a fit; trial_error may score ~10⁵ solutions a unit. Size
  the cache from the measured count. An LRU changes hits, never answers.
- **The bar is WP-1509's**: finished units replayed to their digests (brucite
  hexagonal `c82630be`, trigonal `719d4e0b`; corundum hexagonal `6a060c83`,
  trigonal `e8466d7f`, tetragonal `f610fbdc`; synthetic monoclinic
  `fc4d2b0b`), down to the hkl and line-assignment bytes. The harness captures
  each unit by swapping `engines._REGISTRY` for recorders and running
  `index_pattern` once, then replays per unit. The digest is sha256 of
  `np.array([[*cell, n_indexed] …], float64).tobytes()`. The scripts were
  session scratch; if WP-1519 rebuilt them, reuse its. If WP-1518 has landed,
  hold the digests its handover names.
- Compare timings at one BLAS thread setting: default-thread OpenBLAS made the
  leaves' small products slower than one thread (1509: 82-94 s against 91-112 s
  on the same tree).

### Inherited

- **2026-10-10, from WP-1940 (4th session, PR #864).** The dichotomy traversal now
  runs on numpy alone. § Context's 40-46 % leaf share was measured with the
  compiled traversal (numba 0.67.0), so the traversal's own share is now
  larger and the leaves' smaller. WP-1508 measured the numpy loop at
  1.03-1.09× on real patterns. Re-measure the share before ranking this lever.

- **From WP-1518 (closed 2026-09-28): a digest belongs to a platform, and 1518
  moved five of the six.** The digest hashes the cells' bits. On macOS arm64
  (system BLAS) not one of 1509's six Linux x86-64 digests reproduced on the
  unchanged path. On that Mac, 1518's covariance fix moved brucite hexagonal
  `2b9bc538` → `40752146` and trigonal `e2117cb2` → `867bb1f5`, corundum
  hexagonal `3190bee2` → `f6b582ba` and trigonal `2d3b0c80` → `3e5ac067`, and
  synthetic monoclinic through `index_pattern` `a9f00c79` → `57a6a9e3`.
  Corundum tetragonal held at `8a5fd6cd`. On any other platform, take the
  post-1518 digests from the current tree before holding anything. Dedup
  groups moved, so a unit's candidate list moves from the first pool rank a
  changed group reaches (rank 4-16 of 60 on these units).
- **From WP-1519 (2026-09-29): the harness is committed, and here are the Linux
  digests.** `python -m tests.unit_replay capture DIR`, then `replay DIR UNIT`
  (`--count` counts dedup's χ² tests, `--save` keeps a result for `pool`). On
  Linux x86-64 (numpy 2.5.3, OpenBLAS 0.3.34) the post-1518 digests, unchanged
  by 1519's stacked dedup, are brucite hexagonal `56677409`, trigonal
  `816c0422`; corundum hexagonal `605772e8`, trigonal `aa4fd3f9`, tetragonal
  `f610fbdc`; synthetic monoclinic `ac68ad82`. 1509's synthetic monoclinic
  (`fc4d2b0b`) is the engine called directly with `spec_for`, not a unit
  captured through `index_pattern` (`c6acb64f` now); the harness carries both.
  Dedup no longer dominates the tetragonal unit's non-leaf time (6.5 s of
  ~140 s alone), so a leaf profile there reads cleaner than 1509's.

## Non-goals

A faster solve for the same system. A closed-form 2×2 normal equation would beat
`lstsq` on a 2-D metric but changes the last bits and every digest, which is a
different bar and the maintainer's decision. `engines.TrialIndex` in svd's
assign-and-refine loop and in `priors._check_one`: both still scan whole trial
sets, but svd costs seconds a run (the dossier's Coelho-gate rule) and a prior
is checked once per stated cell. 1509's 15 000-row floor exists because small
sets were measured slower. Revisit only with a profile showing either one.
Dedup (WP-1518, WP-1519).

## Tasks

- [ ] **Count first.** Instrument the replay (a counter keyed as above; no
      behaviour change) on the five 2-D units, synthetic monoclinic,
      trial_error's corundum hexagonal and synthetic monoclinic units, and
      bethanechol set F's manual-mode unit. Record calls, distinct keys and the
      share of `refine_candidate` + `refine_with_shift` time the repeats
      carry. **Gate:** build if repeats are ≥ ~20 % of that time on the real
      units; otherwise close 🛑 with the table.
- [ ] A per-unit cache in each engine that repeats, keyed on the assignment;
      replay every unit to its digest on both traversal paths
      (`RIETX_COMPILED=0` too).
- [ ] Tests: the cached and uncached searches equal on the fast synthetic cases
      (candidates, hkl, line indices, leaf order), and a case built so two
      passes share `line_index` with different hkl, which a line-set key would
      wrongly merge. Make each fail once on purpose.
- [ ] Re-profile the units; `tests/test_acceptance_indexing.py` once on the
      final tree; `tests.bethanechol_benchmark --modes manual`, run alone,
      before and after.
- [ ] Skill: none expected (no call an agent makes changes); say so at close.

## Acceptance

Gate reading recorded with its counts. If built: every finished unit's digest
unchanged on both paths, and the units re-profiled.

```sh
.venv/bin/python -m pytest tests/test_indexing_kernels.py tests/test_indexing_engines.py -n auto --dist loadgroup
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_indexing_kernels.py tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

WP-1509 (the profile, the harness, the digests); WP-1508 (the gate this copies,
and set F's leaf share); WP-1030 (why the centred pass replays at the leaf).

## Handover log

- **2026-09-28** — filed from WP-1509's *Next* (item 3: `refine_candidate`'s
  per-pass `lstsq`, and the index in svd and priors, fenced here with the
  reason).
