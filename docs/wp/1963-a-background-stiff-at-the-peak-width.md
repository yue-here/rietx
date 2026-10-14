# WP-1963 — a background stiff at the peak width, at every angle

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: — (1931 soft: its parked smoothing-strength selector waits on a criterion that does not read profile misfit as background, and this may be one)
Priority: P3 2026-10-14 — a hypothesis from arithmetic, not from a fit: no fit has measured the high-angle absorption it predicts, and `BACKGROUND_ABSORPTION` screens for that harm meanwhile

## Goal

A measured go/no-go on one question. Placing the P-spline's knots by the
instrument's peak width, or uniformly in Q, instead of uniformly in 2θ: does
it lower what the background can absorb at high angle, at the same number of
coefficients, without making the background too stiff anywhere? If it does,
the WP names the builder that ships it.

## Context

**Where this came from.** On 2026-10-14 a session was asked whether a kernel
over the x coordinate could be a background. The answer was that two of the
package's backgrounds already are kernel smoothers, with the smoothing-spline
kernel rather than a squared-exponential one.

- **arPLS** (`background/estimators.py`, `whittaker_solve`, `arpls`). The
  Whittaker smoother (W + λDᵀD)⁻¹Wy is the posterior mean of a Gaussian
  process whose prior penalises second differences (a second-order random
  walk), with W as per-channel noise weights. Measured with W = I: a row of
  the smoother matches Silverman's (1984) equivalent kernel
  ½·e^(−|u|/√2)·sin(|u|/√2 + π/4) at width h = λ^¼ channels, to 4e-5 of its
  peak. The kernel's FWHM is 50, 160 and 508 channels at λ = 1e5, 1e7 and 1e9.
  The kernel runs over channel *index*, so it is a kernel over 2θ only on a
  uniform step.
- **`BackgroundPSpline`** (`schemas/instrument.py`; rows in
  `background/models.py`). This is the same prior in reduced form. The
  penalty rows √(λm)·D₂c/σ̄ are a Gaussian prior on the coefficients, so the
  implied kernel is k(x, x′) = b(x)ᵀ(λ′DᵀD)⁺b(x′), plus an unpenalised straight
  line (D₂'s null space). Measured at the defaults: a 2-50° grid at 0.001°,
  uniform σ, `lambda_smooth` = 1, the background block alone, with the kernel
  row taken at 26°. At 8° knots (9 coefficients) the kernel FWHM is 23.5° and
  tr(H) is 3.61. At 3° knots (19 coefficients) it is 9.1° and 6.88. So the
  constant that `docs/manual/background.md` says "is not computed" (a feature
  of width W costs about λ(h/W)⁴) comes out at about **three knot spacings**
  at λ = 1.

How these numbers were made, so they can be repeated: the smoother row is
(I + λDᵀD)⁻¹eᵢ, solved sparse on 6001 channels. The P-spline's hat matrix is
H = B(BᵀB + k²D₂ᵀD₂)⁻¹Bᵀ, with B from `bspline_design_matrix`, D₂ from
`second_difference_matrix` and k from `pspline_penalty_scale`, at σ = 1.
Scratch venv, numpy 2.5.4, scipy 1.18.1, Linux.

**What follows from the kernel reading, and what does not.**

- A Gaussian process with the same kernel, written over the channels, gives
  the same estimate. The background is a linear block with a Gaussian prior,
  so integrating it out buys nothing (root CLAUDE.md, the VarPro invariant,
  WP-1125). It would cost O(N³) on about 48 000 channels.
- Learning the kernel's hyperparameters by marginal likelihood is REML on the
  P-spline. That is WP-1931's selector, parked on 2026-10-11 because on Si
  640c and LaB₆ 660a it chose a smoothing strength 50-540× below the default
  and read profile misfit as background.
- What is left is that **every current kernel is stationary in 2θ** (uniform
  knots, or channel index), while the peak width is not. The solver survey's
  §C10 (`docs/solver-survey.md`) states the rule this WP tests: the background
  must not be able to vary on the scale of a peak width. Model-discrepancy
  theory (Kennedy & O'Hagan 2001; Brynjarsdóttir & O'Hagan 2014) gives the
  reason: the prior that makes a discrepancy term identifiable has to come
  from outside the data, and here it can come from the instrument.

**The arithmetic behind the hypothesis.** Measured on the same 2-50° grid: the
share of an isolated Gaussian peak at 26° that the background block can
reproduce, g·Hg/g·g, against the peak's FWHM.

| peak FWHM | 0.0035° | 0.05° | 0.3° | 1° | 3° |
|---|---|---|---|---|---|
| 8° knots | 2.5e-4 | 3.5e-3 | 2.1e-2 | 7.1e-2 | 0.21 |
| 3° knots | 6.0e-4 | 8.6e-3 | 5.2e-2 | 0.17 | 0.47 |

The share grows roughly in proportion to the peak FWHM divided by the kernel
width. The peak width varies a lot within one pattern. On the BT-1 LaMnO₃
pattern (`tests/data/gsas2_bt1_lamno3_50K.gsas`, 3-167.75°), the Gaussian FWHM
from its instrument file's type-3 seeds (GU, GV, GW = 239.7, −298.2, 180.8
centideg²) is 0.13° at 3°, 0.094° at 63.8° (the minimum), 0.25° at 130°,
0.79° at 160° and 1.35° at 167.75°: **14×** across one scan. That is
arithmetic from `caglioti.gaussian_fwhm`, not a fit. So a uniform-knot
background should be about an order of magnitude less protective at the back
of that pattern than at its minimum. The back is also where B_iso's
information is (the exp(−2Bs²) factor). An isolated peak understates the
risk, because a dense high-angle cluster carries more low-frequency content
than one line. **None of this has been measured on a fit.** That measurement
is the WP.

