# WP-1418 — the magnetic structure is determined, not only stated

Milestone: magnetic · Status: 🔄 2026-10-06 — M-6 and M-7 landed (PR #389), the #439 row (PR #449), M-7's frame fix (PR #536), #455's Gram path (PR #535) and basis fix (PR #532), #563's sign text (PR #564), M-9's verb `solve_magnetic` with its Part 1 section and skill rows (PR #592), #565's certificates part 1 (PR #582), #679's displacive group (PR #680); M-8, M-9's `help.py` entries, Part 2 and the M-9 PNGs remain
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

- **2026-10-05, from the issue triage (issue #724): `solve_magnetic`'s ranked
  stage frees more nuclear parameters on a supercell child than the parent
  has.** `SOLVE_STAGE_PATHS[1]` frees `phases.*.cell.*` and every
  `.atoms.*.biso` on every candidate, and `reference_for` fits the nuclear
  reference under the same stages minus the moments. The constant's comment
  keeps coordinates out because a larger child asymmetric unit lets the
  nuclear model absorb magnetic intensity; the issue says the same of cell and
  Biso (1419's Context: 28 free child Biso alone took Ba₂FeSbSe₅'s Rwp
  0.118 → 0.076, fork figures). *Checked at `32ef5a6`*: a three-site Pnma
  parent at k = (½, 0, ½) (BNS 11.55) falls back to `nuclear_group="magnetic"`
  (P 1 21/m 1, β 35.93°, 12 child atoms), where stage 2 frees 4 cell
  parameters and 12 Biso against the parent's 3 and 3. A P4₂/mnm parent at
  k = (0, 0, ½) stays on the `"parent"` route and frees 2 + 2, its parent's
  count. `SupercellStatement.site_map` gives (parent atom, coset) per child.
  Proposed: hold the child cell for a supercell statement, tie child Biso per
  parent site (`tie_equal`, a `SOLVE_B_TIED_PER_PARENT_SITE` info row), and a
  synthetic Pnma test. Open, the maintainer's: hold the cell or use 1419's
  metric subspace, and whether the reference fit takes the same ties (ΔBIC
  needs equal free sets). *Decided 2026-10-06, through draft PR #746:*
  `solve_magnetic(..., tie_to_parent=True)` is wanted as an option, default
  off. It holds the child cell, ties child Biso per parent atom, and gives
  the nuclear reference the same ties. That is the screening form. The end
  state follows mode-amplitude practice (ISODISTORT with TOPAS; Campbell,
  Evans, Perselli and Stokes 2007): the parent's own cell parameters refine,
  the child cell is derived from them, and a strain mode is freed only where
  the data show one. It is built once, in WP-1419, never here.

- **2026-10-05, from the issue triage (issue #679): a displacive
  candidate's group is a parent-lattice group at every k ≠ 0.** The rule is
  the magnetic one with 1' switched off: `order_parameter_space`
  (`isotropy.py:596`) stacks +D(g), so directions needing an element acting
  as −D are never enumerated, and `_candidate_group` (`:1132`) emits
  {R | v + Δ} on every coset, so the ε = −1 anti-translation appears as a
  pure translation. The reporter's rule: {R_i | v_i + Δ} fixes a
  displacement when ε(Δ)·D(g_i) does, a grey group on the ε(Δ) = +1
  sublattice. *Checked at `32ef5a6`* with the reporter's script (3d of
  `P m -3 m`, R point, against a random field's stabiliser under
  `grey_little_group`): 11 of 11 candidates wrong; the S10 tilt irrep gives 4
  directions where Howard & Stokes (1998, *Acta Cryst.* B54, 782) list six.
  `verified` cannot see it (#607, below). **PR #680, from a fork, open**
  (base `50777a95`): ε·D for both kinds, displacive elements only where
  ε(Δ) = η with both 1' signs, a field-stabiliser oracle, the six subgroups
  as BNS 140.542, 167.104, 74.555, 12.59, 15.86, 2.5. Unlike the issue, it
  shows `magnetic_supercell` affected: the slow Ba₂FeSbSe₅ S3(a,b) test goes
  from an order-2 group and 24 atoms to order 4 and 12, which moves 1419's
  bullet "The declared operator list and the group are two different objects".

- **2026-10-02, from the issue triage (issue #607): `MagneticCandidate.verified`
  never reads the operator list its docstring says it certifies.**
  `in_allowed_span` (`isotropy.py:956`) says the allowed-span helper "derives
  the allowed subspace back from that operator list" and that "a missing
  anti-translation" breaks it. The code reads `self.direction.stabilizer` and
  the permutation phases, never `self.group`, which is the object labelled and
  handed to the supercell builder and `solve_magnetic`. *Checked at
  `ca9bda29`* with the reporter's script: dropping only the anti-translation
  sign in `_candidate_group` changes all four MnO labels (167.108 → 166.101,
  12.63 → 12.58, 15.90 → 12.62, 2.7 → 2.4), spglib on the generated
  structure disagrees with each, and `verified=True` on all four. The
  unplanted tree agrees with spglib 4 of 4. Two fixes are offered: fold the
  op-by-op invariance of `configurations` under `self.group` (the loop
  `test_every_configuration_is_invariant_under_its_own_group` already runs)
  into the check, or reword the docstring and the failure text to say what is
  checked. The first makes the flag mean what its name says.
- **2026-10-02, from the issue triage (issue #608): the `CandidateSet` column
  "domains" prints `direction.conjugates`, about half the domain count.**
  *Checked at `ca9bda29`*: MnF₂ 136.499, LaMnO₃ 62.448 and Cr₂O₃ 167.106
  print 1 where [G_k1′ : H] is 2, and MnO 15.90 prints 3 where it is 6 (24
  over the four star arms). `_domain_operations`, which the powder sums use,
  gives the hand count on all four, so no intensity is wrong. The fix is a
  relabel of the column (`isotropy.py:1501`), the sentence about "the same
  structure in a different domain", and the test docstring that pins the
  conjugate count under the word "domains"; or print [G_k1′ : H] and say
  whether star arms are included.
- **2026-10-02, from the issue triage (issues #384, #390, #458): what PR #592
  took from each, read off its body.** #390: `MagneticSolution.margin`, the
  seed tilt, the `MAGNETIC_SUBGROUP_PREFERRED` audit and the tie lattice rode
  with M-9, "taken as the WP recorded it". #458: the null-test gate fix is
  commit `9113559c`; the recipe (the `nuclear_reference=` seam, (iv) with its
  stopping rule, the (v) plan, the scale diagnostic) and four residuals are
  reported and left for the recipe PR, as decided on #458. #384: part 1, a
  `magnetic_candidates` section on the winner's `FitReport`, was never built
  and is "left for a follow-up in the series". The handover entry of
  2026-10-02 below records the verb and does not map it to these three
  issues, so this entry does.

- **2026-09-30, from the issue triage (issue #563): the moment recipe printed
  beside `IrrepBasis` has the exponent's sign backwards for 2k ∉ L\*.**
  `modes.py:1078` and `:1083` (`pairing`) and `:132`, `:181-182` (the module
  docstring) still print `exp(-2πi k·R)`, which is FullProf's S_kj, while the
  vectors the module builds are the coefficients of `exp(+2πi k·R)` (S\*_kj).
  *Checked at `e3e6486a`*: the lines are unchanged. The reporter's kagome-K
  case (spglib, no rietx code) gives 36 operations for the `+` field and 12
  for the printed recipe, a mixture of S1 and S6. Nothing shipped consumes a
  complex-k ψ, so this is text and a field-side test, no number moves. Fix PR
  #564 is open. The reporter also asks whether a `moment_field(basis,
  amplitudes, translations)` builder is wanted; that is new public API and
  **Decided 2026-09-30:** the sign text is fixed by PR #564 and the `moment_field` builder waits until a k ≠ 0 consumer exists.
- **2026-09-30, from the issue triage (issue #565): M-7 as a certificate, a
  proposal, not code.** The reporter's scoping (Farkas dual, minimum-norm
  d = 1/‖y‖, isometry, transfers, a consistency rule) gives
  `equivalence_classes` a *proved* or *sampled* label per directed pair.
  Six cubic cases ran on two machines with identical verdicts; the positive
  arm (600 certified draws re-fitted) reproduced none. It touches only
  `isotropy.py` and lands as five PRs after #532. Four questions are open and
  are the maintainer's: what `classes` means (split partition, the
  reporter's suggestion, against union-find), the accept floor (1e-12 with an
  exact LDLᵀ check), the default draw count (12 per direction on unsettled
  cross-irrep pairs), and the metric for d (unweighted L2 with a printed
  bracket). *Checked at `e3e6486a`*: #535 and #536 are merged and #532 is
  open, so the premise holds; the `isotropy.py` line numbers it quotes are on
  `44eaa091` and were not re-measured. **Decided 2026-09-30:** all four suggestions taken (the split partition in `classes` with `merged_classes` beside it; the 1e-12 floor with the exact check as arbiter; 12 draws per direction on unsettled cross-irrep pairs with n printed; unweighted L2 with a printed bracket). Chunked as five PRs after #532, per the issue.
- **2026-09-30, from the issue triage (issue #258, two comments of that
  day): the reporter proposes splitting M-11.** (1) A Fourier-form S_k model
  needs its sign and phase reference (cell origin R_l against full position
  R_l + r_j; FullProf's S against T, Perez-Mato 2012 eq. 1) as a required
  named field, since the two differ by exp(2πi k·r_j) per atom. This is the
  same sign question as #563 above. (2) "Needs none of N-1's machinery"
  does not hold: a Fourier model from G_k basis vectors alone leaves the
  relative phases between orbits that k → −k splits free (CaFe₄As₃: 7
  parameters where the superspace group allows 4; Perez-Mato 2012, Table 4).
  The fix is the extended little group G_{k,−k} and the invariance equation
  (eqs. 16-19). Proposed: **M-11a** the forward model, S_k schema and
  `IrrepBasis` bridge; **M-11b** the k/−k coset and invariance equation,
  shared with N-1, whose acceptance is that it does not reproduce the
  over-parameterisation. **Decided 2026-09-30: split it** into M-11a and M-11b as proposed. The paper's table and equation numbers were not re-read here.
- **From [1506](1506-a-planning-doc-pr-runs-what-reads-it.md), 2026-09-27:
  `isotropy.analyse` on F m -3 m takes 26 s, and the fast suite pays it
  twice.** `isotropy.analyse(isotropy.candidates("F m -3 m", (0, 0, 0),
  GAMMA), d_min=2.0)` measured 26.4 s alone for 6 candidates, about 4.4 s
  each. `candidates` took 0.7 s, and P 4/m m m took 0.5 s for 4. Under a
  loaded fast run the call took about 70 s.
  `test_a_cubic_collinear_site_gives_one_powder_equivalence_class` and
  `test_the_cubic_and_tetragonal_arms_differ_for_the_reason_claimed` each
  compute it, the two slowest tests in the fast selection (68.8 and 71.3 s,
  10% of its 1 372 worker-seconds). A module fixture halves the suite's cost.
  A faster `analyse` would fix the tests and every caller, since the function
  is public. Which one is this WP's call.

- **From WP-1417, 2026-09-27: M-9's "1417's caveat on N" is settled.**
  ΔBIC is charged at N/f², `optimize.statistics.effective_sample_size`
  of the restricted fit's `esd_inflation`, and both statistics want the
  unreduced Σw·Δ². `Statistics.chi2` is reduced, over N − P. At equal
  parameter count that cancels in the ratio, so M-9's ranking is safe
  as long as every trial frees the same count; a trial that frees more
  takes each χ² back to the sum first. `report.compare_freed` covers a
  nested pair only, with each freed parameter's t beside the ΔBIC.

- **2026-09-27, from the issue triage (issue #458): the zero-moment arm is in,
  and the gate fix cannot be a PR off `main`.** Two reporter comments after
  the 2026-09-25 decision below. *Checked at `ebc45b9`*: `solve_magnetic`,
  `strategy/magnetic.py`, `_rank` and `MomentRow` are still not on `main`.
  So decision (1)'s "its own PR" has no base. The reporter proposes the gate
  fix (`pair_supported`, the Q5 fold reading the stored findings) as its own
  first commit in the M-9 PR, and the recipe ((2)-(5)) as a separate PR
  after M-9. A standalone PR right after M-9 is offered as the alternative.
  **The arm asked for**, simulated on the fork's `magnetic-v16` with the gate
  fix, on the same 20 MAGNDATA entries × 3 seeds. A second pattern at the
  same scale with every moment zero was fitted blind (Le Bail
  `profile_only`, then `mccusker_structural`). Its models were the parent
  for `solve_magnetic`, whose ranked stage was restricted through `plan=`.
  Median recovered/published moment, first-site / site-averaged:
  blind 0.943 / 0.943 (58/60 exact group); **R**, reference held with the
  scale held, 0.997 / 0.997 (59/60) at 0.46× the blind arm's wall clock;
  **R′**, scale free, 0.998 / 1.001 (59/60) at 0.43×; the 2-round
  alternation (iv) 0.995 / 0.998 at 3.0×. R − (iv) per entry is
  +0.001 ± 0.022. The gain is carried by holding Biso, extinction, profile,
  cell and coordinates; a freed scale stays at 1.000 of truth once Biso is
  held. R′ lands one three-site entry 6-7 % low on two seeds (its reference
  fit carries `BACKGROUND_ABSORPTION` on the scale, untraced), so R is the
  steadier. The reference fit stopped at `max_iter` on 5 of 60 cells, and R
  and R′ ran on macOS against the earlier arms' Linux (the blind re-run
  matches 47 of 60 cells to four decimals). This measures decision (2) as
  the default, with (iv) the fallback. Four residuals survive an unbiased
  reference (the 1.370 control, one entry ~6 % low, one ~2.5 % low, one
  site swap with the right sum), so they sit in the magnetic step.
  **Decided 2026-09-27** (issue triage, on #458): the gate fix is its own
  first commit in the M-9 PR, and the recipe ((2)-(5)) follows as a separate
  PR once M-9 is in. The held reference, **with its scale held** (R), is the
  default when a reference exists, and (iv) is the fallback. The four
  residuals are M-9's to report, not the recipe PR's to fix.
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
- **2026-09-29** — M-7's frame fix landed from outside: PR #536
  (`mustachefeeling`), merged as `291dee9e` in a `/pr-review` run, closing
  #534. It was gated in one stack with #530, which shares no file with it.
  - **What it fixes.** `isotropy.moment_cartesian` rebuilt the magnetic cell
    from its six parameters through `operators.moment_to_cartesian`, which
    puts the cell in the Cholesky frame. `reflections()` puts ĥ in the
    lattice's own frame, q = A⁻¹h. The two frames agree only for an
    axis-aligned cell, so on a rotated or left-handed k ≠ 0 child cell
    M⊥ = M − (M·ĥ)ĥ was taken against the wrong ĥ. It now returns
    `moments @ lattice`, Σ mᵢ**a**ᵢ in A's frame. That fixes every M-7
    output on such a cell: intensities, M⊥ absences, `determinable_amplitudes`
    and the classes. MnO type (`F m -3 m` 4a, k = (½,½,½), a cell rotated
    140°) now gives two classes, {∥ [111]} and {in the (111) plane}, with the
    [111] candidate absent at (½½½), as Shirane (1959) and Roth (1958) have
    it. Before the fix it gave one class. The refinement path
    (`scattering.magnetic_f2`) builds Q and the moment from the same cell
    parameters and was never affected. A new test holds the two paths equal
    reflection by reflection, on a rotated cell and on a left-handed one.
  - **What it makes possible.** Class counts on rotated cells mean something
    now. **Every count measured on one before `291dee9e` is unreliable**,
    and that includes the cubic k-sweep counts and three of the six cases in
    the #455 note under Inherited (`P m m a` (½,0,½), `P 4/n:1` (½,½,0) and
    `P a -3` (½,½,½)). #534 reports that `P n -3 m:1` at (0,0,½) goes from 4
    classes to 3 with the frame fixed. That number is not re-measured here.
  - **What it does not do.** It leaves #455's seed and basis dependence
    alone. That is #532, and #535 changes how the fit's residual is
    evaluated. Both were measured before this fix and are still open. On
    their PRs the author said they would re-measure on top of it.
    `P b c m` (0.308, 0.114, 0.07) at (½,0,0) has a magnetic cell (b, c, 2a),
    a proper rotation of the parent axes, and its per-shell intensities move
    by up to 1.3× their maximum under this fix. It is one of #535's pinned
    partitions, so that pin has to be re-checked on the new frame.
  - **Gotchas the review found.** (1) A frame test on a standard-orientation
    cell cannot see this class of defect. The old `moment_cartesian` pin
    passed with the bug in place, and the new one rotates and rotoreflects
    the lattice first. (2) `INTENSITY_RTOL` is declared as a tolerance on
    |M⊥|², but `systematic_absences` applies it to |M⊥|. That predates this
    PR and was not changed by it.
  - **Measured on the merged tree** (Linux x86_64, 4 cores, py3.12.3,
    `[dev,jax]`, run as root, `origin/main` `5ac3fc0` + #536 + #530): fast
    6842 passed, 111 skipped. The fast run was on `a332029b`. #542 then
    moved main by four markdown files, and the docs, skill and hook tests
    were re-run on the rebuilt tree: 275 passed. `-m slow`: 229 passed, 14
    skipped, and 1 failed, `test_held_phase`'s ramp runaway guard (137.9 s
    against 60 s under load; it passes alone in 18.6 s; WP-1420's). The
    eight isotropy-importing files, `-m slow`, gave 35 passed. The positive
    arm reproduces the PR's table: with `main`'s `isotropy.py`, 6 of the 8
    new cases fail and the two controls pass. `-W` build clean.
- **2026-09-30** — #455's Gram path landed from outside: PR #535
  (`mustachefeeling`), merged as `44eaa091` in a `/pr-review` run. It
  addresses #455 and does not close it. `powder_equivalent` answers the same
  question as before, much faster: one evaluation is ×110-×180 cheaper and a
  cubic `P n -3 m:1` `equivalence_classes` run takes 53 s where it took
  920-2708 s. It changes no definition. #532, the seed and basis half of
  #455, is still open and now has to rebase onto this.
  - **What it does.** M⊥ is linear in a family's real amplitudes b, so a
    shell's powder intensity is bᵀG_s b, with one real PSD matrix per shell
    (`isotropy.gram`). `_fit_residual`, `powder_intensities(factors=…)` and
    `determinable_amplitudes` evaluate through the stack, and the exact
    Jacobian is 2G_s b. It agrees with the tensor path to 3e-15. That check
    cannot see a frame error, since both contract the same structure
    factors. #536's frame tests run through the Gram path and pass.
  - **Dark shells.** A shell with G_s under `INTENSITY_RTOL` of the stack's
    largest can never be lit by the fitted family. If the target is dark
    there too, the row is dropped. If the target is lit there by more than
    `rtol`, the fit returns that floor without drawing a start. This is
    exact for G_s ≡ 0 only, and the docstring now says so: a shell counted
    dark at the tolerance can still reach the target for a large enough ‖b‖.
    The dark-shell rule settles 36 of 132 cubic ordered pairs, and 12 of 16
    on each `P n m a` case.
  - **The solver.** `lm` when the live shells are at least the amplitudes,
    `trf` otherwise, since `lm` refuses fewer residuals than variables. On
    the fixed frame, `trf` on the live rows hits as often as `lm` on all
    rows, or more, on every pair measured (18→18 cubic: 11-16 of 16 against
    2-11). That is #389's rule.
  - **What it does not do.** The cubic partition is still statistical. On
    the fixed frame, 3 seeds × 3 bases give 3 distinct partitions of 2-4
    classes. S3 and S4 merge in all nine, and S1 against S2 moves. That
    rotation dependence is #532's. The 11-against-5 comparison in the PR's
    first description was measured in the wrong frame on both sides. At the
    default seed, `main` and the branch now give the same 2 classes. The
    test file does not get faster: 94.1 s of 94.3 s on an `F m -3 m`
    `analyse` is `_domain_operations` closing the grey little group in exact
    `Fraction` arithmetic once per `structure_factors` call. The PR names
    that as a separate small fix.
  - **Next, for whoever lands #532.** Its three `isotropy.py` hunks conflict
    with this one. The resolution both PRs agreed: keep #532's canonical
    basis, early stop and cap, and this PR's `grams` argument, so
    `_fit_residual(target, grams, rng, *, restarts, rtol)`, where `rtol`
    serves as both the dark-shell floor and the early stop. #532's
    `test_the_fit_stops_at_the_first_restart_that_reproduces` moves from
    `factors, shells` to `grams`. Hoist `gram(...)` beside #532's
    once-per-case `structure_factors` in `equivalence_classes`. Here it is
    built per draw, about 2.6 ms. Measure `test_magnetic_isotropy.py` once
    on the combined tree: #532's raised cap cost that file ×12-17 on `main`,
    and this path paid for most of it in round 1 (cubic tests 73-75 s
    against 207-215 s).
  - **Gotchas the review found.** `INTENSITY_RTOL` is declared on |M⊥|².
    This PR applies it to G, which is |M⊥|²-scale, so it matches the
    declaration. `systematic_absences` still applies it to |M⊥|. That
    predates both PRs and is recorded in the 2026-09-29 entry above.
  - **Measured on the merged tree** (Linux x86_64, 4 cores, py3.12.3,
    `[dev,jax]`, run as root, nothing else running, on `origin/main`
    `4de2528` with #535). Full suite with slow tests included: 7092 passed, 120 skipped,
    1 failed in 1:09:14. The failure is `test_held_phase`'s ramp runaway
    guard (81.7 s against 60 s; 18.8 s alone, WP-1420's load sensor). The
    7092 is the previous gate's 7084 plus this PR's 8 tests. `main` then
    moved by #560 (two WP files), and `test_docs_consistency` re-ran on the
    rebuilt tree: 25 passed.

- **2026-09-30** — #455's basis fix landed from outside: PR #532
  (`mustachefeeling`), merged as `3fb48679` after three review rounds, on a
  stacked gate with #541, #546 and #522 (fast 7156 passed / 101 skipped, slow
  234 passed / 12 skipped; macOS arm64, `[dev,jax]`). The PR edited no file in
  `docs/wp/`.
  - **What it adds.** `equivalence_classes` no longer depends on the amplitude
    basis (`_canonical_basis`: SVD row space, RREF, QR with positive diagonal),
    stops at the first restart that reproduces (`rtol`), and builds each
    candidate's structure factors and Gram stack once. `_fit_residual` is
    `(target, grams, rng, *, restarts=32, rtol=None)`, where `rtol` is both
    #535's dark-shell floor and the early stop.
  - **What it does not settle.** The cubic case (`P n -3 m:1` (0,0,½)) still
    gives a partition that moves with the rotation although the canonical
    bases agree to 9.2e-16, so the PR says "Addresses #455", not "Closes".
    The docstring numbers (48 % of single restarts, 21 of 32 pair-runs
    distinguishable at 4 restarts, 2 of 192 draws unreproduced in 32) were
    re-measured on #534's fixed frame. Mechanism A at 32 restarts is "usually
    enough", not a margin.
  - **Gotcha.** The fast tier stayed small by passing `restarts=4` in the tests
    whose claim is that two frames agree. A new test of that kind should do
    the same, or it pays the full 32 on every distinguishable pair.

- **2026-10-01** — #563's sign text landed from outside: PR #564. The moment
  recipe printed beside `IrrepBasis` now has the right exponent. The vectors
  are the coefficients of exp(+2πi k·R), and the FullProf mapping is stated:
  S₋ₖ = Σ C·ψ, and Sₖ its conjugate. *Done:* PR #564 (`b6dc8e3c`), merged as
  `beb48147` by `/pr-review`, closing #563 as the `### Inherited` entry of
  2026-09-30 decided. No number moved: only docstrings and the `pairing`
  string changed. The new `test_magnetic_field_convention.py` measures the
  field's active action on a supercell, over three complex-k cases, two
  zone-boundary controls and a conjugated-vector negative arm, with spglib's
  magnetic-space-group identification as a second oracle. *Gotcha:* the
  docstring cites Wills (2000) *Physica B* eq. (3) for SARAh's side, and that
  paper is not in the library. Wills (2025), *Acta Cryst.* B, "SARAh – web
  representational analysis", eq. (3) states the same D({E|t}) =
  exp(−2πi k·t), and the review asked for that citation beside the 2000 one.
  *Next:* #582 (part 1 of 5 of #565), which the maintainer freed for review on
  2026-10-01.

- **2026-10-02** — M-9's verb landed from outside: PR #592 (`66d03eaa`),
  merged as `ac91b5f0` by `/pr-review` after two rounds. `rx.solve_magnetic`
  takes a converged neutron fit with unexplained intensity and returns a
  `MagneticSolution`. It proposes k, refines one trial per powder-equivalence
  class, and ranks them by ΔBIC against a nuclear reference, then the
  magnetic-only R, then parsimony, never Rwp. It writes one magCIF per class
  on request and sets `capabilities().features["magnetic_determination"]`.
  Part 1 is `using/refining.md` § Determining a magnetic structure. The skill
  carries `references/api-magnetic.md` and the §7j routing row. *What the
  review established (round 2):*
  - **A tie inside `SOLVE_TIE_DELTA_BIC` (6.0) is not always an abstention.**
    The magnetic-only R decides when it separates the tied classes by more than
    `SOLVE_TIE_R_MAGNETIC`, then parsimony. The verdict is then `"solved"`, and
    `margin` can be negative by at most the tie width. Only when neither key
    separates them does the verdict abstain. The docs were changed to match
    the code. The 2 % in `SOLVE_TIE_R_MAGNETIC` is **chosen, not measured**:
    no run establishes where two fits of the same data stop agreeing in R.
  - **A fit stopped on its budget is listed, not ranked**, and so is every
    trial measured against a nuclear reference still short after its
    continuations (`MagneticTrial.reference_status`, `stopped_short`). A short
    reference inflates every ΔBIC against it, in the direction that turns
    "nothing to solve" into "solved".
  - Every internal fit passes `telemetry=False`. A refused trial carries
    `None` for what no fit computed.
  - **Acceptance.** Cr₂WO₆ at 4 K solves, and at 150 K the verdict is
    "nothing to solve", with no supported moment after every fit converged.
    The WP's acceptance wording put the k = 0 sentence at 150 K; measured, it
    belongs to the 4 K arm. LaMnO₃'s A-type ranks first of four.
  *Not done, and so M-9 stays open:* no `help.py` entries; the M-9 fixtures
  write no obs/calc/diff PNG beyond the 4 K winner. *Follow-ups filed in the
  review:* `MagneticSolution` has no `model_dump`, which it needs before it
  leaves provisional. `MAGNETIC_SUBGROUP_PREFERRED` carries no `where`. A
  refused row prints `None` in the table's `det` column. *Next:* #582 (part 1
  of 5 of #565), held on one `xdist_group` mark at its round 2.

### 2026-10-02 (2nd session) — #565's isotropy certificates, part 1 of 5

Two candidate models a powder cannot tell apart can now be *proved* apart
where the data allow it, instead of only failing to be joined by random draws.
Part 1 of issue #565 landed from outside: PR #582 (`b34d125e`), merged as
`9ca91dc3` by `/pr-review` after three rounds. `isotropy.powder_relations`
returns a `PairVerdict` per ordered pair, carrying the certificate that
decided it. The certificates run on every ordered pair, and the draws are
skipped on a pair union-find has already joined. Two certificates prove a pair
apart: *absence* (a shell one model lights that the other leaves dark) and
*subspace* (the intensity span leaks). A Gram stack with no gap at the rank
cut gives no subspace certificate, since its span would be a choice of
tolerance. *Measured (the PR's, quoted in the docstrings):* the default draws
give the four classes of the known answer on `P n -3 m:1` at (0, 0, ½) in 78.3
and 78.4 s, against 134.9 and 135.6 s at three draws everywhere (one Linux
x86-64 core). Over every proved-apart pair of five candidate sets, the
smallest margin between a certificate's cut and the draws' `rtol` is 4.1e-2.
*Gotchas:* a certificate does not read `rtol`, so a caller passing `rtol`
above about 4e-2 gets certificates that split pairs the draws would join. That
is stated in `PairVerdict`, not gated, and gating it is left to part 2's
Farkas dual. `test_every_sampled_edge_prints_the_draws_it_actually_made` pins
fit outcomes at one seed and `restarts=4`, and the nightly's Windows leg has
not run it yet. *Next:* #565 part 2.

- **2026-10-06** — #679's displacive isotropy group landed from outside: PR
  #680 (`8c9bbc1a`). A displacive candidate's group now takes the coset
  character ε(Δ), so an element acting as −D is enumerated and the
  anti-translation is no longer emitted as a pure translation. The S10 tilt
  irrep of `P m -3 m` at R now gives Howard & Stokes's (1998) six subgroups,
  and the manual cites that paper beside them. The slow Ba₂FeSbSe₅ S3(a,b)
  pin moves from an order-2 group with 24 atoms to order 4 with 12, and its
  comment now gives the child's 40 atoms. The review took three rounds: the
  re-pin, then the atom arithmetic and the citation. The last round was gated
  on a six-PR stack replayed onto `65a78ab7` (macOS arm64, `[dev,jax]`, full
  suite 8724 passed, 110 skipped, 1 failed on a golden that fails on bare
  `main` on that machine too). *Gotcha:* the merged child is smaller, so
  anything 1419 built on the 24-atom S3(a,b) child should be re-checked.
  *Next:* unchanged, #565 part 2.
