# WP-2017 group Q, measured

Raw: `group_q.jsonl`, 58 rows; head `f148d8abb`, Linux x86_64, Python 3.12.14, numpy 2.5.3, kernels 1.5.0.

## Q1, the synthetic (truth La 0.355, B 0.276 Å²)

| arm | La Biso | (La − truth)/esd | B Biso | (B − truth)/esd | a (Å) | bkg/truth 26-30° | worst absorption | Rwp | evals | noise twin, worst plain esd |
|---|---|---|---|---|---|---|---|---|---|---|
| cheb | 0.3789(0.0132) | 1.80 | 0.2804(0.0860) | 0.05 | 4.156800(6.9e-06) | 0.971 | 0.012 phases.0.atoms.0.biso | 0.06069 | 79 | 4.2e-07 phases.0.cell.a |
| ps1 | 0.3687(0.0146) | 0.94 | 0.2559(0.0952) | -0.21 | 4.156800(7.6e-06) | 0.892 | 0.012 phases.0.atoms.0.biso | 0.06717 | 82 | 3.8e-07 phases.0.cell.a |
| ps001 | 0.3730(0.0130) | 1.38 | 0.2756(0.0843) | -0.00 | 4.156800(6.7e-06) | 0.992 | 0.015 phases.0.atoms.1.biso | 0.05915 | 79 | 4.3e-07 phases.0.cell.a |
| snip3 | 0.4749(0.0137) | 8.76 | 0.2985(0.0850) | 0.26 | 4.156800(6.8e-06) | 0.987 | 0.011 phases.0.atoms.0.biso | 0.05972 | 84 | 4.4e-07 phases.0.cell.a |
| snip6 | 0.4369(0.0136) | 6.02 | 0.3261(0.0869) | 0.58 | 4.156800(6.9e-06) | 0.989 | 0.010 phases.0.atoms.0.biso | 0.06123 | 83 | 4.3e-07 phases.0.cell.a |
| truth | 0.3735(0.0128) | 1.44 | 0.2684(0.0834) | -0.09 | 4.156800(6.7e-06) | 0.997 | 0.011 phases.0.atoms.0.biso | 0.05929 | 79 | 4.3e-07 phases.0.cell.a |

