# WP-2017 group C: the seven `bccg` constants on Pawley fits

Run at `174276095`, Linux x86_64, Python 3.12.14, numpy 2.5.3, rietx-kernels 1.5.0, 2/8 workers, compiled tier on, one kernel thread.  Written by `group_c.py summary`; arms and reads in its docstring.

## Each family's shipped fit

| Family | Pawley columns | Rwp | evaluations | stages converged | `projected_cg` calls (largest n) | `bccg.solve` calls | noise arm, plain esd (background) |
|---|---|---|---|---|---|---|---|
| fap | 329 | 0.0786244 | 41 | 6/6 | 37 (343) | 0 | 1.75e-06 (9.78e-07) |
| nac | 140 | 0.0751638 | 38 | 6/6 | 35 (154) | 0 | 2.52e-06 (1.87e-09) |
| cpd1a | 111 | 0.1643022 | 168 | 6/6 | 0 (0) | 0 | 2.21e-06 (3.62e-07) |

## Each arm against its family's shipped fit

Plain esd over the larger of the two arms' esds (`_shift`); `unreached` is bit-identical rows, Rwp and evaluations.  Reference: the arm's distance from the family's reference, shipped's in brackets, in the reference's unit.

| Constant | Arm | Family | Rwp | evaluations (× shipped) | model | background | unreached | `solve` calls | reference |
|---|---|---|---|---|---|---|---|---|---|
| `_PCG_TOL` | 1e-08 | fap | 0.0805851 | 42 (1.02) | 1.29 | 0.776 | no | 0 | a_gsas 4.24e-05 (4.84e-05); c_gsas 4.88e-05 (4.72e-06) |
| `_PCG_TOL` | 1e-08 | nac | 0.0751638 | 38 (1.00) | 1.22e-07 | 2.89e-09 | no | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_PCG_TOL` | 1e-08 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_PCG_TOL` | 1e-12 | fap | 0.0786278 | 60 (1.46) | 0.0256 | 0.103 | no | 0 | a_gsas 4.85e-05 (4.84e-05); c_gsas 4.84e-06 (4.72e-06) |
| `_PCG_TOL` | 1e-12 | nac | 0.0751638 | 38 (1.00) | 1.91e-07 | 3.85e-09 | no | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_PCG_TOL` | 1e-12 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_PCG_BUDGET_PER_VARIABLE` | 1 | fap | 0.0786248 | 43 (1.05) | 0.00698 | 0.0363 | no | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.76e-06 (4.72e-06) |
| `_PCG_BUDGET_PER_VARIABLE` | 1 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_PCG_BUDGET_PER_VARIABLE` | 1 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_PCG_BUDGET_PER_VARIABLE` | 4 | fap | 0.0786244 | 45 (1.10) | 1.54e-06 | 1e-06 | no | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_PCG_BUDGET_PER_VARIABLE` | 4 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_PCG_BUDGET_PER_VARIABLE` | 4 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_CAUCHY_ARMIJO` | 1e-05 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_CAUCHY_ARMIJO` | 1e-05 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_CAUCHY_ARMIJO` | 1e-05 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_CAUCHY_ARMIJO` | 0.001 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_CAUCHY_ARMIJO` | 0.001 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_CAUCHY_ARMIJO` | 0.001 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_CONVERGED_FRACTION` | 1e-05 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_CONVERGED_FRACTION` | 1e-05 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_CONVERGED_FRACTION` | 1e-05 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_CONVERGED_FRACTION` | 0.001 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_CONVERGED_FRACTION` | 0.001 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_CONVERGED_FRACTION` | 0.001 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_CONVERGED_RUNS` | 2 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_CONVERGED_RUNS` | 2 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_CONVERGED_RUNS` | 2 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_CONVERGED_RUNS` | 5 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_CONVERGED_RUNS` | 5 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_CONVERGED_RUNS` | 5 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_SMALL_FACTOR` | 100 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_SMALL_FACTOR` | 100 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_SMALL_FACTOR` | 100 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_SMALL_FACTOR` | 400 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_SMALL_FACTOR` | 400 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_SMALL_FACTOR` | 400 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_SMALL_RUNS` | 3 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_SMALL_RUNS` | 3 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_SMALL_RUNS` | 3 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |
| `_SMALL_RUNS` | 12 | fap | 0.0786244 | 41 (1.00) | 0 | 0 | yes | 0 | a_gsas 4.84e-05 (4.84e-05); c_gsas 4.72e-06 (4.72e-06) |
| `_SMALL_RUNS` | 12 | nac | 0.0751638 | 38 (1.00) | 0 | 0 | yes | 0 | a_nac 2.11e-04 (2.11e-04); a_caf2 1.47e-03 (1.47e-03) |
| `_SMALL_RUNS` | 12 | cpd1a | 0.1643022 | 168 (1.00) | 0 | 0 | yes | 0 | — |

Spy positive arm: 48 of 48 fits counted the extra `bccg.solve` call.
