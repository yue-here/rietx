# A first refinement

A fit takes three objects and returns one. You supply a `PatternData` from
`read_pattern`, a `Structure` from a CIF, and an `Instrument` that describes the
diffractometer. The package returns a `RefinementResult`.

Throughout this manual, the `examples/` scripts, and the API calls the history
prints back at you, `rietx` is imported as `rx`.

## If you have no data yet

The package ships {{ N_EXAMPLES }} example projects. Each is a real specimen
with a published reference value, and each carries the refinement protocol its
acceptance suite measures, so a fit of one is comparable with a number
somebody else recorded.

```python
from rietx.examples import list_examples

for example in list_examples():
    print(f"{example.name:8} {example.title}")
```

```text
fap      GSAS-II LabData — fluorapatite (lab CuKα doublet)
nac      APS 11-BM — NAC + CaF₂ (synchrotron capillary)
```

One ordinary laboratory pattern and one synchrotron one;
`ExampleInfo.description` says what each teaches.

`rietx.examples.build_example` writes one out as a `.rex` project directory
([](files.md)) at its starting values. Nothing is fitted: the refinement is
yours to run.

```python
import tempfile

from rietx.examples import build_example

with tempfile.TemporaryDirectory() as parent:
    project = build_example("fap", parent)
    print(project.path.name)
    print(project.doc.mode, len(project.doc.plan.stages), "stages")
    print(len(project.data.two_theta), "points")
```

```text
fap.rex
rietveld 6 stages
5753 points
```

In the GUI the same three are listed in the empty state and open with one
click, the first open making your own copy ([](cli.md)).

## The minimal call

The files here are the ones the worked example below uses: an APS 11-BM pattern
of Na₂Ca₃Al₂F₁₄ and the COD structure of that phase.

<!-- api-doc: no-exec — the paths are the walkthrough's data files, which are not on the docs build's path -->
```python
import rietx as rx

data = rx.read_pattern("11BM_NAC.fxye")
structure = rx.Structure.from_cif("cod_1000236.cif")
instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)

result = rx.refine(data, structure, instrument)
print(result)
```

`print(result)`, which is `str(result)`, is the termination view a bare result
can answer without the model that produced it: per-stage status, every
diagnostic, provenance, agreement indices last.

```text
RefinementResult: converged (rietveld)
  stage scale_bkg: converged (10 it, ftol=1e-06)
  ...
  stage biso: converged (8 it, ftol=solver default), max|Δθ|/esd=0.000
  diagnostics: 2 unresolved
    WARNING BOUND_HIT: phases.1.atoms.0.biso refined to its bound — widen the bound or fix the parameter
    INFO CAPILLARY_OFFSET_UNAVAILABLE: ...
  provenance: rietx 1.3.0, backend=numpy, solver=trf
  Rwp 0.0933 / Rexp 0.0264 (GoF 3.53), Rp 0.0623, χ² 12.5, DW 0.18
```

`RefinementResult.status` is a plain string, one of `converged`, `max_iter` and
`diverged`. The second of those means the solver ran out of iterations. It does
not mean the fit failed.

`Statistics.rwp` is a fraction rather than a percentage: 0.0933 is the Rwp of
9.3 % you would quote in a paper, and every R-factor in the package is stored
this way. A `Refinement` session prints more ({ref}`printing-a-result`), and
[](results.md) says what each statistic measures.

One more line draws the fit:

<!-- api-doc: no-exec — it needs a result from the reader's own data -->
```python
result.plot(path="nac_fit.png", wavelength=0.4139090)
```

```{image} figures/nac-fit-light.png
:class: only-light
:alt: Observed points, calculated line, the obs minus calc difference below them and one row of reflection ticks per phase below that
```

```{image} figures/nac-fit-dark.png
:class: only-dark
:alt: Observed points, calculated line, the obs minus calc difference below them and one row of reflection ticks per phase below that
```

Reading down: observed points, the calculated line, the `obs − calc` difference
on the same axis at the same scale, then one row of reflection ticks per phase.
The residual sits directly under the peaks that caused it, and nothing comes
between them. Every series is named in the right-hand margin rather than in a
legend the eye has to look up; the fit statistics sit in the corner, because a
figure's title is its caption.

`wavelength=` puts λ on the 2θ axis, which is meaningless without it. The other
arguments window the pattern, change the axes and move the residual into a panel
of its own. {ref}`plotting-the-fit` takes them one at a time.

## `refine` or a `Refinement` session

`refine` runs one fit and discards the session. It is the right call when one
fit is all you need, and it keeps no history unless you ask for one
(`history=True`).

The object form keeps the session:

<!-- api-doc: no-exec — it refines the reader's own pattern -->
```python
ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_default")
result = ref.fit(data, plan="mccusker_structural")   # continues from the first
```

`Refinement` holds the models between calls, so the second `fit` starts where
the first stopped rather than from the CIF. Three things come with that:

- `Refinement.fitted_structure` and `Refinement.fitted_instrument` return the
  models as the last fit left them.
- `Refinement.history` records every stage as a restorable node, and it is on by
  default here. `Refinement.edit` puts a change to the model on the same record,
  so adding a phase is a recorded move rather than a fresh start.
  [](history.md) is what a node holds and how to go back to one.
- `Refinement.report` builds the `FitReport` with the compiled model attached,
  which `build_report` on a bare result cannot do.

Reach for the object form as soon as a fit needs a second attempt, which in
practice is most of the time.

## Le Bail before Rietveld

Get the peaks into the right places before you ask a structure to explain their
intensities.

A Le Bail fit (`mode="lebail"`) refines the cell, the zero shift and the profile
with the intensities extracted per reflection instead of computed from the
structure. It therefore converges from a much worse start, and it tells you
whether the profile is right independently of whether the structure is. Only
then does a Rietveld fit (`mode="rietveld"`, the default) face a fair question.
This is the IUCr guidelines' own advice for a partial or uncertain model
{cite}`mccusker1999`.

There is a second reason to run one. A Le Bail report flags observed peaks the
model does not account for, so an impurity phase shows up as unmatched peaks at
positions you can identify, before it can distort a structural refinement by
being absorbed into a background or a width.

```{image} figures/impurity-peak-light.png
:class: only-light
:alt: Two zoomed panels near 7.5 degrees; the left has an observed peak with no calculated intensity, the right fits it
```

```{image} figures/impurity-peak-dark.png
:class: only-dark
:alt: Two zoomed panels near 7.5 degrees; the left has an observed peak with no calculated intensity, the right fits it
```

The Le Bail fit knows nothing about CaF₂, so the line at 7.52° is observed
intensity the model cannot place, and the report says so. Adding the phase
accounts for it.

Only one of those directions carries evidence. A Le Bail intensity is extracted
from the counts in the reflection's own window, so a reflection the pattern does
not show is assigned almost nothing, and nothing in the report reads the
absence. Reading it takes a count of predicted positions carrying no intensity
above the fitted background. The indexing chapter's validation reports exactly
that, as `LeBailValidation.predicted_but_absent` ([](indexing.md)). Texture can
empty a reflection the same way, so either one shows up in the Rietveld fit that
follows, where the intensity is computed from the structure.

The cell is on the same footing. Where reflections are dense, extracted
intensities can index one pattern more than one way, so a Le Bail cell that fits
better than a structural model does can still be the wrong cell
{cite}`peterson2005`. Compare it against even a rough model before quoting it.

### With no structure at all

A Le Bail fit computes no structure factors, so it does not need a structure:
a space group and a unit cell are enough. In the GUI, step 2 of the new-project
wizard takes either a CIF or a typed cell, and choosing the second sets the mode
to `lebail`. Type the symbol first. The form then asks for the cell parameters
that symbol leaves free, which for `R -3 c` is `a` and `c`; the rest follow from
the symmetry and are not yours to give.

From Python the same scaffold is `rietx.schemas.structure.lebail_scaffold`,
which takes the symbol and all six cell parameters:

```python
from rietx.schemas.structure import lebail_scaffold

structure = lebail_scaffold("R -3 c", (4.7591, 4.7591, 12.9918, 90, 90, 120))
print(structure.phases[0].space_group, len(structure.phases[0].atoms))
```

```text
R -3 c 1
```

The one atom is there because a `Phase` cannot have an empty atom list. It
contributes nothing: `lebail` and `pawley` mode force-fix every atom parameter,
which [](model.md) lists as `ParameterRow.mode_fixed`. When you later have a
structure, `ref.edit(structure=…)` replaces the scaffold, and the mode goes back
to `rietveld`. [](indexing.md) reaches the same scaffold from the other side,
when the cell came from an indexing run rather than from you.

### Not even a cell

If you do not know the cell either, start from the pattern alone. The wizard's
third answer to step 2 is `None yet`, and `Project.create` takes no `structure=`
at all:

<!-- api-doc: no-exec — it creates a directory from the reader's own files -->
```python
project = rx.Project.create("unknown.rex", pattern="unknown.xye",
                            instrument=instrument)
```

That project has zero phases. Peak picking and indexing work over it, which is
how you find the cell: pick the peaks, index them, adopt a candidate, and the
project becomes the Le Bail one above ([](indexing.md) walks that loop). Until
it has a phase, refining it raises `NoPhasesError` and the GUI's Run button is
disabled. With no phase there is nothing but the background to fit, and a plan
run over one would converge on the background and report success. [](files.md)
has the detail.

## Worked example: NAC on 11-BM

`examples/nac_11bm.py` refines Na₂Ca₃Al₂F₁₄ against APS 11-BM synchrotron data
in three moves: a Le Bail fit, then the CaF₂ impurity that its report exposes,
then Rietveld. The test suite runs it on every push.

```sh
python examples/nac_11bm.py
```

