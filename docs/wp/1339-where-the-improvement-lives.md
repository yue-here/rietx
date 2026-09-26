# WP-1339 — where the improvement lives

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P3 2026-09-23 — a statistic compare already computes, reached as a function

## Goal

The localisation statistic `rietx compare` already computes is reachable as a
library function over **two results on the same pattern**, and a symmetry-aware
wrapper asks the question a global statistic cannot: does the improvement land
where the added degree of freedom says it must?

## Context

`viz/compare.py` already contains the statistic that settles whether a
symmetry-lowering is real, and states the principle exactly:

> **A correction that improves Rwp by rising sharply somewhere and falling
> elsewhere is absorbing something, not modelling it.**

It is reachable only through `rietx compare` — a browser UI over **bundled
standards × predefined variants** (`run(standard_key, variant_key)`,
`catalog()`, standards hard-coded in `_build_srm660c` / `_build_fap` /
`_build_nac` / `_build_lab6_capillary`, variants as `_with_*` functions).
And there is less to lift than "the statistic" suggests: per variant the
cumulative is one line inside `run` (`cumulative = np.cumsum(delta ** 2)`,
stored as `RunRecord.cumulative_chi2`), and the **difference against the
reference** — the panel — is computed in the browser, in the JavaScript
embedded in `compare_app.py`. There is no function taking two results on the
same pattern and returning where their Δχ² lives; one has to be written, and
then both the record and the page consume it. So for the case the principle
was written for — a user's own two candidate space groups on their own data —
the analysis has to be rebuilt by hand.

**Issue #219 rebuilt it by hand, and it reversed the answer.** A laboratory
Cu-Kα pattern of commercial NiO, 6495 points. Cubic `F m -3 m` against
rhombohedral `R -3 m:R`, nested (α → 60° recovers cubic), both fits given
identical treatment — same background, same U/V/W/X/Y, same Biso, same
microstrain — differing only in the symmetry and its one extra degree of
freedom:

| | Rwp % | P | χ² |
|---|---|---|---|
| cubic `F m -3 m` | 5.7490 | 18 | 28816.06 |
| rhombohedral `R -3 m:R` | **5.6445** | 19 | 27778.16 |

ΔBIC(rhombo − cubic) = **−1029.1**. Nested F(1, 6476) = **241.97**,
p = **1.35×10⁻⁵³**. On every global statistic the symmetry-lowering is
overwhelming, and the refined value carries a tight esd: α = **59.9504(30)°**.

**It is wrong anyway, for two reasons no global statistic can see.**

1. **Wrong sign.** NiO contracts along cubic ⟨111⟩ below T_N ≈ 523 K
   (Rooksby 1948), so in the primitive rhombohedral setting α must be
   **greater** than 60°. The refinement gives −0.0496° from 60°. Magnitudes
   for reference: Bartel & Morosin (1971) put saturation at ~4.5 arcmin
   (0.075°); Pomjakushin (arXiv:2509.11715) gives δ_R ≈ +1.9×10⁻³ at 2 K. The
   fit found a distortion of plausible size and the **opposite sense**.
2. **Wrong place, and this is the part the package can check.** The predicted
   splitting is resolvable — it grows from ~48 % to ~104 % of the local
   instrument FWHM across the pattern — but the Δχ² improvement is wildly
   non-monotonic in 2θ, and **the single largest-magnitude decile (75–86°) is
   where the *cubic* model fits better**, while containing the two
   largest-multiplicity predicted split families. Windowing the six
   largest-multiplicity split families (6.2 % of points) captures **−28 % of
   the total Δχ²**: net *negative* precisely where a real rhombohedral
   distortion must concentrate its advantage. The plots show a shared,
   near-identical peak-shape defect driving that region in **both** models —
   the extra degree of freedom is absorbing it, not modelling a symmetry break.

Controls, each able to fail: freeing the zero shift alone recovers only **37 %**
of α's χ² improvement, freeing sample displacement alone only **10 %**, so it
is not a positional systematic either. No diagnostic fired on any of it; the
ones that did fire were a deliberate `lor_strain` floor (`BOUND_HIT`) and
generic symmetric TCHZ degeneracies (`HIGH_CORRELATION` on `lor_size`/
`profile.x` and `lor_strain`/`profile.y`).

