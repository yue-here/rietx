# WP-2017 group F: auto_background's pick near its triggers

Run at `998b47034`, Linux x86_64, Python 3.12.14, numpy 2.5.3, rietx-kernels 1.5.0, 4 workers, compiled tier on, one kernel thread.  Written by `group_f.py summary`; patterns and arms in its docstring.

Shipped triggers: `HUMP_TRIGGER` 0.05, `AIR_SCATTER_TRIGGER` 0.3.

| Pattern | Arm | hump score | air gain | knot step | air term | Rwp | evaluations | status | model shift vs pick (row) | background | reference | air code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| si640c | pick | 0.0991 | 0.0669 | 3 | False | 0.0874401 | 81 | converged | — | — | λ -11.04 ppm from XND | yes |
| si640c | knot_flip | 0.0991 | 0.0669 | 8 | False | 0.1037923 | 78 | converged | 4.03 (`phases.0.lor_size`) | 144 | λ -11.41 ppm from XND | yes |
| si640c | air_flip | 0.0991 | 0.0669 | 3 | True | 0.0874401 | 81 | converged | 3.83e-06 (`phases.0.lor_size`) | 0.000803 | λ -11.04 ppm from XND | no |
| si640c | both_flip | 0.0991 | 0.0669 | 8 | True | 0.1037923 | 78 | converged | 4.03 (`phases.0.lor_size`) | 144 | λ -11.41 ppm from XND | no |
| si640c | noise | 0.0991 | 0.0669 | 3 | False | 0.0874401 | 82 | converged | 3.53e-06 (`instrument.source.lines.0.wavelength`) | 4.68e-08 | λ -11.04 ppm from XND | yes |
| si640c | blank | — | — | — | — | 0.0733927 | 83 | converged | 0.887 (`phases.0.lor_size`) | 630 | λ -10.86 ppm from XND | no |
| cpd-1a | pick | 0.251 | 0.817 | 3 | True | 0.1425790 | 164 | converged | — | — | corundum +0.12, zincite -0.72, fluorite +0.60 wt % | no |
| cpd-1a | knot_flip | 0.251 | 0.817 | 8 | True | 0.1439149 | 163 | converged | 0.72 (`phases.2.lor_size`) | 20.4 | corundum +0.13, zincite -0.75, fluorite +0.62 wt % | no |
| cpd-1a | air_flip | 0.251 | 0.817 | 3 | False | 0.1443592 | 164 | converged | 0.17 (`phases.2.lor_size`) | 23.2 | corundum +0.14, zincite -0.72, fluorite +0.58 wt % | yes |
| cpd-1a | both_flip | 0.251 | 0.817 | 8 | False | 0.1593274 | 163 | converged | 1.48 (`phases.2.lor_size`) | 29.3 | corundum +0.15, zincite -0.74, fluorite +0.59 wt % | yes |
| cpd-1a | noise | 0.251 | 0.817 | 3 | True | 0.1425790 | 164 | converged | 2.46e-06 (`phases.2.cell.a`) | 4.03e-08 | corundum +0.12, zincite -0.72, fluorite +0.60 wt % | no |
| cpd-1b | pick | 0.356 | 0.45 | 3 | True | 0.1281187 | 157 | converged | — | — | corundum +0.12, zincite -0.15, fluorite +0.03 wt % | no |
| cpd-1b | knot_flip | 0.356 | 0.45 | 8 | True | 0.1283604 | 159 | converged | 0.199 (`phases.0.lor_strain`) | 15.1 | corundum +0.11, zincite -0.15, fluorite +0.04 wt % | no |
| cpd-1b | air_flip | 0.356 | 0.45 | 3 | False | 0.1290164 | 157 | converged | 0.101 (`phases.2.scale`) | 17.8 | corundum +0.12, zincite -0.15, fluorite +0.03 wt % | yes |
| cpd-1b | both_flip | 0.356 | 0.45 | 8 | False | 0.1358127 | 159 | converged | 0.615 (`phases.1.scale`) | 19.8 | corundum +0.10, zincite -0.13, fluorite +0.03 wt % | yes |
| cpd-1b | noise | 0.356 | 0.45 | 3 | True | 0.1281187 | 157 | converged | 9.19e-07 (`phases.0.cell.a`) | 9.98e-08 | corundum +0.12, zincite -0.15, fluorite +0.03 wt % | no |
| cpd-1c | pick | 0.246 | 0.245 | 3 | False | 0.0949586 | 139 | converged | — | — | corundum +0.74, zincite -1.01, fluorite +0.28 wt % | yes |
| cpd-1c | knot_flip | 0.246 | 0.245 | 8 | False | 0.1008441 | 142 | converged | 1.21 (`instrument.profile.v`) | 46.1 | corundum +0.88, zincite -1.20, fluorite +0.33 wt % | yes |
| cpd-1c | air_flip | 0.246 | 0.245 | 3 | True | 0.0945991 | 139 | converged | 0.0493 (`phases.2.scale`) | 14.8 | corundum +0.73, zincite -1.00, fluorite +0.28 wt % | no |
| cpd-1c | both_flip | 0.246 | 0.245 | 8 | True | 0.0968442 | 143 | converged | 1.23 (`phases.1.lor_size`) | 55.9 | corundum +0.83, zincite -1.15, fluorite +0.33 wt % | no |
| cpd-1c | noise | 0.246 | 0.245 | 3 | False | 0.0949586 | 139 | converged | 1.24e-05 (`instrument.geometry.axial_sl`) | 1.28e-06 | corundum +0.74, zincite -1.01, fluorite +0.28 wt % | yes |
| cpd-1d | pick | 0.192 | 0.64 | 3 | True | 0.1138846 | 148 | converged | — | — | corundum +1.47, zincite -3.98, fluorite +2.51 wt % | no |
| cpd-1d | knot_flip | 0.192 | 0.64 | 8 | True | 0.1140959 | 147 | converged | 0.91 (`phases.2.lor_size`) | 15.4 | corundum +1.54, zincite -3.98, fluorite +2.44 wt % | no |
| cpd-1d | air_flip | 0.192 | 0.64 | 3 | False | 0.1146811 | 148 | converged | 0.12 (`phases.0.scale`) | 18.9 | corundum +1.49, zincite -3.99, fluorite +2.50 wt % | yes |
| cpd-1d | both_flip | 0.192 | 0.64 | 8 | False | 0.1224250 | 144 | converged | 1.31 (`phases.2.lor_size`) | 22.4 | corundum +1.59, zincite -3.96, fluorite +2.37 wt % | yes |
| cpd-1d | noise | 0.192 | 0.64 | 3 | True | 0.1138846 | 148 | converged | 1.96e-06 (`instrument.geometry.axial_sl`) | 1.29e-07 | corundum +1.47, zincite -3.98, fluorite +2.51 wt % | no |
| cpd-1e | pick | 0.208 | 0.6 | 3 | True | 0.1139475 | 164 | converged | — | — | corundum +2.22, zincite -2.49, fluorite +0.28 wt % | no |
| cpd-1e | knot_flip | 0.208 | 0.6 | 8 | True | 0.1141479 | 165 | converged | 0.617 (`phases.2.lor_size`) | 16.4 | corundum +2.24, zincite -2.48, fluorite +0.24 wt % | no |
| cpd-1e | air_flip | 0.208 | 0.6 | 3 | False | 0.1147442 | 164 | converged | 0.0948 (`phases.0.scale`) | 18.7 | corundum +2.23, zincite -2.49, fluorite +0.28 wt % | yes |
| cpd-1e | both_flip | 0.208 | 0.6 | 8 | False | 0.1219880 | 170 | converged | 0.868 (`phases.2.lor_size`) | 23.1 | corundum +2.26, zincite -2.46, fluorite +0.20 wt % | yes |
| cpd-1e | noise | 0.208 | 0.6 | 3 | True | 0.1139475 | 164 | converged | 6.84e-06 (`phases.2.lor_size`) | 1.73e-06 | corundum +2.22, zincite -2.49, fluorite +0.28 wt % | no |
| cpd-1f | pick | 0.215 | 0.431 | 3 | True | 0.0997838 | 145 | converged | — | — | corundum +2.85, zincite -4.83, fluorite +1.97 wt % | no |
| cpd-1f | knot_flip | 0.215 | 0.431 | 8 | True | 0.1007373 | 143 | converged | 0.885 (`phases.2.lor_strain`) | 14.6 | corundum +2.95, zincite -4.90, fluorite +1.96 wt % | no |
| cpd-1f | air_flip | 0.215 | 0.431 | 3 | False | 0.1004629 | 144 | converged | 0.113 (`phases.0.scale`) | 18.1 | corundum +2.87, zincite -4.85, fluorite +1.97 wt % | yes |
| cpd-1f | both_flip | 0.215 | 0.431 | 8 | False | 0.1067237 | 144 | converged | 1.16 (`phases.0.scale`) | 20.6 | corundum +2.99, zincite -4.92, fluorite +1.93 wt % | yes |
| cpd-1f | noise | 0.215 | 0.431 | 3 | True | 0.0997838 | 145 | converged | 2.04e-06 (`instrument.geometry.axial_sl`) | 2.28e-07 | corundum +2.85, zincite -4.83, fluorite +1.97 wt % | no |
| cpd-1g | pick | 0.201 | 0.526 | 3 | True | 0.1082333 | 153 | converged | — | — | corundum +2.14, zincite -3.92, fluorite +1.78 wt % | no |
| cpd-1g | knot_flip | 0.201 | 0.526 | 8 | True | 0.1086005 | 153 | converged | 0.536 (`phases.2.lor_size`) | 13.7 | corundum +2.19, zincite -3.91, fluorite +1.72 wt % | no |
| cpd-1g | air_flip | 0.201 | 0.526 | 3 | False | 0.1089368 | 153 | converged | 0.148 (`phases.0.lor_size`) | 18.1 | corundum +2.16, zincite -3.93, fluorite +1.77 wt % | yes |
| cpd-1g | both_flip | 0.201 | 0.526 | 8 | False | 0.1157335 | 160 | converged | 0.873 (`phases.2.lor_size`) | 20.2 | corundum +2.24, zincite -3.91, fluorite +1.68 wt % | yes |
| cpd-1g | noise | 0.201 | 0.526 | 3 | True | 0.1082333 | 153 | converged | 1.28e-07 (`instrument.geometry.axial_sl`) | 9.32e-09 | corundum +2.14, zincite -3.92, fluorite +1.78 wt % | no |
| cpd-1h | pick | 0.208 | 0.537 | 3 | True | 0.1109079 | 160 | converged | — | — | corundum +2.01, zincite -3.82, fluorite +1.81 wt % | no |
| cpd-1h | knot_flip | 0.208 | 0.537 | 8 | True | 0.1111368 | 161 | converged | 0.521 (`phases.2.lor_size`) | 15.2 | corundum +2.03, zincite -3.80, fluorite +1.77 wt % | no |
| cpd-1h | air_flip | 0.208 | 0.537 | 3 | False | 0.1116345 | 160 | converged | 0.109 (`phases.0.scale`) | 18 | corundum +2.02, zincite -3.82, fluorite +1.80 wt % | yes |
| cpd-1h | both_flip | 0.208 | 0.537 | 8 | False | 0.1182616 | 159 | converged | 0.944 (`phases.1.scale`) | 21.5 | corundum +2.07, zincite -3.79, fluorite +1.72 wt % | yes |
| cpd-1h | noise | 0.208 | 0.537 | 3 | True | 0.1109079 | 160 | converged | 2.32e-06 (`instrument.geometry.axial_sl`) | 6.38e-07 | corundum +2.01, zincite -3.82, fluorite +1.81 wt % | no |

Si SRM 640c, each arm against the measured-blank arm on λ, zero and Biso (plain esd over the larger esd):

- pick: wavelength 0.43, zero_shift 0.422, biso 0.327
- knot_flip: wavelength 1.09, zero_shift 1.24, biso 3.04
- air_flip: wavelength 0.43, zero_shift 0.422, biso 0.327
- both_flip: wavelength 1.09, zero_shift 1.24, biso 3.04
- noise: wavelength 0.43, zero_shift 0.422, biso 0.327
