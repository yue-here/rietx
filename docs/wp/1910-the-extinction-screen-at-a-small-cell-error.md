# WP-1910 — the extinction screen at a small cell error, and the other centring

Milestone: unscheduled · Status: 🔄 2026-10-26 — the default flip and the gate (PR #939), the margin scan's rows and the PNGs (PR #1178) merged; open: the second screen ruled for the default's confident misses, the contract's prose, point 2, the skill recipe
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-26 — a silent wrong answer on a path few fits run: with the default cell refinement, certified corundum's class hangs on one forbidden position read at 2.8-3.1 σ against a 3 σ bar (#1172), and the margin scan, point 2 and the skill recipe remain

## Goal

`determine_extinction_symbol` states what it requires of the cell it is
handed. A cell a few hundred ppm off then either gets the certified class or a
finding that names the cell as the cause. A P candidate whose R twin is in the
candidate list is told that the screen cannot reach the twin's groups.

## Context

**Source.** Issue #726 (2026-10-05), a design proposal on the IUCr CPD
round-robin SRM 676a corundum pattern (`tests/data/qarr/corundum.prn`;
Madsen et al. 2001). It asks which of two behaviours is intended and for the
documentation to say so.

**1. The screen holds the cell.** Its first step is one shared profile fit of
the absence-free lattice group under `workflow.validation_plan`
(`src/rietx/indexing/workflow.py:256`): background, one shift parameter, `w`,
then `u/v/x/y`. The cell is held on purpose. The docstring argues for
*validation*: "the candidate *is* the hypothesis under test … a candidate whose
metric is slightly wrong is supposed to validate badly". Every class is then
fitted with that cell and instrument frozen (`indexing/extinction.py:654`,
pipeline steps 1-3). A uniform cell error leaves a tan θ position error that
the one shift cannot take, and the absence test reads the misfit at forbidden
positions as intensity.

Measured on `32ef5a6` (`[dev]`, Linux) with the suite's own fixture from
`tests/test_extinction_symbol.py` (`corundum_inputs`: `qarr_instrument()` +
`seed_widths`, 20-90°, certified cell a = 4.759355, c = 12.99231 Å), every
axis multiplied by the factor:

| factor | best class | `R - c -` | shared-fit Rwp |
|---|---|---|---|
| 0.9992 | `R - c -` (ΔBIC −2925.9) | survives | 0.2618 |
| 1.0000 | `R - c -` (ΔBIC −3434.4) | survives, 0 of 6 testable occupied | 0.2587 |
| 1.0004 | `R - c -` (ΔBIC −1811.8) | survives | — |
| 1.0006 | `R - - -` | refuted at (2,0,−1) 44.406°, 1 of 7 | 0.3035 |
| 1.0008 | `R - - -` | refuted at (2,0,5) 56.904°, 1 of 8 | 0.3375 |
| 1.0012-1.0030 | `R - - -` | refuted, 2 of 8 | — |

`R - - -` lists `R 3`, `R -3`, `R 3 2`, `R 3 m`, `R -3 m`, and none is the
certified `R -3 c`. (2,0,5) is one of the two positions WP-1077 removed as
neighbour-tail evidence; here it comes back through the cell. The reporter
measured the flip at ×1.0008 on their own instrument and said ×1.0012 still
passed with `qarr_instrument()`. That second reading did not reproduce with
the seeded fixture. Their certified-cell ΔBIC (−1284) is from another
instrument.

**Where a caller meets it.** The skill's indexing recipe
(`docs/skill/rietx/references/diagnostics-indexing.md:193-197`) runs
`rietx.refine(..., mode="lebail", plan="profile_only")`, discards the result,
and screens `cell`, the unrefined index candidate. The manual
(`docs/manual/using/indexing.md` § The extinction symbol) says to give the
screen "a range and a width law its profile fit can actually match", and says
nothing about the cell. Under the acceptance protocol, `index_pattern`'s
corundum cell sits within 150 ppm of the certificate (asserted in
`tests/test_acceptance_indexing.py`, `test_a_certified_lab_pattern_…`), inside
the measured +0.04 %. The reporter's index cell (a ≈ 4.765, +0.12 %) came from
their own protocol and was not re-run here.

**2. The other centring.** `compatible_groups` (`extinction.py:206`) keeps
the groups whose centring is the candidate's, and its docstring excludes the
`:R` settings because an R lattice arrives in hexagonal axes. Measured: a
trigonal R candidate reaches 7 groups including `R -3 c`; a trigonal P or a
hexagonal P one reaches 45, with no R among them. So a caller who keeps the
hexagonal P twin, which a Le Bail Rwp ladder favours because it has three
times the reflections, can never reach `R -3 c`. The candidate carries no
signal for this. `bravais_ambiguous` means only "the lattice symmetry appears
only at a loose tolerance, or the two methods disagree"
(`schemas/indexing.py:439`, set at `consensus.py:631`). The supercell check
(`supercell_refuted`, WP-1449) relates a superlattice to its parent in the
ranking, never in the screen. Whether `index_pattern` lists the P twin for
corundum, and with which caveats, was not checked here.

**What the reporter proposes.** (1) Document the contract in `indexing.md`:
the cell must be certificate-quality, with the margin and the remedy (refine
the cell by Le Bail first). (2) Optionally a caution, `CELL_OFFSET_REFUTES_CLASS`
in their words, when the best class's verdict flips under ±0.1 % cell scale
(two more evaluations). On this fixture it would fire at the certified cell
itself, since +0.06 % already flips it. (3) When the list holds a centring
twin, say so and screen both, or refuse to name a centring. Explicitly not
proposed: loosening the absence test, whose null model is deliberately silent
where the profile is wrong (WP-1077).

**A fourth option, from this triage.** Refine the cell inside the screen's
shared absence-free fit, then freeze it for every class. Validation's reason
for holding the cell does not transfer: in the screen the *class* is the
hypothesis and the lattice is given. This needs measuring on the three
real-data rows (FAP, NAC, corundum) before it lands, since every class
inherits the shared fit.

**Seen in passing.** The manual's corundum numbers in that section (ΔBIC
−218, five testable positions, shared-fit Rwp 0.149) are not what the suite's
fixture gives on this tree (−3434.4, six, 0.2587). The manual may describe
another protocol. Re-measure before editing the section.

