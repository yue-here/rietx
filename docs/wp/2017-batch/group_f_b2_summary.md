# WP-2017 group F part B: the second real hump, 11-BM LaB6 + cBN (mg2044)

Written by `group_f_b2.py summary`; the raw rows are not committed.

| arm | knot step | hump score (fit range) | trigger | Rwp | status | evals | largest shift vs blank | vs pick | codes |
|---|---|---|---|---|---|---|---|---|---|
| pick | 8.0 | 0.0276 | 0.05 | 0.17174 | converged | 46 | 1.82 instrument.profile.y | — | CAPILLARY_OFFSET_UNAVAILABLE, DISPERSION_NEGLECTED, HIGH_CORRELATION |
| knot_flip | 3.0 | 0.0276 | 0.02760111281950415 | 0.16925 | converged | 47 | 0.415 instrument.profile.y | 1.42 instrument.profile.y | CAPILLARY_OFFSET_UNAVAILABLE, DISPERSION_NEGLECTED, HIGH_CORRELATION |
| noise | 8.0 | 0.0276 | 0.05 | 0.17174 | converged | 46 | 1.82 instrument.profile.y | 1.11e-06 phases.1.cell.a | CAPILLARY_OFFSET_UNAVAILABLE, DISPERSION_NEGLECTED, HIGH_CORRELATION |
| blank | blank | nan | — | 0.16996 | converged | 48 | — | 1.82 instrument.profile.y | CAPILLARY_OFFSET_UNAVAILABLE, DISPERSION_NEGLECTED |

Per row, each arm against `blank` in plain esd over the larger esd:

| row | blank | pick | knot_flip | noise |
|---|---|---|---|---|
| phases.0.scale | 0.000209875(3.5e-07) | 0.000209829 (0.13) | 0.0002098 (0.21) | 0.000209829 (0.13) |
| phases.0.atoms.0.biso | 0.427393(0.0039) | 0.42529 (0.53) | 0.426774 (0.16) | 0.42529 (0.53) |
| phases.0.atoms.1.x | 0.198385(0.00043) | 0.198327 (0.13) | 0.198295 (0.21) | 0.198327 (0.13) |
| phases.0.atoms.1.dof.0 | -0.000515067(0.00043) | -0.000572904 (0.13) | -0.000605307 (0.21) | -0.000572904 (0.13) |
| phases.0.atoms.1.biso | 0.235319(0.026) | 0.241818 (0.25) | 0.236544 (0.05) | 0.241818 (0.25) |
| phases.1.cell.a | 3.61652(3.2e-06) | 3.61652 (0.07) | 3.61652 (0.06) | 3.61652 (0.07) |
| phases.1.cell.b | 3.61652(3.2e-06) | 3.61652 (0.07) | 3.61652 (0.06) | 3.61652 (0.07) |
| phases.1.cell.c | 3.61652(3.2e-06) | 3.61652 (0.07) | 3.61652 (0.06) | 3.61652 (0.07) |
| phases.1.scale | 0.0030224(1.1e-05) | 0.00301765 (0.42) | 0.00302406 (0.15) | 0.00301765 (0.42) |
| phases.1.atoms.0.biso | 0.489707(0.015) | 0.481289 (0.56) | 0.486865 (0.19) | 0.481289 (0.56) |
| phases.1.atoms.1.biso | 0.57518(0.019) | 0.564602 (0.56) | 0.574869 (0.02) | 0.564602 (0.56) |
| instrument.profile.x | 0.00254367(2.9e-05) | 0.00249578 (1.62) | 0.00253377 (0.34) | 0.00249578 (1.62) |
| instrument.profile.y | 0.0367972(0.00023) | 0.0372238 (1.82) | 0.0368928 (0.41) | 0.0372238 (1.82) |

Weight fractions (wt %): pick: LaB6 17.814(0.347), cBN 82.186(0.347); knot_flip: LaB6 17.781(0.321), cBN 82.219(0.321); noise: LaB6 17.814(0.347), cBN 82.186(0.347); blank: LaB6 17.794(0.316), cBN 82.206(0.316)
