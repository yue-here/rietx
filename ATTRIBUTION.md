# Attribution

rietx is an independent implementation, but its design and mathematics
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
- Markvardsen, A. J., David, W. I. F., Johnston, J. C. & Shankland, K. (2001).
  *Acta Cryst.* A57, 47–54 — probabilistic space-group determination from powder
  data, and the reason the answer here is an *extinction symbol* rather than a
  space group. Method reference only: the screen in `indexing/extinction.py`
  scores classes by ΔBIC and direct absence evidence, not by their posterior.
- Bergmann, J., Le Bail, A., Shirley, R. & Zlokazov, V. (2004).
  *Z. Kristallogr.* 219, 783–790 — review of powder-indexing programs, and the
  **bethanechol chloride benchmarks**. Two distinct uses, both paper-only:
  the article's conclusions about data quality and whole-profile confirmation are
  cited in `indexing/quality.py` and `indexing/workflow.py`, and its **Table 6**
  (ten sets of twenty 2θ positions) and **Table 5** (every program's score) are
  transcribed as the test fixture `tests/data/bethanechol_indexing.json`.
  Published tables, transcribed with attribution. **No program named in that
  paper was run and none of their code was consulted** — several (ITO, DICVOL,
  TREOR, McMaille, Crysfire, EFLECH/INDEX) are variously closed, GPL or of
  unstated licence, and this package's grading against them uses only their
  *printed scores*.
- Louër, D. & Louër, M. (1972). *J. Appl. Cryst.* 5, 271–275; Boultif, A. &
  Louër, D. (1991). *ibid.* 24, 987–993 and (2004). *ibid.* 37, 724–731 — the
  **successive-dichotomy** method behind `indexing/dichotomy.py` (the DICVOL
  lineage). Papers only; **no DICVOL code has been read or ported** — it is
  closed source. Two departures are deliberate and documented in that module:
  the search is over the reciprocal metric components (A…F) rather than direct
  cell parameters, which makes the per-domain Q bounds corner-exact by linearity
  in *every* system and so removes the 1991 paper's eight-case analysis for
  hl < 0 (the 1991 paper reaches the same linear form for its own triclinic
  case, for the same reason); and the tolerance is a per-line σ rather than one
  global absolute window. Louër & Louër's Table 1 (data-derived minimum
  parameter limits, and the non-collinearity condition on d₁/d₂) is
  **deliberately not implemented** — WP-1030 measured it as unsound for the
  system that needs it and subsumed where it is sound: the table has no
  monoclinic or triclinic column because for an oblique cell the largest
  observed d can exceed every principal d (A = C = 1, E = −1.7 gives
  d(101) > d(100)), and where the floors *are* sound the engine's own
  line-matching test is strictly stronger, since it uses a complete trial set
  with corner-exact bounds. Measured on the bethanechol domain, that test
  accounts for 0.0 % of box deaths, so a floor derived from it prunes nothing.
- Werner, P.-E. (1964). *Z. Kristallogr.* 120, 375–387; Werner, P.-E., Eriksson,
  L. & Westdahl, M. (1985). *J. Appl. Cryst.* 18, 367–370 — the semi-exhaustive
  **trial-and-error** index-space search behind `indexing/trial_error.py` (the
  TREOR lineage). Papers only; TREOR is GPL and no code has been read. Its
  Table 1 corroborates `BASE_INDEX_MAX = 2` for the low-symmetry base lines,
  independently of how that constant was chosen here.
- Visser, J. W. (1969). *J. Appl. Cryst.* 2, 89–95 — the ITO **zone-indexing**
  method. Read and assessed (WP-1030), **not implemented**, and the no-go is
  recorded in `docs/manual/engines.md` §"What a zone-indexing engine would and
  would not add": a constant 2θ offset splits ITO's coincidence peak rather
  than translating it, so it fails on exactly the uncalibrated laboratory data
  a third opinion would be wanted for. Recorded here because the assessment is
  cited in the manual and the roadmap, not because code derives from it.
- Křivý, I. & Gruber, B. (1976). *Acta Cryst.* A32, 297–298 — the unified
  Niggli-reduction algorithm, whose step A2 tie-break on |η| ≤ |ζ| is what makes
  the reduction canonical when two reduced axes are equal. The reduction itself
  is `gemmi.GruberVector`; what is taken from the paper is the normalisation
  condition the tolerance has to preserve.
- Grosse-Kunstleve, R. W., Sauter, N. K. & Adams, P. D. (2004). *Acta Cryst.*
  A60, 1–6 — the relative tolerance ε = ε_rel·V^(1/3) with ε_rel = 10⁻⁵ that
  makes that algorithm numerically stable, and the requirement that the same ε
  be used in the reduction and in the predicate checking it. Their Test 3 is
  `tests/test_indexing_reduce.py::test_niggli_reduction_is_unimodular_invariant`;
  method reference only (cctbx is permissively licensed but no code was ported).
- de Wolff, P. M. (1968). *J. Appl. Cryst.* 1, 108–113 — the M₂₀ figure of merit.
- Oishi-Tomiyasu, R. (2013). *J. Appl. Cryst.* 46, 1277–1282 — the **reversed**
  and symmetric de Wolff figures of merit, and the roundoff-stable line count
  N^cal. **Implemented** in `indexing/fom.py` (WP-1030) as `m_rev` / `m_sym`
  with `n_cal`, from the paper's eqs. (4), (5), (7) and (9)–(11); papers only,
  no code consulted. Two departures are documented there: the vanishing-δ floor
  is this package's addition (the paper does not address it), and the
  enumeration is over one hkl per Friedel pair with the full-orbit multiplicity,
  so Σ 1/m over the half-sphere is exactly N^cal/2.
- Smith, G. S. & Kahara, E. (1975). *J. Appl. Cryst.* 8, 681–683 — the "020
  detector" relation 2Q(020) + Q(h10) = Q(h30). Concept reference only; not
  implemented (WP-1030).
- Smith, G. S. (1977). *J. Appl. Cryst.* 10, 252–255 — estimating the unit-cell
  volume from one line, `indexing/quality.volume_envelope`. Its two constants
  (0.60 and 0.0052) are the paper's own and reproduce its printed 13.39 / 17.24 /
  21.32. Two things it does **not** contain, checked against the paper on
  2026-07-30: it is **triclinic-only** and publishes no per-system factors, so
  the Laue-orbit and centring scalings here are this package's derivation with
  nothing published to check them against; and the relation is a least-squares
  **mean line** (average discrepancy 10.6 %, −29 % to +32 %), not an upper
  envelope, so any use of it as a search ceiling needs slack this package
  supplies.
- Smith, G. S. & Snyder, R. L. (1979). *J. Appl. Cryst.* 12, 60–65 — the F_N
  figure of merit. (`indexing/fom.py` implements both, with a per-line-σ floor on
  ⟨Δ⟩ that is this package's addition and is documented as such, because it is
  what makes the two figures divergence-free on synthetic data — and what makes
  them non-comparable with a published value computed without it.)
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
- Cromer, D. T. & Liberman, D. (1970). *J. Chem. Phys.* 53, 1891–1898 — relativistic
  calculation of the anomalous scattering factors f′, f″ (also LANL report LA-4403).
- Cromer, D. T. & Liberman, D. (1981). *Acta Cryst.* A37, 267–268 — anomalous
  dispersion near and on the long-wavelength side of an absorption edge.
- Cromer, D. T. (1983). *J. Appl. Cryst.* 16, 437 — f′, f″ at arbitrary wavelengths.
- Kissel, L. & Pratt, R. H. (1990). *Acta Cryst.* A46, 170–175 — corrections to the
  tabulated anomalous-scattering factors (the high-energy limit the bundled table uses).
