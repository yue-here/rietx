# The indexing search and its result

This page gives `index_pattern`: what it takes and refuses, the three engines it runs, the presets and budgets that bound it, the `SearchSpecSpec` controls and a volume window from a formula, and the `IndexingResult` it returns, with each candidate's figures of merit, lattice symmetry, ambiguity partners, supercell checks, whole-profile test and confidence grade.

The peak list the search runs on, and the verdict on whether that list can be searched at all, are in [Peak lists for indexing](peaks.md).
What a consumer reads when it weighs the candidates itself, and how a candidate becomes a phase to refine, are in [Indexing evidence and the route to a phase](indexing-evidence.md).
The quadratic form the engines fit, the figures of merit and the lattice ambiguities are in [Indexing](../theory/indexing.md).

:::{admonition} Provisional
:class: warning
Indexing is still being measured against real data, so every name on this page may change in a 1.x release: `index_pattern`, the types in `rietx.schemas.indexing` and the helpers under `rietx.indexing`.
A change is announced in the release notes, and the data contracts a consumer parses do not move with it.
{ref}`provisional-by-declaration` gives the promise in full.
:::

## Running the search

<!-- api-doc: no-exec — a real search runs for up to two minutes -->
```python
import rietx as rx

data = rx.read_pattern("corundum.prn")
ins = rx.Instrument.bragg_brentano(radiation="CuKa")
peaks = rx.pick_peaks(data, ins)
result = rx.index_pattern(peaks, data=data, instrument=ins)
print(result)
```

| Argument | Default | Does |
|---|---|---|
| `peaks` | `None` | the `PeakList` to index; leave it out and pass `data` and `instrument` to have `pick_peaks` pick one |
| `data` | `None` | the pattern; passing it is what turns the whole-profile test on |
| `instrument` | `None` | needed with `data`, both to pick peaks and for the validation fits |
| `spec` | `None` | the search bounds, as the frozen `rietx.indexing.SearchSpec` that `SearchSpecSpec.to_spec` builds; `None` takes every default |
| `preset` | `None` | the preset that sets the whole-run ceiling; `None` resolves to `quick` |
| `engines` | `None` | which engines to run; `None` runs every registered one |
| `quality` | `None` | a `DataQualityReport` you already computed; `None` runs `assess_peak_list` |
| `shift_from_pairs` | `True` | measure the shift allowance from harmonic reflection pairs, when `quality` is not given |
| `validate` | `True` | run the whole-profile Pawley test when `data` and `instrument` are both given |
| `check_top` | `None` | how many of the top candidates get the expensive checks; `None` is three |
| `two_theta_limits` | `None` | the range the validation fits run over |
| `formula` | `None` | a chemical formula each candidate's implied Z is checked against ([A volume window from the formula](#a-volume-window-from-the-formula)) |
| `temperature` | `298.0` | the measurement temperature in K, for the formula's volume |
| `events` | `None` | an event stream, as `Refinement.fit` takes one |
| `cancel` | `None` | a `CancelToken`; a cancelled search returns what it has rather than raising |

`index_pattern` raises `ValueError` when it gets neither a peak list nor a `data` and `instrument` pair, for a preset it does not know, for a formula Hofmann's table cannot read (before any peak is picked), for an engine name the registry does not hold, and for a time-of-flight pattern.

