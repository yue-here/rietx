# WP-2017 group I: the position bounds' removal on three flat plates

Written by `group_i.py summary` from the raw rows of the workstation run; families, ranges and arms in its docstring.
Commit `7dbbfced3`, Linux x86_64, numpy 2.5.3, rietx-kernels 1.5.0, compiled tier on, one kernel thread.

Narrow range: the 2θ at which the {1, cos θ, tan θ} Gram eigenvalue reaches NAC's capillary trio over 2-24°, 1.6e-05.

| Family | full | eig | narrow | eig |
|---|---|---|---|---|
| `fap` | 15.0-130.0° | 0.00013 | 15.0-70.6° | 1.6e-05 |
| `lab6` | 20.3-150.9° | 0.0017 | 20.3-84.6° | 1.6e-05 |
| `srm1976a` | 20.0-118.6° | 3.1e-05 | 20.0-90.4° | 1.6e-05 |

Cell: each cell row's distance from the reference in ppm, then in its own plain esd and in its reported (inflated) esd. Zero (°) and displacement (mm) with plain esds. `b−f`: largest shift of any non-background row, bounded against free, in plain esd over the larger esd (0.1 bar); `f−s` the same, free against shipped; `noise`: free against its nudged twin.

| Family | Range | Arm | Rwp | evals | cell ppm (esd) | zero | displacement | at old bound | codes |
|---|---|---|---|---|---|---|---|---|---|
| `fap` | full | shipped | 0.09283 | 49 | a +84 (19.20; 8.90); c +84 (15.17; 7.03) | held | +0.0688±0.00079 | — | — |
| `fap` | full | free | 0.09203 | 57 | a -424 (8.25; 3.78); c -427 (8.24; 3.77) | -0.1808±0.018 | -0.2539±0.033 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `fap` | full | bounded | 0.09203 | 57 | a -424 (8.25; 3.78); c -427 (8.24; 3.77) | -0.1808±0.018 | -0.2539±0.033 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `fap` | full | noise | 0.09203 | 57 | a -424 (8.25; 3.78); c -427 (8.24; 3.77) | -0.1808±0.018 | -0.2539±0.033 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `fap` | narrow | shipped | 0.08318 | 48 | a +79 (7.72; 3.88); c +84 (7.30; 3.66) | held | +0.0688±0.0013 | — | — |
| `fap` | narrow | free | 0.08270 | 61 | a -582 (4.94; 2.48); c -580 (4.90; 2.46) | -0.2476±0.044 | -0.3761±0.079 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `fap` | narrow | bounded | 0.08270 | 61 | a -582 (4.94; 2.48); c -580 (4.90; 2.46) | -0.2476±0.044 | -0.3761±0.079 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `fap` | narrow | noise | 0.08270 | 61 | a -582 (4.94; 2.48); c -580 (4.90; 2.46) | -0.2476±0.044 | -0.3761±0.079 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `lab6` | full | shipped | 0.08743 | 76 | a +25 (19.08; 6.78) | held | -0.0792±0.00044 | — | — |
| `lab6` | full | free | 0.08602 | 90 | a -23 (4.78; 1.76) | -0.0218±0.0021 | -0.1216±0.004 | — | HIGH_CORRELATION |
| `lab6` | full | bounded | 0.08602 | 90 | a -23 (4.78; 1.76) | -0.0218±0.0021 | -0.1216±0.004 | — | HIGH_CORRELATION |
| `lab6` | full | noise | 0.08602 | 90 | a -23 (4.78; 1.76) | -0.0218±0.0021 | -0.1216±0.004 | — | HIGH_CORRELATION |
| `lab6` | narrow | shipped | 0.09171 | 85 | a +16 (4.41; 1.68) | held | -0.0793±0.0007 | — | — |
| `lab6` | narrow | free | 0.08644 | 97 | a -984 (17.58; 6.48) | -0.3437±0.019 | -0.6899±0.034 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `lab6` | narrow | bounded | 0.08644 | 97 | a -984 (17.58; 6.48) | -0.3437±0.019 | -0.6899±0.034 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `lab6` | narrow | noise | 0.08644 | 97 | a -984 (17.58; 6.48) | -0.3437±0.019 | -0.6899±0.034 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `srm1976a` | full | shipped | 0.10722 | 112 | a +276 (36.40; 8.24); c +261 (38.37; 8.68) | held | -0.1036±0.0011 | — | — |
| `srm1976a` | full | free | 0.10705 | 124 | a -64 (1.12; 0.24); c -83 (1.44; 0.31) | -0.1197±0.02 | -0.3389±0.039 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `srm1976a` | full | bounded | 0.10705 | 124 | a -64 (1.12; 0.24); c -83 (1.44; 0.31) | -0.1197±0.02 | -0.3389±0.039 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `srm1976a` | full | noise | 0.10705 | 124 | a -64 (1.12; 0.24); c -83 (1.44; 0.31) | -0.1197±0.02 | -0.3389±0.039 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `srm1976a` | narrow | shipped | 0.09218 | 112 | a +334 (18.29; 4.55); c +318 (19.59; 4.88) | held | -0.1002±0.0014 | sample_transparency | FLOOR_HIT |
| `srm1976a` | narrow | free | 0.09213 | 136 | a -111 (0.49; 0.12); c -131 (0.58; 0.14) | -0.1409±0.065 | -0.3801±0.13 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `srm1976a` | narrow | bounded | 0.09213 | 122 | a -111 (0.49; 0.12); c -131 (0.58; 0.14) | -0.1409±0.065 | -0.3801±0.13 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `srm1976a` | narrow | noise | 0.09213 | 136 | a -111 (0.49; 0.12); c -131 (0.58; 0.14) | -0.1409±0.065 | -0.3801±0.13 | — | FLAT_DIRECTION, HIGH_CORRELATION |
| `nac` | full | shipped | 0.14010 | 39 | a +21 (28.32; 3.78) | -0.0002±9.3e-06 | held | — | — |
| `nac` | full | free | 0.13784 | 46 | a -5111 (15.36; 2.01) | -0.1231±0.0068 | +4.865±0.32, +2.124±0.12 | capillary_offset_along_beam, capillary_offset_across_beam | FLAT_DIRECTION, HIGH_CORRELATION |
| `nac` | full | bounded | 0.13827 | 46 | a -1097 (3.23; 0.42) | -0.0421±0.0069 | +1.000±0.33, +0.720±0.12 | capillary_offset_along_beam | BOUND_HIT, FLAT_DIRECTION, HIGH_CORRELATION |

