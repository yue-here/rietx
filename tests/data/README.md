# Test data provenance

Every file below is committed. Data a measurement may read but the tree may
not hold, such as a public download with no licence to redistribute, lives
outside the checkout in `~/rietx-local-data`. `tests/local_data.py` registers
each such file by URL and sha256, fetches it, and says where it is; its
docstring holds the rules.

| File | Contents | Source | License/status |
|---|---|---|---|
| `11BM_NAC.fxye` | Na2Ca3Al2F14 (NAC) powder pattern, APS beamline 11-BM, λ = 0.4139090 Å (from the accompanying `.prm`), 54000 points, GSAS ESD (fxye) format | GSAS-II tutorials repo, `TOF-CW Joint Refinement/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_gsas.prm` | GSAS instrument parameter file for the above (profile from SRM 660a LaB6 fit) | same | same |
| `11BM_Si640c.xy` | NIST SRM 640c silicon powder pattern, APS beamline 11-BM run 4918 (25 Feb 2010), λ seeded at the header's stated 0.412359 Å, 48000 points, 1.996–49.995° 2θ at 0.001°, three columns (2θ, I, propagated σ). Header: `Sample name = Silicon (Si) NIST SRM 640c, certified cell length of 5.4311946 Angstroms` / `Run no. = 4918` / `Calibration file = feb10/11bmb_4917.calib` / `Calibrated wavelength = 0.412359`. The single-histogram refinable-wavelength anchor (`test_acceptance_si640c.py`) — see the section below | APS 11-BM's **published** standard-reference scan of NIST SRM 640c (run 4918, Feb 2010): a facility calibration measurement, not a user sample (its header carries no proposal, user or contact field, unlike this directory's mail-in patterns). Published on 11-BM's Standards Data listing, `wiki-ext.aps.anl.gov/ug11bm/index.php/Standards_Data`; the live download links have since gone dead in a site migration, so the published container was recovered via the Internet Archive (as with the `qarr/*.prn` files below). The committed `.xy` is **verified bit-identical** to the beamline's published `11BM_Si640c` container across all 48 000 retained channels — 2θ, intensity **and** propagated esd exactly equal, `np.array_equal` on all three — with only the first 1 496 low-angle channels (0.500–1.995° 2θ) trimmed off and the comment markers reformatted (`!`→`##`) | Argonne/APS standard-reference scan (U.S. Government work; publicly distributed) — a citable public route, not a private grant |
| `11BM_Kapton.xy` | The **empty Kapton capillary**, APS beamline 11-BM run 4736 (11 Feb 2010), λ 0.412225 Å, 49 497 points, 0.500–49.996° 2θ at 0.001°, three columns (2θ, I, propagated σ). The row above with the specimen taken out: same February 2010 beamtime, same container, and the only file here whose contents are a background rather than a pattern. Header: `Chemical formula = empty Kapton capillary (Kapton)` / `Run no. = 4736` / `Calibration file = feb10/11bmb_4733.calib` / `Calibrated wavelength = 0.412225`. The measured-background fixture (`test_acceptance_si640c.py`'s blank arms, WP-1309) and the file behind the hump identification in `docs/docs/concepts/parameters.md` § Humps — see the section below | APS 11-BM's **published** standard-reference scan, the same Standards Data listing (`wiki-ext.aps.anl.gov/ug11bm/index.php/Standards_Data`) and the same dead-link-and-Internet-Archive route as `11BM_Si640c.xy` above. Supplied by the maintainer on 2026-09-17 and committed byte-for-byte as received. **Verified to be run 4736** rather than taken on the filename: the header fields above are the ones this file's own out-of-package fit was recorded from on 2026-08-26 (section below), and rerunning that fit on the committed bytes reproduces every number it recorded — χ²ᵣ 1.1251 against 1.125, position 4.2416(111)° against 4.2417(111)°, FWHM 6.1529(228)° against 6.153(23)°, the peak-free Chebyshev-3's 5.3255 against 5.33, and fourteen polynomial terms to match the six-parameter fit | Argonne/APS standard-reference scan (U.S. Government work; publicly distributed) — the same citable public route as `11BM_Si640c.xy`, and a facility calibration measurement rather than a user sample (its header carries no proposal, user or contact field) |
| `11BM_LaB6_660a.fxye` | NIST SRM 660a LaB6 powder pattern, APS beamline 11-BM, λ = 0.4131280 Å (from the accompanying `.prm`), 132992 points, 0.4995-66.995° 2θ at 0.0005°, 295.0 K, GSAS ESD (fxye) format — the **capillary** specimen of the v0.5 absorption acceptance (`test_acceptance_capillary.py`). Its own header identifies it: `sample_name, "SRM 660a"` / `chemical_formula, "Lanthanum Hexaboride (LaB6)"` / `comment1, "robotic collection"` | GSAS-II tutorials repo, `FitPeaks/data/11bmb_3844.fxye` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `11bm_lab6_gsas.prm` | GSAS instrument parameter file for the above (λ = 0.4131280 Å, POLA 0.99, profile from the same Feb-2009 SRM 660a fit as `11bm_gsas.prm`) | same, `11bmb_3844.prm` | same |
| `11BM_LaB6_cBN_mg2044.xye` | NIST **SRM 660b LaB₆** + cubic BN two-phase mixture, APS beamline 11-BM, λ = 0.413680 Å (`.prm` ICONS; POLA 0.990), 49 496 points, 0.5–49.99° 2θ at 0.001°, three-column `xye` with **propagated esds** (twelve analyser crystals summed, so column 3 is not √I). From the file header: run **3095**, scanned **17 Feb 2014**, proposal **31405**, user sample name **mg2044**, **295.0 K**, 0.1 s/step, goniometer radius 1000 mm, robotic mail-in collection. (The header's e-mail and sample-barcode fields are redacted in the committed copy — personal contact detail and facility bookkeeping; every data channel is byte-identical to the original.) **No weighed composition is recorded** — the header gives only "Boron Nitride and lanthanum hexaboride" — so every claim referenced to this file is cross-code against two solved TOPAS refinements of it (`lab6_pvii_absorb_cs_mustr` → LaB₆ 17.950 wt %, cBN a = 3.616463 Å; `lab6_pvii_absorb_IB-size-strain` → 17.907 wt %, a = 3.616466 Å; `simulation_quant.txt` → 17.90681). **Those TOPAS `.inp`/`.out`/`.txt` reference files are not committed — they live on the data owner's archive, not in this directory**: the protocol is transcribed into `test_acceptance_lab6_cbn.py`'s docstring and the values recorded in `tests/validation_matrix.py`, but the source files are not in this repo. Two-phase QPA and identifiability acceptance (`test_acceptance_lab6_cbn.py`) | Collected at APS 11-BM under proposal 31405 (M. W. Gaultois, then UC Santa Barbara); robotic mail-in collection, run 3095 | Contributed by the data owner, M. W. Gaultois, for redistribution with this package under the repository's terms. Not a beamline standard scan and not publicly distributed by APS — unlike `11BM_Si640c.xy`, whose row cites a public route; measured Pearson r = 0.499 against the beamline's published single-phase SRM 660b, i.e. a different specimen (a two-phase 660b + cBN mixture) |
| `srm1976a_corundum_xpert.xy` | NIST **SRM 1976a** sintered corundum (α-Al₂O₃) **plate**, flat and genuinely textured, on a Philips/PANalytical X'Pert with an X'Celerator, Cu Kα (Kα2/Kα1 0.5 in the header), Ni filter, no monochromator, 45 kV / 40 mA, scanned **8 Oct 2013**, 5.504–118.531° 2θ at 0.00836° (13 528 points), 10.16 s per step, two columns (2θ, counts; Poisson weights). Optics: 240 mm radius, 1° divergence slit, 2° anti-scatter slit, 0.04 rad Soller slits both sides, X'Celerator active length 2.122°, 6° take-off. sha256 `202a5fd119c1482d03b2a08092a1f922611b5d3898f291c1b2c5601df84defe9`; its 13 528 counts equal the vendor `.xrdml`'s intensities channel for channel (checked 2026-10-17). The `.xrdml` is not committed: its header carries a user login and a tube serial, and this file carries every data channel. The spherical-harmonics texture acceptance (`test_acceptance_srm1976a_texture.py`, #131) | Measured by the data owner, @mustachefeeling | Contributed by the data owner for redistribution with this package under the repository's terms. Reference material: NIST, *Certificate of Analysis, Standard Reference Material 1976a, Instrument Response Standard for X-Ray Powder Diffraction* (cited, not copied) |
| `srm1976a_corundum_xpert_pvii.inp` | The data owner's **solved TOPAS refinement** of the file above, a converged output (identical to its `.out`): `PO_Spherical_Harmonics(sh, 4)` with y20 **2.08901**, y40 **0.87393**, y43m **0.00178**; r_wp 12.4815943 %, r_exp 5.24587644 %, `start_X 20`; PVII peaks, `CuKa5(0.001)`, `LP_Factor(90)`, `Radius(240)`, `Simple_Axial_Model`, `Absorption`, `Specimen_Displacement`, 17 Chebyshev terms plus `One_on_X`; R-3c with a = 4.758877, c = 12.992880 Å held. **Trimmed before commit**: two blocks of comment lines that belonged to other samples' templates were removed (three commented `Out(...)` lines and a 75-line `/* … */` block of commented-out phases), and the `xdd` line was renamed to the committed pattern; the active refinement is otherwise byte-for-byte, CRLF line ends kept. Original sha256 `dae5b356749d27bda54b7df426d323643fac067f8d24663e4991f6c760959614` (230 lines), committed `a715c38f4d508aec8fc95f592106bacba71b1e1002337d68a8c4eda7b60dff77` (152 lines). The suite reads its three coefficients, r_wp and r_exp from this file | same | same; the first TOPAS reference file committed to this directory (§ TOPAS `.inp` below) |
| `cod_1000236.cif` | NAC structure, Courbion & Ferey (1988) J. Solid State Chem. 76, 426, space group I2₁3, a = 10.257 Å | Crystallography Open Database entry 1000236 | COD (public domain dedication) |
| `cod_1000055.cif` | LaB6 structure, Pm-3m, a = 4.157597 Å | COD entry 1000055 | COD (public domain dedication) |
| `cod_4002052.cif` | HKUST-1, Cu₃(BTC)₂, Peterson et al. (2014) Chem. Mater. 26, 4712, space group Fm-3m, a = 26.2711 Å, at 273 K. Its cell draws 648 atoms with its face copies, past the structure viewer's 400, so it is the figure tests' cell past the atom cap (issue #665, WP-1531) | COD entry 4002052 | COD (public domain dedication) |
| `cod_4003235.cif` | (BA)₂(MA)₂Pb₃I₁₀, the n = 3 Ruddlesden–Popper lead iodide, Stoumpos et al. (2016) Chem. Mater. 28, 2852, space group C 2 e b (No. 41), a = 8.9275, b = 51.959, c = 8.8777 Å, at 293 K. Trimmed to the items `structure_from_cif` reads: the reflection list, the SHELX files and the geometry and atom-type loops are left out, and the copy builds the same structure geometry as the full entry. Its I1 at y = 0.0605 lies 3.1435195 Å from the cell face, on a half step of 1e-6 Å. The structure viewer's position key had rounded there, which made it the fixture for the polyhedron-bond test of issue #664 (WP-1531) | COD entry 4003235 | COD (public domain dedication) |
| `cod_2104364.cif` | Monoclinic paracetamol, C₈H₉NO₂, Bouhmaida et al. (2009) Acta Cryst. B 65, 363, space group P2₁/n, a = 7.0915, b = 9.2149, c = 11.6015 Å, β = 97.865°, at 100 K, with anisotropic displacements for C, N and O and isotropic ones for H. One whole molecule cut from a block of cells is the figure tests' molecule: the old rule put its site labels on bonds and on neighbouring atoms, and the label counts could not see it (issue #666, WP-1531) | COD entry 2104364 | COD (public domain dedication) |
| `cod_9007744.cif` | YBa₂Cu₃O₆.₈₂, Brodt et al. (1990) Acta Cryst. C 46, 354, space group Pmmm, a = 3.836, b = 3.883, c = 11.686 Å. A window one period long in a and two cells in b, cut from a block, is the figure tests' case for completing the polyhedra alone: 50 of the 80 atoms `keep(..., complete=True)` adds are far ends of cut bonds that are no kept polyhedron's vertex (issue #667, WP-1531) | COD entry 9007744 | COD (public domain dedication) |
| `cod_7252065.cif` | Benzoic acid, C₇H₆O₂, Rajput & Dalvi (2026) CrystEngComm, doi:10.1039/D6CE00164E, space group P2₁/n, a = 5.507, b = 5.1404, c = 21.964 Å, β = 97.038°, V = 617.1 Å³, Z = 4, at 298 K. The source of the benzoic-acid row of `KNOWN_CELLS` in `test_indexing_formula.py` (WP-2030's measured formula window), which reads its V, Z and temperature; committed whole, as fetched | COD entry 7252065 | COD (public domain dedication, stated in the file) |
| `cod_9003308.cif` | Halite, NaCl, Walker, Verma, Cranswick, Jones, Clark & Buhre (2004) Am. Mineral. 89, 204, space group Fm-3m, a = 5.6401 Å, Z = 4, at 25 °C (298.15 K), the first of that paper's temperature series. The source of the halite row of `KNOWN_CELLS` in `test_indexing_formula.py`, which reads its a, Z and temperature; committed whole, as fetched | COD entry 9003308 (from the American Mineralogist Crystal Structure Database) | COD; the file asks for attribution to the journal article, given here, as for `cod_9007744.cif` |
| `cod_2242872.cif` | Acridine form IX, C₁₃H₉N, Stephens, Schur, Lapidus & Bernstein (2019) Acta Cryst. E 75, 489, doi:10.1107/S2056989019003645, space group P2₁/n, a = 11.28453, b = 12.38182, c = 6.67905 Å, β = 92.0618°, at 295 K; synchrotron capillary data at λ 0.699789 Å, 6 601 points from 2.002 to 35.002° 2θ. Vendored whole, sha256 `7e380aa07c85a36292236d5463d8f498630f12d7d78bc2b37bf91c1b14e1c335`: one block holds the structure and the profile loop (`_pd_proc_2theta_corrected`, `_pd_proc_ls_weight`, `_pd_proc_intensity_net`, `_pd_calc_intensity_net`). **Its `_pd_proc_intensity_net` column carries the background**, despite the item's "after background subtraction" definition: it never falls below 249 counts and is at least 14.1σ above zero at every point, and the Rwp recomputed from the deposited obs, calc and weight columns is 0.0503, the published value, so the deposited calc includes the authors' Chebyshev and broad-peak background. The weights carry a variable counting time (median w·y 1.05 below 18°, 5.1 from 26 to 30°), so σ must come from them. The pdCIF reader's net-column fixture (WP-1806, #561) | COD entry 2242872 | COD (public domain dedication) |
| `cod_1577467.cif` | Diacetylene, C₄H₂, at **5 K**: Lopes Cavalcante, Maynard-Casely, Cable, Duyker, Fayolle, Hodyss, Kennedy, Vu & Ennis (2026) *IUCrJ* 13, 94–104, doi:10.1107/S2052252525010486, space group P n m a, a = 9.3478, b = 5.9890, c = 5.6746 Å, Z = 4, every atom on the 4c mirror at y = 3/4. Carries its own **Wombat** (ANSTO) constant-wavelength neutron profile, λ = 2.413 Å, 943 points over 17.00–134.75° 2θ, as `_pd_meas_intensity_total` with `_pd_proc_ls_weight`, and GSAS-II's rigid-body refinement of it at Rwp 3.57 % (origin x = 0.12673(105), z = 0.49939(212), the midpoint of C2 and C3). Vendored untrimmed; sha256 `4f9791af1f5296329607e273fba94f9f4a1d7f63c41b659cfedc720387bf7a79`. The WP-1807 acceptance case, a linear body on a mirror (`test_rigid_body_special.py`) | Crystallography Open Database entry 1577467 (CC0 public-domain dedication) | COD (public domain dedication); the paper is CC BY 4.0 |
| `cod_1550439.cif` | Perhydropyrene, C₁₆H₂₆, at **350 K**: van de Streek, Alig, Parsons & Vella-Zarb (2019) *IUCrJ* 6, 136–144, doi:10.1107/S205225251801686X, space group P 1 2₁/n 1, a = 14.3334, b = 5.56223, c = 8.53021 Å, β = 92.0219°, Z = 2, so the 21 listed atoms are half a molecule about the 2a inversion centre. Vendored untrimmed; sha256 `df0769b7b33116d62048739a4206cc3394072e3e06775fd0422ad11d5d5f639e`. WP-1807's monoclinic case, a body on −1 (`test_rigid_body_special.py`) | Crystallography Open Database entry 1550439 (CC0 public-domain dedication) | COD (public domain dedication); the paper is CC BY 2.0 UK |
| `cod_1567181.cif` | Glutaric acid–isonicotinamide cocrystal, form II, C₅H₈O₄·C₆H₆N₂O, at 298 K: Linberg, Röder, Al-Sabbagh, Emmerling & Michalchuk (2023) *Faraday Discuss.* 241, 178–193, doi:10.1039/d2fd00115b, space group P 1 2₁/a 1, a = 26.371, b = 5.2029, c = 8.904 Å, β = 99.325°, refined in TOPAS-6 from laboratory Cu Kα₁ powder data. Carries the authors' `_geom_torsion` loop, 18 torsions to 0.01° written by TOPAS's CIF macro, among them a gauche C2–C3–C4–C5 of 64.66° and the amide's −13.40°. Vendored untrimmed, byte-identical to the COD's copy on 2026-10-31; sha256 `8956c5574e00fc43852ab76f4dd8d6bf047ebb87b0b2e99f4d9b4a795ab2fa1c`. WP-1815's published reference for torsion values, their Klyne–Prelog sign and the table's completeness (`test_geometry_torsions.py`) | Crystallography Open Database entry 1567181 (CC0 public-domain dedication) | COD (public domain dedication) |
| `cod_7252065.cif` | Benzoic acid, C₇H₆O₂, single-crystal structure: Rajput & Dalvi (2026) *CrystEngComm* 28, 3874–3883, doi:10.1039/d6ce00164e, space group P 1 2₁/n 1, a = 5.507, b = 5.1404, c = 21.964 Å, β = 97.038°, refined in SHELXL-2019/2. Carries the authors' `_geom_torsion` loop, 12 torsions to 0.1° with esds, written by SHELXL, every one within 1.5° of 0° or 180°. Vendored untrimmed, byte-identical to the COD's copy on 2026-10-31; sha256 `e2231fee9620e8fa32b4e94eb11260efd73bae987edb60afe97427040ea4d296`. WP-1815's second program for the torsion sign, where the angles sit next to the ±180° cut (`test_geometry_torsions.py`) | Crystallography Open Database entry 7252065 (CC0 public-domain dedication) | COD (public domain dedication) |
| `polyhedra_phases.json` | WP-1466's measured phase set for the structure viewer's coordination polyhedra: 21 phases, one per line, each as cell, space group and sites, with the shells a chemist draws first written beside it before the run. Written by `docs/wp/1466-measure/measure.py --fixture`; `test_structure3d.py` holds the default picture to it | 17 Crystallography Open Database entries, named in each row's `source`; the two COD files above and `fluorapatite.cif`; and an olivine built from COD 9007377 by putting Fe at 0.1 beside Mg on both M sites | COD (public domain dedication) |
| `nist_srm660c_100a.cif` | NIST SRM 660c LaB6 certification dataset incl. measured profile (5332 pts in 24 stitched scan regions, Cu Kα + graphite post-monochromator, NIST DBD, R = 217.5 mm) — v0.2 lab-instrument acceptance (`test_acceptance_srm660c.py`) | NIST Public Data Repository mds2-2315 (data.nist.gov) | NIST open data license (U.S. Government work) |
| `FAP.XRA` | Fluorapatite Ca₅(PO₄)₃F powder pattern, conventional lab Bragg-Brentano, Cu Kα doublet, 15-130.04° 2θ, 5753 pts, GSAS STD (counts-only) format — v0.2 cross-code acceptance (`test_acceptance_fap.py`) | GSAS-II tutorials repo, `LabData/data/` (github.com/AdvancedPhotonSource/GSAS-II-tutorials) | Argonne/APS tutorial data (U.S. Government work; publicly distributed) |
| `INST_XRY.PRM` | GSAS instrument parameter file for the above (λ = 1.5405/1.5443 Å, POLA **0.7**, Kα2/Kα1 0.5, starting GU/GV/GW = 2/−2/5 centideg²). Its value is that it states POLA and KRATIO *separately* where `FAP.EXP` states only POLA: both are conventionally 0.5, so this is the file that tells the two ICONS fields apart (this row read 0.5 for POLA until WP-1118 measured it). `read_gsas_prm` **refuses** it — its GU/GV/GW/GP are GSAS's stock placeholders, and the refusal names the GP of 0.1 | same | same |
| `FAP.EXP` | GSAS's **converged** refinement of `FAP.XRA` — the source of every reference value and of the refinement protocol the acceptance test mirrors. Since WP-1118 it is also the corroborating fixture for `rx.read_gsas_exp`, and the acceptance test reads the protocol from it rather than restating it | same | same |
| `fluorapatite.cif` | The `FAP.EXP` starting model (7 sites, P 6₃/m, a = 9.3717, c = 6.8859 Å) transcribed to CIF. Ships in the wheel (`src/rietx/data/examples/`, byte-identical) for the tutorial notebooks and the landing page's worked example (WP-1545). **Not** used by `test_acceptance_fap.py`, which builds the same model from the `CRS1 AT` records instead — one authority per number, and it is not this file | transcribed from `FAP.EXP` (same tutorial repo); the published structure it descends from is Hughes, Cameron & Crowley (1989), *Am. Mineral.* **74**, 870-876 | same |
| `gsas2_pbso4.gpx` | GSAS-II's CIF-tutorial PbSO₄ refinement: one `P n m a` phase against a constant-wavelength neutron histogram (λ = 1.909 Å) **and** a laboratory Cu Kα doublet, converged at Rwp 6.171 % over 8 739 channels with 49 variables, every site refining `XU`. The corroborating fixture for `rx.read_gsas2_gpx`, and the file that states its own variable count twice — `Rvals['Nvars']` and the length of `varyList` — which is the one assertion no single-field bug passes | GSAS-II tutorials repo, `CIFtutorial/data/NXPbSO4.gpx` (github.com/AdvancedPhotonSource/GSAS-II-tutorials), renamed | GSAS-II Open Source License (UChicago Argonne): royalty-free use and redistribution with the notice; vendored verbatim, test data only — nothing enters the wheel |
| `gsas2_lacamno3_magnetic.gpx` | The SimpleMagnetic tutorial's La₀.₈Ca₀.₂MnO₃ at 50 K: a nuclear phase **and** a magnetic one, fourteen constraints naming their variables with GSAS-II's own `G2VarObj`, and a pickle stream with no protocol header. It carries the three things the PbSO₄ file cannot — the magnetic refusal, the constraint decoding, and the third of the corpus a magic-byte sniff would have declined | GSAS-II tutorials repo, `SimpleMagnetic/data/LaCaMnO3 bbb.gpx`, renamed | same |
| `gsas2_mn3o4_setting.gpx` | The Magnetic-V tutorial's hausmannite Mn₃O₄ at 10 K, vendored for one property: it writes its space group as the bare `I 41/a m d`, which the tables hold in two settings, and its own `SGData['SGOps']` are origin choice **2** where the symbol alone resolves to choice 1. It is also the case the *composition* cannot separate — Mn₁₂O₁₆ either way, because both cation sites are Mn — while the two Mn sites exchange multiplicities (8c/4b against 4a/8d), so it is the fixture behind both halves of WP-1118's setting work. Two time-of-flight histograms; the nuclear phase carries a `magPhases` key | GSAS-II tutorials repo, `Magnetic-V/data/Mn3O4 10K.gpx`, renamed | same |
| `gsas2_hb2a.instprm` | A GSAS-II **text instrument file**, HFIR's HB-2A at λ = 2.40627 Å (`PNC`, constant-wavelength neutron): the one file in the tutorial corpus's twelve that `rx.read_gsas2_instprm` reads end to end, and the one the writer is checked against character for character. It states all 13 items of a single-bank constant-wavelength file, a non-zero `Zero` among them, so it pins the degrees convention as well as the centidegree one | GSAS-II tutorials repo, `MDtutorials/k_vec_tutorial/data/HB2A_ge113_op2112_Si_cycle866.instprm` (github.com/AdvancedPhotonSource/GSAS-II-tutorials), renamed | GSAS-II Open Source License (UChicago Argonne): royalty-free use and redistribution with the notice; vendored verbatim, test data only — nothing enters the wheel |
| `gsas2_hb2a_cr2wo6_4K.dat` | Cr₂WO₆ at **4 K**, below its ordering temperature: HFIR HB-2A constant-wavelength neutron, λ = 2.4067 Å (the tutorial's `.prm` `ICONS` line), 1 749 points, 8.000–128.694° 2θ, three columns (2θ, counts, σ). The pattern WP-1327's moment is measured on (`test_acceptance_magnetic.py`) | GSAS-II tutorials repo, `Magnetic-II/data/Cr2WO6_T4K.dat` at commit `924e9eb82dc6bdeebf55b2867ea30558ee530d7c` (github.com/AdvancedPhotonSource/GSAS-II-tutorials), renamed; SHA-256 `73235a5f88d939f51b62778139adb5a220a825fecfaacdb7b0e611c216744ebe` of both the vendored and the upstream bytes | GSAS-II Open Source License (UChicago Argonne): royalty-free use and redistribution with the notice; vendored verbatim, test data only — nothing enters the wheel. The tutorial's `Cr2WO6.cif` is **not** vendored: it is an ICSD entry, "(C) FIZ Karlsruhe … All rights reserved", so the acceptance suite starts from the ideal trirutile positions instead |
| `gsas2_hb2a_cr2wo6_150K.dat` | The same specimen at **150 K**, above the ordering temperature, 1 860 points, 8.000–129.919° 2θ, same instrument and format — WP-1327's null: a moment refined here must come back unsupported | same, `Magnetic-II/data/Cr2WO6_T150K.dat`; SHA-256 `8d093eac29c3f66d36a44331e77308ebea345bdf0168320a1803d6e97c5bca6e` | same |
| `gsas2_hb2a_cr2wo6.prm` | The same diffractometer as a **GSAS-I** instrument file: HFIR's HB-2A at λ = 2.4067 Å, `HTYPE PNCR` with `INS 1PRCF1 3 8` — the first real type-3 constant-wavelength neutron `.prm` `rx.read_gsas_prm` met, and the one that moved its `PNCR` refusal from the `HTYPE` onto the `PRCF` type (issue #437, WP-1312). It states `POLA 0.990` and `KRATIO 0.500` for a source with neither, which is what the reader's "read and not applied" row is tested on. Crossed against `gsas2_hb2a.instprm` in `test_gsas_prm.py`: source kind, geometry, λ to 1.8e-4 and X = Y = 0 agree; U V W, zero and axial terms differ, the two being different calibrations (a tutorial's starting instrument against a refined Si one). 892 bytes, CRLF, sha256 `0709a09bea4e1a0a132276da445371dd5978a8f0e36efadbee802c51f43e376e` | GSAS-II tutorials repo, `Magnetic-II/data/Cr2WO6_T4K_dat.prm` (github.com/AdvancedPhotonSource/GSAS-II-tutorials), renamed | GSAS-II Open Source License (UChicago Argonne): "GSAS-II may be used by anyone on a royalty-free basis. Use and redistribution, with or without modification, are permitted" with the notice; vendored verbatim, test data only — nothing enters the wheel |
| `gsas2_d1b_ba6co6.xye` | Ba₆Co₆ClO₁₆ at **1.4 K**: ILL D1B constant-wavelength neutron, λ = 2.394 Å (the `.prm`'s `ICONS` line), 3 120 points, 4.00–159.95° 2θ at 0.05°, **two columns (2θ, counts), no σ column**, CRLF line ends kept as upstream. The satellite arm's real k ≠ 0 case: its acceptance (`test_satellites_acceptance.py`, WP-1326). The tutorial writes the formula Ba₆Co₆ClO₁₅.₅; its CIF says O₁₆ | GSAS-II tutorials repo, `Magnetic-III/data/Ba6Co6.xye` at commit `924e9eb82dc6bdeebf55b2867ea30558ee530d7c` (github.com/AdvancedPhotonSource/GSAS-II-tutorials), renamed; 53 042 B, SHA-256 `f6609675733310f62898260d94c7ecf7dbc3c46cc896fc4a6b8854dd13107536` of both the vendored and the upstream bytes; downloaded 2026-10-20 with plain `curl`. The tutorial names Mentré, Kauffmann, Ehora, Daviero-Minaud, Abraham & Roussel, *Solid State Sci.* 10, 471–475 (2008), doi:10.1016/j.solidstatesciences.2007.12.032 as the original study (not read here: its propagation vector, k = (0, 0, ½), is the tutorial's, unchecked, and no moment is asserted); the method paper is Perez-Mato *et al.*, *J. Phys.: Condens. Matter* 28, 286001 (2016), doi:10.1088/0953-8984/28/28/286001 | GSAS-II Open Source License (UChicago Argonne): royalty-free use and redistribution with the notice, kept as `gsas2_tutorials_LICENSE` (SHA-256 `eb80a17984592b28cd7624238a93abc3dfd6f7cb27233a88ba3bbf5448e947c2`, the repository's LICENSE); vendored verbatim, test data only — nothing enters the wheel. The tutorial's `Ba6Co6.cif` (9 842 B) is **not** vendored (no ICSD or database notice in that file either; the acceptance test writes the starting coordinates itself from it, cited) |
| `gsas2_d1b.prm` | The same diffractometer as a **GSAS-I** instrument file, the tutorial's dummy spectrum for ILL D1B: λ = 2.39400 Å, `HTYPE PNCR`, `INS 1PRCF1 2 12` — **profile function 2**, which `rx.read_gsas_prm` refuses by name (only type 3 is read), so no reader opens it and the acceptance test takes just its `ICONS` wavelength | same, `Magnetic-III/data/D1B.PRM`; 896 B, SHA-256 `dda05da784485a089bef53c9328d11049b8fa8e399d3c211fa13aa8c80f0070e` of both | same |
| `gsas2_bt1_lamno3_50K.gsas` | LaMnO₃ at **50 K**, below its ordering temperature: NIST NCNR BT-1 constant-wavelength neutron through a Cu(311) monochromator, λ = 1.5403 Å (the `ICONS` line of `gsas2_bt1_cu311.inst`), 3 296 points, 3.00–167.75° 2θ at 0.05°, GSAS `ESD` format (a σ column), CRLF. The title line ends in non-ASCII bytes, kept as they are. WP-1327's second moment dataset and its k = 0 case (`test_acceptance_magnetic_lamno3.py`). The tutorial credits Qingzhen Huang for the data | GSAS-II tutorials repo, `Magnetic-I/data/LaMnO3_50k.gsas` at commit `ddc0dc3c4889fe4e74d8a877584c1a8696b57d27` (github.com/AdvancedPhotonSource/GSAS-II-tutorials), renamed; SHA-256 `f41456e8ba3f676c7812a6a6ddf0bdcc3f829f549c5bd48c5b0a6f9e8dfd7e0f` of both the vendored and the upstream bytes | GSAS-II Open Source License (UChicago Argonne): royalty-free use and redistribution with the notice; vendored verbatim, test data only — nothing enters the wheel. Licence checked per file on 2026-10-03: all three files sit under the tutorials repo's `LICENSE`, the licence the `gsas2_*.gpx` fixtures above already ship under |
| `gsas2_bt1_lamno3.cif` | The tutorial's starting structure for the pattern above: LaMnO₃ in `P n m a`, a = 5.7327, b = 7.67381, c = 5.53544 Å, four sites (La1, Mn2, O3, O4) with U_iso. It carries GSAS-II's own CIF-export comments (`# phase info for La Mn O3 follows`, `# Note that Z affects _cell_formula_sum and _weight`) and no database entry, copyright or ICSD/FIZ notice, checked by reading it whole. That is what lets it ship where the Cr₂WO₆ tutorial's structure file could not | same repo, `Magnetic-I/data/LaMnO3.cif`, same commit, renamed; SHA-256 `075fcbc7c585e734b073472b144d1b3b91210a3db80adcf2bd3e49ca4086cffb` of both | same |
| `gsas2_bt1_cu311.inst` | The tutorial's **GSAS-I** instrument file for that pattern: `HTYPE PNCR`, λ = 1.54030 Å, one bank stating profile functions 1, 2 and 3. `rx.read_gsas_prm` refuses it, because the bank's first function is GSAS type 1, so the acceptance suite takes λ from `ICONS` and its seeds from the type-3 record by hand: GU, GV, GW = 239.7, −298.2, 180.8 centideg², S/L 0.04, H/L 0.03. 1 558 bytes, CRLF | same repo, `Magnetic-I/data/BT1_Cu311.inst`, same commit, renamed; SHA-256 `0c1e0a33ba7b1224dc12bdecdc7b4c7f274340dfdca1ac584b3937e7201d212a` of both | same |
| `gsas2_llb3t2_prsrmno_10K.gda` | (Pr₀.₅Sr₀.₅)MnO₃ at **10 K**, below its ordering temperature: LLB 3T2 constant-wavelength neutron, λ = 1.227 Å (the tutorial's `Saclay 3T2.instprm`), F m m m, GSAS `STD` bank with its `I2` (counter-number) field written, CRLF. The header declares 2 415 channels in 242 records from 6.00° at 0.05°; the body holds 2 395 (6.00–125.70°). WP-1326's centred-lattice case: the tutorial's structure orders at k = (1, 0, 0), the X point of the F lattice (`test_satellites_acceptance.py`). Read there by a positional parser in the test, not by `rx.read_pattern`, whose STD branch misreads a written `I2` (issue #1061). The tutorial's nuclear model (Jana2006 export, two data blocks, no database or copyright notice) is not vendored; the test states its six sites, citing it. Data from Knizek, Hejtmanek, Jirak, Martin, Hervieu, Raveau, Andre & Bouree, *Chem. Mater.* **16**, 1104 (2004), doi:10.1021/cm034997r | GSAS-II tutorials repo, `Magnetic-IV/data/PrSrMnO.gda` at commit `924e9eb82dc6bdeebf55b2867ea30558ee530d7c` (github.com/AdvancedPhotonSource/GSAS-II-tutorials), renamed; SHA-256 `7925e611f93dd66eb404696ba048312afb2c2cde2e46f4126fd04769dbf13723` of both the vendored and the upstream bytes, 19 709 bytes | GSAS-II Open Source License (UChicago Argonne): royalty-free use and redistribution with the notice; vendored verbatim, test data only — nothing enters the wheel. The file sits under the tutorials repo's `LICENSE`, the licence the `gsas2_*` fixtures above already ship under |
| `llb_g41_ba2fesbse5_<T>K.xy` (twelve files: 001p5, 010, 020, 030, 040, 045, 050, 055, 065, 100, 150, 200 K; 181 545 bytes in all) | **Ba₂FeSbSe₅ through its ordering transition**: LLB (Saclay) G4.1 constant-wavelength neutron, λ = 2.426 Å, 800 points each, 2–81.9° 2θ at 0.1°, two columns (2θ, counts) with no σ column, CRLF, the authors' *corrected* patterns. **Reference values** (all from Maier *et al.* 2021, cited in the next two cells; a number a rietx run produced is never one): **T_N = 58 K**, from χ(T) and c_p(T), which "show only one transition" (Fig. 3, p. 7 of the arXiv copy); **ordered moment m_y = 4.13(4) μ_B per Fe at 1.5 K** (p. 9), refined with the two Fe moments constrained equal because the sites are crystallographically identical (the one-site model without the constraint gives about 5.8 μ_B = 4.13 × √2, so the powder fixes only the quadrature sum and the equal split is the paper's assumption); magnetic structure k = (½, 0, ½), Shubnikov group P_a 2₁/m (BNS 11.55, irreps Γ4/Γ8), two Fe³⁺ sites, collinear along b (Table 1, Fig. 5, pp. 9–10). **No other transition is reported**: the paper has no structural transition and no superstructure line. The test holds the onset bracket to T_N (inside 45 K to T_N, upper end within 5 K of it) and the 1.5 K moment to within 0.5 μ_B of 4.13 μ_B, an envelope and not agreement (tier `characterisation`). The one real ramp through an onset in the tree and the first k ≠ 0 series: `test_magnetic_series.py::test_ba2fesbse5_ramp_the_moment_grows_below_the_onset_both_ways` (WP-1329 task 5, magnetic milestone row H; tier `characterisation`). **The twelve are the smallest set that shows the whole shape**: 1.5, 10 and 20 K for the saturated moment, 30–50 K for the fall, 55 K the first pattern with no supported moment, and 65–200 K (four patterns, not one) as the paramagnetic arm, because a null read at one temperature is not a control. The other eleven of the 23 patterns (5, 15, 25, 35, 75, 125, 175, 225, 250, 275, 300 K) are not vendored. `llb_g41_ba2fesbse5.sha256` lists the SHA-256 of each file against the name it carries in the authors' folder (`Ba2FeSbSe5-<T>K-corr.xy`), bytes unchanged; the manifest's own SHA-256 is `8514c2e0244bedec30df71b03cc8d8fd047cfcddc4c98dd277504c7e17d252a2`. No instrument file is shipped: the test states λ and starts the widths itself | Data from Stefan Maier, Michael W. Gaultois, Nami Matsubara, Wesley Surta, Françoise Damay, Sylvie Hébert, Vincent Hardy, David Berthebaud, Franck Gascoin (LLB G4.1); S. Maier, M. W. Gaultois, N. Matsubara, W. Surta, F. Damay, S. Hébert, V. Hardy, D. Berthebaud and F. Gascoin, *Phys. Rev. B* **103**, 054115 (published 25 February 2021), doi:10.1103/PhysRevB.103.054115 (arXiv:2102.06484), neutron data of the study (LLB G4.1). Supplied by M. W. Gaultois, a co-author. The raw patterns were **not deposited with the paper** (the position stated on issue #277), so this is a release by the author, not a public archive copy | **CC BY 4.0**, released by co-author M. W. Gaultois for redistribution in this repository, in [his comment on #1073](https://github.com/yue-here/rietx/pull/1073#issuecomment-6316397776) (2026-10-21). Attribution means citing the publication and acknowledging the facility: We acknowledge the Laboratoire Léon Brillouin for the provision of neutron beam time. (G4.1 two-axis powder diffractometer, Orphée reactor, LLB (CEA–CNRS), CEA Paris-Saclay, France.) Citation: S. Maier, M. W. Gaultois, N. Matsubara, W. Surta, F. Damay, S. Hébert, V. Hardy, D. Berthebaud and F. Gascoin, "Sb–5s lone pair dynamics and collinear magnetic ordering in Ba₂FeSbSe₅", *Phys. Rev. B* **103**, 054115 (2021), https://doi.org/10.1103/PhysRevB.103.054115. Applies to these twelve patterns only. Test data only, nothing enters the wheel. The starting nuclear model the test uses is the published 293 K single-crystal structure of Wang, Greenfield & Kovnir, *J. Solid State Chem.* **242**, 22 (2016), typed into the test as numbers; their CIF is not vendored |
| `seqrefine_cucr2o4/OH_00.fxye` … `seqrefine_cucr2o4/OH_53.fxye` (17 files) | CuCr₂O₄ with a CuO minor phase on a cryostat ramp from **6.778 to 288.7 K** (each header's `Temp (K)`), APS 11-BM, λ = 0.413263 Å (each header's `Calibrated wavelength` and the `.prm`'s `ICONS`), 12 799 points each, 0.500–26.096° 2θ at 0.002°, GSAS `FXYE` (a σ column), runs 4148–4215 of 25 April 2011; about 420 kB each, 7.1 MB for the set. WP-2003's series family B: seven patterns below the published transition near 130 K and ten above it. The per-file runs, temperatures and SHA-256, and the reference values with their citations, are in § WP-2003 series family B below. `test_data_seqrefine_cucr2o4.py` reads every file | GSAS-II tutorials repo, `SeqRefine/data/SeqTut.zip` at commit `924e9eb82dc6bdeebf55b2867ea30558ee530d7c` (github.com/AdvancedPhotonSource/GSAS-II-tutorials; the zip's git blob `7165292a286d07defeddabf4e18de810ece8304c` is the one at that commit), zip SHA-256 `e46f5d34ea9187647156de25aca9148800d037b77bf34dc762a274f4897345ca`, downloaded 2026-10-24; extracted with names and bytes unchanged | GSAS-II Open Source License (UChicago Argonne): royalty-free use and redistribution with the notice, kept as `gsas2_tutorials_LICENSE`; vendored verbatim, test data only — nothing enters the wheel. The zip sits under the tutorials repo's `LICENSE`, the licence the `gsas2_*` fixtures above already ship under |
| `seqrefine_cucr2o4/OH_00.prm` | The tutorial's one **GSAS-I** instrument file for all 17 patterns (the tutorial reads it for the first and has the user select it for the rest): `HTYPE PXCR`, λ = 0.4132630 Å, `POLA` 0.990, `INS 1PRCF1 3 19`, headed `11-BM profile SRM 660a (LaB6) fit (Feb 2009)`. Read by `rx.read_gsas_prm` | same zip, same commit | same |
| `seqrefine_cucr2o4/CuCr2O4.cif`, `seqrefine_cucr2o4/CuO.cif` | The tutorial's **starting models**, which its page has the user import (*Import/Phase/from CIF file*). Both are GSAS-II CIF exports (data block `2p10h`, `# phase info for … follows`, `# Note that Z affects _cell_formula_sum and _weight`) with no database entry, copyright or ICSD/FIZ notice, checked by reading them whole. CuCr₂O₄: `Fddd` with an operator list holding `-x,-y,-z`, i.e. origin choice 2 (rietx resolves `F d d d:2`), a = 7.712699, b = 8.543299, c = 8.536427 Å, three sites (Cu 8a, Cr 16d, O 32h), U_iso(O) written as −0.004 Å². CuO: `C 1 2/c 1`, a = 4.67951, b = 3.420647, c = 5.125283 Å, β = 99.8314°. These cells and coordinates are **the tutorial's GSAS-II values, not reference values**. Vendored because the chain-action measurements fit the series from a stated model and these are the tutorial's own. `structure_from_cif` reads CuCr₂O₄'s O site, `Uiso -0.004`, as Biso −0.32 Å² with no diagnostic: the file states that value, so it is vendored as written, and a chain measurement starting from this model should reset O's displacement first | same zip, same commit | same |
| `topas_moment_basis_A_mono3_mag_hkl.txt` | TOPAS-64 v6's per-reflection table (columns h k l M d Th I_no_scale_pks I_after_scale_pks; 147 reflections, CRLF, 11 907 bytes, sha256 `b7cee8e32e88e366eea87df9fc7dc9f18644828533503a4fd1866bba27e0d255`) for **our own synthetic input**: one Mn²⁺ site at (0.13, 0.27, 0.41) in BNS 1.1 on a 5.2 / 6.9 / 8.4 Å, β = 115° cell, fractional-basis moment components (0.4, −0.3, 0.3), Landé g 2, the magnetic term alone, constant-wavelength neutrons at λ = 2.41 Å, nothing refined (`iters 0`). The artefact behind `TOPAS_MOMENT_CONVENTION`: `test_magcif.py::test_topas_own_intensities_rerun_the_equal_d_pair_check` re-runs the equal-d pair ratios against it (WP-1328, review of #478) | TOPAS run as a **black-box oracle** by the maintainer on 2026-09-25 (block `A_mono3_mag` of the WP-1328 moment-basis kit); no TOPAS source or macro body was read. The input is transcribed in the test | Program output for an input of ours: numbers only, no TOPAS code or text; test data only — nothing enters the wheel |
| `topas_export_stephens_str_lor_fwhm_ycalc.txt` | TOPAS-64 v6's Y_calc at **zero cycles** (`Out_X_Ycalc`: 2θ, Y_calc; 2800 points, 10–150° at 0.05°, CRLF, 78 400 bytes, sha256 `07c3661a8a7f58cfe374778c2177493e0c3ea232308f1a0f675740a9498f597e`) for a whole input whose `str` carries the `lor_fwhm` line `write_topas_inp` writes for **our own synthetic model** built in `test_projects_topas.py` (rutile's cell and sites, a Stephens anisotropic strain block of four unequal symmetry-allowed patterns; scale 2.0e-3), copied with `iters 0`. Instrument stated beside it: constant-wavelength neutrons at λ = 1.594 Å, a TCH profile U, V, W, X, Y = 0.05, −0.03, 0.04, 0.02, 0.01 and a Chebyshev background 300, −40, 15 (`test_projects_topas.py::test_topas_convolves_the_written_width_lines`). | TOPAS run as a **black-box oracle** on 2026-10-06 (the licensed TOPAS VM; LP canary passed, 1233/1233 rows to 3.67e-7; 8/8 hkl tables identical to 2026-09-25); no TOPAS source or macro body was read. The model is built in the test, so the input is reproducible from the tree | Program output for an input of ours: numbers only, no TOPAS code or text; test data only — nothing enters the wheel |
| `topas_export_widths_str_ycalc.txt` | TOPAS-64 v6's Y_calc at **zero cycles** (`Out_X_Ycalc`: 2θ, Y_calc; 2800 points, 10–150° at 0.05°, CRLF, 78 400 bytes, sha256 `f11c96354ae789e97c8a3752ab28636260fa8bf579210eecb8430df0b0e130b6`) for a whole input whose `str` carries the `lor_fwhm` and `gauss_fwhm` lines `write_topas_inp` writes for **our own synthetic model** built in `test_projects_topas.py` (rutile's cell and sites, the same block with `lor_size` 0.03, `gauss_strain` 0.02 and `gauss_size` 0.01; scale 2.0e-3), copied with `iters 0`. Instrument stated beside it: constant-wavelength neutrons at λ = 1.594 Å, a TCH profile U, V, W, X, Y = 0.05, −0.03, 0.04, 0.02, 0.01 and a Chebyshev background 300, −40, 15 (`test_projects_topas.py::test_topas_convolves_the_written_width_lines`). | TOPAS run as a **black-box oracle** on 2026-10-06 (the licensed TOPAS VM; LP canary passed, 1233/1233 rows to 3.67e-7; 8/8 hkl tables identical to 2026-09-25); no TOPAS source or macro body was read. The model is built in the test, so the input is reproducible from the tree | Program output for an input of ours: numbers only, no TOPAS code or text; test data only — nothing enters the wheel |
| `topas_export_nacl_neutron_ycalc.txt` | TOPAS-64 v6's Y_calc at **zero cycles** (`Out_X_Ycalc`: 2θ, Y_calc; 2800 points, CRLF, 78 400 bytes, sha256 `52e9a1f18224f41396225a3a3da3b48ccd6b634833977a42760f853b9d22e7a2`) for the whole TOPAS input `write_topas_inp(..., free=, instrument=, pattern=, scale="topas")` writes (scale × 100) for **our own synthetic model** `tests/topas_export_cases.py::case_nacl_neutron`, copied with `iters 0`, no `do_errors` and the one `Out_X_Ycalc` line. NaCl, constant-wavelength neutrons, a Chebyshev background, a zero shift and Sabine extinction: the neutron scale constant (× 100) and the `scale_pks` extinction term (`test_topas_refined.py`, `test_topas_whole_input.py`). | TOPAS run as a **black-box oracle** on 2026-10-06 (the licensed TOPAS VM; LP canary passed, 1233/1233 rows to 3.7e-7); no TOPAS source or macro body was read. The model is built in the case module, so the input is reproducible from the tree | Program output for an input of ours: numbers only, no TOPAS code or text; test data only — nothing enters the wheel |
| `topas_export_nacl_xray_ycalc.txt` | TOPAS-64 v6's Y_calc at **zero cycles** (`Out_X_Ycalc`: 2θ, Y_calc; 10000 points, CRLF, 280 000 bytes, sha256 `c3653d9afb8a2d80ac1c2c8d53a5850cb49b4bf9caa3d77a5d68729eb45e0eb1`) for the file `write_topas_inp(..., free=, instrument=, pattern=, scale="topas")` writes for **our own synthetic model** `tests/topas_export_cases.py::case_nacl_xray`, copied with `iters 0`, no `do_errors` and the one `Out_X_Ycalc` line. NaCl, Cu Kα₁/Kα₂ at K = 0.5 and a specimen displacement: `LP_Factor`, the X-ray scale constant K and the displacement term (`test_topas_whole_input.py`). The case declares `Source.dispersion = Dispersion()` (on): TOPAS's Y_calc matches rietx at 2.4e-3 with it and at 4.4e-2 with it off, so it carries the anomalous term. Extinction is 0 here; the X-ray extinction unit is measured by `topas_export_nacl_xray_ext20_ycalc.txt`. | TOPAS run as a **black-box oracle** on 2026-10-06 (the licensed TOPAS VM; LP canary passed, 1233/1233 rows to 3.7e-7); no TOPAS source or macro body was read. The model is built in the case module, so the input is reproducible from the tree | Program output for an input of ours: numbers only, no TOPAS code or text; test data only — nothing enters the wheel |
| `topas_export_nacl_xray_ext20_ycalc.txt` | TOPAS-64 v6's Y_calc at **zero cycles** (`Out_X_Ycalc`: 2θ, Y_calc; 10000 points, CRLF, 280 000 bytes, sha256 `1a4961534371ff529a8911172c9c0b325cffca9f0b931a4dd25938b138955f2d`) for the file `write_topas_inp(..., free=, instrument=, pattern=, scale="topas")` writes for **our own synthetic model** `tests/topas_export_cases.py::case_nacl_xray` with the phase's extinction set to 20, copied with `iters 0`, no `do_errors` and the one `Out_X_Ycalc` line (the `scale_pks` term TOPAS ran is the one the writer emits, byte for byte with the parameter's value in place of its name). The X-ray |F|² unit of the Sabine `scale_pks` term: with TOPAS's `A01^2 + B01^2 + A11^2 + B11^2` taken as rietx's |F|² (factor 1) rietx's `predict()` matches at 2.6e-3, the case's own floor; extinction 0 misses by 2.4e-1 and the neutron factor 100 by 3.7 (`test_an_xray_extinction_is_written_in_electrons_squared`). In the same session TOPAS's `A01^2 + B01^2 + A11^2 + B11^2` was 1.0008 × rietx's |F|² on average over 16 reflections (the scattering-factor tables), and the extinction-0 run reproduced `topas_export_nacl_xray_ycalc.txt` byte for byte. | TOPAS run as a **black-box oracle** on 2026-10-08 (the licensed TOPAS VM, tc.exe SHA-256 `292A95FD…95EED0CC`; LP canary passed, 18/18 rows to 2.1e-8); no TOPAS source or macro body was read. The model is built in the case module, so the input is reproducible from the tree | Program output for an input of ours: numbers only, no TOPAS code or text; test data only — nothing enters the wheel |
| `topas_export_nacl_pspline_ycalc.txt` | TOPAS-64 v6's Y_calc at **zero cycles** (`Out_X_Ycalc`: 2θ, Y_calc; 1200 points, CRLF, 33 600 bytes, sha256 `986f9809c2d4d5e362182492a7d7a406f4646d45fff5d25f50df3fec4a2f52c5`) for the file `write_topas_inp(..., free=, instrument=, pattern=, scale="topas")` writes for **our own synthetic model** `tests/topas_export_cases.py::case_nacl_pspline`, copied with `iters 0`, no `do_errors` and the one `Out_X_Ycalc` line. NaCl, neutrons, a smoothed P-spline background and FCJ axial divergence: the `fit_obj` B-spline pieces, the `penalty` terms (TOPAS printed P = 32.039846 for this run, rietx's Σr² 32.039846) and `Finger_et_al` (`test_topas_whole_input.py`). | TOPAS run as a **black-box oracle** on 2026-10-06 (the licensed TOPAS VM; LP canary passed, 1233/1233 rows to 3.7e-7); no TOPAS source or macro body was read. The model is built in the case module, so the input is reproducible from the tree | Program output for an input of ours: numbers only, no TOPAS code or text; test data only — nothing enters the wheel |
| `topas_export_child_magnetic_ycalc.txt` | TOPAS-64 v6's Y_calc at **zero cycles** (`Out_X_Ycalc`: 2θ, Y_calc; 1120 points, CRLF, 31 360 bytes, sha256 `ce03133559aaade8951d5305db218cbb73c9a30f4eab8cdfd14776e743424c95`) for the file `write_topas_inp(..., free=, instrument=, pattern=, scale="topas", p1_expand="auto")` writes for **our own synthetic model** `tests/topas_export_cases.py::case_child_magnetic`, copied with `iters 0`, no `do_errors` and the one `Out_X_Ycalc` line. A k = (½, 0, 0) magnetic child of a synthetic Pbcm parent with a magnetic-only Lorentzian width, a P-spline and FCJ axial: the P1 restatement with its ties and the two-`str` magnetic part (`test_topas_p1_ties.py`). | TOPAS run as a **black-box oracle** on 2026-10-06 (the licensed TOPAS VM; LP canary passed, 1233/1233 rows to 3.7e-7); no TOPAS source or macro body was read. Re-run 2026-10-09 from the writer as rebased onto the merged whole input (`TOPAS-64 Version 6 (c) 1992-2016 Alan A. Coelho`, tc.exe sha256 `292A95FD…95EED0CC`, LP canary 18/18 rows to 2.1e-8): the `.inp` and this file came back byte-identical. The model is built in the case module, so the input is reproducible from the tree | Program output for an input of ours: numbers only, no TOPAS code or text; test data only — nothing enters the wheel |
| `gsas2_bnl.instprm` | The same format and the opposite answer: a converged `PXC` (X-ray) calibration whose `X` is **−0.0978 centidegrees**. GSAS-II bounds none of its width coefficients and this package's Lorentzian terms are softplus-bounded at zero, so it is refused by name — and 2 of the corpus's 4 constant-wavelength files are this case, which is why the refusal is tested against a real file rather than a written one | GSAS-II tutorials repo, `MCsimanneal/data/BNL-I.instprm`, renamed | same |
| `gsas2_sh_texture.json` | **GSAS-II 5.8.4's spherical-harmonics texture correction**, the WP-1960 golden. Sixteen cases, one per Laue class and setting (the three monoclinic unique axes, −3 and −3m on rhombohedral axes, −3m1 and −31m apart), each with a generic cell, every coefficient GSAS-II allows to order 8, and the 62 reflections with \|h\|, \|k\|, \|l\| ≤ 2 taken once per Friedel pair. Per reflection: GSAS-II's frame angles (`CrsAng`), its crystal harmonic per coefficient (`GetKcl`), and `SHPOcal`'s P under `Bragg` and `Debye` at zero goniometer angles for seeded coefficients, with the sample angle ψ used (90° and θ). Per case, `noninvariant` names each coefficient whose harmonic takes two values on one orbit, measured over ±hkl: every n ≠ 0 term of −1 and of all three monoclinic settings, every term on rhombohedral axes, and −31m's n = 3 terms. No basis can match those. `pytexture` is single precision, so agreement is to about 1e-7 relative. Generated twice on 2026-10-14, darwin/arm64, identical apart from the date. 265 KB | Generated by `tests/data/make_gsas2_sh_texture.py` under GSAS-II 5.8.4's own interpreter (its docstring has the command) | Numbers computed by running GSAS-II; no GSAS-II code or data is copied, and nothing enters the wheel |
| `qarr/cpd-1a.prn` … `qarr/cpd-1h.prn` | IUCr CPD QPA round-robin **Sample 1** suite: eight three-phase corundum (Al₂O₃) / zincite (ZnO) / fluorite (CaF₂) mixtures spanning trace→major for each phase; weighed compositions known (below). 2-column ASCII (2θ°, counts), 5–150° 2θ, 0.02° step, 7251 pts — v0.3 QPA acceptance (`test_acceptance_qpa_roundrobin.py`) | IUCr CPD Quantitative Phase Analysis Round Robin, "col" (2θ,counts) format, `www.iucr.org/__data/iucr/powder/QARR/col/`; retrieved via the Internet Archive (the live IUCr site is behind a Cloudflare JS challenge). **The live site is the better route now** — the challenge clears for a real browser session, which is how the `.rd` files below were fetched in 2026-09; see the WP-1407 section | IUCr CPD / CSIRO Minerals round-robin data, freely released on the web (Nov 1999) "for re-analysis with a standard Rietveld code"; no explicit open licence — redistributed here as an academic QPA benchmark, with attribution (see licence note below) |
| `qarr/cpd-2.prn` | **Sample 2** = sample-1 phases + brucite Mg(OH)₂ (strongly platy → preferred-orientation test) | same | same |
| `qarr/cpd-4.prn` | **Sample 4** = corundum / coarse magnetite (Fe₃O₄) / zircon (ZrSiO₄) — microabsorption test | same | same |
| `qarr/corundum.prn`, `qarr/fluorite.prn`, `qarr/zincite.prn`, `qarr/brucite.prn`, `qarr/magnetit.prn`, `qarr/zircon.prn` | Pure single-phase patterns of the round-robin component phases, same instrument/conditions — component references for the mixtures and the SRM 676a corundum comparison | same | same |
| `qarr/corundum.rd`, `qarr/cpd-1e.rd` | The **original logged Philips `.rd`** files behind two of the `.prn` patterns above — binary `V3RD`, 250-byte header, 7251 √-compressed `uint16` intensities, 14752 bytes each. The v1.4 Philips reader's only real fixtures, and the `.prn` beside each is an independent value oracle already in the tree | The same IUCr CPD kit, "Binary Philips RD format (Original logged files)" column, `www.iucr.org/__data/iucr/powder/QARR/philips.zip`, logged 19–21 Dec 1997 — see the WP-1407 section below | same as the `.prn` files (same release, same page, same licence note) |
| `fm3m_gamma_witnesses.json` | The fourteen Farkas witnesses rietx's own `_classify` found on the `F m -3 m` Γ general-site set (site (0.11, 0.13, 0.17), d_min 1.5 Å, 10 shells, seed 20260906, 12 draws per direction across irreps, restarts 32; nine of them in the consistency rule's rejoin pass), each as the draw's intensity on every shell, the target's live shells, the quoted certificate y on them, the dual's maximiser direction and the d bracket, with the pair's labels. The stored-witness acceptance arm of issue #565 part 5 (`test_magnetic_isotropy.py::test_the_fm3m_set_splits_s8_and_s9_from_the_stored_witnesses`) rebuilds each from these numbers, re-verifies it against the stack the module builds, and injects it in place of the draw | A group × k enumeration at a general site: no measured data. Written on 2026-10-13 (macOS arm64, numpy 2.5.2, scipy 1.18.1) by the part-5 run recorded in that test's docstring | This repository's own numbers (MIT) |
| `bethanechol_indexing.json` | The **indexing benchmark**: ten sets of twenty 2θ positions for bethanechol chloride (C₇H₁₇ClN₂O₂), the known answer (monoclinic P2₁/n, a = 8.875, b = 16.408, c = 7.137 Å, β = 93.84°, V = 1036.9 Å³), the published M(20) = 197 / F(20) = 1080, and Table 5's scores — v1.0 indexing acceptance (`test_acceptance_indexing.py`) | Bergmann, Le Bail, Shirley & Zlokazov (2004), *Z. Kristallogr.* **219**, 783-790, Tables 5 and 6 | Published tables, transcribed with attribution; **no program output and no code** — see the section below |
| `wp1932_boundary_pairs.json` | 24 pairs of **this package's own indexing candidates**, each a Niggli-reduced A..F vector with its covariance carried into the reduced frame, exactly as `engines.dedup_groups` compared them: the 8 LaB₆ pairs and 10 bethanechol pairs that one lattice's two descriptions split across a reduction boundary, and 6 bethanechol pairs of two lattices whose sorted Selling scalars still agree within the gate. The acceptance and positive arms of WP-1932 (`test_indexing_reduce_boundaries.py`) | Logged by the WP-1932 boundary count (#834) on `9219e886`, 2026-10-09, from `test_acceptance_indexing.py`'s SRM 660c LaB₆ searches and the benchmark on `bethanechol_indexing.json`; each pair labelled by an exhaustive unimodular search (\|m_ij\| ≤ 3) judged by the unchanged `equal_reduced` | Program output of this package on the two inputs above; no third-party data beyond theirs |
| `hl2_peaks.txt` | 74 peak positions (2θ, d, I_rel) from a **genuinely unindexed** laboratory pattern, Cu Kα1 — the abstention fixture, whose correct answer is "we do not know" | Our own derived product: peaks picked from `HL2-1_2.xy` in the `examples/` folder of datalab-org/guillemot (MIT), which is *not* vendored here | Derived table, carried with attribution |
| `absorption_cylinder_rouse.dat` | Cylinder **transmission** factor A (not A\* = 1/A) vs µR and sin²θ, 4 dp — 80 values: the full sin²θ = 0 column (µR 0.00–0.50 step 0.01) plus four complete µR = 0.50 / 1.00 rows. Ground truth for the WP-0501 capillary absorption correction (`test_absorption.py`) | Rouse, Cooper, York & Chakera (1970), *Acta Cryst.* **A26**, 682-691, Table 1(a)/(b) | Published table, transcribed with attribution; no code involved |
| `backend_goldens/toy_anomalous_y_obs.npy` | The **frozen synthetic observed pattern** of the `toy_anomalous` bit-identity state (`tests/test_backend_shim.py`): 3 350 float64 intensities on `np.arange(28.0, 95.0, 0.02)` °2θ, 25.0 to 6000.45, SHA-256 of the file `5e3d1a3bf8da1a3e`.  Generated by the state's own former simulation, at main `8a47e888`: zincite (`tests/test_dispersion.zincite`) with scale 6.0e-3, an anisotropic Zn site, Cu Kα Bragg-Brentano with dispersion on, `profile.w` 1.2e-2 and a 4-term Chebyshev background, evaluated with `cell.a + 0.004` and `atoms[1].z + 0.003`, plus a flat 25.  Noiseless: no random number and no seed enter it.  Evaluated on macOS 26.7.1 arm64, Python 3.12.13, numpy 2.5.2, 2026-10-08, and identical over two processes.  Frozen because the evaluation goes through libm and moved with the macOS major (#760); see § backend_goldens/ | Generated in this repository (WP-1928) | Synthetic; no external source |
| `planted_series/table.csv` | `SeriesResult.to_table()` of the **synthetic planted-events series** of issue #141 (`tests/planted_series.py`): 248 patterns of a cooling ramp of a generic cubic perovskite, seed 0, events planted at 50 (background step), 87 (blank frame), 124 (an unmodelled rock-salt phase appearing and growing) and 186 (cubic → tetragonal), fitted with one fixed cubic model under `mccusker_default`, `refit="single"`. Columns `index, label, T (K), status, rung, rwp, gof` and the cell edge, scale, zero shift, W and background constant with their esds, six significant figures; 38 578 bytes. The patterns themselves are not vendored: `python -m tests.planted_series --out DIR` regenerates them and this file | Generated in this repository (#141) | Synthetic; no external source |
| `planted_series/signals.json`, `planted_series/null_signals.json` | The same run's signals, read off its `SeriesResult` (`planted_series.signals`): the entries above the Rwp fence, the flagged steps, reseeds, quarantines, `PHASE_UNCONSTRAINED` entries and the series-level codes, with the signal marking each planted event (`planted_series.surfaced`); and the null series' (same ramp and noise, no event, `--null`), all empty. 8 697 and 199 bytes. `test_planted_series.py`'s slow row regenerates both and compares | Generated in this repository (#141) | Synthetic; no external source |
| `d1b_co3o4_quench/300q-1p5K_1.dat` | Co₃O₄ quenched from **300 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; a **spreadsheet export**, eight tab-separated columns, no `XYDATA` heading; rietx reads columns 1–3 and drops row 1 (`PATTERN_ROWS_DROPPED`), 1 279 points from 0.89°; 66729 B, SHA-256 `08005a2c1808ec9a09ce2014c89b38b1976619deeb0926c206d62a6b4f0ed5c6`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.40 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value); the text quotes "2.4 μ_B" for the low-quench samples | ILL D1B, same experiment (no heading: see the section). Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/300q-100K.dat` | Co₃O₄ quenched from **300 K**, measured at **100 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52800 B, SHA-256 `1fd05676419d405d6dd0a512734b16af54f180a664f9dceabe7cc73ed22ede6c`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; the paper shows refinements at 1.5 K and 300 K only (Fig. 7, p. 104104-6) | ILL D1B, 13-Nov-11, run 129864 129853>129864, heading title `edurneorf Co3O4-quenched_RT_100K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/300q-300K.dat` | Co₃O₄ quenched from **300 K**, measured at **300 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52798 B, SHA-256 `8c1f031254181a4801fb6280b0a8664b767b293c6f865c119cbf4fd4866cd576`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; nuclear F d -3 m only (the paper fits its 300 K patterns so, Fig. 7(b), p. 104104-6) | ILL D1B, 15-Nov-11, run 130033 130022>130033, heading title `SparksLave Co-quenched_RT_300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/773q-1p5K_1.dat` | Co₃O₄ quenched from **773 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52801 B, SHA-256 `ac8011ae4d4d0a45ad4a4c36c8f059d56ad72ecb392c5280c73ec45ff5f08eb8`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.41 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value) | ILL D1B, 13-Nov-11, run 129876 129865>129876, heading title `edurneorf Co3O4-quenched_500_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/773q-100K.dat` | Co₃O₄ quenched from **773 K**, measured at **100 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52801 B, SHA-256 `1cef9e9763dd238f2bb4d64363095d020395b9d00e5b37fc3abd87d8dbdd7bca`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; the paper shows refinements at 1.5 K and 300 K only (Fig. 7, p. 104104-6) | ILL D1B, 13-Nov-11, run 129888 129877>129888, heading title `edurneorf Co3O4-quenched_500_100K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/823q-1p5K_1.dat` | Co₃O₄ quenched from **823 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `b268c9a4241f601a5e7ff9d3ded42138f573bb2b4f320e2e7dd59f4e3764c5bf`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.45 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value) | ILL D1B, 14-Nov-11, run 129902 129889>129902, heading title `SparksLave Co3O4-quenched_550_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/823q-100K.dat` | Co₃O₄ quenched from **823 K**, measured at **100 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `db25f5e39f2f682129becc1f12bc5eaa6513057dbe083a71e790b1402d1adfa9`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; the paper shows refinements at 1.5 K and 300 K only (Fig. 7, p. 104104-6) | ILL D1B, 14-Nov-11, run 129916 129903>129916, heading title `SparksLave Co3O4-quenched_550_100K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/823q-300K_1.dat` | Co₃O₄ quenched from **823 K**, measured at **300 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52799 B, SHA-256 `014dfaf0a9f442e1d812054ed60924e9db7c57a8608e75ecc37043d2305a7e94`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; nuclear F d -3 m only (the paper fits its 300 K patterns so, Fig. 7(b), p. 104104-6) | ILL D1B, 15-Nov-11, run 130045 130034>130045, heading title `SparksLave Co-quenched_550_300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/873q-1p5K_1.dat` | Co₃O₄ quenched from **873 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `5df4699053231c9208556c2ac2e042e62d61d1f8e930b69cb1995fadf6c1acb2`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.54 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value) | ILL D1B, 14-Nov-11, run 129997 129986>129997, heading title `SparksLave Co3O4-quenched_600_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/873q-300K.dat` | Co₃O₄ quenched from **873 K**, measured at **300 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `f4788618841d9b4ad30b1c6f859994f586bedaff33041ef519ae5f32bd76300a`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; nuclear F d -3 m only (the paper fits its 300 K patterns so, Fig. 7(b), p. 104104-6) | ILL D1B, 14-Nov-11, run 129985 129974>129985, heading title `SparksLave Co3O4-quenched_600_300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/923q_1p5K_1.dat` | Co₃O₄ quenched from **923 K**, measured at **1.5 K** (renamed from `723q_1p5K_1.dat` on 2026-09-08: the sample quenched from 650 °C, `923q`; its 100 K and 300 K scans do not exist). ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `805a645223aafef30b7c45ea3183482cc42b924cdb6e5279bcd2339921644d64`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.57 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value) | ILL D1B, 16-Nov-11, run 130094 130083>130094, heading title `SparksLave Co3O4-quenched_650_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/973q-1p5K_1.dat` | Co₃O₄ quenched from **973 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `10c0e9b4a271b16336e71c73f2df313048a437bad4c6a93d06874ff324ce1c14`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.63 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value) | ILL D1B, 15-Nov-11, run 130021 130010>130021, heading title `SparksLave Co3O4-quenched_700_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/973q-300K.dat` | Co₃O₄ quenched from **973 K**, measured at **300 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `214f231504d1fa46fff22ba591f3395949739e6c0351eb709b539597b48b06a6`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; nuclear F d -3 m only (the paper fits its 300 K patterns so, Fig. 7(b), p. 104104-6) | ILL D1B, 15-Nov-11, run 130009 129998>130009, heading title `SparksLave Co3O4-quenched_700_300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1023q_1p5K.dat` | Co₃O₄ quenched from **1023 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `ad42fb7de5d2572a7cd09a0f09e5caf4e913b3cc9b32221018cc56af6651b0d5`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.67 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value) | ILL D1B, 15-Nov-11, run 130082 130071>130082, heading title `SparksLave Co3O4-quenched_750_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1023q_300K_1.dat` | Co₃O₄ quenched from **1023 K**, measured at **300 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `72f900143172a2af3c5ebca00a7dfa4c3f44ed7a1f6a3d02324b2ef24c490aa6`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; nuclear F d -3 m only (the paper fits its 300 K patterns so, Fig. 7(b), p. 104104-6) | ILL D1B, 15-Nov-11, run 130070 130059>130070, heading title `SparksLave Co3O4-quenched_750_300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1073q_1p5K.dat` | Co₃O₄ quenched from **1073 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `f96e157a448a224cd7505a87a61666575b4cc3918ab24483a974348918285e70`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.69 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value) | ILL D1B, 16-Nov-11, run 130106 130095>130106, heading title `SparksLave Co3O4-quenched_800_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1073q_300K_1.dat` | Co₃O₄ quenched from **1073 K**, measured at **300 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `07039ffaf3beacca2bd2b3422964a0a4a37fa13030d6ce5407e8db0e0b468b27`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; nuclear F d -3 m only (the paper fits its 300 K patterns so, Fig. 7(b), p. 104104-6) | ILL D1B, 16-Nov-11, run 130118 130107>130118, heading title `SparksLave Co3O4-quenched_800_300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1123q-1p5K_1.dat` | Co₃O₄ quenched from **1123 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `9bdf19d533ae5da23548453b27f87fff45341bd5bb17488b949758b15592f18d`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.70 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value) | ILL D1B, 14-Nov-11, run 129930 129917>129930, heading title `SparksLave Co3O4-quenched_850_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1123q-100K.dat` | Co₃O₄ quenched from **1123 K**, measured at **100 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `415f67f406cbd543eb7517d88e8c9ca513235dbc756186b6c3d4d8a034058925`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; the paper shows refinements at 1.5 K and 300 K only (Fig. 7, p. 104104-6) | ILL D1B, 14-Nov-11, run 129944 129931>129944, heading title `SparksLave Co3O4-quenched_850_100K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1123q_300K.dat` | Co₃O₄ quenched from **1123 K**, measured at **300 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52799 B, SHA-256 `ecafc4fe33137850185e15e5a5196f5a7a10f4b994188b8286dff61a90ea570e`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; nuclear F d -3 m only (the paper fits its 300 K patterns so, Fig. 7(b), p. 104104-6) | ILL D1B, 15-Nov-11, run 130057 130046>130057, heading title `SparksLave Co-quenched_850_300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1173q-1p5K_1.dat` | Co₃O₄ quenched from **1173 K**, measured at **1.5 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52802 B, SHA-256 `4ba8b37912dd6528d99181b227f31710b1c65c852bd6e65a45062c244503a947`. Reference values: k = 0; Γ₇ on 8a (the two A-site Co antiparallel), no 16d moment (pp. 104104-6, -7); ordered A-site moment **2.71 ± 0.02 μ_B, read off Fig. 8** (p. 104104-7; no printed value); the text quotes 2.71 μ_B for this sample but calls it "quenched from 1200 K" | ILL D1B, 14-Nov-11, run 129961 129948>129961, heading title `SparksLave Co3O4-quenched_900_1.5K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/1173q-300K.dat` | Co₃O₄ quenched from **1173 K**, measured at **300 K**. ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52800 B, SHA-256 `d315c53427479485579c0993aeac5d1fbc3d472f7bc96ed1e651d645be04f115`. Reference values: above T_N ≈ 40 K (stated, p. 104104-2): no ordered moment; nuclear F d -3 m only (the paper fits its 300 K patterns so, Fig. 7(b), p. 104104-6) | ILL D1B, 14-Nov-11, run 129973 129962>129973, heading title `SparksLave CoO-quenched_900_300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/standard_garnet_300K_1.dat` | The experiment's **garnet standard** at 300 K, renamed from `standard_YAG_300K_1.dat`: its heading says `YIG-300K`, and its lines index on a garnet cell of about 12.36 Å, not on YAG's (our reading of the peak positions; see the section). ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52757 B, SHA-256 `90baf260d256981bb6bcdbf149bab99257dd619b34c044cf355a78332f90860c`. Reference values: none: no garnet cell is asserted, and it is not a wavelength calibrant until its identity is settled | ILL D1B, 15-Nov-11, run 130058, heading title `SparksLave YIG-300K`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/vanadium_can_120K.dat` | The **empty vanadium can in the cryostat** at 120 K (heading `empty cryostat`; its strongest line is V(110) at 72.2° 2θ). ILL D1B, λ = 2.52 Å; 1 280 points, 0.79–128.69° 2θ at 0.1°, FullProf `XYDATA` (2θ, counts, σ), CRLF; 52793 B, SHA-256 `b2f85cd1c98ad04dfeb1f47bcf828180d81c7a7d53eb2973bbec4a6ed2afd104`. Reference values: none (a background and V-line reference) | ILL D1B, 14-Nov-11, run 129947 129945>129947, heading title `SparksLave empty cryostat`. Data of Sparks *et al.*, *Phys. Rev. B* **99**, 104104 (2019), doi:10.1103/PhysRevB.99.104104 (§ "WP-2003 family D" below) | CC BY 4.0, released for this repository by M. W. Gaultois, a co-author of the study ([release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only, nothing enters the wheel |
| `d1b_co3o4_quench/PLANTED_shuffled_counts_from_873q-1p5K_1.dat` | **PLANTED, not a measurement** (WP-2003, issue #1150: a known-bad pattern for a series' quarantine and `on_error`). `873q-1p5K_1.dat` with its (counts, σ) pairs permuted across the 1 280 channels (NumPy PCG64, seed 2003); 2θ column and heading numbers unchanged, title replaced. Every Bragg peak is gone, totals and noise kept. Rebuilt byte-for-byte by `make_planted.py`; SHA-256 `ed97fd7642f805b9251d890313d39cdccc3a16d664269bde8dfafec422da9a6f`. Reference values: none; the right answer is that no competent refiner would fit it as a Co₃O₄ pattern | Derived by `d1b_co3o4_quench/make_planted.py` from the real file named | As its source file (CC BY 4.0, [release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only |
| `d1b_co3o4_quench/PLANTED_nan_block_from_1023q_1p5K.dat` | **PLANTED, not a measurement** (WP-2003, issue #1150: a known-bad pattern for a series' quarantine and `on_error`). `1023q_1p5K.dat` with counts and σ written `NaN` on 60 channels, 2θ 30.79–36.69° (over the (111) line); title replaced. Rebuilt byte-for-byte by `make_planted.py`; SHA-256 `0d02f333e99be6a5afe14b493a2794b5e09c86a0756ad7331844d67081147598`. Reference values: none; the right answer is that no competent refiner would fit it as a Co₃O₄ pattern | Derived by `d1b_co3o4_quench/make_planted.py` from the real file named | As its source file (CC BY 4.0, [release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only |
| `d1b_co3o4_quench/PLANTED_wrong_sample_garnet_titled_co3o4.dat` | **PLANTED, not a measurement** (WP-2003, issue #1150: a known-bad pattern for a series' quarantine and `on_error`). `standard_garnet_300K_1.dat` with only its title replaced, to read as a Co₃O₄ 300 K quench pattern: a wrong sample put in a series. Rebuilt byte-for-byte by `make_planted.py`; SHA-256 `4106059919e9b89b4d377aec80ac48ba707ecd58df74ae42e7c2a3a60002c3a5`. Reference values: none; the right answer is that no competent refiner would fit it as a Co₃O₄ pattern | Derived by `d1b_co3o4_quench/make_planted.py` from the real file named | As its source file (CC BY 4.0, [release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748)); test data only |
| `d1b_co3o4_quench/make_planted.py` | The deterministic script that writes the three `PLANTED_` files from real files beside it | Written for this repository | MIT, as the code |
| `d1b_co3o4_quench/SHA256SUMS` | SHA-256 of all 27 `.dat` files (`shasum -a 256 -c SHA256SUMS` checks them; `test_d1b_co3o4_quench.py` too) | Written for this repository | As the files it lists |
| `cif_dictionaries/cif_core.dic` | CIF core dictionary **3.3.0** (DDLm 4.2.0, dated 2026-09-22, released 2026-10-01, doi:10.1107/cifdic_core_3.3.0). 963 364 bytes. The registry test (`tests/test_cif_registry.py`, WP-1319) reads it to check every tag the CIF writers emit. | COMCIFS `cif_core` at tag `v3.3.0`, commit `676c7b9a64428d2e03e1f4645b014753af9f69be`, fetched 2026-10-09 through `gh api` and committed byte for byte; SHA-256 `5a898bed8ab8ece0d9a5983e1b665e32838e7de90a1f72a948a77b411774f899` | CC BY 4.0, stated in the file's own `SPDX-License-Identifier` line; attribution in `ATTRIBUTION.md` § Format specifications. Test data only — nothing enters the wheel |
| `cif_dictionaries/cif_pd.dic` | Powder diffraction dictionary **2.5.0** (DDLm 4.2.0, dated 2026-09-08). The commit before the 2.5.1 development stubs; the repository carries no release tag. 521 442 bytes. | COMCIFS `cif_pd` (formerly `Powder_Dictionary`) at commit `d644af4e4b03919d7445dae611174f19c91def63`, fetched 2026-10-09 through `gh api` and committed byte for byte; SHA-256 `de60c8e4090b74195453c25f5f8eeaf407565f48ffce9ce060d20b900c98b658` | CC BY 4.0, stated in the file's own `SPDX-License-Identifier` line; attribution in `ATTRIBUTION.md` § Format specifications. Test data only — nothing enters the wheel |
| `cif_dictionaries/cif_mag.dic` | Magnetic dictionary **0.9.9** (DDLm 4.2.0, dated 2026-07-16). No release tag; the latest commit to the file. 199 490 bytes. | COMCIFS `cif_mag` (formerly `magnetic_dic`) at commit `ceff944841974849ba03dd627826997040a003b4`, fetched 2026-10-09 through `gh api` and committed byte for byte; SHA-256 `d0e4787b8449885050930bc29bc8ca840a6692547954b75e9b35745521cba180` | CC BY 4.0, stated in the file's own `SPDX-License-Identifier` line; attribution in `ATTRIBUTION.md` § Format specifications. Test data only — nothing enters the wheel |
| `cif_dictionaries/ddl.dic` | The DDLm attribute dictionary **4.2.0** the three above conform to (dated 2026-06-29). 108 786 bytes. | COMCIFS `DDLm` at tag `v4.2.0`, commit `525e587463c8a649c2d8d3798a766eef89d3f066`, fetched 2026-10-09 through `gh api` and committed byte for byte; SHA-256 `ffcd5d2794d37dedb0fbfad0432b340b52b32f57e77c97158ac48193504b5062` | CC BY 4.0, stated in the file's own `SPDX-License-Identifier` line; attribution in `ATTRIBUTION.md` § Format specifications. Test data only — nothing enters the wheel |
| `cif_dictionaries/templ_attr.cif` | Attribute templates **2.0.0** (dated 2026-04-20), the file `cif_core.dic` imports 323 definitions' attributes from as doi:10.1107/cifdic_attr_2.0.0. 37 229 bytes. | COMCIFS `Attribute_Templates` at tag `v2.0.0`, commit `a4d4fa550aad5a9133c68b9772fb6b77588894d5`, fetched 2026-10-09 through `gh api` and committed byte for byte; SHA-256 `3003aecf806300cf46a6541eb3a93bde88e6245dbac5f3469f3798a78a9d281b` | CC BY 4.0, stated in the file's own `SPDX-License-Identifier` line; attribution in `ATTRIBUTION.md` § Format specifications. Test data only — nothing enters the wheel |
| `cif_dictionaries/templ_enum.cif` | Enumeration templates **1.4.9** (dated 2026-04-20), imported 37 times by `cif_core.dic` as doi:10.1107/cifdic_enum_1.4.9. 140 908 bytes. | COMCIFS `Enumeration_Templates` at tag `v1.4.9`, commit `7bd3b60895b20f4e9db22c169d1970767b1bb491`, fetched 2026-10-09 through `gh api` and committed byte for byte; SHA-256 `5b224ae7d4e360e049459644cbe662a7995fb2d4213b313bff94e5d137959184` | CC BY 4.0, stated in the file's own `SPDX-License-Identifier` line; attribution in `ATTRIBUTION.md` § Format specifications. Test data only — nothing enters the wheel |

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
patterns improve brucite's Rwp from 18.62 % to 17.84 % with ΔBIC = +22.4 at
N/f² (+592 at raw N) and still drive σ²(M) negative on 7 of 43 reflections
(1.6.0 tree). Corundum: Rwp 14.37 %, ΔBIC = −18.6 at N/f², Layer-1 anisotropy 1.80× and `detected=False`. Re-measure both
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

**macOS 27.0.1 re-baseline (2026-10-02)**: `toy_anomalous` only.  Its last capture
(WP-1121, 2026-08-22) ran under macOS 26.5.1.  The machine moved to 27.0.1 at
00:48 that day, and the state then failed on every tree tried.  That includes `0da9dd80`, the commit that
captured it, so the code did not move.  Numpy did not move it either: 2.5.1
and 2.5.2 diverged identically.  `theta` and `y_calc` stayed bit-identical.
`residual` moved on 162 of 3350 elements, by at most 2.3e-13 of its largest
value.  `jacobian` moved on 1541 of 43 550, by at most 1.3e-13.  Those two
keys read the state's synthetic observed pattern and `y_calc` does not, so the
moved bits enter there.  That pattern is evaluated at a perturbed cell.  The
other nine states reproduced bit-for-bit and were not re-captured.  The size
matches the system-maths-library drift measured below.  Which function changed
was not identified.

**WP-1928 re-baseline (2026-10-08)**: `toy_anomalous` only, on macOS 26.7.1 arm64
(Python 3.12.13, numpy 2.5.2).  The 27.0.1 capture above failed on a
macOS 26 machine (#760), for the same reason it was taken: the state simulated
its observed pattern at run time, through libm.  That pattern is now read from
`toy_anomalous_y_obs.npy` (row in the table at the top), so the golden no longer
depends on the system maths library through its input.  The state's own
`y_calc` still does, as every other state's does.  Against the 27.0.1 file,
`free_paths`, `theta` and `y_calc` are bit-identical.  `residual` moved on 162
of 3350 elements, by at most 1.58e-11 (2.3e-13 of its largest value), and
`jacobian` on 1541 of 43 550, by at most 4.14e-9 (1.3e-13).  That is the
2026-10-02 move in reverse, with the same element counts.  Two separate
processes reproduced every key bit for bit.  The Linux policy below is
unchanged: `y_calc` itself differs there, so the gate still skips.

**WP-1938 re-baseline (2026-10-11)**: all ten states, on macOS 26.6.2 arm64
(Python 3.12.10, numpy 2.5.4).  In that venv, main's code at `12db370b`
reproduces every old file bit for bit, so the move is the code's.  The table now
refines every entry in physical units.  `theta` moved on each former softplus
entry by exactly the softplus map.  A Lorentzian width stored at 0 sat at 1e-12
under softplus and now sits at 0, which moved `y_calc` by up to 1.2e-11 of its
largest value (`srm660c`, `toy_rich`, `toy_stephens`).  The other states moved
by at most 1.3e-15, the round trip through softplus.  A former softplus column
is now the physical one, so the old column equals the new one times expit(u).
That holds to finite-difference truncation, at most 3.7e-6 relative, on every
column but three.  Those three are the widths at 0: `profile.y` in `srm660c`
and `toy_rich`, and `lor_size` in `toy_stephens`.  Against a
Richardson-extrapolated one-sided derivative, the old columns were off by 7 %,
45 % and 14 %, and the new ones by 1.1e-6, 2.8e-8 and 1.6e-8.  The old step in u
moved such a width by about 1e-20, below rounding.  `lebail_intensity` and
`pawley_x0` moved by at most 5.8e-16 relative, since both are seeded from the
decoded values.

**WP-2044 re-baseline (2026-10-24)**: `srm660c` and `toy_rich`, the two states
that free extinction, on macOS 26.6.2 arm64 (Python 3.12.10, numpy 2.5.4, scipy
1.18.1). Sabine's Laue factor became e^(−x)·[I₀ + I₁] in place of GSAS-II's
series and asymptote. In `srm660c` only the extinction column of `jacobian`
moved, by 9.3e-6 of its norm, and every other key is bit-identical. In
`toy_rich` the extinction column moved by 1.2e-5 of its norm. Every other column
moved by at most 4e-13 of its own norm, and `y_calc` and `residual` by at most
4.3e-16 of their largest value. Both states hold extinction at or near 0, where
the column's step is 1e-9 µm² (`FLOOR_SEEDS`' size) and x is about 1e-10. The
difference quotient then subtracts two numbers within 1e-10 of 1, so it carries
the function's own rounding: about 1e-6 for scipy's `i0e`, against 8e-8 for the
old polynomial. At x ≥ 1e-3 the two slopes agree to the last digit. The other
nine states reproduced bit-for-bit and were not re-captured. Both recaptured
states pass twice over.

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

The manual's background-peak section (now `docs/docs/concepts/parameters.md` § Humps) used to rest on a 60 K
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

Three further files corroborate it and **one of them is now committed** — run
4736 arrived from the maintainer on 2026-09-17 and is `11BM_Kapton.xy` in the
table above, so the blank's leg of this argument is regenerable here rather than
cited. The other two are still cited by provenance, as they were — they are
cited by provenance, as the `11BM_LaB6_cBN_mg2044.xye` row cites its TOPAS
references:

| Established | Evidence |
|---|---|
| The hump is the container, not a missed reflection | APS 11-BM **run 4736**, header `Chemical formula = empty Kapton capillary (Kapton)`, `Calibration file = feb10/11bmb_4733.calib`, `Calibrated wavelength = 0.412225`, collected 11 Feb 2010 — the same February 2010 beamtime as run 4918, with the sample taken out. Published on 11-BM's Standards Data listing (`wiki-ext.aps.anl.gov/ug11bm/index.php/Standards_Data`), recovered through the Internet Archive by the same route as the `qarr/*.prn` files. Fitted **outside this package** (numpy Chebyshev + scipy least-squares, weights from the file's own σ column) over the committed pattern's exact 1.997–49.996° range: Chebyshev-3 + one Gaussian gives χ²ᵣ = 1.125 on 48 000 channels, position 4.2417(111)°, FWHM 6.153(23)°, where Chebyshev-3 alone gives 5.33 and it takes fourteen polynomial terms to match the six-parameter fit. Cross-**code** and cross-**scan**, which is what the old example could not offer. **Committed since 2026-09-17**, and that fit reproduces on the committed bytes to every digit recorded here, which is what identifies the file as run 4736 |
| The hump is not the beam or the air path | APS 11-BM's published `background/11BM_background_air_scatter.xy`, header `11-BM Background, No sample - Air Scatter Only`, one hour, run cycle 2009-2, λ 0.458735 Å. Binned over 2–50° it decays strictly monotonically with nothing localised anywhere. Note the **different wavelength**: a d = 4.73 Å halo would sit at 5.56° in this scan rather than 4.98°, so the control is quoted as "no localised feature anywhere", which is wavelength-free, rather than as "nothing at 5°" |
| What the feature is | The blank's envelope maximum is at 4.98° 2θ, which at 0.412225 Å is d = 4.74 Å, Q = 1.33 Å⁻¹ — the polyimide amorphous halo. Quoted as an envelope reading of the data, not as a literature value |
| Why the *refined* centre is 4.18° and not 4.98° | A symmetric Gaussian over 2–50° also absorbs the residual direct-beam rise a 3-term Chebyshev cannot reach, so it is pulled low. Measured, not asserted: give the polynomial three more terms and the same peak relaxes to 5.245(32)° and narrows from 5.57(22)° to 1.94(8)°. The manual carries this caveat in the prose and quotes the envelope for the halo and the fit for the model |

**What that pattern still is, and is not.** Two measurements taken on it are
still cited in this package — in `refine.py` for the held capillary offset and
in `strategy/staged.py` for a stage-ordering effect — where the claim is about
this code's behaviour on a pattern rather than a physical result checked against
an outside source. Those citations keep the measurement and name no specimen,
which is root CLAUDE.md's rule for a private file. The pattern is **no longer**
the background-peak worked example, and no number in that section now comes from
an unpublished fit.

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
**v1 is refused**: no description of it exists.

**v2 (`RAW2`) has one real file, and it is not here** (WP-2059, issue #1164).
Durham's TOPAS tutorial file `Pbso4.raw` (24 328 bytes, SHA-256
`80e990bc360a3628dca6b0efca3ce03278b00136c4183c2088c0d52041a018d7`) is the
PbSO₄ round-robin X-ray pattern of Hill (1992), converted to v2 in 1997. Its
page states no licence, so it is registered in `tests/local_data.py` as
`durham-topas/pbso4` and fetched to the local-only data root
(`python -m tests.local_data durham-topas/pbso4`). `test_readers.py` reads it
where it has been fetched and skips otherwise, pinning 6001 points and every
count. The pin is stated against this directory's `gsas2_pbso4.gpx`, whose X-ray
histogram is the same pattern: the two agree at 5998 of 6000 common points,
the RAW file reads 278 and 276 where the gpx has 275 at 143.375° and 153.725°,
and the RAW file has one more point, 368 counts at 160°. Everything else about
v2 is tested on files `tests/writers_xrd.py` packs from a literal offset table,
with the gpx's counts.

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
place the reader's design is checkable. The files are the maintainer's
unpublished research data, so each is cited here and in the reader as
`archive file N`. The map from number to file is in the private
`yue-here/rietx-corpus-map`.

**One file is committed since #131**: `srm1976a_corundum_xpert_pvii.inp`, the
data owner's own refinement of `srm1976a_corundum_xpert.xy`, contributed with
the pattern so that the spherical-harmonics texture can be compared with
TOPAS's coefficients term by term. It is a reference for that acceptance
(`test_acceptance_srm1976a_texture.py` reads three coefficients and two
agreement indices from it by pattern match), not a reader fixture: no test
passes it to `read_topas_inp`, and the counts above are unchanged by it.

Reader outcome over the 606-file catalogue (`read_topas_inp` then
`projects.topas.to_structure`,
measured 2026-08-27): **516 parse, 367 build a `Structure`**, and **7 refuse at
the encoding gate** (an ASCII-range UTF-16 export whose NUL bytes survive the
decode — guessing the byte order is a repair the reader will not make in
silence). The gap between 516 and 367 is not error: it is Pawley/indexing-only
inputs with no structural phase, `STR(...)`-macro phases the reader refused by
name until WP-1433 (which reads them; its PR records the re-measured counts), magnetic space groups it has no model for, and the stated-but-unreadable
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
| A `str` block ends at the **next block opener of any kind**, not at the next `str` — otherwise a phase absorbs the neighbour's cell, `scale` and `weight_percent` | `archive file 6`: a nameless `str` block used to arrive named `"CaO"` with `scale 1.0`, both read off the `hkl_Is` block below it |
| Which cell macros a real file actually **uses**, and with what spellings of the value in the argument. The *coupling* each one states is a specification fact and is cited per macro in `ATTRIBUTION.md`; the archive's job here is incidence, and it is the reason `Trigonal` is implemented at all | live-text incidence over the 618 swept files: `Hexagonal` **15**, `Cubic` **13**, `Trigonal` **4**, `Tetragonal` **1**, `Rhombohedral` **0**. Read off `Cubic(@ 4.15692`)` (`archive file 8`), `Tetragonal(@ 4.500000`, @ 2.900000`)` (`archive file 11`), `Hexagonal(@ 3.500000`, @ 12.000000`)` (`archive file 12`), `Trigonal( 12.500000, 37.500000)` (`archive file 18`). `Cubic` also appears with an equation for its argument — `Cubic(=SFOx_cub;)` (5 SFO files), `Cubic(=a1;: 5.431500)` (the `archive file 9` series) |
| `Rhombohedral`'s argument order is settled by the reference and **not** by this archive, which is why it is worth writing down that the archive is silent on it | **0 files** in live text; **2** carry it inside a `'` comment (`archive file 17`'s template, `'Rhombohedral(@ #, @ #)`). `Orthorhombic`/`Monoclinic`/`Triclinic` occur in **0 files**, commented or not, and are not cell macros of this format — they stay refused by name |
| A **multi-`occ` single site** (one `site` token, several species/occupancies on one line) does **not** occur in this archive — the mixed-occupancy case is spelled two-line instead (`site Si1_Si … occ Si 0.8` / `site Si1_Ge … occ Ge 0.2` sharing coordinates), which already worked | 0 files with two `occ` on one `site` line; the one-grammar occ reader is latent cover, not a live fix here |
| The anisotropic displacement tensor appears in **three spellings**, the third being a positional six-slot `ADPs { … }` brace block | `adps`/`ADPs`: **6 files** (`archive file 2`, `archive file 24`, `archive file 3`, `archive file 28`, `archive file 22`, `archive file 23`); a live `u11` token: **1 file** (`archive file 22`, the ZrW₂O₈ neutron fit the brace spelling was read from) |
| The tensor's **unit convention** — `u_ij` read as U^ij in Å², the CIF `_atom_site_aniso_U_ij` convention, so the numbers transfer with no 8π² conversion (`_ADP_KEYS`) | **Not measured against TOPAS's own output**, which is what § What generalises to the next foreign format asks for *first*, and which needs a run this tree cannot make. What stands behind it is the field names plus one magnitude argument (`test_a_stated_adp_tensor_is_carried_on_the_model`): at U = 0.013 the isotropic equivalent is B = 8π²·0.013 = 1.03, an ordinary B, where reading the same number *as* B would put the site at U = 0.00016. That separates U from B; on its own it does not exclude a differently normalised U. Worth settling by whoever holds the archive, and cheap to — `archive file 22` is a published ZrW₂O₈ neutron refinement whose tensor can be read against the literature directly. A wrong answer here would be **silent**: `ADP_NOT_POSITIVE_DEFINITE` cannot catch it, since scaling a positive-definite tensor by a constant leaves it positive-definite |
| An edge coupled to another edge (`b`, `c` set from `a`, the tetragonal/cubic case) **does occur**, written with TOPAS's `Get()` built-in, and is **read** — resolved against the cell keys already read for the same phase, with the file's symbol table as the outer scope. It used to refuse, costing the whole file each time | `b =Get(a);` / `c =Get(a);` in **4 files** in live text (`archive file 26`, `archive file 29`, `archive file 30`, `archive file 31`), all four of which now read *and* build. A **fifth** (`archive file 20`) writes the same line inside an `#ifdef phase_2_` the pre-processor kills, so a raw grep says 5 and the live text says 4 — which is the conditional resolver being load-bearing rather than a discrepancy. The bare `b = a;` form occurs in **0 files** |
| The **other** coupled-edge idiom — two edges naming one declared parameter (`prm edge @ 5.0` with `a = edge; b = edge;`) — is read the same way and reported the same way, and the parameter's refine flag is carried onto every edge that resolves through it. Reading only the number made a refined cell arrive held, so a file that refined its cell and one that declared a constant built byte-identical models | **Not measured on the archive**, which is not on this tree: the construct is derived from Technical Reference 2.2 (`prm b1 0.2` declares a parameter that will be refined, `prm !b1 0.2` the held form) rather than from an incidence count, and the rows above are what an incidence count would look like. Worth measuring by whoever holds the archive — the `Get()` row's shape is the shape that answer should take |
| The cells that coupling recovers are checkable against the phases themselves, which is the corroboration the citation cannot give | cBN in `archive file 26` reads a = b = c = **3.6151 Å** (`F-43m`, literature 3.615) and PdO in `archive file 31` reads a = b = **3.0424**, c = **5.3356** (`P42/mmc`, literature 3.043/5.336). A coupled edge takes **no** refine flag of its own — it states an equation, so only the edge it names is refined |
| The **scale convention transfers unchanged** — TOPAS's `scale`/`weight_percent` carried into rietx's Hill & Howard reproduces the file's own quantitative phase analysis, with no systematic 8π²-class factor hiding in it | The weight-percent oracle: of 174 files stating `weight_percent` over ≥2 built phases, the **139 whose stated values sum to 100 ± 2** (i.e. can be one refinement's answer) give a median per-file max \|ΔW\| of **0.0004 wt%** |

The oracle's own limit is recorded with it: three files above 1 wt% are
hand-edited mid-refinement (`archive file 19`, ±10.3 — stale `scale` values that
happen to still sum to 100), and 35 files whose stated sums are 497–656 % are
multi-dataset templates and stale batch files, excluded because their numbers
are not from one converged state. Both classes are named in the round-five sweep
JSON, not hidden in the median.

#### `for` loops — measured against TOPAS v6 (2026-10-01)

The reference says a `for $object_type { … }` loop "expands its body once for
every existing instance of the given object type" and stops there.
`expand_for_loops` needs the rest, and it was measured on TOPAS v6 as a
**black box** on synthetic files only: a flat 20–60° pattern, Cu Kα1, a
Pm-3m Ni phase at a = 4 Å (100 at 22.20°) or 5 Å (110 at 25.17°), and a loop
body setting `th2_offset = 0.5;`, so a reached phase's peaks move by +0.50°.
Positions were read off each dataset's `Out_X_Ycalc` file.

| layout | result | reading |
|---|---|---|
| two `xdd`s, then `for xdds { th2_offset; for strs { the whole phase } }` | both datasets built and shifted | reaches every dataset above it |
| the same loop **above** both `xdd`s | `Error loading sstring_in at xdds` | nothing above → TOPAS refuses |
| `xdd`, loop, `xdd` | the first shifted, the second not | "existing" = opened above the loop |
| two `xdd`s × two `str`s, `for xdds { for strs 1 to 1 { … } }` | in **each** dataset its first `str` shifted | the range counts within one dataset |
| the same, `for strs 1 to 1` (or `for strs`) at the end of the file | only the **last** dataset's phases shifted | a bare `for strs` reaches the dataset it is written in |
| an `xdd` with no `str`, `for strs { … }`; or `for strs 2 to 4` over two | `Error loading sstring_in at strs` (`invalid index`) | nothing to reach → TOPAS refuses |
| `hkl_Is` (a = 4) then `str` (a = 5), `for strs 1 to 1` | the `str` shifted, the `hkl_Is` not | `strs` counts `str` only |
| three `xdd`s, `for xdds 2 to 3` | the second and third shifted | `for xdds N to M` is 1-based over datasets |
| phases written out, `th2_offset` in dataset 1 only (control) | dataset 1 shifted, 2 not | the read-out can fail |

Over the 468 `.inp` files of the archive mirror it was measured on (macOS
metadata stubs excluded): **54 files
go from refused to read and none the other way**; 44 of the 68 files carrying a
live loop open their datasets with `TOF_XYE(...)`, which is why that macro is a
dataset opener. Every one of those is a time-of-flight file, and its banks are
then refused at build by name (issue #193) while a constant-wavelength dataset
beside them still builds: 13 more datasets build than before.

### FullProf `.pcr` — six real files, none of them vendorable

`io/projects/fullprof.py` reads a FullProf refinement *control* file, the same
kind of source as the `.inp` above: the solved model rather than a pattern. It
was written and settled against **six real `.pcr` files** in the same private
archive, and **none is vendored**, for the same reason and under the same
`ATTRIBUTION.md` reasoning — they are a collaborator's and an owner's working
research inputs under no uniform, redistributable licence. A format's *facts*
may be read from them; the bytes may not be shipped.
`tests/test_projects_fullprof.py` synthesizes every fixture inline, with
synthetic values rather than the files' own. The six are cited as
`corpus file 1` to `6`, and the map from number to file is in the private
`yue-here/rietx-corpus-map`. This section
is therefore the only place the real-file evidence is checkable, which is what
`io/CLAUDE.md` § Adding a format, step 1 requires of a format with no vendorable
file.

The six, and what each settled:

| file | what it established |
|---|---|
| `corpus file 2` | The **line grammar**, read off `:4`/`:5` (nineteen fields) and `:7`/`:8`. Also the `ATZ = 963.5` that forced `_PHASE_INTEGER_FIELDS` — `cur.ints()` over the whole phase-control line would refuse every real file, because `ATZ` and `Pr3` are quantities, not counts. And a **stale λ in the refinable-λ slot** |
| `corpus file 6` | The soft-moment constraint block (`SoftMomentConstraint`), and that a magnetic phase present alongside nuclear ones must **refuse** rather than return the nuclear subset silently |
| `corpus file 3` | The two **single-atom coordinate ties** that must *not* refuse: O1's x to its y (parameter 56) and O2's (parameter 57), on `P 42/m n m`'s 4f site, which rietx's own `dof.0` already reproduces. This is the file that makes the tie check re-derive a site's DOF count instead of refusing every shared codeword |
| `corpus file 1` | A second magnetic layout (two magnetic sites), and the **lying phase-number comments** — a `.pcr`'s inline `!Phase No.` text disagrees with the block order, so the reader counts blocks and never trusts the comment |
| `corpus file 4` | `Aut 1`; the `Jbt` header rename; O1's **negative `Biso` = −0.67266 Å²**, a real FullProf outcome that rietx's zero bound cannot clamp without changing every high-Q intensity, hence a refusal rather than a repair; and the cubic **`a = b = c`** cell tie (parameter 40) plus the `F D -3 M` → `F d -3 m:2` origin choice |
| `corpus file 5` | The **`NPATT 6` refusal**. A joint refinement over six patterns is a different layout throughout, and which bank's resolution function to return is a question the file does not answer. This is the only one of the six that does not read |

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

### GSAS-II `.gpx` — 34 tutorial projects, and the two that ship

`io/projects/gsas2.py` reads a GSAS-II project: the phases, the histograms, the
refine flags and the constraints. Unlike the two formats above, this one has a
**public corpus with a redistribution grant** — the GSAS-II tutorials repository
under the GSAS-II Open Source License (UChicago Argonne, royalty-free use and
redistribution with the notice) — so for once the evidence is checkable by
anyone, and two files are vendored rather than none.

All 34 tutorial projects were read before the reader was finished, and the
numbers below are that pass (2026-09-16, `[dev]` venv, darwin/arm64). They are
here rather than in the module because they are facts about a corpus, not about
the code: a later corpus moves them.

Re-fetching the corpus costs one blobless clone and about a minute (measured
2026-09-16, 103 MB on disk for the 34 files): clone
`AdvancedPhotonSource/GSAS-II-tutorials` with `--filter=blob:none
--no-checkout`, then `sparse-checkout init --no-cone`, `sparse-checkout set
'*.gpx'` and `checkout`. A plain clone pulls the tutorials' image and neutron
data as well, so the blob filter is written down here rather than left to
whoever needs the corpus next.

| measured across the 34 | number |
|---|---|
| top-level tree items | 195 `PWDR`, 4 `IMG`, 4 `HKLF`, 3 `Sequential results`, 1 `Sequential peak fit results`, and the six singletons every project carries |
| histogram types | 99 `PNT` (time of flight), 80 `PXC`, 16 `PNC` |
| phases | 46: 40 nuclear, 6 magnetic — and **10 of the nuclear ones carry `magPhases`**. That is not evidence of a magnetic model (issue #606): on the five public projects checked that carry it, the value is one of the project's own histogram names and the project holds no magnetic phase |
| atom refine flags | `''` 270, `XU` 155, `U` 7, `UM` 4, `M` 1, and 2 written as a single space |
| displacement | 313 isotropic sites, 126 anisotropic |
| background functions | 114 `chebyschev-1`, 80 `chebyschev`, 1 `log interpolate` |
| constraints | 93 rows: 86 equivalences, 4 holds, 3 constraint equations |
| distinct pickle globals | 11, of which **7 are outside the allow-list proposed on issue #234** |

Four of those settled a decision, and each would otherwise have been a guess:

- **The allow-list cannot come from one archive.** Issue #234's was measured on
  146 private projects that are all plain CW powder Rietvelds, and it holds
  `numpy.ndarray`, `numpy.dtype` and `_reconstruct`. The public corpus adds
  `numpy.core.multiarray.scalar` (268 uses), `_codecs.encode` (12 files), the
  masked-array pair (19 files), `copy_reg._reconstructor` with
  `__builtin__.object` (6 files), and GSAS-II's own `G2VarObj` (10 files) and
  `ExpressionObj` (1). Refusing the last two by name would refuse **10 of 34
  real projects entire**, which is what the inert stand-in exists to avoid.
- **A python-2 rebuild name is not a python-2 file.** One of the six carrying
  `copy_reg._reconstructor` was written by python 3.6.6, so the correlation a
  reader might have reached for does not hold and the names are admitted
  unconditionally.
- **The sniff cannot be the magic bytes.** 11 of the 34 carry no pickle protocol
  header at all, so the test is "opens as a pickle **and** names a GSAS-II tree
  item", and one of those 11 is vendored so the path stays exercised.
- **`Rvals['GOF']` is the square root of reduced χ².** On all six projects that
  state `chisq`, `Nobs` and `Nvars` together it matches `sqrt(chisq/(Nobs-Nvars))`
  to six figures. This repo's `.EXP` reader claimed the opposite convention for
  GSAS-II in a corroborating clause, which is now corrected.
- **A phase states its setting in its operators, and 4 of the 46 need it to**
  (WP-1118, 2026-09-16). Those four write a bare two-setting symbol — three the
  `F d d d` of CuCr₂O₄ (`AllDataStart`, `SeqFit`, `SingleHistFit`), one the
  `I 41/a m d` of Mn₃O₄ (`Magnetic-V`, vendored as `gsas2_mn3o4_setting.gpx`) —
  and in **all four** the file's own `SGOps`/`SGCen`/`SGInv` reproduce origin
  choice **2**, where gemmi reads the bare symbol as choice 1. The other 42
  reproduce the setting their symbol names, so the operator read agrees with the
  symbol wherever the symbol is unambiguous and corrects it wherever it is not.
  What choice 1 costs is not uniform: the spinel becomes Cu₂CrO₄ (ZMV 1 093 848
  against 1 041 875, 5.0 %), while Mn₃O₄ keeps its formula and exchanges its two
  Mn sites, which moves 56 % of the calculated intensity after the best common
  scale and no composition check can see.

And three limits of the corpus are recorded rather than smoothed over:

- **Not one of the 195 histograms has an excluded region.** Every `Limits` is
  two pairs. The `Limits[2:]` layout is GSAS-II's own statement in
  `GSASIIstrIO.py` rather than a guess, but no real file here exercises it, so
  `test_projects_gsas2.py` writes one that does. The same is true of a Pawley
  phase (`doPawley` is False in all 46) and of a negative occupancy.
- **`Z` is zero in every constant-wavelength histogram that states it** (95 of
  them). So the corpus says nothing about GSAS-II's constant Lorentzian term
  beyond that nobody in it used one — which is the evidence behind refusing a
  non-zero `Z` on the writer rather than growing a schema field for it.
- **19 of the 34 build a structure; 15 refuse by name** — 7 for a negative
  `Uiso`, 5 for anisotropic sites, 2 for stating no phases at all (a cluster
  analysis and a sequential peak fit), 1 for a Le Bail phase with no sites.
  A corpus of teaching files is *meant* to contain mid-refinement states, so
  that ratio is a property of the corpus and not a defect rate.

### GSAS-II `.instprm` — 12 tutorial files, and the two that ship

The same corpus one directory over, fetched the same way with `'*.instprm'` in
place of `'*.gpx'` (a blobless clone, seconds rather than a minute). Measured
2026-09-16, `[dev]` venv, darwin/arm64, over all 12 files and the 27 banks they
hold.

| measured across the 12 | number |
|---|---|
| banks | 27: 23 `PNT` (time of flight), 2 `PXC`, 2 `PNC` |
| files stating several banks | 3, each 6 banks, and each writes `#Bank 6` **twice** |
| constant-wavelength files this build reads | 2 of 4 — the other two are refused for a negative `X` |
| files stating `Diff-type`, `Gonio. radius` or a Kα doublet | 0, 0, 0 |

Four of those decided something:

- **A negative width coefficient is the ordinary case, not a corner.** GSAS-II
  bounds none of `U V W X Y Z`; this package's Lorentzian and Gaussian terms are
  softplus-bounded at zero, where `to_internal` clamps a non-positive value to
  1e-12. Both `PXC` files converged to `X` = −0.0978, so reading them would
  answer from a model the file does not describe. Refused by name, which is
  `io/recipe.py`'s rule one format over — and the same reason it was earned
  there, both committed LaB6 references converging to a negative `Y`.
- **A bank number can name two banks.** GSAS-II's own reader takes the
  lowest-numbered bank silently; a quarter of this corpus writes one number
  twice, so `read_gsas2_instprm` refuses a multi-bank file without `bank=` and
  refuses a repeated number outright.
- **The doublet arm has no file.** No `.instprm` here states `Lam1`/`Lam2`, so
  the key names and their order come from the specification and from
  `gsas2_pbso4.gpx`, whose two histograms carry `INSTPRM_CW_SINGLE` and
  `INSTPRM_CW_DOUBLET` exactly — the same vocabulary GSAS-II writes into both
  files. The same is true of `Diff-type` and the goniometer radius.
- **A token format can be checked character for character.** Reading
  `gsas2_hb2a.instprm` and writing it back reproduces all 13 items it states,
  string for string. The `.EXP` writer had to compare its cards against
  `FAP.EXP`'s own spelling by eye for the same class of check, because a field
  read by column can say something to Fortran that `float()` does not see.

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
| `SH/L` | (S+H)/L | `axial_sl` = `axial_hl` = SH/L / 2 | **Adopted, not measured** — at SH/L = 5e-4 on 0.027° peaks the split moves the calculated profile by 2.7e-4 of its range, against a bar of 1e-3 (see `test_recipe.py`; before #774 the fixed value drew no axial quadrature and the difference was exactly 0). That is a measured size, not a claim about noise: this README has no counting-noise figure for the pattern to compare it with |
| `Zero` | ✗ | — | **Refused when non-zero.** Upstream states the unit twice and disagrees with itself: `easydiff/conversions.py` says centidegrees, `config_loader.py` says "degrees 2theta". Every committed recipe has `Zero = 0`, where the readings coincide |
| `Z` | centideg constant Lorentzian | — | Dropped when fixed at 0 (`RECIPE_FIELD_DROPPED`), refused otherwise: rietx's Lorentzian has no constant term |
| `Itth_weights` | 1/σ² | `PatternData.sigma` = 1/√w | Confirmed against `easydiff/conversions.py:crop_and_sigma` |
| `fit_range` | °2θ, **inclusive** both ends | `two_theta_limits` | Same source |
| `Uiso` | Å² | `biso` = 8π²·Uiso | Direct |
| Chebyshev coefficients | GSAS-II domain | count and `refine_flag` carried; **coefficients re-seeded** | The two codes scale the Chebyshev domain differently; carrying the numbers would be a wrong start dressed as a right one |

## Philips/PANalytical pattern formats (WP-1407)

### `qarr/*.rd` — the original logged files behind patterns already in this tree

The IUCr CPD round-robin kit publishes every sample in **seven** format columns,
and one of them is headed *"Binary Philips RD format (Original logged files)"*.
So the `qarr/*.prn` patterns committed above are a **conversion** of a Philips
`.rd` original that the same page still serves, and every `.prn` here is
therefore an independent value oracle for the `.rd` reader. Retrieved
2026-09-13 from `www.iucr.org/__data/iucr/powder/QARR/philips.zip` (28 files)
and `.../xda.zip` (27 files), through a browser session, since the site sits
behind a Cloudflare challenge that refuses `curl` and plain headless Chromium
alike.

The archive holds **28** files: 21 of 14752 bytes (7251 points, 5–150° 2θ) and 7
of 9752 (4751 points, 5–100°, the pharmaceutical samples), all logged 19 Dec
1997 – 20 Jan 1998. **16** have a `.prn` counterpart committed here. Two are
committed as fixtures; the rest stay out of the tree and only their measurements
are recorded below.

**The header layout, measured off all 28 files.** Offsets are specification
facts (merger, not expression) and were read from the bytes first; the
`ATTRIBUTION.md` row records which independent descriptions corroborate each.

| offset | type | meaning | how established |
|---|---|---|---|
| 0 | 4 bytes | magic `V3RD` (or `V5RD`) | all 28 files; both descriptions |
| 4 | text | `Philips Analytical X-Ray B.V.`, NUL-padded | all 28 |
| 44 | text | `PC-APD, Diffraction software`, NUL-padded | all 28 |
| 84 | int8 | diffractometer code; **3 = PW3710 based system** | all 28 read 3, and the kit's own prose says "Philips 3020 Goniometer with **PW3710** Controller" |
| 85 | int8 | anode code; **0 = Cu** | all 28 read 0; prose says "Copper … X-ray Tube" |
| 86 | int8 | focus code; **3 = LFF** | all 28 read 3; prose says "Long Fine Focus" |
| 94 | 3 × float64 | λα1, λα2, α2/α1 ratio | all 28: 1.540562 / 1.54439 / 0.5 |
| 130 | uint16 | start 2θ × 200 | all 28 agree with the float64 at 222 |
| 132 | uint16 | end 2θ × 200 | all 28 agree with the float64 at 230 |
| 136 | uint16 | **maximum stored value** | equals `max(data)` in all 28 — not in any published description, found here |
| 138 | 8 bytes | file name (`CORUNDUM`) | all 28 |
| 146 | 20 bytes | sample identification (`CPD RR Corundum`) | all 28 |
| 214, 222, 230 | 3 × float64 | step, start 2θ, end 2θ | all 28 |
| 250 | uint16[] | the intensities | `len(file) == 250 + 2·n` in all 28 |

The three enumerated codes at 84/85/86 are worth the row on their own: the kit's
prose states the controller, the anode and the focus type independently, and all
three decode correctly out of the published code tables. That is a check of the
*tables*, not just of one file.

**The intensity encoding, which is the whole reason this format can go wrong
quietly.** The stored `uint16` is not a count. It is
√-compressed, and the count is recovered as

```
counts = (v * v) // 100
```

Read raw, a `.rd` file yields a profile with every peak in the right place and
every intensity wrong, which is exactly the failure mode a reader cannot detect
by looking at the result. Four independent confirmations, and one source that
gets it wrong:

- **The committed `.prn` oracle.** `(v*v)//100` reproduces the committed
  pattern **bit for bit on all 7251 channels** for **15 of the 16** files that
  have one.
- **The kit's second converter.** The `.xda` column was converted from the same
  `.rd` originals by a different program (Winfit, against CONVERT for DOS for
  the `.prn`), and it agrees on the *quantity* for **27 of 27** files, differing
  only by rounding to nearest where `.prn` truncates.
- **The arithmetic itself.** Four of the 28 files hold counts above 65535 (up to
  841 076 for `VALINE.RD`), which a raw `uint16` cannot represent at all.
- **xylib** states it: `floor(0.01 * packed_y * packed_y)`, with the comment
  "intensities are packed into 2-byte integers in this interesting way".
- **PyXRD's `rd_parser.py` omits it entirely** and returns the raw `uint16` as
  the intensity. This is the *permissive* description, the one a port would
  legally start from, and it is the defective one. Nothing but a real file
  reveals that.

**`qarr/cpd-1e.rd` is committed precisely because it is the exception.** Its
committed `.prn` matches `round`, not `truncate`, differing from the other
fifteen on 2108 of 7251 channels by exactly one count. The `.rd` bytes are not
in question: `round((v/10)²)` reproduces that `.prn` exactly on all 7251
channels, so one file's `.prn` was made by the rounding converter. The fixture
pins the story so a successor does not "fix" the reader to chase it.

**Two more defects the real files expose in the published descriptions**, both
invisible without a file: PyXRD computes the point count as
`int((max-min)/step)`, one short of the 7251 actually present, and places the
abscissa at `min + step·(n + 0.5)`, a half-step offset that the committed `.prn`
(which starts at exactly 5.00000) refutes. PyXRD also reads the sample
identification as 16 bytes where xylib reads 20; `622M001912-644 clay form` in
PyXRD's own test data splits 8/16 and `CPD RR Corundum` pads to 20, so 20 is the
reading both files support.

**V5 has no file anywhere.** All 28 are `V3RD`. The only V5-specific fact in any
source is that its data begins at offset **810** instead of 250, and the three
places that state it are one description copied: xylib, then PyXRD and
`Yohko/importtool` reproducing xylib's code tables verbatim (the Igor procedure
even carries xylib's `810 - 214 - 8*3` expression). xylib also states that `.sd`
is this format's V5 extension rather than a separate format, which is what lets
the reader claim both by magic instead of refusing `.sd` by name.

**What the fixtures can and cannot prove.** `qarr/corundum.rd` proves the whole
V3 chain end to end against a committed oracle: header, gates, √-decoding and
all 7251 values. `qarr/cpd-1e.rd` proves the rounding story and nothing else.
Neither proves anything about V5, whose only guarantee is the length gate
(`len == 810 + 2·n`, with `n` derived from the header's own angle triple), and
that gate is stated in the reader as the whole of the V5 evidence.

**PyXRD's inline `.rd` test data is a description, never a fixture.** It embeds
what was once a real file inside a Python **raw** string, so every `\00` is
three literal characters and the bytes are mangled. Its visible structure
(magic, the two `PC-APD` strings, the sample name) is readable and was used
above; its values are not. Same class of trap as
`bruker_raw4_scrambled.raw`.

### `.udf` — 56 real files, and one key vocabulary across all of them

PANalytical `.udf` is not a legacy format: a PANalytical Aeris, a benchtop on
sale today, writes it, and the newest file read here is dated 12 June 2025.
Read 2026-09-13 from `yargerlab/Data` (55 files, ASU PANalytical Aeris, 2023 and
2025 vintages) and `SantiagoJulioD/LabAv2` (1 file, an X'Pert). **Licence
checked per repository: all three of the repositories the scoping session found
declare none at all**, so facts are recorded here and no bytes ship. This is the
`.uxd` position, except that `.udf` also has a vendorable structural fixture
(below), which `.uxd` never had.

**Exactly 19 keys, in one order, in all 56 files** — two labs, two instrument
vintages, four scan ranges. `DiffrType` alone varies between them (`?` on the
Aeris, `XPERT` on the other):

| key | fields | what the 56 files hold |
|---|---|---|
| `SampleIdent` | 1 | free text, may be empty |
| `Title1` | **1 to 10** | free text; **commas are ordinary characters in a value** |
| `Title2` | 1 | usually empty; one file carries a goniometer description |
| `DiffrType` | 1 | `?` or `XPERT` |
| `DiffrNumber` | 1 | `1` |
| `Anode` | 1 | `Cu` |
| `LabdaAlpha1` | 1 | `1.540598` |
| `LabdaAlpha2` | 1 | `1.544426` |
| `RatioAlpha21` | 1 | `0.50000` |
| `DivergenceSlit` | 2 | `Fixed, 1/2` |
| `ReceivingSlit` | 1 | `UNDEFINED` — a sentinel, not an absent key |
| `MonochromatorUsed` | 1 | `NO` |
| `GeneratorVoltage` | 1 | `40` or `45` |
| `TubeCurrent` | 1 | `15` or `40` |
| `FileDateTime` | 1 | `03-jun-2025 15:55` |
| `DataAngleRange` | 2 | e.g. `3.00043,  59.99491` |
| `ScanStepSize` | 1 | `0.01086644000` or `0.02626056501` |
| `ScanType` | 1 | `CONTINUOUS` |
| `ScanStepTime` | 1 | five distinct values; **see the caveat below** |

`Title1` carrying up to ten comma-separated fields is the load-bearing one: a
line cannot be split on every comma, only on the first, with the trailing `,/`
stripped.

**The abscissa is reconstructed, and the file states the count twice.** No 2θ
is stored per point. `round((end - start) / step) + 1` reproduces the number of
values present in **all 56 files with no exceptions**, which makes it a genuine
self-consistency gate rather than a guess. The residue
`(end-start)/step - round(...)` reaches 2.5e-4 of a step, so the stated end
angle is not an exact multiple and rounding is the only correct reconstruction.

**The block.** A `RawScan` marker line (all 56), then comma-separated integers,
eight to a line, terminated by `/`. Every intensity in every file is a
non-negative integer.

**`ScanStepTime` is not seconds per step, and must not be used as one.** The
Aeris pairs `ScanStepTime, 18.87` with a filename claiming an eight-minute scan
over 5246 points; 5246 × 18.87 s is 27 hours. This is a PIXcel-class
position-sensitive detector, where the effective counting time per point is not
the drive's dwell. The reader records the value and derives nothing from it.

**The vendorable fixture, and what it proves.** `PyXRD/test_udf_parser.py`
embeds a complete UDF file inline under BSD-2, and unlike its `.rd` sibling it
is **valid as committed**: UDF is plain ASCII with no backslash escapes, so the
raw-string prefix does it no harm. It is plainly synthesised (`Title1,Dat2rit
program`, 33 points falling 8000 to 1). It proves the parse and the block
structure. It does **not** prove the key vocabulary, carrying only **5** of the
19 keys, and it ends its data block `0/` where every real file ends `425,/` — so
it is also the evidence that the comma before the terminator is optional. The
key table above is what the real files prove, and the two together are why the
reader requires only `DataAngleRange`, `ScanStepSize` and the marker.

## WP-2003 family D — the ILL D1B Co₃O₄ quench series, with planted known-bad patterns

`d1b_co3o4_quench/` holds a second real magnetic series whose truth comes from
outside rietx, for WP-2003's chain actions (issue #1150: the
[offer](https://github.com/yue-here/rietx/pull/1150#issuecomment-6388553856) and the
[maintainer's acceptance](https://github.com/yue-here/rietx/pull/1150#issuecomment-6390008133)).
It also holds the series' first planted known-bad patterns, for quarantine and
`on_error`. `tests/test_d1b_co3o4_quench.py` checks that every file reads, that the
bytes match `SHA256SUMS`, that this file names each one, and that the planted
files rebuild byte for byte. No fit runs there.

**The experiment.** Ten Co₃O₄ samples, quenched by submersion in liquid nitrogen
(p. 104104-2) from 300 K, or from 773 to 1173 K in 50 K steps (Fig. 8 and the
files). They were
measured on the ILL two-axis diffractometer D1B at λ = 2.52 Å, in a vanadium can
in a cryostat, from 13 to 16 November 2011. Every sample has a 1.5 K scan. Some
also have a 100 K or 300 K scan:

| Quench (K) | 300 | 773 | 823 | 873 | 923 | 973 | 1023 | 1073 | 1123 | 1173 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.5 K | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 100 K | ✓ | ✓ | ✓ | | | | | | ✓ | |
| 300 K | ✓ | | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ |

- **Names.** `<Q>q` is the quench temperature in K. The heading title gives it in
  °C (`quenched_500` is 773 K) or as `RT` (300 K). **`923q_1p5K_1.dat` was
  `723q_1p5K_1.dat`** until M. W. Gaultois corrected the name on 2026-09-08. It is
  the sample quenched from 650 °C (923 K), as its heading says. There never was a
  723 K sample, and the 923 K sample's 100 K and 300 K scans are the two missing
  from the set.
- **The counts are not raw counts.** Each scan sums several runs (the heading's
  `Run a b>a` line) and is scaled to the monitor, so counts/σ² is about 12, not 1.
  Weight by the file's σ, which `read_pattern` does.
- **`300q-1p5K_1.dat` is a spreadsheet export**, not the instrument's file. It has
  eight tab-separated columns: 2θ, counts and σ as in the others; then the strongest
  count (246 699, on row 1 only); counts divided by it; an empty column; 2θ again;
  and a second normalised trace whose source we could not identify. It has no
  heading, so no temperature metadata, and rietx drops its seven-field first row.
- **The heading's temperature.** The reader takes the first `TEMP` value. For
  `vanadium_can_120K.dat` that value is 330.000, while the second and third
  (120.037, 120.000) and the file name say 120 K.
- **`1173q-300K.dat`'s heading calls the sample `CoO-quenched_900`**. Its 1.5 K
  scan's heading says `Co3O4`. The paper puts the onset of decomposition to CoO in
  air at about 1165 K (TGA, p. 104104-4). It does not report the CoO content of
  any quenched sample, and none is asserted here.
- **The garnet standard is probably not YAG.** The group's instructions for these
  files call it the YAG standard, and so did its file name (`standard_YAG_300K_1.dat`).
  Its heading says `YIG-300K`. Its lines index on a garnet cell of about 12.36 Å
  (our reading of the peak positions, zero not refined) and miss YAG's by about
  1° 2θ. It is renamed `standard_garnet_300K_1.dat` so that nobody calibrates λ
  against YAG with it. Which garnet it is, is left to whoever uses it. It is
  vendored because it comes from the same experiment (run 130058, 15 November 2011,
  same user heading).
- **The vanadium can** (run 129947, 14 November 2011, heading `empty cryostat`) is
  the empty can in the cryostat. Its strongest line is V(110) at 72.2° 2θ. It is
  vendored as the background and V-line reference for the series.
- **λ/2.** The group's instructions give λ/2 = 1.26 Å at 1 % of λ's intensity. The
  paper does not state it.

**Reference values**, each from Sparks *et al.* (2019), the full citation below.
Michael W. Gaultois is a co-author.

| Quantity | Value | Where |
|---|---|---|
| Propagation vector | k = (0, 0, 0): magnetic intensity on (111), (200), (113), (222), (331), (420), no extra lines | pp. 104104-6, -7 |
| Magnetic model | Γ₇ on 8a (BASIREPS labels; basis (x, y, z) + (−x, −y, −z): the two A-site Co antiparallel). Γ₁₀ on 8a and every 16d representation fit poorly, so there is **no B-site moment in any sample** | eqn (5), p. 104104-7 |
| Moment direction, magnetic space group | **not given** (a cubic powder does not fix the direction) | — |
| Ordered A-site moment vs quench T | 2.40, 2.41, 2.45, 2.54, 2.57, 2.63, 2.67, 2.69, 2.70, 2.71 μ_B for 300, 773, 823, 873, 923, 973, 1023, 1073, 1123, 1173 K; error bars ±0.02 μ_B at every point. **Read off Fig. 8; the paper prints no table.** The text gives "2.4 μ_B" up to 823 K and 2.71 μ_B at the top | Fig. 8, p. 104104-7 |
| T_N | ≈ 40 K, **stated without a measurement of its own** ("the low Néel temperature ≈40 K") | p. 104104-2 |
| Nuclear model | F d -3 m, origin choice 2: Co²⁺ on 8a, Co³⁺ on 16d, O on 32e (u, u, u), the same group above and below T_N. The magnetic refinement starts from the structure of W. L. Roth, *J. Phys. Chem. Solids* **25**, 1 (1964), doi:10.1016/0022-3697(64)90156-8 | p. 104104-2 |
| Nuclear numbers | **No neutron cell, u or ADP is given for any quench.** The nearest published values are from XRD on a slowly cooled sample at 298 K (Co Kα, not these specimens): a = 8.0838(1) Å, u = 0.2632(3) | Table I, p. 104104-6 |

**How the moments were read.** Fig. 8 is an embedded raster (1020 × 893 px). The
axes were calibrated on their tick marks. Each marker centre was found twice, by a
ring fit and by the midpoint of its error-bar caps, which agree to 0.001 μ_B. A
600 dpi render agrees to 0.0006 μ_B, and an independent JPEG rendering to 0.0015
μ_B except where a square hides half a circle. The plotted inversion follows
from the plotted moment through eqn (7) with (1 − i) μ² to within 0.005 at nine
points. The tenth, 973 K, is the source's (see the errata). A planted 0.010 μ_B
error in one moment fails that check. The values are quoted to 0.01 μ_B because
they are readings of a figure.

**Errata, so that no test is held to a misprint:**

- Eqns (6) and (7) print "(1 − i) i μ²(Co²⁺)". The intended term is (1 − i) μ²(Co²⁺): only that form reproduces the plotted inversion.
- The text gives 2.71 μ_B "in the sample quenched from 1200 K" and i = 0.46 for the sample "quenched from 1163 K". Fig. 8 puts both at 1173 K, the highest quench in these files.
- Fig. 8's caption puts the moment on the left axis. The plot has it on the right (unit printed "m_B") and the inversion on the left.
- At 973 K, the plotted inversion is 0.015 above what eqn (7) gives from the plotted moment. The moment is read as plotted.

**The planted known-bad patterns.** There are three. `make_planted.py` builds each
from a real file beside it by a fixed transformation, and the only random step
uses a fixed seed. Each name starts with `PLANTED_`, and each heading title starts
`PLANTED … not a measurement`. None replaces a real file. Each is a defect a person
rejects on sight:

- **corrupted intensities** (`PLANTED_shuffled_counts_from_873q-1p5K_1.dat`): the counts are shuffled, so the pattern has no peaks;
- **a wrong sample in the series** (`PLANTED_wrong_sample_garnet_titled_co3o4.dat`): the garnet standard titled as a Co₃O₄ pattern;
- **a block of NaN counts** (`PLANTED_nan_block_from_1023q_1p5K.dat`): no number exists there to fit.

`read_pattern` reads all three, the NaN rows included, so each can reach a series.
That matters for `on_error`: a series takes `PatternData`, so a file the reader
refuses fails before the series starts and never reaches `on_error`. What the
series code does with them is a measurement for WP-2003's tiering session. Neither
these rows nor the tests assert it.

**Licence and citation.** The 24 real files are released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) by M. W. Gaultois, a
co-author of the study, in the [release comment](https://github.com/yue-here/rietx/pull/1162#issuecomment-6392651748). Attribution
means citing the paper and acknowledging the facility. The paper's
acknowledgement reads: "The authors thank the Institut Laue-Langevin for
neutron-diffraction beam time allocation (D1B)" (p. 104104-9). Neither the paper
nor a search of ILL's data DOIs gives a DOI for this 2011 experiment.

> Data from Taylor D. Sparks, Aleksander Gurlo, Maged F. Bekheet, Michael W. Gaultois, Gennady Cherkashinin, Laetitia Laversenne and David R. Clarke (ILL D1B): T. D. Sparks, A. Gurlo, M. F. Bekheet, M. W. Gaultois, G. Cherkashinin, L. Laversenne and D. R. Clarke, "High-temperature structure of Co₃O₄: Understanding spinel inversion using in situ and ex situ measurements", *Phys. Rev. B* **99**(10), 104104 (published 13 March 2019), doi:10.1103/PhysRevB.99.104104.

**Not vendored** from the same folder: the four CIFs (Co₃O₄ after Roth and after
Will, YAG, V), which are ICSD entries and may not be redistributed; the group's
FullProf `.pcr`, VESTA file and figures; and the group's instructions file, whose
facts are quoted above.

## WP-2003 series family B — the GSAS-II SeqRefine CuCr₂O₄ ramp (`seqrefine_cucr2o4/`)

WP-2003 measures the chain actions on series whose truth is independent of
rietx. This is the second such family (offered on PR #1150, accepted there by
the maintainer on 2026-10-24): CuCr₂O₄ goes from tetragonal `I4₁/amd` to
orthorhombic `Fddd` near 130 K, continuously, with ferrimagnetic order at the
same temperature. So a chain fitted in `I4₁/amd` throughout is missing a
component below a known onset, and a chain fitted in `Fddd` throughout should
fire nothing. Nothing in the tree fits these files yet.

**Provenance.** The tutorial cites no paper. The link to Suchomel *et al.*
(2012) below rests on the files themselves: every header gives `Composition =
CuCr2O4`, 11-BM, proposal 24443 with the paper's first author as contact, and
`Calibrated wavelength = 0.413263`, against the paper's λ = 0.41326 Å for
CuCr₂O₄ (p. 2). The paper's cryostat range is 7-300 K (p. 2), and its
Fig. 5(b) shows patterns at 288 K and 7 K, the two ends of this ramp (288.7 K
and 6.778 K). The paper states a 0.001° step while these files are at 0.002°
with 0.1 s a step (headers), so they are the ramp's scans of the same specimen,
not necessarily the scans behind Table I. The reference values are properties
of the specimen and hold either way.

| File | Run | T (K), header | Against 130 K | Bytes | SHA-256 |
|---|---|---|---|---|---|
| `seqrefine_cucr2o4/OH_00.fxye` | 4148 | 6.778 | below | 419 959 | `99b269c7c136ac7e175ecc250eaf3d5913bea335cca12ee180102ad082c979a4` |
| `seqrefine_cucr2o4/OH_04.fxye` | 4152 | 16.702 | below | 419 950 | `c0425923eb0e26cd3c9d28da0ed95f38103ff6ed3426751dcc17ec1a41bfee21` |
| `seqrefine_cucr2o4/OH_09.fxye` | 4157 | 46.97 | below | 420 031 | `7ce62cac596b33f16941523de6ced9399a79b9d6e2c902fddfdf7eedb92ef75d` |
| `seqrefine_cucr2o4/OH_14.fxye` | 4162 | 75.42 | below | 419 947 | `f609fdd8b736bbbabf721a07bc97dc79c967e5fd56c616f53419bd30fb38345a` |
| `seqrefine_cucr2o4/OH_19.fxye` | 4167 | 98.89 | below | 419 870 | `73f4fac7da75e8ff6b86a97f20877b5fde46ba9d314b22c92506b143e728d794` |
| `seqrefine_cucr2o4/OH_22.fxye` | 4184 | 111.43 | below | 419 742 | `d910c697066b697268cea05494e1f4f37fbcebd2b2e0e11ba51e1c7e296254d0` |
| `seqrefine_cucr2o4/OH_24.fxye` | 4186 | 122.73 | below | 419 782 | `0e4a3933e460134846a5f76da49d39203680351c5f3bb6612fa0538c73f6d77a` |
| `seqrefine_cucr2o4/OH_26.fxye` | 4188 | 134.02 | above | 419 638 | `d7e18d7f2f380ce766a5cc6e5b81e4d53ed76e6d0bf28b4164e1d2dde356d0c3` |
| `seqrefine_cucr2o4/OH_28.fxye` | 4190 | 145.47 | above | 419 651 | `a9891f7a2ed4b00d55fb26396b1b8c1916b572a859936e5b308c88e8f6384ce2` |
| `seqrefine_cucr2o4/OH_30.fxye` | 4192 | 156.9 | above | 419 706 | `947a64d706fffa1a72db3ba90def59f76d43b95dc9b7c3d64bf98b1e82637ae1` |
| `seqrefine_cucr2o4/OH_32.fxye` | 4194 | 168.43 | above | 419 704 | `855ee6daf5365074943782420d469a9baca4060be4dc5bea05a33b918c89222c` |
| `seqrefine_cucr2o4/OH_35.fxye` | 4197 | 185.67 | above | 419 708 | `2501da0196e31eaf6833c5c3fe54912ba6c39a5e3b6985282f069e333d997b44` |
| `seqrefine_cucr2o4/OH_38.fxye` | 4200 | 203.0 | above | 419 668 | `78400e3744b1d76a089e7cba06b55077098bae6e7a2575be092f7e1a23cc835d` |
| `seqrefine_cucr2o4/OH_41.fxye` | 4203 | 220.3 | above | 419 662 | `d8a799118bc04bd250f0e1e2c5296dcefa61f657898ec896a6c0b83ee43699cf` |
| `seqrefine_cucr2o4/OH_45.fxye` | 4207 | 243.4 | above | 419 634 | `7a1dfbced2a5099eb8c0340fa6e41c551a466c0469d1ad79659c895b08ffdda5` |
| `seqrefine_cucr2o4/OH_49.fxye` | 4211 | 266.9 | above | 419 675 | `cbb729d73645ef004e96639ce186dbf2d7b39d26fa14562e9c414bff2a98b00d` |
| `seqrefine_cucr2o4/OH_53.fxye` | 4215 | 288.7 | above | 419 689 | `960671e175830c6c46fd9e2d254d80c03bdfea2bc3c84e93540a2de035dd0f65` |
| `seqrefine_cucr2o4/OH_00.prm` | — | — | — | 1 134 | `2ab05eebadbdc382495ea1fb87333c46e36da385595d64099bf66665a0ed11db` |
| `seqrefine_cucr2o4/CuCr2O4.cif` | — | — | — | 1 951 | `f459c16f6d2cbc788e172dd20530115dc16b2e13984f4523ed4bd907008f5c41` |
| `seqrefine_cucr2o4/CuO.cif` | — | — | — | 1 272 | `bf4d157c15775a4bdcb116751a0e1ae8976bb81f68cad41c6e732f30d11ead27` |
**Reference values.** All from Suchomel *et al.* (2012), read as the authors'
preprint arXiv:1206.5760v1 (25 June 2012), so page numbers are the
preprint's; the journal version was not read. None comes from rietx or from
the tutorial.

| Quantity | Value | Where in the paper |
|---|---|---|
| Room-temperature structure | tetragonal `I4₁/amd`, origin choice 2 | Table I, p. 6; abstract |
| Low-temperature structure | orthorhombic `Fddd`, origin choice 2 | Table I, p. 6; § III B, p. 5 |
| Structural transition | ≈ 130 K, concurrent with ferrimagnetic order | text p. 4 ("an orthorhombic distortion … occurs concurrently with ferrimagnetic ordering at 130 K"); Fig. 8(a) caption, p. 7 ("∼130 K") |
| Order of the transition | second order: V/Z continuous through it | text p. 6, Fig. 8(b) |
| T_N | 130 K, from χ(T) | text p. 3; Fig. 3(a) caption p. 4 ("≈130 K"); Fig. 5(a) caption p. 5 ("T_N = 130 K"). The earlier neutron work the paper cites gives 135 K (p. 2) |
| Second heat-capacity anomaly | 155 K, with a subtle inflection of V/Z | text p. 8; Fig. 12(c) |
| CuO impurity | 1.1 wt % (Rietveld; temperature not stated) | § II, p. 2 |
| Fddd cell, 10 K | a = 7.71271(2), b = 8.53611(2), c = 8.54357(2) Å; V/Z = 70.3098(3) Å³ | Table I, p. 6 |
| I4₁/amd cell, 298 K | a = 6.03277(1), c = 7.78128(1) Å; V/Z = 70.7986(2) Å³ | Table I, p. 6 |
| Axis correspondence | `Fddd` a goes with the tetragonal c; `Fddd` b and c with √2·a_tet, so above 130 K an `Fddd` model's b and c are equal in truth | Fig. 8 caption, p. 7 |
| Ordered moment | **none measured**: the study is X-ray and refines no magnetic structure. It quotes the earlier neutron result of a net 0.5 μ_B per formula unit (p. 2; its refs. 21, 26, 27) and measures a saturation magnetisation of 0.725 μ_B at 2 K by SQUID (pp. 3-4, Fig. 3(b)); neither is a per-site moment, and X-ray data cannot test either | p. 2; pp. 3-4 |

The Table I cells were read from the text layer and again from a 200 dpi
render of p. 6, which agree; V/Z recomputed from each cell matches the printed
value to its last digit. Per-temperature cells exist only as Fig. 8(a), a
plot; no number here is read off a figure.

**Not reference values:** the tutorial's own results (its Rwp of 13-17 %
after the full parameter set, and the 25-30 % at the hottest patterns before
it) and the two CIFs' cells and coordinates, which are the tutorial's GSAS-II
values.

Matthew R. Suchomel, Daniel P. Shoemaker, Lynn Ribaud, Moureen C. Kemei and
Ram Seshadri, "Spin-induced symmetry breaking in orbitally ordered NiCr₂O₄ and
CuCr₂O₄", *Phys. Rev. B* **86**(5), 054406 (2012), published 6 August 2012,
doi:10.1103/PhysRevB.86.054406; preprint arXiv:1206.5760.
