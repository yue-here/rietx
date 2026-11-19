# WP-2017 group G part B: B1.1 at 2 and 3 widths, NAC, a phase under 1 wt %

Rows: 93 fits, head `b0346eb01` (a local commit, never pushed; its two off-tree builders are now `group_g_b11_offtree.py`, rearranged without changing a value), Linux x86_64. Written by `group_g_b11.py summary`; the raw rows are not committed.

Columns: the minor phase's lowest significance the hold compared (σ, `refine._answer_significance`) and its value at the answer; the stages that held it; its weight % (esd) against the reference; the share of the off start's cell offset left against the database start's `s3` answer (0 recovered); Rwp; evaluations; the largest shift of any other row against the same start's `s3`, in plain esd (background apart); and whether `PHASE_UNCONSTRAINED` fired.

| start | n FWHM | arm | minor | σ min / at answer | held in | wt % (ref) | cell left | Rwp | evals | shift vs s3 | bkg shift | PHASE_UNCONSTRAINED |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cpd1a | 0 | s3 | corundum | 19.4 / 19.8 | none | 1.72(0.64) (1.15) | — | 0.1631 | 175 | — | — | no |
| cpd1a | 2 | s3 | corundum | 0.8 / 19.8 | cell | 1.72(0.64) (1.15) | -0.000 | 0.1631 | 184 | — | — | no |
| cpd1a | 2 | s1 | corundum | 0.8 / 19.8 | cell | 1.72(0.64) (1.15) | -0.000 | 0.1631 | 184 | 0 None | 0 | no |
| cpd1a | 2 | off | corundum | 0.8 / 19.8 | none | 1.72(0.64) (1.15) | 0.000 | 0.1631 | 178 | 0.0362 phases.2.lor_strain | 0.00116 | no |
| cpd1a | 2 | noise | corundum | 0.8 / 19.8 | cell | 1.72(0.64) (1.15) | -0.000 | 0.1631 | 184 | 1.78e-06 phases.2.cell.a | 9.49e-08 | no |
| cpd1a | 3 | s3 | corundum | 0.5 / 19.8 | cell | 1.72(0.64) (1.15) | -0.000 | 0.1631 | 184 | — | — | no |
| cpd1a | 3 | s1 | corundum | 0.5 / 19.8 | cell | 1.72(0.64) (1.15) | -0.000 | 0.1631 | 184 | 0 None | 0 | no |
| cpd1a | 3 | off | corundum | 0.5 / 19.8 | none | 1.72(0.64) (1.15) | -0.000 | 0.1631 | 176 | 0.0116 instrument.profile.v | 0.000638 | no |
| cpd1a | 3 | noise | corundum | 0.5 / 19.8 | cell | 1.72(0.64) (1.15) | -0.000 | 0.1631 | 184 | 5.13e-06 instrument.geometry.axial_sl | 3.11e-07 | no |
| cpd1b | 0 | s3 | zincite | 80.8 / 82.7 | none | 1.28(0.12) (1.36) | — | 0.1373 | 159 | — | — | no |
| cpd1b | 2 | s3 | zincite | 15.2 / 82.6 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 158 | — | — | no |
| cpd1b | 2 | s1 | zincite | 15.2 / 82.6 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 158 | 0 None | 0 | no |
| cpd1b | 2 | off | zincite | 15.2 / 82.6 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 158 | 0 None | 0 | no |
| cpd1b | 2 | noise | zincite | 15.2 / 82.7 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 158 | 3.96e-05 instrument.profile.v | 9.28e-06 | no |
| cpd1b | 3 | s3 | zincite | 6.9 / 82.6 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 181 | — | — | no |
| cpd1b | 3 | s1 | zincite | 6.9 / 82.6 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 181 | 0 None | 0 | no |
| cpd1b | 3 | off | zincite | 6.9 / 82.6 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 181 | 0 None | 0 | no |
| cpd1b | 3 | noise | zincite | 6.9 / 82.7 | none | 1.28(0.12) (1.36) | 0.000 | 0.1373 | 181 | 3.55e-06 instrument.profile.v | 9.57e-07 | no |
| cpd1c | 0 | s3 | fluorite | 46.1 / 47.2 | none | 1.78(0.22) (1.36) | — | 0.1052 | 151 | — | — | no |
| cpd1c | 2 | s3 | fluorite | 15.6 / 47.4 | none | 1.78(0.22) (1.36) | -0.000 | 0.1052 | 155 | — | — | no |
| cpd1c | 2 | s1 | fluorite | 15.6 / 47.4 | none | 1.78(0.22) (1.36) | -0.000 | 0.1052 | 155 | 0 None | 0 | no |
| cpd1c | 2 | off | fluorite | 15.6 / 47.4 | none | 1.78(0.22) (1.36) | -0.000 | 0.1052 | 155 | 0 None | 0 | no |
| cpd1c | 2 | noise | fluorite | 15.6 / 47.4 | none | 1.78(0.22) (1.36) | -0.000 | 0.1052 | 155 | 6.13e-07 instrument.geometry.axial_sl | 1.15e-08 | no |
| cpd1c | 3 | s3 | fluorite | 7.2 / 47.4 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 151 | — | — | no |
| cpd1c | 3 | s1 | fluorite | 7.2 / 47.4 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 151 | 0 None | 0 | no |
| cpd1c | 3 | off | fluorite | 7.2 / 47.4 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 151 | 0 None | 0 | no |
| cpd1c | 3 | noise | fluorite | 7.2 / 47.3 | none | 1.78(0.22) (1.36) | 0.000 | 0.1052 | 151 | 6.74e-07 instrument.geometry.sample_displacement | 2.54e-08 | no |
| cucr_cold | 0 | s3 | CuO | 22.0 / 28.7 | none | 0.50(0.26) (1.1) | — | 0.2241 | 98 | — | — | no |
| cucr_cold | 2 | s3 | CuO | 14.3 / 28.7 | none | 0.50(0.26) (1.1) | 0.000 | 0.2241 | 126 | — | — | no |
| cucr_cold | 2 | s1 | CuO | 14.3 / 28.7 | none | 0.50(0.26) (1.1) | 0.000 | 0.2241 | 126 | 0 None | 0 | no |
| cucr_cold | 2 | off | CuO | 14.3 / 28.7 | none | 0.50(0.26) (1.1) | 0.000 | 0.2241 | 126 | 0 None | 0 | no |
| cucr_cold | 2 | noise | CuO | 14.3 / 28.7 | none | 0.50(0.26) (1.1) | 0.000 | 0.2241 | 126 | 3.02e-08 instrument.profile.x | 2.43e-09 | no |
| cucr_cold | 3 | s3 | CuO | 11.2 / 28.7 | none | 0.50(0.26) (1.1) | 0.000 | 0.2241 | 188 | — | — | no |
| cucr_cold | 3 | s1 | CuO | 11.2 / 28.7 | none | 0.50(0.26) (1.1) | 0.000 | 0.2241 | 188 | 0 None | 0 | no |
| cucr_cold | 3 | off | CuO | 11.2 / 28.7 | none | 0.50(0.26) (1.1) | 0.000 | 0.2241 | 188 | 0 None | 0 | no |
| cucr_cold | 3 | noise | CuO | 11.2 / 28.7 | none | 0.50(0.26) (1.1) | 0.000 | 0.2241 | 188 | 2.88e-08 instrument.profile.x | 2.01e-09 | no |
| cucr_hot | 0 | s3 | CuO | 13.3 / 22.7 | none | 0.38(0.25) (1.1) | — | 0.2193 | 438 | — | — | no |
| cucr_hot | 2 | s3 | CuO | 18.2 / 24.2 | none | 0.42(0.26) (1.1) | -4.639 | 0.2190 | 425 | — | — | no |
| cucr_hot | 2 | s1 | CuO | 18.2 / 24.2 | none | 0.42(0.26) (1.1) | -4.639 | 0.2190 | 425 | 0 None | 0 | no |
| cucr_hot | 2 | off | CuO | 18.2 / 24.2 | none | 0.42(0.26) (1.1) | -4.639 | 0.2190 | 425 | 0 None | 0 | no |
| cucr_hot | 2 | noise | CuO | 18.2 / 24.2 | none | 0.42(0.26) (1.1) | -4.639 | 0.2190 | 421 | 0.00184 instrument.profile.v | 7.45e-05 | no |
| cucr_hot | 3 | s3 | CuO | 20.5 / 22.4 | none | 0.38(0.26) (1.1) | 2.080 | 0.2193 | 364 | — | — | no |
| cucr_hot | 3 | s1 | CuO | 20.5 / 22.4 | none | 0.38(0.26) (1.1) | 2.080 | 0.2193 | 364 | 0 None | 0 | no |
| cucr_hot | 3 | off | CuO | 20.5 / 22.4 | none | 0.38(0.26) (1.1) | 2.080 | 0.2193 | 364 | 0 None | 0 | no |
| cucr_hot | 3 | noise | CuO | 20.5 / 22.4 | none | 0.38(0.26) (1.1) | 2.080 | 0.2193 | 363 | 0.00155 phases.1.cell.a | 1.5e-05 | no |
| nac | 0 | s3 | CaF2 | 411.4 / 584.2 | none | 1.35(0.11) (—) | — | 0.0929 | 46 | — | — | no |
| nac | 0 | s1 | CaF2 | 411.4 / 584.2 | none | 1.35(0.11) (—) | — | 0.0929 | 46 | 0 None | 0 | no |
| nac | 0 | off | CaF2 | 411.4 / 584.2 | none | 1.35(0.11) (—) | — | 0.0929 | 46 | 0 None | 0 | no |
| nac | 0 | noise | CaF2 | 411.4 / 584.2 | none | 1.35(0.11) (—) | — | 0.0929 | 46 | 1.84e-07 phases.0.atoms.2.biso | 1.02e-08 | no |
| nac | 1 | s3 | CaF2 | 536.6 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 47 | — | — | no |
| nac | 1 | s1 | CaF2 | 536.6 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 47 | 0 None | 0 | no |
| nac | 1 | off | CaF2 | 536.6 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 47 | 0 None | 0 | no |
| nac | 1 | noise | CaF2 | 536.6 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 47 | 2.35e-07 phases.0.atoms.5.biso | 2.23e-08 | no |
| nac | 2 | s3 | CaF2 | 253.9 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 45 | — | — | no |
| nac | 2 | s1 | CaF2 | 253.9 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 45 | 0 None | 0 | no |
| nac | 2 | off | CaF2 | 253.9 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 45 | 0 None | 0 | no |
| nac | 2 | noise | CaF2 | 253.9 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 45 | 2.62e-07 phases.0.atoms.5.biso | 1.64e-08 | no |
| nac | 3 | s3 | CaF2 | 133.8 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 48 | — | — | no |
| nac | 3 | s1 | CaF2 | 133.8 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 48 | 0 None | 0 | no |
| nac | 3 | off | CaF2 | 133.8 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 48 | 0 None | 0 | no |
| nac | 3 | noise | CaF2 | 133.8 / 584.2 | none | 1.35(0.11) (—) | 0.000 | 0.0929 | 48 | 2.79e-07 phases.0.atoms.5.biso | 2.34e-08 | no |
| cr2wo6 | 0 | s3 | Cr2O3 | 92.2 / 92.2 | none | 0.78(0.10) (0.957) | — | 0.0843 | 64 | — | — | no |
| cr2wo6 | 0 | s1 | Cr2O3 | 92.2 / 92.2 | none | 0.78(0.10) (0.957) | — | 0.0843 | 64 | 0 None | 0 | no |
| cr2wo6 | 0 | off | Cr2O3 | 92.2 / 92.2 | none | 0.78(0.10) (0.957) | — | 0.0843 | 64 | 0 None | 0 | no |
| cr2wo6 | 0 | noise | Cr2O3 | 92.2 / 92.2 | none | 0.78(0.10) (0.957) | — | 0.0843 | 64 | 3.04e-07 instrument.profile.v | 1.95e-08 | no |
| cr2wo6 | 1 | s3 | Cr2O3 | 74.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 77 | — | — | no |
| cr2wo6 | 1 | s1 | Cr2O3 | 74.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 77 | 0 None | 0 | no |
| cr2wo6 | 1 | off | Cr2O3 | 74.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 77 | 0 None | 0 | no |
| cr2wo6 | 1 | noise | Cr2O3 | 74.6 / 92.2 | none | 0.78(0.10) (0.957) | -0.000 | 0.0843 | 77 | 6.42e-07 instrument.profile.u | 4.26e-08 | no |
| cr2wo6 | 2 | s3 | Cr2O3 | 42.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 91 | — | — | no |
| cr2wo6 | 2 | s1 | Cr2O3 | 42.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 91 | 0 None | 0 | no |
| cr2wo6 | 2 | off | Cr2O3 | 42.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 91 | 0 None | 0 | no |
| cr2wo6 | 2 | noise | Cr2O3 | 42.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 91 | 4.67e-08 instrument.profile.v | 8.97e-09 | no |
| cr2wo6 | 3 | s3 | Cr2O3 | 49.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 141 | — | — | no |
| cr2wo6 | 3 | s1 | Cr2O3 | 49.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 141 | 0 None | 0 | no |
| cr2wo6 | 3 | off | Cr2O3 | 49.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 141 | 0 None | 0 | no |
| cr2wo6 | 3 | noise | Cr2O3 | 49.6 / 92.2 | none | 0.78(0.10) (0.957) | 0.000 | 0.0843 | 141 | 5e-07 instrument.profile.v | 3.18e-08 | no |
| geco | 0 | s3 | Co10Ge3O16 | 164.0 / 165.2 | none | 1.39(0.19) (1.374) | — | 0.1095 | 153 | — | — | no |
| geco | 0 | s1 | Co10Ge3O16 | 164.0 / 165.2 | none | 1.39(0.19) (1.374) | — | 0.1095 | 153 | 0 None | 0 | no |
| geco | 0 | off | Co10Ge3O16 | 164.0 / 165.2 | none | 1.39(0.19) (1.374) | — | 0.1095 | 153 | 0 None | 0 | no |
| geco | 0 | noise | Co10Ge3O16 | 164.0 / 165.2 | none | 1.39(0.19) (1.374) | — | 0.1095 | 153 | 1.48e-06 phases.1.cell.a | 3.96e-08 | no |
| geco | 1 | s3 | Co10Ge3O16 | 97.9 / 165.2 | none | 1.39(0.19) (1.374) | -0.000 | 0.1095 | 182 | — | — | no |
| geco | 1 | s1 | Co10Ge3O16 | 97.9 / 165.2 | none | 1.39(0.19) (1.374) | -0.000 | 0.1095 | 182 | 0 None | 0 | no |
| geco | 1 | off | Co10Ge3O16 | 97.9 / 165.2 | none | 1.39(0.19) (1.374) | -0.000 | 0.1095 | 182 | 0 None | 0 | no |
| geco | 1 | noise | Co10Ge3O16 | 97.9 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 182 | 4.79e-07 instrument.profile.w | 4.03e-08 | no |
| geco | 2 | s3 | Co10Ge3O16 | 32.8 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 222 | — | — | no |
| geco | 2 | s1 | Co10Ge3O16 | 32.8 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 222 | 0 None | 0 | no |
| geco | 2 | off | Co10Ge3O16 | 32.8 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 222 | 0 None | 0 | no |
| geco | 2 | noise | Co10Ge3O16 | 32.8 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 222 | 1.03e-06 phases.1.cell.b | 1.59e-08 | no |
| geco | 3 | s3 | Co10Ge3O16 | 25.1 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 169 | — | — | no |
| geco | 3 | s1 | Co10Ge3O16 | 25.1 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 169 | 0 None | 0 | no |
| geco | 3 | off | Co10Ge3O16 | 25.1 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 169 | 0 None | 0 | no |
| geco | 3 | noise | Co10Ge3O16 | 25.1 / 165.2 | none | 1.39(0.19) (1.374) | 0.000 | 0.1095 | 169 | 1.38e-06 phases.1.cell.b | 3.18e-08 | no |

