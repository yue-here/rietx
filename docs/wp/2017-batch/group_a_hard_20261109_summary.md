# WP-2017 group A from hard starts, all ten constants, rerun 2026-11-09 (read from group_a_hard.jsonl)

head fabfe9b3f, rietx 1.12.0.dev0+gfabfe9b3f505, linux, 1 kernel thread per worker, compiled tier on, `[dev]`.

216 of 216 planned fits have a row, 1 of them an error or a timeout.

## Shipped constants from each start

'Reaches' is the family's shipped answer within 0.1 plain esd on every non-background row.  'Noise' is the 1e-12 arm against this row, in plain esd.

| start | reaches | to answer esd | path | Rwp | Rwp / answer | evaluations | noise esd | max r_u | max Q | max λ | rejected | longest stage | gate reads |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lab6_x1.01 | no | 307.5 | phases.0.scale | 0.861637 | 9.855103 | 9 | 0 | 0.984 | 0 | 0 | 0 | 2 | 0 |
| nac_x1.03 | no | 93.02 | phases.1.scale | 0.139436 | 1.501301 | 117 | 0.322 | 19.3 | 2 | 7.18 | 5 | 48 | 0 |
| lab6_x1.03 | no | 108.9 | phases.0.scale | 0.861381 | 9.852168 | 229 | 0.0534 | 26 | 1 | 33.3 | 38 | 108 | 0 |
| cpd1a_x1.01 | yes | 0.08194 | phases.2.lor_size | 0.163067 | 0.999969 | 270 | 4.67e-06 | 1.65 | 1 | 1e+04 | 5 | 155 | 3 |
| fap_x1.01 | yes | 2.164e-06 | instrument.geometry.axial_sl | 0.092829 | 1.000000 | 116 | 9.67e-07 | 1.09 | 1 | 0.0682 | 0 | 49 | 0 |
| nac_x1.01 | yes | 2.402e-07 | phases.0.atoms.2.biso | 0.092877 | 1.000000 | 565 | 2.83e-07 | 1.04 | 1 | 0.0214 | 0 | 374 | 0 |
| fap_x1.03 | yes | 4.264e-06 | instrument.geometry.axial_sl | 0.092829 | 1.000000 | 101 | 5.69e-07 | 1.22 | 2 | 1 | 5 | 33 | 0 |
| cpd1a_x1.03 | no | 41.53 | instrument.source.lines.1.weight | 0.367778 | 2.255307 | 314 | 7.29 | 324 | 2 | 1.37e+07 | 37 | 78 | 8 |
| cpd1a_zircon | yes | 0.06847 | phases.0.scale | 0.163050 | 0.999863 | 380 | 0.0245 | 153 | 2 | 1e+04 | 56 | 108 | 3 |

## Per constant

'Worst over noise' is the arm furthest from the same start's shipped arm among those past that start's noise arm.

| constant | starts reached | worst esd | noise there | arm | start | path | verdict changes | worst where shipped reaches, noise there |
|---|---|---|---|---|---|---|---|---|
| _M_HI | 4: cpd1a_x1.03, cpd1a_zircon, lab6_x1.03, nac_x1.03 | 2.375e+09 | 0.322 | 5.0 | nac_x1.03 | phases.0.atoms.5.biso | none | none |
| _M_LO | 8: cpd1a_x1.01, cpd1a_x1.03, cpd1a_zircon, fap_x1.01, fap_x1.03, lab6_x1.03, nac_x1.01, nac_x1.03 | 2.732e+05 | 0.322 | 0.8 | nac_x1.03 | phases.0.atoms.4.biso | none | 0.0247, 0.0245 (cpd1a_zircon 0.8) |
| _Q_TRIGGER | 0:  | none ||||| none | none |
| _Q_WINDOW | 0:  | none ||||| none | none |
| _LAMBDA_FAIL_FACTOR | 6: cpd1a_x1.01, cpd1a_x1.03, cpd1a_zircon, fap_x1.03, lab6_x1.03, nac_x1.03 | 7.688e+05 | 0.322 | 20.0 | nac_x1.03 | phases.0.atoms.5.biso | none | 6.92e-06, 4.67e-06 (cpd1a_x1.01 5.0) |
| _LAMBDA_FAIL_FLOOR | 6: cpd1a_x1.01, cpd1a_x1.03, cpd1a_zircon, fap_x1.03, lab6_x1.03, nac_x1.03 | 60.38 | 7.29 | 0.01 | cpd1a_x1.03 | phases.2.scale | none | 0.0253, 0.0245 (cpd1a_zircon 0.01) |
| _CONVERGED_RUNS | 8: cpd1a_x1.01, cpd1a_x1.03, cpd1a_zircon, fap_x1.01, fap_x1.03, lab6_x1.03, nac_x1.01, nac_x1.03 | 4.75e+06 | 0.322 | 2 | nac_x1.03 | phases.0.atoms.5.biso | none | 0.00112, 4.67e-06 (cpd1a_x1.01 2) |
| _CURVATURE_GATE | 0:  | none ||||| none | none |
| FTOL | 7: cpd1a_x1.01, cpd1a_x1.03, cpd1a_zircon, fap_x1.01, fap_x1.03, lab6_x1.03, nac_x1.01 | 0.1179 | 0.0534 | 1e-08 | lab6_x1.03 | instrument.geometry.axial_sl | none | 0.00123, 4.67e-06 (cpd1a_x1.01 1e-08) |
| SLOW_DESCENT_ESD | 2: cpd1a_zircon, lab6_x1.03 | none ||||| none | none |
| CELL_WINDOW | 0:  | none ||||| none | none |

