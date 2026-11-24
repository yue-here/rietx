# WP-2017 group A from the shipped starts, rerun 2026-11-09 (read from group_a.jsonl)

head fabfe9b3f, rietx 1.12.0.dev0+gfabfe9b3f505, linux, 1 kernel thread per worker, compiled tier on, `[dev]`.

## Shipped

| family | Rwp | evaluations | stage terminations |
|---|---|---|---|
| lab6 | 0.087431 | 76 | scale_bkg:exhausted_fp64, disp:ftol_runs, cell:ftol_runs, profile_w:ftol_runs, profile:ftol_runs, lines_axial:ftol_runs, biso:exhausted_fp64, closing:ftol_runs |
| nac | 0.092877 | 46 | scale_bkg:exhausted_fp64, zero:exhausted_fp64, cell:ftol_runs, profile_w:ftol_runs, profile:ftol_runs, biso:ftol_runs, closing:ftol_runs |
| fap | 0.092829 | 49 | scale_bkg:exhausted_fp64, disp:exhausted_fp64, cell:ftol_runs, sample_lor:ftol_runs, axial:ftol_runs, biso:exhausted_fp64, closing:ftol_runs |
| cpd1a | 0.163072 | 175 | scale_bkg:exhausted_fp64, zero_disp:ftol_runs, cell:ftol_runs, profile_w:ftol_runs, profile:ftol_runs, sample_broadening:ftol_runs, lines_axial:ftol_runs, biso:ftol_runs, closing:ftol_runs |

## Every arm

