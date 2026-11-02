# WP-1339 — where the improvement lives

Milestone: unscheduled · Status: 🔄 2026-11-02 — claimed by @yue-here (ghostshift runner)
Track: Render what the fit already knows
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

- **Decided 2026-10-16 (maintainer, from the issue triage, #219): #219 closes
  with ask (3) done as report-only.** The seeded-pair helper is not built.
  #219 is closed with a comment naming PR #928's measurement (real parent held
  in 0 of 15 split starts) and the wrong-sign tetragonality that only a pair
  of seeded fits fixes.

- **2026-10-13 (2nd), from WP-1523's close: the hold no longer picks a side
  on a collinear pair, and the wrong-sign start is yours.** A phase's scale
  significance is now conditional on the other phases' scales
  (`refine._significance_columns`). On #219's ridge neither phase is held
  from a split seed: the real parent was held in 9 of 15 before, 0 now. The
  phantom at the identity point is still held. The only report is
  `HIGH_CORRELATION` on the two scales. TWO-PHASE-TRUTH from the degenerate
  seed lands at −1.0e-3 against +3.0e-3 with no hold at all (5 of 5 seeds).
  So ± seeds off the identity point and a comparison, ask (3), is the only
  remedy. Table: WP-1523 § Decided 2026-10-13. The entry below is settled by
  this one.
- **2026-10-13, from WP-1523: the ridge's hold decision is WP-1523's task 7,
  so nothing here waits on it.** WP-1523 first kept the support hold on a
  collinear pair (§ Decided 2026-10-12) without the #219 script. The
  triage's re-run of that script, which the 2026-10-13 entry below points
  to, reopened the choice there as task 7. The candidate statistic is the
  scale's z marginal over every column except the other phases' scales.
  #904's localisation does not answer it, as the entry below says.
- **2026-10-11, from the issue triage (#219, in PR #904; and a re-run of the
  ridge case): asks (1) and (2) are open as the reporter's PR, and the ridge
  now holds the wrong phase.** PR #904 (opened 2026-10-11, fork) adds
  `report.cumulative_delta_chi2` and `report.split_localisation`, moves
  `viz/compare.py` onto `report.cumulative_chi2`, and rewrites the
  `schemas/sequential.py:79` sentence. Ask (3) is not in it. Its tests are
  synthetic, and the NiO acceptance waits on permission to ship the pattern.
  The claims match #219. Checked against the tree at d80ca5f4: no
  `report/localisation.py`, and no `cumulative_delta_chi2` under `src/`.

  The reporter re-ran the two-phase Cu toy at 08176f6f, after WP-1523, with
  the same script, pattern and plan (comment of 2026-10-11 15:17Z). The
  specimen is one cubic Cu phase. The model is the parent plus an
  `I 4/m m m` subgroup that is not there. Their numbers, not re-run here,
  since the script is not in the thread:

  | subgroup seed | Rwp | `PHASE_UNCONSTRAINED` holds | its reading |
  |---|---|---|---|
  | degenerate | 0.0399 | the subgroup | 0.81σ |
  | split, δ = 5e-4 | 0.0399 | **the parent** | 0.20σ |
  | split, δ = 1e-3, 2e-3, 4e-3 | 0.0399 | **the parent** | 0.53σ |

  In the last two rows the parent's cell and strain are held while the
  phantom subgroup carries the pattern at 31-82σ. `HIGH_CORRELATION` on the
  two scales (ρ −0.994 to −0.998) fires in every arm. The positive control (a
  real 40 % subgroup) flags the parent at 2.3σ and 2.2σ from the degenerate
  and δ = 5e-4 seeds. So the marginal test reads low on a collinear pair, as
  the entry below expected, but on whichever phase the start left weaker.
  Which of the two the rule should hold is WP-1523's decision, and its
  Inherited carries the same numbers. Before any becomes a target, the
  script has to be on the tree; the batch asks the reporter for it.

- **From WP-1523, 2026-10-04: the support statistic changed, and the ridge
  case is unmeasured under it.** "Seen" is now the phase scale over its esd at
  3σ (`refine._answer_significance`). The esd comes from (JᵀWJ)⁻¹ against
  counting noise and is marginal over every free column except displacements
  and occupancies, so another phase's scale and cell are in it.
  `phase_support` is now only the screen, ‖y_p/σ‖₂. The #219 entry below read
  0.65σ, 197σ and 54-56σ on the old single-point max. Re-measure it before
  building on it. A phase collinear with another should read low on the
  marginal, but nobody has measured that.
