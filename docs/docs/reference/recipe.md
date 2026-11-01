# The PowderLine recipe

`read_recipe` turns a PowderLine recipe into the objects rietx refines, and `write_recipe_tables` writes the finished fit back out as the four tables PowderLine's consumers read.

[PowderLine](https://github.com/NSLS2/PowderLine) (D. Olds, NSLS-II beamline 28-ID-1, BSD-3-Clause) is a JSON recipe for a powder refinement.
One document carries the pattern, the instrument, the phases, the background and a refine flag for each parameter.
PowderLine sends the recipe to one of several engines and returns one result shape whichever engine ran.
The recipe holds the pattern's arrays inline.

Use a recipe when a pipeline already speaks the format and rietx is to be one of its engines.
For a fit you set up yourself, build the objects directly ([Patterns and structures](data.md), [The instrument](instrument.md)).

## Reading a recipe

<!-- api-doc: no-exec — it reads a recipe file the reader supplies -->
```python
import rietx as rx

recipe = rx.read_recipe("input.json")
for d in recipe.diagnostics:
    print(d.level, d.code, d.message)

ref = rx.Refinement(recipe.structure, recipe.instrument)
result = ref.fit(recipe.pattern, plan=recipe.plan,
                 two_theta_limits=recipe.limits)
rx.write_recipe_tables(ref, "output/")
```

`read_recipe` takes a path or a recipe already parsed into a dict, and returns a `Recipe`.
Pass the path where one exists.
A recipe carries its whole pattern, so a 4096-channel one is about 0.4 MB of JSON.
A payload that size belongs on a filesystem, and not in a prompt or a message body.
`read_recipe` also takes `diagnostics=`, as `read_pattern` does, to collect the diagnostics of several reads in one list.

A recipe rietx cannot represent raises `RecipeError`, naming the field ([Refusals](#refusals)).
`RecipeError` is a subclass of `ValueError`.

### Recipe fields

| Field | Holds |
|---|---|
| `Recipe.structure` | the phases, as a `Structure` |
| `Recipe.instrument` | the source, geometry, peak width and background, as an `Instrument` |
| `Recipe.pattern` | the pattern, as `PatternData` |
| `Recipe.plan` | a `RefinementPlan` that frees the parameters the recipe flags ([The refinement plan](#the-refinement-plan)) |
| `Recipe.limits` | the recipe's `fit_range` in degrees 2θ, inclusive at both ends, or `None` where the recipe states none |
| `Recipe.diagnostics` | every field dropped, convention assumed and value re-seeded |
| `Recipe.schema_name` | the `schema_name` the document declares |
| `Recipe.schema_version` | the `schema_version` the document declares |
| `Recipe.phase_names` | each phase's `phase_name` in the recipe, in order, or its key where it has none |

`Recipe.plan` and `Recipe.limits` are the recipe's own refinement intent, so pass both to the fit.
Each `Phase.name` in `Recipe.structure` is the matching entry of `Recipe.phase_names`.

The reader was checked against `schema_version` 0.26.0.
It reads any other version and reports `RECIPE_SCHEMA_UNTESTED`.
A version whose layout has moved fails at the field that moved, naming it.

### Diagnostics

Read `Recipe.diagnostics` before the answer.
Every code begins `RECIPE_`.
Several mean the fit differs from the reference engine's in a stated way, such as a dropped refine flag or a declined engine default.
[Diagnostics: reading files](diagnostics-files.md) explains each code.

### Fit range and channel count

`fit_range` is a pair of angles, and two engines can select different channels from it.
On the committed recipes rietx's inclusive mask selects 3767 of 4096 channels, from 1.000356° to 14.997604°.
GSAS-II's own `fit_profile.txt` fitted 3768, because it keeps the first channel past the upper limit, at 15.001321°.
`RECIPE_FIT_RANGE_CHANNELS` reports the count.
Check it against the reference engine's before you compare an Rwp.
To reproduce another engine's residual exactly, pass that engine's own range as `two_theta_limits`.

A channel with weight 0 is how PowderLine excludes a point.
Such a channel has no finite σ, so it becomes an excluded region, reported as `RECIPE_ZERO_WEIGHT_EXCLUDED`.

## Neutron recipes

A `PNC` instrument is constant-wavelength neutron.
Its axis is 2θ in degrees, as for `PXC`, so the reader builds it.
`Recipe.instrument` then carries a `NeutronSource` whose wavelength is the recipe's `Lam`, with one wavelength and the polarisation factor pinned at 1.

A stated `Polariz.` has no effect on a neutron pattern.
GSAS-II applies the polarisation factor only to an X-ray type, and `NeutronSource` pins it at 1.
The reader drops it and reports `RECIPE_FIELD_DROPPED`.
A refine flag on it raises `RecipeError`.

## Refusals

A recipe this package cannot represent raises `RecipeError`, naming the field.
PowderLine's own rule for an engine is to reject loudly what it cannot represent, and never to ignore a refine flag silently.

| Refused | Because |
|---|---|
| `schema_name` other than `GSASII_Rietveld` | `GSASII_SPF` is single-peak fitting. rietx does that with `fit_peaks`, which refines no model and so takes no recipe |
| `Type` other than `PXC` or `PNC` | `PNT` (time-of-flight) and `PXE` (energy-dispersive) put a flight time or a photon energy on the x axis, and this reader translates 2θ recipes only. The pink-beam `PXB` and `PNB` need a different profile function from the constant-wavelength one |
| a refine flag on the wavelength | for one pattern, λ and the cell enter only as d = λ/(2 sin θ), so a free λ beside a free cell is a direction the data cannot fix. Calibrate λ on a standard with its cell held instead |
| a non-zero `Zero` | PowderLine states its unit two ways, a factor of 100 apart |
| a non-zero `Z` | rietx's Lorentzian width is X/cos θ + Y·tan θ, with no constant term |
| a negative `W`, `X` or `Y` | rietx bounds these below at zero, and `W` at 1e-8 deg², so the fit would start from a model the recipe did not describe. Both committed LaB<sub>6</sub> reference fits converge to a negative `Y`, so a recipe seeded from a previous GSAS-II or TOPAS fit can carry one |
| a `size_broadening` or `strain_broadening` `model` other than `isotropic` | PowderLine itself raises `NotImplementedError` for these |
| a size or strain magnitude of zero or less | a crystallite size and a microstrain are positive |
| an `LG_eta` outside 0 to 1 | it is the Lorentzian share of one magnitude. GSAS-II does not bound it, and a committed reference fit refined it to 1.5×10<sup>4</sup> |
| a background peak whose Lorentzian FWHM is wider than one 2θ step | rietx's background peak, `HumpComponent`, is a Gaussian |
| an atom with `ADP` set to `Uaniso` | anisotropic displacement through a recipe is not read yet |
| a top-level `single_peaks` block with any live entry | free-standing peaks are not part of a refinement here, and `fit_peaks` fits them on their own. The `background.single_peaks` block is a different block, and the reader reads it |

A missing or malformed field also raises, naming its path in the document.
So does a `fit_range` that leaves fewer than 10 channels.

`Zero` is refused because PowderLine states its unit twice and the two statements disagree.
Its `easydiffraction` engine converts `Zero` as centidegrees.
Its configuration loader annotates it "degrees 2theta".
The two readings differ by a factor of 100, which gives a wrong cell rather than a slightly wrong one.
No committed recipe carries a non-zero `Zero` to settle the question.
Where two statements in a file contradict each other, rietx leaves the choice to you, as its CIF reader does for a cell angle that contradicts its space group.

A value at the model's identity is dropped instead, with a diagnostic.
`Z = 0` is no constant Lorentzian, and a background peak's Lorentzian width under one 2θ step is a width the data cannot hold.
Whether the recipe flags the value decides only the level.
A fixed one is reported as `RECIPE_FIELD_DROPPED`, at `info`.
A flagged one is reported as `RECIPE_FLAG_DROPPED`, at `warning`, because the fit then has one free parameter fewer than the reference engine.

## Unit conventions

| Recipe field | Unit | Becomes |
|---|---|---|
| `U`, `V`, `W` | Gaussian variance in centidegrees² | `instrument.profile.u`, `instrument.profile.v`, `instrument.profile.w`, × 8 ln 2 × 10⁻⁴ |
| `X`, `Y` | Lorentzian FWHM in centidegrees | `instrument.profile.x`, `instrument.profile.y`, × 10⁻² |
| `isotropic_size` | µm | `phases.*.lor_size` = 0.018·η·λ/(π·D) and `phases.*.gauss_size` = [0.018·(1 − η)·λ/(π·D)]² |
| `isotropic_strain` | 10⁻⁶ Δd/d | `phases.*.lor_strain` = 1.8×10⁻⁴·η·µ/π and `phases.*.gauss_strain` = [1.8×10⁻⁴·(1 − η)·µ/π]² |
| `LG_eta` | fraction | η, the Lorentzian share in the two rows above |
| `SH/L` | (S + H)/L | `instrument.geometry.axial_sl` = `instrument.geometry.axial_hl` = SH/L ÷ 2 |
| `Uiso` | Å² | `biso` = 8π²·Uiso |
| `Itth_weights` | 1/σ² | `PatternData.sigma` = 1/√w |
| `fit_range` | degrees 2θ, inclusive at both ends | `Recipe.limits` |

The width conversions were measured against the GSAS-II output PowderLine commits beside its LaB<sub>6</sub> recipe.
The peak list's own `sigma_squared` column reproduces U tan²θ + V tan θ + W to six decimals on all 49 reflections.
The `LG_eta` split follows upstream's own TOPAS engine.
The `SH/L` halving is adopted rather than measured, because no committed recipe can tell it from an uneven split, and the reader reports it as `RECIPE_CONVENTION_ASSUMED`.
`tests/data/README.md` in the repository gives the full table and how each row was established.

GSAS-II carries one magnitude for each broadening effect and a Lorentzian share `LG_eta`.
rietx carries a Lorentzian and a Gaussian parameter for each effect, and no share.
So the reader splits the magnitude.
η of it becomes the Lorentzian coefficient and (1 − η) the Gaussian one, squared because `gauss_size` and `gauss_strain` are FWHM² terms.
At η = 1 the Gaussian half is exactly zero.
That half stays fixed at zero, so the recipe's own η stands and the magnitude refines.
`RECIPE_FLAG_DROPPED` says the fit runs one parameter short of the reference engine's.
Where the recipe flags `LG_eta` itself and both halves are non-zero, both refine, and `RECIPE_FLAG_TRANSLATED` says so.

### Values not carried across

Some numbers in a recipe describe another engine's state, and the reader replaces them.

- The Chebyshev background coefficients start at zero (`RECIPE_BACKGROUND_RESEEDED`). The two codes scale the polynomial's domain differently, so the numbers would describe a different curve here. The term count and the refine flag carry across.
- Each phase scale is re-seeded so that the summed calculated intensity matches the data (`RECIPE_SCALE_RESEEDED`). Each code normalises a scale its own way, and on the committed recipes GSAS-II and TOPAS converge four orders of magnitude apart for the same specimen.
- A broadening block present with a null magnitude is left at zero broadening (`RECIPE_ENGINE_DEFAULT_DECLINED`). GSAS-II fills it with its own project defaults, 1 µm and 1000 × 10⁻⁶. The recipe states no value, so rietx adds none.
- Anomalous dispersion is switched off where the wavelength lies outside the bundled table's 3-70 keV band (`RECIPE_DISPERSION_DECLINED`). Both committed recipes are at 0.1665 Å (74.5 keV).

A `min` or `max` the recipe states is applied, and `RECIPE_BOUND_HONOURED` says so.
PowderLine documents these limits as not implemented in GSAS-II, so a parameter that ends on one is a difference from that engine.

## The refinement plan

PowderLine runs one pass over every flagged parameter.
Translated as a single stage, that pass fails from a cold start.
On the two-phase recipe it walked a monoclinic cell to a = 4231 Å.

So `Recipe.plan` frees the flagged parameters over several stages, in the McCusker et al. (1999) turn-on order the `mccusker_default` and `mccusker_structural` presets follow ([Plan presets](plans.md)).

| Stage | Frees |
|---|---|
| `scale_bkg` | phase scales and background coefficients |
| `zero` | the zero shift |
| `cell` | lattice parameters |
| `profile_w` | `W` |
| `profile` | the other peak-width terms, axial divergence and polarisation |
| `extra_components` | background peaks |
| `sample_broadening` | size and strain |
| `coordinates` | atom coordinates |
| `displacement` | Biso and occupancies |

A stage appears only where the recipe flags something in it, and `RECIPE_PLAN_STAGED` names the stages.
The LaB<sub>6</sub> recipe runs four of them and the two-phase recipe three.
Staging is cumulative, so the last stage frees everything the recipe flags in one pass.
The set of free parameters at the end is the recipe's, and only the order is rietx's.
A recipe that flags nothing gets one stage that frees nothing, and `RECIPE_NOTHING_REFINED`.

Two controls are not translated.
`refinement_cycles` is GSAS-II's cycle count, while a stage's iteration limit in rietx guards against a runaway fit and is not a schedule.
`refinement_algorithm` is not read, and the fit runs rietx's own solver.
Each is reported as `RECIPE_FIELD_DROPPED`.

## The four tables

`write_recipe_tables` takes the `Refinement` after its fit, because the peak list needs the compiled model's per-reflection widths and |F|².
A `RefinementResult` does not carry them.
Before a fit it raises `RuntimeError`.
It returns a dict from each table's name to the path written.

| File | Holds |
|---|---|
| `refined_parameters.csv` | one row for each refined parameter, with its value and esd |
| `<phase>_unit_cell_report.csv` | one file for each phase: the six lattice parameters and the cell volume, with esds |
| `<phase>_peak_list_report.csv` | one file for each phase: h, k, l, multiplicity, d-spacing, 2θ, `sigma_squared`, `gamma`, `F_calc_squared` and the phase name, for the primary emission line |
| `fit_profile.txt` | the fitted channels, tab-separated: 2θ, observed, weight, calculated, difference, background, Q and d-spacing |

`<phase>` is the phase's name.
`phase_names=` maps a phase name to another file name where they differ, and a recipe read with `read_recipe` needs no map.
`sigma_squared` and `gamma` are written in GSAS-II's centidegree units.
`fit_profile.txt` holds the channels the fit used, as TOPAS writes it.
GSAS-II writes the whole scan, with zeros outside the range.

Three of the four headers are a real contract, and the peak list's is not.
GSAS-II and TOPAS write byte-identical headers for the parameter table, the cell table and the profile, and rietx reproduces those byte for byte.
For the peak list they write different headers, 15 columns against 11, sharing nine.
rietx writes the columns it can fill honestly, so `F_obs_squared` is absent.
An observed |F|² from a Rietveld fit is I(calc) times the reflection's own observed-over-calculated ratio, so it favours whatever model partitioned it.

An esd field is empty where nothing computed the number, and `0` where the parameter was held.
In the cell table, `cell_volume` always has an empty esd, because propagating one needs the cell's covariance through dV/d(a, b, c, α, β, γ), and the writer does not do that yet.
A lattice parameter held by the recipe or by symmetry has an esd of `0`, as in both reference engines' tables.

## The cross-engine fixtures

`tests/data/powderline/` in the repository holds two committed recipes, a two-phase cathode and a LaB<sub>6</sub> instrument calibration.
Each comes with the GSAS-II and TOPAS refinements of the same pattern.

The two reference engines disagree.
On the cathode they differ by 2668 ppm on the cubic cell, and GSAS-II reports its own fit singular.
rietx lands within 96 ppm of TOPAS on every free lattice parameter.
[Two phases against TOPAS and GSAS-II](../switching/validation.md#two-phases-against-topas-and-gsas-ii) gives the numbers, and `tests/test_acceptance_powderline.py` asserts them.

Read that as the calibration for any comparison between engines made through this format.
The cells are comparable across engines, and the broadening coefficients are not.