- McCusker et al. (1999). *J. Appl. Cryst.* 32, 36–50 — Rietveld refinement guidelines.
- Toby, B. H. (2006). *Powder Diffraction* 21, 67–70 — agreement indices.
- Bérar & Lelann (1991). *J. Appl. Cryst.* 24, 1–5 — serial-correlation esd correction.
- Hill & Howard (1987). *J. Appl. Cryst.* 20, 467–474 — QPA scale-factor relation.
- Le Bail, Duroy & Fourquet (1988). *Mater. Res. Bull.* 23, 447–452 — Le Bail intensity extraction.
- Coelho, A. A. (2005). *J. Appl. Cryst.* 38, 455–461; (2018) 51, 210–218 & 428–435 —
  minimizer design ideas (bound-constrained solves, adaptive Marquardt). Algorithms
  reimplemented from the papers; TOPAS itself is proprietary and was not consulted as code.
- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* 46, 544–549 — GSAS-II;
  cited for the *practice* of adding explicit broad peaks to the refined background
  (`Instrument.background_peaks`), alongside TOPAS's cell-less "peaks phase"
  (`xo_Is` + `gauss_fwhm`, Coelho 2018 above). Concepts only, from the papers and
  the published manuals: a Gaussian in 2θ is not a diffraction profile and no
  physical derivation is claimed for it — see `BackgroundPeak`'s docstring.
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
- NIST **X-ray Transition Energies Database** (SRD 128), <https://physics.nist.gov/PhysRefData/XrayTrans/> —
  the direct-experimental KL3/KL2 (Kα1/Kα2) and KM3 (Kβ1,3) wavelengths of every
  anode in `schemas/instrument._KA_DOUBLETS` and `background.diagnostics._KBETA`.
  One column of one evaluation for all six anodes, which is what keeps them on a
  common scale. Its two upstream measurements:
  - Hölzer, Fritsch, Deutsch, Härtwig & Förster (1997). *Phys. Rev. A* 56, 4554–4568 — Cr/Fe/Co/Cu Kα and Kβ (database ref `7d`); the Cu pair this package has shipped since v0.2.
  - Deslattes & Kessler (1985), in *Atomic Inner-Shell Physics*, ed. Crasemann (Plenum), 181–235 — Mo/Ag Kα and Kβ (database ref `5d`).
- Deslattes, Kessler, Indelicato, de Billy, Lindroth & Anton (2003). *Rev. Mod. Phys.* 75, 35–99 — the evaluation behind that database.
- Bearden, J. A. (1967). *Rev. Mod. Phys.* 39, 78–124 — W Lα1 wavelength (contamination check). Note his Kα scale is *not* the one used above and the two must not be mixed.
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
- Rouse, K. D., Cooper, M. J., York, E. J. & Chakera, A. (1970). *Acta Cryst.*
  A26, 682–691 — cylinder transmission factor A(µR, θ): eq. (2), the
  exp-of-quadratic fit implemented in `model/absorption.py`, and Table 1, the
  four-decimal tabulation carried as a test fixture
  (`tests/data/absorption_cylinder_rouse.dat`).  Published table and formula,
  transcribed with attribution.
- *International Tables for Crystallography*, Vol. C, §6.3.3 — transmission
  coefficient A (6.3.3.1) vs absorption correction A\* = 1/A (6.3.3.2), the
  exact cylinder integral (6.3.3.4) used as the independent physics check, and
  Table 6.3.3.1's analytic special cases (the flat-plate fence).  © IUCr —
  cited and re-derived, never redistributed.
- Hewat, A. W. (1979). *Acta Cryst.* A35, 248 — the scale × Debye-Waller
  factorisation of cylindrical absorption for µr < 1, which is why µR is
  computed rather than refined (WP-0501).
- Lobanov, N. N. & Alte da Veiga, L. (1998), 6th EPDIC abstract P12-16 — the
  alternative cylinder fit used by GSAS-II and TOPAS, valid to µR ≤ 3.
  **Not implemented**: its coefficients trace only to a conference abstract
  that could not be obtained, so they cannot be verified against a source.
- Stokes, H. T. & Hatch, D. M. (1988). *Isotropy Subgroups of the 230
  Crystallographic Space Groups*, World Scientific — isotropy subgroups
  (`crystallography/magnetic/isotropy.py`).
- Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006).
  *J. Appl. Cryst.* 39, 607–614 (ISODISPLACE) — the mode view of a distorted
  structure, and displacements as polar vectors
  (`crystallography/magnetic/modes.py`, `operators.allowed_displacement_basis`).
- Wills, A. S. (2000). *Physica B* 276–278, 680 (SARAh) — basis vectors as the
  refinable coordinates of a magnetic structure (`modes.py`).
- Rodríguez-Carvajal, J. (1993). *Physica B* 192, 55 — the sign convention for
  the magnetic interaction vector (`isotropy.py`).
- Perez-Mato, J. M., Gallego, S. V., Tasci, E. S., Elcoro, L., de la Flor, G. &
  Aroyo, M. I. (2015). *Annu. Rev. Mater. Res.* 45, 217 — magnetic space groups
  and representation analysis (`isotropy.py`, `operators.py`).
- Gallego, S. V., Tasci, E. S., de la Flor, G., Perez-Mato, J. M. & Aroyo, M. I.
  (2012). *J. Appl. Cryst.* 45, 1236 (MAGNEXT) — magnetic systematic absences,
  and the axial transformation law in its eq. (3) (`isotropy.py`, `operators.py`).
- Davies, Z. & Wills, A. S. (2016). *arXiv*:1610.00472 — the projector's
  normalisation (`modes.py`). Its I4₁32 decomposition, orbit split and
  projection ranks are asserted in `tests/test_magnetic_modes.py`. Its
  basis-vector table is not reproduced, because a basis vector is fixed only up
  to a change of basis.

## Open-source software studied or used