## Off starts

- `cpd1a`: line (1, 0, 4) at 35.1604°, FWHM 0.10003°, one-FWHM factor 1.002755
- `cpd1b`: line (1, 0, 1) at 36.2069°, FWHM 0.14039°, one-FWHM factor 1.003748
- `cpd1c`: line (2, 2, 0) at 47.0138°, FWHM 0.11176°, one-FWHM factor 1.002242
- `cucr_cold`: line (1, 1, 1) at 10.2290°, FWHM 0.01297°, one-FWHM factor 1.001264
- `cucr_hot`: line (1, 1, 1) at 10.2007°, FWHM 0.00642°, one-FWHM factor 1.000627
- `nac`: line (2, 2, 0) at 12.2981°, FWHM 0.00501°, one-FWHM factor 1.000406
- `cr2wo6`: line (2, -1, 6) at 14.2059°, FWHM 0.01088°, one-FWHM factor 1.000762
- `geco`: line (2, 2, 2) at 11.3041°, FWHM 0.02184°, one-FWHM factor 1.001926

## Codes per fit

- nac s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cr2wo6 s3: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- nac s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cpd1b s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1a s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cucr_cold s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cr2wo6 off: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6 s1: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6 noise: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cucr_hot s3: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- geco s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cpd1a_off2 s1: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1a_off3 s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1a_off2 off: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1a_off2 noise: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1a_off2 s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1a_off3 noise: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1a_off3 off: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1a_off3 s1: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1b_off2 s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1b_off2 off: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1b_off2 s1: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1b_off2 noise: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1b_off3 off: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1b_off3 s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1b_off3 s1: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1b_off3 noise: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c_off2 s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c_off2 s1: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c_off3 s3: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c_off2 noise: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c_off3 noise: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c_off3 s1: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c_off2 off: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cpd1c_off3 off: DISPERSION_NEGLECTED, FLAT_DIRECTION, FLOOR_HIT, HIGH_CORRELATION, SPACE_GROUP_SETTING_ASSUMED
- cucr_cold_off2 off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_cold_off2 noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_cold_off2 s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_cold_off2 s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_cold_off3 off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_cold_off3 s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_cold_off3 noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_cold_off3 s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_hot_off3 off: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- cucr_hot_off3 s3: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- cucr_hot_off2 noise: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- cucr_hot_off3 s1: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- cucr_hot_off3 noise: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- cucr_hot_off2 s3: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- cucr_hot_off2 off: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- nac_off1 s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off1 s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off1 off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off2 s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cucr_hot_off2 s1: CAPILLARY_OFFSET_UNAVAILABLE, CONSTRAINT_ACTIVE, FLAT_DIRECTION, HIGH_CORRELATION, PATTERN_UNDERSAMPLED, RESOLUTION_UNCONSTRAINED
- nac_off1 noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off2 s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off2 off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off3 s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off2 noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off3 s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off3 off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- nac_off3 noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- cr2wo6_off1 s1: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off1 s3: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off1 off: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off1 noise: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off2 off: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off2 s3: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off2 s1: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off2 noise: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off3 s3: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off3 s1: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off3 off: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- cr2wo6_off3 noise: CAPILLARY_OFFSET_UNAVAILABLE, RESOLUTION_UNCONSTRAINED
- geco_off1 off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off1 s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off1 s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off1 noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off2 off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off2 s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off2 s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off2 noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off3 s1: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off3 noise: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off3 s3: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
- geco_off3 off: CAPILLARY_OFFSET_UNAVAILABLE, FLOOR_HIT