**Fences.** Markvardsen, David, Johnston & Shankland (2001) is the Bayesian
form of the screen. Its full posterior is a v2 fence (`extinction.py:100-104`)
and is not proposed here. No code is ported.

### Inherited

- **2026-10-27, from WP-2011: the indexer's validation fit is Pawley, and this
  screen's fits are not.** `validate_by_lebail` runs `mode="pawley"`
  (`workflow.VALIDATION_MODE`) and records `LeBailValidation.mode`. The screen's
  reference fit reuses `validation_plan` with its own `mode="lebail"`
  (`extinction.py:983`), as do `_fit_class` (`:773`) and the cell-free prefit
  (`:825`), so nothing here changed. Two facts bear on moving them. One Le Bail
  pass of that plan left `w` on its floor on true corundum and zircon (WP-2011
  § Re-measured 2026-10-27). And a Pawley fit's `n_free_parameters` includes
  its intensity block, so `hamilton_justified`'s `n_lines + n_free_parameters`
  (`:1137-1141`) would count the intensities twice (read, not run). Whether the
  screen moves is WP-2062's decision 2.

- **2026-10-18, from WP-1986 (writing the indexing guide): the shipped
  fluorapatite pattern is a public case of this WP's failure.** `FAP.XRA`,
  Cu Kα lab, true group P 6₃/m. `pick_peaks` over 15-60°, then
  `index_pattern` with `SearchSpec(systems=("hexagonal", "trigonal"),
  max_volume=800)` (11 s) puts the true cell first at a 9.3807, c 6.8936 Å,
  c 0.12 % above the refined 6.8852. `determine_extinction_symbol(data,
  candidate, lab)` on that cell: P - - - first, `P 63 - -` refuted at ΔBIC
  +37.6. With `refine_cell=True` at the default range the cell refines to
  a 9.3252, c 6.8599 (−0.5 %) and `P 63 - -` sits at +122.8, not refuted.
  With `refine_cell=True, two_theta_limits=(15, 130)` the cell lands at
  9.37024 / 6.88524 and `P 63 - -` is best by ΔBIC −37.4 yet refuted on
  (0 0 7) at 103.04°. With `two_theta_limits=(15, 60)` and no refinement,
  `P 63 - -` ranks first at −2.1. Not re-run on PR #939's branch. The
  Guides tab's indexing page (WP-1986 item 18) waits on this.

