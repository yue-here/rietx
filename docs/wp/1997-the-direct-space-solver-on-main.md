# WP-1997 — the direct-space solver on main: site classes, kernels, chemistry, engine and entry point

Milestone: structure-solution · Status: 🔄 2026-10-24 — the site classes (PR #1013), the solve kernels' crate source (PR #1015) and the chemistry terms (PR #1016) landed from outside; the `kernels-v1.4.0` tag, the engine and the entry point remain
Depends on: 1902 (shipped, the cost); 1901 soft (the map, needed only by completion); 1940 (shipped, the kernel crate)
Priority: P2 2026-10-17 — a feature the open milestone was opened for, and three outside PRs (#1013, #1015, #1016) wait on this number

## Goal

`solve_seed` takes a verified cell, a space group and a composition, and returns
a ranked list of structure candidates with their evidence. It has no
`.structure`, and its one gated singleton is `best_or_none()`. It runs on the
cost WP-1902 built, over the Wyckoff classes of the group, with the chemistry
terms reported beside χ², and its inner loops are in `rietx-kernels`.

## Context

**Where this comes from.** Issue #562 (@mustachefeeling) scoped the work and
WP-1515 recorded the scoping. WP-1515 builds nothing, and its non-goal says
nothing from the contributor's spike merges as it stands. The spike predates
WP-1940 and is about 2 100 commits behind `main`. So each chunk below is
rebuilt on `main`, one PR each, branched off `main` and none stacked.

**The cut.** The contributor proposed it on #562 on 2026-10-16, and the
maintainer cut this WP for it on 2026-10-17.
1. The site classes (#1013), a prerequisite the 2026-09-30 review placed before
   the engine.
2. The solver's compiled kernels (#1015), WP-1515's S4 restated as the solver's
   own throughput kernel.
3. The chemistry terms (#1016), WP-1515's S3.
4. The engine, WP-1515's S2a.
5. The entry point, WP-1515's S2b.

The first three are open as PRs, each saying "WP number pending". The last two
are not yet opened.

**What is on `main`.** `solve/cost.py` (WP-1902): the profile χ² as a quadratic
form in the intensity vector, χ²(I) = c − 2rᵀI + IᵀMI with M = ΩᵀWΩ, floored by
its own least-squares solve, and refusing by name a magnetic phase, a
Rietveld-mode model, a satellite and a poor extraction. The engine calls it. It
never calls `predict()` in its loop.

**The design that is decided** (#562, 2026-09-30, and WP-1515's Inherited
entries at the time):
- The answer is a list. `high` needs agreement across independent seeds, and
  every grade ships provisional under a versioned thresholds contract, like
  `indexing_thresholds_version`. The prototype's blind-contrast threshold is
  proposed, not validated, and the Kabova et al. (2025) bars are "worthy of
  close inspection" and not pass bars.
- Special positions and Wyckoff-class enumeration are in from the start
  (amendment (b)). The enumeration reuses `symmetry.site_orbit` and
  `wyckoff.site_constraints`, so there is one orbit authority.
- A prior-off control arm of at least two seeds runs every time. If its leader
  is structurally different and at least 10 % better in χ², the prior-on leader
  is capped at `low` (amendment (c), `prior_excludes_better_fit`).
- The ladder is planned and has no burn-in. Its top temperature is the
  χ²/χ²_floor spread of random structures, and its replica count comes from
  Earl & Deem (2005), eq. 3, at C_v = n_par/2. The contributor's paired
  measurement on a synthetic P2₁/c set at 600 k evaluations per seed gave
  ≥ 17/20 seeds at 18 and 24 DOF and ≥ 15/20 at 30. The regression arm is the
  fixed ladder, reproducing the earlier numbers bit for bit. Swap acceptance is
  recorded per pair and not gated. Nothing is promised above about 30 DOF.
  These numbers are from a private prototype and are targets until the engine
  PR measures them on a public set.
- A term is reported beside χ² and never folded into it. The numpy path stays
  as the fallback and the oracle for every kernel (WP-1115's rules).

**Seams that cross chunks.**
- `model/compiled.py` gets the three entry points in #1015, with the names in a
  new `SOLVE_NAMES` beside `KERNEL_NAMES`, since nothing in `src/` calls them.
  The engine's first caller moves them into `KERNEL_NAMES` and raises
  `KERNEL_FLOOR` to 1.4 in the same change. It also carries the release note
  that rietx needs rietx-kernels 1.4.
- The kernel's contact term loops over the 27 cells around the minimum image,
  which holds every contact only while r₀ is under 1.5 plane spacings. #1015
  refuses past that bound by name, with the wording of `site_clash` in #1016.
  The engine dispatches between them and treats both refusals alike.
- A new kernel bumps the crate's minor. The `kernels-v1.4.0` tag follows
  `docs/RELEASING.md` § The kernel wheel, and the maintainer pushes it.
- The answer type moves `SCHEMA_VERSION`, which WP-1343 and PR #522 also
  contest. The entry point waits for the maintainer's call on timing. A solve
  `Capabilities` field is a registry arm, not a `features` boolean.
- #1016 carries #675's radii tables (Shannon, Pyykkö and Pauling) and its
  `ATTRIBUTION.md` rows. #675 closes as merged into #1016.

### Inherited

- **2026-10-16, from WP-1515 (the #998 triage): `solve_seed` checkpoint, resume
  and progress.** Single seeds on the reporter's blind kit (36 atoms, 4 species,
  lab X-ray) ran past 1 h and then 8 h timeouts, and each kill lost the whole
  deterministic trajectory. The entry point is asked for an atomic checkpoint at
  `_race`'s natural boundaries (RNG state, stage and round, `alive`,
  `rec`/`best_u`, ladders, `evals`/`swaps`, finished records). Resume is refused
  on a cost, spec or version mismatch. Best-so-far candidates carry
  `partial=True`, and a progress callback reports a real fraction done. The
  acceptance is that an interrupted-then-resumed run is byte-identical to an
  uninterrupted one. The reuse seams are `CancelToken` and `runs.py`, never a
  new channel. The reporter will PR it against whichever chunk lands the
  engine.
- **2026-10-05, from WP-1515 (#677): space-group competition is a later WP.**
  `high` is for now "high, given this group". The #677 design (candidates from
  the unrefuted extinction classes, group leaders compared by ΔBIC on χ²_CI at
  N_clump, `space_group_confidence`, an extraction retry, a four-outcome
  acceptance table) is not part of this WP. The radii half of #677 lands in
  #1016.

## Non-goals

- Charge flipping (WP-1515's S6a and S6b) waits for a public case that defeats
  direct space.
- The difference-Fourier map is WP-1901, and completion by difference Fourier
  (S5) needs it. The contributor asked on #562 whether direct space may land
  before 1901, and that order is the maintainer's to rule on. The engine does
  not need the map until S5.
- A general compiled |F|² kernel. `structure_factor.py` is untouched.
- Rigid-body fragment moves (the rigid-bodies milestone's R0 and R1). Free-atom
  moves come first.
- Space-group competition, preferred orientation and Z′ (S9, #677), mixed
  occupancy in the enumeration, and reducing assignments by the affine
  normaliser.
- The GUI run kind and candidates panel (S7b), and the acceptance corpus and
  scoreboard (S8). Each gets its own WP when its chunk is cut.
- Nothing from the contributor's spike merges as it stands.

## Tasks

Each item is one PR off `main`. Check off as they land.

- [x] Site classes (#1013): `crystallography/site_classes.py`, `site_classes()`,
      `site_assignments()`, an exact count and a named refusal past
      `MAX_SITE_ASSIGNMENTS`, checked across all 564 gemmi settings
- [ ] Solve kernels (#1015): `kernels/src/solve.rs`, rietx-kernels 1.4.0, three
      entry points in `model/compiled.py`, `tests/test_solve_kernels.py`; after
      merge, the `kernels-v1.4.0` tag
- [x] Chemistry terms (#1016): `solve/chemistry.py`, `Composition`, the
      minimum-image contact term, the coordination prior and `CandidateCost`;
      #675's radii tables; #675 closes as merged
- [ ] Engine: sites from the site classes, moves, and the planned parallel
      tempering on WP-1902's cost, calling the kernels with the numpy functions
      as fallback and oracle; the prior-off control arm (amendment (c));
      candidates clustered across seeds, symmetry-equivalent and enantiomer
      solutions as one; `SOLVE_NAMES` into `KERNEL_NAMES`, `KERNEL_FLOOR` to
      1.4, the release note; `ATTRIBUTION.md` rows for DASH (MIT), FOX (GPL-2),
      GALLOP (GPL-3), Superflip, the TOPAS reference § 10.23, Kabova and Earl &
      Deem
- [ ] Entry point: `solve_seed`, the answer type with no `.structure`, the
      provisional grades and their versioned thresholds contract, the events,
      and the #998 checkpoint, resume and progress
- [ ] Tests (unit; the acceptance rows above) + the ladder's measurement on a
      public synthetic set
- [ ] Skill: none until the entry point is public, then its routing row (root
      CLAUDE.md § skill)

## Acceptance

The commands the three open PRs state, on the PRs' own platforms:

```sh
.venv/bin/python -m pytest tests/test_site_classes.py tests/test_docs_consistency.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_site_classes.py::test_every_setting_matches_spglib -m slow -n 0
.venv/bin/python -m pytest tests/test_solve_kernels.py -q
.venv/bin/python -m pytest tests/test_solve_chemistry.py tests/test_solve_cost.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The engine and entry-point PRs add their own rows here when they are opened.
Their bars are WP-1515's: simulated structures recovered within 0.10 Å by at
least two of four seeds, symmetry-equivalent solutions clustered as one, no
`.structure` on the result, `best_or_none()` is `None` for one finder, and a
cancelled run returns what it has.

## References

- Issue #562, and its 2026-10-16 comment with the cut. Issues #677 and #998.
- WP-1515 (the scoping), WP-1902 (the cost), WP-1901 (the map), WP-1940 (the
  kernel crate).
- PRs #1013, #1015, #1016, and #675 (the radii tables, folded into #1016).
- David (2004), *J. Appl. Cryst.* 37, 621: the Rietveld and correlated-intensity
  costs (abstract read only).
- Earl & Deem (2005), *Phys. Chem. Chem. Phys.* 7, 3910, § 2.3: replica ladders.
- Favre-Nicolin & Černý (2004), *Z. Kristallogr.* 219, 847 (FOX is GPL-2:
  concepts only).
- Spillman & Shankland (2021), *CrystEngComm* 23, 6481 (GALLOP is GPL-3:
  concepts only).
- Kabova et al. (2025), *Acta Cryst.* C81, 559: proposed bars, to be checked
  against the paper's text before they become constants.

## Handover log

- **2026-10-31** (`/pr-review`) — S2a, the engine's moves, tempering and clustering, merged from outside as PR #1153 (`6a92826e`) after two rounds, split under #1224 ("a machinery PR adds no tier-3 row") at head `1519537e5`. `solve/moves.py` holds `FreeSite` on a Wyckoff class from `site_classes`, `FragmentUnit` placed by the map `crystallography.bodies` uses, a site exchange between two same-class sites of different species, and |F|² held to `CompiledModel._total_f2` at ≤ 1e-13 relative for X-ray, X-ray with dispersion and neutron. `solve/tempering.py` holds the planned geometric ladder, swaps counted per neighbour pair, and `polish`. `solve/cluster.py` holds `equivalences` (the Euclidean normaliser derived from the group's own operations, matching International Tables A Part 15 indices), `align`, `cluster` and `rank`. Nothing is exported from `rietx`. Bar 1 (a rigid 14-atom acridine-shaped fragment in P2₁/n) recovers 4 of 4 seeds within 0.10 Å (0.005 Å), and bar 2 (NAC from its own Pawley intensities) 4 of 4 (0.017 Å), on the compiled and numpy paths alike. Both bars also ask at least 2 seeds within 0.10 Å before the polish, since an accept-every-move walk followed by the polish recovered the rigid fragment 11 to 14 times in 16. The site exchange was not in the cut. NAC reached 11 of 16 seeds at 20 000 sweeps without it and 16 of 16 at an exchange probability of 0.1. The split removed nine tier-3 rows. The engine now chooses no search setting, so `span`, `step`, `exchange`, `swap_every`, `n`, `tol` and `maxiter` are required arguments (a missing one is a `TypeError`, an impossible one a `ValueError`), and the provisional grade with its four thresholds is gone. They return with S2b, each as a tier-3 row for its own ruling. `SWAP_EVERY`, `N_RANDOM`, the clustering RMSD and the three grade thresholds were never varied, so S2b owes a measurement for each. The PR adds three tier-1 rows (`_ISOMETRY_RTOL`, `_TAU`, `REFRESH_EVERY`), and `tests.audit_delta` reports 0 new at `unaudited`. `rank` returns the evidence with no grade and no `.structure`. Given `control=`, each entry carries `control_rmsd_ang` and `control_chi2_data`, the numbers amendment (c)'s rule reads. The review kept bars 1 and 2 as asserting tests and this PR's acceptance. They are `slow`, and each docstring now gives the measured rate (16 of 16) beside the bar (at least 2 of 4). Round 1 items, all fixed: `Solution.control` had no writer and was dropped; the f2 test and bar 2 declare their dispersion and run over the compiled and numpy paths; counts handed to numpy are `intp` for wasm32; three citations were added; `polish(maxiter=)` is required; `Ladder.planned` refuses a non-positive `step` by name. The compiled parametrisations of the f2 test and bar 2 have not run since `bb0c25e46`, because the published rietx-kernels is 1.3.0 and both benches skip them. Bar 1 on the compiled path passed under a local 1.4.0 build before round 2. Left open in the Engine task: orchestration (running seeds and control seeds, racing assignments, merging seed results) is S2b's; `SOLVE_NAMES` into `KERNEL_NAMES`, `KERNEL_FLOOR` to 1.4 and the release note (the PR carries none); the `ATTRIBUTION.md` rows (none is in the PR); the coordination prior is reported per candidate and not steered in the move loop. The `kernels-v1.4.0` tag is still the maintainer's. #998's checkpoint half waits on S2b. No task is ticked. Gate (the six PRs of this round merged together onto main `766c3505d`; macOS arm64, `[dev,jax]`, Python 3.12): fast 12 884 passed, 223 skipped, 32 xfailed; slow 435 passed, 18 skipped, 16 xfailed, with one GUI-boot socket timeout under load that passed alone in 5 s; ruff and the `-W` manual build clean.

- **2026-10-24** — PR #1016 merged (`d71b8127`, review round 5), by `/pr-review`;
  #675 closed as folded into it (its files are on main byte for byte).
  *Done*: the chemistry terms. `solve/chemistry.py` (`Composition`, the
  minimum-image contact term, the coordination prior, `CandidateCost`) and #675's
  radii tables (`crystallography/radii.py`, three `.dat` files, attributed). The
  composition gate reads a part occupancy as written, or as the nearest p/q with
  q ≤ 12 inside its printed rounding (`occupancy_fraction`), so 0.33 is ⅓ and
  0.5 is ½ and nothing else. That rule was the round-4 review's suggestion.
  *Ruled* (2026-10-24): `OCCUPANCY_MAX_DENOMINATOR` stays at tier 3, approved on
  the judgement ground while only tests call `require`. The mechanical ground
  (three published part-occupied structures from unrelated laboratories and
  materials, each accepted at its composition and refused when mis-stated) is
  owed before a default path calls `require`. The maintainer's commit
  `25772efd` on the branch wrote the ruling into the row.
  *Gotchas*: the S2 engine writes occupancy 1.0 on every site it places, so only
  a caller's model meets the fraction reading; nothing in S2a or S2b calls
  `Composition.check` or `require` yet.
  *Measured*: the whole suite on a stack including it, and the fast selection on
  the final stack `bb654fd0` (11 655 passed, macOS arm64).
  Next: the `kernels-v1.4.0` tag, then the engine.

- **2026-10-17** — created at the maintainer's request for the #562 chain; #1013, #1015 and #1016 are open against it, reviews in progress. Next: review each PR against this file.
- **2026-10-23** — PR #1013 (head `019a0adc`) merged as `a1a1aa7d` and PR #1015 (head `0542346c`) as `bcdf80e0`, by `/pr-review`, in one gate with #1102.
  *Done.* The site-classes task is checked. `site_classes()` and `site_assignments()` are on main, refusing past `MAX_SITE_ASSIGNMENTS` with the exact count. The solve kernels' source is in the crate as rietx-kernels 1.4.0, with its three entry points in `model/compiled.py`.
  *Not done.* The solve-kernels task stays open until the `kernels-v1.4.0` tag is pushed and the wheel published. That is the maintainer's release step (`docs/RELEASING.md` § The kernel wheel), and this review did not take it. Until then every `@needs_solve` test skips against the published 1.3 wheel. Nothing in rietx calls the kernels yet.
  *What the review established.* For #1013: an operator list whose special positions leave the 1/24 grid is refused (`SITE_CLASSES_GRID`) by two checks. (a) `_has_fixed_point` decides exactly, by integer row reduction of R − I, whether an operation fixes any point, and refuses one whose fixed points miss the grid. That covers an inversion at x = t/2 and a 3-fold at (2t/3, t/3). (b) A 1/48 scan looks for a point several operations share. Check (b) has no test of its own, because every current case trips (a) first. `MAX_SITE_ASSIGNMENTS` is tier 3, approved 2026-10-21, with grounds rewritten to what the evidence supports. For #1015: `check_cells` refuses a `g` that is not symmetric or not positive definite. The names sit in `SOLVE_NAMES` beside `KERNEL_NAMES`, and `KERNEL_FLOOR` stays 1.3. A 1.3 wheel still loads, and the three wrappers decline. The engine PR moves the names into `KERNEL_NAMES`, raises the floor, and carries round 1's notes: the N = 0 early return before the argument checks, `sig3` above 1000, references on the wrappers, a test that `SOLVE_NAMES` empties, and the numba spike's provenance line.
  *Held.* #1016 (chemistry) waits on the maintainer's ruling on its composition tolerance. Its tolerance reads an occupancy's precision from its shortest decimal form, so a one-decimal value forgives 0.05 per atom. On a 192-fold site, 0.3 then passes 6.4 atoms short of Z = 64, while 0.32 is refused, and a plain 0.5 lets Z = 88 and Z = 104 both match 96 atoms. A float cannot say whether its file printed 0.5 or 0.500.
  *Gate.* Main `3e0dc6f7` with #1102, #1015 and #1013 stacked (`35b9eff5`), macOS arm64, `[dev,jax]` with the published rietx-kernels 1.3.0, nothing else running. Fast suite: 11 322 passed, 195 skipped, 27 xfailed and 2 failed. Whole `-m slow`: 404 passed, 12 skipped, 14 xfailed and 4 failed. All six failures fail identically on main alone. CI's Kernels workflow built and tested the 1.4.0 wheel on #1015's head on five platforms. After the last merge, `git diff 35b9eff5 origin/main` was empty.
