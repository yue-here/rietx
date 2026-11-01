# Calling rietx from a program

A program drives rietx through the Python API a person types, stores an answer as JSON, and asks `capabilities()` what the installed build supports.

The package has no separate wire format.
Its objects are the API, and their JSON dumps are what a program stores or sends.

## The Python API

A program calls the same functions a script calls, such as `read_pattern`, `Structure`, `Refinement.fit`, `refine_sequential` and `build_report`.

<!-- api-doc: no-exec — it refines a pattern the reader supplies -->
```python
import rietx as rx

data = rx.read_pattern("my_sample.xye")
ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_default")
print(ref.summary())
```

[A first fit in Python](../start/first-fit.md) builds the structure and the instrument this block assumes.
`Refinement.summary` returns one string that says whether the fit is done, and why.

Versions up to 1.2 also had an `agent` module.
It took one JSON request and answered with an `{"ok": …}` envelope.
Version 1.3 removed it, after four traced rounds of agent runs recorded no call to it.
Its requests carried each pattern inline, so one lab pattern made a request of about 11 000 tokens and a 68-pattern series one of about 754 000.

### Errors

A failure raises an exception.

| Exception | Raised when |
|---|---|
| `ValueError` | rietx refuses a model, a plan, an argument or a file. A pattern reader's message names the file |
| `NoPhasesError` | a refining call gets a structure with no phases. It is a subclass of `ValueError` and carries the code `"NO_PHASES"`, so catch it before `ValueError` |
| `RuntimeError` | a call needs a fit that has not run, such as `Refinement.report` before the first `Refinement.fit` |
| `RefinementCancelled` | a `CancelToken` stopped the fit. It names the stages that completed and the last node committed ([Stop a fit from your own code](../guides/watch.md#stop-a-fit-from-your-own-code)) |

### Answer types

Each call that answers returns its own type.

| Call | Answer |
|---|---|
| `Refinement.fit` | `RefinementResult` |
| `refine_sequential` | `SeriesResult` |
| `index_pattern` | `IndexingResult` |
| `Refinement.suggest` | `SuggestionResult` |

An `IndexingResult` holds ranked candidate cells and has no single cell.
Indexing is declared provisional ({ref}`provisional-by-declaration`), so its answer type may change in any release.

### Reports

`Refinement.report` builds the `FitReport` for the last fit.
`Refinement.fit` with `stage_reports=True` also builds a report at the end of every stage, and leaves them in `Refinement.stage_reports_`.
A fit's final state is often its least informative one, so read the stage reports on a run you will act on ([Reports at every stage](../concepts/report.md#reports-at-every-stage)).

## Answers as JSON

Every answer type is a pydantic model, so a program on the other side needs nothing from rietx to read one.

`model_dump_json()` writes an answer as JSON text, and `model_validate_json` reads it back.
A non-finite float is written as the string `"Infinity"`, `"-Infinity"` or `"NaN"`, so an unbounded parameter limit survives the round trip.

`model_dump(mode="json")` returns a dict of JSON types, with one exception.
A non-finite float stays a Python float.
Python's `json.dumps` then writes it as a bare `Infinity`.
A strict JSON parser refuses that token.
Store or send the text that `model_dump_json()` writes.

```python
from rietx import Parameter

bound = Parameter(value=1.0)                 # no limits: min is -inf and max is +inf
text = bound.model_dump_json()
assert '"max":"Infinity"' in text
assert Parameter.model_validate_json(text).max == float("inf")
assert bound.model_dump(mode="json")["max"] == float("inf")   # a float, not a string
```

## Tool definitions

rietx ships no tool definition for a tool-calling model.
To offer refinement as a tool, wrap the Python API in your own tool.
Give it paths as arguments, such as a pattern file, a CIF or a project directory.
A pattern passed inline makes every call large.

A dedicated tool adds something where it gates, renders, audits or runs work in parallel.
An agent that has a shell needs none of those to refine a pattern.

## The agent skill

The rietx skill is the protocol an agent reads before it drives a fit.
It gives the order to free parameters in, the checks to make before a number is believed, and how to read a report that declines to answer.
[For agents](agents.md) says how to install it.

`Capabilities.skill_path` is the directory holding the copy this build carries, or `None` where the build carries none.
`rietx skill --path` prints the same directory.
In a checkout of the repository it is `docs/skill/rietx/`.

<!-- api-doc: no-exec — it prints an absolute path that differs per install -->
```python
import rietx as rx
from pathlib import Path

print(Path(rx.capabilities().skill_path, "SKILL.md").read_text())
```

## `capabilities()`

`capabilities()` returns a `Capabilities` object that says what the installed build supports.

Each arm is read from the registry it describes, so a new backend, plan or file format appears in it without an edit to this page.
Read the call when your program runs, and do not copy its contents into code.

```python
import rietx as rx

caps = rx.capabilities()
assert "rietveld" in caps.modes
assert any(backend.name == "numpy" and backend.available for backend in caps.backends)
choices = {plan.name: plan.when_to_use for plan in caps.plans}
```

### Version strings

`Capabilities.package_version` is the installed rietx version, the same string as `rietx.__version__`.
It moves with every release.

Six more strings version the data contracts, and each moves on its own:

- `Capabilities.schema_version`, the pydantic models;
- `Capabilities.report_thresholds_version`, the `FitReport` gates and thresholds;
- `Capabilities.event_schema_version`, the streaming event ladder;
- `Capabilities.project_format_version`, the `.rex` project directory;
- `Capabilities.textdoc_format_version`, the `.rxt` text document;
- `Capabilities.indexing_thresholds_version`, the indexing gates and the grade and caveat vocabularies.

[The six version strings](compatibility.md#the-six-version-strings) says what a change to each means.
Store the contract versions beside any answer you store.
A threshold compared across two `report_thresholds_version` values compares two different tests.

### Arms

| Arm | Holds |
|---|---|
| `Capabilities.backends` | one `BackendCapability` per Jacobian backend `backend=` accepts |
| `Capabilities.solvers` | the names `solver=` accepts |
| `Capabilities.modes` | the fit modes: Rietveld, Le Bail and Pawley |
| `Capabilities.plans` | one `PlanCapability` per plan preset |
| `Capabilities.radiations` | one `RadiationCapability` per source kind `Instrument.source` accepts |
| `Capabilities.anodes` | one `AnodeCapability` per laboratory anode |
| `Capabilities.extra_component_kinds` | the `kind` values `Instrument.extra_components` accepts ([Extra components](instrument.md#extra-components)) |
| `Capabilities.reader_formats` | one `ReaderCapability` per pattern format `read_pattern` recognises |
| `Capabilities.reader_options` | one `ReaderOptionCapability` per reader keyword |
| `Capabilities.project_formats` | one `ProjectFormatCapability` per format of another program's refinement this build reads ([How to open a GSAS, TOPAS or FullProf refinement](../guides/foreign.md)) |
| `Capabilities.search_presets` | one `SearchPresetCapability` per indexing search preset |
| `Capabilities.indexing_engines` | one `EngineCapability` per indexing engine |
| `Capabilities.crystal_systems` | the crystal systems in the order an indexing search enters them, from cubic to triclinic. Each system takes longer to search than the one before it |
| `Capabilities.centrings` | for each crystal system, the Bravais centring letters it admits |
| `Capabilities.shift_templates` | the systematic-shift models the indexing screen can fit |
| `Capabilities.features` | feature flags, name to true or false |
| `Capabilities.compiled_kernels_unavailable` | why the compiled kernels did not load, or `None` where they did |

A feature flag is computed from the thing it reports, such as a schema field's presence or a top-level function's existence.
It turns true by itself in the release that adds the feature.
`features["compiled_kernels"]` says whether the compiled kernels loaded, and `features["compiled_kernels_active"]` whether the next fit will use them.

### Backends

| Field | Meaning |
|---|---|
| `BackendCapability.name` | the value to pass as `backend=` |
| `BackendCapability.available` | whether the backend's optional dependency imports on this machine |
| `BackendCapability.experimental` | true for a backend kept for validation and not for production fits |
| `BackendCapability.requires` | the distribution to install, or `None` when the backend is always available |
| `BackendCapability.dtype` | the precision the backend computes at |

### Plans

| Field | Meaning |
|---|---|
| `PlanCapability.name` | the preset name `plan=` accepts |
| `PlanCapability.title` | a short title for a menu |
| `PlanCapability.description` | what the preset frees, in order |
| `PlanCapability.modes` | the fit modes the preset runs under |
| `PlanCapability.when_to_use` | the situation the preset is for |

A program can offer the choice in its own interface without a hard-coded list.
[Plan presets](plans.md) draws each preset's stages.

### Radiations

`Capabilities.radiations` lists every source kind.
Read it before `Capabilities.anodes`, which describes the X-ray kind alone.
A program that reads only the anodes would conclude that the build handles X-rays only.

| Field | Meaning |
|---|---|
| `RadiationCapability.kind` | the `kind` value to write in `Instrument.source` |
| `RadiationCapability.title` | a one-line name |
| `RadiationCapability.scatterer` | what does the scattering, and so whether the amplitude falls off with Q |
| `RadiationCapability.anomalous_dispersion` | whether the source carries anomalous dispersion (f′ and f″) |
| `RadiationCapability.max_emission_lines` | how many wavelengths the source can carry: `None` for no limit, 1 for a source that is one wavelength |
| `RadiationCapability.polarization_refinable` | whether the polarisation factor can refine |
| `RadiationCapability.harmonic_contamination` | whether the source accepts declared λ/n monochromator harmonics ([Monochromator harmonics](instrument.md#monochromator-harmonics)) |
| `RadiationCapability.magnetic_scattering` | whether a pattern from this source carries the magnetic scattering of a phase that declares moments |

Each flag is computed from the source class, so it changes by itself when the class gains the feature.
A listed kind is one the schema accepts, which does not mean every fit runs on it.
This version reads a time-of-flight bank and refines none ([Time-of-flight bank](instrument.md#time-of-flight-bank)).

### Anodes

| Field | Meaning |
|---|---|
| `AnodeCapability.name` | the anode name, such as `CuKa` or `CuKa1` |
| `AnodeCapability.wavelengths` | the emission wavelengths in Å |
| `AnodeCapability.kalpha1_only` | true for an entry such as `CuKa1`, where a monochromator has removed Kα2 and one line is left |
| `AnodeCapability.kbeta` | the Kβ wavelength for the contamination check, or `None` where it is not tabulated |

### Pattern formats

| Field | Meaning |
|---|---|
| `ReaderCapability.name` | the format's name |
| `ReaderCapability.title` | a title for a file dialogue |
| `ReaderCapability.extensions` | the file extensions |
| `ReaderCapability.sniff` | how a file is recognised as this format |
| `ReaderCapability.sigma` | where the intensity uncertainties come from, which differs between vendors |
| `ReaderCapability.options` | the reader keywords this format honours |
| `ReaderCapability.refuses` | why the format is declined, or `None` for a format that is read |

A format with a `ReaderCapability.refuses` string is one the build recognises in order to decline it, such as a peak list.
"This is the wrong kind of file" is a different answer from "this file cannot be opened".

| Field | Meaning |
|---|---|
| `ReaderOptionCapability.name` | the keyword, such as `scan` |
| `ReaderOptionCapability.kind` | `"str"` or `"int"`, so a form knows which control to draw |
| `ReaderOptionCapability.help` | what the keyword selects |

A reader keyword means the same in every format that takes it, so `Capabilities.reader_options` describes each one once.

### Refinement formats

| Field | Meaning |
|---|---|
| `ProjectFormatCapability.name` | the format's name |
| `ProjectFormatCapability.title` | a title for a file dialogue |
| `ProjectFormatCapability.extensions` | the file extensions |
| `ProjectFormatCapability.sniff` | how a file is recognised as this format |
| `ProjectFormatCapability.carries` | what the file holds beyond a structure, in words |
| `ProjectFormatCapability.reports_at` | where the reader reports its repairs: `"read"`, `"build"` or `"both"` |
| `ProjectFormatCapability.writes` | the function that writes this format, or `None` where this build writes none |
| `ProjectFormatCapability.refuses` | why the format is declined, or `None` for a format that is read |

### Indexing

| Field | Meaning |
|---|---|
| `SearchPresetCapability.name` | the value to pass as `preset=` |
| `SearchPresetCapability.title` | a short title |
| `SearchPresetCapability.description` | what the preset searches |
| `SearchPresetCapability.when_to_use` | the situation the preset is for |
| `SearchPresetCapability.default` | true for the preset `index_pattern` uses when none is given |
| `SearchPresetCapability.total_budget_seconds` | the ceiling on the whole run in seconds, or `None` for no ceiling |
| `SearchPresetCapability.typical_seconds` | the range of run times measured on known cells |
| `EngineCapability.name` | the engine's name |
| `EngineCapability.description` | how the engine searches |

An indexing search runs against a budget.
A program that has to promise a response time reads the ceiling here.
