# Magnetic form factors computed for rietx: inputs, driver and checks

Every curve in `src/rietx/data/mff_computed.dat` (106 blocks) was computed for rietx from free-ion radial
wavefunctions. This folder holds what anyone with the two codes needs to regenerate each curve and check it. It is
not part of the wheel. The codes themselves are not in rietx.

## Files

| file | what |
|---|---|
| `curves.csv` | one row per curve in the data file, in its block order: key, family, kind (table/tail), code, Z, charge, and the code's inputs (RCN: orbitals, open shell, term, IREL, CORRF; GRASP: mass number, J-block CSF counts, start). `config` is the block's configuration line and `verdict` the bare-row note. |
| `mff_lib.py` | deck generator (RCN `in36`, GRASP2018 stdin), readers (RCN `tape2n`, GRASP `rwfn.out`), the radial transform, Brown's form and the blend |
| `regenerate.py` | the driver: write decks, run the codes, transform, write the long CSVs `write_data_file.py` reads; `--compare` a data file; `--gate` |
| `footing_gate.py` | the footing gate (rms/e over Brown's fitting grid), run on rietx's Brown rows |
| `brown_fit_errors.csv` | Brown's printed fit error e per row, ⟨j₀⟩ (ITC Vol. C Tables 4.4.5.1–4) and ⟨j₂⟩ (4.4.5.5–8) |
| `write_data_file.py` | formats the long CSVs into `mff_computed.dat` (selects, checks, rounds to `%.7f`; computes nothing) |

The generator reproduces the inputs of every curve **byte for byte**: 67 RCN `in36` decks and 39 × 5 GRASP2018
stdin files, 262 of 262 identical to the runs that produced the shipped data. So no deck is copied here.

## The codes

- **RCN**: R. D. Cowan's Hartree–Fock program, Mod 36.2.5 (2004-03-29), the Los Alamos source distributed with
  Cowan's permission from the Trinity College Dublin Cowan-code page. Its header says it "may be freely distributed
  gratis anywhere in the world, but may not be sold". Source SHA-256
  `9f4bf68301d6d37efd4ab22dbdd3e7c8c17ab8da742ac84a17dd99f230a89296`. Cowan, *The Theory of Atomic Structure and
  Spectra* (University of California Press, 1981), [doi:10.1525/9780520906150](https://doi.org/10.1525/9780520906150).
- **GRASP2018**: tag `2018-12-03` of `compas/grasp`, commit `2f51bbd`, MIT licence. C. Froese Fischer, G. Gaigalas,
  P. Jönsson & J. Bieroń, *Comput. Phys. Commun.* **237**, 184–187 (2019),
  [doi:10.1016/j.cpc.2018.10.032](https://doi.org/10.1016/j.cpc.2018.10.032). Programs used: `rnucleus`,
  `rcsfgenerate`, `rangular`, `rwfnestimate`, `rmcdhf`.
- **Toolchain of the shipped numbers**: gfortran 16.2.0 (conda-forge), OpenBLAS 0.3.34 / LAPACK 3.11.0, Python 3 with
  numpy and scipy, Apple arm64.

### Building

```sh
# RCN, from the unmodified source:
gfortran -O2 -std=legacy -fno-automatic -fdec-char-conversions -w -o rcn rcn.36.2.5.f
# GRASP2018: the release's Makefiles, with
#   FC_FLAGS="-O2 -fno-automatic -std=legacy -fallow-argument-mismatch -w"
#   LAPACK_LIBS="-llapack -lblas"
# then `make install` in src/lib and `make` in src/appl/{rnucleus90,rcsfgenerate90,rangular90,rwfnestimate90,rmcdhf90}.
```

### The pnl-dump patch, and the route that needs none

The shipped curves were first computed with a locally patched RCN. The patch made two changes, and neither is
needed any more:

1. **A dump of P_nl(r).** Thirteen lines at the top of subroutine `outpt`, after the SCF has converged: open a
   formatted file `pnldump` (append), write a `CONF` line (configuration, Z, ion stage, IREL, IHF, orbital count,
   mesh size), an `ORB` line per orbital (index, label, occupation, node count, eigenvalue), then r(i) and P_nl(i) for
   every orbital at `1pe24.15`, then `END`. Nothing in the SCF was touched.
   **Replaced by reading `tape2n`**, which unpatched RCN writes anyway: with `NORBPT = -9` on the control card its
   end-of-run record holds r and every P_nl(r) on RCN's mesh in double precision (`mff_lib.read_tape2`; the layout
   is the `write (2)` statement of `outpt`). Over the 371 RCN runs behind the data, `tape2n` and `pnldump` agree to
   4.5 × 10⁻¹³, the 16-digit print.
2. **Six Hollerith constants.** Six `data` statements put a quoted character into an INTEGER (`data jhlf/'f'/`,
   `jhuF/'F'/` in three subroutines, plus `jhlg`, `jhuG` in two), which gfortran refuses. The patch rewrote them as
   `1hf`, `1hF`, `1hg`, `1hG`. They are the letters RCN looks for in an LS-term card, so term-specific runs depend
   on them. **Replaced by the compiler flag `-fdec-char-conversions`**, which accepts the original statements.

**Proof:** the unmodified source, built as above, run from the decks in `curves.csv` through `regenerate.py`, gives
back all 106 curves, and `write_data_file.py` turns them into a file **byte-identical** to the shipped
`mff_computed.dat` (SHA-256 `b500a4784c6f7610b965a1a9bdcf0a3d594d21f997715af9196930b8daf917ab`). The per-order
match against the shipped values is in "Checks" below. (The neutral Pd table joined on 2026-11-23; its deck is
byte-identical to the data job's, and its curve matches the data job's to 5 × 10⁻⁹, the `%.8f` print.)

## Footing of each family

| family | curves | code and footing |
|---|---|---|
| 3d, 4d tails (52 rows) | ⟨j₀⟩, ⟨j₂⟩ from s_end = 1.5 | RCN Hartree–Fock (IREL = 0, CORRF = 0), the configuration identified behind each Brown row: Hund LS term for the ions; configuration average where that matched (bare V, Mn, Fe, Co, Cu, Y; Ti³⁺, Sc²⁺, V⁴⁺ and the other single-term d¹, d⁹, d¹⁰ shells); bare Ti in the non-Hund term 3d²4s² ¹G listed by Clementi & Roetti (1974). Bare Cr and Ni match no configuration tried: their tails use the best candidate, and their blocks say so. |
| neutral Mo, Tc, Ru, Rh, Pd (tables) | ⟨j₀⟩, ⟨j₂⟩, ⟨j₄⟩, s = 0–6 | RCN HF, Hund term of the neutral ground configuration (Cowan 1981 Table 4-3): 4d⁵5s ⁷S, 4d⁵5s² ⁶S, 4d⁷5s ⁵F, 4d⁸5s ⁴F; for Pd, whose 4d¹⁰ ¹S ground state has no open shell to carry a moment, the lowest magnetic configuration 4d⁹5s ³D (the d⁹s card is the G²(d, s) term alone; [ruled 2026-11-23](https://github.com/yue-here/rietx/pull/1806#issuecomment-7115570833)) |
| ten high-charge 4d ions (tables) | ⟨j₀⟩, ⟨j₂⟩, ⟨j₄⟩, s = 0–6 | RCN Hartree–Fock-relativistic (IREL = 1, CORRF = 1), configuration average |
| 4f (21 tails + Pr³⁺ table) | from s_end = 1.2 | GRASP2018 Dirac–Fock, single configuration [Kr]4d¹⁰5s²5p⁶4fⁿ, average level: EOL over every level of every J block with standard weights, the generalised average energy of Freeman & Desclaux (1979); finite nucleus, mass number A |
| 5f (16 tails + Pu³⁺ table) | from s_end = 1.5 | as 4f, [Xe]4f¹⁴5d¹⁰6s²6p⁶5fⁿ (Desclaux & Freeman 1978) |

An LS-term card gives the term energy relative to the configuration average in Slater integrals (RCN write-up
§ II-G): for dⁿ the Hund term from the Racah forms, for dⁿs the high-spin coupling adds −(S_core/5)G²(d, s), and
d² ¹G is (50/441)F² + (15/441)F⁴. A GRASP run whose `start` names another key starts from that key's converged
`rwfn.out` (the Thomas–Fermi estimate failed there); the driver runs the start first. The start matters at the
10⁻⁶ level (Gd³⁺ from another ion's orbitals moves ⟨j₀⟩ by 1.2 × 10⁻⁶), so it is part of the input.

## The transform

The radial function is splined (cubic, scipy `CubicSpline`) from the code's mesh onto a uniform mesh of
2 × 10⁻⁴ bohr, cut two mesh points past the last point where the density exceeds 10⁻¹⁴, and integrated by Simpson's
rule:

  ⟨j_n⟩(s) = ∫ ρ(r) j_n(4π s r a₀) dr / ∫ ρ(r) dr,  a₀ = 0.529177 Å,

with ρ = P_nl² for RCN, and for Dirac–Fock ρ = Σ_j (2j + 1)(P² + Q²) / Σ_j (2j + 1) over j = l ∓ ½. s runs over
0–6 at 0.01 (0.005 for the ten 4d tables, of which the data file keeps every second point).

## The blend

A tail starts where Brown's fit of the row ends (s_end). rietx returns Brown's value up to s_end, the computed
curve past s_end + 0.2, and between them (1 − w)·fit + w·tail with the C² quintic w = 10t³ − 15t⁴ + 6t⁵,
t = (s − s_end)/0.2 (`mff_lib.blend`; rietx's own copy is `_blend_onto_tail` in
`crystallography/magnetic/form_factor.py`).

## Regenerating and checking

```sh
export RCN_EXE=<rcn executable> GRASP_BIN=<dir with the GRASP programs>
python regenerate.py --work <scratch> --out <curves dir> --keys Mn2+ Ru4+ Gd3+ \
    --compare ../../src/rietx/data/mff_computed.dat --gate      # a few curves
python regenerate.py --work <scratch> --out <curves dir> --code RCN    # all 67 RCN curves, ~4 min
python regenerate.py --work <scratch> --out <curves dir> --code GRASP  # all 39 GRASP curves, ~2 min
python write_data_file.py --curves <curves dir> --d32 <curves dir>/d32 --out mff_computed.dat
python footing_gate.py --curves <curves dir>                           # needs rietx importable
python regenerate.py --decks-only --work <dir>                         # the inputs alone
```

## Checks

**Regeneration** (unmodified RCN, the GRASP2018 build above), max |regenerated − shipped| per order:

| curve | block | ⟨j₀⟩ | ⟨j₂⟩ | ⟨j₄⟩ |
|---|---|---|---|---|
| Mn²⁺ (RCN HF, 3d⁵ ⁶S) | tail, s = 1.5–6 | 5.5e-8 | 5.5e-8 | — |
| Ti (RCN HF, 3d²4s² ¹G) | tail, s = 1.5–6 | 5.5e-8 | 5.5e-8 | — |
| Ru⁴⁺ (RCN HFR, 4d⁴ average) | table, s = 0–6 | 5.0e-8 | 5.0e-8 | 5.0e-8 |
| Gd³⁺ (GRASP DF, Thomas–Fermi start) | tail, s = 1.2–6 | 5.5e-8 | 5.5e-8 | — |
| Ho³⁺ (GRASP DF, started from Dy³⁺, from Dy²⁺) | tail, s = 1.2–6 | 5.5e-8 | 5.5e-8 | — |

These are the file's `%.7f` rounding (5 × 10⁻⁸, plus 5 × 10⁻⁹ where the source CSV was printed at `%.8f` first). The
regenerated values equal the original computation to every printed digit, and the whole file regenerates
byte-identical.

**Against the published curves the footings come from** (computed before rietx shipped them):

- 3d/4d: the curves reproduce Brown's rows to his printed fit error: median 100·rms/e = 1.03 (3d) and 1.02 (4d) over
  his grid; 99 row-orders of the full-range study at median 1.00, range 0.89–1.86.
- 4f: Freeman & Desclaux (1979) Table 7, 1508 of 1511 cells within 0.6 × 10⁻⁴ (the 3 others are print anomalies);
  their Tables 4/5 ⟨r²⟩ for all 21 ions to the printed precision.
- 5f: Desclaux & Freeman (1978) Table 6, U³⁺ and U⁴⁺ 167 of 168 cells within 1.23 × 10⁻⁴ (U⁴⁺ ⟨j₀⟩(0.25) is
  misprinted 0.3000), Pu³⁺ 84 of 84 within 5.3 × 10⁻⁵. Brown's printed Pu³⁺ rows fit the Pu⁵⁺ curve, which is why
  Pu³⁺ ships as a whole table.

**Convergence:** the transform against an exact Slater-orbital answer ≤ 4.5 × 10⁻⁹; RCN TOLEND 5 × 10⁻⁸ against
5 × 10⁻¹¹ ≤ 1.7 × 10⁻⁸; GRASP's default radial grid against a second grid ≤ 5.9 × 10⁻⁸ beyond s = 1.5. Physics,
for scale: HFR against Dirac–Fock differs by up to 1.5 × 10⁻⁴ beyond s = 1.5.

### Footing gate

`footing_gate.py` scores each Brown row rietx carries against the computed curve its tail comes from:
100·rms(fit − computed)/e over Brown's fitting grid (ITC Vol. C p. 461: 0–1.5 at 0.05 for 3d/4d; 0–0.5 at 0.05 then
0.1 to 1.2 for rare earths, to 1.5 for actinides). On the footing Brown fitted, the ratio is about 1; **above 1.5 it
flags a footing mismatch**. The distance at s_end alone is no gate: a 7-parameter fit can end 2–4 e from a curve it
matches everywhere else. On the shipped curves and rietx's `_J0`/`_J2` (89 rows, median 1.02), four flags:

| row | ⟨j₀⟩ | ⟨j₂⟩ | reading |
|---|---|---|---|
| Ni (bare) | 2.51 | 4.76 | unmatched: no configuration or Clementi–Roetti term tried reproduces it |
| Cr (bare) | 3.10 | 4.06 | unmatched, as Ni |
| Zr⁺ | 1.01 | 1.78 | marginal; the tail is on the identified configuration 4d³ ⁴F |
| Co²⁺ | 1.72 | 1.27 | marginal; the tail is on 3d⁷ ⁴F (its ⟨j₄⟩ row, not carried by rietx, scores 1.84) |

Pu³⁺ and Pr³⁺ are not scored: they ship as computed tables, not Brown rows.

## References

- P. J. Brown, "Magnetic form factors", *International Tables for Crystallography* Vol. C, 3rd ed., § 4.4.5,
  pp. 454–461 (Kluwer, 2004); chapter 4.4,
  [doi:10.1107/97809553602060000594](https://doi.org/10.1107/97809553602060000594).
- A. J. Freeman & J. P. Desclaux, *J. Magn. Magn. Mater.* **12**, 11–21 (1979),
  [doi:10.1016/0304-8853(79)90328-7](https://doi.org/10.1016/0304-8853(79)90328-7).
- J. P. Desclaux & A. J. Freeman, *J. Magn. Magn. Mater.* **8**, 119–129 (1978),
  [doi:10.1016/0304-8853(78)90111-7](https://doi.org/10.1016/0304-8853(78)90111-7).
- E. Clementi & C. Roetti, *At. Data Nucl. Data Tables* **14**, 177–478 (1974),
  [doi:10.1016/S0092-640X(74)80016-1](https://doi.org/10.1016/S0092-640X(74)80016-1).
- R. D. Cowan, *The Theory of Atomic Structure and Spectra* (University of California Press, 1981),
  [doi:10.1525/9780520906150](https://doi.org/10.1525/9780520906150).
- C. Froese Fischer, G. Gaigalas, P. Jönsson & J. Bieroń, *Comput. Phys. Commun.* **237**, 184–187 (2019),
  [doi:10.1016/j.cpc.2018.10.032](https://doi.org/10.1016/j.cpc.2018.10.032).
