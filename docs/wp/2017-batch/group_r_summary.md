# WP-2017 group R, read from group_r.jsonl

head 4cb7aedc7, Linux x86_64, numpy 2.5.3, rietx-kernels 1.5.0, 3 workers, 1 kernel thread a worker, compiled tier on.

42 rows, 0 errors.


Shift: the largest move of a row that is not background against the family's shipped arm, in plain esd over the larger esd (rows with an esd on both sides only; a held row has none), background beside.

## R1. `width_twins_held`

| family | arm | Rwp | evals | status | shift esd | row | off the widths | row | bkg esd | QPA wt % | twins recorded | flat/bound codes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lab6cbn | held | 0.137711 | 47 | converged | 0 | — | 0 | — | 0 | LaB6 16.779, cBN 83.221 | x, y from `size_strain` (4 stages) | FLOOR_HIT |
| lab6cbn | none | 0.128812 | 49 | converged | 55 | phases.0.lor_size | 9.73 | phases.0.atoms.0.biso | 5.03 | LaB6 16.842, cBN 83.158 | none recorded | COVARIANCE_DIRECTION_DISCARDED |
| lab6cbn | specimen | 0.168625 | 51 | converged | 21.3 | phases.1.cell.a | 21.3 | phases.1.cell.a | 4.1 | LaB6 17.787, cBN 82.213 | x, y from `size_strain` (4 stages) | — |
| lab6cbn | noise | 0.137711 | 47 | converged | 9.69e-07 | phases.1.cell.a | 9.69e-07 | phases.1.cell.a | 1.27e-09 | LaB6 16.779, cBN 83.221 | x, y from `size_strain` (4 stages) | FLOOR_HIT |
| cpd1a | held | 0.163072 | 175 | converged | 0 | — | 0 | — | 0 | corundum 1.717, zincite 3.354, fluorite 94.928 | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION |
| cpd1a | none | 0.161872 | 178 | converged | 6.98 | instrument.profile.v | 4.35 | instrument.geometry.axial_sl | 1.48 | corundum 1.981, zincite 3.537, fluorite 94.483 | none recorded | COVARIANCE_DIRECTION_DISCARDED, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE |
| cpd1a | specimen | 0.162894 | 169 | converged | 6.71 | instrument.profile.v | 4.49 | instrument.geometry.axial_sl | 0.878 | corundum 1.425, zincite 3.305, fluorite 95.269 | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION |
| cpd1a | noise | 0.163072 | 175 | converged | 4.75e-06 | instrument.geometry.axial_sl | 4.75e-06 | instrument.geometry.axial_sl | 5.15e-07 | corundum 1.717, zincite 3.354, fluorite 94.928 | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION |
| nac | held | 0.088244 | 57 | converged | 0 | — | 0 | — | 0 | 1000236 98.491, CaF2 1.509 | x, y from `size_strain` (3 stages) | FLOOR_HIT |
| nac | none | 0.088172 | 59 | converged | 113 | phases.0.lor_size | 0.957 | phases.1.atoms.1.biso | 0.553 | 1000236 98.486, CaF2 1.514 | none recorded | COVARIANCE_DIRECTION_DISCARDED, FLOOR_HIT, HIGH_CORRELATION, RESOLUTION_NOT_POSITIVE |
| nac | specimen | 0.092877 | 52 | converged | 10.8 | phases.1.scale | 10.8 | phases.1.scale | 1.41 | 1000236 98.652, CaF2 1.348 | x, y from `size_strain` (3 stages) | FLOOR_HIT |
| nac | noise | 0.088244 | 57 | converged | 2.19e-06 | phases.0.cell.a | 2.19e-06 | phases.0.cell.a | 3.45e-08 | 1000236 98.491, CaF2 1.509 | x, y from `size_strain` (3 stages) | FLOOR_HIT |
| cucr_cold | held | 0.223292 | 104 | converged | 0 | — | 0 | — | 0 | CuCr2O4 99.111, CuO 0.889 | x, y from `size_strain` (2 stages) | FLOOR_HIT |
| cucr_cold | none | 0.223286 | 133 | converged | 8.26 | phases.0.lor_size | 0.17 | phases.0.scale | 0.0861 | CuCr2O4 99.107, CuO 0.893 | none recorded | COVARIANCE_DIRECTION_DISCARDED, FLOOR_HIT, HIGH_CORRELATION |
| cucr_cold | specimen | 0.224123 | 99 | converged | 6.73 | phases.1.scale | 6.73 | phases.1.scale | 0.926 | CuCr2O4 99.498, CuO 0.502 | x, y from `size_strain` (2 stages) | FLOOR_HIT |
| cucr_cold | noise | 0.223292 | 104 | converged | 8.69e-07 | phases.1.cell.b | 8.69e-07 | phases.1.cell.b | 2.11e-08 | CuCr2O4 99.111, CuO 0.889 | x, y from `size_strain` (2 stages) | FLOOR_HIT |

