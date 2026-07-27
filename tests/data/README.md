# Test data provenance

| File | Contents | Source | License/status |
|---|---|---|---|
| `11BM_NAC.fxye` | Na2Ca3Al2F14 (NAC) powder pattern, APS beamline 11-BM, λ = 0.4139090 Å (from the accompanying `.prm`), 54000 points, GSAS ESD (fxye) format | GSAS-II tutorials repo, `TOF-CW Joint Refinement/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_gsas.prm` | GSAS instrument parameter file for the above (profile from SRM 660a LaB6 fit) | same | same |
| `cod_1000236.cif` | NAC structure, Courbion & Ferey (1988) J. Solid State Chem. 76, 426, space group I2₁3, a = 10.257 Å | Crystallography Open Database entry 1000236 | COD (public domain dedication) |
| `cod_1000055.cif` | LaB6 structure, Pm-3m, a = 4.157597 Å | COD entry 1000055 | COD (public domain dedication) |
| `nist_srm660c_100a.cif` | NIST SRM 660c LaB6 certification dataset incl. measured profile (5332 pts in 24 stitched scan regions, Cu Kα + graphite post-monochromator, NIST DBD, R = 217.5 mm) — v0.2 lab-instrument acceptance (`test_acceptance_srm660c.py`) | NIST Public Data Repository mds2-2315 (data.nist.gov) | NIST open data license (U.S. Government work) |
| `FAP.XRA` | Fluorapatite Ca₅(PO₄)₃F powder pattern, conventional lab Bragg-Brentano, Cu Kα doublet, 15-130.04° 2θ, 5753 pts, GSAS STD (counts-only) format — v0.2 cross-code acceptance (`test_acceptance_fap.py`) | GSAS-II tutorials repo, `LabData/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `INST_XRY.PRM` | GSAS instrument parameter file for the above (λ = 1.5405/1.5443 Å, POLA 0.5, Kα2/Kα1 0.5, starting GU/GV/GW = 2/−2/5 centideg²) | same | same |
| `FAP.EXP` | GSAS's **converged** refinement of `FAP.XRA` — the source of every reference value and of the refinement protocol the acceptance test mirrors | same | same |
| `qarr/cpd-1a.prn` … `qarr/cpd-1h.prn` | IUCr CPD QPA round-robin **Sample 1** suite: eight three-phase corundum (Al₂O₃) / zincite (ZnO) / fluorite (CaF₂) mixtures spanning trace→major for each phase; weighed compositions known (below). 2-column ASCII (2θ°, counts), 5–150° 2θ, 0.02° step, 7251 pts — v0.3 QPA acceptance (`test_acceptance_qpa_roundrobin.py`) | IUCr CPD Quantitative Phase Analysis Round Robin, "col" (2θ,counts) format, `www.iucr.org/__data/iucr/powder/QARR/col/`; retrieved via the Internet Archive (the live IUCr site is behind a Cloudflare JS challenge) | IUCr CPD / CSIRO Minerals round-robin data, freely released on the web (Nov 1999) "for re-analysis with a standard Rietveld code"; no explicit open licence — redistributed here as an academic QPA benchmark, with attribution (see licence note below) |
| `qarr/cpd-2.prn` | **Sample 2** = sample-1 phases + brucite Mg(OH)₂ (strongly platy → preferred-orientation test) | same | same |
| `qarr/cpd-4.prn` | **Sample 4** = corundum / coarse magnetite (Fe₃O₄) / zircon (ZrSiO₄) — microabsorption test | same | same |
| `qarr/corundum.prn`, `qarr/fluorite.prn`, `qarr/zincite.prn`, `qarr/brucite.prn`, `qarr/magnetit.prn`, `qarr/zircon.prn` | Pure single-phase patterns of the round-robin component phases, same instrument/conditions — component references for the mixtures and the SRM 676a corundum comparison | same | same |

Note — the amorphous-bearing **Sample 3** (corundum/fluorite/zincite/glass) is
deliberately **not** in the repo: amorphous / internal-standard quantification
is a v2 fence and an explicit WP-0310 non-goal.

Reference values used in acceptance tests:

- NAC cell: a = 10.257(1) Å at RT per Courbion & Ferey (1988) (COD 1000236);
  high-accuracy powder determinations report a ≈ 10.2496-10.2506 Å depending on
  temperature/calibration — the acceptance test therefore checks internal
  consistency (Le Bail vs Rietveld) and agreement with the 11-BM wavelength
  calibration rather than a certificate-grade absolute value.
- LaB6 SRM 660c certified lattice parameter: a = 4.156826(8) Å **at 22.5 °C**
  (expanded uncertainty, k = 2; NIST certificate,
  tsapps.nist.gov/srmext/certificates/660c.pdf).  The `…_100a` data block was
  measured at 20.85 °C and its CIF records NIST's own recomputed cell for
  exactly this dataset, **a = 4.156780 Å** — the value the acceptance test
  compares against (consistent with the certificate via the Sirota et al. 1998
  thermal expansion used by NIST).  The certificate/CIF wavelength scale is
  λ(Cu Kα1) = 1.5405929 Å (Hölzer et al. 1997), which is what
  `Instrument.bragg_brentano(radiation="CuKa")` ships.
- SRM 660c auxiliary references: CIF-recorded specimen displacement
  −0.07877 mm (the v0.2 fit recovers −0.0801 mm with zero fixed);
  Hölzer integrated Kα2/Kα1 intensity ratio ≈ 0.52 (fit: 0.513).
- Fluorapatite (`FAP.EXP`, GSAS's own converged values — a **cross-code
  consistency** reference, not a certificate): cell a = 9.371724(36) Å,
  c = 6.885867(37) Å (`CRS1 ABC`/`ABCSIG`); Rwp = 0.1005, Rp = 0.0766 over
  5750 channels (`HST 1 RPOWD`); refined Lorentzian size LX = 3.35183 and
  strain LY = 2.48803 centideg, specimen shift `shft` = 4.90166, with
  GU/GV/GW held at 2/−2/5 and the zero point held at 0 (`HAP1 1PRCF` flags
  `NNNYYNNY…`, `HST 1 ICONS`).  Structure (7 sites in P 6₃/m, `CRS1 AT`
  records) is used as the starting model.  The v0.2 fit gives Rwp = 0.0973,
  Rp = 0.0776, LX-equivalent 0.0323°, and a cell +116/+113 ppm from GSAS's —
  a uniform d-scale offset, discussed in the test's module docstring.

## v0.3 QPA acceptance data (WP-0310)

**CPD round-robin standard-data-set instrument** (every `qarr/*.prn`): Philips
3020 goniometer + PW3710 controller, 17.3 cm radius; Cu long-fine-focus tube
(40 kV, 40 mA); flat-plate Bragg–Brentano reflection; back-packed, **unspun**
sample; 1° divergence + 1° scatter + 0.3 mm receiving slits; incident- and
diffracted-beam Soller slits; diffracted-beam **curved graphite monochromator**;
proportional counter. Step scan 5–150° 2θ at 0.02°, 3 s/step (7251 points).
Radiation is the Cu Kα doublet — the Sietronics `.cpi` header records
λ = 1.54056 Å (Kα1); the diffracted-beam graphite monochromator removes Kβ but
passes the Kα1/Kα2 doublet. The acceptance tests model it on the
**NIST/Hölzer wavelength scale** (1.5405929/1.5444274 Å — what the `CuKa`
preset ships): the SRM 676a certificate anchor lives on that scale, and the
`.cpi` header's 1.54056 is the same emission line quoted at its older nominal
value (a 22 ppm d-scale choice that would map straight onto the cell being
compared). The `.prn` files are plain two-column ASCII (2θ°, counts) — the
generic xy reader handles them, locked in by
`test_acceptance_qpa_roundrobin.test_read_prn_two_column_ascii`; raw counts
only (no esd column → Poisson √max(y,1) weights per the CLAUDE.md weighting
invariant).

**Round-robin weighed compositions** — the QPA "truth" the acceptance checks
against (mass %, from the CPD "Weighed and Measured Values" page, released
8 Nov 1999):

| Sample | Al₂O₃ (corundum) | ZnO (zincite) | CaF₂ (fluorite) | other |
|---|---|---|---|---|
| 1a | 1.15 | 4.04 | 94.81 | — |
| 1b | 94.31 | 1.36 | 4.33 | — |
| 1c | 5.04 | 93.59 | 1.36 | — |
| 1d | 13.53 | 32.89 | 53.58 | — |
| 1e | 55.12 | 15.25 | 29.62 | — |
| 1f | 27.06 | 55.22 | 17.72 | — |
| 1g | 31.37 | 34.21 | 34.42 | — |
| 1h | 35.12 | 30.19 | 34.69 | — |
| 2  | 21.27 | 19.94 | 22.53 | Mg(OH)₂ 36.26 |
| 4  | 50.46 | — | — | Fe₃O₄ 19.64, ZrSiO₄ 29.90 |

Independent XRF cross-checks on the same page agree with the weighings to
< 1 wt % (e.g. 1g XRF 31.70 / 34.01 / 33.86). Sample **1g** (≈⅓ each) is the
CPD's recommended single-sample option.

**Participant spread is the yardstick, not an arbitrary band.** Even for the
deliberately "simple" sample 1 — phases chosen for minimal microabsorption,
preferred orientation, broadening and overlap — participant-submitted weight
fractions scattered widely (Madsen et al. 2001, Fig. 2 ternary; "note the
spread of results"). The round-robin acceptance tolerance must be *referenced
to that published spread*: matching the weighed values **better** than the
participant spread would be a suspicious result, not a triumph (WP-0310
context). Sample 2 (platy brucite → preferred orientation) and sample 4
(microabsorption "really beyond the limits of the Brindley model in this case",
Scarlett et al. 2002) exacerbate the scatter and exercise the WP-0307 texture
and WP-0305 µR-fence machinery respectively.

- Madsen, I. C.; Scarlett, N. V. Y.; Cranswick, L. M. D.; Lwin, T. (2001).
  *Outcomes of the IUCr CPD Round Robin on Quantitative Phase Analysis: Samples
  1a–1h.* J. Appl. Cryst. **34**, 409–426.
- Scarlett, N. V. Y.; Madsen, I. C.; Cranswick, L. M. D.; Lwin, T.; Groleau, E.;
  Stephenson, G.; Aylmore, M.; Agron-Olshina, N. (2002). *…Samples 2, 3, 4,
  synthetic bauxite, natural granodiorite and pharmaceuticals.* J. Appl. Cryst.
  **35**, 383–400.

**NIST SRM 676a certified values** — Certificate of Analysis, issue
04 Nov 2015 (lattice values certified 23 Apr 2012; original 28 Jan 2008),
`tsapps.nist.gov/srmext/certificates/676a.pdf`; **U.S. Government work**.
Material: α-Al₂O₃ (corundum, *R*-3c), Baikowski alum-route alumina, sub-µm
equiaxed grains (chosen to be non-orienting).

- Certified **crystalline mass fraction 99.02 % ± 1.11 %** (k = 2), the balance
  being a disordered/amorphous surface layer — certified by extrapolating a
  series of SRM 640c-silicon mixtures to zero specific surface area (neutron TOF
  + 25 keV & 67 keV synchrotron, to beat extinction). This is an **amorphous**
  quantity → *outside* the WP-0310 scope; recorded here for completeness only.
- Certified lattice parameters **at 22.5 °C** (k = 2, Type A ⊕ Type B):
  **a = 4.759355 Å ± 0.000080 Å**, **c = 12.99231 Å ± 0.00015 Å**. Certificate
  peak positions use Cu Kα λ = 1.5405929 Å (Hölzer et al. 1997). This is the
  **absolute anchor** the corundum test compares a refined lab-data cell
  against — but NIST publishes **no raw 676a pattern**, and lab
  zero/displacement systematics dominate ordinary Bragg–Brentano data, so the
  practical cell tolerance is far looser than the certificate's ~17 ppm(a) /
  ~12 ppm(c) uncertainty (a point the test task must set honestly). The
  round-robin `qarr/corundum.prn` is a lab α-Al₂O₃ pattern whose provenance is
  **not** documented as SRM 676a, so it stands in as a corundum *specimen*, not
  as the certified material itself.

**Licence note (round-robin data).** The `qarr/*.prn` patterns were placed on
the public IUCr CPD web site in 1999 explicitly for anyone to download and
re-analyse; the sample suite and data originate from CSIRO Minerals (I. Madsen,
R. Hill) under the IUCr Commission on Powder Diffraction. No explicit open
licence (CC0/CC-BY) is attached. They are redistributed here, with attribution,
as a standard QPA benchmark for the exact purpose for which they were released.
The **papers** above are © IUCr (all rights reserved) — cited, never
redistributed. If the IUCr/CSIRO prefer these files not be vendored, they can be
dropped in favour of a fetch-on-demand script against the Internet Archive.

## backend_goldens/ — WP-0401 bit-identity baseline

`backend_goldens/*.npz` hold `evaluate`/residual/Jacobian arrays for the
states defined in `tests/test_backend_shim.py`.  The first five (`srm660c`,
`nac`, `toy_lebail`, `toy_pawley`, `toy_rich`) were captured from the tree
**before** the WP-0401 backend-shim refactors (at commit `c9fc8c0`, numpy 2.x /
macOS arm64 Accelerate).  `toy_restraints` was added by WP-0406 (soft-restraint
penalty rows) from the green post-WP-0406 tree — a *new* baseline, so the
existing five were not re-captured.  `test_backend_shim.py` asserts the current
tree reproduces each **bit-for-bit** (`np.array_equal`) — the acceptance gate
for "nothing here may change a single computed number on the numpy path".

These are *environment-pinned* bit patterns, not physical reference values: a
different BLAS/numpy build may legitimately differ in final bits.  Re-baseline
only from a tree that passes the full suite, via
`.venv/bin/python -m tests.test_backend_shim`, and say so in the commit message.