`walk`: each cell row, free against shipped, in ppm and in the larger reported esd of the two (the reference page's claim is that the esd covers it).

| Family | Range | b−f | f−s | noise | walk | bounded reached |
|---|---|---|---|---|---|---|
| `fap` | full | 0 `None` | 9.91 `instrument.geometry.sample_displacement` | 1.69e-06 | a -508 (4.53); b -508 (4.53); c -510 (4.51) | unreached (bit-identical) |
| `fap` | narrow | 0 `None` | 5.64 `instrument.geometry.sample_displacement` | 1.84e-05 | a -661 (2.82); b -661 (2.82); c -664 (2.82) | unreached (bit-identical) |
| `lab6` | full | 0 `None` | 10.7 `instrument.geometry.sample_displacement` | 3.69e-07 | a -48 (3.62); b -48 (3.62); c -48 (3.62) | unreached (bit-identical) |
| `lab6` | narrow | 0 `None` | 17.9 `instrument.geometry.sample_displacement` | 2.77e-06 | a -1000 (6.58); b -1000 (6.58); c -1000 (6.58) | unreached (bit-identical) |
| `srm1976a` | full | 0 `None` | 6.05 `instrument.geometry.sample_displacement` | 1.39e-07 | a -340 (1.30); b -340 (1.30); c -344 (1.30) | unreached (bit-identical) |
| `srm1976a` | narrow | 4.63e-06 `phases.0.cell.a` | 2.14 `instrument.geometry.sample_displacement` | 5.29e-06 | a -444 (0.49); b -444 (0.49); c -449 (0.49) | no, but not identical |
| `nac` | full | 11.8 `phases.0.cell.a` | 18.2 `instrument.zero_shift` | — | a -5131 (2.02); b -5131 (2.02); c -5131 (2.02) | yes |

Figures: `tests/output/wp2017_groupI_<family>_<range>_<arm>.png`.