Widths at the answer (value(plain esd); fixed = not free at the end; floor = on a 0 lower bound; ±180 = on the ceiling):

- lab6cbn held (LaB6, cBN): profile.u 0; profile.x 0.0024228; profile.y 0.037739; 0.lor_size 0(2.5e-05) floor; 0.lor_strain 0(0.0002) floor; 1.lor_size 0(0.00011) floor; 1.lor_strain 0.03536(0.00081); cells {'phases.0': [4.15689, 4.15689, 4.15689], 'phases.1': [3.6166000941058867, 3.6166000941058867, 3.6166000941058867]}
- lab6cbn none (LaB6, cBN): profile.u 0; profile.x 0.0013173(1.1e-05); profile.y 0.02916(8.4e-05); 0.lor_size 0.0013796(1.3e-05); 0.lor_strain 0(9.8e-05) floor; 1.lor_size 3.0171e-05(9.8e-05); 1.lor_strain 0.051717(0.00074); cells {'phases.0': [4.15689, 4.15689, 4.15689], 'phases.1': [3.616603303389001, 3.616603303389001, 3.616603303389001]}
- lab6cbn specimen (LaB6, cBN): profile.u 0; profile.x 0.0025357(2.9e-05); profile.y 0.036841(0.00023); 0.lor_size 0 floor; 0.lor_strain 0 floor; 1.lor_size 0 floor; 1.lor_strain 0 floor; cells {'phases.0': [4.15689, 4.15689, 4.15689], 'phases.1': [3.6165207332369587, 3.6165207332369587, 3.6165207332369587]}
- lab6cbn noise (LaB6, cBN): profile.u 0; profile.x 0.0024228; profile.y 0.037739; 0.lor_size 0(2.5e-05) floor; 0.lor_strain 0(0.0002) floor; 1.lor_size 0(0.00011) floor; 1.lor_strain 0.03536(0.00081); cells {'phases.0': [4.156890000004157, 4.156890000004157, 4.156890000004157], 'phases.1': [3.6166000941095, 3.6166000941095, 3.6166000941095]}
- cpd1a held (corundum, zincite, fluorite): profile.u 0.0080161; profile.x 0.0035276; profile.y 0.060122; 0.lor_size 0.057748(0.082); 0.lor_strain 0(0.21) floor; 1.lor_size 0.026845(0.01); 1.lor_strain 0(0.026) floor; 2.lor_size 0.016383(0.0014); 2.lor_strain 0.012912(0.0033); cells {'phases.0': [4.758503654953467, 4.758503654953467, 12.990038817516881], 'phases.1': [3.24861181579707, 3.24861181579707, 5.206487049436743], 'phases.2': [5.4628085338723835, 5.4628085338723835, 5.4628085338723835]}
- cpd1a none (corundum, zincite, fluorite): profile.u -0.0055431(20); profile.x 0.0026909(0.043); profile.y -0.19774(0.059); 0.lor_size 0.18886(0.068); 0.lor_strain 0(0.13) floor; 1.lor_size 0.090565(0.045); 1.lor_strain 0.099662(0.067); 2.lor_size 0.016914(0.043); 2.lor_strain 0.27309(0.059); cells {'phases.0': [4.758353587285489, 4.758353587285489, 12.990609839797102], 'phases.1': [3.248652289859891, 3.248652289859891, 5.206581902392657], 'phases.2': [5.462872356720252, 5.462872356720252, 5.462872356720252]}
- cpd1a specimen (corundum, zincite, fluorite): profile.u 0.0011873(0.00084); profile.x 0.00012151(0.0013); profile.y 0.073991(0.0031); 0.lor_size 0.02; 0.lor_strain 0.0001; 1.lor_size 0.02; 1.lor_strain 0.0001; 2.lor_size 0.02; 2.lor_strain 0.0001; cells {'phases.0': [4.758441741884416, 4.758441741884416, 12.990021795098613], 'phases.1': [3.2486479447420025, 3.2486479447420025, 5.206539830775396], 'phases.2': [5.4628568607006365, 5.4628568607006365, 5.4628568607006365]}
- cpd1a noise (corundum, zincite, fluorite): profile.u 0.0080161; profile.x 0.0035276; profile.y 0.060122; 0.lor_size 0.057748(0.082); 0.lor_strain 0(0.21) floor; 1.lor_size 0.026845(0.01); 1.lor_strain 0(0.027) floor; 2.lor_size 0.016383(0.0013); 2.lor_strain 0.012912(0.0032); cells {'phases.0': [4.758503655547184, 4.758503655547184, 12.990038820034687], 'phases.1': [3.2486118162775357, 3.2486118162775357, 5.206487050247495], 'phases.2': [5.462808534683844, 5.462808534683844, 5.462808534683844]}
- nac held (1000236, CaF2): profile.u 0.0010876(2.4e-05); profile.x 0.0020624; profile.y 0.0044515; 0.lor_size 0(1.8e-05) floor; 0.lor_strain 7.1887e-05(0.00017); 1.lor_size 0.0020768(0.00016); 1.lor_strain 0(0.0016) floor; cells {'phases.0': [10.251217032133567, 10.251217032133567, 10.251217032133567], 'phases.1': [5.464642855427947, 5.464642855427947, 5.464642855427947]}
- nac none (1000236, CaF2): profile.u 0.0010872(2.4e-05); profile.x 0(8.7e-06) floor; profile.y -0.00039898(8.3e-05); 0.lor_size 0.0019783(8.8e-06); 0.lor_strain 0.0056641(8.3e-05); 1.lor_size 0.0046324(0.00016); 1.lor_strain 0(0.0015) floor; cells {'phases.0': [10.251216302282293, 10.251216302282293, 10.251216302282293], 'phases.1': [5.464640284452892, 5.464640284452892, 5.464640284452892]}
- nac specimen (1000236, CaF2): profile.u 0.0010625(2.5e-05); profile.x 0.0018937(1.8e-05); profile.y 0.005123(0.00017); 0.lor_size 0.0001; 0.lor_strain 0.0001; 1.lor_size 0.0001; 1.lor_strain 0.0001; cells {'phases.0': [10.251215686897424, 10.251215686897424, 10.251215686897424], 'phases.1': [5.464636085213595, 5.464636085213595, 5.464636085213595]}
- nac noise (1000236, CaF2): profile.u 0.0010876(2.4e-05); profile.x 0.0020624; profile.y 0.0044515; 0.lor_size 0(1.8e-05) floor; 0.lor_strain 7.1887e-05(0.00017); 1.lor_size 0.0020768(0.00016); 1.lor_strain 0(0.0016) floor; cells {'phases.0': [10.251217032143787, 10.251217032143787, 10.251217032143787], 'phases.1': [5.464642855433408, 5.464642855433408, 5.464642855433408]}
- cucr_cold held (CuCr2O4, CuO): profile.u 0.003623(0.0011); profile.x 0.0021188; profile.y 0.055213; 0.lor_size 0(0.00024) floor; 0.lor_strain 0(0.0024) floor; 1.lor_size 0(0.011) floor; 1.lor_strain 0.21035(0.11); cells {'phases.0': [7.712564694587736, 8.542609782766087, 8.537037012274263], 'phases.1': [4.6804120232402004, 3.4217332504726135, 5.124235383611092]}
- cucr_cold none (CuCr2O4, CuO): profile.u 0.0035184(0.0011); profile.x 0(0.00012) floor; profile.y 0.05551(0.0012); 0.lor_size 0.002021(0.00012); 0.lor_strain 3.6907e-06(0.0012); 1.lor_size 0(0.011) floor; 1.lor_strain 0.23214(0.11); cells {'phases.0': [7.712564252419861, 8.542607795731707, 8.53703847061987], 'phases.1': [4.680415369719753, 3.4217568713726507, 5.12420636207873]}
- cucr_cold specimen (CuCr2O4, CuO): profile.u 0.003599(0.0011); profile.x 0.0019823(0.00025); profile.y 0.055225(0.0024); 0.lor_size 0.0001; 0.lor_strain 0.0001; 1.lor_size 0.0001; 1.lor_strain 0.0001; cells {'phases.0': [7.71256612442916, 8.54259487568523, 8.537052963663843], 'phases.1': [4.681090907543784, 3.420850026096486, 5.126808979964818]}
- cucr_cold noise (CuCr2O4, CuO): profile.u 0.003623(0.0011); profile.x 0.0021188; profile.y 0.055213; 0.lor_size 0(0.00024) floor; 0.lor_strain 0(0.0024) floor; 1.lor_size 0(0.011) floor; 1.lor_strain 0.21035(0.11); cells {'phases.0': [7.712564694595523, 8.542609782773573, 8.537037012281838], 'phases.1': [4.680412023718084, 3.4217332517788264, 5.1242353813116255]}

