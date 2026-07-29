# `pxrdref` vs WPEM on the WPEM benchmark datasets

Benchmark of this package — library plus agent-driven refinement — against
**WPEM** / PyXplore on the datasets published with

> B. Cao, Q. Zhang, Z. Feng, T. Zhang, J. Huang, L.-T. Weng, T.-Y. Zhang,
> *AI-Driven Structure Refinement of X-ray Diffraction*, arXiv:2602.16372.

Data from <https://github.com/Bin-Cao/PyWPEM/tree/main/CASES> (the paper's own
data-availability pointer). Structures from COD — WPEM ships none usable.
Everything here is reproducible: see [README.md](README.md).

---

## 0. TL;DR

<!--SUMMARY-->

---

## 1. What is actually being compared

This is the part that determines whether any number below means anything, so it
comes first.

### 1.1 WPEM's published fits contain no atomic structure

Every case notebook in `CASES/` calls `WPEM.XRDfit(...)` with a
`Lattice_constants` list and nothing else. There is no CIF argument, no atom
list, no occupancies. `EMBraggSolver` then gives **each reflection its own free
peak shape**. From WPEM's own shipped `WPEMPeakParas` file for PbSO4 (766 rows =
383 reflections × 2 emission lines):

| column | distinct values across 766 peaks |
|---|---|
| `wi` (integrated weight) | 766 |
| `Ai` (Lorentz/Gauss mixing Δ) | 764 |
| `L_gamma_i` (Lorentzian HWHM) | 761 |
| `G_sigma2_i` (Gaussian variance) | 703 |

So WPEM's PbSO4 refinement carries on the order of **3,000 free peak
parameters** (766 × 4), plus 3 cell parameters and a background fitted through
1,000 anchor points. It is a whole-pattern **decomposition** — the Le
Bail/Pawley family — not a Rietveld refinement. The paper is explicit that this
is the design, and compares against "FullProf profile matching (Le Bail fit)",
which is the right comparison class.

What follows from this, and matters for reading the paper's Fig. 2c: an
agreement factor from a 3,000-parameter decomposition and one from a
50-parameter structural model are not the same claim about a material, even
when they are the same arithmetic.

The freedom is not physically constrained either. Across the PbSO4 fit the
per-peak FWHM spans **0.05° to 9.05°** with a median of 0.176°; 171 of the 766
peaks (22 %) are broader than 0.5°. A 9°-wide "Bragg peak" is not an
instrumental line — those components are absorbing residual and diffuse
scattering. They carry only 2.7 % of the integrated weight, so the effect on
extracted intensities is small, but it is width freedom doing work that a
physical profile function is not allowed to do.

### 1.2 The agreement factors *are* directly comparable — verified

WPEM computes, in `PyXplore/EMBraggOpt/EMBraggSolver.py`:

```python
p_error.append(float(abs(y[j] - i_obser[j])))
wp_error.append((p_error[j] ** 2) / max(float(i_obser[j]), 1))
obs = sum(i_obser)
Rp.append(p_error_sum / obs * 100)
Rwp.append(np.sqrt(wp_error_sum / obs) * 100)
```

`i_obser` is the **raw** pattern, background included, and `y = bac + peaks`.
Substituting Poisson weights w = 1/max(y,1) into the textbook definition gives
Σ w·y² = Σ y, so WPEM's Rwp is exactly the conventional Rietveld Rwp — the same
quantity `pxrdref.optimize.statistics.compute_statistics` returns, on the same
raw profile, since these CSVs carry no esd column and `pxrdref` never subtracts
a background.

`verify_rfactors.py` checks this rather than asserting it. Feeding WPEM's own
shipped fitted profile and the raw pattern into both formulas:

| case | source | Rp % | Rwp % |
|---|---|---|---|
| PbSO4 | paper | 3.023 | 7.124 |
| | WPEM's formula, recomputed | 3.023 | 7.124 |
| | `pxrdref`'s formula | 3.023 | 7.124 |
| Tb2BaCoO5 | paper | 6.175 | 10.107 |
| | WPEM's formula, recomputed | 6.175 | 10.107 |
| | `pxrdref`'s formula | 6.175 | 10.107 |

Agreement to 0.00e+00 in both. **The R-factor comparison in this report is
sound; only the model behind it differs.**

### 1.3 No structures ship with the benchmark

WPEM's fits need none, so `CASES/` contains almost no structural models. The one
PbSO4 CIF in the repository (`Tutorial/class_4_simulation/data/PSO.cif`) is a
pymatgen P1 expansion of a **tripled, axis-permuted** cell labelled
`Pb3(SO6)2` — a = 6.985, b = 8.535, c = 16.120 Å, V = 961 Å³ ≈ 3 × anglesite.
It is not the PbSO4 model anyone refined.

Every structure used here therefore comes from COD, recorded with its ID in
`fetch_cifs.py`. Five of them are the entries WPEM itself started from — its
notebook starting cells reproduce COD 2300259 (gypsum), 9009573 (phosgenite),
9008411 (cerussite), 9008250 (laurionite), 1532765 (α-Ti) and 9012924 (β-Ti) to
every printed digit. Tb2BaCoO5 is not in COD at all and is built by Y→Tb, Ni→Co
substitution into the Immm R₂BaMO₅ structure type (COD 1001501, Y2BaNiO5);
the template's cation–oxygen distances were checked first (Ni–O 1.880 ×2 apical
and 2.189 ×4 equatorial — the expected MO₆ octahedron).

---

## 2. Results

<!--TABLES-->

---

## 3. Case notes

<!--CASES-->

---

## 4. What the benchmark says about `pxrdref`

<!--FINDINGS-->

---

## 5. What the benchmark says about the paper

<!--PAPER-->
