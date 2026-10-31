# rietx — validation matrix

<!-- GENERATED FILE — do not edit by hand.
     Source: tests/validation_matrix.py
     Regenerate: .venv/bin/python -m tests.validation_matrix
     Guarded by: tests/test_validation_matrix.py (fast suite) -->

Every real-data assertion in this repository, and what its tolerance is
referenced to. A bar without its reference value is not a claim: `abs(a - 4.156780) <
2e-4` and `abs(delta_a) < 1e-9` look alike and are not remotely the same
statement — the first is a certified value the fit does not reach and does not
claim to, the second is two of our own fits that must agree to floating point.

The policy this table implements is in [DESIGN.md](DESIGN.md#testing--validation-policy);
the measured milestone records are in [milestones/](milestones/).

## The one rule that shapes everything below

**Judge a correction by what it changed, never by delta Rwp.** Of the eight
corrections in v0.5, two provably cannot move Rwp, one moves it the *wrong way*
when it is right, and the two largest accuracy wins are invisible in it. A
validation matrix whose columns were agreement indices would score that
milestone as having delivered nothing — which is why two of the tiers below
are kinds of evidence rather than kinds of tolerance.

## Tiers

### `identity`

Referenced to floating-point arithmetic, not to any physical quantity.  Two runs that must agree because the difference between them is provably an exact reparameterisation, a value that must be exactly what it was held at, or a sum that must close.  Bars are 1e-12 to 1e-6 and the measured margin is expected to sit orders inside — an identity row whose margin creeps toward its bar is a bug report, not a passing test.

### `certificate`

Referenced to a certified value **with its stated uncertainty**.  A row in this tier must say whether it asserts at certificate grade or is systematics-limited, because on lab data most are the latter: SRM 676a's axial ratio is certificate-grade (+30 ppm against a k=2 uncertainty of ~21 ppm) while its absolute axes carry a −300 ppm d-scale systematic that no widened band should be allowed to hide.

### `cross_code`

Referenced to another code's converged result, **with its protocol adopted** — the same refined set, the same held parameters, the same excluded regions, and a channel count checked to match before any number is compared.  A cross-code figure computed over different channels with a different free set is not a comparison (v0.2 learned this the expensive way on fluorapatite: a plausible guessed protocol gave Rwp 16 % and +390 ppm; the mirrored one gave 9.73 % and +116 ppm in that version).

### `spread`

Referenced to a published inter-laboratory spread — what practitioners actually achieve on this specimen — and never to sigma.  The QPA weight-fraction esds are 0.1-0.7 wt %, several times below the measured errors, so a sigma-referenced bar would fail every participant in the round robin including the ones who got the right answer.

### `own_result`

Referenced to this package's own other result under a fixed protocol — the chained fit against the independent one, the Rietveld cell against the Le Bail cell.  Not truth, but far tighter than any external tolerance: two runs differing only in starting values should agree well inside the physics.

### `characterisation`

Asserts no accuracy at all.  Either the *shape* of a known systematic (that a cell offset is uniform across axes, hence a d-scale convention and not a structural error), or that a model is **inadmissible** — an Rwp improvement both statistical tests bless and a physics guard rejects.  This tier is how a measured failure gets recorded as a result instead of being tuned away.

### `prediction`

A parameter-free prediction written down **before** the measurement, then checked.  What it is checked against decides what it shows, and each row names that kind (`reference_kind`, WP-2010): against an independent measurement it validates, as the dispersion prediction does against the round robin's weighed compositions (predicted RMS 0.83 wt %, measured 0.69, 0.62 on 1.9.0); against the package's own arithmetic, its own earlier result or another code it verifies, however exact the agreement.  The capillary correction's ΔB = c(µR)·λ²/2 predicted 0.016875 Å² and the refits moved every Biso by 0.01687, which shows the code computes the reparameterisation it claims and says nothing about the specimen.

### `ceiling`

**Not a tier.**  A regression bar — `status == 'converged'`, `rwp < 0.20`, `gof < 2.0` — that carries no accuracy claim and is loose on purpose.  Labelled explicitly so it can never be read as validation.  Every acceptance test has these; only the rows whose *only* tier is `ceiling` are claiming nothing else.

## Start dependence

How many independent starting points a quoted number has to survive. This is
a verification axis because it was measured to change a conclusion: sweeping the
Stephens strain seed over 400/800/1600/3000 on round-robin brucite leaves the
coefficients spanning ~100 % relative spread under *both* solvers, and moves the
unconstrained fit in and out of the physical cone (15, 12, 0, 0 reflections
violating). A single-start acceptance number would have called that specimen
either fine or broken depending on which seed the suite happened to pin.

1. A **cell parameter, weight fraction or scale** may be quoted from one start.
   These are well-conditioned and the staged plan reaches the same basin from any
   sane starting model. Every `certificate`, `cross_code` and `spread` row below
   is single-start, and that is not a weakness.
2. A **width or shape parameter entering through a square root, a cone, or a
   softplus floor** must survive a documented sweep before any number is quoted
   from it — that is the class where the objective is flat or non-convex near
   the start.
3. When a sweep is run and the parameters move but the **conclusion** does not,
   the conclusion is what gets recorded and the sweep goes in the docstring. Pinning
   a per-seed number would convert a known instability into a flaky test.

## Datasets

| Key | File | Role | What it is |
|---|---|---|---|
| `srm660c` | `tests/data/nist_srm660c_100a.cif` | **absolute anchor** | NIST SRM 660c LaB6, lab Cu Ka doublet + graphite analyzer; the certification measurement itself |
| `srm676a` | `tests/data/qarr/corundum.prn` | **absolute anchor** | NIST SRM 676a corundum, lab Cu Ka; the round robin's pure-phase pattern doubles as the cell-anchor specimen |
| `lab6_cbn` | `tests/data/11BM_LaB6_cBN_mg2044.xye` | cross-code | APS 11-BM synchrotron NIST SRM 660b LaB6 + cubic BN two-phase mixture, lambda = 0.413680 A from the .prm; propagated esds from twelve analyser crystals. No weighed composition exists, so every row referenced to it is cross-code |
| `si640c` | `tests/data/11BM_Si640c.xy` | cross-code | APS 11-BM synchrotron NIST SRM 640c silicon, run 4918 (Feb 2010), the beamline's provided standard scan; lambda seeded at the header's stated 0.412359 A and refined against the held certificate cell.  Real propagated esds (twelve analysers).  The refined wavelength is cross-code against XND 1.42; the held cell is the NIST certificate |
| `nac` | `tests/data/11BM_NAC.fxye` | characterisation | APS 11-BM synchrotron Na2Ca3Al2F14 with a CaF2 impurity, lambda = 0.4139090 A from the .prm |
| `fap` | `tests/data/FAP.XRA` | cross-code | GSAS-II LabData tutorial fluorapatite; FAP.EXP is GSAS's converged fit and supplies both the reference values and the protocol |
| `powderline_lab6` | `tests/data/powderline/example_LaB6/input.json` | cross-code | NSLS-II 28-ID-1 SRM 660c LaB6, lambda = 0.1665 A, as a PowderLine recipe with the SRM cell HELD -- an instrument-profile calibration, so there is no cell to compare and the reference is the profile GSAS-II and TOPAS each drew |
| `powderline_drx33` | `tests/data/powderline/example_DRX_33/input.json` | cross-code | NSLS-II 28-ID-1 disordered-rocksalt cathode + Li4MgWO6, two phases, as a PowderLine recipe.  The only dataset here with TWO committed reference engines, and they disagree by 2668 ppm on the cubic cell |
| `hl2` | `tests/data/hl2_peaks.txt` | characterisation | 74 peaks from a genuinely UNIDENTIFIED laboratory pattern -- our own derived product from datalab-org/guillemot's MIT examples, carried with attribution; the compound is unknown and stays unknown |
| `qarr` | `tests/data/qarr` | **absolute anchor** | IUCr CPD QPA round-robin patterns (samples 1a-1h, 2, 4 and six pure phases), Cu Ka doublet, graphite diffracted-beam monochromator |
| `srm660a_capillary` | `tests/data/11BM_LaB6_660a.fxye` | consistency only — *never* an anchor | APS 11-BM SRM 660a LaB6 in the beamline's documented 0.81 mm Kapton bore; lambda was calibrated against this very standard |
| `ndruo_joint` | `tests/data/mg090.fxye` | cross-code | Nd2Ru2O7 pyrochlore, one specimen, two histograms: APS 11-BM synchrotron X-ray (lambda 0.4132950 A, 49 493 points) and NCNR BT-1 neutron through a Cu(311) monochromator (lambda 1.54040 A, 3 296 points).  The two histograms of the combined refinement in Gaultois et al., J. Phys.: Condens. Matter 25 (2013) 186004 (doi:10.1088/0953-8984/25/18/186004), whose stated method is to hold the X-ray wavelength and refine the neutron one -- the only one-specimen two-wavelength pair in the suite, hence the only dataset that can exercise a refinable wavelength at all |
| `bethanechol` | `tests/data/bethanechol_indexing.json` | cross-code | Bergmann et al. (2004) Tables 5 and 6: ten sets of twenty 2theta positions for bethanechol chloride, the known P21/n cell, and every program's published score -- the only externally graded benchmark any feature in this package has |
| `cr2wo6_hb2a` | `tests/data/gsas2_hb2a_cr2wo6_4K.dat` | characterisation | HFIR HB-2A constant-wavelength neutron (lambda 2.4067 A) Cr2WO6 at 4 K, below its ordering temperature, and its 150 K partner gsas2_hb2a_cr2wo6_150K.dat, above it -- the GSAS-II Magnetic-II tutorial pair, vendored verbatim.  No certified moment exists, so every row referenced to it is characterisation: a moment the report supports below T_N and refuses above it |
| `lamno3_bt1` | `tests/data/gsas2_bt1_lamno3_50K.gsas` | characterisation | NIST BT-1 constant-wavelength neutron (lambda 1.5403 A, Cu(311)) LaMnO3 at 50 K, below its ordering temperature, with the tutorial's own structure file -- the GSAS-II Magnetic-I tutorial, vendored verbatim.  k = 0, and two magnetic groups index every line.  The tutorial quotes no moment, so every row referenced to it is characterisation: which group the data prefers, and the shape of the moment it carries |
| `srm1976a_plate` | `tests/data/srm1976a_corundum_xpert.xy` | cross-code | NIST SRM 1976a sintered corundum plate, lab Cu Ka on a Philips/PANalytical X'Pert with X'Celerator, 2013; a genuinely textured flat specimen, committed with its solved TOPAS refinement (PO_Spherical_Harmonics at order 4).  The certificate certifies relative intensities on another instrument, not this texture, so every row referenced to it is cross-code |

`consistency` is a fence, not a label: 11-BM calibrated its wavelength against
SRM 660a LaB6 itself, so a refined LaB6 cell from that file reproduces the
certificate by construction. A guard refuses to let any such dataset carry a
`certificate` row.

## Features

Each feature of `rietx.features.FEATURES` (WP-2010), with what verifies it and what
validates it. A claim names the feature its bar is about (`Claim.features`). A
claim validates only against an independent measurement: `certificate` and
`spread` rows do, and a `prediction` row does only where its `reference_kind` is
`independent_measurement`. Every dataset in the tree is development data, so a
validation here is a validation on development data (DESIGN.md § Rules, 2). A
feature with no independent measurement is *not yet validated*, which says
nothing against it and is not *provisional*.

The `prediction` rows that verify rather than validate, by that rule: `test_the_microabsorption_shape_was_mostly_dispersion` (own_result), `test_capillary_absorption_is_an_exact_reparameterisation` (own_arithmetic), `test_the_absorption_shift_is_independent_of_dispersion` (own_arithmetic), `test_the_2004_zeroshift_hypothesis_cannot_be_tested_on_these_data` (own_arithmetic), `test_the_refined_wavelength_is_the_solo_cell_disagreement` (own_result), `test_swapping_which_wavelength_is_held_measures_the_same_ratio` (own_arithmetic), `test_the_neutron_widths_leave_one_esd_at_every_start` (own_arithmetic), `test_the_symmetric_window_recovers_xnd_to_sub_ppm` (another_code).

### `lattice_metric`

Cell and Bragg's law.

**Verified by:** `test_the_cbn_cell_agrees_with_topas_to_better_than_50_ppm`, `test_srm660c_lab6_rietveld`, `test_srm676a_corundum_cell_anchor`, `test_the_two_descriptions_of_the_r_lattice_refine_to_the_same_cell`, `test_drx_cells_land_inside_the_two_engines_envelope`, `test_drx_agrees_with_topas_far_more_closely_than_the_engines_agree`, `test_fap_lab_rietveld_matches_gsas`, `test_nac_lebail_then_rietveld`, `test_the_cell_belongs_to_the_synchrotron`

**Validated by:** `test_srm660c_lab6_rietveld`, dataset `srm660c` (development data). Mismatch: a = 4.156882(21) A, +24 ppm; Rwp 8.74 %, GoF 1.89; zero_shift held at exactly 0.0; displacement -0.0790 mm vs the CIF's -0.07877. The Gaussian width is real at all 60 reflections. 1.9.0 read +25 ppm (24.6 against 24.5), Rwp 8.75 % and -0.0791 mm, before WP-2002's closing stage (#1085). Before WP-1938 the width sat on its clamp at 12 reflections, and the fit read 4.156895 A, +28 ppm, Rwp 8.67 %

**Validated by:** `test_srm676a_corundum_cell_anchor`, dataset `srm676a` (development data). Mismatch: c/a +29 ppm; absolute axes -314 / -284 ppm with |da - dc| within 2.9e-5; Rwp 14.4 %, GoF 1.60 against a GoF floor of 1.5-1.9 for analytical-PSF lab fits (Cline 2015); 1.9.0 read +30, -312 / -282 ppm, Rwp 14.6 % and GoF 1.63

**State:** validated on development data.

### `wavelength`

Emission lines, wavelength scales, harmonics, wavelength-cell degeneracy.

**Verified by:** `test_srm660c_lab6_rietveld`, `test_the_refined_wavelength_is_the_solo_cell_disagreement`, `test_the_diagnostic_reports_the_ppm_and_nothing_claims_rwp`, `test_swapping_which_wavelength_is_held_measures_the_same_ratio`, `test_the_refined_wavelength_recovers_xnds_calibration_error`, `test_the_symmetric_window_recovers_xnd_to_sub_ppm`, `test_the_wavelength_calibration_diagnostic_fires_once_and_reports_the_ppm`

**Validated by:** `test_srm660c_lab6_rietveld`, dataset `srm660c` (development data). Mismatch: a = 4.156882(21) A, +24 ppm; Rwp 8.74 %, GoF 1.89; zero_shift held at exactly 0.0; displacement -0.0790 mm vs the CIF's -0.07877. The Gaussian width is real at all 60 reflections. 1.9.0 read +25 ppm (24.6 against 24.5), Rwp 8.75 % and -0.0791 mm, before WP-2002's closing stage (#1085). Before WP-1938 the width sat on its clamp at 12 reflections, and the fit read 4.156895 A, +28 ppm, Rwp 8.67 %

**State:** validated on development data.

### `position_aberrations`

Zero, specimen displacement and transparency.

**Verified by:** `test_srm660c_lab6_rietveld`

**Validated by:** `test_srm660c_lab6_rietveld`, dataset `srm660c` (development data). Mismatch: a = 4.156882(21) A, +24 ppm; Rwp 8.74 %, GoF 1.89; zero_shift held at exactly 0.0; displacement -0.0790 mm vs the CIF's -0.07877. The Gaussian width is real at all 60 reflections. 1.9.0 read +25 ppm (24.6 against 24.5), Rwp 8.75 % and -0.0791 mm, before WP-2002's closing stage (#1085). Before WP-1938 the width sat on its clamp at 12 reflections, and the fit read 4.156895 A, +28 ppm, Rwp 8.67 %

**State:** validated on development data.

### `capillary_offsets`

Capillary offsets along and across the beam.

**Verified by:** unit tests `tests/test_capillary_displacement.py::test_eq4_is_the_ray_trace_to_first_order`, `tests/test_capillary_displacement.py::test_an_injected_displacement_is_recovered_on_both_axes`

**State:** not yet validated.

### `tof_calibration`

Time-of-flight calibration (DIFC, DIFA, DIFB, TZERO).

**Verified by:** unit tests `tests/test_tof_axis.py::test_a_synthetic_bank_converts_back_to_the_d_spacings_it_was_built_from`, `tests/test_tof_axis.py::test_fit_refuses_a_tof_pattern_against_a_cw_instrument`

**State:** not yet validated.

### `tof_profile`

Time-of-flight peak shape and incident spectrum.

**Verified by:** unit tests `tests/test_instrument_tof.py::test_the_default_type_three_block_is_read_in_the_manuals_order`, `tests/test_tof_axis.py::test_fit_refuses_a_tof_pattern_against_a_cw_instrument`

**State:** not yet validated.

### `instrument_profile`

Caglioti/TCH pseudo-Voigt and true Voigt.

**Verified by:** `test_lab6_drawn_peak_widths_match_the_reference_profile`, `test_fap_lorentzian_matches_gsas_lx_on_gsas_own_model`

**State:** not yet validated.

### `axial_divergence`

Finger-Cox-Jephcoat axial divergence.

**Verified by:** `test_the_refined_wavelength_recovers_xnds_calibration_error`, `test_the_symmetric_window_recovers_xnd_to_sub_ppm`

**State:** not yet validated.

### `bragg_intensities`

Bragg intensities: structure factor, X-ray f0, occupancy, Lorentz-polarisation, Rietveld mode.

**Verified by:** `test_sample1_fractions_within_participant_spread`

**Validated by:** `test_sample1_fractions_within_participant_spread`, dataset `qarr` (development data). Mismatch: worst 5.10 wt % (1f zincite), traces <= 1.3, RMS 2.30; closure exact to 1e-6.  1.9.0 read 4.92, 1.1 and 2.19; WP-2002's closing stage (#1085) took them to 5.08 and 2.26 and its width twin hold (#1113) to 5.10 and 2.30

**State:** validated on development data.

### `neutron_scattering`

Neutron scattering lengths.

**Verified by:** unit tests `tests/test_neutron_scattering.py::test_natural_element_scattering_lengths_match_gemmi_sears_1992`

**State:** not yet validated.

### `anomalous_dispersion`

Anomalous scattering f′ and f″ (Source.dispersion).

**Verified by:** `test_sample1_fractions_beat_the_dispersion_free_fit`, `test_the_microabsorption_shape_was_mostly_dispersion`, `test_zincite_cell_does_not_move`, `test_srm660c_lattice_parameter_is_untouched`, `test_the_neglect_diagnostic_clears_when_the_block_is_on`

**Validated by:** `test_sample1_fractions_beat_the_dispersion_free_fit`, dataset `qarr` (development data). Mismatch: worst 1.37 wt % (was 5.13); 1.20 on 1.9.0, before WP-2002's closing stage (#1085, 1.34) and width twin hold (#1113)

**State:** validated on development data.

### `displacement_parameters`

Isotropic and anisotropic displacement parameters.

**Verified by:** `test_tying_the_similar_atoms_bisos_buys_precision`, `test_biso_is_positive_and_agrees_with_xnd`

**State:** not yet validated.

### `atomic_coordinates`

Fractional coordinates and site-symmetry DOFs.

**Verified by:** `test_the_one_free_coordinate_agrees`, `test_fap_lab_rietveld_matches_gsas`

**State:** not yet validated.

### `rigid_bodies`

Rigid bodies (origin, rotation, torsions; riding H).

**Verified by:** unit tests `tests/test_rigid_body.py::test_body_esds_equal_the_central_fd_chain`, `tests/test_rigid_body.py::test_orientation_recovered_from_a_synthetic_pattern`

**State:** not yet validated.

### `restraints`

Soft restraints and their weighting (Phase.restraints).

**Verified by:** unit tests `tests/test_restraints.py::test_restraint_jacobian_matches_fd_per_kind`, `tests/test_restraints.py::test_bond_restraint_recovers_perturbed_coordinate`

**State:** not yet validated.

### `primary_extinction`

Primary extinction (Sabine).

**Verified by:** `test_nac_extinction_on_the_main_phase_is_bounded_and_unbiasing`

**State:** not yet validated.

### `march_dollase`

Preferred orientation, March-Dollase.

**Verified by:** `test_sample2_brucite_march_dollase`

**Validated by:** `test_sample2_brucite_march_dollase`, dataset `qarr` (development data). Mismatch: r ~ 0.67; worst fraction 3.0 wt % (zincite); H Biso held at exactly 2.5; 1.9.0 read 2.8 wt %

**State:** validated on development data.

### `spherical_harmonics_texture`

Preferred orientation, spherical harmonics.

**Verified by:** `test_sample2_brucite_spherical_harmonics`, `test_c20_and_c40_agree_with_topas_with_no_conversion`, `test_the_measured_ratio_excludes_the_other_normalisations`, `test_without_texture_the_plate_fits_measurably_worse`

**Validated by:** `test_sample2_brucite_spherical_harmonics`, dataset `qarr` (development data). Mismatch: worst fraction 3.71 wt % at order 4, 2.91 at order 6, against March-Dollase's 3.01; C2,0 1.40(4) and 1.39(5); J 1.45 and 1.46; min P 0.47 and 0.39.  Measured by WP-1960 before WP-2002: 3.41, 2.71 and 2.80; the closing stage (#1085) and the width twin hold (#1113) each moved them

**State:** validated on development data.

### `qpa`

Quantitative phase analysis and microabsorption.

**Verified by:** `test_the_qpa_agrees_with_topas_within_its_own_esd`, `test_drx_phase_scales_are_the_same_answer_as_topas`, `test_sample1_fractions_within_participant_spread`, `test_a_supported_trace_phase_is_never_held`, `test_sample2_brucite_march_dollase`, `test_sample2_brucite_spherical_harmonics`, `test_sample1_fractions_beat_the_dispersion_free_fit`, `test_chained_qpa_within_participant_spread`

**Validated by:** `test_sample1_fractions_within_participant_spread`, dataset `qarr` (development data). Mismatch: worst 5.10 wt % (1f zincite), traces <= 1.3, RMS 2.30; closure exact to 1e-6.  1.9.0 read 4.92, 1.1 and 2.19; WP-2002's closing stage (#1085) took them to 5.08 and 2.26 and its width twin hold (#1113) to 5.10 and 2.30

**Validated by:** `test_sample2_brucite_march_dollase`, dataset `qarr` (development data). Mismatch: r ~ 0.67; worst fraction 3.0 wt % (zincite); H Biso held at exactly 2.5; 1.9.0 read 2.8 wt %

**Validated by:** `test_sample2_brucite_spherical_harmonics`, dataset `qarr` (development data). Mismatch: worst fraction 3.71 wt % at order 4, 2.91 at order 6, against March-Dollase's 3.01; C2,0 1.40(4) and 1.39(5); J 1.45 and 1.46; min P 0.47 and 0.39.  Measured by WP-1960 before WP-2002: 3.41, 2.71 and 2.80; the closing stage (#1085) and the width twin hold (#1113) each moved them

**Validated by:** `test_sample1_fractions_beat_the_dispersion_free_fit`, dataset `qarr` (development data). Mismatch: worst 1.37 wt % (was 5.13); 1.20 on 1.9.0, before WP-2002's closing stage (#1085, 1.34) and width twin hold (#1113)

**Validated by:** `test_chained_qpa_within_participant_spread`, dataset `qarr` (development data). Mismatch: identical to the independent fits' record

**State:** validated on development data.

### `attenuation_estimate`

Attenuation coefficients from composition.

**Verified by:** `test_estimated_mu_r_matches_the_documented_capillary`

**State:** not yet validated.

### `capillary_absorption`

Capillary absorption (Rouse).

**Verified by:** `test_capillary_absorption_is_an_exact_reparameterisation`, `test_the_absorption_shift_is_independent_of_dispersion`

**State:** not yet validated.

### `flat_plate_absorption`

Flat-plate absorption (thin specimen).

**Verified by:** unit tests `tests/test_flat_plate.py::test_reflection_matches_the_defining_integral`, `tests/test_flat_plate.py::test_transmission_matches_the_defining_integral`

**State:** not yet validated.

### `surface_roughness`

Surface roughness (Suortti, Pitschke).

**Verified by:** unit tests `tests/test_surface_roughness.py::test_suortti_matches_an_independent_transcription_of_the_published_form`, `tests/test_surface_roughness.py::test_injected_roughness_is_recovered_and_is_resolved_not_merely_fitted`

**State:** not yet validated.

### `size_strain`

Isotropic size and strain widths.

**Verified by:** unit tests `tests/test_profile_size.py::test_the_size_coefficient_maps_to_one_size_at_every_angle`, `tests/test_profile_size.py::test_delta_q_is_scherrer_in_q_whatever_the_instrument`

**State:** not yet validated.

### `microstructure_readings`

A width read as a domain size or a strain.

**Verified by:** unit tests `tests/test_microstructure.py::test_the_strain_coefficient_is_360_over_pi_times_the_strain`, `tests/test_microstructure.py::test_a_size_reads_back_the_crystallite_it_was_built_from`

**State:** not yet validated.

### `stephens_strain`

Stephens anisotropic strain.

**Verified by:** `test_corundum_block_is_inert_and_hamilton_blesses_it_only_at_raw_n`

**State:** not yet validated.

### `magnetic_structure`

Magnetic moments, magnetic form factor, magnetic widths.

**Verified by:** `test_the_4k_moment_does_not_depend_on_its_in_plane_seed`

**State:** not yet validated.

### `magnetic_determination`

Representation analysis and magnetic candidates (solve_magnetic).

**Verified by:** unit tests `tests/test_magnetic_irreps.py::test_character_tables_agree_with_the_spgrep_oracle_for_all_230_groups`, `tests/test_magnetic_isotropy.py::test_pnma_at_gamma_has_exactly_four_maximal_magnetic_subgroups`

**State:** not yet validated.

### `satellites`

Satellites of a propagation vector (Phase.propagation_vector).

**Verified by:** unit tests `tests/test_satellites.py::test_the_manuals_two_worked_examples_on_a_c_lattice`, `tests/test_satellites.py::test_a_satellite_orbit_is_a_multiplicity`

**State:** not yet validated.

### `background_curve`

Chebyshev / P-spline background and air scatter.

**Verified by:** `test_the_chebyshev6_arm_relaxes_the_peak_onto_the_envelope`, `test_a_longer_polynomial_eats_the_measured_scale`

**State:** not yet validated.

### `measured_background`

A measured (blank) background and its scale.

**Verified by:** `test_a_measured_blank_beats_the_polynomial_and_the_fitted_hump`, `test_the_refined_scale_rejects_the_only_value_the_code_could_express`, `test_the_hand_set_scan_puts_the_minimum_where_the_scale_landed`, `test_a_longer_polynomial_eats_the_measured_scale`

**State:** not yet validated.

### `background_estimation`

Model-free background estimate (auto_background).

**Verified by:** unit tests `tests/test_profiles_background.py::test_the_whittaker_baseline_solves_its_defining_system`, `tests/test_profiles_background.py::test_arpls_recovers_baseline_under_peaks`

**State:** not yet validated.

### `extra_components`

Humps and declared extra peaks.

**Verified by:** `test_declaring_the_intruder_recovers_the_clean_cell`, `test_the_excluded_regions_alternative_is_quoted_and_never_gated`, `test_the_declared_holder_lines_come_back_where_they_were_put`, `test_the_declared_peaks_are_ticks_and_not_background`, `test_one_hump_beats_three_more_polynomial_terms`, `test_the_peak_is_diffuse_by_three_orders_and_frees_the_structural_esd`, `test_the_chebyshev6_arm_relaxes_the_peak_onto_the_envelope`

**State:** not yet validated.

### `lebail_pawley`

Le Bail and Pawley intensity extraction (modes).

**Verified by:** `test_a_pawley_fit_past_the_bvls_cut_converges_every_stage`, `test_nac_lebail_then_rietveld`

**State:** not yet validated.

### `indexing`

Indexing: engines, figures of merit, lattice ambiguity, supercells.

**Verified by:** `test_every_set_is_twenty_ascending_lines`, `test_table_5_reconstruction_sums_to_the_published_globals`, `test_the_zeroshift_correction_is_exactly_the_paper_s`, `test_the_intensity_cut_is_a_subset_of_the_same_measurement`, `test_the_published_cell_reproduces_the_paper_s_impurity_counts`, `test_the_runner_adopts_the_paper_s_domain_from_the_fixture`, `test_the_scoring_rule_is_the_paper_s_and_reads_it_from_the_fixture`, `test_the_published_cell_is_recognised_in_the_setting_the_search_returns`, `test_published_figures_of_merit_are_reproduced_unfloored`, `test_positions_alone_cannot_separate_lab6_from_a_half_volume_rival`, `test_the_cross_code_cell_leads_because_the_engines_agree_on_it`

**Validated by:** `test_a_certified_lab_pattern_indexes_and_is_graded_honestly`, dataset `srm676a` (development data). Mismatch: ranked first, trigonal R, a +89 ppm and c +60 ppm, 44 of 46 lines, chi2_red 0.55.  Confidence low on three caveats: engines_disagree, predicted_but_absent (11 -- the R-3c c-glide, not an oversized cell) and fom_panel_disagrees.  best_or_none() returns None.  WP-1038 cleared two of the former four: the shift is now MEASURED before the search from harmonic reflection pairs (-0.0641 deg, against an independently known -0.065), so shift_allowance_assumed no longer fires, and the measured window crosses the 0.9 bar unaided (indexed fraction 0.957).  WP-1110 and WP-1510 took two no_intensity components and five duplicate copies out of the usable list, so the row reads 45 of 47 where it read 51 of 55 (the 49-line and +101 ppm figures of the assumed 0.05 deg window are WP-1038's, not re-run).  The wider window is not free: a window that cannot rule out a constant must stay at |c| everywhere, where the true cos(theta) deviation has fallen to 0.26|c| by 150 deg.  1.9.0 read a +110 and c +57 ppm, 45 of 47 lines and chi2_red 0.67; the peak picker's changes before #1050 (#947 to #951, not bisected among them) took one line from the usable list

**Validated by:** `test_declaring_the_shift_template_is_what_recovers_the_certificate`, dataset `srm676a` (development data). Mismatch: fitted shift -0.0699 +/- 0.0192 deg; a +89 -> -111 ppm, c +60 -> -96 ppm, c/a -29 -> +15 ppm; M20 23.3 -> 187.1, F_N 15.3 -> 145.0, Le Bail Rwp 0.256 -> 0.176.  Since WP-1038 the two mechanisms are cleanly separated: the pair-MEASURED magnitude widens the window and finds lines (both calls index 44 of 46, so indexed_fraction_low has already cleared before the template is declared), and the DECLARED shape is what moves the cell.  Three routes to one systematic, none told the answer: -0.0641 from pairs pre-search, -0.0749 from the post-candidate fit, -0.065 measured against the certificate.  Still low, on caveats that have nothing to do with the shift.  1.9.0 read -0.0749 +/- 0.0187 deg, a +110 -> -114 and c +57 -> -109 ppm, c/a -54 -> +5, M20 23.7 -> 160.0, F_N 16.6 -> 114.9 and Le Bail Rwp 0.285 -> 0.224: the peak picker's changes before #1050 (#947 to #951, not bisected among them) took one line from the usable list, and WP-2002's closing stage and width twin hold (#1085, #1113) moved the Le Bail checks

**Validated by:** `test_a_certified_cubic_cell_is_recovered_with_no_extinction_caveat`, dataset `srm660c` (development data). Mismatch: cubic P ranked first, a -127 ppm against the CIF's 4.156780 A; predicted_but_absent 0 of 30 and predicted_seen_fraction 1.000 against corundum's 0.58.  Still low, but the caveat list has been shrinking by evidence and is now ONE: fom_panel_disagrees.  WP-1038 cleared shift_allowance_assumed (this pattern's +0.0345 deg is measured from harmonic pairs before the search), and WP-1039 cleared engines_disagree -- trial_error was not failing to find the certified cell, it was solving from the wrong base lines, because its pool took the lowest-Q lines of the whole list and five of this pattern's low-angle components are not lines of the phase.  Drawn from the strongest-N selection instead, BOTH engines find it.  Agreement was necessary and not sufficient: a cubic-only search now promotes to high, this four-system one does not.  best_or_none() returns None

**Validated by:** `test_the_shift_screen_survives_the_tail_components_but_the_search_cannot`, dataset `srm660c` (development data). Mismatch: tail components carry sigma ~0.005 deg against the real lines' ~0.0005; after the quadrature allowance that 100x contrast is 1.005.  Screen: +0.0367 +- 0.0015 (0.88 of the predicted 0.0415, the rest being the aberrations SRM 660c's own docstring names).  Search: +0.009 +- 0.016, consistent with none

**Validated by:** `test_what_the_unflagged_tail_components_cost_the_certified_cell`, dataset `srm660c` (development data). Mismatch: a = 4.156801 A, +5 ppm, M20 3266, ZERO caveats, confidence high -- a first on real data, against -127 ppm with none of the three.  But best_or_none() is None: the a*sqrt2 cell (5.878605) reached high in BOTH its I and P descriptions, all three engines finding all three cells; since WP-1449 the P one is refuted as an index-2 superlattice of the I one (supercell_refuted, low) and the I one still reaches high.  The 'best_or_none() non-None' claim recorded here before WP-1041 held only while trial_error's scale-invariant dedup key could return one cubic candidate per search, denying the supercells its vote -- the flagship result was protected by a bug rather than by the gate.  Everything that refutes the supercell is measured and ungated: Rwp 0.100 vs 0.860/0.654, predicted_seen_fraction 1.00 vs 0.88/0.49, m_rev 2245 vs 6.8/1.9, unmatched_observed 21 vs 168/129 (169/127 and Rwp 0.861/0.660 on 1.9.0, before WP-2002's width twin hold moved the Le Bail checks), while the one gated detector (predicted_but_absent) reads 0 for all three.  Also measured: declaring the probe-trimmed screen's own sigma_sys (0.0078, the residual the template LEAVES) gives a window 4.9x too tight for the shift's amplitude (0.038): the search matches uncorrected positions, and only svd, which fits a zero error inside the search (ze +0.033), still finds the certified cell (+5 ppm), which one engine cannot promote past low

**State:** validated on development data.

### `peak_shift_screen`

A systematic 2theta shift measured before the cell.

**Verified by:** `test_the_zeroshift_correction_is_exactly_the_paper_s`, `test_the_2004_zeroshift_hypothesis_cannot_be_tested_on_these_data`

**Validated by:** `test_declaring_the_shift_template_is_what_recovers_the_certificate`, dataset `srm676a` (development data). Mismatch: fitted shift -0.0699 +/- 0.0192 deg; a +89 -> -111 ppm, c +60 -> -96 ppm, c/a -29 -> +15 ppm; M20 23.3 -> 187.1, F_N 15.3 -> 145.0, Le Bail Rwp 0.256 -> 0.176.  Since WP-1038 the two mechanisms are cleanly separated: the pair-MEASURED magnitude widens the window and finds lines (both calls index 44 of 46, so indexed_fraction_low has already cleared before the template is declared), and the DECLARED shape is what moves the cell.  Three routes to one systematic, none told the answer: -0.0641 from pairs pre-search, -0.0749 from the post-candidate fit, -0.065 measured against the certificate.  Still low, on caveats that have nothing to do with the shift.  1.9.0 read -0.0749 +/- 0.0187 deg, a +110 -> -114 and c +57 -> -109 ppm, c/a -54 -> +5, M20 23.7 -> 160.0, F_N 16.6 -> 114.9 and Le Bail Rwp 0.285 -> 0.224: the peak picker's changes before #1050 (#947 to #951, not bisected among them) took one line from the usable list, and WP-2002's closing stage and width twin hold (#1085, #1113) moved the Le Bail checks

**Validated by:** `test_a_certified_shift_is_recovered_from_the_peak_list_alone`, dataset `srm660c` (development data). Mismatch: +0.0345 deg from 10 agreeing pairs of 19 admitted, z = 16.9 against 200 structureless replicates -- within 0.4 sigma of the reference-based fit it never saw, and 0.83 of the geometric prediction (the same 0.75-1.0 band the reference-based screen sits in, for the same reason).  separable is False: constant and cos_theta concentrate within one pair of each other, so a MAGNITUDE is measured and a CAUSE is not

**Validated by:** `test_the_svd_zero_error_is_a_third_road_to_the_anchors_shift`, dataset `srm660c` (development data). Mismatch: +0.0329 deg, within 0.003 of both.  Started AT the certified cell, so this measures the COLUMN and not the search; the search's own use of it is asserted against an exactly known injected shift in test_indexing_engines.py.  It also reaches where the pair screen declines -- a bare 20-line list supplies too few pairs to concentrate, the published bethanechol failure, and this needs none

**Validated by:** `test_the_svd_zero_error_is_a_third_road_to_corundums_shift`, dataset `srm676a` (development data). Mismatch: -0.0674 deg, within 0.003 of both.  Needs trim=1: the list opens on a 5.17 deg edge artifact 3.9x beyond the longest d the lattice allows, which breaks eq. (4)'s weighting outright.  A line no lattice can index is not a shifted line, and the column does not pretend otherwise

**Validated by:** `test_the_shift_screen_survives_the_tail_components_but_the_search_cannot`, dataset `srm660c` (development data). Mismatch: tail components carry sigma ~0.005 deg against the real lines' ~0.0005; after the quadrature allowance that 100x contrast is 1.005.  Screen: +0.0367 +- 0.0015 (0.88 of the predicted 0.0415, the rest being the aberrations SRM 660c's own docstring names).  Search: +0.009 +- 0.016, consistent with none

**State:** validated on development data.

### `peak_picking_and_fitting`

pick_peaks, fit_peaks and their flags.

**Verified by:** unit tests `tests/test_peak_picking.py::test_group_jacobian_matches_finite_differences`, `tests/test_peak_picking.py::test_recovered_positions_and_esds_on_a_clean_group`

**State:** not yet validated.

### `extinction_symbols`

Extinction symbols (determine_extinction_symbol).

**Verified by:** unit tests `tests/test_extinction_symbol.py::test_the_condition_derivation_is_measured_over_the_whole_table`, `tests/test_extinction_symbol.py::test_corundum_returns_the_class_its_certificate_names`

**State:** not yet validated.

### `derived_geometry`

Bond lengths and angles with esds.

**Verified by:** unit tests `tests/test_geometry_table.py::test_corundum_matches_the_published_geometry`, `tests/test_geometry_table.py::test_esd_matches_a_monte_carlo_through_decode`

**State:** not yet validated.

### `esds`

Esds: Berar-Lelann inflation, intervals at a bound, scale-B separation.

**Verified by:** `test_the_neutron_widths_leave_one_esd_at_every_start`

**State:** not yet validated.

### `sequential_series`

Sequential (chained) series.

**Verified by:** `test_chained_qpa_within_participant_spread`, `test_chained_agrees_with_independent_fits`, `test_the_hostile_series_exercises_the_reseed_fence`, `test_the_first_rung_bound_moves_no_accepted_value`, `test_series_exports`

**Validated by:** `test_chained_qpa_within_participant_spread`, dataset `qarr` (development data). Mismatch: identical to the independent fits' record

**State:** validated on development data.

### `joint_refinement`

Joint multi-histogram refinement (refine_multi).

**Verified by:** `test_the_refined_wavelength_is_the_solo_cell_disagreement`, `test_the_diagnostic_reports_the_ppm_and_nothing_claims_rwp`, `test_the_cell_belongs_to_the_synchrotron`, `test_swapping_which_wavelength_is_held_measures_the_same_ratio`, `test_the_neutron_widths_leave_one_esd_at_every_start`

**State:** not yet validated.

### `parametric_refinement`

A parameter as a function of each pattern's coordinates.

**Verified by:** unit tests `tests/test_parametric_series.py::test_a_constant_declaration_is_refine_multi_bit_for_bit`, `tests/test_parametric_series.py::test_a_parametric_slope_recovers_a_known_expansion_within_its_esd`

**State:** not yet validated.

### `distortion_modes`

Distortion-mode amplitudes in a stated child.

**Verified by:** unit tests `tests/test_distortion_modes.py::test_lamno3_reproduces_table_13`

**State:** not yet validated.

### `subgroup_enumeration`

Subgroups: t- and k-subgroups, conjugacy classes, standard settings.

**Verified by:** unit tests `tests/test_subgroups.py::test_each_published_subgroup_is_present_with_its_transformation`, `tests/test_subgroups.py::test_pmmm_has_eight_fmmm_subgroups`

**State:** not yet validated.

## The matrix

### `tests/test_acceptance_extra_peaks.py`

WP-1103's design case on real data: the SRM 660c protocol, contaminated by injecting a two-line holder doublet **onto** two LaB6 reflections, then refined four ways — clean, ignore, declare, exclude.  The intruder is synthetic because no committed standard carries a holder line; the pattern it is injected into is real, which is what the cell bias has to be measured against, and every arm is referenced to the clean arm rather than to the certificate so the protocol's own offset cancels.  The result is more nuanced than the WP assumed and the rows say so: declaring recovers the clean cell (-1.0 ppm) and ignoring does not (+7.6 ppm, esd 8.7x, Rwp 3.7x), but **excluding also recovers it** (+0.6 ppm) for 4.8 % of the channels.  On this fixture the case for declaring is the retained channels and the measured intruder, not cell accuracy; a pattern with few reflections is where that changes, and LaB6 is not one.

#### `test_declaring_the_intruder_recovers_the_clean_cell`

`own_result` · dataset `srm660c`

**Claims:** declaring a sharp intruder that overlaps sample peaks recovers the cell the same data gives when the intruder is not there; ignoring it inflates the cell's reported esd about tenfold, and since WP-2002 moves the cell under a ppm, which no assertion orders

**Referenced to:** the *clean* arm of this same fixture, refined by the same protocol — not the NIST certificate, because what is being measured is what an unmodelled overlapping line does to the cell and its esd, and the protocol's own +24 ppm offset from the certificate is common to every arm and cancels

**Measured:** declare -0.1 ppm against the clean arm, ignore -0.4 ppm (bar 20 ppm on declare); the ignore arm inflates the cell esd 9.9x (2.14e-05 -> 2.11e-04 A) against a bar of 5x, and Rwp 4.4x (0.0874 -> 0.3837).  An esd scales with the misfit, so the inflation measures no bias (WP-2036). The lines go in at the clean fit's ticks, which follow the displacement since WP-1908, 0.039 deg higher than before; 1.9.0 read -0.2 and +6.3 ppm and 10.1x, before WP-2002's width twin hold (#1113) moved the ignore arm's cell

**Diagnostics:** `EXTRA_PEAK_ON_REFLECTION`

#### `test_the_excluded_regions_alternative_is_quoted_and_never_gated`

`own_result` `ceiling` · dataset `srm660c`

**Claims:** the excluded-regions alternative is reported beside the declared one, with its cell and the channels it costs, and neither arm is refused

**Referenced to:** the same clean arm; the ceiling is that nothing anywhere gates either choice, which is a property of the code rather than of a number

**Measured:** exclude +0.3 ppm for 256 of 5332 channels (4.8 %; 1.9.0 read +0.2) — i.e. on THIS fixture exclusion is as accurate as declaring, and the case for declaring is the retained channels and the measured intruder, not cell accuracy. A pattern with few reflections is where that changes, and LaB6 is not one

#### `test_the_declared_holder_lines_come_back_where_they_were_put`

`own_result` · dataset `srm660c`

**Claims:** the declared components recover the injected intruder's position, area and width, with esds

**Referenced to:** the injected truth, which is known exactly because the injection uses the package's own evaluator — so this row is a self-consistency check on real data and never a claim about a real holder

**Measured:** centres within 0.005 deg of 37.4814 and 43.6593 (bar 0.05); areas 125.7(37) and 123.5(19) against 120, 1.5 and 1.8 sigma high, which is the on-reflection degeneracy being real.  1.9.0 read areas 125.6(37) and 123.4(19)

#### `test_the_declared_peaks_are_ticks_and_not_background`

`identity` `ceiling` · dataset `srm660c`

**Claims:** a declared peak's positions join result.ticks and its curve stays out of result.y_background

**Referenced to:** the member contract's clause 2 (schemas/instrument.py): a member's aggregate is declared data, and for a peak it is the tick list, not the background

**Measured:** 4 ticks under the reserved key (two peaks x two emission lines); across 3xFWHM of each centre the reported background swings < 2 % of the peak standing on it

#### `test_the_arms_are_plotted_for_inspection`

`ceiling` · dataset `srm660c`

**Claims:** every arm writes obs/calc/diff and per-intruder zooms for visual inspection

**Measured:** 12 PNGs to tests/output/; the ignore arm's residual carries the whole injected doublet and the declare arm's is flat

### `tests/test_acceptance_lab6_cbn.py`

Two-phase QPA on an APS 11-BM histogram of NIST SRM 660b LaB6 mixed with cubic BN, with the standard's certified cell held so the second phase's is measurable against it.  There is no weighed composition, so every row here is cross-code against TOPAS, bounded by the 0.043 wt % spread between TOPAS's own two models of this pattern.  The suite's real subject is identifiability: Lorentzian FWHMs add, so freeing the instrument's X,Y alongside each phase's lor_size/lor_strain is one quantity split three ways, and the degenerate fit reaches a LOWER Rwp while its phase fractions move several sigma away from the reference.  An Rwp comparison would have chosen the wrong model.

#### `test_the_protocol_matches_before_any_number_is_compared`

`identity` `ceiling` · dataset `lab6_cbn`

**Claims:** Rexp reproduces TOPAS's, which is what shows both codes fitted the same channels under the same weights before any model is compared

**Referenced to:** Rexp depends only on the data, its esds and the free parameter count, so agreement is a protocol check and not a model one; TOPAS records 0.0529264 over start_X 5.1

**Measured:** Rexp 0.0529335 against TOPAS's 0.0529264, 1.3e-4 relative (P = 26 free here, the Gaussian triple held since WP-1930; Rexp moves with the parameter count and nothing else); 44895 of the file's 49496 channels fitted

#### `test_the_file_esds_are_used_rather_than_poisson`

`identity` `ceiling` · dataset `lab6_cbn`

**Claims:** read_pattern uses the file's propagated esd column rather than falling back to sqrt(I)

**Referenced to:** 11-BM sums twelve analyser crystals, so column 3 is a propagated esd; the package's weighting invariant says the file's column wins wherever there is one

**Measured:** data.sig() equals column 3 exactly; the ratio to sqrt(I) is 0.94 over the fitted range and 1.45 below 2.5 deg (0.98 is the whole-file median), i.e. angle-dependent in a way Poisson cannot be

#### `test_the_cbn_cell_agrees_with_topas_to_better_than_50_ppm`

`cross_code` `ceiling` · dataset `lab6_cbn`

**Claims:** the second phase's cell, measured against the standard's held certificate value and the beamline wavelength

**Referenced to:** TOPAS's two models give 3.616463 and 3.616466 A, 0.8 ppm apart; the 50 ppm band is cross-code consistency with headroom, the same status as the FAP suite's 300 ppm, and is NOT a truth claim about cBN's lattice parameter

**Measured:** a = 3.616521(17) A, +17 ppm from TOPAS (16.8 on 1.9.0 and on 1.10.0; this row read +16 before)

#### `test_the_one_free_coordinate_agrees`

`cross_code` `ceiling` · dataset `lab6_cbn`

**Claims:** LaB6's boron x, the only free positional parameter in either phase and therefore the whole structural content of the fit

**Referenced to:** TOPAS refines it to 0.19890; the 2e-3 band is tighter than this fit's own esd of 2.3e-3

**Measured:** x = 0.19836 (shared-broadening plan), 5.4e-4 from TOPAS; 1.9.0 read 0.19839 and 5.1e-4, before WP-2002's closing stage (#1085)

#### `test_rwp_is_worse_than_topas_and_the_reason_is_the_peak_shape`

`characterisation` `ceiling` · dataset `lab6_cbn`

**Claims:** rietx has no PVII, and on this instrument that costs about a factor two in Rwp -- recorded as a characterised deficit rather than asserted away

**Referenced to:** TOPAS fits PVII_Peak_Type with six free shape parameters; rietx offers TCHZ and a true Voigt. The band is one-sided and loose on purpose: it catches a regression, it does not certify the profile

**Measured:** Rwp 0.1686 against TOPAS's 0.0810 (0.1687 on 1.9.0); 88 % of chi2 sits in the 11 % of channels where the calculated Bragg part is more than half the total, mean delta/sigma +1.10 -- a shape deficit at the peak tops, not a background or scale one

#### `test_the_qpa_agrees_with_topas_within_its_own_esd`

`cross_code` `ceiling` · dataset `lab6_cbn`

**Claims:** two-phase QPA on a synchrotron histogram with the standard's cell held, referenced to TOPAS's own two-model interval

**Referenced to:** TOPAS's two shipped models of this histogram give LaB6 17.907 and 17.950 wt %, so the reference is an interval 0.043 wt % wide, not a number; no weighed composition exists and none is claimed

**Measured:** LaB6 17.787 +- 0.319 wt %, 0.120 outside the interval, i.e. 0.38 of its own esd; 1.9.0 read 17.791, 0.116 and 0.36

#### `test_the_lowest_rwp_is_the_worst_answer`

`characterisation` `ceiling` · dataset `lab6_cbn`

**Claims:** freeing per-phase Lorentzian broadening alongside the instrument's lowers Rwp and moves the QPA several sigma away from TOPAS

**Referenced to:** Lorentzian FWHMs add, so instrument X,Y and per-phase lor_size/lor_strain are one quantity split three ways; the expected signature is |rho| -> 1 and an Rwp that improves while the partition degrades

**Measured:** before WP-2002's width twin hold, rho = -1.000 (phases.0.lor_strain ~ instrument.profile.y); with X and Y held, Rwp 0.1377 against 0.1686 identifiable and LaB6 16.779(194) against 17.787(319) wt % -- the better Rwp is 5.8 sigma outside TOPAS's interval; 1.9.0 read Rwp 0.1289 and 16.850(192) wt %, 5.5 sigma

#### `test_the_correlation_diagnostic_separates_the_two`

`characterisation` `ceiling` · dataset `lab6_cbn`

**Claims:** neither HIGH_CORRELATION nor COVARIANCE_DIRECTION_DISCARDED fires on the identifiable fit, and on the plan that frees the phases' Lorentzian widths too the width twin hold takes X and Y and leaves no flat width (WP-2002)

**Referenced to:** a flat direction is held where it is exact, and the diagnostic channel stays silent on what the data determine

**Measured:** 0 findings on either plan, macOS arm64; X and Y held against both phases' twins from size_strain on; before WP-2002 COVARIANCE_DIRECTION_DISCARDED named all six widths on Linux x86-64 (WP-1930)

#### `test_the_twin_hold_leaves_no_flat_width_whatever_rounding_does`

`characterisation` `ceiling` · dataset `lab6_cbn` · survives 10 starts

**Claims:** at the 1e-14 nudges to w's start where rounding once decided whether the two flat broadening directions were flagged, the width twin hold takes X and Y, no specimen width is flat, and each has a finite nonzero esd (WP-2002; WP-1930 before it)

**Referenced to:** the Linux nightly from 0f30d584 on: no HIGH_CORRELATION on this fit, reproduced on macOS arm64 by 1e-14 nudges to w's start (six widths at an esd of 0)

**Measured:** macOS arm64, k = 0, 1, 7 since WP-2002: the hold at every nudge, cBN lor_strain 0.0354(35) (0.0008 is its esd before the Berar-Lelann factor of 4.4), LaB6's widths and cBN's lor_size on their 0 floor; before it, over k in {0, +-1, +-3, +-7, +-20, 50}, HIGH_CORRELATION in all ten and esds of 8.9 to 3420

**Diagnostics:** `HIGH_CORRELATION`, `COVARIANCE_DIRECTION_DISCARDED`

#### `test_the_shared_fit_reaches_one_minimum_on_every_platform`

`characterisation` `ceiling` · dataset `lab6_cbn`

**Claims:** the shared-broadening fit reaches one minimum whatever the platform's rounding, and its profile stage seeds nothing: refined in deg, profile.y leaves its floor on its own (WP-1938)

**Referenced to:** issue #832: the same tree reached Rwp 0.18696 on Linux and 0.16478 on macOS. The 2 % band about the two-platform measurement is the reporter's, and it fails at either old minimum

**Measured:** Rwp 0.168625, chi2_red 10.14803 on macOS arm64 since WP-2002's closing stage (#1085); 1.9.0 read 0.168656 and 10.15182 on macOS arm64 and Linux x86-64, agreeing to 1e-12 relative, and eight rounding-level changes to w's start on one machine gave the same digits

#### `test_the_fits_render`

`ceiling` · dataset `lab6_cbn`

**Claims:** both fits draw obs/calc/diff panels for looking at

**Referenced to:** existence, not a number -- a ceiling row

**Measured:** four PNGs written to tests/output/, lab6_cbn_shared.png, lab6_cbn_degenerate.png and a 5.1-12 deg zoom of each

### `tests/test_acceptance_srm660c.py`

The absolute lab anchor. NIST's own SRM 660c certification measurement, refined against the cell recomputed for this dataset's temperature block.

#### `test_srm660c_lab6_rietveld`

`certificate` `identity` `ceiling` · dataset `srm660c`

**Claims:** the absolute lab cell anchor: a, the Berar-Lelann esd inflation, the held zero shift, the sample displacement and the Ka2 ratio

**Referenced to:** NIST's cell recomputed for this dataset's 20.85 C block, 4.156780 A, under an explicitly interim +-2e-4 A band; the certificate's own +-8e-6 at 22.5 C is NOT claimed and the residual is a characterised cotTheta/sin2Theta aberration (divergence, tube tails, monochromator passband) fenced to the v2 FPA work

**Measured:** a = 4.156882(21) A, +24 ppm; Rwp 8.74 %, GoF 1.89; zero_shift held at exactly 0.0; displacement -0.0790 mm vs the CIF's -0.07877. The Gaussian width is real at all 60 reflections. 1.9.0 read +25 ppm (24.6 against 24.5), Rwp 8.75 % and -0.0791 mm, before WP-2002's closing stage (#1085). Before WP-1938 the width sat on its clamp at 12 reflections, and the fit read 4.156895 A, +28 ppm, Rwp 8.67 %

#### `test_srm660c_extinction_does_no_harm`

`characterisation` `ceiling` · dataset `srm660c`

**Claims:** primary extinction freed on a specimen that has none refines to zero and does not move the anchor

**Referenced to:** the cell must return to its own unextinguished value within the same 2e-4 A band; the extinction parameter itself is one-sided (< 1e-2 from a 1e-3 seed)

**Measured:** extinction exactly 0.0 from a 1e-3 seed; Rwp 0.0873248, a 4.1568830; the warm-extend path agrees with the whole plan to 1.6e-7 in Rwp and 1.7e-7 A in a, since the whole plan now runs its closing stage after the extinction stage and the warm-extended stage runs none (WP-2002, #1085); 1.9.0 read Rwp 0.0875138, a 4.1568823, and agreement to 9e-11 and 6e-10 A

### `tests/test_acceptance_srm676a.py`

The second absolute anchor, and the sharper one — but only on the axial ratio, where the lab d-scale systematic cancels.

#### `test_srm676a_corundum_cell_anchor`

`certificate` `characterisation` `identity` `ceiling` · dataset `srm676a`

**Claims:** c/a at certificate grade, the absolute axes only at lab-realistic grade, and the difference between them asserted to be a uniform d-scale systematic rather than a structural error

**Referenced to:** NIST SRM 676a certificate a = 4.759355(80), c = 12.99231(15) A (k = 2, 22.5 C).  c/a's relative k=2 uncertainty is ~21 ppm and the bar is 100 ppm — a small multiple of it.  The absolute bar is 600 ppm, nowhere near certificate grade, and the uniformity check |da - dc| < 1.5e-4 is what stops an esd laundering a many-sigma systematic

**Measured:** c/a +29 ppm; absolute axes -314 / -284 ppm with |da - dc| within 2.9e-5; Rwp 14.4 %, GoF 1.60 against a GoF floor of 1.5-1.9 for analytical-PSF lab fits (Cline 2015); 1.9.0 read +30, -312 / -282 ppm, Rwp 14.6 % and GoF 1.63

#### `test_the_two_descriptions_of_the_r_lattice_refine_to_the_same_cell`

`identity` `own_result` `characterisation` `ceiling` · dataset `srm676a` · survives 2 starts

**Claims:** that the two axis descriptions of corundum's R lattice are one lattice: the cell ties hold bitwise through a fit on rhombohedral axes, and the hexagonal image of that answer equals the independently-fitted hexagonal answer

**Referenced to:** ITA's rhombohedral/hexagonal relations for an R lattice (a_H = 2 a_R sin(alpha/2), c_H = a_R sqrt(3 + 6 cos alpha), V_H = 3 V_R) as the identity bar, and this package's own hexagonal-axes Le Bail fit of the same pattern from the same physical starting lattice as the own_result bar.  **No certificate claim**: the +-1e-3 band against SRM 676a is a sanity check that the fit found the right lattice, not a graded comparison — this is Le Bail with only w/u/v/x/y and lor_size free, deliberately looser than the Rietveld row above, which owns this specimen's certificate claim.  Registered because WP-1036 made the RHOMBOHEDRAL description representable at all; before it, c refined free of a and all three angles were locked, so this row could not have been written

**Measured:** a = b = c and alpha = beta = gamma bitwise after the fit; alpha walks 54.987 -> 55.287 from a 0.3 deg displacement (certificate 55.287); the two descriptions agree to 1.9e-9 (a) and 9.1e-9 (c) relative with Rwp equal to five decimals; V_H = 3 V_R to 1e-9; against the certificate a -326 / c -332 ppm, the same uniform d-scale systematic the Rietveld row measures at -314 / -284; Rwp 0.144, GoF 1.61.  1.9.0 read alpha 55.288, agreement 4.8e-10 and 4.9e-9, -328 / -336 ppm, Rwp 0.147 and GoF 1.64

### `tests/test_acceptance_powderline.py`

The only fixtures carrying **two** reference engines, and they disagree: 2668 ppm on a cell where the FAP band is 300, because GSAS-II reports its own fit singular. So the bar is the envelope the two engines bracket, and where this package falls inside it is the finding rather than the gate.

#### `test_drx_cells_land_inside_the_two_engines_envelope`

`cross_code` `ceiling` · dataset `powderline_drx33`

**Claims:** both phases' cells land inside the interval the two reference engines bracket, widened by the FAP band at each end

**Referenced to:** GSAS-II and TOPAS, both committed by upstream for this specimen, and the bar is the SPAN they leave rather than either of them: they differ by 2668 ppm on the cubic a and 386-1770 ppm on the monoclinic phase's four free parameters, so the WP's original +/-300 ppm against both is arithmetically impossible.  +/-300 ppm of slack at each end of the span is the FAP cross-code band applied where it can mean something

**Measured:** every free parameter inside the span with margin; the two engines' own gap is 386-2668 ppm

#### `test_drx_agrees_with_topas_far_more_closely_than_the_engines_agree`

`cross_code` `characterisation` · dataset `powderline_drx33`

**Claims:** this package sits on TOPAS's side of the two engines' disagreement by an order of magnitude, which is the finding the envelope gate cannot state

**Referenced to:** the two engines' own spread on the same five free cell parameters.  A one-sided claim on purpose: it asserts WHERE in the argument this answer falls, not that either engine is right.  GSAS-II reports two SVD singularities and 100 % Mustrain;mx/;i correlation on this recipe and returns a negative crystallite size for phase 1, so neither reference is truth here

**Measured:** worst deviation from TOPAS 96 ppm (bar 200) against an engine-to-engine gap of 2668 ppm (bar 1000); the ratio asserted under a tenth; 1.9.0 read 98 ppm

#### `test_drx_rwp_is_reported_beside_both_engines_and_gated_at_neither`

`ceiling` · dataset `powderline_drx33`

**Claims:** Rwp is a regression ceiling and is reported beside both engines' own figures, which are READ from their committed files

**Referenced to:** deliberately nothing: an Rwp comparison is never this package's evidence, and the two references disagree by 3.5 percentage points on this specimen anyway.  The assertion is a 0.15 ceiling plus a 0.01 band on TOPAS, which is a sanity check and not an accuracy claim

**Measured:** Rwp 7.322 % against TOPAS's 7.326 % and GSAS-II's 10.83 % (7.328 % on 1.9.0)

#### `test_drx_phase_scales_are_the_same_answer_as_topas`

`cross_code` · dataset `powderline_drx33`

**Claims:** the phase-scale RATIO agrees with TOPAS's, which is the quantity the recipe exists to produce and the only transferable one

**Referenced to:** TOPAS's own refined scales for the same two phases.  The absolute values are not comparable and are not compared: each code normalises the scale its own way (GSAS-II converges four orders from TOPAS on the LaB6 fixture), which is why read_recipe re-seeds a recipe's scale rather than carrying it.  20 % relative, sized to the ratio's own dependence on the size/strain valley both engines reported singular

**Measured:** within the 20 % band; the two engines' size/strain answers for the same specimen differ by six orders of magnitude

#### `test_lab6_cell_is_held_exactly_where_the_recipe_put_it`

`identity` · dataset `powderline_lab6`

**Claims:** a cell the recipe holds comes back at exactly the value the recipe stated, matching both engines bit for bit

**Referenced to:** the recipe's own 4.15682 A, which both reference engines also report unchanged with esd 0.  1e-9 A, an identity bar: a held parameter that moved would be a translation bug, not a refinement result

**Measured:** exact against both engines' unit_cell_report.csv

#### `test_lab6_drawn_peak_widths_match_the_reference_profile`

`cross_code` `characterisation` · dataset `powderline_lab6`

**Claims:** the fitted profile's peak widths reproduce GSAS-II's own calculated profile, reflection by reflection, despite three stated model differences that make the width COEFFICIENTS incomparable

**Referenced to:** the FWHM of GSAS-II's committed y_calc minus its y_bkg, measured on the first ten reflections.  Widths rather than U V W X Y Z because the reference model carries a constant Lorentzian Z this package has not got, a NEGATIVE Y whose gamma is clamped at a 0.001 centideg floor on 26 of its 49 reflections, and GSAS-II's own 1 um / 1000 microstrain fill for the recipe's null size/strain.  The bar is 5 %, sized above those three rather than to the profile's own precision

**Measured:** median 0.5 %, worst 1.0 % over ten reflections; 1.9.0 read 1.2 % and 2.3 %, before WP-2002's width twin hold and floor removal (#1113)

#### `test_lab6_rwp_is_reported_beside_both_engines`

`ceiling` · dataset `powderline_lab6`

**Claims:** Rwp is a regression ceiling, reported beside both engines' figures read from their own committed files

**Referenced to:** nothing, for the reason the DRX row gives; a 0.12 ceiling and a 0.01 band on TOPAS, which shares neither Z nor the negative-Y clamp with GSAS-II

**Measured:** Rwp 8.410 % against TOPAS's 8.519 % and GSAS-II's 6.53 %; 1.9.0 read 8.801 %, before WP-2002's width twin hold and floor removal (#1113)

#### `test_lab6_declares_the_three_model_differences_it_has`

`characterisation` · dataset `powderline_lab6`

**Claims:** every place this fit differs from the reference engine's model is SAID at read time rather than absorbed silently

**Referenced to:** no numeric bar: the assertion is that three diagnostic codes fire.  This is the row that keeps the Rwp gap above from being a mystery — a difference nobody declared is indistinguishable from a bug

**Measured:** RECIPE_FLAG_DROPPED, RECIPE_ENGINE_DEFAULT_DECLINED and RECIPE_BACKGROUND_PEAK_DEGENERATE all present

**Diagnostics:** `RECIPE_FLAG_DROPPED`, `RECIPE_ENGINE_DEFAULT_DECLINED`, `RECIPE_BACKGROUND_PEAK_DEGENERATE`

#### `test_lab6_hump_is_the_degenerate_direction_both_engines_found`

`characterisation` · dataset `powderline_lab6`

**Claims:** a background peak the recipe declares wider than its own fitted range is a degenerate direction, and this package reaches the same verdict both reference engines did

**Referenced to:** the two engines' own answers for the same peak, from opposite ends: GSAS-II let it run to 8.77e10 deg 2theta at esd 0 (off the pattern, unmeasured) and TOPAS kept it at 1.63 deg with an esd 188x its own value.  Here it correlates with the low-order background at |rho| = 1 and its stage spends its budget.  A measured failure recorded as a result: the recipe is over-parameterised and no fit of it can say otherwise

**Measured:** HIGH_CORRELATION on the peak against the background, and the last stage freeing it at max_iter: since WP-2002 that is the closing stage, and the declared extra_components stage converges at the intermediate tolerance (1.9.0: the extra_components stage at max_iter); GSAS-II's own committed position 8.77e10 with esd exactly 0

**Diagnostics:** `HIGH_CORRELATION`, `STAGE_MAX_ITER`

#### `test_the_written_tables_reproduce_the_answer_they_came_from`

`identity` · dataset `powderline_drx33`

**Claims:** the four tables written back out carry the same answer the fit produced -- an Rwp recomputed from the written profile reproduces the result's own

**Referenced to:** this fit's own numbers, so the bar is floating point: 1e-8 on a cell parameter and 1e-6 on an Rwp recomputed from the file's y_obs, y_calc and y_weights columns.  A writer that dropped or reordered a channel would fail it

**Measured:** orders inside both bars

### `tests/test_acceptance_fap.py`

The one cross-code comparison. GSAS-II's converged fluorapatite tutorial, with its protocol mirrored parameter for parameter.

#### `test_fap_lab_rietveld_matches_gsas`

`cross_code` `characterisation` `identity` `ceiling` · dataset `fap`

**Claims:** agreement with GSAS-II's converged fit on the same channels under the same protocol, with the residual cell offset asserted to be a uniform d-scale convention difference

**Referenced to:** GSAS's own FAP.EXP: Rwp 0.1005, Rp 0.0766, a = 9.371724(36), c = 6.885867(37) A on 5750 channels after its EXC 2 record.  Bars are rel=0.10 on the R-factors and 300 ppm on the cell — a convention-aware band, not 1e-4 A ground truth.  The esd window is one-sided on purpose: ours carry Berar-Lelann inflation and GSAS's do not

**Measured:** Rwp 0.0928 vs 0.1005, Rp 0.0714 vs 0.0766, cell +84/+84 ppm with the two agreeing inside 1e-4, at 6.3e-7 (the uniformity claim); 1.9.0 read Rwp 0.0925, Rp 0.0712, +83/+82 ppm and 2.8e-7, before WP-2002's closing stage (#1085); channel count 5750 exactly (GU GV GW read as a Gaussian variance, #735; before: Rwp 0.0970, Rp 0.0774, cell +114/+112 ppm)

#### `test_fap_lorentzian_matches_gsas_lx_on_gsas_own_model`

`cross_code` `characterisation` · dataset `fap`

**Claims:** the sample Lorentzian rietx refines against GSAS's own LX, with the two things GSAS's function 2 lacks (axial divergence, the preset's instrument X) removed, and with the held Gaussian read both as the variance the manual states and as the FWHM-squared it was once read as

**Referenced to:** FAP.EXP's LX = 3.35183 centideg = 0.0335 deg, a fitted output under held GU GV GW.  Bar rel=0.05 on the variance reading; the old reading must miss by more than 25 %, and the corrected one must have the lower Rwp

**Measured:** lor_size 0.0323 (-3.6 %, Rwp 0.0958) with the variance reading; 0.0495 (+48 %, Rwp 0.1096) with the old one; 1.9.0 read 0.0326 (-2.7 %, Rwp 0.0953) and 0.0497 (Rwp 0.1090)

#### `test_tying_the_similar_atoms_bisos_buys_precision`

`own_result` `identity` `characterisation` `ceiling` · dataset `fap`

**Claims:** a user constraint on three chemically equivalent sites reduces the parameter count and tightens the esd, without moving the values the free refinement measured

**Referenced to:** the same protocol's own free fit on the same 5750 channels, the only difference being the tie.  The esd bar is referenced twice: to the best of the three free esds (0.1078 A^2) and to their inverse-variance combination (0.0769), which is what the constraint has to beat to have recovered the information rather than merely divided by root-N.  The identity half is that the three tied rows carry the *same* value and esd to 1e-12, since they are one parameter.  Rwp is deliberately not a reference value: it moves by 0.05 % of itself, so no bar on it could distinguish a good constraint from a bad one

**Measured:** 20 -> 18 free parameters, 287.5 -> 319.4 points per parameter; B(O) 0.3469(1526) / 0.6005(1610) / 0.5137(1086) free against 0.4985(763) tied, the three free values 0.99 / 0.63 / 0.14 of their own esds from the tied value (esds with Berar-Lelann eqs (10)-(12), #674); the four untied Biso sites move by < 0.5 sigma.  1.9.0 read 0.3647(1513) / 0.6016(1590) / 0.5377(1078) against 0.5150(754), 0.99 / 0.54 / 0.21

#### `test_a_pawley_fit_past_the_bvls_cut_converges_every_stage`

`own_result` `ceiling` · dataset `fap` · survives 5 starts

**Claims:** the default Pawley plan, whose block crosses lm.BVLS_MAX_COLUMNS, converges every stage under the default driver, and lands no higher than TRF does from the same start

**Referenced to:** this package's own TRF fit on the same channels and plan: Rwp 0.07826556-0.07992336 over five starts 1e-14 apart.  The bar, Rwp < 0.0790, sits under BCCG's capped 0.0804 and above LM's answer; convergence of every stage is the ceiling half (WP-1953)

**Measured:** Rwp 0.0786244 at the shipped start, every stage converged, the closing stage included, 329 columns in the final model (one start, macOS arm64).  1.9.0 read 0.0782443 at that start and 329 columns; on 2026-10-12 it read 0.07824432 on all five starts, 343 columns at the profile stage and 0.8 s idle (macOS arm64)

#### `test_the_file_states_a_wider_free_set_than_this_plan`

`cross_code` `identity` · dataset `fap`

**Claims:** the free set this plan refines against the free set GSAS's own file states, with the difference named rather than implied

**Referenced to:** FAP.EXP's own refine flags, read by rx.read_gsas_exp and converted to rietx dot-paths through to_structure.  The file states 28 variables in its REFN GDNFT record, and the flags reconstruct that exactly: 2 cell + 12 coordinate DOFs + 7 Biso structural, plus 1 histogram scale, 3 background terms and 3 profile terms.  This is an identity check against a number the file states somewhere else, not a tolerance

**Measured:** this plan frees 20 parameters and GSAS freed 28.  It leaves out the 12 coordinate DOFs, which no stage here turns on, and frees four more: axial_sl, which GSAS held, and a six-term Chebyshev where GSAS refined three terms of its function 5.  Every other structural parameter the file frees, this plan frees too.  Freeing the DOFs measured 2026-10-08: Rwp 0.092498 -> 0.092314, cell +82.5/+82.3 -> +82.3/+81.9 ppm, no wall-clock change, still converged — so closing the gap is nearly free and is a deliberate change with its own numbers rather than a silent one

### `tests/test_acceptance_nac.py`

The synchrotron vertical slice, and the FitReport's impurity claim: CaF2 is found from unmatched peaks rather than declared.

#### `test_nac_lebail_then_rietveld`

`own_result` `characterisation` `ceiling` · dataset `nac`

**Claims:** Le Bail then two-phase Rietveld; the cell is checked much more tightly against our own Le Bail pass than against the literature, and the CaF2 impurity is found by the report rather than declared

**Referenced to:** literature a = 10.2496-10.2506 A (high-accuracy powder) and 10.257(1) (Courbion & Ferey 1988) under a 2e-3 A band that allows for the beamline wavelength calibration; the Rietveld-vs-Le Bail agreement is held to 5e-4 A

**Measured:** a = 10.251216(39) A, Rwp 9.3 %; CaF2 lands at 5.4646 A; 1.9.0 read the esd as 40

#### `test_nac_extinction_on_the_main_phase_is_bounded_and_unbiasing`

`identity` `characterisation` `ceiling` · dataset `nac`

**Claims:** extinction freed only on the well-determined phase stays bounded and does not bias the cell; the impurity's stays exactly zero

**Referenced to:** the correction's own size (min E > 0.8, i.e. at most ~12 % on the strongest line) and the unextinguished cell.  The impurity extinction is exact-zero because it is never freed — freeing it was measured to run away to E ~ 0.31

**Measured:** min E > 0.8 on the main phase; phases[1].extinction == 0.0 exactly

#### `test_nac_termination_view_golden_shape`

`ceiling` · dataset `nac`

**Claims:** Refinement.summary()'s shape (WP-1302: sections, labels, ordering) survives untouched when only a number moves — no accuracy claim, a text-shape regression bar only, referenced to a masked golden file

**Measured:** 37 lines (summary(deliverable='qpa') on the two-phase Rietveld fit), against a golden file of 39 that this tree fails: the diagnostics header now counts levels and an info finding prints on one line (WP-2037 owns it); str(result) alone is 14.  1.9.0 read 29 and 12, matching its golden

### `tests/test_acceptance_qpa_roundrobin.py`

Quantitative phase analysis against weighed truth, at tolerances referenced to what the round robin's participants achieved.

#### `test_read_prn_two_column_ascii`

`identity` · dataset `qarr`

**Claims:** the two-column .prn reader contract: grid, step, no esd column

**Referenced to:** the files themselves — 7251 points from 5 to 150 deg at 0.02 deg, to 1 microdeg because cpd-1e truncates its ordinates to seven characters; sigma is None so the Poisson fallback is what weights these fits

**Measured:** exact

#### `test_sample1_fractions_within_participant_spread`

`spread` `identity` `ceiling` · dataset `qarr`

**Claims:** weight fractions on the eight sample-1 mixtures, and the closure of the fraction sum

**Referenced to:** the weighed composition is truth; the tolerance is the published participant spread (Madsen 2001 Fig. 2), 6.0 wt % for majors and 2.0 for traces below 5 wt %.  Never sigma(W): those esds are 0.1-0.7 wt %, several times below the measured errors

**Measured:** worst 5.10 wt % (1f zincite), traces <= 1.3, RMS 2.30; closure exact to 1e-6.  1.9.0 read 4.92, 1.1 and 2.19; WP-2002's closing stage (#1085) took them to 5.08 and 2.26 and its width twin hold (#1113) to 5.10 and 2.30

#### `test_sample1_bias_has_the_dispersion_shape`

`characterisation` · dataset `qarr`

**Claims:** the sample-1 residual bias is not noise: its sign is fixed per phase and its shape is the one neglected anomalous scattering predicts

**Referenced to:** the per-phase Bragg-power ratios from f' at Cu Ka (1.0542 corundum / 0.8441 zincite / 1.0728 fluorite), which set the signs; WP-0502 separately excluded surface roughness as the competing explanation, which is what makes the attribution single-valued

**Measured:** zincite mean < -1.0, corundum mean > +0.5, fluorite |mean| < 2.0 wt %

#### `test_a_supported_trace_phase_is_never_held`

`identity` · dataset `qarr`

**Claims:** a phase the data *can* see is refined exactly as before the unsupported-phase hold existed (WP-1301)

**Referenced to:** cpd-1c is 1.36 wt % fluorite by weighing — a trace phase that is genuinely there, and the counter-example params.vector.cell_window's docstring is built on: windowing every phase rather than only the invisible ones cost that fit its iteration budget and 2.7 wt % of its corundum. A hold is stronger than a window, so the same restriction has to hold, and it is asserted on the record rather than on the outcome

**Measured:** no phase path held and none released across all nine stages, the closing stage included, and no PHASE_UNCONSTRAINED; from sample_broadening on the width twin hold holds U, X and Y, which the test excludes (WP-2002; 1.9.0 ran eight stages and held nothing); the fractions are the row above's

**Diagnostics:** `PHASE_UNCONSTRAINED` asserted *absent*

#### `test_sample2_brucite_march_dollase`

`spread` `characterisation` `identity` `ceiling` · dataset `qarr`

**Claims:** platy brucite is detected as preferred orientation rather than absorbed into the fractions

**Referenced to:** participant spread again on the fractions; the March coefficient is judged as physics (r < 1 means platy, and 0.4 < r < 0.9 is far enough from the r = 1 identity to be a detection rather than a fitted nothing)

**Measured:** r ~ 0.67; worst fraction 3.0 wt % (zincite); H Biso held at exactly 2.5; 1.9.0 read 2.8 wt %

#### `test_sample2_brucite_spherical_harmonics`

`spread` `characterisation` `identity` · dataset `qarr`

**Claims:** the spherical-harmonics texture carries brucite's platy habit as well as March-Dollase does, at orders 4 and 6 (WP-1960)

**Referenced to:** participant spread on the fractions, the bar March-Dollase meets on the same protocol; C2,0 is judged as physics (positive is platy with psi = 0 on a reflection plate, and five esd from the C = 0 identity is a detection)

**Measured:** worst fraction 3.71 wt % at order 4, 2.91 at order 6, against March-Dollase's 3.01; C2,0 1.40(4) and 1.39(5); J 1.45 and 1.46; min P 0.47 and 0.39.  Measured by WP-1960 before WP-2002: 3.41, 2.71 and 2.80; the closing stage (#1085) and the width twin hold (#1113) each moved them

#### `test_sample4_microabsorption_characterised_not_hidden`

`characterisation` `ceiling` · dataset `qarr`

**Claims:** the round robin's designed Brindley-defeating sample fails in the documented direction, the muR fence fires, and the correction moves two of three phases the right way

**Referenced to:** **no accuracy band is claimed** — this specimen is meant to defeat the correction.  What is asserted is the sign and rough size of each error, that BRINDLEY_OUTSIDE_REGIME names magnetite, and that tau < 1 < tau holds across the absorption contrast.  Zircon is deliberately NOT asserted to improve (measured -9.1 to -9.3)

**Measured:** corundum +24, magnetite -15, zircon -9 wt %

**Diagnostics:** `BRINDLEY_OUTSIDE_REGIME`

### `tests/test_acceptance_dispersion.py`

The same round robin with anomalous scattering applied — a pre-registered, parameter-free prediction about numbers already recorded in the v0.3 milestone.

#### `test_sample1_fractions_beat_the_dispersion_free_fit`

`prediction` `spread` `identity` `ceiling` · dataset `qarr`

**Claims:** with f' and f'' applied, every sample-1 mixture meets a tolerance the dispersion-free fit could not

**Referenced to:** the weighed composition at 2.5 wt %, tightened from the participant spread's 6.0/2.0 — the tightening IS the claim, and it was written down before the refits

**Measured:** worst 1.37 wt % (was 5.13); 1.20 on 1.9.0, before WP-2002's closing stage (#1085, 1.34) and width twin hold (#1113)

#### `test_the_microabsorption_shape_was_mostly_dispersion`

`prediction` `own_result` · dataset `qarr`

**Claims:** the signed bias v0.3 attributed to microabsorption collapses when dispersion is applied — a v0.3 conclusion re-derived, not merely a number improved

**Referenced to:** the frozen V03_ERRORS table (the eight measured signed wt % errors from milestones/v0.3.md), phase by phase.  The prediction was parameter-free and beat itself: predicted RMS 0.83, measured 0.69 (0.62 on 1.9.0)

**Measured:** RMS 2.26 -> 0.69 wt % (0.62 on 1.9.0, before WP-2002's closing stage and width twin hold); zincite's -1 wt % mean bias goes to |mean| < 1.0 (-0.63)

#### `test_zincite_cell_does_not_move`

`own_result` · dataset `qarr`

**Claims:** dispersion is an intensity correction and must not move a non-centrosymmetric structure's cell

**Referenced to:** the same fit with the block off; 0.1 of the cell's esd on a and c, the suite's start-invariance bar, since WP-2002's width twin hold (1e-5 A before, an identity bar): the hold keeps the X/Y split the QPA plan's instrument stage lands on, and dispersion moves that split

**Measured:** a 9.3e-6 and c 1.5e-5 A apart (0.04 of c's esd of 3.7e-4 A); 1.9.0 read 2.7e-7 and 8.5e-7 A

#### `test_zincite_oxygen_adp_becomes_physical`

`characterisation` · dataset `qarr`

**Claims:** the sharpest single dispersion result: B(O) comes off its floor once Zn's missing f' stops being absorbed by a displacement parameter, while Rwp barely moves

**Referenced to:** physical plausibility, not a measured value — B(O) below 0.1 A^2 is a parameter pinned on a bound, and 0.2-1.2 is the range an oxide oxygen actually occupies.  Rwp is asserted only one-sided, because this is exactly a case where the fit statistic does not see the fix

**Measured:** B(O) 0.018 -> 0.432 A^2; 0.047 -> 0.456 on 1.9.0, before WP-2002's closing stage (#1085) and width twin hold (#1113)

#### `test_srm660c_lattice_parameter_is_untouched`

`identity` · dataset `srm660c`

**Claims:** the absolute anchor survives the flip: a does not move when dispersion is applied

**Referenced to:** the dispersion-off baseline, at 2e-6 A — well inside the 21e-6 A esd, so the anchor is safe either way

**Measured:** a = 4.156882 A both ways

#### `test_srm660c_displacement_parameters_absorb_the_change`

`characterisation` · dataset `srm660c`

**Claims:** where the change lands instead: the displacement parameters, by 12 % and 22 %

**Referenced to:** the dispersion-off baseline; floors on the size of the move (>0.02 and >0.05 A^2) plus a physical band on the result, which is a characterisation and not an accuracy claim — no certified Biso exists for this specimen

**Measured:** B(La) and B(B) move ~12 % / ~22 %; Rwp 8.743 -> 8.721 % (8.751 -> 8.730 % on 1.9.0)

#### `test_the_neglect_diagnostic_clears_when_the_block_is_on`

`identity` · dataset `srm660c`

**Claims:** 'off' is loud: the neglect diagnostic is present dispersion-off and absent dispersion-on

**Referenced to:** the diagnostic set itself — set membership, both directions

**Measured:** exact

**Diagnostics:** `DISPERSION_NEGLECTED`, `DISPERSION_NEGLECTED` asserted *absent*

### `tests/test_acceptance_capillary.py`

A correction that provably cannot improve the fit, on real data. The whole of its content is a predicted shift in every displacement parameter.

#### `test_estimated_mu_r_matches_the_documented_capillary`

`characterisation` `identity` · dataset `srm660a_capillary`

**Claims:** muR from composition and the documented bore lands in the physically plausible band, and the public estimator agrees with what the refinement resolved internally

**Referenced to:** the beamline's documented 0.81 mm Kapton bore and a packing fraction of 0.35-0.6, which spans muR 0.47-0.81; the estimator/resolver agreement is floating-point (rel=1e-9)

**Measured:** muR 0.679, method rouse_cylinder, not out of range

#### `test_capillary_absorption_is_an_exact_reparameterisation`

`prediction` `identity` · dataset `srm660a_capillary`

**Claims:** the headline: applying the correction provably cannot change the fit, and the whole of its content is a predicted shift in every Biso

**Referenced to:** the analytic prediction DeltaB = c(muR)*lambda^2/2, computed before the refits.  Rwp and the cell are held to 1e-6 and 1e-9 A **between two of our own fits** — referenced to floating point, not to any external value, because Rouse's expression factors exactly into a Debye-Waller shape

**Measured:** Delta Rwp -3.4e-14, Delta a +2.0e-14 A, every Biso +0.016875 against a predicted 0.016875 (to 3e-9); 1.9.0 read 4.0e-9, -1.8e-11 A and +0.01687, before WP-2002's closing stage (#1085)

#### `test_fit_quality_and_the_circular_cell`

`characterisation` `ceiling` · dataset `srm660a_capillary`

**Claims:** the fit is sound and its cell agrees with SRM 660a — recorded as consistency, explicitly NOT as an anchor

**Referenced to:** **circular by construction**: 11-BM calibrated lambda against LaB6 itself (the file's own calibration header), so this cell reproduces the standard whatever the code does.  The 1e-4 relative band is a divergence guard, deliberately generous

**Measured:** 16 ppm from the SRM 660a certificate; Rwp 8.81 % (8.88 % on 1.9.0)

#### `test_the_absorption_shift_is_independent_of_dispersion`

`prediction` `identity` `characterisation` · dataset `srm660a_capillary`

**Claims:** the absorption identity still holds on a dispersion-on model, and the two corrections are separable in size and sign

**Referenced to:** the same analytic DeltaB prediction, re-measured on top of dispersion; plus a sign/magnitude cross-check that dispersion moves B(La) the other way and 2.6x further

**Measured:** Delta B still 0.016875 to 1e-5 (4.2e-9; 3.5e-6 on 1.9.0); dispersion moves B(La) by about -0.044 A^2

### `tests/test_acceptance_sequential.py`

A warm-started chain over the round robin: what changes when only the starting point changes.

#### `test_chained_qpa_within_participant_spread`

`spread` `identity` · dataset `qarr`

**Claims:** a warm-started chain meets the unchained suite's criterion, unchanged

**Referenced to:** the QPA suite's own MAJOR_TOL/TRACE_TOL, imported rather than restated, so what differs between the two suites is only the chaining

**Measured:** identical to the independent fits' record

#### `test_chained_agrees_with_independent_fits`

`own_result` · dataset `qarr`

**Claims:** chaining changes the starting point, not the answer

**Referenced to:** this package's own independent fits under the same protocol, at 1 wt % and 0.005 in Rwp — generous rather than tight, and framed in participant-spread units because that is what the quantity means

**Measured:** mean Rwp 0.1282 chained against 0.1258 independent: since WP-2002's width twin hold (#1113) every warm-started pattern lands 0.0020-0.0043 above its independent fit (bar 0.005); chained and independent weight fractions within 0.07 wt %.  1.9.0 read 0.1278 either way, within 0.07 wt %

#### `test_cells_are_stable_across_the_series`

`characterisation` · dataset `qarr`

**Claims:** a trajectory that should be flat is flat: no trend imprinted by the chaining order

**Referenced to:** the trajectory's own spread — a slope is only a finding if it exceeds the scatter it is drawn from.  This is the shape check that separates a measured trajectory from an ordering artefact

**Measured:** per-phase spread < 20e-4 A with no monotone drift

#### `test_warm_start_iteration_cost_is_reported`

`characterisation` `ceiling` · dataset `qarr`

**Claims:** the headline iteration saving is printed and only divergence is gated — the number is a finding, not a bar

**Referenced to:** **deliberately not asserted.** Before WP-1123's intermediate_ftol: 2863 iterations unchained, 1623 re-walking the staged plan warm, 904 with the plan collapsed; the carry-glob hypothesis was refuted at 838. Gating a speed number would turn machine noise into a test failure

**Measured:** 408 restricted and 655 carrying everything vs 1255 iterations, at mean Rwp 0.1282 for both chains against 0.1258 (2026-10-25, macOS arm64, after WP-2045 converged the last declared stage); 1.9.0 read 403 vs 1214 at identical mean Rwp (365 carrying everything).  1.10.0's hostile series did not finish (next row)

#### `test_the_hostile_series_exercises_the_reseed_fence`

`identity` `characterisation` · dataset `qarr`

**Claims:** the reseed fence's accounting is exact, the escalation ladder is only ever climbed as a prefix, and a reseed never leaves the fit worse than the warm start it rejected

**Referenced to:** internal consistency: the SEQUENTIAL_RESEED diagnostic count must equal the number of entries flagged reseeded, exactly; every entry's rungs_tried must be a prefix of the ladder and contain the rung it kept.  The fence never fired on the hostile series — the collapsed refit recovers a bad warm start within the fit — so it is insurance, pinned by unit tests rather than by this suite

**Measured:** exact accounting; zero reseeds on the hostile series, every pattern after the first kept on its warm rung, and no kept rung above the Rwp fence (2026-10-25, macOS arm64, after WP-2045; 1.9.0 the same).  1.10.0's hostile series did not finish, spending over 50 CPU minutes in the closing stage that follows cpd-1b's warm rung (Rwp 0.760)

**Diagnostics:** `SEQUENTIAL_RESEED`, `SEQUENTIAL_UNRECOVERED`, `SEQUENTIAL_RWP_OUTLIER`

#### `test_the_first_rung_bound_moves_no_accepted_value`

`identity` · dataset `qarr`

**Claims:** FIRST_RUNG_FACTOR is answer-invariant on the hostile series: the chain with WP-1127's first-rung bound and the chain without it report the same values, esds, rungs, fences and codes, and no kept first rung reaches the budget the bound would set

**Referenced to:** the same chain with first_rung_factor=None, to the bit; the margin against FIRST_RUNG_FACTOR itself (WP-2003). It verifies the bound and validates nothing, the reference being rietx's own unbounded chain

**Measured:** bit-identical; kept first rungs past the armed point 0.064-0.080x the running maximum against a factor of 3.0 (2026-10-25, macOS arm64, after WP-2045; 0.34-0.39x on 2026-10-24, Linux x86-64, with cpd-1b's runaway in the chain)

#### `test_the_hostile_pairs_warm_stage_stops_short_of_the_runaway`

`ceiling` · dataset `qarr`

**Claims:** a regression bar, no accuracy claim: cpd-1b's warm stage, carried from cpd-1a's answer, ends with axial_sl under 1 and is kept on its warm rung, and no closing compile sees a ratio above 1

**Referenced to:** real instruments sit near 0.01-0.05; the runaway it guards against reached 557.8 on 1.10.0 (WP-2045), so the bar of 1 is loose on purpose

**Measured:** axial_sl 0.0082 at Rwp 0.1398, against 0.1373 for the independent fit (2026-10-25, macOS arm64); the parent tree fails it at 557.8

#### `test_the_hostile_pairs_runaway_reports_its_stale_windows`

`ceiling` · dataset `qarr`

**Claims:** a regression bar, no accuracy claim: under the tolerance schedule before WP-2045, cpd-1b's warm stage ends with its frozen windows dropping over half the Bragg intensity, and every cpd-1a stage under the 2 % each window may drop

**Referenced to:** the stage's own window_area_tol, 2 %, is the reporting threshold; the bar of 0.5 on the runaway is loose on purpose

**Measured:** 73.4 % on cpd-1b's warm stage at axial_sl 557.8, and at most 1.32 % on cpd-1a (2026-10-25, macOS arm64, WP-2047)

#### `test_series_exports`

`identity` · dataset `qarr`

**Claims:** the series CSV and trajectory plot exist with the declared columns and one row per pattern

**Referenced to:** the export contract itself

**Measured:** exact

### `tests/test_acceptance_stephens.py`

Anisotropic strain, and the matrix's canonical inadmissibility result — an improvement both statistical tests bless and the physics rejects.

#### `test_brucite_improvement_is_justified_but_leaves_the_physical_cone`

`characterisation` · dataset `qarr` · survives 4 starts

**Claims:** an Rwp improvement that both statistical tests bless is rejected by a physics guard, on real data — the matrix's canonical inadmissibility row

**Referenced to:** **no accuracy claim.** Hamilton at alpha = 0.05 and Delta BIC both pass at N/f^2 (WP-1417), while at most one of the four S_HKL coefficients lies 2 sigma from zero; the strain-variance cone sigma^2(M) >= 0 fails on 7 of 43 reflections, so STEPHENS_STRAIN_NOT_POSITIVE fires and no S_HKL is quotable.  The r ~ 0.65 March coefficient is checked against WP-0310's own measurement on the same material

**Measured:** Rwp 18.64 -> 18.04 %, Delta BIC +12.5 at N/f^2 (N_eff 473, f 3.914; +448.0 at raw N), 3 parameters added, anisotropy at its 1e6 cap (narrowest direction at zero strain; bar 3.0); every stage of the TRF fit converges.  1.9.0 read 18.64 -> 17.88 % and +21.0 (+578.4), before WP-2002's width twin hold and floor removal (#1113); this module declines the closing stage

**Diagnostics:** `STEPHENS_STRAIN_NOT_POSITIVE`

#### `test_corundum_is_reported_isotropic`

`characterisation` `ceiling` · dataset `qarr`

**Claims:** the control: an isotropic specimen must be reported isotropic, and must never leave the cone

**Referenced to:** the Layer-1 strain diagnostic's own verdict (not detected, R^2 < 0.5) plus the derived pattern count for R-3c; the anisotropy ratio of an insignificant fit carries no bar since WP-2002, having been a runaway guard at 6

**Measured:** R^2 = 0.079, anisotropy at its 1e6 cap, 4 patterns, 64 reflections, at chi2_red 2.65119: the width twin hold (#1113) keeps the instrument's Y, a reflection's specimen width clips to zero, and the ratio is infinite (lor_size 0.015).  1.9.0 read R^2 0.11 and 1.49x at 2.65202 (lor_size 0.043), and the closing stage (#1085) alone gave 4.52x, so the ratio rides the Lorentzian split's flat direction; never leaves the cone at any seed

#### `test_corundum_block_is_inert_and_hamilton_blesses_it_only_at_raw_n`

`characterisation` `identity` · dataset `qarr`

**Claims:** freeing the block on an isotropic specimen is inert, and both statistics say so at N/f^2 while Hamilton at the raw channel count blesses it

**Referenced to:** Hamilton's R-ratio test at alpha = 0.05 and raw N **passes** a 0.25 % chi^2 improvement from three inert parameters, exactly as it passes brucite's 8.0 % one, on 7251 channels.  At N/f^2 (issue #270, WP-1417) both tests refuse it: Delta BIC -18.0 against brucite's +21.0.  The certificate-grade c/a is asserted not to move (rel=1e-4)

**Measured:** Delta BIC -18.1 at N/f^2 (-18.0 on 1.9.0) and Hamilton refuses; Hamilton at raw N says justified; c/a unmoved

#### `test_constrained_solver_keeps_brucite_inside_the_cone`

`characterisation` · dataset `qarr` · survives 4 starts

**Claims:** under solver='lm' the cone is carried as a linear inequality and brucite comes back inside it

**Referenced to:** the physics constraint itself: sigma^2(M) > 0 on all 43 reflections, with the optimum sitting on the cone face.  Rwp is bounded loosely.  Before WP-1938 it was WORSE than the unconstrained TRF fit's.  On 1.8.0 that TRF fit stopped at max_iter above it, and since WP-1953 it converges below it again

**Measured:** 0 of 43 violations; Rwp 0.18147 against TRF's 0.18042 (0.17995 against 0.17877 on 1.9.0; 0.17946 against 0.17844 before WP-1938)

#### `test_unconstrained_solver_leaves_the_cone_on_the_same_data`

`characterisation` · dataset `qarr` · survives 4 starts

**Claims:** the control for the row above: the TRF driver its fixture names, same data, leaves the cone

**Referenced to:** the same cone test, opposite direction — at least 5 of 43 reflections violating, plus the guard diagnostic

**Measured:** 19 of 43 violations at the pinned seed; 19/19/19/17 across the four-seed sweep (400, 800, 1600, 3000), every fit converged (7 and 15/7/19/24 on 1.9.0; the pinned seed's count moved with #1085, though this module declines the closing stage), which is why that row carries starts=4

**Diagnostics:** `STEPHENS_STRAIN_NOT_POSITIVE`

### `tests/test_acceptance_indexing.py`

The only externally *graded* feature in the package. Bergmann et al. (2004) published both the data and every program's score, so the bar here is what ITO13, DICVOL91, TREOR90 and McMaille actually achieved rather than a tolerance chosen in this repo. The fixture is checked against three statements that paper makes in prose and never tabulates before anything is graded against it. One qualifier belongs on every summary drawn from these rows (WP-1043): the real-data corpus sits at <= 2 free metric parameters in nine of ten datasets (0 orthorhombic, 1 monoclinic, 0 triclinic), so any 'never wrong' claim is a claim about **high-symmetry lattices** until the corpus moves — which is post-v1 by the user's scope call.

#### `test_every_set_is_twenty_ascending_lines`

`identity` · dataset `bethanechol`

**Claims:** the fixture has the shape the paper's Table 6 has: ten sets, twenty strictly ascending positions each

**Referenced to:** Table 6's ten columns -- A/B/C/D are treatments and each was applied to BOTH ICDD entries, which is why the global score runs over twenty numbers and not ten

**Measured:** 10 sets x 20 lines, all ascending

#### `test_table_5_reconstruction_sums_to_the_published_globals`

`identity` `cross_code` · dataset `bethanechol`

**Claims:** the transcribed per-program scores sum to the Global column the paper prints beside them, which is what makes the bar itself trustworthy

**Referenced to:** Table 5 is a 20-column grid of +-1 with subscripted zeros and does not survive conversion intact -- the copy this was read from had a row of 21 values where there are 20.  Each graded row's twenty independently-read cells must reproduce its printed total

**Measured:** First 4 sums to +9 and Best of all to +12, both exact; the four programs the +9 is the best of scored -14, -8, -4 and +5 individually

#### `test_the_zeroshift_correction_is_exactly_the_paper_s`

`identity` `cross_code` · dataset `bethanechol`

**Claims:** the zero-corrected columns are exactly the raw ones less the paper's stated zeropoint

**Referenced to:** the text says only that the entries carry 'a surprisingly large zeropoint error that is close to 0.10 (2theta) deg' and prints both columns; the arithmetic linking them is never stated, and eighty values have to agree

**Measured:** C = A - 0.100 and D = B - 0.100 to 5e-13 on all four pairs

#### `test_the_intensity_cut_is_a_subset_of_the_same_measurement`

`identity` `cross_code` · dataset `bethanechol`

**Claims:** the I >= 5 % sets are subsets of the raw sets of the same specimen, and reach further in 2theta for the stated reason

**Referenced to:** B is 'the first 20 lines with I >= 5 % I_max' of the same pattern as A, so every B line inside A's range must be one of A's bit-for-bit -- and dropping the weak lines is what lets twenty survivors extend past A's last line

**Measured:** 13 of 13 and 15 of 15 common lines identical to 1e-12; both B sets reach beyond their A set's maximum

#### `test_the_published_cell_reproduces_the_paper_s_impurity_counts`

`cross_code` `characterisation` · dataset `bethanechol`

**Claims:** the published cell accounts for exactly as many of each entry's first twenty lines as the paper's own impurity statement implies

**Referenced to:** '8 impurity lines among the first 26 lines' in PDF 43-1748 and '3 impurity lines among the first 35' in 46-1964.  Nothing is fitted: the cell is the paper's and the offset is a one-parameter scan, so this uses the ANSWER to check the data and no typo in either survives it

**Measured:** 3 unexplained of 20 in every 46-1964 set, 7 in 43-1748, 0 in both new measurements

#### `test_the_runner_adopts_the_paper_s_domain_from_the_fixture`

`identity` `cross_code` · dataset `bethanechol`

**Claims:** the graded runner searches the paper's own domain, field by field, in both modes -- read from the transcribed fixture rather than retyped

**Referenced to:** adopting a protocol means adopting it whole: a score over a narrower domain is not comparable with Table 5, and the failure would be silent because a narrowed run still produces a number.  Default is 'the programs' default values ... in all crystal symmetries' with V <= 2000 A^3 and axes <= 20 A; manual is the paper's 'special conditions' block

**Measured:** default: max_d_axis 20, max_volume 2000, all 7 systems, n_unindexed at the package default; manual: monoclinic only, 800-1200 A^3, 5-20 A, n_unindexed 8

#### `test_the_scoring_rule_is_the_paper_s_and_reads_it_from_the_fixture`

`identity` `cross_code` · dataset `bethanechol`

**Claims:** the +-1 arithmetic is the paper's, including the bucket our engines can reach and the paper has no name for

**Referenced to:** '+1 correct cell ranked first, 0 in the top ten, -1 not found', from the text preceding Table 5.  The three values are read from the fixture's scoring block, so the rule this package grades itself by is the transcribed one

**Measured:** rank 1 -> +1; ranks 2..10 -> 0; rank 11 and absent -> -1 (consensus returns twelve, and the rule has no 11th bucket)

#### `test_the_published_cell_is_recognised_in_the_setting_the_search_returns`

`identity` `characterisation` · dataset `bethanechol`

**Claims:** a correct answer in another setting is scored correct, and a supercell or a foreign metric or a wrong centring is not

**Referenced to:** a candidate cell is a lattice, not a tuple.  The search returns the published cell as its c + a setting -- (7.1346, 16.4091, 11.7530, beta 131.107) for a published (8.875, 16.408, 7.137, beta 93.84), same lattice, same volume to 0.1 A^3, not one axis in common -- and comparing conventional axes scored that rank-1 answer -1 until this benchmark caught it (WP-1026 reopen).  The match reduces both sides first, then applies the centring and the band

**Measured:** the returned setting matches at rank 2 of a planted list; a doubled axis, a foreign metric and a C-centred description of the same metric all fail

#### `test_a_bare_position_list_says_its_sigma_was_assumed`

`characterisation` · dataset `bethanechol`

**Claims:** the benchmark's input form is carried honestly: every line says its sigma was assumed, and the quality gate lets it through anyway

**Referenced to:** the sets are positions only, so sigma is PEAK_ASSUMED_ESD_DEG -- chosen by this package.  A precision nobody measured may not be grounds for refusing to index, which is the inverse of the mistake indexing/quality.py exists to prevent.  All ten sets failed the sigma(Q)/Q abstention before WP-1026, including the one whose published M(20) is 197

**Measured:** source == 'positions' and sigma_assumed on every line of all ten sets; supports_indexing True on all ten; shift.source 'unavailable'

#### `test_published_figures_of_merit_are_reproduced_unfloored`

`cross_code` `characterisation` · dataset `bethanechol`

**Claims:** the published M(20) and F(20) are reproduced from the transcription with the de Wolff / Smith-Snyder definitions, and are shown NOT to be reproducible from this package's own floored versions

**Referenced to:** M(20) = 197 and F(20) = 1080 (0.0006, 32) on the synchrotron set.  m20/f_n floor <delta> at the median sigma, which on a from_positions list is the ASSUMED 0.02 deg -- thirty times the paper's <|d2theta|> -- so the floored figures are not comparable with a published value computed without the floor, and the row says so rather than quietly comparing them

**Measured:** unfloored M = 116, F = 654 with <|d2theta|> = 0.00099 deg and N_poss = 31 against the published 0.0006 and 32; the residual gap is the printed cell's own rounding (3 dp on the axes, 2 on beta).  Floored, the same data give 5.8 and 32.3

#### `test_the_2004_zeroshift_hypothesis_cannot_be_tested_on_these_data`

`characterisation` `prediction` · dataset `bethanechol`

**Claims:** the paper's own hypothesis about the cause of the zeroshift is tested for the first time and comes back UNANSWERABLE, with the reason quantified -- and the magnitude it does determine disagrees with the paper's round number

**Referenced to:** Bergmann et al. wrote the shift 'would be consistent with a systematic specimen-displacement error' and had no way to check, every program of the day fitting one constant zeropoint.  fit_shift_model fits three physical causes as nested single fits.  The prediction written down before the measurement is quality.py's: over a short low-angle range the templates are collinear and no cause is attributable

**Measured:** max_collinearity 1.0000 and separable=False on all ten sets over their 6-31 deg span.  Magnitude: PDF 43-1748 carries +0.080 deg and 46-1964 +0.058, not the quoted 0.10 -- so subtracting 0.100 overshoots to -0.020 and -0.043, which is why Table 5 does not show C as uniformly easier than A

#### `test_a_certified_lab_pattern_indexes_and_is_graded_honestly`

`certificate` `characterisation` · dataset `srm676a`

**Claims:** a raw certified pattern is picked and indexed end to end, the certified lattice is ranked first with the right centring, and the gate still refuses to promote it -- naming four reasons, all real

**Referenced to:** NIST SRM 676a a = 4.759355(80), c = 12.99231(15) A (k = 2). Both axes are asserted at 150 ppm.  An earlier version of this row asserted c as a RANGE of 1000-5000 ppm and called it 'what an uncalibrated lab pattern costs'; it was not, it was dichotomy's duplicate-leaf hash skipping the leaf that held the certificate's c (WP-1026, _box_key)

**Measured:** ranked first, trigonal R, a +89 ppm and c +60 ppm, 44 of 46 lines, chi2_red 0.55.  Confidence low on three caveats: engines_disagree, predicted_but_absent (11 -- the R-3c c-glide, not an oversized cell) and fom_panel_disagrees.  best_or_none() returns None.  WP-1038 cleared two of the former four: the shift is now MEASURED before the search from harmonic reflection pairs (-0.0641 deg, against an independently known -0.065), so shift_allowance_assumed no longer fires, and the measured window crosses the 0.9 bar unaided (indexed fraction 0.957).  WP-1110 and WP-1510 took two no_intensity components and five duplicate copies out of the usable list, so the row reads 45 of 47 where it read 51 of 55 (the 49-line and +101 ppm figures of the assumed 0.05 deg window are WP-1038's, not re-run).  The wider window is not free: a window that cannot rule out a constant must stay at |c| everywhere, where the true cos(theta) deviation has fallen to 0.26|c| by 150 deg.  1.9.0 read a +110 and c +57 ppm, 45 of 47 lines and chi2_red 0.67; the peak picker's changes before #1050 (#947 to #951, not bisected among them) took one line from the usable list

**Diagnostics:** `INDEX_SHIFT_FROM_PAIRS`

#### `test_declaring_the_shift_template_is_what_recovers_the_certificate`

`certificate` `characterisation` · dataset `srm676a`

**Claims:** declaring a shift template recovers a specimen displacement the package was never told about, and moves the cell to the certificate while it does so

**Referenced to:** The displacement was measured independently against the certificate as a -0.065 deg cos(theta) term (WP-1023).  This row never supplies it: the search fits the template after each candidate survives, from the pattern alone.  The cell and the figures of merit are asserted TOGETHER, because f_n's stated blind spot is that a refined shift can manufacture a large figure of merit on its own

**Measured:** fitted shift -0.0699 +/- 0.0192 deg; a +89 -> -111 ppm, c +60 -> -96 ppm, c/a -29 -> +15 ppm; M20 23.3 -> 187.1, F_N 15.3 -> 145.0, Le Bail Rwp 0.256 -> 0.176.  Since WP-1038 the two mechanisms are cleanly separated: the pair-MEASURED magnitude widens the window and finds lines (both calls index 44 of 46, so indexed_fraction_low has already cleared before the template is declared), and the DECLARED shape is what moves the cell.  Three routes to one systematic, none told the answer: -0.0641 from pairs pre-search, -0.0749 from the post-candidate fit, -0.065 measured against the certificate.  Still low, on caveats that have nothing to do with the shift.  1.9.0 read -0.0749 +/- 0.0187 deg, a +110 -> -114 and c +57 -> -109 ppm, c/a -54 -> +5, M20 23.7 -> 160.0, F_N 16.6 -> 114.9 and Le Bail Rwp 0.285 -> 0.224: the peak picker's changes before #1050 (#947 to #951, not bisected among them) took one line from the usable list, and WP-2002's closing stage and width twin hold (#1085, #1113) moved the Le Bail checks

**Diagnostics:** `INDEX_SHIFT_FROM_PAIRS`

#### `test_a_certified_shift_is_recovered_from_the_peak_list_alone`

`certificate` · dataset `srm660c`

**Claims:** a systematic 2theta shift is measured from the peak list alone -- no cell, no indices, no reference positions

**Referenced to:** NIST's own recorded specimen displacement, -0.07877 mm at R = 217.5 mm, PREDICTS +0.0415 deg cos(theta) parameter-free through model.corrections; the reference-based screen fits +0.0367 +/- 0.0015 against it.  The reflection-pair method (Dong, Wu & Chen 1999) sees neither: only harmonic pairs among the list's own lines, m sin(theta) = sin(theta'), which hold for any lattice

**Measured:** +0.0345 deg from 10 agreeing pairs of 19 admitted, z = 16.9 against 200 structureless replicates -- within 0.4 sigma of the reference-based fit it never saw, and 0.83 of the geometric prediction (the same 0.75-1.0 band the reference-based screen sits in, for the same reason).  separable is False: constant and cos_theta concentrate within one pair of each other, so a MAGNITUDE is measured and a CAUSE is not

**Diagnostics:** `INDEX_SHIFT_FROM_PAIRS`

#### `test_the_svd_zero_error_is_a_third_road_to_the_anchors_shift`

`certificate` `characterisation` · dataset `srm660c`

**Claims:** a systematic 2theta shift measured a THIRD way -- as one design column solved with the metric inside the search -- agrees with both of the package's existing roads to it

**Referenced to:** Coelho (2003) sec. 2.3 eq. (7): a zero error enters Q through Ze (pi/360)(4/lambda^2) sin(2theta), appended to the SVD design matrix.  It sees neither certified positions (the reference-based screen, +0.0367 deg) nor harmonic pairs (WP-1038, +0.0359 deg on the constant template) -- only a candidate lattice -- so the three share no input

**Measured:** +0.0329 deg, within 0.003 of both.  Started AT the certified cell, so this measures the COLUMN and not the search; the search's own use of it is asserted against an exactly known injected shift in test_indexing_engines.py.  It also reaches where the pair screen declines -- a bare 20-line list supplies too few pairs to concentrate, the published bethanechol failure, and this needs none

#### `test_the_svd_zero_error_is_a_third_road_to_corundums_shift`

`certificate` `characterisation` · dataset `srm676a`

**Claims:** the same three-way agreement on the lab specimen with the larger shift, and the line the column is NOT allowed to rescue

**Referenced to:** as above, against -0.0673 deg from harmonic pairs and -0.0650 deg measured against the SRM 676a certificate

**Measured:** -0.0674 deg, within 0.003 of both.  Needs trim=1: the list opens on a 5.17 deg edge artifact 3.9x beyond the longest d the lattice allows, which breaks eq. (4)'s weighting outright.  A line no lattice can index is not a shifted line, and the column does not pretend otherwise

#### `test_one_shift_is_measured_from_a_multi_phase_pattern`

`characterisation` · dataset `qarr`

**Claims:** harmonic pairs constrain the instrument rather than the lattice, so one shift is measurable from a multi-phase pattern with no cell for any of its phases

**Referenced to:** Dong, Wu & Chen (1999) sec. 3's second example: two of its eleven pairs come from an NiO impurity and agree with the other nine.  Reproduced here on bundled data -- the IUCr round-robin's three-phase mixture (corundum + zincite + fluorite) against the single-phase corundum specimen run on the same diffractometer

**Measured:** corundum -0.0641 deg (against -0.065 measured independently vs the certificate); cpd-1a -0.0091 deg (a separate fit of its 16 fluorite lines gives -0.0095 +/- 0.0023), z 8.4 and 4.6.  The two do not agree, and need not: a cos(theta) shift is specimen displacement, set per mount (cpd-1a read -0.0382 until WP-1510, when two of its five pairs turned out to be one line fitted twice)

**Diagnostics:** `INDEX_SHIFT_FROM_PAIRS`

#### `test_the_phantom_lines_are_what_had_blocked_it`

`characterisation` · dataset `srm676a`

**Claims:** the peak list this package produces from a real lab pattern contains components that are profile-shape repair rather than lines, and they are flagged rather than reported

**Referenced to:** detect_peaks proposes 41 groups with ONE seed each; the fitter returns 62 components.  The row asserts the flagged ones are weak satellites of much stronger lines -- the geometry no dBIC can refuse, because dBIC judges two models that both fail (chi2_red 17.4 at n=1, 4.6 at n=2)

**Measured:** 8 of 62 flagged not_separable, 47 usable (50 before WP-1510 took out five duplicate copies); before the fix neither engine could index this certified pattern at all

#### `test_a_three_phase_mixture_abstains`

`characterisation` · dataset `qarr`

**Claims:** a three-phase mixture returns no cell rather than the best of a bad list, and reports which systems were searched instead of concluding about the specimen

**Referenced to:** qarr/cpd-1a.prn is corundum + zincite + fluorite.  The failure this guards against is the one the prior art at the guillemot-study tag retracted a claim over: a coverage score cannot tell a multiphase pattern from a single-phase one of lower symmetry

**Measured:** best_or_none() is None; no candidate reaches high

#### `test_a_certified_cubic_cell_is_recovered_with_no_extinction_caveat`

`certificate` `characterisation` · dataset `srm660c`

**Claims:** the absolute lab anchor is indexed from the pattern alone, and the refuting caveat that fires on correct cells is silent on the one bundled phase whose space group has no absences

**Referenced to:** P m -3 m extinguishes nothing, so if predicted_but_absent means what WP-1026 read it to mean -- space-group extinctions counted against the LATTICE group, the only model that exists before determine_extinction_symbol runs -- it must be silent here and is 11-12 on R-3c corundum.  The cell bar is 200 ppm and is set by a defect this same file measures, not by the data: a tighter one would assert the tail components below do not exist

**Measured:** cubic P ranked first, a -127 ppm against the CIF's 4.156780 A; predicted_but_absent 0 of 30 and predicted_seen_fraction 1.000 against corundum's 0.58.  Still low, but the caveat list has been shrinking by evidence and is now ONE: fom_panel_disagrees.  WP-1038 cleared shift_allowance_assumed (this pattern's +0.0345 deg is measured from harmonic pairs before the search), and WP-1039 cleared engines_disagree -- trial_error was not failing to find the certified cell, it was solving from the wrong base lines, because its pool took the lowest-Q lines of the whole list and five of this pattern's low-angle components are not lines of the phase.  Drawn from the strongest-N selection instead, BOTH engines find it.  Agreement was necessary and not sufficient: a cubic-only search now promotes to high, this four-system one does not.  best_or_none() returns None

**Diagnostics:** `INDEX_SHIFT_ALLOWANCE`

#### `test_weak_impurity_lines_cost_the_certificate_its_rank_never_and_its_grade_only_a_notch`

`characterisation` · dataset `srm660c` · survives 2 starts

**Claims:** the contamination curve: k weak injected impurity lines cost the certified cell its RANK never and, since WP-1969, its GRADE only a notch (medium by the line-count cap); six at the stronger half's intensities still cost it the grade (low)

**Referenced to:** Le Bail (2004) Powder Diffr. 19, 249 SS V states the fractions -- under 35 % impurity lines by number the correct cell is generally first, at 35-50 % it may be found but usually not first, provided impurity intensity stays under 15 %.  Coelho (2003) Table 6 is deliberately NOT the reference: its rates are over an ensemble of different structures in systems with three to six free metric parameters, this is one cubic lattice with one, and cubic does not appear in that table

**Measured:** the truth indexes EXACTLY its own 25 lines at every k and never an injected one, so indexed_fraction is 25/(25+k), which crossed the 0.9 bar between k = 2 (0.926) and k = 3 (0.893) and refuted the truth while the caveat read the count.  Read on intensity (WP-1969) it is 0.93-1.00 through k = 6 and the truth is high at every k; six lines at the stronger half's intensities (26-27 % of the total) take it to 0.73-0.74, low on indexed_fraction_low at rank 1.  Rank is far more robust than grade, and how robust depends on a budget the user does not have -- first at k = 6/9/12/15/18 is 8/8, 8/8, 8/8, 2/8, 1/8 with n_unindexed = k and 8/8, 5/8, 2/8, 1/8, 0/8 with n_unindexed = 3 (eight seeds each).  The second column is the honest one and is the absolute budget showing as a contamination limit: when it misses it returns the truth NOWHERE, not second.  The first column is NOT monotone past k = 12 -- k = 21 returns 8/8 -- because M20 of the truth runs ~160, ~300, then 3-5 once more than twenty injected lines mean the first twenty of the list are mostly impurity, at which point the member is noise for every candidate alike

#### `test_the_supercells_that_used_to_outrank_brucite_now_sit_below_it`

`characterisation` · dataset `qarr`

**Claims:** the c-multiple supercells that WP-1026 measured ABOVE brucite's truth now sit below it, separated by the reversed coverage member alone

**Referenced to:** A literature cell for the mineral (Zigan & Rothbauer, P -3 m 1, a = 3.142, c = 4.766 A), never a certificate for this specimen -- whose a sits +1750 ppm from it, 30x the goniometer-radius floor.  So the bar is 3e-3 and asserts lattice type and centring, never a ppm figure.  WP-1026's measurement was taken before WP-1030's prunes, WP-1039's search-line ordering, WP-1040's third engine and WP-1041's dedup key, and was never a row, so it was never re-run

**Measured:** truth ranked FIRST (was: every one of twelve candidates a supercell, c x 3.002 first, the truth in none of them).  a = 3.1476, c = 4.7697.  Forward coverage cannot separate them -- 25 of 28 lines for the truth and the c x 2 cell alike (it read 31, 31 and 32 of 37, the supercells indexing MORE, before the peak list lost its duplicate copies) -- while predicted_seen_fraction reads 0.86 against 0.43, the exact 1/2 an exact supercell must give (no c x 3 cell is in the list any more; it read 0.32).  Still low on predicted_but_absent (1 of 28, the 6_3 screw); indexed_fraction_low, 0.89 of the lines, cleared with WP-1969, which reads the 0.98 of the intensity, and the line count under the bar is now the capping indexed_lines_low, so the grade is still low; best_or_none() returns None.  RANK RE-MEASURED 2026-09-22 (WP-1442): an a x 2 supercell had taken the rank on one extra panel line, 34 against 33, and WP-1446 measured that the peak list alone cannot order the pair.  RANK RESTORED 2026-09-27 (WP-1449) by the supercell check: of the 25 added lines no extinction could remove, 2 sit on an observed line where chance puts 2.6 (p = 0.76), so the a x 2 cell sits below the truth with supercell_refuted.  Measured on a finished search (900 s a unit, [dev], Linux x86-64): truth first and second (hexagonal, trigonal), a x 2 third and fourth; on a finished 1.7.0 search (52 s, [dev], darwin/arm64) the c x 2 cells are third and fourth and the a x 2 ones fifth and sixth.  The rank reads the order, so it waits for a finished search.  1.9.0 read 25 of 29 lines: the peak picker's changes before #1050 (#947 to #951, not bisected among them) took one line from the usable list

#### `test_magnetites_correct_cell_is_ranked_first_and_graded_below_its_rival`

`characterisation` · dataset `qarr`

**Claims:** the panel ranks the cubic F truth first and the GATE grades it below its own primitive rival -- a measured inversion, not a tolerance

**Referenced to:** A literature cell (F d -3 m, a = 8.3941 A), so 1e-3 and no ppm claim.  The inversion is referenced to nothing external: it is asserted structurally, as the presence of predicted_but_absent on the correct cell and its ABSENCE on the wrong one -- and since WP-1043 the mechanism is regenerated, not quoted

**Measured:** cubic F first at -334 ppm, its P description of identical axes second; predicted_seen_fraction 0.46 against 0.19 and n_indexed identical at 17 of 17, so the reversed member is the whole separation.  The detector then fires on the truth and not on the rival: F d -3 m's d-glide refutes the CORRECT cell (3 of 52) while P's Le Bail fit predicts 163 reflections on a 17-line pattern and reports ZERO absent.  The grade no longer inverts: both are low, P held there by supercell_refuted and engines_disagree (it was medium before WP-1449 and WP-1510 refuted the P description as an index-2 superlattice, and the list lost six lines).  WP-1043 measured why: the detector's inputs are the candidate's to buy -- the rival's own fit drives the co-refined background NEGATIVE (mean -7.3 counts, -5.8 on 1.9.0; no physical floor in the validation plan), so net clears 3 sigma at 99.6 % of channels and nothing can read absent; with the truth's background under the same positions 8-14 absences return, while swapping widths alone (inflated 2-3x in both fits) restores none.  Rwp 0.21 against 0.65 (0.72 on 1.9.0) is the same corrupted fit seen by a different instrument, so it stays surfaced and never ranked on.  best_or_none() returns None either way.  The 99.6 % was measured on 1.9.0 and not re-run

#### `test_the_tail_components_escape_not_separable_and_are_flagged_by_cause`

`characterisation` · dataset `srm660c`

**Claims:** the not_separable screen misses six components on this pattern -- and since WP-1043 the cause-specific flags reach all six blind, one MORE than the certificate probe itself reaches

**Referenced to:** The screen asks three questions (re-seeded, inside the neighbour's profile at <=25 % of its area, group still refuted).  Thirteen components face them here; the six survivors fail three DIFFERENT conditions, so widening PEAK_SATELLITE_NEAR_FWHM would reach four of six and be a knob rather than a measurement.  WP-1043's screens are not that knob: axial_tail is ONE-SIDED (the offset's sign must match the aberration's 90-degree flip) and kalpha2_residual sits at the mate's PREDICTED doublet position -- physics signatures, informational flags, components kept usable

**Measured:** 4 too far (1.73-2.99 FWHM), 1 not re-seeded (the detection seed slid into the tail and the new component took the real line), 1 on a group whose fit is not refuted (chi2_red 1.38).  WP-1043: all six flagged by cause (5 axial_tail, 1 kalpha2_residual), all six still usable.  The flag trim reaches ONE MORE component than the certificate probe: the 43.5 deg tail sits at dev -0.003 because the axial shift cancels the specimen displacement there, so an answer-based probe reads it as on-lattice while the side test does not -- dropping it takes the calibrated screen's leftover scatter from 0.0078 to 0.0025 deg.  Across the six other real lab patterns the screens reach 11 further usable components nobody has verified, which is why the flags report instead of refusing

**Diagnostics:** `PEAK_AXIAL_TAIL`, `PEAK_KALPHA2_RESIDUAL`

#### `test_the_surviving_components_sit_on_the_axial_divergence_side`

`characterisation` · dataset `srm660c`

**Claims:** the surviving components are aberration shape rather than lines, and the side they sit on names which aberration

**Referenced to:** Axial divergence puts a tail on the low-2theta side below 90 deg and the high side above it; nothing else in a Bragg-Brentano pattern changes sign there.  The single exception is asserted to be exactly one and to sit on its group-mate's Kalpha2 maximum -- an alias the detection screen drops (PEAK_KALPHA2_ALIAS, 23 dropped) and the group fit re-creates at 3 % of the parent's area

**Measured:** 5 axial-divergence tails, 1 Kalpha2 residual, 0 lines of LaB6; the sign flips at 90 deg on every one of them

**Diagnostics:** `PEAK_KALPHA2_ALIAS`

#### `test_the_shift_screen_survives_the_tail_components_but_the_search_cannot`

`certificate` `characterisation` · dataset `srm660c`

**Claims:** an assumed matching allowance costs the relative weighting the peak fitter measured, which is why declaring a shift template recovers corundum's certificate and not this one's

**Referenced to:** The displacement is PREDICTED, parameter-free, from NIST's own recorded -0.07877 mm at R = 217.5 mm through model.corrections.displacement_shift_deg: +0.0415 deg cos theta.  fit_shift_model weights by each line's own sigma; the search adds DEFAULT_UNKNOWN_SHIFT_DEG = 0.05 deg in quadrature to every sigma, which is flat

**Measured:** tail components carry sigma ~0.005 deg against the real lines' ~0.0005; after the quadrature allowance that 100x contrast is 1.005.  Screen: +0.0367 +- 0.0015 (0.88 of the predicted 0.0415, the rest being the aberrations SRM 660c's own docstring names).  Search: +0.009 +- 0.016, consistent with none

#### `test_positions_alone_cannot_separate_lab6_from_a_half_volume_rival`

`identity` `characterisation` · dataset `srm660c`

**Claims:** a geometrical ambiguity that is exact rather than approximate, and that the derivative-lattice enumeration cannot reach from one side

**Referenced to:** Tetragonal P at (a/sqrt2, a) gives Q = (2h2+2k2+l2)/a2, and 2(h2+k2)+l2 represents exactly the integers h2+k2+l2 does -- both miss precisely 4^n(8m+7).  So the two lattices are isospectral everywhere, not within a tolerance.  ambiguity_partners enumerates SUBlattices of index 2-4, i.e. supercells, and this rival has half the volume

**Measured:** represented sets identical to N=400; predicted Q identical to 3e-16 relative (the round-off of sqrt2, not a difference).  0 partners from the cubic side; from the tetragonal side the cubic is found at index 2 with ZERO discriminating reflections

#### `test_the_isospectral_rival_is_ranked_beside_the_truth`

`characterisation` · dataset `srm660c`

**Claims:** both engines find the isospectral rival on the measured pattern, and neither it nor the truth carries the caveat that should hold the pair

**Referenced to:** The WP's 'a geometrical-ambiguity case where NEITHER partner reaches high' row, answered on certified data rather than synthetically -- and a stronger case, because this partner is exactly isospectral rather than isospectral within a tolerance.  Nothing is promoted here for an unrelated reason (the allowance was assumed), so what is pinned is the missing geometric_ambiguity caveat

**Measured:** the half-volume tetragonal cell is ranked in the same list, found_by both engines; neither partner reaches high and neither carries geometric_ambiguity

#### `test_what_the_unflagged_tail_components_cost_the_certified_cell`

`certificate` `characterisation` · dataset `srm660c`

**Claims:** with every piece of evidence supplied the gate reaches high for the first time on real data and the cell lands 5 ppm from a certified value -- and best_or_none() still declines, because the a*sqrt2 supercell reaches high too

**Referenced to:** An attribution probe, not a protocol: the off-lattice components are identified USING the certificate, which no user of an unknown phase can do.  What it establishes is that the pipeline's arithmetic is sound to the ppm and that what stands between it and a blind certified answer is a peak list.  Three things are supplied -- the five off-lattice components removed, the systematic measured rather than assumed, the cos_theta template declared

**Measured:** a = 4.156801 A, +5 ppm, M20 3266, ZERO caveats, confidence high -- a first on real data, against -127 ppm with none of the three.  But best_or_none() is None: the a*sqrt2 cell (5.878605) reached high in BOTH its I and P descriptions, all three engines finding all three cells; since WP-1449 the P one is refuted as an index-2 superlattice of the I one (supercell_refuted, low) and the I one still reaches high.  The 'best_or_none() non-None' claim recorded here before WP-1041 held only while trial_error's scale-invariant dedup key could return one cubic candidate per search, denying the supercells its vote -- the flagship result was protected by a bug rather than by the gate.  Everything that refutes the supercell is measured and ungated: Rwp 0.100 vs 0.860/0.654, predicted_seen_fraction 1.00 vs 0.88/0.49, m_rev 2245 vs 6.8/1.9, unmatched_observed 21 vs 168/129 (169/127 and Rwp 0.861/0.660 on 1.9.0, before WP-2002's width twin hold moved the Le Bail checks), while the one gated detector (predicted_but_absent) reads 0 for all three.  Also measured: declaring the probe-trimmed screen's own sigma_sys (0.0078, the residual the template LEAVES) gives a window 4.9x too tight for the shift's amplitude (0.038): the search matches uncorrected positions, and only svd, which fits a zero error inside the search (ze +0.033), still finds the certified cell (+5 ppm), which one engine cannot promote past low

**Diagnostics:** `INDEX_SHIFT_ALLOWANCE` asserted *absent*

#### `test_a_short_clean_list_is_searched_ranked_and_reported_unscored`

`characterisation` · dataset `qarr`

**Claims:** a pattern with too few lines to score is searched anyway, over the systems its line count supports, and reported unscored with the certified cell ranked first

**Referenced to:** CaF2 is Fm-3m with a = 5.4631 A, and over 5-150 deg Cu Ka that lattice yields fewer than twenty usable lines.  Twenty is where M20 is DEFINED and where this package scores F_N -- a scoring bar, not a searching one (WP-1043): seventeen lines are seventeen-fold over-determined for a cubic metric, and the pre-1043 gate's abstention here refused a question the engines answer at -5 ppm each when asked directly.  High symmetry makes a pattern easy to index right up until it makes it too sparse to SCORE -- no longer too sparse to search

**Measured:** 17 usable; supports_indexing True with m20/f_n absent for cause; four systems searched to completion; 12 candidates, certified cell first at -18 ppm, caveats exactly [fom_panel_reduced] so the grade holds at medium and best_or_none() still refuses -- the capping caveat is what keeps a 17-line high unreachable

**Diagnostics:** `INDEX_PANEL_REDUCED`, `INDEX_ABSTAINED`, `INDEX_DATA_INSUFFICIENT` asserted *absent*

#### `test_a_hexagonal_lab_pattern_recovers_its_lattice`

`characterisation` · dataset `qarr`

**Claims:** a hexagonal lab pattern recovers its lattice, both engines agreeing, and supplies the third point of the extinction-caveat table

**Referenced to:** Kihara & Donnay (1985) for ZnO wurtzite.  A LITERATURE cell for the mineral, never a certificate for this specimen -- brucite in the same series sits +1750 ppm from its own literature cell, 30x the goniometer-radius floor, which is why these rows assert lattice type and centring at a lab d-scale level and not a ppm number

**Measured:** a -217 ppm, c -185 ppm; ALL 27 usable lines indexed; M20 910; both engines.  predicted_but_absent = 4 (the 6_3 screw and c-glide of P 6_3 m c, invisible to the lattice hexagonal P), so graded low and best_or_none() is None

#### `test_a_centred_tetragonal_lattice_is_recovered_with_its_centring`

`characterisation` · dataset `qarr`

**Claims:** the only row that recovers a CENTRING, and it shows which figure of merit does the choosing

**Referenced to:** Hazen & Finger (1979) for ZrSiO4.  Two centrings of one metric are deliberately NOT merged (engines.dedup_groups) because they predict different numbers of lines; the panel chooses.  The primitive twin indexes exactly as many OBSERVED lines, so forward coverage cannot separate them -- only coverage scored in the other direction can

**Measured:** tetragonal I ranked first, a +140 ppm and c +2011 ppm, 45 of 55 lines; the P twin indexes 45 too and loses on predicted_seen_fraction 0.53 against 0.27.  predicted_but_absent = 7 (4_1 screw and glides on top of the centring); low, best_or_none() None.  1.9.0 read 45 of 56, the P twin 44, and 6 absent: the peak picker's changes before #1050 took one line from the usable list, and WP-2002's width twin hold moved the Le Bail check

#### `test_short_wavelength_data_is_indexed_by_the_engines_that_enumerate_nothing`

`characterisation` · dataset `nac`

**Claims:** a short-wavelength pattern defeats an exhaustive box search and is still indexed, by the two engines that enumerate no box -- and the third one finding nothing is still a disagreement, so the gate declines it

**Referenced to:** lambda = 0.4139 A to 57.4 deg gives d_min = 0.43 A, at which a 10.25 A cubic cell exceeds engines.reflection_ceiling_ok -- the crash guard in front of every generate_reflections call -- so the dichotomy rejects its first box.  search_svd sizes its prediction set from the CURRENT trial metric under Coelho's N_c/N_o gate, and search_trial_error solves the metric from a few base lines; neither meets that resolution

**Measured:** zero boxes explored by the dichotomy, premise unchanged; svd AND trial_error both return a = 10.2512 A, +21 ppm (+19 on 1.9.0) from the certified 10.2510, in both the P and the I description of identical axes.  Le Bail chooses: I predicts 0 of 837 absent at Rwp 0.155, P predicts 80 of 1668 at Rwp 0.193.  The panel does NOT -- borda leads with P 4-3 on margins of 0.5 % and 0.01 % against m_rev separating them 961x (1425.5 vs 1.48; 693x on 1.9.0) and m_sym 1926x (399x); pinned until 2026-09-27, when the supercell check inverted it (WP-1449): the P description is an index-2 superlattice of the I cell, and 1 of its 187 added lines no extinction could remove sits on an observed line at p0 = 0.030 (p = 1.0), so P now sits below I with supercell_refuted.  No aggregate of the panel was needed.  Still low / best_or_none() None on engines_disagree.  This row has now turned over TWICE -- 'cannot be indexed' died in WP-1040, 'only svd can' in WP-1041, where trial_error turned out to have reached the cell all along and discarded it: its dedup key was scale-invariant (every cubic candidate hashing to one entry) and carried no centring across the centring loop, so P claimed the metric and I was dropped unscored.  Three recorded no-goes have died on this one dataset.  A recorded no-go inherits the defects of the run that produced it

**Diagnostics:** `INDEX_SEARCH_INCOMPLETE`, `INDEX_ABSTAINED`

#### `test_the_cross_code_cell_leads_because_the_engines_agree_on_it`

`cross_code` `characterisation` · dataset `fap`

**Claims:** the cross-code cell is reachable, every engine agrees on it, it leads the ranking because of that agreement and not because the panel prefers it, and the gate declines it anyway

**Referenced to:** GSAS's own converged FAP.EXP cell for this exact pattern.  The band is 500 ppm, NOT the refinement suite's +-300: an indexed cell has no displacement parameter and absorbs the displacement instead, worth a measured 127 ppm on SRM 660c and ~180 on SRM 676a.  The row asserts MEMBERSHIP and REFUSAL rather than rank, because writing it as 'rank 0 is the answer' would mean tuning the panel on a dataset whose reference is another code's fit

**Measured:** a +131 ppm, c +410 ppm, found by EVERY engine, 130 of 135 lines (1.9.0: +123 and +414 ppm, 131 of 136, before the peak picker's changes ahead of #1050 took one line from the usable list).  Ranked FOURTH until WP-1046, below three cells 966-1396 ppm out that index 152 and score a higher M20 (today's single-engine cells scoring a higher M20 are 607-1028 ppm out and index 110-119); it leads since, because those three are one engine's and corroboration is the ranking's first key.  The panel was NOT touched and still prefers a wrong cell -- the row now pins that directly.  best_or_none() None and nothing reaches high, which is the half that did not move

#### `test_an_unidentified_pattern_stays_unidentified`

`characterisation` · dataset `hl2`

**Claims:** the only fixture whose compound is genuinely unknown stays unknown, and is refused on merit rather than on coverage

**Referenced to:** Every other real-data row has a known answer and measures whether it is found; this measures the opposite half, which no benchmark can.  The trap it guards is that forward coverage READS like a solution -- the leaders index 73 of 74 lines.  What refuses them is M20 an order below anything publishable (de Wolff's own guidance is M20 > 10; the bethanechol synchrotron set reaches 197 in this same file)

**Measured:** 12 candidates, all low, M20 3.1-4.7, none validated, best_or_none() None; systems_searched reported and search_complete False on two of the four, so the null is not dressed up as an exhausted domain

**Diagnostics:** `INDEX_ABSTAINED`, `INDEX_SEARCH_INCOMPLETE`

### `tests/test_acceptance_wavelength.py`

A parameter that is exactly degenerate in one histogram and measurable in several, on the two histograms of a published combined refinement whose stated method is precisely that. The bar worth reading is the third row: the refined wavelength reproduces, to 2 %, the cell disagreement the two histograms already showed when refined separately — a prediction made without freeing anything. The fourth adds the check that keeps it honest, which is that holding the other end measures the same ratio with the opposite sign.

#### `test_holding_both_wavelengths_costs_the_neutron_histogram`

`characterisation` · dataset `ndruo_joint`

**Claims:** the problem statement, asserted: one cell for two uncalibrated wavelengths lands the whole calibration mismatch on the histogram with less leverage on the cell

**Referenced to:** each histogram against **its own solo fit** on the same protocol -- our own results either side of one change, so the bar is the 10 % degradation being an order larger on one histogram than the other, not any external value

**Measured:** neutron Rwp 0.05234 alone -> 0.06216 jointly (+19 %); X-ray 0.09176 -> 0.09186 (+0.1 %), a ratio of ~170; 1.9.0 read 0.05259 -> 0.06226 (+18 %), 0.09365 -> 0.09373 and ~200

#### `test_freeing_the_neutron_wavelength_recovers_its_fit`

`characterisation` · dataset `ndruo_joint`

**Claims:** the degradation above goes away when the neutron wavelength is freed, and the X-ray histogram does not pay for it -- the SYMPTOM, recorded because a correction does not ship on an Rwp comparison

**Referenced to:** the same three fits as the row above.  Deliberately a loose band: two independently converged fits differ by more than their own ftol, so the bars are 'more than half the way back' and 'not past the solo floor', never a figure

**Measured:** 0.06216 held -> 0.05490 freed, against a 0.05234 solo floor: 74 % of the gap recovered; X-ray unchanged to 0.03 %; 1.9.0 read 0.06226 -> 0.05502 against 0.05259, 75 %

#### `test_the_refined_wavelength_is_the_solo_cell_disagreement`

`prediction` · dataset `ndruo_joint`

**Claims:** the headline: the refined wavelength reproduces the cell disagreement the two histograms already showed when refined separately -- one number arrived at two independent ways

**Referenced to:** the ratio of the two SOLO cells, computed without freeing anything, is a prediction for how far the neutron lambda must move.  The 20 % band is the scatter two separately converged single-histogram fits carry, not a tolerance

**Measured:** solo cells 10.342905 vs 10.340285 A = +253 ppm; refined lambda 1.540400 -> 1.5407972(795) A = +257.9 ppm, agreeing to 2 %; the move is 5.0x its own esd; 1.9.0 read 1.5407968(843), +257.6 ppm and 4.7x

#### `test_the_diagnostic_reports_the_ppm_and_nothing_claims_rwp`

`identity` · dataset `ndruo_joint`

**Claims:** the record field this correction ships with: WAVELENGTH_CALIBRATION fires exactly where a wavelength was refined, carries the ppm as Diagnostic.value, and is silent on the held histogram and on a fit that held both

**Referenced to:** floating point (rel=1e-9) between the diagnostic's value and the ppm recomputed from the row -- one measurement, two surfaces, pinned rather than re-derived

**Measured:** one diagnostic, level info, value +257.9 ppm (+257.6 on 1.9.0), where hist.1.instrument.source.lines.0.wavelength; zero on histogram 0 and zero on the both-held fit

**Diagnostics:** `WAVELENGTH_CALIBRATION`

#### `test_the_cell_belongs_to_the_synchrotron`

`cross_code` `characterisation` · dataset `ndruo_joint`

**Claims:** holding the X-ray wavelength hands the cell to the X-ray histogram -- the accuracy hierarchy in action -- and the result agrees with the published combined refinement

**Referenced to:** the X-ray SOLO cell to 5e-6 relative (our own result, the claim being that the joint cell lands ON it rather than between the two), and the published a = 10.342312(8) A under a 2e-4 relative band.  The published band is NOT claimed: this is a single-phase fit against a refinement carrying 0.5(1) mol % RuO2 and a modelled lambda/2 second-order contribution, neither of which rietx does

**Measured:** joint a = 10.342904(48) A, on the solo 10.342905 and +57 ppm above the published value; x(O 48f) 0.33001(41) against a published 0.33012(7), inside its own esd; 1.9.0 read 10.342904(51) and 0.32994(43)

#### `test_swapping_which_wavelength_is_held_measures_the_same_ratio`

`prediction` `identity` · dataset `ndruo_joint`

**Claims:** the sharpest statement of the physics: a joint fit determines the RATIO of the two wavelengths, so which one is called 'the calibration error' is a choice of what to hold and not a result

**Referenced to:** eq. pos-lambda-cell, which says the two runs are one fit in two parameterisations.  Bars: the two ppm figures agree to 2 % of the effect, every per-histogram Rwp to 2e-3 relative and the shared x(O) to 1e-5 absolute

**Measured:** +257.9 ppm holding the X-ray against -256.9 ppm holding the neutron -- 0.9 ppm apart on an effect of 258 (0.35 %); both histograms' Rwp agree to 6e-5 relative, x(O) to 1.5e-6.  1.9.0 read +257.6 and -256.7 ppm (0.34 %), Rwp identical to 5 decimals and x(O) to 1.2e-6

#### `test_the_neutron_widths_leave_one_esd_at_every_start`

`prediction` `identity` · dataset `ndruo_joint`

**Claims:** issue #831's platform split, reproduced on one machine: x's esd is one number however the start is nudged at the size of two platforms' arithmetic, with y on its old floor of 0 and since WP-2002 with y free

**Referenced to:** the esd the width column gives when taken in physical units and chained by dp/du, computed by WP-1929 at three softplus stopping points before WP-1938 refined in those units (0.0098437, 1e-4 relative), and the spread across four nudged starts under 1e-6 relative

**Measured:** 0.0098437 at nudges 0, +-1e-14, 2e-14 (eight nudges spread 4e-8 relative, macOS arm64); y = 0 +- 0.018101, at_bound. The pre-1938 tree gives 0.00322, Linux's figure. Since WP-2002: 0.0102922 at four starts, spread 2.2e-9 (1.5e-9 when WP-2002 measured it), y = -0.0210949(191) off any bound

#### `test_a_width_on_its_floor_has_a_one_sided_profile_interval`

`characterisation` · dataset `ndruo_joint`

**Claims:** the neutron fit's Lorentzian y on a floor of 0 (the caller's since WP-2002) gets a one-sided profile interval: the bound is one end, and the other lies where the data's chi2 has risen by chi2_1(0.90) x chi2_red x f^2, inside the sqrt(2.706) esd a stationary floor would give, because the data press y against the floor

**Referenced to:** the threshold itself for where the end lies (1 % of it), and the stationary-floor end sqrt(2.706) x 0.018101 = 0.0298 (x 0.018997 = 0.0312 since WP-2002) as a ceiling that LM's active set (the gradient at 0 points out of the range) says the end must sit under; the value is pinned at ten times its own solve tolerance, 1e-3 esd

**Measured:** upper end 0.0166098 (0.558 of 0.0298), Delta chi2 there 0.0044 under a cut of 21.343, 19 refits, 3 s; the same to 5e-10 relative at six starts nudged by 1e-14 (macOS arm64), on 1.9.0.  Since WP-2002 left U and V unfloored and Y's floor to the caller: 0.0164535 (0.527 of 0.0312, the esd now 0.018997), Delta chi2 there 0.0069 over a cut of 21.048, 10 refits

#### `test_the_fits_render`

`ceiling` · dataset `ndruo_joint`

**Claims:** the per-histogram obs/calc/diff renderings exist, so the fit can be looked at rather than only summarised

**Referenced to:** existence, not a number -- a ceiling row

**Measured:** two PNGs written to tests/output/, mg090_joint_hist0.png and mg090_joint_hist1.png

### `tests/test_acceptance_si640c.py`

The single-histogram refinable wavelength, on NIST SRM 640c silicon at APS 11-BM, against an independent XND 1.42 refinement of the same scan.  Holding the certified cell is what makes a free lambda a measurement of the monochromator's calibration error, and the fit finds it +30 to +41 ppm off the beamline's stated value at many sigma.  The row worth reading is the pair: on XND's own 2-50 deg range the codes agree to 11 ppm, and that gap is entirely the asymmetry convention (rietx's FCJ axial divergence against XND's A_T2) -- restrict to the symmetric peaks where neither applies one and the agreement collapses to 0.4 ppm.  The sub-ppm number lives where the two codes model the same physics, and the residual is named rather than tuned away.

#### `test_the_protocol_is_sane_and_states_what_differs_from_xnd`

`identity` `ceiling` · dataset `si640c`

**Claims:** Rexp lands in the right neighbourhood of XND's on the same channels, and the grid is XND's exactly -- the protocol check before any refined number is compared

**Referenced to:** the file's own 47999-point grid (XND's SIZE) as the identity bar; Rexp is only asked to sit in the counting-statistics band both codes see (~0.06-0.07), not matched to XND's 0.065, because rietx's free set and effective-N differ.  The two modelled differences from XND -- a P-spline background vs eleven interpolated points, FCJ asymmetry vs A_T2 -- are declared in the docstring, which is the cross-code tier's requirement

**Measured:** Rexp 0.0609 against XND's 0.065; 47999 channels exactly; converged, GoF 1.35 (1.36 on 1.9.0)

#### `test_the_refined_wavelength_recovers_xnds_calibration_error`

`cross_code` `characterisation` · dataset `si640c`

**Claims:** on XND's own 2-50 deg range the refined lambda moves +30 ppm off the beamline's stated value and agrees with XND within the one modelled difference -- the FCJ-vs-A_T2 asymmetry convention

**Referenced to:** XND 1.42's converged lambda 0.412376076 +- 0.000000379 A (+41.4 ppm off the header's 0.412359), cell held.  The band to XND is 18 ppm -- the MEASURED FCJ-vs-A_T2 convention difference with headroom, NOT a truth claim: lambda sits on a rho = -0.9 ridge with zero, and which point is picked is set by the low-angle asymmetry model the two codes spell differently.  The move off nominal is the calibration error, asserted resolved (>4 sigma) and in XND's sign and order

**Measured:** lambda = 0.412371546 A, esd 4.7 ppm; +30.4 ppm off nominal (6.5 sigma), -11.0 ppm from XND; Rwp 0.0823, GoF 1.35 (1.9.0 read 0.412371535, 4.6 ppm, 6.6 sigma, 0.0826 and 1.36).  Background choice moves it <0.1 ppm and dispersion is inert (Si far above its edge), so the residual is the asymmetry convention alone -- the next row proves it

#### `test_the_symmetric_window_recovers_xnd_to_sub_ppm`

`prediction` `characterisation` · dataset `si640c`

**Claims:** restricting to the symmetric peaks -- where neither code applies a consequential asymmetry correction -- collapses the disagreement with XND to sub-ppm, proving the full-range gap is the convention and nothing else

**Referenced to:** the prediction written before the fit: if the 11 ppm full-range gap is FCJ-vs-A_T2 and not a real lambda difference, dropping everything below the (111) at 7.54 deg must recover XND.  The band is 3 ppm against XND's 0.412376076; this is the asymmetry-model-free determination, recorded as such rather than as XND's exact protocol (it is not -- the low-angle channels XND kept are excluded here)

**Measured:** lambda +41.0 ppm off nominal, -0.4 ppm from XND, now resolved at 43 sigma because the low-angle region was the whole source of the lambda~zero indeterminacy; Rwp 0.0724; 1.9.0 read 35 sigma and Rwp 0.0736, before WP-2002's closing stage (#1085)

#### `test_the_wavelength_calibration_diagnostic_fires_once_and_reports_the_ppm`

`identity` · dataset `si640c`

**Claims:** WAVELENGTH_CALIBRATION fires exactly once where lambda was refined, names the scoped path, carries the ppm as Diagnostic.value, and is silent on the fit that held lambda

**Referenced to:** floating point (rel=1e-9) between the diagnostic's value and the ppm recomputed from the refined lambda -- one measurement, two surfaces, pinned rather than re-derived; and set membership for the silence on the held fit

**Measured:** one diagnostic, level info, value +30.4 ppm, where instrument.source.lines.0.wavelength; zero on the lambda-held fit

**Diagnostics:** `WAVELENGTH_CALIBRATION`

#### `test_biso_is_positive_and_agrees_with_xnd`

`cross_code` · dataset `si640c`

**Claims:** the one structural parameter comes back positive and within a fraction of a combined sigma of XND's

**Referenced to:** XND's Biso(Si) 0.438984 +- 0.001711 A^2.  Both codes carry Berar-Lelann inflated esds -- XND's Berar is the same one rietx implements -- so this is a genuine sigma-distance, bounded at 2 combined sigma.  Positivity is its own claim: the prior bad-intensity-model attempt drove Biso negative

**Measured:** Biso 0.42188(1897) against 0.438984(1711), 0.90 combined sigma; positive (0.42198(1880) on 1.9.0)

#### `test_the_lambda_zero_correlation_is_high_but_below_the_guard`

`characterisation` · dataset `si640c`

**Claims:** lambda~zero is reported high-but-below-guard as XND found it, the fit raises no HIGH_CORRELATION, and nothing sits at |rho| -> 1

**Referenced to:** XND printed lambda~zero = -0.897; d = lambda/(2 sin theta) makes the ridge real and correct, not a defect.  The checks are that it appears in top_correlations near XND's value, that no pair reaches the 0.98 guard (so HIGH_CORRELATION is silent), and that the tied FCJ pair leaves nothing at |rho| -> 1 -- freeing S/L and H/L both would sit at -1.000

**Measured:** lambda~zero -0.920 (XND -0.897); zero~axial +0.914 (XND zero~asym +0.941); no HIGH_CORRELATION; max |rho| < 0.98

**Diagnostics:** `HIGH_CORRELATION` asserted *absent*

#### `test_the_held_cell_is_the_certificate`

`certificate` `identity` · dataset `si640c`

**Claims:** the held cell IS the certificate value -- the anchor of the whole protocol, asserted as the identity it is rather than measured

**Referenced to:** NIST SRM 640c certificate a = 5.4311946 +- 0.0000092 A at 22.5 C.  Held, not refined: holding a certified cell is what turns a free lambda into a calibration measurement.  The cubic ties (b<-a, c<-a) carry the source's value, so this is an identity bar (exact) and the absent esd shows nothing was refined.  XND held 5.4311948, 0.4 ppm above, negligible against every band here and stated in the docstring

**Measured:** cell.b and cell.c both exactly 5.4311946 A, esd None

#### `test_the_sample_broadening_is_positive_and_finite`

`characterisation` · dataset `si640c`

**Claims:** the Lorentzian sample broadening refines to positive, finite terms, and is explicitly NOT compared to NIST's certificate coefficients

**Referenced to:** SRM 640c's Information Values give a Lorentzian FWHM 0.0065(5)/cos theta + 0.0086(6) tan theta, which map unit-for-unit onto lor_size and lor_strain -- but by CONVENTION only.  NIST's split is a fundamental-parameters analysis at its own Cu Ka instrument, so the instrument/sample division differs from this Caglioti-plus-Lorentzian model at 11-BM; the claim is positivity and finiteness, with the NIST numbers a NOTE and never a bar (no equality is asserted)

**Measured:** lor_size 0.0023(2), lor_strain 0.0150(12) deg2theta (0.0149 on 1.9.0) -- the same order as NIST's 0.0065/0.0086, the split apportioned differently; both positive and finite

#### `test_one_hump_beats_three_more_polynomial_terms`

`own_result` `ceiling` · dataset `si640c`

**Claims:** one background peak buys more Rwp than three extra Chebyshev terms buy, at the same parameter cost -- which is the only form in which an Rwp improvement from a free position/height/width is evidence

**Referenced to:** this package's own arms under one fixed protocol: three fits differing only in how three parameters are spent (Chebyshev-3, Chebyshev-3+peak, Chebyshev-6).  Not referenced to any external number -- the identification of the feature is separate evidence (11-BM's published empty-Kapton blank and air-scatter scans, provenance in tests/data/README.md, neither committed nor read here)

**Measured:** Rwp 0.120051 -> 0.082134 with the peak (-31.6 % relative) against 0.088232 with three more polynomial terms (-26.5 %); the bar is a 1.15x margin on the ordering and the measured ratio is 1.19x.  Biso(Si) 0.413(64) -> 0.421(10), GoF 1.9708 -> 1.3484, zero HIGH_CORRELATION.  1.9.0 read 0.119977 -> 0.082503 against 0.088596, Biso 0.414(65) and GoF 1.9695 -> 1.3544

**Diagnostics:** `HIGH_CORRELATION` asserted *absent*

#### `test_the_peak_is_diffuse_by_three_orders_and_frees_the_structural_esd`

`characterisation` `own_result` · dataset `si640c`

**Claims:** the fitted term is a *background* term -- its width comes from disorder and not from the goniometer -- and describing it returns precision to the structural parameters rather than moving them

**Referenced to:** the instrumental FWHM at the peak's own position from CompiledModel.instrument_fwhm_deg -- the same function check_hump_width (HUMP_MIN_WIDTH_MULT) measures against, called rather than re-derived, so the two stay equal if a later revision frees the Lorentzian X/Y this protocol holds at zero -- and the peak-free arm's own esds.  The refined *position* is deliberately NOT referenced to the halo: a symmetric Gaussian over 2-50 deg also absorbs the residual direct-beam rise, so it lands at 4.16(9) deg where the envelope reads 4.98 deg, and the band here is wide enough to say so

**Measured:** FWHM 5.607(223) deg against an instrumental 0.00347 deg at 4.162 deg -- 1618x, where the guard is 4x and the bar here 1000x; Biso(Si) esd falls 6.4x and lambda's 6.3x while neither value moves by 0.12 of the wider esd.  1.9.0 read 5.567(220) at 4.178 deg, 1608x, 6.5x and 6.4x, and 0.11

**Diagnostics:** `HUMP_TOO_NARROW` asserted *absent*

#### `test_the_chebyshev6_arm_relaxes_the_peak_onto_the_envelope`

`characterisation` `own_result` · dataset `si640c`

**Claims:** the fitted peak and the polynomial describe overlapping freedom, so a higher-order background changes what the peak's parameters mean -- which is why the manual's rule is to declare a peak *instead of* extra polynomial terms, not on top of them

**Referenced to:** this package's own two peak arms under the one protocol: the Chebyshev-3 arm, whose short polynomial cannot take the residual direct-beam rise, against the Chebyshev-6 arm, whose can.  Not referenced to any external number -- the halo's position is separate evidence (the blank and the envelope)

**Measured:** the peak moves from 4.16(9) deg / 5.61(22) deg with three Chebyshev terms onto the envelope at 5.238(31) deg and narrows to 1.92(8) deg with six, while Rwp moves only 0.082134 -> 0.076711; zero HIGH_CORRELATION or HUMP_TOO_NARROW in either arm.  1.9.0 read 4.18(9) / 5.57(22), 5.245(32) and 1.94(8), Rwp 0.082503 -> 0.077152

**Diagnostics:** `HIGH_CORRELATION` asserted *absent*, `HUMP_TOO_NARROW` asserted *absent*

#### `test_a_measured_blank_beats_the_polynomial_and_the_fitted_hump`

`own_result` `ceiling` · dataset `si640c`

**Claims:** a background shape somebody measured with the sample out, declared and not fitted, beats both the polynomial that cannot describe it and the three-parameter hump that can -- which is the case for scanning a blank at all

**Referenced to:** this package's own three arms under the one protocol (Chebyshev-3, Chebyshev-3 + one hump, Chebyshev-3 + the declared blank), scored on ONE weight -- the specimen's own sigma -- because a measured background's esds move the weight and an Rwp column across arms that declare different curves is not otherwise a ranking

**Measured:** Rwp 0.120051 (bare polynomial) -> 0.082134 (fitted hump, three free parameters) -> 0.078843 (declared blank, none), all under the specimen's sigma; zero HIGH_CORRELATION; 1.9.0 read 0.119977 -> 0.082503 -> 0.079310

**Diagnostics:** `HIGH_CORRELATION` asserted *absent*

#### `test_the_refined_scale_rejects_the_only_value_the_code_could_express`

`own_result` · dataset `si640c`

**Claims:** the fraction of the blank that reached the specimen scan is a measurement, and it is not 1.0 -- the value this package could express before the scale field existed

**Referenced to:** issue #171's hand-set scan of the same two files, rerun as this module's `blank_scan` fixture: the refined scale is checked against the minimum a caller had to find by hand.  Not an external number -- the monitor normalisation and the specimen's attenuation of the container are not separately known here, and the WP records the angle-dependence a constant scale cannot carry

**Measured:** scale 0.8413(107): the hand-set minimum 0.85 is 0.8 esd away and unity 14.8 esd; Rwp falls 0.073609 -> 0.073393 under its own sigma and 0.078843 -> 0.076946 under the specimen's.  Biased low as the synthetic fixture predicted (regression dilution, this blank's sigma/I is 8-17 %).  1.9.0 read 0.8374(113), 1.1 and 14.3 esd, 0.074011 -> 0.073748 and 0.079310 -> 0.077327

#### `test_the_hand_set_scan_puts_the_minimum_where_the_scale_landed`

`own_result` · dataset `si640c`

**Claims:** the minimum in the scale is *interior*, so an additive polynomial cannot reach it however many terms it is given -- the whole reason a measured curve needs a multiplier

**Referenced to:** issue #171's own experiment, rerun in the issue's own weighting (the blank's esd column dropped, since it measured this before `fixed_sigma` existed) at three hand-set scales

**Measured:** Rwp 0.077626 / 0.076929 / 0.078755 at s = 0.75 / 0.85 / 1.00; unity costs 2.4 % of Rwp where the issue measured 2.2 %, and the refined scale lands inside the bracket; 1.9.0 read 0.077949 / 0.077315 / 0.079219 and 2.5 %

#### `test_a_longer_polynomial_eats_the_measured_scale`

`characterisation` `own_result` · dataset `si640c`

**Claims:** an additive polynomial and a multiplicative scale share the background's level, so a longer polynomial walks the measured scale away while Rwp improves -- a lower Rwp does not make a scale more nearly measured

**Referenced to:** this module's two free-scale arms, three Chebyshev terms against six, scored on one common weight.  The same walk was measured on a synthetic blank in test_background_measured.py (0.8315 on two terms to 0.6479 on six); this row is that mechanism on data nobody built

**Measured:** scale 0.8413(107) on three terms, 0.6935(192) on six -- 6.7 combined esds apart and away from the hand-set minimum -- while Rwp under one weight *prefers* the six-term arm (0.075953 against 0.076946); 1.9.0 read 0.8374(113), 0.6935(196), 6.3 and 0.076381 against 0.077327

#### `test_the_blank_widens_the_weight_it_is_judged_by`

`characterisation` · dataset `si640c`

**Claims:** a measured background carries counting statistics, they enter the weight as sigma^2 + s^2 sigma_f^2, and Rwp is therefore a function of the declared scale -- so a column of Rwp down a scan of scales is not a ranking and every comparison needs one common sigma

**Referenced to:** one arm's own residual under two weights -- its own sigma and the specimen's alone -- so nothing about the fit changes between the two numbers

**Measured:** the held arm reads 0.073609 against its own sigma and 0.078843 against the specimen's, 7.1 % of the number being weighting rather than fit (0.074011, 0.079310 and 7.2 % on 1.9.0); down the scan the sigma-weighted minimum sits at s = 0.90 where the common-weight minimum is at 0.85, which is where the refined scale is

#### `test_the_blank_arms_render`

`ceiling` · dataset `si640c`

**Claims:** both blank arms render, including a window framed below the (111) so the halo is the only thing in the picture -- a correction that acts on 5 % of the range can be looked at rather than only summarised

**Referenced to:** existence, not a number -- a ceiling row

**Measured:** four PNGs to tests/output/si640c_blank_{held,free}[_halo].png

#### `test_the_fit_renders`

`ceiling` · dataset `si640c`

**Claims:** the obs/calc/diff rendering exists, so the fit can be looked at rather than only summarised

**Referenced to:** existence, not a number -- a ceiling row

**Measured:** one PNG written to tests/output/si640c_full.png

### `tests/test_acceptance_magnetic.py`

A magnetic moment on real neutron data, and the refusal of one. The pair is one specimen either side of its ordering temperature, so the same moment model is asked twice: below T_N the report calls the moment supported, along a from either in-plane seed; above it the report calls it unsupported and Rwp does not move. No moment here is certified, so the rows are characterisation -- the second is the one that separates no moment from a small invented one.

#### `test_the_4k_moment_is_supported_and_lies_along_a`

`characterisation` `ceiling` · dataset `cr2wo6_hb2a`

**Claims:** below T_N a moment under BNS 58.395 is reported supported, along a, and removes about half of the nuclear-only misfit

**Referenced to:** no certified moment exists; the band 1.9-2.3 mu_B is an envelope around GSAS-II's own 2.121 +/- 0.019 on the tutorial's steps (a black-box run, protocol NOT adopted) and the 2026-09-23 re-run's 2.078 +/- 0.066 from the tutorial's ICSD start -- never a cross-code bar

**Measured:** |m| 2.125 +/- 0.045 mu_B (47 sigma, bar 10), a-component 0.9994 of |m|; Rwp 0.1047 against 0.2035 nuclear-only (bar 0.65x); 1.9.0 read 2.124 +/- 0.043 (50 sigma), 0.9998 and Rwp 0.1042, before WP-2002's closing stage (#1085)

#### `test_the_4k_moment_does_not_depend_on_its_in_plane_seed`

`own_result` · dataset `cr2wo6_hb2a` · survives 2 starts

**Claims:** seeded along a or along b, the 4 K fit lands on the same moment

**Referenced to:** the same protocol from the other in-plane seed

**Measured:** |m| agrees to 1.2e-8 mu_B (2.6e-7 esd; bar 0.1 esd); Rwp to 1.6e-12 relative; 8.4e-6 and 2.8e-9 on 1.9.0, before WP-2002's closing stage (#1085)

#### `test_the_150k_null_finds_no_moment`

`characterisation` · dataset `cr2wo6_hb2a`

**Claims:** above T_N the same moment model is reported unsupported and does not move Rwp -- WP-1327's null, the one check separating no moment from a small invented one

**Referenced to:** the nuclear-only fit to the same 150 K pattern; the claim is inadmissibility (supported is False), not a value

**Measured:** |m| 0.067 +/- 0.330 mu_B (0.20 sigma, bar 3); Rwp 0.099241 against 0.099242 nuclear-only, 1.1e-5 relative (bar 1e-3 relative), both fitted with no closing stage; with one on the null alone, 1e-14 start nudges read 1.2e-3 at some starts, which was the closing stage (WP-2036, 2026-10-25, macOS arm64; Linux deff4c301). The esd grows as the modulus shrinks, since the moment's column vanishes at zero.  1.9.0's LM read the same 0.067 +/- 0.330 at 1.1e-5, the protocol having had no closing stage then either; TRF stopped at 0.067 +/- 0.83; the esd read 3.24 before WP-1929 left the stationary polar angle out of the covariance

### `tests/test_acceptance_magnetic_lamno3.py`

The second moment dataset, and the k = 0 case: LaMnO3 at 50 K on BT-1, from the GSAS-II Magnetic-I tutorial.  Two magnetic groups index every line, so the suite asks the tutorial's own question of both: Pn'ma' puts a supported moment along a and fits the pair of lines at 33.3 and 34.4 deg that Pnma, with its moment along c, does not.  The tutorial quotes no moment, so the rows are characterisation.

#### `test_the_50k_moment_is_supported_and_lies_along_a`

`characterisation` `ceiling` · dataset `lamno3_bt1`

**Claims:** under Pn'ma' (BNS 62.448) a Mn3+ moment is reported supported, along a with My held at zero as the tutorial holds it, below the spin-only ceiling, and removes about half of the nuclear-only misfit

**Referenced to:** no reference magnitude: the tutorial quotes none.  The band's ceiling is Mn3+'s spin-only gS = 4 mu_B; its floor of 3.3 mu_B sits under every protocol variant measured (3.54-3.56 mu_B with the axial or Lorentzian widths freed or held) -- never a literature value

**Measured:** |m| 3.560 +/- 0.043 mu_B (82 sigma, bar 10; 10.2 esd under 4 mu_B, bar 3), m = (3.546, 0, 0.317) mu_B: a-component 0.996 of |m| (bar 0.98); the polar angle ends 0.089 rad from 90 deg, where the symmetry fixes it, and has no esd (MOMENT_ANGLE_STATIONARY; it read 1.5 esd from 90 deg before WP-1929); Rwp 0.0629 against 0.1379 nuclear-only (bar 0.6x).  1.9.0 read 3.558 +/- 0.044, (3.543, 0, 0.325), 0.091 rad and Rwp 0.0631 against 0.1381

#### `test_pn_ma_beats_pnma_at_the_tutorials_pair`

`characterisation` · dataset `lamno3_bt1`

**Claims:** the tutorial's discrimination: both candidate groups carry a supported moment, along a under Pn'ma' and along c under Pnma, and Pn'ma' fits better, overall and at the pair of lines at 33.3 and 34.4 deg 2theta the tutorial names

**Referenced to:** the Pnma fit on the same protocol.  The tutorial reads the same pair and reports Rwp ~8.7 % against ~10 % at its Step 7, a protocol not adopted here

**Measured:** Rwp 0.0629 against 0.0842 (ratio 0.75, bar 0.85); chi2 over 32.8-35.0 deg 66 against 2709 (ratio 0.024, bar 0.1); Pnma |m| 3.337 +/- 0.069 mu_B, c-component 0.997 of |m| (bar 0.98); 1.9.0 read 0.0631 against 0.0844, 67 against 2711 (0.025) and 3.335

### `tests/test_acceptance_srm1976a_texture.py`

The spherical-harmonics texture (WP-1960) on a sintered NIST SRM 1976a corundum plate, against the solved TOPAS refinement committed beside the pattern, coefficient by coefficient (#131).  TOPAS states no normalisation, so the conversion is measured: the n = 0 terms close at ratio 1 and two other readings are excluded.  The one n != 0 term is zero in both codes, so its factor, sign and azimuth wait for a forward TOPAS run (WP-1973).

#### `test_the_protocol_matches_before_any_number_is_compared`

`cross_code` `ceiling` · dataset `srm1976a_plate`

**Claims:** Rexp reproduces TOPAS's, so both codes fitted the same channels under the same weights before any coefficient is compared

**Referenced to:** Rexp depends on the data, the weights and the free-parameter count only; TOPAS records r_exp 5.24587644 % over start_X 20 with 33 refined parameters

**Measured:** Rexp 0.0524721 against 0.0524588, 2.5e-4 relative; 11793 channels, 27 free parameters.  The gap is the parameter count and nothing else: Rexp goes as sqrt(N - P), and (11793 - 27)/(11793 - 33) puts the ratio at 1 + 2.55e-4

#### `test_c20_and_c40_agree_with_topas_with_no_conversion`

`cross_code` `ceiling` · dataset `srm1976a_plate` · survives 4 starts

**Claims:** Phase.texture's C2,0 and C4,0 equal TOPAS's y20 and y40 with no conversion factor, under TOPAS's protocol (cell held, ψ = 0)

**Referenced to:** the committed .inp's own y20 2.08901 and y40 0.87393; the bar is two of rietx's esds (which carry the Berar-Lelann factor, 4.35 here)

**Measured:** C2,0 2.0791(231), -0.43 esd; C4,0 0.8650(286), -0.31 esd; ratios 0.995 and 0.990; measured when the suite landed, before WP-2002's closing stage (#1085): 2.0794(233), -0.41 and 0.8652(288), -0.30

#### `test_the_measured_ratio_excludes_the_other_normalisations`

`cross_code` · dataset `srm1976a_plate` · survives 4 starts

**Claims:** the n = 0 conversion is measured: of three readings of TOPAS's harmonics, only ratio 1 (Von Dreele 1997, or Jarvinen's max-normalised harmonics, which agree for every n = 0 term) closes both orders

**Referenced to:** ratios 1, sqrt((2l+1)/4pi) and sqrt(2l+1), each stated from its source in the suite's docstring; one convention must close every term

**Measured:** ratio 1 misses by 0.43 and 0.31 esd; sqrt((2l+1)/4pi) by 33.0 and 4.4; sqrt(2l+1) by 112 and 61 (0.41, 0.30, 32.8 and 111 before the closing stage)

#### `test_c43_is_zero_within_error_in_both_codes`

`characterisation` · dataset `srm1976a_plate` · survives 4 starts

**Claims:** the one n != 0 term is zero within error in both codes, so its conversion factor (0.679 between the two surviving readings), sign and azimuth are not measured by this plate

**Referenced to:** TOPAS's y43m 0.00178 against rietx's own esd; the factor waits for a forward TOPAS run (WP-1973)

**Measured:** C4,3 -0.0021(225); TOPAS's 0.00178 is 0.08 of that esd

#### `test_the_fit_reaches_topas_rwp_with_physical_displacements`

`ceiling` · dataset `srm1976a_plate`

**Claims:** converged below TOPAS's Rwp with positive Biso and no texture positivity finding

**Measured:** Rwp 0.1142 against TOPAS's 0.1248 (TCHZ against PVII, two lines against CuKa5); Biso Al 0.992, O 0.963 A^2 against TOPAS's beq 1.210, 1.065 (0.1146, 0.995 and 0.962 before the closing stage)

**Diagnostics:** `BISO_NEGATIVE` asserted *absent*, `TEXTURE_NOT_POSITIVE` asserted *absent*

#### `test_without_texture_the_plate_fits_measurably_worse`

`own_result` `ceiling` · dataset `srm1976a_plate`

**Claims:** the positive arm: the same plate and protocol with no texture term fits far worse, so the comparison above can fail

**Referenced to:** the texture-free fit on the identical protocol

**Measured:** Rwp 0.3563 against 0.1142; chi2_red 46.09 against 4.74 (ratio 9.7, bar 5); 0.3562, 0.1146, 46.07 and 4.77 before the closing stage

## The one default this matrix decided

`Source.dispersion` shipped opt-in through v0.6 so that landing it did not
invalidate the record. WP-1001 was chartered to decide whether it should be the
default, and measured the question rather than inheriting the recommendation.

**For it.** Dispersion is the only correction in the package that needs *no
information the caller does not already have*. Capillary absorption wants muR,
roughness a surface, Stephens a strain model, March-Dollase a habit — dispersion
wants the species and the wavelength, both already in the model. Neglecting it
costs RMS 2.26 -> 0.69 wt % on round-robin QPA (0.62 on 1.9.0).

**The anchors survive.** SRM 660c's cell does not move (4.156882 A either way since WP-1938, 4.156895 A before).
SRM 676a's certificate-grade c/a moves +30.2 -> +30.6 ppm against a 100 ppm bar —
measured for this WP, since WP-0504 never checked it. And Rwp on corundum gets
*worse*, 14.574 -> 14.725 %, while the physics gets better: the rule at the top of
this document, now at the level of a package default.

**Against it, measured.** A wavelength inside an absorption-edge interval
**raises** rather than degrading — 12 of 1176 (element x shipped anode)
combinations including Eu and Ho at Cu Ka, and 0.0-1.2 % of arbitrary synchrotron
wavelengths depending on the specimen. Raising is kept deliberately: a selective
fallback would leave some species corrected and others not, manufacturing exactly
the unequal cross-phase bias the correction exists to remove, which is *worse*
than uniformly declining. `dispersion = None` is the one-line escape and the
diagnostic names it.

**Decided: flipped.** Absorbing it moved 21 tests, and the shape of that cost is
the lasting lesson — nine were bit-identity goldens with no opinion about
dispersion at all; they simply inherited it. Every test that pins a number now
declares this setting explicitly, and every golden is bit-identical again, which
is the evidence the flip touched physics and not plumbing. Two knock-on effects
are recorded rather than tuned away:

- Light-atom ADPs come back **less precise even as they come back less biased**:
  rutile U11/U33 separate at 5.1 sigma with the block on against 5.5 sigma without,
  because f" raises the heavy atom's share of every reflection.
- The calibrate -> freeze -> refine size/strain split degrades from 27 % low to
  39 % low — a bar that was already marginal on a degenerate direction
  (lor_size, gauss_strain and the frozen instrument X are one correlated triple).

## Known gaps

A matrix that lists only what passed is marketing. These are the holes a reader
should know about before trusting a number, each with what would close it.

- **Every acceptance number in the repo is a Cu Ka measurement.** Six anodes ship (Cr/Fe/Co/Cu/Mo/Ag plus Ka1-only variants) and what is verified for the other five is the wavelength table and its checks, not a refinement.  The cheapest close is one Co Ka pattern from an Fe-bearing specimen — the routine real case, since Cu Ka fluoresces Fe (mu/rho 297.7 vs 56.2) — which would exercise dispersion, absorption and the per-anode K-beta contamination check at once.

- **No dataset here can constrain a low-angle intensity correction.** The qarr phases first reflect at 25.6/28.3/31.8 deg and SRM 660c at 21.4, so surface roughness (WP-0502) has a negative acceptance result only: two of three phases collapse to the identity and raise ROUGHNESS_UNCONSTRAINED.  Closing it needs a pattern starting below ~15 deg with real low-angle reflections.

- **The SRM 660c certificate band is not reached and is not claimed.** Measured +24 ppm against a certificate uncertainty of +-8e-6 A.  The residual is a characterised cotTheta/sin2Theta aberration — equatorial divergence, tube tails, monochromator passband — which is the fundamental-parameters territory fenced to v2, not a tuning gap.

- **GoF does not reach 1 on lab data and should not be expected to.** Cline et al. (2015) put the floor for analytical-PSF fits on this instrument class at 1.5-1.9; FPA reaches 1.08.  Measured 1.63 on corundum with Rexp ~ 8.9 %, so Rwp 14.6 % is mostly counting statistics.  A policy demanding GoF -> 1 would be demanding FPA.

- **The Apple-GPU (MPS) evidence is maintainer-machine-only.** Every torch-mps assertion is gated on torch.backends.mps.is_available(), which is False on hosted macOS runners.  The all-fp32 refinement landing 3.5e-8 A from numpy fp64 is real-hardware evidence for the fp64-host boundary, and no CI job reproduces it.  A green macOS job must not be read as 'MPS verified'.

- **Multi-phase CIF round-tripping is not verified.** write_refinement_cif's round trip is checked single-phase only; a multi-phase re-read was never a v0.3 commitment.  Whatever the frozen API says about CIF round-tripping has to narrow to that.

- **The bit-identity goldens hold on one platform, by measurement.** tests/test_backend_shim.py's array_equal gate — the check that says no refactor changed a single computed number — is pinned to darwin/arm64 (GOLDEN_PLATFORM) and skips elsewhere.  WP-1002's CI matrix measured why: a numpy change does not move the goldens (2.4.6 and 2.5.1 agree bit for bit) but Linux x86-64 diverges on every state, by 1 ulp on quantities that are a single arithmetic chain and up to ~1100 ulp (1.7e-13 relative) on y_calc, which accumulates ~130 windows of transcendentals.  That gradient with chain length identifies a libm and summation-order difference, not a code difference, and even the worst of it is ten orders below the tightest physical bar here.  A hosted macOS/arm64 runner then reproduced 7 of 8 states at identical numpy/scipy/Accelerate and missed toy_rich by exactly one ulp, so the pin is really to a machine image and **no CI environment asserts these bits at all** — maintainer-machine evidence, the same shape as the MPS gap.  A tolerance wide enough to absorb a libm difference would absorb a real one too, so the gate stays exact and CI reports it instead.

- **Windows passes, once, and nothing keeps it that way.** Probed on a throwaway branch 2026-07-29: the fast suite is 982 passed / 115 skipped / 0 failed on windows-latest with Python 3.13.  Getting there fixed one real bug — write_qpa_table handed csv.writer output, which already ends \r\n, to write_text, so text mode translated each \n again and every row ended \r\r\n, i.e. corrupt CSV for Windows users and invisible on POSIX — plus every text read/write in the tree now names encoding=utf-8, since the default is cp1252 there and UTF-8 here.  tests/test_portability.py guards both by AST.  But **no scheduled job runs Windows**, so this is a point measurement, not a supported platform, and pyproject claims no OS classifier.

- **CI reports; it does not gate.** Branch protection needs a paid plan or a public repository, so nothing stops a red push landing on main today.  Every number in this document was produced by a green tree, but the enforcement that would keep it that way arrives with the v1.0 release (WP-1003).
