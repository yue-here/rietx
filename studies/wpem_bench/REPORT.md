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

Running eight unfamiliar datasets through the package end-to-end, in agent mode,
surfaced six defects and confirmed four design decisions. Everything here was
hit, not inspected for.

### 4.1 Defects, roughly in order of how much they cost

**(a) Real-world CIFs break stage compile since v1.0.** Six of the eleven COD
entries used here put a *site label* in `_atom_site_type_symbol` — `O1`, `O2`,
`Cl1` — where the dictionary wants an element with an optional charge. This is
endemic in AMCSD-derived entries. `Structure.from_cif` passes the value through,
and `crystallography/dispersion.py::normalize_element` then raises

```
KeyError: cannot read an element symbol from species 'O1'
```

at `compile_model`, because its regex is `^([A-Za-z]{1,2})(\d*[+-])?$`. **This
is a v1.0 regression in reach, not in code**: those files loaded fine while
`Source.dispersion` defaulted to `None`, and turning anomalous scattering on by
default (WP-1001) made a previously-unreached lookup mandatory. The failure is
also late and unhelpful — it happens at the first `fit()`, not at
`from_cif`, and names a species rather than a file or a site.
Suggested fix: strip a trailing site index in `normalize_element` (or normalise
at CIF read, with a diagnostic recording the substitution — that is what
`bench.normalize_cif_species` does here as a workaround).

**(b) A Le Bail refinement needs an outer fixed-point loop, and nothing says
so.** One call to `fit(mode="lebail")` walks the staged plan once. But the
extracted per-hkl intensities are frozen inside each least-squares run (by the
frozen-per-stage invariant), so the intensities and the profile can only
converge *jointly* by alternating. Measured on PbSO4:

| pass | Rwp | U | V | W |
|---|---|---|---|---|
| 1 | 20.756 % | 0.0045 | **+0.0615** | 0.0064 |
| 2 | 11.372 % | 0.0489 | −0.0577 | 0.0187 |
| 3 | 10.262 % | 0.0372 | −0.0544 | 0.0175 |
| 4 | 10.247 % | 0.0349 | −0.0529 | 0.0172 |

A caller who runs `fit(mode="lebail")` once and believes it is off by a factor
of two in Rwp and holds a Caglioti V of the wrong sign. Neither the docstring
nor AGENT_PROTOCOL §2 (which does say "structure-free first when you can")
mentions the requirement. Suggested fix: iterate internally when
`mode == "lebail"` until Rwp stops moving, or say so in §2. Note the loop is
**not monotone** — pass 2 on Tb2BaCoO5 came back *worse* than pass 1 — so
whatever does the iterating has to keep the best node, not the last.