- **Decided 2026-10-16 (maintainer, from the issue triage, #726): the
  local-baseline refutation check is welcome as a PR after #939 merges.** Its
  fixture is public (PbSO4, `tests/data/gsas2_pbso4.gpx`), never the
  unpublished pattern; the 10-kit table travels with it; the PR states what
  the check still catches once the prefit has seeded the background.

- **2026-10-16, from the issue triage (#726): two comments of 2026-10-15 are
  in no WP, and one carries an unanswered PR offer.** The 2026-10-13 comment
  (gate + prefit) is the 2026-10-14 entry's PR #939. The two after it are not
  recorded; figures are the reporter's, not re-run. (1) **Ba2FeSbSe5** (Pnma
  read as Pmcn, true class `P - c n`; lab Cu Kα; unpublished, so not a
  fixture): the screen abstained after the cell-free `profile_only` Le Bail
  prefit with `auto_background(seed=True)` (prefit Rwp 0.046). Every class
  with a testable absence was refuted, `P - c n` at ΔBIC −13.9 (5 of 7
  positions), its sub-classes at −91.8 and −84.1. The flagged positions
  (0,1,0)/(1,0,0) at 9.63-9.68°, (0,0,3) at 21.07° are empty in the raw
  counts; the background there is steep and high (5 600 and 3 450 counts) and
  the 3σ test reads its misfit. So the prefit does not cure WP-1542's pedestal
  mechanism where the background is steep. (2) **Proposed check, in their
  harness:** a refutation stands only if a flagged position carries a line
  against a local quadratic baseline (±6 FWHM, ±1.5 FWHM and picked peaks left
  out, upward clipping; Z ≥ 3 or a picked peak within ½ FWHM), the residual
  test staying the trigger; among survivors prefer the most testable absences
  over lowest ΔBIC. Scored on 10 benchmark kits with the true cell
  (Ba2FeSbSe5, PbSO4, Si x2, Al2O3 x3, Fe2O3, ZnO, CeO2, NiO): false
  refutations 20 against 7, inconsistent classes refuted 127 of 131 against
  123, pick consistent with the true group 10 of 10 (the screen: 4
  abstentions). Its 7 remaining false refutations are weak real lines at
  forbidden positions (Ba2FeSbSe5 40.50° and 49.80°, ZnO 52.69°, one on Al2O3
  BT1), unexplained. They offered a PR against the screen; nobody has
  answered. Tree: PR #939 (the gate and the default flip) is in review round 2
  and edits `determine_extinction_symbol`, so a second PR on the same function
  conflicts. Decision for the maintainer: take the check as a PR (suggest
  after #939 merges, with the 10-kit table and a public-data-only fixture,
  PbSO4 `tests/data/gsas2_pbso4.gpx`), or keep it in their harness.

- **2026-10-11, from the issue triage (#726, the reporter's comment of
  2026-10-11 09:56Z): a second public case, PbSO₄, where both documented
  remedies together give a wrong class.** Both histograms of
  `tests/data/gsas2_pbso4.gpx` (Hill 1992). The screen gets the cell
  `index_pattern` returned for the neutron pattern, (6.9644, 5.4038, 8.4956) Å,
  0.1-0.2 % long, so the true class reads `P c - n`. The reproducer is in the
  comment and reads the histograms through the private
  `io.projects.gsas2._read_tree`. **Reproduced at d80ca5f4 on the X-ray
  histogram** (`[dev]`, macOS arm64):

  | arm | `best_or_none()` | `P c - n` |
  |---|---|---|
  | `refine_cell=True` | `P c - n` | ΔBIC −295.5, 5 testable |
  | + `auto_background(seed=True)` | **`P c - -`** | refuted at (2,3,0) 57.579° |
  | `profile_only` Le Bail first, then screen with its instrument and cell | `P c - n` | ΔBIC −559.6, 7 testable |

  `P c - -` excludes `P n m a`. The reporter's reading: rows 2 and 3 screen
  cells that agree to 75 ppm, and what separates them is the shared profile
  fit (Rwp 0.170 against 0.087), so refining the cell inside the shared fit
  (option 4) is not enough on this pattern. Only a full Le Bail before the
  screen got the X-ray class with either background. The neutron arms were
  not re-run here. In the reporter's numbers they abstain at every arm
  except Le Bail first on 10-100°, which gives `P c - n` at ΔBIC −88. Their
  closing note bears on the default this WP chooses: the skill's recipe
  already runs a `profile_only` Le Bail, then discards it and screens the
  unrefined cell with the declared instrument. The neutron half's mechanism
  is WP-1542's, and its Inherited has it.

- **2026-10-09, from WP-1930 (PR #849).** `validation_plan` called
  without `two_theta_max` takes the 6° cap of `VALIDATION_SLACK_BOUNDS_DEG`,
  and on FAP its `profile` stage then never converges (max_iter at 100, 400 and
  2000 alike). `determine_extinction_symbol` always passes it, so only tests
  call it bare: `test_extinction_symbol.py`'s FAP 003-window test did, and now
  passes it; the corundum call near its line 738 still does, and passes.
  Making the argument required, or deriving it in the fit, was not measured.

- **2026-10-08, from WP-1546 (the 1.7.0 cut).** The "seen in passing"
  mismatch above is re-measured and bisected. The manual's numbers were the
  shipped protocol's until the WP-1112 merge (`e794a9e4`, #80, 2026-08-21):
  every commit before it gives shared-fit Rwp 0.1491 and ΔBIC −218, and every
  commit from it gives 0.2586 and −3434 over six testable positions. So 1.6.0
  already shipped the move. Over 5-150° the shared fit now reads 0.262, so its
  Rwp no longer separates the 20-90° arm from the wide one, where it was 0.149
  against 0.270. Whether WP-1112 corrected the shared fit or broke it is
  unexamined. The cut made `using/indexing.md` (about lines 1256-1268) and the
  skill's `references/diagnostics-indexing.md` quote what the code does, and
  dropped "fitted peaks a third too wide", which it could not re-measure. The
  bisect script is `m_bisect.py` in WP-1546's session scratchpad, which is not
  kept. Its method was the suite's `corundum_inputs` and
  `determine_extinction_symbol` over `T.CORUNDUM_RANGE` on each commit's `src`.
- **2026-10-13, from the issue triage (#931, in PR #932, from outside): a
  declared container halo is held at the caller's pre-fit, and the true class
  is refuted under it.** Checked against the tree at c3d0367: `_screen_plan`
  (`indexing/extinction.py:625`) frees only `instrument.background.*`, and the
  shared fit's `validation_plan` frees no `extra_components`, so a declared
  `HumpComponent` is never refit. The reporter's synthetic pyrochlore
  reproduces on all 21 runs. With the halo declared on (200), the hump comes
  back at 51-53 counts and 1.33-1.35° against a true 90 counts and 1.0°, and
  `F d - -` is refuted at (2,0,0) on 3 of 3 seeds, with no screen-level
  caution beyond `EXTINCTION_GROUPS_NOT_SEPARABLE`. PR #932 frees each
  background-aggregate component per class, with its FWHM floored at
  `HUMP_MIN_WIDTH_MULT` × the instrument FWHM inside the screen only. Applied
  in-process on the same tree, it returns `F d - -` on 3 of 3 seeds, and both
  positive controls still refute. The width floor is load-bearing at lab
  resolution: without it the freed hump absorbs a real 0.1° line and accepts
  `F d - -`. The PR's claim and the issue agree. Its CI was green and it
  carried a merge conflict on 2026-10-13. The undeclared-halo half (a changed
  null model for the absence test) stays open under the PR and sits inside
  this WP's Non-goal on loosening the absence test (WP-1077).

- 2026-10-26 issue triage: #1172 (from @mustachefeeling, found while building PR #1170):
  with the default `refine_cell=True`, corundum started at ×0.995 returns `R - - -`
  confidently, the gate silent (`reference_rwp_net` 0.194). Checked against the tree at
  c0e32ab29 (`[dev]`, macOS arm64): reproduced to the issue's digits. ×0.994 and ×0.995
  return `R - - -`; ×0.99, ×0.993, ×0.996-×1.00 return `R - c -`, every refined cell within
  0.01 % of the certified one. The refuting position is (3,0,3) at 72.004°, 1 of 6
  testable. Σ(obs − calc) over its window against the propagated σ reads 2.79-3.06 at every
  start and 2.90 at the certified one, against `k_sigma` 3.0. So this is not a cell-margin
  failure: one forbidden position holds a real excess sitting on the threshold, and the
  third decimal of the refined c decides which side. The certified-cell pin
  (`test_corundum_returns_the_class_its_certificate_names`) is 0.10 σ from failing. What
  the excess at 72.0° is (impurity, a Kβ or tube line) was not checked. Any fix touches the
  absence test, which this WP's Non-goals fence (loosening it, WP-1077), so it needs the
  maintainer's call first: a refutation resting only on positions within a margin of the
  threshold could mark the class "marginal" and abstain between the two, or the per-class
  bar could account for the number of testable positions (six windows at 3 σ each). Task 1's
  scan should report the decisive position's ratio beside each class, never the class alone.
  Probe scripts: the 2026-10-26 triage scratchpad, not kept.

## Non-goals

- Loosening the absence test or `_model_is_quiet` (WP-1077).
- The Bayesian posterior (v2 fence).
- How `index_pattern` ranks centring twins (WP-1449's supercell ordering).

## Tasks

- [ ] A failing row: the corundum fixture at ×1.0008 refutes `R - c -` today.
      Add the margin both ways at finer steps, and the same scan on FAP
      (`P 63 - -`) and the synthetic monoclinic, so the contract quotes a
      margin per pattern, not one number. *Rows pinned by PR #1178; the
      contract's prose waits for #1170 and #1140.*
- [x] Maintainer decision on point 1, recorded here: document only; refine
      the cell in the shared fit; a caution (code name settled at review);
      or a combination. *Decided 2026-10-06 on PR #747: document the
      contract and add `refine_cell=True` as an option, default unchanged;
      the caution is not decided.*
- [x] Land it. If the shared fit changes, the FAP, NAC and corundum rows of
      `tests/test_extinction_symbol.py` must keep their classes.
- [ ] Maintainer decision on point 2: a new caveat or screen diagnostic for a
      centring twin in the list (not a wider `bravais_ambiguous`), screening
      both, or refusing to name a centring. Then land it.
- [x] Manual Part 1, § The extinction symbol: the contract, and the corundum
      numbers re-measured.
- [ ] Skill: `references/diagnostics-indexing.md`'s recipe screens the
      Le Bail-refined cell (or states the contract), inside
      `tests/skill_caps.py`'s budget; a diagnostic code adds its row.
- [x] Tests, with obs/calc/diff PNGs to `tests/output/`. *PR #1178.*
- [ ] The default's confident misses (PR #1178's four strict xfails). *Ruled
      2026-10-26: (c).* Screen again at the prefit's cell, held, from the
      declared instrument, and report a finding when the two return different
      decisive classes; a held screen with no decisive class is recorded, not
      flagged, or PbSO₄'s eleven rows raise false alarms. On a disagreement
      the answer carries both rankings and picks neither. Measure (b) (carry
      the cell and background, refit widths and zero) on the same scan, and
      build it too only if it fixes rows (c) can only flag. Corundum ×0.985
      and the monoclinic ×0.9975 stay strict xfails: the prefit's cell is off.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction_symbol.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_skill.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The corundum fixture at ×1.0008 either returns `R - c -` or reports a finding
that names the cell. The certified-cell, FAP and NAC rows keep their classes.
A hexagonal P candidate for corundum's metric says that the R twin's groups
are out of its reach.

## References

- Madsen, I. C. et al. (2001). *J. Appl. Cryst.* 34, 409 — the IUCr CPD QPA
  round robin, `tests/data/qarr/`.
- Markvardsen, A. J., David, W. I. F., Johnston, J. C. & Shankland, K. (2001).
  *Acta Cryst.* A57, 47-54 — cited in `extinction.py`. Not read in this
  triage.
- Issue #726; WP-1025 (the screen), WP-1077 (the neighbour-tail gate),
  WP-1449 (ranking on the screen).

## Handover log

- **2026-10-05** — created, from the 2026-10-05 issue triage (issue #726).
  Checked against the tree at 32ef5a6: on the suite's corundum fixture the
  certified class survives to ×1.0004 and is refuted from ×1.0006, and a P
  candidate reaches 45 groups with no R among them. No open WP owns it:
  WP-1510 (🔄, merged, every task landed) is the chemist's priors, WP-1511
  compares supplied cells by Le Bail and never screens a class, and WP-1447
  and WP-1542 are a ghost threshold and a Le Bail background. WP-1025, 1077,
  1449 and 1451, which built, gated and ranked the screen or share its word,
  are ✅. *Next:* task 1.
- **2026-10-07** — PR #747 (#726, point 1) merged from the reporter's fork
  as `2a1cb5a`. It was gated on `main` at `57aa2c1` plus #811, #788, #755
  and #770, the stack merging ahead of it, plus #747 (`3afc93e`; Linux,
  4 cores, `[dev,jax]`):
  - ruff is clean;
  - the fast suite gave 8796 passed, 118 skipped and 1 xfailed;
  - the slow tier, run in two halves, gave 287 passed, 9 skipped and
    1 failed. `test_pair_diagnostic_class.py::test_every_pair_on_a_solution_names_a_class_whose_rows_carry_it`
    fails identically on bare `57aa2c1`.

  After the merge, `main` is content-identical to `main` + #747 as tested.
  That tree differs from the gated one only by #814's WP-1911 entry, and
  `test_docs_consistency` and `test_skill` pass on it.
  - **What landed.**
    - `determine_extinction_symbol(..., refine_cell=True)` inserts a `cell`
      stage after the shift and before the widths of the shared absence-free
      fit. It then screens every class, the reference included, at that
      refined cell, so the classes still differ only in their reflection
      sets. `ExtinctionScreen.cell` is the refined cell.
    - The default `False` screens exactly as before.
    - `docs/manual/using/indexing.md` states the contract: the screen holds
      the candidate's cell.
    - The skill's `EXTINCTION_FORBIDDEN_INTENSITY` row says a held cell off
      by about 10⁻³ refutes the true class, and names the remedy.
    - `tests/test_extinction_refine_cell.py` pins both arms on the corundum
      fixture at ×1.0012:
      - held: the class is refuted;
      - refined: `R - c -` with `R 3 c:H` and `R -3 c:H`, at a cell nearer
        the certificate.
  - **What it deliberately does not do.**
    - The default is unchanged, so this WP's acceptance (×1.0008 returns
      `R - c -` or names the cell) still fails unless the caller opts in.
      "Land it" stays open on that decision.
    - The `CELL_OFFSET_REFUTES_CLASS` caution and point 2 (the centring
      twin) are not in it.
    - Task 1's per-pattern margins (FAP, the synthetic monoclinic) were not
      measured.
    - The manual's corundum numbers in that section were not re-measured.
  - **Gotchas, from review.**
    - The docstring first said ×1.0008, the reporter's figure from another
      instrument. It now says ×1.0012, the factor the test measures. This
      WP's table has the flip from ×1.0006 on the suite's fixture.
    - `api.md` sat 21 bytes under its cap, so the function's summary line
      was shortened to fit the new keyword.
    - The new test builds the corundum inputs outside
      `test_extinction_symbol.py`'s `extinction-symbol` xdist group, about
      5 s. Give it the group if a second test joins.
  - *Next:* the maintainer decision on the default (opting in moves the
    FAP, NAC and corundum rows only for callers who opt in), then task 1's
    margins and point 2.
- **2026-10-14** — from the PR review (PR #939): the default is decided.
  @yue-here takes the flip: the screen refines the cell by default, through
  #939's cell-free `profile_only` Le Bail prefit, with a gate on the reference
  fit (Toby 2006's background-subtracted R_wp, the net taken against the
  picker's envelope). The condition is this WP's acceptance case pinned before
  merge, corundum at ×1.0008 returning `R - c -`, with the margin either side.
  The PR tests ×1.0012, and `profile_only`'s cell stage has no window slack
  where the in-plan stage it removes had `validation_plan`'s. Round 1 at
  `38ca3b8c` also asks for four fixes: a late cancel erases the gate's
  `"unreliable"`, the prefit takes no cancel token, `auto_background` is
  called without the caller's kind, and an empty screen drops
  `EXTINCTION_SCREEN_UNRELIABLE`. Point 2 and the caution stay undecided.
  *Next:* #939's round 2.
- **2026-10-25** — PR #939 (by @mustachefeeling) merged at round 5 as
  `fe4cbcc3`, carrying #941's and #993's synced heads. `determine_extinction_symbol`
  refines the cell by default, in a cell-free `profile_only` Le Bail that runs
  without the closing stage, as the screen's other fits do. It abstains with
  `EXTINCTION_SCREEN_UNRELIABLE` when the reference fit's background-subtracted
  Rwp passes `REFERENCE_NET_RWP_MAX` (1/√2, tier 3, ruled 2026-10-21). The
  pinned classes held (synthetic P 2₁/c, FAP, NAC, certified corundum), with
  their ΔBIC moved. The PbSO₄ X-ray histogram at a 0.1-0.2 % cell went from
  an abstention to `P c - n`. The manual's `reference/extinction.md` states the
  contract with the corundum numbers. The review's sync commit `9f8e8f21`
  moved the notes to `docs/releases/1.11.0.md`, put the thresholds note under
  C3's 1.12, and added schema 0.60's history line for `ExtinctionScreen.prefit_rwp`
  and `.reference_rwp_net`. Gate: as WP-1956's 2026-10-25 entry. Open: the
  margin scan (task 1), point 2, the skill recipe, and the PNGs. Round 4's
  follow-ups stand: print √(N/(N+S)) beside `reference_rwp_net`, and show the
  gate firing on a real family. *Next:* task 1's margin scan, then point 2.
- **2026-10-26** — PR #1178 (task 1's scan and the PNGs, by @mustachefeeling)
  merged as `7b5181bb`. `tests/test_extinction_margin.py` pins the margin per
  pattern at both edges, held and default: corundum ×0.998-1.0004 held,
  ×0.9975-1.015 default; FAP ×0.9996-1.001 held, ×1.000-1.005 default;
  synthetic P 2₁/c ×0.9998-1.0002 held, ×0.9995-1.001 default. The scans
  were identical on macOS arm64 and Linux x86_64. Four **strict xfails** pin
  the default returning a wrong class confidently: corundum ×0.995
  (`R - - -`), FAP ×1.0075 (`P - - -`), and the monoclinic ×0.999 and
  ×1.002 (`P 1 - 1`). A control row holds the prefit's own cell, screens again
  from the declared instrument, and gets the true class at each. So what
  refutes the class is what the prefit carries besides the cell (its widths,
  zero and seeded background). Carrying the cell alone costs PbSO₄'s X-ray
  `P c - n`. Each row draws the true class's own screen fit, through a spy
  on `_fit_class`, whole and zoomed on the first refuting position. The
  corundum ×0.995 zoom shows the prefit's profile overshooting the 70.4° line.
  The contract's prose waits for #1170 and #1140, which edit the same two
  files. The PR asks which way the default goes: (a) accept the misses,
  (b) carry the cell and background but refit widths and zero, or (c) report
  a finding when the default and the held-at-the-prefit's-cell answers
  disagree. That question went to the maintainer the same day. Gated in a
  stack with #1179 (counts in WP-1968's entry of today). *Next:* the
  maintainer's answer on the default, then the contract's prose after #1170
  and #1140, point 2, and the skill recipe.
- **2026-10-26 (later)** — The maintainer answered #1178's question: (c),
  with (b) measured beside it. The indexing rulebook's governing rule is
  never one confident answer, with confidence from methods that fail
  differently agreeing, so (a) would leave a standing breach and (c) is the
  rulebook's own device. (b) changes a default and stays one screen. Posted
  on #1178; the task above carries the detail. *Next:* that task, then the
  contract's prose after #1170 and #1140, point 2, and the skill recipe.
