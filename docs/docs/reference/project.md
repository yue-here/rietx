# Project and run directories

A rietx project is a directory ending in `.rex`, and this page lists every file rietx writes into one, the fields of `project.json`, what `Project.open` checks, and the run directories a fit writes outside a project.

The tree comes from a project built from the `fap` example, so the entries are the ones a project holds.
`Project.create` makes the directory, `Project.open` reads it, and `rietx gui my_sample.rex` opens it in the GUI.
[About the project](../concepts/project.md) gives why a project is laid out this way.

```{include} ../_generated/project.md
```

## Creating a project

<!-- api-doc: no-exec — it creates a directory from the reader's own files -->
```python
project = rx.Project.create("my_sample.rex", pattern="my_sample.xye",
                            structure=structure, instrument=instrument)
project.fit()
project.save()

project = rx.Project.open("my_sample.rex")
```

`Project.create` copies the pattern file into the directory byte for byte, reads it, writes `project.json` and starts `history.jsonl` with a root node.
`pattern=` is a path, not a `PatternData`, because the file's bytes and its esd column are what the project keeps.
Its other keywords set the first settings: `mode=`, `plan=`, `two_theta_limits=`, `excluded_regions=`, `reader_options=` (`block` or `scan`, recorded as the reader call) and `ui=`.

`Project.create` refuses a directory that already holds a `project.json`, a pattern file that does not exist, and a time-of-flight pattern.

## Opening a project

`Project.open` resumes at the history head.
It re-checks every binding rather than assuming it, and each failure raises with its own message, because each has a different cause and a different fix:

| Refused when | Raises |
|---|---|
| the directory holds no `project.json` | `FileNotFoundError` |
| `project.json` was written under another major version of the project format | `ValueError`, naming both versions |
| `project.json` lists no pattern, or more than one | `ValueError` |
| the pattern file is missing from the directory | `FileNotFoundError` |
| the pattern file's bytes no longer hash to the recorded sha256 | `ValueError`: the file changed after the project was made |
| the pattern reads as time of flight | `ValueError` |
| the bytes match but this build parses them to different numbers | `ValueError`: a reader change, not a corrupt project, naming the recorded reader and options |
| `history.jsonl` is missing | `FileNotFoundError` |
| the history was recorded against a different pattern | `ValueError`, naming both fingerprints |
| the history log holds no node to resume from | `ValueError` |

A `project.json` that fails validation raises pydantic's error before any of these.
An older release's project may spell component paths the old way in its saved plan.
`Project.open` rewrites those paths in the text before reading it, so the plan's globs still free what they freed.

Opening appends a line to the history log before any verb runs.
Every verb that changes a project writes into its directory as it runs.
To look at a project without changing it, open a copy: `rietx gui PROJECT.rex --scratch` copies the directory byte for byte to a temporary one and opens that ([The command line](cli.md)).

## A project with no structure

`structure=` may be left out, which makes a pattern-only project: zero phases, for a pattern whose phase you do not know yet.

<!-- api-doc: no-exec — it creates a directory from the reader's own files -->
```python
project = rx.Project.create("unknown.rex", pattern="unknown.xye",
                            instrument=instrument)
```

Peak picking and indexing work over it, and the parameter table holds the instrument and the background.
Both routes out of it end in a phase: index the peaks and adopt a candidate cell, or build a Le Bail scaffold from a space-group symbol and the cell parameters that setting leaves free (`rietx.schemas.structure.lebail_scaffold`).
In the GUI it is the third answer to the wizard's structure step.

It cannot be refined.
A phase reaches the pattern only through `scale × |F|² × profile`, so with no phase only the background is left to fit, and a plan run over it would converge on the background and report success.
`Refinement.fit`, `Refinement.run_stage`, `refine_multi` and `refine_sequential` therefore raise `NoPhasesError` before they start.
`NoPhasesError.code` is the string `NO_PHASES`, which the GUI also gives as its reason for a disabled Run button:

```python
import rietx as rx

print(rx.NoPhasesError.code)
```

```text
NO_PHASES
```

`Refinement.predict` still works, because evaluating the background as it stands is not a refinement.

