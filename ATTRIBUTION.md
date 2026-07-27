# Attribution

pxrd-refine is an independent implementation, but its design and mathematics
draw on published literature and on existing open-source software. This file
records every source of inspiration or data, its license, and exactly what was
used. Sources under GPL were **studied only**; no GPL code has been ported.

## Algorithms and equations (literature — cited in docstrings and docs)

- Rietveld, H. M. (1969). *J. Appl. Cryst.* 2, 65–71 — the profile refinement method.
- Caglioti, Paoletti & Ricci (1958). *Nucl. Instrum.* 3, 223–228 — U,V,W width law.
- Thompson, Cox & Hastings (1987). *J. Appl. Cryst.* 20, 79–83 — TCH pseudo-Voigt.
- Stephens, P. W. (1999). *J. Appl. Cryst.* 32, 281–289 — phenomenological model of
  anisotropic peak broadening; the rank-4 S_HKL invariants and the per-Laue-class
  term counts of its Table 1. The allowed subspace here is *derived* from the
  space-group operators (`crystallography/stephens.py`), not transcribed from the
  table — the table is the independent check.
- Popa, N. C. (1998). *J. Appl. Cryst.* 31, 176–180 — the equivalent
  strain-tensor formulation of the same anisotropy (concept reference; the
  phenomenological parameterisation is what is implemented).
- Weideman, J. A. C. (1994). *SIAM J. Numer. Anal.* 31, 1497–1518 — rational
  (FFT-coefficient) approximation of the complex error function w(z); the
  N=32 algorithm behind the shared, backend-agnostic Faddeeva in the opt-in
  true-Voigt profile (implemented from the paper, no code ported).
- Armstrong, B. H. (1967). *J. Quant. Spectrosc. Radiat. Transfer* 7, 61–88 —
  the Voigt profile as Re[w(z)] and its Gaussian/Lorentzian limits.
- Finger, Cox & Jephcoat (1994). *J. Appl. Cryst.* 27, 892–900 — axial-divergence asymmetry.
- Waasmaier & Kirfel (1995). *Acta Cryst.* A51, 416–431 — 5-Gaussian form factors.
- McCusker et al. (1999). *J. Appl. Cryst.* 32, 36–50 — Rietveld refinement guidelines.
- Toby, B. H. (2006). *Powder Diffraction* 21, 67–70 — agreement indices.
- Bérar & Lelann (1991). *J. Appl. Cryst.* 24, 1–5 — serial-correlation esd correction.
- Hill & Howard (1987). *J. Appl. Cryst.* 20, 467–474 — QPA scale-factor relation.
- Le Bail, Duroy & Fourquet (1988). *Mater. Res. Bull.* 23, 447–452 — Le Bail intensity extraction.
- Coelho, A. A. (2005). *J. Appl. Cryst.* 38, 455–461; (2018) 51, 210–218 & 428–435 —
  minimizer design ideas (bound-constrained solves, adaptive Marquardt). Algorithms
  reimplemented from the papers; TOPAS itself is proprietary and was not consulted as code.