- **From WP-1469, 2026-09-29: the support statistic now has an owner.** The
  #219 entry below found `phase_support` reading 0.65-197σ on one phantom
  phase depending only on its seed. WP-1469 found its noise twin: a frame
  with no phase in it, fitted alone, released its held cell at 2.14σ support
  on a scale 1.3σ from zero, or held it, depending on the start. Both are
  filed as [1523](1523-a-phase-fitted-to-noise-passes-the-support-test.md),
  which owns what "the data can see this phase" means. The #219 numbers stay
  here as this WP's evidence; a fix there changes which phases read
  supported in any comparison this WP builds.
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
- **2026-10-13, from the issue triage (#219, after PR #904 merged
  2026-10-12): two loose ends for the close.** First, the reporter's
  two-phase script is now in the thread (2026-10-12 00:11Z), so the 2026-10-11
  entry's "not re-run here, since the script is not in the thread" is stale.
  It was re-run at c3d0367, and the result is in WP-1523's Inherited, which
  owns the hold. PR #904's localisation does not answer it, by its own
  docstring (coexistence "is not what this measures"). Second, this file says
  two things about #219's ask (3): task 4 is ticked as decided report-only on
  2026-09-03, while the 2026-10-12 handover says "Issue #219 stays open for
  ask (3)", and #904's body says "Ask (3) is not here". Settle which, and say
  on #219 what is left. Tasks 5 (the NiO acceptance, waiting on permission to
  ship the pattern) and 7 (the skill's routing row, which went into
  `numbers.md` rather than `judging.md`) are what remains here.

## Non-goals

- Deciding the space group. The package's standing rule holds:
  `determine_extinction_symbol` returns ranked classes, never a confident
  singleton, and this WP adds evidence rather than a verdict.
- `rietx compare`'s standards and variants registry, and its UI. Adding a row
  there when a correction lands stays a separate obligation (root CLAUDE.md).
- The NiO physics. The dataset is an acceptance case, not a claim about NiO.

## Tasks

- [x] Write the library function over two results on one pattern (the
      cumulative Σ(δ²_b − δ²_a) and its quantile breakdown); `run` and the
      page's JavaScript both consume it, so there is one authority and the UI
      is a consumer.
- [x] The NiO pattern: obtain it from the contributor with permission to ship
      it under `tests/data/` and a provenance row in `tests/data/README.md`
      (data carries its own fence, per file — root CLAUDE.md § Licensing), or
      build the acceptance on a constructed nested pair and keep NiO as an
      external check quoted from the issue.
- [x] The split-family enumerator and the windowed Δχ² share, for two nested
      models.
- [x] The disagreement case as report-only output (decided 2026-09-03: a
      number the reader judges, never a `Diagnostic` with a threshold); write
      the reason where the number lives.
- [ ] Acceptance on the NiO pair: the localisation test must return the
      negative share (~−28 % on 6.2 % of points) that reversed the answer, and
      the check must be able to fail — a genuinely localised improvement on a
      constructed case must score positive.
- [x] Tests: `tests/test_compare_ui.py` keeps asserting the UI field by field;
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

- **2026-10-12** — PR #904 merged from outside as `9669796d`. Two fits of one
  pattern can now say *where* the richer one gained, which ΔBIC cannot.
  `report.cumulative_delta_chi2` gives the running Σ(δ²_b − δ²_a) and its
  equal-count quantiles. `report.split_localisation(higher, lower)` shares the
  Δχ² among the windows of the reflections a symmetry-lowering splits, those it
  leaves whole, and the rest. A genuine distortion puts its gain on the split
  reflections, and an absorbed one does not. Issue #219 stays open for ask (3).
  - *Done.* Tasks 1, 3, 4 and 6, and task 2 by its second branch. The
    acceptance rests on a constructed nested pair in `tests/test_localisation.py`:
    a tetragonal Cu specimen gives ΔBIC +190 at N/f² and +68 % of the gain on
    3.2 % of the points, and a cubic one with a reflection-dependent shift
    gives ΔBIC +25 and −30 % on 4.9 %. `viz.compare.run` stores
    `report.cumulative_chi2`, so the page and the report share one authority.
    `THRESHOLDS_VERSION` is 1.12.
  - *Gated* on the same four-PR stack as WP-1322's entry of today (stack
    `0e4b7e25` on main `f22e9a7c`; main `f47c728e` content-identical after the
    merges).
  - *Gotchas.*
    - Children match parents **within one emission line**. A tick's line is
      its rank among the ticks sharing its `tick_hkl`, since `ticks` carries no
      line index. A line whose image falls off the axis for one reflection
      shifts that reflection's later ranks, and the docstring says so.
    - Coincident parents (333 and 511) are one `SplitFamily` carrying `hkls`.
    - Both functions refuse two fits whose `sig()` differ, since a measured
      background widens σ at compile (WP-1309).
    - No #219 value is in the tree. The pattern is not cleared to ship, so
      the manual and the skill quote the synthetic pair and cite #219 by
      number.
  - *Not done.*
    - Task 5, the NiO acceptance, waits on the pattern.
    - Task 7's row is in `references/numbers.md`, tagged `(Measured: …)`,
      because `judging.md` sat 41 B under its budget. Whether that placement
      discharges the task is the maintainer's call.
    - Two follow-ups from the review: `SplitFamily.emission_line` defaults to
      0, and a child whose nearest parent lies just outside the fitted range is
      counted nowhere.
    - `docs/releases/1.8.0.md` has no line for the two functions.
  - *Next:* decide task 7's placement. Task 5 waits on the NiO pattern.

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #219).
  Re-checked the same day against the tree: there is no function to lift —
  the cumulative is one line in `run` and the difference is browser
  JavaScript; the NiO pattern is not in the repo, so acceptance rests on a
  constructed pair. Decisions recorded the same day: scope is (1) and (2)
  with NiO as acceptance, (3) is report-only.
