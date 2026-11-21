# WP-2017 group J: Le Bail and Pawley refining the Kα2/Kα1 weight

Written by `group_j.py summary` from the raw rows of the workstation run; families and arms in its docstring.
Commit `fc2d89c6d`, Linux x86_64, numpy 2.5.3, rietx-kernels 1.5.0, compiled tier on, one kernel thread.

Weight: the refined Kα2/Kα1 with its reported (plain) esd; `vs 0.5` in reported esds. `vs Rietveld`: combined σ = √(e₁² + e₂²) of the reported esds, then over the larger. `free−held`: largest cell shift, weight free against held in that mode, in plain esd over the larger (0.1 bar); `noise`: the free arm against its nudged twin, same measure.

| Family | Mode | weight | vs 0.5 | vs Rietveld | free−held cell | noise | Rwp free / held | evals | codes |
|---|---|---|---|---|---|---|---|---|---|
| `lab6` | rietveld | 0.5125 ± 0.0048 (0.0017) | 2.62 | — | 0.375 `phases.0.cell.a` | 5.79e-07 | 0.08743 / 0.08788 | 76 | — |
| `lab6` | lebail | 0.5133 ± 0.0029 (0.0012) | 4.60 | 0.13σ (0.15) | 0.592 `phases.0.cell.a` | 9.13e-07 | 0.07934 / 0.08000 | 75 | — |
| `lab6` | pawley | 0.5146 ± 0.0036 (0.0015) | 4.00 | 0.34σ (0.42) | 0.535 `phases.0.cell.a` | 3.5e-07 | 0.07900 / 0.07967 | 86 | PAWLEY_OVERLAP_UNRESOLVED |
| `fap` | rietveld | 0.4757 ± 0.006 (0.0028) | 4.06 | — | 0.325 `phases.0.cell.a` | 6.68e-07 | 0.09222 / 0.09283 | 58 | — |
| `fap` | lebail | 0.4609 ± 0.0047 (0.002) | 8.24 | 1.93σ (2.47) | 0.068 `phases.0.cell.c` | 0.000477 | 0.09959 / 0.10254 | 53 | — |
| `fap` | pawley | 0.4750 ± 0.0046 (0.0026) | 5.38 | 0.08σ (0.10) | 0.351 `phases.0.cell.a` | 4.03e-06 | 0.08066 / 0.08135 | 59 | PAWLEY_OVERLAP_UNRESOLVED |
| `srm1976a` | rietveld | 0.4753 ± 0.011 (0.0025) | 2.32 | — | 0 `None` | 0 | 0.11378 / 0.11421 | 142 | FLOOR_HIT |
| `srm1976a` | lebail | 0.4430 ± 0.0039 (0.0015) | 14.51 | 2.84σ (3.03) | 0 `None` | 0 | 0.09187 / 0.09208 | 128 | — |
| `srm1976a` | pawley | 0.4755 ± 0.0047 (0.0019) | 5.27 | 0.01σ (0.02) | 0 `None` | 0 | 0.08231 / 0.08288 | 134 | PAWLEY_OVERLAP_UNRESOLVED |

Positive arm, SRM 660c against WP-2002 (2026-10-20):

| Mode | WP-2002 | here |
|---|---|---|
| rietveld | 0.5126 ± 0.0048 | 0.5125 ± 0.0048 |
| lebail | 0.5224 ± 0.0033 | 0.5133 ± 0.0029 |
| pawley | 0.5145 ± 0.0036 | 0.5146 ± 0.0036 |

Figures: `tests/output/wp2017_groupJ_<family>_<arm>.png`.
