# Reference

Reference pages list names you look up: the API, the parameters, the plans, the diagnostic codes and the files rietx writes.

Most of them are built from the code that owns their facts, so they match the version this manual was built from.

- [API: everyday calls](api.md), [API: techniques](api-techniques.md) and [API: everything else](api-types.md) give each exported name with its signature or fields.
- [The command line](cli.md) gives each `rietx` subcommand with its options, its output and its routes.
- [Patterns and structures](data.md) gives the fields of `PatternData`, `Structure`, `Phase`, `Cell`, `Atom` and `Parameter`.
- [The instrument](instrument.md) gives the fields of `Instrument`: its constructors, the X-ray, neutron and time-of-flight sources, the geometry, the peak width, the background and declared extra peaks.
- [Pattern files](pattern-files.md) gives the formats `read_pattern` opens, where each takes its esds, and what each reader repairs, reports or refuses, time-of-flight banks included.
- [Structure files](structure-files.md) gives what a CIF and a magnetic CIF read and write, and how a magnetic phase crosses to and from TOPAS and FullProf.
- [Instrument files](instrument-files.md) gives the instrument profile, the GSAS-I `.prm` and `.iparm` and the GSAS-II `.instprm`, with what each reader converts and refuses.
- [Refinement files from other programs](foreign-files.md) gives what `read_project_model` reads from a GSAS-II, GSAS, TOPAS or FullProf refinement, how it recognises each format, and which TOPAS constructs it carries.
- [Files written for other programs](foreign-writers.md) gives what the TOPAS, FullProf, GSAS and GSAS-II writers put in a file, and what each refuses.
- [Models of other programs' files](foreign-models.md) gives the fields of `TopasModel`, `FullProfModel`, `GsasModel` and `Gsas2Model`.
- [Pattern diagnostics](pattern-diagnostics.md) gives each field `diagnose` measures on a pattern before a fit, and the two low-angle checks a fit adds.
- [Parameter map](parameters.md) lists every refinable parameter, grouped by what it does.
- [The parameter table](parameter-table.md) gives the fields of a `ParameterRow`, why a row cannot be freed, ties and restraints, the bounds a fit runs in, what `set_vary` and `set_values` return and refuse, the rows a result reports, and the profile interval.
- [Stage settings, flags and options](settings.md) lists the other names rietx uses: stage settings, peak flags, peak origins, reader options, instrument preset fields and indexing search settings.
- [Plan presets](plans.md) draws each preset's stages.
- [The refinement](refinement.md) gives the calls that run a fit and where each setting goes, the fit modes, the plan and stage objects and their stored form, what each stage records, the guard findings, the event stream, cancellation and the provenance record.
- [Magnetic refinement](magnetic.md) gives the satellite test for unexplained intensity, the moment and magnetic space group fields, what the report says about a moment, the magnetic peak width, and `solve_magnetic` with its answer types.
- [Peak lists for indexing](peaks.md) gives what `pick_peaks` and `fit_peaks` return and refuse, the fields of a `PeakList` and an `ObservedPeak`, the peak flags, and whether a list can be indexed, with its systematic-shift screen.
- [The indexing search and its result](indexing.md) gives what `index_pattern` takes and refuses, its engines, presets and search settings, and the fields of an `IndexingResult` and each `CellCandidate`, with the confidence gate and its caveats.
- [Indexing evidence and the route to a phase](indexing-evidence.md) gives the evidence view of an indexing result, the figures drawn from it, and how a candidate cell becomes a phase to refine.
- [The extinction symbol](extinction.md) gives `determine_extinction_symbol`: what it takes and refuses, the ranked extinction classes it returns with their space groups, when it answers, and the prior that declares what the chemistry rules out.
- [Sequential refinement](series.md) gives `refine_sequential` and `SequentialRefinement`: the arguments of a series, what crosses from one pattern to the next, the `SeriesResult` with its trajectories, the series diagnostics and the restart ladder.
- [Joint refinement](joint.md) gives `refine_multi` and `MultiHistogramRefinement`: which parameters the patterns share, two radiations and a refinable wavelength, the per-pattern result, and a report per pattern.
- [Parametric refinement](parametric.md) gives `CoordinateTable` and `ParametricEquation`, what a declaration refuses, the coefficients a fit reports, the test of the declared form and the equation at any coordinate.
- [The refinement result](result.md) gives what a `RefinementResult` carries beside the refined values: the agreement statistics, the structure R-factors, the observation count, the identifiability evidence, the restraint and absorption records, the diagnostics and the printed views.
- [Result fields](result-fields.md) says what each field of a `RefinementResult`, a `StageResult`, a `SeriesResult` and a `SeriesEntry` holds, and what it means when it is empty.
- [Derived quantities](derived.md) gives the distances, angles, cell volumes, crystallite sizes and microstrain a fit computes, with their esds.
- [Phase fractions](qpa.md) gives the weight fractions a Rietveld fit reports, the width profile that tests whether a fraction is determined, and the Brindley microabsorption correction.
- [The fit report](report.md) gives the fields of a `FitReport`: the misfit regions and unmatched peaks, the attribution and its gates, the trends, texture and strain readings, the suggested actions and the report at each stage.
- [Report evidence](report-evidence.md) gives the report's background, esd and Le Bail gap sections.
- [Model comparison](comparison.md) gives `Refinement.suggest`, `compare_freed`, the cumulative Δχ² and split localisation of two fits, and the rigid-body check.
- [Diagnostic codes](diagnostics.md) lists every code with its name, and links the page that explains it.
- [Project and run directories](project.md) shows the files in a `.rex` project and gives the fields of `project.json`, what opening one checks, and the run directories a fit writes.
- [Exports and derived tables](exports.md) gives the three export writers, the calculated pattern and its tick positions, the reflection list, the items a refinement CIF holds, and the value(esd) notation.
- [Figures and structure pictures](figures.md) gives the fit figure's options and `render_structure`, which draws a phase to a PNG and reports what the picture hides.
- [The refinement history](history.md) gives the fields of a history node, the actions that commit one, what a checkout restores, the queries on a tree and the format of the `history.jsonl` log.
- [Names in other programs](foreign-names.md) gives each parameter's name in GSAS-II, GSAS, TOPAS and FullProf.
- [The GUI panel by panel](gui-guide.md) says what each panel of `rietx gui` is for.
- [The GUI as a text document and a wire](gui-power.md) gives the `.rxt` grammar, the keyboard, the command palette and the HTTP routes.
- [Calling rietx from a program](programs.md) gives the exceptions and answer types a program meets, an answer's JSON form and each arm of `capabilities()`.
- [The PowderLine recipe](recipe.md) gives what `read_recipe` reads, refuses and converts, and the four tables `write_recipe_tables` writes.
- [For agents](agents.md) says how an agent gets the rietx skill.
- [Compatibility](compatibility.md) says what a version string promises and which parts are declared provisional.

```{toctree}
:hidden:

api
api-techniques
api-types
cli
data
instrument
pattern-files
structure-files
instrument-files
foreign-files
foreign-writers
foreign-models
pattern-diagnostics
parameters
parameter-table
settings
plans
refinement
magnetic
peaks
indexing
indexing-evidence
extinction
series
joint
parametric
result
result-fields
derived
qpa
report
report-evidence
comparison
diagnostics
project
exports
figures
history
foreign-names
gui-guide
gui-power
programs
recipe
agents
compatibility
```
