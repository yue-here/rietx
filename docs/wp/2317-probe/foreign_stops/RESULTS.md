# Do GSAS-II's and FullProf's default stops leave a fit short in their own programs? (WP-2317 probe)

**Programs:** GSAS-II 5.8.4 (pixi env, `-I`, installed package), FullProf 8.20 (x86_64 under
Rosetta, `fp2k`). rietx 1.13.0.dev0 from the `ghostshift-land-2312-404666` worktree's venv was used
only to export the start. Darwin 25.6.0 arm64. Total machine time was under 15 minutes.
Every program is compared **with itself**: its default stop against a tight stop from the same
start, on the same model and free set. The esd is the tight run's own esd. GSAS-II's is
√(χ²_red·diag(cov)). FullProf's is its `+/-` column.

## Start and protocol

- **rietx start** (Measured): `export_cpd.py` ran `tests/test_acceptance_sequential.py`'s `chained`
  fixture (carry=`CARRY`, `seed_scales` hook, `qpa_plan()`, shipped stops) over cpd-1a…1f. rietx's
  1f answer has χ²_red 1.9658 (S = 14179 over 7251 points, 38 free).
- **In-program warm start.** Each program first fits cpd-1e from rietx's 1e answer, converted
  (GSAS-II: `g2/p5.gpx`, S = 12767.5; FullProf: `fp*/p5.pcr`, S ≈ 12665). Then cpd-1f's counts
  replace 1e's on the same 2θ grid, and every other value is carried. This mirrors rietx's warm
  start. Scales are set two ways:
  - `carry`: the program's own 1e scales. This is GSAS-II's `Copy2Next` practice.
  - `seed`: each phase's scale × rietx's start/1e-answer ratio (0.594, 0.132, 0.371). This is the
    start rietx's warm pattern 6 actually had (`seed_scales`' equal split).
  - `seedlin` (GSAS-II only): `seed`, then scales and background alone refined first.
- **GSAS-II free set** (33): 3 phase fractions (histogram scale held), 6 `chebyschev-1`, Zero, Shift,
  5 cell terms, V, W, SH/L, I(L2)/I(L1), isotropic Size and Mustrain per phase (LGmix 1, Lorentzian),
  and 6 Uiso. U, X and Y are held. This mirrors rietx's width twin hold: rietx's last stage holds
  U, X and Y. Dispersion is patched off, as rietx declines it on this suite.
- **FullProf free set** (32 with S_L free, 31 with it held): Zero, SyCos, 6 polynomial
  background terms, U, V and W shared across phases, S_L shared (D_L = 0, since rietx's
  `axial_hl` is 0), and per phase a scale, X, Y and cell. There are also 6 Biso. The Kα2 ratio is
  held at rietx's 0.44219, because FullProf has no codeword for it. GauSiz is held. Npr = 7 (TCHZ),
  relaxation factors 1.0, Cthm 0.7998.
  - (Measured) Two other free sets failed. Shared W with per-phase GauSiz and U is an exact
    degeneracy, since IG/cos²θ = IG + IG·tan²θ. Per-phase U from rietx's u, v, w makes the
    Gaussian FWHM² negative above about 120° for corundum. FullProf then froze U, V and W, with
    esds near 1e-9.
- **Stops.** GSAS-II default: `max cyc` 3 and `min dM/M` 1e-3 (`GSASIIobj.DefaultControls`).
  Also run: `dm`, which is 1e-3 with 1000 cycles (the test alone); `presses`, which repeats default
  Refine calls until GSAS-II says converged; and `tight`, which is 1e-9 with 1000 cycles, pressed
  three times. Each tight run ends at "ouch #4 stuck": no step lowers χ² by more than 1e-9
  relative, even at λ = 100. FullProf default is Eps 0.2, which the manual calls "a reasonable
  value". Also run: Eps 0.1, NCY 15, and tight (Eps 0.001, NCY 600).

## 1. cpd-1f, GSAS-II (`g2_cpd1f_table.txt`)

All rows are Measured. Departures are |Δ|/esd, worst per family.

