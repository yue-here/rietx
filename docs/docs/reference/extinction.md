# The extinction symbol

This page gives `determine_extinction_symbol`: what it takes, runs and refuses, the `ExtinctionScreen` it returns with one `ExtinctionCandidate` per extinction class, when `ExtinctionScreen.best_or_none` answers, which forbidden positions count as evidence, and the `ExtinctionPrior` that declares what the chemistry already rules out.

Once a lattice is established, the next question is which reflections are systematically absent.
Only systematic absences reach a powder pattern, so every space group sharing an absence set gives an identical pattern, and the screen answers with a class of space groups rather than one.
The lattice it screens comes from [The indexing search and its result](indexing.md), and the peak list that can seed its widths from [Peak lists for indexing](peaks.md).
How a candidate becomes the phase the screen fits is in [Indexing evidence and the route to a phase](indexing-evidence.md#from-a-candidate-to-a-phase).

:::{admonition} Provisional
:class: warning
Indexing is still being measured against real data, so every name on this page may change in a 1.x release: `determine_extinction_symbol`, the types in `rietx.schemas.indexing` and the helpers under `rietx.indexing.extinction`.
A change is announced in the release notes, and the data contracts a consumer parses do not move with it.
{ref}`provisional-by-declaration` gives the promise in full.
:::

## Running the screen

<!-- api-doc: no-exec — it runs one Le Bail fit per extinction class -->
```python
import rietx as rx

screen = rx.determine_extinction_symbol(data, candidate, ins,
                                        two_theta_limits=(15.0, 90.0))
klass = screen.best_or_none()
if klass is not None:
    print(klass.symbol, klass.space_groups)
```

Screening a freshly indexed candidate takes the candidate, the pattern and the peaks it came from in one call.
`IndexingResult.candidates` is the ranked list to choose from:

<!-- api-doc: no-exec — it runs an indexing search and then the screen -->
```python
idx = rx.index_pattern(peaks, data=data, instrument=ins)
screen = rx.determine_extinction_symbol(data, idx.candidates[0], ins, peaks=peaks)
```

| Argument | Default | Does |
|---|---|---|
| `data` | | the `PatternData`, on a 2θ axis |
| `candidate` | | the `CellCandidate` under test; its cell, system, centring and lattice group are used as given |
| `instrument` | | the `Instrument`; the shared profile fit starts from it |
| `peaks` | `None` | a `PeakList`; when the declared Gaussian width disagrees with the list's median FWHM, `W` is seeded from it before the profile fit |
| `two_theta_limits` | `None`, the whole pattern | the range the classes are enumerated over and judged in |
| `k_sigma` | 3.0 (`rietx.indexing.workflow.ABSENT_SIGMA`) | the detection threshold of the absence test, in σ of the intensity integrated over a window of ±½ FWHM |
| `max_classes` | `None` | fit at most this many classes, fewest absences first; a value under 1 still fits one |
| `refine_cell` | `False` | free the cell inside the shared profile fit, so every class is screened at the refined cell |
| `restrict` | `None` | an `ExtinctionPrior`, or its dict, that filters each class's members ([Declaring what the chemistry rules out](#declaring-what-the-chemistry-rules-out)) |
| `cancel` | `None` | a cancel token, read before each class's fit |

Every argument after `instrument` is keyword-only.
Two things raise before anything is fitted: a pattern whose axis is not 2θ, since every step is a Le Bail fit, and a `restrict` that does not validate as an `ExtinctionPrior`.
A prior declaring none of its three facts is no prior, and the screen records `None`.

Two failures come back as an answer instead of an exception, because every class would inherit them.
When the shared profile fit or the reference fit raises, or the lattice group predicts no reflection in the measured range, the screen returns with `status="failed"`, no candidates, and [`EXTINCTION_SCREEN_FAILED`](diagnostics-indexing.md#extinction_screen_failed) naming the cause.
The `cancel` token is not handed to the profile fit; it is read between class fits, and a cancelled screen returns with `status="cancelled"` and the classes it never reached marked as not screened.

### What the screen runs

Four steps, each on the same pattern and range:

1. One shared profile fit of the absence-free lattice group, as the whole-profile test runs it ([The whole-profile test](indexing.md#the-whole-profile-test)): the background, one peak-position parameter, then `W`, then `U`, `V`, `X` and `Y`.
   Every class is then fitted with that instrument frozen, so no class can make up for a missing reflection with a wider neighbour.
2. The reference fit: the absence-free class under the same one-stage protocol as every other class, so all the χ² values compare.
3. One Le Bail fit per class, fewest absences first, freeing the background and every declared hump and nothing else.
4. The absence test at each class's testable forbidden positions, read against that class's own calculated pattern: a position carrying intensity the class cannot account for refutes it, with the reflection named.

Each class is scored against the reference by ΔBIC {cite}`schwarz1978` and by Hamilton's ratio test {cite}`hamilton1965`, with the class's testable absences as the parameters removed.
The ranking is a nested comparison and not lowest Rwp, because a class with fewer absences has more reflections and always fits at least as well.
[Which parameter to free next](../theory/estimation.md#which-parameter-to-free-next) derives both; the screen takes N as the fitted channel count, `ExtinctionScreen.n_points`.

The candidate's `CellCandidate.system` is taken as given rather than screened again.
When the Bravais screen reported an ambiguity that field is the conservative reading, and classes enumerated in a higher symmetry would be classes the lattice may not have.

### Which classes are enumerated

The classes are derived, never transcribed.
Every space-group setting whose lattice matches the candidate's is enumerated, its absences are computed over the reflections in range, and the settings are grouped by identical absence sets.
Four rules decide which settings take part:

- A hexagonal lattice carries both the hexagonal and the trigonal groups, since the trigonal ones own classes (`P 3 c 1`, `P 31 c`) the hexagonal ones do not; every other system is itself.
- A monoclinic cell's unique axis is read off the cell, the angle furthest from 90°, and `b` when all three are 90°.
- An R lattice is screened in hexagonal axes, so the rhombohedral-axes settings are left out.
- With the axes fixed by indexing, two settings of one group are two hypotheses about this cell, and both are enumerated: `P n m a` and `P m n b` are different classes here.

Two classes differing only outside the fitted range are one class here, which is why `ExtinctionScreen.two_theta_range` is part of the answer rather than a setting.
Each class's representative, the member whose reflections are generated, is the one with the largest Laue group, so the absence-free class's representative is the lattice group itself.

### The cell it is screened at

With `refine_cell=False` the cell is held at the candidate's, so it has to be good.
A cell off by a few parts in 10⁴ leaves a tan θ position error that the shared fit's one shift cannot absorb, and a line the true class forbids then shows intensity at its position.
On the IUCr round-robin SRM 676a corundum (`tests/data/qarr/corundum.prn`), the certified cell gives `R - c -` and the same cell scaled by 1.0012 gives `R - - -`, whose members exclude `R -3 c`.
Refine the cell by Le Bail first and screen that, or pass `refine_cell=True`, which frees the cell after the shift and before the widths; `ExtinctionScreen.cell` is then the refined cell, and the classes still differ only in their reflection sets.

### A container halo

A capillary's amorphous halo is about 1° wide and can sit on a forbidden position, and the screen's background cannot take it: a P-spline is stiff by design.
An undeclared halo there reads as intensity the class forbids, and refutes it.
Declare it as a `HumpComponent` in `Instrument.extra_components` ([How to add a hump to the background](../guides/hump.md)) and fit it in the Le Bail pre-fit.
The screen refits every declared hump per class, alongside the background, with its width floored at {{ HUMP_MIN_WIDTH_MULT }} instrument widths at its position (`rietx.strategy.staged.HUMP_MIN_WIDTH_MULT`), so a hump cannot narrow onto a forbidden line and explain a real violation away.
A declared peak is not background and stays held.

## The screen

`ExtinctionScreen` has no symbol and no space group of its own, only a ranked list and `ExtinctionScreen.best_or_none`.
Even that returns a class, which lists its space groups, so the type cannot express "the space group is P2₁/c" where the powder can only say "the extinction symbol is `P 1 21/c 1`".

| Field | Holds |
|---|---|
| `ExtinctionScreen.candidates` | the `ExtinctionCandidate` list, ranked as below |
| `ExtinctionScreen.lattice_group` | the absence-free group every class is compared against |
| `ExtinctionScreen.cell` | the cell screened: the candidate's, or the refined one under `refine_cell=True` |
| `ExtinctionScreen.system`, `ExtinctionScreen.centring` | the candidate's crystal system and centring |
| `ExtinctionScreen.wavelength` | the primary emission line's wavelength, Å |
| `ExtinctionScreen.two_theta_range` | the fitted channels' first and last 2θ, which is part of the answer |
| `ExtinctionScreen.n_classes` | classes enumerated |
| `ExtinctionScreen.n_screened` | classes whose Le Bail fit ran |
| `ExtinctionScreen.reference_rwp`, `ExtinctionScreen.reference_chi2` | the absence-free class's own fit, the reference model; χ² is the raw sum Σw·Δ², not divided by N − P |
| `ExtinctionScreen.reference_lines` | distinct lines the lattice group predicts in range |
| `ExtinctionScreen.n_points` | channels in the fitted range, the N of every ΔBIC |
| `ExtinctionScreen.profile_rwp` | the shared profile fit every class inherits its instrument from |
| `ExtinctionScreen.prior` | the declared `ExtinctionPrior`, or `None` |
| `ExtinctionScreen.z` | the formula units per cell the member filter used, or `None` |
| `ExtinctionScreen.z_from_density` | the Z the declared density gives on `cell`, not rounded, or `None` |
| `ExtinctionScreen.status` | `"converged"`, `"failed"` (no class could be screened) or `"cancelled"` |
| `ExtinctionScreen.thresholds_version` | the indexing thresholds version that produced the ranking |
| `ExtinctionScreen.diagnostics` | findings about the answer |

The ranking puts refuted classes last and classes never fitted after the fitted ones, then orders by `ExtinctionCandidate.delta_bic`, ties going to fewer absences: an absence you cannot see is not one you may claim.

The screen's diagnostics say what the answer is and why it may not be one.
[`EXTINCTION_GROUPS_NOT_SEPARABLE`](diagnostics-indexing.md#extinction_groups_not_separable) fires whenever the leading class holds more than one space group, as a statement about the physics and not about weak data.
[`LAUE_CLASS_NOT_SEPARABLE`](diagnostics-indexing.md#laue_class_not_separable) fires when its members span more than one Laue class.
[`EXTINCTION_SYMBOL_AMBIGUOUS`](diagnostics-indexing.md#extinction_symbol_ambiguous) gives each reason `best_or_none` abstained, and [`EXTINCTION_PRIOR_APPLIED`](diagnostics-indexing.md#extinction_prior_applied) what a declared prior removed.

### When the screen answers

`ExtinctionScreen.best_or_none` returns the leading class only when all of these hold:

- no class that is not refuted was left unfitted, since a `max_classes` cap or a cancelled run leaves a question unasked, which must not read as a clean answer;
- the class was fitted and is not refuted;
- it rests on at least one absence the data could test, or is the absence-free class itself, whose claim is that there is nothing to see;
- it leads the next surviving class by at least the decisive ΔBIC margin, 10 (`rietx.indexing.extinction.DECISIVE_DELTA_BIC`).

Otherwise it returns `None`, with the reason in `ExtinctionScreen.diagnostics`.
With a declared prior, only classes it leaves a member in can be returned and the margin is taken to the next such class; a class the prior emptied that the data prefer by the decisive margin makes it abstain.
A returned class still lists every space group it admits, and nothing in the package yields one space group from the data alone.

## One class

| Field | Holds |
|---|---|
| `ExtinctionCandidate.symbol` | the IT-style extinction symbol, derived from the members |
| `ExtinctionCandidate.representative` | the H-M symbol whose reflections were generated, which identifies the class |
| `ExtinctionCandidate.space_groups` | every space group in the class, in IT number order; with a declared prior only the members it admits, possibly none |
| `ExtinctionCandidate.excluded_groups` | the members a declared prior removed; empty without one |
| `ExtinctionCandidate.exclusion_reasons` | for each removed member, the declared facts it fails |
| `ExtinctionCandidate.special_positions` | for each kept member at which the declared Z′ is not whole, the special positions a formula unit needs |
| `ExtinctionCandidate.laue_classes` | `space_groups` grouped by Laue class |
| `ExtinctionCandidate.conditions` | the derived reflection conditions, such as `00l: l = 2n`, for a person to check |
| `ExtinctionCandidate.conditions_complete` | `False` when the conditions leave some absence unnamed; the absence set is what the screen uses either way |
| `ExtinctionCandidate.n_lines` | distinct lines this class predicts in range |
| `ExtinctionCandidate.n_absent` | lines of the lattice group this class forbids |
| `ExtinctionCandidate.n_testable` | of those, the ones the data can check; `None` when the class was not fitted or its fit raised |
| `ExtinctionCandidate.n_present` | testable forbidden positions carrying intensity: the refutation |
| `ExtinctionCandidate.forbidden_hkl`, `ExtinctionCandidate.forbidden_two_theta` | which reflections those are, and where, ° 2θ to four decimals |
| `ExtinctionCandidate.rwp`, `ExtinctionCandidate.gof`, `ExtinctionCandidate.chi2` | the class's own Le Bail fit, χ² the raw sum; infinite when it was not fitted or its fit raised |
| `ExtinctionCandidate.delta_bic` | BIC of this class minus BIC of the absence-free reference; negative favours this class, and `0.0` for a class never fitted |
| `ExtinctionCandidate.absences_rejected` | `True` when Hamilton's test finds restoring the forbidden reflections justified, so the absences are contradicted |
| `ExtinctionCandidate.screened` | whether this class's Le Bail fit ran |
| `ExtinctionCandidate.refuted`, `ExtinctionCandidate.refuted_reason` | refuted, and why, naming the first refuting reflection |
| `ExtinctionCandidate.diagnostics` | findings about this class |

Two classes' `delta_bic` values compare directly, since both are taken against the same reference, so their difference is itself a ΔBIC.

A class's diagnostics are about that class alone.
[`EXTINCTION_FORBIDDEN_INTENSITY`](diagnostics-indexing.md#extinction_forbidden_intensity) names the reflections that refuted it, [`EXTINCTION_SYMBOL_AMBIGUOUS`](diagnostics-indexing.md#extinction_symbol_ambiguous) fires on a class none of whose absences could be tested, and [`EXTINCTION_CONDITIONS_PARTIAL`](diagnostics-indexing.md#extinction_conditions_partial) on one whose printed conditions are incomplete.

### The symbol and its members

The symbol is derived from the member carrying the fewest absence-generating elements, with every position that extinguishes nothing written `-`: {`P 63`, `P 63/m`, `P 63 2 2`} is `P 63 - -`.
A monoclinic symbol keeps its `1` placeholders, as in `P 1 21/c 1`.
It is a label rather than a key: for an enantiomorphic pair the choice between the two screw axes is arbitrary, so `ExtinctionCandidate.representative` is what identifies the class and `ExtinctionCandidate.space_groups` is the answer.

The members of one class predict the same reflections at the same positions, so choosing among them is chemistry, and any member can be handed to `structure_from_candidate` for the fit that follows.
Members can also differ in Laue class: `P 6/m` and `P -3 1 m` share `P - - -` on a hexagonal lattice.
They then differ in which reflections are equivalent, which moves the intensity partition inside an overlapped multiplet and no position or absence, so a structure solution that follows runs once per Laue class.

### Which forbidden positions count

`ExtinctionCandidate.n_absent` and `ExtinctionCandidate.n_testable` answer different questions, and the gap between them is usually large.
Three kinds of forbidden position are not observations:

- one outside the fitted range, or with no channel within ±½ FWHM of it;
- one overlapping a line the class still allows, in any emission line, so a Kα2 image on a forbidden Kα1 position is not read as forbidden intensity;
- one whose window this class's own fitted pattern already fills: the model must predict less intensity there than the test's own detection threshold.

The third is why `n_testable` waits for the class's fit, and why it is `None` rather than zero before one.
A window carrying a neighbour's tail measures how well that tail is modelled, not whether the absence holds.
Measured on the corundum pattern over 20–90°: at sham positions 1–3 FWHM from an allowed line, where no reflection of any kind is predicted, the same 3σ test fired on 40–50 % of probes and reached 24.7σ, on the low-angle flank only, which is the unmodelled axial tail.
Requiring the model to be quiet means no error in a neighbour's tail, not even a total one, can manufacture a refutation.

Only testable absences enter the comparison too.
A class whose extra absences all hide under allowed neighbours would otherwise win on parsimony alone, with no measurement behind it.

Refutation is one-sided by construction.
A class asserts absences, so intensity where it forbids one contradicts it; a class claiming too few absences asserts nothing the data can falsify, and is outranked rather than refuted.
The one other way a class is refuted is a Le Bail fit that raised, which `ExtinctionCandidate.refuted_reason` says.
A testable position carrying intensity refutes a class whatever its ΔBIC.
A single refuting position can still be an impurity line rather than a violated absence, so check it against the candidate's unmatched observed lines (`LeBailValidation.unmatched_observed_two_theta`) before dropping the class.

## Declaring what the chemistry rules out

The members of one class give identical patterns, and `restrict` is where the chemistry that chooses among them is declared.

```python
import rietx as rx

prior = rx.ExtinctionPrior(sohncke=True)
print(prior.declared())          # {'sohncke': True}
```

| Field | Holds |
|---|---|
| `ExtinctionPrior.sohncke` | `True`: only Sohncke groups, with no inversion, mirror or glide (an enantiopure chiral compound); `False`: only the others |
| `ExtinctionPrior.centrosymmetric` | `True` or `False`: only groups with, or without, an inversion centre (a second-harmonic signal says `False`) |
| `ExtinctionPrior.polar` | `True`: only the polar groups, whose point group leaves a direction fixed (a pyroelectric response); `False`: only the others |
| `ExtinctionPrior.z` | formula units per cell; with `formula`, removes the groups whose orbits cannot hold that content |
| `ExtinctionPrior.density` | measured density in g/cm³, which fixes Z through the formula weight and the screened cell's volume; needs `formula` |
| `ExtinctionPrior.formula` | the formula unit, written as a chemist writes it (`"Cu12Sb4S13"`); a fractional count declares a shared site |
| `ExtinctionPrior.declared` | the method returning the facts actually declared, by name |

Each field is `None` by default, which declares nothing, and each is read off the group's own operators.
A contradictory declaration, `sohncke=True` with `centrosymmetric=True` or `polar=True` with `centrosymmetric=True`, is refused when it is built, and so are a `density` without a `formula` and a `formula` with neither `z` nor `density`.

The prior filters members and nothing else.
Every class is still fitted and ranked on the data, `ExtinctionCandidate.excluded_groups` names what it removed, and `EXTINCTION_PRIOR_APPLIED` reports it, as a warning when it emptied the class the data rank first.
A class the prior empties stays in the ranking, so a declaration the data contradict is visible: a P 2₁/c specimen declared enantiopure gets no chiral answer, because `best_or_none` abstains.

<!-- api-doc: no-exec — it runs one Le Bail fit per extinction class -->
```python
screen = rx.determine_extinction_symbol(data, candidate, ins,
                                        restrict={"sohncke": True})
```

On a P 2₁ specimen declared enantiopure, the answer is `P 1 21 1` holding `P 1 21 1` alone, where the data alone leave {`P 1 21 1`, `P 1 21/m 1`}.

### The content per cell

With `z` and `formula`, a group is removed when some element's atoms per cell, Z times its count in the formula, cannot sit on whole orbits of the group.
The orbits are derived from the group's operators; a Wyckoff position with no free parameter is one orbit and holds its count once.
This is the test of an ordered model.
An element written with a fractional count (`Cu0.5Au0.5`) shares a site, and is not counted.
Where Z is not a whole multiple of a kept member's general multiplicity (Z′ below one, or 3/2), the member stays and `ExtinctionCandidate.special_positions` names the special positions a formula unit then sits on.
A molecule there must carry that site's symmetry, which nothing declared says, so this is a statement and never an exclusion: a P 2₁ salt at Z = 2 keeps P 2₁/m, with each formula unit on an inversion centre or a mirror.
`ExtinctionCandidate.exclusion_reasons` names the fact each removed group fails.

A `density` gives Z = ρ·V·N_A / M on the screened cell, `ExtinctionScreen.z_from_density`.
It must sit within 8 % of the declared `z`, or, with none declared, of exactly one whole number, and `ExtinctionScreen.z` is the Z the filter used.
When it does not, nothing is filtered by Z, `ExtinctionScreen.density_contradicts_z()` is `True`, `EXTINCTION_PRIOR_APPLIED` is a warning and `best_or_none` abstains.

## On real data

On the GSAS-II fluorapatite tutorial pattern over 15–90°, the screen enumerates seven classes and fits all seven in under two seconds.
It returns `P 63 - -`, whose members are `P 63`, `P 63/m` and `P 63 2 2`, with one condition, `00l: l = 2n`, one testable absence and ΔBIC −15.7 against the absence-free class; every other class but `P - - -` is refuted by named reflections.
That is a complete answer rather than a hedge.
The mirror and the twofold axes that separate those three produce no absences, so no counting time distinguishes them, and both `EXTINCTION_GROUPS_NOT_SEPARABLE` and `LAUE_CLASS_NOT_SEPARABLE` say so, the last because `P 63 2 2` sits in a different Laue class from the other two.
Declared enantiopure, the same screen returns `P 63 - -` holding `P 63` and `P 63 2 2`.

α-Al₂O₃ is certified `R -3 c`.
On the round-robin corundum pattern over 20–90°, with the widths seeded from the peak list, the screen returns `R - c -` = {`R 3 c`, `R -3 c`} at ΔBIC −3435, with six of its ten forbidden lines testable and all six absent: the certified group listed, never chosen, beside the non-centrosymmetric partner no counting time separates from it.
`ExtinctionScreen.profile_rwp` reads 0.259 there.

Read `ExtinctionScreen.profile_rwp` before believing a refutation anyway.
Every class is fitted with the shared instrument frozen, so a poor shared fit is a poor screen, and the quiet-model rule bounds what a neighbour can do rather than what a wrong profile can.
Same specimen and certified cell over the whole 5–150° range with the round-robin instrument's declared widths: the shared fit reaches 0.262, four forbidden positions read as occupied, the certified class is refuted, and `best_or_none` returns `R - - -`, whose members exclude `R -3 c`.
The two arms' Rwp, 0.259 and 0.262, do not tell them apart.
Give the screen a range and a width law its profile fit can match, and read `ExtinctionScreen.profile_rwp` to check that it did.

What to do with each answer, as a procedure, is the agent skill's §7e ([For agents](agents.md) says how to get it).
