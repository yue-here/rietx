# 7g. The project and recipe readers: what an imported file does not carry

Load it when you read another program's *project* file — a TOPAS `.inp` or a FullProf `.pcr` — or its *recipe* file — a PowderLine recipe — and a `Diagnostic` came with it.

*A reference file of the `rietx` skill. The body it belongs to is [`SKILL.md`](../SKILL.md); section numbers are the ones the body cites.*

These are the codes of `rietx.io.projects` — one module per foreign format,
governed by WP-1118 — and of the PowderLine recipe reader. They are a different
channel from every other family in §7, but not because none of them ever
appears on `result.diagnostics`. The criterion that separates them is
**whose file you are reading**: another program's project or recipe file — a TOPAS `.inp`,
a FullProf `.pcr`, a PowderLine recipe — against your own data and structure
files, which every fit reads whether or not another program was ever involved.
Those own-file codes are in §7i,
[`diagnostics-reading.md`](diagnostics-reading.md) (WP-1415).
A project reader emits its codes at *import*, into a list you pass in
(`read_topas_inp(..., diagnostics=[])`,
`rietx.io.projects.fullprof.to_structure(..., diagnostics=[])`); the recipe
reader emits its own at the read (`read_recipe`, `Recipe.diagnostics`). If you
do not pass a list the finding for a project import is still on the model —
`model.coverage.reported`, `model.skipped_blocks`, `species_raw` — but nothing
is raised. The two writers take the same list (`write_topas_inp(...,
diagnostics=[])`) for the one `_SPECIES_WRITTEN_NEUTRAL` row each emits.
So the question a project reader answers is not "is my fit wrong"
but **"is the model I just imported the model that file describes"**, asked
before a fit exists; the recipe reader answers a related but distinct question
of its own, below. GSAS and GSAS-II have a file of their own, §7h,
[`references/diagnostics-gsas.md`](diagnostics-gsas.md), holding four file
kinds between them and the writers that put three of them back, under the same
criterion.

The TOPAS `.inp` reader's magnetic rows (`TOPAS_MAGNETIC_GROUP_READ`, `TOPAS_MOMENT_CONVENTION`,
`TOPAS_MOMENT_ION_UNCHARGED`) and the FullProf `.pcr` reader's
`FULLPROF_MAGNETIC_PHASE_OMITTED` are in §7j,
[`references/magnetic.md`](magnetic.md), beside the rest of the magnetic
family. They fire at import and never reach `result.diagnostics`.

Each row states, as the others do, what you must *not* assume once it fires.
Two conventions run across the family. A reader **repairs and reports** where
the repair is a stated, recoverable loss and **refuses** where carrying on
would mean choosing between two readings of the file — so an `_NORMALISED` or
`_DROPPED` code is a repair you can undo, and a `_REFUSED` one is a build that
did not happen. And every construct a format can write is classified in
`rietx.io.projects.coverage`, one row per feature, so support for a construct
arrives by moving its row rather than by growing a reader.

