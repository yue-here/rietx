# guiLLeMot example patterns — an external-data exercise

**2026-07-29. Not part of the package, not run by CI, not a WP.** Every
diffraction file in the `examples/` folder of
[datalab-org/guillemot](https://github.com/datalab-org/guillemot) (MIT; a 2025
LLM-hackathon project that drives TOPAS from a chat interface) refined with
pxrd-refine, plus an audit of the non-refinement scaffolding that fed it.

Kept because two of those folders ship a **converged TOPAS input and its
output** — an independent cross-check on real laboratory and synchrotron data
that this repository's own acceptance suites (NIST, GSAS-II, IUCr) do not
provide.

## The data is not vendored here

It belongs to another project. Clone it and point the scripts at it:

```sh
git clone --depth 1 https://github.com/datalab-org/guillemot
export GUILLEMOT_EXAMPLES=$PWD/guillemot/examples
```

Then, from this directory (the scripts import a sibling `common.py`):

```sh
../../.venv/bin/python run_fesb.py        # and run_nacoo2 / run_mnsb_synch /
                                          # run_mnsb34 / run_hl2
../../.venv/bin/python audit_tools.py     # the four provenance checks
../../.venv/bin/python audit_figs.py      # their figures, light + dark
../../.venv/bin/python build_reports.py   # inline the plots into the reports
```

Everything under `out/` is committed, so the numbers below are readable without
re-running anything.

## What is here

| | |
|---|---|
| `common.py` | data path, cell/atom builders, the result summariser |
| `run_fesb.py` | Fe₁₊ₓSb, the one dataset with a converged TOPAS answer to check |
| `run_nacoo2.py` | P2-Naₓ CoO₂; includes the determinability checks on Biso and the Na occupancies |
| `run_mnsb_synch.py` | Mn₁₊ₓSb at Diamond I11 — capillary absorption + Stephens strain |
| `run_mnsb34.py` | MnSb + Sb two-phase, QPA, Stephens under bounded LM |
| `run_hl2.py` | the unidentified pattern: peak table + a Pawley description |
| `peaks.py` | raw-pattern overview and peak lists for all five |
| `index_hl2.py` | a ~60-line pair-seeded two-parameter autoindexer |
| `match_hl2.py` | a 36-cell phase-position screen |
| `audit_tools.py` | provenance checks A–D (see below) |
| `audit_figs.py`, `build_reports.py` | the two report figures; the HTML build |
| `guillemot_report.html` | report 1 — the refinements, self-contained |
| `guillemot_audit.html` | report 2 — where the inputs came from |
| `out/` | plots, per-run logs, obs/calc/diff columns, the HL2-1 peak table |

## Results, in one table

| Folder | Rwp | Outcome |
|---|---|---|
| `FeSb_19RBM` | 4.07 % | vs TOPAS: a −101 ppm, c −76 ppm, occ(Fe2) 0.8 σ, Rwp −0.02 pts, Rexp −0.003 pts, DW +0.003 |
| `MnSb_34_impure` | 5.39 % | MnSb + Sb identified from the pattern; Sb ≈ 2 wt % |
| `KD1-2_5_NaCoO2` | 3.07 % | March–Dollase r = 0.496(15); Biso and Na occupancies **not** determinable |
| `MnSb_33_BM` | 12.47 % | cell −200/−323 ppm, occ(Mn2) 0.02 σ vs TOPAS; profile disagrees (TOPAS 8.45 %) |
| `NaCoO2` | — | `.inp` only; its `Out_CIF_STR("KD1-2_riet_01.cif")` is what pairs it to `KD1-2_5` |
| `HL2-1` | — | unidentified; not cubic/tetragonal/hexagonal. Deliverable is `out/HL2-1_peaks.txt` |

## What it says about *this* package

Five things worth having if anyone comes back:

1. **An independent implementation check on real data.** On the one dataset with
   a converged reference, pxrd-refine lands within 100 ppm on the cell, inside
   1 σ on a refined site occupancy, and within 0.02 points on Rwp, Rexp and
   Durbin–Watson. The single disagreement is Biso (0.51 vs 1.12 Å²), traceable
   to background order and the absence of any flat-plate absorption term in
   either model.
2. **`solver="lm"` earned its keep outside the test suite.** The Stephens cone
   as a linear inequality separated a *real* anisotropy from a *fitted* one on
   two samples of the same material: on MnSb_34 the constrained fit is better
   than TRF (5.39 % vs 5.51 %) and the guard falls silent; on MnSb_33 enforcing
   the cone throws away nearly all of the improvement (17.1 → 16.6 % against
   TRF's 12.5 %), i.e. that width anisotropy is not Stephens strain at all.
   Same block, same seed, opposite verdicts.
3. **There is no user-level equality tie between two parameters.** TOPAS's
   `total_beq` (one Biso shared by three sites) had to be emulated with a
   fixed-point loop in `run_fesb.py` — refine one, copy onto the others, refit,
   7 cycles. `ParameterTable` has `AffineTie` internally; nothing exposes it.
4. **The instrument ⊕ sample width split fails silently without a standard.**
   Freeing both gives ρ = 1.000 between `instrument.profile.w` and
   `phases.0.gauss_size`. The correlation guard does report it, but only after
   the fit; there is no check that refuses the combination up front.
5. **`Geometry.goniometer_radius_mm` defaults to 217.5 mm and carries a
   systematic no esd reports.** Measured on FeSb over 180–320 mm: Rwp moves
   0.029 points (the data cannot identify R), the specimen displacement absorbs
   the change by a factor of 4.6, and the residue lands on the cell as ≈ ±85 ppm
   — larger than the refinement's own 1 σ, and the same size as the TOPAS
   agreement in point 1. Worth a diagnostic when a lab cell is quoted tighter
   than that and no radius was supplied.

## The audit checks

`audit_tools.py`, log in `out/audit_full.txt`:

- **A** — cost of the assumed goniometer radius (above).
- **B** — the Sb impurity cell was recalled from memory, not read from a file.
  Restarting more than ~2 % off in `a` does not recover: the refinement drives
  the minor phase to its bounds and reports 0.0–0.2 wt %, warning only through
  a 0.5-point Rwp penalty. Its `z` is not measured at all (0.2358 and 0.2642
  give identical Rwp, cell and weight fraction).
- **C** — the autoindexer covers two-parameter metrics only. Complete synthetic
  peak lists from single-phase orthorhombic/monoclinic compounds score 50–60 %,
  against 82–100 % for genuinely tetragonal/hexagonal ones. HL2-1 scores 69 %,
  which is why the "at least two phases" claim in report 1 was withdrawn.
- **D** — the phase screen matches positions and ignores structure factors.
  Pointed at MnSb_34, whose answer is known, the truth separates only on the
  *joint* criterion (share of observed intensity indexed **and** share of the
  candidate's own lines seen); on the first column alone NaSb wins with 390
  predicted lines and 9 % of them present.