## Starts whose shipped fit misses the answer

Esds on these answers can be huge or absent, so Rwp shows the scatter better.  One noise arm is one draw.

| start | shipped Rwp | noise Rwp | reached arms' Rwp | polished shipped | polished noise | polished arms |
|---|---|---|---|---|---|---|
| lab6_x1.01 | 0.8616 | 0.8616 | n/a | 0.8616 | n/a | n/a |
| nac_x1.03 | 0.1394 | 0.1394 | 0.1394 to 0.8089 | 0.1394 | 0.1394 | 0.1394 to 0.8024 |
| lab6_x1.03 | 0.8614 | 0.8614 | 0.8226 to 0.8616 | 0.8225 | n/a | 0.8225 to 0.8616 |
| cpd1a_x1.03 | 0.3678 | 0.3356 | 0.3268 to 0.8023 | 0.3666 | 0.3341 | 0.2949 to 0.8012 |

## Every arm

| start | constant | arm | model esd | noise esd | path | bkg esd | Rwp ratio | eval ratio | conv | reached | reaches answer | changed | ref further esd | ref name |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fap_x1.01 | _LAMBDA_FAIL_FACTOR | 5.0 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _Q_WINDOW | 5 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _Q_TRIGGER | 7 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _M_HI | 20.0 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _M_HI | 5.0 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _Q_TRIGGER | 3 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _M_LO | 0.8 | 6.356e-07 | 9.67e-07 | instrument.geometry.axial_sl | 6.981e-08 | 1.000000 | 1.000 | True | yes | yes | no | 0.000 | lx_gsas |
| fap_x1.01 | _Q_WINDOW | 20 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _M_LO | 0.2 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _LAMBDA_FAIL_FLOOR | 0.01 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _LAMBDA_FAIL_FLOOR | 1.0 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _LAMBDA_FAIL_FACTOR | 20.0 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _CONVERGED_RUNS | 2 | 0.000128 | 9.67e-07 | instrument.geometry.axial_sl | 7.394e-05 | 1.000000 | 0.957 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.01 | _CURVATURE_GATE | 30.0 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _CURVATURE_GATE | 1000.0 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | FTOL | 1e-08 | 9.23e-05 | 9.67e-07 | instrument.geometry.axial_sl | 9.311e-06 | 1.000000 | 0.991 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.01 | _CONVERGED_RUNS | 5 | 2.672e-06 | 9.67e-07 | instrument.geometry.axial_sl | 2.631e-07 | 1.000000 | 1.034 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.01 | SLOW_DESCENT_ESD | 0.5 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | SLOW_DESCENT_ESD | 2.0 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | SLOW_DESCENT_ESD | None | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | FTOL | 1e-10 | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | CELL_WINDOW | off | 0 | 9.67e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | noise | 1e-12 | 9.673e-07 | 9.67e-07 | instrument.geometry.axial_sl | 9.799e-08 | 1.000000 | 1.000 | True | yes | yes | no | 0.000 | lx_gsas |
| fap_x1.03 | _M_HI | 5.0 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _M_LO | 0.8 | 6.151e-08 | 5.69e-07 | phases.0.atoms.5.biso | 6.551e-09 | 1.000000 | 0.990 | True | yes | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _Q_TRIGGER | 3 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _M_HI | 20.0 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _Q_TRIGGER | 7 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _M_LO | 0.2 | 2.454e-06 | 5.69e-07 | instrument.geometry.axial_sl | 2.433e-07 | 1.000000 | 1.000 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.03 | _Q_WINDOW | 5 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _Q_WINDOW | 20 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 1.757e-06 | 5.69e-07 | instrument.geometry.axial_sl | 1.801e-07 | 1.000000 | 1.040 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 1.5e-06 | 5.69e-07 | instrument.geometry.axial_sl | 1.505e-07 | 1.000000 | 1.000 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 7.642e-07 | 5.69e-07 | instrument.geometry.axial_sl | 8.023e-08 | 1.000000 | 1.050 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 1.226e-05 | 5.69e-07 | phases.0.scale | 5.679e-05 | 1.000000 | 1.129 | True | yes | yes | no | 0.000 | lx_gsas |
| fap_x1.03 | _CONVERGED_RUNS | 2 | 9.708e-05 | 5.69e-07 | instrument.geometry.axial_sl | 9.783e-06 | 1.000000 | 0.931 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.03 | _CURVATURE_GATE | 1000.0 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | FTOL | 1e-08 | 9.719e-05 | 5.69e-07 | instrument.geometry.axial_sl | 9.805e-06 | 1.000000 | 0.980 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.03 | FTOL | 1e-10 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | SLOW_DESCENT_ESD | 2.0 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _CURVATURE_GATE | 30.0 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _CONVERGED_RUNS | 5 | 2.78e-07 | 5.69e-07 | instrument.geometry.axial_sl | 2.724e-08 | 1.000000 | 1.059 | True | yes | yes | no | 0.000 | lx_gsas |
| fap_x1.03 | SLOW_DESCENT_ESD | 0.5 | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| nac_x1.01 | _M_HI | 5.0 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| fap_x1.03 | noise | 1e-12 | 5.689e-07 | 5.69e-07 | instrument.geometry.axial_sl | 6.082e-08 | 1.000000 | 1.000 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.03 | SLOW_DESCENT_ESD | None | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | CELL_WINDOW | off | 0 | 5.69e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| nac_x1.01 | _M_HI | 20.0 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _M_LO | 0.8 | 6.247e-07 | 2.83e-07 | phases.0.atoms.5.biso | 4.848e-08 | 1.000000 | 1.000 | True | yes | yes | no | 0.000 | a_nac |
| nac_x1.01 | _M_LO | 0.2 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _Q_WINDOW | 20 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _Q_TRIGGER | 3 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _Q_WINDOW | 5 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _Q_TRIGGER | 7 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _LAMBDA_FAIL_FACTOR | 5.0 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _LAMBDA_FAIL_FACTOR | 20.0 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _LAMBDA_FAIL_FLOOR | 0.01 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _LAMBDA_FAIL_FLOOR | 1.0 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _CONVERGED_RUNS | 2 | 0.000374 | 2.83e-07 | phases.1.atoms.1.biso | 4.598e-06 | 1.000000 | 0.991 | True | yes | yes | no | -0.000 | a_nac |
| nac_x1.01 | _CONVERGED_RUNS | 5 | 0.000144 | 2.83e-07 | phases.1.atoms.1.biso | 1.774e-06 | 1.000000 | 1.011 | True | yes | yes | no | 0.000 | a_caf2 |
| nac_x1.01 | _CURVATURE_GATE | 30.0 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _CURVATURE_GATE | 1000.0 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | FTOL | 1e-08 | 0.0003737 | 2.83e-07 | phases.1.atoms.1.biso | 4.593e-06 | 1.000000 | 0.996 | True | yes | yes | no | -0.000 | a_nac |
| nac_x1.01 | FTOL | 1e-10 | 0.0001442 | 2.83e-07 | phases.1.atoms.1.biso | 1.775e-06 | 1.000000 | 1.004 | True | yes | yes | no | 0.000 | a_caf2 |
| nac_x1.03 | _M_LO | 0.2 | 0.3221 | 0.322 | phases.1.scale | 0.01883 | 0.999987 | 1.282 | True | yes | no | no | 0.001 | a_nac |
| nac_x1.01 | SLOW_DESCENT_ESD | 2.0 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | SLOW_DESCENT_ESD | 0.5 | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | SLOW_DESCENT_ESD | None | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | CELL_WINDOW | off | 0 | 2.83e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | noise | 1e-12 | 2.83e-07 | 2.83e-07 | phases.0.atoms.4.biso | 2.665e-08 | 1.000000 | 1.000 | True | yes | yes | no | -0.000 | a_caf2 |
| nac_x1.03 | _Q_TRIGGER | 3 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _Q_TRIGGER | 7 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _Q_WINDOW | 5 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _Q_WINDOW | 20 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 0.2418 | 0.322 | phases.1.scale | 0.04057 | 0.999928 | 1.111 | True | yes | no | no | -0.007 | a_nac |
| nac_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 0.4341 | 0.322 | phases.1.scale | 0.01277 | 1.000005 | 1.222 | True | yes | no | no | -0.000 | a_nac |
| nac_x1.03 | _CURVATURE_GATE | 1000.0 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _CURVATURE_GATE | 30.0 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | FTOL | 1e-08 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | FTOL | 1e-10 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | SLOW_DESCENT_ESD | 0.5 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | SLOW_DESCENT_ESD | None | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | SLOW_DESCENT_ESD | 2.0 | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | CELL_WINDOW | off | 0 | 0.322 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | noise | 1e-12 | 0.3221 | 0.322 | phases.1.scale | 0.01882 | 0.999987 | 1.333 | True | yes | no | no | 0.001 | a_nac |
| nac_x1.03 | _CONVERGED_RUNS | 2 | 4.75e+06 | 0.322 | phases.0.atoms.5.biso | 9.804 | 5.754753 | 3.248 | True | yes | no | no | 221.810 | a_nac |
| nac_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 7.688e+05 | 0.322 | phases.0.atoms.5.biso | 9.804 | 5.754753 | 3.735 | True | yes | no | no | 221.854 | a_nac |
| nac_x1.03 | _M_HI | 20.0 | 3.49e+05 | 0.322 | phases.0.atoms.4.biso | 9.825 | 5.667071 | 5.282 | True | yes | no | no | 525.796 | a_nac |
| nac_x1.03 | _M_LO | 0.8 | 2.732e+05 | 0.322 | phases.0.atoms.4.biso | 9.831 | 5.692928 | 5.256 | True | yes | no | no | 178.844 | a_nac |
| cpd1a_x1.01 | _M_HI | 5.0 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _M_LO | 0.8 | 0.0001672 | 4.67e-06 | instrument.profile.v | 7.279e-06 | 1.000000 | 1.026 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _M_HI | 20.0 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _M_LO | 0.2 | 2.437e-06 | 4.67e-06 | phases.2.cell.a | 1.716e-07 | 1.000000 | 0.996 | True | yes | yes | no | 0.000 | wt_corundum |
| nac_x1.03 | _M_HI | 5.0 | 2.375e+09 | 0.322 | phases.0.atoms.5.biso | 9.803 | 5.754753 | 8.453 | True | yes | no | no | 223.014 | a_nac |
| cpd1a_x1.01 | _Q_TRIGGER | 3 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _Q_TRIGGER | 7 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _Q_WINDOW | 5 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _LAMBDA_FAIL_FACTOR | 5.0 | 6.922e-06 | 4.67e-06 | instrument.geometry.axial_sl | 6.648e-07 | 1.000000 | 1.004 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _Q_WINDOW | 20 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| nac_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 1.579e+05 | 0.322 | phases.0.atoms.4.biso | 10.09 | 5.739986 | 7.615 | False | yes | no | no | 177.011 | a_nac |
| cpd1a_x1.01 | _LAMBDA_FAIL_FACTOR | 20.0 | 3.645e-06 | 4.67e-06 | instrument.geometry.sample_displacement | 1.405e-07 | 1.000000 | 0.996 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _CONVERGED_RUNS | 2 | 0.001119 | 4.67e-06 | instrument.profile.v | 0.0001556 | 1.000001 | 0.970 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_x1.01 | _LAMBDA_FAIL_FLOOR | 0.01 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.004 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _LAMBDA_FAIL_FLOOR | 1.0 | 0 | 4.67e-06 | None | 0 | 1.000000 | 0.996 | True | yes | yes | no | 0.000 | wt_corundum |
| nac_x1.03 | _CONVERGED_RUNS | 5 | 8.471e+05 | 0.322 | phases.0.atoms.5.biso | 9.476 | 5.800992 | 7.803 | False | yes | no | no | 146.441 | a_nac |
| cpd1a_x1.01 | _CONVERGED_RUNS | 5 | 0.0005199 | 4.67e-06 | phases.0.atoms.0.biso | 0.0001242 | 1.000000 | 1.052 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _CURVATURE_GATE | 30.0 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _CURVATURE_GATE | 1000.0 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | FTOL | 1e-08 | 0.001235 | 4.67e-06 | phases.0.scale | 0.0003126 | 1.000000 | 0.978 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_x1.01 | FTOL | 1e-10 | 0.0006295 | 4.67e-06 | phases.0.atoms.0.biso | 0.0001537 | 1.000000 | 1.011 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | SLOW_DESCENT_ESD | 0.5 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | SLOW_DESCENT_ESD | 2.0 | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | SLOW_DESCENT_ESD | None | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | CELL_WINDOW | off | 0 | 4.67e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | noise | 1e-12 | 4.674e-06 | 4.67e-06 | instrument.geometry.axial_sl | 3.491e-07 | 1.000000 | 1.000 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _M_LO | 0.2 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 21.72 | 7.29 | phases.2.atoms.0.biso | 5.083 | 1.235482 | 0.889 | True | yes | no | no | -0.396 | wt_fluorite |
| cpd1a_x1.03 | _M_HI | 20.0 | 8.807 | 7.29 | phases.2.atoms.0.biso | 0.3199 | 0.891637 | 1.092 | True | yes | no | no | -0.016 | wt_fluorite |
| cpd1a_x1.03 | _Q_TRIGGER | 3 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _Q_WINDOW | 5 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _Q_TRIGGER | 7 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _Q_WINDOW | 20 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 8.594 | 7.29 | phases.2.atoms.0.biso | 0.321 | 0.888617 | 0.959 | True | yes | no | no | -0.023 | wt_fluorite |
| cpd1a_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 60.38 | 7.29 | phases.2.scale | 5.267 | 2.178563 | 1.506 | True | yes | no | no | 0.509 | wt_zincite |
| cpd1a_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 6.927 | 7.29 | phases.2.atoms.0.biso | 0.2516 | 0.918350 | 1.000 | True | yes | no | no | -0.012 | wt_fluorite |
| cpd1a_x1.03 | _CONVERGED_RUNS | 5 | 18.42 | 7.29 | phases.1.scale | 4.733 | 1.186540 | 1.089 | True | yes | no | no | 0.262 | wt_zincite |
| cpd1a_x1.03 | _CURVATURE_GATE | 30.0 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| lab6_x1.01 | _M_HI | 5.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _M_HI | 20.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| cpd1a_x1.03 | _CURVATURE_GATE | 1000.0 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| lab6_x1.01 | _M_LO | 0.2 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _M_LO | 0.8 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _Q_TRIGGER | 3 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _Q_TRIGGER | 7 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _Q_WINDOW | 5 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _Q_WINDOW | 20 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| cpd1a_x1.03 | SLOW_DESCENT_ESD | 2.0 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | SLOW_DESCENT_ESD | None | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| lab6_x1.01 | _LAMBDA_FAIL_FACTOR | 5.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _LAMBDA_FAIL_FACTOR | 20.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| cpd1a_x1.03 | FTOL | 1e-10 | 0.1722 | 7.29 | instrument.geometry.sample_displacement | 0.0552 | 0.999883 | 1.010 | True | yes | no | no | -0.001 | wt_zincite |
| lab6_x1.01 | _LAMBDA_FAIL_FLOOR | 0.01 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| cpd1a_x1.03 | SLOW_DESCENT_ESD | 0.5 | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| lab6_x1.01 | _LAMBDA_FAIL_FLOOR | 1.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| cpd1a_x1.03 | FTOL | 1e-08 | 0.2843 | 7.29 | instrument.geometry.sample_displacement | 0.4226 | 1.000419 | 1.038 | True | yes | no | no | -0.041 | wt_fluorite |
| lab6_x1.01 | _CURVATURE_GATE | 1000.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _CONVERGED_RUNS | 2 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _CONVERGED_RUNS | 5 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | FTOL | 1e-08 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _CURVATURE_GATE | 30.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | FTOL | 1e-10 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | SLOW_DESCENT_ESD | 0.5 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | SLOW_DESCENT_ESD | 2.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | SLOW_DESCENT_ESD | None | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | CELL_WINDOW | off | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | noise | 1e-12 | 0 | 0 | None | 1.905e-13 | 1.000000 | 1.000 | True | yes | no | no | n/a | None |
| cpd1a_x1.03 | _CONVERGED_RUNS | 2 | 23.68 | 7.29 | instrument.source.lines.1.weight | 1.519 | 1.745561 | 1.427 | True | yes | no | no | -0.037 | wt_fluorite |
| cpd1a_x1.03 | CELL_WINDOW | off | 0 | 7.29 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| lab6_x1.03 | _M_LO | 0.8 | 0.3172 | 0.0534 | instrument.source.lines.1.weight | 0.01656 | 1.000011 | 0.424 | True | yes | no | no | 0.039 | disp_spec |
| cpd1a_x1.03 | noise | 1e-12 | 7.287 | 7.29 | phases.2.atoms.0.biso | 0.2581 | 0.912560 | 0.831 | True | yes | no | no | -0.014 | wt_fluorite |
| lab6_x1.03 | _M_HI | 5.0 | 0.0192 | 0.0534 | instrument.profile.w | 0.01629 | 1.000008 | 0.983 | True | yes | no | no | 0.000 | disp_spec |
| lab6_x1.03 | _Q_TRIGGER | 3 | 0 | 0.0534 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _Q_WINDOW | 5 | 0 | 0.0534 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _Q_WINDOW | 20 | 0 | 0.0534 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _M_LO | 0.2 | 0.1113 | 0.0534 | instrument.source.lines.1.weight | 0.02086 | 0.999996 | 1.135 | True | yes | no | no | 0.028 | disp_spec |
| lab6_x1.03 | _M_HI | 20.0 | 0.001901 | 0.0534 | instrument.source.lines.1.weight | 0.0003628 | 1.000000 | 1.057 | True | yes | no | no | 0.000 | disp_spec |
| lab6_x1.03 | _Q_TRIGGER | 7 | 0 | 0.0534 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 0.1094 | 0.0534 | instrument.source.lines.1.weight | 0.005419 | 1.000001 | 0.974 | True | yes | no | no | 0.015 | disp_spec |
| lab6_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 16.89 | 0.0534 | instrument.geometry.sample_displacement | 2.4 | 0.954933 | 0.856 | True | yes | no | no | 16.890 | disp_spec |
| lab6_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 0.1544 | 0.0534 | instrument.source.lines.1.weight | 0.009781 | 0.999985 | 0.943 | True | yes | no | no | 0.112 | disp_spec |
| lab6_x1.03 | FTOL | 1e-08 | 0.1179 | 0.0534 | instrument.geometry.axial_sl | 0.0316 | 1.000008 | 0.686 | True | yes | no | no | 0.038 | a_cert |
| lab6_x1.03 | _CURVATURE_GATE | 1000.0 | 0 | 0.0534 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _CURVATURE_GATE | 30.0 | 0 | 0.0534 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _CONVERGED_RUNS | 5 | 0.3786 | 0.0534 | instrument.source.lines.1.weight | 0.008049 | 0.999997 | 1.122 | True | yes | no | no | 0.218 | disp_spec |
| lab6_x1.03 | SLOW_DESCENT_ESD | 0.5 | 0.01504 | 0.0534 | instrument.source.lines.1.weight | 0.004433 | 0.999999 | 0.991 | True | yes | no | no | 0.001 | a_cert |
| lab6_x1.03 | FTOL | 1e-10 | 0.001879 | 0.0534 | instrument.source.lines.1.weight | 0.0002815 | 1.000000 | 1.114 | True | yes | no | no | -0.000 | a_cert |
| lab6_x1.03 | _CONVERGED_RUNS | 2 | 51.39 | 0.0534 | instrument.source.lines.1.weight | 0.3015 | 1.000298 | 1.218 | True | yes | no | no | 24.737 | disp_spec |
| lab6_x1.03 | noise | 1e-12 | 0.05343 | 0.0534 | instrument.source.lines.1.weight | 0.001881 | 1.000000 | 0.773 | True | yes | no | no | 0.011 | a_cert |
| lab6_x1.03 | SLOW_DESCENT_ESD | 2.0 | 0.005764 | 0.0534 | instrument.source.lines.1.weight | 0.001198 | 1.000000 | 0.921 | True | yes | no | no | -0.000 | a_cert |
| lab6_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 135.9 | 0.0534 | instrument.source.lines.1.weight | 0.3015 | 1.000298 | 1.611 | True | yes | no | no | 26.833 | disp_spec |
| lab6_x1.03 | CELL_WINDOW | off | 0 | 0.0534 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | SLOW_DESCENT_ESD | None | 0.01504 | 0.0534 | instrument.source.lines.1.weight | 0.004433 | 0.999999 | 0.991 | True | yes | no | no | 0.001 | a_cert |
| cpd1a_zircon | _M_LO | 0.2 | 0.0007926 | 0.0245 | phases.3.scale | 0.0001127 | 1.000000 | 0.808 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | _M_HI | 5.0 | 4.447e-05 | 0.0245 | phases.0.cell.c | 1.884e-05 | 1.000000 | 0.853 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _M_LO | 0.8 | 0.02467 | 0.0245 | instrument.profile.v | 0.00113 | 0.999976 | 0.908 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | _LAMBDA_FAIL_FACTOR | 5.0 | 0.0007384 | 0.0245 | phases.3.scale | 0.0001555 | 1.000000 | 0.868 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _M_HI | 20.0 | 3.516e-05 | 0.0245 | phases.2.atoms.1.biso | 1.694e-05 | 1.000000 | 0.921 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _Q_TRIGGER | 3 | 0 | 0.0245 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _Q_TRIGGER | 7 | 0 | 0.0245 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _Q_WINDOW | 20 | 0 | 0.0245 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _LAMBDA_FAIL_FACTOR | 20.0 | 0.02177 | 0.0245 | instrument.profile.v | 0.00103 | 0.999979 | 0.945 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | _Q_WINDOW | 5 | 0 | 0.0245 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _LAMBDA_FAIL_FLOOR | 0.01 | 0.02532 | 0.0245 | instrument.profile.v | 0.001062 | 0.999975 | 0.837 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | FTOL | 1e-08 | 0.001007 | 0.0245 | phases.0.atoms.0.biso | 0.000216 | 1.000000 | 0.813 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | _LAMBDA_FAIL_FLOOR | 1.0 | 0.0008129 | 0.0245 | phases.3.scale | 0.0001317 | 1.000000 | 1.032 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | _CONVERGED_RUNS | 2 | 0.01563 | 0.0245 | instrument.profile.v | 0.000523 | 1.000015 | 0.984 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _CONVERGED_RUNS | 5 | 0.02446 | 0.0245 | phases.2.lor_size | 0.000507 | 1.000013 | 1.079 | True | yes | yes | no | 0.000 | wt_zincite |
| cpd1a_zircon | _CURVATURE_GATE | 30.0 | 0 | 0.0245 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _CURVATURE_GATE | 1000.0 | 0 | 0.0245 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | SLOW_DESCENT_ESD | 0.5 | 0.0003136 | 0.0245 | phases.3.scale | 5.687e-05 | 1.000000 | 1.026 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | FTOL | 1e-10 | 0.0001649 | 0.0245 | phases.0.atoms.0.biso | 3.477e-05 | 1.000000 | 1.005 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | SLOW_DESCENT_ESD | 2.0 | 0.0004964 | 0.0245 | phases.3.scale | 7.089e-05 | 1.000000 | 0.979 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | SLOW_DESCENT_ESD | None | 4.057e-05 | 0.0245 | phases.2.atoms.1.biso | 2.086e-05 | 1.000000 | 1.053 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | CELL_WINDOW | off | 0 | 0.0245 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | noise | 1e-12 | 0.02454 | 0.0245 | phases.2.lor_size | 0.0005392 | 1.000013 | 1.013 | True | yes | yes | no | 0.000 | wt_zincite |
| cpd1a_x1.03 | _M_LO | 0.8 | 3.746e+04 | 7.29 | instrument.geometry.axial_sl | 4.478 | 2.181350 | 1.898 | True | yes | no | no | 0.649 | wt_zincite |
| cpd1a_x1.03 | _M_HI | 5.0 | error: FitTimeout: past 1200 s ||||||||| no | no |||