| code | what you must not assume, and what to do |
|---|---|
| `TOPAS_SPECIES_NORMALISED` | (info — from the TOPAS `.inp` reader: pass `read_topas_inp(..., diagnostics=[])` to collect it; it is not on `result.diagnostics`) Assume the model's species are the file's literal tokens (`La+3` became `La3+`). Each message names its substitution and `where` lists the atoms it touched. The `.inp` sibling of `CIF_SPECIES_NORMALISED` |
| `TOPAS_ORIGIN_TRANSLATED` | (info — from the TOPAS `.inp` reader, same channel) Assume the space group is the file's literal symbol (`Pn-3mZ` became `Pn-3m:2`). Not cosmetic: dropping the suffix silently selects the *other* origin, so a Cu2O written on choice 2 would be built on choice 1's symmetry with nothing raised |
| `TOPAS_BLOCK_SKIPPED` | (warning — from the TOPAS `.inp` reader, same channel) A `str` block with a cell or sites and no `phase_name`/`space_group` is recorded on `model.skipped_blocks`, never dropped in silence; the message says what it lacked and what it carried. `to_structure` **refuses** where other phases build, because dropping a cell-bearing block would leave the weight fractions not summing. Read `model.phases`/`model.skipped_blocks` to see what the file states |
| `TOPAS_CELL_COUPLING_DROPPED` | (warning — from the TOPAS `.inp` reader, same channel) Two cell keys the file ties arrived as two independent numbers, because resolving either idiom copies the **value** and not the constraint. Both idioms are reported: `b = Get(a);` and `a = edge; b = edge;`. Reported only where the phase's own space group does **not** already tie the pair (under `P 4/m m m` rietx ties `b ← a` itself, so this stays silent). Tie the edges in the refinement plan before fitting, or read `model.phases` for the file's own text. The message names the idiom and `where` names the coupled key |
| `TOPAS_FIRST_RUN_READ` | (warning — from the TOPAS `.inp` reader, same channel) Assume the model is the one every run of the file refines. It is run 0's. Where the gated text is output commands (a multi-pattern reel file) the model is unaffected; where it gates phases or refinement flags, only run 0's is here. Read the gated `#if` blocks, or the `.inp` TOPAS wrote for the run you want. The message states the `num_runs` value, or says it could not be evaluated |
| `TOPAS_FEATURES_NOT_IMPORTED` | (warning — from the TOPAS `.inp` reader, same channel) **The import is partial, and this says how far it goes.** The numbers that reach the `Structure` are unaffected; what is missing is the model around them, so an Rwp computed against rietx's own profile is not comparable with the file's. One diagnostic per import, naming each feature and the keywords the file actually wrote. `model.coverage.reported` carries the same list whether or not a `diagnostics=` list was passed, and `model.coverage.partial` is the yes/no. A second diagnostic of the same code names **calls** to a macro the file never defines and the reader does not read (`model.coverage.unread_calls`), a user's include or a typo; a misspelt bare keyword is still silent, so `partial=False` is not a proof the file was read whole |
| `TOPAS_FEATURE_REFUSED` | (warning — from the TOPAS `.inp` reader, same channel) `read_topas_inp` **reads** such a file and records it; `to_structure` is what refuses, naming the construct and what building without it would claim. For a **time-of-flight dataset** (issue #193) `model.time_of_flight` names each dataset and what said so, and `to_structure(dataset=N)` still builds a constant-wavelength dataset of a mixed file. Read `model.phases` for what the file states and `model.coverage` for every construct the import does not carry. Which construct takes which stance is declared in `rietx.io.projects.coverage`, one row per feature; support for one arrives by moving its row |
| `TOPAS_SPECIES_WRITTEN_NEUTRAL` | (warning — from the TOPAS `.inp` **writer**: pass `write_topas_inp(..., diagnostics=[])` to collect it) `SPECIES_FALLBACK_NEUTRAL` is the same fact at fit time. No writer refuses a species for its charge (WP-1527). `value` is the fractional error on \|f\| at s = 0 and `where` lists every site. A digitless ion the table carries is not named: `Cu+` is written `Cu+1`, the Cu¹⁺ rietx computes |
| `TOPAS_FIELD_NOT_WRITTEN` | (warning — from the TOPAS `.inp` **writer**, same channel as `TOPAS_SPECIES_WRITTEN_NEUTRAL`) Assume TOPAS computes the pattern rietx did from the exported file. A `str`-only file (no `instrument=`) states the size and strain widths and a Stephens block, but no magnetic-only width, extinction or texture (a preferred orientation only with r ≠ 1). With `instrument=` the extinction is written, a magnetic-only width becomes a `mag_only` magnetic-part `str`, and only a preferred orientation with r ≠ 1 is named. `where` names each term |
| `TOPAS_PHASE_RESTATED_IN_P1` | (info — from the TOPAS `.inp` **writer** with `p1_expand="auto"`: pass `write_topas_inp(..., diagnostics=[])`) Expect a long `str` (one `site` per atom of the cell) and `mag_space_group 1.1`; the free set is still the fit's. To get a tabulated group instead, restate the phase in its standard setting before writing |
| `FULLPROF_SPECIES_NORMALISED` | (info — from the FullProf project reader: pass `rietx.io.projects.fullprof.to_structure(..., diagnostics=[])` to collect it; it is not on `result.diagnostics`) `read_fullprof_pcr` keeps the raw token on `species_raw`, so the model is checkable against the file even without this; the code fires only at the build, where the raw form is dropped. Each message names its substitution and `where` lists the atoms it touched. A magnetic form-factor label (`MCR3`) is left verbatim. On a neutron file a LINE-12 user b names its isotope, and the message says so (`LI7` → `7Li`; issue #558) |
| `FULLPROF_ORIGIN_CHOICE` | (info — from the FullProf project reader, same channel) Assume the built phase's space group is the `.pcr`'s literal symbol. FullProf writes **no** suffix, so the reader chose: origin choice 2 where the bare symbol resolves to 1 (`F D -3 M` → `F d -3 m:2`, the spinel case), and rhombohedral axes where the cell says so (`R -3 c` over an a = b = c, α = β = γ cell → `R -3 c:R`). The two R settings differ by a factor of three in general multiplicity. The choice is licensed by the occupancy-ratio check, which a wrong setting fails, except where `FULLPROF_OCCUPANCY_UNCHECKED` also fired, and then it is unlicensed |
| `FULLPROF_OCCUPANCY_UNCHECKED` | (warning — from the FullProf project reader, same channel) Assume the origin/axes choice above was verified. It was not: a single site is one equation in two unknowns (FullProf's `Occ` carries one arbitrary per-phase factor), and no better test repairs that. Confirm the setting against the published structure yourself, or add a site. `where` names the site |
| `FULLPROF_TIE_DROPPED` | (warning — from the FullProf project reader, same channel) Assume the built `Structure` has the same free parameters as the refinement the `.pcr` records. It has **more**. Whether this **reports** or **refuses** turns on one question: can you put the tie back in a single unambiguous call? A **cell** tie the space group does not hold equal (`a = b` under an orthorhombic or triclinic symbol, or a scaled `b = 2a`) and a **cross-site** tie in `Biso`/`Occ` **or in one coordinate column where every site involved has exactly one DOF** all report; this matches `TOPAS_CELL_COUPLING_DROPPED` one reader over. A tie whose restoring call would be a *choice* **refuses** instead: a group spanning different columns on different atoms, or a coordinate group touching a site whose DOF count is not 1, since `dof.k` on two different sites is not the same direction. `to_structure(..., drop_parameter_ties=True)` declares that you accept the looser model, and the message then says so. Either way, re-declare the constraint on the refinement, and **mind which spelling the call takes**: `Refinement.tie_equal(['phases.i.atoms.j.biso', ...])` on the column paths for a `Biso`/`Occ` group, but on the **DOF paths** (`Refinement.tie_equal(['phases.i.atoms.j.dof.k', ...])`) for a coordinate group, because a coordinate column already follows its own `dof` by site symmetry and `tie_equal` refuses to outrank that (`phases.0.atoms.1.x` raises `already follows 'phases.0.atoms.1.dof.0' (symmetry)`). `Refinement.tie(path, source, scale=multiplier)` for a signed one |
| `FULLPROF_LIMITS_NOT_APPLIED` | (info — from the FullProf project reader, same channel) Assume the built parameters are bounded as the `.pcr` bounds them. They are not: each `Nre` limit names a FullProf parameter *number*, kept on `model.parameter_limits`, and none becomes a `min`/`max`. Set one by hand where the parameter must stay inside it |
| `FULLPROF_SPECIES_WRITTEN_NEUTRAL` | (warning — from the FullProf `.pcr` **writer**, X-ray files only: pass `write_fullprof_pcr(..., diagnostics=[])`) The `.pcr` twin of `TOPAS_SPECIES_WRITTEN_NEUTRAL`: the `Typ` is the neutral element (`FE` for `Fe+`). A neutron file keys b on the element for every ion, so it substitutes nothing and never fires |
| `FULLPROF_RHOMBOHEDRAL_RESTATED` | (warning — from the `.pcr` **writer**: pass `write_fullprof_pcr(..., diagnostics=[])`) Assume the phase was already in hexagonal axes. FullProf reads `R -3 c` as hexagonal whatever the cell says, so the file has the hexagonal cell of the same lattice, every cell edge and coordinate held and the scale divided by 9. Free what you mean to refine; the ties between the old parameters are not stated |

The `RECIPE_*` family is the reader of the **PowderLine interchange format**
(`read_recipe`, `Recipe.diagnostics`) rather than `result.diagnostics`, and it
answers a question the others do not: *how does the fit I am about to run
differ from the one the recipe describes?* A recipe is written for whichever
engine gets it, so some of what it declares has no counterpart here, and every
such difference is a row below rather than a silence. Anything the format
states that this package cannot represent at all raises `RecipeError` naming
the field — see the manual's recipe chapter for the list and the reason behind
each.

| Code | What it means you must not do |
|---|---|
| `RECIPE_FLAG_DROPPED` | (warning) Compare this fit's free-parameter count, esds or χ² against the reference engine's as if the two refined the same problem. The flag was not honoured for GSAS-II's constant Lorentzian `Z`, a hump's Lorentzian γ, or a size/strain half that `LG_eta` put at exactly its off state (held there so the recipe's η stands). The starting model is unchanged (each is at its identity), so the answer is a fit to the same data with one fewer degree of freedom. `where` names what carries the difference instead |
| `RECIPE_FIELD_DROPPED` | (info) Assume every field of the recipe reached the model. A **fixed** value at its identity was dropped: `Z = 0`, a hump's γ under one 2θ step (a width these data cannot hold), `refinement_cycles` (the stopping rule here is the solver's ftol), and a `PNC` (neutron) instrument's `Polariz.` (`NeutronSource` pins K = 1). The *record* of what the recipe said is now this diagnostic and not the model |
| `RECIPE_FLAG_TRANSLATED` | (info) Look for a mixing parameter in the result. There is none; `where` gives the two coefficients a freed `LG_eta` became |
| `RECIPE_ENGINE_DEFAULT_DECLINED` | (info) Read a difference from the reference engine's broadening as a disagreement about the data. GSAS-II fills a null size or strain magnitude with its own project default (1 µm, 1000 × 10⁻⁶ Δd/d; Measured: off its committed output, not read from a manual). On a synchrotron pattern the strain default alone is 0.057°·tanθ, a quarter of the peak width at the top of the range (Measured), so the instrument terms will differ by however much that was. Another engine's project default is not physics; if you want it, state it in the recipe |
| `RECIPE_BACKGROUND_RESEEDED` / `RECIPE_SCALE_RESEEDED` | (info) Compare a background coefficient or a phase scale against the recipe's own number, or against another engine's. The term count and the refine flag are carried; the values are re-seeded, the scale by matching the summed calculated intensity to the data. (Measured: on one committed specimen GSAS-II converges to a scale of 3.77e-2 and TOPAS to 2.61e-6.) **Phase scale *ratios* are comparable and the absolute values are not**, which is what a recipe quantifying phase fractions actually needs |
| `RECIPE_BACKGROUND_PEAK_DEGENERATE` | (warning) Quote the background-peak parameters, or expect the fit to converge. The peak correlates with the low-order background at \|ρ\| = 1. (Measured: both reference engines confirm it from opposite ends on the one committed instance: one let the peak run to 8.77e10 °2θ at esd 0, the other kept it at 1.63° with an esd 188× its own value.) A hump substitutes for polynomial terms; it never adds to them (§`HUMP_TOO_NARROW` is the same lesson from the narrow end) |
| `RECIPE_CONVENTION_ASSUMED` | (info) Treat the split as measured. If your specimen's slit and detector heights differ, set `axial_sl` and `axial_hl` yourself. The `.instprm` sibling is `GSAS2_INSTPRM_CONVENTION_ASSUMED` |
| `RECIPE_PLAN_STAGED` | (info) Read the stage list as a change to what the recipe asked to refine. Staging here is **cumulative**, so the free set at the end is the recipe's and only the route differs. (Measured: a single cold step walked a monoclinic cell to a = 4231 Å on a real fixture.) |
| `RECIPE_DISPERSION_DECLINED` | (info) Read it as an approximation you are choosing. A PDF-beamline λ = 0.1665 Å is 74.5 keV, outside the table's 3-70 keV band, and f = f₀ is the correct limit there; extrapolating the table would be wrong. The result still carries `DISPERSION_NEGLECTED`, as any `dispersion=None` fit does |
| `RECIPE_FIT_RANGE_CHANNELS` | (info) Compare an Rwp against another engine's before checking this count against theirs. `value` is the count and the message gives the first and last 2θ. (Measured: on the committed fixtures this package's inclusive mask selects 3767 where GSAS-II's own `fit_profile.txt` shows it fitted 3768, keeping the first channel past the stated upper limit.) |
| `RECIPE_ZERO_WEIGHT_EXCLUDED` | (info) Assume the pattern's channel count is the fitted count. The excluded points are in `excluded_regions` |
| `RECIPE_BOUND_HONOURED` | (info) Read a `BOUND_HIT` on this path as a bug. PowderLine documents the 4-tuple's `min`/`max` as *not implemented in GSAS-II*; honouring it is the conservative reading and a **recorded difference** from the reference engine, not an accident |
| `RECIPE_SCHEMA_UNTESTED` | (warning) Trust a field whose meaning may have moved. It is read anyway because PowderLine's models allow extra fields on purpose, so a field that changed meaning is read with its old one |
| `RECIPE_NOTHING_REFINED` | (warning) Read the answer as a refinement. The plan has one stage that frees nothing, so the model is evaluated at its declared values: a simulation |
