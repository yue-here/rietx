# WP-2110 — A trial_error unit stays inside its memory under a raised budget

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: —
Priority: P2 2026-11-05 — a run killed for memory returns nothing, and the skill's own advice for a unit cut by time (raise `budget_seconds`) is the route to it; the default 30 s slice cuts it short since #1244, which is why it is not P1

## Goal

A trial_error (engine × system) unit's memory is bounded by a named module
constant, whatever its `budget_seconds`. A unit that reaches the bound stops,
reports `complete=False` with `INDEX_SEARCH_INCOMPLETE` ("outgrew a size cap
on …"), and returns every candidate it had already built.

## Context

- **The report** (issue #1376, carried from #780's 2026-10-14 measurements;
  not re-run since). The list is glutaric acid–isonicotinamide form II, a
  synthetic list from the published cell: `tests/data/cod_1567181.cif`,
  P 1 2₁/a 1, a = 26.371, b = 5.2029, c = 8.904 Å, β = 99.325°,
  V = 1205.5 Å³, Cu Kα 5–34° 2θ, 49 lines. One engine per process, every
  system, a 600 s per-unit cap, a 32 GB Mac at load 2–8, measured at
  `86f947987` (before WP-1959's kernels and before #1244). trial_error
  ran 1696 s and peaked at **9.2 GB** (physical footprint, as
  `tests/repro_780.py` reads it). It reached the true cell at rank 1 about
  16 min into its monoclinic unit. With two impurity lines added it ran
  2094 s, peaked at 8.7 GB and found nothing. On the same lists svd peaked
  at 0.34 GB or less. trial_error's monoclinic unit also ran 998 s and
  1372 s against a 600 s budget there; that overrun is fixed (next bullet).
- **What has moved since.** #1244 (WP-1924, 2026-10-31) made
  `trial_error._search_system` read its `Budget` before each `_score`, so a
  unit now stops within about 1.5 s of its slice. Under the default 30 s
  slice the 9.2 GB run is cut long before it peaks. A caller who raises
  `budget_seconds` still reaches the allocation. The skill's
  `INDEX_SEARCH_INCOMPLETE` row (`docs/skill/rietx/references/diagnostics-indexing.md`)
  advises exactly that when a unit ran out of time. The same PR bounded
  dichotomy's memory (`dichotomy.MAX_GRID_BYTES` = 1 GiB of survivor lists,
  `dichotomy.MAX_HARVEST` = 20 000 accepted leaves, both tier 3, approved
  2026-10-31). svd measured 0.34 GB or less. So trial_error is now the only
  engine with no memory bound.
- **What in the unit can grow** (read from the tree at `541f0daf7`, not
  measured; the profile decides which, if any, it is):
  1. `seen`, the set of `engines.solution_key` tuples in `_search_system`.
     It gets one entry for every distinct exact solution scored, spans the
     centring loop, and is never pruned. It grows with the number of
     solutions, not with the number of candidates.
  2. `found`. `dedup_candidates` runs when `len(found) > 2000`, read once
     per base, so `found` grows with the number of *distinct* lattices
     accepted, and one base can append any number of candidates before the
     check. Each `EngineCandidate` carries a refined fit and per-line arrays;
     WP-1924 measured about 11 KB pickled for dichotomy's.
  3. One base's working set. `_combos` builds the Cartesian product of the
     base lines' allowed labels: up to `MAX_ASSIGN_PER_BASE` (4 000 000) rows
     × n_dof int64, plus the meshgrid. `_solve_assignments` holds the
     survivors' metrics and combos. This is transient and released per base,
     so it sets a floor, not a growth with time.
  4. The scoring set per centring: `trial_hkl(_scoring_index(...))`,
     `design_matrix` and `TrialIndex.build`. These are sized by
     `max_d_axis·√Q_max`, built once per centring, and fixed in time.

  #1376 says the growth "may be elsewhere, for example in the trial index
  tables or the base list". **Profile before ranking**
  (`src/rietx/indexing/CLAUDE.md`: a cost model reasoned from the
  algorithm's structure is not a profile).
- **How to profile** (WP-1924 § Profile, mirrored). Sample the process's
  physical footprint (`tests/repro_780.memory_bytes`, `proc_pid_rusage` on
  macOS) in a thread, and log the unit's own counters at each base boundary:
  `len(seen)`, `len(found)`, the base's `len(combos)`, the elapsed CPU. The
  growing allocation is the counter whose size tracks the footprint's
  growth. Confirm it with a scratch change that drops that one structure,
  never by inference. **Not `tracemalloc`**: WP-1924 measured that it slows
  the run so far that the peak never appears (200 MB traced against 0.5 GB
  RSS). macOS leaves compressed pages out of the RSS (57 MB against 1.9 GB
  of footprint under load, WP-1924), so read the footprint, at equal work:
  count the clock in CPU seconds (`repro_780 --cpu-clock`'s device) so a
  loaded machine does not search less and peak lower. A run to the reported
  peak is about 16–30 min. Run it alone.
- **The bound.** It is a named constant in `trial_error.py`, on the
  structure the profile names, counted as what is *held* (distinct entries
  after any dedup), never raw arrivals. `dichotomy.MAX_HARVEST`'s audit
  verdict was "weak" because it counts raw leaves, mostly copies. Reaching
  it ends the unit with `complete = False`, and the existing branch in
  `search_trial_error` files a unit that is neither cancelled nor out of
  time under `capped`. So `incomplete_diagnostic` already says "outgrew a
  size cap on <system>" and advises narrowing rather than more time. No new
  diagnostic code is needed. The unit returns `found` as it stands: a cap
  never discards a candidate already built, and the count rides in
  `stats["<system>.…"]` as dichotomy's `harvest` does. If the profile names
  `seen` and nothing else, there is a second form: evict from `seen` and
  keep searching. That costs only time, which the budget bounds (the
  maintainer's 2026-10-30 reasoning on dichotomy's truncated frontier, WP-1924
  § Unbounded routes). But a re-scored duplicate can change which member
  dedup keeps, so finished searches would no longer replay. Record which
  form was chosen and why; the default is stop-at-cap, as #1376 asks.
- **Equivalence bar.** Every finished search is bit-identical: the cap must
  not fire on any unit that finishes today. Use
  `python -m tests.unit_replay` against the trial_error digests in WP-1924's
  2026-10-31 handover (brucite `f14bfc55`; corundum cubic `e3b0c442`,
  hexagonal `6f277e25`, tetragonal `e8addc35`, trigonal `397c20a8`; macOS
  arm64, compiled tier on). Size the constant so that the largest finished
  trial_error unit on the acceptance and bethanechol lists sits well inside
  it, and quote that margin.
- **Tier.** The constant is new judgement, a memory bound of rietx's own,
  so it is tier 3, as `MAX_HARVEST` and `MAX_GRID_BYTES` were. Its
  `rietx._audit.ROWS` row carries `grounds` (the measured largest finished
  unit and the margin) and needs the maintainer's dated `approved`.
  `tests/test_audit_table.py` stays red until he writes it, which is the
  documented waiting state. Never enter it at `unaudited`:
  `tests/audit_delta.py` fails a new name there.
- Licensing: nothing ported. trial_error follows Werner, Eriksson &
  Westdahl (1985) and Altomare *et al.* (N-TREOR), from the papers only.

## Non-goals

- The time budget and how a ceiling shares among units (#1374, WP-1924's
  last task). This WP bounds memory, not time.
- WP-1924's dichotomy caps, which are on main. This WP mirrors them and
  changes neither.
- The consensus list's 12-cell cap (#1375).
- trial_error's search order, `BASE_POOL_MIN`, `BASE_INDEX_MAX` or
  `MAX_ASSIGN_PER_BASE`. A cap is not a pruning rule.

## Tasks

- [ ] A repro for the case, on `tests/repro_780.py`'s pattern (a
  `--case`/`--engines trial_error` arm there, or `tests/repro_1376.py`
  importing its `memory_bytes` and `cpu_clock`). It builds the list from
  `cod_1567181.cif`'s cell at Cu Kα1 over 5–34° 2θ, searches monoclinic only,
  with a raised `budget_seconds`, and prints the wall, the peak footprint,
  the unit's clock and completeness, candidate 0, and the sampled curve on
  `--trace`. Record the line count it builds against the reporter's 49.
- [ ] Profile one unit on main under a raised budget (§ Context, *How to
  profile*). Name the allocation that grows, its size as a function of
  bases walked and solutions scored, and whether it is released. If no
  allocation grows on main, say so with the curve, and close the WP with a
  test pinning the bound that holds.
- [ ] The bound: a named constant on what the profile names. Reaching it
  ends the unit `complete = False` through the existing `capped` path, keeps
  `found`, and records the count in `stats`. Add the audit row (tier 3,
  `grounds`, approval asked in the PR). Finished units replay to their
  digests (`tests.unit_replay`).
- [ ] Tests in `tests/test_indexing_engines.py`, beside
  `test_a_dichotomy_unit_stops_at_its_harvest_cap`. On a small synthetic case
  whose uncapped unit finishes with at least two candidates (assert it, so the
  test cannot go quiet), monkeypatch the constant low and assert:
  `search_complete[system]` is `False`; `INDEX_SEARCH_INCOMPLETE` says
  "outgrew a size cap on <system>"; the capped unit's `found` is a **prefix**
  of the uncapped unit's in enumeration order (call `_search_system` directly,
  on a case where the in-loop dedup never fires); and every ranked capped
  candidate is the same lattice as an uncapped one (`same_lattice` on the
  reduced cell, never a cell tuple). Add a bounded-memory guard that counts
  the bounded structure's entries, a deterministic count with an exact
  margin, not an RSS figure, which would be a load sensor. Make each new test
  fail once on purpose (`tests/CLAUDE.md` § Guards that go quiet).
- [ ] `tests/test_acceptance_indexing.py` before closing
  (`src/rietx/indexing/CLAUDE.md`: an engine change is not closed on the fast
  indexing tests alone).
- [ ] Skill: likely none. The `INDEX_SEARCH_INCOMPLETE` row already limits
  "raise `budget_seconds`" to the "within … s per system" message, and a cap
  reads "outgrew a size cap". Confirm that, and say so in the handover.

## Acceptance

```sh
.venv/bin/python -m tests.repro_1376 --cpu-clock 1800   # or repro_780's new arm: the peak footprint inside the stated bound, the unit capped or finished
.venv/bin/python -m tests.unit_replay replay <dir>      # trial_error units at their WP-1924 digests (macOS arm64)
.venv/bin/python -m pytest tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_audit_table.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Werner, Eriksson & Westdahl (1985), *J. Appl. Cryst.* 18, 367–370
  (TREOR90); Altomare *et al.* (2000), *J. Appl. Cryst.* 33, 1180–1186
  (N-TREOR), the engine's method.
- Linberg, Röder, Al-Sabbagh, Emmerling & Michalchuk (2023), *Faraday
  Discuss.* 241, 178–193 (the case's cell; COD 1567181).
- Issues #1376 (this WP's), #780 (the parent), #1374, #1375; PR #1244
  (the dichotomy caps and trial_error's per-`_score` budget read); WP-1924
  (`docs/wp/1924-a-monoclinic-search-inside-its-ceiling.md`, closing in PR
  #1373); WP-1519 (`tests.unit_replay`).

## Handover log

- **2026-11-05** — created from issue #1376 (planning only, no code). No
  open WP owns it: WP-1924 bounded dichotomy, filed #1376 as a follow-up it
  does not own, and closes in PR #1373. Its last task, the time share, is
  #1374, which bounds time, not memory. The growth candidates in § Context
  come from reading `trial_error.py` at `541f0daf7`; nothing was run. The
  first action is the repro and the profile.
