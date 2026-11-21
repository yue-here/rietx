# WP-2110 — A trial_error unit stays inside its memory under a raised budget

Milestone: unscheduled · Status: 🔄 2026-11-16 — every task done in PR #1586; `MAX_SEEN`'s tier-3 audit row waits on the maintainer's dated approval, and with it whether 4 000 000 is the bound
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

- [x] A repro for the case, on `tests/repro_780.py`'s pattern (a
  `--case`/`--engines trial_error` arm there, or `tests/repro_1376.py`
  importing its `memory_bytes` and `cpu_clock`). It builds the list from
  `cod_1567181.cif`'s cell at Cu Kα1 over 5–34° 2θ, searches monoclinic only,
  with a raised `budget_seconds`, and prints the wall, the peak footprint,
  the unit's clock and completeness, candidate 0, and the sampled curve on
  `--trace`. Record the line count it builds against the reporter's 49.
- [x] Profile one unit on main under a raised budget (§ Context, *How to
  profile*). Name the allocation that grows, its size as a function of
  bases walked and solutions scored, and whether it is released. If no
  allocation grows on main, say so with the curve, and close the WP with a
  test pinning the bound that holds.
- [x] The bound: a named constant on what the profile names. Reaching it
  ends the unit `complete = False` through the existing `capped` path, keeps
  `found`, and records the count in `stats`. Add the audit row (tier 3,
  `grounds`, approval asked in the PR). Finished units replay to their
  digests (`tests.unit_replay`).
- [x] Tests in `tests/test_indexing_engines.py`, beside
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
- [x] `tests/test_acceptance_indexing.py` before closing
  (`src/rietx/indexing/CLAUDE.md`: an engine change is not closed on the fast
  indexing tests alone).
- [x] Skill: likely none. The `INDEX_SEARCH_INCOMPLETE` row already limits
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

