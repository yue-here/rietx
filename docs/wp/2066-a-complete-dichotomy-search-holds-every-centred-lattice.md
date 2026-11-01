# WP-2066 — a complete dichotomy search holds every centred lattice and polishes its truth leaf

Milestone: unscheduled · Status: 🔄 2026-11-01 — options for A measured; waits on the maintainer's decision (first task)
Track: What fires, and what stays silent
Depends on: — (1924 soft: the same engine, the same #780 units)
Priority: P2 2026-10-31 — a defect that fires wrongly: `search_complete=True` while the true cell is absent, on 22-32 % of C-centred monoclinic lattices by the reporter's draw; end to end the gate abstains rather than promoting the supercell (all `low`, `INDEX_ABSTAINED`), so a clean pattern returns no cell rather than a wrong one

## Goal

When `search_dichotomy` reports a system complete, its harvest holds the true
lattice in its own centring at its primitive volume, for C-centred monoclinic
and orthorhombic lattices whose every C setting falls in the swap-pruned half
of the domain, and for dense lists where the leaf holding the truth is many σ
coarse above the driven range. A completed silence stays evidence
(`indexing/CLAUDE.md`, engines section).

## Context

**Source.** Issue #1258 (mustachefeeling, 2026-10-31), follows #780.
Measured on `main` at `d35ffeda7` and again at `8b9c0a3ae`; every row of the
issue's tables reproduces at `d87c8cc91` (triage, macOS arm64, compiled tier
on, `scratchpad/lane-A/r1258.py`).

**A. The axis-swap prune drops every C setting of some C lattices.**
`_test_box` refuses a box lying wholly in A < C (monoclinic) or A < B, A < C,
B < C (orthorhombic), because an axis permutation is a setting change and some
other box holds the equivalent description (`axis_swaps`, `_test_box`, and
its transcription in `kernels/src/dichotomy.rs`). That holds for the metric.
It does not hold for the centring: a↔c maps C to A, and the orthorhombic
permutations map C to A or B. The leaf's centred replay tests only
`CENTRINGS[system]` ((P, C) monoclinic, (P, C, I, F) orthorhombic) in the
leaf's own setting. So when every C setting of the lattice lies in the pruned
half, or past the 30° obliquity bound, the engine reports the metric as P at
twice the primitive volume.

| list (exact positions, Cu Kα1) | complete | returned (triage run at d87c8cc91) |
|---|---|---|
| C m m m 4.2 / 12.9 / 5.9 Å, 37 lines | True, 1.1 s | I (4.2, 11.8, 12.9) and P (4.2, 5.9, 12.9), both primitive V 319.66, 37/37; none at the true 159.83 |
| control C m m m 4.2 / 5.9 / 12.9 Å | True, 4.5 s | C (4.2, 5.9, 12.9) first, primitive V 159.83 |
| C 1 2/c 1 12.3 / 6.1 / 9.5 Å, β 115° (a > c), 28 lines | True, 62 s | two P cells at V ≈ 646 (2 × 323.0) |
| control C 1 2/c 1 10.2 / 3.9 / 7.4 Å, β 104° | True, 164 s | C (10.2, 3.9, 11.058, β 139.51) first, primitive V 142.81 |

The reporter's draw: 906 of 4000 C-monoclinic cells (a, c in [5, 15] Å,
β in [90, 125]°) have no C setting in the kept half-domain, 22.7 %; 1281 of
4000 with [4, 20] Å and [90, 135]°, 32.0 %. An orthorhombic C lattice is hit
whenever its centred face is not that of its two shortest axes. End to end,
`index_pattern(preset="quick")` on the orthorhombic list returns 12
candidates, none at the true primitive volume. Triage re-run at `d87c8cc91`
(`scratchpad/lane-A/r1258q.py`): `best_or_none()` is `None`, every candidate
`low`, `INDEX_ABSTAINED`; the P (4.2, 5.9, 12.9) index-2 supercell ranks 3rd
and is found by all three engines, so svd and trial_error do not rescue the C
lattice either; orthorhombic was cut by the ceiling (`search_complete` False
under `quick`).

Fix options from the issue (not built in the tree):
1. At a leaf, also replay the centring images under the admitted
   permutations (monoclinic A and I, orthorhombic A and B), and report an
   accepted A/B leaf in its conventional C setting through
   `engines.conventional_fit`. The replay already runs only on survivors
   (WP-1509), so the cost is one replay per extra letter per leaf.
2. Apply the swap prune only where the system's admitted centrings are
   closed under the swaps. This changes `_test_box`, so the compiled kernel
   changes in the same commit (the box test is held to the numpy loop on the
   bit, leaf by leaf, WP-1959).

