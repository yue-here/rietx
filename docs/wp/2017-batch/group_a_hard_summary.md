# WP-2017 group A from hard starts, read from group_a_hard.jsonl

head 1ed7a9517, rietx 1.12.0.dev0, darwin, 1 kernel thread per worker, compiled tier on, `[dev]`.

153 of 153 planned fits have a row, 0 of them an error or a timeout.

## Shipped constants from each start

'Reaches' is the family's shipped answer within 0.1 plain esd on every non-background row.  'Noise' is the 1e-12 arm against this row, in plain esd.

| start | reaches | to answer esd | path | Rwp | Rwp / answer | evaluations | noise esd | max r_u | max Q | max λ | rejected | longest stage | gate reads |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nac_x1.03 | no | 93.11 | phases.1.scale | 0.139436 | 1.501308 | 149 | 2.31e-07 | 17.2 | 2 | 14.5 | 5 | 81 | 0 |
| nac_x1.01 | yes | 2.459e-07 | phases.0.atoms.4.biso | 0.092877 | 1.000000 | 565 | 2.12e-07 | 1.04 | 1 | 0.0208 | 0 | 374 | 0 |
| fap_x1.01 | yes | 6.559e-07 | instrument.geometry.axial_sl | 0.092829 | 1.000000 | 116 | 1.39e-06 | 1.09 | 1 | 0.0682 | 0 | 49 | 0 |
| lab6_x1.01 | no | 307.5 | phases.0.scale | 0.861637 | 9.855103 | 9 | 0 | 0.984 | 0 | 0 | 0 | 2 | 0 |
| fap_x1.03 | yes | 2.099e-06 | phases.0.atoms.5.biso | 0.092829 | 1.000000 | 101 | 2.85e-06 | 1.22 | 2 | 1 | 5 | 33 | 0 |
| cpd1a_x1.01 | yes | 0.0784 | phases.2.lor_size | 0.163067 | 0.999969 | 270 | 4.36e-06 | 1.65 | 1 | 1e+04 | 5 | 155 | 3 |
| lab6_x1.03 | no | 109.7 | phases.0.scale | 0.861380 | 9.852158 | 206 | 0.0942 | 35.8 | 1 | 33.3 | 33 | 107 | 0 |
| cpd1a_x1.03 | no | 171.9 | phases.0.cell.c | 0.621952 | 3.813967 | 585 | 3.99 | 18.3 | 1 | 1e+08 | 64 | 240 | 14 |
| cpd1a_zircon | yes | 0.06849 | phases.0.scale | 0.163050 | 0.999866 | 311 | 0.00547 | 12.9 | 2 | 1e+04 | 35 | 76 | 3 |

## Per constant

'Worst over noise' is the arm furthest from the same start's shipped arm among those past that start's noise arm.

| constant | starts reached | worst esd | noise there | arm | start | path | verdict changes | worst where shipped reaches, noise there |
|---|---|---|---|---|---|---|---|---|
| _M_HI | 4: cpd1a_x1.03, cpd1a_zircon, lab6_x1.03, nac_x1.03 | 7.586e+05 | 2.31e-07 | 20.0 | nac_x1.03 | phases.0.atoms.4.biso | none | none |
| _Q_TRIGGER | 0:  | none ||||| none | none |
| _Q_WINDOW | 0:  | none ||||| none | none |
| _LAMBDA_FAIL_FACTOR | 6: cpd1a_x1.01, cpd1a_x1.03, cpd1a_zircon, fap_x1.03, lab6_x1.03, nac_x1.03 | 1.009e+07 | 2.31e-07 | 5.0 | nac_x1.03 | phases.0.atoms.5.biso | none | 0.00844, 0.00547 (cpd1a_zircon 20.0) |
| _LAMBDA_FAIL_FLOOR | 6: cpd1a_x1.01, cpd1a_x1.03, cpd1a_zircon, fap_x1.03, lab6_x1.03, nac_x1.03 | 2.417e+09 | 2.31e-07 | 0.01 | nac_x1.03 | phases.0.atoms.5.biso | none | 1.25e-05, 2.85e-06 (fap_x1.03 1.0) |
| _CURVATURE_GATE | 0:  | none ||||| none | none |
| SLOW_DESCENT_ESD | 2: cpd1a_x1.03, lab6_x1.03 | none ||||| none | none |