## R2. `ProfileTCHZ:y` against Y ≥ 0

| family | arm | Rwp | evals | Y | X | shift esd | row | bkg esd | cell a | lor_size, lor_strain | codes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fap | shipped | 0.092829 | 49 | 0 | 0.001 | 0 | — | 0 | 9.372514 | 0.023983(0.00068), 0.038055(0.0014) | — |
| fap | yfloor | 0.092829 | 49 | 0 | 0.001 | 0 | — | 0 | 9.372514 | 0.023983(0.00068), 0.038055(0.0014) | — |
| fap | noise | 0.092829 | 49 | 0 | 0.001 | 1.71e-06 | instrument.geometry.axial_sl | 1.71e-07 | 9.372514 | 0.023983(0.00068), 0.038055(0.0014) | — |
| nac | shipped | 0.092877 | 46 | 0.005223(0.00017) | 0.0019937(1.8e-05) | 0 | — | 0 | 10.251216 | 0, 0, 0, 0 | FLOOR_HIT |
| nac | yfloor | 0.092877 | 46 | 0.005223(0.00017) | 0.0019937(1.8e-05) | 0 | — | 0 | 10.251216 | 0, 0, 0, 0 | FLOOR_HIT |
| nac | noise | 0.092877 | 46 | 0.005223(0.00017) | 0.0019937(1.8e-05) | 2.1e-06 | phases.0.cell.a | 7.29e-09 | 10.251216 | 0, 0, 0, 0 | FLOOR_HIT |
| cpd1a | shipped | 0.163072 | 175 | 0.060122 | 0.0035276 | 0 | — | 0 | 4.758504 | 0.057748(0.082), 0(0.21), 0.026845(0.01), 0(0.026), 0.016383(0.0014), 0.012912(0.0033) | FLOOR_HIT, HIGH_CORRELATION |
| cpd1a | yfloor | 0.163072 | 175 | 0.060122 | 0.0035276 | 0 | — | 0 | 4.758504 | 0.057748(0.082), 0(0.21), 0.026845(0.01), 0(0.026), 0.016383(0.0014), 0.012912(0.0033) | FLOOR_HIT, HIGH_CORRELATION |
| cpd1a | noise | 0.163072 | 175 | 0.060122 | 0.0035276 | 4.75e-06 | instrument.geometry.axial_sl | 5.15e-07 | 4.758504 | 0.057748(0.082), 0(0.21), 0.026845(0.01), 0(0.027), 0.016383(0.0013), 0.012912(0.0032) | FLOOR_HIT, HIGH_CORRELATION |
| lab6 | shipped | 0.087431 | 76 | 0.015116(0.001) | 0.028128(0.00074) | 0 | — | 0 | 4.156883 | 0, 0 | RESOLUTION_NOT_POSITIVE |
| lab6 | yfloor | 0.087431 | 77 | 0.015116(0.001) | 0.028128(0.00074) | 5.81e-08 | instrument.geometry.axial_sl | 5.42e-09 | 4.156883 | 0, 0 | RESOLUTION_NOT_POSITIVE |
| lab6 | noise | 0.087431 | 76 | 0.015116(0.001) | 0.028128(0.00074) | 5.79e-07 | phases.0.cell.a | 1.07e-08 | 4.156883 | 0, 0 | RESOLUTION_NOT_POSITIVE |
| lab6ss | shipped | 0.087580 | 86 | 0.013299 | 0.030155 | 0 | — | 0 | 4.156877 | 0(0.00071), 0(0.00094) | FLOOR_HIT, RESOLUTION_NOT_POSITIVE |
| lab6ss | yfloor | 0.087580 | 87 | 0.013299 | 0.030155 | 0.000126 | instrument.profile.u | 4.88e-05 | 4.156877 | 0(0.00071), 0(0.00094) | FLOOR_HIT, RESOLUTION_NOT_POSITIVE |

