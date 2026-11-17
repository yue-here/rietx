(guide-embed)=
# How to embed rietx in an application

An application that ships rietx inside itself, such as a desktop program frozen with PyInstaller, has three things to settle.
Every fit records itself to disk unless told otherwise, the freeze has to carry files that no `import` names, and the compiled kernels choose their own thread count.

## Choose where the runs go

A fit with no `telemetry=` records a run under `.rietx/runs` in the working directory, so that `rietx watch` can list it.
In a desktop application the working directory may be the user's home or a directory inside the application bundle.
Settle it once, when the application starts, before the first fit.

To record nothing, set `RIETX_TELEMETRY=0` in the environment, or call `rietx.runs.set_enabled(False)`.

To keep the runs somewhere of your choosing, name a directory once for the whole process:

<!-- api-doc: no-exec — sets a process-wide setting that would leak into every later block of the build -->
```python
from rietx import runs

runs.set_root("/path/to/your/app/cache/runs")
```

`RIETX_RUNS_DIR` in the environment does the same, and `runs.set_root` outranks it.
The directory holds the run directories themselves, as a `telemetry=` path does.
A relative path is taken against the working directory at the call.
`runs.set_root(None)` goes back to the environment, then to the working directory.

The configured directory replaces the working directory's `.rietx/runs` and nothing else:

| A fit's run goes to | when |
|---|---|
| nowhere | `RIETX_TELEMETRY=0`, `runs.set_enabled(False)` or `telemetry=False` |
| the `telemetry=` directory | the call passed one |
| the project's `live/` directory | the fit belongs to a `.rex` project |
| the configured directory | `runs.set_root` or `RIETX_RUNS_DIR` names one |
| `.rietx/runs` in the working directory | none of the above |

rietx treats the configured directory as its own.
It creates it, puts a `.gitignore` in it and prunes it by the same rules as the working directory's: over 1 GiB, finished runs older than a week are deleted, oldest first.
To look at the runs, start `rietx watch` with the directory as its argument.
Started with no argument in a shell where `RIETX_RUNS_DIR` names a directory elsewhere, `rietx watch` prints where a fit started there records.

## Freeze it with PyInstaller

rietx carries its own PyInstaller hook, registered through PyInstaller's `pyinstaller40` entry point, so a freeze needs no `--collect-data`, `--hidden-import` or `--copy-metadata` for it.
The hook adds four things that following imports would miss:

- the files under the package that are not Python: the scattering, dispersion and attenuation tables, the example projects, and the pages the browser views serve;
- every module of the package, since some are imported by name at run time;
- `rietx_kernels`, the compiled kernels, which rietx imports inside a function;
- the package metadata, from which every result reads the version it stamps.

Without the kernels a frozen fit still runs, on the numpy path at about half the speed, and warns once.
Without the metadata it warns and stamps every result with a development version.
To check a frozen build, read `rietx.capabilities()` in it, or `rietx.model.compiled.unavailable()`, which is `None` when the kernels loaded.

Freeze from an environment holding only what the application needs.
PyInstaller follows imports into the optional `jax` and `torch` backends wherever they are installed, so a build environment that has them makes a much larger application.

## Set the kernel threads

The compiled kernels split their work across `min(8, cpu_count)` threads.
An application that already runs fits in parallel, one per process or one per thread of its own, sets `RIETX_COMPILED_THREADS=1` so the two layers do not compete for the same cores.
Set it before the first fit: the pool is built once per process.

## See also

- [How to watch or stop a running fit](watch.md) covers `rietx watch`, the stop button and what a run records.
- [The project reference](../reference/project.md) has the run directory's files and the retention rules in full.