## The open project

An open project holds the session in seven attributes.

| Attribute | Holds |
|---|---|
| `Project.path` | the project directory |
| `Project.doc` | the `ProjectDoc`, which is `project.json` in memory |
| `Project.data` | the `PatternData` read back from the copied file |
| `Project.refinement` | the `Refinement`, positioned at the history head |
| `Project.history` | that refinement's `RefinementTree` |
| `Project.data_diagnostics` | what the pattern reader repaired or assumed on the last read |
| `Project.history_diagnostics` | what reading the history log repaired, on the last open ([The refinement history](history.md#repairs-on-read)) |

The two diagnostics lists are held in memory and are not `project.json` fields.
The pattern's repairs are a function of the bytes, the reader and its options, which the data reference already records.
The history's repairs are a function of the log and of the release reading it.

`Project.parameters`, `Project.fit` and `Project.run_stage` are the session verbs, with the meaning they have on `Refinement`.
Each takes the mode from the project's settings unless you pass one.
`Project.fit` takes the 2θ limits and the plan from them too, `Project.run_stage` the limits and the `phase_support_sigma` of the plan, and both record the run into `Project.live_dir`.
`Project.exports_dir` and `Project.live_dir` are the paths of `exports/` and `live/`.
`Project.data_ref` returns the pattern's `DataRef`.

## project.json

`ProjectDoc` is `project.json`, the half of a session that nothing else records.
The model state is in `history.jsonl`, whose head is the working state, so no parameter value is written in both places.
Every verb that changes the model commits a history node as it runs, so the work is on disk whether or not anyone calls `Project.save`.
`Project.save` rewrites `project.json` alone.

| Field | Holds |
|---|---|
| `ProjectDoc.patterns` | the data references, one per pattern |
| `ProjectDoc.plan` | the plan the next run will use, as a `PlanSpec` |
| `ProjectDoc.mode` | the intensity mode the next run will use |
| `ProjectDoc.two_theta_limits` | the range the next run will fit |
| `ProjectDoc.excluded_regions` | 2θ regions masked out of the residual |
| `ProjectDoc.indexing` | the next indexing run's controls |
| `ProjectDoc.history_file` | the log's filename inside the directory |
| `ProjectDoc.format_version` | the version of the `.rex` format ([Compatibility](compatibility.md#the-six-version-strings)) |
| `ProjectDoc.package_version` | the version of rietx that wrote it |
| `ProjectDoc.created_utc`, `ProjectDoc.updated_utc` | when it was created, and when it was last saved |
| `ProjectDoc.ui` | keys a front end persists, with no schema |

The plan, the mode and the limits are what `Project.fit` and `Project.run_stage` will be called with.
A history node records a mode and limits too, as the ones a past run used.
The document says what the next run will use.
Before the first run there is no node to ask.

`ProjectDoc.patterns` is a list because stacking several patterns into one joint residual is a later milestone's work.
A project holds one pattern today, and `Project.open` refuses a document carrying more rather than opening the first.

`ProjectDoc.ui` has no schema on purpose.
A front end owns those keys and the document only stores them, so a layout change is not a schema change.

## The pattern reference

The pattern file is copied byte for byte, because the reader takes σ from the file's own esd column.
`Project.data_ref` returns the `DataRef` that makes those bytes trustworthy on re-open.

| Field | Holds |
|---|---|
| `DataRef.filename` | the pattern file's name inside the directory |
| `DataRef.sha256` | the digest of the file as copied, which catches an edit in place |
| `DataRef.fingerprint` | the digest of the parsed 2θ and intensity arrays, which catches a change of reader |
| `DataRef.reader`, `DataRef.options` | which pattern format claimed the file, and the reader options it was read with |
| `DataRef.n_points`, `DataRef.two_theta_range` | the number of points and the 2θ range |
| `DataRef.has_sigma` | whether σ was measured, from an esd column or the format's own counting convention, rather than the Poisson fallback |

The reader call is part of the reference, because a pdCIF holding a measured and a calculated block is a different pattern depending on the block.
Agreeing bytes with a disagreeing fingerprint mean the reader changed, and the file is intact.
`DataRef.has_sigma` is a property of every fit in the project that is invisible once the data are read, so it is written down.

## Fit range and excluded regions

`Project.set_excluded_regions` records regions to leave out of the fit, in the document and on the data together.
They live in `project.json` because they are protocol that neither the pattern file nor a history node records.
An inverted or empty interval is refused rather than reordered.

`Project.fitted_mask` answers which channels the next run fits: the excluded regions intersected with `ProjectDoc.two_theta_limits`.
`rietx.project.fitted_mask` asks the same of any pattern:

```python
import rietx as rx
from rietx.examples import examples_dir
from rietx.project import fitted_mask

data = rx.read_pattern(examples_dir() / "11BM_NAC.fxye")
print(len(data.two_theta), int(fitted_mask(data, (2.0, 24.0)).sum()))
data.excluded_regions = [(7.4, 7.6)]
print(int(fitted_mask(data, (2.0, 24.0)).sum()))
```

```text
59498 22003
21803
```

On the 11-BM NAC pattern, limits of 2–24° keep 22 003 of 59 498 channels, and excluding 7.4–7.6° as well removes 200 more.

## Run directories outside a project

A fit records itself into a run directory unless recording is switched off ([How to watch or stop a running fit](../guides/watch.md)).
A fit from a project records into the project's `live/`.
Any other fit records under `.rietx/runs/` in its working directory, one directory per fit, named for the date, the time and the process id, such as `20261020-030217-66184`.
A fit given `telemetry=` records into the directory it names instead.

```text
.rietx/runs/
    .gitignore
    20261020-030217-66184/
        events.jsonl
        snapshot.json
        summary.txt
        meta.json
        status.json
        run.lock
```

The generated table above gives what each file holds.
The `.gitignore` holds `*`, so runs stay out of `git status`.
rietx writes it only into a runs root it chose itself, and leaves a directory named with `telemetry=` alone.

Two directories are spelled `.rietx`, and they have nothing to do with each other.
`$HOME/.rietx` holds the GUI's per-user state: the recent list and the theme.
`--state-dir` or `RIETX_STATE_DIR` moves it.
The runs root is relative to the working directory, and no environment variable moves it.
A fit run inside somebody else's package leaves `.rietx/` in their working directory, and `RIETX_TELEMETRY=0` is how a process declines.

### Retention

The first time a process records under a runs root that rietx chose, it prunes that root by age and size, never by count.
When the root holds more than 1 GiB, rietx deletes finished runs older than a week, oldest first, until the root is under 1 GiB.
If the root is over the limit with nothing old enough to delete, rietx warns and keeps everything.
A directory is deleted only if its name is a run id, it sits directly under the root, and its `meta.json` carries rietx's record tag, so a directory a user made there is never pruned.

### What a run records

`events.jsonl` holds every free parameter's value at every recorded evaluation, with the stage boundaries and the statistics at each.
`snapshot.json` holds the observed, calculated and difference curves of the last finished stage, decimated for drawing, and is rewritten each stage.
No pattern file is copied into a run.

The decimation keeps the minimum and the maximum of every curve in each of 2000 bins, the 4000-point budget the GUI and the comparison page use too.
Where the curves' extremes fall at different points a bin keeps more than two, so the drawn count can pass 4000.
A long pattern reaches a run as a picture of itself, and a short one arrives nearly whole: the fluorapatite pattern's 5753 points reached the snapshot as 5221.

`meta.json` holds the run's label, its start time, the rietx version, the working directory and the command line.
`status.json` holds the state (`running`, `done`, `failed` or `cancelled`), the process id and host, a heartbeat time, the current stage and its index of how many, and Rwp, the goodness of fit, χ² and the number of free parameters at that stage.
A series member's run adds its place in the series, and a run that stopped recording, or declined a stop request, says why.
`run.lock` is held locked while the fitting process lives, and `cancel` appears when a viewer asks the fit to stop.

The run directory carries no version string ({ref}`provisional-by-declaration`).
A run holds every free parameter's trajectory and most of the observed pattern, so set `RIETX_TELEMETRY=0` where the refinement is confidential and the working directory is shared.