## Starts whose shipped fit misses the answer

Esds on these answers can be huge or absent, so Rwp shows the scatter better.  One noise arm is one draw.

| start | shipped Rwp | noise Rwp | reached arms' Rwp | polished shipped | polished noise | polished arms |
|---|---|---|---|---|---|---|
| nac_x1.03 | 0.1394 | 0.1394 | 0.1394 to 0.8024 | 0.1394 | n/a | 0.1394 to 0.8024 |
| lab6_x1.01 | 0.8616 | 0.8616 | n/a | 0.8616 | n/a | n/a |
| lab6_x1.03 | 0.8614 | 0.8614 | 0.8227 to 0.8616 | 0.8586 | n/a | 0.8215 to 0.8616 |
| cpd1a_x1.03 | 0.6220 | 0.3650 | 0.2360 to 0.6911 | 0.3657 | 0.3641 | 0.2360 to 0.4544 |

## Every arm

| start | constant | arm | model esd | noise esd | path | bkg esd | Rwp ratio | eval ratio | conv | reached | reaches answer | changed | ref further esd | ref name |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fap_x1.01 | _M_HI | 20.0 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _Q_TRIGGER | 7 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _Q_TRIGGER | 3 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _M_HI | 5.0 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _Q_WINDOW | 5 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _LAMBDA_FAIL_FACTOR | 20.0 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _LAMBDA_FAIL_FACTOR | 5.0 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _Q_WINDOW | 20 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _LAMBDA_FAIL_FLOOR | 0.01 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _LAMBDA_FAIL_FLOOR | 1.0 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _CURVATURE_GATE | 30.0 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | _CURVATURE_GATE | 1000.0 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | SLOW_DESCENT_ESD | None | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | noise | 1e-12 | 1.393e-06 | 1.39e-06 | instrument.geometry.axial_sl | 1.437e-07 | 1.000000 | 1.000 | True | yes | yes | no | -0.000 | c_gsas |
| fap_x1.01 | SLOW_DESCENT_ESD | 0.5 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.01 | SLOW_DESCENT_ESD | 2.0 | 0 | 1.39e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _M_HI | 5.0 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _Q_TRIGGER | 3 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _M_HI | 20.0 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _Q_TRIGGER | 7 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _Q_WINDOW | 20 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _Q_WINDOW | 5 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 2.213e-06 | 2.85e-06 | instrument.geometry.axial_sl | 2.143e-07 | 1.000000 | 1.040 | True | yes | yes | no | 0.000 | lx_gsas |
| fap_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 1.747e-06 | 2.85e-06 | instrument.geometry.axial_sl | 1.741e-07 | 1.000000 | 1.050 | True | yes | yes | no | 0.000 | lx_gsas |
| fap_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 2.651e-07 | 2.85e-06 | instrument.geometry.axial_sl | 3.131e-08 | 1.000000 | 1.000 | True | yes | yes | no | 0.000 | lx_gsas |
| fap_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 1.25e-05 | 2.85e-06 | phases.0.scale | 5.689e-05 | 1.000000 | 1.129 | True | yes | yes | no | 0.000 | lx_gsas |
| fap_x1.03 | _CURVATURE_GATE | 30.0 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | _CURVATURE_GATE | 1000.0 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | SLOW_DESCENT_ESD | 0.5 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | SLOW_DESCENT_ESD | 2.0 | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | SLOW_DESCENT_ESD | None | 0 | 2.85e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_gsas |
| fap_x1.03 | noise | 1e-12 | 2.853e-06 | 2.85e-06 | instrument.geometry.axial_sl | 2.816e-07 | 1.000000 | 1.000 | True | yes | yes | no | 0.000 | lx_gsas |
| nac_x1.01 | _M_HI | 5.0 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _M_HI | 20.0 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _Q_TRIGGER | 3 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _Q_TRIGGER | 7 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _Q_WINDOW | 5 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _Q_WINDOW | 20 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _LAMBDA_FAIL_FACTOR | 5.0 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _LAMBDA_FAIL_FACTOR | 20.0 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _LAMBDA_FAIL_FLOOR | 0.01 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _LAMBDA_FAIL_FLOOR | 1.0 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _CURVATURE_GATE | 1000.0 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | _CURVATURE_GATE | 30.0 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | SLOW_DESCENT_ESD | 0.5 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | SLOW_DESCENT_ESD | 2.0 | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | SLOW_DESCENT_ESD | None | 0 | 2.12e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | a_nac |
| nac_x1.01 | noise | 1e-12 | 2.121e-07 | 2.12e-07 | phases.0.atoms.4.biso | 1.296e-08 | 1.000000 | 1.000 | True | yes | yes | no | -0.000 | a_caf2 |
| nac_x1.03 | _M_HI | 5.0 | 0.5706 | 2.31e-07 | phases.1.scale | 0.01394 | 0.999983 | 1.148 | True | yes | no | no | 0.002 | a_nac |
| nac_x1.03 | _Q_TRIGGER | 3 | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _Q_TRIGGER | 7 | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _Q_WINDOW | 5 | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _Q_WINDOW | 20 | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 1.009e+07 | 2.31e-07 | phases.0.atoms.5.biso | 9.801 | 5.754725 | 2.832 | True | yes | no | no | 222.673 | a_nac |
| nac_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 2.417e+09 | 2.31e-07 | phases.0.atoms.5.biso | 9.801 | 5.754725 | 2.128 | True | yes | no | no | 222.724 | a_nac |
| nac_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 541.8 | 2.31e-07 | instrument.zero_shift | 9.834 | 5.666883 | 2.470 | True | yes | no | no | 515.677 | a_nac |
| nac_x1.03 | _M_HI | 20.0 | 7.586e+05 | 2.31e-07 | phases.0.atoms.4.biso | 9.836 | 5.692400 | 4.248 | True | yes | no | no | 182.929 | a_nac |
| nac_x1.03 | _CURVATURE_GATE | 30.0 | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | _CURVATURE_GATE | 1000.0 | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | SLOW_DESCENT_ESD | 0.5 | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | SLOW_DESCENT_ESD | 2.0 | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | SLOW_DESCENT_ESD | None | 0 | 2.31e-07 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_nac |
| nac_x1.03 | noise | 1e-12 | 2.315e-07 | 2.31e-07 | phases.0.atoms.5.biso | 1.27e-08 | 1.000000 | 0.953 | True | yes | no | no | 0.000 | a_nac |
| nac_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 1.448e+06 | 2.31e-07 | phases.0.atoms.4.biso | 10.28 | 5.526613 | 4.188 | True | yes | no | no | 518.467 | a_nac |
| cpd1a_x1.01 | _M_HI | 5.0 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _M_HI | 20.0 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _Q_TRIGGER | 3 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _Q_TRIGGER | 7 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _Q_WINDOW | 5 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _Q_WINDOW | 20 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _LAMBDA_FAIL_FACTOR | 5.0 | 4.124e-06 | 4.36e-06 | instrument.geometry.sample_displacement | 2.052e-07 | 1.000000 | 1.004 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _LAMBDA_FAIL_FACTOR | 20.0 | 5.857e-06 | 4.36e-06 | instrument.geometry.sample_displacement | 2.856e-07 | 1.000000 | 0.996 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _LAMBDA_FAIL_FLOOR | 0.01 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.004 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _LAMBDA_FAIL_FLOOR | 1.0 | 0 | 4.36e-06 | None | 0 | 1.000000 | 0.996 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _CURVATURE_GATE | 30.0 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | _CURVATURE_GATE | 1000.0 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | SLOW_DESCENT_ESD | 0.5 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | SLOW_DESCENT_ESD | 2.0 | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | SLOW_DESCENT_ESD | None | 0 | 4.36e-06 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.01 | noise | 1e-12 | 4.359e-06 | 4.36e-06 | instrument.geometry.sample_displacement | 1.184e-07 | 1.000000 | 1.000 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _M_HI | 5.0 | 102.6 | 3.99 | phases.0.cell.c | 1.616 | 0.379385 | 0.503 | True | yes | no | no | -0.035 | wt_fluorite |
| cpd1a_x1.03 | _M_HI | 20.0 | 3.047 | 3.99 | phases.0.cell.a | 0.5206 | 0.592113 | 0.484 | True | yes | no | no | 0.010 | wt_zincite |
| cpd1a_x1.03 | _Q_TRIGGER | 3 | 0 | 3.99 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _Q_TRIGGER | 7 | 0 | 3.99 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _Q_WINDOW | 5 | 0 | 3.99 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 7.884 | 3.99 | instrument.profile.v | 0.5317 | 0.542431 | 0.492 | True | yes | no | no | 0.008 | wt_fluorite |
| cpd1a_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 21.85 | 3.99 | phases.2.atoms.0.biso | 1.584 | 0.730562 | 0.509 | True | yes | no | no | -0.034 | wt_fluorite |
| cpd1a_x1.03 | _Q_WINDOW | 20 | 0 | 3.99 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 9.446 | 3.99 | instrument.profile.v | 0.5432 | 0.528518 | 0.407 | True | yes | no | no | 0.008 | wt_fluorite |
| cpd1a_x1.03 | _CURVATURE_GATE | 30.0 | 0 | 3.99 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _CURVATURE_GATE | 1000.0 | 0 | 3.99 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | SLOW_DESCENT_ESD | 0.5 | 0.01598 | 3.99 | phases.1.scale | 0.009996 | 1.000191 | 1.183 | True | yes | no | no | 0.000 | wt_zincite |
| cpd1a_x1.03 | noise | 1e-12 | 3.991 | 3.99 | phases.0.cell.a | 0.524 | 0.586891 | 0.533 | True | yes | no | no | 0.010 | wt_zincite |
| lab6_x1.01 | _M_HI | 5.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _M_HI | 20.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _Q_TRIGGER | 3 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _Q_TRIGGER | 7 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _Q_WINDOW | 5 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _Q_WINDOW | 20 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _LAMBDA_FAIL_FACTOR | 5.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _LAMBDA_FAIL_FACTOR | 20.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _LAMBDA_FAIL_FLOOR | 0.01 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _LAMBDA_FAIL_FLOOR | 1.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _CURVATURE_GATE | 30.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | _CURVATURE_GATE | 1000.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | SLOW_DESCENT_ESD | 0.5 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | SLOW_DESCENT_ESD | 2.0 | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | SLOW_DESCENT_ESD | None | 0 | 0 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | n/a | None |
| lab6_x1.01 | noise | 1e-12 | 0 | 0 | None | 1.362e-13 | 1.000000 | 1.000 | True | yes | no | no | n/a | None |
| lab6_x1.03 | _M_HI | 5.0 | 0.01905 | 0.0942 | instrument.geometry.sample_displacement | 0.004292 | 1.000000 | 1.184 | True | yes | no | no | 0.019 | a_cert |
| cpd1a_x1.03 | SLOW_DESCENT_ESD | None | 0.2492 | 3.99 | phases.1.scale | 0.01977 | 1.010408 | 1.253 | True | yes | no | no | 0.001 | wt_zincite |
| cpd1a_x1.03 | SLOW_DESCENT_ESD | 2.0 | 0.02099 | 3.99 | phases.2.atoms.1.biso | 0.09311 | 1.111160 | 0.983 | True | yes | no | no | -0.001 | wt_zincite |
| lab6_x1.03 | _Q_TRIGGER | 3 | 0 | 0.0942 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _M_HI | 20.0 | 0.01582 | 0.0942 | instrument.profile.w | 0.004759 | 1.000000 | 1.107 | True | yes | no | no | 0.004 | disp_spec |
| lab6_x1.03 | _Q_TRIGGER | 7 | 0 | 0.0942 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _Q_WINDOW | 5 | 0 | 0.0942 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _Q_WINDOW | 20 | 0 | 0.0942 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 0.1123 | 0.0942 | instrument.source.lines.1.weight | 0.003454 | 1.000002 | 1.248 | True | yes | no | no | 0.042 | disp_spec |
| lab6_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 0.1433 | 0.0942 | instrument.geometry.sample_displacement | 0.006457 | 0.999986 | 1.107 | True | yes | no | no | 0.111 | disp_spec |
| lab6_x1.03 | _CURVATURE_GATE | 30.0 | 0 | 0.0942 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 19.39 | 0.0942 | instrument.geometry.sample_displacement | 1.941 | 0.955059 | 1.388 | True | yes | no | no | 19.391 | disp_spec |
| lab6_x1.03 | _CURVATURE_GATE | 1000.0 | 0 | 0.0942 | None | 0 | 1.000000 | 1.000 | True | unreached | no | no | 0.000 | a_cert |
| lab6_x1.03 | SLOW_DESCENT_ESD | 0.5 | 0.006159 | 0.0942 | instrument.source.lines.1.weight | 0.0006473 | 1.000000 | 1.369 | True | yes | no | no | 0.001 | a_cert |
| lab6_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 118.1 | 0.0942 | instrument.geometry.sample_displacement | 0.2609 | 1.000299 | 1.417 | True | yes | no | no | 118.056 | disp_spec |
| lab6_x1.03 | SLOW_DESCENT_ESD | 2.0 | 0.007409 | 0.0942 | instrument.source.lines.1.weight | 0.0001246 | 1.000000 | 1.034 | True | yes | no | no | 0.003 | disp_spec |
| lab6_x1.03 | noise | 1e-12 | 0.0942 | 0.0942 | instrument.source.lines.1.weight | 0.007001 | 0.999994 | 1.053 | True | yes | no | no | 0.014 | a_cert |
| lab6_x1.03 | SLOW_DESCENT_ESD | None | 0.01291 | 0.0942 | instrument.source.lines.1.weight | 0.000143 | 1.000000 | 2.204 | True | yes | no | no | 0.003 | a_cert |
| cpd1a_zircon | _Q_TRIGGER | 3 | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _M_HI | 20.0 | 0.0002136 | 0.00547 | phases.3.scale | 2.83e-05 | 1.000000 | 1.113 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | _M_HI | 5.0 | 7.452e-05 | 0.00547 | phases.0.atoms.0.biso | 1.85e-05 | 1.000000 | 1.151 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 68.58 | 3.99 | phases.2.scale | 1.578 | 0.639294 | 1.824 | False | yes | no | no | -0.033 | wt_fluorite |
| cpd1a_zircon | _Q_TRIGGER | 7 | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _Q_WINDOW | 5 | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _LAMBDA_FAIL_FACTOR | 5.0 | 0.00274 | 0.00547 | instrument.profile.v | 0.0001665 | 0.999997 | 1.029 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _Q_WINDOW | 20 | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _CURVATURE_GATE | 30.0 | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _LAMBDA_FAIL_FLOOR | 0.01 | 0.0003165 | 0.00547 | phases.3.scale | 5.996e-05 | 1.000000 | 1.109 | True | yes | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | _LAMBDA_FAIL_FACTOR | 20.0 | 0.008436 | 0.00547 | instrument.profile.v | 0.0004 | 0.999991 | 0.997 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | _LAMBDA_FAIL_FLOOR | 1.0 | 0.002561 | 0.00547 | instrument.profile.v | 0.0001934 | 0.999997 | 1.248 | True | yes | yes | no | 0.000 | wt_fluorite |
| cpd1a_zircon | _CURVATURE_GATE | 1000.0 | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | SLOW_DESCENT_ESD | 0.5 | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | SLOW_DESCENT_ESD | 2.0 | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | SLOW_DESCENT_ESD | None | 0 | 0.00547 | None | 0 | 1.000000 | 1.000 | True | unreached | yes | no | 0.000 | wt_corundum |
| cpd1a_zircon | noise | 1e-12 | 0.005468 | 0.00547 | instrument.profile.v | 0.0002718 | 1.000005 | 1.167 | True | yes | yes | no | 0.000 | wt_corundum |