- **2026-11-16** — A trial_error unit's memory now has a ceiling. The profile
  found what grows: the set of solutions the unit has already scored, about
  0.4 KB an entry and never pruned, while the candidates it keeps stay in the
  hundreds. A unit that reaches 4 000 000 entries (about 1.7 GB) now stops,
  says it outgrew a size cap, and returns every candidate it had built.
  Searches that finish today are untouched. #1376's list still finds its
  true cell at rank 1 before the cap. The number is a proposal: the
  maintainer approves it or picks another, and the audit test stays red
  until he dates the row. PR #1586.
  - *Done.* `tests/repro_1376.py` (item 1): the list from
    `cod_1567181.cif` at Cu Kα1 over 5–34° 2θ has **63** lines against the
    reporter's 49. The reporter's builder is not recorded, and merging lines
    within 0.08° gives 48, so the two lists differ. It has `--trace` (the
    per-base counters, read by wrapping the module's functions) and
    `--max-gb` (exit 3 on a shared machine). `trial_error.MAX_SEEN`
    stops a unit before it adds an entry past the cap (stop-at-cap, the
    default #1376 asks for). It goes through the existing `capped` path,
    and `<system>.seen` rides in `stats` beside `solves` and `seconds`.
    Two tests sit beside the harvest-cap test: the prefix/`same_lattice`
    test and an exact-count guard at caps 1, 7 and 300. Each failed once on
    purpose (`>` for `>=`; cap removed). The `_audit` row is tier 3 with
    `grounds`, `approved` None. Skill: unchanged, confirmed. The
    `INDEX_SEARCH_INCOMPLETE` row limits "raise `budget_seconds`" to the
    "within … s per system" message, and a cap reads "outgrew a size cap".
  - *Measured, profile* (a Linux x86-64 workstation, `--cpu-clock`, at
    `2e4e4304d` = main + the repro). At 1 800 CPU s there were 2.24 M
    entries in `seen`, the peak was 1.14 GB RSS, `found` held 196, and
    41 bases had been walked. At 4 000 CPU s: 5.03 M entries, 2.31 GB, 200
    found, 60 of 140 bases walked, still unfinished. Linear, about 0.43 KB
    an entry, so a finish is about 12 M entries and about 5 GB, the
    reporter's scale. The true cell was candidate 0 in both runs. Confirmed
    by a scratch tree with `seen.add` removed: 0.25–0.30 GB flat at
    600 CPU s, against 0.58 GB on main at equal CPU. Form chosen:
    stop-at-cap, not eviction, because eviction lets a re-scored duplicate
    change which member dedup keeps, so finished searches would no longer
    replay.
  - *Measured, sizing*: `len(seen)` of every trial_error unit, counted by a
    plugin wrapping `_score`/`_search_system`. The acceptance suite: 61
    finished units, largest **38 076** (three-phase mixture, tetragonal).
    The bethanechol benchmark as it runs (both modes, 30 s a unit): 80 units,
    45 finished, largest finished 65 588 (orthorhombic). One unfinished
    triclinic unit there held 43 944 candidates in `found`. Bethanechol in manual mode, trial_error alone,
    CPU budget 3 600 s: Ab finished at **254 344** in 1 216 CPU s, and Aa
    at 127 310 in 410 CPU s. The other eight manual sets were still
    running at handover on the same workstation. The cap sits about 16× above
    the largest finished unit measured.
  - *Measured, equivalence* (macOS arm64, `tests.unit_replay`, units
    captured on this tree): every trial_error unit replays to main's digest
    with the cap in place. Brucite hexagonal and trigonal `f14bfc55`.
    Corundum cubic `e3b0c442`, hexagonal `6f277e25`, trigonal `397c20a8`,
    tetragonal `77c695ae`. Synthetic monoclinic (`synthmono_ip`)
    `0b4a059e`. **Corundum tetragonal moved on main** since WP-1924's
    `e8addc35`, before this branch; the branch did not move it.
  - *Gates* (Linux x86-64 workstation, a `[dev]` venv, tree `a62aeb87b`):
    `test_indexing_engines.py` 101 passed;
    `test_acceptance_indexing.py -m ""` 45 passed (also 45 on main);
    the fast suite (`-m "not slow" -n 8`) 14 853 passed, 280 skipped, 32 xfailed and 1 failed, 10:39 beside other runners' jobs. The four cases added (one test, one parametrised three ways) are the whole intended delta; main was not re-measured. Their cost on that run: 7.10 s for the prefix test and 0.17 s for the three guards, so neither joins the slow tail. `test_audit_table.py`: 22 passed and 1 failed,
    `test_an_audited_row_carries_its_evidence` on `MAX_SEEN`'s missing
    `approved`, the documented waiting state. `tests.audit_delta`: 1 added,
    0 new at `unaudited`. `tests.reader_output`: exit 0, unchanged. ruff
    clean. The acceptance repro on the final tree: `repro_1376 4000 --cpu-clock` (same workstation) stopped at the cap after 3 412 CPU s. It held 4 000 000 entries and `found` 200, peaked at **1.70 GB**, `search_complete` was False with `INDEX_SEARCH_INCOMPLETE` and no `INDEX_BUDGET_EXHAUSTED` (so filed as a cap, not a clock), and candidate 0 was the published cell. Main's run on the same arithmetic reached 2.31 GB at 4 000 CPU s and was still growing.
  - *Review*: a read-only review agent found no blockers. Two low fixes
    were applied (the prefix test asserts the in-loop dedup never ran;
    `--max-gb` refuses without a memory reading). Declined: a unit that
    reaches the cap within one score of its clock is filed as out of time.
    That is the same race the index-table cap already has, and it is less
    than one solution wide.
  - *Gotchas.* In bethanechol's manual mode `found` grows too: on set F,
    4 980 distinct candidates after dedup at 600 CPU s, with the in-loop
    dedup running every base on up to 17 000 raw ones, and the unit clock
    reaching 617 s on a 600 s budget. That is its dedup step, not a
    `_score`. Memory stayed at 0.66 GB, so `MAX_SEEN` bounds it only by
    count. The `INDEX_SEARCH_INCOMPLETE` message is shared with the
    index-table cap; `seen == MAX_SEEN` in `stats` tells them apart.
  - Next: (1) the maintainer approves `MAX_SEEN` or names another value,
    dating its `_audit` row, which turns `test_audit_table` green. (2) The
    eight manual-mode bethanechol units still running: if one finishes above
    about 1 M, the margin narrows and the value should be revisited. (3) Open
    question for the maintainer: whether `found`'s growth in manual mode
    (with the dedup-every-base overrun) wants its own bound, as dichotomy's
    `MAX_HARVEST`, or belongs to #1374's time work. (4) Generality judge's
    verdict on the row: see *Generality* below.
  - *Generality* (the generality judge, Opus, its sections unedited):

    #### rietx.indexing.trial_error.MAX_SEEN

    **weak**: the case for stopping is stronger, since a run killed for memory returns nothing. The number itself rests on one case where it fires and two dataset families where it stays silent, and nine of the ten bethanechol manual sets have not finished.

    | Q | Author's answer (where) | Found | Verdict |
    |---|---|---|---|
    | 1 Decides | stop a unit at 4 M distinct solutions and keep `found` (trial_error.py comment) | The caller has no way to raise the cap: it is not a `SearchSpec` field. The cap can bind only under a raised `budget_seconds`: at #1376's rate (about 1 250 entries per CPU s) it is reached after about 3 200 CPU s. Under the default 30 s slice it cannot fire there. | holds |
    | 2 Kind | none given (no `ambiguity` field; none is required on a constant) | Kind 1: Rule 1's protection, "keep the best attempt", instead of an OS kill | holds |
    | 3 Against | none given | A refiner on a 32 GB+ machine who raises `budget_seconds` to finish #1376 exhaustively: about 12 M entries at finish, about 5 GB of keys, which fits there. Once capped, the message says more time changes nothing and offers only narrowing. Whether the true cell is in `found` before 4 M: **none given** (the old 9.2 GB run reached it at rank 1 after about 16 min). GSAS-II, FullProf, TOPAS defaults: not checked here. TREOR/N-TREOR are not among the seven programs. | weak |
    | 4 For | "reported incomplete instead" (grounds); repro: 1.14 GB at 2.24 M entries, 2.31 GB at 5.03 M. Scratch run without `seen`: flat at 0.25–0.30 GB | An OOM kill loses every candidate already built. The footprint tracking `len(seen)` is measured, and dropping `seen` confirms it is the structure that grows. | holds |
    | 5 Tier | 3, "rietx's own choice, a memory bound on a laptop" (grounds) | Correct, and the same shape as the approved `MAX_HARVEST` and `MAX_GRID_BYTES`. `approved` is None, as it should be. The 0.43 KB per entry is a Linux x86-64 figure on one case; the macOS footprint was not measured. `found` is a second route that grows (set F: 4 980 distinct at 600 CPU s), and this cap bounds it by count, not by bytes. | weak |
    | 6 Families | acceptance suite max 38 076; bethanechol set Ab 254 344; 16× margin (grounds) | Silent on two families: IUCr round-robin plus synthetic, and bethanechol (probably development data). The firing case, #1376, is synthetic from a COD cell. The reference is the unit's own replay digest (cell + n_indexed), which only verifies. Bethanechol manual mode is unfinished, so "largest finished unit" is provisional. | weak |
    | 7 Field | `INDEX_SEARCH_INCOMPLETE` "outgrew a size cap", `search_complete=False`, `stats["<system>.seen"]` | Present and tested (`test_a_trial_error_unit_stops_at_its_seen_cap`, `…never_holds_more_than_max_seen`). The message is shared with the index-table cap (`allowed < len(rows_all)`), so the reader can only tell which cap fired from `seen == MAX_SEEN`. | holds |

    Would change the verdict: the nine bethanechol manual sets' finished `seen` counts; a third unrelated family; whether #1376's true cell is held at 4 M; the per-entry cost on macOS arm64.

    Author: the true cell is held before 4 M. It was candidate 0 at 2.24 M entries (1 800 CPU s) and in the scratch run at 600 CPU s, and it is candidate 0 of the capped run on the final tree (1.70 GB at 4 M). The other three remain open, and are why the value is put to the maintainer.

    #### Names on UNAUDITED_BASELINE / OTHER_RECORD_FIELDS / NOT_WALKED / WALKED / DEFAULT_SEATS

    **holds**: the diff touches none of them, and `tests.audit_delta` reports 1 added, 0 at `unaudited`.

    #### `<system>.seen` in EngineResult.stats

    **holds**: it is a count that reports, not a heuristic, and it is the visible statistic behind item 1. (7 Field, weak on wording: the early return for a pool smaller than n_dof records no `seen` key, as it records no `seconds` key; the claim is narrowed to units that search.)

- **2026-11-05** — created from issue #1376 (planning only, no code). No
  open WP owns it: WP-1924 bounded dichotomy, filed #1376 as a follow-up it
  does not own, and closes in PR #1373. Its last task, the time share, is
  #1374, which bounds time, not memory. The growth candidates in § Context
  come from reading `trial_error.py` at `541f0daf7`; nothing was run. The
  first action is the repro and the profile.
