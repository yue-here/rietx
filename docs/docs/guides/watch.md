(guide-watch)=
# How to watch or stop a running fit

Run `rietx watch` in the directory the fit was started from, and it lists every recorded run, plots the one you pick and gives a running fit a stop button.

Every fit records itself without being asked, so this works for a fit started from a script, a notebook or an agent.
To stop a fit from your own code instead, pass it a `CancelToken`.

## Watch a fit

```console
$ rietx watch --open
```

The page lists the runs under the working directory, newest first, and shows the newest until you select another.
The selected run shows its status line, the observed and calculated pattern as of the last finished stage, and its event log.
`--port` sets the port (8899 by default).

A fit records into `.rietx/runs/` under the directory it ran in.
A fit started from a project records into the project's `live/` directory.
Pass a run's directory to open it directly:

```console
$ rietx watch ./my_sample.rex/live
```

Without a name, a run's row shows the name of its working directory or project.
Pass `label=` to the fit to name it, which tells forty fits started from one directory apart:

<!-- api-doc: no-exec — it refines your own pattern -->
```python
result = ref.fit(data, label="candidate-07 rutile")
```

The `state` column says whether each run is still going:

| State | Means |
|---|---|
| `running` | a process on this machine is writing the run |
| `done`, `failed`, `cancelled` | the run recorded how it ended |
| `abandoned` | the run says it is running, but no process is writing it, as after a crash |
| `unknown` | this machine cannot tell, for example because the run was written on another host |

## Stop a fit from the page

A `running` run has a stop button, which asks you to confirm.
The fit stops at its next residual evaluation, usually within a fraction of a second.
In the process running the fit, `fit` raises `RefinementCancelled`, as if the fit had been given a cancel token and the token had been set.
A script that doesn't catch the exception prints a traceback and exits.

The stages that finished are kept, and the model stands at the last of them.
The stage in flight is abandoned: it records no history node, and the model goes back to the values that stage started from.

Only a run being written on this machine can be stopped.
`rietx watch --read-only` serves the same page without the stop button.

## Stop a fit from your own code

Pass `fit` a `CancelToken` and call `CancelToken.cancel` from anywhere, usually another thread.
This script stops a fit from its own event stream when the first stage ends, so the run stops at the same place every time:

```{literalinclude} ../../../examples/guides/watch.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

<!-- output of examples/guides/watch.py -->
```text
started scale_bkg
ended scale_bkg converged
started zero_disp
ended zero_disp cancelled
abandoned: zero_disp
completed: ['scale_bkg']
working state at node n0001
```

The token is read between residual evaluations, so the fit never stops part-way through one.
`RefinementCancelled` carries three fields:

- `stage`, the name of the abandoned stage;
- `completed_stages`, a `StageResult` for each stage that finished, empty if the first stage was cancelled;
- `node_id`, the history node the model now stands at, or `None` if no stage finished or the history is switched off.

A cancelled fit therefore loses only the stage in flight.
The full script is `examples/guides/watch.py`.

## Read the events yourself

`events=` takes a function, called with each event as a dictionary, or a file path, to which each event is appended as one line of JSON.
Each event has a `kind`, a time `t` and a `data` dictionary.
The kinds are `fit_start` and `fit_end`, `stage_start` and `stage_end`, and `eval` for each residual evaluation.

Read `data` with `.get`, because a later version of rietx may add fields to a kind.
A cancelled fit's `fit_end` carries no statistics.
An exception raised in your function stops the fit, since the function is yours.

## Switch recording off

| Setting | Reaches |
|---|---|
| `RIETX_TELEMETRY=0` in the environment | this process and every process it starts |
| `telemetry=False` on a call | that call |
| `rietx.runs.set_enabled(False)` | this process, until you set it back |
| `telemetry="/some/dir"` on a call | records, into the directory you name |

The environment setting wins over `telemetry=`.
Only `rietx.runs.set_enabled(True)` turns recording back on in a process started with `RIETX_TELEMETRY=0`.
A run that is not recorded can't be watched, and has no stop button.

:::{warning}
A run directory holds every free parameter's value at every recorded evaluation.
It also holds the observed intensities at most of the pattern's points, so that the page can draw the plot.
Set `RIETX_TELEMETRY=0` where the refinement or the data are confidential and the working directory is shared.
:::

A failure to write a run never stops the fit.
The recorder stops, warns once per process and, where it can still write, says why in the run's `status.json`.

## See also

- [How to run a plan one stage at a time](stage.md) takes `events=` and `cancel=` too.
