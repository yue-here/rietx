# WP-2107 — an equation over a reflection

Milestone: unscheduled · Status: ⬜
Track: Coming from another code
Depends on: 1964 (the grammar, evaluated on arrays)
Priority: P2 2026-11-04 — a feature the open milestone may take: ZrP₂O₇'s calibration curve and ZrMo₂O₈'s width need it, and the maintainer has not ruled on the fence

## Goal

A user writes a peak's width or position as an equation in its hkl and its angle, as a
TOPAS user writes `lor_fwhm` or `th2_offset`. Its coefficients refine with exact
derivatives, and it fits in a joint fit like any other parameter.

## Context

The `parametric` milestone fences equations over a reflection or a data point, and the
fence is provisional. This WP is the scope for lifting it, written so the maintainer can
rule on measured numbers. It sits unscheduled until that ruling.

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
| ZrMo₂O₈ (9.2) | `spherical_harmonics_hkl ahkl`, then `lor_fwhm = zeta Max(ee_2Th,0)^.5` | **this WP plus `sh`**: a tanθ width scaled by √ahkl |
| Published TOF template | Stephens macros | nothing: `Phase.microstrain` |

ZrMo₂O₈'s harmonic coefficients are fixed (`!ahkl_c00` and so on) and one number per
pattern refines. It runs 68 patterns through `num_runs`, so it is a series and no joint
fit. The first scoping read only WO₃ and ZrP₂O₇, and its statement that nothing in hand
needs an hkl equation was wrong.

The private archive of 606 inputs would settle how common these are, and it is not on
this machine (`mdfind` for a mapped file name: nothing). Its incidence has not been
measured for these keywords.

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
naming the first hkl. `orbit_mean(...)` is the way out. TOPAS's choice of image is not
established, and the oracle task finds it.

### Rules this WP inherits

- **A condition reads frozen integers only.** `h`, `k`, `l` and `m` do not move in a
  stage. A comparison on `th`, `d`, `xo` or a coefficient changes which branch a
  reflection takes during a solve, which breaks frozen-per-stage discreteness and makes
  the residual jump. It is refused, with TOPAS's spelling named in the message.
- **A coefficient is a table entry.** The forward model never reads a `vars.*` path, and
  `column_reach`, the flatness tests and the holds all rest on that (root CLAUDE.md,
  WP-1342). So an equation's coefficient is an entry under its phase. Sharing it is a tie
  to a variable or a `sharing=` entry, and the probe's direct read of `vars.*` was a
  shortcut. `Entry` bounds and `at_bound` then work unchanged.
- **Per line, never per phase.** `Th` and `Xo` differ between Kα1 and Kα2, so the
  equation is evaluated inside `_width_block` and `apparent_two_theta`. The `aniso` memo
  is line-independent and cannot hold it. `apparent_two_theta` takes no phase index today,
  and `_shift_key` and the width key must carry the coefficients.
- **Widths compose as they do now.** A Gaussian term adds in variance and a Lorentzian
  term in FWHM. `test_topas_convolves_the_written_width_lines` already holds that against
  TOPAS at zero cycles, for the width lines `write_topas_inp` writes.
- **The total width stays positive.** `Max(x, 0)` is legal and has the kink Stephens'
  clamp has. A total width at or below zero at the answer is a guard finding, and it
  cannot be a box bound since it couples the coefficients.

### Slices

1. **Width and position**, this WP. `lor_fwhm`, `gauss_fwhm` and `th2_offset` in `h`, `k`,
   `l`, `m`, `d`, `th`, `xo`, plus `orbit_mean`. It serves ZrP₂O₇ and TOPAS's own examples.
2. **The harmonic `sh`**, gated. A real spherical harmonic of the hkl direction in the
   grammar, needed by ZrMo₂O₈ alone among the inputs read.
   `crystallography/spherical_harmonics.py` holds the machinery. TOPAS's `sh_Cij_prm`
   normalisation is not established, so this needs the oracle.
3. **Intensity**, gated. The `scale_pks` analogue needs the two hand-folded builders, a
   refusal under Le Bail and Pawley, and an answer for phase fractions: a factor that is
   not normalised changes scale × ZMV (cell mass and volume) and so the QPA, with nothing
   to say so. None of the inputs read needs it, and rietx has texture natively.