**(c) `lab_bragg_brentano` frees a degenerate pair that its own protocol doc
warns about.** Its `zero_disp` stage frees `zero_shift` and
`sample_displacement` together, and AGENT_PROTOCOL §3 lists exactly that pair
("zero shift · sample displacement · cell", "do not free the second member of a
group without checking the first is pinned by something outside the fit").
Nothing pins either one in these datasets. Measured on Tb2BaCoO5:

| | zero_shift | sample_displacement | cell error vs WPEM |
|---|---|---|---|
| both freed | 0.232 ± 0.220° | 0.391 ± 0.392 mm | 400–800 ppm |
| zero only | 0.0132 ± 0.0032° | held | **43–145 ppm** |

Two parameters whose esds equal their own values is one parameter reported
twice, and it moved the cell. Suggested fix: `lab_bragg_brentano` should free
zero alone by default and offer displacement as an opt-in, or the plan should
carry the caveat in its docstring.

**(d) No divergence guard.** A starting cell 3 % off puts every peak outside its
frozen evaluation window. The result is not an error — it is
`status="converged"` at **Rwp = 7 225 %** (Ti-15Nb from WPEM's own starting
cells) and **Rwp = 2.6 × 10⁵ %** for a three-phase Le Bail, with `zero_shift`
and all five profile terms pinned to bounds. AGENT_PROTOCOL §1 states the ≈1 %
precondition and Layer 2 is designed to answer `reindex_or_recheck_cell`, but at
that Rwp the report is never reached and a batch caller sees "converged".
Suggested fix: a `MODEL_FAR_FROM_DATA` diagnostic when Rwp exceeds some
obviously-broken threshold after a stage, naming window coverage as the likely
cause; a Le Bail run whose extracted intensities grow without bound deserves its
own guard.

**(e) `PreferredOrientation` is not exported at package level.**
`pr.schemas.PreferredOrientation` works; `pr.PreferredOrientation` raises
`AttributeError`. It is a user-constructed schema — you cannot enable texture
without it — and every other such schema (`Atom`, `Cell`, `Phase`, `Parameter`)
is re-exported. Worth catching before the WP-1003 API freeze.

**(f) March-Dollase divides by zero.** `model/preferred_orientation.py:92–93`
emits `RuntimeWarning: divide by zero encountered in divide` and
`invalid value encountered in power` when `r` underflows, despite the softplus
bound that is supposed to keep it strictly positive. Seen on the Ti-15Nb
three-phase fit where one phase's scale went to zero.

### 4.2 Confirmed by use

- **The FitReport found an impurity phase.** On Tb2BaCoO5 the single-phase
  Layer-0 unmatched-observed list read 23.82 / 23.94 / 24.08 / 24.20 / 27.78°,
  which is witherite 111 / 021 / 002 at Cu Kα — unreacted BaCO₃, the standard
  leftover of a Ba-bearing solid-state synthesis. Adding it took Rwp from
  13.039 % to 12.353 % and removed a region carrying 7.1 % of χ². The report
  identified it; no human looked at a plot first.
- **The esds refuse numbers that should be refused.** On the Ti-15Nb α/α′ split
  the package returns 84 ± 31 wt % / 16 ± 31 wt % — an esd larger than the
  answer, i.e. "this is not measured". WPEM reports 48.32 : 46.19 with no
  uncertainty. Both are fits to the same data; only one of them says what it
  does not know.
- **`BACKGROUND_ABSORPTION` earned its place.** The auto P-spline on PbSO4 takes
  53 coefficients, correlates at ρ > 0.99 between neighbours, emits 1 326
  `HIGH_CORRELATION` warnings and reports R² = 0.56 of a Biso column absorbable
  by the background block. Switching to the auto-order Chebyshev is what made
  the PbSO4 refinement trustworthy, and the diagnostic is why the switch
  happened.
- **The `direction="both"` sequential check is the only thing in either package
  that separates a measured trajectory from an ordering artefact** — see §3.

---

## 5. What the benchmark says about the paper

Points that a reader reproducing this work should know. Several are internal
inconsistencies between the paper, its shipped outputs, and its own code.

**(a) The paper's headline comparison is between models of very different
size.** Fig. 2c sets WPEM's R-factors against FullProf profile matching and
TOPAS FPA. WPEM's PbSO4 fit carries ~3 000 free per-peak parameters (§1.1); a
FullProf Le Bail fit carries a Caglioti triple and a handful of shape terms. The
text promises to report "the number of free profile parameters" alongside the
R-factors, and that number does not appear in the manuscript body. Without it,
lower R is not evidence of a better model — it is evidence of a larger one.

**(b) The Egyptian make-up mass fractions in the paper and in the shipped
output disagree, on two of five phases.** Paper text: 12.53 / 18.53 / 32.02 /
9.69 / 27.23 % for gypsum / phosgenite / cerussite / galena / laurionite.
`CASES/EgyptianMakeup/.../MassFraction_estimate_2026.2.8_17.5.txt`: 12.66 /
22.28 / 34.19 / **1.68** / 29.20 %. Galena differs by a factor of 5.8. The
shipped `LatticeConstances` file also gives galena a = 5.97898 Å against the
paper's own 5.9388 Å and a literature 5.9362 Å — a +0.7 % error on a cubic
lattice parameter, which for PbS is far outside anything a fit should produce.

**(c) The Ru–Mn case's shipped output does not match its description.** The
paper describes screening Ru site occupations in a **3 × 3 supercell** deposited
as CCDC 2530452 (accessed 2026-02-12). The shipped
`LatticeConstances_2023.6.16_11.43.csv` is a cubic a = 9.40851 Å phase plus a
tetragonal a = 4.41115, c = 3.04844 Å phase — bixbyite (Mn,Ru)₂O₃ and rutile
RuO₂ in their ordinary cells, not a supercell (which would be ≈28 Å) — and is
dated **2023-06-16**, three years before the deposition it is attributed to.
The paper also calls the parent "orthorhombic Mn₂O₃"; the shipped cell is cubic.

**(d) The wavelengths in the text and in the code differ.** The paper states
Cu Kα1 = 1.540560, Kα2 = 1.544330 Å (Bearden). Every case notebook passes
`wavelength = [1.540593, 1.544414]`. That is 21 ppm on Kα1 and 54 ppm on Kα2 —
a systematic scale factor on every reported cell, in a paper that quotes cells
to 5 decimal places. (`pxrdref`'s `"CuKa"` is 1.5405929 / 1.5444274, i.e. on the
notebooks' scale for Kα1 and 9 ppm off it for Kα2.)

**(e) Credit where it is due: WPEM's convergence radius is genuinely larger.**
Its α-Ti starting cell is 3.0 % from its own refined answer and it walks there.
`pxrdref` cannot: freezing each reflection's evaluation window at stage compile
is what keeps the residual smooth for the analytic Jacobian, and it costs
exactly this. Whether the trade is worth it depends on whether you have a
starting model — but for the paper's stated use case, taking hypotheses from a
generative model where the cell may be several percent off, a large convergence
radius is the right property to optimise and WPEM has it.

**(f) The R-factor advantage does not survive parameter counting.** On PbSO4,
WPEM's 7.124 % from ~3 000 free peak parameters is matched by 7.13 % from a
51-parameter structural refinement here. On Tb2BaCoO5 WPEM is genuinely ahead
(10.107 % vs 12.353 %), which is what one expects when 131 reflections each get
their own shape and the competing model has to explain intensities with 61
parameters and a substituted structure.