| constant | arm | family | model esd | path | bkg esd | Rwp ratio | eval ratio | conv | reached | ref further esd | ref name |
|---|---|---|---|---|---|---|---|---|---|---|---|
| _M_HI | 20.0 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _M_LO | 0.2 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _M_LO | 0.8 | fap | 0.0000 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 1.000 | True | yes | 3.1e-07 | lx_gsas |
| _M_HI | 5.0 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _Q_TRIGGER | 3 | fap | 0.0000 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 0.980 | True | yes | 3e-07 | lx_gsas |
| _Q_WINDOW | 20 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _LAMBDA_FAIL_FLOOR | 0.01 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _LAMBDA_FAIL_FACTOR | 5.0 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _LAMBDA_FAIL_FLOOR | 1.0 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _Q_TRIGGER | 7 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _LAMBDA_FAIL_FACTOR | 20.0 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _Q_WINDOW | 5 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _M_HI | 5.0 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _CONVERGED_RUNS | 5 | fap | 0.0000 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 1.041 | True | yes | 1.6e-06 | lx_gsas |
| _CURVATURE_GATE | 30.0 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _CONVERGED_RUNS | 2 | fap | 0.0001 | instrument.geometry.axial_sl | 0.0001 | 1.000000 | 0.918 | True | yes | -5e-05 | c_gsas |
| _CURVATURE_GATE | 1000.0 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _M_HI | 20.0 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| FTOL | 1e-08 | fap | 0.0001 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 0.980 | True | yes | -3.6e-05 | c_gsas |
| CELL_WINDOW | off | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| SLOW_DESCENT_ESD | None | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| FTOL | 1e-10 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| SLOW_DESCENT_ESD | 0.5 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| SLOW_DESCENT_ESD | 2.0 | fap | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_gsas |
| _M_LO | 0.2 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| noise | 1e-12 | fap | 0.0000 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 1.000 | True | yes | 1.2e-06 | lx_gsas |
| _M_LO | 0.8 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _Q_TRIGGER | 3 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _Q_WINDOW | 5 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _Q_TRIGGER | 7 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _Q_WINDOW | 20 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _LAMBDA_FAIL_FACTOR | 20.0 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _CONVERGED_RUNS | 2 | nac | 0.0004 | phases.1.atoms.1.biso | 0.0000 | 1.000000 | 0.891 | True | yes | -5.3e-06 | a_nac |
| _LAMBDA_FAIL_FACTOR | 5.0 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _LAMBDA_FAIL_FLOOR | 1.0 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _LAMBDA_FAIL_FLOOR | 0.01 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _CONVERGED_RUNS | 5 | nac | 0.0001 | phases.1.atoms.1.biso | 0.0000 | 1.000000 | 1.109 | True | yes | 2.9e-05 | a_caf2 |
| _CURVATURE_GATE | 30.0 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| FTOL | 1e-08 | nac | 0.0004 | phases.1.atoms.1.biso | 0.0000 | 1.000000 | 0.957 | True | yes | -5.3e-06 | a_nac |
| _CURVATURE_GATE | 1000.0 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| SLOW_DESCENT_ESD | 0.5 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| SLOW_DESCENT_ESD | 2.0 | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| FTOL | 1e-10 | nac | 0.0001 | phases.1.atoms.1.biso | 0.0000 | 1.000000 | 1.043 | True | yes | 2.9e-05 | a_caf2 |
| CELL_WINDOW | off | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| noise | 1e-12 | nac | 0.0000 | phases.0.atoms.2.biso | 0.0000 | 1.000000 | 1.000 | True | yes | 1.2e-07 | a_nac |
| SLOW_DESCENT_ESD | None | nac | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_nac |
| _M_HI | 5.0 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _M_LO | 0.2 | cpd1a | 0.0000 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 0.994 | True | yes | 2.6e-08 | wt_zincite |
| _M_HI | 20.0 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _M_LO | 0.8 | cpd1a | 0.0000 | phases.0.scale | 0.0000 | 1.000000 | 1.034 | True | yes | 2.1e-06 | wt_fluorite |
| _Q_TRIGGER | 7 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _Q_TRIGGER | 3 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _Q_WINDOW | 5 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _Q_WINDOW | 20 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _LAMBDA_FAIL_FLOOR | 0.01 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.006 | True | yes | 0 | wt_corundum |
| _LAMBDA_FAIL_FACTOR | 5.0 | cpd1a | 0.0000 | instrument.geometry.sample_displacement | 0.0000 | 1.000000 | 1.006 | True | yes | -2.6e-11 | wt_fluorite |
| _LAMBDA_FAIL_FACTOR | 20.0 | cpd1a | 0.0000 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 0.994 | True | yes | 2.7e-08 | wt_corundum |
| _LAMBDA_FAIL_FLOOR | 1.0 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 0.994 | True | yes | 0 | wt_corundum |
| _M_HI | 5.0 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| _M_HI | 20.0 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| _CONVERGED_RUNS | 2 | cpd1a | 0.0023 | instrument.profile.v | 0.0003 | 0.999998 | 0.954 | True | yes | 0.00018 | wt_fluorite |
| _M_LO | 0.2 | lab6 | 0.0000 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 1.000 | True | yes | -5.2e-08 | disp_spec |
| _CURVATURE_GATE | 30.0 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _CURVATURE_GATE | 1000.0 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| FTOL | 1e-08 | cpd1a | 0.0011 | phases.0.scale | 0.0003 | 1.000000 | 0.966 | True | yes | 0.00032 | wt_fluorite |
| _CONVERGED_RUNS | 5 | cpd1a | 0.0006 | phases.0.atoms.0.biso | 0.0002 | 1.000000 | 1.080 | True | yes | 0.00018 | wt_corundum |
| _M_LO | 0.8 | lab6 | 0.0000 | instrument.geometry.axial_sl | 0.0000 | 1.000000 | 1.026 | True | yes | 8.6e-08 | disp_spec |
| SLOW_DESCENT_ESD | 2.0 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| SLOW_DESCENT_ESD | None | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| noise | 1e-12 | cpd1a | 0.0000 | instrument.geometry.sample_displacement | 0.0000 | 1.000000 | 1.000 | True | yes | 4e-08 | wt_fluorite |
| _Q_TRIGGER | 3 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| SLOW_DESCENT_ESD | 0.5 | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _Q_TRIGGER | 7 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| FTOL | 1e-10 | cpd1a | 0.0007 | phases.0.atoms.0.biso | 0.0002 | 1.000000 | 1.017 | True | yes | 0.00022 | wt_corundum |
| _Q_WINDOW | 20 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| CELL_WINDOW | off | cpd1a | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | wt_corundum |
| _Q_WINDOW | 5 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| _LAMBDA_FAIL_FACTOR | 20.0 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| _LAMBDA_FAIL_FACTOR | 5.0 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| _LAMBDA_FAIL_FLOOR | 1.0 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| _LAMBDA_FAIL_FLOOR | 0.01 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| _CONVERGED_RUNS | 2 | lab6 | 0.0001 | instrument.profile.w | 0.0000 | 1.000000 | 0.921 | True | yes | 5.6e-05 | a_cert |
| _CURVATURE_GATE | 30.0 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| _CONVERGED_RUNS | 5 | lab6 | 0.0000 | instrument.profile.w | 0.0000 | 1.000000 | 1.132 | True | yes | 8.2e-10 | a_cert |
| _CURVATURE_GATE | 1000.0 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| FTOL | 1e-08 | lab6 | 0.0001 | instrument.profile.w | 0.0000 | 1.000000 | 0.987 | True | yes | 5.6e-05 | a_cert |
| FTOL | 1e-10 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| SLOW_DESCENT_ESD | 0.5 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| SLOW_DESCENT_ESD | None | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| SLOW_DESCENT_ESD | 2.0 | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| CELL_WINDOW | off | lab6 | 0.0000 | None | 0.0000 | 1.000000 | 1.000 | True | unreached | 0 | a_cert |
| noise | 1e-12 | lab6 | 0.0000 | instrument.geometry.sample_displacement | 0.0000 | 1.000000 | 1.000 | True | yes | -7.1e-08 | a_cert |

## Polish

| constant | arm | family | to shipped | to shipped polished | path | bkg | S/S polished | rounds | settled |
|---|---|---|---|---|---|---|---|---|---|
