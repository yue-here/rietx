# WP-2017 group O — measured

Written by `group_o.py summary` from the raw rows; domains, rows and arms as fixed in the WP before running.

Run: `{"head": "0d4578e062f1be3042fef2b67896381971621a96", "kernels": "1.5.0", "numpy": "2.5.3", "platform": "Linux x86_64", "python": "3.12.14"}`

## O1: the profile interval's five search constants

Screen (seeds 0-19 but 14, no intervals): the test passes on seeds 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19; the first two join seed 14.

| Family | Row | Value | Unit | Shipped interval | Stops | Refits | Crossings (lo/hi) | Fit is minimum | Reference plain vs noise | Shipped vs reference | Noise twin, shipped | Domain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pnma0 | `phases.0.atoms.1.moment.dof0` | 0.704081 | esd 0.292 | 0.698133 to 0.714886 | threshold/threshold | 26 | 1/1 | True | 1.04e-10 | 3.8e-06 | 1.04e-10 | inside |
| pnma0 | `phases.0.atoms.0.moment.dof1` | 1.56762 | half-width 0.00897 | 1.56032 to 1.58128 | threshold/threshold | 31 | 1/1 | True | 2.12e-10 | 3.93e-05 | 8.31e-10 | inside |
| pnma0 | `phases.0.atoms.1.moment.dof1` | 1.55498 | half-width 0.0442 | 1.51872 to 1.62287 | threshold/threshold | 31 | 1/1 | True | 8.78e-09 | 2.67e-05 | 3.88e-09 | inside |
| pnma1 | `phases.0.atoms.1.moment.dof0` | 0.701981 | esd 0.00102 | 0.697354 to 0.715591 | threshold/threshold | 35 | 1/1 | False | 2.89e-08 | 0.00021 | 2.9e-08 | inside |
| pnma1 | `phases.0.atoms.0.moment.dof2` | 0.0161413 | half-width 0.0392 | -0.0421694 to 0.0421802 | threshold/threshold | 31 | 1/1 | False | 1.01e-09 | 0.000251 | 1.64e-09 | inside |
| pnma1 | `phases.0.atoms.1.moment.dof2` | -0.0808415 | half-width 0.125 | -0.207974 to 0.208022 | threshold/threshold | 30 | 1/1 | False | 1.67e-09 | 0.000207 | 4.83e-09 | inside |
| pnma14 | `phases.0.atoms.1.moment.dof0` | 0.702909 | esd 0.000985 | 0.699713 to 0.710957 | threshold/threshold | 34 | 1/1 | False | 2.81e-08 | 1.97e-05 | 2.11e-08 | inside |
| pnma14 | `phases.0.atoms.0.moment.dof1` | 1.56878 | half-width 0.00624 | 1.5606 to 1.58099 | threshold/threshold | 29 | 1/1 | False | 1.64e-09 | 0.000239 | 1.71e-09 | inside |
| pnma14 | `phases.0.atoms.0.moment.dof2` | 0.0105876 | half-width 0.0201 | -0.0315224 to 0.0315209 | threshold/threshold | 27 | 1/1 | False | 1.98e-09 | 0.000105 | 2.18e-09 | inside |
| pnma14 | `phases.0.atoms.1.moment.dof1` | 1.56077 | half-width 0.0325 | 1.52007 to 1.62152 | threshold/threshold | 33 | 1/1 | False | 1.51e-09 | 8.01e-05 | 2.73e-09 | inside |
| pnma14 | `phases.0.atoms.1.moment.dof2` | 0.0527353 | half-width 0.0808 | -0.155937 to 0.155919 | threshold/threshold | 32 | 1/1 | False | 2.55e-09 | 0.000202 | 2.88e-09 | inside |
| cpd1a | `phases.1.scale` | 0.000632233 | esd 1.21e-05 | 0.000561997 to 0.000708885 | threshold/threshold | 22 | 1/1 | True | 3.23e-08 | 0.00045 | 1.24e-05 | inside |
| cpd1a | `phases.1.lor_strain` | 0 | esd 0.0265 | 0 to 0.0283718 | bound/threshold | 10 | 0/1 | True | 7.85e-09 | 6.38e-05 | 1.24e-07 | inside |
| fap | `phases.0.atoms.0.biso` | 0.3741 | esd 0.0251 | 0.271302 to 0.480004 | threshold/threshold | 22 | 1/1 | True | 1.92e-08 | 0.000255 | 1.98e-08 | inside |