Strongest peak 20000 counts; seed FWHM 0.0480°, half-window 7 points (#1569: 7); FWHM off the cheb fit 2.55 points; cheb background BackgroundChebyshev n=16.

Other count levels and Poisson draws (plain arms only):

| peak | seed | arm | peak counts | La Biso | (La − truth)/esd | B Biso | (B − truth)/esd | bkg/truth 26-30° | worst absorption |
|---|---|---|---|---|---|---|---|---|---|
| 2000 | 20261112 | cheb | 2000 | 0.4164(0.0822) | 0.75 | 0.0000(0.3980) | -0.69 | 0.972 | 0.022 |
| 2000 | 20261112 | snip3 | 2000 | 0.5562(0.0871) | 2.31 | 0.0000(0.3894) | -0.71 | 0.992 | 0.016 |
| 2000 | 20261112 | truth | 2000 | 0.3606(0.0784) | 0.07 | 0.0000(0.3852) | -0.72 | 0.997 | 0.020 |
| 20000 | 20261113 | cheb | 20000 | 0.3774(0.0132) | 1.71 | 0.1813(0.0842) | -1.13 | 0.973 | 0.012 |
| 20000 | 20261113 | snip3 | 20000 | 0.4644(0.0137) | 8.00 | 0.1862(0.0836) | -1.07 | 0.988 | 0.011 |
| 20000 | 20261113 | truth | 20000 | 0.3710(0.0128) | 1.26 | 0.1810(0.0818) | -1.16 | 0.998 | 0.011 |
| 20000 | 20261114 | cheb | 20000 | 0.3308(0.0130) | -1.86 | 0.1746(0.0837) | -1.21 | 0.972 | 0.012 |
| 20000 | 20261114 | snip3 | 20000 | 0.4169(0.0136) | 4.57 | 0.2503(0.0842) | -0.30 | 0.997 | 0.011 |
| 20000 | 20261114 | truth | 20000 | 0.3264(0.0126) | -2.28 | 0.1696(0.0809) | -1.31 | 0.997 | 0.011 |
| 200000 | 20261112 | cheb | 200000 | 0.3551(0.0034) | 0.02 | 0.2796(0.0240) | 0.15 | 0.970 | 0.007 |
| 200000 | 20261112 | snip3 | 200000 | 0.3886(0.0043) | 7.89 | 0.2826(0.0297) | 0.22 | 0.940 | 0.025 |
| 200000 | 20261112 | truth | 200000 | 0.3544(0.0033) | -0.18 | 0.2772(0.0234) | 0.05 | 0.997 | 0.006 |

## Q1, real patterns in Rietveld (no truth: direction only)

### srm1976a

FWHM 8.48 points, half-window 23. Rwp cheb 0.11421, snip3 0.10975; GOF 2.177 / 2.091; worst absorption 0.062 phases.0.atoms.0.biso / 0.141 phases.0.atoms.0.biso; codes added ['HIGH_CORRELATION'], dropped [].

| row | cheb | snip3 | Δ / larger esd |
|---|---|---|---|
| `phases.0.atoms.0.biso` | 0.992496(0.018) | 1.27116(0.02) | +13.97 |
| `phases.0.atoms.1.biso` | 0.962749(0.027) | 1.31351(0.029) | +12.14 |

Noise twin of cheb: worst 1.2e-07 plain esd (instrument.geometry.sample_transparency).

Noise twin of snip3: worst 7.2e-08 plain esd (instrument.geometry.sample_transparency).

### fap

FWHM 6.79 points, half-window 10. Rwp cheb 0.09283, snip3 0.09752; GOF 1.658 / 1.741; worst absorption 0.199 phases.0.atoms.2.biso / 0.272 phases.0.atoms.1.biso; codes added ['BACKGROUND_ABSORPTION'], dropped [].

| row | cheb | snip3 | Δ / larger esd |
|---|---|---|---|
| `phases.0.cell.a` | 9.37251(4.1e-05) | 9.37286(4.1e-05) | +8.30 |
| `phases.0.cell.b` | 9.37251(4.1e-05) | 9.37286(4.1e-05) | +8.30 |
| `phases.0.cell.c` | 6.88644(3.8e-05) | 6.88666(3.9e-05) | +5.68 |
| `phases.0.atoms.0.biso` | 0.3741(0.025) | 0.846667(0.033) | +14.39 |
| `phases.0.atoms.1.biso` | 0.249765(0.02) | 0.73262(0.027) | +18.09 |
| `phases.0.atoms.2.biso` | 0.245234(0.028) | 0.725886(0.036) | +13.38 |
| `phases.0.atoms.3.biso` | 1.16023(0.099) | 1.34393(0.11) | +1.61 |
| `phases.0.atoms.4.biso` | 0.346869(0.071) | 0.77555(0.085) | +5.03 |
| `phases.0.atoms.5.biso` | 0.600483(0.075) | 1.0663(0.091) | +5.11 |
| `phases.0.atoms.6.biso` | 0.513742(0.05) | 0.830944(0.059) | +5.33 |

Noise twin of cheb: worst 1.7e-06 plain esd (instrument.geometry.axial_sl).

Noise twin of snip3: worst 2.8e-07 plain esd (instrument.geometry.axial_sl).

## Q1, real patterns in Le Bail (no truth: direction only)

### pbso4

FWHM 6.20 points, half-window 13. Rwp cheb 0.09720, snip3 0.09008; GOF 1.968 / 1.824; worst absorption —  / — ; codes added [], dropped ['CONSTRAINT_ACTIVE', 'RESOLUTION_UNCONSTRAINED'].

| row | cheb | snip3 | Δ / larger esd |
|---|---|---|---|
| `phases.0.cell.a` | 8.47928(9.3e-05) | 8.47933(7.4e-05) | +0.54 |
| `phases.0.cell.b` | 5.39735(6.6e-05) | 5.39796(5.5e-05) | +9.25 |
| `phases.0.cell.c` | 6.95887(8.5e-05) | 6.95938(6.5e-05) | +5.96 |
| `instrument.profile.u` | 0.0317881(0.0014) | 0.0115906(0.00082) | -14.31 |
| `instrument.profile.v` | -0.0432949(0.0015) | -0.0152712(0.001) | +18.39 |
| `instrument.profile.w` | 0.0147417(0.00043) | 0.012401(0.00033) | -5.44 |
| `instrument.profile.x` | 0.00775244(0.0014) | 0.0189901(0.0011) | +8.19 |
| `instrument.profile.y` | 0.124523(0.0038) | 0.00443592(0.0033) | -31.38 |

Noise twin of cheb: worst 0.072 plain esd (instrument.profile.u).

Noise twin of snip3: worst 0.00033 plain esd (phases.0.cell.c).

### corundum726

FWHM 11.44 points, half-window 24. Rwp cheb 0.13631, snip3 0.13742; GOF 1.785 / 1.800; worst absorption —  / — ; codes added [], dropped [].

| row | cheb | snip3 | Δ / larger esd |
|---|---|---|---|
| `phases.0.cell.a` | 4.75823(8.3e-05) | 4.75824(8.6e-05) | +0.16 |
| `phases.0.cell.b` | 4.75823(8.3e-05) | 4.75824(8.6e-05) | +0.16 |
| `phases.0.cell.c` | 12.9893(0.00028) | 12.9893(0.00029) | +0.07 |
| `instrument.profile.u` | 0.00774588(0.007) | 0.00355503(0.0072) | -0.58 |
| `instrument.profile.v` | -0.00195744(0.0072) | 0.00449752(0.0075) | +0.86 |
| `instrument.profile.w` | 0.0166501(0.0018) | 0.0157359(0.0018) | -0.51 |
| `instrument.profile.x` | 0.0204076(0.0027) | 0.0209744(0.0027) | +0.21 |
| `instrument.profile.y` | 0.0565415(0.0066) | 0.0472569(0.0068) | -1.37 |

Noise twin of cheb: worst 2e-07 plain esd (instrument.profile.y).

Noise twin of snip3: worst 1.9e-07 plain esd (instrument.profile.u).

## Q2, `LEBAIL_CONVERGED_REL` (5 passes)

| family | arm | worst plain esd vs shipped | Rwp | evals | codes | stop / pair |
|---|---|---|---|---|---|---|
| lab6cbn | shipped | 0  | 0.136087 | 81 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation stopped at the first pass that did not lower Rwp. Pass 1 of 2 was kept (Rwp % per pass: 13.609, 13.649). |
| lab6cbn | 1e-3 | 0  | 0.136087 | 81 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation stopped at the first pass that did not lower Rwp. Pass 1 of 2 was kept (Rwp % per pass: 13.609, 13.649). |
| lab6cbn | 1e-5 | 0  | 0.136087 | 81 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation stopped at the first pass that did not lower Rwp. Pass 1 of 2 was kept (Rwp % per pass: 13.609, 13.649). |
| lab6cbn | noise | 1.4e-06 phases.0.cell.a | 0.136087 | 81 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation stopped at the first pass that did not lower Rwp. Pass 1 of 2 was kept (Rwp % per pass: 13.609, 13.649). |
| fap | shipped | 0  | 0.087096 | 35 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation reached the cap of 5 passes with Rwp still falling. Pass 5 of 5 was kept (Rwp % per pass: 10.108, 9.355, 9.019, 8.821, 8.710). |
| fap | 1e-3 | 0  | 0.087096 | 35 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation reached the cap of 5 passes with Rwp still falling. Pass 5 of 5 was kept (Rwp % per pass: 10.108, 9.355, 9.019, 8.821, 8.710). |
| fap | 1e-5 | 0  | 0.087096 | 35 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation reached the cap of 5 passes with Rwp still falling. Pass 5 of 5 was kept (Rwp % per pass: 10.108, 9.355, 9.019, 8.821, 8.710). |
| fap | noise | 6.9e-05 instrument.profile.u | 0.087096 | 35 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation reached the cap of 5 passes with Rwp still falling. Pass 5 of 5 was kept (Rwp % per pass: 10.108, 9.355, 9.019, 8.821, 8.710). |
| cpd1a | shipped | 0  | 0.225609 | 474 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation stopped at the first pass that did not lower Rwp. Pass 1 of 2 was kept (Rwp % per pass: 22.561, 33.879). |
| cpd1a | 1e-3 | 0  | 0.225609 | 474 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation stopped at the first pass that did not lower Rwp. Pass 1 of 2 was kept (Rwp % per pass: 22.561, 33.879). |
| cpd1a | 1e-5 | 0  | 0.225609 | 474 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation stopped at the first pass that did not lower Rwp. Pass 1 of 2 was kept (Rwp % per pass: 22.561, 33.879). |
| cpd1a | noise | 3.5e-07 phases.0.cell.a | 0.225609 | 474 | LEBAIL_ALTERNATION_STOPPED | The Le Bail alternation stopped at the first pass that did not lower Rwp. Pass 1 of 2 was kept (Rwp % per pass: 22.561, 33.878). |

## Q2, `StageSpec:lebail_tol`

| family | arm | worst plain esd vs shipped | Rwp | evals | codes | stop / pair |
|---|---|---|---|---|---|---|
| lab6cbn | shipped | 0  | 0.136087 | 81 |  |  |
| lab6cbn | 1e-6 | 0.00018 instrument.profile.y | 0.136087 | 81 |  |  |
| lab6cbn | 1e-9 | 0.00019 instrument.profile.y | 0.136087 | 81 |  |  |
| lab6cbn | noise | 1.4e-06 phases.0.cell.a | 0.136087 | 81 |  |  |
| fap | shipped | 0  | 0.101080 | 49 |  | 506 share 0.0010 |
| fap | 1e-6 | 0.0095 phases.0.cell.c | 0.101076 | 49 |  | 506 share 0.0484 |
| fap | 1e-9 | 0.00054 instrument.profile.u | 0.101080 | 49 |  | 506 share 0.0000 |
| fap | noise | 3.3e-05 phases.0.cell.c | 0.101080 | 49 |  | 506 share 0.0010 |
| cpd1a | shipped | 0  | 0.225609 | 474 |  |  |
| cpd1a | 1e-6 | 0.76 phases.0.cell.a | 0.225646 | 516 |  |  |
| cpd1a | 1e-9 | 0.82 phases.0.cell.a | 0.225594 | 517 |  |  |
| cpd1a | noise | 3.5e-07 phases.0.cell.a | 0.225609 | 474 |  |  |

## Q2, `LEBAIL_GAP_CYCLES` (Rietveld protocol, gap read at 5, 2, 20)

| family | twin | ratio at 5 | at 2 | at 20 | n_cycles echoed | Rwp |
|---|---|---|---|---|---|---|
| cpd1a | plain | 0.5490 | 0.5358 | 0.6255 | [5, 2, 20] | 0.16307 |
| cpd1a | noise | 0.5490 | 0.5358 | 0.6255 | [5, 2, 20] | 0.16307 |
| fap | plain | 0.9796 | 0.7635 | 1.0517 | [5, 2, 20] | 0.09283 |
| fap | noise | 0.9796 | 0.7635 | 1.0517 | [5, 2, 20] | 0.09283 |
| lab6cbn | plain | 0.9776 | 0.9774 | 0.9775 | [5, 2, 20] | 0.16862 |
| lab6cbn | noise | 0.9776 | 0.9774 | 0.9775 | [5, 2, 20] | 0.16862 |

