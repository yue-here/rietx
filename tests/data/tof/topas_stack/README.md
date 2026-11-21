# TOPAS's two-exponential peak stack is the back-to-back pulse

**Synthetic input, no measured data.** One Gaussian peak (σ = 10 µs, `pv_fwhm` 23.548…, `pv_lor 0`), d = 2 Å on
`TOF_x_axis_calibration(0, 10000, 0)` so at 20000 µs, `d_Is` intensity 1000, a flat zero pattern 15000–25000 µs at 0.5 µs,
`iters 0`. Its two exponentials are the rise α = 0.2 µs⁻¹ (`exp_conv_const −34.538…`, = ln(0.001)/α) and the decay
β = 0.03 µs⁻¹ (`exp_conv_const +230.258…`), written as TOPAS's peak stack:

```
push_peak / exp_conv_const (rise) / bring_2nd_peak_to_top / exp_conv_const (decay) / add_pop_1st_2nd_peak
```

| file | what it is |
|---|---|
| `stack_P.inp` | the un-weighted stack (the beamline `GSAS_btb` form), byte for byte as run |
| `stack_PW.inp` | the same with `scale_top_peak 3` on the decay member |
| `stack_P_stack.txt.gz`, `stack_PW_stack_w3.txt.gz` | TOPAS's `Out_X_Ycalc` for each, CR stripped, cropped to 19800–20600 µs (every row outside is exactly 0), gzipped (`gzip -n -9`) |

**The program:** TOPAS-64 Version 6 (c) 1992-2016 Alan A. Coelho, as its console reports, run as a black box on
2026-10-01. No TOPAS file was read beyond its output.

**What it shows** (`tests/test_tof_topas_synthetic.py`): the un-weighted stack equals rietx's back-to-back exponential ⊗
Gaussian, 1000·H(T − 20000; α, β, σ), to **9.8e-4 of the maximum** — TOPAS's 1e-3 exponential truncation — and is *not* the
equal-weight sum of the two one-sided convolutions (0.71 off). The members are not unit-area, so their sum is Von Dreele,
Jorgensen & Windsor's (1982) eq. 10. With `scale_top_peak 3` the peak is 0.137 of its maximum off the pulse: a different
kind, which the reader refuses by name.

SHA-256:

```
6a2c14e722c35625c094af692e2f0b258ceb32e4b3f42fd481a0bbb157c6d26f  stack_P.inp
8af2bf79a0436df83995a9d6b9ddca638d41664c71d8b0cbcfefd9451634b73c  stack_PW.inp
45c442e91e35c813b7f8d4982d61bd0625ce183c42e540d89ed35e136d19fea8  stack_P_stack.txt.gz
5547e86bbeb96c47dbc2cc2ec738515c031860d37f9e0bc197c9851f9f9f221a  stack_PW_stack_w3.txt.gz
```
