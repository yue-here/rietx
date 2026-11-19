# WP-2017 group B, Q4: `BVLS_MAX_COLUMNS` on three Pawley fits

Rows: 9 fits, head `b0346eb01ce5f08d2e8a9c3c01af5c2730f0e9ba`, Linux x86_64, numpy 2.5.3, rietx-kernels 1.5.0.  Written by `group_b_q4.py summary`; the raw rows are not committed.

Columns: the constant; the largest LM solve's column count and the path it took; solves by path; Rwp; evaluations; status; the largest shift of any row against `shipped` in plain esd over the larger esd, and of the background rows apart.

| family | arm | constant | largest solve | its path | BVLS / PCG solves | Rwp | evals | status | shift vs shipped | bkg shift |
|---|---|---|---|---|---|---|---|---|---|---|
| fap | shipped | 128 | 343 | pcg | 0 / 37 | 0.078624 | 41 | converged | — | — |
| fap | noise | 128 | 343 | pcg | 0 / 47 | 0.078624 | 51 | converged | 1.75e-06 instrument.profile.u | 9.78e-07 |
| fap | flip | 343 | 343 | bvls | 55 / 0 | 0.080630 | 58 | converged | 1.27 phases.0.cell.c | 0.807 |
| nac | shipped | 128 | 154 | pcg | 0 / 35 | 0.075164 | 38 | converged | — | — |
| nac | noise | 128 | 154 | pcg | 0 / 35 | 0.075164 | 38 | converged | 2.52e-06 phases.0.cell.a | 1.87e-09 |
| nac | flip | 154 | 154 | bvls | 35 / 0 | 0.075164 | 38 | converged | 4.94e-08 instrument.profile.v | 3.54e-09 |
| cpd1a | shipped | 128 | 128 | bvls | 168 / 0 | 0.164302 | 168 | converged | — | — |
| cpd1a | noise | 128 | 128 | bvls | 168 / 0 | 0.164302 | 168 | converged | 2.21e-06 phases.0.cell.c | 3.62e-07 |
| cpd1a | flip | 127 | 128 | pcg | 101 / 74 | 0.164328 | 176 | converged | 1.19 phases.0.cell.c | 0.187 |

## References

- fap shipped: a_gsas 9.371676(0.000034) vs 9.371724; c_gsas 6.885862(0.000033) vs 6.885867
- fap flip: a_gsas 9.371677(0.000036) vs 9.371724; c_gsas 6.885819(0.000034) vs 6.885867
- nac shipped: a_nac 10.251211(0.000004) vs 10.251; a_caf2 5.464572(0.000006) vs 5.4631
- nac flip: a_nac 10.251211(0.000004) vs 10.251; a_caf2 5.464572(0.000006) vs 5.4631

## Codes

- cpd1a shipped: DISPERSION_NEGLECTED, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED, SPACE_GROUP_SETTING_ASSUMED
- fap shipped: DISPERSION_NEGLECTED, FLOOR_HIT, PATTERN_UNDERSAMPLED, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED, RESOLUTION_NOT_POSITIVE
- nac shipped: CAPILLARY_OFFSET_UNAVAILABLE, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED
- nac noise: CAPILLARY_OFFSET_UNAVAILABLE, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED
- fap noise: DISPERSION_NEGLECTED, FLOOR_HIT, PATTERN_UNDERSAMPLED, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED, RESOLUTION_NOT_POSITIVE
- cpd1a noise: DISPERSION_NEGLECTED, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED, SPACE_GROUP_SETTING_ASSUMED
- nac flip: CAPILLARY_OFFSET_UNAVAILABLE, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED
- cpd1a flip: DISPERSION_NEGLECTED, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED, SPACE_GROUP_SETTING_ASSUMED
- fap flip: DISPERSION_NEGLECTED, FLOOR_HIT, PATTERN_UNDERSAMPLED, PAWLEY_OFF_DATA_RIDGED, PAWLEY_OVERLAP_UNRESOLVED