## Polish

22 polishes, 0 refused.

| start | constant | arm | to shipped | to shipped polished | path | bkg | S/S polished | to answer | S/S answer | rounds | settled |
|---|---|---|---|---|---|---|---|---|---|---|---|
| nac_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 1.009e+07 | 1.009e+07 | phases.0.atoms.5.biso | 9.801 | 33.1168549 | 1.516e+07 | 74.6427084 | 2 | True |
| nac_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 2.417e+09 | 2.417e+09 | phases.0.atoms.5.biso | 9.801 | 33.1168550 | 3.63e+09 | 74.6427085 | 2 | True |
| nac_x1.03 | _M_HI | 5.0 | 0.5707 | 0.5707 | phases.1.scale | 0.01369 | 0.9999651 | 94.34 | 2.2538403 | 2 | True |
| nac_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 7.454e+08 | 7.454e+08 | phases.0.atoms.4.biso | 9.834 | 32.1135567 | 1.119e+09 | 72.3813555 | 3 | True |
| nac_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 1.448e+06 | 1.448e+06 | phases.0.atoms.4.biso | 10.28 | 30.5434511 | 2.173e+06 | 68.8424646 | 2 | True |
| cpd1a_x1.03 | _M_HI | 5.0 | 102.6 | 39.42 | instrument.source.lines.1.weight | 15.89 | 0.4163627 | 33.15 | 2.0936684 | 2 | True |
| nac_x1.03 | _M_HI | 20.0 | 7.586e+05 | 7.586e+05 | phases.0.atoms.4.biso | 9.834 | 32.1135567 | 1.139e+06 | 72.3813554 | 5 | True |
| cpd1a_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 21.85 | 21.8 | phases.2.atoms.0.biso | 17.17 | 1.5439957 | 31 | 7.7639392 | 2 | True |
| cpd1a_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 7.973 | 6.779 | phases.2.atoms.0.biso | 1.925 | 0.8443541 | 47.36 | 4.2458108 | 5 | False |
| cpd1a_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 9.536 | 8.106 | instrument.profile.v | 3.229 | 0.8021723 | 48.58 | 4.0337010 | 5 | False |
| cpd1a_x1.03 | _M_HI | 20.0 | 4.383 | 0.5919 | phases.1.scale | 1.583 | 1.0081160 | 41.5 | 5.0692831 | 5 | False |
| lab6_x1.03 | _LAMBDA_FAIL_FACTOR | 5.0 | 34.6 | 196.8 | instrument.geometry.sample_displacement | 1.589 | 0.9667140 | 305.7 | 93.2336904 | 5 | False |
| lab6_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 16.92 | 522.4 | instrument.geometry.sample_displacement | 3.538 | 0.9175984 | 77.42 | 88.4967923 | 5 | False |
| lab6_x1.03 | _LAMBDA_FAIL_FLOOR | 1.0 | 19.35 | 404.2 | instrument.geometry.sample_displacement | 4.157 | 0.9154163 | 69.98 | 88.2863414 | 5 | False |
| cpd1a_x1.03 | noise | 1e-12 | 4.339 | 0.5814 | phases.1.scale | 1.352 | 0.9915943 | 42.04 | 4.9862042 | 5 | False |
| lab6_x1.03 | _LAMBDA_FAIL_FACTOR | 20.0 | 118.1 | 1.102e+04 | instrument.geometry.sample_displacement | 2.366 | 1.0070432 | 9.274e+04 | 97.1232024 | 2 | True |
| lab6_x1.01 | shipped | shipped | 0 | 0 | None | 0 | 1.0000000 | 307.5 | 97.1232024 | 2 | True |
| cpd1a_x1.03 | SLOW_DESCENT_ESD | None | 0.8848 | 0.2689 | phases.0.scale | 0.5468 | 0.9993569 | 41.81 | 5.0252381 | 5 | False |
| nac_x1.03 | shipped | shipped | 2.686e-07 | 0 | None | 0 | 1.0000000 | 93.11 | 2.2539190 | 2 | True |
| cpd1a_x1.03 | shipped | shipped | 0.9325 | 0 | None | 0 | 1.0000000 | 41.84 | 5.0284720 | 5 | False |
| cpd1a_x1.03 | _LAMBDA_FAIL_FLOOR | 0.01 | 68.67 | 69.11 | phases.2.scale | 11.73 | 1.1147119 | 72.04 | 5.6052977 | 5 | True |
| lab6_x1.03 | shipped | shipped | 131.2 | 0 | None | 0 | 1.0000000 | 1.031e+05 | 96.4439241 | 5 | False |
