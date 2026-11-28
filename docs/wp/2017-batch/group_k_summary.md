# WP-2017 group K, `MODEL_FAR_FROM_DATA`'s level on a thinned family

Rows: 464 fits (0 raised or timed out), head `4efc1b4c5`, Linux x86_64, Python 3.12.14, numpy 2.5.3, scipy 1.18.1, rietx-kernels 1.5.0; α = 0.05. Written by `group_k.py summary`; the raw rows are not committed.

p is Hamilton's upper-tail probability of the fit against the background-only fit, the quantity `MODEL_FAR_FROM_DATA` compares with α (it fires at p ≥ α; an undefined test reads 1).  Arms, classes and labels: the script's docstring, fixed before the run.

## The edges

- Largest p over the 64 correct fits: 4.651e-142 (fap/protocol/+0.00%/0.05c_s3, Rwp 0.9161, F 53.8).
- Smallest p over the 204 full collapses: 0.999999999998798 (fap/protocol/+0.00%/1c_s2/scale0, Rwp 0.8658, F 1.2e-12).
- Correct fits flagged: 0; full collapses not flagged: 0.
- Read after the run: the pre-registered label (the main phase's scale under 0.001 of the correct fit's) took 252 fits.  204 of them have every phase's scale there.  The other 48 (nac) lost the main phase while another phase kept its scale: 2 flagged, p 4.71e-69 to 0.99, scale of the other phase over its correct fit's 0.0334 to 2.08.  Over the pre-registered set the smallest p is 4.71e-69.
- Spy and code agree (flagged ⇔ p ≥ α) on 464 of 464 rows.

Five correct fits with the largest p: fap/protocol/+0.00%/0.05c_s3 4.651e-142; srm660c/protocol/+0.00%/0.05c_s3 1.776e-180; fap/protocol/+0.00%/0.05c_s2 7.713e-184; srm660c/protocol/+0.00%/0.05c_s2 2.193e-185; srm660c/protocol/+0.00%/0.05c_s1 2.703e-207.

Five full collapses with the smallest p: fap/protocol/+0.00%/1c_s2/scale0 0.999999999998798; fap/protocol/+0.00%/full/scale0 0.999999999999619; nac/protocol/+0.00%/0.05c_s1/scale0 1; corundum/mccusker_default/-3.00%/full 1; corundum/protocol/-3.00%/full 1.

## Correct starts and held collapses, by family and count

