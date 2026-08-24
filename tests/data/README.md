# Test data provenance

| File | Contents | Source | License/status |
|---|---|---|---|
| `11BM_NAC.fxye` | Na2Ca3Al2F14 (NAC) powder pattern, APS beamline 11-BM, λ = 0.4139090 Å (from the accompanying `.prm`), 54000 points, GSAS ESD (fxye) format | GSAS-II tutorials repo, `TOF-CW Joint Refinement/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_gsas.prm` | GSAS instrument parameter file for the above (profile from SRM 660a LaB6 fit) | same | same |
| `11BM_LaB6_660a.fxye` | NIST SRM 660a LaB6 powder pattern, APS beamline 11-BM, λ = 0.4131280 Å (from the accompanying `.prm`), 132992 points, 0.4995-66.995° 2θ at 0.0005°, 295.0 K, GSAS ESD (fxye) format — the **capillary** specimen of the v0.5 absorption acceptance (`test_acceptance_capillary.py`). Its own header identifies it: `sample_name, "SRM 660a"` / `chemical_formula, "Lanthanum Hexaboride (LaB6)"` / `comment1, "robotic collection"` | GSAS-II tutorials repo, `FitPeaks/data/11bmb_3844.fxye` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_lab6_gsas.prm` | GSAS instrument parameter file for the above (λ = 0.4131280 Å, POLA 0.99, profile from the same Feb-2009 SRM 660a fit as `11bm_gsas.prm`) | same, `11bmb_3844.prm` | same |
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

**Reference values, published.** Gaultois *et al.*, *J. Phys.: Condens. Matter*
(2013), ms. CM/461205 — the combined refinement of these two histograms:

| quantity | published |
|---|---|
| a (Å) | 10.342312(8) |
| x(O 48f) | 0.33012(7) |
| data points | 51 295 |
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
a = 10.342904(60) Å, **+57 ppm** above the published value: the published
refinement carries 0.5(1) mol % RuO₂ alongside and models the λ/2 second-order
contribution, and rietx does neither. x(O 48f) 0.32994(51) is inside its own esd
of the published 0.33012(7).

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