**How close this came to going the other way** is the argument for the WP: two
independent agents fitted the same file and reached **opposite** conclusions —
"rhombohedral decisively favoured, ΔBIC −5553" and "the data do not
discriminate". Both were wrong. The first had a cubic baseline 1.1 pp worse
than achievable, so its extra symmetry absorbed the difference; the second
computed its information criterion on a quantity that was not a χ². The
localisation test is what settled it, and it settled it **against** the
statistically overwhelming answer.

This is also the package's own standing rule one rank up: **a new correction
ships with a record field or a diagnostic stating what it changed, never an
Rwp comparison as its evidence** (root CLAUDE.md). #219 is that rule applied
to a *user's* model choice rather than to a package correction, and the
machinery for it already exists in one place with the wrong reach.

**Three asks, in increasing novelty.** (1) is close to a refactor and the
contributor has offered a PR for it alone; (2) is the genuinely new part; (3)
is a design call to take rather than accept.

1. `cumulative_delta_chi2(result_a, result_b)` returning the cumulative
   Σ_{2θ′ ≤ 2θ}(δ²_b − δ²_a) against 2θ for two results on the same pattern,
   plus its decile/quantile breakdown. No UI, no bundled standards, no
   predefined variants.
2. A **symmetry-aware wrapper**: given two nested candidate models, enumerate
   the reflection families the lower-symmetry model **splits**, window the
   pattern to them, and report what fraction of the total Δχ² lands there
   against what fraction of the points they cover. The verdict is then
   mechanical — an improvement concentrated on the split families supports the
   distortion; one flat across the pattern, or **negative on the split
   families**, is absorption.
3. A **diagnostic when the two disagree**: the global statistic prefers the
   richer model while the improvement is anti-localised with respect to the
   degree of freedom that model adds. This is a different failure from what is
   covered — `BACKGROUND_ABSORPTION` asks whether the background can reproduce
   a phase's scale, and the identifiability machinery works at a converged
   point in parameter space. This one is about **where in the data** an
   improvement lives relative to where its physics says it must.

**Decided 2026-09-03 by the maintainer**: asks (1) and (2) together, the NiO
case as acceptance (the pattern to be obtained with permission — the task
below), and (3) as **report-only output** — a number the reader judges, not
a `Diagnostic`, because a diagnostic needs a threshold and the package
reports evidence rather than verdicts. The contributor's PR offer for (1)
and (2) is accepted.

### Inherited

- **From WP-1417, 2026-09-27: `references/judging.md` now has a § 4
  section on adding a parameter** (the t-ratio before ΔBIC at N/f²,
  `report.compare_freed`). This WP's routing row, that ΔBIC and a
  nested F-test do not settle two candidate space groups, belongs
  beside it and should cite it rather than restate N/f².

- **From WP-1461, 2026-09-26: the page this WP's Context describes has
  moved.** The compare page is files in `compare_app/static/`, and the
  JavaScript embedded in `compare_app.py` is gone. The Δχ² against the
  reference is now `rxplot.difference`, a plain subtraction in the chart
  module's `overlay` figure. It was a linear interpolation between two
  separately decimated grids. The subtraction holds because every variant of
  a standard fits the same channels, and
  `test_no_variant_moves_the_channels_a_standard_fits` pins that. A user's
  two candidate models on their own data have no such guarantee unless both
  fits share limits and exclusions. `RunRecord` now keeps float64 arrays at
  every fitted channel, and `RunRecord.curves()` packs them for the page.
  There is still no Python function taking two results and returning where
  their Δχ² lives, so the lift this WP plans is unchanged.
