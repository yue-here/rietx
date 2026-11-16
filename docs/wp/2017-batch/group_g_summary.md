# WP-2017 group G, the absent-phase hold's threshold

Rows: 55 fits, head `51e56e95f`, Linux x86_64, numpy 2.5.3, rietx-kernels 1.5.0.  Written by `group_g.py summary`; the raw rows are not committed.

Columns: the minor phase's scale over its esd at the answer; the stages that held it; its weight fraction and the reference; the share of the off start's cell displacement left against the database start's `s3` answer (0 recovered, 1 never moved); Rwp; evaluations; the largest shift of any other row against the same start's `s3` arm, in plain esd (background rows apart); and whether `PHASE_UNCONSTRAINED` fired.

| start | arm | minor | scale/esd | held in | wt % (ref) | cell left | Rwp | evals | shift vs s3 | bkg shift | PHASE_UNCONSTRAINED |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cpd1a | s3 | corundum | 8.7 | none | 1.72(0.64) (1.15) | — | 0.1631 | 175 | — | — | no |
| cpd1a | s1 | corundum | 8.7 | none | 1.72(0.64) (1.15) | — | 0.1631 | 175 | 0 None | 0 | no |
| cpd1a | off | corundum | 8.7 | none | 1.72(0.64) (1.15) | — | 0.1631 | 175 | 0 None | 0 | no |
| cpd1a | window_off | corundum | 8.7 | none | 1.72(0.64) (1.15) | — | 0.1631 | 175 | 0 None | 0 | no |
| cpd1a | noise | corundum | 8.7 | none | 1.72(0.64) (1.15) | — | 0.1631 | 175 | 2.58e-06 instrument.geometry.sample_displacement | 1.39e-07 | no |
| cpd1b | s3 | zincite | 33.8 | none | 1.28(0.12) (1.36) | — | 0.1373 | 159 | — | — | no |
| cpd1b | s1 | zincite | 33.8 | none | 1.28(0.12) (1.36) | — | 0.1373 | 159 | 0 None | 0 | no |
| cpd1b | off | zincite | 33.8 | none | 1.28(0.12) (1.36) | — | 0.1373 | 159 | 0 None | 0 | no |
| cpd1b | window_off | zincite | 33.8 | none | 1.28(0.12) (1.36) | — | 0.1373 | 159 | 0 None | 0 | no |
| cpd1b | noise | zincite | 33.8 | none | 1.28(0.12) (1.36) | — | 0.1373 | 159 | 3.07e-05 instrument.profile.v | 7.09e-06 | no |
| cpd1c | s3 | fluorite | 22.4 | none | 1.78(0.22) (1.36) | — | 0.1052 | 151 | — | — | no |
| cpd1c | s1 | fluorite | 22.4 | none | 1.78(0.22) (1.36) | — | 0.1052 | 151 | 0 None | 0 | no |
| cpd1c | off | fluorite | 22.4 | none | 1.78(0.22) (1.36) | — | 0.1052 | 151 | 0 None | 0 | no |
| cpd1c | window_off | fluorite | 22.4 | none | 1.78(0.22) (1.36) | — | 0.1052 | 151 | 0 None | 0 | no |
| cpd1c | noise | fluorite | 22.5 | none | 1.78(0.22) (1.36) | — | 0.1052 | 151 | 1.26e-06 instrument.geometry.sample_displacement | 4.27e-08 | no |
| cpd1a_zircon | s3 | zircon | 1.3 | closing | 0.03(0.07) (0.00) | — | 0.1630 | 380 | — | — | yes |
| cpd1a_zircon | s1 | zircon | 0.7 | none | 0.02(0.11) (0.00) | — | 0.1630 | 374 | 0.206 phases.3.scale | 0.0397 | no |
| cpd1a_zircon | off | zircon | 0.7 | none | 0.02(0.11) (0.00) | — | 0.1630 | 374 | 0.206 phases.3.scale | 0.0397 | yes |
| cpd1a_zircon | window_off | zircon | 1.3 | closing | 0.03(0.07) (0.00) | — | 0.1630 | 380 | 0 None | 0 | yes |
| cpd1a_zircon | noise | zircon | 1.3 | closing | 0.03(0.07) (0.00) | — | 0.1631 | 385 | 0.0245 phases.2.lor_size | 0.000539 | yes |
| cucr_cold | s3 | CuO | 17.2 | none | 0.50(0.26) (1.10) | — | 0.2241 | 98 | — | — | no |
| cucr_cold | s1 | CuO | 17.2 | none | 0.50(0.26) (1.10) | — | 0.2241 | 98 | 0 None | 0 | no |
| cucr_cold | off | CuO | 17.2 | none | 0.50(0.26) (1.10) | — | 0.2241 | 98 | 0 None | 0 | no |
| cucr_cold | window_off | CuO | 17.2 | none | 0.50(0.26) (1.10) | — | 0.2241 | 98 | 0 None | 0 | no |
| cucr_cold | noise | CuO | 17.2 | none | 0.50(0.26) (1.10) | — | 0.2241 | 98 | 8.01e-08 instrument.profile.x | 5.21e-09 | no |
| cucr_hot | s3 | CuO | 14.8 | none | 0.38(0.25) (1.10) | — | 0.2193 | 438 | — | — | no |
| cucr_hot | s1 | CuO | 14.8 | none | 0.38(0.25) (1.10) | — | 0.2193 | 438 | 0 None | 0 | no |
| cucr_hot | off | CuO | 14.8 | none | 0.38(0.25) (1.10) | — | 0.2193 | 438 | 0 None | 0 | no |
| cucr_hot | window_off | CuO | 14.8 | none | 0.38(0.25) (1.10) | — | 0.2193 | 438 | 0 None | 0 | no |
| cucr_hot | noise | CuO | 14.8 | none | 0.38(0.25) (1.10) | — | 0.2193 | 438 | 0.000789 phases.1.cell.b | 6.8e-06 | no |
| cpd1a_off | s3 | corundum | 8.7 | none | 1.72(0.64) (1.15) | 0.000 | 0.1631 | 179 | — | — | no |
| cpd1a_off | s1 | corundum | 8.7 | none | 1.72(0.64) (1.15) | 0.000 | 0.1631 | 179 | 0 None | 0 | no |
| cpd1a_off | off | corundum | 8.7 | none | 1.72(0.64) (1.15) | 0.000 | 0.1631 | 179 | 0 None | 0 | no |
| cpd1a_off | window_off | corundum | 8.7 | none | 1.72(0.64) (1.15) | 0.000 | 0.1631 | 179 | 0 None | 0 | no |
| cpd1a_off | noise | corundum | 8.7 | none | 1.72(0.64) (1.15) | 0.000 | 0.1631 | 179 | 0.000136 phases.0.scale | 4.22e-05 | no |
| cpd1b_off | s3 | zincite | 33.8 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 176 | — | — | no |
| cpd1b_off | s1 | zincite | 33.8 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 176 | 0 None | 0 | no |
| cpd1b_off | off | zincite | 33.8 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 176 | 0 None | 0 | no |
| cpd1b_off | window_off | zincite | 33.8 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 176 | 0 None | 0 | no |
| cpd1b_off | noise | zincite | 33.8 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 176 | 6.13e-06 instrument.profile.v | 1.69e-06 | no |
| cpd1c_off | s3 | fluorite | 22.4 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 176 | — | — | no |
| cpd1c_off | s1 | fluorite | 22.4 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 176 | 0 None | 0 | no |
| cpd1c_off | off | fluorite | 22.4 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 176 | 0 None | 0 | no |
| cpd1c_off | window_off | fluorite | 22.4 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 176 | 0 None | 0 | no |
| cpd1c_off | noise | fluorite | 22.5 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 176 | 2.49e-06 phases.1.cell.a | 3.51e-08 | no |
| cucr_cold_off | s3 | CuO | 17.2 | none | 0.50(0.26) (1.10) | 0.000 | 0.2241 | 87 | — | — | no |
| cucr_cold_off | s1 | CuO | 17.2 | none | 0.50(0.26) (1.10) | 0.000 | 0.2241 | 87 | 0 None | 0 | no |
| cucr_cold_off | off | CuO | 17.2 | none | 0.50(0.26) (1.10) | 0.000 | 0.2241 | 87 | 0 None | 0 | no |
| cucr_cold_off | window_off | CuO | 17.2 | none | 0.50(0.26) (1.10) | 0.000 | 0.2241 | 87 | 0 None | 0 | no |
| cucr_cold_off | noise | CuO | 17.2 | none | 0.50(0.26) (1.10) | 0.000 | 0.2241 | 87 | 7.06e-08 instrument.profile.x | 4.79e-09 | no |
| cucr_hot_off | s3 | CuO | 14.8 | none | 0.38(0.25) (1.10) | 0.000 | 0.2193 | 429 | — | — | no |
| cucr_hot_off | s1 | CuO | 14.8 | none | 0.38(0.25) (1.10) | 0.000 | 0.2193 | 429 | 0 None | 0 | no |
| cucr_hot_off | off | CuO | 14.8 | none | 0.38(0.25) (1.10) | 0.000 | 0.2193 | 429 | 0 None | 0 | no |
| cucr_hot_off | window_off | CuO | 14.8 | none | 0.38(0.25) (1.10) | 0.000 | 0.2193 | 429 | 0 None | 0 | no |
| cucr_hot_off | noise | CuO | 14.8 | none | 0.38(0.25) (1.10) | 0.000 | 0.2193 | 425 | 0.00948 instrument.profile.w | 0.000358 | no |

