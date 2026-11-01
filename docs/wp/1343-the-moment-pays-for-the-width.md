# WP-1343 — the magnetic peaks are broader, and the moment pays for it

Milestone: magnetic · Status: 🔄 2026-10-25 — 12 of 12 tasks done; PR #1111 merged (the synthetic k = 0 case, a wide esd and the path named); open: the maintainer's choice of fix for `MAGNETIC_WIDTH_UNMODELLED`'s silence where every magnetic reflection is also nuclear (a strict xfail holds the case)
Depends on: 1327 (the moment, the magnetic |F_⊥|², the shared scale);
1326 soft (the satellites that make the term identifiable)
Priority: P2 2026-10-05 — was P3: `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` fires on a warm refit under `fit` (#729), a flag firing wrongly whose workaround is `run_stage`

## Goal

A phase's magnetic contribution is drawn with its own extra Lorentzian
width, refined as a term of that phase rather than of a second one, so a
specimen whose magnetic order is coherent over a shorter length than its
crystallites reports a moment the profile has not biased low. The report
says whether the width was measurable at all, and a plan that frees it
beside the moment from a cold start is named before it is run.

## Context

Fifth rung of the magnetic scattering track (ROADMAP § Unscheduled), opened
2026-09-08 from issue #277. It cannot start before 1327: there is no moment
to bias, no magnetic |F_⊥|² to draw twice, and no magnetic-only reflection
to measure a width on until that WP lands.

### This is 1327's price, not an extra

1327 took the site-attribute shape — a moment on an atom of the *nuclear*
phase, one `Phase.scale` for both contributions, one reflection list — and
rejected FullProf's separate magnetic phase for two measured reasons: it
doubles the specimen's mass in `phase_zmv` unless excluded by hand, and it
needs two scale factors kept equal.

The rejection has a price, and this WP is the price. A separate magnetic
phase also carries **its own size and microstrain terms**, and that is what
a GSAS-II or FullProf user reaches for when the magnetic peaks come out
broader than the nuclear ones. With one phase and one profile, rietx cannot
say it. The residual under a magnetic peak that is broader than the
calculated one then has exactly one way down: shrink the moment until the
narrow calculated peak's *height* matches the broad observed peak's. |F_m|²
∝ m², the peak is at the right position with the right shape, χ² falls, the
fit converges, and the moment is low by the ratio of the two widths with
nothing in the report saying so.

**The physics.** A crystallite's magnetic order need not be coherent across
the whole crystallite: antiphase and domain-wall boundaries, an incompletely
grown order parameter near T_N, and chemical disorder that couples to the
exchange all cut the magnetic coherence length below the structural one,
while leaving the nuclear peaks untouched. The broadening that follows is
Scherrer's, applied to the magnetic domain: ≈ Kλ/(L cos θ), the same 1/cos θ
law `caglioti.lorentzian_fwhm` already carries for `lor_size`, with L the
magnetic coherence length. A magnetic order parameter that varies across the
specimen adds the tan θ law instead. So the two terms this WP wants are the
Lorentzian pair the package already has, applied to one component of the
intensity rather than to the peak.

### What issue #277 offers, and what of it could be checked

The issue is right about the shape and its evidence cannot be reproduced
here. Both halves matter to whoever picks this up.

**Unverifiable as stated.** The measured table (POWGEN banks 2 and 4 on
Mn₃O₄, observed/calculated FWHM ratios of 1.28–1.50 on the magnetic
reflections against 1.00 on a nuclear one; Mn1 at 3.25 μ_B against GSAS-II's
4.92; a magnetic-to-nuclear (110) ratio of 0.251 against 0.231) cannot have
been produced by any rietx that exists. There is no moment on main —
`Atom.moment`, `Phase.magnetic_symmetry` and the magnetic structure factor
are all 1327's unstarted tasks — so nothing could be "written into the rietx
phase and held". POWGEN is a **time-of-flight** instrument, and neutron TOF
is still inside the v2 fence (ROADMAP § v2+; 1327 § Non-goals repeats it):
`model/forward_tof.py`, which the issue's "where it touches" names, does not
exist and is not this track's to write. `MomentEvidence` and `T-3c`, both
cited as existing, appear nowhere in the repository. Whatever produced those
numbers, it was not this package, and none of them may be used as a
tolerance or a target here.

**Withdrawn by its own author.** The issue's follow-up comment retracts most
of the Mn₃O₄ signature: below T_N that specimen is two lattices, tetragonal
I4₁/amd and orthorhombic Fddd in near-equal fractions with an a–b splitting
of +0.628 % (Kemei et al. 2014), so the parent-forbidden (110) is a
(200)/(020) pair in the ordered fraction and most of the "magnetic peaks are
broader" width excess is a **phase-coexistence splitting** rietx can already
state as two nuclear phases. That is a correct diagnosis and it removes the
primary dataset from the argument.

**What survives, and it is enough.** The mechanism is standard practice in
every code that refines a magnetic structure, and 1327's shape closes the
route those codes use. That is a design gap, argued from the shape of our
own model, and it does not need the issue's numbers. The second case the
issue names, Ba₂FeSbSe₅ on G4.1 (Maier, Gaultois et al. 2021), is
**constant-wavelength** and therefore in scope, and the comment argues it is
the clean one: a single lattice, k = (½, 0, ½), with a smooth
magnetostriction below T_N and no second phase to split the magnetic peaks.
The data is not vendored and its licence is not checked; getting it is a
task below, not an assumption.

### The seams

- **`model/forward.py::phase_peaks`** is where the split has to survive.
  Today the per-line intensity is one array: `base = scale · mult · f2`,
  then March-Dollase, extinction, Lp, specimen absorption and roughness
  multiply it. 1327 adds the magnetic term to `f2`. This WP needs the two
  contributions **separable at that point** — `f2` and `f2_mag` as two
  arrays, one `base` each — with every factor after them (all of PO, Lp,
  absorption, extinction, roughness) multiplying both exactly as it does
  the single array today. Nothing in that chain is a function of which
  contribution it multiplies, so the change is a second pass, not a second
  correction chain. 1327's `### Inherited` carries the ask (written
  2026-09-08): a 1327 that folds the magnetic term into `f2` irreversibly
  makes this WP a rewrite of its structure-factor path rather than an
  extension.
