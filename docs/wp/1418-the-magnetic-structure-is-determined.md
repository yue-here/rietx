# WP-1418 — the magnetic structure is determined, not only stated

Milestone: v1.6 · Status: 🔄 2026-09-25 — M-6 and M-7 landed (PR #389), and the #439 row (PR #449); M-8, M-9, the Part 1 chapter and the skill rows remain
Depends on: PR #290's `crystallography.magnetic` (landed 2026-09-10);
1326 (the k candidates) for the k-search rung; 1327 (the moment, the hold)
for the determination verb. The irrep and isotropy rungs depend on nothing
unlanded.
Priority: P2 2026-09-23 — the open milestone's; M-6 and M-7 first by the set order, no forward-model contact

## Goal

A user with a neutron pattern whose nuclear model leaves intensity
unexplained gets, in order: the candidate propagation vectors, the candidate
magnetic space groups compatible with each, a trial refinement per candidate
under 1327's hold rules, and a ranked list grouped into the classes a powder
average cannot separate, each written out as a magCIF. The stored form stays
1327's operator list. The group theory is computed inside the package from
published algorithms, with spglib's database and spgrep as the oracles.

## Context

Issue #256 (2026-09-03), a design proposal for the rungs after 1326–1329,
with a 60-line check script; issue #257's amendments are folded into the
WPs they touch (1326, 1327, 1328) and not here.

**Why this is a candidate and not a fenced item.** 1327 § Non-goals reads
*"Determining a magnetic structure: representation analysis, k-SUBGROUPSMAG,
ISODISTORT's job. This WP refines a structure the user states."* #256 asks
for that to read as sequencing: the operator list 1327 refines is what the
determination rungs produce. Two facts moved since the fence was written.
`pyproject.toml` pins `spglib>=2.4`, and spglib carries the 1651 magnetic
space groups (UNI/BNS/OG numbers, operations with time reversals, and the
identification of a moment configuration's group; Shinohara, Togo & Tanaka
2023). And the first rung has **landed**: PR #290 (2026-09-10, from the
issue's author) added `crystallography.magnetic.operators`, with
`MagneticOperator`/`MagneticGroup`, `magnetic_group(spec)` and
`database_settings` over spglib's database, `identify()` from a bare
operator list, `MagneticGroup.transformed` via magCIF's
`transform_BNS_Pp_abc`, and `allowed_moment_basis`/`in_span` for the
per-site moment subspace. Its tests build all 1651 groups, round-trip
38 307 operations, identify 1648 of 1651 (three are a spglib database
defect), and assert twenty published moments lie in the *span* of the
derived subspace, never its dimension, with the Rᵀ control on three
hexagonal cases. That is root CLAUDE.md's rule for a symmetry action, kept.

So the maintainer has already accepted the layer. **The decision this WP
carries is whether 1327's non-goal becomes a sequencing statement.** The
triage's recommendation (2026-09-15) is yes, as a candidate the way 1325 is:
the shape is written, no milestone owns it, and it sits behind 1327 for the
verb while the irrep and isotropy rungs could land on their own with no
forward-model contact.

**What was measured.** With spglib 2.7.0 and spgrep 0.7.0 (BSD-3, numpy
only), for Pnma with Mn on 4b (0, 0, ½) at k = 0 the magnetic representation
decomposes into the four inversion-even one-dimensional irreps at
multiplicity 3 each and the four odd ones at 0, Σ n·dim = 12: Bertaut's
LaMnO₃ result, because a moment is axial and the 4b site symmetry contains
−1. A 4c orbit as control gives (1, 2, 2, 1, 1, 2, 2, 1). At k = (0, 0, ½)
the little group is all eight operations and returns two two-dimensional
irreps, each ×3. The group theory needed is about 60 lines over what the
tree depends on, plus tests.

**The rungs**, in the issue's letters (numbers are the maintainer's):

- **M-6 — little group, star, irreps, decomposition, projection.** Rᵀ on k;
  small irreps by induction with the factor system (the projective case at a
  zone-boundary k of a non-symmorphic group is why Kovalev tabulated them);
  CDML labels where k has one; Γ_perm ⊗ Γ_axial (and ⊗ Γ_V for displacements,
  which 1419 consumes) decomposed; basis vectors projected with every row of
  a multi-dimensional irrep and the lattice return-vector phase
  e^{−2πi k·a_g}, Gram–Schmidt reduced, real combinations where an irrep
  pairs with its conjugate. Shows it works: the Pnma check above on real
  data (LaMnO₃, `Magnetic-I`); agreement with spgrep up to a unitary
  intertwiner for all 230 groups at every special k; a published SARAh or
  BasIreps table reproduced; Σ n·dim = 3N.
