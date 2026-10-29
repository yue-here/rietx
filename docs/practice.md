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
| rietx | plans of cumulative stages; the last frees everything the plan freed | reflection list, windows, FCJ nodes: per stage |
| RIETAN-FP | `NAUTO = 2`: early cycles refine subsets (background and scale; widths; asymmetry; widths and asymmetry; cell; atoms), then everything together to convergence. `NAUTO = 1`: the user lists the early cycles | windows follow every evaluation; Le Bail intensities per cycle |
| BGMN | automatic: isotropic models first, anisotropic ones added, then a closing run with everything free restarted from the answer; a weak anisotropic term is switched off | the ray-traced instrument function for the whole fit |
| MAUD | the refinement wizard: cumulative stages (scales and background; cell, zero, B; size and strain; atoms), no final all-free cycle | windows follow every evaluation; texture, strain, Le Bail intensities and structure factors per iteration |
| FullProf | none; the user runs successive files in the manual's advised order | windows and point assignment for the whole run (`Ias = 0`) |
| GSAS-II | none; scripting takes a user list | the reflection list per `Refine` call; windows every evaluation |
| TOPAS | none; `_rem` and `quick_refine` drop parameters for an iteration | the peak buffer up to its tolerances |
| EasyDiffraction | none | nothing: reflection list and windows rebuilt every evaluation |

None of the seven tests whether its answer depends on the path or the start, and none of
their manuals discusses it.

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
| rietx | a rung at a time, collapsed warm refit, then the full plan from the warm state, then the full plan cold, when the fit diverges or its Rwp exceeds `RESEED_FACTOR` (1.25) × the median Rwp of the accepted patterns; the best attempt is kept, convergence before Rwp and a truncated rung below any completed one (`reseed=True`, checked) | diverged after every rung: quarantined, `SEQUENTIAL_UNRECOVERED`. Every rung raised: `on_error="carry"` records it (`SERIES_PATTERN_FAILED`) and the chain goes on; `"skip"` starts the successor cold, `"raise"` stops. Converged above the fence: kept, `SEQUENTIAL_RWP_OUTLIER` | no: the successor starts from the last accepted pattern, and a quarantined pattern joins no median (checked) |
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
| rietx | `direction="backward"`; `"forward"` by default | `direction="both"`, off by default, runs the chain each way and flags a parameter whose two trajectories differ by more than `PATH_DEPENDENCE_SIGMA` (3) combined esds, `SEQUENTIAL_PATH_DEPENDENT` | none since WP-2003: `SeriesResult.steps` lists every step in esds of the later fit, largest first, with no threshold and no diagnostic (until then `SEQUENTIAL_DISCONTINUITY`, at 5× the median absolute step and 3 combined esds from 5 points); `verify_steps=k` refits the k largest pairs cold, 0 by default (checked) |
| GSAS-II | "Reverse order?" (`Reverse Seq`), off by default | none | none. The results table colours a last-cycle Δχ² above 1 % yellow and above 10 % red, only with `ShowCell` on (off by default); a user-run cluster analysis offers outlier detection on the data (checked) |
| EasyDiffraction | `reverse`, off by default ("useful when starting values are better matched to the last file") | none | none (checked) |
| MAUD | the row order of the instruction file | none | none (checked) |
| FullProf | not established | not established | none described; the slides state the assumption that the refined parameters evolve continuously (inferred) |
| TOPAS | the user's script | none built in | none built in (inferred) |
| BGMN with Profex | not established | none described | none described (inferred) |
| RIETAN-FP | not established | not established | not established |

Anything else a series mode decides by itself:

- rietx: stage seeds are zeroed on a warm start, so a neighbour's answer sitting on a floor is
  not lifted; the collapsed first rung gets an evaluation budget of `first_rung_factor` (3.0) ×
  the dearest converged first rung, once `FIRST_RUNG_SAMPLES` (3) have converged; a magnetic
  moment the pattern does not support is floored before it seeds the next
  (`SEQUENTIAL_MOMENT_HOLD`); the wavelength-calibration diagnostic measures from the series
  root's declared λ, not the carried one; a cancelled
  series returns what completed (`SEQUENTIAL_CANCELLED`); a finding on most patterns is
  summarised once (`SEQUENTIAL_PERSISTENT_FINDING`) (checked).
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
restart ladder with its Rwp fence (`RESEED_FACTOR`, the median, `_prefer`) and the first-rung
budget; the quarantine's exclusion from the median; `direction="both"` and
`SEQUENTIAL_PATH_DEPENDENT`; the discontinuity scan and its cold verification; and the moment
floor and onset (`SEQUENTIAL_MOMENT_HOLD`, `SEQUENTIAL_MOMENT_ONSET`), the persistent-finding
summary and the width-growth screen (`SEQUENTIAL_WIDTH_GROWTH`).

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

## Searching for a propagation vector

Surveyed 2026-10-29 in the issue triage, for M-8's k-search (#795, WP-1418).

- GSAS-II 5.8.4, checked: `GSASII/k_vector_search.py`, class `kVector` (Zhang & Paddison,
  2024). It builds a k-path with seekpath (Hinuma et al. 2017, *Comput. Mater. Sci.* 128,
  140). `option` sets the scope: 0, the default, searches the path's high-symmetry points
  only; 1 adds its edges; 2 adds a grid over the whole Brillouin zone, step `kstep`
  0.01 per axis (docstring, `:119-227`). Each k is scored by a one-to-one assignment of
  predicted to observed satellites (`scipy.optimize.linear_sum_assignment`,
  `updateCandidateList`, `:412-509`). The largest Δd/d is compared with the caller's
  `threshold`, which has no default. A k under it is returned directly (`kOptFinder`,
  `:511-620`). Nothing estimates how often random peaks would pass the same threshold.
- FullProf, recalled and not checked this session: the `K_Search` program scans a grid of k
  over the zone and ranks by how many satellites it indexes.

So both programs score by agreement alone. A chance baseline, as #795 proposes, is not
practice in either.

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
| rietx | `src/rietx/sequential.py`: `SequentialRefinement.fit` and its docstring, `refine_sequential`, `RESEED_FACTOR`, `FIRST_RUNG_FACTOR`, `_series_steps`, `PATH_DEPENDENCE_SIGMA`, `ON_ERROR_POLICIES`, `_ladder`, `_reseed_needed`, `_prefer`, `_carry_into`, `_fit_one` |
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
