# Refinement files from other programs

This page gives what `read_project_model` reads from a GSAS-II `.gpx`, a GSAS `.EXP`, a TOPAS `.inp` or a FullProf `.pcr`, what it answers with, how it recognises each format, and which TOPAS constructs it carries.

A file of this kind states a whole refinement: the phases, the instrument, and which parameters were free.
The free set is the part nobody can reconstruct from a CIF and a pattern.
A coordinate typed wrongly while transcribing one by hand stays symmetry-valid, so the fit runs and gives a plausible wrong answer.
[How to open a GSAS, TOPAS or FullProf refinement and write one back](../guides/foreign.md) gives the procedure.
[Files written for other programs](foreign-writers.md) gives the four writers, and [Models of other programs' files](foreign-models.md) gives each format's model field by field.
[Diagnostics: other programs' projects](diagnostics-projects.md) gives every code this page names.

These readers are declared provisional ({ref}`provisional-by-declaration`).
Their names and their models may change in a 1.x release, because each model mirrors its format and grows with the reader's coverage.
What a reader refuses is the stable part.

## Reading a file

`read_project_model` takes a path and works out which program wrote the file:

```python
import rietx as rx
from rietx.examples import examples_dir

model = rx.read_project_model(examples_dir() / "FAP.EXP")
print(model.format.name, model.stated.rwp)
print([note.code for note in model.diagnostics])

notes = []
structure = model.to_structure(diagnostics=notes)
print(structure.phases[0].name, structure.phases[0].space_group, len(structure.phases[0].atoms))
print([note.code for note in notes])
```

```text
gsas_exp 0.1005
['GSAS_EXP_BACKGROUND_NOT_CARRIED']
fap P 63/m 7
['GSAS_EXP_SPECIES_NORMALISED', 'GSAS_EXP_COORDINATES_SYMMETRY_FIXED', 'GSAS_EXP_SCALE_NOT_COMPARABLE']
```

`FAP.EXP` is GSAS's own refinement of the bundled fluorapatite pattern.
The read reported the background function rietx does not carry, and the build reported three repairs of its own.

Dispatch is on the content of the file and never on its extension.
Several unrelated programs write `.inp` files, and a reader that claimed one by its suffix would return a plausible wrong model for a finite-element input deck.
`identify_project_format` names the format that claims a file, reading only its head.
`read_topas_inp`, `read_fullprof_pcr`, `read_gsas_exp` and `read_gsas2_gpx` each read one format, for when you know what you have.

A file no format claims is refused.
The message names the formats this build reads and the three readers such a file usually belongs to:

```text
fluorapatite.cif is not a refinement file this build can read. Supported: GSAS-II .gpx [.gpx], FullProf .pcr [.pcr], GSAS .EXP [.exp, .EXP], TOPAS .inp [.inp]. A powder pattern goes through read_pattern, a GSAS-I instrument-parameter file through read_gsas_prm, and a PowderLine recipe through read_recipe.
```

A binary file gets "(it looks binary)" after its name, since none of those three readers is the right advice for it.

A construct a reader cannot represent raises a `ValueError` naming the file.
The reader never returns a half-built model.
A pattern reader repairs a file where it can report the repair.
A project reader refuses instead, because its output is a whole model and you could not see which part of it was the file's.

## The returned model

`read_project_model` answers with a `ProjectModel`.
It names the format and hands on that format's own model untouched.
It is not one shape with blanks where a file was silent, because a blank reads as an answer, and you could not tell "this file carried none" from "the reader found none".

| Field | Holds |
|---|---|
| `ProjectModel.format` | the `ProjectFormat` that claimed the file |
| `ProjectModel.path` | the file that was read |
| `ProjectModel.stated` | what the file stated, in that format's own model ([Models of other programs' files](foreign-models.md)) |
| `ProjectModel.diagnostics` | what the read repaired or assumed, kept whether or not you passed a list |
| `ProjectModel.to_structure` | builds a `Structure` from the model, with the file's refine flags |

`ProjectModel.to_structure` passes its keywords through to the format's own conversion:

| Format | Keywords |
|---|---|
| TOPAS `.inp` | `dataset=` picks one dataset of a multi-dataset file. `scale=` is `"file"` (the default) or `"rietx"`, which converts TOPAS's scale. `constraints=` collects the ties the file states. `aniso=True` builds a stated displacement tensor, which is otherwise refused. `cell_limits=False` drops the file's own cell bounds. `magnetic_symmetry=` names a magnetic group the file states as a symbol ([Structure files](structure-files.md#reading-a-magnetic-phase)) |
| FullProf `.pcr` | `nuclear_only=True` builds the nuclear phases alone where a magnetic phase does not map. `drop_parameter_ties=True` accepts the model without a codeword tie on an atom that would otherwise refuse |
| GSAS `.EXP` | `phase=` picks a phase by number |
| GSAS-II `.gpx` | `phase=` picks a phase by name or by number |

The keywords are not flattened into one vocabulary, because two formats' options that shared a name would not share a meaning.
An unknown keyword raises, naming itself.
With several phases and no `phase=`, the GSAS and GSAS-II conversions refuse to choose.

## The format registry

`capabilities()` publishes the formats this build reads:

```python
import rietx as rx

caps = rx.capabilities()
print([(f.name, f.extensions, f.reports_at, f.writes) for f in caps.project_formats])
```

```text
[('gsas2_gpx', ['.gpx'], 'both', None), ('fullprof_pcr', ['.pcr'], 'build', 'write_fullprof_pcr'), ('gsas_exp', ['.exp', '.EXP'], 'both', 'write_gsas_exp'), ('topas_inp', ['.inp'], 'both', 'write_topas_inp')]
```

[Calling rietx from a program](programs.md#refinement-formats) gives each field of the arm.
The order is the dispatch order, and the first format whose test passes claims the file.

| Format | Recognised by |
|---|---|
| GSAS-II `.gpx` | a pickle stream whose head carries one of GSAS-II's own top-level tree labels |
| FullProf `.pcr` | a `COMM` title line, which the format requires first |
| GSAS `.EXP` | 80-character records whose first 12 characters are a GSAS record key |
| TOPAS `.inp` | a TOPAS block opener or top-level directive at the start of a line, in the first 64 kB |

GSAS-II is first because it is the one binary format, and every other test reads the head as text and drops any byte that is not valid text.
TOPAS is last because a keyword anywhere in 64 kB is the weakest of the four tests.
A `.gpx` is not recognised by its pickle header alone: 11 of the 34 GSAS-II tutorial projects carry none.

### The diagnostics channel

`ProjectFormatCapability.reports_at` says which call takes your `diagnostics=` list:

- `"build"`, for a `.pcr`: every repair happens while FullProf's codewords become a `Structure`, so the list goes to `ProjectModel.to_structure`.
- `"both"`, for the other three. A `.EXP` reports the histograms it cannot carry while parsing, and the species it normalises while building. A `.inp` reports a rewritten species spelling or a translated origin suffix while parsing, and its magnetic group and moment readings while building.

Pass a list to both calls to collect either half without knowing which format claimed the file.
The read's half is also on `ProjectModel.diagnostics`, list or no list.
For a format that reports only at build, that tuple is always empty and says nothing either way.

### The registry entry

`ProjectFormat` is the registry entry the arm is built from.

| Field | Holds |
|---|---|
| `ProjectFormat.name` | the registry key |
| `ProjectFormat.title` | what a person calls the format |
| `ProjectFormat.extensions` | the conventional suffixes, informational only |
| `ProjectFormat.sniff` | how the format is recognised, in words |
| `ProjectFormat.carries` | what the file holds beyond a structure, in words |
| `ProjectFormat.reports_at` | `"read"`, `"build"` or `"both"`, as above |
| `ProjectFormat.matches` | the test the dispatch calls on a path |
| `ProjectFormat.read` | the format's reader, which returns its model |
| `ProjectFormat.to_structure` | the format's conversion to a `Structure` |
| `ProjectFormat.write` | the format's writer, or `None` where this build has none |
| `ProjectFormat.refuses` | why a format is recognised in order to be declined, or `None`. No format in this build sets it |

`ProjectFormatCapability.writes` is the writer's name rather than a flag, so a program learns what to call.
It is `None` for a `.gpx`, which this build reads and does not write.
A `False` there would be an answer about a format nobody had wired, so the empty value is `None`.

## TOPAS constructs and their stances

A TOPAS file states more than a structure, and dropping a construct can change the model.
So every construct the TOPAS reader knows is a `Feature` with a declared `Stance`, and a phase keyword with no stance fails a test.
What one file turned out to contain comes back on `TopasModel.coverage` as a `Coverage` of `Hit` rows.
A construct written as a library macro (`TCHZ_Peak_Type(…)`, `CS_L(…)`, `Specimen_Displacement(…)`) is met as well as one written in keywords, inside a phase or at dataset level.
The types live in `rietx.io.projects.coverage`.

| Name | Means |
|---|---|
| `Stance.READ` | carried into the model |
| `Stance.IGNORED` | about the run rather than the model, such as where output goes, and dropped without a message |
| `Stance.REPORTED` | about the model, met and not carried, and named in the diagnostics |
| `Stance.REFUSED` | met, and `to_structure` refuses to build a phase that states it |
| `Feature.name`, `Feature.what`, `Feature.why` | one construct, what it is, and the argument for its stance |
| `Feature.stance`, `Feature.keywords` | the stance, and the format keywords it governs |
| `Feature.macros` | the library macros that state the same construct |
| `Hit.feature`, `Hit.keywords`, `Hit.phases` | one construct met in a file, the keywords and macros the file actually wrote, and the phases that stated it |
| `Coverage.reported`, `Coverage.refused` | the hits of each kind |
| `Coverage.partial` | whether the file states anything about the model this import does not carry: a reported or refused hit, or an unread call |
| `Coverage.unread_calls` | names the file calls as `name(…)` without defining them, for which the reader has no row: a macro from an include the reader has not seen, or one spelt wrongly |
| `Coverage.summary`, `Coverage.summary_of` | the reported and refused hits in one line, and the same line for any list of hits |

A bare keyword spelt wrongly, such as `lor_fwhmm 0.1`, is not caught by `Coverage.unread_calls`.

The read names each reported construct, and each unread call, in [`TOPAS_FEATURES_NOT_IMPORTED`](diagnostics-projects.md#topas_features_not_imported).
It names a refused one in [`TOPAS_FEATURE_REFUSED`](diagnostics-projects.md#topas_feature_refused) and returns the model, so the numbers stay readable on `TopasModel.phases`.
`to_structure` then raises, naming the file and the construct, for any phase being built that states it.
The constructs this build refuses are a rigid body, merged occupancies (`occ_merge`), a scaled occupancy (`scale_occ`), stacking faults and a magnetic-only phase (`mag_only`), because each would read back as numbers that describe another model.
The one magnetic-only form that does build is the merged magnetic part described below.
Without a `diagnostics=` list the read is silent and returns the same model.

## TOPAS constraints as ties

A TOPAS file states constraints that its numbers alone do not carry: one parameter name written at several values, and equations over names (TOPAS Technical Reference § 2.3).
`to_structure(constraints=TopasConstraints())` reads them as rietx ties, and `apply_ties` declares them on a `Refinement`:

```python
import tempfile
from pathlib import Path

import rietx as rx
from rietx.examples import examples_dir
from rietx.io.projects.topas import read_topas_inp, to_structure
from rietx.io.projects.topas_ties import TopasConstraints, apply_ties

structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
ref = rx.Refinement(structure, instrument)
ref.set_vary(["phases.0.cell.*", "phases.0.atoms.*.biso"], True)
ref.tie_equal(["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"])
path = Path(tempfile.mkdtemp()) / "fap.inp"
rx.write_topas_inp(ref.fitted_structure, path, free=ref)

cons = TopasConstraints()
back = rx.Refinement(to_structure(read_topas_inp(path), constraints=cons), instrument)
print(apply_ties(back, cons))
print(cons.skipped)
```

```text
['phases.0.atoms.1.biso']
['phases.0.cell.b: not applied, already tied (symmetry or an earlier tie)']
```

The file writes Ca2's `beq` under Ca1's name, so it comes back tied to Ca1.
It writes the hexagonal cell's `b` under `a`'s name too, and that tie is skipped because the space group already makes it.

A value that is exactly a name, or an equation affine in names, becomes a tie on the first value that carries that name alone.
A moment stated as one name times a direction becomes a tie on the moment's degrees of freedom: the modulus, and for an antiparallel copy the opposite direction (θ → π − θ, φ → φ + π).
An equation in any other form keeps its value, and `TopasConstraints.skipped` says why.
A shared name stated at two values, a moment component's included, is refused.
The test is relative, to 1e-6 of the larger value, so a scale of 1e-6 against one of 1.5e-6 counts as two values.

`apply_ties` declares the free set the file's names state, then each tie, and returns the paths it tied.
It leaves a path as it is, and says why in `TopasConstraints.skipped`, when:

- the refinement has no such parameter;
- the path is already tied, by symmetry or an earlier tie;
- the path is locked;
- the refinement holds it (`unhold` it first if the file's flag should win);
- `set_vary` declines it;
- the parameter table refuses the tie.

`to_structure(scale="rietx")` converts TOPAS's scale from what the file states about its radiation: ÷ 100 under `neutron_data`, and ÷ K under `LP_Factor`.
It refuses a file stating neither.
A `"<name> magnetic part"` `str` of `mag_only` sites is merged back into its phase where it agrees with it ([Structure files](structure-files.md#reading-a-magnetic-phase)).
The magnetic widths and the extinction come back from parameters named `p<i>_magnetic_lor_size`, `p<i>_magnetic_lor_strain` and `p<i>_extinction`, since TOPAS has no keyword for them.
A file whose own parameter carries one of those names is read as the phase term, so each one read is reported as [`TOPAS_PHASE_TERM_READ`](diagnostics-projects.md#topas_phase_term_read).
