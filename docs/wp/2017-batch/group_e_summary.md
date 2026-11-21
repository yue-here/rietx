# WP-2017 group E: TRF's GTOL and XTOL, and the bound test's thresholds

Run at `998b47034`, Linux x86_64, Python 3.12.14, numpy 2.5.3, rietx-kernels 1.5.0, 4 workers, compiled tier on, one kernel thread, `solver="trf"` throughout.  Written by `group_e.py summary`; fits, arms and cases in its docstring.

## Part 1: each arm against its family's shipped TRF fit

Plain esd over the larger of the two arms' esds (`_shift`), bar 0.1.  Solves: TRF calls, and the scipy statuses they ended on (1 gtol, 2 ftol, 3 xtol, 4 ftol and xtol, 0 budget).

| Family | Arm | Rwp | evaluations (× shipped) | status | model shift (row) | background | unreached | solves: statuses | reference |
|---|---|---|---|---|---|---|---|---|---|
| cpd1a | shipped | 0.1630717 | 171 | converged | — | — | — | 2×9 | corundum +0.57, zincite -0.69, fluorite +0.12 wt % from weighed |
| cpd1a | gtol | 0.1630717 | 171 (1.00) | converged | 0 (`None`) | 0 | yes | 2×9 | corundum +0.57, zincite -0.69, fluorite +0.12 wt % from weighed |
| cpd1a | xtol | 0.1630717 | 171 (1.00) | converged | 0 (`None`) | 0 | yes | 2×9 | corundum +0.57, zincite -0.69, fluorite +0.12 wt % from weighed |
| cpd1a | both | 0.1630717 | 171 (1.00) | converged | 0 (`None`) | 0 | yes | 2×9 | corundum +0.57, zincite -0.69, fluorite +0.12 wt % from weighed |
| cpd1a | noise | 0.1630717 | 171 (1.00) | converged | 6.81e-06 (`phases.0.atoms.0.biso`) | 1.51e-06 | no | 2×9 | corundum +0.57, zincite -0.69, fluorite +0.12 wt % from weighed |
| corundum | shipped | 0.1457209 | 119 | converged | — | — | — | 2×7, 4×1 | — |
| corundum | gtol | 0.1457209 | 119 (1.00) | converged | 0 (`None`) | 0 | yes | 1×1, 2×7 | — |
| corundum | xtol | 0.1457209 | 119 (1.00) | converged | 0 (`None`) | 0 | yes | 2×7, 4×1 | — |
| corundum | both | 0.1457209 | 119 (1.00) | converged | 0 (`None`) | 0 | yes | 1×1, 2×7 | — |
| corundum | noise | 0.1457181 | 126 (1.06) | converged | 0.101 (`phases.0.microstrain.s004`) | 0.0423 | no | 2×7, 4×1 | — |
| si640c | shipped | 0.0823153 | 92 | converged | — | — | — | 2×5, 3×2 | λ -10.98 ppm from XND |
| si640c | gtol | 0.0823153 | 92 (1.00) | converged | 0 (`None`) | 0 | yes | 2×5, 3×2 | λ -10.98 ppm from XND |
| si640c | xtol | 0.0823153 | 83 (0.90) | converged | 0.00491 (`instrument.zero_shift`) | 4.06e-07 | no | 2×4, 3×3 | λ -10.99 ppm from XND |
| si640c | both | 0.0823153 | 83 (0.90) | converged | 0.00491 (`instrument.zero_shift`) | 4.06e-07 | no | 2×4, 3×3 | λ -10.99 ppm from XND |
| si640c | noise | 0.0823153 | 93 (1.01) | converged | 3.5e-06 (`instrument.source.lines.0.wavelength`) | 3.11e-08 | no | 2×4, 3×1, 4×2 | λ -10.98 ppm from XND |

## Part 2: issue #273's construction on cpd-1a under TRF