- **2026-09-23, from the issue triage (issue #219).** The reporter's
  2026-09-04 comment carries this WP's question to a second phase, and no
  session had folded it. Synthetic cubic Cu with anisotropic Stephens strain,
  modelled as the parent plus an `I 4/m m m` subgroup phase that is not in the
  specimen. The absent subgroup takes the misfit at 57σ support and ΔBIC −1818,
  with no `PHASE_UNCONSTRAINED` and no hold. On the isotropic control, Rwp is
  0.0399 in every arm, and the subgroup's support reads 0.65σ (held), 197σ or
  54-56σ depending only on the seed. So for a phase collinear with another,
  `phase_support` measures where the fit landed on a ridge. `HIGH_CORRELATION`
  fires on the two scales in every arm and separates nothing. The localisation
  statistic transfers weakly: a gain-density ratio of 2.4 for the phantom
  against 1.3 for a real 40 % subgroup, with no sign flip. What did separate
  them was ± seeds off the identity point and the rival with the same freedom
  on the parent (ΔBIC +797 against the phantom). Checked against the tree at
  `644dff84`: `schemas/sequential.py:78-81` still calls `PHASE_UNCONSTRAINED`
  the measurement that answers "is this phase real", which this falsifies for
  a collinear phase. That sentence is a fix whatever else this WP decides.
- **From WP-1434, 2026-09-18: which codes fired in that measurement may no
  longer reproduce.** `BOUND_HIT` now asks whether the limit carried load
  instead of whether the value stopped near one, so the `lor_strain` floor
  observation was taken under a test that no longer exists. Re-run before
  building on the list of what fired.

## Non-goals

- Deciding the space group. The package's standing rule holds:
  `determine_extinction_symbol` returns ranked classes, never a confident
  singleton, and this WP adds evidence rather than a verdict.
- `rietx compare`'s standards and variants registry, and its UI. Adding a row
  there when a correction lands stays a separate obligation (root CLAUDE.md).
- The NiO physics. The dataset is an acceptance case, not a claim about NiO.

## Tasks

- [ ] Write the library function over two results on one pattern (the
      cumulative Σ(δ²_b − δ²_a) and its quantile breakdown); `run` and the
      page's JavaScript both consume it, so there is one authority and the UI
      is a consumer.
- [ ] The NiO pattern: obtain it from the contributor with permission to ship
      it under `tests/data/` and a provenance row in `tests/data/README.md`
      (data carries its own fence, per file — root CLAUDE.md § Licensing), or
      build the acceptance on a constructed nested pair and keep NiO as an
      external check quoted from the issue.
- [ ] The split-family enumerator and the windowed Δχ² share, for two nested
      models.
- [ ] The disagreement case as report-only output (decided 2026-09-03: a
      number the reader judges, never a `Diagnostic` with a threshold); write
      the reason where the number lives.
- [ ] Acceptance on the NiO pair: the localisation test must return the
      negative share (~−28 % on 6.2 % of points) that reversed the answer, and
      the check must be able to fail — a genuinely localised improvement on a
      constructed case must score positive.
- [ ] Tests: `tests/test_compare_ui.py` keeps asserting the UI field by field;
      the new function is tested on results, not on the UI's standards.
- [ ] Skill: `references/judging.md` — the routing row for "two candidate
      space groups, which one", pointing at the localisation share and saying
      plainly that ΔBIC and a nested F-test do not settle it.

## Acceptance

A constructed nested pair with a genuinely localised improvement scores
positive and an absorbed one scores negative; the NiO pair, if it ships,
reproduces the measured decile breakdown and the −28 % split-family share.
The pattern is not in the repo today.

```sh
.venv/bin/python -m pytest tests/test_compare_ui.py -q   # plus the new function's own module, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #219 (NiO, laboratory Cu-Kα, 6495 points; the contributor offers a PR
  for ask 1, or 1 and 2 with the NiO case as acceptance).
- Rooksby (1948) — the ⟨111⟩ contraction below T_N ≈ 523 K, which fixes the
  sign. Bartel & Morosin (1971), *Phys. Rev. B* — saturation ~4.5 arcmin.
  Pomjakushin, arXiv:2509.11715 — δ_R ≈ +1.9×10⁻³ at 2 K.
- Search the local paper corpus before requesting any of these.

## Handover log

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #219).
  Re-checked the same day against the tree: there is no function to lift —
  the cumulative is one line in `run` and the difference is browser
  JavaScript; the NiO pattern is not in the repo, so acceptance rests on a
  constructed pair. Decisions recorded the same day: scope is (1) and (2)
  with NiO as acceptance, (3) is report-only.
