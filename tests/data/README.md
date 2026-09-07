# Test data provenance

| File | Contents | Source | License/status |
|---|---|---|---|
| `11BM_NAC.fxye` | Na2Ca3Al2F14 (NAC) powder pattern, APS beamline 11-BM, λ = 0.4139090 Å (from the accompanying `.prm`), 54000 points, GSAS ESD (fxye) format | GSAS-II tutorials repo, `TOF-CW Joint Refinement/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_gsas.prm` | GSAS instrument parameter file for the above (profile from SRM 660a LaB6 fit) | same | same |
| `11BM_Si640c.xy` | NIST SRM 640c silicon powder pattern, APS beamline 11-BM run 4918 (25 Feb 2010), λ seeded at the header's stated 0.412359 Å, 48000 points, 1.996–49.995° 2θ at 0.001°, three columns (2θ, I, propagated σ). Header: `Sample name = Silicon (Si) NIST SRM 640c, certified cell length of 5.4311946 Angstroms` / `Run no. = 4918` / `Calibration file = feb10/11bmb_4917.calib` / `Calibrated wavelength = 0.412359`. The single-histogram refinable-wavelength anchor (`test_acceptance_si640c.py`) — see the section below | APS 11-BM's **published** standard-reference scan of NIST SRM 640c (run 4918, Feb 2010): a facility calibration measurement, not a user sample (its header carries no proposal, user or contact field, unlike this directory's mail-in patterns). Published on 11-BM's Standards Data listing, `wiki-ext.aps.anl.gov/ug11bm/index.php/Standards_Data`; the live download links have since gone dead in a site migration, so the published container was recovered via the Internet Archive (as with the `qarr/*.prn` files below). The committed `.xy` is **verified bit-identical** to the beamline's published `11BM_Si640c` container across all 48 000 retained channels — 2θ, intensity **and** propagated esd exactly equal, `np.array_equal` on all three — with only the first 1 496 low-angle channels (0.500–1.995° 2θ) trimmed off and the comment markers reformatted (`!`→`##`) | Argonne/APS standard-reference scan (U.S. Government work; publicly distributed) — a citable public route, not a private grant |
| `11BM_LaB6_660a.fxye` | NIST SRM 660a LaB6 powder pattern, APS beamline 11-BM, λ = 0.4131280 Å (from the accompanying `.prm`), 132992 points, 0.4995-66.995° 2θ at 0.0005°, 295.0 K, GSAS ESD (fxye) format — the **capillary** specimen of the v0.5 absorption acceptance (`test_acceptance_capillary.py`). Its own header identifies it: `sample_name, "SRM 660a"` / `chemical_formula, "Lanthanum Hexaboride (LaB6)"` / `comment1, "robotic collection"` | GSAS-II tutorials repo, `FitPeaks/data/11bmb_3844.fxye` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_lab6_gsas.prm` | GSAS instrument parameter file for the above (λ = 0.4131280 Å, POLA 0.99, profile from the same Feb-2009 SRM 660a fit as `11bm_gsas.prm`) | same, `11bmb_3844.prm` | same |
| `11BM_LaB6_cBN_mg2044.xye` | NIST **SRM 660b LaB₆** + cubic BN two-phase mixture, APS beamline 11-BM, λ = 0.413680 Å (`.prm` ICONS; POLA 0.990), 49 496 points, 0.5–49.99° 2θ at 0.001°, three-column `xye` with **propagated esds** (twelve analyser crystals summed, so column 3 is not √I). From the file header: run **3095**, scanned **17 Feb 2014**, proposal **31405**, user sample name **mg2044**, **295.0 K**, 0.1 s/step, goniometer radius 1000 mm, robotic mail-in collection. (The header's e-mail and sample-barcode fields are redacted in the committed copy — personal contact detail and facility bookkeeping; every data channel is byte-identical to the original.) **No weighed composition is recorded** — the header gives only "Boron Nitride and lanthanum hexaboride" — so every claim referenced to this file is cross-code against two solved TOPAS refinements of it (`lab6_pvii_absorb_cs_mustr` → LaB₆ 17.950 wt %, cBN a = 3.616463 Å; `lab6_pvii_absorb_IB-size-strain` → 17.907 wt %, a = 3.616466 Å; `simulation_quant.txt` → 17.90681). **Those TOPAS `.inp`/`.out`/`.txt` reference files are not committed — they live on the data owner's archive, not in this directory**: the protocol is transcribed into `test_acceptance_lab6_cbn.py`'s docstring and the values recorded in `tests/validation_matrix.py`, but the source files are not in this repo. Two-phase QPA and identifiability acceptance (`test_acceptance_lab6_cbn.py`) | Collected at APS 11-BM under proposal 31405 (M. W. Gaultois, then UC Santa Barbara); robotic mail-in collection, run 3095 | Contributed by the data owner, M. W. Gaultois, for redistribution with this package under the repository's terms. Not a beamline standard scan and not publicly distributed by APS — unlike `11BM_Si640c.xy`, whose row cites a public route; measured Pearson r = 0.499 against the beamline's published single-phase SRM 660b, i.e. a different specimen (a two-phase 660b + cBN mixture) |
| `cod_1000236.cif` | NAC structure, Courbion & Ferey (1988) J. Solid State Chem. 76, 426, space group I2₁3, a = 10.257 Å | Crystallography Open Database entry 1000236 | COD (public domain dedication) |
| `cod_1000055.cif` | LaB6 structure, Pm-3m, a = 4.157597 Å | COD entry 1000055 | COD (public domain dedication) |
| `nist_srm660c_100a.cif` | NIST SRM 660c LaB6 certification dataset incl. measured profile (5332 pts in 24 stitched scan regions, Cu Kα + graphite post-monochromator, NIST DBD, R = 217.5 mm) — v0.2 lab-instrument acceptance (`test_acceptance_srm660c.py`) | NIST Public Data Repository mds2-2315 (data.nist.gov) | NIST open data license (U.S. Government work) |
| `FAP.XRA` | Fluorapatite Ca₅(PO₄)₃F powder pattern, conventional lab Bragg-Brentano, Cu Kα doublet, 15-130.04° 2θ, 5753 pts, GSAS STD (counts-only) format — v0.2 cross-code acceptance (`test_acceptance_fap.py`) | GSAS-II tutorials repo, `LabData/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `INST_XRY.PRM` | GSAS instrument parameter file for the above (λ = 1.5405/1.5443 Å, POLA 0.5, Kα2/Kα1 0.5, starting GU/GV/GW = 2/−2/5 centideg²) | same | same |
| `FAP.EXP` | GSAS's **converged** refinement of `FAP.XRA` — the source of every reference value and of the refinement protocol the acceptance test mirrors | same | same |
| `fluorapatite.cif` | The `FAP.EXP` starting model (7 sites, P 6₃/m, a = 9.3717, c = 6.8859 Å) transcribed to CIF, for `examples/fap_lab.py` and the landing page's worked example. **Not** used by `test_acceptance_fap.py`, which builds the same model from the `CRS1 AT` records instead — one authority per number, and it is not this file | transcribed from `FAP.EXP` (same tutorial repo); the published structure it descends from is Hughes, Cameron & Crowley (1989), *Am. Mineral.* **74**, 870-876 | same |
| `qarr/cpd-1a.prn` … `qarr/cpd-1h.prn` | IUCr CPD QPA round-robin **Sample 1** suite: eight three-phase corundum (Al₂O₃) / zincite (ZnO) / fluorite (CaF₂) mixtures spanning trace→major for each phase; weighed compositions known (below). 2-column ASCII (2θ°, counts), 5–150° 2θ, 0.02° step, 7251 pts — v0.3 QPA acceptance (`test_acceptance_qpa_roundrobin.py`) | IUCr CPD Quantitative Phase Analysis Round Robin, "col" (2θ,counts) format, `www.iucr.org/__data/iucr/powder/QARR/col/`; retrieved via the Internet Archive (the live IUCr site is behind a Cloudflare JS challenge) | IUCr CPD / CSIRO Minerals round-robin data, freely released on the web (Nov 1999) "for re-analysis with a standard Rietveld code"; no explicit open licence — redistributed here as an academic QPA benchmark, with attribution (see licence note below) |
| `qarr/cpd-2.prn` | **Sample 2** = sample-1 phases + brucite Mg(OH)₂ (strongly platy → preferred-orientation test) | same | same |
| `qarr/cpd-4.prn` | **Sample 4** = corundum / coarse magnetite (Fe₃O₄) / zircon (ZrSiO₄) — microabsorption test | same | same |
| `qarr/corundum.prn`, `qarr/fluorite.prn`, `qarr/zincite.prn`, `qarr/brucite.prn`, `qarr/magnetit.prn`, `qarr/zircon.prn` | Pure single-phase patterns of the round-robin component phases, same instrument/conditions — component references for the mixtures and the SRM 676a corundum comparison | same | same |
| `bethanechol_indexing.json` | The **indexing benchmark**: ten sets of twenty 2θ positions for bethanechol chloride (C₇H₁₇ClN₂O₂), the known answer (monoclinic P2₁/n, a = 8.875, b = 16.408, c = 7.137 Å, β = 93.84°, V = 1036.9 Å³), the published M(20) = 197 / F(20) = 1080, and Table 5's scores — v1.0 indexing acceptance (`test_acceptance_indexing.py`) | Bergmann, Le Bail, Shirley & Zlokazov (2004), *Z. Kristallogr.* **219**, 783-790, Tables 5 and 6 | Published tables, transcribed with attribution; **no program output and no code** — see the section below |
| `hl2_peaks.txt` | 74 peak positions (2θ, d, I_rel) from a **genuinely unindexed** laboratory pattern, Cu Kα1 — the abstention fixture, whose correct answer is "we do not know" | Our own derived product: peaks picked from `HL2-1_2.xy` in the `examples/` folder of datalab-org/guillemot (MIT), which is *not* vendored here | Derived table, carried with attribution |
| `absorption_cylinder_rouse.dat` | Cylinder **transmission** factor A (not A\* = 1/A) vs µR and sin²θ, 4 dp — 80 values: the full sin²θ = 0 column (µR 0.00–0.50 step 0.01) plus four complete µR = 0.50 / 1.00 rows. Ground truth for the WP-0501 capillary absorption correction (`test_absorption.py`) | Rouse, Cooper, York & Chakera (1970), *Acta Cryst.* **A26**, 682-691, Table 1(a)/(b) | Published table, transcribed with attribution; no code involved |

Note — the Rouse fixture carries only the blocks that could be read
unambiguously from the available scan (each cell holds five *consecutive* µR
rows and the printed labels are offset by three; see the file header). Every
value in it was checked against a quadrature of ITC Vol. C eq. (6.3.3.4) before
being committed — max difference 1.7e-4, within the table's own four-decimal
resolution. The damaged remainder of the grid is deliberately absent rather than
guessed.

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
- LaB6 **SRM 660a** (the 11-BM capillary pattern) certified lattice parameter:
  a = 4.1569162(97) Å at 22.5 °C (k = 2; NIST certificate,
  tsapps.nist.gov/srmext/certificates/archives/660a.pdf).  **Not an anchor for
  this dataset** — see the capillary section below.
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

The two *pure-phase* patterns `qarr/brucite.prn` and `qarr/corundum.prn` carry a
second job from WP-0503, as the anisotropic-strain acceptance pair
(`test_acceptance_stephens.py`): brucite as the candidate for directional
broadening and corundum as the isotropic control on the same instrument,
protocol and channel count. **The reference values there are not a certificate —
they are a characterisation**, and the headline one is negative: three Stephens
patterns improve brucite's Rwp from 18.55 % to 17.90 % with ΔBIC = +488 and
still drive σ²(M) negative on 12 of 43 reflections. Corundum: Rwp 14.37 %,
ΔBIC = −17, Layer-1 anisotropy 1.60× and `detected=False`. Re-measure both
before changing any of them.

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

## v0.5 capillary absorption acceptance data (WP-0508)

`11BM_LaB6_660a.fxye` is the repo's only pattern from a specimen whose
**container is specified**, which is what makes a capillary-absorption
acceptance possible at all: µR needs a bore radius and a composition, and most
published patterns state neither.

**The container.** 11-BM is a transmission (Debye-Scherrer) instrument, and its
rapid-access mail-in program supplies exactly one standard capillary:
"Standard Size = 0.8 mm diameter Kapton tube and mounting base", identified on
the beamline's *Supplies and Tools* page as Cole-Parmer #95820-06,
**ID 0.0320″ = 0.81 mm**, OD 0.0340″ = 0.86 mm (a 1.5 mm size was added later).
This scan's header records `comment1, "robotic collection"` — the mail-in robot,
which takes only those bases. So R = 0.405 mm is the documented standard
container, not a measurement of this particular tube.

**µR.** With the LaB6 composition and λ = 0.4131280 Å, `rietx.estimate_mu_r`
gives µ = 33.7 cm⁻¹ for the crystalline solid, hence

| packing fraction | 0.35 | 0.50 | 0.60 |
|---|---|---|---|
| µR | 0.47 | 0.67 | 0.81 |

all inside the Rouse et al. (1970) fit's stated range (µR ≤ 1). Packing is the
one input nobody measures; the acceptance is built so that **its conclusion does
not depend on the value** (below).

**The cell is not an anchor for this dataset, and the reason is in the file
header.** `# Calibration from: /data/oct09/11bmb_3843.calib` — λ was calibrated
at the beamline against LaB6 itself, so refining a LaB6 cell against it is
circular: a is pinned by construction to reproduce the standard. It does
(a = 4.156850 Å vs the certificate's 4.1569162 Å at 22.5 °C, 16 ppm, with the
scan at 295.0 K worth ≈ −4 ppm of that), and that is quotable as a consistency
check only. The absolute cell anchors remain SRM 660c (`nist_srm660c_100a.cif`,
lab flat plate) and SRM 676a (`qarr/corundum.prn`).

**What the acceptance asserts instead.** The Rouse transmission factor is
*exactly* a constant times exp(c·sin²θ), so applying it is an exact
reparameterisation of {phase scale, Biso}: the fit cannot improve, and the
displacement parameters carry the entire content. Measured over 2–60° 2θ
(116 001 points), the same staged plan run with and without µR = 0.674:

| | no correction | µR = 0.674 | Δ |
|---|---|---|---|
| Rwp | 0.0884883 | 0.0884884 | +3.2e-8 |
| a (Å) | 4.1568496 | 4.1568496 | −7.9e-12 |
| B(La) (Å²) | 0.453890 | 0.470545 | **+0.0166542** |
| B(B) (Å²) | 0.205395 | 0.222049 | **+0.0166542** |

against `equivalent_delta_biso(0.674, 0.413128) = 0.0166542`. Any µR would give
the same *form* of result with its own predicted shift, which is why the
packing-fraction uncertainty does not weaken it.

**The absolute Biso here is not a reference value.** Turning on anomalous
dispersion (WP-0504; La at 30 keV has f′ = −1.22, f″ = +0.94, its K edge being
at 38.9 keV) moves B(La) 0.4539 → 0.4098 and B(B) 0.2054 → 0.2690 — 2.6× the
absorption effect and, for La, in the opposite direction. Two independent biases
land on the same parameters; only the difference this test measures is
attributable to absorption, and the identity above reproduces to 0.0166540 with
dispersion switched on, which is the check that they are independent.

## Refinable-wavelength acceptance data — the published Nd₂Ru₂O₇ pair

Four files, **1 711 066 bytes** (1.63 MiB) total: the two histograms of a
published joint refinement, plus the instrument-parameter file of each.

| file | bytes | instrument | λ (Å) | points | range (°2θ) | σ |
|---|---|---|---|---|---|---|
| `mg090.fxye` | 1 654 008 | APS 11-BM synchrotron X-ray, 295 K | 0.4132950 | 49 493 | 0.500–49.992 | from file |
| `mg090.prm` | 1 134 | its GSAS instrument-parameter file (`ICONS 0.4132950`, POLA 0.990) | — | — | — | — |
| `mg090.Cu311.gsas` | 54 366 | NCNR BT-1 neutron, Cu(311) monochromator, 300 K | 1.54040 | 3 296 | 3.000–167.750, 0.05° step | from file |
| `mg090.Cu311.inst` | 1 558 | its GSAS instrument-parameter file (`ICONS 1.54040`) | — | — | — | — |

Nd₂Ru₂O₇ pyrochlore, one specimen. The `.prm` and `.inst` are committed for the
same reason as the patterns: `ICONS` is where each wavelength comes from, so
committing them keeps the wavelength's provenance in the repository instead of
as a literal in a test.

**What they are for.** These are the only two histograms in the suite that are
*one specimen at two wavelengths*, which makes them the only dataset that can
exercise a refinable wavelength at all — for one histogram λ and the cell are
exactly degenerate, and the degeneracy breaks only across histograms sharing one
cell. They come from a published refinement whose stated method *is* the
feature, so `tests/test_acceptance_wavelength.py` asks "does rietx reproduce a
published refinement that required this", not "does the new parameter move".

**Reference values, published.** Gaultois *et al.*, "Structural disorder,
magnetism, and electrical and thermoelectric properties of pyrochlore
Nd₂Ru₂O₇", *J. Phys.: Condens. Matter* **25** (2013) 186004,
[doi:10.1088/0953-8984/25/18/186004](https://doi.org/10.1088/0953-8984/25/18/186004)
(preprint [arXiv:1301.6661](https://arxiv.org/abs/1301.6661)) — the combined
refinement of these two histograms:

| quantity | published |
|---|---|
| a (Å) | 10.342312(8) |
| x(O 48f) | 0.33012(7) |
| data points | 51 295, a subset of these files' 49 493 + 3 296 |
| refined neutron λ (Å) | 1.5406704, from a declared 1.54040 (+176 ppm) |

and the paper's own account of the protocol, which is what this feature
implements: *"the synchrotron X-ray wavelength was fixed while the neutron
wavelength was allowed to vary, though the refined wavelength was within two
standard deviations of the starting value"*. The paper gives the Cu(311)
monochromator as λ = 1.5402(2) Å with a **second-order contribution at λ/2**.

**Cross-code consistency, not an absolute anchor** — the distinction this file
draws elsewhere. `nist_srm660c_100a.cif` and `qarr/corundum.prn` are absolute
cell anchors because a certificate says what the answer is; here the reference is
another refinement of the same data, so agreement bounds a modelling difference
rather than an error. The single-phase fit in the acceptance suite lands
a = 10.342904(60) Å, **+57 ppm** above the published value. Three modelling
differences sit behind that: the published refinement carries 0.5(1) mol % RuO₂
alongside, models the λ/2 second-order contribution, and frees **one A-site
occupancy** — Ru substituting on the Nd site, converging at 7.0(3) mol % — where
rietx's fit does none of the three. x(O 48f) 0.32994(51) is inside its own esd of
the published 0.33012(7).

**The occupancy is the one not to copy**, and the paper is the reason. It
concludes that A-site disorder is *suggested*, not established, and says why in
its own terms: allowing it improves the fit only marginally; the neutron
histogram cannot see it at all, because Nd and Ru have nearly the same coherent
scattering length — 7.69 fm against 7.03 fm, the values Sears (1992) tabulates
and gemmi ships — so the Z contrast lives entirely in the synchrotron
histogram; and an X-ray PDF of the same specimen would not
settle it either — the substitution refined to unphysical occupancies there
(correlated with the scale factor), and ideal ordering against 7.0 % Ru gave
R = 10.05 % against 10.02 %, a difference the paper describes as smaller than
the noise in the fit. There is **no occupancy constraint** in the published
work, and none in this repository: `test_acceptance_wavelength.py::_structure`
builds four atoms at full default occupancy, which is a deliberate agreement
with the paper's own conclusion rather than a simplification of it.

Worth quoting for the reason it is a caveat and not a footnote, since this
package keeps meeting the same problem: on the Hamilton test that made the
improvement formally significant, the paper notes that *"with only one
additional parameter between the two models, the large number of independent
measurements makes virtually any improvement in Rwp statistically
significant"*. A significance test against 51 295 points is not a model
comparison, which is the argument for judging a marginal extra parameter on
what it changes rather than on whether Rwp fell.

**Kennedy & Vogt (1996)**, *J. Solid State Chem.* **126**, 261–270 (ICSD 82304)
is the citable *structure* reference for Nd₂Ru₂O₇ — Fd-3m:2, a = 10.3442(1),
x(O 48f) = 0.3301(2), Biso 0.86 / 0.20 / 0.50 / 0.69, R = 0.022 — and is where
the acceptance suite's site assignment comes from: Nd on 16d (½,½,½), Ru on 16c
(0,0,0), O1 on 48f (x,⅛,⅛), O2 on 8b (⅜,⅜,⅜).

**Known confound this package does not model.** The Cu(311) monochromator passes
a second-order λ/2 component, which the paper states and models and rietx does
not. It is the obvious candidate for the difference between the +176 ppm
published wavelength shift and the +258 ppm the acceptance suite measures — the
same sign and order from a different code and a different model. Read the two as
agreeing about the *existence and size* of a calibration error, not as two
measurements of one number.

## Single-histogram refinable-wavelength acceptance data — Si SRM 640c

`11BM_Si640c.xy`, **1 517 979 bytes**: one APS 11-BM synchrotron pattern of NIST
SRM 640c silicon, and the flagship of the *single-histogram* refinable wavelength
(WP-1128 made a free λ admissible when the cell is held; WP-1134 gave it the
`WAVELENGTH_CALIBRATION` record). `test_acceptance_si640c.py`.

**Provenance — the beamline's own published standard, cited not asserted.** Run
4918, `11bmb_4918.mda` processed 2010-02-10, scan collected 25 Feb 2010;
calibration file `11bmb_4917.calib`; `Sample name = Silicon (Si) NIST SRM 640c,
certified cell length of 5.4311946 Angstroms`; `Calibrated wavelength =
0.412359`. This is not a private contribution but APS 11-BM's **publicly
distributed** standard-reference scan: the facility publishes its SRM
calibration measurements on the 11-BM Standards Data listing
(`wiki-ext.aps.anl.gov/ug11bm/index.php/Standards_Data`). The live download
links died in a site migration, so the published container was recovered via the
Internet Archive — and the committed `.xy` here is **verified bit-identical** to
that published `11BM_Si640c` container across all 48 000 retained channels (2θ,
intensity and propagated esd all exactly equal), differing only in that the first
1 496 low-angle channels (0.500–1.995° 2θ) are trimmed and the comment markers
are reformatted (`!`→`##`). So the file rests on public distribution as a
U.S. Government work, not on anyone's authorisation. 48 000 points,
1.996–49.995° 2θ at 0.001°, three columns. The third column is a **real
propagated esd** (11-BM sums twelve analyser crystals; median σ/√I = 0.9675 over
the range, so it is not √I), and `read_pattern` uses it.

**No weighed anything — the certificate is the cell, XND is the cross-code.**
This dataset has two references and they answer different questions:

| reference | what it fixes | tier |
|---|---|---|
| NIST SRM 640c certificate | a = 5.4311946 ± 0.0000092 Å at 22.5 °C, **held** | certificate (identity) |
| XND 1.42 (Bérar & Baldinozzi) | the refined λ, zero, Biso of the same `.xy` | cross-code |

The held certificate cell is what licenses a free λ (a powder measures only the
product λ·(1/d), so one of the two must be pinned), and it is asserted as an
*identity*, not measured. Everything the fit *refines* — λ above all — is
referenced to **XND 1.42**, an independent code that refined this exact scan;
its files (`Si640c.k`/`.new` inputs, `Si640c.lst` log) live beside the data on
the owner's archive. XND's Bérar is the same one rietx's Bérar–Lelann esd
inflation implements, so the esds are comparable.

**XND's converged numbers** (`Si640c.lst`, cell held at 5.4311948 Å — 0.4 ppm
above the certificate rietx holds, negligible):

| quantity | XND |
|---|---|
| λ (Å) | 0.412376076 ± 0.000000379 (+41.4 ppm off the header's 0.412359) |
| zero (°) | −0.00048302 ± 0.00001424 |
| Biso(Si) (Å²) | 0.438984 ± 0.001711 |
| Rwp / Rp / GoF | 0.0961 / 0.0691 / 1.49 (Rexp 0.065) |
| correlations > 0.6 | λ~zero −0.897, zero~asym +0.941, λ~asym −0.738, scale~Biso +0.691 |

**What rietx does differently, and why the headline is a pair.** rietx co-refines
a penalized P-spline background rather than XND's eleven interpolated points
(measured to move λ < 0.1 ppm; Si is far above its K edge so dispersion is inert
too), and models the low-angle asymmetry as **Finger–Cox–Jephcoat** axial
divergence (tied `axial_sl` = `axial_hl`) rather than XND's empirical A_T2. The
asymmetry is the whole story: on XND's own 2–50° range rietx lands λ at +30 ppm,
11 ppm short of XND, and that gap **is** the FCJ-vs-A_T2 convention — λ trades it
against zero along a ρ = −0.9 ridge. Restrict to the *symmetric* peaks (≥ 8°,
below which the (111) sits) where neither code applies a consequential asymmetry
correction, and the agreement collapses to −0.4 ppm. The sub-ppm number lives
where the two codes model the same physics; the residual is named, not tuned
away. Either way λ moves +30 to +41 ppm off the beamline's stated 0.412359 at
many σ — the calibration error the feature exists to detect.

**Certificate Information Values, used as a NOTE only.** SRM 640c's certificate
carries NIST's own fundamental-parameters Lorentzian sample-broadening FWHM
(°2θ) = 0.0065(5)/cos θ + 0.0086(6)·tan θ (a ~1.4 µm crystallite size, ~0.02° on
(533)), which maps unit-for-unit onto rietx's `lor_size` and `lor_strain`. No
equality is asserted: NIST's split is FPA-based and taken at its Cu Kα
instrument, not at 11-BM, so the instrument/sample division differs by
convention. The certificate's median particle size (4.9 µm) is of **agglomerates**
and is not a broadening input. Measured here: `lor_size` ≈ 0.0023, `lor_strain`
≈ 0.015 — the same order, apportioned differently.

## backend_goldens/ — WP-0401 bit-identity baseline

`backend_goldens/*.npz` hold `evaluate`/residual/Jacobian arrays for the
states defined in `tests/test_backend_shim.py`.  The first five (`srm660c`,
`nac`, `toy_lebail`, `toy_pawley`, `toy_rich`) were captured from the tree
**before** the WP-0401 backend-shim refactors (at commit `c9fc8c0`, numpy 2.x /
macOS arm64 Accelerate).  `toy_restraints` was added by WP-0406 (soft-restraint
penalty rows) from the green post-WP-0406 tree — a *new* baseline, so the
existing five were not re-captured.  `toy_stephens` (WP-0503, hkl-dependent
anisotropic-strain widths), `toy_capillary` (WP-0501, cylindrical absorption),
`toy_roughness` (WP-0502, Bragg-Brentano Suortti surface roughness: an `exp`
of a reciprocal `sin`, folded into `phase_peaks` and both analytic column
builders) and `toy_anomalous` (WP-0504, anomalous f′/f″ on a
non-centrosymmetric structure — the only state where the Friedel-averaged
|A|² + |B|² differs from |F|² at the orbit representative) were added the same
way, each from its own green tree and each capturing only the new state — the
earlier goldens were left untouched every time.  `toy_capillary` and
`toy_roughness` are deliberately a pair: one locks the capillary intensity
factor, the other the flat-plate one.
`test_backend_shim.py` asserts the current
tree reproduces each **bit-for-bit** (`np.array_equal`) — the acceptance gate
for "nothing here may change a single computed number on the numpy path".

**WP-1112 re-baselines (2026-08-21), two distinct events:**

1. *Batched derivative bases*: `srm660c` and `toy_rich` — the two FCJ-live
   states — re-captured.  Only their `jacobian` key moved, by ≤ 7.4e-16 and
   ≤ 2.5e-16 per-column relative: the FCJ node-weighted sums are batched
   matmuls where the loop ran one dgemv per reflection, and the node
   generation is vectorised (`fcj_offsets_weights_batch`) — reduction-order
   changes inside the WP's declared ≤ ~1e-15 bar.  Every other state and key
   reproduced bit-for-bit un-recaptured, which is the measured evidence for
   the WP's other claim: symmetric rows batch **bit-identically**.
2. *Area-criterion windows*: **all ten** states re-captured.  Window extents
   are compiled state, so every `y_calc`/`residual`/`jacobian` moves with
   them; the equivalence argument is the recorded tolerance
   (`forward.WINDOW_AREA_TOL = 2e-2`, the discarded-area bound, chosen by the
   sweep in the WP file: QPA round-robin fractions flat to < 0.3 wt % from
   5e-3 to 5e-2 while the protocol fits ran 1.9-2.4× faster) — not an Rwp
   comparison, which legitimately *rises* in the third digit as the
   truncated tail residue becomes visible.

**WP-1121 re-baseline (2026-08-22)**: the eight states with a free
`phases.N.scale` — `srm660c`, `nac`, `toy_rich`, `toy_restraints`,
`toy_stephens`, `toy_capillary`, `toy_roughness`, `toy_anomalous`.  Only their
`jacobian` key moved and, inside it, **only the `.scale` columns** (1 of 22, 2
of 25, 1 of the rest), by 2.4e-6 to 8.1e-6 relative.  That is a deliberate
accuracy change, not a reduction-order one: the intensity is exactly linear in
a phase scale, so `_scale_column` computes ∂y/∂scale in closed form where the
peak-chain FD carried the softplus transform's O(h) curvature error — the new
column agrees with a difference quotient in *physical* space (which has no
truncation error at any step) to 3.6e-16, the old one to 4.6e-6.  `toy_lebail`
and `toy_pawley` were **not** re-captured and reproduce bit-for-bit: those
modes force-fix the scale, so they have no such column, which is the
independent check that the `rietveld`-only guard on the new branch holds.  The
same tree's depth-2 scalar memo moved no key of any state, which is what
bit-identical means for it.

These are *environment-pinned* bit patterns, not physical reference values: a
different BLAS/numpy build may legitimately differ in final bits.  **WP-1002
measured which half of that sentence is true.**  The *numpy* half is not:
Python 3.11 with numpy 2.4.6 / scipy 1.17.1 and Pythons 3.12/3.13/3.14 with
2.5.1 / 1.18.0 all reproduce every golden bit-for-bit on macOS/arm64.  The
*platform* half is, and comprehensively — on Linux x86-64 (GitHub-hosted
runner, OpenBLAS) all eight toy states diverge on all three Pythons, with the
same values every time:

| state | key | max \|Δ\| | relative | ulps |
|---|---|---|---|---|
| `toy_lebail` | `lebail_intensity` | 2.3e-13 | 2.0e-16 | 1.0 |
| `toy_pawley` | `pawley_x0` | 1.7e-13 | 1.5e-16 | 0.8 |
| `toy_stephens` | `theta` | 1.8e-12 | 1.7e-16 | 1.0 |
| `toy_capillary` | `y_calc` | 1.9e-11 | 8.4e-15 | 41 |
| `toy_restraints` | `y_calc` | 7.5e-11 | 8.8e-15 | 41 |
| `toy_roughness` | `y_calc` | 1.2e-10 | 2.0e-14 | 128 |
| `toy_rich` | `y_calc` | 2.7e-10 | 4.6e-14 | 295 |
| `toy_anomalous` | `y_calc` | 1.0e-09 | 1.7e-13 | 1124 |

The gradient is the finding: quantities that are a single arithmetic chain
land within 1 ulp, while `y_calc` — which accumulates ~130 windows of
transcendental evaluations — drifts three orders of magnitude further.  That is
the signature of a different libm and a different summation order, not of
different code, and even the worst of it is ten orders of magnitude below the
tightest physical bar in the tree.

**And the pin is to a machine image, not to a platform tuple.**  The same WP
then ran the suite on a *hosted* macOS/arm64 runner reporting the same numpy
2.5.1, the same scipy 1.18.0 and the same Accelerate BLAS as the capture
machine — and 7 of the 8 states were bit-identical while `toy_rich:y_calc`
differed by 1.4210854715202004e-14, which is **exactly one ulp** at a value in
[64,128), on a single element.  Local runs at 1, 2, 4 and 8 BLAS threads are
bit-stable, so it is not reduction ordering; the residual variable is the
system math library that ships with the macOS image, and nothing visible from
Python distinguishes it.  Two consequences: `("darwin", "arm64")` is the right
predicate for *worth attempting* (7/8 and one ulp, against 8/8 and ~1100 ulp on
Linux) but not a promise of a match, and **no CI environment asserts these
bits** — the weekly macOS job reports the comparison and only *fails* if the
goldens skip.  That makes the gate maintainer-machine evidence, the same shape
as the Apple-GPU (MPS) gap, and it is recorded in `docs/VALIDATION.md` rather
than papered over.

So `tests/test_backend_shim.py` pins the gate to
`GOLDEN_PLATFORM = ("darwin", "arm64")` and skips elsewhere with that reason
attached, and the capture entry point refuses to write a state off that
platform (a half-and-half baseline set could never be green anywhere).
Relaxing `np.array_equal` to a tolerance was the alternative and was rejected:
it would delete the only check in the tree that says no refactor changed a
single computed number.

Re-baseline only from a tree that passes the full suite, via

    .venv/bin/python -m tests.test_backend_shim STATE [STATE ...]

naming **only** the states that genuinely changed, and say so in the commit
message.  The state names are required rather than optional on purpose: capturing
every state at once quietly rebases baselines that were meant to be fixed points,
which is the one failure mode these files cannot detect themselves.

## v1.0 indexing acceptance data (WP-1026)

### `bethanechol_indexing.json` — the only *published, scored* benchmark this package has

Bergmann, Le Bail, Shirley & Zlokazov (2004) ran eleven indexing programs over
one compound presented at six levels of difficulty, and printed both the data
(Table 6) and every program's score (Table 5).  That combination is what makes
indexing gradeable here rather than merely demonstrable: the bar is not a
tolerance somebody chose, it is what ITO, DICVOL91, TREOR90 and McMaille
actually achieved on these exact numbers.

**Ten sets, not six.**  The paper's A/B/C/D are *treatments* and each was applied
to **two** ICDD entries, so Table 6 has ten columns: `Aa Ab Ba Bb Ca Cb Da Db E F`,
where `a` = PDF 43-1748 and `b` = PDF 46-1964 (both λ = 1.5418 Å).  A is raw,
B keeps only lines with I ≥ 5 % I_max, C is A corrected for zeroshift, D is both;
E is a new laboratory measurement (λ = 1.54056 Å) and F a synchrotron one
(λ = 0.6995 Å).  Scoring is per set **per mode** — default and manual — so the
global runs over twenty numbers in ±20.  (The WP file described six sets; that
was a misreading of the table and is corrected here.)

**Two consumers, and the split is deliberate.**
`tests/test_acceptance_indexing.py` *proves the fixture* — the zeroshift
arithmetic, the I ≥ 5 % subsetting and the paper's own impurity counts, three
statements it makes in prose and never tabulates — and asserts **no score**.
`tests/bethanechol_benchmark.py` *runs the benchmark*: `python -m
tests.bethanechol_benchmark` grades the twenty runs by the paper's ±1 rule and
writes `tests/output/bethanechol_benchmark.json`.  It is a module you run rather
than a `slow` row because a full protocol is tens of minutes of pure search for a
number that moves only when an engine moves.  Both read the *same* helpers (the
runner's), so the file that is certified and the file that is graded cannot
drift apart.

**Only the printed tables are used.**  No program was run, no output parsed, and
none of the eleven programs' code was consulted — the CLAUDE.md licensing fence.
Intensities are not carried at all: the paper's table is positions only (it
points at the UPPW web site for intensities), which is exactly the input
`PeakList.from_positions` exists for, and which is why every set raises
`PEAK_SIGMA_ASSUMED`.

**The transcription is verified against three statements the paper makes but does
not tabulate**, so a typo cannot pass silently (`test_acceptance_indexing.py`):

1. **C = A − 0.100 and D = B − 0.100**, on all 80 values, to the last printed
   digit — the zeroshift correction the text describes.
2. **Every B line inside A's 2θ range is bit-identical to an A line** (13 of 13
   for `a`, 15 of 15 for `b`) — B being the I ≥ 5 % subset of the same
   measurement.  B reaches further in 2θ precisely because dropping weak lines
   from the first 26/35 lets twenty survivors extend past A's last line.
3. **The published cell reproduces the paper's own impurity counts.**  Against
   the P2₁/n cell, 3 of the 20 lines are unexplained in *every* 46-1964 set —
   the text's "3 impurity lines among the first 35" — and 7 of the first 20 in
   43-1748, consistent with "8 impurity lines among the first 26".

Reference values and what they are referenced to:

- **The cell** is `cross_code`, not a certificate: it is another study's
  published solution, adopted with its protocol (same wavelengths, same twenty
  lines, same volume/axis caps in manual mode).  The paper reports it was later
  confirmed by a full structure determination, which is why this benchmark has an
  answer at all — the other ten UPPW cases do not.
- **M(20) = 197 and F(20) = 1080 (0.0006, 32)** are quoted for set F.  This
  package's `m20`/`f_n` **floor ⟨Δ⟩ at the median σ**, and for a
  `from_positions` list that σ is the *assumed* `PEAK_ASSUMED_ESD_DEG` = 0.02°,
  which is thirty times the paper's ⟨|Δ2θ|⟩ — so the floored figures are 5.8 and
  32.3 where the paper prints 197 and 1080, and **the published figures are not
  reproducible from a bare position list, by construction**.  Unfloored, the same
  transcription gives M = 116 and F = 654 with ⟨|Δ2θ|⟩ = 0.00099° and
  N_poss = 31 against the paper's 0.0006° and 32.  The residual gap is the
  *cell's* rounding, not the data's: a, b, c are printed to 3 decimals and β to
  2, which alone moves predicted positions by ~0.001°.  The test therefore asserts
  the **unfloored** figures against the paper and records the floored ones, rather
  than pretending the package's ranking statistic is de Wolff's.

### `hl2_peaks.txt` — the fixture whose correct answer is "we do not know"

74 peaks picked by this package from `HL2-1_2.xy`, an unidentified laboratory
pattern in the `examples/` folder of **datalab-org/guillemot** (MIT).  The
pattern itself is *not* vendored; this table is our own derived product and is
carried with attribution.  It arrives here from the pinned tag
`guillemot-study` (not merged into `main`), which is the only artifact the
indexing work packages take from that study — everything else there is read in
place:

    git show guillemot-study:studies/guillemot/out/HL2-1_peaks.txt

Its value is that **the compound is unknown and stays unknown**.  An acceptance
suite made only of datasets whose answer is known measures one half of an
indexer; this measures the other, where `best_or_none()` must return `None`
rather than the best of a bad list.

### `nist_srm660c_100a.cif` read a second way — the anchor, *indexed*

No new file: `test_acceptance_indexing.py` builds this pattern through
`test_acceptance_srm660c.build_srm_inputs()` so the two suites cannot disagree
about the protocol, then throws the `Structure` away.  Three things make it the
right second known-cell dataset after SRM 676a corundum, and each is a property
of the *specimen* rather than a convenience:

* **P m -3 m has no systematic absences at all.**  That makes it the control for
  `predicted_but_absent`, the refuting caveat corundum's R-3c c-glide sets off
  (measured: 0 of 30 here against 11-12 there, and `predicted_seen_fraction`
  1.000 against 0.86).  A caveat that fired on both would not mean what its name
  says.
* **The specimen displacement is recorded in the CIF** (−0.07877 mm) and so is
  the goniometer radius (217.5 mm), so the `cos_theta` template's amplitude is
  *predicted* — +0.0415° — rather than merely fitted.  Corundum's −0.065° had to
  be measured against its own certificate first (WP-1023).
* **The cell is certified in the same file the pattern is in**, at this data
  block's own temperature (4.156780 Å at 20.85 °C — not the certificate's
  4.156826(8) Å at 22.5 °C, which is the wrong comparison here).

Its 2θ range, 20.3-150.9° in 24 stitched regions, is also what makes it
demanding: axial divergence reverses the sign of its tail at 90°, and both signs
appear in the picked list.

## v1.0 vendor pattern formats (WP-1047)

### `rigaku_*.ras` — the Rigaku text export, one real file and two synthetic

`.ras` is what a SmartLab or MiniFlex writes: self-describing ASCII, one or
more `*RAS_HEADER_START … *RAS_INT_END` scans inside a `*RAS_DATA_START`
wrapper.  Three fixtures, because the reader's three non-obvious policies each
need a file that exhibits the case.

| File | Source | Licence | What only this one proves |
|---|---|---|---|
| `rigaku_nims.ras` | `nims-mdpf/M-DaC_XRD`, `source/XRD_RIGAKU.ras` | MIT | **Real** SmartLab export: 3501 points, 25–60° at 0.01°, Cu, `TwoThetaTheta`. Its header keys are spelled the way an instrument spells them, which no synthetic file can establish. Intensities are integers to the last point, so it is also the σ story's "these are counts" arm. |
| `rigaku_multiscan.ras` | `garrekstemo/RigakuFiles.jl`, `test/data/multiscan.ras` | MIT | Two scans in one file — the `scan=` option, `PATTERN_MULTISCAN_DEFAULTED`, and `list_scans` labelling each from its own `*FILE_COMMENT`. Synthetic (3 points per scan); proves structure, not data. |
| `rigaku_three_column.ras` | `garrekstemo/RigakuFiles.jl`, `test/data/three_column.ras` | MIT | The third (attenuator) column, and `RAS_ATTENUATOR_PRESENT` firing on a column that is not identically 1. Synthetic, and its column is `0.0000` — not a physical attenuator value, which is itself the reason the reader reports rather than applies. |

**Licences were checked per *file*, and it mattered.**  `Dinghao-Wu/xrd-toolkit`
ships `tests/fixtures/cu-75sn-real.ras` — 8501 points of real integer-counts
powder data, the most attractive fixture found — and the repository has **no
LICENSE file at all**.  It is therefore not vendored here.  A repo-level grant
also does not automatically convey user-contributed instrument output, which is
why the two RigakuFiles.jl files (repo-authored, clearly synthetic) and the
NIMS file (a documented example dataset) were taken and that one was not.

**Two real files decided policy without being vendored**, and are recorded here
because the reasoning is only checkable against them:

* `josefmtd/rigaku-xrd-analysis`, `data/example.ras` (MIT) — declares
  `*MEAS_SCAN_UNIT_Y "counts"` and stores values like `84.3047`, which **no**
  scale makes integral (searched: 1/1000 to 2, and 1–200).  This is the file
  that proves the declared unit is a claim rather than a measurement, and hence
  that σ must be decided by arithmetic.  It is also an `Omega` scan — a rocking
  curve — which is the case the axis refusal exists for.
* `ttruttmann/rasloader`, `test/example_scan.ras` (MIT) — `TwoThetaOmega`,
  declares counts, 3.4 % integral.  A second, independent instance of the same
  header-disagrees-with-data case.

**The attenuator question remains open, and this is what was checked.**  Five
`.ras` files were examined for a *varying* third column, which is the only
evidence that could settle whether column 2 is already corrected for it: all
five have it constant (1.0 in four, 0.0 in the one synthetic).  Absent such a
file the reader states its contract rather than guessing — see
`io/formats/ras.py`.

### `vnb5053.dat` — the GSAS file whose bank hides behind its own step table

HIPD@LANSCE time-of-flight data from the **GSAS distribution's own examples**
(`https://subversion.xray.aps.anl.gov/EXPGUI/gsas/all/example/vnb5053.dat`,
Von Dreele).  **Not vendored, and it cannot be**: the data carries the Regents
of the University of California's affirmatively asserted copyright, and the
distribution's notice grants permission to copy "this software" while saying
nothing about the data files.  So `tests/test_readers.py::_gsas_behind_long_time_map`
packs the layout literally, and this section records what the real file
established — the only place the synthetic write-up is checkable against the
real shape.  (The facts below were read from the file directly on 2026-08-26;
the APS SVN host has since been intermittently behind a failover page.)

| Established | Evidence |
|---|---|
| A `TIME_MAP` step table is written **before** the bank it feeds | `TIME_MAP10   703   71 TIME_MAP  50 CONLOG[0.30:0.0005]` opening the file, followed by 71 records of `(10I8)` |
| A long table pushes the first `BANK` record **past the 4 kB sniff window** | first bank at byte **6068** — the sniff read only `head()`'s 4 kB, so the file was never claimed as `gsas` and fell to the `xy` catch-all |
| A real `TIME_MAP` bank writes **one coefficient** (the map number), not the CONS start/step pair | `BANK  1  7550  755 TIME_MAP   1 STD 00000000` — which is why a strict two-coefficient record regex cannot see it, and the bintype must be read off a **loose header match** before the layout parse |
| The `TIME_MAP` token itself lands **inside** the first 4 kB | it opens the table — the shape gate the bounded 64 kB escalation fires on, so a random pattern never escalates |
| What the miss cost before this round | `xy` read the 8-column fixed-format records as columns and refused with the wrong cause — "2θ does not run in one direction — 18002° → 12°" — a 2θ complaint about a file that has no 2θ axis, and only the misread column running backwards kept it from being a plausible wrong pattern |

The synthetic fixture reproduces every row of that table by construction (the
writer asserts its own bank offset exceeds `HEAD_BYTES`), shares no constant
with the parser, and all three regression tests fail against the unfixed
sniff.

### The background-peak worked example — Si SRM 640c in Kapton, and the blank that identifies it

`docs/manual/using/data.md`'s background-peak section used to rest on a 60 K
BT-1 neutron pattern of Cr₂WO₆ compared against its owner's TOPAS fit. That
example is **gone**, and this section records why and what replaced it, because
the previous version of this section named its own weakness and this is the
follow-up it asked for.

**What was wrong with it.** Two things. The TOPAS fit quoted was **unpublished**,
and so was the pattern — the material has a paper (Gaultois, Kemei, Harada &
Seshadri, *J. Appl. Phys.* **117**, 014105, 2015) but it reports the
room-temperature *synchrotron* refinement, not that 60 K neutron fit, so it was
context for the material and never the source of a number. And the fit put the
peak on top of a **7-term Chebyshev**, a background flexible enough to describe
much of the hump itself — the peak and the polynomial were entangled, which is
the hardest case to read as evidence rather than the clearest. The old section
said as much: it recorded that the strongest form of the argument "would rest on
a peak fitted in a **published** refinement, over a *simple* background so the
peak is not entangled with a flexible one," and logged finding one as follow-up.
This is that follow-up.

**What replaced it.** `11BM_Si640c.xy` — already in this directory, already the
subject of `test_acceptance_si640c.py`, already provenanced in the table at the
top of this file as an APS 11-BM *published* standards scan and a U.S.
Government work. NIST SRM 640c silicon in a **Kapton capillary**: the container
scatters, the polynomial is a 3-term Chebyshev, and the hump has nowhere to hide.
Every number in the manual's table is regenerable from a file in this repository
with the acceptance test's own protocol; **nothing is vendored for the new
example that was not already here.**

Three further files corroborate it and **none of them is committed** — they are
cited by provenance, as the `11BM_LaB6_cBN_mg2044.xye` row cites its TOPAS
references:

| Established | Evidence |
|---|---|
| The hump is the container, not a missed reflection | APS 11-BM **run 4736**, header `Chemical formula = empty Kapton capillary (Kapton)`, `Calibration file = feb10/11bmb_4733.calib`, `Calibrated wavelength = 0.412225`, collected 11 Feb 2010 — the same February 2010 beamtime as run 4918, with the sample taken out. Published on 11-BM's Standards Data listing (`wiki-ext.aps.anl.gov/ug11bm/index.php/Standards_Data`), recovered through the Internet Archive by the same route as the `qarr/*.prn` files. Fitted **outside this package** (numpy Chebyshev + scipy least-squares, weights from the file's own σ column) over the committed pattern's exact 1.997–49.996° range: Chebyshev-3 + one Gaussian gives χ²ᵣ = 1.125 on 48 000 channels, position 4.2417(111)°, FWHM 6.153(23)°, where Chebyshev-3 alone gives 5.33 and it takes fourteen polynomial terms to match the six-parameter fit. Cross-**code** and cross-**scan**, which is what the old example could not offer |
| The hump is not the beam or the air path | APS 11-BM's published `background/11BM_background_air_scatter.xy`, header `11-BM Background, No sample - Air Scatter Only`, one hour, run cycle 2009-2, λ 0.458735 Å. Binned over 2–50° it decays strictly monotonically with nothing localised anywhere. Note the **different wavelength**: a d = 4.73 Å halo would sit at 5.56° in this scan rather than 4.98°, so the control is quoted as "no localised feature anywhere", which is wavelength-free, rather than as "nothing at 5°" |
| What the feature is | The blank's envelope maximum is at 4.98° 2θ, which at 0.412225 Å is d = 4.74 Å, Q = 1.33 Å⁻¹ — the polyimide amorphous halo. Quoted as an envelope reading of the data, not as a literature value |
| Why the *refined* centre is 4.18° and not 4.98° | A symmetric Gaussian over 2–50° also absorbs the residual direct-beam rise a 3-term Chebyshev cannot reach, so it is pulled low. Measured, not asserted: give the polynomial three more terms and the same peak relaxes to 5.245(41)° and narrows from 5.57(27)° to 1.94(11)°. The manual carries this caveat in the prose and quotes the envelope for the halo and the fit for the model |

**What Cr₂WO₆ still is, and is not.** It remains cited elsewhere in this
package — in `refine.py` for esd inflation and in `strategy/staged.py` for a
stage-ordering effect — where the claim is about this code's behaviour on a
pattern rather than a physical result checked against an outside source. It is
**no longer** the background-peak worked example, and no number in that section
now comes from an unpublished fit.

### `.uxd` — the format with real evidence and no vendorable file

Bruker/Siemens DIFFRAC-AT ASCII.  **Nothing is vendored for it**, and that is
the finding rather than a gap: of the five real `.uxd` files obtained, one repo
is GPL-2.0 (`mtex-toolbox/mtex`, `data/PoleFigure/bruker.UXD`), one carries **no
LICENSE at all** (`usnistgov/texture`, `exp_uxd/fss.UXD` and `e_steel.UXD`), and
the rest are student lab-course outputs in repos with no declared licence
(`joeyko2706/FP-Protokolle`, `v44/data/*.UXD`).  A file format's *facts* may be
read from any of those — that reasoning is in `ATTRIBUTION.md` — but the bytes
may not be redistributed.  So `tests/test_readers.py::write_uxd` synthesizes
them, and this section records what the real files established, since that is
the only place the reader's design is checkable:

| Established | Evidence |
|---|---|
| The block marker is **two independent facts** — a `_2THETA` prefix meaning "a position column is present", and a `COUNTS`/`CPS` suffix meaning the unit | `_2THETACOUNTS` in four files, `_2THETACPS` in `mtex_bruker.UXD` |
| The unit the marker declares is **true**, unlike `.ras`'s free-text field | every `COUNTS` block integral to the last of 3774 points (`nist_fss.UXD`) |
| The `_2THETA` prefix is a **misnomer**: the first column is whatever `_DRIVE` names | `fp_rocking.UXD` is `_DRIVE='THETA'` — a rocking curve — under a `_2THETACOUNTS` marker |
| Most `.uxd` files in the wild are **not powder scans** | 4 of 5: two 153-range pole figures, one 68-range pole figure, one rocking curve. The one 2θ scan is a detector alignment scan (`fp_detector.UXD`, `_DRIVE='2THETA'`) |
| Counting time is **per range**, not per file — so ranges cannot be concatenated | `nist_esteel.UXD` carries `_STEPTIME` of both 2 s and 20 s across its 153 ranges: a factor of ten in counting statistics under one Poisson assumption |
| `_GONIOMETER_RADIUS` is present and real | 250, 300 and 350 mm across the five |

No obtainable `.uxd` is a powder pattern, so `_DRIVE='COUPLED'` — the value a
powder file would carry — is accepted on the **format's vocabulary** rather than
on a fixture.  That is stated in the reader and is the one part of its axis
allowlist not backed by a file.

### `panalytical_*.xrdml` — three real files, and the one that settles the attenuator

PANalytical/Malvern XRDML: the XML an Empyrean or X'Pert writes, in a
*versioned* namespace (`…/XRDMeasurement/1.6` and `/2.1` are both current in the
wild, and both appear below — which is why nothing in the reader matches on it).
All three are real vendor output; two ship an independent expected-value oracle.

| File | Source | Licence | What only this one proves |
|---|---|---|---|
| `panalytical_powder.xrdml` (+`.json`) | FAIRmat `readers-xrd`, `tests/data/XRD-918-16_10.xrdml` | Apache-2.0 | **Real** Empyrean powder scan: 5027 points, 4.007–69.999°, Cu 45 kV/40 mA, `scanAxis="Gonio"`, schema 1.6, `<intensities unit="counts">`. Integral to the last point, so it is the "raw counts, σ=None is correct" arm. The `.json` is FAIRmat's own reader output for the same file — an **independent implementation's** answer, which is what makes it an oracle rather than a transcription of ours. |
| `panalytical_attenuator.xrdml` | FAIRmat `readers-xrd`, `tests/data/m54313_om2th_10.xrdml` | Apache-2.0 | **The file that settles `beamAttenuationFactors`** (below). Real ω–2θ scan of a GaAs epilayer, 1800 points, 26.025–79.995° at 0.03°, schema 2.1, `<counts>`. Also the `2Theta-Omega` axis name and a 0.5 s counting time. |
| `panalytical_mesh.xrdml` (+`.json`) | FAIRmat `readers-xrd`, `tests/data/m82762_rc1mm_1_16dg_src_slit_phi-101_3dg_-420_mesh_long.xrdml` | Apache-2.0 | **101 scans in one file** — a reciprocal-space map — so it is the `.xrdml` arm of `scan=`, `PATTERN_MULTISCAN_DEFAULTED` and `list_scans`. The only real evidence for the third `positions` form, `listPositions` (255 explicit 2θ values per scan). Its 101 labels are identical but for the ω each scan was fixed at, which is why `list_xrdml_scans` labels from what *varies*. |

**Licences were checked per *file*, and this time they conveyed.** All three
were committed by `readers-xrd`'s own maintainers into an Apache-2.0 repository
(`9ec0c0de`, `fd8a192a`). The repo's `ikz.py` is "adapted from" the unlicensed
`carichte/IKZ`, which is why `ATTRIBUTION.md` fences that *code* — but IKZ holds
15 files and **no data at all**, so the fence does not reach these bytes.

**The attenuator question, which `.ras` could not answer, is answered here.**
A PANalytical attenuator drops a foil in front of the detector for the few
points that would saturate it. Whether the stored series is already corrected
for it is undecidable without a file where the factor *varies* — and
`panalytical_attenuator.xrdml` is one: exactly one point, at the apex of the
GaAs 004 substrate reflection, carries a factor of **188**. Its raw
neighbourhood is

| 2θ | 66.045 | 66.075 | **66.105** | 66.135 | 66.165 |
|---|---|---|---|---|---|
| stored counts | 1341 | 14602 | **1877** | 13749 | 1667 |
| × factor | 1341 | 14602 | **352876** | 13749 | 1667 |

The raw series *dips* by 87 % at exactly the attenuated point — which is the
attenuation, not a profile, since a substrate reflection cannot have a hole in
its apex. The product restores a monotone peak. So the stored counts are the
attenuated ones, `intensity = counts × factor`, and σ = √counts·factor rather
than √y. FAIRmat's reader computes the same product independently. This is the
structural test `io/formats/ras.py` describes and could not run; it is also the
case GSAS-II gets wrong, weighting 1/y regardless.

Two files were examined and **not** vendored, having established nothing the
three above do not: `EJZ060_13_004_RSM.brml` (5.1 MB) and
`Omega-2Theta_scan_high_temperature.rasx` belong to the `.brml`/`.rasx` readers,
not this one.

### `rigaku_*.rasx` — the zip container, and the premise it refuted

`.rasx` is what SmartLab Studio II writes: a zip whose `root.xml` manifest lists
one `Data<N>` group per scan, each holding a tab-separated `Profile<N>.txt` and
a `MesurementConditions<N>.xml` (the misspelling is the vendor's). Both files
below are real, both from FAIRmat's Apache-2.0 `readers-xrd`, and the pair is
chosen for the σ contrast.

| File | Source | Licence | What only this one proves |
|---|---|---|---|
| `rigaku_powder.rasx` | `readers-xrd`, `tests/data/TwoTheta_scan_powder.rasx` | Apache-2.0 | **Real powder scan**: 2726 points, 10–119° at 0.04°, `TwoTheta`, Cu, 1 deg/min. Declares `<IntensityUnit>counts</IntensityUnit>` and stores 170.55354309082 — the **refuting** arm. |
| `rigaku_zno_counts.rasx` | `readers-xrd`, `tests/data/ZnO-ALD-training_001_1_0-000_0-000.rasx` | Apache-2.0 | 7001 points, 20–90° at 0.01°, `TwoThetaTheta`. Declares counts and **is** integral to the last point — the confirming arm, so the σ test is shown deciding both ways on real files of one format. |

**This WP's premise that `.rasx` cps was "verified by fixture" is wrong, and the
fixtures are what say so.** Searched on `rigaku_powder.rasx`: no scale in
1/400…400, nor k/60, nor 60/k, nor the file's own derived counting time
(0.04° ÷ 1 deg/min × 60 = 2.4 s) makes its intensities integral.
`Omega-2Theta_scan_high_temperature.rasx` (not vendored) is the same case, so it
is two of three real files. The declaration is therefore the same free-text
claim `.ras` gets wrong — unsurprising, since the container embeds a `RASHeader`
of the very same `*MEAS_SCAN_*` keys — and both formats decide σ by
`base.sigma_by_arithmetic` instead.

**Two real files established structure without being vendored:**

* `RSM_111_sdd=350.rasx` (2.3 MB, Apache-2.0) — **401** `Data<N>` groups, each
  with its own conditions XML, in one archive: the format's multi-scan case, and
  the reason `root.xml` rather than the zip name list is read as the authority
  on order and membership. Not vendored for its size; `write_rasx` in
  `tests/test_readers.py` synthesizes the several-groups case from that
  structure.
* `Omega-2Theta_scan_high_temperature.rasx` — `TwoThetaOmega`, 44–49° at
  0.0048°, the second non-integral "counts" file above.

### `bruker_absorber.brml` — the third answer to the attenuator question

`.brml` is what DIFFRAC.MEASUREMENT writes: a zip of XML in which
`Experiment0/DataContainer.xml` lists one `RawData<N>.xml` per scan, and each
scan describes its own **columns** in `DataViews` rather than fixing them.

| File | Source | Licence | What only this one proves |
|---|---|---|---|
| `bruker_absorber.brml` | FAIRmat `readers-xrd`, `tests/data/23-012-AG_2thomegascan_long.brml` | Apache-2.0 | **Real** HRXRD 2θ–ω scan of a thin film, 2001 points, 44–48° at 0.002°, Cu, λ = 1.5406, 1 s/step. Its `AbsorptionFactor` channel **varies** (1.0 → 8.3 across 29 points), which is what settles the convention below. Also the layout that kills a fixed index: 2θ is column 2 and the intensity is column **7**. |

**Bruker's absorber is already applied to the stored intensity — the opposite of
`.xrdml`, on the same test.** Over the 29 attenuated points of the substrate
peak:

| 2θ | 45.784 | 45.786 | 45.788 | **45.790** | 45.792 |
|---|---|---|---|---|---|
| factor `a` | 1.0 | 1.0 | 1.0 | **8.3** | 8.3 |
| stored `y` | 120757 | 151306 | 182114 | **213600.5** | 243746.1 |
| `y / a` | 120757 | 151306 | 182114 | **25735** | 29367 |

`y` runs *continuously* across the transition while `y / a` steps by a factor of
seven, and — measured over all 2001 points — `y` is not integral, `y × a` is not
integral, and `y / a` **is**. So the stored series is the corrected one: nothing
is multiplied, and the only thing the factor changes is σ, which must go back
through it as √(y/a)·a. Three vendors have now given three answers to one
question (`.ras`/`.rasx` undecidable and reported, `.xrdml` applied, `.brml`
already applied), which is the argument for measuring rather than adopting a
convention.

**One real file established structure without being vendored:**
`EJZ060_13_004_RSM.brml` (5.1 MB, Apache-2.0) — **801** `RawData<N>.xml`
members, which is where the multi-scan design comes from, and two facts that are
guards in the reader. Its zip name list runs `…RawData20, RawData22, RawData21,
experimentCollection.xml, RawData23…`, so the manifest and not the name list
orders the scans. And its `RecordedRawDataView` has `Length="1280"` — each row is
a whole position-sensitive-detector frame — while its `ScanAxes` still declares
`AxisId="TwoTheta"`, so the axis check passes and **only the recorded view's own
length says the rows are not a profile**.

### `bruker_raw4_scrambled.raw` — a real header whose intensities are not real

`.raw` is DIFFRAC's binary: after a 61-byte preamble the file is a chain of
`(uint32 type, uint32 length)` segments; a type of 0 or 160 marks a **range**,
whose header ends with a nested chain of its own and is followed by `nSteps`
records of `datumSize` bytes, of which the leading float32 is the intensity.

| File | Source | Licence | What only this one proves |
|---|---|---|---|
| `bruker_raw4_scrambled.raw` | FAIRmat `readers-xrd`, `tests/data/TwoTheta_scan_scrambled.raw` | Apache-2.0 | **Real DIFFRAC.EVA header**, 7134 points, 10–85.0413° at 0.0105203°, `Locked Coupled`, LynxEye, Cu at 40 kV/40 mA, 310.003 ms/step. The only real RAW4 obtainable, and the file that shows the two other readers' bugs. Committed by that repo's own maintainer, so risk 1 is clear for it. |

**Its intensities are not the measurement, and the acceptance line for `.raw`
may therefore claim structure and metadata only.** Three measurements say so:

* the lag-1 autocorrelation of the intensity series is **0.016**, and
  `std(diff)/std(y)` is **1.403 ≈ √2** — the signature of independent values. A
  profile stepped at 0.0105° has adjacent channels on the same peak;
* **32.5 %** of the values are negative, and the exact minimum −164.5344696
  repeats **1069 times**;
* FAIRmat's own `notes/RAW_FORMAT_NOTES.md` quotes this measurement's range as
  `[-164.53, 11291.77]` and says its first ten values match a powDLL `.xrdml`
  export exactly. The **shipped** file's maximum is **11330.587**, so the file
  in the repo is not the file that was validated.

`tests/test_readers.py` pins all three, so a later session cannot read "7134
real points" off the header and write an acceptance row against noise.

**What the header does establish**, and where the two consulted readers go
wrong on it:

* `datumSize` is **8** here and the trailing four bytes of every one of the 7134
  records are `int32 == 1` — a field no description explains. GSAS-II reads
  `datumSize` and then reads `nSteps` *consecutive* float32s anyway, so it
  consumes half the block and returns alternating value / 1e-45; FAIRmat
  hard-codes the 8-byte stride as "interleaved float32 pairs". Both are right
  here and wrong on a `datumSize == 4` file, which is why the reader strides by
  the declared size and the synthesized fixtures cover 4, 8 and 12.
* **`2Theta` occurs twice** — once as a drive record and once as the scan-axis
  record — in a file with **one** range. GSAS-II counts that string to decide
  how many banks a file holds, so it reports two.
* The scanned drive is the record whose flag is non-zero **and** whose stored
  position is the range's start angle: `2Theta` at 10.0 against `Theta` at 5.0,
  where 10.0 is also `startAngle`. One file is not enough to trust the flag on
  its own, which is why both statements have to agree.
* The type-30 source segment gives Kα-mean 1.5405999, Kα1 the same, **Kα2 0.0**,
  Kβ 1.3922200 and **ratio 0.0** — mean equal to Kα1 with no Kα2, which is
  three fields agreeing that the doublet was not used. Relevant to task 15's
  anode suggestion, which resolves a zero ratio to the Kα1 preset.
* FAIRmat's notes state that tube voltage, current, counting time and the
  wavelengths are **not in the format**; all four are, at fixed offsets in the
  range header and in the type-30 segment. Their search was for ASCII strings,
  and these are IEEE floats.

**v3 (`RAW1.01`) has no fixture, from any source.** What stands in for one is
three independent descriptions that agree — GSAS-II, `bracerino/xrd-file-converter`
(MIT) and `reductus/reductus` (Unlicense, a field-by-field transcription of
Bruker's own header definition) — plus two gates a mis-parse cannot pass:
`data_record_length == 4 + 8·popcount(varying_parameters)`, which two fields
written from one fact have to satisfy, and the requirement that the declared
ranges account for the file exactly. `tests/writers_xrd.py` packs v3 from its
own literal offset table, so the writer cannot drift with the reader.
**v1 and v2 are refused**: GSAS-II describes v2 and nothing else corroborated
does, and one description with no file is how a reader comes to return a
plausible wrong pattern.

### GSAS ESD — the 8-character field, and why no file here has a bright peak

The GSAS `ESD` bank is **positional**: five (intensity, esd) pairs to an
80-column record, eight characters to a field.  Three descriptions agree, and
`src/rietx/io/formats/gsas.py` cites all three — APS 11-BM's own *Data Formats*
page ("*the intensities and their uncertainties (esd) are alternated with five
pair of numbers per line (8 characters per number), as described in the GSAS
manual*"), the manual it points at (Larson & Von Dreele 2004, LAUR 86-748), and
GSAS-II's `G2pwd_fxye.py`, whose ESD reader takes `S[i:i+8]` and `S[i+8:i+16]`
on a 16-character stride.  The reader used to split the record on whitespace
instead, which is right only while every value is at most seven characters
wide.

**Nothing is vendored for this.**  The files that establish it are APS 11-BM's
published standards patterns, recovered from the Internet Archive; no
redistribution grant was found for them.  What the beamline's pages state is
about *acknowledgement in publications* — the APS acknowledgement statement,
and the SRM-certificate page's "provided for the convenience of APS beamline
11-BM users" — and acknowledgement is not redistribution.  So
`tests/test_readers.py::write_gsas_esd` packs the layout instead, literally and
without importing anything from the parser, and this section records what the
real files established:

| Established | Evidence |
|---|---|
| Every data record is exactly 80 characters holding exactly ten non-blank fields — the format is positional, not merely usually-spaced | all six real ESD/STD banks measured, on-disk: 9 900 records each in the four 11-BM files, 660 in `mg090.Cu311.gsas`, 576 in `FAP.XRA` |
| A value that **fills** its field leaves no separating space, and the record then yields nine numbers where it holds ten | `11BM_LaB6.raw` record 1050: `… 64175.2   298.5101641.3   375.8`. 16 such records in that file, 4 in `11BM_Si640c.raw` |
| The threshold is set by the **writer's decimal convention**, not by a universal count: at 11-BM's one decimal place an intensity of 100 000 is exactly eight characters | the 68 full-width fields measured across the two files run 100 130.4, 100 547.4, 101 641.3 … 560 731.2, and the smallest is 100 130.4 — nothing below 100 000 ever fuses. `mg090.Cu311.gsas` writes the same bank with **no** decimals (`14476.`), which puts its own threshold at 10 000 000 |
| The positional read is **exact**, not merely parseable | all four 11-BM ESD banks reproduce the beamline's own `.fxye` of the identical scan channel for channel: max abs Δ2θ 1.4e-14, max abs ΔI and Δesd 0.050 — which is the half-step of the ESD container's own one-decimal rounding, so the residual is the container's, not the parser's |
| A sibling file is **not** evidence for this: the same bug is invisible on a dim pattern | `11BM_Kapton.raw` (brightest channel 718.7) and `11BM_background_air_scatter.gsa` (49.4) parse identically either way, and so do the two committed banks, `mg090.Cu311.gsas` (14 476) and `FAP.XRA` (19 693). Zero full-width fields in any of the four |
| Records are padded with **explicit zeros**, never with blanks, so a blank field is only ever a short final record | zero interior blank fields across all six banks; every real bank's tail reads `0.0` pairs |

Two things the same corpus establishes about the *other* flavours, and both are
reasons **not** to widen the change:

* `FXYE` is genuinely free-format — the committed `mg090.fxye` writes tokens 9
  and 10 characters wide on records of 31 to 34 characters, so 8-character
  slicing would destroy it.  Whitespace splitting is the correct read there and
  is left alone.
* `STD`'s 8-character field is a 2-character repeat count plus a 6-character
  value, so a value can never reach the field's left edge and fusion is
  **structurally impossible** in a bank GSAS could have written.  `FAP.XRA`
  confirms the uncompressed shape (every count subfield blank, values
  right-justified in the low six characters).  The *compressed* variant — a
  non-blank repeat count — is a question no obtainable file answers, and it is
  not guessed at.

## v1.0 project readers (WP-1118)

### TOPAS `.inp` — the archive with no vendorable file

`io/projects/topas.py` reads a Bruker TOPAS refinement *input*, not a pattern:
the solved model — phases, sites, cell, instrument and the converged `r_wp` — so
it is the cheapest source of a *validated* reference to test against. It was
written and settled against a **private archive of 606 solved refinements** (the
author's own research inputs, `catalogue/inp_files.txt`). **Nothing is
vendored**, and that is the finding rather than a gap: the files are working
research inputs under no uniform, redistributable licence — a format's *facts*
may be read from them (that reasoning is in `ATTRIBUTION.md`), the bytes may not
be shipped. `tests/test_projects_topas.py` synthesizes every fixture inline, and
this section records what the real files established, since that is then the only
place the reader's design is checkable.

Reader outcome over the 606-file catalogue (`read_topas_inp` then
`projects.topas.to_structure`,
measured 2026-08-27): **516 parse, 367 build a `Structure`**, and **7 refuse at
the encoding gate** (an ASCII-range UTF-16 export whose NUL bytes survive the
decode — guessing the byte order is a repair the reader will not make in
silence). The gap between 516 and 367 is not error: it is Pawley/indexing-only
inputs with no structural phase, `STR(...)`-macro phases the reader refuses by
name, magnetic space groups it has no model for, and the stated-but-unreadable
refusals below — every one a *report or refuse*, none a silent drop.

The count *fell* from the 572/389 measured on 2026-08-26, and the fall is the
point: resolving the pre-processor correctly stopped 62 files reading whose
`for xdds { for strs … }` loops move where a card attaches, and reading the
live branch of a nested conditional stopped others reading a dead one. Reading
the coupled-edge `Get()` case then moved 4 files back the other way. The
weight-percent oracle is what says the fall was for the right reason: it lost
exactly the eight rows the transfer had been getting wrong by more than 1 wt%.

| Established | Evidence (files in the archive) |
|---|---|
| A `str` block ends at the **next block opener of any kind**, not at the next `str` — otherwise a phase absorbs the neighbour's cell, `scale` and `weight_percent` | `simulate_Nb_Cu.inp`: a nameless `str` block used to arrive named `"CaO"` with `scale 1.0`, both read off the `hkl_Is` block below it |
| Which cell macros a real file actually **uses**, and with what spellings of the value in the argument. The *coupling* each one states is a specification fact and is cited per macro in `ATTRIBUTION.md`; the archive's job here is incidence, and it is the reason `Trigonal` is implemented at all | live-text incidence over the 618 swept files: `Hexagonal` **15**, `Cubic` **13**, `Trigonal` **4**, `Tetragonal` **1**, `Rhombohedral` **0**. Read off `Cubic(@ 4.15692`)` (`LaB6_Riet_TCHZ_01.inp`), `Tetragonal(@ 4.594290`, @ 2.958587`)` (`d5_05005_pawley_01.inp`), `Hexagonal(@ 3.613074`, @ 12.037126`)` (`BL104_B_1.inp`), `Trigonal( 12.695126, 37.972985)` (`AT027-23…mythen_summed_rf_fin`). `Cubic` also appears with an equation for its argument — `Cubic(=SFOx_cub;)` (5 SFO files), `Cubic(=a1;: 5.431500)` (the `Si_in_cap_NOMAD` series) |
| `Rhombohedral`'s argument order is settled by the reference and **not** by this archive, which is why it is worth writing down that the archive is silent on it | **0 files** in live text; **2** carry it inside a `'` comment (`D20.inp`'s template, `'Rhombohedral(@ #, @ #)`). `Orthorhombic`/`Monoclinic`/`Triclinic` occur in **0 files**, commented or not, and are not cell macros of this format — they stay refused by name |
| A **multi-`occ` single site** (one `site` token, several species/occupancies on one line) does **not** occur in this archive — the mixed-occupancy case is spelled two-line instead (`site Si1_Si … occ Si 0.8` / `site Si1_Ge … occ Ge 0.2` sharing coordinates), which already worked | 0 files with two `occ` on one `site` line; the one-grammar occ reader is latent cover, not a live fix here |
| The anisotropic displacement tensor appears in **three spellings**, the third being a positional six-slot `ADPs { … }` brace block | `adps`/`ADPs`: **6 files** (`Gd12Co5Bi`, `Gd12Co5Bi_refine_peakshape`, `SXC223C_seed_01`, `lasf_longruns_riet_07`, `zrwneut_sh_riet_01`, `107_P63_Pawley_11BM`); a live `u11` token: **1 file** (`zrwneut_sh_riet_01`, the ZrW₂O₈ neutron fit the brace spelling was read from) |
| The tensor's **unit convention** — `u_ij` read as U^ij in Å², the CIF `_atom_site_aniso_U_ij` convention, so the numbers transfer with no 8π² conversion (`_ADP_KEYS`) | **Not measured against TOPAS's own output**, which is what § What generalises to the next foreign format asks for *first*, and which needs a run this tree cannot make. What stands behind it is the field names plus one magnitude argument (`test_a_stated_adp_tensor_is_carried_on_the_model`): at U = 0.013 the isotropic equivalent is B = 8π²·0.013 = 1.03, an ordinary B, where reading the same number *as* B would put the site at U = 0.00016. That separates U from B; on its own it does not exclude a differently normalised U. Worth settling by whoever holds the archive, and cheap to — `zrwneut_sh_riet_01` is a published ZrW₂O₈ neutron refinement whose tensor can be read against the literature directly. A wrong answer here would be **silent**: `ADP_NOT_POSITIVE_DEFINITE` cannot catch it, since scaling a positive-definite tensor by a constant leaves it positive-definite |
| An edge coupled to another edge (`b`, `c` set from `a`, the tetragonal/cubic case) **does occur**, written with TOPAS's `Get()` built-in, and is **read** — resolved against the cell keys already read for the same phase, with the file's symbol table as the outer scope. It used to refuse, costing the whole file each time | `b =Get(a);` / `c =Get(a);` in **4 files** in live text (`140401_PbPdO2_11bm_BN`, `LL002_PbPdO2_Li01_afterTC`, `Li01_PdO_AfterZEM`, `PdO_AfterZEM`), all four of which now read *and* build. A **fifth** (`GLP2C001.inp`) writes the same line inside an `#ifdef phase_2_` the pre-processor kills, so a raw grep says 5 and the live text says 4 — which is the conditional resolver being load-bearing rather than a discrepancy. The bare `b = a;` form occurs in **0 files** |
| The **other** coupled-edge idiom — two edges naming one declared parameter (`prm edge @ 5.0` with `a = edge; b = edge;`) — is read the same way and reported the same way, and the parameter's refine flag is carried onto every edge that resolves through it. Reading only the number made a refined cell arrive held, so a file that refined its cell and one that declared a constant built byte-identical models | **Not measured on the archive**, which is not on this tree: the construct is derived from Technical Reference 2.2 (`prm b1 0.2` declares a parameter that will be refined, `prm !b1 0.2` the held form) rather than from an incidence count, and the rows above are what an incidence count would look like. Worth measuring by whoever holds the archive — the `Get()` row's shape is the shape that answer should take |
| The cells that coupling recovers are checkable against the phases themselves, which is the corroboration the citation cannot give | cBN in `140401_PbPdO2_11bm_BN` reads a = b = c = **3.6151 Å** (`F-43m`, literature 3.615) and PdO in `PdO_AfterZEM` reads a = b = **3.0424**, c = **5.3356** (`P42/mmc`, literature 3.043/5.336). A coupled edge takes **no** refine flag of its own — it states an equation, so only the edge it names is refined |
| The **scale convention transfers unchanged** — TOPAS's `scale`/`weight_percent` carried into rietx's Hill & Howard reproduces the file's own quantitative phase analysis, with no systematic 8π²-class factor hiding in it | The weight-percent oracle: of 174 files stating `weight_percent` over ≥2 built phases, the **139 whose stated values sum to 100 ± 2** (i.e. can be one refinement's answer) give a median per-file max \|ΔW\| of **0.0004 wt%** |

The oracle's own limit is recorded with it: three files above 1 wt% are
hand-edited mid-refinement (`CR_BN.inp`, ±10.3 — stale `scale` values that
happen to still sum to 100), and 35 files whose stated sums are 497–656 % are
multi-dataset templates and stale batch files, excluded because their numbers
are not from one converged state. Both classes are named in the round-five sweep
JSON, not hidden in the median.

### FullProf `.pcr` — six real files, none of them vendorable

`io/projects/fullprof.py` reads a FullProf refinement *control* file, the same
kind of source as the `.inp` above: the solved model rather than a pattern. It
was written and settled against **six real `.pcr` files** in the same private
archive, and **none is vendored**, for the same reason and under the same
`ATTRIBUTION.md` reasoning — they are a collaborator's and an owner's working
research inputs under no uniform, redistributable licence. A format's *facts*
may be read from them; the bytes may not be shipped.
`tests/test_projects_fullprof.py` synthesizes every fixture inline. This section
is therefore the only place the real-file evidence is checkable, which is what
`io/CLAUDE.md` § Adding a format, step 1 requires of a format with no vendorable
file.

The six, and what each settled:

| file | what it established |
|---|---|
| `crwo6002_momcomp.pcr` | The **line grammar**, read off `:4`/`:5` (nineteen fields) and `:7`/`:8`. Also the `ATZ = 963.5` that forced `_PHASE_INTEGER_FIELDS` — `cur.ints()` over the whole phase-control line would refuse every real file, because `ATZ` and `Pr3` are quantities, not counts. And a **stale λ in the refinable-λ slot** |
| `crwo6002_momcomp_softconstrained.pcr` | The soft-moment constraint block (`SoftMomentConstraint`), and that a magnetic phase present alongside nuclear ones must **refuse** rather than return the nuclear subset silently |
| `crwo6002_BV2andBV4.pcr` | The two **single-atom coordinate ties** that must *not* refuse: O1's x to its y (parameter 56) and O2's (parameter 57), on `P 42/m n m`'s 4f site, which rietx's own `dof.0` already reproduces. This is the file that makes the tie check re-derive a site's DOF count instead of refusing every shared codeword |
| `crwo6002_G5_nc.pcr` | A second magnetic layout (two magnetic sites), and the **lying phase-number comments** — a `.pcr`'s inline `!Phase No.` text disagrees with the block order, so the reader counts blocks and never trusts the comment |
| `300q-1p5K_1.pcr` | `Aut 1`; the `Jbt` header rename; O1's **negative `Biso` = −0.67266 Å²**, a real FullProf outcome that rietx's zero bound cannot clamp without changing every high-Q intensity, hence a refusal rather than a repair; and the cubic **`a = b = c`** cell tie (parameter 40) plus the `F D -3 M` → `F d -3 m:2` origin choice |
| `yag_xpress_072_new.pcr` | The **`NPATT 6` refusal**. A joint refinement over six patterns is a different layout throughout, and which bank's resolution function to return is a question the file does not answer. This is the only one of the six that does not read |

Two limits of this corpus are recorded rather than smoothed over, because both
shaped the code:

- **It contains no cross-atom tie at all.** Every shared-number group in all six
  files is a *single-atom* coordinate tie, i.e. one rietx carries. So the corpus
  reaches neither arm of the report-versus-refuse split that
  `atom_tie_recoverability` draws, and a rule inferred from it would have been an
  accident. That is why the split is derived from whether the restoring
  `Refinement.tie_equal` call can be written unambiguously, and tested on
  synthesized files, rather than from what these six happen to contain.
- **Its cell ties are tetragonal and cubic only** — parameter 5 (`a = b`) and
  parameter 40 (`a = b = c`) — so the space group masks the defect in every case
  the archive can reach. The same codewords under an orthorhombic or triclinic
  symbol are *not* reproduced, which is why `cell_parameter_ties` asks
  `crystallography.symmetry.cell_constraints` rather than trusting the corpus.
  Exactly the limit `TOPAS_CELL_COUPLING_DROPPED` hit one reader over, whose four
  coupled files were tetragonal and cubic for the same reason.

## v1.3 PowderLine recipe fixtures (WP-1306)

`powderline/` holds two complete **cross-engine** refinement fixtures vendored
verbatim from [NSLS2/PowderLine](https://github.com/NSLS2/PowderLine) at commit
`e9aba0c8f8da314e64e85025fc4b9ef8ebfd16ea` (2026-08-27), BSD-3-Clause,
copyright 2026 Daniel Olds.  The upstream directory names are kept (`LaB6/`,
`DRX_33/`, each with `output/` for GSAS-II and `output/topas/` for TOPAS) so a
later session can diff the tree against a fresh clone; `powderline/LICENSE` is
the copy the BSD-3 redistribution clause requires.  **Nothing here enters the
wheel** — the recipe reader is `src/rietx/io/recipe.py`, its fixtures are test
data only.

What makes these worth vendoring is not the interchange format.  It is that
each is one pattern refined by **two independent engines** whose outputs are
both committed, which is the `FAP.EXP` cross-code check with a second opinion
attached — and the two opinions turn out to disagree.

| File (upstream path under the repo root) | Bytes | sha256 (first 16) |
|---|---|---|
| `LICENSE` | 1 498 | `db8057805ceeebdb` |
| `examples/example_LaB6/DESCRIPTION.md` | 3 334 | `615fa0ba50cf6eca` |
| `examples/example_LaB6/input.json` | 455 017 | `bb19011a62f48b09` |
| `examples/example_LaB6/output/refined_parameters.csv` | 1 482 | `605d14d734f45f94` |
| `examples/example_LaB6/output/LaB6_unit_cell_report.csv` | 243 | `2556a5f5bb765f1b` |
| `examples/example_LaB6/output/LaB6_peak_list_report.csv` | 8 511 | `3127394b0f2ce995` |
| `examples/example_LaB6/output/fit_profile.txt` | 377 143 | `f136702695fff8f9` |
| `examples/example_LaB6/output/topas/refined_parameters.csv` | 1 427 | `1d3ad5e1dcf21e55` |
| `examples/example_LaB6/output/topas/LaB6_unit_cell_report.csv` | 142 | `a69c9d16986577ac` |
| `examples/example_LaB6/output/topas/LaB6_peak_list_report.csv` | 6 038 | `4050a4d23310ea9c` |
| `examples/example_DRX_33/DESCRIPTION.md` | 4 765 | `da229bd6d629a5ed` |
| `examples/example_DRX_33/input.json` | 421 522 | `2b808bb74cf6ef9e` |
| `examples/example_DRX_33/output/refined_parameters.csv` | 1 969 | `d1757260b774c5fb` |
| `examples/example_DRX_33/output/DRX_33_unit_cell_report.csv` | 243 | `21bec7db090ae510` |
| `examples/example_DRX_33/output/DRX_33_peak_list_report.csv` | 2 879 | `6d76d62db5c04193` |
| `examples/example_DRX_33/output/Li4MgWO6_SG12_unit_cell_report.csv` | 245 | `22f4a29da53cb03e` |
| `examples/example_DRX_33/output/Li4MgWO6_SG12_peak_list_report.csv` | 77 577 | `4a2093fd137a06d8` |
| `examples/example_DRX_33/output/fit_profile.txt` | 378 300 | `2eeaea5df455d592` |
| `examples/example_DRX_33/output/topas/refined_parameters.csv` | 1 790 | `06699c08ec83b997` |
| `examples/example_DRX_33/output/topas/DRX_33_unit_cell_report.csv` | 191 | `fe3b27762c9b8663` |
| `examples/example_DRX_33/output/topas/DRX_33_peak_list_report.csv` | 2 316 | `8799263e2c22db90` |
| `examples/example_DRX_33/output/topas/Li4MgWO6_SG12_unit_cell_report.csv` | 211 | `fe89864c4e136a33` |
| `examples/example_DRX_33/output/topas/Li4MgWO6_SG12_peak_list_report.csv` | 67 254 | `4650b77698fc33fd` |
| `examples/example_LaB6/output/dummy.lst` | 8 600 | `9b4c78339987a4f0` |
| `examples/example_LaB6/output/topas/example_LaB6_results.csv` | 977 | `ce942d214fb25b2f` |
| `examples/example_DRX_33/output/dummy.lst` | 17 234 | `cb22ad84b11a6fae` |
| `examples/example_DRX_33/output/topas/example_DRX_33_results.csv` | 1 607 | `8b8d6b3fefb9e1a5` |

The last four carry each engine's own Rwp — GSAS-II's in its `.lst` log
(`Final refinement wR = 6.53%`), TOPAS's in its results CSV (`r_wp`) — so the
acceptance test **reads** the reference figure instead of quoting a number
typed into a docstring, which is the same rule the manual's injected constants
follow.

Every file is pure LF, asserted at vendoring time.  The **TOPAS** `fit_profile.txt`
of each example is deliberately *not* vendored: it is 340 kB per example and
carries the same header contract as the GSAS-II one on a different x grid
(TOPAS writes only the fitted range, 3 769 rows from 1.000356°; GSAS-II writes
all 4 096 channels with zeros outside it).  Its upstream paths are
`examples/example_*/output/topas/fit_profile.txt`.

### What the data is

Both patterns are NSLS-II beamline 28-ID-1 (PDF), λ = 0.1665 Å, 4 096 channels
over 0.647–15.867 °2θ, with `fit_range` [1, 15] leaving **3 768 fitted
channels** — the number both engines report their residual on.  The recipes are
*file-less*: `payload.xrd_data` carries `tth`, `Itth` and `Itth_weights`
(= 1/σ²) inline, which is why an `input.json` is 0.4 MB.

* **LaB6** — NIST SRM 660c, `P m -3 m`, a = 4.15682 Å **held**.  Refines the
  phase scale, six Chebyshev terms, one background peak and the six instrument
  broadening terms U V W X Y Z.  It is an instrument-profile calibration, so
  the cell is a fixed input rather than an answer.
* **DRX_33** — a disordered-rocksalt battery cathode: `F m -3 m` DRX plus
  monoclinic `C2/m` Li₄MgWO₆.  Refines both phases' scales, cells, isotropic
  size and strain with their `LG_eta` mixing terms, and six Chebyshev terms;
  instrument and atoms held.  Data from
  [doi:10.26434/chemrxiv.15003271/v1](https://doi.org/10.26434/chemrxiv.15003271/v1)
  — **cite that work when using this pattern**.

### The two reference engines disagree, and by how much

This is the reason the acceptance bar for `test_acceptance_powderline.py` is an
*envelope* rather than a tolerance against either engine.  Measured off the
committed `*_unit_cell_report.csv` files:

| Phase | Parameter | GSAS-II | TOPAS | Δ |
|---|---|---|---|---|
| DRX_33 | a (Å) | 4.171 525 | 4.182 656 | **+2 665 ppm** |
| Li₄MgWO₆ | a (Å) | 5.124 071 | 5.133 141 | +1 770 ppm |
| Li₄MgWO₆ | b (Å) | 8.791 228 | 8.787 832 | −386 ppm |
| Li₄MgWO₆ | c (Å) | 5.097 912 | 5.104 563 | +1 304 ppm |
| Li₄MgWO₆ | β (°) | 110.708 935 | 110.821 300 | +1 015 ppm |

So no answer can be within the WP's original ±300 ppm of *both*: the two
engines are 9× that apart on the cubic phase alone.  Their own
`docs/regression-tolerance.md` does not contradict this — its `rtol 1e-4` on a
cell is a **cross-build** tolerance (same engine, different OS), measured at
~2e-7 drift, and it says in as many words to "compare lattice parameters, not
Rwp, across engines".

The disagreement is not mysterious, and upstream documents its cause.
`example_DRX_33/DESCRIPTION.md` records that GSAS-II reports **2 soft (SVD)
Hessian singularities** on `0:0:Size;mx` and `1:0:Size;i`, with
`Mustrain;mx`/`Mustrain;i` correlated at 100 % in *both* phases.  The two
engines land in different minima of that flat valley, and their broadening
answers say so plainly:

| | GSAS-II | TOPAS |
|---|---|---|
| DRX_33 size | `Size;i` 253.2 µm, `Size;mx` 1.51e4 ± 7.4e3 | 4.92e6 µm (i.e. none), η = 0.0781 |
| DRX_33 strain | `Mustrain;i` 145.9, `;mx` 137.8 | 16 737 ± 587, η = 0.296 |
| Li₄MgWO₆ size | `Size;i` **−1 364.6** µm (unphysical) | 5.05e8 µm (none), η = 0.0156 |
| Rwp | 10.83 % | 7.33 % |

For **LaB6** the same holds one rank smaller: GSAS-II's background peak ran off
to position 8.77e10 °2θ with intensity −2.79e8 and **esd 0** — an unmeasured
direction that contributes exactly nothing over 1–15° — while TOPAS placed a
real hump at 1.628° with a 12.3° Gaussian FWHM.  GSAS-II's `Y` is −15.81
centideg against TOPAS's −8.97.  Rwp 6.53 % against 8.52 %.

Read as: **the cells are the comparable quantity and even they carry a 2 665 ppm
cross-code spread on this specimen; the broadening terms are not comparable at
all.**

### The convention table, and how each row was established

`src/rietx/io/recipe.py` carries the conversions.  Every row below marked
*measured* was checked against the committed LaB6 GSAS-II output before the
reader was written — the peak list's own `sigma_squared`/`gamma` columns and the
drawn width of `y_calc − y_bkg` in `fit_profile.txt`:

| Recipe field | Unit | rietx target | How established |
|---|---|---|---|
| `U`, `V`, `W` | centideg² Gaussian **variance** | `profile.u/v/w` × 8ln2·1e-4 | *Measured*: `sigma_squared` reproduces `U tan²θ + V tanθ + W` to 6 dp on all 49 reflections, and the drawn FWHM of their own `y_calc` matches √(8ln2)·√sig/100 to 0.1–0.9 % (the residue is the SH/L asymmetry, not modelled in the check) |
| `X`, `Y` | centideg Lorentzian **FWHM** | `profile.x/y` × 0.01 | *Measured*, same route |
| `isotropic_size` | µm | `lor_size` = 0.018·η·λ/(π·D); `gauss_size` = [0.018·(1−η)·λ/(π·D)]² | *Measured*: the peak list's `gamma` exceeds the instrument-only X/cosθ + Y·tanθ + Z by exactly 1.8λ/(π·D·cosθ) + 0.018·µ·tanθ/π centideg at GSAS-II's defaults D = 1 µm, µ = 1000 |
| `isotropic_strain` | 1e-6 Δd/d | `lor_strain` = 1.8e-4·η·µ/π; `gauss_strain` = [1.8e-4·(1−η)·µ/π]² | *Measured*, same route |
| `LG_eta` | — | the Lorentzian **share**; (1−η) goes to the Gaussian | Upstream's own second engine (`src/powderline/topas/conversions.py`) splits it this way |
| `Lam` | Å | `source.lines[0].wavelength` | Direct |
| `Polariz.` | — | `source.polarization` | Direct |
| `SH/L` | (S+H)/L | `axial_sl` = `axial_hl` = SH/L / 2 | **Adopted, not measured** — at SH/L = 5e-4 on 0.027° peaks the split is below what this pattern can show (see `test_recipe.py`) |
| `Zero` | ✗ | — | **Refused when non-zero.** Upstream states the unit twice and disagrees with itself: `easydiff/conversions.py` says centidegrees, `config_loader.py` says "degrees 2theta". Every committed recipe has `Zero = 0`, where the readings coincide |
| `Z` | centideg constant Lorentzian | — | Dropped when fixed at 0 (`RECIPE_FIELD_DROPPED`), refused otherwise: rietx's Lorentzian has no constant term |
| `Itth_weights` | 1/σ² | `PatternData.sigma` = 1/√w | Confirmed against `easydiff/conversions.py:crop_and_sigma` |
| `fit_range` | °2θ, **inclusive** both ends | `two_theta_limits` | Same source |
| `Uiso` | Å² | `biso` = 8π²·Uiso | Direct |
| Chebyshev coefficients | GSAS-II domain | count and `refine_flag` carried; **coefficients re-seeded** | The two codes scale the Chebyshev domain differently; carrying the numbers would be a wrong start dressed as a right one |