- **`_width_block` / `caglioti.lorentzian_fwhm`** answer "convolved with the
  extra magnetic width" without any convolution machinery. The package's
  composition law is already the right one (root CLAUDE.md: Gaussian
  variances add, Lorentzian FWHMs add), so the magnetic component's widths
  are `x_size + magnetic_lor_size` and `y_strain + magnetic_lor_strain` fed
  to the same function. The width block gains a second output, not a second
  law.
- **The frozen discreteness is where the real work is.** `cp.win[il, k]` and
  `cp.fcj_n[il, k]` are per (line, reflection) and frozen at stage compile.
  A component that is *broader* needs its own window range and its own FCJ
  node count, so `CompiledPhase` grows a second family of frozen arrays and
  `BatchLayout` gathers a second block of rows. Sizing them at compile means
  `compile_model` must see the magnetic widths the stage can reach, which is
  `moving_paths`, never `free_paths` — the rule root CLAUDE.md states for
  FCJ node sizing, and the same one that gates `skip_extinction`.
- **The off state is a structural skip, which is what makes bit-identity
  cheap.** With both magnetic width terms at zero and outside `moving_paths`
  the two components have identical widths, so the second family is not
  built at all and the magnetic intensity is added into `f2` exactly as
  1327 leaves it. Bit-identity then holds because the code path is the same
  one, not because two floats happened to agree.
  `CompiledPhase.skip_extinction` is the precedent to copy, including its
  `moving_paths` gate — and including that gate's own limit:
  `gate_off_states` is `moving_paths is not None`, so a caller that makes
  no claim (public `compile_model`, plots, replay) builds the second family
  anyway. On that path bit-identity is *only* two floats agreeing, which is
  the weaker statement, so the bit-identity task has to assert both paths
  and say which is which.
- **The Jacobian.** Two new derivative paths. `_make_jacobian` dispatches on
  the free path's *name*, so they take the whole-model FD column until a
  branch claims them; when a branch lands it declares its `_column_extras`
  reach and the `test_cross_backend.py` configs grow a row, per root
  CLAUDE.md. The traced twin in `backend/traced.py` carries the term or
  declines by name.
- **`help.py`, `capabilities()`, `SCHEMA_VERSION`.** Two new parameter names
  mean two `help.py` entries with unit, default and typical range —
  `test_help.py` crosses that vocabulary both ways, so the entries are not
  optional. The schema bump carries its one-sentence comment.

### Decisions taken here, with what was rejected

**Two terms, both Lorentzian.** `Phase.magnetic_lor_size` (deg, 1/cos θ) and
`Phase.magnetic_lor_strain` (deg, tan θ), both `min = 0.0` under softplus,
both defaulting to zero. Zero **is** the off state here — no extra magnetic
broadening — and the forward model does not divide by either, so root
CLAUDE.md's softplus rule says `min = 0.0` is safe and no floor like
`MARCH_R_MIN` is wanted. The *conversion* to a coherence length does divide, and
`model/microstructure.py` already answers a zero coefficient by returning
no value at all — `_reading`'s first branch, `unavailable="at_zero"` — not
an infinite length. That is `lor_size`'s existing case and not a new one.

*Rejected: the Gaussian partners as well.* The issue offers
`magnetic_gauss_size`/`_strain` "if the existing pattern is kept". A field
nothing frees and no plan reaches is WP-1076's exact trap — a declared name
is a claim, and an absent writer fails no test. Magnetic coherence-length
broadening is Lorentzian in shape; the Gaussian partners land when a dataset
measurably needs them and can be freed against it, not for symmetry.

*Rejected: a separate magnetic scale.* 1327 refused it and this WP does not
reopen it. A second scale reaches the same fit through the moment's own
degeneracy and returns a wrong number confidently, which is the failure this
WP exists to close.

*Rejected: a magnetic lattice offset.* The issue's comment raises it for a
later dataset. It is a different freedom (the magnetic peaks in the *wrong
place*, not the wrong width), it is what the Mn₃O₄ coexistence case actually
needs, and rietx already answers that one with two nuclear phases. Fenced
here by name so it is not smuggled in.

### When the term is measurable, and when it is not

The two width terms enter only the magnetic component, so they are
identifiable exactly to the extent that the magnetic/nuclear intensity ratio
**differs across reflections**. Three regimes, and the report has to
distinguish them rather than return a number for all three:

- **k ≠ 0.** The magnetic supercell carries parent-forbidden reflections
  that are magnetic-only. Those measure the width directly, and this is the
  case the WP is written for.
- **k = 0, and every magnetic reflection is also nuclear.** The two
  components sit at the same positions with intensity ratios set by the
  moment. The width is then weakly determined at best, and on a collinear
  structure whose magnetic and nuclear intensities happen to track each
  other it is not determined at all.
- **Paramagnetic.** No magnetic component, so the column is identically
  flat, exactly as 1327's moment modulus is at its floor.

The package already has the machinery for all three, and it is used rather
than duplicated: an equilibrated normal matrix, a gradient-free column that
`ParameterTable.unmeasured_rows` names, and an esd that is **absent rather
than zero**. A magnetic width that comes back unmeasured is reported that
way; it is never quoted, and it never rides to a bound. 1301's rule applies
one rank down as well — a flat direction is held for the stage, not bounded.

### The diagnostic: read the residual's shape, do not measure a width

Issue #277 asks for observed FWHM ÷ calculated FWHM per reflection. The
package cannot compute the numerator: there is no observed-peak-width
measurement in it, and the one that is coming is v1.4's `fit_peaks`
(WP-1101), which this WP must not wait on or duplicate.

