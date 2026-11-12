# What the other Rietveld programs do

A standing reference: what established programs do by default, by topic, each claim cited and
marked checked (read in the source or manual), ran (measured) or inferred. Read it before
designing a default, a limit or an automatic action, since tier 2 of the audit rule rests on
it (`docs/milestones/generality.md` § The rule). Add a section after every survey, rather
than leaving one in a conversation or a WP's batch directory.

The seven programs are the ones rietx-bench runs: GSAS-II 5.8.4 (source), FullProf 8.20 (manual
and `fp2k` runs), TOPAS Technical Reference Version 9 (no source or `Topas.inc` read), RIETAN-FP
3.12 (manual and runs; its licence forbids copying, so it is paraphrased), BGMN 4.2.23 with
Profex 5.7.2 (manual, Profex docs and templates, runs; GPL, so no source), MAUD 3.07 (BSD-3
source at the tag) and EasyDiffraction 0.21.1 with cryspy 0.13.0 (source). Where each sits on
disk is in the maintainer's memory (`foreign-code-sources-on-disk`).

The first sections were surveyed 2026-10-21 for WP-2002's fifth round, one agent per program,
with the load-bearing numbers checked by the lead. Each later section carries its own date.

## How far a peak is computed

The Lorentzian column is the area a pure Lorentzian loses to the default cut.

| Program | Default cut | Lorentzian area lost | When the window is set |
|---|---|---|---|
| rietx | `WINDOW_AREA_TOL`, 2 % of each peak's own area | 2 % | once per stage, at the stage's start (checked) |
| TOPAS | `ymin_on_ymax` 0.001 of the strongest line's height | 2.0 % | peak buffer rebuilt when a width moves past `aberration_range_change_allowed`, and per derivative for width parameters (§7.4, §7.7, checked) |
| MAUD | ±30 HWHM (±15 FWHM) | 2.1 % | every evaluation, finite-difference columns included (checked) |
| RIETAN-FP | `PC` 0.002 of each peak's own height, in three of four shipped examples; no default | 2.8 % | every evaluation (ran) |
| FullProf | `Wdt` × FWHM each side; no default, floored at 3; examples 3-15, PbSO₄ 6 | 5.3 % at 6 (10.5 % at 3, 2.1 % at 15) | once per run, at the starting widths (`Ias = 0`, ran); `Ias = 1` lags one cycle |
| GSAS-II | 50 FWHM below, 75 above | 0.53 % | every evaluation (checked) |
| BGMN | no cut seen out to 22° from a peak | ~0 | not documented |
| EasyDiffraction | none (cryspy sums every reflection over every point); the crysfml calculator uses 30 FWHM | 0 (1.1 %) | every evaluation (checked) |

## Axial divergence quadrature

| Program | Method |
|---|---|
| rietx | FCJ, node count from `NODES_PER_FWHM` etc., frozen per stage |
| GSAS-II | FCJ, Gauss-Legendre per profile point, count from the angular gap over the width, rounded up to a table, capped at 400; single precision (checked) |
| RIETAN-FP | FCJ, Gauss-Legendre per reflection, 10 to 100 nodes; Howard's model by Simpson with 3 to 9 terms (checked) |
| TOPAS | `axial_conv` (Cheary & Coelho 1998) by `axial_n_beta` rays, no printed default |
| FullProf | FCJ under `Npr = 7`; quadrature not documented |
| MAUD, EasyDiffraction (cryspy) | no FCJ; an empirical or Bérar-Baldinozzi asymmetry |
| BGMN | ray-traced instrument function, computed once before the fit and held |

## Axial divergence at zero, and whether a refine flag reaches the calculation

