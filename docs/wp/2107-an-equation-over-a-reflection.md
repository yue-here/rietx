# WP-2107 — an equation over a reflection

Milestone: parametric · Status: ⬜
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

- [ ] **The surface.** A consent item for the maintainer, since it names a field and a
  top-level type. `rx.PeakEquation(target=..., expression=...)` is a placeholder. The
  target names follow the package's own words (`lor_`, `gauss_`, position), and the
  manual's table maps TOPAS's onto them.
- [ ] **Stored format.** A `Phase` field is a stored-format change, so it goes to the
  maintainer with the version it bumps. `.rxt` rendering, `help.py`, `capabilities()` and
  the `rietx._audit` rows follow.
- [ ] **Compile.** Freeze `h`, `k`, `l`, `m` on `CompiledPhase`. Evaluate on every orbit
  image and refuse a disagreement, with `orbit_mean` as the exit. Refuse a moving
  condition. Teach `_shift_est` and `_size_family` the equation, and pin the windows with
  the probe's number. `generation_window` runs before reflections exist
  (`forward.py:4133`), so a phase-level position in hkl needs a bound over the expression
  that takes no reflection list, or a margin stated and tested.
- [ ] **Forward.** Width in `_width_block`, position in `apparent_two_theta` with its
  phase index, and every memo key. Check `reflection_positions`, the ticks and the
  exporters' reflection table read the same answer. `apparent_two_theta` also takes arrays
  that are no reflection list (`report/satellites.py`, `refine.py:11552`), so those callers
  read the pattern level or refuse. Width readers outside `_width_block` follow too
  (`refine.py:11342`, `report/strain.py:120`, `io/exporters.py:362`).
- [ ] **Derivatives.** An exact branch for a coefficient, reached through
  `scalar_chain_supported` and the extras gate. `test_cross_backend.py` gains a row, and
  the oracle follows the invariant on exactness.
- [ ] **The guard.** A total width at or below zero at the answer.
- [ ] **A joint fit.** An equation on each table, a coefficient shared across patterns,
  and a pattern's coordinate readable in the expression.
- [ ] **Intensity.** The third target, the two hand-folded builders, the Le Bail and Pawley
  refusal, and the QPA diagnostic with its row in `rietx._audit`.
- [ ] **The harmonic.** A symmetric function of hkl in the grammar, with its derivative.
- [ ] **An independent check.** Each target against a built-in with the same physics,
  so no code is shared with what it certifies: `y*tan(th)` against `lor_strain`, a cosθ
  position against sample displacement, an exponential in s² (sinθ/λ squared) against
  Biso. A variance term against the instrument's U, V and W. TOPAS at zero cycles is a
  welcome extra if a run is cheap, and no gate.
- [ ] **Manual and skill.** A guide page, `reference/parametric.md`, the Theory tab's
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