Each arm against the shipped arm on the same twin: the largest end shift over the rows inside the domain, in each row's unit; then refits spent (shipped → arm, summed over rows) and the stop reasons that changed. *Reached*: the arm's probes differ from shipped's on at least one row.

| Family | Twin | Arm | Largest shift (inside) | Its row | Outside rows, largest | Refits | Stops changed | Reached |
|---|---|---|---|---|---|---|---|---|
| pnma0 | plain | refits30 | 0 | `—` | — | 88 → 88 | — | no |
| pnma0 | plain | refits120 | 0 | `—` | — | 88 → 88 | — | no |
| pnma0 | plain | settle2 | 1.28e-08 | `phases.0.atoms.0.moment.dof1` | — | 88 → 80 | — | yes |
| pnma0 | plain | settle8 | 0 | `—` | — | 88 → 88 | — | no |
| pnma0 | plain | xtol1e-2 | 0.0018 | `phases.0.atoms.0.moment.dof1` | — | 88 → 78 | — | yes |
| pnma0 | plain | xtol1e-4 | 5e-05 | `phases.0.atoms.0.moment.dof1` | — | 88 → 90 | — | yes |
| pnma0 | plain | growth1.5 | 0.000164 | `phases.0.atoms.0.moment.dof1` | — | 88 → 77 | — | yes |
| pnma0 | plain | growth3 | 0.535 | `phases.0.atoms.1.moment.dof1` | — | 88 → 92 | — | yes |
| pnma0 | plain | chi2tol0.003 | 8.5e-06 | `phases.0.atoms.1.moment.dof0` | — | 88 → 88 | — | yes |
| pnma0 | plain | chi2tol0.03 | 5.99e-07 | `phases.0.atoms.1.moment.dof0` | — | 88 → 90 | — | yes |
| pnma0 | plain | reference | 3.93e-05 | `phases.0.atoms.0.moment.dof1` | — | 88 → 98 | — | yes |
| pnma0 | noise | refits30 | 0 | `—` | — | 88 → 88 | — | no |
| pnma0 | noise | refits120 | 0 | `—` | — | 88 → 88 | — | no |
| pnma0 | noise | settle2 | 1.29e-08 | `phases.0.atoms.0.moment.dof1` | — | 88 → 80 | — | yes |
| pnma0 | noise | settle8 | 0 | `—` | — | 88 → 88 | — | no |
| pnma0 | noise | xtol1e-2 | 0.0018 | `phases.0.atoms.0.moment.dof1` | — | 88 → 78 | — | yes |
| pnma0 | noise | xtol1e-4 | 5e-05 | `phases.0.atoms.0.moment.dof1` | — | 88 → 90 | — | yes |
| pnma0 | noise | growth1.5 | 0.000164 | `phases.0.atoms.0.moment.dof1` | — | 88 → 77 | — | yes |
| pnma0 | noise | growth3 | 0.535 | `phases.0.atoms.1.moment.dof1` | — | 88 → 92 | — | yes |
| pnma0 | noise | chi2tol0.003 | 8.5e-06 | `phases.0.atoms.1.moment.dof0` | — | 88 → 88 | — | yes |
| pnma0 | noise | chi2tol0.03 | 5.99e-07 | `phases.0.atoms.1.moment.dof0` | — | 88 → 90 | — | yes |
| pnma0 | noise | reference | 3.93e-05 | `phases.0.atoms.0.moment.dof1` | — | 88 → 98 | — | yes |
| pnma1 | plain | refits30 | 0 | `—` | — | 96 → 96 | — | no |
| pnma1 | plain | refits120 | 0 | `—` | — | 96 → 96 | — | no |
| pnma1 | plain | settle2 | 1.17e-06 | `phases.0.atoms.0.moment.dof2` | — | 96 → 90 | — | yes |
| pnma1 | plain | settle8 | 0 | `—` | — | 96 → 96 | — | no |
| pnma1 | plain | xtol1e-2 | 0.00143 | `phases.0.atoms.0.moment.dof2` | — | 96 → 90 | — | yes |
| pnma1 | plain | xtol1e-4 | 0.000246 | `phases.0.atoms.0.moment.dof2` | — | 96 → 104 | — | yes |
| pnma1 | plain | growth1.5 | 0.000464 | `phases.0.atoms.0.moment.dof2` | — | 96 → 91 | — | yes |
| pnma1 | plain | growth3 | 0.000405 | `phases.0.atoms.1.moment.dof2` | — | 96 → 106 | — | yes |
| pnma1 | plain | chi2tol0.003 | 9.94e-05 | `phases.0.atoms.0.moment.dof2` | — | 96 → 102 | — | yes |
| pnma1 | plain | chi2tol0.03 | 0.000138 | `phases.0.atoms.0.moment.dof2` | — | 96 → 95 | — | yes |
| pnma1 | plain | reference | 0.000251 | `phases.0.atoms.0.moment.dof2` | — | 96 → 108 | — | yes |
| pnma1 | noise | refits30 | 0 | `—` | — | 96 → 96 | — | no |
| pnma1 | noise | refits120 | 0 | `—` | — | 96 → 96 | — | no |
| pnma1 | noise | settle2 | 1.17e-06 | `phases.0.atoms.0.moment.dof2` | — | 96 → 90 | — | yes |
| pnma1 | noise | settle8 | 0 | `—` | — | 96 → 96 | — | no |
| pnma1 | noise | xtol1e-2 | 0.00143 | `phases.0.atoms.0.moment.dof2` | — | 96 → 90 | — | yes |
| pnma1 | noise | xtol1e-4 | 0.000246 | `phases.0.atoms.0.moment.dof2` | — | 96 → 104 | — | yes |
| pnma1 | noise | growth1.5 | 0.000464 | `phases.0.atoms.0.moment.dof2` | — | 96 → 91 | — | yes |
| pnma1 | noise | growth3 | 0.000405 | `phases.0.atoms.1.moment.dof2` | — | 96 → 106 | — | yes |
| pnma1 | noise | chi2tol0.003 | 9.94e-05 | `phases.0.atoms.0.moment.dof2` | — | 96 → 102 | — | yes |
| pnma1 | noise | chi2tol0.03 | 0.000138 | `phases.0.atoms.0.moment.dof2` | — | 96 → 95 | — | yes |
| pnma1 | noise | reference | 0.000251 | `phases.0.atoms.0.moment.dof2` | — | 96 → 108 | — | yes |
| pnma14 | plain | refits30 | 0 | `—` | — | 155 → 155 | — | no |
| pnma14 | plain | refits120 | 0 | `—` | — | 155 → 155 | — | no |
| pnma14 | plain | settle2 | 3.81e-08 | `phases.0.atoms.1.moment.dof0` | — | 155 → 144 | — | yes |
| pnma14 | plain | settle8 | 0 | `—` | — | 155 → 155 | — | no |
| pnma14 | plain | xtol1e-2 | 0.00262 | `phases.0.atoms.1.moment.dof0` | — | 155 → 139 | — | yes |
| pnma14 | plain | xtol1e-4 | 0.000239 | `phases.0.atoms.0.moment.dof1` | — | 155 → 165 | — | yes |
| pnma14 | plain | growth1.5 | 0.000348 | `phases.0.atoms.0.moment.dof1` | — | 155 → 155 | — | yes |
| pnma14 | plain | growth3 | 0.000287 | `phases.0.atoms.1.moment.dof2` | — | 155 → 168 | — | yes |
| pnma14 | plain | chi2tol0.003 | 0 | `—` | — | 155 → 155 | — | no |
| pnma14 | plain | chi2tol0.03 | 3.81e-08 | `phases.0.atoms.1.moment.dof0` | — | 155 → 151 | — | yes |
| pnma14 | plain | reference | 0.000239 | `phases.0.atoms.0.moment.dof1` | — | 155 → 175 | — | yes |
| pnma14 | noise | refits30 | 0 | `—` | — | 155 → 155 | — | no |
| pnma14 | noise | refits120 | 0 | `—` | — | 155 → 155 | — | no |
| pnma14 | noise | settle2 | 2.83e-08 | `phases.0.atoms.1.moment.dof0` | — | 155 → 144 | — | yes |
| pnma14 | noise | settle8 | 0 | `—` | — | 155 → 155 | — | no |
| pnma14 | noise | xtol1e-2 | 0.00262 | `phases.0.atoms.1.moment.dof0` | — | 155 → 139 | — | yes |
| pnma14 | noise | xtol1e-4 | 0.000239 | `phases.0.atoms.0.moment.dof1` | — | 155 → 165 | — | yes |
| pnma14 | noise | growth1.5 | 0.000348 | `phases.0.atoms.0.moment.dof1` | — | 155 → 155 | — | yes |
| pnma14 | noise | growth3 | 0.000287 | `phases.0.atoms.1.moment.dof2` | — | 155 → 168 | — | yes |
| pnma14 | noise | chi2tol0.003 | 0 | `—` | — | 155 → 155 | — | no |
| pnma14 | noise | chi2tol0.03 | 2.83e-08 | `phases.0.atoms.1.moment.dof0` | — | 155 → 151 | — | yes |
| pnma14 | noise | reference | 0.000239 | `phases.0.atoms.0.moment.dof1` | — | 155 → 175 | — | yes |
| cpd1a | plain | refits30 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | plain | refits120 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | plain | settle2 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | plain | settle8 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | plain | xtol1e-2 | 0.00165 | `phases.1.scale` | — | 32 → 30 | — | yes |
| cpd1a | plain | xtol1e-4 | 0.00045 | `phases.1.scale` | — | 32 → 36 | — | yes |
| cpd1a | plain | growth1.5 | 0.00047 | `phases.1.scale` | — | 32 → 36 | — | yes |
| cpd1a | plain | growth3 | 0.00049 | `phases.1.scale` | — | 32 → 38 | — | yes |
| cpd1a | plain | chi2tol0.003 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | plain | chi2tol0.03 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | plain | reference | 0.00045 | `phases.1.scale` | — | 32 → 38 | — | yes |
| cpd1a | noise | refits30 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | noise | refits120 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | noise | settle2 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | noise | settle8 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | noise | xtol1e-2 | 0.00165 | `phases.1.scale` | — | 32 → 30 | — | yes |
| cpd1a | noise | xtol1e-4 | 0.000462 | `phases.1.scale` | — | 32 → 36 | — | yes |
| cpd1a | noise | growth1.5 | 0.000482 | `phases.1.scale` | — | 32 → 36 | — | yes |
| cpd1a | noise | growth3 | 0.000502 | `phases.1.scale` | — | 32 → 38 | — | yes |
| cpd1a | noise | chi2tol0.003 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | noise | chi2tol0.03 | 0 | `—` | — | 32 → 32 | — | no |
| cpd1a | noise | reference | 0.000462 | `phases.1.scale` | — | 32 → 38 | — | yes |
| fap | plain | refits30 | 0 | `—` | — | 22 → 22 | — | no |
| fap | plain | refits120 | 0 | `—` | — | 22 → 22 | — | no |
| fap | plain | settle2 | 0 | `—` | — | 22 → 22 | — | no |
| fap | plain | settle8 | 0 | `—` | — | 22 → 22 | — | no |
| fap | plain | xtol1e-2 | 0.00177 | `phases.0.atoms.0.biso` | — | 22 → 20 | — | yes |
| fap | plain | xtol1e-4 | 0.000255 | `phases.0.atoms.0.biso` | — | 22 → 24 | — | yes |
| fap | plain | growth1.5 | 0.000264 | `phases.0.atoms.0.biso` | — | 22 → 26 | — | yes |
| fap | plain | growth3 | 0.000228 | `phases.0.atoms.0.biso` | — | 22 → 28 | — | yes |
| fap | plain | chi2tol0.003 | 0 | `—` | — | 22 → 22 | — | no |
| fap | plain | chi2tol0.03 | 0 | `—` | — | 22 → 22 | — | no |
| fap | plain | reference | 0.000255 | `phases.0.atoms.0.biso` | — | 22 → 24 | — | yes |
| fap | noise | refits30 | 0 | `—` | — | 22 → 22 | — | no |
| fap | noise | refits120 | 0 | `—` | — | 22 → 22 | — | no |
| fap | noise | settle2 | 0 | `—` | — | 22 → 22 | — | no |
| fap | noise | settle8 | 0 | `—` | — | 22 → 22 | — | no |
| fap | noise | xtol1e-2 | 0.00177 | `phases.0.atoms.0.biso` | — | 22 → 20 | — | yes |
| fap | noise | xtol1e-4 | 0.000255 | `phases.0.atoms.0.biso` | — | 22 → 24 | — | yes |
| fap | noise | growth1.5 | 0.000264 | `phases.0.atoms.0.biso` | — | 22 → 26 | — | yes |
| fap | noise | growth3 | 0.000228 | `phases.0.atoms.0.biso` | — | 22 → 28 | — | yes |
| fap | noise | chi2tol0.003 | 0 | `—` | — | 22 → 22 | — | no |
| fap | noise | chi2tol0.03 | 0 | `—` | — | 22 → 22 | — | no |
| fap | noise | reference | 0.000255 | `phases.0.atoms.0.biso` | — | 22 → 24 | — | yes |