## Polish

35 polishes, 1 refused.

| start | constant | arm | to shipped | to shipped polished | path | bkg | S/S polished | to answer | S/S answer | rounds | settled |
|---|---|---|---|---|---|---|---|---|---|---|---|
| nac_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 0.4341 | 0.4341 | phases.1.scale | 0.01277 | 1.0000099 | 93.11 | 2.2539190 | 2 | True |
| nac_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 0.2418 | 0.2418 | phases.1.scale | 0.04057 | 0.9998565 | 185.3 | 2.2535732 | 2 | True |
| nac_x1.03 | _M_LO | 0.2 | 0.3212 | 0.3212 | phases.1.scale | 0.01881 | 0.9999750 | 94.36 | 2.2538403 | 2 | True |
| nac_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 7.688e+05 | 7.688e+05 | phases.0.atoms.5.biso | 9.803 | 33.1171831 | 1.155e+06 | 74.6427090 | 2 | True |
| nac_x1.03 | _CONVERGED_RUNS | 2 | 4.75e+06 | 4.75e+06 | phases.0.atoms.5.biso | 9.803 | 33.1171831 | 7.133e+06 | 74.6427090 | 2 | True |
| nac_x1.03 | _M_HI | 5.0 | 2.375e+09 | 2.375e+09 | phases.0.atoms.5.biso | 9.803 | 33.1171829 | 3.567e+09 | 74.6427086 | 2 | True |
| nac_x1.03 | noise | 1e-12 | 0.3225 | 0.3225 | phases.1.scale | 0.01882 | 0.9999750 | 94.4 | 2.2538403 | 2 | True |
| cpd1a_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 21.72 | 21.68 | phases.2.atoms.0.biso | 8.271 | 1.5359631 | 31.01 | 7.7642342 | 2 | True |
| nac_x1.03 | _M_HI | 20.0 | 3.49e+05 | 3.49e+05 | phases.0.atoms.4.biso | 9.837 | 32.1138746 | 5.24e+05 | 72.3813553 | 5 | True |
| nac_x1.03 | _CONVERGED_RUNS | 5 | 8.471e+05 | 8.471e+05 | phases.0.atoms.5.biso | 9.803 | 33.1171829 | 1.272e+06 | 74.6427085 | 3 | True |
| cpd1a_x1.03 | _M_HI | 20.0 | 8.625 | 9.266 | instrument.profile.v | 0.2978 | 0.7920017 | 49.33 | 4.0035380 | 5 | False |
| cpd1a_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 8.381 | 9.184 | instrument.profile.v | 0.2628 | 0.7863832 | 47.96 | 3.9751367 | 5 | False |
| cpd1a_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 6.774 | 7.32 | instrument.profile.v | 0.2449 | 0.8418438 | 47.35 | 4.2554877 | 5 | False |
| lab6_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 16.81 | 0.001029 | instrument.geometry.axial_sl | 0.0001907 | 1.0000000 | 76.5 | 88.4971768 | 2 | True |
| cpd1a_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 220.9 | 220.9 | instrument.profile.v | 8.653 | 4.7750416 | 236.7 | 24.1376510 | 5 | False |
| nac_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 8.7e+12 | 8.7e+12 | phases.0.atoms.4.biso | 10.09 | 32.9337804 | 1.306e+13 | 74.2293383 | 5 | False |
| lab6_x1.03 | _M_LO | 0.2 | 22.23 | 20.14 | instrument.geometry.sample_displacement | 2.738 | 1.0959828 | 305.7 | 96.9913868 | 2 | True |
| lab6_x1.03 | _CONVERGED_RUNS | 2 | 51.39 | 2390 | instrument.source.lines.1.weight | 2.627 | 1.0974723 | 5.879e+04 | 97.1232024 | 2 | True |
| lab6_x1.03 | _M_LO | 0.8 | 17.14 | 3.982 | phases.0.scale | 0.7663 | 1.0091255 | 470.8 | 89.3047597 | 5 | True |
| cpd1a_x1.03 | _CONVERGED_RUNS | 5 | 80.24 | 80.18 | phases.1.cell.c | 7.194 | 1.4000506 | 79.01 | 7.0772019 | 5 | True |
| cpd1a_x1.03 | FTOL | 1e-10 | 0.5142 | 0.224 | instrument.geometry.sample_displacement | 0.01399 | 0.9999781 | 41.53 | 5.0548507 | 5 | False |
| cpd1a_x1.03 | noise | 1e-12 | 7.113 | 7.724 | instrument.profile.v | 0.251 | 0.8303125 | 47.72 | 4.1971974 | 5 | False |
| lab6_x1.03 | _CONVERGED_RUNS | 5 | 0.7935 | 80.55 | phases.0.cell.a | 2.28 | 1.0967442 | 2.418e+04 | 97.0587683 | 5 | True |
| lab6_x1.01 | shipped | shipped | 0 | 0 | None | 0 | 1.0000000 | 307.5 | 97.1232024 | 2 | True |
| lab6_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 135.9 | 6268 | instrument.source.lines.1.weight | 2.658 | 1.0974723 | 1.546e+05 | 97.1232024 | 2 | True |
| nac_x1.03 | shipped | shipped | 3.176e-07 | 0 | None | 0 | 1.0000000 | 93.02 | 2.2538967 | 2 | True |
| lab6_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 1.642 | 70.07 | phases.0.cell.a | 2.399 | 1.0956657 | 867.3 | 96.9633171 | 5 | False |
| cpd1a_x1.03 | FTOL | 1e-08 | 0.5276 | 0.04245 | instrument.geometry.sample_displacement | 0.006682 | 0.9998459 | 41.51 | 5.0541824 | 5 | False |
| lab6_x1.03 | shipped | shipped | 16.81 | 0 | None | 0 | 1.0000000 | 76.51 | 88.4971761 | 3 | True |
| lab6_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 34.31 | 35.5 | instrument.geometry.sample_displacement | 2.552 | 1.0534861 | 305.8 | 93.2305489 | 5 | False |
| lab6_x1.03 | FTOL | 1e-08 | 1.046 | 75.92 | phases.0.cell.a | 2.467 | 1.0965900 | 225.3 | 97.0451165 | 5 | True |
| nac_x1.03 | _M_LO | 0.8 | 2.732e+05 | 2.732e+05 | phases.0.atoms.4.biso | 9.837 | 32.1138747 | 4.101e+05 | 72.3813556 | 5 | False |
| cpd1a_x1.03 | shipped | shipped | 0.5142 | 0 | None | 0 | 1.0000000 | 41.51 | 5.0549614 | 5 | False |
| cpd1a_x1.03 | _CONVERGED_RUNS | 2 | 27.85 | 27.85 | instrument.source.lines.1.weight | 3.219 | 0.6468649 | 35.32 | 3.2698773 | 5 | False |