A list that cannot be searched in any crystal system is not an error.
The answer comes back with no candidates, an empty `IndexingResult.engines_run`, and [`INDEX_DATA_INSUFFICIENT`](diagnostics-indexing.md#index_data_insufficient) from the quality report, before any budget is spent.
A list that can be searched but is short of the twenty lines the classical figures of merit need is searched over the systems it supports, ranked on the reduced panel, and capped ([Enough lines, and precise enough](peaks.md#enough-lines-and-precise-enough)).

The run goes in this order: the quality report, which may end it; a shift template adopted from the screen when it is safe to name ([The systematic shift](peaks.md#the-systematic-shift-and-the-window-it-opens)); the engines, one crystal system at a time; a second pass under the inlier rule when no lattice has two engines behind it; the declared prior cells; the merge, the ranking, the supercell checks and the lattice-symmetry screen; the whole-profile validation; the geometrical-ambiguity walk on what the clock leaves; and the confidence gate.

### Three engines, and why the default is all of them

Confidence here is engines agreeing, and the three registered engines fail in different ways, which is the point.

| Engine | How it searches | What defeats it |
|---|---|---|
| `dichotomy` | exhaustive branch-and-bound over boxes of the reciprocal metric | a domain too wide for its budget; it is the only engine whose silence, when it finishes a system, is evidence that no cell exists there |
| `trial_error` | assumes indices for a few base lines, solves the metric exactly, then checks every line | a wrong base line |
| `svd` | proposes metrics at random over a volume ladder and iterates the assignment and the solve until the indices stop changing; seeded by `SearchSpecSpec.seed` | a bad starting basin |

The set is a registry, so ask which engines this build has:

```python
import rietx as rx

caps = rx.capabilities()
engines = {engine.name: engine.description for engine in caps.indexing_engines}
assert set(engines) == {"dichotomy", "svd", "trial_error"}
```

Each row is an `EngineCapability`, quoted from the live registry ([Calling rietx from a program](programs.md#indexing)).

Naming a subset narrows what the answer can say.
Adding an engine raises the bar rather than lowering it, because a candidate is `high` only when every engine that ran found it.
A run of one engine carries [`INDEX_SINGLE_ENGINE`](diagnostics-indexing.md#index_single_engine) and grades every candidate `low`, since one finder is never agreement.

Only `dichotomy` makes an exhaustiveness claim, and it holds only where `IndexingResult.search_complete` is true for the system.
Read that field before concluding anything from a silence.

### Presets, budgets and the three states of a system

| Preset | Whole-run ceiling | Use it |
|---|---|---|
| `quick` | 120 s, covering search, probe and validation | by default: a first look, and every interactive call |
| `full` | none; only the per-slice budget bounds the search, and validation runs with no budget | for a rerun, when a `quick` run reported systems truncated or not reached and the answer may live there |

`Capabilities.search_presets` quotes the same rows with their measured typical times ([Calling rietx from a program](programs.md#indexing)).
`quick` narrows nothing: no engine, system or search box is dropped.
What a binding ceiling cuts is the trailing low-symmetry systems, and the run says so with [`INDEX_BUDGET_EXHAUSTED`](diagnostics-indexing.md#index_budget_exhausted).
A declared `SearchSpecSpec.total_budget_seconds` is never overridden, and the result then records `IndexingResult.preset` as `"custom"`.

There are two budgets, and they bound different things.
`SearchSpecSpec.budget_seconds` bounds one slice, one engine on one crystal system, and `SearchSpecSpec.total_budget_seconds` bounds the whole run.
The slices run system by system: every engine finishes one system before any engine starts the next, cubic first and triclinic last.
So a binding ceiling cuts trailing systems for every engine alike, and a completed system holds every engine's answer, which the agreement gate needs.

Under a ceiling, the search stops 15 % of it early when validation is going to run, so the validation fits are not starved.
The fits then run cheapest first, by the number of reflections each refines, and each may use whatever the clock still holds.
That order finishes the most fits before the ceiling.
`rietx.indexing.engines.estimate_ceiling` is the arithmetic for choosing a value before starting, and [`rietx index --ceiling`](cli.md#the-cost-ceiling) prints it.

After a run, every crystal system is in one of three states:

- in `IndexingResult.systems_searched` with `IndexingResult.search_complete` true: searched to exhaustion;
- in `systems_searched` with `search_complete` false: truncated, so a negative result there means nothing;
- absent from `systems_searched`: never reached.

A system counts as complete only when every engine that ran both entered it and exhausted its domain.
[`INDEX_SEARCH_INCOMPLETE`](diagnostics-indexing.md#index_search_incomplete) says which engine stopped where and why, and [`INDEX_SYSTEMS_NOT_COVERED`](diagnostics-indexing.md#index_systems_not_covered) names the systems never searched.

Measured on the SRM 676a corundum scan with every default (2026-10-22, Linux, `[dev]`), the run ran to its 120 s ceiling and entered four of the seven systems: cubic, hexagonal and trigonal completed, tetragonal was truncated, and the three lowest were never reached.

### The search specification

`SearchSpecSpec` is the whole control surface.
It is flat and complete, because the engines' agreement only means something when they were given identical bounds.
The same model is the GUI's search form and the project document's `ProjectDoc.indexing.search`, and [Indexing search settings](settings.md#indexing-search-settings) gives each field's help entry.

| Field | Default | Does |
|---|---|---|
| `SearchSpecSpec.systems` | `None`, all seven | the crystal systems to search; they always run from cubic to triclinic |
| `SearchSpecSpec.centrings` | `None`, every centring a system admits | Bravais centrings per system, as a dict from system to letters |
| `SearchSpecSpec.min_d_axis`, `SearchSpecSpec.max_d_axis` | 2 Å, 25 Å | the range of principal d-spacings, a bound on d(100) rather than on a; raising the top costs search volume |
| `SearchSpecSpec.min_volume` | 15 Å³ | the volume floor |
| `SearchSpecSpec.max_volume` | `None` | the volume ceiling, taken verbatim; `None` takes 1.5 times Smith's envelope for each system from the quality report, or 8000 Å³ where the report has none |
| `SearchSpecSpec.n_unindexed` | `None` | driven lines a cell may leave unexplained: `None` is two, with a retry under the inlier rule; `"inliers"` that rule from the start; an integer that count, with no retry |
| `SearchSpecSpec.n_search_lines` | 20 | how many lines drive the search, the strongest N |
| `SearchSpecSpec.k_sigma` | 3 | the matching window, in multiples of each line's σ with the shift allowance added in quadrature |
| `SearchSpecSpec.shift_allowance_deg` | 0 | a shift amplitude you measured, ° 2θ; 0 lets the run size the window itself |
| `SearchSpecSpec.shift_template` | `None` | `"constant"`, `"cos_theta"` or `"sin_2theta"`: refit each surviving candidate with this shift column |
| `SearchSpecSpec.budget_seconds` | 30 s | the budget of one engine on one system |
| `SearchSpecSpec.total_budget_seconds` | `None` | the whole-run ceiling; `None` leaves it to the preset |
| `SearchSpecSpec.preset` | `None` | the preset, passed to `index_pattern` as `preset=`; `None` resolves to `quick` |
| `SearchSpecSpec.max_candidates` | 12 | how many candidates the answer reports |
| `SearchSpecSpec.seed` | 0 | the seed of the `svd` engine and of the pair screen's null replicates |
| `SearchSpecSpec.prior_cells` | `None` | cells from a structural analogue, (a, b, c, α, β, γ) in Å and degrees |
| `SearchSpecSpec.prior_spacegroups` | `None` | space-group symbols from that analogue |

| System | Centrings it admits |
|---|---|
| cubic | P, I, F |
| hexagonal | P |
| trigonal | P, R |
| tetragonal | P, I |
| orthorhombic | P, C, I, F |
| monoclinic | P, C |
| triclinic | P |

`SearchSpecSpec.to_spec` builds the `SearchSpec` that `index_pattern` takes.
The two carry the same search fields, held equal by a test.
`SearchSpecSpec.preset` is the one field `to_spec` leaves out, because a preset is an argument of the run rather than a bound of the search.

```python
from rietx.schemas.indexing import SearchSpecSpec

controls = SearchSpecSpec(systems=["trigonal", "hexagonal"],
                          centrings={"trigonal": ["R"]},
                          max_volume=600.0, budget_seconds=60.0, preset="full")
spec = controls.to_spec()
assert spec.systems == ("trigonal", "hexagonal")
assert spec.centrings == {"trigonal": ("R",)}
assert spec.max_volume == 600.0
```

The model refuses rather than narrowing in silence.
It raises a `ValidationError` naming the live vocabulary for an unknown crystal system, centring, shift template, preset or space-group symbol, and for a centring the system does not admit.
An empty centring list is refused rather than skipping the system, because leaving the key out is how a system keeps its full set and dropping a system is `systems`' job.
A prior cell with an axis at or below zero, or an angle outside (0, 180)°, is refused too, as are a zero or negative budget, d-spacing or volume floor, and `n_search_lines` below 2.

`SearchSpecSpec.shift_allowance_deg` takes the shift's amplitude, `ShiftScreen.allowance_deg`, never the scatter `ShiftScreen.sigma_sys_deg`.
Left at 0, the run sizes the window itself, and an assumed window caps every candidate ([The systematic shift, and the window it opens](peaks.md#the-systematic-shift-and-the-window-it-opens)).
A window does not correct a cell; only a shift template does.

#### Driven lines and the inlier rule

A search is driven by the `n_search_lines` strongest usable lines, chosen from a low-angle pool twice that size, and every candidate is then scored against every usable line.
Leave `SearchSpecSpec.n_search_lines` alone: raising it is neither free nor safe.
Under a count, a cell must index all but that many of the driven lines, an absolute budget, so every foreign line admitted can refute the true cell rather than merely rank it lower.

The default first pass lets a cell leave two driven lines unindexed.
A run that ends with no lattice two engines agree on is searched again under the inlier rule, the acceptance RANSAC uses {cite}`fischler1981`: a cell is accepted when it indexes at least 60 % of the driven lines (and at least four more than the metric's degrees of freedom), the five strongest among them.
The retry adds candidates and never removes the first pass's, and [`INDEX_INLIER_RETRY`](diagnostics-indexing.md#index_inlier_retry) says the answer came from it.
`n_unindexed="inliers"` searches that way from the start, and an integer forbids the retry.
Only such a run retries, because the inlier rule changes the pool the panel ranks, and the ranking depends on that pool.
A list whose lines all carry one intensity, such as `PeakList.from_positions` without intensities, has no strongest five to anchor on and keeps the count of two.

Under every rule, what a cell leaves is reported rather than hidden: `CellCandidate.n_search_unindexed` counts the driven lines it left, and `CellCandidate.unindexed_two_theta` lists every usable line it left, the residue a second phase would explain.

#### Priors from a structural analogue

A prior steers the search and never gates it.
Each crystal system a prior names moves to the front of the queue, and a prior cell's metric seeds the `svd` engine's starting basin.
The cell is then checked against the peak list the engines' own way, and if it indexes the driven lines it joins the answer as finder `"prior"`: added to `CellCandidate.found_by` when an engine also found the lattice, and otherwise appended after the ranked list, never ranked among the engines' candidates.
`"prior"` never appears in `IndexingResult.engines_run`, so the agreement caveat grades a prior-only candidate down.

No system is dropped and no range changes, so a wrong prior costs time rather than truth.
A prior cell outside the declared axis range is reported as unusable rather than widening the box, and the check refutes a cell it would have to move more than 10 % in volume to fit.
[`INDEX_PRIOR_USED`](diagnostics-indexing.md#index_prior_used) records what was supplied and what it changed.
Two settings of one lattice, such as an acute and an obtuse monoclinic angle, come back as one candidate, because the merge compares reduced cells.

#### The controls a project stores

`IndexingControls` is the same surface one level up: everything a run is asked with that is not the data.
It is what `ProjectDoc.indexing` persists, so a run can be repeated from a stored setting rather than from a call site.

| Field | Default | Holds |
|---|---|---|
| `IndexingControls.search` | every default | the `SearchSpecSpec` |
| `IndexingControls.engines` | `None`, every registered engine | which engines to run; an unknown name raises `ValidationError` |
| `IndexingControls.validate_candidates` | `True` | whether to run the whole-profile test |
| `IndexingControls.check_top` | `None`, three | how many top candidates get the expensive checks, at least 1 |

`two_theta_limits` is deliberately not a field: the project document already owns the range.

### A volume window from the formula

A formula says roughly how much room one formula unit takes in a crystal.
`rietx.indexing.SearchSpec.from_formula` turns that into a volume window.
One formula unit's volume is the sum of Hofmann's average atomic volumes {cite}`hofmann2002`, from `rietx.crystallography.atomic_volume.formula_unit_volume`.
The window holds `z` formula units, widened to the bounds {{ VOLUME_RATIO_LOW }} to {{ VOLUME_RATIO_HIGH }} on the ratio of observed to estimated volume, outside which about 1 % of the structures Hofmann fitted lie.

```python
from rietx.crystallography.atomic_volume import formula_unit_volume
from rietx.indexing import SearchSpec

volume, esd = formula_unit_volume("C7H6O2")      # benzoic acid, at 298 K
assert (round(volume, 2), round(esd, 2)) == (150.35, 0.93)

spec = SearchSpec.from_formula("C7H6O2", z=(2, 8), max_d_axis=32.0)
assert round(spec.min_volume, 2) == 240.56       # 2 x 150.35 x 0.8
assert round(spec.max_volume, 2) == 1503.5       # 8 x 150.35 x 1.25
```

`z` counts formula units in the conventional cell: an integer, a `(min, max)` pair or `None`.
`None` sets only the floor of one formula unit and leaves the ceiling to the quality report's envelope, because a formula says nothing about how many units the cell holds.
The floor never drops below the 15 Å³ default.
Every other `SearchSpec` field passes through as a keyword.

`from_formula` raises `ValueError` when `min_volume` or `max_volume` is passed beside the formula, for a `z` that is not a whole number of at least 1 with its minimum no larger than its maximum, when the formula's ceiling falls below the floor, and for a formula or temperature `formula_unit_volume` refuses.

One crystal scatters about Hofmann's estimate by {{ VOLUME_SCATTER_PCT }} %, and the window is wider still, because a window that excludes the true cell makes the search return a wrong one.
The volumes were fitted to organic and metal-organic crystals, and an ionic compound comes out too large, so the floor can exclude its cell.

Passing `formula=` to `index_pattern` checks each candidate instead of narrowing the search.
A cell whose volume holds a fractional number of formula units carries [`INDEX_Z_NOT_INTEGER`](diagnostics-indexing.md#index_z_not_integer), a warning whose `value` is the implied Z.
It fires when the nearest whole number is more than {{ Z_INTEGER_TOLERANCE_PCT }} % away, twice one crystal's scatter, so it is silent above Z = {{ Z_CHECK_SILENT_ABOVE }}.
The candidate keeps its rank and its grade.
[Volume from a formula](../theory/indexing.md#volume-from-a-formula) gives the estimate.

## The result object

`IndexingResult` is a ranked list of hypotheses with the evidence behind each, and what the search covered.
It has no `cell` and no `best`: the only route to one cell is `IndexingResult.best_or_none`.

| Field | Holds |
|---|---|
| `IndexingResult.candidates` | the ranked `CellCandidate` list, at most `max_candidates` long |
| `IndexingResult.engines_run` | the engines that ran, the denominator of the agreement gate |
| `IndexingResult.systems_searched` | the systems any engine entered |
| `IndexingResult.search_complete` | per system, whether every engine that ran entered it and exhausted its domain |
| `IndexingResult.engine_stats` | per-engine counters, each key prefixed with the engine's name and a dot |
| `IndexingResult.fom_panel_disagrees` | whether the panel's members put different candidates first |
| `IndexingResult.quality` | the `DataQualityReport` the run used |
| `IndexingResult.validated` | whether a pattern was supplied and validation ran at all; it says nothing about any one candidate |
| `IndexingResult.n_usable_lines` | the usable lines the answer is about |
| `IndexingResult.wavelength` | the primary wavelength, Å |
| `IndexingResult.preset` | the preset that set the ceiling, `"custom"` when your own `total_budget_seconds` did, or `None` on a result recorded before presets |
| `IndexingResult.provenance` | the package version and time, with every search setting in `Provenance.notes` |
| `IndexingResult.thresholds_version` | which set of gates and vocabularies produced the grades, `rietx.schemas.indexing.INDEXING_THRESHOLDS_VERSION` at the time |
| `IndexingResult.diagnostics` | the run-level findings |

`IndexingResult.best_or_none` returns a candidate only when exactly one is `high` and it has no ambiguity partners.
Everything else returns `None`: nothing found, two cells that both explain the pattern, a search with no validation, an assumed tolerance.
[`INDEX_ABSTAINED`](diagnostics-indexing.md#index_abstained) then names the top candidate's caveats, and [`INDEX_MULTIPLE_SOLUTIONS`](diagnostics-indexing.md#index_multiple_solutions) fires when more than one candidate is `high`.

`IndexingResult.diagnostics` says things about the run, such as a truncated budget or systems not covered, while a statement about one cell lives on that candidate, in `CellCandidate.diagnostics` and `CellCandidate.confidence_caveats`.

Printing a result gives the run line, one block per candidate with its grade and the caveats holding it down, the verdict, and every diagnostic.
`rietx index` prints exactly that ([`rietx index`](cli.md#rietx-index)).

### One candidate

| Field | Holds |
|---|---|
| `CellCandidate.cell`, `CellCandidate.cell_esd` | a, b, c in Å and α, β, γ in degrees, with esds, in the conventional setting |
| `CellCandidate.a`, `CellCandidate.b`, `CellCandidate.c`, `CellCandidate.alpha`, `CellCandidate.beta`, `CellCandidate.gamma` | the members of `cell` by name |
| `CellCandidate.engine_cell`, `CellCandidate.change_of_basis` | the cell in the setting the engine found, and the integer matrix M taking it to `cell`; `None` on a candidate built some other way |
| `CellCandidate.system`, `CellCandidate.centring` | the crystal system, and the Bravais centring letter |
| `CellCandidate.lattice_group` | the absence-free group of the lattice: its holohedry and centring |
| `CellCandidate.volume`, `CellCandidate.volume_esd` | the cell volume and its esd, Å³ |
| `CellCandidate.af` | the six quadratic-form parameters A to F actually fitted {eq}`idx-af`, in the reported setting |
| `CellCandidate.n_indexed`, `CellCandidate.n_lines` | the usable lines the engine's assignment indexes, of the usable lines it was offered |
| `CellCandidate.n_search_unindexed` | driven lines this cell leaves unindexed; `None` when not computed |
| `CellCandidate.unindexed_two_theta` | 2θ of every usable line this cell leaves unindexed, ascending; `None` when not computed |
| `CellCandidate.chi2_red` | reduced χ² of the metric fit |
| `CellCandidate.shift_template`, `CellCandidate.shift_coefficient`, `CellCandidate.shift_esd` | the shift column refitted with the cell, its amplitude in ° 2θ and its esd; `None`, 0 and 0 when none was |
| `CellCandidate.fom` | the figure-of-merit panel, one `FigureOfMerit` per member |
| `CellCandidate.found_by` | the engines that reached this lattice, sorted, with `"prior"` for a checked prior |
| `CellCandidate.ambiguity` | the lattices this data cannot tell from this one, as `AmbiguityPartner` entries |
| `CellCandidate.supercell_checks` | one `SupercellCheck` per reported candidate this one is a superlattice of; `[]` when there is none, `None` when never asked |
| `CellCandidate.bravais` | the two opinions on the lattice symmetry, a `BravaisOpinion`, or `None` when gemmi or spglib refused the cell |
| `CellCandidate.lebail` | the whole-profile test, a `LeBailValidation`, or `None` when it did not run on this candidate |
| `CellCandidate.confidence` | `"high"`, `"medium"` or `"low"` |
| `CellCandidate.confidence_caveats` | every reason it is not `"high"`, from a closed vocabulary |
| `CellCandidate.diagnostics` | the findings about this candidate |

`CellCandidate.to_cell` returns `cell` as a `Cell` with every parameter fixed, and the esds stay on `cell_esd`, since a `Parameter` carries none.
`CellCandidate.fom_value` reads one panel member by name and returns `None` rather than raising, because which members exist depends on what the list could support.

A candidate is reported in its conventional setting, whatever setting the engine reached.
Only a monoclinic lattice has one to choose: b is the unique axis, a and c are the shortest translations normal to it, and β is obtuse.
An engine may arrive at β = 81.78° for a lattice whose conventional β is 98.22°, or at any of a C cell's settings, and `af`, `cell` and `cell_esd` are re-set through one exact map.
The engine's own cell stays in `engine_cell`, and `change_of_basis` is M with (reported axes) = M · (engine axes), the identity where nothing moved.
Two cells are one lattice when `rietx.indexing.same_lattice` says so on their `af`, never when the six numbers match.

`CellCandidate.lattice_group` is the absence-free group, never a plausible space group, and the distinction is load-bearing.
A group carrying reflection conditions would hide exactly the reflections whose absence is not yet established, and hiding them is how an oversized cell passes.

### The figure-of-merit panel

The panel ranks candidates and does not score them.
A margin is comparable within one member and not across them, so the members vote by a Borda count instead of being summed, and each carries what it is blind to.

| Field | Holds |
|---|---|
| `FigureOfMerit.name` | which member this is |
| `FigureOfMerit.value` | its value |
| `FigureOfMerit.n_lines`, `FigureOfMerit.n_possible` | the observed lines it read, and the lines the lattice allows over them |
| `FigureOfMerit.k_sigma` | the matching window it was computed at, in multiples of each line's σ |
| `FigureOfMerit.mean_discrepancy` | the mean \|Δ\| of the matched lines in the member's own units, Å⁻² for M₂₀ and ° for $F_N$; −1 when nothing matched, which is not zero |
| `FigureOfMerit.blind_spot` | what this member cannot see, as a sentence |

On a list of 20 or more usable lines the panel has seven members.

| Member | What it asks | Lines it reads |
|---|---|---|
| `m20` | de Wolff's M₂₀ {eq}`idx-m20` | the 20 lowest-angle lines |
| `f_n` | Smith and Snyder's $F_N$ {eq}`idx-fn`, scored at N = 20 | the 20 lowest-angle lines |
| `indexed_fraction` | the share of observed lines the lattice indexes | every usable line |
| `indexed_intensity_fraction` | the same share, weighted by intensity | every usable line |
| `predicted_seen_fraction` | the share of the lattice's predicted lines that are observed | every usable line |
| `m_rev` | Oishi-Tomiyasu's reversed figure {cite}`oishitomiyasu2013` | the 20 lowest-angle lines |
| `m_sym` | the product of the forward and reversed figures over one window | the 20 lowest-angle lines |

Below 20 usable lines `m20` and `f_n` are left out of every candidate's panel alike, and `DataQualityReport.fom_undefined` names each with its reason.
Coverage is scored in both directions, and that is what the reversed members are for.
Share-of-observed alone puts a supercell above the truth, since a supercell indexes every observed line, while the reversed direction asks how much of what the cell predicts was actually seen.
A candidate refitted with a shift column is scored on its own corrected positions, and every coverage member matches in the window the search matched with.

`FigureOfMerit.blind_spot` is a field because every published figure of merit has a failure mode, and a value read without it is one step from a confident wrong answer.
Where the search let lines go unindexed, it also says how many lines the mean discrepancy was trimmed by.

The ranking puts corroboration first: every candidate at least two engines found ranks above every candidate fewer found, and the Borda count orders each group.
`IndexingResult.fom_panel_disagrees` is true when the members' first choices differ, which means at least one blind spot is active, and the gate reads it ([The confidence gate](#the-confidence-gate)).
[Figures of merit, in both directions](../theory/indexing.md#figures-of-merit-in-both-directions) gives the formulas.

### The lattice symmetry, and its ambiguities

`CellCandidate.bravais` is a `BravaisOpinion`: two independent readings of the same Niggli-reduced cell, each over a tolerance sweep.
gemmi's tolerance is an obliquity in degrees (0.5°, 1°, 2° and 3°) and spglib's a distance in Å (1, 3 and 10 times the cell's own esd), so a disagreement between them is information about the cell rather than a bug in either.

| Field | Holds |
|---|---|
| `BravaisOpinion.system` | the symmetry that survives the whole sweep: the lower of the two methods' answers at their tightest tolerance |
| `BravaisOpinion.system_loosest` | the highest symmetry either method reported at any tolerance |
| `BravaisOpinion.system_gemmi`, `BravaisOpinion.system_spglib` | each method's answer at its tightest tolerance |
| `BravaisOpinion.ambiguous` | whether `system_loosest` is higher than `system`, a symmetry that appears only at a loose tolerance |
| `BravaisOpinion.methods_disagree` | whether the two methods' tightest answers differ |
| `BravaisOpinion.reduced_cell` | the Niggli-reduced, primitive cell the symbols refer to |

Either flag raises [`INDEX_BRAVAIS_AMBIGUOUS`](diagnostics-indexing.md#index_bravais_ambiguous) on the candidate.

A powder pattern carries only the length of a reciprocal vector, so distinct lattices can produce the same line positions {eq}`idx-hnf`.
Those are reported, never resolved, as `AmbiguityPartner` entries.
The search walks the derivative lattices of index 2 to 4.
A partner counts when it indexes at least as many observed lines with a mean discrepancy no more than 1.5 times worse, and no extra line it predicts inside the measured range is missing from the pattern.

| Field | Holds |
|---|---|
| `AmbiguityPartner.cell` | the partner lattice, a superlattice of this candidate's cell |
| `AmbiguityPartner.system` | always `"triclinic"`, the system its lines are predicted in |
| `AmbiguityPartner.volume` | its volume, Å³ |
| `AmbiguityPartner.transformation` | the integer matrix from this candidate's basis to the partner's |
| `AmbiguityPartner.index` | \|det\| of that matrix, 2 to 4 |
| `AmbiguityPartner.discriminating_reflections` | up to six hkl, lowest angle first, whose positions would break the tie |
| `AmbiguityPartner.discriminating_two_theta` | where each would have to appear or be absent, ° 2θ |

A partner that survived has no missing extra line inside the measured range, so its discriminating reflections lie outside it, up to 1.5 times the top of the range or below its bottom.
They say where to measure again, which makes the ambiguity something to act on.
A partner raises [`INDEX_GEOMETRIC_AMBIGUITY`](diagnostics-indexing.md#index_geometric_ambiguity) on the candidate.
The walk finds only larger cells, so a smaller rival with the same line positions is not reported.

The walk is expensive and runs only on the checked candidates, after validation, on whatever the clock leaves.
A candidate the walk never reached has an empty `CellCandidate.ambiguity`, and the gate reads that as a question not asked ([The confidence gate](#the-confidence-gate)).

### A supercell and the cell inside it

A cell twice as long along one axis explains every line the smaller cell explains, and predicts more, and the panel can rank it first: on the round-robin brucite pattern it ranked a supercell above the certified cell.
So every pair of reported candidates in which one is a superlattice of the other, holding 2 to 4 of its primitive cells, is asked whether the pattern shows the extra lines the larger cell needs.

Missing lines alone cannot answer that, since a correct cell's symmetry can extinguish lines.
But an extinction only ever acts on a line that sits on a mirror plane or a rotation axis of the lattice, so only the extra lines lying on neither are counted.
A line is seen when it falls inside an observed line's matching window, and the count is compared with chance: the share of the measured range those windows cover, which is how often a position with no line at all would still read as seen {eq}`idx-supercell-chance`.

The verdict is one of three, at a significance level of 0.01:

- refuted: the extras are seen no more often than chance, and the test had the power to say otherwise. The larger cell moves to directly below the lowest-ranked smaller cell that refutes it, stays in the list, and carries the `supercell_refuted` caveat and [`INDEX_SUPERCELL_REFUTED`](diagnostics-indexing.md#index_supercell_refuted).
- supported: the extras seen on observed lines the smaller cell cannot index are more than chance gives. The larger cell moves to directly above the highest-ranked smaller cell that supports it, unless another check refutes it.
- undecided: even seeing every extra could not have reached the level, or the extras are seen beyond chance only on lines the smaller cell already explains, as on a pseudo-symmetric description of the smaller cell's own lattice. Nothing moves.

Nothing else in the order changes, and a refuted cell is never moved up.
*Refuted* means seen no more often than chance, since a non-significant test does not establish the null, so extras seen above chance but not significantly leave the verdict `"undecided"`.
The check needs only the peak list, so it runs on a bare list too.

Which pairs are asked is a question about the lines, not the volumes (indexing thresholds 1.12).
A cell is asked as the larger one whenever every observed line the smaller cell indexes it indexes too, and its own line set is the denser.
That reaches a sublattice pair, and it reaches pairs that are not: a cubic I cell at √2 the edge of a cubic F truth, whose primitive volume is 5.66 times the truth's, and a trigonal description with the truth's own volume, which outranked it on a synthetic silicon pattern.
`SupercellCheck.relation` says which kind of pair it was.
The extras are counted at the measured resolution, one FWHM, after the common shift the cell's own matches imply, never in the window the search matched with.

| Field | Holds |
|---|---|
| `SupercellCheck.parent_cell`, `SupercellCheck.parent_system`, `SupercellCheck.parent_centring` | the smaller candidate this cell contains |
| `SupercellCheck.index` | how many of the parent's primitive cells one of this cell's holds; 0 when the parent is not a sublattice |
| `SupercellCheck.relation` | `"sublattice"`, or `"containment"` when the smaller cell only indexes a subset of this one's lines |
| `SupercellCheck.n_extra`, `SupercellCheck.n_seen` | the extra lines in range no extinction could remove, and how many sit on an observed line |
| `SupercellCheck.n_seen_unexplained` | of those seen, the ones on an observed line the parent cannot index; `None` in a record from before thresholds version 1.7 |
| `SupercellCheck.p0` | the chance that a position with no line reads as seen |
| `SupercellCheck.p_value` | the binomial chance of seeing at least `n_seen` of `n_extra`, had the extra lines not existed |
| `SupercellCheck.verdict` | `"refuted"`, `"supported"` or `"undecided"` |
| `SupercellCheck.absent_two_theta` | where the extras nothing was seen at would be, on the pattern's own 2θ axis, lowest first and at most six |

On the SRM 676a corundum scan all three engines find the certified cell's c/2 subcell, which leaves 10 of the usable lines unexplained, and corroboration ranks it above the certified cell, which fewer engines find.
The certified cell's 18 extras over the subcell are seen 8 times, all on lines the subcell cannot index, where chance gives 2.7, so the check is `supported` and the certified cell moves to first.

A real superstructure whose extra lines are too weak to pick is what this check cannot see.
Before discarding a refuted cell whose chemistry makes it likely, look at the pattern at `SupercellCheck.absent_two_theta`.

### The whole-profile test

Four of the panel's members read only the first twenty lines, and none of the seven sees intensity.
A Pawley fit against the whole pattern sees three things the panel cannot: lines beyond the twentieth, reflections predicted where there is no intensity, and impurity content.
The middle one is the classic doubled-cell false positive, which is why validation is part of the default run.
`CellCandidate.lebail` is that test, as a `LeBailValidation`.

| Field | Holds |
|---|---|
| `LeBailValidation.rwp`, `LeBailValidation.gof` | the fit's agreement; both infinite when the fit raised |
| `LeBailValidation.space_group` | the absence-free lattice group the fit used |
| `LeBailValidation.n_reflections` | the primary line's reflections in the fitted range |
| `LeBailValidation.predicted_but_absent` | lines the lattice predicts where the pattern has nothing above the picker's background envelope at the measured width |
| `LeBailValidation.predicted_but_absent_uncancellable` | of those, the lines no space group of the lattice could extinguish |
| `LeBailValidation.predicted_but_absent_uncancellable_in_window` | of those, the lines inside the first twenty observed lines; the caveat reads this one |
| `LeBailValidation.n_lines_screened` | the lines the screen asked about, merged at the resolution; the share `predicted_but_absent` is of |
| `LeBailValidation.absent_source` | `"line_screen"`, or `"fitted_background"` when no peak list was supplied |
| `LeBailValidation.unmatched_observed` | observed peaks with no calculated reflection nearby, as the fit report's Layer 0 counts them |
| `LeBailValidation.predicted_but_absent_two_theta`, `LeBailValidation.unmatched_observed_two_theta` | where each of those is, ° 2θ |
| `LeBailValidation.status` | the fit's status; `"failed"` when the fit raised, which is evidence about the cell and not a crash |
| `LeBailValidation.n_stages` | the stages the fit ran, of the validation plan's four |
| `LeBailValidation.diagnostics` | findings from the fit; [`INDEX_VALIDATION_FAILED`](diagnostics-indexing.md#index_validation_failed) when it raised |
| `LeBailValidation.mode` | the decomposition the fit ran: `"pawley"` since 1.11, `"lebail"` on a record written before it |

The fit holds the cell.
The candidate is the hypothesis under test, and letting it walk would validate a different cell from the one reported.
It frees the background, then exactly one peak-position parameter chosen from the candidate's own shift template (the zero shift by default, and always on a geometry other than Bragg-Brentano), then `W`, then `U`, `V`, `X` and `Y` together.
When the declared instrument's widths disagree with the picked lines', `W` starts from the lines' median FWHM.
`freeze_profile=True` drops the two width stages and keeps the profile at the peak list's measured width, shared by every candidate, so a wrong cell cannot broaden a neighbour to cover a line it does not explain.
The fit is single-phase, since a candidate is one lattice.
The fit is Pawley, and the type keeps its Le Bail name.
One Le Bail pass re-extracts the intensities only between solves, and on the true cells of nine real patterns it left a width on its lower bound for corundum and zircon and up to four times as many observed lines unmatched.
A Pawley fit refines the intensities in the same solve.

The test runs on the checked candidates only: the top `check_top`, plus every candidate every engine found, since those are the only ones the gate could promote.
A candidate outside that set, or one whose fit the clock stopped, keeps `lebail = None`.

The absent count is not this fit's.
A cell that needs intensity under many reflections can buy it from its own background: on a laboratory magnetite pattern the wrong primitive description drove its co-refined background below zero and read nothing absent of 163.
So the count is a line screen's, computed from inputs the candidate cannot change: the peak list's positions, widths and shapes, the picker's background envelope, and the package's own overlap rule.
A predicted line is absent when it is resolved from every picked line, the peak-list model is quiet there, and nothing stands above the envelope at the measured width.

`LeBailValidation.rwp` is not a panel member.
It costs a refinement, so it is computed for a shortlist rather than for every candidate, and reading it as a rank would bring back the blind spot it exists to close.
A converged fit of a cell that predicts every reflection of another cell fits at least as well as that cell, so `rwp` separates a wrong metric. It cannot separate an oversized cell, or a primitive cell standing in for a centred one.
On a laboratory magnetite pattern the wrong primitive description reads 0.174 against the true cell's 0.180.
Read `predicted_but_absent` as "this cell predicts lines the pattern lacks", never as "this cell is too big".
It counts against the lattice group, so a space-group extinction (a glide plane, a screw axis) shows in the count on a correct cell, and the extinction screen afterwards separates the two ([The extinction symbol](extinction.md)).
The caveat of the same name reads only the absences no extinction could cancel, inside the first twenty lines, and it caps rather than refutes: a correct cell's weak reflections below detection read absent too, over the whole range, so the count keeps `high` out of reach and the supercell check is what refutes.
A nonzero count raises [`INDEX_PREDICTED_BUT_ABSENT`](diagnostics-indexing.md#index_predicted_but_absent), and unmatched observed lines raise [`INDEX_IMPURITY_LINES`](diagnostics-indexing.md#index_impurity_lines).

### The confidence gate

`CellCandidate.confidence` is `high`, `medium` or `low`, written by one rule:

- `low` when fewer than two finders stand behind the candidate, or when any refuting caveat applies;
- `high` when every engine that ran found it and no caveat applies at all;
- `medium` otherwise: at least two finders, and only capping caveats.

Every reason a candidate falls short is a member of a closed vocabulary in `CellCandidate.confidence_caveats`.
Six of the fourteen refute the candidate, each being evidence against the cell or evidence that the data cannot choose.
The other eight cap it.
The count of caveats decides nothing.

| Caveat | Written when | Effect |
|---|---|---|
| `geometric_ambiguity` | the candidate has an ambiguity partner, or the ambiguity walk never reached it | refutes |
| `fom_panel_disagrees` | the panel's members put different candidates first; written on every candidate of the run | refutes |
| `indexed_fraction_low` | the intensity share the cell explains (`indexed_intensity_fraction`, falling back to the `indexed_fraction` line count where there is none) is below 0.9, or missing | refutes |
| `volume_unphysical` | the volume is below 15 Å³, or above 1.5 times Smith's envelope for its system | refutes |
| `validation_failed` | the validation fit's status is `"failed"` or `"diverged"` | refutes |
| `supercell_refuted` | a `SupercellCheck` on this candidate reads `"refuted"` | refutes |
| `indexed_lines_low` | the intensity share passes 0.9 but the `indexed_fraction` line count is below 0.9, as a sub-cell missing a superstructure would be | caps |
| `predicted_but_absent` | the line screen found lines this lattice predicts, that no extinction could remove, inside the first twenty lines, where the pattern has nothing | caps |
| `engines_disagree` | some engine that ran did not find this lattice | caps |
| `not_validated` | this candidate has no validation fit behind it | caps |
| `search_incomplete` | the candidate's own crystal system was not searched to completion | caps |
| `shift_allowance_assumed` | the matching window was widened by an assumed allowance | caps |
| `fom_panel_reduced` | the list is too short for `m20` and `f_n` | caps |
| `bravais_ambiguous` | `BravaisOpinion.ambiguous` or `BravaisOpinion.methods_disagree`, or no opinion could be formed | caps |

A candidate the ambiguity walk never reached reads `geometric_ambiguity` with an empty `CellCandidate.ambiguity`.
Not enumerated is not the same as none found, and the gate will not read an unasked question as a clean answer.
On a run whose clock ran out before the walk, every candidate carries this caveat and grades `low`.

`volume_unphysical` uses the same 1.5 times the envelope the search prunes at, so it fires only on a cell a declared `max_volume` let past it.
It raises [`INDEX_VOLUME_UNPHYSICAL`](diagnostics-indexing.md#index_volume_unphysical).

`not_validated` and `validation_failed` are separate on purpose: the absence of a test and a failed test are different statements, and only the second is evidence about the cell.
`not_validated` has two causes, and they are not the same news.
Either no pattern was supplied, so no candidate could be validated, and `IndexingResult.validated` is false with [`INDEX_NOT_VALIDATED`](diagnostics-indexing.md#index_not_validated) on the run.
Or a pattern was supplied and this candidate's fit did not run, because it was outside the checked set or the ceiling expired partway down it, which `INDEX_BUDGET_EXHAUSTED` counts.
So `IndexingResult.validated` true does not mean any one candidate was validated: on the bundled fluorapatite pattern a default run (the same day and build) reports it true while none of its twelve candidates carries a fit.

`shift_allowance_assumed` is why `high` is out of reach on real data with no measured shift: a cell found inside a widened window has absorbed the shift.
Reference positions handed to `assess_peak_list`, a shift the pair screen measured, or a declared `SearchSpecSpec.shift_allowance_deg` clears it.

Never take `candidates[0]` because it is ranked first.
The ranking orders the hypotheses and the gate judges them, which are different questions.
The order leads with corroboration and moves a supercell by its checks, which is closer to the gate's reading than a panel ranking alone, and still not it.

On the default corundum run above, the certified trigonal R lattice comes back first, found by two of the three engines, with a converged Pawley fit.
It grades `low`, so `best_or_none` returns `None`.
`LeBailValidation.predicted_but_absent` counts the c-glide's reflections, the shape a space-group extinction takes when read against a lattice group that does not know about it; none of them is a line no space group could extinguish, so the caveat is silent, and the extinction screen ([The extinction symbol](extinction.md)) is what names the glide.
`geometric_ambiguity` is there on every candidate because the ceiling stopped the run before the ambiguity walk, and `fom_panel_disagrees` because the panel's members split.
None of the caveats says the cell is wrong; they say what has not been established, which is the difference between this answer and a confident one.