The reporter's prototype of option 1 (arm A, wrappers outside rietx, issue
comment of 2026-10-31): truth accepted on 4 of the issue's 5 lists (main 2),
20 of 22 #780 units holding a truth cell (main 17), loses the truth nowhere,
+2-11 % wall. Costs found: one lattice returned in up to three settings (I, C,
A relabelled C) that `rank_candidates` keeps as separate candidates; a
permutation-only relabelling can give an obtuse β (a build wants the reduced
C setting); on one orthorhombic-F lab list 15 wrong A/B cells rank above the
truth.

**B. A leaf holding the true metric is polished onto a nearby wrong cell.**
The stopping rule (`dichotomy.py` near `tol_accept`, `width <= tol_accept`)
measures the box on the driven lines only, but `_accept` assigns every usable
line. On dense lists a box fine enough for the low-Q driven range is many σ
coarse at high Q, the first annealed pass assigns wrong hkl above the driven
range, and the refinement walks off the truth. Repro: P 1 21/c 1, 13.8 / 19.1
/ 16.0 Å, β 97.5°, 2θ ≤ 40°, 381 exact lines, domain d ∈ [13, 19.5] Å,
V ∈ [4000, 4400] Å³: complete in 0.7 s, two candidates indexing 288 and 273
of 381, the true cell (381/381) not returned (reproduced at d87c8cc91). In a
#780 unit where phase 2 did return the truth, 7 of the 9 leaves holding a
setting of it failed this way. The docstring's promise at the stopping rule,
a leaf "whose centre the assign-refine loop can polish onto the true cell",
is what fails.

The reporter's variant V3 (measurement, not a PR): the annealed passes
assign only lines with Q ≤ highest driven Q + k·σ_max; the two closing passes
at σ assign every line, and every test after the loop is unchanged. It
returns the B repro's truth first at 381/381, accepts all 9 leaves of the
other unit, loses the truth nowhere, and costs +37 % accepted leaves and +7 %
phase-2 time on the #780 units (+12 % wall on the synthetic lists). Its extra
candidates on the orthorhombic C control (42 against 25) are mostly partial
cells sharing no lattice with the truth, ranked 9-42. A + V3 together:
5 of 5 synthetic lists, 22 of 22 #780 truth units, truth first in 21.

**Not a defect.** The impurity variant of the C case leaves 3 of 20 driven
lines unindexed against a miss budget of 2 and is refused even at the true
metric; the inlier retry (`INDEX_INLIER_RETRY`) is its route.

