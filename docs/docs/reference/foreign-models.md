# Models of other programs' files

This page gives the fields of the model each reader of another program's refinement returns: `TopasModel`, `FullProfModel`, `GsasModel` and `Gsas2Model`, with the parts each one is built from.

`read_project_model` hands one of these on as `ProjectModel.stated` ([Refinement files from other programs](foreign-files.md)).
A model is what the file said, seeded with nothing.
A value the file omitted arrives as `None` and never as a default.
The models differ from each other because the formats do, and each one changes as its reader's coverage grows ({ref}`provisional-by-declaration`).

## TOPAS input files

`read_topas_inp` returns a `TopasModel`.

| Field | Holds |
|---|---|
| `TopasModel.path` | the file it was read from |
| `TopasModel.phases` | the phases the file states, with their sites and refine flags |
| `TopasModel.r_wp`, `TopasModel.gof` | the run's own figures, stated at top level above every block. `None` where the file states none there or several, since `Tr_wp` can hang off each dataset as well |
| `TopasModel.r_wp_all`, `TopasModel.gof_all` | every such value in file order, since a multi-dataset file states one per dataset |
| `TopasModel.n_datasets` | how many `xdd`-family blocks the file opens, a data-file macro (`RAW(…)`, `XYE(…)`, `TOF_XYE(…)`) counting as one. More than one means the phases belong to different patterns |
| `TopasModel.data_files` | the pattern files it points at |
| `TopasModel.emission_lines`, `TopasModel.emission_macro`, `TopasModel.anode` | every emission line in file order, and the macro that named the profile (`CuKa5`, read as anode `CuKa`) |
| `TopasModel.wavelength` | the profile's reference wavelength: the `lo` of the `lo_ref` line, else of the line with the largest `la`, and `None` where the file states no profile |
| `TopasModel.geometry` | `"debye_scherrer"` only where the file states a capillary construct, `None` where every dataset is time of flight, and otherwise `"bragg_brentano"`. That last value is the reader's default, so read this field only as "a capillary was declared, or not" |
| `TopasModel.goniometer_radius_mm` | the goniometer radius, where the file states one |
| `TopasModel.background_terms`, `TopasModel.background_refined` | how many coefficients the `bkg` list states, and whether any is refined (`@`) rather than held (`!`). Both `None` when the file states no `bkg` |
| `TopasModel.skipped_blocks` | `str` blocks that stated no name, or neither a `space_group` nor a `mag_space_group`, with the cell, scale and `weight_percent` each did carry. Recorded whether or not a diagnostics list was passed |
| `TopasModel.coverage` | what the reader met and did not carry ([TOPAS constructs and their stances](foreign-files.md#topas-constructs-and-their-stances)) |
| `TopasModel.time_of_flight` | the datasets that are neutron time of flight, each with the constructs that said so. `to_structure` refuses their phases by name |
| `TopasModel.symbols` | every parameter the file declares, by name, with its value and refine flag: what a name in an equation refers to |
| `TopasModel.neutron` | whether the file states `neutron_data` |
| `TopasModel.lp_factor` | the angle of the file's `LP_Factor(c)`, or `None`. With `neutron`, what `to_structure(scale="rietx")` converts TOPAS's scale by |

## FullProf input files

`read_fullprof_pcr` returns a `FullProfModel`.

| Field | Holds |
|---|---|
| `FullProfModel.path`, `FullProfModel.title` | the file, and its `COMM` title line |
| `FullProfModel.pcr_name` | the `PCR-file:` name in the header comment, which is often another refinement's |
| `FullProfModel.phases` | every phase, nuclear and magnetic |
| `FullProfModel.nuclear_phases`, `FullProfModel.magnetic_phases` | the same, split. A magnetic phase always reads, and builds only as the moments of the nuclear phase it restates ([Structure files](structure-files.md#magnetic-phases-in-a-fullprof-input-file)) |
| `FullProfModel.chi2` | the converged figure, from the comment FullProf rewrites each cycle |
| `FullProfModel.control` | the `Job`/`Npr`/`Nph` control line, field by field |
| `FullProfModel.job` | the experiment the file declares: 0 for X-ray and 1 for neutron constant wavelength. A time-of-flight file (`Job = -1`) is refused at read |
| `FullProfModel.lambda1`, `FullProfModel.lambda2` | the wavelengths the refinement used |
| `FullProfModel.lambda_slot` | the refinable-wavelength slot of the zero-shift line, read for provenance. It can hold a stale value FullProf never used, so `lambda1` is the wavelength |
| `FullProfModel.zero_shift` | the zero correction and the sample-displacement terms, with their codewords decoded |
| `FullProfModel.background` | the background points the file declares, as (2θ, value) with their codewords |
| `FullProfModel.background_kind`, `FullProfModel.background_coefficients` | which background the file's `Nba` selects (interpolated points, or a polynomial, Fourier or Chebyshev series), and a series' coefficients with their codewords. A background held in a companion `.bac` file is refused at read |
| `FullProfModel.parameter_limits` | the hard limits the file's `Nre` count declares, one per refined parameter number. They are reported at the build (`FULLPROF_LIMITS_NOT_APPLIED`) and set no bound |
| `FullProfModel.excluded_regions`, `FullProfModel.fitted_range` | what the run left out, and the range it fitted |
| `FullProfModel.user_scatterers` | a neutron file's LINE-12 user scattering lengths, each read as the isotope it is the Sears b of. A name that is not an element and a mass number with that b is refused at read |
| `FullProfModel.dispersion` | an X-ray file's LINE-12 f′ and f″ per element, as stated. A pair differing from rietx's Cromer-Liberman value at the file's wavelength is refused at read |
| `FullProfModel.data_file`, `FullProfModel.pattern` | the data file the header comment names, and the pattern block's settings. The name is reported and never followed, since it is often stale |
| `FullProfModel.cycles` | the `NCY`/`Eps` line, field by field: the cycle count, the convergence criterion, the relaxation factors and the 2θ range and step |
| `FullProfModel.refined_parameter_count`, `FullProfModel.parameter_numbers` | the count of refined parameters the file declares, and every parameter number its codewords reference. Compare the two: they disagree in at least one real file |
| `FullProfModel.output` | the output options the file sets |

## GSAS experiment files

`read_gsas_exp` returns a `GsasModel`.
A GSAS experiment file holds the whole experiment rather than one phase, so the model is a tree: phases, histograms, and one entry per phase-and-histogram pair, which is where GSAS keeps the profile coefficients.

| Field | Holds |
|---|---|
| `GsasModel.path`, `GsasModel.title`, `GsasModel.version` | the file, its `DESCR` title and the GSAS version that wrote it |
| `GsasModel.phases` | every phase the file states |
| `GsasModel.histograms` | every histogram, with its machine and the pattern it points at |
| `GsasModel.hap` | the phase-and-histogram entries, keyed `(phase number, histogram number)` |
| `GsasModel.rwp`, `GsasModel.rp` | the run's own agreement indices |
| `GsasModel.reduced_chi2` | GSAS's `GDNFT` figure, which is reduced χ² rather than its root |
| `GsasModel.n_variables`, `GsasModel.n_observations` | how many parameters the run refined, and over how many channels |
| `GsasModel.unsupported` | one line per thing the read could not carry, kept whether or not you passed a list |
| `GsasModel.histogram`, `GsasModel.profile` | pick one histogram, or one pair's refined profile. Both refuse to choose when the file carries several and you named none |

A phase is a `GsasPhase`.

| Field | Holds |
|---|---|
| `GsasPhase.number`, `GsasPhase.name` | its `CRS` ordinal and the name the file gives it |
| `GsasPhase.space_group` | the symbol, as written |
| `GsasPhase.cell` | the lattice, its esds and its one refine flag |
| `GsasPhase.atoms` | the sites |
| `GsasPhase.kind`, `GsasPhase.magnetic` | GSAS's phase type, and whether it is one of the two magnetic ones |
| `GsasPhase.formula` | the `CHMF` unit-cell contents, per species |

Its lattice is a `GsasCell`.

| Field | Holds |
|---|---|
| `GsasCell.a`, `GsasCell.b`, `GsasCell.c`, `GsasCell.alpha`, `GsasCell.beta`, `GsasCell.gamma` | the lattice parameters |
| `GsasCell.esd_a`, `GsasCell.esd_b`, `GsasCell.esd_c`, `GsasCell.esd_alpha`, `GsasCell.esd_beta`, `GsasCell.esd_gamma` | their esds, where the run produced them |
| `GsasCell.volume`, `GsasCell.volume_esd` | the cell volume and its esd |
| `GsasCell.refined`, `GsasCell.damping` | the one refine flag and its damping. GSAS refines the cell as metric-tensor elements under one flag |

Each of its sites is a `GsasAtom`.

| Field | Holds |
|---|---|
| `GsasAtom.label`, `GsasAtom.species` | the site's name and its scattering species, in the file's own upper case |
| `GsasAtom.x`, `GsasAtom.y`, `GsasAtom.z`, `GsasAtom.occupancy`, `GsasAtom.multiplicity` | the site |
| `GsasAtom.uiso` | the isotropic displacement in Å², or `None` for an anisotropic site |
| `GsasAtom.uij`, `GsasAtom.anisotropic` | the six anisotropic values, or `None` |
| `GsasAtom.refine_xyz`, `GsasAtom.refine_u`, `GsasAtom.refine_occupancy` | the `X`, `U` and `F` letters of the file's own refine codes |
| `GsasAtom.damping` | the damping codes per group |

A histogram is a `GsasHistogram`.

| Field | Holds |
|---|---|
| `GsasHistogram.number`, `GsasHistogram.kind` | its ordinal and GSAS's `HTYP`, such as `PXC` for powder X-ray at constant wavelength |
| `GsasHistogram.is_powder`, `GsasHistogram.is_constant_wavelength` | that type, read for you |
| `GsasHistogram.data_file`, `GsasHistogram.instrument_file` | the pattern and `.prm` it points at, as the file spells them |
| `GsasHistogram.bank`, `GsasHistogram.anode` | the detector bank, and the anode `IRAD` names |
| `GsasHistogram.wavelengths` | the emission lines, Kα1 first |
| `GsasHistogram.zero`, `GsasHistogram.refine_zero` | the zero correction and its flag |
| `GsasHistogram.polarization`, `GsasHistogram.polarization_type` | the polarisation fraction and its type code |
| `GsasHistogram.ka2_ratio` | the Kα2/Kα1 ratio, or `None` where the field is blank |
| `GsasHistogram.excluded_regions` | what the run left out, without GSAS's spacer pair |
| `GsasHistogram.two_theta_range` | the range the data cover |
| `GsasHistogram.n_channels_used`, `GsasHistogram.n_channels_total` | how many points were fitted, of how many recorded |
| `GsasHistogram.scale`, `GsasHistogram.refine_scale` | the histogram scale and its flag |
| `GsasHistogram.background` | the background function and its coefficients |
| `GsasHistogram.default_profiles` | the profile sets the instrument file supplied, which is where the histogram started |
| `GsasHistogram.rwp`, `GsasHistogram.rp` | this histogram's own agreement indices |

A phase-and-histogram pair is a `GsasHap`.

| Field | Holds |
|---|---|
| `GsasHap.phase`, `GsasHap.histogram` | which pair this is |
| `GsasHap.phase_fraction`, `GsasHap.refine_phase_fraction` | the phase fraction and its flag |
| `GsasHap.profile` | the refined profile for this pair |
| `GsasHap.preferred_orientation` | the March-Dollase rows, each with its axis and flag |
| `GsasHap.extinction`, `GsasHap.refine_extinction` | the powder extinction coefficient and its flag |

Its profile is a `GsasProfile` of `GsasProfileTerm` rows.

| Field | Holds |
|---|---|
| `GsasProfile.function`, `GsasProfile.n_coefficients`, `GsasProfile.cutoff`, `GsasProfile.damping` | which GSAS profile function, over how many coefficients |
| `GsasProfile.terms` | the coefficients, named |
| `GsasProfile.by_name` | the same, keyed by GSAS's name for each |
| `GsasProfile.refined_names` | the ones the run was free to move, which is the protocol |
| `GsasProfileTerm.name`, `GsasProfileTerm.index` | GSAS's name for the coefficient and its 1-based position |
| `GsasProfileTerm.value`, `GsasProfileTerm.refined` | the file's own number, and its flag |
| `GsasProfileTerm.degrees` | the same quantity in degrees, or `None` where the unit is compound |

The background is a `GsasBackground`.

| Field | Holds |
|---|---|
| `GsasBackground.function`, `GsasBackground.n_coefficients` | which of GSAS's background functions, over how many terms |
| `GsasBackground.coefficients` | the terms themselves |
| `GsasBackground.refined`, `GsasBackground.damping` | whether the run refined them, and the damping |

### Profile coefficient names

The names come from the profile function the file declares.
GSAS's constant-wavelength function 2 has `LX` fourth, and function 3 has `GP` fourth.
A function this build cannot name is refused rather than read by position, because a width assigned to the wrong coefficient gives a plausible wrong answer and no error.

### Profile units

GSAS states the profile coefficients in centidegrees, and `GsasProfileTerm.degrees` converts them.
It is `None` for the anisotropic terms `L11` to `L23`, whose unit also involves d².
`None` there means no conversion was made, and the value need not be zero.

### Blank and unreadable fields

A blank field is not a zero.
The polarisation fraction and the Kα2/Kα1 ratio are both conventionally 0.5, and they sit in adjacent fields of one record.
Where the file leaves the ratio blank, `GsasHistogram.ka2_ratio` is `None`, and choosing a ratio is then yours to do explicitly.

A field that is written but is not a number is refused, and the read does not return `None` for it.
The message names the file, the record key, the card columns and the text.
A record like that is misaligned or corrupt, so nothing on it can be trusted by column.
The `.prm` reader shares the record grammar and refuses the same way.

A field of nothing but asterisks is Fortran's output for a value too wide for its field: the writer had the number and ran out of columns.
In a required field, such as a cell edge or a `.prm`'s `LAM1`, the read is refused with a message that says overflow.
In an optional one, such as an esd or the history Rwp, the field reads as `None`, and [`GSAS_FIELD_OVERFLOW`](diagnostics-projects.md#gsas_field_overflow) names the record and the columns.
One case no rule for a single field can catch: a number that spills across a field boundary and leaves two readable halves, such as a left-aligned `46.60` read as `46` and `.60`.

## GSAS-II project files

`read_gsas2_gpx` returns a `Gsas2Model`.
A GSAS-II project has the same tree shape as a `.EXP`: phases, histograms, and one entry per phase-and-histogram pair.
It carries two things the older format has no room for: the constraints the refinement ran under, and the list of variables it actually refined.

| Field | Holds |
|---|---|
| `Gsas2Model.path`, `Gsas2Model.saved_as`, `Gsas2Model.version` | the file you opened, where GSAS-II last saved it, and the revision that wrote it |
| `Gsas2Model.phases`, `Gsas2Model.histograms` | every phase, and every powder histogram |
| `Gsas2Model.hap` | the phase-and-histogram entries, keyed `(phase name, histogram name)`, GSAS-II's own keys |
| `Gsas2Model.vary_list`, `Gsas2Model.esds` | the variables the last refinement refined, in GSAS-II's `p:h:name` spelling, and their standard uncertainties in the same order. This is the protocol, stated by the file itself |
| `Gsas2Model.constraints` | the equivalences, holds and constraint equations, with their variables resolved into names |
| `Gsas2Model.rwp`, `Gsas2Model.gof`, `Gsas2Model.chi2` | the run's own agreement indices. `gof` is the square root of reduced χ². `chi2` is GSAS-II's `chisq`, which is Σw(I<sub>o</sub> − I<sub>c</sub>)² and not reduced |
| `Gsas2Model.n_observations`, `Gsas2Model.n_variables`, `Gsas2Model.converged` | how many channels, how many parameters, and whether GSAS-II called the run converged. `n_variables` is `None` where the file's `Rvals` does not state it, which happens |
| `Gsas2Model.unsupported` | one line per thing the read could not carry, kept whether or not you passed a list |
| `Gsas2Model.histogram`, `Gsas2Model.phase` | pick one by name or by number. Both refuse to choose when the file carries several and you named none |

A phase is a `Gsas2Phase`.

| Field | Holds |
|---|---|
| `Gsas2Phase.name`, `Gsas2Phase.number` | the name GSAS-II gives it, and its `pId`, which is the `p` of a `p:h:name` variable |
| `Gsas2Phase.space_group` | the symbol, as written |
| `Gsas2Phase.space_group_from_operators`, `Gsas2Phase.resolved_space_group` | the setting the project's own operators describe, and the symbol to build under: the first where the file settled one, and `space_group` otherwise |
| `Gsas2Phase.cell`, `Gsas2Phase.volume` | the six lattice parameters and the cell volume |
| `Gsas2Phase.refine_cell` | the one refine flag GSAS-II keeps for the whole cell |
| `Gsas2Phase.atoms` | the sites |
| `Gsas2Phase.isotope` | the isotope chosen per atom type, GSAS-II's `General['Isotope']` |
| `Gsas2Phase.kind`, `Gsas2Phase.magnetic` | GSAS-II's phase type, and whether it is a magnetic one |
| `Gsas2Phase.magnetic_partner` | GSAS-II's `magPhases` entry on a nuclear phase, verbatim and not interpreted |
| `Gsas2Phase.pawley` | whether the phase was fitted by Pawley extraction, in which case its refined quantities are intensities rather than sites |

GSAS-II writes the symmetry operations themselves, so a symbol such as `F d d d`, which the tables hold in two settings, is read from the operators rather than assumed.
`to_structure` builds under `Gsas2Phase.resolved_space_group`, and [`GSAS2_GPX_SETTING_FROM_OPERATORS`](diagnostics-projects.md#gsas2_gpx_setting_from_operators) says when it differs from the symbol.

GSAS-II keeps an isotope in `Gsas2Phase.isotope` rather than in the atom type.
`to_structure` builds a site whose type has a mass-number choice as that isotope, so `H` with `2` is `2H`.

GSAS-II does not document `magPhases`, so `Gsas2Phase.magnetic_partner` is not evidence of magnetic scattering.
On the public projects that carry it, it names one of the project's own histograms, and the project holds no magnetic phase.
A phase GSAS-II types `magnetic` is what makes the file's figures include magnetic scattering, and [`GSAS2_GPX_PHASE_MAGNETIC`](diagnostics-projects.md#gsas2_gpx_phase_magnetic) reports it.

Each of its sites is a `Gsas2Atom`.

| Field | Holds |
|---|---|
| `Gsas2Atom.label`, `Gsas2Atom.species` | the site's name and its scattering species, in the file's own spelling. GSAS-II writes an ionic charge sign first, as `Mn+3` |
| `Gsas2Atom.x`, `Gsas2Atom.y`, `Gsas2Atom.z`, `Gsas2Atom.occupancy` | the site |
| `Gsas2Atom.site_symmetry`, `Gsas2Atom.multiplicity` | what GSAS-II worked out about the position |
| `Gsas2Atom.adp`, `Gsas2Atom.anisotropic` | `I` or `A`, and that flag read for you |
| `Gsas2Atom.uiso`, `Gsas2Atom.uij` | the isotropic displacement in Å², and the six anisotropic values |
| `Gsas2Atom.refine_flags` | the letters the file carries, such as `XU`. An empty string is the file saying the site is held |
| `Gsas2Atom.refine_xyz`, `Gsas2Atom.refine_u`, `Gsas2Atom.refine_occupancy`, `Gsas2Atom.refine_moment` | those letters read one at a time |

A histogram is a `Gsas2Histogram`.

| Field | Holds |
|---|---|
| `Gsas2Histogram.number`, `Gsas2Histogram.name` | its `hId`, and the tree label that `Gsas2Model.hap` uses as a key |
| `Gsas2Histogram.kind`, `Gsas2Histogram.constant_wavelength` | GSAS-II's type code, such as `PXC`, and whether this build names its coefficients |
| `Gsas2Histogram.terms`, `Gsas2Histogram.by_name` | the instrument coefficients, and the same keyed by GSAS-II's name for each |
| `Gsas2Histogram.wavelengths` | the emission lines, primary first |
| `Gsas2Histogram.limits`, `Gsas2Histogram.measured_limits` | the range the refinement used, and the range the file was loaded with. The pair shows a narrowed range |
| `Gsas2Histogram.excluded_regions` | ranges masked out of the fit |
| `Gsas2Histogram.background` | the background function and its coefficients |
| `Gsas2Histogram.sample` | the refinable sample parameters with their flags, keyed by GSAS-II's own names (`Scale`, `DisplaceX`, `Shift`, `Absorption` and their kind) |
| `Gsas2Histogram.geometry`, `Gsas2Histogram.gonio_radius`, `Gsas2Histogram.temperature` | `Debye-Scherrer` or `Bragg-Brentano`, the radius in mm, and the temperature |
| `Gsas2Histogram.n_points` | how many channels the file carries |

An instrument coefficient is a `Gsas2Term`.

| Field | Holds |
|---|---|
| `Gsas2Term.name` | GSAS-II's own name, such as `U` or `SH/L` |
| `Gsas2Term.value`, `Gsas2Term.initial` | the refined number and the one it started from, which the format keeps side by side |
| `Gsas2Term.refined` | whether the run was free to move it |
| `Gsas2Term.degrees` | the same quantity in degrees for the six centidegree coefficients, and `None` for everything else |

The background is a `Gsas2Background`.

| Field | Holds |
|---|---|
| `Gsas2Background.function` | GSAS-II's own name for it, such as `chebyschev-1` |
| `Gsas2Background.coefficients`, `Gsas2Background.refined` | the terms, and whether the run refined them |
| `Gsas2Background.n_debye`, `Gsas2Background.n_peaks` | how many diffuse terms and fitted background peaks sat beside them |

A phase-and-histogram pair is a `Gsas2Hap`.

| Field | Holds |
|---|---|
| `Gsas2Hap.phase`, `Gsas2Hap.histogram` | which pair this is |
| `Gsas2Hap.scale`, `Gsas2Hap.used` | the phase's scale in this histogram, and whether the pair was in the fit at all |
| `Gsas2Hap.size`, `Gsas2Hap.mustrain` | the sample broadening, which GSAS-II refines per pair |
| `Gsas2Hap.hstrain` | the hydrostatic-strain terms |
| `Gsas2Hap.preferred_orientation` | a March-Dollase entry: the model, its value, its flag and its axis. `None` for a spherical-harmonics entry |
| `Gsas2Hap.texture` | a spherical-harmonics entry, as a `Gsas2Texture`, or `None` |
| `Gsas2Hap.extinction` | the extinction coefficient |
| `Gsas2Hap.lebail` | whether this pair's intensities were extracted rather than calculated |

Size and microstrain are each a `Gsas2Broadening`.

| Field | Holds |
|---|---|
| `Gsas2Broadening.kind` | `isotropic`, `uniaxial` or `generalized`. Read this first |
| `Gsas2Broadening.values` | the direct numbers with their flags: a size in µm, a microstrain in units of 10⁻⁶ |
| `Gsas2Broadening.axis` | the unique axis a uniaxial model uses |
| `Gsas2Broadening.terms` | the hkl-dependent coefficients. The format writes this row whatever the model, so on an isotropic one it is the unused default |

A spherical-harmonics texture is a `Gsas2Texture`, in GSAS-II's own numbers.

| Field | Holds |
|---|---|
| `Gsas2Texture.order` | the highest even degree. Below 2 there is no term |
| `Gsas2Texture.coefficients` | each coefficient under GSAS-II's own name, such as `C(4,0)` |
| `Gsas2Texture.refined` | the one refine flag GSAS-II keeps for all of them |

A constraint is a `Gsas2Constraint`.

| Field | Holds |
|---|---|
| `Gsas2Constraint.kind` | the format's own letter: `e` equivalent variables, `c` a constraint equation, `h` a variable held, `f` a new variable |
| `Gsas2Constraint.group` | which variables it constrains: `Phase`, `Hist`, `HAP` or `Global` |
| `Gsas2Constraint.terms` | `(multiplier, name)` pairs, the names resolved out of the random-number ids the file stores |
| `Gsas2Constraint.value`, `Gsas2Constraint.vary` | the right-hand side of a constraint equation, and whether a new variable is refined |
| `Gsas2Constraint.is_equivalence` | whether it is an equivalence, the one shape `Refinement.tie_equal` reproduces in one call |

Anything with a flag beside it is a `Gsas2Value`, which holds `Gsas2Value.value` and `Gsas2Value.refined` and nothing else.

### The pickle allow-list

A `.gpx` is a sequence of Python pickles, and loading a pickle runs whatever it names.
So this reader resolves an allow-list and refuses every other name, naming it, without loading the file.
GSAS-II's own two classes are admitted as inert stand-ins that hold data and do nothing, which is why a project with constraints reads at all.
So a `.gpx` from a source you do not trust either opens, having named nothing outside the list, or is refused with a message naming the global.

### Instrument coefficient units

`Gsas2Term.degrees` converts `U`, `V`, `W`, `X`, `Y` and `Z` from centidegrees, and no other coefficient.
For `U`, `V` and `W` it changes the unit and nothing else.
The result is still a Gaussian variance in degrees², which is what GSAS-II states, so rietx's `profile.u`, `profile.v` and `profile.w` are 8 ln 2 times it.
Setting `profile.u = terms["U"].degrees` gives a Gaussian 2.35 times too narrow.
`instprm_factor` (in `rietx.io.projects.gsas2`) carries the whole factor, and [Instrument files](instrument-files.md#gsas-ii-instprm) gives the `.instprm` conversion.
`Zero` is already in degrees, which is where the two GSAS generations differ: GSAS writes that field in centidegrees and GSAS-II does not.
So `Gsas2Term.degrees` is `None` for `Zero`, meaning no conversion was needed.

### Refused phases

`to_structure` refuses these by name, naming the phase and leaving the numbers on the model:

- a magnetic phase, since the reader does not read a `.gpx` magnetic block yet (a magCIF of the same structure reads through `Structure.from_cif`);
- a macromolecular phase, whose atom records carry residue and chain columns this reader does not read;
- a Pawley phase, whose refined quantities are the reflection intensities;
- a phase with anisotropic sites, since no file here settles which off-diagonal convention GSAS-II wrote the anisotropic values in, and a wrong factor of 2 is a silently wrong Debye-Waller factor at high Q;
- a phase with no sites, which GSAS-II fits by extracting its intensities;
- a phase with no space-group symbol, or one this build does not resolve;
- an isotope choice that is not a mass number, or names a nucleus the Sears table rietx scatters from does not carry, since reading it as natural abundance would change the site's scattering length without saying so.

A file with no phases at all is refused too.
A negative `Uiso` is read as the file states it, and becomes a negative `Biso`.
A converged refinement can end there, and a fit that keeps it reports [`BISO_NEGATIVE`](diagnostics-refinement.md#biso_negative).

### Texture conversion

GSAS-II refines a spherical-harmonics texture per phase and histogram.
`to_structure` carries it onto `Phase.texture` where one conversion holds at every reflection, and reports [`GSAS2_GPX_TEXTURE_CONVERTED`](diagnostics-projects.md#gsas2_gpx_texture_converted).
GSAS-II puts a Bragg-Brentano histogram's sample angle at 90°, and rietx puts it on the plate normal.
So each coefficient is multiplied by the Legendre polynomial P<sub>l</sub>(0), which is −1/2 at l = 2.
The warning under {eq}`corr-sh` gives the whole conversion.
In Laue classes 4/m, −3 and 6/m the n ≠ 0 terms take a further √2.
Fitted under the `bragg_brentano` geometry, the carried texture gives GSAS-II's own multipliers to GSAS-II's single precision.

The phase builds without the texture in four cases, and [`GSAS2_GPX_TEXTURE_NOT_CARRIED`](diagnostics-projects.md#gsas2_gpx_texture_not_carried) says why:

- a Debye-Scherrer histogram, where GSAS-II's sample angle follows θ, so no constant converts it;
- histograms that disagree, including a histogram where the phase has no texture. A phase here has one texture, which a joint fit shares. Histograms that differ only in the refine flag agree, and the texture is freed;
- a term GSAS-II 5.8.4 evaluates wrongly. Its function takes two values on one set of equivalent reflections, so its coefficient matches no invariant function. This happens for every n ≠ 0 term in −1 and 2/m, for every term on rhombohedral axes, and for the n = 3 terms of −31m. A zero coefficient there is dropped, since nothing is lost;
- a name no term of the class matches.

A cubic phase at order 2 has no term, so nothing is lost, and the report says so at `info`.
A March-Dollase entry stays on `Gsas2Hap.preferred_orientation` and is not carried.