## Off starts

- `cpd1a_off`: line (1, 0, 4) at 35.1604°, FWHM 0.10003°, cell × 1.002755
- `cpd1b_off`: line (1, 0, 1) at 36.2069°, FWHM 0.14039°, cell × 1.003748
- `cpd1c_off`: line (2, 2, 0) at 47.0138°, FWHM 0.11176°, cell × 1.002242
- `cucr_cold_off`: line (1, 1, 1) at 10.2290°, FWHM 0.01297°, cell × 1.001264
- `cucr_hot_off`: line (1, 1, 1) at 10.2007°, FWHM 0.00642°, cell × 1.000627

## Every fit's weight fractions against the reference

- cpd1a s3: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1a s1: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1a off: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1a window_off: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1a noise: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1b s3: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1b s1: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1b off: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1b window_off: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1b noise: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1c s3: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1c s1: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1c off: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1c window_off: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1c noise: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1a_zircon s3: corundum 1.73(0.66) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.89(0.67) vs 94.81; zircon 0.03(0.07) vs 0.00
- cpd1a_zircon s1: corundum 1.73(0.66) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.90(0.67) vs 94.81; zircon 0.02(0.11) vs 0.00
- cpd1a_zircon off: corundum 1.73(0.66) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.90(0.67) vs 94.81; zircon 0.02(0.11) vs 0.00
- cpd1a_zircon window_off: corundum 1.73(0.66) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.89(0.67) vs 94.81; zircon 0.03(0.07) vs 0.00
- cpd1a_zircon noise: corundum 1.73(0.66) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.89(0.67) vs 94.81; zircon 0.03(0.07) vs 0.00
- cucr_cold s3: CuO 0.50(0.26) vs 1.10
- cucr_cold s1: CuO 0.50(0.26) vs 1.10
- cucr_cold off: CuO 0.50(0.26) vs 1.10
- cucr_cold window_off: CuO 0.50(0.26) vs 1.10
- cucr_cold noise: CuO 0.50(0.26) vs 1.10
- cucr_hot s3: CuO 0.38(0.25) vs 1.10
- cucr_hot s1: CuO 0.38(0.25) vs 1.10
- cucr_hot off: CuO 0.38(0.25) vs 1.10
- cucr_hot window_off: CuO 0.38(0.25) vs 1.10
- cucr_hot noise: CuO 0.38(0.25) vs 1.10
- cpd1a_off s3: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1a_off s1: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1a_off off: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1a_off window_off: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1a_off noise: corundum 1.72(0.64) vs 1.15; zincite 3.35(0.21) vs 4.04; fluorite 94.93(0.65) vs 94.81
- cpd1b_off s3: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1b_off s1: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1b_off off: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1b_off window_off: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1b_off noise: corundum 94.29(0.23) vs 94.31; zincite 1.28(0.12) vs 1.36; fluorite 4.43(0.19) vs 4.33
- cpd1c_off s3: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1c_off s1: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1c_off off: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1c_off window_off: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cpd1c_off noise: corundum 6.30(0.62) vs 5.04; zincite 91.92(0.66) vs 93.59; fluorite 1.78(0.22) vs 1.36
- cucr_cold_off s3: CuO 0.50(0.26) vs 1.10
- cucr_cold_off s1: CuO 0.50(0.26) vs 1.10
- cucr_cold_off off: CuO 0.50(0.26) vs 1.10
- cucr_cold_off window_off: CuO 0.50(0.26) vs 1.10
- cucr_cold_off noise: CuO 0.50(0.26) vs 1.10
- cucr_hot_off s3: CuO 0.38(0.25) vs 1.10
- cucr_hot_off s1: CuO 0.38(0.25) vs 1.10
- cucr_hot_off off: CuO 0.38(0.25) vs 1.10
- cucr_hot_off window_off: CuO 0.38(0.25) vs 1.10
- cucr_hot_off noise: CuO 0.38(0.25) vs 1.10

## Group H's count on these fits

438 solves over 55 fits: a phase windowed in 2, a free cell column bounded in 0, an edge reached in 0.

## The ramp, 17 frames chained

| start | arm | frames CuO held at the answer | CuO wt %, median (range) | CuO cell left, last frame | frames rejected | codes |
|---|---|---|---|---|---|---|
| off | off | 0 of 17 | 0.58 (0.38-0.64) | 0.000 | 0 |  |
| db | s3 | 0 of 17 | 0.58 (0.38-0.64) | — | 0 |  |
| off | s1 | 0 of 17 | 0.58 (0.38-0.64) | 0.000 | 0 |  |
| off | window_off | 0 of 17 | 0.58 (0.38-0.64) | 0.000 | 0 |  |
| off | s3 | 0 of 17 | 0.58 (0.38-0.64) | 0.000 | 0 |  |

Group H on the ramp: 190 solves, a free cell column bounded in 0.
