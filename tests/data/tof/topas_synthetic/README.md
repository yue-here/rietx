# A synthetic time-of-flight bank, calculated by TOPAS

**Synthetic input, no measured data.** Every number in this directory is either
written in `spec.json` or computed from it: a made-up two-phase specimen (NiO and
Si, cell and coordinates rounded, Biso chosen) on a made-up bank (DIFC 10000 µs/Å,
DIFA −3.25 µs/Å², TZERO +7.5 µs, 2θ 90°, a three-term Chebyshev background), over
8000–12000 µs at 1 µs. Two profiles: `type1` (back-to-back exponentials ⊗
Gaussian, γ ≡ 0) and `type3` (⊗ pseudo-Voigt, γ ≠ 0).

| file | what it is |
|---|---|
| `spec.json` | the specimen, the bank and the two profiles |
| `generate.py` | the generator: builds the rietx `Structure`/`Instrument` from `spec.json` and writes each `<case>.inp` with `rietx.io.projects.topas_tof.from_tof` (`iters 0`, `convolution_step 4`, one `Out_X_Ycalc` line), plus the all-zero `flat.xye` the `.inp` reads, which is not vendored |
| `type1.inp`, `type3.inp` | the input TOPAS ran, byte for byte as the generator wrote it |
| `type1_ycalc.txt.gz`, `type3_ycalc.txt.gz` | TOPAS's `Out_X_Ycalc` output for each, CR stripped, gzipped (`gzip -n -9`) |

**The program:** TOPAS-64 Version 6 (c) 1992-2016 Alan A. Coelho, as its console
reports, run as a black box with `tc.exe` on the input above. No TOPAS file was
read for this fixture beyond what TOPAS writes as its output. **The date:**
2026-10-01.

SHA-256 of the vendored files:

```
52c1cc5dc78f90cb87bbc93624944ed28e3a97ff648ffe27af74bffddc26e10c  type1.inp
bce59a680626632418f3ee4c7157a53218b8c09f1e2a1b067fd12efc24f13456  type3.inp
da55acd3bff4b6e41f6fa8c9e6eaa6c972c8832ed2d9407f8fa42bfd11a5b4d2  type1_ycalc.txt.gz
1134ae478efed363a79b53886af094900b24731944f5e86a652670d37ee3e46f  type3_ycalc.txt.gz
```

`tests/test_tof_topas_synthetic.py` builds the same model from `spec.json`,
evaluates rietx's flight-time forward model on the same grid and compares. On
the day the fixture was made the largest difference was 1.26e-3 of the maximum
(`type1`) and 1.05e-3 (`type3`). That residual is TOPAS's own: it truncates each
convolution exponential where it has fallen to 1e-3 and renormalises, which
leaves about that much at the peaks. The test's bar is 1.5e-3. Its positive arm
plants two errors on the rietx side, DIFA's sign and α swapped with β, and each
must miss by more than 0.1 of the maximum (measured 0.37–0.40 and 0.85–0.86).

To regenerate: `python tests/data/tof/topas_synthetic/generate.py OUT`, run
TOPAS on `OUT/type1.inp` and `OUT/type3.inp`, strip `\r` from the two
`*_ycalc.txt` and gzip them here. A changed `.inp` is a changed writer, and the
test that regenerates the input says so first.