- Eilers, P. H. C. (2003). *Anal. Chem.* 75, 3631 — Whittaker smoother.
- Eilers & Marx (1996). *Stat. Sci.* 11, 89–121 — P-spline penalized regression
  (the co-refined background's second-difference penalty rows).
- Baek et al. (2015). *Analyst* 140, 250 — arPLS baseline estimation.
- Ryan et al. (1988). *Nucl. Instrum. Meth.* B34, 396 — SNIP background clipping.
- David, W. I. F. (2004). *J. Res. NIST* 109 — cumulative-χ² diagnostics.
- Hill & Flack (1987). *J. Appl. Cryst.* 20, 356–361 — Durbin-Watson statistic in Rietveld refinement.
- Andreev, Y. G. (1994). *J. Appl. Cryst.* 27, 288–297 — noted as the refinement of the
  Bérar-Lelann estimator's white-noise bias (paywalled; concept referenced, formula not reproduced).
- Hamilton, W. C. (1965). *Acta Cryst.* 18, 502–510 — R-factor ratio significance test.
- Schwarz, G. (1978). *Ann. Stat.* 6, 461–464 — Bayesian information criterion.
- Wilson, A. J. C. (1963). *Mathematical Theory of X-ray Powder Diffractometry*;
  Klug & Alexander (1974), ch. 5 — Bragg-Brentano displacement/transparency aberrations.
- Hölzer et al. (1997). *Phys. Rev. A* 56, 4554–4568 — Cu Kα/Kβ emission wavelengths and intensity ratios (also Co/Cr/Fe Kα, for WP-0507).
- Bearden, J. A. (1967). *Rev. Mod. Phys.* 39, 78–124 — W Lα1 wavelength (contamination check).
- Deslattes et al. (2003). *Rev. Mod. Phys.* 75, 35–99 — X-ray transition energies/wavelengths (Mo/Ag Kα, for WP-0507; named at `schemas/instrument.py:334`).
- Sabine, T. M. (1985). *Aust. J. Phys.* 38, 507–518 — extinction in polycrystalline materials.
- Sabine, T. M. (1988). *Acta Cryst.* A44, 368–373 — a reconciliation of the Zachariasen and Darwin extinction theories (the Bragg·sin²θ + Laue·cos²θ blend, WP-0506).
- Sabine, Von Dreele & Jørgensen (1988). *Acta Cryst.* A44, 374–379 — extinction in time-of-flight neutron powder diffraction (the same model applied to a Rietveld refinement).
- Cheary & Coelho (1992). *J. Appl. Cryst.* 25, 109–121 — the fundamental-parameters convolution approach to line profiles (v2-fenced; DESIGN note only).
- Mendenhall et al. (2022). *J. Appl. Cryst.* 55, 1362–1367 — NIST fundamental-parameters → pseudo-Voigt term mapping (the lighter-weight FPA route in the DESIGN note; concept only, not implemented).
- Belsley, Kuh & Welsch (1980). *Regression Diagnostics*, Wiley — scaled-Gram
  condition number as a collinearity diagnostic (FitReport Layer-1 gate).
- Brindley, G. W. (1945). *Phil. Mag.* 36, 347–369 — particle-absorption
  (microabsorption) correction of QPA weight fractions, incl. the
  fine/medium/coarse powder classification (µD < 0.01 / 0.01–0.1 / > 0.1).
- Taylor, J. C. & Matulis, C. E. (1991). *J. Appl. Cryst.* 24, 14–17 —
  practical application and limits of the Brindley correction in Rietveld QPA.
- McMaster, W. H., Del Grande, N. K., Mallett, J. H. & Hubbell, J. H. (1969).
  *Compilation of X-ray Cross Sections*, UCRL-50174 Sec. II Rev. 1 — the
  photon-atom cross sections behind per-phase linear attenuation coefficients.
- Hubbell, J. H. & Seltzer, S. M. (1995). *NISTIR 5632* — NIST mass
  attenuation coefficients; used as independent test anchors for µ/ρ.
- Rodríguez-Carvajal, J. — *Quantitative Phase Analysis with the Rietveld
  Method* (ILL/FullProf school notes) — the iterative Brindley scheme and the
  quadratic representation 1 − 1.450x + 1.426x² of Brindley's τ table
  (validation anchor only; no code).
- Lutterotti, L. — *QPA methods developments* course notes (MAUD) — the
  exponential fit to Brindley's τ table (validation anchor only; no code).

## Open-source software studied or used

| Project | License | Relationship |
|---|---|---|
| lmfit | BSD-3 | **API inspiration**: the Parameter model (value/vary/min/max/expr). No code ported. |
| GSAS-II | custom Argonne royalty-free (grant-back clause) | **Behavioral reference** for conventions and validation goldens (e.g. the Sabine extinction parameterization and its Laue-series coefficients, WP-0506). Concepts and goldens are freely usable; the license is *not* a standard BSD — verbatim porting carries attribution and an upstream grant-back obligation, so no code is ported. |
| CrysPy | MIT | Reference for pure-Python Rietveld mathematics. No code ported. |
| MAUD | BSD-3 | Reference for texture / residual-stress methods (studied for the v2-fenced spherical-harmonics texture path). No code ported. |
| CrysFML / CrysFML2008 | LGPL-3.0-or-later + ILL no-military-use clause | Studied (concepts only — the LGPL and the ILL clause both bar a port into an MIT core). **No code ported.** |
| powerxrd | MIT | Reference for a minimal quick-look powder-XRD API surface. No code ported. |
| Dans_Diffraction | Apache-2.0 | Reference for scattering computations. No code ported. |
| pymatgen | MIT | Cross-check for structure factors/multiplicities in tests. |
| cctbx | BSD-style | Cross-check for symmetry constraints in tests. |
| EasyDiffraction | BSD-3 | Architecture reference (schema-driven design). No code ported. |
| pybaselines (derb12) | BSD-3 | **Algorithm reference** for arPLS/SNIP implementations (reimplemented from the papers with the pybaselines documentation as a guide); optional dependency for extended baseline algorithms. |
| gemmi | MPL-2.0 | **Dependency** — CIF parsing, space-group operations, hkl utilities. |
| matplotlib | PSF-based (matplotlib license) | **Optional dependency** (`[viz]`) — static fit plots and the VLM montage. |
| plotly | MIT | **Optional dependency** (`[viz]`) — self-contained interactive HTML viewer (plotly.js embedded in generated files). |
| BGMN / Profex | GPL | Studied (papers/docs only). **No code ported.** |
| xrayutilities | GPL-2.0 | Studied (papers/docs only). **No code ported.** |

## Data tables

- `src/pxrdref/data/f0_WaasKirf.dat` — Waasmaier & Kirfel (1995) 5-Gaussian f0
  coefficients, obtained from the ESRF DABAX collection (public scientific data,
  redistributed by silx (MIT) among others). Cite Waasmaier & Kirfel (1995).
- `src/pxrdref/data/mu_McMaster.dat` — photon-atom cross sections from the
  McMaster et al. (1969) compilation (UCRL-50174, a U.S. Government report),
  extracted from the ESRF DABAX file `CrossSec_McMaster.dat` (itself generated
  with P. Bandyopadhyay's mucal). Modified for bundling: energy-trimmed to
  2–120 keV and reduced to the PhotonEnergy/Photoelectric/Total columns (the
  file header documents the same). Cite McMaster et al. (1969).
- Test patterns under `tests/data/` — see `tests/data/README.md` for per-file
  provenance (NIST / APS 11-BM public data are works of the U.S. Government).