**Interaction with WP-1924.** `MAX_GRID_BYTES` (#1244) now stops 5 of 11
monoclinic #780 grids before they reach a truth leaf, so B shows in fewer
units because the leaf is cut off earlier, not because it is fixed.

**Rules that bind.**
- "Removing a redundant search must not remove its prunes" and "run
  `tests/test_acceptance_indexing.py` before closing anything that touches an
  engine" (`indexing/CLAUDE.md`).
- Finished units replay to their digests (`python -m tests.unit_replay`), or
  each move is named.
- A candidate is reported in its conventional setting at
  `to_cell_candidate` (WP-1923); an A/B leaf goes through
  `conventional_fit`, never a permutation of its own.
- Tier: option 1 and V3 add no constant if k is the existing window's; a
  new k is tier 3 with its measured window.

**Licensing.** Dichotomy follows Boultif & Louër (DICVOL), concepts from the
papers only.

## Non-goals

- The ceiling and memory of a dichotomy unit (WP-1924).
- The leaf cost of `refine_candidate` (WP-1520).
- Triclinic units: no centring to replay; V3 accepted no triclinic truth on
  the #780 set either, so a triclinic miss is a separate question.

## Tasks

- [ ] **Decision (maintainer):** A's option 1 or 2, and whether V3 is wanted,
      recorded as `Decided YYYY-MM-DD:` and answered on #1258.
- [ ] A: the chosen fix, with the duplicate settings merged before ranking
      (one lattice, one candidate) and the C setting reduced; the compiled
      kernel transcribed in the same commit if `_test_box` changes.
- [ ] B: the annealed passes bounded as decided, the closing passes unchanged.
- [ ] Tests: the issue's orthorhombic and monoclinic C lists and the B repro
      as fixtures (exact positions, `search_complete` asserted beside the
      truth's presence at its primitive volume); unit replay digests and
      `tests/test_acceptance_indexing.py` unchanged or each move named.
- [ ] Re-measure the orthorhombic-F lab list the reporter saw move (truth
      5 → 7/8), and say whether the A/B cells above it are refuted.
- [ ] Skill: none expected (engine internals; no code or verb changes).

## Acceptance

The issue's five lists return the true lattice at its primitive volume
with `search_complete=True`; acceptance rows keep their rankings.

```sh
.venv/bin/python -m tests.unit_replay
.venv/bin/python -m pytest tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Boultif, A. & Louër, D. (2004). *J. Appl. Cryst.* **37**, 724-731 (DICVOL04).
- Issue #1258 and its 2026-10-31 measurement comment; issue #780.
- WP-1509 (survivor-only leaf replay), WP-1923 (`conventional_fit`),
  WP-1924, WP-1959 (the compiled box test).

## Handover log

### 2026-11-01 — both fixes for A measured; the choice waits on the maintainer

The tree still loses the issue's C-centred lattices. All five rows
reproduce on `main` at `f4db77639`. This session measured the fix the
reporter had not built. Dropping the axis-swap prune (option 2) finds both
missing C lattices, but searches about twice the boxes in monoclinic and four
times in orthorhombic. Replaying the swapped centring letters at each leaf
(option 1) finds the same two lattices with the box count unchanged, and an
argument below shows the two options reach exactly the same lattices. Neither
touches B; only the reporter's V3 variant does. No code landed, because the
WP's first task is the maintainer's decision. The brief is at the end of
this entry. PR #1294 carries the entry.

**Measured** (macOS arm64, this worktree's `[dev]` venv, compiled tier on,
`main` at `f4db77639`). The machine ran concurrent shifts at load 50-77 on
10 cores, so wall seconds are noise here and box counts are the cost. The
script is the issue's reproduction with one monkeypatch per arm, kept outside
the tree (`~/.cache/ghostshift/rietx/wp-2066/arms.py`): option 2 makes
`axis_swaps` return nothing, and option 1 adds A, I to monoclinic and A, B to
orthorhombic in `engines.CENTRINGS`, with no relabelling. "Truth rank" is the
rank of the first candidate at the true primitive volume (within 1 %) that
indexes at least 95 % of the lines. "Leaves" is the harvest of accepted
leaves before dedup.

| list | main: truth rank, boxes, leaves | option 2 | option 1 |
|---|---|---|---|
| C m m m 4.2 / 12.9 / 5.9 | absent, 43 599, 39 | 1, 177 285 (×4.07), 236 | 1, 43 599, 56 |
| control C m m m 4.2 / 5.9 / 12.9 | 1, 49 007, 64 | 1, 211 480 (×4.32), 286 | 1, 49 007, 64 |
| C 1 2/c 1, a > c | absent, 5 428 291, 646 | 1, 10 664 947 (×1.96), 1 600 | 1, 5 428 291, 1 118 |
| control C 1 2/c 1 | 1, 14 328 646, 1 315 | 1, 28 328 799 (×1.98), 2 406 | 1, 14 328 646, 1 586 |
| B repro, 381 lines | absent, 50 666, 2 | absent, 86 288, 4 | absent, 50 666, 2 |

Every run reported `search_complete=True`.

- Option 1 returns the letters it replayed, so one lattice comes back up to
  three times. On the monoclinic control, ranks 1-3 are I, C and A
  descriptions of the truth. This reproduces the reporter's duplicate
  finding.
- Option 2 returns C, but not in the conventional setting. Orthorhombic comes
  back in a non-standard axis order, C (12.9, 4.2, 5.9). The monoclinic truth
  comes back at β 141.07° on a 17.74 Å axis. So both options need a
  relabelling step. `reduce.conventional_setting` today re-sets monoclinic P
  and C only, and orthorhombic not at all.

**Why the two options reach the same lattices** (a derivation, not a
measurement). A setting change the prune quotients by also relabels the
centring. In orthorhombic, P, I and F map to themselves and A, B and C map
onto one another. In monoclinic, the one swap (a↔c) fixes P and I and
exchanges A and C. So searching the pruned half for C asks the same question
as searching the kept half for A (and B in orthorhombic). The leaf replay
already answers "would that centring's own search reach this box" exactly,
because every prune is monotone under bisection (WP-1509's argument). So
option 1 with A (monoclinic) and A, B (orthorhombic) reaches what option 2
reaches, with no extra boxes. The leaves differ, because the two halves are
bisected differently. The monoclinic I replay is coverage beyond option 2:
it would catch a C lattice whose every C and A setting lies past the 30°
obliquity bound. Whether such a lattice exists inside the domain is not
checked. The orthorhombic-F list whose truth moved 5 → 8 under the
reporter's arm A is therefore not evidence between the options: option 2
reaches the same wrong A/B lattices, labelled C.

**Done.** Claimed the WP. Re-checked the findings: `dichotomy.py`'s
commits since the triage sha `d87c8cc91` (WP-2030's volume window) touch
neither the prune, `_accept` nor `CENTRINGS`, and every row reproduces.
`### Inherited`: none to prune.

**Not done.** No fixtures. The C m m m list (under 3 s) and the B repro
(under 1 s) can be fast tests; the monoclinic C lists take 30-190 s here and
belong under `slow`. The fixture asserts the truth's primitive volume, which
is setting-free, but it waits on the ruling so that no test is written to
fail on purpose.

**Decision 1 (the maintainer's, by the WP's first task): fix A by option 1
or option 2.**

- *Why it matters.* Dichotomy is the one engine whose "searched and found
  nothing" is evidence. Today it reports a monoclinic or orthorhombic search
  complete while a C-centred lattice is missing. The reporter's draw puts
  that at 22-32 % of random C-monoclinic cells. It hits every orthorhombic C
  lattice whose centred face is not on its two shortest axes. A user gets no
  cell, because the gate abstains, rather than a wrong one. Moderate.
- *Aim.* An honest completeness claim for anyone indexing a centred
  low-symmetry phase. Search cost comes second.
- *Option 1.* At each leaf, replay A in monoclinic and A, B in orthorhombic,
  optionally I in monoclinic. Re-set an accepted A, B or I leaf to its
  conventional C through `engines.conventional_fit`, extending
  `reduce.conventional_setting` to those letters, so one lattice gives one
  candidate. Measured: boxes unchanged, leaves +0-73 % on these lists;
  the reporter measured +2-11 % wall. Python only; the compiled kernel is
  untouched. Reversible.
- *Option 2.* Drop the swap prune for monoclinic and orthorhombic, in
  `_test_box` and in `kernels/src/dichotomy.rs` together. Measured: boxes
  ×1.96-1.98 monoclinic, ×4.07-4.32 orthorhombic; leaves ×2-6. It needs the
  same relabelling for orthorhombic order. Inferred, not measured: on #780's
  real monoclinic grids, which already stop at the 1 GiB frontier cap in 5
  of 11 units (WP-1924), a doubled domain makes more units report
  incomplete. Reversible, but it moves the kernel.
- *Do nothing.* The false completeness stays.
- *Dropped:* closing the prune per centring inside the box test (a new
  mechanism neither the issue nor practice proposes).
- *Practice.* DICVOL (Boultif & Louër 2004) searches primitive metric forms
  and reads the centring off the reduced cell afterwards. That is recall:
  the DICVOL papers are not in the local corpus, and TOPAS and GSAS-II were
  not checked. Neither option departs from it in what is reported.
- *Recommendation: option 1, clear call.* The crux is cost, because the two
  options cover the same lattices. Option 2 pays 2-4× the boxes for nothing
  option 1 lacks. A lattice that option 2 finds and option 1 does not would
  flip it; the argument above says none exists, so one would refute the
  argument.

**Decision 2 (the maintainer's, same task): bound the annealed passes for B
(the reporter's V3)?**

- *Why it matters.* On dense lists the leaf holding the true cell is
  polished onto a nearby wrong cell. On the B repro the true cell indexes
  381 of 381 lines and is absent, while two cells indexing 288 and 273 are
  returned, with `search_complete=True`. Neither A option touches it
  (measured above). Moderate.
- *V3.* The annealed passes assign only lines up to the highest driven Q
  plus k·σ_max, with the existing k (no new constant); the two closing passes
  assign every line, as now. The reporter measured: the B truth first at
  381/381, the truth gained in 3 of the #780 units and lost in none, +37 %
  accepted leaves, +7 % phase-2 time, +12 % wall on the synthetic lists. On
  the orthorhombic C control 19 extra partial cells enter at ranks 9-42, and
  one orthorhombic-F lab list's truth drops 5 → 7.
- *Do nothing.* B stays.
- *Practice.* Not checked: no program's annealing schedule is surveyed.
- *Recommendation: V3, lean.* The crux is a truth found against extra
  candidates ranked below it, which cost validation time and no rank on
  these lists. A ranking move in `tests/test_acceptance_indexing.py` would
  flip it.

**Next.** On the ruling, record `Decided 2026-MM-DD:` in the first task and
answer #1258. Then build A as decided, with the relabelling and the
one-lattice-one-candidate merge. Then V3 if wanted. Then the fixtures, the
unit replay digests and the indexing acceptance suite.

- **2026-10-31** — filed from the issue triage of #1258. No open WP owns
  dichotomy's completeness: WP-1924 owns its ceiling and memory, WP-1520 its
  leaf cost, WP-1969 stray lines in the list. Every table row reproduces at
  `d87c8cc91`.
