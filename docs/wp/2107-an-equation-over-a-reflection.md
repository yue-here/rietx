# WP-2107 — an equation over a reflection

Milestone: parametric · Status: 🔄 2026-11-20 — every task built and tested (PR #1635, ready for review); waiting on the maintainer's read of two new diagnostics and the schema bump
Depends on: 1964 (the grammar, evaluated on arrays)
Priority: P2 2026-11-04 — a feature the open milestone was opened for: the method's founding paper uses both a 2θ calibration curve and a width on a family of hkl

## Goal

A user writes a peak's width, position or intensity as an equation in its hkl and its
angle. Its coefficients refine with exact derivatives, and it works in a joint fit like
any other parameter.

## Context

The maintainer ruled on 2026-11-04: build robust machinery, and do not overfit to TOPAS.
So this is general machinery on rietx's own terms. Its names are rietx's, and its tests
are a known truth and an analytic oracle. TOPAS is one source of use cases, and an agent
rewrites a TOPAS line into this form from the manual. The incidence of these keywords in
the private archive no longer decides anything.

**Why it belongs in the method.** Stinton & Evans (2007) use both shapes. Examples 1 and 2
apply a second-order 2θ calibration polynomial, refined from all the data in example 1.
Example 3 carries "2 terms to describe additional broadening of 0kl reflections".

**The fence named two different things.** An equation in `Xo` and an equation in `H`
are the same machinery: one array of per-reflection values, evaluated where a peak's
position or width is built. So "2θ only" is no cheaper than "hkl", and the first
scoping's two options collapse into one. `fit_obj` is the different one. It runs over
data points and adds to the pattern, so it is an expression member of
`Instrument.extra_components` (that contract's clause 6), and it stays fenced. The TOPAS
archive states it at the start of a line twice (`io/projects/topas.py`).

**What real inputs do.** Three Durham tutorials and one published input were read.

| Input | Line | What it needs |
|---|---|---|
| WO₃ | `scale_pks = Exp(-2 b/(2 D_spacing)^2)` | nothing: one overall B per pattern, a tie |
| WO₃ | `th2_offset = -2 Rad (height) Cos(Th) / Rs` | nothing: `sample_displacement` |
| ZrP₂O₇ | `th2_offset = (Xo-mid)^2 (square/1000) + ...` | **this WP**: a two-coefficient curve |
| ZrMo₂O₈ (9.2) | `spherical_harmonics_hkl ahkl`, then `lor_fwhm = zeta Max(ee_2Th,0)^.5` | **this WP's harmonic**: a tanθ width scaled by √ahkl |
| Published TOF template | Stephens macros | nothing: `Phase.microstrain` |

ZrMo₂O₈'s harmonic coefficients are fixed (`!ahkl_c00` and so on) and one number per
pattern refines. It runs 68 patterns through `num_runs`, so it is a series and no joint
fit. The first scoping read only WO₃ and ZrP₂O₇, and its statement that nothing in hand
needs an hkl equation was wrong.

**Practice.** `docs/practice.md` § An equation over a reflection. TOPAS takes an equation
in `H`, `K`, `L`, `M`, `Xo`, `Th` and `D_spacing` on `lor_fwhm`, `gauss_fwhm`,
`th2_offset`, `scale_pks` and more (Table 2-3). FullProf has built-in models and integer
rules on hkl. GSAS-II has no such equation.

### What a probe showed

`hkl_probe` patched three equations onto `CompiledModel` in a scratch script, leaving
`src/` alone (`[dev]`, macOS arm64, 2026-11-04). The phase was synthetic brucite, 38
reflections, 5250 points, with one equation on each target:
`lor_fwhm = If(L==0, a, b) Tan(Th)`, the ZrP₂O₇ curve, and an intensity factor `p` on
reflections with L ≠ 0.

- **The seams hold.** All five coefficients came back from wrong starts. Over 12 noise
  seeds the mean z-score against the truth ran from -0.27 to +0.28, with a spread of 0.53
  to 0.91 (below 1 because of the Bérar-Lelann esd inflation). χ²/N was 1.013 on seed 17,
  and the Δ/σ plot was flat.
- **Compile must evaluate the equation.** A compile that ignores a width equation sizes
  each peak's window from the wrong width. At the true values that added 1767 to χ² over
  5250 points. The refit landed at χ²/N 1.273 and the esds grew 2.3×, while the values
  stayed inside them. `compile_model` keeps its own copies of the shift and the width
  (`_shift_est`, `_size_family`), so these are second builders.
- **A hand-folded intensity builder comes back short.** Under an intensity factor of 0.7,
  a coordinate's analytic column was wrong by 43 % of its own size, which is 1/0.7 - 1
  exactly. Two builders fold intensity by hand (`forward.py:2735`, `:2825`). Nothing
  raises, so the column is silently wrong.
- **A forward difference is poor on a small coefficient.** At `sq` ≈ 2.4e-5 with
  `typical` = 1 the column was 8.5 % off a central difference. Rescaling the coefficient
  to about 2.4 took that to 7e-7. The answer barely moved: mean z 0.273 against 0.279.
  The invariant still asks for exactness, and it is cheap here (the grammar's rule times
  the existing `d_pos`, `d_gamma` and `d_eta` bases).
- **Speed is no constraint.** `evaluate` took 165 µs without equations and 169 µs with
  all three. An array equation over 7600 reflections took 7 µs. That equation was hand
  written, so a tree walk will cost more. TOPAS reports its computer algebra at 5-10 % of
  a Rietveld run (Coelho 2018, § 6).

### A reflection is an orbit

rietx holds one representative per Laue orbit, so a program's answer to `If(L==0, ...)`
can depend on which image it holds. TOPAS leaves this to the user and offers
`Multiplicities_Sum`, which iterates over the multiplicities. Orbits on which TOPAS's
own example conditions are not single-valued, on lists rietx generates to 120° 2θ with
Cu Kα1:

| Space group | Reflections | `L==0` | `Mod(L,2)==0` | `Mod(H,2)==0` |
|---|---|---|---|---|
| P -3 m 1 | 38 | 0 | 0 | 24 |
| P 4₂/m n m | 39 | 0 | 0 | 16 |
| P n m a | 173 | 0 | 0 | 0 |
| P 2₁/c | 724 | 0 | 0 | 0 |
| R -3 c | 44 | 0 | 0 | 32 |
| F m -3 m | 15 | 6 | 0 | 0 |
| I a -3 | 107 | 22 | 67 | 67 |

So a port of an hkl equation can change its numbers silently on any group above
orthorhombic. Compile evaluates the equation on every image and refuses a disagreement,
naming the first hkl. The test uses random trial coefficients beside the stored ones,
because `If(l==0,a,b)` with a equal to b passes at the start and splits during the fit.
A family has a symmetric spelling: in a cubic group `h==0` is refused and `h*k*l==0`
reads Stinton & Evans's 0kl family. `orbit_mean(...)` is the way out. TOPAS's choice of image is not
established and does not matter here: the refusal holds on physics, since a peak holds
every image. A port meets the refusal and takes the exit knowingly.

### Rules this WP inherits

- **A condition reads frozen integers only.** `h`, `k`, `l` and `m` do not move in a
  stage. A comparison on `th`, `d`, `xo` or a coefficient changes which branch a
  reflection takes during a solve, which breaks frozen-per-stage discreteness and makes
  the residual jump. It is refused, and the message names the frozen integers it may read.
- **A coefficient is a table entry.** The forward model never reads a `vars.*` path, and
  `column_reach`, the flatness tests and the holds all rest on that (root CLAUDE.md,
  WP-1342). So an equation's coefficient is an entry under its phase. Sharing it is a tie
  to a variable or a `sharing=` entry, and the probe's direct read of `vars.*` was a
  shortcut. `Entry` bounds and `at_bound` then work unchanged.
- **An equation has a level.** ZrP₂O₇'s curve sits in a macro at the pattern level, so it
  moves every phase's peaks. So a position equation attaches to the instrument and reads
  only the angle, or attaches to a phase and may read hkl. The first is
  `_position_shift_deg`'s seam as it stands. Only the second needs a phase index.
- **Per line, never per phase.** θ and the position differ between Kα1 and Kα2, so the
  equation is evaluated inside `_width_block` and `apparent_two_theta`. The `aniso` memo
  is line-independent and cannot hold it. `_shift_key` and the width key must carry the
  coefficients.
- **Widths compose as they do now.** A Gaussian term adds in variance and a Lorentzian
  term in FWHM. So the Gaussian target is a signed variance as well as a FWHM. ZrP₂O₇
  gives each phase its own six TCHZ terms, shared across patterns, as Stinton & Evans
  §§ 4.1 and 4.2 do, and its stored v and w are negative for two of the three phases.
  `Phase` has no V or W, and a FWHM cannot carry a negative term. The guard below reads
  the total. That is the package's rule, and TOPAS happens to agree at zero cycles
  (`test_topas_convolves_the_written_width_lines`).
- **The total width stays positive.** `Max(x, 0)` is legal and has the kink Stephens'
  clamp has. A total width at or below zero at the answer is a guard finding, and it
  cannot be a box bound since it couples the coefficients.

### What it builds, in order

1. **Width and position.** A Lorentzian width, a Gaussian width and a position, in `h`,
   `k`, `l`, `m`, `d`, `th` and the position before the equation acts, plus `orbit_mean`.
2. **Intensity.** The same mechanism on a third target. It needs the two hand-folded
   builders, a refusal under Le Bail and Pawley, and an answer for phase fractions. A
   factor that is not normalised changes scale × ZMV (cell mass and volume) and so the
   QPA, so such a fit carries a diagnostic that says so and quotes the factor's range.
3. **A symmetric function of hkl.** A real spherical harmonic of the hkl direction, so a
   user can write an anisotropy that is invariant by construction instead of meeting the
   orbit refusal. `crystallography/spherical_harmonics.py` holds the machinery, and
   rietx's own normalisation is stated in the manual. A port converts its coefficients.

## Non-goals

- A convolution by equation: `hat`, `one_on_x_conv`, `exp_conv_const`, `circles_conv`,
  `stacked_hats_conv`, `user_defined_convolution`.
- TOPAS's remaining peak keywords (`pk_xo`, `modify_peak_eqn`, `h1`, `h2`, `m1`, `m2`,
  `la`, `lo`), and any keyword-by-keyword parity.
- An equation reading a structure factor (`A01`, `B01`) or an intensity.
- `fit_obj`: an expression member of `extra_components`, and not this seam.
- A time-of-flight bank. `th` and `xo` mean nothing there, so a peak equation is refused
  by name until someone asks for one in `d`.
- Anisotropic size as a named block: [2061](2061-a-crystallite-has-a-shape.md), which
  derives its subspace from the operators. A user can write such a form here without
  that guarantee.

## Tasks

- [x] **The surface.** A consent item for the maintainer, since it names a field and a
  top-level type. `rx.PeakEquation(target=..., expression=...)` is a placeholder. The
  target names follow the package's own words (`lor_`, `gauss_`, position), and the
  manual's table maps TOPAS's onto them.
- [x] **Stored format.** A `Phase` field is a stored-format change, so it goes to the
  maintainer with the version it bumps. `.rxt` rendering, `help.py`, `capabilities()` and
  the `rietx._audit` rows follow.
- [x] **Compile.** Freeze `h`, `k`, `l`, `m` on `CompiledPhase`. Evaluate on every orbit
  image and refuse a disagreement, with `orbit_mean` as the exit. Refuse a moving
  condition. Teach `_shift_est` and `_size_family` the equation, and pin the windows with
  the probe's number. `generation_window` runs before reflections exist
  (`forward.py:4133`), so a phase-level position in hkl needs a bound over the expression
  that takes no reflection list, or a margin stated and tested.
- [x] **Forward.** Width in `_width_block`, position in `apparent_two_theta` with its
  phase index, and every memo key. Check `reflection_positions`, the ticks and the
  exporters' reflection table read the same answer. `apparent_two_theta` also takes arrays
  that are no reflection list (`report/satellites.py`, `refine.py:11552`), so those callers
  read the pattern level or refuse. Width readers outside `_width_block` follow too
  (`refine.py:11342`, `report/strain.py:120`, `io/exporters.py:362`).
- [x] **Derivatives.** An exact branch for a coefficient, reached through
  `scalar_chain_supported` and the extras gate. `test_cross_backend.py` gains a row, and
  the oracle follows the invariant on exactness.
- [x] **The guard.** A total width at or below zero at the answer.
- [x] **A joint fit.** An equation on each table, a coefficient shared across patterns,
  and a pattern's coordinate readable in the expression.
- [x] **Intensity.** The third target, the two hand-folded builders, the Le Bail and Pawley
  refusal, and the QPA diagnostic with its row in `rietx._audit`.
- [x] **The harmonic.** A symmetric function of hkl in the grammar, with its derivative.
- [x] **An independent check.** Each target against a built-in with the same physics,
  so no code is shared with what it certifies: `y*tan(th)` against `lor_strain`, a cosθ
  position against sample displacement, an exponential in s² (sinθ/λ squared) against
  Biso. A variance term against the instrument's U, V and W. TOPAS at zero cycles is a
  welcome extra if a run is cheap, and no gate.
- [x] **Manual and skill.** A guide page, `reference/parametric.md`, the Theory tab's
  equation, a keyword-to-target table in `switching/topas.md`, the skill's row.

## Acceptance

Over 12 pinned seeds on a synthetic phase, every coefficient of a width, a position and
an intensity equation has a mean z-score under 0.5 in size. Each equation's Y_calc matches
its built-in twin to 1e-12 relative. On a synthetic ramp with ZrP₂O₇'s curve and a
per-phase TCHZ, each coefficient is recovered within 2 esd. The milestone's ZrP₂O₇ row
then adds both to its protocol.

```sh
.venv/bin/python -m pytest tests/test_parametric_series.py tests/test_cross_backend.py   # in [dev,jax,torch]: the torch rows skip themselves in [dev]
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95, §§ 4.1-4.3.
- Coelho, A. A. (2018). *J. Appl. Cryst.* 51, 210-218 — TOPAS and TOPAS-Academic.
- Stephens, P. W. (1999). *J. Appl. Cryst.* 32, 281-289 — the template for a width in hkl.
- TOPAS Technical Reference v8, Table 2-3 and § 20.17; FullProf manual § Selective size
  broadening.
- WP-1964 (the grammar), WP-0503 (Stephens), WP-1102 (the expression clause), WP-2061.

## Handover log

- **2026-11-20 (ghostshift runners, two sessions; PR #1635)** — A user can now write
  a peak's width, position or intensity as an equation in its hkl and angle, refine the
  coefficients with exact derivatives, and share or parametrise them in a joint fit. Every
  task in the list is built. On synthetic data each target matches the built-in term with
  the same physics to 1e-12, twelve noise seeds recover every coefficient with a mean
  z-score under 0.31, and a ZrP₂O₇-shaped ramp (a 2θ calibration curve plus two phases'
  own TCHZ terms, five patterns) recovers all twelve coefficients within 2 esd. Two new
  diagnostics and a schema version bump reach a reader, and they wait on the maintainer.
  - *Done, first session (2026-11-19, commits 9f0a7f0bd-81d759009).* The grammar's
    `orbit_mean` and `harmonic` with `GRAMMAR_VERSION` 2; `rx.PeakEquation` and the two
    fields; the compile with the orbit refusal; the forward model; the exact phase
    coefficient column (`least_squares._peak_equation_column`), with instrument
    coefficients on the scalar chain; the intensity factor in both hand-folded intensity
    builders; the `peak_equations` config in `tests/test_cross_backend.py`.
  - *Done, this session.* Merged origin/main (clean). `PEAK_WIDTH_NOT_POSITIVE`
    (`staged.check_peak_width_positive`, joint fit included) and `QPA_INTENSITY_FACTOR`
    (`refine._qpa_intensity_factor_diagnostics`), with help, audit and skill rows.
    `tests/test_peak_equations.py` (26 tests, about 6 s). Schema 0.61 → 0.62. Help
    families for the coefficients, a parameter-map group, the GUI's `PLACES` entries and a
    rebuilt dist. The `.rxt` shows each equation as a comment on its coefficient rows.
    `features["peak_equations"]`. A guide page with its example script, the reference in
    `reference/data.md`, the Theory tab's `fm-peak-equation`, a keyword table in
    `switching/topas.md`. The milestone's ZrP₂O₇ row now names the equations.
  - *The joint fit needed no code.* A `ParametricEquation` whose target is
    `phases.0.peak_equations.0.w` makes the coefficient follow a coordinate: w0 and w1
    came back 0.63 and 0.94 esd from their truth over four patterns.
  - *Measured* ([dev,jax], macOS arm64). Twins: lor_strain, U, sample displacement (both
    levels) and Biso each under 1e-12 relative. Twelve-seed single-pattern recovery:
    mean z from -0.24 to +0.31. ZrP₂O₇-shaped ramp: pinned seed worst 1.68 esd; over
    twelve ramps every mean z-score 0.50 or less, and the worst of the twelve passed 2 esd
    on two ramps. `python -m tests.reader_output`: exit 0, the standard fit's text
    unchanged.
  - *Gotchas.* `Refinement.predict` draws at the closing window (1e-3) while a default fit
    measures at 2e-2, so a synthetic pattern carries Lorentzian tails the fit cuts. On the
    ramp that took a broad phase's x coefficient 1.2 esd low on average until the plan
    closed at `CLOSING_WINDOW_TOL`. A noise seed shared between runs (`seed + k`) made
    twelve ramps look biased; seed each pattern with `[seed, k]`. `F d -3 m` takes origin
    choice 1, where Si at 1/8 loses its 220; write `F d -3 m:2`.
  - *Settled by Claude.*
    1. Schema 0.61 → 0.62 rather than "also in 0.61": 1.12.0 shipped 0.61 two days
       after the consent list was written, and the changelog's practice bumps once a
       version has shipped. Alternative: keep 0.61, which would let a 1.12 build read the
       version as its own and refuse the field without saying why.
    2. No `.rxt` `FORMAT_VERSION` bump, against consent item 1's "1 → 2 for the new
       block". The coefficients render as ordinary rows and the equation as a comment, so
       there is no new block, and `textdoc.py`'s written rule says a new line is not a bump
       because a bump refuses every stored document. Alternative: a real equation block,
       editable as text, which would need the bump.
    3. The guard reads Γ_G² as the built-in terms' floored value plus the equation's, so
       a dip the instrument's own U, V and W cause stays `RESOLUTION_NOT_POSITIVE`'s.
       Alternative: one guard over the whole width, which would report the instrument's
       fault twice.
    4. `QPA_INTENSITY_FACTOR` is a warning, silent with one phase in the analysis.
       Alternative: info, on the reading that the user chose the factor.
  - *For the maintainer.* The two new diagnostics' text, shown in the PR body, since a
    change to what a reader receives comes to you before merge.
  - *Next.* The maintainer's read of the diagnostics and the schema bump, then merge. After
    merge: the real-data ZrP₂O₇ port frees the curve and the TCHZ terms beside the
    calibration (the milestone row). A follow-on from the 2026-11-20 ruling: a
    `wavelength` name in a peak equation's grammar, so a size-like term can be written
    once for patterns at several wavelengths, as TOPAS's `Lam` allows. Not built here.
  - *Review, fixed.* A phase whose magnetic component is drawn on its own profile family
    took a short analytic column, so its coefficients now take the scalar chain. A
    negative Lorentzian term sized an empty window and dropped the reflection unseen; the
    window sizing now floors it.
  - *Review, left open.* Three findings needed a design call, none of them a wrong answer
    on the tests' fits. (1) A joint fit across wavelengths shares a phase coefficient in
    degrees, while the size rule shares the size; an equation's λ dependence is the
    user's to write, and nothing warns. (2) The LM driver's width inequalities read the
    built-in terms alone, so a negative equation term is caught by the guard after the
    fit rather than held inside the step. (3) `orbit_mean` and `harmonic` parse in any
    expression and raise only when a tie or a background evaluates one.
  - *Ruled by the maintainer, 2026-11-20.* (1) Option a: a warning, not a conversion.
    `PEAK_EQUATION_SHARED_ACROSS_WAVELENGTHS` (`multi._peak_equation_sharing_diagnostics`,
    a joint fit's fit-level row) fires once per equation whose degree-valued coefficients
    are one column across patterns declaring two or more wavelengths. It names the
    equation and the shared coefficients, says the right value in degrees can differ
    with λ (a size-like term scales with it, a strain-like one does not), and names the
    `SharingMap(per_histogram=[...])` glob that unshares them. Silent with one wavelength,
    an unshared or parametric coefficient, or an `intensity_factor`. Practice, in the
    guide: TOPAS writes such a term per pattern or with `Lam` in the expression. Audit,
    help, silence-pair and skill rows added. (2) `QPA_INTENSITY_FACTOR` reworded in the
    maintainer's words. The code multiplies intensity by scale × factor, so the fitted
    scale absorbs 1/mean factor: the message now says the fraction is *too high* by
    1/mean where the mean is below 1, and *too low* above 1. The maintainer's draft
    suggestion said "divide this phase's scale by 0.83"; the code's direction makes the
    correction a multiplication, so the suggestion says "multiply this phase's scale by
    0.74" (its real mean on the test fixture). The help entry and guide had the
    direction backwards ("about 0.7 of what it would be"), and both now agree with the
    code.
  - *Settled by the lead, 2026-11-20.* (3) `orbit_mean` and `harmonic` are refused where
    an expression is parsed, with code `unbound`, naming the function and saying it reads
    a reflection. `Expression(text)` refuses them, and only the peak equation's compile
    passes `reflection=True`, so a tie, a variable and a `ParametricEquation` each refuse
    them at declaration. `tests/test_peak_equations.py` holds all three surfaces.
  - *Left open.* (2) The LM driver's width inequalities read the built-in terms alone.

- **2026-11-19 (the ruling)** — The maintainer ruled on 2026-11-19 on the 2026-11-17
  decision. **Option A**: a peak equation is a field on the model. No objection was raised
  to the five consent items, so each stands as written below. Ruled by the maintainer
  2026-11-19.
  1. The type is `rx.PeakEquation(target, expression, coefficients)`. The fields are
     `Phase.peak_equations` and `Instrument.peak_equations`. Each level holds at most one
     equation per target. Paths use the list index.
  2. The five targets and their units stand: `lor_fwhm`, `gauss_fwhm`,
     `gauss_fwhm_squared`, `shift` and `intensity_factor`. The instrument level takes
     `shift` only.
  3. The reflection names are `h`, `k`, `l`, `m`, `d`, `theta` and `two_theta`. A
     coefficient may take none of them, and may not be called `scale`.
  4. `orbit_mean` and `harmonic` join the grammar, and `GRAMMAR_VERSION` moves 1 → 2.
  5. In a joint fit a coefficient varies through a `ParametricEquation` whose target is
     its path.

  The maintainer also confirmed that the 2026-11-05 tie-family ruling on WP-1964 does not
  cover a peak equation. That ruling governs a formula that makes an existing parameter
  follow something. A peak equation adds a physical term. Nothing is built. Next: the
  Compile task, the first that builds anything, on the surface named above.

- **2026-11-17 (a ghostshift runner; PR #1635)** — Nothing is built yet. The first task
  names a field on `Phase` and a top-level type, so it is the maintainer's to rule, and
  every later task builds on the field it names. This session read the seams and the
  rulings the surface rests on, and wrote the decision below with the call each option
  produces. The stored-format task rides on the same answer.
  - *Decision for the maintainer: where a peak equation is declared.* It reaches you as
    a new field and a new top-level name on the main surface.
    - **Why it matters.** A peak equation adds a term to each reflection's width or
      position, or multiplies its intensity, as `Phase.microstrain` and `Phase.texture`
      already do with built-in forms. Its coefficients must be ordinary parameters of
      the phase (§ Rules this WP inherits), so they get bounds, esds, holds and sharing
      like any other. Where the equation is declared decides whether those coefficients
      travel with the model. A series carries the models from pattern to pattern, and a
      fact kept only in the refinement's own record reaches pattern 1 and nothing after
      (root CLAUDE.md, WP-1441). A joint fit takes structures and instruments, and
      shares a phase's parameters across patterns by default while an instrument's stay
      per pattern (`params/multi.py` `SharingMap`). Importance: moderate. The choice is
      cheap to change before anyone stores a file, and costly after.
    - **Aim.** Machinery for the expert who writes their own model, ported from TOPAS by
      an agent (the 2026-11-03 and 2026-11-04 rulings). The milestone's ZrP₂O₇ row is the
      first case.
    - **The worked case.** ZrP₂O₇'s 2θ calibration curve on the whole pattern, and Stinton
      & Evans's extra Lorentzian width on 0kl reflections. Names below are illustrative
      until ruled.
    - **Option A, a field on the model** (the WP's placeholder):

      ```python
      phase.peak_equations = [rx.PeakEquation(
          target="lor_fwhm", expression="if(h == 0, w, 0) * tan(theta)",
          coefficients={"w": rx.Parameter(value=0.01, vary=True, min=0.0)})]
      instrument.peak_equations = [rx.PeakEquation(
          target="shift", expression="sq * (two_theta - 60)^2 + ln * (two_theta - 60)",
          coefficients={"sq": rx.Parameter(value=0.0, vary=True),
                        "ln": rx.Parameter(value=0.0, vary=True)})]
      ```

      The coefficients are entries at `phases.0.peak_equations.0.w` and
      `instrument.peak_equations.0.sq`. A series carries them, a joint fit shares `w` and
      keeps `sq` per pattern unless `SharingMap(shared=...)` says otherwise, and the model
      JSON and the `.rxt` text show them. Cost: one additive field on `Phase` and one on
      `Instrument`, defaulted to `[]`. Under the 0.25 → 0.26 rule that is "Also in 0.61"
      (1.12 has not shipped), and an older build refuses a file that carries one.
      `gui/textdoc.FORMAT_VERSION` moves 1 → 2 for the new block. Undoable until a release
      stores one.
    - **Option B, a command in the tie family:**

      ```python
      ref.add_peak_equation(phase=0, target="lor_fwhm",
                            expression="if(h == 0, w, 0) * tan(theta)",
                            coefficients={"w": 0.01})
      ```

      The equation lives in the refinement's record, as ties and variables do. The
      models stay unchanged. Cost: a new record fact and history node kind. A series
      then carries the equation nowhere until someone builds it the path WP-1441 says is
      missing. A joint fit needs its own argument, since `refine_multi` takes models.
    - **Option C, park the WP.** Neither curve can be written, and the ZrP₂O₇ row ports
      without its calibration curve.
    - Dropped: reusing `ParametricEquation`. It indexes patterns, and a peak equation
      indexes reflections. One type carrying both indices would make every validator ask
      which one it holds.
    - **Practice** (`docs/practice.md` § An equation over a reflection, checked
      2026-11-04, plus recall). TOPAS writes the equation as a keyword at the level it
      acts on: `th2_offset` on the pattern, `lor_fwhm` inside the phase. FullProf chooses
      a closed model by an integer in the phase. Both put the declaration in the model,
      which is option A. rietx's own precedents agree: `Phase.texture` keeps its
      coefficients as a `dict[str, Parameter]` inside the block (paths
      `phases.0.texture.c4_1`), and `Instrument.extra_components` is a list addressed by
      index (`instrument.extra_components.0.fwhm`).
    - **A ruling that reads the other way.** On WP-1964 (decision (a), 2026-11-05) you
      ruled that a formula in a single refinement is declared by a command in the tie
      family, "never by a field on the parameter". Its grounds were that one place
      declares what a parameter follows. A peak equation makes no existing parameter
      follow anything. It adds a physical term, as `microstrain` does. So the ruling
      does not cover it on my reading. If you meant it to cover every formula a user
      writes, option B follows.
    - **Recommendation: option A, a lean towards a clear call.** The crux is whether the
      coefficients are model values. Under A they behave like every other phase
      parameter with no new path. Under B a series and a joint fit each need one built,
      and the series half is the absence the root CLAUDE.md already warns about. This
      flips if your WP-1964 ruling was meant to cover any user formula.
  - *Consent list, if option A stands.* Each stands unless you object.
    1. The type is `rx.PeakEquation(target, expression, coefficients)`, mirroring
       `ParametricEquation(target=, expression=)`. The fields are `Phase.peak_equations`
       and `Instrument.peak_equations`. At most one equation per target per level, since
       a sum goes in one expression. Paths use the list index, as `extra_components`
       does. That has one trap. Deleting an equation renumbers the later ones, so a
       stored hold on `peak_equations.1.*` then names another equation.
    2. Targets, in the package's words and units. `lor_fwhm` adds to the Lorentzian FWHM
       in degrees 2θ. `gauss_fwhm` adds in quadrature, in degrees. `gauss_fwhm_squared`
       is a signed term in deg², added where U, V and W are. `shift` is degrees 2θ added
       to the position. `intensity_factor` multiplies the reflection's intensity. The
       instrument level takes `shift` only and reads no hkl. The manual's table maps
       TOPAS's keywords onto these.
    3. Reflection names, bound only inside a peak equation and reserved nowhere else.
       `h`, `k`, `l`, `m` (multiplicity) and `d` (Å), plus `theta` in radians, so that
       `tan(theta)` works under the grammar's radians-only trigonometry, and `two_theta`
       in degrees, the position before the equation acts, as every rietx 2θ is. A
       coefficient may not take one of these names. Nor may it be called `scale`, which
       `SharingMap` would make per pattern by its suffix.
    4. Two grammar functions. `orbit_mean(x)` averages x over the reflection's orbit
       images. `harmonic(l, n)` is Bunge's symmetrised spherical harmonic K_l^n of the
       reflection's direction, named as `crystallography/spherical_harmonics.py` names
       texture terms. Both move `GRAMMAR_VERSION` 1 → 2, which `capabilities()` quotes.
    5. A pattern's coordinate is not read inside a peak equation. In a joint fit a
       coefficient follows a coordinate through a `ParametricEquation` whose target is
       its path, such as `phases.0.peak_equations.0.w`. That is one mechanism where the
       task "A joint fit" asked for two.
  - *Gotchas.* The WP's line numbers have drifted, but the names still hold:
    `generation_window` is now called at `model/forward.py:4367`, and `_shift_est` sits at
    4347 and `_size_family` at 4478. WP-2101 (the parametric surface in the manual) is
    held by another runner, so the manual task here coordinates with it.
  - *Next.* Your ruling on the surface and on the consent list. Then the compile task,
    which is the first to build anything.

- **2026-11-04 (the ruling)** — The maintainer ruled for robust machinery with no
  overfitting to TOPAS, so this WP joined the milestone with all three targets, and the
  TOPAS oracle and the archive stopped being gates. Stinton & Evans (2007) showed a
  position curve belongs at the pattern level, which changed the design. Next: 1964's
  grammar, then the surface.
- **2026-11-04** — Filed as the scope the maintainer asked for. No open WP owned it: 2061
  owns a named anisotropic size block, 1964 and 2105 fence these equations, and 1963 is a
  kernel. Nothing is built. A scratch probe showed the seams carry such an equation, found
  the two silent failures above, and showed that a 2θ equation and an hkl equation are one
  piece of work. Next: the maintainer's ruling on the slices, then the surface.
