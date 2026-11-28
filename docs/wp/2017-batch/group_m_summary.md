# WP-2017 group M: the two starts with and without the closing stage

Written by `group_m.py summary` from the raw rows of the workstation run; families and arms in its docstring.
Commit `ec68ea97e`, Linux x86_64, numpy 2.5.3, rietx-kernels 1.5.0, compiled tier on, one kernel thread.

Every fit. `closing`: the protocol's closing stage (1e-3); `none`: `closing_window_tol=None`. Biso rows: refined Biso rows in the answer (0 = the start is the answer). Reference: cell distance in ppm (plain esd), cpd-1a's fractions minus the weighed (wt %), the synthetic's weight against its truth.

| Family | Closing | Arm | last stage | Rwp | evals | status | Biso rows | λ/2 weight refined | harmonics declared | reference |
|---|---|---|---|---|---|---|---|---|---|---|
| `fap` | closing | b05 | closing | 0.092829 | 48 | converged | 7 | — | 0 | 0.a +84 ppm (19.20); 0.c +84 ppm (15.17) |
| `fap` | closing | b15 | closing | 0.092829 | 52 | converged | 7 | — | 0 | 0.a +84 ppm (19.20); 0.c +84 ppm (15.17) |
| `fap` | closing | noise | closing | 0.092829 | 48 | converged | 7 | — | 0 | 0.a +84 ppm (19.20); 0.c +84 ppm (15.17) |
| `fap` | none | b05 | biso | 0.092498 | 39 | converged | 7 | — | 0 | 0.a +83 ppm (18.83); 0.c +82 ppm (14.96) |
| `fap` | none | b15 | biso | 0.092509 | 43 | converged | 7 | — | 0 | 0.a +82 ppm (18.79); 0.c +82 ppm (14.94) |
| `fap` | none | noise | biso | 0.092498 | 39 | converged | 7 | — | 0 | 0.a +83 ppm (18.83); 0.c +82 ppm (14.96) |
| `nac` | closing | b05 | closing | 0.092877 | 47 | converged | 8 | — | 0 | 0.a +21 ppm (43.89); 1.a +281 ppm (179.77) |
| `nac` | closing | b15 | closing | 0.092877 | 47 | converged | 8 | — | 0 | 0.a +21 ppm (43.89); 1.a +281 ppm (179.77) |
| `nac` | closing | noise | closing | 0.092877 | 47 | converged | 8 | — | 0 | 0.a +21 ppm (43.89); 1.a +281 ppm (179.77) |
| `nac` | none | b05 | biso | 0.093170 | 40 | converged | 8 | — | 0 | 0.a +21 ppm (43.75); 1.a +281 ppm (179.33) |
| `nac` | none | b15 | biso | 0.093170 | 40 | converged | 8 | — | 0 | 0.a +21 ppm (43.74); 1.a +281 ppm (179.33) |
| `nac` | none | noise | biso | 0.093170 | 40 | converged | 8 | — | 0 | 0.a +21 ppm (43.75); 1.a +281 ppm (179.33) |
| `cpd1a` | closing | b05 | closing | 0.163051 | 168 | converged | 6 | — | 0 | corundum +0.57, zincite -0.69, fluorite +0.12 |
| `cpd1a` | closing | b15 | closing | 0.163425 | 170 | converged | 6 | — | 0 | corundum +0.55, zincite -0.60, fluorite +0.05 |
| `cpd1a` | closing | noise | closing | 0.163051 | 168 | converged | 6 | — | 0 | corundum +0.57, zincite -0.69, fluorite +0.12 |
| `cpd1a` | none | b05 | biso | 0.167591 | 154 | converged | 6 | — | 0 | corundum +0.44, zincite -0.73, fluorite +0.29 |
| `cpd1a` | none | b15 | biso | 0.168033 | 157 | converged | 6 | — | 0 | corundum +0.47, zincite -0.63, fluorite +0.16 |
| `cpd1a` | none | noise | biso | 0.167591 | 154 | converged | 6 | — | 0 | corundum +0.44, zincite -0.73, fluorite +0.29 |
| `lab6` | closing | b05 | closing | 0.087431 | 75 | converged | 2 | — | 0 | 0.a +25 ppm (19.08) |
| `lab6` | closing | b15 | closing | 0.087431 | 77 | converged | 2 | — | 0 | 0.a +25 ppm (19.56) |
| `lab6` | closing | noise | closing | 0.087431 | 75 | converged | 2 | — | 0 | 0.a +25 ppm (19.08) |
| `lab6` | none | b05 | biso | 0.087515 | 68 | converged | 2 | — | 0 | 0.a +25 ppm (19.56) |
| `lab6` | none | b15 | biso | 0.087520 | 68 | converged | 2 | — | 0 | 0.a +25 ppm (19.17) |
| `lab6` | none | noise | biso | 0.087515 | 68 | converged | 2 | — | 0 | 0.a +25 ppm (19.56) |
| `harm0` | closing | s0.001 | closing | 0.032453 | 55 | converged | 2 | yes | 1 | weight 0.00008±0.00011 (0.73 esd from 0) |
| `harm0` | closing | s0.01 | closing | 0.032453 | 61 | converged | 2 | yes | 1 | weight 0.00008±0.00011 (0.74 esd from 0) |
| `harm0` | closing | s0.3 | closing | 0.032453 | 165 | converged | 2 | yes | 1 | weight 0.00008±0.00011 (0.72 esd from 0) |
| `harm0` | closing | noise | closing | 0.032453 | 61 | converged | 2 | yes | 1 | weight 0.00008±0.00011 (0.74 esd from 0) |
| `harm0` | none | s0.001 | harmonic | 0.032971 | 51 | converged | 2 | yes | 1 | weight 0.00005±0.00011 (0.44 esd from 0) |
| `harm0` | none | s0.01 | harmonic | 0.033017 | 57 | converged | 2 | yes | 1 | weight 0.00006±0.00011 (0.55 esd from 0) |
| `harm0` | none | s0.3 | harmonic | 0.033334 | 162 | converged | 2 | yes | 1 | weight 0.00008±0.00011 (0.77 esd from 0) |
| `harm0` | none | noise | harmonic | 0.033017 | 57 | converged | 2 | yes | 1 | weight 0.00006±0.00011 (0.55 esd from 0) |
| `harm0.003` | closing | s0.001 | closing | 0.032263 | 55 | converged | 2 | yes | 1 | weight 0.00314±0.00012 (1.20 esd from 0.003) |
| `harm0.003` | closing | s0.01 | closing | 0.032263 | 59 | converged | 2 | yes | 1 | weight 0.00314±0.00012 (1.20 esd from 0.003) |
| `harm0.003` | closing | s0.3 | closing | 0.032263 | 137 | converged | 2 | yes | 1 | weight 0.00314±0.00012 (1.19 esd from 0.003) |
| `harm0.003` | closing | noise | closing | 0.032263 | 59 | converged | 2 | yes | 1 | weight 0.00314±0.00012 (1.20 esd from 0.003) |
| `harm0.003` | none | s0.001 | harmonic | 0.032802 | 52 | converged | 2 | yes | 1 | weight 0.00311±0.00012 (0.89 esd from 0.003) |
| `harm0.003` | none | s0.01 | harmonic | 0.032813 | 56 | converged | 2 | yes | 1 | weight 0.00312±0.00012 (1.02 esd from 0.003) |
| `harm0.003` | none | s0.3 | harmonic | 0.033137 | 134 | converged | 2 | yes | 1 | weight 0.00315±0.00012 (1.24 esd from 0.003) |
| `harm0.003` | none | noise | harmonic | 0.032813 | 56 | converged | 2 | yes | 1 | weight 0.00312±0.00012 (1.02 esd from 0.003) |
| `harm0.05` | closing | s0.001 | closing | 0.030938 | 53 | converged | 2 | yes | 1 | weight 0.05050±0.00023 (2.19 esd from 0.05) |
| `harm0.05` | closing | s0.01 | closing | 0.030938 | 58 | converged | 2 | yes | 1 | weight 0.05050±0.00023 (2.20 esd from 0.05) |
| `harm0.05` | closing | s0.3 | closing | 0.030938 | 94 | converged | 2 | yes | 1 | weight 0.05050±0.00023 (2.20 esd from 0.05) |
| `harm0.05` | closing | noise | closing | 0.030938 | 58 | converged | 2 | yes | 1 | weight 0.05050±0.00023 (2.20 esd from 0.05) |
| `harm0.05` | none | s0.001 | harmonic | 0.031585 | 50 | converged | 2 | yes | 1 | weight 0.05047±0.00023 (2.05 esd from 0.05) |
| `harm0.05` | none | s0.01 | harmonic | 0.031477 | 55 | converged | 2 | yes | 1 | weight 0.05041±0.00023 (1.79 esd from 0.05) |
| `harm0.05` | none | s0.3 | harmonic | 0.031752 | 91 | converged | 2 | yes | 1 | weight 0.05058±0.00023 (2.53 esd from 0.05) |
| `harm0.05` | none | noise | harmonic | 0.031477 | 55 | converged | 2 | yes | 1 | weight 0.05041±0.00023 (1.79 esd from 0.05) |

