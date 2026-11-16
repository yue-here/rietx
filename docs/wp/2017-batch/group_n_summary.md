# WP-2017 group N: the four hand rows

Written by `group_n.py summary` from the raw rows of the workstation run; claims, fits and arms in its docstring.
Commit `7a738a47b`, Linux x86_64, numpy 2.5.3, rietx-kernels 1.5.0, compiled tier on, one kernel thread.

Every comparison: the arm against the shipped arm in plain esd over the larger esd, every row that is not a background coefficient, S/L and H/L ordered (0.1 bar); `noise` the nudged twin of shipped.

## (1) The Le Bail/Pawley intensity seed

| Family | Mode | Arm | Rwp | evals | status | compiles rewritten | reflections rewritten | against x1 | codes that differ |
|---|---|---|---|---|---|---|---|---|---|
| `fap` | lebail | x1 | 0.101080 | 49 | converged | 0 | 0 | — | — |
| `fap` | lebail | x0.01 | 0.101080 | 49 | converged | 7 | 2303 | 2.57e-06 `instrument.profile.v` | — |
| `fap` | lebail | x100 | 0.101080 | 49 | converged | 7 | 2303 | 3.92e-06 `instrument.profile.v` | — |
| `fap` | lebail | shaped | 0.101080 | 49 | converged | 7 | 2303 | 6.54e-05 `instrument.profile.u` | — |
| `fap` | lebail | noise | 0.101080 | 49 | converged | 0 | 0 | 3.31e-05 `phases.0.cell.c` | — |
| `fap` | pawley | x1 | 0.078624 | 41 | converged | 0 | 0 | — | — |
| `fap` | pawley | x0.01 | 0.078624 | 41 | converged | 6 | 1974 | 1.95e-07 `instrument.profile.u` | — |
| `fap` | pawley | x100 | 0.078624 | 41 | converged | 6 | 1974 | 1.36e-07 `instrument.profile.u` | — |
| `fap` | pawley | shaped | 0.078624 | 41 | converged | 6 | 1974 | 0.000138 `instrument.profile.u` | — |
| `fap` | pawley | noise | 0.078624 | 51 | converged | 0 | 0 | 1.75e-06 `instrument.profile.u` | — |
| `nac` | lebail | x1 | 0.143459 | 41 | converged | 0 | 0 | — | — |
| `nac` | lebail | x0.01 | 0.143459 | 41 | converged | 6 | 774 | 1.02e-08 `instrument.zero_shift` | — |
| `nac` | lebail | x100 | 0.143459 | 41 | converged | 6 | 774 | 3.98e-08 `instrument.zero_shift` | — |
| `nac` | lebail | shaped | 0.143459 | 41 | converged | 6 | 774 | 2.44e-07 `instrument.profile.y` | — |
| `nac` | lebail | noise | 0.143459 | 41 | converged | 0 | 0 | 1.4e-06 `phases.0.cell.a` | — |
| `nac` | pawley | x1 | 0.134787 | 49 | converged | 0 | 0 | — | — |
| `nac` | pawley | x0.01 | 0.134787 | 49 | converged | 5 | 645 | 5.4e-08 `instrument.zero_shift` | — |
| `nac` | pawley | x100 | 0.134787 | 49 | converged | 5 | 645 | 1.25e-08 `instrument.profile.y` | — |
| `nac` | pawley | shaped | 0.134787 | 49 | converged | 5 | 645 | 5.53e-08 `instrument.zero_shift` | — |
| `nac` | pawley | noise | 0.134787 | 49 | converged | 0 | 0 | 1.39e-06 `phases.0.cell.a` | — |
| `lab6` | lebail | x1 | 0.094993 | 78 | converged | 0 | 0 | — | — |
| `lab6` | lebail | x0.01 | 0.094993 | 78 | converged | 7 | 210 | 0 `None` (bit-identical) | — |
| `lab6` | lebail | x100 | 0.094993 | 78 | converged | 7 | 210 | 0 `None` (bit-identical) | — |
| `lab6` | lebail | shaped | 0.094993 | 78 | converged | 7 | 210 | 9.13e-08 `instrument.profile.u` | — |
| `lab6` | lebail | noise | 0.094993 | 78 | converged | 0 | 0 | 6.11e-07 `phases.0.cell.a` | — |
| `lab6` | pawley | x1 | 0.092650 | 75 | converged | 0 | 0 | — | — |
| `lab6` | pawley | x0.01 | 0.092650 | 75 | converged | 6 | 180 | 4.97e-08 `instrument.profile.v` | — |
| `lab6` | pawley | x100 | 0.092650 | 75 | converged | 6 | 180 | 4.97e-08 `instrument.profile.v` | — |
| `lab6` | pawley | shaped | 0.092650 | 75 | converged | 6 | 180 | 9.57e-08 `instrument.zero_shift` | — |
| `lab6` | pawley | noise | 0.092650 | 75 | converged | 0 | 0 | 7.15e-07 `phases.0.cell.a` | — |

