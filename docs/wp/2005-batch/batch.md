# WP-2005 batch, part 2: the codes that need a ruling

Written 2026-11-17 by a ghostshift runner, for the maintainer. It follows the gate as written
in `docs/milestones/generality.md` § The order. Each code was asked two questions in order.
Q1 asks whether the package should make this call at all: shown the number, would every
competent refiner act before quoting a result? Q2 asks, only for a code that passes Q1,
whether its threshold holds beyond the data it was tuned on.

*2026-11-21:* each of the 31 codes is answered in `rulings.md`. Nine are settled by Claude,
19 wait on the maintainer as consent lines, `HIGH_CORRELATION` has a full brief, and the two
magnetic codes are Mike's. Nothing below is approved yet.

## What is already done, and what is left

75 codes are in this WP's inventory (`inventory.json`). 11 were tiered before this session.
This session tiered 33 more in `src/rietx/_audit.py`, because each reports an act or a fact
(the WP handover lists them). **31 codes need a ruling**, in five classes. A sixth question
covers the responses this session held back.

| Class | Codes | Q1 | What the batch proposes |
|---|---|---|---|
| A | 12 | fails: a named refiner would quote the number | the warning goes; the number stays in the message or a field |
| B | 9 | passes | keep the code; approve its threshold at tier 3, or measure it first |
| C | 4 | passes | split one code into two, one per level |
| D | 2 | magnetic | Mike rules (memory: magnetic-path decisions are Mike's since 2026-11-04) |
| E | 4 | passes | tier 3 under the approved CELL_RUNAWAY convention, or wait on another row |

On this WP's 75 codes, Q1 demotes 12 (16 %). Q2 has demoted none yet, because no class-B
threshold was measured on three families in this session. In WP-2002 and WP-2003, Q1 demoted
23-33 % of items (the tally behind the maintainer's 2026-11-16 ruling to run WPs 2005-2007).

The generality judge read the 39 rows first drafted here and found six it could not pass
(`MODEL_FAR_FROM_DATA`, `PHASE_UNCONSTRAINED`, `LEBAIL_ALTERNATION_STOPPED`,
`SPECIES_FALLBACK_NEUTRAL`, `PATTERN_UNDERSAMPLED`, `DATA_SUPPORT_LOW`). They are back in
classes C and E below.

Every class-A and class-C change alters what a reader of some fit receives, so none lands
before the maintainer's ruling. The standard fit that `python -m tests.reader_output` runs
prints one of these codes, `RESOLUTION_UNCONSTRAINED`. Its class-B proposal changes only its
tier, so that print stays.

The rulings of 2026-11-03, 11-04 and 11-16 point one way for class A. Each reversed a
thresholded warning or action over a fit metric and chose "a field, and the caller decides"
(memory, settled-decision-reversals). Class A applies that ruling to the codes this WP owns.

## Class A: the warning fails Q1

Each row names a refiner who would quote the number anyway. The proposal is the record's
§ Demotion. Where the threshold only decides whether the code exists, the code goes and the
number becomes a field or stays in a field already there. Where the code also reports a
tier-1 or tier-2 fact, it stays at `info`.

| Code | Fires when | Who would quote anyway | Proposal |
|---|---|---|---|
| `SIZE_UNUSUALLY_SMALL` | size below 5 nm (`SIZE_FLAG_SIZE_A`), set from one TOPAS archive, one family | a refiner of 2-5 nm catalyst or quantum-dot particles | remove; the size is in `microstructure` already |
| `STRAIN_UNUSUALLY_LARGE` | `lor_strain` above 1.5 (`STRAIN_FLAG_WIDTH`), same archive | a refiner of ball-milled or cold-worked metal | remove; the strain is in `microstructure` already |
| `BISO_UNUSUALLY_LARGE` | Biso past the Lindemann melting amplitude (Gilvarry 1956, tier 2) | a refiner of a rattler or superionic site, as its own suggestion says | `info`; the fact is tier 2 |
| `HIGH_CORRELATION` | \|ρ\| above 0.98 (`CORRELATION_GUARD`) | anyone quoting a cell beside a correlated zero, whose esds already carry ρ | `info`; GSAS-II lists pairs above about 0.95 in its log and asks for no act (`docs/practice.md` § Correlations); `FLAT_DIRECTION` stays a warning |
| `RESTRAINT_TENSION` | a restraint more than 3σ from its target | a refiner who set a loose restraint on purpose | `info`, with the distance in σ |
| `LOW_ANGLE_UNMODELLED` | low-angle residual above 3× χ²_red, measured on one pattern (Ba₂FeSbSe₅) | a refiner keeping real diffuse scatter (issue #1219: three competent responses) | `info`; drop the suggestion, as #1219 asks |
| `AIR_SCATTER_UNDECLARED` | a 1/(2θ) column would remove 0.5 % of χ² | a refiner whose spline is stiff at the low edge (issue #1215: fires on 20 of 20 clean patterns) | `info`; name both explanations, suggest neither |
| `EXTRA_PEAK_ON_REFLECTION` | a declared extra peak within 0.08° of a reflection | a refiner modelling a shoulder or a stacking-fault peak at a Bragg position | `info` |
| `ROUGHNESS_UNCONSTRAINED` | refined roughness moves no intensity by 1 % | a refiner who wants the roughness esd as an upper bound | `info`, with the depression stated |
| `HARMONIC_FRACTION` | a harmonic fraction; a warning above 15 % | a beamline scientist with a detuned monochromator | one `info` record with the fraction and its esd, no threshold |
| `HARMONIC_ABSENT` | fraction below 1e-3 | (merges into the row above) | folded into the row above |
| `DISPERSION_NEGLECTED` | dispersion turned off and \|f\|² moves 2 % (info) or 5 % (warning) | someone reproducing a published fit made without f′, f″ | one `info` record with the largest change per element |
| `RESOLUTION_UNCONSTRAINED`, `ROUGHNESS_OUTSIDE_REGIME`: see classes B and C | | | |

Q2 is not asked of class A, by the gate's order.

**Question A for the maintainer.** Approve class A as a whole, or name the rows to keep as
warnings. Each approved row then needs its help entry's observation sentence updated and a
release-notes line for each removed code (the WP's task 5).

## Class B: Q1 passes, the threshold needs a ruling

Every competent refiner would act on these, so each stays. Each threshold is rietx's own and
needs tier 3 with the maintainer's approval. Q2 asks for three unrelated families; the
"families on disk" column says what the constant's own docstring records. None was measured
in this session.

| Code | Threshold | Why Q1 passes | Families on disk | Proposal |
|---|---|---|---|---|
| `BACKGROUND_ABSORPTION` | R² 0.25 (`staged.BACKGROUND_ABSORPTION_GUARD`) | a background that imitates a peak biases Biso up and scales down while Rwp improves (root CLAUDE.md) | "sane backgrounds 0.01-0.03, a 1° unpenalised spline 0.46", families not named | measure on three families, then approve |
| `ROUGHNESS_ABSORPTION` | R² 0.9 | at R² 0.9 the data cannot separate roughness from the ADPs | one synthetic pattern, cutoff varied | measure, then approve |
| `HUMP_TOO_NARROW` | 4× instrumental FWHM | a hump that narrow is a Bragg peak with no cell | "chosen from the corpus", one family | tier 3 under "where three families do not exist" (humps are rare) |
| `PATTERN_DEAD_CHANNELS` | `background.diagnostics.DEAD_*` | dead channels with shrunk σ dominate the weights | not recorded in the docstring; not checked | measure, then approve |
| `FROZEN_COMPILE_STALE` | χ² gap 1e-2 | `info`; says the reported χ² is the frozen compile's | 358 fits: Si 640c, FAP, Stephens brucite, QPA round robin | approve at tier 3 on both grounds, once the four are checked as separate families by lab, instrument and material |
| `PAWLEY_OVERLAP_UNRESOLVED` | relative esd 0.3 | `info`; root CLAUDE.md asks for this flag beside an equal split | LaB6 only | approve; 0.3 is I/σ ≈ 3.3, near the usual 3σ |
| `ABSORPTION_THICKNESS_MATTERS` | ΔBiso 0.05 Å² (`FLAT_PLATE_BIAS_MIN`) | `info`; says what the caller's declared thickness did | "about a typical Biso esd", no family | approve, or report ΔBiso whenever a thickness is declared (no threshold) |
| `ABSORPTION_PLATE_THICKNESS` | inline 0.7 of the optimal counts | `info`; says the specimen is thinner than optimal | none | lift 0.7 into a named constant at tier 3, or remove the code as experiment advice |
| `RESOLUTION_UNCONSTRAINED` | more than half the channels Lorentzian (inline in `staged.py`) | McCusker et al. (1999) § Synchrotron names the failure and the remedy | the standard LaB6 fit fires it, beside `RESOLUTION_NOT_POSITIVE` | tier 2 on McCusker, reading "predominantly" as "at more than half the points" |

**Question B for the maintainer.** Approve each class-B threshold now on the families listed,
or send the three marked "measure" back for a three-family measurement first.

## Class C: one code, two levels

The record's clause 2 says two consequences are two codes, never a threshold between levels.
All four codes in class C carry a threshold between their levels. One more code splits on a
fact (`DECLARED_RANGE_RESTORED`: a warning where the value sits on the restored limit). It is
tiered and keeps no response until split. Its split is mechanical and comes back with the
names in the next session.

| Code | Levels now | Proposal |
|---|---|---|
| `NEUTRON_RESONANT_ABSORBER` | info for a complex b; warning above 1000 barn | an `info` code for the complex b (tier 1), a warning code for the four black absorbers, Cd, Eu, Sm and Gd (a gap in the table, tier 1) |
| `ROUGHNESS_OUTSIDE_REGIME` | warning past sin θ_min (Pitschke's regime); info past half of it (inline 0.5) | keep the warning at the paper's edge; drop the info band, since its half is rietx's own |
| `DATA_SUPPORT_LOW` | info below five observations per parameter; warning below three | two codes on McCusker et al. (1999) § 9's two numbers; tier 2 once WP-2004 tiers `OBS_PER_PARAMETER_MIN` and `_PREFERRED`, which are its rows and unaudited |
| `LEBAIL_ALTERNATION_STOPPED` | info when converged; warning otherwise | the split rests on `LEBAIL_CONVERGED_REL` (tier 3, one family, an Rwp change), so it is a thresholded warning over a fit metric; propose one `info` record naming why the passes stopped |

**Question C for the maintainer.** Approve the four proposals, including the new code names.

## Class D: magnetic, for Mike

| Code | Fires when | Q1 reading |
|---|---|---|
| `MAGNETIC_WIDTH_MOVED_MOMENT` | freeing the magnetic width moved a released moment by more than 1 esd (`report.schemas.MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA`, 2004's row) | passes: a moment that moves with the width is not separately measured |
| `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` | a stage frees the magnetic width in the stage that first frees the moment | contested: a refiner with a strong magnetic signal frees both at once |

## Class E: Q1 passes, and the tier waits on a convention or another row

The generality judge sent these back. Each code's warning passes Q1. Its tier does not follow
from the rows already approved.

| Code | Why it waits | Proposal |
|---|---|---|
| `MODEL_FAR_FROM_DATA` | its `error` level is an act: `usable=False`, the series ladder escalates and quarantines on it. Two approved rows of that shape are tier 3 (`CELL_RUNAWAY`, B8; `SEQUENTIAL_UNRECOVERED`, 2026-11-03). The judge also derives a case against, not measured: on a frame with 1-2 counts per step a correct model sits near Rwp 0.7-1.0 | tier 3 citing B12, the row naming the series consequence; measure the low-count case before approving |
| `PHASE_UNCONSTRAINED` | it says out loud the absent-phase hold (`StageResult.held`, tier 3, approved 2026-11-04), the `CELL_RUNAWAY` shape | tier 3 on the hold's approval |
| `SPECIES_FALLBACK_NEUTRAL` | the record is a fact, but the substitution it records (neutral atom for an untabulated ion) is a fallback chain the table cannot see; what GSAS-II, FullProf and TOPAS do: not checked | survey the programs' default, then tier the fallback and the code together |
| `PATTERN_UNDERSAMPLED` | its five steps per FWHM cites McCusker et al. (1999) § 2, a paper not in the local corpus, and the peak census rests on two unaudited numbers (`SAMPLING_HEIGHT_FRACTION`, `SAMPLING_PROMINENCE_SIGMA`) | read § 2, tier the census numbers, then tier the code |

**Question E for the maintainer.** One convention question sits under the whole table. A
code that states a tiered threshold's outcome now takes tier 1 for its own part in three rows
(`BOUND_HIT`, `FLOOR_HIT`, `BACKGROUND_ORDER_AT_CAP`, as `STAGE_SLOW_DESCENT` does). Two
rows inherit their threshold's tier 2 instead (`ABSORPTION_MU_R_OUT_OF_RANGE`,
`BRINDLEY_OUTSIDE_REGIME`). A code that voices the package's own act takes tier 3. Should
one rule govern the first two shapes, and which? The judge's reading: "tier 1 for a fact,
tier 3 for an act" covers every approved row so far.

## The responses held back

A code row's response sets its level under a purpose, and a warning or error response needs a
silence pair: a fixture where the code fires and one where it stays silent
(`tests/test_silence.py`). This session built none. So the 23 tiered warnings keep no
response, and only eight `info` codes got one. `RESOLUTION_NOT_POSITIVE` would also move the
standard fit's printed line ("warning under every purpose" becomes "microstructure,
calibration").

**Question F for the maintainer.** Do responses fall under the 2026-11-01 reader-output
ruling? A response changes what `summary(deliverable=…)` prints for other fits than the one
`tests.reader_output` runs. If not, the next session gives the 23 their responses with a
silence pair each. If so, it brings them in one batch.

## The four inline literals

Each waits on its code's ruling above, because a removed code takes its literal with it.
`0.7` goes with `ABSORPTION_PLATE_THICKNESS` (class B). The two-FWHM edge and the 2σ channel
test go with `LOW_ANGLE_UNMODELLED` and its suggestion (class A). The half of sin θ_min goes
with `ROUGHNESS_OUTSIDE_REGIME` (class C). A literal that survives is lifted with a
bit-identity check before and after.
