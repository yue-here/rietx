# WP-1343 — the magnetic peaks are broader, and the moment pays for it

Milestone: unscheduled · Status: ⬜
Depends on: 1327 (the moment, the magnetic |F_⊥|², the shared scale);
1326 soft (the satellites that make the term identifiable)

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
  `moving_paths` gate.
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
`MARCH_R_MIN` is wanted. The *conversion* to a coherence length does divide,
and at zero it returns an infinite length, which is `lor_size`'s existing
case in `model/microstructure.py` and not a new one.

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

- [ ] Schema: `Phase.magnetic_lor_size` and `Phase.magnetic_lor_strain`
      (deg, `min = 0.0`, default 0.0), refused on a phase with no moment
      block; `SCHEMA_VERSION` bump with its one-sentence comment;
      `help.py` entries with unit, default and typical range.
- [ ] Forward model: `f2`/`f2_mag` kept separable through `phase_peaks`, the
      second width from `_width_block` via the existing addition law, the
      second frozen window and FCJ family on `CompiledPhase`, and the
      structural skip at the off state gated on `moving_paths`.
- [ ] Bit-identity: every shipped fixture, and 1327's own magnetic
      acceptance, unchanged with the new fields at their default — asserted
      as the *same code path*, not as two floats agreeing.
- [ ] Jacobian: FD first, then the analytic branch with its `_column_extras`
      reach declared, the `test_cross_backend.py` rows that cover it, the
      traced twin.
- [ ] Multi-histogram: rows in `params.multi.SIZE_LAMBDA_POWER` for the new
      size term (λ¹, as `lor_size`), or the joint fit shares a coefficient
      that is not one number across wavelengths (WP-1131's invariant), with
      the two-histogram test that catches it.
- [ ] Identifiability: the unmeasured path named rather than quoted, on all
      three regimes above; a synthetic k = 0 case asserted to come back with
      no esd rather than a small one.
- [ ] `MAGNETIC_WIDTH_UNMODELLED`: the differential centre-versus-tails
      statistic on magnetic-only against nuclear-only reflections, its
      message naming the reflections and the direction the moment would
      move, and its row in `references/diagnostics.md`
      (`test_docs_consistency.py` looks for it there).
- [ ] Staging: the three-step order in the magnetic plan preset, and the
      report for a stage list that frees the widths beside the moment —
      either the first `STAGE_FREES_*` check or a written skill row, decided
      on cost at the time.
- [ ] Manual: Part 2 gains the two-component draw with its *Source* line
      beside 1327's structure factor; Part 1 gains the paragraph in the
      magnetic chapter.
- [ ] Skill: rows in the magnetic `references/` file 1327 opens — the
      turn-on order, what the diagnostic means, and when the width is not
      measurable. Paid for by a named cut if the body moves at all.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`, magnetic-only
      reflections zoomed.

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
   4.13(4) μ_B, before and after. **Ask for the data and check its licence
   before vendoring** (memory: the maintainer supplies literature and data
   on request; `tests/data/README.md`'s per-file fence applies). If it
   cannot be obtained, a synthetic k ≠ 0 supercell built from a published
   structure stands in and the acceptance says which was used.
5. **Staging.** A plan that frees the widths beside the moment from a cold
   start is reported by name before it runs.
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

- **2026-09-08** — created, from the assessment of issue #277. The proposal
  is accepted in shape and its evidence is not: the measured table it leads
  with cannot have come from rietx (no moment on main, and POWGEN is TOF,
  still fenced), and its own follow-up comment attributes most of that
  signature to a phase coexistence rietx can already model. What carries the
  WP instead is an argument from our own design — 1327 rejected the separate
  magnetic phase, and this term is what that phase was buying. Four things
  changed from the issue's proposal: the Gaussian partners are dropped
  (WP-1076's absent-writer trap), the acceptance is CW-only, the FWHM-ratio
  diagnostic becomes a differential residual-shape test that needs no peak
  fitting, and the identifiability question the issue does not raise (k = 0
  makes the term nearly flat) is answered with the package's existing
  unmeasured-row rule. No code touched. First task is the schema, and it
  cannot start before 1327.