Control, the fit's own intervals against the explicit calls (shipped, plain): largest end difference in the row's unit.

- pnma0: 4 rows attached by the fit, largest difference 0
- pnma1: 4 rows attached by the fit, largest difference 0
- pnma14: 6 rows attached by the fit, largest difference 0

## O2: the fraction grid's three constants

| Family | Phase | Twin | Arm | Grid (n, min, span) | W ± esd, wt % | Admissible range, wt % | Range ends − shipped, in esd | Best point − shipped's, in esd | Basins | χ² fit − best (cut) | Domain |
|---|---|---|---|---|---|---|---|---|---|---|---|
| multimodal | CaF2 | plain | shipped | 11, 0.01, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, 0 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | plain | n5 | 5, 0.01, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, 0.000119 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | plain | n21 | 21, 0.01, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, 7.76e-05 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | plain | min0.003 | 11, 0.003, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, -7.16e-05 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | plain | min0.03 | 11, 0.03, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, 6.19e-05 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | plain | span0.3 | 11, 0.01, 0.3 | 0.931 ± 0.33 | 0.930 to 1.319 | 0, -230 | 0 | 1 | 0.0 (5.2) | inside |
| multimodal | CaF2 | plain | span0.7 | 11, 0.01, 0.7 | 0.931 ± 0.33 | 0.930 to 1.353 | 0, -230 | 0 | 1 | 0.0 (5.2) | inside |
| multimodal | CaF2 | noise | shipped | 11, 0.01, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, 0 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | noise | n5 | 5, 0.01, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, 0.000119 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | noise | n21 | 21, 0.01, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, 7.76e-05 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | noise | min0.003 | 11, 0.003, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, -7.16e-05 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | noise | min0.03 | 11, 0.03, 0.5 | 0.931 ± 0.33 | 0.930 to 77.067 | 0, 6.19e-05 | 0 | 2 | 0.0 (5.2) | top grid point admissible |
| multimodal | CaF2 | noise | span0.3 | 11, 0.01, 0.3 | 0.931 ± 0.33 | 0.930 to 1.319 | 0, -230 | 0 | 1 | 0.0 (5.2) | inside |
| multimodal | CaF2 | noise | span0.7 | 11, 0.01, 0.7 | 0.931 ± 0.33 | 0.930 to 1.353 | 0, -230 | 0 | 1 | 0.0 (5.2) | inside |
| control | CaF2 | plain | shipped | 11, 0.01, 0.5 | 3.674 ± 0.412 | 3.291 to 3.937 | 0, 0 | 0 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | plain | n5 | 5, 0.01, 0.5 | 3.674 ± 0.412 | 3.674 to 3.674 | 0.929, -0.64 | 0.8 | 0 | 0.0 (5.1) | no admissible grid point |
| control | CaF2 | plain | n21 | 21, 0.01, 0.5 | 3.674 ± 0.412 | 3.291 to 3.937 | 5.13e-06, 2.48e-06 | -0.824 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | plain | min0.003 | 11, 0.003, 0.5 | 3.674 ± 0.412 | 3.208 to 3.931 | -0.2, -0.0146 | -0.0146 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | plain | min0.03 | 11, 0.03, 0.5 | 3.674 ± 0.412 | 3.478 to 4.062 | 0.455, 0.302 | -1.11 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | plain | span0.3 | 11, 0.01, 0.3 | 3.674 ± 0.412 | 3.257 to 3.853 | -0.0817, -0.203 | -0.203 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | plain | span0.7 | 11, 0.01, 0.7 | 3.674 ± 0.412 | 3.313 to 3.992 | 0.0551, 0.133 | 0.133 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | noise | shipped | 11, 0.01, 0.5 | 3.674 ± 0.412 | 3.291 to 3.937 | 0, 0 | 0 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | noise | n5 | 5, 0.01, 0.5 | 3.674 ± 0.412 | 3.674 to 3.674 | 0.929, -0.64 | 0.8 | 0 | 0.0 (5.1) | no admissible grid point |
| control | CaF2 | noise | n21 | 21, 0.01, 0.5 | 3.674 ± 0.412 | 3.291 to 3.937 | 5.13e-06, 2.48e-06 | -0.824 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | noise | min0.003 | 11, 0.003, 0.5 | 3.674 ± 0.412 | 3.208 to 3.931 | -0.2, -0.0146 | -0.0146 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | noise | min0.03 | 11, 0.03, 0.5 | 3.674 ± 0.412 | 3.478 to 4.062 | 0.455, 0.302 | -1.11 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | noise | span0.3 | 11, 0.01, 0.3 | 3.674 ± 0.412 | 3.257 to 3.853 | -0.0817, -0.203 | -0.203 | 1 | 0.0 (5.1) | inside |
| control | CaF2 | noise | span0.7 | 11, 0.01, 0.7 | 3.674 ± 0.412 | 3.313 to 3.992 | 0.0551, 0.133 | 0.133 | 1 | 0.0 (5.1) | inside |
| cpd1a | corundum | plain | shipped | 11, 0.01, 0.5 | 1.717 ± 0.643 | 51.520 to 64.299 | 0, 0 | 0 | 4 | 1891.4 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | plain | n5 | 5, 0.01, 0.5 | 1.717 ± 0.643 | 52.543 to 94.120 | 1.59, 46.4 | 61.9 | 3 | 1898.6 (77.4), fit not admissible | top grid point admissible; FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | plain | n21 | 21, 0.01, 0.5 | 1.717 ± 0.643 | 48.989 to 63.147 | -3.94, -1.79 | 0.542 | 4 | 1892.6 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | plain | min0.003 | 11, 0.003, 0.5 | 1.717 ± 0.643 | 50.272 to 62.868 | -1.94, -2.23 | -1.77 | 4 | 1886.8 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | plain | min0.03 | 11, 0.03, 0.5 | 1.717 ± 0.643 | 53.128 to 93.086 | 2.5, 44.8 | 58.6 | 4 | 1948.9 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | plain | span0.3 | 11, 0.01, 0.3 | 1.717 ± 0.643 | 52.989 to 55.717 | 2.29, -13.4 | -0.586 | 4 | 1886.3 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | plain | span0.7 | 11, 0.01, 0.7 | 1.717 ± 0.643 | 53.118 to 92.916 | 2.49, 44.5 | 58.9 | 4 | 1946.6 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | noise | shipped | 11, 0.01, 0.5 | 1.717 ± 0.643 | 51.495 to 64.299 | 0, 0 | 0 | 4 | 1891.4 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | noise | n5 | 5, 0.01, 0.5 | 1.717 ± 0.643 | 52.906 to 53.148 | 2.2, -17.4 | -1.88 | 2 | 1884.2 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | noise | n21 | 21, 0.01, 0.5 | 1.717 ± 0.643 | 53.149 to 93.938 | 2.57, 46.1 | 58.8 | 4 | 1947.7 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | noise | min0.003 | 11, 0.003, 0.5 | 1.717 ± 0.643 | 50.985 to 62.868 | -0.794, -2.23 | -1.77 | 4 | 1886.8 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | noise | min0.03 | 11, 0.03, 0.5 | 1.717 ± 0.643 | 51.266 to 64.815 | -0.356, 0.803 | 0.543 | 4 | 1892.6 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | noise | span0.3 | 11, 0.01, 0.3 | 1.717 ± 0.643 | 51.503 to 55.297 | 0.0122, -14 | -0.586 | 4 | 1886.3 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | corundum | noise | span0.7 | 11, 0.01, 0.7 | 1.717 ± 0.643 | 51.188 to 62.181 | -0.478, -3.3 | 0.558 | 4 | 1892.6 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | zincite | plain | shipped | 11, 0.01, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | 0, 0 | 0 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | plain | n5 | 5, 0.01, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | 0.000106, 0 | 0.000106 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | plain | n21 | 21, 0.01, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | -0.00303, 0 | -0.00303 | 1 | 90.4 (77.4), fit not admissible | inside |
| cpd1a | zincite | plain | min0.003 | 11, 0.003, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | 5.62e-05, 0 | 5.62e-05 | 1 | 90.1 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 1 points |
| cpd1a | zincite | plain | min0.03 | 11, 0.03, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | -0.000453, 0 | -0.000453 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | plain | span0.3 | 11, 0.01, 0.3 | 3.354 ± 0.208 | 3.484 to 3.509 | -0.000308, 0 | 1.45e-06 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | plain | span0.7 | 11, 0.01, 0.7 | 3.354 ± 0.208 | 3.484 to 3.509 | 1.89e-06, 0 | 1.89e-06 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | noise | shipped | 11, 0.01, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | 0, 0 | 0 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | noise | n5 | 5, 0.01, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | 0.000106, 0 | 0.000106 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | noise | n21 | 21, 0.01, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | -0.00302, 0 | -0.00302 | 1 | 90.4 (77.4), fit not admissible | inside |
| cpd1a | zincite | noise | min0.003 | 11, 0.003, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | 5.62e-05, 0 | 5.62e-05 | 1 | 90.1 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 1 points |
| cpd1a | zincite | noise | min0.03 | 11, 0.03, 0.5 | 3.354 ± 0.208 | 3.484 to 3.509 | -0.000307, 0 | -0.000307 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | noise | span0.3 | 11, 0.01, 0.3 | 3.354 ± 0.208 | 3.484 to 3.509 | -0.000308, 0 | -1.94e-06 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | zincite | noise | span0.7 | 11, 0.01, 0.7 | 3.354 ± 0.208 | 3.484 to 3.509 | 2.28e-05, 0 | 2.28e-05 | 1 | 90.1 (77.4), fit not admissible | inside |
| cpd1a | fluorite | plain | shipped | 11, 0.01, 0.5 | 94.928 ± 0.645 | 94.619 to 94.913 | 0, 0 | 0 | 1 | 89.8 (77.4), fit not admissible | top grid point admissible; FROZEN_COMPILE_STALE at 5 points |
| cpd1a | fluorite | plain | n5 | 5, 0.01, 0.5 | 94.928 ± 0.645 | 94.621 to 94.809 | 0.00186, -0.161 | 0.00213 | 1 | 89.8 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 1 points |
| cpd1a | fluorite | plain | n21 | 21, 0.01, 0.5 | 94.928 ± 0.645 | 94.609 to 94.919 | -0.0168, 0.00954 | -0.0168 | 1 | 90.1 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 3 points |
| cpd1a | fluorite | plain | min0.003 | 11, 0.003, 0.5 | 94.928 ± 0.645 | 94.619 to 94.915 | 0.00012, 0.0025 | 0.000276 | 1 | 89.8 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 1 points |
| cpd1a | fluorite | plain | min0.03 | 11, 0.03, 0.5 | 94.928 ± 0.645 | 94.620 to 94.906 | 0.000911, -0.0104 | 0.00246 | 1 | 89.9 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 3 points |
| cpd1a | fluorite | plain | span0.3 | 11, 0.01, 0.3 | 94.928 ± 0.645 | 94.619 to 94.914 | -0.00134, 0.00208 | 0.00261 | 1 | 89.9 (77.4), fit not admissible | top grid point admissible; FROZEN_COMPILE_STALE at 1 points |
| cpd1a | fluorite | plain | span0.7 | 11, 0.01, 0.7 | 94.928 ± 0.645 | 94.619 to 94.912 | 2.38e-06, -0.00139 | 2.38e-06 | 1 | 89.8 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | fluorite | noise | shipped | 11, 0.01, 0.5 | 94.928 ± 0.645 | 94.619 to 94.913 | 0, 0 | 0 | 1 | 89.8 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 4 points |
| cpd1a | fluorite | noise | n5 | 5, 0.01, 0.5 | 94.928 ± 0.645 | 94.621 to 94.809 | 0.00186, -0.161 | 0.00213 | 1 | 89.8 (77.4), fit not admissible | inside |
| cpd1a | fluorite | noise | n21 | 21, 0.01, 0.5 | 94.928 ± 0.645 | 94.609 to 94.919 | -0.0168, 0.00954 | -0.0168 | 1 | 90.1 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
| cpd1a | fluorite | noise | min0.003 | 11, 0.003, 0.5 | 94.928 ± 0.645 | 94.619 to 94.915 | 0.000124, 0.0025 | 0.000279 | 1 | 89.8 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 1 points |
| cpd1a | fluorite | noise | min0.03 | 11, 0.03, 0.5 | 94.928 ± 0.645 | 94.620 to 94.906 | 0.000914, -0.0104 | 0.00246 | 1 | 89.9 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 4 points |
| cpd1a | fluorite | noise | span0.3 | 11, 0.01, 0.3 | 94.928 ± 0.645 | 94.619 to 94.914 | -0.00134, 0.00208 | 0.00262 | 1 | 89.9 (77.4), fit not admissible | top grid point admissible; FROZEN_COMPILE_STALE at 2 points |
| cpd1a | fluorite | noise | span0.7 | 11, 0.01, 0.7 | 94.928 ± 0.645 | 94.619 to 94.912 | 5.77e-06, -0.00139 | 5.77e-06 | 1 | 89.8 (77.4), fit not admissible | FROZEN_COMPILE_STALE at 2 points |