| start | stop | cycles | S at stop | tight S | says converged | worst |Δ|/esd: cell / zero,disp / profile / Uiso / scale / bkg |
|---|---|---|---|---|---|---|
| carry | default (1 press) | 3 | 20763 | 13965.0 | no | 34 / 25 / 23 / 2.7 / 2.9 / 3.6 |
| carry | presses to "converged" | 13 (5 presses) | 14017.7 | 13965.0 | yes | **16** (zincite c\*) / **14** (Zero) / 0.77 / 0.12 / 0.07 / 0.06 |
| carry | dM/M 1e-3, uncapped | 13 | 14018.6 | 13965.0 | yes | 16 / 14 / 0.77 / 0.12 / 0.08 / 0.06 |
| carry | dM/M 1e-9 first press | 28 | 13965.4 | 13965.0 | yes | 1.3 / 0.96 / 0.31 / 0.02 / 0.01 / 0.01 |
| seedlin | default | 3 | 13967.3 | 13966.7 | no | 0.46 / 0.25 / 0.30 / 0.02 / 0.01 / 0.01 |
| seedlin | to "converged" | 4 | 13967.8 | 13966.7 | yes | 0.26 / 0.32 / 0.28 / 0.01 / 0.01 / 0.004 |
| seed | any | 3-7 | 147150 | 147150 | no | stuck at χ²_red 20.4 |

- (Measured) With GSAS-II's own warm start, its 1e-3 test stops after 13 cycles and reports
  convergence. Zero sits 14 esd from the tight answer (−0.1005° against −0.0387°, esd 0.0043°).
  Shift sits 12 esd off (−167 against −77 µm), and zincite's c\* term 16 esd off. S is 53.6 higher,
  which is 0.38 %. Pressing Refine until GSAS-II says converged lands in the same place. A single
  default Refine (3 cycles) is far short (S +49 %), but it says it has not converged.
- (Measured) GSAS-II's own floor: the tight answers from `carry` and `seedlin` differ by up to
  1.5 esd along the same zero/shift/cell valley (S 13965.0 against 13966.7).
- (Measured) The test also passes on a step that **raised** χ². DelChi2 was −1.1e-5 at the tight
  stop and −3.6e-5 at the `seedlin` stop. This is because `HessianLSQ` accepts any step with
  χ²_new ≤ χ²_old·(1 + ftol) and then tests (χ²_old − χ²_new)/χ²_old < ftol.
- (Measured) From rietx's own 1f start (`seed`), GSAS-II never converges. With every parameter
  free, its first steps raise χ² 4- to 40-fold. λ climbs to 100, and it stops "stuck" at χ²_red
  20, saying not converged. This is a start problem, not a stop problem.
- (Inference) Here the crawl is the zero/displacement/cell valley, not the axial term. SH/L stays
  within 0.8 esd.

## 2. cpd-1f, FullProf (`fp_cpd1f_table.txt`)

| free set | stop | cycles | S at stop | reference S | says converged | worst |Δ|/esd (others) |
|---|---|---|---|---|---|---|
| S_L held | Eps 0.2 (default) | 12 | 14382.44 | 14381.48 (Eps 0.001, 26 cyc, converged) | yes | 0.079 zincite c (rest ≤ 0.07) |
| S_L held | Eps 0.1 | 13 | 14381.91 | 14381.48 | yes | 0.046 |
| S_L free | Eps 0.2 (default) | 11 | **14383.53** | 14406.23 (600 cyc, no convergence) | yes | S_L 37; cell 0.21, zero/disp 0.24, Biso 0.24, scale 0.28 |
| S_L free | Eps 0.1 | 65 | 14395.59 | 14406.23 | yes | S_L 18 |
| any | rietx's `seed` start | 7-9 | NaN | n/a | **yes** | diverged |

- (Measured) Where FullProf's minimum is well defined (S_L held), the Eps 0.2 stop is 0.08 esd
  from Eps 0.001, and S is 0.96 higher. Undamped Gauss-Newton lands in 12-13 cycles, and a tighter
  Eps then needs only 13 more.
- (Measured) With S_L free, FullProf's long run goes **uphill**. χ²_red is 1.995 at cycle 12 and
  1.999 at cycle 600, while S_L drifts from 0.0130 to 0.0116. Each cycle's shift is 0.1-0.3 of an
  esd of about 4e-5. So the default stop sits at a lower χ² than any later state. Measured against
  the 600-cycle end, S_L is "37 esd off", but that end is the worse fit.
- (Inference) FullProf's S_L esd and value look wrong. Its esd (4e-5) is 23× GSAS-II's SH/L esd
  (9.3e-4) and 70× rietx's (2.7e-3). Its value (0.012) is less than half of GSAS-II's (0.029) and
  rietx's (0.032). D_L = 0 may be the cause; not tested. A D_L = 0.01 trial diverged in Zero/SyCos
  (±0.36°).
- (Measured, misbehaviour) From rietx's `seed` start, FullProf diverges: χ²_red goes 79 → 364 →
  NaN. It then prints "Convergence reached at this CYCLE" with NaN parameters. This happened with
  either free set.