- **M-7 — isotropy subgroups and the candidate models for (G, k).** Kernel
  and stabilisers of each irrep's order-parameter directions become 1327
  operator lists with irrep label and parent-cell transform; systematic
  absences per candidate (MAGNEXT) as a symmetry-only discriminator;
  **powder-equivalence classes**, candidates whose orbit-averaged |M⊥|²
  agree on every reflection (Shirane 1959 made mechanical). Shows it works:
  the published group of ≥ 10 MAGNDATA parents is in the list with its
  label; Pnma at Γ gives four maximal candidates; Shirane's cubic collinear
  degeneracy comes out as one class.
- **M-8 — the k-search beyond {0, ½}³.** 1326's arm with a pluggable
  candidate generator (issue #257 A1): every special point and line of the
  zone, labelled, then a general-k grid, an incommensurate k admitted as a
  *position* hypothesis and reported as such. Same files as 1326, so after
  it lands.
- **M-9 — the determination verb.** k candidates → M-7 candidates → one
  trial refinement per class under 1327's hold → ranking by ΔBIC at equal
  parameter count (with 1417's caveat on N) and a magnetic-only R over the
  magnetic intensities, plus the null test → a report listing the class, the
  members a powder cannot separate, the irrep, direction and symbol, and a
  magCIF per candidate (1328). Abstains with the reason when classes tie
  (1043's rule; never a confident singleton). Shows it works: LaMnO₃ 50 K
  ranks A-type first of four; Cr₂WO₆ prints the k = 0 sentence and holds at
  150 K.

M-10, mode amplitudes as degrees of freedom, is
[1419](1419-a-child-structure-refined-on-its-mode-amplitudes.md).

**Questions the issue leaves, with the triage's answers.** Irreps from
scratch with spgrep as a dev-only oracle (recommended by the issue and here:
a published algorithm, no runtime dependency, and the strongest test
available; BSD-3 makes either admissible). A UNI/BNS/OG number as an
alternative input: M-5 already does this, and a symbol *string* is refused
by name because spglib exposes numbers only. The internal moment basis: M-5
ships the conversions (`moment_to_cartesian` and back), with a MAGNDATA
round trip as the test (#257 A6). The non-goal reading: this WP.

**What it touches.** New `crystallography/magnetic/{irreps,isotropy}.py` and
tests; manual Part 2 sections with `*Source:*` lines; `ATTRIBUTION.md` rows
for spgrep if it becomes more than a test oracle (PR #290 already added
spglib's). M-8 and M-9 reach `refine.py`'s report arm and `strategy/`, and
the skill's `references/magnetic.md` (the file #287's ruling assigns to the
whole track).

**Datasets.** `Magnetic-I` (LaMnO₃, BT-1, 50 K) and `Magnetic-II` (Cr₂WO₆,
HB-2A, 4 K/150 K) as 1326/1327 name them; `Magnetic-III` (Ba₆Co₆-type
cobaltite, D1B) and `Magnetic-IV` (Pr₀.₅Sr₀.₅MnO₃, 3T2) are the first public
k ≠ 0 commensurate candidates, k to confirm from the tutorial pages before
either is named; `Magnetic-V` (Mn₃O₄, POWGEN) is TOF and stays fenced.
MAGNDATA magCIF entries serve the round-trip and span tests with no pattern.

### Inherited

- **From WP-1417, 2026-09-27: M-9's "1417's caveat on N" is settled.**
  ΔBIC is charged at N/f², `optimize.statistics.effective_sample_size`
  of the restricted fit's `esd_inflation`, and both statistics want the
  unreduced Σw·Δ². `Statistics.chi2` is reduced, over N − P. At equal
  parameter count that cancels in the ratio, so M-9's ranking is safe
  as long as every trial frees the same count; a trial that frees more
  takes each χ² back to the sum first. `report.compare_freed` covers a
  nested pair only, with each freed parameter's t beside the ΔBIC.

- **2026-09-25, from the issue triage (issue #455): M-7's class count is a
  random variable of the platform and the seed.** `isotropy.equivalence_classes`
  calls a pair *distinguishable* when any one of its draws has every restart
  of `_fit_residual` above `rtol`, and *equivalent* when all `draws` (3)
  reproduce. The reporter swept 2422 cases on a Mac and a Linux machine:
  candidate counts and MSG-type censuses agree on all of them, and 103 class
  counts differ from this cause alone. Two mechanisms. **A, local minima**
  (five of six cases studied): at `restarts=4`, 21 of 40 pair-runs that are
  equivalent came out distinguishable, so the count is too high. **B,
  partial reachability** (`P a -3`, k = (½,½,½)): one family reproduces
  about three quarters of the other's draws and converges to a real non-zero
  minimum on the rest, so 3 draws pass it about 42 % of the time and the
  count is too low. More restarts do not fix B. The platform enters through
  `MagneticCandidate.configurations`: a multi-copy or multi-dimensional
  family's basis is fixed only up to a rotation within its span (Accelerate
  and OpenBLAS pick different ones), so one seeded `rng.normal` stream draws
  different moments. *Reproduced at `07952d4e`* (macOS arm64, numpy 2.5.3,
  scipy 1.18.1, one thread): the issue's script prints the reporter's macOS
  column residual for residual, `((0, 1), (2,))` for `P 1 21/c 1`
  k = (0,0,½), and basis rotation 3 flips it to `((0,), (1,), (2,))` on one
  machine. That flip is the machine-independent proof. **The asks, the
  reporter's:** (1) stop at the first restart that reaches `rtol` and raise
  the cap (at 32, both machines agree on the five A cases, members included;
  cost ×0.97 to ×5.2; one equivalent draw still needed its 32nd restart, so
  32 is not a margin); (2) make the amplitude basis canonical, the RREF-and-QR
  that `_projector_rows` already applies, extended to the copy basis, so a
  count at least means the same thing everywhere; (3) the docstring says both
  verdicts are statistical. B needs more draws, and how small an unreachable
  fraction still counts as "distinguishable" is a definitional choice the
  reporter leaves to this WP, unmeasured in cost. A deterministic
  alternative (seed the B-fit from A's amplitudes through the span
  intersection) is named and unmeasured. M-7 is ticked, so this reopens it
  as a defect in a landed rung. The MAGNDATA recovery acceptance should say
  which platform and seed its counts were taken on.
- **2026-09-25, from the issue triage (issue #458): a blind nuclear pre-fit
  biases every moment low, measured on the fork against M-9.**
  `solve_magnetic` is not on `main` yet (checked at `07952d4e`), so this is
  read as a claim about the fork's `magnetic-v16`, taken on at M-9's PR.
  The nuclear model is pre-fitted to the whole pattern, so scale, Biso and
  extinction absorb the magnetic intensity and the profile and coordinates
  co-adapt. The final "all" stage of `SOLVE_STAGE_PATHS` frees scale and
  Biso again but does not undo it. On simulated neutron patterns of 20
  MAGNDATA structures × 3 noise seeds, solved blind: median recovered /
  published first-site moment 0.943, 10 of 20 entries at 0.43-0.93, and the
  bias tracks the pre-fit scale's overshoot (Spearman ρ −0.62). Two blind
  recipes close it: **(iv)** hold the ranked winner's moments, re-fit the
  whole nuclear model with the moment present from a generic prior (Biso
  1.0 Å², extinction 0), carry it back and solve again (0.995 at round 2);
  **(v)** one solve whose last stage also frees extinction, the coordinate
  DOFs and the profile (0.998). Both hold the exact published group on
  58 of 60 and leave a k ≠ 0 negative control unchanged. (v) frees
  coordinates in the *ranked* stage, the confound M-9 removed, and timed out
  once at 1500 s; (iv) keeps the ranked stage and needs a stopping rule and
  an API that hands `solve_magnetic` a nuclear state from a refined trial.
  **A gate defect found on the way, independent of the recipe:** `_rank`'s
  3σ null test reads each modulus of a powder-degenerate pair alone (each
  esd about 2.4× its value, the quadrature sum 63σ clear), so a correct
  class is ineligible; and the Q5 fold reads only the five-slot
  `top_correlations`, which free coordinates can fill. Fork branch
  `fix/w14-rank-key` adds `MomentRow.pair_supported` and reads the stored
  `HIGH_CORRELATION`/`FLAT_DIRECTION` findings. **The asks:** the gate fix
  first; a default recipe (the reporter reads (iv) as default and (v) as an
  opt-in plan); a diagnostic when the nuclear scale moves by more than its
  esd between the pre-fit and the final stage. WP-1343 is the same symptom
  (a moment reading low) from a different cause, the width. All numbers
  are on simulated data; none on incommensurate k or a joint fit.
  **Decided 2026-09-25**, after the maintainer asked for established
  practice. Neither recipe is it: Rodríguez-Carvajal's FullProf tutorial
  refines the nuclear model on a pattern above T_N, fixes the structural
  parameters below it, and keeps "the scale factor … constant and equal to
  the scale factor obtained for the nuclear structure; otherwise the
  magnetic moment amplitudes cannot be properly determined" (checked
  verbatim). So: (1) the gate fix first, its own PR; (2) `solve_magnetic`
  takes a nuclear reference when there is one (a paramagnetic pattern, or a
  refined nuclear model with its scale), held in the ranked stage; (3) with
  none, (iv) is the default, with the stopping rule and a round cap, through
  the same seam as (2); (4) (v) is an opt-in plan; (5) the nuclear-scale
  diagnostic. The reporter was asked for a zero-moment arm standing in for
  the paramagnetic reference.
- **2026-09-24, from the issue triage (issue #439): the spgrep oracle's
  refusal count depends on the machine.**
  `tests/test_magnetic_irreps.py::test_physically_irreducible_dimensions_agree_with_the_spgrep_oracle`
  (M-6, PR #389) pins `(checked, agreed, declined) == (1363, 1363, 114)`
  under spgrep 0.7.0. The reporter found one case, `P n -3 m:1` at
  k = (½, ½, ½), where spgrep's own `real=True` construction raises
  `AssertionError: T is not square root of intertwiner.` on their macOS
  arm64 machine but returns on their WSL2 x86_64 one, which reads
  `(1364, 1364, 113)` and fails the pin. *Checked at `8fbafe5`*: **the split
  is not macOS against Linux.** On this triage's Linux x86_64 container
  (numpy 2.5.3 on scipy-openblas 0.3.34, `DYNAMIC_ARCH`, Haswell kernel;
  spgrep 0.7.0) that case declines too, and the test passes at the pinned
  counts in 42 s. The likeliest variable is the BLAS kernel OpenBLAS picks
  for the CPU, which is unmeasured. Either way the pinned `declined` count
  measures spgrep's floating point on one machine, not this package. **The
  ask, the reporter's:** keep the two platform-independent assertions
  (`agreed == checked`, `checked + declined == 1477`). Replace the exact
  pin with the invariant that matters, that the declined set is a subset of
  a recorded list of spgrep's refusals (114 entries, this case included), so
  a machine that declines fewer still passes and one that declines a new
  case fails by name. Keep the mutation-probe property the test's docstring
  records (a construction that raises everywhere must still go red). A
  test-only change; the reporter offered the PR. Whether to report the
  assertion upstream to spgrep is separate.
- **2026-09-21, from the issue triage: #384 and #390, both measured on the
  fork against this WP's solver.** Checked against the tree at `4ee4e7f5`:
  `solve_magnetic` is not on `main` yet, so neither can be reproduced here;
  both are read as claims about the fork's `magnetic-v16` (aa665eaf) and
  taken on at the PR. **#390** ran the determination verb blind over every
  commensurate MAGNDATA entry with the published k: 70 % recover the
  published group exactly, 88 % it or a supergroup. The supergroup cases
  were *not* a missing kernel-subgroup candidate (checked: the published
  class is enumerated, refined and loses); the real fault was a moment with
  two or more free components seeded along its first basis row, a stationary
  point of χ² where the residual point-group action fixes that row, fixed by
  a deterministic 0.02 tilt (0.15 regressed two of twenty controls). After
  it, six of nine supergroup winners remain across noise draws: the
  secondary order parameter is unsupported at those statistics, a power
  finding and not a ranking defect. Three pieces of machinery ride in the
  series: `MagneticSolution.margin` (ΔBIC over the best *other eligible*
  class, `None` on abstention, one eligibility helper), a **descent audit
  after selection** (the winner's maximal same-k operator-list subgroups
  refitted from its own solution, `MAGNETIC_SUBGROUP_PREFERRED` if one beats
  it beyond the tie width; k ≠ 0 descents changing the atom count not yet
  matched), and the group–subgroup lattice among tied classes in the
  summary. Proposed acceptance wording, to take or leave: *a supergroup
  winner is accompanied by the descent audit's statement of what ΔBIC its
  maximal subgroups reached, and the report says the secondary order
  parameter is unsupported rather than absent.* **#384** asks that the
  candidate comparison reach where a person reads a fit afterwards: (1) a
  structured `magnetic_candidates` section on the winner's `FitReport` (the
  rows `str(solution)` prints, plus verdict, reason and tie diagnostics;
  smallest, offered for this WP's PR series); (2) the tree records the
  fan-out, one `stage` subtree per candidate class with the chosen class the
  continuing branch, under a `select` kind carrying criterion and margin,
  with `cherry_pick` able to replay a loser as the completeness check;
  (3) the GUI tree greys rejected branches and shows the margin on hover.
  (2) is a `NodeKind` addition and so a vocabulary member that needs its
  writer named (root CLAUDE.md, WP-1076); (3) is `gui/`'s. **Decided
  2026-09-21** (posted on both threads): #384 part 1, the `FitReport`
  section, lands in this WP's PR series; parts 2 and 3 are a follow-up WP
  after this one ships, since a `select` kind is a vocabulary member with a
  writer to name and the GUI reads what the tree records. #390's acceptance
  wording is taken as offered and is this WP's; the seed tilt's docstring
  carries the two numbers that chose it (0.15 regressed two of twenty
  controls, 0.02 none) and the control set.
- **2026-09-18 — this WP is v1.6's first, and M-6 and M-7 are its first PRs.**
  The milestone opened today ([record](../milestones/v1.6.md)) over the seven
  magnetic WPs. The order was set on #286: M-6 (irreps, spgrep as a test oracle
  only) and M-7 (isotropy subgroups → operator lists, powder-equivalence
  classes) go first, on the reading that neither touches the forward model and
  both exist on the `mustachefeeling` fork with green suites; M-9 lands with
  this WP rather than with 1327; 1419 is a PR of its own. Two housekeeping
  clauses came with it. **The `SCHEMA_VERSION` ladder starts above `main`'s
  own** — check what `schemas/common.py` holds when the first PR is cut, rather
  than reusing a number reserved weeks earlier. And **every magnetic row in the
  agent skill goes in `references/magnetic.md`, diagnostic codes included**;
  the caps are checked on the merge result, so the whole set is measured once
  before the first PR rather than discovered at the sixth merge. `main`'s
  headroom today, after the `diagnostics-gsas.md` split landed:
  `diagnostics.md` 29 942 B of 36 000, `SKILL.md` 32 864 B of 33 000 — 136 B,
  so the body takes nothing, which is what the routing row rule already says.
  **Added 2026-09-18: the same holds for the entry points.** A magnetic verb
  renders to a generated `references/api-magnetic.md` and never into `api.md`,
  which every session about to call rietx loads whole, so a name only a
  magnetic refinement reaches costs every other session nothing. That file is
  the *generated* index and is distinct from the authored
  `references/magnetic.md` above; only the generated one is pinned byte for
  byte against `make_api_index.py`. `tests/test_skill.py`'s coverage gate
  reads the union of `api*.md`, so M-9's verb is documented by appearing in
  the magnetic index and nothing has to be added to a list. Root CLAUDE.md
  § skill carries the rule.
- **2026-09-17, from [1436](1436-k-is-the-wavevector-everywhere-else.md):
  `k` is free for the propagation vector.** The earlier note here warned that
  `scattering.py`, `structure_factor.py` and `dispersion.py` all spent `k` on
  sinθ/λ, in the same subpackage `crystallography/magnetic/` lives in, and
  asked this WP to spell the propagation vector out rather than add a second
  bare `k`. 1436 has landed: that quantity is `stol` in python and `s` in
  equations throughout, following Waasmaier & Kirfel and the IUCr core
  dictionary, and a tree-wide sweep found no line left pairing a bare `k` with
  sinθ/λ in `src/`, `tests/`, `examples/` or the manual. **So name the
  propagation vector `k` and add no qualifier.** Root CLAUDE.md § Conventions
  carries the rule that keeps it free. The same note is in 1326, 1327, 1328 and 1329.

## Non-goals

- Modulated and incommensurate structures (superspace): issue #258 holds the
  shared design and the v2+ fence holds the item.
- Time-of-flight, polarised neutrons, magnetic X-rays (1327's fences).
- Mode amplitudes as refinable DOFs (1419).
- A magnetic phase as a second phase; 1327's site-attribute shape stands.

## Tasks

- [x] M-6: irreps and decomposition, spgrep as oracle in the test suite
      only; the Pnma 4b/4c checks and the 230-group intertwiner test.
- [x] M-7: isotropy subgroups → operator lists, absences, powder-equivalence
      classes; ≥ 10 MAGNDATA parents recover their published group.
- [ ] M-8: 1326's candidate generator made pluggable and the zone's special
      points and lines added, labelled.
- [ ] M-9: the verb, the ranking, the abstention, the magCIF per candidate;
      `capabilities()` feature flag; `help.py` entries.
- [ ] Manual Part 2: the projection operator, the return-vector phase, the
      powder-equivalence criterion, each with a *Source* line; Part 1 chapter
      under the magnetic one.
- [ ] Skill: the rows in `references/magnetic.md` (never the body); the
      1043-style abstention row.
- [ ] Tests, with obs/calc/diff PNGs to `tests/output/` for the M-9 fixtures.

## Acceptance

LaMnO₃ 50 K ranks A-type first of four with the class listed; Cr₂WO₆ 150 K
abstains with the k = 0 sentence; every shipped fixture is bit-identical with
no magnetic model declared.

```sh
.venv/bin/python -m pytest tests/test_magnetic_operators.py tests/test_magnetic_irreps.py tests/test_magnetic_isotropy.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #256, #257 (2026-09-03); PR #290 (M-5, landed 2026-09-10).
- Bertaut, E. F. (1968), *Acta Cryst.* A**24**, 217.
- Izyumov, Yu. A., Naish, V. E. & Ozerov, R. P. (1991), *Neutron Diffraction
  of Magnetic Materials*, Kluwer.
- Wills, A. S. (2000), *Physica B* **276–278**, 680 (SARAh).
- Bradley, C. J. & Cracknell, A. P. (1972), *The Mathematical Theory of
  Symmetry in Solids*, Oxford; Neto, N. (1973), *Acta Cryst.* A**29**, 464;
  Stokes, H. T., Campbell, B. J. & Cordes, R. (2013), *Acta Cryst.* A**69**,
  388 (ISO-IR).
- Stokes, H. T. & Hatch, D. M. (1988), *Isotropy Subgroups of the 230
  Crystallographic Space Groups*, World Scientific; Campbell, B. J., Stokes,
  H. T., Tanner, D. E. & Hatch, D. M. (2006), *J. Appl. Cryst.* **39**, 607
  (ISODISPLACE); Perez-Mato, J. M., Gallego, S. V., Tasci, E. S., Elcoro, L.,
  de la Flor, G. & Aroyo, M. I. (2015), *Annu. Rev. Mater. Res.* **45**, 217.
- Gallego, S. V. et al. (2012), *J. Appl. Cryst.* **45**, 1236 (MAGNEXT);
  Gallego, S. V. et al. (2016), *J. Appl. Cryst.* **49**, 1750 and 1941
  (MAGNDATA).
- Shirane, G. (1959), *Acta Cryst.* **12**, 282.
- Shinohara, K., Togo, A. & Tanaka, I. (2023), *Acta Cryst.* A**79**, 390;
  Shinohara, K. (2023), *JOSS* **8**, 5269 (spgrep, BSD-3).
- Hinuma, Y. et al. (2017), *Comput. Mater. Sci.* **128**, 140; Aroyo, M. I.
  et al. (2014), *Acta Cryst.* A**70**, 126 (k-point labels).
- The full register with DOIs is issue #256's comment of 2026-09-06.

## Handover log

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #256).
  Checked against the tree: M-5 is on `main` as PR #290 and nothing in
  `docs/` recorded it until this round; spglib 2.7.0 in the venv carries the
  magnetic database. The decision it carries, the non-goal as sequencing, is
  the maintainer's; the triage recommends yes as a candidate.

- **2026-09-23** — M-6 and M-7 landed from outside: PR #389
  (`mustachefeeling`), merged as `ff5e5244` after four review rounds.
  - **What it adds.** `crystallography/magnetic/irreps.py` (small irreps of
    the little group by the ω-twisted regular representation, projective at a
    non-symmorphic zone boundary), `modes.py` (Γ_perm ⊗ Γ_axial decomposed,
    basis vectors projected per irrep row, real gauges where FS = +1) and
    `isotropy.py` (isotropy subgroups as operator lists, MAGNEXT absences,
    powder-equivalence classes). `symmetry.OperatorGroup`/`resolve_group`/
    `as_group`/`group_key` let a symbol-less group reach `site_orbit` and
    `wyckoff.site_constraints`. Manual Part 2 gains
    `representation-analysis.md`, eight equations with Source lines. spgrep
    joins `[dev]` as a test oracle only.
  - **What it makes possible.** M-8 and M-9 can call `isotropy.candidates` and
    `equivalence_classes` directly. Nothing is re-exported at `rx.` and no
    verb exists, so the api index and the skill owe nothing yet.
  - **What it does not do.** The Part 1 chapter, the skill rows and the M-9
    acceptance (LaMnO₃, Cr₂WO₆) are all still open, so the manual task stays
    unticked. Irrep labels are positional, and the CDML mapping is deferred
    in `irreps.py`. Direction labels are the package's own, and a comparison
    with a published table must go through the subgroup (BNS number).
  - **Gotchas the review found.** (1) Importing spgrep sets
    `spglib.error.OLD_ERROR_HANDLING = False` process-wide, which turns every
    `None` test on a spglib call into a raise. All ten call sites were swept.
    The reachable ones in `operators.py`, `wyckoff.py` and `indexing/reduce.py`
    now catch `SpglibError` as well. `tests/conftest.py` sets the flag back to
    spglib's default per test, so the suite cannot see the flip. (2) A rank-2
    order-parameter family's basis is gauge-dependent across platforms: a
    component pin failed on Linux and passed on darwin. Select candidates by
    BNS number and assert spans. (3) `powder_equivalent` under `lm` refused
    fewer shells than amplitudes and read the refusal as "different". It now
    switches to `trf` and skips a family with no pattern at that d limit.
  - **Left for the maintainer.** Three modules declare the same refusal tuple
    (`wyckoff.SPGLIB_REFUSALS`, `indexing.reduce.SPGLIB_REFUSALS`,
    `isotropy.IDENTIFY_REFUSALS`); one authority would need an import across
    two subtrees. The suite pins spglib's deprecated error mode and emits
    about 1530 `DeprecationWarning`s from `test_magnetic_operators.py` alone.
    Moving the package to the new mode is its own WP. The new ATTRIBUTION row
    for closed tools sits under the open-source heading, beside `xylib`.
  - **Measured on the merged tree** (darwin/arm64, py3.12, `[dev,jax]`,
    spglib 2.7.0, spgrep 0.7.0): fast 5889 passed, 84 skipped; `-m slow`
    191 passed, 7 skipped, 1 xfailed; docs ladder 63 passed, `-W` build clean.
- **2026-09-25** — the #439 row landed from outside: PR #449
  (`mustachefeeling`), merged as `2a308ec1`, closing #439 by hand (the PR
  named it without a closing keyword). Test-only, one file.
  - **What it changes.** The spgrep oracle test no longer pins
    `(checked, agreed, declined) == (1363, 1363, 114)`. It still asserts
    `agreed == checked` and that checked plus declined covers all 1477 pairs.
    On the measured spgrep, every declined `(setting, k)` must be in
    `ORACLE_REAL_MAY_DECLINE`, the 114 pairs over 58 settings recorded on
    macOS arm64. A machine declining fewer passes, and one declining a pair
    off the list fails, naming it.
  - **What it does not do.** Which BLAS kernel decides `P n -3 m:1` at
    (½, ½, ½) is still unmeasured. The list is one machine's, so a machine
    that declines a pair this Mac returns on would fail until the pair is
    recorded.
  - **Measured on the merged tree** (darwin/arm64, py3.12, `[dev,jax]`,
    spgrep 0.7.0), run twice because main moved by one WP file during the
    first: fast 6094 passed, 89 skipped; `test_magnetic_irreps.py` 46 passed;
    `-m slow` 197 passed, 7 skipped, 1 xfailed. This Mac still declines
    `P n -3 m:1` at (½, ½, ½), checked directly.