The start's reach, per closing setting: the other start (Biso 1.5; seeds 0.001 and 0.3) against the shipped one (Biso 0.5; seed 0.01), in plain esd over the larger esd on every row that is not a background coefficient, S/L and H/L ordered (0.1 bar); `noise` the nudged twin against shipped; `closing's move` the shipped start without the closing stage against with it; `start test` what `tests/test_staged_start_invariance.py` reads under the closing stage.

| Family | Closing | other start(s) | noise | closing's move | codes that differ | start test |
|---|---|---|---|---|---|---|
| `fap` | closing | b15: 2.78e-05 `phases.0.lor_strain` | 1.45e-06 | — | — | 0.000 |
| `fap` | none | b15: 0.119 `phases.0.atoms.1.biso` | 7.03e-07 | 0.912 `phases.0.lor_size` | — | — |
| `nac` | closing | b15: 3.14e-06 `phases.1.cell.a` | 2.14e-06 | — | — | 0.000 |
| `nac` | none | b15: 0.00838 `instrument.profile.x` | 1.97e-06 | 0.158 `instrument.profile.x` | — | — |
| `cpd1a` | closing | b15: 15.6 `phases.2.lor_strain` | 1.41e-06 | — | — | 15.68 (xfail) |
| `cpd1a` | none | b15: 14.8 `phases.2.lor_strain` | 4.79e-07 | 0.895 `phases.1.scale` | — | — |
| `lab6` | closing | b15: 0.00933 `instrument.profile.x` | 7.26e-07 | — | — | <= 0.1 |
| `lab6` | none | b15: 0.199 `phases.0.atoms.0.biso` | 6.23e-07 | 0.214 `instrument.profile.x` | — | — |
| `harm0` | closing | s0.001: 0.00192 `instrument.source.lines.1.weight`; s0.3: 0.0144 `instrument.source.lines.1.weight` | 5.87e-07 | — | BACKGROUND_ABSORPTION, HIGH_CORRELATION | <= 0.003 |
| `harm0` | none | s0.001: 0.42 `phases.0.atoms.1.biso`; s0.3: 1.15 `phases.0.atoms.1.biso` | 4.43e-07 | 1.14 `phases.0.atoms.1.biso` | BACKGROUND_ABSORPTION, CONSTRAINT_ACTIVE, FROZEN_COMPILE_STALE, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE | — |
| `harm0.003` | closing | s0.001: 0.000775 `instrument.profile.x`; s0.3: 0.0151 `instrument.source.lines.1.weight` | 4.41e-07 | — | BACKGROUND_ABSORPTION, HIGH_CORRELATION | <= 0.003 |
| `harm0.003` | none | s0.001: 0.264 `phases.0.atoms.1.biso`; s0.3: 0.691 `phases.0.atoms.1.biso` | 4.36e-07 | 0.813 `phases.0.atoms.1.biso` | BACKGROUND_ABSORPTION, CONSTRAINT_ACTIVE, FROZEN_COMPILE_STALE, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE | — |
| `harm0.05` | closing | s0.001: 0.00369 `instrument.source.lines.1.weight`; s0.3: 0.00376 `instrument.zero_shift` | 4.55e-07 | — | — | <= 0.003 |
| `harm0.05` | none | s0.001: 0.99 `phases.0.atoms.1.biso`; s0.3: 1.44 `phases.0.scale` | 4.42e-07 | 1.54 `phases.0.scale` | CONSTRAINT_ACTIVE, FROZEN_COMPILE_STALE | — |

Figures: `tests/output/wp2017_groupM_<family>_<closing>_<arm>.png`.