The signature is available without it. A calculated peak that is too narrow
under a broad observed one leaves a **sign-structured** residual at the
reflection's position: negative in the middle, positive in both tails. The
low moment the fit has already taken does not erase it, it only moves where
the two cross — least squares trades centre against tails and cannot make
both zero with the wrong width — so the statistic is the centre-versus-tails
sign split of the weighted residual inside the Layer-1 validity radius
(0.4 · FWHM, already the package's constant), evaluated at the
**magnetic-only** reflections and compared against the same statistic at the
**nuclear-only** ones. Differencing the two is what makes it safe: a wrong
instrument profile, a wrong `lor_size`, a wrong background all move both
sets together and cancel, and only a component-specific width difference
survives.

`MAGNETIC_WIDTH_UNMODELLED` fires when both magnetic width terms are held at
zero and that differential split exceeds its own noise. The message names
the reflections it read, says what the term would do, and — the part that
makes it actionable — says which way the moment would move. It never quotes
an Rwp comparison as its evidence (root CLAUDE.md), and it is not fired by a
trial solve: it is read off the converged residual the report already holds.

When the terms *are* freed, the evidence is the trajectory, not a
diagnostic: the stage that freed them is a rung on `stage_reports_`, so the
moment before and after is a record the plan already produces (WP-1058, and
WP-1073's rule that a correction's evidence is a rung, never the endpoint).

### Staging: this term and the moment want the same thing

Both lower the calculated peak height, so freed together from a cold start
they trade against each other and the plan converges on whichever pair the
first step happened to like. The order is the one the package already
prescribes for nuclear size/strain against scale: **moment first with the
widths held at zero, then the widths with the moment held, then both
together.** The issue quotes the maintainer on it — "we are careful not to
open up everything right away" — and it is the same discipline
`mccusker_structural` encodes.

A stage list that frees `phases.*.magnetic_lor_*` alongside
`phases.*.atoms.*.moment.dof.*` before either has converged is reported.
There is no stage-list check on main to extend (grepped 2026-09-08: no
`STAGE_FREES_*` code exists), so this WP either adds the first one or the
rule goes in the skill's magnetic reference as a written ordering row. Take
the cheaper of the two at the time; the skill row is required either way.

### Inherited

- **2026-10-12, from [1929](1929-an-esd-follows-where-the-solver-stopped-beside-a-flat-column.md):
  the moment rung reads moduli by name and skips a tied one.**
  `refine._moment_rung` keeps only untied `dof0` entries. A modulus a
  `vars.X` drives is tied, and the variable is no moment path, so that site
  has no row and `MAGNETIC_WIDTH_MOVED_MOMENT` has nothing to compare. Two
  more reads take freed paths by name: the gate in `fit` that decides whether
  to build the rung, and the `moments` set of
  `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT`. A stage that frees a moment only
  through a variable is invisible to both. `_MAGNETIC_WIDTH_PATH` has the same
  shape for a width a variable drives. The fix is `ParameterTable.column_reach`,
  with one rung row per column so a tie still counts once. Found by reading,
  not run.

- **2026-10-05, from the issue triage (issue #729):
  `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` fires on a warm refit through
  `fit`, the third step its own docstring calls fine.**
  `_stage_order_diagnostics` (`refine.py:5281`) counts as already freed only
  `table.free_paths`. `run_stage` passes the working state's free set, but
  `fit` passes `_prepare_table(restore=False)` (`refine.py:4068`), with
  everything held. So under `fit` a single stage freeing the moment and a
  width always reads as a cold start, and the message says "from a cold
  start ... Neither number that comes back is a measurement of its own
  quantity". *Checked at `32ef5a6`* with the issue's script (`_mnf2`, Poisson,
  seed 3): `plan="magnetic_width"` reports nothing; the same stage refit
  warm fires, both on a new `Refinement` built from `fitted_structure` and on
  the same converged one; `run_stage` of that stage on the converged one is
  silent. The moment stays 4.58505 ± 0.01907 μB and both widths stay 0.0, so
  nothing traded. The check needs a discriminator it can compute, or a message
  that states the condition instead of asserting a cold start (root CLAUDE.md,
  WP-1118's rule). Which one is the maintainer's: the Refinement's own last
  fit can show "warm" for the same object, and nothing can for a fresh one.

- **2026-09-28, from [1338](1338-the-skills-own-gates.md): `references/diagnostics.md` is closed to growth.**
  Every skill file now has a ceiling and a budget below it
  (`tests/skill_caps.py`), and the budget fails a change that grows a file
  past it. `diagnostics.md` (35 111 B) and `diagnostics-indexing.md`
  (35 124 B) sit over their 34 600 B budget, so a row this WP adds there
  comes with an equal cut in the same change, or goes to the file a reader
  meets the code in (the criterion in the `REFERENCE_MAX_BYTES` comment).
  CI's lint job reports each changed file's headroom on the draft PR.

- **2026-09-15, from the issue triage (issue #287): this WP's four codes go
  to `references/magnetic.md`, never to `diagnostics.md`.** The ruling of
  2026-09-09 gives the magnetic family (1326–1329 and this WP) one gated
  reference file numbered `2b`, carrying codes, strategy and traps, with a
  one-line pointer from § 7. `diagnostics.md` has 20 B free on this tree
  and the family never enters it. 1327's Inherited holds the file's shape.
  If this WP lands before 1327 it opens the file with the pinned header.
- **2026-10-13, from the issue triage (#277): acceptance 4 falls back to a
  synthetic case.** Posted 2026-10-12: the Ba₂FeSbSe₅ G4.1 patterns cannot be
  released (the raw data were not published with Phys. Rev. B 103, 054115),
  so the 4.13(4) μ_B target lapses with them. The reporter will open a
  tests-only PR against this WP: a seeded k ≠ 0 CW pattern from rietx's
  forward model with a planted `magnetic_lor_size`, a planted moment and
  Poisson noise; a nuclear-only control on which `MAGNETIC_WIDTH_UNMODELLED`
  stays silent; and the acceptance that width and moment are recovered within
  their esds, with the moment's bias when the term is left out. Data drawn
  from the model being fitted tests recovery and the diagnostic, not the
  model, and the acceptance should say so. Asked of them: build the child
  from a published structure and name it in the test.

- **2026-10-26 issue triage (#1082's reproduction): `MAGNETIC_WIDTH_UNMODELLED`
  fires on a moment no stage refined.** Checked against the tree at c0e32ab29:
  on #1081's synthetic k = (0,0,½) child, simulated with no magnetic
  broadening, a moment held 20 % high (3.6 against 3.0 μ_B) under
  `mccusker_default` and `mccusker_structural` makes the magnetic peaks too
  tall at their centres, and the diagnostic reads it as the width signature:
  "fitted by peaks that are too narrow, so the refined moment is biased low".
  The moment was not refined and is biased high. The centre-versus-tails test
  assumes the moment was free; where it was held, the same residual shape is
  the moment's error. #1089's reporter measured the same while writing #1087:
  with the moment held 10-20 % high it fires on 7 of 8 sharp arms.

- **2026-10-26 issue triage: #1089, when the magnetic width is freed; the
  reporter's final answer keeps the tree's behaviour and changes one text.**
  Checked against the tree at c0e32ab29: no default plan frees
  `magnetic_lor_*` (only `plan="magnetic_width"` does) and nothing consults
  `MAGNETIC_WIDTH_UNMODELLED`. The reporter measured three real families
  (Ba₂FeSbSe₅ G4.1, Cr₂WO₆ HB-2A, LaMnO₃ BT-1): the trigger is silent on all six
  patterns before and after #1087; on Ba₂FeSbSe₅ freeing the width moved the
  moment by about 3 esd while ΔBIC was weak or against, and after tying the
  child Biso and refitting the background (#1073) the width is rejected at every
  temperature (ΔBIC −5.8 to −9.0 at N/f²). The moved moment came from Lorentzian
  tails the 9.35° line does not have; the line's misfit is a low-angle centroid
  shift, now WP-2056's (#1090). Their revised ask: no default frees the width,
  no default reads the trigger, and the three texts that say to quote the
  freed-width moment change (`help.py:3026-3034`,
  `report/magnetic.py:637-640`, `references/magnetic.md:60`). The issue's
  first-pass trigger-first rule is withdrawn by its author. Also measured: the
  trigger fires on a moment held too large (the reporter's 7 of 8 sharp arms at
  10-20 % high; this round's #1082 reproduction at 20 % high under
  `mccusker_default`, "biased low" on data with no magnetic broadening), so it is
  read only after a stage that freed the moment. The four width codes are
  `unaudited` (`_audit.py:720-722`); the reporter's proposed tiers (the ΔBIC
  test tier 2 statistic, tier 3 action; width after moment tier 2, from
  FullProf's manual order and Rodríguez-Carvajal 1993) go to whichever of this
  WP and WP-2004 tiers `report/magnetic.py` first. Question B (cell free in the
  moment stages): no change to `SOLVE_STAGE_PATHS`, since freeing the cell there
  moved no moment by more than 0.1 esd on three families, a ramp and two
  above-T_N starts.

## Non-goals

- **Neutron TOF**, and with it the whole POWGEN/Mn₃O₄ case the issue leads
  with. The v2 fence stands (ROADMAP § v2+; 1327 § Non-goals). Nothing in
  this WP touches a TOF width law, because there is none.
- **Anisotropic magnetic broadening** (an hkl-dependent magnetic width, the
  Stephens shape one component over) and a separate magnetic peak *shape*.
  Both follow only when the isotropic pair has shown what it recovers.
- **A magnetic lattice offset or magnetostriction** as a refinable freedom;
  see the rejection above.
- **A second scale factor**, or anything that reintroduces the separate
  magnetic phase 1327 rejected.
- Everything 1327 fences: incommensurate structures, polarised neutrons,
  single-crystal data, magnetic X-ray scattering, terms beyond the dipole
  approximation.

## Tasks

- [x] Schema: `Phase.magnetic_lor_size` and `Phase.magnetic_lor_strain`
      (deg, `min = 0.0`, default 0.0), refused on a phase with no moment
      block; `SCHEMA_VERSION` bump with its one-sentence comment;
      `help.py` entries with unit, default and typical range.
- [x] Forward model: `f2`/`f2_mag` kept separable through `phase_peaks`, the
      second width from `_width_block` via the existing addition law, the
      second frozen window and FCJ family on `CompiledPhase`, and the
      structural skip at the off state gated on `moving_paths`.
- [x] Bit-identity: every shipped fixture, and 1327's own magnetic
      acceptance, unchanged with the new fields at their default — asserted
      as the *same code path*, not as two floats agreeing.
- [x] Jacobian: FD first, then the analytic branch with its `_column_extras`
      reach declared, the `test_cross_backend.py` rows that cover it, the
      traced twin.
- [x] Multi-histogram: rows in `params.multi.SIZE_LAMBDA_POWER` for the new
      size term (λ¹, as `lor_size`), or the joint fit shares a coefficient
      that is not one number across wavelengths (WP-1131's invariant), with
      the two-histogram test that catches it.
- [x] Identifiability: the unmeasured path named rather than quoted, on all
      three regimes above; a synthetic k = 0 case asserted to come back with
      no esd rather than a small one.
- [x] `MAGNETIC_WIDTH_UNMODELLED`: the differential centre-versus-tails
      statistic on magnetic-only against nuclear-only reflections, its
      message naming the reflections and the direction the moment would
      move, and its row in `references/diagnostics.md`
      (`test_docs_consistency.py` looks for it there).
- [x] Staging: the three-step order in the magnetic plan preset, and the
      report for a stage list that frees the widths beside the moment —
      either the first `STAGE_FREES_*` check or a written skill row, decided
      on cost at the time.
- [x] Manual: Part 2 gains the two-component draw with its *Source* line
      beside 1327's structure factor; Part 1 gains the paragraph in the
      magnetic chapter.
- [x] Skill: rows in the magnetic `references/` file 1327 opens — the
      turn-on order, what the diagnostic means, and when the width is not
      measurable. Paid for by a named cut if the body moves at all.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`, magnetic-only
      reflections zoomed.
- [x] `MAGNETIC_WIDTH_UNMODELLED` divides its statistic by a pooled scatter
      that the misfit itself inflates, so its evidence shrinks as the problem
      grows. *Decided 2026-10-15 (from PR #943): a task here, with no change
      in #943.* On #943's synthetic CrSBr (k = (0, 0, ½), 5 000 counts on the
      strongest magnetic line, seed 1343), the width held at zero returns the
      moment 25 % low (2.317 against 3.09 μ_B) while the diagnostic reads
      z = 2.99 against its 3.0 bar, with the scatter at s = 2.57 against about
      1 for a good fit. Five other seeds at 5 000 counts fire 4 of 5, twice
      the counts 5 of 6, four times 6 of 6. Measure a noise estimate the
      misfit cannot inflate, keep the nuclear-only control silent, and turn
      #943's A2 arm from an expected failure into a pass.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_magnetic.py tests/test_cross_backend.py -q
.venv/bin/python -m ruff check src tests examples
```

1. **Synthetic round trip.** A CW neutron pattern generated with a known
   `magnetic_lor_size` and a known moment refines back to both within 1σ.
   The same pattern refined *without* the term returns the moment low by
   more than its esd, and `MAGNETIC_WIDTH_UNMODELLED` fires naming the
   magnetic-only reflections. Both halves are the acceptance; the second one
   is what says the diagnostic is not decorative.
2. **Bit-identity.** Every fixture pinned before this WP, and 1327's Cr₂WO₆
   and LaMnO₃ acceptance, bit-identical with the fields at their default.
   `qpa.weight_fractions` untouched, asserted.
3. **1327's own datasets, reported either way.** With the term freed on
   Cr₂WO₆ (HB-2A, k = 0) and LaMnO₃ (BT-1, k = 0), report whether it is
   separable at all. Both are k = 0, so the expected answer is *not
   separable*, returned as an absent esd and a named unmeasured row — a
   null result that the acceptance records rather than hides. If either
   *is* separable, that is the more interesting outcome and it is measured,
   not assumed.
4. **A k ≠ 0 CW dataset**, which is the case the term is for. Ba₂FeSbSe₅ at
   1.5 K on G4.1 is the candidate the issue names: the strongest magnetic
   peak's height ratio and the fitted moment against the paper's
   4.13(4) μ_B, before and after — a number quoted here **through the
   issue**, so check it against the paper itself when the paper arrives,
   before it is used as a target. **Ask for the data and check its licence
   before vendoring** (memory: the maintainer supplies literature and data
   on request; `tests/data/README.md`'s per-file fence applies). If it
   cannot be obtained, a synthetic k ≠ 0 supercell built from a published
   structure stands in and the acceptance says which was used.
5. **Staging.** Whichever of the task's two routes was taken is what this
   asserts: with the `STAGE_FREES_*` check, a plan that frees the widths
   beside the moment from a cold start is reported by name before it runs;
   with the skill row, `tests/test_skill.py` sees the ordering row and the
   preset's three-step order is asserted directly.
6. **Cross-backend.** The new derivative paths appear as rows in
   `test_cross_backend.py`, agreeing per column.

## References

- Issue [#277](https://github.com/yue-here/rietx/issues/277) and its
  follow-up comment, which retracts most of its own Mn₃O₄ evidence.
- Kemei, M. C., Harada, J. K., Seshadri, R. & Suchomel, M. R. (2014).
  *Phys. Rev. B* **90**, 064418 — Mn₃O₄ tetragonal/orthorhombic coexistence
  below T_N, the +0.628 % a–b splitting. **Not in the corpus; ask.**
- Maier, S., Gaultois, M. W. et al. (2021). *Phys. Rev. B* **103**, 054115 —
  Ba₂FeSbSe₅, k = (½, 0, ½), the 4.13(4) μ_B this WP's item 4 targets.
  **Not in the corpus; ask.**
- Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
  manual (in the corpus) is where the separate magnetic phase carries its
  own size and strain. Concepts only; the GPL fence in `ATTRIBUTION.md`
  applies, and to GSAS-II's derived magnetic phase equally.
- Scherrer's law as the package already carries it:
  `model/profiles/caglioti.py` and its cited sources; the magnetic reading
  substitutes the magnetic coherence length for the crystallite size.
- [1326](1326-satellites-without-a-moment.md),
  [1327](1327-magnetic-structure.md),
  [1328](1328-magnetic-interchange.md),
  [1329](1329-moment-in-a-series.md) — the track;
  [1301](1301-hold-unsupported-phase.md) the hold rule;
  [1131](1131-sample-broadening-is-a-specimen-property.md) the λ-power invariant
  the new size term joins; [1101](1101-standalone-peak-fitting.md) the
  observed-width measurement this WP deliberately does not wait on.

## Handover log

- **2026-10-25** — PR #1111 (outside contributor) merged as `942f8db4`. It
  adds `tests/test_magnetic_width_k_zero.py` and lands the last two Tasks rows:
  the identifiability row and the k = 0 half of the Tests + PNGs row. The k = 0
  case is CrSBr's ferromagnet along c (BNS 59.409, on the parent cell), on
  #943's specimen, instrument and counts. Along c, no reflection carrying at
  least 0.1 % of the strongest magnetic line is over 95 % magnetic, so it is
  the WP's second regime. The b-axis child is not, because its (0 0 1) is 97 %
  magnetic, and MnF₂ is the first regime. The identifiability row is met in
  #524's accepted form: a wide esd that covers the truth, with the path named,
  never a small esd. On the test draw the width came back 0.2030 ± 0.0729°
  against 0.1969 ± 0.0046° at k = ½, 15.8× wider. Over 30 scratch draws the
  esd was 0.062-0.081° and the pulls had s.d. 0.67. Each of five arms names
  exactly the widths under 3σ, both ways. New PNGs `crsbr_k000_{free,held}`
  with (1 0 1) and (0 2 1) zooms, since this regime has no magnetic-only line.
  *What the merge does not do*: it fixes nothing in the source. It records one
  defect as a strict xfail, `test_k0_held_the_report_names_the_missing_width`.
  With the width held at zero the k = 0 moment comes back 28.5 % low on the
  test draw (25 % mean, at least 8.1 esd over 30 draws), and
  `MAGNETIC_WIDTH_UNMODELLED` fires on 0 of 30. Its statistic differences
  magnetic-only against nuclear-only reflections, and this regime has no
  magnetic-only reflection. `_classified_reflections` keeps a row on
  `f_mag > 0.0`, so its magnetic-only set is five rows extinct to rounding
  (f_mag ~1e-30) and (1 1 2) at 0.03 % of the strongest line. Nothing in the
  report says the check could not be made. The PR ranks three fixes: report
  that the check had nothing to read; floor the classifier relative to the
  strongest magnetic line (a precondition, silent on its own); or a regime-2
  statistic on the most magnetic mixed reflections (new design). Which fix,
  if any, is the maintainer's call, asked on 2026-10-25.
  *Gate*: stacked with #1073 on tree `1923c693` (main `f9a983d7` + both PRs;
  macOS arm64, Python 3.12.10, `[dev,jax]`, nothing else running): the whole
  suite, slow tests included, 12 255 passed, 206 skipped, 43 xfailed in
  35 min. Main after the last merge (`4cfd4598`) is content-identical to that
  tree.
  *Cross-reference*: #1073, merged in the same stack, vendors the real
  Ba₂FeSbSe₅ G4.1 ramp, which acceptance 4 names as the better k ≠ 0 row. Its
  description reports that freeing both magnetic widths there costs BIC at 1.5,
  20, 40 and 50 K (ΔBIC −5.8 to −9.0), with the Biso tied per parent site. Its
  test does not free the widths. *Next*: the choice among the three fixes, then
  a Tasks row for it.
- **2026-10-21** — PR #1087 (outside contributor) merged as `f0c7285b`. It
  lands the last Tasks row. `MAGNETIC_WIDTH_UNMODELLED` now divides its
  statistic by the weighted residual's s.d. over the nuclear-only channels it
  read, where it used the s.d. over the magnetic-only channels too. The
  docstring grounds this in the F test's rule (Hamilton 1965, eq. 20): the
  error variance comes from residuals the tested effect does not enter. On
  #943's CrSBr arm (seed 1343) the scatter is 0.99 against 2.57 before, and
  z reads 7.76 against 2.99 (6.9-8.2 on seeds 1343 and 1346-1352, the
  contributor's measurement). The A2 arm is an ordinary pass, and the 4x arm
  reads 17.0. `THRESHOLDS_VERSION` moves 1.12 → 1.13, because z's meaning
  changed although no number did. A new planted-residual test pins z as linear
  in the planted misfit with the noise unchanged.
  The review established one thing the
  merge does not do: a non-width misfit on the magnetic channels no longer
  damps z through the noise, so the false-fire guard is now only the
  differencing against the nuclear-only split. The tests that the nuclear-only
  control and the C1 sharp-width arm stay silent still pass. Gated on the merged tree
  `51b94dae` (main `37d087a5` + the PR; macOS arm64, `[dev,jax]`, nothing
  else running): fast suite 11 053 passed, 120 skipped, 2 xfailed; whole
  `-m slow` 323 passed, 12 skipped, 1 xfailed; main after the merge is
  content-identical to that tree. Two follow-ups left on the PR: the skill
  row in `references/magnetic.md` still says "its own noise", and no
  release note says the diagnostic now fires where it was silent. *Next:* the
  Tests row's synthetic k = 0 no-esd case with its PNGs, and the
  identifiability row.
- **2026-10-15** — PR #943 (outside contributor) merged as `2e5b5eb8`.
  It adds `tests/test_magnetic_width_k_half.py`, acceptance 4's synthetic
  fallback: CrSBr at k = (0, 0, ½), from a published structure, with a
  nuclear-only control and obs/calc/diff PNGs to `tests/output/` with
  magnetic-only zooms. So acceptance 4 is met by the synthetic stand-in, and
  the test's docstring says which was used. Real k ≠ 0 CW data (Ba₂FeSbSe₅)
  is still the better row whenever it arrives. Round 2 made the A2 arm
  `xfail(strict=False)`, since z = 2.99 sits 0.3 % under the 3.0 bar. That arm
  records the width-diagnostic task above, and it becomes a pass when that
  task lands. The merge was gated in a stack with #949, #955 and #947 on tree
  `2268e525`. The fast suite gave 10632 passed, 120 skipped, 2 xfailed, and
  the whole `-m slow` suite gave 317 passed, 12 skipped (macOS arm64,
  `[dev,jax]`, Python 3.12.10). The Tests row stays open for its k = 0
  no-esd case. *Next:* the width diagnostic's noise estimate (Tasks, last
  row).
- **2026-10-15** — from the PR review (PR #943): the width diagnostic can stay
  silent on the case it exists for. On #943's synthetic CrSBr the moment came
  back 25 % low with the width held at zero, and `MAGNETIC_WIDTH_UNMODELLED`
  read z = 2.99 against its 3.0 bar. @yue-here decided it is a task here, with
  no change in #943 (Tasks, last row). Round 1 at `98cfb0a4` asks one change
  before merge: the A2 test's `xfail(strict=True)` becomes non-strict, since
  2.99 sits 0.3 % from the bar and any platform's last digits can cross it.
  *Next:* #943's round 2. It carries the Tests row and acceptance 4's
  synthetic fallback.
- **2026-10-06** — PR #734 (outside contributor, issue #729) merged as
  `36765711`. `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` is now silent where
  the width starts the stage above zero. The order the code describes starts
  widths held at zero, so a width with a value is a refit of a measured one,
  and the warm-refit false alarm of #729 is gone. The skill row in
  `references/magnetic.md` says so, in all three copies. It was gated on a
  six-PR stack replayed onto `65a78ab7`. On macOS arm64 with a `[dev,jax]`
  venv the full suite gave 8724 passed, 110 skipped, 1 failed. The failure is
  `test_backend_shim.py::test_numpy_path_bit_identical_to_golden[toy_anomalous]`,
  which fails on bare `origin/main` on that machine too. No task below is
  ticked by it, because #729 arrived as an inherited item. The three open
  tasks are unchanged.

- **2026-09-30** — A magnetic phase's magnetic peaks can now be broader
  than its nuclear ones, so a specimen whose magnetic order is coherent over
  a shorter length than its crystallites no longer has its moment shrunk to
  pay for the width. `Phase.magnetic_lor_size` (1/cosθ) and
  `Phase.magnetic_lor_strain` (tanθ) broaden the magnetic component alone,
  under the phase's one scale. `plan="magnetic_width"` frees them in the
  order that keeps them from trading against the moment, and the report
  says when the width was needed but held, when it came back unmeasured,
  when releasing it moved the moment, and when a hand-written plan frees it
  beside a cold moment. At the zero defaults nothing moves: the second draw
  is not built, and every existing fit runs WP-1327's code path. This
  landed as PR #524 (`mustachefeeling`), merged as `e3e6486a` in a
  `/pr-review` run after three review rounds. Nine of the eleven task lines
  are done. Identifiability and the tests-plus-PNGs line are partial, and
  acceptance 4's real k ≠ 0 dataset was not measured.
  - **Schema and table.** Both terms are deg 2θ, softplus, `min = 0.0`,
    default 0.0, refused by name when non-zero or free on a phase with no
    `magnetic_symmetry`, and registered only on a phase that declares one.
    Where no magnetic component is drawn they are force-fixed, not
    refused: on a non-neutron source outside a joint table
    (`_magnetic_component_drawn` asks `magnetic_wanted`), and under Le Bail
    or Pawley through `mode_fixed_path`. `SCHEMA_VERSION` 0.36 → 0.37,
    `THRESHOLDS_VERSION` 1.9 → 1.10, two `help.py` entries, and the GUI's
    `PLACES` rows with the dist rebuilt.
  - **Forward model, and bit-identity as a code path.**
    `phase_peaks(component=0|1)` keeps ⟨|F_N|²⟩ and p²⟨|F_⊥|²⟩ as two
    arrays with one `base` each, and every later factor multiplies both.
    `_width_block(magnetic=True)` adds the pair under the Lorentzian-FWHM
    law. `CompiledPhase` gains `win_mag`/`fcj_n_mag`/`batch_mag`, sized
    from `moving_paths` with `MAGNETIC_SIZING_FLOOR`, and
    `CompiledModel.mag_split` is the one reader of whether they exist. With
    both terms zero and neither in `moving_paths` nothing is built;
    `test_at_the_default_no_second_family_is_built` asserts that on the
    gated and the ungated compile. The PR measured `predict()` bytes equal
    to `f1b89d63`'s for MnF₂ and for Cr₂WO₆ with a moment.
  - **Jacobian and multi-histogram.** No new branch: the peak-chain branch
    already claims every `phases.*` name, so no new `_column_extras` reach;
    the peak-chain, scale and axial builders now iterate
    `DerivativeBases.components(ip)`, without which the columns came back
    short. A free width against an unclaimed compile is refused by name in
    `run_least_squares`. `test_cross_backend.py` gains a `magnetic_width`
    row with axial S/L and H/L set, and jax and torch decline it by name,
    as they decline any moment. `SIZE_LAMBDA_POWER["magnetic_lor_size"]`
    is 1.0, the strain partner unlisted.
  - **Report and staging.** `MAGNETIC_WIDTH_UNMODELLED` (warning) is the
    centre-versus-tails sign split at the magnetic-only reflections minus
    the same at the nuclear-only ones, read while both widths are held at
    zero; it names the reflections and says the moment is biased low.
    `MAGNETIC_WIDTH_UNMEASURED` (info) names a freed width below
    `MOMENT_SUPPORT_SIGMA` of its esd or back with none.
    `MAGNETIC_WIDTH_MOVED_MOMENT` (warning) compares the moment at step 1
    against step 3. Both staging routes were taken: the preset (moment,
    then the widths seeded to 0.05° with the moment held, then both) and
    the first `STAGE_FREES_*` check,
    `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT`, read off the plan in `fit`
    and `run_stage` before the first stage runs.
  - **Other readers of the draw.** Four took the component-0 default and
    now read both: `structure_intensity_partition` (NaN on magnetic-only
    reflections), `reflection_support` (scored them 0), the
    `effective_observations` census and `report.strain`. Layer 1 and the
    texture partition read both through `DerivativeBases.component_entries`.
    `ReflectionRow.component` gives a split phase one `"nuclear"` and one
    `"magnetic"` row per (line, reflection).
  - **Docs and tests.** Manual Part 2's `int-two-component` equations with
    their `{source}` line, Part 1's `sec-magnetic-width` in
    `using/refining.md`, and a "Magnetic-width codes" table in the skill's
    `references/magnetic.md` (copies identical, `SKILL.md` unchanged).
    `tests/test_magnetic_width.py` holds 52 cases, none marked slow.
  - **Deviations, argued and accepted.** The off-state gate reads the
    values plus `moving_paths`, not `gate_off_states`, so a plot or replay
    of a magnetic phase is not split. The magnetic-only set is a purity cut
    on the intensities, not `nuclear_mask`, which misses a supercell's
    strong magnetic rows. An unmeasurable width returns an esd larger than
    its value, or none, never an absent esd from `unmeasured_rows`. The
    code rows went to `references/magnetic.md`, per the #287 ruling this
    WP inherited.
  - **What the PR measured** (off-suite scratch script, macOS arm64). On a
    synthetic Pbcm supercell, k = (½, 0, 0), three draws, a planted width
    of 0.25° and moment of 3.6 μ_B: freed, the moment lands within
    0.73-0.86σ and the width 1.2 % low (1.2-1.3σ, read as the fit's own
    windows truncating tails the data carry); held, the moment is about
    nine esds low and `MAGNETIC_WIDTH_UNMODELLED` fires; with no planted
    width both warnings stay silent. Cr₂WO₆ (HB-2A, 4 K, k = 0) is not
    separable, as the WP expected: size 0.0337 ± 0.0164, strain on its
    floor, both declared unmeasured. The in-suite round trip is MnF₂ at 2σ
    and 5 % bars rather than 1σ, and its docstring argues why.
  - **What it deliberately does not do.** No real k ≠ 0 dataset
    (Ba₂FeSbSe₅ is not vendored and its licence is unchecked), and no PNGs
    to `tests/output/`. `multi.py`'s joint report emits none of the four
    codes. No microstructure-table row for a magnetic coherence length.
    `report/satellites._peak_widths` still reads the nuclear widths on a
    split phase and needs the wider of the two, a separate change.
  - **What the reviews found.** Ten defects over rounds 1 and 2, all fixed;
    round 3 asked only for a merge of `main` (a CI flake #547 had fixed)
    and restated the merge order. The ones worth remembering:
    - Bit-level assertions inherited the compiled tier and failed on Linux
      at 1.24e-16 relative. They now declare the numpy path through a
      `numpy_path` fixture.
    - The ordering check restated `set_vary`'s filter without the hold,
      and fired under Le Bail and Pawley on a stage that freed neither
      quantity. `ParameterTable._glob_reaches` is now the one predicate,
      `would_free` its dry run, and `mode` a required argument.
    - The preset's seed wrote 0.05° into both widths under Le Bail and
      Pawley, because it ran before the mode's force-fix drop, and the
      next Rietveld fit then drew a split and silenced
      `MAGNETIC_WIDTH_UNMODELLED`. The drop now precedes both seeds.
    - Also fixed: `run_stage` warning on step 3 of the preset, Layer 1 and
      texture reading only the nuclear draw, the width raising rather than
      being force-fixed where no split is drawn, a no-esd cause stated
      unchecked, an extra forward evaluation per result, and no
      cross-backend row on the magnetic FCJ family.
  - **Gotchas for the successor.**
    - **Seed, then hold.** `_hold_unsupported_phases` runs after the
      stage's seeds, so a magnetic phase the data cannot see at step 2 of
      `magnetic_width` gets both widths seeded to 0.05° and then held. They
      return at 0.05°, unrefined and absent from `parameters`. This
      predates WP-1343 and applies to every seeded parameter.
    - **`resolve_plan` does not enforce `PLAN_INFO`'s modes**, so
      `plan="magnetic_width"` resolves under Le Bail and Pawley; harmless
      only because the force-fix drop now runs before the seeds.
    - **`API_INDEX_MAX_BYTES` went 39 000 → 39 500** (maintainer's call):
      main stood at 38 993 B and #524 renders 137 B more. A technique split
      (`api-magnetic.md`) is the alternative when it next fills.
    - **Two collisions, owned by the later PRs.** #522 takes
      `SCHEMA_VERSION` 0.38 and drops its copy of the `API_INDEX_MAX_BYTES`
      hunk. #546 adds `DIAGNOSTIC_SCOPES` rows for
      `_stage_order_diagnostics` and `_moved_moment_diagnostics` as
      `ABSENT` (neither helper is called from `multi.py`, so a joint
      neutron fit gets no ordering warning today — wiring them in is a
      separate change).
  - **Next.** Root `CLAUDE.md`'s "exactly two of the six sample-broadening
    quantities" is three of seven on a magnetic phase now; that edit is the
    maintainer's, flagged in round 1. Then the two partial lines: a
    synthetic k = 0 case in the suite whose intensities track, asserted
    unmeasured (or a ruling that deviation 3 answers it), and the PNGs.
    Acceptance 4 still wants real k ≠ 0 CW data: ask for Ba₂FeSbSe₅ and
    check its licence before vendoring.
  - **Measured on the merged tree** (Linux x86_64, 4 cores, py3.12.3,
    `[dev,jax]`, run as root, on `origin/main` `e8d15d0` with #524). Full
    suite with slow tests included: 7201 passed, 124 skipped, 1 failed in
    1:07:35. The failure is `test_held_phase`'s ramp runaway guard (76.5 s
    against 60 s; 19.7 s alone, WP-1420's load sensor). `main` then moved by
    #566 (four WP files) and the head was rebased onto it. Its tree equals
    the rebuilt merge, which differs from the gated one only there, and
    `test_docs_consistency` passed on it. The GUI ladder: the rebuilt dist
    is byte-identical to the committed one, vitest 581 passed in 24 files,
    svelte-check 0 errors in 392 files.
- **2026-09-08** — created, from the assessment of issue #277. The package
  now has a written answer to a gap that WP-1327 opens and does not close:
  a magnetic peak broader than the nuclear profile is fitted by shrinking
  the moment, and there is no term to stop it because the separate magnetic
  phase that carried one was rejected. Anyone reading this WP also knows not
  to trust the issue's numbers — no rietx that exists could have produced
  them — and knows which of its four design choices were changed and why. No
  code touched, and nothing here can start before 1327 lands.

  *Done*: the WP file, the ROADMAP row and its section paragraph (rewritten
  from nine lines to ten while carrying the new fact), the size cap
  645 → 648 with its dated diary line, and the one forward reference this WP
  needs — 1327's `### Inherited` now carries the ask to let the magnetic
  |F_⊥|² arrive as its own array beside `f2` and stay separable through to
  the per-line `base`. That ask is free for 1327 and it is the difference
  between 1343 being an extension of its structure-factor path and a rewrite
  of it.

  *Measured*: nothing about the physics — this session ran no fit and could
  not, since there is no moment to refine. What it did check is the tree, and
  the checks are the reason the issue's evidence is refused: `MomentEvidence`,
  `T-3c` and `model/forward_tof.py`, all cited in the issue as existing,
  appear nowhere in the repository; `Atom.moment` and `Phase.magnetic_symmetry`
  are 1327's unstarted tasks; POWGEN is TOF and neutron TOF is still fenced;
  and no `STAGE_FREES_*` check exists to extend for the staging rule. Test
  counts did not move — no test was added, and the only file touched under
  `tests/` is the size-cap diary. `tests/test_docs_consistency.py`,
  `test_skill.py`, `test_no_stale_name.py` and `test_workflow_hooks.py`:
  91 passed, on the pr-bench `[dev]` venv, macOS (darwin 25.5.0).

  *Gotchas for the successor*: (1) the two width terms are only identifiable
  where the magnetic/nuclear intensity ratio differs across reflections, so
  1327's own k = 0 datasets are expected to return them **unmeasurable** —
  that is the acceptance's answer, not its failure. (2) The diagnostic
  deliberately does not measure an observed width; the machinery for that is
  v1.4's `fit_peaks` (WP-1101) and waiting on it would put this WP behind a
  milestone it has no other reason to wait for. (3) The Ba₂FeSbSe₅ data the
  one k ≠ 0 acceptance row wants is not vendored and its licence is not
  checked — ask for it early, because the fallback (a synthetic supercell)
  changes what that row proves.

  *Next*: 1327, which this WP cannot start before; 1326 is soft, and
  without it the k ≠ 0 acceptance row has no satellites to read. When it does,
  the first task is the schema, and the first thing to re-check is whether
  1327 honoured the `### Inherited` ask — if the magnetic term was folded
  into `f2`, the forward-model task is a rewrite and should be re-estimated
  before the schema is touched.