Surveyed 2026-10-25 for WP-1421 (#774's zero case). rietx sizes the FCJ nodes and the peak
window as if S/L = H/L = 0.02 when both sit at zero and either is free, so that a refinement
starting from zero has a live finite-difference column. A model at zero therefore draws a
curve that depends on its free set, by 4.8e-5 of the strongest peak on 2026-10-25 (1.66e-4 on
2026-10-16), measured on #774's rutile reproducer.

| Program | At zero | Does a refine flag reach the profile? |
|---|---|---|
| rietx | FCJ off when both are 0; sized at 0.02 when free (`forward.AXIAL_SIZING_FLOOR`) | yes, at exactly zero only |
| GSAS-II | never computed: one parameter SH/L = (S+H)/L, floored at 0.002 by value for the profile and its window at every evaluation, refined or not; the Fortran's zero branch gives a stand-in derivative of 0.002·sign(Δ2θ) (checked) | no; windows come from values each evaluation |
| RIETAN-FP | not described; Gauss-Legendre N between 10 and 100 "depending on τmin", which follows rs and rd (§3.10.3, checked) | no flag named; the count follows the values |
| FullProf | not described; S_L and D_L act only below `AsymLim`, an angle (LINE 30 notes, checked) | no flag named |
| TOPAS | not read this session | not read this session |

No program read makes a calculation depend on whether a parameter is refined. GSAS-II avoids a
zero state by flooring the physics itself, and its zero branch, never reached through the
profile call, carries a stand-in slope.

GSAS-II 5.8.4 sources: the floor at `GSASIIstrMath.py:3980` (profile) and `:4309`
(derivatives), 0.0005 at `:3723` (`GetFobsSq`); the window `GSASIIpwd.getWidthsCW`
(`GSASIIpwd.py:811-832`) widens its low-angle side by 50·SH/L·|cos 2θ|; the zero branch and its
stand-in derivative in `sources/powsubs/psvfcjo.for:139` and `:288-299`.

## Reflections past the fitted range

| Program | Margin |
|---|---|
| rietx | `REFLECTION_MARGIN_DEG` 0.5° each side |
| TOPAS | `extra_X_left`, `extra_X_right` 0.5° each side (checked) |
| GSAS-II | none: a reflection must lie strictly inside the limits (checked) |
| RIETAN-FP | none: a reflection centred outside is dropped with its tails (ran) |
| FullProf | 3 × `Wdt` × FWHM above the upper limit (1.8° on PbSO₄); none below the lower (ran) |
| MAUD | `cutoff` × 0.1°, 3° at the default (checked) |
| EasyDiffraction | 4° in 2θ each side of the included points (checked) |
| BGMN | about the Kα₁-Kα₂ split, 0.05° at 30° to 0.6° at 150° (ran) |

## Staging and what a stage holds

| Program | Staging | Held during a fit |
|---|---|---|
| rietx | plans of cumulative stages; a stage may also fix (WP-2208); the closing stage re-solves the declared stages' end state | reflection list, windows, FCJ nodes: per stage |
| RIETAN-FP | `NAUTO = 2`: early cycles refine subsets (background and scale; widths; asymmetry; widths and asymmetry; cell; atoms), then everything together to convergence. `NAUTO = 1`: the user lists the early cycles | windows follow every evaluation; Le Bail intensities per cycle |
| BGMN | automatic: isotropic models first, anisotropic ones added, then a closing run with everything free restarted from the answer; a weak anisotropic term is switched off | the ray-traced instrument function for the whole fit |
| MAUD | the refinement wizard: cumulative stages (scales and background; cell, zero, B; size and strain; atoms), no final all-free cycle | windows follow every evaluation; texture, strain, Le Bail intensities and structure factors per iteration |
| FullProf | none; the user runs successive files in the manual's advised order | windows and point assignment for the whole run (`Ias = 0`) |
| GSAS-II | none; scripting takes a user list | the reflection list per `Refine` call; windows every evaluation |
| TOPAS | none; `_rem` and `quick_refine` drop parameters for an iteration | the peak buffer up to its tolerances |
| EasyDiffraction | none | nothing: reflection list and windows rebuilt every evaluation |

None of the seven tests whether its answer depends on the path or the start, and none of
their manuals discusses it.

## A site's multiplicity during a fit

Surveyed 2026-10-26 for WP-2052 (issue #1088); the GSAS-II lines re-read 2026-11-01.

| Program | When a site's multiplicity is decided | Status |
|---|---|---|
| rietx | once per `fit()` or `run_stage()`, from the coordinates the call starts at; every stage compile and the closing compile reuse it, and `SITE_MULTIPLICITY_KEPT` names a site the returned coordinates would recount | checked |
| GSAS-II | once, at setup: `Amul` is read from the stored atom record (`GSASIIstrIO.py:1762`) and the structure factor weights every operation by `Mult·frac/nOps` (`GSASIIstrMath.py:1279`); it is rewritten only when the user edits or transforms the atom. Because every operation is summed at that weight, a site that leaves a special position keeps `Mult·frac` atoms per cell; rietx gives such a site its full orbit at its occupancy, as it did before WP-2052, and only a rigid body's pose reaches that case | checked (5.8.4 source) |
| TOPAS, FullProf, RIETAN-FP, BGMN, MAUD, EasyDiffraction | | not checked |

## Surface roughness starting values

| Program | Pitschke | Suortti | Default start |
|---|---|---|---|
| rietx | `RoughnessPitschke` | `RoughnessSuortti` | c and b seeded at 0.3 by the roughness stage |
| RIETAN-FP | yes | yes (and Sparks, Sidey) | none given |
| FullProf | the P₀, Cp, τ form | no | none; shipped examples start Cp 1.23-1.50, τ 0.134-0.145 |
| TOPAS | `Surface_Roughness_Pitschke_et_al` | `Surface_Roughness_Suortti` | not in the reference (in `Topas.inc`, not read) |
| GSAS-II | no | `SurfaceRough` | SRA = SRB = 0, not refined |
| BGMN, MAUD, EasyDiffraction | no | no | |

## Peak-width limits

| Program | U, V, W, X, Y limits | Negative width | Sample-broadening limits |
|---|---|---|---|
| rietx | floors only since 2026-10-21 | Γ_G² clamped at 1e-8 deg² | `lor_size` etc. by their own schema |
| GSAS-II | none | Gaussian variance and Lorentzian width floored per reflection | none |
| FullProf | none | Γ_G set to 1e-10 with a message; peaks vanish (ran) | none |
| RIETAN-FP | none | refused at the start; a step to one is rejected | none |
| TOPAS | no u-y rows in Table 2-1; opt-in `force_positive_fwhm` | undocumented | `CS_L` 0.3 nm to min(2·Val + 0.3, 10 000) |
| MAUD | ±0.5, ±0.3, ±0.1 on U, V, W, not enforced by its least squares | floored at 1e-7° | size 50-5000 Å, strain ≤ 0.005, not enforced |
| EasyDiffraction | none | H_G² floored at machine ε; a negative H_L passes | none |
| BGMN | no Caglioti widths | fatal error | Profex writes B1 ≤ 0.01 and k2 ≤ 1e-4 into the files it creates |

## Limits a control file declares

Checked 2026-10-30 for PR #1199 (the `.pcr` reader's `Nre` limits), FullProf only.

FullProf's hard limits (`Nre` > 0, one LINE 47 per limit) clamp in least squares, not only
in simulated annealing (ran). On FullProf's own `ce1.pcr` (`Cry = 0`, which ships two limits),
a limit of [5.400, 5.405] Å on cell a, below its converged 5.41222(3), held a at 5.40500(3)
from the first cycle. The volume went from 158.536 to 157.902 Å³. The `.out` file lists the
limits it read and converts a cell limit to its internal metric. A limit applies to the first
value carrying its codeword, and that value must have a positive sign and a unit multiplier.
Other values tied to it follow through their multipliers (manual § Hard limits for parameters,
LINE 47; checked). The periodic boundary type (`IBOUND = 1`) was not tested. MAUD's declared
limits are not enforced by its least squares (§ Peak-width limits above). The other five
programs were not surveyed for this.

## Instrument and specimen widths refined together

Read 2026-10-23 (WP-2002, 8th session), after removing rietx's U and Y floors exposed the
degeneracy those floors had been breaking. An instrument width coefficient and a specimen
broadening term with the same angular shape are exactly degenerate when both are free: the data
fix only their sum. The pairs, in each program's own letters, follow from the formulas cited
below. Gaussian, in the variance: the instrument's tan²θ term (U) and the specimen's Gaussian
microstrain; and where a program has a 1/cos²θ instrument term (FullProf's IG, TOPAS's Z), the
Gaussian size. Lorentzian, in the width: the instrument's tanθ term and the specimen's Lorentzian
microstrain, and the instrument's 1/cosθ term and the Lorentzian size. FullProf and
EasyDiffraction call the tanθ Lorentzian term X and the 1/cosθ one Y; GSAS-II, RIETAN-FP and
rietx call them the other way round, Y and X. In GSAS-II a microstrain's Gaussian part enters
the variance squared, so it goes as tan²θ like U.

| Program | Positivity enforced on | Both twins refined together | Instrument function alone kept positive |
|---|---|---|---|
| GSAS-II 5.8.4 | the total width, `max(0.001, …)` per reflection (`GSASIIstrMath.py:3900-3903`) | no check pairs instrument and sample flags (grep of five modules); size and mustrain refine flags off by default (`GSASIImath.py:6295-6298`), `.instprm` widths off (`GSASIIfiles.py:531`); singular parameters dropped and pairs above 0.95 listed after the fit (`GSASIIstrMain.py:54-139`) | no |
| FullProf 8.20 | the user's | structural: with a resolution file (IRF, `Res=`) the instrument lives there and the `.pcr` terms "have a meaning" as sample size and strain, V and W to be fixed at zero (manual p. 21, p. 51); the shipped `cuf1k.pcr` holds U, V, W, X at 0 and refines Y with the Stephens terms; without an IRF, only the general advice to refine correlated parameters separately (p. 14); size and strain last in the advised order (p. 13) | no |
| RIETAN-FP 3.12 | refuses a negative width | manual: U, V, W do not converge stably together and adding P makes the matrix singular; fix V and W from a well-crystallised standard with P = 0, then subtract the standard's U and Y by hand to read strain (manual pp. 35, 106-107; paraphrased, its licence forbids copying) | no |
| TOPAS v9 | opt-in `force_positive_fwhm`, on the convolution widths (§7) | nothing in the reference; no default limits on u-z (Table 2-1); the `CS_*`/`Strain_*` macros are exact twins of the TCHZ terms (§7.2, §22.1); nothing refines unless marked (§2.1) | no |
| BGMN 4.2 | B1 cannot be negative; bounds by `start_lower^upper` (§4.2, App. A.4) | impossible by design: the instrument function is ray-traced or learnt from a standard (`STANDARDPAR`, §10.3) and has no refinable width, which the manual calls the reason the refinement is robust (§5.5) | not refinable |
| MAUD 3.07 | the total half-width, floored at 1e-7° (`InstrumentBroadening.java:45-46`) | nothing (grep of the tree; `FilePar.checkBound` is a stub); help text says free U, V, W by hand after one cycle; Delft strain is Gaussian in tanθ, so it twins the instrument's tan²θ variance term (`SizeStrainDelf.java:57-65`) | no |
| EasyDiffraction 0.21.1 | H_G² floored at machine ε; H_L unfloored (`cryspy/.../powder_diffraction_const_wavelength.py:122-123`) | no constant-wavelength sample term to pair (`easydiffraction/analysis/calculators/cryspy.py:849-854`); cryspy's own per-phase terms add to the instrument's and are degenerate by construction; correlations shown on request only; every parameter starts fixed (`core/variable.py:46-49`) | no |

**The practice.** No program floors an instrument coefficient, and none keeps the instrument
function alone positive; positivity, where enforced, is on the total width. None refuses, warns
about or automatically holds a twin pair. Every program that separates instrument from specimen
does it by holding the instrument from a standard: FullProf (the IRF) and BGMN (ray tracing) by
design, RIETAN-FP by its advised protocol, GSAS-II through defaults that leave the sample terms
off. Three readers checked every citation above in the source or manual on 2026-10-23; their
scratch copies were not kept. The claims they marked inferred are TOPAS's quadrature/linear
combination rule (not stated in the reference), the scope of `force_positive_fwhm`, and
FullProf's constant-wavelength combination rule with an IRF.

## Extinction

Surveyed 2026-10-24 for WP-2044, one agent across six programs, with each
load-bearing line re-read by the lead. Sabine's powder model is
E = E_L·cos²θ + E_B·sin²θ. Its Laue half E_L is printed as a series for x ≤ 1
and an asymptote above (Sabine, Von Dreele & Jørgensen 1988, eqs 3-4; ITC C
§6.4.5). Both truncate e^(−x)·[I₀(x) + I₁(x)], the integral ITC describes,
checked by quadrature in WP-2044. The table gives each program's value of E_L
on either side of x = 1.

| Program | Powder extinction model | E_L at 1⁻ / 1⁺ | Derivative |
|---|---|---|---|
| rietx (to 1.9) | Sabine, GSAS-II's branches | 0.6742 / 0.6981, +3.6 % | forward difference (checked) |
| Sabine's paper, ITC C | series and four-term asymptote | 0.6823 / 0.6678, −2.2 % | — |
| exact (WP-2044) | e^(−x)·[I₀ + I₁] | 0.6737, continuous | dE_L/dx = −e^(−x)·I₁/x |
| GSAS-II | Sabine: six-term series, two-term asymptote, switch at x = 1 | 0.6742 / 0.6981, +3.6 % | analytic per branch (checked) |
| MAUD | Sabine: the paper's series, and its asymptote with the bracket inside the square root, switch at x = 1 | 0.6823 / 0.7299, +7.0 % | none in the class, so numerical (inferred) |
| TOPAS | no keyword; §16.6 suggests an empirical `scale_pks = 1/Sqrt(1 + 1e-5·extinction·I)`, with no angle dependence | — | numerical for an expression (inferred) |
| FullProf | one empirical powder parameter (`Extinc`, the SHELX-style form); `Ext-Model` is single-crystal only | — | not found |
| EasyDiffraction (cryspy) | Becker-Coppens, single crystal only; no powder use found | — | analytic |
| RIETAN-FP | none (the manual calls secondary extinction negligible for powders) | — | — |
| BGMN | none found in the keyword table | — | — |

No program evaluates E_L continuously. The two that carry Sabine's E_L both
switch branches at x = 1, and neither gives a reason. TOPAS's expression
language has no modified Bessel function (Table 3-1; "there is no Bessel
function", near §16 on modulated structures). Its functions are Sqrt, Exp, Ln,
the trigonometric and hyperbolic functions, the Erf, Erfc and Gamma
approximations, Abs, Min, Max, Mod, Round and Sign, with If, For and Sum.

Sources: GSAS-II `GSASIIstrMath.GetPwdrExt` and `GetPwdrExtDerv`. MAUD
`src/it/unitn/ing/rista/diffr/sfm/ExtinctionSabineModel.java:140-146`, with the
same constants in the 3.07 jar by `javap`. TOPAS Technical Reference v9 §16.6
and Table 3-1. FullProf manual, the scale line's `Extinc` and the `Ext-Model`
entry in the 2002 news. cryspy 0.13.0 `A_functions_base/extinction.py`, and
EasyDiffraction `analysis/calculators/cryspy.py:1575-1576` ("single crystal
only"). RIETAN-FP 3.12 manual, by full-text search (one hit, on secondary
extinction). BGMN by the binary's keyword table, with no manual
installed.

### Is powder extinction refined unasked?

Surveyed 2026-11-03 for WP-1944 (issue #877), on whether a structural
refinement frees extinction by default.

| Program | Where the parameter lives | Refined by default | Mark |
|---|---|---|---|
| GSAS-II 5.8.4 | every phase-histogram pair carries `'Extinction': [0.0, False]` | no; the user ticks it | checked: `GSASIIddataGUI.py:1436`, `GSASIIphsGUI.py:9412`, `GSASIImath.py:6300` |
| FullProf | `Extinc` on each phase's scale line, with its own codeword | no; a codeword of 0 holds it, and nothing turns it on unasked | recall, not checked |
| TOPAS | no keyword (table above) | nothing to refine | checked, table above |
| RIETAN-FP | none (table above) | nothing to refine | checked, table above |
| BGMN | none found (table above) | nothing to refine | checked, table above |

No program surveyed refines powder extinction unless the user asks. GSAS-II
matches rietx's data shape: the parameter exists on every phase at 0. It
differs in the refine flag. None of these programs ships a staged plan, so
none has a stage that could free it on the user's behalf.

## A sharp peak no phase accounts for

Surveyed 2026-10-25 for WP-2036, on what `tests/test_acceptance_extra_peaks.py` should assert.

- McCusker et al. (1999), *J. Appl. Cryst.* 32, 36, checked. §12.6: small unindexed peaks
  found in other preparations too are probably not an impurity, though they may be the
  sample holder's. Peaks that vary between preparations probably belong to a second phase,
  which is identified and refined as a second phase where its structure is known. The paper
  never recommends excluding the region, and quantifies no bias from leaving a peak
  unmodelled. §10: e.s.d.'s assume counting statistics are the only error, and "reflect the
  precision of the refined parameters and not their accuracy". An unmodelled peak is a
  systematic error of the kind they say an e.s.d. cannot estimate.
- GSAS-II 5.8.4, checked: background peaks, each with a refinable position, intensity and
  Gaussian and Lorentzian width (`BkPkpos`, `BkPkint`, `BkPksig`, `BkPkgam`;
  `GSASIIpwd.py:1093-1096`), are the same mechanism as a declared extra peak.
- TOPAS, not read this session: `xo_Is` single peaks, recorded as prior art in WP-1103.

So practice declares an intruder, or identifies its phase. What modelling it buys is claimed
as a sound fit, not as a measured gain in accuracy. rietx's own measurement agrees: on the
SRM 660c fixture, ignoring two holder lines moves the cell 0.4 ppm and reports an esd 9.9×
the clean fit's. Rwp rises 4.4× in the same arm, and an esd scales with √χ², so the larger
esd reports the worse fit; it does not measure the bias.

## When a peak counts as explained by a reflection

Surveyed 2026-11-01 for WP-1977, on when Layer 0 should call a residual peak unindexed.

- GSAS-II 5.8.4, checked. `IndexPeaks` (`GSASIIindex.py:311-352`) gives a picked peak the
  nearest calculated d-spacing, one peak to one line, with no tolerance at all. Unindexed
  lines are counted afterwards for M20 (`calc_M20`, :163-190). The automatic peak search
  drops a pick within 2 × FWHM of another (`GSASIIpwdGUI.py:825`), which spaces peaks and
  matches nothing. No check of a difference-curve peak after a Rietveld fit was found.
- FullProf 8.20, checked. The manual has no report of unaccounted or impurity peaks. WinPLOTR
  finds peaks from zero crossings of the derivative, above a fraction of the largest
  derivative amplitude (`WINPLOTR.pdf` § 5.4.1). It sets no angular window.
- TOPAS, inferred from a summarised fetch of the Durham manual (§ 12.3), not read directly.
  `index_max_th2_error` (default 0.05° 2θ) marks un-indexed lines in indexing. No
  residual-peak check after a fit was found.
- Indexing programs, checked in the docs FullProf bundles. DICVOL marks a line outside a
  fixed absolute error (default 0.03° 2θ) as impurity or spurious (`dicvol06.inf:139-157`).
  ITO's `TOLG` is 0.06° 2θ (`ito15.inf:337-342`). TREOR's window is fixed in sin²θ
  (`treor90.inf:786-805`), so it widens with angle and not with the peak width.
- McCusker et al. (1999) and Toby (2006), inferred (recall, no local copy). Both tell the
  reader to read the difference curve by eye. A derivative-shaped residual at a line is a
  position, width or asymmetry misfit, and a peak where no line is calculated is a foreign
  phase. Neither gives a numeric rule.

So the programs match an *observed* peak list to calculated lines, inside indexing, with a
fixed angular or sin²θ window. None scales the window with the peak width, and none flags a
difference-curve peak after a Rietveld fit. rietx's `unmatched_obs` has no direct precedent.
The programs leave the difference curve to the person reading it. So rietx lists every
residual peak and records what that reader looks at: whether a valley separates the peak
from the calculated peak beside it, how far out it sits in that peak's FWHM, and whether the
other strong lines carry the same lobe. It names no cause for an unresolved shoulder, and
suggests no impurity phase for one (WP-1977, ruled 2026-11-01).

## Sequential refinement

Surveyed 2026-10-24 for WP-2003, one agent across the seven programs. A chain here is N
separate refinements over an ordered series, one pattern at a time; a joint fit over the
series (`multi.py`, parametric refinement) is not this. Only GitHub and PyPI answered from the
session; the ILL, PSI, profex-xrd.org, topas-academic.com, Durham and readthedocs hosts were
refused. So GSAS-II (tag `v5.8.4`), MAUD (tag `v3.07`) and EasyDiffraction (the 0.21.1 wheel)
are read in their source, while FullProf, TOPAS and Profex rest on search-engine excerpts of
their manuals and news pages and are marked inferred. RIETAN-FP's and BGMN's manuals were not
reached.

Where each pattern starts:

| Program | Series mode | Next pattern starts from | What is carried | Le Bail or Pawley intensities |
|---|---|---|---|---|
| rietx | `refine_sequential` | the last accepted pattern's refined values (`carry=("*",)`); the first pattern runs the plan cold, later ones the plan collapsed into one stage freeing the same set (`refit="single"`) | every table entry, a coordinate as its site's displacement, rigid-body orientations and torsions, named variables; ties and holds are re-declared per pattern by `constrain`, never carried | carried (`carry_hkl_intensities=True`), matched by hkl (checked) |
| GSAS-II | Controls, "Select datasets" (`Seq Data`) | the values stored for each histogram: `Copy2Next` ("Copy results to next histogram?") is off by default. A phase parameter starts from that histogram's result in an earlier sequential run, if there is one | with `Copy2Next` on, every varied parameter, renamed to the next histogram | with `Copy2Next` on, a Le Bail phase's F² are copied when the two reflection lists have the same length; otherwise an error is printed and nothing is copied (checked) |
| EasyDiffraction | `fit_sequential` over a directory | the free parameters of the last successful fit, and the template's values until one succeeds | free parameters only; fixed ones keep the template's values | none: the worker collects parameter values only (checked) |
| MAUD | no series mode; "Launch batch file" runs a CIF-style instruction loop, one analysis per row | the analysis file the row names, read afresh (checked). The batch dialog's default ("Uses the list (or just one)") names the listed file on every row and saves each result over it, so with one file listed each row reads what the previous row saved (inferred from the code, not run; how the data files then accumulate is not established). "Use from previous analysis for next" names the previous row's saved file outright | whatever the saved analysis file holds | whatever the saved file holds (inferred) |
| FullProf | cyclic mode from the command line, `fp2k cyc <pcr> <datcode> <first> <last> …` (FullProf News 2004, 2005) | the previous pattern's output, which the workshop slides describe as the next one's input, with the same refinement conditions for every pattern (inferred) | the `.pcr`'s parameters (inferred) | not established |
| TOPAS | none built in: `num_runs` reruns one INP and values pass between runs through `out` and `#include` (Technical Reference v8); a series is the user's batch file or, from v6, a `#list` macro (inferred) | what the user's script writes | the user's choice | the user's choice |
| BGMN with Profex | Profex runs loaded projects one after another (Run, "Run batch refinement"); a batch that feeds one project's results to the next is described as a separate "sequential batch" workflow (inferred) | each project's own control file in a plain batch (inferred) | not established | not established |
| RIETAN-FP | none found | not established; a third-party wrapper, RIETPY 0.2.0, chains runs and passes refined parameters on (its PyPI description, checked) | not established | not established |

When a fit goes wrong:

| Program | Restart on a bad fit | A pattern that fails | Does the failure seed the next? |
|---|---|---|---|
| rietx | a rung at a time, collapsed warm refit, then the full plan from the warm state, then the full plan cold, when the fit diverges, raises or carries an `error`-level code (an Rwp fence only where the caller passes `reseed_factor`, none by default since WP-2003), and to the staged warm rung alone when the collapsed fit's GoF exceeds 1.25× its seed pattern's (WP-2080); the best attempt is kept, an unrejected one before Rwp and a truncated rung below any completed one (`reseed=True`, checked) | still rejected after every rung: quarantined, `SEQUENTIAL_UNRECOVERED`. Every rung raised: `on_error="carry"` records it (`SERIES_PATTERN_FAILED`) and the chain goes on; `"skip"` starts the successor cold, `"raise"` stops. A high Rwp is kept and recorded, `SeriesEntry.rwp_over_median` | no: the successor starts from the last accepted pattern, and a quarantined pattern joins no median (checked) |
| GSAS-II | none | a singular normal matrix ends the chain at that histogram ("Sequential refinement failed at histogram") and the histograms before it are written to the results table; an exception ends the run before that table is written (checked) | not applicable: the chain has stopped |
| EasyDiffraction | none | an exception is caught and written as a failed row of `results.csv`, and the chain goes on (checked) | no: only a fit whose `fit_result.success` is true moves the start values (checked) |
| MAUD | none | an exception that reaches the batch loop ends the batch; a fit that finishes, however poor, is saved and the next row runs (checked) | the next row reads whatever file it names (inferred) |
| FullProf | not established | not established | not established |
| TOPAS | none built in; a rule would be the user's macro (inferred) | the user's script | the user's script |
| BGMN with Profex | none described | aborting a running project moves the batch on to the next one (manual 3.13, inferred) | not established |
| RIETAN-FP | not established | not established | not established |

Order and flags:

| Program | Reverse order | Forward-backward comparison | Test on steps between neighbours |
|---|---|---|---|
| rietx | `direction="backward"`; `"forward"` by default | `direction="both"`, off by default, runs the chain each way and lists every path's gap per pattern in combined esds, largest first, with no threshold (`SeriesResult.direction_gaps`; until WP-2003 `SEQUENTIAL_PATH_DEPENDENT` at 3 combined esds) | none since WP-2003: `SeriesResult.steps` lists every step in esds of the later fit, largest first, with no threshold and no diagnostic (until then `SEQUENTIAL_DISCONTINUITY`, at 5× the median absolute step and 3 combined esds from 5 points); `verify_steps=k` refits the k largest pairs cold, 0 by default (checked) |
| GSAS-II | "Reverse order?" (`Reverse Seq`), off by default | none | none. The results table colours a last-cycle Δχ² above 1 % yellow and above 10 % red, only with `ShowCell` on (off by default); a user-run cluster analysis offers outlier detection on the data (checked) |
| EasyDiffraction | `reverse`, off by default ("useful when starting values are better matched to the last file") | none | none (checked) |
| MAUD | the row order of the instruction file | none | none (checked) |
| FullProf | not established | not established | none described; the slides state the assumption that the refined parameters evolve continuously (inferred) |
| TOPAS | the user's script | none built in | none built in (inferred) |
| BGMN with Profex | not established | none described | none described (inferred) |
| RIETAN-FP | not established | not established | not established |

Anything else a series mode decides by itself:

- rietx: stage seeds are zeroed on a warm start, so a neighbour's answer sitting on a floor is
  not lifted; the collapsed first rung gets no evaluation budget unless the caller passes
  `first_rung_factor` (none by default since WP-2003's C3, 2026-11-02); a magnetic
  moment the pattern does not support is floored before it seeds the next
  (`SEQUENTIAL_MOMENT_HOLD`); the wavelength-calibration diagnostic measures from the series
  root's declared λ, not the carried one; a cancelled
  series returns what completed (`SEQUENTIAL_CANCELLED`); every per-pattern code is
  counted over the series (`SeriesResult.code_counts`, no threshold since WP-2003) (checked).
- GSAS-II refuses to start a sequential refinement that refines a phase's lattice parameters
  or texture coefficients, and says to use the per-histogram Dij and C(L,N) instead. With
  `Copy2Next` on it prints the variables added or removed when a histogram's vary list
  differs. A variable outside `parmMinDict`/`parmMaxDict` is reset to its limit and frozen for
  that histogram, and both dicts are empty by default. "Clear previous seq. results" is a
  button, never automatic. Each histogram is fitted by `RefineCore`, the single fit's solver
  (checked).
- EasyDiffraction resumes a re-run from `results.csv`, skipping fitted files and starting from
  the last successful row; with `max_workers` above 1 every file of a chunk starts from the
  same values (checked).
- MAUD's wizard indices above 1000 rerun the refinement wizard while GoF falls, zeroing the
  minor phase on each pass. That removes phases; it is not a restart (checked).
- FullProf appends to its summary file in cyclic mode, and `Rpa = -2` writes the refined
  parameters to a `.SEQ` file (inferred).

None of the seven restarts a pattern by itself, compares a chain with its reverse, or tests
the step between neighbours. The rietx behaviours with a program default behind them are:

- the warm start from the previous pattern: EasyDiffraction (checked) and FullProf's cyclic
  mode (inferred). GSAS-II dissents (each histogram starts from its own values unless
  `Copy2Next` is ticked), and MAUD's and Profex's batches start from the file each row names;
- carrying on past a failed pattern from the last good one, and not seeding from the failure
  (`on_error="carry"`, the quarantine's carry half): EasyDiffraction (checked). GSAS-II and
  MAUD dissent: a failure ends the chain;
- forward order, with reverse available and off: GSAS-II and EasyDiffraction (checked);
- one refinement freeing the same set on every warm pattern (`refit="single"`): GSAS-II and
  EasyDiffraction fit every pattern with one vary list (checked), and FullProf's slides ask for
  the same conditions on every pattern (inferred). rietx alone stages the first pattern;
- carrying extracted intensities with a warm start: GSAS-II does it, but only under its opt-in
  `Copy2Next` (checked); no program carries them by default.

rietx carries every entry where GSAS-II and EasyDiffraction carry the varied ones. A fixed
entry holds the same value either way, so the two differ only where a fixed value changes
during the chain. The behaviours with no program default behind them are rietx's own: the
restart ladder (its Rwp fence and first-rung budget the caller's opt-ins since WP-2003, the
median, `_prefer`); the quarantine's exclusion from the median; `direction="both"` and
its gap list; the step list and its cold verification; and the moment
floor and onset (`SEQUENTIAL_MOMENT_HOLD`, `SEQUENTIAL_MOMENT_ONSET`), the per-pattern code
counts and the width-growth screen (`SEQUENTIAL_WIDTH_GROWTH`).

Parameters the setup fixes. Surveyed 2026-11-02 for WP-2081, one session. GSAS-II 5.8.4 is
read in its source (`GSASIIstrMain.SeqRefine`, `GSASIIstrIO.ReadConstraints`,
`GSASIIpwdGUI.OnInstFlagCopy`). FullProf rests on its manual (`FullProf_Manual.pdf` shipped
with 8.20, the cyclic-mode and codeword passages) and TOPAS on the Technical Reference
(version 9, topas-academic.com, sections 2.1, 2.7 and 2.26). Neither closed program was run.
MAUD, BGMN with Profex and RIETAN-FP were not surveyed for this topic.

| Program | How a parameter stays fixed down a series | What can free it anyway | One refined value shared by every pattern | "Refine on the first pattern, then freeze" |
|---|---|---|---|---|
| rietx | `ref.hold(glob)` inside the `constrain` hook, which runs on every rung and every `verify_steps` refit (checked) | `vary=False` on the models: any plan stage whose `turn_on` matches frees it (WP-1208), and `load_instrument_profile`'s frozen instrument comes back `vary=False` only (checked). A hold blocks the plan and raises `HOLD_BLOCKED_PLAN` (checked) | not in a chain. The joint fit (`multi.py`, `SharingMap`) shares a path across histograms; `instrument.*` is per histogram by default and a `shared=` glob overrides it (checked) | no declaration. Three hooks spell it: `on_result` keeps pattern 0's value, `prepare` writes it in, `constrain` holds it. A hold alone fixes whatever value reaches the rung, and the cold rung starts from the initial models (measured, WP-2081) |
| GSAS-II | each histogram's own refine flags build its vary list, histogram by histogram (`SeqRefine` calls `GetHistogramData` per histogram); "Copy flags" copies one histogram's instrument flags to the others (checked) | nothing: there is no plan. With `Copy2Next` on, only parameters in the vary list pass to the next histogram, so a fixed one keeps the value stored in its own histogram (checked). Hold constraints exist; a sequential run applies only constraints whose histogram is the wildcard by default (`_seqmode` `wildcards-only`, checked) | not in a sequential run, which fits one histogram at a time and refuses lattice parameters (use Dij). A plain refinement over several histograms shares phase parameters (recall). Equations can be fitted to the sequential results table afterwards (`SeqParFitEqList`, checked) | by hand: refine, copy the values to the other histograms, turn the flags off (inferred from the menu commands) |
| FullProf | cyclic mode (`CYC`) runs one PCR and rewrites it after each file, so every file uses the same codewords; a zero codeword fixes a parameter at the value the PCR holds (checked in the manual). An instrumental resolution file (`Res` ≠ 0) supplies the resolution function (checked) | nothing beyond the codewords (inferred) | the multi-pattern PCR (`NPATT`) refines several patterns at once (checked); which parameters it shares was not read | by hand: set the codeword to 0 in the PCR after a first run (inferred) |
| TOPAS | a parameter is refined when named and fixed when its name carries `!` (§ 2.1, checked). A series is the user's batch file or `num_runs`, passing values through `out` and `#include` (§ 2.26, checked) | nothing: the flag is on the parameter (checked) | a parameter named at the top level of one INP is one parameter in every `xdd` (§ 2.7, checked). Parametric refinement builds on this (Stinton & Evans 2007, recall) | by hand: write the refined value into an include file and mark it `!` (inferred) |
| EasyDiffraction | a fixed parameter keeps the template's value on every file (row above, checked) | not established | not established | not established |

Every program surveyed keeps the fixed flag on the parameter itself, and its series honours
it on every pattern. None of them has a plan that frees a parameter the user fixed. rietx
departs in two ways. A plan replaces the vary flags, so a hold in a hook is the only flag a
series honours. And the cold rung restarts a pattern from the initial models, which no
other program does (the restart table above), so what a held value is on that rung is a
question only rietx has.

How a person works a series. Surveyed 2026-11-04 for WP-2081, one session, against Yue's
account of the traditional workflow recorded there. GSAS-II 5.8.4 is read in its source:
`GSASIIplot.py` (the multi-pattern key commands, `:2067`, `:2213`), `GSASIIpwdplot.py` (`:140`),
`GSASIIstrMain.py:996-1000`, `GSASIIstrIO.py:3019-3027` and `GSASIIpwdGUI.py:2506-2520`
(`OnLimitCopy`). FullProf rests on its manual (`FullProf_Manual.pdf` shipped with 8.20: `Jbt`,
`Nex` and the multi-pattern lines). TOPAS is recall only. MAUD, BGMN with Profex, RIETAN-FP
and EasyDiffraction were not surveyed for this topic, and the literature was not searched.

| Program | A view of the raw series before any fit | A second pass over the series | Rietveld beside Pawley or Le Bail in one fit | Excluded regions across a series |
|---|---|---|---|---|
| rietx | none: `plot_pattern` draws one pattern and the GUI's Series panel draws a frame only after the run (checked) | no verb. A `prepare` hook can start each frame from its own earlier answer, and the record still names the neighbour (measured, WP-2081) | no: `mode` is one value for a fit, and `Phase` has no mode field (checked) | a list on each `PatternData`, and the GUI copies the project's regions to every frame. Nothing reports a reflection crossing a region's edge (checked) |
| GSAS-II | waterfall and contour plots over several histograms (checked) | with `Copy2Next` off, its default, each histogram starts its phase parameters from its own result in an earlier sequential run (`elif histogram in SeqResult`, checked) | per phase: `doPawley` on the phase, and a `LeBail` flag per phase and histogram (checked) | per histogram under Limits, and "Copy limits" copies them to other histograms (checked). Any warning for a reflection crossing an edge was not checked |
| FullProf | not checked (WinPLOTR was not read) | the user reruns the cyclic mode on the rewritten PCR (inferred) | per phase: `Jbt` 0 is Rietveld and 2 is profile matching, in one PCR (checked in the manual) | `Nex` regions per pattern in a multi-pattern PCR (checked); cyclic mode reuses one PCR, so one list for every file (inferred) |
| TOPAS | not checked | the user's script (inferred) | a `str` phase beside an `hkl_Is` phase in one `xdd` (recall) | `exclude` per `xdd` (recall) |

Two of these change the comparison with rietx. A second pass is free in GSAS-II because each
histogram keeps its own values between runs. rietx's chain starts every later frame from a
neighbour, so its stages stay inside one frame. And GSAS-II and FullProf (TOPAS by recall)
let a phase be fitted without a structure beside one fitted with a structure, where rietx
sets that for the whole fit.

## A pdCIF weight column with bad entries

Surveyed 2026-10-26 for PR #1173, by the lead. The question: a `_pd_proc_ls_weight` column with
mostly positive entries and a few negative or null (`?`, `.`) ones. Does a reader keep the good
weights or drop the column?

The dictionary (`cif_pd.dic` 2.5.1-dev, 2026-09-08, checked) gives the item
`_enumeration.range 0.0:`, so a negative weight lies outside its definition. A zero marks "a
data point not used for refinement". It states no meaning for a null.

| Program | What it does with the column |
|---|---|
| rietx | Reads it as 1/σ² when every entry is ≥ 0 and one is positive; a zero excludes its own point. Any negative or null entry drops the whole column to the Poisson σ (checked, `io/formats/pdcif.py`) |
| GSAS-II 5.8.4 | `G2pwd_CIF.py:300-306` turns a null into a weight of 0 and passes a negative through unchecked. The line that would use the result, `w = np.array(vl)`, is commented out (`:334`). The weights come from the intensity's own su, else √y, whatever the weight column holds (checked; PyCifRW parses `?` and `.` as `None` and `-0.5` as itself, ran) |
| MAUD 3.07 | `CIFDataFile.java:161, 219` sets each weight from √I and reads no weight or su column (checked at tag v3.07) |
| FullProf 8.20 | No pdCIF data input in the manual (checked) |
| EasyDiffraction 0.21.1, cryspy 0.13.0 | No reader of `_pd_proc_ls_weight` in either package (checked by search) |
| TOPAS, RIETAN-FP, BGMN | Not checked; no pdCIF data reader is known |

No program surveyed uses a pdCIF weight column at all. rietx's whole-column fallback
therefore never trusts the file less than practice does. GSAS-II's unused code shows one
intent: a null weight means an excluded point.

## A NaN or infinite value in a pattern file

Surveyed 2026-11-01 for WP-2079 (issue #1187), and its GSAS-II row re-read 2026-11-03. The
question: a pattern file whose count, σ or 2θ is NaN or ±inf on some rows, as a reduction writes
where it divided by a zero monitor. Does a reader drop the row, keep it at zero weight, or refuse
the file?

| Program | What it does with the row |
|---|---|
| rietx | Every reader drops a row whose 2θ, count or σ is NaN or ±inf and reports `PATTERN_ROWS_DROPPED` with the 2θ of the dropped rows; a file with no finite row is refused. Bruker RAW refuses the file instead, since a non-finite float32 there means a wrong stride (checked, `io/formats/base.py` `finite_rows`) |
| GSAS-II 5.8.4 | `imports/G2pwd_xye.py:170-201` passes the columns through `nan_to_num`: a NaN count or σ becomes y = 0 at weight 0, so the point stays in the pattern and leaves the fit, silently. A +inf count with a finite σ becomes y ≈ 1.8e308 at weight 1/σ², and a NaN 2θ passes through (checked by reading, not run). One importer only |
| FullProf, TOPAS, RIETAN-FP, BGMN, MAUD, EasyDiffraction | Not checked |

Dropping and zero weight give the same χ². The two differ in what the pattern holds afterwards:
GSAS-II keeps the point to plot, and rietx's pdCIF reader likewise keeps a zero-weight point as an
excluded region.

## Separators, trailing comments and text lines in a column file

Surveyed 2026-11-09 for WP-1952 (issue #897). The question: in a plain two- or three-column
file, which characters separate the columns, what happens to a comment after a row's numbers, a
text line inside the data and a decimal comma?

| Program | What it does |
|---|---|
| rietx | Whitespace, `,` and `;` separate, and a `;` line is a comment. A field opening with `#` or `!` ends the row, without a report. A line between the first and last data row that is not a row of numbers is dropped and reported by line (`PATTERN_ROWS_DROPPED`); a header above the data and a footer below it are skipped silently. Quoted fields and a comma inside a number (a decimal comma or a thousands separator) are refused by name (checked, `io/formats/xy.py`) |
| GSAS-II 5.8.4 | `imports/G2pwd_xye.py:166` and `G2pwd_csv.py:28,73` replace `,` and `;` with spaces, so both importers read either separator. After the header, a line with fewer than two fields is printed to the console and skipped; a field that is not a number refuses the whole file, naming the line (`:187`). Columns past the third are ignored, so `10.0 100 # c` reads while `10.0 100 #c` refuses. A quoted field refuses. A decimal comma or a thousands separator splits the number in two, as rietx did before (checked by reading, not run) |
| FullProf, TOPAS, RIETAN-FP, BGMN, MAUD | Not checked |

## A magCIF in a non-standard orientation

Surveyed 2026-11-01 for WP-1918's decision on the 91 untabulated orientations, by a research
agent for the lead. The question: a magCIF whose nuclear group has its axes in an orientation
no tabulated setting has. An example is an orthorhombic subgroup written in its hexagonal
parent's axes. Does a reader keep the file's axes, or restate the structure in the magnetic
space group's standard setting?

MAGNDATA writes the parent-related setting on purpose. Gallego et al. (2016, *J. Appl.
Cryst.* 49, 1750, §2.2) say most entries keep "the origin and orientation of the
crystallographic axes of the paramagnetic phase". They call the listed operations sufficient,
and the BNS label and the transformation to standard "complementary information". Their §2.3
keeps the parent's metric unless a strain is observed. The symmetry-allowed strain is stated
in the parent's axes. The IUCr guidelines (Perez-Mato et al. 2024, *Acta Cryst.* B80) accept
either setting, call the non-standard one "in most cases more convenient", and require the
transformation to standard beside the label (checked through the real-case companion,
§2.1.1).

| Program | What it does |
|---|---|
| rietx | Refuses the file: `OperatorGroup` takes its cell ties from a tabulated closest type, and there is none (`magcif._unnamed_nuclear_group`, checked) |
| GSAS-II 5.8.4 | Keeps the file's axes and operators. The group is built from the parent symbol, its operators are replaced by the file's (`SGFixed`), and the cell refines under the parent's Laue class (`G2phase_CIF.py:238-262, 311-318`; `GSASIIstrIO.py:1000-1027`; checked). For a nuclear CIF whose operators disagree with GSAS-II's setting, it asks before sending the file to Bilbao's standard-setting service (`G2phase_CIF.py:729-779`, checked) |
| FullProf 8.20 | Uses explicit operators in the PCR's own setting. "Transform to standard" carries the standard operators to that setting only when none are given (FullProf News, 6 Feb 2018; checked). The cell ties for such operators were not checked |
| Jana2020 | Supports non-standard settings. "Transform to the standard setting" is a command the user runs (changelog, checked). That its import keeps the file's setting is inferred |
| TOPAS v9 | `#inp_from_cif` reads an mCIF only in its BNS standard setting. "A file in any other setting stops with a message" (Technical Reference, magnetic section; checked) |
| Bilbao MVISUALIZE, STRCONVERT, ISOCIF | Change the setting on request. ISODISTORT needs the standard setting, which ISOCIF produces first (Gallego et al. 2016, §3-4; checked) |

No program surveyed restates a magCIF on read. Those that read the file keep its axes. Moving
to the standard setting is a step the user takes. GSAS-II's cell rule, the parent's Laue
class in the file's axes, is the parent-metric model of MAGNDATA §2.3 with no strain freed.

## Structure-free fitting: Le Bail or Pawley

Surveyed 2026-10-27 for WP-2062, one agent across the seven programs, with the GSAS-II lines
checked by the lead. Terms follow Le Bail (2005): a Le Bail fit sets each intensity by the
Rietveld partition formula between least-squares steps and never refines it, and a Pawley fit
makes each intensity a least-squares parameter. A program's own label is not reliable: BGMN
calls its Pawley-type mode "LeBail". TOPAS was read at Technical Reference v5 (§8), not v9.

| Program | Offers | Default or first steer | Le Bail re-extraction | Pawley overlap handling |
|---|---|---|---|---|
| rietx | both | no default argument picks either (`mode` defaults to `rietveld`); the indexer's validation fit is Pawley since WP-2011 | a partition before and after each least-squares *run*, none inside it, repeated until a cycle moves 1e-7 of the Bragg counts under a cap of 25000 cycles (WP-1542; 3 fixed cycles before it) | seeded from one Le Bail partition; overlapped groups held by an equal-split restraint and flagged |
| GSAS-II 5.8.4 | both | neither is on by default (`doPawley` and the histogram's `LeBail` both False); a "Start Le Bail extraction?" button on each histogram, Pawley a Phase › General checkbox | once per least-squares iteration under the default analytic Hessian (checked) | reflections exactly overlapped by symmetry tied equal; a negative-intensity penalty, weight 0 by default |
| FullProf 8.20 | Le Bail only (`Jbt` = 2, profile matching) | the manual advises profile matching before Rietveld when the model is crude | every least-squares cycle (ran); stops when χ² changes by < 1e-3 | not offered |
| TOPAS (TR v5) | both | Pawley: "The default is Pawley refinement, the keyword lebail triggers a Le Bail refinement" (§8, p.84) | every iteration, a "two-step cyclic process"; "convergence is usually slow" | each intensity a parameter from 1; no rule stated |
| RIETAN-FP 3.12 | Le Bail, plus a "hybrid" decomposition that refines intensities after it | Le Bail first; Wilson-statistics start advised | after every cycle | hybrid step only: reflections within `RWID` × FWHM set equal, groups of at most `MREG` |
| BGMN 4.2.23 | one mode it calls "LeBail", refining one intensity per peak (Pawley-type) | automatic when a structure lists no atoms | n/a | intensities ≥ 0; no overlap rule found |
| MAUD 3.07 | both | new phases are atomic; the help text says start with Le Bail, then switch to Pawley | end of each refinement iteration, up to 5 inner iterations | intensities bounded 0 to 1e9; no overlap rule |
| EasyDiffraction 0.21.1 | neither | n/a | n/a | n/a |

What the table settles. **Every program that has Le Bail re-extracts the intensities inside the
refinement, once per least-squares cycle or iteration.** rietx re-extracts only between whole
solves, so one rietx Le Bail pass is one cycle of everyone else's. Of the two programs that
offer both, TOPAS defaults to Pawley and GSAS-II defaults to neither. MAUD steers Le Bail
first and then Pawley. No program makes a structure-free fit the default mode.

**How many cycles, and what stops them** (survey for WP-1542, 2026-11-05; GSAS-II source
checked, the rest from the table's sources). No surveyed program stops on the extracted
intensities at a fixed model. GSAS-II's `DoLeBail` runs a fixed `cycles=10`
(`GSASIIstrMain.py:761`, the loop near `:825`), and in a refinement it extracts once per
least-squares iteration and stops on the relative change in χ² (1e-3, at most 3 cycles by
default). FullProf extracts once per cycle and stops when χ² changes by under 1e-3. TOPAS
extracts every iteration and RIETAN-FP every cycle. MAUD runs up to 5 inner iterations. Le Bail
(2005) gives no rule for the count, and says only that one pass is not enough to reach the
minimum Rwp. In those programs the model moves between extractions, so many cycles accumulate
over a refinement. rietx holds the model frozen through a solve (the frozen-per-stage rule),
so one partition has to carry what those cycles carry. That is why rietx alone has a stop on
the intensities, and why it accelerates the step: plain repetition needed 17 512 cycles on
one partition of a real neutron pattern at ten times this tolerance.

**GSAS-II** (source, checked). `GetFobsSq`, the Le Bail update, runs at the end of every
derivative pass (`GSASIIstrMath.py:4808`, `:4929`) and overwrites the calculated F² with the
extracted one when the phase-histogram's `LeBail` flag is set (`:3782-3783`). The scripting
default is `DoLeBail(cycles=10)` (`GSASIIstrMain.py:761`). Pawley ties come from
`GetPawleyConstr` (`GSASIIstrIO.py:955-998`): equal index sums in the uniaxial and cubic
classes, |Δd|/d < 1e-4 elsewhere, so a near-overlap stays free. "Pawley create" seeds every
intensity at 100.0 (`GSASIIphsGUI.py:12546`); an optional estimate scales the observed peak
height (`:12563-12626`).

**FullProf** (manual, July 2001, shipped with 8.20; ran). `Jbt` = 2 refines intensities "using
iteratively the Rietveld formula" with the scale fixed (PDF p.15). A run of the shipped
`pbso.pcr` with every refinement code at zero moved χ² 78.8, 10.4, 5.89, 5.17, 4.81 over its
first five cycles, so the intensities alone move once a cycle. The stop rule is the
2005-11-08 news entry. The manual warns profile matching is "more prone to instabilities"
when profile or microstructure parameters refine (p.14). Pawley is named but is no `Jbt` value.

**TOPAS** (Technical Reference v5 §8, pp.84-85, and the User Manual pp.41-42, 60; read from a
public copy, not re-read by the lead). Pawley has "better and faster convergence" and keeps the
A matrix charge flipping uses. The indexing GUI refines each selected solution by Pawley or Le
Bail and reports Rwp.

**RIETAN-FP** (manual, paraphrased). Le Bail is simple, needs no large normal matrix and
gives no negative intensities, but needs a more exact starting cell, and overlapped
intensities stay near their starting values (§10.4). The hybrid decomposition exists because
of those convergence problems (§11.1).

**MAUD** (source at the v3.07 tag). The default structure-factor model is atomic
(`Phase.java:337`); `src/help/pawley.txt` advises Le Bail first, then Pawley with the
extracted values carried over.

**Le Bail (2005)**, *Powder Diffr.* 20, 316-326. §IV.B (p.318): the method "requires as good
starting cell and profile parameters as the Rietveld method itself". §IV.C (pp.318-319): two
round robins could not show either method better, and Le Bail can also give negative
intensities when the background is overestimated. §VI (p.321): Kariuki et al. (1999) tested
cell hypotheses by Le Bail, "faster than with the Pawley method", and one partition pass may be
"insufficient for attaining the minimum Rwp" when calculation and observation differ widely.
The paper gives no timings.

Not determined: TOPAS v9 and its Pawley overlap rule, FullProf's current manual, the Profex
5.7.2 manual. MAUD, BGMN and RIETAN-FP were not run.

## Ranking extinction symbols: which fit, and how a weak line is judged

Surveyed 2026-11-05 for WP-2076, from the GSAS-II source and a web search. The paper corpus
holds neither ExtSym paper, so the ExtSym row rests on its abstract and its catalogue records.

| Program | What the ranking reads | How a weak line enters |
|---|---|---|
| rietx (main) | a Pawley χ² per class (the lattice less its testable forbidden lines, WP-2076) against an absence-free Pawley reference, as ΔBIC | a testable forbidden position counts ln N in the class's favour, and a window test at 3σ refutes |
| ExtSym (Markvardsen et al. 2001, 2008) | integrated intensities and their errors, from a Pawley-type fit. Validated on TF12LS output, then on DASH, FullProf, GSAS, PRODD and TOPAS output | a probability per symbol. The abstract says the result depends heavily on the accuracy of the error estimates |
| GSAS-II 5.8.4 | no extinction-symbol ranking found. The Unit Cells tab lists space groups for a cell with M20 and X20 (`GSASIIpwdGUI.py:737-768`) | not applicable |
| TOPAS, FullProf | not checked | not checked |

**The Le Bail partition clamps in GSAS-II too.** `ComputeFobsSqCW` keeps a channel only where the
observed-over-calculated ratio is positive (`GSASIImpsubs.py:177`, checked), which is the
channel clamp `lebail_update` applies through `max(net, 0)`. The bias was not measured in
GSAS-II, and the two programs' peak windows were not compared.

Not determined: how DASH or TOPAS rank without ExtSym, and what EXPO2014's statistical
approach reads.

## A volume window from the formula, in indexing

Checked by the maintainer in the sources on 2026-10-24 (#1121) and entered for WP-2030;
only what each program asks the user for is recorded here.

| Program | What the indexer takes for the volume | A volume from the formula |
|---|---|---|
| rietx | `SearchSpec.min_volume`/`max_volume`, default 15 Å³ and the data's envelope; `SearchSpec.from_formula` sets a ceiling, `z` × Hofmann's (2002) estimate × 1.25, and no floor (WP-2030) | yes, on the caller's request |
| GSAS-II 5.8.4 | a start volume, and no composition (`GSASIIpwdGUI.py`, checked) | no |
| DICVOL06 | VOLMIN and VOLMAX from the user, ceiling 2500 Å³ by default, and optionally a measured density and formula weight (`dicvol06.inf`, card 4, checked) | no |

Neither program estimates a volume from the formula, so the volume range is always the user's.
`from_formula`'s ceiling therefore rests on no program default; its audit row is tier 2 on
Hofmann's citation and the 21 published cells it was checked against.

## Which lines an indexing search is given

Surveyed 2026-11-12 for WP-2078, on whether a relative intensity floor on the picked list is
practice. "Checked" means read in the program's documentation or source, or in the paper; the
TOPAS and Conograph programs were not run. Bergmann et al.'s Table 5 was read from the rendered
page, because the PDF's text layer drops its minus signs.

- TOPAS (Technical Reference v9, "Keywords in detail", the `index_*` keywords), checked. Each
  line is an `index_th2` or `index_d`, optionally with `index_I`. The manual says `index_I`
  weights the line. Coelho (2003, *J. Appl. Cryst.* 36, 86) eq. 4 puts it into the minimised
  quantity as a factor. The keyword list has no intensity floor and no line count. The controls
  are `index_max_Nc_on_No` and `index_max_th2_error`, and a `good` flag marks a line as not an
  impurity. Coelho's examples feed every observed peak. In one he notes three small peaks that
  "would not normally be included". `lp_search` fits the pattern itself, so it takes no list.
- GSAS-II 5.8.4, checked. `OnReload` (`GSASIIpwdGUI.py:4210-4222`) copies every fitted peak
  into the indexing list with `use` set. The `use` checkbox is the only selection
  (`GSASIIpwdGUI.py:4280-4286`). `GSASIIindex.py` never reads the intensity column, and
  `calc_M20` (`:163-191`) scores the first twenty rows in list order. The controls offer no
  intensity threshold.
- DICVOL06 and DICVOL14 (FullProf suite), checked. Card 2's N is the number of lines that
  drive the search, "e.g. N = 20", below the total supplied (`dicvol06.inf:83-91`). The
  solutions are then reviewed against every line. The input has no intensity field. Boultif &
  Louër (2004, *J. Appl. Cryst.* 37, 724) §3.4: with DICVOL91 the advice for suspected spurious
  lines was to omit low-intensity lines in a first run. DICVOL04 replaced that advice with an
  impurity-line tolerance.
- TREOR90 (FullProf suite), checked. Intensity "is never used by the indexing program"
  (`treor90.inf:309-311`). The manual recommends the first 25 well-measured lines (`:72-74`).
  `USE`, the lines in trial indexing, defaults to 19 with a maximum of 20 (`:716-726`). Werner,
  Eriksson & Westdahl (1985, *J. Appl. Cryst.* 18, 367) used the first 25 lines.
- ITO15 (FullProf suite), checked. It uses at most the first 40 lines, in ascending 2θ
  (`ito15.inf:127-133`). An optional intensity field is read and no calculation uses it
  (`:238-248`).
- WinPLOTR, FullProf's front end to the three, checked in `WINPLOTR.pdf` §5.4.1 and §5.4.9-11.
  Its peak search has a detection threshold relative to the largest derivative amplitude
  (default 0.02). That is a picker's sensitivity, not a cut on I/Imax. The export dialogs offer
  no intensity cut. The dialogs were read, not run.
- McMaille (Le Bail 2004, *Powder Diffr.* 19, 249), checked. The automatic mode takes twenty
  lines with intensities, and its score is the share of observed intensity a cell leaves
  unexplained. Impurities are tolerated while they hold under 10-15 % of the total intensity.
  Weak lines therefore count for little in the score, and none is removed.
- Conograph (Oishi-Tomiyasu 2014, *J. Appl. Cryst.* 47, 593), checked. By default it takes the
  48 smallest q values, chosen by position. The paper argues for more lines, not fewer.
- N-TREOR09 in EXPO, checked only through ITC Vol. H ch. 3.4 (Altomare, Cuocci, Moliterni &
  Rizzi). EXPO passes its indexer "the first 43 peaks" with intensities above "a default
  threshold". The chapter states no value. This is the one automatic intensity floor found.
- ITC Vol. H ch. 3.4, checked. M₂₀'s twenty lines are "a compromise (coming from experience)"
  (§3.4.2.1). The introduction suggests setting overlapping peaks aside in a first attempt. No
  sentence recommends a general intensity floor.
- Bergmann, Le Bail, Shirley & Zlokazov (2004, *Z. Kristallogr.* 219, 783), the bethanechol
  round robin, checked. Every program was given "the 20 first lines, or the first 20 lines with
  I ≥ 5 % (I/Imax)" (p. 786). Set A is the raw list and set B the 5 % list. Two ICDD entries
  were used, one with 8 impurity lines among its first 26 and one with 3 among its first 35.
  Table 5 scores each run −1 (not in the first ten), 0 (found, not first) or +1 (first). Over
  ITO13, DICVOL91, TREOR90 and McMaille, two entries and two modes, A to B gave 5 runs better,
  1 worse and 10 unchanged. The worse run is McMaille's default run on the second entry, which
  went from first to not found. After a zero correction (sets C to D) the floor gave 4 better,
  0 worse and 12 unchanged. The manual runs also tolerated up to 8-10 unindexed lines, so the
  gains are not the floor's alone. The paper's conclusion: removing weak peaks "should not be
  done routinely" and is worth a try when the full list gives no clear answer (p. 789).
- Not held on this machine, so no claim made: de Wolff (1968), Shirley's Crysfire guide and his
  2003 newsletter article, Altomare et al. (2009) on N-TREOR09, Coelho (2017) on `lp_search`,
  Boultif & Louër (1991). X-Cell was not read.

So the programs choose the search lines by count and by position: the first twenty, then every
line to review or score. TOPAS and McMaille let intensity weight a line, and nothing else lets
it act at all. One program applies an intensity floor by default, EXPO's N-TREOR09, at a value
its documentation does not state. The literature offers a floor as a second attempt after the
full list fails, at 5 % of Imax, and its one benchmark measured a small gain on impurity-laden
lists with one loss. A floor applied to every search before it runs is therefore rietx's own
(tier 3). A floor tried after the full list finds nothing has precedent (tier 2, Bergmann et
al. 2004 and DICVOL91's advice). rietx drives with the strongest twenty from a low-angle pool
and scores on every line (WP-1039), which keeps the convention's count and changes its order.

## The doublet ratio and asymmetry a peak picker holds

Surveyed 2026-11-06 for WP-2055, on whether `pick_peaks` should refine the Kα2/Kα1 ratio or
the axial apertures per pattern before fitting lines.

- GSAS-II 5.8.4, checked in source. The peak fit (`DoPeakFit`, `GSASIIpwd.py:2651`) takes the
  ratio `I(L2)/I(L1)` from the instrument parameters, at 0.5 in the default lab Cu Kα file
  (`defaultIparms.py:35`), with the axial term `SH/L` at 0.002 (`defaultIparms.py:36`).
  Both are on the list a peak fit may vary (`GSASIIpwd.py:2789-2790`), but only when their
  refine flag is set, and a file read from a GSAS instrument file arrives with every flag
  off (`GSASIIfiles.py:258-259`).
- FullProf's WinPLOTR, checked in its manual (`WINPLOTR.pdf`). The radiation block takes λ1,
  λ2 and the ratio Iλ2/Iλ1, defaulting to Cu Kα at 0.5. A profile fit started from the
  automatic peak search fits **single** peaks (`JOBT = 2`) with the asymmetry at 0 and the
  positions held, refining intensities and background. A fit read from a `.PIK` file can fit
  Kα1/Kα2 pairs (`JOBT = 1`), and there the ratio is global profile parameter 1, with a refine
  flag the user sets.
- DICVOL06, checked in its manual (`dicvol06.pdf`). It reads positions only, with one
  wavelength (Cu Kα1 by default) and an absolute 2θ error `EPS`, 0.02-0.03° recommended. The
  doublet is the picker's problem upstream.
- TOPAS, not read this session. An emission profile's line areas are fixed numbers unless
  given a name, by the Technical Reference's rule that only named parameters refine (§2.1,
  recorded under Sources below).

So no program surveyed refines the doublet ratio of a peak fit by default. GSAS-II and
WinPLOTR both offer it as a flag the user sets. Of the three programs read, GSAS-II alone
applies a nonzero axial term by default. rietx refines the ratio only in a Rietveld plan that
names it: the `lines_axial` stage of the `lab_bragg_brentano` and `lab_calibrate` presets, and
of the round-robin QPA test's own plan. WP-2055 measured why the picker should not: on the 16 IUCr round-robin
patterns the fitted ratio runs from 0 to 0.462 on one tube and one diffractometer, so it is
absorbing profile shape, not measuring the tube.

## Machinery and the heuristics that drive it

Surveyed 2026-10-30 by the lead for issue #1224, which proposes landing machinery (what an
agent operates) before heuristics (the automatic route through it). Software engineering
calls this the separation of mechanism and policy. Read in full only where marked checked.

| Source | What it does or says | Read |
|---|---|---|
| Wulf et al. (1974) Commun. ACM 17, 337, HYDRA's design principle 2 | Separating mechanism from policy "leaves the complex decisions in the hands of the person who should make them". A kernel holds mechanisms, and "policy decisions certainly are not" in it. It credits Brinch Hansen (1970) for the argument | checked (OCR of the scan) |
| Levin et al. (1975) SOSP 5, 132 | Complete separation is impractical. The scheduler keeps a parametrised policy in the kernel, so the policy outside sets its parameters | inferred from two course summaries; paper not reached |
| scikit-learn, Buitinck et al. (2013) arXiv:1309.0238, §2.1 and §4 | Every estimator parameter has a "sensible default" giving "a baseline solution", for non-experts. Every parameter is a public constructor argument. Model selection (`GridSearchCV`) is a meta-estimator built only from that public interface | checked |
| cctbx and PHENIX, Grosse-Kunstleve & Adams (2003) IUCr Comput. Comm. Newsl. 1 | "PHENIX depends on the cctbx, but not vice versa", which keeps the toolbox a reusable library. High-level refinement protocols are written in Python above it | search excerpt; page refused (403) |
| TOPAS, Coelho (2018) J. Appl. Cryst. 51, 210 | A least-squares kernel driven by an input language whose macros, `topas.inc` among them, carry the refinement recipes as text a user reads and overrides | bibliographic only; inferred from the input format |
| X Window System, via Raymond (2003) *The Art of Unix Programming* | X's designers shipped "mechanism, not policy". Users met inconsistent interfaces as a result | secondary blog quoting the book |
| Sadowski et al. (2018) ICSE-SEIP, Google's code review | Small changes get first feedback in a median under an hour, very large ones in about 5 hours; the median change is about 24 lines | secondary summaries; paper not reached |

What it adds up to. The principle has been settled since the 1970s. Two refinements matter for a
rietx rule. First, mechanism is allowed a default (scikit-learn, Levin) provided the default is
an exposed, overridable parameter; rietx's form of that condition is the audit tier, so a
default that needs no ruling (tier 1 or 2), or a required argument on an opt-in verb (a `caller`
row), can land with its machinery. Second, policy has to follow: X shows the cost of mechanism
shipped with no policy, and scikit-learn's defaults exist for the non-expert. rietx separates per
audit row, finer than cctbx's per-package split, because its thresholds sit inside machinery
modules. No test in the tree checks import direction between the two (checked by grep).

## Grading the evidence behind a heuristic

Surveyed 2026-10-30 by the lead, asked whether the audit's tiers (`docs/milestones/
generality.md` § The rule) match how other fields grade the evidence behind a model choice.
None of the sources below is a Rietveld program, since none of the seven grades its own
defaults.

| Source | What it grades | Its counterpart in the tiers | Read |
|---|---|---|---|
| GRADE, Guyatt et al. (2008) BMJ 336, 924 | Quality of evidence, and separately the strength of a recommendation | The tier grades a statistic or threshold, and the judgement ground decides the action whatever its tier | abstract and summaries; that a strong recommendation may rest on weak evidence is recalled from later GRADE papers, not checked |
| Sandia PCMM, Pilch, Oberkampf & Trucano (2007) SAND2007-5948 | Four maturity levels on six elements, one of them uncertainty quantification and sensitivity analysis | No element: a consequence axis was considered and not taken (generality.md § Decisions, 2026-10-20) | Sandia's abstract; level criteria not read |
| NASA-STD-7009A (2016) | Five levels per factor, among them input pedigree, use history and results robustness | Pedigree is the tier. Use history is tier 2's program default | NASA summaries; the handbook's level criteria not read |
| Sculley et al. (2015) NeurIPS 28 | Names fixed thresholds and configuration as hidden debt | The reason the table exists | secondary summaries |
| Simmons, Nelson & Simonsohn (2011); Steegen et al. (2016) | Each analysis choice is a degree of freedom; a multiverse analysis reports the answer across every reasonable choice | The three-family ground with its stated failing case; no multiverse | secondary summaries |

Measured on the tree at 44de0f62a: 1266 rows; 871 `unaudited` under the shrink-only baseline,
149 tier 1, 41 tier 2, 142 tier 3, 44 `invariant`, 19 `caller`. Of the 41 tier-2 rows, 40 cite
a dated source and one (`StageResult.window_area_tol`) rests on program defaults alone. All 142
tier-3 rows carry an `approved` date. That date is not tied to the row's value: a value retuned
under the same tier keeps it, and `tests/audit_delta.py` prints the change for the judge
without failing on it.

## The tier-2 rows resting on a program default

| Row | Programs that agree | Dissent |
|---|---|---|
| `Source:dispersion` (f′, f″ on for X-rays) | all seven (BGMN through the `.ano` table its default `LAMBDA=CU` names; other line files drop it silently) | none |
| `mode` rows (Rietveld) | GSAS-II, MAUD, EasyDiffraction, BGMN (Le Bail only with no atoms); FullProf, RIETAN-FP and TOPAS make the user state it | none |
| `two_theta_limits` rows (the full range) | GSAS-II, FullProf, RIETAN-FP, MAUD, EasyDiffraction; BGMN takes the instrument function's range; TOPAS's default is not stated (its `start_X`, `finish_X` are optional) | none |
| `refine:solver` (Marquardt-damped) | GSAS-II, TOPAS, RIETAN-FP, MAUD, EasyDiffraction, BGMN (regularised Gauss-Newton) | FullProf: Gauss-Newton with relaxation factors, undamped |
| `_TCH_ETA`, `_TCH_GAMMA` | GSAS-II, FullProf, RIETAN-FP, EasyDiffraction, TOPAS (whose §7.2 prints the cubic η term as 0.1116, likely a misprint of 0.11116) | none; MAUD and BGMN do not use TCH |
| `CELL_MIN_LENGTH_A` (1.5 Å) | TOPAS | none floor a cell length; the floor binds on no real cell |
| `auto_background:seed` (not from the data) | all seven start from zero, a constant or the user's numbers | none |
| `BRINDLEY_MU_R_FENCE` | the citation; FullProf prints the same classes as text | not asked of the others |

## Dropping candidates in a search race

Surveyed 2026-10-31 by the lead, for #1262's assignment race (WP-1997): when may a search over
several discrete configurations stop running one, if dropping the right one makes the answer
wrong? Hyperparameter search and algorithm configuration answer this. All from recall; no
source was opened, so every row is inferred. The lead's reading of AutoML practice ends
around early 2026.

| Source | What it does | Fit to the race |
|---|---|---|
| Successive halving, Karnin et al. (2013) ICML; Jamieson & Talwalkar (2016) AISTATS | Run every configuration on a small budget, keep the better half, double the budget, repeat. Fixed budget: it drops half whatever the margin | What #1262 ships. Right when the short-budget ranking predicts the final one |
| Hyperband, Li et al. (2018) JMLR 18, 185 | Runs halving at several levels of aggressiveness, one bracket dropping nothing | Bounds the cost of a misleading early ranking to a constant factor of budget. Hedges rather than tests |
| Hoeffding races, Maron & Moore (1994) NeurIPS 6 | Drops a configuration once a confidence bound puts it worse than the leader | Fixed confidence: the form an all-or-nothing loss asks for |
| F-Race, Birattari et al. (2002) GECCO; irace, López-Ibáñez et al. (2016) Oper. Res. Perspect. 3, 43 | Racing with a Friedman test across instances or seeds, from algorithm configuration | The closest field. Needs a run-to-run spread, so several seeds per configuration |
| LUCB, Kalyanakrishnan et al. (2012) ICML | Fixed-confidence best-arm identification with a sample bound | The bandit statement of the same problem |
| SMAC3's intensification, Lindauer et al. (2022) JMLR 23, 54 | Re-runs a challenger against the incumbent on more seeds before rejecting it | A library form of racing |
| Optuna `SuccessiveHalvingPruner`, `HyperbandPruner` | Library implementations of the two halving rows above | Same algorithm as #1262; a dependency would hold the race's state outside the byte-identical checkpoint |
| TPE, Bergstra et al. (2011) NeurIPS 24 (Optuna's and Hyperopt's default sampler) | Models where good results came from to choose the next configuration to try | Not this problem: the assignments are few (six for NAC) and all are tried. Nor the inner search, where many coordinates and cheap evaluations favour annealing, as in DASH, FOX and TOPAS |

What it adds up to. Halving is established practice under a fixed budget. Under an all-or-nothing
loss, practice is racing: drop only past the measured noise. Ruled 2026-10-31 (WP-1997): halving
ships, and racing is the next solver PR's first task.

## Correlations against a parameter the data does not determine

Read 2026-11-01 for WP-2050. When the normal matrix carries a direction the data does not
move, how does a program report the correlations of the parameters in it? rietx kept such a
direction at an eigenvalue rounding set, and its correlation guard then reported pairs
against the direction's members, or not, as a 1e-14 change to a start value moved them.

| Program | What it does | Mark |
|---|---|---|
| GSAS-II 5.8.4 | Scales the Hessian to unit diagonal, then takes a pseudo-inverse that zeroes every singular value under `SVDtol` × the largest (`GSASIImath.setHcorr`, `GSASIImath.py:131-148`; `pinv`, `:64`). The default is 1e-6 (`GSASIIobj.py:20`; the GUI allows 1e-9 to 0.01, `GSASIIdataGUI.py:8261`). Correlations come off that truncated inverse. Pairs above `max(0.95, 0.99 × the largest)` are listed, or above `min(0.99, …)` once a singular value was zeroed (`GSASIImath.py:143-147`). The count of zeroed values is reported as "soft (SVD) Hessian singularities", with the parameters most involved (`setSVDwarn`, `GSASIImath.py:150-162`; `GSASIIstrMain.ReportProblems`, `:54-139`) | checked |
| TOPAS v9 | Errors and the correlation matrix (`C_matrix_normalized`) come from an SVD by default; `use_LU_for_errors` switches to LU, which "results in very large errors" for fully correlated intensities (Technical Reference §5.10, "Errors - SVD and bootstrap errors"). The SVD cut is not stated. Nothing in the reference suppresses or flags a correlation against an undetermined parameter | checked; cut not stated |
| FullProf 8.20 | Writes the correlation matrix on request (`Mat=1`, manual "Common flags"). The manual advises refining separately any pair above about 50 % (p. 14). No treatment of a singular direction beyond advice to start with the scale alone (Trouble shooting) | checked |
| RIETAN-FP, BGMN, MAUD, EasyDiffraction | not checked | |

**The practice.** The two programs whose solve is documented take the correlations off a
pseudo-inverse truncated at a relative cut, so a direction below the cut contributes nothing
to any ρ. GSAS-II's cut, 1e-6 on the eigenvalues of the unit-diagonal normal matrix, is a
user setting with no stated derivation. No program found reports a correlation as
undetermined. rietx takes GSAS-II's mechanism at a cut derived from its own Jacobian's
accuracy (`statistics.resolved_correlation`): GSAS-II's 1e-6 would also have removed
brucite's zero-shift/displacement direction at 1.4e-10, whose correlations hold to 2e-5.

## Stephens anisotropic strain: the width's shape and its clamp

Collected 2026-11-02 for WP-1467 from three sources. Stephens' paper was read by the lead. GSAS-II
5.8.4's source was read by the lead. The TOPAS macros were read by the 2026-09-25 review behind the
WP, and that reading was not repeated. Stephens (1999, eq. 6) splits the anisotropic width
Γ_A with a mixing parameter ζ. (1−ζ)·Γ_A joins the Gaussian width in quadrature, and ζ·Γ_A
joins the Lorentzian one. His two examples refined ζ to 0.404 and 0.558, and holding his
first at ζ = 0 raised Rwp from 8.22 % to 10.81 % (his Table 2).

| Program | Gaussian/Lorentzian split | σ²(M) < 0 |
|---|---|---|
| rietx | none: Λ is wholly Lorentzian (ζ = 1) | clamped to zero width; the default LM driver holds σ² ≥ 0, and `STEPHENS_STRAIN_NOT_POSITIVE` reports the clamped intensity share under TRF or a joint fit |
| GSAS-II 5.8.4 | `Mustrain;mx`, Stephens' form: γ += Mγ·mx, σ² += (Mγ·(1−mx))² (`GSASIIstrMath.py:3330-3331`; checked) | no clamp at the width: `np.sqrt(Sum)` (`GSASIIstrMath.py:3265`; checked); what follows a negative sum was not traced |
| TOPAS (shipped macros) | `eta`: `gauss_fwhm = 1.8/π·pp·(1−eta)·Tan(Th)`, `lor_fwhm = 1.8/π·pp·eta·Tan(Th)` | `Sqrt(Max(mhkl, 0))`, the same clamp, reported nowhere; `Stephens_tetragonal` takes `Abs()` first, folding a negative σ² back into a positive width (TOPAS wiki, read 2026-09-25 by the review) |

So no program reports a fit that leaned on the clamp, and a TOPAS Stephens fit carries no
evidence that σ²(M) stayed positive. A protocol that refines ζ cannot be mirrored in rietx
(WP-0503's fence).

## Testing the residual for serial correlation

Surveyed 2026-11-04 for WP-2086, which reads Hill & Flack's test as a decision. Their paper
(1987, J. Appl. Cryst. 20, 356, eq. 2, read) sets Q = 2[(N−1)/(N−P) − 3.0902/(N+2)^½], the
0.1 % point, and reads d < Q as neighbours sharing a sign and d > 4 − Q as neighbours
alternating.

| Program | d | The threshold it states |
|---|---|---|
| rietx | `Statistics.durbin_watson`, printed as `DW` | Q as the paper prints it, used to gate the instrument half of the unseen-phase hold and never printed |
| FullProf 8.20 | `DW-Stat.` in the `.sum` file (ran) | `DW-exp`, printed by default. The manual's QD (eq. 3.20) and the output are the paper's Q with 3.0901: N − P 5723 and 5275 give the printed 1.9301 and 1.9277 to the digit (ran on `pbso4.sum`, N from N−P+C and P = 34) |
| RIETAN-FP 3.12 | defined in the manual, § Durbin–Watson statistics | the paper's Q, manual eq. 4.32, and its 4 − Q |
| GSAS-II 5.8.4 | `Histogram['Residuals']['Durbin-Watson']`, `GSASIIstrMath.py:4995` | none |
| TOPAS (Tech. Ref. v9) | among the criteria of fit, § 5.19 | none stated |
| BGMN, MAUD, EasyDiffraction | no match for "durbin" in the BGMN and EasyDiffraction trees or MAUD's java source (searched by file text, not read, and PDFs not searched) | none found |

On white noise of 3000-22 000 points (200 000 draws, 60 000 at the largest, not fitted, P 12-34),
the one-sided test d < Q fires 0.17-0.41 % of the time.

Every program that has the test reports it. None gates an action on it, and none holds an
instrument term because no phase is seen (§ Staging and what a stage holds; `StageResult.held`'s
audit row). So rietx's use of the threshold is its own, and the number is the paper's.

## A parameter set by an equation the user writes

Surveyed 2026-11-03 for WP-1964, three agents and the lead, across scattering software, global
fitting in other fields, and expression languages. The lead re-read the TOPAS rows in the Technical
Reference and in the Durham inputs. Web pages were read through a summarising tool, so wording in
the non-TOPAS rows is unverified. "Checked" means the page or file was read; "recall" means it was
not. Every source is a user document or paper, and no closed or GPL code was read.

| Program or format | How the form is written | Parameters, sharing, bounds | Per-dataset values | Derivatives | Status |
|---|---|---|---|---|---|
| TOPAS | a string on any parameter, one grammar throughout (Tech. Ref. Table 3-1): `+ - * / ^`, `If`, `And`, `Or`, `Min`, `Max`, `Exp`, `Ln`, `Gamma_P` and more; user `fn` with `def` and `return` (§21.3) | `prm` is global and `local` per `xdd` or `str` (§2.2); sharing is by name; min and max are equations (§2.3) | `#list` of macros, or a generated `prm` per pattern (§2.26.2) | computer algebra carries the chain through equations (§21.3.2, Coelho 2018 abstract); `del` is the step for numerical derivatives of the pattern (§2.3) | checked |
| GSAS-II | a Python-syntax string, fitted to the sequential table after the refinement and stored with it (`SeqParFitEqList`), never in a joint residual, and also usable as an expression restraint; external functions allowed | a repeated label links equations; a `b` is auto-renamed to stop accidental sharing | the table's columns | not stated | checked, derivatives recall |
| FullProf | `EQUAL` and `PEQU_pat` link parameters; no equation in a coordinate found | none found | none found | none found | search excerpts |
| Jana2020, MAUD | no equation across datasets found | | | | not found |
| Artemis, Larch | strings on path parameters, with roles `guess`, `def`, `set`, `lguess`, `restrain`, and built-in `eins()`, `debye()` | by name | `set` per dataset | finite difference (recall) | checked |
| Mantid | tie strings, muParser (search excerpt) | `$domains=All`, ties, bound strings | from the workspace | analytic if the function supplies it, else numerical with a named step | checked |
| Bumps, refnx | operator overloading on `Parameter` objects builds a lazy tree | one shared object | model objects | not stated | checked, refnx syntax recall |
| lmfit | a Python-syntax string run by asteval | `Parameter(value, min, max, vary, expr)` | caller's own | finite difference (recall) | checked |
| PEtab (systems biology) | formula strings in tables; v1's page names no grammar | one parameter table holds bounds, start and estimate; v2 removed `parameterScale` as "a constant source of confusion" | a condition table of overrides by id | AMICI: symbolic partials, sparse assembly, threads over conditions | checked |
| NONMEM, Monolix, nlmixr2 | code lines; the structural model and the covariate model are separate layers | `(low, init, up)` per coefficient; covariates centred on a reference | columns of the dataset | sensitivity equations (recall) | checked |
| pyhf, HS3 (particle physics) | pyhf: seven closed modifier types; HS3: a graph with a generic-expression escape, its grammar the least specified part | by name, in a flat namespace; bounds sit in a separate measurement block | channels | autodiff (recall) | checked |
| RooFit | `RooFormulaVar` strings over shared objects | one object, many models | an index category | numerical, or generated code with Clad | checked |
| JuMP, CasADi, AMPL | the system owns an operator tree or graph with a registered vocabulary, and never evaluates host code | variables apart from data | data apart from the model | exact, on the graph; forward mode for small user operators | checked, AMPL recall |
| CEL | a written grammar with a version and conformance tests, no side effects, always terminates | | bindings | none | checked |

What they agree on.

- **Form.** Every system with exact derivatives owns a tree with a closed operator list. `asteval`
  and `simpleeval` evaluate python values, so they expose nothing to differentiate. sympy's
  `parse_expr` calls `eval` and `lambdify` calls `exec`. sympy 1.14.0's `lambdify` does ship a
  `torch` module (`MODULES`, checked 2026-11-04), so DESIGN.md's reason has aged and these two
  grounds carry the rejection. General parser libraries such as lark were not surveyed.
- **Sharing.** Text formats share a coefficient by name, and python APIs (Bumps, refnx, RooFit)
  by a shared object. The per-dataset value is an ordinary fixed number. Start, bounds and fixed
  flag sit beside the equations.
- **Grammar.** Where a format left its grammar unwritten (PEtab v1, HS3), the first parser became
  the specification. PEtab's test suite and CEL's conformance tests are the counter-examples: small
  cases with an expected number.
- **Presets.** Monolix's library and nlmixr2's `linCmt()` expand into the expert layer. No program
  found has a second parser for its presets.
- **Traps.** TOPAS ignores min and max on a parameter defined by an equation, as stated in its forum
  (threads 767 and 831, checked). The Reference pages read here do not say so. A generated
  equation's error points at `topas.log` rather than the user's text. `x^y^z` is left-associative in
  TOPAS (Table 3-1) and right-associative in python and most mathematics. `^` is XOR in python's
  parser.
- **Nonlinear fits.** Systems biology treats multi-start with a sorted-objective plot as routine, and
  profile likelihood as the honest interval, because a Wald interval is symmetric (Villaverde et al.
  protocol, checked). Evans warns that a wrong form can fit better than the right one, and recommends
  a sequential fit unless there is a good reason (slides and forum 582, checked).

Not reached: `Topas.inc`, the Jana2020
and MAUD manuals, the HS3 expression appendix, and MathOptInterface's nonlinear pages.

### The same language across a program

Surveyed 2026-11-06 for WP-2118, by the lead and two agents. The table above asks how one
parametric equation is written. This one asks what a formula language does across a whole
program. The lead read the TOPAS Technical Reference (version 9), the GSAS-II 5.8.4 source, the
FullProf 8.20 manual and Stinton & Evans (2007). The agents read the other programs' pages through a
summarising tool, so wording in those rows is unverified. Lepton's `Parser.cpp`, JuMP's changelog
and muParser's `muParserDef.h` were read as files. "Checked" means read this session, "search" means
a search-result excerpt only, and "recall" means not read. No closed or GPL code was read.

The columns are the seven questions of WP-2118's first task.

- **Grammar.** Does one language serve constraints (a parameter set by a formula), restraints
  (a penalty on a formula) and model equations?
- **Names.** How does a formula name a model quantity?
- **Declared.** Is the formula stored on the parameter, in a separate list, or made by a command?
- **Linear.** Is a linear constraint kept on a separate, faster route?
- **Version.** Is the grammar or its stored text versioned, and how is old text upgraded?
- **Error.** Does an error point at a place in the user's text?
- **Units.** Are physical units checked?

| Program | Grammar | Names | Declared | Linear | Version | Error | Units | Status |
|---|---|---|---|---|---|---|---|---|
| TOPAS | one: an equation can stand for any parameter's value (§2.4, "linear and non-linear constraints"), for its `min` and `max` (§2.3), and for a `penalty` (§5.6) | a parameter is named where it is declared, `beq b1 0.5` (§2.1). Names are identifiers with no dots, and `local` scopes one to its `str` or `xdd` (§2.2) | on the parameter: the equation replaces the value, `occ Ti+4 = 1-zr;` (§2.4) | none. Linear and nonlinear equations take one route through computer algebra (§2.4; Coelho 2018) | none stated. Macro meanings changed between program versions, for example `Ramp` after Version 4 (§4.1.6) | not stated in the Reference; the earlier rows record `topas.log` | none | checked |
| GSAS-II 5.8.4 | two: linear constraints in their own records (`GSASIImapvars`: equivalence, `Constr`, `New Var`, hold), and Python expressions (`ExpressionObj`) for general restraints, pseudo-variables and fits to the sequential table (`GSASIIobj.py:1697-1703`) | bare labels, each bound to a GSAS-II variable name by a table (`assgnVars`), since those names hold colons (`0::A0`) | separate lists: the Constraints and Restraints trees, and the sequential table's equation list | yes. Linear constraints are solved apart by `GSASIImapvars`, and expressions never constrain | none on the expression; the project is a pickle | Python's `SyntaxError` lines, which carry a caret (`GSASIIobj.py:1886-1893`) | none | checked |
| FullProf 8.20 | linear codewords only, C = sign(a)(10p + a) (manual, § Rietveld refinement) | a parameter number p | in the `.pcr` file, beside each parameter | the codeword is the only route | n/a | n/a | none | checked |
| OpenMM's Lepton | one syntax across the custom forces, restraints included. Holonomic constraints are a separate mechanism | bare names, declared by `addGlobalParameter` or `addPerParticleParameter` | a command: the formula is a constructor argument | none | no grammar version. The XML serializer versions each force and refuses a mismatch, with no migration | a message that echoes the whole formula, with no position (`Parser.cpp`) | none; the host API's units are implied | checked |
| Stan | one language for model statements, transformed parameters and generated quantities. Bounds are a transform on the declaration | bare names of declared variables. `pi()` is a function | in typed blocks of the program | none | no version flag. Each deprecation names its replacement and its removal version; the compiler warns, then errors; `stanc --print-canonical` rewrites old code | file, line and column range | none (recall) | checked |
| JuMP / MathOptInterface | one Julia expression tree for objectives and constraints since JuMP 1.15. Before that `@NLconstraint` was a second language | host objects (`VariableRef`) | a command (`@constraint`, `@expression`) | yes, by design: affine and quadratic forms are built as their own types, and only the rest is nonlinear (`ScalarAffineFunction`, `ScalarNonlinearFunction`) | MathOptFormat files carry a major and minor version and a JSON schema. The legacy `@NL` macros were kept unchanged | Julia's own errors; a MathOptFormat file error names the JSON path | none (recall) | checked |
| CasADi | one symbolic graph for constraints, objectives and model equations | host objects; the string is only a display name | a command (`opti.subject_to`) | opt-in (`Opti('conic')`, `detect_simple_bounds`) | `Function.save` since 3.5.5, with no cross-version promise found | Python and C++ tracebacks | none (recall) | checked, serialization search |
| lmfit | constraints only. Restraints are terms the user adds to the residual | bare parameter names, Python identifiers, so no dots | on the parameter, `Parameter(expr=...)` | none: `expr='b'` is a formula like any other (recall) | none | a message kept in `interp.error`, with no position | none | checked |
| Mantid | ties are muParser expressions. Bounds are a separate mini-language (`4.0 < c < 4.2`) applied as a penalty | bare names in one function; `f1.Sigma` in a composite, so a dot prefix names the member function | a fit property (`Ties`) or inside the function string | none: `f1.Sigma=f0.Sigma` is an expression | not found | muParser carries a position (`GetPos`); Mantid surfacing it was not found | not found | checked; muParser use search |
| RooFit | one TFormula grammar for a derived value and a pdf. A constraint penalty is a separate pdf (recall) | by name, or by position `@0` in a list passed with the formula | a command: `RooFormulaVar(name, formula, args)` | linear forms have their own classes, such as `RooPolyVar` (recall) | none found | a message naming the unknown name, with no position | none (recall) | checked |
| CEL | one language; hosts embed it for every use | dotted names are part of the language, resolved by a written lookup order | the host binds the names | n/a | no grammar version; one change is dated to spec v0.7.0 | line and column in cel-go (recall) | none | checked |
| PEtab v1 → v2 | v1 left the formula language unwritten, and tools disagreed on precedence. v2 writes one grammar for observable, noise and condition formulas | identifiers without dots; a model name with a dot is aliased through a mapping table | separate tables and a YAML file | no ties at all | a required `format_version`, and a converter from v1 to v2 (`petab1to2`) | not found | none | checked; converter search |
| SBML, CellML, Modelica | | | | | | | SBML: optional, inconsistency warns (recall). CellML 2.0: mandatory (recall). Modelica: a `unit` attribute, checking left to the tool (checked) | as marked |

#### Angles

| Program | Trigonometry | A degree route |
|---|---|---|
| TOPAS | radians; the reserved `Th` is in radians (§2.19) | `Deg` as a multiplier in the Reference's examples, `Sin(X Deg / 2)` and `r Sin(60 Deg)`. Its definition was not on the pages read |
| GSAS-II | **degrees** in expressions: `sin`, `cos` and `tan` are defined there as degree functions, beside `sind`, `cosd`, `tand` (`GSASIIobj.py:1640-1642`) | the default |
| Stan, Lepton, Modelica, JuMP | radians | none. Julia's `sind` exists outside JuMP (recall) |
| lmfit (asteval) | radians | `radians()` and `degrees()` converters |
| CasADi, muParser, PEtab v2, RooFit | not stated | none found |

So two diffraction programs take opposite conventions, and GSAS-II's `sin(x)` means sin(x°). A
formula ported from a GSAS-II expression with a cell angle in it gives a different number in TOPAS
or in rietx, with no error. Only GSAS-II offers degree functions, and only there are they the
default.

#### A minus sign before a power

TOPAS Table 3-1 states that `x^y^z` is (x^y)^z, and says nothing of a minus sign before a power. The
§20.9.3 example writes the Fourier transform of a Voigt as
`Exp(-(Pi FT_K gfwhm)^2 / (4 Ln(2)) - Pi FT_K lfwhm)`. That transform decays with k only if
`-(u)^2` is read as −(u²), so TOPAS reads the minus after the power, as rietx does. This is an
inference from a documented example. TOPAS was not run, and how it lexes a literal `-2` is not
stated.

Everything else that defines the case reads `-2^2` as −4: Stan (precedence table), Lepton
(`Parser.cpp`), Modelica and PEtab v2 (their precedence tables), muParser (a source comment, not
run), and Python's `-2**2`. CEL has no power operator. In GSAS-II's Python syntax `^` is a bitwise
XOR, which the earlier rows record.

#### The value of a formula and its esd after a fit

WP-1964 left a gap: no call gives the esd of a curve with a per-pattern ΔT set to zero.

- TOPAS reports any equation's value by writing `: 0` after it (§2.9). With `do_errors` set, it
  reports the equation's error too, propagated through the whole covariance and scaled by the GoF
  (§2.17). A user who wants the curve at 300 K writes it as a dependent `prm` with ΔT left out.
- GSAS-II's fit to the sequential table gives each coefficient's esd from the covariance's diagonal
  (`DoParEqFit`, `GSASIIseqGUI.py:924-990`). It gives no esd of the fitted curve. A
  pseudo-variable has an esd at each pattern, from numerical derivatives with a step of a tenth
  of each esd (`EvalPSvarDeriv`, `:837-846`).
- Stinton & Evans (2007) § 4.2 plot cell parameters against the refined temperature (Fig. 6), and
  ΔT per data set beside its polynomial (Fig. 7). The passages read report no esd of a curve.

So TOPAS's route is a formula the user writes after the fit, whose value and esd the program
reports. It is general and needs no argument naming a per-pattern variable.

#### What the rows add up to

- **One grammar.** Every program that defines a formula language uses it for more than one job.
  Where it stops short, a separate linear mechanism (GSAS-II, FullProf) or bound syntax (Stan,
  Mantid) sits beside it. TOPAS alone runs constraints, bounds and penalties through one
  grammar. PEtab's move from v1 to v2 is the cost of not writing the grammar down: tools had
  disagreed on precedence.
- **Names.** A text grammar names bare identifiers, and a separate binding maps them to the
  model: GSAS-II's `assgnVars`, Lepton's `addGlobalParameter`, RooFit's argument list. Dotted
  names appear in Mantid as a member prefix and in CEL with a written lookup order. PEtab v2
  refuses them and aliases a dotted name through a table. TOPAS avoids the question by naming a
  parameter where it is declared.
- **Declared.** Text formats store the formula on the parameter (TOPAS, lmfit). Programs with an
  API make it with a command (Lepton, JuMP, RooFit, CasADi). GSAS-II and PEtab keep lists.
- **Linear.** The diffraction programs that separate linear constraints (GSAS-II, FullProf)
  have no nonlinear constraint. JuMP keeps affine forms as their own type because solvers
  exploit them. TOPAS, lmfit and Mantid run a linear tie as an ordinary formula.
- **Versions.** Stan's practice is the most complete. Each deprecation names its replacement and
  removal version, the compiler warns and then errors, and a canonicaliser rewrites old text.
  PEtab and MathOptFormat put a version on the file. No program surveyed stores a grammar version
  beside each formula.
- **Errors.** Stan gives line and column, Python and muParser a position, and the rest a message.
- **Units.** Only the model-exchange formats (CellML mandatory, SBML and Modelica optional) check
  them. No fitting program surveyed does.

Not reached: the SBML and CellML specification pages, Mantid's error output, and TOPAS's lexing of
a signed literal.

## An equation over a reflection

Surveyed 2026-11-04 for WP-2107. This is about a value that differs between reflections, set by
something the user writes. "Checked" means the document or source was read.

| Program | What the user can write | Symmetry | Status |
|---|---|---|---|
| TOPAS | an equation in `H`, `K`, `L`, `M`, `Xo`, `Th` and `D_spacing` on `lor_fwhm`, `gauss_fwhm`, `th2_offset`, `scale_pks`, `hat`, the other convolutions and more (Tech. Ref. Table 2-3). `spherical_harmonics_hkl` and `str_hkl_angle` supply values to use in one. A separate peak shape is then calculated for each peak (§ `peak_buffer_step`) | left to the user, with `Multiplicities_Sum` to iterate over the multiplicities (§ 20.17, `scale_occ`). Which image an equation sees otherwise is not stated | checked (Technical Reference); not run |
| FullProf | closed models chosen by integer: selective size (`IsizeModel`) and selective shift (`ModS`). The user may add rules on the indices, each a linear equality, up to 10 lines for shifts. The shift takes the form 2 SHIFT d² tanθ × 10⁻², and no free expression was found | a rule is applied to the hkl FullProf holds; not established further | checked (manual, § Selective size broadening and § HKL-dependent shifts) |
| GSAS-II 5.8.4 | none. Size and microstrain take built-in forms (`uniaxial`, ellipsoidal, generalized). `ExpressionCalcObj` reaches restraints, and no reflection-level use was found in `GSASIIstrMath.py` | derived from the Laue class in the built-in forms | checked (grep of the source) |

TOPAS's own examples are `If(L==0, a Tan(Th) + 0.2, b Tan(Th))` on `gauss_fwhm`, `If(L == 0, at Tan(Th), bt Tan(Th))` on `th2_offset`, and a March relation over `str_hkl_angle` on `lor_fwhm`. TOPAS's `occ` stays single-valued for QUANT, so it cannot be a function of hkl, and `scale_occ` exists for that case. Whether its QPA reads a `scale_pks` is not established.

Stinton & Evans (2007) use both shapes: a second-order 2θ calibration polynomial on the whole pattern (§§ 4.1, 4.2) and two terms of extra broadening on 0kl reflections (§ 4.3). They also give each phase its own TCHZ terms, shared across patterns. Their first example fits a sample holder by Pawley beside two Rietveld phases, and their second refines one temperature offset per data set through every phase's cell equation (checked).

Of the Durham tutorials, ZrP₂O₇ writes a two-coefficient curve in `Xo` on `th2_offset`, and ZrMo₂O₈ writes a tanθ width scaled by `spherical_harmonics_hkl` with fixed coefficients. WO₃'s two lines need neither: one is an overall B and one a sample height. Incidence over a larger set is not measured, since the private archive was not on the machine that ran this, and since 2026-11-04 it decides nothing here.

## The window layout of a GUI

Surveyed 2026-11-06 to 2026-11-08 for the gui-overhaul milestone, and restated 2026-11-08 for
WP-2123. Desktop applications rather than refinement programs, because the question is how a
window lets a person hide, resize and stack its panels. Each row is marked checked (read in the
product's documentation) or recall (from use, not re-read).

| Program | Panel toggles | Resizing | A narrow window | A choice among views |
|---|---|---|---|---|
| VS Code | a layout control for each side bar and the panel, at the matching end of the title bar; each never moves (checked, user interface docs) | a sash between parts; drag, double-click resets (recall) | parts stay side by side; the window has a minimum width (recall) | — |
| Xcode | the navigator toggle at the toolbar's left end, the inspector toggle at its right (recall) | drag the divider (recall) | panes stay side by side (recall) | segmented controls in the toolbar and inspectors (recall) |
| Claude desktop app | the side panel's toggle sits on its own side (recall) | drag the divider (recall) | drops to one panel below a width (recall) | — |
| macOS and iOS | — | — | — | a segmented control draws its choices on one track, the chosen one raised (recall, Apple Human Interface Guidelines) |
| GSAS-II 5.8.4 | none: the data tree on the left and the notebook on the right are fixed (recall) | a splitter between them (recall) | — | — |

The practice these add up to: each side's toggle sits on its own side and does not move, a sash
resizes and a double-click resets it, and a segmented choice is drawn on a track rather than as
a row of buttons. Only the Claude app drops to one column below a width; the maintainer chose
that behaviour on 2026-11-07. The refinement programs offer no model for any of this: TOPAS works
through a text editor, and FullProf's and GSAS-II's windows are fixed panes (recall).

## Where a GUI keeps its secondary controls

Gathered 2026-11-11 for WP-2214, the GUI rebuild's inventory, which gives every control of the
old GUI a home in the new design. Every row is recall (from use, not re-read).

| Program | Commands | An object's actions | Facts and live state | A plot's options and export |
|---|---|---|---|---|
| VS Code | a command palette holding every command with its key | a right-click menu on every item | the status bar: language mode, encoding and the Problems count on the right, each opening a menu or its panel | — |
| Figma | a quick-actions search | a right-click menu on every object; a properties panel showing only what fits the selection | — | — |
| Origin, Igor Pro | the menu bar | — | Origin's status bar reads the cursor's coordinates | a right-click menu on the plot (copy, export, axis options) and a plot-details dialog |
| ImageJ, QGIS, GIMP | the menu bar | — | the status bar reads the pointer's coordinates and the value under it | — |
| GraphPad Prism | the menu bar | — | — | a format dialog opened from the graph; the graph window shows only the graph |
| GSAS-II 5.8.4 | the menu bar | a right-click menu on a plot for a few actions | — | — |
| Gmail, GitHub | single-letter keys for frequent verbs; `?` lists them | — | — | — |
| macOS | ⌘. cancels the operation in progress (Human Interface Guidelines) | — | — | — |

The practice these add up to: the window shows the work and few controls. An object's actions
sit on that object, behind a right-click or a selection. A command palette or a list of keys
holds every command. The status bar carries facts about the document and the pointer. No
refinement program draws its window this way, so the rebuild follows the desktop applications.

## The start screen and the New project flow

Surveyed 2026-11-08 for the maintainer's round-9 GUI design and restated 2026-11-09 for WP-2131.
Desktop applications again, because no diffraction program has a start screen: GSAS-II,
FullProf's WinPLOTR, TOPAS and Profex each open on an empty main window (recall, not re-read).
Each row is marked checked (read in source or documentation) or recall (from use, not re-read).

| Program | The first screen | At launch | A new project asks first |
|---|---|---|---|
| VS Code | Welcome: Start (New, Open), Recent, Walkthroughs (recall) | reopens the last folder (recall) | a folder; no name step (recall) |
| JetBrains IDEs | New Project, Open, a recent list with a ⋯ menu and Remove from list, Learn (recall) | reopens the last project, a setting (recall) | the name and the location, then the language (recall) |
| Xcode | Create, Clone, Open, and the recent list beside them (recall) | the welcome window, a setting (recall) | a template, then the name, then the place (recall) |
| Blender | the splash: New File, Open, Recent, links to the manual and the release notes (recall) | the splash over a default scene (recall) | — |
| Obsidian | Create, Open folder, the vault list (recall) | reopens the last vault (recall) | the vault's name and location in one dialog (recall) |
| Profex 5 | — | an empty main window (recall) | one dialog: the pattern, then the device's instrument file (recall) |
| GSAS-II 5.8.4 | — | an empty data tree (recall) | importing a pattern with no instrument file offers a list of default instrument files, the first `CuKa lab data`; Cancel imports nothing (checked, `defaultIparms.py:31`, `GSASIIdataGUI.py:1840-1860`) |

Interface guidance read the same day, from recall: Apple's Human Interface Guidelines and
Microsoft's Fluent 2 both advise onboarding that can be skipped and is brief, and Nielsen Norman
Group's articles advise a wizard only where a later step depends on an earlier answer. The four
answers here are independent, which is the case for one dialog.

The practice these add up to: New, Open, a recent list and a small learning area, with no tour;
reopen the last project at launch; ask for the name and the place before anything else. The
round-9 design follows all three. Its departure is the instrument: no surveyed program assumes one
silently, and GSAS-II makes the person pick from a list. rietx assumes the first entry of that list
and tags the line `assumed`. Claude settled that call in the round-9 design of 2026-11-08, and it
is reversible.

## A pattern recalculated while a control moves

Surveyed 2026-11-09 for WP-2125, lightly: a minor decision, so one search and recall. The
question is whether a program redraws the calculated pattern while a person drags a value, and
how fast a drag must be answered. Each row is marked checked (read in the product's
documentation) or recall (from use, not re-read).

| Program | Live recalculation while a value moves | Where the model runs |
|---|---|---|
| CrystalDiffract 6 (CrystalMaker) | real-time parameter controls for diffraction and sample settings, with instant feedback (checked, a university software catalogue quoting the version 6 description, tigerware.lsu.edu); which parameters have sliders is not established | in the program |
| Diamond 5 (Crystal Impact) | the powder diagram updates automatically when structure parameters change (checked, crystalimpact.com, the Diamond 5 manual page on powder patterns) | in the program |
| PowderCell | the cell and the pattern are edited interactively and redrawn (recall) | in the program |
| TOPAS, GSAS-II, FullProf | none: a value changes by editing the input or a table, and the pattern is recalculated by a refinement or a calculate step (recall) | — |

The latency bar comes from web practice rather than from crystallography. Google's RAIL model
counts a drag as an animation, budgets 10 ms of work per frame at 60 frames a second, and
allows 100 ms for a response to feel immediate (web.dev, "Measure performance with the RAIL
model", checked). The practice these add up to: the simulation programs redraw at every step
of a control, inside the program that owns the physics, and no refinement program offers it.
rietx's GUI serves the curve from the package's own forward model through a local route, so
the page draws numbers and computes none (WP-2125).

## A stage that fixes a parameter

Surveyed 2026-11-10 for WP-2208, one agent. GSAS-II 5.8.4 source and scripting manual read (checked), TOPAS Technical Reference v9 fetched and grepped (checked), FullProf 8.20 manual and RIETAN-FP manual converted with pdftotext and grepped (checked). MAUD 3.07 was read only as compiled jars with no Java source (class strings only, inferred); nothing was run.

| Program | How a step fixes a parameter | Order within a step | Carried to the next step |
|---|---|---|---|
| rietx | `StageSpec.turn_off` since WP-2208, a `fix` clause in `.rxt`; before it a stage only freed, and a plan starts every fit from nothing free (WP-1208) | `turn_on` first, then `turn_off`, as GSAS-II | Yes: the flags carry, so a fix lasts until a later stage frees the path again. The closing stage re-solves the end state of the declared stages |
| GSAS-II scripting (`do_refinements`) | A step dict has `set`, `clear`, `once` and `skip`. `clear` switches a refine flag off, for example `{"clear": {"LeBail": True}, "set": {"Atoms": ...}}` in the manual's own recipe (checked: `GSASIIscriptable.py:2013-2105`, `:2190-2230`; `docs/source/GSASIIscriptable.rst` § Refinement recipe) | `set` for the whole step first, then `clear`, then (in `iter_refinements`) `once` is applied as a `set` before the refinement and cleared after it. A `once` entry therefore wins over a `clear` of the same key (checked: `:2085-2106`; `set_refinement` runs all `set` code before `clear`, `:2166-2230`) | Yes. The flags live in the project, so a flag set in step k stays set in step k+1 unless a later step clears it. `once` is the only auto-reverting form, and it reverts at the end of its own step (checked: `:2100-2104`) |
| GSAS-II GUI and refinement engine | Three layers. (1) An unticked refine flag. (2) A `Hold` constraint, whose dialog legend reads "Will not be varied, even if vary flag is set" (checked: `GSASIIconstrGUI.py:845-866`; `GSASIImapvars.py:52`). (3) In a sequential refinement, per-histogram "Fix FXU" and `FixedSeqVars` lists strip phase variables from one histogram's vary list (checked: `GSASIIstrMain.py:850-872`). Out-of-range variables are also frozen automatically in `parmFrozen` (checked: `GSASIIstrMain.py:1066-1073`, `:1198-1215`) | Not applicable (state, not a step) | A `Hold` is stored with the constraints and applies to every later refinement until deleted. A sequential refinement builds the vary list per histogram from that histogram's own flags (`varyList = rbVary+redphaseVary+hapVary+histVary`, `:961`) and stores the union in the result (`:974`). So the varied set can differ between histograms (checked) |
| TOPAS (Technical Reference v9) | No keyword turns a refined parameter into a fixed one between convergences inside one INP. A parameter refines unless it is written `prm !b1` (checked: § 2.2 "User defined parameters", `prm !b1 0.2`). The `Constant(expr)` function evaluates once and freezes the number (checked: `Constant(expression)` entry). `quick_refine_remove` drops parameters temporarily inside a cycle and reinstates them at the start of the next cycle (checked: § quick_refine). `val_on_continue` changes a parameter's value after convergence, not its flag (checked: attribute list in § 2.3) | Not applicable | `num_runs` restarts the INP, and the INP is re-read each run. State crosses a run only through the OUT file and `#include`. "Equations may simplify to a constant during a run" is the documented way a parameter stops refining in a later run (checked: § `num_runs`). `Run_Number` and `Cycle` are readable in equations and `#if`, so a run can branch on them (checked) |
| FullProf 8.20 | A refinement code of 0 means "not refined"; the code is `sign(a)(10p + a)` (checked: manual lines 589-596 of the text dump). A run does not change codes. The user edits `CODFIL.pcr` between runs. `Aut=1` renumbers the codes automatically so that zeroing one in the middle leaves no hole, but it only renumbers what the user edited (checked: `Aut` description, text lines 3494-3508) | Not applicable | The program writes `CODFIL.new` or rewrites the PCR on every run, codes included, so edits persist (checked: text line 326). In sequential mode (`CYC`) pattern n+1 starts from the PCR updated by pattern n, with the same codes for every pattern (checked: text lines 285-296). The manual's staged order is advice for the user's own edits (scale, then zero/background/cell, then positions, then profile, and so on; checked: text lines 618-640) |
| RIETAN-FP | With `NAUTO=1` the user lists the parameters refined in each of the first cycles, one line per cycle, ended by `/`. The manual's example lists background and scale in cycle 1, cell in cycle 2, profile in cycle 3, structure in cycle 4. Read plainly, each listed cycle refines only its own list, so cycle 2 holds the background fixed that cycle 1 refined (checked: § 17.3.17, text line 8625; the exclusive reading is from the wording and was not run) | The listed groups run in order. After the last listed cycle, all parameters with `ID(I)=1` refine together (checked: § 17.3.17) | Not applicable. The schedule lives in the input file and is the whole recipe. `NAUTO=2` picks the groups automatically (checked: § 17.3.17, § 4.1.4) |
| MAUD 3.07 | Not reached. Only compiled jars are on disk. The class `launchRefineWizard` calls `FilePar.prepareWizard` and prints "Start first cycle ... Start last cycle". `FilePar` has `freeAll*Parameters` and `fixAll*ParametersPreserveBound` methods, so fixing is available to it. Whether the wizard fixes a parameter an earlier step freed was not determined (inferred from class strings, not source) | not determined | not determined |

### Pawley or Le Bail first, then Rietveld

| Program | How the documentation does it | One job or two |
|---|---|---|
| GSAS-II | The scripting manual's example recipe sets `LeBail` and the cell, then profile terms (`Instrument Parameters` U V W X Y), then a step with `{"clear": {"LeBail": True}, "set": {"Atoms": ...}}`. The profile flags stay set in that example, so the profile keeps refining in the structure steps. To lock it one would add `clear` of those terms (checked: `GSASIIscriptable.rst` § Refinement recipe). | One job, several steps, flags carried. |
| TOPAS | Le Bail and Pawley extraction use the `hkl_Is` block with `lebail` (§ 20.2, examples `lebail1.inp`, `pawley1.inp`). A structure refinement uses a `str` block. The TR documents no switch inside one INP, and an INP re-run takes its flags from the text (checked). That the usual practice is to edit the INP between the two jobs is from memory (inferred). | Two INP files, or two edits of one. |
| FullProf | The manual says to analyse by profile matching first ("to determine accurately the profile shape function, background and cell parameters before running the Rietveld method"; text lines 610-613). Its recipe for `Jbt=2` is: run with zero refined parameters and `Aut=0`, rename `CODFIL.new` to `CODFIL.pcr`, then edit the codes (checked: text lines 674-692). | Two runs of the program with an edited PCR in between. |
| RIETAN-FP | Le Bail is a mode (`NMODE=4`). The manual's Le Bail template says to comment out the structure parameters in the same `.ins` file (checked: § 11.3, text lines 5116-5122). Rietveld is the same file with `NMODE` changed back. | Two runs of one edited input file. |
| MAUD | Not reached. | not determined |

### Practice adds up to

No program has a plan whose steps declare "fix this" as a separate list from "free this". GSAS-II comes closest and is the only one with the shape the maintainer describes: a step dict with both `set` and `clear`, flags kept in the project and carried forward, and `set` applied before `clear` within a step. `once` is its way to make a flag last for one step only. TOPAS, FullProf and RIETAN-FP all keep the recipe outside the program, as an edit of the input file between runs, except that RIETAN-FP's `NAUTO=1` list is a built-in schedule in which each cycle refines only its own group, which fixes the earlier groups. For a series, GSAS-II builds the vary list per histogram and has per-histogram fix lists, FullProf reuses one set of codes for every pattern, and TOPAS rereads the INP each run. For Pawley then Rietveld, the three documented routes are two runs with a file edit between them, with GSAS-II alone doing it as steps of one job.

## Sources

Line numbers are at the versions above. RIETAN-FP's and FullProf's manuals are cited by
section, TOPAS's Technical Reference by section and keyword as printed.

| Program | Window | Staging and freezing | Roughness, widths, limits |
|---|---|---|---|
| GSAS-II 5.8.4 | `GSASIIpwd.getWidthsCW` (`GSASIIpwd.py:811-832`); used at `GSASIIstrMath.py:4071-4077`; FCJ in `sources/powsubs/psvfcjo.for:176-188`; reflections strictly inside the limits, `GSASIIstrIO.py:3175-3177` | hkl list once per `Refine`, `GSASIIstrIO.py:3131`; `DefaultControls`, `GSASIIobj.py:18-20`; `HessianLSQ`, `GSASIImath.py:164-432` | `SurfaceRough`, `GSASIIpwd.py:129-140`, SRA = SRB = 0 at `GSASIIdataGUI.py:2078`; width floors `GSASIIstrMath.py:3901, 3903`; no default limits (`parmMinDict` empty, `GSASIIscriptable.py:2983`); `dropOOBvars`, `GSASIIstrMain.py:1198-1230` |
| FullProf 8.20 | `Wdt`, Appendix LINE 8; floored at 3 (ran); `Ias`, LINE 4 ("reordering ... only at the first cycle") | the manual's advised order, Rietveld section; solver, Mathematical section eqs 3.5-3.7 | P₀, Cp, τ roughness, LINE 15; negative Γ_G² message in `fp2k.inf` (Sep 2002); TCH coefficients eqs 3.16-3.17 |
| TOPAS (Tech. Ref. v9) | `ymin_on_ymax`, §7.1 and the `lam` entry, default 0.001; `peak_buffer_step` and `aberration_range_change_allowed`, §7.4, Table 7-3; per-derivative rebuilds, §7.7; `extra_X_left`/`_right`, default 0.5 | §2.1 (only named parameters refine); §5 (Newton-Raphson with Marquardt, BCCG §5.1); §5.15-5.17 cycles | roughness macros §22.1.8 (signatures only); Table 2-1 in §2.17 (no u-y rows; cell, occupancy, `CS_L` rows); η's printed 0.1116 in §7.2 |
| RIETAN-FP 3.12 | `PC`, per-peak height fraction (listing text "Cut-off = PC*(PEAK INTENSITY)"); recomputed each evaluation (ran) | `NAUTO`, §17.3.17; Le Bail intensities per cycle, §10.1-10.3; stall handling, §17.8.2 | roughness models, §3.2; FCJ by Gauss-Legendre 10-100 nodes, §3.10.3; negative width refused (ran); TCH, eqs 3.66-3.67 |
| BGMN 4.2.23 | no cut seen to 22° from a peak (ran) | automatic ladder and closing run, manual §A.4 and Doebelin & Kleeberg (2015) J. Appl. Cryst. 48, 1573, §2; instrument function held, manual §2.1 | no roughness model, §6.4; B1, k1, k2, §5.5-5.6; limits by RG-CD active set, §5.1; no esd at a limit, §A.4; Profex's default limits, its UI reference §3.4.7 |
| MAUD 3.07 | `_pd_proc_ls_peak_cutoff` default 30 HWHM, `R/diffr/PseudoVoigtPeak.java:267-268` | wizard stages, `R/comp/launchRefineWizard.java` and `FilePar.prepareWizard`; per-iteration holds, `COMP_STATUS` in `FilePar` | Caglioti bounds `InstrumentBroadeningPVCaglioti.initializeAsNew`; bounds not enforced, `FilePar.checkBound`, `LeastSquareFit` |
| EasyDiffraction 0.21.1 | `cutoff_fwhm` default 0 (none), `cryspy/A_functions_base/powder_diffraction_const_wavelength.py:207`; crysfml `WDT 30`, `easydiffraction/analysis/calculators/crysfml.py:125` | everything per evaluation, `easydiffraction/analysis/calculators/cryspy.py:201, 349`; hkl margin `cryspy/procedure_rhochi/rhochi_pd.py:141-148` | widths unbounded, `variable.py:397-400`; H_G² floor, `powder_diffraction_const_wavelength.py:123` |

Sequential refinement (WP-2003, read 2026-10-24):

| Program | Where |
|---|---|
| rietx | `src/rietx/sequential.py`: `SequentialRefinement.fit` and its docstring, `refine_sequential`, `_check_factor`, `_rejected`, `_series_steps`, `PATH_DEPENDENCE_SIGMA`, `ON_ERROR_POLICIES`, `_ladder`, `_reseed_needed`, `_prefer`, `_carry_into`, `_fit_one` |
| GSAS-II 5.8.4 | `SeqRefine`, `GSASIIstrMain.py:875-1196`: cell and texture refused `:910-918`; reverse `:923-924`; `Copy2Next`, the Le Bail copy and the earlier-run start `:980-1000`; vary-list change `:1038-1058`; stop on failure `:1098-1100`, singular matrix in a sequential fit `:376-391`; carried set `:1146-1162`; exception `:1169-1173`; results table written `:1178-1180`; `dropOOBvars` `:1123, 1198-1230`. Defaults `GSASIIobj.py:22, 27`; checkboxes and the clear button `GSASIIdataGUI.py:8158-8199`; Δχ² colouring `GSASIIseqGUI.py:1491-1499, 1818-1830`; cluster-analysis outliers `GSASIIseqGUI.py:2232-2249`; scripting `seqCopy`/`Reverse Seq` `GSASIIscriptable.py:3144-3152` |
| EasyDiffraction 0.21.1 | `easydiffraction/analysis/sequential.py`: worker and caught errors `:73-170`, collected values `:330-375`, start values `:591-598`, reverse `:923-924`, resume `:1094-1110`, chunk size `:1146-1147`, one start per chunk `:1229-1233`, propagation `:1251-1262`, `fit_sequential` `:1265-1294`; defaults `easydiffraction/analysis/categories/sequential_fit/default.py:54-95` |
| MAUD 3.07 | `src/it/unitn/ing/rista/util/batchProcess.java`: exception ends the batch `:111-187`, row loop `:261-514`, analysis read per row `:284-327`, refine and save `:562-575`, GoF loop `:591-613`; dialog defaults `src/it/unitn/ing/rista/awt/BatchFileDialog.java:181, 187, 243, 297, 398-453` |
| FullProf | search-engine excerpts only, the hosts being refused: FullProf News 2004 and 2005 (`fp2k cyc …`), the cyclic-mode workshop slides `FullProf_seq.pdf` (cdifx.univ-rennes.fr), and the manual's note that the `.sum` file is appended to in cyclic mode |
| TOPAS | search-engine excerpts only: Technical Reference v8 (`num_runs`, `out`, `#include`, `out_record`) and the Durham TOPAS wiki's `sequential_refinements` page; v9 not reached |
| BGMN with Profex | search-engine excerpts only: Profex User Manual 3.13 (batch refinement, abort behaviour) and Part 3 UI reference 4.0, and the tutorial title "Profex XRD: Sequential batch refinements"; 5.7.2 and the BGMN manual not reached |
| RIETAN-FP | manual not reached; RIETPY 0.2.0's PyPI description for the third-party wrapper |

Found beside the questions, for rietx-bench rather than rietx: its BGMN case names
`LAMBDA=cu_hoelzer97`, which has no `.ano` table, so that run has no anomalous dispersion
(12 % of |F| on Pb (101)), while its `engine.toml` says it uses `cu.ano`.

A stage that fixes a parameter (WP-2208, read 2026-11-10):

- `~/Code/rietx-bench/tools/gsas2/GSAS-II-5.8.4/GSASII/GSASIIscriptable.py:2013-2105` (`do_refinements`, `iter_refinements`: `once`, `skip`), `:2108-2230` (`set_refinement`: set then clear), `:4107`, `:4190` (histogram `set_refinements`, `clear_refinements`)
- `~/Code/rietx-bench/tools/gsas2/GSAS-II-5.8.4/docs/source/GSASIIscriptable.rst:589-690` (Refinement recipe, key table, LeBail example)
- `~/Code/rietx-bench/tools/gsas2/GSAS-II-5.8.4/GSASII/GSASIIconstrGUI.py:845-866` (Hold), `GSASIImapvars.py:52`, `:1002` (`StoreHold`)
- `~/Code/rietx-bench/tools/gsas2/GSAS-II-5.8.4/GSASII/GSASIIstrMain.py:850-872` (`phaseCheck`, Fix FXU, FixedSeqVars), `:961-974` (per-histogram vary list), `:1066-1073`, `:1198` (frozen variables), `:912` (lattice refused in sequential)
- TOPAS Technical Reference v9, https://topas-academic.com/technical_reference: § 2.2 (`prm !`), § 2.3 (attributes, `val_on_continue`), § `num_runs`, § `Constant`, § quick_refine, § 20.2 Pawley and Le Bail extraction
- FullProf 8.20 manual `~/Code/rietx-bench/tools/fullprof/files/Docs/FullProf_Manual.pdf`, lines of its `pdftotext` dump: 285-296 (CYC sequential), 326 (`.new`), 589-596 (codewords), 610-640 (staged order, profile matching first), 674-692 (`Jbt=2` recipe), 3494-3508 (`Aut`)
- RIETAN-FP manual `~/Code/rietx-bench/tools/rietan/RIETAN_VENUS/documents/RIETAN-FP_manual.pdf`: § 4.1.4 (text line 2830), § 11.3 (5116), § 17.3.17 (8625)
- MAUD: `~/Code/rietx-bench/tools/maud/Maud.app/Contents/Java/Maud.jar`, classes `it/unitn/ing/rista/comp/launchRefineWizard` and `it/unitn/ing/rista/diffr/FilePar`, string table only (no Java runtime on this Mac, no source)