- (Measured, observation) FullProf runs single precision ("Number of bytes for floating point
  variables: 4"). Its rewritten PCR keeps 3-6 decimals, so restarting from it truncates values.
  Each 1f variant above ran from one PCR in one run.

## 3. CuCr₂O₄ ramp, GSAS-II sequential (`g2seq_table.txt`)

17 patterns OH_00…OH_53 (11-BM, λ = 0.41326 Å), CuCr₂O₄ + CuO, `OH_00.prm`, `chebyschev-1` 8
terms. OH_00 was fitted first with a staged plan to tight. Then came a sequential run with
`Copy2Next` on, freeing per pattern: histogram Scale, CuO fraction, background, Zero, U, V, W, X,
Y and **Dij** for both phases. GSAS-II refuses a sequential run with the cell flag on: "lattice
parameters should not be refined in a sequential refinement … use the Dij parameters". So Dij is
its sequential cell. Each chain carries its own answers forward, as rietx's series measurement
does. Tight reference: dM/M 1e-9, 1000 cycles, 247 cycles in all, every pattern ending "stuck".

| stop | cycles (17 patterns) | say converged | max (median) ΔS | CuCr₂O₄ Dij | CuO Dij | zero | profile | scale | bkg |
|---|---|---|---|---|---|---|---|---|---|
| default, 1 press | 48 | 3/17 | 39 908 (1 084) | 4.9 | 14 | 2.5 | 79 (U) | 6.8 | 3.8 |
| default, pressed twice | 35 more | 15/17 | 1 455 (20) | 0.75 | 14 | 0.77 | 55 (U) | 1.7 | 0.40 |
| dM/M 1e-3, uncapped | 89 | **17/17** | 757 (101) | 0.50 | **10.5** (OH_30 D22) | 0.84 | **52** (OH_49 U) | 1.3 | 0.38 |

The tight S has median 33 412 over 12 799 points, so a ΔS of 757 is 2.3 %. All rows are Measured.

- (Measured) The test alone reports convergence on all 17 patterns. CuO's Dij is up to 10.5 esd
  off. U is up to 52 esd off (−55.6 against −32.5 centideg², esd 0.44), with V and W moving with
  it. The tight chain also walks U from −3.5 to −32 and W below zero along the ramp. Pressing
  Refine on a sequential run does continue from the stored results: a second press made 15/17
  report convergence.
- (Inference) The crawl is the U-V-W valley of a near-zero Gaussian width on synchrotron data.
  GSAS-II lets W go negative, while rietx floors the Gaussian at Γ_G² ≥ 1e-8, so rietx's valley
  is cut short. This may be why rietx's in-solver GSAS-like stop left only 0.4 esd on profile
  there.
- FullProf's ramp: **skipped**. Sequential mode needs a per-file PCR chain, and the 11-BM `.fxye`
  would need conversion. Section 2 also showed FullProf freezes U, V and W once the Gaussian FWHM²
  turns negative, which a near-zero synchrotron Gaussian invites. Making that run trustworthy would
  cost more than the budget allowed.

## Answer (Inference, from the measurements above)

- **GSAS-II:** yes, at home too, and by about as much as rietx's in-solver version.
  - The 1e-3 test reports convergence while the answer is still 14-16 esd short on cpd-1f. On cpd-1f
    that is zero, shift and zincite c, with χ² 0.4 % high. On the ramp it is 10.5 esd on CuO's
    cell and 52 esd on U, with χ² up to 2.3 % high.
  - rietx's in-solver result was 18 esd with χ²_red 9 % high on cpd-1f, and 1.8 esd on the ramp.
  - The parameter that crawls differs: zero/shift/cell and U-V-W here, against `axial_sl` in rietx.
  - The shipped 3-cycle cap is further short still, but there GSAS-II says it has not converged.
- **FullProf:** no, where its minimum is well posed.
  - Undamped Gauss-Newton lands within 0.08 esd at Eps 0.2.
  - With S_L free its long run drifts uphill, so "tighter" is worse, and its S_L esd looks too
    small to trust.
- **rietx's chained start breaks both programs.** GSAS-II sticks at χ²_red 20, honestly
  unconverged. FullProf reaches NaN and reports convergence.

## Files

Scripts: `export_cpd.py` (rietx), `g2cpd.py` + `g2_all.sh` + `analyse_g2.py`, `fpcpd.py` +
`analyse_fp.py` (+ `fptest*.py`, free-set trials), `g2seq.py` + `analyse_g2seq.py`. Raw: `cpd/`,
`g2/`, `fp/` (S_L free; `fp/withIG`, `fp/noIG_ownU` hold the failed free sets), `fp_slheld/`,
`g2seq/`.