**The cheap realisation needs no schema change.** `BackgroundPSpline.breakpoints`
already accepts any strictly increasing knots, and `bspline_design_matrix`
takes them as given. D₂ on the coefficients penalises curvature in the *knot
index*. So knots placed uniformly in a warped coordinate u(2θ) make the prior
stationary in u with no change to the evaluator, the penalty rows or the
Jacobian. Two warps are worth measuring:

- u = ∫ d(2θ)/Γ(2θ), which places knots a fixed number of FWHMs apart. Γ comes
  from `model/profiles/caglioti.py` (`gaussian_fwhm`, `lorentzian_fwhm`),
  combined by `model/profiles/pseudovoigt.py`'s `tch_gamma_eta`.
- u = Q = 4π sinθ/λ, which needs no profile. Air, Compton, thermal diffuse and
  amorphous scattering are smooth in Q, and size broadening is constant in Q
  (`caglioti.delta_q_fwhm`).

**Two seams to settle before a builder.**

1. `pspline_penalty_scale` takes m = N/n, the fitted channels per coefficient,
   as one mean. Under warped knots the channels per coefficient vary along the
   pattern: sparse knots at the back each hold more channels. The effective
   width in u should then drift as about (m_local/m)^(−¼). That is mild, but
   measure it, and decide whether m becomes per row.
2. Knots are model data, fixed when the background is built, while Γ refines
   during a fit. So place them once from the **declared** profile (a loaded
   `lab_calibrate` profile is the natural input), and never re-place them
   between stages. Re-placing would change what every coefficient means, and a
   history checkout would no longer restore the same curve.

**How to judge.** Never by Rwp (root CLAUDE.md: a correction's evidence is a
record field or a diagnostic). WP-1931 settled
`FitReport.background.worst_absorption` as the measure that separated its arms
(0.46 against 0.08), so read it with its path. Beside it read: B_iso and its
esd, `BACKGROUND_ABSORPTION`, and the too-stiff side, which is the off-region
χ²_red and Durbin-Watson d that `increase_background_flexibility` reports
(`docs/manual/background.md` § "What the pure number leaves to the counts").
Read the front and back thirds separately, because the warp moves flexibility
from the back to the front. Compare arms at equal coefficient count, so tr(H)
stays comparable.

**Datasets.**

- `FAP.XRA`: lab Bragg-Brentano, Cu Kα, 15-130°, run under
  `test_acceptance_fap.py`'s protocol.
- `gsas2_bt1_lamno3_50K.gsas`: CW neutron, 3-167.75°, under
  `test_acceptance_magnetic_lamno3.py`'s protocol (nuclear phase only).
- `11BM_Si640c.xy` and `11BM_LaB6_660a.fxye`: 11-BM. Their narrow ranges give
  little variation in Γ, so these are the controls where the warp should change
  nothing.