Bound 3 answer esds past the optimum (`bind`) or on the far side (`control`), start 1 esd inside it.  Gap: |value − limit| over the row's own esd, what `bound_findings` reads against `BOUND_HIT_ESD_FRAC` = 0.01; cosine against `BOUND_HIT_COS_MIN` = 0.0001.

| Case | path | mode | ftol | gap / esd | |cosine| | fired | at_bound | status (termination) | evaluations |
|---|---|---|---|---|---|---|---|---|---|
| fluorite_biso_min | `phases.2.atoms.0.biso` | bind | 1e-09 | 2.65e-15 | 0.165 | BOUND_HIT | True | converged (gtol) | 6 |
| fluorite_biso_min | `phases.2.atoms.0.biso` | bind | 1e-06 | 2.57e-10 | 0.165 | BOUND_HIT | True | converged (ftol) | 5 |
| fluorite_biso_min | `phases.2.atoms.0.biso` | bind | 0.0001 | 2.57e-10 | 0.165 | BOUND_HIT | True | converged (ftol) | 5 |
| fluorite_biso_min | `phases.2.atoms.0.biso` | bind | 0.001 | 3.06e-05 | 0.165 | BOUND_HIT | True | converged (ftol) | 4 |
| fluorite_biso_min | `phases.2.atoms.0.biso` | control | 1e-09 | 3.55 | 1.25e-09 | none | False | converged (ftol) | 6 |
| fluorite_biso_min | `phases.2.atoms.0.biso` | control | 1e-06 | 3.55 | 1.25e-09 | none | False | converged (ftol) | 6 |
| fluorite_biso_min | `phases.2.atoms.0.biso` | control | 0.0001 | 3.55 | 1.78e-05 | none | False | converged (ftol) | 5 |
| fluorite_biso_min | `phases.2.atoms.0.biso` | control | 0.001 | 3.58 | 0.00176 | none | False | converged (ftol) | 4 |
| zincite_biso_max | `phases.1.atoms.1.biso` | bind | 1e-09 | 1.13e-15 | 0.193 | BOUND_HIT | True | converged (gtol) | 7 |
| zincite_biso_max | `phases.1.atoms.1.biso` | bind | 1e-06 | 7.7e-10 | 0.193 | BOUND_HIT | True | converged (ftol) | 6 |
| zincite_biso_max | `phases.1.atoms.1.biso` | bind | 0.0001 | 7.7e-10 | 0.193 | BOUND_HIT | True | converged (ftol) | 6 |
| zincite_biso_max | `phases.1.atoms.1.biso` | bind | 0.001 | 5.74e-05 | 0.193 | BOUND_HIT | True | converged (ftol) | 5 |
| zincite_biso_max | `phases.1.atoms.1.biso` | control | 1e-09 | 3.96 | 2.89e-10 | none | False | converged (ftol) | 8 |
| zincite_biso_max | `phases.1.atoms.1.biso` | control | 1e-06 | 3.96 | 1.6e-07 | none | False | converged (ftol) | 7 |
| zincite_biso_max | `phases.1.atoms.1.biso` | control | 0.0001 | 3.96 | 4.64e-05 | none | False | converged (ftol) | 6 |
| zincite_biso_max | `phases.1.atoms.1.biso` | control | 0.001 | 4.07 | 0.00216 | none | False | converged (ftol) | 5 |
| fluorite_lor_size_max | `phases.2.lor_size` | bind | 1e-09 | 2.9e-16 | 0.419 | BOUND_HIT | True | converged (gtol) | 8 |
| fluorite_lor_size_max | `phases.2.lor_size` | bind | 1e-06 | 1.49e-13 | 0.419 | BOUND_HIT | True | converged (ftol) | 7 |
| fluorite_lor_size_max | `phases.2.lor_size` | bind | 0.0001 | 1.49e-13 | 0.419 | BOUND_HIT | True | converged (ftol) | 7 |
| fluorite_lor_size_max | `phases.2.lor_size` | bind | 0.001 | 1.09e-06 | 0.419 | BOUND_HIT | True | converged (ftol) | 6 |
| fluorite_lor_size_max | `phases.2.lor_size` | control | 1e-09 | 9.36 | 2.29e-10 | none | False | converged (ftol) | 10 |
| fluorite_lor_size_max | `phases.2.lor_size` | control | 1e-06 | 9.36 | 8.96e-08 | none | False | converged (ftol) | 9 |
| fluorite_lor_size_max | `phases.2.lor_size` | control | 0.0001 | 9.36 | 3.4e-05 | none | False | converged (ftol) | 8 |
| fluorite_lor_size_max | `phases.2.lor_size` | control | 0.001 | 9.36 | 3.4e-05 | none | False | converged (ftol) | 8 |
| zincite_scale_max | `phases.1.scale` | bind | 1e-09 | 3.92e-15 | 0.211 | BOUND_HIT | True | converged (gtol) | 6 |
| zincite_scale_max | `phases.1.scale` | bind | 1e-06 | 4.58e-10 | 0.211 | BOUND_HIT | True | converged (ftol) | 5 |
| zincite_scale_max | `phases.1.scale` | bind | 0.0001 | 4.58e-10 | 0.211 | BOUND_HIT | True | converged (ftol) | 5 |
| zincite_scale_max | `phases.1.scale` | bind | 0.001 | 4.61e-05 | 0.211 | BOUND_HIT | True | converged (ftol) | 4 |
| zincite_scale_max | `phases.1.scale` | control | 1e-09 | 4.11 | 1.59e-15 | none | False | converged (ftol) | 7 |
| zincite_scale_max | `phases.1.scale` | control | 1e-06 | 4.11 | 1.74e-08 | none | False | converged (ftol) | 6 |
| zincite_scale_max | `phases.1.scale` | control | 0.0001 | 4.11 | 5.69e-05 | none | False | converged (ftol) | 5 |
| zincite_scale_max | `phases.1.scale` | control | 0.001 | 4.18 | 0.00332 | none | False | converged (ftol) | 4 |
| zero_shift_max | `instrument.zero_shift` | bind | 1e-09 | 1.68e-14 | 0.472 | BOUND_HIT | True | converged (ftol) | 9 |
| zero_shift_max | `instrument.zero_shift` | bind | 1e-06 | 1.68e-14 | 0.472 | BOUND_HIT | True | converged (ftol) | 9 |
| zero_shift_max | `instrument.zero_shift` | bind | 0.0001 | 1.47e-09 | 0.472 | BOUND_HIT | True | converged (ftol) | 8 |
| zero_shift_max | `instrument.zero_shift` | bind | 0.001 | 1.47e-09 | 0.472 | BOUND_HIT | True | converged (ftol) | 8 |
| zero_shift_max | `instrument.zero_shift` | control | 1e-09 | 247 | 1.66e-08 | none | False | converged (ftol) | 12 |
| zero_shift_max | `instrument.zero_shift` | control | 1e-06 | 247 | 1.66e-08 | none | False | converged (ftol) | 12 |
| zero_shift_max | `instrument.zero_shift` | control | 0.0001 | 247 | 8.65e-06 | none | False | converged (ftol) | 11 |
| zero_shift_max | `instrument.zero_shift` | control | 0.001 | 247 | 8.65e-06 | none | False | converged (ftol) | 11 |

Binding cases: largest gap 5.7e-05 esd, margin 174× under the threshold (WP-1434: 13×); smallest |cosine| 0.17, 1.65e+03× above it (WP-1434: 150×).
Controls (free optima): largest |cosine| 0.0033, against the threshold 0.0001 (WP-1434's free optimum: 5e-10); controls at or over it, by ftol: 1e-09 0, 1e-06 0, 0.0001 0, 0.001 3.  None fired: the distance half held every one.