| family | counts a channel | correct: fits | Rwp | flagged | largest p | smallest F | scale0: fits | Rwp | flagged | smallest p |
|---|---|---|---|---|---|---|---|---|---|---|
| corundum | as measured | 1 | 0.144-0.144 | 0 | 0.00e+00 | 1.52e+04 | 1 | 0.820-0.820 | 1 | 1 |
| corundum | 0.05 | 3 | 0.844-0.855 | 0 | 0.00e+00 | 157 | 3 | 0.980-0.983 | 3 | 1 |
| corundum | 0.1 | 3 | 0.789-0.814 | 0 | 0.00e+00 | 210 | 3 | 0.972-0.975 | 3 | 1 |
| corundum | 0.2 | 3 | 0.727-0.755 | 0 | 0.00e+00 | 302 | 3 | 0.962-0.963 | 3 | 1 |
| corundum | 0.5 | 3 | 0.643-0.656 | 0 | 0.00e+00 | 509 | 3 | 0.940-0.943 | 3 | 1 |
| corundum | 1 | 3 | 0.582-0.597 | 0 | 0.00e+00 | 676 | 3 | 0.923-0.925 | 3 | 1 |
| fap | as measured | 1 | 0.093-0.093 | 0 | 0.00e+00 | 2.24e+04 | 1 | 0.693-0.693 | 1 | 0.999999999999619 |
| fap | 0.05 | 3 | 0.891-0.916 | 0 | 4.65e-142 | 53.8 | 3 | 0.974-0.977 | 3 | 1 |
| fap | 0.1 | 3 | 0.856-0.869 | 0 | 1.10e-231 | 88.8 | 3 | 0.955-0.959 | 3 | 1 |
| fap | 0.2 | 3 | 0.805-0.808 | 0 | 0.00e+00 | 137 | 3 | 0.929-0.937 | 3 | 1 |
| fap | 0.5 | 3 | 0.707-0.714 | 0 | 0.00e+00 | 228 | 3 | 0.890-0.900 | 3 | 1 |
| fap | 1 | 3 | 0.624-0.636 | 0 | 0.00e+00 | 349 | 3 | 0.859-0.867 | 3 | 0.999999999998798 |
| srm660c | as measured | 1 | 0.087-0.087 | 0 | 0.00e+00 | 4.26e+04 | 1 | 0.862-0.862 | 1 | 1 |
| srm660c | 0.05 | 3 | 0.889-0.900 | 0 | 1.78e-180 | 79.6 | 3 | 0.977-0.980 | 3 | 1 |
| srm660c | 0.1 | 3 | 0.840-0.851 | 0 | 2.71e-284 | 129 | 3 | 0.966-0.967 | 3 | 1 |
| srm660c | 0.2 | 3 | 0.782-0.786 | 0 | 0.00e+00 | 206 | 3 | 0.950-0.951 | 3 | 1 |
| srm660c | 0.5 | 3 | 0.681-0.692 | 0 | 0.00e+00 | 364 | 3 | 0.932-0.935 | 3 | 1 |
| srm660c | 1 | 3 | 0.583-0.593 | 0 | 0.00e+00 | 627 | 3 | 0.920-0.923 | 3 | 1 |
| nac | as measured | 1 | 0.093-0.093 | 0 | 0.00e+00 | 9.82e+04 | 1 | 0.838-0.838 | 1 | 1 |
| nac | 0.05 | 3 | 0.740-0.753 | 0 | 0.00e+00 | 1.07e+03 | 3 | 0.990-0.990 | 3 | 1 |
| nac | 0.1 | 3 | 0.693-0.696 | 0 | 0.00e+00 | 1.48e+03 | 3 | 0.986-0.986 | 3 | 1 |
| nac | 0.2 | 3 | 0.635-0.649 | 0 | 0.00e+00 | 1.62e+03 | 3 | 0.979-0.981 | 3 | 1 |
| nac | 0.5 | 3 | 0.568-0.582 | 0 | 0.00e+00 | 2.15e+03 | 3 | 0.965-0.967 | 3 | 1 |
| nac | 1 | 3 | 0.521-0.526 | 0 | 0.00e+00 | 2.77e+03 | 3 | 0.950-0.953 | 3 | 1 |

## Displaced starts (the reach harness)

| family | counts | fits | reached | error | silent | full collapse | partial capture | other |
|---|---|---|---|---|---|---|---|---|
| corundum | as measured | 13 | 7 | 5 | 1 | 3 | 1 | 2 |
| corundum | 0.5 | 39 | 3 | 36 | 0 | 27 | 9 | 0 |
| corundum | 0.1 | 39 | 1 | 36 | 2 | 33 | 3 | 2 |
| fap | as measured | 13 | 8 | 1 | 4 | 1 | 4 | 0 |
| fap | 0.5 | 39 | 19 | 2 | 18 | 0 | 14 | 6 |
| fap | 0.1 | 39 | 10 | 9 | 20 | 3 | 18 | 8 |
| srm660c | as measured | 13 | 1 | 12 | 0 | 9 | 3 | 0 |
| srm660c | 0.5 | 39 | 3 | 31 | 5 | 30 | 5 | 1 |
| srm660c | 0.1 | 39 | 3 | 30 | 6 | 30 | 6 | 0 |
| nac | as measured | 9 | 0 | 1 | 8 | 9 | 0 | 0 |
| nac | 0.5 | 27 | 0 | 3 | 24 | 24 | 3 | 0 |
| nac | 0.1 | 27 | 0 | 3 | 24 | 19 | 8 | 0 |

Every displaced fit that did not reach its answer:

| case | class | label | scale / correct | every phase | Rwp | usable | flagged | p | errors |
|---|---|---|---|---|---|---|---|---|---|
| corundum/lab_bragg_brentano/+1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+1.50%/0.1c_s3 | error | partial capture | 0.00286 | no | 0.9714 | False | True | 0.657 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+1.50%/0.5c_s1 | error | partial capture | 0.00357 | no | 0.9422 | False | True | 0.819 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+1.50%/0.5c_s3 | error | partial capture | 0.00299 | no | 0.9411 | False | True | 0.802 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9426 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/+3.00%/full | silent | partial capture | 0.0158 | no | 0.8015 | True | False | 1.92e-66 | — |
| corundum/lab_bragg_brentano/-1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9426 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-1.50%/full | error | other | 3.09e+07 | no | 0.8204 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-3.00%/0.5c_s1 | error | partial capture | 0.00366 | no | 0.9423 | False | True | 0.932 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/lab_bragg_brentano/-3.00%/full | error | full collapse | 0 | yes | 0.8204 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+0.00%/0.1c_s1/z+0.2 | silent | other | 0.907 | no | 0.8009 | True | False | 0 | — |
| corundum/mccusker_default/+0.00%/0.1c_s3/z+0.2 | silent | other | 0.732 | no | 0.7963 | True | False | 0 | — |
| corundum/mccusker_default/+1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+1.50%/0.1c_s3 | error | partial capture | 0.00532 | no | 0.9718 | False | True | 0.962 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+1.50%/0.5c_s1 | error | partial capture | 0.00161 | no | 0.9426 | False | True | 0.999 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+1.50%/0.5c_s3 | error | partial capture | 0.00177 | no | 0.9415 | False | True | 0.996 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9426 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/+3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9426 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-3.00%/0.5c_s1 | error | partial capture | 0.00339 | no | 0.9424 | False | True | 0.802 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/mccusker_default/-3.00%/full | error | full collapse | 0 | yes | 0.8204 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+1.50%/0.1c_s3 | error | partial capture | 0.00282 | no | 0.9713 | False | True | 0.582 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+1.50%/0.5c_s1 | error | partial capture | 0.00359 | no | 0.9422 | False | True | 0.818 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+1.50%/0.5c_s3 | error | partial capture | 0.00323 | no | 0.9412 | False | True | 0.858 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9426 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/+3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9426 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-1.50%/full | error | other | 3.08e+07 | no | 0.8204 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9737 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9748 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9719 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-3.00%/0.5c_s1 | error | partial capture | 0.00387 | no | 0.9424 | False | True | 0.948 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9405 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9415 | False | True | 1 | MODEL_FAR_FROM_DATA |
| corundum/protocol/-3.00%/full | error | full collapse | 0 | yes | 0.8204 | False | True | 1 | MODEL_FAR_FROM_DATA |
| fap/lab_bragg_brentano/+1.50%/0.1c_s1 | error | partial capture | 0.0536 | no | 0.9544 | False | True | 0.356 | MODEL_FAR_FROM_DATA |
| fap/lab_bragg_brentano/+1.50%/0.1c_s2 | silent | other | 0.94 | no | 0.8650 | True | False | 1.94e-241 | — |
| fap/lab_bragg_brentano/+1.50%/0.1c_s3 | silent | other | 1.11 | no | 0.8688 | True | False | 4.1e-235 | — |
| fap/lab_bragg_brentano/+1.50%/0.5c_s1 | silent | other | 1.08 | no | 0.7093 | True | False | 0 | — |
| fap/lab_bragg_brentano/+1.50%/0.5c_s2 | silent | other | 0.927 | no | 0.7159 | True | False | 0 | — |
| fap/lab_bragg_brentano/+3.00%/0.1c_s1 | silent | partial capture | 0.198 | no | 0.9520 | True | False | 1.73e-05 | — |
| fap/lab_bragg_brentano/+3.00%/0.1c_s2 | error | partial capture | 0.0391 | no | 0.9566 | False | True | 0.657 | MODEL_FAR_FROM_DATA |
| fap/lab_bragg_brentano/+3.00%/0.1c_s3 | silent | other | 1.04 | no | 0.8936 | True | False | 1.31e-165 | — |
| fap/lab_bragg_brentano/+3.00%/0.5c_s1 | silent | other | 1.08 | no | 0.7093 | True | False | 0 | — |
| fap/lab_bragg_brentano/+3.00%/0.5c_s2 | error | partial capture | 0.0187 | no | 0.8903 | False | True | 0.0941 | MODEL_FAR_FROM_DATA |
| fap/lab_bragg_brentano/+3.00%/full | silent | partial capture | 0.121 | no | 0.6893 | True | False | 5.11e-08 | — |
| fap/lab_bragg_brentano/-1.50%/0.1c_s1 | silent | other | 1.19 | no | 0.8578 | True | False | 3.08e-257 | — |
| fap/lab_bragg_brentano/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9572 | False | True | 1 | MODEL_FAR_FROM_DATA |
| fap/lab_bragg_brentano/-1.50%/0.1c_s3 | silent | other | 1.04 | no | 0.8687 | True | False | 3.71e-235 | — |
| fap/lab_bragg_brentano/-1.50%/0.5c_s1 | silent | other | 1.08 | no | 0.7093 | True | False | 0 | — |
| fap/lab_bragg_brentano/-1.50%/0.5c_s2 | silent | other | 0.927 | no | 0.7159 | True | False | 0 | — |
| fap/lab_bragg_brentano/-1.50%/full | error | full collapse | 0 | yes | 0.6928 | False | True | 1 | MODEL_FAR_FROM_DATA |
| fap/lab_bragg_brentano/-3.00%/0.1c_s1 | silent | partial capture | 0.213 | no | 0.9502 | True | False | 1.6e-09 | — |
| fap/lab_bragg_brentano/-3.00%/0.1c_s2 | silent | partial capture | 0.213 | no | 0.9517 | True | False | 1.62e-10 | — |
| fap/lab_bragg_brentano/-3.00%/0.1c_s3 | silent | partial capture | 0.151 | no | 0.9541 | True | False | 6.3e-09 | — |
| fap/lab_bragg_brentano/-3.00%/0.5c_s1 | silent | partial capture | 0.198 | no | 0.8814 | True | False | 2.11e-20 | — |
| fap/lab_bragg_brentano/-3.00%/0.5c_s2 | silent | partial capture | 0.101 | no | 0.8866 | True | False | 4.26e-10 | — |
| fap/lab_bragg_brentano/-3.00%/0.5c_s3 | silent | partial capture | 0.253 | no | 0.8898 | True | False | 4.03e-24 | — |
| fap/lab_bragg_brentano/-3.00%/full | silent | partial capture | 0.0701 | no | 0.6833 | True | False | 5.67e-28 | — |
| fap/mccusker_default/+1.50%/0.1c_s1 | error | partial capture | 0.0481 | no | 0.9547 | False | True | 0.3 | MODEL_FAR_FROM_DATA |
| fap/mccusker_default/+3.00%/0.1c_s2 | error | partial capture | 0.0874 | no | 0.9565 | False | True | 0.237 | MODEL_FAR_FROM_DATA |
| fap/mccusker_default/+3.00%/0.1c_s3 | silent | other | 1.03 | no | 0.8905 | True | False | 2.95e-177 | — |
| fap/mccusker_default/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9572 | False | True | 1 | MODEL_FAR_FROM_DATA |
| fap/mccusker_default/-3.00%/0.1c_s1 | silent | partial capture | 0.122 | no | 0.9529 | True | False | 9.63e-05 | — |
| fap/mccusker_default/-3.00%/0.1c_s2 | silent | other | 0.688 | no | 0.9405 | True | False | 3.05e-40 | — |
| fap/mccusker_default/-3.00%/0.1c_s3 | silent | partial capture | 0.0978 | no | 0.9572 | True | False | 0.00454 | — |
| fap/mccusker_default/-3.00%/0.5c_s1 | silent | partial capture | 0.173 | no | 0.8803 | True | False | 6.29e-24 | — |
| fap/mccusker_default/-3.00%/0.5c_s2 | silent | partial capture | 0.117 | no | 0.8847 | True | False | 3.25e-15 | — |
| fap/mccusker_default/-3.00%/0.5c_s3 | silent | partial capture | 0.0625 | no | 0.8968 | True | False | 8.2e-07 | — |
| fap/mccusker_default/-3.00%/full | silent | partial capture | 0.12 | no | 0.6761 | True | False | 4.52e-55 | — |
| fap/protocol/+1.50%/0.1c_s1 | error | partial capture | 0.0542 | no | 0.9548 | False | True | 0.0922 | MODEL_FAR_FROM_DATA |
| fap/protocol/+1.50%/0.1c_s3 | silent | partial capture | 0.236 | no | 0.9566 | True | False | 3.45e-06 | — |
| fap/protocol/+1.50%/0.5c_s1 | silent | partial capture | 0.0957 | no | 0.8883 | True | False | 4.26e-06 | — |
| fap/protocol/+1.50%/0.5c_s3 | silent | partial capture | 0.07 | no | 0.8984 | True | False | 2.28e-05 | — |
| fap/protocol/+3.00%/0.1c_s1 | silent | partial capture | 0.0886 | no | 0.9539 | True | False | 0.000461 | — |
| fap/protocol/+3.00%/0.1c_s2 | error | partial capture | 0.0871 | no | 0.9566 | False | True | 0.055 | MODEL_FAR_FROM_DATA |
| fap/protocol/+3.00%/0.1c_s3 | silent | partial capture | 0.135 | no | 0.9576 | True | False | 0.000799 | — |
| fap/protocol/+3.00%/0.5c_s1 | silent | partial capture | 0.0352 | no | 0.8891 | True | False | 0.000383 | — |
| fap/protocol/+3.00%/0.5c_s2 | silent | partial capture | 0.0309 | no | 0.8909 | True | False | 0.0318 | — |
| fap/protocol/+3.00%/0.5c_s3 | error | partial capture | 0.0263 | no | 0.8998 | False | True | 0.0807 | MODEL_FAR_FROM_DATA |
| fap/protocol/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9572 | False | True | 1 | MODEL_FAR_FROM_DATA |
| fap/protocol/-1.50%/0.1c_s3 | silent | other | 1.93 | no | 0.9432 | True | False | 5.83e-33 | — |
| fap/protocol/-3.00%/0.1c_s1 | silent | partial capture | 0.129 | no | 0.9532 | True | False | 9.45e-06 | — |
| fap/protocol/-3.00%/0.1c_s2 | silent | partial capture | 0.211 | no | 0.9524 | True | False | 1.32e-12 | — |
| fap/protocol/-3.00%/0.1c_s3 | silent | partial capture | 0.117 | no | 0.9575 | True | False | 0.00046 | — |
| fap/protocol/-3.00%/0.5c_s1 | silent | partial capture | 0.252 | no | 0.8759 | True | False | 6.36e-33 | — |
| fap/protocol/-3.00%/0.5c_s2 | silent | partial capture | 0.251 | no | 0.8752 | True | False | 1.42e-37 | — |
| fap/protocol/-3.00%/0.5c_s3 | silent | other | 0.787 | no | 0.8801 | True | False | 1.5e-47 | — |
| fap/protocol/-3.00%/full | silent | partial capture | 0.118 | no | 0.6735 | True | False | 5.87e-61 | — |
| nac/mccusker_default/+0.00%/0.1c_s1/z+0.2 | error | full collapse | 0 | yes | 0.9856 | False | True | 1 | MODEL_FAR_FROM_DATA |
| nac/mccusker_default/+0.00%/0.1c_s2/z+0.2 | error | full collapse | 0 | yes | 0.9855 | False | True | 1 | MODEL_FAR_FROM_DATA |
| nac/mccusker_default/+0.00%/0.1c_s3/z+0.2 | error | full collapse | 0 | yes | 0.9863 | False | True | 1 | MODEL_FAR_FROM_DATA |
| nac/mccusker_default/+0.00%/0.5c_s1/z+0.2 | error | partial capture | 0.00139 | no | 0.9647 | False | True | 0.847 | MODEL_FAR_FROM_DATA |
| nac/mccusker_default/+0.00%/0.5c_s2/z+0.2 | error | full collapse | 0.000509 | no | 0.9662 | False | True | 0.472 | MODEL_FAR_FROM_DATA |
| nac/mccusker_default/+0.00%/0.5c_s3/z+0.2 | error | full collapse | 0.000313 | no | 0.9670 | False | True | 0.99 | MODEL_FAR_FROM_DATA |
| nac/mccusker_default/+0.00%/full/z+0.2 | error | full collapse | 0 | yes | 0.8380 | False | True | 1 | MODEL_FAR_FROM_DATA |
| nac/mccusker_default/+1.50%/0.1c_s1 | silent | full collapse | 0 | no | 0.9836 | True | False | 2.3e-16 | — |
| nac/mccusker_default/+1.50%/0.1c_s2 | silent | full collapse | 0 | no | 0.9834 | True | False | 3.99e-17 | — |
| nac/mccusker_default/+1.50%/0.1c_s3 | silent | partial capture | 0.00311 | no | 0.9840 | True | False | 3.75e-18 | — |
| nac/mccusker_default/+1.50%/0.5c_s1 | silent | full collapse | 0 | no | 0.9613 | True | False | 5.46e-29 | — |
| nac/mccusker_default/+1.50%/0.5c_s2 | silent | full collapse | 0 | no | 0.9641 | True | False | 1.45e-18 | — |
| nac/mccusker_default/+1.50%/0.5c_s3 | silent | full collapse | 0 | no | 0.9646 | True | False | 1.45e-20 | — |
| nac/mccusker_default/+1.50%/full | silent | full collapse | 0 | no | 0.8315 | True | False | 1.13e-68 | — |
| nac/mccusker_default/+3.00%/0.1c_s1 | silent | partial capture | 0.00169 | no | 0.9836 | True | False | 2.08e-16 | — |
| nac/mccusker_default/+3.00%/0.1c_s2 | silent | full collapse | 0 | no | 0.9834 | True | False | 3.99e-17 | — |
| nac/mccusker_default/+3.00%/0.1c_s3 | silent | full collapse | 0 | no | 0.9842 | True | False | 5.91e-17 | — |
| nac/mccusker_default/+3.00%/0.5c_s1 | silent | full collapse | 1.02e-06 | no | 0.9613 | True | False | 5.4e-29 | — |
| nac/mccusker_default/+3.00%/0.5c_s2 | silent | full collapse | 0 | no | 0.9641 | True | False | 1.45e-18 | — |
| nac/mccusker_default/+3.00%/0.5c_s3 | silent | full collapse | 0 | no | 0.9646 | True | False | 1.44e-20 | — |
| nac/mccusker_default/+3.00%/full | silent | full collapse | 0 | no | 0.8315 | True | False | 1.13e-68 | — |
| nac/mccusker_default/-1.50%/0.1c_s1 | silent | full collapse | 0 | no | 0.9836 | True | False | 2.38e-16 | — |
| nac/mccusker_default/-1.50%/0.1c_s2 | silent | full collapse | 0 | no | 0.9834 | True | False | 3.99e-17 | — |
| nac/mccusker_default/-1.50%/0.1c_s3 | silent | full collapse | 0 | no | 0.9842 | True | False | 5.9e-17 | — |
| nac/mccusker_default/-1.50%/0.5c_s1 | silent | full collapse | 0 | no | 0.9613 | True | False | 5.39e-29 | — |
| nac/mccusker_default/-1.50%/0.5c_s2 | silent | full collapse | 2.09e-05 | no | 0.9641 | True | False | 1.45e-18 | — |
| nac/mccusker_default/-1.50%/0.5c_s3 | silent | full collapse | 0.000108 | no | 0.9646 | True | False | 1.43e-20 | — |
| nac/mccusker_default/-1.50%/full | silent | full collapse | 0 | no | 0.8315 | True | False | 1.13e-68 | — |
| nac/mccusker_default/-3.00%/0.1c_s1 | silent | partial capture | 0.00313 | no | 0.9836 | True | False | 1.86e-16 | — |
| nac/mccusker_default/-3.00%/0.1c_s2 | silent | full collapse | 0 | no | 0.9834 | True | False | 4e-17 | — |
| nac/mccusker_default/-3.00%/0.1c_s3 | silent | partial capture | 0.00209 | no | 0.9842 | True | False | 4.98e-17 | — |
| nac/mccusker_default/-3.00%/0.5c_s1 | silent | full collapse | 0.000571 | no | 0.9613 | True | False | 5.13e-29 | — |
| nac/mccusker_default/-3.00%/0.5c_s2 | silent | full collapse | 0.000441 | no | 0.9641 | True | False | 1.41e-18 | — |
| nac/mccusker_default/-3.00%/0.5c_s3 | silent | partial capture | 0.00216 | no | 0.9645 | True | False | 7.53e-21 | — |
| nac/mccusker_default/-3.00%/full | silent | full collapse | 0.00026 | no | 0.8315 | True | False | 6.53e-68 | — |
| nac/protocol/+1.50%/0.1c_s1 | silent | full collapse | 0 | no | 0.9836 | True | False | 2.3e-16 | — |
| nac/protocol/+1.50%/0.1c_s2 | silent | full collapse | 0 | no | 0.9834 | True | False | 3.99e-17 | — |
| nac/protocol/+1.50%/0.1c_s3 | silent | partial capture | 0.00311 | no | 0.9840 | True | False | 3.73e-18 | — |
| nac/protocol/+1.50%/0.5c_s1 | silent | full collapse | 0 | no | 0.9612 | True | False | 1.18e-28 | — |
| nac/protocol/+1.50%/0.5c_s2 | silent | full collapse | 0 | no | 0.9639 | True | False | 5.38e-19 | — |
| nac/protocol/+1.50%/0.5c_s3 | silent | full collapse | 0 | no | 0.9645 | True | False | 3.62e-20 | — |
| nac/protocol/+1.50%/full | silent | full collapse | 0 | no | 0.8313 | True | False | 4.72e-69 | — |
| nac/protocol/+3.00%/0.1c_s1 | silent | partial capture | 0.00169 | no | 0.9836 | True | False | 2.08e-16 | — |
| nac/protocol/+3.00%/0.1c_s2 | silent | full collapse | 0 | no | 0.9834 | True | False | 3.99e-17 | — |
| nac/protocol/+3.00%/0.1c_s3 | silent | full collapse | 0 | no | 0.9842 | True | False | 5.91e-17 | — |
| nac/protocol/+3.00%/0.5c_s1 | silent | full collapse | 0 | no | 0.9612 | True | False | 1.17e-28 | — |
| nac/protocol/+3.00%/0.5c_s2 | silent | full collapse | 0 | no | 0.9639 | True | False | 5.38e-19 | — |
| nac/protocol/+3.00%/0.5c_s3 | silent | full collapse | 0 | no | 0.9645 | True | False | 3.6e-20 | — |
| nac/protocol/+3.00%/full | silent | full collapse | 0 | no | 0.8313 | True | False | 4.71e-69 | — |
| nac/protocol/-1.50%/0.1c_s1 | silent | full collapse | 0 | no | 0.9836 | True | False | 2.38e-16 | — |
| nac/protocol/-1.50%/0.1c_s2 | silent | full collapse | 0 | no | 0.9834 | True | False | 3.99e-17 | — |
| nac/protocol/-1.50%/0.1c_s3 | silent | full collapse | 0 | no | 0.9842 | True | False | 5.9e-17 | — |
| nac/protocol/-1.50%/0.5c_s1 | silent | full collapse | 0 | no | 0.9612 | True | False | 1.17e-28 | — |
| nac/protocol/-1.50%/0.5c_s2 | silent | full collapse | 0 | no | 0.9639 | True | False | 5.38e-19 | — |
| nac/protocol/-1.50%/0.5c_s3 | silent | full collapse | 0.000117 | no | 0.9645 | True | False | 3.57e-20 | — |
| nac/protocol/-1.50%/full | silent | full collapse | 0 | no | 0.8313 | True | False | 4.71e-69 | — |
| nac/protocol/-3.00%/0.1c_s1 | silent | partial capture | 0.00313 | no | 0.9836 | True | False | 1.86e-16 | — |
| nac/protocol/-3.00%/0.1c_s2 | silent | full collapse | 0 | no | 0.9834 | True | False | 4e-17 | — |
| nac/protocol/-3.00%/0.1c_s3 | silent | partial capture | 0.00209 | no | 0.9842 | True | False | 4.98e-17 | — |
| nac/protocol/-3.00%/0.5c_s1 | silent | full collapse | 0.000561 | no | 0.9612 | True | False | 1.11e-28 | — |
| nac/protocol/-3.00%/0.5c_s2 | silent | full collapse | 0.000426 | no | 0.9639 | True | False | 5.22e-19 | — |
| nac/protocol/-3.00%/0.5c_s3 | silent | partial capture | 0.00212 | no | 0.9645 | True | False | 2.12e-20 | — |
| nac/protocol/-3.00%/full | silent | full collapse | 0.000129 | no | 0.8312 | True | False | 2.93e-65 | — |
| srm660c/lab_bragg_brentano/+1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+1.50%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+3.00%/0.1c_s2 | silent | partial capture | 0.0503 | no | 0.9638 | True | False | 1.64e-05 | — |
| srm660c/lab_bragg_brentano/+3.00%/0.1c_s3 | silent | partial capture | 0.0922 | no | 0.9637 | True | False | 1.73e-05 | — |
| srm660c/lab_bragg_brentano/+3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/+3.00%/0.5c_s2 | silent | partial capture | 0.142 | no | 0.9265 | True | False | 6.74e-16 | — |
| srm660c/lab_bragg_brentano/+3.00%/0.5c_s3 | silent | partial capture | 0.056 | no | 0.9284 | True | False | 1.68e-05 | — |
| srm660c/lab_bragg_brentano/+3.00%/full | error | partial capture | 0.00168 | no | 0.8610 | False | True | 0.685 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-1.50%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/lab_bragg_brentano/-3.00%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+1.50%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+3.00%/0.1c_s2 | silent | partial capture | 0.0431 | no | 0.9652 | True | False | 0.000842 | — |
| srm660c/mccusker_default/+3.00%/0.1c_s3 | silent | partial capture | 0.103 | no | 0.9626 | True | False | 6.28e-09 | — |
| srm660c/mccusker_default/+3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/+3.00%/0.5c_s2 | error | partial capture | 0.215 | no | 0.9192 | False | False | 4.64e-35 | — |
| srm660c/mccusker_default/+3.00%/0.5c_s3 | silent | partial capture | 0.0447 | no | 0.9290 | True | False | 2.95e-05 | — |
| srm660c/mccusker_default/+3.00%/full | error | partial capture | 0.00297 | no | 0.8615 | False | True | 0.986 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-1.50%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/mccusker_default/-3.00%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+1.50%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+3.00%/0.1c_s2 | silent | partial capture | 0.0522 | no | 0.9637 | True | False | 3.8e-06 | — |
| srm660c/protocol/+3.00%/0.1c_s3 | silent | partial capture | 0.102 | no | 0.9626 | True | False | 4.31e-08 | — |
| srm660c/protocol/+3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/+3.00%/0.5c_s2 | silent | partial capture | 0.108 | no | 0.9288 | True | False | 2.1e-10 | — |
| srm660c/protocol/+3.00%/0.5c_s3 | silent | other | 0.842 | no | 0.9226 | True | False | 3.23e-17 | — |
| srm660c/protocol/+3.00%/full | error | partial capture | 0.00293 | no | 0.8614 | False | True | 0.994 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-1.50%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-1.50%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-1.50%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-1.50%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-1.50%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-1.50%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-1.50%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-3.00%/0.1c_s1 | error | full collapse | 0 | yes | 0.9662 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-3.00%/0.1c_s2 | error | full collapse | 0 | yes | 0.9675 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-3.00%/0.1c_s3 | error | full collapse | 0 | yes | 0.9673 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-3.00%/0.5c_s1 | error | full collapse | 0 | yes | 0.9348 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-3.00%/0.5c_s2 | error | full collapse | 0 | yes | 0.9350 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-3.00%/0.5c_s3 | error | full collapse | 0 | yes | 0.9319 | False | True | 1 | MODEL_FAR_FROM_DATA |
| srm660c/protocol/-3.00%/full | error | full collapse | 0 | yes | 0.8616 | False | True | 1 | MODEL_FAR_FROM_DATA |