- WP-1055's over-flexible fixture (`tests/test_background_auto.py`, § WP-1055):
  synthetic, with a known B_iso of 0.5.

`rietx compare` already has a `_with_pspline` variant at 8° knots
(`viz/compare.py`). A warped twin would sit beside it, and would need its row
in `tests/test_compare_ui.py` if it lands (root CLAUDE.md, the compare rule).

**Licensing.** Concepts from the papers only. mgcv is GPL (WP-1931's note).

## Non-goals

- Choosing the smoothing strength from the data (REML, GCV): WP-1931.
- A Gaussian-process background written over the channels: the same estimate
  as the P-spline, at O(N³).
- A squared-exponential or Matérn kernel shape. Where peaks are narrow, the
  share the background can reproduce is already 1e-4 to 1e-2. Where they are
  broad (nanocrystalline), no prior shape separates a peak from a hump of the
  same width: that is identifiability, and the fit's job is to report it.
- arPLS on a non-uniform step, where index space is not 2θ: a separate
  question.
- Changing `auto_background`'s default. This WP's measurement informs that
  decision, and it is taken afterwards.

## Tasks

- [ ] Equivalent-kernel helper, test-side: kernel FWHM and tr(H) for given
      knots, smoothing strength and σ. Put the measured constant (about three
      knot spacings at λ = 1) into `docs/manual/background.md` in place of
      "not computed", citing Silverman (1984).
- [ ] Spike builder, no public API yet: knots uniform in ∫d(2θ)/Γ and uniform
      in Q, at the uniform arm's coefficient count.
- [ ] Measure each dataset under the three arms (uniform, Γ-warped,
      Q-warped): `worst_absorption` and its path, B_iso ± esd,
      `BACKGROUND_ABSORPTION`, off-region χ²_red and d, front and back thirds
      separately. Obs/calc/diff PNGs to `tests/output/`.
- [ ] Seam 1: the equivalent-kernel width in u along a warped pattern, against
      the (m_local/m)^(−¼) prediction. Decide whether the penalty scale goes
      per row.
- [ ] Decision in the handover entry. **Go** means: a public builder
      (`BackgroundPSpline.for_profile` / `for_q`, names to be decided), a manual
      equation with its `*Source:*` line, a `rietx compare` variant and its
      `test_compare_ui.py` row, and `help.py` entries for any new field. **No-go**
      means the numbers, and a line in `docs/manual/background.md` saying why
      the knots stay uniform.
- [ ] Skill: none for the measurement. On a go, the builder's row in the
      background reference, keyed by its name.

## Acceptance

The measurement table is in the handover for all five datasets under all three
arms, and the go/no-go is written with its reason. On a go, the builder's
tests and the compare row pass:

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_compare_ui.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Eilers, P. H. C. & Marx, B. D. (1996). *Stat. Sci.* **11**, 89-121
  (P-splines).
- Eilers, P. H. C. (2003). *Anal. Chem.* **75**, 3631-3636 (the Whittaker
  smoother).
- Silverman, B. W. (1984). *Ann. Statist.* **12**, 898-916 (the equivalent
  kernel of spline smoothing).
- Rasmussen, C. E. & Williams, C. K. I. (2006). *Gaussian Processes for
  Machine Learning*, MIT Press, §6.3 (splines as Gaussian processes) and §7.1
  (the equivalent kernel).
- Kennedy, M. C. & O'Hagan, A. (2001). *J. R. Statist. Soc.* B **63**,
  425-464.
- Brynjarsdóttir, J. & O'Hagan, A. (2014). *Inverse Problems* **30**, 114007.
- Caglioti, G., Paoletti, A. & Ricci, F. P. (1958). *Nucl. Instrum.* **3**,
  223-228.
- `docs/solver-survey.md` §C10 and §E8; WP-1931, WP-1055, WP-1125, WP-1454.

## Handover log

- **2026-10-14** — created. The package's two penalised backgrounds turned out
  to be kernel smoothers already, so the open question is narrower than "add a
  kernel". Their kernel has one width in 2θ while the peaks do not, and on
  BT-1 the peak width varies 14× across one scan. This WP measures whether
  matching knot spacing to peak width pays. No open WP owns knot placement:
  1931 owns how stiff the background is, chosen from the data (parked), 1542
  the Le Bail seed, and 1460 the reporting of flat directions. Next: task 1,
  then the spike.
