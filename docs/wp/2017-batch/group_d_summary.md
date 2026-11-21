# WP-2017 group D: the joint solve's layout switch on three joint fits

Run at `bf012fbc5`, Linux x86_64, Python 3.12.14, numpy 2.5.3, rietx-kernels 1.5.0, 4 workers, compiled tier on, one kernel thread.  Written by `group_d.py summary`; fits, arms and reads in its docstring.

`DENSE_JACOBIAN_MAX_BYTES` = 268435456 (256 MiB).

## Each fit and arm

Shift: plain esd over the larger of the two arms' esds against `dense` (`_shift`), model rows and background rows; bar 0.1.  Solves: joint solves the spy saw, and the layouts they took.

| Fit | Arm | solves (layouts) | largest dense J (MiB) | Rwp | evaluations | status | model shift (row) | background shift | same codes as dense | wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| library20 | dense | 6 (dense) | 43.6 | 0.034825048 | 38 | converged | — | — | — | 3 |
| library20 | blocked | 6 (blocked) | 43.6 | 0.034825048 | 38 | converged | 8.49e-06 (`hist.18.instrument.profile.u`) | 0 | yes | 2 |
| library20 | rule | 6 (dense) | 43.6 | 0.034825048 | 38 | converged | 0 (`None`) | 0 | yes | 3 |
| library20 | noise | 6 (dense) | 43.6 | 0.034825048 | 38 | converged | 1.74e-05 (`hist.18.instrument.profile.u`) | 0 | yes | 3 |
| cpd1_joint | dense | 9 (dense) | 11.3 | 0.127174638 | 159 | converged | — | — | — | 13 |
| cpd1_joint | blocked | 9 (blocked) | 11.3 | 0.127174638 | 167 | converged | 3.61e-06 (`phases.2.lor_size`) | 0 | yes | 13 |
| cpd1_joint | rule | 9 (dense) | 11.3 | 0.127174638 | 159 | converged | 0 (`None`) | 0 | yes | 13 |
| cpd1_joint | noise | 9 (dense) | 11.3 | 0.127174638 | 159 | converged | 3.46e-06 (`phases.2.lor_size`) | 0 | yes | 13 |
| cucr_cold | dense | 6 (dense) | 110.0 | 0.222537206 | 250 | converged | — | — | — | 171 |
| cucr_cold | blocked | 6 (blocked) | 110.0 | 0.222537206 | 248 | converged | 0.00503 (`hist.4.phases.1.cell.b`) | 0 | yes | 155 |
| cucr_cold | rule | 6 (dense) | 110.0 | 0.222537206 | 250 | converged | 0 (`None`) | 0 | yes | 171 |
| cucr_cold | noise | 6 (dense) | 110.0 | 0.222537206 | 248 | converged | 0.00503 (`hist.4.phases.1.cell.b`) | 0 | yes | 167 |

## Esds against `dense`

The rows carrying an esd, and the largest relative difference in an esd between the arm and `dense` (the near-cut case `blocked.py`'s docstring names would show here as a different set).

| Fit | Arm | rows with an esd (dense) | same set | largest relative esd difference (row) |
|---|---|---|---|---|
| library20 | blocked | 264 (264) | yes | 2.88e-05 (`hist.18.instrument.profile.u`) |
| library20 | rule | 264 (264) | yes | 0 (`vars.a_3`) |
| library20 | noise | 264 (264) | yes | 4.39e-06 (`hist.18.instrument.profile.w`) |
| cpd1_joint | blocked | 72 (72) | yes | 0.07 (`hist.0.instrument.profile.w`) |
| cpd1_joint | rule | 72 (72) | yes | 0 (`phases.2.lor_strain`) |
| cpd1_joint | noise | 72 (72) | yes | 0.0849 (`hist.2.instrument.profile.w`) |
| cucr_cold | blocked | 161 (161) | yes | 0.000678 (`hist.6.phases.0.cell.c`) |
| cucr_cold | rule | 161 (161) | yes | 0 (`hist.6.phases.1.scale`) |
| cucr_cold | noise | 161 (161) | yes | 0.000574 (`hist.6.phases.0.cell.c`) |

## References, read beside the bar

- cucr_cold dense, coldest frame against Suchomel et al. (2012) Table I at 10 K: a -19 ppm, b +110 ppm, c -114 ppm
- library20 dense surface: 1 4.1647 ± 5e-06, x 0.010467 ± 1.5e-05, y 0.00820717 ± 1.8e-05, x*y 0.00404996 ± 7.5e-05
- cucr_cold blocked, coldest frame against Suchomel et al. (2012) Table I at 10 K: a -19 ppm, b +110 ppm, c -114 ppm
- library20 blocked surface: 1 4.1647 ± 5e-06, x 0.010467 ± 1.5e-05, y 0.00820717 ± 1.8e-05, x*y 0.00404996 ± 7.5e-05