| Project | License | Relationship |
|---|---|---|
| lmfit | BSD-3 | **API inspiration**: the Parameter model (value/vary/min/max/expr). No code ported. |
| GSAS-II | custom Argonne royalty-free (grant-back clause) | **Behavioral reference** for conventions and validation goldens (e.g. the Sabine extinction parameterization and its Laue-series coefficients, WP-0506; the Suortti surface-roughness parameterization `SurfaceRough`, whose SRA/SRB are our `a`/`b`, WP-0502 — independently confirmed against Pitschke *et al.* (1993) p. 78, which quotes Suortti's form directly, so the physics does not rest on the GSAS-II reading alone; and its `Absorb` cylinder routine, consulted for WP-0501 and then *not* followed — see the Lobanov note above). Concepts and goldens are freely usable; the license is *not* a standard BSD — verbatim porting carries attribution and an upstream grant-back obligation, so no code is ported. |
| CrysPy | MIT | Reference for pure-Python Rietveld mathematics. No code ported. |
| MAUD | BSD-3 | Reference for texture / residual-stress methods (studied for the v2-fenced spherical-harmonics texture path). No code ported. |
| CrysFML / CrysFML2008 | LGPL-3.0-or-later + ILL no-military-use clause | Studied (concepts only — the LGPL and the ILL clause both bar a port into an MIT core). **No code ported.** |
| powerxrd | MIT | Reference for a minimal quick-look powder-XRD API surface. No code ported. |
| Dans_Diffraction | Apache-2.0 | Reference for scattering computations. No code ported. |
| pymatgen | MIT | Cross-check for structure factors/multiplicities in tests. |
| cctbx | BSD-style | Cross-check for symmetry constraints in tests. |
| EasyDiffraction | BSD-3 | Architecture reference (schema-driven design). No code ported. |
| pybaselines (derb12) | BSD-3 | **Algorithm reference** for arPLS/SNIP implementations (reimplemented from the papers with the pybaselines documentation as a guide). Not a dependency: the implementations are ours, and the `baselines` extra that used to install it was removed in v1.0 because no module imported it. |
| gemmi | MPL-2.0 | **Dependency** — CIF parsing, space-group operations, hkl utilities. |
| spglib | BSD-3 | **Dependency, and the source of two tabulations.** Wyckoff letters and oriented site-symmetry symbols (`crystallography/wyckoff.py`), and the **magnetic space-group database** the 1651 Shubnikov groups are read from (`crystallography/magnetic/operators.py`). Nothing is vendored: the tables are queried at run time through the installed library. spglib's own `msg.py` credits **Litvin, D. B. (2013), *Magnetic Group Tables*, IUCr** (`https://www.iucr.org/publ/978-0-9553602-2-0`) for the Litvin serial number it returns beside each group; the sequential 1–1651 numbering the package speaks in is the UNI numbering of **Campbell, Stokes, Perez-Mato & Rodríguez-Carvajal (2022), *Acta Cryst.* A78, 99**, and the identification algorithms are **Shinohara, Togo & Tanaka (2023), *Acta Cryst.* A79, 390**. Three of its 1651 entries do not round-trip through its own identification on 2.7.0 and are named in `operators.UNI_NOT_IDENTIFIABLE` rather than worked around. |
| spgrep | BSD-3 | **Dev-only test oracle** (`[dev]`, never a runtime dependency): an independent generator of the small irreps of a little group, used in `tests/test_magnetic_irreps.py` to check `crystallography/magnetic/irreps.py` against a second implementation of a different algorithm (Neto's subgroup chain against our split of the twisted regular representation). Every test using it carries `_oracle` in its name and `pytest.importorskip`, so the suite is green without it. **No code ported**; the licence text was read at 0.7.0 (BSD 3-Clause, Kohei Shinohara, 2022), as was that of its own dependency `hsnf` (MIT, same author). Nothing from either is redistributed. |
| matplotlib | PSF-based (matplotlib license) | **Optional dependency** (`[viz]`) — static fit plots and the VLM montage. |
| BGMN / Profex | GPL | Studied (papers/docs only). **No code ported.** |
| xrayutilities | GPL-2.0 | Studied (papers/docs only). **No code ported.** |
| FAIRmat `readers-xrd` | Apache-2.0 | **Vendor-format reference and fixture source** (WP-1047): its `tests/data` files are vendored as `tests/data/panalytical_*.xrdml` (and their `.json` reader outputs, used as independent oracles), and its element paths were consulted as specification. **One fence, and it is not cured by the wrapper's licence**: `src/fairmat_readers_xrd/ikz.py` — the file holding *both* its BRML and RASX readers — says it is "adapted from" `github.com/carichte/IKZ`, which has **no LICENSE file at all**, and Apache-2.0 on the wrapper grants nothing the upstream did not. So that file is **structural specification only**, never a line-for-line reading. It holds no data, so the fence does not reach the fixtures. |
| PowderLine (NSLS2) | BSD-3 | **Interchange format, fixture source and convention reference** (WP-1306). `src/rietx/io/recipe.py` reads its `GSASII_Rietveld` recipe; two complete cross-engine fixtures are vendored verbatim under `tests/data/powderline/` (test data only — nothing enters the wheel) with the upstream `LICENSE` beside them, as the BSD-3 redistribution clause requires. Its `topas/conversions.py` and `easydiff/conversions.py` were read as a **unit table** — merger, the way a format specification is (see the section below) — and every row of it was re-measured here against the committed LaB6 GSAS-II output before the reader was written; the one row the fixtures cannot settle (`Zero`, on which the two upstream modules disagree with each other) is refused rather than adopted. **No code ported.** |
| xylib | LGPL-2.1 | Listed **precisely to state that it was not ported.** It is the most complete open catalogue of vendor powder formats and its `uxd.cpp`, `rigaku_dat.cpp` and `bruker_raw.cpp` were *not* consulted for any reader here; the LGPL bars a port into an MIT core, and where a format fact was needed it was taken from a permissive source or measured off a file. |

## Closed-source software (not used)

These programs publish no source code. rietx implements the methods from the
papers that describe them, listed above. It does not run them, copy their
output or reproduce their tables.

| Program | What rietx took, and from where |
|---|---|
| ISOTROPY Software Suite: ISODISTORT, FINDSYM (Stokes, Hatch & Campbell) | The method, from Stokes & Hatch (1988) and Campbell et al. (2006). The isotropy direction labels are rietx's own (`isotropy.py`). Compare with an ISODISTORT table through the subgroup's BNS number. |
| SARAh (Wills) | The method, from Wills (2000). |
| BasIreps (FullProf suite) | The method, from Rodríguez-Carvajal (1993). The irrep labels and their order are rietx's own and are not CDML labels (`irreps.py`). The CDML mapping is deferred. |
| Bilbao Crystallographic Server: MAXMAGN, MAGNEXT, k-SUBGROUPSMAG | The method, from Perez-Mato et al. (2015) and Gallego et al. (2012). MAXMAGN and MAGNEXT were unreachable on 2026-09-06 (404 and HTTP 500), and no number in this repository comes from either (`tests/test_magnetic_isotropy.py`). |

TOPAS and FullProf are closed-source too. What rietx took from their papers and
documentation is recorded where it was used, in the literature list above and
in § Format specifications below.

## Format specifications (WP-1047)

A file format is an **interface**, not an expression: there is exactly one
number that is "the offset of nSteps", one string that is a magic marker, one
element path that holds the intensities. Those facts are merger, so they may be
written down from any description — including a source whose licence would bar
a port — and implemented independently. The practice this project follows is to
extract the facts into a written table first, noting which source each came
from, and then write the parser **with the source file closed**, in this repo's
idioms. No line of any reader below is transcribed.

**A repository grant does not settle a file, and the worked example is
`luttero/maud`** (WP-1407). Its repository LICENSE is BSD-3, yet
`PhilipsDataFile.java` — a UDF reader, exactly the thing a session would reach
for — carries a 1997 header reading *"provided as it is as confidential and
proprietary information … in accordance with the terms of the license agreement
you entered into with the author"*. Repo grant, contradictory file notice, and
the contradiction is only visible in the file. That is `io/CLAUDE.md` § Adding a
format step 1 in one instance: **check the licence per file, before reading it
for facts and before touching a parser.**

| Format | Specification consulted | Note |
|---|---|---|
| pdCIF | IUCr pdCIF dictionary; Toby (2003), *J. Appl. Cryst.* **36**, 1240 | Parsed through gemmi, so only the *tag preference order* is ours. |
| magCIF | COMCIFS `magnetic_dic` (`cif_mag.dic`, github.com/COMCIFS/magnetic_dic; revision of 2026-06-03, fetched 2026-09-06 and read to a scratch directory), the BNS/OG settings and the parent-to-magnetic-cell transform these tags carry: Perez-Mato, Gallego, Tasci, Elcoro, de la Flor & Aroyo (2015), *Annu. Rev. Mater. Res.* **45**, 217; and the magnetic-group notation: González-Platas, Katcho & Rodríguez-Carvajal (2021), "Extension of Hall symbols of crystallographic space groups to magnetic space groups", *J. Appl. Cryst.* **54**, 338–342, doi:10.1107/S1600576720015897 | **Tag names only, and nothing vendored.** Which items exist and what each means are specification facts, and the three lists in `crystallography/magcif.py` (`READ_TAGS`, `WRITTEN_TAGS`, `REFUSED_TAGS`) are the written table `io/CLAUDE.md` § Adding a format asks for — extracted first, with the dictionary then closed. The dictionary's own text is quoted in two docstrings and nowhere else: the `crystalaxis` cosine-metric definition and the spherical frame (x ∥ **a**, z ∥ **c**\*), both because getting either wrong is a wrong moment rather than a wrong spelling. Parsed through gemmi, so the CIF grammar is not ours; the *one* item gemmi cannot tokenise is read off the raw text and said so in place (`_parent_propagation_vector.kxkykz`, written `[0 0 0]` in CIF2 bracket syntax inside a CIF1 file) — read only to refuse a k that is not Γ, and not stored or written. Two items this model needs have **no** magnetic-dictionary tag — the form-factor ion and the Landé g — and go out under a namespaced `_rietx_` category enumerated in `magcif.PRIVATE_TAGS` rather than under a guessed dictionary name. **MAGNDATA** (Gallego et al. 2016, *J. Appl. Cryst.* **49**, 1750) was read to verify fixtures and is not a source of any number: the Bilbao server states no licence or redistribution grant of any kind (re-checked 2026-09-06, M-5's finding unchanged), so no entry is shipped, every fixture is typed, each operator list is verified by identifying it back to the published BNS number, and each moment is cited to the original paper. |
| GSAS raw (FXYE/ESD/STD) | Larson & Von Dreele (2004), LAUR 86-748, §"Powder data file formats" — also the authority for the **bintype vocabulary** (`COND`, `CONS`, `CONQ`, `EDS`, `LOG6`, `LPSD`, `RALF`, `SLOG`, `TIME_MAP`) and for what each one puts on the x axis, corroborated against real bank records wherever one was obtainable; and for the **ESD bank's field width** specifically, **three descriptions that agree**: APS 11-BM's own *Data Formats* page (https://11bm.xray.aps.anl.gov/users/filetypes) — "*the intensities and their uncertainties (esd) are alternated with five pair of numbers per line (8 characters per number), as described in the GSAS manual*" — the manual it points at, and GSAS-II's `G2pwd_fxye.py` consulted as **spec only** for the fact that its ESD reader takes `S[i:i+8]`/`S[i+8:i+16]` on a 16-character stride | Documentation only; see the GSAS-II row above for why no code is ported. **`CONS`/`CONST` is the only bintype implemented and every other one is refused by name** — and on *scope*, not on the Bruker v1/v2 "no corroborated description" bar: none of the other eight puts 2θ on the x axis, and `PatternData` holds 2θ. Real files are abundant (GSAS-II's own tutorial data ships `SLOG` and `RALF` banks); **none was vendored**, because for every file carrying real instrument data no redistribution grant is establishable — three separate repositories ship non-CONS GSAS data under licences whose operative text is unambiguously *code*-scoped, which is `io/CLAUDE.md` § Adding a format step 1 earning its keep again. Two corrections to the consulted sources are recorded, because either would have shipped a wrong answer: GSAS-II's `G2pwd_fxye` divides the FXYE x column by 100 **unconditionally**, with no bintype branch anywhere in the module, where the manual says that column is *"centidegrees for CW data or microseconds for TOF data"*; and for `ALT` records the manual's own Fortran format (`F8.0,F7.4,F5.4`) and GSAS-II's scale factors disagree by 100× on x and 10× on intensity and esd. The type flags: `STD`, `ESD` and `FXYE` are implemented against real files; `ALT` and `FXY` are named and refused, and *there* the reason is the fixture — every obtainable `ALT` file is also a `RALF` bank, so it cannot exercise an ALT reader at all, and no `FXY` file was found anywhere. On the **ESD field width**: it is merger — there is one number that is "the width of an ESD field" — so it may be read from GSAS-II, which in any case permits redistribution royalty-free. The width went into a written table before the parser was touched, and `tests/test_readers.py::write_gsas_esd` packs `:8.1f` **literally** rather than importing `ESD_FIELD_CHARS`, so the writer cannot drift with the reader. The files corroborate independently: every data record of all six real ESD/STD banks obtainable here is exactly 80 characters holding ten non-blank fields (`tests/data/README.md` § GSAS ESD). |
| GSAS-I `.prm` (instrument-parameter file) | Larson & Von Dreele (2004), LAUR 86-748 — the same manual as the GSAS raw row above, here for the `INS`/`ICONS`/`PRCF`/`HTYPE` instrument-parameter records rather than the `BANK` data record | Manual-as-spec; no code taken. Only `HTYPE PXCR` (constant-wavelength X-ray), one bank, GSAS profile function 3 is read (`io/instrument_profile.py::read_gsas_prm`) — the case that is essentially the whole of an APS 11-BM archive scan (1499/1500 real `PXCR` files were this exact shape — that corpus is a **private, unpublished diffraction archive** that ships in no wheel and no reader here can open it, so every count quoted from it in this row and in `io/instrument_profile.py`'s comments is evidence a reader must take on trust rather than check); `HTYPE PNTR` (neutron time-of-flight) and profile functions 1, 2 and 4 are refused by name, the latter three for lacking a real, non-template file to derive or verify a coefficient layout from. The centidegree(²)-to-degree(²) conversion for `GU`/`GV`/`GW`/`LX`/`LY` is this project's arithmetic, verified against a real pattern's measured peak widths, a GSAS `.LST` refinement log for the same instrument, and an independently-fitted rietx profile of the same beamline (three checks, not one) rather than taken on the manual's word alone. **No `.prm` is vendored from that archive**: every file in it carries a specific beamline's calibration, so `tests/test_gsas_prm.py` synthesizes every refusal-path fixture inline.  The `.prm`/`.inst` files it does read are the ones already committed under `tests/data/` and documented in that directory's `README.md`, which predate this reader. The **writer** (WP-1118, `write_gsas_prm`) states the same records under the same manual-as-spec fence and inverts the same conversion; it writes `ICONS`' `ZERO` at 0 only, and refuses a non-zero one, because that field's unit is the one thing no file in either corpus settles. |
| FIT2D / pyFAI `.chi` | Hammersley (1997/2016), *FIT2D: An Introduction and Overview*, ESRF Internal Report ESRF97HA02T, §"CHI file format" | The four-line header. The x-axis-label policy (refuse a recognisably q or d axis) is this project's, not the format's — the format does not standardise the label at all. |
| `.dif` peak lists | Bruker DIFFRAC-AT output; RRUFF calculated-powder tables | Recognised **in order to be refused**; there is no parser to attribute. |
| Bruker/Siemens `.uxd` | Keys, block markers and range structure read off five real files (`usnistgov/texture`, `mtex-toolbox/mtex`, `joeyko2706/FP-Protokolle`) | **No file is vendored**: one repo is GPL-2.0 and the others declare no licence at all. Facts may be read from them; bytes may not be redistributed. `tests/data/README.md` records what each established. xylib's `uxd.cpp` (LGPL) was **not** consulted. |
| Rigaku `.ras` | Section markers and header keys read off real exports, plus the format notes in `garrekstemo/RigakuFiles.jl` (MIT) and `nims-mdpf/M-DaC_XRD` (MIT) | The format is self-describing ASCII, so the "spec" is a list of key names. The three policies that cost more than the parsing — the axis refusal, σ decided by arithmetic rather than by the declared unit, and the un-applied attenuator — are this project's; no source states any of them. |
| PANalytical `.xrdml` | Element paths and attribute names read off three real files, cross-checked against the paths named in `paruch-group/xrdtools` (MIT) and FAIRmat `readers-xrd` (Apache-2.0) | Fixtures **are** vendored: all three were committed by `readers-xrd`'s own maintainers into an Apache-2.0 repo, and the `ikz.py` fence below does not reach them (IKZ holds no data files). That `intensity = counts × beamAttenuationFactors` is asserted by FAIRmat's reader and **independently measured here** on the real file — `tests/data/README.md` has the five-point table; `xrdtools` ignores the field entirely. σ through that product, and the counts/cps composition, are this project's. |
| Rigaku `.rasx` | Member paths and the `root.xml` manifest read off four real archives (FAIRmat `readers-xrd`, Apache-2.0) | A zip of text files. FAIRmat's own RASX reader lives in the fenced `ikz.py`, so it was **not** read; the manifest convention was taken from the archives themselves. The σ arithmetic, the bounded member read and the "manifest, not name list" rule are this project's. |
| Bruker `.brml` | `DataContainer.xml` → `RawData<N>.xml`, and the `DataViews` `Start`/`Length`/`FieldDefinitions` layout, read off two real archives (FAIRmat `readers-xrd`, Apache-2.0); GSAS-II's `brml` import consulted as **spec only** for the container shape | The same `ikz.py` fence applies to FAIRmat's BRML reader. Locating channels from `DataViews` instead of GSAS-II's fixed `entry[2]`/`entry[4]` is this project's, and the real files are why: 2θ sits at column 2 and the intensity at column 7. That the absorber is *already applied* was **measured**, not read from any source — `tests/data/README.md` has the table. |
| Bruker/Siemens `.raw` (v4) | The segment chain, the range-header field order and the four magic strings, from **two descriptions that agree**: the real file `tests/data/bruker_raw4_scrambled.raw` walked byte by byte here, and GSAS-II's `G2pwd_BrukerRAW.py` as **spec only** | The offsets went into a written table before any parser was opened, and the parser was written with the sources closed; `tests/writers_xrd.py` packs the same table *independently*, so the two cannot drift together. FAIRmat's `bruker_raw_parser.py` (MIT) is **not** a third description — it hard-codes absolute offsets taken from that one file — and was used only as a cross-check that its constants land where the structural walk puts them. Two corrections to the consulted sources are this project's and are asserted by test: striding by the declared `datumSize` (GSAS-II reads the field and ignores it; FAIRmat hard-codes 8), and walking to EOF rather than counting `b'2Theta'` (which occurs **twice** in the single-range real file). |
| Bruker/Siemens `.raw` (v3, `RAW1.01`) | **Three** descriptions that agree and **no file at all**: GSAS-II (spec only), `bracerino/xrd-file-converter` (MIT), and `reductus/reductus` `reflred/bruker.py` (**Unlicense**), the last a field-by-field transcription of Bruker's own header definition (`length_of_RAW_RANGE_HEADER`, `data_record_length`, `total_size_of_extra_records`, `varying_parameters`) | The WP's `+40` / `int32@+256` ambiguity is not one: the third description names both missing fields, so the data offset is arithmetic rather than a guess with a fallback. The scan-type enum has a **single** source, which is why an unfamiliar code is assumed and reported rather than refused. Having no fixture is why v3's gates are the strict ones — the declared ranges must account for the file exactly. |
| Bruker/Siemens `.raw` (v1, v2) | **Not implemented.** GSAS-II describes v2 and nothing else found does; the one other v2 attempt located (`SrValentim/MatFinder`) carries no licence, is visibly heuristic, and disagrees with GSAS-II on where the first block starts. v1 has no description at all | Both are refused by name and version. One uncorroborated description with no file to check it against is how a reader comes to return a plausible wrong pattern. |
| PANalytical `.udf` | The key vocabulary, the `RawScan` marker and the block shape read off **56 real files** (`yargerlab/Data`, 55 from an ASU PANalytical Aeris; `SantiagoJulioD/LabAv2`, 1 from an X'Pert), corroborated by PyXRD's `udf_parser.py` (**BSD-2**) and psidata's `xrd_panalytical.py` (**Apache-2.0**). CrysFML's `Read_Pattern_Panalytical_Udf` (LGPL) and xylib's `philips_udf.cpp` (LGPL) were **not** consulted: two permissive descriptions plus 56 files made them unnecessary, and the xylib fence stays where it is | **No real file is vendored**: all three repositories that hold them declare no licence at all, checked per repository. `tests/data/README.md` records the 19-key table and what each file established. The *vendorable* fixture is the complete UDF file PyXRD embeds inline in its own test under BSD-2, which is valid as committed because UDF is plain ASCII — and which carries only 5 of the 19 keys, so it proves the parse and not the vocabulary. Three things are this project's and no source states any: which keys are *required* (the two that make an abscissa, plus the marker), the point-count gate `round((end−start)/step)+1`, and the refusal to derive a counting time from `ScanStepTime`, which on a PIXcel-class detector is not seconds per step — 5246 points at the stated 18.87 s would be 27 hours against a scan the file's own name calls eight minutes |
| Philips PC-APD `.rd` / `.sd` (V3, V5) | Byte offsets, the three enumerated code tables (diffractometer / anode / focus) and the **√-compressed intensity rule** from **two descriptions that agree** — xylib's `philips_raw.cpp` (LGPL, from Martijn Fransen's vendor-supplied specification) and PyXRD's `rd_parser.py` (**BSD-2**) — and independently measured here on **28 real files**. `Yohko/importtool`'s `import_Philips_Raw.ipf` is **not** a third description: it reproduces xylib's code tables verbatim and even carries xylib's `810 - 214 - 8*3` expression | The offsets went into the table in `tests/data/README.md` § Philips before any parser was opened, and were derived from the bytes first, which is why the sources' errors are visible rather than inherited. **PyXRD, the permissive description, is the defective one**: it omits the √ decode entirely and returns the raw `uint16` as the intensity, computes the point count as `int((max−min)/step)` — one short of the 7251 actually present — and offsets the abscissa by half a step. All three are refuted by files: the committed `qarr/*.prn` conversions of these very scans, which the √ rule reproduces bit for bit. Two facts here are this project's: the header field at offset 136 holding `max(data)`, which is in no description and is used as a gate, and the decision to read **V5 only behind the length gate** — its data offset (810) rests on one description copied twice and no file anywhere, and `len == 810 + 2·n` with `n` from the header's own angle triple is the whole of its evidence. `tests/writers_xrd.py` packs the offsets **literally**, so the writer cannot drift with the reader |
| Bruker TOPAS `.inp` (project reader, `io/projects/topas.py`) | **TOPAS Academic's own Technical Reference** (https://topas-academic.com/technical_reference) for the format's structure: 1.2 *Conventions* (the notation - `[ ]`, `...`, `#`, `$`, `E`, `!E`, `N` - and the `'` / **nestable** `/* */` comment rules), 2.1-2.3 (when a parameter is refined; `prm`/`local`; the attribute list), 2.5 *The Get function* (what `Get(xx)` returns, and that it resolves `xx` locally and then outward through the enclosing scopes - which is how a *coupled cell edge* written `b = Get(a);` is read; the built-in is documented in its own right, so reading it needs no macro at all), 5.1 *Data structures* (the keyword-dependency tree: which keyword may sit inside which block, and which repeat), 19 (the pre-processor's directive list and the Topas.inc macro conventions), 19.3 (the argument-naming convention that makes a macro's argument order legible: a `c` suffix is a parameter *name*, `v` a *value*, `cv` either, so the stem of `a_cv` or `al_cv` names the cell key it carries). **The cell macros are supported by an enumerated list and each is cited on its own line** - `io/CLAUDE.md` § Adding a format step 2 admits a macro's *semantics* as a specification fact, and the enumeration is the bound on that, since `Topas.inc` ships hundreds of macros and only these are read. A name not on this list is refused by name, and earns support only with its own citation, never by analogy: **`Cubic(cv)`** - 19.3.2, and 19.1, whose prose states the single argument "defines the a, b and c lattice parameters"; **`Tetragonal(a_cv, c_cv)`** - 19.3.2; **`Hexagonal(a_cv, c_cv)`** - 19.3.2; **`Rhombohedral(a_cv, al_cv)`** - 19.3.2, which is also where the argument *order* comes from, an edge then an angle, read off the argument names via 19.3's convention rather than guessed; **`Trigonal(a_cv, c_cv)`** - **1.3** *Input file example*, the reference's own worked input, where `Trigonal(@ 4.759, @ 12.992)` gives the cell of an `R-3C` corundum, i.e. a hexagonal-setting a and c. 19.3.2's list has only the first four, so `Trigonal`'s authority is deliberately recorded as the example and not the list. How each argument then *propagates* to the keys the reference does not name is crystallography rietx already owns, not a fact of this format. `Orthorhombic`, `Monoclinic` and `Triclinic` are **not** cell macros of this format - 19.3.2 has exactly four entries and across the manual those three words occur only as English (crystal-system labels; an `Orthorhombic_Bipyramide` bond-length restraint, which is not a cell) - so they are refused by name. The page also carries a machine-readable transcription of the 5.1 tree - 43 top-level types, 680 nodes, 698 names - used to enumerate the keyword space exhaustively rather than by sampling files. That enumeration is checked in as `io/projects/coverage.py`'s `PHASE_SCOPE`, one declared stance per construct with this package's own argument for it; the keyword names are the format's, every description is ours, and `SPEC` states which edition of the reference the table was written against so a later one is a declared piece of work rather than a silent gap. **Keyword names, nesting, arity and notation are specification facts** (`io/CLAUDE.md` § Adding a format, step 2): merger, written down and implemented independently, with no TOPAS code and no Topas.inc macro *body* reproduced. Corroborated against a **private archive of 606 solved refinements** — the maintainer's own research inputs. TOPAS itself is closed source and **no TOPAS code or macro library was consulted**. The archive is not redistributable and is the maintainer's own unpublished research data, so **no file in it is named anywhere in this repository**: each is cited as `archive file N`, the map from number to file is private (the maintainer holds it in `yue-here/rietx-corpus-map`), and the facts it settled were tabled *before* the parser was written and are recorded in `tests/data/README.md`, each against the numbered file it was read off — the `_BLOCK` boundary, the per-macro *incidence* of the cell macros (`Hexagonal` 15, `Cubic` 13, `Trigonal` 4, `Tetragonal` 1, `Rhombohedral` 0, which is what says `Trigonal` is worth implementing and that nothing here corroborates `Rhombohedral`), the multi-`occ`/`adps`/`u11` incidences, the coupled-edge `Get()` case and the weight-percent oracle — so the evidence for every position is checkable | Everything the reader decides is this project's: the `_BLOCK` boundary (which 5.1 licenses but does not specify), the one value grammar read once with its flag (`_read_tail`), report-or-refuse on a *stated but unreadable* cell key / `occ` / `beq` / ADP tensor, the file-level `site`-count guard, and every refusal - *which* construct is refused, and with what message, is a judgement about what rietx can honour and is stated nowhere in the reference. What the reference settled, and the archive could not, is five facts: a parameter's **name** is itself its refine flag (2.1), a block comment **nests** (1.2), `#ifdef`/`#ifndef` test a `#define`d name with no `!` form described (19), the scope is four levels deep, `xdd` -> `str` -> `site` -> `occ` (5.1), and `Rhombohedral`'s arguments are an edge then an angle (19.3.2/19.3) - the last on a macro **0** archive files use in live text, so the citation is the whole of the evidence and a wrong order would have been a wrong cell with nothing raised. **No macro body is reproduced** - not in code, comments, tests or docs. The coupling each supported macro states is written in this reader's own idiom (`_CellMacro`: one entry per positional argument naming the keys it sets, plus the angles the crystal system fixes), which is a different thing from transcribing the definition that implements it. The emission-profile macros (`CuKa5` and friends) are **not** expanded — only the anode is reported, and the wavelengths come from `rietx.schemas.instrument._RADIATIONS`. **No `.inp` is vendored** — they are the owner's data — so `tests/test_projects_topas.py` synthesizes every fixture inline and the comment on each names the archive idiom it stands for and what reading it wrong would do. The fixtures' *site* lines are written here — species, coordinates, occupancies — while the cell and `ADPs` rows carry synthetic values at the archive's own column widths and spellings, the spelling being the fact those rows exist to pin. Two cells are kept real and are certified reference materials whose values are published — the LaB6 and Si standards — so a reader can recognise them; every other cell, coordinate and ADP tensor is synthetic. The two `grep -i topas` hits above are *physics* (Lobanov, the GSAS-II/TOPAS cylinder fit), reimplemented from papers; neither is this format. |
| FullProf `.pcr` (`io/projects/fullprof.py`) | The line order, the field order of each control line, the `Isy` sub-grammars and the `10·n + multiplier` codeword encoding, read off **six real `.pcr` files** from the maintainer's archive, cited throughout as `corpus file 1` to `6` because they are unpublished research data (the map from number to file is in the private `yue-here/rietx-corpus-map`) plus the format description in Rodríguez-Carvajal's FullProf manual and the ILL/FullProf school notes already cited above. **FullProf itself is closed and no FullProf source was consulted** | The facts went into a written table — `_CONTROL_FIELDS`, `_PHASE_FIELDS`, `_CELL_COLUMNS` and the rest of that module's column tuples — *before* the parser, and each carries the file and line it was read off, so the evidence for every position is checkable. The column *names* are the module's own and the file's `!` header comments are discarded before the walk, because the header text changes with `Jbt` (`Ang`/`Mom` in one column) and a parser keyed on it breaks on exactly the magnetic phase. Three things are this project's and no source states them: that FullProf's `Occ` normalisation is degenerate with the phase scale, so only the *ratio* between sites is recoverable and a phase whose ratios disagree is refused; the origin-choice preference for a bare symbol (verified by that same ratio test rather than trusted); and reading a magnetic phase in full while refusing to *build* it. **No real `.pcr` is vendored** — they are the owner's data — so the test fixtures are synthetic and every line in them is quoted, in a comment, from a numbered corpus file and a line. Every refined *structure* value in them is synthetic too — coordinates, displacement parameters, cell edges, scales, moments and their targets — because a column width and a field count are facts about the format while a refined coordinate is somebody's structure. The format's own settings (the codewords, the wavelengths, the agreement factors) stay the files' own, being what the layout claims are read against. |
| GSAS-I `.EXP` (project reader, `io/projects/gsas.py`) | Larson & Von Dreele (2004), LAUR 86-748 — the same manual as the two GSAS rows above, here for § *File Structures in GSAS*, which lists every record key with its Fortran FORMAT and its meaning, and for § *CW profile functions*, which names each function's coefficients. The record keys, the column offsets and the coefficient names are **specification facts** (`io/CLAUDE.md` § Adding a format, step 2): they were extracted into a written table first and the parser was written with the manual closed. Corroborated against `tests/data/FAP.EXP`, GSAS's own converged fluorapatite refinement, which has been committed here since v0.2 and carries its own provenance row in `tests/data/README.md`. **No GSAS or GSAS-II code was consulted for this reader at all** — not as spec and not otherwise; the manual and the file were enough, which is why the GSAS-II row's grant-back clause does not arise here. | Everything the reader decides is this project's. **Three corrections to the manual are recorded in the module docstring and asserted by test**, because each would have shipped a plausible wrong number rather than an error: the CW function 2 paragraph lists its eighteen coefficients twice and **transposes positions 8 and 9** between the physics-symbol and GSAS-name tuples (settled against GSAS's own EXPEDT listing, which prints `#8(shft)`, and against this file's converged sample displacement at index 8; function 3's two tuples agree, which is what shows it to be a slip); `CELVOL` is `2F15.3` in every file here against a printed `2F10.3`, which at the printed width reads 523.755 as 52.0; and the `ATmmmB` key template is printed one character short of the twelve real files write. `RPOWD` carries undocumented fields past its declared `2F10.4` and they are **not** read — the observation count comes from `REFN STATS`, which the manual does declare. CW profile functions 1, 2 and 3 are named; **function 4 and above are refused by name**, the manual describing type 4 only as "between 14 and 27 coefficients … `S400`, etc.", which does not enumerate a layout, and no file here corroborates one — the Bruker `.raw` v3 bar applied to a coefficient order rather than to a byte offset. The centidegree(²)-to-degree(²) conversion is the one the `.prm` row above already establishes and cross-checks three ways; this reader is a fourth check on it, since `FAP.EXP`'s `LX` of 3.35183 is the 0.0335° the acceptance suite independently transcribed. An **anisotropic** site reads but refuses to build: the six `UIJ` values are carried on the model, and which off-diagonal convention they follow is settled by no file here, the same refusal `fullprof.to_structure` makes about a `β` block and for the same reason. The **writer** (WP-1118) reads the same manual for the same record layouts and takes nothing further from it; its one fact the manual does not state is that a field must carry an explicit decimal point, since a Fortran `F`/`E` edit descriptor supplies one from its own `d` otherwise — established from the language rather than from any GSAS source, and corroborated against `FAP.EXP`'s own spelling (`0.333333`, `0.000000E+00`), which is the only check available because no test in this package can see the difference. |
| GSAS-II `.gpx` (project reader, `io/projects/gsas2.py`) | **GSAS-II's own `docs/source/objvarorg.rst`**, read 2026-09-16 as specification: § *GSAS-II Data Tree* for the file layout (one `pickle.dump` per top-level tree item, each a list whose first element is a `[label, data]` pair and whose rest are its children's), § *Constraints Tree Item* for the `[[mult, var], …, fixed, vary, type]` row and its four type letters, § *Covariance Tree Item* for `varyList`/`sig`/`Rvals`, § *Phase Information* and § *Atom Records* for the phase keys and the `cx, ct, cs, cia` column pointers — the pointers are why a magnetic phase's ADP flag is read at 12 rather than at 9 — and § *Powder Diffraction Tree Items* with § *CW/TOF Instrument Parameters* for the histogram children and the `[initial, value, flag]` triple. Excluded regions are documented in none of those, and come instead from GSAS-II's `GSASIIstrIO.py` stating that `Limits[2:]` is the excluded list and that each pair masks the data *inside* it — **spec only**, one line of behaviour, no code taken. The allow-list *shape* follows PyTorch's `weights_only` unpickler, which is the established answer to this exact problem (a `find_class` allow-list, a by-name refusal, and a dummy class for what must be accepted but not constructed); it was read as a **pattern**, and none of its code is here. Corroborated against the public GSAS-II tutorial corpus (34 projects, `AdvancedPhotonSource/GSAS-II-tutorials`), of which three are vendored under `tests/data/` with their provenance rows. | The GSAS-II row above governs: royalty-free, grant-back on derivative works, **no code ported**. Everything this reader decides is this project's — the allow-list's membership and each entry's reason, every refusal and its message, and the stance table over the tree items. **Four measurements are recorded in the module docstring and asserted by test**, each because the alternative was a plausible wrong answer rather than an error: the CW profile coefficients are centidegrees (corroborated *across formats* — the tutorial `.gpx` of the 11-BM instrument states the `U`, `V`, `W` that `tests/data/11bm_gsas.prm` states 1e-4 smaller, and `read_gsas_prm` already converts those) while `Zero` is degrees, so the two GSAS generations do **not** share that convention; `Rvals['GOF']` is the **square root** of reduced χ², which is the opposite of what this repo's `.EXP` reader claimed until this WP measured it on six files; eleven distinct globals appear across the corpus, of which seven are outside the allow-list proposed on issue #234, so an allow-list taken from one archive would have refused 10 of the 34 real projects; and a third of the corpus carries no pickle protocol header at all, so the sniff cannot be the magic bytes. A **fifth** landed with WP-1118: four corpus phases write a Hermann-Mauguin symbol the tables hold in two settings, and in every one of them the project's own `SGData['SGOps']` describe origin choice 2 where the bare symbol resolves to choice 1 — so the setting is read from the operators the file states, not adopted from any statement about GSAS-II's conventions. An **anisotropic** site reads but refuses to build, the same refusal `gsas.to_structure` and `fullprof.to_structure` make and for the same reason. |
| GSAS-II `.instprm` and the phase CIF it imports (`io/instrument_profile.py`, `io/projects/gsas2.py`) | **GSAS-II's own modules, read 2026-09-16 as specification only** (WP-1118): `GSASIIfiles.ReadInstprm`/`WriteInstprm` for the file's grammar — the header its reader tests for, the `#Bank n:` split, the `;` separator, the space-stripping and the triple-quoted value — and `GSASIIfiles.SetPowderInstParms` for the two constant-wavelength key sets, single line and doublet, in the order it builds them. Three further facts, each read where GSAS-II *uses* the number rather than where it stores it: `GSASIIstrMath.GetIntensityCorr` applies the polarization factor only to an `XC` or `XB` type, so the field is inert on a neutron bank in that program exactly as it is here; `GSASIIpwd.Polarization` is `(1-Pola)cos²(2θ)+Pola` at zero azimuth, which is this package's K term with K = `Pola`; and `GSASIIpwd.SetInstParms` floors `SH/L` at 0.002 before evaluating a profile. `GSASIIfiles.SetPowderInstParms` also corroborates the units from the other side, copying a GSAS-I `.prm`'s `GU/GV/GW` across unconverted and dividing its `ZERO` by 100. For the CIF half, `imports/G2phase_CIF.py` for which tags that importer reads — `_symmetry_space_group_name_H-M` first and `_space_group_name_H-M_alt` second, both through its own `SpcGroup` grammar, the `_symmetry_equiv_pos_as_xyz` / `_space_group_symop_operation_xyz` loop it checks that reading against, and the `_atom_site_*` columns including `_atom_site_b_iso_or_equiv` divided by 8π² — and its own message naming origin choice 1 "a space group setting not compatible with GSAS-II", which is where the two programs' opposite defaults are established. The CIF tag names are checked against COMCIFS `cif_core.dic` rather than remembered. Corroborated against the tutorial corpus's 12 `.instprm` files (4 constant-wavelength; 2 vendored under `tests/data/` with their provenance rows). | The GSAS-II row above governs: royalty-free, grant-back on derivative works, **no code ported**. Everything here is this project's: which types are read, every refusal and its message, the `bank=` selection (GSAS-II takes the lowest-numbered bank silently; this refuses and names them, three of the twelve corpus files being multi-bank and one of those writing `#Bank 6` twice), and the decision to write the setting in three places rather than pick a spelling. Two measurements are recorded in the tests: the writer reproduces a real file's own 13 items character for character, and **2 of the 4 constant-wavelength corpus files carry a negative `X`** and are refused, GSAS-II bounding none of its width coefficients where this package's are softplus-bounded at zero. gemmi's preference for `_space_group_name_H-M_alt` over the deprecated tag when both are present was measured here, not read anywhere. |

## Bundled frontend code (redistributed in the wheel)

Every other row above is either studied or installed by the user's own package
manager. These are different in kind: the GUI's build output is **committed**
under `src/rietx/gui/static` and ships inside the wheel, so this package
redistributes their compiled bytes. All are MIT, and none is modified — the
lockfile `gui/package-lock.json` is the version statement, and
`tests/test_gui_dist.py` is what keeps the shipped bytes tied to the sources
they were built from. Their licence texts ship in the wheel and sdist as
`LICENSE-3RD-PARTY.md` (WP-1003).

| Project | License | Relationship |
|---|---|---|
| Svelte | MIT | **Bundled** (WP-1010) — the compiler is a build-time tool, but its runtime is part of `assets/app.js`. |
| CodeMirror 6 (`@codemirror/*`, `@lezer/highlight`, `@lezer/common`, `style-mod`, `w3c-keyname`, `crelt`) | MIT | **Bundled** (WP-1013) — the text pane's editor, in its own `assets/vendor-cm.js` chunk, fetched when the pane is first opened. Unmodified: the `.rxt` highlighting is a `StreamLanguage` defined in this repo (`gui/src/lib/rxt.ts`), not a patched grammar. |
| uPlot | MIT | **Vendored** (WP-1461) — `src/rietx/viz/static/uPlot.iife.min.js` and `uPlot.min.css`, unmodified, with the licence beside them as `uPlot.LICENSE`. `npm run build` copies them from the exact pin in `gui/package.json` (`gui/scripts/vendor.py`), and `tests/test_gui_dist.py` holds the file's banner version equal to that pin. The page `viz.html.write_html` writes inlines the code with the licence as a comment beside it, because a written file leaves the package. |
| svgcanvas (Zeno Zeng; canvas2svg, Gliffy Inc.) | MIT | **Vendored** (WP-1461) — `src/rietx/viz/static/svgcanvas.esm.js`, unmodified, with the licence beside it as `svgcanvas.LICENSE`, whose notice names both copyright holders. The charts' SVG export redraws each pane through it, loading it on the first export. `npm run build` copies it from the exact pin in `gui/package.json` (`gui/scripts/vendor.py`), records the version in `VENDORED.json` beside it, and `tests/test_gui_dist.py` holds that equal to the pin. The page `viz.html.write_html` writes inlines it with the licence as a comment. |

## Data tables

- `src/rietx/data/b_Sears.dat` — bound coherent neutron scattering lengths and
  cross sections, obtained from the NIST Center for Neutron Research's
  machine-readable copy (https://www.ncnr.nist.gov/resources/n-lengths/list.html,
  retrieved 2026-08-23; public scientific data). Cite Sears, V. F. (1992).
  *Neutron News* **3**(3), 26–37, and the same author's tabulation in
  *International Tables for Crystallography* Vol. C, ch. 4.4.4, Table 4.4.4.1.
  Thermal values only — no energy dependence, which is a fence for TOF rather
  than a gap for constant wavelength.
- `src/rietx/data/f0_WaasKirf.dat` — Waasmaier & Kirfel (1995) 5-Gaussian f0
  coefficients, obtained from the ESRF DABAX collection (public scientific data,
  redistributed by silx (MIT) among others). Cite Waasmaier & Kirfel (1995).
- `src/rietx/data/mu_McMaster.dat` — photon-atom cross sections from the
  McMaster et al. (1969) compilation (UCRL-50174, a U.S. Government report),
  extracted from the ESRF DABAX file `CrossSec_McMaster.dat` (itself generated
  with P. Bandyopadhyay's mucal). Modified for bundling: energy-trimmed to
  2–120 keV and reduced to the PhotonEnergy/Photoelectric/Total columns (the
  file header documents the same). Cite McMaster et al. (1969).
- `src/rietx/data/f1f2_CromerLiberman.dat` — anomalous scattering factors
  f′, f″, extracted from the DABAX file `f1f2_CromerLiberman.dat` obtained from
  [oasys-kit/DabaxFiles](https://github.com/oasys-kit/DabaxFiles) (MIT,
  © 2022 Manuel Sanchez del Rio), itself generated with D. T. Cromer's FPRIME
  program (version 3F, 1993; redistributed in LLNL's RTAB database) including
  the Kissel & Pratt (1990) high-energy-limit correction. Modified for
  bundling: energy-trimmed to 3–70 keV (the file header documents the same).
  Cite Cromer & Liberman (1970, 1981) and Kissel & Pratt (1990).
  **Deliberately not used:** the DABAX `f1f2_Chantler.dat` file, whose header
  restricts use to the ESRF and which sits over a live NIST Standard Reference
  Data (SRD 66) copyright — SRD is the statutory exception to 17 U.S.C. §105,
  so it is *not* public domain and the DABAX repository's MIT grant cannot
  convey it. Also deliberately not used: `gemmi.cromer_liberman`, although
  gemmi is already a dependency — its f″ is sound (and is used as a test
  oracle) but its f′ disagrees with every published tabulation for several
  lanthanides and actinides.
- Magnetic **form-factor coefficients** in
  `src/rietx/crystallography/magnetic/form_factor.py` (`_J0`, `_J2`) — the
  ⟨j₀⟩ and ⟨j₂⟩ analytic-fit coefficients of Brown, P. J., *International
  Tables for Crystallography* Vol. C, § 4.4.5. Transcribed from the
  **public-domain** `periodictable` package (`periodictable/magnetic_ff.py`,
  © Paul Kienzle; its `LICENSE.txt` opens "Periodictable is in the public
  domain", and the per-file exception it names covers `cromermann.py` only,
  which is not used here), which in turn carries the CrysFML Fortran table.
  `periodictable` is **not** a dependency of this package — the numbers are in
  source, keyed by ion, with no runtime import. The float literals there are
  float32 round-trips of the published four-decimal values (`90.029602` for
  `90.0296`) and were rounded back, with the correction asserted to lie inside
  float32 relative precision so a genuine fifth decimal could not be
  truncated. The CrysFML O(1−) row is deliberately **not** taken: it is
  printed to six decimals, has no ⟨j₂⟩ partner, and does not come from Brown's
  tabulation. Cross-checked against published rows: Fe³⁺ ⟨j₀⟩ (all seven
  coefficients) against arXiv:1309.3683, which cites Dianoux & Lander,
  *Neutron Data Booklet* (OCP Science, 2003), and Mn²⁺ ⟨j₀⟩ (all seven)
  against the 2025 MnF₂ polarised-neutron study. Cite Brown (ITC C § 4.4.5).
  **Deliberately not used:** GSAS-II's `atmdata.py` (spec-only under its
  grant-back clause) and McPhase's table as it travels with Dans_Diffraction
  (GPL) — the numbers in both are Brown's, but those files are not ours to
  copy. `periodictable`'s pre-combined `J` table is also not used: its own
  module docstring writes the dipole coefficient as (1 − 2/g), which is the
  wrong sign, and then says of the table that it "does not seem to be the
  case in practice". Only ⟨j₀⟩ and ⟨j₂⟩ are taken, and the combination
  f = ⟨j₀⟩ + (2/g − 1)⟨j₂⟩ is computed here.
- Element **colours** in `src/rietx/gui/structure3d.py` (`_CPK`) — the
  *assignments* are the CPK convention (Corey & Pauling, 1953, Rev. Sci. Instrum.
  24, 621; Koltun, 1965, US Patent 3,170,246): hydrogen white, carbon black,
  nitrogen blue, oxygen red, sulfur yellow, halogens green, and so on. The hex
  values are **chosen here** for contrast against both a light and a dark page —
  pure white and pure black each vanish into one of them — so no table is
  transcribed from another implementation (Jmol, VESTA and PyMOL all publish one,
  and all are GPL or otherwise unsuitable to copy into an MIT core). Elements the
  convention does not name get a colour *derived* from the atomic number rather
  than looked up. Element **radii** and the metal flag come from gemmi, which is
  already a dependency.
- The **OKLab** colour space in the same module (WP-1029) — Björn Ottosson,
  "A perceptual color space for image processing" (2020),
  https://bottosson.github.io/posts/oklab/, whose reference implementation is
  released as public domain / MIT at the author's option. What is used here is
  the *published transform*: two 3×3 matrices and a cube root, transcribed from
  the paper's own statement of them, which is the same standing as the
  Cromer-Liberman tabulation above — a published numerical definition, not
  someone's implementation of one. It exists because sRGB has no perceptual
  distance, and the whole question the palette pass answers is "are these two
  colours the same colour to a person".
- Test patterns under `tests/data/` — see `tests/data/README.md` for per-file
  provenance (NIST / APS 11-BM public data are works of the U.S. Government).