```text
pattern: 59498 points, 0.50-59.99 deg, sigma from file: True
phase: Na2Ca3Al2F14, I 21 3, a=10.257 A, 6 asymmetric atoms

Le Bail:  status=converged  Rwp=0.1435  GoF=5.44  a=10.251214 A
Rietveld: status=converged  Rwp=0.0933  GoF=3.54
          a = 10.251216 +/- 0.000046 A (COD reference 10.257(1); high-accuracy powder ~10.2497-10.2506)
          [warning] BOUND_HIT: phases.1.atoms.0.biso refined to its bound
```

It goes on to print the report summary, its five worst regions, and the history
tree below.

The script is three blocks. First, read the pattern, the structure and the
instrument, and set the profile starting values in the right decade for 11-BM's
resolution:

```{literalinclude} ../../../examples/nac_11bm.py
:language: python
:dedent: 4
:start-at: data = rx.read_pattern
:end-before: "# --- Le Bail first"
```

Then the Le Bail fit, which refines the cell and the profile without the
structure, and tags the node it reached:

```{literalinclude} ../../../examples/nac_11bm.py
:language: python
:dedent: 4
:start-at: "# --- Le Bail first"
:end-before: "# --- Rietveld seeded"
```

Then the impurity its report exposed, added as a recorded model edit, and the
Rietveld fit that follows with a displacement stage appended to the preset:

```{literalinclude} ../../../examples/nac_11bm.py
:language: python
:dedent: 4
:start-at: "# --- Rietveld seeded"
:end-before: return data, ref, lebail, result
```

The imports, and the `main` that builds the report and prints the history, are
in the file itself.

Six things in it are moves that any later refinement repeats:

- One `Refinement` is the session. `Refinement.fit` can be called again, and the
  models carry over.
- Every stage commits a node. `Refinement.history` holds both refinements and the
  model edit between them, and `RefinementTree.tag` names a node to come back
  to:

  ```text
  t5544a638  13 nodes  data=11BM_NAC.fxye
   n0000  root                   —
  └─  n0001  stage:bkg              Rwp 3.1772
     └─  n0002  stage:zero             Rwp 1.0407
        └─  n0003  stage:cell             Rwp 0.1683
           └─  n0004  stage:profile_w        Rwp 0.1592
              └─  n0005  stage:profile          Rwp 0.1435  [lebail]
                 └─  n0006  edit_model:add CaF2 impurity phase —
                    └─  n0007  stage:scale_bkg        Rwp 0.1199
                       └─  n0008  stage:zero             Rwp 0.1199
                          └─  n0009  stage:cell             Rwp 0.0959
                             └─  n0010  stage:profile_w        Rwp 0.0959
                                └─  n0011  stage:profile          Rwp 0.0957
                                   └─ *n0012  stage:biso             Rwp 0.0933
  ```

  [](history.md) is the whole record.
- A plan is editable. `plan.stages.append(rx.Stage("biso", [...]))` adds a
  displacement stage after the preset's, and `Stage` takes fnmatch globs over
  the parameter dot-paths (`phases.*.atoms.*.biso`). [](model.md) is the path
  grammar and how to see which paths a glob actually reaches.
- `RefinementResult.parameter` looks one parameter up by path, with its esd:
  `result.parameter("phases.0.cell.a").stderr`.
- `RefinementResult.diagnostics` is the channel for "your answer is wrong
  although Rwp is fine". Read it every time. [](results.md) says what a
  diagnostic carries, beside the statistics it outranks.
- `build_report` turns the result into a `FitReport`: where the misfit is, what
  would fix it, and whether the package is confident enough to say so.

## The `RefinementResult` object

`RefinementResult.status` says whether the solver converged.
`RefinementResult.statistics` carries the agreement indices, of which
`Statistics.rwp` and `Statistics.gof` are the two usually quoted, and
`Statistics.n_points`, `Statistics.n_free_parameters` and
`Statistics.esd_inflation` are what make them interpretable.

The curves are on the result as `RefinementResult.y_obs`,
`RefinementResult.y_calc` and `RefinementResult.y_background`, over
`RefinementResult.two_theta`. `RefinementResult.plot` writes an
observed/calculated/difference figure with matplotlib (the `viz` extra).
[](results.md) goes through the rest of the object field by field: the
structure R-factors, the bonding geometry, and the two counts that say whether
the pattern supported the model.

Rwp is a fit statistic and not the answer. This package can show you a fit whose
Rwp improved while its displacement parameters and phase fractions moved away
from the truth. What it hands you instead is [the report](report.md).

## Your own data

The script above builds its structure and instrument in code, which is the
shortest way to show a whole fit. [](data.md) is the reference for doing that
with your own experiment: what each field of `PatternData`, `Structure` and
`Instrument` means, which of the three instrument presets matches your
diffractometer, and how to calibrate one on a standard and reuse it.
[](files.md) is the same ground from the file side, for data you already have on
disk.