## R3. TRF and the ±180 bound

| fit | solver | closing | Rwp | evals | status | min Γ_L (deg) at 2θ | widths | twins recorded | codes |
|---|---|---|---|---|---|---|---|---|---|
| brucite_iso | lm | none | 0.186423 | 278 | converged | 0.02374 at 5.0 | profile.x 0 floor; profile.y 0.14243; profile.u 0.0098329; 0.lor_size 0.017428(0.0016); 0.lor_strain 0.0016843(0.0066) | u, x, y from `sample_broadening` (3 stages) | FLOOR_HIT, HIGH_CORRELATION |
| brucite_iso | lm | 1e-3 | 0.185483 | 288 | converged | 0.02161 at 5.0 | profile.x 0 floor; profile.y 0.14243; profile.u 0.0098329; 0.lor_size 0.01473(0.0016); 0.lor_strain 0.014786(0.0069) | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION |
| brucite_iso | trf | none | 0.186423 | 266 | converged | 0.02374 at 5.0 | profile.x 5.2194e-19 floor; profile.y 0.14242; profile.u 0.0098304; 0.lor_size 0.017428(0.0014); 0.lor_strain 0.0016937(0.0062) | u, x, y from `sample_broadening` (3 stages) | FLOOR_HIT, HIGH_CORRELATION |
| brucite_iso | trf | 1e-3 | 0.185483 | 275 | converged | 0.02161 at 5.0 | profile.x 5.2194e-19 floor; profile.y 0.14242; profile.u 0.0098304; 0.lor_size 0.01473(0.0014); 0.lor_strain 0.014793(0.0064) | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION |
| brucite_aniso | lm | none | 0.181409 | 346 | converged | 0.006219 at 5.0 | profile.x 0 floor; profile.y 0.14243; profile.u 0.0098329; 0.lor_size 0(0.002) floor; 0.lor_strain 0 floor | u, x, y from `sample_broadening` (3 stages) | FLOOR_HIT, HIGH_CORRELATION |
| brucite_aniso | lm | 1e-3 | 0.180563 | 374 | converged | 0.006219 at 5.0 | profile.x 0 floor; profile.y 0.14243; profile.u 0.0098329; 0.lor_size 0(0.0022) floor; 0.lor_strain 0 floor | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION |
| brucite_aniso | trf | none | 0.180419 | 312 | converged | 0.006218 at 5.0 | profile.x 5.2194e-19 floor; profile.y 0.14242; profile.u 0.0098304; 0.lor_size 7.0326e-39(0.0017) floor; 0.lor_strain 0 floor | u, x, y from `sample_broadening` (3 stages) | FLOOR_HIT, HIGH_CORRELATION, STEPHENS_STRAIN_NOT_POSITIVE |
| brucite_aniso | trf | 1e-3 | 0.179370 | 344 | converged | 0.006218 at 5.0 | profile.x 5.2194e-19 floor; profile.y 0.14242; profile.u 0.0098304; 0.lor_size 5.2647e-36(0.0017) floor; 0.lor_strain 0 floor | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION, STEPHENS_STRAIN_NOT_POSITIVE |
| corundum | lm | none | 0.145752 | 116 | converged | 0.04555 at 5.0 | profile.x 0.02843; profile.y 0.03729; profile.u -0.0017887; 0.lor_size 0.014831(0.0017); 0.lor_strain 0.014102(0.0033) | u, x, y from `sample_broadening` (3 stages) | FLOOR_HIT, HIGH_CORRELATION |
| corundum | lm | 1e-3 | 0.143596 | 125 | converged | 0.04893 at 5.0 | profile.x 0.02843; profile.y 0.03729; profile.u -0.0017887; 0.lor_size 0.018366(0.0016); 0.lor_strain 0.010692(0.0033) | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION |
| corundum | trf | none | 0.145752 | 117 | converged | 0.04555 at 5.0 | profile.x 0.028421; profile.y 0.037299; profile.u -0.0017883; 0.lor_size 0.01484(0.0016); 0.lor_strain 0.014093(0.0033) | u, x, y from `sample_broadening` (3 stages) | FLOOR_HIT, HIGH_CORRELATION |
| corundum | trf | 1e-3 | 0.143596 | 125 | converged | 0.04893 at 5.0 | profile.x 0.028421; profile.y 0.037299; profile.u -0.0017883; 0.lor_size 0.018374(0.0016); 0.lor_strain 0.010684(0.0032) | u, x, y from `sample_broadening` (4 stages) | FLOOR_HIT, HIGH_CORRELATION |