## Non-goals

- A convolution by equation: `hat`, `one_on_x_conv`, `exp_conv_const`, `circles_conv`,
  `stacked_hats_conv`, `user_defined_convolution`.
- `pk_xo`, `modify_peak_eqn`, `h1`, `h2`, `m1`, `m2`, `la`, `lo`.
- An equation reading a structure factor (`A01`, `B01`) or an intensity.
- `fit_obj`: an expression member of `extra_components`, and not this seam.
- A time-of-flight bank. `th` and `xo` mean nothing there, so a peak equation is refused
  by name until someone asks for one in `d`.
- Anisotropic size as a named block: [2061](2061-a-crystallite-has-a-shape.md), which
  derives its subspace from the operators. A user can write such a form here without
  that guarantee.

## Tasks

- [ ] **The surface.** A consent item for the maintainer, since it names a field on
  `Phase` and a top-level type. `rx.PeakEquation(target=..., expression=...)` is a
  placeholder. The target names need the field's words. TOPAS's are the candidates.
- [ ] **Stored format.** A `Phase` field is a stored-format change, so it goes to the
  maintainer with the version it bumps. `.rxt` rendering, `help.py`, `capabilities()` and
  the `rietx._audit` rows follow.
- [ ] **Compile.** Freeze `h`, `k`, `l`, `m` on `CompiledPhase`. Evaluate on every orbit
  image and refuse a disagreement, with `orbit_mean` as the exit. Refuse a moving
  condition. Teach `_shift_est` and `_size_family` the equation, and pin the windows with
  the probe's number.
- [ ] **Forward.** Width in `_width_block`, position in `apparent_two_theta` with its
  phase index, and every memo key. Check `reflection_positions`, the ticks and the
  exporters' reflection table read the same answer.
- [ ] **Derivatives.** An exact branch for a coefficient, reached through
  `scalar_chain_supported` and the extras gate. `test_cross_backend.py` gains a row, and
  the oracle follows the invariant on exactness.
- [ ] **The guard.** A total width at or below zero at the answer.
- [ ] **A joint fit.** An equation on each table, a coefficient shared across patterns,
  and a pattern's coordinate readable in the expression.
- [ ] **TOPAS as an oracle.** Synthetic inputs at zero cycles on the licensed VM, the way
  `topas_export_widths_str_ycalc.txt` was made. Cover `If(L==0)` on a width, the ZrP₂O₇
  curve on a doublet source, and a non-invariant condition with and without
  `Multiplicities_Sum`. That settles the image TOPAS holds and whether `Xo` is per line.
- [ ] **The reader.** 2105's dropped-with-its-size rows for these lines become readings.
- [ ] **Manual and skill.** A guide page, `reference/parametric.md`, the Theory tab's
  equation, the skill's row.
- [ ] **Decide slices 2 and 3** from the archive's incidence, if it can be reached, and
  file them or fence them.

## Acceptance

Over 12 pinned seeds on a synthetic phase, every coefficient of a width and a position
equation has a mean z-score under 0.5 in size. Each equation's Y_calc matches TOPAS's
zero-cycle output within the bar `test_topas_convolves_the_written_width_lines` uses. The
milestone's ZrP₂O₇ row runs with the input's `th2_offset` curve free.

```sh
.venv/bin/python -m pytest tests/test_parametric_series.py tests/test_cross_backend.py tests/test_projects_topas.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* 51, 210-218 — TOPAS and TOPAS-Academic.
- Stephens, P. W. (1999). *J. Appl. Cryst.* 32, 281-289 — the template for a width in hkl.
- TOPAS Technical Reference v8, Table 2-3 and § 20.17; FullProf manual § Selective size
  broadening.
- WP-1964 (the grammar), WP-0503 (Stephens), WP-1102 (the expression clause), WP-2061.

## Handover log

- **2026-11-04** — Filed as the scope the maintainer asked for. No open WP owned it: 2061
  owns a named anisotropic size block, 1964 and 2105 fence these equations, and 1963 is a
  kernel. Nothing is built. A scratch probe showed the seams carry such an equation, found
  the two silent failures above, and showed that a 2θ equation and an hkl equation are one
  piece of work. Next: the maintainer's ruling on the slices, then the surface.
