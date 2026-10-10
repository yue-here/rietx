# Installation

`rietx` needs Python 3.11 or newer and installs from PyPI. Install it into a
virtual environment, one per project.

::::{tab-set}

:::{tab-item} macOS
:sync: macos

With [uv](https://docs.astral.sh/uv/getting-started/installation/), which
creates the environment and installs in one tool:

```sh
uv venv --python 3.12
uv pip install rietx
source .venv/bin/activate
```

With `pip`:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install rietx
```
:::

:::{tab-item} Linux
:sync: linux

With [uv](https://docs.astral.sh/uv/getting-started/installation/), which
creates the environment and installs in one tool:

```sh
uv venv --python 3.12
uv pip install rietx
source .venv/bin/activate
```

With `pip`:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install rietx
```
:::

:::{tab-item} Windows
:sync: windows

With [uv](https://docs.astral.sh/uv/getting-started/installation/), which
creates the environment and installs in one tool:

```powershell
uv venv --python 3.12
uv pip install rietx
.venv\Scripts\activate
```

With `pip`:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install rietx
```
:::

::::

Check it:

```sh
python -c "import rietx; print(rietx.__version__)"
```

That prints the version you installed, {{ release }} for the copy this manual
was built from. Then start with [](quickstart.md).

## Requirements

| Requirement | Purpose |
|---|---|
| Python ≥ 3.11 | |
| `numpy` ≥ 1.26 | the fp64 arrays the core computes in |
| `scipy` ≥ 1.11 | the trust-region least-squares solver |
| `pydantic` ≥ 2.6 | the schemas: validation, defaults, JSON round-trip |
| `gemmi` ≥ 0.6.5 | CIF reading, space groups, symmetry operations |
| `spglib` ≥ 2.4 | site symmetry, Wyckoff positions, cell reduction |
| `rietx-kernels` ≥ 1, < 2 | the compiled peak kernels, one wheel per platform ({ref}`the-compiled-kernels`) |
| `matplotlib` ≥ 3.10 (≥ 3.10.5 on Python 3.14) | figures: `RefinementResult.plot`, `PatternData.plot` and the report figures |

Those seven are the whole install, and nothing in that list is optional.
Matplotlib is imported only when a figure is drawn, so `import rietx` does not
load it. The install reads patterns and CIFs, applies every correction, runs
the staged refinement machinery, builds the report, draws the figures, indexes
an unknown cell, and keeps projects and history.

## Optional extras

No extra changes a refined number. Name one in brackets to install it, quoting
the argument because `zsh` reads bare brackets as a glob:

```sh
pip install "rietx[jax]"           # one extra
pip install "rietx[jax,docs]"      # several, comma-separated, no spaces
uv pip install -e ".[dev]"         # from a source checkout
```

| Extra | Installs | Purpose |
|---|---|---|
| `viz` | nothing | Empty since 1.7, and kept so an existing `rietx[viz]` install line still works. Matplotlib is now a dependency. |
| `gui` | nothing | Empty, and kept so an existing `rietx[gui]` install line still works. The refinement GUI, `rietx gui`, runs on a base install. Its built front end is committed inside the package with every library it draws with. |
| `jax` | jax | The `backend="jax"` Jacobian (`jacfwd`, chunked). |
| `torch` | torch | Experimental. `backend="torch"` (CPU fp64) and `backend="torch-mps"` (Apple GPU, necessarily fp32). About 500 MB, and slower than numpy on this hardware. It buys an independent opinion in the Jacobian-agreement matrix, and the forward model as a differentiable layer. It does not buy speed. |
| `docs` | sphinx, myst-parser, sphinxcontrib-bibtex, sphinx-design, furo | Builds this manual. |
| `notebooks` | ipykernel, nbclient, nbformat | Executes notebooks headless: the tutorial builder in `examples/tutorials/` and the display tests. Jupyter itself is yours to install. |
| `dev` | the `docs` and `notebooks` extras, pytest, pytest-xdist, hypothesis, ruff | The test suite. |

:::{note}
`backend="numpy"` is the default and the only backend a refinement needs. The
others hold the analytic Jacobian to an independent account: an Apple-GPU
refinement runs 46 to 182 times *slower* than numpy, because the work is
launch-latency-bound. Precision is not the trade either way. A GPU backend may
compute Jacobian columns in fp32, but the residual used for the cost and the
statistics, and the solve itself, stay fp64 on the host.
:::

(the-compiled-kernels)=
## The compiled kernels

The peak profile, its derivatives and the accumulation that scatters them onto
the pattern are evaluated by compiled kernels rather than by numpy expressions.
They are on by default and there is nothing to install or select. Measured on a
four-phase Cu Kα refinement they take the fit from 17.6 s to 8.9 s; on a
three-phase one, from 4.2 s to 2.2 s; on a two-phase synchrotron pattern with no
axial divergence, from 0.54 s to 0.40 s.

The kernels are written in Rust and ship as a separate package, `rietx-kernels`,
which `pip` installs with rietx. It is one compiled wheel per platform, between
140 and 250 kB: Linux (glibc) on x86_64 and aarch64, macOS on arm64 and x86_64,
and Windows on x64. There is no compile step and no cache. Importing the wheel
is the whole start-up cost. Releases before the kernels became a wheel compiled
them with `numba` on first use and cached the result in `~/.rietx/numba-cache`.
That directory is no longer read, and you can delete it.

The dichotomy indexing engine and the structure figure run on numpy alone, so
these kernels and the switch below do not reach them.

Turn the kernels off with `RIETX_COMPILED=0`, which needs no reinstall. Every
kernel has the numpy expression it replaces standing behind it, so refinements
run correctly, only slower. Use it for a run that has to reproduce another one
exactly.

```sh
RIETX_COMPILED=0 python my_refinement.py
```

An install without the wheel also runs the numpy path (see Troubleshooting).
It warns once per process, at the first refinement or the first
`capabilities()` call:

```text
RuntimeWarning: rietx's compiled kernels did not load, because importing
rietx_kernels raised ModuleNotFoundError (No module named 'rietx_kernels').
Fits run the numpy path, which is slower. Install the kernels with pip install
"rietx-kernels>=1,<2", or set RIETX_COMPILED=0 to choose the numpy path and
silence this warning.
```

The same warning names a wheel of another major version, whose kernel
interface this rietx does not call.

`capabilities()` answers the three questions separately, because they can
disagree. `features["compiled_kernels"]` is whether the wheel loaded here.
`features["compiled_kernels_active"]` is whether the next refinement will use
it. `Capabilities.compiled_kernels_unavailable` is the reason the wheel did not
load, or `None` when it did.

```python
from rietx import capabilities

caps = capabilities()
caps.features["compiled_kernels"]
caps.features["compiled_kernels_active"]
caps.compiled_kernels_unavailable
```

The compiled and numpy paths agree to within one or two units in the last place,
everywhere and on every platform. The accumulation is bit-for-bit identical,
being multiplication and addition in a fixed order with no library function in
it. The peak shapes call `exp`, whose last bit belongs to whichever library
provides it, so they land on the same doubles on some platforms and one part in
3e-17 away on others; peaks carrying the axial-divergence correction differ by
about 1e-16 on all of them, a different summation order for the same quadrature.
None of this is visible in a refined parameter or its esd.

## Checking an install

Ask the package rather than a table that goes stale. `capabilities()` reports
the versions, the backends, the plans, the modes, the anodes, the pattern
formats it can open, and the feature flags. For each backend it reports whether
the optional dependency imports *here*:

```python
from rietx import capabilities

caps = capabilities()
caps.package_version
[backend.name for backend in caps.backends if backend.available]
[fmt.name for fmt in caps.reader_formats]
```

`Capabilities.backends` is the field that answers "did my `jax` extra take?".
Each `BackendCapability` carries `BackendCapability.available` (does it import
here), `BackendCapability.requires` (the distribution to install) and
`BackendCapability.experimental`. [](agents.md) covers the rest of the object.

`rietx.__version__` is the version of the installed distribution, the same
string `capabilities().package_version` reports and every `Provenance`,
`TreeHeader` and `project.json` is stamped with, so a result and the package
that produced it can never disagree about it. A source checkout is the one
exception. If its `pyproject.toml` has moved on since its editable install,
the source's version is stamped instead, with the commit as a local label (see
Troubleshooting).

## Installing from source

Install from source to contribute, or to run against an unreleased change:

```sh
git clone https://github.com/yue-here/rietx
cd rietx
uv venv --python 3.12 && uv pip install -e ".[dev]"
```

Then run the suite. The fast selection is the unit and property tests. The full
selection adds the real-data acceptance suites, which refine certified standards
and take tens of minutes:

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # fast
.venv/bin/python -m pytest -n auto --dist loadgroup                 # everything
```

`--dist loadgroup` is not optional. It honours the marks that keep a shared
refinement fixture on one worker; plain `--dist load` silently refits, so the
suite refuses a parallel run without it and names what to pass. The suite
prints its own counts, and those counts depend on the extras installed: `jax` and
`torch` turn skips into passes.

## Troubleshooting

`zsh: no matches found: rietx[jax]`. `zsh` expanded the brackets as a glob.
Quote the argument: `pip install "rietx[jax]"`.

`rietx.__version__` reads `0.0.0+dev`. No distribution of that name is
installed, and what you imported is a source checkout sitting on `sys.path`
ahead of its own install. Install it (`uv pip install -e .`) before refining
anything: that string is stamped into the provenance of every result, every
history tree and every project file the session writes.

`RuntimeWarning: the installed rietx metadata says '1.4.0' but the source tree
it is imported from says '1.6.0.dev0'`. The checkout's version was bumped after
its editable install, which writes its metadata once, when it is installed.
Results are stamped with the source version and the commit
(`1.6.0.dev0+g` and twelve hex digits, `.dirty` if a tracked file was edited),
so they still name the code that ran. Reinstall (`uv pip install -e ".[dev]"`)
to make the two agree.

`No matching distribution found for rietx-kernels`. Your platform has no
`rietx-kernels` wheel, and the package publishes no source to build one from.
Two common cases are a musllinux system such as Alpine, and a free-threaded
Python build (3.13t or 3.14t), which cannot load the wheels that exist. Install
rietx without its dependencies and run the numpy path. The first refinement
warns once that the kernels did not load, and `RIETX_COMPILED=0` silences it.

```sh
pip install --no-deps rietx
pip install numpy scipy pydantic gemmi spglib matplotlib
```

## Validation and accuracy claims

[`docs/VALIDATION.md`](https://github.com/yue-here/rietx/blob/main/docs/VALIDATION.md)
tabulates every real-data assertion in the repository and says what each
tolerance is referenced to. It is generated from the suite, so it is the
accuracy claim, and nothing in this manual restates it.

It opens with the rule to read it under: judge a correction by what it changed,
never by ΔRwp. Of the eight corrections in v0.5, two provably cannot move Rwp,
one moves it the wrong way when it is right, and the two largest accuracy wins
are invisible in it.