## (2) `refine._FLAT_AXIS_TEST_DIRECTIONS`

Held: the last stage's held rows. Flat axis: the stage record's axis (crystal axes); angle: between this arm's axis and shipped's. Spy: `_flat_rotation_axis` calls and the pairs it read (control: the arm's pair must be among them). The patterns are noise-free, so an esd here is a rounding-scale number (1e-18 to 1e-13): the moment rows' largest absolute change (rad, μ_B) rides beside the esd reading.

| Case | Arm | Rwp | evals | status | held | flat axis | angle to shipped's (°) | turned | spy calls | spy saw arm's pair | against shipped |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `rh` | shipped | 0.000000 | 15 | converged | dof2 | (-0.4449, -0.4449, -0.4449) | 0 | 1 | 4 | True | — |
| `rh` | rot30 | 0.000000 | 15 | converged | dof2 | (-0.4449, -0.4449, -0.4449) | 0 | 1 | 4 | True | 0.00589 `phases.0.atoms.0.moment.dof1`; moment rows Δ ≤ 1.8e-15 |
| `rh` | rng | 0.000000 | 15 | converged | dof2 | (-0.4449, -0.4449, -0.4449) | 0 | 1 | 4 | True | 0.0103 `phases.0.atoms.0.moment.dof1`; moment rows Δ ≤ 1.6e-15 |
| `rh` | noise | 0.000000 | 15 | converged | dof2 | (-0.4449, -0.4449, -0.4449) | 0 | 1 | 4 | True | 0.00432 `phases.0.scale`; moment rows Δ ≤ 8.9e-16 |
| `tet` | shipped | 0.000000 | 17 | converged | dof2 | — | — | 0 | 0 | no call | — |
| `tet` | rot30 | 0.000000 | 17 | converged | dof2 | — | — | 0 | 0 | no call | 0 `None` (bit-identical); moment rows Δ ≤ 0.0e+00 |
| `tet` | rng | 0.000000 | 17 | converged | dof2 | — | — | 0 | 0 | no call | 0 `None` (bit-identical); moment rows Δ ≤ 0.0e+00 |
| `tet` | noise | 0.000000 | 17 | converged | dof2 | — | — | 0 | 0 | no call | 24.8 `phases.0.atoms.0.moment.dof1`; moment rows Δ ≤ 2.2e-16 |
| `joint` | shipped | 0.000000 | 14 | converged | dof2 | (-0.4449, -0.4449, -0.4449) | 0 | 1 | 4 | True | — |
| `joint` | rot30 | 0.000000 | 14 | converged | dof2 | (-0.4449, -0.4449, -0.4449) | 1.5e-06 | 1 | 4 | True | 0.00916 `hist.1.phases.0.scale`; moment rows Δ ≤ 2.2e-16 |
| `joint` | rng | 0.000000 | 14 | converged | dof2 | (-0.4449, -0.4449, -0.4449) | 0 | 1 | 4 | True | 0.0215 `phases.0.atoms.0.moment.dof1`; moment rows Δ ≤ 8.9e-16 |
| `joint` | noise | 0.000000 | 14 | converged | dof2 | (-0.4449, -0.4449, -0.4449) | 0 | 1 | 4 | True | 0.0143 `phases.0.atoms.0.moment.dof1`; moment rows Δ ≤ 8.9e-16 |

## (3) `arpls`'s `max_iter` and `tol`

Baseline move: the largest |arm − shipped| / σ over the fitted channels at each λ a caller passes (1e7 = `PEAK_MASK_BASELINE_LAMBDA` and the default; `auto_lambda`'s and `select_arpls_lambda`'s shipped picks). Mask flips: channels `peak_mask` moves between background and peak. λ picks and `auto_background`'s pick: shipped → arm.

| Pattern | Arm | kwdefaults read | baseline move (σ) at λ | mask flips / background channels | `auto_lambda` | `select_arpls_lambda` | `auto_background` pick |
|---|---|---|---|---|---|---|---|
| `fap` | shipped | 50, 0.001 | 1e+04: 0; 1e+07: 0; 1e+10: 0 | 0 / 3155 | 1e+10 → 1e+10 | 1e+04 → 1e+04 | same |
| `fap` | tight | 500, 1e-06 | 1e+04: 0.133; 1e+07: 0.00649; 1e+10: 0.0132 | 0 / 3155 | 1e+10 → 1e+10 | 1e+04 → 1e+04 | same |
| `fap` | loose | 10, 0.01 | 1e+04: 2.99; 1e+07: 0.351; 1e+10: 5.43 | 37 / 3155 | 1e+10 → 1e+10 | 1e+04 → 1e+04 | same |
| `nac` | shipped | 50, 0.001 | 1e+06: 0; 1e+07: 0; 1e+10: 0 | 0 / 17587 | 1e+10 → 1e+10 | 1e+06 → 1e+06 | same |
| `nac` | tight | 500, 1e-06 | 1e+06: 0.0123; 1e+07: 0.0095; 1e+10: 0.00166 | 1 / 17587 | 1e+10 → 1e+10 | 1e+06 → 1e+06 | same |
| `nac` | loose | 10, 0.01 | 1e+06: 0.33; 1e+07: 0.543; 1e+10: 0.00781 | 18 / 17587 | 1e+10 → 1e+10 | 1e+06 → 1e+06 | same |
| `cpd1a` | shipped | 50, 0.001 | 1e+07: 0; 1e+08: 0; 1e+10: 0 | 0 / 6258 | 1e+10 → 1e+10 | 1e+08 → 1e+08 | same |
| `cpd1a` | tight | 500, 1e-06 | 1e+07: 0.0361; 1e+08: 0.0407; 1e+10: 0.0132 | 0 / 6258 | 1e+10 → 1e+10 | 1e+08 → 1e+08 | same |
| `cpd1a` | loose | 10, 0.01 | 1e+07: 0.0791; 1e+08: 0.481; 1e+10: 0.222 | 3 / 6258 | 1e+10 → 1e+10 | 1e+08 → 1e+08 | same |
| `lab6` | shipped | 50, 0.001 | 1e+05: 0; 1e+07: 0; 1e+10: 0 | 0 / 2692 | 1e+10 → 1e+10 | 1e+05 → 1e+05 | same |
| `lab6` | tight | 500, 1e-06 | 1e+05: 4.59; 1e+07: 0.00947; 1e+10: 0.00512 | 0 / 2692 | 1e+10 → 1e+10 | 1e+05 → 1e+05 | same |
| `lab6` | loose | 10, 0.01 | 1e+05: 6.09; 1e+07: 0.777; 1e+10: 0.285 | 29 / 2692 | 1e+10 → 1e+10 | 1e+05 → 1e+05 | same |
| `si640c` | shipped | 50, 0.001 | 1e+07: 0; 1e+08: 0; 1e+10: 0 | 0 / 45263 | 1e+10 → 1e+10 | 1e+08 → 1e+08 | same |
| `si640c` | tight | 500, 1e-06 | 1e+07: 0.00365; 1e+08: 0.00435; 1e+10: 0.0368 | 1 / 45263 | 1e+10 → 1e+10 | 1e+08 → 1e+08 | same |
| `si640c` | loose | 10, 0.01 | 1e+07: 0.0305; 1e+08: 0.0339; 1e+10: 0.28 | 3 / 45263 | 1e+10 → 1e+10 | 1e+08 → 1e+08 | same |
| `srm1976a` | shipped | 50, 0.001 | 1e+07: 0; 1e+10: 0 | 0 / 10017 | 1e+10 → 1e+10 | 1e+10 → 1e+10 | same |
| `srm1976a` | tight | 500, 1e-06 | 1e+07: 0.0105; 1e+10: 0.00138 | 0 / 10017 | 1e+10 → 1e+10 | 1e+10 → 1e+10 | same |
| `srm1976a` | loose | 10, 0.01 | 1e+07: 0.0734; 1e+10: 0.0143 | 0 / 10017 | 1e+10 → 1e+10 | 1e+10 → 1e+10 | same |

## (4) `params.vector.FLOOR_SEEDS`

Floor reads: `least_squares` reads of the table during the fit (control: 0 means the arm measured nothing). Width esd ratio: the arm's plain esd over shipped's on the rows whose unit is in the table (the Caglioti terms, X, Y and the sample widths), smallest and largest.

| Family | Arm | Rwp | evals | status | floor reads | against shipped | width esd ratio (min, max) | codes that differ |
|---|---|---|---|---|---|---|---|---|
| `fap` | shipped | 0.092829 | 49 | converged | 117 | — | — | — |
| `fap` | x10 | 0.092829 | 49 | converged | 117 | 0 `None` (bit-identical) | 1.0000, 1.0000 | — |
| `fap` | d10 | 0.092829 | 49 | converged | 117 | 0 `None` (bit-identical) | 1.0000, 1.0000 | — |
| `fap` | noise | 0.092829 | 49 | converged | 117 | 1.71e-06 `instrument.geometry.axial_sl` | 1.0000, 1.0000 | — |
| `nac` | shipped | 0.092877 | 46 | converged | 147 | — | — | — |
| `nac` | x10 | 0.092877 | 46 | converged | 147 | 1.57e-07 `phases.0.atoms.2.biso` | 1.0000, 1.0000 | — |
| `nac` | d10 | 0.092877 | 46 | converged | 147 | 3.26e-07 `phases.0.atoms.5.biso` | 1.0000, 1.0000 | — |
| `nac` | noise | 0.092877 | 46 | converged | 147 | 2.1e-06 `phases.0.cell.a` | 1.0000, 1.0000 | — |
| `cpd1a` | shipped | 0.163072 | 175 | converged | 254 | — | — | — |
| `cpd1a` | x10 | 0.163072 | 175 | converged | 254 | 2.44e-06 `phases.2.cell.a` | 0.9681, 10.0060 | — |
| `cpd1a` | d10 | 0.163072 | 175 | converged | 254 | 2.12e-06 `instrument.geometry.sample_displacement` | 0.0835, 1.0022 | — |
| `cpd1a` | noise | 0.163072 | 175 | converged | 254 | 4.75e-06 `instrument.geometry.axial_sl` | 0.9585, 1.0004 | — |
| `lab6` | shipped | 0.087431 | 76 | converged | 120 | — | — | — |
| `lab6` | x10 | 0.087431 | 76 | converged | 120 | 1.98e-07 `instrument.geometry.axial_sl` | 1.0000, 1.0000 | — |
| `lab6` | d10 | 0.087431 | 76 | converged | 120 | 2.78e-07 `instrument.geometry.axial_sl` | 1.0000, 1.0000 | — |
| `lab6` | noise | 0.087431 | 76 | converged | 120 | 5.79e-07 `phases.0.cell.a` | 1.0000, 1.0000 | — |
